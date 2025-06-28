"""Configuration management utilities."""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

from core.exceptions import ConfigurationError


@dataclass
class AppConfig:
    """Application configuration."""

    api_key: str
    base_url: str
    openai_api_key: Optional[str] = None
    hotkey: str = "shift+f1"
    max_history_entries: int = 10
    enable_notifications: bool = True
    menu_position_offset: tuple = (0, 0)
    debug_mode: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """Create config from dictionary."""
        return cls(**data)


def load_config(env_file: Optional[str] = None) -> AppConfig:
    """Load configuration from environment variables and .env file."""
    if env_file:
        load_dotenv(env_file, override=True)
    else:
        load_dotenv(override=True)

    api_key = os.getenv("API_KEY")
    base_url = os.getenv("BASE_URL")

    if not api_key:
        raise ConfigurationError("API_KEY environment variable is required")

    if not base_url:
        raise ConfigurationError("BASE_URL environment variable is required")

    config = AppConfig(
        api_key=api_key,
        base_url=base_url,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        hotkey=os.getenv("HOTKEY", "shift+f1"),
        max_history_entries=int(os.getenv("MAX_HISTORY_ENTRIES", "10")),
        enable_notifications=os.getenv("ENABLE_NOTIFICATIONS", "true").lower()
        == "true",
        debug_mode=os.getenv("DEBUG_MODE", "false").lower() == "true",
    )
    # Parse menu position offset
    offset_str = os.getenv("MENU_POSITION_OFFSET", "0,0")
    try:
        x, y = map(int, offset_str.split(","))
        config.menu_position_offset = (x, y)
    except ValueError:
        config.menu_position_offset = (0, 0)

    return config


def validate_config(config: AppConfig) -> None:
    """Validate configuration values."""
    if not config.api_key.strip():
        raise ConfigurationError("API key cannot be empty")

    if not config.base_url.strip():
        raise ConfigurationError("Base URL cannot be empty")

    if not config.base_url.startswith(("http://", "https://")):
        raise ConfigurationError("Base URL must start with http:// or https://")

    if config.max_history_entries < 1:
        raise ConfigurationError("Max history entries must be at least 1")
