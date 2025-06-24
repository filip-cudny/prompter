"""Abstract interfaces and protocols for the prompt store application."""

from abc import ABC, abstractmethod
from typing import List, Optional, Protocol
from .models import MenuItem, PromptData, PresetData, ExecutionResult


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
