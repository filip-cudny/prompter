"""Conversation management for MessageShareDialog."""

from typing import List, Dict, Optional, TYPE_CHECKING

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy
from PyQt5.QtCore import QTimer

from core.context_manager import ContextItem, ContextItemType
from modules.gui.dialog_styles import (
    apply_section_size_policy,
    get_text_edit_content_height,
)
from modules.gui.shared_widgets import (
    CollapsibleSectionHeader,
    ImageChipWidget,
    create_text_edit,
    TEXT_EDIT_MIN_HEIGHT,
)
from modules.gui.message_share_data import ConversationTurn, TabState

if TYPE_CHECKING:
    from modules.gui.message_share_dialog import MessageShareDialog


class ConversationManager:
    """Manages multi-turn conversation state and dynamic sections.

    Handles:
    - Creating reply and output sections
    - Section deletion and renumbering
    - State capture/restore for tab switching
    - Validation of conversation state
    """

    def __init__(self, dialog: "MessageShareDialog"):
        self.dialog = dialog

    # --- Section Creation ---

    def create_reply_section(self, turn_number: int) -> QWidget:
        """Create input section for a reply turn (displayed as Message).

        Args:
            turn_number: Visual turn number for the header

        Returns:
            Container widget with all section components attached as attributes
        """
        dialog = self.dialog
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

        text_edit = create_text_edit(
            placeholder="Type your message...\n(Ctrl+Enter: Close & get result to clipboard | Alt+Enter: Send & show | Ctrl+V: Paste image)"
        )
        text_edit.textChanged.connect(dialog._update_send_buttons_state)
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
        header.undo_requested.connect(
            lambda s=container: dialog._undo_dynamic_section(s)
        )
        header.redo_requested.connect(
            lambda s=container: dialog._redo_dynamic_section(s)
        )

        # Connect delete signal
        header.delete_requested.connect(lambda s=container: self.delete_section(s))

        # Connect text changes for debounced state saving and height update
        text_edit.textChanged.connect(
            lambda s=container: dialog._schedule_dynamic_state_save(s)
        )
        text_edit.textChanged.connect(
            lambda s=container: dialog._update_dynamic_section_height(s)
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

    def create_dynamic_output_section(self, turn_number: int) -> QWidget:
        """Create output section for a conversation turn.

        Args:
            turn_number: Turn number for the header

        Returns:
            Container widget with all section components attached as attributes
        """
        dialog = self.dialog
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
        header.undo_requested.connect(
            lambda s=container: dialog._undo_dynamic_section(s)
        )
        header.redo_requested.connect(
            lambda s=container: dialog._redo_dynamic_section(s)
        )

        # Connect delete signal
        header.delete_requested.connect(lambda s=container: self.delete_section(s))

        # Connect text changes for debounced state saving and height update
        text_edit.textChanged.connect(
            lambda s=container: dialog._schedule_dynamic_state_save(s)
        )
        text_edit.textChanged.connect(
            lambda s=container: dialog._update_dynamic_section_height(s)
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

    # --- Section Management ---

    def delete_section(self, section: QWidget):
        """Delete a single dynamic section (only the one clicked)."""
        dialog = self.dialog

        # Handle Message section deletion
        if section in dialog._dynamic_sections:
            if section != dialog._dynamic_sections[-1]:
                return  # Only allow deleting last message

            # Remove only the message section
            dialog._dynamic_sections.remove(section)
            section.setParent(None)
            section.deleteLater()

        # Handle Output section deletion
        elif section in dialog._output_sections:
            if section != dialog._output_sections[-1]:
                return  # Only allow deleting last output

            # Remove only the output section
            dialog._output_sections.remove(section)
            section.setParent(None)
            section.deleteLater()

        # Remove corresponding turn from conversation history
        turn_number = getattr(section, "turn_number", None)
        if turn_number is not None:
            dialog._conversation_turns = [
                t for t in dialog._conversation_turns if t.turn_number != turn_number
            ]

        # Update section numbering and delete button visibility
        self.renumber_sections()
        self.update_delete_button_visibility()

        # Show reply button if we have output to reply to
        if dialog._output_section_shown or dialog._output_sections:
            dialog.reply_btn.setVisible(True)

        dialog._update_send_buttons_state()

    def renumber_sections(self):
        """Update section headers to reflect correct visual numbering."""
        dialog = self.dialog
        dialog.input_header.set_title("Message #1")
        dialog.output_header.set_title("Output #1")

        for idx, section in enumerate(dialog._dynamic_sections):
            section.header.set_title(f"Message #{idx + 2}")

        for idx, section in enumerate(dialog._output_sections):
            section.header.set_title(f"Output #{idx + 2}")

    def clear_dynamic_sections(self):
        """Remove all dynamic reply and output sections from layout."""
        dialog = self.dialog

        for section in dialog._dynamic_sections:
            dialog.sections_layout.removeWidget(section)
            section.setParent(None)
            section.deleteLater()
        dialog._dynamic_sections.clear()

        for section in dialog._output_sections:
            dialog.sections_layout.removeWidget(section)
            section.setParent(None)
            section.deleteLater()
        dialog._output_sections.clear()

    def update_delete_button_visibility(self):
        """Show delete button only on the absolute last section (bottom-most)."""
        dialog = self.dialog

        # Hide delete on all dynamic sections
        for section in dialog._dynamic_sections:
            section.header.set_delete_button_visible(False)
        for section in dialog._output_sections:
            section.header.set_delete_button_visible(False)

        # Determine which section is at the bottom
        # Sections alternate: Message -> Output -> Message -> Output
        # Message #N has turn_number = N+1, Output #N has turn_number = N
        # When user clicks Reply after Output #N, Message #N is created (turn N+1)
        # So if both exist, compare turn numbers to find the bottom one

        if dialog._dynamic_sections and dialog._output_sections:
            msg_turn = dialog._dynamic_sections[-1].turn_number
            out_turn = dialog._output_sections[-1].turn_number
            # Message section's turn_number is the turn it was created FOR
            # Output section's turn_number is the turn it displays results FOR
            # If msg_turn > out_turn, message is at the bottom (user is typing reply)
            # If out_turn >= msg_turn, output is at the bottom (just received response)
            if msg_turn > out_turn:
                dialog._dynamic_sections[-1].header.set_delete_button_visible(True)
            else:
                dialog._output_sections[-1].header.set_delete_button_visible(True)
        elif dialog._dynamic_sections:
            dialog._dynamic_sections[-1].header.set_delete_button_visible(True)
        elif dialog._output_sections:
            dialog._output_sections[-1].header.set_delete_button_visible(True)

    # --- Validation ---

    def has_empty_conversation_sections(self) -> bool:
        """Check if there are empty sections in conversation history (excluding current input).

        This prevents errors from having gaps in the conversation.
        """
        dialog = self.dialog

        if dialog._output_section_shown and not dialog.output_edit.toPlainText().strip():
            return True

        for section in dialog._output_sections:
            if not section.text_edit.toPlainText().strip():
                return True

        for section in dialog._dynamic_sections[:-1]:
            if not section.text_edit.toPlainText().strip() and not section.turn_images:
                return True

        if dialog._dynamic_sections or dialog._output_section_shown:
            if (
                not dialog.input_edit.toPlainText().strip()
                and not dialog._message_images
            ):
                return True

        return False

    def is_regenerate_mode(self) -> bool:
        """Check if dialog is in regenerate mode (can regenerate last output)."""
        dialog = self.dialog

        if dialog._execution_handler.is_waiting:
            return False

        if (
            not dialog._conversation_turns
            or not dialog._conversation_turns[-1].is_complete
        ):
            return False

        if not dialog._dynamic_sections:
            return True

        if dialog._output_sections:
            msg_turn = dialog._dynamic_sections[-1].turn_number
            out_turn = dialog._output_sections[-1].turn_number
            return out_turn >= msg_turn

        return False

    # --- Reply Image Handling ---

    def rebuild_reply_image_chips(self, section: QWidget):
        """Rebuild image chips for a reply section."""
        dialog = self.dialog

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
            self.rebuild_reply_image_chips(section)
            self.dialog._update_send_buttons_state()

    def _on_reply_image_copy(self, section: QWidget, index: int):
        """Handle reply image copy request."""
        if 0 <= index < len(section.image_chips):
            section.image_chips[index].copy_to_clipboard()

    def paste_image_to_reply(self, section: QWidget) -> bool:
        """Paste image to reply section."""
        dialog = self.dialog
        if not dialog.clipboard_manager or not dialog.clipboard_manager.has_image():
            return False

        image_data = dialog.clipboard_manager.get_image_data()
        if image_data:
            base64_data, media_type = image_data
            new_image = ContextItem(
                item_type=ContextItemType.IMAGE,
                data=base64_data,
                media_type=media_type,
            )
            section.turn_images.append(new_image)
            self.rebuild_reply_image_chips(section)
            dialog._update_send_buttons_state()
            return True
        return False

    # --- State Capture/Restore ---

    def restore_dynamic_sections(
        self, reply_data: List[Dict], output_data: List[Dict]
    ):
        """Recreate dynamic sections from serialized data."""
        dialog = self.dialog

        # Recreate reply sections
        for data in reply_data:
            section = self.create_reply_section(data["turn_number"])
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
            self.rebuild_reply_image_chips(section)

            # Restore collapsed/wrapped state
            if data.get("collapsed", False):
                section.toggle_fn()
            section.header.set_wrap_state(data.get("wrapped", True))

            dialog._dynamic_sections.append(section)
            dialog.sections_layout.addWidget(section)
            section.text_edit.installEventFilter(dialog)

        # Recreate output sections
        for data in output_data:
            section = self.create_dynamic_output_section(data["turn_number"])
            section.text_edit.setPlainText(data["text"])
            section.undo_stack = list(data["undo_stack"])
            section.redo_stack = list(data["redo_stack"])
            section.last_text = data["last_text"]

            # Restore collapsed/wrapped state
            if data.get("collapsed", False):
                section.toggle_fn()
            section.header.set_wrap_state(data.get("wrapped", True))

            dialog._output_sections.append(section)
            dialog.sections_layout.addWidget(section)
            section.text_edit.installEventFilter(dialog)
