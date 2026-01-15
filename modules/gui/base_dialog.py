"""Base dialog class with common functionality."""

from PyQt5.QtCore import QEvent, Qt, QTimer
from PyQt5.QtWidgets import QDialog

from modules.gui.dialog_styles import (
    DEFAULT_DIALOG_SIZE,
    DIALOG_SHOW_DELAY_MS,
    MIN_DIALOG_SIZE,
    get_dialog_stylesheet,
)
from modules.utils.ui_state import UIStateManager


class BaseDialog(QDialog):
    """Base class for dialogs with geometry persistence and focus management.

    Features:
    - Window geometry save/restore via UIStateManager
    - Focus management to keep dialog on top
    - Standard dark theme styling
    - Configurable window size and minimum size

    Subclasses should:
    - Override STATE_KEY with a unique identifier
    - Call apply_dialog_styles() in __init__ if using standard styling
    - Call restore_geometry_from_state() after setting up the UI
    """

    # Override in subclass for state persistence key
    STATE_KEY: str = "base_dialog"

    # Override in subclass for custom sizes
    DEFAULT_SIZE = DEFAULT_DIALOG_SIZE
    MIN_SIZE = MIN_DIALOG_SIZE

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ui_state = UIStateManager()
        self.setWindowFlags(Qt.Window)
        self.setMinimumSize(*self.MIN_SIZE)
        self.resize(*self.DEFAULT_SIZE)

    def apply_dialog_styles(self):
        """Apply standard dark theme dialog styles."""
        self.setStyleSheet(get_dialog_stylesheet())

    def restore_geometry_from_state(self):
        """Restore window geometry from saved state."""
        geometry = self._ui_state.get(f"{self.STATE_KEY}.geometry")
        if geometry:
            width = geometry.get("width", self.DEFAULT_SIZE[0])
            height = geometry.get("height", self.DEFAULT_SIZE[1])
            x = geometry.get("x")
            y = geometry.get("y")

            # Apply size (respect minimums)
            self.resize(max(width, self.MIN_SIZE[0]), max(height, self.MIN_SIZE[1]))

            # Apply position if saved (Qt/WM handles off-screen)
            if x is not None and y is not None:
                self.move(x, y)

    def save_geometry_to_state(self):
        """Save current window geometry to state."""
        geom = self.geometry()
        self._ui_state.set(
            f"{self.STATE_KEY}.geometry",
            {
                "x": geom.x(),
                "y": geom.y(),
                "width": geom.width(),
                "height": geom.height(),
            },
        )

    def get_section_state(self, section: str, default=False):
        """Get a section's collapsed/wrapped state.

        Args:
            section: Section identifier (e.g., "context", "context_wrapped")
            default: Default value if not found

        Returns:
            The saved state value or default
        """
        key = f"{self.STATE_KEY}.sections.{section}"
        return self._ui_state.get(key, default)

    def save_section_state(self, section: str, value):
        """Save a section's collapsed/wrapped state.

        Args:
            section: Section identifier
            value: State value to save
        """
        key = f"{self.STATE_KEY}.sections.{section}"
        self._ui_state.set(key, value)

    def closeEvent(self, event):
        """Save geometry on close."""
        self.save_geometry_to_state()
        super().closeEvent(event)

    def event(self, event):
        """Handle events to ensure proper focus behavior."""
        if event.type() in (
            QEvent.WindowActivate,
            QEvent.FocusIn,
            QEvent.MouseButtonPress,
        ):
            # Immediate raise
            self.raise_()
            self.activateWindow()
            # Delayed raise to override context menu's focus restoration
            QTimer.singleShot(DIALOG_SHOW_DELAY_MS, self._ensure_focus)
        return super().event(event)

    def _ensure_focus(self):
        """Ensure dialog stays focused after context menu cleanup."""
        if self.isVisible():
            self.raise_()
            self.activateWindow()

    def handle_escape_key(self, event) -> bool:
        """Handle Escape key to close dialog.

        Returns True if the event was handled.
        """
        if event.key() == Qt.Key_Escape:
            self.close()
            return True
        return False
