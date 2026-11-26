# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the WeCom Reader desktop application.

Build with ``python scripts/build.py``. The same spec produces:

* Windows: ``dist/WeComReader.exe`` (single file, console window)
* macOS:   ``dist/WeCom Reader.app`` (app bundle, no console)
"""

import os
import re
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))
APP_NAME = "WeComReader"

version = "0.1.0"
try:
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as handle:
        match = re.search(r'^version\s*=\s*"([^"]+)"', handle.read(), re.M)
    if match:
        version = match.group(1)
except OSError:
    pass

datas = [
    (
        os.path.join(ROOT, "wecom_reader", "templates"),
        os.path.join("wecom_reader", "templates"),
    ),
    (
        os.path.join(ROOT, "wecom_reader", "static"),
        os.path.join("wecom_reader", "static"),
    ),
]

hiddenimports = [
    "wecom_reader.web",
    "wecom_reader.reader",
    "wecom_reader.crypto.decrypt",
    "wecom_reader.crypto.key_extract",
    "wecom_reader.db.contact",
    "wecom_reader.db.media",
    "wecom_reader.db.message",
    "wecom_reader.db.proto",
    "wecom_reader.db.session",
]

# Windows uses a Tk folder picker; macOS uses the native AppleScript dialog.
if sys.platform == "win32":
    hiddenimports += ["tkinter", "tkinter.filedialog", "tkinter.messagebox"]

a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "_pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    app = BUNDLE(
        exe,
        name="WeCom Reader.app",
        icon=None,
        bundle_identifier="com.wecomreader.desktop",
        info_plist={
            "CFBundleName": "WeCom Reader",
            "CFBundleDisplayName": "企微记录查看器",
            "CFBundleShortVersionString": version,
            "CFBundleVersion": version,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "10.15",
            "LSApplicationCategoryType": "public.app-category.productivity",
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,
    )
