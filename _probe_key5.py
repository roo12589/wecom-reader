"""Probe v5: locate the db salt in client memory, then test every 16/32-byte
window in its neighborhood as a raw AES key (MD5 for AES-128, SHA-256 for
AES-256 per SQLite3MultipleCiphers).
"""
import hashlib
import os
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
WINDOW = 160          # bytes to examine around a salt hit
MAX_READ = 2 * 1024 ** 3

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


def decrypt_page1(raw_key, page1):
    nkey = raw_key + struct.pack("<I", 1) + SALT
    if len(raw_key) == 16:
        key = hashlib.md5(nkey).digest()
    elif len(raw_key) == 32:
        key = hashlib.sha256(nkey).digest()
    else:
        return None
    data = bytearray(page1)
    frag = bytes(data[16:24])
    data[16:24] = data[8:16]
    iv = generate_initial_vector(1)
    tail = AES.new(key, AES.MODE_CBC, iv).decrypt(bytes(data[16:PAGE_SZ]))
    data[16:PAGE_SZ] = tail
    if bytes(data[16:24]) != frag:
        return None
    out = bytes(data)
    if out[:16] != SQLITE_HDR:
        return None
    if out[100] not in (0x02, 0x05, 0x0A, 0x0D):
        return None
    return out


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
    salts = {}
    for name, page1 in dbs:
        salts.setdefault(page1[:16], []).append((name, page1))
    print(f"[*] {len(dbs)} dbs, {len(salts)} unique salts")

    hits = 0
    total = 0
    for pid, mem in pids_for(EXE):
        h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
        if not h:
            continue
        try:
            for base, size in _enum_memory_regions(h):
                if total > MAX_READ:
                    break
                if size > 32 * 1024 * 1024:
                    continue
                data = _read_process_memory(h, base, size)
                if not data:
                    continue
                total += len(data)
                for salt, owners in salts.items():
                    start = 0
                    while True:
                        idx = data.find(salt, start)
                        if idx < 0:
                            break
                        start = idx + 1
                        lo = max(0, idx - WINDOW)
                        hi = min(len(data), idx + WINDOW)
                        chunk = data[lo:hi]
                        for klen in (16, 32):
                            for off in range(0, len(chunk) - klen + 1):
                                cand = chunk[off:off + klen]
                                dec = decrypt_page1(cand, owners[0][1])
                                if dec:
                                    print(f"[+] pid={pid} salt={salt.hex()} "
                                          f"offset_near_salt={lo + off - idx} "
                                          f"klen={klen} dbs={[o[0] for o in owners]}")
                                    print(f"    key={cand.hex()}")
                                    hits += 1
                                    break
                            if hits:
                                break
                        if hits:
                            break
                    if hits:
                        break
        finally:
            kernel32.CloseHandle(h)
        if hits:
            break
    print(f"[*] read {total/1e6:.0f}MB, hits={hits}")


if(__name__ == "__main__"):
    main()
