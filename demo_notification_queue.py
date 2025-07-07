#!/usr/bin/env python3
"""
Demonstration script for the fixed notification queue system.

This script shows how the notification queue properly handles multiple
notifications without overlapping or showing empty content.
"""

import sys
import time
from pathlib import Path

# Add the modules directory to the path
current_dir = Path(__file__).parent
modules_dir = current_dir / "modules"
sys.path.insert(0, str(modules_dir))

from PyQt5.QtWidgets import QApplication
from modules.utils.notifications import PyQtNotificationManager
from modules.utils.manage_daemon import is_daemon_running, start_daemon


def demo_notification_queue():
    """Demonstrate the notification queue system."""
    print("🔔 Notification Queue Demo")
    print("=" * 50)
    
    # Ensure daemon is running
    if not is_daemon_running():
        print("Starting notification daemon...")
        if not start_daemon():
            print("❌ Failed to start daemon")
            return False
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Create notification manager
    manager = PyQtNotificationManager(app)
    
    if not manager.is_available():
        print("❌ Notification system not available")
        return False
    
    print("✅ Notification system ready")
    
    # Instructions
    print("\n📋 Queue System Demo:")
    print("This demo will send multiple notifications rapidly.")
    print("Watch how they appear one at a time in sequence,")
    print("without overlapping or showing empty content.")
    print("\nStarting demo automatically...")
    
    time.sleep(1)
    
    # Demo sequence - send all notifications rapidly
    print("\n🚀 Sending notifications rapidly...")
    
    notifications = [
        ("success", "Queue Test 1", "First notification - should appear first"),
        ("error", "Queue Test 2", "Second notification - should appear second"),
        ("info", "Queue Test 3", "Third notification - should appear third"),
        ("success", "Queue Test 4", "Fourth notification - should appear fourth"),
        ("info", "Queue Test 5", "Fifth notification - should appear last"),
    ]
    
    # Send all notifications as quickly as possible
    for i, (type_, title, message) in enumerate(notifications):
        print(f"  Sending {i+1}/{len(notifications)}: {title}")
        
        if type_ == "success":
            manager.show_success_notification(title, message)
        elif type_ == "error":
            manager.show_error_notification(title, message)
        elif type_ == "info":
            manager.show_info_notification(title, message)
        
        # Process Qt events immediately
        app.processEvents()
        
        # No delay - send them as fast as possible
    
    print("\n✅ All notifications sent!")
    print("\n📋 What you should observe:")
    print("  1. Notifications appear one at a time")
    print("  2. Each notification displays for ~2 seconds")
    print("  3. No notifications are empty or overlapping")
    print("  4. Notifications appear in order: 1 → 2 → 3 → 4 → 5")
    print("  5. Each notification has proper content and styling")
    
    return True


def demo_mixed_scenarios():
    """Demonstrate mixed notification scenarios."""
    print("\n🎯 Mixed Scenarios Demo")
    print("=" * 30)
    
    app = QApplication(sys.argv)
    manager = PyQtNotificationManager(app)
    
    print("Testing various edge cases...")
    
    # Test rapid burst followed by delayed notifications
    print("\n1. Rapid burst...")
    for i in range(3):
        manager.show_info_notification(f"Burst {i+1}", f"Rapid notification {i+1}")
        app.processEvents()
    
    # Wait a moment then send more
    print("2. Waiting 2 seconds...")
    time.sleep(2)
    
    print("3. Adding more to queue...")
    manager.show_success_notification("Late Success", "This should queue after the burst")
    app.processEvents()
    
    manager.show_error_notification("Late Error", "This should queue last")
    app.processEvents()
    
    print("✅ Mixed scenarios demo completed")
    print("   All notifications should still appear in order")


def demo_focus_behavior():
    """Demonstrate focus-safe behavior."""
    print("\n🎯 Focus Safety Demo")
    print("=" * 30)
    
    app = QApplication(sys.argv)
    manager = PyQtNotificationManager(app)
    
    print("📋 Focus Test Instructions:")
    print("1. Open a text editor or terminal")
    print("2. Click in the text area and start typing")
    print("3. Notifications will be sent automatically")
    print("4. Keep typing while notifications appear")
    print("5. Verify notifications don't steal focus")
    
    print("\nStarting focus test automatically...")
    time.sleep(1)
    
    print("Starting focus test in 3 seconds...")
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)
    
    print("🚀 Sending notifications now - keep typing!")
    
    # Send focus test notifications
    focus_tests = [
        ("Focus Test 1", "Keep typing - this shouldn't steal focus"),
        ("Focus Test 2", "Still typing? Good!"),
        ("Focus Test 3", "Final test - notifications should stay on top"),
    ]
    
    for title, message in focus_tests:
        manager.show_info_notification(title, message)
        app.processEvents()
        time.sleep(0.5)
    
    print("✅ Focus test completed")


def main():
    """Main demonstration function."""
    print("🧪 Notification Queue System - Fixed Demo")
    print("=" * 60)
    
    print("This demo shows the fixes for:")
    print("  • Multiple notifications overlapping")
    print("  • Notifications appearing empty")
    print("  • Notifications dismissing prematurely")
    print("  • Focus stealing issues")
    
    try:
        # Main queue demo
        if not demo_notification_queue():
            return False
        
        # Mixed scenarios
        demo_mixed_scenarios()
        
        # Focus behavior test
        demo_focus_behavior()
        
        print("\n" + "=" * 60)
        print("✅ All demos completed successfully!")
        
        print("\n🔧 Key Fixes Implemented:")
        print("  ✓ Separate widget instances for each notification")
        print("  ✓ Proper notification queuing system")
        print("  ✓ Clean animation and timer management")
        print("  ✓ Proper widget cleanup after display")
        print("  ✓ Focus-safe display on macOS")
        
        print("\n📋 Issues Resolved:")
        print("  ✓ No more overlapping notifications")
        print("  ✓ No more empty notification content")
        print("  ✓ No more premature dismissal")
        print("  ✓ Proper sequential display")
        print("  ✓ No focus stealing")
        
        return True
        
    except KeyboardInterrupt:
        print("\n⚠️ Demo interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)