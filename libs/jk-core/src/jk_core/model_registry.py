import json
from pathlib import Path
from jk_core.constants import SHARED_CONFIG_PATH
from jk_core.providers.google import GoogleProvider

class ModelRegistry:
    """
    Orchestrates multiple providers and manages local model metadata caching.
    """
    def __init__(self):
        self.cache_file = Path(SHARED_CONFIG_PATH) / "models_cache.json"
        # Register active provider instances
        self.providers = {
            "google": GoogleProvider()
        }

    def refresh_cache(self):
        """Polls all providers and updates the local JSON cache."""
        all_models = []
        for name, provider in self.providers.items():
            try:
                models = provider.list_models()
                all_models.extend(models)
            except Exception as e:
                print(f"⚠️ Error fetching models from {name}: {e}")

        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(all_models, f, indent=2)
        return all_models

    def get_models_by_action(self, action: str = "generateContent"):
        """Filters models by capability from the local cache."""
        if not self.cache_file.exists():
            self.refresh_cache()

        with open(self.cache_file, "r") as f:
            data = json.load(f)


        # CHANGE: Check if 'action' exists as a key inside the 'capabilities' dict
        return [
            m for m in data
            if action in m.get("capabilities", {})
        ]
