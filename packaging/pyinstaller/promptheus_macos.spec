# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for macOS Promptheus application bundle."""

import site
import sys
from pathlib import Path

block_cipher = None

PROJECT_ROOT = Path(SPECPATH).parent.parent
HOOKS_DIR = PROJECT_ROOT / "packaging" / "pyinstaller" / "hooks"
MACOS_DIR = PROJECT_ROOT / "packaging" / "macos"


def find_sounddevice_lib():
    """Find the portaudio library from _sounddevice_data package."""
    lib_name = "libportaudio.dylib"
    for sp in site.getsitepackages() + [site.getusersitepackages()]:
        lib_path = Path(sp) / "_sounddevice_data" / "portaudio-binaries" / lib_name
        if lib_path.exists():
            return str(lib_path)
    venv_path = PROJECT_ROOT / ".venv" / "lib"
    for pyver in venv_path.glob("python*"):
        lib_path = pyver / "site-packages" / "_sounddevice_data" / "portaudio-binaries" / lib_name
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
        # macOS-specific pynput backends
        "pynput.keyboard._darwin",
        "pynput.mouse._darwin",
        "pynput._util.darwin",
        # macOS Objective-C bridge
        "objc",
        "AppKit",
        "Foundation",
        "Cocoa",
        "CoreFoundation",
        "Quartz",
        # Audio
        "sounddevice",
        "_sounddevice_data",
        # Qt
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtSvg",
        # Network/API
        "openai",
        "httpx",
        "anyio",
        "sniffio",
        "h11",
        "httpcore",
        "certifi",
        # Config
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
    upx=False,  # UPX disabled on macOS (causes issues with signed apps)
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=str(MACOS_DIR / "entitlements.plist"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Promptheus",
)

icns_path = MACOS_DIR / "Promptheus.icns"

app = BUNDLE(
    coll,
    name="Promptheus.app",
    icon=str(icns_path) if icns_path.exists() else None,
    bundle_identifier="com.promptheus.app",
    info_plist={
        "CFBundleName": "Promptheus",
        "CFBundleDisplayName": "Promptheus",
        "CFBundleExecutable": "Promptheus",
        "CFBundleIdentifier": "com.promptheus.app",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "LSMinimumSystemVersion": "10.15",
        "LSUIElement": True,  # Hide from Dock (menu bar app)
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription": "Promptheus requires microphone access for speech-to-text functionality.",
        "NSAppleEventsUsageDescription": "Promptheus uses Apple Events for system integration.",
    },
)
