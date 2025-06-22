"""Main application class for the prompt store application."""

import sys
import signal
import time
import tkinter as tk
import queue
from typing import Optional

from core.services import PromptStoreService
from core.exceptions import ConfigurationError
from providers.menu_providers import (
    PromptMenuProvider,
    PresetMenuProvider,
    HistoryMenuProvider,
    SystemMenuProvider,
)
from providers.prompt_providers import APIPromptProvider
from providers.execution_handlers import (
    PromptExecutionHandler,
    PresetExecutionHandler,
    HistoryExecutionHandler,
    SystemExecutionHandler,
)
from gui.menu_coordinator import MenuCoordinator, MenuEventHandler
from gui.hotkey_manager import HotkeyManager
from utils.clipboard import SystemClipboardManager
from utils.config import load_config, validate_config
from utils.system import check_macos_permissions, show_macos_permissions_help
from utils.notifications import NotificationManager
from api import PromptStoreAPI


class PromptStoreApp:
    """Main application class for the prompt store."""

    def __init__(self, config_file: Optional[str] = None):
        self.config = None
        self.running = False
        self.root: Optional[tk.Tk] = None
        self.hotkey_queue = queue.Queue()

        # Core services
        self.api: Optional[PromptStoreAPI] = None
        self.clipboard_manager: Optional[SystemClipboardManager] = None
        self.prompt_store_service: Optional[PromptStoreService] = None

        # Providers
        self.prompt_provider: Optional[APIPromptProvider] = None
        self.menu_providers = []

        # GUI components
        self.hotkey_manager: Optional[HotkeyManager] = None
        self.menu_coordinator: Optional[MenuCoordinator] = None
        self.event_handler: Optional[MenuEventHandler] = None

        # Load configuration
        self._load_config(config_file)

        # Initialize components
        self._initialize_components()
        self._setup_signal_handlers()

    def _load_config(self, config_file: Optional[str] = None) -> None:
        """Load and validate configuration."""
        try:
            self.config = load_config(config_file)
            validate_config(self.config)
        except ConfigurationError as e:
            print(f"Configuration error: {e}")
            sys.exit(1)

    def _initialize_components(self) -> None:
        """Initialize all application components."""
        try:
            # Initialize API client
            self.api = PromptStoreAPI(
                self.config.base_url, self.config.api_key)

            # Initialize clipboard manager
            self.clipboard_manager = SystemClipboardManager()

            # Initialize prompt provider
            self.prompt_provider = APIPromptProvider(self.api)

            # Initialize core service
            self.prompt_store_service = PromptStoreService(
                self.prompt_provider, self.clipboard_manager
            )

            # Initialize GUI components first
            self._initialize_gui()

            # Register execution handlers after GUI is ready
            self._register_execution_handlers()

            # Initialize menu providers
            self._initialize_menu_providers()

        except Exception as e:
            print(f"Failed to initialize application: {e}")
            sys.exit(1)

    def _register_execution_handlers(self) -> None:
        """Register execution handlers with the service."""
        handlers = [
            PromptExecutionHandler(
                self.api, self.clipboard_manager, self.root),
            PresetExecutionHandler(
                self.api, self.clipboard_manager, self.root),
            HistoryExecutionHandler(self.clipboard_manager),
            SystemExecutionHandler(
                refresh_callback=self._refresh_data,
                main_root=self.root
            ),
        ]

        for handler in handlers:
            self.prompt_store_service.execution_service.register_handler(
                handler)

    def _initialize_gui(self) -> None:
        """Initialize GUI components."""
        # Create hidden root window
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.attributes("-alpha", 0.01)

        # Initialize hotkey manager
        self.hotkey_manager = HotkeyManager(self.config.hotkey)
        self.hotkey_manager.set_callback(self._on_hotkey_pressed)
        self.hotkey_manager.set_f2_callback(self._on_f2_hotkey_pressed)

        # Initialize menu coordinator
        self.menu_coordinator = MenuCoordinator(self.prompt_store_service)
        self.menu_coordinator.set_root(self.root)
        self.menu_coordinator.set_menu_position_offset(
            self.config.menu_position_offset)

        # Initialize event handler
        self.event_handler = MenuEventHandler(self.menu_coordinator)

        # Initialize notification manager for event handler
        notification_manager = NotificationManager(self.root)
        self.event_handler.set_notification_manager(notification_manager)

        self.menu_coordinator.set_execution_callback(
            self.event_handler.handle_execution_result
        )
        self.menu_coordinator.set_error_callback(
            self.event_handler.handle_error
        )

    def _initialize_menu_providers(self) -> None:
        """Initialize menu providers."""
        data_manager = self.prompt_store_service.data_manager
        history_service = self.prompt_store_service.history_service

        # Create menu providers
        self.menu_providers = [
            PromptMenuProvider(data_manager, self._execute_menu_item),
            PresetMenuProvider(data_manager, self._execute_menu_item),
            HistoryMenuProvider(history_service, self._execute_menu_item),
            SystemMenuProvider(self._refresh_data),
        ]

        # Register providers with coordinator
        for provider in self.menu_providers:
            self.menu_coordinator.add_provider(provider)

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            print(f"\nReceived signal {signum}, shutting down...")
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _on_hotkey_pressed(self) -> None:
        """Handle hotkey press event."""
        # Put hotkey event in queue for main thread to process
        try:
            self.hotkey_queue.put_nowait("show_menu")
        except queue.Full:
            pass  # Ignore if queue is full

    def _on_f2_hotkey_pressed(self) -> None:
        """Handle Shift+F2 hotkey press event."""
        # Put F2 hotkey event in queue for main thread to process
        try:
            self.hotkey_queue.put_nowait("execute_active_prompt")
        except queue.Full:
            pass  # Ignore if queue is full

    def _execute_menu_item(self, item) -> None:
        """Execute a menu item (placeholder for provider callbacks)."""
        # This is handled by the menu coordinator's wrapped actions
        pass

    def _refresh_data(self) -> None:
        """Refresh all data from providers."""
        try:
            self.prompt_store_service.refresh_data()
            self.menu_coordinator.refresh_providers()
            print("Data refreshed successfully")
        except Exception as e:
            print(f"Failed to refresh data: {e}")

    def _execute_active_prompt(self) -> None:
        """Execute the active prompt with current clipboard content."""
        try:
            result = self.prompt_store_service.execute_active_prompt()
            if self.event_handler:
                self.event_handler.handle_execution_result(result)
        except Exception as e:
            if self.event_handler:
                self.event_handler.handle_error(
                    f"Failed to execute active prompt: {e}")
            else:
                print(f"Failed to execute active prompt: {e}")

    def run(self) -> None:
        """Run the application."""
        print("Starting Prompt Store Service...")
        print(f"Hotkey: {self.config.hotkey}")
        print("Shift+F2: Execute active prompt")
        print("Press Ctrl+C to stop\n")

        # Check platform-specific permissions
        if not check_macos_permissions():
            show_macos_permissions_help()

        self.running = True

        try:
            # Start hotkey manager
            self.hotkey_manager.start()

            # Run main loop
            self._run_main_loop()

        except KeyboardInterrupt:
            print("\nShutting down...")
        except Exception as e:
            print(f"Application error: {e}")
        finally:
            self.stop()

    def _run_main_loop(self) -> None:
        """Run the main application loop."""
        while self.running:
            try:
                # Process hotkey events from queue
                self._process_hotkey_queue()

                if self.root and self.root.winfo_exists():
                    self.root.update()

                # Small sleep to prevent high CPU usage
                time.sleep(0.05)

            except tk.TclError:
                # Root window destroyed
                break
            except Exception as e:
                print(f"Main loop error: {e}")
                break

    def _process_hotkey_queue(self) -> None:
        """Process hotkey events from the queue."""
        try:
            while True:
                try:
                    event = self.hotkey_queue.get_nowait()
                    if event == "show_menu" and self.menu_coordinator:
                        self.menu_coordinator.show_menu()
                    elif event == "execute_active_prompt":
                        self._execute_active_prompt()
                except queue.Empty:
                    break
        except Exception as e:
            print(f"Error processing hotkey queue: {e}")

    def stop(self) -> None:
        """Stop the application."""
        self.running = False

        # Stop hotkey manager
        if self.hotkey_manager:
            self.hotkey_manager.stop()

        # Cleanup menu coordinator
        if self.menu_coordinator:
            self.menu_coordinator.cleanup()

        # Destroy root window
        if self.root:
            try:
                self.root.quit()
                self.root.destroy()
            except tk.TclError:
                pass

        print("Application stopped")

    def get_status(self) -> dict:
        """Get application status information."""
        return {
            "running": self.running,
            "hotkey": self.config.hotkey if self.config else None,
            "api_url": self.config.base_url if self.config else None,
            "providers_count": len(self.menu_providers),
            "hotkey_active": self.hotkey_manager.is_running() if self.hotkey_manager else False,
            "last_execution_results": (
                self.event_handler.get_recent_results(
                    5) if self.event_handler else []
            ),
        }

    def reload_config(self, config_file: Optional[str] = None) -> None:
        """Reload configuration and reinitialize components."""
        print("Reloading configuration...")

        # Stop current components
        was_running = self.running
        if was_running:
            self.hotkey_manager.stop()

        try:
            # Reload config
            self._load_config(config_file)

            # Reinitialize hotkey manager with new config
            if self.hotkey_manager:
                self.hotkey_manager.set_hotkey(self.config.hotkey)

            # Update menu position offset
            if self.menu_coordinator:
                self.menu_coordinator.set_menu_position_offset(
                    self.config.menu_position_offset)

            # Restart if was running
            if was_running:
                self.hotkey_manager.start()

            print("Configuration reloaded successfully")

        except Exception as e:
            print(f"Failed to reload configuration: {e}")
            # Try to restore previous state
            if was_running and self.hotkey_manager:
                try:
                    self.hotkey_manager.start()
                except Exception:
                    pass
