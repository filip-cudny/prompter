"""Utilities module for Promptheus application."""

from .clipboard import ClipboardManager, SystemClipboardManager
from .speech_to_text import SpeechToTextService, AudioRecorder
from .system import (
    get_cursor_position,
    check_macos_permissions,
    get_platform,
    is_macos,
    is_linux,
    is_windows,
    on_dialog_open,
    on_dialog_close,
)
from .config import AppConfig, load_config
from .ui_state import UIStateManager


__all__ = [
    "ClipboardManager",
    "SystemClipboardManager",
    "get_cursor_position",
    "check_macos_permissions",
    "get_platform",
    "is_macos",
    "is_linux",
    "is_windows",
    "on_dialog_open",
    "on_dialog_close",
    "AppConfig",
    "load_config",
    "SpeechToTextService",
    "AudioRecorder",
    "UIStateManager",
]
