"""
Asynchronous prompt execution using QThread to prevent UI blocking.
"""

import time
import uuid
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from modules.prompts.async_execution import PromptExecutionWorker

try:
    from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
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

    class QTimer:
        @staticmethod
        def singleShot(interval, callback):
            pass

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
from core.placeholder_service import PlaceholderService
from core.context_manager import ContextManager
from modules.utils.notifications import PyQtNotificationManager, format_execution_time
from modules.utils.notification_config import is_notification_enabled

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """Context for tracking a specific execution."""

    execution_id: str
    worker: "PromptExecutionWorker"
    item: MenuItem
    context: Optional[str]
    start_time: float
    is_alternative: bool
    original_input: Optional[str]


class PromptExecutionWorker(QThread):
    """
    Worker thread for executing prompts asynchronously to prevent UI blocking.
    """

    # Signal for streaming chunks: (chunk, accumulated, is_final, execution_id)
    chunk_received = pyqtSignal(str, str, bool, str)

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
        notification_manager: PyQtNotificationManager,
        openai_service: OpenAiService,
        config,
        context_manager: ContextManager,
        execution_id: str = "",
    ):
        super().__init__()
        self.settings_prompt_provider = settings_prompt_provider
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager
        self.openai_service = openai_service
        self.config = config
        self.context_manager = context_manager
        self.placeholder_service = PlaceholderService(
            clipboard_manager, context_manager
        )
        self.execution_id = execution_id

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
            # Ensure error callback is called for early return so cleanup happens
            logger.warning(
                "Worker run() called with no item - triggering error callback"
            )
            if self.error_callback:
                self.error_callback(
                    "No item to execute", "Unknown", 0, self.execution_id
                )
            return

        self.start_time = time.time()
        prompt_name = (
            (self.item.data.get("prompt_name") if self.item.data else None)
            or self.item.label
            or "Unknown Prompt"
        )

        try:
            # Call started callback
            if self.started_callback:
                self.started_callback(prompt_name, self.execution_id)

            # Check if streaming is enabled via conversation_data
            use_streaming = False
            if self.item and self.item.data:
                conv_data = self.item.data.get("conversation_data", {})
                use_streaming = conv_data.get("use_streaming", False)

            # Execute the prompt (streaming or sync)
            if use_streaming:
                result = self._execute_prompt_streaming()
            else:
                result = self._execute_prompt_sync()

            # Attach execution_id to result
            result.execution_id = self.execution_id
            execution_time = time.time() - self.start_time

            if result.success:
                if self.finished_callback:
                    self.finished_callback(
                        result, prompt_name, execution_time, self.execution_id
                    )
            else:
                if self.error_callback:
                    self.error_callback(
                        result.error or "Unknown error",
                        prompt_name,
                        execution_time,
                        self.execution_id,
                    )

        except Exception as e:
            execution_time = time.time() - self.start_time
            logger.error("Worker thread exception: %s", e, exc_info=True)
            if self.error_callback:
                self.error_callback(
                    str(e), prompt_name, execution_time, self.execution_id
                )

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

            # Check for multi-turn conversation data
            conversation_data = self.item.data.get("conversation_data")

            if conversation_data:
                # Multi-turn conversation mode
                processed_messages = self._build_conversation_messages(
                    prompt_id, messages, conversation_data
                )
            else:
                # Single-turn mode (original logic)
                processed_messages: List[ChatCompletionMessageParam] = []
                processed_messages = self.placeholder_service.process_messages(
                    messages, self.context
                )

                # Check for working_images in item.data (from MessageShareDialog)
                # These are temporary images not saved to persistent context
                working_images = self.item.data.get("working_images", [])
                if working_images and processed_messages:
                    # Add working images to the last message (user message)
                    last_message = processed_messages[-1]
                    last_content = last_message.get("content", "")

                    # Build content array with text and images
                    message_content = []

                    # Handle existing content (could be string or list)
                    if isinstance(last_content, str):
                        if last_content.strip():
                            message_content.append(
                                {"type": "text", "text": last_content}
                            )
                    elif isinstance(last_content, list):
                        message_content.extend(last_content)

                    # Add working images
                    for img in working_images:
                        img_data = img.get("data", "")
                        media_type = img.get("media_type", "image/png")
                        if img_data:
                            message_content.append(
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{media_type};base64,{img_data}"
                                    },
                                }
                            )

                    # Update the last message with combined content
                    if message_content:
                        processed_messages[-1] = {
                            "role": last_message.get("role", "user"),
                            "content": message_content,
                        }

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

    def _build_conversation_messages(
        self, prompt_id: str, base_messages: list, conversation_data: dict
    ) -> List[ChatCompletionMessageParam]:
        """Build messages from multi-turn conversation history."""
        processed = []

        # Start with system message from prompt
        for msg in base_messages:
            if msg.get("role") == "system":
                content = msg.get("content", "")
                # Process placeholders in system message
                if hasattr(self.placeholder_service, "_process_content"):
                    content = self.placeholder_service._process_content(
                        content, self.context
                    )
                processed.append({"role": "system", "content": content})
                break

        # Add conversation turns
        for turn in conversation_data.get("turns", []):
            role = turn.get("role")

            if role == "assistant":
                # Assistant response
                processed.append({"role": "assistant", "content": turn.get("text", "")})
            else:
                # User turn - build content with text and images
                content = []

                # Handle context (only in first turn)
                context_text = turn.get("context_text", "")
                text = turn.get("text", "")

                if context_text:
                    # First turn with context
                    content.append(
                        {
                            "type": "text",
                            "text": f"<context>\n{context_text}\n</context>\n\n{text}",
                        }
                    )
                elif text.strip():
                    content.append({"type": "text", "text": text})

                # Add context images (first turn only)
                for img in turn.get("context_images", []):
                    img_data = img.get("data", "")
                    media_type = img.get("media_type", "image/png")
                    if img_data:
                        content.append(
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{img_data}"
                                },
                            }
                        )

                # Add message images
                for img in turn.get("images", []):
                    img_data = img.get("data", "")
                    media_type = img.get("media_type", "image/png")
                    if img_data:
                        content.append(
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{img_data}"
                                },
                            }
                        )

                if content:
                    processed.append({"role": "user", "content": content})

        return processed

    def _execute_prompt_streaming(self) -> ExecutionResult:
        """Execute the prompt with streaming (runs in worker thread)."""
        start_time = time.time()

        try:
            if not self.item or not self.item.data:
                return ExecutionResult(
                    success=False,
                    error="Invalid menu item",
                    execution_time=time.time() - start_time,
                    metadata={"action": "execute_prompt", "streaming": True},
                )

            prompt_id = self.item.data.get("prompt_id")
            if not prompt_id:
                return ExecutionResult(
                    success=False,
                    error="Missing prompt ID",
                    execution_time=time.time() - start_time,
                    metadata={"action": "execute_prompt", "streaming": True},
                )

            # Get model from MenuItem.data.model
            model_name = self.item.data.get("model")
            if not model_name:
                model_name = self.config.default_model

            if not model_name or not isinstance(model_name, str):
                return ExecutionResult(
                    success=False,
                    error="No valid model specified",
                    execution_time=time.time() - start_time,
                    metadata={"action": "execute_prompt", "streaming": True},
                )

            if not self.openai_service.has_model(model_name):
                return ExecutionResult(
                    success=False,
                    error=f"Model '{model_name}' not found in configuration",
                    execution_time=time.time() - start_time,
                    metadata={"action": "execute_prompt", "streaming": True},
                )

            messages = self.settings_prompt_provider.get_prompt_messages(prompt_id)
            if not messages:
                return ExecutionResult(
                    success=False,
                    error=f"Prompt '{prompt_id}' not found",
                    execution_time=time.time() - start_time,
                    metadata={"action": "execute_prompt", "streaming": True},
                )

            # Check for multi-turn conversation data
            conversation_data = self.item.data.get("conversation_data")

            if conversation_data:
                processed_messages = self._build_conversation_messages(
                    prompt_id, messages, conversation_data
                )
            else:
                processed_messages: List[ChatCompletionMessageParam] = []
                processed_messages = self.placeholder_service.process_messages(
                    messages, self.context
                )

            if not processed_messages:
                return ExecutionResult(
                    success=False,
                    error="No valid messages found after processing",
                    execution_time=time.time() - start_time,
                    metadata={"action": "execute_prompt", "streaming": True},
                )

            # Stream response using complete_stream
            accumulated = ""
            for chunk_text, accumulated in self.openai_service.complete_stream(
                model_key=model_name,
                messages=processed_messages,
            ):
                # Emit chunk signal (Qt handles thread safety)
                self.chunk_received.emit(
                    chunk_text, accumulated, False, self.execution_id
                )

            # Emit final signal
            self.chunk_received.emit("", accumulated, True, self.execution_id)

            return ExecutionResult(
                success=True,
                content=accumulated,
                execution_time=time.time() - start_time,
                metadata={"action": "execute_prompt", "streaming": True},
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Streaming execution failed: {str(e)}",
                execution_time=time.time() - start_time,
                metadata={"action": "execute_prompt", "streaming": True},
            )


class AsyncPromptExecutionManager:
    """
    Manager for asynchronous prompt execution that keeps the UI responsive.
    Supports multiple concurrent executions with execution_id tracking.
    """

    def __init__(
        self,
        settings_prompt_provider,
        clipboard_manager: ClipboardManager,
        notification_manager: Optional[PyQtNotificationManager],
        openai_service: OpenAiService,
        config,
        context_manager: ContextManager,
        prompt_store_service=None,
    ):
        self.settings_prompt_provider = settings_prompt_provider
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager or PyQtNotificationManager()
        self.openai_service = openai_service
        self.config = config
        self.prompt_store_service = prompt_store_service
        self.context_manager = context_manager
        self.placeholder_service = PlaceholderService(
            clipboard_manager, context_manager
        )

        # Multi-execution tracking
        self._active_executions: Dict[str, ExecutionContext] = {}

        # Legacy single-execution tracking (for backwards compatibility)
        self.worker: Optional[PromptExecutionWorker] = None
        self.is_executing = False
        self.current_item: Optional[MenuItem] = None
        self.current_context: Optional[str] = None
        self.is_alternative_execution: bool = False
        self.original_input_content: Optional[str] = None
        logger.info(
            "AsyncPromptExecutionManager initialized - is_executing=False, worker=None"
        )

    def is_busy(self) -> bool:
        """Check if any execution is currently in progress."""
        has_active = bool(self._active_executions) or self.is_executing
        if has_active:
            logger.warning(
                f"is_busy() returning True - is_executing={self.is_executing}, "
                f"active_executions={len(self._active_executions)}, "
                f"worker={self.worker is not None}, "
                f"worker_running={self.is_worker_still_running()}"
            )
        return has_active

    def has_execution(self, execution_id: str) -> bool:
        """Check if a specific execution is active."""
        return execution_id in self._active_executions

    def execute_prompt_async(
        self, item: MenuItem, context: Optional[str] = None
    ) -> Optional[str]:
        """
        Execute a prompt asynchronously.

        Returns:
            execution_id if execution started, None if failed
        """
        # Generate unique execution ID
        execution_id = str(uuid.uuid4())

        logger.info(
            f"execute_prompt_async called - item={item.id if item else None}, "
            f"execution_id={execution_id}, active_executions={len(self._active_executions)}"
        )

        # Create and start worker thread with execution_id
        worker = PromptExecutionWorker(
            self.settings_prompt_provider,
            self.clipboard_manager,
            self.notification_manager,
            self.openai_service,
            self.config,
            self.context_manager,
            execution_id=execution_id,
        )

        # Set callbacks for cross-thread communication
        worker.set_callbacks(
            self._on_execution_started,
            self._on_execution_finished,
            self._on_execution_error,
        )

        # Connect streaming chunk signal to route through menu coordinator
        if self.prompt_store_service and hasattr(
            self.prompt_store_service, "_menu_coordinator"
        ):
            worker.chunk_received.connect(self._on_chunk_received, Qt.QueuedConnection)

        # Determine if this is alternative execution
        is_alternative = bool(
            item.data and item.data.get("alternative_execution", False)
        )

        # Capture the original input content before execution starts
        if is_alternative:
            original_input = context if context is not None else ""
        elif context is not None:
            original_input = context
        else:
            try:
                original_input = self.clipboard_manager.get_content()
            except Exception:
                original_input = ""

        # Create execution context and store it
        exec_context = ExecutionContext(
            execution_id=execution_id,
            worker=worker,
            item=item,
            context=context,
            start_time=time.time(),
            is_alternative=is_alternative,
            original_input=original_input,
        )
        self._active_executions[execution_id] = exec_context

        # Legacy single-execution tracking (for backwards compatibility)
        self.worker = worker
        self.current_item = item
        self.current_context = context
        self.is_alternative_execution = is_alternative
        self.original_input_content = original_input
        self.is_executing = True

        # Set parameters and start
        worker.set_execution_params(item, context)
        worker.start()

        # Emit execution started signal for global awareness
        if self.prompt_store_service:
            self.prompt_store_service.emit_execution_started(execution_id)

        return execution_id

    def _on_execution_started(self, prompt_name: str, execution_id: str = ""):
        """Handle execution started signal."""
        self.is_executing = True

    def _on_chunk_received(
        self, chunk: str, accumulated: str, is_final: bool, execution_id: str = ""
    ):
        """Route streaming chunk signal to menu coordinator."""
        if self.prompt_store_service and hasattr(
            self.prompt_store_service, "_menu_coordinator"
        ):
            self.prompt_store_service._menu_coordinator.streaming_chunk.emit(
                chunk, accumulated, is_final, execution_id
            )

    def _on_execution_finished(
        self,
        result: ExecutionResult,
        prompt_name: str,
        execution_time: float,
        execution_id: str = "",
    ):
        """Handle successful execution completion."""
        # Look up execution context
        exec_context = (
            self._active_executions.get(execution_id) if execution_id else None
        )
        current_item = exec_context.item if exec_context else self.current_item
        original_input = (
            exec_context.original_input if exec_context else self.original_input_content
        )
        worker = exec_context.worker if exec_context else self.worker

        try:
            # Copy response to clipboard (unless explicitly skipped)
            skip_clipboard = (
                current_item
                and current_item.data
                and current_item.data.get("skip_clipboard_copy", False)
            )
            if result.content and not skip_clipboard:
                self.clipboard_manager.set_content(result.content)

            # Add to history using prompt store service which has proper logic
            if self.prompt_store_service and current_item:
                input_content = original_input or ""
                self.prompt_store_service.add_history_entry(
                    current_item, input_content, result
                )

            # Get model configuration for display name
            model_config = None
            if worker and hasattr(worker, "item") and worker.item and worker.item.data:
                model_name = worker.item.data.get("model") or self.config.default_model
                if model_name:
                    try:
                        model_config = self.openai_service.get_model_config(model_name)
                    except Exception:
                        pass

            # Show success notification
            if is_notification_enabled("prompt_execution_success"):
                model_display = model_config["display_name"] if model_config else "AI"
                notification_message = f"{model_display} processed in {format_execution_time(execution_time)}".strip()
                self.notification_manager.show_success_notification(
                    f"{prompt_name} completed", notification_message
                )

            # Emit execution completed signal for GUI updates
            if self.prompt_store_service:
                self.prompt_store_service.emit_execution_completed(result, execution_id)

        except Exception as e:
            logger.error("Error in _on_execution_finished: %s", e, exc_info=True)
            self.notification_manager.show_error_notification(
                "Execution completed with warning",
                f"Response generated but failed to copy to clipboard: {str(e)}",
            )
            if self.prompt_store_service:
                error_result = ExecutionResult(
                    success=False,
                    error=f"Post-execution error: {str(e)}",
                    metadata={"action": "execute_prompt"},
                    execution_id=execution_id,
                )
                self.prompt_store_service.emit_execution_completed(
                    error_result, execution_id
                )
        finally:
            self._cleanup_execution(execution_id)

    def _on_execution_error(
        self,
        error_message: str,
        prompt_name: str,
        execution_time: float,
        execution_id: str = "",
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
                execution_id=execution_id,
            )
            self.prompt_store_service.emit_execution_completed(
                error_result, execution_id
            )

        self._cleanup_execution(execution_id)

    def _cleanup_execution(self, execution_id: str = ""):
        """Clean up a specific execution by ID."""
        # Remove from active executions
        exec_context = (
            self._active_executions.pop(execution_id, None) if execution_id else None
        )
        worker = exec_context.worker if exec_context else self.worker

        # Reset legacy state if no more active executions
        if not self._active_executions:
            self.is_executing = False
            self.current_item = None
            self.current_context = None
            self.is_alternative_execution = False
            self.original_input_content = None
            self.worker = None

        if worker:
            try:
                worker.set_callbacks(None, None, None)
            except Exception:
                pass

            if worker.isRunning():
                worker.quit()
                QTimer.singleShot(
                    100, lambda w=worker: self._finish_worker_cleanup_for(w)
                )
            else:
                worker.deleteLater()

    def _finish_worker_cleanup_for(self, worker: PromptExecutionWorker):
        """Complete worker cleanup after thread has had time to quit."""
        if worker:
            if worker.isRunning():
                worker.terminate()
                QTimer.singleShot(
                    50, lambda w=worker: self._force_worker_cleanup_for(w)
                )
            else:
                worker.deleteLater()

    def _force_worker_cleanup_for(self, worker: PromptExecutionWorker):
        """Force cleanup of worker thread."""
        if worker:
            worker.deleteLater()

    def stop_execution(
        self, execution_id: Optional[str] = None, silent: bool = False
    ) -> bool:
        """Stop specific execution by ID, or all if None.

        Args:
            execution_id: Specific execution to stop, or None for all
            silent: If True, skip notification and signal emission (caller handles UI)
        """
        if execution_id:
            return self._stop_specific_execution(execution_id, silent)

        # Stop all executions for backward compatibility
        stopped_any = False
        for eid in list(self._active_executions.keys()):
            if self._stop_specific_execution(eid, silent):
                stopped_any = True
        return stopped_any

    def _stop_specific_execution(self, execution_id: str, silent: bool = False) -> bool:
        """Stop and clean up a specific execution."""
        exec_context = self._active_executions.get(execution_id)
        if not exec_context:
            return False

        cancelled_item = exec_context.item
        worker = exec_context.worker

        # Remove from active executions
        self._active_executions.pop(execution_id, None)

        # Reset legacy state if this was the current execution
        if not self._active_executions:
            self.is_executing = False
            self.current_item = None
            self.current_context = None
            self.is_alternative_execution = False
            self.original_input_content = None
            self.worker = None

        # Stop the worker
        if worker and worker.isRunning():
            worker.quit()
            QTimer.singleShot(100, lambda w=worker: self._cleanup_worker_for(w))

        # Skip notification and signal if silent mode (caller handles UI)
        if silent:
            return True

        # Show notification and emit signal
        prompt_name = "Prompt"
        if cancelled_item and cancelled_item.data:
            prompt_name = cancelled_item.data.get("prompt_name", "Prompt")

        if is_notification_enabled("prompt_execution_cancel"):
            self.notification_manager.show_warning_notification(
                f"{prompt_name} cancelled"
            )

        if self.prompt_store_service:
            cancel_result = ExecutionResult(
                success=True,
                content="",
                metadata={"action": "execution_cancelled"},
                execution_id=execution_id,
            )
            self.prompt_store_service.emit_execution_completed(
                cancel_result, execution_id
            )

        return True

    def _cleanup_worker_for(self, worker: PromptExecutionWorker):
        """Clean up worker thread resources (non-blocking)."""
        if not worker:
            return
        try:
            worker.set_callbacks(None, None, None)
        except Exception:
            pass
        if worker.isRunning():
            worker.quit()
            QTimer.singleShot(500, lambda w=worker: self._force_terminate_worker(w))
        else:
            worker.deleteLater()

    def _force_terminate_worker(self, worker: PromptExecutionWorker):
        """Force terminate worker if still running after timeout."""
        if not worker:
            return
        if worker.isRunning():
            worker.terminate()
            QTimer.singleShot(100, lambda w=worker: w.deleteLater() if w else None)
        else:
            worker.deleteLater()

    def force_reset_state(self):
        """Force reset execution state - use when stuck."""
        if self.is_executing:
            self.stop_execution()

    def is_worker_still_running(self) -> bool:
        """Check if any worker thread is actually still running."""
        if self.worker is not None and self.worker.isRunning():
            return True
        for exec_context in self._active_executions.values():
            if exec_context.worker and exec_context.worker.isRunning():
                return True
        return False

    def get_execution_status(self) -> dict:
        """Get detailed execution status for debugging."""
        return {
            "is_executing": self.is_executing,
            "has_worker": self.worker is not None,
            "worker_running": self.is_worker_still_running(),
            "current_item": self.current_item.id if self.current_item else None,
            "is_alternative": self.is_alternative_execution,
        }
