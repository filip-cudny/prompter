"""Placeholder service for processing placeholders in messages."""

import logging
import re
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod

from core.interfaces import ClipboardManager
from core.context_manager import ContextManager
from core.exceptions import ClipboardUnavailableError

logger = logging.getLogger(__name__)


class PlaceholderProcessor(ABC):
    """Abstract base class for placeholder processors."""

    @abstractmethod
    def get_placeholder_name(self) -> str:
        """Return the placeholder name this processor handles."""

    @abstractmethod
    def get_description(self) -> str:
        """Return a description of what this placeholder provides."""

    @abstractmethod
    def process(self, context: Optional[str] = None) -> str:
        """Process and return the replacement value."""


class ClipboardPlaceholderProcessor(PlaceholderProcessor):
    """Processor for clipboard placeholder."""

    def __init__(self, clipboard_manager: ClipboardManager):
        self.clipboard_manager = clipboard_manager

    def get_placeholder_name(self) -> str:
        return "clipboard"

    def get_description(self) -> str:
        return "The current clipboard text content"

    def process(self, context: Optional[str] = None) -> str:
        """Get clipboard content or use provided context."""
        if context is not None:
            return context

        try:
            content = self.clipboard_manager.get_content()
            if not content or not content.strip():
                raise ClipboardUnavailableError("Clipboard is empty")
            return content
        except ClipboardUnavailableError:
            raise
        except Exception as e:
            raise ClipboardUnavailableError(f"Clipboard unavailable: {e}")


class ContextPlaceholderProcessor(PlaceholderProcessor):
    """Processor for context placeholder."""

    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager

    def get_placeholder_name(self) -> str:
        return "context"

    def get_description(self) -> str:
        return "Persistent context data set across prompt executions"

    def process(self, context: Optional[str] = None) -> str:
        """Return stored context value or empty string."""
        return self.context_manager.get_context_or_default("")




class PlaceholderService:
    """Service for processing placeholders in messages."""

    def __init__(
        self, clipboard_manager: ClipboardManager, context_manager: ContextManager
    ):
        self.processors: Dict[str, PlaceholderProcessor] = {}
        self.context_manager = context_manager
        self._register_default_processors(clipboard_manager, context_manager)

    def _register_default_processors(
        self, clipboard_manager: ClipboardManager, context_manager: ContextManager
    ) -> None:
        """Register default placeholder processors."""
        self.register_processor(ClipboardPlaceholderProcessor(clipboard_manager))
        self.register_processor(ContextPlaceholderProcessor(context_manager))

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
        self, messages: List[Dict[str, Any]], context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Process placeholders in messages."""
        processed_messages = []

        for i, message in enumerate(messages):
            if message and isinstance(message.get("content"), str):
                # For the last message (user message), attach images if available
                is_last_message = i == len(messages) - 1
                processed_message = self._process_message_with_context(
                    message, context, is_last_message
                )
                processed_messages.append(processed_message)

        return processed_messages

    def _process_message_with_context(
        self,
        message: Dict[str, Any],
        context: Optional[str] = None,
        is_last_message: bool = False,
    ) -> Dict[str, Any]:
        """Process message with context, handling both text and images."""
        content = message.get("content", "")
        role = message.get("role", "user")

        # Process text placeholders
        processed_content = self._process_content(content, context)

        # For the last message, check if we have images to attach
        if is_last_message and self.context_manager.has_images():
            context_images = self.context_manager.get_context_images()

            # Create message with content array for images
            message_content: List[Dict[str, Any]] = []

            # Add text content first if not empty
            if processed_content.strip():
                message_content.append({"type": "text", "text": processed_content})

            # Add images
            for img in context_images:
                message_content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{img['media_type']};base64,{img['data']}"
                        },
                    }
                )

            return {"role": role, "content": message_content}

        # Standard text-only message
        return {"role": role, "content": processed_content}

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
                except ClipboardUnavailableError:
                    raise
                except Exception as e:
                    logger.error(
                        "Failed to process placeholder %s: %s", placeholder_name, e
                    )
                    processed_content = processed_content.replace(
                        placeholder_pattern, ""
                    )

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

    def get_placeholder_info(self) -> Dict[str, str]:
        """Get dictionary mapping placeholder names to their descriptions."""
        return {
            name: processor.get_description()
            for name, processor in self.processors.items()
        }

    def find_invalid_placeholders(self, content: str) -> List[str]:
        """Find all invalid placeholders in content.

        Returns:
            List of placeholder names that are not registered.
        """
        pattern = r"\{\{(\w+)\}\}"
        found_placeholders = re.findall(pattern, content)
        valid_names = set(self.processors.keys())
        return [name for name in found_placeholders if name not in valid_names]
