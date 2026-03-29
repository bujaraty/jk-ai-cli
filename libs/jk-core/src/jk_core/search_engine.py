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
        """Returns the .npy path for a given session id."""
        return self.vectors_dir / f"{sess_id}.npy"

    def _load_metadata(self) -> dict:
        if not self.index_file.exists():
            return {}
        with open(self.index_file, "r", encoding="utf-8") as f:
            return json.load(f)

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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rebuild_index(self):
        """
        Re-embeds every user turn across all sessions.

        Storage layout after this call:
          search_index.json          — metadata (text, turn_index, display_name, filename)
          search_vectors/<id>.npy    — float32 matrix, shape (N_turns, embedding_dim)
        """
        self._ensure_vectors_dir()

        metadata = {}
        session_files = [
            f for f in self.session_dir.glob("*.json")
            if f.name != "metadata.json"
        ]

        for f in session_files:
            with open(f, "r", encoding="utf-8") as s:
                data = json.load(s)

            sess_id = data["session_id"]
            messages_meta = []
            vectors = []

            for i, turn in enumerate(data.get("history", [])):
                if turn["role"] != "user":
                    continue

                # Extract text from parts list
                text = ""
                for p in turn.get("parts", []):
                    if isinstance(p, str):
                        text += p
                    elif hasattr(p, "text"):
                        text += p.text
                if not text.strip():
                    continue

                try:
                    vector = self.client.embed_content(text, task_type="RETRIEVAL_DOCUMENT")
                except Exception as e:
                    print(f"  ⚠️  Skipping turn {i} in {f.name}: {e}")
                    continue
                vectors.append(vector)
                messages_meta.append({"text": text, "turn_index": i})

            if not vectors:
                continue

            # Save dense matrix for this session
            matrix = np.array(vectors, dtype=np.float32)
            self._save_session_vectors(sess_id, matrix)

            # Save metadata (no vectors here)
            metadata[sess_id] = {
                "display_name": data.get("display_name"),
                "filename": f.name,
                "messages": messages_meta,   # text + turn_index only
            }

        self._save_metadata(metadata)

    def search(self, query: str, top_n: int = 5) -> list[dict]:
        """
        Semantic search across all indexed sessions.

        For each session, loads its .npy matrix and computes cosine similarity
        against the query vector in one vectorized operation — no Python loop
        over individual embeddings.
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
            norms = np.where(norms == 0, 1, norms)   # avoid div-by-zero
            unit_matrix = matrix / norms
            scores = unit_matrix @ query_unit          # shape: (N,)

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
        # Remove .npy file
        npy_path = self._vectors_path(sess_id)
        if npy_path.exists():
            npy_path.unlink()

        # Remove from metadata JSON
        metadata = self._load_metadata()
        if sess_id in metadata:
            del metadata[sess_id]
            self._save_metadata(metadata)
