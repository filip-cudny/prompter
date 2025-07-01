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
    speech_toggle_hotkey_pressed = pyqtSignal()


class HotkeyConfig:
    """Configuration for platform-specific hotkeys."""

    def __init__(self):
        system = platform.system().lower()

        if system == "darwin":  # macOS
            self.context_menu_hotkey = "cmd+f1"
            self.re_execute_hotkey = "cmd+f2"
            self.speech_toggle_hotkey = "shift+f1"
        else:  # Linux and others
            self.context_menu_hotkey = "ctrl+f1"
            self.re_execute_hotkey = "ctrl+f2"
            self.speech_toggle_hotkey = "shift+f1"

        # Parse hotkeys to extract keys and modifiers
        self.context_menu_parsed = self._parse_hotkey(self.context_menu_hotkey)
        self.re_execute_parsed = self._parse_hotkey(self.re_execute_hotkey)
        self.speech_toggle_parsed = self._parse_hotkey(self.speech_toggle_hotkey)

    def _parse_hotkey(self, hotkey_str: str) -> dict:
        """Parse hotkey string and return modifiers and key."""
        parts = hotkey_str.lower().split('+')
        key_name = parts[-1]
        modifier_names = parts[:-1]
        
        # Map string names to Key objects
        key_map = {
            'f1': Key.f1, 'f2': Key.f2, 'f3': Key.f3, 'f4': Key.f4, 'f5': Key.f5,
            'f6': Key.f6, 'f7': Key.f7, 'f8': Key.f8, 'f9': Key.f9, 'f10': Key.f10,
            'f11': Key.f11, 'f12': Key.f12, 'f13': Key.f13, 'f14': Key.f14, 'f15': Key.f15,
            'f16': Key.f16, 'f17': Key.f17, 'f18': Key.f18, 'f19': Key.f19, 'f20': Key.f20,
            'esc': Key.esc, 'escape': Key.esc, 'space': Key.space, 'tab': Key.tab,
            'enter': Key.enter, 'return': Key.enter, 'up': Key.up, 'down': Key.down,
            'left': Key.left, 'right': Key.right, 'home': Key.home, 'end': Key.end,
            'delete': Key.delete, 'backspace': Key.backspace, 'page_up': Key.page_up,
            'page_down': Key.page_down, 'caps_lock': Key.caps_lock
        }
        
        # Add letter and number keys
        for i in range(26):
            letter = chr(ord('a') + i)
            key_map[letter] = keyboard.KeyCode.from_char(letter)
        
        for i in range(10):
            key_map[str(i)] = keyboard.KeyCode.from_char(str(i))
        
        modifier_map = {
            'cmd': [Key.cmd, Key.cmd_l, Key.cmd_r],
            'ctrl': [Key.ctrl, Key.ctrl_l, Key.ctrl_r],
            'shift': [Key.shift, Key.shift_l, Key.shift_r],
            'alt': [Key.alt, Key.alt_l, Key.alt_r],
            'meta': [Key.cmd, Key.cmd_l, Key.cmd_r],  # alias for cmd
            'super': [Key.cmd, Key.cmd_l, Key.cmd_r]  # alias for cmd
        }
        
        parsed_modifiers = []
        for mod_name in modifier_names:
            if mod_name in modifier_map:
                parsed_modifiers.extend(modifier_map[mod_name])
        
        parsed_key = key_map.get(key_name)
        if parsed_key is None:
            parsed_key = keyboard.KeyCode.from_char(key_name)
        
        return {
            'modifiers': parsed_modifiers,
            'key': parsed_key
        }


HOTKEY_CONFIG = HotkeyConfig()


class PyQtHotkeyListener:
    """Handles global hotkey detection using pynput with Qt signals."""

    def __init__(self):
        self.listener: Optional[keyboard.Listener] = None
        self.pressed_keys: Set[Key] = set()
        self.re_execute_hotkey_pressed = False
        self.context_menu_hotkey_pressed = False
        self.speech_toggle_hotkey_pressed = False
        self.signals = HotkeySignals()
        self.running = False
        self.re_execute_reset_timer: Optional[threading.Timer] = None
        self.context_menu_reset_timer: Optional[threading.Timer] = None
        self.speech_toggle_reset_timer: Optional[threading.Timer] = None

    def connect_re_execute_callback(self, callback: Callable[[], None]) -> None:
        """Connect callback for re-execute hotkey (Cmd/Ctrl+F2)."""
        self.signals.re_execute_hotkey_pressed.connect(callback)

    def connect_context_menu_callback(self, callback: Callable[[], None]) -> None:
        """Connect callback for context menu hotkey (Cmd/Ctrl+F1)."""
        self.signals.context_menu_hotkey_pressed.connect(callback)

    def connect_speech_toggle_callback(self, callback: Callable[[], None]) -> None:
        """Connect callback for speech toggle hotkey (Shift+F1)."""
        self.signals.speech_toggle_hotkey_pressed.connect(callback)

    def start(self) -> None:
        """Start the hotkey listener."""
        if self.running:
            return

        try:
            self.listener = keyboard.Listener(
                on_press=self._on_press, on_release=self._on_release, suppress=False
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

        if self.speech_toggle_reset_timer:
            self.speech_toggle_reset_timer.cancel()
            self.speech_toggle_reset_timer = None

        if self.listener:
            self.listener.stop()
            self.listener = None

        self.pressed_keys.clear()
        self.re_execute_hotkey_pressed = False
        self.context_menu_hotkey_pressed = False
        self.speech_toggle_hotkey_pressed = False

    def _on_press(self, key: Key) -> None:
        """Handle key press events."""
        self.pressed_keys.add(key)

        if self._is_re_execute_hotkey_pressed():
            self._trigger_re_execute_hotkey()
        elif self._is_context_menu_hotkey_pressed():
            self._trigger_context_menu_hotkey()
        elif self._is_speech_toggle_hotkey_pressed():
            self._trigger_speech_toggle_hotkey()

    def _on_release(self, key: Key) -> None:
        """Handle key release events."""
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)

    def _is_re_execute_hotkey_pressed(self) -> bool:
        """Check if re-execute hotkey combination is pressed."""
        config = HOTKEY_CONFIG.re_execute_parsed
        modifier_pressed = any(
            mod in self.pressed_keys for mod in config['modifiers']
        )
        key_pressed = config['key'] in self.pressed_keys
        return modifier_pressed and key_pressed

    def _is_context_menu_hotkey_pressed(self) -> bool:
        """Check if context menu hotkey combination is pressed."""
        config = HOTKEY_CONFIG.context_menu_parsed
        modifier_pressed = any(
            mod in self.pressed_keys for mod in config['modifiers']
        )
        key_pressed = config['key'] in self.pressed_keys
        return modifier_pressed and key_pressed

    def _is_speech_toggle_hotkey_pressed(self) -> bool:
        """Check if speech toggle hotkey combination is pressed."""
        config = HOTKEY_CONFIG.speech_toggle_parsed
        modifier_pressed = any(
            mod in self.pressed_keys for mod in config['modifiers']
        )
        key_pressed = config['key'] in self.pressed_keys
        return modifier_pressed and key_pressed

    def _trigger_re_execute_hotkey(self) -> None:
        """Trigger re-execute hotkey signal if not already triggered."""
        if not self.re_execute_hotkey_pressed:
            self.re_execute_hotkey_pressed = True
            self.signals.re_execute_hotkey_pressed.emit()
            self.re_execute_reset_timer = threading.Timer(
                1.0, self._reset_re_execute_hotkey_flag
            )
            self.re_execute_reset_timer.start()

    def _trigger_context_menu_hotkey(self) -> None:
        """Trigger context menu hotkey signal if not already triggered."""
        if not self.context_menu_hotkey_pressed:
            self.context_menu_hotkey_pressed = True
            self.signals.context_menu_hotkey_pressed.emit()
            self.context_menu_reset_timer = threading.Timer(
                1.0, self._reset_context_menu_hotkey_flag
            )
            self.context_menu_reset_timer.start()

    def _trigger_speech_toggle_hotkey(self) -> None:
        """Trigger speech toggle hotkey signal if not already triggered."""
        if not self.speech_toggle_hotkey_pressed:
            self.speech_toggle_hotkey_pressed = True
            self.signals.speech_toggle_hotkey_pressed.emit()
            self.speech_toggle_reset_timer = threading.Timer(
                1.0, self._reset_speech_toggle_hotkey_flag
            )
            self.speech_toggle_reset_timer.start()

    def _reset_re_execute_hotkey_flag(self) -> None:
        """Reset re-execute hotkey flag to prevent rapid firing."""
        self.re_execute_hotkey_pressed = False
        self.re_execute_reset_timer = None

    def _reset_context_menu_hotkey_flag(self) -> None:
        """Reset context menu hotkey flag to prevent rapid firing."""
        self.context_menu_hotkey_pressed = False
        self.context_menu_reset_timer = None

    def _reset_speech_toggle_hotkey_flag(self) -> None:
        """Reset speech toggle hotkey flag to prevent rapid firing."""
        self.speech_toggle_hotkey_pressed = False
        self.speech_toggle_reset_timer = None


class PyQtHotkeyManager:
    """Manages global hotkey detection and configuration using PyQt5."""

    def __init__(
        self,
    ):
        self.hotkey = HOTKEY_CONFIG.re_execute_hotkey
        self.listener = PyQtHotkeyListener()
        self.running = False

    def connect_re_execute_callback(self, callback: Callable[[], None]) -> None:
        """Connect callback for re-execute hotkey activation."""
        self.listener.connect_re_execute_callback(callback)

    def connect_context_menu_callback(self, callback: Callable[[], None]) -> None:
        """Connect callback for context menu hotkey activation."""
        self.listener.connect_context_menu_callback(callback)

    def connect_speech_toggle_callback(self, callback: Callable[[], None]) -> None:
        """Connect callback for speech toggle hotkey activation."""
        self.listener.connect_speech_toggle_callback(callback)

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

        for modifier in parts[:-1]:
            if modifier not in valid_modifiers:
                return False

        key = parts[-1]
        if key not in valid_keys:
            return False

        return True
