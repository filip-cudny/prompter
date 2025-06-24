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
        load_dotenv(env_file)
    else:
        load_dotenv()

    api_key = os.getenv("API_KEY")
    base_url = os.getenv("BASE_URL")

    if not api_key:
        raise ConfigurationError("API_KEY environment variable is required")

    if not base_url:
        raise ConfigurationError("BASE_URL environment variable is required")

    config = AppConfig(
        api_key=api_key,
        base_url=base_url,
        openai_api_key=os.getenv("LOCAL_OPENAI_API_KEY"),
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

    # Validate hotkey format
    from .system import validate_hotkey_format

    if not validate_hotkey_format(config.hotkey):
        raise ConfigurationError(f"Invalid hotkey format: {config.hotkey}")


def get_config_template() -> str:
    """Get a template .env file content."""
    return """# Prompt Store Configuration

# Required settings
API_KEY=your_api_key_here
BASE_URL=https://your-api-server.com

# Optional settings for speech-to-text
OPENAI_API_KEY=your_openai_api_key_here

# Optional settings
HOTKEY=shift+f1
MAX_HISTORY_ENTRIES=10
AUTO_REFRESH_INTERVAL=300
ENABLE_NOTIFICATIONS=true
CLIPBOARD_TIMEOUT=5.0
MENU_POSITION_OFFSET=0,0
DEBUG_MODE=false
"""


def create_default_env_file(path: str = ".env") -> None:
    """Create a default .env file if it doesn't exist."""
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(get_config_template())


def get_env_file_path() -> str:
    """Get the path to the .env file."""
    # Look for .env in current directory first
    if os.path.exists(".env"):
        return ".env"

    # Look in user's home directory
    home_env = os.path.expanduser("~/.prompt-store.env")
    if os.path.exists(home_env):
        return home_env

    # Default to current directory
    return ".env"
