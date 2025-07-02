"""Configuration management utilities."""

import os
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from pathlib import Path
from dotenv import load_dotenv

from core.exceptions import ConfigurationError
from .keymap import KeymapManager, load_keymaps_from_settings


@dataclass
class AppConfig:
    """Application configuration."""

    api_key: str
    base_url: str
    openai_api_key: Optional[str] = None
    menu_position_offset: tuple = (0, 0)
    keymap_manager: Optional[KeymapManager] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        config_dict = asdict(self)
        config_dict.pop('keymap_manager', None)
        return config_dict

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """Create config from dictionary."""
        data_copy = data.copy()
        data_copy.pop('keymap_manager', None)
        return cls(**data_copy)


def load_config(env_file: Optional[str] = None, settings_file: Optional[str] = None) -> AppConfig:
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
    )
    
    # Parse menu position offset
    offset_str = os.getenv("MENU_POSITION_OFFSET", "0,0")
    try:
        x, y = map(int, offset_str.split(","))
        config.menu_position_offset = (x, y)
    except ValueError:
        config.menu_position_offset = (0, 0)

    # Load keymap configuration - use default settings file if not specified
    keymap_settings_file = settings_file or "settings/settings.json"
    if Path(keymap_settings_file).exists():
        try:
            config.keymap_manager = load_keymaps_from_settings(Path(keymap_settings_file))
        except Exception as e:
            raise ConfigurationError(f"Failed to load keymap configuration: {e}")

    return config


def validate_config(config: AppConfig) -> None:
    """Validate configuration values."""
    if not config.api_key.strip():
        raise ConfigurationError("API key cannot be empty")

    if not config.base_url.strip():
        raise ConfigurationError("Base URL cannot be empty")

    if not config.base_url.startswith(("http://", "https://")):
        raise ConfigurationError("Base URL must start with http:// or https://")


def load_settings_file(settings_path: Path) -> Dict[str, Any]:
    """Load settings from JSON file."""
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise ConfigurationError(f"Settings file not found: {settings_path}")
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON in settings file: {e}")
    except Exception as e:
        raise ConfigurationError(f"Error loading settings file: {e}")
