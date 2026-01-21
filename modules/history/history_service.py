import logging
import time
from collections import deque
from collections.abc import Callable

from core.models import (
    HistoryEntry,
    HistoryEntryType,
)

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
        """Get all history entries, most recent first."""
        return list(reversed(self._history))

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
