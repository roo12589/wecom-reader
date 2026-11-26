"""Desktop launcher for the packaged Windows / macOS builds.

The packaged application has no command line, so this module fills the gaps:

* locate the WeCom data directory (or remember the last one chosen),
* ask the user to pick a directory when auto-detection fails,
* request administrator rights on Windows (needed to read the key from memory),
* start the local web UI and open it in the default browser.

Build instructions live in ``scripts/build.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from typing import Optional

from .reader import WeComReader
from .web import app, set_reader

APP_NAME = "WeComReader"
APP_TITLE = "企微记录查看器 (WeCom Reader)"
DEFAULT_PORT = 8765

_DB_NAMES = ("session.db", "message.db")


# ----------------------------------------------------------------------
# Paths / config
# ----------------------------------------------------------------------

def _user_data_dir() -> str:
    """Per-user directory for config, logs and decrypted data."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_NAME)
    if sys.platform == "darwin":
        return os.path.join(
            os.path.expanduser("~"), "Library", "Application Support", APP_NAME
        )
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share"
    )
    return os.path.join(base, APP_NAME)


def _config_path() -> str:
    return os.path.join(_user_data_dir(), "config.json")


def _load_config() -> dict:
    try:
        with open(_config_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_config(data: dict) -> None:
    try:
        os.makedirs(_user_data_dir(), exist_ok=True)
        with open(_config_path(), "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _redirect_output() -> None:
    """Send stdout/stderr to a log file for windowed (macOS) builds."""
    try:
        os.makedirs(_user_data_dir(), exist_ok=True)
        stream = open(
            os.path.join(_user_data_dir(), "app.log"),
            "a",
            encoding="utf-8",
            buffering=1,
        )
    except OSError:
        return
    sys.stdout = stream
    sys.stderr = stream


# ----------------------------------------------------------------------
# Directory detection
# ----------------------------------------------------------------------

def _is_plain_sqlite(path: str) -> bool:
    try:
        with open(path, "rb") as handle:
            return handle.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False


def _has_encrypted_db(directory: str) -> bool:
    """True when the directory holds an encrypted WeCom database."""
    for name in _DB_NAMES:
        path = os.path.join(directory, name)
        try:
            if os.path.getsize(path) < 4096:
                continue
        except OSError:
            continue
        if not _is_plain_sqlite(path):
            return True
    return False


def _looks_decrypted(directory: Optional[str]) -> bool:
    """True when the directory already contains decrypted databases."""
    if not directory or not os.path.isdir(directory):
        return False
    return all(_is_plain_sqlite(os.path.join(directory, name)) for name in _DB_NAMES)


def _listdir(path: str) -> list[str]:
    try:
        return os.listdir(path)
    except OSError:
        return []


def _detect_db_dir() -> Optional[str]:
    """Find ``Documents/<vendor>/<account>/Data`` trees with encrypted DBs."""
    documents = os.path.join(os.path.expanduser("~"), "Documents")
    candidates: list[str] = []
    for vendor in _listdir(documents):
        vendor_dir = os.path.join(documents, vendor)
        if not os.path.isdir(vendor_dir):
            continue
        for account in _listdir(vendor_dir):
            data_dir = os.path.join(vendor_dir, account, "Data")
            if os.path.isdir(data_dir) and _has_encrypted_db(data_dir):
                candidates.append(data_dir)
    if not candidates:
        return None

    def _mtime(path: str) -> float:
        for name in _DB_NAMES:
            try:
                return os.path.getmtime(os.path.join(path, name))
            except OSError:
                continue
        return 0.0

    return max(dict.fromkeys(candidates), key=_mtime)


def _macos_script(script: str) -> Optional[str]:
    """Run a short AppleScript and return its stdout (None on cancel/failure)."""
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _pick_directory(title: str, initial: Optional[str] = None) -> Optional[str]:
    """Native folder picker; falls back to a console prompt on Windows."""
    if sys.platform == "darwin" and os.path.exists("/usr/bin/osascript"):
        script = 'POSIX path of (choose folder with prompt "%s")' % title.replace(
            '"', '\\"'
        )
        picked = _macos_script(script)
        return picked.rstrip("/") if picked else None

    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        picked = filedialog.askdirectory(
            title=title, initialdir=initial or os.path.expanduser("~")
        )
        root.destroy()
        return picked or None
    except Exception:
        pass

    if sys.platform == "win32":
        try:
            return input(f"{title}\n路径: ").strip().strip('"') or None
        except (EOFError, KeyboardInterrupt):
            return None
    return None


def _show_error(message: str) -> None:
    print(f"[!] {message}")
    if sys.platform == "darwin" and os.path.exists("/usr/bin/osascript"):
        escaped = (
            message.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        )
        if _macos_script(
            f'display alert "WeCom Reader" message "{escaped}" as critical'
        ) is not None:
            return
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        messagebox.showerror(APP_TITLE, message)
        root.destroy()
    except Exception:
        pass


# ----------------------------------------------------------------------
# Windows elevation
# ----------------------------------------------------------------------

def _is_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _relaunch_as_admin(
    db_dir: str,
    decrypted_dir: str,
    media_dir: Optional[str],
    self_id: Optional[int],
    port: int,
    host: str,
    no_browser: bool,
) -> bool:
    """Start an elevated copy of this executable. True when it was launched."""
    if sys.platform != "win32":
        return False
    params = [f"--db-dir={db_dir}", f"--decrypted-dir={decrypted_dir}"]
    if media_dir:
        params.append(f"--media-dir={media_dir}")
    if self_id is not None:
        params.append(f"--self-id={self_id}")
    params.extend([f"--port={port}", f"--host={host}"])
    if no_browser:
        params.append("--no-browser")
    try:
        import ctypes

        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            subprocess.list2cmdline(params),
            None,
            1,
        )
        return int(result) > 32
    except Exception:
        return False


# ----------------------------------------------------------------------
# Server helpers
# ----------------------------------------------------------------------

def _find_port(preferred: int) -> int:
    """Return the first free port at or after *preferred*."""
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _open_browser_later(url: str, delay: float = 1.0) -> None:
    def _worker() -> None:
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


def _browser_host(host: str) -> str:
    return "127.0.0.1" if host in ("0.0.0.0", "::", "") else host


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=APP_NAME, description=APP_TITLE)
    parser.add_argument("--db-dir", default=None, help="WeCom data directory")
    parser.add_argument("--decrypted-dir", default=None, help="Decrypted DB directory")
    parser.add_argument("--media-dir", default=None, help="Media cache directory")
    parser.add_argument("--self-id", type=int, default=None, help="Current account id")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Web server port")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser")
    parser.add_argument("--reset", action="store_true", help="Forget the saved paths")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        _redirect_output()
    try:
        os.makedirs(_user_data_dir(), exist_ok=True)
    except OSError:
        pass

    config = {} if args.reset else _load_config()
    db_dir = args.db_dir or config.get("db_dir")
    decrypted_dir = args.decrypted_dir or config.get("decrypted_dir")

    if sys.platform == "darwin":
        # macOS cannot read the key from the client's memory; it only browses
        # data decrypted on Windows.
        if _looks_decrypted(args.db_dir):
            db_dir, decrypted_dir = None, args.db_dir
        elif not _looks_decrypted(decrypted_dir):
            picked = _pick_directory(
                "请选择已解密的 wxwork_decrypted 目录（包含 session.db、message.db）",
                decrypted_dir,
            )
            if not picked:
                _show_error(
                    "未选择已解密的数据目录，程序退出。\n\n"
                    "macOS 无法从企业微信进程内存中提取密钥。请先在 Windows 上"
                    "生成 wxwork_decrypted 目录，再拷贝到本机后选择该目录。"
                )
                return 1
            db_dir, decrypted_dir = None, picked
    else:
        # A folder that already holds decrypted DBs is used as-is.
        if _looks_decrypted(db_dir) and not _looks_decrypted(decrypted_dir):
            decrypted_dir = db_dir
        if not db_dir or not os.path.isdir(db_dir):
            db_dir = _detect_db_dir() or db_dir
        if not db_dir or not os.path.isdir(db_dir):
            picked = _pick_directory(
                "请选择企业微信数据目录（包含 session.db、message.db 的 Data 或 Cache 目录）",
                db_dir,
            )
            if not picked:
                _show_error("未选择企业微信数据目录，程序退出。")
                return 1
            db_dir = picked

    if not decrypted_dir:
        decrypted_dir = os.path.join(_user_data_dir(), "decrypted")

    _save_config(
        {
            "db_dir": db_dir,
            "decrypted_dir": decrypted_dir,
            **({"media_dir": args.media_dir} if args.media_dir else {}),
            **({"self_id": args.self_id} if args.self_id is not None else {}),
        }
    )

    # Reading the key from the client's memory requires administrator rights.
    if (
        sys.platform == "win32"
        and getattr(sys, "frozen", False)
        and not _is_admin()
        and not _looks_decrypted(decrypted_dir)
    ):
        if _relaunch_as_admin(
            db_dir,
            decrypted_dir,
            args.media_dir,
            args.self_id,
            args.port,
            args.host,
            args.no_browser,
        ):
            return 0
        print("[!] 未获得管理员权限，无法读取聊天密钥。")

    reader = WeComReader(
        db_dir=db_dir,
        decrypted_dir=decrypted_dir,
        media_dir=args.media_dir,
        self_id=args.self_id,
    )

    try:
        ready = reader.ensure_ready(timeout=120)
    except Exception as exc:  # never prevent the page from starting
        ready = {"ready": False, "error": str(exc)}

    if ready.get("ready"):
        print("[*] 数据已就绪。")
    else:
        detail = ready.get("error") or "未找到可用的解密数据"
        print(f"[!] 数据尚未就绪: {detail}")
        if sys.platform != "win32":
            _show_error(f"无法读取数据：\n{detail}")
            return 1

    set_reader(reader)

    port = _find_port(args.port)
    url = f"http://{_browser_host(args.host)}:{port}"
    if not args.no_browser:
        _open_browser_later(url)

    print(f"[*] 解密数据目录: {decrypted_dir}")
    print(f"[*] 浏览器访问: {url}")
    print("[*] 按 Ctrl+C 退出。")
    try:
        app.run(host=args.host, port=port, debug=False, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
