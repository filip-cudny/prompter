"""Standalone undo/redo functions for GUI components."""

from collections.abc import Callable
from typing import TypeVar

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QTextEdit

T = TypeVar("T")


def perform_undo(
    undo_stack: list[T],
    redo_stack: list[T],
    get_current_state: Callable[[], T],
    restore_state: Callable[[T], None],
) -> T | None:
    """Perform undo operation.

    Args:
        undo_stack: Stack of previous states
        redo_stack: Stack of undone states
        get_current_state: Function to get current state
        restore_state: Function to restore a state

    Returns:
        Restored state or None if nothing to undo
    """
    if not undo_stack:
        return None
    redo_stack.append(get_current_state())
    state = undo_stack.pop()
    restore_state(state)
    return state


def perform_redo(
    undo_stack: list[T],
    redo_stack: list[T],
    get_current_state: Callable[[], T],
    restore_state: Callable[[T], None],
) -> T | None:
    """Perform redo operation.

    Args:
        undo_stack: Stack of previous states
        redo_stack: Stack of undone states
        get_current_state: Function to get current state
        restore_state: Function to restore a state

    Returns:
        Restored state or None if nothing to redo
    """
    if not redo_stack:
        return None
    undo_stack.append(get_current_state())
    state = redo_stack.pop()
    restore_state(state)
    return state


def save_state_if_changed(
    current_value: str,
    last_value: str,
    undo_stack: list[T],
    redo_stack: list[T],
    create_state: Callable[[str], T],
) -> str:
    """Save state if value changed.

    Args:
        current_value: Current text value
        last_value: Previously saved text value
        undo_stack: Stack of previous states
        redo_stack: Stack of undone states (will be cleared)
        create_state: Function to create state from text

    Returns:
        New last_value (current_value if changed, else original last_value)
    """
    if current_value != last_value:
        undo_stack.append(create_state(last_value))
        redo_stack.clear()
        return current_value
    return last_value


def set_text_with_signal_block(text_edit: QTextEdit, text: str) -> str:
    """Set text on QTextEdit while blocking signals.

    Args:
        text_edit: The QTextEdit widget
        text: Text to set

    Returns:
        The text that was set
    """
    text_edit.blockSignals(True)
    text_edit.setPlainText(text)
    text_edit.blockSignals(False)
    return text


class TextEditUndoHelper:
    """Helper for managing undo/redo on a QTextEdit with debouncing.

    This class encapsulates the common undo/redo pattern used across
    dialogs with text editing. It handles:
    - Debounced state saving to avoid excessive undo points
    - Signal blocking during state restoration
    - Button state updates via callback

    Usage:
        def on_buttons_changed(can_undo: bool, can_redo: bool):
            self.undo_btn.setEnabled(can_undo)
            self.redo_btn.setEnabled(can_redo)

        self._undo_helper = TextEditUndoHelper(
            self.text_edit,
            on_buttons_changed,
        )
        self._undo_helper.initialize(initial_text)
        self.text_edit.textChanged.connect(self._undo_helper.schedule_save)
    """

    def __init__(
        self,
        text_edit: QTextEdit,
        on_buttons_changed: Callable[[bool, bool], None],
        debounce_ms: int = 500,
    ):
        """Create a text edit undo helper.

        Args:
            text_edit: The QTextEdit to manage
            on_buttons_changed: Callback with (can_undo, can_redo)
            debounce_ms: Milliseconds to debounce state saves
        """
        self._text_edit = text_edit
        self._on_buttons_changed = on_buttons_changed
        self._undo_stack: list[str] = []
        self._redo_stack: list[str] = []
        self._last_text: str = ""

        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self._save_if_changed)

    def initialize(self, text: str = ""):
        """Initialize with given text or current text edit content.

        Args:
            text: Initial text (if empty, uses current text edit content)
        """
        self._last_text = text if text else self._text_edit.toPlainText()
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._notify_buttons_changed()

    def schedule_save(self):
        """Schedule a debounced state save. Call on text changes."""
        self._timer.start()

    def _save_if_changed(self):
        """Save state if text has changed (called by timer)."""
        current = self._text_edit.toPlainText()
        if current != self._last_text:
            self._undo_stack.append(self._last_text)
            self._redo_stack.clear()
            self._last_text = current
            self._notify_buttons_changed()

    def undo(self) -> bool:
        """Undo last change.

        Returns:
            True if undo was performed, False if nothing to undo
        """
        if not self._undo_stack:
            return False
        self._redo_stack.append(self._text_edit.toPlainText())
        self._last_text = set_text_with_signal_block(
            self._text_edit, self._undo_stack.pop()
        )
        self._notify_buttons_changed()
        return True

    def redo(self) -> bool:
        """Redo last undone change.

        Returns:
            True if redo was performed, False if nothing to redo
        """
        if not self._redo_stack:
            return False
        self._undo_stack.append(self._text_edit.toPlainText())
        self._last_text = set_text_with_signal_block(
            self._text_edit, self._redo_stack.pop()
        )
        self._notify_buttons_changed()
        return True

    def _notify_buttons_changed(self):
        """Notify listener of button state change."""
        self._on_buttons_changed(bool(self._undo_stack), bool(self._redo_stack))

    def clear(self):
        """Clear all undo/redo history."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._last_text = self._text_edit.toPlainText()
        self._notify_buttons_changed()

    @property
    def last_text(self) -> str:
        """Get the last saved text value."""
        return self._last_text

    @last_text.setter
    def last_text(self, value: str):
        """Set the last saved text value."""
        self._last_text = value

    @property
    def undo_stack(self) -> list[str]:
        """Get the undo stack (for advanced use cases)."""
        return self._undo_stack

    @property
    def redo_stack(self) -> list[str]:
        """Get the redo stack (for advanced use cases)."""
        return self._redo_stack

    @property
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return bool(self._redo_stack)
