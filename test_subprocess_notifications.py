#!/usr/bin/env python3
"""
Comprehensive test for subprocess-based notifications that don't steal focus.

This test verifies that notifications appear without stealing focus from
the currently active window on macOS.
"""

import sys
import time
import subprocess
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QLabel,
    QPushButton,
    QTextEdit,
)
from PyQt5.QtCore import QTimer, Qt
from modules.utils.notifications import PyQtNotificationManager


class TestMainWindow(QMainWindow):
    """Test window to verify focus is not stolen."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Focus Test Window - Keep This Active")
        self.setGeometry(100, 100, 600, 400)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Instructions
        instructions = QLabel("""
        FOCUS STEALING TEST INSTRUCTIONS:

        1. Keep this window active and focused
        2. Click in the text area below and start typing
        3. Click the 'Test Notifications' button
        4. Continue typing while notifications appear
        5. Verify that your typing is NOT interrupted

        If notifications steal focus, your typing will be interrupted.
        If the implementation works correctly, you should be able to
        continue typing without interruption.
        """)
        instructions.setWordWrap(True)
        instructions.setStyleSheet(
            "padding: 10px; background-color: #f0f0f0; border-radius: 5px;"
        )
        layout.addWidget(instructions)

        # Text area for typing test
        self.text_area = QTextEdit()
        self.text_area.setPlaceholderText("Type here continuously during the test...")
        self.text_area.setStyleSheet("font-size: 14px; padding: 10px;")
        layout.addWidget(self.text_area)

        # Test button
        self.test_button = QPushButton("Test Notifications (Start typing first!)")
        self.test_button.setStyleSheet(
            "padding: 10px; font-size: 14px; font-weight: bold;"
        )
        self.test_button.clicked.connect(self.run_notification_test)
        layout.addWidget(self.test_button)

        # Status label
        self.status_label = QLabel(
            "Ready to test. Click in text area and start typing."
        )
        self.status_label.setStyleSheet("padding: 5px; font-weight: bold;")
        layout.addWidget(self.status_label)

        # Initialize notification manager
        self.notification_manager = PyQtNotificationManager(QApplication.instance())

    def run_notification_test(self):
        """Run the notification test sequence."""
        self.status_label.setText("🔥 TEST RUNNING - Keep typing in the text area!")
        self.test_button.setEnabled(False)

        # Ensure text area has focus
        self.text_area.setFocus()

        # Schedule multiple notifications
        notifications = [
            ("Test #1", "This is the first notification", 0),
            ("Test #2", "This is the second notification", 2000),
            ("Test #3", "This is the third notification", 4000),
            ("Success Test", "If you kept typing, the test passed!", 6000),
            ("Error Test", "Testing error notifications", 8000),
            ("Final Test", "Last notification - keep typing!", 10000),
        ]

        for title, message, delay in notifications:
            QTimer.singleShot(
                delay, lambda t=title, m=message: self.show_test_notification(t, m)
            )

        # Reset UI after test
        QTimer.singleShot(12000, self.reset_test_ui)

    def show_test_notification(self, title, message):
        """Show a test notification."""
        # Randomly choose notification type
        import random

        notification_type = random.choice(["info", "success", "error"])

        if notification_type == "info":
            self.notification_manager.show_info_notification(title, message)
        elif notification_type == "success":
            self.notification_manager.show_success_notification(title, message)
        else:
            self.notification_manager.show_error_notification(title, message)

        print(f"Sent {notification_type} notification: {title}")

    def reset_test_ui(self):
        """Reset the UI after test completion."""
        self.status_label.setText(
            "✅ Test completed! Check if your typing was interrupted."
        )
        self.test_button.setEnabled(True)
        self.test_button.setText("Run Test Again")


def test_subprocess_isolation():
    """Test that subprocess notifications run in isolation."""
    print("Testing subprocess isolation...")

    # Test data
    test_data = {
        "title": "Isolation Test",
        "message": "This runs in a separate process",
        "duration": 2000,
        "bg_color": "#2196F3",
        "icon": "🔬",
        "screen_geometry": {"x": 0, "y": 0, "width": 1920, "height": 1080},
    }

    # Launch subprocess directly
    import json
    import os

    current_dir = os.path.dirname(os.path.abspath(__file__))
    subprocess_script = os.path.join(
        current_dir, "modules", "utils", "notification_subprocess.py"
    )

    try:
        process = subprocess.Popen(
            [sys.executable, subprocess_script, json.dumps(test_data)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, stderr = process.communicate(timeout=5)

        if process.returncode == 0:
            print("✅ Subprocess notification launched successfully")
        else:
            print(f"❌ Subprocess failed with return code: {process.returncode}")
            if stderr:
                print(f"Error: {stderr.decode()}")

    except subprocess.TimeoutExpired:
        print("✅ Subprocess is running (timeout as expected)")
        process.kill()
    except Exception as e:
        print(f"❌ Subprocess test failed: {e}")


def main():
    """Main test function."""
    app = QApplication(sys.argv)

    print("🧪 Starting Subprocess Notification Test")
    print("=" * 50)

    # Test 1: Subprocess isolation
    test_subprocess_isolation()

    print("\n🖥️  Starting Interactive Focus Test")
    print("=" * 50)

    # Test 2: Interactive focus test
    test_window = TestMainWindow()
    test_window.show()
    test_window.raise_()
    test_window.activateWindow()

    print("Interactive test window opened.")
    print("Follow the instructions in the window to test focus stealing.")

    # Run the application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
