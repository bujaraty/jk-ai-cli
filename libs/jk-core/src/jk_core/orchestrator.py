import json
from pathlib import Path
from jk_core.constants import SHARED_CONFIG_PATH

class Orchestrator:
    """
    The Intelligence layer with Tier and Versioning strategy.

    Arguments:
    - tier: 'lite' (Speed), 'normal' (Balanced), 'high' (Power)
    - prefer_latest: Boolean, if True, adds a bonus to models with 'latest' in ID.
    """
    def __init__(self, provider: str = "google", tier: str = "normal", prefer_latest: bool = False):
        self.provider = provider
        self.tier = tier.lower()
        self.prefer_latest = prefer_latest
        self.cache_file = Path(SHARED_CONFIG_PATH) / "models_cache.json"



    def _load_cache(self) -> list:
        if not self.cache_file.exists():
            return []
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return []

    def get_score_details(self, model_entry: dict, action: str) -> dict:
        """
        Calculates the score and returns the breakdown.
        Higher Score = Better Choice.
        """
        score = 0
        reasons = []

        model_id = model_entry.get("id", "").lower()
        capabilities = model_entry.get("capabilities", {})

        # 1. Action Support (Mandatory)
        if action not in capabilities:
            return {"total": -999, "reasons": ["Ineligible: Action not supported"]}

        action_data = capabilities.get(action, {})
        status = action_data.get("status", "PENDING")

        # 2. Health Weighting (The primary factor)
        if status == "PASS":
            score += 100
            reasons.append("+100 Health (PASS)")
        elif status == "FAIL":
            score -= 100
            reasons.append("-100 Health (FAIL)")
        else:
            score += 10
            reasons.append("+10 Health (PENDING)")


        # 3. Tier-based Scoring (Speed vs. Intelligence)
        if self.tier == "lite":
            if "lite" in model_id or "-8b" in model_id:
                score += 50
                reasons.append("+50 Tier (Lite/8B)")
            elif "flash" in model_id:
                score += 20
                reasons.append("+20 Tier (Flash fallback)")
        elif self.tier == "high":
            if "pro" in model_id:
                score += 50
                reasons.append("+50 Tier (Pro/Intelligence)")
            elif "lite" in model_id:
                score -= 20
                reasons.append("-20 Tier (not preferable for high performance)")
            elif "flash" in model_id:
                score += 10
                reasons.append("+10 Tier (Flash fallback)")
        else: # Default: 'normal'
            if "flash" in model_id and "lite" not in model_id:
                score += 50
                reasons.append("+50 Tier (Flash/Balanced)")

        # 4. Versioning Preference (Independent Argument)
        if self.prefer_latest and "latest" in model_id:
            score += 25
            reasons.append("+25 Version (Latest preference)")
        elif "latest" in model_id:
            score -= 5
            reasons.append("-5 Version (Keep the latest to be used later)")

        # 5. Give a little higher priority to the newest model
        if "preview" in model_id:
            score += 2
            reasons.append("+2 Preview")

        return {"total": score, "reasons": reasons}

    # CHANGE: pick_best_model now returns the winner with its reasoning
    def pick_best_model(self, action: str = "generateContent") -> dict:
        rankings = self.get_rankings(action)
        if not rankings:
            return None

        # The first item is the winner (sorted by refresh_rankings)
        return rankings[0]

    # CHANGE: get_rankings now provides a full list with reasons for debugging
    def get_rankings(self, action: str = "generateContent") -> list:
        """Returns all models for this provider, ranked by affinity score."""
        models = self._load_cache()
        scored_list = []

        for m in models:
            if m.get("provider") == self.provider:
                details = self.get_score_details(m, action)
                if details["total"] > -500: # Filter out strictly ineligible models
                    scored_list.append({
                        "id": m["id"],
                        "display_name": m["display_name"],
                        "score": details["total"],
                        "reasons": details["reasons"],
                        "status": m.get("capabilities", {}).get(action, {}).get("status", "N/A")
                    })

        # Sort by score descending
        return sorted(scored_list, key=lambda x: x["score"], reverse=True)

