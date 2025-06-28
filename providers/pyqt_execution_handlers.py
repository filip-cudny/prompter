"""PyQt5-specific execution handlers that accept shared notification manager."""

from typing import Optional, Callable, List
import logging
from core.interfaces import ClipboardManager
from core.models import MenuItem, MenuItemType, ExecutionResult, ErrorCode
from core.exceptions import ClipboardError
from api import PromptStoreAPI, APIError, create_user_message
from open_ai_api import OpenAIClient
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from core.services import SettingsService
from utils.pyqt_notifications import (
    PyQtNotificationManager,
    format_execution_time,
    truncate_text,
)
import time

logger = logging.getLogger(__name__)


class PyQtPromptExecutionHandler:
    """PyQt5 handler for executing prompt menu items with shared notification manager."""

    def __init__(
        self,
        api: PromptStoreAPI,
        clipboard_manager: ClipboardManager,
        notification_manager: Optional[PyQtNotificationManager] = None,
    ):
        self.api = api
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager or PyQtNotificationManager()

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can execute the given menu item."""
        if item.item_type != MenuItemType.PROMPT:
            return False
        if item.data is None:
            return False

        source = item.data.get("source")
        # Only handle items that explicitly have "api-provider" source
        # This prevents handling items with None or other sources
        return source == "api-provider"

    def execute(self, item: MenuItem, context: Optional[str] = None) -> ExecutionResult:
        """Execute a prompt menu item."""
        start_time = time.time()
        prompt_name = (
            item.data.get("prompt_name", "Unknown Prompt")
            if item.data
            else "Unknown Prompt"
        )
        prompt_id = item.data.get("prompt_id") if item.data else None

        logger.info(f"Starting prompt execution: {prompt_name} (ID: {prompt_id})")

        try:
            if not item.data or not item.data.get("prompt_id"):
                logger.error(f"Invalid prompt data for item: {item}")
                return ExecutionResult(
                    success=False,
                    error="Invalid prompt data",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

            prompt_id = item.data["prompt_id"]

            # Use provided context or fall back to clipboard
            if context is not None:
                clipboard_content = context
                logger.debug(f"Using provided context (length: {len(context)})")
            else:
                if self.clipboard_manager.is_empty():
                    logger.warning("Clipboard is empty, cannot execute prompt")
                    return ExecutionResult(
                        success=False,
                        error="Clipboard is empty",
                        error_code=ErrorCode.CLIPBOARD_ERROR,
                    )
                clipboard_content = self.clipboard_manager.get_content()
                logger.debug(
                    f"Using clipboard content (length: {len(clipboard_content)})"
                )

            user_message = create_user_message(clipboard_content)
            logger.debug(
                f"Executing prompt {prompt_id} with input length: {len(clipboard_content)}"
            )

            api_result = self.api.execute_prompt(prompt_id, [user_message])
            content = api_result.get("content", "No response content")
            logger.debug(f"API response received (length: {len(content)})")

            if not self.clipboard_manager.set_content(content):
                return ExecutionResult(
                    success=False,
                    error=f"Prompt executed but failed to copy result to clipboard.\n\nResult:\n{content}",
                    error_code=ErrorCode.CLIPBOARD_ERROR,
                )

            execution_time = time.time() - start_time
            logger.info(
                f"Prompt execution successful: {prompt_name} (ID: {prompt_id}) - input: {len(clipboard_content)} chars, output: {len(content)} chars, time: {execution_time:.2f}s"
            )

            execution_result = ExecutionResult(
                success=True,
                content=content,
                execution_time=execution_time,
                metadata={
                    "prompt_id": prompt_id,
                    "prompt_name": item.data.get("prompt_name"),
                    "input_length": len(clipboard_content),
                    "output_length": len(content),
                },
            )

            notification_message = (
                f"Processed in {format_execution_time(execution_time)}"
            )
            self.notification_manager.show_success_notification(
                f"{prompt_name} completed", notification_message
            )

            return execution_result

        except APIError as e:
            error_msg = f"Failed to execute prompt: {str(e)}"
            execution_time = time.time() - start_time
            logger.error(
                f"API error executing prompt {prompt_name} (ID: {prompt_id}): {str(e)} (execution time: {execution_time:.2f}s)"
            )

            execution_result = ExecutionResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.API_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification(
                "Prompt Failed", truncate_text(str(e)), prompt_name
            )

            return execution_result
        except ClipboardError as e:
            error_msg = str(e)
            execution_time = time.time() - start_time
            logger.error(
                f"Clipboard error executing prompt {prompt_name} (ID: {prompt_id}): {error_msg} (execution time: {execution_time:.2f}s)"
            )

            execution_result = ExecutionResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.CLIPBOARD_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification(
                "Clipboard Error", truncate_text(error_msg), prompt_name
            )

            return execution_result
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            execution_time = time.time() - start_time
            logger.exception(
                f"Unexpected error executing prompt {prompt_name} (ID: {prompt_id}): {str(e)} (execution time: {execution_time:.2f}s)"
            )

            execution_result = ExecutionResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.UNKNOWN_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification(
                "Execution Error", truncate_text(str(e)), prompt_name
            )

            return execution_result


class PyQtPresetExecutionHandler:
    """PyQt5 handler for executing preset menu items with shared notification manager."""

    def __init__(
        self,
        api: PromptStoreAPI,
        clipboard_manager: ClipboardManager,
        notification_manager: Optional[PyQtNotificationManager] = None,
    ):
        self.api = api
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager or PyQtNotificationManager()

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can execute the given menu item."""
        return (
            item.item_type == MenuItemType.PRESET
            and item.data is not None
            and item.data.get("source") == "api-provider"
        )

    def execute(self, item: MenuItem, context: Optional[str] = None) -> ExecutionResult:
        """Execute a preset menu item."""
        start_time = time.time()
        preset_name = (
            item.data.get("preset_name", "Unknown Preset")
            if item.data
            else "Unknown Preset"
        )
        preset_id = item.data.get("preset_id") if item.data else None
        prompt_id = item.data.get("prompt_id") if item.data else None

        logger.info(
            f"Starting preset execution: {preset_name} (ID: {preset_id}, Prompt ID: {prompt_id})"
        )

        try:
            if not item.data or not item.data.get("preset_id"):
                logger.error(f"Invalid preset data for item: {item}")
                return ExecutionResult(
                    success=False,
                    error="Invalid preset data",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

            preset_id = item.data["preset_id"]

            if not prompt_id:
                logger.error(f"No prompt_id found for preset: {preset_name}")
                return ExecutionResult(
                    success=False,
                    error="Invalid preset data: missing prompt_id",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

            # Use provided context or fall back to clipboard
            if context is not None:
                clipboard_content = context
                logger.debug(f"Using provided context (length: {len(context)})")
            else:
                if self.clipboard_manager.is_empty():
                    logger.warning("Clipboard is empty, cannot execute preset")
                    return ExecutionResult(
                        success=False,
                        error="Clipboard is empty",
                        error_code=ErrorCode.CLIPBOARD_ERROR,
                    )
                clipboard_content = self.clipboard_manager.get_content()
                logger.debug(
                    f"Using clipboard content (length: {len(clipboard_content)})"
                )

            user_message = create_user_message(clipboard_content)
            logger.debug(
                f"Executing preset {preset_id} with input length: {len(clipboard_content)}"
            )

            api_result = self.api.execute_prompt(prompt_id, [user_message])
            content = api_result.get("content", "No response content")
            logger.debug(f"API response received (length: {len(content)})")

            if not self.clipboard_manager.set_content(content):
                return ExecutionResult(
                    success=False,
                    error=f"Preset executed but failed to copy result to clipboard.\n\nResult:\n{content}",
                    error_code=ErrorCode.CLIPBOARD_ERROR,
                )

            execution_time = time.time() - start_time
            logger.info(
                f"Preset execution successful: {preset_name} (ID: {preset_id}) - input: {len(clipboard_content)} chars, output: {len(content)} chars, time: {execution_time:.2f}s"
            )

            execution_result = ExecutionResult(
                success=True,
                content=content,
                execution_time=execution_time,
                metadata={
                    "preset_id": preset_id,
                    "preset_name": item.data.get("preset_name"),
                    "prompt_id": item.data.get("prompt_id"),
                    "input_length": len(clipboard_content),
                    "output_length": len(content),
                },
            )

            notification_message = (
                f"Processed in {format_execution_time(execution_time)}"
            )
            self.notification_manager.show_success_notification(
                f"{preset_name} completed", notification_message
            )

            return execution_result

        except APIError as e:
            error_msg = f"Failed to execute preset: {str(e)}"
            execution_time = time.time() - start_time
            logger.error(
                f"API error executing preset {preset_name} (ID: {preset_id}): {str(e)} (execution time: {execution_time:.2f}s)"
            )

            execution_result = ExecutionResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.API_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification(
                "Preset Failed", truncate_text(str(e)), preset_name
            )

            return execution_result
        except ClipboardError as e:
            error_msg = str(e)
            execution_time = time.time() - start_time
            logger.error(
                f"Clipboard error executing preset {preset_name} (ID: {preset_id}): {error_msg} (execution time: {execution_time:.2f}s)"
            )

            execution_result = ExecutionResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.CLIPBOARD_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification(
                "Clipboard Error", truncate_text(error_msg), preset_name
            )

            return execution_result
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            execution_time = time.time() - start_time
            logger.exception(
                f"Unexpected error executing preset {preset_name} (ID: {preset_id}): {str(e)} (execution time: {execution_time:.2f}s)"
            )

            execution_result = ExecutionResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.UNKNOWN_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification(
                "Execution Error", truncate_text(str(e)), preset_name
            )

            return execution_result


class PyQtHistoryExecutionHandler:
    """PyQt5 handler for executing history menu items."""

    def __init__(self, clipboard_manager: ClipboardManager):
        self.clipboard_manager = clipboard_manager

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can execute the given menu item."""
        return item.item_type == MenuItemType.HISTORY

    def execute(self, item: MenuItem, context: Optional[str] = None) -> ExecutionResult:
        """Execute a history menu item."""
        start_time = time.time()

        try:
            if not item.data:
                return ExecutionResult(
                    success=False,
                    error="No history data available",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

            content_type = item.data.get("content_type")
            content = item.data.get("content", "")

            if not content:
                return ExecutionResult(
                    success=False,
                    error="History item has no content",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

            if not self.clipboard_manager.set_content(content):
                return ExecutionResult(
                    success=False,
                    error="Failed to copy history item to clipboard",
                    error_code=ErrorCode.CLIPBOARD_ERROR,
                )

            execution_time = time.time() - start_time
            logger.info(f"History item copied to clipboard: {content_type}")

            return ExecutionResult(
                success=True,
                content=f"Copied {content_type} to clipboard",
                execution_time=execution_time,
                metadata={"content_type": content_type, "content_length": len(content)},
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error executing history item: {str(e)}")

            return ExecutionResult(
                success=False,
                error=f"Failed to copy history item: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR,
                execution_time=execution_time,
            )


class PyQtSystemExecutionHandler:
    """PyQt5 handler for executing system menu items with shared notification manager."""

    def __init__(
        self,
        refresh_callback=None,
        notification_manager: Optional[PyQtNotificationManager] = None,
    ):
        self.refresh_callback = refresh_callback
        self.notification_manager = notification_manager or PyQtNotificationManager()

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can execute the given menu item."""
        return item.item_type == MenuItemType.SYSTEM

    def execute(self, item: MenuItem, context: Optional[str] = None) -> ExecutionResult:
        """Execute a system menu item."""
        start_time = time.time()

        try:
            if item.id == "refresh_data":
                if self.refresh_callback:
                    self.refresh_callback()
                    execution_time = time.time() - start_time

                    self.notification_manager.show_success_notification(
                        "Data Refreshed", "All data has been refreshed successfully"
                    )

                    return ExecutionResult(
                        success=True,
                        content="Data refreshed successfully",
                        execution_time=execution_time,
                        metadata={"action": "refresh_data"},
                    )
                else:
                    return ExecutionResult(
                        success=False,
                        error="No refresh callback available",
                        error_code=ErrorCode.VALIDATION_ERROR,
                    )
            else:
                return ExecutionResult(
                    success=False,
                    error=f"Unknown system action: {item.id}",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error executing system item {item.id}: {str(e)}")

            execution_result = ExecutionResult(
                success=False,
                error=f"System action failed: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification(
                "System Error", truncate_text(str(e))
            )

            return execution_result


class PyQtSystemPromptExecutionHandler:
    """PyQt5 handler for executing system prompts using OpenAI with settings configuration."""

    def __init__(
        self,
        clipboard_manager: ClipboardManager,
        settings_service: SettingsService,
        notification_manager: Optional[PyQtNotificationManager] = None,
    ):
        self.clipboard_manager = clipboard_manager
        self.settings_service = settings_service
        self.notification_manager = notification_manager or PyQtNotificationManager()
        self.openai_client: Optional[OpenAIClient] = None

    def _get_openai_client(self) -> OpenAIClient:
        """Get or create OpenAI client."""
        if self.openai_client is None:
            self.openai_client = OpenAIClient()
        return self.openai_client

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can execute the given menu item."""
        return (
            item.item_type == MenuItemType.PROMPT
            and item.data is not None
            and item.data.get("prompt_id") is not None
            and bool(item.data.get("use_openai", False))
        )

    def execute(self, item: MenuItem, context: Optional[str] = None) -> ExecutionResult:
        """Execute a system prompt using OpenAI."""
        start_time = time.time()
        prompt_name = (
            item.data.get("prompt_name", "Unknown Prompt")
            if item.data
            else "Unknown Prompt"
        )
        prompt_id = item.data.get("prompt_id") if item.data else None

        logger.info(
            f"Starting OpenAI prompt execution: {prompt_name} (ID: {prompt_id})"
        )

        try:
            if not item.data or not item.data.get("prompt_id"):
                logger.error(f"Invalid prompt data for item: {item}")
                return ExecutionResult(
                    success=False,
                    error="Invalid prompt data",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

            prompt_id = item.data["prompt_id"]

            if context is not None:
                clipboard_content = context
                logger.debug(f"Using provided context (length: {len(context)})")
            else:
                if self.clipboard_manager.is_empty():
                    logger.warning("Clipboard is empty, cannot execute prompt")
                    return ExecutionResult(
                        success=False,
                        error="Clipboard is empty",
                        error_code=ErrorCode.CLIPBOARD_ERROR,
                    )
                clipboard_content = self.clipboard_manager.get_content()
                logger.debug(
                    f"Using clipboard content (length: {len(clipboard_content)})"
                )

            messages = self.settings_service.get_resolved_prompt_messages(prompt_id)
            if not messages:
                return ExecutionResult(
                    success=False,
                    error=f"Prompt {prompt_id} not found in settings",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

            processed_messages = []
            for message in messages:
                content = message["content"].replace("{{clipboard}}", clipboard_content)
                processed_messages.append({"role": message["role"], "content": content})

            model_configs = self.settings_service.get_model_configs()
            openai_models = model_configs.get("openai", [])
            if not openai_models:
                return ExecutionResult(
                    success=False,
                    error="No OpenAI model configuration found in settings",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

            model_config = openai_models[0]
            model = model_config.get("model", "gpt-4.1")
            temperature = model_config.get("temperature", 0.7)

            logger.debug(f"Using model: {model}, temperature: {temperature}")

            openai_client = self._get_openai_client()
            content = openai_client.complete(
                messages=processed_messages,  # type: ignore
                model=model,
                temperature=temperature,
            )

            logger.debug(f"OpenAI response received (length: {len(content)})")

            if not self.clipboard_manager.set_content(content):
                return ExecutionResult(
                    success=False,
                    error=f"Prompt executed but failed to copy result to clipboard.\n\nResult:\n{content}",
                    error_code=ErrorCode.CLIPBOARD_ERROR,
                )

            execution_time = time.time() - start_time
            logger.info(
                f"OpenAI prompt execution successful: {prompt_name} (ID: {prompt_id}) - input: {len(clipboard_content)} chars, output: {len(content)} chars, time: {execution_time:.2f}s"
            )

            execution_result = ExecutionResult(
                success=True,
                content=content,
                execution_time=execution_time,
                metadata={
                    "prompt_id": prompt_id,
                    "prompt_name": item.data.get("prompt_name"),
                    "input_length": len(clipboard_content),
                    "output_length": len(content),
                    "model": model,
                    "temperature": temperature,
                },
            )

            notification_message = (
                f"Processed in {format_execution_time(execution_time)}"
            )
            self.notification_manager.show_success_notification(
                f"{prompt_name} completed", notification_message
            )

            return execution_result

        except APIError as e:
            error_msg = f"Failed to execute prompt: {str(e)}"
            execution_time = time.time() - start_time
            logger.error(
                f"OpenAI API error executing prompt {prompt_name} (ID: {prompt_id}): {str(e)} (execution time: {execution_time:.2f}s)"
            )

            execution_result = ExecutionResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.API_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification(
                "Prompt Failed", truncate_text(str(e)), prompt_name
            )

            return execution_result
        except ClipboardError as e:
            error_msg = str(e)
            execution_time = time.time() - start_time
            logger.error(
                f"Clipboard error executing prompt {prompt_name} (ID: {prompt_id}): {error_msg} (execution time: {execution_time:.2f}s)"
            )

            execution_result = ExecutionResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.CLIPBOARD_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification(
                "Clipboard Error", truncate_text(error_msg), prompt_name
            )

            return execution_result
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            execution_time = time.time() - start_time
            logger.exception(
                f"Unexpected error executing prompt {prompt_name} (ID: {prompt_id}): {str(e)} (execution time: {execution_time:.2f}s)"
            )

            execution_result = ExecutionResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.UNKNOWN_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification(
                "Execution Error", truncate_text(str(e)), prompt_name
            )

            return execution_result


class PyQtSpeechExecutionHandler:
    """PyQt5 handler for executing speech-to-text menu items."""

    def __init__(
        self,
        clipboard_manager: ClipboardManager,
        notification_manager: Optional[PyQtNotificationManager] = None,
        recording_indicator_callback: Optional[Callable[[bool], None]] = None,
        speech_history_service=None,
    ):
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager or PyQtNotificationManager()
        self.recording_indicator_callback = recording_indicator_callback
        self.speech_history_service = speech_history_service
        self.speech_service = None
        self._transcription_start_time: Optional[float] = None
        self._initialize_speech_service()

    def _initialize_speech_service(self) -> None:
        """Initialize speech-to-text service."""
        try:
            from utils.speech_to_text import SpeechToTextService
            from utils.config import load_config

            config = load_config()
            if config.openai_api_key:
                self.speech_service = SpeechToTextService(config.openai_api_key)
                self.speech_service.set_recording_started_callback(
                    self._on_recording_started
                )
                self.speech_service.set_recording_stopped_callback(
                    self._on_recording_stopped
                )
                self.speech_service.set_transcription_callback(
                    self._on_transcription_complete
                )
                self.speech_service.set_error_callback(self._on_speech_error)
            else:
                pass  # OpenAI API key not configured for speech-to-text
        except Exception as e:
            pass  # Failed to initialize speech service

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can execute the given menu item."""
        return item.item_type == MenuItemType.SPEECH

    def execute(self, item: MenuItem, context: Optional[str] = None) -> ExecutionResult:
        """Execute a speech-to-text menu item."""
        start_time = time.time()

        try:
            # Handle speech history items
            if item.data and item.data.get("type") == "last_speech_output":
                return self._handle_speech_history_item(item, start_time)

            # Handle speech-to-text recording
            if not self.speech_service:
                error_msg = "Speech-to-text service not available. Please configure OPENAI_API_KEY and install PyAudio."

                self.notification_manager.show_error_notification(
                    "Speech-to-Text Error", error_msg
                )

                return ExecutionResult(
                    success=False,
                    error=error_msg,
                    error_code=ErrorCode.API_ERROR,
                    execution_time=time.time() - start_time,
                )

            # Toggle recording
            self.speech_service.toggle_recording()

            return ExecutionResult(
                success=True,
                content="Speech recording toggled",
                execution_time=time.time() - start_time,
            )

        except Exception as e:
            execution_time = time.time() - start_time

            # Provide more specific error messages
            error_msg = str(e)
            if "PyAudio" in error_msg:
                error_msg = "PyAudio is not installed. Please install it with: pip install pyaudio"
            elif "OpenAI" in error_msg:
                error_msg = "OpenAI API key not configured. Please set OPENAI_API_KEY environment variable."

            execution_result = ExecutionResult(
                success=False,
                error=f"Speech action failed: {error_msg}",
                error_code=ErrorCode.UNKNOWN_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification(
                "Speech Error", truncate_text(error_msg)
            )

            return execution_result

    def _on_recording_started(self) -> None:
        """Handle recording started event."""
        self.notification_manager.show_info_notification(
            "Recording Started",
            "Click Speech to Text again to stop.",
        )
        if self.recording_indicator_callback:
            self.recording_indicator_callback(True)

    def _on_recording_stopped(self) -> None:
        """Handle recording stopped event."""
        self._transcription_start_time = time.time()
        self.notification_manager.show_info_notification(
            "Processing Audio", "Transcribing your speech to text"
        )
        if self.recording_indicator_callback:
            self.recording_indicator_callback(False)

    def _on_transcription_complete(self, transcription: str) -> None:
        """Handle transcription completion."""
        try:
            if transcription:
                # Store transcription in speech history
                if self.speech_history_service:
                    self.speech_history_service.add_transcription(transcription)

                success = self.clipboard_manager.set_content(transcription)
                if success:
                    execution_time = time.time() - getattr(
                        self, "_transcription_start_time", time.time()
                    )
                    notification_message = (
                        f"Processed in {format_execution_time(execution_time)}"
                    )
                    self.notification_manager.show_success_notification(
                        "Transcription completed", notification_message
                    )
                else:
                    self.notification_manager.show_error_notification(
                        "Clipboard Error",
                        "Transcription successful but failed to copy to clipboard",
                    )
            else:
                self.notification_manager.show_info_notification(
                    "No Speech Detected", "No speech was detected in the recording"
                )
        except Exception as e:
            self.notification_manager.show_error_notification(
                "Transcription Error", f"Failed to process transcription: {str(e)}"
            )

    def _handle_speech_history_item(
        self, item: MenuItem, start_time: float
    ) -> ExecutionResult:
        """Handle speech history menu items."""
        try:
            content = item.data.get("content") if item.data else None

            if not content:
                return ExecutionResult(
                    success=False,
                    error="No speech transcription content available",
                    execution_time=time.time() - start_time,
                )

            # Copy to clipboard
            success = self.clipboard_manager.set_content(content)

            if success:
                self.notification_manager.show_success_notification(
                    "Speech Output Copied"
                )

                return ExecutionResult(
                    success=True,
                    content=content,
                    execution_time=time.time() - start_time,
                )
            else:
                return ExecutionResult(
                    success=False,
                    error="Failed to copy speech transcription to clipboard",
                    execution_time=time.time() - start_time,
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Failed to handle speech history item: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _on_speech_error(self, error_msg: str) -> None:
        """Handle speech service errors."""
        self.notification_manager.show_error_notification("Speech Error", error_msg)


class SettingsPromptExecutionHandler:
    """Handler for executing settings-based prompt menu items."""

    def __init__(
        self,
        settings_prompt_provider,
        clipboard_manager: ClipboardManager,
        notification_manager: Optional[PyQtNotificationManager] = None,
    ):
        self.settings_prompt_provider = settings_prompt_provider
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager or PyQtNotificationManager()
        self.openai_client = OpenAIClient()

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can execute the given menu item."""
        if item.item_type != MenuItemType.PROMPT:
            return False
        if item.data is None:
            return False

        source = item.data.get("source")
        # Only handle items that explicitly have "settings" source
        return source == "settings"

    def execute(
        self, item: MenuItem, _context: Optional[str] = None
    ) -> ExecutionResult:
        """Execute a settings prompt menu item."""
        start_time = time.time()

        try:
            prompt_id = item.data.get("prompt_id") if item.data else None
            if not prompt_id:
                return ExecutionResult(
                    success=False,
                    error="Missing prompt ID",
                    execution_time=time.time() - start_time,
                )

            messages = self.settings_prompt_provider.get_prompt_messages(prompt_id)
            if not messages:
                return ExecutionResult(
                    success=False,
                    error=f"Prompt '{prompt_id}' not found",
                    execution_time=time.time() - start_time,
                )

            # Get current clipboard content for placeholder replacement
            try:
                clipboard_content = self.clipboard_manager.get_content()
            except Exception as e:
                clipboard_content = ""
                logger.warning(f"Failed to get clipboard content: {e}")

            processed_messages: List[ChatCompletionMessageParam] = []
            for message in messages:
                if message and isinstance(message.get("content"), str):
                    content = message["content"].replace(
                        "{{clipboard}}", clipboard_content
                    )
                    role = message.get("role", "user")
                    processed_messages.append({"role": role, "content": content})

            if not processed_messages:
                return ExecutionResult(
                    success=False,
                    error="No valid messages found after processing",
                    execution_time=time.time() - start_time,
                )

            # Call OpenAI API
            response_text = self.openai_client.complete(processed_messages)

            # Copy response to clipboard
            self.clipboard_manager.set_content(response_text)

            # Show notification
            prompt_name = (
                item.data.get("prompt_name", prompt_id) if item.data else prompt_id
            )
            execution_time = time.time() - start_time
            notification_message = (
                f"Processed in {format_execution_time(execution_time)}"
            )
            self.notification_manager.show_success_notification(
                f"{prompt_name} completed", notification_message
            )

            return ExecutionResult(
                success=True,
                content=response_text,
                execution_time=time.time() - start_time,
            )

        except APIError as e:
            return ExecutionResult(
                success=False,
                error=f"OpenAI API error: {str(e)}",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Failed to execute settings prompt: {str(e)}",
                execution_time=time.time() - start_time,
            )


class SettingsPresetExecutionHandler:
    """Handler for executing settings-based preset menu items."""

    def __init__(
        self,
        settings_prompt_provider,
        clipboard_manager: ClipboardManager,
        notification_manager: Optional[PyQtNotificationManager] = None,
    ):
        self.settings_prompt_provider = settings_prompt_provider
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager or PyQtNotificationManager()

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can execute the given menu item."""
        return (
            item.item_type == MenuItemType.PRESET
            and item.data is not None
            and item.data.get("source") == "settings"
        )

    def execute(
        self, item: MenuItem, _context: Optional[str] = None
    ) -> ExecutionResult:
        """Execute a settings preset menu item."""
        start_time = time.time()

        try:
            preset_id = item.data.get("preset_id") if item.data else None
            if not preset_id:
                return ExecutionResult(
                    success=False,
                    error="Missing preset ID",
                    execution_time=time.time() - start_time,
                )

            presets = self.settings_prompt_provider.get_presets()
            preset = None
            for p in presets if presets else []:
                if p.id == preset_id:
                    preset = p
                    break

            if not preset:
                return ExecutionResult(
                    success=False,
                    error=f"Preset '{preset_id}' not found",
                    execution_time=time.time() - start_time,
                )

            # Get the prompt messages
            messages = self.settings_prompt_provider.get_prompt_messages(
                preset.prompt_id
            )
            if not messages:
                return ExecutionResult(
                    success=False,
                    error=f"Prompt for preset '{preset_id}' not found",
                    execution_time=time.time() - start_time,
                )

            # Apply preset values to messages
            formatted_content = []
            for message in messages:
                role = message.get("role", "user")
                content = message.get("content", "")

                # Apply preset values if available
                if hasattr(preset, "values") and preset.values:
                    for key, value in preset.values.items():
                        content = content.replace(f"{{{key}}}", str(value))

                formatted_content.append(f"{role}: {content}")

            content_text = "\n\n".join(formatted_content)

            # Copy to clipboard
            self.clipboard_manager.set_content(content_text)

            # Show notification
            preset_name = (
                item.data.get("preset_name", preset_id) if item.data else preset_id
            )
            self.notification_manager.show_success_notification(
                "Settings Preset Copied", f"Copied preset '{preset_name}' to clipboard"
            )

            return ExecutionResult(
                success=True,
                content=content_text,
                execution_time=time.time() - start_time,
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Failed to execute settings preset: {str(e)}",
                execution_time=time.time() - start_time,
            )
