"""Context manager service for storing and managing context values.

This service supports both text and image content as an ordered list of items:
- Text items: stored as string content, used with {{context}} placeholder
- Image items: stored as base64 data with media type, automatically included in messages
- Mixed context: can have both text and image items in any order

Image handling:
- Images are automatically detected from clipboard when using context actions
- Supports PNG, JPEG, GIF, and BMP formats across platforms
- Images are encoded as base64 and included in OpenAI message format
- Multiple images can be appended to the same context

Context items are stored in insertion order, which is preserved when injected into prompts.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class ContextItemType(Enum):
    """Type of context item."""

    TEXT = "text"
    IMAGE = "image"


@dataclass
class ContextItem:
    """Represents a single context item (text or image)."""

    item_type: ContextItemType
    content: str | None = None  # For text items
    data: str | None = None  # For image items (base64)
    media_type: str | None = None  # For image items (e.g., "image/png")


class ContextManager:
    """Service for managing context values used in placeholders."""

    def __init__(self):
        self._items: list[ContextItem] = []
        self._lock = Lock()
        self._change_callbacks: list[Callable[[], None]] = []

    def set_context(self, value: str) -> None:
        """Set the context value, clearing all existing items."""
        with self._lock:
            self._items = [ContextItem(item_type=ContextItemType.TEXT, content=value)]
            logger.debug("Context value set")
        self._notify_change()

    def append_context(self, value: str) -> None:
        """Append a new text item to context."""
        with self._lock:
            self._items.append(ContextItem(item_type=ContextItemType.TEXT, content=value))
            logger.debug("Context text item appended")
        self._notify_change()

    def get_context(self) -> str | None:
        """Get concatenated text from all text items."""
        with self._lock:
            text_items = [
                item.content for item in self._items if item.item_type == ContextItemType.TEXT and item.content
            ]
            if not text_items:
                return None
            return "\n".join(text_items)

    def clear_context(self) -> None:
        """Clear all context items."""
        with self._lock:
            self._items = []
            logger.debug("Context cleared")
        self._notify_change()

    def has_context(self) -> bool:
        """Check if context has any text items."""
        with self._lock:
            return any(item.item_type == ContextItemType.TEXT for item in self._items)

    def get_context_or_default(self, default: str = "") -> str:
        """Get concatenated text or return default if no text items."""
        with self._lock:
            text_items = [
                item.content for item in self._items if item.item_type == ContextItemType.TEXT and item.content
            ]
            if not text_items:
                return default
            return "\n".join(text_items)

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
        """Notify all registered callbacks about context change.

        Note: This method must be called OUTSIDE of the lock to avoid deadlocks,
        as callbacks may call back into ContextManager methods that need the lock.
        """
        with self._lock:
            callbacks = self._change_callbacks.copy()

        logger.debug(f"Notifying {len(callbacks)} context change callbacks")
        for callback in callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in context change callback: {e}")

    def set_context_images(self, images: list[dict[str, Any]]) -> None:
        """Set context images, clearing all existing items."""
        with self._lock:
            self._items = [
                ContextItem(
                    item_type=ContextItemType.IMAGE,
                    data=img.get("data"),
                    media_type=img.get("media_type", "image/png"),
                )
                for img in images
            ]
            logger.debug("Context images set")
        self._notify_change()

    def set_context_image(self, image_data: str, image_type: str = "image/png") -> None:
        """Set context with a single image, clearing all existing items."""
        with self._lock:
            self._items = [
                ContextItem(
                    item_type=ContextItemType.IMAGE,
                    data=image_data,
                    media_type=image_type,
                )
            ]
            logger.debug("Context image set")
        self._notify_change()

    def append_context_image(self, image_data: str, image_type: str = "image/png") -> None:
        """Append a new image item to context."""
        with self._lock:
            self._items.append(
                ContextItem(
                    item_type=ContextItemType.IMAGE,
                    data=image_data,
                    media_type=image_type,
                )
            )
            logger.debug("Context image item appended")
        self._notify_change()

    def get_context_images(self) -> list[dict[str, Any]]:
        """Get all image items in legacy format for backward compatibility."""
        with self._lock:
            return [
                {"type": "image", "data": item.data, "media_type": item.media_type}
                for item in self._items
                if item.item_type == ContextItemType.IMAGE
            ]

    def has_images(self) -> bool:
        """Check if context has any image items."""
        with self._lock:
            return any(item.item_type == ContextItemType.IMAGE for item in self._items)

    def get_full_context(self) -> dict[str, Any]:
        """Get complete context including text and images (legacy format)."""
        with self._lock:
            text_items = [
                item.content for item in self._items if item.item_type == ContextItemType.TEXT and item.content
            ]
            text = "\n".join(text_items) if text_items else None
            images = [
                {"type": "image", "data": item.data, "media_type": item.media_type}
                for item in self._items
                if item.item_type == ContextItemType.IMAGE
            ]
            return {"text": text, "images": images}

    def has_text_or_images(self) -> bool:
        """Check if context has any items."""
        with self._lock:
            return len(self._items) > 0

    # New item-oriented methods

    def get_items(self) -> list[ContextItem]:
        """Get all context items in order."""
        with self._lock:
            return self._items.copy()

    def remove_item(self, index: int) -> bool:
        """Remove a specific item by index. Returns True if successful."""
        removed = False
        with self._lock:
            if 0 <= index < len(self._items):
                del self._items[index]
                logger.debug(f"Context item at index {index} removed")
                removed = True
        if removed:
            self._notify_change()
        return removed

    def get_item_count(self) -> int:
        """Get total number of context items."""
        with self._lock:
            return len(self._items)

    def get_text_items(self) -> list[ContextItem]:
        """Get only text items in order."""
        with self._lock:
            return [item for item in self._items if item.item_type == ContextItemType.TEXT]

    def get_image_items(self) -> list[ContextItem]:
        """Get only image items in order."""
        with self._lock:
            return [item for item in self._items if item.item_type == ContextItemType.IMAGE]
