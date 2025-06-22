"""Notification utilities using custom tkinter snackbar."""

import tkinter as tk
import queue
from typing import Optional


class NotificationManager:
    """Cross-platform notification manager using tkinter snackbar."""

    def __init__(self, main_root: Optional[tk.Tk] = None):
        self.main_root = main_root
        self.notification_queue = queue.Queue()
        self._processing = False

    def set_main_root(self, root: tk.Tk) -> None:
        """Set the main tkinter root window."""
        self.main_root = root

    def show_success_notification(self, title: str, message: str, prompt_name: Optional[str] = None) -> None:
        """Show a success notification."""
        if prompt_name:
            full_message = f"✔ {title} - {prompt_name}\n{message}"
        else:
            full_message = f"✔ {title}\n{message}"

        self._queue_notification(full_message, "#6B7A4A", 2000)

    def show_error_notification(self, title: str, message: str, prompt_name: Optional[str] = None) -> None:
        """Show an error notification."""
        if prompt_name:
            full_message = f"𐄂 {title} - {prompt_name}\n{message}"
        else:
            full_message = f"𐄂 {title}\n{message}"

        self._queue_notification(full_message, "#9B6B67", 4000)

    def show_info_notification(self, title: str, message: str) -> None:
        """Show an info notification."""
        full_message = f"ⓘ {title}\n{message}"
        self._queue_notification(full_message, "#6A7D93", 2000)

    def _queue_notification(self, message: str, bg_color: str, duration: int) -> None:
        """Queue a notification to be shown on the main thread."""
        try:
            self.notification_queue.put_nowait({
                'message': message,
                'bg_color': bg_color,
                'duration': duration
            })
            self._schedule_process_queue()
        except queue.Full:
            pass

    def _schedule_process_queue(self) -> None:
        """Schedule processing of the notification queue on the main thread."""
        if self.main_root and not self._processing:
            self.main_root.after_idle(self._process_notification_queue)

    def _process_notification_queue(self) -> None:
        """Process notifications from the queue on the main thread."""
        if self._processing:
            return

        self._processing = True

        try:
            while True:
                try:
                    notification = self.notification_queue.get_nowait()
                    self._show_snackbar_main_thread(
                        notification['message'],
                        notification['duration'],
                        notification['bg_color']
                    )
                except queue.Empty:
                    break
        finally:
            self._processing = False

    def _show_snackbar_main_thread(self, msg: str, duration: int = 2000, bg_color: str = "#323232") -> None:
        """Show a snackbar notification on the main thread."""
        try:
            if not self.main_root:
                print(f"ⓘ {msg}")
                return

            snackbar = tk.Toplevel(self.main_root)
            snackbar.overrideredirect(True)
            snackbar.attributes("-topmost", True, "-alpha", 0.85)

            label = tk.Label(
                snackbar,
                text=msg,
                bg=bg_color,
                fg="white",
                font=("Arial", 13),
                padx=24,
                pady=12,
                justify=tk.LEFT
            )
            label.pack()

            snackbar.update_idletasks()
            w = snackbar.winfo_screenwidth()
            h = snackbar.winfo_screenheight()
            sw = label.winfo_reqwidth()
            sh = label.winfo_reqheight()
            x = w - sw - 20
            y = 50
            snackbar.geometry(f"+{x}+{y}")

            def destroy_snackbar():
                try:
                    if snackbar.winfo_exists():
                        snackbar.destroy()
                except tk.TclError:
                    pass

            snackbar.after(duration, destroy_snackbar)

        except Exception as e:
            print(f"Failed to show notification: {e}")
            print(f"🔔 {msg}")

    def is_available(self) -> bool:
        """Check if notifications are available on this platform."""
        return True


def format_execution_time(execution_time: float) -> str:
    """Format execution time for display."""
    if execution_time < 1:
        return f"{execution_time * 1000:.0f}ms"
    else:
        return f"{execution_time:.1f}s"


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text for notification display."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
