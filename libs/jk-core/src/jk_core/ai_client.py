from google import genai
from google.genai import types
from jk_core.key_manager import KeyManager
from jk_core.constants import DEFAULT_MODEL

class GeminiClient:
    def __init__(self, tier: str = "free"):
        self.km = KeyManager(provider="google", tier=tier)
        self.client = None
        self.key_id = None

    def _execute_with_retry(self, fn, model_id: str):
        """Executes fn(), rotating keys on 429 up to len(keys) times."""
        max_attempts = len(self.km._load_keys()) or 3
        for attempt in range(max_attempts):
            try:
                if not self.client:
                    self._refresh_client(model_id=model_id)
                return fn()
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "quota" in error_str:
                    self.km.mark_exhausted(self.key_id, model_id)
                    try:
                        self._refresh_client(model_id=model_id)
                    except PermissionError:
                        raise PermissionError(f"MODEL_EXHAUSTED:{model_id}")
                else:
                    raise e
        raise PermissionError(f"MODEL_EXHAUSTED:{model_id}")

    def _refresh_client(self, model_id: str = None):
        # CHANGE: Pass the model_id to get_available_key
        api_key, key_id = self.km.get_available_key(model_id=model_id)
        if not api_key:
            # If we were specific and it failed, raise the error for chat.py fallback
            raise PermissionError(f"MODEL_EXHAUSTED:{model_id}")

        self.key_id = key_id
        print(f"🔄 Switched to Key: {self.key_id}")
        # Initialize with the correct client class
        self.client = genai.Client(api_key=api_key)

    def generate(self, prompt, system_instruction=None, model_name=None):
        target_model = model_name or DEFAULT_MODEL
        def fn():
            response = self.client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction
                ) if system_instruction else None
            )
            meta = response.usage_metadata
            if meta:
                self.km.record_usage(self.key_id, target_model,
                                     meta.prompt_token_count,
                                     meta.candidates_token_count)
            return response.text
        return self._execute_with_retry(fn, target_model)
    
    
    def generate_with_meta(self, prompt, system_instruction=None, model_name=None):
        target_model = model_name or DEFAULT_MODEL
        def fn():
            response = self.client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction
                ) if system_instruction else None
            )
            meta = response.usage_metadata
            if meta:
                self.km.record_usage(self.key_id, target_model,
                                     meta.prompt_token_count,
                                     meta.candidates_token_count)
            return response.text, meta
        return self._execute_with_retry(fn, target_model)
    
    def generate_with_history(self, history, system_instruction=None, model_name=None):
        target_model = model_name or DEFAULT_MODEL
        formatted_history = [
            types.Content(
                role=turn["role"],
                parts=[types.Part(text=(turn.get("parts", [""])[0]
                                        if isinstance(turn.get("parts"), list)
                                        else str(turn.get("parts", ""))))]
            )
            for turn in history
        ]
        if not formatted_history:
            raise ValueError("No history provided for generation.")
    
        def fn():
            response = self.client.models.generate_content(
                model=target_model,
                contents=formatted_history,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction
                ) if system_instruction else None
            )
            meta = response.usage_metadata
            return response.text, meta
        return self._execute_with_retry(fn, target_model)

    def embed_content(self, text: str, model_name: str = "models/gemini-embedding-001", task_type: str = "RETRIEVAL_QUERY"):
        """
        Modified to accept a dynamic model name for better fallback support.
        """
        if not self.client:
            self._refresh_client()

        try:
            # CHANGE: Use the model_name passed from the caller (Orchestrator)
            result = self.client.models.embed_content(
                model=model_name,
                contents=text,
                config=types.EmbedContentConfig(task_type=task_type)
            )

            # CHANGE: Access result differently based on SDK response structure
            # Some versions use embeddings[0].values, others use result.embeddings.values
            if hasattr(result, 'embeddings') and hasattr(result.embeddings, 'values'):
                return result.embeddings.values
            return result.embeddings[0].values

        except Exception as e:
            error_str = str(e).lower()
            if "404" in error_str:
                raise LookupError(f"Model {model_name} not found.")
            if "429" in error_str or "quota" in error_str:
                # CHANGE: Pass both key and model_name
                self.km.mark_exhausted(self.key_id, model_name)
                # CHANGE: Pass model_id
                self._refresh_client(model_id=model_name)
                return self.embed_content(text, model_name, task_type)
            raise e

