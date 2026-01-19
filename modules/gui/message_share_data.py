"""Data classes for MessageShareDialog state management."""

from dataclasses import dataclass
from typing import List, Optional, Dict

from core.context_manager import ContextItem


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
