from dataclasses import dataclass, field
from unittest.mock import Mock

import pytest


@dataclass
class ConversationTurn:
    turn_number: int
    message_text: str
    message_images: list = field(default_factory=list)
    output_text: str | None = None
    is_complete: bool = False


@dataclass
class ContextItem:
    item_type: str
    data: str
    media_type: str | None = None


@dataclass
class ContextSectionState:
    images: list[ContextItem]
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
    context_images: list[ContextItem]
    context_text: str
    context_undo_stack: list[ContextSectionState]
    context_redo_stack: list[ContextSectionState]
    last_context_text: str
    message_images: list[ContextItem]
    message_text: str
    input_undo_stack: list[PromptInputState]
    input_redo_stack: list[PromptInputState]
    last_input_text: str
    output_text: str
    output_section_shown: bool
    output_undo_stack: list[OutputState]
    output_redo_stack: list[OutputState]
    last_output_text: str
    conversation_turns: list[ConversationTurn]
    current_turn_number: int
    dynamic_sections_data: list[dict]
    output_sections_data: list[dict]
    waiting_for_result: bool
    is_streaming: bool
    streaming_accumulated: str
    context_collapsed: bool
    input_collapsed: bool
    output_collapsed: bool
    context_wrapped: bool
    input_wrapped: bool
    output_wrapped: bool
    history_entry_id: str | None = None


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


@dataclass
class OutputVersionState:
    undo_stack: list[str] = field(default_factory=list)
    redo_stack: list[str] = field(default_factory=list)
    last_text: str = ""


def make_turn_with_versions(
    turn_number: int = 1,
    message_text: str = "test message",
    output_versions: list[str] = None,
    current_version_index: int = 0,
    version_undo_states: list[OutputVersionState] = None,
    is_complete: bool = True,
) -> "ConversationTurnWithVersions":
    return ConversationTurnWithVersions(
        turn_number=turn_number,
        message_text=message_text,
        output_versions=output_versions if output_versions else ["output"],
        current_version_index=current_version_index,
        version_undo_states=version_undo_states if version_undo_states else [],
        is_complete=is_complete,
    )


@dataclass
class ConversationTurnWithVersions:
    turn_number: int
    message_text: str
    message_images: list = field(default_factory=list)
    output_text: str | None = None
    is_complete: bool = False
    output_versions: list[str] = field(default_factory=list)
    current_version_index: int = 0
    version_undo_states: list[OutputVersionState] = field(default_factory=list)
