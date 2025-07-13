"""PyQt5-specific execution handlers that accept shared notification manager."""

from typing import Optional
import logging
from core.interfaces import ClipboardManager
from core.models import MenuItem, MenuItemType, ExecutionResult, ErrorCode
from modules.utils.notifications import (
    PyQtNotificationManager,
)
import time

logger = logging.getLogger(__name__)


class HistoryExecutionHandler:
    """PyQt5 handler for executing history menu items."""

    def __init__(
        self,
        clipboard_manager: ClipboardManager,
        notification_manager: PyQtNotificationManager,
    ):
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager

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

            content_type = item.data.get("type")
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

            self.notification_manager.show_success_notification("Copied")

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
