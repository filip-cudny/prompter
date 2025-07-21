"""
Native QMenu implementation with invisible focus window for cross-platform keyboard navigation.
"""

import os
import platform
import subprocess
from typing import Optional, Callable, List, Dict, Any, Tuple
from PyQt5.QtWidgets import (
    QWidget, QMenu, QAction, QApplication, QDesktopWidget
)
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QPoint, Qt
from PyQt5.QtGui import QKeySequence


class InvisibleFocusWindow(QWidget):
    """Invisible window that grabs focus to enable QMenu keyboard navigation."""
    
    menu_closed = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.menu: Optional[QMenu] = None
        self.setup_window()
        
    def setup_window(self):
        """Setup invisible window properties."""
        # Make window invisible but focusable
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(1, 1)
        self.setWindowOpacity(0.01)  # Nearly invisible but not completely
        
    def grab_focus_and_show_menu(self, menu: QMenu, position: QPoint):
        """Grab focus and show the menu."""
        self.menu = menu
        
        # Position the invisible window near the menu
        self.move(position.x(), position.y())
        
        # Force application activation
        self._force_app_activation()
        
        # Show invisible window and grab focus
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.OtherFocusReason)
        
        # Show menu after a short delay to ensure focus is grabbed
        QTimer.singleShot(50, lambda: self._show_menu_at_position(position))
        
    def _force_app_activation(self):
        """Force application activation based on platform."""
        if platform.system() == "Darwin":
            self._activate_macos()
        elif platform.system() == "Windows":
            self._activate_windows()
        elif platform.system() == "Linux":
            self._activate_linux()
            
    def _activate_macos(self):
        """Activate application on macOS."""
        try:
            # Try PyObjC first
            try:
                from Foundation import NSRunningApplication
                app = NSRunningApplication.runningApplicationWithProcessIdentifier_(os.getpid())
                if app:
                    app.activateWithOptions_(1)  # NSApplicationActivateIgnoringOtherApps
                    return
            except ImportError:
                pass
            
            # Fallback to AppleScript
            script = f"""
            tell application "System Events"
                set frontmost of first process whose unix id is {os.getpid()} to true
            end tell
            """
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=2, check=False)
            
        except Exception:
            pass
            
    def _activate_windows(self):
        """Activate application on Windows."""
        try:
            import ctypes
            hwnd = int(self.winId())
            if hwnd:
                user32 = ctypes.windll.user32
                user32.SetForegroundWindow(hwnd)
                user32.BringWindowToTop(hwnd)
        except Exception:
            pass
            
    def _activate_linux(self):
        """Activate application on Linux."""
        try:
            subprocess.run(
                ["wmctrl", "-a", str(os.getpid())],
                capture_output=True,
                timeout=1,
                check=False
            )
        except Exception:
            pass
    
    def _show_menu_at_position(self, position: QPoint):
        """Show the menu at the specified position."""
        if self.menu and not self.menu.isVisible():
            # Connect menu aboutToHide to our cleanup
            self.menu.aboutToHide.connect(self._on_menu_hidden)
            
            # Show menu
            self.menu.exec_(position)
            
    def _on_menu_hidden(self):
        """Handle menu being hidden."""
        self.menu_closed.emit()
        self.hide()
        
    def keyPressEvent(self, event):
        """Forward key events to the menu if it's visible."""
        if self.menu and self.menu.isVisible():
            # Forward the key event to the menu
            QApplication.sendEvent(self.menu, event)
        else:
            super().keyPressEvent(event)
            
    def closeEvent(self, event):
        """Handle close event."""
        if self.menu and self.menu.isVisible():
            self.menu.hide()
        super().closeEvent(event)


class NativeContextMenu(QObject):
    """Native QMenu-based context menu with proper keyboard navigation support."""
    
    item_selected = pyqtSignal(dict)
    menu_closed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.focus_window: Optional[InvisibleFocusWindow] = None
        self.current_menu: Optional[QMenu] = None
        self.execution_callback: Optional[Callable] = None
        self.menu_position_offset = (0, 0)
        
    def set_execution_callback(self, callback: Callable):
        """Set the callback for menu item execution."""
        self.execution_callback = callback
        
    def create_menu(self, items: List[Dict[str, Any]]) -> QMenu:
        """Create a native QMenu from menu items."""
        menu = QMenu()
        self._setup_menu_style(menu)
        self._add_menu_items(menu, items)
        return menu
        
    def _setup_menu_style(self, menu: QMenu):
        """Apply styling to the menu."""
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 4px;
                color: #ffffff;
                font-size: 13px;
            }
            QMenu::item {
                background-color: transparent;
                padding: 8px 16px;
                border-radius: 4px;
                margin: 1px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
                color: #ffffff;
            }
            QMenu::item:disabled {
                color: #666666;
            }
            QMenu::separator {
                height: 1px;
                background-color: #555555;
                margin: 4px 8px;
            }
            QMenu::indicator {
                width: 16px;
                height: 16px;
                margin-left: 4px;
            }
        """)
        
    def _add_menu_items(self, menu: QMenu, items: List[Dict[str, Any]]):
        """Add items to the menu."""
        for item in items:
            if item.get('type') == 'separator':
                menu.addSeparator()
                continue
                
            action = QAction(item.get('text', ''), menu)
            
            # Handle shortcuts
            if 'shortcut' in item:
                action.setShortcut(QKeySequence(item['shortcut']))
                
            # Handle enabled state
            if 'enabled' in item:
                action.setEnabled(item['enabled'])
                
            # Handle submenu
            if 'submenu' in item and item['submenu']:
                submenu = QMenu(item.get('text', ''), menu)
                self._setup_menu_style(submenu)
                self._add_menu_items(submenu, item['submenu'])
                action.setMenu(submenu)
            else:
                # Handle action execution
                action.triggered.connect(lambda checked, item=item: self._execute_item(item))
                
            menu.addAction(action)
            
    def _execute_item(self, item: Dict[str, Any]):
        """Execute a menu item."""
        self.item_selected.emit(item)
        if self.execution_callback:
            # If there's a stored MenuItem object, use it
            if 'menu_item' in item:
                self.execution_callback(item['menu_item'])
            # If there's a direct action, execute it
            elif 'action' in item and item['action']:
                try:
                    result = item['action']()
                    # Handle result if needed
                except Exception as e:
                    print(f"Error executing action: {e}")
            else:
                self.execution_callback(item)
            
    def show_at_cursor(self):
        """Show menu at cursor position."""
        cursor_pos = self.get_cursor_position()
        self.show_at_position(cursor_pos)
        
    def show_at_position(self, position: QPoint, items: List[Dict[str, Any]] = None):
        """Show menu at specific position."""
        if items:
            self.current_menu = self.create_menu(items)
        
        if not self.current_menu:
            return
            
        # Apply position offset
        offset_x, offset_y = self.menu_position_offset
        adjusted_position = QPoint(position.x() + offset_x, position.y() + offset_y)
        
        # Adjust for screen bounds
        adjusted_position = self.adjust_for_screen_bounds(adjusted_position)
        
        # Create focus window if needed
        if not self.focus_window:
            self.focus_window = InvisibleFocusWindow()
            self.focus_window.menu_closed.connect(self._on_menu_closed)
            
        # Show menu with focus grabbing
        self.focus_window.grab_focus_and_show_menu(self.current_menu, adjusted_position)
        
    def _on_menu_closed(self):
        """Handle menu being closed."""
        self.menu_closed.emit()
        
    def get_cursor_position(self) -> QPoint:
        """Get current cursor position."""
        return QApplication.instance().desktop().cursor().pos()
        
    def adjust_for_screen_bounds(self, position: QPoint) -> QPoint:
        """Adjust menu position to stay within screen bounds."""
        screen = QDesktopWidget().screenGeometry()
        
        # Estimate menu size (rough approximation)
        menu_width = 200
        menu_height = 300
        
        # Adjust X position
        if position.x() + menu_width > screen.right():
            position.setX(screen.right() - menu_width)
        if position.x() < screen.left():
            position.setX(screen.left())
            
        # Adjust Y position
        if position.y() + menu_height > screen.bottom():
            position.setY(screen.bottom() - menu_height)
        if position.y() < screen.top():
            position.setY(screen.top())
            
        return position
        
    def set_menu_position_offset(self, offset: Tuple[int, int]):
        """Set position offset for the menu."""
        self.menu_position_offset = offset
        
    def destroy(self):
        """Clean up resources."""
        if self.focus_window:
            self.focus_window.hide()
            self.focus_window.deleteLater()
            self.focus_window = None
            
        if self.current_menu:
            self.current_menu.hide()
            self.current_menu.deleteLater()
            self.current_menu = None
            
    @property
    def menu(self):
        """Get the current menu for compatibility."""
        return self.current_menu