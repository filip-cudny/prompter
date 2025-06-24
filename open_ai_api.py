"""OpenAI API client for speech-to-text transcription."""

import os
from typing import Optional, BinaryIO
from openai import OpenAI
from api import APIError


class OpenAIClient:
    """Client for OpenAI API operations."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("LOCAL_OPENAI_API_KEY")
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
