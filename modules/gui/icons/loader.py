"""SVG loading with caching."""

import base64
import os

_SVG_DIR = os.path.join(os.path.dirname(__file__), "svg")

_svg_content_cache: dict[str, str] = {}
_svg_data_url_cache: dict[str, str] = {}


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

    with open(path, encoding="utf-8") as f:
        content = f.read()

    _svg_content_cache[name] = content
    return content


def get_available_icons() -> list[str]:
    """List all available icon names.

    Returns:
        List of icon names (without .svg extension)
    """
    if not os.path.exists(_SVG_DIR):
        return []

    return [os.path.splitext(f)[0] for f in os.listdir(_SVG_DIR) if f.endswith(".svg")]


def get_svg_data_url(name: str, color: str) -> str:
    """Return a data URL for an SVG icon with color applied.

    Data URLs can be used in Qt stylesheets where raw SVG paths
    would render currentColor as black.

    Args:
        name: Icon name (without .svg extension)
        color: Hex color string to replace currentColor with

    Returns:
        Data URL string (data:image/svg+xml;base64,...)
    """
    cache_key = f"{name}:{color}"
    if cache_key in _svg_data_url_cache:
        return _svg_data_url_cache[cache_key]

    svg_content = get_svg_content(name)
    svg_colored = svg_content.replace("currentColor", color)
    encoded = base64.b64encode(svg_colored.encode()).decode()
    data_url = f"data:image/svg+xml;base64,{encoded}"

    _svg_data_url_cache[cache_key] = data_url
    return data_url
