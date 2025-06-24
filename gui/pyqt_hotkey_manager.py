"""PyQt5-based hotkey manager for global hotkey detection."""

import platform
import threading
from typing import Set, Optional, Callable
from PyQt5.QtCore import QObject, pyqtSignal
from pynput import keyboard
from pynput.keyboard import Key
from core.exceptions import HotkeyError


class HotkeySignals(QObject):
    """Qt signals for thread-safe communication between pynput and Qt."""
    re_execute_hotkey_pressed = pyqtSignal()
    context_menu_hotkey_pressed = pyqtSignal()


class HotkeyConfig:
    """Configuration for platform-specific hotkeys."""
    
    def __init__(self):
        system = platform.system().lower()
        
        if system == 'darwin':  # macOS
            self.context_menu_hotkey = 'cmd+f2'
            self.re_execute_hotkey = 'cmd+f1'
            self.modifier_keys = [Key.cmd, Key.cmd_l, Key.cmd_r]
        else:  # Linux and others
            self.context_menu_hotkey = 'ctrl+f2'
            self.re_execute_hotkey = 'ctrl+f1'
            self.modifier_keys = [Key.ctrl, Key.ctrl_l, Key.ctrl_r]


HOTKEY_CONFIG = HotkeyConfig()


class PyQtHotkeyListener:
    """Handles global hotkey detection using pynput with Qt signals."""

    def __init__(self):
        self.listener: Optional[keyboard.Listener] = None
        self.pressed_keys: Set[Key] = set()
        self.re_execute_hotkey_pressed = False
        self.context_menu_hotkey_pressed = False
        self.signals = HotkeySignals()
        self.running = False
        self.re_execute_reset_timer: Optional[threading.Timer] = None
        self.context_menu_reset_timer: Optional[threading.Timer] = None

    def connect_re_execute_callback(self, callback: Callable[[], None]) -> None:
        """Connect callback for re-execute hotkey (Cmd/Ctrl+F1)."""
        self.signals.re_execute_hotkey_pressed.connect(callback)

    def connect_context_menu_callback(self, callback: Callable[[], None]) -> None:
        """Connect callback for context menu hotkey (Cmd/Ctrl+F2)."""
        self.signals.context_menu_hotkey_pressed.connect(callback)

    def start(self) -> None:
        """Start the hotkey listener."""
        if self.running:
            return

        try:
            self.listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
                suppress=False
            )
            self.listener.start()
            self.running = True
        except Exception as e:
            raise HotkeyError(f"Failed to start hotkey listener: {e}") from e

    def stop(self) -> None:
        """Stop the hotkey listener."""
        self.running = False

        if self.re_execute_reset_timer:
            self.re_execute_reset_timer.cancel()
            self.re_execute_reset_timer = None

        if self.context_menu_reset_timer:
            self.context_menu_reset_timer.cancel()
            self.context_menu_reset_timer = None

        if self.listener:
            self.listener.stop()
            self.listener = None

        self.pressed_keys.clear()
        self.re_execute_hotkey_pressed = False
        self.context_menu_hotkey_pressed = False

    def _on_press(self, key: Key) -> None:
        """Handle key press events."""
        self.pressed_keys.add(key)

        if self._is_re_execute_hotkey_pressed():
            self._trigger_re_execute_hotkey()
        elif self._is_context_menu_hotkey_pressed():
            self._trigger_context_menu_hotkey()

    def _on_release(self, key: Key) -> None:
        """Handle key release events."""
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)

    def _is_re_execute_hotkey_pressed(self) -> bool:
        """Check if re-execute hotkey combination is pressed."""
        modifier_pressed = any(
            mod in self.pressed_keys for mod in HOTKEY_CONFIG.modifier_keys
        )
        f1_pressed = Key.f1 in self.pressed_keys
        return modifier_pressed and f1_pressed

    def _is_context_menu_hotkey_pressed(self) -> bool:
        """Check if context menu hotkey combination is pressed."""
        modifier_pressed = any(
            mod in self.pressed_keys for mod in HOTKEY_CONFIG.modifier_keys
        )
        f2_pressed = Key.f2 in self.pressed_keys
        return modifier_pressed and f2_pressed

    def _trigger_re_execute_hotkey(self) -> None:
        """Trigger re-execute hotkey signal if not already triggered."""
        if not self.re_execute_hotkey_pressed:
            self.re_execute_hotkey_pressed = True
            self.signals.re_execute_hotkey_pressed.emit()
            self.re_execute_reset_timer = threading.Timer(1.0, self._reset_re_execute_hotkey_flag)
            self.re_execute_reset_timer.start()

    def _trigger_context_menu_hotkey(self) -> None:
        """Trigger context menu hotkey signal if not already triggered."""
        if not self.context_menu_hotkey_pressed:
            self.context_menu_hotkey_pressed = True
            self.signals.context_menu_hotkey_pressed.emit()
            self.context_menu_reset_timer = threading.Timer(1.0, self._reset_context_menu_hotkey_flag)
            self.context_menu_reset_timer.start()

    def _reset_re_execute_hotkey_flag(self) -> None:
        """Reset re-execute hotkey flag to prevent rapid firing."""
        self.re_execute_hotkey_pressed = False
        self.re_execute_reset_timer = None

    def _reset_context_menu_hotkey_flag(self) -> None:
        """Reset context menu hotkey flag to prevent rapid firing."""
        self.context_menu_hotkey_pressed = False
        self.context_menu_reset_timer = None


class PyQtHotkeyManager:
    """Manages global hotkey detection and configuration using PyQt5."""

    def __init__(self, hotkey: Optional[str] = None):
        self.hotkey = hotkey.lower() if hotkey else HOTKEY_CONFIG.re_execute_hotkey
        self.listener = PyQtHotkeyListener()
        self.running = False

    def connect_re_execute_callback(self, callback: Callable[[], None]) -> None:
        """Connect callback for re-execute hotkey activation."""
        self.listener.connect_re_execute_callback(callback)

    def connect_context_menu_callback(self, callback: Callable[[], None]) -> None:
        """Connect callback for context menu hotkey activation."""
        self.listener.connect_context_menu_callback(callback)

    def start(self) -> None:
        """Start hotkey detection."""
        if self.running:
            return

        try:
            self.listener.start()
            self.running = True
        except Exception as e:
            raise HotkeyError(f"Failed to start hotkey manager: {e}") from e

    def stop(self) -> None:
        """Stop hotkey detection."""
        self.running = False
        self.listener.stop()

    def is_running(self) -> bool:
        """Check if hotkey detection is running."""
        return self.running

    def get_hotkey(self) -> str:
        """Get the current hotkey combination."""
        return self.hotkey

    def set_hotkey(self, hotkey: str) -> None:
        """Set a new hotkey combination."""
        if not self._validate_hotkey(hotkey):
            raise HotkeyError(f"Invalid hotkey format: {hotkey}")

        was_running = self.running
        if was_running:
            self.stop()

        self.hotkey = hotkey.lower()

        if was_running:
            self.start()

    def _validate_hotkey(self, hotkey: str) -> bool:
        """Validate hotkey format."""
        if not hotkey:
            return False

        parts = hotkey.lower().split('+')
        if len(parts) < 2:
            return False

        valid_modifiers = {'shift', 'ctrl', 'alt', 'cmd', 'meta', 'super'}
        valid_keys = {
            'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
            'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
            'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
            '1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
            'space', 'tab', 'enter', 'return', 'esc', 'escape',
            'up', 'down', 'left', 'right',
            'home', 'end', 'page_up', 'page_down', 'insert', 'delete',
        }

        for modifier in parts[:-1]:
            if modifier not in valid_modifiers:
                return False

        key = parts[-1]
        if key not in valid_keys:
            return False

        return True