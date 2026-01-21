"""Main Settings dialog with VSCode-style sidebar navigation."""

from typing import Optional

from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from modules.gui.shared.base_dialog import BaseDialog
from modules.gui.shared.dialog_styles import (
    BUTTON_ROW_SPACING,
    COLOR_BORDER,
    COLOR_BUTTON_BG,
    COLOR_BUTTON_HOVER,
    COLOR_DIALOG_BG,
    COLOR_TEXT,
    TOOLTIP_STYLE,
    create_singleton_dialog_manager,
)
from modules.utils.config import ConfigService
from .settings_sidebar import SettingsSidebar
from .panels import (
    GeneralPanel,
    PromptsPanel,
    ModelsPanel,
    NotificationsPanel,
    SpeechPanel,
    KeymapsPanel,
)


SETTINGS_DIALOG_SIZE = (800, 600)
SETTINGS_MIN_SIZE = (700, 500)


SAVE_BTN_STYLE = (
    f"""
    QPushButton {{
        background-color: {COLOR_BUTTON_BG};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 8px 24px;
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


CATEGORIES = [
    ("general", "General"),
    ("prompts", "Prompts"),
    ("models", "Models"),
    ("notifications", "Notifications"),
    ("speech", "Speech"),
    ("keymaps", "Keymaps"),
]


class SettingsDialog(BaseDialog):
    """VSCode-style settings dialog with sidebar navigation."""

    STATE_KEY = "settings_dialog"
    DEFAULT_SIZE = SETTINGS_DIALOG_SIZE
    MIN_SIZE = SETTINGS_MIN_SIZE

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._config_service = ConfigService()
        self.setWindowTitle("Settings")
        self.apply_dialog_styles()
        self._setup_ui()
        self.restore_geometry_from_state()

    def _setup_ui(self):
        """Set up the dialog UI."""
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._sidebar = SettingsSidebar(CATEGORIES)
        self._sidebar.category_selected.connect(self._on_category_selected)
        main_layout.addWidget(self._sidebar)

        content_container = QWidget()
        content_container.setStyleSheet(f"""
            QWidget {{
                background-color: {COLOR_DIALOG_BG};
            }}
        """)
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._panels = {}

        self._panels["general"] = GeneralPanel()
        self._panels["prompts"] = PromptsPanel()
        self._panels["models"] = ModelsPanel()
        self._panels["notifications"] = NotificationsPanel()
        self._panels["speech"] = SpeechPanel()
        self._panels["keymaps"] = KeymapsPanel()

        for panel in self._panels.values():
            self._stack.addWidget(panel)
            panel.settings_changed.connect(self._on_settings_changed)

        content_layout.addWidget(self._stack)
        main_layout.addWidget(content_container)

        main_container = QWidget()
        main_container.setLayout(main_layout)
        outer_layout.addWidget(main_container, 1)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(16, 8, 16, 12)
        button_row.setSpacing(BUTTON_ROW_SPACING)
        button_row.addStretch()

        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setStyleSheet(SAVE_BTN_STYLE)
        self._reset_btn.setToolTip("Discard changes and reset to saved settings")
        self._reset_btn.setEnabled(False)
        self._reset_btn.clicked.connect(self._on_reset_all)
        button_row.addWidget(self._reset_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.setStyleSheet(SAVE_BTN_STYLE)
        self._save_btn.setToolTip("Save all changes")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save_all)
        button_row.addWidget(self._save_btn)

        outer_layout.addLayout(button_row)

        self.setLayout(outer_layout)
        self._on_category_selected(0)

    def _on_category_selected(self, index: int):
        """Handle category selection from sidebar."""
        if 0 <= index < len(CATEGORIES):
            category_id = CATEGORIES[index][0]
            if category_id in self._panels:
                self._stack.setCurrentWidget(self._panels[category_id])

    def _on_settings_changed(self):
        """Handle settings change from any panel."""
        self._update_save_button_state()

    def _update_save_button_state(self):
        """Enable Save and Reset buttons if any panel has unsaved changes."""
        any_dirty = any(panel.is_dirty() for panel in self._panels.values())
        self._save_btn.setEnabled(any_dirty)
        self._reset_btn.setEnabled(any_dirty)

    def _on_save_all(self):
        """Save all pending changes."""
        for panel in self._panels.values():
            if panel.is_dirty():
                panel.save_changes()
        self._config_service.save_settings()
        self._update_save_button_state()

    def _on_reset_all(self):
        """Reset all panels to saved settings."""
        self._config_service.reload_settings()
        for panel in self._panels.values():
            panel.load_settings()
        self._update_save_button_state()

    def keyPressEvent(self, event):
        """Handle key press events."""
        if self.handle_escape_key(event):
            return
        super().keyPressEvent(event)


_show_dialog = create_singleton_dialog_manager()


def show_settings_dialog():
    """Show the settings dialog (singleton)."""
    _show_dialog("settings_dialog", lambda: SettingsDialog())
