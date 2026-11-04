"""Probe: try to extract the wxSQLite3 key from a running WeCom-family client process.

Usage: python _probe_key.py <exe_name> <db_dir> [pid ...]
"""
import ctypes
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wecom_reader.crypto.decrypt import verify_key  # noqa: E402
from wecom_reader.crypto.key_extract import (  # noqa: E402
    _enum_memory_regions,
    _read_process_memory,
    kernel32,
)

hex_re = re.compile(b"x'([0-9a-fA-F]{32,192})'")


def find_pids(exe_name):
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
            out.append((int(parts[1]), int(parts[4].replace(",", "").replace(" K", "").strip() or 0)))
    out.sort(key=lambda x: -x[1])
    return out


def collect(db_dir):
    dbs = []
    for root, dirs, files in os.walk(db_dir):
        for name in files:
            if name.endswith(".db"):
                p = os.path.join(root, name)
                if os.path.getsize(p) < 4096:
                    continue
                with open(p, "rb") as f:
                    page1 = f.read(4096)
                if page1[:16] == b"SQLite format 3\x00":
                    continue
                dbs.append((name, p, page1[:16].hex(), page1))
    return dbs


def main():
    exe = sys.argv[1]
    db_dir = sys.argv[2]
    dbs = collect(db_dir)
    print(f"[*] encrypted dbs: {len(dbs)} in {db_dir}")
    salts = {d[2] for d in dbs}
    print(f"[*] unique salts: {len(salts)}")
    pids = find_pids(exe)
    print(f"[*] {exe} pids: {pids}")
    found = {}
    t0 = time.time()
    for pid, mem in pids:
        h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
        if not h:
            print(f"[-] pid {pid}: cannot open")
            continue
        try:
            regions = _enum_memory_regions(h)
            total = sum(s for _, s in regions)
            print(f"[*] pid {pid}: {len(regions)} regions, {total/1e6:.0f} MB readable")
            for base, size in regions:
                if size > 64 * 1024 * 1024:
                    continue
                data = _read_process_memory(h, base, size)
                if not data:
                    continue
                for m in hex_re.finditer(data):
                    hs = m.group(1).decode()
                    cands = []
                    if len(hs) == 32:
                        cands.append(hs)
                    elif len(hs) == 64:
                        cands += [hs[:32], hs]
                    elif len(hs) == 96:
                        cands += [hs[:64], hs[:32]]
                    for ch in cands:
                        if len(ch) not in (32, 64):
                            continue
                        if len(ch) == 32:
                            key = bytes.fromhex(ch)
                            for name, p, salt, page1 in dbs:
                                if salt in found:
                                    continue
                                if verify_key(key, page1):
                                    found[salt] = (ch, name, pid)
                                    print(f"[+] KEY FOUND salt={salt} db={name} pid={pid} key={ch}")
                                    break
                if len(found) >= len(salts):
                    break
        finally:
            kernel32.CloseHandle(h)
        if len(found) >= len(salts):
            break
    print(f"[*] elapsed {time.time()-t0:.1f}s; matched {len(found)}/{len(salts)} salts")


if __name__ == "__main__":
    main()
