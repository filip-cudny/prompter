"""Context menu provider for displaying and managing context items."""

from typing import List, Callable, Optional

from core.models import MenuItem, MenuItemType
from core.context_manager import ContextManager


class ContextMenuProvider:
    """Provides menu items for the context section."""

    def __init__(
        self,
        context_manager: ContextManager,
        execute_callback: Callable[[MenuItem], None],
        prompt_store_service=None,
    ):
        self.context_manager = context_manager
        self.execute_callback = execute_callback
        self.prompt_store_service = prompt_store_service

    def get_menu_items(self) -> List[MenuItem]:
        """Return menu items for the context section."""
        items = []

        # Add the context section widget item
        # This will be rendered as a custom widget in the menu
        context_section_item = MenuItem(
            id="context_section",
            label="Context",
            item_type=MenuItemType.CONTEXT,
            action=lambda: None,
            data={"context_manager": self.context_manager},
            enabled=True,
            separator_after=False,
        )
        items.append(context_section_item)

        # Add "Copy context text" menu item
        context_content = self.context_manager.get_context()

        context_label = "\u2398 Copy context text"
        if context_content:
            preview = (
                context_content[:30] + "..."
                if len(context_content) > 30
                else context_content
            )
            context_label = f"\u2398 Copy context text: {preview}"

        context_enabled = context_content is not None
        if self.prompt_store_service:
            context_enabled = (
                context_enabled
                and not self.prompt_store_service.should_disable_action(
                    "history_copy_context"
                )
            )

        copy_item = MenuItem(
            id="context_copy_text",
            label=context_label,
            item_type=MenuItemType.HISTORY,  # Use HISTORY type for consistent handling
            action=lambda: None,
            data={"type": "copy_context", "content": context_content},
            enabled=context_enabled,
            separator_after=True,
            tooltip=context_content,
        )
        copy_item.action = lambda item=copy_item: self.execute_callback(item)

        # Add alternative action for preview
        if context_content:
            copy_item.alternative_action = self._create_preview_action(
                "Context Content", context_content
            )

        items.append(copy_item)

        return items

    def _create_preview_action(self, title: str, content: str):
        """Create an action that opens a text preview dialog."""

        def show_preview():
            from modules.gui.text_preview_dialog import show_preview_dialog

            show_preview_dialog(title, content)
            return None

        return show_preview

    def refresh(self) -> None:
        """Refresh the provider's data."""
        # Context is managed by ContextManager, nothing to refresh here
        pass
