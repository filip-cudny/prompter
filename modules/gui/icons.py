"""SVG icon helper module using Lucide icons."""

from PyQt5.QtCore import QByteArray, QSize, Qt
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer


# Lucide icon SVG templates (viewBox 0 0 24 24, stroke-based)
# Icons use currentColor for stroke, which we replace with the specified color
LUCIDE_ICONS = {
    "copy": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
        <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
    </svg>""",
    "delete": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 6 6 18"/>
        <path d="m6 6 12 12"/>
    </svg>""",
    "info": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h6"/>
        <path d="m21 3-9 9"/>
        <path d="M15 3h6v6"/>
    </svg>""",
    "edit": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>
        <path d="m15 5 4 4"/>
    </svg>""",
    "undo": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 7v6h6"/>
        <path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/>
    </svg>""",
    "redo": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 7v6h-6"/>
        <path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3l3 2.7"/>
    </svg>""",
}

# Color constants matching the app's color scheme
ICON_COLOR_NORMAL = "#888888"
ICON_COLOR_HOVER = "#aaaaaa"
ICON_COLOR_DISABLED = "#555555"


def create_icon(name: str, color: str = ICON_COLOR_NORMAL, size: int = 16) -> QIcon:
    """Create a QIcon from a Lucide SVG icon.

    Args:
        name: Icon name (copy, delete, info, edit, undo, redo)
        color: Hex color string for the icon stroke
        size: Icon size in pixels

    Returns:
        QIcon with the rendered SVG
    """
    if name not in LUCIDE_ICONS:
        raise ValueError(f"Unknown icon: {name}")

    svg_template = LUCIDE_ICONS[name]
    svg_data = svg_template.replace("currentColor", color)

    # Render SVG to QPixmap
    renderer = QSvgRenderer(QByteArray(svg_data.encode()))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return QIcon(pixmap)


def create_icon_pixmap(name: str, color: str = ICON_COLOR_NORMAL, size: int = 16) -> QPixmap:
    """Create a QPixmap from a Lucide SVG icon.

    Args:
        name: Icon name (copy, delete, info, edit, undo, redo)
        color: Hex color string for the icon stroke
        size: Icon size in pixels

    Returns:
        QPixmap with the rendered SVG
    """
    if name not in LUCIDE_ICONS:
        raise ValueError(f"Unknown icon: {name}")

    svg_template = LUCIDE_ICONS[name]
    svg_data = svg_template.replace("currentColor", color)

    renderer = QSvgRenderer(QByteArray(svg_data.encode()))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return pixmap
