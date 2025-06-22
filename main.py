#!/usr/bin/env python3
"""Background GUI application for displaying and selecting prompts from a context menu."""

import os
import tkinter as tk
from tkinter import messagebox
import platform
import sys
import signal
import time
import threading
import subprocess
from dotenv import load_dotenv
from pynput import keyboard
from pynput.keyboard import Key
from api import PromptStoreAPI, APIError, create_user_message


class PromptStoreGUI:
    def __init__(self):
        load_dotenv()

        self.api_key = os.getenv("API_KEY")
        self.base_url = os.getenv("BASE_URL")

        if not self.api_key or not self.base_url:
            raise ValueError("API_KEY and BASE_URL must be set in .env file")

        self.api = PromptStoreAPI(self.base_url, self.api_key)
        self.prompts = []
        self.presets = []
        self.root = None
        self.menu = None
        self.is_executing = False
        self.running = False
        self.listener = None
        self.hotkey_pressed = False
        self.pressed_keys = set()
        self.show_menu_flag = False

        self.load_data()

    def get_clipboard_content(self):
        """Get clipboard content using platform-specific methods"""
        try:
            if platform.system() == "Darwin":
                result = subprocess.run(["pbpaste"], capture_output=True, text=True)
                return result.stdout
            elif platform.system() == "Linux":
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-o"],
                    capture_output=True,
                    text=True,
                )
                return result.stdout
            elif platform.system() == "Windows":
                import tkinter as tk

                temp_root = tk.Tk()
                temp_root.withdraw()
                try:
                    content = temp_root.clipboard_get()
                    temp_root.destroy()
                    return content
                except tk.TclError:
                    temp_root.destroy()
                    return ""
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return ""

    def set_clipboard_content(self, content):
        """Set clipboard content using platform-specific methods"""
        try:
            if platform.system() == "Darwin":
                result = subprocess.run(
                    ["pbcopy"], input=content, text=True, capture_output=True
                )
                return result.returncode == 0
            elif platform.system() == "Linux":
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=content,
                    text=True,
                    capture_output=True,
                )
                return result.returncode == 0
            elif platform.system() == "Windows":
                import tkinter as tk

                temp_root = tk.Tk()
                temp_root.withdraw()
                try:
                    temp_root.clipboard_clear()
                    temp_root.clipboard_append(content)
                    temp_root.update()
                    temp_root.destroy()
                    return True
                except tk.TclError:
                    temp_root.destroy()
                    return False
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return False

    def load_data(self):
        try:
            data = self.api.get_all_data()
            self.prompts = data["prompts"]
            self.presets = data["presets"]

            self.prompt_id_to_name = {
                prompt["id"]: prompt["name"] for prompt in self.prompts
            }
        except APIError as e:
            messagebox.showerror("API Error", f"Failed to load data: {str(e)}")
            self.prompts = []
            self.presets = []
            self.prompt_id_to_name = {}

    def create_context_menu(self):
        if self.menu:
            self.menu.destroy()

        self.menu = tk.Menu(self.root, tearoff=0)

        if not self.prompts and not self.presets:
            self.menu.add_command(
                label="No prompts or presets available", state="disabled"
            )
        else:
            for prompt in self.prompts:
                prompt_name = prompt.get("name", "Unnamed Prompt")
                self.menu.add_command(
                    label=prompt_name,
                    command=lambda p=prompt: self.on_prompt_selected(p),
                )

            for preset in self.presets:
                preset_name = preset.get("presetName", "Unnamed Preset")
                prompt_id = preset.get("promptId")
                prompt_name = self.prompt_id_to_name.get(prompt_id, "Unknown Prompt")
                display_name = f"{preset_name} ({prompt_name})"
                self.menu.add_command(
                    label=display_name,
                    command=lambda p=preset: self.on_preset_selected(p),
                    foreground="gray",
                )

        self.menu.add_separator()
        self.menu.add_command(label="Refresh", command=self.on_refresh)
        self.menu.add_command(label="Exit", command=self.on_exit)

    def on_prompt_selected(self, prompt):
        self.is_executing = True
        prompt_id = prompt.get("id")

        if not prompt_id:
            messagebox.showerror("Error", "Invalid prompt data")
            self.is_executing = False
            return

        try:
            clipboard_content = self.get_clipboard_content()

            if not clipboard_content.strip():
                messagebox.showwarning("Warning", "Clipboard is empty")
                self.is_executing = False
                return

            user_message = create_user_message(clipboard_content)
            result = self.api.execute_prompt(prompt_id, [user_message])

            content = result.get("content", "No response content")

            if not self.set_clipboard_content(content):
                messagebox.showerror(
                    "Clipboard Error",
                    f"Prompt executed but failed to copy result to clipboard.\n\nResult:\n{
                        content
                    }",
                )

        except APIError as e:
            messagebox.showerror(
                "Execution Error", f"Failed to execute prompt: {str(e)}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error: {str(e)}")

        self.is_executing = False

    def on_preset_selected(self, preset):
        self.is_executing = True
        preset_id = preset.get("id")
        prompt_id = preset.get("promptId")

        if not preset_id or not prompt_id:
            messagebox.showerror("Error", "Invalid preset data")
            self.is_executing = False
            return

        try:
            clipboard_content = self.get_clipboard_content()

            if not clipboard_content.strip():
                messagebox.showwarning("Warning", "Clipboard is empty")
                self.is_executing = False
                return

            user_message = create_user_message(clipboard_content)
            result = self.api.execute_prompt_with_preset(
                prompt_id, preset_id, [user_message]
            )

            content = result.get("content", "No response content")

            if not self.set_clipboard_content(content):
                messagebox.showerror(
                    "Clipboard Error",
                    f"Preset executed but failed to copy result to clipboard.\n\nResult:\n{
                        content
                    }",
                )

        except APIError as e:
            messagebox.showerror(
                "Execution Error", f"Failed to execute preset: {str(e)}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error: {str(e)}")

        self.is_executing = False

    def on_refresh(self):
        self.load_data()

    def on_exit(self):
        self.stop()

    def get_cursor_position(self):
        """Get absolute cursor position across all displays"""
        try:
            from pynput.mouse import Controller

            mouse = Controller()
            x, y = mouse.position
            return int(x), int(y)
        except Exception:
            pass

        # Fallback to tkinter method
        if self.root:
            self.root.update_idletasks()
            return self.root.winfo_pointerx(), self.root.winfo_pointery()

        return 0, 0

    def show_menu_at_cursor(self):
        self.create_context_menu()
        x, y = self.get_cursor_position()

        # Move root window to cursor position to enable cross-display menu
        if self.root:
            try:
                self.root.geometry(f"1x1+{x}+{y}")
                self.root.update_idletasks()
            except tk.TclError:
                pass

        try:
            self.menu.tk_popup(x, y)
        except tk.TclError as e:
            print(f"Menu popup failed at {x}, {y}: {e}")
            try:
                self.menu.tk_popup(x + 10, y + 10)
            except tk.TclError:
                pass

    def on_hotkey_press(self):
        """Handle hotkey press event"""
        if not self.hotkey_pressed:
            self.hotkey_pressed = True
            print("Shift+F1 pressed - showing context menu")
            self.show_menu_flag = True

            threading.Timer(1.0, self.reset_hotkey_flag).start()

    def reset_hotkey_flag(self):
        """Reset hotkey flag to prevent rapid firing"""
        self.hotkey_pressed = False

    def is_shift_f1_pressed(self):
        """Check if Shift+F1 combination is pressed"""
        shift_pressed = (
            Key.shift in self.pressed_keys
            or Key.shift_l in self.pressed_keys
            or Key.shift_r in self.pressed_keys
        )
        f1_pressed = Key.f1 in self.pressed_keys

        return shift_pressed and f1_pressed

    def on_press(self, key):
        """Handle key press events"""
        self.pressed_keys.add(key)

        if self.is_shift_f1_pressed():
            self.on_hotkey_press()

    def on_release(self, key):
        """Handle key release events"""
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)

    def setup_hotkey_listener(self):
        """Setup global hotkey listener for Shift+F1"""
        try:
            self.listener = keyboard.Listener(
                on_press=self.on_press, on_release=self.on_release, suppress=False
            )
        except Exception as e:
            print(f"Error setting up hotkey listener: {e}")
            raise

    def setup_tkinter_root(self):
        """Setup hidden tkinter root"""
        try:
            self.root = tk.Tk()
            self.root.withdraw()
            self.root.attributes("-alpha", 0.01)
        except Exception as e:
            print(f"Warning: Could not setup tkinter root: {e}")
            self.root = None

    def signal_handler(self, signum, _):
        """Handle shutdown signals"""
        print(f"\nReceived signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def check_macos_permissions(self):
        """Check if accessibility permissions are granted on macOS"""
        if platform.system() == "Darwin":
            try:
                result = subprocess.run(
                    [
                        "python",
                        "-c",
                        "from pynput import keyboard; listener = keyboard.Listener(lambda key: None); listener.start(); listener.stop()",
                    ],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode != 0:
                    print("Warning: Accessibility permissions may be required on macOS")
                    print(
                        "Go to System Preferences > Security & Privacy > Privacy > Accessibility"
                    )
                    print("and grant access to Terminal or your Python application")
            except Exception:
                pass

    def start(self):
        """Start the background service"""
        print("Starting Prompt Store Background Service...")
        print("Hotkey: Shift+F1")
        print("Press Ctrl+C to stop\n")

        self.check_macos_permissions()

        self.running = True

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        self.setup_tkinter_root()
        self.setup_hotkey_listener()

        try:
            self.listener.start()
        except Exception as e:
            print(f"Error starting hotkey listener: {e}")
            return

        try:
            while self.running:
                if self.root and self.root.winfo_exists():
                    self.root.update()

                    if self.show_menu_flag:
                        self.show_menu_flag = False
                        self.show_menu_at_cursor()

                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nShutting down...")
        except Exception as e:
            print(f"Service error: {e}")
        finally:
            self.stop()

    def stop(self):
        """Stop the background service"""
        self.running = False

        if self.listener:
            self.listener.stop()

        if self.root:
            try:
                self.root.quit()
                self.root.destroy()
            except tk.TclError:
                pass


def main():
    try:
        app = PromptStoreGUI()
        app.start()
    except KeyboardInterrupt:
        print("\nService stopped by user")
    except Exception as e:
        print(f"Service error: {e}")
    finally:
        if "app" in locals():
            app.stop()


if __name__ == "__main__":
    main()
