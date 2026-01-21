#!/usr/bin/env python3
"""Entry point for the Promptheus application."""

import sys
import logging
from app.application import PromtheusApp
from modules.utils.system import is_macos


def setup_logging(debug: bool = False) -> None:
    """Configure logging for the application."""
    log_level = logging.DEBUG if debug else logging.WARNING
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    handlers = [logging.StreamHandler()]

    if debug:
        # Add file handler in debug mode
        file_handler = logging.FileHandler("promptheus-debug.log")
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers,
    )


def main():
    """Main entry point."""
    import argparse

    if is_macos():
        from AppKit import NSBundle

        info = NSBundle.mainBundle().infoDictionary()
        info["LSUIElement"] = "1"

    parser = argparse.ArgumentParser(description="Promptheus Application")
    parser.add_argument("--config", "-c", help="Configuration file path")
    parser.add_argument(
        "--debug", "-d", action="store_true", help="Enable debug mode with detailed logging"
    )
    args = parser.parse_args()

    setup_logging(debug=args.debug)

    if args.debug:
        logging.info("Debug mode enabled - logging to promptheus-debug.log")

    try:
        app = PromtheusApp(args.config)
        return app.run()
    except KeyboardInterrupt:
        print("\nService stopped by user")
        return 0
    except Exception as e:
        print(f"Service error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
