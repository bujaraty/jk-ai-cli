from google import genai
from google.genai import types
from jk_core.key_manager import KeyManager
from jk_core.constants import DEFAULT_MODEL

class GeminiClient:
    def __init__(self, tier: str = "free"):
        self.km = KeyManager(provider="google", tier=tier)
        self.client = None
        self.key_id = None

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
                # CHANGE: Pass both key and model
                self.km.mark_exhausted(self.key_id, target_model)
                # CHANGE: Pass model_id to only find keys with quota for THIS model
                self._refresh_client(model_id=target_model)
                return self.generate(prompt, system_instruction, model_name=target_model)
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
            if "429" in str(e) or "quota" in str(e).lower():
                # CHANGE: Pass both key and model
                self.km.mark_exhausted(self.key_id, target_model)
                # CHANGE: Pass model_id
                self._refresh_client(model_id=target_model)
                return self.generate_with_meta(prompt, system_instruction, model_name=target_model)
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
            if "429" in error_str or "quota" in error_str:
                try:
                    # CHANGE: Pass both key and model
                    self.km.mark_exhausted(self.key_id, target_model)
                    # CHANGE: Pass model_id
                    self._refresh_client(model_id=target_model)
                    return self.generate_with_history(history, system_instruction, target_model)
                except (RuntimeError, PermissionError):
                    # CHANGE: Re-raise specifically if no keys are left for THIS model
                    raise PermissionError(f"MODEL_EXHAUSTED:{target_model}")
            raise e

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

