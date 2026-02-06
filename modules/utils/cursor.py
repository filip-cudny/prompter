"""Cursor position detection for IPC commands, with Wayland compositor support."""

import json
import subprocess

from modules.utils.system import get_wayland_compositor, is_wayland_session


def get_cursor_position_for_ipc() -> tuple[int, int] | None:
    if is_wayland_session():
        pos = _get_cursor_wayland()
        if pos:
            return pos

    pos = _get_cursor_xdotool()
    if pos:
        return pos

    pos = _get_cursor_qt()
    if pos:
        return pos

    return None


def _get_cursor_wayland() -> tuple[int, int] | None:
    compositor = get_wayland_compositor()

    if compositor == "hyprland":
        return _get_cursor_hyprland()
    if compositor == "sway":
        return _get_cursor_sway()

    return None


def _get_cursor_hyprland() -> tuple[int, int] | None:
    try:
        result = subprocess.run(
            ["hyprctl", "cursorpos"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(",")
            if len(parts) == 2:
                return int(parts[0].strip()), int(parts[1].strip())
    except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
        pass
    return None


def _get_cursor_sway() -> tuple[int, int] | None:
    try:
        result = subprocess.run(
            ["swaymsg", "-t", "get_seats", "--raw"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            seats = json.loads(result.stdout)
            for seat in seats:
                cursor = seat.get("cursor", {})
                x = cursor.get("x")
                y = cursor.get("y")
                if x is not None and y is not None:
                    return int(x), int(y)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired):
        pass
    return None


def _get_cursor_xdotool() -> tuple[int, int] | None:
    try:
        result = subprocess.run(
            ["xdotool", "getmouselocation", "--shell"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            values = {}
            for line in result.stdout.strip().splitlines():
                if "=" in line:
                    key, val = line.split("=", 1)
                    values[key] = val
            x = values.get("X")
            y = values.get("Y")
            if x is not None and y is not None:
                return int(x), int(y)
    except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
        pass
    return None


def _get_cursor_qt() -> tuple[int, int] | None:
    try:
        from PySide6.QtWidgets import QApplication

        if not QApplication.instance():
            return None

        from PySide6.QtGui import QCursor

        pos = QCursor.pos()
        if pos.x() != 0 or pos.y() != 0:
            return pos.x(), pos.y()
    except Exception:
        pass
    return None
