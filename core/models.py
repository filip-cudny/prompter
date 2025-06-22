"""Data models and types for the prompt store application."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from enum import Enum


class MenuItemType(Enum):
    """Types of menu items."""
    PROMPT = "prompt"
    PRESET = "preset"
    HISTORY = "history"
    SYSTEM = "system"


class ErrorCode(Enum):
    """Error codes for execution results."""
    NO_ACTIVE_PROMPT = "no_active_prompt"
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


@dataclass
class PromptData:
    """Represents a prompt with its metadata."""
    id: str
    name: str
    content: str
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PresetData:
    """Represents a preset configuration for a prompt."""
    id: str
    preset_name: str
    prompt_id: str
    temperature: Optional[float] = None
    model: Optional[str] = None
    context: Optional[str] = None
    placeholder_values: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Result of executing a prompt or preset."""
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[ErrorCode] = None
    execution_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HistoryEntry:
    """Represents a history entry for input/output tracking."""
    id: str
    timestamp: str
    input_content: str
    output_content: Optional[str] = None
    prompt_id: Optional[str] = None
    preset_id: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class AppConfig:
    """Application configuration."""
    api_key: str
    base_url: str
    hotkey: str = "shift+f1"
    max_history_entries: int = 10
    enable_notifications: bool = True
    clipboard_timeout: float = 5.0
    menu_position_offset: tuple = (0, 0)
    debug_mode: bool = False
