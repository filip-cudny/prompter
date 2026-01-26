"""Data models and types for the Promptheus application."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class MenuItemType(Enum):
    """Types of menu items."""

    PROMPT = "prompt"
    PRESET = "preset"
    HISTORY = "history"
    SYSTEM = "system"
    SPEECH = "speech"
    CONTEXT = "context"
    LAST_INTERACTION = "last_interaction"
    SETTINGS_SECTION = "settings_section"


class HistoryEntryType(Enum):
    """Types of history entries."""

    SPEECH = "speech"
    TEXT = "text"


class ErrorCode(Enum):
    """Error codes for execution results."""

    NO_ACTIVE_PROMPT = "no_active_prompt"
    EXECUTION_IN_PROGRESS = "execution_in_progress"
    CLIPBOARD_ERROR = "clipboard_error"
    API_ERROR = "api_error"
    VALIDATION_ERROR = "validation_error"
    TIMEOUT_ERROR = "timeout_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class MenuItem:
    """Represents a menu item in the context menu."""

    id: str
    label: str
    item_type: MenuItemType
    action: Callable[[], None]
    data: dict[str, Any] | None = None
    enabled: bool = True
    separator_after: bool = False
    style: str | None = None
    tooltip: str | None = None
    submenu_items: list[MenuItem] | None = None
    icon: str | None = None  # Icon name from icons.py (e.g., "mic", "copy")


@dataclass
class PromptData:
    """Represents a prompt with its metadata."""

    id: str
    name: str
    content: str
    model: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Result of executing a prompt."""

    success: bool
    content: str | None = None
    error: str | None = None
    error_code: ErrorCode | None = None
    execution_time: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_id: str | None = None


@dataclass
class SerializedConversationTurn:
    """Serializable conversation turn for storage."""

    turn_number: int
    message_text: str
    message_image_paths: list[str] = field(default_factory=list)
    output_text: str | None = None
    is_complete: bool = False
    output_versions: list[str] = field(default_factory=list)
    current_version_index: int = 0


@dataclass
class ConversationHistoryData:
    """Complete conversation data for history storage."""

    context_text: str
    context_image_paths: list[str] = field(default_factory=list)
    turns: list[SerializedConversationTurn] = field(default_factory=list)
    prompt_id: str | None = None
    prompt_name: str | None = None


@dataclass
class HistoryEntry:
    """Represents a history entry for input/output tracking."""

    id: str
    timestamp: str
    input_content: str
    entry_type: HistoryEntryType
    output_content: str | None = None
    prompt_id: str | None = None
    success: bool = True
    error: str | None = None
    is_conversation: bool = False
    prompt_name: str | None = None
    conversation_data: ConversationHistoryData | None = None


@dataclass
class AppConfig:
    """Application configuration."""

    api_key: str
    base_url: str
    max_history_entries: int = 10
    clipboard_timeout: float = 5.0
    menu_position_offset: tuple = (0, 0)


@dataclass
class ModelConfig:
    """Configuration for a model."""

    model: str
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None


@dataclass
class ProviderConfig:
    """Configuration for a model provider."""

    name: str
    models: list[ModelConfig] = field(default_factory=list)
    api_key: str | None = None
    base_url: str | None = None


@dataclass
class MessageConfig:
    """Configuration for a message in a prompt."""

    role: str
    content: str | None = None
    file: str | None = None


@dataclass
class PromptConfig:
    """Configuration for a prompt."""

    id: str
    name: str
    messages: list[MessageConfig] = field(default_factory=list)
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    model: str | None = None


@dataclass
class SettingsConfig:
    """Main settings configuration."""

    models: list[dict[str, Any]] = field(default_factory=list)
    prompts: list[PromptConfig] = field(default_factory=list)
    providers: list[ProviderConfig] = field(default_factory=list)
    settings_path: str | None = None


class ExecutionHandler(Protocol):
    """Protocol for execution handlers."""

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can handle the given menu item."""
        ...

    def execute(self, item: MenuItem, input_content: str | None = None) -> ExecutionResult:
        """Execute the menu item with optional input content."""
        ...
