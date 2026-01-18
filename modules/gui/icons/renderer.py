"""Icon rendering with caching."""

from functools import lru_cache

from PyQt5.QtCore import QByteArray, QSize, Qt
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QApplication

from .constants import ICON_COLOR_NORMAL
from .loader import get_svg_content


def _get_dpr() -> float:
    app = QApplication.instance()
    return app.devicePixelRatio() if app else 1.0


@lru_cache(maxsize=256)
def _render_pixmap(name: str, color: str, size: int, dpr: float) -> QPixmap:
    """Render SVG to pixmap with caching.

    Cache key is (name, color, size, dpr) tuple.
    """
    svg_content = get_svg_content(name)
    svg_data = svg_content.replace("currentColor", color)

    physical_size = int(size * dpr)

    renderer = QSvgRenderer(QByteArray(svg_data.encode()))
    pixmap = QPixmap(QSize(physical_size, physical_size))
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

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


def create_icon_pixmap(
    name: str, color: str = ICON_COLOR_NORMAL, size: int = 16
) -> QPixmap:
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
