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

DEFAULT_SYSTEM_PROMPT = """You are an AI assistant whose sole task is to generate a short, concise description explaining what a given prompt does.

You will receive:

* The prompt name.
* The full system prompt content.
* The user message template, including placeholders and their explanations.

Your goal:

* Produce a brief description (1–3 sentences or up to 3 bullet points) that clearly summarizes the purpose and behavior of the prompt.
* The description must be suitable for quick recall in a list or context menu.
* **Always write the description in the same language as the core system prompt.**
* **Ignore the language of examples, sample inputs, or sample outputs inside the prompt.**
* **If the system prompt is written in English, the output MUST be in English.**

Rules:

* Emphasize whether the prompt performs execution, refinement, correction, translation, or a **lossless transformation**.
* Explicitly distinguish transformations from summarization or content reduction when applicable.
* Do not restate the prompt name verbatim.
* Do not describe internal formatting, Markdown, or XML mechanics unless essential to understanding behavior.
* Do not explain placeholders individually unless they are critical to the prompt’s function.
* Do not add examples.
* Output either a single short paragraph or up to 3 bullet points.
* Do not use meta commentary.
* Output only the final description text.
* **Under no circumstances translate the description into another language.**

"""


class PromptTemplateDialog(QDialog):
    """Dialog for editing the description generator prompt template."""

    def __init__(
        self,
        current_prompt: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._current_prompt = current_prompt or DEFAULT_SYSTEM_PROMPT
        self._result_prompt: Optional[str] = None

        self.setWindowTitle("Edit Description Generator System Prompt")
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
            "Edit the system prompt used for description generation.\n"
            "The prompt name, system message, and user template are passed automatically."
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
        self._prompt_edit.setPlainText(DEFAULT_SYSTEM_PROMPT)

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
