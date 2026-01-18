"""SVG icon module with caching.

Public API:
    create_icon(name, color, size) -> QIcon
    create_icon_pixmap(name, color, size) -> QPixmap
    get_svg_path(name) -> str
    get_svg_content(name) -> str
    get_available_icons() -> List[str]

Color constants:
    ICON_COLOR_NORMAL
    ICON_COLOR_HOVER
    ICON_COLOR_DISABLED
    DISABLED_OPACITY

Stylesheet paths:
    SVG_CHEVRON_DOWN
    SVG_CHEVRON_UP
"""

from .constants import (
    DISABLED_OPACITY,
    ICON_COLOR_DISABLED,
    ICON_COLOR_HOVER,
    ICON_COLOR_NORMAL,
)
from .loader import get_available_icons, get_svg_content, get_svg_path
from .renderer import create_icon, create_icon_pixmap

SVG_CHEVRON_DOWN = get_svg_path("chevron-down")
SVG_CHEVRON_UP = get_svg_path("chevron-up")

__all__ = [
    "create_icon",
    "create_icon_pixmap",
    "get_svg_path",
    "get_svg_content",
    "get_available_icons",
    "ICON_COLOR_NORMAL",
    "ICON_COLOR_HOVER",
    "ICON_COLOR_DISABLED",
    "DISABLED_OPACITY",
    "SVG_CHEVRON_DOWN",
    "SVG_CHEVRON_UP",
]
