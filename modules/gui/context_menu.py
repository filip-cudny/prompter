"""PyQt5-based context menu system for the Prompter application."""

from typing import List, Optional, Tuple, Callable
from PyQt5.QtWidgets import (
    QMenu,
    QAction,
    QApplication,
    QWidget,
    QVBoxLayout,
    QLabel,
    QFrame,
    QWidgetAction,
)
from PyQt5.QtCore import Qt, QPoint, QTimer, QObject, QEvent, pyqtSignal
from PyQt5.QtGui import QCursor, QKeyEvent
from core.models import MenuItem, MenuItemType

from PyQt5.QtWidgets import QWidgetAction, QLabel
from PyQt5.QtCore import Qt
import sip
import platform
import os
import subprocess


class FocusablePopupMenu(QWidget):
    """Custom popup menu widget that can receive focus and handle keyboard navigation."""

    item_selected = pyqtSignal(object)
    menu_closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: List[MenuItem] = []
        self.current_index = 0
        self.item_widgets: List[QWidget] = []
        self.shift_pressed = False

        # Better window flags for cross-platform focus handling
        flags = Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint

        # Platform-specific window flags
        if platform.system() == "Darwin":  # macOS
            # On macOS, use standard popup flags that allow focus
            flags = Qt.Popup | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        else:  # Linux/X11
            flags |= Qt.X11BypassWindowManagerHint

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setFocusPolicy(Qt.StrongFocus)

        self.setup_ui()
        self.apply_styles()

    def setup_ui(self):
        """Setup the UI layout."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(1)

    def apply_styles(self):
        """Apply dark theme styles."""
        self.setStyleSheet("""
            FocusablePopupMenu {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                border-radius: 6px;
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
        """Find the first selectable (enabled) item."""
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
        widget = QLabel(item.label)
        widget.setProperty("item_index", index)
        widget.setProperty("menu_item", item)

        widget.setStyleSheet("""
            QLabel {
                background-color: transparent;
                padding: 8px 16px;
                border-radius: 4px;
                margin: 1px;
                color: #f0f0f0;
                font-size: 13px;
                min-height: 24px;
                border: none;
            }
            QLabel[selected="true"] {
                background-color: #454545;
                border-radius: 4px;
            }
            QLabel[disabled="true"] {
                color: #666666;
            }
        """)

        if not item.enabled:
            widget.setProperty("disabled", "true")

        def make_click_handler(item_index):
            def handler(event):
                self.on_item_clicked(item_index, event)

            return handler

        def make_hover_handler(item_index):
            def handler(event):
                self.on_item_hover(item_index)

            return handler

        widget.mousePressEvent = make_click_handler(index)
        widget.enterEvent = make_hover_handler(index)

        return widget

    def on_item_clicked(self, index: int, event):
        """Handle item click."""
        try:
            if index < len(self.items):
                item = self.items[index]
                if item.enabled:
                    self.shift_pressed = bool(
                        QApplication.keyboardModifiers() & Qt.ShiftModifier
                    )
                    # Emit signal first, then close to prevent crashes
                    QTimer.singleShot(0, lambda: self.item_selected.emit(item))
                    QTimer.singleShot(10, lambda: self.close())
        except Exception as e:
            print(f"Click handler error: {e}")
            self.close()

    def on_item_hover(self, index: int):
        """Handle item hover."""
        if index != self.current_index and index < len(self.items):
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
                widget.setProperty("selected", "true" if is_selected else "false")
                widget.style().unpolish(widget)
                widget.style().polish(widget)

    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard navigation."""
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
        if not self.items:
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
        try:
            if (
                self.current_index < len(self.items)
                and self.items[self.current_index].enabled
            ):
                item = self.items[self.current_index]
                # Emit signal first, then close to prevent crashes
                QTimer.singleShot(0, lambda: self.item_selected.emit(item))
                QTimer.singleShot(10, lambda: self.close())
        except Exception as e:
            print(f"Activation error: {e}")
            self.close()

    def showEvent(self, event):
        """Handle show event - grab focus."""
        super().showEvent(event)
        # Use multiple attempts to grab focus on macOS
        QTimer.singleShot(10, self._grab_focus)
        QTimer.singleShot(50, self._grab_focus)
        QTimer.singleShot(100, self._grab_focus)

    def _grab_focus(self):
        """Grab focus with multiple attempts for macOS compatibility."""
        try:
            # On macOS, force the application to become active first
            if platform.system() == "Darwin":
                self._force_app_activation_macos()

            self.raise_()
            self.activateWindow()
            self.setFocus(Qt.ActiveWindowFocusReason)

            # Force the application to become active
            app = QApplication.instance()
            if app:
                app.setActiveWindow(self)

            # Check if focus was successful
            QTimer.singleShot(10, self._check_focus_success)
        except Exception as e:
            print(f"Focus grab error: {e}")

    def _check_focus_success(self):
        """Check if focus grab was successful."""
        try:
            has_focus = self.hasFocus()

            if not has_focus and platform.system() == "Darwin":
                self.setWindowState(Qt.WindowActive)
                QTimer.singleShot(50, lambda: self.setFocus(Qt.PopupFocusReason))
        except Exception as e:
            pass

    def _force_app_activation_macos(self):
        """Force application activation on macOS when triggered from another app."""
        try:
            # Method 1: Try PyObjC if available
            try:
                from Foundation import NSRunningApplication

                app = NSRunningApplication.runningApplicationWithProcessIdentifier_(
                    os.getpid()
                )
                if app:
                    app.activateWithOptions_(
                        1
                    )  # NSApplicationActivateIgnoringOtherApps
                    return
            except ImportError:
                pass

            # Method 2: Use AppleScript to activate the process
            script = f"""
            tell application "System Events"
                set frontmost of first process whose unix id is {os.getpid()} to true
            end tell
            """
            subprocess.run(
                ["osascript", "-e", script], capture_output=True, timeout=2, check=False
            )

        except Exception:
            pass

    def closeEvent(self, event):
        """Handle close event."""
        try:
            # Emit signal with delay to prevent crashes
            QTimer.singleShot(0, lambda: self.menu_closed.emit())
        except Exception as e:
            print(f"Close event error: {e}")
        super().closeEvent(event)

    def show_at_position(self, position: QPoint):
        """Show menu at specific position."""
        self.move(position)
        self.adjustSize()
        self.show()

        # Additional focus attempts for macOS
        if platform.system() == "Darwin":
            QTimer.singleShot(0, lambda: self.setFocus(Qt.ActiveWindowFocusReason))
            QTimer.singleShot(0, lambda: self.activateWindow())
            QTimer.singleShot(0, lambda: self.raise_())
            QTimer.singleShot(100, lambda: self.setFocus(Qt.PopupFocusReason))


class PyQtContextMenu(QObject):
    """PyQt5-based context menu implementation with keyboard navigation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.popup_menu: Optional[FocusablePopupMenu] = None
        self.menu_position_offset = (0, 0)
        self.original_active_window = None
        self.qt_active_window = None
        self.execution_callback: Optional[Callable] = None
        self.shift_pressed = False
        self.event_filter_installed = False
        self.hovered_widgets = set()

        self._menu_stylesheet = """
            QMenu {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 4px;
                color: white;
                font-size: 13px;
            }
            QMenu::item {
                background-color: transparent;
                padding: 8px 16px;
                border-radius: 4px;
                margin: 1px;
                color: #f0f0f0;
                font-size: 13px;
                min-height: 24px;
                border: none;
            }
            QMenu::item:selected {
                background-color: #454545;
                border-radius: 4px;
            }
            QMenu::item:disabled {
                color: #666666;
            }
            QMenu::separator {
                height: 1px;
                background-color: #555555;
                margin: 4px 8px;
            }
        """

    def set_execution_callback(self, callback: Callable):
        """Set callback for menu item execution."""
        self.execution_callback = callback

    def create_menu(self, items: List[MenuItem]) -> FocusablePopupMenu:
        """Create a focusable popup menu from menu items."""
        if self.popup_menu:
            self.popup_menu.deleteLater()

        self.popup_menu = FocusablePopupMenu(self.parent)
        self.popup_menu.set_items(items)

        self.popup_menu.item_selected.connect(self._on_item_selected)
        self.popup_menu.menu_closed.connect(self._on_menu_closed)

        return self.popup_menu

    def _on_item_selected(self, item: MenuItem):
        """Handle item selection."""
        try:
            if self.execution_callback:
                shift_pressed = (
                    self.popup_menu.shift_pressed if self.popup_menu else False
                )
                self.execution_callback(item, shift_pressed)
        except Exception as e:
            print(f"Menu execution error: {e}")
        finally:
            # Ensure menu cleanup
            QTimer.singleShot(50, self._cleanup_menu)

    def _on_menu_closed(self):
        """Handle menu close."""
        try:
            self._restore_qt_focus()
        except Exception as e:
            print(f"Focus restore error: {e}")
        finally:
            QTimer.singleShot(100, self._cleanup_menu)

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

            # macOS specific: Force application activation
            if platform.system() == "Darwin":
                QTimer.singleShot(0, self._force_macos_activation)

        except Exception as e:
            print(f"Menu show error: {e}")

    def get_cursor_position(self) -> Tuple[int, int]:
        """Get current cursor position."""
        cursor_pos = QCursor.pos()
        return (cursor_pos.x(), cursor_pos.y())

    def adjust_for_screen_bounds(
        self, position: QPoint, items: List[MenuItem]
    ) -> QPoint:
        """Adjust menu position to stay within screen bounds."""
        return position

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
        if self.popup_menu:
            try:
                if not sip.isdeleted(self.popup_menu):
                    self.popup_menu.close()
                    self.popup_menu.deleteLater()
            except Exception as e:
                print(f"Popup cleanup error: {e}")
            self.popup_menu = None
        self.original_active_window = None
        self.qt_active_window = None
        self.shift_pressed = False
        self.event_filter_installed = False
        self.hovered_widgets.clear()

    def _force_macos_activation(self):
        """Force application activation on macOS."""
        try:
            if platform.system() == "Darwin":
                # Force the entire application to become active
                self._activate_application_macos()

                app = QApplication.instance()
                if app and self.popup_menu and not sip.isdeleted(self.popup_menu):
                    # Try to activate the application
                    app.setActiveWindow(self.popup_menu)
                    self.popup_menu.raise_()
                    self.popup_menu.activateWindow()

                    # Try to get focus with different focus reasons
                    for focus_reason in [
                        Qt.ActiveWindowFocusReason,
                        Qt.PopupFocusReason,
                        Qt.OtherFocusReason,
                    ]:
                        self.popup_menu.setFocus(focus_reason)
        except Exception as e:
            print(f"macOS activation error: {e}")

    def _activate_application_macos(self):
        """Activate the entire application on macOS."""
        try:
            # Use AppleScript to bring the application to front
            script = f"""
            tell application "System Events"
                tell process id {os.getpid()}
                    set frontmost to true
                end tell
            end tell
            """
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=1)
        except Exception as e:
            print(f"Application activation error: {e}")

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
            print(f"Qt focus restore error: {e}")
        finally:
            self.qt_active_window = None

    def create_submenu(
        self, parent_menu: QMenu, title: str, items: List[MenuItem]
    ) -> QMenu:
        """Create a submenu with consistent styling."""
        title_with_arrow = f"{title}"
        submenu = parent_menu.addMenu(title_with_arrow)
        submenu.setWindowFlags(
            Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        )
        submenu.setAttribute(Qt.WA_TranslucentBackground, True)
        submenu.setStyleSheet(self._menu_stylesheet)

        submenu.installEventFilter(self)
        self._cleanup_deleted_widgets()
        self._add_menu_items(submenu, items)
        return submenu

    def _add_menu_items(self, menu: QMenu, items: List[MenuItem]) -> None:
        """Add menu items to a QMenu."""
        for item in items:
            if hasattr(item, "submenu_items") and item.submenu_items:
                self.create_submenu(menu, item.label, item.submenu_items)
            else:
                action = self._create_custom_menu_item(menu, item)
                if action:
                    menu.addAction(action)

            if hasattr(item, "separator_after") and item.separator_after:
                menu.addSeparator()

    def _create_custom_menu_item(
        self, menu: QMenu, item: MenuItem
    ) -> Optional[QAction]:
        """Create a custom menu item with hover effects."""

        class ClickableLabel(QLabel):
            def __init__(self, text, menu_item, context_menu):
                super().__init__(text)
                self._menu_item = menu_item
                self._context_menu = context_menu
                self.setStyleSheet("""
                    QLabel {
                        background-color: transparent;
                        padding: 8px 16px;
                        border-radius: 4px;
                        margin: 1px;
                        color: #f0f0f0;
                        font-size: 13px;
                        min-height: 24px;
                        border: none;
                    }
                """)

                self._normal_style = self.styleSheet()
                self._hover_style = """
                    QLabel {
                        background-color: #454545;
                        padding: 8px 16px;
                        border-radius: 4px;
                        margin: 1px;
                        color: #ffffff;
                        font-size: 13px;
                        min-height: 24px;
                        border: none;
                    }
                """

            def mousePressEvent(self, event):
                if event.button() == Qt.LeftButton:
                    self._context_menu._execute_action(self._menu_item)
                    if hasattr(self._context_menu, "menu") and self._context_menu.menu:
                        self._context_menu.menu.close()

            def enterEvent(self, event):
                self.setStyleSheet(self._hover_style)
                self._context_menu.hovered_widgets.add(self)

            def leaveEvent(self, event):
                self.setStyleSheet(self._normal_style)
                if self in self._context_menu.hovered_widgets:
                    self._context_menu.hovered_widgets.remove(self)

        widget = ClickableLabel(item.label, item, self)
        if not item.enabled:
            widget.setEnabled(False)

        action = QWidgetAction(menu)
        action.setDefaultWidget(widget)
        action._menu_item = item
        return action

    def _execute_action(self, item: MenuItem) -> None:
        """Execute menu item action."""
        if self.execution_callback:
            self.execution_callback(item, self.shift_pressed)

    def eventFilter(self, obj, event):
        """Filter events to detect shift key state and mouse clicks."""
        if not self.event_filter_installed:
            return False

        if isinstance(obj, QMenu):
            if event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Shift:
                    self.shift_pressed = True
            elif event.type() == QEvent.KeyRelease:
                if event.key() == Qt.Key_Shift:
                    self.shift_pressed = False
            elif event.type() == QEvent.MouseButtonPress:
                current_shift = bool(
                    QApplication.keyboardModifiers() & Qt.ShiftModifier
                )
                if current_shift != self.shift_pressed:
                    self.shift_pressed = current_shift
                action = obj.actionAt(event.pos())
                if action and action.isEnabled():
                    item = getattr(action, "_menu_item", None)

                    if (
                        self.shift_pressed
                        and item
                        and (
                            item.item_type == MenuItemType.PROMPT
                            or item.item_type == MenuItemType.PRESET
                        )
                    ):
                        self._handle_shift_right_click(action)
                        return True
            elif event.type() == QEvent.Show:
                self.shift_pressed = bool(
                    QApplication.keyboardModifiers() & Qt.ShiftModifier
                )
            elif event.type() == QEvent.Leave:
                self._clear_all_hover_states()
            elif event.type() == QEvent.MouseMove:
                if not obj.rect().contains(event.pos()):
                    self._clear_all_hover_states()
        return False

    def _handle_shift_right_click(self, action):
        """Handle shift + right click for alternative actions."""
        menu_item = getattr(action, "_menu_item", None)
        if menu_item:
            self._execute_alternative_action(menu_item)

    def _execute_alternative_action(self, item: MenuItem):
        """Execute alternative action for menu item."""

        def execute_and_emit():
            try:
                if hasattr(item, "alternative_action") and item.alternative_action:
                    return item.alternative_action()
                else:
                    return item.action() if item.action else None
            except Exception as e:
                return f"Error: {str(e)}"

        execute_and_emit()
        if self.execution_callback:
            self.execution_callback(item, True)

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
            except (RuntimeError, AttributeError):
                widgets_to_remove.append(widget)

        for widget in widgets_to_remove:
            self.hovered_widgets.discard(widget)

    def _store_external_window_async(self):
        """Store external window information asynchronously."""
        pass

    def _store_active_window(self):
        """Store information about the currently active window."""
        pass

    def _restore_focus(self):
        """Restore focus to the previously active window."""
        self._restore_qt_focus()

    @property
    def menu(self):
        """Compatibility property for existing code."""
        return self.popup_menu
