"""PyQt5-based context menu system for the prompt store application."""

from typing import List, Optional, Tuple, Dict, Any
from PyQt5.QtWidgets import QMenu, QAction, QApplication
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QCursor
from core.models import MenuItem, MenuItemType


class PyQtContextMenu:
    """PyQt5-based context menu implementation."""

    def __init__(self, parent=None):
        self.parent = parent
        self.menu: Optional[QMenu] = None
        self.menu_position_offset = (0, 0)

    def create_menu(self, items: List[MenuItem]) -> QMenu:
        """Create a QMenu from menu items."""
        menu = QMenu(self.parent)
        menu.setWindowFlags(
            Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        )
        menu.setAttribute(Qt.WA_TranslucentBackground, False)

        # Set menu style
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 4px;
                color: white;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
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
        """)

        self._add_menu_items(menu, items)
        return menu

    def create_submenu(
        self, parent_menu: QMenu, title: str, items: List[MenuItem]
    ) -> QMenu:
        """Create a submenu."""
        submenu = parent_menu.addMenu(title)
        submenu.setStyleSheet(parent_menu.styleSheet())
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

    def _add_menu_items(self, menu: QMenu, items: List[MenuItem]) -> None:
        """Add menu items to a QMenu."""
        for item in items:
            if not item.enabled and not self._should_show_disabled_item(item):
                continue

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

        if hasattr(item, "tooltip") and item.tooltip:
            action.setToolTip(item.tooltip)

        if item.action is not None:
            action.triggered.connect(lambda checked, i=item: self._execute_action(i))

        return action

    def _execute_action(self, item: MenuItem) -> None:
        """Execute a menu item action."""
        try:
            if item.action is not None:
                item.action()
        except Exception as e:
            print(f"Error executing menu action: {e}")

    def _should_show_disabled_item(self, item: MenuItem) -> bool:
        """Determine if a disabled item should still be shown."""
        # Show disabled history and speech items so users can see what's available
        return (
            item.item_type == MenuItemType.HISTORY
            or item.item_type == MenuItemType.SPEECH
        )


class PyQtMenuBuilder:
    """Builder for creating structured menus."""

    def __init__(self):
        self.items: List[MenuItem] = []

    def add_items(self, items: List[MenuItem]) -> "PyQtMenuBuilder":
        """Add multiple items to the menu."""
        self.items.extend(items)
        return self

    def add_separator(self) -> "PyQtMenuBuilder":
        """Add a separator to the menu."""
        if self.items and not getattr(self.items[-1], "separator_after", False):
            self.items[-1].separator_after = True
        return self

    def add_items_with_separator(self, items: List[MenuItem]) -> "PyQtMenuBuilder":
        """Add items with a separator before them."""
        if self.items:
            self.add_separator()
        return self.add_items(items)

    def build(self) -> List[MenuItem]:
        """Build and return the menu items."""
        return self.items

    def clear(self) -> "PyQtMenuBuilder":
        """Clear all items."""
        self.items.clear()
        return self

    def filter_enabled(self) -> "PyQtMenuBuilder":
        """Filter to only enabled items."""
        self.items = [item for item in self.items if item.enabled]
        return self

    def sort_by_label(self) -> "PyQtMenuBuilder":
        """Sort items by label."""
        self.items.sort(key=lambda x: x.label.lower())
        return self

    def group_by_type(self) -> "PyQtMenuBuilder":
        """Group items by type with separators."""
        if not self.items:
            return self

        # Group items by type
        grouped: Dict[MenuItemType, List[MenuItem]] = {}
        for item in self.items:
            item_type = item.item_type
            if item_type not in grouped:
                grouped[item_type] = []
            grouped[item_type].append(item)

        # Rebuild items with separators between groups
        new_items: List[MenuItem] = []
        type_order = [
            MenuItemType.PROMPT,
            MenuItemType.PRESET,
            MenuItemType.HISTORY,
            MenuItemType.SPEECH,
            MenuItemType.SYSTEM,
        ]

        for i, item_type in enumerate(type_order):
            if item_type in grouped:
                if (
                    i > 0 and new_items
                ):  # Add separator before each group (except first)
                    new_items[-1].separator_after = True
                new_items.extend(grouped[item_type])

        self.items = new_items
        return self


class PyQtMenuPosition:
    """Utility class for menu positioning."""

    @staticmethod
    def get_cursor_position() -> Tuple[int, int]:
        """Get current cursor position using PyQt5."""
        cursor_pos = QCursor.pos()
        return (cursor_pos.x(), cursor_pos.y())

    @staticmethod
    def get_screen_bounds_at_position(
        position: Tuple[int, int],
    ) -> Tuple[int, int, int, int]:
        """Get screen bounds at the given position."""
        x, y = position
        screen = QApplication.desktop().screenAt(QPoint(x, y))
        if screen == -1:
            screen = QApplication.desktop().primaryScreen()

        geometry = QApplication.desktop().screenGeometry(screen)
        return (geometry.left(), geometry.top(), geometry.right(), geometry.bottom())

    @staticmethod
    def apply_offset(
        position: Tuple[int, int], offset: Tuple[int, int]
    ) -> Tuple[int, int]:
        """Apply offset to position."""
        x, y = position
        offset_x, offset_y = offset
        return (x + offset_x, y + offset_y)
