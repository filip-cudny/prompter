"""Chat-style message bubble widgets for PromptExecuteDialog."""

from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from core.context_manager import ContextItem, ContextItemType
from modules.gui.shared.theme import (
    QWIDGETSIZE_MAX,
    TEXT_CHANGE_DEBOUNCE_MS,
    get_text_edit_content_height,
)
from modules.gui.shared.widgets import (
    BUBBLE_TEXT_EDIT_MIN_HEIGHT,
    CollapsibleSectionHeader,
    ImageChipWidget,
    create_text_edit,
)

if TYPE_CHECKING:
    from modules.gui.prompt_execute_dialog.dialog import PromptExecuteDialog


class UserMessageBubble(QWidget):
    """Chat bubble widget for user messages.

    Features:
    - Collapsible header with "Message #N" label
    - Undo/redo buttons, wrap toggle
    - Image chips container
    - Editable text edit
    """

    text_changed = Signal()
    images_changed = Signal()
    delete_requested = Signal(str)

    def __init__(
        self,
        node_id: str,
        message_number: int,
        content: str = "",
        images: list[ContextItem] | None = None,
        show_delete_button: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.node_id = node_id
        self.message_number = message_number
        self._images = images or []
        self._image_chips: list[ImageChipWidget] = []

        self._undo_stack: list[str] = []
        self._redo_stack: list[str] = []
        self._last_text = content

        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(TEXT_CHANGE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._save_state_if_changed)

        self._setup_ui(content, show_delete_button)

    def _setup_ui(self, content: str, show_delete_button: bool):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.header = CollapsibleSectionHeader(
            f"Message #{self.message_number}",
            show_save_button=False,
            show_undo_redo=True,
            show_delete_button=show_delete_button,
            show_wrap_button=True,
        )
        layout.addWidget(self.header)

        self.images_container = QWidget()
        self.images_container.setStyleSheet("background: transparent;")
        self.images_layout = QHBoxLayout(self.images_container)
        self.images_layout.setContentsMargins(0, 0, 0, 4)
        self.images_layout.setSpacing(6)
        self.images_layout.addStretch()
        self.images_container.hide()
        layout.addWidget(self.images_container)

        self.text_edit = create_text_edit(
            placeholder="Type your message...\n(Ctrl+Enter: Close & get result to clipboard | Alt+Enter: Send & show | Ctrl+V: Paste image)",
            min_height=BUBBLE_TEXT_EDIT_MIN_HEIGHT,
        )
        self.text_edit.setPlainText(content)
        self.text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.text_edit)

        self.header.toggle_requested.connect(self._toggle_section)
        self.header.wrap_requested.connect(self._toggle_wrap)
        self.header.undo_requested.connect(self.undo)
        self.header.redo_requested.connect(self.redo)
        self.header.delete_requested.connect(lambda: self.delete_requested.emit(self.node_id))

        self._rebuild_image_chips()

        content_height = get_text_edit_content_height(self.text_edit, min_height=BUBBLE_TEXT_EDIT_MIN_HEIGHT)
        self.text_edit.setMinimumHeight(content_height)
        self.text_edit.setMaximumHeight(content_height)
        self.header.set_wrap_state(False)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

    def _toggle_section(self):
        is_visible = self.text_edit.isVisible()
        self.text_edit.setVisible(not is_visible)
        self.images_container.setVisible(not is_visible and bool(self._images))
        self.header.set_collapsed(is_visible)
        if is_visible:
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        elif self.header.is_wrapped():
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        else:
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

    def _toggle_wrap(self):
        is_wrapped = self.header.is_wrapped()
        new_wrapped = not is_wrapped
        self.header.set_wrap_state(new_wrapped)
        if new_wrapped:
            self.text_edit.setMinimumHeight(BUBBLE_TEXT_EDIT_MIN_HEIGHT)
            self.text_edit.setMaximumHeight(QWIDGETSIZE_MAX)
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        else:
            content_height = get_text_edit_content_height(self.text_edit, min_height=BUBBLE_TEXT_EDIT_MIN_HEIGHT)
            self.text_edit.setMinimumHeight(content_height)
            self.text_edit.setMaximumHeight(content_height)
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

    def _on_text_changed(self):
        self._save_timer.start()
        self.text_changed.emit()
        if not self.header.is_wrapped():
            content_height = get_text_edit_content_height(self.text_edit, min_height=BUBBLE_TEXT_EDIT_MIN_HEIGHT)
            self.text_edit.setMinimumHeight(content_height)
            self.text_edit.setMaximumHeight(content_height)

    def _save_state_if_changed(self):
        current = self.text_edit.toPlainText()
        if current != self._last_text:
            self._undo_stack.append(self._last_text)
            self._redo_stack.clear()
            self._last_text = current
            self._update_undo_redo_buttons()

    def _update_undo_redo_buttons(self):
        self.header.set_undo_redo_enabled(bool(self._undo_stack), bool(self._redo_stack))

    def undo(self):
        if not self._undo_stack:
            return
        current = self.text_edit.toPlainText()
        self._redo_stack.append(current)
        previous = self._undo_stack.pop()
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(previous)
        self.text_edit.blockSignals(False)
        self._last_text = previous
        self._update_undo_redo_buttons()

    def redo(self):
        if not self._redo_stack:
            return
        current = self.text_edit.toPlainText()
        self._undo_stack.append(current)
        next_state = self._redo_stack.pop()
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(next_state)
        self.text_edit.blockSignals(False)
        self._last_text = next_state
        self._update_undo_redo_buttons()

    def _rebuild_image_chips(self):
        for chip in self._image_chips:
            chip.deleteLater()
        self._image_chips.clear()

        while self.images_layout.count():
            self.images_layout.takeAt(0)

        if not self._images:
            self.images_container.hide()
            return

        self.images_container.show()

        for idx, item in enumerate(self._images):
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

    def _on_image_delete(self, index: int):
        if 0 <= index < len(self._images):
            del self._images[index]
            self._rebuild_image_chips()
            self.images_changed.emit()

    def _on_image_copy(self, index: int):
        if 0 <= index < len(self._image_chips):
            self._image_chips[index].copy_to_clipboard()

    def add_image(self, image: ContextItem):
        self._images.append(image)
        self._rebuild_image_chips()
        self.images_changed.emit()

    def get_content(self) -> str:
        return self.text_edit.toPlainText()

    def set_content(self, content: str):
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(content)
        self.text_edit.blockSignals(False)
        self._last_text = content

    def get_images(self) -> list[ContextItem]:
        return list(self._images)

    def set_message_number(self, number: int):
        self.message_number = number
        self.header.set_title(f"Message #{number}")

    def set_delete_button_visible(self, visible: bool):
        self.header.set_delete_button_visible(visible)


class AssistantBubble(QWidget):
    """Chat bubble widget for assistant (AI) responses.

    Features:
    - Collapsible header with "Output #N" label
    - Regenerate button (refresh-cw icon)
    - Branch navigation (prev/next arrows + "1/3" label)
    - Undo/redo buttons, wrap toggle
    - Editable text edit
    """

    text_changed = Signal()
    regenerate_requested = Signal(str)
    branch_prev_requested = Signal(str)
    branch_next_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(
        self,
        node_id: str,
        output_number: int,
        content: str = "",
        show_delete_button: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.node_id = node_id
        self.output_number = output_number

        self._undo_stack: list[str] = []
        self._redo_stack: list[str] = []
        self._last_text = content

        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(TEXT_CHANGE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._save_state_if_changed)

        self._setup_ui(content, show_delete_button)

    def _setup_ui(self, content: str, show_delete_button: bool):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.header = CollapsibleSectionHeader(
            f"Output #{self.output_number}",
            show_save_button=False,
            show_undo_redo=True,
            show_delete_button=show_delete_button,
            show_wrap_button=True,
            show_version_nav=True,
            show_regenerate_button=True,
        )
        layout.addWidget(self.header)

        self.text_edit = create_text_edit(
            placeholder="Output will appear here...",
            min_height=BUBBLE_TEXT_EDIT_MIN_HEIGHT,
        )
        self.text_edit.setPlainText(content)
        self.text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.text_edit)

        self.header.toggle_requested.connect(self._toggle_section)
        self.header.wrap_requested.connect(self._toggle_wrap)
        self.header.undo_requested.connect(self.undo)
        self.header.redo_requested.connect(self.redo)
        self.header.delete_requested.connect(lambda: self.delete_requested.emit(self.node_id))
        self.header.regenerate_requested.connect(lambda: self.regenerate_requested.emit(self.node_id))
        self.header.version_prev_requested.connect(lambda: self.branch_prev_requested.emit(self.node_id))
        self.header.version_next_requested.connect(lambda: self.branch_next_requested.emit(self.node_id))

        content_height = get_text_edit_content_height(self.text_edit, min_height=BUBBLE_TEXT_EDIT_MIN_HEIGHT)
        self.text_edit.setMinimumHeight(content_height)
        self.text_edit.setMaximumHeight(content_height)
        self.header.set_wrap_state(False)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

    def _toggle_section(self):
        is_visible = self.text_edit.isVisible()
        self.text_edit.setVisible(not is_visible)
        self.header.set_collapsed(is_visible)
        if is_visible:
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        elif self.header.is_wrapped():
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        else:
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

    def _toggle_wrap(self):
        is_wrapped = self.header.is_wrapped()
        new_wrapped = not is_wrapped
        self.header.set_wrap_state(new_wrapped)
        if new_wrapped:
            self.text_edit.setMinimumHeight(BUBBLE_TEXT_EDIT_MIN_HEIGHT)
            self.text_edit.setMaximumHeight(QWIDGETSIZE_MAX)
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        else:
            content_height = get_text_edit_content_height(self.text_edit, min_height=BUBBLE_TEXT_EDIT_MIN_HEIGHT)
            self.text_edit.setMinimumHeight(content_height)
            self.text_edit.setMaximumHeight(content_height)
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

    def _on_text_changed(self):
        self._save_timer.start()
        self.text_changed.emit()
        if not self.header.is_wrapped():
            content_height = get_text_edit_content_height(self.text_edit, min_height=BUBBLE_TEXT_EDIT_MIN_HEIGHT)
            self.text_edit.setMinimumHeight(content_height)
            self.text_edit.setMaximumHeight(content_height)

    def _save_state_if_changed(self):
        current = self.text_edit.toPlainText()
        if current != self._last_text:
            self._undo_stack.append(self._last_text)
            self._redo_stack.clear()
            self._last_text = current
            self._update_undo_redo_buttons()

    def _update_undo_redo_buttons(self):
        self.header.set_undo_redo_enabled(bool(self._undo_stack), bool(self._redo_stack))

    def undo(self):
        if not self._undo_stack:
            return
        current = self.text_edit.toPlainText()
        self._redo_stack.append(current)
        previous = self._undo_stack.pop()
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(previous)
        self.text_edit.blockSignals(False)
        self._last_text = previous
        self._update_undo_redo_buttons()

    def redo(self):
        if not self._redo_stack:
            return
        current = self.text_edit.toPlainText()
        self._undo_stack.append(current)
        next_state = self._redo_stack.pop()
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(next_state)
        self.text_edit.blockSignals(False)
        self._last_text = next_state
        self._update_undo_redo_buttons()

    def get_content(self) -> str:
        return self.text_edit.toPlainText()

    def set_content(self, content: str):
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(content)
        self.text_edit.blockSignals(False)
        self._last_text = content

    def set_output_number(self, number: int):
        self.output_number = number
        self.header.set_title(f"Output #{number}")

    def set_delete_button_visible(self, visible: bool):
        self.header.set_delete_button_visible(visible)

    def set_branch_info(self, current: int, total: int):
        """Update branch navigation display.

        Args:
            current: Current branch number (1-indexed)
            total: Total number of sibling branches
        """
        self.header.set_version_info(current, total)

    def set_regenerate_enabled(self, enabled: bool):
        """Enable or disable the regenerate button."""
        self.header.set_regenerate_button_enabled(enabled)

    def clear_undo_stack(self):
        """Clear the undo/redo stacks (e.g., after regeneration)."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._last_text = self.text_edit.toPlainText()
        self._update_undo_redo_buttons()
