"""Probe v9: test the SQLCipher page layout hypothesis.

Evidence: page-1 header fragment bytes 16..23 == 10 00 02 02 00 40 20 20
  -> page size 4096, write/read version 0x40/0x20, **reserved bytes = 0x20 (32)**

SQLCipher v4 layout per page:
  encrypted area : bytes 16 .. pageSize-reserved        (page 1), 0..pageSize-reserved (others)
  tail (reserved): last 32 bytes = IV(16) || HMAC(16)

Key schedule when a raw 32-byte key is supplied (PRAGMA key = "x'..'"):
  pbkdf2_hmac_sha512(raw_key, salt=page1[0:16], iter, 64) -> 32-byte AES key + 32-byte HMAC key

Validation without the full key: decrypt the first ciphertext block at offset 16
with the page IV and compare against page1[8:16] (the plaintext header fragment).
That needs exactly one AES block decrypt per candidate.
"""
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Cryptodome.Cipher import AES  # noqa: E402

from wecom_reader.crypto.key_extract import (  # noqa: E402
    _enum_memory_regions,
    _read_process_memory,
    kernel32,
)

EXE = sys.argv[1]
DB_DIR = sys.argv[2]
ITERS = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [64000, 256000]
MAX_SECONDS = float(sys.argv[4]) if len(sys.argv) > 4 else 300

PAGE_SZ = 4096
RESERVED = 32


def pids_for(exe_name):
    import subprocess
    r = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/FO", "CSV", "/NH"],
        capture_output=True, text=True,
    )
    out = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line or not line.startswith('"'):
            continue
        parts = line.strip('"').split('","')
        if len(parts) >= 5:
            mem = parts[4].replace(",", "").replace(" K", "").strip() or "0"
            out.append((int(parts[1]), int(mem)))
    out.sort(key=lambda x: -x[1])
    return out


def check_sqlcipher(raw_key, page1, iters):
    salt = page1[:16]
    iv = page1[PAGE_SZ - RESERVED:PAGE_SZ - RESERVED + 16]
    expect = page1[8:16]
    for it in iters:
        try:
            dk = hashlib.pbkdf2_hmac("sha512", raw_key, salt, it, 64)
        except Exception:
            continue
        aes_key = dk[:32]
        block = AES.new(aes_key, AES.MODE_CBC, iv).decrypt(page1[16:32])
        if block == expect:
            return it
    return None


def main():
    dbs = {}
    for name in sorted(os.listdir(DB_DIR)):
        if not name.endswith(".db"):
            continue
        p = os.path.join(DB_DIR, name)
        if os.path.getsize(p) < PAGE_SZ:
            continue
        with open(p, "rb") as f:
            page1 = f.read(PAGE_SZ)
        if page1[:16] == b"SQLite format 3\x00":
            continue
        frag = page1[16:24]
        reserved = frag[7]
        dbs[name] = page1
        print(f"[*] {name}: page1 frag={frag.hex()} reserved={reserved}")
    print(f"[*] testing {len(dbs)} dbs with iters={ITERS}")

    # harvest all 64-hex (32-byte) tokens from memory
    t0 = time.time()
    tokens = set()
    total = 0
    for pid, mem in pids_for(EXE):
        h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
        if not h:
            continue
        try:
            for base, size in _enum_memory_regions(h):
                if size > 32 * 1024 * 1024:
                    continue
                data = _read_process_memory(h, base, size)
                if not data:
                    continue
                total += len(data)
                # 64 hex chars = 32-byte key
                for m in __import__("re").finditer(rb"[0-9a-fA-F]{64}", data):
                    tokens.add(m.group(0))
        finally:
            kernel32.CloseHandle(h)
        if time.time() - t0 > MAX_SECONDS:
            break
    print(f"[*] read {total/1e6:.0f}MB, {len(tokens)} 32-byte hex tokens")

    for tok in tokens:
        raw = bytes.fromhex(tok.decode())
        for name, page1 in dbs.items():
            it = check_sqlcipher(raw, page1, ITERS)
            if it:
                print(f"[+] SQLCIPHER MATCH db={name} iter={it} key={tok.decode()}")
                with open("_key_sqlcipher.json", "w") as f:
                    json.dump({"key": tok.decode(), "iter": it, "db": name}, f)
                return
    print("[-] no SQLCipher match")


if __name__ == "__main__":
    main()
