"""PyQt5-based menu coordinator for the Prompter application."""

import logging
from typing import List, Optional, Callable, Tuple, Dict, Any
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtWidgets import QApplication

from core.models import MenuItem, ExecutionResult, MenuItemType, ErrorCode
from core.exceptions import MenuError
from modules.utils.config import ConfigService
from .context_menu import PyQtContextMenu

logger = logging.getLogger(__name__)


class PyQtMenuCoordinator(QObject):
    """Coordinates menu providers and handles menu display using PyQt5."""

    # Qt signals for thread-safe communication
    execution_completed = pyqtSignal(object)  # ExecutionResult
    execution_error = pyqtSignal(str)

    def __init__(self, prompt_store_service, parent=None):
        super().__init__(parent)
        self.prompt_store_service = prompt_store_service
        self.providers = []
        self.context_menu = PyQtContextMenu()
        self.context_menu.menu_coordinator = self
        self.context_menu.set_execution_callback(self._handle_menu_item_execution)
        self.app = QApplication.instance()

        # Set menu coordinator reference in Prompter service for GUI updates
        if hasattr(self.prompt_store_service, "set_menu_coordinator"):
            self.prompt_store_service.set_menu_coordinator(self)

        # Callbacks
        self.execution_callback: Optional[Callable[[ExecutionResult], None]] = None
        self.error_callback: Optional[Callable[[str], None]] = None

        # Context manager for cache invalidation
        self.context_manager = None

        # Menu state
        self.last_menu_items: List[MenuItem] = []
        self.menu_cache: Dict[str, List[MenuItem]] = {}
        self.cache_timeout = 30000  # 30 seconds
        self.cache_timer = QTimer()
        self.cache_timer.timeout.connect(self._clear_menu_cache)

        # Separate caches for different menu parts
        self._cached_dynamic_items = (
            None  # Active prompt info and dynamic provider items
        )
        self._cached_static_items = (
            None  # Static provider items (prompts, presets, etc.)
        )
        self._dynamic_items_dirty = True
        self._static_items_dirty = True

        # Dynamic provider class names (providers whose items change frequently)
        self._dynamic_provider_classes = {"HistoryMenuProvider", "SpeechMenuProvider"}

        # Connect internal signals
        self.execution_completed.connect(self._handle_execution_result)
        self.execution_error.connect(self._handle_error)
        
    def _handle_menu_item_execution(self, item: MenuItem, shift_pressed: bool = False):
        """Handle menu item execution from the context menu."""
        try:
            if shift_pressed:
                # For shift+click, check if item has alternative action
                if hasattr(item, 'alternative_action') and item.alternative_action:
                    result = item.alternative_action()
                    if result:
                        self._handle_execution_result(result)
                else:
                    # For items that support alternative execution (prompts), create modified item
                    if item.item_type == MenuItemType.PROMPT:
                        alt_item = MenuItem(
                            id=item.id,
                            label=item.label,
                            item_type=item.item_type,
                            action=item.action,
                            data={**(item.data or {}), "alternative_execution": True},
                            enabled=item.enabled,
                        )
                        self._execute_menu_item(alt_item)
                    else:
                        # For system items (set default model, set active prompt), just execute normally
                        self._execute_menu_item(item)
            else:
                self._execute_menu_item(item)
        except Exception as e:
            self._handle_error(f"Failed to execute menu item: {str(e)}")

    def set_context_manager(self, context_manager):
        """Set the context manager and register for change notifications."""
        self.context_manager = context_manager
        if context_manager:
            context_manager.add_change_callback(self._on_context_changed)

    def _on_context_changed(self):
        """Handle context changes by invalidating cache."""
        logger.debug("Context changed, invalidating menu cache")
        self._invalidate_cache()

    def add_provider(self, provider) -> None:
        """Add a menu provider."""
        self.providers.append(provider)
        self._clear_menu_cache()

    def remove_provider(self, provider) -> None:
        """Remove a menu provider."""
        if provider in self.providers:
            self.providers.remove(provider)
            self._clear_menu_cache()

    def set_execution_callback(
        self, callback: Callable[[ExecutionResult], None]
    ) -> None:
        """Set callback for execution results."""
        self.execution_callback = callback

    def set_error_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for errors."""
        self.error_callback = callback

    def set_menu_position_offset(self, offset: Tuple[int, int]) -> None:
        """Set menu positioning offset."""
        self.context_menu.set_menu_position_offset(offset)

    def set_number_input_debounce_ms(self, debounce_ms: int) -> None:
        """Set debounce delay for number input in milliseconds."""
        self.context_menu.set_number_input_debounce_ms(debounce_ms)

    def show_menu(self) -> None:
        """Show the context menu at cursor position."""
        if self.context_menu.menu and self.context_menu.menu.isVisible():
            self.context_menu.menu.close()
        try:
            items = self._get_all_menu_items()
            if not items:
                logger.warning("No menu items available")
                return

            self.last_menu_items = items
            self.context_menu.show_at_cursor(items)

        except (RuntimeError, Exception) as e:
            self._handle_error(f"Failed to show menu: {str(e)}")

    def show_menu_at_position(self, position: Tuple[int, int]) -> None:
        """Show the context menu at specific position."""
        try:
            items = self._get_all_menu_items()
            if not items:
                self._handle_error("No menu items available")
                return

            self.last_menu_items = items
            self.context_menu.show_at_position(items, position)

        except (RuntimeError, Exception) as e:
            self._handle_error(f"Failed to show menu at position: {str(e)}")

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.cache_timer.isActive():
            self.cache_timer.stop()

        if self.context_manager:
            self.context_manager.remove_change_callback(self._on_context_changed)

        if self.context_menu:
            self.context_menu.destroy()

        self.providers.clear()
        self._clear_menu_cache()

    def _get_all_menu_items(self) -> List[MenuItem]:
        """Get all menu items with selective caching."""
        # Check if we have valid complete cache
        if (
            self._cached_static_items is not None
            and self._cached_dynamic_items is not None
            and not self._static_items_dirty
            and not self._dynamic_items_dirty
        ):
            # Combine cached items
            all_items = []
            all_items.extend(self._cached_static_items)
            all_items.extend(self._cached_dynamic_items)
            return all_items

        try:
            # Get or rebuild static provider items
            if self._cached_static_items is None or self._static_items_dirty:
                static_items = []
                for provider in self.providers:
                    if (
                        provider.__class__.__name__
                        not in self._dynamic_provider_classes
                    ):
                        try:
                            items = provider.get_menu_items()
                            if items:
                                wrapped_items = self._wrap_provider_items(items)
                                static_items.extend(wrapped_items)
                        except (RuntimeError, Exception) as e:
                            print(
                                f"Error getting items from provider {provider.__class__.__name__}: {e}"
                            )
                            continue

                self._cached_static_items = static_items
                self._static_items_dirty = False

            # Get or rebuild dynamic items
            if self._cached_dynamic_items is None or self._dynamic_items_dirty:
                self._cached_dynamic_items = self._build_dynamic_items()
                self._dynamic_items_dirty = False

            # Combine all items
            all_items = []
            all_items.extend(self._cached_static_items or [])
            all_items.extend(self._cached_dynamic_items or [])

            self._start_cache_timer()
            return all_items

        except Exception as e:
            raise MenuError(f"Failed to build menu items: {str(e)}") from e

    def _wrap_provider_items(self, items: List[MenuItem]) -> List[MenuItem]:
        """Wrap provider items to handle execution through the service."""
        wrapped_items = []

        for item in items:
            # Create a new item with wrapped action
            wrapped_item = MenuItem(
                id=item.id,
                label=item.label,
                item_type=item.item_type,
                action=lambda captured_item=item: self._execute_menu_item(
                    captured_item
                ),
                data=item.data,
                enabled=item.enabled,
                tooltip=getattr(item, "tooltip", None),
            )

            # Copy separator info if present
            if hasattr(item, "separator_after"):
                wrapped_item.separator_after = item.separator_after

            wrapped_items.append(wrapped_item)

        return wrapped_items

    def _execute_menu_item(self, item: MenuItem) -> None:
        """Execute a menu item through the Prompter service or direct action call."""
        try:
            # For system items with direct actions (like set default model, set active prompt),
            # call the action directly instead of going through the execution service
            if item.item_type == MenuItemType.SYSTEM and item.action is not None and callable(item.action):
                # Call the action directly - it will emit its own execution_completed signal
                item.action()
            else:
                # Execute the item using the service for prompts and other items
                result = self.prompt_store_service.execute_item(item)

                # Invalidate dynamic cache based on action type
                self._invalidate_cache_for_action(item, result)

                # Emit signal for thread-safe handling
                self.execution_completed.emit(result)

        except (RuntimeError, Exception) as e:
            error_msg = f"Failed to execute menu item '{item.label}': {str(e)}"
            self.execution_error.emit(error_msg)

    def _handle_execution_result(self, result: ExecutionResult) -> None:
        """Handle execution result on main thread."""
        # Invalidate cache for actions that need it (handles submenu items)
        self._invalidate_cache_for_result(result)

        if self.execution_callback:
            try:
                self.execution_callback(result)
            except (RuntimeError, Exception) as e:
                print(f"Error in execution callback: {e}")

    def _handle_error(self, error_message: str) -> None:
        """Handle error on main thread."""
        if self.error_callback:
            try:
                self.error_callback(error_message)
            except (RuntimeError, Exception) as e:
                print(f"Error in error callback: {e}")
        else:
            print(f"Menu error: {error_message}")

    def _start_cache_timer(self) -> None:
        """Start the cache cleanup timer."""
        if not self.cache_timer.isActive():
            self.cache_timer.start(self.cache_timeout)

    def _clear_menu_cache(self) -> None:
        """Clear the menu item cache."""
        self.menu_cache.clear()
        self._cached_dynamic_items = None
        self._cached_static_items = None
        self._dynamic_items_dirty = True
        self._static_items_dirty = True
        if self.cache_timer.isActive():
            self.cache_timer.stop()

    def get_last_menu_items(self) -> List[MenuItem]:
        """Get the last displayed menu items."""
        return self.last_menu_items

    def get_provider_count(self) -> int:
        """Get the number of registered providers."""
        return len(self.providers)

    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information for debugging."""
        return {
            "cached_keys": list(self.menu_cache.keys()),
            "cache_active": self.cache_timer.isActive(),
            "cache_timeout": self.cache_timeout,
        }

    def _build_dynamic_items(self) -> List[MenuItem]:
        """Build dynamic menu items (active prompt info and dynamic provider items)."""
        dynamic_items = []

        # Get items from dynamic providers
        for provider in self.providers:
            if provider.__class__.__name__ in self._dynamic_provider_classes:
                try:
                    items = provider.get_menu_items()
                    if items:
                        wrapped_items = self._wrap_provider_items(items)
                        dynamic_items.extend(wrapped_items)
                except (RuntimeError, Exception) as e:
                    print(
                        f"Error getting items from dynamic provider {provider.__class__.__name__}: {e}"
                    )
                    continue

        # Add active prompt info
        self._add_active_prompt_info(dynamic_items)

        return dynamic_items

    def _add_active_prompt_info(self, all_items: List[MenuItem]) -> None:
        """Add settings submenu and active prompt selector to the menu."""
        if not self.prompt_store_service:
            return

        # Get default model display name
        config = ConfigService().get_config()
        default_model_display_name = config.default_model
        if config.models and config.default_model in config.models:
            default_model_config = config.models[config.default_model]
            default_model_display_name = default_model_config.get(
                "display_name", config.default_model
            )

        # Add Settings subdmenu
        settings_item = MenuItem(
            id="settings_submenu",
            label=f"Settings ({default_model_display_name})",
            item_type=MenuItemType.SYSTEM,
            action=lambda: None,
            enabled=True,
            separator_after=False,
        )
        settings_item.submenu_items = self._get_settings_submenu_items()

        # Get active prompt display name
        display_name = "None"
        if self.prompt_store_service.active_prompt_service.has_active_prompt():
            active_name = self.prompt_store_service.active_prompt_service.get_active_prompt_display_name()
            if active_name:
                # Truncate long names
                if len(active_name) > 30:
                    display_name = active_name[:27] + "..."
                else:
                    display_name = active_name

        # Create active prompt selector item with submenu
        active_prompt_item = MenuItem(
            id="active_prompt_selector",
            label=f"Active Prompt ({display_name})",
            item_type=MenuItemType.SYSTEM,
            action=lambda: None,  # No direct action, submenu will handle it
            enabled=True,
            separator_after=False,
        )

        # Set submenu items
        active_prompt_item.submenu_items = self._get_prompt_selector_items()

        # Add separator before settings item if there are other items
        if all_items:
            if hasattr(all_items[-1], "separator_after"):
                all_items[-1].separator_after = True
            else:
                # Add separator attribute to the last item
                setattr(all_items[-1], "separator_after", True)

        all_items.append(settings_item)
        all_items.append(active_prompt_item)

    def _get_prompt_selector_items(self) -> List[MenuItem]:
        """Get prompt selector submenu items."""
        try:
            # Get prompts and presets directly from service
            prompts = self.prompt_store_service.get_prompts()

            if not prompts:
                return [
                    MenuItem(
                        id="no_prompts",
                        label="No prompts available",
                        item_type=MenuItemType.SYSTEM,
                        action=lambda: None,
                        enabled=False,
                    )
                ]

            # Create submenu items
            submenu_items = []

            # Add prompts
            for prompt in prompts:

                def make_set_active_action(p):
                    def set_active():
                        # Create MenuItem with proper data structure
                        active_item = MenuItem(
                            id=f"prompt_{p.id}",
                            label=p.name,
                            item_type=MenuItemType.PROMPT,
                            action=lambda: None,
                            data={
                                "prompt_id": p.id,
                                "prompt_name": p.name,
                                "model": p.model,
                                "source": p.source,
                            },
                        )
                        self.prompt_store_service.set_active_prompt(active_item)
                        # Show confirmation through execution result
                        result = ExecutionResult(
                            success=True,
                            content=f"Active prompt set to: {p.name}",
                            metadata={"action": "set_active_prompt", "prompt": p.name},
                        )
                        self.execution_completed.emit(result)

                    return set_active

                submenu_item = MenuItem(
                    id=f"select_prompt_{prompt.id}",
                    label=prompt.name,
                    item_type=MenuItemType.SYSTEM,
                    action=make_set_active_action(prompt),
                    enabled=True,
                    separator_after=False,
                )
                submenu_items.append(submenu_item)

            return submenu_items

        except Exception as e:
            return [
                MenuItem(
                    id="error_prompts",
                    label=f"Error loading prompts: {str(e)}",
                    item_type=MenuItemType.SYSTEM,
                    action=lambda: None,
                    enabled=False,
                )
            ]

    def _get_settings_submenu_items(self) -> List[MenuItem]:
        """Get settings submenu items."""
        try:
            from modules.utils.config import ConfigService

            config_service = ConfigService()
            config = config_service.get_config()

            if not config.models:
                return [
                    MenuItem(
                        id="no_models",
                        label="No models available",
                        item_type=MenuItemType.SYSTEM,
                        action=lambda: None,
                        enabled=False,
                    )
                ]

            submenu_items = []

            # Add model selection items
            for model_key, model_config in config.models.items():
                is_default = model_key == config.default_model

                def make_set_default_model_action(key, model_config):
                    def set_default_model():
                        try:
                            config_service = ConfigService()
                            config_service.update_default_model(key)

                            # Show confirmation through execution result
                            result = ExecutionResult(
                                success=True,
                                content=f"Default model set to: {model_config.get('display_name', key)}",
                                metadata={"action": "set_default_model", "model": key},
                            )
                            self.execution_completed.emit(result)
                            self._invalidate_cache()
                        except Exception as e:
                            result = ExecutionResult(
                                success=False,
                                content=f"Error setting default model: {str(e)}",
                                metadata={"action": "set_default_model", "model": key},
                            )
                            self.execution_completed.emit(result)

                    return set_default_model

                # Add checkmark for default model
                label = model_config.get("display_name", model_key)
                if is_default:
                    label = f"✓ {label}"

                submenu_item = MenuItem(
                    id=f"set_default_model_{model_key}",
                    label=label,
                    item_type=MenuItemType.SYSTEM,
                    action=make_set_default_model_action(model_key, model_config),
                    enabled=True,
                    separator_after=False,
                )
                submenu_items.append(submenu_item)

            return submenu_items

        except Exception as e:
            return [
                MenuItem(
                    id="error_settings",
                    label=f"Error loading settings: {str(e)}",
                    item_type=MenuItemType.SYSTEM,
                    action=lambda: None,
                    enabled=False,
                )
            ]

    def _invalidate_cache_for_action(
        self, item: MenuItem, result: ExecutionResult
    ) -> None:
        """Invalidate specific cache parts based on the executed action."""
        if not result.success:
            return

        # Get action from metadata or item type
        action = result.metadata.get("action") if result.metadata else None
        item_type = item.item_type

        # Actions that change active prompt or generate new input/output
        if action in [
            "set_active_prompt",
            "execute_prompt",
            "execute_preset",
            "execute_active_prompt",
            "speech_recording_started",
            "speech_recording_stopped",
            "set_context",
            "append_context",
            "clear_context",
        ] or item_type in [MenuItemType.PROMPT]:
            self._invalidate_cache()

    def _invalidate_cache_for_result(self, result: ExecutionResult) -> None:
        """Invalidate cache based on execution result (for submenu items)."""
        if not result.success:
            return

        # Get action from metadata
        action = result.metadata.get("action") if result.metadata else None

        # Actions that change active prompt or generate new input/output
        if action in [
            "set_active_prompt",
            "execute_prompt",
            "execute_preset",
            "execute_active_prompt",
            "speech_recording_started",
            "speech_recording_stopped",
            "set_context",
            "append_context",
            "clear_context",
        ]:
            self._invalidate_cache()

    def _invalidate_cache(self) -> None:
        """Invalidate only dynamic items cache."""
        logger.debug("Invalidating menu cache")
        self._cached_dynamic_items = None
        self._dynamic_items_dirty = True
        self._cached_static_items = None
        self._static_items_dirty = True

    def get_cache_status(self) -> Dict[str, Any]:
        """Get detailed cache status for debugging."""
        return {
            "static_cache_valid": self._cached_static_items is not None
            and not self._static_items_dirty,
            "dynamic_cache_valid": self._cached_dynamic_items is not None
            and not self._dynamic_items_dirty,
            "static_items_count": len(self._cached_static_items)
            if self._cached_static_items
            else 0,
            "dynamic_items_count": len(self._cached_dynamic_items)
            if self._cached_dynamic_items
            else 0,
            "static_dirty": self._static_items_dirty,
            "dynamic_dirty": self._dynamic_items_dirty,
            "dynamic_provider_classes": self._dynamic_provider_classes,
        }


class PyQtMenuEventHandler:
    """Handles menu execution results and errors."""

    def __init__(self, menu_coordinator: PyQtMenuCoordinator):
        self.menu_coordinator = menu_coordinator
        self.notification_manager = None
        self.recent_results: List[ExecutionResult] = []
        self.max_recent_results = 10

    def set_notification_manager(self, notification_manager) -> None:
        """Set the notification manager."""
        self.notification_manager = notification_manager

    def handle_execution_result(self, result: ExecutionResult) -> None:
        """Handle execution result."""
        try:
            # Store result in recent results
            self.recent_results.append(result)
            if len(self.recent_results) > self.max_recent_results:
                self.recent_results.pop(0)

            if result.success:
                self._handle_success_result(result)
            else:
                self._handle_error_result(result)

        except (RuntimeError, Exception) as e:
            print(f"Error handling execution result: {e}")

    def handle_error(self, error_message: str) -> None:
        """Handle execution error."""
        try:
            if self.notification_manager:
                self.notification_manager.show_error_notification(
                    "Execution Error", error_message
                )
            else:
                print(f"Execution error: {error_message}")

        except (RuntimeError, Exception) as e:
            print(f"Error handling error message: {e}")

    def get_recent_results(self, count: int = 5) -> List[ExecutionResult]:
        """Get recent execution results."""
        return self.recent_results[-count:] if self.recent_results else []

    def _handle_success_result(self, result: ExecutionResult) -> None:
        """Handle successful execution result."""
        # Success handling is done by the execution handlers themselves
        # which now use the shared notification manager
        return

    def _handle_error_result(self, result: ExecutionResult) -> None:
        """Handle error execution result."""
        if self.notification_manager and result.error:
            # Get prompt/preset name from metadata if available
            prompt_name = None
            if result.metadata:
                prompt_name = result.metadata.get("prompt_name") or result.metadata.get(
                    "preset_name"
                )

            # Format error message with prompt name if available
            error_message = result.error
            if prompt_name:
                error_message = f"{result.error}\n({prompt_name})"

            # Show warning for NO_ACTIVE_PROMPT and EXECUTION_IN_PROGRESS, error for others
            if result.error_code == ErrorCode.NO_ACTIVE_PROMPT:
                self.notification_manager.show_warning_notification(
                    "No Active Prompt",
                    error_message,
                )
            elif result.error_code == ErrorCode.EXECUTION_IN_PROGRESS:
                self.notification_manager.show_warning_notification(
                    "Prompt execution in progress",
                    "Please wait for the current prompt to complete",
                )
            else:
                self.notification_manager.show_error_notification(
                    "Execution Failed",
                    error_message,
                )
        else:
            print(f"Execution failed: {result.error}")
