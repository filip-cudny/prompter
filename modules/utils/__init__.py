"""Utilities module for Promptheus application."""

from .clipboard import ClipboardManager, SystemClipboardManager
from .config import AppConfig, load_config
from .speech_to_text import AudioRecorder, SpeechToTextService
from .system import (
    check_macos_permissions,
    get_cursor_position,
    get_platform,
    is_linux,
    is_macos,
    is_windows,
    on_dialog_close,
    on_dialog_open,
)
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
