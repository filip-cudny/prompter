"""Widget for displaying a list of prompts."""

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.gui.shared.theme import (
    COLOR_BORDER,
    COLOR_SELECTION,
    COLOR_TEXT,
    COLOR_TEXT_EDIT_BG,
)


class PromptListWidget(QWidget):
    """Widget displaying a list of prompts."""

    prompt_selected = Signal(dict)
    order_changed = Signal(list)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._prompts: list[dict[str, Any]] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

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
        layout.addWidget(self._list_widget, 1)

    def set_prompts(self, prompts: list[dict[str, Any]]):
        self._prompts = list(prompts)
        self._rebuild_list()

    def _rebuild_list(self):
        self._list_widget.blockSignals(True)
        self._list_widget.clear()

        for index, prompt in enumerate(self._prompts, start=1):
            name = prompt.get("name", "Unnamed")
            item = QListWidgetItem(f"{index}. {name}")
            item.setData(Qt.UserRole, prompt.get("id"))
            self._list_widget.addItem(item)
        self._list_widget.blockSignals(False)

    def _on_selection_changed(self):
        current = self._list_widget.currentItem()
        if current:
            prompt_id = current.data(Qt.UserRole)
            for prompt in self._prompts:
                if prompt.get("id") == prompt_id:
                    self.prompt_selected.emit(prompt)
                    break

    def move_up(self):
        current_row = self._list_widget.currentRow()
        if current_row > 0:
            self._prompts[current_row], self._prompts[current_row - 1] = (
                self._prompts[current_row - 1],
                self._prompts[current_row],
            )
            self._rebuild_list()
            self._list_widget.setCurrentRow(current_row - 1)
            self._emit_order_changed()

    def move_down(self):
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
        order = [p.get("id") for p in self._prompts]
        self.order_changed.emit(order)

    def current_item(self) -> QListWidgetItem | None:
        return self._list_widget.currentItem()

    def current_row(self) -> int:
        return self._list_widget.currentRow()

    def count(self) -> int:
        return self._list_widget.count()

    def clear_selection(self):
        self._list_widget.clearSelection()
        self._list_widget.setCurrentRow(-1)

    def select_by_id(self, prompt_id: str):
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            if item.data(Qt.UserRole) == prompt_id:
                self._list_widget.setCurrentItem(item)
                break

    def get_prompt_ids(self) -> list[str]:
        return [p.get("id") for p in self._prompts]
