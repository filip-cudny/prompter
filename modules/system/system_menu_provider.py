"""Menu item provider for system functionality."""

from collections.abc import Callable

from core.models import MenuItem


class SystemMenuProvider:
    """Provides system menu items (refresh, etc.)."""

    def __init__(
        self,
        execute_callback: Callable[[MenuItem], None] | None = None,
        prompt_store_service=None,
    ):
        self.execute_callback = execute_callback
        self.prompt_store_service = prompt_store_service

    def get_menu_items(self) -> list[MenuItem]:
        """Return system menu items."""
        items: list[MenuItem] = []

        # Add other system menu items here as needed
        # For now, this is a placeholder for future system functionality

        return items

    def refresh(self) -> None:
        """Refresh the provider's data."""
