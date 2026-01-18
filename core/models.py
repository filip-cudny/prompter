"""Data models and types for the Prompter application."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Protocol
from enum import Enum


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
    data: Optional[Dict[str, Any]] = None
    enabled: bool = True
    separator_after: bool = False
    style: Optional[str] = None
    tooltip: Optional[str] = None
    submenu_items: Optional[List[MenuItem]] = None
    icon: Optional[str] = None  # Icon name from icons.py (e.g., "mic", "copy")


@dataclass
class PromptData:
    """Represents a prompt with its metadata."""

    id: str
    name: str
    content: str
    model: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Result of executing a prompt."""

    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[ErrorCode] = None
    execution_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_id: Optional[str] = None


@dataclass
class HistoryEntry:
    """Represents a history entry for input/output tracking."""

    id: str
    timestamp: str
    input_content: str
    entry_type: HistoryEntryType
    output_content: Optional[str] = None
    prompt_id: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    is_conversation: bool = False


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
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None


@dataclass
class ProviderConfig:
    """Configuration for a model provider."""

    name: str
    models: List[ModelConfig] = field(default_factory=list)
    api_key: Optional[str] = None
    base_url: Optional[str] = None


@dataclass
class MessageConfig:
    """Configuration for a message in a prompt."""

    role: str
    content: Optional[str] = None
    file: Optional[str] = None


@dataclass
class PromptConfig:
    """Configuration for a prompt."""

    id: str
    name: str
    messages: List[MessageConfig] = field(default_factory=list)
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    model: Optional[str] = None


@dataclass
class SettingsConfig:
    """Main settings configuration."""

    models: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    prompts: List[PromptConfig] = field(default_factory=list)
    providers: List[ProviderConfig] = field(default_factory=list)
    settings_path: Optional[str] = None


class ExecutionHandler(Protocol):
    """Protocol for execution handlers."""

    def can_handle(self, item: MenuItem) -> bool:
        """Check if this handler can handle the given menu item."""
        ...

    def execute(
        self, item: MenuItem, input_content: Optional[str] = None
    ) -> ExecutionResult:
        """Execute the menu item with optional input content."""
        ...
