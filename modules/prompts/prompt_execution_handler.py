"""PyQt5-specific execution handlers that accept shared notification manager."""

from typing import Optional, List
import logging
from core.interfaces import ClipboardManager
from core.models import MenuItem, MenuItemType, ExecutionResult
from modules.utils.config import AppConfig
from core.openai_service import OpenAiService
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from modules.utils.notifications import (
    PyQtNotificationManager,
    format_execution_time,
)
import time

logger = logging.getLogger(__name__)


class PromptExecutionHandler:
    """Handler for executing settings-based prompt menu items."""

    def __init__(
        self,
        settings_prompt_provider,
        clipboard_manager: ClipboardManager,
        notification_manager: Optional[PyQtNotificationManager],
        openai_service: OpenAiService,
        config: AppConfig,
    ):
        self.settings_prompt_provider = settings_prompt_provider
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager or PyQtNotificationManager()
        self.openai_service = openai_service
        self.config = config

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
        """Execute a settings prompt menu item."""
        start_time = time.time()

        try:
            prompt_id = item.data.get("prompt_id") if item.data else None
            if not prompt_id:
                return ExecutionResult(
                    success=False,
                    error="Missing prompt ID",
                    execution_time=time.time() - start_time,
                )

            # Get model from MenuItem.data.model
            model_name = item.data.get("model") if item.data else None

            # Use default model if not specified
            if not model_name:
                model_name = self.config.default_model

            # Ensure model_name is a string
            if not model_name or not isinstance(model_name, str):
                return ExecutionResult(
                    success=False,
                    error="No valid model specified",
                    execution_time=time.time() - start_time,
                )

            # Validate model exists in openai service
            if not self.openai_service.has_model(model_name):
                return ExecutionResult(
                    success=False,
                    error=f"Model '{model_name}' not found in configuration",
                    execution_time=time.time() - start_time,
                )

            # Get model configuration for display name
            model_config = self.openai_service.get_model_config(model_name)

            messages = self.settings_prompt_provider.get_prompt_messages(prompt_id)
            if not messages:
                return ExecutionResult(
                    success=False,
                    error=f"Prompt '{prompt_id}' not found",
                    execution_time=time.time() - start_time,
                )

            if context:
                clipboard_content = context
            else:
                try:
                    clipboard_content = self.clipboard_manager.get_content()
                except Exception as e:
                    clipboard_content = ""
                    logger.warning("Failed to get clipboard content: %s", e)

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
                )

            # Call OpenAI API
            response_text = self.openai_service.complete(
                model_key=model_name,
                messages=processed_messages,
            )

            # Copy response to clipboard
            self.clipboard_manager.set_content(response_text)

            # Show notification
            prompt_name = (
                item.data.get("prompt_name", prompt_id) if item.data else prompt_id
            )
            execution_time = time.time() - start_time
            notification_message = f"{model_config['display_name']} processed in {format_execution_time(execution_time)}".strip()
            self.notification_manager.show_success_notification(
                f"{prompt_name} completed", notification_message
            )

            return ExecutionResult(
                success=True,
                content=response_text,
                execution_time=time.time() - start_time,
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Failed to execute settings prompt: {str(e)}",
                execution_time=time.time() - start_time,
            )
