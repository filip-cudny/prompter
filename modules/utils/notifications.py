"""PyQt5-based notification utilities."""

from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QWidget,
)
from PyQt5.QtCore import (
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    pyqtSignal,
    QObject,
    Qt,
)
from PyQt5.QtGui import QCursor, QPainter, QPen, QColor, QPainterPath, QWindow
from PyQt5.QtCore import QRectF
from typing import Optional, List, Union
import threading
import platform
import subprocess
import sys
import json
import os
import tempfile
import time

# Platform-specific configuration
MACOS_PLATFORM = platform.system() == "Darwin"


class NotificationWidget(QWidget):
    """Custom notification widget with fade animations using QWindow for better control."""

    def __init__(
        self,
        title: str,
        message: str | None = None,
        icon: str = "",
        bg_color: Union[str, QColor] = "#323232",
        parent=None,
    ):
        super().__init__(parent)

        # Create underlying QWindow for native control
        self.native_window = QWindow()
        self.native_window.setFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )

        # Configure the widget window
        if MACOS_PLATFORM:
            self.native_window.setModality(Qt.NonModal)

        self.bg_color = bg_color
        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
            }
        """)
        self._setup_non_activating_window()
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        # macOS-specific attributes to prevent activation
        if MACOS_PLATFORM:
            self.setAttribute(Qt.WA_MacNoClickThrough, True)
            self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)

        # Create main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 24, 12)
        main_layout.setSpacing(8)

        # Create icon label
        self.icon_label = QLabel()
        self.icon_label.setText(icon)
        self.icon_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 16px;
                font-weight: bold;
                min-width: 20px;
                max-width: 20px;
                background: transparent;
                border: none;
            }
        """)
        self.icon_label.setAlignment(Qt.AlignCenter)

        # Create vertical layout for text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        # Create title label (bold header)
        if title:
            self.title_label = QLabel()
            self.title_label.setText(title)
            self.title_label.setStyleSheet("""
                QLabel {
                    color: white;
                    font-size: 14px;
                    font-weight: 600;
                    background: transparent;
                    border: none;
                }
            """)
            self.title_label.setWordWrap(False)
            self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            text_layout.addWidget(self.title_label)

        # Create body label
        if message:
            self.body_label = QLabel()
            self.body_label.setText(message)
            self.body_label.setStyleSheet("""
                QLabel {
                    color: white;
                    font-size: 13px;
                    background: transparent;
                    border: none;
                }
            """)
            self.body_label.setWordWrap(False)
            self.body_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            text_layout.addWidget(self.body_label)

        # Add widgets to main layout
        if icon:
            main_layout.addWidget(self.icon_label)
        main_layout.addLayout(text_layout)
        main_layout.addStretch()

        # Set up opacity effect for animations
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)

        # Animation for fade in/out
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")

        # Timer for auto-hide
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.fade_out)

    def _setup_non_activating_window(self):
        """Configure window flags for non-activating overlay behavior."""
        base_flags = (
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )

        # Platform-specific window flags
        if platform.system() == "Darwin":  # macOS
            # On macOS, use additional flags to prevent activation
            flags = base_flags
        elif platform.system() == "Linux":
            # On Linux, bypass window manager for true overlay behavior
            flags = base_flags | Qt.X11BypassWindowManagerHint
        else:  # Windows
            flags = base_flags

        self.setWindowFlags(flags)

        # Additional attributes for non-activating behavior
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        if MACOS_PLATFORM:
            # macOS-specific: prevent window from becoming key window
            if hasattr(Qt, "WA_MacAlwaysShowToolWindow"):
                self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
            if hasattr(Qt, "WA_MacNonActivatingToolWindow"):
                self.setAttribute(Qt.WA_MacNonActivatingToolWindow, True)

        # Enable debug mode for testing (can be disabled in production)
        self._debug_enabled = False

    def show_notification(
        self,
        duration: int = 2000,
        target_screen_geometry=None,
        notification_index: int = 0,
    ):
        """Show the notification with fade-in animation."""
        try:
            # Position the notification at top-right of screen
            self.adjustSize()

            if target_screen_geometry:
                screen_geometry = target_screen_geometry
            else:
                screen_geometry = QApplication.desktop().screenGeometry()

            x = screen_geometry.x() + screen_geometry.width() - self.width() - 20
            y = screen_geometry.y() + 50 + (notification_index * 80)
            self.move(x, y)

            # Show and fade in without activating
            self._show_without_activation()
            self.fade_in()

            # Set timer to fade out
            self.hide_timer.start(duration)
        except Exception as e:
            print(f"Error showing notification: {e}")

    def fade_in(self):
        """Fade in animation."""
        self.fade_animation.setDuration(300)
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(0.9)
        self.fade_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_animation.start()

    def fade_out(self):
        """Fade out animation."""
        self.fade_animation.setDuration(300)
        self.fade_animation.setStartValue(0.9)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.InCubic)
        self.fade_animation.finished.connect(self.close)
        self.fade_animation.start()

    def paintEvent(self, event):
        """Custom paint event for rounded corners with proper transparency."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Create rounded rectangle
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)

        # Fill with background color
        painter.fillPath(path, QColor(self.bg_color))

        # Draw border
        pen = QPen(QColor(255, 255, 255, 77))  # rgba(255, 255, 255, 0.3)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)

        painter.end()

    def _show_without_activation(self):
        """Show the notification without stealing focus."""
        if MACOS_PLATFORM:
            # On macOS, try to prevent activation entirely
            self.setVisible(True)
            self._configure_macos_window_level()
            # Don't call show() or raise_() as they can cause activation
        else:
            self.show()
            self.raise_()

        # Debug information
        self._debug_window_state()

    def _configure_macos_window_level(self):
        """Configure macOS window level for proper overlay behavior."""
        # Use Qt-only approach for all platforms - this is more reliable
        self._configure_qt_window_level()

    def _configure_qt_window_level(self):
        """Configure window level using Qt-only methods."""
        try:
            # Ensure window stays on top but doesn't steal focus
            current_flags = self.windowFlags()
            if not (current_flags & Qt.WindowStaysOnTopHint):
                self.setWindowFlags(current_flags | Qt.WindowStaysOnTopHint)

            # Additional attributes to prevent activation
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)

            # Platform-specific attributes
            if MACOS_PLATFORM:
                if hasattr(Qt, "WA_MacNoClickThrough"):
                    self.setAttribute(Qt.WA_MacNoClickThrough, False)
        except Exception as e:
            print(f"Warning: Could not configure Qt window level: {e}")

    def _debug_window_state(self):
        """Debug method to verify non-activating window behavior."""
        if hasattr(self, "_debug_enabled") and self._debug_enabled:
            flags = self.windowFlags()
            print(f"🔧 Notification Debug Info:")
            print(f"  Platform: {platform.system()}")
            print(f"  Window flags: {flags}")
            print(
                f"  WA_ShowWithoutActivating: {self.testAttribute(Qt.WA_ShowWithoutActivating)}"
            )
            print(
                f"  WindowDoesNotAcceptFocus: {bool(flags & Qt.WindowDoesNotAcceptFocus)}"
            )
            print(f"  WindowStaysOnTopHint: {bool(flags & Qt.WindowStaysOnTopHint)}")
            print(f"  ✅ Non-activating configuration applied successfully")


class NotificationDispatcher(QObject):
    """Thread-safe notification dispatcher using Qt signals."""

    show_notification_signal = pyqtSignal(str, object, str, int, str)

    def __init__(self, notification_manager):
        super().__init__()
        self.notification_manager = notification_manager
        self.show_notification_signal.connect(
            self._show_notification_slot, Qt.QueuedConnection
        )

    def _show_notification_slot(
        self,
        title: str,
        message: str | None,
        bg_color: str,
        duration: int,
        icon: str = "",
    ):
        """Slot to handle notification display on main thread."""
        self.notification_manager._show_notification_internal(
            title, message, duration, bg_color, icon
        )


class PyQtNotificationManager:
    """PyQt5-based notification manager with immediate display and multi-screen support."""

    def __init__(self, app: Optional[QApplication] = None):
        self.app = app or QApplication.instance()
        self.active_notifications: List[NotificationWidget] = []
        self.dispatcher = NotificationDispatcher(self) if self.app else None
        self.desktop = QApplication.desktop() if self.app else None

    def show_success_notification(self, title: str, message: str | None = None) -> None:
        """Show a success notification."""
        self._display_notification(title, message, "#43803e", 2000, "✔")

    def show_error_notification(
        self,
        title: str,
        message: str | None = None,
    ) -> None:
        """Show an error notification."""
        self._display_notification(title, message, "#9B6B67", 4000, "✗")

    def show_info_notification(self, title: str, message: str) -> None:
        """Show an info notification."""
        self._display_notification(title, message, "#6A7D93", 2000, "ⓘ")

    def _display_notification(
        self,
        title: str,
        message: str | None,
        bg_color: str,
        duration: int,
        icon: str = "",
    ) -> None:
        """Display a notification immediately, handling threading properly."""
        if not self.app or not self.dispatcher:
            display_text = f"{title}: {message}" if message else title
            print(f"🔔 {display_text}")
            return

        current_thread = threading.current_thread()
        main_thread = threading.main_thread()
        is_main_thread = current_thread == main_thread

        # Always use QTimer.singleShot for deferred execution on macOS to avoid blocking
        if platform.system() == "Darwin":
            if is_main_thread:
                QTimer.singleShot(
                    0,
                    lambda: self._show_notification_internal(
                        title, message, duration, bg_color, icon
                    ),
                )
            else:
                # Use signal for cross-thread communication
                self.dispatcher.show_notification_signal.emit(
                    title, message, bg_color, duration, icon
                )
        elif is_main_thread:
            # On Linux/Windows, show immediately if on main thread
            self._show_notification_internal(title, message, duration, bg_color, icon)
        else:
            # We're on a background thread, use signal to show on main thread
            self.dispatcher.show_notification_signal.emit(
                title, message, bg_color, duration, icon
            )

    def _get_active_screen_geometry(self):
        """Get the geometry of the screen where the mouse cursor is currently located."""
        if not self.desktop:
            return QApplication.desktop().screenGeometry()

        try:
            # Get current cursor position
            cursor_pos = QCursor.pos()

            # Find which screen contains the cursor
            screen_number = self.desktop.screenNumber(cursor_pos)

            # Validate screen number and get geometry
            if screen_number >= 0 and screen_number < self.desktop.screenCount():
                screen_geometry = self.desktop.screenGeometry(screen_number)
                # Additional validation - ensure the geometry is valid
                if screen_geometry.width() > 0 and screen_geometry.height() > 0:
                    return screen_geometry

            # Fallback 1: Try to find screen containing cursor by iterating all screens
            for i in range(self.desktop.screenCount()):
                screen_geom = self.desktop.screenGeometry(i)
                if screen_geom.contains(cursor_pos):
                    return screen_geom

            # Fallback 2: Use primary screen
            primary_screen_num = 0
            if hasattr(self.desktop, "primaryScreen"):
                try:
                    primary_screen_num = self.desktop.primaryScreen()
                except:
                    primary_screen_num = 0

            if primary_screen_num < self.desktop.screenCount():
                return self.desktop.screenGeometry(primary_screen_num)

            # Fallback 3: Use first available screen
            if self.desktop.screenCount() > 0:
                return self.desktop.screenGeometry(0)

        except Exception as e:
            # Log the error for debugging on different platforms
            try:
                print(f"Display detection error on {platform.system()}: {e}")
            except:
                pass

        # Final fallback to default screen geometry
        try:
            return QApplication.desktop().screenGeometry()
        except:
            # Emergency fallback with reasonable defaults
            from PyQt5.QtCore import QRect

            return QRect(0, 0, 1920, 1080)

    def _show_notification_internal(
        self,
        title: str,
        message: str | None,
        duration: int,
        bg_color: str = "#323232",
        icon: str = "",
    ) -> None:
        """Internal method to show notification (must be called on main thread)."""
        try:
            if not self.app:
                display_text = f"{title}: {message}" if message else title
                print(f"🔔 {display_text}")
                return

            current_thread = threading.current_thread()
            is_main_thread = current_thread == threading.main_thread()

            # Ensure we're running on the main GUI thread
            if not is_main_thread:
                print(
                    f"Warning: Notification called from background thread on {platform.system()}"
                )
                return

            # On macOS, use daemon to avoid focus stealing
            if MACOS_PLATFORM:
                self._show_notification_daemon(
                    title, message, duration, bg_color, icon
                )
                return

            # Get the active screen geometry
            active_screen = self._get_active_screen_geometry()

            # Clean up old notifications
            self.active_notifications = [
                n for n in self.active_notifications if n.isVisible()
            ]

            # Create and show new notification
            notification = NotificationWidget(title, message, icon, bg_color)
            self.active_notifications.append(notification)

            # Always use the active screen geometry for positioning
            notification_index = len(self.active_notifications) - 1
            notification.show_notification(duration, active_screen, notification_index)

        except (RuntimeError, Exception) as e:
            print(f"Failed to show notification: {e}")
            display_text = f"{title}: {message}" if message else title
            print(f"🔔 {display_text}")

    def is_available(self) -> bool:
        """Check if notifications are available."""
        return self.app is not None

    def enable_debug_mode(self, enabled: bool = True):
        """Enable or disable debug mode for notification windows."""
        for notification in self.active_notifications:
            if hasattr(notification, "_debug_enabled"):
                notification._debug_enabled = enabled

    def test_non_activating_notifications(self):
        """Test the non-activating notification system."""
        if not self.is_available():
            print("Notification system not available")
            return

        # Enable debug mode for testing
        self.enable_debug_mode(True)

        # Show test notifications
        self.show_info_notification(
            "Test Non-Activating", "This notification should not steal focus"
        )

        # Show additional notification to test stacking
        QTimer.singleShot(
            1000,
            lambda: self.show_success_notification(
                "Focus Test", "Your active window should remain focused"
            ),
        )

        print(
            "Test notifications sent. Check that your current window maintains focus."
        )

    def _show_notification_daemon(
        self,
        title: str,
        message: str | None,
        duration: int,
        bg_color: str = "#323232",
        icon: str = "",
    ) -> None:
        """Show notification using daemon to avoid focus stealing."""
        try:
            # Create notification data
            notification_data = {
                "title": title,
                "message": message,
                "duration": duration,
                "bg_color": bg_color,
                "icon": icon,
                "screen_geometry": self._get_screen_geometry_dict(),
            }

            # Get daemon pipe path
            temp_dir = tempfile.gettempdir()
            pipe_path = os.path.join(temp_dir, "prompt_store_notifications")
            
            # Check if daemon is running
            if not os.path.exists(pipe_path):
                # Start daemon if not running
                if not self._start_notification_daemon():
                    raise Exception("Failed to start daemon")
            
            # Send notification to daemon
            if os.path.exists(pipe_path):
                with open(pipe_path, 'w') as pipe:
                    pipe.write(json.dumps(notification_data) + '\n')
                    pipe.flush()
            else:
                # Fallback if daemon couldn't start
                raise Exception("Daemon not available")

        except Exception as e:
            print(f"Failed to show daemon notification: {e}")
            # Fallback to regular notification
            display_text = f"{title}: {message}" if message else title
            print(f"🔔 {display_text}")

    def _start_notification_daemon(self):
        """Start the notification daemon if not running."""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            daemon_script = os.path.join(current_dir, "notification_daemon.py")
            
            if os.path.exists(daemon_script):
                subprocess.Popen(
                    [sys.executable, daemon_script],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                
                # Wait for daemon to start
                temp_dir = tempfile.gettempdir()
                pipe_path = os.path.join(temp_dir, "prompt_store_notifications")
                
                # Wait up to 3 seconds for daemon to start
                for _ in range(30):
                    if os.path.exists(pipe_path):
                        return True
                    time.sleep(0.1)
                
                print("Daemon startup timeout - pipe not created")
                return False
            else:
                print(f"Daemon script not found: {daemon_script}")
                return False
        except Exception as e:
            print(f"Failed to start notification daemon: {e}")
            return False

    def _show_notification_subprocess(
        self,
        title: str,
        message: str | None,
        duration: int,
        bg_color: str = "#323232",
        icon: str = "",
    ) -> None:
        """Show notification using subprocess to avoid focus stealing."""
        try:
            # Create notification data
            notification_data = {
                "title": title,
                "message": message,
                "duration": duration,
                "bg_color": bg_color,
                "icon": icon,
                "screen_geometry": self._get_screen_geometry_dict(),
            }

            # Get the path to the notification subprocess script
            current_dir = os.path.dirname(os.path.abspath(__file__))
            subprocess_script = os.path.join(current_dir, "notification_subprocess.py")

            # Launch subprocess
            subprocess.Popen(
                [sys.executable, subprocess_script, json.dumps(notification_data)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # Detach from parent process
            )

        except Exception as e:
            print(f"Failed to show subprocess notification: {e}")
            # Fallback to regular notification
            display_text = f"{title}: {message}" if message else title
            print(f"🔔 {display_text}")

    def _get_screen_geometry_dict(self) -> dict:
        """Get screen geometry as dictionary for subprocess."""
        try:
            screen_geometry = self._get_active_screen_geometry()
            return {
                "x": screen_geometry.x(),
                "y": screen_geometry.y(),
                "width": screen_geometry.width(),
                "height": screen_geometry.height(),
            }
        except Exception:
            return {"x": 0, "y": 0, "width": 1920, "height": 1080}

    def get_display_info(self) -> dict:
        """Get information about available displays for debugging."""
        if not self.desktop:
            return {"error": "Desktop not available", "platform": platform.system()}

        try:
            cursor_pos = QCursor.pos()
            active_screen = self.desktop.screenNumber(cursor_pos)

            # Get primary screen number safely
            primary_screen = 0
            try:
                if hasattr(self.desktop, "primaryScreen"):
                    primary_screen = self.desktop.primaryScreen()
            except:
                primary_screen = 0

            display_info = {
                "platform": platform.system(),
                "cursor_position": {"x": cursor_pos.x(), "y": cursor_pos.y()},
                "active_screen": active_screen,
                "primary_screen": primary_screen,
                "total_screens": self.desktop.screenCount(),
                "screens": [],
            }

            for i in range(self.desktop.screenCount()):
                try:
                    screen_geom = self.desktop.screenGeometry(i)
                    available_geom = self.desktop.availableGeometry(i)

                    screen_info = {
                        "screen_number": i,
                        "geometry": {
                            "x": screen_geom.x(),
                            "y": screen_geom.y(),
                            "width": screen_geom.width(),
                            "height": screen_geom.height(),
                        },
                        "available_geometry": {
                            "x": available_geom.x(),
                            "y": available_geom.y(),
                            "width": available_geom.width(),
                            "height": available_geom.height(),
                        },
                        "is_primary": i == primary_screen,
                        "is_current": i == active_screen,
                        "contains_cursor": screen_geom.contains(cursor_pos),
                    }

                    display_info["screens"].append(screen_info)

                except Exception as screen_error:
                    display_info["screens"].append(
                        {"screen_number": i, "error": str(screen_error)}
                    )

            return display_info

        except Exception as e:
            return {"error": str(e), "platform": platform.system()}


def format_execution_time(execution_time: float) -> str:
    """Format execution time for display."""
    if execution_time < 1:
        return f"{execution_time * 1000:.0f}ms"
    else:
        return f"{execution_time:.1f}s"


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text for notification display."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def get_display_info() -> dict:
    """Get detailed information about all available displays."""
    app = QApplication.instance()
    if not app:
        return {"error": "No QApplication instance available"}

    desktop = QApplication.desktop()
    if not desktop:
        return {"error": "Desktop not available"}

    try:
        cursor_pos = QCursor.pos()
        active_screen = desktop.screenNumber(cursor_pos)

        display_info = {
            "platform": platform.system(),
            "cursor_position": {"x": cursor_pos.x(), "y": cursor_pos.y()},
            "active_screen": active_screen,
            "total_screens": desktop.screenCount(),
            "screens": [],
        }

        for i in range(desktop.screenCount()):
            screen_geom = desktop.screenGeometry(i)
            available_geom = desktop.availableGeometry(i)
            display_info["screens"].append(
                {
                    "screen_number": i,
                    "geometry": {
                        "x": screen_geom.x(),
                        "y": screen_geom.y(),
                        "width": screen_geom.width(),
                        "height": screen_geom.height(),
                    },
                    "available_geometry": {
                        "x": available_geom.x(),
                        "y": available_geom.y(),
                        "width": available_geom.width(),
                        "height": available_geom.height(),
                    },
                    "is_primary": i == desktop.primaryScreen()
                    if hasattr(desktop, "primaryScreen")
                    else i == 0,
                    "is_current": i == active_screen,
                }
            )

        return display_info

    except Exception as e:
        return {"error": str(e), "platform": platform.system()}


def test_notification_positioning():
    """Test function to verify notification positioning on multiple displays."""
    app = QApplication.instance()
    if not app:
        print("No QApplication instance available for testing")
        return

    manager = PyQtNotificationManager(app)
    display_info = manager.get_display_info()

    print("Display Information:")
    print(f"Platform: {display_info.get('platform', 'Unknown')}")
    print(f"Total screens: {display_info.get('total_screens', 0)}")
    print(f"Active screen: {display_info.get('active_screen', -1)}")

    if "screens" in display_info:
        for screen in display_info["screens"]:
            print(
                f"Screen {screen['screen_number']}: "
                f"{screen['geometry']['width']}x{screen['geometry']['height']} "
                f"at ({screen['geometry']['x']}, {screen['geometry']['y']}) "
                f"{'(PRIMARY)' if screen['is_primary'] else ''} "
                f"{'(CURRENT)' if screen['is_current'] else ''}"
            )

    # Show test notification
    manager.show_info_notification(
        "Multi-Display Test",
        f"This notification should appear on screen {display_info.get('active_screen', 0)}",
    )


def test_non_activating_notifications():
    """Test function to verify non-activating notification behavior."""
    app = QApplication.instance()
    if not app:
        print("No QApplication instance available for testing")
        return

    manager = PyQtNotificationManager(app)

    print("Testing non-activating notifications...")
    print("Instructions: Focus on another application window, then run this test.")
    print(
        "The notifications should appear WITHOUT stealing focus from your current window."
    )

    # Test the non-activating notification system
    manager.test_non_activating_notifications()

    print("✅ Non-activating notification test completed successfully!")
    print("🔍 Verify that your active window maintained focus during the test.")
