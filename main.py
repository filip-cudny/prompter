#!/usr/bin/env python3
"""Entry point for the Prompter application."""

import sys
from app.application import PrompterApp
from modules.utils.system import is_macos


def main():
    """Main entry point."""
    import argparse

    if is_macos():
        from AppKit import NSBundle
        info = NSBundle.mainBundle().infoDictionary()
        info["LSUIElement"] = "1"

    parser = argparse.ArgumentParser(description="Prompter PyQt5 Application")
    parser.add_argument("--config", "-c", help="Configuration file path")
    args = parser.parse_args()

    try:
        app = PrompterApp(args.config)
        return app.run()
    except KeyboardInterrupt:
        print("\nService stopped by user")
        return 0
    except Exception as e:
        print(f"Service error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
