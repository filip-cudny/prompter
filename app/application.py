"""Main PyQt5 application class for the prompt store application."""

import sys
import signal
import platform
from typing import Optional, List
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QAction
from PyQt5.QtCore import QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtCore import Qt

from core.services import PromptStoreService
from core.exceptions import ConfigurationError

from modules.providers.menu_providers import (
    PromptMenuProvider,
    PresetMenuProvider,
    HistoryMenuProvider,
    SystemMenuProvider,
)
from modules.providers.settings_menu_provider import (
    SettingsPromptMenuProvider,
    SettingsPresetMenuProvider,
)
from modules.providers.prompt_providers import APIPromptProvider
from modules.providers.settings_prompt_provider import SettingsPromptProvider
from modules.providers.execution_handlers import (
    PyQtPromptExecutionHandler,
    PyQtPresetExecutionHandler,
    PyQtHistoryExecutionHandler,
    PyQtSystemExecutionHandler,
    PyQtSpeechExecutionHandler,
    SettingsPromptExecutionHandler,
    SettingsPresetExecutionHandler,
)
from modules.gui.menu_coordinator import PyQtMenuCoordinator, PyQtMenuEventHandler
from modules.gui.hotkey_manager import PyQtHotkeyManager
from modules.utils.clipboard import SystemClipboardManager
from modules.utils.config import load_config, validate_config
from modules.utils.system import check_macos_permissions, show_macos_permissions_help
from modules.utils.notifications import PyQtNotificationManager
from api import PromptStoreAPI


class PromptStoreApp(QObject):
    """Main PyQt5 application class for the prompt store."""

    # Qt signals
    shutdown_requested = pyqtSignal()

    def __init__(self, config_file: Optional[str] = None):
        super().__init__()

        # Create QApplication
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # Initialize variables
        self.config = None
        self.running = False

        # Core services
        self.api: Optional[PromptStoreAPI] = None
        self.clipboard_manager: Optional[SystemClipboardManager] = None
        self.prompt_store_service: Optional[PromptStoreService] = None

        # Providers
        self.prompt_providers: List = []
        self.menu_providers: List = []

        # GUI components
        self.hotkey_manager: Optional[PyQtHotkeyManager] = None
        self.menu_coordinator: Optional[PyQtMenuCoordinator] = None
        self.event_handler: Optional[PyQtMenuEventHandler] = None
        self.notification_manager: Optional[PyQtNotificationManager] = None
        self.system_tray: Optional[QSystemTrayIcon] = None

        # Speech service
        self.speech_service = None

        # Recording state
        self.normal_icon = None
        self.recording_icon = None
        self.is_recording = False

        # Load configuration
        self._load_config(config_file)

        # Initialize components
        self._initialize_components()
        self._setup_signal_handlers()

    def _load_config(self, config_file: Optional[str] = None) -> None:
        """Load and validate configuration."""
        try:
            config = load_config(config_file)
            validate_config(config)
            self.config = config
        except ConfigurationError as e:
            print(f"Configuration error: {e}")
            sys.exit(1)

    def _initialize_components(self) -> None:
        """Initialize all application components."""
        try:
            if not self.config:
                raise RuntimeError("Configuration not loaded")

            # Initialize API client
            self.api = PromptStoreAPI(self.config.base_url, self.config.api_key)

            # Initialize clipboard manager
            self.clipboard_manager = SystemClipboardManager()

            # Initialize prompt providers
            self._initialize_prompt_providers()

            # Initialize notification manager
            self.notification_manager = PyQtNotificationManager(self.app)

            # Initialize speech service
            self._initialize_speech_service()

            # Initialize core service
            self.prompt_store_service = PromptStoreService(
                self.prompt_providers, self.clipboard_manager, self.notification_manager, self.speech_service
            )

            # Initialize GUI components
            self._initialize_gui()

            # Register execution handlers
            self._register_execution_handlers()

            # Initialize menu providers
            self._initialize_menu_providers()

        except Exception as e:
            print(f"Failed to initialize application: {e}")
            sys.exit(1)

    def _initialize_speech_service(self) -> None:
        """Initialize speech-to-text service as singleton."""
        try:
            from modules.utils.speech_to_text import SpeechToTextService

            if self.config.openai_api_key:
                self.speech_service = SpeechToTextService(self.config.openai_api_key)
            else:
                self.speech_service = None
        except Exception as e:
            self.speech_service = None

    def _initialize_prompt_providers(self) -> None:
        """Initialize prompt providers."""
        if not self.api:
            raise RuntimeError("API not initialized")

        # Initialize API prompt provider
        # api_provider = APIPromptProvider(self.api)
        # self.prompt_providers.append(api_provider)

        # Initialize settings prompt provider
        try:
            settings_provider = SettingsPromptProvider()
            self.prompt_providers.append(settings_provider)
        except Exception as e:
            print(f"Warning: Failed to initialize settings prompt provider: {e}")

    def _register_execution_handlers(self) -> None:
        """Register execution handlers with the service."""
        if not self.api or not self.clipboard_manager or not self.prompt_store_service:
            raise RuntimeError("Required services not initialized")

        handlers = [
            PyQtPromptExecutionHandler(
                self.api, self.clipboard_manager, self.notification_manager
            ),
            PyQtPresetExecutionHandler(
                self.api, self.clipboard_manager, self.notification_manager
            ),
            PyQtHistoryExecutionHandler(self.clipboard_manager),
            PyQtSystemExecutionHandler(
                refresh_callback=self._refresh_data,
                notification_manager=self.notification_manager,
            ),
            PyQtSpeechExecutionHandler(
                self.clipboard_manager,
                self.notification_manager,
                self.set_recording_indicator,
                self.prompt_store_service.speech_history_service,
                self._refresh_ui_after_speech,
                self.speech_service,
            ),
        ]

        # Add settings-based execution handlers if available
        settings_provider = self._get_settings_prompt_provider()
        if settings_provider:
            handlers.extend(
                [
                    SettingsPromptExecutionHandler(
                        settings_provider,
                        self.clipboard_manager,
                        self.notification_manager,
                    ),
                    SettingsPresetExecutionHandler(
                        settings_provider,
                        self.clipboard_manager,
                        self.notification_manager,
                    ),
                ]
            )

        for handler in handlers:
            self.prompt_store_service.execution_service.register_handler(handler)

    def _initialize_gui(self) -> None:
        """Initialize GUI components."""
        if not self.config or not self.prompt_store_service:
            raise RuntimeError("Configuration or prompt store service not initialized")

        # Initialize hotkey manager
        self.hotkey_manager = PyQtHotkeyManager()
        self.hotkey_manager.connect_context_menu_callback(self._on_f2_hotkey_pressed)
        self.hotkey_manager.connect_re_execute_callback(self._on_f1_hotkey_pressed)
        self.hotkey_manager.connect_speech_toggle_callback(
            self._on_shift_f1_hotkey_pressed
        )

        # Initialize menu coordinator
        self.menu_coordinator = PyQtMenuCoordinator(self.prompt_store_service, self.app)
        self.menu_coordinator.set_menu_position_offset(self.config.menu_position_offset)

        # Initialize event handler
        self.event_handler = PyQtMenuEventHandler(self.menu_coordinator)
        self.event_handler.set_notification_manager(self.notification_manager)

        # Connect coordinator callbacks
        self.menu_coordinator.set_execution_callback(
            self.event_handler.handle_execution_result
        )
        self.menu_coordinator.set_error_callback(self.event_handler.handle_error)

    def _initialize_menu_providers(self) -> None:
        """Initialize menu providers."""
        if not self.prompt_store_service or not self.menu_coordinator:
            raise RuntimeError("Required services not initialized")

        data_manager = self.prompt_store_service.data_manager
        history_service = self.prompt_store_service.history_service

        # Create menu providers
        self.menu_providers = [
            PromptMenuProvider(data_manager, self._execute_menu_item),
            PresetMenuProvider(data_manager, self._execute_menu_item),
            HistoryMenuProvider(history_service, self._execute_menu_item),
            SystemMenuProvider(
                self._refresh_data,
                self._speech_to_text,
                self.prompt_store_service.speech_history_service,
                self._execute_menu_item,
            ),
        ]

        # Add settings-based menu providers if available
        settings_provider = self._get_settings_prompt_provider()
        if settings_provider:
            self.menu_providers.extend(
                [
                    # SettingsPromptMenuProvider(
                    #     settings_provider, self._execute_menu_item
                    # ),
                    # SettingsPresetMenuProvider(
                    #     settings_provider, self._execute_menu_item
                    # ),
                ]
            )

        # Register providers with coordinator
        for provider in self.menu_providers:
            self.menu_coordinator.add_provider(provider)

    def _get_settings_prompt_provider(self) -> Optional[SettingsPromptProvider]:
        """Get the SettingsPromptProvider from the initialized providers."""
        for provider in self.prompt_providers:
            if isinstance(provider, SettingsPromptProvider):
                return provider
        return None

    def _create_tray_icon(self, color) -> QIcon:
        """Create a system tray icon with the specified color."""
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setBrush(color)
        painter.drawEllipse(0, 0, 16, 16)
        painter.end()
        return QIcon(pixmap)

    def set_recording_indicator(self, recording: bool) -> None:
        """Update system tray icon to show recording status."""
        if self.system_tray:
            if recording and not self.is_recording:
                self.system_tray.setIcon(self.recording_icon)
                self.system_tray.setToolTip("Prompt Store - Recording...")
                self.is_recording = True
            elif not recording and self.is_recording:
                self.system_tray.setIcon(self.normal_icon)
                system = platform.system()
                hotkey = "Cmd+F1" if system == "Darwin" else "Ctrl+F1"
                self.system_tray.setToolTip(
                    f"Prompt Store - {hotkey} for menu, Shift+F1 for speech"
                )
                self.is_recording = False

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        # Set up Unix signal handling using Qt's mechanism
        if hasattr(signal, "SIGINT"):
            signal.signal(signal.SIGINT, self._unix_signal_handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, self._unix_signal_handler)

        # Enable keyboard interrupt processing
        QTimer.singleShot(0, self._enable_keyboard_interrupt)

        # Connect Qt signal
        self.shutdown_requested.connect(self.stop)

    def _unix_signal_handler(self, signum, _frame):
        """Handle Unix signals by emitting Qt signal."""
        print(f"\nReceived signal {signum}, shutting down...")
        self.shutdown_requested.emit()

    def _enable_keyboard_interrupt(self):
        """Enable keyboard interrupt handling by processing events periodically."""
        # Create a timer that processes events to allow Ctrl+C to work
        self.interrupt_timer = QTimer()
        self.interrupt_timer.timeout.connect(lambda: None)  # Just process events
        self.interrupt_timer.start(100)  # Check every 100ms

    def _tray_activated(self, reason):
        """Handle system tray activation."""
        if reason == QSystemTrayIcon.Trigger:
            self._on_hotkey_pressed()

    def _on_hotkey_pressed(self) -> None:
        """Handle context menu hotkey press event."""
        if self.menu_coordinator:
            self.menu_coordinator.show_menu()

    def _on_f1_hotkey_pressed(self) -> None:
        """Handle F1 hotkey press event for executing active prompt."""
        # Use QTimer.singleShot to ensure execution on main Qt thread
        QTimer.singleShot(0, self._execute_active_prompt)

    def _on_f2_hotkey_pressed(self) -> None:
        """Handle F2 hotkey press event for showing context menu."""

        # Use QTimer.singleShot to ensure execution on main Qt thread
        def show_menu():
            if self.menu_coordinator:
                self.menu_coordinator.show_menu()

        QTimer.singleShot(0, show_menu)

    def _on_shift_f1_hotkey_pressed(self) -> None:
        """Handle Shift+F1 hotkey press event for speech-to-text toggle."""
        # Use QTimer.singleShot to ensure execution on main Qt thread
        QTimer.singleShot(0, self._speech_to_text)

    def _execute_menu_item(self, item) -> None:
        """Execute a menu item (placeholder for provider callbacks)."""
        # This is handled by the menu coordinator's wrapped actions
        return

    def _refresh_data(self) -> None:
        """Refresh all data from providers."""
        try:
            if self.prompt_store_service:
                self.prompt_store_service.refresh_data()
            if self.menu_coordinator:
                self.menu_coordinator.refresh_providers()
            print("Data refreshed successfully")
        except Exception as e:
            print(f"Failed to refresh data: {e}")

    def _refresh_ui_after_speech(self) -> None:
        """Refresh UI after speech-to-text completion to show 'Copy last speech' item."""
        try:
            if self.menu_coordinator:
                self.menu_coordinator.force_rebuild_dynamic_items()
        except Exception as e:
            print(f"Failed to refresh UI after speech: {e}")

    def _speech_to_text(self) -> None:
        """Handle speech-to-text action."""
        try:
            from core.models import MenuItem, MenuItemType

            # Create speech-to-text menu item
            speech_item = MenuItem(
                id="system_speech_to_text",
                label="Speech to Text",
                item_type=MenuItemType.SPEECH,
                action=lambda: None,
                data={"type": "speech_to_text"},
                enabled=True,
            )

            # Execute the speech item through the prompt store service
            if self.prompt_store_service:
                result = self.prompt_store_service.execute_item(speech_item)

                # Handle the result through the event handler if available
                if hasattr(self, "event_handler") and self.event_handler:
                    self.event_handler.handle_execution_result(result)
                elif not result.success:
                    # Fallback error handling
                    if self.notification_manager:
                        self.notification_manager.show_error_notification(
                            "Speech Error", result.error or "Unknown error occurred"
                        )
                    else:
                        print(f"Speech-to-text error: {result.error}")

        except Exception as e:
            error_msg = f"Failed to execute speech-to-text: {e}"
            if self.notification_manager:
                self.notification_manager.show_error_notification(
                    "Speech Error", error_msg
                )
            else:
                print(error_msg)

    def _execute_active_prompt(self) -> None:
        """Execute the active prompt with current clipboard content."""
        try:
            if not self.prompt_store_service:
                print("Prompt store service not initialized")
                return

            result = self.prompt_store_service.execute_active_prompt()

            # Clear menu cache only (no auto-refresh)
            if self.menu_coordinator:
                self.menu_coordinator._clear_menu_cache()

            if self.event_handler:
                self.event_handler.handle_execution_result(result)
        except Exception as e:
            if self.event_handler:
                self.event_handler.handle_error(f"Failed to execute active prompt: {e}")
            else:
                print(f"Failed to execute active prompt: {e}")

    def run(self) -> int:
        """Run the application."""
        print("Starting Prompt Store...")
        system = platform.system()
        hotkey_f1 = "Cmd+F1" if system == "Darwin" else "Ctrl+F1"
        hotkey_f2 = "Cmd+F2" if system == "Darwin" else "Ctrl+F2"
        print(f"Execute Active Prompt: {hotkey_f1}")
        print(f"Context Menu: {hotkey_f2}")
        print("Speech-to-Text Toggle: Shift+F1")
        print("Press Ctrl+C to stop\n")

        # Check platform-specific permissions
        if not check_macos_permissions():
            show_macos_permissions_help()

        self.running = True

        try:
            # Start hotkey manager
            if self.hotkey_manager:
                self.hotkey_manager.start()

            # Show system tray message
            if self.system_tray:
                self.system_tray.showMessage(
                    "Prompt Store Started",
                    f"Press {hotkey_f1} to show menu",
                    QSystemTrayIcon.Information,
                    2000,
                )

            # Run the Qt event loop
            return self.app.exec_()

        except KeyboardInterrupt:
            print("\nShutting down...")
            self.stop()
            return 0
        except Exception as e:
            print(f"Application error: {e}")
            self.stop()
            return 1

    def stop(self) -> None:
        """Stop the application."""
        if not self.running:
            return

        self.running = False
        print("Stopping application...")

        # Stop interrupt timer
        if hasattr(self, "interrupt_timer"):
            self.interrupt_timer.stop()

        # Stop hotkey manager
        if self.hotkey_manager:
            self.hotkey_manager.stop()

        # Cleanup menu coordinator
        if self.menu_coordinator:
            self.menu_coordinator.cleanup()

        # Hide system tray
        if self.system_tray:
            self.system_tray.hide()

        # Quit application
        if self.app:
            QTimer.singleShot(100, self.app.quit)

        print("Application stopped")

    def get_status(self) -> dict:
        """Get application status information."""
        return {
            "running": self.running,
            "hotkey": self.config.hotkey if self.config else None,
            "api_url": self.config.base_url if self.config else None,
            "prompt_providers_count": len(self.prompt_providers),
            "menu_providers_count": len(self.menu_providers),
            "hotkey_active": self.hotkey_manager.is_running()
            if self.hotkey_manager
            else False,
            "last_execution_results": (
                self.event_handler.get_recent_results(5) if self.event_handler else []
            ),
        }

    def get_prompt_providers_info(self) -> List[dict]:
        """Get information about available prompt providers."""
        providers_info = []
        for i, provider in enumerate(self.prompt_providers):
            provider_info = {
                "index": i,
                "type": type(provider).__name__,
                "is_primary": i == 0,
            }

            if hasattr(provider, "get_info"):
                provider_info.update(provider.get_info())

            providers_info.append(provider_info)

        return providers_info

    def add_prompt_provider(self, provider) -> bool:
        """Add a new prompt provider to the list."""
        try:
            if provider not in self.prompt_providers:
                self.prompt_providers.append(provider)
                print(f"Added prompt provider: {type(provider).__name__}")
                return True
            else:
                print(f"Provider already exists: {type(provider).__name__}")
                return False
        except Exception as e:
            print(f"Failed to add prompt provider: {e}")
            return False

    def remove_prompt_provider(self, provider_index: int) -> bool:
        """Remove a prompt provider by index."""
        try:
            if 0 <= provider_index < len(self.prompt_providers):
                if provider_index == 0 and len(self.prompt_providers) > 1:
                    print("Cannot remove primary provider when other providers exist")
                    return False

                removed_provider = self.prompt_providers.pop(provider_index)
                print(f"Removed prompt provider: {type(removed_provider).__name__}")

                # Update primary provider in service if we removed the first one
                if (
                    provider_index == 0
                    and self.prompt_store_service
                    and self.prompt_providers
                ):
                    self.prompt_store_service.primary_provider = self.prompt_providers[
                        0
                    ]

                return True
            else:
                print(f"Invalid provider index: {provider_index}")
                return False
        except Exception as e:
            print(f"Failed to remove prompt provider: {e}")
            return False

    def set_primary_prompt_provider(self, provider_index: int) -> bool:
        """Set a prompt provider as primary by moving it to index 0."""
        try:
            if 0 <= provider_index < len(self.prompt_providers):
                if provider_index != 0:
                    provider = self.prompt_providers.pop(provider_index)
                    self.prompt_providers.insert(0, provider)

                    # Update service with new primary provider
                    if self.prompt_store_service:
                        self.prompt_store_service.primary_provider = provider

                    print(f"Set primary prompt provider: {type(provider).__name__}")
                return True
            else:
                print(f"Invalid provider index: {provider_index}")
                return False
        except Exception as e:
            print(f"Failed to set primary prompt provider: {e}")
            return False

    def reload_config(self, config_file: Optional[str] = None) -> None:
        """Reload configuration and reinitialize components."""
        print("Reloading configuration...")

        # Stop current components
        was_running = self.running
        if was_running and self.hotkey_manager:
            self.hotkey_manager.stop()

        try:
            # Reload config
            self._load_config(config_file)

            # Reinitialize API with new config
            if self.config:
                self.api = PromptStoreAPI(self.config.base_url, self.config.api_key)

            # Reinitialize prompt providers
            self.prompt_providers.clear()
            self._initialize_prompt_providers()

            # Update prompt store service with new primary provider
            if self.prompt_store_service and self.prompt_providers:
                primary_provider = self.prompt_providers[0]
                self.prompt_store_service.primary_provider = primary_provider

            # Reinitialize hotkey manager with new config
            if self.hotkey_manager and self.config:
                self.hotkey_manager.set_hotkey(self.config.hotkey)

            # Update menu position offset
            if self.menu_coordinator and self.config:
                self.menu_coordinator.set_menu_position_offset(
                    self.config.menu_position_offset
                )

            # Restart if was running
            if was_running and self.hotkey_manager:
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


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Prompt Store PyQt5 Application")
    parser.add_argument("--config", "-c", help="Configuration file path")
    args = parser.parse_args()

    app = PromptStoreApp(args.config)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
