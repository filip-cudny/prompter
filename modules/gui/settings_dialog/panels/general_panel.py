"""General settings panel."""

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from modules.gui.dialog_styles import (
    COLOR_BORDER,
    COLOR_BUTTON_BG,
    COLOR_COMBOBOX_ARROW,
    COLOR_DIALOG_BG,
    COLOR_TEXT,
    COLOR_TEXT_EDIT_BG,
)
from modules.gui.icons import get_svg_data_url
from modules.utils.config import ConfigService
from ..settings_panel_base import SettingsPanelBase

_SVG_CHEVRON_DOWN_URL = get_svg_data_url("chevron-down", COLOR_COMBOBOX_ARROW)
_SVG_CHEVRON_UP_URL = get_svg_data_url("chevron-up", COLOR_COMBOBOX_ARROW)

FORM_STYLE = f"""
    QComboBox {{
        background-color: {COLOR_TEXT_EDIT_BG};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 6px 10px;
        min-width: 200px;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox::down-arrow {{
        image: url("{_SVG_CHEVRON_DOWN_URL}");
        width: 12px;
        height: 12px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {COLOR_DIALOG_BG};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        selection-background-color: {COLOR_BUTTON_BG};
    }}
    QSpinBox {{
        background-color: {COLOR_TEXT_EDIT_BG};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 6px 10px;
        min-width: 100px;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        background-color: {COLOR_BUTTON_BG};
        border: none;
        width: 20px;
    }}
    QSpinBox::up-arrow {{
        image: url("{_SVG_CHEVRON_UP_URL}");
        width: 10px;
        height: 10px;
    }}
    QSpinBox::down-arrow {{
        image: url("{_SVG_CHEVRON_DOWN_URL}");
        width: 10px;
        height: 10px;
    }}
    QLabel {{
        color: {COLOR_TEXT};
    }}
"""


class GeneralPanel(SettingsPanelBase):
    """Panel for general application settings."""

    @property
    def panel_title(self) -> str:
        return "General"

    def _setup_content(self, layout: QVBoxLayout) -> None:
        """Set up the general settings content."""
        self._config_service = ConfigService()

        form_container = QWidget()
        form_container.setStyleSheet(FORM_STYLE)
        form_layout = QFormLayout(form_container)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(16)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._model_combo = QComboBox()
        self._populate_model_combo()
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)

        model_label = QLabel("Default Model:")
        model_label.setToolTip("The default AI model used for prompt execution")
        form_layout.addRow(model_label, self._model_combo)

        self._debounce_spin = QSpinBox()
        self._debounce_spin.setRange(0, 10000)
        self._debounce_spin.setSuffix(" ms")
        self._debounce_spin.setSingleStep(50)
        self._load_debounce_value()
        self._debounce_spin.valueChanged.connect(self._on_debounce_changed)

        debounce_label = QLabel("Number Input Debounce:")
        debounce_label.setToolTip(
            "Delay before processing number input in menus (milliseconds)"
        )
        form_layout.addRow(debounce_label, self._debounce_spin)

        layout.addWidget(form_container)

    def _populate_model_combo(self):
        """Populate the model dropdown from config."""
        self._model_combo.clear()
        config = self._config_service.get_config()
        settings_data = self._config_service.get_settings_data()

        current_default = settings_data.get("default_model", "")

        if config.models:
            for model in config.models:
                model_id = model.get("id")
                display_name = model.get("display_name", model_id)
                self._model_combo.addItem(display_name, model_id)

                if model_id == current_default:
                    self._model_combo.setCurrentIndex(self._model_combo.count() - 1)

    def _load_debounce_value(self):
        """Load the debounce value from config."""
        settings_data = self._config_service.get_settings_data()
        debounce = settings_data.get("number_input_debounce_ms", 200)
        self._debounce_spin.setValue(debounce)

    def _on_model_changed(self, index: int):
        """Handle model selection change."""
        if index >= 0:
            self.mark_dirty()

    def _on_debounce_changed(self, value: int):
        """Handle debounce value change."""
        self.mark_dirty()

    def save_changes(self) -> bool:
        """Save pending changes to config."""
        model_key = self._model_combo.currentData()
        if model_key:
            self._config_service.update_setting("default_model", model_key, persist=False)
            self._config_service.update_default_model(model_key)

        debounce_value = self._debounce_spin.value()
        self._config_service.update_setting(
            "number_input_debounce_ms", debounce_value, persist=False
        )

        self.mark_clean()
        return True

    def load_settings(self) -> None:
        """Reload settings from config."""
        self._populate_model_combo()
        self._load_debounce_value()
        self.mark_clean()
