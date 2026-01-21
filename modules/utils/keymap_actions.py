"""Keymap actions module - defines and handles available Promptheus actions."""

import logging
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

from modules.utils.notification_config import is_notification_enabled

if TYPE_CHECKING:
    from core.context_manager import ContextManager
    from core.interfaces import ClipboardManager
    from modules.utils.notifications import PyQtNotificationManager

logger = logging.getLogger(__name__)


class KeymapAction(ABC):
    """Base class for keymap actions."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Action name identifier."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the action."""
        pass

    @abstractmethod
    def execute(self, context: dict[str, Any] | None = None) -> bool:
        """Execute the action. Returns True if successful, False otherwise."""
        pass


class OpenContextMenuAction(KeymapAction):
    """Action to open the context menu."""

    @property
    def name(self) -> str:
        return "open_context_menu"

    @property
    def description(self) -> str:
        return "Open the context menu with available prompts"

    def execute(self, context: dict[str, Any] | None = None) -> bool:
        """Execute context menu opening."""
        try:
            logger.info("Opening context menu via keymap action")
            # Add timestamp for debugging
            context = context or {}
            context["timestamp"] = time.time()
            context["action_type"] = "context_menu"
            return True
        except Exception as e:
            logger.error(f"Failed to open context menu: {e}")
            return False


class SpeechToTextToggleAction(KeymapAction):
    """Action to toggle speech-to-text functionality."""

    @property
    def name(self) -> str:
        return "speech_to_text_toggle"

    @property
    def description(self) -> str:
        return "Toggle speech-to-text input mode"

    def execute(self, context: dict[str, Any] | None = None) -> bool:
        """Execute speech-to-text toggle."""
        try:
            logger.info("Toggling speech-to-text via keymap action")
            # Add timestamp for debugging
            context = context or {}
            context["timestamp"] = time.time()
            context["action_type"] = "speech_toggle"
            return True
        except Exception as e:
            logger.error(f"Failed to toggle speech-to-text: {e}")
            return False


class ExecuteActivePromptAction(KeymapAction):
    """Action to execute the currently active prompt."""

    @property
    def name(self) -> str:
        return "execute_active_prompt"

    @property
    def description(self) -> str:
        return "Execute the currently selected/active prompt"

    def execute(self, context: dict[str, Any] | None = None) -> bool:
        """Execute the active prompt."""
        try:
            logger.info("Executing active prompt via keymap action")
            # Add timestamp for debugging
            context = context or {}
            context["timestamp"] = time.time()
            context["action_type"] = "execute_prompt"
            return True
        except Exception as e:
            logger.error(f"Failed to execute active prompt: {e}")
            return False


class SetContextValueAction(KeymapAction):
    """Action to set context value from clipboard (supports both text and images)."""

    def __init__(
        self,
        context_manager: "ContextManager",
        clipboard_manager: "ClipboardManager",
        notification_manager: Optional["PyQtNotificationManager"] = None,
    ):
        self.context_manager = context_manager
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager

    @property
    def name(self) -> str:
        return "set_context_value"

    @property
    def description(self) -> str:
        return "Set context value from clipboard content (text or image)"

    def execute(self, context: dict[str, Any] | None = None) -> bool:
        """Set context value from clipboard (handles both text and images)."""
        try:
            if self.clipboard_manager.has_image():
                image_data = self.clipboard_manager.get_image_data()
                if image_data:
                    base64_data, media_type = image_data
                    self.context_manager.set_context_image(base64_data, media_type)
                    logger.info("Context image set from clipboard")

                    if self.notification_manager and is_notification_enabled("context_set"):
                        self.notification_manager.show_success_notification(
                            "Context image set"
                        )

                    return True
                else:
                    logger.warning("Failed to get image data from clipboard")
                    return False
            else:
                clipboard_content = self.clipboard_manager.get_content()
                self.context_manager.set_context(clipboard_content)
                logger.info("Context value set from clipboard")

                if self.notification_manager and is_notification_enabled("context_set"):
                    self.notification_manager.show_success_notification("Context set")

                return True
        except Exception as e:
            logger.error(f"Failed to set context value: {e}")
            return False


class AppendContextValueAction(KeymapAction):
    """Action to append context value from clipboard (supports both text and images)."""

    def __init__(
        self,
        context_manager: "ContextManager",
        clipboard_manager: "ClipboardManager",
        notification_manager: Optional["PyQtNotificationManager"] = None,
    ):
        self.context_manager = context_manager
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager

    @property
    def name(self) -> str:
        return "append_context_value"

    @property
    def description(self) -> str:
        return "Append clipboard content to context value (text or image)"

    def execute(self, context: dict[str, Any] | None = None) -> bool:
        """Append clipboard content to context value (handles both text and images)."""
        try:
            if self.clipboard_manager.has_image():
                image_data = self.clipboard_manager.get_image_data()
                if image_data:
                    base64_data, media_type = image_data
                    self.context_manager.append_context_image(base64_data, media_type)
                    logger.info("Context image appended from clipboard")

                    if self.notification_manager and is_notification_enabled("context_append"):
                        self.notification_manager.show_success_notification(
                            "Context image appended"
                        )

                    return True
                else:
                    logger.warning("Failed to get image data from clipboard")
                    return False
            else:
                clipboard_content = self.clipboard_manager.get_content()
                self.context_manager.append_context(clipboard_content)
                logger.info("Context value appended from clipboard")

                if self.notification_manager and is_notification_enabled("context_append"):
                    self.notification_manager.show_success_notification(
                        "Context appended"
                    )

                return True
        except Exception as e:
            logger.error(f"Failed to append context value: {e}")
            return False


class ClearContextAction(KeymapAction):
    """Action to clear context value."""

    def __init__(
        self,
        context_manager: "ContextManager",
        notification_manager: Optional["PyQtNotificationManager"] = None,
    ):
        self.context_manager = context_manager
        self.notification_manager = notification_manager

    @property
    def name(self) -> str:
        return "clear_context"

    @property
    def description(self) -> str:
        return "Clear the stored context value"

    def execute(self, context: dict[str, Any] | None = None) -> bool:
        """Clear the context value."""
        try:
            self.context_manager.clear_context()
            logger.info("Context value cleared")

            if self.notification_manager and is_notification_enabled("context_cleared"):
                self.notification_manager.show_success_notification("Context cleared")

            return True
        except Exception as e:
            logger.error(f"Failed to clear context value: {e}")
            return False


class ActionRegistry:
    """Registry for managing available keymap actions."""

    def __init__(
        self,
        context_manager: Optional["ContextManager"] = None,
        clipboard_manager: Optional["ClipboardManager"] = None,
        notification_manager: Optional["PyQtNotificationManager"] = None,
    ):
        """Initialize the action registry with default actions."""
        self._actions: dict[str, KeymapAction] = {}
        self.context_manager = context_manager
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager
        self._register_default_actions()

    def _register_default_actions(self):
        """Register the default actions."""
        default_actions = [
            OpenContextMenuAction(),
            SpeechToTextToggleAction(),
            ExecuteActivePromptAction(),
        ]

        # Add context management actions if managers are available
        if self.context_manager and self.clipboard_manager:
            default_actions.extend(
                [
                    SetContextValueAction(
                        self.context_manager,
                        self.clipboard_manager,
                        self.notification_manager,
                    ),
                    AppendContextValueAction(
                        self.context_manager,
                        self.clipboard_manager,
                        self.notification_manager,
                    ),
                    ClearContextAction(self.context_manager, self.notification_manager),
                ]
            )

        for action in default_actions:
            self.register_action(action)

    def register_action(self, action: KeymapAction) -> None:
        """Register a new action."""
        if not isinstance(action, KeymapAction):
            raise ValueError("Action must be an instance of KeymapAction")

        self._actions[action.name] = action
        logger.debug(f"Registered action: {action.name}")

    def unregister_action(self, action_name: str) -> bool:
        """Unregister an action by name."""
        if action_name in self._actions:
            del self._actions[action_name]
            logger.debug(f"Unregistered action: {action_name}")
            return True
        return False

    def get_action(self, action_name: str) -> KeymapAction | None:
        """Get an action by name."""
        return self._actions.get(action_name)

    def get_all_actions(self) -> dict[str, KeymapAction]:
        """Get all registered actions."""
        return self._actions.copy()

    def get_available_action_names(self) -> set:
        """Get set of all available action names."""
        return set(self._actions.keys())

    def execute_action(
        self, action_name: str, context: dict[str, Any] | None = None
    ) -> bool:
        """Execute an action by name."""
        action = self.get_action(action_name)
        if action is None:
            logger.warning(f"Action not found: {action_name}")
            return False

        logger.debug(f"Executing action: {action_name}")
        start_time = time.time()

        # Add execution metadata to context
        context = context or {}
        context["action_name"] = action_name
        context["execution_start"] = start_time

        result = action.execute(context)

        execution_time = time.time() - start_time
        logger.debug(
            f"Action '{action_name}' executed in {execution_time:.4f}s, result: {result}"
        )

        return result

    def is_valid_action(self, action_name: str) -> bool:
        """Check if an action name is valid/registered."""
        return action_name in self._actions


_global_action_registry: ActionRegistry | None = None


def get_global_action_registry() -> ActionRegistry:
    """Get the global action registry instance."""
    global _global_action_registry
    if _global_action_registry is None:
        _global_action_registry = ActionRegistry()
    return _global_action_registry


def initialize_global_action_registry(
    context_manager: Optional["ContextManager"] = None,
    clipboard_manager: Optional["ClipboardManager"] = None,
    notification_manager: Optional["PyQtNotificationManager"] = None,
) -> ActionRegistry:
    """Initialize the global action registry with managers."""
    global _global_action_registry
    _global_action_registry = ActionRegistry(
        context_manager, clipboard_manager, notification_manager
    )
    return _global_action_registry


def execute_keymap_action(
    action_name: str, context: dict[str, Any] | None = None
) -> bool:
    """Execute a keymap action using the global registry."""
    registry = get_global_action_registry()
    return registry.execute_action(action_name, context)


def get_available_actions() -> dict[str, str]:
    """Get available actions with their descriptions."""
    registry = get_global_action_registry()
    return {
        name: action.description for name, action in registry.get_all_actions().items()
    }
