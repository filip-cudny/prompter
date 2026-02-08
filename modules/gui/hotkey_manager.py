"""PySide6-based hotkey manager for global hotkey detection."""

import os
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from pynput import keyboard
from pynput.keyboard import Key
from PySide6.QtCore import QObject, Signal

from core.exceptions import HotkeyError
from modules.utils.config import ConfigService
from modules.utils.keymap import KeymapManager


def _write_hotkey_debug_log(message: str) -> None:
    """Write hotkey debug info to help diagnose hotkey issues."""
    from modules.utils.paths import get_debug_log_path

    timestamp = datetime.now().isoformat()
    with open(get_debug_log_path(), "a") as f:
        f.write(f"[{timestamp}] HOTKEY: {message}\n")


class HotkeySignals(QObject):
    """Qt signals for thread-safe communication between pynput and Qt."""

    action_triggered = Signal(str)


class HotkeyConfig:
    """Configuration for platform-specific hotkeys from keymap system."""

    def __init__(self, keymap_manager: KeymapManager | None = None):
        self.keymap_manager = keymap_manager or KeymapManager([])

    def _parse_hotkey(self, hotkey_str: str) -> dict:
        """Parse hotkey string and return modifiers and key."""
        parts = hotkey_str.lower().split("+")
        key_name = parts[-1]
        modifier_names = parts[:-1]

        # Map string names to Key objects
        key_map = {
            "f1": Key.f1,
            "f2": Key.f2,
            "f3": Key.f3,
            "f4": Key.f4,
            "f5": Key.f5,
            "f6": Key.f6,
            "f7": Key.f7,
            "f8": Key.f8,
            "f9": Key.f9,
            "f10": Key.f10,
            "f11": Key.f11,
            "f12": Key.f12,
            "f13": Key.f13,
            "f14": Key.f14,
            "f15": Key.f15,
            "f16": Key.f16,
            "f17": Key.f17,
            "f18": Key.f18,
            "f19": Key.f19,
            "f20": Key.f20,
            "esc": Key.esc,
            "escape": Key.esc,
            "space": Key.space,
            "tab": Key.tab,
            "enter": Key.enter,
            "return": Key.enter,
            "up": Key.up,
            "down": Key.down,
            "left": Key.left,
            "right": Key.right,
            "home": Key.home,
            "end": Key.end,
            "delete": Key.delete,
            "backspace": Key.backspace,
            "page_up": Key.page_up,
            "page_down": Key.page_down,
            "caps_lock": Key.caps_lock,
        }

        # Add letter and number keys
        for i in range(26):
            letter = chr(ord("a") + i)
            key_map[letter] = keyboard.KeyCode.from_char(letter)

        for i in range(10):
            key_map[str(i)] = keyboard.KeyCode.from_char(str(i))

        modifier_map = {
            "cmd": [Key.cmd, Key.cmd_l, Key.cmd_r],
            "ctrl": [Key.ctrl, Key.ctrl_l, Key.ctrl_r],
            "shift": [Key.shift, Key.shift_l, Key.shift_r],
            "alt": [Key.alt, Key.alt_l, Key.alt_r],
            "meta": [Key.cmd, Key.cmd_l, Key.cmd_r],  # alias for cmd
            "super": [Key.cmd, Key.cmd_l, Key.cmd_r],  # alias for cmd
        }

        modifier_groups = []
        for mod_name in modifier_names:
            if mod_name in modifier_map:
                modifier_groups.append(modifier_map[mod_name])

        parsed_key = key_map.get(key_name)
        if parsed_key is None:
            parsed_key = keyboard.KeyCode.from_char(key_name)

        return {"modifier_groups": modifier_groups, "key": parsed_key}


# Global hotkey config will be initialized when needed
HOTKEY_CONFIG = None


class PyQtHotkeyListener:
    """Handles global hotkey detection using pynput with Qt signals."""

    def __init__(self, keymap_manager: KeymapManager | None = None):
        self.keymap_manager = keymap_manager or KeymapManager([])
        self.listener: keyboard.Listener | None = None
        self.pressed_keys: set[Key] = set()
        self.action_states: dict[str, bool] = {}
        self.action_timers: dict[str, threading.Timer | None] = {}
        self.signals = HotkeySignals()
        self.running = False

        # Initialize action states and timers for available actions
        available_actions = {
            "open_context_menu",
            "execute_active_prompt",
            "speech_to_text_toggle",
            "set_context_value",
            "append_context_value",
            "clear_context",
        }
        for action in available_actions:
            self.action_states[action] = False
            self.action_timers[action] = None

    def connect_action_callback(self, callback: Callable[[str], None]) -> None:
        """Connect callback for any action trigger."""
        self.signals.action_triggered.connect(callback)

    def start(self) -> None:
        """Start the hotkey listener."""
        if self.running:
            return

        global HOTKEY_CONFIG
        if HOTKEY_CONFIG is None:
            HOTKEY_CONFIG = HotkeyConfig(self.keymap_manager)

        _write_hotkey_debug_log("Starting pynput keyboard listener...")
        _write_hotkey_debug_log(f"  DISPLAY={os.environ.get('DISPLAY', 'NOT SET')}")
        _write_hotkey_debug_log(f"  WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY', 'NOT SET')}")
        _write_hotkey_debug_log(f"  XDG_SESSION_TYPE={os.environ.get('XDG_SESSION_TYPE', 'NOT SET')}")

        try:
            self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release, suppress=False)
            self.listener.start()
            self.running = True
            _write_hotkey_debug_log("Keyboard listener started successfully")
        except Exception as e:
            _write_hotkey_debug_log(f"FAILED to start keyboard listener: {type(e).__name__}: {e}")
            raise HotkeyError(f"Failed to start hotkey listener: {e}") from e

    def stop(self) -> None:
        """Stop the hotkey listener."""
        self.running = False

        # Cancel all action timers
        for action, timer in self.action_timers.items():
            if timer:
                timer.cancel()
                self.action_timers[action] = None

        if self.listener:
            self.listener.stop()
            self.listener = None

        self.pressed_keys.clear()

        # Reset action states
        for action in self.action_states:
            self.action_states[action] = False

    def _on_press(self, key: Key) -> None:
        """Handle key press events."""
        self.pressed_keys.add(key)

        # Check all configured hotkeys from keymap
        all_bindings = self.keymap_manager.get_all_bindings()
        for binding in all_bindings:
            if self._is_action_hotkey_pressed(binding.action, binding.key_combination):
                self._trigger_action_hotkey(binding.action)
                break  # Only trigger first matching action

    def _on_release(self, key: Key) -> None:
        """Handle key release events."""
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)

    def _is_action_hotkey_pressed(self, action_name: str, hotkey_combination: str) -> bool:
        """Check if a specific action's hotkey combination is pressed."""
        if not hotkey_combination:
            return False

        parsed = HOTKEY_CONFIG._parse_hotkey(hotkey_combination)
        modifier_pressed = all(
            any(mod in self.pressed_keys for mod in group)
            for group in parsed["modifier_groups"]
        )
        key_pressed = parsed["key"] in self.pressed_keys
        return modifier_pressed and key_pressed

    def _trigger_action_hotkey(self, action_name: str) -> None:
        """Trigger action hotkey signal if not already triggered."""
        if not self.action_states.get(action_name, False):
            self.action_states[action_name] = True
            self.signals.action_triggered.emit(action_name)

            # Execute the action through keymap manager
            from modules.utils.keymap_actions import execute_keymap_action

            execute_keymap_action(action_name)

            # Set reset timer
            self.action_timers[action_name] = threading.Timer(1.0, lambda: self._reset_action_flag(action_name))
            self.action_timers[action_name].start()

    def _reset_action_flag(self, action_name: str) -> None:
        """Reset action flag to prevent rapid firing."""
        self.action_states[action_name] = False
        self.action_timers[action_name] = None


class PyQtHotkeyManager:
    """Manages global hotkey detection and configuration using PyQt5."""

    def __init__(
        self,
        settings_path: Path | None = None,
        keymap_manager: KeymapManager | None = None,
    ):
        if keymap_manager:
            self.keymap_manager = keymap_manager
        elif settings_path:
            config_service = ConfigService()
            if config_service._config is None:
                config_service.initialize(settings_file=str(settings_path))
            config = config_service.get_config()
            self.keymap_manager = config.keymap_manager
        else:
            self.keymap_manager = KeymapManager([])

        # Find execute prompt hotkey from keymap
        execute_hotkey = None
        for binding in self.keymap_manager.get_all_bindings():
            if binding.action == "execute_active_prompt":
                execute_hotkey = binding.key_combination
                break
        self.hotkey = execute_hotkey or "cmd+f2"
        self.listener = PyQtHotkeyListener(self.keymap_manager)
        self.running = False

    def connect_action_callback(self, callback: Callable[[str], None]) -> None:
        """Connect callback for any action activation."""
        self.listener.connect_action_callback(callback)

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
        return key in valid_keys

    def get_keymap_manager(self) -> KeymapManager:
        """Get the keymap manager."""
        return self.keymap_manager

    def get_hotkey_for_action(self, action_name: str) -> str | None:
        """Get hotkey combination for a specific action."""
        for binding in self.keymap_manager.get_all_bindings():
            if binding.action == action_name:
                return binding.key_combination
        return None

    def get_all_hotkeys(self) -> dict[str, list[str]]:
        """Get all configured hotkeys."""
        result = {}
        for binding in self.keymap_manager.get_all_bindings():
            if binding.action not in result:
                result[binding.action] = []
            result[binding.action].append(binding.key_combination)
        return result

    def reload_config(self, settings_path: Path | None = None) -> None:
        """Reload keymap configuration from settings."""
        was_running = self.running
        if was_running:
            self.stop()

        if settings_path:
            config_service = ConfigService()
            if config_service._config is None:
                config_service.initialize(settings_file=str(settings_path))
            config = config_service.get_config()
            self.keymap_manager = config.keymap_manager

        # Update execute hotkey
        execute_hotkey = None
        for binding in self.keymap_manager.get_all_bindings():
            if binding.action == "execute_active_prompt":
                execute_hotkey = binding.key_combination
                break
        self.hotkey = execute_hotkey or "cmd+f2"
        self.listener.keymap_manager = self.keymap_manager

        if was_running:
            self.start()
