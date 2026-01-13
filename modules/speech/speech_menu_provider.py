"""Menu item provider for speech functionality."""

from typing import List, Callable, Optional
from core.models import MenuItem, MenuItemType


class SpeechMenuProvider:
    """Provides speech-related menu items."""

    def __init__(
        self,
        speech_callback: Optional[Callable[[], None]] = None,
        history_service=None,
        execute_callback: Optional[Callable[[MenuItem], None]] = None,
        prompt_store_service=None,
    ):
        self.speech_callback = speech_callback
        self.history_service = history_service
        self.execute_callback = execute_callback
        self.prompt_store_service = prompt_store_service

    def get_menu_items(self) -> List[MenuItem]:
        """Return speech-related menu items."""
        items = []

        # Speech to text item
        if self.speech_callback:
            speech_enabled = True
            speech_label = "Speech to text"
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
                separator_after=True,
                icon="mic",
            )
            items.append(speech_item)

        return items

    def refresh(self) -> None:
        """Refresh the provider's data."""
