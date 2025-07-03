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
    speech_to_text_model: Optional[Dict[str, Any]] = None
    default_model: Optional[str] = None

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
            # Load models and speech_to_text_model configuration
            settings_data = load_settings_file(Path(keymap_settings_file))
            config.models = settings_data.get("models", {})
            config.speech_to_text_model = settings_data.get("speech_to_text_model")
            
            # Set default_model to first model key
            if config.models:
                config.default_model = next(iter(config.models.keys()))
            
            # Load API keys from environment variables
            _load_api_keys(config.models)
            if config.speech_to_text_model:
                _load_api_key_for_model(config.speech_to_text_model, "speech_to_text_model")
        except Exception as e:
            raise ConfigurationError(f"Failed to load models configuration: {e}")

    validate_config(config)
    return config


def validate_config(config: AppConfig) -> None:
    """Validate configuration values."""

    if config.models is None:
        raise ConfigurationError("Models configuration is required")

    if not config.models:
        raise ConfigurationError("At least one model must be configured")

    # Validate all model entries
    for model_name, model_config in config.models.items():
        if not isinstance(model_config, dict):
            raise ConfigurationError(f"Model '{model_name}' must be a dictionary")

        # Required fields
        required_fields = ["model", "display_name", "api_key_env"]
        for field in required_fields:
            if field not in model_config:
                raise ConfigurationError(
                    f"Model '{model_name}' missing required field: {field}"
                )

            if not model_config[field]:
                raise ConfigurationError(
                    f"Model '{model_name}' field '{field}' cannot be empty"
                )

        # Validate temperature if present (optional field)
        if "temperature" in model_config and model_config["temperature"] is not None:
            try:
                temp = float(model_config["temperature"])
                if temp < 0 or temp > 2:
                    raise ConfigurationError(
                        f"Model '{model_name}' temperature must be between 0 and 2"
                    )
            except (ValueError, TypeError):
                raise ConfigurationError(
                    f"Model '{model_name}' temperature must be a number"
                )

        # Validate base_url if present (optional field)
        if "base_url" in model_config and model_config["base_url"]:
            if not model_config["base_url"].startswith(("http://", "https://")):
                raise ConfigurationError(
                    f"Model '{model_name}' base_url must start with http:// or https://"
                )

    # Validate speech_to_text_model if present
    if config.speech_to_text_model is not None:
        if not isinstance(config.speech_to_text_model, dict):
            raise ConfigurationError("speech_to_text_model must be a dictionary")

        # Required fields for speech_to_text_model
        required_fields = ["model", "display_name", "api_key_env"]
        for field in required_fields:
            if field not in config.speech_to_text_model:
                raise ConfigurationError(
                    f"speech_to_text_model missing required field: {field}"
                )

            if not config.speech_to_text_model[field]:
                raise ConfigurationError(
                    f"speech_to_text_model field '{field}' cannot be empty"
                )

        # Validate base_url if present (optional field)
        if (
            "base_url" in config.speech_to_text_model
            and config.speech_to_text_model["base_url"]
        ):
            if not config.speech_to_text_model["base_url"].startswith(
                ("http://", "https://")
            ):
                raise ConfigurationError(
                    "speech_to_text_model base_url must start with http:// or https://"
                )


def _load_api_keys(models: Dict[str, Any]) -> None:
    """Load API keys from environment variables for all models."""
    for model_name, model_config in models.items():
        _load_api_key_for_model(model_config, model_name)


def _load_api_key_for_model(model_config: Dict[str, Any], model_name: str) -> None:
    """Load API key from environment variable for a single model."""
    api_key_env = model_config.get("api_key_env")
    if api_key_env:
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise ConfigurationError(
                f"Environment variable '{api_key_env}' for model '{model_name}' is not set or empty"
            )
        model_config["api_key"] = api_key


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
