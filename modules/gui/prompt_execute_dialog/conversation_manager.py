"""Conversation management for PromptExecuteDialog."""

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from core.context_manager import ContextItem, ContextItemType
from modules.gui.prompt_execute_dialog.data import (
    ConversationNode,
    ConversationTree,
    create_node,
)
from modules.gui.prompt_execute_dialog.message_widgets import (
    AssistantBubble,
    UserMessageBubble,
)
from modules.gui.shared.theme import (
    apply_section_size_policy,
    get_text_edit_content_height,
)
from modules.gui.shared.widgets import (
    TEXT_EDIT_MIN_HEIGHT,
    CollapsibleSectionHeader,
    ImageChipWidget,
    create_text_edit,
)

if TYPE_CHECKING:
    from modules.gui.prompt_execute_dialog.dialog import PromptExecuteDialog


class ConversationManager:
    """Manages multi-turn conversation state and dynamic sections.

    Handles:
    - Creating reply and output sections
    - Section deletion and renumbering
    - State capture/restore for tab switching
    - Validation of conversation state
    """

    def __init__(self, dialog: "PromptExecuteDialog"):
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
        header.undo_requested.connect(lambda s=container: dialog._undo_dynamic_section(s))
        header.redo_requested.connect(lambda s=container: dialog._redo_dynamic_section(s))

        # Connect delete signal
        header.delete_requested.connect(lambda s=container: self.delete_section(s))

        # Connect text changes for debounced state saving and height update
        text_edit.textChanged.connect(lambda s=container: dialog._schedule_dynamic_state_save(s))
        text_edit.textChanged.connect(lambda s=container: dialog._update_dynamic_section_height(s))

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
            show_version_nav=True,
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
        header.undo_requested.connect(lambda s=container: dialog._undo_dynamic_section(s))
        header.redo_requested.connect(lambda s=container: dialog._redo_dynamic_section(s))

        # Connect delete signal
        header.delete_requested.connect(lambda s=container: self.delete_section(s))

        # Connect version navigation signals
        header.version_prev_requested.connect(lambda s=container: dialog._on_version_prev_dynamic(s))
        header.version_next_requested.connect(lambda s=container: dialog._on_version_next_dynamic(s))

        # Connect text changes for debounced state saving and height update
        text_edit.textChanged.connect(lambda s=container: dialog._schedule_dynamic_state_save(s))
        text_edit.textChanged.connect(lambda s=container: dialog._update_dynamic_section_height(s))

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
            dialog._conversation_turns = [t for t in dialog._conversation_turns if t.turn_number != turn_number]

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

        return bool(
            (dialog._dynamic_sections or dialog._output_section_shown)
            and not dialog.input_edit.toPlainText().strip()
            and not dialog._message_images
        )

    def is_regenerate_mode(self) -> bool:
        """Check if dialog is in regenerate mode (can regenerate last output)."""
        dialog = self.dialog

        if dialog._execution_handler.is_waiting:
            return False

        if not dialog._conversation_turns or not dialog._conversation_turns[-1].is_complete:
            return False

        # If input_edit has content, user wants to send a new message, not regenerate
        if dialog.input_edit.toPlainText().strip() or dialog._message_images:
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
            chip.delete_requested.connect(lambda i, s=section: self._on_reply_image_delete(s, i))
            chip.copy_requested.connect(lambda i, s=section: self._on_reply_image_copy(s, i))
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

    def restore_dynamic_sections(self, reply_data: list[dict], output_data: list[dict]):
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

            # Restore version display from corresponding ConversationTurn
            turn_number = data["turn_number"]
            for turn in dialog._conversation_turns:
                if turn.turn_number == turn_number and turn.output_versions:
                    section.header.set_version_info(turn.current_version_index + 1, len(turn.output_versions))
                    break

    # --- Tree-Based Conversation Methods ---

    def add_user_message_to_tree(
        self,
        content: str,
        images: list[ContextItem] | None = None,
    ) -> ConversationNode:
        """Add a user message to the conversation tree.

        Args:
            content: Message text content
            images: Optional list of images

        Returns:
            The created user node
        """
        dialog = self.dialog
        tree = dialog._conversation_tree
        if not tree:
            tree = ConversationTree()
            dialog._conversation_tree = tree

        # Find parent (last node in current path, should be assistant or None)
        parent_id = None
        if tree.current_path:
            parent_id = tree.current_path[-1]

        user_node = create_node(
            role="user",
            content=content,
            parent_id=parent_id,
            images=images,
        )
        tree.append_to_current_path(user_node)
        return user_node

    def add_assistant_response_to_tree(
        self,
        content: str,
        user_node_id: str,
    ) -> ConversationNode:
        """Add an assistant response to the conversation tree.

        Args:
            content: Response text content
            user_node_id: ID of the parent user node

        Returns:
            The created assistant node
        """
        dialog = self.dialog
        tree = dialog._conversation_tree
        if not tree:
            return None

        assistant_node = create_node(
            role="assistant",
            content=content,
            parent_id=user_node_id,
        )
        tree.append_to_current_path(assistant_node)
        return assistant_node

    def regenerate_response_in_tree(self, assistant_node_id: str) -> ConversationNode:
        """Create a new branch by regenerating a response.

        This creates a new assistant node as a sibling of the existing one.

        Args:
            assistant_node_id: ID of the assistant node to regenerate

        Returns:
            The new assistant node (placeholder with empty content)
        """
        dialog = self.dialog
        tree = dialog._conversation_tree
        if not tree:
            return None

        old_node = tree.get_node(assistant_node_id)
        if not old_node or old_node.role != "assistant":
            return None

        parent_id = old_node.parent_id
        if not parent_id:
            return None

        # Create new assistant node as sibling
        new_node = create_node(
            role="assistant",
            content="",
            parent_id=parent_id,
        )
        tree.add_node(new_node)

        # Update current path to point to new branch
        try:
            old_idx = tree.current_path.index(assistant_node_id)
            tree.current_path = tree.current_path[:old_idx]
            tree._extend_path_to_leaf(new_node.node_id)
        except ValueError:
            tree.current_path.append(new_node.node_id)

        return new_node

    def get_tree_branch_count(self, node_id: str) -> tuple[int, int]:
        """Get the branch index and total count for a node.

        Args:
            node_id: The node ID

        Returns:
            Tuple of (current_index_1based, total_count)
        """
        dialog = self.dialog
        tree = dialog._conversation_tree
        if not tree:
            return (1, 1)

        siblings, idx = tree.get_siblings(node_id)
        return (idx + 1, len(siblings))

    def switch_to_branch(self, node_id: str, direction: int):
        """Switch to a different branch.

        Args:
            node_id: The node whose branch to switch
            direction: -1 for previous, +1 for next
        """
        dialog = self.dialog
        tree = dialog._conversation_tree
        if not tree:
            return

        node = tree.get_node(node_id)
        if not node or not node.parent_id:
            return

        siblings, idx = tree.get_siblings(node_id)
        new_idx = idx + direction
        if 0 <= new_idx < len(siblings):
            tree.switch_branch(node.parent_id, new_idx)
            dialog._rebuild_message_bubbles_from_tree()

    def is_tree_regenerate_mode(self) -> bool:
        """Check if dialog is in regenerate mode using tree structure."""
        dialog = self.dialog
        if dialog._execution_handler.is_waiting:
            return False

        tree = dialog._conversation_tree
        if not tree or tree.is_empty():
            return False

        # Regenerate mode: last node in path is an assistant node
        leaf = tree.get_current_leaf()
        if not leaf:
            return False

        return leaf.role == "assistant"

    def has_empty_tree_sections(self) -> bool:
        """Check if there are empty nodes in the tree path."""
        dialog = self.dialog
        tree = dialog._conversation_tree
        if not tree or tree.is_empty():
            return False

        # Check all nodes in current path except the last user node (current input)
        nodes = tree.get_current_branch()
        for i, node in enumerate(nodes):
            # Skip the last node if it's a user node (active input)
            if i == len(nodes) - 1 and node.role == "user":
                continue
            if not node.content.strip() and not node.images:
                return True
        return False
