"""Dialog for editing a single prompt."""

import logging
import uuid
import re
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.gui.context_widgets import IconButton
from modules.gui.dialog_styles import (
    COLOR_BORDER,
    COLOR_BUTTON_BG,
    COLOR_BUTTON_HOVER,
    COLOR_DIALOG_BG,
    COLOR_TEXT,
    COLOR_TEXT_EDIT_BG,
    SVG_CHEVRON_DOWN_PATH,
    TOOLTIP_STYLE,
    get_dialog_stylesheet,
)

logger = logging.getLogger(__name__)

MIN_CONTENT_LENGTH = 10


class DescriptionGeneratorWorker(QThread):
    """Worker thread for generating descriptions via API."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        name: str,
        system_content: str,
        user_content: str,
        placeholder_info: Dict[str, str],
        parent: Optional[QThread] = None,
    ):
        super().__init__(parent)
        self._name = name
        self._system_content = system_content
        self._user_content = user_content
        self._placeholder_info = placeholder_info

    def _build_user_message(self) -> str:
        """Build the structured user message with prompt details."""
        parts = [f"Prompt to describe\nprompt name: {self._name}"]

        if self._system_content:
            parts.append(f"\nsystem:\n<system_prompt>\n{self._system_content}\n</system_prompt>")

        if self._user_content:
            parts.append(f"\n<user_message>\n{self._user_content}\n</user_message>")

        if self._placeholder_info:
            placeholder_lines = []
            for name, description in self._placeholder_info.items():
                placeholder_lines.append(f'<placeholder name="{name}">{description}</placeholder>')
            placeholders_xml = "\n".join(placeholder_lines)
            parts.append(
                f"\nPlaceholders:\n"
                f"Placeholders are marked as {{{{xxx}}}} and are dynamically replaced during prompt execution.\n\n"
                f"<placeholders>\n{placeholders_xml}\n</placeholders>"
            )

        return "\n".join(parts)

    def run(self):
        try:
            from modules.utils.config import ConfigService

            config_service = ConfigService()
            config = config_service.get_description_generator_config()

            model_id = config.get("model", "")
            system_prompt = config.get("system_prompt", "")

            if not model_id:
                models = config_service.get_models_list()
                if models:
                    model_id = models[0].get("id")

            if not model_id:
                self.error.emit("No model configured for description generation")
                return

            model_config = config_service.get_model_by_id(model_id)
            if not model_config:
                self.error.emit(f"Model '{model_id}' not found")
                return

            from core.openai_service import OpenAiService

            single_model_config = [{
                "id": model_id,
                **model_config,
            }]

            service = OpenAiService(models_config=single_model_config)

            user_message = self._build_user_message()
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
            response = service.complete(model_id, messages)

            description = response.strip()
            self.finished.emit(description)

        except Exception as e:
            logger.exception("Failed to generate description")
            self.error.emit(str(e))


class PromptEditorDialog(QDialog):
    """Dialog for creating or editing a prompt."""

    def __init__(
        self,
        prompt_data: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._prompt_data = prompt_data or {}
        self._is_new = prompt_data is None
        self._result_data: Optional[Dict[str, Any]] = None
        self._generator_worker: Optional[DescriptionGeneratorWorker] = None

        self.setWindowTitle("New Prompt" if self._is_new else "Edit Prompt")
        self.setMinimumSize(600, 500)
        self.resize(700, 600)
        self.setStyleSheet(get_dialog_stylesheet())

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        form_container = QWidget()
        form_container.setStyleSheet(f"""
            QLineEdit, QComboBox {{
                background-color: {COLOR_TEXT_EDIT_BG};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                padding: 8px;
            }}
            QTextEdit {{
                background-color: {COLOR_TEXT_EDIT_BG};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                padding: 8px;
                font-family: "Menlo", "Monaco", "Consolas", monospace;
                font-size: 12px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
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
            QLabel {{
                color: {COLOR_TEXT};
            }}
        """)
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(12)

        name_row = QHBoxLayout()
        name_label = QLabel("Name:")
        name_label.setFixedWidth(100)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Prompt name")
        name_row.addWidget(name_label)
        name_row.addWidget(self._name_edit)
        form_layout.addLayout(name_row)

        model_row = QHBoxLayout()
        model_label = QLabel("Model (optional):")
        model_label.setFixedWidth(100)
        self._model_combo = QComboBox()
        self._model_combo.addItem("Use Default", "")
        self._populate_models()
        model_row.addWidget(model_label)
        model_row.addWidget(self._model_combo)
        form_layout.addLayout(model_row)

        placeholder_info_label = QLabel(self._build_placeholder_info_text())
        placeholder_info_label.setStyleSheet(f"""
            QLabel {{
                color: #888888;
                font-size: 11px;
                padding: 4px 0;
            }}
        """)
        placeholder_info_label.setWordWrap(True)
        form_layout.addWidget(placeholder_info_label)

        system_label = QLabel("System Message:")
        form_layout.addWidget(system_label)

        self._system_edit = QTextEdit()
        self._system_edit.setPlaceholderText("Enter system message content...")
        self._system_edit.setMinimumHeight(120)
        form_layout.addWidget(self._system_edit)

        user_label = QLabel("User Message Template:")
        form_layout.addWidget(user_label)

        self._user_edit = QTextEdit()
        self._user_edit.setPlaceholderText(
            "Enter user message template. Use {{clipboard}} and {{context}} placeholders."
        )
        self._user_edit.setMinimumHeight(100)
        form_layout.addWidget(self._user_edit)

        description_label = QLabel("Description:")
        form_layout.addWidget(description_label)

        description_row = QHBoxLayout()
        description_row.setAlignment(Qt.AlignTop)
        self._description_edit = QTextEdit()
        self._description_edit.setPlaceholderText("Description (optional)")
        self._description_edit.setMinimumHeight(60)
        self._description_edit.setMaximumHeight(80)
        description_row.addWidget(self._description_edit)

        icon_btn_style = f"""
            QPushButton {{
                background: transparent;
                border: none;
                padding: 4px;
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
            }}
            {TOOLTIP_STYLE}
        """
        self._generate_btn = IconButton("bot", size=18)
        self._generate_btn.setStyleSheet(icon_btn_style)
        self._generate_btn.setToolTip("Generate description using AI")
        self._generate_btn.setEnabled(False)
        self._generate_btn.clicked.connect(self._on_generate_description)
        description_row.addWidget(self._generate_btn, alignment=Qt.AlignTop)
        form_layout.addLayout(description_row)

        self._system_edit.textChanged.connect(self._update_generate_button_state)
        self._user_edit.textChanged.connect(self._update_generate_button_state)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setWidget(form_container)
        layout.addWidget(scroll_area)

        button_row = QHBoxLayout()
        button_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_BUTTON_BG};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_BUTTON_HOVER};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_BUTTON_BG};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_BUTTON_HOVER};
            }}
        """)
        save_btn.clicked.connect(self._on_save)
        button_row.addWidget(save_btn)

        layout.addLayout(button_row)

    def _populate_models(self):
        """Populate model dropdown from config."""
        from modules.utils.config import ConfigService

        config_service = ConfigService()
        config = config_service.get_config()

        if config.models:
            for model in config.models:
                model_id = model.get("id")
                display_name = model.get("display_name", model_id)
                self._model_combo.addItem(display_name, model_id)

    def _load_file_content(self, file_path: str) -> str:
        """Load content from a file path."""
        import logging

        from core.services import SettingsService

        try:
            settings_service = SettingsService()
            settings_service.load_settings()
            return settings_service._load_file_content(file_path)
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to load file {file_path}: {e}")
            return f"[Error loading file: {file_path}]"

    def _load_data(self):
        """Load prompt data into form fields."""
        if not self._prompt_data:
            self._user_edit.setPlainText("{{clipboard}}")
            self._update_generate_button_state()
            return

        self._name_edit.setText(self._prompt_data.get("name", ""))
        self._description_edit.setPlainText(self._prompt_data.get("description", ""))

        model = self._prompt_data.get("model", "")
        for i in range(self._model_combo.count()):
            if self._model_combo.itemData(i) == model:
                self._model_combo.setCurrentIndex(i)
                break

        messages = self._prompt_data.get("messages", [])
        for msg in messages:
            role = msg.get("role", "")
            if role == "system":
                if "file" in msg:
                    content = self._load_file_content(msg["file"])
                    self._system_edit.setPlainText(content)
                elif "content" in msg:
                    self._system_edit.setPlainText(msg["content"])
            elif role == "user":
                self._user_edit.setPlainText(msg.get("content", ""))

        self._update_generate_button_state()

    def _on_save(self):
        """Handle save button click."""
        name = self._name_edit.text().strip()
        if not name:
            return

        invalid_placeholders = self._validate_placeholders()
        if invalid_placeholders:
            unique_invalid = list(dict.fromkeys(invalid_placeholders))
            placeholder_list = ", ".join(f"{{{{{p}}}}}" for p in unique_invalid)
            reply = QMessageBox.warning(
                self,
                "Invalid Placeholders",
                f"The following placeholders are not recognized:\n{placeholder_list}\n\n"
                "These will not be replaced during prompt execution.",
                QMessageBox.Save | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if reply != QMessageBox.Save:
                return

        prompt_id = self._prompt_data.get("id", str(uuid.uuid4()))

        messages = []

        system_content = self._system_edit.toPlainText().strip()
        if system_content:
            messages.append({"role": "system", "content": system_content})

        user_content = self._user_edit.toPlainText().strip()
        if user_content:
            messages.append({"role": "user", "content": user_content})

        self._result_data = {
            "id": prompt_id,
            "name": name,
            "messages": messages,
        }

        description = self._description_edit.toPlainText().strip()
        if description:
            self._result_data["description"] = description

        model = self._model_combo.currentData()
        if model:
            self._result_data["model"] = model

        self.accept()

    def get_result(self) -> Optional[Dict[str, Any]]:
        """Get the edited prompt data.

        Returns:
            Prompt data dict if saved, None if cancelled
        """
        return self._result_data

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    def _get_combined_content_length(self) -> int:
        """Get the combined length of system and user content."""
        system_len = len(self._system_edit.toPlainText().strip())
        user_len = len(self._user_edit.toPlainText().strip())
        return system_len + user_len

    def _update_generate_button_state(self):
        """Update the generate button enabled state and tooltip."""
        content_len = self._get_combined_content_length()
        is_generating = (
            self._generator_worker is not None and self._generator_worker.isRunning()
        )

        if is_generating:
            self._generate_btn.setEnabled(False)
            self._generate_btn.setToolTip("Generating...")
        elif content_len >= MIN_CONTENT_LENGTH:
            self._generate_btn.setEnabled(True)
            self._generate_btn.setToolTip("Generate description using AI")
        else:
            chars_needed = MIN_CONTENT_LENGTH - content_len
            self._generate_btn.setEnabled(False)
            self._generate_btn.setToolTip(
                f"Enter at least {chars_needed} more character{'s' if chars_needed != 1 else ''}"
            )

    def _on_generate_description(self):
        """Start description generation in background thread."""
        if self._generator_worker is not None and self._generator_worker.isRunning():
            return

        name = self._name_edit.text().strip()
        system_content = self._system_edit.toPlainText().strip()
        user_content = self._user_edit.toPlainText().strip()
        placeholder_info = self._get_placeholder_info()

        self._generator_worker = DescriptionGeneratorWorker(
            name=name,
            system_content=system_content,
            user_content=user_content,
            placeholder_info=placeholder_info,
            parent=self,
        )
        self._generator_worker.finished.connect(self._on_generation_finished)
        self._generator_worker.error.connect(self._on_generation_error)
        self._generator_worker.start()

        self._update_generate_button_state()

    def _on_generation_finished(self, description: str):
        """Handle successful description generation."""
        self._description_edit.setPlainText(description)
        self._update_generate_button_state()

    def _on_generation_error(self, error_msg: str):
        """Handle description generation error."""
        logger.warning(f"Description generation failed: {error_msg}")
        self._update_generate_button_state()

    def _get_placeholder_info(self) -> Dict[str, str]:
        """Get placeholder info from the placeholder registry."""
        return {
            "clipboard": "The current clipboard text content",
            "context": "Persistent context data set across prompt executions",
        }

    def _build_placeholder_info_text(self) -> str:
        """Build the placeholder info display text."""
        info = self._get_placeholder_info()
        lines = ["Available Placeholders:"]
        for name, description in info.items():
            lines.append(f"  {{{{{name}}}}} - {description}")
        return "\n".join(lines)

    def _find_invalid_placeholders(self, content: str) -> List[str]:
        """Find invalid placeholders in content."""
        pattern = r"\{\{(\w+)\}\}"
        found = re.findall(pattern, content)
        valid_names = set(self._get_placeholder_info().keys())
        return [name for name in found if name not in valid_names]

    def _validate_placeholders(self) -> List[str]:
        """Validate placeholders in both system and user messages.

        Returns:
            List of invalid placeholder names found.
        """
        system_content = self._system_edit.toPlainText()
        user_content = self._user_edit.toPlainText()
        combined_content = f"{system_content}\n{user_content}"
        return self._find_invalid_placeholders(combined_content)
