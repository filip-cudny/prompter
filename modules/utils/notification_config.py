"""Notification configuration and settings helpers.

This module is separate from notifications.py to avoid circular imports.
"""

from typing import Dict, Any

NOTIFICATION_ICON_MONOCHROME_COLOR = "#1a1a1a"
NOTIFICATION_BG_COLOR = "#FFFFFF"

NOTIFICATION_TYPES = {
    "success": {
        "icon": "circle-check",
        "icon_color": "#43803e",
    },
    "error": {
        "icon": "circle-x",
        "icon_color": "#c94a4a",
    },
    "info": {
        "icon": "info",
        "icon_color": "#6A7D93",
    },
    "warning": {
        "icon": "circle-alert",
        "icon_color": "#b8860b",
    },
}

DEFAULT_NOTIFICATION_SETTINGS: Dict[str, Any] = {
    "events": {
        "prompt_execution_success": True,
        "prompt_execution_cancel": True,
        "speech_recording_start": True,
        "speech_recording_stop": True,
        "speech_transcription_success": True,
        "context_saved": True,
        "context_set": True,
        "context_append": True,
        "context_cleared": True,
        "clipboard_copy": True,
        "image_added": True,
        "prompt_execution_in_progress": True,
    },
    "background_colors": {
        "success": "#FFFFFF",
        "error": "#FFFFFF",
        "info": "#FFFFFF",
        "warning": "#FFFFFF",
    },
    "monochromatic_notification_icons": True,
    "opacity": 0.8,
}


def get_notification_settings() -> Dict[str, Any]:
    """Get notification settings from config service."""
    try:
        from modules.utils.config import ConfigService

        config_service = ConfigService()
        settings_data = config_service.get_settings_data()
        return settings_data.get("notifications", DEFAULT_NOTIFICATION_SETTINGS)
    except Exception:
        return DEFAULT_NOTIFICATION_SETTINGS


def is_notification_enabled(event_name: str) -> bool:
    """Check if a notification event is enabled in settings.

    Error notifications are always enabled regardless of settings.
    """
    settings = get_notification_settings()
    events = settings.get("events", DEFAULT_NOTIFICATION_SETTINGS["events"])
    return events.get(event_name, True)


def get_background_color(notification_type: str) -> str:
    """Get background color for a notification type from settings."""
    settings = get_notification_settings()
    bg_colors = settings.get(
        "background_colors", DEFAULT_NOTIFICATION_SETTINGS["background_colors"]
    )
    return bg_colors.get(notification_type, NOTIFICATION_BG_COLOR)


def is_monochromatic_mode() -> bool:
    """Check if monochromatic icon mode is enabled."""
    settings = get_notification_settings()
    return settings.get(
        "monochromatic_notification_icons",
        DEFAULT_NOTIFICATION_SETTINGS["monochromatic_notification_icons"],
    )


def get_notification_opacity() -> float:
    """Get the notification window opacity from settings."""
    settings = get_notification_settings()
    return settings.get("opacity", DEFAULT_NOTIFICATION_SETTINGS["opacity"])
