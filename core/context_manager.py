"""Context manager service for storing and managing context values.

This service supports both text and image content:
- Text context: stored as string, used with {{context}} placeholder
- Image context: stored as base64 data with media type, automatically included in messages
- Mixed context: can have both text and multiple images simultaneously

Image handling:
- Images are automatically detected from clipboard when using context actions
- Supports PNG, JPEG, GIF, and BMP formats across platforms
- Images are encoded as base64 and included in OpenAI message format
- Multiple images can be appended to the same context
"""

import logging
from typing import Optional, Callable, List, Dict, Any
from threading import Lock

logger = logging.getLogger(__name__)


class ContextManager:
    """Service for managing context values used in placeholders."""

    def __init__(self):
        self._context_value: Optional[str] = None
        self._context_images: List[Dict[str, Any]] = []
        self._lock = Lock()
        self._change_callbacks: List[Callable[[], None]] = []

    def set_context(self, value: str) -> None:
        """Set the context value."""
        with self._lock:
            self._context_value = value
            self._context_images = []
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
            self._context_images = []
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
            logger.debug(
                f"Added context change callback, total callbacks: {len(self._change_callbacks)}"
            )

    def remove_change_callback(self, callback: Callable[[], None]) -> None:
        """Remove a change callback."""
        with self._lock:
            if callback in self._change_callbacks:
                self._change_callbacks.remove(callback)
                logger.debug(
                    f"Removed context change callback, total callbacks: {len(self._change_callbacks)}"
                )

    def _notify_change(self) -> None:
        """Notify all registered callbacks about context change."""
        logger.debug(
            f"Notifying {len(self._change_callbacks)} context change callbacks"
        )
        for callback in self._change_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in context change callback: {e}")

    def set_context_images(self, images: List[Dict[str, Any]]) -> None:
        """Set context images, clearing existing images."""
        with self._lock:
            self._context_images = images.copy()
            logger.debug("Context images set")
            self._notify_change()

    def set_context_image(self, image_data: str, image_type: str = "image/png") -> None:
        """Set context with a single image, clearing existing images."""
        with self._lock:
            self._context_images = [
                {"type": "image", "data": image_data, "media_type": image_type}
            ]
            logger.debug("Context image set")
            self._notify_change()

    def append_context_image(
        self, image_data: str, image_type: str = "image/png"
    ) -> None:
        """Append an image to existing context."""
        with self._lock:
            self._context_images.append(
                {"type": "image", "data": image_data, "media_type": image_type}
            )
            logger.debug("Context image appended")
            self._notify_change()

    def get_context_images(self) -> List[Dict[str, Any]]:
        """Get the current context images."""
        with self._lock:
            return self._context_images.copy()

    def has_images(self) -> bool:
        """Check if context has images."""
        with self._lock:
            return len(self._context_images) > 0

    def get_full_context(self) -> Dict[str, Any]:
        """Get complete context including text and images."""
        with self._lock:
            return {"text": self._context_value, "images": self._context_images.copy()}

    def has_text_or_images(self) -> bool:
        """Check if context has either text or images."""
        with self._lock:
            return self._context_value is not None or len(self._context_images) > 0
