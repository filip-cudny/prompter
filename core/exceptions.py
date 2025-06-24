"""Custom exceptions for the prompt store application."""


class PromptStoreError(Exception):
    """Base exception for prompt store errors."""

    pass


class ExecutionError(PromptStoreError):
    """Raised when prompt or preset execution fails."""

    pass


class DataError(PromptStoreError):
    """Raised when data operations fail."""

    pass


class ClipboardError(PromptStoreError):
    """Raised when clipboard operations fail."""

    pass


class ConfigurationError(PromptStoreError):
    """Raised when configuration is invalid or missing."""

    pass


class ProviderError(PromptStoreError):
    """Raised when a provider operation fails."""

    pass


class MenuError(PromptStoreError):
    """Raised when menu operations fail."""

    pass


class HotkeyError(PromptStoreError):
    """Raised when hotkey operations fail."""

    pass
