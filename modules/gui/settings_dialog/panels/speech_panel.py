"""Speech settings panel."""


from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from modules.gui.shared.dialog_styles import (
    COLOR_BORDER,
    COLOR_TEXT,
    COLOR_TEXT_EDIT_BG,
)
from modules.utils.config import ConfigService

from ..settings_panel_base import SettingsPanelBase

FORM_STYLE = f"""
    QLineEdit {{
        background-color: {COLOR_TEXT_EDIT_BG};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 8px;
    }}
    QLabel {{
        color: {COLOR_TEXT};
    }}
"""


class SpeechPanel(SettingsPanelBase):
    """Panel for speech-to-text model settings."""

    @property
    def panel_title(self) -> str:
        return "Speech"

    def _setup_content(self, layout: QVBoxLayout) -> None:
        """Set up the speech panel content."""
        self._config_service = ConfigService()

        description = QLabel(
            "Configure the speech-to-text model used for voice input.\n"
            "This model is used for transcribing audio recordings."
        )
        description.setStyleSheet("color: #888888; margin-bottom: 16px;")
        description.setWordWrap(True)
        layout.addWidget(description)

        form_container = QWidget()
        form_container.setStyleSheet(FORM_STYLE)
        form_layout = QFormLayout(form_container)
        form_layout.setSpacing(16)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._model_edit = QLineEdit()
        self._model_edit.setPlaceholderText("gpt-4o-transcribe")
        self._model_edit.setToolTip("Model ID sent to the API for transcription")
        form_layout.addRow("Model:", self._model_edit)

        self._display_name_edit = QLineEdit()
        self._display_name_edit.setPlaceholderText("Speech Model Name")
        self._display_name_edit.setToolTip("Display name shown in the UI")
        form_layout.addRow("Display Name:", self._display_name_edit)

        self._api_key_env_edit = QLineEdit()
        self._api_key_env_edit.setPlaceholderText("OPENAI_API_KEY")
        self._api_key_env_edit.setToolTip(
            "Environment variable name containing the API key"
        )
        form_layout.addRow("API Key Env:", self._api_key_env_edit)

        self._base_url_edit = QLineEdit()
        self._base_url_edit.setPlaceholderText("https://api.openai.com/v1")
        self._base_url_edit.setToolTip("API base URL for the transcription service")
        form_layout.addRow("Base URL:", self._base_url_edit)

        layout.addWidget(form_container)

        self._model_edit.textChanged.connect(self._on_field_changed)
        self._display_name_edit.textChanged.connect(self._on_field_changed)
        self._api_key_env_edit.textChanged.connect(self._on_field_changed)
        self._base_url_edit.textChanged.connect(self._on_field_changed)

        self._load_settings()

    def _load_settings(self):
        """Load speech model settings from config."""
        settings_data = self._config_service.get_settings_data()
        speech_config = settings_data.get("speech_to_text_model", {})

        self._model_edit.blockSignals(True)
        self._display_name_edit.blockSignals(True)
        self._api_key_env_edit.blockSignals(True)
        self._base_url_edit.blockSignals(True)

        self._model_edit.setText(speech_config.get("model", ""))
        self._display_name_edit.setText(speech_config.get("display_name", ""))
        self._api_key_env_edit.setText(speech_config.get("api_key_env", ""))
        self._base_url_edit.setText(speech_config.get("base_url", ""))

        self._model_edit.blockSignals(False)
        self._display_name_edit.blockSignals(False)
        self._api_key_env_edit.blockSignals(False)
        self._base_url_edit.blockSignals(False)

    def _on_field_changed(self):
        """Handle any field change."""
        self.mark_dirty()

    def save_changes(self) -> bool:
        """Save pending changes to config."""
        model = self._model_edit.text().strip()
        display_name = self._display_name_edit.text().strip()
        api_key_env = self._api_key_env_edit.text().strip()

        if not all([model, display_name, api_key_env]):
            self.mark_clean()
            return True

        speech_config = {
            "model": model,
            "display_name": display_name,
            "api_key_env": api_key_env,
        }

        base_url = self._base_url_edit.text().strip()
        if base_url:
            speech_config["base_url"] = base_url

        self._config_service.update_speech_model(speech_config, persist=False)
        self.mark_clean()
        return True

    def load_settings(self) -> None:
        """Reload settings from config."""
        self._load_settings()
        self.mark_clean()
