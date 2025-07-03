"""Speech-to-text service with audio recording functionality."""

import contextlib
import os
import sys
import tempfile
import threading
import time
import uuid
from typing import Callable, Dict, Optional

try:
    import pyaudio

    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
import wave

from open_ai_api import OpenAIClient


@contextlib.contextmanager
def suppress_stderr():
    """Suppress stderr to hide ALSA/JACK warnings."""
    with open(os.devnull, "w") as devnull:
        old_stderr = sys.stderr
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stderr = old_stderr


class AudioRecorder:
    """Audio recorder for capturing microphone input."""

    def __init__(self):
        self.chunk = 1024
        if PYAUDIO_AVAILABLE:
            self.format = pyaudio.paInt16
        else:
            self.format = None
        self.channels = 1
        self.rate = 44100
        self.recording = False
        self.frames = []
        self.audio = None
        self.stream = None
        self.recording_thread = None
        self.input_device_index = None

    def start_recording(self) -> None:
        """Start audio recording."""
        if self.recording:
            return

        if not PYAUDIO_AVAILABLE:
            raise Exception(
                "PyAudio is not available. Please install it with: pip install pyaudio"
            )

        try:
            with suppress_stderr():
                self.audio = pyaudio.PyAudio()

            # Find a working input device
            if self.input_device_index is None:
                self.input_device_index = self._find_working_input_device()

            # Try to open stream with various configurations
            stream_opened = False
            configs_to_try = [
                # Configuration 1: Default with specific device
                {
                    "format": self.format,
                    "channels": self.channels,
                    "rate": self.rate,
                    "input": True,
                    "input_device_index": self.input_device_index,
                    "frames_per_buffer": self.chunk,
                },
                # Configuration 2: Default device, lower sample rate
                {
                    "format": self.format,
                    "channels": self.channels,
                    "rate": 16000,
                    "input": True,
                    "frames_per_buffer": self.chunk,
                },
                # Configuration 3: Mono, even lower sample rate
                {
                    "format": self.format,
                    "channels": 1,
                    "rate": 8000,
                    "input": True,
                    "frames_per_buffer": self.chunk,
                },
            ]

            for i, config in enumerate(configs_to_try):
                try:
                    with suppress_stderr():
                        self.stream = self.audio.open(**config)
                    # Update our settings to match what worked
                    if i > 0:  # If we had to fall back
                        self.rate = config["rate"]
                        self.channels = config["channels"]
                    stream_opened = True
                    break
                except Exception as e:
                    if i == len(configs_to_try) - 1:  # Last attempt
                        raise e
                    continue

            if not stream_opened:
                raise Exception("Could not open audio stream with any configuration")

            self.recording = True
            self.frames = []
            self.recording_thread = threading.Thread(
                target=self._record_audio, daemon=True
            )
            self.recording_thread.start()

        except Exception:
            self._cleanup()
            error_msg = f"Failed to start audio recording: {e}"
            if "ALSA" in str(e) or "jack" in str(e).lower():
                error_msg += "\n\nLinux audio troubleshooting:\n"
                error_msg += "1. Install ALSA dev packages: sudo apt-get install libasound2-dev\n"
                error_msg += "2. Check audio devices: arecord -l\n"
                error_msg += (
                    "3. Test microphone: arecord -d 3 test.wav && aplay test.wav\n"
                )
                error_msg += "4. Try PulseAudio: pulseaudio --start"
            raise

    def stop_recording(self) -> str:
        """Stop recording and return path to recorded audio file."""
        if not self.recording:
            raise Exception("Recording is not active")

        self.recording = False

        if self.recording_thread:
            self.recording_thread.join(timeout=2.0)

        try:
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_path = temp_file.name
            temp_file.close()

            wf = wave.open(temp_path, "wb")
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.audio.get_sample_size(self.format))
            wf.setframerate(self.rate)
            wf.writeframes(b"".join(self.frames))
            wf.close()

            self._cleanup()
            return temp_path

        except Exception:
            self._cleanup()
            raise

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.recording

    def _record_audio(self) -> None:
        """Internal method to record audio in separate thread."""
        try:
            while self.recording and self.stream:
                try:
                    data = self.stream.read(self.chunk, exception_on_overflow=False)
                    self.frames.append(data)
                except Exception as e:
                    # Try to continue recording even if we get occasional read errors
                    if "Input overflowed" in str(e):
                        continue
                    else:
                        self.recording = False
                        break
        except Exception:
            self.recording = False

    def _cleanup(self) -> None:
        """Clean up audio resources."""
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        if self.audio:
            try:
                self.audio.terminate()
            except Exception:
                pass
            self.audio = None

        self.frames = []

    def _find_working_input_device(self) -> Optional[int]:
        """Find a working audio input device."""
        if not self.audio:
            return None

        try:
            device_count = self.audio.get_device_count()

            # First, try to find the default input device
            try:
                default_device = self.audio.get_default_input_device_info()
                if default_device["maxInputChannels"] > 0:
                    return default_device["index"]
            except:
                pass

            # If no default, scan all devices for one that supports input
            for i in range(device_count):
                try:
                    device_info = self.audio.get_device_info_by_index(i)
                    if device_info["maxInputChannels"] > 0:
                        # Test if this device actually works
                        try:
                            with suppress_stderr():
                                test_stream = self.audio.open(
                                    format=self.format,
                                    channels=1,
                                    rate=self.rate,
                                    input=True,
                                    input_device_index=i,
                                    frames_per_buffer=1024,
                                )
                                test_stream.close()
                            return i
                        except:
                            continue
                except:
                    continue

            return None

        except Exception:
            return None


class SpeechToTextService:
    """Service for speech-to-text functionality."""

    def __init__(self, api_key: str, base_url: str, transcribe_model: str):
        print("transcibe", transcribe_model)
        self.openai_client = OpenAIClient(api_key, base_url)
        self.recorder = AudioRecorder()
        self.transcribe_model = transcribe_model
        self.recording_started_callback: Optional[Callable[[], None]] = None
        self.recording_stopped_callback: Optional[Callable[[], None]] = None
        self.transcription_callbacks: Dict[str, Dict] = {}
        self.error_callback: Optional[Callable[[str], None]] = None
        self.current_handler_name: Optional[str] = None

    def set_recording_started_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for when recording starts."""
        self.recording_started_callback = callback

    def set_recording_stopped_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for when recording stops."""
        self.recording_stopped_callback = callback

    def add_transcription_callback(
        self,
        callback: Callable[[str, float], None],
        handler_name: Optional[str] = None,
        run_always: bool = False,
    ) -> Callable[[], None]:
        """Add a transcription callback.

        Args:
            callback: Function to call when transcription is complete (receives transcription and duration)
            handler_name: Name of the handler (mutually exclusive with run_always)
            run_always: Whether to run for all recordings (mutually exclusive with handler_name)

        Returns:
            Function to remove this callback
        """
        if handler_name is not None and run_always:
            raise ValueError("handler_name and run_always are mutually exclusive")

        if handler_name is None and not run_always:
            raise ValueError(
                "Either handler_name must be provided or run_always must be True"
            )

        callback_id = str(uuid.uuid4())
        self.transcription_callbacks[callback_id] = {
            "callback": callback,
            "handler_name": handler_name,
            "run_always": run_always,
        }

        def remove_callback():
            self.transcription_callbacks.pop(callback_id, None)

        return remove_callback

    def set_error_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for error handling."""
        self.error_callback = callback

    def toggle_recording(self, handler_name: Optional[str] = None) -> None:
        """Toggle recording state - start if stopped, stop if started."""
        if self.recorder.is_recording():
            self.stop_recording()
        else:
            self.start_recording(handler_name)

    def start_recording(self, handler_name: Optional[str] = None) -> None:
        """Start audio recording.

        Args:
            handler_name: Name of the handler for targeted callback execution
        """
        try:
            self.current_handler_name = handler_name
            self.recorder.start_recording()
            if self.recording_started_callback:
                self.recording_started_callback()
        except Exception as e:
            error_msg = f"Failed to start recording: {e}"
            if self.error_callback:
                self.error_callback(error_msg)
            else:
                raise

    def stop_recording(self) -> None:
        """Stop recording and start transcription."""
        try:
            if not self.recorder.is_recording():
                return

            audio_file_path = self.recorder.stop_recording()

            if self.recording_stopped_callback:
                self.recording_stopped_callback()

            threading.Thread(
                target=self._transcribe_async,
                args=(audio_file_path, self.current_handler_name),
                daemon=True,
            ).start()

        except Exception as e:
            error_msg = f"Failed to stop recording: {e}"
            if self.error_callback:
                self.error_callback(error_msg)
            else:
                raise

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.recorder.is_recording()

    def _transcribe_async(
        self, audio_file_path: str, handler_name: Optional[str] = None
    ) -> None:
        """Transcribe audio file asynchronously."""
        try:
            start_time = time.time()
            transcription = self.openai_client.transcribe_audio_file(
                audio_file_path, self.transcribe_model
            )
            transcription_duration = time.time() - start_time

            try:
                os.unlink(audio_file_path)
            except:
                pass

            if transcription:
                self._execute_transcription_callbacks(
                    transcription, transcription_duration, handler_name
                )

        except Exception as e:
            try:
                os.unlink(audio_file_path)
            except:
                pass

            error_msg = f"Transcription failed: {e}"
            if self.error_callback:
                self.error_callback(error_msg)

    def _execute_transcription_callbacks(
        self,
        transcription: str,
        transcription_duration: float,
        handler_name: Optional[str] = None,
    ) -> None:
        """Execute appropriate transcription callbacks based on handler_name."""
        for callback_info in self.transcription_callbacks.values():
            should_execute = False

            if callback_info["run_always"]:
                should_execute = True
            elif (
                handler_name is not None
                and callback_info["handler_name"] == handler_name
            ):
                should_execute = True
            elif handler_name is None and callback_info["handler_name"] is None:
                should_execute = True

            if should_execute:
                try:
                    callback_info["callback"](transcription, transcription_duration)
                except Exception as e:
                    error_msg = f"Transcription callback failed: {e}"
                    if self.error_callback:
                        self.error_callback(error_msg)
