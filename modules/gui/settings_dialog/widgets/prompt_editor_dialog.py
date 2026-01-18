"""Dialog for editing a single prompt."""

import uuid
from typing import Any, Dict, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.gui.dialog_styles import (
    COLOR_BORDER,
    COLOR_BUTTON_BG,
    COLOR_BUTTON_HOVER,
    COLOR_DIALOG_BG,
    COLOR_TEXT,
    COLOR_TEXT_EDIT_BG,
    get_dialog_stylesheet,
)


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
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid {COLOR_TEXT};
                margin-right: 8px;
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

        system_label = QLabel("System Message:")
        form_layout.addWidget(system_label)

        self._system_edit = QTextEdit()
        self._system_edit.setPlaceholderText(
            "Enter system message content or leave empty for file reference..."
        )
        self._system_edit.setMinimumHeight(120)
        form_layout.addWidget(self._system_edit)

        system_file_row = QHBoxLayout()
        file_label = QLabel("Or file path:")
        file_label.setFixedWidth(100)
        self._system_file_edit = QLineEdit()
        self._system_file_edit.setPlaceholderText("prompts/my_prompt.md")
        system_file_row.addWidget(file_label)
        system_file_row.addWidget(self._system_file_edit)
        form_layout.addLayout(system_file_row)

        user_label = QLabel("User Message Template:")
        form_layout.addWidget(user_label)

        self._user_edit = QTextEdit()
        self._user_edit.setPlaceholderText(
            "Enter user message template. Use {{clipboard}} and {{context}} placeholders."
        )
        self._user_edit.setMinimumHeight(100)
        form_layout.addWidget(self._user_edit)

        layout.addWidget(form_container)

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
            for model_key, model_config in config.models.items():
                display_name = model_config.get("display_name", model_key)
                self._model_combo.addItem(display_name, model_key)

    def _load_data(self):
        """Load prompt data into form fields."""
        if not self._prompt_data:
            self._user_edit.setPlainText("{{clipboard}}")
            return

        self._name_edit.setText(self._prompt_data.get("name", ""))

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
                    self._system_file_edit.setText(msg["file"])
                elif "content" in msg:
                    self._system_edit.setPlainText(msg["content"])
            elif role == "user":
                self._user_edit.setPlainText(msg.get("content", ""))

    def _on_save(self):
        """Handle save button click."""
        name = self._name_edit.text().strip()
        if not name:
            return

        prompt_id = self._prompt_data.get("id", str(uuid.uuid4()))

        messages = []

        system_content = self._system_edit.toPlainText().strip()
        system_file = self._system_file_edit.text().strip()

        if system_file:
            messages.append({"role": "system", "file": system_file})
        elif system_content:
            messages.append({"role": "system", "content": system_content})

        user_content = self._user_edit.toPlainText().strip()
        if user_content:
            messages.append({"role": "user", "content": user_content})

        self._result_data = {
            "id": prompt_id,
            "name": name,
            "messages": messages,
        }

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
