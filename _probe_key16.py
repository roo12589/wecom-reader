"""Probe v16: which process has the Data dir / *.db paths mapped in memory?"""
import ctypes
import ctypes.wintypes as wt
import sys

sys.path.insert(0, sys.path[0] or ".")

from wecom_reader.crypto.key_extract import (  # noqa: E402
    _enum_memory_regions,
    _read_process_memory,
    kernel32,
)

TH32CS_SNAPPROCESS = 0x2
NEEDLES = [
    b"message.db",
    b"session.db",
    b"WXWork",
    b"airchina",
]
PATHNEEDLE = b"1688849876550208_1970325081491960"


class PE(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


def procs():
    k = ctypes.windll.kernel32
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    e = PE()
    e.dwSize = ctypes.sizeof(PE)
    out = []
    ok = k.Process32First(snap, ctypes.byref(e))
    while ok:
        out.append((e.th32ProcessID, e.szExeFile.decode("utf-8", "replace")))
        ok = k.Process32Next(snap, ctypes.byref(e))
    k.CloseHandle(snap)
    return out


for pid, name in procs():
    if name.lower() in ("[system process]", "system", "csrss.exe", "wininit.exe"):
        continue
    h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
    if not h:
        continue
    counts = {}
    sames = []
    try:
        for base, size in _enum_memory_regions(h):
            d = _read_process_memory(h, base, size)
            if not d:
                continue
            for needle in NEEDLES:
                counts[needle] = counts.get(needle, 0) + d.count(needle)
            i = d.find(PATHNEEDLE)
            if i != -1 and len(sames) < 2:
                sames.append(hex(base + i))
    finally:
        kernel32.CloseHandle(h)
    if counts or sames:
        print(f"{name} pid {pid}: {counts} profilePath@{sames}")
