#!/usr/bin/env python3
"""Test script to verify PyQt5 migration works correctly."""

import sys
import os
import time
from typing import Optional

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication, QMenu, QAction
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QCursor

from gui.pyqt_hotkey_manager import PyQtHotkeyManager
from utils.pyqt_notifications import PyQtNotificationManager
from gui.pyqt_context_menu import PyQtContextMenu, PyQtMenuBuilder
from core.models import MenuItem, MenuItemType


class PyQtTestApp:
    """Test application to verify PyQt5 components work correctly."""

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        self.notification_manager = PyQtNotificationManager(self.app)
        self.hotkey_manager = PyQtHotkeyManager()
        self.context_menu = PyQtContextMenu()
        
        self.test_count = 0
        self.max_tests = 3
        
        self.setup_hotkeys()
        self.setup_timer()
        
    def setup_hotkeys(self):
        """Setup hotkey callbacks."""
        self.hotkey_manager.connect_context_menu_callback(self.show_test_menu)
        self.hotkey_manager.connect_re_execute_callback(self.test_notifications)
        
    def setup_timer(self):
        """Setup timer for automatic testing."""
        self.timer = QTimer()
        self.timer.timeout.connect(self.run_automatic_test)
        
    def show_test_menu(self):
        """Show a test context menu."""
        print("Showing test context menu...")
        
        # Create test menu items
        items = [
            MenuItem(
                id="test1",
                label="Test Action 1",
                item_type=MenuItemType.PROMPT,
                action=lambda: self.test_action("Action 1"),
                enabled=True
            ),
            MenuItem(
                id="test2", 
                label="Test Action 2",
                item_type=MenuItemType.PRESET,
                action=lambda: self.test_action("Action 2"),
                enabled=True
            ),
            MenuItem(
                id="test3",
                label="Disabled Action",
                item_type=MenuItemType.HISTORY,
                action=lambda: self.test_action("Action 3"),
                enabled=False
            ),
            MenuItem(
                id="quit",
                label="Quit Test",
                item_type=MenuItemType.SYSTEM,
                action=self.quit_app,
                enabled=True
            )
        ]
        
        self.context_menu.show_at_cursor(items)
        
    def test_action(self, action_name: str):
        """Test menu action execution."""
        print(f"Executed: {action_name}")
        self.notification_manager.show_success_notification(
            "Action Executed",
            f"{action_name} was triggered successfully"
        )
        
    def test_notifications(self):
        """Test notification system."""
        print("Testing notifications...")
        
        notifications = [
            ("Success", "This is a success notification", "success"),
            ("Error", "This is an error notification", "error"), 
            ("Info", "This is an info notification", "info")
        ]
        
        for i, (title, message, ntype) in enumerate(notifications):
            QTimer.singleShot(i * 1000, lambda t=title, m=message, nt=ntype: self.show_notification(t, m, nt))
            
    def show_notification(self, title: str, message: str, ntype: str):
        """Show a notification of the specified type."""
        if ntype == "success":
            self.notification_manager.show_success_notification(title, message)
        elif ntype == "error":
            self.notification_manager.show_error_notification(title, message)
        else:
            self.notification_manager.show_info_notification(title, message)
            
    def run_automatic_test(self):
        """Run automatic tests."""
        self.test_count += 1
        
        if self.test_count == 1:
            print("Running automatic test 1: Notifications")
            self.test_notifications()
        elif self.test_count == 2:
            print("Running automatic test 2: Context Menu")
            self.show_test_menu()
        elif self.test_count >= self.max_tests:
            print("All automatic tests completed. Use hotkeys for manual testing.")
            self.timer.stop()
            
    def quit_app(self):
        """Quit the test application."""
        print("Quitting test application...")
        self.hotkey_manager.stop()
        QTimer.singleShot(100, self.app.quit)
        
    def run(self):
        """Run the test application."""
        import platform
        
        system = platform.system()
        hotkey_f1 = "Cmd+F1" if system == "Darwin" else "Ctrl+F1"
        hotkey_f2 = "Cmd+F2" if system == "Darwin" else "Ctrl+F2"
        
        print("PyQt5 Test Application Started")
        print("=" * 40)
        print(f"Press {hotkey_f1} to show test menu")
        print(f"Press {hotkey_f2} to test notifications")
        print("Press Ctrl+C to stop")
        print()
        print("Starting automatic tests in 2 seconds...")
        
        try:
            # Start hotkey manager
            self.hotkey_manager.start()
            print("✓ Hotkey manager started")
            
            # Start automatic tests
            self.timer.start(2000)
            
            # Run Qt event loop
            return self.app.exec_()
            
        except KeyboardInterrupt:
            print("\nTest stopped by user")
            self.quit_app()
            return 0
        except Exception as e:
            print(f"Test error: {e}")
            return 1


def main():
    """Main test entry point."""
    print("Testing PyQt5 migration...")
    
    # Test basic PyQt5 availability
    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import QTimer
        from PyQt5.QtGui import QCursor
        print("✓ PyQt5 imports successful")
    except ImportError as e:
        print(f"✗ PyQt5 import failed: {e}")
        print("Please install PyQt5: pip install PyQt5")
        return 1
        
    # Test pynput availability  
    try:
        from pynput import keyboard
        print("✓ pynput imports successful")
    except ImportError as e:
        print(f"✗ pynput import failed: {e}")
        print("Please install pynput: pip install pynput")
        return 1
        
    # Run test app
    test_app = PyQtTestApp()
    return test_app.run()


if __name__ == "__main__":
    sys.exit(main())