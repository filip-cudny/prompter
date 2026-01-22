# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for macOS Promptheus.app bundle."""

import site
import sys
from pathlib import Path

block_cipher = None

PROJECT_ROOT = Path(SPECPATH).parent.parent
HOOKS_DIR = PROJECT_ROOT / "packaging" / "pyinstaller" / "hooks"

def find_sounddevice_lib():
    """Find the portaudio library from _sounddevice_data package."""
    for sp in site.getsitepackages() + [site.getusersitepackages()]:
        lib_path = Path(sp) / "_sounddevice_data" / "portaudio-binaries" / "libportaudio.dylib"
        if lib_path.exists():
            return str(lib_path)
    venv_path = PROJECT_ROOT / ".venv" / "lib"
    for pyver in venv_path.glob("python*"):
        lib_path = pyver / "site-packages" / "_sounddevice_data" / "portaudio-binaries" / "libportaudio.dylib"
        if lib_path.exists():
            return str(lib_path)
    return None

portaudio_lib = find_sounddevice_lib()
sounddevice_binaries = [(portaudio_lib, "_sounddevice_data/portaudio-binaries")] if portaudio_lib else []

a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=sounddevice_binaries,
    datas=[
        (str(PROJECT_ROOT / "settings_example"), "settings_example"),
        (str(PROJECT_ROOT / "modules" / "gui" / "icons" / "svg"), "modules/gui/icons/svg"),
        (str(PROJECT_ROOT / "icon.svg"), "."),
        (str(PROJECT_ROOT / "tray_icon.svg"), "."),
        (str(PROJECT_ROOT / ".env.example"), "."),
    ],
    hiddenimports=[
        "pynput.keyboard._darwin",
        "pynput.mouse._darwin",
        "pynput._util.darwin",
        "sounddevice",
        "_sounddevice_data",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtSvg",
        "objc",
        "AppKit",
        "Foundation",
        "Quartz",
        "openai",
        "httpx",
        "anyio",
        "sniffio",
        "h11",
        "httpcore",
        "certifi",
        "json5",
        "dotenv",
    ],
    hookspath=[str(HOOKS_DIR)],
    hooksconfig={},
    runtime_hooks=[str(PROJECT_ROOT / "packaging" / "pyinstaller" / "runtime_hook.py")],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "PIL",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

if (PROJECT_ROOT / "prompts").exists():
    a.datas += [(str(PROJECT_ROOT / "prompts"), "prompts")]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Promptheus",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Promptheus",
)

icns_path = PROJECT_ROOT / "packaging" / "macos" / "Promptheus.icns"

app = BUNDLE(
    coll,
    name="Promptheus.app",
    icon=str(icns_path) if icns_path.exists() else None,
    bundle_identifier="com.promptheus.app",
    info_plist={
        "CFBundleName": "Promptheus",
        "CFBundleDisplayName": "Promptheus",
        "CFBundleIdentifier": "com.promptheus.app",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription": "Promptheus needs microphone access for speech-to-text functionality.",
        "NSAppleEventsUsageDescription": "Promptheus needs accessibility permissions for global hotkeys.",
    },
)
