"""Message share dialog for sending custom messages to prompts."""

import time
from dataclasses import dataclass
from typing import Optional, Callable, List, Dict

from PyQt5.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QWidget,
    QLabel,
    QSizePolicy,
    QScrollArea,
    QFrame,
)
from PyQt5.QtCore import Qt, QTimer, QEvent, pyqtSignal, QSize

from core.models import MenuItem, ExecutionResult
from core.context_manager import ContextManager, ContextItem, ContextItemType
from modules.gui.base_dialog import BaseDialog
from modules.gui.dialog_styles import (
    DEFAULT_WRAPPED_HEIGHT,
    DIALOG_SHOW_DELAY_MS,
    QWIDGETSIZE_MAX,
    TEXT_CHANGE_DEBOUNCE_MS,
    apply_section_size_policy,
    apply_wrap_state,
    get_text_edit_content_height,
)
from modules.gui.icons import create_icon
from modules.gui.shared_widgets import (
    CollapsibleSectionHeader,
    ImageChipWidget,
    create_text_edit,
    TOOLTIP_STYLE,
    TEXT_EDIT_MIN_HEIGHT,
)

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


@dataclass
class TabState:
    """Complete state of a conversation tab."""

    tab_id: str
    tab_name: str

    # Context section
    context_images: List[ContextItem]
    context_text: str
    context_undo_stack: List[ContextSectionState]
    context_redo_stack: List[ContextSectionState]
    last_context_text: str

    # Message/Input section
    message_images: List[ContextItem]
    message_text: str
    input_undo_stack: List[PromptInputState]
    input_redo_stack: List[PromptInputState]
    last_input_text: str

    # Output section
    output_text: str
    output_section_shown: bool
    output_undo_stack: List[OutputState]
    output_redo_stack: List[OutputState]
    last_output_text: str

    # Multi-turn conversation
    conversation_turns: List[ConversationTurn]
    current_turn_number: int
    dynamic_sections_data: List[Dict]  # Serialized reply sections
    output_sections_data: List[Dict]  # Serialized output sections

    # Execution state
    waiting_for_result: bool
    is_streaming: bool
    streaming_accumulated: str

    # UI collapsed/wrapped states
    context_collapsed: bool
    input_collapsed: bool
    output_collapsed: bool
    context_wrapped: bool
    input_wrapped: bool
    output_wrapped: bool


class ConversationTabBar(QWidget):
    """Custom tab bar for conversation tabs."""

    tab_selected = pyqtSignal(str)  # Emits tab_id
    tab_close_requested = pyqtSignal(str)  # Emits tab_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tabs: Dict[str, QWidget] = {}  # tab_id -> tab button widget
        self._tab_order: List[str] = []  # Ordered list of tab IDs
        self._active_tab_id: Optional[str] = None

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._layout.addStretch()

    def add_tab(self, tab_id: str, name: str):
        """Add a new tab to the bar."""
        if tab_id in self._tabs:
            return

        tab_widget = self._create_tab_widget(tab_id, name)
        self._tabs[tab_id] = tab_widget
        self._tab_order.append(tab_id)

        # Insert before the stretch
        self._layout.insertWidget(self._layout.count() - 1, tab_widget)

    def remove_tab(self, tab_id: str):
        """Remove a tab from the bar."""
        if tab_id not in self._tabs:
            return

        tab_widget = self._tabs.pop(tab_id)
        self._tab_order.remove(tab_id)
        tab_widget.setParent(None)
        tab_widget.deleteLater()

    def set_active_tab(self, tab_id: str):
        """Set the active tab visually."""
        if tab_id not in self._tabs:
            return

        self._active_tab_id = tab_id

        for tid, widget in self._tabs.items():
            is_active = tid == tab_id
            widget.setProperty("active", is_active)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def get_tab_count(self) -> int:
        """Get the number of tabs."""
        return len(self._tabs)

    def get_tab_ids(self) -> List[str]:
        """Get ordered list of tab IDs."""
        return list(self._tab_order)

    def _create_tab_widget(self, tab_id: str, name: str) -> QWidget:
        """Create a tab button widget."""
        tab = QWidget()
        tab.setProperty("active", False)
        tab.setStyleSheet("""
            QWidget {
                background: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                padding: 4px 8px 2px 8px;
            }
            QWidget:hover {
                background: rgba(255, 255, 255, 0.05);
            }
            QWidget[active="true"] {
                border-bottom: 2px solid #888888;
            }
        """)

        layout = QHBoxLayout(tab)
        layout.setContentsMargins(6, 4, 4, 4)
        layout.setSpacing(6)

        # Tab label
        label = QLabel(name)
        label.setStyleSheet("border: none; background: transparent; color: #cccccc;")
        label.setCursor(Qt.PointingHandCursor)
        layout.addWidget(label)

        # Close button
        close_btn = QPushButton()
        close_btn.setIcon(create_icon("delete", "#888888", 14))
        close_btn.setIconSize(QSize(14, 14))
        close_btn.setFixedSize(18, 18)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #555555;
            }
        """)
        close_btn.clicked.connect(lambda: self.tab_close_requested.emit(tab_id))
        layout.addWidget(close_btn)

        # Store tab_id on the widget for click handling
        tab.tab_id = tab_id
        tab.label = label

        # Make the tab clickable
        tab.mousePressEvent = lambda e, tid=tab_id: self._on_tab_clicked(tid)
        label.mousePressEvent = lambda e, tid=tab_id: self._on_tab_clicked(tid)

        return tab

    def _on_tab_clicked(self, tab_id: str):
        """Handle tab click."""
        self.tab_selected.emit(tab_id)


def show_message_share_dialog(
    menu_item: MenuItem,
    execution_callback: Callable[[MenuItem, bool], None],
    prompt_store_service=None,
    context_manager: Optional[ContextManager] = None,
    clipboard_manager=None,
    notification_manager=None,
):
    """Show the message share dialog.

    Args:
        menu_item: The prompt menu item to execute
        execution_callback: Callback to execute the prompt
        prompt_store_service: The prompt store service for execution
        context_manager: The context manager for loading/saving context
        notification_manager: The notification manager for UI notifications
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
            notification_manager,
        )
        _open_dialogs[window_key] = dialog
        dialog.finished.connect(lambda: _open_dialogs.pop(window_key, None))
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    QTimer.singleShot(DIALOG_SHOW_DELAY_MS, create_and_show)


class MessageShareDialog(BaseDialog):
    """Dialog for typing a message to send to a prompt."""

    STATE_KEY = "message_share_dialog"

    def __init__(
        self,
        menu_item: MenuItem,
        execution_callback: Callable[[MenuItem, bool], None],
        prompt_store_service=None,
        context_manager: Optional[ContextManager] = None,
        clipboard_manager=None,
        notification_manager=None,
        parent=None,
    ):
        super().__init__(parent)
        self.menu_item = menu_item
        self.execution_callback = execution_callback
        self._waiting_for_result = False
        self._prompt_store_service = prompt_store_service
        self.context_manager = context_manager
        self.clipboard_manager = clipboard_manager
        self.notification_manager = notification_manager

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
        self._text_change_timer.setInterval(TEXT_CHANGE_DEBOUNCE_MS)
        self._text_change_timer.timeout.connect(self._save_text_states)

        # Streaming state
        self._is_streaming = False
        self._streaming_accumulated = ""

        # Throttling for UI updates during streaming (60fps max)
        self._streaming_throttle_timer = QTimer()
        self._streaming_throttle_timer.setSingleShot(True)
        self._streaming_throttle_timer.setInterval(16)
        self._streaming_throttle_timer.timeout.connect(self._flush_streaming_update)
        self._last_ui_update_time = 0

        # Signal connection tracking to prevent duplicate connections
        self._execution_signal_connected = False
        self._streaming_signal_connected = False

        # Tab management
        self._tabs: Dict[str, TabState] = {}
        self._active_tab_id: Optional[str] = None
        self._tab_counter: int = 0
        self._tab_bar: Optional[ConversationTabBar] = None
        self._tab_scroll: Optional[QScrollArea] = None
        self._max_tabs: int = 10

        # Extract prompt name for title
        prompt_name = (
            menu_item.data.get("prompt_name", "Prompt") if menu_item.data else "Prompt"
        )
        self.setWindowTitle(f"Message to: {prompt_name}")

        self._setup_ui()
        self.apply_dialog_styles()
        self._load_context()
        self._restore_ui_state()

        # Focus message input for immediate typing
        self.input_edit.setFocus()

    def _setup_ui(self):
        """Set up the dialog UI with three collapsible sections."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 0, 10)  # No right margin - scrollbar sticks to edge
        layout.setSpacing(8)

        # Scroll area for scrolling when many sections
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        # Container widget with layout for all sections
        self.sections_container = QWidget()
        self.sections_layout = QVBoxLayout(self.sections_container)
        self.sections_layout.setContentsMargins(0, 0, 14, 0)  # Right margin for scrollbar + 2px gap
        self.sections_layout.setSpacing(8)

        # Section 1: Context (with save button)
        self.context_section = self._create_context_section()
        self.sections_layout.addWidget(self.context_section)

        # Section 2: Prompt Input (no save button)
        self.input_section = self._create_input_section()
        self.sections_layout.addWidget(self.input_section)

        # Section 3: Output (no save button) - NOT added initially
        self.output_section = self._create_output_section()
        # Output section is hidden until user clicks Alt+Enter

        self.scroll_area.setWidget(self.sections_container)
        layout.addWidget(self.scroll_area)

        # Button bar (includes tabs inline)
        self._create_button_bar(layout)

        # Install event filters for keyboard handling
        self.context_text_edit.installEventFilter(self)
        self.input_edit.installEventFilter(self)
        # output_edit event filter is installed when output section is shown

    def _create_context_section(self) -> QWidget:
        """Create the collapsible context section with save button."""
        container = QWidget()
        apply_section_size_policy(container, expanding=False)
        section_layout = QVBoxLayout(container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)

        # Header with collapse toggle, wrap button, undo/redo, and save button
        self.context_header = CollapsibleSectionHeader(
            "Context",
            show_save_button=True,
            show_undo_redo=True,
            show_wrap_button=True,
            hint_text="",
        )
        self.context_header.toggle_requested.connect(self._toggle_context_section)
        self.context_header.wrap_requested.connect(self._toggle_context_wrap)
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

        # Text edit area - context uses smaller min height since it has max constraint
        self.context_text_edit = create_text_edit(
            placeholder="Context content...",
            min_height=100,
        )
        self.context_text_edit.setMaximumHeight(TEXT_EDIT_MIN_HEIGHT)  # Default wrapped height
        self.context_text_edit.textChanged.connect(self._on_context_text_changed)
        section_layout.addWidget(self.context_text_edit)

        return container

    def _create_input_section(self) -> QWidget:
        """Create the collapsible prompt input section (no save button)."""
        container = QWidget()
        section_layout = QVBoxLayout(container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)

        # Header with collapse toggle, wrap button, and undo/redo (NO save button)
        self.input_header = CollapsibleSectionHeader(
            "Message",
            show_save_button=False,
            show_undo_redo=True,
            show_wrap_button=True,
            hint_text="",
        )
        self.input_header.toggle_requested.connect(self._toggle_input_section)
        self.input_header.wrap_requested.connect(self._toggle_input_wrap)
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
        self.input_edit = create_text_edit(
            placeholder="Type your message... (Ctrl+Enter: Send & copy | Alt+Enter: Send & show | Ctrl+V: Paste image)"
        )
        self.input_edit.setToolTip("Type and send message with prompt")
        self.input_edit.textChanged.connect(self._on_input_text_changed)
        section_layout.addWidget(self.input_edit)

        apply_section_size_policy(container, expanding=True, widget=self.input_edit)

        return container

    def _create_output_section(self) -> QWidget:
        """Create the collapsible output section (no save button)."""
        container = QWidget()
        section_layout = QVBoxLayout(container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)

        # Header with collapse toggle, wrap button, and undo/redo (NO save button)
        self.output_header = CollapsibleSectionHeader(
            "Output",
            show_save_button=False,
            show_undo_redo=True,
            show_wrap_button=True,
            hint_text="",
        )
        self.output_header.toggle_requested.connect(self._toggle_output_section)
        self.output_header.wrap_requested.connect(self._toggle_output_wrap)
        self.output_header.undo_requested.connect(self._undo_output)
        self.output_header.redo_requested.connect(self._redo_output)
        section_layout.addWidget(self.output_header)

        # Text edit area
        self.output_edit = create_text_edit(placeholder="Output will appear here...")
        self.output_edit.textChanged.connect(self._on_output_text_changed)
        section_layout.addWidget(self.output_edit)

        apply_section_size_policy(container, expanding=True, widget=self.output_edit)

        return container

    def _create_button_bar(self, layout: QVBoxLayout):
        """Create button bar with tabs inline and send actions."""
        button_widget = QWidget()
        button_widget.setFixedHeight(36)
        button_bar = QHBoxLayout(button_widget)
        button_bar.setContentsMargins(12, 0, 12, 0)

        # Add tab button on the left (plus icon)
        self.add_tab_btn = QPushButton()
        self.add_tab_btn.setIcon(create_icon("plus", "#888888", 16))
        self.add_tab_btn.setToolTip("New conversation tab")
        self.add_tab_btn.clicked.connect(self._on_add_tab_clicked)
        button_bar.addWidget(self.add_tab_btn)

        # Tab bar in horizontal scroll area
        self._tab_scroll = QScrollArea()
        self._tab_scroll.setWidgetResizable(True)
        self._tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._tab_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._tab_scroll.setFrameShape(QFrame.NoFrame)
        self._tab_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._tab_scroll.setFixedHeight(32)

        self._tab_bar = ConversationTabBar()
        self._tab_bar.tab_selected.connect(self._on_tab_selected)
        self._tab_bar.tab_close_requested.connect(self._on_tab_close_requested)
        self._tab_scroll.setWidget(self._tab_bar)
        button_bar.addWidget(self._tab_scroll, 1)  # stretch factor 1

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

    # --- Context loading/saving ---

    def _load_context(self):
        """Load context from context_manager."""
        if not self.context_manager:
            return

        items = self.context_manager.get_items()

        # Separate images and text
        self._current_images = [
            ContextItem(
                item_type=item.item_type, data=item.data, media_type=item.media_type
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

        # Show success notification
        if self.notification_manager:
            self.notification_manager.show_success_notification("Context Saved")

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
        self.context_images_container.setVisible(
            not is_visible and len(self._current_images) > 0
        )
        self.context_header.set_collapsed(is_visible)
        # When collapsed, use Fixed policy to take minimal space
        if is_visible:  # Will be collapsed
            self.context_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        else:  # Will be expanded
            self.context_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self._save_section_state("context", collapsed=is_visible)

    def _toggle_input_section(self):
        """Toggle input section visibility."""
        is_visible = self.input_edit.isVisible()
        self.input_edit.setVisible(not is_visible)
        self.input_header.set_collapsed(is_visible)
        # When collapsed, use Fixed policy to take minimal space
        if is_visible:  # Will be collapsed
            self.input_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        else:  # Will be expanded
            self.input_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self._save_section_state("input", collapsed=is_visible)

    def _toggle_output_section(self):
        """Toggle output section visibility."""
        if not self._output_section_shown:
            # Output not yet in layout - add it now
            self._expand_output_section()
            return

        is_visible = self.output_edit.isVisible()
        self.output_edit.setVisible(not is_visible)
        self.output_header.set_collapsed(is_visible)
        # When collapsed, use Fixed policy to take minimal space
        if is_visible:  # Will be collapsed
            self.output_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        else:  # Will be expanded
            self.output_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self._save_section_state("output", collapsed=is_visible)

    def _toggle_context_wrap(self):
        """Toggle context section wrap state."""
        is_wrapped = self.context_header.is_wrapped()
        new_wrapped = not is_wrapped
        self.context_header.set_wrap_state(new_wrapped)
        if new_wrapped:
            self.context_text_edit.setMinimumHeight(100)
            self.context_text_edit.setMaximumHeight(TEXT_EDIT_MIN_HEIGHT)
        else:
            content_height = get_text_edit_content_height(self.context_text_edit)
            self.context_text_edit.setMinimumHeight(content_height)
            self.context_text_edit.setMaximumHeight(QWIDGETSIZE_MAX)
        self._save_section_state("context_wrapped", collapsed=new_wrapped)

    def _toggle_input_wrap(self):
        """Toggle input section wrap state."""
        is_wrapped = self.input_header.is_wrapped()
        new_wrapped = not is_wrapped
        self.input_header.set_wrap_state(new_wrapped)
        if new_wrapped:
            self.input_edit.setMinimumHeight(TEXT_EDIT_MIN_HEIGHT)
        else:
            content_height = get_text_edit_content_height(self.input_edit)
            self.input_edit.setMinimumHeight(content_height)
        self._save_section_state("input_wrapped", collapsed=new_wrapped)

    def _toggle_output_wrap(self):
        """Toggle output section wrap state."""
        is_wrapped = self.output_header.is_wrapped()
        new_wrapped = not is_wrapped
        self.output_header.set_wrap_state(new_wrapped)
        if new_wrapped:
            self.output_edit.setMinimumHeight(TEXT_EDIT_MIN_HEIGHT)
        else:
            content_height = get_text_edit_content_height(self.output_edit)
            self.output_edit.setMinimumHeight(content_height)
        self._save_section_state("output_wrapped", collapsed=new_wrapped)

    def _save_section_state(self, section: str, collapsed: bool):
        """Save section state (collapsed or wrapped)."""
        self.save_section_state(section, collapsed)

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
        """Restore collapsed and wrap states from saved state."""
        # Restore geometry (uses BaseDialog method)
        self.restore_geometry_from_state()

        # Restore collapsed states
        context_collapsed = self.get_section_state("context.collapsed", False)
        input_collapsed = self.get_section_state("input.collapsed", False)

        if context_collapsed:
            self.context_text_edit.hide()
            self.context_images_container.hide()
            self.context_header.set_collapsed(True)
            self.context_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        if input_collapsed:
            self.input_edit.hide()
            self.input_header.set_collapsed(True)
            self.input_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        # Restore wrap states
        context_wrapped = self.get_section_state("context_wrapped", True)
        input_wrapped = self.get_section_state("input_wrapped", True)
        output_wrapped = self.get_section_state("output_wrapped", True)

        self.context_header.set_wrap_state(context_wrapped)
        if not context_wrapped:
            content_height = get_text_edit_content_height(self.context_text_edit)
            self.context_text_edit.setMinimumHeight(content_height)
            self.context_text_edit.setMaximumHeight(QWIDGETSIZE_MAX)

        self.input_header.set_wrap_state(input_wrapped)
        if not input_wrapped:
            content_height = get_text_edit_content_height(self.input_edit)
            self.input_edit.setMinimumHeight(content_height)

        self.output_header.set_wrap_state(output_wrapped)
        if not output_wrapped:
            content_height = get_text_edit_content_height(self.output_edit)
            self.output_edit.setMinimumHeight(content_height)

    def closeEvent(self, event):
        """Save geometry on close and disconnect signals."""
        # Disconnect from signals if connected
        self._disconnect_execution_signal()
        self._disconnect_streaming_signal()

        # Stop streaming if active
        if self._is_streaming:
            self._streaming_throttle_timer.stop()
            self._is_streaming = False

        # BaseDialog handles geometry save
        super().closeEvent(event)

    # --- Undo/Redo: Context Section ---

    def _get_context_state(self) -> ContextSectionState:
        """Get current context state."""
        return ContextSectionState(
            images=[
                ContextItem(
                    item_type=img.item_type, data=img.data, media_type=img.media_type
                )
                for img in self._current_images
            ],
            text=self.context_text_edit.toPlainText(),
        )

    def _restore_context_state(self, state: ContextSectionState):
        """Restore context state."""
        self._current_images = [
            ContextItem(
                item_type=img.item_type, data=img.data, media_type=img.media_type
            )
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
        if not hasattr(section, "_save_timer"):
            section._save_timer = QTimer()
            section._save_timer.setSingleShot(True)
            section._save_timer.setInterval(500)
            section._save_timer.timeout.connect(
                lambda s=section: self._save_dynamic_state(s)
            )
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
            len(section.undo_stack) > 0, len(section.redo_stack) > 0
        )

    def _update_dynamic_section_height(self, section: QWidget):
        """Update height for dynamic section when unwrapped."""
        if not section.header.is_wrapped():
            content_height = get_text_edit_content_height(section.text_edit)
            section.text_edit.setMinimumHeight(content_height)

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
        if not self.context_header.is_wrapped():
            content_height = get_text_edit_content_height(self.context_text_edit)
            self.context_text_edit.setMinimumHeight(content_height)

    def _on_input_text_changed(self):
        """Handle input text changes - debounce state saving and update buttons."""
        self._text_change_timer.start()
        self._update_send_buttons_state()
        if not self.input_header.is_wrapped():
            content_height = get_text_edit_content_height(self.input_edit)
            self.input_edit.setMinimumHeight(content_height)

    def _on_output_text_changed(self):
        """Handle output text changes - debounce state saving."""
        self._text_change_timer.start()
        if not self.output_header.is_wrapped():
            content_height = get_text_edit_content_height(self.output_edit)
            self.output_edit.setMinimumHeight(content_height)

    def _save_text_states(self):
        """Save state if text has significantly changed in any section."""
        # Context
        current_context = self.context_text_edit.toPlainText()
        if current_context != self._last_context_text:
            state = ContextSectionState(
                images=[
                    ContextItem(
                        item_type=img.item_type,
                        data=img.data,
                        media_type=img.media_type,
                    )
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

    # --- Tab Management ---

    def _capture_current_state(self) -> TabState:
        """Capture complete state of current conversation for tab switching."""
        # Serialize dynamic sections
        dynamic_sections_data = []
        for section in self._dynamic_sections:
            section_data = {
                "turn_number": section.turn_number,
                "text": section.text_edit.toPlainText(),
                "images": [
                    {"data": img.data, "media_type": img.media_type}
                    for img in section.turn_images
                ],
                "undo_stack": list(section.undo_stack),
                "redo_stack": list(section.redo_stack),
                "last_text": section.last_text,
                "collapsed": section.header.is_collapsed(),
                "wrapped": section.header.is_wrapped(),
            }
            dynamic_sections_data.append(section_data)

        # Serialize output sections
        output_sections_data = []
        for section in self._output_sections:
            section_data = {
                "turn_number": section.turn_number,
                "text": section.text_edit.toPlainText(),
                "undo_stack": list(section.undo_stack),
                "redo_stack": list(section.redo_stack),
                "last_text": section.last_text,
                "collapsed": section.header.is_collapsed(),
                "wrapped": section.header.is_wrapped(),
            }
            output_sections_data.append(section_data)

        return TabState(
            tab_id=self._active_tab_id or "",
            tab_name=f"Tab {self._tab_counter}",
            # Context section
            context_images=[
                ContextItem(item_type=img.item_type, data=img.data, media_type=img.media_type)
                for img in self._current_images
            ],
            context_text=self.context_text_edit.toPlainText(),
            context_undo_stack=list(self._context_undo_stack),
            context_redo_stack=list(self._context_redo_stack),
            last_context_text=self._last_context_text,
            # Message/Input section
            message_images=[
                ContextItem(item_type=img.item_type, data=img.data, media_type=img.media_type)
                for img in self._message_images
            ],
            message_text=self.input_edit.toPlainText(),
            input_undo_stack=list(self._input_undo_stack),
            input_redo_stack=list(self._input_redo_stack),
            last_input_text=self._last_input_text,
            # Output section
            output_text=self.output_edit.toPlainText(),
            output_section_shown=self._output_section_shown,
            output_undo_stack=list(self._output_undo_stack),
            output_redo_stack=list(self._output_redo_stack),
            last_output_text=self._last_output_text,
            # Multi-turn conversation
            conversation_turns=list(self._conversation_turns),
            current_turn_number=self._current_turn_number,
            dynamic_sections_data=dynamic_sections_data,
            output_sections_data=output_sections_data,
            # Execution state
            waiting_for_result=self._waiting_for_result,
            is_streaming=self._is_streaming,
            streaming_accumulated=self._streaming_accumulated,
            # UI collapsed/wrapped states
            context_collapsed=self.context_header.is_collapsed(),
            input_collapsed=self.input_header.is_collapsed(),
            output_collapsed=self.output_header.is_collapsed(),
            context_wrapped=self.context_header.is_wrapped(),
            input_wrapped=self.input_header.is_wrapped(),
            output_wrapped=self.output_header.is_wrapped(),
        )

    def _restore_state(self, state: TabState):
        """Restore complete state from a TabState object."""
        # Clear dynamic sections first
        self._clear_dynamic_sections()

        # Restore context section
        self._current_images = [
            ContextItem(item_type=img.item_type, data=img.data, media_type=img.media_type)
            for img in state.context_images
        ]
        self._rebuild_image_chips()
        self.context_text_edit.blockSignals(True)
        self.context_text_edit.setPlainText(state.context_text)
        self.context_text_edit.blockSignals(False)
        self._context_undo_stack = list(state.context_undo_stack)
        self._context_redo_stack = list(state.context_redo_stack)
        self._last_context_text = state.last_context_text

        # Restore message/input section
        self._message_images = [
            ContextItem(item_type=img.item_type, data=img.data, media_type=img.media_type)
            for img in state.message_images
        ]
        self._rebuild_message_image_chips()
        self.input_edit.blockSignals(True)
        self.input_edit.setPlainText(state.message_text)
        self.input_edit.blockSignals(False)
        self._input_undo_stack = list(state.input_undo_stack)
        self._input_redo_stack = list(state.input_redo_stack)
        self._last_input_text = state.last_input_text

        # Restore output section
        self.output_edit.blockSignals(True)
        self.output_edit.setPlainText(state.output_text)
        self.output_edit.blockSignals(False)
        self._output_undo_stack = list(state.output_undo_stack)
        self._output_redo_stack = list(state.output_redo_stack)
        self._last_output_text = state.last_output_text

        # Handle output section visibility
        if state.output_section_shown and not self._output_section_shown:
            self.sections_layout.addWidget(self.output_section)
            self.output_edit.installEventFilter(self)
            self._output_section_shown = True
        elif not state.output_section_shown and self._output_section_shown:
            self.sections_layout.removeWidget(self.output_section)
            self.output_section.setParent(None)
            self._output_section_shown = False

        # Restore multi-turn conversation state
        self._conversation_turns = list(state.conversation_turns)
        self._current_turn_number = state.current_turn_number

        # Restore dynamic sections
        self._restore_dynamic_sections(
            state.dynamic_sections_data, state.output_sections_data
        )

        # Restore execution state
        self._waiting_for_result = state.waiting_for_result
        self._is_streaming = state.is_streaming
        self._streaming_accumulated = state.streaming_accumulated

        # Restore UI collapsed/wrapped states
        self._restore_section_ui_states(state)

        # Update button states
        self._update_undo_redo_buttons()
        self._update_send_buttons_state()
        self._update_delete_button_visibility()

        # Show reply button if needed
        has_output = self._output_section_shown or bool(self._output_sections)
        has_pending_reply = bool(self._dynamic_sections)
        self.reply_btn.setVisible(
            has_output and not self._waiting_for_result and not has_pending_reply
        )

    def _clear_dynamic_sections(self):
        """Remove all dynamic reply and output sections from layout."""
        for section in self._dynamic_sections:
            self.sections_layout.removeWidget(section)
            section.setParent(None)
            section.deleteLater()
        self._dynamic_sections.clear()

        for section in self._output_sections:
            self.sections_layout.removeWidget(section)
            section.setParent(None)
            section.deleteLater()
        self._output_sections.clear()

    def _restore_dynamic_sections(
        self, reply_data: List[Dict], output_data: List[Dict]
    ):
        """Recreate dynamic sections from serialized data."""
        # Recreate reply sections
        for data in reply_data:
            section = self._create_reply_section(data["turn_number"])
            section.text_edit.setPlainText(data["text"])
            section.undo_stack = list(data["undo_stack"])
            section.redo_stack = list(data["redo_stack"])
            section.last_text = data["last_text"]

            # Restore images
            for img_data in data.get("images", []):
                section.turn_images.append(
                    ContextItem(
                        item_type=ContextItemType.IMAGE,
                        data=img_data["data"],
                        media_type=img_data["media_type"],
                    )
                )
            self._rebuild_reply_image_chips(section)

            # Restore collapsed/wrapped state
            if data.get("collapsed", False):
                section.toggle_fn()
            section.header.set_wrap_state(data.get("wrapped", True))

            self._dynamic_sections.append(section)
            self.sections_layout.addWidget(section)
            section.text_edit.installEventFilter(self)

        # Recreate output sections
        for data in output_data:
            section = self._create_dynamic_output_section(data["turn_number"])
            section.text_edit.setPlainText(data["text"])
            section.undo_stack = list(data["undo_stack"])
            section.redo_stack = list(data["redo_stack"])
            section.last_text = data["last_text"]

            # Restore collapsed/wrapped state
            if data.get("collapsed", False):
                section.toggle_fn()
            section.header.set_wrap_state(data.get("wrapped", True))

            self._output_sections.append(section)
            self.sections_layout.addWidget(section)
            section.text_edit.installEventFilter(self)

    def _restore_section_ui_states(self, state: TabState):
        """Restore collapsed and wrapped states for main sections."""
        # Context section
        if state.context_collapsed:
            self.context_text_edit.hide()
            self.context_images_container.hide()
            self.context_header.set_collapsed(True)
            self.context_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        else:
            self.context_text_edit.show()
            if self._current_images:
                self.context_images_container.show()
            self.context_header.set_collapsed(False)
            self.context_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        self.context_header.set_wrap_state(state.context_wrapped)
        if not state.context_wrapped:
            content_height = get_text_edit_content_height(self.context_text_edit)
            self.context_text_edit.setMinimumHeight(content_height)
            self.context_text_edit.setMaximumHeight(QWIDGETSIZE_MAX)
        else:
            self.context_text_edit.setMinimumHeight(100)
            self.context_text_edit.setMaximumHeight(TEXT_EDIT_MIN_HEIGHT)

        # Input section
        if state.input_collapsed:
            self.input_edit.hide()
            self.input_header.set_collapsed(True)
            self.input_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        else:
            self.input_edit.show()
            self.input_header.set_collapsed(False)
            self.input_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self.input_header.set_wrap_state(state.input_wrapped)
        if not state.input_wrapped:
            content_height = get_text_edit_content_height(self.input_edit)
            self.input_edit.setMinimumHeight(content_height)

        # Output section
        if self._output_section_shown:
            if state.output_collapsed:
                self.output_edit.hide()
                self.output_header.set_collapsed(True)
                self.output_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            else:
                self.output_edit.show()
                self.output_header.set_collapsed(False)
                self.output_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

            self.output_header.set_wrap_state(state.output_wrapped)
            if not state.output_wrapped:
                content_height = get_text_edit_content_height(self.output_edit)
                self.output_edit.setMinimumHeight(content_height)

    def _reset_to_initial_state(self):
        """Reset dialog to fresh initial state for a new tab."""
        # Clear dynamic sections
        self._clear_dynamic_sections()

        # Remove output section from layout if shown
        if self._output_section_shown:
            self.sections_layout.removeWidget(self.output_section)
            self.output_section.setParent(None)
            self._output_section_shown = False

        # Reset context - reload from context_manager
        self._context_undo_stack.clear()
        self._context_redo_stack.clear()
        self._load_context()

        # Reset message/input section
        self._message_images.clear()
        self._rebuild_message_image_chips()
        self.input_edit.blockSignals(True)
        self.input_edit.setPlainText("")
        self.input_edit.blockSignals(False)
        self._input_undo_stack.clear()
        self._input_redo_stack.clear()
        self._last_input_text = ""

        # Reset output section
        self.output_edit.blockSignals(True)
        self.output_edit.setPlainText("")
        self.output_edit.blockSignals(False)
        self._output_undo_stack.clear()
        self._output_redo_stack.clear()
        self._last_output_text = ""

        # Reset multi-turn conversation state
        self._conversation_turns.clear()
        self._current_turn_number = 0

        # Reset execution state
        self._waiting_for_result = False
        self._is_streaming = False
        self._streaming_accumulated = ""

        # Reset UI states
        self.context_text_edit.show()
        self.context_header.set_collapsed(False)
        self.input_edit.show()
        self.input_header.set_collapsed(False)
        self.reply_btn.setVisible(False)

        # Update button states
        self._update_undo_redo_buttons()
        self._update_send_buttons_state()

    def _on_add_tab_clicked(self):
        """Handle add tab button click."""
        if len(self._tabs) >= self._max_tabs:
            return

        # If this is the first tab creation, create Tab 1 for current state
        if not self._active_tab_id:
            self._tab_counter += 1
            first_tab_id = f"tab_{self._tab_counter}"
            first_tab_name = f"Tab {self._tab_counter}"

            # Capture current state as Tab 1
            first_state = self._capture_current_state()
            first_state.tab_id = first_tab_id
            first_state.tab_name = first_tab_name
            self._tabs[first_tab_id] = first_state
            self._active_tab_id = first_tab_id

            # Add first tab to tab bar
            self._tab_bar.add_tab(first_tab_id, first_tab_name)
        else:
            # Save current tab state
            self._tabs[self._active_tab_id] = self._capture_current_state()

        # Increment tab counter and generate new tab ID
        self._tab_counter += 1
        new_tab_id = f"tab_{self._tab_counter}"
        new_tab_name = f"Tab {self._tab_counter}"

        # Reset dialog to initial state
        self._reset_to_initial_state()

        # Create and store new tab state
        new_state = self._capture_current_state()
        new_state.tab_id = new_tab_id
        new_state.tab_name = new_tab_name
        self._tabs[new_tab_id] = new_state
        self._active_tab_id = new_tab_id

        # Add tab to tab bar
        self._tab_bar.add_tab(new_tab_id, new_tab_name)
        self._tab_bar.set_active_tab(new_tab_id)

        # Focus input for immediate typing
        self.input_edit.setFocus()

    def _on_tab_selected(self, tab_id: str):
        """Handle tab selection."""
        if tab_id == self._active_tab_id:
            return

        # Save current tab state
        if self._active_tab_id:
            self._tabs[self._active_tab_id] = self._capture_current_state()

        # Switch to new tab
        self._active_tab_id = tab_id
        self._tab_bar.set_active_tab(tab_id)

        # Restore state from selected tab
        if tab_id in self._tabs:
            self._restore_state(self._tabs[tab_id])

    def _on_tab_close_requested(self, tab_id: str):
        """Handle tab close request."""
        if self._tab_bar.get_tab_count() <= 1:
            # Last tab - just reset to initial state instead of closing
            self._reset_to_initial_state()
            return

        # If closing active tab, switch to another first
        if tab_id == self._active_tab_id:
            tab_ids = self._tab_bar.get_tab_ids()
            current_idx = tab_ids.index(tab_id)
            # Switch to previous tab, or next if this is first
            new_idx = current_idx - 1 if current_idx > 0 else current_idx + 1
            new_tab_id = tab_ids[new_idx]
            self._on_tab_selected(new_tab_id)

        # Remove tab from storage and UI
        self._tabs.pop(tab_id, None)
        self._tab_bar.remove_tab(tab_id)

    # --- Execution ---

    def _get_prompt_store_service(self):
        """Get the prompt store service for execution."""
        return self._prompt_store_service

    def _connect_execution_signal(self):
        """Connect to execution completed signal."""
        if self._execution_signal_connected:
            return
        service = self._get_prompt_store_service()
        if service and hasattr(service, "_menu_coordinator"):
            try:
                service._menu_coordinator.execution_completed.connect(
                    self._on_execution_result
                )
                self._execution_signal_connected = True
            except Exception:
                pass

    def _disconnect_execution_signal(self):
        """Disconnect from execution completed signal."""
        if not self._execution_signal_connected:
            return
        service = self._get_prompt_store_service()
        if service and hasattr(service, "_menu_coordinator"):
            try:
                service._menu_coordinator.execution_completed.disconnect(
                    self._on_execution_result
                )
            except Exception:
                pass
        self._execution_signal_connected = False

    def _connect_streaming_signal(self):
        """Connect to streaming chunk signal for live updates."""
        if self._streaming_signal_connected:
            return
        service = self._get_prompt_store_service()
        if service and hasattr(service, "_menu_coordinator"):
            try:
                service._menu_coordinator.streaming_chunk.connect(
                    self._on_streaming_chunk
                )
                self._streaming_signal_connected = True
            except Exception:
                pass

    def _disconnect_streaming_signal(self):
        """Disconnect from streaming chunk signal."""
        if not self._streaming_signal_connected:
            return
        service = self._get_prompt_store_service()
        if service and hasattr(service, "_menu_coordinator"):
            try:
                service._menu_coordinator.streaming_chunk.disconnect(
                    self._on_streaming_chunk
                )
            except Exception:
                pass
        self._streaming_signal_connected = False

    def _on_streaming_chunk(self, chunk: str, accumulated: str, is_final: bool):
        """Handle streaming chunk with adaptive throttling."""
        if not self._waiting_for_result:
            return

        if not self._is_streaming and not is_final:
            self._is_streaming = True
            self._streaming_accumulated = ""

        self._streaming_accumulated = accumulated

        if is_final:
            self._flush_streaming_update()
            self._is_streaming = False
            self._streaming_throttle_timer.stop()
            return

        # Adaptive throttling
        current_time = time.time() * 1000
        time_since_update = current_time - self._last_ui_update_time

        # Small chunks or enough time passed - update immediately
        if len(chunk) < 10 or time_since_update >= 16:
            self._flush_streaming_update()
        elif not self._streaming_throttle_timer.isActive():
            self._streaming_throttle_timer.start()

    def _flush_streaming_update(self):
        """Update UI with accumulated streaming text."""
        if not self._streaming_accumulated:
            return

        self._last_ui_update_time = time.time() * 1000

        # Get correct output text edit based on turn number
        if self._current_turn_number == 1 or not self._output_sections:
            output_edit = self.output_edit
        else:
            output_edit = self._output_sections[-1].text_edit

        # Update text without triggering undo stack
        output_edit.blockSignals(True)
        output_edit.setPlainText(self._streaming_accumulated)
        cursor = output_edit.textCursor()
        cursor.movePosition(cursor.End)
        output_edit.setTextCursor(cursor)
        output_edit.blockSignals(False)

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

        # Enable streaming for "Send & Show" mode
        if keep_open:
            conv_data["use_streaming"] = True

        # For backward compatibility, also build full_message for single-turn case
        working_context_text = self.context_text_edit.toPlainText().strip()
        full_message = msg_text
        if len(self._conversation_turns) == 1 and working_context_text:
            full_message = (
                f"<context>\n{working_context_text}\n</context>\n\n{msg_text}"
            )

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
            # Connect to receive result and streaming chunks
            self._waiting_for_result = True
            self._connect_execution_signal()
            self._connect_streaming_signal()

            # Create output section for this turn
            if self._current_turn_number == 1:
                # First turn uses existing output section
                self._expand_output_section()
                self.output_edit.setPlainText("Executing...")
                # Set expanded mode and update height after text is set
                self.output_header.set_wrap_state(False)
                content_height = get_text_edit_content_height(self.output_edit)
                self.output_edit.setMinimumHeight(content_height)
            else:
                # Subsequent turns create new output section
                output_section = self._create_dynamic_output_section(
                    self._current_turn_number
                )
                self._output_sections.append(output_section)
                self.sections_layout.addWidget(output_section)
                output_section.text_edit.installEventFilter(self)
                output_section.text_edit.setPlainText("Executing...")
                # Set expanded mode and update height after text is set
                output_section.header.set_wrap_state(False)
                content_height = get_text_edit_content_height(output_section.text_edit)
                output_section.text_edit.setMinimumHeight(content_height)
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
        """Expand output section - add to layout if first time."""
        if not self._output_section_shown:
            # First time showing output
            self.sections_layout.addWidget(self.output_section)
            self.output_edit.installEventFilter(self)
            self._output_section_shown = True
            self.output_edit.setVisible(True)
            self.output_header.set_collapsed(False)
            self._scroll_to_bottom()
        elif not self.output_edit.isVisible():
            # Already in layout, just expand
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
        self._disconnect_streaming_signal()

        # Check if streaming already updated the UI
        is_streaming = result.metadata and result.metadata.get("streaming", False)

        # Mark the current turn as complete and store output
        if self._conversation_turns:
            self._conversation_turns[-1].output_text = (
                result.content if result.success else None
            )
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

        # Only update text if NOT streaming (streaming already did it) or on error
        if not is_streaming or not result.success:
            if result.success and result.content:
                output_edit.setPlainText(result.content)
            elif result.error:
                output_edit.setPlainText(f"Error: {result.error}")
            else:
                output_edit.setPlainText("No output received")

        # Update height for expanded output sections (streaming blocks signals)
        if self._current_turn_number == 1 or not self._output_sections:
            if not self.output_header.is_wrapped():
                content_height = get_text_edit_content_height(self.output_edit)
                self.output_edit.setMinimumHeight(content_height)
        else:
            section = self._output_sections[-1]
            if not section.header.is_wrapped():
                content_height = get_text_edit_content_height(section.text_edit)
                section.text_edit.setMinimumHeight(content_height)

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
        self.sections_layout.addWidget(section)
        section.text_edit.installEventFilter(self)
        self.reply_btn.setVisible(False)
        section.text_edit.setFocus()
        self._update_delete_button_visibility()
        self._update_send_buttons_state()
        self._scroll_to_bottom()

    def _create_reply_section(self, turn_number: int) -> QWidget:
        """Create input section for a reply turn (displayed as Message)."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = CollapsibleSectionHeader(
            f"Message #{turn_number}",
            show_save_button=False,
            show_undo_redo=True,
            show_delete_button=True,
            show_wrap_button=True,
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

        text_edit = create_text_edit(placeholder="Type your message...")
        text_edit.textChanged.connect(self._update_send_buttons_state)
        layout.addWidget(text_edit)

        apply_section_size_policy(container, expanding=True, widget=text_edit)

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

        # Connect text changes for debounced state saving and height update
        text_edit.textChanged.connect(
            lambda s=container: self._schedule_dynamic_state_save(s)
        )
        text_edit.textChanged.connect(
            lambda s=container: self._update_dynamic_section_height(s)
        )

        # Wrap toggle function
        def toggle_wrap(c=container, h=header, te=text_edit):
            is_wrapped = h.is_wrapped()
            new_wrapped = not is_wrapped
            h.set_wrap_state(new_wrapped)
            if new_wrapped:
                te.setMinimumHeight(TEXT_EDIT_MIN_HEIGHT)
            else:
                content_height = get_text_edit_content_height(te)
                te.setMinimumHeight(content_height)

        header.wrap_requested.connect(toggle_wrap)

        # Toggle function for collapse/expand
        def toggle_section(c=container, h=header, te=text_edit, ic=images_container):
            is_visible = te.isVisible()
            te.setVisible(not is_visible)
            ic.setVisible(not is_visible and bool(c.turn_images))
            h.set_collapsed(is_visible)
            # Update size policy based on collapsed state
            if is_visible:  # Will be collapsed
                c.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            else:  # Will be expanded
                c.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        header.toggle_requested.connect(toggle_section)
        container.toggle_fn = toggle_section

        return container

    def _create_dynamic_output_section(self, turn_number: int) -> QWidget:
        """Create output section for a conversation turn."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = CollapsibleSectionHeader(
            f"Output #{turn_number}",
            show_save_button=False,
            show_undo_redo=True,
            show_delete_button=True,
            show_wrap_button=True,
        )
        layout.addWidget(header)

        text_edit = create_text_edit(placeholder="Output will appear here...")
        layout.addWidget(text_edit)

        apply_section_size_policy(container, expanding=True, widget=text_edit)

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

        # Connect text changes for debounced state saving and height update
        text_edit.textChanged.connect(
            lambda s=container: self._schedule_dynamic_state_save(s)
        )
        text_edit.textChanged.connect(
            lambda s=container: self._update_dynamic_section_height(s)
        )

        # Wrap toggle function
        def toggle_wrap(c=container, h=header, te=text_edit):
            is_wrapped = h.is_wrapped()
            new_wrapped = not is_wrapped
            h.set_wrap_state(new_wrapped)
            if new_wrapped:
                te.setMinimumHeight(TEXT_EDIT_MIN_HEIGHT)
            else:
                content_height = get_text_edit_content_height(te)
                te.setMinimumHeight(content_height)

        header.wrap_requested.connect(toggle_wrap)

        # Toggle function for collapse/expand
        def toggle_section(c=container, h=header, te=text_edit):
            is_visible = te.isVisible()
            te.setVisible(not is_visible)
            h.set_collapsed(is_visible)
            # Update size policy based on collapsed state
            if is_visible:  # Will be collapsed
                c.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            else:  # Will be expanded
                c.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

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
        has_content = bool(self.input_edit.toPlainText().strip()) or bool(
            self._message_images
        )

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
