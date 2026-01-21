"""Context menu provider for displaying and managing context items."""

from collections.abc import Callable

from core.context_manager import ContextManager
from core.models import MenuItem, MenuItemType


class ContextMenuProvider:
    """Provides menu items for the context section."""

    def __init__(
        self,
        context_manager: ContextManager,
        execute_callback: Callable[[MenuItem], None],
        prompt_store_service=None,
        notification_manager=None,
        clipboard_manager=None,
    ):
        self.context_manager = context_manager
        self.execute_callback = execute_callback
        self.prompt_store_service = prompt_store_service
        self.notification_manager = notification_manager
        self.clipboard_manager = clipboard_manager

    def get_menu_items(self) -> list[MenuItem]:
        """Return menu items for the context section."""
        items = []

        # Add the context section widget item
        # This will be rendered as a custom widget in the menu
        # Copy functionality is now in the header widget
        context_section_item = MenuItem(
            id="context_section",
            label="Context",
            item_type=MenuItemType.CONTEXT,
            action=lambda: None,
            data={
                "context_manager": self.context_manager,
                "notification_manager": self.notification_manager,
                "clipboard_manager": self.clipboard_manager,
            },
            enabled=True,
            separator_after=True,
        )
        items.append(context_section_item)

        return items

    def refresh(self) -> None:
        """Refresh the provider's data."""
        # Context is managed by ContextManager, nothing to refresh here
        pass
