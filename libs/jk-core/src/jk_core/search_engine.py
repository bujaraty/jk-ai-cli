import json
import numpy as np
from jk_core.constants import SESSIONS_DIR, SEARCH_INDEX_PATH

class SearchEngine:
    def __init__(self, client):
        self.client = client
        self.session_dir = SESSIONS_DIR
        self.index_file = SEARCH_INDEX_PATH

    def _cosine_similarity(self, v1, v2):
        return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

    def rebuild_index(self):
        """Milestone 1: Indexing every individual turn for pinpoint accuracy."""
        index_data = {}
        session_files = list(self.session_dir.glob("*.json"))
        session_files = [f for f in session_files if f.name != "metadata.json"]

        for f in session_files:
            with open(f, "r", encoding="utf-8") as s:
                data = json.load(s)
                sess_id = data['session_id']

                index_data[sess_id] = {
                    "display_name": data.get('display_name'),
                    "filename": f.name, # NEW: Store filename
                    "messages": []
                }

                # Embed each USER message separately
                for i, turn in enumerate(data.get('history', [])):
                    if turn['role'] == "user":
                        # CHANGE: Extract string from list ['text']
                        text = ""
                        for p in turn.get('parts', []):
                            if isinstance(p, str): text += p
                            elif hasattr(p, 'text'): text += p.text
                        if not text.strip(): continue

                        vector = self.client.embed_content(text, task_type="RETRIEVAL_DOCUMENT")
                        index_data[sess_id]["messages"].append({
                            "text": text,
                            "vector": vector,
                            "turn_index": i
                        })

        with open(self.index_file, "w", encoding="utf-8") as i:
            json.dump(index_data, i)

    def search(self, query: str, top_n: int = 5):
        if not self.index_file.exists(): return []

        query_vector = self.client.embed_content(query, task_type="RETRIEVAL_QUERY")
        with open(self.index_file, "r") as i:
            index = json.load(i)

        all_matches = []
        for sess_id, sess_data in index.items():
            for msg in sess_data["messages"]:
                score = self._cosine_similarity(query_vector, msg["vector"])
                all_matches.append({
                    "score": score,
                    "session_name": sess_data["display_name"],
                    "filename": sess_data["filename"],
                    "matched_text": msg["text"], # NEW: The 'Reason'
                    "turn_no": (msg["turn_index"] // 2) + 1
                })

        # Sort by best match across ALL messages in ALL sessions
        return sorted(all_matches, key=lambda x: x['score'], reverse=True)[:top_n]

