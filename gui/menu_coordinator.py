"""Menu coordinator to bridge providers and GUI components."""

import tkinter as tk
from typing import List, Callable, Optional, Dict, Any
import time

from core.interfaces import MenuItemProvider
from core.models import MenuItem, ExecutionResult, MenuItemType, ErrorCode
from core.services import PromptStoreService
from .context_menu import ContextMenu, MenuBuilder, MenuPosition
from utils.notifications import NotificationManager


class MenuCoordinator:
    """Coordinates between menu providers and GUI components."""

    def __init__(self, prompt_store_service: PromptStoreService):
        self.prompt_store_service = prompt_store_service
        self.providers: List[MenuItemProvider] = []
        self.context_menu: Optional[ContextMenu] = None
        self.root: Optional[tk.Tk] = None
        self.menu_builder = MenuBuilder()
        self.execution_callback: Optional[Callable[[
            ExecutionResult], None]] = None
        self.error_callback: Optional[Callable[[str], None]] = None
        self.menu_position_offset = (0, 0)
        self._executing = False

    def set_root(self, root: tk.Tk) -> None:
        """Set the tkinter root window."""
        self.root = root
        self.context_menu = ContextMenu(root)

    def add_provider(self, provider: MenuItemProvider) -> None:
        """Add a menu item provider."""
        self.providers.append(provider)

    def remove_provider(self, provider: MenuItemProvider) -> None:
        """Remove a menu item provider."""
        if provider in self.providers:
            self.providers.remove(provider)

    def set_execution_callback(self, callback: Callable[[ExecutionResult], None]) -> None:
        """Set callback for execution results."""
        self.execution_callback = callback

    def set_error_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for error handling."""
        self.error_callback = callback

    def set_menu_position_offset(self, offset: tuple) -> None:
        """Set position offset for menu display."""
        self.menu_position_offset = offset

    def show_menu(self) -> None:
        """Show the context menu at cursor position."""
        if not self.context_menu:
            self._handle_error("Context menu not initialized")
            return

        if self._executing:
            return  # Don't show menu while executing

        try:
            # Get cursor position
            x, y = MenuPosition.get_cursor_position()

            # Apply offset
            x, y = MenuPosition.apply_offset(x, y, self.menu_position_offset)

            # Adjust for screen bounds
            x, y = MenuPosition.adjust_for_screen_bounds(x, y)

            # Build menu items
            items = self._build_menu_items()

            # Create and show menu
            self.context_menu.create_menu(items)
            self.context_menu.show_at_position(x, y)

        except Exception as e:
            self._handle_error(f"Failed to show menu: {str(e)}")

    def refresh_providers(self) -> None:
        """Refresh all providers."""
        for provider in self.providers:
            try:
                provider.refresh()
            except Exception:
                # Continue if one provider fails
                continue

    def _build_menu_items(self) -> List[MenuItem]:
        """Build menu items from all providers."""
        self.menu_builder.clear()

        # Collect items from all providers
        # Build menu items from all providers
        for provider in self.providers:
            try:
                items = provider.get_menu_items()
                if items:
                    # Wrap actions to handle execution
                    wrapped_items = [self._wrap_menu_item(
                        item) for item in items]
                    self.menu_builder.add_items_with_separator(wrapped_items)
            except Exception:
                # Continue if one provider fails
                continue

        # Add active prompt info at the bottom
        self._add_active_prompt_info()

        built_items = self.menu_builder.build()

        # Handle submenu creation after building
        self._prepare_submenus(built_items)

        return built_items

    def _prepare_submenus(self, items: List[MenuItem]) -> None:
        """Prepare submenu items for context menu display."""
        # This method will be called by context menu when creating the menu
        # Store submenu information for later use
        pass

    def _wrap_menu_item(self, item: MenuItem) -> MenuItem:
        """Wrap menu item action to handle execution."""

        def wrapped_action():
            if self._executing:
                return

            self._executing = True

            try:
                # Execute the item through the service
                result = self.prompt_store_service.execute_item(item)

                # Call execution callback if set
                if self.execution_callback:
                    self.execution_callback(result)

                # Handle result
                if not result.success and result.error:
                    self._handle_error(result.error)

            except Exception as e:
                self._handle_error(f"Execution failed: {str(e)}")
            finally:
                self._executing = False

        # Create new item with wrapped action
        wrapped_item = MenuItem(
            id=item.id,
            label=item.label,
            item_type=item.item_type,
            action=wrapped_action,
            data=item.data,
            enabled=item.enabled and not self._executing,
            separator_after=item.separator_after,
            style=item.style
        )

        return wrapped_item

    def _handle_error(self, error_message: str) -> None:
        """Handle error by calling error callback or showing dialog."""
        if self.error_callback:
            self.error_callback(error_message)
        else:
            # Fallback to messagebox
            try:
                import tkinter.messagebox as messagebox
                messagebox.showerror("Error", error_message)
            except Exception:
                print(f"Error: {error_message}")

    def _add_active_prompt_info(self) -> None:
        """Add active prompt selector to the menu."""
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

        # Create active prompt selector item
        active_prompt_item = MenuItem(
            id="active_prompt_selector",
            label=f"Active Prompt: {display_name}",
            item_type=MenuItemType.SYSTEM,
            action=None,  # No direct action, submenu will handle it
            enabled=True,
            separator_after=False,
            style="normal"
        )

        # Store submenu items for this menu item
        active_prompt_item.submenu_items = self._get_prompt_selector_items()

        # Add with separator before
        self.menu_builder.add_separator()
        self.menu_builder.add_items([active_prompt_item])

    def _get_prompt_selector_items(self) -> List[MenuItem]:
        """Get prompt selector submenu items."""
        try:
            # Get all available prompts
            available_prompts = self.prompt_store_service.get_all_available_prompts()

            if not available_prompts:
                return [MenuItem(
                    id="no_prompts",
                    label="No prompts available",
                    item_type=MenuItemType.SYSTEM,
                    action=lambda: None,
                    enabled=False
                )]

            # Create submenu items
            submenu_items = []
            for prompt_item in available_prompts:
                # Create wrapper action to set active prompt
                def make_set_active_action(item):
                    def set_active():
                        self.prompt_store_service.set_active_prompt(item)
                        # Show confirmation
                        if self.execution_callback:
                            result = ExecutionResult(
                                success=True,
                                content=f"Active prompt set to: {item.label}",
                                metadata={
                                    "action": "set_active_prompt", "prompt": item.label}
                            )
                            self.execution_callback(result)
                    return set_active

                submenu_item = MenuItem(
                    id=f"select_{prompt_item.id}",
                    label=prompt_item.label,
                    item_type=prompt_item.item_type,
                    action=make_set_active_action(prompt_item),
                    enabled=True,
                    separator_after=False
                )
                submenu_items.append(submenu_item)

            return submenu_items

        except Exception as e:
            return [MenuItem(
                id="error_prompts",
                label=f"Error loading prompts: {str(e)}",
                item_type=MenuItemType.SYSTEM,
                action=lambda: None,
                enabled=False
            )]

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.context_menu:
            self.context_menu.destroy()

        self.providers.clear()
        self.menu_builder.clear()


class MenuEventHandler:
    """Handles menu-related events and callbacks."""

    def __init__(self, coordinator: MenuCoordinator):
        self.coordinator = coordinator
        self.execution_results: List[ExecutionResult] = []
        self.max_results = 50
        self.notification_manager: Optional[NotificationManager] = None

    def set_notification_manager(self, notification_manager: NotificationManager) -> None:
        """Set the notification manager."""
        self.notification_manager = notification_manager

    def handle_execution_result(self, result: ExecutionResult) -> None:
        """Handle execution result."""
        # Store result in history
        self.execution_results.append(result)
        if len(self.execution_results) > self.max_results:
            self.execution_results.pop(0)

        # Log result
        if result.success:
            print(f"Execution successful: {result.metadata}")
        else:
            print(f"Execution failed: {result.error}")

            # Show info notification for "no active prompt" case
            if self.notification_manager and result.error_code == ErrorCode.NO_ACTIVE_PROMPT:
                self.notification_manager.show_info_notification(
                    "No Default Prompt",
                    "Select an active prompt first using the menu"
                )

    def handle_error(self, error_message: str) -> None:
        """Handle error message."""
        print(f"Menu error: {error_message}")

        # Show error dialog if possible
        try:
            import tkinter.messagebox as messagebox
            messagebox.showerror("Menu Error", error_message)
        except Exception:
            pass

    def get_recent_results(self, count: int = 10) -> List[ExecutionResult]:
        """Get recent execution results."""
        return self.execution_results[-count:] if self.execution_results else []

    def clear_results(self) -> None:
        """Clear execution results history."""
        self.execution_results.clear()


class MenuState:
    """Manages menu state and configuration."""

    def __init__(self):
        self.is_visible = False
        self.last_shown = 0.0
        self.position = (0, 0)
        self.items_count = 0
        self.providers_count = 0
        self.config: Dict[str, Any] = {
            'auto_hide_delay': 30.0,  # seconds
            'min_show_interval': 0.5,  # seconds between shows
            'max_items_per_provider': 20,
            'enable_keyboard_navigation': True,
            'enable_mouse_navigation': True,
        }

    def can_show_menu(self) -> bool:
        """Check if menu can be shown based on timing constraints."""
        current_time = time.time()
        min_interval = self.config.get('min_show_interval', 0.5)
        return current_time - self.last_shown >= min_interval

    def mark_shown(self, position: tuple, items_count: int) -> None:
        """Mark menu as shown."""
        self.is_visible = True
        self.last_shown = time.time()
        self.position = position
        self.items_count = items_count

    def mark_hidden(self) -> None:
        """Mark menu as hidden."""
        self.is_visible = False
        self.position = (0, 0)
        self.items_count = 0

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)

    def set_config(self, key: str, value: Any) -> None:
        """Set configuration value."""
        self.config[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary."""
        return {
            'is_visible': self.is_visible,
            'last_shown': self.last_shown,
            'position': self.position,
            'items_count': self.items_count,
            'providers_count': self.providers_count,
            'config': self.config.copy(),
        }
