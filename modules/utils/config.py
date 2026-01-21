"""Configuration management utilities."""

import contextlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

import json5
from dotenv import load_dotenv

from core.exceptions import ConfigurationError

from .keymap import KeymapManager


def safe_load_json(file_path: Path) -> dict[str, Any]:
    """Load JSON file with optional comment support."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        return json5.loads(content)

    except FileNotFoundError as e:
        raise ConfigurationError(f"Settings file not found: {file_path}") from e
    except (json.JSONDecodeError, ValueError) as e:
        raise ConfigurationError(f"Invalid JSON in settings file: {e}") from e
    except Exception as e:
        raise ConfigurationError(f"Error loading settings file: {e}") from e


@dataclass
class AppConfig:
    """Application configuration."""

    menu_position_offset: tuple = (0, 0)
    number_input_debounce_ms: int = 200
    keymap_manager: Optional["KeymapManager"] = None
    models: list[dict[str, Any]] | None = None
    speech_to_text_model: dict[str, Any] | None = None
    default_model: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        config_dict = asdict(self)
        config_dict.pop("keymap_manager", None)
        return config_dict

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
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
            self._on_save_callbacks = []
            self._initialized = True

    def initialize(self, env_file: str | None = None, settings_file: str | None = None):
        """Initialize the configuration service."""
        self._config = self._load_config(env_file, settings_file)
        return self._config

    def register_on_save_callback(self, callback):
        """Register callback to be called after settings are saved."""
        self._on_save_callbacks.append(callback)

    def get_config(self) -> AppConfig:
        """Get the current configuration."""
        if self._config is None:
            raise ConfigurationError("ConfigService not initialized. Call initialize() first.")
        return self._config

    def get_settings_data(self) -> dict[str, Any]:
        """Get the raw settings data."""
        if self._settings_data is None:
            raise ConfigurationError("ConfigService not initialized. Call initialize() first.")
        return self._settings_data

    def reload_settings(self) -> None:
        """Reload settings from disk, discarding any in-memory changes."""
        settings_file = Path("settings/settings.json")
        if not settings_file.exists():
            raise ConfigurationError(f"Settings file not found: {settings_file}")

        self._settings_data = safe_load_json(settings_file)

        if self._config:
            self._config.models = self._settings_data.get("models", [])
            self._config.speech_to_text_model = self._settings_data.get("speech_to_text_model")
            self._config.default_model = self._settings_data.get("default_model")

            _migrate_model_params(self._config.models)
            _load_api_keys(self._config.models)
            if self._config.speech_to_text_model:
                _load_api_key_for_model(self._config.speech_to_text_model, "speech_to_text_model")

    def update_default_model(self, model_id: str) -> None:
        """Update the default model configuration."""
        if self._config is None:
            raise ConfigurationError("ConfigService not initialized. Call initialize() first.")

        if not self.get_model_by_id(model_id):
            raise ConfigurationError(f"Model '{model_id}' not found in configuration")

        self._config.default_model = model_id

    def get_model_by_id(self, model_id: str) -> dict[str, Any] | None:
        """Get a model configuration by its ID."""
        if self._config is None or not self._config.models:
            return None
        for model in self._config.models:
            if model.get("id") == model_id:
                return model
        return None

    def get_models_list(self) -> list[dict[str, Any]]:
        """Get list of all model configurations."""
        if self._config is None or not self._config.models:
            return []
        return self._config.models

    def save_settings(self) -> None:
        """Save current settings to JSON file."""
        if self._settings_data is None:
            raise ConfigurationError("ConfigService not initialized. Call initialize() first.")

        settings_file = Path("settings/settings.json")
        settings_to_save = self._sanitize_settings_for_save(self._settings_data)
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings_to_save, f, indent=2, ensure_ascii=False)

        for callback in self._on_save_callbacks:
            callback()

    def _sanitize_settings_for_save(self, settings: dict[str, Any]) -> dict[str, Any]:
        """Remove sensitive data (api_key) before saving to disk, except for direct API keys."""
        import copy

        sanitized = copy.deepcopy(settings)

        if "models" in sanitized and isinstance(sanitized["models"], list):
            for model_config in sanitized["models"]:
                if model_config.get("api_key_source") != "direct":
                    model_config.pop("api_key", None)

        if "speech_to_text_model" in sanitized:
            sanitized["speech_to_text_model"].pop("api_key", None)

        return sanitized

    def update_prompts_order(self, prompt_ids: list[str], persist: bool = True) -> None:
        """Reorder prompts by ID list.

        Args:
            prompt_ids: List of prompt IDs in the desired order
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError("ConfigService not initialized. Call initialize() first.")

        prompts = self._settings_data.get("prompts", [])
        id_to_prompt = {p["id"]: p for p in prompts}
        self._settings_data["prompts"] = [id_to_prompt[pid] for pid in prompt_ids if pid in id_to_prompt]
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
            raise ConfigurationError("ConfigService not initialized. Call initialize() first.")

        self._settings_data[key] = value
        if persist:
            self.save_settings()

        if self._config and hasattr(self._config, key):
            setattr(self._config, key, value)

    def add_prompt(self, prompt_data: dict[str, Any], persist: bool = True) -> None:
        """Add a new prompt to settings.

        Args:
            prompt_data: Prompt configuration dict with id, name, messages, etc.
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError("ConfigService not initialized. Call initialize() first.")

        if "prompts" not in self._settings_data:
            self._settings_data["prompts"] = []

        self._settings_data["prompts"].append(prompt_data)
        if persist:
            self.save_settings()

    def update_prompt(self, prompt_id: str, prompt_data: dict[str, Any], persist: bool = True) -> None:
        """Update an existing prompt.

        Args:
            prompt_id: ID of the prompt to update
            prompt_data: Updated prompt configuration
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError("ConfigService not initialized. Call initialize() first.")

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
            raise ConfigurationError("ConfigService not initialized. Call initialize() first.")

        prompts = self._settings_data.get("prompts", [])
        self._settings_data["prompts"] = [p for p in prompts if p.get("id") != prompt_id]
        if persist:
            self.save_settings()

    def add_model(self, model_id: str, model_config: dict[str, Any], persist: bool = True) -> None:
        """Add a new model to settings.

        Args:
            model_id: UUID for the model
            model_config: Model configuration dict (should include 'id')
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError("ConfigService not initialized. Call initialize() first.")

        if "models" not in self._settings_data:
            self._settings_data["models"] = []

        model_with_id = {"id": model_id, **model_config}
        self._settings_data["models"].append(model_with_id)
        if self._config:
            if self._config.models is None:
                self._config.models = []
            self._config.models.append(model_with_id)
        if persist:
            self.save_settings()

    def update_model(self, model_id: str, model_config: dict[str, Any], persist: bool = True) -> None:
        """Update an existing model configuration or add if not found.

        Args:
            model_id: UUID of the model to update
            model_config: Updated model configuration
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError("ConfigService not initialized. Call initialize() first.")

        if "models" not in self._settings_data:
            self._settings_data["models"] = []

        model_with_id = {"id": model_id, **model_config}

        found = False
        for i, model in enumerate(self._settings_data["models"]):
            if model.get("id") == model_id:
                self._settings_data["models"][i] = model_with_id
                found = True
                break

        if not found:
            self._settings_data["models"].append(model_with_id)

        if self._config:
            if self._config.models is None:
                self._config.models = []
            config_found = False
            for i, model in enumerate(self._config.models):
                if model.get("id") == model_id:
                    self._config.models[i] = model_with_id
                    config_found = True
                    break
            if not config_found:
                self._config.models.append(model_with_id)

        if persist:
            self.save_settings()

    def delete_model(self, model_id: str, persist: bool = True) -> None:
        """Delete a model by ID.

        Args:
            model_id: UUID of the model to delete
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError("ConfigService not initialized. Call initialize() first.")

        models = self._settings_data.get("models", [])
        self._settings_data["models"] = [m for m in models if m.get("id") != model_id]

        if self._config and self._config.models:
            self._config.models = [m for m in self._config.models if m.get("id") != model_id]

        if persist:
            self.save_settings()

    def update_notifications(self, notifications_config: dict[str, Any], persist: bool = True) -> None:
        """Update notifications configuration.

        Args:
            notifications_config: Full notifications configuration dict
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError("ConfigService not initialized. Call initialize() first.")

        self._settings_data["notifications"] = notifications_config
        if persist:
            self.save_settings()

    def update_speech_model(self, speech_config: dict[str, Any], persist: bool = True) -> None:
        """Update speech-to-text model configuration.

        Args:
            speech_config: Speech model configuration dict
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError("ConfigService not initialized. Call initialize() first.")

        self._settings_data["speech_to_text_model"] = speech_config
        if self._config:
            self._config.speech_to_text_model = speech_config
        if persist:
            self.save_settings()

    def update_keymaps(self, keymaps: list[dict[str, Any]], persist: bool = True) -> None:
        """Update keymaps configuration.

        Args:
            keymaps: List of keymap configuration dicts
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError("ConfigService not initialized. Call initialize() first.")

        self._settings_data["keymaps"] = keymaps
        if persist:
            self.save_settings()

    def get_description_generator_config(self) -> dict[str, Any]:
        """Get the description generator configuration.

        Returns:
            Dict with 'model' and 'system_prompt' keys
        """
        if self._settings_data is None:
            raise ConfigurationError("ConfigService not initialized. Call initialize() first.")

        default_system_prompt = (
            "You are an AI assistant whose sole task is to generate a short, concise "
            "description explaining what a given prompt does.\n\n"
            "You will receive:\n\n"
            "* The prompt name.\n"
            "* The full system prompt content.\n"
            "* The user message template, including placeholders and their explanations.\n\n"
            "Your goal:\n\n"
            "* Produce a brief description (1–3 sentences or up to 3 bullet points) that "
            "clearly summarizes the purpose and behavior of the prompt.\n"
            "* The description must be suitable for quick recall in a list or context menu.\n"
            "* Write the description in the same primary language as the prompt itself "
            "(the core prompt language), even if examples inside the prompt use other languages.\n\n"
            "Rules:\n\n"
            "* Emphasize whether the prompt performs execution, refinement, correction, "
            "translation, or a lossless transformation.\n"
            "* Explicitly distinguish transformations from summarization or content reduction "
            "when applicable.\n"
            "* Do not restate the prompt name verbatim.\n"
            "* Do not describe internal formatting or XML mechanics unless essential.\n"
            "* Do not explain placeholders individually unless critical.\n"
            "* Do not add examples.\n"
            "* Output either a short paragraph or up to 3 bullet points.\n"
            "* Do not use meta commentary.\n"
            "* Output only the final description text."
        )

        default_config = {
            "model": "",
            "system_prompt": default_system_prompt,
        }

        config = self._settings_data.get("description_generator", {})
        result = {**default_config, **config}

        if "prompt" in result and "system_prompt" not in config:
            result["system_prompt"] = result.pop("prompt")
        elif "prompt" in result:
            del result["prompt"]

        return result

    def update_description_generator_config(self, config: dict[str, Any], persist: bool = True) -> None:
        """Update description generator configuration.

        Args:
            config: Dict with 'model' and/or 'prompt' keys
            persist: Whether to save settings to file immediately
        """
        if self._settings_data is None:
            raise ConfigurationError("ConfigService not initialized. Call initialize() first.")

        if "description_generator" not in self._settings_data:
            self._settings_data["description_generator"] = {}

        self._settings_data["description_generator"].update(config)
        if persist:
            self.save_settings()

    def _load_config(self, env_file: str | None = None, settings_file: str | None = None) -> AppConfig:
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

                config.keymap_manager = KeymapManager(self._settings_data.get("keymaps", []))

                # Load models and speech_to_text_model configuration (now array)
                config.models = self._settings_data.get("models", [])
                config.speech_to_text_model = self._settings_data.get("speech_to_text_model")

                # Migrate legacy model params to nested parameters dict
                _migrate_model_params(config.models)

                # Set default_model to first model ID if not set
                config.default_model = self._settings_data.get("default_model")
                if config.models and not config.default_model:
                    config.default_model = config.models[0].get("id")

                # Load number input debounce delay from settings if available
                if "number_input_debounce_ms" in self._settings_data:
                    with contextlib.suppress(ValueError, TypeError):
                        config.number_input_debounce_ms = int(self._settings_data["number_input_debounce_ms"])

                # Load API keys from environment variables
                _load_api_keys(config.models)
                if config.speech_to_text_model:
                    _load_api_key_for_model(config.speech_to_text_model, "speech_to_text_model")

            except Exception as e:
                raise ConfigurationError(f"Failed to load configuration: {e}") from e
        else:
            raise ConfigurationError(f"Settings file not found: {keymap_settings_file}")

        validate_config(config)
        return config


def get_config_service(env_file: str | None = None, settings_file: str | None = None) -> ConfigService:
    """Get initialized ConfigService singleton."""
    config_service = ConfigService()
    if config_service._config is None:
        config_service.initialize(env_file, settings_file)
    return config_service


def initialize_config(env_file: str | None = None, settings_file: str | None = None) -> AppConfig:
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


def load_config(env_file: str | None = None, settings_file: str | None = None) -> AppConfig:
    """Load configuration from environment variables and .env file."""
    config_service = get_config_service(env_file, settings_file)
    return config_service.get_config()


def validate_config(config: AppConfig) -> None:
    """Validate configuration values."""

    if config.models is None:
        raise ConfigurationError("Models configuration is required")

    if not config.models:
        raise ConfigurationError("At least one model must be configured")

    if not isinstance(config.models, list):
        raise ConfigurationError("Models must be an array")

    seen_ids = set()
    for model_config in config.models:
        if not isinstance(model_config, dict):
            raise ConfigurationError("Each model entry must be a dictionary")

        model_id = model_config.get("id")
        if not model_id:
            raise ConfigurationError("Each model must have an 'id' field")

        if model_id in seen_ids:
            raise ConfigurationError(f"Duplicate model ID: '{model_id}'")
        seen_ids.add(model_id)

        model_display = model_config.get("display_name", model_id)

        required_fields = ["model", "display_name"]
        for field in required_fields:
            if field not in model_config:
                raise ConfigurationError(f"Model '{model_display}' missing required field: {field}")

            if not model_config[field]:
                raise ConfigurationError(f"Model '{model_display}' field '{field}' cannot be empty")

        api_key_source = model_config.get("api_key_source", "env")
        if api_key_source == "env":
            if "api_key_env" not in model_config or not model_config["api_key_env"]:
                raise ConfigurationError(f"Model '{model_display}' requires 'api_key_env' when api_key_source is 'env'")
        elif api_key_source == "direct" and ("api_key" not in model_config or not model_config["api_key"]):
            raise ConfigurationError(f"Model '{model_display}' requires 'api_key' when api_key_source is 'direct'")

        if "parameters" in model_config:
            params = model_config["parameters"]
            if not isinstance(params, dict):
                raise ConfigurationError(f"Model '{model_display}' parameters must be a dictionary")
            for param_name, param_value in params.items():
                if not isinstance(param_value, (int, float, str, bool)):
                    raise ConfigurationError(
                        f"Model '{model_display}' parameter '{param_name}' must be a number, string, or boolean"
                    )

        if (
            "base_url" in model_config
            and model_config["base_url"]
            and not model_config["base_url"].startswith(("http://", "https://"))
        ):
            raise ConfigurationError(f"Model '{model_display}' base_url must start with http:// or https://")

    # Validate number_input_debounce_ms
    if config.number_input_debounce_ms is not None:
        try:
            debounce_ms = int(config.number_input_debounce_ms)
            if debounce_ms < 0 or debounce_ms > 10000:
                raise ConfigurationError("number_input_debounce_ms must be between 0 and 10000 milliseconds")
        except (ValueError, TypeError) as e:
            raise ConfigurationError("number_input_debounce_ms must be a valid integer") from e

    # Validate speech_to_text_model if present
    if config.speech_to_text_model is not None:
        if not isinstance(config.speech_to_text_model, dict):
            raise ConfigurationError("speech_to_text_model must be a dictionary")

        # Required fields for speech_to_text_model
        required_fields = ["model", "display_name", "api_key_env"]
        for field in required_fields:
            if field not in config.speech_to_text_model:
                raise ConfigurationError(f"speech_to_text_model missing required field: {field}")

            if not config.speech_to_text_model[field]:
                raise ConfigurationError(f"speech_to_text_model field '{field}' cannot be empty")

        # Validate base_url if present (optional field)
        if (
            "base_url" in config.speech_to_text_model
            and config.speech_to_text_model["base_url"]
            and not config.speech_to_text_model["base_url"].startswith(("http://", "https://"))
        ):
            raise ConfigurationError("speech_to_text_model base_url must start with http:// or https://")


def _load_api_keys(models: list[dict[str, Any]]) -> None:
    """Load API keys from environment variables for all models."""
    for model_config in models:
        model_name = model_config.get("display_name", model_config.get("id", "unknown"))
        _load_api_key_for_model(model_config, model_name)


def _load_api_key_for_model(model_config: dict[str, Any], model_name: str) -> None:
    """Load API key based on api_key_source setting."""
    source = model_config.get("api_key_source", "env")
    if source == "env":
        api_key_env = model_config.get("api_key_env")
        if api_key_env:
            model_config["api_key"] = os.getenv(api_key_env)


def _migrate_model_params(models: list[dict[str, Any]]) -> None:
    """Migrate top-level model params to nested 'parameters' dict."""
    KNOWN_PARAMS = {"temperature", "max_tokens", "top_p", "frequency_penalty", "presence_penalty", "reasoning_effort"}

    for model in models:
        if "parameters" not in model:
            model["parameters"] = {}

        for param in list(KNOWN_PARAMS):
            if param in model and param not in model["parameters"]:
                model["parameters"][param] = model.pop(param)


def load_settings_file(settings_path: Path) -> dict[str, Any]:
    """Load settings from JSON file with optional comment support."""
    return safe_load_json(settings_path)
