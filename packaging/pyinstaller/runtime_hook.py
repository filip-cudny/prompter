"""PyInstaller runtime hook for Promptheus.

This hook runs before the main application and sets up the environment
for proper operation in frozen mode.
"""

import os
import sys


def setup_environment():
    """Configure environment for frozen application."""
    if not getattr(sys, "frozen", False):
        return

    bundle_dir = sys._MEIPASS

    os.chdir(bundle_dir)

    if sys.platform == "darwin":
        qt_plugins = os.path.join(bundle_dir, "PySide6", "Qt", "plugins")
        if os.path.exists(qt_plugins):
            os.environ["QT_PLUGIN_PATH"] = qt_plugins

    elif sys.platform.startswith("linux"):
        if "XDG_RUNTIME_DIR" not in os.environ:
            runtime_dir = f"/run/user/{os.getuid()}"
            if os.path.exists(runtime_dir):
                os.environ["XDG_RUNTIME_DIR"] = runtime_dir

        qt_plugins = os.path.join(bundle_dir, "PySide6", "Qt", "plugins")
        if os.path.exists(qt_plugins):
            os.environ["QT_PLUGIN_PATH"] = qt_plugins


setup_environment()
