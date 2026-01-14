"""Shared widgets for GUI dialogs."""

import base64
import logging
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QApplication,
)
from PyQt5.QtCore import Qt, pyqtSignal, QByteArray, QBuffer
from PyQt5.QtGui import QImage

from modules.gui.context_widgets import IconButton
from modules.gui.icons import ICON_COLOR_NORMAL

logger = logging.getLogger(__name__)

# Transparent button style (no border, no background)
ICON_BTN_STYLE = """
    QPushButton {
        background: transparent;
        border: none;
        padding: 2px;
        min-width: 0px;
        max-width: 24px;
    }
"""


class CollapsibleSectionHeader(QWidget):
    """Header widget for collapsible sections with title, collapse toggle, and optional buttons."""

    toggle_requested = pyqtSignal()
    save_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()
    delete_requested = pyqtSignal()

    def __init__(
        self,
        title: str,
        show_save_button: bool = True,
        show_undo_redo: bool = False,
        show_delete_button: bool = False,
        hint_text: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._collapsed = False
        self._title = title

        # Ensure transparent background
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 12, 4)  # 12px right margin for alignment
        layout.setSpacing(4)

        # Collapse toggle button FIRST (left side)
        self.toggle_btn = IconButton("chevron-down", size=16)
        self.toggle_btn.setToolTip("Collapse section")
        # Remove padding so chevron aligns with text edit border
        self.toggle_btn.setStyleSheet("QPushButton { background: transparent; border: none; padding: 0px; }")
        self.toggle_btn.clicked.connect(lambda: self.toggle_requested.emit())
        layout.addWidget(self.toggle_btn)

        # Title label after chevron
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            "QLabel { color: #888888; font-size: 11px; font-weight: bold; }"
        )
        layout.addWidget(self.title_label)

        # Optional hint text (e.g., "Paste image: Ctrl+V")
        if hint_text:
            hint_label = QLabel(hint_text)
            hint_label.setStyleSheet("QLabel { color: #666666; font-size: 11px; }")
            layout.addWidget(hint_label)

        layout.addStretch()

        # Button container for tighter spacing
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(2)

        # Undo/redo buttons (optional)
        self.undo_btn = None
        self.redo_btn = None
        if show_undo_redo:
            self.undo_btn = IconButton("undo", size=16)
            self.undo_btn.setToolTip("Undo (Ctrl+Z)")
            self.undo_btn.setStyleSheet(ICON_BTN_STYLE)
            self.undo_btn.clicked.connect(lambda: self.undo_requested.emit())
            self.undo_btn.setEnabled(False)
            btn_layout.addWidget(self.undo_btn)

            self.redo_btn = IconButton("redo", size=16)
            self.redo_btn.setToolTip("Redo (Ctrl+Shift+Z)")
            self.redo_btn.setStyleSheet(ICON_BTN_STYLE)
            self.redo_btn.clicked.connect(lambda: self.redo_requested.emit())
            self.redo_btn.setEnabled(False)
            btn_layout.addWidget(self.redo_btn)

        # Delete button (optional) - for removing sections
        self.delete_btn = None
        if show_delete_button:
            self.delete_btn = IconButton("delete", size=16)
            self.delete_btn.setToolTip("Delete this section")
            self.delete_btn.setStyleSheet(ICON_BTN_STYLE)
            self.delete_btn.clicked.connect(lambda: self.delete_requested.emit())
            btn_layout.addWidget(self.delete_btn)

        # Save button (optional) - icon only, no border, on right side
        self.save_btn = None
        if show_save_button:
            self.save_btn = IconButton("save", size=16)
            self.save_btn.setToolTip(f"Save {title.lower()}")
            self.save_btn.setStyleSheet(ICON_BTN_STYLE)
            self.save_btn.clicked.connect(lambda: self.save_requested.emit())
            btn_layout.addWidget(self.save_btn)

        layout.addWidget(btn_container)

    def set_collapsed(self, collapsed: bool):
        """Update the visual state of the toggle button."""
        self._collapsed = collapsed
        icon_name = "chevron-right" if collapsed else "chevron-down"
        self.toggle_btn._icon_name = icon_name
        self.toggle_btn._update_icon(ICON_COLOR_NORMAL)
        self.toggle_btn.setToolTip(
            "Expand section" if collapsed else "Collapse section"
        )

    def set_undo_redo_enabled(self, can_undo: bool, can_redo: bool):
        """Update undo/redo button enabled states."""
        if self.undo_btn:
            self.undo_btn.setEnabled(can_undo)
        if self.redo_btn:
            self.redo_btn.setEnabled(can_redo)

    def set_delete_button_visible(self, visible: bool):
        """Show or hide the delete button."""
        if self.delete_btn:
            self.delete_btn.setVisible(visible)


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
                300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation
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
        if not self.delete_btn.geometry().contains(
            event.pos()
        ) and not self.copy_btn.geometry().contains(event.pos()):
            self._on_copy_clicked()
        super().mousePressEvent(event)
