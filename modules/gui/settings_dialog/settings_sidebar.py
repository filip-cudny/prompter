"""Settings sidebar with category navigation."""

from typing import List, Optional, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem

from modules.gui.dialog_styles import (
    COLOR_DIALOG_BG,
    COLOR_TEXT,
    COLOR_SELECTION,
    COLOR_BORDER,
)


SIDEBAR_WIDTH = 180


class SettingsSidebar(QWidget):
    """Sidebar widget for settings category navigation."""

    category_selected = pyqtSignal(int)

    def __init__(
        self,
        categories: List[Tuple[str, str]],
        parent: Optional[QWidget] = None,
    ):
        """Initialize the sidebar.

        Args:
            categories: List of (id, display_name) tuples for each category
            parent: Parent widget
        """
        super().__init__(parent)
        self._categories = categories
        self._setup_ui()

    def _setup_ui(self):
        """Set up the sidebar UI."""
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLOR_DIALOG_BG};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._list_widget = QListWidget()
        self._list_widget.setFocusPolicy(Qt.NoFocus)
        self._list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: transparent;
                border: none;
                border-right: 1px solid {COLOR_BORDER};
                outline: none;
                padding: 8px 0;
            }}
            QListWidget::item {{
                color: {COLOR_TEXT};
                padding: 10px 16px;
                margin: 2px 8px;
                border-radius: 6px;
            }}
            QListWidget::item:hover {{
                background-color: #3a3a3a;
            }}
            QListWidget::item:selected {{
                background-color: {COLOR_SELECTION};
                color: {COLOR_TEXT};
            }}
        """)

        for category_id, display_name in self._categories:
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, category_id)
            self._list_widget.addItem(item)

        self._list_widget.currentRowChanged.connect(self._on_selection_changed)

        if self._categories:
            self._list_widget.setCurrentRow(0)

        layout.addWidget(self._list_widget)

    def _on_selection_changed(self, row: int):
        """Handle category selection change."""
        if row >= 0:
            self.category_selected.emit(row)

    def select_category(self, index: int):
        """Select a category by index."""
        if 0 <= index < self._list_widget.count():
            self._list_widget.setCurrentRow(index)

    def current_category_id(self) -> Optional[str]:
        """Get the currently selected category ID."""
        current_item = self._list_widget.currentItem()
        if current_item:
            return current_item.data(Qt.UserRole)
        return None
