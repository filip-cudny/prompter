"""Menu item provider for system functionality."""

from typing import List, Callable, Optional
from core.models import MenuItem


class SystemMenuProvider:
    """Provides system menu items (refresh, etc.)."""

    def __init__(
        self,
        execute_callback: Optional[Callable[[MenuItem], None]] = None,
        prompt_store_service=None,
    ):
        self.execute_callback = execute_callback
        self.prompt_store_service = prompt_store_service

    def get_menu_items(self) -> List[MenuItem]:
        """Return system menu items."""
        items: List[MenuItem] = []

        # Add other system menu items here as needed
        # For now, this is a placeholder for future system functionality

        return items

    def refresh(self) -> None:
        """Refresh the provider's data."""