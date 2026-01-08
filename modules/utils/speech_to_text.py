"""Minimal speech-to-text service without numpy/scipy dependencies."""

import array
import os
import tempfile
import threading
import time
import uuid
import wave
from typing import Callable, Dict, Optional

try:
    import sounddevice as sd

    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False

from core.openai_service import OpenAiService


class AudioRecorder:
    """Audio recorder for capturing microphone input."""

    def __init__(self):
        self.channels = 1
        self.rate = 44100
        self.recording = False
        self.frames = []
        self.stream = None
        self.input_device_index = None

    def start_recording(self) -> None:
        """Start audio recording."""
        if self.recording:
            return

        if not SOUNDDEVICE_AVAILABLE:
            raise Exception(
                "sounddevice is not available. Please install it with: pip install sounddevice"
            )

        try:
            if self.input_device_index is None:
                self.input_device_index = self._find_working_input_device()

            rates_to_try = [44100, 48000, 16000, 8000]

            for rate in rates_to_try:
                try:
                    sd.check_input_settings(
                        device=self.input_device_index,
                        channels=self.channels,
                        samplerate=rate,
                    )
                    self.rate = rate
                    break
                except Exception as e:
                    if rate == rates_to_try[-1]:
                        raise Exception(
                            f"Could not find working audio configuration: {e}"
                        ) from e
                    continue

            self.recording = True
            self.frames = []

            self.stream = sd.InputStream(
                device=self.input_device_index,
                channels=self.channels,
                samplerate=self.rate,
                callback=self._audio_callback,
                dtype="int16",
            )
            self.stream.start()

        except Exception as e:
            self._cleanup()
            error_msg = f"Failed to start audio recording: {e}"
            if "ALSA" in str(e) or "jack" in str(e).lower():
                error_msg += "\n\nLinux audio troubleshooting:\n"
                error_msg += "1. Install ALSA dev packages: sudo apt-get install libasound2-dev\n"
                error_msg += "2. Check audio devices: python -c 'import sounddevice; print(sounddevice.query_devices())'\n"
                error_msg += "3. Test microphone: python -c 'import sounddevice; sounddevice.rec(44100, samplerate=44100, channels=1)'\n"
                error_msg += "4. Try PulseAudio: pulseaudio --start"
            raise Exception(error_msg) from e

    def stop_recording(self) -> str:
        """Stop recording and return path to recorded audio file."""
        if not self.recording:
            raise Exception("Recording is not active")

        self.recording = False

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        try:
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_path = temp_file.name
            temp_file.close()

            with wave.open(temp_path, "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)
                wf.setframerate(self.rate)

                if self.frames:
                    audio_data = array.array("h")
                    for frame in self.frames:
                        if hasattr(frame, "flatten"):
                            audio_data.extend(frame.flatten())
                        else:
                            audio_data.extend(frame)
                    wf.writeframes(audio_data.tobytes())

            self._cleanup()
            return temp_path

        except Exception:
            self._cleanup()
            raise

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.recording

    def _audio_callback(self, indata, _frame_count, _time_info, status):
        """Callback function for continuous audio input stream."""
        if status:
            print(f"Audio input status: {status}")

        if self.recording:
            self.frames.append(indata.copy())

    def _cleanup(self) -> None:
        """Clean up audio resources."""
        self.recording = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        self.frames = []

    def _find_working_input_device(self) -> Optional[int]:
        """Find a working audio input device."""
        try:
            devices = sd.query_devices()

            try:
                default_device = sd.default.device[0]
                if default_device is not None:
                    device_info = sd.query_devices(default_device)
                    if device_info["max_input_channels"] > 0:
                        return default_device
            except Exception:
                pass

            for i, device_info in enumerate(devices):
                if device_info["max_input_channels"] > 0:
                    try:
                        sd.check_input_settings(
                            device=i, channels=1, samplerate=self.rate
                        )
                        return i
                    except Exception:
                        continue

            return None

        except Exception:
            return None


class SpeechToTextService:
    """Minimal speech-to-text service without numpy/scipy dependencies."""

    def __init__(self, openai_service: OpenAiService):
        self.openai_service = openai_service
        self.recorder = AudioRecorder()
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
            transcription = self.openai_service.transcribe_audio_file(
                audio_file_path, "speech_to_text"
            )
            transcription_duration = time.time() - start_time

            try:
                os.unlink(audio_file_path)
            except Exception:
                pass

            if transcription:
                self._execute_transcription_callbacks(
                    transcription, transcription_duration, handler_name
                )

        except Exception as e:
            try:
                os.unlink(audio_file_path)
            except Exception:
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
