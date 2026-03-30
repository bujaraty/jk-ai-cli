import json
import time
from google.genai import types
from jk_core.constants import SESSIONS_DIR

class SessionManager:
    """
    Manages session history using JSONL for messages and
    a metadata JSON for human-readable session names.
    """
    def __init__(self, system_instruction=""):
        self.base_dir = SESSIONS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.metadata_file = self.base_dir / "metadata.json"
        self.system_instruction = system_instruction
        self.session_id = f"sess_{int(time.time())}"
        self.display_name = "New Chat" # Default name

        # In-memory history cache for the current session
        self.history = []

        # Initialize Metadata Registry
        self._init_metadata()

    def _init_metadata(self):
        if not self.metadata_file.exists():
            self._save_metadata({})

    def _load_metadata(self) -> dict:
        with open(self.metadata_file, "r") as f:
            return json.load(f)

    def _save_metadata(self, data: dict):
        with open(self.metadata_file, "w") as f:
            json.dump(data, f, indent=2)

    def _update_meta_entry(self):
        """Internal helper to sync current session stats to metadata.json index."""
        meta = self._load_metadata()
        meta[self.session_id] = {
            "name": self.display_name,
            "updated_at": int(time.time()),
            "message_count": len(self.history)
        }
        self._save_metadata(meta)

    def add_message(self, role: str, text: str, model_id: str = None):
        message = {
            "role": role,
            "parts": [text],
            "metadata": {"model": model_id} if model_id else {}
        }
        self.history.append(message)
        self.save()

    def branch(self):
        old_id = self.session_id
        self.session_id = f"{old_id}_branch_{int(time.time())}"
        self.display_name = f"Branch of {self.display_name}"
        self.save()
        return self.session_id

    def get_recent_sessions(self, limit=20):
        meta = self._load_metadata()
        needs_save = False

        valid = {}
        for sess_id, info in meta.items():
            session_file = self.base_dir / f"{sess_id}.json"

            # Skip missing or corrupted files
            if not session_file.exists():
                continue
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            # Backfill message_count and updated_at if missing (legacy sessions)
            if 'message_count' not in info or 'updated_at' not in info:
                history = data.get('history', [])
                info['message_count'] = len(history)
                info['updated_at'] = int(session_file.stat().st_mtime)
                meta[sess_id] = info
                needs_save = True

            valid[sess_id] = info

        if needs_save:
            self._save_metadata(meta)

        sorted_valid = sorted(
            valid.items(),
            key=lambda x: x[1].get('updated_at', 0),
            reverse=True
        )
        return sorted_valid[:limit]

    def get_last_turns(self, n=5):
        return self.history[-(n*2):] if self.history else []

    def is_eligible_for_autoname(self) -> bool:
        # We only auto-name if it's the default name and we have 2 messages (1 pair)
        return self.display_name == "New Chat" and len(self.history) == 2

    def load(self, session_id: str):
        session_file = self.base_dir / f"{session_id}.json"
        if not session_file.exists():
            return False

        try:
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False

        self.session_id = data.get("session_id", session_id)
        self.display_name = data.get("display_name", "Unnamed")
        self.system_instruction = data.get("system_instruction", "")
        self.history = data.get("history", [])

        # Refresh the index entry
        self._update_meta_entry()
        return True

    def save(self):
        """Saves EVERYTHING into one JSON file for ease of editing (Milestone 5)."""
        session_file = self.base_dir / f"{self.session_id}.json"
        payload = {
            "session_id": self.session_id,
            "display_name": self.display_name,
            "system_instruction": self.system_instruction,
            "history": self.history
        }
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        # Sync the index file
        self._update_meta_entry()

    def set_display_name(self, name: str):
        """CHANGE: Maps the internal session_id to a user-defined name."""
        self.display_name = name
        meta = self._load_metadata()
        meta[self.session_id] = {
            "name": name,
            "created_at": int(time.time()),
            "system_instruction": self.system_instruction
        }
        self._save_metadata(meta)

    def time_travel(self, index: int, new_text: str):
        """
        Milestone 5: Resets history to a clean state starting at the edit.
        """
        # 1. Truncate EVERYTHING from the edit point onwards
        # If we edit index 2, self.history becomes [0, 1]
        self.history = self.history[:index]

        # 2. Re-insert the EDITED user message as the new 'latest' message
        # This ensures the next response from AI will be 'model' role
        self.add_message("user", new_text)

    def undo(self):
        """Removes the last exchange from memory and REWRITES the .jsonl."""
        if len(self.history) >= 2:
            self.history = self.history[:-2]
            self.save()

