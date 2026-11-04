"""Probe v2: run the project's full extract_key pipeline but against airchina.exe."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wecom_reader.crypto import key_extract as ke  # noqa: E402

EXE = sys.argv[1] if len(sys.argv) > 1 else "airchina.exe"
DB_DIR = sys.argv[2]


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


ke._get_wxwork_pids = lambda: pids_for(EXE)
t0 = time.time()
try:
    km = ke.extract_key(db_dir=DB_DIR, timeout=600, verbose=True)
    print("[+] keys:")
    for k, v in km.items():
        print("    ", k, "->", v)
except Exception as e:
    print("[-] failed:", type(e).__name__, e)
print(f"[*] elapsed {time.time()-t0:.1f}s")
