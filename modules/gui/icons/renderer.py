"""Icon rendering with caching."""

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

from .constants import ICON_COLOR_NORMAL
from .loader import get_svg_content


def _get_dpr() -> float:
    app = QApplication.instance()
    return app.devicePixelRatio() if app else 1.0


@lru_cache(maxsize=256)
def _render_pixmap_raw(name: str, color: str, physical_size: int) -> QPixmap:
    """Render SVG to pixmap at exact physical size (no dpr scaling)."""
    svg_content = get_svg_content(name)
    svg_data = svg_content.replace("currentColor", color)

    renderer = QSvgRenderer(QByteArray(svg_data.encode()))
    pixmap = QPixmap(QSize(physical_size, physical_size))
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

    return pixmap


def _render_pixmap(name: str, color: str, size: int, dpr: float) -> QPixmap:
    """Render SVG to pixmap with dpr scaling."""
    physical_size = int(size * dpr)
    pixmap = _render_pixmap_raw(name, color, physical_size)
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def create_icon(name: str, color: str = ICON_COLOR_NORMAL, size: int = 16) -> QIcon:
    """Create a QIcon from an SVG icon.

    Args:
        name: Icon name (without .svg extension)
        color: Hex color string for the icon stroke
        size: Icon size in pixels

    Returns:
        QIcon with the rendered SVG
    """
    dpr = _get_dpr()
    pixmap = _render_pixmap(name, color, size, dpr)
    return QIcon(pixmap)


def create_icon_pixmap(name: str, color: str = ICON_COLOR_NORMAL, size: int = 16) -> QPixmap:
    """Create a QPixmap from an SVG icon.

    Args:
        name: Icon name (without .svg extension)
        color: Hex color string for the icon stroke
        size: Icon size in pixels

    Returns:
        QPixmap with the rendered SVG
    """
    dpr = _get_dpr()
    return _render_pixmap(name, color, size, dpr)


def create_composite_icon(
    left_name: str,
    right_name: str,
    color: str = ICON_COLOR_NORMAL,
    size: int = 16,
    separator: str = "",
    separator_padding: int = 2,
) -> QIcon:
    """Create a composite icon with two icons side-by-side.

    Args:
        left_name: Icon name for left icon
        right_name: Icon name for right icon
        color: Hex color string for icon strokes
        size: Size of each individual icon in pixels
        separator: Optional text to render between icons (e.g., "&")
        separator_padding: Padding on each side of separator in pixels

    Returns:
        QIcon with both icons rendered side-by-side
    """
    dpr = _get_dpr()
    physical_size = int(size * dpr)
    padding_px = int(separator_padding * dpr)

    font = QFont()
    font.setPixelSize(int(size * 0.7 * dpr))
    metrics = QFontMetrics(font)
    text_width = metrics.horizontalAdvance(separator) if separator else 0
    separator_width = text_width + (padding_px * 2) if separator else 0

    total_width = (physical_size * 2) + separator_width
    pixmap = QPixmap(total_width, physical_size)
    pixmap.fill(Qt.transparent)

    left_pixmap = _render_pixmap_raw(left_name, color, physical_size)
    right_pixmap = _render_pixmap_raw(right_name, color, physical_size)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.drawPixmap(0, 0, left_pixmap)

    if separator:
        painter.setFont(font)
        painter.setPen(QColor(color))
        text_rect = QRect(physical_size, 0, separator_width, physical_size)
        painter.drawText(text_rect, Qt.AlignCenter, separator)

    painter.drawPixmap(physical_size + separator_width, 0, right_pixmap)
    painter.end()

    pixmap.setDevicePixelRatio(dpr)
    return QIcon(pixmap)
