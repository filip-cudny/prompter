"""PyQt5-based context menu system for the Prompter application."""

from typing import List, Optional, Tuple, Callable
from PyQt5.QtWidgets import QMenu, QAction, QApplication, QWidgetAction, QLabel, QWidget
from PyQt5.QtCore import Qt, QPoint, QTimer, QObject, QEvent
from PyQt5.QtGui import QCursor, QKeyEvent
from core.models import MenuItem, MenuItemType
import sip
import platform
import subprocess
import os


class InvisibleFocusWindow(QWidget):
    """Invisible window that grabs focus to enable QMenu keyboard navigation."""
    
    def __init__(self):
        super().__init__()
        self.menu: Optional[QMenu] = None
        self.setup_window()
        
    def setup_window(self):
        """Setup invisible window properties."""
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(1, 1)
        self.setWindowOpacity(0.01)
        
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
        
        # Ensure this window can receive keyboard events
        self.setFocusPolicy(Qt.StrongFocus)
        
        # Show menu after a short delay to ensure focus is grabbed
        QTimer.singleShot(50, lambda: self._show_menu_at_position(position))
        
        # Additional focus attempts to ensure keyboard events work
        QTimer.singleShot(100, lambda: self.setFocus(Qt.OtherFocusReason))
        QTimer.singleShot(150, lambda: self.activateWindow())
        
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
            try:
                from Foundation import NSRunningApplication
                app = NSRunningApplication.runningApplicationWithProcessIdentifier_(os.getpid())
                if app:
                    app.activateWithOptions_(1)
                    return
            except ImportError:
                pass
            
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
            self.menu.aboutToHide.connect(self._on_menu_hidden)
            self.menu.popup(position)
            
    def _on_menu_hidden(self):
        """Handle menu being hidden."""
        self.hide()
        
    def keyPressEvent(self, event):
        """Forward key events to the menu if it's visible."""
        if self.menu and self.menu.isVisible():
            # Forward key events to the menu
            QApplication.sendEvent(self.menu, event)
            event.accept()
        else:
            super().keyPressEvent(event)
            
    def closeEvent(self, event):
        """Handle close event."""
        if self.menu and self.menu.isVisible():
            self.menu.hide()
        super().closeEvent(event)


class PyQtContextMenu(QObject):
    """PyQt5-based context menu implementation with keyboard navigation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.menu: Optional[QMenu] = None
        self.menu_position_offset = (0, 0)
        self.execution_callback: Optional[Callable] = None
        self.shift_pressed = False
        self.event_filter_installed = False
        self.hovered_widgets = set()
        self.original_active_window = None
        self.qt_active_window = None
        self.focus_window: Optional[InvisibleFocusWindow] = None

        self._menu_stylesheet = """
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
                min-height: 24px;
            }
            QMenu::item:selected {
                background-color: #454545;
                color: #ffffff;
            }
            QMenu::item:focus {
                background-color: #454545;
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
        """

    def set_execution_callback(self, callback: Callable):
        """Set callback for menu item execution."""
        self.execution_callback = callback

    def create_menu(self, items: List[MenuItem]) -> QMenu:
        """Create a QMenu from menu items with keyboard navigation support."""
        menu = QMenu(self.parent)
        
        # Configure window flags for better focus behavior when triggered from external apps
        if platform.system() == "Darwin":
            # macOS needs different flags for external app focus
            menu.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        else:
            menu.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
            
        menu.setAttribute(Qt.WA_TranslucentBackground, False)
        menu.setAttribute(Qt.WA_ShowWithoutActivating, False)  # Allow activation
        menu.setStyleSheet(self._menu_stylesheet)

        # Enable keyboard navigation with strong focus
        menu.setFocusPolicy(Qt.StrongFocus)
        
        # Reset shift state and install event filter
        self.shift_pressed = False
        self.event_filter_installed = True
        menu.installEventFilter(self)

        self._add_menu_items(menu, items)
        return menu

    def create_submenu(self, parent_menu: QMenu, title: str, items: List[MenuItem]) -> QMenu:
        """Create a submenu with consistent styling."""
        submenu = QMenu(title, parent_menu)
        submenu.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        submenu.setAttribute(Qt.WA_TranslucentBackground, True)
        submenu.setStyleSheet(self._menu_stylesheet)
        submenu.setFocusPolicy(Qt.StrongFocus)
        submenu.installEventFilter(self)

        self._add_menu_items(submenu, items)
        return submenu

    def show_at_cursor(self, items: List[MenuItem]) -> None:
        """Show context menu at cursor position."""
        cursor_pos = self.get_cursor_position()
        self.show_at_position(items, cursor_pos)

    def show_at_position(self, items: List[MenuItem], position: Tuple[int, int]) -> None:
        """Show context menu at specific position with invisible focus window for keyboard navigation."""
        if not items:
            return

        try:
            self._store_qt_active_window()

            x, y = position
            offset_x, offset_y = self.menu_position_offset
            adjusted_pos = QPoint(x + offset_x, y + offset_y)

            self.shift_pressed = bool(QApplication.keyboardModifiers() & Qt.ShiftModifier)

            self.menu = self.create_menu(items)
            
            # Create focus window if needed
            if not self.focus_window:
                self.focus_window = InvisibleFocusWindow()
                
            # Use invisible focus window for robust keyboard navigation
            self.focus_window.grab_focus_and_show_menu(self.menu, adjusted_pos)

        except Exception as e:
            print(f"Menu show error: {e}")



    def _force_app_activation_macos(self):
        """Force application activation on macOS when triggered from another app."""
        try:
            # Try PyObjC first for more reliable activation
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
            
            # Additional activation attempt
            script2 = f"""
            tell application id "{os.getpid()}" to activate
            """
            subprocess.run(["osascript", "-e", script2], capture_output=True, timeout=1, check=False)
            
        except Exception:
            pass

    def _force_app_activation_windows(self):
        """Force application activation on Windows when triggered from another app."""
        try:
            import ctypes
            from ctypes import wintypes
            
            # Get current process window
            hwnd = int(self.menu.winId()) if self.menu else 0
            if hwnd:
                # SetForegroundWindow and BringWindowToTop
                user32 = ctypes.windll.user32
                user32.SetForegroundWindow(hwnd)
                user32.BringWindowToTop(hwnd)
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                
        except Exception:
            pass

    def _force_app_activation_linux(self):
        """Force application activation on Linux when triggered from another app."""
        try:
            # Use wmctrl if available
            subprocess.run(
                ["wmctrl", "-a", str(os.getpid())],
                capture_output=True,
                timeout=1,
                check=False
            )
        except Exception:
            pass

    def get_cursor_position(self) -> Tuple[int, int]:
        """Get current cursor position."""
        cursor_pos = QCursor.pos()
        return (cursor_pos.x(), cursor_pos.y())

    def set_menu_position_offset(self, offset: Tuple[int, int]) -> None:
        """Set offset for menu positioning."""
        self.menu_position_offset = offset

    def destroy(self) -> None:
        """Clean up the menu."""
        try:
            self._cleanup_menu()
        except Exception as e:
            print(f"Menu cleanup error: {e}")

    def _cleanup_menu(self):
        """Internal cleanup method."""
        if self.focus_window:
            self.focus_window.hide()
            self.focus_window.deleteLater()
            self.focus_window = None
            
        if self.menu:
            try:
                if not sip.isdeleted(self.menu):
                    self.menu.close()
                    self.menu.deleteLater()
            except Exception:
                pass
            self.menu = None
        
        self.original_active_window = None
        self.qt_active_window = None
        self.shift_pressed = False
        self.event_filter_installed = False
        self.hovered_widgets.clear()

    def _add_menu_items(self, menu: QMenu, items: List[MenuItem]) -> None:
        """Add menu items to a QMenu."""
        for item in items:
            if hasattr(item, 'submenu_items') and item.submenu_items:
                # Create submenu with consistent styling
                submenu = self.create_submenu(menu, item.label, item.submenu_items)
                submenu_action = menu.addMenu(submenu)
                submenu_action.setEnabled(item.enabled)
            else:
                action = self._create_custom_menu_item(menu, item)
                if action:
                    menu.addAction(action)

            if hasattr(item, "separator_after") and item.separator_after:
                menu.addSeparator()

    def _create_custom_menu_item(self, menu: QMenu, item: MenuItem) -> Optional[QAction]:
        """Create a custom menu item with hover effects."""

        class ClickableLabel(QLabel):
            def __init__(self, text, menu_item, context_menu):
                super().__init__(text)
                self._menu_item = menu_item
                self._context_menu = context_menu
                self._is_highlighted = False
                
                self._normal_style = """
                    QLabel {
                        background-color: transparent;
                        padding: 8px 16px;
                        border-radius: 4px;
                        margin: 1px;
                        color: #f0f0f0;
                        font-size: 13px;
                        min-height: 24px;
                    }
                    QLabel:disabled {
                        color: #666666;
                    }
                """
                self._hover_style = """
                    QLabel {
                        background-color: #454545;
                        padding: 8px 16px;
                        border-radius: 4px;
                        margin: 1px;
                        color: #ffffff;
                        font-size: 13px;
                        min-height: 24px;
                    }
                """
                self.setStyleSheet(self._normal_style)
                self.setFocusPolicy(Qt.StrongFocus)

            def mousePressEvent(self, event):
                if event.button() == Qt.LeftButton and self._menu_item.enabled:
                    if self._context_menu.execution_callback:
                        shift_pressed = bool(QApplication.keyboardModifiers() & Qt.ShiftModifier)
                        self._context_menu.execution_callback(self._menu_item, shift_pressed)
                        # Close the menu after execution
                        if self._context_menu.menu:
                            self._context_menu.menu.close()
                        if self._context_menu.focus_window:
                            self._context_menu.focus_window.hide()

            def enterEvent(self, event):
                if self._menu_item.enabled:
                    self._is_highlighted = True
                    self.setStyleSheet(self._hover_style)
                    self._context_menu.hovered_widgets.add(self)
                super().enterEvent(event)

            def leaveEvent(self, event):
                if self._menu_item.enabled and not self.hasFocus():
                    self._is_highlighted = False
                    self.setStyleSheet(self._normal_style)
                    self._context_menu.hovered_widgets.discard(self)
                super().leaveEvent(event)

            def focusInEvent(self, event):
                if self._menu_item.enabled:
                    self._is_highlighted = True
                    self.setStyleSheet(self._hover_style)
                super().focusInEvent(event)

            def focusOutEvent(self, event):
                if self._menu_item.enabled:
                    self._is_highlighted = False
                    self.setStyleSheet(self._normal_style)
                super().focusOutEvent(event)

            def keyPressEvent(self, event):
                if event.key() in (Qt.Key_Return, Qt.Key_Enter) and self._menu_item.enabled:
                    if self._context_menu.execution_callback:
                        shift_pressed = bool(QApplication.keyboardModifiers() & Qt.ShiftModifier)
                        self._context_menu.execution_callback(self._menu_item, shift_pressed)
                        # Close the menu after execution
                        if self._context_menu.menu:
                            self._context_menu.menu.close()
                        if self._context_menu.focus_window:
                            self._context_menu.focus_window.hide()
                    event.accept()
                else:
                    super().keyPressEvent(event)

        widget = ClickableLabel(item.label, item, self)
        if not item.enabled:
            widget.setEnabled(False)

        action = QWidgetAction(menu)
        action.setDefaultWidget(widget)
        
        # Ensure the action can receive focus for keyboard navigation
        action.setEnabled(item.enabled)
        
        return action

    def eventFilter(self, obj, event):
        """Filter events to detect shift key state and enable keyboard navigation."""
        if not self.event_filter_installed:
            return False

        if isinstance(obj, QMenu):
            if event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Shift:
                    self.shift_pressed = True
                elif event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space, Qt.Key_Escape):
                    # Let QMenu handle these keys natively
                    return False
            elif event.type() == QEvent.KeyRelease:
                if event.key() == Qt.Key_Shift:
                    self.shift_pressed = False
            elif event.type() == QEvent.MouseButtonPress:
                current_shift = bool(QApplication.keyboardModifiers() & Qt.ShiftModifier)
                if current_shift != self.shift_pressed:
                    self.shift_pressed = current_shift

                if event.button() == Qt.RightButton and self.shift_pressed:
                    action = obj.actionAt(event.pos())
                    if action and hasattr(action, "_menu_item"):
                        self._handle_shift_right_click(action)
                        return True
            elif event.type() == QEvent.Show:
                self.shift_pressed = bool(QApplication.keyboardModifiers() & Qt.ShiftModifier)
            elif event.type() == QEvent.Leave:
                self._clear_all_hover_states()

        return False

    def _handle_shift_right_click(self, action):
        """Handle shift + right click for alternative actions."""
        menu_item = getattr(action, "_menu_item", None)
        if menu_item and self.execution_callback:
            self.execution_callback(menu_item, True)
            if self.menu:
                self.menu.close()
            if self.focus_window:
                self.focus_window.hide()

    def _clear_all_hover_states(self):
        """Clear all hover states."""
        widgets_to_clear = list(self.hovered_widgets)
        for widget in widgets_to_clear:
            try:
                if not sip.isdeleted(widget) and hasattr(widget, "_normal_style"):
                    widget.setStyleSheet(widget._normal_style)
                if widget in self.hovered_widgets:
                    self.hovered_widgets.remove(widget)
            except (RuntimeError, AttributeError):
                if widget in self.hovered_widgets:
                    self.hovered_widgets.remove(widget)

    def _cleanup_deleted_widgets(self):
        """Clean up deleted widget references."""
        widgets_to_remove = []
        for widget in self.hovered_widgets:
            try:
                if sip.isdeleted(widget):
                    widgets_to_remove.append(widget)
            except RuntimeError:
                widgets_to_remove.append(widget)

        for widget in widgets_to_remove:
            self.hovered_widgets.discard(widget)

    def _store_qt_active_window(self):
        """Store Qt active window reference for focus restoration."""
        try:
            self.qt_active_window = QApplication.activeWindow()
        except Exception:
            self.qt_active_window = None