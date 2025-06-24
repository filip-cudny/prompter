"""PyQt5-based notification utilities."""

from PyQt5.QtWidgets import QApplication, QLabel, QGraphicsOpacityEffect
from PyQt5.QtCore import QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QObject
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from typing import Optional, List
import threading


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

    def show_notification(self, duration: int = 2000):
        """Show the notification with fade-in animation."""
        # Position the notification at top-right of screen
        self.adjustSize()
        screen = QApplication.desktop().screenGeometry()
        x = screen.width() - self.width() - 20
        y = 50
        self.move(x, y)

        # Show and fade in
        self.show()
        self.fade_in()

        # Set timer to fade out
        self.hide_timer.start(duration)

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
        self.show_notification_signal.connect(self._show_notification_slot)
        
    def _show_notification_slot(self, message: str, bg_color: str, duration: int):
        """Slot to handle notification display on main thread."""
        self.notification_manager._show_notification_internal(message, duration, bg_color)


class PyQtNotificationManager:
    """PyQt5-based notification manager with immediate display."""

    def __init__(self, app: Optional[QApplication] = None):
        self.app = app or QApplication.instance()
        self.active_notifications: List[NotificationWidget] = []
        self.dispatcher = NotificationDispatcher(self) if self.app else None

    def show_success_notification(
        self, title: str, message: str, prompt_name: Optional[str] = None
    ) -> None:
        """Show a success notification."""
        if prompt_name:
            full_message = f"✔ {title} - {prompt_name}\n{message}"
        else:
            full_message = f"✔ {title}\n{message}"

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

        # Check if we're on the main thread
        if threading.current_thread() == threading.main_thread():
            # We're on main thread, show immediately
            self._show_notification_internal(message, duration, bg_color)
        else:
            # We're on a background thread, use signal to show on main thread
            self.dispatcher.show_notification_signal.emit(message, bg_color, duration)

    def _show_notification_internal(
        self, message: str, duration: int = 2000, bg_color: str = "#323232"
    ) -> None:
        """Internal method to show notification (must be called on main thread)."""
        try:
            if not self.app:
                print(f"🔔 {message}")
                return

            # Clean up old notifications
            self.active_notifications = [
                n for n in self.active_notifications if n.isVisible()
            ]

            # Create and show new notification
            notification = NotificationWidget(message, bg_color)
            self.active_notifications.append(notification)

            # Adjust position if there are other notifications
            if len(self.active_notifications) > 1:
                screen = QApplication.desktop().screenGeometry()
                y_offset = 50 + (len(self.active_notifications) - 1) * 80
                x = screen.width() - notification.sizeHint().width() - 20
                notification.move(x, y_offset)

            notification.show_notification(duration)

        except (RuntimeError, Exception) as e:
            print(f"Failed to show notification: {e}")
            print(f"🔔 {message}")

    def is_available(self) -> bool:
        """Check if notifications are available."""
        return self.app is not None


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