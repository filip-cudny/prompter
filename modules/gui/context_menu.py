"""PyQt5-based context menu system for the Prompter application."""

from typing import List, Optional, Tuple, Callable
from PyQt5.QtWidgets import QMenu, QAction, QApplication, QWidgetAction, QLabel, QWidget
from PyQt5.QtCore import Qt, QPoint, QTimer, QObject, QEvent
from PyQt5.QtGui import QCursor
from core.models import MenuItem, MenuItemType
from modules.gui.shared_widgets import TOOLTIP_STYLE
from modules.gui.dialog_styles import DISABLED_OPACITY
import sip
import platform
import subprocess
import os


def _set_macos_window_move_to_active_space(widget):
    """
    Set NSWindowCollectionBehaviorMoveToActiveSpace on a PyQt5 widget's native window.
    This ensures the window appears on the current Space instead of causing a Space switch.

    Must be called AFTER the widget has been shown (winId is only valid then).
    """
    if platform.system() != "Darwin":
        return

    try:
        from ctypes import c_void_p
        import objc

        # NSWindowCollectionBehaviorMoveToActiveSpace = 1 << 1 = 2
        NSWindowCollectionBehaviorMoveToActiveSpace = 1 << 1

        # Get the native window ID (returns an integer pointer to NSView on macOS)
        win_id = widget.winId()
        if not win_id:
            return

        # Convert the integer pointer to a PyObjC NSView object
        ns_view = objc.objc_object(c_void_p=c_void_p(int(win_id)))

        # Get the NSWindow from the NSView
        ns_window = ns_view.window()
        if ns_window is None:
            return

        # Get current collection behavior and add MoveToActiveSpace
        current_behavior = ns_window.collectionBehavior()
        new_behavior = current_behavior | NSWindowCollectionBehaviorMoveToActiveSpace
        ns_window.setCollectionBehavior_(new_behavior)

    except ImportError:
        pass
    except Exception as e:
        print(f"Warning: Could not set macOS window collection behavior: {e}")


class InvisibleFocusWindow(QWidget):
    """Invisible window that grabs focus to enable QMenu keyboard navigation."""

    def __init__(self, context_menu=None):
        super().__init__()
        self.menu: Optional[QMenu] = None
        self.context_menu = context_menu
        self.setup_window()

    def setup_window(self):
        """Setup invisible window properties."""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(1, 1)
        self.setWindowOpacity(0.01)

    def grab_focus_and_show_menu(self, menu: QMenu, position: QPoint):
        """Grab focus and show the menu."""
        self.menu = menu

        # Position the invisible window near the menu
        self.move(position.x(), position.y())

        # Force application activation
        self._force_app_activation()

        # Show invisible window and grab focus
        self.show()

        # Set macOS window collection behavior AFTER show() so winId is valid
        _set_macos_window_move_to_active_space(self)

        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.OtherFocusReason)

        # Ensure this window can receive keyboard events
        self.setFocusPolicy(Qt.StrongFocus)

        # Show menu after a short delay to ensure focus is grabbed
        QTimer.singleShot(50, lambda: self._show_menu_at_position(position))

        # Additional focus attempts to ensure keyboard events work
        QTimer.singleShot(50, lambda: self.setFocus(Qt.OtherFocusReason))
        QTimer.singleShot(75, lambda: self.activateWindow())

    def _force_app_activation(self):
        """Force application activation based on platform."""
        if platform.system() == "Darwin":
            self._activate_macos()
        elif platform.system() == "Windows":
            self._activate_windows()
        elif platform.system() == "Linux":
            self._activate_linux()

    def _activate_macos(self):
        """Activate application on macOS."""
        try:
            try:
                from Foundation import NSRunningApplication

                app = NSRunningApplication.runningApplicationWithProcessIdentifier_(
                    os.getpid()
                )
                if app:
                    app.activateWithOptions_(1)
                    return
            except ImportError:
                pass

            script = f"""
            tell application "System Events"
                set frontmost of first process whose unix id is {os.getpid()} to true
            end tell
            """
            subprocess.run(
                ["osascript", "-e", script], capture_output=True, timeout=2, check=False
            )

        except Exception:
            pass

    def _activate_windows(self):
        """Activate application on Windows."""
        try:
            import ctypes

            hwnd = int(self.winId())
            if hwnd:
                user32 = ctypes.windll.user32
                user32.SetForegroundWindow(hwnd)
                user32.BringWindowToTop(hwnd)
        except Exception:
            pass

    def _activate_linux(self):
        """Activate application on Linux."""
        try:
            subprocess.run(
                ["wmctrl", "-a", str(os.getpid())],
                capture_output=True,
                timeout=1,
                check=False,
            )
        except Exception:
            pass

    def _show_menu_at_position(self, position: QPoint):
        """Show the menu at the specified position."""
        if self.menu and not self.menu.isVisible():
            self.menu.aboutToHide.connect(self._on_menu_hidden)
            self.menu.popup(position)

            # Set macOS window collection behavior on menu after popup
            _set_macos_window_move_to_active_space(self.menu)

    def _on_menu_hidden(self):
        """Handle menu being hidden."""
        if self.context_menu and hasattr(self.context_menu, "_on_menu_about_to_hide"):
            self.context_menu._on_menu_about_to_hide()
        self.hide()

    def keyPressEvent(self, event):
        """Forward key events to the menu if it's visible."""
        if self.menu and self.menu.isVisible():
            # Forward key events to the menu
            QApplication.sendEvent(self.menu, event)
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Handle close event."""
        if self.menu and self.menu.isVisible():
            self.menu.hide()
        super().closeEvent(event)


class PyQtContextMenu(QObject):
    """PyQt5-based context menu implementation with keyboard navigation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.menu: Optional[QMenu] = None
        self.menu_position_offset = (0, 0)
        self.number_input_debounce_ms = 200
        self.execution_callback: Optional[Callable] = None
        self.shift_pressed = False
        self.event_filter_installed = False
        self.hovered_widgets = set()
        self.original_active_window = None
        self.qt_active_window = None
        self.focus_window: Optional[InvisibleFocusWindow] = None
        self.number_input_buffer = ""
        self.number_timer = None
        self._focus_restore_pending = False
        self._cleanable_widgets = []
        self._execution_signal_connected = False
        self._last_menu_position = None

        self._menu_stylesheet = """
            QMenu {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 4px;
                color: #ffffff;
                font-size: 13px;
            }
            QMenu::item {
                background-color: transparent;
                padding: 8px 16px;
                border-radius: 4px;
                margin: 1px;
            }
            QMenu::item:selected {
                background-color: #454545;
                color: #ffffff;
            }
            QMenu::item:focus {
                background-color: #454545;
                color: #ffffff;
            }
            QMenu::item:disabled {
                color: #666666;
            }
            QMenu::separator {
                height: 1px;
                background-color: #555555;
                margin: 4px 8px;
            }
            QMenu::indicator {
                width: 16px;
                height: 16px;
                margin-left: 4px;
            }
        """ + TOOLTIP_STYLE

    def set_execution_callback(self, callback: Callable):
        """Set callback for menu item execution."""
        self.execution_callback = callback

    def create_menu(self, items: List[MenuItem]) -> QMenu:
        """Create a QMenu from menu items with keyboard navigation support."""
        # Clean up any existing tracked widgets before creating new menu
        for widget in self._cleanable_widgets:
            try:
                if hasattr(widget, 'cleanup') and callable(widget.cleanup):
                    if not sip.isdeleted(widget):
                        widget.cleanup()
            except Exception:
                pass
        self._cleanable_widgets.clear()

        menu = QMenu(self.parent)

        # Configure window flags for better focus behavior when triggered from external apps
        if platform.system() == "Darwin":
            # macOS needs different flags for external app focus
            menu.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        else:
            menu.setWindowFlags(
                Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
            )

        menu.setAttribute(
            Qt.WA_TranslucentBackground, True
        )  # Enable transparency for rounded corners
        menu.setAttribute(Qt.WA_ShowWithoutActivating, False)  # Allow activation
        menu.setStyleSheet(self._menu_stylesheet)

        # Enable keyboard navigation with strong focus
        menu.setFocusPolicy(Qt.StrongFocus)

        # Reset shift state and install event filter
        self.shift_pressed = False
        self.event_filter_installed = True
        menu.installEventFilter(self)

        self._add_menu_items(menu, items)

        # Connect menu aboutToHide signal to cleanup number timer
        menu.aboutToHide.connect(self._on_menu_about_to_hide)

        return menu

    def create_submenu(
        self, parent_menu: QMenu, title: str, items: List[MenuItem]
    ) -> QMenu:
        """Create a submenu with consistent styling."""
        submenu = QMenu(title, parent_menu)
        submenu.setWindowFlags(
            Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        )
        submenu.setAttribute(Qt.WA_TranslucentBackground, True)
        submenu.setStyleSheet(self._menu_stylesheet)
        submenu.setFocusPolicy(Qt.StrongFocus)
        submenu.installEventFilter(self)

        self._add_menu_items(submenu, items)
        return submenu

    def show_at_cursor(self, items: List[MenuItem]) -> None:
        """Show context menu at cursor position."""
        cursor_pos = self.get_cursor_position()
        self.show_at_position(items, cursor_pos)

    def show_at_position(
        self, items: List[MenuItem], position: Tuple[int, int]
    ) -> None:
        """Show context menu at specific position with invisible focus window for keyboard navigation."""
        if not items:
            return

        try:
            # Store both Qt and external application info
            self._store_qt_active_window()
            self._store_active_window()

            x, y = position
            offset_x, offset_y = self.menu_position_offset

            self.shift_pressed = bool(
                QApplication.keyboardModifiers() & Qt.ShiftModifier
            )

            self.menu = self.create_menu(items)

            # Calculate anchor offset to position cursor at prompts section
            anchor_offset = self._calculate_anchor_offset()
            adjusted_y = y + offset_y - anchor_offset

            # Ensure menu doesn't go above screen top
            if adjusted_y < 0:
                adjusted_y = 0

            adjusted_pos = QPoint(x + offset_x, adjusted_y)
            self._last_menu_position = adjusted_pos

            # Connect to execution_completed signal for auto-refresh
            self._connect_execution_signal()

            # Create focus window if needed
            if not self.focus_window:
                self.focus_window = InvisibleFocusWindow(self)

            # Use invisible focus window for robust keyboard navigation
            self.focus_window.grab_focus_and_show_menu(self.menu, adjusted_pos)

        except Exception as e:
            print(f"Menu show error: {e}")

    def _calculate_anchor_offset(self) -> int:
        """Calculate Y offset to anchor menu at Prompts section.

        This calculates the total height of Context and LastInteraction widgets
        that appear before the prompts, so the menu can be positioned with
        the cursor at the prompts section.
        """
        if not self.menu:
            return 0

        from modules.gui.context_widgets import (
            ContextSectionWidget,
            LastInteractionSectionWidget,
        )

        offset = 0
        for action in self.menu.actions():
            # Only QWidgetAction has defaultWidget(), not regular QAction
            if not isinstance(action, QWidgetAction):
                if action.isSeparator():
                    offset += 9
                else:
                    # Regular action (submenu), stop counting
                    break
                continue

            widget = action.defaultWidget()
            if not widget:
                # QWidgetAction without widget, stop counting
                break

            # Check if it's Context or LastInteraction widget
            if isinstance(widget, (ContextSectionWidget, LastInteractionSectionWidget)):
                # Force layout calculation for accurate size
                widget.adjustSize()
                offset += widget.sizeHint().height()
            else:
                # Reached prompts section, stop counting
                break

        return offset

    def _force_app_activation_macos(self):
        """Force application activation on macOS when triggered from another app."""
        try:
            # Try PyObjC first for more reliable activation
            try:
                from Foundation import NSRunningApplication

                app = NSRunningApplication.runningApplicationWithProcessIdentifier_(
                    os.getpid()
                )
                if app:
                    app.activateWithOptions_(
                        1
                    )  # NSApplicationActivateIgnoringOtherApps
                    return
            except ImportError:
                pass

            # Fallback to AppleScript
            script = f"""
            tell application "System Events"
                set frontmost of first process whose unix id is {os.getpid()} to true
            end tell
            """
            subprocess.run(
                ["osascript", "-e", script], capture_output=True, timeout=2, check=False
            )

            # Additional activation attempt
            script2 = f"""
            tell application id "{os.getpid()}" to activate
            """
            subprocess.run(
                ["osascript", "-e", script2],
                capture_output=True,
                timeout=1,
                check=False,
            )

        except Exception:
            pass

    def _force_app_activation_windows(self):
        """Force application activation on Windows when triggered from another app."""
        try:
            import ctypes

            # Get current process window
            hwnd = int(self.menu.winId()) if self.menu else 0
            if hwnd:
                # SetForegroundWindow and BringWindowToTop
                user32 = ctypes.windll.user32
                user32.SetForegroundWindow(hwnd)
                user32.BringWindowToTop(hwnd)
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE

        except Exception:
            pass

    def _force_app_activation_linux(self):
        """Force application activation on Linux when triggered from another app."""
        try:
            # Use wmctrl if available
            subprocess.run(
                ["wmctrl", "-a", str(os.getpid())],
                capture_output=True,
                timeout=1,
                check=False,
            )
        except Exception:
            pass

    def get_cursor_position(self) -> Tuple[int, int]:
        """Get current cursor position."""
        cursor_pos = QCursor.pos()
        return (cursor_pos.x(), cursor_pos.y())

    def set_menu_position_offset(self, offset: Tuple[int, int]) -> None:
        """Set offset for menu positioning."""
        self.menu_position_offset = offset

    def set_number_input_debounce_ms(self, debounce_ms: int) -> None:
        """Set debounce delay for number input in milliseconds."""
        self.number_input_debounce_ms = debounce_ms

    def destroy(self) -> None:
        """Clean up the menu."""
        try:
            self._cleanup_menu()
        except Exception as e:
            print(f"Menu cleanup error: {e}")

    def _connect_execution_signal(self):
        """Connect to execution_completed signal for auto-refresh."""
        if self._execution_signal_connected:
            return
        if hasattr(self, 'menu_coordinator') and self.menu_coordinator:
            try:
                self.menu_coordinator.execution_completed.connect(
                    self._on_execution_completed_while_open
                )
                self._execution_signal_connected = True
            except Exception:
                pass

    def _disconnect_execution_signal(self):
        """Disconnect from execution_completed signal."""
        if not self._execution_signal_connected:
            return
        if hasattr(self, 'menu_coordinator') and self.menu_coordinator:
            try:
                self.menu_coordinator.execution_completed.disconnect(
                    self._on_execution_completed_while_open
                )
            except Exception:
                pass
        self._execution_signal_connected = False

    def _on_execution_completed_while_open(self, result):
        """Refresh menu when execution completes while open."""
        if self.menu and self.menu.isVisible() and self._last_menu_position:
            # Invalidate cache so fresh item states are fetched
            if hasattr(self, 'menu_coordinator') and self.menu_coordinator:
                self.menu_coordinator._invalidate_cache()
            # Use short timer to allow event loop to process
            QTimer.singleShot(10, self._rebuild_and_show_menu)

    def _rebuild_and_show_menu(self):
        """Rebuild and show the menu at the stored position."""
        if not hasattr(self, 'menu_coordinator') or not self.menu_coordinator:
            return

        pos = self._last_menu_position
        if not pos:
            return

        items = self.menu_coordinator._get_all_menu_items()
        if not items:
            return

        old_menu = self.menu
        self.menu = self.create_menu(items)

        # Show new menu FIRST (before closing old) to prevent blink
        if self.focus_window:
            self.focus_window.menu = self.menu
            self.focus_window._show_menu_at_position(pos)

        # Close old menu AFTER showing new one
        # Disconnect signals first to prevent cleanup from affecting new menu
        if old_menu:
            try:
                if not sip.isdeleted(old_menu):
                    old_menu.aboutToHide.disconnect()
                    old_menu.hide()
                    QTimer.singleShot(50, lambda: self._cleanup_old_menu(old_menu))
            except Exception:
                pass

    def _cleanup_old_menu(self, menu):
        """Clean up old menu after transition."""
        try:
            if menu and not sip.isdeleted(menu):
                menu.close()
                menu.deleteLater()
        except Exception:
            pass

    def _cleanup_menu(self):
        """Internal cleanup method."""
        # Disconnect from execution signal
        self._disconnect_execution_signal()
        self._last_menu_position = None

        # Clean up tracked widgets FIRST
        for widget in self._cleanable_widgets:
            try:
                if hasattr(widget, 'cleanup') and callable(widget.cleanup):
                    if not sip.isdeleted(widget):
                        widget.cleanup()
            except Exception:
                pass
        self._cleanable_widgets.clear()

        if self.focus_window:
            self.focus_window.hide()
            self.focus_window.deleteLater()
            self.focus_window = None

        if self.menu:
            try:
                if not sip.isdeleted(self.menu):
                    self.menu.close()
                    self.menu.deleteLater()
            except Exception:
                pass
            self.menu = None

        self.shift_pressed = False

        # Clean up number input timer
        if self.number_timer:
            self.number_timer.stop()
            self.number_timer.deleteLater()
            self.number_timer = None
        self.number_input_buffer = ""
        self.event_filter_installed = False
        self.hovered_widgets.clear()

        # Clear focus references after ensuring restoration
        self.original_active_window = None
        self.qt_active_window = None

    def _add_menu_items(self, menu: QMenu, items: List[MenuItem]) -> None:
        """Add menu items to a QMenu."""
        for item in items:
            if item.item_type == MenuItemType.CONTEXT:
                # Create context section widget
                action = self._create_context_section_item(menu, item)
                if action:
                    menu.addAction(action)
            elif item.item_type == MenuItemType.LAST_INTERACTION:
                # Create last interaction section widget
                action = self._create_last_interaction_section_item(menu, item)
                if action:
                    menu.addAction(action)
            elif item.item_type == MenuItemType.SETTINGS_SECTION:
                # Create settings section widget with chips
                action = self._create_settings_section_item(menu, item)
                if action:
                    menu.addAction(action)
            elif hasattr(item, "submenu_items") and item.submenu_items:
                # Create submenu with consistent styling
                submenu = self.create_submenu(menu, item.label, item.submenu_items)
                submenu_action = menu.addMenu(submenu)
                submenu_action.setEnabled(item.enabled)
            else:
                action = self._create_custom_menu_item(menu, item)
                if action:
                    menu.addAction(action)

            if hasattr(item, "separator_after") and item.separator_after:
                menu.addSeparator()

    def _create_context_section_item(
        self, menu: QMenu, item: MenuItem
    ) -> Optional[QAction]:
        """Create a context section widget action."""
        from modules.gui.context_widgets import ContextSectionWidget

        context_manager = item.data.get("context_manager") if item.data else None
        if not context_manager:
            return None

        notification_manager = item.data.get("notification_manager") if item.data else None
        clipboard_manager = item.data.get("clipboard_manager") if item.data else None
        widget = ContextSectionWidget(
            context_manager,
            notification_manager=notification_manager,
            clipboard_manager=clipboard_manager,
        )
        self._cleanable_widgets.append(widget)
        action = QWidgetAction(menu)
        action.setDefaultWidget(widget)
        return action

    def _create_last_interaction_section_item(
        self, menu: QMenu, item: MenuItem
    ) -> Optional[QAction]:
        """Create a last interaction section widget action."""
        from modules.gui.context_widgets import LastInteractionSectionWidget

        history_service = item.data.get("history_service") if item.data else None
        if not history_service:
            return None

        notification_manager = item.data.get("notification_manager") if item.data else None
        clipboard_manager = item.data.get("clipboard_manager") if item.data else None
        widget = LastInteractionSectionWidget(
            history_service,
            notification_manager=notification_manager,
            clipboard_manager=clipboard_manager,
        )
        self._cleanable_widgets.append(widget)
        action = QWidgetAction(menu)
        action.setDefaultWidget(widget)
        return action

    def _create_settings_section_item(
        self, menu: QMenu, item: MenuItem
    ) -> Optional[QAction]:
        """Create a settings section widget action with model and prompt chips."""
        from modules.gui.context_widgets import SettingsSectionWidget

        if not item.data:
            return None

        model_options = item.data.get("model_options", [])
        prompt_options = item.data.get("prompt_options", [])
        current_model = item.data.get("current_model", "None")
        current_prompt = item.data.get("current_prompt", "None")
        on_prompt_clear = item.data.get("on_prompt_clear")

        widget = SettingsSectionWidget(
            model_options=model_options,
            prompt_options=prompt_options,
            current_model=current_model,
            current_prompt=current_prompt,
            on_prompt_clear=on_prompt_clear,
        )
        action = QWidgetAction(menu)
        action.setDefaultWidget(widget)
        return action

    def _create_custom_menu_item(
        self, menu: QMenu, item: MenuItem
    ) -> Optional[QAction]:
        """Create a custom menu item with hover effects."""
        from PyQt5.QtWidgets import QHBoxLayout, QGraphicsOpacityEffect
        from PyQt5.QtGui import QPixmap, QPainter
        from modules.gui.icons import create_icon_pixmap, ICON_COLOR_NORMAL, ICON_COLOR_DISABLED
        from modules.gui.context_widgets import IconButton

        class ClickableMenuItem(QWidget):
            def __init__(self, text, menu_item, context_menu):
                super().__init__()
                self.setAttribute(Qt.WA_StyledBackground, True)
                self._menu_item = menu_item
                self._context_menu = context_menu
                self._is_highlighted = False
                self._disable_reason = None
                self._is_recording_action = False
                self._is_executing_action = False
                self._rotation_angle = 0
                self._rotation_timer = None

                self._normal_style = """
                    QWidget {
                        background-color: transparent;
                        border-radius: 4px;
                        margin: 1px;
                    }
                """
                self._hover_style = """
                    QWidget {
                        background-color: #454545;
                        border-radius: 4px;
                        margin: 1px;
                    }
                """
                self._label_style = """
                    QLabel {
                        background: transparent;
                        color: #f0f0f0;
                        font-size: 13px;
                    }
                """
                self._label_hover_style = """
                    QLabel {
                        background: transparent;
                        color: #ffffff;
                        font-size: 13px;
                    }
                """
                self._label_disabled_style = """
                    QLabel {
                        background: transparent;
                        color: #666666;
                        font-size: 13px;
                    }
                """

                self.setStyleSheet(self._normal_style)
                self.setFocusPolicy(Qt.StrongFocus)

                # Layout
                layout = QHBoxLayout(self)
                layout.setContentsMargins(16, 8, 16, 8)
                layout.setSpacing(8)

                # Icon (optional)
                self._icon_label = None
                if menu_item.icon:
                    self._icon_label = QLabel()
                    icon_color = ICON_COLOR_DISABLED if not menu_item.enabled else ICON_COLOR_NORMAL
                    pixmap = create_icon_pixmap(menu_item.icon, icon_color, 16)
                    self._icon_label.setPixmap(pixmap)
                    self._icon_label.setFixedSize(16, 16)
                    self._icon_label.setStyleSheet("background: transparent;")
                    layout.addWidget(self._icon_label)

                # Text label
                self._text_label = QLabel(text)
                self._text_label.setStyleSheet(self._label_style)
                layout.addWidget(self._text_label)

                # State indicator icons (hidden by default) - stop first, then loader
                self._stop_label = QLabel()
                self._stop_label.setFixedSize(20, 20)
                self._stop_label.setStyleSheet("background: transparent;")
                self._stop_label.setAlignment(Qt.AlignCenter)
                self._stop_label.hide()
                layout.addWidget(self._stop_label)

                self._loader_label = QLabel()
                self._loader_label.setFixedSize(20, 20)
                self._loader_label.setStyleSheet("background: transparent;")
                self._loader_label.setAlignment(Qt.AlignCenter)
                self._loader_label.hide()
                layout.addWidget(self._loader_label)

                layout.addStretch()

                # Mic button for alternative execution (only for PROMPT items)
                self._mic_btn = None
                if menu_item.item_type == MenuItemType.PROMPT:
                    self._mic_btn = IconButton("mic", size=16)
                    self._mic_btn.setStyleSheet("""
                        QPushButton {
                            background: transparent;
                            border: none;
                            padding: 2px;
                            min-width: 20px;
                            max-width: 20px;
                            min-height: 20px;
                            max-height: 20px;
                        }
                    """)
                    self._mic_btn.setCursor(Qt.PointingHandCursor)
                    self._mic_btn.setToolTip("Record voice input")
                    self._mic_btn.clicked.connect(self._on_mic_clicked)
                    layout.addWidget(self._mic_btn)

                # Message share button (only for PROMPT items)
                self._message_btn = None
                if menu_item.item_type == MenuItemType.PROMPT:
                    self._message_btn = IconButton("message-square-share", size=16)
                    self._message_btn.setStyleSheet("""
                        QPushButton {
                            background: transparent;
                            border: none;
                            padding: 2px;
                            min-width: 20px;
                            max-width: 20px;
                            min-height: 20px;
                            max-height: 20px;
                        }
                    """)
                    self._message_btn.setCursor(Qt.PointingHandCursor)
                    self._message_btn.setToolTip("Send message to prompt")
                    self._message_btn.clicked.connect(self._on_message_share_clicked)
                    layout.addWidget(self._message_btn)

            def _check_is_recording_action(self) -> bool:
                """Check if this menu item is the currently recording action."""
                if hasattr(self._context_menu, 'menu_coordinator') and self._context_menu.menu_coordinator:
                    prompt_store_service = self._context_menu.menu_coordinator.prompt_store_service
                    if prompt_store_service:
                        recording_action_id = prompt_store_service.get_recording_action_id()
                        return recording_action_id == self._menu_item.id
                return False

            def set_disabled_state(self, disable_reason: Optional[str]):
                """Set disabled state with visual feedback based on reason."""
                self._disable_reason = disable_reason
                self._is_recording_action = self._check_is_recording_action()

                if disable_reason:
                    # Apply opacity effect to text label
                    text_effect = QGraphicsOpacityEffect(self._text_label)
                    text_effect.setOpacity(DISABLED_OPACITY)
                    self._text_label.setGraphicsEffect(text_effect)

                    # Apply opacity to icon if present
                    if self._icon_label:
                        icon_effect = QGraphicsOpacityEffect(self._icon_label)
                        icon_effect.setOpacity(DISABLED_OPACITY)
                        self._icon_label.setGraphicsEffect(icon_effect)

                    # Update text style
                    self._text_label.setStyleSheet(self._label_disabled_style)

                    # Update mic button state based on reason - disabled with opacity
                    if self._mic_btn:
                        if disable_reason in ('recording', 'executing'):
                            self._mic_btn.setEnabled(False)
                            self._mic_btn.setCursor(Qt.ArrowCursor)
                            # Apply opacity to disabled mic button
                            mic_effect = QGraphicsOpacityEffect(self._mic_btn)
                            mic_effect.setOpacity(DISABLED_OPACITY)
                            self._mic_btn.setGraphicsEffect(mic_effect)

                    # Message buttons stay enabled - no opacity effect (same as normal state)
                    if self._message_btn:
                        self._message_btn.setEnabled(True)
                        self._message_btn.setCursor(Qt.PointingHandCursor)
                        self._message_btn.setGraphicsEffect(None)
                else:
                    # Clear opacity effects
                    self._text_label.setGraphicsEffect(None)
                    if self._icon_label:
                        self._icon_label.setGraphicsEffect(None)

                    # Restore normal text style
                    self._text_label.setStyleSheet(self._label_style)

                    # Enable buttons and clear any opacity effects
                    if self._mic_btn:
                        self._mic_btn.setEnabled(True)
                        self._mic_btn.setCursor(Qt.PointingHandCursor)
                        self._mic_btn.setGraphicsEffect(None)
                    if self._message_btn:
                        self._message_btn.setEnabled(True)
                        self._message_btn.setCursor(Qt.PointingHandCursor)
                        self._message_btn.setGraphicsEffect(None)

            def set_recording_action_state(self, is_recording_action: bool):
                """Set this item as the currently recording action."""
                self._is_recording_action = is_recording_action

                if is_recording_action and self._mic_btn:
                    # Clear opacity for this specific item since it's the active recording one
                    self.setGraphicsEffect(None)

                    # Restore normal text style
                    self._text_label.setStyleSheet(self._label_style)

                    # Change mic icon to square (stop icon)
                    self._mic_btn.set_icon("square")
                    self._mic_btn.setToolTip("Stop recording")
                    self._mic_btn.setEnabled(True)
                    self._mic_btn.setCursor(Qt.PointingHandCursor)

                    # Message button stays enabled
                    if self._message_btn:
                        self._message_btn.setEnabled(True)
                        self._message_btn.setCursor(Qt.PointingHandCursor)

            def set_executing_action_state(self, is_executing_action: bool):
                """Set this item as the currently executing action."""
                self._is_executing_action = is_executing_action

                if is_executing_action:
                    # Clear any disabled opacity effects
                    self.setGraphicsEffect(None)
                    self._text_label.setStyleSheet(self._label_style)
                    self._text_label.setGraphicsEffect(None)
                    if self._icon_label:
                        self._icon_label.setGraphicsEffect(None)

                    # Show stop icon first (in font color), then loader icon
                    stop_pixmap = create_icon_pixmap("square", "#f0f0f0", 14)
                    self._stop_label.setPixmap(stop_pixmap)
                    self._stop_label.show()

                    loader_pixmap = create_icon_pixmap("loader", ICON_COLOR_DISABLED, 14)
                    self._loader_label.setPixmap(loader_pixmap)
                    self._loader_label.show()

                    # Apply slight opacity to loader only
                    loader_effect = QGraphicsOpacityEffect(self._loader_label)
                    loader_effect.setOpacity(0.85)
                    self._loader_label.setGraphicsEffect(loader_effect)

                    # Start rotation animation for loader
                    self._start_loader_animation()

                    # Disable mic button during execution
                    if self._mic_btn:
                        self._mic_btn.setEnabled(False)
                        self._mic_btn.setCursor(Qt.ArrowCursor)
                        mic_effect = QGraphicsOpacityEffect(self._mic_btn)
                        mic_effect.setOpacity(DISABLED_OPACITY)
                        self._mic_btn.setGraphicsEffect(mic_effect)

                    # Message button stays enabled
                    if self._message_btn:
                        self._message_btn.setEnabled(True)
                        self._message_btn.setCursor(Qt.PointingHandCursor)
                else:
                    # Hide indicators
                    if self._loader_label:
                        self._loader_label.hide()
                    if self._stop_label:
                        self._stop_label.hide()
                    self._stop_loader_animation()

            def _start_loader_animation(self):
                """Start rotating the loader icon."""
                self._rotation_angle = 0
                # Cache the base pixmap at smaller size to leave room for rotation
                self._loader_base_pixmap = create_icon_pixmap("loader", ICON_COLOR_DISABLED, 12)
                self._loader_dpr = self._loader_base_pixmap.devicePixelRatio()
                self._loader_canvas_size = int(20 * self._loader_dpr)
                self._loader_icon_size = int(12 * self._loader_dpr)
                self._rotation_timer = QTimer(self)
                self._rotation_timer.timeout.connect(self._rotate_loader)
                self._rotation_timer.start(150)

            def _rotate_loader(self):
                """Rotate the loader icon smoothly on a fixed-size canvas."""
                self._rotation_angle = (self._rotation_angle + 30) % 360
                if self._loader_label and hasattr(self, '_loader_base_pixmap'):
                    # Create fixed-size output pixmap
                    canvas = self._loader_canvas_size
                    icon = self._loader_icon_size
                    offset = (canvas - icon) // 2

                    result = QPixmap(canvas, canvas)
                    result.fill(Qt.transparent)

                    # Paint rotated icon centered on fixed canvas
                    painter = QPainter(result)
                    painter.setRenderHint(QPainter.Antialiasing)
                    painter.setRenderHint(QPainter.SmoothPixmapTransform)
                    painter.translate(canvas / 2, canvas / 2)
                    painter.rotate(self._rotation_angle)
                    painter.translate(-icon / 2, -icon / 2)
                    painter.drawPixmap(0, 0, self._loader_base_pixmap)
                    painter.end()

                    result.setDevicePixelRatio(self._loader_dpr)
                    self._loader_label.setPixmap(result)

            def _stop_loader_animation(self):
                """Stop the loader animation."""
                if self._rotation_timer:
                    self._rotation_timer.stop()
                    self._rotation_timer = None

            def _update_style(self, highlighted: bool):
                """Update styles for highlight state."""
                # Don't update style if disabled (keep disabled appearance)
                if self._disable_reason and not self._is_recording_action and not self._is_executing_action:
                    return

                if highlighted:
                    self.setStyleSheet(self._hover_style)
                    self._text_label.setStyleSheet(self._label_hover_style)
                else:
                    self.setStyleSheet(self._normal_style)
                    if self._menu_item.enabled:
                        self._text_label.setStyleSheet(self._label_style)
                    else:
                        self._text_label.setStyleSheet(self._label_disabled_style)

            def _on_message_share_clicked(self):
                """Handle message share button click."""
                # Message button is always enabled, so allow this
                # Close the menu
                if self._context_menu.menu:
                    self._context_menu.menu.close()
                if self._context_menu.focus_window:
                    self._context_menu.focus_window.hide()

                # Get prompt store service, context manager, clipboard manager, and notification manager from menu coordinator
                prompt_store_service = None
                context_manager = None
                clipboard_manager = None
                notification_manager = None
                if hasattr(self._context_menu, 'menu_coordinator') and self._context_menu.menu_coordinator:
                    prompt_store_service = self._context_menu.menu_coordinator.prompt_store_service
                    context_manager = self._context_menu.menu_coordinator.context_manager
                    notification_manager = self._context_menu.menu_coordinator.notification_manager
                    if prompt_store_service and hasattr(prompt_store_service, 'clipboard_manager'):
                        clipboard_manager = prompt_store_service.clipboard_manager

                # Open message share dialog
                from modules.gui.message_share_dialog import show_message_share_dialog
                show_message_share_dialog(
                    self._menu_item,
                    self._context_menu.execution_callback,
                    prompt_store_service=prompt_store_service,
                    context_manager=context_manager,
                    clipboard_manager=clipboard_manager,
                    notification_manager=notification_manager,
                )

            def _on_mic_clicked(self):
                """Handle mic button click - trigger alternative execution (speech input)."""
                # For recording action, this stops recording (always allowed)
                # For non-recording actions when enabled
                if self._context_menu.execution_callback:
                    if self._is_recording_action or self._menu_item.enabled:
                        # True = shift_pressed, triggers alternative execution (speech-to-text)
                        self._context_menu.execution_callback(self._menu_item, True)
                        # Close the menu after execution
                        if self._context_menu.menu:
                            self._context_menu.menu.close()
                        if self._context_menu.focus_window:
                            self._context_menu.focus_window.hide()
                        # Restore focus after execution
                        self._context_menu._focus_restore_pending = True
                        QTimer.singleShot(
                            100, self._context_menu._restore_focus_with_cleanup
                        )

            def mousePressEvent(self, event):
                # Check if click is on a button - if so, let the button handle it
                if self._mic_btn and self._mic_btn.geometry().contains(event.pos()):
                    return super().mousePressEvent(event)
                if self._message_btn and self._message_btn.geometry().contains(event.pos()):
                    return super().mousePressEvent(event)

                # For text area clicks, check if action is enabled
                if event.button() == Qt.LeftButton:
                    # If this is the executing action, clicking cancels execution
                    if self._is_executing_action:
                        if hasattr(self._context_menu, 'menu_coordinator') and self._context_menu.menu_coordinator:
                            # Cancel will emit execution_completed signal which triggers auto-refresh
                            self._context_menu.menu_coordinator.prompt_store_service.cancel_current_execution()
                        event.accept()
                        return

                    # Block if disabled (but allow if this is the recording action for stopping)
                    if self._disable_reason and not self._is_recording_action:
                        event.ignore()
                        return

                    if self._menu_item.enabled or self._is_recording_action:
                        if self._context_menu.execution_callback:
                            shift_pressed = bool(
                                QApplication.keyboardModifiers() & Qt.ShiftModifier
                            )
                            self._context_menu.execution_callback(
                                self._menu_item, shift_pressed
                            )
                            # Close the menu after execution
                            if self._context_menu.menu:
                                self._context_menu.menu.close()
                            if self._context_menu.focus_window:
                                self._context_menu.focus_window.hide()
                            # Restore focus after execution
                            self._context_menu._focus_restore_pending = True
                            QTimer.singleShot(
                                100, self._context_menu._restore_focus_with_cleanup
                            )

            def enterEvent(self, event):
                if self._menu_item.enabled or self._is_recording_action or self._is_executing_action:
                    self._is_highlighted = True
                    self._update_style(True)
                    self._context_menu.hovered_widgets.add(self)
                super().enterEvent(event)

            def leaveEvent(self, event):
                if (self._menu_item.enabled or self._is_recording_action or self._is_executing_action) and not self.hasFocus():
                    self._is_highlighted = False
                    self._update_style(False)
                    self._context_menu.hovered_widgets.discard(self)
                super().leaveEvent(event)

            def focusInEvent(self, event):
                if self._menu_item.enabled or self._is_recording_action or self._is_executing_action:
                    self._is_highlighted = True
                    self._update_style(True)
                super().focusInEvent(event)

            def focusOutEvent(self, event):
                if self._menu_item.enabled or self._is_recording_action or self._is_executing_action:
                    self._is_highlighted = False
                    self._update_style(False)
                super().focusOutEvent(event)

            def keyPressEvent(self, event):
                if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                    # If this is the executing action, Enter cancels execution
                    if self._is_executing_action:
                        if hasattr(self._context_menu, 'menu_coordinator') and self._context_menu.menu_coordinator:
                            # Cancel will emit execution_completed signal which triggers auto-refresh
                            self._context_menu.menu_coordinator.prompt_store_service.cancel_current_execution()
                        event.accept()
                        return

                    if self._menu_item.enabled or self._is_recording_action:
                        if self._context_menu.execution_callback:
                            shift_pressed = bool(
                                QApplication.keyboardModifiers() & Qt.ShiftModifier
                            )
                            self._context_menu.execution_callback(
                                self._menu_item, shift_pressed
                            )
                            # Close the menu after execution
                            if self._context_menu.menu:
                                self._context_menu.menu.close()
                            if self._context_menu.focus_window:
                                self._context_menu.focus_window.hide()
                            # Restore focus after execution
                            self._context_menu._focus_restore_pending = True
                            QTimer.singleShot(
                                100, self._context_menu._restore_focus_with_cleanup
                            )
                        event.accept()
                else:
                    super().keyPressEvent(event)

        widget = ClickableMenuItem(item.label, item, self)

        # Apply disabled state if needed
        disable_reason = item.data.get("disable_reason") if item.data else None
        is_recording_action = item.data.get("is_recording_action", False) if item.data else False
        is_executing_action = item.data.get("is_executing_action", False) if item.data else False

        if is_executing_action:
            widget.set_executing_action_state(True)
        elif is_recording_action:
            widget.set_recording_action_state(True)
        elif disable_reason:
            widget.set_disabled_state(disable_reason)
        elif not item.enabled:
            widget.setEnabled(False)

        # Set tooltip if available
        if hasattr(item, "tooltip") and item.tooltip:
            widget.setToolTip(item.tooltip)

        action = QWidgetAction(menu)
        action.setDefaultWidget(widget)

        # Keep action enabled so buttons can be clicked
        # Disabling is handled at widget level via set_disabled_state()
        action.setEnabled(True)

        return action

    def eventFilter(self, obj, event):
        """Filter events to detect shift key state and enable keyboard navigation."""
        if not self.event_filter_installed:
            return False

        if isinstance(obj, QMenu):
            if event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Shift:
                    self.shift_pressed = True
                elif event.key() == Qt.Key_Escape:
                    # Cancel number input on Escape
                    self._cancel_number_input()
                    return False
                elif event.key() in (
                    Qt.Key_Up,
                    Qt.Key_Down,
                    Qt.Key_Return,
                    Qt.Key_Enter,
                    Qt.Key_Space,
                ):
                    # Let QMenu handle these keys natively
                    return False
                elif event.key() >= Qt.Key_0 and event.key() <= Qt.Key_9:
                    # Handle number key presses for prompt execution (including 0 for multi-digait)
                    digit = event.key() - Qt.Key_0
                    self.shift_pressed = bool(
                        QApplication.keyboardModifiers() & Qt.ShiftModifier
                    )
                    is_alternative = self.shift_pressed
                    if self._handle_number_input(obj, str(digit), is_alternative):
                        return True
                else:
                    # Handle any key that produces a digit character (including shifted numbers)
                    text = event.text()
                    if text and len(text) == 1 and text.isdigit():
                        self.shift_pressed = bool(
                            QApplication.keyboardModifiers() & Qt.ShiftModifier
                        )
                        is_alternative = self.shift_pressed
                        if self._handle_number_input(obj, text, is_alternative):
                            return True
                    # Also handle shifted number characters (!@#$%^&*()
                    elif text in "!@#$%^&*()":
                        shift_char_to_number = {
                            "!": "1",
                            "@": "2",
                            "#": "3",
                            "$": "4",
                            "%": "5",
                            "^": "6",
                            "&": "7",
                            "*": "8",
                            "(": "9",
                            ")": "0",
                        }
                        digit = shift_char_to_number.get(text)
                        if digit:
                            if self._handle_number_input(obj, digit, True):
                                return True
            elif event.type() == QEvent.KeyRelease:
                if event.key() == Qt.Key_Shift:
                    self.shift_pressed = False
            elif event.type() == QEvent.MouseButtonPress:
                current_shift = bool(
                    QApplication.keyboardModifiers() & Qt.ShiftModifier
                )
                if current_shift != self.shift_pressed:
                    self.shift_pressed = current_shift

                if event.button() == Qt.RightButton and self.shift_pressed:
                    action = obj.actionAt(event.pos())
                    if action and hasattr(action, "_menu_item"):
                        self._handle_shift_right_click(action)
                        return True
            elif event.type() == QEvent.Show:
                self.shift_pressed = bool(
                    QApplication.keyboardModifiers() & Qt.ShiftModifier
                )
            elif event.type() == QEvent.Leave:
                self._clear_all_hover_states()

        return False

    def _handle_number_input(self, menu, digit, is_alternative):
        """Handle number input with debouncing for multi-digit numbers."""
        # Add digit to buffer
        self.number_input_buffer += digit

        # Cancel previous timer if exists
        if self.number_timer:
            self.number_timer.stop()
            self.number_timer.deleteLater()

        # Create new timer to execute after 300ms
        self.number_timer = QTimer()
        self.number_timer.setSingleShot(True)
        self.number_timer.timeout.connect(
            lambda: self._execute_buffered_number(menu, is_alternative)
        )
        self.number_timer.start(self.number_input_debounce_ms)

        return True

    def _execute_buffered_number(self, menu, is_alternative):
        """Execute the number from the buffer."""
        if not self.number_input_buffer:
            return

        try:
            number = int(self.number_input_buffer)
            if number >= 1:  # Allow any number >= 1
                self._handle_number_key_press(menu, number, is_alternative)
        except ValueError:
            pass
        finally:
            # Clear buffer
            self.number_input_buffer = ""
            if self.number_timer:
                self.number_timer.deleteLater()
                self.number_timer = None

    def _cancel_number_input(self):
        """Cancel pending number input."""
        if self.number_timer:
            self.number_timer.stop()
            self.number_timer.deleteLater()
            self.number_timer = None
        self.number_input_buffer = ""

    def _on_menu_about_to_hide(self):
        """Handle menu about to hide - cleanup number timer and restore focus."""
        # Disconnect from execution signal
        self._disconnect_execution_signal()
        self._last_menu_position = None

        if self.number_timer:
            self.number_timer.stop()
            self.number_timer.deleteLater()
            self.number_timer = None
        self.number_input_buffer = ""
        self.shift_pressed = False

        # Restore focus when menu closes (only if not already restoring via execution)
        if not hasattr(self, "_focus_restore_pending"):
            self._focus_restore_pending = True
            QTimer.singleShot(50, self._restore_focus_with_cleanup)

    def _handle_number_key_press(self, menu, number, is_alternative):
        """Handle number key press to execute prompts by index."""
        # Find prompt items and their indices
        prompt_items = []
        for action in menu.actions():
            if isinstance(action, QWidgetAction):
                widget = action.defaultWidget()
                if (
                    hasattr(widget, "_menu_item")
                    and widget._menu_item.item_type.name == "PROMPT"
                ):
                    menu_item = widget._menu_item
                    if hasattr(menu_item, "data") and "menu_index" in menu_item.data:
                        prompt_items.append(
                            (menu_item.data["menu_index"], widget, menu_item)
                        )

        # Sort by menu index
        prompt_items.sort(key=lambda x: x[0])

        # Check if the number is valid
        if 1 <= number <= len(prompt_items):
            _, widget, menu_item = prompt_items[number - 1]

            # Hide menu before execution
            menu.hide()

            # Execute the prompt using the context menu's execution callback
            if self.execution_callback:
                self.execution_callback(menu_item, is_alternative)
                # Close the menu after execution and restore focus
                if self.menu:
                    self.menu.close()
                if self.focus_window:
                    self.focus_window.hide()
                # Restore focus after execution
                self._focus_restore_pending = True
                QTimer.singleShot(50, self._restore_focus_with_cleanup)

            return True

        return False

    def _handle_shift_right_click(self, action):
        """Handle shift + right click for alternative actions."""
        menu_item = getattr(action, "_menu_item", None)
        if menu_item and self.execution_callback:
            self.execution_callback(menu_item, True)
            if self.menu:
                self.menu.close()
            if self.focus_window:
                self.focus_window.hide()
            # Restore focus after execution
            self._focus_restore_pending = True
            QTimer.singleShot(50, self._restore_focus_with_cleanup)

    def _clear_all_hover_states(self):
        """Clear all hover states."""
        widgets_to_clear = list(self.hovered_widgets)
        for widget in widgets_to_clear:
            try:
                if not sip.isdeleted(widget) and hasattr(widget, "_normal_style"):
                    widget.setStyleSheet(widget._normal_style)
                if widget in self.hovered_widgets:
                    self.hovered_widgets.remove(widget)
            except (RuntimeError, AttributeError):
                if widget in self.hovered_widgets:
                    self.hovered_widgets.remove(widget)

    def _cleanup_deleted_widgets(self):
        """Clean up deleted widget references."""
        widgets_to_remove = []
        for widget in self.hovered_widgets:
            try:
                if sip.isdeleted(widget):
                    widgets_to_remove.append(widget)
            except RuntimeError:
                widgets_to_remove.append(widget)

        for widget in widgets_to_remove:
            self.hovered_widgets.discard(widget)

    def _store_qt_active_window(self):
        """Store Qt active window reference for focus restoration."""
        try:
            self.qt_active_window = QApplication.activeWindow()
        except Exception:
            self.qt_active_window = None

    def _store_active_window(self):
        """Store information about the currently active external application."""
        try:
            if platform.system() == "Darwin":  # macOS
                # Use AppleScript to get the frontmost application
                script = """
                tell application "System Events"
                    set frontApp to name of first application process whose frontmost is true
                    set frontAppPath to POSIX path of (file of first application process whose frontmost is true)
                end tell
                return frontApp & "|||" & frontAppPath
                """
                result = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if result.returncode == 0:
                    app_info = result.stdout.strip().split("|||")
                    self.original_active_window = {
                        "name": app_info[0],
                        "path": app_info[1] if len(app_info) > 1 else None,
                    }
            elif platform.system() == "Linux":  # Linux
                # Use xdotool to get the active window
                try:
                    # Get active window ID
                    result = subprocess.run(
                        ["xdotool", "getactivewindow"],
                        capture_output=True,
                        text=True,
                        timeout=1,
                    )
                    if result.returncode == 0:
                        window_id = result.stdout.strip()

                        # Get window info
                        result = subprocess.run(
                            ["xdotool", "getwindowname", window_id],
                            capture_output=True,
                            text=True,
                            timeout=1,
                        )
                        window_name = (
                            result.stdout.strip()
                            if result.returncode == 0
                            else "Unknown"
                        )

                        # Get process info
                        result = subprocess.run(
                            ["xdotool", "getwindowpid", window_id],
                            capture_output=True,
                            text=True,
                            timeout=1,
                        )
                        pid = result.stdout.strip() if result.returncode == 0 else None

                        self.original_active_window = {
                            "window_id": window_id,
                            "name": window_name,
                            "pid": pid,
                        }
                except FileNotFoundError:
                    # xdotool not available, try xprop as fallback
                    result = subprocess.run(
                        ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
                        capture_output=True,
                        text=True,
                        timeout=1,
                    )
                    if result.returncode == 0:
                        # Extract window ID from xprop output
                        import re

                        match = re.search(r"0x[0-9a-fA-F]+", result.stdout)
                        if match:
                            window_id = match.group()
                            self.original_active_window = {
                                "window_id": window_id,
                                "name": "Unknown",
                                "pid": None,
                            }
        except Exception as e:
            print(f"Error storing active window: {e}")
            self.original_active_window = None

    def _restore_focus(self):
        """Restore focus to the original application that was active before menu was shown."""
        try:
            # First try Qt-native focus restoration (fast)
            if self.qt_active_window and not sip.isdeleted(self.qt_active_window):
                self.qt_active_window.activateWindow()
                self.qt_active_window.raise_()
                return

            # If Qt window is not available, try external focus restoration
            if not self.original_active_window:
                return

            if platform.system() == "Darwin":  # macOS
                app_name = self.original_active_window.get("name")
                if app_name and app_name not in (
                    "Python",
                    "Prompter",
                ):  # Don't try to activate our own app
                    try:
                        # First try by application name
                        script = f'''
                        tell application "{app_name}"
                            activate
                        end tell
                        '''
                        result = subprocess.run(
                            ["osascript", "-e", script],
                            capture_output=True,
                            text=True,
                            timeout=2,
                        )

                        # If that fails, try by process name
                        if result.returncode != 0:
                            script2 = f'''
                            tell application "System Events"
                                set frontmost of first process whose name is "{app_name}" to true
                            end tell
                            '''
                            subprocess.run(
                                ["osascript", "-e", script2],
                                capture_output=True,
                                text=True,
                                timeout=2,
                            )
                    except Exception as e:
                        print(f"Error restoring macOS focus to {app_name}: {e}")
            elif platform.system() == "Linux":  # Linux
                window_id = self.original_active_window.get("window_id")
                if window_id:
                    try:
                        # Try xdotool first
                        subprocess.run(
                            ["xdotool", "windowactivate", window_id],
                            capture_output=True,
                            text=True,
                            timeout=1,
                        )
                    except FileNotFoundError:
                        # xdotool not available, try wmctrl as fallback
                        try:
                            subprocess.run(
                                ["wmctrl", "-ia", window_id],
                                capture_output=True,
                                text=True,
                                timeout=1,
                            )
                        except FileNotFoundError:
                            # Neither tool available, try xprop method
                            subprocess.run(
                                [
                                    "xprop",
                                    "-id",
                                    window_id,
                                    "-f",
                                    "_NET_ACTIVE_WINDOW",
                                    "32a",
                                    "-set",
                                    "_NET_ACTIVE_WINDOW",
                                    window_id,
                                ],
                                capture_output=True,
                                text=True,
                                timeout=1,
                            )
        except Exception as e:
            print(f"Error restoring focus: {e}")

    def _restore_focus_with_cleanup(self):
        """Restore focus and clear the pending flag."""
        try:
            self._restore_focus()
        finally:
            # Clear the pending flag
            if hasattr(self, "_focus_restore_pending"):
                delattr(self, "_focus_restore_pending")
