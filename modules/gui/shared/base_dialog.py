"""Base dialog class with common functionality."""

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from modules.gui.shared.dialog_styles import (
    DEFAULT_DIALOG_SIZE,
    DIALOG_SHOW_DELAY_MS,
    MIN_DIALOG_SIZE,
    SCROLL_CONTENT_MARGINS,
    SCROLL_CONTENT_SPACING,
    get_dialog_stylesheet,
)
from modules.utils.system import on_dialog_close, on_dialog_open
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

    _focus_in_progress = False

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

    def create_scroll_area(self) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
        """Create a standardized scroll area with container.

        Returns:
            Tuple of (scroll_area, container_widget, container_layout)
        """
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(*SCROLL_CONTENT_MARGINS)
        container_layout.setSpacing(SCROLL_CONTENT_SPACING)

        scroll_area.setWidget(container)
        return scroll_area, container, container_layout

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

    def toggle_section_collapsed(
        self,
        section_key: str,
        header,
        content_widgets: QWidget | list[QWidget],
        container: QWidget,
        expanding: bool = True,
    ):
        """Toggle a section's collapsed state with size policy management.

        Args:
            section_key: State key (without _collapsed suffix)
            header: CollapsibleSectionHeader widget
            content_widgets: Widget(s) to show/hide
            container: Section container for size policy
            expanding: If True, use Expanding policy when visible; else Maximum
        """
        widgets = content_widgets if isinstance(content_widgets, list) else [content_widgets]
        is_visible = any(w.isVisible() for w in widgets)

        for widget in widgets:
            widget.setVisible(not is_visible)

        header.set_collapsed(is_visible)

        if is_visible:  # Will be collapsed
            container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        else:  # Will be expanded
            policy = QSizePolicy.Expanding if expanding else QSizePolicy.Maximum
            container.setSizePolicy(QSizePolicy.Preferred, policy)

        self.save_section_state(f"{section_key}_collapsed", is_visible)

    def restore_section_collapsed(
        self,
        section_key: str,
        header,
        content_widgets: QWidget | list[QWidget],
        container: QWidget,
    ) -> bool:
        """Restore a section's collapsed state from saved state.

        Args:
            section_key: State key (without _collapsed suffix)
            header: CollapsibleSectionHeader widget
            content_widgets: Widget(s) to hide if collapsed
            container: Section container for size policy

        Returns:
            True if section was collapsed, False otherwise
        """
        collapsed = self.get_section_state(f"{section_key}_collapsed", False)
        if collapsed:
            widgets = content_widgets if isinstance(content_widgets, list) else [content_widgets]
            for widget in widgets:
                widget.hide()
            header.set_collapsed(True)
            container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        return collapsed

    def showEvent(self, event):
        """Handle show event - activates dock icon on macOS."""
        on_dialog_open()
        super().showEvent(event)

    def closeEvent(self, event):
        """Save geometry on close and hide dock icon if last dialog."""
        self.save_geometry_to_state()
        on_dialog_close()
        super().closeEvent(event)

    def event(self, event):
        """Handle events to ensure proper focus behavior."""
        if event.type() in (
            QEvent.WindowActivate,
            QEvent.FocusIn,
            QEvent.MouseButtonPress,
        ) and not BaseDialog._focus_in_progress:
            BaseDialog._focus_in_progress = True
            self.raise_()
            self.activateWindow()
            QTimer.singleShot(DIALOG_SHOW_DELAY_MS, self._clear_focus_guard)
        return super().event(event)

    def _clear_focus_guard(self):
        """Clear the focus guard after focus operations complete."""
        BaseDialog._focus_in_progress = False
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
