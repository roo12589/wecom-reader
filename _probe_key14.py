"""Probe v14: is any DB page-1 actually resident (decrypted) in client memory?

Signature of a *decrypted* SQLite page 1:
  b"SQLite format 3\\x00" + 8 bytes + b"\\x10\\x00\\x02\\x02\\x00\\x40\\x20\\x20"
(we do not require contiguity: just report both markers and dump context)
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wecom_reader.crypto.key_extract import (  # noqa: E402
    _enum_memory_regions,
    _read_process_memory,
    kernel32,
)

HDR = b"SQLite format 3\x00"
FRAG = bytes.fromhex("1000020200402020")
TH32CS_SNAPPROCESS = 0x2


class PE(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


def pids_of(exe):
    k = ctypes.windll.kernel32
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    e = PE()
    e.dwSize = ctypes.sizeof(PE)
    out = []
    ok = k.Process32First(snap, ctypes.byref(e))
    while ok:
        if e.szExeFile.decode("utf-8", "replace").lower() == exe:
            out.append(e.th32ProcessID)
        ok = k.Process32Next(snap, ctypes.byref(e))
    k.CloseHandle(snap)
    return out


for exe in sys.argv[1:]:
    for pid in pids_of(exe.lower()):
        h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
        if not h:
            continue
        hits = 0
        for base, size in _enum_memory_regions(h):
            d = _read_process_memory(h, base, size)
            if not d:
                continue
            i = d.find(HDR)
            while i != -1:
                ctx = d[i:i + 32]
                if ctx[16:24] == FRAG:
                    hits += 1
                    print(f"[+] {exe} pid {pid} @ {hex(base+i)}: page1-like {ctx.hex()}")
                else:
                    if hits == 0:
                        print(f"[?] {exe} pid {pid} @ {hex(base+i)}: hdr only {ctx[:24].hex()}")
                i = d.find(HDR, i + 1)
                if i > 0 and hits > 3:
                    break
        kernel32.CloseHandle(h)
        print(f"[*] {exe} pid {pid}: page1-signature hits={hits}")
