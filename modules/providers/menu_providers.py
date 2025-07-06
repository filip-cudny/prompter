"""Menu item providers for the prompt store application."""

from typing import List, Callable, Optional
from core.models import MenuItem, MenuItemType, HistoryEntryType


class SystemMenuProvider:
    """Provides system menu items (refresh, etc.)."""

    def __init__(
        self,
        refresh_callback: Callable[[], None],
        speech_callback: Optional[Callable[[], None]] = None,
        history_service=None,
        execute_callback: Optional[Callable[[MenuItem], None]] = None,
        settings_service=None,
        prompt_store_service=None,
    ):
        self.refresh_callback = refresh_callback
        self.speech_callback = speech_callback
        self.history_service = history_service
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
        if self.history_service:
            last_entry = self.history_service.get_last_item_by_type(
                HistoryEntryType.SPEECH
            )
            if last_entry:
                last_transcription = last_entry.output_content

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

        return items

    def refresh(self) -> None:
        """Refresh the provider's data."""
        if self.settings_service:
            self.settings_service.reload_settings()
