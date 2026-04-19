# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Vinted local worker shipped as a Tauri sidecar.
# Build:
#   pyinstaller api/desktop_vinted_server.spec --noconfirm --clean
# Output: ./dist/goupix-vinted-worker(.exe)
#
# Notes:
#  - On Windows we want `console=False` so launching the Tauri app does not pop a cmd window.
#    Logs are written to `%LOCALAPPDATA%\GoupixDex\logs\vinted-worker.log` (see desktop_vinted_server.py).
#  - `nodriver` and `uvicorn` heavily use lazy imports → declare them as hidden imports.

from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# `pyinstaller` exécute toujours le .spec depuis le répertoire courant ; on lance la commande
# depuis `api/` (CI : `working-directory: api`, dev : `cd api && pyinstaller …`).
SPEC_DIR = Path(os.getcwd())
if not (SPEC_DIR / "desktop_vinted_server.py").is_file():
    candidate = Path(__file__).resolve().parent if "__file__" in globals() else None
    if candidate is not None and (candidate / "desktop_vinted_server.py").is_file():
        SPEC_DIR = candidate
    else:
        raise RuntimeError(
            "desktop_vinted_server.spec doit être lancé depuis le dossier `api/` du dépôt."
        )

ENTRY_SCRIPT = str(SPEC_DIR / "desktop_vinted_server.py")

hiddenimports = []
hiddenimports += collect_submodules("nodriver")
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("anyio")
hiddenimports += collect_submodules("httpx")
hiddenimports += collect_submodules("services")
hiddenimports += collect_submodules("services.vinted_wardrobe")
hiddenimports += collect_submodules("core")
hiddenimports += collect_submodules("schemas")
hiddenimports += collect_submodules("models")
hiddenimports += collect_submodules("app_types")
hiddenimports += [
    "pymysql",
    "bcrypt",
    "browser_cookie3",
    "vinted_scraper",
]

datas = []
datas += collect_data_files("nodriver", include_py_files=False)

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
    excludes=[
        "tkinter",
        "PIL.ImageTk",
    ],
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
    name="goupix-vinted-worker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # `console=False` on Windows = no cmd window pops up when Tauri spawns the worker.
    # On macOS/Linux it has no visible effect (Tauri inherits no terminal anyway).
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
