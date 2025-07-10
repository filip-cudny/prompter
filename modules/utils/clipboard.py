"""Cross-platform clipboard utilities."""

import subprocess
import platform
from core.exceptions import ClipboardError
from core.interfaces import ClipboardManager


class SystemClipboardManager(ClipboardManager):
    """Cross-platform clipboard manager implementation."""

    def __init__(self):
        self.platform = platform.system()

    def get_content(self) -> str:
        """Get the current clipboard content."""
        try:
            if self.platform == "Darwin":
                return self._get_content_macos()
            elif self.platform == "Linux":
                return self._get_content_linux()
            elif self.platform == "Windows":
                return self._get_content_windows()
            else:
                raise ClipboardError(f"Unsupported platform: {self.platform}")
        except Exception as e:
            raise ClipboardError(f"Failed to get clipboard content: {str(e)}")

    def set_content(self, content: str) -> bool:
        """Set the clipboard content. Returns True if successful."""
        try:
            if self.platform == "Darwin":
                return self._set_content_macos(content)
            elif self.platform == "Linux":
                return self._set_content_linux(content)
            elif self.platform == "Windows":
                return self._set_content_windows(content)
            else:
                raise ClipboardError(f"Unsupported platform: {self.platform}")
        except Exception as e:
            raise ClipboardError(f"Failed to set clipboard content: {str(e)}")

    def is_empty(self) -> bool:
        """Check if the clipboard is empty."""
        try:
            content = self.get_content()
            return not content.strip()
        except ClipboardError:
            return True

    def _get_content_macos(self) -> str:
        """Get clipboard content on macOS."""
        result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            raise ClipboardError(f"pbpaste failed: {result.stderr}")
        return result.stdout

    def _set_content_macos(self, content: str) -> bool:
        """Set clipboard content on macOS."""
        result = subprocess.run(
            ["pbcopy"], input=content, text=True, capture_output=True, timeout=5
        )
        return result.returncode == 0

    def _get_content_linux(self) -> str:
        """Get clipboard content on Linux."""
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                raise ClipboardError(f"xclip failed: {result.stderr}")
            return result.stdout
        except FileNotFoundError:
            try:
                result = subprocess.run(
                    ["xsel", "--clipboard", "--output"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode != 0:
                    raise ClipboardError(f"xsel failed: {result.stderr}")
                return result.stdout
            except FileNotFoundError as exc:
                raise ClipboardError(
                    "Neither xclip nor xsel found. Please install one."
                ) from exc

    def _set_content_linux(self, content: str) -> bool:
        """Set clipboard content on Linux."""
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=content,
                text=True,
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except FileNotFoundError:
            try:
                result = subprocess.run(
                    ["xsel", "--clipboard", "--input"],
                    input=content,
                    text=True,
                    capture_output=True,
                    timeout=5,
                )
                return result.returncode == 0
            except FileNotFoundError as exc:
                raise ClipboardError(
                    "Neither xclip nor xsel found. Please install one."
                ) from exc

    def _get_content_windows(self) -> str:
        """Get clipboard content on Windows."""
        try:
            from PyQt5.QtWidgets import QApplication
            from PyQt5.QtCore import QMimeData

            app = QApplication.instance()
            if app is None:
                app = QApplication([])

            clipboard = app.clipboard()
            mime_data = clipboard.mimeData()

            if mime_data.hasText():
                return mime_data.text()
            else:
                return ""
        except Exception as e:
            raise ClipboardError(f"Failed to get Windows clipboard: {str(e)}")

    def _set_content_windows(self, content: str) -> bool:
        """Set clipboard content on Windows."""
        try:
            from PyQt5.QtWidgets import QApplication

            app = QApplication.instance()
            if app is None:
                app = QApplication([])

            clipboard = app.clipboard()
            clipboard.setText(content)
            return True
        except Exception:
            return False
