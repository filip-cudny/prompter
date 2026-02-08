"""Temporary image storage service for conversation history."""

import base64
import hashlib
import logging
import shutil
import time
from pathlib import Path

from modules.utils.paths import get_temp_images_dir

logger = logging.getLogger(__name__)


def initialize() -> None:
    """Initialize temp image storage - clears all existing images on app startup."""
    temp_dir = get_temp_images_dir()
    if temp_dir.exists():
        try:
            shutil.rmtree(temp_dir)
            logger.debug("Cleared temp conversation images directory")
        except Exception as e:
            logger.warning(f"Failed to clear temp images directory: {e}")
    temp_dir.mkdir(parents=True, exist_ok=True)


def save_image(base64_data: str, media_type: str) -> str | None:
    """Save base64 image data to temp storage.

    Args:
        base64_data: Base64-encoded image data
        media_type: MIME type (e.g., "image/png", "image/jpeg")

    Returns:
        File path to saved image, or None on failure
    """
    try:
        temp_dir = get_temp_images_dir()
        temp_dir.mkdir(parents=True, exist_ok=True)

        extension = _get_extension_for_media_type(media_type)
        content_hash = hashlib.md5(base64_data.encode()).hexdigest()[:12]
        timestamp = int(time.time() * 1000)
        filename = f"img_{timestamp}_{content_hash}{extension}"

        filepath = temp_dir / filename
        image_bytes = base64.b64decode(base64_data)
        filepath.write_bytes(image_bytes)

        logger.debug(f"Saved temp image: {filepath}")
        return str(filepath)
    except Exception as e:
        logger.error(f"Failed to save temp image: {e}")
        return None


def load_image(filepath: str) -> tuple[str, str] | None:
    """Load image from disk as base64.

    Args:
        filepath: Path to the image file

    Returns:
        Tuple of (base64_data, media_type), or None if file not found
    """
    try:
        path = Path(filepath)
        if not path.exists():
            logger.warning(f"Temp image not found: {filepath}")
            return None

        image_bytes = path.read_bytes()
        base64_data = base64.b64encode(image_bytes).decode("utf-8")
        media_type = _get_media_type_for_extension(path.suffix)

        return base64_data, media_type
    except Exception as e:
        logger.error(f"Failed to load temp image: {e}")
        return None


def cleanup() -> None:
    """Remove all temp images. Called on app shutdown or as needed."""
    temp_dir = get_temp_images_dir()
    if temp_dir.exists():
        try:
            shutil.rmtree(temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)
            logger.debug("Cleaned up temp conversation images")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp images: {e}")


def _get_extension_for_media_type(media_type: str) -> str:
    """Get file extension for a MIME type."""
    extensions = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
    }
    return extensions.get(media_type.lower(), ".png")


def _get_media_type_for_extension(extension: str) -> str:
    """Get MIME type for a file extension."""
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    return media_types.get(extension.lower(), "image/png")
