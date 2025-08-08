"""Cross-platform clipboard utilities."""

import subprocess
import platform
import base64
import io
import logging
from typing import Optional, Tuple
from core.exceptions import ClipboardError
from core.interfaces import ClipboardManager

logger = logging.getLogger(__name__)


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

    def has_image(self) -> bool:
        """Check if the clipboard contains an image."""
        try:
            if self.platform == "Darwin":
                return self._has_image_macos()
            elif self.platform == "Linux":
                return self._has_image_linux()
            elif self.platform == "Windows":
                return self._has_image_windows()
            else:
                return False
        except Exception:
            return False

    def _has_image_macos(self) -> bool:
        """Check if clipboard contains an image on macOS."""
        try:
            from AppKit import NSPasteboard

            pb = NSPasteboard.generalPasteboard()
            logger.debug("Checking macOS clipboard for images using pyobjc")

            # Check for common image types using UTI strings
            image_types = ["public.png", "public.jpeg", "public.tiff", "com.adobe.pdf"]
            for image_type in image_types:
                if pb.dataForType_(image_type):
                    logger.debug(f"Found image of type: {image_type}")
                    return True
            logger.debug("No images found in macOS clipboard")
            return False
        except ImportError as e:
            logger.debug(f"pyobjc not available: {e}, falling back to pngpaste")
            # Fallback to pngpaste if pyobjc not available
            try:
                result = subprocess.run(
                    ["pngpaste", "-"], capture_output=True, timeout=5
                )
                has_image = result.returncode == 0
                logger.debug(f"pngpaste result: {has_image}")
                return has_image
            except FileNotFoundError:
                logger.debug("pngpaste not found")
                return False
        except Exception as e:
            logger.error(f"Error checking for images on macOS: {e}")
            return False

    def _get_image_data_macos(self) -> Optional[Tuple[str, str]]:
        """Get image data from clipboard on macOS."""
        try:
            from AppKit import NSPasteboard
            from PIL import Image

            logger.debug(
                "Attempting to get image data from macOS clipboard using pyobjc"
            )
            pb = NSPasteboard.generalPasteboard()

            # Try different image formats in order of preference using UTI strings
            formats = [
                ("public.png", "image/png"),
                ("public.jpeg", "image/jpeg"),
                ("public.tiff", "image/tiff"),
            ]

            for pasteboard_type, format_name in formats:
                logger.debug(f"Trying format: {format_name}")
                data = pb.dataForType_(pasteboard_type)
                if data:
                    logger.debug(
                        f"Found image data for {format_name}, size: {len(data.bytes())} bytes"
                    )
                    # Convert NSData to bytes and then to PIL Image
                    image_bytes = data.bytes()
                    image = Image.open(io.BytesIO(image_bytes))

                    # Convert to PNG for consistent format
                    png_buffer = io.BytesIO()
                    image.save(png_buffer, format="PNG")
                    png_data = png_buffer.getvalue()

                    # Encode as base64
                    image_data = base64.b64encode(png_data).decode("utf-8")
                    logger.debug(
                        f"Successfully converted image to base64, length: {len(image_data)}"
                    )
                    return (image_data, "image/png")

            logger.debug("No image data found in any supported format")
            return None

        except ImportError as e:
            logger.debug(f"pyobjc/PIL not available: {e}, falling back to pngpaste")
            # Fallback to pngpaste if pyobjc/PIL not available
            try:
                result = subprocess.run(
                    ["pngpaste", "-"], capture_output=True, timeout=10
                )
                if result.returncode == 0 and result.stdout:
                    logger.debug(
                        f"pngpaste successful, data size: {len(result.stdout)} bytes"
                    )
                    image_data = base64.b64encode(result.stdout).decode("utf-8")
                    return (image_data, "image/png")
                else:
                    logger.debug(
                        f"pngpaste failed with return code: {result.returncode}"
                    )
            except FileNotFoundError:
                logger.debug("pngpaste command not found")
            except Exception as e:
                logger.debug(f"pngpaste failed with exception: {e}")

            return None
        except Exception as e:
            logger.error(f"Error getting image data from macOS clipboard: {e}")
            return None

    def _has_image_linux(self) -> bool:
        """Check if clipboard contains an image on Linux."""
        logger.debug("Checking Linux clipboard for images")
        # Try xclip first as it has reliable TARGETS support
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                targets = result.stdout.lower()
                logger.debug(f"xclip targets: {targets}")
                has_image = any(
                    fmt in targets
                    for fmt in ["image/png", "image/jpeg", "image/gif", "image/bmp"]
                )
                logger.debug(f"xclip image detection result: {has_image}")
                return has_image
        except FileNotFoundError:
            logger.debug("xclip not found, trying xsel with manual detection")

        # Fallback: try to detect images by attempting to retrieve them with xsel
        try:
            image_formats = ["image/png", "image/jpeg", "image/gif", "image/bmp"]
            for mime_type in image_formats:
                result = subprocess.run(
                    ["xsel", "--clipboard", "--output", "--target", mime_type],
                    capture_output=True,
                    timeout=2,
                )
                if result.returncode == 0 and result.stdout:
                    logger.debug(f"xsel detected image format: {mime_type}")
                    return True
            logger.debug("xsel found no image formats")
            return False
        except FileNotFoundError:
            logger.debug("xsel not found either")

        logger.debug("No clipboard tools available for image detection")
        return False

    def _get_image_data_linux(self) -> Optional[Tuple[str, str]]:
        """Get image data from clipboard on Linux."""
        image_formats = [
            ("image/png", "png"),
            ("image/jpeg", "jpeg"),
            ("image/gif", "gif"),
            ("image/bmp", "bmp"),
        ]

        logger.debug("Attempting to get image data from Linux clipboard")

        # Try xclip first as it's more reliable
        for mime_type, ext in image_formats:
            logger.debug(f"Trying to get image data for MIME type: {mime_type}")
            try:
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-t", mime_type, "-o"],
                    capture_output=True,
                    timeout=5,
                )

                if result.returncode == 0 and result.stdout:
                    logger.debug(
                        f"Successfully retrieved image data using xclip, size: {len(result.stdout)} bytes"
                    )
                    image_data = base64.b64encode(result.stdout).decode("utf-8")
                    return (image_data, mime_type)
                else:
                    logger.debug(
                        f"xclip failed for {mime_type}, return code: {result.returncode}"
                    )
            except FileNotFoundError:
                break  # Try xsel for all formats if xclip not found

        # Fallback to xsel if xclip is not available
        try:
            subprocess.run(["xsel", "--version"], capture_output=True, timeout=2)
            logger.debug("xclip not found, trying xsel")
            for mime_type, ext in image_formats:
                logger.debug(
                    f"Trying to get image data for MIME type: {mime_type} using xsel"
                )
                try:
                    result = subprocess.run(
                        ["xsel", "--clipboard", "--output", "--target", mime_type],
                        capture_output=True,
                        timeout=5,
                    )

                    if result.returncode == 0 and result.stdout:
                        logger.debug(
                            f"Successfully retrieved image data using xsel, size: {len(result.stdout)} bytes"
                        )
                        image_data = base64.b64encode(result.stdout).decode("utf-8")
                        return (image_data, mime_type)
                    else:
                        logger.debug(
                            f"xsel failed for {mime_type}, return code: {result.returncode}"
                        )
                except Exception as e:
                    logger.debug(f"xsel error for {mime_type}: {e}")
                    continue
        except FileNotFoundError:
            logger.debug("xsel not found either")

        logger.debug("No image data could be retrieved from Linux clipboard")
        return None

    def _has_image_windows(self) -> bool:
        """Check if clipboard contains an image on Windows."""
        try:
            from PyQt5.QtWidgets import QApplication

            app = QApplication.instance()
            if app is None:
                app = QApplication([])

            clipboard = app.clipboard()
            mime_data = clipboard.mimeData()

            return mime_data.hasImage()
        except Exception:
            return False

    def _get_image_data_windows(self) -> Optional[Tuple[str, str]]:
        """Get image data from clipboard on Windows."""
        try:
            from PyQt5.QtWidgets import QApplication
            from PyQt5.QtCore import QBuffer, QIODevice
            from PyQt5.QtGui import QPixmap

            app = QApplication.instance()
            if app is None:
                app = QApplication([])

            clipboard = app.clipboard()
            mime_data = clipboard.mimeData()

            if mime_data.hasImage():
                pixmap = QPixmap(clipboard.pixmap())
                if not pixmap.isNull():
                    buffer = QBuffer()
                    buffer.open(QIODevice.WriteOnly)
                    pixmap.save(buffer, "PNG")
                    image_data = base64.b64encode(buffer.data()).decode("utf-8")
                    return (image_data, "image/png")

        except Exception:
            pass

        return None

    def get_image_data(self) -> Optional[Tuple[str, str]]:
        """Get image data from clipboard as (base64_data, media_type) tuple."""
        try:
            if self.platform == "Darwin":
                return self._get_image_data_macos()
            elif self.platform == "Linux":
                return self._get_image_data_linux()
            elif self.platform == "Windows":
                return self._get_image_data_windows()
            else:
                return None
        except Exception:
            return None

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
        # try:
        #     result = subprocess.run(
        #         ["xclip", "-selection", "clipboard", "-o"],
        #         capture_output=True,
        #         text=True,
        #         timeout=5,
        #     )
        #     if result.returncode != 0:
        #         raise ClipboardError(f"xclip failed: {result.stderr}")
        #     return result.stdout
        # except FileNotFoundError:
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
        except FileNotFoundError:
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
            except FileNotFoundError as exc:
                raise ClipboardError(
                    "Neither xsel nor xclip found. Please install one."
                ) from exc

    def _set_content_linux(self, content: str) -> bool:
        """Set clipboard content on Linux."""
        try:
            result = subprocess.run(
                ["xsel", "--clipboard", "--input"],
                input=content,
                text=True,
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except FileNotFoundError:
            try:
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=content,
                    text=True,
                    capture_output=True,
                    timeout=5,
                )
                return result.returncode == 0
            except FileNotFoundError as exc:
                raise ClipboardError(
                    "Neither xsel nor xclip found. Please install one."
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
