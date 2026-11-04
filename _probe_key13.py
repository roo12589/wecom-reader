"""Probe v13: targeted memory search for the private-deployment client.

Searches each client process for:
  * the 24-byte page-1 prefix of message.db / company.db (constant 8-byte run)
  * literal "sAlT" / "sqlite3_key" / "wxSQLite3" / client exe markers
  * hex-quoted key tokens x'...'
Also prints every running process name so helper processes are not missed.
"""
import ctypes
import ctypes.wintypes as wt
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wecom_reader.crypto.key_extract import (  # noqa: E402
    _enum_memory_regions,
    _read_process_memory,
    kernel32,
)

DATA = os.environ.get(
    "DATA_DIR",
    r"C:\Users\Administrator\Documents\airchina\1688849876550208_1970325081491960\Data",
)
TH32CS_SNAPPROCESS = 0x2
HEX_RE = re.compile(rb"x'([0-9a-fA-F]{32,192})'")


class PE(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


def all_procs():
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


def page_prefix(name):
    p = os.path.join(DATA, name)
    with open(p, "rb") as f:
        return f.read(24)


def main():
    procs = all_procs()
    print(f"[*] {len(procs)} processes running")
    names = sorted({n for _, n in procs})
    print("[*] names:", ", ".join(names))

    p1_msg = page_prefix("message.db")
    p1_co = page_prefix("company.db")
    print(f"[*] message.db prefix: {p1_msg.hex()}")
    print(f"[*] company.db prefix: {p1_co.hex()}")

    marks = {
        "msgP1_24": p1_msg,
        "coP1_24": p1_co,
        "msgP1_16": p1_msg[:16],
        "const8": p1_msg[:8],
        "sAlT": b"sAlT",
        "sqlite3_key": b"sqlite3_key",
        "wxSQLite3": b"wxSQLite3",
        "WXWork": b"WXWork",
        "airchina": b"airchina",
        "AES128": b"Rijndael",
    }

    targets = [p for p in procs if p[1].lower() in ("airchina.exe", "airchina5.0.exe")]

    for pid, name in targets:
        h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
        if not h:
            print(f"[*] {name} pid {pid}: open failed")
            continue
        regs = _enum_memory_regions(h)
        counts = {k: 0 for k in marks}
        hexhits = 0
        hexsamples = []
        total = 0
        for base, size in regs:
            if size > 300 * 1024 * 1024:
                continue
            d = _read_process_memory(h, base, size)
            if not d:
                continue
            total += len(d)
            for key, pat in marks.items():
                counts[key] += d.count(pat)
            for m in HEX_RE.finditer(d):
                hexhits += 1
                if len(hexsamples) < 8:
                    hexsamples.append(m.group(1)[:80].decode())
        kernel32.CloseHandle(h)
        print(f"\n[*] {name} pid {pid}: {len(regs)} regions scanned, {total/1e6:.0f} MB")
        print("    " + " ".join(f"{k}={v}" for k, v in counts.items() if v))
        print(f"    hex-tokens={hexhits}")
        for s in hexsamples:
            print(f"      {s}")


if __name__ == "__main__":
    main()
