"""Data classes for PromptExecuteDialog state management."""

import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

from core.context_manager import ContextItem


@dataclass
class OutputVersionState:
    """Undo/redo state for a single output version."""

    undo_stack: list[str] = field(default_factory=list)
    redo_stack: list[str] = field(default_factory=list)
    last_text: str = ""


@dataclass
class ContextSectionState:
    """Snapshot of context section state for undo/redo."""

    images: list[ContextItem]
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
    """Single turn in multi-turn conversation (legacy, kept for backward compatibility)."""

    turn_number: int
    message_text: str
    message_images: list[ContextItem]
    output_text: str | None = None
    is_complete: bool = False
    output_versions: list[str] = field(default_factory=list)
    current_version_index: int = 0
    version_undo_states: list[OutputVersionState] = field(default_factory=list)


@dataclass
class ConversationNode:
    """A single node in the conversation tree."""

    node_id: str
    parent_id: str | None
    role: Literal["user", "assistant"]
    content: str
    images: list[ContextItem] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    children: list[str] = field(default_factory=list)
    undo_stack: list[str] = field(default_factory=list)
    redo_stack: list[str] = field(default_factory=list)
    last_text: str = ""


def create_node(
    role: Literal["user", "assistant"],
    content: str,
    parent_id: str | None = None,
    images: list[ContextItem] | None = None,
) -> ConversationNode:
    """Create a new conversation node with a unique ID."""
    return ConversationNode(
        node_id=str(uuid.uuid4()),
        parent_id=parent_id,
        role=role,
        content=content,
        images=images or [],
        last_text=content,
    )


@dataclass
class ConversationTree:
    """Tree structure for branched conversations."""

    nodes: dict[str, ConversationNode] = field(default_factory=dict)
    root_node_id: str | None = None
    current_path: list[str] = field(default_factory=list)

    def get_node(self, node_id: str) -> ConversationNode | None:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def add_node(self, node: ConversationNode) -> None:
        """Add a node to the tree."""
        self.nodes[node.node_id] = node
        if node.parent_id and node.parent_id in self.nodes:
            parent = self.nodes[node.parent_id]
            if node.node_id not in parent.children:
                parent.children.append(node.node_id)
        if self.root_node_id is None and node.parent_id is None:
            self.root_node_id = node.node_id

    def get_current_branch(self) -> list[ConversationNode]:
        """Get nodes in the current path from root to current leaf."""
        return [self.nodes[nid] for nid in self.current_path if nid in self.nodes]

    def get_siblings(self, node_id: str) -> tuple[list[str], int]:
        """Get sibling IDs and current index for a node.

        Returns:
            Tuple of (sibling_ids, current_index)
        """
        node = self.nodes.get(node_id)
        if not node or not node.parent_id:
            return [node_id] if node else [], 0
        parent = self.nodes.get(node.parent_id)
        if not parent:
            return [node_id], 0
        siblings = parent.children
        try:
            idx = siblings.index(node_id)
        except ValueError:
            idx = 0
        return siblings, idx

    def switch_branch(self, node_id: str, new_child_idx: int) -> None:
        """Switch to a different branch at the given node.

        Args:
            node_id: The node whose child branch to switch
            new_child_idx: Index of the new child branch to follow
        """
        node = self.nodes.get(node_id)
        if not node or not node.children:
            return
        if new_child_idx < 0 or new_child_idx >= len(node.children):
            return

        try:
            node_path_idx = self.current_path.index(node_id)
        except ValueError:
            return

        self.current_path = self.current_path[: node_path_idx + 1]
        new_child_id = node.children[new_child_idx]
        self._extend_path_to_leaf(new_child_id)

    def _extend_path_to_leaf(self, start_node_id: str) -> None:
        """Extend the current path from a node to its first leaf."""
        current_id = start_node_id
        while current_id:
            self.current_path.append(current_id)
            node = self.nodes.get(current_id)
            if not node or not node.children:
                break
            current_id = node.children[0]

    def get_current_leaf(self) -> ConversationNode | None:
        """Get the current leaf node."""
        if not self.current_path:
            return None
        return self.nodes.get(self.current_path[-1])

    def append_to_current_path(self, node: ConversationNode) -> None:
        """Add a node and append it to the current path."""
        self.add_node(node)
        self.current_path.append(node.node_id)

    def get_message_pairs(self) -> list[tuple[ConversationNode, ConversationNode | None]]:
        """Get user-assistant message pairs from the current path.

        Returns:
            List of (user_node, assistant_node) tuples. assistant_node may be None
            if the user message has no response yet.
        """
        pairs = []
        nodes = self.get_current_branch()
        i = 0
        while i < len(nodes):
            if nodes[i].role == "user":
                user_node = nodes[i]
                assistant_node = None
                if i + 1 < len(nodes) and nodes[i + 1].role == "assistant":
                    assistant_node = nodes[i + 1]
                    i += 1
                pairs.append((user_node, assistant_node))
            i += 1
        return pairs

    def is_empty(self) -> bool:
        """Check if the tree has no nodes."""
        return len(self.nodes) == 0


@dataclass
class TabState:
    """Complete state of a conversation tab."""

    tab_id: str
    tab_name: str

    # Context section
    context_images: list[ContextItem]
    context_text: str
    context_undo_stack: list[ContextSectionState]
    context_redo_stack: list[ContextSectionState]
    last_context_text: str

    # Message/Input section (for the sticky input at bottom)
    message_images: list[ContextItem]
    message_text: str
    input_undo_stack: list[PromptInputState]
    input_redo_stack: list[PromptInputState]
    last_input_text: str

    # Output section (legacy - for backward compatibility)
    output_text: str
    output_section_shown: bool
    output_undo_stack: list[OutputState]
    output_redo_stack: list[OutputState]
    last_output_text: str

    # Tree-based conversation (new)
    conversation_tree: ConversationTree | None

    # Legacy: linear conversation (kept for backward compatibility)
    conversation_turns: list[ConversationTurn]
    current_turn_number: int
    dynamic_sections_data: list[dict]
    output_sections_data: list[dict]

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

    # History tracking (must be at end due to default value)
    history_entry_id: str | None = None
