"""SVG loading with caching."""

import os
from typing import Dict, List

_SVG_DIR = os.path.join(os.path.dirname(__file__), "svg")

_svg_content_cache: Dict[str, str] = {}


def get_svg_path(name: str) -> str:
    """Return the file path for an SVG icon.

    Args:
        name: Icon name (without .svg extension)

    Returns:
        Absolute path to the SVG file
    """
    return os.path.join(_SVG_DIR, f"{name}.svg")


def get_svg_content(name: str) -> str:
    """Load SVG content with caching.

    Args:
        name: Icon name (without .svg extension)

    Returns:
        SVG content as string

    Raises:
        ValueError: If icon file doesn't exist
    """
    if name in _svg_content_cache:
        return _svg_content_cache[name]

    path = get_svg_path(name)
    if not os.path.exists(path):
        raise ValueError(f"Unknown icon: {name}")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    _svg_content_cache[name] = content
    return content


def get_available_icons() -> List[str]:
    """List all available icon names.

    Returns:
        List of icon names (without .svg extension)
    """
    if not os.path.exists(_SVG_DIR):
        return []

    return [
        os.path.splitext(f)[0]
        for f in os.listdir(_SVG_DIR)
        if f.endswith(".svg")
    ]
