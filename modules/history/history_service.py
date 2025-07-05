
import time
from collections import deque
from typing import  List, Optional

from core.models import (
    HistoryEntry,
)
class HistoryService:
    """Service for tracking execution history."""

    def __init__(self, max_entries: int = 10):
        self.max_entries = max_entries
        self._history: deque = deque(maxlen=max_entries)

    def add_entry(
        self,
        input_content: str,
        output_content: Optional[str] = None,
        prompt_id: Optional[str] = None,
        preset_id: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Add a new history entry."""
        entry = HistoryEntry(
            id=str(int(time.time() * 1000)),  # millisecond timestamp as ID
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            input_content=input_content,
            output_content=output_content,
            prompt_id=prompt_id,
            preset_id=preset_id,
            success=success,
            error=error,
        )
        self._history.append(entry)

    def get_history(self) -> List[HistoryEntry]:
        """Get all history entries, most recent first."""
        return list(reversed(self._history))

    def get_last_input(self) -> Optional[str]:
        """Get the last input content."""
        if self._history:
            return self._history[-1].input_content
        return None

    def get_last_output(self) -> Optional[str]:
        """Get the last successful output content."""
        for entry in reversed(self._history):
            if entry.success and entry.output_content:
                return entry.output_content
        return None

    def clear_history(self) -> None:
        """Clear all history entries."""
        self._history.clear()

    def get_entry_by_id(self, entry_id: str) -> Optional[HistoryEntry]:
        """Get a specific history entry by ID."""
        for entry in self._history:
            if entry.id == entry_id:
                return entry
        return None
