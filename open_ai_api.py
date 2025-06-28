"""OpenAI API client for speech-to-text transcription."""

import os
from typing import Optional, BinaryIO, List, Any
from openai import OpenAI
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from api import APIError


class OpenAIClient:
    """Client for OpenAI API operations."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise APIError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable."
            )

        self.client = OpenAI(api_key=self.api_key)

    def transcribe_audio(
        self, audio_file: BinaryIO, model: str = "gpt-4o-transcribe"
    ) -> str:
        """
        Transcribe audio using OpenAI Whisper API.

        Args:
            audio_file: Binary audio file object
            model: Model to use for transcription (default: gpt-4o-transcribe)

        Returns:
            Transcribed text

        Raises:
            APIError: If transcription fails
        """
        try:
            transcription = self.client.audio.transcriptions.create(
                model=model,
                file=audio_file,
            )
            return transcription.text.strip()

        except Exception as e:
            raise APIError(f"Failed to transcribe audio: {e}") from e

    def transcribe_audio_file(
        self, file_path: str, model: str = "gpt-4o-transcribe"
    ) -> str:
        """
        Transcribe audio from file path.

        Args:
            file_path: Path to the audio file
            model: Model to use for transcription (default: gpt-4o-transcribe)

        Returns:
            Transcribed text

        Raises:
            APIError: If transcription fails
        """
        if not os.path.exists(file_path):
            raise APIError(f"Audio file not found: {file_path}")

        try:
            with open(file_path, "rb") as audio_file:
                return self.transcribe_audio(audio_file, model)
        except IOError as e:
            raise APIError(f"Failed to read audio file: {e}") from e

    def complete(
        self,
        messages: List[ChatCompletionMessageParam],
        model: str = "gpt-4.1",
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate text completion using OpenAI Chat API.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            model: Model to use for completion (default: gpt-4.1)
            temperature: Sampling temperature (default: 0.7)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters for the API call

        Returns:
            Generated text completion

        Raises:
            APIError: If completion fails
        """
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            raise APIError(f"Failed to generate completion: {e}") from e
