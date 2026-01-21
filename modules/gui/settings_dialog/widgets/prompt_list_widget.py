"""Widget for displaying and managing a list of prompts."""

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from modules.gui.shared.context_widgets import IconButton
from modules.gui.shared.dialog_styles import (
    COLOR_BORDER,
    COLOR_BUTTON_BG,
    COLOR_BUTTON_HOVER,
    COLOR_DIALOG_BG,
    COLOR_SELECTION,
    COLOR_TEXT,
    COLOR_TEXT_EDIT_BG,
    TOOLTIP_STYLE,
)

TOOLBAR_BTN_STYLE = (
    f"""
    QPushButton {{
        background-color: {COLOR_BUTTON_BG};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 6px 12px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_BUTTON_HOVER};
    }}
    QPushButton:disabled {{
        background-color: {COLOR_DIALOG_BG};
        color: #666666;
    }}
"""
    + TOOLTIP_STYLE
)


ICON_BTN_STYLE = (
    f"""
    QPushButton {{
        background-color: {COLOR_BUTTON_BG};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 4px;
        min-width: 28px;
        max-width: 28px;
        min-height: 28px;
        max-height: 28px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_BUTTON_HOVER};
    }}
    QPushButton:disabled {{
        background-color: {COLOR_DIALOG_BG};
    }}
"""
    + TOOLTIP_STYLE
)


class PromptListWidget(QWidget):
    """Widget for managing a list of prompts with reorder capability."""

    prompt_selected = Signal(dict)
    prompt_add_requested = Signal()
    prompt_edit_requested = Signal(dict)
    prompt_delete_requested = Signal(str)
    order_changed = Signal(list)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._prompts: list[dict[str, Any]] = []
        self._setup_ui()

    def _setup_ui(self):
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._add_btn = QPushButton("Add")
        self._add_btn.setStyleSheet(TOOLBAR_BTN_STYLE)
        self._add_btn.setToolTip("Add new prompt")
        self._add_btn.clicked.connect(lambda: self.prompt_add_requested.emit())
        toolbar.addWidget(self._add_btn)

        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setStyleSheet(TOOLBAR_BTN_STYLE)
        self._edit_btn.setToolTip("Edit selected prompt")
        self._edit_btn.setEnabled(False)
        self._edit_btn.clicked.connect(self._on_edit_clicked)
        toolbar.addWidget(self._edit_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setStyleSheet(TOOLBAR_BTN_STYLE)
        self._delete_btn.setToolTip("Delete selected prompt")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        toolbar.addWidget(self._delete_btn)

        toolbar.addStretch()

        self._up_btn = IconButton("chevron-up", size=16)
        self._up_btn.setStyleSheet(ICON_BTN_STYLE)
        self._up_btn.setToolTip("Move up")
        self._up_btn.setEnabled(False)
        self._up_btn.clicked.connect(self._on_move_up)
        toolbar.addWidget(self._up_btn)

        self._down_btn = IconButton("chevron-down", size=16)
        self._down_btn.setStyleSheet(ICON_BTN_STYLE)
        self._down_btn.setToolTip("Move down")
        self._down_btn.setEnabled(False)
        self._down_btn.clicked.connect(self._on_move_down)
        toolbar.addWidget(self._down_btn)

        layout.addLayout(toolbar)

        self._list_widget = QListWidget()
        self._list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {COLOR_TEXT_EDIT_BG};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 10px;
                border-bottom: 1px solid {COLOR_BORDER};
            }}
            QListWidget::item:last-child {{
                border-bottom: none;
            }}
            QListWidget::item:selected {{
                background-color: {COLOR_SELECTION};
            }}
            QListWidget::item:hover {{
                background-color: #3a3a3a;
            }}
        """)
        self._list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self._list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._list_widget, 1)

    def set_prompts(self, prompts: list[dict[str, Any]]):
        """Set the list of prompts.

        Args:
            prompts: List of prompt data dicts
        """
        self._prompts = list(prompts)
        self._rebuild_list()

    def _rebuild_list(self):
        """Rebuild the list widget from prompts data."""
        self._list_widget.clear()

        for index, prompt in enumerate(self._prompts, start=1):
            name = prompt.get("name", "Unnamed")
            item = QListWidgetItem(f"{index}. {name}")
            item.setData(Qt.UserRole, prompt.get("id"))
            self._list_widget.addItem(item)

        self._update_button_states()

    def _on_selection_changed(self):
        """Handle selection change."""
        self._update_button_states()

        current = self._list_widget.currentItem()
        if current:
            prompt_id = current.data(Qt.UserRole)
            for prompt in self._prompts:
                if prompt.get("id") == prompt_id:
                    self.prompt_selected.emit(prompt)
                    break

    def _update_button_states(self):
        """Update enabled state of buttons based on selection."""
        has_selection = self._list_widget.currentItem() is not None
        current_row = self._list_widget.currentRow()
        count = self._list_widget.count()

        self._edit_btn.setEnabled(has_selection)
        self._delete_btn.setEnabled(has_selection)
        self._up_btn.setEnabled(has_selection and current_row > 0)
        self._down_btn.setEnabled(has_selection and current_row < count - 1)

    def _on_edit_clicked(self):
        """Handle edit button click."""
        current = self._list_widget.currentItem()
        if current:
            prompt_id = current.data(Qt.UserRole)
            for prompt in self._prompts:
                if prompt.get("id") == prompt_id:
                    self.prompt_edit_requested.emit(prompt)
                    break

    def _on_delete_clicked(self):
        """Handle delete button click."""
        current = self._list_widget.currentItem()
        if current:
            prompt_id = current.data(Qt.UserRole)
            self.prompt_delete_requested.emit(prompt_id)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Handle item double-click to edit."""
        prompt_id = item.data(Qt.UserRole)
        for prompt in self._prompts:
            if prompt.get("id") == prompt_id:
                self.prompt_edit_requested.emit(prompt)
                break

    def _on_move_up(self):
        """Move selected item up."""
        current_row = self._list_widget.currentRow()
        if current_row > 0:
            self._prompts[current_row], self._prompts[current_row - 1] = (
                self._prompts[current_row - 1],
                self._prompts[current_row],
            )
            self._rebuild_list()
            self._list_widget.setCurrentRow(current_row - 1)
            self._emit_order_changed()

    def _on_move_down(self):
        """Move selected item down."""
        current_row = self._list_widget.currentRow()
        if current_row < len(self._prompts) - 1:
            self._prompts[current_row], self._prompts[current_row + 1] = (
                self._prompts[current_row + 1],
                self._prompts[current_row],
            )
            self._rebuild_list()
            self._list_widget.setCurrentRow(current_row + 1)
            self._emit_order_changed()

    def _emit_order_changed(self):
        """Emit the new prompt order."""
        order = [p.get("id") for p in self._prompts]
        self.order_changed.emit(order)

    def get_prompt_ids(self) -> list[str]:
        """Get the current order of prompt IDs."""
        return [p.get("id") for p in self._prompts]
