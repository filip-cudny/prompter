"""Notifications settings panel."""


from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from modules.gui.shared.dialog_styles import (
    COLOR_BORDER,
    COLOR_BUTTON_BG,
    COLOR_BUTTON_HOVER,
    COLOR_TEXT,
)
from modules.utils.config import ConfigService
from modules.utils.notification_config import DEFAULT_NOTIFICATION_SETTINGS

from ..settings_panel_base import SettingsPanelBase

EVENT_LABELS = {
    "prompt_execution_success": "Prompt execution success",
    "prompt_execution_cancel": "Prompt execution cancelled",
    "prompt_execution_in_progress": "Prompt execution in progress",
    "speech_recording_start": "Speech recording started",
    "speech_recording_stop": "Speech recording stopped",
    "speech_transcription_success": "Speech transcription success",
    "context_saved": "Context saved",
    "context_set": "Context set",
    "context_append": "Context appended",
    "context_cleared": "Context cleared",
    "clipboard_copy": "Clipboard copy",
    "image_added": "Image added",
}


GROUP_STYLE = f"""
    QGroupBox {{
        color: {COLOR_TEXT};
        font-weight: bold;
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        margin-top: 12px;
        padding-top: 8px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
    }}
"""

CHECKBOX_STYLE = f"""
    QCheckBox {{
        color: {COLOR_TEXT};
        spacing: 8px;
    }}
"""


class ColorButton(QPushButton):
    """Button that shows and allows selection of a color."""

    def __init__(self, color: str = "#FFFFFF", parent: QWidget | None = None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(80, 28)
        self.clicked.connect(self._on_clicked)
        self._update_style()

    def _update_style(self):
        """Update button style to show current color."""
        text_color = "#000000" if self._is_light_color() else "#FFFFFF"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._color};
                color: {text_color};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid {COLOR_BUTTON_HOVER};
            }}
            QPushButton:disabled {{
                background-color: {COLOR_BUTTON_BG};
                color: #666666;
                border: 1px solid {COLOR_BORDER};
            }}
        """)
        self.setText(self._color)

    def _is_light_color(self) -> bool:
        """Check if the current color is light."""
        try:
            hex_color = self._color.lstrip("#")
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            return luminance > 0.5
        except (ValueError, IndexError):
            return True

    def _on_clicked(self):
        """Handle button click to show color picker."""
        from PySide6.QtGui import QColor
        color = QColorDialog.getColor(QColor(self._color), self, "Select Color")
        if color.isValid():
            self._color = color.name()
            self._update_style()

    def get_color(self) -> str:
        """Get the current color."""
        return self._color

    def set_color(self, color: str):
        """Set the current color."""
        self._color = color
        self._update_style()


class NotificationsPanel(SettingsPanelBase):
    """Panel for notification settings."""

    @property
    def panel_title(self) -> str:
        return "Notifications"

    def _setup_content(self, layout: QVBoxLayout) -> None:
        """Set up the notifications panel content."""
        self._config_service = ConfigService()
        self._event_checkboxes: dict[str, QCheckBox] = {}
        self._color_buttons: dict[str, ColorButton] = {}
        self._icon_color_buttons: dict[str, ColorButton] = {}

        events_group = QGroupBox("Notification Events")
        events_group.setStyleSheet(GROUP_STYLE)
        events_layout = QVBoxLayout(events_group)
        events_layout.setSpacing(8)

        for event_key, label in EVENT_LABELS.items():
            checkbox = QCheckBox(label)
            checkbox.setStyleSheet(CHECKBOX_STYLE)
            checkbox.stateChanged.connect(self._on_event_changed)
            self._event_checkboxes[event_key] = checkbox
            events_layout.addWidget(checkbox)

        layout.addWidget(events_group)

        colors_group = QGroupBox("Colors")
        colors_group.setStyleSheet(GROUP_STYLE)
        colors_layout = QVBoxLayout(colors_group)
        colors_layout.setSpacing(12)

        self._monochrome_checkbox = QCheckBox("Use monochromatic icons")
        self._monochrome_checkbox.setStyleSheet(CHECKBOX_STYLE)
        self._monochrome_checkbox.stateChanged.connect(self._on_monochrome_changed)
        colors_layout.addWidget(self._monochrome_checkbox)

        color_grid = QFormLayout()
        color_grid.setSpacing(8)

        for color_type in ["success", "error", "info", "warning"]:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(12)

            bg_btn = ColorButton()
            bg_btn.clicked.connect(self._on_color_changed)
            self._color_buttons[color_type] = bg_btn

            icon_btn = ColorButton()
            icon_btn.clicked.connect(self._on_icon_color_changed)
            self._icon_color_buttons[color_type] = icon_btn

            bg_label = QLabel("background:")
            bg_label.setStyleSheet(f"color: {COLOR_TEXT};")
            row_layout.addWidget(bg_label)
            row_layout.addWidget(bg_btn)
            icon_label = QLabel("icon:")
            icon_label.setStyleSheet(f"color: {COLOR_TEXT};")
            row_layout.addWidget(icon_label)
            row_layout.addWidget(icon_btn)
            row_layout.addStretch()

            label = QLabel(f"{color_type.capitalize()}")
            label.setStyleSheet(f"color: {COLOR_TEXT}; font-weight: bold;")
            color_grid.addRow(label, row_layout)

        colors_layout.addLayout(color_grid)
        layout.addWidget(colors_group)

        options_group = QGroupBox("Display Options")
        options_group.setStyleSheet(GROUP_STYLE)
        options_layout = QVBoxLayout(options_group)

        opacity_row = QHBoxLayout()
        opacity_label = QLabel("Opacity:")
        opacity_label.setStyleSheet(f"color: {COLOR_TEXT};")
        opacity_row.addWidget(opacity_label)

        self._opacity_slider = QSlider(Qt.Horizontal)
        self._opacity_slider.setMinimum(20)
        self._opacity_slider.setMaximum(100)
        self._opacity_slider.setTickPosition(QSlider.TicksBelow)
        self._opacity_slider.setTickInterval(10)
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_row.addWidget(self._opacity_slider)

        self._opacity_value_label = QLabel("80%")
        self._opacity_value_label.setStyleSheet(f"color: {COLOR_TEXT}; min-width: 40px;")
        opacity_row.addWidget(self._opacity_value_label)

        options_layout.addLayout(opacity_row)

        layout.addWidget(options_group)

        self._load_settings()

    def _load_settings(self):
        """Load notification settings from config."""
        settings_data = self._config_service.get_settings_data()
        notifications = settings_data.get("notifications", DEFAULT_NOTIFICATION_SETTINGS)

        events = notifications.get("events", DEFAULT_NOTIFICATION_SETTINGS["events"])
        for event_key, checkbox in self._event_checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(events.get(event_key, True))
            checkbox.blockSignals(False)

        bg_colors = notifications.get(
            "background_colors", DEFAULT_NOTIFICATION_SETTINGS["background_colors"]
        )
        for color_type, color_btn in self._color_buttons.items():
            color_btn.set_color(bg_colors.get(color_type, "#FFFFFF"))

        icon_colors = notifications.get(
            "icon_colors", DEFAULT_NOTIFICATION_SETTINGS["icon_colors"]
        )
        for color_type, icon_btn in self._icon_color_buttons.items():
            default_color = DEFAULT_NOTIFICATION_SETTINGS["icon_colors"].get(color_type, "#000000")
            icon_btn.set_color(icon_colors.get(color_type, default_color))

        monochrome = notifications.get(
            "monochromatic_notification_icons",
            DEFAULT_NOTIFICATION_SETTINGS["monochromatic_notification_icons"],
        )
        self._monochrome_checkbox.blockSignals(True)
        self._monochrome_checkbox.setChecked(monochrome)
        self._monochrome_checkbox.blockSignals(False)

        for btn in self._icon_color_buttons.values():
            btn.setEnabled(not monochrome)
            btn.setToolTip("Disabled because monochromatic icons is enabled" if monochrome else "")

        opacity = notifications.get("opacity", DEFAULT_NOTIFICATION_SETTINGS["opacity"])
        opacity_percent = int(opacity * 100)
        self._opacity_slider.blockSignals(True)
        self._opacity_slider.setValue(opacity_percent)
        self._opacity_slider.blockSignals(False)
        self._opacity_value_label.setText(f"{opacity_percent}%")

    def _on_event_changed(self, state: int):
        """Handle event checkbox change."""
        self.mark_dirty()

    def _on_color_changed(self):
        """Handle color button change."""
        self.mark_dirty()

    def _on_icon_color_changed(self):
        """Handle icon color button change."""
        self.mark_dirty()

    def _on_monochrome_changed(self, state: int):
        """Handle monochrome checkbox change."""
        is_monochrome = state == Qt.Checked
        for btn in self._icon_color_buttons.values():
            btn.setEnabled(not is_monochrome)
            btn.setToolTip("Disabled because monochromatic icons is enabled" if is_monochrome else "")
        self.mark_dirty()

    def _on_opacity_changed(self, value: int):
        """Handle opacity slider change."""
        self._opacity_value_label.setText(f"{value}%")
        self.mark_dirty()

    def save_changes(self) -> bool:
        """Save notification settings to config."""
        events = {key: cb.isChecked() for key, cb in self._event_checkboxes.items()}
        bg_colors = {key: btn.get_color() for key, btn in self._color_buttons.items()}
        icon_colors = {key: btn.get_color() for key, btn in self._icon_color_buttons.items()}
        opacity = self._opacity_slider.value() / 100.0

        notifications_config = {
            "events": events,
            "background_colors": bg_colors,
            "icon_colors": icon_colors,
            "monochromatic_notification_icons": self._monochrome_checkbox.isChecked(),
            "opacity": opacity,
        }

        self._config_service.update_notifications(notifications_config, persist=False)
        self.mark_clean()
        return True

    def load_settings(self) -> None:
        """Reload settings from config."""
        self._load_settings()
        self.mark_clean()
