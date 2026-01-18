import logging
from typing import List, Optional
from core.exceptions import DataError
from core.services import ExecutionService
from modules.utils.speech_to_text import SpeechToTextService
from core.interfaces import PromptStoreServiceProtocol
from modules.history.history_service import HistoryService
from modules.utils.notifications import PyQtNotificationManager
from modules.utils.notification_config import is_notification_enabled
from core.openai_service import OpenAiService
from core.models import (
    ErrorCode,
    ExecutionResult,
    HistoryEntryType,
    MenuItem,
    MenuItemType,
    PromptData,
)

logger = logging.getLogger(__name__)


class PromptStoreService(PromptStoreServiceProtocol):
    """Main business logic coordinator for the Prompter."""

    def __init__(
        self,
        prompt_providers,
        clipboard_manager,
        notification_manager=None,
        speech_service: Optional[SpeechToTextService] = None,
        openai_service: Optional[OpenAiService] = None,
        context_manager=None,
        history_service: Optional[HistoryService] = None,
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
        self.openai_service = openai_service
        self.context_manager = context_manager
        self.execution_service = ExecutionService(self)
        self.execution_service.set_speech_service(self.speech_service)
        self._menu_coordinator = None
        self.history_service = history_service or HistoryService()
        self.active_prompt_service = ActivePromptService()
        self._prompts_cache = None

    def get_prompts(self) -> List[PromptData]:
        """Get prompts with caching."""

        if self._prompts_cache is None:
            return self._refresh_prompts()

        return self._prompts_cache

    def _refresh_prompts(self) -> List[PromptData]:
        """Refresh prompts cache."""
        try:
            all_prompts = []
            for provider in self.prompt_providers:
                if provider and hasattr(provider, "get_prompts"):
                    try:
                        provider_prompts = provider.get_prompts()
                        all_prompts.extend(provider_prompts)
                    except Exception as e:
                        print(
                            f"Warning: Failed to get prompts from provider {type(provider).__name__}: {e}"
                        )

            self._prompts_cache = all_prompts
            return self._prompts_cache
        except Exception as e:
            raise DataError(f"Failed to refresh prompts: {str(e)}") from e

    def invalidate_cache(self):
        """Invalidate prompt cache and refresh from providers."""
        self._prompts_cache = None
        for provider in self.prompt_providers:
            if hasattr(provider, "refresh"):
                provider.refresh()
        if self._menu_coordinator and hasattr(self._menu_coordinator, "_clear_menu_cache"):
            self._menu_coordinator._clear_menu_cache()

    def execute_item(self, item: MenuItem) -> ExecutionResult:
        """Execute a menu item and track in history."""
        try:
            if item.data and item.data.get("alternative_execution", False):
                # Alternative execution triggers speech-to-text
                # Don't add history here - ExecutionService._on_transcription_complete will handle it
                return self.execution_service.execute_item(item, None, use_speech=True)
            else:
                input_content = self.clipboard_manager.get_content()
                result = self.execution_service.execute_item(item, input_content)
                # Only add history for non-async executions and non-speech actions
                # Async executions will add history when they complete
                # Speech actions should not be added to history (only final prompt results should be)
                should_skip_history = (
                    result.success
                    and result.content == "Execution started asynchronously"
                ) or (
                    result.metadata
                    and result.metadata.get("action")
                    in ["speech_recording_started", "speech_recording_stopped"]
                )
                if not should_skip_history:
                    self.add_history_entry(item, input_content, result)
                return result
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return bool(self.speech_service and self.speech_service.is_recording())

    def get_recording_action_id(self) -> Optional[str]:
        """Get the ID of the action that started recording."""
        return self.execution_service.get_recording_action_id()

    def should_disable_action(self, action_id: str) -> bool:
        """Check if action should be disabled due to recording or execution state."""
        return self.execution_service.should_disable_action(action_id)

    def is_executing(self) -> bool:
        """Check if any handler is executing (LLM request in progress)."""
        return self.execution_service.is_executing()

    def get_disable_reason(self, action_id: str) -> Optional[str]:
        """Get the reason for disabling an action ('recording', 'executing', or None)."""
        return self.execution_service.get_disable_reason(action_id)

    def get_executing_action_id(self) -> Optional[str]:
        """Get the ID of the action that is currently executing."""
        return self.execution_service.get_executing_action_id()

    def cancel_current_execution(self) -> bool:
        """Cancel any running execution. Returns True if execution was cancelled."""
        return self.execution_service.cancel_current_execution()

    def set_menu_coordinator(self, menu_coordinator):
        """Set the menu coordinator for GUI updates."""
        self._menu_coordinator = menu_coordinator

    def emit_execution_completed(self, result: ExecutionResult, execution_id: str = "") -> None:
        """Emit execution completed signal to update GUI."""
        if self._menu_coordinator:
            eid = execution_id or (result.execution_id if result else "") or ""
            self._menu_coordinator.execution_completed.emit(result, eid)

    def emit_execution_started(self, execution_id: str) -> None:
        """Emit execution started signal to notify all listeners."""
        if self._menu_coordinator:
            self._menu_coordinator.execution_started.emit(execution_id)

    def add_history_entry(
        self, item: MenuItem, input_content: str, result: ExecutionResult
    ) -> None:
        """Add entry to history service for prompt executions."""
        if item.item_type in [MenuItemType.PROMPT]:
            is_conversation = bool(item.data and item.data.get("conversation_data"))
            if result.success and item.data:
                self.history_service.add_entry(
                    input_content=input_content,
                    entry_type=HistoryEntryType.TEXT,
                    output_content=result.content,
                    prompt_id=item.data.get("prompt_id"),
                    success=True,
                    is_conversation=is_conversation,
                )
            elif not result.success:
                self.history_service.add_entry(
                    input_content=input_content,
                    entry_type=HistoryEntryType.TEXT,
                    output_content=None,
                    prompt_id=item.data.get("prompt_id") if item.data else None,
                    success=False,
                    error=result.error,
                    is_conversation=is_conversation,
                )

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
            if is_notification_enabled("prompt_execution_success"):
                self.notification_manager.show_success_notification(
                    f"{prompt_name} is active",
                )

    def execute_active_prompt(self) -> ExecutionResult:
        """Execute the active prompt with current clipboard content."""
        active_prompt = self.active_prompt_service.get_active_prompt()
        if not active_prompt:
            return ExecutionResult(
                success=False,
                error="No active prompt selected",
                error_code=ErrorCode.NO_ACTIVE_PROMPT,
            )

        return self.execute_item(active_prompt)

    def get_all_available_prompts(self) -> List[MenuItem]:
        """Get all available prompts as menu items."""
        items = []
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
