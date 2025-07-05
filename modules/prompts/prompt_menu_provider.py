"""Menu item providers for the prompt store application."""

from typing import List, Callable, Optional
from core.models import MenuItem, MenuItemType
from core.services import  DataManager


class PromptMenuProvider:
    """Provides menu items for prompts."""

    def __init__(
        self,
        data_manager: DataManager,
        execute_callback: Callable[[MenuItem], None],
        prompt_store_service=None,
    ):
        self.data_manager = data_manager
        self.execute_callback = execute_callback
        self.prompt_store_service = prompt_store_service

    def get_menu_items(self) -> List[MenuItem]:
        """Return menu items for all available prompts."""
        items = []

        try:
            prompts = self.data_manager.get_prompts()

            for prompt in prompts:
                item_id = f"prompt_{prompt.id}"
                enabled = True
                if self.prompt_store_service:
                    enabled = not self.prompt_store_service.should_disable_action(
                        item_id
                    )

                item = MenuItem(
                    id=item_id,
                    label=prompt.name,
                    item_type=MenuItemType.PROMPT,
                    action=lambda: None,
                    data={
                        "prompt_id": prompt.id,
                        "prompt_name": prompt.name,
                        "type": "prompt",
                        "source": prompt.source,
                        "model": prompt.model,
                    },
                    enabled=enabled,
                )
                item.action = lambda item=item: self.execute_callback(item)
                items.append(item)

        except Exception:
            # If loading fails, return empty list
            pass
        return items

    def refresh(self) -> None:
        """Refresh the provider's data."""
        self.data_manager.refresh()

