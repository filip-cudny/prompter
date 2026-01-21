"""UI state persistence for dialog preferences."""

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class UIStateManager:
    """Singleton manager for UI state persistence."""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._state_file = Path("settings/ui_state.json")
            self._state: dict[str, Any] = {}
            self._load_state()
            self._initialized = True

    def _load_state(self) -> None:
        """Load state from file."""
        if self._state_file.exists():
            try:
                with open(self._state_file) as f:
                    self._state = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load UI state: {e}")
                self._state = {}

    def _save_state(self) -> None:
        """Save state to file."""
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_file, "w") as f:
                json.dump(self._state, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save UI state: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a state value by dot-notation key.

        Args:
            key: Dot-notation key (e.g. "context_editor.sections.context.collapsed")
            default: Default value if key not found

        Returns:
            The value at the key path, or default if not found
        """
        keys = key.split(".")
        value = self._state
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a state value by dot-notation key.

        Args:
            key: Dot-notation key (e.g. "context_editor.sections.context.collapsed")
            value: Value to set
        """
        keys = key.split(".")
        current = self._state
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value
        self._save_state()
