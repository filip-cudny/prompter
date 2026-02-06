"""PySide6-based menu coordinator for the Promptheus application."""

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from core.exceptions import MenuError
from core.models import ErrorCode, ExecutionResult, MenuItem, MenuItemType
from modules.utils.config import ConfigService
from modules.utils.notification_config import is_notification_enabled

from .context_menu import PyQtContextMenu

logger = logging.getLogger(__name__)


class PyQtMenuCoordinator(QObject):
    """Coordinates menu providers and handles menu display using PyQt5."""

    # Qt signals for thread-safe communication
    execution_completed = Signal(object, str)  # ExecutionResult, execution_id
    execution_started = Signal(str)  # execution_id
    execution_error = Signal(str)
    streaming_chunk = Signal(str, str, bool, str)  # chunk, accumulated, is_final, execution_id

    def __init__(self, prompt_store_service, parent=None):
        super().__init__(parent)
        self.prompt_store_service = prompt_store_service
        self.providers = []
        self.context_menu = PyQtContextMenu()
        self.context_menu.menu_coordinator = self
        self.context_menu.set_execution_callback(self._handle_menu_item_execution)
        self.app = QApplication.instance()

        # Set menu coordinator reference in PromptStore service for GUI updates
        if hasattr(self.prompt_store_service, "set_menu_coordinator"):
            self.prompt_store_service.set_menu_coordinator(self)

        # Callbacks
        self.execution_callback: Callable[[ExecutionResult], None] | None = None
        self.error_callback: Callable[[str], None] | None = None

        # Context manager for change notifications
        self.context_manager = None

        # Notification manager for UI notifications
        self.notification_manager = None

        # Shutdown callback for proper app termination
        self.shutdown_callback: Callable[[], None] | None = None

        # Menu state
        self.last_menu_items: list[MenuItem] = []

        # Load menu section order from config
        self._config_service = ConfigService()
        self._menu_section_order = self._config_service.get_menu_section_order()
        self._config_service.register_on_save_callback(self._on_settings_saved)

        # Connect internal signals
        self.execution_completed.connect(self._handle_execution_result)
        self.execution_started.connect(self._on_execution_started)
        self.execution_error.connect(self._handle_error)

    def _handle_menu_item_execution(self, item: MenuItem, shift_pressed: bool = False):
        """Handle menu item execution from the context menu."""
        try:
            if shift_pressed:
                # For shift+click, check if item has alternative action
                if hasattr(item, "alternative_action") and item.alternative_action:
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

    def set_shutdown_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for application shutdown."""
        self.shutdown_callback = callback

    def _handle_close_app(self) -> None:
        """Handle close app request with proper cleanup."""
        from PySide6.QtCore import QTimer

        if self.context_menu:
            self.context_menu.destroy()

        if self.shutdown_callback:
            self.shutdown_callback()
        else:
            QTimer.singleShot(100, lambda: QApplication.instance().quit())

    def _on_context_changed(self):
        """Handle context changes."""
        logger.debug("Context changed")

    def _on_settings_saved(self):
        """Handle settings save event - reload menu section order."""
        self._menu_section_order = self._config_service.get_menu_section_order()

    def add_provider(self, provider) -> None:
        """Add a menu provider."""
        self.providers.append(provider)

    def remove_provider(self, provider) -> None:
        """Remove a menu provider."""
        if provider in self.providers:
            self.providers.remove(provider)

    def set_execution_callback(self, callback: Callable[[ExecutionResult], None]) -> None:
        """Set callback for execution results."""
        self.execution_callback = callback

    def set_error_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for errors."""
        self.error_callback = callback

    def set_menu_position_offset(self, offset: tuple[int, int]) -> None:
        """Set menu positioning offset."""
        self.context_menu.set_menu_position_offset(offset)

    def set_number_input_debounce_ms(self, debounce_ms: int) -> None:
        """Set debounce delay for number input in milliseconds."""
        self.context_menu.set_number_input_debounce_ms(debounce_ms)

    def show_menu(self, position: tuple[int, int] | None = None) -> None:
        """Show the context menu at cursor position or at a specific position."""
        if self.context_menu.menu and self.context_menu.menu.isVisible():
            self.context_menu.menu.close()
        try:
            items = self._get_all_menu_items()
            if not items:
                logger.warning("No menu items available")
                return

            self.last_menu_items = items
            if position:
                self.context_menu.show_at_position(items, position)
            else:
                self.context_menu.show_at_cursor(items)

        except (RuntimeError, Exception) as e:
            self._handle_error(f"Failed to show menu: {str(e)}")

    def show_menu_at_position(self, position: tuple[int, int]) -> None:
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
        if self.context_manager:
            self.context_manager.remove_change_callback(self._on_context_changed)

        if self.context_menu:
            self.context_menu.destroy()

        self.providers.clear()

    def _get_all_menu_items(self) -> list[MenuItem]:
        """Get all menu items from providers based on configured section order."""
        try:
            all_items = []
            section_order = self._menu_section_order
            total_sections = len(section_order)

            for section_index, section_id in enumerate(section_order):
                section_items = []
                is_last_section = section_index == total_sections - 1

                if section_id == "prompts":
                    section_items = self._build_prompt_items()
                elif section_id == "settings":
                    section_items = self._build_settings_items()
                else:
                    section_items = self._build_provider_items(section_id)

                if section_items:
                    for item in section_items:
                        item.section_id = section_id
                    all_items.extend(section_items)
                    if not is_last_section and all_items:
                        all_items[-1].separator_after = True

            return all_items

        except Exception as e:
            raise MenuError(f"Failed to build menu items: {str(e)}") from e

    def _wrap_provider_items(self, items: list[MenuItem]) -> list[MenuItem]:
        """Wrap provider items to handle execution through the service."""
        wrapped_items = []

        for item in items:
            # Create a new item with wrapped action
            wrapped_item = MenuItem(
                id=item.id,
                label=item.label,
                item_type=item.item_type,
                action=lambda captured_item=item: self._execute_menu_item(captured_item),
                data=item.data,
                enabled=item.enabled,
                tooltip=getattr(item, "tooltip", None),
                icon=item.icon,
            )

            # Copy separator info if present
            if hasattr(item, "separator_after"):
                wrapped_item.separator_after = item.separator_after

            # Copy alternative_action if present (but NOT for PROMPT items which use their own alternative execution path)
            if hasattr(item, "alternative_action") and item.item_type != MenuItemType.PROMPT:
                wrapped_item.alternative_action = item.alternative_action

            wrapped_items.append(wrapped_item)

        return wrapped_items

    def _execute_menu_item(self, item: MenuItem) -> None:
        """Execute a menu item through the PromptStore service or direct action call."""
        try:
            logger.debug(f"Executing menu item: {item.id} (type: {item.item_type})")
            # For system items with direct actions (like set default model, set active prompt),
            # call the action directly instead of going through the execution service
            if item.item_type == MenuItemType.SYSTEM and item.action is not None and callable(item.action):
                # Call the action directly - it will emit its own execution_completed signal
                item.action()
            else:
                # Execute the item using the service for prompts and other items
                result = self.prompt_store_service.execute_item(item)

                # Emit signal for thread-safe handling
                self.execution_completed.emit(result, result.execution_id or "")

        except (RuntimeError, Exception) as e:
            error_msg = f"Failed to execute menu item '{item.label}': {str(e)}"
            self.execution_error.emit(error_msg)

    def _handle_execution_result(self, result: ExecutionResult, execution_id: str = "") -> None:
        """Handle execution result on main thread."""
        if self.execution_callback:
            try:
                self.execution_callback(result)
            except (RuntimeError, Exception) as e:
                print(f"Error in execution callback: {e}")

    def _on_execution_started(self, execution_id: str) -> None:
        """Handle execution started event."""
        pass

    def _handle_error(self, error_message: str) -> None:
        """Handle error on main thread."""
        if self.error_callback:
            try:
                self.error_callback(error_message)
            except (RuntimeError, Exception) as e:
                print(f"Error in error callback: {e}")
        else:
            print(f"Menu error: {error_message}")

    def get_last_menu_items(self) -> list[MenuItem]:
        """Get the last displayed menu items."""
        return self.last_menu_items

    def get_provider_count(self) -> int:
        """Get the number of registered providers."""
        return len(self.providers)

    def _build_provider_items(self, provider_class_name: str) -> list[MenuItem]:
        """Build menu items from a specific provider by class name."""
        for provider in self.providers:
            if provider.__class__.__name__ == provider_class_name:
                try:
                    items = provider.get_menu_items()
                    if items:
                        return self._wrap_provider_items(items)
                except (RuntimeError, Exception) as e:
                    logger.error(f"Error getting items from provider {provider_class_name}: {e}")
        return []

    def _build_prompt_items(self) -> list[MenuItem]:
        """Build prompt menu items from non-dynamic providers."""
        prompt_items = []
        dynamic_providers = {"LastInteractionMenuProvider", "ContextMenuProvider", "SpeechMenuProvider"}

        for provider in self.providers:
            if provider.__class__.__name__ not in dynamic_providers:
                try:
                    items = provider.get_menu_items()
                    if items:
                        wrapped_items = self._wrap_provider_items(items)
                        prompt_items.extend(wrapped_items)
                except (RuntimeError, Exception) as e:
                    logger.error(f"Error getting items from provider {provider.__class__.__name__}: {e}")
                    continue

        return prompt_items

    def _build_settings_items(self) -> list[MenuItem]:
        """Build settings section items."""
        settings_items = []
        self._add_active_prompt_info(settings_items)
        return settings_items

    def _open_settings_dialog(self):
        """Open the settings dialog."""
        from modules.gui.settings_dialog import show_settings_dialog

        show_settings_dialog()

    def _add_active_prompt_info(self, all_items: list[MenuItem]) -> None:
        """Add settings section with model and prompt chips to the menu."""
        if not self.prompt_store_service:
            return

        config = ConfigService().get_config()
        default_model_display_name = config.default_model
        if config.models and config.default_model:
            for model in config.models:
                if model.get("id") == config.default_model:
                    default_model_display_name = model.get("display_name", config.default_model)
                    break

        active_prompt_display_name = "None"
        if self.prompt_store_service.active_prompt_service.has_active_prompt():
            active_name = self.prompt_store_service.active_prompt_service.get_active_prompt_display_name()
            if active_name:
                active_prompt_display_name = active_name[:27] + "..." if len(active_name) > 30 else active_name

        settings_section_item = MenuItem(
            id="settings_section",
            label="Settings",
            item_type=MenuItemType.SETTINGS_SECTION,
            action=lambda: None,
            enabled=True,
            separator_after=False,
            data={
                "model_options": self._get_settings_submenu_items(),
                "prompt_options": self._get_prompt_selector_items(),
                "current_model": default_model_display_name,
                "current_prompt": active_prompt_display_name,
                "on_prompt_clear": self._handle_prompt_clear,
                "on_settings_click": self._open_settings_dialog,
                "on_close_app_click": self._handle_close_app,
            },
        )

        all_items.append(settings_section_item)

    def _handle_prompt_clear(self):
        """Handle clearing the active prompt."""
        if self.prompt_store_service:
            self.prompt_store_service.active_prompt_service.clear_active_prompt()
            result = ExecutionResult(
                success=True,
                content="Active prompt cleared",
                metadata={"action": "clear_active_prompt"},
            )
            self.execution_completed.emit(result, "")

    def _get_prompt_selector_items(self) -> list[MenuItem]:
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
                        self.execution_completed.emit(result, "")

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

    def _get_settings_submenu_items(self) -> list[MenuItem]:
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
            for model in config.models:
                model_id = model.get("id")
                is_default = model_id == config.default_model

                def make_set_default_model_action(mid, model_config):
                    def set_default_model():
                        try:
                            config_service = ConfigService()
                            config_service.update_default_model(mid)

                            # Show confirmation through execution result
                            result = ExecutionResult(
                                success=True,
                                content=f"Default model set to: {model_config.get('display_name', mid)}",
                                metadata={"action": "set_default_model", "model": mid},
                            )
                            self.execution_completed.emit(result, "")
                        except Exception as e:
                            result = ExecutionResult(
                                success=False,
                                content=f"Error setting default model: {str(e)}",
                                metadata={"action": "set_default_model", "model": mid},
                            )
                            self.execution_completed.emit(result, "")

                    return set_default_model

                # Add checkmark for default model
                label = model.get("display_name", model_id)
                if is_default:
                    label = f"✓ {label}"

                submenu_item = MenuItem(
                    id=f"set_default_model_{model_id}",
                    label=label,
                    item_type=MenuItemType.SYSTEM,
                    action=make_set_default_model_action(model_id, model),
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


class PyQtMenuEventHandler:
    """Handles menu execution results and errors."""

    def __init__(self, menu_coordinator: PyQtMenuCoordinator):
        self.menu_coordinator = menu_coordinator
        self.notification_manager = None
        self.recent_results: list[ExecutionResult] = []
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
                self.notification_manager.show_error_notification("Execution Error", error_message)
            else:
                print(f"Execution error: {error_message}")

        except (RuntimeError, Exception) as e:
            print(f"Error handling error message: {e}")

    def get_recent_results(self, count: int = 5) -> list[ExecutionResult]:
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
                prompt_name = result.metadata.get("prompt_name") or result.metadata.get("preset_name")

            # Format error message with prompt name if available
            error_message = result.error
            if prompt_name:
                error_message = f"{result.error}\n({prompt_name})"

            # Show warning for NO_ACTIVE_PROMPT, EXECUTION_IN_PROGRESS, and CLIPBOARD_ERROR; error for others
            if result.error_code == ErrorCode.NO_ACTIVE_PROMPT:
                self.notification_manager.show_warning_notification(
                    "No Active Prompt",
                    error_message,
                )
            elif result.error_code == ErrorCode.EXECUTION_IN_PROGRESS:
                if is_notification_enabled("prompt_execution_in_progress"):
                    self.notification_manager.show_warning_notification(
                        "Prompt execution in progress",
                        "Please wait for the current prompt to complete",
                    )
            elif result.error_code == ErrorCode.CLIPBOARD_ERROR:
                self.notification_manager.show_warning_notification(
                    "Clipboard Unavailable",
                    "Copy some text to clipboard and try again",
                )
            else:
                self.notification_manager.show_error_notification(
                    "Execution Failed",
                    error_message,
                )
        else:
            print(f"Execution failed: {result.error}")
