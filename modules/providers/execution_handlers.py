"""PyQt5-specific execution handlers that accept shared notification manager."""

from typing import Optional, Callable, List
import logging
from core.interfaces import ClipboardManager
from core.models import MenuItem, MenuItemType, ExecutionResult, ErrorCode
from modules.utils.config import AppConfig
from modules.utils.speech_to_text import SpeechToTextService
from open_ai_api import OpenAIClient
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from modules.utils.notifications import (
    PyQtNotificationManager,
    format_execution_time,
    truncate_text,
)
import time

logger = logging.getLogger(__name__)


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


class PyQtSpeechExecutionHandler:
    """PyQt5 handler for executing speech-to-text menu items."""

    def __init__(
        self,
        clipboard_manager: ClipboardManager,
        notification_manager: Optional[PyQtNotificationManager] = None,
        recording_indicator_callback: Optional[Callable[[bool], None]] = None,
        speech_history_service=None,
        ui_refresh_callback: Optional[Callable[[], None]] = None,
        speech_service=SpeechToTextService,
    ):
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager or PyQtNotificationManager()
        self.recording_indicator_callback = recording_indicator_callback
        self.speech_history_service = speech_history_service
        self.ui_refresh_callback = ui_refresh_callback
        self.speech_service = speech_service
        self._transcription_start_time: Optional[float] = None
        self._setup_speech_callbacks()

    def _setup_speech_callbacks(self) -> None:
        """Setup callbacks for the speech service."""
        if self.speech_service:
            self.speech_service.set_recording_started_callback(
                self._on_recording_started
            )
            self.speech_service.set_recording_stopped_callback(
                self._on_recording_stopped
            )
            self.speech_service.add_transcription_callback(
                self._on_transcription_complete, handler_name=self.__class__.__name__
            )
            self.speech_service.set_error_callback(self._on_speech_error)

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
            self.speech_service.toggle_recording(self.__class__.__name__)

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

    def _on_transcription_complete(self, transcription: str, _duration: float) -> None:
        """Handle transcription completion."""
        try:
            if transcription:
                # Store transcription in speech history
                if self.speech_history_service:
                    self.speech_history_service.add_transcription(transcription)

                success = self.clipboard_manager.set_content(transcription)
                if not success:
                    self.notification_manager.show_error_notification(
                        "Clipboard Error",
                        "Transcription successful but failed to copy to clipboard",
                    )
                    return

                # Trigger UI refresh to show "Copy last speech" item
                if self.ui_refresh_callback:
                    self.ui_refresh_callback()
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
        notification_manager: Optional[PyQtNotificationManager],
        config: AppConfig,
    ):
        self.settings_prompt_provider = settings_prompt_provider
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager or PyQtNotificationManager()
        self.config = config

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can execute the given menu item."""
        if item.item_type != MenuItemType.PROMPT:
            return False
        if item.data is None:
            return False

        source = item.data.get("source")
        # Only handle items that explicitly have "settings" source
        return source == "settings"

    def execute(self, item: MenuItem, context: Optional[str] = None) -> ExecutionResult:
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

            print(item.data)
            # Get model from MenuItem.data.model
            model_name = item.data.get("model") if item.data else None

            # Use default model if not specified
            if not model_name:
                model_name = self.config.default_model

            # Validate model exists in config
            if not self.config.models or model_name not in self.config.models:
                return ExecutionResult(
                    success=False,
                    error=f"Model '{model_name}' not found in configuration",
                    execution_time=time.time() - start_time,
                )

            # Get model configuration
            model_config = self.config.models[model_name]

            # Create OpenAI client with model configuration
            openai_client = OpenAIClient(
                api_key=model_config["api_key"], base_url=model_config.get("base_url")
            )

            messages = self.settings_prompt_provider.get_prompt_messages(prompt_id)
            if not messages:
                return ExecutionResult(
                    success=False,
                    error=f"Prompt '{prompt_id}' not found",
                    execution_time=time.time() - start_time,
                )

            if context:
                clipboard_content = context
            else:
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
            response_text = openai_client.complete(
                messages=processed_messages,
                model=model_config["model"],
                temperature=model_config.get("temperature"),
            )

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

        except Exception as e:
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
