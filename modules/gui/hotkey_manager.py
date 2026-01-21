"""PySide6-based hotkey manager for global hotkey detection."""

import threading
from typing import Set, Optional, Callable, Dict, List
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from pynput import keyboard
from pynput.keyboard import Key
from core.exceptions import HotkeyError
from modules.utils.keymap import KeymapManager
from modules.utils.config import ConfigService


class HotkeySignals(QObject):
    """Qt signals for thread-safe communication between pynput and Qt."""

    action_triggered = Signal(str)  # Generic signal that emits action name

    # Legacy signals for backwards compatibility
    re_execute_hotkey_pressed = Signal()
    context_menu_hotkey_pressed = Signal()
    speech_toggle_hotkey_pressed = Signal()


class HotkeyConfig:
    """Configuration for platform-specific hotkeys from keymap system."""

    def __init__(self, keymap_manager: Optional[KeymapManager] = None):
        self.keymap_manager = keymap_manager or KeymapManager([])

        # Get hotkeys from keymap manager for current OS
        all_bindings = self.keymap_manager.get_all_bindings()

        # Find all hotkeys for each action
        self.context_menu_hotkeys = self._find_hotkeys_for_action(
            all_bindings, "open_context_menu"
        ) or ["cmd+f1"]
        self.re_execute_hotkeys = self._find_hotkeys_for_action(
            all_bindings, "execute_active_prompt"
        ) or ["cmd+f2"]
        self.speech_toggle_hotkeys = self._find_hotkeys_for_action(
            all_bindings, "speech_to_text_toggle"
        ) or ["shift+f1"]

        # Parse hotkeys to extract keys and modifiers
        self.context_menu_parsed = [
            self._parse_hotkey(hotkey) for hotkey in self.context_menu_hotkeys
        ]
        self.re_execute_parsed = [
            self._parse_hotkey(hotkey) for hotkey in self.re_execute_hotkeys
        ]
        self.speech_toggle_parsed = [
            self._parse_hotkey(hotkey) for hotkey in self.speech_toggle_hotkeys
        ]

        # Keep first hotkey for backward compatibility
        self.context_menu_hotkey = self.context_menu_hotkeys[0]
        self.re_execute_hotkey = self.re_execute_hotkeys[0]
        self.speech_toggle_hotkey = self.speech_toggle_hotkeys[0]

    def _find_hotkey_for_action(self, bindings, action_name: str) -> Optional[str]:
        """Find hotkey combination for a specific action."""
        for binding in bindings:
            if binding.action == action_name:
                return binding.key_combination
        return None

    def _find_hotkeys_for_action(self, bindings, action_name: str) -> List[str]:
        """Find all hotkey combinations for a specific action."""
        hotkeys = []
        for binding in bindings:
            if binding.action == action_name:
                hotkeys.append(binding.key_combination)
        return hotkeys

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

        parsed_modifiers = []
        for mod_name in modifier_names:
            if mod_name in modifier_map:
                parsed_modifiers.extend(modifier_map[mod_name])

        parsed_key = key_map.get(key_name)
        if parsed_key is None:
            parsed_key = keyboard.KeyCode.from_char(key_name)

        return {"modifiers": parsed_modifiers, "key": parsed_key}


# Global hotkey config will be initialized when needed
HOTKEY_CONFIG = None


class PyQtHotkeyListener:
    """Handles global hotkey detection using pynput with Qt signals."""

    def __init__(self, keymap_manager: Optional[KeymapManager] = None):
        self.keymap_manager = keymap_manager or KeymapManager([])
        self.listener: Optional[keyboard.Listener] = None
        self.pressed_keys: Set[Key] = set()
        self.action_states: Dict[str, bool] = {}
        self.action_timers: Dict[str, Optional[threading.Timer]] = {}
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

        # Legacy state tracking for backwards compatibility
        self.re_execute_hotkey_pressed = False
        self.context_menu_hotkey_pressed = False
        self.speech_toggle_hotkey_pressed = False
        self.re_execute_reset_timer: Optional[threading.Timer] = None
        self.context_menu_reset_timer: Optional[threading.Timer] = None
        self.speech_toggle_reset_timer: Optional[threading.Timer] = None

    def connect_action_callback(self, callback: Callable[[str], None]) -> None:
        """Connect callback for any action trigger."""
        self.signals.action_triggered.connect(callback)

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

        global HOTKEY_CONFIG
        if HOTKEY_CONFIG is None:
            HOTKEY_CONFIG = HotkeyConfig(self.keymap_manager)

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

        # Cancel all action timers
        for action, timer in self.action_timers.items():
            if timer:
                timer.cancel()
                self.action_timers[action] = None

        # Legacy timer cleanup
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

        # Reset action states
        for action in self.action_states:
            self.action_states[action] = False

        # Legacy state reset
        self.re_execute_hotkey_pressed = False
        self.context_menu_hotkey_pressed = False
        self.speech_toggle_hotkey_pressed = False

    def _on_press(self, key: Key) -> None:
        """Handle key press events."""
        self.pressed_keys.add(key)

        # Check all configured hotkeys from keymap
        all_bindings = self.keymap_manager.get_all_bindings()
        for binding in all_bindings:
            if self._is_action_hotkey_pressed(binding.action, binding.key_combination):
                self._trigger_action_hotkey(binding.action)
                break  # Only trigger first matching action

        # Legacy hotkey checking for backwards compatibility
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

    def _is_action_hotkey_pressed(
        self, action_name: str, hotkey_combination: str
    ) -> bool:
        """Check if a specific action's hotkey combination is pressed."""
        if not hotkey_combination:
            return False

        parsed = HOTKEY_CONFIG._parse_hotkey(hotkey_combination)
        modifier_pressed = any(mod in self.pressed_keys for mod in parsed["modifiers"])
        key_pressed = parsed["key"] in self.pressed_keys
        return modifier_pressed and key_pressed

    def _is_re_execute_hotkey_pressed(self) -> bool:
        """Check if re-execute hotkey combination is pressed."""
        if HOTKEY_CONFIG is None:
            return False
        # Check all configured hotkey combinations for re-execute
        for config in HOTKEY_CONFIG.re_execute_parsed:
            modifier_pressed = any(
                mod in self.pressed_keys for mod in config["modifiers"]
            )
            key_pressed = config["key"] in self.pressed_keys
            if modifier_pressed and key_pressed:
                return True
        return False

    def _is_context_menu_hotkey_pressed(self) -> bool:
        """Check if context menu hotkey combination is pressed."""
        if HOTKEY_CONFIG is None:
            return False
        # Check all configured hotkey combinations for context menu
        for config in HOTKEY_CONFIG.context_menu_parsed:
            modifier_pressed = any(
                mod in self.pressed_keys for mod in config["modifiers"]
            )
            key_pressed = config["key"] in self.pressed_keys
            if modifier_pressed and key_pressed:
                return True
        return False

    def _is_speech_toggle_hotkey_pressed(self) -> bool:
        """Check if speech toggle hotkey combination is pressed."""
        if HOTKEY_CONFIG is None:
            return False
        # Check all configured hotkey combinations for speech toggle
        for config in HOTKEY_CONFIG.speech_toggle_parsed:
            modifier_pressed = any(
                mod in self.pressed_keys for mod in config["modifiers"]
            )
            key_pressed = config["key"] in self.pressed_keys
            if modifier_pressed and key_pressed:
                return True
        return False

    def _trigger_action_hotkey(self, action_name: str) -> None:
        """Trigger action hotkey signal if not already triggered."""
        if not self.action_states.get(action_name, False):
            self.action_states[action_name] = True
            self.signals.action_triggered.emit(action_name)

            # Execute the action through keymap manager
            from modules.utils.keymap_actions import execute_keymap_action

            execute_keymap_action(action_name)

            # Set reset timer
            self.action_timers[action_name] = threading.Timer(
                1.0, lambda: self._reset_action_flag(action_name)
            )
            self.action_timers[action_name].start()

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

    def _reset_action_flag(self, action_name: str) -> None:
        """Reset action flag to prevent rapid firing."""
        self.action_states[action_name] = False
        self.action_timers[action_name] = None

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
        settings_path: Optional[Path] = None,
        keymap_manager: Optional[KeymapManager] = None,
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

    def get_keymap_manager(self) -> KeymapManager:
        """Get the keymap manager."""
        return self.keymap_manager

    def get_hotkey_for_action(self, action_name: str) -> Optional[str]:
        """Get hotkey combination for a specific action."""
        for binding in self.keymap_manager.get_all_bindings():
            if binding.action == action_name:
                return binding.key_combination
        return None

    def get_all_hotkeys(self) -> Dict[str, List[str]]:
        """Get all configured hotkeys."""
        result = {}
        for binding in self.keymap_manager.get_all_bindings():
            if binding.action not in result:
                result[binding.action] = []
            result[binding.action].append(binding.key_combination)
        return result

    def reload_config(self, settings_path: Optional[Path] = None) -> None:
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
        self.listener = PyQtHotkeyListener(self.keymap_manager)

        if was_running:
            self.start()
