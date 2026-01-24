"""Platform-aware path resolution for frozen and development environments."""

import os
import shutil
import sys
from pathlib import Path


def is_frozen() -> bool:
    """Check if running as a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_bundle_dir() -> Path:
    """Get the bundled resources directory.

    Returns:
        Path to bundle resources (sys._MEIPASS for frozen, cwd for dev)
    """
    if is_frozen():
        return Path(sys._MEIPASS)
    return Path.cwd()


def get_user_config_dir() -> Path:
    """Get user-specific configuration directory.

    Returns:
        - macOS: ~/Library/Application Support/promptheus
        - Linux: ~/.config/promptheus
        - Windows: %APPDATA%/promptheus
    """
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "promptheus"
    elif sys.platform == "win32":
        import os

        return Path(os.environ.get("APPDATA", Path.home())) / "promptheus"
    else:
        return Path.home() / ".config" / "promptheus"


def get_settings_dir() -> Path:
    """Get the settings directory.

    Returns:
        User config dir for frozen apps, ./settings for development
    """
    if is_frozen():
        config_dir = get_user_config_dir()
        _initialize_user_settings(config_dir)
        return config_dir
    return Path("settings")


def get_settings_file() -> Path:
    """Get the path to settings.json."""
    return get_settings_dir() / "settings.json"


def get_env_file() -> Path:
    """Get the path to .env file.

    Returns:
        User config dir .env for frozen, project root .env for development
    """
    if is_frozen():
        config_dir = get_user_config_dir()
        _initialize_user_settings(config_dir)
        return config_dir / ".env"
    return Path(".env")


def get_prompts_dir() -> Path:
    """Get the path to external prompts directory.

    Returns:
        User config dir prompts for frozen, ./prompts for development
    """
    if is_frozen():
        config_dir = get_user_config_dir()
        _initialize_user_settings(config_dir)
        return config_dir / "prompts"
    return Path("prompts")


def get_svg_icons_dir() -> Path:
    """Get the path to SVG icons directory.

    Returns:
        Bundled icons dir for frozen, local path for development
    """
    if is_frozen():
        return get_bundle_dir() / "modules" / "gui" / "icons" / "svg"
    return Path(__file__).parent.parent / "gui" / "icons" / "svg"


def get_root_icon_path(name: str) -> Path:
    """Get path to root-level icon (icon.svg, tray_icon.svg).

    Args:
        name: Icon filename (e.g., 'icon.svg')

    Returns:
        Path to the icon file
    """
    return get_bundle_dir() / name


def get_debug_log_path() -> Path:
    """Get the path to debug.log file.

    Returns platform-appropriate log location and ensures directory exists.
    """
    config_dir = get_user_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "debug.log"


def _initialize_user_settings(config_dir: Path) -> None:
    """Copy settings_example to user config directory on first run.

    Args:
        config_dir: Target configuration directory
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    bundle_dir = get_bundle_dir()

    if not (config_dir / "settings.json").exists():
        settings_example_dir = bundle_dir / "settings_example"
        if settings_example_dir.exists():
            for item in settings_example_dir.iterdir():
                dest = config_dir / item.name
                if item.is_file():
                    shutil.copy2(item, dest)
                elif item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)

        prompts_dir = bundle_dir / "prompts"
        if prompts_dir.exists():
            dest_prompts = config_dir / "prompts"
            shutil.copytree(prompts_dir, dest_prompts, dirs_exist_ok=True)

    env_example = bundle_dir / ".env.example"
    env_dest = config_dir / ".env"
    if env_example.exists() and not env_dest.exists():
        shutil.copy2(env_example, env_dest)
