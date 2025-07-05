"""Menu item providers for the prompt store application."""

from typing import List, Callable, Optional
from core.models import MenuItem, MenuItemType
from core.services import  DataManager
from modules.history.history_service import  HistoryService


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


class PresetMenuProvider:
    """Provides menu items for presets."""

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
        """Return menu items for all available presets."""
        items = []

        try:
            presets = self.data_manager.get_presets()

            for preset in presets:
                prompt_name = self.data_manager.get_prompt_name(preset.prompt_id)
                display_name = f"{preset.preset_name} ({prompt_name})"
                item_id = f"preset_{preset.id}"
                enabled = True
                if self.prompt_store_service:
                    enabled = not self.prompt_store_service.should_disable_action(
                        item_id
                    )

                item = MenuItem(
                    id=item_id,
                    label=display_name,
                    item_type=MenuItemType.PRESET,
                    action=lambda: None,
                    data={
                        "preset_id": preset.id,
                        "preset_name": preset.preset_name,
                        "prompt_id": preset.prompt_id,
                        "type": "preset",
                        "source": preset.source,
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


class HistoryMenuProvider:
    """Provides menu items for history (last input/output)."""

    def __init__(
        self,
        history_service: HistoryService,
        execute_callback: Callable[[MenuItem], None],
        prompt_store_service=None,
    ):
        self.history_service = history_service
        self.execute_callback = execute_callback
        self.prompt_store_service = prompt_store_service

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
        output_label = "⎘ Copy last output"
        if last_output:
            preview = last_output[:30] + "..." if len(last_output) > 30 else last_output
            output_label = f"⎘ Copy last output: {preview}"

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
            separator_after=True,
            tooltip=last_output,
        )
        output_item.action = lambda item=output_item: self.execute_callback(item)
        items.append(output_item)

        return items

    def refresh(self) -> None:
        """Refresh the provider's data."""
        # History doesn't need external refresh


class SystemMenuProvider:
    """Provides system menu items (refresh, etc.)."""

    def __init__(
        self,
        refresh_callback: Callable[[], None],
        speech_callback: Optional[Callable[[], None]] = None,
        speech_history_service=None,
        execute_callback: Optional[Callable[[MenuItem], None]] = None,
        settings_service=None,
        prompt_store_service=None,
    ):
        self.refresh_callback = refresh_callback
        self.speech_callback = speech_callback
        self.speech_history_service = speech_history_service
        self.execute_callback = execute_callback
        self.settings_service = settings_service
        self.prompt_store_service = prompt_store_service

    def get_menu_items(self) -> List[MenuItem]:
        """Return system menu items."""
        items = []

        # Speech to text item
        if self.speech_callback:
            speech_enabled = True
            speech_label = "Speech to Text"
            if self.prompt_store_service and self.prompt_store_service.is_recording():
                speech_label = "Stop Recording"
            elif self.prompt_store_service:
                speech_enabled = not self.prompt_store_service.should_disable_action(
                    "system_speech_to_text"
                )

            speech_item = MenuItem(
                id="system_speech_to_text",
                label=speech_label,
                item_type=MenuItemType.SPEECH,
                action=self.speech_callback,
                data={"type": "speech_to_text"},
                enabled=speech_enabled,
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

        speech_output_enabled = last_transcription is not None
        if self.prompt_store_service:
            speech_output_enabled = (
                speech_output_enabled
                and not self.prompt_store_service.should_disable_action(
                    "speech_last_output"
                )
            )

        speech_output_item = MenuItem(
            id="speech_last_output",
            label=speech_output_label,
            item_type=MenuItemType.SPEECH,
            action=lambda: None,
            data={"type": "last_speech_output", "content": last_transcription},
            enabled=speech_output_enabled,
            separator_after=True,
            tooltip=last_transcription,
        )
        speech_output_item.action = (
            lambda item=speech_output_item: self.execute_callback(item)
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
