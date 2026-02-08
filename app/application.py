"""Main PySide6 application class for the Promptheus application."""

import contextlib
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPalette, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QToolTip

from core.context_manager import ContextManager
from core.exceptions import ConfigurationError
from core.openai_service import OpenAiService
from modules.context.context_menu_provider import ContextMenuProvider
from modules.gui.hotkey_manager import PyQtHotkeyManager
from modules.gui.menu_coordinator import PyQtMenuCoordinator, PyQtMenuEventHandler
from modules.gui.shared import MENU_STYLESHEET, TOOLTIP_STYLE
from modules.history.history_execution_handler import HistoryExecutionHandler
from modules.history.last_interaction_menu_provider import LastInteractionMenuProvider
from modules.prompts.prompt_execution_handler import PromptExecutionHandler
from modules.prompts.prompt_menu_provider import PromptMenuProvider
from modules.prompts.prompt_provider import PromptProvider
from modules.prompts.prompt_service import PromptStoreService
from modules.speech.speech_execution_handler import (
    PyQtSpeechExecutionHandler,
)
from modules.speech.speech_menu_provider import (
    SpeechMenuProvider,
)
from modules.utils.clipboard import SystemClipboardManager
from modules.utils.config import ConfigService, load_config, validate_config
from modules.utils.keymap_actions import initialize_global_action_registry
from modules.utils.notification_config import is_notification_enabled
from modules.utils.notifications import PyQtNotificationManager


def _write_startup_debug_log() -> None:
    """Write startup debug info to help diagnose config loading issues."""
    from modules.utils.paths import get_settings_file, get_user_config_dir, is_frozen

    debug_log_path = Path.home() / ".config" / "promptheus" / "debug.log"
    debug_log_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"\n{'=' * 60}",
        f"Startup Debug Log - {datetime.now().isoformat()}",
        f"{'=' * 60}",
        f"is_frozen(): {is_frozen()}",
        f"sys.frozen attr: {getattr(sys, 'frozen', 'NOT SET')}",
        f"sys._MEIPASS attr: {getattr(sys, '_MEIPASS', 'NOT SET')}",
        f"Path.home(): {Path.home()}",
        f"os.environ.get('HOME'): {os.environ.get('HOME', 'NOT SET')}",
        f"os.environ.get('XDG_CONFIG_HOME'): {os.environ.get('XDG_CONFIG_HOME', 'NOT SET')}",
        f"get_user_config_dir(): {get_user_config_dir()}",
        f"get_settings_file(): {get_settings_file()}",
        f"Settings file exists: {get_settings_file().exists()}",
        f"sys.executable: {sys.executable}",
        f"sys.argv: {sys.argv}",
        f"os.getcwd(): {os.getcwd()}",
        "",
        "--- Display Server Info (for hotkey diagnostics) ---",
        f"DISPLAY: {os.environ.get('DISPLAY', 'NOT SET')}",
        f"WAYLAND_DISPLAY: {os.environ.get('WAYLAND_DISPLAY', 'NOT SET')}",
        f"XDG_SESSION_TYPE: {os.environ.get('XDG_SESSION_TYPE', 'NOT SET')}",
        f"sys.platform: {sys.platform}",
    ]

    settings_file = get_settings_file()
    if settings_file.exists():
        try:
            import json

            with open(settings_file) as f:
                settings = json.load(f)
            keys = list(settings.keys())[:10]
            lines.append(f"Settings keys (first 10): {keys}")
            if "default_model" in settings:
                lines.append(f"default_model value: {settings['default_model']}")
        except Exception as e:
            lines.append(f"Error reading settings: {e}")

    lines.append(f"{'=' * 60}\n")

    with open(debug_log_path, "a") as f:
        f.write("\n".join(lines))


class PromtheusApp(QObject):
    """Main PySide6 application class for Promptheus."""

    # Qt signals
    shutdown_requested = Signal()

    def __init__(self, config_file: str | None = None):
        super().__init__()

        # Write debug log at very start of initialization
        _write_startup_debug_log()

        # Create QApplication (Qt6 handles HiDPI automatically)
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # Apply global tooltip styling (affects all tooltips in the app)
        self.app.setStyleSheet(TOOLTIP_STYLE)

        # Also set tooltip palette to ensure consistent colors across all widgets
        tooltip_palette = QPalette()
        tooltip_palette.setColor(QPalette.ToolTipBase, QColor("#0d0d0d"))
        tooltip_palette.setColor(QPalette.ToolTipText, QColor("#f0f0f0"))
        QToolTip.setPalette(tooltip_palette)

        # Initialize variables
        self.config = None
        self.running = False

        # Core services
        self.clipboard_manager: SystemClipboardManager | None = None
        self.context_manager: ContextManager | None = None
        self.openai_service: OpenAiService | None = None
        self.prompt_store_service: PromptStoreService | None = None
        self._pending_api_key_warning: str | None = None

        # Providers
        self.prompt_providers: list = []
        self.menu_providers: list = []

        # GUI components
        self.hotkey_manager: PyQtHotkeyManager | None = None
        self.menu_coordinator: PyQtMenuCoordinator | None = None
        self.event_handler: PyQtMenuEventHandler | None = None
        self.notification_manager: PyQtNotificationManager | None = None

        # Speech service
        self.speech_service = None
        self.speech_history_service = None

        # System tray
        self.system_tray: QSystemTrayIcon | None = None
        self.tray_menu: QMenu | None = None

        # Initialize basic services needed for config loading
        self._initialize_basic_services()

        # Load configuration
        self._load_config(config_file)

        # Initialize components
        self._initialize_components()
        self._setup_signal_handlers()

    def _load_config(self, config_file: str | None = None) -> None:
        """Load and validate configuration."""
        try:
            config = load_config(config_file)
            validate_config(config)
            self.config = config
        except ConfigurationError as e:
            print(f"Configuration error: {e}")
            sys.exit(1)

    def _initialize_basic_services(self) -> None:
        """Initialize basic services needed for configuration loading."""
        # Initialize clipboard manager
        self.clipboard_manager = SystemClipboardManager()

        # Initialize context manager
        self.context_manager = ContextManager()

        # Initialize global action registry with managers
        initialize_global_action_registry(self.context_manager, self.clipboard_manager)

    def _initialize_components(self) -> None:
        """Initialize all application components."""
        try:
            if not self.config:
                raise RuntimeError("Configuration not loaded")

            # Initialize prompt providers
            self._initialize_prompt_providers()

            # Initialize notification manager
            self.notification_manager = PyQtNotificationManager(self.app)

            # Re-initialize global action registry with notification manager
            initialize_global_action_registry(self.context_manager, self.clipboard_manager, self.notification_manager)

            # Initialize OpenAI service
            self._initialize_openai_service()

            # Initialize speech service
            self._initialize_speech_service()
            self._initialize_history_service()

            # Initialize core service
            self.prompt_store_service = PromptStoreService(
                self.prompt_providers,
                self.clipboard_manager,
                self.notification_manager,
                self.speech_service,
                self.openai_service,
                self.context_manager,
                self.history_service,
            )

            # Register callback to invalidate prompt cache when settings are saved
            config_service = ConfigService()
            config_service.register_on_save_callback(self.prompt_store_service.invalidate_cache)
            config_service.register_on_save_callback(self._reload_hotkeys)

            # Initialize GUI components
            self._initialize_gui()

            # Initialize system tray if enabled
            self._initialize_system_tray()

            # Register execution handlers
            self._register_execution_handlers()

            # Initialize menu providers
            self._initialize_menu_providers()

            # Show warning notification if API key is missing (delayed to ensure notification manager is ready)
            if self._pending_api_key_warning and self.notification_manager:
                QTimer.singleShot(500, lambda: self._show_api_key_warning())

        except Exception as e:
            print(f"Failed to initialize application: {e}")
            sys.exit(1)

    def _initialize_openai_service(self) -> None:
        """Initialize OpenAI service with all model configurations."""
        if not self.config or not self.config.models:
            self._pending_api_key_warning = "No AI models configured in settings"
            return

        self.openai_service = OpenAiService(
            models_config=self.config.models,
            speech_to_text_config=self.config.speech_to_text_model,
        )

        default_model = self.config.default_model
        if default_model and not self.openai_service.has_model(default_model):
            reason = self.openai_service.get_model_unavailable_reason(default_model)
            if reason and "Missing API key" in reason:
                display_name = default_model
                for model in self.config.models:
                    if model.get("id") == default_model:
                        display_name = model.get("display_name", default_model)
                        break
                self._pending_api_key_warning = (
                    f"Default model '{display_name}' unavailable: API key not configured. "
                    "Set OPENAI_API_KEY in ~/.config/promptheus/.env"
                )

    def _initialize_speech_service(self) -> None:
        """Initialize speech-to-text service as singleton."""
        try:
            from modules.utils.speech_to_text import SpeechToTextService

            if self.config and self.config.speech_to_text_model and self.openai_service:
                self.speech_service = SpeechToTextService(openai_service=self.openai_service)
                self._setup_common_speech_notifications()
            else:
                self.speech_service = None
        except Exception:
            self.speech_service = None

    def _initialize_history_service(self) -> None:
        """Initialize unified history service."""
        try:
            from modules.history.history_service import HistoryService

            self.history_service = HistoryService()
            self.history_service.initialize()  # Clear temp images on startup
        except Exception:
            self.history_service = None

    def _setup_common_speech_notifications(self) -> None:
        """Setup common speech notifications that run for all transcriptions."""
        if self.speech_service and self.notification_manager:
            from modules.utils.notifications import format_execution_time

            def _on_transcription_notification(transcription: str, duration: float) -> None:
                """Handle common transcription notifications."""
                try:
                    if transcription:
                        if is_notification_enabled("speech_transcription_success"):
                            notification_message = f"Processed in {format_execution_time(duration)}"
                            self.notification_manager.show_success_notification(
                                "Transcription completed", notification_message
                            )
                    else:
                        self.notification_manager.show_info_notification(
                            "No Speech Detected",
                            "No speech was detected in the recording",
                        )
                except Exception as e:
                    self.notification_manager.show_error_notification(
                        "Notification Error",
                        f"Failed to show transcription notification: {str(e)}",
                    )

            def _on_recording_started() -> None:
                """Handle recording started event."""
                if is_notification_enabled("speech_recording_start"):
                    self.notification_manager.show_info_notification(
                        "Recording Started",
                        "Click Speech to Text again to stop.",
                    )

            def _on_recording_stopped() -> None:
                """Handle recording stopped event."""
                if is_notification_enabled("speech_recording_stop"):
                    self.notification_manager.show_info_notification(
                        "Processing Audio", "Transcribing your speech to text"
                    )

            self.speech_service.set_recording_started_callback(_on_recording_started)
            self.speech_service.set_recording_stopped_callback(_on_recording_stopped)

            self.speech_service.add_transcription_callback(_on_transcription_notification, run_always=True)

    def _initialize_prompt_providers(self) -> None:
        """Initialize prompt providers."""

        try:
            settings_provider = PromptProvider()
            self.prompt_providers.append(settings_provider)
        except Exception as e:
            print(f"Warning: Failed to initialize settings prompt provider: {e}")

    def _register_execution_handlers(self) -> None:
        """Register execution handlers with the service."""
        if not self.clipboard_manager or not self.prompt_store_service:
            raise RuntimeError("Required services not initialized")

        handlers = [
            HistoryExecutionHandler(
                self.clipboard_manager,
                self.notification_manager,  # type: ignore
            ),
            PyQtSpeechExecutionHandler(
                self.clipboard_manager,
                self.notification_manager,
                self.history_service,
                self.speech_service,
                self.menu_coordinator,
            ),
        ]

        # Add settings-based execution handlers if available
        settings_provider = self._get_settings_prompt_provider()
        if settings_provider:
            handlers.extend(
                [
                    PromptExecutionHandler(
                        settings_provider,
                        self.clipboard_manager,
                        self.notification_manager,
                        self.openai_service,  # type: ignore
                        self.config,  # type: ignore
                        self.context_manager,
                        self.prompt_store_service,
                    ),
                ]
            )

        for handler in handlers:
            self.prompt_store_service.execution_service.register_handler(handler)

    def _initialize_gui(self) -> None:
        """Initialize GUI components."""
        if not self.config or not self.prompt_store_service:
            raise RuntimeError("Configuration or PromptStore service not initialized")

        # Initialize hotkey manager
        self.hotkey_manager = PyQtHotkeyManager(keymap_manager=self.config.keymap_manager)
        self.hotkey_manager.connect_action_callback(self._on_hotkey_action)

        # Initialize menu coordinator
        self.menu_coordinator = PyQtMenuCoordinator(self.prompt_store_service, self.app)
        self.menu_coordinator.set_menu_position_offset(self.config.menu_position_offset)
        self.menu_coordinator.set_number_input_debounce_ms(self.config.number_input_debounce_ms)
        self.menu_coordinator.notification_manager = self.notification_manager
        self.menu_coordinator.set_shutdown_callback(self.stop)

        # Initialize event handler
        self.event_handler = PyQtMenuEventHandler(self.menu_coordinator)
        self.event_handler.set_notification_manager(self.notification_manager)

        # Connect coordinator callbacks
        self.menu_coordinator.set_execution_callback(self.event_handler.handle_execution_result)
        self.menu_coordinator.set_error_callback(self.event_handler.handle_error)

        # Connect context manager for cache invalidation
        self.menu_coordinator.set_context_manager(self.context_manager)

    def _initialize_system_tray(self) -> None:
        """Initialize system tray icon if enabled in settings."""
        config_service = ConfigService()
        settings_data = config_service.get_settings_data()
        show_tray = settings_data.get("show_tray_icon", True)

        if not show_tray:
            return

        try:
            from modules.utils.paths import get_root_icon_path

            icon_path = get_root_icon_path("tray_icon.svg")
            if icon_path.exists():
                icon = QIcon(str(icon_path))
            else:
                icon = self._create_fallback_tray_icon()

            self.system_tray = QSystemTrayIcon(icon, self.app)
            self.system_tray.setToolTip("Promptheus")

            self.tray_menu = QMenu()
            self.tray_menu.setStyleSheet(MENU_STYLESHEET)

            self._tray_show_menu_action = QAction("Show Menu", self.tray_menu)
            self._tray_show_menu_action.triggered.connect(self._on_show_menu_hotkey_pressed)
            self.tray_menu.addAction(self._tray_show_menu_action)

            self._tray_settings_action = QAction("Settings", self.tray_menu)
            self._tray_settings_action.triggered.connect(self._show_settings_dialog)
            self.tray_menu.addAction(self._tray_settings_action)

            self.tray_menu.addSeparator()

            self._tray_quit_action = QAction("Quit", self.tray_menu)
            self._tray_quit_action.triggered.connect(self.stop)
            self.tray_menu.addAction(self._tray_quit_action)

            # On macOS, setContextMenu() creates disabled menu items, so we skip it
            # and handle clicks manually via the activated signal
            if sys.platform != "darwin":
                self.system_tray.setContextMenu(self.tray_menu)
            self.system_tray.activated.connect(self._on_tray_icon_activated)
            self.system_tray.show()

        except Exception as e:
            import logging

            logging.error(f"Failed to initialize system tray: {e}")

    def _create_fallback_tray_icon(self) -> QIcon:
        """Create a simple colored circle as fallback tray icon."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QPainter

        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setBrush(QColor("#4a90d9"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, 16, 16)
        painter.end()
        return QIcon(pixmap)

    def _on_tray_icon_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation - show menu manually on macOS."""
        if sys.platform == "darwin":
            if reason in (
                QSystemTrayIcon.ActivationReason.Trigger,
                QSystemTrayIcon.ActivationReason.Context,
            ):
                from PySide6.QtGui import QCursor

                self.tray_menu.popup(QCursor.pos())

    def _show_settings_dialog(self) -> None:
        """Show the settings dialog."""
        try:
            from modules.gui.settings_dialog.settings_dialog import SettingsDialog

            dialog = SettingsDialog(parent=None)
            dialog.exec()
        except Exception as e:
            import logging

            logging.error(f"Failed to show settings dialog: {e}")

    def _initialize_menu_providers(self) -> None:
        """Initialize menu providers."""
        if not self.prompt_store_service or not self.menu_coordinator:
            raise RuntimeError("Required services not initialized")

        history_service = self.prompt_store_service.history_service

        # Create menu providers
        self.menu_providers = [
            PromptMenuProvider(
                self.prompt_store_service,
                self._execute_menu_item,
                self.prompt_store_service,
            ),
            ContextMenuProvider(
                self.context_manager,
                self._execute_menu_item,
                self.prompt_store_service,
                self.notification_manager,
                self.clipboard_manager,
            ),
            LastInteractionMenuProvider(
                history_service,
                self.notification_manager,
                self.clipboard_manager,
                self.prompt_store_service,
            ),
            SpeechMenuProvider(
                self._speech_to_text,
                self.history_service,
                self._execute_menu_item,
                self.prompt_store_service,
            ),
        ]

        # Register providers with coordinator
        for provider in self.menu_providers:
            self.menu_coordinator.add_provider(provider)

    def _get_settings_prompt_provider(self) -> PromptProvider | None:
        """Get the SettingsPromptProvider from the initialized providers."""
        for provider in self.prompt_providers:
            if isinstance(provider, PromptProvider):
                return provider
        return None

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

    def _on_hotkey_action(self, action_name: str) -> None:
        action_handlers = {
            "open_context_menu": self._on_show_menu_hotkey_pressed,
            "execute_active_prompt": self._on_active_prompt_hotkey_pressed,
            "speech_to_text_toggle": self._on_speech_to_text_hotkey_pressed,
        }
        handler = action_handlers.get(action_name)
        if handler:
            handler()

    def _on_active_prompt_hotkey_pressed(self) -> None:
        """Handle F1 hotkey press event for executing active prompt."""
        # Use QTimer.singleShot to ensure execution on main Qt thread
        QTimer.singleShot(0, self._execute_active_prompt)

    def _on_show_menu_hotkey_pressed(self) -> None:
        """Handle F2 hotkey press event for showing context menu."""

        # Use QTimer.singleShot to ensure execution on main Qt thread
        def show_menu():
            if self.menu_coordinator:
                self.menu_coordinator.show_menu()

        QTimer.singleShot(0, show_menu)

    def _on_speech_to_text_hotkey_pressed(self) -> None:
        """Handle Shift+F1 hotkey press event for speech-to-text toggle."""
        # Use QTimer.singleShot to ensure execution on main Qt thread
        QTimer.singleShot(0, self._speech_to_text)

    def _execute_menu_item(self, item) -> None:
        """Execute a menu item (placeholder for provider callbacks)."""
        return

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

            # Execute the speech item through the PromptStore service
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

                if hasattr(self, "menu_coordinator") and self.menu_coordinator:
                    self.menu_coordinator.execution_completed.emit(result, "")

        except Exception as e:
            error_msg = f"Failed to execute speech-to-text: {e}"
            if self.notification_manager:
                self.notification_manager.show_error_notification("Speech Error", error_msg)
            else:
                print(error_msg)

    def _execute_active_prompt(self) -> None:
        """Execute the active prompt with current clipboard content."""
        try:
            if not self.prompt_store_service:
                print("PromptStore service not initialized")
                return

            result = self.prompt_store_service.execute_active_prompt()

            if self.event_handler:
                self.event_handler.handle_execution_result(result)
        except Exception as e:
            if self.event_handler:
                self.event_handler.handle_error(f"Failed to execute active prompt: {e}")
            else:
                print(f"Failed to execute active prompt: {e}")

    def _show_api_key_warning(self) -> None:
        """Show warning notification about missing API key."""
        if self._pending_api_key_warning and self.notification_manager:
            self.notification_manager.show_warning_notification(
                "API Key Missing",
                self._pending_api_key_warning,
            )
            self._pending_api_key_warning = None

    def run(self) -> int:
        """Run the application."""
        print("Starting app")
        print("Press Ctrl+C to stop\n")

        self.running = True

        # Handle macOS reopen events to prevent multiple launches
        self._setup_macos_app_delegate()

        try:
            # Start hotkey manager
            if self.hotkey_manager:
                self.hotkey_manager.start()

            # Run the Qt event loop
            return self.app.exec()

        except KeyboardInterrupt:
            print("\nShutting down...")
            self.stop()
            return 0
        except Exception as e:
            print(f"Application error: {e}")
            self.stop()
            return 1

    def _setup_macos_app_delegate(self) -> None:
        """Setup macOS app delegate to handle reopen events properly."""
        if sys.platform != "darwin":
            return

        try:
            from AppKit import NSApplication, NSObject

            class AppDelegate(NSObject):
                """macOS app delegate to handle application events."""

                def applicationShouldHandleReopen_hasVisibleWindows_(self, app, flag) -> bool:
                    """Handle reopen events (clicking dock icon, etc).

                    Return False to prevent macOS from trying to reopen/relaunch the app.
                    """
                    return False

                def applicationShouldTerminateAfterLastWindowClosed_(self, app) -> bool:
                    """Prevent app from terminating when last window closes."""
                    return False

            delegate = AppDelegate.alloc().init()
            NSApplication.sharedApplication().setDelegate_(delegate)
            # Keep reference to prevent garbage collection
            self._macos_app_delegate = delegate
        except Exception:
            pass

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

        # Clean up notification manager
        if self.notification_manager:
            self.notification_manager.cleanup()

        # Hide system tray and cleanup menu
        if self.system_tray:
            self.system_tray.hide()
            self.system_tray = None
        if hasattr(self, "tray_menu"):
            self.tray_menu = None

        # Quit application
        if self.app:
            QTimer.singleShot(100, self.app.quit)

        print("Application stopped")

    def get_status(self) -> dict:
        """Get application status information."""
        return {
            "running": self.running,
            "hotkey": (self.hotkey_manager.hotkey if self.hotkey_manager else None),
            "prompt_providers_count": len(self.prompt_providers),
            "menu_providers_count": len(self.menu_providers),
            "hotkey_active": self.hotkey_manager.is_running() if self.hotkey_manager else False,
            "last_execution_results": (self.event_handler.get_recent_results(5) if self.event_handler else []),
        }

    def get_prompt_providers_info(self) -> list[dict]:
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
                if provider_index == 0 and self.prompt_store_service and self.prompt_providers:
                    self.prompt_store_service.primary_provider = self.prompt_providers[0]

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

    def _reload_hotkeys(self) -> None:
        from modules.utils.keymap import KeymapManager

        config_service = ConfigService()
        settings_data = config_service.get_settings_data()
        keymap_manager = KeymapManager(settings_data.get("keymaps", []))

        if self.config:
            self.config.keymap_manager = keymap_manager
        if self.hotkey_manager:
            self.hotkey_manager.keymap_manager = keymap_manager
            self.hotkey_manager.reload_config()

    def reload_config(self, config_file: str | None = None) -> None:
        """Reload configuration and reinitialize components."""
        print("Reloading configuration...")

        # Stop current components
        was_running = self.running
        if was_running and self.hotkey_manager:
            self.hotkey_manager.stop()

        try:
            # Reload config
            self._load_config(config_file)

            # Reinitialize prompt providers
            self.prompt_providers.clear()
            self._initialize_prompt_providers()

            # Update PromptStore service with new primary provider
            if self.prompt_store_service and self.prompt_providers:
                primary_provider = self.prompt_providers[0]
                self.prompt_store_service.primary_provider = primary_provider

            # Reinitialize hotkey manager with new config
            if self.hotkey_manager and self.config and self.config.keymap_manager:
                self.hotkey_manager.reload_config()

            # Update menu position offset
            if self.menu_coordinator and self.config:
                self.menu_coordinator.set_menu_position_offset(self.config.menu_position_offset)
                self.menu_coordinator.set_number_input_debounce_ms(self.config.number_input_debounce_ms)

            # Restart if was running
            if was_running and self.hotkey_manager:
                self.hotkey_manager.start()

            print("Configuration reloaded successfully")

        except Exception as e:
            print(f"Failed to reload configuration: {e}")
            # Try to restore previous state
            if was_running and self.hotkey_manager:
                with contextlib.suppress(Exception):
                    self.hotkey_manager.start()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Promptheus Application")
    parser.add_argument("--config", "-c", help="Configuration file path")
    args = parser.parse_args()

    app = PromtheusApp(args.config)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
