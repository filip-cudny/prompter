"""OpenAI service for managing multiple OpenAI client instances."""

import logging
import os
import re
from collections.abc import Generator
from typing import Any, BinaryIO

logger = logging.getLogger(__name__)

from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from core.exceptions import ConfigurationError

BASE64_PATTERN = re.compile(r"(data:[^;]+;base64,)[A-Za-z0-9+/=]{50,}")


def truncate_base64_for_logging(obj: Any) -> Any:
    """Recursively truncate base64 data in nested structures for logging."""
    if isinstance(obj, str):
        return BASE64_PATTERN.sub(r"\1<base64 truncated>", obj)
    if isinstance(obj, dict):
        return {k: truncate_base64_for_logging(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [truncate_base64_for_logging(item) for item in obj]
    return obj


class OpenAiService:
    """Service for managing OpenAI client instances for different models."""

    def __init__(
        self,
        models_config: list[dict[str, Any]],
        speech_to_text_config: dict[str, Any] | None = None,
    ):
        """
        Initialize OpenAI service with model configurations.

        Args:
            models_config: List of model configurations from settings (array with 'id' field)
            speech_to_text_config: Optional speech-to-text model configuration
        """
        self._clients: dict[str, OpenAI] = {}
        self._models_by_id: dict[str, dict[str, Any]] = {}
        self._unavailable_models: dict[str, str] = {}
        self._speech_to_text_config = speech_to_text_config

        for model in models_config:
            model_id = model.get("id")
            if model_id:
                self._models_by_id[model_id] = model

        self._initialize_clients()

    def _initialize_clients(self) -> None:
        """Initialize OpenAI clients for all configured models.

        Models with missing API keys are tracked in _unavailable_models instead of
        raising exceptions, allowing the app to start in degraded mode.
        """
        for model_id, model_config in self._models_by_id.items():
            api_key = model_config.get("api_key")
            if not api_key:
                self._unavailable_models[model_id] = "Missing API key"
                continue

            try:
                client = OpenAI(
                    api_key=api_key,
                    base_url=model_config.get("base_url"),
                )
                self._clients[model_id] = client
            except Exception as e:
                self._unavailable_models[model_id] = str(e)

        if self._speech_to_text_config:
            api_key = self._speech_to_text_config.get("api_key")
            if not api_key:
                self._unavailable_models["speech_to_text"] = "Missing API key"
            else:
                try:
                    client = OpenAI(
                        api_key=api_key,
                        base_url=self._speech_to_text_config.get("base_url"),
                    )
                    self._clients["speech_to_text"] = client
                except Exception as e:
                    self._unavailable_models["speech_to_text"] = str(e)

    def get_unavailable_models(self) -> dict[str, str]:
        """Get dictionary of unavailable models and their reasons.

        Returns:
            Dictionary mapping model_id to reason string for unavailable models
        """
        return self._unavailable_models.copy()

    def complete(
        self,
        model_key: str,
        messages: list[ChatCompletionMessageParam],
        **kwargs: Any,
    ) -> str:
        """
        Generate text completion using specified model.

        Args:
            model_key: Key of the model configuration to use
            messages: List of message dictionaries with 'role' and 'content' keys
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters for the API call

        Returns:
            Generated text completion

        Raises:
            ConfigurationError: If model_key is not found
            Exception: If completion fails
        """
        if model_key not in self._clients:
            raise ConfigurationError(f"Model '{model_key}' not found in configuration")

        if model_key not in self._models_by_id:
            raise ConfigurationError(f"Model configuration for '{model_key}' not found")

        client = self._clients[model_key]
        model_config = self._models_by_id[model_key]

        try:
            completion_params = {
                "model": model_config["model"],
                "messages": messages,
                **kwargs,
            }

            parameters = model_config.get("parameters", {})
            for param_name, param_value in parameters.items():
                completion_params[param_name] = param_value

            logger.debug("Sending completion request: %s", truncate_base64_for_logging(completion_params))
            response = client.chat.completions.create(**completion_params)
            return response.choices[0].message.content.strip()
        except AuthenticationError as e:
            raise Exception("API key is invalid or expired. Please check your API key configuration.") from e
        except APIConnectionError as e:
            raise Exception("Connection failed. Please check your internet connection and try again.") from e
        except RateLimitError as e:
            raise Exception("Rate limit exceeded. Please wait a moment and try again.") from e
        except APIStatusError as e:
            raise Exception(f"API error (status {e.status_code}): {e.message}") from e
        except Exception as e:
            raise Exception(f"Failed to generate completion: {e}") from e

    def complete_stream(
        self,
        model_key: str,
        messages: list[ChatCompletionMessageParam],
        **kwargs: Any,
    ) -> Generator[tuple[str, str], None, None]:
        """
        Generate streaming text completion using specified model.

        Args:
            model_key: Key of the model configuration to use
            messages: List of message dictionaries with 'role' and 'content' keys
            **kwargs: Additional parameters for the API call

        Yields:
            Tuples of (chunk_text, accumulated_text) for each streamed token

        Raises:
            ConfigurationError: If model_key is not found
            Exception: If completion fails
        """
        if model_key not in self._clients:
            raise ConfigurationError(f"Model '{model_key}' not found in configuration")

        if model_key not in self._models_by_id:
            raise ConfigurationError(f"Model configuration for '{model_key}' not found")

        client = self._clients[model_key]
        model_config = self._models_by_id[model_key]

        try:
            completion_params = {
                "model": model_config["model"],
                "messages": messages,
                "stream": True,
                **kwargs,
            }

            parameters = model_config.get("parameters", {})
            for param_name, param_value in parameters.items():
                completion_params[param_name] = param_value

            logger.debug("Sending streaming request: %s", truncate_base64_for_logging(completion_params))
            accumulated = ""
            response = client.chat.completions.create(**completion_params)

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    chunk_text = chunk.choices[0].delta.content
                    accumulated += chunk_text
                    yield (chunk_text, accumulated)

        except AuthenticationError as e:
            raise Exception("API key is invalid or expired. Please check your API key configuration.") from e
        except APIConnectionError as e:
            raise Exception("Connection failed. Please check your internet connection and try again.") from e
        except RateLimitError as e:
            raise Exception("Rate limit exceeded. Please wait a moment and try again.") from e
        except APIStatusError as e:
            raise Exception(f"API error (status {e.status_code}): {e.message}") from e
        except Exception as e:
            raise Exception(f"Failed to generate streaming completion: {e}") from e

    def transcribe_audio(
        self,
        audio_file: BinaryIO,
        model_key: str = "speech_to_text",
    ) -> str:
        """
        Transcribe audio using specified model.

        Args:
            audio_file: Binary audio file object
            model_key: Key of the model configuration to use (defaults to "speech_to_text")

        Returns:
            Transcribed text

        Raises:
            ConfigurationError: If model_key is not found
            Exception: If transcription fails
        """
        if model_key not in self._clients:
            raise ConfigurationError(f"Model '{model_key}' not found in configuration")

        client = self._clients[model_key]

        if model_key == "speech_to_text" and self._speech_to_text_config:
            model_name = self._speech_to_text_config["model"]
        elif model_key in self._models_by_id:
            model_name = self._models_by_id[model_key]["model"]
        else:
            raise ConfigurationError(f"Model configuration for '{model_key}' not found")

        try:
            transcription = client.audio.transcriptions.create(
                model=model_name,
                file=audio_file,
            )
            return transcription.text.strip()
        except AuthenticationError as e:
            raise Exception("API key is invalid or expired. Please check your API key configuration.") from e
        except APIConnectionError as e:
            raise Exception("Connection failed. Please check your internet connection and try again.") from e
        except RateLimitError as e:
            raise Exception("Rate limit exceeded. Please wait a moment and try again.") from e
        except APIStatusError as e:
            raise Exception(f"API error (status {e.status_code}): {e.message}") from e
        except Exception as e:
            raise Exception(f"Failed to transcribe audio: {e}") from e

    def transcribe_audio_file(
        self,
        file_path: str,
        model_key: str = "speech_to_text",
    ) -> str:
        """
        Transcribe audio from file path.

        Args:
            file_path: Path to the audio file
            model_key: Key of the model configuration to use (defaults to "speech_to_text")

        Returns:
            Transcribed text

        Raises:
            ConfigurationError: If model_key is not found
            Exception: If transcription fails
        """
        if model_key not in self._clients:
            raise ConfigurationError(f"Model '{model_key}' not found in configuration")

        if not os.path.exists(file_path):
            raise Exception(f"Audio file not found: {file_path}")

        try:
            with open(file_path, "rb") as audio_file:
                return self.transcribe_audio(audio_file, model_key)
        except OSError as e:
            raise Exception(f"Failed to read audio file: {e}") from e

    def get_model_config(self, model_key: str) -> dict[str, Any]:
        """
        Get model configuration for specified key.

        Args:
            model_key: Key of the model configuration

        Returns:
            Model configuration dictionary

        Raises:
            ConfigurationError: If model_key is not found
        """
        if model_key == "speech_to_text" and self._speech_to_text_config:
            return self._speech_to_text_config
        elif model_key in self._models_by_id:
            return self._models_by_id[model_key]
        else:
            raise ConfigurationError(f"Model configuration for '{model_key}' not found")

    def get_available_models(self) -> list[str]:
        """
        Get list of available model keys.

        Returns:
            List of available model keys
        """
        models = list(self._models_by_id.keys())
        if self._speech_to_text_config:
            models.append("speech_to_text")
        return models

    def has_model(self, model_key: str) -> bool:
        """
        Check if model key is available.

        Args:
            model_key: Key to check

        Returns:
            True if model is available, False otherwise
        """
        return model_key in self._clients

    def get_model_unavailable_reason(self, model_key: str) -> str | None:
        """
        Get reason why a model is unavailable, if any.

        Args:
            model_key: Key to check

        Returns:
            Reason string if unavailable, None if available or unknown
        """
        return self._unavailable_models.get(model_key)
