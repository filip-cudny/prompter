"""Message share dialog for sending custom messages to prompts."""

from dataclasses import dataclass
from typing import Optional, Callable, List, Dict

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QWidget,
    QLabel,
    QSizePolicy,
    QScrollArea,
    QFrame,
    QSplitter,
)
from PyQt5.QtCore import Qt, QTimer, QEvent
from PyQt5.QtGui import QFont

from core.models import MenuItem, ExecutionResult
from core.context_manager import ContextManager, ContextItem, ContextItemType
from modules.gui.context_widgets import IconButton
from modules.gui.icons import create_icon
from modules.gui.shared_widgets import CollapsibleSectionHeader, ImageChipWidget
from modules.utils.ui_state import UIStateManager

_open_dialogs: Dict[str, "MessageShareDialog"] = {}


@dataclass
class ContextSectionState:
    """Snapshot of context section state for undo/redo."""
    images: List[ContextItem]
    text: str


@dataclass
class PromptInputState:
    """Snapshot of prompt input section state for undo/redo."""
    text: str


@dataclass
class OutputState:
    """Snapshot of output section state for undo/redo."""
    text: str


@dataclass
class ConversationTurn:
    """Single turn in multi-turn conversation."""
    turn_number: int
    message_text: str
    message_images: List[ContextItem]
    output_text: Optional[str] = None
    is_complete: bool = False


def show_message_share_dialog(
    menu_item: MenuItem,
    execution_callback: Callable[[MenuItem, bool], None],
    prompt_store_service=None,
    context_manager: Optional[ContextManager] = None,
    clipboard_manager=None,
):
    """Show the message share dialog.

    Args:
        menu_item: The prompt menu item to execute
        execution_callback: Callback to execute the prompt
        prompt_store_service: The prompt store service for execution
        context_manager: The context manager for loading/saving context
    """
    # Get unique key for this prompt window
    prompt_id = menu_item.data.get("prompt_id", "") if menu_item.data else ""
    window_key = prompt_id or str(id(menu_item))

    # Check if dialog for THIS prompt already exists
    if window_key in _open_dialogs:
        dialog = _open_dialogs[window_key]
        dialog.raise_()
        dialog.activateWindow()
        return

    def create_and_show():
        # Double-check after timer delay
        if window_key in _open_dialogs:
            _open_dialogs[window_key].raise_()
            _open_dialogs[window_key].activateWindow()
            return

        dialog = MessageShareDialog(
            menu_item,
            execution_callback,
            prompt_store_service,
            context_manager,
            clipboard_manager,
        )
        _open_dialogs[window_key] = dialog
        dialog.finished.connect(
            lambda: _open_dialogs.pop(window_key, None)
        )
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    QTimer.singleShot(75, create_and_show)


class MessageShareDialog(QDialog):
    """Dialog for typing a message to send to a prompt."""

    def __init__(
        self,
        menu_item: MenuItem,
        execution_callback: Callable[[MenuItem, bool], None],
        prompt_store_service=None,
        context_manager: Optional[ContextManager] = None,
        clipboard_manager=None,
        parent=None,
    ):
        super().__init__(parent)
        self.menu_item = menu_item
        self.execution_callback = execution_callback
        self._ui_state = UIStateManager()
        self._waiting_for_result = False
        self._prompt_store_service = prompt_store_service
        self.context_manager = context_manager
        self.clipboard_manager = clipboard_manager

        # Working state for context section
        self._current_images: List[ContextItem] = []
        self._image_chips: List[ImageChipWidget] = []

        # Working state for message section images
        self._message_images: List[ContextItem] = []
        self._message_image_chips: List[ImageChipWidget] = []

        # Track if output section has been shown
        self._output_section_shown = False

        # Multi-turn conversation state
        self._conversation_turns: List[ConversationTurn] = []
        self._current_turn_number: int = 0
        self._dynamic_sections: List[QWidget] = []  # Reply input sections
        self._output_sections: List[QWidget] = []  # Output sections for each turn

        # Separate undo/redo stacks for each section
        self._context_undo_stack: List[ContextSectionState] = []
        self._context_redo_stack: List[ContextSectionState] = []
        self._input_undo_stack: List[PromptInputState] = []
        self._input_redo_stack: List[PromptInputState] = []
        self._output_undo_stack: List[OutputState] = []
        self._output_redo_stack: List[OutputState] = []

        # Track last text for debounced state saving
        self._last_context_text = ""
        self._last_input_text = ""
        self._last_output_text = ""

        # Text change debounce timer (created early to avoid timing issues)
        self._text_change_timer = QTimer()
        self._text_change_timer.setSingleShot(True)
        self._text_change_timer.setInterval(500)
        self._text_change_timer.timeout.connect(self._save_text_states)

        # Extract prompt name for title
        prompt_name = (
            menu_item.data.get("prompt_name", "Prompt") if menu_item.data else "Prompt"
        )
        self.setWindowTitle(f"Message to: {prompt_name}")
        self.setMinimumSize(500, 400)
        self.resize(600, 500)
        self.setWindowFlags(Qt.Window)

        self._setup_ui()
        self._apply_styles()
        self._load_context()
        self._restore_ui_state()

        # Focus message input for immediate typing
        self.input_edit.setFocus()

    def _setup_ui(self):
        """Set up the dialog UI with three collapsible sections."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Scroll area for scrolling when many sections
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        # Container widget with splitter layout for all sections
        self.sections_container = QWidget()
        container_layout = QVBoxLayout(self.sections_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Splitter for resizable sections
        self.sections_splitter = QSplitter(Qt.Vertical)
        self.sections_splitter.setHandleWidth(4)
        self.sections_splitter.setChildrenCollapsible(False)
        # Allow splitter to grow beyond viewport for scrolling
        self.sections_splitter.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        # Section 1: Context (with save button)
        self.context_section = self._create_context_section()
        self.sections_splitter.addWidget(self.context_section)

        # Section 2: Prompt Input (no save button)
        self.input_section = self._create_input_section()
        self.sections_splitter.addWidget(self.input_section)

        # Section 3: Output (no save button) - NOT added initially
        self.output_section = self._create_output_section()
        # Output section is hidden until user clicks Alt+Enter

        # Spacer widget at the end to absorb extra space and push sections to top
        self._splitter_spacer = QWidget()
        self._splitter_spacer.setMinimumHeight(0)
        self._splitter_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.sections_splitter.addWidget(self._splitter_spacer)
        self.sections_splitter.setStretchFactor(self.sections_splitter.count() - 1, 1)

        container_layout.addWidget(self.sections_splitter)

        self.scroll_area.setWidget(self.sections_container)
        layout.addWidget(self.scroll_area)

        # Button bar (includes hint label)
        self._create_button_bar(layout)

        # Install event filters for keyboard handling
        self.context_text_edit.installEventFilter(self)
        self.input_edit.installEventFilter(self)
        # output_edit event filter is installed when output section is shown

    def _create_context_section(self) -> QWidget:
        """Create the collapsible context section with save button."""
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        section_layout = QVBoxLayout(container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)

        # Header with collapse toggle, undo/redo, and save button
        self.context_header = CollapsibleSectionHeader(
            "Context",
            show_save_button=True,
            show_undo_redo=True,
            hint_text="",
        )
        self.context_header.toggle_requested.connect(self._toggle_context_section)
        self.context_header.save_requested.connect(self._save_context)
        self.context_header.undo_requested.connect(self._undo_context)
        self.context_header.redo_requested.connect(self._redo_context)
        section_layout.addWidget(self.context_header)

        # Images row
        self.context_images_container = QWidget()
        self.context_images_container.setStyleSheet("background: transparent;")
        self.context_images_layout = QHBoxLayout(self.context_images_container)
        self.context_images_layout.setContentsMargins(0, 0, 0, 4)
        self.context_images_layout.setSpacing(6)
        self.context_images_layout.addStretch()
        section_layout.addWidget(self.context_images_container)
        self.context_images_container.hide()  # Hidden if no images

        # Text edit area
        self.context_text_edit = QTextEdit()
        self.context_text_edit.setFont(QFont("Menlo, Monaco, Consolas, monospace", 12))
        self.context_text_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        self.context_text_edit.setPlaceholderText("Context content...")
        self.context_text_edit.setMinimumHeight(80)
        self.context_text_edit.textChanged.connect(self._on_context_text_changed)
        section_layout.addWidget(self.context_text_edit)

        return container

    def _create_input_section(self) -> QWidget:
        """Create the collapsible prompt input section (no save button)."""
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        section_layout = QVBoxLayout(container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)

        # Header with collapse toggle and undo/redo (NO save button)
        self.input_header = CollapsibleSectionHeader(
            "Message",
            show_save_button=False,
            show_undo_redo=True,
            hint_text="",
        )
        self.input_header.toggle_requested.connect(self._toggle_input_section)
        self.input_header.undo_requested.connect(self._undo_input)
        self.input_header.redo_requested.connect(self._redo_input)
        section_layout.addWidget(self.input_header)

        # Images row (for pasted images)
        self.message_images_container = QWidget()
        self.message_images_container.setStyleSheet("background: transparent;")
        self.message_images_layout = QHBoxLayout(self.message_images_container)
        self.message_images_layout.setContentsMargins(0, 0, 0, 4)
        self.message_images_layout.setSpacing(6)
        self.message_images_layout.addStretch()
        section_layout.addWidget(self.message_images_container)
        self.message_images_container.hide()  # Hidden if no images

        # Text edit area
        self.input_edit = QTextEdit()
        self.input_edit.setFont(QFont("Menlo, Monaco, Consolas, monospace", 12))
        self.input_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        self.input_edit.setPlaceholderText("Type your message here...")
        self.input_edit.setToolTip("Type and send message with prompt")
        self.input_edit.setMinimumHeight(100)
        self.input_edit.textChanged.connect(self._on_input_text_changed)
        section_layout.addWidget(self.input_edit)

        return container

    def _create_output_section(self) -> QWidget:
        """Create the collapsible output section (no save button)."""
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        section_layout = QVBoxLayout(container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)

        # Header with collapse toggle and undo/redo (NO save button)
        self.output_header = CollapsibleSectionHeader(
            "Output",
            show_save_button=False,
            show_undo_redo=True,
            hint_text="",
        )
        self.output_header.toggle_requested.connect(self._toggle_output_section)
        self.output_header.undo_requested.connect(self._undo_output)
        self.output_header.redo_requested.connect(self._redo_output)
        section_layout.addWidget(self.output_header)

        # Text edit area
        self.output_edit = QTextEdit()
        self.output_edit.setFont(QFont("Menlo, Monaco, Consolas, monospace", 12))
        self.output_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        self.output_edit.setPlaceholderText("Output will appear here...")
        self.output_edit.setMinimumHeight(100)
        self.output_edit.textChanged.connect(self._on_output_text_changed)
        section_layout.addWidget(self.output_edit)

        return container

    def _create_button_bar(self, layout: QVBoxLayout):
        """Create button bar with hint label and send actions."""
        button_widget = QWidget()
        button_bar = QHBoxLayout(button_widget)
        button_bar.setContentsMargins(12, 0, 12, 0)

        # Hint label on the left
        hint_label = QLabel("Ctrl+Enter: Send & copy | Alt+Enter: Send & show result")
        hint_label.setStyleSheet("QLabel { color: #666666; font-size: 11px; }")
        button_bar.addWidget(hint_label)

        button_bar.addStretch()

        # Reply button (hidden until output received)
        self.reply_btn = QPushButton()
        self.reply_btn.setIcon(create_icon("message-square-reply", "#444444", 16))
        self.reply_btn.setToolTip("Reply to continue conversation")
        self.reply_btn.clicked.connect(self._on_reply)
        self.reply_btn.setVisible(False)
        button_bar.addWidget(self.reply_btn)

        # Send & Show button (Alt+Enter)
        self.send_show_btn = QPushButton()
        self.send_show_btn.setIcon(create_icon("send-horizontal", "#444444", 16))
        self.send_show_btn.setToolTip("Send & Show Result (Alt+Enter)")
        self.send_show_btn.clicked.connect(self._on_send_show)
        self.send_show_btn.setEnabled(False)  # Disabled until message has content
        button_bar.addWidget(self.send_show_btn)

        # Send & Copy button (Ctrl+Enter) - default
        self.send_copy_btn = QPushButton()
        self.send_copy_btn.setIcon(create_icon("copy", "#444444", 16))
        self.send_copy_btn.setToolTip("Send & Copy to Clipboard (Ctrl+Enter)")
        self.send_copy_btn.clicked.connect(self._on_send_copy)
        self.send_copy_btn.setDefault(True)
        self.send_copy_btn.setEnabled(False)  # Disabled until message has content
        button_bar.addWidget(self.send_copy_btn)

        layout.addWidget(button_widget)

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
                padding: 8px;
                selection-background-color: #3d6a99;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: #f0f0f0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 12px;
                min-width: 32px;
                min-height: 24px;
            }
            QPushButton:hover {
                background-color: #454545;
            }
            QPushButton:pressed {
                background-color: #505050;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #444444;
                border: 1px solid #3a3a3a;
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
                height: 0;
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
                width: 0;
            }
            QScrollArea {
                background-color: #2b2b2b;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: #2b2b2b;
            }
            QSplitter {
                background-color: #2b2b2b;
            }
            QSplitter::handle {
                background-color: transparent;
            }
            QSplitter::handle:vertical {
                height: 4px;
                background-color: transparent;
            }
            QSplitter::handle:vertical:hover {
                background-color: transparent;
            }
        """
        )

    # --- Context loading/saving ---

    def _load_context(self):
        """Load context from context_manager."""
        if not self.context_manager:
            return

        items = self.context_manager.get_items()

        # Separate images and text
        self._current_images = [
            ContextItem(item_type=item.item_type, data=item.data, media_type=item.media_type)
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
        self.context_text_edit.setPlainText(text_content)
        self._last_context_text = text_content

        # Clear undo/redo stacks
        self._context_undo_stack.clear()
        self._context_redo_stack.clear()
        self._update_undo_redo_buttons()

    def _save_context(self):
        """Save context changes to context_manager."""
        if not self.context_manager:
            return

        self.context_manager.clear_context()

        # Add images first
        for image_item in self._current_images:
            self.context_manager.append_context_image(
                image_item.data, image_item.media_type or "image/png"
            )

        # Add text
        text_content = self.context_text_edit.toPlainText().strip()
        if text_content:
            self.context_manager.append_context(text_content)

    def _rebuild_image_chips(self):
        """Rebuild image chips from current state."""
        for chip in self._image_chips:
            chip.deleteLater()
        self._image_chips.clear()

        while self.context_images_layout.count():
            self.context_images_layout.takeAt(0)

        if not self._current_images:
            self.context_images_container.hide()
            return

        self.context_images_container.show()

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
            self.context_images_layout.addWidget(chip)

        self.context_images_layout.addStretch()

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

    def _paste_image_from_clipboard(self) -> bool:
        """Paste image from clipboard to context. Returns True if image was pasted."""
        if not self.clipboard_manager or not self.clipboard_manager.has_image():
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
            return True
        return False

    # --- Message image methods ---

    def _rebuild_message_image_chips(self):
        """Rebuild message image chips from current state."""
        for chip in self._message_image_chips:
            chip.deleteLater()
        self._message_image_chips.clear()

        while self.message_images_layout.count():
            self.message_images_layout.takeAt(0)

        if not self._message_images:
            self.message_images_container.hide()
            return

        self.message_images_container.show()

        for idx, item in enumerate(self._message_images):
            chip = ImageChipWidget(
                index=idx,
                image_number=idx + 1,
                image_data=item.data or "",
                media_type=item.media_type or "image/png",
            )
            chip.delete_requested.connect(self._on_message_image_delete)
            chip.copy_requested.connect(self._on_message_image_copy)
            self._message_image_chips.append(chip)
            self.message_images_layout.addWidget(chip)

        self.message_images_layout.addStretch()

    def _on_message_image_delete(self, index: int):
        """Handle message image chip delete request."""
        if 0 <= index < len(self._message_images):
            del self._message_images[index]
            self._rebuild_message_image_chips()

    def _on_message_image_copy(self, index: int):
        """Handle message image chip copy request."""
        if 0 <= index < len(self._message_image_chips):
            self._message_image_chips[index].copy_to_clipboard()

    def _paste_image_to_message(self) -> bool:
        """Paste image from clipboard to message. Returns True if image was pasted."""
        if not self.clipboard_manager or not self.clipboard_manager.has_image():
            return False

        image_data = self.clipboard_manager.get_image_data()
        if image_data:
            base64_data, media_type = image_data
            new_image = ContextItem(
                item_type=ContextItemType.IMAGE,
                data=base64_data,
                media_type=media_type,
            )
            self._message_images.append(new_image)
            self._rebuild_message_image_chips()
            self._update_send_buttons_state()  # Message now has content (image)
            return True
        return False

    # --- Section toggle methods ---

    def _toggle_context_section(self):
        """Toggle context section visibility."""
        is_visible = self.context_text_edit.isVisible()
        self.context_text_edit.setVisible(not is_visible)
        self.context_images_container.setVisible(not is_visible and len(self._current_images) > 0)
        self.context_header.set_collapsed(is_visible)
        self._save_section_state("context", collapsed=is_visible)
        # Adjust section sizing for splitter
        collapsed_height = self.context_header.sizeHint().height() + 8
        if is_visible:
            # Collapsing - fix height to header only
            self.context_section.setMaximumHeight(collapsed_height)
            self._set_splitter_section_height(0, collapsed_height)
        else:
            # Expanding - restore flexible sizing
            self.context_section.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX

    def _toggle_input_section(self):
        """Toggle input section visibility."""
        is_visible = self.input_edit.isVisible()
        self.input_edit.setVisible(not is_visible)
        self.input_header.set_collapsed(is_visible)
        self._save_section_state("input", collapsed=is_visible)
        # Adjust section sizing for splitter
        collapsed_height = self.input_header.sizeHint().height() + 8
        if is_visible:
            self.input_section.setMaximumHeight(collapsed_height)
            self._set_splitter_section_height(1, collapsed_height)
        else:
            self.input_section.setMaximumHeight(16777215)

    def _toggle_output_section(self):
        """Toggle output section visibility."""
        if not self._output_section_shown:
            # Output not yet in layout - add it now
            self._expand_output_section()
            return

        is_visible = self.output_edit.isVisible()
        self.output_edit.setVisible(not is_visible)
        self.output_header.set_collapsed(is_visible)
        self._save_section_state("output", collapsed=is_visible)
        # Adjust section sizing for splitter
        collapsed_height = self.output_header.sizeHint().height() + 8
        if is_visible:
            self.output_section.setMaximumHeight(collapsed_height)
            # Output section index is 2 when shown
            self._set_splitter_section_height(2, collapsed_height)
        else:
            self.output_section.setMaximumHeight(16777215)

    def _save_section_state(self, section: str, collapsed: bool):
        """Save section collapsed state."""
        key = f"message_share_dialog.sections.{section}.collapsed"
        self._ui_state.set(key, collapsed)

    def _set_splitter_section_height(self, index: int, height: int):
        """Set a specific section's height in the splitter."""
        sizes = self.sections_splitter.sizes()
        if index < len(sizes):
            # Calculate difference and redistribute to other sections
            diff = sizes[index] - height
            sizes[index] = height
            # Give extra space to the last non-spacer section or spacer
            if diff > 0 and len(sizes) > 1:
                # Find a section to give the extra space to
                for i in range(len(sizes) - 1, -1, -1):
                    if i != index:
                        sizes[i] += diff
                        break
            self.sections_splitter.setSizes(sizes)

    def _set_splitter_section_height_for_widget(self, widget: QWidget, height: int):
        """Set a widget's height in the splitter by finding its index."""
        for i in range(self.sections_splitter.count()):
            if self.sections_splitter.widget(i) == widget:
                self._set_splitter_section_height(i, height)
                break

    def _scroll_to_bottom(self):
        """Scroll the scroll area to the bottom."""
        # Use a small delay to ensure layout is complete before scrolling
        QTimer.singleShot(50, self._do_scroll_to_bottom)

    def _do_scroll_to_bottom(self):
        """Perform the actual scroll to bottom."""
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    # --- UI state persistence ---

    def _restore_ui_state(self):
        """Restore collapsed states from saved state. Splitter sizes are restored in showEvent."""
        # Restore geometry
        geometry = self._ui_state.get("message_share_dialog.geometry")
        if geometry:
            self._restore_geometry(geometry)

        # Get collapsed states
        context_collapsed = self._ui_state.get("message_share_dialog.sections.context.collapsed", False)
        input_collapsed = self._ui_state.get("message_share_dialog.sections.input.collapsed", False)

        # Store splitter sizes for restoration in showEvent (after dialog is visible)
        self._pending_splitter_sizes = self._ui_state.get("message_share_dialog.splitter_sizes")

        # Apply collapsed states (visual state only, sizes applied in showEvent)
        if context_collapsed:
            collapsed_height = self.context_header.sizeHint().height() + 8
            self.context_text_edit.hide()
            self.context_images_container.hide()
            self.context_header.set_collapsed(True)
            self.context_section.setMaximumHeight(collapsed_height)
        if input_collapsed:
            collapsed_height = self.input_header.sizeHint().height() + 8
            self.input_edit.hide()
            self.input_header.set_collapsed(True)
            self.input_section.setMaximumHeight(collapsed_height)

    def showEvent(self, event):
        """Handle show event - restore splitter sizes after dialog is visible."""
        super().showEvent(event)
        # Restore splitter sizes after dialog is shown (Qt needs geometry to be finalized)
        if hasattr(self, '_pending_splitter_sizes') and self._pending_splitter_sizes:
            if len(self._pending_splitter_sizes) == self.sections_splitter.count():
                # Use timer to ensure layout is complete
                QTimer.singleShot(0, self._apply_pending_splitter_sizes)

    def _apply_pending_splitter_sizes(self):
        """Apply pending splitter sizes after layout is complete."""
        if not hasattr(self, '_pending_splitter_sizes') or not self._pending_splitter_sizes:
            return
        if len(self._pending_splitter_sizes) == self.sections_splitter.count():
            self.sections_splitter.setSizes(self._pending_splitter_sizes)
        self._pending_splitter_sizes = None

    def _restore_geometry(self, geometry: dict):
        """Restore window geometry."""
        width = geometry.get("width", 600)
        height = geometry.get("height", 500)
        x = geometry.get("x")
        y = geometry.get("y")

        self.resize(max(width, 500), max(height, 400))

        if x is not None and y is not None:
            self.move(x, y)

    def closeEvent(self, event):
        """Save geometry and splitter sizes on close and disconnect signals."""
        geom = self.geometry()
        self._ui_state.set(
            "message_share_dialog.geometry",
            {
                "x": geom.x(),
                "y": geom.y(),
                "width": geom.width(),
                "height": geom.height(),
            },
        )
        # Save splitter sizes
        self._ui_state.set(
            "message_share_dialog.splitter_sizes",
            self.sections_splitter.sizes(),
        )
        # Disconnect from execution signal if connected
        self._disconnect_execution_signal()
        super().closeEvent(event)

    # --- Undo/Redo: Context Section ---

    def _get_context_state(self) -> ContextSectionState:
        """Get current context state."""
        return ContextSectionState(
            images=[
                ContextItem(item_type=img.item_type, data=img.data, media_type=img.media_type)
                for img in self._current_images
            ],
            text=self.context_text_edit.toPlainText(),
        )

    def _restore_context_state(self, state: ContextSectionState):
        """Restore context state."""
        self._current_images = [
            ContextItem(item_type=img.item_type, data=img.data, media_type=img.media_type)
            for img in state.images
        ]
        self._rebuild_image_chips()
        self.context_text_edit.blockSignals(True)
        self.context_text_edit.setPlainText(state.text)
        self._last_context_text = state.text
        self.context_text_edit.blockSignals(False)

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
        self._context_redo_stack.append(self._get_context_state())
        state = self._context_undo_stack.pop()
        self._restore_context_state(state)
        self._update_undo_redo_buttons()

    def _redo_context(self):
        """Redo last undone context change."""
        if not self._context_redo_stack:
            return
        self._context_undo_stack.append(self._get_context_state())
        state = self._context_redo_stack.pop()
        self._restore_context_state(state)
        self._update_undo_redo_buttons()

    # --- Undo/Redo: Input Section ---

    def _get_input_state(self) -> PromptInputState:
        """Get current input state."""
        return PromptInputState(text=self.input_edit.toPlainText())

    def _restore_input_state(self, state: PromptInputState):
        """Restore input state."""
        self.input_edit.blockSignals(True)
        self.input_edit.setPlainText(state.text)
        self._last_input_text = state.text
        self.input_edit.blockSignals(False)

    def _undo_input(self):
        """Undo last input change."""
        if not self._input_undo_stack:
            return
        self._input_redo_stack.append(self._get_input_state())
        state = self._input_undo_stack.pop()
        self._restore_input_state(state)
        self._update_undo_redo_buttons()

    def _redo_input(self):
        """Redo last undone input change."""
        if not self._input_redo_stack:
            return
        self._input_undo_stack.append(self._get_input_state())
        state = self._input_redo_stack.pop()
        self._restore_input_state(state)
        self._update_undo_redo_buttons()

    # --- Undo/Redo: Output Section ---

    def _get_output_state(self) -> OutputState:
        """Get current output state."""
        return OutputState(text=self.output_edit.toPlainText())

    def _restore_output_state(self, state: OutputState):
        """Restore output state."""
        self.output_edit.blockSignals(True)
        self.output_edit.setPlainText(state.text)
        self._last_output_text = state.text
        self.output_edit.blockSignals(False)

    def _undo_output(self):
        """Undo last output change."""
        if not self._output_undo_stack:
            return
        self._output_redo_stack.append(self._get_output_state())
        state = self._output_undo_stack.pop()
        self._restore_output_state(state)
        self._update_undo_redo_buttons()

    def _redo_output(self):
        """Redo last undone output change."""
        if not self._output_redo_stack:
            return
        self._output_undo_stack.append(self._get_output_state())
        state = self._output_redo_stack.pop()
        self._restore_output_state(state)
        self._update_undo_redo_buttons()

    # --- Common undo/redo ---

    def _update_undo_redo_buttons(self):
        """Update undo/redo button states for all sections."""
        self.context_header.set_undo_redo_enabled(
            len(self._context_undo_stack) > 0,
            len(self._context_redo_stack) > 0,
        )
        self.input_header.set_undo_redo_enabled(
            len(self._input_undo_stack) > 0,
            len(self._input_redo_stack) > 0,
        )
        self.output_header.set_undo_redo_enabled(
            len(self._output_undo_stack) > 0,
            len(self._output_redo_stack) > 0,
        )

    # --- Dynamic section undo/redo ---

    def _undo_dynamic_section(self, section: QWidget):
        """Undo last change in a dynamic section."""
        if not section.undo_stack:
            return
        current = section.text_edit.toPlainText()
        section.redo_stack.append(current)
        previous = section.undo_stack.pop()
        section.text_edit.blockSignals(True)
        section.text_edit.setPlainText(previous)
        section.text_edit.blockSignals(False)
        section.last_text = previous
        self._update_dynamic_section_buttons(section)

    def _redo_dynamic_section(self, section: QWidget):
        """Redo last undone change in a dynamic section."""
        if not section.redo_stack:
            return
        current = section.text_edit.toPlainText()
        section.undo_stack.append(current)
        next_state = section.redo_stack.pop()
        section.text_edit.blockSignals(True)
        section.text_edit.setPlainText(next_state)
        section.text_edit.blockSignals(False)
        section.last_text = next_state
        self._update_dynamic_section_buttons(section)

    def _schedule_dynamic_state_save(self, section: QWidget):
        """Schedule state save for dynamic section (debounced)."""
        if not hasattr(section, '_save_timer'):
            section._save_timer = QTimer()
            section._save_timer.setSingleShot(True)
            section._save_timer.setInterval(500)
            section._save_timer.timeout.connect(lambda s=section: self._save_dynamic_state(s))
        section._save_timer.start()

    def _save_dynamic_state(self, section: QWidget):
        """Save state for a dynamic section if text changed."""
        current = section.text_edit.toPlainText()
        if current != section.last_text:
            section.undo_stack.append(section.last_text)
            section.redo_stack.clear()
            section.last_text = current
            self._update_dynamic_section_buttons(section)

    def _update_dynamic_section_buttons(self, section: QWidget):
        """Update undo/redo buttons for a dynamic section."""
        section.header.set_undo_redo_enabled(
            len(section.undo_stack) > 0,
            len(section.redo_stack) > 0
        )

    # --- Section deletion ---

    def _delete_section(self, section: QWidget):
        """Delete a single dynamic section (only the one clicked)."""
        # Handle Message section deletion
        if section in self._dynamic_sections:
            if section != self._dynamic_sections[-1]:
                return  # Only allow deleting last message

            # Remove only the message section
            self._dynamic_sections.remove(section)
            section.setParent(None)
            section.deleteLater()

        # Handle Output section deletion
        elif section in self._output_sections:
            if section != self._output_sections[-1]:
                return  # Only allow deleting last output

            # Remove only the output section
            self._output_sections.remove(section)
            section.setParent(None)
            section.deleteLater()

        # Update delete button visibility on remaining sections
        self._update_delete_button_visibility()

        # Show reply button if we have output to reply to
        if self._output_section_shown or self._output_sections:
            self.reply_btn.setVisible(True)

        self._update_send_buttons_state()

    def _update_delete_button_visibility(self):
        """Show delete button only on the absolute last section (bottom-most)."""
        # Hide delete on all dynamic sections
        for section in self._dynamic_sections:
            section.header.set_delete_button_visible(False)
        for section in self._output_sections:
            section.header.set_delete_button_visible(False)

        # Determine which section is at the bottom
        # Sections alternate: Message -> Output -> Message -> Output
        # Message #N has turn_number = N+1, Output #N has turn_number = N
        # When user clicks Reply after Output #N, Message #N is created (turn N+1)
        # So if both exist, compare turn numbers to find the bottom one

        if self._dynamic_sections and self._output_sections:
            msg_turn = self._dynamic_sections[-1].turn_number
            out_turn = self._output_sections[-1].turn_number
            # Message section's turn_number is the turn it was created FOR
            # Output section's turn_number is the turn it displays results FOR
            # If msg_turn > out_turn, message is at the bottom (user is typing reply)
            # If out_turn >= msg_turn, output is at the bottom (just received response)
            if msg_turn > out_turn:
                self._dynamic_sections[-1].header.set_delete_button_visible(True)
            else:
                self._output_sections[-1].header.set_delete_button_visible(True)
        elif self._dynamic_sections:
            self._dynamic_sections[-1].header.set_delete_button_visible(True)
        elif self._output_sections:
            self._output_sections[-1].header.set_delete_button_visible(True)

    def _update_send_buttons_state(self):
        """Enable/disable send buttons based on current input content."""
        # Check current input section (could be original or reply)
        if self._dynamic_sections:
            section = self._dynamic_sections[-1]
            has_text = bool(section.text_edit.toPlainText().strip())
            has_images = bool(section.turn_images)
        else:
            has_text = bool(self.input_edit.toPlainText().strip())
            has_images = bool(self._message_images)

        has_message = has_text or has_images
        can_send = has_message and not self._waiting_for_result

        self.send_show_btn.setEnabled(can_send)
        self.send_copy_btn.setEnabled(can_send)

        # Update icon colors based on enabled state
        icon_color = "#f0f0f0" if can_send else "#444444"
        self.send_show_btn.setIcon(create_icon("send-horizontal", icon_color, 16))
        self.send_copy_btn.setIcon(create_icon("copy", icon_color, 16))

    def _on_context_text_changed(self):
        """Handle context text changes - debounce state saving."""
        self._text_change_timer.start()

    def _on_input_text_changed(self):
        """Handle input text changes - debounce state saving and update buttons."""
        self._text_change_timer.start()
        self._update_send_buttons_state()

    def _on_output_text_changed(self):
        """Handle output text changes - debounce state saving."""
        self._text_change_timer.start()

    def _save_text_states(self):
        """Save state if text has significantly changed in any section."""
        # Context
        current_context = self.context_text_edit.toPlainText()
        if current_context != self._last_context_text:
            state = ContextSectionState(
                images=[
                    ContextItem(item_type=img.item_type, data=img.data, media_type=img.media_type)
                    for img in self._current_images
                ],
                text=self._last_context_text,
            )
            self._context_undo_stack.append(state)
            self._context_redo_stack.clear()
            self._last_context_text = current_context

        # Input
        current_input = self.input_edit.toPlainText()
        if current_input != self._last_input_text:
            state = PromptInputState(text=self._last_input_text)
            self._input_undo_stack.append(state)
            self._input_redo_stack.clear()
            self._last_input_text = current_input

        # Output
        current_output = self.output_edit.toPlainText()
        if current_output != self._last_output_text:
            state = OutputState(text=self._last_output_text)
            self._output_undo_stack.append(state)
            self._output_redo_stack.clear()
            self._last_output_text = current_output

        self._update_undo_redo_buttons()

    # --- Execution ---

    def _get_prompt_store_service(self):
        """Get the prompt store service for execution."""
        return self._prompt_store_service

    def _connect_execution_signal(self):
        """Connect to execution completed signal."""
        service = self._get_prompt_store_service()
        if service and hasattr(service, "_menu_coordinator"):
            try:
                service._menu_coordinator.execution_completed.connect(
                    self._on_execution_result
                )
            except Exception:
                pass

    def _disconnect_execution_signal(self):
        """Disconnect from execution completed signal."""
        service = self._get_prompt_store_service()
        if service and hasattr(service, "_menu_coordinator"):
            try:
                service._menu_coordinator.execution_completed.disconnect(
                    self._on_execution_result
                )
            except Exception:
                pass

    def _execute_with_message(self, message: str, keep_open: bool = False):
        """Execute the prompt with conversation history.

        Uses working context (images + text) from dialog, NOT from persistent storage.
        Context is sent with the prompt but NOT saved to context_manager.

        Args:
            message: The message to use as input (ignored if dynamic sections exist)
            keep_open: If True, keep dialog open and show result
        """
        # Get current input from reply section if exists, otherwise original input
        if self._dynamic_sections:
            section = self._dynamic_sections[-1]
            msg_text = section.text_edit.toPlainText()
            msg_images = list(section.turn_images)
        else:
            msg_text = message
            msg_images = list(self._message_images)

        # Validate message has content
        if not msg_text.strip() and not msg_images:
            return

        # Get the prompt store service
        service = self._get_prompt_store_service()
        if not service:
            if keep_open:
                self._expand_output_section()
                self.output_edit.setPlainText("Error: Prompt service not available")
            return

        # Record turn in conversation history
        if self._current_turn_number == 0:
            self._current_turn_number = 1

        turn = ConversationTurn(
            turn_number=self._current_turn_number,
            message_text=msg_text,
            message_images=msg_images,
        )
        self._conversation_turns.append(turn)

        # Build conversation data for API
        conv_data = self._build_conversation_data()

        # For backward compatibility, also build full_message for single-turn case
        working_context_text = self.context_text_edit.toPlainText().strip()
        full_message = msg_text
        if len(self._conversation_turns) == 1 and working_context_text:
            full_message = f"<context>\n{working_context_text}\n</context>\n\n{msg_text}"

        # Create a modified menu item with conversation data
        modified_item = MenuItem(
            id=self.menu_item.id,
            label=self.menu_item.label,
            item_type=self.menu_item.item_type,
            action=self.menu_item.action,
            data={
                **(self.menu_item.data or {}),
                "custom_context": full_message,
                "conversation_data": conv_data,
            },
            enabled=self.menu_item.enabled,
        )

        if keep_open:
            # Connect to receive result
            self._waiting_for_result = True
            self._connect_execution_signal()

            # Create output section for this turn
            if self._current_turn_number == 1:
                # First turn uses existing output section
                self._expand_output_section()
                self.output_edit.setPlainText("Executing...")
            else:
                # Subsequent turns create new output section
                output_section = self._create_dynamic_output_section(self._current_turn_number)
                self._output_sections.append(output_section)
                # Insert before spacer
                self.sections_splitter.insertWidget(self.sections_splitter.count() - 1, output_section)
                output_section.text_edit.installEventFilter(self)
                output_section.text_edit.setPlainText("Executing...")
                self._update_delete_button_visibility()
                self._scroll_to_bottom()

            # Disable buttons during execution
            self.send_show_btn.setEnabled(False)
            self.send_copy_btn.setEnabled(False)

        # Execute using the prompt execution handler
        for handler in service.execution_service.handlers:
            if handler.can_handle(modified_item):
                result = handler.execute(modified_item, full_message)
                if not keep_open:
                    self.accept()
                return

        # Fallback: use execution callback
        if self.execution_callback:
            if self.menu_item.data:
                self.menu_item.data["custom_context"] = full_message
            self.execution_callback(self.menu_item, False)
            if not keep_open:
                self.accept()

    def _build_conversation_data(self) -> dict:
        """Build conversation history for API."""
        context_text = self.context_text_edit.toPlainText().strip()
        context_images = [
            {"data": img.data, "media_type": img.media_type or "image/png"}
            for img in self._current_images
        ]

        turns = []
        for i, turn in enumerate(self._conversation_turns):
            turn_data = {
                "role": "user",
                "text": turn.message_text,
                "images": [
                    {"data": img.data, "media_type": img.media_type or "image/png"}
                    for img in turn.message_images
                ],
            }
            # First turn includes context
            if i == 0:
                turn_data["context_text"] = context_text
                turn_data["context_images"] = context_images

            turns.append(turn_data)

            if turn.is_complete and turn.output_text:
                turns.append({"role": "assistant", "text": turn.output_text})

        return {"turns": turns}

    def _expand_output_section(self):
        """Expand output section - add to splitter if first time."""
        if not self._output_section_shown:
            # First time showing output - insert before spacer
            self.sections_splitter.insertWidget(self.sections_splitter.count() - 1, self.output_section)
            self.output_edit.installEventFilter(self)
            self._output_section_shown = True
            self.output_edit.setVisible(True)
            self.output_header.set_collapsed(False)
            self._scroll_to_bottom()
        elif not self.output_edit.isVisible():
            # Already in splitter, just expand
            self.output_edit.setVisible(True)
            self.output_header.set_collapsed(False)
            self._save_section_state("output", collapsed=False)
            self._scroll_to_bottom()

    def _on_execution_result(self, result: ExecutionResult):
        """Handle execution result for multi-turn conversation."""
        if not self._waiting_for_result:
            return

        self._waiting_for_result = False
        self._disconnect_execution_signal()

        # Mark the current turn as complete and store output
        if self._conversation_turns:
            self._conversation_turns[-1].output_text = result.content if result.success else None
            self._conversation_turns[-1].is_complete = True

        # Show Reply button now that we have output
        self.reply_btn.setVisible(True)
        self.reply_btn.setIcon(create_icon("message-square-reply", "#f0f0f0", 16))

        # Update send buttons state
        self._update_send_buttons_state()

        # Get the correct output text edit based on turn number
        if self._current_turn_number == 1 or not self._output_sections:
            output_edit = self.output_edit  # Original output section
        else:
            output_edit = self._output_sections[-1].text_edit

        # Display result
        if result.success and result.content:
            output_edit.setPlainText(result.content)
        elif result.error:
            output_edit.setPlainText(f"Error: {result.error}")
        else:
            output_edit.setPlainText("No output received")

        self._scroll_to_bottom()

    def _on_send_copy(self):
        """Ctrl+Enter: Send, copy result to clipboard, close window."""
        message = self.input_edit.toPlainText()
        has_content = bool(message.strip()) or bool(self._message_images)
        if not has_content:
            self.close()
            return
        self._execute_with_message(message, keep_open=False)

    def _on_send_show(self):
        """Alt+Enter: Send, show result in window, stay open."""
        message = self.input_edit.toPlainText()
        has_content = bool(message.strip()) or bool(self._message_images)
        if not has_content:
            return
        self._execute_with_message(message, keep_open=True)

    def _on_reply(self):
        """Add new input section for reply."""
        self._current_turn_number += 1
        section = self._create_reply_section(self._current_turn_number)
        self._dynamic_sections.append(section)
        # Insert before spacer
        self.sections_splitter.insertWidget(self.sections_splitter.count() - 1, section)
        section.text_edit.installEventFilter(self)
        self.reply_btn.setVisible(False)
        section.text_edit.setFocus()
        self._update_delete_button_visibility()
        self._update_send_buttons_state()
        self._scroll_to_bottom()

    def _create_reply_section(self, turn_number: int) -> QWidget:
        """Create input section for a reply turn (displayed as Message)."""
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = CollapsibleSectionHeader(
            f"Message #{turn_number - 1}",
            show_save_button=False,
            show_undo_redo=True,
            show_delete_button=True,
        )
        layout.addWidget(header)

        # Images container
        images_container = QWidget()
        images_container.setStyleSheet("background: transparent;")
        images_layout = QHBoxLayout(images_container)
        images_layout.setContentsMargins(0, 0, 0, 4)
        images_layout.setSpacing(6)
        images_layout.addStretch()
        images_container.hide()
        layout.addWidget(images_container)

        text_edit = QTextEdit()
        text_edit.setFont(QFont("Menlo, Monaco, Consolas, monospace", 12))
        text_edit.setPlaceholderText("Type your message...")
        text_edit.setMinimumHeight(100)
        text_edit.textChanged.connect(self._update_send_buttons_state)
        layout.addWidget(text_edit)

        # Store references as attributes on container
        container.header = header
        container.text_edit = text_edit
        container.images_container = images_container
        container.images_layout = images_layout
        container.turn_images = []
        container.image_chips = []
        container.turn_number = turn_number

        # Undo/redo stacks for this section
        container.undo_stack = []
        container.redo_stack = []
        container.last_text = ""

        # Connect undo/redo signals
        header.undo_requested.connect(lambda s=container: self._undo_dynamic_section(s))
        header.redo_requested.connect(lambda s=container: self._redo_dynamic_section(s))

        # Connect delete signal
        header.delete_requested.connect(lambda s=container: self._delete_section(s))

        # Connect text changes for debounced state saving
        text_edit.textChanged.connect(lambda s=container: self._schedule_dynamic_state_save(s))

        # Toggle function for collapse/expand with fixed height
        def toggle_section(c=container, h=header, te=text_edit, ic=images_container):
            is_visible = te.isVisible()
            te.setVisible(not is_visible)
            ic.setVisible(not is_visible and bool(c.turn_images))
            h.set_collapsed(is_visible)
            collapsed_height = h.sizeHint().height() + 8
            if is_visible:
                c.setMaximumHeight(collapsed_height)
                self._set_splitter_section_height_for_widget(c, collapsed_height)
            else:
                c.setMaximumHeight(16777215)

        header.toggle_requested.connect(toggle_section)
        container.toggle_fn = toggle_section

        return container

    def _create_dynamic_output_section(self, turn_number: int) -> QWidget:
        """Create output section for a conversation turn."""
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = CollapsibleSectionHeader(
            f"Output #{turn_number}",
            show_save_button=False,
            show_undo_redo=True,
            show_delete_button=True,
        )
        layout.addWidget(header)

        text_edit = QTextEdit()
        text_edit.setFont(QFont("Menlo, Monaco, Consolas, monospace", 12))
        text_edit.setPlaceholderText("Output will appear here...")
        text_edit.setMinimumHeight(100)
        layout.addWidget(text_edit)

        # Store references
        container.header = header
        container.text_edit = text_edit
        container.turn_number = turn_number

        # Undo/redo stacks for this section
        container.undo_stack = []
        container.redo_stack = []
        container.last_text = ""

        # Connect undo/redo signals
        header.undo_requested.connect(lambda s=container: self._undo_dynamic_section(s))
        header.redo_requested.connect(lambda s=container: self._redo_dynamic_section(s))

        # Connect delete signal
        header.delete_requested.connect(lambda s=container: self._delete_section(s))

        # Connect text changes for debounced state saving
        text_edit.textChanged.connect(lambda s=container: self._schedule_dynamic_state_save(s))

        # Toggle function for collapse/expand with fixed height
        def toggle_section(c=container, h=header, te=text_edit):
            is_visible = te.isVisible()
            te.setVisible(not is_visible)
            h.set_collapsed(is_visible)
            collapsed_height = h.sizeHint().height() + 8
            if is_visible:
                c.setMaximumHeight(collapsed_height)
                self._set_splitter_section_height_for_widget(c, collapsed_height)
            else:
                c.setMaximumHeight(16777215)

        header.toggle_requested.connect(toggle_section)
        container.toggle_fn = toggle_section

        return container

    def _rebuild_reply_image_chips(self, section: QWidget):
        """Rebuild image chips for a reply section."""
        # Clear existing chips
        for chip in section.image_chips:
            chip.deleteLater()
        section.image_chips.clear()

        while section.images_layout.count():
            section.images_layout.takeAt(0)

        if not section.turn_images:
            section.images_container.hide()
            return

        section.images_container.show()

        for idx, item in enumerate(section.turn_images):
            chip = ImageChipWidget(
                index=idx,
                image_number=idx + 1,
                image_data=item.data or "",
                media_type=item.media_type or "image/png",
            )
            chip.delete_requested.connect(
                lambda i, s=section: self._on_reply_image_delete(s, i)
            )
            chip.copy_requested.connect(
                lambda i, s=section: self._on_reply_image_copy(s, i)
            )
            section.image_chips.append(chip)
            section.images_layout.addWidget(chip)

        section.images_layout.addStretch()

    def _on_reply_image_delete(self, section: QWidget, index: int):
        """Handle reply image delete request."""
        if 0 <= index < len(section.turn_images):
            del section.turn_images[index]
            self._rebuild_reply_image_chips(section)
            self._update_send_buttons_state()

    def _on_reply_image_copy(self, section: QWidget, index: int):
        """Handle reply image copy request."""
        if 0 <= index < len(section.image_chips):
            section.image_chips[index].copy_to_clipboard()

    def _paste_image_to_reply(self, section: QWidget) -> bool:
        """Paste image to reply section."""
        if not self.clipboard_manager or not self.clipboard_manager.has_image():
            return False

        image_data = self.clipboard_manager.get_image_data()
        if image_data:
            base64_data, media_type = image_data
            new_image = ContextItem(
                item_type=ContextItemType.IMAGE,
                data=base64_data,
                media_type=media_type,
            )
            section.turn_images.append(new_image)
            self._rebuild_reply_image_chips(section)
            self._update_send_buttons_state()
            return True
        return False

    # --- Event handling ---

    def keyPressEvent(self, event):
        """Handle key press events."""
        key = event.key()
        modifiers = event.modifiers()

        # Check if message has content (text or images)
        has_content = bool(self.input_edit.toPlainText().strip()) or bool(self._message_images)

        # Ctrl+Enter: Send, copy result to clipboard, close window
        if key in (Qt.Key_Return, Qt.Key_Enter) and (modifiers & Qt.ControlModifier):
            if has_content:
                self._on_send_copy()
            event.accept()
            return

        # Alt+Enter: Send, show result in window, stay open
        if key in (Qt.Key_Return, Qt.Key_Enter) and (modifiers & Qt.AltModifier):
            if has_content:
                self._on_send_show()
            event.accept()
            return

        # Escape to close
        if key == Qt.Key_Escape:
            self.close()
            return

        super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        """Filter events to intercept Ctrl+Z/Ctrl+Shift+Z on text edits."""
        if event.type() == QEvent.KeyPress:
            key = event.key()
            modifiers = event.modifiers()

            # Ctrl+Z for undo
            if key == Qt.Key_Z and (modifiers & Qt.ControlModifier):
                if modifiers & Qt.ShiftModifier:
                    # Ctrl+Shift+Z for redo
                    if obj == self.context_text_edit:
                        self._redo_context()
                    elif obj == self.input_edit:
                        self._redo_input()
                    elif obj == self.output_edit:
                        self._redo_output()
                    else:
                        # Check dynamic sections
                        for section in self._dynamic_sections + self._output_sections:
                            if obj == section.text_edit:
                                self._redo_dynamic_section(section)
                                break
                else:
                    # Ctrl+Z for undo
                    if obj == self.context_text_edit:
                        self._undo_context()
                    elif obj == self.input_edit:
                        self._undo_input()
                    elif obj == self.output_edit:
                        self._undo_output()
                    else:
                        # Check dynamic sections
                        for section in self._dynamic_sections + self._output_sections:
                            if obj == section.text_edit:
                                self._undo_dynamic_section(section)
                                break
                return True  # Event handled

            # Ctrl+Y for redo (alternative)
            if key == Qt.Key_Y and (modifiers & Qt.ControlModifier):
                if obj == self.context_text_edit:
                    self._redo_context()
                elif obj == self.input_edit:
                    self._redo_input()
                elif obj == self.output_edit:
                    self._redo_output()
                else:
                    # Check dynamic sections
                    for section in self._dynamic_sections + self._output_sections:
                        if obj == section.text_edit:
                            self._redo_dynamic_section(section)
                            break
                return True

            # Ctrl+V for paste image (if clipboard has image)
            if key == Qt.Key_V and (modifiers & Qt.ControlModifier):
                # Check reply sections first
                for section in self._dynamic_sections:
                    if obj == section.text_edit:
                        if self._paste_image_to_reply(section):
                            return True  # Event handled, don't paste as text

                if obj == self.context_text_edit:
                    if self._paste_image_from_clipboard():
                        return True  # Event handled, don't paste as text
                elif obj == self.input_edit:
                    if self._paste_image_to_message():
                        return True  # Event handled, don't paste as text

        return super().eventFilter(obj, event)
