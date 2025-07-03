"""Settings-based prompt provider that reads from configuration files."""

from typing import List, Dict, Any, Optional
from core.models import PromptData, PresetData
from core.exceptions import ProviderError
from core.services import SettingsService


class SettingsPromptProvider:
    """Prompt provider that reads from settings configuration files."""

    def __init__(self, settings_path: Optional[str] = None):
        self.settings_service = SettingsService(settings_path)
        self._prompts_cache: Optional[List[PromptData]] = None
        self._presets_cache: Optional[List[PresetData]] = None

    def get_prompts(self) -> List[PromptData]:
        """Get prompts from settings configuration."""
        try:
            if self._prompts_cache is None:
                self._load_prompts()
            return self._prompts_cache or []
        except Exception as e:
            raise ProviderError(f"Failed to get prompts from settings: {str(e)}") from e

    def get_presets(self) -> List[PresetData]:
        """Get presets from settings configuration."""
        try:
            if self._presets_cache is None:
                self._load_presets()
            return self._presets_cache or []
        except Exception as e:
            raise ProviderError(f"Failed to get presets from settings: {str(e)}") from e

    def get_prompt_details(self, prompt_id: str) -> Optional[PromptData]:
        """Get detailed information about a specific prompt."""
        try:
            prompts = self.get_prompts()
            for prompt in prompts:
                if prompt.id == prompt_id:
                    return prompt
            return None
        except Exception as e:
            raise ProviderError(f"Failed to get prompt details: {str(e)}") from e

    def refresh(self) -> None:
        """Refresh data from settings file."""
        self._prompts_cache = None
        self._presets_cache = None
        self.settings_service.reload_settings()

    def _load_prompts(self) -> None:
        """Load prompts from settings configuration."""
        try:
            settings = self.settings_service.get_settings()
            self._prompts_cache = []

            for prompt_config in settings.prompts:
                prompt_data = self.settings_service.convert_to_prompt_data(
                    prompt_config
                )
                self._prompts_cache.append(prompt_data)

        except Exception as e:
            raise ProviderError(
                f"Failed to load prompts from settings: {str(e)}"
            ) from e

    def _load_presets(self) -> None:
        """Load presets from settings configuration."""
        self._presets_cache = []

    def get_model_configs(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get model configurations from settings."""
        try:
            return self.settings_service.get_model_configs()
        except Exception as e:
            raise ProviderError(f"Failed to get model configs: {str(e)}") from e

    def get_prompt_messages(self, prompt_id: str) -> Optional[List[Dict[str, str]]]:
        """Get the raw message structure for a prompt."""
        try:
            settings = self.settings_service.get_settings()

            for prompt_config in settings.prompts:
                if prompt_config.id == prompt_id:
                    messages = []
                    for message in prompt_config.messages:
                        content = self.settings_service.resolve_message_content(message)
                        messages.append({"role": message.role, "content": content})
                    return messages

            return None
        except Exception as e:
            raise ProviderError(f"Failed to get prompt messages: {str(e)}") from e
