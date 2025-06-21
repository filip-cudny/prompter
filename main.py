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
    elif platform.system() == "Linux":
        from Xlib import display
except ImportError:
    pass

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

        self.load_prompts()

    def load_prompts(self):
        try:
            self.prompts = self.api.get_prompts()
        except APIError as e:
            messagebox.showerror("API Error", f"Failed to load prompts: {str(e)}")
            self.prompts = []

    def create_context_menu(self):
        self.root = tk.Tk()
        self.root.withdraw()

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
        prompt_name = prompt.get('name', 'Unnamed Prompt')
        prompt_id = prompt.get('id')

        if not prompt_id:
            messagebox.showerror("Error", "Invalid prompt data")
            return

        try:
            sample_message = create_user_message("Hello, this is a test message")
            result = self.api.execute_prompt(prompt_id, [sample_message])

            content = result.get('content', 'No response content')
            messagebox.showinfo("Prompt Result", f"Prompt: {prompt_name}\n\nResult:\n{content}")

        except APIError as e:
            messagebox.showerror("Execution Error", f"Failed to execute prompt: {str(e)}")

        self.root.quit()

    def on_refresh(self):
        self.load_prompts()
        self.root.quit()
        self.run()

    def on_exit(self):
        self.root.quit()

    def get_cursor_position(self):
        # Simple approach: just get the cursor position directly
        self.root.update_idletasks()
        return self.root.winfo_pointerx(), self.root.winfo_pointery()

    def show_menu_at_cursor(self):
        x, y = self.get_cursor_position()

        # Create a reference window at cursor position
        self.root.geometry(f"1x1+{x}+{y}")
        self.root.update()

        try:
            self.menu.tk_popup(x, y)
        except tk.TclError as e:
            print(f"Menu popup failed at {x}, {y}: {e}")
            try:
                # Fallback: show menu at a slight offset
                self.menu.tk_popup(x + 10, y + 10)
            except tk.TclError:
                pass
        finally:
            self.menu.grab_release()

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
