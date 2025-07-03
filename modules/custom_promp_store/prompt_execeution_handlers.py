from typing import Optional, Callable, List
import logging
from core.interfaces import ClipboardManager
from core.models import MenuItem, MenuItemType, ExecutionResult, ErrorCode
from core.exceptions import ClipboardError
from api import PromptStoreAPI, APIError, create_user_message
from modules.utils.speech_to_text import SpeechToTextService
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from modules.utils.notifications import (
    PyQtNotificationManager,
    format_execution_time,
    truncate_text,
)
import time


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
