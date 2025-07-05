"""PyQt5-based context menu system for the prompt store application."""

from typing import List, Optional, Tuple
from PyQt5.QtWidgets import QMenu, QAction, QApplication
from PyQt5.QtCore import Qt, QPoint, QTimer, QObject, QEvent
from PyQt5.QtGui import QCursor
from core.models import MenuItem, MenuItemType


class PyQtContextMenu(QObject):
    """PyQt5-based context menu implementation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.menu: Optional[QMenu] = None
        self.menu_position_offset = (0, 0)
        self.shift_pressed = False
        self.event_filter_installed = False
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
            }
            QMenu::item:selected {
                background-color: #0066cc;
            }
            QMenu::item:disabled {
                color: #888888;
            }
            QMenu::separator {
                height: 1px;
                background-color: #555555;
                margin: 4px 8px;
            }
        """

    def create_menu(self, items: List[MenuItem]) -> QMenu:
        """Create a QMenu from menu items."""
        menu = QMenu(self.parent)
        menu.setWindowFlags(
            Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        )
        menu.setAttribute(Qt.WA_TranslucentBackground, False)
        menu.setStyleSheet(self._menu_stylesheet)

        # Reset shift state and install event filter
        self.shift_pressed = False
        self.event_filter_installed = True
        menu.installEventFilter(self)

        self._add_menu_items(menu, items)
        return menu

    def create_submenu(
        self, parent_menu: QMenu, title: str, items: List[MenuItem]
    ) -> QMenu:
        """Create a submenu."""
        submenu = parent_menu.addMenu(title)

        submenu.setWindowFlags(
            Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        )
        submenu.setAttribute(Qt.WA_TranslucentBackground, True)
        submenu.setStyleSheet(self._menu_stylesheet)

        # Install event filter on submenu too
        submenu.installEventFilter(self)

        self._add_menu_items(submenu, items)
        return submenu

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

        # Apply position offset
        x, y = position
        offset_x, offset_y = self.menu_position_offset
        adjusted_pos = QPoint(x + offset_x, y + offset_y)

        # Check current shift state before showing menu
        self.shift_pressed = bool(QApplication.keyboardModifiers() & Qt.ShiftModifier)

        self.menu = self.create_menu(items)
        self.menu.exec_(adjusted_pos)

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
        if self.menu:
            self.menu.close()
            self.menu = None
        self.shift_pressed = False
        self.event_filter_installed = False

    def _add_menu_items(self, menu: QMenu, items: List[MenuItem]) -> None:
        """Add menu items to a QMenu."""
        for item in items:
            # Check if item has submenu
            if hasattr(item, "submenu_items") and item.submenu_items:
                self.create_submenu(menu, item.label, item.submenu_items)
            else:
                action = self._create_action(menu, item)
                menu.addAction(action)

            if hasattr(item, "separator_after") and item.separator_after:
                menu.addSeparator()

    def _create_action(self, menu: QMenu, item: MenuItem) -> QAction:
        """Create a QAction from a MenuItem."""
        action = QAction(item.label, menu)
        action.setEnabled(item.enabled)

        # Store reference to MenuItem for shift+right click handling
        action._menu_item = item

        if hasattr(item, "tooltip") and item.tooltip:
            action.setToolTip(item.tooltip)

        if item.action is not None:
            action.triggered.connect(lambda checked, i=item: self._execute_action(i))

        return action

    def _execute_action(self, item: MenuItem) -> None:
        """Execute a menu item action asynchronously to prevent menu blocking."""
        try:
            if item.action is not None:
                # Execute action asynchronously to prevent blocking the menu
                QTimer.singleShot(0, item.action)
        except Exception as e:
            print(f"Error executing menu action: {e}")

    def eventFilter(self, obj, event):
        """Filter events to detect shift key state and mouse clicks."""
        if not self.event_filter_installed:
            return False

        if isinstance(obj, QMenu):
            # Handle key events for shift tracking
            if event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Shift:
                    self.shift_pressed = True
            elif event.type() == QEvent.KeyRelease:
                if event.key() == Qt.Key_Shift:
                    self.shift_pressed = False
            # Handle mouse events
            elif event.type() == QEvent.MouseButtonPress:
                # Double-check shift state with current keyboard modifiers
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
                        return True  # Consume the event
            # Handle show event to check shift state
            elif event.type() == QEvent.Show:
                # Check actual keyboard state when menu shows
                self.shift_pressed = bool(
                    QApplication.keyboardModifiers() & Qt.ShiftModifier
                )
        return False

    def _handle_shift_right_click(self, action: QAction):
        """Handle shift+click on menu items."""
        # Get the MenuItem associated with this action
        item = getattr(action, "_menu_item", None)
        if item and (
            item.item_type == MenuItemType.PROMPT
            or item.item_type == MenuItemType.PRESET
        ):
            # Close the menu after handling
            self._execute_alternative_action(item)
            if self.menu:
                self.menu.close()

    def _execute_alternative_action(self, item: MenuItem) -> None:
        """Execute menu item with alternative flag."""
        try:
            if item.data is None:
                item.data = {}
            item.data["alternative_execution"] = True

            if item.action is not None:
                QTimer.singleShot(0, item.action)
        except Exception as e:
            print(f"Error executing alternative menu action: {e}")
