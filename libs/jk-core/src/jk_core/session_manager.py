import json
import time
from pathlib import Path
from google.genai import types
from jk_core.constants import SHARED_CONFIG_PATH

class SessionManager:
    """
    Manages session history using JSONL for messages and
    a metadata JSON for human-readable session names.
    """
    def __init__(self, system_instruction=""):
        self.base_dir = Path(SHARED_CONFIG_PATH) / "sessions"
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

    # CHANGE: Logic consolidated to update the global index (metadata.json)
    # with the latest count and timestamp for high-speed /resume listing.
    def _update_meta_entry(self):
        """Internal helper to sync current session stats to metadata.json index."""
        meta = self._load_metadata()
        meta[self.session_id] = {
            "name": self.display_name,
            "updated_at": int(time.time()),
            "message_count": len(self.history)
        }
        self._save_metadata(meta)

    def add_message(self, role: str, text: str):
        self.history.append({"role": role, "parts": [text]})
        self.save()

    def branch(self):
        old_id = self.session_id
        self.session_id = f"{old_id}_branch_{int(time.time())}"
        self.display_name = f"Branch of {self.display_name}"
        self.save()
        return self.session_id

    def get_recent_sessions(self, limit=20):
        meta = self._load_metadata()
        # Sort by timestamp descending
        sorted_meta = sorted(
            meta.items(),
            key=lambda x: x[1].get('updated_at', 0),
            reverse=True
        )
        return sorted_meta[:limit]

    def get_last_turns(self, n=5):
        return self.history[-(n*2):] if self.history else []

    def is_eligible_for_autoname(self) -> bool:
        # We only auto-name if it's the default name and we have 2 messages (1 pair)
        return self.display_name == "New Chat" and len(self.history) == 2

    def load(self, session_id: str):
        session_file = self.base_dir / f"{session_id}.json"
        if not session_file.exists():
            return False

        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)
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

    def undo(self):
        """Removes the last exchange from memory and REWRITES the .jsonl."""
        if len(self.history) >= 2:
            self.history = self.history[:-2]
            # Rewrite JSONL (Standard practice for undo/delete in JSONL)
            history_path = self.base_dir / f"{self.session_id}.jsonl"
            with open(history_path, "w", encoding="utf-8") as f:
                for msg in self.history:
                    f.write(json.dumps(msg) + "\n")

