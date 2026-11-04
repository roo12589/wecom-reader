"""Probe v11: find which process holds the encrypted DB / decrypted pages.

Searches every readable region of each candidate process for:
  - the 16-byte DB "salt" prefix seen in every encrypted db
  - that salt as lowercase hex
  - plaintext SQLite headers (page cache evidence)
  - the literal "sAlT" wxSQLite3 KDF marker
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

TH32CS_SNAPPROCESS = 0x2

SALT = bytes.fromhex("1ee95536c52457a0b1aa6fd7e2dcb193")
HDR = b"SQLite format 3\x00"
HDRF = bytes.fromhex("1000020200402020")


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
    if snap == -1:
        return []
    e = PE()
    e.dwSize = ctypes.sizeof(PE)
    out = []
    ok = k.Process32First(snap, ctypes.byref(e))
    while ok:
        if e.szExeFile.decode("utf-8", "replace").lower() == exe.lower():
            out.append(e.th32ProcessID)
        ok = k.Process32Next(snap, ctypes.byref(e))
    k.CloseHandle(snap)
    return out


def scan(exe):
    for pid in pids_of(exe):
        h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
        if not h:
            print(f"  pid {pid}: open failed")
            continue
        regs = _enum_memory_regions(h)
        total = 0
        stats = {"salt": 0, "salthex": 0, "hdr": 0, "hdrfrag": 0, "sAlT": 0}
        samples = []
        for base, size in regs:
            d = _read_process_memory(h, base, size)
            if not d:
                continue
            total += len(d)
            stats["salt"] += d.count(SALT)
            stats["salthex"] += d.count(SALT.hex().encode())
            stats["hdr"] += d.count(HDR)
            stats["hdrfrag"] += d.count(HDRF)
            stats["sAlT"] += d.count(b"sAlT")
            if stats["salt"] and len(samples) < 3:
                off = d.find(SALT)
                samples.append((hex(base + off), bytes(d[max(0, off - 32):off + 64]).hex()))
        kernel32.CloseHandle(h)
        print(f"  pid {pid}: {len(regs)} regions, {total/1e6:.0f} MB")
        print(f"    {stats}")
        for addr, ctx in samples:
            print(f"    salt@{addr}: {ctx}")
    return


for exe in sys.argv[1:] or ["airchina.exe", "AirChina5.0.exe"]:
    print(f"[*] {exe}")
    scan(exe)
