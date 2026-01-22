"""PyInstaller hook for pynput - collects platform-specific backends."""

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("pynput")
