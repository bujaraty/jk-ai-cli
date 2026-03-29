import json
from datetime import datetime, timezone
from pathlib import Path
from google import genai
from jk_core.constants import SHARED_CONFIG_PATH
from jk_core.key_manager import KeyManager

class ModelTester:
    def __init__(self, provider: str = "google"):
        self.cache_file = Path(SHARED_CONFIG_PATH) / "models_cache.json"
        self.history_file = Path(SHARED_CONFIG_PATH) / "probe_history.jsonl"
        self.km = KeyManager(provider=provider)

    def _load_cache(self):
        if not self.cache_file.exists(): return []
        with open(self.cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _log_probe(self, model_id, action, status, key_id, error=None):
        """CHANGE: Appends a single probe event to the history JSONL file."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_id": model_id,
            "action": action,
            "status": status,
            "key_id": key_id,
            "error": error
        }
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

    def sync_model_status(self):
        """Probes specific capabilities and updates the local JSON cache."""
        cache = self._load_cache()
        api_key, key_id = self.km.get_available_key()
        if not api_key or not cache: return [], key_id

        client = genai.Client(api_key=api_key)
        now_str = datetime.now(timezone.utc).isoformat()
        report_data = []

        for model_entry in cache:
            m_id = model_entry['id']
            # CHANGE: Work directly with the 'capabilities' dictionary
            caps = model_entry.get('capabilities', {})

            # We only probe actions relevant to our current app features
            actions_to_test = ["generateContent", "embedContent"]

            for action in actions_to_test:
                if action in caps:
                    status = "FAIL"
                    error_msg = None
                    print(f"  🔍 Probing [{key_id}] {m_id} → {action} ...", end=" ", flush=True)
                    try:
                        if action == "generateContent":
                            client.models.generate_content(model=m_id, contents="hi")
                        elif action == "embedContent":
                            client.models.embed_content(model=m_id, contents="hi")
                        status = "PASS"
                        print("✅")
                    except Exception as e:
                        error_msg = str(e).replace("\n", " ")
                        print("❌")

                    caps[action].update({
                        "status": status,
                        "last_probed": now_str,
                        "error": error_msg
                    })

                    self._log_probe(m_id, action, status, key_id, error_msg)

                    report_data.append({
                        "id": m_id,
                        "action": action,
                        "status": status,
                        "error": error_msg or "-"
                    })

        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)

        return report_data, key_id

