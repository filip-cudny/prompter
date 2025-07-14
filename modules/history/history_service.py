import time
import logging
from collections import deque
from typing import List, Optional

from core.models import (
    HistoryEntry,
    HistoryEntryType,
)

logger = logging.getLogger(__name__)


class HistoryService:
    """Service for tracking execution history."""

    def __init__(self, max_entries: int = 10):
        self.max_entries = max_entries
        self._history: deque = deque(maxlen=max_entries)

    def add_entry(
        self,
        input_content: str,
        entry_type: HistoryEntryType,
        output_content: Optional[str] = None,
        prompt_id: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
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
        )
        self._history.append(entry)

    def get_history(self) -> List[HistoryEntry]:
        """Get all history entries, most recent first."""
        return list(reversed(self._history))

    def clear_history(self) -> None:
        """Clear all history entries."""
        self._history.clear()

    def get_entry_by_id(self, entry_id: str) -> Optional[HistoryEntry]:
        """Get a specific history entry by ID."""
        for entry in self._history:
            if entry.id == entry_id:
                return entry
        return None

    def get_last_item_by_type(
        self, entry_type: HistoryEntryType
    ) -> Optional[HistoryEntry]:
        """Get the most recent history entry of the specified type."""
        for entry in reversed(self._history):
            if entry.entry_type == entry_type:
                return entry
        return None
