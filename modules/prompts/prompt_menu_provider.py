"""Menu item providers for the Prompter application."""

from typing import List, Callable
from core.models import MenuItem, MenuItemType
from modules.prompts.prompt_service import PromptStoreService


class PromptMenuProvider:
    """Provides menu items for prompts."""

    def __init__(
        self,
        prompt_store: PromptStoreService,
        execute_callback: Callable[[MenuItem], None],
        prompt_store_service=None,
    ):
        self.prompt_store = prompt_store
        self.execute_callback = execute_callback
        self.prompt_store_service = prompt_store_service

    def get_menu_items(self) -> List[MenuItem]:
        """Return menu items for all available prompts."""
        items = []

        try:
            prompts = self.prompt_store.get_prompts()
            
            model_configs = {}
            if self.prompt_store.primary_provider and hasattr(self.prompt_store.primary_provider, 'get_model_configs'):
                try:
                    model_configs = self.prompt_store.primary_provider.get_model_configs()
                except Exception:
                    pass

            for prompt in prompts:
                item_id = f"prompt_{prompt.id}"
                enabled = True
                if self.prompt_store_service:
                    enabled = not self.prompt_store_service.should_disable_action(
                        item_id
                    )

                model_display_name = prompt.model
                if prompt.model and model_configs.get(prompt.model):
                    model_display_name = model_configs[prompt.model].get('display_name', prompt.model)
                
                item = MenuItem(
                    id=item_id,
                    label=f"{prompt.name}{f' <i style="color: rgba(128, 128, 128, 0.5)">({model_display_name})</i>' if prompt.model else ''}",
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
