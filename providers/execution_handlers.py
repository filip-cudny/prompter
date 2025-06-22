"""Execution handlers for different types of menu items."""

from typing import Optional
from core.interfaces import ExecutionHandler, ClipboardManager
from core.models import MenuItem, MenuItemType, ExecutionResult
from core.exceptions import ExecutionError, ClipboardError
from api import PromptStoreAPI, APIError, create_user_message
import time


class PromptExecutionHandler:
    """Handler for executing prompt menu items."""

    def __init__(self, api: PromptStoreAPI, clipboard_manager: ClipboardManager):
        self.api = api
        self.clipboard_manager = clipboard_manager

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
            return ExecutionResult(
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

        except APIError as e:
            return ExecutionResult(
                success=False,
                error=f"Failed to execute prompt: {str(e)}",
                execution_time=time.time() - start_time
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


class PresetExecutionHandler:
    """Handler for executing preset menu items."""

    def __init__(self, api: PromptStoreAPI, clipboard_manager: ClipboardManager):
        self.api = api
        self.clipboard_manager = clipboard_manager

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
            return ExecutionResult(
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

        except APIError as e:
            return ExecutionResult(
                success=False,
                error=f"Failed to execute preset: {str(e)}",
                execution_time=time.time() - start_time
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

    def __init__(self, refresh_callback=None, exit_callback=None):
        self.refresh_callback = refresh_callback
        self.exit_callback = exit_callback

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
                return ExecutionResult(
                    success=True,
                    content="Data refreshed",
                    execution_time=time.time() - start_time,
                    metadata={"command": "refresh"}
                )
            elif command_type == "exit":
                if self.exit_callback:
                    self.exit_callback()
                return ExecutionResult(
                    success=True,
                    content="Application exiting",
                    execution_time=time.time() - start_time,
                    metadata={"command": "exit"}
                )
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
