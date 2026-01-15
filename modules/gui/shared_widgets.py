"""Shared widgets for GUI dialogs."""

import base64
import logging
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QApplication,
    QTextEdit,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal, QByteArray, QBuffer, QTimer
from PyQt5.QtGui import QFont, QImage

from modules.gui.context_widgets import IconButton
from modules.gui.icons import ICON_COLOR_NORMAL

logger = logging.getLogger(__name__)

# Dark theme tooltip style - single source of truth for all tooltips
TOOLTIP_STYLE = """
    QToolTip {
        background-color: #0d0d0d;
        color: #f0f0f0;
        border: 1px solid #444444;
        border-radius: 0px;
        padding: 6px 8px;
    }
"""

# Transparent button style (no border, no background)
ICON_BTN_STYLE = """
    QPushButton {
        background: transparent;
        border: none;
        padding: 2px;
        min-width: 0px;
        max-width: 24px;
    }
""" + TOOLTIP_STYLE


class CollapsibleSectionHeader(QWidget):
    """Header widget for collapsible sections with title, collapse toggle, and optional buttons."""

    toggle_requested = pyqtSignal()
    save_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()
    delete_requested = pyqtSignal()
    wrap_requested = pyqtSignal()

    def __init__(
        self,
        title: str,
        show_save_button: bool = True,
        show_undo_redo: bool = False,
        show_delete_button: bool = False,
        show_wrap_button: bool = False,
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
        layout.setContentsMargins(0, 0, 12, 0)  # Minimal vertical margins for compact collapsed headers
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

        # Wrap button (optional) - placed before undo/redo
        self.wrap_btn = None
        self._wrapped = True  # Default state: wrapped (height limited)
        if show_wrap_button:
            self.wrap_btn = IconButton("chevrons-up-down", size=16)
            self.wrap_btn.setToolTip("Expand to fit content")
            self.wrap_btn.setStyleSheet(ICON_BTN_STYLE)
            self.wrap_btn.clicked.connect(lambda: self.wrap_requested.emit())
            btn_layout.addWidget(self.wrap_btn)

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

    def set_wrap_state(self, wrapped: bool):
        """Update the wrap button icon based on state.

        Args:
            wrapped: True if content is wrapped (height limited), False if expanded
        """
        self._wrapped = wrapped
        if self.wrap_btn:
            # chevrons-up-down = wrapped (arrows pointing outward = can expand)
            # chevrons-down-up = unwrapped (arrows pointing inward = can compress)
            icon_name = "chevrons-up-down" if wrapped else "chevrons-down-up"
            self.wrap_btn._icon_name = icon_name
            self.wrap_btn._update_icon(ICON_COLOR_NORMAL)
            self.wrap_btn.setToolTip(
                "Expand to fit content" if wrapped else "Wrap to fixed height"
            )

    def set_wrap_button_visible(self, visible: bool):
        """Show or hide the wrap button."""
        if self.wrap_btn:
            self.wrap_btn.setVisible(visible)

    def is_wrapped(self) -> bool:
        """Return current wrap state."""
        return self._wrapped


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


def create_text_edit(
    placeholder: str = "",
    min_height: int = 100,
    font_size: int = 12,
) -> QTextEdit:
    """Create a pre-configured QTextEdit with standard styling.

    Args:
        placeholder: Placeholder text
        min_height: Minimum height in pixels (0 for no minimum)
        font_size: Font size for monospace font

    Returns:
        Configured QTextEdit widget
    """
    text_edit = QTextEdit()
    text_edit.setFont(QFont("Menlo, Monaco, Consolas, monospace", font_size))
    text_edit.setLineWrapMode(QTextEdit.WidgetWidth)
    text_edit.setAcceptRichText(False)
    if min_height > 0:
        text_edit.setMinimumHeight(min_height)
    if placeholder:
        text_edit.setPlaceholderText(placeholder)
    return text_edit


class ExpandableTextSection(QWidget):
    """A collapsible text section with wrap/expand functionality and undo/redo support.

    This widget combines a CollapsibleSectionHeader with a QTextEdit and provides:
    - Collapse/expand toggle for the section
    - Wrap/expand toggle for the text area (300px default vs fit content)
    - Built-in undo/redo state management
    - Optional save button

    Signals:
        collapsed_changed(bool): Emitted when section is collapsed/expanded
        wrapped_changed(bool): Emitted when wrap state changes
        text_changed(): Emitted when text content changes
        save_requested(): Emitted when save button is clicked
    """

    collapsed_changed = pyqtSignal(bool)
    wrapped_changed = pyqtSignal(bool)
    text_changed = pyqtSignal()
    save_requested = pyqtSignal()

    # Default height when wrapped
    DEFAULT_WRAPPED_HEIGHT = 300

    def __init__(
        self,
        title: str,
        show_save_button: bool = False,
        show_undo_redo: bool = True,
        show_wrap_button: bool = True,
        placeholder: str = "",
        hint_text: str = "",
        parent: Optional[QWidget] = None,
    ):
        """Create an expandable text section.

        Args:
            title: Section header title
            show_save_button: Show save button in header
            show_undo_redo: Show undo/redo buttons in header
            show_wrap_button: Show wrap/expand toggle button
            placeholder: Placeholder text for the text edit
            hint_text: Optional hint text in header
            parent: Parent widget
        """
        super().__init__(parent)
        self._collapsed = False
        self._wrapped = True  # Default: wrapped (height limited)
        self._title = title

        # Undo/redo state
        self._undo_stack: list = []
        self._redo_stack: list = []
        self._last_text = ""

        # Text change debounce timer
        self._text_change_timer = QTimer()
        self._text_change_timer.setSingleShot(True)
        self._text_change_timer.setInterval(500)
        self._text_change_timer.timeout.connect(self._save_text_state)

        self._setup_ui(
            title,
            show_save_button,
            show_undo_redo,
            show_wrap_button,
            placeholder,
            hint_text,
        )

    def _setup_ui(
        self,
        title: str,
        show_save_button: bool,
        show_undo_redo: bool,
        show_wrap_button: bool,
        placeholder: str,
        hint_text: str,
    ):
        """Set up the section UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        self.header = CollapsibleSectionHeader(
            title,
            show_save_button=show_save_button,
            show_undo_redo=show_undo_redo,
            show_wrap_button=show_wrap_button,
            hint_text=hint_text,
        )
        self.header.toggle_requested.connect(self._on_toggle)
        self.header.wrap_requested.connect(self._on_wrap_toggle)
        self.header.undo_requested.connect(self.undo)
        self.header.redo_requested.connect(self.redo)
        self.header.save_requested.connect(lambda: self.save_requested.emit())
        layout.addWidget(self.header)

        # Text edit
        self.text_edit = create_text_edit(placeholder=placeholder, min_height=0)
        self.text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.text_edit)

        # Apply initial wrap state
        self._apply_wrap_state()

    def _on_toggle(self):
        """Handle collapse/expand toggle."""
        self._collapsed = not self._collapsed
        self.text_edit.setVisible(not self._collapsed)
        self.header.set_collapsed(self._collapsed)
        self.collapsed_changed.emit(self._collapsed)

    def _on_wrap_toggle(self):
        """Handle wrap/expand toggle."""
        self._wrapped = not self._wrapped
        self.header.set_wrap_state(self._wrapped)
        self._apply_wrap_state()
        self.wrapped_changed.emit(self._wrapped)

    def _apply_wrap_state(self):
        """Apply the current wrap state to the text edit."""
        if self._wrapped:
            self.text_edit.setMaximumHeight(self.DEFAULT_WRAPPED_HEIGHT)
            self.text_edit.setMinimumHeight(0)
        else:
            self.text_edit.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
            self.text_edit.setMinimumHeight(0)

    def _on_text_changed(self):
        """Handle text changes - debounce state saving."""
        self._text_change_timer.start()
        self.text_changed.emit()

    def _save_text_state(self):
        """Save text state if changed (called by debounce timer)."""
        current_text = self.text_edit.toPlainText()
        if current_text != self._last_text:
            self._undo_stack.append(self._last_text)
            self._redo_stack.clear()
            self._last_text = current_text
            self._update_undo_redo_buttons()

    def _update_undo_redo_buttons(self):
        """Update undo/redo button enabled states."""
        self.header.set_undo_redo_enabled(
            len(self._undo_stack) > 0,
            len(self._redo_stack) > 0,
        )

    # Public API

    def undo(self):
        """Undo last text change."""
        if not self._undo_stack:
            return
        self._redo_stack.append(self.text_edit.toPlainText())
        previous_text = self._undo_stack.pop()
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(previous_text)
        self._last_text = previous_text
        self.text_edit.blockSignals(False)
        self._update_undo_redo_buttons()

    def redo(self):
        """Redo last undone text change."""
        if not self._redo_stack:
            return
        self._undo_stack.append(self.text_edit.toPlainText())
        redo_text = self._redo_stack.pop()
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(redo_text)
        self._last_text = redo_text
        self.text_edit.blockSignals(False)
        self._update_undo_redo_buttons()

    def set_text(self, text: str):
        """Set the text content without affecting undo stack."""
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(text)
        self._last_text = text
        self.text_edit.blockSignals(False)
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._update_undo_redo_buttons()

    def get_text(self) -> str:
        """Get the current text content."""
        return self.text_edit.toPlainText()

    def set_collapsed(self, collapsed: bool):
        """Set the collapsed state."""
        if self._collapsed != collapsed:
            self._collapsed = collapsed
            self.text_edit.setVisible(not collapsed)
            self.header.set_collapsed(collapsed)

    def is_collapsed(self) -> bool:
        """Return whether the section is collapsed."""
        return self._collapsed

    def set_wrapped(self, wrapped: bool):
        """Set the wrapped state."""
        if self._wrapped != wrapped:
            self._wrapped = wrapped
            self.header.set_wrap_state(wrapped)
            self._apply_wrap_state()

    def is_wrapped(self) -> bool:
        """Return whether the text is wrapped (height limited)."""
        return self._wrapped

    def clear_undo_stack(self):
        """Clear the undo/redo stacks."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._update_undo_redo_buttons()
