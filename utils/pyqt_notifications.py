"""PyQt5-based notification utilities."""

from PyQt5.QtWidgets import QApplication, QLabel, QGraphicsOpacityEffect
from PyQt5.QtCore import (
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    pyqtSignal,
    QObject,
    Qt,
)
from PyQt5.QtGui import QCursor
from typing import Optional, List
import threading
import platform


class NotificationWidget(QLabel):
    """Custom notification widget with fade animations."""

    def __init__(self, message: str, bg_color: str = "#323232", parent=None):
        super().__init__(parent)
        self.setText(message)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: white;
                padding: 12px 24px;
                border-radius: 8px;
                font-family: Arial;
                font-size: 13px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}
        """)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)

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

            # Show and fade in
            self.show()
            self.raise_()  # Ensure notification is on top
            self.activateWindow()  # Activate window on macOS
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


class NotificationDispatcher(QObject):
    """Thread-safe notification dispatcher using Qt signals."""

    show_notification_signal = pyqtSignal(str, str, int)

    def __init__(self, notification_manager):
        super().__init__()
        self.notification_manager = notification_manager
        self.show_notification_signal.connect(
            self._show_notification_slot, Qt.QueuedConnection
        )

    def _show_notification_slot(self, message: str, bg_color: str, duration: int):
        """Slot to handle notification display on main thread."""
        self.notification_manager._show_notification_internal(
            message, duration, bg_color
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
        if message:
            full_message = f"✔ {title}\n{message}"
        else:
            full_message = f"✔ {title}"

        self._display_notification(full_message, "#6B7A4A", 2000)

    def show_error_notification(
        self, title: str, message: str, prompt_name: Optional[str] = None
    ) -> None:
        """Show an error notification."""
        if prompt_name:
            full_message = f"✗ {title} - {prompt_name}\n{message}"
        else:
            full_message = f"✗ {title}\n{message}"

        self._display_notification(full_message, "#9B6B67", 4000)

    def show_info_notification(self, title: str, message: str) -> None:
        """Show an info notification."""
        full_message = f"ⓘ {title}\n{message}"
        self._display_notification(full_message, "#6A7D93", 2000)

    def _display_notification(self, message: str, bg_color: str, duration: int) -> None:
        """Display a notification immediately, handling threading properly."""
        if not self.app or not self.dispatcher:
            print(f"🔔 {message}")
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
                        message, duration, bg_color
                    ),
                )
            else:
                # Use signal for cross-thread communication
                self.dispatcher.show_notification_signal.emit(
                    message, bg_color, duration
                )
        elif is_main_thread:
            # On Linux/Windows, show immediately if on main thread
            self._show_notification_internal(message, duration, bg_color)
        else:
            # We're on a background thread, use signal to show on main thread
            self.dispatcher.show_notification_signal.emit(message, bg_color, duration)

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
        self, message: str, duration: int = 2000, bg_color: str = "#323232"
    ) -> None:
        """Internal method to show notification (must be called on main thread)."""
        try:
            if not self.app:
                print(f"🔔 {message}")
                return

            current_thread = threading.current_thread()
            is_main_thread = current_thread == threading.main_thread()

            # Ensure we're running on the main GUI thread
            if not is_main_thread:
                print(
                    f"Warning: Notification called from background thread on {platform.system()}"
                )
                return

            # Get the active screen geometry
            active_screen = self._get_active_screen_geometry()

            # Clean up old notifications
            self.active_notifications = [
                n for n in self.active_notifications if n.isVisible()
            ]

            # Create and show new notification
            notification = NotificationWidget(message, bg_color)
            self.active_notifications.append(notification)

            # Always use the active screen geometry for positioning
            notification_index = len(self.active_notifications) - 1
            notification.show_notification(duration, active_screen, notification_index)

        except (RuntimeError, Exception) as e:
            print(f"Failed to show notification: {e}")
            print(f"🔔 {message}")

    def is_available(self) -> bool:
        """Check if notifications are available."""
        return self.app is not None

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
