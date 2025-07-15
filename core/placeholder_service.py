"""Placeholder service for processing placeholders in messages."""

import logging
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod

from core.interfaces import ClipboardManager

logger = logging.getLogger(__name__)


class PlaceholderProcessor(ABC):
    """Abstract base class for placeholder processors."""

    @abstractmethod
    def get_placeholder_name(self) -> str:
        """Return the placeholder name this processor handles."""

    @abstractmethod
    def process(self, context: Optional[str] = None) -> str:
        """Process and return the replacement value."""


class ClipboardPlaceholderProcessor(PlaceholderProcessor):
    """Processor for clipboard placeholder."""

    def __init__(self, clipboard_manager: ClipboardManager):
        self.clipboard_manager = clipboard_manager

    def get_placeholder_name(self) -> str:
        return "clipboard"

    def process(self, context: Optional[str] = None) -> str:
        """Get clipboard content or use provided context."""
        if context is not None:
            return context

        try:
            return self.clipboard_manager.get_content()
        except Exception as e:
            logger.warning("Failed to get clipboard content: %s", e)
            return ""


class ContextPlaceholderProcessor(PlaceholderProcessor):
    """Processor for context placeholder."""

    def get_placeholder_name(self) -> str:
        return "context"

    def process(self, context: Optional[str] = None) -> str:
        """Return provided context or empty string."""
        return context or ""


class PlaceholderService:
    """Service for processing placeholders in messages."""

    def __init__(self, clipboard_manager: ClipboardManager):
        self.processors: Dict[str, PlaceholderProcessor] = {}
        self._register_default_processors(clipboard_manager)

    def _register_default_processors(self, clipboard_manager: ClipboardManager) -> None:
        """Register default placeholder processors."""
        self.register_processor(ClipboardPlaceholderProcessor(clipboard_manager))
        self.register_processor(ContextPlaceholderProcessor())

    def register_processor(self, processor: PlaceholderProcessor) -> None:
        """Register a placeholder processor."""
        placeholder_name = processor.get_placeholder_name()
        self.processors[placeholder_name] = processor
        logger.debug("Registered placeholder processor: %s", placeholder_name)

    def unregister_processor(self, placeholder_name: str) -> None:
        """Unregister a placeholder processor."""
        if placeholder_name in self.processors:
            del self.processors[placeholder_name]
            logger.debug("Unregistered placeholder processor: %s", placeholder_name)

    def process_messages(
        self,
        messages: List[Dict[str, Any]],
        context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Process placeholders in messages."""
        processed_messages = []

        for message in messages:
            if message and isinstance(message.get("content"), str):
                content = self._process_content(message["content"], context)
                role = message.get("role", "user")
                processed_messages.append({"role": role, "content": content})

        return processed_messages

    def _process_content(self, content: str, context: Optional[str] = None) -> str:
        """Process placeholders in content string."""
        processed_content = content

        for placeholder_name, processor in self.processors.items():
            placeholder_pattern = f"{{{{{placeholder_name}}}}}"
            if placeholder_pattern in processed_content:
                try:
                    replacement_value = processor.process(context)
                    processed_content = processed_content.replace(
                        placeholder_pattern, replacement_value
                    )
                    logger.debug("Processed placeholder: %s", placeholder_name)
                except Exception as e:
                    logger.error("Failed to process placeholder %s: %s", placeholder_name, e)
                    processed_content = processed_content.replace(placeholder_pattern, "")

        return processed_content

    def get_available_placeholders(self) -> List[str]:
        """Get list of available placeholder names."""
        return list(self.processors.keys())

    def has_placeholders(self, content: str) -> bool:
        """Check if content contains any registered placeholders."""
        for placeholder_name in self.processors.keys():
            placeholder_pattern = f"{{{{{placeholder_name}}}}}"
            if placeholder_pattern in content:
                return True
        return False
