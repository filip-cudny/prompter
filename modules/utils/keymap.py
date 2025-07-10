"""Keymap configuration management utilities."""

import platform
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from core.exceptions import ConfigurationError
from .keymap_actions import get_global_action_registry


@dataclass
class KeymapBinding:
    """Individual key binding configuration."""

    key_combination: str
    action: str

    def __post_init__(self):
        """Validate the binding after initialization."""
        if not self.key_combination.strip():
            raise ConfigurationError("Key combination cannot be empty")
        if not self.action.strip():
            raise ConfigurationError("Action cannot be empty")


@dataclass
class KeymapContext:
    """Keymap context with bindings."""

    context: str
    bindings: Dict[str, str]

    def __post_init__(self):
        """Validate the context after initialization."""
        if not self.context.strip():
            raise ConfigurationError("Context cannot be empty")
        if not self.bindings:
            raise ConfigurationError("Bindings cannot be empty")

    def get_bindings(self) -> List[KeymapBinding]:
        """Get list of KeymapBinding objects."""
        return [
            KeymapBinding(key_combination=key, action=action)
            for key, action in self.bindings.items()
        ]

    def matches_current_os(self) -> bool:
        """Check if this context matches the current operating system."""
        current_os = get_current_os()

        if "os ==" not in self.context:
            return True

        if f"os == {current_os}" in self.context:
            return True

        return False


class KeymapManager:
    """Manages keymap configuration and resolution."""

    AVAILABLE_CONTEXTS = {"windows", "linux", "macos"}

    def __init__(self, keymaps: List[Dict[str, Any]]):
        """Initialize keymap manager with keymap data."""
        self.action_registry = get_global_action_registry()
        self.contexts = self._parse_keymaps(keymaps)

    def _parse_keymaps(self, keymaps: List[Dict[str, Any]]) -> List[KeymapContext]:
        """Parse keymap data into KeymapContext objects."""
        contexts = []

        for keymap_data in keymaps:
            context = keymap_data.get("context", "")
            bindings = keymap_data.get("bindings", {})

            keymap_context = KeymapContext(context=context, bindings=bindings)
            self._validate_keymap_context(keymap_context)
            contexts.append(keymap_context)

        return contexts

    def _validate_keymap_context(self, keymap_context: KeymapContext) -> None:
        """Validate a keymap context."""
        available_actions = self.action_registry.get_available_action_names()
        for binding in keymap_context.get_bindings():
            if binding.action not in available_actions:
                raise ConfigurationError(
                    f"Invalid action '{binding.action}'. "
                    f"Available actions: {', '.join(sorted(available_actions))}"
                )

    def get_active_keymaps(self) -> List[KeymapContext]:
        """Get keymaps that match the current operating system."""
        return [context for context in self.contexts if context.matches_current_os()]

    def get_all_bindings(self) -> List[KeymapBinding]:
        """Get all active key bindings for the current OS."""
        bindings = []
        for context in self.get_active_keymaps():
            bindings.extend(context.get_bindings())
        return bindings

    def find_action_for_key(self, key_combination: str) -> Optional[str]:
        """Find the action associated with a key combination."""
        for binding in self.get_all_bindings():
            if binding.key_combination == key_combination:
                return binding.action
        return None

    def get_bindings_for_action(self, action: str) -> List[str]:
        """Get all key combinations bound to a specific action."""
        key_combinations = []
        for binding in self.get_all_bindings():
            if binding.action == action:
                key_combinations.append(binding.key_combination)
        return key_combinations


def get_current_os() -> str:
    """Get the current operating system identifier."""
    system = platform.system().lower()

    if system == "darwin":
        return "macos"
    elif system == "windows":
        return "windows"
    elif system == "linux":
        return "linux"
    else:
        return "linux"


def validate_keymap_data(keymaps: List[Dict[str, Any]]) -> None:
    """Validate keymap data structure."""
    if not isinstance(keymaps, list):
        raise ConfigurationError("Keymaps must be a list")

    for i, keymap in enumerate(keymaps):
        if not isinstance(keymap, dict):
            raise ConfigurationError(f"Keymap at index {i} must be a dictionary")

        if "context" not in keymap:
            raise ConfigurationError(f"Keymap at index {i} missing 'context' field")

        if "bindings" not in keymap:
            raise ConfigurationError(f"Keymap at index {i} missing 'bindings' field")

        if not isinstance(keymap["bindings"], dict):
            raise ConfigurationError(f"Bindings at index {i} must be a dictionary")
