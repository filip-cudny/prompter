"""Context manager service for storing and managing context values."""

import logging
from typing import Optional
from threading import Lock

logger = logging.getLogger(__name__)


class ContextManager:
    """Service for managing context values used in placeholders."""

    def __init__(self):
        self._context_value: Optional[str] = None
        self._lock = Lock()

    def set_context(self, value: str) -> None:
        """Set the context value."""
        with self._lock:
            self._context_value = value
            logger.debug("Context value set")

    def append_context(self, value: str) -> None:
        """Append value to existing context."""
        with self._lock:
            if self._context_value is None:
                self._context_value = value
            else:
                self._context_value += "\n" + value
            logger.debug("Context value appended")

    def get_context(self) -> Optional[str]:
        """Get the current context value."""
        with self._lock:
            return self._context_value

    def clear_context(self) -> None:
        """Clear the context value."""
        with self._lock:
            self._context_value = None
            logger.debug("Context value cleared")

    def has_context(self) -> bool:
        """Check if context has a value."""
        with self._lock:
            return self._context_value is not None

    def get_context_or_default(self, default: str = "") -> str:
        """Get context value or return default if None."""
        with self._lock:
            return self._context_value if self._context_value is not None else default