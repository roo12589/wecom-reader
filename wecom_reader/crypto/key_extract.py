"""Extract WeCom (企业微信) database decryption key from the client process memory.

Three scanning strategies:
1. x'...' pattern: Fast regex match for SQL-embedded hex keys
2. sAlT proximity: 16-byte windows around the wxSQLite3 KDF marker ``"sAlT"``
3. cipher struct: Slower but more reliable heap object layout scan

The client executable is auto-detected from the running processes and the data
directory name (consumer builds ship ``WXWork.exe``; private deployments such as
airchina use a renamed binary like ``airchina.exe``). Override with
``--process-name`` or ``WXWORK_PROCESS_NAME``.

Requires: Windows, admin privileges, the client running.
"""

import bisect
import ctypes
import ctypes.wintypes as wt
import os
import re
import struct
import subprocess
import time
from typing import Optional

from .decrypt import is_plain_sqlite, is_wxsqlite3_aes128_page1, verify_key

# Windows API constants
kernel32 = ctypes.windll.kernel32
MEM_COMMIT = 0x1000
READABLE = {0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80}


class MBI(ctypes.Structure):
    """MEMORY_BASIC_INFORMATION for VirtualQueryEx."""
    _fields_ = [
        ("BaseAddress", ctypes.c_uint64),
        ("AllocationBase", ctypes.c_uint64),
        ("AllocationProtect", wt.DWORD),
        ("_pad1", wt.DWORD),
        ("RegionSize", ctypes.c_uint64),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
        ("_pad2", wt.DWORD),
    ]


def _read_process_memory(handle, addr: int, size: int) -> Optional[bytes]:
    buf = ctypes.create_string_buffer(size)
    n = ctypes.c_size_t(0)
    if kernel32.ReadProcessMemory(
        handle, ctypes.c_uint64(addr), buf, size, ctypes.byref(n)
    ):
        return buf.raw[: n.value]
    return None


def _enum_memory_regions(handle) -> list[tuple[int, int]]:
    regs = []
    addr = 0
    mbi = MBI()
    while addr < 0x7FFFFFFFFFFF:
        if kernel32.VirtualQueryEx(
            handle, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)
        ) == 0:
            break
        if (
            mbi.State == MEM_COMMIT
            and mbi.Protect in READABLE
            and 0 < mbi.RegionSize < 500 * 1024 * 1024
        ):
            regs.append((mbi.BaseAddress, mbi.RegionSize))
        nxt = mbi.BaseAddress + mbi.RegionSize
        if nxt <= addr:
            break
        addr = nxt
    return regs


DEFAULT_PROCESS_NAMES = ("WXWork.exe",)

# Names of *other* products that often coexist with a private-deployment client
# and must never be scanned by auto-detection (e.g. AirChina5.0.exe is the
# Feishu-based build, not the WeCom-based airchina.exe).
EXCLUDED_PROCESS_NAMES = frozenset({"airchina5.0.exe"})


def _iter_processes() -> list[tuple[int, str]]:
    """List running (pid, exe_name) pairs via a Toolhelp snapshot."""
    TH32CS_SNAPPROCESS = 0x00000002

    class _PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wt.DWORD),
            ("cntUsage", wt.DWORD),
            ("th32ProcessID", wt.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wt.DWORD),
            ("cntThreads", wt.DWORD),
            ("th32ParentProcessID", wt.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wt.DWORD),
            ("szExeFile", ctypes.c_char * 260),
        ]

    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == -1 or snap is None:
        return []
    entry = _PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(_PROCESSENTRY32)
    found = []
    try:
        ok = kernel32.Process32First(snap, ctypes.byref(entry))
        while ok:
            found.append(
                (entry.th32ProcessID, entry.szExeFile.decode("utf-8", "replace"))
            )
            ok = kernel32.Process32Next(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return found


def _pids_via_toolhelp(exe_name: str) -> list[tuple[int, int]]:
    """Enumerate PIDs by executable name with a Toolhelp snapshot.

    Avoids spawning ``tasklist`` (which needs stdio pipes) so this works under
    restricted sandboxes. Returns (pid, 0) tuples; memory size is unknown.
    """
    found = [
        (pid, 0)
        for pid, name in _iter_processes()
        if name.lower() == exe_name.lower()
    ]
    return found


def _pids_via_tasklist(exe_name: str) -> list[tuple[int, int]]:
    """Enumerate PIDs via tasklist, including working-set size for sorting."""
    r = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
    )
    pids = []
    for line in r.stdout.strip().split("\n"):
        if not line.strip() or not line.startswith('"'):
            continue
        p = line.strip('"').split('","')
        if len(p) >= 5:
            pid = int(p[1])
            mem = int(p[4].replace(",", "").replace(" K", "").strip() or "0")
            pids.append((pid, mem))
    pids.sort(key=lambda x: x[1], reverse=True)
    return pids


def _get_wxwork_pids(exe_name: str = "WXWork.exe") -> list[tuple[int, int]]:
    """Get client process PIDs sorted by memory usage (descending).

    ``exe_name`` defaults to the consumer client, but private-deployment builds
    ship a renamed binary (e.g. ``airchina.exe``), so callers can override it.
    Falls back to a Toolhelp snapshot when ``tasklist`` cannot be spawned.
    """
    try:
        return _pids_via_tasklist(exe_name)
    except (OSError, subprocess.SubprocessError):
        pids = _pids_via_toolhelp(exe_name)
        pids.sort(key=lambda x: x[1], reverse=True)
        return pids


def _exe_candidates_from_dir(db_dir: Optional[str]) -> list[str]:
    """Guess the client executable name from a ``Documents/<client>/...`` path.

    ``...\\Documents\\airchina\\<account>\\Data`` -> ``airchina.exe``.
    The vendor folder name is the best available hint for private deployments.
    """
    if not db_dir:
        return []

    current = os.path.abspath(db_dir)
    parts = []
    while True:
        parent, tail = os.path.split(current)
        if not tail or parent == current:
            break
        parts.append(tail)
        current = parent

    # parts are leaf-first: ["Data", "<account>", "airchina", "Documents", ...]
    # so the vendor folder sits immediately *before* "Documents" in this order.
    for idx, part in enumerate(parts):
        if part.lower() == "documents" and idx >= 1:
            return [parts[idx - 1] + ".exe"]
    # Fallback: the folder two levels above the Data tree (Data -> account -> vendor).
    if len(parts) >= 3:
        return [parts[2] + ".exe"]
    return []


def resolve_process_names(
    db_dir: Optional[str] = None,
    process_names: Optional[list[str]] = None,
) -> list[str]:
    """Resolve which executable names should be scanned for the key.

    Order of preference:
    1. Explicit ``process_names`` (``--process-name`` / ``WXWORK_PROCESS_NAME``).
    2. Running processes that match the vendor folder of ``db_dir``.
    3. Running ``WXWork.exe`` (consumer client).
    4. Untested guesses derived from the path, ending with ``WXWork.exe``.
    """
    if process_names:
        return [n for n in process_names if n]

    running = {name.lower(): name for _, name in _iter_processes()}
    hinted = [n for n in _exe_candidates_from_dir(db_dir) if n.lower() in running]
    if hinted:
        return hinted
    if "wxwork.exe" in running:
        return [running["wxwork.exe"]]

    guesses = _exe_candidates_from_dir(db_dir) + list(DEFAULT_PROCESS_NAMES)
    seen = set()
    unique = []
    for name in guesses:
        if name.lower() in seen or name.lower() in EXCLUDED_PROCESS_NAMES:
            continue
        seen.add(name.lower())
        unique.append(name)
    return unique


def _auto_detect_db_dir() -> Optional[str]:
    """Scan %USERPROFILE%\\Documents\\WXWork\\*\\Data for encrypted DBs."""
    docs = os.path.join(os.environ.get("USERPROFILE", ""), "Documents", "WXWork")
    if not os.path.isdir(docs):
        return None

    candidates = []
    for name in os.listdir(docs):
        data_dir = os.path.join(docs, name, "Data")
        if not os.path.isdir(data_dir):
            continue
        for fname in os.listdir(data_dir):
            if not fname.endswith(".db"):
                continue
            fpath = os.path.join(data_dir, fname)
            if os.path.getsize(fpath) < 4096:
                continue
            with open(fpath, "rb") as f:
                header = f.read(16)
            if header != b"SQLite format 3\x00":
                candidates.append(data_dir)
                break

    if not candidates:
        return None
    # Return most recently modified
    candidates.sort(key=lambda d: os.path.getmtime(d), reverse=True)
    return candidates[0]


def _collect_db_files(db_dir: str) -> tuple[list, dict]:
    """Collect all .db files with their salts and page 1 data."""
    db_files = []  # (rel_path, abs_path, size, salt_hex, page1_bytes)
    salt_to_dbs = {}  # salt_hex -> [rel_path, ...]

    for root, dirs, files in os.walk(db_dir):
        dirs[:] = [d for d in dirs if d not in ("-journal",)]
        for name in files:
            if not name.endswith(".db") or name.endswith("-wal") or name.endswith("-shm"):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, db_dir)
            sz = os.path.getsize(path)
            if sz < 4096:
                continue
            with open(path, "rb") as f:
                page1 = f.read(4096)
            if is_plain_sqlite(page1):
                continue
            salt_hex = page1[:16].hex()
            db_files.append((rel, path, sz, salt_hex, page1))
            salt_to_dbs.setdefault(salt_hex, []).append(rel)

    return db_files, salt_to_dbs


def _verify_key_wxwork(enc_key: bytes, db_page1: bytes) -> tuple[bool, str]:
    """Verify key against database page 1 with multiple parameter sets."""
    if len(enc_key) == 16 and verify_key(enc_key, db_page1):
        return True, "wxSQLite3 AES-128-CBC, per-page MD5 key/IV, no HMAC"
    return False, ""


SALT_MARKER = b"sAlT"
# Linux/macOS builds and some blobs store the KDF salt as uppercase.
SALT_MARKERS = (b"sAlT", b"SALT")
KEY_LEN_HINTS = (16, 32, 48, 64)


def _iter_marker_keys(data: bytes):
    """Yield candidate 16-byte keys found next to a ``sAlT`` KDF marker.

    Private-deployment builds keep the cipher key as an object laid out like::

        [ ... ][ key:16 ][ key_len:4 ][ b"sAlT" ][ ... ]

    so the key usually sits 20 bytes before the marker. We also try the
    neighbouring windows because allocator padding / alignment varies between
    builds.
    """
    for marker in SALT_MARKERS:
        start = data.find(marker)
        while start != -1:
            # Explicit key-length field directly before the marker.
            if start >= 4:
                declared = struct.unpack_from("<I", data, start - 4)[0]
                if declared in KEY_LEN_HINTS:
                    off = start - 4 - 16
                    if off >= 0:
                        yield data[off : off + 16]
            # Fixed layout: key(16) + len(4) + "sAlT".
            off = start - 20
            if off >= 0:
                yield data[off : off + 16]
            # Marker directly after the key, and other alignments.
            for delta in (16, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64):
                off = start - delta - 16
                if off >= 0:
                    yield data[off : off + 16]
            start = data.find(marker, start + 1)


def _scan_salt_markers(
    regions_read,
    db_files,
    remaining_salts,
    key_map,
    tried_keys,
) -> None:
    """Strategy 2: find the key in the object stored next to the KDF marker."""
    for data in regions_read:
        for candidate in _iter_marker_keys(data):
            if len(candidate) != 16 or candidate in tried_keys:
                continue
            if candidate == b"\x00" * 16 or len(set(candidate)) < 4:
                continue
            tried_keys.add(candidate)
            for salt_hex in list(remaining_salts):
                for rel, path, size, salt, page1 in db_files:
                    if salt != salt_hex:
                        continue
                    ok, _ = _verify_key_wxwork(candidate, page1)
                    if ok:
                        key_map[salt_hex] = candidate.hex()
                        remaining_salts.discard(salt_hex)
                    break
            if not remaining_salts:
                return


def extract_key(
    db_dir: Optional[str] = None,
    timeout: int = 120,
    verbose: bool = False,
    process_names: Optional[list[str]] = None,
) -> dict[str, str]:
    """Extract decryption keys from the WeCom client's process memory.

    Args:
        db_dir: Path to WeCom data directory. Auto-detected if None.
        timeout: Max seconds for struct scan per process.
        verbose: Print progress to stderr.
        process_names: Executable names to scan. Defaults to ``WXWork.exe``;
            pass e.g. ``["airchina.exe"]`` for a private-deployment build.

    Returns:
        Dict mapping salt_hex -> enc_key_hex for each database found.
        Also includes "_db_dir" key with the database directory path.

    Raises:
        RuntimeError: If no client process is running or no keys found.
    """
    if db_dir is None:
        db_dir = _auto_detect_db_dir()
    if not db_dir or not os.path.isdir(db_dir):
        raise RuntimeError(
            "Cannot find WeCom data directory. "
            "Set db_dir or ensure %USERPROFILE%\\Documents\\WXWork\\*\\Data exists."
        )

    db_files, salt_to_dbs = _collect_db_files(db_dir)
    if not db_files:
        raise RuntimeError(f"No encrypted databases found in {db_dir}")

    names = resolve_process_names(db_dir, process_names)
    pids = []
    for name in names:
        pids.extend(_get_wxwork_pids(name))
    if not pids:
        raise RuntimeError(
            f"None of {names} is running. "
            "Start the WeCom client, or pass --process-name <exe> "
            "(private-deployment builds rename WXWork.exe, e.g. airchina.exe)."
        )
    if verbose:
        print(f"[*] Scanning {len(pids)} process(es) for {', '.join(names)}")

    key_map = {}
    remaining_salts = set(salt_to_dbs.keys())
    hex_re = re.compile(b"x'([0-9a-fA-F]{32,192})'")

    # Largest working set first: the UI process is usually the one holding the
    # cipher objects, and private deployments spawn several helper processes.
    pids.sort(key=lambda item: item[1], reverse=True)

    for pid, mem_kb in pids:
        handle = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
        if not handle:
            if verbose:
                print(f"[!] pid {pid}: cannot open (needs admin privileges)")
            continue

        tried_keys = set()
        try:
            regions = _enum_memory_regions(handle)
            total_bytes = sum(s for _, s in regions)

            # Strategies 1 + 2 need the raw bytes only; walk regions once.
            for base, size in regions:
                data = _read_process_memory(handle, base, size)
                if not data:
                    continue

                # Strategy 1: x'...' pattern scan
                for m in hex_re.finditer(data):
                    if not remaining_salts:
                        break
                    hex_str = m.group(1).decode()
                    hex_len = len(hex_str)

                    candidates = []
                    if hex_len == 32:
                        candidates.append((hex_str, None))
                    elif hex_len == 64:
                        candidates.append((hex_str[:32], hex_str[32:]))
                        candidates.append((hex_str, None))
                    elif hex_len == 96:
                        candidates.append((hex_str[:64], hex_str[64:]))
                        candidates.append((hex_str[:32], hex_str[-32:]))

                    for enc_key_hex, salt_hex in candidates:
                        if len(enc_key_hex) not in (32, 64):
                            continue
                        enc_key = bytes.fromhex(enc_key_hex)

                        targets = (
                            [s for s in remaining_salts if s == salt_hex]
                            if salt_hex
                            else list(remaining_salts)
                        )

                        for s in targets:
                            for rel, path, sz, salt, page1 in db_files:
                                if salt == s:
                                    ok, desc = _verify_key_wxwork(enc_key, page1)
                                    if ok:
                                        key_map[s] = enc_key_hex
                                        remaining_salts.discard(s)
                                    break

                        if not remaining_salts:
                            break

                # Strategy 2: key stored next to the wxSQLite3 "sAlT" marker.
                # This is what private-deployment builds expose when they never
                # build an "x'...'" SQL literal.
                if remaining_salts and SALT_MARKER in data:
                    _scan_salt_markers(
                        [data],
                        db_files,
                        remaining_salts,
                        key_map,
                        tried_keys,
                    )

                if not remaining_salts:
                    break

            # Strategy 3: cipher struct scan (if the first two didn't find all)
            if remaining_salts:
                memory_regions = []
                for base, size in regions:
                    data = _read_process_memory(handle, base, size)
                    if data:
                        memory_regions.append((int(base), int(base) + len(data), data))
                memory_regions.sort(key=lambda item: item[0])
                starts = [item[0] for item in memory_regions]

                page_sizes = {512, 1024, 2048, 4096, 8192, 16384, 32768, 65536}
                t0 = time.time()

                for base, end, data in memory_regions:
                    if time.time() - t0 > timeout:
                        break
                    max_off = len(data) - 0x40
                    off = 0
                    while off >= 0 and off < max_off:
                        flag0, flag4 = struct.unpack_from("<II", data, off)
                        if flag0 in (1, 2) and flag4 in (1, 2, 4096, 8192, 16384):
                            cipher_addr = base + off
                            aes_ctx = struct.unpack_from("<I", data, off + 0x2C)[0]
                            # Validate page_size pointer chain
                            ps_holder = _read_u32(memory_regions, starts, cipher_addr + 0x30)
                            if ps_holder and _valid_ptr(memory_regions, starts, ps_holder, 8):
                                ps_obj = _read_u32(memory_regions, starts, ps_holder + 4)
                                if ps_obj and _valid_ptr(memory_regions, starts, ps_obj + 0x24, 4):
                                    page_size = _read_u32(memory_regions, starts, ps_obj + 0x24)
                                    if page_size in page_sizes:
                                        enc_key = data[off + 8 : off + 24]
                                        if enc_key != b"\x00" * 16 and len(set(enc_key)) >= 6:
                                            for s in list(remaining_salts):
                                                for rel, path, sz, salt, page1 in db_files:
                                                    if salt == s:
                                                        ok, _ = _verify_key_wxwork(enc_key, page1)
                                                        if ok:
                                                            key_map[s] = enc_key.hex()
                                                            remaining_salts.discard(s)
                                                        break
                                            if not remaining_salts:
                                                break
                        off += 4
                    if not remaining_salts:
                        break

        finally:
            kernel32.CloseHandle(handle)

        if not remaining_salts:
            break

    # Cross-verify: try known keys against unmatched salts
    if remaining_salts and key_map:
        for salt_hex in list(remaining_salts):
            for rel, path, sz, s, page1 in db_files:
                if s == salt_hex:
                    for known_key_hex in key_map.values():
                        enc_key = bytes.fromhex(known_key_hex)
                        ok, _ = _verify_key_wxwork(enc_key, page1)
                        if ok:
                            key_map[salt_hex] = known_key_hex
                            remaining_salts.discard(salt_hex)
                    break

    if not key_map:
        raise RuntimeError(
            "Failed to extract any decryption keys from "
            + ", ".join(names)
            + ". Run with --process-name <exe> to force the client process, "
            "and make sure the client is elevated/admin-readable."
        )

    key_map["_db_dir"] = db_dir
    return key_map


def _read_u32(memory_regions, starts, addr):
    idx = bisect.bisect_right(starts, addr) - 1
    if idx < 0:
        return None
    base, end, data = memory_regions[idx]
    if base <= addr and addr + 4 <= end:
        return struct.unpack_from("<I", data, addr - base)[0]
    return None


def _valid_ptr(memory_regions, starts, addr, length=4):
    idx = bisect.bisect_right(starts, addr) - 1
    if idx < 0:
        return False
    base, end, _ = memory_regions[idx]
    return base <= addr and addr + length <= end
