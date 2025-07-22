from typing import List, Callable
from core.models import MenuItem, MenuItemType, HistoryEntryType
from modules.history.history_service import HistoryService
from core.context_manager import ContextManager


class HistoryMenuProvider:
    """Provides menu items for history (last input/output)."""

    def __init__(
        self,
        history_service: HistoryService,
        execute_callback: Callable[[MenuItem], None],
        prompt_store_service=None,
        context_manager: ContextManager = None,
    ):
        self.history_service = history_service
        self.execute_callback = execute_callback
        self.prompt_store_service = prompt_store_service
        self.context_manager = context_manager

    def get_menu_items(self) -> List[MenuItem]:
        """Return menu items for history operations."""
        items = []

        last_history_text_prompt_item = self.history_service.get_last_item_by_type(
            entry_type=HistoryEntryType.TEXT
        )

        last_input = None
        last_output = None
        if last_history_text_prompt_item is not None:
            last_input = last_history_text_prompt_item.input_content
            last_output = last_history_text_prompt_item.output_content

        input_label = "⎘ Copy input"
        if last_input:
            preview = last_input[:30] + "..." if len(last_input) > 30 else last_input
            input_label = f"⎘ Copy input: {preview}"

        input_enabled = last_input is not None
        if self.prompt_store_service:
            input_enabled = (
                input_enabled
                and not self.prompt_store_service.should_disable_action(
                    "history_last_input"
                )
            )

        input_item = MenuItem(
            id="history_last_input",
            label=input_label,
            item_type=MenuItemType.HISTORY,
            action=lambda: None,
            data={"type": "last_input", "content": last_input},
            enabled=input_enabled,
            tooltip=last_input,
        )
        input_item.action = lambda item=input_item: self.execute_callback(item)
        items.append(input_item)

        # Last Output item
        output_label = "⎘ Copy output"
        if last_output:
            preview = last_output[:30] + "..." if len(last_output) > 30 else last_output
            output_label = f"⎘ Copy output: {preview}"

        output_enabled = last_output is not None
        if self.prompt_store_service:
            output_enabled = (
                output_enabled
                and not self.prompt_store_service.should_disable_action(
                    "history_last_output"
                )
            )

        output_item = MenuItem(
            id="history_last_output",
            label=output_label,
            item_type=MenuItemType.HISTORY,
            action=lambda: None,
            data={"type": "last_output", "content": last_output},
            enabled=output_enabled,
            tooltip=last_output,
        )
        output_item.action = lambda item=output_item: self.execute_callback(item)
        items.append(output_item)

        # Copy Context item
        context_content = None
        if self.context_manager:
            context_content = self.context_manager.get_context()

        context_label = "⎘ Copy context"
        if context_content:
            preview = context_content[:30] + "..." if len(context_content) > 30 else context_content
            context_label = f"⎘ Copy context: {preview}"

        context_enabled = context_content is not None
        if self.prompt_store_service:
            context_enabled = (
                context_enabled
                and not self.prompt_store_service.should_disable_action(
                    "history_copy_context"
                )
            )

        context_item = MenuItem(
            id="history_copy_context",
            label=context_label,
            item_type=MenuItemType.HISTORY,
            action=lambda: None,
            data={"type": "copy_context", "content": context_content},
            enabled=context_enabled,
            separator_after=True,
            tooltip=context_content,
        )
        context_item.action = lambda item=context_item: self.execute_callback(item)
        items.append(context_item)

        return items

    def refresh(self) -> None:
        """Refresh the provider's data."""
        # History doesn't need external refresh
