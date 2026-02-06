"""System-specific utilities and platform detection."""

import os
import platform
import subprocess
import sys

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


def is_wayland_session() -> bool:
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"


def is_x11_session() -> bool:
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "x11"


def get_wayland_compositor() -> str:
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return "hyprland"
    if os.environ.get("SWAYSOCK"):
        return "sway"
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "gnome" in desktop:
        return "gnome"
    if "kde" in desktop or "plasma" in desktop:
        return "kde"
    return "unknown"


def get_cursor_position() -> tuple[int, int]:
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
    """Check if Input Monitoring permission is granted on macOS.

    Uses AXIsProcessTrusted() which is the authoritative check for
    whether the app can monitor keyboard/mouse input.
    """
    if not is_macos():
        return True

    try:
        from ApplicationServices import AXIsProcessTrusted

        return AXIsProcessTrusted()
    except ImportError:
        return True
    except Exception:
        return True


def show_macos_permissions_help() -> None:
    """Show help and open System Preferences for Input Monitoring."""
    if not is_macos():
        return

    print("\n" + "=" * 60)
    print("INPUT MONITORING PERMISSION REQUIRED")
    print("=" * 60)
    print("Promptheus needs Input Monitoring permission to detect hotkeys.")
    print("")
    print("For unsigned/dev builds: Permission must be RE-GRANTED after each rebuild!")
    print("")
    print("Steps:")
    print("1. Open System Preferences > Security & Privacy > Privacy > Input Monitoring")
    print("2. Remove old Promptheus entries (if any)")
    print("3. Click '+' and add the new Promptheus.app")
    print("4. Restart Promptheus")
    print("=" * 60 + "\n")

    try:
        subprocess.run([
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
        ], check=False)
    except Exception:
        pass


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
