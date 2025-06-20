#!/usr/bin/env python3
"""GUI application for displaying and selecting prompts from a context menu."""

import tkinter as tk
from tkinter import messagebox
import platform

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
        self.prompts = [
            "prompt1",
            "prompt2",
            "prompt3",
            "prompt4",
            "prompt5"
        ]
        self.root = None
        self.menu = None

    def create_context_menu(self):
        self.root = tk.Tk()
        self.root.withdraw()

        self.menu = tk.Menu(self.root, tearoff=0)

        for prompt in self.prompts:
            self.menu.add_command(
                label=prompt,
                command=lambda p=prompt: self.on_prompt_selected(p)
            )

        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self.on_exit)

    def on_prompt_selected(self, prompt):
        messagebox.showinfo("Selected", f"You selected: {prompt}")
        self.root.quit()

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
