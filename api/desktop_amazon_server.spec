# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — worker Amazon local (Tauri sidecar).
# Depuis `api/` :
#   pyinstaller desktop_amazon_server.spec --noconfirm --clean
# Sortie : ./dist/goupix-amazon-worker(.exe)

from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = Path(os.getcwd())
if not (SPEC_DIR / "desktop_amazon_server.py").is_file():
    candidate = Path(__file__).resolve().parent if "__file__" in globals() else None
    if candidate is not None and (candidate / "desktop_amazon_server.py").is_file():
        SPEC_DIR = candidate
    else:
        raise RuntimeError(
            "desktop_amazon_server.spec doit être lancé depuis le dossier `api/` du dépôt."
        )

ENTRY_SCRIPT = str(SPEC_DIR / "desktop_amazon_server.py")

# Ne pas utiliser collect_submodules("core") : cela tire SQLAlchemy / l’API entière.
hiddenimports: list[str] = [
    "core.deps",
    "core.win32_asyncio",
    "worker_env_bootstrap",
    "services.os_service",
    "services.amazon_profile_session_service",
    "browser_cookie3",
    "nodriver",
    "amazon_config",
    "amazon_http",
    "amazon_nodriver",
    "amazon_parse",
    "nodriver_executor",
    "scraper",
    "bs4",
    "soupsieve",
]
hiddenimports += collect_submodules("nodriver")
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("httpx")
hiddenimports += collect_submodules("anyio")
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("starlette")

block_cipher = None

a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[str(SPEC_DIR)],
    binaries=[],
    datas=[],
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
    name="goupix-amazon-worker",
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
