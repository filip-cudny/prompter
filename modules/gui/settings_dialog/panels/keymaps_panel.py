"""Keymaps settings panel."""

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.gui.shared.dialog_styles import (
    COLOR_BORDER,
    COLOR_BUTTON_BG,
    COLOR_BUTTON_HOVER,
    COLOR_DIALOG_BG,
    COLOR_SELECTION,
    COLOR_TEXT,
    COLOR_TEXT_EDIT_BG,
    SVG_CHEVRON_DOWN_PATH,
    TOOLTIP_STYLE,
)
from modules.utils.config import ConfigService
from ..settings_panel_base import SettingsPanelBase


AVAILABLE_ACTIONS = [
    ("open_context_menu", "Open Context Menu"),
    ("execute_active_prompt", "Execute Active Prompt"),
    ("set_context_value", "Set Context Value"),
    ("append_context_value", "Append Context Value"),
    ("clear_context", "Clear Context"),
    ("speech_to_text_toggle", "Speech to Text Toggle"),
]


TAB_STYLE = f"""
    QTabWidget::pane {{
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        background-color: {COLOR_TEXT_EDIT_BG};
    }}
    QTabBar::tab {{
        background-color: {COLOR_BUTTON_BG};
        color: {COLOR_TEXT};
        padding: 8px 16px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }}
    QTabBar::tab:selected {{
        background-color: {COLOR_TEXT_EDIT_BG};
    }}
    QTabBar::tab:hover {{
        background-color: {COLOR_BUTTON_HOVER};
    }}
"""

TABLE_STYLE = f"""
    QTableWidget {{
        background-color: {COLOR_TEXT_EDIT_BG};
        color: {COLOR_TEXT};
        border: none;
        gridline-color: {COLOR_BORDER};
    }}
    QTableWidget::item {{
        padding: 8px;
    }}
    QTableWidget::item:selected {{
        background-color: {COLOR_SELECTION};
    }}
    QHeaderView::section {{
        background-color: {COLOR_DIALOG_BG};
        color: {COLOR_TEXT};
        padding: 8px;
        border: none;
        border-bottom: 1px solid {COLOR_BORDER};
    }}
"""

TOOLBAR_BTN_STYLE = f"""
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
""" + TOOLTIP_STYLE


class KeymapsPanel(SettingsPanelBase):
    """Panel for keyboard shortcut settings."""

    @property
    def panel_title(self) -> str:
        return "Keymaps"

    def _setup_content(self, layout: QVBoxLayout) -> None:
        """Set up the keymaps panel content."""
        self._config_service = ConfigService()
        self._os_tabs: Dict[str, QTableWidget] = {}

        description = QLabel(
            "Configure keyboard shortcuts for each operating system.\n"
            "Format: modifier+key (e.g., cmd+f1, ctrl+shift+a)"
        )
        description.setStyleSheet("color: #888888; margin-bottom: 16px;")
        description.setWordWrap(True)
        layout.addWidget(description)

        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet(TAB_STYLE)

        for os_name, os_context in [("macOS", "macos"), ("Linux", "linux"), ("Windows", "windows")]:
            tab = self._create_os_tab(os_context)
            self._tab_widget.addTab(tab, os_name)
            self._os_tabs[os_context] = tab.findChild(QTableWidget)

        layout.addWidget(self._tab_widget)

        self._load_keymaps()

    def _create_os_tab(self, os_context: str) -> QWidget:
        """Create a tab for a specific OS."""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(8, 8, 8, 8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        add_btn = QPushButton("Add Binding")
        add_btn.setStyleSheet(TOOLBAR_BTN_STYLE)
        add_btn.clicked.connect(lambda: self._add_binding(os_context))
        toolbar.addWidget(add_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet(TOOLBAR_BTN_STYLE)
        delete_btn.clicked.connect(lambda: self._delete_binding(os_context))
        toolbar.addWidget(delete_btn)

        toolbar.addStretch()
        tab_layout.addLayout(toolbar)

        table = QTableWidget()
        table.setStyleSheet(TABLE_STYLE)
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Shortcut", "Action"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.setColumnWidth(0, 200)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.verticalHeader().setDefaultSectionSize(36)

        tab_layout.addWidget(table)

        return tab

    def _load_keymaps(self):
        """Load keymaps from config."""
        settings_data = self._config_service.get_settings_data()
        keymaps = settings_data.get("keymaps", [])

        os_bindings = {"macos": {}, "linux": {}, "windows": {}}

        for keymap in keymaps:
            context = keymap.get("context", "")
            bindings = keymap.get("bindings", {})

            for os_name in os_bindings.keys():
                if f"os == {os_name}" in context:
                    os_bindings[os_name] = bindings
                    break

        for os_context, bindings in os_bindings.items():
            if os_context in self._os_tabs:
                table = self._os_tabs[os_context]
                table.setRowCount(0)

                for shortcut, action in bindings.items():
                    row = table.rowCount()
                    table.insertRow(row)

                    shortcut_item = QTableWidgetItem(shortcut)
                    table.setItem(row, 0, shortcut_item)

                    action_combo = QComboBox()
                    action_combo.setStyleSheet(f"""
                        QComboBox {{
                            background-color: {COLOR_TEXT_EDIT_BG};
                            color: {COLOR_TEXT};
                            border: none;
                            padding: 4px;
                        }}
                        QComboBox::drop-down {{
                            border: none;
                            width: 20px;
                        }}
                        QComboBox::down-arrow {{
                            image: url("{SVG_CHEVRON_DOWN_PATH}");
                            width: 12px;
                            height: 12px;
                        }}
                        QComboBox QAbstractItemView {{
                            background-color: {COLOR_DIALOG_BG};
                            color: {COLOR_TEXT};
                            border: 1px solid {COLOR_BORDER};
                        }}
                    """)
                    for action_key, action_label in AVAILABLE_ACTIONS:
                        action_combo.addItem(action_label, action_key)

                    for i in range(action_combo.count()):
                        if action_combo.itemData(i) == action:
                            action_combo.setCurrentIndex(i)
                            break

                    table.setCellWidget(row, 1, action_combo)

    def _add_binding(self, os_context: str):
        """Add a new binding row."""
        if os_context not in self._os_tabs:
            return

        table = self._os_tabs[os_context]
        row = table.rowCount()
        table.insertRow(row)

        shortcut_item = QTableWidgetItem("")
        table.setItem(row, 0, shortcut_item)

        action_combo = QComboBox()
        action_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLOR_TEXT_EDIT_BG};
                color: {COLOR_TEXT};
                border: none;
                padding: 4px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: url("{SVG_CHEVRON_DOWN_PATH}");
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLOR_DIALOG_BG};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
            }}
        """)
        for action_key, action_label in AVAILABLE_ACTIONS:
            action_combo.addItem(action_label, action_key)

        table.setCellWidget(row, 1, action_combo)
        table.selectRow(row)
        table.editItem(shortcut_item)
        self.mark_dirty()

    def _delete_binding(self, os_context: str):
        """Delete the selected binding."""
        if os_context not in self._os_tabs:
            return

        table = self._os_tabs[os_context]
        current_row = table.currentRow()
        if current_row >= 0:
            table.removeRow(current_row)
            self.mark_dirty()

    def _collect_keymaps(self) -> list:
        """Collect keymaps from all OS tabs."""
        keymaps = []

        for os_context, table in self._os_tabs.items():
            bindings = {}

            for row in range(table.rowCount()):
                shortcut_item = table.item(row, 0)
                action_combo = table.cellWidget(row, 1)

                if shortcut_item and action_combo:
                    shortcut = shortcut_item.text().strip()
                    action = action_combo.currentData()

                    if shortcut and action:
                        bindings[shortcut] = action

            if bindings:
                keymaps.append({
                    "context": f"os == {os_context}",
                    "bindings": bindings,
                })

        return keymaps

    def save_changes(self) -> bool:
        """Save pending changes to config."""
        keymaps = self._collect_keymaps()
        self._config_service.update_keymaps(keymaps, persist=False)
        self.mark_clean()
        return True

    def load_settings(self) -> None:
        """Reload settings from config."""
        self._load_keymaps()
        self.mark_clean()
