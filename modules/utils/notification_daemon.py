#!/usr/bin/env python3
"""
Notification daemon that runs continuously to avoid focus stealing.

This daemon runs in the background and receives notification requests
through a named pipe, preventing focus stealing that occurs when
spawning new processes for each notification.
"""

import os
import sys
import json
import time
import threading
import tempfile
import signal
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
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
from PyQt5.QtGui import QPainter, QPen, QColor, QPainterPath
import platform


class NotificationWidget(QWidget):
    """Non-activating notification widget."""
    
    # Signal emitted when notification is completely finished
    notification_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.bg_color = "#2d3748"
        self.screen_geometry = {}
        self.hide_timer = None

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
            | Qt.X11BypassWindowManagerHint
        )

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DontShowOnScreen, False)

        if platform.system() == "Darwin":
            self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
            if hasattr(Qt, "WA_MacNonActivatingToolWindow"):
                self.setAttribute(Qt.WA_MacNonActivatingToolWindow, True)
            if hasattr(Qt, "WA_MacNoClickThrough"):
                self.setAttribute(Qt.WA_MacNoClickThrough, True)

        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
            }
        """)

        self.setup_animations()

    def setup_ui(self, title, message, icon):
        """Set up the notification UI with given content."""
        # Clear existing layout
        if self.layout():
            while self.layout().count():
                child = self.layout().takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            self.layout().deleteLater()

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 24, 12)
        main_layout.setSpacing(8)

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

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

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

    def setup_animations(self):
        """Set up fade animations."""
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)

        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")

    def show_notification(
        self, title, message, icon, bg_color, screen_geometry, duration=2000
    ):
        """Show the notification without stealing focus."""
        # Cancel any existing timer
        if self.hide_timer:
            self.hide_timer.stop()
            self.hide_timer = None
            
        self.bg_color = bg_color
        self.screen_geometry = screen_geometry

        self.setup_ui(title, message, icon)
        self.adjustSize()

        x = (
            self.screen_geometry["x"]
            + self.screen_geometry["width"]
            - self.width()
            - 20
        )
        y = self.screen_geometry["y"] + 50
        self.move(x, y)

        # Use setVisible instead of show() to avoid activation
        self.setVisible(True)
        self.fade_in()

        # Auto-hide after duration
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.fade_out)
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
        
        # Disconnect any existing connections to avoid multiple signals
        try:
            self.fade_animation.finished.disconnect()
        except:
            pass
        
        # Connect to cleanup method
        self.fade_animation.finished.connect(self._on_fade_finished)
        self.fade_animation.start()
    
    def _on_fade_finished(self):
        """Called when fade animation completes."""
        self.hide()
        self.notification_finished.emit()

    def paintEvent(self, event):
        """Custom paint event for rounded corners."""
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


class NotificationHandler(QObject):
    """Handles notification requests in the Qt thread."""

    show_notification_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.current_notification = None
        self.notification_queue = []
        self.show_notification_signal.connect(self.handle_notification)

    def handle_notification(self, data):
        """Handle notification display in the main thread."""
        # Add to queue
        self.notification_queue.append(data)
        
        # Process queue if no notification is currently showing
        if self.current_notification is None:
            self._show_next_notification()

    def _show_next_notification(self):
        """Show the next notification in the queue."""
        if not self.notification_queue:
            return
            
        # Get next notification data
        data = self.notification_queue.pop(0)
        
        # Create new widget instance for this notification
        self.current_notification = NotificationWidget()
        
        # Connect cleanup signal
        self.current_notification.notification_finished.connect(
            self._on_notification_finished
        )
        
        # Show the notification
        self.current_notification.show_notification(
            data["title"],
            data["message"],
            data["icon"],
            data["bg_color"],
            data["screen_geometry"],
            data["duration"],
        )

    def _on_notification_finished(self):
        """Called when a notification fade animation finishes."""
        # Clean up current notification
        if self.current_notification:
            self.current_notification.deleteLater()
            self.current_notification = None
        
        # Process next notification in queue after a short delay
        QTimer.singleShot(200, self._show_next_notification)


class NotificationDaemon:
    """Notification daemon that listens for requests."""

    def __init__(self):
        self.pipe_path = self._get_pipe_path()
        self.pid_file = self._get_pid_file()
        self.running = False
        self.app = None
        self.handler = None

    def _get_pipe_path(self):
        """Get the named pipe path."""
        temp_dir = tempfile.gettempdir()
        return os.path.join(temp_dir, "prompt_store_notifications")

    def _get_pid_file(self):
        """Get the PID file path."""
        temp_dir = tempfile.gettempdir()
        return os.path.join(temp_dir, "prompt_store_daemon.pid")

    def start(self):
        """Start the notification daemon."""
        self.running = True

        # Save PID
        try:
            with open(self.pid_file, "w") as f:
                f.write(str(os.getpid()))
        except Exception as e:
            print(f"Failed to save PID file: {e}")

        # Create Qt application
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # Create notification handler
        self.handler = NotificationHandler()

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Start pipe listener in background thread
        listener_thread = threading.Thread(
            target=self._listen_for_requests, daemon=True
        )
        listener_thread.start()

        print(f"Notification daemon started. Pipe: {self.pipe_path}")

        # Run Qt event loop
        try:
            sys.exit(self.app.exec_())
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Stop the notification daemon."""
        self.running = False

        # Clean up pipe
        if os.path.exists(self.pipe_path):
            try:
                os.unlink(self.pipe_path)
            except OSError:
                pass

        # Clean up PID file
        if os.path.exists(self.pid_file):
            try:
                os.unlink(self.pid_file)
            except OSError:
                pass

        if self.app:
            self.app.quit()

    def _signal_handler(self, signum, frame):
        """Handle system signals."""
        print(f"Received signal {signum}, shutting down...")
        self.stop()

    def _listen_for_requests(self):
        """Listen for notification requests on the named pipe."""
        # Create named pipe
        if os.path.exists(self.pipe_path):
            os.unlink(self.pipe_path)

        try:
            os.mkfifo(self.pipe_path)
        except OSError as e:
            print(f"Failed to create named pipe: {e}")
            return

        while self.running:
            try:
                # Open pipe for reading (blocking)
                with open(self.pipe_path, "r") as pipe:
                    while self.running:
                        try:
                            line = pipe.readline()
                            if not line:
                                break

                            # Parse notification data
                            data = json.loads(line.strip())

                            # Emit signal to handle in main thread
                            if self.handler:
                                self.handler.show_notification_signal.emit(data)

                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            print(f"Error processing notification: {e}")
                            continue

            except Exception as e:
                if self.running:
                    print(f"Pipe error: {e}")
                    time.sleep(1)


def send_notification(
    title, message, icon="ℹ️", bg_color="#2d3748", screen_geometry=None, duration=2000
):
    """Send a notification to the daemon."""
    daemon = NotificationDaemon()
    pipe_path = daemon._get_pipe_path()

    if not os.path.exists(pipe_path):
        print("Notification daemon not running")
        return False

    # Default screen geometry if not provided
    if screen_geometry is None:
        screen_geometry = {"x": 0, "y": 0, "width": 1920, "height": 1080}

    notification_data = {
        "title": title,
        "message": message,
        "icon": icon,
        "bg_color": bg_color,
        "screen_geometry": screen_geometry,
        "duration": duration,
    }

    try:
        with open(pipe_path, "w") as pipe:
            pipe.write(json.dumps(notification_data) + "\n")
            pipe.flush()
        return True
    except Exception as e:
        print(f"Failed to send notification: {e}")
        return False


def main():
    """Main function for the daemon."""
    if len(sys.argv) > 1 and sys.argv[1] == "send":
        # Send mode
        if len(sys.argv) < 4:
            print(
                "Usage: notification_daemon.py send <title> <message> [icon] [bg_color]"
            )
            sys.exit(1)

        title = sys.argv[2]
        message = sys.argv[3]
        icon = sys.argv[4] if len(sys.argv) > 4 else "ℹ️"
        bg_color = sys.argv[5] if len(sys.argv) > 5 else "#2d3748"

        success = send_notification(title, message, icon, bg_color)
        sys.exit(0 if success else 1)
    else:
        # Daemon mode
        daemon = NotificationDaemon()
        daemon.start()


if __name__ == "__main__":
    main()
