#!/usr/bin/env python3
"""GUI application for displaying and selecting prompts from a context menu."""

import os
import tkinter as tk
from tkinter import messagebox
import platform
from dotenv import load_dotenv
from api import PromptStoreAPI, APIError, create_user_message
try:
    if platform.system() == "Windows":
        import ctypes
        from ctypes import wintypes
    elif platform.system() == "Darwin":
        from AppKit import NSEvent, NSScreen
        import subprocess
    elif platform.system() == "Linux":
        from Xlib import display
        import subprocess
except ImportError:
    import subprocess

class PromptStoreGUI:
    def __init__(self):
        load_dotenv()

        self.api_key = os.getenv('API_KEY')
        self.base_url = os.getenv('BASE_URL')

        if not self.api_key or not self.base_url:
            raise ValueError("API_KEY and BASE_URL must be set in .env file")

        self.api = PromptStoreAPI(self.base_url, self.api_key)
        self.prompts = []
        self.root = None
        self.menu = None
        self.is_executing = False

        self.load_prompts()

    def get_clipboard_content(self):
        """Get clipboard content using platform-specific methods"""
        try:
            if platform.system() == "Darwin":  # macOS
                result = subprocess.run(['pbpaste'], capture_output=True, text=True)
                return result.stdout
            elif platform.system() == "Linux":
                result = subprocess.run(['xclip', '-selection', 'clipboard', '-o'], 
                                      capture_output=True, text=True)
                return result.stdout
            elif platform.system() == "Windows":
                import tkinter as tk
                root = tk.Tk()
                root.withdraw()
                try:
                    content = root.clipboard_get()
                    root.destroy()
                    return content
                except tk.TclError:
                    root.destroy()
                    return ""
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        return ""

    def set_clipboard_content(self, content):
        """Set clipboard content using platform-specific methods"""
        try:
            if platform.system() == "Darwin":  # macOS
                result = subprocess.run(['pbcopy'], input=content, text=True, capture_output=True)
                return result.returncode == 0
            elif platform.system() == "Linux":
                result = subprocess.run(['xclip', '-selection', 'clipboard'], input=content, text=True, capture_output=True)
                return result.returncode == 0
            elif platform.system() == "Windows":
                import tkinter as tk
                root = tk.Tk()
                root.withdraw()
                try:
                    root.clipboard_clear()
                    root.clipboard_append(content)
                    root.update()
                    root.destroy()
                    return True
                except tk.TclError:
                    root.destroy()
                    return False
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        return False

    def load_prompts(self):
        try:
            self.prompts = self.api.get_prompts()
        except APIError as e:
            messagebox.showerror("API Error", f"Failed to load prompts: {str(e)}")
            self.prompts = []

    def create_context_menu(self):
        self.root = tk.Tk()
        self.root.withdraw()
        
        # Make window focusable but invisible
        self.root.overrideredirect(True)
        self.root.attributes('-alpha', 0.01)  # Nearly transparent
        self.root.attributes('-topmost', True)

        self.menu = tk.Menu(self.root, tearoff=0)

        if not self.prompts:
            self.menu.add_command(label="No prompts available", state='disabled')
        else:
            for prompt in self.prompts:
                prompt_name = prompt.get('name', 'Unnamed Prompt')
                self.menu.add_command(
                    label=prompt_name,
                    command=lambda p=prompt: self.on_prompt_selected(p)
                )

        self.menu.add_separator()
        self.menu.add_command(label="Refresh", command=self.on_refresh)
        self.menu.add_command(label="Exit", command=self.on_exit)

    def on_prompt_selected(self, prompt):
        self.is_executing = True
        prompt_name = prompt.get('name', 'Unnamed Prompt')
        prompt_id = prompt.get('id')

        if not prompt_id:
            messagebox.showerror("Error", "Invalid prompt data")
            self.is_executing = False
            return

        try:
            clipboard_content = self.get_clipboard_content()
            
            if not clipboard_content.strip():
                messagebox.showwarning("Warning", "Clipboard is empty")
                self.is_executing = False
                self.root.quit()
                return

            user_message = create_user_message(clipboard_content)
            result = self.api.execute_prompt(prompt_id, [user_message])

            content = result.get('content', 'No response content')
            
            if not self.set_clipboard_content(content):
                messagebox.showerror("Clipboard Error", f"Prompt executed but failed to copy result to clipboard.\n\nResult:\n{content}")

        except APIError as e:
            messagebox.showerror("Execution Error", f"Failed to execute prompt: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error: {str(e)}")

        self.is_executing = False
        self.root.quit()

    def on_refresh(self):
        self.load_prompts()
        self.root.quit()
        self.run()

    def check_menu_active(self):
        """Check if menu is still active, quit if not and not executing"""
        if not self.is_executing:
            try:
                # If menu is no longer posted, quit the application
                if not self.menu.winfo_ismapped():
                    self.root.quit()
                    return
            except tk.TclError:
                # Menu was destroyed or is no longer accessible
                self.root.quit()
                return
        
        # Schedule next check
        self.root.after(100, self.check_menu_active)

    def on_exit(self):
        self.root.quit()

    def get_cursor_position(self):
        # Simple approach: just get the cursor position directly
        self.root.update_idletasks()
        return self.root.winfo_pointerx(), self.root.winfo_pointery()

    def show_menu_at_cursor(self):
        x, y = self.get_cursor_position()

        # Position the root window at cursor
        self.root.geometry(f"10x10+{x}+{y}")
        self.root.deiconify()  # Show the window
        self.root.focus_force()
        self.root.update()

        try:
            self.menu.tk_popup(x, y)
            # Start checking if menu is still active
            self.root.after(100, self.check_menu_active)
        except tk.TclError as e:
            print(f"Menu popup failed at {x}, {y}: {e}")
            try:
                self.menu.tk_popup(x + 10, y + 10)
                self.root.after(100, self.check_menu_active)
            except tk.TclError:
                self.root.quit()

    def run(self):
        self.create_context_menu()
        self.root.after(100, self.show_menu_at_cursor)
        self.root.mainloop()
        self.root.destroy()

def main():
    app = PromptStoreGUI()
    app.run()

if __name__ == "__main__":
    main()
