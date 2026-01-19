"""Conversation tab bar widget for PromptExecuteDialog."""

from typing import Dict, List, Optional

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal, QSize

from modules.gui.icons import create_icon


class ConversationTabBar(QWidget):
    """Custom tab bar for conversation tabs."""

    tab_selected = pyqtSignal(str)  # Emits tab_id
    tab_close_requested = pyqtSignal(str)  # Emits tab_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tabs: Dict[str, QWidget] = {}  # tab_id -> tab button widget
        self._tab_order: List[str] = []  # Ordered list of tab IDs
        self._active_tab_id: Optional[str] = None

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._layout.addStretch()

    def add_tab(self, tab_id: str, name: str):
        """Add a new tab to the bar."""
        if tab_id in self._tabs:
            return

        tab_widget = self._create_tab_widget(tab_id, name)
        self._tabs[tab_id] = tab_widget
        self._tab_order.append(tab_id)

        # Insert before the stretch
        self._layout.insertWidget(self._layout.count() - 1, tab_widget)

    def remove_tab(self, tab_id: str):
        """Remove a tab from the bar."""
        if tab_id not in self._tabs:
            return

        tab_widget = self._tabs.pop(tab_id)
        self._tab_order.remove(tab_id)
        tab_widget.setParent(None)
        tab_widget.deleteLater()

    def set_active_tab(self, tab_id: str):
        """Set the active tab visually."""
        if tab_id not in self._tabs:
            return

        self._active_tab_id = tab_id

        for tid, widget in self._tabs.items():
            is_active = tid == tab_id
            widget.setProperty("active", is_active)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            if hasattr(widget, "label"):
                font = widget.label.font()
                font.setWeight(63 if is_active else 50)  # DemiBold : Normal
                widget.label.setFont(font)

    def get_tab_count(self) -> int:
        """Get the number of tabs."""
        return len(self._tabs)

    def get_tab_ids(self) -> List[str]:
        """Get ordered list of tab IDs."""
        return list(self._tab_order)

    def _create_tab_widget(self, tab_id: str, name: str) -> QWidget:
        """Create a tab button widget."""
        tab = QWidget()
        tab.setProperty("active", False)
        tab.setStyleSheet("""
            QWidget {
                background: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                padding: 4px 8px 2px 8px;
            }
            QWidget:hover {
                background: rgba(255, 255, 255, 0.05);
            }
            QWidget[active="true"] {
                border-bottom: 2px solid #888888;
            }
        """)

        layout = QHBoxLayout(tab)
        layout.setContentsMargins(6, 4, 4, 4)
        layout.setSpacing(6)

        # Tab label
        label = QLabel(name)
        label.setStyleSheet("border: none; background: transparent; color: #cccccc;")
        label.setCursor(Qt.PointingHandCursor)
        layout.addWidget(label)

        # Close button
        close_btn = QPushButton()
        close_btn.setIcon(create_icon("delete", "#888888", 14))
        close_btn.setIconSize(QSize(14, 14))
        close_btn.setFixedSize(18, 18)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 9px;
                padding: 0;
                margin: 0;
            }
            QPushButton:hover {
                background: #555555;
            }
        """)
        close_btn.clicked.connect(lambda: self.tab_close_requested.emit(tab_id))
        layout.addWidget(close_btn)

        # Store tab_id on the widget for click handling
        tab.tab_id = tab_id
        tab.label = label

        # Make the tab clickable
        tab.mousePressEvent = lambda e, tid=tab_id: self._on_tab_clicked(tid)
        label.mousePressEvent = lambda e, tid=tab_id: self._on_tab_clicked(tid)

        return tab

    def _on_tab_clicked(self, tab_id: str):
        """Handle tab click."""
        self.tab_selected.emit(tab_id)
