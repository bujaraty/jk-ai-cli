from google import genai
from jk_core.providers.base import BaseAIProvider
from jk_core.key_manager import KeyManager

class GoogleProvider(BaseAIProvider):
    def __init__(self):
        self.km = KeyManager(provider="google")

    def _get_client(self):
        api_key, _ = self.km.get_available_key()
        if not api_key:
            raise RuntimeError("No Google API key available.")
        return genai.Client(api_key=api_key)

    def list_models(self) -> list:
        client = self._get_client()
        standardized_models = []
        
        for m in client.models.list():
            # This allows us to track the status of each specific action later.
            caps = {action: {"status": "PENDING", "last_probed": None, "error": None}
                    for action in m.supported_actions}

            standardized_models.append({
                "id": m.name,
                "provider": "google",
                "display_name": m.display_name,
                "description": m.description,
                "input_token_limit": m.input_token_limit,
                "output_token_limit": m.output_token_limit,
                "capabilities": caps
            })
        return standardized_models

    def generate_content(self, contents: str, config: dict = None) -> str:
        # Placeholder for your existing ai_client logic
        pass

