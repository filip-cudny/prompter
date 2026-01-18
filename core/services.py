"""Core business services for the Prompter application."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.interfaces import PromptStoreServiceProtocol
from modules.utils.config import ConfigService

from .exceptions import ConfigurationError, DataError
from .models import (
    ExecutionHandler,
    ExecutionResult,
    MenuItem,
    MessageConfig,
    PromptConfig,
    PromptData,
    SettingsConfig,
)

logger = logging.getLogger(__name__)


class ExecutionService:
    """Service for executing menu items with different handlers."""

    def __init__(self, prompt_store_service: PromptStoreServiceProtocol):
        self.handlers: List[ExecutionHandler] = []
        self.speech_service = None
        self.recording_action_id: Optional[str] = None
        self.pending_execution_item: Optional[MenuItem] = None
        self.prompt_store_service = prompt_store_service

    def register_handler(self, handler: ExecutionHandler) -> None:
        """Register an execution handler."""
        self.handlers.append(handler)

    def set_speech_service(self, speech_service) -> None:
        """Set the speech-to-text service instance."""
        self.speech_service = speech_service
        if speech_service:
            speech_service.add_transcription_callback(
                self._on_transcription_complete, run_always=True
            )

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return bool(self.speech_service and self.speech_service.is_recording())

    def get_recording_action_id(self) -> Optional[str]:
        """Get the ID of the action that started recording."""
        return self.recording_action_id

    def is_executing(self) -> bool:
        """Check if any handler is executing (LLM request in progress)."""
        for handler in self.handlers:
            if hasattr(handler, 'async_manager') and handler.async_manager.is_busy():
                return True
        return False

    def get_executing_action_id(self) -> Optional[str]:
        """Get the ID of the action that is currently executing."""
        for handler in self.handlers:
            if hasattr(handler, 'async_manager') and handler.async_manager.is_busy():
                current_item = handler.async_manager.current_item
                if current_item:
                    if current_item.data and current_item.data.get('prompt_id'):
                        return f"prompt_{current_item.data.get('prompt_id')}"
                    return current_item.id
        return None

    def cancel_current_execution(self) -> bool:
        """Cancel any running execution. Returns True if execution was cancelled."""
        for handler in self.handlers:
            if hasattr(handler, 'async_manager') and handler.async_manager.is_busy():
                handler.async_manager.stop_execution()
                return True
        return False

    def cancel_execution(self, execution_id: str, silent: bool = False) -> bool:
        """Cancel specific execution by ID. Returns True if execution was cancelled.

        Args:
            execution_id: The execution ID to cancel
            silent: If True, skip notification and signal emission (caller handles UI)
        """
        for handler in self.handlers:
            if hasattr(handler, 'async_manager'):
                if handler.async_manager.has_execution(execution_id):
                    return handler.async_manager.stop_execution(execution_id, silent)
        return False

    def should_disable_action(self, action_id: str) -> bool:
        """Check if action should be disabled due to recording or execution state."""
        if self.is_recording() and self.recording_action_id != action_id:
            return True
        executing_id = self.get_executing_action_id()
        if executing_id:
            if executing_id == action_id:
                return False
            return True
        return False

    def get_disable_reason(self, action_id: str) -> Optional[str]:
        """Returns 'recording', 'executing', or None."""
        if self.is_recording() and self.recording_action_id != action_id:
            return 'recording'
        executing_id = self.get_executing_action_id()
        if executing_id:
            if executing_id == action_id:
                return None
            return 'executing'
        return None

    def execute_item(
        self,
        item: MenuItem,
        input_content: Optional[str] = None,
        use_speech: bool = False,
    ) -> ExecutionResult:
        """Execute a menu item using the appropriate handler."""

        if not item.enabled:
            return ExecutionResult(success=False, error="Menu item is disabled")

        # If recording is active, any click should stop recording
        if self.speech_service and (use_speech or self.speech_service.is_recording()):
            return self._execute_with_speech(item)

        for handler in self.handlers:
            if handler.can_handle(item):
                try:
                    return handler.execute(item, input_content)
                except Exception as e:
                    return ExecutionResult(success=False, error=str(e))

        return ExecutionResult(
            success=False, error="No handler found for this item type"
        )

    def _execute_with_speech(self, item: MenuItem) -> ExecutionResult:
        """Execute item with speech-to-text input."""
        try:
            if not self.speech_service:
                return ExecutionResult(
                    success=False, error="Speech service not available"
                )

            is_alternative = item.data and item.data.get("alternative_execution", False)

            if self.speech_service.is_recording():
                self.speech_service.stop_recording()
                self.recording_action_id = None
                return ExecutionResult(
                    success=True,
                    content="Recording stopped",
                    metadata={"action": "speech_recording_stopped"},
                )
            else:
                action_id = getattr(item, "id", str(id(item)))
                self.recording_action_id = action_id
                self.pending_execution_item = item

                self.speech_service.start_recording(handler_name=action_id)
                return ExecutionResult(
                    success=True,
                    content="Recording started",
                    metadata={"action": "speech_recording_started"},
                )

        except Exception as e:
            self.recording_action_id = None
            self.pending_execution_item = None
            return ExecutionResult(success=False, error=f"Speech execution failed: {e}")

    def _on_transcription_complete(self, transcription: str, _duration: float) -> None:
        """Handle transcription completion and execute pending item."""
        if self.pending_execution_item:
            item = self.pending_execution_item
            self.pending_execution_item = None
            self.recording_action_id = None

            # Check if this is alternative execution (shift+click)
            is_alternative = item.data and item.data.get("alternative_execution", False)

            if transcription.strip():
                for handler in self.handlers:
                    if handler.can_handle(item):
                        try:
                            result = handler.execute(item, transcription)

                            # For alternative execution, don't add history here
                            # The async execution manager will handle it when the prompt completes
                            if not is_alternative:
                                self.prompt_store_service.add_history_entry(
                                    item,
                                    transcription,
                                    result,
                                )

                            # Always emit signal for failed executions so user gets feedback
                            # For successful alternative execution, async manager will handle it
                            if not result.success:
                                self.prompt_store_service.emit_execution_completed(
                                    result
                                )
                            elif not is_alternative:
                                self.prompt_store_service.emit_execution_completed(
                                    result
                                )
                            break
                        except Exception as e:
                            logger.error(f"Handler execution failed: {e}")
            else:
                logger.info("Empty transcription received, execution cancelled")
                # Still emit signal to update GUI even if transcription was empty
                empty_result = ExecutionResult(
                    success=False,
                    error="Empty transcription received",
                    metadata={"action": "transcription_cancelled"},
                )
                self.prompt_store_service.emit_execution_completed(empty_result)
        else:
            self.recording_action_id = None
            self.pending_execution_item = None


class SettingsService:
    """Service for loading and managing application settings."""

    def __init__(self, settings_path: Optional[str] = None):
        self.settings_path = settings_path or "settings/settings.json"
        self._settings: Optional[SettingsConfig] = None
        self._base_path: Optional[Path] = None
        self._config_service = ConfigService()

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

            # Initialize ConfigService if needed
            if self._config_service._config is None:
                self._config_service.initialize(settings_file=str(settings_file))

            data = self._config_service.get_settings_data()

            return self._parse_settings_data(data)

        except ConfigurationError as e:
            raise DataError(f"Configuration error: {str(e)}") from e
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
                    model=prompt_data.get("model"),
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
            model=prompt_config.model,
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
