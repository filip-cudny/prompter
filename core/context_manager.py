"""Context manager service for storing and managing context values."""

import logging
from typing import Optional, Callable, List
from threading import Lock

logger = logging.getLogger(__name__)


class ContextManager:
    """Service for managing context values used in placeholders."""

    def __init__(self):
        self._context_value: Optional[str] = None
        self._lock = Lock()
        self._change_callbacks: List[Callable[[], None]] = []

    def set_context(self, value: str) -> None:
        """Set the context value."""
        with self._lock:
            self._context_value = value
            logger.debug("Context value set")
            self._notify_change()

    def append_context(self, value: str) -> None:
        """Append value to existing context."""
        with self._lock:
            if self._context_value is None:
                self._context_value = value
            else:
                self._context_value += "\n" + value
            logger.debug("Context value appended")
            self._notify_change()

    def get_context(self) -> Optional[str]:
        """Get the current context value."""
        with self._lock:
            return self._context_value

    def clear_context(self) -> None:
        """Clear the context value."""
        with self._lock:
            self._context_value = None
            logger.debug("Context value cleared")
            self._notify_change()

    def has_context(self) -> bool:
        """Check if context has a value."""
        with self._lock:
            return self._context_value is not None

    def get_context_or_default(self, default: str = "") -> str:
        """Get context value or return default if None."""
        with self._lock:
            return self._context_value if self._context_value is not None else default

    def add_change_callback(self, callback: Callable[[], None]) -> None:
        """Add a callback to be called when context changes."""
        with self._lock:
            self._change_callbacks.append(callback)
            logger.debug(f"Added context change callback, total callbacks: {len(self._change_callbacks)}")

    def remove_change_callback(self, callback: Callable[[], None]) -> None:
        """Remove a change callback."""
        with self._lock:
            if callback in self._change_callbacks:
                self._change_callbacks.remove(callback)
                logger.debug(f"Removed context change callback, total callbacks: {len(self._change_callbacks)}")

    def _notify_change(self) -> None:
        """Notify all registered callbacks about context change."""
        logger.debug(f"Notifying {len(self._change_callbacks)} context change callbacks")
        for callback in self._change_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in context change callback: {e}")