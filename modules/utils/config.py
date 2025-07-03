"""Configuration management utilities."""

import os
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from dotenv import load_dotenv

from core.exceptions import ConfigurationError
from .keymap import KeymapManager, load_keymaps_from_settings


@dataclass
class AppConfig:
    """Application configuration."""

    menu_position_offset: tuple = (0, 0)
    keymap_manager: Optional[KeymapManager] = None
    models: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        config_dict = asdict(self)
        config_dict.pop("keymap_manager", None)
        return config_dict

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """Create config from dictionary."""
        data_copy = data.copy()
        data_copy.pop("keymap_manager", None)
        return cls(**data_copy)


def load_config(
    env_file: Optional[str] = None, settings_file: Optional[str] = None
) -> AppConfig:
    """Load configuration from environment variables and .env file."""
    if env_file:
        load_dotenv(env_file, override=True)
    else:
        load_dotenv(override=True)

    config = AppConfig()

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
            config.keymap_manager = load_keymaps_from_settings(
                Path(keymap_settings_file)
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to load keymap configuration: {e}")

        try:
            # Load models configuration
            settings_data = load_settings_file(Path(keymap_settings_file))
            config.models = settings_data.get("models", {})
        except Exception as e:
            raise ConfigurationError(f"Failed to load models configuration: {e}")

    validate_config(config)
    return config


def validate_config(config: AppConfig) -> None:
    """Validate configuration values."""

    if config.models is None:
        raise ConfigurationError("Models configuration is required")

    if "default" not in config.models:
        raise ConfigurationError("Default model must be configured")

    if not config.models["default"]:
        raise ConfigurationError("Default model configuration cannot be empty")

    # Validate all model entries
    for model_name, model_list in config.models.items():
        if not isinstance(model_list, list):
            raise ConfigurationError(f"Model '{model_name}' must be a list")

        if not model_list:
            raise ConfigurationError(f"Model '{model_name}' list cannot be empty")

        for i, model_config in enumerate(model_list):
            if not isinstance(model_config, dict):
                raise ConfigurationError(
                    f"Model '{model_name}[{i}]' must be a dictionary"
                )

            # Required fields
            required_fields = ["model", "display_name", "api_key_env"]
            for field in required_fields:
                if field not in model_config:
                    raise ConfigurationError(
                        f"Model '{model_name}[{i}]' missing required field: {field}"
                    )

                if not model_config[field]:
                    raise ConfigurationError(
                        f"Model '{model_name}[{i}]' field '{field}' cannot be empty"
                    )

            # Validate temperature if present (optional field)
            if (
                "temperature" in model_config
                and model_config["temperature"] is not None
            ):
                try:
                    temp = float(model_config["temperature"])
                    if temp < 0 or temp > 2:
                        raise ConfigurationError(
                            f"Model '{model_name}[{i}]' temperature must be between 0 and 2"
                        )
                except (ValueError, TypeError):
                    raise ConfigurationError(
                        f"Model '{model_name}[{i}]' temperature must be a number"
                    )

            # Validate base_url if present (optional field)
            if "base_url" in model_config and model_config["base_url"]:
                if not model_config["base_url"].startswith(("http://", "https://")):
                    raise ConfigurationError(
                        f"Model '{model_name}[{i}]' base_url must start with http:// or https://"
                    )


def load_settings_file(settings_path: Path) -> Dict[str, Any]:
    """Load settings from JSON file."""
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise ConfigurationError(f"Settings file not found: {settings_path}")
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON in settings file: {e}")
    except Exception as e:
        raise ConfigurationError(f"Error loading settings file: {e}")
