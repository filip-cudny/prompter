"""Context editor dialog for editing context (text and images)."""

import base64
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple
from copy import deepcopy

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QWidget,
    QLabel,
    QPushButton,
    QApplication,
    QScrollArea,
    QFrame,
)
from PyQt5.QtCore import Qt, QTimer, QEvent, pyqtSignal, QByteArray, QBuffer
from PyQt5.QtGui import QFont, QImage

from core.context_manager import ContextManager, ContextItem, ContextItemType
from modules.gui.context_widgets import IconButton

logger = logging.getLogger(__name__)

# Module-level list to keep dialog references alive
_open_dialogs = []


@dataclass
class EditorState:
    """Snapshot of editor state for undo/redo."""
    images: List[ContextItem]
    text: str


def show_context_editor(
    context_manager: ContextManager,
    clipboard_manager,
    notification_manager=None,
):
    """Show the context editor dialog."""
    def create_and_show():
        dialog = ContextEditorDialog(
            context_manager,
            clipboard_manager,
            notification_manager,
        )
        _open_dialogs.append(dialog)
        dialog.finished.connect(
            lambda: _open_dialogs.remove(dialog) if dialog in _open_dialogs else None
        )
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    # Delay to let context menu cleanup finish
    QTimer.singleShot(75, create_and_show)


class ImageChipWidget(QWidget):
    """Chip widget for displaying an image in the editor."""

    delete_requested = pyqtSignal(int)
    copy_requested = pyqtSignal(int)

    # Styles matching ContextChipBase in context_widgets.py
    _chip_style = """
        QWidget#editorChip {
            background-color: #3a3a3a;
            border: 1px solid #555555;
            border-radius: 12px;
            padding: 2px;
        }
        QWidget#editorChip QPushButton {
            background: transparent;
            border: none;
            padding: 2px;
            min-width: 20px;
            max-width: 20px;
            min-height: 20px;
            max-height: 20px;
        }
        QWidget#editorChip QLabel {
            color: #f0f0f0;
            font-size: 12px;
            padding: 2px 4px;
            background: transparent;
        }
    """

    _chip_hover_style = """
        QWidget#editorChip {
            background-color: #454545;
            border: 1px solid #555555;
            border-radius: 12px;
            padding: 2px;
        }
        QWidget#editorChip QPushButton {
            background: transparent;
            border: none;
            padding: 2px;
            min-width: 20px;
            max-width: 20px;
            min-height: 20px;
            max-height: 20px;
        }
        QWidget#editorChip QLabel {
            color: #f0f0f0;
            font-size: 12px;
            padding: 2px 4px;
            background: transparent;
        }
    """

    def __init__(
        self,
        index: int,
        image_number: int,
        image_data: str,
        media_type: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.index = index
        self.image_data = image_data
        self.media_type = media_type

        self.setObjectName("editorChip")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(self._chip_style)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(4)

        # Copy button
        self.copy_btn = IconButton("copy", size=16)
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setToolTip("Copy to clipboard")
        self.copy_btn.clicked.connect(self._on_copy_clicked)
        layout.addWidget(self.copy_btn)

        # Label
        self.label = QLabel(f"[image #{image_number}]")
        layout.addWidget(self.label)

        # Delete button
        self.delete_btn = IconButton("delete", size=16)
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setToolTip("Remove image")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self.delete_btn)

        # Setup tooltip with thumbnail
        self._setup_image_tooltip()

    def _setup_image_tooltip(self):
        """Set up tooltip with image thumbnail."""
        try:
            image_bytes = base64.b64decode(self.image_data)
            image = QImage()
            image.loadFromData(QByteArray(image_bytes))

            if image.isNull():
                self.setToolTip("Image preview unavailable")
                return

            orig_width = image.width()
            orig_height = image.height()

            thumbnail = image.scaled(
                150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

            buffer = QBuffer()
            buffer.open(QBuffer.WriteOnly)
            thumbnail.save(buffer, "PNG")
            thumb_base64 = base64.b64encode(buffer.data()).decode("utf-8")
            buffer.close()

            format_name = self.media_type.split("/")[-1].upper()
            tooltip_html = f"""
                <div style="text-align: center;">
                    <img src="data:image/png;base64,{thumb_base64}" /><br/>
                    <span style="color: #888888; font-size: 11px;">
                        {orig_width} x {orig_height} ({format_name})
                    </span>
                </div>
            """
            self.setToolTip(tooltip_html)
        except Exception as e:
            logger.warning(f"Failed to create image tooltip: {e}")
            self.setToolTip("Image preview unavailable")

    def _on_copy_clicked(self):
        self.copy_requested.emit(self.index)

    def _on_delete_clicked(self):
        self.delete_requested.emit(self.index)

    def copy_to_clipboard(self):
        """Copy image to clipboard."""
        try:
            image_bytes = base64.b64decode(self.image_data)
            image = QImage()
            image.loadFromData(QByteArray(image_bytes))
            if not image.isNull():
                QApplication.clipboard().setImage(image)
        except Exception as e:
            logger.warning(f"Failed to copy image to clipboard: {e}")

    def enterEvent(self, event):
        self.setStyleSheet(self._chip_hover_style)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(self._chip_style)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        # Copy on click (except on buttons)
        if not self.delete_btn.geometry().contains(event.pos()) and \
           not self.copy_btn.geometry().contains(event.pos()):
            self._on_copy_clicked()
        super().mousePressEvent(event)


class ContextEditorDialog(QDialog):
    """Dialog for editing context (text and images)."""

    context_saved = pyqtSignal()

    def __init__(
        self,
        context_manager: ContextManager,
        clipboard_manager,
        notification_manager=None,
        parent=None,
    ):
        super().__init__(parent)
        self.context_manager = context_manager
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager

        # Working state
        self._current_images: List[ContextItem] = []
        self._image_chips: List[ImageChipWidget] = []

        # Undo/redo stacks
        self._undo_stack: List[EditorState] = []
        self._redo_stack: List[EditorState] = []

        self.setWindowTitle("Context Editor")
        self.setMinimumSize(500, 400)
        self.resize(600, 500)
        self.setWindowFlags(Qt.Window)

        self._setup_ui()
        self._apply_styles()
        self._load_context()

        # Install event filter to intercept Ctrl+V on text_edit
        self.text_edit.installEventFilter(self)

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Toolbar with undo/redo
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        self.undo_btn = IconButton("undo", size=18)
        self.undo_btn.setToolTip("Undo (Ctrl+Z)")
        self.undo_btn.clicked.connect(self._undo)
        self.undo_btn.setEnabled(False)
        toolbar.addWidget(self.undo_btn)

        self.redo_btn = IconButton("redo", size=18)
        self.redo_btn.setToolTip("Redo (Ctrl+Shift+Z)")
        self.redo_btn.clicked.connect(self._redo)
        self.redo_btn.setEnabled(False)
        toolbar.addWidget(self.redo_btn)

        paste_hint = QLabel("(Paste image: Cmd/Ctrl+V)")
        paste_hint.setStyleSheet("QLabel { color: #666666; font-size: 11px; }")
        toolbar.addWidget(paste_hint)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Images section (hidden when no images) - simple horizontal layout, no scroll
        self.images_section = QWidget()
        self.images_section.setStyleSheet("background: transparent;")
        self.images_layout = QHBoxLayout(self.images_section)
        self.images_layout.setContentsMargins(0, 0, 0, 0)
        self.images_layout.setSpacing(6)
        self.images_layout.addStretch()

        layout.addWidget(self.images_section)
        self.images_section.hide()  # Hidden by default

        # Text section
        text_label = QLabel("Text:")
        text_label.setStyleSheet("QLabel { color: #888888; font-size: 11px; font-weight: bold; }")
        layout.addWidget(text_label)

        self.text_edit = QTextEdit()
        self.text_edit.setFont(QFont("Menlo, Monaco, Consolas, monospace", 12))
        self.text_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        self.text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.text_edit)

        # Button bar
        button_bar = QHBoxLayout()
        button_bar.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_bar.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._on_save_clicked)
        save_btn.setDefault(True)
        button_bar.addWidget(save_btn)

        layout.addLayout(button_bar)

        # Track text changes for undo
        self._last_text = ""
        self._text_change_timer = QTimer()
        self._text_change_timer.setSingleShot(True)
        self._text_change_timer.setInterval(500)
        self._text_change_timer.timeout.connect(self._save_text_state)

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
                selection-background-color: #3d6a99;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: #f0f0f0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 12px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #454545;
            }
            QPushButton:pressed {
                background-color: #505050;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666666;
            }
            QScrollArea {
                background: transparent;
                border: none;
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
        """)

    def _load_context(self):
        """Load current context into the dialog."""
        items = self.context_manager.get_items()

        # Separate images and text
        self._current_images = [
            ContextItem(
                item_type=item.item_type,
                data=item.data,
                media_type=item.media_type,
            )
            for item in items
            if item.item_type == ContextItemType.IMAGE
        ]

        text_items = [
            item.content
            for item in items
            if item.item_type == ContextItemType.TEXT and item.content
        ]
        text_content = "\n".join(text_items)

        self._rebuild_image_chips()
        self.text_edit.setPlainText(text_content)
        self._last_text = text_content

        # Clear undo/redo stacks
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._update_undo_redo_buttons()

    def _rebuild_image_chips(self):
        """Rebuild the image chips from current state."""
        # Clear existing chips
        for chip in self._image_chips:
            chip.deleteLater()
        self._image_chips.clear()

        # Remove all items from layout
        while self.images_layout.count():
            self.images_layout.takeAt(0)

        if not self._current_images:
            self.images_section.hide()
            return

        self.images_section.show()

        for idx, item in enumerate(self._current_images):
            chip = ImageChipWidget(
                index=idx,
                image_number=idx + 1,
                image_data=item.data or "",
                media_type=item.media_type or "image/png",
            )
            chip.delete_requested.connect(self._on_image_delete)
            chip.copy_requested.connect(self._on_image_copy)
            self._image_chips.append(chip)
            self.images_layout.addWidget(chip)

        self.images_layout.addStretch()

    def _get_current_state(self) -> EditorState:
        """Get current editor state."""
        return EditorState(
            images=[
                ContextItem(
                    item_type=item.item_type,
                    data=item.data,
                    media_type=item.media_type,
                )
                for item in self._current_images
            ],
            text=self.text_edit.toPlainText(),
        )

    def _restore_state(self, state: EditorState):
        """Restore editor state."""
        self._current_images = [
            ContextItem(
                item_type=item.item_type,
                data=item.data,
                media_type=item.media_type,
            )
            for item in state.images
        ]
        self._rebuild_image_chips()

        # Block signal to prevent recursive undo state saving
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(state.text)
        self._last_text = state.text
        self.text_edit.blockSignals(False)

    def _save_state(self):
        """Save current state to undo stack."""
        state = self._get_current_state()
        self._undo_stack.append(state)
        self._redo_stack.clear()
        self._update_undo_redo_buttons()

    def _save_text_state(self):
        """Save state if text has significantly changed."""
        current_text = self.text_edit.toPlainText()
        if current_text != self._last_text:
            # Save state with previous text
            state = EditorState(
                images=[
                    ContextItem(
                        item_type=item.item_type,
                        data=item.data,
                        media_type=item.media_type,
                    )
                    for item in self._current_images
                ],
                text=self._last_text,
            )
            self._undo_stack.append(state)
            self._redo_stack.clear()
            self._last_text = current_text
            self._update_undo_redo_buttons()

    def _undo(self):
        """Undo last change."""
        if not self._undo_stack:
            return

        # Save current state to redo stack
        self._redo_stack.append(self._get_current_state())

        # Restore previous state
        state = self._undo_stack.pop()
        self._restore_state(state)
        self._update_undo_redo_buttons()

    def _redo(self):
        """Redo last undone change."""
        if not self._redo_stack:
            return

        # Save current state to undo stack
        self._undo_stack.append(self._get_current_state())

        # Restore redo state
        state = self._redo_stack.pop()
        self._restore_state(state)
        self._update_undo_redo_buttons()

    def _update_undo_redo_buttons(self):
        """Update undo/redo button states."""
        self.undo_btn.setEnabled(len(self._undo_stack) > 0)
        self.redo_btn.setEnabled(len(self._redo_stack) > 0)

    def _on_text_changed(self):
        """Handle text changes - debounce state saving."""
        self._text_change_timer.start()

    def _on_image_delete(self, index: int):
        """Handle image chip delete request."""
        if 0 <= index < len(self._current_images):
            self._save_state()
            del self._current_images[index]
            self._rebuild_image_chips()

    def _on_image_copy(self, index: int):
        """Handle image chip copy request."""
        if 0 <= index < len(self._image_chips):
            self._image_chips[index].copy_to_clipboard()
            if self.notification_manager:
                self.notification_manager.show_success_notification("Copied")

    def _paste_image_from_clipboard(self) -> bool:
        """Paste image from clipboard. Returns True if image was pasted."""
        if not self.clipboard_manager.has_image():
            return False

        image_data = self.clipboard_manager.get_image_data()
        if image_data:
            base64_data, media_type = image_data
            self._save_state()
            new_image = ContextItem(
                item_type=ContextItemType.IMAGE,
                data=base64_data,
                media_type=media_type,
            )
            self._current_images.append(new_image)
            self._rebuild_image_chips()

            if self.notification_manager:
                self.notification_manager.show_success_notification("Image added")
            return True
        return False

    def _on_save_clicked(self):
        """Save changes to ContextManager."""
        self.context_manager.clear_context()

        # Add images first
        for image_item in self._current_images:
            self.context_manager.append_context_image(
                image_item.data,
                image_item.media_type or "image/png",
            )

        # Add text if not empty
        text_content = self.text_edit.toPlainText().strip()
        if text_content:
            self.context_manager.append_context(text_content)

        self.context_saved.emit()
        self.accept()

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

        # Ctrl+V for paste image (always try if clipboard has image)
        if event.key() == Qt.Key_V and (event.modifiers() & Qt.ControlModifier):
            if self.clipboard_manager.has_image():
                self._paste_image_from_clipboard()
                event.accept()
                return

        # Escape to close
        if event.key() == Qt.Key_Escape:
            self.close()
            return

        super().keyPressEvent(event)

    def event(self, event):
        """Handle events to ensure proper focus behavior."""
        if event.type() in (QEvent.WindowActivate, QEvent.FocusIn, QEvent.MouseButtonPress):
            self.raise_()
            self.activateWindow()
            QTimer.singleShot(75, self._ensure_focus)
        return super().event(event)

    def eventFilter(self, obj, event):
        """Filter events to intercept Ctrl+V on text_edit when clipboard has image."""
        if obj == self.text_edit and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_V and (event.modifiers() & Qt.ControlModifier):
                if self.clipboard_manager.has_image():
                    self._paste_image_from_clipboard()
                    return True  # Event handled, don't pass to text_edit
        return super().eventFilter(obj, event)

    def _ensure_focus(self):
        """Ensure dialog stays focused after context menu cleanup."""
        if self.isVisible():
            self.raise_()
            self.activateWindow()
