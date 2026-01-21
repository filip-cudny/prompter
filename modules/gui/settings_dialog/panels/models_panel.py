"""Models settings panel."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from modules.gui.shared.dialog_styles import (
    COLOR_BORDER,
    COLOR_BUTTON_BG,
    COLOR_BUTTON_HOVER,
    COLOR_DIALOG_BG,
    COLOR_SELECTION,
    COLOR_TEXT,
    COLOR_TEXT_EDIT_BG,
    TOOLTIP_STYLE,
)
from modules.utils.config import ConfigService

from ..settings_panel_base import SettingsPanelBase
from ..widgets.model_editor_widget import ModelEditorWidget

TOOLBAR_BTN_STYLE = (
    f"""
    QPushButton {{
        background-color: {COLOR_BUTTON_BG};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 6px 12px;
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


class ModelsPanel(SettingsPanelBase):
    """Panel for managing AI model configurations."""

    @property
    def panel_title(self) -> str:
        return "Models"

    def _setup_content(self, layout: QVBoxLayout) -> None:
        """Set up the models panel content."""
        self._config_service = ConfigService()

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._add_btn = QPushButton("Add")
        self._add_btn.setStyleSheet(TOOLBAR_BTN_STYLE)
        self._add_btn.setToolTip("Add new model")
        self._add_btn.clicked.connect(self._on_add_model)
        toolbar.addWidget(self._add_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setStyleSheet(TOOLBAR_BTN_STYLE)
        self._delete_btn.setToolTip("Delete selected model")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete_model)
        toolbar.addWidget(self._delete_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {COLOR_BORDER};
                width: 1px;
            }}
        """)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 8, 0)

        self._model_list = QListWidget()
        self._model_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {COLOR_TEXT_EDIT_BG};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 10px;
                border-bottom: 1px solid {COLOR_BORDER};
            }}
            QListWidget::item:last-child {{
                border-bottom: none;
            }}
            QListWidget::item:selected {{
                background-color: {COLOR_SELECTION};
            }}
            QListWidget::item:hover {{
                background-color: #3a3a3a;
            }}
        """)
        self._model_list.itemSelectionChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self._model_list)
        splitter.addWidget(left_container)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(8, 0, 0, 0)

        self._model_editor = ModelEditorWidget()
        right_layout.addWidget(self._model_editor)
        splitter.addWidget(right_container)

        splitter.setSizes([200, 400])
        layout.addWidget(splitter)

        self._load_models()

    def _load_models(self):
        """Load models from config."""
        self._model_list.clear()
        self._model_editor.clear()

        settings_data = self._config_service.get_settings_data()
        models = settings_data.get("models", [])

        for model in models:
            model_id = model.get("id")
            display_name = model.get("display_name", model_id)
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, model_id)
            self._model_list.addItem(item)

        self._update_button_states()

    def _on_selection_changed(self):
        """Handle model selection change."""
        self._update_button_states()

        current = self._model_list.currentItem()
        if current:
            model_id = current.data(Qt.UserRole)
            settings_data = self._config_service.get_settings_data()
            models = settings_data.get("models", [])
            for model in models:
                if model.get("id") == model_id:
                    self._model_editor.load_model(model_id, model)
                    break

    def _update_button_states(self):
        """Update enabled state of buttons based on selection."""
        has_selection = self._model_list.currentItem() is not None
        self._delete_btn.setEnabled(has_selection and not self._model_editor.is_new_model())

    def _on_add_model(self):
        """Handle add model request."""
        self._model_list.clearSelection()
        self._model_editor.set_new_mode()
        self._delete_btn.setEnabled(False)
        self.mark_dirty()

    def _on_save_model(self):
        """Handle save model request (in-panel save button)."""
        result = self._model_editor.get_model_data()
        if not result:
            return

        model_id, config = result
        self._config_service.update_model(model_id, config, persist=False)
        self._load_models()
        self.mark_dirty()

        for i in range(self._model_list.count()):
            item = self._model_list.item(i)
            if item.data(Qt.UserRole) == model_id:
                self._model_list.setCurrentItem(item)
                break

    def _on_delete_model(self):
        """Handle delete model request."""
        current = self._model_list.currentItem()
        if current:
            model_id = current.data(Qt.UserRole)
            self._config_service.delete_model(model_id, persist=False)
            self._load_models()
            self.mark_dirty()

    def save_changes(self) -> bool:
        """Save pending changes to config."""
        result = self._model_editor.get_model_data()
        if result:
            model_id, config = result
            self._config_service.update_model(model_id, config, persist=False)
            self._load_models()
            for i in range(self._model_list.count()):
                item = self._model_list.item(i)
                if item.data(Qt.UserRole) == model_id:
                    self._model_list.setCurrentItem(item)
                    break
        self.mark_clean()
        return True

    def load_settings(self) -> None:
        """Reload settings from config."""
        self._load_models()
        self.mark_clean()
