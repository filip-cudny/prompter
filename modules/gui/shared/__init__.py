"""Shared GUI components and utilities.

This module provides common widgets, dialogs, and utilities used across
multiple GUI components.
"""

# Dialog styles and constants
from modules.gui.shared.dialog_styles import (
    DIALOG_SHOW_DELAY_MS,
    TEXT_CHANGE_DEBOUNCE_MS,
    DEFAULT_WRAPPED_HEIGHT,
    QWIDGETSIZE_MAX,
    DIALOG_CONTENT_MARGINS,
    SCROLL_CONTENT_MARGINS,
    SCROLL_CONTENT_SPACING,
    BUTTON_ROW_SPACING,
    DEFAULT_DIALOG_SIZE,
    MIN_DIALOG_SIZE,
    SMALL_DIALOG_SIZE,
    SMALL_MIN_DIALOG_SIZE,
    COLOR_DIALOG_BG,
    COLOR_TEXT_EDIT_BG,
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
    COLOR_BORDER,
    COLOR_BUTTON_BG,
    COLOR_BUTTON_HOVER,
    COLOR_BUTTON_PRESSED,
    COLOR_BUTTON_DISABLED_BG,
    COLOR_BUTTON_DISABLED_TEXT,
    COLOR_SELECTION,
    COLOR_SCROLLBAR_HANDLE,
    COLOR_SCROLLBAR_HANDLE_HOVER,
    COLOR_TOOLTIP_BG,
    COLOR_TOOLTIP_BORDER,
    COLOR_COMBOBOX_ARROW,
    TOOLTIP_STYLE,
    SVG_CHEVRON_DOWN_PATH,
    SVG_CHEVRON_UP_PATH,
    COMBOBOX_STYLE,
    SPINBOX_STYLE,
    DIALOG_STYLESHEET,
    get_dialog_stylesheet,
    get_text_edit_content_height,
    apply_wrap_state,
    apply_section_size_policy,
    create_singleton_dialog_manager,
)

# Base dialog class
from modules.gui.shared.base_dialog import BaseDialog

# Context widgets
from modules.gui.shared.context_widgets import (
    IconButton,
    ContextChipBase,
    TextContextChip,
    ImageContextChip,
    ContextHeaderWidget,
    FlowLayout,
    ContextSectionWidget,
    LastInteractionChip,
    LastInteractionHeaderWidget,
    LastInteractionSectionWidget,
    SettingsSelectorChip,
    SettingsHeaderWidget,
    SettingsSectionWidget,
)

# Shared widgets
from modules.gui.shared.widgets import (
    ICON_BTN_STYLE,
    TEXT_EDIT_MIN_HEIGHT,
    CollapsibleSectionHeader,
    ImageChipWidget,
    create_text_edit,
    ExpandableTextSection,
    UndoRedoManager,
    ImageChipContainer,
)

# Undo/redo utilities
from modules.gui.shared.undo_redo import (
    perform_undo,
    perform_redo,
    save_state_if_changed,
    set_text_with_signal_block,
    TextEditUndoHelper,
)

# Image handler
from modules.gui.shared.image_handler import SectionImageHandler

__all__ = [
    # Dialog styles
    "DIALOG_SHOW_DELAY_MS",
    "TEXT_CHANGE_DEBOUNCE_MS",
    "DEFAULT_WRAPPED_HEIGHT",
    "QWIDGETSIZE_MAX",
    "DIALOG_CONTENT_MARGINS",
    "SCROLL_CONTENT_MARGINS",
    "SCROLL_CONTENT_SPACING",
    "BUTTON_ROW_SPACING",
    "DEFAULT_DIALOG_SIZE",
    "MIN_DIALOG_SIZE",
    "SMALL_DIALOG_SIZE",
    "SMALL_MIN_DIALOG_SIZE",
    "COLOR_DIALOG_BG",
    "COLOR_TEXT_EDIT_BG",
    "COLOR_TEXT",
    "COLOR_TEXT_SECONDARY",
    "COLOR_BORDER",
    "COLOR_BUTTON_BG",
    "COLOR_BUTTON_HOVER",
    "COLOR_BUTTON_PRESSED",
    "COLOR_BUTTON_DISABLED_BG",
    "COLOR_BUTTON_DISABLED_TEXT",
    "COLOR_SELECTION",
    "COLOR_SCROLLBAR_HANDLE",
    "COLOR_SCROLLBAR_HANDLE_HOVER",
    "COLOR_TOOLTIP_BG",
    "COLOR_TOOLTIP_BORDER",
    "COLOR_COMBOBOX_ARROW",
    "TOOLTIP_STYLE",
    "SVG_CHEVRON_DOWN_PATH",
    "SVG_CHEVRON_UP_PATH",
    "COMBOBOX_STYLE",
    "SPINBOX_STYLE",
    "DIALOG_STYLESHEET",
    "get_dialog_stylesheet",
    "get_text_edit_content_height",
    "apply_wrap_state",
    "apply_section_size_policy",
    "create_singleton_dialog_manager",
    # Base dialog
    "BaseDialog",
    # Context widgets
    "IconButton",
    "ContextChipBase",
    "TextContextChip",
    "ImageContextChip",
    "ContextHeaderWidget",
    "FlowLayout",
    "ContextSectionWidget",
    "LastInteractionChip",
    "LastInteractionHeaderWidget",
    "LastInteractionSectionWidget",
    "SettingsSelectorChip",
    "SettingsHeaderWidget",
    "SettingsSectionWidget",
    # Shared widgets
    "ICON_BTN_STYLE",
    "TEXT_EDIT_MIN_HEIGHT",
    "CollapsibleSectionHeader",
    "ImageChipWidget",
    "create_text_edit",
    "ExpandableTextSection",
    "UndoRedoManager",
    "ImageChipContainer",
    # Undo/redo
    "perform_undo",
    "perform_redo",
    "save_state_if_changed",
    "set_text_with_signal_block",
    "TextEditUndoHelper",
    # Image handler
    "SectionImageHandler",
]
