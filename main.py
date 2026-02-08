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


def main():
    """Main entry point."""
    import argparse

    if is_macos():
        from AppKit import NSBundle

        info = NSBundle.mainBundle().infoDictionary()
        info["LSUIElement"] = "1"

    # Prevent multiple instances using file lock
    lock = acquire_instance_lock()
    if lock is None:
        print("Another instance of Promptheus is already running")
        return 0

    parser = argparse.ArgumentParser(description="Promptheus Application")
    parser.add_argument("--config", "-c", help="Configuration file path")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode with detailed logging")
    args = parser.parse_args()

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
        # Release the lock when done
        if lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_UN)
                lock.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
