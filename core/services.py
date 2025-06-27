"""Core business services for the prompt store application."""

from typing import List, Dict, Optional, Any
import time
import json
from pathlib import Path
from collections import deque


from .models import (
    PromptData,
    PresetData,
    ExecutionResult,
    HistoryEntry,
    MenuItem,
    MenuItemType,
    ErrorCode,
    SettingsConfig,
    PromptConfig,
    MessageConfig,
)
from .exceptions import DataError
from utils.pyqt_notifications import PyQtNotificationManager


class PromptStoreService:
    """Main business logic coordinator for the prompt store."""

    def __init__(self, prompt_providers, clipboard_manager, notification_manager=None):
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
        self.execution_service = ExecutionService(
            self.primary_provider, clipboard_manager
        )
        self.data_manager = DataManager(self.prompt_providers)
        self.history_service = HistoryService()
        self.active_prompt_service = ActivePromptService()
        self.speech_history_service = SpeechHistoryService()

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

    def get_last_speech_transcription(self) -> Optional[str]:
        """Get the last speech transcription."""
        return self.speech_history_service.get_last_transcription()

    def add_speech_transcription(self, transcription: str) -> None:
        """Add a speech transcription to history."""
        self.speech_history_service.add_transcription(transcription)

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

    def __init__(self, prompt_providers):
        self.prompt_providers = (
            prompt_providers
            if isinstance(prompt_providers, list)
            else [prompt_providers]
        )
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
            for provider in self.prompt_providers:
                if provider and hasattr(provider, "refresh"):
                    provider.refresh()
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
            self._update_prompt_id_mapping()
            return self._prompts_cache
        except Exception as e:
            raise DataError(f"Failed to refresh prompts: {str(e)}") from e

    def _refresh_presets(self) -> List[PresetData]:
        """Refresh presets cache."""
        try:
            all_presets = []
            for provider in self.prompt_providers:
                if provider and hasattr(provider, "get_presets"):
                    try:
                        provider_presets = provider.get_presets()
                        all_presets.extend(provider_presets)
                    except Exception as e:
                        print(
                            f"Warning: Failed to get presets from provider {type(provider).__name__}: {e}"
                        )

            self._presets_cache = all_presets
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

    def update_active_on_execution(self, item: MenuItem) -> None:
        """Update active prompt when a prompt/preset is executed."""
        if item.item_type in [MenuItemType.PROMPT, MenuItemType.PRESET]:
            self._active_prompt = item


class SpeechHistoryService:
    """Service for tracking speech transcriptions."""

    def __init__(self, max_entries: int = 10):
        self.max_entries = max_entries
        self._transcriptions: deque = deque(maxlen=max_entries)

    def add_transcription(self, transcription: str) -> None:
        """Add a new transcription to history."""
        if transcription and transcription.strip():
            self._transcriptions.append(transcription.strip())

    def get_last_transcription(self) -> Optional[str]:
        """Get the most recent transcription."""
        if self._transcriptions:
            return self._transcriptions[-1]
        return None

    def get_all_transcriptions(self) -> List[str]:
        """Get all transcriptions, most recent first."""
        return list(reversed(self._transcriptions))

    def clear_history(self) -> None:
        """Clear all transcriptions."""
        self._transcriptions.clear()

    def has_transcriptions(self) -> bool:
        """Check if there are any transcriptions."""
        return len(self._transcriptions) > 0


class SettingsService:
    """Service for loading and managing application settings."""

    def __init__(self, settings_path: Optional[str] = None):
        self.settings_path = settings_path or "settings/settings.json"
        self._settings: Optional[SettingsConfig] = None
        self._base_path: Optional[Path] = None

    def load_settings(self) -> SettingsConfig:
        """Load settings from the configuration file."""
        if self._settings is None:
            self._settings = self._load_from_file()
        return self._settings

    def get_settings(self) -> SettingsConfig:
        """Get current settings (loads if not already loaded)."""
        return self.load_settings()

    def reload_settings(self) -> SettingsConfig:
        """Force reload settings from file."""
        self._settings = None
        return self.load_settings()

    def get_prompt_configs(self) -> List[PromptConfig]:
        """Get all prompt configurations."""
        settings = self.get_settings()
        return settings.prompts

    def get_model_configs(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get model configurations."""
        settings = self.get_settings()
        return settings.models

    def resolve_message_content(self, message: MessageConfig) -> str:
        """Resolve message content, loading from file if necessary."""
        if message.content is not None:
            return message.content

        if message.file is not None:
            return self._load_file_content(message.file)

        return ""

    def _load_from_file(self) -> SettingsConfig:
        """Load settings from the JSON file."""
        try:
            settings_file = Path(self.settings_path)
            self._base_path = settings_file.parent

            if not settings_file.exists():
                raise DataError(f"Settings file not found: {self.settings_path}")

            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            return self._parse_settings_data(data)

        except json.JSONDecodeError as e:
            raise DataError(f"Invalid JSON in settings file: {str(e)}") from e
        except Exception as e:
            raise DataError(f"Failed to load settings: {str(e)}") from e

    def _parse_settings_data(self, data: Dict[str, Any]) -> SettingsConfig:
        """Parse raw settings data into SettingsConfig."""
        try:
            # Parse prompts
            prompts = []
            for prompt_data in data.get("prompts", []):
                messages = []
                for msg_data in prompt_data.get("messages", []):
                    message = MessageConfig(
                        role=msg_data["role"],
                        content=msg_data.get("content"),
                        file=msg_data.get("file"),
                    )
                    messages.append(message)

                prompt = PromptConfig(
                    id=prompt_data["id"],
                    name=prompt_data["name"],
                    messages=messages,
                    description=prompt_data.get("description"),
                    tags=prompt_data.get("tags", []),
                    metadata=prompt_data.get("metadata", {}),
                )
                prompts.append(prompt)

            # Parse models (keep as raw dict for flexibility)
            models = data.get("models", {})

            return SettingsConfig(
                models=models, prompts=prompts, settings_path=self.settings_path
            )

        except KeyError as e:
            raise DataError(f"Missing required field in settings: {str(e)}") from e
        except Exception as e:
            raise DataError(f"Failed to parse settings data: {str(e)}") from e

    def _load_file_content(self, file_path: str) -> str:
        """Load content from a file referenced in settings."""
        try:
            if self._base_path is None:
                raise DataError("Base path not set")

            full_path = self._base_path / file_path

            if not full_path.exists():
                raise DataError(f"Referenced file not found: {file_path}")

            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()

        except Exception as e:
            raise DataError(
                f"Failed to load file content from {file_path}: {str(e)}"
            ) from e

    def convert_to_prompt_data(self, prompt_config: PromptConfig) -> PromptData:
        """Convert PromptConfig to PromptData for compatibility."""
        # Combine all messages into content
        content_parts = []
        for message in prompt_config.messages:
            message_content = self.resolve_message_content(message)
            content_parts.append(f"{message.role}: {message_content}")

        content = "\n\n".join(content_parts)

        prompt_data = PromptData(
            id=prompt_config.id,
            name=prompt_config.name,
            content=content,
            description=prompt_config.description,
            tags=prompt_config.tags,
            source="settings",
            metadata=prompt_config.metadata,
        )
        return prompt_data

    def get_prompt_by_id(self, prompt_id: str) -> Optional[PromptConfig]:
        """Get a specific prompt configuration by ID."""
        settings = self.get_settings()
        for prompt in settings.prompts:
            if prompt.id == prompt_id:
                return prompt
        return None

    def get_resolved_prompt_messages(
        self, prompt_id: str
    ) -> Optional[List[Dict[str, str]]]:
        """Get resolved messages for a prompt (with file contents loaded)."""
        prompt_config = self.get_prompt_by_id(prompt_id)
        if not prompt_config:
            return None

        messages = []
        for message in prompt_config.messages:
            content = self.resolve_message_content(message)
            messages.append({"role": message.role, "content": content})

        return messages

    def get_available_models(self) -> List[str]:
        """Get list of available model names from all providers."""
        settings = self.get_settings()
        models = []

        for provider_name, provider_models in settings.models.items():
            for model_config in provider_models:
                model_name = model_config.get("model", "")
                if model_name:
                    models.append(f"{provider_name}/{model_name}")

        return models

    def get_model_config(self, provider: str, model: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific model."""
        settings = self.get_settings()
        provider_models = settings.models.get(provider, [])

        for model_config in provider_models:
            if model_config.get("model") == model:
                return model_config

        return None
