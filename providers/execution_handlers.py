"""Execution handlers for different types of menu items."""

from typing import Optional
import logging
from PyQt5.QtWidgets import QApplication
from core.interfaces import ClipboardManager
from core.models import MenuItem, MenuItemType, ExecutionResult, ErrorCode
from core.exceptions import ClipboardError
from api import PromptStoreAPI, APIError, create_user_message
from utils.pyqt_notifications import (
    PyQtNotificationManager,
    format_execution_time,
    truncate_text,
)
import time

logger = logging.getLogger(__name__)


class PromptExecutionHandler:
    """Handler for executing prompt menu items."""

    def __init__(
        self,
        api: PromptStoreAPI,
        clipboard_manager: ClipboardManager,
        app: Optional[QApplication] = None,
    ):
        self.api = api
        self.clipboard_manager = clipboard_manager
        self.notification_manager = PyQtNotificationManager(app)

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can execute the given menu item."""
        return item.item_type == MenuItemType.PROMPT

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

            result = self.api.execute_prompt(prompt_id, [user_message])
            content = result.get("content", "No response content")
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

            result = ExecutionResult(
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

            message = f"Processed in {format_execution_time(execution_time)}"
            self.notification_manager.show_success_notification(
                "Prompt Completed", message, prompt_name
            )

            return result

        except APIError as e:
            error_msg = f"Failed to execute prompt: {str(e)}"
            execution_time = time.time() - start_time
            logger.error(
                f"API error executing prompt {prompt_name} (ID: {prompt_id}): {str(e)} (execution time: {execution_time:.2f}s)"
            )

            result = ExecutionResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.API_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification(
                "Prompt Failed", truncate_text(str(e)), prompt_name
            )

            return result
        except ClipboardError as e:
            error_msg = str(e)
            execution_time = time.time() - start_time
            logger.error(
                f"Clipboard error executing prompt {prompt_name} (ID: {prompt_id}): {error_msg} (execution time: {execution_time:.2f}s)"
            )

            result = ExecutionResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.CLIPBOARD_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification(
                "Clipboard Error", truncate_text(error_msg), prompt_name
            )

            return result
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            execution_time = time.time() - start_time
            logger.exception(
                f"Unexpected error executing prompt {prompt_name} (ID: {prompt_id}): {str(e)} (execution time: {execution_time:.2f}s)"
            )

            result = ExecutionResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.UNKNOWN_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification(
                "Execution Error", truncate_text(str(e)), prompt_name
            )

            return result


class PresetExecutionHandler:
    """Handler for executing preset menu items."""

    def __init__(
        self,
        api: PromptStoreAPI,
        clipboard_manager: ClipboardManager,
        app: Optional[QApplication] = None,
    ):
        self.api = api
        self.clipboard_manager = clipboard_manager
        self.notification_manager = PyQtNotificationManager(app)

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can execute the given menu item."""
        return item.item_type == MenuItemType.PRESET

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
            f"Starting preset execution: {preset_name} (Preset ID: {preset_id}, Prompt ID: {prompt_id})"
        )

        try:
            if (
                not item.data
                or not item.data.get("preset_id")
                or not item.data.get("prompt_id")
            ):
                logger.error(f"Invalid preset data for item: {item}")
                return ExecutionResult(
                    success=False,
                    error="Invalid preset data",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

            preset_id = item.data["preset_id"]
            prompt_id = item.data["prompt_id"]

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
                f"Executing preset {preset_id} with prompt {prompt_id}, input length: {len(clipboard_content)}"
            )

            result = self.api.execute_prompt_with_preset(
                prompt_id, preset_id, [user_message], context
            )
            content = result.get("content", "No response content")
            logger.debug(f"API response received (length: {len(content)})")

            if not self.clipboard_manager.set_content(content):
                return ExecutionResult(
                    success=False,
                    error=f"Preset executed but failed to copy result to clipboard.\n\nResult:\n{content}",
                    error_code=ErrorCode.CLIPBOARD_ERROR,
                )

            execution_time = time.time() - start_time
            logger.info(
                f"Preset execution successful: {preset_name} (Preset ID: {preset_id}, Prompt ID: {prompt_id}) - input: {len(clipboard_content)} chars, output: {len(content)} chars, time: {execution_time:.2f}s"
            )

            result = ExecutionResult(
                success=True,
                content=content,
                execution_time=execution_time,
                metadata={
                    "preset_id": preset_id,
                    "preset_name": item.data.get("preset_name"),
                    "prompt_id": prompt_id,
                    "input_length": len(clipboard_content),
                    "output_length": len(content),
                },
            )

            message = f"Processed in {format_execution_time(execution_time)}"
            self.notification_manager.show_success_notification(
                "Preset Completed", message, preset_name
            )

            return result

        except APIError as e:
            error_msg = f"Failed to execute preset: {str(e)}"
            execution_time = time.time() - start_time
            logger.error(
                f"API error executing preset {preset_name} (Preset ID: {preset_id}, Prompt ID: {prompt_id}): {str(e)} (execution time: {execution_time:.2f}s)"
            )

            result = ExecutionResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.API_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification(
                "Preset Failed", truncate_text(str(e)), preset_name
            )

            return result
        except ClipboardError as e:
            error_msg = str(e)
            execution_time = time.time() - start_time
            logger.error(
                f"Clipboard error executing preset {preset_name} (Preset ID: {preset_id}, Prompt ID: {prompt_id}): {error_msg} (execution time: {execution_time:.2f}s)"
            )

            result = ExecutionResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.CLIPBOARD_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification(
                "Clipboard Error", truncate_text(error_msg), preset_name
            )

            return result
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            execution_time = time.time() - start_time
            logger.exception(
                f"Unexpected error executing preset {preset_name} (Preset ID: {preset_id}, Prompt ID: {prompt_id}): {str(e)} (execution time: {execution_time:.2f}s)"
            )

            result = ExecutionResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.UNKNOWN_ERROR,
                execution_time=execution_time,
            )

            self.notification_manager.show_error_notification(
                "Execution Error", truncate_text(str(e)), preset_name
            )

            return result


class HistoryExecutionHandler:
    """Handler for executing history menu items."""

    def __init__(self, clipboard_manager: ClipboardManager):
        self.clipboard_manager = clipboard_manager

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can execute the given menu item."""
        return item.item_type == MenuItemType.HISTORY

    def execute(self, item: MenuItem, context: Optional[str] = None) -> ExecutionResult:
        """Execute a history menu item."""
        start_time = time.time()

        try:
            if (
                not item.data
                or not item.data.get("type")
                or not item.data.get("content")
            ):
                return ExecutionResult(
                    success=False,
                    error="Invalid history data or no content available",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

            content = item.data["content"]
            history_type = item.data["type"]

            if not self.clipboard_manager.set_content(content):
                return ExecutionResult(
                    success=False,
                    error=f"Failed to copy {history_type} to clipboard",
                    error_code=ErrorCode.CLIPBOARD_ERROR,
                )

            execution_time = time.time() - start_time
            return ExecutionResult(
                success=True,
                content=content,
                execution_time=execution_time,
                metadata={"history_type": history_type, "content_length": len(content)},
            )

        except ClipboardError as e:
            return ExecutionResult(
                success=False,
                error=str(e),
                error_code=ErrorCode.CLIPBOARD_ERROR,
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR,
                execution_time=time.time() - start_time,
            )


class SystemExecutionHandler:
    """Handler for executing system menu items."""

    def __init__(self, refresh_callback=None, app: Optional[QApplication] = None):
        self.refresh_callback = refresh_callback
        self.notification_manager = PyQtNotificationManager(app)

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can execute the given menu item."""
        return item.item_type == MenuItemType.SYSTEM

    def execute(self, item: MenuItem, context: Optional[str] = None) -> ExecutionResult:
        """Execute a system menu item."""
        start_time = time.time()

        try:
            if not item.data or not item.data.get("type"):
                return ExecutionResult(
                    success=False,
                    error="Invalid system command",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

            command_type = item.data["type"]

            if command_type == "refresh":
                if self.refresh_callback:
                    self.refresh_callback()

                execution_time = time.time() - start_time
                result = ExecutionResult(
                    success=True,
                    content="Data refreshed",
                    execution_time=execution_time,
                    metadata={"command": "refresh"},
                )

                self.notification_manager.show_info_notification(
                    "Data Refreshed",
                    f"Completed in {format_execution_time(execution_time)}",
                )

                return result
            else:
                return ExecutionResult(
                    success=False,
                    error=f"Unknown system command: {command_type}",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"System command failed: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR,
                execution_time=time.time() - start_time,
            )