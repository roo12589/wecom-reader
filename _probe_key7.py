"""Probe v7: locate SQLite3MultipleCiphers cipher structs in client memory.

Struct layouts (x64, from cipher_wxaes128.c / cipher_wxaes256.c):

  AES128Cipher: int m_legacy(0), int m_legacyPageSize(4), int m_keyLength(8),
                uint8 m_key[16](12), Rijndael* m_aes(aligned -> 32)
  AES256Cipher: int m_legacy(0), int m_legacyPageSize(4), int m_kdfIter(8),
                int m_keyLength(12), uint8 m_key[32](16), Rijndael* m_aes(48)

So we scan for offsets where legacy==0, legacyPageSize==0,
(128): keyLength==16, (256): kdfIter small and keyLength==32,
and then use the embedded key bytes against the encrypted page 1.
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
    return hashlib.sha256(nkey).digest()


def try_key(raw_key, page1, legacy):
    key = page_key(raw_key, 1)
    iv = generate_initial_vector(1)
    if legacy:
        dec = AES.new(key, AES.MODE_CBC, iv).decrypt(bytes(page1))
        hdr, tail_ok = dec[:16], True
    else:
        data = bytearray(page1)
        frag = bytes(data[16:24])
        data[16:24] = data[8:16]
        data[16:PAGE_SZ] = AES.new(key, AES.MODE_CBC, iv).decrypt(
            bytes(data[16:PAGE_SZ]))
        hdr, tail_ok = bytes(data[:16]), bytes(data[16:24]) == frag
    return hdr == SQLITE_HDR and tail_ok


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
    print(f"[*] {len(dbs)} encrypted dbs")

    seen = set()
    for pid, mem in pids_for(EXE):
        h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
        if not h:
            continue
        try:
            for base, size in _enum_memory_regions(h):
                if size > 64 * 1024 * 1024:
                    continue
                data = _read_process_memory(h, base, size)
                if not data or len(data) < 64:
                    continue
                for off in range(0, len(data) - 64, 4):
                    legacy, lgps = struct.unpack_from("<ii", data, off)
                    if legacy != 0 or lgps != 0:
                        continue
                    a, b = struct.unpack_from("<ii", data, off + 8)
                    # AES-128 layout: a == m_keyLength == 16
                    if a == 16:
                        cand = bytes(data[off + 12:off + 28])
                        for name, page1 in dbs:
                            if try_key(cand, page1, False):
                                print(f"[+] AES128 nonlegacy pid={pid} db={name} "
                                      f"key={cand.hex()}")
                                seen.add(cand.hex())
                                break
                    # AES-256 layout: a == m_kdfIter (small), b == 32
                    if b == 32 and 0 <= a <= 64:
                        cand = bytes(data[off + 16:off + 48])
                        for name, page1 in dbs:
                            if try_key(cand, page1, False):
                                print(f"[+] AES256 nonlegacy pid={pid} db={name} "
                                      f"key={cand.hex()}")
                                seen.add(cand.hex())
                                break
        finally:
            kernel32.CloseHandle(h)
        if seen:
            break
    if not seen:
        print("[-] no cipher struct match")


if __name__ == "__main__":
    main()
