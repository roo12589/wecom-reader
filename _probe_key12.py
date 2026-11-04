"""Probe v12: find which process holds an open handle to a given file (Restart Manager API)."""
import ctypes
import ctypes.wintypes as wt
import os
import sys


class RM_UNIQUE_PROCESS(ctypes.Structure):
    _fields_ = [("dwProcessId", wt.DWORD), ("ProcessStartTime", wt.FILETIME)]


class RM_PROCESS_INFO(ctypes.Structure):
    _fields_ = [
        ("Process", RM_UNIQUE_PROCESS),
        ("strAppName", wt.WCHAR * 256),
        ("strServiceShortName", wt.WCHAR * 64),
        ("ApplicationType", ctypes.c_uint),
        ("AppStatus", wt.DWORD),
        ("TSSessionId", wt.DWORD),
        ("bRestartable", wt.BOOL),
    ]


MAX_PROC = 64

def who_holds(path):
    rm = ctypes.WinDLL("rstrtmgr")
    session = wt.DWORD(0)
    key = (wt.WCHAR * 64)()
    flags = wt.DWORD(0)
    if rm.RmStartSession(ctypes.byref(session), ctypes.byref(flags), key) != 0:
        print("RmStartSession failed")
        return []
    try:
        files = (wt.WCHAR * (len(path) + 1))(path)
        if rm.RmRegisterResources(
            session, 1, files, 0, None, 0, None
        ) != 0:
            print("RmRegisterResources failed")
            return []
        arr = (RM_PROCESS_INFO * MAX_PROC)()
        needed = wt.DWORD(0)
        count = wt.DWORD(MAX_PROC)
        rc = rm.RmGetList(session, ctypes.byref(needed), ctypes.byref(count), arr, ctypes.byref(wt.DWORD(0)))
        out = []
        for i in range(count.value if rc in (0, 234) else 0):
            info = arr[i]
            out.append((info.Process.dwProcessId, info.strAppName, info.ApplicationType, info.bRestartable))
        return out
    finally:
        rm.RmEndSession(session)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(f"=== {p}")
        print(f"    exists={os.path.exists(p)}")
        for item in who_holds(p):
            pid, name, atype, rest = item
            print(f"    pid={pid} app={name!r} type={atype} restartable={rest}")
