"""Menu order settings panel."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from modules.gui.shared.context_widgets import IconButton
from modules.gui.shared.theme import (
    COLOR_BORDER,
    COLOR_BUTTON_BG,
    COLOR_BUTTON_HOVER,
    COLOR_DIALOG_BG,
    COLOR_SELECTION,
    COLOR_TEXT,
    COLOR_TEXT_EDIT_BG,
    TOOLTIP_STYLE,
)
from modules.utils.config import ConfigService, DEFAULT_MENU_SECTION_ORDER

from ..settings_panel_base import SettingsPanelBase

SECTION_LABELS = {
    "LastInteractionMenuProvider": "Last Interaction",
    "ContextMenuProvider": "Context",
    "SpeechMenuProvider": "Speech to Text",
    "prompts": "Prompts",
    "settings": "Settings",
}

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


class MenuOrderListWidget(QWidget):
    """Widget for reordering menu sections."""

    order_changed = Signal(list)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._sections: list[str] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

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
        layout.addWidget(self._list_widget, 1)

    def set_sections(self, sections: list[str]):
        self._sections = list(sections)
        self._rebuild_list()

    def _rebuild_list(self):
        self._list_widget.clear()

        for section_id in self._sections:
            label = SECTION_LABELS.get(section_id, section_id)
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, section_id)
            self._list_widget.addItem(item)

        self._update_button_states()

    def _on_selection_changed(self):
        self._update_button_states()

    def _update_button_states(self):
        has_selection = self._list_widget.currentItem() is not None
        current_row = self._list_widget.currentRow()
        count = self._list_widget.count()

        self._up_btn.setEnabled(has_selection and current_row > 0)
        self._down_btn.setEnabled(has_selection and current_row < count - 1)

    def _on_move_up(self):
        current_row = self._list_widget.currentRow()
        if current_row > 0:
            self._sections[current_row], self._sections[current_row - 1] = (
                self._sections[current_row - 1],
                self._sections[current_row],
            )
            self._rebuild_list()
            self._list_widget.setCurrentRow(current_row - 1)
            self.order_changed.emit(list(self._sections))

    def _on_move_down(self):
        current_row = self._list_widget.currentRow()
        if current_row < len(self._sections) - 1:
            self._sections[current_row], self._sections[current_row + 1] = (
                self._sections[current_row + 1],
                self._sections[current_row],
            )
            self._rebuild_list()
            self._list_widget.setCurrentRow(current_row + 1)
            self.order_changed.emit(list(self._sections))

    def get_sections(self) -> list[str]:
        return list(self._sections)


class MenuOrderPanel(SettingsPanelBase):
    """Panel for configuring context menu section order."""

    @property
    def panel_title(self) -> str:
        return "Menu Order"

    def _setup_content(self, layout: QVBoxLayout) -> None:
        self._config_service = ConfigService()

        description = QLabel(
            "Configure the order of sections in the context menu. "
            "Use the up/down buttons to reorder."
        )
        description.setStyleSheet("color: #888888; margin-bottom: 16px;")
        description.setWordWrap(True)
        layout.addWidget(description)

        self._list_widget = MenuOrderListWidget()
        self._list_widget.order_changed.connect(self._on_order_changed)

        self._load_sections()

        layout.addWidget(self._list_widget, 1)

    def _load_sections(self):
        sections = self._config_service.get_menu_section_order()
        known_sections = set(DEFAULT_MENU_SECTION_ORDER)
        valid_sections = [s for s in sections if s in known_sections]

        for default_section in DEFAULT_MENU_SECTION_ORDER:
            if default_section not in valid_sections:
                valid_sections.append(default_section)

        self._list_widget.set_sections(valid_sections)

    def _on_order_changed(self, new_order: list[str]):
        self.mark_dirty()

    def save_changes(self) -> bool:
        sections = self._list_widget.get_sections()
        self._config_service.update_menu_section_order(sections, persist=False)
        self.mark_clean()
        return True

    def load_settings(self) -> None:
        self._load_sections()
        self.mark_clean()
