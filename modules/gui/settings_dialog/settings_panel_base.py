"""Base class for settings panels."""


from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from modules.gui.shared.dialog_styles import COLOR_DIALOG_BG, COLOR_TEXT


class SettingsPanelBase(QWidget):
    """Base class for all settings panels.

    Subclasses should implement:
    - panel_title: Property returning the panel's display title
    - _setup_content(): Method to set up the panel's UI content
    """

    settings_changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._is_dirty = False
        self._setup_ui()

    def mark_dirty(self):
        """Mark panel as having unsaved changes."""
        self._is_dirty = True
        self.settings_changed.emit()

    def mark_clean(self):
        """Mark panel as having no unsaved changes."""
        self._is_dirty = False

    def is_dirty(self) -> bool:
        """Check if panel has unsaved changes."""
        return self._is_dirty

    @property
    def panel_title(self) -> str:
        """Return the panel's display title. Override in subclasses."""
        return "Settings"

    def _setup_content(self, layout: QVBoxLayout) -> None:
        """Set up the panel's content widgets. Override in subclasses.

        Args:
            layout: The content layout to add widgets to
        """
        pass

    def _setup_ui(self):
        """Set up the panel UI with title and scrollable content."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        title_label = QLabel(self.panel_title)
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT};
                font-size: 18px;
                font-weight: bold;
            }}
        """)
        main_layout.addWidget(title_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: {COLOR_DIALOG_BG};
            }}
        """)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 12, 0)
        content_layout.setSpacing(12)

        self._setup_content(content_layout)

        content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

    def save_changes(self) -> bool:
        """Save any pending changes. Override in subclasses.

        Returns:
            True if save was successful, False otherwise
        """
        self.mark_clean()
        return True

    def load_settings(self) -> None:
        """Load/reload settings from config. Override in subclasses."""
        pass
