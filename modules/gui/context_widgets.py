"""Context section widgets for displaying and managing context items as chips."""

import base64
import logging
from typing import Optional, Callable

from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolTip,
    QApplication,
)
from PyQt5.QtCore import Qt, pyqtSignal, QByteArray, QBuffer, QSize, QPoint, QMimeData
from PyQt5.QtGui import QPixmap, QImage, QCursor

from core.context_manager import ContextManager, ContextItem, ContextItemType
from modules.gui.icons import (
    create_icon,
    ICON_COLOR_NORMAL,
    ICON_COLOR_HOVER,
    ICON_COLOR_DISABLED,
)


class IconButton(QPushButton):
    """QPushButton with SVG icon that changes color on hover."""

    def __init__(
        self,
        icon_name: str,
        size: int = 16,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._icon_name = icon_name
        self._icon_size = size
        self._update_icon(ICON_COLOR_NORMAL)
        self.setIconSize(QSize(size, size))

    def _update_icon(self, color: str):
        """Update the icon with specified color."""
        self.setIcon(create_icon(self._icon_name, color, self._icon_size))

    def enterEvent(self, event):
        """Change icon color on hover."""
        if self.isEnabled():
            self._update_icon(ICON_COLOR_HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Restore icon color when not hovering."""
        if self.isEnabled():
            self._update_icon(ICON_COLOR_NORMAL)
        super().leaveEvent(event)

    def setEnabled(self, enabled: bool):
        """Update icon color when enabled state changes."""
        super().setEnabled(enabled)
        if enabled:
            self._update_icon(ICON_COLOR_NORMAL)
        else:
            self._update_icon(ICON_COLOR_DISABLED)

logger = logging.getLogger(__name__)


class ContextChipBase(QWidget):
    """Base class for context chips with copy and delete buttons."""

    delete_requested = pyqtSignal(int)  # Emits item index
    copy_requested = pyqtSignal(int)  # Emits item index

    _chip_style = """
        QWidget#chip {
            background-color: #3a3a3a;
            border: 1px solid #555555;
            border-radius: 12px;
            padding: 2px;
        }
    """

    _chip_hover_style = """
        QWidget#chip {
            background-color: #454545;
            border: 1px solid #555555;
            border-radius: 12px;
            padding: 2px;
        }
    """

    _label_style = """
        QLabel {
            color: #f0f0f0;
            font-size: 12px;
            padding: 2px 4px;
            background: transparent;
        }
    """

    _icon_btn_style = """
        QPushButton {
            background: transparent;
            border: none;
            padding: 2px;
            min-width: 20px;
            max-width: 20px;
            min-height: 20px;
            max-height: 20px;
        }
    """

    def __init__(self, index: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.index = index
        self.setObjectName("chip")
        self.setAttribute(Qt.WA_StyledBackground, True)  # Enable background painting
        self.setStyleSheet(self._chip_style)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(4)

        # Copy icon at the beginning
        self.copy_btn = IconButton("copy", size=16)
        self.copy_btn.setStyleSheet(self._icon_btn_style)
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setToolTip("Copy to clipboard")
        self.copy_btn.clicked.connect(self._on_copy_clicked)
        layout.addWidget(self.copy_btn)

        self.label = QLabel()
        self.label.setStyleSheet(self._label_style)
        layout.addWidget(self.label)

        # Delete button (x) at the end
        self.delete_btn = IconButton("delete", size=16)
        self.delete_btn.setStyleSheet(self._icon_btn_style)
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setToolTip("Remove from context")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self.delete_btn)

        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

    def _on_delete_clicked(self):
        """Handle delete button click."""
        self.delete_requested.emit(self.index)

    def _on_copy_clicked(self):
        """Handle copy button click."""
        self.copy_requested.emit(self.index)

    def mousePressEvent(self, event):
        """Handle mouse press - copy on click (except on buttons)."""
        # Check if click is on the delete button area
        delete_btn_rect = self.delete_btn.geometry()
        copy_btn_rect = self.copy_btn.geometry()

        if not delete_btn_rect.contains(event.pos()) and not copy_btn_rect.contains(
            event.pos()
        ):
            self._on_copy_clicked()
        super().mousePressEvent(event)

    def set_label_text(self, text: str):
        """Set the chip label text."""
        self.label.setText(text)

    def enterEvent(self, event):
        """Handle mouse enter - show hover state."""
        self.setStyleSheet(self._chip_hover_style)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Handle mouse leave - restore normal state."""
        self.setStyleSheet(self._chip_style)
        super().leaveEvent(event)

    def copy_to_clipboard(self):
        """Copy chip content to clipboard. Override in subclasses."""
        pass


class TextContextChip(ContextChipBase):
    """Chip widget for text context items."""

    def __init__(
        self,
        index: int,
        text_content: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(index, parent)
        self.full_text = text_content

        # Truncate text for display (max 30 chars)
        display_text = text_content.replace("\n", " ")
        if len(display_text) > 30:
            display_text = display_text[:27] + "..."
        self.set_label_text(display_text)

        # Set tooltip with full text
        self.setToolTip(text_content)

    def copy_to_clipboard(self):
        """Copy text content to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.full_text)


class ImageContextChip(ContextChipBase):
    """Chip widget for image context items."""

    def __init__(
        self,
        index: int,
        image_number: int,
        image_data: str,
        media_type: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(index, parent)
        self.image_data = image_data
        self.media_type = media_type

        self.set_label_text(f"[image #{image_number}]")

        # Create tooltip with thumbnail preview
        self._setup_image_tooltip()

    def _setup_image_tooltip(self):
        """Set up tooltip with image thumbnail and metadata."""
        try:
            # Decode base64 image data
            image_bytes = base64.b64decode(self.image_data)
            image = QImage()
            image.loadFromData(QByteArray(image_bytes))

            if image.isNull():
                self.setToolTip("Image preview unavailable")
                return

            # Get original dimensions
            orig_width = image.width()
            orig_height = image.height()

            # Scale to thumbnail (max 150px)
            thumbnail = image.scaled(
                150,
                150,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )

            # Convert to base64 PNG for HTML tooltip
            buffer = QBuffer()
            buffer.open(QBuffer.WriteOnly)
            thumbnail.save(buffer, "PNG")
            thumb_base64 = base64.b64encode(buffer.data()).decode("utf-8")
            buffer.close()

            # Get format from media type
            format_name = self.media_type.split("/")[-1].upper()

            # Create HTML tooltip
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

    def copy_to_clipboard(self):
        """Copy image to clipboard."""
        try:
            image_bytes = base64.b64decode(self.image_data)
            image = QImage()
            image.loadFromData(QByteArray(image_bytes))

            if not image.isNull():
                clipboard = QApplication.clipboard()
                clipboard.setImage(image)
        except Exception as e:
            logger.warning(f"Failed to copy image to clipboard: {e}")


class ContextHeaderWidget(QWidget):
    """Header widget with 'Context' label, edit, copy and clear buttons."""

    clear_requested = pyqtSignal()
    copy_requested = pyqtSignal()
    edit_requested = pyqtSignal()

    _header_style = """
        QWidget {
            background: transparent;
        }
    """

    _title_style = """
        QLabel {
            color: #888888;
            font-size: 11px;
            font-weight: bold;
            padding: 2px 4px;
            background: transparent;
        }
    """

    _btn_style = """
        QPushButton {
            background: transparent;
            border: none;
            padding: 2px;
            min-width: 22px;
            max-width: 22px;
            min-height: 22px;
            max-height: 22px;
        }
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setStyleSheet(self._header_style)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 2)
        layout.setSpacing(4)

        title_label = QLabel("Context")
        title_label.setStyleSheet(self._title_style)
        layout.addWidget(title_label)

        layout.addStretch()

        # Edit button
        self.edit_btn = IconButton("edit", size=18)
        self.edit_btn.setStyleSheet(self._btn_style)
        self.edit_btn.setCursor(Qt.PointingHandCursor)
        self.edit_btn.setToolTip("Edit context")
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        layout.addWidget(self.edit_btn)

        # Copy button
        self.copy_btn = IconButton("copy", size=18)
        self.copy_btn.setStyleSheet(self._btn_style)
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setToolTip("Copy context text")
        self.copy_btn.clicked.connect(self._on_copy_clicked)
        self.copy_btn.setEnabled(False)  # Disabled by default
        layout.addWidget(self.copy_btn)

        # Clear button
        clear_btn = IconButton("delete", size=18)
        clear_btn.setStyleSheet(self._btn_style)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setToolTip("Clear all context")
        clear_btn.clicked.connect(self._on_clear_clicked)
        layout.addWidget(clear_btn)

    def _on_clear_clicked(self):
        """Handle clear button click."""
        self.clear_requested.emit()

    def _on_copy_clicked(self):
        """Handle copy button click."""
        self.copy_requested.emit()

    def _on_edit_clicked(self):
        """Handle edit button click."""
        self.edit_requested.emit()

    def set_copy_enabled(self, enabled: bool):
        """Enable or disable the copy button."""
        self.copy_btn.setEnabled(enabled)


class FlowLayout(QVBoxLayout):
    """Simple flow-like layout using horizontal layouts that wrap."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setContentsMargins(4, 0, 4, 0)
        self.setSpacing(2)
        self._rows = []

    def clear_widgets(self):
        """Remove all widgets from the layout."""
        while self.count():
            item = self.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
        self._rows = []

    def _clear_layout(self, layout):
        """Recursively clear a layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def add_widget(self, widget: QWidget):
        """Add a widget, creating new rows as needed."""
        # For simplicity, add each chip in a horizontal layout
        # that allows multiple chips per row
        if not self._rows or self._current_row_full():
            self._add_new_row()
        self._rows[-1].addWidget(widget)

    def _current_row_full(self) -> bool:
        """Check if current row is full (simple heuristic: max 3 chips)."""
        if not self._rows:
            return True
        return self._rows[-1].count() >= 3

    def _add_new_row(self):
        """Add a new horizontal row."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addStretch()  # This will be at the end
        self.addLayout(row)
        self._rows.append(row)

    def add_widget(self, widget: QWidget):
        """Add a widget to the flow layout."""
        if not self._rows or self._current_row_full():
            self._add_new_row()

        # Insert widget before the stretch
        row = self._rows[-1]
        row.insertWidget(row.count() - 1, widget)


class ContextSectionWidget(QWidget):
    """Container widget for the context section in the menu."""

    context_changed = pyqtSignal()

    _container_style = """
        QWidget#contextSection {
            background: transparent;
        }
    """

    def __init__(
        self,
        context_manager: ContextManager,
        copy_callback: Optional[Callable[[], None]] = None,
        notification_manager=None,
        clipboard_manager=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.context_manager = context_manager
        self.copy_callback = copy_callback
        self.notification_manager = notification_manager
        self.clipboard_manager = clipboard_manager
        self._chips = []  # Store references to chips
        self.setObjectName("contextSection")
        self.setStyleSheet(self._container_style)

        self._setup_ui()
        self._rebuild_chips()

        # Subscribe to context changes
        self.context_manager.add_change_callback(self._on_context_changed)

    def _setup_ui(self):
        """Set up the widget UI."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(2)

        # Header with title, edit, copy and clear buttons
        self.header = ContextHeaderWidget()
        self.header.clear_requested.connect(self._on_clear_all)
        self.header.copy_requested.connect(self._on_copy_text)
        self.header.edit_requested.connect(self._on_edit_context)
        self.main_layout.addWidget(self.header)

        # Container for chips
        self.chips_container = QWidget()
        self.chips_layout = FlowLayout()
        self.chips_container.setLayout(self.chips_layout)
        self.main_layout.addWidget(self.chips_container)

    def _rebuild_chips(self):
        """Rebuild all chips from current context items."""
        self.chips_layout.clear_widgets()
        self._chips = []  # Store references to chips for copy handling

        items = self.context_manager.get_items()

        # Update header copy button state (enabled only if text content exists)
        has_text = self.context_manager.has_context()
        self.header.set_copy_enabled(has_text)

        if not items:
            # Show "No context" label when empty
            empty_label = QLabel("No context items")
            empty_label.setStyleSheet(
                "QLabel { color: #666666; font-size: 11px; padding: 4px 8px; }"
            )
            self.chips_layout.addWidget(empty_label)
            return

        # Separate images and text items, preserving original indices
        image_items = [(idx, item) for idx, item in enumerate(items) if item.item_type == ContextItemType.IMAGE]
        text_items = [(idx, item) for idx, item in enumerate(items) if item.item_type == ContextItemType.TEXT]

        # Display images first (with ascending numbering), then text
        image_number = 0
        for idx, item in image_items:
            image_number += 1
            chip = ImageContextChip(
                index=idx,
                image_number=image_number,
                image_data=item.data or "",
                media_type=item.media_type or "image/png",
            )
            chip.delete_requested.connect(self._on_chip_delete)
            chip.copy_requested.connect(self._on_chip_copy)
            self._chips.append(chip)
            self.chips_layout.add_widget(chip)

        # Add spacing between images and text if both exist
        if image_items and text_items:
            spacer = QWidget()
            spacer.setFixedHeight(4)
            self.chips_layout.addWidget(spacer)

        for idx, item in text_items:
            chip = TextContextChip(
                index=idx,
                text_content=item.content or "",
            )
            chip.delete_requested.connect(self._on_chip_delete)
            chip.copy_requested.connect(self._on_chip_copy)
            self._chips.append(chip)
            self.chips_layout.add_widget(chip)

    def _on_context_changed(self):
        """Handle context manager change notification."""
        # Rebuild chips on the main thread
        self._rebuild_chips()
        self.context_changed.emit()

    def _on_chip_delete(self, index: int):
        """Handle chip delete request."""
        self.context_manager.remove_item(index)

    def _on_chip_copy(self, index: int):
        """Handle chip copy request."""
        # Find the chip with this index and copy its content
        for chip in self._chips:
            if chip.index == index:
                chip.copy_to_clipboard()
                self._show_copied_notification()
                break

    def _on_clear_all(self):
        """Handle clear all request."""
        self.context_manager.clear_context()

    def _on_copy_text(self):
        """Handle copy text request from header button."""
        text_content = self.context_manager.get_context()
        if text_content:
            clipboard = QApplication.clipboard()
            clipboard.setText(text_content)
            self._show_copied_notification()

    def _on_edit_context(self):
        """Handle edit context request - open the context editor dialog."""
        if self.clipboard_manager is None:
            logger.warning("Cannot open context editor: clipboard_manager not available")
            return

        from modules.gui.context_editor_dialog import show_context_editor

        show_context_editor(
            self.context_manager,
            self.clipboard_manager,
            self.notification_manager,
        )

    def _show_copied_notification(self):
        """Show a 'Copied' notification."""
        if self.notification_manager:
            self.notification_manager.show_success_notification("Copied")

    def cleanup(self):
        """Clean up resources."""
        try:
            self.context_manager.remove_change_callback(self._on_context_changed)
        except Exception:
            pass


class LastInteractionChip(QWidget):
    """Chip widget for last interaction items (input/output/transcription)."""

    copy_requested = pyqtSignal()
    details_requested = pyqtSignal()

    _chip_style = """
        QWidget#lastInteractionChip {
            background-color: #3a3a3a;
            border: 1px solid #555555;
            border-radius: 12px;
            padding: 2px;
        }
    """

    _chip_hover_style = """
        QWidget#lastInteractionChip {
            background-color: #454545;
            border: 1px solid #555555;
            border-radius: 12px;
            padding: 2px;
        }
    """

    _chip_disabled_style = """
        QWidget#lastInteractionChip {
            background-color: #2a2a2a;
            border: 1px solid #444444;
            border-radius: 12px;
            padding: 2px;
        }
    """

    _label_style = """
        QLabel {
            color: #f0f0f0;
            font-size: 12px;
            padding: 2px 4px;
            background: transparent;
        }
    """

    _label_disabled_style = """
        QLabel {
            color: #666666;
            font-size: 12px;
            padding: 2px 4px;
            background: transparent;
        }
    """

    _icon_btn_style = """
        QPushButton {
            background: transparent;
            border: none;
            padding: 2px;
            min-width: 20px;
            max-width: 20px;
            min-height: 20px;
            max-height: 20px;
        }
    """

    def __init__(
        self,
        chip_type: str,
        content: Optional[str],
        title: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.chip_type = chip_type
        self.content = content
        self.title = title
        self._enabled = content is not None and len(content) > 0

        self.setObjectName("lastInteractionChip")
        self.setAttribute(Qt.WA_StyledBackground, True)

        if self._enabled:
            self.setStyleSheet(self._chip_style)
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setStyleSheet(self._chip_disabled_style)
            self.setCursor(Qt.ArrowCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(4)

        # Copy icon at the beginning
        self.copy_btn = IconButton("copy", size=16)
        self.copy_btn.setStyleSheet(self._icon_btn_style)
        self.copy_btn.setCursor(Qt.PointingHandCursor if self._enabled else Qt.ArrowCursor)
        self.copy_btn.setToolTip("Copy to clipboard")
        self.copy_btn.setEnabled(self._enabled)
        self.copy_btn.clicked.connect(self._on_copy_clicked)
        layout.addWidget(self.copy_btn)

        # Label with type name
        self.label = QLabel()
        self.label.setStyleSheet(self._label_style if self._enabled else self._label_disabled_style)
        self._set_display_text()
        layout.addWidget(self.label)

        # Details button (info icon) at the end
        self.details_btn = IconButton("info", size=16)
        self.details_btn.setStyleSheet(self._icon_btn_style)
        self.details_btn.setCursor(Qt.PointingHandCursor if self._enabled else Qt.ArrowCursor)
        self.details_btn.setToolTip("Show details")
        self.details_btn.setEnabled(self._enabled)
        self.details_btn.clicked.connect(self._on_details_clicked)
        layout.addWidget(self.details_btn)

        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

        # Set tooltip
        if self._enabled:
            self.setToolTip(self.content)
        else:
            self.setToolTip("No content available")

    def _set_display_text(self):
        """Set the display text for the label."""
        self.label.setText(self.chip_type.capitalize())

    def _on_copy_clicked(self):
        """Handle copy button click."""
        if self._enabled:
            self.copy_requested.emit()

    def _on_details_clicked(self):
        """Handle details button click."""
        if self._enabled:
            self.details_requested.emit()

    def mousePressEvent(self, event):
        """Handle mouse press - copy on click (except on buttons)."""
        if not self._enabled:
            super().mousePressEvent(event)
            return

        # Check if click is on button areas
        details_btn_rect = self.details_btn.geometry()
        copy_btn_rect = self.copy_btn.geometry()

        if not details_btn_rect.contains(event.pos()) and not copy_btn_rect.contains(
            event.pos()
        ):
            self._on_copy_clicked()
        super().mousePressEvent(event)

    def enterEvent(self, event):
        """Handle mouse enter - show hover state."""
        if self._enabled:
            self.setStyleSheet(self._chip_hover_style)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Handle mouse leave - restore normal state."""
        if self._enabled:
            self.setStyleSheet(self._chip_style)
        else:
            self.setStyleSheet(self._chip_disabled_style)
        super().leaveEvent(event)

    def copy_to_clipboard(self):
        """Copy chip content to clipboard."""
        if self.content:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.content)


class LastInteractionHeaderWidget(QWidget):
    """Header widget with 'Last interaction' label only."""

    _header_style = """
        QWidget {
            background: transparent;
        }
    """

    _title_style = """
        QLabel {
            color: #888888;
            font-size: 11px;
            font-weight: bold;
            padding: 2px 4px;
            background: transparent;
        }
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setStyleSheet(self._header_style)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 2)
        layout.setSpacing(4)

        title_label = QLabel("Last interaction")
        title_label.setStyleSheet(self._title_style)
        layout.addWidget(title_label)

        layout.addStretch()


class LastInteractionSectionWidget(QWidget):
    """Container widget for the last interaction section in the menu."""

    _container_style = """
        QWidget#lastInteractionSection {
            background: transparent;
        }
    """

    def __init__(
        self,
        history_service,
        notification_manager=None,
        clipboard_manager=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.history_service = history_service
        self.notification_manager = notification_manager
        self.clipboard_manager = clipboard_manager
        self._chips = []

        self.setObjectName("lastInteractionSection")
        self.setStyleSheet(self._container_style)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the widget UI."""
        from core.models import HistoryEntryType

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(2)

        # Header with title
        header = LastInteractionHeaderWidget()
        self.main_layout.addWidget(header)

        # Retrieve last interaction data
        last_text_entry = None
        last_speech_entry = None

        if self.history_service:
            last_text_entry = self.history_service.get_last_item_by_type(
                HistoryEntryType.TEXT
            )
            last_speech_entry = self.history_service.get_last_item_by_type(
                HistoryEntryType.SPEECH
            )

        input_content = last_text_entry.input_content if last_text_entry else None
        output_content = last_text_entry.output_content if last_text_entry else None
        transcription_content = (
            last_speech_entry.output_content if last_speech_entry else None
        )

        # Create horizontal layout for chips
        chips_container = QWidget()
        chips_layout = QHBoxLayout(chips_container)
        chips_layout.setContentsMargins(4, 0, 4, 4)
        chips_layout.setSpacing(6)

        # Create chips
        input_chip = LastInteractionChip(
            chip_type="input",
            content=input_content,
            title="Input Content",
        )
        input_chip.copy_requested.connect(lambda: self._on_copy(input_chip))
        input_chip.details_requested.connect(
            lambda: self._on_details("Input Content", input_content)
        )
        self._chips.append(input_chip)
        chips_layout.addWidget(input_chip)

        output_chip = LastInteractionChip(
            chip_type="output",
            content=output_content,
            title="Output Content",
        )
        output_chip.copy_requested.connect(lambda: self._on_copy(output_chip))
        output_chip.details_requested.connect(
            lambda: self._on_details("Output Content", output_content)
        )
        self._chips.append(output_chip)
        chips_layout.addWidget(output_chip)

        transcription_chip = LastInteractionChip(
            chip_type="transcription",
            content=transcription_content,
            title="Transcription",
        )
        transcription_chip.copy_requested.connect(
            lambda: self._on_copy(transcription_chip)
        )
        transcription_chip.details_requested.connect(
            lambda: self._on_details("Transcription", transcription_content)
        )
        self._chips.append(transcription_chip)
        chips_layout.addWidget(transcription_chip)

        chips_layout.addStretch()
        self.main_layout.addWidget(chips_container)

    def _on_copy(self, chip: LastInteractionChip):
        """Handle copy request from a chip."""
        chip.copy_to_clipboard()
        if self.notification_manager:
            self.notification_manager.show_success_notification("Copied")

    def _on_details(self, title: str, content: Optional[str]):
        """Handle details request - show preview dialog."""
        if content:
            from modules.gui.text_preview_dialog import show_preview_dialog

            show_preview_dialog(title, content)
