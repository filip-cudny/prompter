from typing import List,Optional
from core.services import DataManager, ExecutionService
from utils.speech_to_text import SpeechToTextService
from core.interfaces import PromptStoreServiceProtocol
from modules.history.history_service import HistoryService
from modules.utils.notifications import PyQtNotificationManager
from core.models import (
    ErrorCode,
    ExecutionResult,
    HistoryEntry,
    MenuItem,
    MenuItemType,
    PresetData,
    PromptData,
)


class PromptStoreService(PromptStoreServiceProtocol):
    """Main business logic coordinator for the prompt store."""

    def __init__(
        self,
        prompt_providers,
        clipboard_manager,
        notification_manager=None,
        speech_service=SpeechToTextService,
    ):
        self.prompt_providers = (
            prompt_providers
            if isinstance(prompt_providers, list)
            else [prompt_providers]
        )
        self.primary_provider = (
            self.prompt_providers[0] if self.prompt_providers else None
        )
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager or PyQtNotificationManager()
        self.speech_service = speech_service
        self.execution_service = ExecutionService(self)
        self.execution_service.set_speech_service(self.speech_service)
        self.data_manager = DataManager(self.prompt_providers)
        self.history_service = HistoryService()
        self.active_prompt_service = ActivePromptService()
        self.pending_alternative_execution = None

    def refresh_data(self) -> None:
        """Refresh all data from providers."""
        for provider in self.prompt_providers:
            if hasattr(provider, "refresh"):
                provider.refresh()
        self.data_manager.refresh()

    def get_prompts(self) -> List[PromptData]:
        """Get all available prompts."""
        return self.data_manager.get_prompts()

    def get_presets(self) -> List[PresetData]:
        """Get all available presets."""
        return self.data_manager.get_presets()

    def execute_item(self, item: MenuItem) -> ExecutionResult:
        """Execute a menu item and track in history."""
        try:
            if item.data and item.data.get("alternative_execution", False):
                # Alternative execution triggers speech-to-text
                result = self.execution_service.execute_item(
                    item, None, use_speech=True
                )
                return result
            else:
                input_content = self.clipboard_manager.get_content()
                result = self.execution_service.execute_item(item, input_content)
                self.add_history_entry(item, input_content, result)
                return result
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.execution_service.is_recording()

    def get_recording_action_id(self) -> Optional[str]:
        """Get the ID of the action that started recording."""
        return self.execution_service.get_recording_action_id()

    def should_disable_action(self, action_id: str) -> bool:
        """Check if action should be disabled due to recording state."""
        return self.execution_service.should_disable_action(action_id)

    def _handle_transcription_execution(self, item: MenuItem) -> ExecutionResult:
        """Handle execution that should trigger transcription first."""
        try:
            self.pending_alternative_execution = item

            if self.speech_service:
                self.speech_service.start_recording("PromptStoreService")
                return ExecutionResult(
                    success=True, content="Recording started for transcription..."
                )
            else:
                return ExecutionResult(
                    success=False, error="Speech service not available"
                )
        except Exception as e:
            return ExecutionResult(
                success=False, error=f"Failed to start transcription: {str(e)}"
            )

    def _on_transcription_for_execution(
        self, transcription: str, _duration: float
    ) -> None:
        """Handle transcription completion for pending execution."""
        try:
            if self.pending_alternative_execution and transcription:
                # Execute the pending item with transcribed text
                result = self.execution_service.execute_item(
                    self.pending_alternative_execution, transcription
                )
                self.add_history_entry(
                    self.pending_alternative_execution, transcription, result
                )
                self.pending_alternative_execution = None
        except Exception:
            # Handle error but don't raise to avoid breaking other callbacks
            pass

    def add_history_entry(
        self, item: MenuItem, input_content: str, result: ExecutionResult
    ) -> None:
        """Add entry to history service for prompt and preset executions."""
        # Only add to history for prompt and preset executions, not history or system operations
        if item.item_type in [MenuItemType.PROMPT, MenuItemType.PRESET]:
            if result.success and item.data:
                self.history_service.add_entry(
                    input_content=input_content,
                    output_content=result.content,
                    prompt_id=item.data.get("prompt_id"),
                    preset_id=item.data.get("preset_id"),
                    success=True,
                )
            elif not result.success:
                self.history_service.add_entry(
                    input_content=input_content,
                    output_content=None,
                    prompt_id=item.data.get("prompt_id") if item.data else None,
                    preset_id=item.data.get("preset_id") if item.data else None,
                    success=False,
                    error=result.error,
                )

    def get_history(self) -> List[HistoryEntry]:
        """Get execution history."""
        return self.history_service.get_history()

    def get_last_input(self) -> Optional[str]:
        """Get the last input from history."""
        return self.history_service.get_last_input()

    def get_last_output(self) -> Optional[str]:
        """Get the last output from history."""
        return self.history_service.get_last_output()

    def get_active_prompt(self) -> Optional[MenuItem]:
        """Get the active prompt/preset."""
        return self.active_prompt_service.get_active_prompt()

    def set_active_prompt(self, item: MenuItem) -> None:
        """Set the active prompt/preset."""
        self.active_prompt_service.set_active_prompt(item)

        if item.item_type == MenuItemType.PROMPT:
            prompt_name = (
                item.data.get("prompt_name", "Unknown Prompt")
                if item.data
                else "Unknown Prompt"
            )
            self.notification_manager.show_success_notification(
                f"{prompt_name} is active",
            )
        elif item.item_type == MenuItemType.PRESET:
            preset_name = (
                item.data.get("preset_name", "Unknown Preset")
                if item.data
                else "Unknown Preset"
            )
            self.notification_manager.show_success_notification(
                f"{preset_name} is active",
            )

    def execute_active_prompt(self) -> ExecutionResult:
        """Execute the active prompt/preset with current clipboard content."""
        active_prompt = self.active_prompt_service.get_active_prompt()
        if not active_prompt:
            return ExecutionResult(
                success=False,
                error="No active prompt selected",
                error_code=ErrorCode.NO_ACTIVE_PROMPT,
            )

        return self.execute_item(active_prompt)

    def get_all_available_prompts(self) -> List[MenuItem]:
        """Get all available prompts and presets as menu items."""
        items = []

        # Add prompts
        for prompt in self.get_prompts():

            def make_prompt_action(p):
                def action():
                    self.set_active_prompt(
                        MenuItem(
                            id=f"prompt_{p.id}",
                            label=p.name,
                            item_type=MenuItemType.PROMPT,
                            action=lambda: None,
                            data={
                                "prompt_id": p.id,
                                "prompt_name": p.name,
                                "source": p.source,
                                "model": p.model,
                            },
                        )
                    )

                return action

            item = MenuItem(
                id=f"prompt_{prompt.id}",
                label=prompt.name,
                item_type=MenuItemType.PROMPT,
                action=make_prompt_action(prompt),
                data={
                    "prompt_id": prompt.id,
                    "prompt_name": prompt.name,
                    "source": prompt.source,
                    "model": prompt.model,
                },
            )
            items.append(item)

        # Add presets
        for preset in self.get_presets():

            def make_preset_action(p):
                def action():
                    self.set_active_prompt(
                        MenuItem(
                            id=f"preset_{p.id}",
                            label=p.preset_name,
                            item_type=MenuItemType.PRESET,
                            action=lambda: None,
                            data={
                                "preset_id": p.id,
                                "preset_name": p.preset_name,
                                "prompt_id": p.prompt_id,
                                "source": p.source,
                            },
                        )
                    )

                return action

            item = MenuItem(
                id=f"preset_{preset.id}",
                label=preset.preset_name,
                item_type=MenuItemType.PRESET,
                action=make_preset_action(preset),
                data={
                    "preset_id": preset.id,
                    "preset_name": preset.preset_name,
                    "prompt_id": preset.prompt_id,
                    "source": preset.source,
                },
            )
            items.append(item)

        return items

class ActivePromptService:
    """Service for tracking the actively selected prompt or preset."""

    def __init__(self):
        self._active_prompt: Optional[MenuItem] = None

    def set_active_prompt(self, item: MenuItem) -> None:
        """Set the active prompt/preset."""
        if item.item_type in [MenuItemType.PROMPT, MenuItemType.PRESET]:
            self._active_prompt = item

    def get_active_prompt(self) -> Optional[MenuItem]:
        """Get the active prompt/preset."""

        return self._active_prompt

    def get_active_prompt_display_name(self) -> Optional[str]:
        """Get a display name for the active prompt/preset."""
        if not self._active_prompt or not self._active_prompt.data:
            return None

        if self._active_prompt.item_type == MenuItemType.PRESET:
            return self._active_prompt.data.get("preset_name", "Unknown Preset")
        else:
            return self._active_prompt.data.get("prompt_name", "Unknown Prompt")

    def has_active_prompt(self) -> bool:
        """Check if there is an active prompt/preset."""
        return self._active_prompt is not None

    def clear_active_prompt(self) -> None:
        """Clear the active prompt/preset."""
        self._active_prompt = None
