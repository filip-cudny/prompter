"""Context menu GUI operations for the prompt store application."""

import tkinter as tk
from typing import List, Optional, Tuple
from core.models import MenuItem, MenuItemType
from core.exceptions import MenuError


class ContextMenu:
    """Pure tkinter context menu operations."""

    def __init__(self, root: Optional[tk.Tk] = None):
        self.root = root
        self.menu: Optional[tk.Menu] = None

    def create_menu(self, items: List[MenuItem]) -> tk.Menu:
        """Create a tkinter menu from menu items."""
        if not self.root:
            raise MenuError("Root window not available")

        if self.menu:
            self.menu.destroy()

        self.menu = tk.Menu(self.root, tearoff=0)

        if not items:
            self.menu.add_command(label="No items available", state="disabled")
            return self.menu

        for i, item in enumerate(items):
            self._add_menu_item(self.menu, item, i)

        return self.menu

    def show_at_position(self, x: int, y: int) -> None:
        """Show the menu at the specified position."""
        if not self.menu:
            raise MenuError("Menu not created")

        try:
            # Create anchor window at cursor position for multi-monitor support
            if self.root:
                self._create_anchor_window(x, y)

            self.menu.tk_popup(x, y)
        except tk.TclError as e:
            # Try with slight offset if position fails
            try:
                self.menu.tk_popup(x + 10, y + 10)
            except tk.TclError:
                raise MenuError(
                    f"Failed to show menu at position {x}, {y}: {e}")

    def _create_anchor_window(self, x: int, y: int) -> None:
        """Create a temporary anchor window to help with multi-monitor positioning."""
        try:
            # Create a temporary window at the target position
            anchor = tk.Toplevel(self.root)
            anchor.geometry(f"1x1+{x}+{y}")
            anchor.withdraw()  # Hide the window
            anchor.update_idletasks()

            # Update root window position to match
            self.root.geometry(f"1x1+{x}+{y}")
            self.root.update_idletasks()

            # Destroy the anchor window
            anchor.destroy()
        except Exception:
            # If anchor window creation fails, just update root position
            try:
                self.root.geometry(f"1x1+{x}+{y}")
                self.root.update_idletasks()
            except Exception:
                pass

    def destroy(self) -> None:
        """Destroy the menu."""
        if self.menu:
            self.menu.destroy()
            self.menu = None

    def _add_menu_item(self, menu: tk.Menu, item: MenuItem, index: int) -> None:
        """Add a menu item to the tkinter menu."""
        # Configure item appearance based on type and style
        config = self._get_item_config(item)

        # Add the command with appropriate state
        menu.add_command(
            label=item.label,
            command=item.action if item.enabled else None,
            **config
        )

        # Add separator after item if requested
        if item.separator_after:
            menu.add_separator()

    def _get_item_config(self, item: MenuItem) -> dict:
        """Get tkinter configuration for a menu item."""
        config = {}

        # Apply style-based configuration
        if item.style:
            if item.style == "gray":
                config["foreground"] = "gray"
            elif item.style == "disabled":
                config["foreground"] = "gray"

        # Apply type-based configuration
        if item.item_type == MenuItemType.PRESET:
            config["foreground"] = "gray"
        elif item.item_type == MenuItemType.HISTORY:
            config["foreground"] = "blue"
        elif item.item_type == MenuItemType.SYSTEM:
            config["foreground"] = "black"

        # Set state and appearance for disabled items
        if not item.enabled:
            config["state"] = "disabled"
            config["foreground"] = "gray"

        return config


class MenuBuilder:
    """Builder for creating context menus from providers."""

    def __init__(self):
        self.items: List[MenuItem] = []
        self.separators: List[int] = []

    def add_items(self, items: List[MenuItem]) -> 'MenuBuilder':
        """Add menu items to the builder."""
        self.items.extend(items)
        return self

    def add_separator(self) -> 'MenuBuilder':
        """Add a separator at the current position."""
        self.separators.append(len(self.items))
        return self

    def add_items_with_separator(self, items: List[MenuItem]) -> 'MenuBuilder':
        """Add menu items with a separator before them."""
        if self.items:  # Only add separator if there are existing items
            self.add_separator()
        self.add_items(items)
        return self

    def build(self) -> List[MenuItem]:
        """Build the final list of menu items with separators."""
        if not self.items:
            return []

        # Mark separator positions in items
        for separator_pos in self.separators:
            if 0 <= separator_pos < len(self.items):
                # Mark the item after separator position
                if separator_pos < len(self.items):
                    # Find the actual item at this position and mark it
                    # This is handled by adding separator_after to the previous item
                    if separator_pos > 0:
                        self.items[separator_pos - 1].separator_after = True

        return self.items

    def clear(self) -> 'MenuBuilder':
        """Clear all items and separators."""
        self.items.clear()
        self.separators.clear()
        return self

    def filter_enabled(self) -> 'MenuBuilder':
        """Remove disabled items from the builder."""
        self.items = [item for item in self.items if item.enabled]
        return self

    def sort_by_label(self) -> 'MenuBuilder':
        """Sort items by label."""
        self.items.sort(key=lambda item: item.label.lower())
        return self

    def group_by_type(self) -> 'MenuBuilder':
        """Group items by type."""
        # Sort items by type, keeping original order within each type
        type_order = {
            MenuItemType.PROMPT: 0,
            MenuItemType.PRESET: 1,
            MenuItemType.HISTORY: 2,
            MenuItemType.SYSTEM: 3,
        }

        self.items.sort(key=lambda item: (
            type_order.get(item.item_type, 999),
            item.label.lower()
        ))
        return self


class MenuPosition:
    """Utility class for calculating menu positions."""

    @staticmethod
    def get_cursor_position() -> Tuple[int, int]:
        """Get the current cursor position with multi-monitor support."""
        import platform

        # Platform-specific cursor position detection for multi-monitor support
        system = platform.system()

        if system == "Darwin":  # macOS
            return MenuPosition._get_cursor_position_macos()
        elif system == "Windows":
            return MenuPosition._get_cursor_position_windows()
        elif system == "Linux":
            return MenuPosition._get_cursor_position_linux()
        else:
            return MenuPosition._get_cursor_position_fallback()

    @staticmethod
    def _get_cursor_position_macos() -> Tuple[int, int]:
        """Get cursor position on macOS with multi-monitor support."""
        try:
            from AppKit import NSEvent, NSScreen

            # Get mouse location in screen coordinates
            loc = NSEvent.mouseLocation()
            x, y = int(loc.x), int(loc.y)

            # macOS uses bottom-left origin, convert to top-left
            try:
                screens = NSScreen.screens()
                if screens:
                    main_screen = screens[0]
                    screen_height = main_screen.frame().size.height
                    y = int(screen_height - y)
            except Exception:
                pass

            return x, y
        except ImportError:
            # AppKit not available, try alternative method
            try:
                import subprocess
                result = subprocess.run(
                    ['cliclick', 'p'], capture_output=True, text=True)
                if result.returncode == 0:
                    coords = result.stdout.strip().split(',')
                    if len(coords) == 2:
                        return int(coords[0]), int(coords[1])
            except Exception:
                pass
        except Exception:
            pass

        return MenuPosition._get_cursor_position_fallback()

    @staticmethod
    def _get_cursor_position_windows() -> Tuple[int, int]:
        """Get cursor position on Windows with multi-monitor support."""
        try:
            import ctypes
            from ctypes import wintypes

            # Check if required Windows API is available
            if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'user32'):
                # Get cursor position using Windows API
                point = wintypes.POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
                return point.x, point.y
        except (ImportError, AttributeError, OSError):
            pass
        except Exception:
            pass

        return MenuPosition._get_cursor_position_fallback()

    @staticmethod
    def _get_cursor_position_linux() -> Tuple[int, int]:
        """Get cursor position on Linux with multi-monitor support."""
        try:
            from Xlib import display

            # Get cursor position using X11
            d = display.Display()
            root = d.screen().root
            pointer = root.query_pointer()
            return pointer.root_x, pointer.root_y
        except ImportError:
            # Xlib not available, try alternative methods
            try:
                import subprocess
                # Try xdotool first
                result = subprocess.run(
                    ['xdotool', 'getmouselocation'], capture_output=True, text=True)
                if result.returncode == 0:
                    output = result.stdout.strip()
                    # Parse "x:123 y:456 screen:0 window:..."
                    parts = output.split()
                    x = y = None
                    for part in parts:
                        if part.startswith('x:'):
                            x = int(part[2:])
                        elif part.startswith('y:'):
                            y = int(part[2:])
                    if x is not None and y is not None:
                        return x, y
            except Exception:
                pass
        except Exception:
            pass

        return MenuPosition._get_cursor_position_fallback()

    @staticmethod
    def _get_cursor_position_fallback() -> Tuple[int, int]:
        """Fallback cursor position detection."""
        try:
            from pynput.mouse import Controller

            mouse = Controller()
            x, y = mouse.position
            return int(x), int(y)
        except Exception:
            pass

        # Final fallback to tkinter method
        try:
            temp_root = tk.Tk()
            temp_root.withdraw()
            x = temp_root.winfo_pointerx()
            y = temp_root.winfo_pointery()
            temp_root.destroy()
            return x, y
        except Exception:
            pass

        return 0, 0

    @staticmethod
    def adjust_for_screen_bounds(x: int, y: int, menu_width: int = 200, menu_height: int = 300) -> Tuple[int, int]:
        """Adjust menu position to ensure it fits on screen with multi-monitor support."""

        try:
            # Get screen bounds for the monitor containing the cursor
            screen_bounds = MenuPosition._get_screen_bounds_at_position(x, y)

            if screen_bounds:
                screen_x, screen_y, screen_width, screen_height = screen_bounds

                # Adjust horizontal position relative to screen bounds
                if x + menu_width > screen_x + screen_width:
                    x = screen_x + screen_width - menu_width
                if x < screen_x:
                    x = screen_x

                # Adjust vertical position relative to screen bounds
                if y + menu_height > screen_y + screen_height:
                    y = screen_y + screen_height - menu_height
                if y < screen_y:
                    y = screen_y

                return x, y
        except Exception:
            pass

        # Fallback to single screen bounds
        try:
            temp_root = tk.Tk()
            temp_root.withdraw()

            screen_width = temp_root.winfo_screenwidth()
            screen_height = temp_root.winfo_screenheight()

            temp_root.destroy()

            # Adjust horizontal position
            if x + menu_width > screen_width:
                x = screen_width - menu_width
            if x < 0:
                x = 0

            # Adjust vertical position
            if y + menu_height > screen_height:
                y = screen_height - menu_height
            if y < 0:
                y = 0

            return x, y
        except Exception:
            return x, y

    @staticmethod
    def _get_screen_bounds_at_position(x: int, y: int) -> Optional[Tuple[int, int, int, int]]:
        """Get screen bounds (x, y, width, height) for the screen containing the given position."""
        import platform

        system = platform.system()

        if system == "Darwin":  # macOS
            return MenuPosition._get_screen_bounds_macos(x, y)
        elif system == "Windows":
            return MenuPosition._get_screen_bounds_windows(x, y)
        elif system == "Linux":
            return MenuPosition._get_screen_bounds_linux(x, y)

        return None

    @staticmethod
    def _get_screen_bounds_macos(x: int, y: int) -> Optional[Tuple[int, int, int, int]]:
        """Get screen bounds on macOS for the screen containing the position."""
        try:
            from AppKit import NSScreen

            screens = NSScreen.screens()
            if not screens:
                return None

            # Convert coordinates back to macOS coordinate system (bottom-left origin)
            main_screen = screens[0]
            main_screen_height = main_screen.frame().size.height
            mac_y = main_screen_height - y

            # Find screen containing the point
            for screen in screens:
                frame = screen.frame()
                screen_x = int(frame.origin.x)
                screen_y = int(frame.origin.y)
                screen_width = int(frame.size.width)
                screen_height = int(frame.size.height)

                # Check if point is within this screen (macOS coordinates)
                if (screen_x <= x < screen_x + screen_width and
                        screen_y <= mac_y < screen_y + screen_height):

                    # Convert back to top-left origin for return
                    top_left_y = int(main_screen_height -
                                     screen_y - screen_height)
                    return (screen_x, top_left_y, screen_width, screen_height)

            # If not found, return main screen bounds
            main_frame = screens[0].frame()
            return (0, 0, int(main_frame.size.width), int(main_frame.size.height))

        except ImportError:
            # AppKit not available, fallback to system_profiler or default
            try:
                import subprocess
                result = subprocess.run(
                    ['system_profiler', 'SPDisplaysDataType'], capture_output=True, text=True)
                if result.returncode == 0:
                    # Basic parsing - this is a fallback, may not be perfect
                    output = result.stdout
                    if 'Resolution:' in output:
                        # This is a very basic fallback
                        return (0, 0, 1920, 1080)  # Default assumption
            except Exception:
                pass
            return None
        except Exception:
            return None

    @staticmethod
    def _get_screen_bounds_windows(x: int, y: int) -> Optional[Tuple[int, int, int, int]]:
        """Get screen bounds on Windows for the screen containing the position."""
        try:
            import ctypes
            from ctypes import wintypes

            # Check if required Windows API is available
            if not (hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'user32')):
                return None

            # Get monitor handle for the point
            point = wintypes.POINT(x, y)
            monitor = ctypes.windll.user32.MonitorFromPoint(
                point, 2)  # MONITOR_DEFAULTTONEAREST

            if monitor:
                # Get monitor info
                class MONITORINFO(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", wintypes.DWORD),
                        ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT),
                        ("dwFlags", wintypes.DWORD)
                    ]

                mi = MONITORINFO()
                mi.cbSize = ctypes.sizeof(MONITORINFO)

                if ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(mi)):
                    rect = mi.rcMonitor
                    return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
        except (ImportError, AttributeError, OSError):
            pass
        except Exception:
            pass

        return None

    @staticmethod
    def _get_screen_bounds_linux(x: int, y: int) -> Optional[Tuple[int, int, int, int]]:
        """Get screen bounds on Linux for the screen containing the position."""
        try:
            from Xlib import display

            # Get display
            d = display.Display()
            screen = d.screen()

            # Try to get screen resources for multi-monitor info
            try:
                import subprocess
                result = subprocess.run(
                    ['xrandr'], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if ' connected ' in line and '+' in line:
                            # Parse screen geometry: "1920x1080+1920+0"
                            parts = line.split()
                            for part in parts:
                                if 'x' in part and '+' in part:
                                    try:
                                        # Extract dimensions and position
                                        geom = part.split('+')
                                        if len(geom) >= 3:
                                            dims = geom[0].split('x')
                                            width, height = int(
                                                dims[0]), int(dims[1])
                                            offset_x, offset_y = int(
                                                geom[1]), int(geom[2])

                                            # Check if point is within this screen
                                            if (offset_x <= x < offset_x + width and
                                                    offset_y <= y < offset_y + height):
                                                return (offset_x, offset_y, width, height)
                                    except (ValueError, IndexError):
                                        continue
            except Exception:
                pass

            # Fallback to root window size
            root = screen.root
            geom = root.get_geometry()
            return (0, 0, geom.width, geom.height)

        except ImportError:
            # Xlib not available, try xrandr directly
            try:
                import subprocess
                result = subprocess.run(
                    ['xrandr'], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if ' connected ' in line and '+' in line:
                            parts = line.split()
                            for part in parts:
                                if 'x' in part and '+' in part:
                                    try:
                                        geom = part.split('+')
                                        if len(geom) >= 3:
                                            dims = geom[0].split('x')
                                            width, height = int(
                                                dims[0]), int(dims[1])
                                            offset_x, offset_y = int(
                                                geom[1]), int(geom[2])

                                            if (offset_x <= x < offset_x + width and
                                                    offset_y <= y < offset_y + height):
                                                return (offset_x, offset_y, width, height)
                                    except (ValueError, IndexError):
                                        continue
            except Exception:
                pass
            return None
        except Exception:
            pass

        return None

    @staticmethod
    def apply_offset(x: int, y: int, offset: Tuple[int, int]) -> Tuple[int, int]:
        """Apply position offset."""
        offset_x, offset_y = offset
        return x + offset_x, y + offset_y
