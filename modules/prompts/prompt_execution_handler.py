"""PyQt5-specific execution handlers that accept shared notification manager."""

from typing import Optional, List, Callable
import logging
from core.interfaces import ClipboardManager
from core.models import MenuItem, MenuItemType, ExecutionResult
from modules.utils.config import AppConfig
from core.open_ai_api import OpenAIClient
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
        config: AppConfig,
    ):
        self.settings_prompt_provider = settings_prompt_provider
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager or PyQtNotificationManager()
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

            # Validate model exists in config
            if not self.config.models or model_name not in self.config.models:
                return ExecutionResult(
                    success=False,
                    error=f"Model '{model_name}' not found in configuration",
                    execution_time=time.time() - start_time,
                )

            # Get model configuration
            model_config = self.config.models[model_name]

            # Create OpenAI client with model configuration
            openai_client = OpenAIClient(
                api_key=model_config["api_key"], base_url=model_config.get("base_url")
            )

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
                    logger.warning(f"Failed to get clipboard content: {e}")

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
            response_text = openai_client.complete(
                messages=processed_messages,
                model=model_config["model"],
                temperature=model_config.get("temperature"),
            )

            # Copy response to clipboard
            self.clipboard_manager.set_content(response_text)

            # Show notification
            prompt_name = (
                item.data.get("prompt_name", prompt_id) if item.data else prompt_id
            )
            execution_time = time.time() - start_time
            notification_message = (
                f"Processed in {format_execution_time(execution_time)}"
            )
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
                error=f"OpenAI API error: {str(e)}",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Failed to execute settings prompt: {str(e)}",
                execution_time=time.time() - start_time,
            )
