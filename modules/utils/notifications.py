"""Enhanced notification system with non-focus-stealing implementation."""

import platform
import threading
from typing import Union, Optional
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QDesktopWidget,
    QGraphicsOpacityEffect,
)
from PyQt5.QtCore import (
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    Qt,
    QRectF,
    QObject,
    pyqtSignal,
)
from PyQt5.QtGui import QPainter, QPen, QColor, QPainterPath, QCursor

# Platform-specific configuration
MACOS_PLATFORM = platform.system() == "Darwin"
LINUX_PLATFORM = platform.system() == "Linux"
WINDOWS_PLATFORM = platform.system() == "Windows"


class EnhancedNotificationWidget(QWidget):
    """Enhanced notification widget with proper non-focus-stealing implementation."""

    notification_finished = pyqtSignal()

    def __init__(
        self,
        title: str,
        message: str | None = None,
        icon: str = "",
        bg_color: Union[str, QColor] = "#323232",
        parent=None,
    ):
        # Ensure we're on the main thread when creating widgets
        if threading.current_thread() != threading.main_thread():
            raise RuntimeError("NotificationWidget must be created on the main thread")

        super().__init__(parent)

        self.bg_color = bg_color
        self.hide_timer: Optional[QTimer] = None
        self._is_visible = False

        # Configure non-activating window
        self._setup_non_activating_window()

        # Setup UI
        self._setup_ui(title, message, icon)

        # Setup animations
        self._setup_animations()

    def _setup_non_activating_window(self):
        """Configure window for non-activating overlay behavior."""
        # Base window flags for all platforms
        base_flags = (
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )

        # Platform-specific window flags
        if LINUX_PLATFORM:
            # On Linux, bypass window manager for true overlay behavior
            flags = base_flags | Qt.X11BypassWindowManagerHint
        else:
            flags = base_flags

        self.setWindowFlags(flags)

        # Essential attributes for non-activating behavior
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DontShowOnScreen, False)

        # macOS-specific attributes
        if MACOS_PLATFORM:
            self.setAttribute(Qt.WA_MacNoClickThrough, True)
            self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
            if hasattr(Qt, "WA_MacNonActivatingToolWindow"):
                self.setAttribute(Qt.WA_MacNonActivatingToolWindow, True)

        # Styling
        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
            }
        """)

    def _setup_ui(self, title: str, message: str | None, icon: str):
        """Setup the notification UI."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 24, 12)
        main_layout.setSpacing(8)

        # Icon
        if icon:
            icon_label = QLabel()
            icon_label.setText(icon)
            icon_label.setStyleSheet("""
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
            icon_label.setAlignment(Qt.AlignCenter)
            main_layout.addWidget(icon_label)

        # Text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        # Title
        if title:
            title_label = QLabel()
            title_label.setText(title)
            title_label.setStyleSheet("""
                QLabel {
                    color: white;
                    font-size: 14px;
                    font-weight: 600;
                    background: transparent;
                    border: none;
                }
            """)
            title_label.setWordWrap(False)
            title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            text_layout.addWidget(title_label)

        # Message
        if message:
            body_label = QLabel()
            body_label.setText(message)
            body_label.setStyleSheet("""
                QLabel {
                    color: white;
                    font-size: 13px;
                    background: transparent;
                    border: none;
                }
            """)
            body_label.setWordWrap(False)
            body_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            text_layout.addWidget(body_label)

        main_layout.addLayout(text_layout)
        main_layout.addStretch()

    def _setup_animations(self):
        """Setup fade animations."""
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)

        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")

    def show_notification(
        self, duration: int = 2000, screen_geometry=None, notification_index: int = 0
    ):
        """Show notification without stealing focus."""
        if self.hide_timer:
            self.hide_timer.stop()
            self.hide_timer = None

        # Position notification
        if screen_geometry:
            self.adjustSize()
            x = screen_geometry.x() + screen_geometry.width() - self.width() - 20
            y = screen_geometry.y() + 50 + (notification_index * 80)
            self.move(x, y)

        # Show without activation
        self._show_without_activation()
        self.fade_in()

        # Auto-hide timer
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.fade_out)
        self.hide_timer.start(duration)

    def _show_without_activation(self):
        """Show widget without activating it."""
        if MACOS_PLATFORM:
            # On macOS, use setVisible to avoid activation
            self.setVisible(True)
            self._configure_macos_window_level()
        else:
            # On other platforms, show normally
            self.setVisible(True)

        self._is_visible = True

    def _configure_macos_window_level(self):
        """Configure macOS window level for proper overlay behavior."""
        try:
            # Ensure proper window level without external dependencies
            if hasattr(self, "winId"):
                # Keep current Qt-based approach for stability
                pass
        except Exception as e:
            print(f"Warning: Could not configure macOS window level: {e}")

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

        # Disconnect existing connections to avoid multiple signals
        try:
            self.fade_animation.finished.disconnect()
        except TypeError:
            pass

        self.fade_animation.finished.connect(self._on_fade_finished)
        self.fade_animation.start()

    def _on_fade_finished(self):
        """Handle fade animation completion."""
        self.setVisible(False)
        self._is_visible = False
        self.notification_finished.emit()

    def paintEvent(self, event):
        """Custom paint event for rounded corners."""
        _ = event  # Unused parameter
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)

        painter.fillPath(path, QColor(self.bg_color))

        pen = QPen(QColor(255, 255, 255, 77))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)

        painter.end()

    def cleanup(self):
        """Clean up resources."""
        try:
            if self.hide_timer:
                self.hide_timer.stop()
                self.hide_timer = None

            if hasattr(self, "fade_animation"):
                self.fade_animation.stop()
        except Exception as e:
            print(f"Error during notification cleanup: {e}")


class NotificationDispatcher(QObject):
    """Thread-safe notification dispatcher."""

    show_notification_signal = pyqtSignal(str, str, str, str, int)

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.show_notification_signal.connect(
            self._show_notification_slot, Qt.QueuedConnection
        )

    def _show_notification_slot(
        self, title: str, message: str, icon: str, bg_color: str, duration: int
    ):
        """Handle notification display in main thread."""
        self.manager._display_notification_internal(
            title, message, icon, bg_color, duration
        )


class EnhancedNotificationManager:
    """Enhanced notification manager with single-process implementation."""

    def __init__(self, app: QApplication):
        self.app = app
        self.desktop = QDesktopWidget()
        self.active_notifications: list[EnhancedNotificationWidget] = []
        self.dispatcher = NotificationDispatcher(self)
        self.notification_lock = threading.Lock()

    def show_success_notification(
        self, title: str, message: str | None = None, duration: int = 2000
    ):
        """Show success notification."""
        self._display_notification(title, message, "✔", "#43803e", duration)

    def show_error_notification(
        self, title: str, message: str | None = None, duration: int = 4000
    ):
        """Show error notification."""
        self._display_notification(title, message, "✗", "#9B6B67", duration)

    def show_info_notification(
        self, title: str, message: str | None = None, duration: int = 2000
    ):
        """Show info notification."""
        self._display_notification(title, message, "ⓘ", "#6A7D93", duration)

    def show_warning_notification(
        self, title: str, message: str | None = None, duration: int = 3000
    ):
        """Show warning notification."""
        self._display_notification(title, message, "⚠️", "#f57c00", duration)

    def _display_notification(
        self,
        title: str,
        message: str | None,
        icon: str,
        bg_color: str,
        duration: int,
    ):
        """Display a notification with enhanced non-focus-stealing behavior."""
        if not self.app:
            display_text = f"{title}: {message}" if message else title
            print(f"🔔 {display_text}")
            return

        # Always use signal to ensure proper thread handling
        self.dispatcher.show_notification_signal.emit(
            title, message or "", icon, bg_color, duration
        )

    def _display_notification_internal(
        self,
        title: str,
        message: str | None,
        icon: str,
        bg_color: str,
        duration: int,
    ):
        """Internal method to display notification (must be called on main thread)."""
        try:
            # Ensure we're on the main thread
            if threading.current_thread() != threading.main_thread():
                print(
                    "Warning: Notification called from background thread, using fallback"
                )
                display_text = f"{title}: {message}" if message else title
                print(f"🔔 {display_text}")
                return

            # Check if app is still available
            if (
                not self.app
                or not hasattr(self.app, "instance")
                or not self.app.instance()
            ):
                display_text = f"{title}: {message}" if message else title
                print(f"🔔 {display_text}")
                return

            with self.notification_lock:
                # Clean up finished notifications
                self._cleanup_finished_notifications()

                # Get active screen geometry
                screen_geometry = self._get_active_screen_geometry()
                notification_index = len(self.active_notifications)

                # Create notification widget
                notification = EnhancedNotificationWidget(
                    title=title, message=message, icon=icon, bg_color=bg_color
                )

                # Connect cleanup signal
                notification.notification_finished.connect(
                    lambda: self._on_notification_finished(notification)
                )

                # Add to active notifications
                self.active_notifications.append(notification)

                # Show notification
                notification.show_notification(
                    duration=duration,
                    screen_geometry=screen_geometry,
                    notification_index=notification_index,
                )

        except Exception as e:
            print(f"Error displaying notification: {e}")
            display_text = f"{title}: {message}" if message else title
            print(f"🔔 {display_text}")

    def _cleanup_finished_notifications(self):
        """Remove finished notifications from active list."""
        self.active_notifications = [
            notif for notif in self.active_notifications if notif._is_visible
        ]

    def _on_notification_finished(self, notification):
        """Handle notification completion."""
        try:
            with self.notification_lock:
                if notification in self.active_notifications:
                    self.active_notifications.remove(notification)

                # Ensure cleanup happens on main thread
                if hasattr(notification, "cleanup"):
                    notification.cleanup()

                # Schedule deletion on main thread
                if hasattr(notification, "deleteLater"):
                    notification.deleteLater()

        except Exception as e:
            print(f"Error cleaning up notification: {e}")

    def _get_active_screen_geometry(self):
        """Get geometry of the screen containing the cursor."""
        try:
            if not self.desktop:
                try:
                    from PyQt5.QtCore import QRect

                    return QRect(0, 0, 1920, 1080)
                except ImportError:
                    return None

            cursor_pos = QCursor.pos()
            screen_number = self.desktop.screenNumber(cursor_pos)

            # Validate screen number
            if screen_number < 0 or screen_number >= self.desktop.screenCount():
                screen_number = 0

            return self.desktop.screenGeometry(screen_number)
        except Exception as e:
            print(f"Error getting screen geometry: {e}")
            try:
                from PyQt5.QtCore import QRect

                return QRect(0, 0, 1920, 1080)
            except ImportError:
                return None

    def is_available(self) -> bool:
        """Check if notifications are available."""
        return self.app is not None

    def cleanup(self):
        """Clean up all active notifications."""
        with self.notification_lock:
            for notification in self.active_notifications:
                notification.cleanup()
                notification.deleteLater()
            self.active_notifications.clear()


# Legacy compatibility - keep the old class name
class PyQtNotificationManager(EnhancedNotificationManager):
    """Legacy compatibility class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# Legacy compatibility - keep the old widget name
class NotificationWidget(EnhancedNotificationWidget):
    """Legacy compatibility class."""

    def __init__(
        self,
        title: str,
        message: str | None = None,
        icon: str = "",
        bg_color: Union[str, QColor] = "#323232",
        parent=None,
    ):
        super().__init__(title, message, icon, bg_color, parent)


def format_execution_time(seconds: float) -> str:
    """Format execution time for display."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    else:
        return f"{seconds:.1f}s"


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text to specified length."""
    return text[:max_length] + "..." if len(text) > max_length else text
