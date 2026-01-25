"""Widget for editing model configuration."""

import uuid
from typing import Any

from PySide6.QtCore import QLocale, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from modules.gui.icons import create_icon
from modules.gui.shared.theme import (
    COLOR_BORDER,
    COLOR_BUTTON_BG,
    COLOR_BUTTON_HOVER,
    COLOR_DIALOG_BG,
    COLOR_TEXT,
    COLOR_TEXT_EDIT_BG,
    COLOR_TEXT_SECONDARY,
    SVG_CHEVRON_DOWN_PATH,
    SVG_CHEVRON_UP_PATH,
)

PARAMETER_PRESETS = [
    ("temperature", "number"),
    ("max_tokens", "number"),
    ("top_p", "number"),
    ("frequency_penalty", "number"),
    ("presence_penalty", "number"),
    ("reasoning_effort", "string"),
]

PARAM_TYPES = ["number", "string", "boolean"]

FORM_STYLE = f"""
    QLineEdit {{
        background-color: {COLOR_TEXT_EDIT_BG};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 6px 10px;
    }}
    QDoubleSpinBox, QSpinBox {{
        background-color: {COLOR_TEXT_EDIT_BG};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 6px 10px;
        min-width: 100px;
    }}
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
    QSpinBox::up-button, QSpinBox::down-button {{
        background-color: {COLOR_BUTTON_BG};
        border: none;
        width: 20px;
    }}
    QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {{
        image: url("{SVG_CHEVRON_UP_PATH}");
        width: 10px;
        height: 10px;
    }}
    QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {{
        image: url("{SVG_CHEVRON_DOWN_PATH}");
        width: 10px;
        height: 10px;
    }}
    QLabel {{
        color: {COLOR_TEXT};
    }}
    QComboBox {{
        background-color: {COLOR_TEXT_EDIT_BG};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 6px 10px;
        min-width: 140px;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox::down-arrow {{
        image: url("{SVG_CHEVRON_DOWN_PATH}");
        width: 12px;
        height: 12px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {COLOR_DIALOG_BG};
        color: {COLOR_TEXT};
        selection-background-color: {COLOR_BUTTON_BG};
    }}
    QCheckBox {{
        color: {COLOR_TEXT};
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {COLOR_BORDER};
        border-radius: 3px;
        background-color: {COLOR_TEXT_EDIT_BG};
    }}
    QCheckBox::indicator:checked {{
        background-color: {COLOR_BUTTON_BG};
    }}
"""

ICON_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: transparent;
        border: none;
        padding: 4px;
        border-radius: 4px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_BUTTON_BG};
    }}
"""

ADD_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {COLOR_BUTTON_BG};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 6px 12px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_BORDER};
    }}
"""


class PasswordLineEdit(QWidget):
    """Line edit with password toggle button."""

    textChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._visible = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._line_edit = QLineEdit()
        self._line_edit.setEchoMode(QLineEdit.Password)
        self._line_edit.textChanged.connect(self.textChanged.emit)
        layout.addWidget(self._line_edit)

        self._toggle_btn = QPushButton()
        self._toggle_btn.setIcon(create_icon("eye"))
        self._toggle_btn.setFixedSize(28, 28)
        self._toggle_btn.setStyleSheet(ICON_BUTTON_STYLE)
        self._toggle_btn.setToolTip("Show/hide API key")
        self._toggle_btn.clicked.connect(self._toggle_visibility)
        layout.addWidget(self._toggle_btn)

    def _toggle_visibility(self):
        self._visible = not self._visible
        self._line_edit.setEchoMode(QLineEdit.Normal if self._visible else QLineEdit.Password)
        self._toggle_btn.setIcon(create_icon("eye-off" if self._visible else "eye"))

    def text(self) -> str:
        return self._line_edit.text()

    def setText(self, text: str):
        self._line_edit.setText(text)

    def setPlaceholderText(self, text: str):
        self._line_edit.setPlaceholderText(text)

    def clear(self):
        self._line_edit.clear()
        self._visible = False
        self._line_edit.setEchoMode(QLineEdit.Password)
        self._toggle_btn.setIcon(create_icon("eye"))


class ParameterRowWidget(QWidget):
    """Widget representing a single parameter row."""

    deleted = Signal(object)

    def __init__(
        self,
        name: str,
        value: Any,
        param_type: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._name = name
        self._param_type = param_type
        self._setup_ui(value)

    def _setup_ui(self, value: Any):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 8, 4)
        layout.setSpacing(8)

        self._name_label = QLabel(self._name)
        self._name_label.setMinimumWidth(120)
        self._name_label.setStyleSheet(f"color: {COLOR_TEXT};")
        layout.addWidget(self._name_label)

        if self._param_type == "number":
            if isinstance(value, float) or (isinstance(value, int) and "." in str(value)):
                self._value_widget = QDoubleSpinBox()
                self._value_widget.setLocale(QLocale(QLocale.C))
                self._value_widget.setRange(-1000000, 1000000)
                self._value_widget.setDecimals(2)
                self._value_widget.setSingleStep(0.1)
                self._value_widget.setValue(float(value) if value is not None else 0.0)
            else:
                self._value_widget = QSpinBox()
                self._value_widget.setLocale(QLocale(QLocale.C))
                self._value_widget.setRange(-1000000, 1000000)
                self._value_widget.setValue(int(value) if value is not None else 0)
        elif self._param_type == "boolean":
            self._value_widget = QCheckBox()
            self._value_widget.setChecked(bool(value) if value is not None else False)
        else:
            self._value_widget = QLineEdit()
            self._value_widget.setText(str(value) if value is not None else "")

        self._value_widget.setMinimumWidth(100)
        layout.addWidget(self._value_widget, 1)

        type_label = QLabel(f"({self._param_type})")
        type_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(type_label)

        delete_btn = QPushButton()
        delete_btn.setIcon(create_icon("trash"))
        delete_btn.setFixedSize(28, 28)
        delete_btn.setStyleSheet(ICON_BUTTON_STYLE)
        delete_btn.setToolTip("Remove parameter")
        delete_btn.clicked.connect(lambda: self.deleted.emit(self))
        layout.addWidget(delete_btn)

    def get_name(self) -> str:
        return self._name

    def get_value(self) -> Any:
        if self._param_type == "number":
            return self._value_widget.value()
        elif self._param_type == "boolean":
            return self._value_widget.isChecked()
        else:
            return self._value_widget.text()

    def get_type(self) -> str:
        return self._param_type


class AddParameterDialog(QDialog):
    """Dialog for adding a new parameter."""

    def __init__(self, existing_params: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self._existing_params = existing_params
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Add Parameter")
        self.setMinimumWidth(350)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_DIALOG_BG};
            }}
            QLabel {{
                color: {COLOR_TEXT};
            }}
            QLineEdit, QComboBox {{
                background-color: {COLOR_TEXT_EDIT_BG};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                padding: 6px 10px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLOR_DIALOG_BG};
                color: {COLOR_TEXT};
                selection-background-color: {COLOR_BUTTON_BG};
            }}
            QDoubleSpinBox {{
                background-color: {COLOR_TEXT_EDIT_BG};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                padding: 6px 10px;
            }}
            QCheckBox {{
                color: {COLOR_TEXT};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        self._name_combo = QComboBox()
        self._name_combo.setEditable(True)
        available_presets = [name for name, _ in PARAMETER_PRESETS if name not in self._existing_params]
        self._name_combo.addItems(available_presets)
        self._name_combo.setCurrentText("")
        self._name_combo.currentTextChanged.connect(self._on_name_changed)
        form_layout.addRow("Name:", self._name_combo)

        self._type_combo = QComboBox()
        self._type_combo.addItems(["Number", "String", "Boolean"])
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        form_layout.addRow("Type:", self._type_combo)

        self._value_stack = QStackedWidget()

        self._number_input = QDoubleSpinBox()
        self._number_input.setLocale(QLocale(QLocale.C))
        self._number_input.setRange(-1000000, 1000000)
        self._number_input.setDecimals(2)
        self._number_input.setSingleStep(0.1)
        self._value_stack.addWidget(self._number_input)

        self._string_input = QLineEdit()
        self._value_stack.addWidget(self._string_input)

        self._boolean_input = QCheckBox("Enabled")
        self._value_stack.addWidget(self._boolean_input)

        form_layout.addRow("Value:", self._value_stack)

        layout.addLayout(form_layout)

        button_row = QHBoxLayout()
        button_row.addStretch()

        button_style = f"""
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
        """

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(button_style)
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)

        save_btn = QPushButton("Add")
        save_btn.setStyleSheet(button_style)
        save_btn.clicked.connect(self.accept)
        button_row.addWidget(save_btn)

        layout.addLayout(button_row)

    def _on_name_changed(self, name: str):
        preset_types = dict(PARAMETER_PRESETS)
        if name in preset_types:
            param_type = preset_types[name]
            type_index = {"number": 0, "string": 1, "boolean": 2}.get(param_type, 0)
            self._type_combo.setCurrentIndex(type_index)

    def _on_type_changed(self, type_text: str):
        type_lower = type_text.lower()
        index = {"number": 0, "string": 1, "boolean": 2}.get(type_lower, 0)
        self._value_stack.setCurrentIndex(index)

    def get_parameter(self) -> tuple[str, Any, str] | None:
        name = self._name_combo.currentText().strip()
        if not name:
            return None

        type_text = self._type_combo.currentText().lower()
        if type_text == "number":
            value = self._number_input.value()
        elif type_text == "boolean":
            value = self._boolean_input.isChecked()
        else:
            value = self._string_input.text()

        return (name, value, type_text)


class ModelEditorWidget(QWidget):
    """Widget for editing a model's configuration."""

    model_changed = Signal(str, dict)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._model_id: str | None = None
        self._is_new: bool = False
        self._parameter_rows: list[ParameterRowWidget] = []
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

        self._display_name_edit = QLineEdit()
        self._display_name_edit.setPlaceholderText("Model Display Name")
        self._display_name_edit.setToolTip("Name shown in the UI")
        form_layout.addRow("Display Name:", self._display_name_edit)

        self._model_edit = QLineEdit()
        self._model_edit.setPlaceholderText("gpt-4")
        self._model_edit.setToolTip("Model ID sent to the API")
        form_layout.addRow("Model ID:", self._model_edit)

        self._api_key_source_combo = QComboBox()
        self._api_key_source_combo.addItems(["Environment Variable", "Direct"])
        self._api_key_source_combo.currentIndexChanged.connect(self._on_api_key_source_changed)
        self._api_key_source_combo.setToolTip("How the API key is provided")
        form_layout.addRow("API Key Source:", self._api_key_source_combo)

        self._api_key_stack = QStackedWidget()

        self._api_key_env_edit = QLineEdit()
        self._api_key_env_edit.setPlaceholderText("OPENAI_API_KEY")
        self._api_key_env_edit.setToolTip("Environment variable name containing the API key")
        self._api_key_stack.addWidget(self._api_key_env_edit)

        self._api_key_direct_edit = PasswordLineEdit()
        self._api_key_direct_edit.setPlaceholderText("sk-...")
        self._api_key_stack.addWidget(self._api_key_direct_edit)

        form_layout.addRow("API Key:", self._api_key_stack)

        self._base_url_edit = QLineEdit()
        self._base_url_edit.setPlaceholderText("https://api.openai.com/v1")
        self._base_url_edit.setToolTip("API base URL (optional)")
        form_layout.addRow("Base URL:", self._base_url_edit)

        layout.addLayout(form_layout)

        self._setup_parameters_section(layout)

        layout.addStretch()

        self.setEnabled(False)

    def _setup_parameters_section(self, parent_layout: QVBoxLayout):
        """Set up the parameters section with dynamic add/remove."""
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        params_label = QLabel("Parameters")
        params_label.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT};
                font-size: 13px;
                font-weight: bold;
            }}
        """)
        header_layout.addWidget(params_label)

        header_layout.addStretch()

        add_btn = QPushButton("+ Add")
        add_btn.setStyleSheet(ADD_BUTTON_STYLE)
        add_btn.clicked.connect(self._add_parameter)
        header_layout.addWidget(add_btn)

        parent_layout.addLayout(header_layout)

        self._params_container = QWidget()
        self._params_layout = QVBoxLayout(self._params_container)
        self._params_layout.setContentsMargins(0, 0, 0, 0)
        self._params_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self._params_container)
        scroll_area.setMaximumHeight(200)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                background-color: {COLOR_TEXT_EDIT_BG};
            }}
            QScrollBar:vertical {{
                background-color: {COLOR_DIALOG_BG};
                width: 10px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLOR_BORDER};
                border-radius: 5px;
            }}
        """)
        parent_layout.addWidget(scroll_area)

        self._no_params_label = QLabel("No parameters configured")
        self._no_params_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; padding: 12px;")
        self._no_params_label.setAlignment(Qt.AlignCenter)
        self._params_layout.addWidget(self._no_params_label)

    def _on_api_key_source_changed(self, index: int):
        self._api_key_stack.setCurrentIndex(index)

    def _add_parameter(self):
        existing = [row.get_name() for row in self._parameter_rows]
        dialog = AddParameterDialog(existing, self)
        if dialog.exec() == QDialog.Accepted:
            result = dialog.get_parameter()
            if result:
                name, value, param_type = result
                if name not in existing:
                    self._add_parameter_row(name, value, param_type)

    def _add_parameter_row(self, name: str, value: Any, param_type: str):
        if self._no_params_label.isVisible():
            self._no_params_label.hide()

        row = ParameterRowWidget(name, value, param_type, self)
        row.deleted.connect(self._remove_parameter_row)
        self._parameter_rows.append(row)
        self._params_layout.addWidget(row)

    def _remove_parameter_row(self, row: ParameterRowWidget):
        if row in self._parameter_rows:
            self._parameter_rows.remove(row)
            self._params_layout.removeWidget(row)
            row.deleteLater()

            if not self._parameter_rows:
                self._no_params_label.show()

    def _clear_parameters(self):
        for row in self._parameter_rows[:]:
            self._params_layout.removeWidget(row)
            row.deleteLater()
        self._parameter_rows.clear()
        self._no_params_label.show()

    def load_model(self, model_id: str, config: dict[str, Any]):
        """Load a model configuration into the editor."""
        self._model_id = model_id
        self._is_new = False
        self.setEnabled(True)

        self._display_name_edit.setText(config.get("display_name", ""))
        self._model_edit.setText(config.get("model", ""))

        api_key_source = config.get("api_key_source", "env")
        if api_key_source == "direct":
            self._api_key_source_combo.setCurrentIndex(1)
            self._api_key_direct_edit.setText(config.get("api_key", ""))
            self._api_key_env_edit.clear()
        else:
            self._api_key_source_combo.setCurrentIndex(0)
            self._api_key_env_edit.setText(config.get("api_key_env", ""))
            self._api_key_direct_edit.clear()

        self._base_url_edit.setText(config.get("base_url", ""))

        self._clear_parameters()
        parameters = config.get("parameters", {})
        for name, value in parameters.items():
            param_type = self._infer_param_type(value)
            self._add_parameter_row(name, value, param_type)

    def _infer_param_type(self, value: Any) -> str:
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, (int, float)):
            return "number"
        else:
            return "string"

    def clear(self):
        """Clear the editor and disable it."""
        self._model_id = None
        self._is_new = False
        self.setEnabled(False)

        self._display_name_edit.clear()
        self._model_edit.clear()
        self._api_key_source_combo.setCurrentIndex(0)
        self._api_key_env_edit.clear()
        self._api_key_direct_edit.clear()
        self._base_url_edit.clear()
        self._clear_parameters()

    def get_model_data(self) -> tuple[str, dict[str, Any]] | None:
        """Get the current model data from the editor."""
        display_name = self._display_name_edit.text().strip()
        model = self._model_edit.text().strip()

        api_key_source = "direct" if self._api_key_source_combo.currentIndex() == 1 else "env"

        if api_key_source == "env":
            api_key_env = self._api_key_env_edit.text().strip()
            if not all([display_name, model, api_key_env]):
                return None
        else:
            api_key = self._api_key_direct_edit.text().strip()
            if not all([display_name, model, api_key]):
                return None

        model_id = self._model_id if self._model_id else str(uuid.uuid4())

        config = {
            "display_name": display_name,
            "model": model,
            "api_key_source": api_key_source,
        }

        if api_key_source == "env":
            config["api_key_env"] = self._api_key_env_edit.text().strip()
        else:
            config["api_key"] = self._api_key_direct_edit.text().strip()

        base_url = self._base_url_edit.text().strip()
        if base_url:
            config["base_url"] = base_url

        parameters = {}
        for row in self._parameter_rows:
            parameters[row.get_name()] = row.get_value()
        if parameters:
            config["parameters"] = parameters

        return (model_id, config)

    def is_new_model(self) -> bool:
        """Check if this is editing a new model."""
        return self._is_new

    def get_model_id(self) -> str | None:
        """Get the current model ID."""
        return self._model_id

    def set_new_mode(self):
        """Set the editor to new model mode with a new UUID."""
        self._model_id = str(uuid.uuid4())
        self._is_new = True
        self.setEnabled(True)

        self._display_name_edit.clear()
        self._model_edit.clear()
        self._api_key_source_combo.setCurrentIndex(0)
        self._api_key_env_edit.setText("OPENAI_API_KEY")
        self._api_key_direct_edit.clear()
        self._base_url_edit.setText("https://api.openai.com/v1")
        self._clear_parameters()

        self._display_name_edit.setFocus()
