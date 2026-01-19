import pytest
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from unittest.mock import Mock


@dataclass
class ConversationTurn:
    turn_number: int
    message_text: str
    message_images: List = field(default_factory=list)
    output_text: Optional[str] = None
    is_complete: bool = False


@dataclass
class ContextItem:
    item_type: str
    data: str
    media_type: Optional[str] = None


@dataclass
class ContextSectionState:
    images: List[ContextItem]
    text: str


@dataclass
class PromptInputState:
    text: str


@dataclass
class OutputState:
    text: str


@dataclass
class TabState:
    tab_id: str
    tab_name: str
    context_images: List[ContextItem]
    context_text: str
    context_undo_stack: List[ContextSectionState]
    context_redo_stack: List[ContextSectionState]
    last_context_text: str
    message_images: List[ContextItem]
    message_text: str
    input_undo_stack: List[PromptInputState]
    input_redo_stack: List[PromptInputState]
    last_input_text: str
    output_text: str
    output_section_shown: bool
    output_undo_stack: List[OutputState]
    output_redo_stack: List[OutputState]
    last_output_text: str
    conversation_turns: List[ConversationTurn]
    current_turn_number: int
    dynamic_sections_data: List[Dict]
    output_sections_data: List[Dict]
    waiting_for_result: bool
    is_streaming: bool
    streaming_accumulated: str
    context_collapsed: bool
    input_collapsed: bool
    output_collapsed: bool
    context_wrapped: bool
    input_wrapped: bool
    output_wrapped: bool


def make_section(turn_number: int, text: str = "", images: list = None) -> Mock:
    section = Mock()
    section.turn_number = turn_number
    section.text_edit = Mock()
    section.text_edit.toPlainText.return_value = text
    section.turn_images = images if images is not None else []
    section.header = Mock()
    section.header.is_collapsed.return_value = False
    section.header.is_wrapped.return_value = False
    section.undo_stack = []
    section.redo_stack = []
    section.last_text = text
    return section


def make_output_section(turn_number: int, text: str = "") -> Mock:
    section = Mock()
    section.turn_number = turn_number
    section.text_edit = Mock()
    section.text_edit.toPlainText.return_value = text
    section.header = Mock()
    section.header.is_collapsed.return_value = False
    section.header.is_wrapped.return_value = False
    section.undo_stack = []
    section.redo_stack = []
    section.last_text = text
    return section


@pytest.fixture
def mock_dialog():
    dialog = Mock()
    dialog._waiting_for_result = False
    dialog._conversation_turns = []
    dialog._dynamic_sections = []
    dialog._output_sections = []
    dialog._output_section_shown = False
    dialog._message_images = []
    dialog._current_images = []
    dialog._disable_for_global_execution = False
    dialog._current_execution_id = None
    dialog._is_streaming = False
    dialog._streaming_accumulated = ""
    dialog._last_ui_update_time = 0
    dialog.output_edit = Mock()
    dialog.output_edit.toPlainText.return_value = ""
    dialog.input_edit = Mock()
    dialog.input_edit.toPlainText.return_value = ""
    dialog.context_text_edit = Mock()
    dialog.context_text_edit.toPlainText.return_value = ""
    dialog._context_undo_stack = []
    dialog._context_redo_stack = []
    dialog._input_undo_stack = []
    dialog._input_redo_stack = []
    dialog._output_undo_stack = []
    dialog._output_redo_stack = []
    dialog._last_context_text = ""
    dialog._last_input_text = ""
    dialog._last_output_text = ""
    return dialog


@pytest.fixture
def mock_dynamic_section():
    def _make(turn_number: int, text: str = "", images: list = None):
        return make_section(turn_number, text, images)
    return _make


@pytest.fixture
def mock_output_section():
    def _make(turn_number: int, text: str = ""):
        return make_output_section(turn_number, text)
    return _make
