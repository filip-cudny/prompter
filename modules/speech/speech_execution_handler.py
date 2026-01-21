"""PyQt5-specific execution handlers that accept shared notification manager."""

import logging
import time

from core.interfaces import ClipboardManager
from core.models import (
    ErrorCode,
    ExecutionResult,
    HistoryEntryType,
    MenuItem,
    MenuItemType,
)
from modules.gui.menu_coordinator import PyQtMenuCoordinator
from modules.utils.notification_config import is_notification_enabled
from modules.utils.notifications import (
    PyQtNotificationManager,
    truncate_text,
)
from modules.utils.speech_to_text import SpeechToTextService

logger = logging.getLogger(__name__)


class PyQtSpeechExecutionHandler:
    """PyQt5 handler for executing speech-to-text menu items."""

    def __init__(
        self,
        clipboard_manager: ClipboardManager,
        notification_manager: PyQtNotificationManager | None = None,
        history_service=None,
        speech_service=SpeechToTextService,
        menu_coordinator=PyQtMenuCoordinator,
    ):
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager or PyQtNotificationManager()
        self.history_service = history_service
        self.speech_service = speech_service
        self._transcription_start_time: float | None = None
        self.menu_coordinator = menu_coordinator
        self._setup_speech_callbacks()

    def _setup_speech_callbacks(self) -> None:
        """Setup callbacks for the speech service."""
        if self.speech_service:
            self.speech_service.add_transcription_callback(
                self._on_transcription_complete, handler_name=self.__class__.__name__
            )
            self.speech_service.set_error_callback(self._on_speech_error)

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can execute the given menu item."""
        return item.item_type == MenuItemType.SPEECH

    def execute(self, item: MenuItem, context: str | None = None) -> ExecutionResult:
        """Execute a speech-to-text menu item."""
        start_time = time.time()

        try:
            # Handle speech history items
            if item.data and item.data.get("type") == "last_speech_output":
                return self._handle_speech_history_item(item, start_time)

            # Handle speech-to-text recording
            if not self.speech_service:
                error_msg = (
                    "Speech-to-text service not available. Please configure OPENAI_API_KEY and install sounddevice."
                )

                self.notification_manager.show_error_notification("Speech-to-Text Error", error_msg)

                return ExecutionResult(
                    success=False,
                    error=error_msg,
                    error_code=ErrorCode.API_ERROR,
                    execution_time=time.time() - start_time,
                )

            # Toggle recording
            self.speech_service.toggle_recording(self.__class__.__name__)

            action = "speech_recording_started" if self.speech_service.is_recording() else "speech_recording_stopped"
            return ExecutionResult(
                success=True,
                content="Speech recording toggled",
                execution_time=time.time() - start_time,
                metadata={"action": action},
            )

        except Exception as e:
            execution_time = time.time() - start_time

            # Provide more specific error messages
            error_msg = str(e)
            if "sounddevice" in error_msg:
                error_msg = "sounddevice is not installed. Please install it with: pip install sounddevice"
            elif "OpenAI" in error_msg:
                error_msg = "OpenAI API key not configured. Please set OPENAI_API_KEY environment variable."

            execution_result = ExecutionResult(
                success=False,
                error=f"Speech action failed: {error_msg}",
                error_code=ErrorCode.UNKNOWN_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification("Speech Error", truncate_text(error_msg))

            return execution_result

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

                # self.refresh_ui()
                success = self.clipboard_manager.set_content(transcription)
                self.menu_coordinator.execution_completed.emit(
                    ExecutionResult(
                        success=True,
                        content=transcription,
                        metadata={"action": "speech_recording_stopped"},
                    ),
                    "",
                )
                if not success:
                    self.notification_manager.show_error_notification(
                        "Clipboard Error",
                        "Transcription successful but failed to copy to clipboard",
                    )
                    return

        except Exception as e:
            self.notification_manager.show_error_notification(
                "Transcription Error", f"Failed to process transcription: {str(e)}"
            )

    def _handle_speech_history_item(self, item: MenuItem, start_time: float) -> ExecutionResult:
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

            if success and is_notification_enabled("speech_transcription_success"):
                self.notification_manager.show_success_notification("Copied")

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
