"""Prompt providers for different data sources."""

from typing import List, Dict, Any, Optional
from core.models import PromptData, PresetData
from core.exceptions import ProviderError
from api import PromptStoreAPI, APIError


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
                    source="api-provider",
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
                    source="api-provider",
                    metadata=preset_dict.get("metadata", {}),
                )
                presets.append(preset)
            except Exception as e:
                # Skip invalid presets but continue processing
                continue
        return presets
