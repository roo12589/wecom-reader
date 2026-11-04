"""Probe v10: extract wxSQLite3 key for private-deployment client (airchina.exe).

Differs from key_extract in that PIDs are enumerated via ctypes toolhelp snapshot
instead of spawning `tasklist` (works without stdio pipes).
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wecom_reader.crypto import key_extract as ke  # noqa: E402

TH32CS_SNAPPROCESS = 0x00000002
PIDS = []


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wt.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


def _snapshot_pids(exe_name):
    k = ctypes.windll.kernel32
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == -1:
        return []
    pe = PROCESSENTRY32()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
    out = []
    ok = k.Process32First(snap, ctypes.byref(pe))
    while ok:
        if pe.szExeFile.decode("utf-8", "replace").lower() == exe_name.lower():
            out.append((pe.th32ProcessID, 0))
        ok = k.Process32Next(snap, ctypes.byref(pe))
    k.CloseHandle(snap)
    return out


def main():
    exe = sys.argv[1]
    db_dir = sys.argv[2]
    limit_pid = int(sys.argv[3]) if len(sys.argv) > 3 else 0

    pids = _snapshot_pids(exe)
    print(f"[*] {exe} pids: {pids}")
    if limit_pid:
        pids = [p for p in pids if p[0] == limit_pid]
    if not pids:
        print("[-] no process")
        return

    ke._get_wxwork_pids = lambda: pids
    t0 = time.time()
    try:
        km = ke.extract_key(db_dir=db_dir, timeout=900, verbose=True)
        print("[+] key map:")
        for k, v in km.items():
            print("   ", k, "->", v)
    except Exception as e:
        print("[-] failed:", type(e).__name__, e)
    print(f"[*] elapsed {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
