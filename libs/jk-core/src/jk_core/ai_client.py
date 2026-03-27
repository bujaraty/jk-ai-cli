# libs/jk-core/src/jk_core/ai_client.py
from google import genai  # Use the correct namespace
from google.genai import types
from jk_core.key_manager import KeyManager
from jk_core.constants import DEFAULT_MODEL

class GeminiClient:
    def __init__(self, tier: str = "free"):
        self.km = KeyManager(provider="google", tier=tier)
        self.client = None
        self.key_id = None

    def _refresh_client(self):
        api_key, key_id = self.km.get_available_key()
        if not api_key:
            raise RuntimeError("All Google API keys are exhausted.")

        self.key_id = key_id
        print(f"🔄 Switched to Key: {self.key_id}")
        # Initialize with the correct client class
        self.client = genai.Client(api_key=api_key)

    def generate(self, prompt: str, system_instruction: str = None):
        if not self.client:
            self._refresh_client()

        try:
            response = self.client.models.generate_content(
                model=DEFAULT_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction
                ) if system_instruction else None
            )
            return response.text
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                self.km.mark_exhausted(self.key_id)
                self._refresh_client()
                return self.generate(prompt, system_instruction)
            raise e

