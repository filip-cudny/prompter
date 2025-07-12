"""OpenAI service for managing multiple OpenAI client instances."""

import os
from typing import Dict, Optional, List, BinaryIO, Any
from openai import OpenAI
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from core.exceptions import ConfigurationError


class OpenAiService:
    """Service for managing OpenAI client instances for different models."""

    def __init__(
        self,
        models_config: Dict[str, Any],
        speech_to_text_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize OpenAI service with model configurations.

        Args:
            models_config: Dictionary of model configurations from settings
            speech_to_text_config: Optional speech-to-text model configuration
        """
        self._clients: Dict[str, OpenAI] = {}
        self._models_config = models_config
        self._speech_to_text_config = speech_to_text_config

        self._initialize_clients()

    def _initialize_clients(self) -> None:
        """Initialize OpenAI clients for all configured models."""
        for model_key, model_config in self._models_config.items():
            try:
                api_key = model_config.get("api_key")
                if not api_key:
                    raise Exception(
                        "OpenAI API key not found. Set OPENAI_API_KEY environment variable."
                    )

                client = OpenAI(
                    api_key=api_key,
                    base_url=model_config.get("base_url"),
                )
                self._clients[model_key] = client
            except Exception as e:
                raise ConfigurationError(
                    f"Failed to initialize OpenAI client for model '{model_key}': {e}"
                ) from e

        if self._speech_to_text_config:
            try:
                api_key = self._speech_to_text_config.get("api_key")
                if not api_key:
                    raise Exception(
                        "OpenAI API key not found. Set OPENAI_API_KEY environment variable."
                    )

                client = OpenAI(
                    api_key=api_key,
                    base_url=self._speech_to_text_config.get("base_url"),
                )
                self._clients["speech_to_text"] = client
            except Exception as e:
                raise ConfigurationError(
                    f"Failed to initialize OpenAI client for speech-to-text: {e}"
                ) from e

    def complete(
        self,
        model_key: str,
        messages: List[ChatCompletionMessageParam],
        max_tokens: Optional[int] = None,
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

        if model_key not in self._models_config:
            raise ConfigurationError(f"Model configuration for '{model_key}' not found")

        client = self._clients[model_key]
        model_config = self._models_config[model_key]

        try:
            response = client.chat.completions.create(
                model=model_config["model"],
                messages=messages,
                temperature=model_config.get("temperature", 0.7),
                max_tokens=max_tokens,
                **kwargs,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise Exception(f"Failed to generate completion: {e}") from e

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
        elif model_key in self._models_config:
            model_name = self._models_config[model_key]["model"]
        else:
            raise ConfigurationError(f"Model configuration for '{model_key}' not found")

        try:
            transcription = client.audio.transcriptions.create(
                model=model_name,
                file=audio_file,
            )
            return transcription.text.strip()
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
        except IOError as e:
            raise Exception(f"Failed to read audio file: {e}") from e

    def get_model_config(self, model_key: str) -> Dict[str, Any]:
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
        elif model_key in self._models_config:
            return self._models_config[model_key]
        else:
            raise ConfigurationError(f"Model configuration for '{model_key}' not found")

    def get_available_models(self) -> List[str]:
        """
        Get list of available model keys.

        Returns:
            List of available model keys
        """
        models = list(self._models_config.keys())
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