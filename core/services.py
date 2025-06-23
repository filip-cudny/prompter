"""Core business services for the prompt store application."""

from typing import List, Dict, Optional
import time
from collections import deque


from .models import (
    PromptData,
    PresetData,
    ExecutionResult,
    HistoryEntry,
    MenuItem,
    MenuItemType,
    ErrorCode,
)
from .exceptions import DataError
from utils.notifications import NotificationManager


class PromptStoreService:
    """Main business logic coordinator for the prompt store."""

    def __init__(self, prompt_provider, clipboard_manager, notification_manager=None):
        self.prompt_provider = prompt_provider
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager or NotificationManager()
        self.execution_service = ExecutionService(prompt_provider, clipboard_manager)
        self.data_manager = DataManager(prompt_provider)
        self.history_service = HistoryService()
        self.active_prompt_service = ActivePromptService()

    def refresh_data(self) -> None:
        """Refresh all data from providers."""
        self.prompt_provider.refresh()
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
            input_content = self.clipboard_manager.get_content()
            result = self.execution_service.execute_item(item, input_content)

            # Only add to history for prompt and preset executions, not history or system operations
            if item.item_type in [MenuItemType.PROMPT, MenuItemType.PRESET]:
                # Track active prompt/preset
                if result.success and item.data:
                    self.active_prompt_service.update_active_on_execution(item)

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

            return result
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

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
                "Active Prompt Set",
                "Ready to execute with clipboard content",
                prompt_name,
            )
        elif item.item_type == MenuItemType.PRESET:
            preset_name = (
                item.data.get("preset_name", "Unknown Preset")
                if item.data
                else "Unknown Preset"
            )
            self.notification_manager.show_success_notification(
                "Active Preset Set",
                "Ready to execute with clipboard content",
                preset_name,
            )

    def execute_active_prompt(self) -> ExecutionResult:
        """Execute the active prompt/preset with current clipboard content."""
        active_prompt = self.active_prompt_service.get_active_prompt()
        if not active_prompt:
            return ExecutionResult(
                success=False,
                error="No default prompt selected",
                error_code=ErrorCode.NO_ACTIVE_PROMPT,
            )

        return self.execute_item(active_prompt)

    def get_all_available_prompts(self) -> List[MenuItem]:
        """Get all available prompts and presets as menu items."""
        items = []

        # Add prompts
        for prompt in self.get_prompts():
            item = MenuItem(
                id=f"prompt_{prompt.id}",
                label=prompt.name,
                item_type=MenuItemType.PROMPT,
                action=lambda p=prompt: self.set_active_prompt(
                    MenuItem(
                        id=f"prompt_{p.id}",
                        label=p.name,
                        item_type=MenuItemType.PROMPT,
                        action=None,
                        data={"prompt_id": p.id, "prompt_name": p.name},
                    )
                ),
                data={"prompt_id": prompt.id, "prompt_name": prompt.name},
            )
            items.append(item)

        # Add presets
        for preset in self.get_presets():
            item = MenuItem(
                id=f"preset_{preset.id}",
                label=preset.preset_name,
                item_type=MenuItemType.PRESET,
                action=lambda p=preset: self.set_active_prompt(
                    MenuItem(
                        id=f"preset_{p.id}",
                        label=p.preset_name,
                        item_type=MenuItemType.PRESET,
                        action=None,
                        data={
                            "preset_id": p.id,
                            "preset_name": p.preset_name,
                            "prompt_id": p.prompt_id,
                        },
                    )
                ),
                data={
                    "preset_id": preset.id,
                    "preset_name": preset.preset_name,
                    "prompt_id": preset.prompt_id,
                },
            )
            items.append(item)

        return items


class ExecutionService:
    """Service for executing prompts and presets."""

    def __init__(self, prompt_provider, clipboard_manager):
        self.prompt_provider = prompt_provider
        self.clipboard_manager = clipboard_manager
        self.handlers = []

    def register_handler(self, handler) -> None:
        """Register an execution handler."""
        self.handlers.append(handler)

    def execute_item(
        self, item: MenuItem, input_content: Optional[str] = None
    ) -> ExecutionResult:
        """Execute a menu item using the appropriate handler."""
        if not item.enabled:
            return ExecutionResult(success=False, error="Menu item is disabled")

        for handler in self.handlers:
            if handler.can_handle(item):
                try:
                    return handler.execute(item, input_content)
                except Exception as e:
                    return ExecutionResult(success=False, error=str(e))

        return ExecutionResult(
            success=False, error="No handler found for this item type"
        )


class DataManager:
    """Manages prompt and preset data with caching."""

    def __init__(self, prompt_provider):
        self.prompt_provider = prompt_provider
        self._prompts_cache: Optional[List[PromptData]] = None
        self._presets_cache: Optional[List[PresetData]] = None
        self._prompt_id_to_name: Dict[str, str] = {}
        self._last_refresh = 0.0
        self._cache_ttl = 300.0  # 5 minutes

    def get_prompts(self) -> List[PromptData]:
        """Get prompts with caching."""
        if self._should_refresh():
            return self._refresh_prompts()

        if self._prompts_cache is None:
            return self._refresh_prompts()

        return self._prompts_cache

    def get_presets(self) -> List[PresetData]:
        """Get presets with caching."""
        if self._should_refresh():
            return self._refresh_presets()

        if self._presets_cache is None:
            return self._refresh_presets()

        return self._presets_cache

    def get_prompt_name(self, prompt_id: str) -> str:
        """Get prompt name by ID."""
        if not self._prompt_id_to_name or self._should_refresh():
            self.refresh()

        return self._prompt_id_to_name.get(prompt_id, "Unknown Prompt")

    def refresh(self) -> None:
        """Force refresh of all cached data."""
        try:
            self.prompt_provider.refresh()
            self._refresh_prompts()
            self._refresh_presets()
            self._last_refresh = time.time()
        except Exception as e:
            raise DataError(f"Failed to refresh data: {str(e)}") from e

    def _should_refresh(self) -> bool:
        """Check if cache should be refreshed."""
        return time.time() - self._last_refresh > self._cache_ttl

    def _refresh_prompts(self) -> List[PromptData]:
        """Refresh prompts cache."""
        try:
            self._prompts_cache = self.prompt_provider.get_prompts()
            self._update_prompt_id_mapping()
            return self._prompts_cache
        except Exception as e:
            raise DataError(f"Failed to refresh prompts: {str(e)}") from e

    def _refresh_presets(self) -> List[PresetData]:
        """Refresh presets cache."""
        try:
            self._presets_cache = self.prompt_provider.get_presets()
            return self._presets_cache
        except Exception as e:
            raise DataError(f"Failed to refresh presets: {str(e)}") from e

    def _update_prompt_id_mapping(self) -> None:
        """Update the prompt ID to name mapping."""
        if self._prompts_cache:
            self._prompt_id_to_name = {
                prompt.id: prompt.name for prompt in self._prompts_cache
            }


class HistoryService:
    """Service for tracking execution history."""

    def __init__(self, max_entries: int = 10):
        self.max_entries = max_entries
        self._history: deque = deque(maxlen=max_entries)

    def add_entry(
        self,
        input_content: str,
        output_content: Optional[str] = None,
        prompt_id: Optional[str] = None,
        preset_id: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Add a new history entry."""
        entry = HistoryEntry(
            id=str(int(time.time() * 1000)),  # millisecond timestamp as ID
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            input_content=input_content,
            output_content=output_content,
            prompt_id=prompt_id,
            preset_id=preset_id,
            success=success,
            error=error,
        )
        self._history.append(entry)

    def get_history(self) -> List[HistoryEntry]:
        """Get all history entries, most recent first."""
        return list(reversed(self._history))

    def get_last_input(self) -> Optional[str]:
        """Get the last input content."""
        if self._history:
            return self._history[-1].input_content
        return None

    def get_last_output(self) -> Optional[str]:
        """Get the last successful output content."""
        for entry in reversed(self._history):
            if entry.success and entry.output_content:
                return entry.output_content
        return None

    def clear_history(self) -> None:
        """Clear all history entries."""
        self._history.clear()

    def get_entry_by_id(self, entry_id: str) -> Optional[HistoryEntry]:
        """Get a specific history entry by ID."""
        for entry in self._history:
            if entry.id == entry_id:
                return entry
        return None


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
        if not self._active_prompt:
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

    def update_active_on_execution(self, item: MenuItem) -> None:
        """Update active prompt when a prompt/preset is executed."""
        if item.item_type in [MenuItemType.PROMPT, MenuItemType.PRESET]:
            self._active_prompt = item
