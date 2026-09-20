# PyInstaller spec for the Leboncoin local worker (Tauri sidecar).
# Build from api/: pyinstaller desktop_leboncoin_server.spec --noconfirm --clean

from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

SPEC_DIR = Path(os.getcwd())
if not (SPEC_DIR / "desktop_leboncoin_server.py").is_file():
    candidate = Path(__file__).resolve().parent if "__file__" in globals() else None
    if candidate is not None and (candidate / "desktop_leboncoin_server.py").is_file():
        SPEC_DIR = candidate
    else:
        raise RuntimeError("Run PyInstaller from the api/ folder.")

ENTRY_SCRIPT = str(SPEC_DIR / "desktop_leboncoin_server.py")

hiddenimports = []
hiddenimports += collect_submodules("nodriver")
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("anyio")
hiddenimports += collect_submodules("httpx")
hiddenimports += collect_submodules("services")
hiddenimports += collect_submodules("core")
hiddenimports += collect_submodules("schemas")
hiddenimports += collect_submodules("models")
hiddenimports += ["browser_cookie3", "pymysql", "bcrypt"]

datas = collect_data_files("nodriver", include_py_files=False)
if (SPEC_DIR / "worker_bundled.env").is_file():
    datas += [(str(SPEC_DIR / "worker_bundled.env"), ".")]

block_cipher = None

a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[str(SPEC_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PIL.ImageTk"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="goupix-leboncoin-worker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
