"""Settings-based menu providers for the prompt store application."""

from typing import List, Callable, Optional
from core.models import MenuItem, MenuItemType
from .settings_prompt_provider import SettingsPromptProvider


class SettingsPromptMenuProvider:
    """Provides menu items for prompts from settings configuration."""

    def __init__(
        self, 
        settings_prompt_provider: SettingsPromptProvider,
        execute_callback: Callable[[MenuItem], None]
    ):
        self.settings_prompt_provider = settings_prompt_provider
        self.execute_callback = execute_callback

    def get_menu_items(self) -> List[MenuItem]:
        """Return menu items for all available prompts from settings."""
        items = []

        try:
            prompts = self.settings_prompt_provider.get_prompts()

            for prompt in prompts:
                item = MenuItem(
                    id=f"settings_prompt_{prompt.id}",
                    label=f"📝 {prompt.name}",
                    item_type=MenuItemType.PROMPT,
                    action=lambda: None,
                    data={
                        "prompt_id": prompt.id,
                        "prompt_name": prompt.name,
                        "type": "settings_prompt",
                        "source": "settings"
                    },
                    enabled=True,
                    tooltip=f"Settings prompt: {prompt.name}"
                )
                item.action = lambda item=item: self.execute_callback(item)
                items.append(item)

        except Exception as e:
            print(f"Error loading settings prompts: {e}")

        return items

    def refresh(self) -> None:
        """Refresh the provider's data."""
        self.settings_prompt_provider.refresh()




class SettingsPresetMenuProvider:
    """Provides menu items for presets from settings configuration."""

    def __init__(
        self, 
        settings_prompt_provider: SettingsPromptProvider,
        execute_callback: Callable[[MenuItem], None]
    ):
        self.settings_prompt_provider = settings_prompt_provider
        self.execute_callback = execute_callback

    def get_menu_items(self) -> List[MenuItem]:
        """Return menu items for all available presets from settings."""
        items = []

        try:
            presets = self.settings_prompt_provider.get_presets()

            for preset in presets:
                prompt_name = self._get_prompt_name(preset.prompt_id)
                display_name = f"⚙️ {preset.preset_name}"
                if prompt_name:
                    display_name += f" ({prompt_name})"

                item = MenuItem(
                    id=f"settings_preset_{preset.id}",
                    label=display_name,
                    item_type=MenuItemType.PRESET,
                    action=lambda: None,
                    data={
                        "preset_id": preset.id,
                        "preset_name": preset.preset_name,
                        "prompt_id": preset.prompt_id,
                        "type": "settings_preset",
                        "source": "settings"
                    },
                    enabled=True,
                    tooltip=f"Settings preset: {preset.preset_name}"
                )
                item.action = lambda item=item: self.execute_callback(item)
                items.append(item)

        except Exception as e:
            print(f"Error loading settings presets: {e}")

        return items

    def refresh(self) -> None:
        """Refresh the provider's data."""
        self.settings_prompt_provider.refresh()



    def _get_prompt_name(self, prompt_id: str) -> Optional[str]:
        """Get prompt name by ID."""
        try:
            prompt = self.settings_prompt_provider.get_prompt_details(prompt_id)
            return prompt.name if prompt else None
        except Exception:
            return None

