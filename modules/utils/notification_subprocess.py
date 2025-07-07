#!/usr/bin/env python3
"""
Subprocess script for displaying notifications without stealing focus.

This script runs in a separate process to completely isolate notification
display from the main application, preventing any focus stealing.
"""

import sys
import json
import os
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QGraphicsOpacityEffect,
)
from PyQt5.QtCore import QTimer, QPropertyAnimation, QEasingCurve, Qt, QRectF
from PyQt5.QtGui import QPainter, QPen, QColor, QPainterPath
import platform


class IsolatedNotificationWidget(QWidget):
    """Isolated notification widget that runs in its own process."""

    def __init__(self, title, message, icon, bg_color, screen_geometry):
        super().__init__()
        self.bg_color = bg_color
        self.screen_geometry = screen_geometry

        # Configure window to absolutely prevent focus stealing
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
            | Qt.X11BypassWindowManagerHint
        )

        # Critical attributes to prevent activation
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DontShowOnScreen, False)

        # macOS-specific attributes
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

        self.setup_ui(title, message, icon)
        self.setup_animations()

    def setup_ui(self, title, message, icon):
        """Set up the notification UI."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 24, 12)
        main_layout.setSpacing(8)

        # Icon label
        if icon:
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
            main_layout.addWidget(self.icon_label)

        # Text layout
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        # Title label
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

        # Message label
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

        main_layout.addLayout(text_layout)
        main_layout.addStretch()

    def setup_animations(self):
        """Set up fade animations."""
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)

        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")

    def show_notification(self, duration=2000):
        """Show the notification without stealing focus."""
        self.adjustSize()

        # Position at top-right of screen
        x = (
            self.screen_geometry["x"]
            + self.screen_geometry["width"]
            - self.width()
            - 20
        )
        y = self.screen_geometry["y"] + 50
        self.move(x, y)

        # Show using setVisible to avoid activation
        self.setVisible(True)

        # Start fade in animation
        self.fade_in()

        # Set timer for fade out
        QTimer.singleShot(duration, self.fade_out)

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
        self.fade_animation.finished.connect(self.close_and_exit)
        self.fade_animation.start()

    def close_and_exit(self):
        """Close the notification and exit the process."""
        self.close()
        QApplication.quit()

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


def main():
    """Main function for the subprocess."""
    if len(sys.argv) < 2:
        print("Usage: notification_subprocess.py <notification_data_json>")
        sys.exit(1)

    try:
        # Parse notification data
        notification_data = json.loads(sys.argv[1])

        # Create isolated Qt application
        app = QApplication(sys.argv)

        # Prevent this app from appearing in dock/taskbar
        app.setQuitOnLastWindowClosed(True)

        # Create and show notification
        notification = IsolatedNotificationWidget(
            notification_data["title"],
            notification_data["message"],
            notification_data["icon"],
            notification_data["bg_color"],
            notification_data["screen_geometry"],
        )

        notification.show_notification(notification_data["duration"])

        # Run the isolated app
        sys.exit(app.exec_())

    except Exception as e:
        print(f"Subprocess notification error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
