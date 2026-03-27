import yaml
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from jk_core.constants import SHARED_CONFIG_PATH

class KeyManager:
    def __init__(self, provider: str, tier: str = "free"):
        self.provider = provider
        self.tier = tier
        
        # Use the shared path from constants
        self.config_dir = Path(SHARED_CONFIG_PATH)
        self.keys_file = self.config_dir / "keys.yaml"
        self.state_file = self.config_dir / "state.json"
        
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _load_keys(self) -> list:
        if not self.keys_file.exists():
            return []
        with open(self.keys_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            # Accessing: data['google']['free']
            provider_data = data.get(self.provider, {})
            return provider_data.get(self.tier, [])

    def _load_state(self) -> dict:
        """Load dynamic state (exhaustion/cooldowns) from state.json."""
        if not self.state_file.exists():
            return {}
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return {}

    def _save_state(self, state: dict):
        """Persist the current exhaustion state to disk."""
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def get_available_key(self) -> (str, str):
        """
        Retrieves the first available API key that is not currently cooling down.
        Returns: (api_key_string, key_id_string) or (None, None)
        """
        all_keys = self._load_keys()
        state = self._load_state()
        now = datetime.now(timezone.utc)

        for k in all_keys:
            key_id = k.get('id')
            key_val = k.get('key')

            if not key_id or not key_val:
                continue

            key_state = state.get(key_id, {})
            reset_at_str = key_state.get("reset_at")

            # If no reset time is set, the key is fresh
            if not reset_at_str:
                return key_val, key_id

            # Check if the cooldown period has passed
            try:
                reset_at = datetime.fromisoformat(reset_at_str)

                # Double check the reset_at has timezone info, if not, force UTC
                if reset_at.tzinfo is None:
                    reset_at = reset_at.replace(tzinfo=timezone.utc)
                if now > reset_at:
                    return key_val, key_id
            except ValueError:
                # If timestamp is corrupted, assume key is available
                return key_val, key_id

        return None, None

    def mark_exhausted(self, key_id: str):
        """Calculates the next reset time based on provider standards."""
        state = self._load_state()
        now_utc = datetime.now(timezone.utc)

        if self.provider == "google":
            # Google resets at 00:00 Pacific Time (PT is UTC-8 or UTC-7)
            # Simplest safe approach: Reset at 00:00 PT (approx 08:00 UTC)
            # For a more robust app, we'll target the next 08:00 UTC
            reset_time = now_utc.replace(hour=8, minute=0, second=0, microsecond=0)
            if now_utc >= reset_time:
                reset_time += timedelta(days=1)
        else:
            # Default to 00:00 UTC for OpenAI/Anthropic
            reset_time = (now_utc + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        state[key_id] = {
            "reset_at": reset_time.isoformat(),
            "status": "exhausted",
            "updated_at": now_utc.isoformat()
        }
        self._save_state(state)

    # libs/jk-core/src/jk_core/key_manager.py

    def record_usage(self, key_id: str, model_id: str, input_tokens: int, output_tokens: int):
        """
        CHANGE: Increments request and token counts for a specific key/model pair.
        Stored in state.json under a 'usage' key.
        """
        state = self._load_state()
        
        # Ensure the 'usage' section exists
        if "usage" not in state:
            state["usage"] = {}
        if key_id not in state["usage"]:
            state["usage"][key_id] = {"models": {}}
            
        models_usage = state["usage"][key_id]["models"]
        
        # Initialize or update the specific model entry
        if model_id not in models_usage:
            models_usage[model_id] = {
                "request_count": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "last_used": None
            }
            
        entry = models_usage[model_id]
        entry["request_count"] += 1
        entry["total_input_tokens"] += input_tokens
        entry["total_output_tokens"] += output_tokens
        entry["last_used"] = datetime.now(timezone.utc).isoformat()
        
        self._save_state(state)


