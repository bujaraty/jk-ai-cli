import json
import numpy as np
from pathlib import Path
from jk_core.constants import SESSIONS_DIR, SEARCH_INDEX_PATH

# Vectors live in a sibling directory next to search_index.json
# e.g. ~/.config/jk-ai/search_vectors/<session_id>.npy
VECTORS_DIR = SEARCH_INDEX_PATH.parent / "search_vectors"


class SearchEngine:
    def __init__(self, client):
        self.client = client
        self.session_dir = SESSIONS_DIR
        self.index_file = SEARCH_INDEX_PATH      # JSON: metadata only
        self.vectors_dir = VECTORS_DIR            # .npy files: one per session

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_vectors_dir(self):
        self.vectors_dir.mkdir(parents=True, exist_ok=True)

    def _vectors_path(self, sess_id: str) -> Path:
        return self.vectors_dir / f"{sess_id}.npy"

    def _load_metadata(self) -> dict:
        if not self.index_file.exists():
            return {}
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    def _save_metadata(self, data: dict):
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load_session_vectors(self, sess_id: str) -> np.ndarray | None:
        """Returns (N, D) float32 array or None if the file is missing."""
        path = self._vectors_path(sess_id)
        if not path.exists():
            return None
        return np.load(path)

    def _save_session_vectors(self, sess_id: str, matrix: np.ndarray):
        np.save(self._vectors_path(sess_id), matrix.astype(np.float32))

    def _extract_text(self, turn: dict) -> str:
        text = ""
        for p in turn.get("parts", []):
            if isinstance(p, str):
                text += p
            elif hasattr(p, "text"):
                text += p.text
        return text.strip()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_index(self) -> tuple[int, int]:
        """
        Incremental indexing — only embeds turns not yet in the index.

        For each session file:
          - If never indexed: embed all user turns.
          - If partially indexed: embed only turns after the last indexed position.
          - If fully up to date: skip entirely.

        Tracks progress via `indexed_turn_count` in metadata — a cursor into
        the raw history list (all roles), so it stays stable regardless of
        how many user vs model turns exist.

        Returns (sessions_updated, turns_added) for reporting.
        """
        self._ensure_vectors_dir()
        metadata = self._load_metadata()

        session_files = [
            f for f in self.session_dir.glob("*.json")
            if f.name != "metadata.json"
        ]

        sessions_updated = 0
        turns_added = 0

        for f in session_files:
            try:
                with open(f, "r", encoding="utf-8") as s:
                    data = json.load(s)
            except (json.JSONDecodeError, OSError) as e:
                print(f"  ⚠️  Skipping corrupted session file {f.name}: {e}")
                continue

            sess_id = data["session_id"]
            history = data.get("history", [])
            total_turns = len(history)

            # How far into history[] we've already indexed.
            # Migration: old rebuild_index() entries have no indexed_turn_count.
            # Infer from the last turn_index in messages so we don't re-embed.
            existing = metadata.get(sess_id, {})
            if "indexed_turn_count" in existing:
                indexed_up_to = existing["indexed_turn_count"]
            elif existing.get("messages"):
                last_turn_index = existing["messages"][-1]["turn_index"]
                indexed_up_to = last_turn_index + 1  # exclusive upper bound
            else:
                indexed_up_to = 0

            # Nothing new since last index
            if indexed_up_to >= total_turns:
                continue

            # Slice only the unindexed tail
            new_turns = history[indexed_up_to:]
            new_vectors = []
            new_messages_meta = []

            for i, turn in enumerate(new_turns, start=indexed_up_to):
                if turn["role"] != "user":
                    continue
                text = self._extract_text(turn)
                if not text:
                    continue
                try:
                    vector = self.client.embed_content(text, task_type="RETRIEVAL_DOCUMENT")
                except Exception as e:
                    print(f"  ⚠️  Skipping turn {i} in {f.name}: {e}")
                    continue
                new_vectors.append(vector)
                new_messages_meta.append({"text": text, "turn_index": i})

            # Advance the cursor even if no embeddable user turns were found
            if not new_vectors:
                metadata.setdefault(sess_id, {
                    "display_name": data.get("display_name"),
                    "filename": f.name,
                    "messages": [],
                    "indexed_turn_count": 0,
                })
                metadata[sess_id]["indexed_turn_count"] = total_turns
                metadata[sess_id]["display_name"] = data.get("display_name")
                continue

            # Append new vectors onto existing .npy (or create fresh)
            existing_matrix = self._load_session_vectors(sess_id)
            new_matrix = np.array(new_vectors, dtype=np.float32)
            combined = np.vstack([existing_matrix, new_matrix]) if existing_matrix is not None else new_matrix
            self._save_session_vectors(sess_id, combined)

            # Merge metadata
            metadata[sess_id] = {
                "display_name": data.get("display_name"),
                "filename": f.name,
                "messages": existing.get("messages", []) + new_messages_meta,
                "indexed_turn_count": total_turns,
            }

            sessions_updated += 1
            turns_added += len(new_vectors)

        self._save_metadata(metadata)
        return sessions_updated, turns_added

    def search(self, query: str, top_n: int = 5) -> list[dict]:
        """
        Semantic search across all indexed sessions.

        For each session, loads its .npy matrix and computes cosine similarity
        against the query vector in one vectorized operation.
        """
        metadata = self._load_metadata()
        if not metadata:
            return []

        query_vec = np.array(
            self.client.embed_content(query, task_type="RETRIEVAL_QUERY"),
            dtype=np.float32,
        )
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []
        query_unit = query_vec / query_norm

        all_matches = []

        for sess_id, sess_data in metadata.items():
            matrix = self._load_session_vectors(sess_id)
            if matrix is None or matrix.shape[0] == 0:
                continue

            # Vectorized cosine similarity: (N,) scores in one shot
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1, norms)
            unit_matrix = matrix / norms
            scores = unit_matrix @ query_unit

            for idx, msg_meta in enumerate(sess_data["messages"]):
                all_matches.append({
                    "score": float(scores[idx]),
                    "session_name": sess_data["display_name"],
                    "filename": sess_data["filename"],
                    "matched_text": msg_meta["text"],
                    "turn_no": (msg_meta["turn_index"] // 2) + 1,
                })

        return sorted(all_matches, key=lambda x: x["score"], reverse=True)[:top_n]

    def delete_session(self, sess_id: str):
        """
        Removes a session's vectors and metadata entry from the index.
        Call this when a session file is deleted so the index stays consistent.
        """
        npy_path = self._vectors_path(sess_id)
        if npy_path.exists():
            npy_path.unlink()

        metadata = self._load_metadata()
        if sess_id in metadata:
            del metadata[sess_id]
            self._save_metadata(metadata)
