"""Probe v3: verify memory reading works and dump candidate key material.

Checks:
 1. Can we read regions at all (count readable bytes returned vs requested)?
 2. Are there ASCII markers like "WXWork" / "sqlite3_key" / "x'" in memory?
 3. Collect all 32/64-char hex tokens from memory and try AES-128 (16B) and
    AES-256 (32B) decryption against the encrypted page 1.
"""
import ctypes
import hashlib
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wecom_reader.crypto.decrypt import (  # noqa: E402
    PAGE_SZ,
    SQLITE_HDR,
    derive_page_key,
    generate_initial_vector,
    has_wxsqlite3_plain_header_fragment,
)
from wecom_reader.crypto.key_extract import (  # noqa: E402
    _enum_memory_regions,
    _read_process_memory,
    kernel32,
)
from Cryptodome.Cipher import AES  # noqa: E402

EXE = sys.argv[1]
DB_DIR = sys.argv[2]
MAX_READ = int(sys.argv[3]) if len(sys.argv) > 3 else 3 * 1024 ** 3

HEX_RE = re.compile(rb"[0-9a-fA-F]{32,128}")


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


def decrypt_page_generic(raw_key, page_data, page_no):
    """Try decrypting a page with arbitrary key length (16/24/32)."""
    key = hashlib.md5(raw_key + struct.pack("<I", page_no) + b"sAlT").digest()
    if len(key) != 16 and len(key) != 24 and len(key) != 32:
        return None
    iv = generate_initial_vector(page_no)
    data = bytearray(page_data)
    frag = bytes(data[16:24])
    data[16:24] = data[8:16]
    tail = AES.new(key, AES.MODE_CBC, iv).decrypt(bytes(data[16:]))
    data[16:] = tail
    if bytes(data[16:24]) != frag:
        return None
    data[:16] = SQLITE_HDR
    return bytes(data)


def looks_valid(page):
    return page[:16] == SQLITE_HDR and len(page) >= 108 and page[100] in (0x02, 0x05, 0x0A, 0x0D)


def main():
    dbs = []
    for name in os.listdir(DB_DIR):
        if not name.endswith(".db"):
            continue
        p = os.path.join(DB_DIR, name)
        if os.path.getsize(p) < PAGE_SZ:
            continue
        with open(p, "rb") as f:
            page1 = f.read(PAGE_SZ)
        if page1[:16] == SQLITE_HDR:
            continue
        if not has_wxsqlite3_plain_header_fragment(page1):
            print(f"[!] {name}: unfamiliar header {page1[:24].hex()}")
            continue
        dbs.append((name, page1))
    print(f"[*] {len(dbs)} encrypted dbs loaded; salts={len({d[1][:16] for d in dbs})}")

    pids = pids_for(EXE)
    print(f"[*] pids: {pids}")
    cands = set()
    for pid, mem in pids:
        h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
        if not h:
            print(f"[-] pid {pid}: open failed")
            continue
        read_ok = 0
        read_bytes = 0
        markers = 0
        try:
            regions = _enum_memory_regions(h)
            for base, size in regions:
                if read_bytes > MAX_READ:
                    break
                if size > 32 * 1024 * 1024:
                    continue
                data = _read_process_memory(h, base, size)
                if not data:
                    continue
                read_ok += 1
                read_bytes += len(data)
                if b"sqlite3_key" in data or b"wxSQLite3" in data or b"WXWork" in data:
                    markers += 1
                for m in HEX_RE.finditer(data):
                    tok = m.group(0).decode()
                    if len(tok) in (32, 48, 64):
                        cands.add(tok)
        finally:
            kernel32.CloseHandle(h)
        print(f"[*] pid {pid}: read_ok={read_ok} regions, {read_bytes/1e6:.0f}MB, "
              f"markers={markers} regions")

    print(f"[*] unique hex candidates: {len(cands)}")
    hit = None
    for tok in cands:
        raw = bytes.fromhex(tok)
        for key_len in (16, 24, 32):
            if len(raw) != key_len:
                continue
            for name, page1 in dbs:
                page = decrypt_page_generic(raw, page1, 1)
                if page and looks_valid(page):
                    hit = (tok, key_len, name)
                    print(f"[+] KEY MATCH len={key_len} db={name} key={tok}")
                    break
            if hit:
                break
        if hit:
            break
    if not hit:
        print("[-] no key match among candidates")


if __name__ == "__main__":
    main()
