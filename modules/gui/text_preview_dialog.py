"""Text preview dialog for displaying and editing content."""

from typing import List, Optional

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QApplication
from PyQt5.QtCore import Qt, QTimer, QEvent

from modules.gui.context_widgets import IconButton
from modules.gui.shared_widgets import create_text_edit, TOOLTIP_STYLE
from modules.utils.ui_state import UIStateManager
from core.interfaces import ClipboardManager

_open_dialogs = []

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
    if _open_dialogs:
        dialog = _open_dialogs[0]
        dialog.raise_()
        dialog.activateWindow()
        return

    def create_and_show():
        if _open_dialogs:
            _open_dialogs[0].raise_()
            _open_dialogs[0].activateWindow()
            return
        dialog = TextPreviewDialog(title, content, clipboard_manager=clipboard_manager)
        _open_dialogs.append(dialog)
        dialog.finished.connect(
            lambda: _open_dialogs.remove(dialog) if dialog in _open_dialogs else None
        )
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    # Delay to let context menu cleanup finish
    QTimer.singleShot(75, create_and_show)


class TextPreviewDialog(QDialog):
    """Dialog for displaying and editing text content with undo/redo support."""

    def __init__(
        self,
        title: str,
        content: str,
        parent=None,
        clipboard_manager: Optional[ClipboardManager] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(400, 300)
        self.resize(600, 400)
        self.setWindowFlags(Qt.Window)

        self._ui_state = UIStateManager()
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
        self._apply_styles()
        self._restore_geometry()

    def _setup_ui(self, content: str):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

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

        layout.addLayout(toolbar)

        # Editable text area
        self.text_edit = create_text_edit(min_height=0)
        self.text_edit.setPlainText(content or "")
        self.text_edit.textChanged.connect(self._on_text_changed)
        self.text_edit.setMaximumHeight(300)  # Default wrapped height

        layout.addWidget(self.text_edit)

    def _apply_styles(self):
        """Apply dark theme styling."""
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #f0f0f0;
            }
            QTextEdit {
                background-color: #1e1e1e;
                color: #f0f0f0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 12px;
                padding-right: 24px;
                selection-background-color: #3d6a99;
            }
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #666666;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background-color: #2b2b2b;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background-color: #555555;
                border-radius: 6px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #666666;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """
            + TOOLTIP_STYLE
        )

    def _restore_geometry(self):
        """Restore window geometry and wrap state."""
        geometry = self._ui_state.get("text_preview_dialog.geometry")
        if geometry:
            width = geometry.get("width", 600)
            height = geometry.get("height", 400)
            x = geometry.get("x")
            y = geometry.get("y")

            # Apply size (respect minimums)
            self.resize(max(width, 400), max(height, 300))

            # Apply position if saved (Qt/WM handles off-screen)
            if x is not None and y is not None:
                self.move(x, y)

        # Restore wrap state
        wrapped = self._ui_state.get("text_preview_dialog.wrapped", True)
        self._wrapped = wrapped
        if not wrapped:
            self.text_edit.setMaximumHeight(16777215)
            self.wrap_btn.set_icon("chevrons-up-down")

    def closeEvent(self, event):
        """Save geometry on close."""
        geom = self.geometry()
        self._ui_state.set(
            "text_preview_dialog.geometry",
            {
                "x": geom.x(),
                "y": geom.y(),
                "width": geom.width(),
                "height": geom.height(),
            },
        )
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
        if self._wrapped:
            self.text_edit.setMaximumHeight(300)
            self.wrap_btn.set_icon("chevrons-down-up")
        else:
            self.text_edit.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
            self.wrap_btn.set_icon("chevrons-up-down")
        self._ui_state.set("text_preview_dialog.wrapped", self._wrapped)

    def _copy_all(self):
        """Copy all text content to clipboard."""
        text = self.text_edit.toPlainText()
        if text:
            if self._clipboard_manager:
                # Use xclip/xsel to avoid X11 clipboard ownership issues
                self._clipboard_manager.set_content(text)
            else:
                QApplication.clipboard().setText(text)

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
            QTimer.singleShot(75, self._ensure_focus)
        return super().event(event)

    def _ensure_focus(self):
        """Ensure dialog stays focused after context menu cleanup."""
        if self.isVisible():
            self.raise_()
            self.activateWindow()

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
        if event.key() == Qt.Key_Escape:
            self.close()
            return

        super().keyPressEvent(event)
