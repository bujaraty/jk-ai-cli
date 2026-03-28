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

    def add_message(self, role: str, text: str):
        message = {"role": role, "parts": [text]}
        self.history.append(message)

        history_path = self.base_dir / f"{self.session_id}.jsonl"
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(message) + "\n")

    def branch(self):
        """Clones current history into a new .jsonl with a new ID."""
        old_id = self.session_id
        self.session_id = f"{old_id}_branch_{int(time.time())}"
        self.set_display_name(f"Branch of {self.display_name}")

        # Copy file
        old_path = self.base_dir / f"{old_id}.jsonl"
        new_path = self.base_dir / f"{self.session_id}.jsonl"
        if old_path.exists():
            import shutil
            shutil.copy(old_path, new_path)

        return self.session_id

    def load(self, session_id: str):
        meta = self._load_metadata()
        if session_id not in meta:
            return False

        self.session_id = session_id
        self.display_name = meta[session_id].get("name", "Unnamed")
        self.system_instruction = meta[session_id].get("system_instruction", "")

        # Read the .jsonl file line by line
        self.history = []
        history_path = self.base_dir / f"{self.session_id}.jsonl"
        if history_path.exists():
            with open(history_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self.history.append(json.loads(line))
        return True

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

