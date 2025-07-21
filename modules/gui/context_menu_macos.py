"""macOS-compatible context menu with robust focus handling."""

from typing import List, Optional, Tuple, Callable
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QFrame
from PyQt5.QtCore import Qt, QPoint, QTimer, QObject, pyqtSignal
from PyQt5.QtGui import QCursor, QKeyEvent
from core.models import MenuItem

import sip
import os


class MacOSFocusableMenu(QWidget):
    """macOS-optimized popup menu with reliable focus handling."""

    item_selected = pyqtSignal(object)
    menu_closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: List[MenuItem] = []
        self.current_index = 0
        self.item_widgets: List[QWidget] = []
        self.shift_pressed = False
        self.is_closing = False

        # macOS-specific window configuration
        self.setWindowFlags(
            Qt.Tool  # Use Tool instead of Popup for better macOS behavior
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            # Removed Qt.WindowDoesNotAcceptFocus to allow focus
        )

        # Essential attributes for macOS
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)

        # Strong focus policy
        self.setFocusPolicy(Qt.StrongFocus)

        self.setup_ui()
        self.apply_styles()

    def setup_ui(self):
        """Setup the UI layout."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(1)

    def apply_styles(self):
        """Apply dark theme styles optimized for macOS."""
        self.setStyleSheet("""
            MacOSFocusableMenu {
                background-color: rgba(43, 43, 43, 0.95);
                border: 1px solid #555555;
                border-radius: 8px;
                color: white;
                font-size: 13px;
            }
        """)

    def set_items(self, items: List[MenuItem]):
        """Set menu items and create widgets."""
        self.items = items
        self.current_index = self._find_first_selectable_item()
        self.clear_widgets()
        self.create_item_widgets()
        self.update_selection()

    def _find_first_selectable_item(self) -> int:
        """Find the first selectable item."""
        for i, item in enumerate(self.items):
            if item.enabled:
                return i
        return 0

    def clear_widgets(self):
        """Clear existing item widgets."""
        for widget in self.item_widgets:
            widget.deleteLater()
        self.item_widgets.clear()

        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def create_item_widgets(self):
        """Create widgets for menu items."""
        for i, item in enumerate(self.items):
            item_widget = self.create_menu_item_widget(item, i)
            self.layout.addWidget(item_widget)
            self.item_widgets.append(item_widget)

            # Add separator after item if requested
            if hasattr(item, "separator_after") and item.separator_after:
                separator = QFrame()
                separator.setFrameShape(QFrame.HLine)
                separator.setStyleSheet("""
                    QFrame {
                        color: #555555;
                        background-color: #555555;
                        height: 1px;
                        margin: 4px 8px;
                    }
                """)
                self.layout.addWidget(separator)
                self.item_widgets.append(separator)

    def create_menu_item_widget(self, item: MenuItem, index: int) -> QWidget:
        """Create a widget for a menu item."""
        widget = MenuItemLabel(item.label, item, index, self)
        widget.setProperty("item_index", index)
        widget.setProperty("menu_item", item)

        if not item.enabled:
            widget.setProperty("disabled", "true")

        return widget

    def on_item_clicked(self, index: int, event):
        """Handle item click with crash protection."""
        if self.is_closing:
            return

        try:
            if 0 <= index < len(self.items):
                item = self.items[index]
                if item.enabled:
                    self.shift_pressed = bool(
                        QApplication.keyboardModifiers() & Qt.ShiftModifier
                    )
                    self.is_closing = True

                    # Use delayed execution to prevent crashes
                    QTimer.singleShot(10, lambda: self._emit_selection(item))
                    QTimer.singleShot(50, self.close)
        except Exception as e:
            print(f"Click handler error: {e}")
            self.close()

    def _emit_selection(self, item):
        """Safely emit item selection signal."""
        try:
            if not self.is_closing:
                return
            self.item_selected.emit(item)
        except Exception as e:
            print(f"Signal emission error: {e}")

    def on_item_hover(self, index: int):
        """Handle item hover."""
        if index != self.current_index and 0 <= index < len(self.items):
            item = self.items[index]
            if item.enabled:
                self.current_index = index
                self.update_selection()

    def update_selection(self):
        """Update visual selection state."""
        for i, widget in enumerate(self.item_widgets):
            if (
                hasattr(widget, "property")
                and widget.property("item_index") is not None
            ):
                widget_index = widget.property("item_index")
                is_selected = widget_index == self.current_index
                widget.set_selected(is_selected)

    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard navigation."""
        if self.is_closing:
            return

        key = event.key()

        if key == Qt.Key_Shift:
            self.shift_pressed = True

        elif key in (Qt.Key_Up, Qt.Key_Down):
            self.navigate_items(key == Qt.Key_Down)

        elif key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.activate_current_item()

        elif key == Qt.Key_Escape:
            self.close()

        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        """Handle key release events."""
        if event.key() == Qt.Key_Shift:
            self.shift_pressed = False
        super().keyReleaseEvent(event)

    def navigate_items(self, down: bool):
        """Navigate through menu items."""
        if not self.items or self.is_closing:
            return

        direction = 1 if down else -1
        start_index = self.current_index

        while True:
            self.current_index = (self.current_index + direction) % len(self.items)

            current_item = self.items[self.current_index]
            if current_item.enabled:
                break

            if self.current_index == start_index:
                break

        self.update_selection()

    def activate_current_item(self):
        """Activate the currently selected item."""
        if self.is_closing:
            return

        try:
            if (
                0 <= self.current_index < len(self.items)
                and self.items[self.current_index].enabled
            ):
                item = self.items[self.current_index]
                self.is_closing = True

                # Use delayed execution to prevent crashes
                QTimer.singleShot(10, lambda: self._emit_selection(item))
                QTimer.singleShot(50, self.close)
        except Exception as e:
            print(f"Activation error: {e}")
            self.close()

    def showEvent(self, event):
        """Handle show event with macOS-specific focus grabbing."""
        super().showEvent(event)

        # macOS focus strategy: multiple delayed attempts
        focus_delays = [0, 10, 50, 100, 200]
        for delay in focus_delays:
            QTimer.singleShot(delay, self._attempt_focus_grab)

    def _attempt_focus_grab(self):
        """Attempt to grab focus with macOS-specific methods."""
        if self.is_closing or not self.isVisible():
            return

        try:
            # First, try to bring the app to foreground
            self._bring_app_to_front()

            # Force window to front
            self.raise_()
            self.activateWindow()

            # Multiple focus methods
            self.setFocus(Qt.ActiveWindowFocusReason)
            self.setFocus(Qt.PopupFocusReason)

            # macOS-specific application activation
            app = QApplication.instance()
            if app:
                app.setActiveWindow(self)
                app.processEvents()

        except Exception as e:
            print(f"Focus grab error: {e}")

    def _bring_app_to_front(self):
        """Bring the application to the front on macOS."""
        try:
            # Method 1: Try PyObjC if available
            try:
                from Foundation import NSRunningApplication

                app = NSRunningApplication.runningApplicationWithProcessIdentifier_(
                    os.getpid()
                )
                app.activateWithOptions_(1)  # NSApplicationActivateIgnoringOtherApps
                return
            except ImportError:
                pass

            # Method 2: Use AppleScript
            import subprocess

            script = f"""
            tell application "System Events"
                set frontmost of first process whose unix id is {os.getpid()} to true
            end tell
            """
            subprocess.run(
                ["osascript", "-e", script], capture_output=True, check=False, timeout=1
            )

        except Exception as e:
            print(f"App activation error: {e}")

    def closeEvent(self, event):
        """Handle close event safely."""
        self.is_closing = True

        try:
            # Emit close signal with delay to prevent crashes
            QTimer.singleShot(0, lambda: self.menu_closed.emit())
        except Exception as e:
            print(f"Close event error: {e}")

        super().closeEvent(event)

    def show_at_position(self, position: QPoint):
        """Show menu at specific position with macOS optimizations."""
        self.is_closing = False

        # Ensure menu is properly sized
        self.adjustSize()

        # Position the menu
        self.move(position)

        # Show and attempt focus
        self.show()

        # Additional macOS-specific activation
        QTimer.singleShot(0, self._macos_post_show_setup)

    def _macos_post_show_setup(self):
        """Post-show setup specific to macOS with aggressive activation."""
        try:
            # Force application to foreground using NSApplication
            self._force_app_to_foreground()

            # Ensure window is at front
            self.raise_()
            self.activateWindow()

            # Try to make the app active
            app = QApplication.instance()
            if app:
                app.setActiveWindow(self)

        except Exception as e:
            print(f"macOS post-show setup error: {e}")

    def _force_app_to_foreground(self):
        """Force the Python application to become the frontmost application."""
        try:
            # Use NSApplication to force activation
            from PyQt5.QtCore import QCoreApplication
            from PyQt5.QtMacExtras import QMacApplication

            # Force application activation
            QMacApplication.instance().requestActivate()

        except ImportError:
            # Fallback: Try using Objective-C directly
            try:
                import subprocess

                # AppleScript to activate the application
                script = """
                tell application "System Events"
                    set frontmost of first process whose unix id is {} to true
                end tell
                """.format(os.getpid())

                subprocess.run(
                    ["osascript", "-e", script], capture_output=True, check=False
                )
            except Exception as e:
                print(f"Application activation fallback failed: {e}")
        except Exception as e:
            print(f"Application activation failed: {e}")


class MenuItemLabel(QLabel):
    """Custom label for menu items with proper event handling."""

    def __init__(self, text, menu_item, index, parent_menu):
        super().__init__(text)
        self._menu_item = menu_item
        self._index = index
        self._parent_menu = parent_menu
        self._selected = False

        self.setStyleSheet("""
            QLabel {
                background-color: transparent;
                padding: 8px 16px;
                border-radius: 6px;
                margin: 1px;
                color: #f0f0f0;
                font-size: 13px;
                min-height: 24px;
                border: none;
            }
            QLabel[disabled="true"] {
                color: #666666;
            }
        """)

    def set_selected(self, selected: bool):
        """Set selection state."""
        self._selected = selected
        if selected:
            self.setStyleSheet(
                self.styleSheet()
                + """
                QLabel {
                    background-color: #007ACC;
                    color: white;
                }
            """
            )
        else:
            # Reset to normal style
            self.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    padding: 8px 16px;
                    border-radius: 6px;
                    margin: 1px;
                    color: #f0f0f0;
                    font-size: 13px;
                    min-height: 24px;
                    border: none;
                }
                QLabel[disabled="true"] {
                    color: #666666;
                }
            """)

    def mousePressEvent(self, event):
        """Handle mouse press with crash protection."""
        if event.button() == Qt.LeftButton:
            self._parent_menu.on_item_clicked(self._index, event)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        """Handle mouse enter."""
        if self._menu_item.enabled:
            self._parent_menu.on_item_hover(self._index)
        super().enterEvent(event)


class MacOSContextMenu(QObject):
    """macOS-optimized context menu wrapper."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.popup_menu: Optional[MacOSFocusableMenu] = None
        self.menu_position_offset = (0, 0)
        self.execution_callback: Optional[Callable] = None
        self.qt_active_window = None

    def set_execution_callback(self, callback: Callable):
        """Set callback for menu item execution."""
        self.execution_callback = callback

    def create_menu(self, items: List[MenuItem]) -> MacOSFocusableMenu:
        """Create a macOS-optimized popup menu."""
        if self.popup_menu and not sip.isdeleted(self.popup_menu):
            self.popup_menu.close()
            self.popup_menu.deleteLater()

        self.popup_menu = MacOSFocusableMenu(self.parent)
        self.popup_menu.set_items(items)

        # Connect signals with error handling
        self.popup_menu.item_selected.connect(self._on_item_selected)
        self.popup_menu.menu_closed.connect(self._on_menu_closed)

        return self.popup_menu

    def _on_item_selected(self, item: MenuItem):
        """Handle item selection with error protection."""
        try:
            if self.execution_callback:
                shift_pressed = (
                    self.popup_menu.shift_pressed if self.popup_menu else False
                )
                self.execution_callback(item, shift_pressed)
        except Exception as e:
            print(f"Menu execution error: {e}")
        finally:
            QTimer.singleShot(100, self._cleanup_menu)

    def _on_menu_closed(self):
        """Handle menu close."""
        try:
            self._restore_qt_focus()
        except Exception as e:
            print(f"Focus restore error: {e}")
        finally:
            QTimer.singleShot(200, self._cleanup_menu)

    def show_at_cursor(self, items: List[MenuItem]) -> None:
        """Show context menu at cursor position."""
        cursor_pos = self.get_cursor_position()
        self.show_at_position(items, cursor_pos)

    def show_at_position(
        self, items: List[MenuItem], position: Tuple[int, int]
    ) -> None:
        """Show context menu at specific position."""
        if not items:
            return

        try:
            self._store_qt_active_window()

            x, y = position
            offset_x, offset_y = self.menu_position_offset
            adjusted_pos = QPoint(x + offset_x, y + offset_y)

            menu = self.create_menu(items)
            menu.show_at_position(adjusted_pos)

        except Exception as e:
            print(f"Menu show error: {e}")

    def get_cursor_position(self) -> Tuple[int, int]:
        """Get current cursor position."""
        cursor_pos = QCursor.pos()
        return (cursor_pos.x(), cursor_pos.y())

    def set_menu_position_offset(self, offset: Tuple[int, int]) -> None:
        """Set offset for menu positioning."""
        self.menu_position_offset = offset

    def destroy(self) -> None:
        """Clean up the menu."""
        self._cleanup_menu()

    def _cleanup_menu(self):
        """Internal cleanup method."""
        try:
            if self.popup_menu and not sip.isdeleted(self.popup_menu):
                self.popup_menu.close()
                self.popup_menu.deleteLater()
            self.popup_menu = None
        except Exception as e:
            print(f"Cleanup error: {e}")

    def _store_qt_active_window(self) -> None:
        """Store Qt active window reference for focus restoration."""
        try:
            self.qt_active_window = QApplication.activeWindow()
        except Exception:
            self.qt_active_window = None

    def _restore_qt_focus(self) -> None:
        """Restore focus to the previously active Qt window."""
        try:
            if self.qt_active_window and not sip.isdeleted(self.qt_active_window):
                self.qt_active_window.activateWindow()
                self.qt_active_window.raise_()
        except Exception as e:
            print(f"Focus restore error: {e}")
        finally:
            self.qt_active_window = None

    @property
    def menu(self):
        """Compatibility property for existing code."""
        return self.popup_menu
