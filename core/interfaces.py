"""Abstract interfaces and protocols for the prompt store application."""

from abc import ABC, abstractmethod
from typing import List, Optional, Protocol
from .models import MenuItem, PromptData, PresetData, ExecutionResult, HistoryEntry


class MenuItemProvider(Protocol):
    """Protocol for providing menu items to the context menu."""

    def get_menu_items(self) -> List[MenuItem]:
        """Return a list of menu items to be displayed."""
        ...

    def refresh(self) -> None:
        """Refresh the provider's data if needed."""
        ...


class PromptProvider(Protocol):
    """Protocol for providing prompts from different sources."""

    def get_prompts(self) -> List[PromptData]:
        """Return a list of available prompts."""
        ...

    def get_presets(self) -> List[PresetData]:
        """Return a list of available presets."""
        ...

    def get_prompt_details(self, prompt_id: str) -> Optional[PromptData]:
        """Get detailed information about a specific prompt."""
        ...

    def refresh(self) -> None:
        """Refresh the provider's data."""
        ...


class ExecutionHandler(Protocol):
    """Protocol for handling different types of executions."""

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can execute the given menu item."""
        ...

    def execute(self, item: MenuItem, context: Optional[str] = None) -> ExecutionResult:
        """Execute the menu item and return the result."""
        ...


class ClipboardManager(ABC):
    """Abstract base class for clipboard operations."""

    @abstractmethod
    def get_content(self) -> str:
        """Get the current clipboard content."""
        pass

    @abstractmethod
    def set_content(self, content: str) -> bool:
        """Set the clipboard content. Returns True if successful."""
        pass

    @abstractmethod
    def is_empty(self) -> bool:
        """Check if the clipboard is empty."""
        pass


class PromptStoreServiceProtocol(Protocol):
    """Protocol for the main prompt store service."""

    def refresh_data(self) -> None:
        """Refresh all data from providers."""
        ...

    def get_prompts(self) -> List[PromptData]:
        """Get all available prompts."""
        ...

    def get_presets(self) -> List[PresetData]:
        """Get all available presets."""
        ...

    def execute_item(self, item: MenuItem) -> ExecutionResult:
        """Execute a menu item and track in history."""
        ...

    def is_recording(self) -> bool:
        """Check if currently recording."""
        ...

    def get_recording_action_id(self) -> Optional[str]:
        """Get the ID of the action that started recording."""
        ...

    def should_disable_action(self, action_id: str) -> bool:
        """Check if action should be disabled due to recording state."""
        ...

    def add_history_entry(self, item: MenuItem, input_content: str, result: ExecutionResult) -> None:
        """Add entry to history service for prompt and preset executions."""
        ...

    def get_history(self) -> List[HistoryEntry]:
        """Get execution history."""
        ...

    def get_last_input(self) -> Optional[str]:
        """Get the last input from history."""
        ...

    def get_last_output(self) -> Optional[str]:
        """Get the last output from history."""
        ...

    def get_active_prompt(self) -> Optional[MenuItem]:
        """Get the active prompt/preset."""
        ...

    def set_active_prompt(self, item: MenuItem) -> None:
        """Set the active prompt/preset."""
        ...

    def execute_active_prompt(self) -> ExecutionResult:
        """Execute the active prompt/preset with current clipboard content."""
        ...

    def get_all_available_prompts(self) -> List[MenuItem]:
        """Get all available prompts and presets as menu items."""
        ...
