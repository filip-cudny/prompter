#!/usr/bin/env python3
"""Entry point for the Promptheus application."""

import fcntl
import logging
import os
import sys

from app.application import PromtheusApp
from modules.utils.paths import get_debug_log_path, get_error_log_path, get_settings_file, get_user_config_dir
from modules.utils.system import is_macos


def get_debug_mode_from_settings() -> bool:
    """Read debug_mode setting from settings.json."""
    import json

    settings_file = get_settings_file()
    if settings_file.exists():
        try:
            with open(settings_file, encoding="utf-8") as f:
                settings = json.load(f)
            return settings.get("debug_mode", False)
        except Exception:
            pass
    return False


def acquire_instance_lock():
    """Acquire a lock to prevent multiple instances.

    Returns:
        File descriptor if lock acquired, None if another instance is running.
    """
    lock_file = get_user_config_dir() / "promptheus.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    fd = open(lock_file, "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd.write(str(os.getpid()))
        fd.flush()
        return fd
    except OSError:
        fd.close()
        return None


def setup_logging(debug: bool = False) -> None:
    """Configure logging for the application.

    Args:
        debug: Whether to enable debug mode (verbose logging to debug.log)

    Logging behavior:
        - Errors (ERROR level and above) are always logged to error.log
        - Debug mode logs all levels (DEBUG+) to debug.log
        - Console output shows WARNING+ normally, DEBUG+ in debug mode
    """
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if debug else logging.WARNING)
    console_handler.setFormatter(formatter)

    error_handler = logging.FileHandler(get_error_log_path())
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    handlers = [console_handler, error_handler]

    if debug:
        debug_handler = logging.FileHandler(get_debug_log_path())
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(formatter)
        handlers.append(debug_handler)

    for handler in handlers:
        root_logger.addHandler(handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


IPC_ACTIONS = {
    "toggle_menu": "open_context_menu",
    "execute_active": "execute_active_prompt",
    "speech_toggle": "speech_to_text_toggle",
    "set_context": "set_context_value",
    "append_context": "append_context_value",
    "clear_context": "clear_context",
}


def _handle_ipc_command(args) -> int | None:
    for attr, action in IPC_ACTIONS.items():
        value = getattr(args, attr, None)
        if value is None:
            continue
        if isinstance(value, bool) and not value:
            continue

        from modules.ipc.socket_client import send_ipc_command
        from modules.utils.cursor import get_cursor_position_for_ipc

        cursor_pos = get_cursor_position_for_ipc()

        payload = None
        if isinstance(value, str):
            payload = value

        if payload:
            pass

        success = send_ipc_command(action, cursor_pos)
        return 0 if success else 1

    return None


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Promptheus Application")
    parser.add_argument("--config", "-c", help="Configuration file path")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode with detailed logging")

    ipc_group = parser.add_argument_group("IPC commands (send to running instance)")
    ipc_group.add_argument(
        "--toggle-menu", "--menu", dest="toggle_menu", action="store_true", default=None,
        help="Open the context menu at cursor position",
    )
    ipc_group.add_argument(
        "--execute-active", dest="execute_active", action="store_true", default=None,
        help="Execute the active prompt",
    )
    ipc_group.add_argument(
        "--speech-toggle", dest="speech_toggle", action="store_true", default=None,
        help="Toggle speech-to-text recording",
    )
    ipc_group.add_argument(
        "--set-context", dest="set_context", action="store_true", default=None,
        help="Set context value",
    )
    ipc_group.add_argument(
        "--append-context", dest="append_context", action="store_true", default=None,
        help="Append to context value",
    )
    ipc_group.add_argument(
        "--clear-context", dest="clear_context", action="store_true", default=None,
        help="Clear context value",
    )

    args = parser.parse_args()

    ipc_result = _handle_ipc_command(args)
    if ipc_result is not None:
        return ipc_result

    if is_macos():
        from AppKit import NSBundle

        info = NSBundle.mainBundle().infoDictionary()
        info["LSUIElement"] = "1"

    lock = acquire_instance_lock()
    if lock is None:
        print("Another instance of Promptheus is already running")
        return 0

    debug_enabled = (
        args.debug
        or os.environ.get("PROMPTHEUS_DEBUG", "").lower() in ("1", "true", "yes")
        or get_debug_mode_from_settings()
    )
    setup_logging(debug=debug_enabled)

    if debug_enabled:
        logging.info("Debug mode enabled - logging to debug.log")

    try:
        app = PromtheusApp(args.config)
        return app.run()
    except KeyboardInterrupt:
        print("\nService stopped by user")
        return 0
    except Exception as e:
        print(f"Service error: {e}")
        return 1
    finally:
        if lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_UN)
                lock.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
