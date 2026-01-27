import logging
import time
from collections import deque
from collections.abc import Callable

from core.context_manager import ContextItem, ContextItemType
from core.models import (
    ConversationHistoryData,
    HistoryEntry,
    HistoryEntryType,
    SerializedConversationNode,
    SerializedConversationTurn,
)
from modules.history import image_storage

logger = logging.getLogger(__name__)


class HistoryService:
    """Service for tracking execution history."""

    def __init__(self, max_entries: int = 100):
        self.max_entries = max_entries
        self._history: deque = deque(maxlen=max_entries)
        self._change_callbacks: list[Callable[[], None]] = []

    def add_entry(
        self,
        input_content: str,
        entry_type: HistoryEntryType,
        output_content: str | None = None,
        prompt_id: str | None = None,
        success: bool = True,
        error: str | None = None,
        is_conversation: bool = False,
        prompt_name: str | None = None,
    ) -> None:
        """Add a new history entry."""
        entry = HistoryEntry(
            id=str(int(time.time() * 1000)),  # millisecond timestamp as ID
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            input_content=input_content,
            entry_type=entry_type,
            output_content=output_content,
            prompt_id=prompt_id,
            success=success,
            error=error,
            is_conversation=is_conversation,
            prompt_name=prompt_name,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._history.append(entry)
        self._notify_change()

    def add_change_callback(self, callback: Callable[[], None]) -> None:
        """Add a callback to be notified when history changes."""
        if callback not in self._change_callbacks:
            self._change_callbacks.append(callback)

    def remove_change_callback(self, callback: Callable[[], None]) -> None:
        """Remove a change callback."""
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)

    def _notify_change(self) -> None:
        """Notify all registered callbacks of a change."""
        for callback in self._change_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in history change callback: {e}")

    def get_history(self) -> list[HistoryEntry]:
        """Get all history entries, sorted by most recently updated/created first."""
        entries = list(self._history)
        entries.sort(key=lambda e: e.updated_at or e.created_at or e.timestamp, reverse=True)
        return entries

    def clear_history(self) -> None:
        """Clear all history entries."""
        self._history.clear()

    def get_entry_by_id(self, entry_id: str) -> HistoryEntry | None:
        """Get a specific history entry by ID."""
        for entry in self._history:
            if entry.id == entry_id:
                return entry
        return None

    def get_last_item_by_type(self, entry_type: HistoryEntryType) -> HistoryEntry | None:
        """Get the most recent history entry of the specified type."""
        for entry in reversed(self._history):
            if entry.entry_type == entry_type:
                return entry
        return None

    def initialize(self) -> None:
        """Initialize service - clear temp images on startup."""
        image_storage.initialize()
        logger.debug("History service initialized, temp images cleared")

    def add_conversation_entry(
        self,
        turns: list,
        context_text: str,
        context_images: list[ContextItem],
        prompt_id: str | None = None,
        prompt_name: str | None = None,
        success: bool = True,
        error: str | None = None,
        conversation_tree=None,
    ) -> str:
        """Create new conversation history entry.

        Args:
            turns: List of ConversationTurn objects from the dialog (legacy)
            context_text: Context text content
            context_images: List of context ContextItems with image data
            prompt_id: ID of the prompt used
            prompt_name: Name of the prompt
            success: Whether execution was successful
            error: Error message if unsuccessful
            conversation_tree: ConversationTree object (new tree-based format)

        Returns:
            Entry ID for later updates
        """
        context_image_paths = self._save_images_to_temp(context_images)
        serialized_turns = self._serialize_turns(turns)

        # Serialize tree if provided
        serialized_nodes = []
        root_node_id = None
        current_path = []
        if conversation_tree and not conversation_tree.is_empty():
            serialized_nodes = self._serialize_tree_nodes(conversation_tree)
            root_node_id = conversation_tree.root_node_id
            current_path = list(conversation_tree.current_path)

        conv_data = ConversationHistoryData(
            context_text=context_text,
            context_image_paths=context_image_paths,
            turns=serialized_turns,
            prompt_id=prompt_id,
            prompt_name=prompt_name,
            nodes=serialized_nodes,
            root_node_id=root_node_id,
            current_path=current_path,
        )

        input_summary = self._build_input_summary(turns)
        output_summary = self._build_output_summary(turns)

        entry = HistoryEntry(
            id=str(int(time.time() * 1000)),
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            input_content=input_summary,
            entry_type=HistoryEntryType.TEXT,
            output_content=output_summary,
            prompt_id=prompt_id,
            success=success,
            error=error,
            is_conversation=True,
            prompt_name=prompt_name,
            conversation_data=conv_data,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._history.append(entry)
        self._notify_change()

        logger.debug(f"Added conversation entry {entry.id} with {len(turns)} turns")
        return entry.id

    def update_conversation_entry(
        self,
        entry_id: str,
        turns: list,
        context_text: str,
        context_images: list[ContextItem],
        conversation_tree=None,
    ) -> bool:
        """Update existing conversation entry with new turns.

        Args:
            entry_id: ID of the entry to update
            turns: Updated list of ConversationTurn objects
            context_text: Current context text
            context_images: Current context images
            conversation_tree: ConversationTree object (new tree-based format)

        Returns:
            True if update successful, False if entry not found
        """
        entry = self.get_entry_by_id(entry_id)
        if not entry or not entry.conversation_data:
            logger.warning(f"Conversation entry {entry_id} not found for update")
            return False

        context_image_paths = self._save_images_to_temp(context_images)
        serialized_turns = self._serialize_turns(turns)

        entry.conversation_data.context_text = context_text
        entry.conversation_data.context_image_paths = context_image_paths
        entry.conversation_data.turns = serialized_turns

        # Update tree if provided
        if conversation_tree and not conversation_tree.is_empty():
            entry.conversation_data.nodes = self._serialize_tree_nodes(conversation_tree)
            entry.conversation_data.root_node_id = conversation_tree.root_node_id
            entry.conversation_data.current_path = list(conversation_tree.current_path)

        entry.input_content = self._build_input_summary(turns)
        entry.output_content = self._build_output_summary(turns)
        entry.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        entry.updated_at = time.strftime("%Y-%m-%d %H:%M:%S")

        self._notify_change()
        logger.debug(f"Updated conversation entry {entry_id} to {len(turns)} turns")
        return True

    def get_conversation_data(self, entry_id: str) -> ConversationHistoryData | None:
        """Get full conversation data for restoration.

        Args:
            entry_id: ID of the history entry

        Returns:
            ConversationHistoryData or None if not found
        """
        entry = self.get_entry_by_id(entry_id)
        if entry and entry.conversation_data:
            return entry.conversation_data
        return None

    def load_images_from_paths(self, paths: list[str]) -> list[ContextItem]:
        """Load images from disk back into ContextItems.

        Args:
            paths: List of file paths to load

        Returns:
            List of ContextItems with loaded image data
        """
        items = []
        for path in paths:
            result = image_storage.load_image(path)
            if result:
                base64_data, media_type = result
                items.append(
                    ContextItem(
                        item_type=ContextItemType.IMAGE,
                        data=base64_data,
                        media_type=media_type,
                    )
                )
        return items

    def _save_images_to_temp(self, images: list[ContextItem]) -> list[str]:
        """Save ContextItem images to temp storage.

        Args:
            images: List of ContextItems with image data

        Returns:
            List of file paths to saved images
        """
        paths = []
        for img in images:
            if img.item_type == ContextItemType.IMAGE and img.data:
                path = image_storage.save_image(img.data, img.media_type or "image/png")
                if path:
                    paths.append(path)
        return paths

    def _serialize_turns(self, turns: list) -> list[SerializedConversationTurn]:
        """Convert ConversationTurn objects to serializable form.

        Args:
            turns: List of ConversationTurn objects from dialog

        Returns:
            List of SerializedConversationTurn for storage
        """
        serialized = []
        for turn in turns:
            image_paths = self._save_images_to_temp(turn.message_images)
            serialized.append(
                SerializedConversationTurn(
                    turn_number=turn.turn_number,
                    message_text=turn.message_text,
                    message_image_paths=image_paths,
                    output_text=turn.output_text,
                    is_complete=turn.is_complete,
                    output_versions=list(turn.output_versions),
                    current_version_index=turn.current_version_index,
                )
            )
        return serialized

    def _serialize_tree_nodes(self, tree) -> list[SerializedConversationNode]:
        """Convert ConversationTree nodes to serializable form.

        Args:
            tree: ConversationTree object from dialog

        Returns:
            List of SerializedConversationNode for storage
        """
        serialized = []
        for node in tree.nodes.values():
            image_paths = self._save_images_to_temp(node.images) if node.images else []
            serialized.append(
                SerializedConversationNode(
                    node_id=node.node_id,
                    parent_id=node.parent_id,
                    role=node.role,
                    content=node.content,
                    image_paths=image_paths,
                    timestamp=node.timestamp,
                    children=list(node.children),
                )
            )
        return serialized

    def deserialize_tree_nodes(self, conv_data: ConversationHistoryData):
        """Deserialize tree nodes from history data.

        Args:
            conv_data: ConversationHistoryData with serialized nodes

        Returns:
            ConversationTree object or None if no tree data
        """
        from modules.gui.prompt_execute_dialog.data import ConversationNode, ConversationTree

        if not conv_data.nodes:
            return None

        tree = ConversationTree()
        tree.root_node_id = conv_data.root_node_id
        tree.current_path = list(conv_data.current_path)

        for node_data in conv_data.nodes:
            images = self.load_images_from_paths(node_data.image_paths)
            node = ConversationNode(
                node_id=node_data.node_id,
                parent_id=node_data.parent_id,
                role=node_data.role,
                content=node_data.content,
                images=images,
                timestamp=node_data.timestamp,
                children=list(node_data.children),
                last_text=node_data.content,
            )
            tree.nodes[node.node_id] = node

        return tree

    def _build_input_summary(self, turns: list) -> str:
        """Build summary of input content for history display.

        Args:
            turns: List of ConversationTurn objects

        Returns:
            Summary string for display
        """
        if not turns:
            return "(no input)"
        last_turn = turns[-1]
        last_msg = last_turn.message_text
        if not last_msg and last_turn.message_images:
            last_msg = "(image)"
        if not last_msg:
            last_msg = "(empty)"
        if len(turns) > 1:
            return f"{last_msg[:100]}... (+{len(turns) - 1} more)"
        return last_msg[:200] if len(last_msg) > 200 else last_msg

    def _build_output_summary(self, turns: list) -> str:
        """Build summary of output content for history display.

        Args:
            turns: List of ConversationTurn objects

        Returns:
            Summary string for display
        """
        complete_turns = [t for t in turns if t.is_complete and t.output_text]
        if not complete_turns:
            return "(no output yet)"
        last_output = complete_turns[-1].output_text or ""
        if len(complete_turns) > 1:
            return f"{last_output[:100]}... (+{len(complete_turns) - 1} more)"
        return last_output[:200] if len(last_output) > 200 else last_output
