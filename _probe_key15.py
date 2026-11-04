"""Probe v15: inventory the whole profile + who holds the DB files.

1. classify every .db in the profile (plain vs encrypted + salt prefix)
2. report the wxSQLite3/private-deploy feature flags from Config.cfg
3. report the Restart Manager result for message.db / session.db
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import sys

ROOT = r"C:\Users\Administrator\Documents\airchina"
PROFILE = os.path.join(ROOT, "1688849876550208_1970325081491960")
DATA = os.path.join(PROFILE, "Data")
HDR = b"SQLite format 3\x00"
FRAG = bytes.fromhex("1000020200402020")


def load_config():
    p = os.path.join(PROFILE, "Config.cfg")
    return json.loads(open(p, encoding="utf-8", errors="replace").read())


def classify():
    buckets = {}
    for dp, dn, fns in os.walk(ROOT):
        for fn in fns:
            if not fn.endswith(".db") or fn.endswith(("-wal", "-shm")):
                continue
            p = os.path.join(dp, fn)
            try:
                if os.path.getsize(p) < 4096:
                    continue
                with open(p, "rb") as f:
                    head = f.read(24)
            except OSError:
                continue
            tag = "PLAIN" if head[:16] == HDR else "ENC"
            buckets.setdefault(tag, []).append((os.path.relpath(p, ROOT), head[:24].hex()))
    return buckets


def main():
    cfg = load_config()["config"]
    print("[*] feature flags:")
    for k in sorted(cfg):
        if re.search(r"DbKey|Encrypt|Encrypt|Storage|Backup", k, re.I):
            print(f"    {k} = {cfg[k]!r}")

    buckets = classify()
    for tag, rows in buckets.items():
        print(f"\n[*] {tag}: {len(rows)}")
        for rel, hdr in rows:
            print(f"    {rel}\n        {hdr}")
            break
        # summarize prefixes
        prefixes = {}
        for rel, hdr in rows:
            prefixes.setdefault(hdr[:16], []).append(rel)
        for pref, files in prefixes.items():
            print(f"    prefix {pref}: {len(files)} files, e.g. {os.path.basename(files[0])}")


if __name__ == "__main__":
    main()
