"""Generic undo/redo manager for MessageShareDialog sections."""

from typing import Generic, TypeVar, List, Optional, Callable

StateT = TypeVar('StateT')


class UndoRedoManager(Generic[StateT]):
    """Generic undo/redo stack manager.

    Manages undo/redo stacks for any state type. Can be used for text states,
    section states with images, or any other serializable state.
    """

    def __init__(self):
        self.undo_stack: List[StateT] = []
        self.redo_stack: List[StateT] = []
        self.last_state: Optional[StateT] = None

    def save_state(self, state: StateT) -> None:
        """Save state to undo stack and clear redo stack."""
        self.undo_stack.append(state)
        self.redo_stack.clear()

    def save_if_changed(
        self,
        current: StateT,
        last: StateT,
        comparator: Optional[Callable[[StateT, StateT], bool]] = None
    ) -> bool:
        """Save state only if it has changed from last state.

        Args:
            current: Current state to potentially save
            last: Last saved state to compare against
            comparator: Optional function to compare states (default uses !=)

        Returns:
            True if state was saved, False otherwise
        """
        if comparator:
            has_changed = not comparator(current, last)
        else:
            has_changed = current != last

        if has_changed:
            self.save_state(last)
            return True
        return False

    def undo(self, get_current: Callable[[], StateT]) -> Optional[StateT]:
        """Undo to previous state.

        Args:
            get_current: Function to get current state (will be saved to redo stack)

        Returns:
            Previous state to restore, or None if nothing to undo
        """
        if not self.undo_stack:
            return None
        self.redo_stack.append(get_current())
        return self.undo_stack.pop()

    def redo(self, get_current: Callable[[], StateT]) -> Optional[StateT]:
        """Redo to next state.

        Args:
            get_current: Function to get current state (will be saved to undo stack)

        Returns:
            Next state to restore, or None if nothing to redo
        """
        if not self.redo_stack:
            return None
        self.undo_stack.append(get_current())
        return self.redo_stack.pop()

    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self.redo_stack) > 0

    def clear(self) -> None:
        """Clear both undo and redo stacks."""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.last_state = None

    def get_stack_sizes(self) -> tuple:
        """Get sizes of undo and redo stacks.

        Returns:
            Tuple of (undo_size, redo_size)
        """
        return len(self.undo_stack), len(self.redo_stack)
