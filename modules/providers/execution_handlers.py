"""PyQt5-specific execution handlers that accept shared notification manager."""

from typing import Optional, Callable
import logging
from core.interfaces import ClipboardManager
from core.models import (
    MenuItem,
    MenuItemType,
    ExecutionResult,
    ErrorCode,
    HistoryEntryType,
)
from modules.utils.speech_to_text import SpeechToTextService
from modules.utils.notifications import (
    PyQtNotificationManager,
    truncate_text,
)
import time

logger = logging.getLogger(__name__)


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
        history_service=None,
        ui_refresh_callback: Optional[Callable[[], None]] = None,
        speech_service=SpeechToTextService,
    ):
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager or PyQtNotificationManager()
        self.history_service = history_service
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

    def _on_recording_stopped(self) -> None:
        """Handle recording stopped event."""
        self._transcription_start_time = time.time()
        self.notification_manager.show_info_notification(
            "Processing Audio", "Transcribing your speech to text"
        )

    def _on_transcription_complete(self, transcription: str, _duration: float) -> None:
        """Handle transcription completion."""
        try:
            if transcription:
                if self.history_service:
                    self.history_service.add_entry(
                        input_content=transcription,
                        entry_type=HistoryEntryType.SPEECH,
                        output_content=transcription,
                        success=True,
                    )

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
