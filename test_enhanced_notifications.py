#!/usr/bin/env python3
"""
Test script for the enhanced notification system.
This script verifies that notifications work without stealing focus.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel
from PyQt5.QtCore import QTimer
from modules.utils.notifications import EnhancedNotificationManager


class TestWindow(QMainWindow):
    """Test window to verify focus is not stolen."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Enhanced Notifications Test")
        self.setGeometry(100, 100, 400, 300)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create layout
        layout = QVBoxLayout(central_widget)
        
        # Add instructions
        instructions = QLabel("""
Instructions:
1. Click on this window to focus it
2. Click the test buttons below
3. Verify that notifications appear WITHOUT stealing focus
4. This window should remain active and focused
        """)
        layout.addWidget(instructions)
        
        # Test buttons
        success_btn = QPushButton("Test Success Notification")
        success_btn.clicked.connect(self.test_success)
        layout.addWidget(success_btn)
        
        error_btn = QPushButton("Test Error Notification")
        error_btn.clicked.connect(self.test_error)
        layout.addWidget(error_btn)
        
        info_btn = QPushButton("Test Info Notification")
        info_btn.clicked.connect(self.test_info)
        layout.addWidget(info_btn)
        
        warning_btn = QPushButton("Test Warning Notification")
        warning_btn.clicked.connect(self.test_warning)
        layout.addWidget(warning_btn)
        
        sequence_btn = QPushButton("Test Notification Sequence")
        sequence_btn.clicked.connect(self.test_sequence)
        layout.addWidget(sequence_btn)
        
        # Status label
        self.status_label = QLabel("Ready to test notifications")
        layout.addWidget(self.status_label)
        
        # Initialize notification manager
        self.notification_manager = EnhancedNotificationManager(QApplication.instance())
        
    def test_success(self):
        """Test success notification."""
        self.status_label.setText("Testing success notification...")
        self.notification_manager.show_success_notification(
            "Success!", 
            "This is a success notification that should not steal focus"
        )
        
    def test_error(self):
        """Test error notification."""
        self.status_label.setText("Testing error notification...")
        self.notification_manager.show_error_notification(
            "Error!", 
            "This is an error notification that should not steal focus"
        )
        
    def test_info(self):
        """Test info notification."""
        self.status_label.setText("Testing info notification...")
        self.notification_manager.show_info_notification(
            "Information", 
            "This is an info notification that should not steal focus"
        )
        
    def test_warning(self):
        """Test warning notification."""
        self.status_label.setText("Testing warning notification...")
        self.notification_manager.show_warning_notification(
            "Warning!", 
            "This is a warning notification that should not steal focus"
        )
        
    def test_sequence(self):
        """Test a sequence of notifications."""
        self.status_label.setText("Testing notification sequence...")
        
        # Show multiple notifications with delays
        self.notification_manager.show_info_notification(
            "Sequence Test", 
            "Notification 1 of 4"
        )
        
        QTimer.singleShot(1000, lambda: self.notification_manager.show_success_notification(
            "Sequence Test", 
            "Notification 2 of 4"
        ))
        
        QTimer.singleShot(2000, lambda: self.notification_manager.show_warning_notification(
            "Sequence Test", 
            "Notification 3 of 4"
        ))
        
        QTimer.singleShot(3000, lambda: self.notification_manager.show_error_notification(
            "Sequence Test", 
            "Notification 4 of 4 - Test complete!"
        ))
        
        QTimer.singleShot(4000, lambda: self.status_label.setText("Sequence test complete"))


def main():
    """Main function to run the test."""
    app = QApplication(sys.argv)
    
    # Create and show test window
    window = TestWindow()
    window.show()
    
    # Bring window to front
    window.raise_()
    window.activateWindow()
    
    print("Enhanced Notifications Test")
    print("=" * 50)
    print("Instructions:")
    print("1. Keep this terminal/console window visible")
    print("2. Click on the test window to focus it")
    print("3. Click the test buttons")
    print("4. Verify that notifications appear in the top-right corner")
    print("5. IMPORTANT: The test window should remain focused!")
    print("6. If focus is stolen, the implementation needs improvement")
    print("=" * 50)
    
    # Run the application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()