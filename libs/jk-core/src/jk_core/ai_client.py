from google import genai
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

    def generate(self, prompt: str, system_instruction: str = None, model_name: str = None):
        if not self.client:
            self._refresh_client()

        target_model = model_name or DEFAULT_MODEL

        try:
            response = self.client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction
                ) if system_instruction else None
            )
            # CHANGE: Extract token counts and record usage
            meta = response.usage_metadata
            if meta:
                self.km.record_usage(
                    key_id=self.key_id,
                    model_id=target_model,
                    input_tokens=meta.prompt_token_count,
                    output_tokens=meta.candidates_token_count
                )
            return response.text
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                self.km.mark_exhausted(self.key_id)
                self._refresh_client()
                return self.generate(prompt, system_instruction)
            raise e


    def generate_with_meta(self, prompt: str, system_instruction: str = None, model_name: str = None):
        """
        Generates content and returns a tuple of (text, usage_metadata).
        """
        if not self.client:
            self._refresh_client()

        target_model = model_name or DEFAULT_MODEL

        try:
            response = self.client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction
                ) if system_instruction else None
            )

            meta = response.usage_metadata
            if meta:
                self.km.record_usage(
                    key_id=self.key_id,
                    model_id=target_model,
                    input_tokens=meta.prompt_token_count,
                    output_tokens=meta.candidates_token_count
                )

            return response.text, meta

        except Exception as e:
            # Handle rotation logic as before...
            if "429" in str(e) or "quota" in str(e).lower():
                self.km.mark_exhausted(self.key_id)
                self._refresh_client()
                return self.generate_with_meta(prompt, system_instruction, model_name)
            raise e

    def generate_with_history(self, history: list, system_instruction: str = None, model_name: str = None):
        if not self.client:
            self._refresh_client()

        target_model = model_name or DEFAULT_MODEL
        formatted_history = []
        for turn in history:
            raw_parts = turn.get("parts", [""])
            # If it's a list, take the first element; otherwise, use as is
            text_str = raw_parts[0] if isinstance(raw_parts, list) else str(raw_parts)

            formatted_history.append(
                types.Content(
                    role=turn["role"],
                    parts=[types.Part(text=text_str)] # Now it's a valid string
                )
            )

        try:
            # If formatted_history is empty, the SDK throws 'contents are required'
            # We must ensure there is at least one message
            if not formatted_history:
                raise ValueError("No history provided for generation.")

            response = self.client.models.generate_content(
                model=target_model,
                contents=formatted_history,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction
                ) if system_instruction else None
            )

            meta = response.usage_metadata
            return response.text, meta

        except Exception as e:
            error_str = str(e).lower()
            # 429 = Quota/Rate Limit
            if "429" in error_str or "quota" in error_str:
                # 1. First, try to rotate KEY for the SAME model
                try:
                    self.km.mark_exhausted(self.key_id) # Mark current key/model pair (Logic needed in KM)
                    self._refresh_client()
                    return self.generate_with_history(history, system_instruction, target_model)
                except RuntimeError:
                    # 2. If NO KEYS left for this model, raise a specific error to trigger MODEL rotation
                    raise PermissionError(f"MODEL_EXHAUSTED:{target_model}")
            raise e

