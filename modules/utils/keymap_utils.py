"""Keymap utilities for testing and demonstration."""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from .keymap import KeymapManager, load_keymaps_from_settings
from .keymap_actions import execute_keymap_action, get_available_actions
from .config import load_settings_file

logger = logging.getLogger(__name__)


def test_keymap_configuration(settings_path: Path) -> bool:
    """Test keymap configuration from settings file."""
    try:
        logger.info(f"Testing keymap configuration from: {settings_path}")

        keymap_manager = load_keymaps_from_settings(settings_path)

        logger.info("Keymap configuration loaded successfully")

        active_keymaps = keymap_manager.get_active_keymaps()
        logger.info(f"Found {len(active_keymaps)} active keymap contexts")

        all_bindings = keymap_manager.get_all_bindings()
        logger.info(f"Total active bindings: {len(all_bindings)}")

        for binding in all_bindings:
            logger.info(f"  {binding.key_combination} -> {binding.action}")

        return True

    except Exception as e:
        logger.error(f"Keymap configuration test failed: {e}")
        return False


def print_keymap_summary(settings_path: Path) -> None:
    """Print a summary of keymap configuration."""
    try:
        keymap_manager = load_keymaps_from_settings(settings_path)

        print("\n=== Keymap Configuration Summary ===")
        print(f"Settings file: {settings_path}")

        active_keymaps = keymap_manager.get_active_keymaps()
        print(f"\nActive contexts: {len(active_keymaps)}")

        for context in active_keymaps:
            print(f"  - {context.context}")

        all_bindings = keymap_manager.get_all_bindings()
        print(f"\nActive key bindings: {len(all_bindings)}")

        for binding in all_bindings:
            print(f"  {binding.key_combination:<20} -> {binding.action}")

        available_actions = get_available_actions()
        print(f"\nAvailable actions: {len(available_actions)}")

        for action_name, description in available_actions.items():
            print(f"  {action_name:<25} - {description}")

    except Exception as e:
        print(f"Error: {e}")


def simulate_key_press(
    settings_path: Path, key_combination: str, context: Optional[Dict[str, Any]] = None
) -> bool:
    """Simulate a key press and execute the associated action."""
    try:
        keymap_manager = load_keymaps_from_settings(settings_path)

        action = keymap_manager.find_action_for_key(key_combination)
        if action is None:
            logger.warning(f"No action found for key combination: {key_combination}")
            return False

        logger.info(
            f"Executing action '{action}' for key combination '{key_combination}'"
        )
        return execute_keymap_action(action, context)

    except Exception as e:
        logger.error(f"Error simulating key press: {e}")
        return False


def get_bindings_for_action(settings_path: Path, action_name: str) -> List[str]:
    """Get all key combinations bound to a specific action."""
    try:
        keymap_manager = load_keymaps_from_settings(settings_path)
        return keymap_manager.get_bindings_for_action(action_name)

    except Exception as e:
        logger.error(f"Error getting bindings for action: {e}")
        return []


def validate_settings_keymaps(settings_path: Path) -> bool:
    """Validate keymap configuration in settings file."""
    try:
        settings_data = load_settings_file(settings_path)

        if "keymaps" not in settings_data:
            logger.warning("No keymaps section found in settings")
            return True

        keymaps = settings_data["keymaps"]
        if not isinstance(keymaps, list):
            logger.error("Keymaps must be a list")
            return False

        for i, keymap in enumerate(keymaps):
            if not isinstance(keymap, dict):
                logger.error(f"Keymap at index {i} must be a dictionary")
                return False

            if "context" not in keymap:
                logger.error(f"Keymap at index {i} missing 'context' field")
                return False

            if "bindings" not in keymap:
                logger.error(f"Keymap at index {i} missing 'bindings' field")
                return False

            if not isinstance(keymap["bindings"], dict):
                logger.error(f"Bindings at index {i} must be a dictionary")
                return False

        logger.info("Keymap validation passed")
        return True

    except Exception as e:
        logger.error(f"Keymap validation failed: {e}")
        return False


def interactive_keymap_test(settings_path: Path) -> None:
    """Interactive keymap testing utility."""
    try:
        print("=== Interactive Keymap Test ===\n")

        if not validate_settings_keymaps(settings_path):
            print("Settings validation failed!")
            return

        keymap_manager = load_keymaps_from_settings(settings_path)

        while True:
            print("\nOptions:")
            print("1. Show keymap summary")
            print("2. Test key combination")
            print("3. Show bindings for action")
            print("4. List available actions")
            print("5. Exit")

            choice = input("\nEnter your choice (1-5): ").strip()

            if choice == "1":
                print_keymap_summary(settings_path)

            elif choice == "2":
                key_combo = input(
                    "Enter key combination (e.g., 'ctrl-space'): "
                ).strip()
                if key_combo:
                    success = simulate_key_press(settings_path, key_combo)
                    print(f"Action execution: {'Success' if success else 'Failed'}")

            elif choice == "3":
                action = input("Enter action name: ").strip()
                if action:
                    bindings = get_bindings_for_action(settings_path, action)
                    if bindings:
                        print(f"Key bindings for '{action}': {', '.join(bindings)}")
                    else:
                        print(f"No bindings found for action '{action}'")

            elif choice == "4":
                actions = get_available_actions()
                print("\nAvailable actions:")
                for name, desc in actions.items():
                    print(f"  {name}: {desc}")

            elif choice == "5":
                print("Exiting...")
                break

            else:
                print("Invalid choice. Please try again.")

    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python keymap_utils.py <settings_file_path>")
        sys.exit(1)

    settings_file = Path(sys.argv[1])
    if not settings_file.exists():
        print(f"Settings file not found: {settings_file}")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)
    interactive_keymap_test(settings_file)
