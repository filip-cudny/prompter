"""Keymap actions module - defines and handles available prompter actions."""

from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
import logging
import time

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
    def execute(self, context: Optional[Dict[str, Any]] = None) -> bool:
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

    def execute(self, context: Optional[Dict[str, Any]] = None) -> bool:
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

    def execute(self, context: Optional[Dict[str, Any]] = None) -> bool:
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

    def execute(self, context: Optional[Dict[str, Any]] = None) -> bool:
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


class ActionRegistry:
    """Registry for managing available keymap actions."""

    def __init__(self):
        """Initialize the action registry with default actions."""
        self._actions: Dict[str, KeymapAction] = {}
        self._register_default_actions()

    def _register_default_actions(self):
        """Register the default actions."""
        default_actions = [
            OpenContextMenuAction(),
            SpeechToTextToggleAction(),
            ExecuteActivePromptAction(),
        ]

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

    def get_action(self, action_name: str) -> Optional[KeymapAction]:
        """Get an action by name."""
        return self._actions.get(action_name)

    def get_all_actions(self) -> Dict[str, KeymapAction]:
        """Get all registered actions."""
        return self._actions.copy()

    def get_available_action_names(self) -> set:
        """Get set of all available action names."""
        return set(self._actions.keys())

    def execute_action(
        self, action_name: str, context: Optional[Dict[str, Any]] = None
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


def get_global_action_registry() -> ActionRegistry:
    """Get the global action registry instance."""
    if not hasattr(get_global_action_registry, "_instance"):
        get_global_action_registry._instance = ActionRegistry()
    return get_global_action_registry._instance


def execute_keymap_action(
    action_name: str, context: Optional[Dict[str, Any]] = None
) -> bool:
    """Execute a keymap action using the global registry."""
    registry = get_global_action_registry()
    return registry.execute_action(action_name, context)


def get_available_actions() -> Dict[str, str]:
    """Get available actions with their descriptions."""
    registry = get_global_action_registry()
    return {
        name: action.description for name, action in registry.get_all_actions().items()
    }
