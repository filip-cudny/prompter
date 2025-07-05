"""System-specific utilities and platform detection."""

import platform
import subprocess
import sys
from typing import Tuple, Optional
from core.exceptions import HotkeyError


def get_platform() -> str:
    """Get the current platform name."""
    return platform.system()


def is_macos() -> bool:
    """Check if running on macOS."""
    return platform.system() == "Darwin"


def is_linux() -> bool:
    """Check if running on Linux."""
    return platform.system() == "Linux"


def is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system() == "Windows"


def get_cursor_position() -> Tuple[int, int]:
    """Get absolute cursor position across all displays."""
    try:
        from pynput.mouse import Controller

        mouse = Controller()
        x, y = mouse.position
        return int(x), int(y)
    except Exception:
        pass

    # Fallback to PyQt5 method
    try:
        from PyQt5.QtGui import QCursor

        cursor_pos = QCursor.pos()
        return cursor_pos.x(), cursor_pos.y()
    except Exception:
        pass

    return 0, 0


def check_macos_permissions() -> bool:
    """Check if accessibility permissions are granted on macOS."""
    if not is_macos():
        return True

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from pynput import keyboard; listener = keyboard.Listener(lambda key: None); listener.start(); listener.stop()",
            ],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def show_macos_permissions_help() -> None:
    """Show help message for macOS accessibility permissions."""
    if is_macos():
        print("Warning: Accessibility permissions may be required on macOS")
        print("Go to System Preferences > Security & Privacy > Privacy > Accessibility")
        print("and grant access to Terminal or your Python application")


def get_process_info() -> dict:
    """Get information about the current process."""
    import os
    import psutil

    try:
        process = psutil.Process(os.getpid())
        return {
            "pid": process.pid,
            "name": process.name(),
            "exe": process.exe(),
            "cmdline": process.cmdline(),
            "cwd": process.cwd(),
            "username": process.username(),
        }
    except Exception:
        return {
            "pid": os.getpid(),
            "name": "unknown",
            "exe": sys.executable,
            "cmdline": sys.argv,
            "cwd": os.getcwd(),
            "username": "unknown",
        }


def is_process_running(process_name: str) -> bool:
    """Check if a process with the given name is running."""
    try:
        import psutil

        for process in psutil.process_iter(["name"]):
            if process.info["name"] == process_name:
                return True
        return False
    except Exception:
        return False


def get_screen_info() -> dict:
    """Get information about the screen(s)."""
    try:
        from PyQt5.QtWidgets import QApplication, QDesktopWidget

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        desktop = QDesktopWidget()
        screen = desktop.screenGeometry()

        screen_info = {
            "width": screen.width(),
            "height": screen.height(),
            "dpi": desktop.logicalDpiX(),
        }

        return screen_info
    except Exception:
        return {
            "width": 1920,
            "height": 1080,
            "dpi": 96,
        }


def validate_hotkey_format(hotkey: str) -> bool:
    """Validate hotkey format (e.g., 'shift+f1', 'ctrl+alt+x')."""
    if not hotkey:
        return False

    parts = hotkey.lower().split("+")
    if len(parts) < 2:
        return False

    valid_modifiers = {"shift", "ctrl", "alt", "cmd", "meta", "super"}
    valid_keys = {
        "f1",
        "f2",
        "f3",
        "f4",
        "f5",
        "f6",
        "f7",
        "f8",
        "f9",
        "f10",
        "f11",
        "f12",
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "i",
        "j",
        "k",
        "l",
        "m",
        "n",
        "o",
        "p",
        "q",
        "r",
        "s",
        "t",
        "u",
        "v",
        "w",
        "x",
        "y",
        "z",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "0",
        "space",
        "tab",
        "enter",
        "return",
        "esc",
        "escape",
        "up",
        "down",
        "left",
        "right",
        "home",
        "end",
        "page_up",
        "page_down",
        "insert",
        "delete",
    }

    # All parts except the last should be modifiers
    for modifier in parts[:-1]:
        if modifier not in valid_modifiers:
            return False

    # Last part should be a key
    key = parts[-1]
    if key not in valid_keys:
        return False

    return True


def get_environment_info() -> dict:
    """Get information about the environment."""
    return {
        "platform": get_platform(),
        "python_version": sys.version,
        "executable": sys.executable,
        "path": sys.path,
        "process_info": get_process_info(),
        "screen_info": get_screen_info(),
    }
