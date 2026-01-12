"""Context editor dialog for editing context (text and images) and clipboard."""

import base64
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QWidget,
    QLabel,
    QPushButton,
    QApplication,
    QSplitter,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer, QEvent, pyqtSignal, QByteArray, QBuffer
from PyQt5.QtGui import QFont, QImage

from core.context_manager import ContextManager, ContextItem, ContextItemType
from modules.gui.context_widgets import IconButton
from modules.gui.icons import ICON_COLOR_NORMAL
from modules.utils.ui_state import UIStateManager

logger = logging.getLogger(__name__)

# Module-level list to keep dialog references alive
_open_dialogs = []

# Transparent button style (no border, no background)
# Explicitly override min-width from dialog QPushButton style
_icon_btn_style = """
    QPushButton {
        background: transparent;
        border: none;
        padding: 2px;
        min-width: 0px;
        max-width: 24px;
    }
"""


@dataclass
class ContextState:
    """Snapshot of context editor state for undo/redo."""

    images: List[ContextItem]
    text: str


@dataclass
class ClipboardState:
    """Snapshot of clipboard editor state for undo/redo."""

    text: str
    image: Optional[Tuple[str, str]]  # (base64, media_type)


def show_context_editor(
    context_manager: ContextManager,
    clipboard_manager,
    notification_manager=None,
):
    """Show the context editor dialog. If already open, bring to front."""
    # If dialog already open, just raise it
    if _open_dialogs:
        dialog = _open_dialogs[0]
        dialog.raise_()
        dialog.activateWindow()
        return

    def create_and_show():
        # Double-check in case dialog was opened during timer delay
        if _open_dialogs:
            _open_dialogs[0].raise_()
            _open_dialogs[0].activateWindow()
            return
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


class CollapsibleSectionHeader(QWidget):
    """Header widget for collapsible sections with title, collapse toggle, and optional buttons."""

    toggle_requested = pyqtSignal()
    save_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()

    # Transparent button style (no border, no background)
    _icon_btn_style = """
        QPushButton {
            background: transparent;
            border: none;
            padding: 2px;
        }
    """

    def __init__(
        self,
        title: str,
        show_save_button: bool = True,
        show_undo_redo: bool = False,
        hint_text: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._collapsed = False
        self._title = title

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
            self.undo_btn.setStyleSheet(self._icon_btn_style)
            self.undo_btn.clicked.connect(lambda: self.undo_requested.emit())
            self.undo_btn.setEnabled(False)
            btn_layout.addWidget(self.undo_btn)

            self.redo_btn = IconButton("redo", size=16)
            self.redo_btn.setToolTip("Redo (Ctrl+Shift+Z)")
            self.redo_btn.setStyleSheet(self._icon_btn_style)
            self.redo_btn.clicked.connect(lambda: self.redo_requested.emit())
            self.redo_btn.setEnabled(False)
            btn_layout.addWidget(self.redo_btn)

        # Save button (optional) - icon only, no border, on right side
        if show_save_button:
            self.save_btn = IconButton("save", size=16)
            self.save_btn.setToolTip(f"Save {title.lower()}")
            self.save_btn.setStyleSheet(self._icon_btn_style)
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


class ContextEditorDialog(QDialog):
    """Dialog for editing context (text and images) and clipboard."""

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
        self._ui_state = UIStateManager()

        # Working state
        self._current_images: List[ContextItem] = []
        self._image_chips: List[ImageChipWidget] = []
        self._clipboard_image: Optional[Tuple[str, str]] = None  # (base64, media_type)
        self._clipboard_image_chip: Optional[ImageChipWidget] = None

        # Separate undo/redo stacks for context and clipboard
        self._context_undo_stack: List[ContextState] = []
        self._context_redo_stack: List[ContextState] = []
        self._clipboard_undo_stack: List[ClipboardState] = []
        self._clipboard_redo_stack: List[ClipboardState] = []

        self.setWindowTitle("Context Editor")
        self.setMinimumSize(500, 400)
        self.resize(600, 500)
        self.setWindowFlags(Qt.Window)

        self._setup_ui()
        self._apply_styles()
        self._load_context()
        self._restore_ui_state()

        # Install event filter to intercept Ctrl+V on text_edit and clipboard_edit
        self.text_edit.installEventFilter(self)
        self.clipboard_edit.installEventFilter(self)

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Images section (collapsible, not in splitter - fixed height)
        self.images_section = self._create_images_section()
        layout.addWidget(self.images_section)

        # Main splitter for resizable sections
        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.setHandleWidth(3)
        self.main_splitter.setChildrenCollapsible(False)

        # Context section (collapsible, resizable)
        self.context_section = self._create_context_section()
        self.main_splitter.addWidget(self.context_section)

        # Clipboard section (collapsible, resizable)
        self.clipboard_section = self._create_clipboard_section()
        self.main_splitter.addWidget(self.clipboard_section)

        # Connect splitter movement to save state
        self.main_splitter.splitterMoved.connect(self._on_splitter_moved)

        layout.addWidget(self.main_splitter)

        # Button bar (wrapped in QWidget for consistent positioning)
        button_widget = QWidget()
        button_bar = QHBoxLayout(button_widget)
        button_bar.setContentsMargins(0, 0, 12, 0)  # 12px right margin for alignment
        button_bar.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_bar.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._on_save_clicked)
        save_btn.setDefault(True)
        button_bar.addWidget(save_btn)

        layout.addWidget(button_widget)

        # Track text changes for undo
        self._last_text = ""
        self._last_clipboard_text = ""
        self._text_change_timer = QTimer()
        self._text_change_timer.setSingleShot(True)
        self._text_change_timer.setInterval(500)
        self._text_change_timer.timeout.connect(self._save_text_state)

    def _create_images_section(self) -> QWidget:
        """Create the images row (no header, just chips)."""
        # Just the images container - no header
        self.images_content = QWidget()
        self.images_content.setStyleSheet("background: transparent;")
        self.images_layout = QHBoxLayout(self.images_content)
        self.images_layout.setContentsMargins(0, 0, 0, 4)
        self.images_layout.setSpacing(6)
        self.images_layout.addStretch()

        return self.images_content

    def _create_context_section(self) -> QWidget:
        """Create the collapsible context text section."""
        container = QWidget()
        section_layout = QVBoxLayout(container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)

        # Header with collapse toggle, hint, undo/redo, and save button
        self.context_header = CollapsibleSectionHeader(
            "Context",
            show_undo_redo=True,
            hint_text="(Paste image: Ctrl+V)",
        )
        self.context_header.toggle_requested.connect(self._toggle_context_section)
        self.context_header.save_requested.connect(self._save_context_only)
        self.context_header.undo_requested.connect(self._undo_context)
        self.context_header.redo_requested.connect(self._redo_context)
        section_layout.addWidget(self.context_header)

        # Text edit area
        self.text_edit = QTextEdit()
        self.text_edit.setFont(QFont("Menlo, Monaco, Consolas, monospace", 12))
        self.text_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        self.text_edit.setMinimumHeight(0)  # Allow section to be resized very small
        self.text_edit.textChanged.connect(self._on_text_changed)
        section_layout.addWidget(self.text_edit, 1)  # stretch factor 1 to fill space

        return container

    def _create_clipboard_section(self) -> QWidget:
        """Create the collapsible clipboard text section."""
        container = QWidget()
        section_layout = QVBoxLayout(container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)

        # Header with collapse toggle, undo/redo, and save button
        self.clipboard_header = CollapsibleSectionHeader(
            "Clipboard",
            show_undo_redo=True,
        )
        self.clipboard_header.toggle_requested.connect(self._toggle_clipboard_section)
        self.clipboard_header.save_requested.connect(self._save_clipboard_only)
        self.clipboard_header.undo_requested.connect(self._undo_clipboard)
        self.clipboard_header.redo_requested.connect(self._redo_clipboard)
        section_layout.addWidget(self.clipboard_header)

        # Image container (shown when clipboard has image) - fixed height, not stretched
        self.clipboard_image_container = QWidget()
        self.clipboard_image_container.setStyleSheet("background: transparent;")
        self.clipboard_image_layout = QHBoxLayout(self.clipboard_image_container)
        self.clipboard_image_layout.setContentsMargins(0, 4, 0, 4)
        self.clipboard_image_layout.setSpacing(6)
        self.clipboard_image_layout.addStretch()
        section_layout.addWidget(self.clipboard_image_container, 0, Qt.AlignTop)  # No stretch, align top
        self.clipboard_image_container.hide()  # Hidden by default

        # Text edit area (shown when clipboard has text)
        self.clipboard_edit = QTextEdit()
        self.clipboard_edit.setFont(QFont("Menlo, Monaco, Consolas, monospace", 12))
        self.clipboard_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        self.clipboard_edit.setMinimumHeight(0)  # Allow section to be resized very small
        self.clipboard_edit.textChanged.connect(self._on_clipboard_text_changed)
        section_layout.addWidget(self.clipboard_edit, 1)  # stretch factor 1 to fill space

        # Stretch widget for when image is shown (pushes content to top)
        self.clipboard_stretch = QWidget()
        self.clipboard_stretch.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        section_layout.addWidget(self.clipboard_stretch)
        self.clipboard_stretch.hide()  # Hidden by default (shown when image is displayed)

        return container

    def _toggle_context_section(self):
        """Toggle context section visibility."""
        is_visible = self.text_edit.isVisible()
        will_collapse = is_visible

        if will_collapse:
            # Save current height before collapsing
            sizes = self.main_splitter.sizes()
            if sizes[0] > 50:  # Only save if it's a meaningful size
                self._ui_state.set(
                    "context_editor_dialog.sections.context.height", sizes[0]
                )

        self.text_edit.setVisible(not is_visible)
        self.context_header.set_collapsed(is_visible)
        self._save_section_state("context", collapsed=is_visible)
        self._adjust_splitter_for_collapse()

    def _toggle_clipboard_section(self):
        """Toggle clipboard section visibility."""
        # Content is visible if either text edit or image container is shown
        content_visible = self.clipboard_edit.isVisible() or self.clipboard_image_container.isVisible()
        will_collapse = content_visible

        if will_collapse:
            # Save current height before collapsing
            sizes = self.main_splitter.sizes()
            if sizes[1] > 50:  # Only save if it's a meaningful size
                self._ui_state.set(
                    "context_editor_dialog.sections.clipboard.height", sizes[1]
                )
            # Hide both (one is already hidden)
            self.clipboard_edit.hide()
            self.clipboard_image_container.hide()
            self.clipboard_stretch.hide()
        else:
            # Show the appropriate content
            if self._clipboard_image:
                self.clipboard_image_container.show()
                self.clipboard_stretch.show()  # Show stretch to push content to top
            else:
                self.clipboard_edit.show()
                self.clipboard_stretch.hide()

        self.clipboard_header.set_collapsed(will_collapse)
        self._save_section_state("clipboard", collapsed=will_collapse)
        self._adjust_splitter_for_collapse()

    def _adjust_splitter_for_collapse(self):
        """Adjust splitter sizes based on collapsed states."""
        context_collapsed = not self.text_edit.isVisible()
        clipboard_collapsed = not (self.clipboard_edit.isVisible() or self.clipboard_image_container.isVisible())

        header_height = 30  # Height of collapsed section (just header)

        # Reset size constraints first
        self.context_section.setMinimumHeight(0)
        self.context_section.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
        self.clipboard_section.setMinimumHeight(0)
        self.clipboard_section.setMaximumHeight(16777215)

        if context_collapsed and clipboard_collapsed:
            # Both collapsed - lock both to header height, hide splitter handle
            self.context_section.setFixedHeight(header_height)
            self.clipboard_section.setFixedHeight(header_height)
            self.main_splitter.setHandleWidth(0)
        elif context_collapsed:
            # Context collapsed and locked, clipboard takes rest
            self.context_section.setFixedHeight(header_height)
            self.main_splitter.setHandleWidth(0)  # Hide handle - can't resize
        elif clipboard_collapsed:
            # Clipboard collapsed and locked, context takes rest
            self.clipboard_section.setFixedHeight(header_height)
            self.main_splitter.setHandleWidth(0)  # Hide handle - can't resize
        else:
            # Both expanded - restore saved sizes, show splitter handle
            self.main_splitter.setHandleWidth(3)
            saved_context_height = self._ui_state.get(
                "context_editor_dialog.sections.context.height", 200
            )
            saved_clipboard_height = self._ui_state.get(
                "context_editor_dialog.sections.clipboard.height", 150
            )
            self.main_splitter.setSizes([saved_context_height, saved_clipboard_height])

    def _save_section_state(self, section: str, collapsed: bool):
        """Save section collapsed state."""
        key = f"context_editor_dialog.sections.{section}.collapsed"
        self._ui_state.set(key, collapsed)

    def _save_splitter_state(self):
        """Save splitter sizes (only when both sections are expanded)."""
        # Only save sizes when both sections are expanded
        context_expanded = self.text_edit.isVisible()
        clipboard_expanded = self.clipboard_edit.isVisible() or self.clipboard_image_container.isVisible()

        if not (context_expanded and clipboard_expanded):
            return

        sizes = self.main_splitter.sizes()
        if len(sizes) >= 2:
            self._ui_state.set(
                "context_editor_dialog.sections.context.height", sizes[0]
            )
            self._ui_state.set(
                "context_editor_dialog.sections.clipboard.height", sizes[1]
            )

    def _on_splitter_moved(self, pos: int, index: int):
        """Handle splitter movement - save new sizes."""
        self._save_splitter_state()

    def _restore_ui_state(self):
        """Restore splitter sizes and collapsed states from saved state."""
        # FIRST: Restore geometry before adjusting splitter
        geometry = self._ui_state.get("context_editor_dialog.geometry")
        if geometry:
            self._restore_geometry(geometry)

        # Restore collapsed states
        context_collapsed = self._ui_state.get(
            "context_editor_dialog.sections.context.collapsed", False
        )
        clipboard_collapsed = self._ui_state.get(
            "context_editor_dialog.sections.clipboard.collapsed", False
        )

        if context_collapsed:
            self.text_edit.hide()
            self.context_header.set_collapsed(True)
        if clipboard_collapsed:
            self.clipboard_edit.hide()
            self.clipboard_image_container.hide()
            self.clipboard_stretch.hide()
            self.clipboard_header.set_collapsed(True)

        # Defer splitter adjustment until Qt has processed the layout
        QTimer.singleShot(0, self._adjust_splitter_for_collapse)

    def _restore_geometry(self, geometry: dict):
        """Restore window geometry."""
        width = geometry.get("width", 600)
        height = geometry.get("height", 500)
        x = geometry.get("x")
        y = geometry.get("y")

        self.resize(max(width, 500), max(height, 400))

        if x is not None and y is not None:
            self.move(x, y)

    def _save_window_geometry(self):
        """Save window geometry to UI state."""
        geom = self.geometry()
        self._ui_state.set("context_editor_dialog.geometry", {
            "x": geom.x(),
            "y": geom.y(),
            "width": geom.width(),
            "height": geom.height()
        })

    def closeEvent(self, event):
        """Save geometry on close."""
        self._save_window_geometry()
        super().closeEvent(event)

    def _save_context_only(self):
        """Save only the context changes."""
        self.context_manager.clear_context()

        # Add images first
        for image_item in self._current_images:
            self.context_manager.append_context_image(
                image_item.data,
                image_item.media_type or "image/png",
            )

        # Add text
        text_content = self.text_edit.toPlainText().strip()
        if text_content:
            self.context_manager.append_context(text_content)

        if self.notification_manager:
            self.notification_manager.show_success_notification("Context saved")

    def _save_clipboard_only(self):
        """Save only the clipboard changes."""
        if self._clipboard_image:
            # Copy image to system clipboard
            if self._clipboard_image_chip:
                self._clipboard_image_chip.copy_to_clipboard()
        elif self.clipboard_edit.isVisible():
            # Save text to clipboard
            clipboard_content = self.clipboard_edit.toPlainText()
            self.clipboard_manager.set_content(clipboard_content)

        if self.notification_manager:
            self.notification_manager.show_success_notification("Clipboard saved")

    def _apply_styles(self):
        """Apply dark theme styling."""
        self.setStyleSheet(
            """
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
            QSplitter::handle {
                background-color: #3a3a3a;
            }
            QSplitter::handle:hover {
                background-color: #555555;
            }
            QSplitter::handle:vertical {
                height: 6px;
            }
        """
        )

    def _load_context(self):
        """Load current context and clipboard into the dialog."""
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

        # Load clipboard content (check for image first)
        try:
            if self.clipboard_manager.has_image():
                image_data = self.clipboard_manager.get_image_data()
                if image_data:
                    self._clipboard_image = image_data
                    self._rebuild_clipboard_image_chip()
                    self.clipboard_image_container.show()
                    self.clipboard_stretch.show()  # Push content to top
                    self.clipboard_edit.hide()
                    self._last_clipboard_text = ""
                else:
                    self._load_clipboard_text()
            else:
                self._load_clipboard_text()
        except Exception as e:
            logger.warning(f"Failed to load clipboard content: {e}")
            self._load_clipboard_text()

        # Clear undo/redo stacks
        self._context_undo_stack.clear()
        self._context_redo_stack.clear()
        self._clipboard_undo_stack.clear()
        self._clipboard_redo_stack.clear()
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

    def _load_clipboard_text(self):
        """Load text content from clipboard."""
        try:
            clipboard_content = self.clipboard_manager.get_content()
            self.clipboard_edit.setPlainText(clipboard_content or "")
            self._last_clipboard_text = clipboard_content or ""
        except Exception as e:
            logger.warning(f"Failed to load clipboard text: {e}")
            self.clipboard_edit.setPlainText("")
            self._last_clipboard_text = ""
        self._clipboard_image = None
        self.clipboard_image_container.hide()
        self.clipboard_stretch.hide()
        self.clipboard_edit.show()

    def _rebuild_clipboard_image_chip(self):
        """Rebuild the clipboard image chip."""
        # Clear existing chip
        if self._clipboard_image_chip:
            self._clipboard_image_chip.deleteLater()
            self._clipboard_image_chip = None

        # Remove all items from layout
        while self.clipboard_image_layout.count():
            self.clipboard_image_layout.takeAt(0)

        if not self._clipboard_image:
            return

        base64_data, media_type = self._clipboard_image
        chip = ImageChipWidget(
            index=0,
            image_number=1,
            image_data=base64_data,
            media_type=media_type,
        )
        chip.delete_requested.connect(self._on_clipboard_image_delete)
        chip.copy_requested.connect(self._on_clipboard_image_copy)
        self._clipboard_image_chip = chip
        self.clipboard_image_layout.addWidget(chip)
        self.clipboard_image_layout.addStretch()

    def _on_clipboard_image_delete(self, index: int):
        """Handle clipboard image delete request."""
        self._save_clipboard_state()
        self._clipboard_image = None
        self._rebuild_clipboard_image_chip()
        self.clipboard_image_container.hide()
        self.clipboard_stretch.hide()
        self.clipboard_edit.show()
        self.clipboard_edit.setPlainText("")
        self._last_clipboard_text = ""

    def _on_clipboard_image_copy(self, index: int):
        """Handle clipboard image copy request."""
        if self._clipboard_image_chip:
            self._clipboard_image_chip.copy_to_clipboard()
            if self.notification_manager:
                self.notification_manager.show_success_notification("Copied")

    # --- Context state management ---

    def _get_context_state(self) -> ContextState:
        """Get current context state."""
        return ContextState(
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

    def _restore_context_state(self, state: ContextState):
        """Restore context state."""
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

    def _save_context_state(self):
        """Save current context state to undo stack."""
        state = self._get_context_state()
        self._context_undo_stack.append(state)
        self._context_redo_stack.clear()
        self._update_undo_redo_buttons()

    def _undo_context(self):
        """Undo last context change."""
        if not self._context_undo_stack:
            return

        # Save current state to redo stack
        self._context_redo_stack.append(self._get_context_state())

        # Restore previous state
        state = self._context_undo_stack.pop()
        self._restore_context_state(state)
        self._update_undo_redo_buttons()

    def _redo_context(self):
        """Redo last undone context change."""
        if not self._context_redo_stack:
            return

        # Save current state to undo stack
        self._context_undo_stack.append(self._get_context_state())

        # Restore redo state
        state = self._context_redo_stack.pop()
        self._restore_context_state(state)
        self._update_undo_redo_buttons()

    # --- Clipboard state management ---

    def _get_clipboard_state(self) -> ClipboardState:
        """Get current clipboard state."""
        return ClipboardState(
            text=self.clipboard_edit.toPlainText(),
            image=self._clipboard_image,
        )

    def _restore_clipboard_state(self, state: ClipboardState):
        """Restore clipboard state."""
        self.clipboard_edit.blockSignals(True)
        self.clipboard_edit.setPlainText(state.text)
        self._last_clipboard_text = state.text
        self.clipboard_edit.blockSignals(False)

        # Restore clipboard image state
        self._clipboard_image = state.image
        self._rebuild_clipboard_image_chip()
        if self._clipboard_image:
            self.clipboard_image_container.show()
            self.clipboard_stretch.show()
            self.clipboard_edit.hide()
        else:
            self.clipboard_image_container.hide()
            self.clipboard_stretch.hide()
            self.clipboard_edit.show()

    def _save_clipboard_state(self):
        """Save current clipboard state to undo stack."""
        state = self._get_clipboard_state()
        self._clipboard_undo_stack.append(state)
        self._clipboard_redo_stack.clear()
        self._update_undo_redo_buttons()

    def _undo_clipboard(self):
        """Undo last clipboard change."""
        if not self._clipboard_undo_stack:
            return

        # Save current state to redo stack
        self._clipboard_redo_stack.append(self._get_clipboard_state())

        # Restore previous state
        state = self._clipboard_undo_stack.pop()
        self._restore_clipboard_state(state)
        self._update_undo_redo_buttons()

    def _redo_clipboard(self):
        """Redo last undone clipboard change."""
        if not self._clipboard_redo_stack:
            return

        # Save current state to undo stack
        self._clipboard_undo_stack.append(self._get_clipboard_state())

        # Restore redo state
        state = self._clipboard_redo_stack.pop()
        self._restore_clipboard_state(state)
        self._update_undo_redo_buttons()

    # --- Common state management ---

    def _update_undo_redo_buttons(self):
        """Update undo/redo button states for both sections."""
        self.context_header.set_undo_redo_enabled(
            len(self._context_undo_stack) > 0,
            len(self._context_redo_stack) > 0,
        )
        self.clipboard_header.set_undo_redo_enabled(
            len(self._clipboard_undo_stack) > 0,
            len(self._clipboard_redo_stack) > 0,
        )

    def _save_text_state(self):
        """Save state if text has significantly changed."""
        current_text = self.text_edit.toPlainText()
        current_clipboard = self.clipboard_edit.toPlainText()

        # Save context state if text changed
        if current_text != self._last_text:
            state = ContextState(
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
            self._context_undo_stack.append(state)
            self._context_redo_stack.clear()
            self._last_text = current_text

        # Save clipboard state if text changed
        if current_clipboard != self._last_clipboard_text:
            state = ClipboardState(
                text=self._last_clipboard_text,
                image=self._clipboard_image,
            )
            self._clipboard_undo_stack.append(state)
            self._clipboard_redo_stack.clear()
            self._last_clipboard_text = current_clipboard

        self._update_undo_redo_buttons()

    def _on_text_changed(self):
        """Handle text changes - debounce state saving."""
        self._text_change_timer.start()

    def _on_clipboard_text_changed(self):
        """Handle clipboard text changes - debounce state saving."""
        self._text_change_timer.start()

    def _on_image_delete(self, index: int):
        """Handle image chip delete request."""
        if 0 <= index < len(self._current_images):
            self._save_context_state()
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
            self._save_context_state()
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
        """Save both context and clipboard changes."""
        # Save context
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

        # Save clipboard (only if text edit is visible - image already in clipboard)
        if self.clipboard_edit.isVisible():
            clipboard_content = self.clipboard_edit.toPlainText()
            self.clipboard_manager.set_content(clipboard_content)

        self.context_saved.emit()
        self.accept()

    def keyPressEvent(self, event):
        """Handle key press events."""
        # Ctrl+Z for undo (focus-aware)
        if event.key() == Qt.Key_Z and (event.modifiers() & Qt.ControlModifier):
            if event.modifiers() & Qt.ShiftModifier:
                # Ctrl+Shift+Z for redo
                if self.clipboard_edit.hasFocus():
                    self._redo_clipboard()
                else:
                    self._redo_context()
            else:
                # Ctrl+Z for undo
                if self.clipboard_edit.hasFocus():
                    self._undo_clipboard()
                else:
                    self._undo_context()
            event.accept()
            return

        # Ctrl+Y for redo (alternative, focus-aware)
        if event.key() == Qt.Key_Y and (event.modifiers() & Qt.ControlModifier):
            if self.clipboard_edit.hasFocus():
                self._redo_clipboard()
            else:
                self._redo_context()
            event.accept()
            return

        # Ctrl+C for copy (use xclip to avoid X11 clipboard ownership freeze)
        if (
            event.key() == Qt.Key_C
            and (event.modifiers() & Qt.ControlModifier)
            and not (event.modifiers() & Qt.ShiftModifier)
        ):
            # Check which text edit has focus and get selected text
            focused_edit = None
            if self.text_edit.hasFocus():
                focused_edit = self.text_edit
            elif self.clipboard_edit.hasFocus():
                focused_edit = self.clipboard_edit

            if focused_edit:
                selected_text = focused_edit.textCursor().selectedText()
                if selected_text:
                    # Replace paragraph separators with newlines
                    selected_text = selected_text.replace('\u2029', '\n')
                    self.clipboard_manager.set_content(selected_text)
                    event.accept()
                    return
            # Fall through to default Qt handling if no selection

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
        if event.type() in (
            QEvent.WindowActivate,
            QEvent.FocusIn,
            QEvent.MouseButtonPress,
        ):
            self.raise_()
            self.activateWindow()
            QTimer.singleShot(75, self._ensure_focus)
        return super().event(event)

    def eventFilter(self, obj, event):
        """Filter events to intercept Ctrl+Z, Ctrl+C, and Ctrl+V on text edits."""
        if obj in (self.text_edit, self.clipboard_edit) and event.type() == QEvent.KeyPress:
            # Ctrl+Z for undo (focus-aware)
            if event.key() == Qt.Key_Z and (event.modifiers() & Qt.ControlModifier):
                if event.modifiers() & Qt.ShiftModifier:
                    # Ctrl+Shift+Z for redo
                    if obj == self.clipboard_edit:
                        self._redo_clipboard()
                    else:
                        self._redo_context()
                else:
                    # Ctrl+Z for undo
                    if obj == self.clipboard_edit:
                        self._undo_clipboard()
                    else:
                        self._undo_context()
                return True  # Event handled
            # Ctrl+Y for redo (alternative)
            if event.key() == Qt.Key_Y and (event.modifiers() & Qt.ControlModifier):
                if obj == self.clipboard_edit:
                    self._redo_clipboard()
                else:
                    self._redo_context()
                return True  # Event handled
            # Ctrl+C for copy (use xclip to avoid X11 clipboard ownership freeze)
            if (
                event.key() == Qt.Key_C
                and (event.modifiers() & Qt.ControlModifier)
                and not (event.modifiers() & Qt.ShiftModifier)
            ):
                selected_text = obj.textCursor().selectedText()
                if selected_text:
                    # Replace paragraph separators with newlines
                    selected_text = selected_text.replace('\u2029', '\n')
                    self.clipboard_manager.set_content(selected_text)
                    return True  # Event handled
            # Ctrl+V for paste image
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
