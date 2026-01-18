"""Widget for editing model configuration."""

from typing import Any, Dict, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from modules.gui.dialog_styles import (
    COLOR_BORDER,
    COLOR_BUTTON_BG,
    COLOR_DIALOG_BG,
    COLOR_TEXT,
    COLOR_TEXT_EDIT_BG,
)


FORM_STYLE = f"""
    QLineEdit {{
        background-color: {COLOR_TEXT_EDIT_BG};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 6px 10px;
    }}
    QDoubleSpinBox {{
        background-color: {COLOR_TEXT_EDIT_BG};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 6px 10px;
        min-width: 100px;
    }}
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
        background-color: {COLOR_BUTTON_BG};
        border: none;
        width: 20px;
    }}
    QLabel {{
        color: {COLOR_TEXT};
    }}
"""


class ModelEditorWidget(QWidget):
    """Widget for editing a model's configuration."""

    model_changed = pyqtSignal(str, dict)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_key: Optional[str] = None
        self._setup_ui()

    def _setup_ui(self):
        """Set up the widget UI."""
        self.setStyleSheet(FORM_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("Model Configuration")
        title.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT};
                font-size: 14px;
                font-weight: bold;
            }}
        """)
        layout.addWidget(title)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._key_edit = QLineEdit()
        self._key_edit.setPlaceholderText("unique-model-key")
        self._key_edit.setToolTip("Unique identifier for the model (used internally)")
        form_layout.addRow("Key:", self._key_edit)

        self._display_name_edit = QLineEdit()
        self._display_name_edit.setPlaceholderText("Model Display Name")
        self._display_name_edit.setToolTip("Name shown in the UI")
        form_layout.addRow("Display Name:", self._display_name_edit)

        self._model_edit = QLineEdit()
        self._model_edit.setPlaceholderText("gpt-4")
        self._model_edit.setToolTip("Model ID sent to the API")
        form_layout.addRow("Model ID:", self._model_edit)

        self._api_key_env_edit = QLineEdit()
        self._api_key_env_edit.setPlaceholderText("OPENAI_API_KEY")
        self._api_key_env_edit.setToolTip(
            "Environment variable name containing the API key"
        )
        form_layout.addRow("API Key Env:", self._api_key_env_edit)

        self._base_url_edit = QLineEdit()
        self._base_url_edit.setPlaceholderText("https://api.openai.com/v1")
        self._base_url_edit.setToolTip("API base URL (optional)")
        form_layout.addRow("Base URL:", self._base_url_edit)

        self._temperature_spin = QDoubleSpinBox()
        self._temperature_spin.setRange(0.0, 2.0)
        self._temperature_spin.setSingleStep(0.1)
        self._temperature_spin.setDecimals(1)
        self._temperature_spin.setValue(0.7)
        self._temperature_spin.setToolTip("Temperature for response generation (0-2)")
        form_layout.addRow("Temperature:", self._temperature_spin)

        layout.addLayout(form_layout)
        layout.addStretch()

        self.setEnabled(False)

    def load_model(self, key: str, config: Dict[str, Any]):
        """Load a model configuration into the editor.

        Args:
            key: The model key
            config: The model configuration dict
        """
        self._current_key = key
        self.setEnabled(True)

        self._key_edit.setText(key)
        self._display_name_edit.setText(config.get("display_name", ""))
        self._model_edit.setText(config.get("model", ""))
        self._api_key_env_edit.setText(config.get("api_key_env", ""))
        self._base_url_edit.setText(config.get("base_url", ""))
        self._temperature_spin.setValue(config.get("temperature", 0.7))

    def clear(self):
        """Clear the editor and disable it."""
        self._current_key = None
        self.setEnabled(False)

        self._key_edit.clear()
        self._display_name_edit.clear()
        self._model_edit.clear()
        self._api_key_env_edit.clear()
        self._base_url_edit.clear()
        self._temperature_spin.setValue(0.7)

    def get_model_data(self) -> Optional[tuple]:
        """Get the current model data from the editor.

        Returns:
            Tuple of (key, config) or None if invalid
        """
        key = self._key_edit.text().strip()
        display_name = self._display_name_edit.text().strip()
        model = self._model_edit.text().strip()
        api_key_env = self._api_key_env_edit.text().strip()

        if not all([key, display_name, model, api_key_env]):
            return None

        config = {
            "display_name": display_name,
            "model": model,
            "api_key_env": api_key_env,
            "temperature": self._temperature_spin.value(),
        }

        base_url = self._base_url_edit.text().strip()
        if base_url:
            config["base_url"] = base_url

        return (key, config)

    def is_new_model(self) -> bool:
        """Check if this is editing a new model.

        Returns:
            True if editing a new model, False if editing existing
        """
        return self._current_key is None

    def get_original_key(self) -> Optional[str]:
        """Get the original model key (before any edits).

        Returns:
            The original key or None if new model
        """
        return self._current_key

    def set_new_mode(self):
        """Set the editor to new model mode."""
        self._current_key = None
        self.setEnabled(True)

        self._key_edit.clear()
        self._display_name_edit.clear()
        self._model_edit.clear()
        self._api_key_env_edit.setText("OPENAI_API_KEY")
        self._base_url_edit.setText("https://api.openai.com/v1")
        self._temperature_spin.setValue(0.7)

        self._key_edit.setFocus()
