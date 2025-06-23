"""PyQt5-based menu coordinator for the prompt store application."""

from typing import List, Optional, Callable, Tuple, Dict, Any
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtWidgets import QApplication

from core.models import MenuItem, ExecutionResult
from core.exceptions import MenuError
from .pyqt_context_menu import PyQtContextMenu, PyQtMenuBuilder


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
        self.app = QApplication.instance()
        
        # Callbacks
        self.execution_callback: Optional[Callable[[ExecutionResult], None]] = None
        self.error_callback: Optional[Callable[[str], None]] = None
        
        # Menu state
        self.last_menu_items: List[MenuItem] = []
        self.menu_cache: Dict[str, List[MenuItem]] = {}
        self.cache_timeout = 30000  # 30 seconds
        self.cache_timer = QTimer()
        self.cache_timer.timeout.connect(self._clear_menu_cache)
        
        # Connect internal signals
        self.execution_completed.connect(self._handle_execution_result)
        self.execution_error.connect(self._handle_error)

    def add_provider(self, provider) -> None:
        """Add a menu provider."""
        self.providers.append(provider)
        self._clear_menu_cache()

    def remove_provider(self, provider) -> None:
        """Remove a menu provider."""
        if provider in self.providers:
            self.providers.remove(provider)
            self._clear_menu_cache()

    def set_execution_callback(self, callback: Callable[[ExecutionResult], None]) -> None:
        """Set callback for execution results."""
        self.execution_callback = callback

    def set_error_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for errors."""
        self.error_callback = callback

    def set_menu_position_offset(self, offset: Tuple[int, int]) -> None:
        """Set menu positioning offset."""
        self.context_menu.set_menu_position_offset(offset)

    def show_menu(self) -> None:
        """Show the context menu at cursor position."""
        try:
            items = self._get_all_menu_items()
            if not items:
                self._handle_error("No menu items available")
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

    def refresh_providers(self) -> None:
        """Refresh all providers and clear cache."""
        try:
            for provider in self.providers:
                if hasattr(provider, 'refresh'):
                    provider.refresh()
            self._clear_menu_cache()
        except (RuntimeError, Exception) as e:
            self._handle_error(f"Failed to refresh providers: {str(e)}")

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.cache_timer.isActive():
            self.cache_timer.stop()
        
        if self.context_menu:
            self.context_menu.destroy()
        
        self.providers.clear()
        self._clear_menu_cache()

    def _get_all_menu_items(self) -> List[MenuItem]:
        """Get all menu items from providers with caching."""
        cache_key = "all_items"
        
        # Check cache first
        if cache_key in self.menu_cache:
            return self.menu_cache[cache_key]

        # Build menu items
        builder = PyQtMenuBuilder()
        
        try:
            # Get items from each provider
            for provider in self.providers:
                try:
                    provider_items = provider.get_menu_items()
                    if provider_items:
                        # Wrap provider actions to handle execution
                        wrapped_items = self._wrap_provider_items(provider_items)
                        builder.add_items_with_separator(wrapped_items)
                except (RuntimeError, Exception) as e:
                    print(f"Error getting items from provider {provider.__class__.__name__}: {e}")
                    continue

            items = builder.build()
            
            # Cache the items
            self.menu_cache[cache_key] = items
            self._start_cache_timer()
            
            return items
            
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
                action=lambda captured_item=item: self._execute_menu_item(captured_item),
                data=item.data,
                enabled=item.enabled,
                tooltip=getattr(item, 'tooltip', None)
            )
            
            # Copy separator info if present
            if hasattr(item, 'separator_after'):
                wrapped_item.separator_after = item.separator_after
                
            wrapped_items.append(wrapped_item)
            
        return wrapped_items

    def _execute_menu_item(self, item: MenuItem) -> None:
        """Execute a menu item through the prompt store service."""
        try:
            # Execute the item using the service
            result = self.prompt_store_service.execute_item(item)
            
            # Emit signal for thread-safe handling
            self.execution_completed.emit(result)
            
        except (RuntimeError, Exception) as e:
            error_msg = f"Failed to execute menu item '{item.label}': {str(e)}"
            self.execution_error.emit(error_msg)

    def _handle_execution_result(self, result: ExecutionResult) -> None:
        """Handle execution result on main thread."""
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
        """Clear the menu cache."""
        self.menu_cache.clear()
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
            "cache_timeout": self.cache_timeout
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
                    "Execution Error",
                    error_message
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
        # Success handling is typically done by the execution handlers themselves
        # This is here for any additional processing if needed
        return

    def _handle_error_result(self, result: ExecutionResult) -> None:
        """Handle error execution result."""
        if self.notification_manager and result.error:
            # Get prompt/preset name from metadata if available
            prompt_name = None
            if result.metadata:
                prompt_name = (result.metadata.get('prompt_name') or 
                             result.metadata.get('preset_name'))
            
            self.notification_manager.show_error_notification(
                "Execution Failed",
                result.error,
                prompt_name
            )
        else:
            print(f"Execution failed: {result.error}")