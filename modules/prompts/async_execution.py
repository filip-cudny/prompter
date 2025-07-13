"""
Asynchronous prompt execution using QThread to prevent UI blocking.
"""

import time
import logging
from typing import Optional, List

try:
    from PyQt5.QtCore import QThread, pyqtSignal, Qt
except ImportError:
    # Fallback for environments where PyQt5 is not available
    class QThread:
        def __init__(self, parent=None):
            pass

        def start(self):
            pass

        def quit(self):
            pass

        def wait(self):
            pass

        def deleteLater(self):
            pass

        def isRunning(self):
            return False

    def pyqtSignal(*args):
        return None

    class Qt:
        QueuedConnection = None


try:
    from openai.types.chat.chat_completion_message_param import (
        ChatCompletionMessageParam,
    )
except ImportError:
    # Fallback type hint
    ChatCompletionMessageParam = dict

from core.models import ExecutionResult, MenuItem
from core.openai_service import OpenAiService
from core.interfaces import ClipboardManager
from modules.utils.notifications import PyQtNotificationManager, format_execution_time

logger = logging.getLogger(__name__)


class PromptExecutionWorker(QThread):
    """
    Worker thread for executing prompts asynchronously to prevent UI blocking.
    """

    # Callbacks for cross-thread communication
    def set_callbacks(self, started_callback, finished_callback, error_callback):
        """Set callbacks for execution events."""
        self.started_callback = started_callback
        self.finished_callback = finished_callback
        self.error_callback = error_callback

    def __init__(
        self,
        settings_prompt_provider,
        clipboard_manager: ClipboardManager,
        notification_manager: Optional[PyQtNotificationManager],
        openai_service: OpenAiService,
        config,
        parent=None,
    ):
        super().__init__(parent)
        self.settings_prompt_provider = settings_prompt_provider
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager
        self.openai_service = openai_service
        self.config = config

        # Callbacks for cross-thread communication
        self.started_callback = None
        self.finished_callback = None
        self.error_callback = None

        # Execution parameters (set before starting thread)
        self.item: Optional[MenuItem] = None
        self.context: Optional[str] = None
        self.start_time: float = 0

    def set_execution_params(self, item: MenuItem, context: Optional[str] = None):
        """Set the parameters for the next execution."""
        self.item = item
        self.context = context

    def run(self):
        """Execute the prompt in the worker thread."""
        if not self.item:
            return

        self.start_time = time.time()
        prompt_name = self.item.label or "Unknown Prompt"

        try:
            # Call started callback
            if self.started_callback:
                self.started_callback(prompt_name)

            # Execute the prompt
            result = self._execute_prompt_sync()
            execution_time = time.time() - self.start_time

            if result.success:
                if self.finished_callback:
                    self.finished_callback(result, prompt_name, execution_time)
            else:
                if self.error_callback:
                    self.error_callback(
                        result.error or "Unknown error", prompt_name, execution_time
                    )

        except Exception as e:
            execution_time = time.time() - self.start_time
            logger.error("Worker thread exception: %s", e, exc_info=True)
            if self.error_callback:
                self.error_callback(str(e), prompt_name, execution_time)

    def _execute_prompt_sync(self) -> ExecutionResult:
        """Execute the prompt synchronously (runs in worker thread)."""
        start_time = time.time()

        try:
            if not self.item or not self.item.data:
                return ExecutionResult(
                    success=False,
                    error="Invalid menu item",
                    execution_time=time.time() - start_time,
                    metadata={"action": "execute_prompt"},
                )

            prompt_id = self.item.data.get("prompt_id")
            if not prompt_id:
                return ExecutionResult(
                    success=False,
                    error="Missing prompt ID",
                    execution_time=time.time() - start_time,
                    metadata={"action": "execute_prompt"},
                )

            # Get model from MenuItem.data.model
            model_name = self.item.data.get("model")

            # Use default model if not specified
            if not model_name:
                model_name = self.config.default_model

            # Ensure model_name is a string
            if not model_name or not isinstance(model_name, str):
                return ExecutionResult(
                    success=False,
                    error="No valid model specified",
                    execution_time=time.time() - start_time,
                    metadata={"action": "execute_prompt"},
                )

            # Validate model exists in openai service
            if not self.openai_service.has_model(model_name):
                return ExecutionResult(
                    success=False,
                    error=f"Model '{model_name}' not found in configuration",
                    execution_time=time.time() - start_time,
                    metadata={"action": "execute_prompt"},
                )

            messages = self.settings_prompt_provider.get_prompt_messages(prompt_id)
            if not messages:
                return ExecutionResult(
                    success=False,
                    error=f"Prompt '{prompt_id}' not found",
                    execution_time=time.time() - start_time,
                    metadata={"action": "execute_prompt"},
                )

            # Get clipboard content
            if self.context is not None:
                clipboard_content = self.context
            else:
                try:
                    clipboard_content = self.clipboard_manager.get_content()
                except Exception:
                    clipboard_content = ""

            # Process messages
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
                    metadata={"action": "execute_prompt"},
                )

            # Call OpenAI API (this is the blocking call that now runs in worker thread)
            response_text = self.openai_service.complete(
                model_key=model_name,
                messages=processed_messages,
            )

            return ExecutionResult(
                success=True,
                content=response_text,
                execution_time=time.time() - start_time,
                metadata={"action": "execute_prompt"},
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Failed to execute prompt: {str(e)}",
                execution_time=time.time() - start_time,
                metadata={"action": "execute_prompt"},
            )


class AsyncPromptExecutionManager:
    """
    Manager for asynchronous prompt execution that keeps the UI responsive.
    """

    def __init__(
        self,
        settings_prompt_provider,
        clipboard_manager: ClipboardManager,
        notification_manager: Optional[PyQtNotificationManager],
        openai_service: OpenAiService,
        config,
        prompt_store_service=None,
    ):
        self.settings_prompt_provider = settings_prompt_provider
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager or PyQtNotificationManager()
        self.openai_service = openai_service
        self.config = config
        self.prompt_store_service = prompt_store_service

        self.worker: Optional[PromptExecutionWorker] = None
        self.is_executing = False
        self.current_item: Optional[MenuItem] = None
        self.current_context: Optional[str] = None
        self.is_alternative_execution: bool = False
        self.original_input_content: Optional[str] = None

    def is_busy(self) -> bool:
        """Check if execution is currently in progress."""
        return self.is_executing

    def execute_prompt_async(
        self, item: MenuItem, context: Optional[str] = None
    ) -> bool:
        """
        Execute a prompt asynchronously.

        Returns:
            True if execution started, False if already executing
        """
        if self.is_executing:
            return False

        # Create and start worker thread
        self.worker = PromptExecutionWorker(
            self.settings_prompt_provider,
            self.clipboard_manager,
            self.notification_manager,
            self.openai_service,
            self.config,
        )

        # Set callbacks for cross-thread communication
        self.worker.set_callbacks(
            self._on_execution_started,
            self._on_execution_finished,
            self._on_execution_error,
        )

        # Store current execution info for history tracking
        self.current_item = item
        self.current_context = context
        self.is_alternative_execution = bool(
            item.data and item.data.get("alternative_execution", False)
        )

        # Capture the original input content before execution starts
        if self.is_alternative_execution:
            # For alternative execution, the context contains the transcribed text which should be the input
            # Use context even if it's empty string - transcription might be legitimately empty
            self.original_input_content = context if context is not None else ""
        elif context is not None:
            # For regular execution with explicit context
            self.original_input_content = context
        else:
            # For regular execution, get current clipboard content as input
            try:
                self.original_input_content = self.clipboard_manager.get_content()
            except Exception:
                self.original_input_content = ""

        # Set parameters and start
        self.worker.set_execution_params(item, context)
        self.worker.start()

        self.is_executing = True
        return True

    def _on_execution_started(self, prompt_name: str):
        """Handle execution started signal."""
        self.is_executing = True

    def _on_execution_finished(
        self, result: ExecutionResult, prompt_name: str, execution_time: float
    ):
        """Handle successful execution completion."""
        try:
            # Copy response to clipboard
            if result.content:
                self.clipboard_manager.set_content(result.content)

            # Add to history using prompt store service which has proper logic
            if self.prompt_store_service and self.current_item:
                # Use the original input content that was captured before execution
                input_content = self.original_input_content or ""

                # For alternative execution, ensure the transcribed text is recorded as prompt input
                # This makes it available in "copy input" for prompts, not "copy output" for speech
                self.prompt_store_service.add_history_entry(
                    self.current_item, input_content, result
                )

            # Get model configuration for display name
            model_config = None
            if (
                self.worker
                and hasattr(self.worker, "item")
                and self.worker.item
                and self.worker.item.data
            ):
                model_name = (
                    self.worker.item.data.get("model") or self.config.default_model
                )
                if model_name:
                    try:
                        model_config = self.openai_service.get_model_config(model_name)
                    except Exception:
                        pass

            # Show success notification
            model_display = model_config["display_name"] if model_config else "AI"
            notification_message = f"{model_display} processed in {format_execution_time(execution_time)}".strip()

            self.notification_manager.show_success_notification(
                f"{prompt_name} completed", notification_message
            )

            # Emit execution completed signal for GUI updates
            if self.prompt_store_service:
                self.prompt_store_service.emit_execution_completed(result)

        except Exception as e:
            logger.error("Error in _on_execution_finished: %s", e, exc_info=True)
            # Fallback notification on clipboard error
            self.notification_manager.show_error_notification(
                "Execution completed with warning",
                f"Response generated but failed to copy to clipboard: {str(e)}",
            )
            # Still emit signal on error to ensure UI updates
            if self.prompt_store_service:
                error_result = ExecutionResult(
                    success=False,
                    error=f"Post-execution error: {str(e)}",
                    metadata={"action": "execute_prompt"},
                )
                self.prompt_store_service.emit_execution_completed(error_result)
        finally:
            self._cleanup_worker()

    def _on_execution_error(
        self, error_message: str, prompt_name: str, execution_time: float
    ):
        """Handle execution error."""
        self.notification_manager.show_error_notification(
            f"{prompt_name} failed", f"Error: {error_message}"
        )

        # Emit execution error signal for GUI updates
        if self.prompt_store_service:
            error_result = ExecutionResult(
                success=False,
                error=error_message,
                metadata={"action": "execute_prompt"},
            )
            self.prompt_store_service.emit_execution_completed(error_result)

        self._cleanup_worker()

    def _cleanup_worker(self):
        """Clean up the worker thread."""
        # Always ensure state is reset, regardless of how we got here
        self.is_executing = False
        self.current_item = None
        self.current_context = None
        self.is_alternative_execution = False
        self.original_input_content = None

        if self.worker:
            try:
                # Clear callbacks to prevent any race conditions
                self.worker.set_callbacks(None, None, None)
            except Exception:
                # Ignore callback clearing errors
                pass

            # Clean shutdown of worker thread
            if self.worker.isRunning():
                self.worker.quit()
                self.worker.wait()  # Wait for thread to finish

            self.worker.deleteLater()
            self.worker = None

    def stop_execution(self):
        """Stop any running execution."""
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()
        self._cleanup_worker()

    def force_reset_state(self):
        """Force reset execution state - use when stuck."""
        if self.is_executing:
            self.stop_execution()

    def is_worker_still_running(self) -> bool:
        """Check if worker thread is actually still running."""
        return self.worker is not None and self.worker.isRunning()

    def get_execution_status(self) -> dict:
        """Get detailed execution status for debugging."""
        return {
            "is_executing": self.is_executing,
            "has_worker": self.worker is not None,
            "worker_running": self.is_worker_still_running(),
            "current_item": self.current_item.id if self.current_item else None,
            "is_alternative": self.is_alternative_execution,
        }
