"""Execution handlers for different types of menu items."""

from typing import Optional
import tkinter as tk
from core.interfaces import ClipboardManager
from core.models import MenuItem, MenuItemType, ExecutionResult
from core.exceptions import ClipboardError
from api import PromptStoreAPI, APIError, create_user_message
from utils.notifications import NotificationManager, format_execution_time, truncate_text
import time


class PromptExecutionHandler:
    """Handler for executing prompt menu items."""

    def __init__(self, api: PromptStoreAPI, clipboard_manager: ClipboardManager, main_root: Optional[tk.Tk] = None):
        self.api = api
        self.clipboard_manager = clipboard_manager
        self.notification_manager = NotificationManager(main_root)

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can execute the given menu item."""
        return item.item_type == MenuItemType.PROMPT

    def execute(self, item: MenuItem, context: Optional[str] = None) -> ExecutionResult:
        """Execute a prompt menu item."""
        start_time = time.time()

        try:
            if not item.data or not item.data.get("prompt_id"):
                return ExecutionResult(
                    success=False,
                    error="Invalid prompt data"
                )

            prompt_id = item.data["prompt_id"]

            # Use provided context or fall back to clipboard
            if context is not None:
                clipboard_content = context
            else:
                if self.clipboard_manager.is_empty():
                    return ExecutionResult(
                        success=False,
                        error="Clipboard is empty"
                    )
                clipboard_content = self.clipboard_manager.get_content()

            user_message = create_user_message(clipboard_content)

            result = self.api.execute_prompt(prompt_id, [user_message])
            content = result.get("content", "No response content")

            if not self.clipboard_manager.set_content(content):
                return ExecutionResult(
                    success=False,
                    error=f"Prompt executed but failed to copy result to clipboard.\n\nResult:\n{
                        content}"
                )

            execution_time = time.time() - start_time
            result = ExecutionResult(
                success=True,
                content=content,
                execution_time=execution_time,
                metadata={
                    "prompt_id": prompt_id,
                    "prompt_name": item.data.get("prompt_name"),
                    "input_length": len(clipboard_content),
                    "output_length": len(content)
                }
            )
            
            prompt_name = item.data.get("prompt_name", "Unknown Prompt")
            message = f"Processed in {format_execution_time(execution_time)}"
            self.notification_manager.show_success_notification(
                "Prompt Completed", 
                message, 
                prompt_name
            )
            
            return result

        except APIError as e:
            error_msg = f"Failed to execute prompt: {str(e)}"
            result = ExecutionResult(
                success=False,
                error=error_msg,
                execution_time=time.time() - start_time
            )
            
            prompt_name = item.data.get("prompt_name", "Unknown Prompt") if item.data else "Unknown Prompt"
            self.notification_manager.show_error_notification(
                "Prompt Failed",
                truncate_text(str(e)),
                prompt_name
            )
            
            return result
        except ClipboardError as e:
            error_msg = str(e)
            result = ExecutionResult(
                success=False,
                error=error_msg,
                execution_time=time.time() - start_time
            )
            
            prompt_name = item.data.get("prompt_name", "Unknown Prompt") if item.data else "Unknown Prompt"
            self.notification_manager.show_error_notification(
                "Clipboard Error",
                truncate_text(error_msg),
                prompt_name
            )
            
            return result
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            result = ExecutionResult(
                success=False,
                error=error_msg,
                execution_time=time.time() - start_time
            )
            
            prompt_name = item.data.get("prompt_name", "Unknown Prompt") if item.data else "Unknown Prompt"
            self.notification_manager.show_error_notification(
                "Execution Error",
                truncate_text(str(e)),
                prompt_name
            )
            
            return result


class PresetExecutionHandler:
    """Handler for executing preset menu items."""

    def __init__(self, api: PromptStoreAPI, clipboard_manager: ClipboardManager, main_root: Optional[tk.Tk] = None):
        self.api = api
        self.clipboard_manager = clipboard_manager
        self.notification_manager = NotificationManager(main_root)

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can execute the given menu item."""
        return item.item_type == MenuItemType.PRESET

    def execute(self, item: MenuItem, context: Optional[str] = None) -> ExecutionResult:
        """Execute a preset menu item."""
        start_time = time.time()

        try:
            if not item.data or not item.data.get("preset_id") or not item.data.get("prompt_id"):
                return ExecutionResult(
                    success=False,
                    error="Invalid preset data"
                )

            preset_id = item.data["preset_id"]
            prompt_id = item.data["prompt_id"]

            # Use provided context or fall back to clipboard
            if context is not None:
                clipboard_content = context
            else:
                if self.clipboard_manager.is_empty():
                    return ExecutionResult(
                        success=False,
                        error="Clipboard is empty"
                    )
                clipboard_content = self.clipboard_manager.get_content()

            user_message = create_user_message(clipboard_content)

            result = self.api.execute_prompt_with_preset(
                prompt_id, preset_id, [user_message], context
            )
            content = result.get("content", "No response content")

            if not self.clipboard_manager.set_content(content):
                return ExecutionResult(
                    success=False,
                    error=f"Preset executed but failed to copy result to clipboard.\n\nResult:\n{
                        content}"
                )

            execution_time = time.time() - start_time
            result = ExecutionResult(
                success=True,
                content=content,
                execution_time=execution_time,
                metadata={
                    "preset_id": preset_id,
                    "preset_name": item.data.get("preset_name"),
                    "prompt_id": prompt_id,
                    "input_length": len(clipboard_content),
                    "output_length": len(content)
                }
            )
            
            preset_name = item.data.get("preset_name", "Unknown Preset")
            message = f"Processed in {format_execution_time(execution_time)}"
            self.notification_manager.show_success_notification(
                "Preset Completed", 
                message, 
                preset_name
            )
            
            return result

        except APIError as e:
            error_msg = f"Failed to execute preset: {str(e)}"
            result = ExecutionResult(
                success=False,
                error=error_msg,
                execution_time=time.time() - start_time
            )
            
            preset_name = item.data.get("preset_name", "Unknown Preset") if item.data else "Unknown Preset"
            self.notification_manager.show_error_notification(
                "Preset Failed",
                truncate_text(str(e)),
                preset_name
            )
            
            return result
        except ClipboardError as e:
            error_msg = str(e)
            result = ExecutionResult(
                success=False,
                error=error_msg,
                execution_time=time.time() - start_time
            )
            
            preset_name = item.data.get("preset_name", "Unknown Preset") if item.data else "Unknown Preset"
            self.notification_manager.show_error_notification(
                "Clipboard Error",
                truncate_text(error_msg),
                preset_name
            )
            
            return result
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            result = ExecutionResult(
                success=False,
                error=error_msg,
                execution_time=time.time() - start_time
            )
            
            preset_name = item.data.get("preset_name", "Unknown Preset") if item.data else "Unknown Preset"
            self.notification_manager.show_error_notification(
                "Execution Error",
                truncate_text(str(e)),
                preset_name
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
            if not item.data or not item.data.get("type") or not item.data.get("content"):
                return ExecutionResult(
                    success=False,
                    error="Invalid history data or no content available"
                )

            content = item.data["content"]
            history_type = item.data["type"]

            if not self.clipboard_manager.set_content(content):
                return ExecutionResult(
                    success=False,
                    error=f"Failed to copy {history_type} to clipboard"
                )

            execution_time = time.time() - start_time
            return ExecutionResult(
                success=True,
                content=content,
                execution_time=execution_time,
                metadata={
                    "history_type": history_type,
                    "content_length": len(content)
                }
            )

        except ClipboardError as e:
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                execution_time=time.time() - start_time
            )


class SystemExecutionHandler:
    """Handler for executing system menu items."""

    def __init__(self, refresh_callback=None, main_root: Optional[tk.Tk] = None):
        self.refresh_callback = refresh_callback
        self.notification_manager = NotificationManager(main_root)

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
                    error="Invalid system command"
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
                    metadata={"command": "refresh"}
                )
                
                self.notification_manager.show_info_notification(
                    "Data Refreshed",
                    f"Completed in {format_execution_time(execution_time)}"
                )
                
                return result
            else:
                return ExecutionResult(
                    success=False,
                    error=f"Unknown system command: {command_type}"
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"System command failed: {str(e)}",
                execution_time=time.time() - start_time
            )
