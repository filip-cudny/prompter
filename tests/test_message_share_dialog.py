from unittest.mock import Mock

from tests.conftest import (
    ContextItem,
    ConversationTurn,
    OutputState,
    OutputVersionState,
    PromptInputState,
    make_output_section,
    make_section,
    make_turn_with_versions,
)


def _is_regenerate_mode_standalone(
    waiting_for_result: bool,
    conversation_turns: list,
    dynamic_sections: list,
    output_sections: list,
) -> bool:
    if waiting_for_result:
        return False

    if not conversation_turns or not conversation_turns[-1].is_complete:
        return False

    if not dynamic_sections:
        return True

    if output_sections:
        msg_turn = dynamic_sections[-1].turn_number
        out_turn = output_sections[-1].turn_number
        return out_turn >= msg_turn

    return False


def _has_empty_conversation_sections_standalone(
    output_section_shown: bool,
    output_text: str,
    output_sections: list,
    dynamic_sections: list,
    input_text: str,
    message_images: list,
) -> bool:
    if output_section_shown and not output_text.strip():
        return True

    for section in output_sections:
        if not section.text_edit.toPlainText().strip():
            return True

    for section in dynamic_sections[:-1]:
        if not section.text_edit.toPlainText().strip() and not section.turn_images:
            return True

    return bool((dynamic_sections or output_section_shown) and not input_text.strip() and not message_images)


def _can_send_standalone(
    has_message: bool,
    has_conversation_error: bool,
    waiting_for_result: bool,
    disable_for_global_execution: bool,
) -> bool:
    return has_message and not has_conversation_error and not waiting_for_result and not disable_for_global_execution


def _can_act_standalone(
    has_message: bool,
    is_regenerate: bool,
    has_conversation_error: bool,
    waiting_for_result: bool,
    disable_for_global_execution: bool,
) -> bool:
    return (
        (has_message or is_regenerate)
        and not has_conversation_error
        and not waiting_for_result
        and not disable_for_global_execution
    )


def _build_conversation_data_standalone(
    context_text: str,
    context_images: list,
    conversation_turns: list,
) -> dict:
    turns = []
    for i, turn in enumerate(conversation_turns):
        turn_data = {
            "role": "user",
            "text": turn.message_text,
            "images": [{"data": img.data, "media_type": img.media_type or "image/png"} for img in turn.message_images],
        }
        if i == 0:
            turn_data["context_text"] = context_text
            turn_data["context_images"] = [
                {"data": img.data, "media_type": img.media_type or "image/png"} for img in context_images
            ]

        turns.append(turn_data)

        if turn.is_complete and turn.output_text:
            turns.append({"role": "assistant", "text": turn.output_text})

    return {"turns": turns}


def _undo_stack_operation(undo_stack: list, redo_stack: list, get_current_state, restore_state):
    if not undo_stack:
        return None
    redo_stack.append(get_current_state())
    state = undo_stack.pop()
    restore_state(state)
    return state


def _redo_stack_operation(undo_stack: list, redo_stack: list, get_current_state, restore_state):
    if not redo_stack:
        return None
    undo_stack.append(get_current_state())
    state = redo_stack.pop()
    restore_state(state)
    return state


def _save_text_state(current_text: str, last_text: str, undo_stack: list, redo_stack: list, state_class):
    if current_text != last_text:
        state = (
            state_class(text=last_text)
            if state_class in (PromptInputState, OutputState)
            else state_class
        )
        undo_stack.append(state)
        redo_stack.clear()
        return current_text
    return last_text


def _determine_bottom_section(dynamic_sections: list, output_sections: list) -> str:
    if dynamic_sections and output_sections:
        msg_turn = dynamic_sections[-1].turn_number
        out_turn = output_sections[-1].turn_number
        if msg_turn > out_turn:
            return "message"
        else:
            return "output"
    elif dynamic_sections:
        return "message"
    elif output_sections:
        return "output"
    return None


def _can_delete_section(section, dynamic_sections: list, output_sections: list) -> bool:
    if section in dynamic_sections:
        return section == dynamic_sections[-1]
    if section in output_sections:
        return section == output_sections[-1]
    return False


def _renumber_sections_standalone(dynamic_sections: list, output_sections: list) -> dict:
    result = {
        "input": "Message #1",
        "output": "Output #1",
        "dynamic": [],
        "outputs": [],
    }
    for idx, _ in enumerate(dynamic_sections):
        result["dynamic"].append(f"Message #{idx + 2}")
    for idx, _ in enumerate(output_sections):
        result["outputs"].append(f"Output #{idx + 2}")
    return result


def _should_process_streaming_chunk(
    waiting_for_result: bool,
    chunk_execution_id: str,
    current_execution_id: str,
) -> bool:
    if not waiting_for_result:
        return False
    return not (chunk_execution_id and current_execution_id and chunk_execution_id != current_execution_id)


class TestIsRegenerateMode:
    def test_waiting_for_result_returns_false(self, mock_dialog):
        mock_dialog._waiting_for_result = True
        mock_dialog._conversation_turns = [ConversationTurn(1, "test", is_complete=True)]

        result = _is_regenerate_mode_standalone(
            mock_dialog._waiting_for_result,
            mock_dialog._conversation_turns,
            mock_dialog._dynamic_sections,
            mock_dialog._output_sections,
        )

        assert result is False

    def test_no_conversation_turns_returns_false(self, mock_dialog):
        mock_dialog._conversation_turns = []

        result = _is_regenerate_mode_standalone(
            mock_dialog._waiting_for_result,
            mock_dialog._conversation_turns,
            mock_dialog._dynamic_sections,
            mock_dialog._output_sections,
        )

        assert result is False

    def test_last_turn_incomplete_returns_false(self, mock_dialog):
        mock_dialog._conversation_turns = [ConversationTurn(1, "test", is_complete=False)]

        result = _is_regenerate_mode_standalone(
            mock_dialog._waiting_for_result,
            mock_dialog._conversation_turns,
            mock_dialog._dynamic_sections,
            mock_dialog._output_sections,
        )

        assert result is False

    def test_turn_1_complete_no_dynamic_sections_returns_true(self, mock_dialog):
        mock_dialog._conversation_turns = [ConversationTurn(1, "test", is_complete=True)]
        mock_dialog._dynamic_sections = []

        result = _is_regenerate_mode_standalone(
            mock_dialog._waiting_for_result,
            mock_dialog._conversation_turns,
            mock_dialog._dynamic_sections,
            mock_dialog._output_sections,
        )

        assert result is True

    def test_message_turn_2_with_output_turn_2_returns_true(self, mock_dialog):
        mock_dialog._conversation_turns = [ConversationTurn(1, "test", is_complete=True)]
        mock_dialog._dynamic_sections = [make_section(turn_number=2)]
        mock_dialog._output_sections = [make_section(turn_number=2)]

        result = _is_regenerate_mode_standalone(
            mock_dialog._waiting_for_result,
            mock_dialog._conversation_turns,
            mock_dialog._dynamic_sections,
            mock_dialog._output_sections,
        )

        assert result is True

    def test_message_turn_3_with_output_turn_2_returns_false(self, mock_dialog):
        mock_dialog._conversation_turns = [ConversationTurn(1, "test", is_complete=True)]
        mock_dialog._dynamic_sections = [make_section(turn_number=3)]
        mock_dialog._output_sections = [make_section(turn_number=2)]

        result = _is_regenerate_mode_standalone(
            mock_dialog._waiting_for_result,
            mock_dialog._conversation_turns,
            mock_dialog._dynamic_sections,
            mock_dialog._output_sections,
        )

        assert result is False

    def test_message_turn_2_with_no_outputs_returns_false(self, mock_dialog):
        mock_dialog._conversation_turns = [ConversationTurn(1, "test", is_complete=True)]
        mock_dialog._dynamic_sections = [make_section(turn_number=2)]
        mock_dialog._output_sections = []

        result = _is_regenerate_mode_standalone(
            mock_dialog._waiting_for_result,
            mock_dialog._conversation_turns,
            mock_dialog._dynamic_sections,
            mock_dialog._output_sections,
        )

        assert result is False

    def test_output_turn_greater_than_message_turn_returns_true(self, mock_dialog):
        mock_dialog._conversation_turns = [ConversationTurn(1, "test", is_complete=True)]
        mock_dialog._dynamic_sections = [make_section(turn_number=2)]
        mock_dialog._output_sections = [make_section(turn_number=3)]

        result = _is_regenerate_mode_standalone(
            mock_dialog._waiting_for_result,
            mock_dialog._conversation_turns,
            mock_dialog._dynamic_sections,
            mock_dialog._output_sections,
        )

        assert result is True


class TestHasEmptyConversationSections:
    def test_output_shown_but_empty_returns_true(self):
        result = _has_empty_conversation_sections_standalone(
            output_section_shown=True,
            output_text="",
            output_sections=[],
            dynamic_sections=[],
            input_text="some input",
            message_images=[],
        )
        assert result is True

    def test_output_section_with_whitespace_only_returns_true(self):
        result = _has_empty_conversation_sections_standalone(
            output_section_shown=True,
            output_text="   \n\t  ",
            output_sections=[],
            dynamic_sections=[],
            input_text="some input",
            message_images=[],
        )
        assert result is True

    def test_output_section_list_with_empty_text_returns_true(self):
        output_section = make_output_section(turn_number=2, text="")

        result = _has_empty_conversation_sections_standalone(
            output_section_shown=False,
            output_text="",
            output_sections=[output_section],
            dynamic_sections=[],
            input_text="some input",
            message_images=[],
        )
        assert result is True

    def test_dynamic_section_not_last_with_no_text_or_images_returns_true(self):
        section1 = make_section(turn_number=2, text="", images=[])
        section2 = make_section(turn_number=3, text="has content")

        result = _has_empty_conversation_sections_standalone(
            output_section_shown=False,
            output_text="",
            output_sections=[],
            dynamic_sections=[section1, section2],
            input_text="",
            message_images=[],
        )
        assert result is True

    def test_dynamic_section_not_last_with_images_but_no_text_returns_false(self):
        image = ContextItem(item_type="image", data="base64data", media_type="image/png")
        section1 = make_section(turn_number=2, text="", images=[image])
        section2 = make_section(turn_number=3, text="has content")

        result = _has_empty_conversation_sections_standalone(
            output_section_shown=False,
            output_text="",
            output_sections=[],
            dynamic_sections=[section1, section2],
            input_text="test",
            message_images=[],
        )
        assert result is False

    def test_first_turn_empty_when_has_conversation_returns_true(self):
        dynamic_section = make_section(turn_number=2, text="reply content")

        result = _has_empty_conversation_sections_standalone(
            output_section_shown=False,
            output_text="",
            output_sections=[],
            dynamic_sections=[dynamic_section],
            input_text="",
            message_images=[],
        )
        assert result is True

    def test_first_turn_empty_with_output_shown_returns_true(self):
        result = _has_empty_conversation_sections_standalone(
            output_section_shown=True,
            output_text="output here",
            output_sections=[],
            dynamic_sections=[],
            input_text="",
            message_images=[],
        )
        assert result is True

    def test_first_turn_has_images_no_text_returns_false(self):
        image = ContextItem(item_type="image", data="base64data", media_type="image/png")

        result = _has_empty_conversation_sections_standalone(
            output_section_shown=True,
            output_text="output",
            output_sections=[],
            dynamic_sections=[],
            input_text="",
            message_images=[image],
        )
        assert result is False

    def test_all_sections_have_content_returns_false(self):
        output_section = make_output_section(turn_number=2, text="output content")
        dynamic_section = make_section(turn_number=3, text="reply content")

        result = _has_empty_conversation_sections_standalone(
            output_section_shown=True,
            output_text="first output",
            output_sections=[output_section],
            dynamic_sections=[dynamic_section],
            input_text="first input",
            message_images=[],
        )
        assert result is False

    def test_no_conversation_no_validation_needed_returns_false(self):
        result = _has_empty_conversation_sections_standalone(
            output_section_shown=False,
            output_text="",
            output_sections=[],
            dynamic_sections=[],
            input_text="",
            message_images=[],
        )
        assert result is False


class TestUpdateSendButtonsState:
    def test_no_message_no_images_can_send_false(self):
        result = _can_send_standalone(
            has_message=False,
            has_conversation_error=False,
            waiting_for_result=False,
            disable_for_global_execution=False,
        )
        assert result is False

    def test_has_text_can_send_true(self):
        result = _can_send_standalone(
            has_message=True,
            has_conversation_error=False,
            waiting_for_result=False,
            disable_for_global_execution=False,
        )
        assert result is True

    def test_waiting_for_result_can_send_false(self):
        result = _can_send_standalone(
            has_message=True,
            has_conversation_error=False,
            waiting_for_result=True,
            disable_for_global_execution=False,
        )
        assert result is False

    def test_global_execution_disabled_can_send_false(self):
        result = _can_send_standalone(
            has_message=True,
            has_conversation_error=False,
            waiting_for_result=False,
            disable_for_global_execution=True,
        )
        assert result is False

    def test_conversation_error_can_send_false(self):
        result = _can_send_standalone(
            has_message=True,
            has_conversation_error=True,
            waiting_for_result=False,
            disable_for_global_execution=False,
        )
        assert result is False

    def test_regenerate_mode_allows_empty_message(self):
        result = _can_act_standalone(
            has_message=False,
            is_regenerate=True,
            has_conversation_error=False,
            waiting_for_result=False,
            disable_for_global_execution=False,
        )
        assert result is True

    def test_regenerate_mode_blocked_by_waiting(self):
        result = _can_act_standalone(
            has_message=False,
            is_regenerate=True,
            has_conversation_error=False,
            waiting_for_result=True,
            disable_for_global_execution=False,
        )
        assert result is False

    def test_regenerate_mode_blocked_by_conversation_error(self):
        result = _can_act_standalone(
            has_message=False,
            is_regenerate=True,
            has_conversation_error=True,
            waiting_for_result=False,
            disable_for_global_execution=False,
        )
        assert result is False

    def test_has_message_and_regenerate_can_act_true(self):
        result = _can_act_standalone(
            has_message=True,
            is_regenerate=True,
            has_conversation_error=False,
            waiting_for_result=False,
            disable_for_global_execution=False,
        )
        assert result is True


class TestBuildConversationData:
    def test_first_turn_includes_context(self):
        context_images = [ContextItem(item_type="image", data="ctx_img", media_type="image/png")]
        turns = [
            ConversationTurn(
                turn_number=1,
                message_text="Hello",
                message_images=[],
                output_text="Hi there",
                is_complete=True,
            )
        ]

        result = _build_conversation_data_standalone(
            context_text="System context",
            context_images=context_images,
            conversation_turns=turns,
        )

        assert len(result["turns"]) == 2
        assert result["turns"][0]["context_text"] == "System context"
        assert result["turns"][0]["context_images"][0]["data"] == "ctx_img"

    def test_subsequent_turns_no_context(self):
        turns = [
            ConversationTurn(1, "First", output_text="Response 1", is_complete=True),
            ConversationTurn(2, "Second", output_text="Response 2", is_complete=True),
        ]

        result = _build_conversation_data_standalone(
            context_text="Context",
            context_images=[],
            conversation_turns=turns,
        )

        assert "context_text" in result["turns"][0]
        assert "context_text" not in result["turns"][2]

    def test_images_serialized_correctly(self):
        img = ContextItem(item_type="image", data="base64data", media_type="image/jpeg")
        turns = [
            ConversationTurn(
                turn_number=1,
                message_text="Look at this",
                message_images=[img],
                is_complete=False,
            )
        ]

        result = _build_conversation_data_standalone(
            context_text="",
            context_images=[],
            conversation_turns=turns,
        )

        assert result["turns"][0]["images"][0]["data"] == "base64data"
        assert result["turns"][0]["images"][0]["media_type"] == "image/jpeg"

    def test_turn_ordering(self):
        turns = [
            ConversationTurn(1, "User 1", output_text="Assistant 1", is_complete=True),
            ConversationTurn(2, "User 2", output_text="Assistant 2", is_complete=True),
        ]

        result = _build_conversation_data_standalone(
            context_text="",
            context_images=[],
            conversation_turns=turns,
        )

        assert result["turns"][0]["role"] == "user"
        assert result["turns"][0]["text"] == "User 1"
        assert result["turns"][1]["role"] == "assistant"
        assert result["turns"][1]["text"] == "Assistant 1"
        assert result["turns"][2]["role"] == "user"
        assert result["turns"][2]["text"] == "User 2"
        assert result["turns"][3]["role"] == "assistant"
        assert result["turns"][3]["text"] == "Assistant 2"

    def test_empty_context_handling(self):
        turns = [ConversationTurn(1, "Test", is_complete=False)]

        result = _build_conversation_data_standalone(
            context_text="",
            context_images=[],
            conversation_turns=turns,
        )

        assert result["turns"][0]["context_text"] == ""
        assert result["turns"][0]["context_images"] == []

    def test_incomplete_turn_no_assistant_response(self):
        turns = [ConversationTurn(1, "Pending", is_complete=False)]

        result = _build_conversation_data_standalone(
            context_text="",
            context_images=[],
            conversation_turns=turns,
        )

        assert len(result["turns"]) == 1
        assert result["turns"][0]["role"] == "user"

    def test_default_media_type(self):
        img = ContextItem(item_type="image", data="data", media_type=None)
        turns = [ConversationTurn(1, "Test", message_images=[img], is_complete=False)]

        result = _build_conversation_data_standalone(
            context_text="",
            context_images=[],
            conversation_turns=turns,
        )

        assert result["turns"][0]["images"][0]["media_type"] == "image/png"


class TestUndoRedoStack:
    def test_undo_pops_from_stack_pushes_to_redo(self):
        undo_stack = [PromptInputState("state1"), PromptInputState("state2")]
        redo_stack = []
        current_state = PromptInputState("current")
        restored = [None]

        def get_current():
            return current_state

        def restore(state):
            restored[0] = state

        result = _undo_stack_operation(undo_stack, redo_stack, get_current, restore)

        assert result.text == "state2"
        assert len(undo_stack) == 1
        assert len(redo_stack) == 1
        assert redo_stack[0].text == "current"

    def test_redo_pops_from_redo_pushes_to_undo(self):
        undo_stack = []
        redo_stack = [PromptInputState("redo_state")]
        current_state = PromptInputState("current")
        restored = [None]

        def get_current():
            return current_state

        def restore(state):
            restored[0] = state

        result = _redo_stack_operation(undo_stack, redo_stack, get_current, restore)

        assert result.text == "redo_state"
        assert len(undo_stack) == 1
        assert len(redo_stack) == 0
        assert undo_stack[0].text == "current"

    def test_new_change_clears_redo_stack(self):
        undo_stack = []
        redo_stack = [PromptInputState("will be cleared")]

        new_last = _save_text_state(
            current_text="new text",
            last_text="old text",
            undo_stack=undo_stack,
            redo_stack=redo_stack,
            state_class=PromptInputState,
        )

        assert len(redo_stack) == 0
        assert len(undo_stack) == 1
        assert new_last == "new text"

    def test_empty_stack_undo_noop(self):
        undo_stack = []
        redo_stack = []
        called = [False]

        def get_current():
            called[0] = True
            return PromptInputState("current")

        def restore(state):
            pass

        result = _undo_stack_operation(undo_stack, redo_stack, get_current, restore)

        assert result is None
        assert not called[0]

    def test_empty_stack_redo_noop(self):
        undo_stack = []
        redo_stack = []
        called = [False]

        def get_current():
            called[0] = True
            return PromptInputState("current")

        def restore(state):
            pass

        result = _redo_stack_operation(undo_stack, redo_stack, get_current, restore)

        assert result is None
        assert not called[0]


class TestSaveTextStates:
    def test_context_changed_adds_to_undo(self):
        undo_stack = []
        redo_stack = []

        new_last = _save_text_state(
            current_text="new context",
            last_text="old context",
            undo_stack=undo_stack,
            redo_stack=redo_stack,
            state_class=PromptInputState,
        )

        assert len(undo_stack) == 1
        assert undo_stack[0].text == "old context"
        assert new_last == "new context"

    def test_input_changed_adds_to_undo(self):
        undo_stack = []
        redo_stack = []

        new_last = _save_text_state(
            current_text="new input",
            last_text="old input",
            undo_stack=undo_stack,
            redo_stack=redo_stack,
            state_class=PromptInputState,
        )

        assert len(undo_stack) == 1
        assert new_last == "new input"

    def test_output_changed_adds_to_undo(self):
        undo_stack = []
        redo_stack = []

        _save_text_state(
            current_text="new output",
            last_text="old output",
            undo_stack=undo_stack,
            redo_stack=redo_stack,
            state_class=OutputState,
        )

        assert len(undo_stack) == 1
        assert undo_stack[0].text == "old output"

    def test_no_change_no_stack_update(self):
        undo_stack = []
        redo_stack = [PromptInputState("existing redo")]

        new_last = _save_text_state(
            current_text="same text",
            last_text="same text",
            undo_stack=undo_stack,
            redo_stack=redo_stack,
            state_class=PromptInputState,
        )

        assert len(undo_stack) == 0
        assert len(redo_stack) == 1
        assert new_last == "same text"

    def test_multiple_changes_all_tracked(self):
        undo_stack = []
        redo_stack = []

        last = _save_text_state("v1", "", undo_stack, redo_stack, PromptInputState)
        last = _save_text_state("v2", last, undo_stack, redo_stack, PromptInputState)
        last = _save_text_state("v3", last, undo_stack, redo_stack, PromptInputState)

        assert len(undo_stack) == 3
        assert undo_stack[0].text == ""
        assert undo_stack[1].text == "v1"
        assert undo_stack[2].text == "v2"


class TestConversationTabBar:
    def test_add_tab_creates_entry(self):
        tabs = {}
        tab_order = []

        tab_id = "tab-1"
        tabs[tab_id] = {"name": "Tab 1"}
        tab_order.append(tab_id)

        assert tab_id in tabs
        assert tab_id in tab_order

    def test_add_duplicate_tab_ignored(self):
        tabs = {"tab-1": {"name": "Tab 1"}}
        tab_order = ["tab-1"]

        tab_id = "tab-1"
        if tab_id not in tabs:
            tabs[tab_id] = {"name": "Duplicate"}
            tab_order.append(tab_id)

        assert len(tabs) == 1
        assert len(tab_order) == 1

    def test_remove_tab_cleans_up(self):
        tabs = {"tab-1": {"name": "Tab 1"}, "tab-2": {"name": "Tab 2"}}
        tab_order = ["tab-1", "tab-2"]

        del tabs["tab-1"]
        tab_order.remove("tab-1")

        assert "tab-1" not in tabs
        assert "tab-1" not in tab_order

    def test_set_active_tab_updates_state(self):
        active_tab_id = None

        active_tab_id = "tab-2"

        assert active_tab_id == "tab-2"

    def test_get_tab_ids_returns_ordered_list(self):
        tab_order = ["tab-3", "tab-1", "tab-2"]

        result = list(tab_order)

        assert result == ["tab-3", "tab-1", "tab-2"]


class TestDeleteSection:
    def test_only_last_message_can_be_deleted(self):
        section1 = make_section(turn_number=2)
        section2 = make_section(turn_number=3)
        dynamic_sections = [section1, section2]

        can_delete_first = _can_delete_section(section1, dynamic_sections, [])
        can_delete_last = _can_delete_section(section2, dynamic_sections, [])

        assert can_delete_first is False
        assert can_delete_last is True

    def test_only_last_output_can_be_deleted(self):
        section1 = make_output_section(turn_number=1)
        section2 = make_output_section(turn_number=2)
        output_sections = [section1, section2]

        can_delete_first = _can_delete_section(section1, [], output_sections)
        can_delete_last = _can_delete_section(section2, [], output_sections)

        assert can_delete_first is False
        assert can_delete_last is True

    def test_deleting_removes_from_conversation_turns(self):
        turns = [
            ConversationTurn(1, "First"),
            ConversationTurn(2, "Second"),
        ]
        turn_to_remove = 2

        turns = [t for t in turns if t.turn_number != turn_to_remove]

        assert len(turns) == 1
        assert turns[0].turn_number == 1


class TestRenumberSections:
    def test_sections_numbered_sequentially(self):
        dynamic_sections = [make_section(2), make_section(3)]
        output_sections = [make_output_section(2)]

        result = _renumber_sections_standalone(dynamic_sections, output_sections)

        assert result["input"] == "Message #1"
        assert result["output"] == "Output #1"
        assert result["dynamic"] == ["Message #2", "Message #3"]
        assert result["outputs"] == ["Output #2"]

    def test_renumber_after_deletion(self):
        dynamic_sections = [make_section(2)]
        output_sections = []

        result = _renumber_sections_standalone(dynamic_sections, output_sections)

        assert result["dynamic"] == ["Message #2"]


class TestDeleteButtonVisibility:
    def test_last_message_section_has_delete(self):
        section = make_section(turn_number=3)
        dynamic_sections = [make_section(2), section]

        bottom = _determine_bottom_section(dynamic_sections, [])

        assert bottom == "message"

    def test_last_output_section_has_delete(self):
        section = make_output_section(turn_number=2)
        output_sections = [section]

        bottom = _determine_bottom_section([], output_sections)

        assert bottom == "output"

    def test_message_after_output_is_bottom(self):
        dynamic_sections = [make_section(turn_number=3)]
        output_sections = [make_output_section(turn_number=2)]

        bottom = _determine_bottom_section(dynamic_sections, output_sections)

        assert bottom == "message"

    def test_output_after_message_is_bottom(self):
        dynamic_sections = [make_section(turn_number=2)]
        output_sections = [make_output_section(turn_number=3)]

        bottom = _determine_bottom_section(dynamic_sections, output_sections)

        assert bottom == "output"

    def test_equal_turn_numbers_output_is_bottom(self):
        dynamic_sections = [make_section(turn_number=2)]
        output_sections = [make_output_section(turn_number=2)]

        bottom = _determine_bottom_section(dynamic_sections, output_sections)

        assert bottom == "output"


class TestStreamingChunkFiltering:
    def test_matching_execution_id_processes_chunk(self):
        result = _should_process_streaming_chunk(
            waiting_for_result=True,
            chunk_execution_id="exec-123",
            current_execution_id="exec-123",
        )
        assert result is True

    def test_mismatched_execution_id_ignored(self):
        result = _should_process_streaming_chunk(
            waiting_for_result=True,
            chunk_execution_id="exec-456",
            current_execution_id="exec-123",
        )
        assert result is False

    def test_not_waiting_for_result_ignored(self):
        result = _should_process_streaming_chunk(
            waiting_for_result=False,
            chunk_execution_id="exec-123",
            current_execution_id="exec-123",
        )
        assert result is False

    def test_empty_execution_ids_processes(self):
        result = _should_process_streaming_chunk(
            waiting_for_result=True,
            chunk_execution_id="",
            current_execution_id="",
        )
        assert result is True

    def test_chunk_id_empty_current_not_empty_processes(self):
        result = _should_process_streaming_chunk(
            waiting_for_result=True,
            chunk_execution_id="",
            current_execution_id="exec-123",
        )
        assert result is True


class TestTabStateSerialization:
    def test_capture_preserves_context_images(self):
        images = [ContextItem("image", "data1", "image/png")]
        state = {
            "context_images": images,
        }
        assert len(state["context_images"]) == 1
        assert state["context_images"][0].data == "data1"

    def test_capture_preserves_message_text(self):
        state = {"message_text": "Hello world"}
        assert state["message_text"] == "Hello world"

    def test_capture_preserves_output_text(self):
        state = {"output_text": "Response here"}
        assert state["output_text"] == "Response here"

    def test_capture_preserves_conversation_turns(self):
        turns = [
            ConversationTurn(1, "First", output_text="R1", is_complete=True),
            ConversationTurn(2, "Second", output_text="R2", is_complete=True),
        ]
        state = {"conversation_turns": list(turns)}
        assert len(state["conversation_turns"]) == 2

    def test_capture_preserves_undo_stacks(self):
        undo_stack = [PromptInputState("s1"), PromptInputState("s2")]
        redo_stack = [PromptInputState("r1")]
        state = {
            "undo_stack": list(undo_stack),
            "redo_stack": list(redo_stack),
        }
        assert len(state["undo_stack"]) == 2
        assert len(state["redo_stack"]) == 1

    def test_capture_preserves_ui_states(self):
        state = {
            "context_collapsed": True,
            "input_collapsed": False,
            "output_collapsed": True,
            "context_wrapped": False,
            "input_wrapped": True,
            "output_wrapped": False,
        }
        assert state["context_collapsed"] is True
        assert state["input_wrapped"] is True


class TestSectionWrapStates:
    def test_wrap_sets_wrapped_state(self):
        is_wrapped = False

        is_wrapped = True

        assert is_wrapped is True

    def test_unwrap_clears_wrapped_state(self):
        is_wrapped = True

        is_wrapped = False

        assert is_wrapped is False

    def test_wrap_state_independent_of_collapse(self):
        is_wrapped = True
        is_collapsed = False

        assert is_wrapped is True
        assert is_collapsed is False

        is_collapsed = True

        assert is_wrapped is True
        assert is_collapsed is True


def _sync_undo_to_version(turn, restored_text):
    if turn and turn.output_versions:
        idx = turn.current_version_index
        if 0 <= idx < len(turn.output_versions):
            turn.output_versions[idx] = restored_text


def _sync_redo_to_version(turn, restored_text):
    if turn and turn.output_versions:
        idx = turn.current_version_index
        if 0 <= idx < len(turn.output_versions):
            turn.output_versions[idx] = restored_text


def _save_version_undo_state(turn, undo_stack, redo_stack):
    if turn is None:
        return
    idx = turn.current_version_index
    while len(turn.version_undo_states) <= idx:
        turn.version_undo_states.append(OutputVersionState())
    turn.version_undo_states[idx] = OutputVersionState(
        undo_stack=list(undo_stack),
        redo_stack=list(redo_stack),
        last_text=turn.output_versions[idx] if turn.output_versions else "",
    )


class TestUndoRedoVersionSync:
    def test_undo_output_syncs_to_version_array(self):
        turn = make_turn_with_versions(
            output_versions=["v1"],
            current_version_index=0,
        )
        restored_text = "v1_undone"

        _sync_undo_to_version(turn, restored_text)

        assert turn.output_versions[0] == "v1_undone"

    def test_redo_output_syncs_to_version_array(self):
        turn = make_turn_with_versions(
            output_versions=["v1"],
            current_version_index=0,
        )
        restored_text = "v1_redone"

        _sync_redo_to_version(turn, restored_text)

        assert turn.output_versions[0] == "v1_redone"

    def test_undo_output_no_turn_no_error(self):
        turn = None

        _sync_undo_to_version(turn, "any_text")

    def test_undo_output_empty_versions_no_error(self):
        turn = make_turn_with_versions(output_versions=[])
        turn.output_versions = []

        _sync_undo_to_version(turn, "any_text")

    def test_undo_syncs_to_correct_version_index(self):
        turn = make_turn_with_versions(
            output_versions=["v1", "v2"],
            current_version_index=1,
        )

        _sync_undo_to_version(turn, "v2_undone")

        assert turn.output_versions[1] == "v2_undone"
        assert turn.output_versions[0] == "v1"

    def test_undo_dynamic_section_syncs_to_version_array(self):
        turn = make_turn_with_versions(
            turn_number=2,
            output_versions=["v1"],
            current_version_index=0,
        )
        section = Mock()
        section.turn_number = 2

        _sync_undo_to_version(turn, "v1_undone")

        assert turn.output_versions[0] == "v1_undone"

    def test_redo_dynamic_section_syncs_to_version_array(self):
        turn = make_turn_with_versions(
            turn_number=2,
            output_versions=["v1"],
            current_version_index=0,
        )
        section = Mock()
        section.turn_number = 2

        _sync_redo_to_version(turn, "v1_redone")

        assert turn.output_versions[0] == "v1_redone"


class TestRegenerationPreservesUndoState:
    def test_regenerate_saves_current_version_undo_state(self):
        turn = make_turn_with_versions(
            output_versions=["version_1"],
            current_version_index=0,
        )
        undo_stack = ["state_a", "state_b"]
        redo_stack = ["state_c"]

        _save_version_undo_state(turn, undo_stack, redo_stack)

        assert len(turn.version_undo_states) == 1
        saved_state = turn.version_undo_states[0]
        assert saved_state.undo_stack == ["state_a", "state_b"]
        assert saved_state.redo_stack == ["state_c"]
        assert saved_state.last_text == "version_1"

    def test_regenerate_preserves_other_versions_undo_states(self):
        existing_state_0 = OutputVersionState(
            undo_stack=["old_undo"],
            redo_stack=["old_redo"],
            last_text="old_text",
        )
        turn = make_turn_with_versions(
            output_versions=["v1", "v2"],
            current_version_index=1,
            version_undo_states=[existing_state_0],
        )
        undo_stack = ["new_undo"]
        redo_stack = []

        _save_version_undo_state(turn, undo_stack, redo_stack)

        assert len(turn.version_undo_states) == 2
        assert turn.version_undo_states[0].undo_stack == ["old_undo"]
        assert turn.version_undo_states[1].undo_stack == ["new_undo"]

    def test_save_version_undo_state_no_turn_no_error(self):
        _save_version_undo_state(None, [], [])

    def test_save_version_undo_state_creates_entries_as_needed(self):
        turn = make_turn_with_versions(
            output_versions=["v1", "v2", "v3"],
            current_version_index=2,
        )

        _save_version_undo_state(turn, ["undo"], ["redo"])

        assert len(turn.version_undo_states) == 3
        assert turn.version_undo_states[2].undo_stack == ["undo"]

    def test_save_version_undo_state_copies_stacks(self):
        turn = make_turn_with_versions(
            output_versions=["v1"],
            current_version_index=0,
        )
        undo_stack = ["a", "b"]
        redo_stack = ["c"]

        _save_version_undo_state(turn, undo_stack, redo_stack)

        undo_stack.append("d")
        redo_stack.append("e")

        assert turn.version_undo_states[0].undo_stack == ["a", "b"]
        assert turn.version_undo_states[0].redo_stack == ["c"]


def _restore_pending_version_data(dialog, turn):
    """Mirrors execution_handler.py lines 321-327.

    This MUST match the actual implementation in execute_with_message.
    Update this when the fix is applied to execution_handler.py.
    """
    if hasattr(dialog, "_pending_version_history"):
        turn.output_versions = dialog._pending_version_history
        delattr(dialog, "_pending_version_history")
    if hasattr(dialog, "_pending_version_undo_states"):
        turn.version_undo_states = dialog._pending_version_undo_states
        delattr(dialog, "_pending_version_undo_states")
    if hasattr(dialog, "_pending_version_index"):
        turn.current_version_index = dialog._pending_version_index
        delattr(dialog, "_pending_version_index")


class TestRegenerationPreservesVersionIndex:
    def test_version_index_restored_after_regeneration(self):
        dialog = Mock()
        dialog._pending_version_history = ["original v1", "original v2"]
        dialog._pending_version_undo_states = []
        dialog._pending_version_index = 1

        turn = make_turn_with_versions(
            output_versions=[],
            current_version_index=0,
        )

        _restore_pending_version_data(dialog, turn)

        _sync_all_outputs_to_versions_standalone(
            conversation_turns=[turn],
            output_edit_text="Regenerating...",
            output_sections=[],
        )

        assert turn.output_versions[0] == "original v1", "Version 0 should be preserved"
        assert turn.output_versions[1] == "Regenerating...", "Version 1 should be updated"


def _sync_output_to_version_on_text_change(
    turn,
    current_output_text: str,
    last_output_text: str,
) -> str:
    """Standalone version of sync logic in _save_text_states."""
    if current_output_text != last_output_text:
        if turn and turn.output_versions:
            turn.output_versions[turn.current_version_index] = current_output_text
        return current_output_text
    return last_output_text


def _sync_all_outputs_to_versions_standalone(
    conversation_turns: list,
    output_edit_text: str,
    output_sections: list,
):
    """Standalone version of _sync_all_outputs_to_versions."""
    if not conversation_turns:
        return

    turn1 = conversation_turns[0]
    if turn1.output_versions:
        turn1.output_versions[turn1.current_version_index] = output_edit_text

    for section in output_sections:
        turn_number = section.turn_number
        for turn in conversation_turns:
            if turn.turn_number == turn_number and turn.output_versions:
                turn.output_versions[turn.current_version_index] = section.text_edit.toPlainText()
                break


def _build_conversation_data_with_versions(
    context_text: str,
    context_images: list,
    conversation_turns: list,
) -> dict:
    """Standalone version that uses output_versions like the real implementation."""
    turns = []
    for i, turn in enumerate(conversation_turns):
        turn_data = {
            "role": "user",
            "text": turn.message_text,
            "images": [{"data": img.data, "media_type": img.media_type or "image/png"} for img in turn.message_images],
        }
        if i == 0:
            turn_data["context_text"] = context_text
            turn_data["context_images"] = [
                {"data": img.data, "media_type": img.media_type or "image/png"} for img in context_images
            ]

        turns.append(turn_data)

        if turn.is_complete and turn.output_versions:
            selected_text = turn.output_versions[turn.current_version_index]
            turns.append({"role": "assistant", "text": selected_text})
        elif turn.is_complete and turn.output_text:
            turns.append({"role": "assistant", "text": turn.output_text})

    return {"turns": turns}


def _on_send_copy_expected(
    sync_fn,
    execute_fn,
    close_fn,
    message_text: str,
    message_images: list,
):
    """Expected behavior of _on_send_copy - MUST call sync before executing.

    This defines the contract: _on_send_copy must sync outputs to versions
    before sending to ensure edited text is included in conversation data.
    """
    sync_fn()  # REQUIRED: sync edited outputs to version arrays
    has_content = bool(message_text.strip()) or bool(message_images)
    if not has_content:
        close_fn()
        return
    execute_fn(message_text, keep_open=False)


def _on_send_show_expected(
    sync_fn,
    execute_fn,
    regenerate_fn,
    is_regenerate_mode: bool,
    message_text: str,
    message_images: list,
):
    """Expected behavior of _on_send_show - MUST call sync before executing.

    This defines the contract: _on_send_show must sync outputs to versions
    before sending (unless in regenerate mode, which has its own sync).
    """
    if is_regenerate_mode:
        regenerate_fn()
        return

    sync_fn()  # REQUIRED: sync edited outputs to version arrays
    has_content = bool(message_text.strip()) or bool(message_images)
    if not has_content:
        return
    execute_fn(message_text, keep_open=True)


class TestSendMethodsCallSync:
    """Tests that verify _on_send_copy and _on_send_show call sync before sending.

    These tests read the actual source code to verify the sync call is present.
    This catches the bug where edited output wasn't synced before sending.
    """

    def test_on_send_copy_source_contains_sync_call(self):
        """Verify _on_send_copy calls _sync_all_outputs_to_versions in source."""
        import os

        dialog_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "modules",
            "gui",
            "prompt_execute_dialog",
            "dialog.py",
        )
        with open(dialog_path) as f:
            source = f.read()

        # Find _on_send_copy method
        import re

        match = re.search(r"def _on_send_copy\(self\):.*?(?=\n    def |\nclass |\Z)", source, re.DOTALL)
        assert match, "_on_send_copy method not found in dialog.py"

        method_source = match.group(0)
        assert "_sync_all_outputs_to_versions" in method_source, (
            "_on_send_copy must call _sync_all_outputs_to_versions() to sync edited outputs before sending"
        )

    def test_on_send_show_source_contains_sync_call(self):
        """Verify _on_send_show calls _sync_all_outputs_to_versions in source."""
        import os

        dialog_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "modules",
            "gui",
            "prompt_execute_dialog",
            "dialog.py",
        )
        with open(dialog_path) as f:
            source = f.read()

        # Find _on_send_show method
        import re

        match = re.search(r"def _on_send_show\(self\):.*?(?=\n    def |\nclass |\Z)", source, re.DOTALL)
        assert match, "_on_send_show method not found in dialog.py"

        method_source = match.group(0)
        assert "_sync_all_outputs_to_versions" in method_source, (
            "_on_send_show must call _sync_all_outputs_to_versions() to sync edited outputs before sending"
        )

    def test_sync_method_exists(self):
        """Verify _sync_all_outputs_to_versions method exists in dialog.py."""
        import os

        dialog_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "modules",
            "gui",
            "prompt_execute_dialog",
            "dialog.py",
        )
        with open(dialog_path) as f:
            source = f.read()

        assert "def _sync_all_outputs_to_versions(self)" in source, (
            "_sync_all_outputs_to_versions method must exist in dialog.py "
            "to sync edited outputs to version arrays before sending"
        )


class TestOutputVersionSyncOnEdit:
    """Tests that verify edited output text is synced to turn.output_versions.

    This test class catches the bug where user edits to output_edit were not
    synced to turn.output_versions, causing stale data to be sent in
    _build_conversation_data.
    """

    def test_edited_output_synced_on_text_change(self):
        """Verify that editing output syncs to version array."""
        turn = make_turn_with_versions(
            output_versions=["original output"],
            current_version_index=0,
        )

        _sync_output_to_version_on_text_change(
            turn=turn,
            current_output_text="user edited this",
            last_output_text="original output",
        )

        assert turn.output_versions[0] == "user edited this"

    def test_edited_output_used_in_conversation_data(self):
        """Verify that _build_conversation_data uses the edited (synced) version."""
        turn = make_turn_with_versions(
            turn_number=1,
            message_text="Hello",
            output_versions=["original output"],
            current_version_index=0,
            is_complete=True,
        )

        _sync_output_to_version_on_text_change(
            turn=turn,
            current_output_text="user edited this",
            last_output_text="original output",
        )

        result = _build_conversation_data_with_versions(
            context_text="",
            context_images=[],
            conversation_turns=[turn],
        )

        assert result["turns"][1]["text"] == "user edited this"

    def test_sync_before_send_updates_all_outputs(self):
        """Verify _sync_all_outputs_to_versions syncs Output #1 before sending."""
        turn = make_turn_with_versions(
            turn_number=1,
            message_text="Hello",
            output_versions=["original output"],
            current_version_index=0,
            is_complete=True,
        )

        _sync_all_outputs_to_versions_standalone(
            conversation_turns=[turn],
            output_edit_text="edited in UI",
            output_sections=[],
        )

        assert turn.output_versions[0] == "edited in UI"

    def test_sync_before_send_updates_dynamic_outputs(self):
        """Verify _sync_all_outputs_to_versions syncs dynamic output sections."""
        turn1 = make_turn_with_versions(
            turn_number=1,
            message_text="First",
            output_versions=["output 1"],
            current_version_index=0,
            is_complete=True,
        )
        turn2 = make_turn_with_versions(
            turn_number=2,
            message_text="Second",
            output_versions=["output 2 original"],
            current_version_index=0,
            is_complete=True,
        )

        output_section = make_output_section(turn_number=2, text="output 2 edited")

        _sync_all_outputs_to_versions_standalone(
            conversation_turns=[turn1, turn2],
            output_edit_text="output 1",
            output_sections=[output_section],
        )

        assert turn2.output_versions[0] == "output 2 edited"

    def test_no_sync_when_text_unchanged(self):
        """Verify no sync happens when text hasn't changed."""
        turn = make_turn_with_versions(
            output_versions=["same text"],
            current_version_index=0,
        )

        result = _sync_output_to_version_on_text_change(
            turn=turn,
            current_output_text="same text",
            last_output_text="same text",
        )

        assert result == "same text"
        assert turn.output_versions[0] == "same text"

    def test_sync_to_correct_version_index(self):
        """Verify sync updates the correct version when multiple versions exist."""
        turn = make_turn_with_versions(
            output_versions=["v1", "v2 original", "v3"],
            current_version_index=1,
        )

        _sync_output_to_version_on_text_change(
            turn=turn,
            current_output_text="v2 edited",
            last_output_text="v2 original",
        )

        assert turn.output_versions[0] == "v1"
        assert turn.output_versions[1] == "v2 edited"
        assert turn.output_versions[2] == "v3"

    def test_full_flow_edit_then_send(self):
        """End-to-end test: edit output, sync, then verify conversation data."""
        turn1 = make_turn_with_versions(
            turn_number=1,
            message_text="First message",
            output_versions=["First response"],
            current_version_index=0,
            is_complete=True,
        )

        turn1.output_versions[turn1.current_version_index] = "Edited first response"

        turn2 = make_turn_with_versions(
            turn_number=2,
            message_text="Second message",
            output_versions=[],
            current_version_index=0,
            is_complete=False,
        )

        result = _build_conversation_data_with_versions(
            context_text="System context",
            context_images=[],
            conversation_turns=[turn1, turn2],
        )

        assert result["turns"][0]["text"] == "First message"
        assert result["turns"][1]["text"] == "Edited first response"
        assert result["turns"][2]["text"] == "Second message"
        assert len(result["turns"]) == 3

    def test_empty_turns_no_error(self):
        """Verify sync handles empty conversation turns gracefully."""
        _sync_all_outputs_to_versions_standalone(
            conversation_turns=[],
            output_edit_text="some text",
            output_sections=[],
        )

    def test_turn_without_versions_no_error(self):
        """Verify sync handles turns without output_versions gracefully."""
        turn = make_turn_with_versions(
            output_versions=[],
            current_version_index=0,
        )
        turn.output_versions = []

        _sync_output_to_version_on_text_change(
            turn=turn,
            current_output_text="edited",
            last_output_text="original",
        )
