"""Prompts settings panel."""

from typing import Optional

from PyQt5.QtWidgets import QVBoxLayout, QWidget

from modules.utils.config import ConfigService
from ..settings_panel_base import SettingsPanelBase
from ..widgets.prompt_list_widget import PromptListWidget
from ..widgets.prompt_editor_dialog import PromptEditorDialog


class PromptsPanel(SettingsPanelBase):
    """Panel for managing prompts."""

    @property
    def panel_title(self) -> str:
        return "Prompts"

    def _setup_content(self, layout: QVBoxLayout) -> None:
        """Set up the prompts panel content."""
        self._config_service = ConfigService()

        self._prompt_list = PromptListWidget()
        self._prompt_list.prompt_add_requested.connect(self._on_add_prompt)
        self._prompt_list.prompt_edit_requested.connect(self._on_edit_prompt)
        self._prompt_list.prompt_delete_requested.connect(self._on_delete_prompt)
        self._prompt_list.order_changed.connect(self._on_order_changed)

        self._load_prompts()

        layout.addWidget(self._prompt_list)

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
        self.mark_clean()
        return True

    def load_settings(self) -> None:
        """Reload settings from config."""
        self._load_prompts()
        self.mark_clean()
