#!/usr/bin/env python3
"""Build the standalone WeCom Reader desktop app for the current OS.

The build must run on the target operating system (PyInstaller cannot
cross-compile):

    Windows:  python scripts/build.py   -> dist/WeComReader.exe
    macOS:    python3 scripts/build.py  -> dist/WeCom Reader.app

The packaged application bundles the Python runtime and every dependency, so
end users do not need Python installed.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "scripts", "wecom_reader.spec")
DIST = os.path.join(ROOT, "dist")
BUILD = os.path.join(ROOT, "build")


def _version() -> str:
    try:
        with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as handle:
            match = re.search(r'^version\s*=\s*"([^"]+)"', handle.read(), re.M)
        if match:
            return match.group(1)
    except OSError:
        pass
    return "0.0.0"


def _archive_windows(version: str) -> str | None:
    source = os.path.join(DIST, "WeComReader.exe")
    if not os.path.isfile(source):
        return None
    target = os.path.join(DIST, f"WeComReader-{version}-windows-x64.zip")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(source, "WeComReader.exe")
    return target


def _archive_macos(version: str) -> str | None:
    source = os.path.join(DIST, "WeCom Reader.app")
    if not os.path.isdir(source):
        return None
    target = os.path.join(DIST, f"WeComReader-{version}-macos.dmg")
    if os.path.exists(target):
        os.remove(target)
    subprocess.run(
        [
            "hdiutil",
            "create",
            "-volname",
            "WeCom Reader",
            "-srcfolder",
            source,
            "-ov",
            "-format",
            "UDZO",
            target,
        ],
        check=True,
    )
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the WeCom Reader desktop app")
    parser.add_argument("--clean", action="store_true", help="Remove build/ and dist/ first")
    parser.add_argument("--no-archive", action="store_true", help="Skip the zip/dmg step")
    args = parser.parse_args()

    if sys.version_info < (3, 10):
        sys.exit("需要 Python 3.10 或更高版本。")

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit(
            "缺少 PyInstaller，请先运行：\n"
            f"  {sys.executable} -m pip install -r scripts/requirements-build.txt"
        )

    if args.clean:
        shutil.rmtree(BUILD, ignore_errors=True)
        shutil.rmtree(DIST, ignore_errors=True)

    print(f"[*] Building for {sys.platform} ...")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", SPEC],
        cwd=ROOT,
        check=True,
    )

    version = _version()
    targets: list[str] = []
    if sys.platform == "win32":
        targets.append(os.path.join(DIST, "WeComReader.exe"))
        if not args.no_archive:
            archive = _archive_windows(version)
            if archive:
                targets.append(archive)
    elif sys.platform == "darwin":
        targets.append(os.path.join(DIST, "WeCom Reader.app"))
        if not args.no_archive:
            archive = _archive_macos(version)
            if archive:
                targets.append(archive)
    else:
        targets.append(os.path.join(DIST, "WeComReader"))

    print("\n[*] Build finished:")
    for target in targets:
        print(f"    {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
