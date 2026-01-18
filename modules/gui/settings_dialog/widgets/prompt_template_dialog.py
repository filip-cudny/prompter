"""Dialog for editing the description generator prompt template."""

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.gui.dialog_styles import (
    COLOR_BORDER,
    COLOR_BUTTON_BG,
    COLOR_BUTTON_HOVER,
    COLOR_TEXT,
    COLOR_TEXT_EDIT_BG,
    get_dialog_stylesheet,
)

DEFAULT_PROMPT = """Generate a concise 3-4 word description for the following AI prompt.
The description should capture the primary purpose or action.
Only respond with the description, nothing else.

Prompt name: {{name}}
System message: {{system}}
User message template: {{user}}"""


class PromptTemplateDialog(QDialog):
    """Dialog for editing the description generator prompt template."""

    def __init__(
        self,
        current_prompt: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._current_prompt = current_prompt or DEFAULT_PROMPT
        self._result_prompt: Optional[str] = None

        self.setWindowTitle("Edit Description Generator Prompt")
        self.setMinimumSize(500, 400)
        self.resize(600, 450)
        self.setStyleSheet(get_dialog_stylesheet())

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        info_label = QLabel(
            "Edit the prompt template used to generate descriptions.\n"
            "Available placeholders: {{name}}, {{system}}, {{user}}"
        )
        info_label.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 12px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self._prompt_edit = QTextEdit()
        self._prompt_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLOR_TEXT_EDIT_BG};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                padding: 8px;
                font-family: "Menlo", "Monaco", "Consolas", monospace;
                font-size: 12px;
            }}
        """)
        self._prompt_edit.setPlainText(self._current_prompt)
        layout.addWidget(self._prompt_edit)

        button_row = QHBoxLayout()

        reset_btn = QPushButton("Reset to Default")
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_BUTTON_BG};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_BUTTON_HOVER};
            }}
        """)
        reset_btn.clicked.connect(self._on_reset)
        button_row.addWidget(reset_btn)

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

    def _on_reset(self):
        """Reset prompt to default."""
        self._prompt_edit.setPlainText(DEFAULT_PROMPT)

    def _on_save(self):
        """Handle save button click."""
        self._result_prompt = self._prompt_edit.toPlainText().strip()
        self.accept()

    def get_result(self) -> Optional[str]:
        """Get the edited prompt template."""
        return self._result_prompt

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
