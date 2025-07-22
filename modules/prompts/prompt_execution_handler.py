"""PyQt5-specific execution handlers that accept shared notification manager."""

from typing import Optional
import logging
from core.interfaces import ClipboardManager
from core.models import MenuItem, MenuItemType, ExecutionResult, ErrorCode
from modules.utils.config import AppConfig
from core.openai_service import OpenAiService
from modules.utils.notifications import PyQtNotificationManager
from modules.prompts.async_execution import AsyncPromptExecutionManager

logger = logging.getLogger(__name__)


class PromptExecutionHandler:
    """Handler for executing settings-based prompt menu items asynchronously."""

    def __init__(
        self,
        settings_prompt_provider,
        clipboard_manager: ClipboardManager,
        notification_manager: Optional[PyQtNotificationManager],
        openai_service: OpenAiService,
        config: AppConfig,
        context_manager,
        prompt_store_service=None,
    ):
        self.settings_prompt_provider = settings_prompt_provider
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager or PyQtNotificationManager()
        self.openai_service = openai_service
        self.config = config
        self.context_manager = context_manager
        self.prompt_store_service = prompt_store_service

        # Initialize async execution manager
        self.async_manager = AsyncPromptExecutionManager(
            settings_prompt_provider,
            clipboard_manager,
            notification_manager,
            openai_service,
            config,
            context_manager,
            prompt_store_service,
        )

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
        """Execute a settings prompt menu item asynchronously."""
        # Check if execution is already in progress
        if self.async_manager.is_busy():
            # Check if worker is actually still running - if not, force reset
            if not self.async_manager.is_worker_still_running():
                logger.warning("Async manager stuck in executing state, forcing reset")
                self.async_manager.force_reset_state()
            else:
                return ExecutionResult(
                    success=False,
                    error="Execution already in progress",
                    error_code=ErrorCode.EXECUTION_IN_PROGRESS,
                )

        # Basic validation
        if not item.data or not item.data.get("prompt_id"):
            return ExecutionResult(success=False, error="Missing prompt ID")

        # Start async execution
        if self.async_manager.execute_prompt_async(item, context):
            # Return immediate success - actual result will be handled by signals
            return ExecutionResult(
                success=True, content="Execution started asynchronously"
            )
        else:
            return ExecutionResult(
                success=False, error="Failed to start async execution"
            )
