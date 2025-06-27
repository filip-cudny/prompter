"""Menu item providers for the prompt store application."""

from typing import List, Callable, Optional
from core.models import MenuItem, MenuItemType, PromptData, PresetData
from core.services import HistoryService, DataManager


class PromptMenuProvider:
    """Provides menu items for prompts."""

    def __init__(
        self, data_manager: DataManager, execute_callback: Callable[[MenuItem], None]
    ):
        self.data_manager = data_manager
        self.execute_callback = execute_callback

    def get_menu_items(self) -> List[MenuItem]:
        """Return menu items for all available prompts."""
        items = []

        try:
            prompts = self.data_manager.get_prompts()

            for prompt in prompts:
                item = MenuItem(
                    id=f"prompt_{prompt.id}",
                    label=prompt.name,
                    item_type=MenuItemType.PROMPT,
                    action=lambda p=prompt: self.execute_callback(
                        self._create_prompt_item(p)
                    ),
                    data={
                        "prompt_id": prompt.id,
                        "prompt_name": prompt.name,
                        "type": "prompt",
                        "source": prompt.source,
                    },
                    enabled=True,
                )
                items.append(item)

        except Exception:
            # If loading fails, return empty list
            pass
        return items

    def refresh(self) -> None:
        """Refresh the provider's data."""
        self.data_manager.refresh()

    def _create_prompt_item(self, prompt: PromptData) -> MenuItem:
        """Create a menu item for a prompt."""
        return MenuItem(
            id=f"prompt_{prompt.id}",
            label=prompt.name,
            item_type=MenuItemType.PROMPT,
            action=lambda: None,  # Will be handled by execution handler
            data={
                "prompt_id": prompt.id,
                "prompt_name": prompt.name,
                "type": "prompt",
                "source": prompt.source,
            },
            enabled=True,
        )


class PresetMenuProvider:
    """Provides menu items for presets."""

    def __init__(
        self, data_manager: DataManager, execute_callback: Callable[[MenuItem], None]
    ):
        self.data_manager = data_manager
        self.execute_callback = execute_callback

    def get_menu_items(self) -> List[MenuItem]:
        """Return menu items for all available presets."""
        items = []

        try:
            presets = self.data_manager.get_presets()

            for preset in presets:
                prompt_name = self.data_manager.get_prompt_name(preset.prompt_id)
                display_name = f"{preset.preset_name} ({prompt_name})"

                item = MenuItem(
                    id=f"preset_{preset.id}",
                    label=display_name,
                    item_type=MenuItemType.PRESET,
                    action=lambda p=preset: self.execute_callback(
                        self._create_preset_item(p)
                    ),
                    data={
                        "preset_id": preset.id,
                        "preset_name": preset.preset_name,
                        "prompt_id": preset.prompt_id,
                        "type": "preset",
                        "source": preset.source,
                    },
                    enabled=True,
                )
                items.append(item)

        except Exception:
            # If loading fails, return empty list
            pass

        return items

    def refresh(self) -> None:
        """Refresh the provider's data."""
        self.data_manager.refresh()

    def _create_preset_item(self, preset: PresetData) -> MenuItem:
        """Create a menu item for a preset."""
        prompt_name = self.data_manager.get_prompt_name(preset.prompt_id)
        display_name = f"{preset.preset_name} ({prompt_name})"

        return MenuItem(
            id=f"preset_{preset.id}",
            label=display_name,
            item_type=MenuItemType.PRESET,
            action=lambda: None,  # Will be handled by execution handler
            data={
                "preset_id": preset.id,
                "preset_name": preset.preset_name,
                "prompt_id": preset.prompt_id,
                "type": "preset",
                "source": preset.source,
            },
            enabled=True,
        )


class HistoryMenuProvider:
    """Provides menu items for history (last input/output)."""

    def __init__(
        self,
        history_service: HistoryService,
        execute_callback: Callable[[MenuItem], None],
    ):
        self.history_service = history_service
        self.execute_callback = execute_callback

    def get_menu_items(self) -> List[MenuItem]:
        """Return menu items for history operations."""
        items = []

        last_input = self.history_service.get_last_input()
        last_output = self.history_service.get_last_output()

        # Last Input item
        input_label = "⎘ Copy last input"
        if last_input:
            preview = last_input[:30] + "..." if len(last_input) > 30 else last_input
            input_label = f"⎘ Copy last input: {preview}"

        input_item = MenuItem(
            id="history_last_input",
            label=input_label,
            item_type=MenuItemType.HISTORY,
            action=lambda: self.execute_callback(self._create_last_input_item()),
            data={"type": "last_input", "content": last_input},
            enabled=last_input is not None,
            tooltip=last_input,
        )
        items.append(input_item)

        # Last Output item
        output_label = "⎘ Copy last output"
        if last_output:
            preview = last_output[:30] + "..." if len(last_output) > 30 else last_output
            output_label = f"⎘ Copy last output: {preview}"

        output_item = MenuItem(
            id="history_last_output",
            label=output_label,
            item_type=MenuItemType.HISTORY,
            action=lambda: self.execute_callback(self._create_last_output_item()),
            data={"type": "last_output", "content": last_output},
            enabled=last_output is not None,
            separator_after=True,
            tooltip=last_output,
        )
        items.append(output_item)

        return items

    def refresh(self) -> None:
        """Refresh the provider's data."""
        # History doesn't need external refresh

    def _create_last_input_item(self) -> MenuItem:
        """Create a menu item for last input."""
        last_input = self.history_service.get_last_input()
        preview = (
            last_input[:30] + "..."
            if last_input and len(last_input) > 30
            else last_input
        )
        label = f"⎘ Copy last input: {preview}" if last_input else "⎘ Copy last input"

        return MenuItem(
            id="history_last_input",
            label=label,
            item_type=MenuItemType.HISTORY,
            action=lambda: None,  # Will be handled by execution handler
            data={"type": "last_input", "content": last_input},
            enabled=last_input is not None,
            tooltip=last_input,
        )

    def _create_last_output_item(self) -> MenuItem:
        """Create a menu item for last output."""
        last_output = self.history_service.get_last_output()
        preview = (
            last_output[:30] + "..."
            if last_output and len(last_output) > 30
            else last_output
        )
        label = (
            f"⎘ Copy last output: {preview}" if last_output else "⎘ Copy last output"
        )

        return MenuItem(
            id="history_last_output",
            label=label,
            item_type=MenuItemType.HISTORY,
            action=lambda: None,  # Will be handled by execution handler
            data={"type": "last_output", "content": last_output},
            enabled=last_output is not None,
            tooltip=last_output,
        )


class SystemMenuProvider:
    """Provides system menu items (refresh, etc.)."""

    def __init__(
        self,
        refresh_callback: Callable[[], None],
        speech_callback: Optional[Callable[[], None]] = None,
        speech_history_service=None,
        execute_callback: Optional[Callable[[MenuItem], None]] = None,
        settings_service=None,
    ):
        self.refresh_callback = refresh_callback
        self.speech_callback = speech_callback
        self.speech_history_service = speech_history_service
        self.execute_callback = execute_callback
        self.settings_service = settings_service

    def get_menu_items(self) -> List[MenuItem]:
        """Return system menu items."""
        items = []

        # Add system prompts from settings
        if self.settings_service:
            system_prompts = self._get_system_prompts()
            items.extend(system_prompts)
            if system_prompts:
                items[-1].separator_after = True

        # Speech to text item
        if self.speech_callback:
            speech_item = MenuItem(
                id="system_speech_to_text",
                label="Speech to Text",
                item_type=MenuItemType.SPEECH,
                action=self.speech_callback,
                data={"type": "speech_to_text"},
                enabled=True,
            )
            items.append(speech_item)

        # Last Speech Output item - always show, matching input/output button pattern
        last_transcription = None
        if self.speech_history_service:
            last_transcription = self.speech_history_service.get_last_transcription()

        speech_output_label = "⎘ Copy last speech output"
        if last_transcription:
            preview = (
                last_transcription[:30] + "..."
                if len(last_transcription) > 30
                else last_transcription
            )
            speech_output_label = f"⎘ Copy last speech output: {preview}"

        speech_output_item = MenuItem(
            id="speech_last_output",
            label=speech_output_label,
            item_type=MenuItemType.SPEECH,
            action=lambda: self.execute_callback(self._create_last_speech_item()),
            data={"type": "last_speech_output", "content": last_transcription},
            enabled=last_transcription is not None,
            separator_after=True,
            tooltip=last_transcription,
        )
        items.append(speech_output_item)

        # refresh_item = MenuItem(
        #     id="system_refresh",
        #     label="Refresh",
        #     item_type=MenuItemType.SYSTEM,
        #     action=self.refresh_callback,
        #     data={"type": "refresh"},
        #     enabled=True,
        # )
        # items.append(refresh_item)

        return items

    def refresh(self) -> None:
        """Refresh the provider's data."""
        if self.settings_service:
            self.settings_service.reload_settings()

    def _get_system_prompts(self) -> List[MenuItem]:
        """Get system prompts from settings that should use OpenAI."""
        items = []
        try:
            settings = self.settings_service.get_settings()
            for prompt_config in settings.prompts:
                item = MenuItem(
                    id=f"system_prompt_{prompt_config.id}",
                    label=prompt_config.name,
                    item_type=MenuItemType.PROMPT,
                    action=lambda p=prompt_config: self.execute_callback(
                        self._create_system_prompt_item(p)
                    )
                    if self.execute_callback
                    else None,
                    data={
                        "prompt_id": prompt_config.id,
                        "prompt_name": prompt_config.name,
                        "use_openai": True,
                    },
                    enabled=True,
                )
                items.append(item)
        except Exception:
            pass
        return items

    def _create_system_prompt_item(self, prompt_config) -> MenuItem:
        """Create a menu item for a system prompt."""
        return MenuItem(
            id=f"system_prompt_{prompt_config.id}",
            label=prompt_config.name,
            item_type=MenuItemType.PROMPT,
            action=lambda: None,
            data={
                "prompt_id": prompt_config.id,
                "prompt_name": prompt_config.name,
                "use_openai": True,
            },
            enabled=True,
        )

    def _create_last_speech_item(self) -> MenuItem:
        """Create a menu item for last speech transcription."""
        last_transcription = None
        if self.speech_history_service:
            last_transcription = self.speech_history_service.get_last_transcription()

        preview = (
            last_transcription[:30] + "..."
            if last_transcription and len(last_transcription) > 30
            else last_transcription
        )
        label = (
            f"⎘ Copy last speech output: {preview}"
            if last_transcription
            else "⎘ Copy last speech output"
        )

        return MenuItem(
            id="speech_last_output",
            label=label,
            item_type=MenuItemType.SPEECH,
            action=lambda: None,  # Will be handled by execution handler
            data={"type": "last_speech_output", "content": last_transcription},
            enabled=last_transcription is not None,
            tooltip=last_transcription,
        )
