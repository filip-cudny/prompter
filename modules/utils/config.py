"""Configuration management utilities."""

import os
import json
import json5
from typing import Any, Dict, List, Optional
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
    number_input_debounce_ms: int = 200
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

    def save_settings(self) -> None:
        """Save current settings to JSON file."""
        if self._settings_data is None:
            raise ConfigurationError(
                "ConfigService not initialized. Call initialize() first."
            )

        settings_file = Path("settings/settings.json")
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(self._settings_data, f, indent=2)

    def update_prompts_order(self, prompt_ids: List[str], persist: bool = True) -> None:
        """Reorder prompts by ID list.

        Args:
            prompt_ids: List of prompt IDs in the desired order
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError(
                "ConfigService not initialized. Call initialize() first."
            )

        prompts = self._settings_data.get("prompts", [])
        id_to_prompt = {p["id"]: p for p in prompts}
        self._settings_data["prompts"] = [
            id_to_prompt[pid] for pid in prompt_ids if pid in id_to_prompt
        ]
        if persist:
            self.save_settings()

    def update_setting(self, key: str, value: Any, persist: bool = True) -> None:
        """Update a top-level setting value and save.

        Args:
            key: Setting key (e.g., 'default_model', 'number_input_debounce_ms')
            value: New value for the setting
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError(
                "ConfigService not initialized. Call initialize() first."
            )

        self._settings_data[key] = value
        if persist:
            self.save_settings()

        if self._config and hasattr(self._config, key):
            setattr(self._config, key, value)

    def add_prompt(self, prompt_data: Dict[str, Any], persist: bool = True) -> None:
        """Add a new prompt to settings.

        Args:
            prompt_data: Prompt configuration dict with id, name, messages, etc.
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError(
                "ConfigService not initialized. Call initialize() first."
            )

        if "prompts" not in self._settings_data:
            self._settings_data["prompts"] = []

        self._settings_data["prompts"].append(prompt_data)
        if persist:
            self.save_settings()

    def update_prompt(
        self, prompt_id: str, prompt_data: Dict[str, Any], persist: bool = True
    ) -> None:
        """Update an existing prompt.

        Args:
            prompt_id: ID of the prompt to update
            prompt_data: Updated prompt configuration
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError(
                "ConfigService not initialized. Call initialize() first."
            )

        prompts = self._settings_data.get("prompts", [])
        for i, prompt in enumerate(prompts):
            if prompt.get("id") == prompt_id:
                self._settings_data["prompts"][i] = prompt_data
                break
        if persist:
            self.save_settings()

    def delete_prompt(self, prompt_id: str, persist: bool = True) -> None:
        """Delete a prompt by ID.

        Args:
            prompt_id: ID of the prompt to delete
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError(
                "ConfigService not initialized. Call initialize() first."
            )

        prompts = self._settings_data.get("prompts", [])
        self._settings_data["prompts"] = [
            p for p in prompts if p.get("id") != prompt_id
        ]
        if persist:
            self.save_settings()

    def add_model(
        self, model_key: str, model_config: Dict[str, Any], persist: bool = True
    ) -> None:
        """Add a new model to settings.

        Args:
            model_key: Unique key for the model
            model_config: Model configuration dict
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError(
                "ConfigService not initialized. Call initialize() first."
            )

        if "models" not in self._settings_data:
            self._settings_data["models"] = {}

        self._settings_data["models"][model_key] = model_config
        if self._config:
            self._config.models[model_key] = model_config
        if persist:
            self.save_settings()

    def update_model(
        self, model_key: str, model_config: Dict[str, Any], persist: bool = True
    ) -> None:
        """Update an existing model configuration.

        Args:
            model_key: Key of the model to update
            model_config: Updated model configuration
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError(
                "ConfigService not initialized. Call initialize() first."
            )

        if "models" not in self._settings_data:
            self._settings_data["models"] = {}

        self._settings_data["models"][model_key] = model_config
        if self._config:
            self._config.models[model_key] = model_config
        if persist:
            self.save_settings()

    def delete_model(self, model_key: str, persist: bool = True) -> None:
        """Delete a model by key.

        Args:
            model_key: Key of the model to delete
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError(
                "ConfigService not initialized. Call initialize() first."
            )

        models = self._settings_data.get("models", {})
        if model_key in models:
            del self._settings_data["models"][model_key]
            if self._config and model_key in self._config.models:
                del self._config.models[model_key]
        if persist:
            self.save_settings()

    def update_notifications(
        self, notifications_config: Dict[str, Any], persist: bool = True
    ) -> None:
        """Update notifications configuration.

        Args:
            notifications_config: Full notifications configuration dict
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError(
                "ConfigService not initialized. Call initialize() first."
            )

        self._settings_data["notifications"] = notifications_config
        if persist:
            self.save_settings()

    def update_speech_model(
        self, speech_config: Dict[str, Any], persist: bool = True
    ) -> None:
        """Update speech-to-text model configuration.

        Args:
            speech_config: Speech model configuration dict
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError(
                "ConfigService not initialized. Call initialize() first."
            )

        self._settings_data["speech_to_text_model"] = speech_config
        if self._config:
            self._config.speech_to_text_model = speech_config
        if persist:
            self.save_settings()

    def update_keymaps(
        self, keymaps: List[Dict[str, Any]], persist: bool = True
    ) -> None:
        """Update keymaps configuration.

        Args:
            keymaps: List of keymap configuration dicts
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError(
                "ConfigService not initialized. Call initialize() first."
            )

        self._settings_data["keymaps"] = keymaps
        if persist:
            self.save_settings()

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

        # Parse number input debounce delay
        debounce_str = os.getenv("NUMBER_INPUT_DEBOUNCE_MS", "200")
        try:
            config.number_input_debounce_ms = int(debounce_str)
        except ValueError:
            config.number_input_debounce_ms = 200

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

                # Load number input debounce delay from settings if available
                if "number_input_debounce_ms" in self._settings_data:
                    try:
                        config.number_input_debounce_ms = int(
                            self._settings_data["number_input_debounce_ms"]
                        )
                    except (ValueError, TypeError):
                        pass

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

    # Validate number_input_debounce_ms
    if config.number_input_debounce_ms is not None:
        try:
            debounce_ms = int(config.number_input_debounce_ms)
            if debounce_ms < 0 or debounce_ms > 10000:
                raise ConfigurationError(
                    "number_input_debounce_ms must be between 0 and 10000 milliseconds"
                )
        except (ValueError, TypeError):
            raise ConfigurationError("number_input_debounce_ms must be a valid integer")

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
