"""Data classes for PromptExecuteDialog state management."""

from dataclasses import dataclass, field

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
    """Single turn in multi-turn conversation."""

    turn_number: int
    message_text: str
    message_images: list[ContextItem]
    output_text: str | None = None
    is_complete: bool = False
    output_versions: list[str] = field(default_factory=list)
    current_version_index: int = 0
    version_undo_states: list[OutputVersionState] = field(default_factory=list)


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

    # Message/Input section
    message_images: list[ContextItem]
    message_text: str
    input_undo_stack: list[PromptInputState]
    input_redo_stack: list[PromptInputState]
    last_input_text: str

    # Output section
    output_text: str
    output_section_shown: bool
    output_undo_stack: list[OutputState]
    output_redo_stack: list[OutputState]
    last_output_text: str

    # Multi-turn conversation
    conversation_turns: list[ConversationTurn]
    current_turn_number: int
    dynamic_sections_data: list[dict]  # Serialized reply sections
    output_sections_data: list[dict]  # Serialized output sections

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
