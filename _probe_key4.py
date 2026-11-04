"""Probe v4: correct per-page key derivation for both wxSQLite3 AES-128 (MD5)
and AES-256 (SHA-256) variants, tested against hex tokens harvested from the
client process memory.
"""
import hashlib
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Cryptodome.Cipher import AES  # noqa: E402

from wecom_reader.crypto.decrypt import (  # noqa: E402
    PAGE_SZ,
    SQLITE_HDR,
    generate_initial_vector,
)
from wecom_reader.crypto.key_extract import (  # noqa: E402
    _enum_memory_regions,
    _read_process_memory,
    kernel32,
)

EXE = sys.argv[1]
DB_DIR = sys.argv[2]
MAX_READ = int(sys.argv[3]) if len(sys.argv) > 3 else 2 * 1024 ** 3

HEX_RE = re.compile(rb"[0-9a-fA-F]{32,128}")
SALT = b"sAlT"


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


def page_key(raw_key, page_no):
    """Return (key_bytes, cipher_name) per SQLite3MultipleCiphers."""
    nkey = raw_key + struct.pack("<I", page_no) + SALT
    if len(raw_key) == 16:
        return hashlib.md5(nkey).digest(), "aes128"
    if len(raw_key) == 32:
        # sqlite3mcAES256 uses SHA-256 over raw_key + page_le32 + "sAlT"
        return hashlib.sha256(nkey).digest(), "aes256"
    return None, None


def try_decrypt_page1(raw_key, page1):
    """Non-legacy scheme: header bytes 16..23 are plaintext; restore from 8..15."""
    key, name = page_key(raw_key, 1)
    if not key:
        return None, None
    data = bytearray(page1)
    frag = bytes(data[16:24])
    data[16:24] = data[8:16]
    iv = generate_initial_vector(1)
    tail = AES.new(key, AES.MODE_CBC, iv).decrypt(bytes(data[16:PAGE_SZ]))
    data[16:PAGE_SZ] = tail
    if bytes(data[16:24]) != frag:
        return None, name
    out = bytes(data)
    if out[:16] != SQLITE_HDR:
        return None, name
    if out[100] not in (0x02, 0x05, 0x0A, 0x0D):
        return None, name
    return out, name


def main():
    dbs = []
    for name in sorted(os.listdir(DB_DIR)):
        if not name.endswith(".db"):
            continue
        p = os.path.join(DB_DIR, name)
        if os.path.getsize(p) < PAGE_SZ:
            continue
        with open(p, "rb") as f:
            page1 = f.read(PAGE_SZ)
        if page1[:16] == SQLITE_HDR:
            continue
        frag = page1[16:24]
        ps = (frag[0] << 8) | (frag[1] << 16)
        if not (512 <= ps <= 65536 and (ps & (ps - 1)) == 0 and frag[5] == 0x40
                and frag[6] == 0x20 and frag[7] == 0x20):
            print(f"[!] {name}: unexpected header frag {frag.hex()}")
            continue
        dbs.append((name, page1))
    print(f"[*] {len(dbs)} encrypted dbs, salts={len({d[1][:16] for d in dbs})}")
    print(f"[*] page size from header: {(dbs[0][1][16]<<8)|(dbs[0][1][17]<<16)}")

    cands = set()
    pids = pids_for(EXE)
    total_read = 0
    for pid, mem in pids:
        h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
        if not h:
            continue
        try:
            for base, size in _enum_memory_regions(h):
                if total_read > MAX_READ:
                    break
                if size > 32 * 1024 * 1024:
                    continue
                data = _read_process_memory(h, base, size)
                if not data:
                    continue
                total_read += len(data)
                for m in HEX_RE.finditer(data):
                    tok = m.group(0).decode()
                    if len(tok) in (32, 64):
                        cands.add(tok)
        finally:
            kernel32.CloseHandle(h)
        print(f"[*] pid {pid}: cumulative {total_read/1e6:.0f}MB, {len(cands)} hex tokens")

    print(f"[*] scanning {len(cands)} unique hex tokens ...")
    hits = {}
    for tok in cands:
        raw = bytes.fromhex(tok)
        if len(raw) not in (16, 32):
            continue
        for name, page1 in dbs:
            salt = page1[:16].hex()
            if salt in hits:
                continue
            dec, cipher = try_decrypt_page1(raw, page1)
            if dec:
                hits[salt] = (tok, cipher, name)
                print(f"[+] MATCH cipher={cipher} salt={salt} db={name}\n    key={tok}")
                break
    print(f"[*] matched {len(hits)} / {len({d[1][:16] for d in dbs})} salts")
    if not hits:
        print("[-] no match")


if __name__ == "__main__":
    main()
