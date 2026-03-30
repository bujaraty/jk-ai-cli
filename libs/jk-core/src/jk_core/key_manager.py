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

    def get_available_key(self, model_id: str = None):
        """
        Returns an available (key, key_id) pair.
        If model_id is provided, skips keys where that specific model is exhausted.
        If model_id is None (e.g. during probing), only checks that the key exists.
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

            # Skip model-level exhaustion check when no model_id is given (probe mode)
            if model_id is not None:
                model_usage = state.get("usage", {}).get(key_id, {}).get("models", {}).get(model_id, {})
                reset_at_str = model_usage.get("reset_at")

                if reset_at_str:
                    try:
                        reset_at = datetime.fromisoformat(reset_at_str)
                        if reset_at.tzinfo is None:
                            reset_at = reset_at.replace(tzinfo=timezone.utc)
                        if now < reset_at:
                            continue
                    except ValueError:
                        pass  # Corrupted date, assume okay

            return key_val, key_id

        return None, None

    def mark_exhausted(self, key_id: str, model_id: str):
        """
        REFACTORED: Marks only the specific MODEL as exhausted on this key.
        """
        state = self._load_state()
        now_utc = datetime.now(timezone.utc)

        # Calculate next reset (08:00 UTC for Google)
        reset_time = now_utc.replace(hour=8, minute=0, second=0, microsecond=0)
        if now_utc >= reset_time:
            reset_time += timedelta(days=1)

        # CHANGE: Navigate to the specific model entry in the usage block
        if "usage" not in state: state["usage"] = {}
        if key_id not in state["usage"]: state["usage"][key_id] = {"models": {}}

        models_usage = state["usage"][key_id]["models"]
        if model_id not in models_usage:
            models_usage[model_id] = {"request_count": 0, "total_input_tokens": 0, "total_output_tokens": 0}

        entry = models_usage[model_id]
        entry["status"] = "exhausted"
        entry["reset_at"] = reset_time.isoformat()
        entry["updated_at"] = now_utc.isoformat()

        self._save_state(state)

    def _append_usage_history(self, key_id: str, model_id: str, entry: dict, window_start: str):
        """Appends the completed window's usage as one line to usage_history.jsonl."""
        import json as _json
        history_file = self.config_dir / "usage_history.jsonl"
        # Parse date from window_start for the log line
        try:
            date_str = datetime.fromisoformat(window_start).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            date_str = "unknown"
        record = {
            "date":           date_str,
            "key_id":         key_id,
            "model_id":       model_id,
            "requests":       entry.get("request_count", 0),
            "input_tokens":   entry.get("total_input_tokens", 0),
            "output_tokens":  entry.get("total_output_tokens", 0),
        }
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(_json.dumps(record) + "\n")

    def _daily_reset_time(self, now_utc: datetime) -> datetime:
        """Returns the next 08:00 UTC reset boundary from now."""
        reset = now_utc.replace(hour=8, minute=0, second=0, microsecond=0)
        if now_utc >= reset:
            reset += timedelta(days=1)
        return reset

    def record_usage(self, key_id: str, model_id: str, input_tokens: int, output_tokens: int):
        """
        Increments daily request and token counts for a specific key/model pair.
        Resets counters automatically when the daily 08:00 UTC window rolls over,
        keeping accumulated totals in sync with the exhaustion reset cycle.
        """
        state = self._load_state()
        now_utc = datetime.now(timezone.utc)

        # Ensure nested structure exists
        if "usage" not in state:
            state["usage"] = {}
        if key_id not in state["usage"]:
            state["usage"][key_id] = {"models": {}}

        models_usage = state["usage"][key_id]["models"]

        # Initialize entry if new
        if model_id not in models_usage:
            models_usage[model_id] = {
                "request_count": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "status": "active",
                "last_used": None,
                "window_start": now_utc.isoformat(),
            }

        entry = models_usage[model_id]

        # Check if the daily window has rolled over — if so, reset counters
        reset_at_str = entry.get("reset_at")
        if reset_at_str:
            try:
                reset_at = datetime.fromisoformat(reset_at_str)
                if reset_at.tzinfo is None:
                    reset_at = reset_at.replace(tzinfo=timezone.utc)
                if now_utc >= reset_at:
                    # Archive the expiring window before resetting
                    self._append_usage_history(
                        key_id, model_id, entry,
                        window_start=entry.get("window_start", "")
                    )
                    entry["request_count"] = 0
                    entry["total_input_tokens"] = 0
                    entry["total_output_tokens"] = 0
                    entry["status"] = "active"
                    entry["window_start"] = now_utc.isoformat()
                    # Advance reset_at to the next window
                    entry["reset_at"] = self._daily_reset_time(now_utc).isoformat()
            except ValueError:
                pass  # Corrupted date, skip reset

        entry["request_count"] += 1
        entry["total_input_tokens"] += input_tokens
        entry["total_output_tokens"] += output_tokens
        entry["last_used"] = now_utc.isoformat()

        self._save_state(state)
