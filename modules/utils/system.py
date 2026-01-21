"""System-specific utilities and platform detection."""

import platform
import subprocess
import sys
from typing import Tuple

_open_dialog_count = 0


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

    # Fallback to PySide6 method
    try:
        from PySide6.QtGui import QCursor

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


def on_dialog_open():
    """Call when a dialog opens. Shows dock icon on macOS if this is the first dialog."""
    global _open_dialog_count
    _open_dialog_count += 1
    if _open_dialog_count == 1 and is_macos():
        _set_macos_activation_policy_regular()


def on_dialog_close():
    """Call when a dialog closes. Hides dock icon on macOS if this was the last dialog."""
    global _open_dialog_count
    _open_dialog_count = max(0, _open_dialog_count - 1)
    if _open_dialog_count == 0 and is_macos():
        _set_macos_activation_policy_accessory()


def _set_macos_activation_policy_regular():
    """Set macOS activation policy to Regular (shows in dock, normal window behavior)."""
    try:
        from AppKit import NSApp, NSApplicationActivationPolicyRegular
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        NSApp.activateIgnoringOtherApps_(True)
    except ImportError:
        pass
    except Exception as e:
        print(f"Warning: Could not set activation policy to regular: {e}")


def _set_macos_activation_policy_accessory():
    """Set macOS activation policy to Accessory (hidden from dock)."""
    try:
        from AppKit import NSApp, NSApplicationActivationPolicyAccessory
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except ImportError:
        pass
    except Exception as e:
        print(f"Warning: Could not set activation policy to accessory: {e}")
