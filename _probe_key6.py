"""Probe v6: brute-force the raw key from an in-memory salt hit.

For every salt occurrence found in memory we test:
  1. 16-byte and 32-byte windows in a wide neighbourhood
  2. AES-128/MD5 and AES-256/SHA-256 page-key derivations
  3. both non-legacy and legacy page-1 layouts

Print diagnostics: how many salt occurrences were located at all.
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
WINDOW = int(sys.argv[3]) if len(sys.argv) > 3 else 512

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


def page_key(raw_key, page_no):
    nkey = raw_key + struct.pack("<I", page_no) + SALT_BYTES
    if len(raw_key) == 16:
        return hashlib.md5(nkey).digest()
    if len(raw_key) == 32:
        return hashlib.sha256(nkey).digest()
    return None


def test_nonlegacy(raw_key, page1):
    key = page_key(raw_key, 1)
    if not key:
        return False
    data = bytearray(page1)
    frag = bytes(data[16:24])
    data[16:24] = data[8:16]
    iv = generate_initial_vector(1)
    data[16:PAGE_SZ] = AES.new(key, AES.MODE_CBC, iv).decrypt(bytes(data[16:PAGE_SZ]))
    if bytes(data[16:24]) != frag:
        return False
    return bytes(data[:16]) == SQLITE_HDR and data[100] in (0x02, 0x05, 0x0A, 0x0D)


def test_legacy(raw_key, page1):
    key = page_key(raw_key, 1)
    if not key:
        return False
    iv = generate_initial_vector(1)
    dec = AES.new(key, AES.MODE_CBC, iv).decrypt(bytes(page1))
    return dec[:16] == SQLITE_HDR and dec[100] in (0x02, 0x05, 0x0A, 0x0D)


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
    print(f"[*] {len(dbs)} dbs, {len(salts)} salts, window={WINDOW}")

    total = 0
    salt_hits = 0
    tried = 0
    for pid, mem in pids_for(EXE):
        h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
        if not h:
            continue
        try:
            for base, size in _enum_memory_regions(h):
                if size > 64 * 1024 * 1024:
                    continue
                data = _read_process_memory(h, base, size)
                if not data:
                    continue
                total += len(data)
                for salt, owners in salts.items():
                    pos = data.find(salt)
                    while pos >= 0:
                        salt_hits += 1
                        lo = max(0, pos - WINDOW)
                        hi = min(len(data), pos + WINDOW)
                        chunk = data[lo:hi]
                        page1 = owners[0][1]
                        for klen in (16, 32):
                            for off in range(len(chunk) - klen + 1):
                                cand = chunk[off:off + klen]
                                tried += 1
                                if test_nonlegacy(cand, page1):
                                    print(f"[+] NONLEGACY keylen={klen} pid={pid} "
                                          f"salt={salt.hex()} key={cand.hex()} "
                                          f"dbs={[o[0] for o in owners]}")
                                    return
                                if test_legacy(cand, page1):
                                    print(f"[+] LEGACY keylen={klen} pid={pid} "
                                          f"salt={salt.hex()} key={cand.hex()} "
                                          f"dbs={[o[0] for o in owners]}")
                                    return
                        pos = data.find(salt, pos + 1)
        finally:
            kernel32.CloseHandle(h)
    print(f"[*] read {total/1e6:.0f}MB, salt_hits={salt_hits}, candidates_tried={tried}")


if __name__ == "__main__":
    main()
