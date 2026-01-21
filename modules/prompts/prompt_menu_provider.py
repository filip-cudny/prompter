"""Menu item providers for the Promptheus application."""

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
            if self.prompt_store.primary_provider and hasattr(
                self.prompt_store.primary_provider, "get_model_configs"
            ):
                try:
                    model_configs = (
                        self.prompt_store.primary_provider.get_model_configs()
                    )
                except Exception:
                    pass

            for index, prompt in enumerate(prompts, 1):
                item_id = f"prompt_{prompt.id}"
                enabled = True
                disable_reason = None
                is_recording_action = False

                is_executing_action = False

                if self.prompt_store_service:
                    enabled = not self.prompt_store_service.should_disable_action(
                        item_id
                    )
                    disable_reason = self.prompt_store_service.get_disable_reason(
                        item_id
                    )
                    # Check if this is the currently recording action
                    recording_action_id = self.prompt_store_service.get_recording_action_id()
                    is_recording_action = recording_action_id == item_id
                    # Check if this is the currently executing action
                    executing_action_id = self.prompt_store_service.get_executing_action_id()
                    is_executing_action = executing_action_id == item_id

                model_display_name = prompt.model
                if prompt.model and model_configs.get(prompt.model):
                    model_display_name = model_configs[prompt.model].get(
                        "display_name", prompt.model
                    )

                # Calculate max width needed (assume max 999 prompts)
                max_digits = len(str(len(prompts))) if prompts else 1
                max_digits = max(
                    max_digits, 2
                )  # Minimum 2 digits for better appearance

                # Right-align number with non-breaking spaces
                number_str = str(index)
                padding_needed = max_digits - len(number_str)
                padding = "&nbsp;" * padding_needed
                prefix = f"{padding}{number_str}. "

                numeration = f'<i style="color: rgba(128, 128, 128, 0.5)">{prefix}</i>'
                model_suffix = (
                    f' <i style="color: rgba(128, 128, 128, 0.5)">({model_display_name})</i>'
                    if prompt.model
                    else ""
                )

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
                        "disable_reason": disable_reason,
                        "is_recording_action": is_recording_action,
                        "is_executing_action": is_executing_action,
                    },
                    enabled=enabled,
                    tooltip=prompt.description if prompt.description else None,
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
