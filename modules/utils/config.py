"""Configuration management utilities."""

import os
import json
import json5
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from dotenv import load_dotenv
from .keymap import KeymapManager

from core.exceptions import ConfigurationError


def safe_load_json(file_path: Path) -> Dict[str, Any]:
    """Load JSON file with optional comment support."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        return json5.loads(content)

    except FileNotFoundError:
        raise ConfigurationError(f"Settings file not found: {file_path}")
    except (json.JSONDecodeError, ValueError) as e:
        raise ConfigurationError(f"Invalid JSON in settings file: {e}")
    except Exception as e:
        raise ConfigurationError(f"Error loading settings file: {e}")


@dataclass
class AppConfig:
    """Application configuration."""

    menu_position_offset: tuple = (0, 0)
    keymap_manager: Optional["KeymapManager"] = None
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


class ConfigService:
    """Singleton service for configuration management."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._config = None
            self._settings_data = None
            self._initialized = True

    def initialize(
        self, env_file: Optional[str] = None, settings_file: Optional[str] = None
    ):
        """Initialize the configuration service."""
        self._config = self._load_config(env_file, settings_file)
        return self._config

    def get_config(self) -> AppConfig:
        """Get the current configuration."""
        if self._config is None:
            raise ConfigurationError(
                "ConfigService not initialized. Call initialize() first."
            )
        return self._config

    def get_settings_data(self) -> Dict[str, Any]:
        """Get the raw settings data."""
        if self._settings_data is None:
            raise ConfigurationError(
                "ConfigService not initialized. Call initialize() first."
            )
        return self._settings_data

    def update_default_model(self, model_key: str) -> None:
        """Update the default model configuration."""
        if self._config is None:
            raise ConfigurationError(
                "ConfigService not initialized. Call initialize() first."
            )

        if model_key not in self._config.models:
            raise ConfigurationError(f"Model '{model_key}' not found in configuration")

        self._config.default_model = model_key

    def _load_config(
        self, env_file: Optional[str] = None, settings_file: Optional[str] = None
    ) -> AppConfig:
        """Load configuration from environment variables and settings file."""
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

        # Load settings file
        keymap_settings_file = settings_file or "settings/settings.json"
        if Path(keymap_settings_file).exists():
            try:
                self._settings_data = safe_load_json(Path(keymap_settings_file))

                # Load keymap configuration
                from .keymap import KeymapManager

                config.keymap_manager = KeymapManager(
                    self._settings_data.get("keymaps", [])
                )

                # Load models and speech_to_text_model configuration
                config.models = self._settings_data.get("models", {})
                config.speech_to_text_model = self._settings_data.get(
                    "speech_to_text_model"
                )

                # Set default_model to first model key
                config.default_model = self._settings_data.get("default_model")
                if config.models and not config.default_model:
                    config.default_model = next(iter(config.models.keys()))

                # Load API keys from environment variables
                _load_api_keys(config.models)
                if config.speech_to_text_model:
                    _load_api_key_for_model(
                        config.speech_to_text_model, "speech_to_text_model"
                    )

            except Exception as e:
                raise ConfigurationError(f"Failed to load configuration: {e}")
        else:
            raise ConfigurationError(f"Settings file not found: {keymap_settings_file}")

        validate_config(config)
        return config


def get_config_service(
    env_file: Optional[str] = None, settings_file: Optional[str] = None
) -> ConfigService:
    """Get initialized ConfigService singleton."""
    config_service = ConfigService()
    if config_service._config is None:
        config_service.initialize(env_file, settings_file)
    return config_service


def initialize_config(
    env_file: Optional[str] = None, settings_file: Optional[str] = None
) -> AppConfig:
    """Initialize configuration for the application.

    Usage example:
        # In your main application startup:
        from modules.utils.config import initialize_config
        config = initialize_config()

        # Then in other services:
        from modules.utils.config import ConfigService
        config_service = ConfigService()
        settings_data = config_service.get_settings_data()
        app_config = config_service.get_config()
    """
    config_service = get_config_service(env_file, settings_file)
    return config_service.get_config()


def load_config(
    env_file: Optional[str] = None, settings_file: Optional[str] = None
) -> AppConfig:
    """Load configuration from environment variables and .env file."""
    config_service = get_config_service(env_file, settings_file)
    return config_service.get_config()


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
        model_config["api_key"] = api_key


def load_settings_file(settings_path: Path) -> Dict[str, Any]:
    """Load settings from JSON file with optional comment support."""
    return safe_load_json(settings_path)


def _strip_json_comments(content: str) -> str:
    """Strip // comments from JSON content."""
    lines = content.split("\n")
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("//"):
            continue

        comment_pos = line.find("//")
        if comment_pos != -1:
            in_string = False
            escaped = False
            for i, char in enumerate(line):
                if escaped:
                    escaped = False
                    continue
                if char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = not in_string
                elif (
                    char == "/"
                    and i + 1 < len(line)
                    and line[i + 1] == "/"
                    and not in_string
                ):
                    line = line[:i].rstrip()
                    break

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)
