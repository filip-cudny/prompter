# PyQt5 Migration Guide

This document explains the migration from tkinter to PyQt5 and how to use the new PyQt5-based application.

## Why PyQt5?

The original tkinter-based application had a critical issue on macOS:

### The Problem
1. When the context menu was triggered, actions worked correctly
2. After executing an action, the active app switched to "Python" 
3. With Python as the active app, subsequent context menu actions would fail
4. Users had to switch focus to another app to restore functionality

### Root Cause
- **tkinter Focus Issue**: tkinter causes the Python process to become the active application on macOS
- **Event Handling Interference**: Once Python becomes active, tkinter's event handling gets confused
- **Window Manager Integration**: tkinter doesn't integrate cleanly with macOS's window manager
- **Hidden Root Window Problem**: Even hidden tkinter windows interfere with event dispatching

### The Solution
PyQt5 handles macOS integration much better:
- No focus stealing issues
- Proper integration with macOS window manager
- Better event handling for global hotkeys
- Native-looking menus and notifications

## Installation

Install PyQt5 dependencies:

```bash
pip install PyQt5>=5.15.0
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

## Usage

### Running the Application

**New PyQt5 Application:**
```bash
python main.py
```

**Old tkinter Application (deprecated):**
```bash
python -m app.application
```

### Command Line Options

```bash
python main.py --config /path/to/config.json
```

### Hotkeys

The hotkeys remain the same:

- **macOS**: 
  - `Cmd+F1`: Show context menu
  - `Cmd+F2`: Execute active prompt
  
- **Linux/Windows**:
  - `Ctrl+F1`: Show context menu  
  - `Ctrl+F2`: Execute active prompt

### System Tray

The PyQt5 version includes a system tray icon (when available) that provides:
- Right-click menu with options
- Visual indicator that the app is running
- Alternative way to access functions

## Testing

Test the PyQt5 migration:

```bash
python test_pyqt.py
```

This will:
1. Test PyQt5 component imports
2. Test hotkey detection
3. Test context menu display
4. Test notification system
5. Run automatic tests

## Architecture Changes

### Component Mapping

| tkinter Component | PyQt5 Component | Description |
|-------------------|-----------------|-------------|
| `tk.Tk()` | `QApplication` | Main application |
| `tkinter.Menu` | `QMenu` | Context menus |
| Custom snackbar | `NotificationWidget` | Notifications |
| tkinter events | Qt signals | Thread communication |
| Manual positioning | Qt positioning | Menu positioning |

### File Structure

```
gui/
├── hotkey_manager.py          # Old tkinter-based (deprecated)
├── pyqt_hotkey_manager.py     # New PyQt5-based hotkey manager
├── pyqt_context_menu.py       # New PyQt5-based context menus
├── pyqt_menu_coordinator.py   # New PyQt5-based menu coordinator
└── context_menu.py            # Old tkinter-based (deprecated)

utils/
├── notifications.py           # Old tkinter-based (deprecated)  
└── pyqt_notifications.py      # New PyQt5-based notifications

app/
├── application.py             # Old tkinter-based (deprecated)
└── pyqt_application.py        # New PyQt5-based application
```

### Key Technical Changes

1. **Thread Safety**: Uses Qt signals for thread-safe communication between pynput and Qt
2. **Event Loop**: Uses Qt's event loop instead of manual polling
3. **Menu Rendering**: Uses native Qt menus instead of tkinter menus
4. **Notifications**: Uses Qt widgets with animations instead of tkinter snackbars
5. **System Integration**: Better integration with system tray and window manager

## Migration Benefits

### Fixed Issues
- ✅ **No more focus stealing on macOS**
- ✅ **Reliable context menu actions**
- ✅ **Better system integration**
- ✅ **More stable hotkey handling**

### New Features
- ✅ **System tray icon**
- ✅ **Animated notifications**
- ✅ **Better menu styling**
- ✅ **Improved error handling**

### Performance Improvements
- ✅ **More efficient event handling**
- ✅ **Better memory management**
- ✅ **Reduced CPU usage**

## Troubleshooting

### PyQt5 Installation Issues

**macOS:**
```bash
# If you get Qt platform plugin errors
export QT_QPA_PLATFORM_PLUGIN_PATH=/usr/local/lib/python3.x/site-packages/PyQt5/Qt5/plugins

# Alternative installation
brew install pyqt5
pip install PyQt5
```

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install python3-pyqt5

# CentOS/RHEL
sudo yum install PyQt5
```

**Windows:**
```bash
pip install PyQt5
```

### Common Issues

**1. "No module named 'PyQt5'"**
```bash
pip install PyQt5>=5.15.0
```

**2. "qt.qpa.plugin: Could not load the Qt platform plugin"**
- Reinstall PyQt5
- Check system dependencies
- Try setting QT_QPA_PLATFORM_PLUGIN_PATH

**3. Hotkeys not working**
- Check accessibility permissions (macOS)
- Ensure pynput is installed
- Run as administrator (Windows)

**4. System tray not showing**
- System tray might not be available on your desktop environment
- The app will still work without system tray

## Backwards Compatibility

The core functionality remains identical:
- Same configuration file format
- Same command line options
- Same hotkey combinations
- Same menu structure
- Same execution handlers

Only the GUI framework has changed from tkinter to PyQt5.

## Development Notes

### Adding New Features

When adding new GUI features:
1. Use PyQt5 components (`QWidget`, `QMenu`, etc.)
2. Use Qt signals for thread communication
3. Follow the existing pattern in `pyqt_*.py` files
4. Test on multiple platforms

### Code Style

- Use Qt signals for thread-safe communication
- Inherit from `QObject` when using signals
- Use `QTimer.singleShot()` for delayed actions
- Follow PyQt5 naming conventions

### Testing

Always test new features with:
```bash
python test_pyqt.py
```

This ensures basic PyQt5 functionality works correctly.

## Deprecation Notice

The following files are deprecated and will be removed in future versions:
- `gui/hotkey_manager.py`
- `gui/context_menu.py` 
- `utils/notifications.py`
- `app/application.py`

Use the PyQt5 equivalents instead.