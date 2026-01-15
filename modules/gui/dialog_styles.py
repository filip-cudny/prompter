"""Shared dialog styling constants and functions."""

from typing import Callable, Dict, Optional, TypeVar

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QDialog

# Timing constants
DIALOG_SHOW_DELAY_MS = 75
TEXT_CHANGE_DEBOUNCE_MS = 500

# Layout constants
DEFAULT_WRAPPED_HEIGHT = 300
QWIDGETSIZE_MAX = 16777215

# Window size defaults
DEFAULT_DIALOG_SIZE = (600, 500)
MIN_DIALOG_SIZE = (500, 400)
SMALL_DIALOG_SIZE = (600, 400)
SMALL_MIN_DIALOG_SIZE = (400, 300)

# Colors
COLOR_DIALOG_BG = "#2b2b2b"
COLOR_TEXT_EDIT_BG = "#1e1e1e"
COLOR_TEXT = "#f0f0f0"
COLOR_BORDER = "#555555"
COLOR_BUTTON_BG = "#3a3a3a"
COLOR_BUTTON_HOVER = "#454545"
COLOR_BUTTON_PRESSED = "#505050"
COLOR_BUTTON_DISABLED_BG = "#2a2a2a"
COLOR_BUTTON_DISABLED_TEXT = "#444444"
COLOR_SELECTION = "#3d6a99"
COLOR_SCROLLBAR_HANDLE = "#555555"
COLOR_SCROLLBAR_HANDLE_HOVER = "#666666"

# Tooltip colors
COLOR_TOOLTIP_BG = "#0d0d0d"
COLOR_TOOLTIP_BORDER = "#444444"

# Dark theme tooltip style - single source of truth for all tooltips
TOOLTIP_STYLE = f"""
    QToolTip {{
        background-color: {COLOR_TOOLTIP_BG};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_TOOLTIP_BORDER};
        border-radius: 2px;
        padding: 2px 2px;
    }}
"""

# Complete dialog stylesheet
DIALOG_STYLESHEET = f"""
    QDialog {{
        background-color: {COLOR_DIALOG_BG};
        color: {COLOR_TEXT};
    }}
    QTextEdit {{
        background-color: {COLOR_TEXT_EDIT_BG};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 8px;
        selection-background-color: {COLOR_SELECTION};
    }}
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
    QPushButton:pressed {{
        background-color: {COLOR_BUTTON_PRESSED};
    }}
    QPushButton:disabled {{
        background-color: {COLOR_BUTTON_DISABLED_BG};
        color: {COLOR_BUTTON_DISABLED_TEXT};
    }}
    QScrollBar:vertical {{
        background-color: {COLOR_DIALOG_BG};
        width: 12px;
        border-radius: 6px;
    }}
    QScrollBar::handle:vertical {{
        background-color: {COLOR_SCROLLBAR_HANDLE};
        border-radius: 6px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {COLOR_SCROLLBAR_HANDLE_HOVER};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background-color: {COLOR_DIALOG_BG};
        height: 12px;
        border-radius: 6px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {COLOR_SCROLLBAR_HANDLE};
        border-radius: 6px;
        min-width: 20px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {COLOR_SCROLLBAR_HANDLE_HOVER};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    QScrollArea {{
        background: transparent;
        border: none;
    }}
    QScrollArea > QWidget > QWidget {{
        background-color: {COLOR_DIALOG_BG};
    }}
"""


def get_dialog_stylesheet() -> str:
    """Return complete dialog stylesheet with tooltip style."""
    return DIALOG_STYLESHEET + TOOLTIP_STYLE


def get_text_edit_content_height(text_edit, min_height: int = 100) -> int:
    """Calculate the height needed to display all content without scrolling.

    Args:
        text_edit: The QTextEdit widget
        min_height: Minimum height to return (default: 100)

    Returns:
        Height in pixels needed to display all content
    """
    doc = text_edit.document()
    doc.setTextWidth(text_edit.viewport().width())
    margins = text_edit.contentsMargins()
    height = int(doc.size().height()) + margins.top() + margins.bottom() + 20
    return max(height, min_height)


def apply_wrap_state(
    text_edit, is_wrapped: bool, wrapped_height: int = DEFAULT_WRAPPED_HEIGHT
):
    """Apply wrap state to a text edit widget.

    This is the shared implementation for wrap/expand toggling across all dialogs.

    Args:
        text_edit: The QTextEdit widget to modify
        is_wrapped: True to wrap (limit height), False to expand
        wrapped_height: Maximum height when wrapped (default: DEFAULT_WRAPPED_HEIGHT)
    """
    if is_wrapped:
        text_edit.setMinimumHeight(0)
        text_edit.setMaximumHeight(wrapped_height)
    else:
        content_height = get_text_edit_content_height(text_edit)
        text_edit.setMinimumHeight(content_height)
        text_edit.setMaximumHeight(QWIDGETSIZE_MAX)


# Dialog singleton management
T = TypeVar("T", bound=QDialog)


def create_singleton_dialog_manager() -> Callable:
    """Create a singleton dialog manager for preventing duplicate windows.

    Returns a function that manages dialog creation and visibility.

    Usage:
        _show_dialog = create_singleton_dialog_manager()

        def show_my_dialog(...):
            _show_dialog("my_dialog", lambda: MyDialog(...))
    """
    _dialogs: Dict[str, QDialog] = {}

    def show_dialog(
        key: str,
        create_fn: Callable[[], T],
        delay_ms: int = DIALOG_SHOW_DELAY_MS,
    ) -> Optional[T]:
        """Show a singleton dialog, bringing existing one to front if open.

        Args:
            key: Unique identifier for this dialog type/instance
            create_fn: Factory function to create the dialog
            delay_ms: Delay before creating dialog (for menu cleanup)

        Returns:
            None (dialog is shown asynchronously)
        """
        if key in _dialogs:
            dialog = _dialogs[key]
            dialog.raise_()
            dialog.activateWindow()
            return None

        def create_and_show():
            if key in _dialogs:
                _dialogs[key].raise_()
                _dialogs[key].activateWindow()
                return

            dialog = create_fn()
            _dialogs[key] = dialog
            dialog.finished.connect(lambda: _dialogs.pop(key, None))
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()

        QTimer.singleShot(delay_ms, create_and_show)
        return None

    return show_dialog
