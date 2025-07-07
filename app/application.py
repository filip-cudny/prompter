"""Main PyQt5 application class for the prompt store application."""

import sys
import os
import signal
import tempfile
import subprocess
from typing import Optional, List
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, pyqtSignal, QObject

from modules.prompts.prompt_service import PromptStoreService
from core.exceptions import ConfigurationError

from modules.providers.menu_providers import (
    SystemMenuProvider,
)
from modules.prompts.prompt_menu_provider import PromptMenuProvider
from modules.prompts.prompt_provider import PromptProvider
from modules.providers.execution_handlers import (
    PyQtSpeechExecutionHandler,
)

from modules.history.history_menu_provider import HistoryMenuProvider
from modules.prompts.prompt_execution_handler import PromptExecutionHandler
from modules.history.history_execution_handler import HistoryExecutionHandler
from modules.gui.menu_coordinator import PyQtMenuCoordinator, PyQtMenuEventHandler
from modules.gui.hotkey_manager import PyQtHotkeyManager
from modules.utils.clipboard import SystemClipboardManager
from modules.utils.config import load_config, validate_config
from modules.utils.system import check_macos_permissions, show_macos_permissions_help
from modules.utils.notifications import PyQtNotificationManager


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

        # Speech service
        self.speech_service = None
        self.speech_history_service = None

        # Notification daemon
        self.notification_daemon_process = None
        self.notification_daemon_pid_file = None

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

            # Initialize clipboard manager
            self.clipboard_manager = SystemClipboardManager()

            # Initialize prompt providers
            self._initialize_prompt_providers()

            # Start notification daemon (before notification manager)
            self._start_notification_daemon()

            # Initialize notification manager
            self.notification_manager = PyQtNotificationManager(self.app)

            # Initialize speech service
            self._initialize_speech_service()
            self._initialize_history_service()
            # Initialize core service
            self.prompt_store_service = PromptStoreService(
                self.prompt_providers,
                self.clipboard_manager,
                self.notification_manager,
                self.speech_service,
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

            if self.config.speech_to_text_model:
                self.speech_service = SpeechToTextService(
                    api_key=self.config.speech_to_text_model.get("api_key"),
                    base_url=self.config.speech_to_text_model.get("base_url"),
                    transcribe_model=self.config.speech_to_text_model.get("model"),
                )
                self._setup_common_speech_notifications()
            else:
                self.speech_service = None
        except Exception as e:
            self.speech_service = None

    def _initialize_history_service(self) -> None:
        """Initialize unified history service."""
        try:
            from modules.history.history_service import HistoryService

            self.history_service = HistoryService()
        except Exception as e:
            self.history_service = None

    def _setup_common_speech_notifications(self) -> None:
        """Setup common speech notifications that run for all transcriptions."""
        if self.speech_service and self.notification_manager:
            from modules.utils.notifications import format_execution_time

            def _on_transcription_notification(
                transcription: str, duration: float
            ) -> None:
                """Handle common transcription notifications."""
                try:
                    if transcription:
                        notification_message = (
                            f"Processed in {format_execution_time(duration)}"
                        )
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
                self.notification_manager.show_info_notification(
                    "Recording Started",
                    "Click Speech to Text again to stop.",
                )

            def _on_recording_stopped() -> None:
                """Handle recording stopped event."""
                self.notification_manager.show_info_notification(
                    "Processing Audio", "Transcribing your speech to text"
                )

            self.speech_service.set_recording_started_callback(_on_recording_started)
            self.speech_service.set_recording_stopped_callback(_on_recording_stopped)

            self.speech_service.add_transcription_callback(
                _on_transcription_notification, run_always=True
            )

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
                self.notification_manager,
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
                        self.config,
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
        self.hotkey_manager = PyQtHotkeyManager(
            keymap_manager=self.config.keymap_manager
        )
        self.hotkey_manager.connect_context_menu_callback(
            self._on_show_menu_hotkey_pressed
        )
        self.hotkey_manager.connect_re_execute_callback(
            self._on_active_prompt_hotkey_pressed
        )
        self.hotkey_manager.connect_speech_toggle_callback(
            self._on_speech_to_text_hotkey_pressed
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

        history_service = self.prompt_store_service.history_service

        # Create menu providers
        self.menu_providers = [
            PromptMenuProvider(
                self.prompt_store_service,
                self._execute_menu_item,
                self.prompt_store_service,
            ),
            HistoryMenuProvider(
                history_service, self._execute_menu_item, self.prompt_store_service
            ),
            SystemMenuProvider(
                self._speech_to_text,
                self.history_service,
                self._execute_menu_item,
                self.prompt_store_service,
            ),
        ]

        # Register providers with coordinator
        for provider in self.menu_providers:
            self.menu_coordinator.add_provider(provider)

    def _get_settings_prompt_provider(self) -> Optional[PromptProvider]:
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

                if hasattr(self, "menu_coordinator") and self.menu_coordinator:
                    self.menu_coordinator.execution_completed.emit(result)

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
        print("Starting app")
        print("Press Ctrl+C to stop\n")

        # Check platform-specific permissions
        if not check_macos_permissions():
            show_macos_permissions_help()

        self.running = True

        try:
            # Start hotkey manager
            if self.hotkey_manager:
                self.hotkey_manager.start()

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

        # Stop notification daemon
        self._stop_notification_daemon()

        # Hide system tray
        # if self.system_tray:
        #     self.system_tray.hide()

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

            # Reinitialize prompt providers
            self.prompt_providers.clear()
            self._initialize_prompt_providers()

            # Update prompt store service with new primary provider
            if self.prompt_store_service and self.prompt_providers:
                primary_provider = self.prompt_providers[0]
                self.prompt_store_service.primary_provider = primary_provider

            # Reinitialize hotkey manager with new config
            if self.hotkey_manager and self.config and self.config.keymap_manager:
                self.hotkey_manager.reload_config()

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

    def _start_notification_daemon(self) -> bool:
        """Start the notification daemon process."""
        try:
            # Get daemon paths
            current_dir = os.path.dirname(os.path.abspath(__file__))
            daemon_script = os.path.join(
                current_dir, "..", "modules", "utils", "notification_daemon.py"
            )
            daemon_script = os.path.normpath(daemon_script)

            if not os.path.exists(daemon_script):
                print(f"Daemon script not found: {daemon_script}")
                return False

            # Setup paths
            temp_dir = tempfile.gettempdir()
            pipe_path = os.path.join(temp_dir, "prompt_store_notifications")
            app_dir = os.path.dirname(os.path.abspath(__file__))
            self.notification_daemon_pid_file = os.path.join(
                app_dir, "..", ".prompt_store_daemon.pid"
            )
            self.notification_daemon_pid_file = os.path.normpath(
                self.notification_daemon_pid_file
            )

            # Check if daemon is already running
            if self._is_daemon_running():
                print("Notification daemon already running")
                return True

            # Start daemon process
            self.notification_daemon_process = subprocess.Popen(
                [sys.executable, daemon_script],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

            # Wait for daemon to start
            import time

            for _ in range(30):  # Wait up to 3 seconds
                if os.path.exists(pipe_path):
                    print("Notification daemon started successfully")
                    return True
                time.sleep(0.1)

            print("Notification daemon startup timeout")
            return False

        except Exception as e:
            print(f"Failed to start notification daemon: {e}")
            return False

    def _stop_notification_daemon(self) -> None:
        """Stop the notification daemon process."""
        try:
            # Stop by PID file first (more reliable since daemon may be detached)
            temp_dir = tempfile.gettempdir()
            app_dir = os.path.dirname(os.path.abspath(__file__))
            pid_file = os.path.join(app_dir, "..", ".prompt_store_daemon.pid")
            pid_file = os.path.normpath(pid_file)

            if os.path.exists(pid_file):
                try:
                    with open(pid_file, "r") as f:
                        pid = int(f.read().strip())

                    # Send SIGTERM to daemon
                    os.kill(pid, signal.SIGTERM)

                    # Wait for daemon to shut down
                    import time

                    for i in range(20):  # Wait up to 2 seconds
                        try:
                            os.kill(pid, 0)  # Check if process still exists

                            time.sleep(0.1)
                        except OSError:
                            break  # Process is gone
                    else:
                        # Force kill if still running
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except OSError:
                            pass

                except (ValueError, OSError):
                    pass

            # Clean up process reference
            if self.notification_daemon_process:
                try:
                    self.notification_daemon_process.terminate()
                    self.notification_daemon_process.wait(timeout=1)
                except:
                    pass
                finally:
                    self.notification_daemon_process = None

            # Clean up files
            files_to_clean = [
                os.path.join(temp_dir, "prompt_store_notifications"),
                pid_file,
            ]

            for file_path in files_to_clean:
                if os.path.exists(file_path):
                    try:
                        os.unlink(file_path)
                    except OSError:
                        pass

            print("Notification daemon stopped")

        except Exception as e:
            print(f"Error stopping notification daemon: {e}")

    def _is_daemon_running(self) -> bool:
        """Check if the notification daemon is running."""
        temp_dir = tempfile.gettempdir()
        pipe_path = os.path.join(temp_dir, "prompt_store_notifications")
        app_dir = os.path.dirname(os.path.abspath(__file__))
        pid_file = os.path.join(app_dir, "..", ".prompt_store_daemon.pid")
        pid_file = os.path.normpath(pid_file)

        # Check if pipe exists
        if not os.path.exists(pipe_path):
            return False

        # Check if PID file exists and process is running
        if os.path.exists(pid_file):
            try:
                with open(pid_file, "r") as f:
                    pid = int(f.read().strip())

                # Check if process is running
                try:
                    os.kill(
                        pid, 0
                    )  # Signal 0 doesn't kill, just checks if process exists
                    return True
                except OSError:
                    # Process doesn't exist, clean up stale files
                    try:
                        os.unlink(pid_file)
                        if os.path.exists(pipe_path):
                            os.unlink(pipe_path)
                    except OSError:
                        pass
                    return False
            except (ValueError, IOError):
                return False

        return False


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
