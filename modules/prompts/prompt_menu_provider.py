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

            for index, prompt in enumerate(prompts, 1):
                item_id = f"prompt_{prompt.id}"
                enabled = True
                if self.prompt_store_service:
                    enabled = not self.prompt_store_service.should_disable_action(
                        item_id
                    )

                model_display_name = prompt.model
                if prompt.model and model_configs.get(prompt.model):
                    model_display_name = model_configs[prompt.model].get('display_name', prompt.model)
                
                numeration = f'<i style="color: rgba(128, 128, 128, 0.5)">{index}.</i> '
                model_suffix = f' <i style="color: rgba(128, 128, 128, 0.5)">({model_display_name})</i>' if prompt.model else ''
                
                item = MenuItem(
                    id=item_id,
                    label=f"{numeration}{prompt.name}{model_suffix}",
                    item_type=MenuItemType.PROMPT,
                    action=lambda: None,
                    data={
                        "prompt_id": prompt.id,
                        "prompt_name": prompt.name,
                        "type": "prompt",
                        "source": prompt.source,
                        "model": prompt.model,
                        "menu_index": index,
                    },
                    enabled=enabled,
                )
                def create_action(menu_item):
                    return lambda: self.execute_callback(menu_item)
                def create_alternative_action(menu_item):
                    # Create alternative item with speech-to-text flag
                    alt_item = MenuItem(
                        id=menu_item.id,
                        label=menu_item.label,
                        item_type=menu_item.item_type,
                        action=menu_item.action,
                        data={**menu_item.data, "alternative_execution": True},
                        enabled=menu_item.enabled,
                    )
                    return lambda: self.execute_callback(alt_item)
                item.action = create_action(item)
                item.alternative_action = create_alternative_action(item)
                items.append(item)

        except Exception:
            # If loading fails, return empty list
            pass
        return items

    def refresh(self) -> None:
        """Refresh the provider's data."""
        pass
