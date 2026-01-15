"""Text preview dialog for displaying and editing content."""

from typing import List, Optional

from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QApplication, QScrollArea, QFrame, QWidget
from PyQt5.QtCore import Qt, QTimer

from modules.gui.base_dialog import BaseDialog
from modules.gui.context_widgets import IconButton
from modules.gui.dialog_styles import (
    DEFAULT_WRAPPED_HEIGHT,
    DIALOG_SHOW_DELAY_MS,
    QWIDGETSIZE_MAX,
    SMALL_DIALOG_SIZE,
    SMALL_MIN_DIALOG_SIZE,
    apply_wrap_state,
    create_singleton_dialog_manager,
)
from modules.gui.shared_widgets import create_text_edit, TOOLTIP_STYLE
from core.interfaces import ClipboardManager

# Singleton dialog manager for this module
_show_dialog = create_singleton_dialog_manager()

_icon_btn_style = """
    QPushButton {
        background: transparent;
        border: none;
        padding: 2px;
    }
""" + TOOLTIP_STYLE


def show_preview_dialog(
    title: str,
    content: str,
    clipboard_manager: Optional[ClipboardManager] = None,
):
    """Show a preview dialog with the given title and content. If already open, bring to front."""
    _show_dialog(
        "text_preview",
        lambda: TextPreviewDialog(title, content, clipboard_manager=clipboard_manager),
    )


class TextPreviewDialog(BaseDialog):
    """Dialog for displaying and editing text content with undo/redo support."""

    STATE_KEY = "text_preview_dialog"
    DEFAULT_SIZE = SMALL_DIALOG_SIZE
    MIN_SIZE = SMALL_MIN_DIALOG_SIZE

    def __init__(
        self,
        title: str,
        content: str,
        parent=None,
        clipboard_manager: Optional[ClipboardManager] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)

        self._clipboard_manager = clipboard_manager

        # Undo/redo state
        self._undo_stack: List[str] = []
        self._redo_stack: List[str] = []
        self._last_text: str = content or ""
        self._wrapped: bool = True  # Default wrapped state

        # Debounce timer for text changes
        self._text_change_timer = QTimer()
        self._text_change_timer.setSingleShot(True)
        self._text_change_timer.setInterval(100)
        self._text_change_timer.timeout.connect(self._save_text_state)

        self._setup_ui(content)
        self.apply_dialog_styles()
        self._restore_state()

    def _setup_ui(self, content: str):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 0, 10)  # No right margin for scrollbar
        layout.setSpacing(8)

        # Scroll area for content
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        # Container for content
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 14, 0)  # Right margin for scrollbar
        content_layout.setSpacing(8)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(2)
        toolbar.addStretch()

        # Wrap toggle button (before undo/redo)
        self.wrap_btn = IconButton("chevrons-down-up", size=18)
        self.wrap_btn.setToolTip("Toggle wrap/expand")
        self.wrap_btn.setStyleSheet(_icon_btn_style)
        self.wrap_btn.clicked.connect(self._toggle_wrap)
        toolbar.addWidget(self.wrap_btn)

        self.undo_btn = IconButton("undo", size=18)
        self.undo_btn.setToolTip("Undo (Ctrl+Z)")
        self.undo_btn.setStyleSheet(_icon_btn_style)
        self.undo_btn.clicked.connect(self._undo)
        self.undo_btn.setEnabled(False)
        toolbar.addWidget(self.undo_btn)

        self.redo_btn = IconButton("redo", size=18)
        self.redo_btn.setToolTip("Redo (Ctrl+Shift+Z)")
        self.redo_btn.setStyleSheet(_icon_btn_style)
        self.redo_btn.clicked.connect(self._redo)
        self.redo_btn.setEnabled(False)
        toolbar.addWidget(self.redo_btn)

        self.copy_btn = IconButton("copy", size=18)
        self.copy_btn.setToolTip("Copy all (Ctrl+Shift+C)")
        self.copy_btn.setStyleSheet(_icon_btn_style)
        self.copy_btn.clicked.connect(self._copy_all)
        toolbar.addWidget(self.copy_btn)

        content_layout.addLayout(toolbar)

        # Editable text area
        self.text_edit = create_text_edit(min_height=0)
        self.text_edit.setPlainText(content or "")
        self.text_edit.textChanged.connect(self._on_text_changed)
        self.text_edit.setMaximumHeight(DEFAULT_WRAPPED_HEIGHT)  # Default wrapped height
        content_layout.addWidget(self.text_edit)

        self.scroll_area.setWidget(content_container)
        layout.addWidget(self.scroll_area)

    def _restore_state(self):
        """Restore window geometry and wrap state."""
        self.restore_geometry_from_state()

        # Restore wrap state
        wrapped = self.get_section_state("wrapped", True)
        self._wrapped = wrapped
        apply_wrap_state(self.text_edit, wrapped)
        if not wrapped:
            self.wrap_btn.set_icon("chevrons-up-down")

    def closeEvent(self, event):
        """Save geometry on close."""
        self.save_geometry_to_state()
        super().closeEvent(event)

    def _on_text_changed(self):
        """Handle text changes - debounce state saving."""
        self._text_change_timer.start()

    def _save_text_state(self):
        """Save state if text has changed."""
        current_text = self.text_edit.toPlainText()
        if current_text != self._last_text:
            self._undo_stack.append(self._last_text)
            self._redo_stack.clear()
            self._last_text = current_text
            self._update_undo_redo_buttons()

    def _undo(self):
        """Undo last change."""
        if not self._undo_stack:
            return

        # Save current state to redo stack
        self._redo_stack.append(self.text_edit.toPlainText())

        # Restore previous state
        previous_text = self._undo_stack.pop()
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(previous_text)
        self._last_text = previous_text
        self.text_edit.blockSignals(False)
        self._update_undo_redo_buttons()

    def _redo(self):
        """Redo last undone change."""
        if not self._redo_stack:
            return

        # Save current state to undo stack
        self._undo_stack.append(self.text_edit.toPlainText())

        # Restore redo state
        redo_text = self._redo_stack.pop()
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(redo_text)
        self._last_text = redo_text
        self.text_edit.blockSignals(False)
        self._update_undo_redo_buttons()

    def _update_undo_redo_buttons(self):
        """Update undo/redo button states."""
        self.undo_btn.setEnabled(len(self._undo_stack) > 0)
        self.redo_btn.setEnabled(len(self._redo_stack) > 0)

    def _toggle_wrap(self):
        """Toggle wrap/expand state."""
        self._wrapped = not self._wrapped
        apply_wrap_state(self.text_edit, self._wrapped)
        icon_name = "chevrons-down-up" if self._wrapped else "chevrons-up-down"
        self.wrap_btn.set_icon(icon_name)
        self.save_section_state("wrapped", self._wrapped)

    def _copy_all(self):
        """Copy all text content to clipboard."""
        text = self.text_edit.toPlainText()
        if text:
            if self._clipboard_manager:
                # Use xclip/xsel to avoid X11 clipboard ownership issues
                self._clipboard_manager.set_content(text)
            else:
                QApplication.clipboard().setText(text)

    def keyPressEvent(self, event):
        """Handle key press events."""
        # Ctrl+Z for undo
        if event.key() == Qt.Key_Z and (event.modifiers() & Qt.ControlModifier):
            if event.modifiers() & Qt.ShiftModifier:
                # Ctrl+Shift+Z for redo
                self._redo()
            else:
                # Ctrl+Z for undo
                self._undo()
            event.accept()
            return

        # Ctrl+Y for redo (alternative)
        if event.key() == Qt.Key_Y and (event.modifiers() & Qt.ControlModifier):
            self._redo()
            event.accept()
            return

        # Ctrl+C for copy (use xclip to avoid X11 clipboard ownership freeze)
        if (
            event.key() == Qt.Key_C
            and (event.modifiers() & Qt.ControlModifier)
            and not (event.modifiers() & Qt.ShiftModifier)
        ):
            if self._clipboard_manager:
                selected_text = self.text_edit.textCursor().selectedText()
                if selected_text:
                    # Replace paragraph separators with newlines
                    selected_text = selected_text.replace('\u2029', '\n')
                    self._clipboard_manager.set_content(selected_text)
                    event.accept()
                    return
            # Fall through to default Qt handling if no clipboard_manager or no selection

        # Ctrl+Shift+C for copy all
        if (
            event.key() == Qt.Key_C
            and (event.modifiers() & Qt.ControlModifier)
            and (event.modifiers() & Qt.ShiftModifier)
        ):
            self._copy_all()
            event.accept()
            return

        # Escape to close
        if self.handle_escape_key(event):
            return

        super().keyPressEvent(event)
