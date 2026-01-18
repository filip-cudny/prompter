"""Prompts settings panel."""

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from modules.gui.context_widgets import IconButton
from modules.gui.dialog_styles import (
    COLOR_BORDER,
    COLOR_TEXT,
    COLOR_TEXT_EDIT_BG,
    COLOR_DIALOG_BG,
    TOOLTIP_STYLE,
)
from modules.utils.config import ConfigService
from ..settings_panel_base import SettingsPanelBase
from ..widgets.prompt_list_widget import PromptListWidget
from ..widgets.prompt_editor_dialog import PromptEditorDialog
from ..widgets.prompt_template_dialog import PromptTemplateDialog


class PromptsPanel(SettingsPanelBase):
    """Panel for managing prompts."""

    @property
    def panel_title(self) -> str:
        return "Prompts"

    def _setup_content(self, layout: QVBoxLayout) -> None:
        """Set up the prompts panel content."""
        self._config_service = ConfigService()
        self._pending_generator_config = {}

        self._setup_generator_config_section(layout)

        self._prompt_list = PromptListWidget()
        self._prompt_list.prompt_add_requested.connect(self._on_add_prompt)
        self._prompt_list.prompt_edit_requested.connect(self._on_edit_prompt)
        self._prompt_list.prompt_delete_requested.connect(self._on_delete_prompt)
        self._prompt_list.order_changed.connect(self._on_order_changed)

        self._load_prompts()
        self._load_generator_config()

        layout.addWidget(self._prompt_list)

    def _setup_generator_config_section(self, layout: QVBoxLayout) -> None:
        """Set up the description generator configuration section."""
        container = QWidget()
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {COLOR_DIALOG_BG};
            }}
            QLabel {{
                color: {COLOR_TEXT};
            }}
            QComboBox {{
                background-color: {COLOR_TEXT_EDIT_BG};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                padding: 6px 8px;
                min-width: 200px;
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
        """)

        section_layout = QVBoxLayout(container)
        section_layout.setContentsMargins(0, 0, 0, 12)
        section_layout.setSpacing(8)

        title_label = QLabel("Description Generator")
        title_label.setStyleSheet(f"color: {COLOR_TEXT}; font-weight: bold;")
        section_layout.addWidget(title_label)

        row_layout = QHBoxLayout()
        row_layout.setSpacing(8)

        model_label = QLabel("Model:")
        row_layout.addWidget(model_label)

        self._generator_model_combo = QComboBox()
        self._generator_model_combo.addItem("Default (first available)", "")
        self._populate_generator_models()
        self._generator_model_combo.currentIndexChanged.connect(
            self._on_generator_model_changed
        )
        row_layout.addWidget(self._generator_model_combo)

        row_layout.addStretch()

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
        self._edit_prompt_btn = IconButton("edit", size=18)
        self._edit_prompt_btn.setStyleSheet(icon_btn_style)
        self._edit_prompt_btn.setToolTip("Edit generation prompt template")
        self._edit_prompt_btn.setCursor(Qt.PointingHandCursor)
        self._edit_prompt_btn.clicked.connect(self._on_edit_generator_prompt)
        row_layout.addWidget(self._edit_prompt_btn)

        section_layout.addLayout(row_layout)
        layout.addWidget(container)

    def _populate_generator_models(self) -> None:
        """Populate the generator model dropdown."""
        config = self._config_service.get_config()
        if config.models:
            for model in config.models:
                model_id = model.get("id")
                display_name = model.get("display_name", model_id)
                self._generator_model_combo.addItem(display_name, model_id)

    def _load_generator_config(self) -> None:
        """Load the description generator config into UI."""
        config = self._config_service.get_description_generator_config()
        model_id = config.get("model", "")

        for i in range(self._generator_model_combo.count()):
            if self._generator_model_combo.itemData(i) == model_id:
                self._generator_model_combo.setCurrentIndex(i)
                break

    def _on_generator_model_changed(self, index: int) -> None:
        """Handle generator model selection change."""
        model_id = self._generator_model_combo.itemData(index)
        self._pending_generator_config["model"] = model_id
        self.mark_dirty()

    def _on_edit_generator_prompt(self) -> None:
        """Open dialog to edit the generator prompt template."""
        config = self._config_service.get_description_generator_config()
        current_prompt = self._pending_generator_config.get(
            "prompt", config.get("prompt", "")
        )

        dialog = PromptTemplateDialog(current_prompt=current_prompt, parent=self)
        if dialog.exec_():
            result = dialog.get_result()
            if result is not None:
                self._pending_generator_config["prompt"] = result
                self.mark_dirty()

    def _load_prompts(self):
        """Load prompts from config."""
        settings_data = self._config_service.get_settings_data()
        prompts = settings_data.get("prompts", [])
        self._prompt_list.set_prompts(prompts)

    def _on_add_prompt(self):
        """Handle add prompt request."""
        dialog = PromptEditorDialog(parent=self)
        if dialog.exec_():
            result = dialog.get_result()
            if result:
                self._config_service.add_prompt(result, persist=False)
                self._load_prompts()
                self.mark_dirty()

    def _on_edit_prompt(self, prompt_data: dict):
        """Handle edit prompt request."""
        dialog = PromptEditorDialog(prompt_data=prompt_data, parent=self)
        if dialog.exec_():
            result = dialog.get_result()
            if result:
                self._config_service.update_prompt(result["id"], result, persist=False)
                self._load_prompts()
                self.mark_dirty()

    def _on_delete_prompt(self, prompt_id: str):
        """Handle delete prompt request."""
        self._config_service.delete_prompt(prompt_id, persist=False)
        self._load_prompts()
        self.mark_dirty()

    def _on_order_changed(self, prompt_ids: list):
        """Handle prompt order change."""
        self._config_service.update_prompts_order(prompt_ids, persist=False)
        self.mark_dirty()

    def save_changes(self) -> bool:
        """Save pending changes to config."""
        if self._pending_generator_config:
            self._config_service.update_description_generator_config(
                self._pending_generator_config, persist=False
            )
            self._pending_generator_config = {}
        self.mark_clean()
        return True

    def load_settings(self) -> None:
        """Reload settings from config."""
        self._load_prompts()
        self._load_generator_config()
        self._pending_generator_config = {}
        self.mark_clean()
