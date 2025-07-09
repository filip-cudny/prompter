# Enhanced Notification System

## Overview

The enhanced notification system replaces the previous daemon-based implementation with a single-process solution that provides non-focus-stealing notifications with improved performance and reliability.

## Key Improvements

### 1. Single-Process Architecture
- **Eliminated daemon process**: Removed the separate notification daemon process that was causing performance issues
- **Reduced complexity**: No more inter-process communication, PID file management, or process lifecycle handling
- **Better resource utilization**: Single Qt application instance instead of multiple processes

### 2. Enhanced Non-Focus-Stealing Implementation
- **Proper window configuration**: Uses Qt's `WindowDoesNotAcceptFocus` and `WA_ShowWithoutActivating` attributes
- **Platform-specific optimizations**: macOS-specific attributes like `WA_MacNonActivatingToolWindow`
- **Improved window level management**: Better overlay behavior without external dependencies

### 3. Improved Focus Management
- **Qt-based focus restoration**: Uses Qt's native focus management instead of subprocess calls
- **Fallback mechanisms**: Graceful degradation when Qt methods are insufficient
- **Reduced external dependencies**: Minimal reliance on system-specific tools

## Architecture

### Core Components

#### `EnhancedNotificationWidget`
- Main notification widget with proper non-activating window configuration
- Handles fade animations and positioning
- Platform-specific window behavior

#### `EnhancedNotificationManager`
- Thread-safe notification dispatcher
- Manages notification lifecycle and cleanup
- Provides different notification types (success, error, info, warning)

#### `NotificationDispatcher`
- Handles cross-thread communication for notification display
- Ensures notifications are shown on the main Qt thread

### Legacy Compatibility

The system maintains backward compatibility through:
- `PyQtNotificationManager` class (inherits from `EnhancedNotificationManager`)
- `NotificationWidget` class (inherits from `EnhancedNotificationWidget`)

## Usage

### Basic Usage

```python
from modules.utils.notifications import EnhancedNotificationManager
from PyQt5.QtWidgets import QApplication

app = QApplication([])
manager = EnhancedNotificationManager(app)

# Show different types of notifications
manager.show_success_notification("Success!", "Operation completed")
manager.show_error_notification("Error!", "Something went wrong")
manager.show_info_notification("Info", "Information message")
manager.show_warning_notification("Warning!", "Be careful")
```

### Advanced Usage

```python
# Custom duration and positioning
manager.show_info_notification(
    title="Custom Notification",
    message="This will show for 5 seconds",
    duration=5000
)

# Cleanup when done
manager.cleanup()
```

### Legacy API Support

```python
# Still works with existing code
from modules.utils.notifications import PyQtNotificationManager

manager = PyQtNotificationManager(app)
manager.show_success_notification("Legacy API", "Still supported")
```

## Platform Support

### macOS
- Uses `WA_MacNonActivatingToolWindow` and `WA_MacAlwaysShowToolWindow`
- Proper window level management to prevent focus stealing
- Enhanced focus restoration using Qt's native methods

### Linux
- Uses `X11BypassWindowManagerHint` for true overlay behavior
- Fallback to X11 methods when available
- Graceful degradation when X11 tools are not present

### Windows
- Standard Qt window flags for non-activating behavior
- Platform-specific optimizations as needed

## Performance Improvements

### Before (Daemon-based)
- Process startup/shutdown overhead
- Inter-process communication latency
- Resource duplication (separate Qt application)
- Complex lifecycle management

### After (Single-process)
- Instant notification display
- No IPC overhead
- Single Qt application instance
- Simplified resource management

## Configuration

### Window Behavior
```python
# The system automatically configures:
# - Non-activating window flags
# - Proper transparency and styling
# - Platform-specific attributes
# - Fade animations
```

### Notification Types
- **Success**: Green background, ✅ icon, 2-second duration
- **Error**: Red background, ❌ icon, 4-second duration  
- **Info**: Blue background, ℹ️ icon, 2-second duration
- **Warning**: Orange background, ⚠️ icon, 3-second duration

## Testing

### Test Script
Run the test script to verify the notification system:

```bash
python test_enhanced_notifications.py
```

### Manual Testing
1. Focus on another application
2. Trigger notifications from the prompt store
3. Verify that focus remains on the original application
4. Check that notifications appear in the top-right corner

### Test Checklist
- [ ] Notifications appear without stealing focus
- [ ] Multiple notifications stack properly
- [ ] Fade animations work smoothly
- [ ] Different notification types display correctly
- [ ] Performance is responsive
- [ ] No process overhead

## Troubleshooting

### Common Issues

#### Focus Still Being Stolen
1. Check Qt version compatibility
2. Verify window flags are properly set
3. Test on different platforms
4. Check for conflicting window attributes

#### Notifications Not Appearing
1. Ensure QApplication instance is available
2. Check desktop geometry detection
3. Verify notification widget creation
4. Test with different screen configurations

#### Performance Issues
1. Monitor notification cleanup
2. Check for memory leaks
3. Verify thread safety
4. Profile notification creation/destruction

### Debug Mode
```python
# Enable debug information
manager.enable_debug_mode(True)
```

## Migration Guide

### From Daemon-based System
1. Remove daemon startup/shutdown code
2. Update imports to use `EnhancedNotificationManager`
3. Remove IPC-related code
4. Update notification calls (API is mostly compatible)

### Code Changes Required
- Replace `_start_notification_daemon()` calls
- Remove daemon process management
- Update notification manager initialization
- Clean up IPC-related imports

## Future Enhancements

### Planned Features
- Notification queuing system
- Custom notification themes
- Sound notifications
- Notification history
- User preferences for notification behavior

### Performance Optimizations
- Lazy widget creation
- Improved memory management
- Better animation performance
- Optimized screen geometry detection

## Contributing

When contributing to the notification system:
1. Maintain backward compatibility
2. Test on all supported platforms
3. Follow Qt best practices
4. Document any new features
5. Add appropriate tests

## License

This enhanced notification system is part of the prompt-store project and follows the same license terms.