"""Prompt providers for different data sources."""

from typing import List, Dict, Any, Optional
from core.interfaces import PromptProvider
from core.models import PromptData, PresetData
from core.exceptions import ProviderError
from api import PromptStoreAPI, APIError
from .settings_prompt_provider import SettingsPromptProvider


class APIPromptProvider:
    """Prompt provider that uses the existing API client."""

    def __init__(self, api: PromptStoreAPI):
        self.api = api
        self._prompts_cache: Optional[List[PromptData]] = None
        self._presets_cache: Optional[List[PresetData]] = None

    def get_prompts(self) -> List[PromptData]:
        """Get prompts from the API."""
        try:
            if self._prompts_cache is None:
                self._load_prompts()
            return self._prompts_cache or []
        except Exception as e:
            raise ProviderError(f"Failed to get prompts: {str(e)}") from e

    def get_presets(self) -> List[PresetData]:
        """Get presets from the API."""
        try:
            if self._presets_cache is None:
                self._load_presets()
            return self._presets_cache or []
        except Exception as e:
            raise ProviderError(f"Failed to get presets: {str(e)}") from e

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
        """Refresh data from the API."""
        self._prompts_cache = None
        self._presets_cache = None

    def _load_data(self) -> None:
        """Load both prompts and presets from API."""
        try:
            data = self.api.get_all_data()
            self._prompts_cache = self._convert_prompts(data.get("prompts", []))
            self._presets_cache = self._convert_presets(data.get("presets", []))
        except APIError as e:
            raise ProviderError(f"API error: {str(e)}") from e

    def _load_prompts(self) -> None:
        """Load prompts from API."""
        try:
            prompts_data = self.api.get_prompts()
            self._prompts_cache = self._convert_prompts(prompts_data)
        except APIError as e:
            raise ProviderError(f"Failed to load prompts: {str(e)}") from e

    def _load_presets(self) -> None:
        """Load presets from API."""
        try:
            presets_data = self.api.get_presets()
            self._presets_cache = self._convert_presets(presets_data)
        except APIError as e:
            raise ProviderError(f"Failed to load presets: {str(e)}") from e

    def _convert_prompts(self, prompts_data: List[Dict[str, Any]]) -> List[PromptData]:
        """Convert API prompt data to PromptData objects."""
        prompts = []
        for prompt_dict in prompts_data:
            try:
                prompt = PromptData(
                    id=prompt_dict.get("id", ""),
                    name=prompt_dict.get("name", "Unnamed Prompt"),
                    content=prompt_dict.get("content", ""),
                    description=prompt_dict.get("description"),
                    tags=prompt_dict.get("tags", []),
                    created_at=prompt_dict.get("createdAt"),
                    updated_at=prompt_dict.get("updatedAt"),
                    metadata=prompt_dict.get("metadata", {}),
                )
                prompts.append(prompt)
            except Exception as e:
                # Skip invalid prompts but continue processing
                continue
        return prompts

    def _convert_presets(self, presets_data: List[Dict[str, Any]]) -> List[PresetData]:
        """Convert API preset data to PresetData objects."""
        presets = []
        for preset_dict in presets_data:
            try:
                preset = PresetData(
                    id=preset_dict.get("id", ""),
                    preset_name=preset_dict.get("presetName", "Unnamed Preset"),
                    prompt_id=preset_dict.get("promptId", ""),
                    temperature=preset_dict.get("temperature"),
                    model=preset_dict.get("model"),
                    context=preset_dict.get("context"),
                    placeholder_values=preset_dict.get("placeholderValues", {}),
                    metadata=preset_dict.get("metadata", {}),
                )
                presets.append(preset)
            except Exception as e:
                # Skip invalid presets but continue processing
                continue
        return presets


class LocalPromptProvider:
    """Prompt provider that reads from local files."""

    def __init__(self, prompts_dir: str = "prompts"):
        self.prompts_dir = prompts_dir
        self._prompts_cache: Optional[List[PromptData]] = None
        self._presets_cache: Optional[List[PresetData]] = None

    def get_prompts(self) -> List[PromptData]:
        """Get prompts from local files."""
        try:
            if self._prompts_cache is None:
                self._load_prompts()
            return self._prompts_cache or []
        except Exception as e:
            raise ProviderError(f"Failed to get local prompts: {str(e)}") from e

    def get_presets(self) -> List[PresetData]:
        """Get presets from local files."""
        try:
            if self._presets_cache is None:
                self._load_presets()
            return self._presets_cache or []
        except Exception as e:
            raise ProviderError(f"Failed to get local presets: {str(e)}") from e

    def get_prompt_details(self, prompt_id: str) -> Optional[PromptData]:
        """Get detailed information about a specific prompt."""
        try:
            prompts = self.get_prompts()
            for prompt in prompts:
                if prompt.id == prompt_id:
                    return prompt
            return None
        except Exception as e:
            raise ProviderError(f"Failed to get local prompt details: {str(e)}") from e

    def refresh(self) -> None:
        """Refresh data from local files."""
        self._prompts_cache = None
        self._presets_cache = None

    def _load_prompts(self) -> None:
        """Load prompts from local files."""
        import os
        import json

        self._prompts_cache = []

        if not os.path.exists(self.prompts_dir):
            return

        for filename in os.listdir(self.prompts_dir):
            if filename.endswith(".json"):
                try:
                    filepath = os.path.join(self.prompts_dir, filename)
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    if isinstance(data, dict) and "prompts" in data:
                        # File contains multiple prompts
                        for prompt_dict in data["prompts"]:
                            prompt = self._dict_to_prompt(prompt_dict)
                            if prompt:
                                self._prompts_cache.append(prompt)
                    elif isinstance(data, dict):
                        # File contains a single prompt
                        prompt = self._dict_to_prompt(data)
                        if prompt:
                            self._prompts_cache.append(prompt)
                except Exception:
                    # Skip invalid files
                    continue

    def _load_presets(self) -> None:
        """Load presets from local files."""
        import os
        import json

        self._presets_cache = []

        presets_dir = os.path.join(self.prompts_dir, "presets")
        if not os.path.exists(presets_dir):
            return

        for filename in os.listdir(presets_dir):
            if filename.endswith(".json"):
                try:
                    filepath = os.path.join(presets_dir, filename)
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    if isinstance(data, dict) and "presets" in data:
                        # File contains multiple presets
                        for preset_dict in data["presets"]:
                            preset = self._dict_to_preset(preset_dict)
                            if preset:
                                self._presets_cache.append(preset)
                    elif isinstance(data, dict):
                        # File contains a single preset
                        preset = self._dict_to_preset(data)
                        if preset:
                            self._presets_cache.append(preset)
                except Exception:
                    # Skip invalid files
                    continue

    def _dict_to_prompt(self, data: Dict[str, Any]) -> Optional[PromptData]:
        """Convert dictionary to PromptData."""
        try:
            return PromptData(
                id=data.get("id", ""),
                name=data.get("name", "Unnamed Prompt"),
                content=data.get("content", ""),
                description=data.get("description"),
                tags=data.get("tags", []),
                created_at=data.get("created_at"),
                updated_at=data.get("updated_at"),
                metadata=data.get("metadata", {}),
            )
        except Exception:
            return None

    def _dict_to_preset(self, data: Dict[str, Any]) -> Optional[PresetData]:
        """Convert dictionary to PresetData."""
        try:
            return PresetData(
                id=data.get("id", ""),
                preset_name=data.get("preset_name", "Unnamed Preset"),
                prompt_id=data.get("prompt_id", ""),
                temperature=data.get("temperature"),
                model=data.get("model"),
                context=data.get("context"),
                placeholder_values=data.get("placeholder_values", {}),
                metadata=data.get("metadata", {}),
            )
        except Exception:
            return None


class CompositePromptProvider:
    """Composite provider that combines multiple prompt providers."""

    def __init__(self, providers: List[PromptProvider]):
        self.providers = providers

    def get_prompts(self) -> List[PromptData]:
        """Get prompts from all providers."""
        all_prompts = []
        for provider in self.providers:
            try:
                prompts = provider.get_prompts()
                all_prompts.extend(prompts)
            except Exception:
                # Continue if one provider fails
                continue
        return all_prompts

    def get_presets(self) -> List[PresetData]:
        """Get presets from all providers."""
        all_presets = []
        for provider in self.providers:
            try:
                presets = provider.get_presets()
                all_presets.extend(presets)
            except Exception:
                # Continue if one provider fails
                continue
        return all_presets

    def get_prompt_details(self, prompt_id: str) -> Optional[PromptData]:
        """Get prompt details from the first provider that has it."""
        for provider in self.providers:
            try:
                details = provider.get_prompt_details(prompt_id)
                if details:
                    return details
            except Exception:
                # Continue if one provider fails
                continue
        return None

    def refresh(self) -> None:
        """Refresh all providers."""
        for provider in self.providers:
            try:
                provider.refresh()
            except Exception:
                # Continue if one provider fails
                continue

    def add_provider(self, provider: PromptProvider) -> None:
        """Add a new provider."""
        self.providers.append(provider)

    def remove_provider(self, provider: PromptProvider) -> None:
        """Remove a provider."""
        if provider in self.providers:
            self.providers.remove(provider)
