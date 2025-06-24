#!/usr/bin/env python3
"""Entry point for the prompt store application."""

import sys
import os

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.pyqt_application import PromptStoreApp


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Prompt Store PyQt5 Application")
    parser.add_argument("--config", "-c", help="Configuration file path")
    args = parser.parse_args()

    try:
        app = PromptStoreApp(args.config)
        return app.run()
    except KeyboardInterrupt:
        print("\nService stopped by user")
        return 0
    except Exception as e:
        print(f"Service error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
