"""Execution handler for PromptExecuteDialog."""

import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCursor

from core.models import ExecutionResult, MenuItem
from modules.gui.icons import create_icon
from modules.gui.prompt_execute_dialog.data import OutputVersionState
from modules.gui.shared.dialog_styles import get_text_edit_content_height

if TYPE_CHECKING:
    from modules.gui.prompt_execute_dialog.dialog import PromptExecuteDialog


class ExecutionHandler:
    """Handles prompt execution, streaming, and result processing.

    Manages the execution lifecycle including:
    - Signal connections to prompt store service
    - Streaming chunk processing with throttling
    - Execution result handling
    - Button state management (send/stop toggle)
    - Global execution tracking for cross-dialog awareness
    """

    def __init__(self, dialog: "PromptExecuteDialog"):
        self.dialog = dialog

        # Execution state
        self._current_execution_id: str | None = None
        self._waiting_for_result = False
        self._stop_button_active: str | None = None  # "alt" or "ctrl"

        # Streaming state
        self._is_streaming = False
        self._streaming_accumulated = ""
        self._last_ui_update_time = 0

        # Global execution tracking
        self._disable_for_global_execution = False

        # Signal connection tracking
        self._execution_signal_connected = False
        self._streaming_signal_connected = False
        self._global_execution_signal_connected = False

        # Streaming throttle timer (60fps max)
        self._streaming_throttle_timer = QTimer()
        self._streaming_throttle_timer.setSingleShot(True)
        self._streaming_throttle_timer.setInterval(16)
        self._streaming_throttle_timer.timeout.connect(self._flush_streaming_update)

    @property
    def is_waiting(self) -> bool:
        """Check if waiting for execution result."""
        return self._waiting_for_result

    @property
    def is_streaming(self) -> bool:
        """Check if currently streaming."""
        return self._is_streaming

    @property
    def current_execution_id(self) -> str | None:
        """Get current execution ID."""
        return self._current_execution_id

    @property
    def is_disabled_for_global(self) -> bool:
        """Check if disabled due to global execution."""
        return self._disable_for_global_execution

    def _get_prompt_store_service(self):
        """Get the prompt store service."""
        return self.dialog._prompt_store_service

    # --- Signal Management ---

    def connect_execution_signal(self):
        """Connect to execution completed signal."""
        if self._execution_signal_connected:
            return
        service = self._get_prompt_store_service()
        if service and hasattr(service, "_menu_coordinator"):
            try:
                service._menu_coordinator.execution_completed.connect(self.on_execution_result)
                self._execution_signal_connected = True
            except Exception:
                pass

    def disconnect_execution_signal(self):
        """Disconnect from execution completed signal."""
        if not self._execution_signal_connected:
            return
        service = self._get_prompt_store_service()
        if service and hasattr(service, "_menu_coordinator"):
            try:
                service._menu_coordinator.execution_completed.disconnect(self.on_execution_result)
            except Exception:
                pass
        self._execution_signal_connected = False

    def connect_streaming_signal(self):
        """Connect to streaming chunk signal for live updates."""
        if self._streaming_signal_connected:
            return
        service = self._get_prompt_store_service()
        if service and hasattr(service, "_menu_coordinator"):
            try:
                service._menu_coordinator.streaming_chunk.connect(self.on_streaming_chunk)
                self._streaming_signal_connected = True
            except Exception:
                pass

    def disconnect_streaming_signal(self):
        """Disconnect from streaming chunk signal."""
        if not self._streaming_signal_connected:
            return
        service = self._get_prompt_store_service()
        if service and hasattr(service, "_menu_coordinator"):
            try:
                service._menu_coordinator.streaming_chunk.disconnect(self.on_streaming_chunk)
            except Exception:
                pass
        self._streaming_signal_connected = False

    def connect_global_execution_signals(self):
        """Connect to global execution state signals for cross-dialog awareness."""
        if self._global_execution_signal_connected:
            return
        service = self._get_prompt_store_service()
        if service and hasattr(service, "_menu_coordinator"):
            try:
                service._menu_coordinator.execution_started.connect(self.on_global_execution_started)
                service._menu_coordinator.execution_completed.connect(self.on_global_execution_completed)
                self._global_execution_signal_connected = True

                # Check if an execution is already running when dialog opens
                if service.is_executing():
                    self._disable_for_global_execution = True
                    self.dialog._update_send_buttons_state()
            except Exception:
                pass

    def disconnect_global_execution_signals(self):
        """Disconnect from global execution state signals."""
        if not self._global_execution_signal_connected:
            return
        service = self._get_prompt_store_service()
        if service and hasattr(service, "_menu_coordinator"):
            try:
                service._menu_coordinator.execution_started.disconnect(self.on_global_execution_started)
            except Exception:
                pass
            try:
                service._menu_coordinator.execution_completed.disconnect(self.on_global_execution_completed)
            except Exception:
                pass
        self._global_execution_signal_connected = False

    def disconnect_all_signals(self):
        """Disconnect all signals."""
        self.disconnect_execution_signal()
        self.disconnect_streaming_signal()
        self.disconnect_global_execution_signals()

    # --- Global Execution Tracking ---

    def on_global_execution_started(self, execution_id: str):
        """Handle any execution starting globally."""
        # If this dialog is NOT the one executing, disable its buttons
        if execution_id != self._current_execution_id:
            self._disable_for_global_execution = True
            self.dialog._update_send_buttons_state()

    def on_global_execution_completed(self, result: ExecutionResult, execution_id: str):
        """Handle any execution completing globally."""
        # Check if any execution is still running
        service = self._get_prompt_store_service()
        if service and not service.is_executing():
            self._disable_for_global_execution = False
            self.dialog._update_send_buttons_state()

    # --- Streaming ---

    def on_streaming_chunk(self, chunk: str, accumulated: str, is_final: bool, execution_id: str = ""):
        """Handle streaming chunk with adaptive throttling."""
        if not self._waiting_for_result:
            return

        # Filter by execution_id - only process chunks for this dialog's execution
        if execution_id and self._current_execution_id and execution_id != self._current_execution_id:
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
        output_edit = self._get_current_output_edit()

        # Update text without triggering undo stack
        output_edit.blockSignals(True)
        output_edit.setPlainText(self._streaming_accumulated)
        cursor = output_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        output_edit.setTextCursor(cursor)
        output_edit.blockSignals(False)

    def _get_current_output_edit(self):
        """Get the current output text edit based on turn number."""
        if self.dialog._current_turn_number == 1 or not self.dialog._output_sections:
            return self.dialog.output_edit
        return self.dialog._output_sections[-1].text_edit

    # --- Execution ---

    def execute_with_message(
        self,
        message: str,
        keep_open: bool = False,
        regenerate: bool = False,
    ):
        """Execute the prompt with conversation history.

        Uses working context (images + text) from dialog, NOT from persistent storage.
        Context is sent with the prompt but NOT saved to context_manager.

        Args:
            message: The message to use as input (ignored if dynamic sections exist)
            keep_open: If True, keep dialog open and show result
            regenerate: If True, reuse existing output section instead of creating new one
        """
        dialog = self.dialog

        # Get current input from reply section if exists, otherwise original input
        if dialog._dynamic_sections:
            section = dialog._dynamic_sections[-1]
            msg_text = section.text_edit.toPlainText()
            msg_images = list(section.turn_images)
        else:
            msg_text = message
            msg_images = list(dialog._message_images)

        # Validate message has content
        if not msg_text.strip() and not msg_images:
            return

        # Get the prompt store service
        service = self._get_prompt_store_service()
        if not service:
            if keep_open:
                dialog._expand_output_section()
                dialog.output_edit.setPlainText("Error: Prompt service not available")
            return

        # Record turn in conversation history
        if dialog._current_turn_number == 0:
            dialog._current_turn_number = 1

        from modules.gui.prompt_execute_dialog.data import ConversationTurn

        turn = ConversationTurn(
            turn_number=dialog._current_turn_number,
            message_text=msg_text,
            message_images=msg_images,
        )

        # Restore version history for regeneration
        if hasattr(dialog, "_pending_version_history"):
            turn.output_versions = dialog._pending_version_history
            delattr(dialog, "_pending_version_history")
        if hasattr(dialog, "_pending_version_undo_states"):
            turn.version_undo_states = dialog._pending_version_undo_states
            delattr(dialog, "_pending_version_undo_states")
        if hasattr(dialog, "_pending_version_index"):
            turn.current_version_index = dialog._pending_version_index
            delattr(dialog, "_pending_version_index")

        dialog._conversation_turns.append(turn)

        # Build conversation data for API
        conv_data = self._build_conversation_data()

        # Enable streaming for "Send & Show" mode
        if keep_open:
            conv_data["use_streaming"] = True

        # For backward compatibility, also build full_message for single-turn case
        working_context_text = dialog.context_text_edit.toPlainText().strip()
        full_message = msg_text
        if len(dialog._conversation_turns) == 1 and working_context_text:
            full_message = f"<context>\n{working_context_text}\n</context>\n\n{msg_text}"

        # Create a modified menu item with conversation data
        modified_item = MenuItem(
            id=dialog.menu_item.id,
            label=dialog.menu_item.label,
            item_type=dialog.menu_item.item_type,
            action=dialog.menu_item.action,
            data={
                **(dialog.menu_item.data or {}),
                "custom_context": full_message,
                "conversation_data": conv_data,
                "skip_clipboard_copy": keep_open,
            },
            enabled=dialog.menu_item.enabled,
        )

        if keep_open:
            # Connect to receive result and streaming chunks
            self._waiting_for_result = True
            self.connect_execution_signal()
            self.connect_streaming_signal()

            status_text = "Regenerating..." if regenerate else "Executing..."

            # Create output section for this turn
            self._setup_output_section_for_execution(regenerate, status_text)

            # Transform button to stop mode and disable the other button
            self._transform_button_to_stop(is_alt_enter=True)
            dialog.send_copy_btn.setEnabled(False)

        # Execute using the prompt execution handler and capture execution_id
        for handler in service.execution_service.handlers:
            if handler.can_handle(modified_item):
                if hasattr(handler, "async_manager"):
                    # Always use async execution so it's cancellable via context menu
                    execution_id = handler.async_manager.execute_prompt_async(modified_item, full_message)

                    if keep_open:
                        # Stay open and track execution for result display
                        self._current_execution_id = execution_id
                    else:
                        # Close dialog immediately - execution continues in background
                        # Cancellable via context menu like normal context menu executions
                        dialog.accept()
                else:
                    # Fallback for handlers without async_manager
                    handler.execute(modified_item, full_message)
                    if not keep_open:
                        dialog.accept()
                return

        # Fallback: use execution callback
        if dialog.execution_callback:
            if dialog.menu_item.data:
                dialog.menu_item.data["custom_context"] = full_message
            dialog.execution_callback(dialog.menu_item, False)
            if not keep_open:
                dialog.accept()

    def _setup_output_section_for_execution(self, regenerate: bool, status_text: str):
        """Set up output section before execution starts."""
        dialog = self.dialog

        if dialog._current_turn_number == 1:
            # First turn uses existing output section
            dialog._expand_output_section()
            dialog.output_edit.setPlainText(status_text)
            # Set expanded mode and update height after text is set
            dialog.output_header.set_wrap_state(False)
            content_height = get_text_edit_content_height(dialog.output_edit)
            dialog.output_edit.setMinimumHeight(content_height)
        elif regenerate and dialog._output_sections:
            # Regenerating - reuse existing output section
            output_section = dialog._output_sections[-1]
            output_section.text_edit.blockSignals(True)
            output_section.text_edit.setPlainText(status_text)
            output_section.text_edit.blockSignals(False)
            # Set expanded mode
            output_section.header.set_wrap_state(False)
            content_height = get_text_edit_content_height(output_section.text_edit)
            output_section.text_edit.setMinimumHeight(content_height)
        else:
            # Subsequent turns create new output section
            output_section = dialog._create_dynamic_output_section(dialog._current_turn_number)
            dialog._output_sections.append(output_section)
            dialog.sections_layout.addWidget(output_section)
            output_section.text_edit.installEventFilter(dialog)
            output_section.text_edit.setPlainText(status_text)
            # Set expanded mode and update height after text is set
            output_section.header.set_wrap_state(False)
            content_height = get_text_edit_content_height(output_section.text_edit)
            output_section.text_edit.setMinimumHeight(content_height)
            dialog._renumber_sections()
            dialog._update_delete_button_visibility()
            dialog._scroll_to_bottom()

    def _build_conversation_data(self) -> dict:
        """Build conversation history for API."""
        dialog = self.dialog
        context_text = dialog.context_text_edit.toPlainText().strip()
        context_images = [
            {"data": img.data, "media_type": img.media_type or "image/png"} for img in dialog._current_images
        ]

        turns = []
        for i, turn in enumerate(dialog._conversation_turns):
            turn_data = {
                "role": "user",
                "text": turn.message_text,
                "images": [
                    {"data": img.data, "media_type": img.media_type or "image/png"} for img in turn.message_images
                ],
            }
            # First turn includes context
            if i == 0:
                turn_data["context_text"] = context_text
                turn_data["context_images"] = context_images

            turns.append(turn_data)

            if turn.is_complete and turn.output_versions:
                # Use the currently selected version
                selected_text = turn.output_versions[turn.current_version_index]
                turns.append({"role": "assistant", "text": selected_text})
            elif turn.is_complete and turn.output_text:
                # Fallback for backward compatibility
                turns.append({"role": "assistant", "text": turn.output_text})

        return {"turns": turns}

    def _clear_regeneration_flag(self) -> bool:
        """Clear regeneration flag and return whether it was set."""
        dialog = self.dialog
        is_regeneration = getattr(dialog, "_pending_is_regeneration", False)
        if hasattr(dialog, "_pending_is_regeneration"):
            delattr(dialog, "_pending_is_regeneration")
        return is_regeneration

    def _update_turn_with_output(self, output_text: str, is_regeneration: bool):
        """Update turn's version history and mark as complete."""
        dialog = self.dialog
        if not dialog._conversation_turns:
            return

        turn = dialog._conversation_turns[-1]
        turn.output_text = output_text
        turn.is_complete = True

        if not output_text:
            return

        if is_regeneration and turn.output_versions:
            turn.output_versions[turn.current_version_index] = output_text
            turn.version_undo_states[turn.current_version_index] = OutputVersionState(
                undo_stack=[], redo_stack=[], last_text=output_text
            )
        else:
            turn.output_versions.append(output_text)
            turn.current_version_index = len(turn.output_versions) - 1
            turn.version_undo_states.append(OutputVersionState(undo_stack=[], redo_stack=[], last_text=output_text))

    def _update_version_ui(self, output_text: str):
        """Update version display and sync undo state in UI."""
        dialog = self.dialog
        if not dialog._conversation_turns:
            return

        turn = dialog._conversation_turns[-1]

        if turn.turn_number == 1 or not dialog._output_sections:
            dialog.output_header.set_version_info(turn.current_version_index + 1, len(turn.output_versions))
            if turn.output_versions:
                dialog._output_undo_stack.clear()
                dialog._output_redo_stack.clear()
                dialog._last_output_text = output_text or ""
                dialog._update_undo_redo_buttons()
        else:
            section = dialog._output_sections[-1]
            section.header.set_version_info(turn.current_version_index + 1, len(turn.output_versions))
            if turn.output_versions:
                section.undo_stack.clear()
                section.redo_stack.clear()
                section.last_text = output_text or ""
                dialog._update_dynamic_section_buttons(section)

    def _finalize_execution_ui(self):
        """Show reply button and update send buttons after execution ends."""
        dialog = self.dialog
        dialog.reply_btn.setVisible(True)
        dialog.reply_btn.setIcon(create_icon("message-square-reply", "#f0f0f0", 16))
        dialog._update_send_buttons_state()

    def stop_execution(self):
        """Cancel this dialog's execution only."""
        if not self._current_execution_id:
            return

        execution_id_to_cancel = self._current_execution_id

        is_regeneration = self._clear_regeneration_flag()

        self._waiting_for_result = False
        self._current_execution_id = None
        self._disable_for_global_execution = False
        self._revert_button_to_send_state()

        output_edit = self._get_current_output_edit()
        current_text = output_edit.toPlainText()
        if current_text and current_text not in ("Executing...", "Regenerating..."):
            cancelled_text = current_text + "\n\n[cancelled]"
        else:
            cancelled_text = "[cancelled]"
        output_edit.setPlainText(cancelled_text)

        self._update_turn_with_output(cancelled_text, is_regeneration)
        self._update_version_ui(cancelled_text)
        self._finalize_execution_ui()

        service = self._get_prompt_store_service()
        if service:
            service.execution_service.cancel_execution(execution_id_to_cancel, silent=True)

    # --- Result Handling ---

    def on_execution_result(self, result: ExecutionResult, execution_id: str = ""):
        """Handle execution result for multi-turn conversation."""
        if not self._waiting_for_result:
            return

        if execution_id and self._current_execution_id and execution_id != self._current_execution_id:
            return

        self._waiting_for_result = False
        self._current_execution_id = None
        self.disconnect_execution_signal()
        self.disconnect_streaming_signal()
        self._revert_button_to_send_state()

        dialog = self.dialog
        is_regeneration = self._clear_regeneration_flag()
        is_streaming = result.metadata and result.metadata.get("streaming", False)

        output_text = result.content if result.success else None
        self._update_turn_with_output(output_text, is_regeneration)
        self._update_version_ui(output_text)
        self._finalize_execution_ui()

        output_edit = self._get_current_output_edit()

        if not is_streaming or not result.success:
            if result.success and result.content:
                output_edit.setPlainText(result.content)
            elif result.error:
                output_edit.setPlainText(f"Error: {result.error}")
            else:
                output_edit.setPlainText("No output received")

        if dialog._current_turn_number == 1 or not dialog._output_sections:
            if not dialog.output_header.is_wrapped():
                content_height = get_text_edit_content_height(dialog.output_edit)
                dialog.output_edit.setMinimumHeight(content_height)
        else:
            section = dialog._output_sections[-1]
            if not section.header.is_wrapped():
                content_height = get_text_edit_content_height(section.text_edit)
                section.text_edit.setMinimumHeight(content_height)

        dialog._scroll_to_bottom()

    # --- Button State Management ---

    def _transform_button_to_stop(self, is_alt_enter: bool):
        """Transform send button to stop button during execution."""
        dialog = self.dialog

        if is_alt_enter:
            dialog.send_show_btn.setIcon(create_icon("square", "#f0f0f0", 16))
            dialog.send_show_btn.setToolTip("Stop execution (Alt+Enter)")
            try:
                dialog.send_show_btn.clicked.disconnect()
            except TypeError:
                pass
            dialog.send_show_btn.clicked.connect(self._on_stop_button_clicked)
            dialog.send_show_btn.setEnabled(True)
            self._stop_button_active = "alt"
        else:
            dialog.send_copy_btn.setIcon(create_icon("square", "#f0f0f0", 16))
            dialog.send_copy_btn.setToolTip("Stop execution (Ctrl+Enter)")
            try:
                dialog.send_copy_btn.clicked.disconnect()
            except TypeError:
                pass
            dialog.send_copy_btn.clicked.connect(self._on_stop_button_clicked)
            dialog.send_copy_btn.setEnabled(True)
            self._stop_button_active = "ctrl"

    def _on_stop_button_clicked(self):
        """Handle stop button click."""
        self.stop_execution()

    def _revert_button_to_send_state(self):
        """Revert stop button back to send button."""
        dialog = self.dialog

        if self._stop_button_active == "alt":
            try:
                dialog.send_show_btn.clicked.disconnect()
            except TypeError:
                pass
            dialog.send_show_btn.clicked.connect(dialog._on_send_show)
            dialog.send_show_btn.setIcon(create_icon("send-horizontal", "#444444", 16))
            dialog.send_show_btn.setToolTip("Send & Show Result (Alt+Enter)")
        elif self._stop_button_active == "ctrl":
            try:
                dialog.send_copy_btn.clicked.disconnect()
            except TypeError:
                pass
            dialog.send_copy_btn.clicked.connect(dialog._on_send_copy)
            dialog.send_copy_btn.setIcon(create_icon("copy", "#444444", 16))
            dialog.send_copy_btn.setToolTip("Send & Copy to Clipboard (Ctrl+Enter)")
        self._stop_button_active = None
        dialog._update_send_buttons_state()

    def cleanup(self):
        """Clean up handler on dialog close."""
        self.disconnect_all_signals()
        if self._is_streaming:
            self._streaming_throttle_timer.stop()
            self._is_streaming = False
