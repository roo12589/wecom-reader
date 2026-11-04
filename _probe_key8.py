"""Probe v8: treat every 16/32-byte window of every readable region as a raw
key candidate (not just hex tokens), verifying against encrypted page 1.

This is exhaustive but bounded: we walk each region in steps of 4 bytes.
"""
import hashlib
import os
import struct
import sys
import time

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
MAX_SECONDS = float(sys.argv[3]) if len(sys.argv) > 3 else 120

SALT_BYTES = b"sAlT"


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


def prep_keys():
    """Precompute MD5/SHA256 material constants."""
    return None


def try_key(raw_key, page1):
    nkey = raw_key + struct.pack("<I", 1) + SALT_BYTES
    if len(raw_key) == 16:
        key = hashlib.md5(nkey).digest()
    else:
        key = hashlib.sha256(nkey).digest()
    data = bytearray(page1)
    frag = bytes(data[16:24])
    data[16:24] = data[8:16]
    iv = generate_initial_vector(1)
    data[16:PAGE_SZ] = AES.new(key, AES.MODE_CBC, iv).decrypt(bytes(data[16:PAGE_SZ]))
    if bytes(data[16:24]) != frag:
        return False
    return bytes(data[:16]) == SQLITE_HDR and data[100] in (0x02, 0x05, 0x0A, 0x0D)


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
        dbs.append((name, page1))
    salt_map = {}
    for name, page1 in dbs:
        salt_map.setdefault(page1[:16].hex(), []).append((name, page1))
    print(f"[*] {len(dbs)} dbs, {len(salt_map)} salts, budget={MAX_SECONDS}s")

    t0 = time.time()
    tried = 0
    for pid, mem in pids_for(EXE):
        h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
        if not h:
            continue
        try:
            for base, size in _enum_memory_regions(h):
                if time.time() - t0 > MAX_SECONDS:
                    break
                if size > 32 * 1024 * 1024:
                    continue
                data = _read_process_memory(h, base, size)
                if not data or len(data) < 32:
                    continue
                for off in range(0, len(data) - 32, 4):
                    cand32 = data[off:off + 32]
                    tried += 1
                    for salt, owners in salt_map.items():
                        if try_key(cand32, owners[0][1]):
                            print(f"[+] AES256 pid={pid} salt={salt} "
                                  f"dbs={[o[0] for o in owners]} key={cand32.hex()}")
                            return
                    cand16 = data[off:off + 16]
                    for salt, owners in salt_map.items():
                        if try_key(cand16, owners[0][1]):
                            print(f"[+] AES128 pid={pid} salt={salt} "
                                  f"dbs={[o[0] for o in owners]} key={cand16.hex()}")
                            return
        finally:
            kernel32.CloseHandle(h)
    print(f"[-] no hit after {tried} candidates, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
