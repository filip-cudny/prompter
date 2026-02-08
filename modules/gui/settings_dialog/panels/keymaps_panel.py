"""Keymaps settings panel."""

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from modules.gui.shared.theme import (
    COLOR_BORDER,
    COLOR_BUTTON_BG,
    COLOR_BUTTON_HOVER,
    COLOR_DIALOG_BG,
    COLOR_SELECTION,
    COLOR_TEXT,
    COLOR_TEXT_EDIT_BG,
    COLOR_TEXT_HINT,
    SVG_CHEVRON_DOWN_PATH,
    TOOLTIP_STYLE,
)
from modules.utils.config import ConfigService
from modules.utils.system import is_macos

from ..settings_panel_base import SettingsPanelBase

AVAILABLE_ACTIONS = [
    ("open_context_menu", "Open Context Menu"),
    ("execute_active_prompt", "Execute Active Prompt"),
    ("set_context_value", "Set Context Value"),
    ("append_context_value", "Append Context Value"),
    ("clear_context", "Clear Context"),
    ("speech_to_text_toggle", "Speech to Text Toggle"),
]

MODIFIER_CANONICAL_ORDER = ["cmd", "ctrl", "super", "meta", "shift", "alt"]

MODIFIER_KEYS = {
    Qt.Key_Control,
    Qt.Key_Shift,
    Qt.Key_Alt,
    Qt.Key_Meta,
    Qt.Key_Super_L,
    Qt.Key_Super_R,
}

SPECIAL_KEY_MAP = {
    Qt.Key_F1: "f1", Qt.Key_F2: "f2", Qt.Key_F3: "f3", Qt.Key_F4: "f4",
    Qt.Key_F5: "f5", Qt.Key_F6: "f6", Qt.Key_F7: "f7", Qt.Key_F8: "f8",
    Qt.Key_F9: "f9", Qt.Key_F10: "f10", Qt.Key_F11: "f11", Qt.Key_F12: "f12",
    Qt.Key_F13: "f13", Qt.Key_F14: "f14", Qt.Key_F15: "f15", Qt.Key_F16: "f16",
    Qt.Key_F17: "f17", Qt.Key_F18: "f18", Qt.Key_F19: "f19", Qt.Key_F20: "f20",
    Qt.Key_Escape: "esc", Qt.Key_Space: "space", Qt.Key_Tab: "tab",
    Qt.Key_Return: "enter", Qt.Key_Enter: "enter",
    Qt.Key_Backspace: "backspace", Qt.Key_Delete: "delete",
    Qt.Key_Insert: "insert", Qt.Key_Home: "home", Qt.Key_End: "end",
    Qt.Key_PageUp: "pageup", Qt.Key_PageDown: "pagedown",
    Qt.Key_Up: "up", Qt.Key_Down: "down", Qt.Key_Left: "left", Qt.Key_Right: "right",
    Qt.Key_Print: "print", Qt.Key_Pause: "pause",
}


def _qt_key_to_modifier(key: int) -> str | None:
    if key == Qt.Key_Shift:
        return "shift"
    if key == Qt.Key_Alt:
        return "alt"
    if is_macos():
        if key == Qt.Key_Meta:
            return "cmd"
        if key == Qt.Key_Control:
            return "ctrl"
    else:
        if key == Qt.Key_Control:
            return "ctrl"
        if key in (Qt.Key_Meta, Qt.Key_Super_L, Qt.Key_Super_R):
            return "super"
    return None


def _qt_key_to_name(key: int) -> str | None:
    if key in SPECIAL_KEY_MAP:
        return SPECIAL_KEY_MAP[key]
    if Qt.Key_A <= key <= Qt.Key_Z:
        return chr(key).lower()
    if Qt.Key_0 <= key <= Qt.Key_9:
        return chr(key)
    return None


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

RECORDER_IDLE_STYLE = f"""
    QLabel {{
        color: {COLOR_TEXT};
        padding: 0px 8px;
        border: 1px solid transparent;
        border-radius: 3px;
        background-color: transparent;
    }}
"""

RECORDER_IDLE_EMPTY_STYLE = f"""
    QLabel {{
        color: {COLOR_TEXT_HINT};
        padding: 0px 8px;
        border: 1px solid transparent;
        border-radius: 3px;
        background-color: transparent;
    }}
"""

RECORDER_RECORDING_STYLE = f"""
    QLabel {{
        color: {COLOR_TEXT};
        padding: 0px 8px;
        border: 1px solid {COLOR_SELECTION};
        border-radius: 3px;
        background-color: {COLOR_TEXT_EDIT_BG};
    }}
"""


class KeyRecorderWidget(QWidget):
    shortcut_changed = Signal(str)

    def __init__(self, shortcut: str = "", parent=None):
        super().__init__(parent)
        self._recording = False
        self._shortcut = shortcut
        self._previous_shortcut = shortcut
        self._held_modifiers: set[str] = set()

        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel()
        self._label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self._label)

        self._update_display()

    def text(self) -> str:
        return self._shortcut

    def _update_display(self):
        if self._recording:
            self._label.setStyleSheet(RECORDER_RECORDING_STYLE)
            if self._held_modifiers:
                prefix = "+".join(
                    m for m in MODIFIER_CANONICAL_ORDER if m in self._held_modifiers
                )
                self._label.setText(f"{prefix}+")
            else:
                self._label.setText("Press keys...")
        else:
            if self._shortcut:
                self._label.setStyleSheet(RECORDER_IDLE_STYLE)
                self._label.setText(self._shortcut)
            else:
                self._label.setStyleSheet(RECORDER_IDLE_EMPTY_STYLE)
                self._label.setText("Click to record")

    def _start_recording(self):
        if self._recording:
            return
        self._recording = True
        self._previous_shortcut = self._shortcut
        self._held_modifiers.clear()
        self._update_display()

    def _stop_recording(self, restore: bool = False):
        if not self._recording:
            return
        self._recording = False
        self._held_modifiers.clear()
        if restore:
            self._shortcut = self._previous_shortcut
        self._update_display()

    def _finalize(self, shortcut: str):
        self._shortcut = shortcut
        self._recording = False
        self._held_modifiers.clear()
        self._update_display()
        self.shortcut_changed.emit(shortcut)

    def mousePressEvent(self, event):
        if not self._recording:
            self._start_recording()
            self.setFocus(Qt.MouseFocusReason)
        event.accept()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if not self._recording:
            self._start_recording()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._stop_recording(restore=True)

    def event(self, event):
        if self._recording and event.type() == QEvent.ShortcutOverride:
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        if not self._recording:
            super().keyPressEvent(event)
            return

        event.accept()
        key = event.key()

        if key == Qt.Key_Escape:
            self._stop_recording(restore=True)
            return

        modifier_name = _qt_key_to_modifier(key)
        if modifier_name:
            self._held_modifiers.add(modifier_name)
            self._update_display()
            return

        if not self._held_modifiers:
            return

        key_name = _qt_key_to_name(key)
        if not key_name:
            return

        parts = [m for m in MODIFIER_CANONICAL_ORDER if m in self._held_modifiers]
        parts.append(key_name)
        self._finalize("+".join(parts))

    def keyReleaseEvent(self, event):
        if not self._recording:
            super().keyReleaseEvent(event)
            return

        event.accept()
        modifier_name = _qt_key_to_modifier(event.key())
        if modifier_name:
            self._held_modifiers.discard(modifier_name)
            self._update_display()


class KeymapsPanel(SettingsPanelBase):
    """Panel for keyboard shortcut settings."""

    @property
    def panel_title(self) -> str:
        return "Keymaps"

    def _setup_content(self, layout: QVBoxLayout) -> None:
        self._config_service = ConfigService()
        self._os_tabs: dict[str, QTableWidget] = {}

        description = QLabel(
            "Configure keyboard shortcuts for each operating system.\n"
            "Click a shortcut cell to record a new key combination."
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

        layout.addWidget(self._tab_widget, 1)

        self._load_keymaps()

    def _setup_ui(self):
        super()._setup_ui()
        stretch_index = self._content_layout.count() - 1
        item = self._content_layout.takeAt(stretch_index)
        del item

    def _create_os_tab(self, os_context: str) -> QWidget:
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
        table.verticalHeader().setDefaultSectionSize(46)

        tab_layout.addWidget(table)

        return tab

    def _create_action_combo(self) -> QComboBox:
        action_combo = QComboBox()
        action_combo.setFocusPolicy(Qt.StrongFocus)
        action_combo.wheelEvent = lambda e: e.ignore()
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
        return action_combo

    def _load_keymaps(self):
        settings_data = self._config_service.get_settings_data()
        keymaps = settings_data.get("keymaps", [])

        os_bindings = {"macos": {}, "linux": {}, "windows": {}}

        for keymap in keymaps:
            context = keymap.get("context", "")
            bindings = keymap.get("bindings", {})

            for os_name in os_bindings:
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

                    recorder = KeyRecorderWidget(shortcut)
                    recorder.shortcut_changed.connect(lambda _: self.mark_dirty())
                    table.setCellWidget(row, 0, recorder)

                    action_combo = self._create_action_combo()
                    for i in range(action_combo.count()):
                        if action_combo.itemData(i) == action:
                            action_combo.setCurrentIndex(i)
                            break

                    table.setCellWidget(row, 1, action_combo)

    def _add_binding(self, os_context: str):
        if os_context not in self._os_tabs:
            return

        table = self._os_tabs[os_context]
        row = table.rowCount()
        table.insertRow(row)

        recorder = KeyRecorderWidget("")
        recorder.shortcut_changed.connect(lambda _: self.mark_dirty())
        table.setCellWidget(row, 0, recorder)

        action_combo = self._create_action_combo()
        table.setCellWidget(row, 1, action_combo)

        table.selectRow(row)
        recorder.setFocus()
        self.mark_dirty()

    def _delete_binding(self, os_context: str):
        if os_context not in self._os_tabs:
            return

        table = self._os_tabs[os_context]
        current_row = table.currentRow()
        if current_row >= 0:
            table.removeRow(current_row)
            self.mark_dirty()

    def _collect_keymaps(self) -> list:
        keymaps = []

        for os_context, table in self._os_tabs.items():
            bindings = {}

            for row in range(table.rowCount()):
                recorder = table.cellWidget(row, 0)
                action_combo = table.cellWidget(row, 1)

                if recorder and action_combo:
                    shortcut = recorder.text().strip()
                    action = action_combo.currentData()

                    if shortcut and action:
                        bindings[shortcut] = action

            if bindings:
                keymaps.append(
                    {
                        "context": f"os == {os_context}",
                        "bindings": bindings,
                    }
                )

        return keymaps

    def save_changes(self) -> bool:
        keymaps = self._collect_keymaps()
        self._config_service.update_keymaps(keymaps, persist=False)
        self.mark_clean()
        return True

    def load_settings(self) -> None:
        self._load_keymaps()
        self.mark_clean()
