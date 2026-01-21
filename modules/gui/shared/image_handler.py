"""Image chip management for dialog sections."""

from collections.abc import Callable

from PySide6.QtWidgets import QHBoxLayout, QWidget

from core.context_manager import ContextItem, ContextItemType
from modules.gui.shared.widgets import ImageChipWidget


class SectionImageHandler:
    """Handles image chips for context/message/reply sections.

    Manages the creation, deletion, and clipboard operations for image chips
    across different dialog sections.
    """

    def __init__(self, clipboard_manager=None):
        self.clipboard_manager = clipboard_manager

    def rebuild_chips(
        self,
        images: list[ContextItem],
        container: QWidget,
        layout: QHBoxLayout,
        chips_list: list[ImageChipWidget],
        on_delete: Callable[[int], None],
        on_copy: Callable[[int], None],
    ) -> list[ImageChipWidget]:
        """Rebuild image chips from current image list.

        Args:
            images: List of ContextItem images to display
            container: Container widget for the images
            layout: Layout to add chips to
            chips_list: List to store chip references (will be cleared)
            on_delete: Callback when delete is requested (receives index)
            on_copy: Callback when copy is requested (receives index)

        Returns:
            Updated list of ImageChipWidget instances
        """
        for chip in chips_list:
            chip.deleteLater()
        chips_list.clear()

        while layout.count():
            layout.takeAt(0)

        if not images:
            container.hide()
            return chips_list

        container.show()

        for idx, item in enumerate(images):
            chip = ImageChipWidget(
                index=idx,
                image_number=idx + 1,
                image_data=item.data or "",
                media_type=item.media_type or "image/png",
            )
            chip.delete_requested.connect(on_delete)
            chip.copy_requested.connect(on_copy)
            chips_list.append(chip)
            layout.addWidget(chip)

        layout.addStretch()
        return chips_list

    def paste_from_clipboard(
        self,
        images_list: list[ContextItem],
        on_rebuild: Callable[[], None],
        on_state_save: Callable[[], None] | None = None,
    ) -> bool:
        """Paste image from clipboard to images list.

        Args:
            images_list: List to append new image to
            on_rebuild: Callback to rebuild chips after paste
            on_state_save: Optional callback to save state before modification

        Returns:
            True if image was pasted, False otherwise
        """
        if not self.clipboard_manager or not self.clipboard_manager.has_image():
            return False

        image_data = self.clipboard_manager.get_image_data()
        if image_data:
            base64_data, media_type = image_data
            if on_state_save:
                on_state_save()
            new_image = ContextItem(
                item_type=ContextItemType.IMAGE,
                data=base64_data,
                media_type=media_type,
            )
            images_list.append(new_image)
            on_rebuild()
            return True
        return False

    def delete_image(
        self,
        images_list: list[ContextItem],
        index: int,
        on_rebuild: Callable[[], None],
        on_state_save: Callable[[], None] | None = None,
    ) -> bool:
        """Delete image at index from images list.

        Args:
            images_list: List to delete image from
            index: Index of image to delete
            on_rebuild: Callback to rebuild chips after delete
            on_state_save: Optional callback to save state before modification

        Returns:
            True if image was deleted, False otherwise
        """
        if 0 <= index < len(images_list):
            if on_state_save:
                on_state_save()
            del images_list[index]
            on_rebuild()
            return True
        return False

    def copy_image(self, chips_list: list[ImageChipWidget], index: int) -> bool:
        """Copy image at index to clipboard.

        Args:
            chips_list: List of ImageChipWidget instances
            index: Index of chip to copy

        Returns:
            True if image was copied, False otherwise
        """
        if 0 <= index < len(chips_list):
            chips_list[index].copy_to_clipboard()
            return True
        return False
