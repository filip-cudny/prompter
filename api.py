""" API """
import json
from typing import Optional, Dict, List, Any
import requests


class PromptStoreAPI:
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()

        if api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            })

    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                     data: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"

        try:
            if method.upper() == 'GET':
                response = self.session.get(url, params=params)
            elif method.upper() == 'POST':
                response = self.session.post(url, params=params, json=data)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise APIError(f"Request failed: {str(e)}") from e
        except json.JSONDecodeError:
            raise APIError("Invalid JSON response") from e

    def get_prompts(self) -> List[Dict[str, Any]]:
        response = self._make_request('GET', '/api/prompt-store', params={'type': 'prompts'})

        if not response.get('success'):
            raise APIError("Failed to fetch prompts")

        return response.get('prompts', [])

    def get_presets(self) -> List[Dict[str, Any]]:
        response = self._make_request('GET', '/api/prompt-store', params={'type': 'presets'})

        if not response.get('success'):
            raise APIError("Failed to fetch presets")

        return response.get('presets', [])

    def get_prompt_details(self, prompt_id: str) -> Dict[str, Any]:
        params = {
            'type': 'prompt-details',
            'id': prompt_id
        }
        response = self._make_request('GET', '/api/prompt-store', params=params)

        if not response.get('success'):
            raise APIError(f"Failed to fetch prompt details for ID: {prompt_id}")

        return {
            'prompt': response.get('prompt'),
            'presets': response.get('presets', [])
        }

    def execute_prompt(self, prompt_id: str, messages: List[Dict[str, str]],
                      context: Optional[str] = None, temperature: Optional[float] = None,
                      model: Optional[str] = None, streaming: bool = False,
                      placeholder_values: Optional[Dict[str, str]] = None,
                      preset_id: Optional[str] = None) -> Dict[str, Any]:
        data = {
            'promptId': prompt_id,
            'messages': messages,
            'streaming': streaming
        }

        if context:
            data['context'] = context
        if temperature is not None:
            data['temperature'] = temperature
        if model:
            data['model'] = model
        if placeholder_values:
            data['placeholderValues'] = placeholder_values
        if preset_id:
            data['presetId'] = preset_id

        response = self._make_request('POST', '/api/prompt-execute', data=data)

        if not response.get('success'):
            raise APIError("Failed to execute prompt")

        return response

    def execute_prompt_with_preset(self, prompt_id: str, preset_id: str,
                                  messages: List[Dict[str, str]],
                                  context: Optional[str] = None) -> Dict[str, Any]:
        return self.execute_prompt(
            prompt_id=prompt_id,
            messages=messages,
            context=context,
            preset_id=preset_id
        )

    def execute_prompt_with_placeholders(self, prompt_id: str,
                                       messages: List[Dict[str, str]],
                                       placeholder_values: Dict[str, str],
                                       context: Optional[str] = None) -> Dict[str, Any]:
        return self.execute_prompt(
            prompt_id=prompt_id,
            messages=messages,
            context=context,
            placeholder_values=placeholder_values
        )


class APIError(Exception):
    pass


def create_user_message(content: str) -> Dict[str, str]:
    return {
        'role': 'user',
        'content': content
    }


def create_system_message(content: str) -> Dict[str, str]:
    return {
        'role': 'system',
        'content': content
    }


def create_assistant_message(content: str) -> Dict[str, str]:
    return {
        'role': 'assistant',
        'content': content
    }
