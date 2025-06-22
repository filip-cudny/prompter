#!/usr/bin/env python3
"""Entry point for the prompt store application."""

import sys
import os

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.application import PromptStoreApp


def main():
    """Main entry point."""
    try:
        app = PromptStoreApp()
        app.run()
    except KeyboardInterrupt:
        print("\nService stopped by user")
    except Exception as e:
        print(f"Service error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()