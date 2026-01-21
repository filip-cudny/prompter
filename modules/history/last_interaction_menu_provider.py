"""Menu provider for last interaction section (input/output/transcription)."""


from core.models import MenuItem, MenuItemType


class LastInteractionMenuProvider:
    """Provides menu items for the last interaction section."""

    def __init__(
        self,
        history_service,
        notification_manager=None,
        clipboard_manager=None,
    ):
        self.history_service = history_service
        self.notification_manager = notification_manager
        self.clipboard_manager = clipboard_manager

    def get_menu_items(self) -> list[MenuItem]:
        """Return menu items for the last interaction section."""
        last_interaction_item = MenuItem(
            id="last_interaction_section",
            label="Last interaction",
            item_type=MenuItemType.LAST_INTERACTION,
            action=lambda: None,
            data={
                "history_service": self.history_service,
                "notification_manager": self.notification_manager,
                "clipboard_manager": self.clipboard_manager,
            },
            enabled=True,
            separator_after=True,
        )
        return [last_interaction_item]

    def refresh(self) -> None:
        """Refresh the provider's data."""
        pass
