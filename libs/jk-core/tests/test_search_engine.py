"""
Tests for SearchEngine.

The Google API is never called. client.embed_content is replaced with a
deterministic fake that returns orthogonal unit vectors keyed by text content,
making cosine similarity results fully predictable.

File layout under tmp_path:
  sessions/          — session JSON files (input to update_index)
  search_index.json  — metadata output
  search_vectors/    — .npy output files
"""
import json
import numpy as np
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from jk_core.search_engine import SearchEngine


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

DIM = 8  # embedding dimension used in all tests


def make_vector(seed: int) -> list[float]:
    """
    Returns a deterministic unit vector in R^DIM.
    Each seed produces a unique direction — cosine similarity between
    different seeds is low, same seed is 1.0.
    """
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(DIM).astype(np.float32)
    return (v / np.linalg.norm(v)).tolist()


def fake_embed(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """
    Deterministic embedding: hash the text to a seed so the same text
    always gets the same vector, and different texts get different vectors.
    """
    return make_vector(hash(text) % (2**31))


def make_client() -> MagicMock:
    client = MagicMock()
    client.embed_content.side_effect = fake_embed
    return client


def make_se(tmp_path) -> SearchEngine:
    """SearchEngine with all paths redirected to tmp_path."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(exist_ok=True)
    vectors_dir = tmp_path / "search_vectors"

    se = SearchEngine(client=make_client())
    se.session_dir = sessions_dir
    se.index_file = tmp_path / "search_index.json"
    se.vectors_dir = vectors_dir
    return se


def write_session(tmp_path, sess_id: str, history: list, display_name: str = "Test Session") -> Path:
    """Write a session JSON file into tmp_path/sessions/."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(exist_ok=True)
    data = {
        "session_id": sess_id,
        "display_name": display_name,
        "system_instruction": "",
        "history": history,
    }
    f = sessions_dir / f"{sess_id}.json"
    f.write_text(json.dumps(data))
    return f


def make_history(*pairs) -> list:
    """
    Build a history list from (user_text, model_text) pairs.
    Each pair becomes two turns: user then model.
    """
    history = []
    for user_text, model_text in pairs:
        history.append({"role": "user", "parts": [user_text], "metadata": {}})
        history.append({"role": "model", "parts": [model_text], "metadata": {}})
    return history


# ---------------------------------------------------------------------------
# _extract_text
# ---------------------------------------------------------------------------

class TestExtractText:
    def test_string_parts(self, tmp_path):
        se = make_se(tmp_path)
        turn = {"parts": ["hello world"]}
        assert se._extract_text(turn) == "hello world"

    def test_object_with_text_attr(self, tmp_path):
        se = make_se(tmp_path)
        obj = MagicMock()
        obj.text = "from object"
        turn = {"parts": [obj]}
        assert se._extract_text(turn) == "from object"

    def test_empty_parts(self, tmp_path):
        se = make_se(tmp_path)
        assert se._extract_text({"parts": []}) == ""

    def test_strips_whitespace(self, tmp_path):
        se = make_se(tmp_path)
        turn = {"parts": ["  spaced  "]}
        assert se._extract_text(turn) == "spaced"

    def test_missing_parts_key(self, tmp_path):
        se = make_se(tmp_path)
        assert se._extract_text({}) == ""


# ---------------------------------------------------------------------------
# update_index — first-time indexing
# ---------------------------------------------------------------------------

class TestUpdateIndexFresh:
    def test_indexes_user_turns_only(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("hello", "hi back")))
        sessions, turns = se.update_index()
        assert sessions == 1
        assert turns == 1  # only the user turn

    def test_creates_npy_file(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("hello", "hi")))
        se.update_index()
        assert (tmp_path / "search_vectors" / "sess_a.npy").exists()

    def test_creates_metadata_json(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("hello", "hi")))
        se.update_index()
        assert se.index_file.exists()
        meta = json.loads(se.index_file.read_text())
        assert "sess_a" in meta

    def test_metadata_contains_correct_fields(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("hello", "hi")), display_name="My Chat")
        se.update_index()
        meta = json.loads(se.index_file.read_text())
        entry = meta["sess_a"]
        assert entry["display_name"] == "My Chat"
        assert entry["filename"] == "sess_a.json"
        assert entry["indexed_turn_count"] == 2  # 1 user + 1 model
        assert len(entry["messages"]) == 1
        assert entry["messages"][0]["text"] == "hello"
        assert entry["messages"][0]["turn_index"] == 0

    def test_multiple_sessions(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("q1", "a1")))
        write_session(tmp_path, "sess_b", make_history(("q2", "a2"), ("q3", "a3")))
        sessions, turns = se.update_index()
        assert sessions == 2
        assert turns == 3

    def test_skips_empty_user_text(self, tmp_path):
        se = make_se(tmp_path)
        history = [
            {"role": "user", "parts": ["   "], "metadata": {}},  # blank
            {"role": "model", "parts": ["ok"], "metadata": {}},
        ]
        write_session(tmp_path, "sess_a", history)
        sessions, turns = se.update_index()
        assert turns == 0

    def test_skips_corrupted_session_file(self, tmp_path):
        se = make_se(tmp_path)
        bad = tmp_path / "sessions" / "sess_bad.json"
        bad.write_text("")  # empty = corrupted
        sessions, turns = se.update_index()
        assert sessions == 0

    def test_embed_content_called_once_per_user_turn(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("q1", "a1"), ("q2", "a2")))
        se.update_index()
        assert se.client.embed_content.call_count == 2

    def test_npy_shape_matches_turn_count(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("q1", "a1"), ("q2", "a2"), ("q3", "a3")))
        se.update_index()
        matrix = np.load(tmp_path / "search_vectors" / "sess_a.npy")
        assert matrix.shape[0] == 3  # 3 user turns


# ---------------------------------------------------------------------------
# update_index — incremental (already partially indexed)
# ---------------------------------------------------------------------------

class TestUpdateIndexIncremental:
    def test_skips_fully_indexed_session(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("q1", "a1")))
        se.update_index()
        call_count_after_first = se.client.embed_content.call_count

        se.update_index()  # nothing new
        assert se.client.embed_content.call_count == call_count_after_first

    def test_only_indexes_new_turns(self, tmp_path):
        se = make_se(tmp_path)
        # First index: 1 exchange
        write_session(tmp_path, "sess_a", make_history(("q1", "a1")))
        se.update_index()
        first_call_count = se.client.embed_content.call_count

        # Add more turns to the session file
        write_session(tmp_path, "sess_a", make_history(("q1", "a1"), ("q2", "a2"), ("q3", "a3")))
        sessions, turns = se.update_index()

        assert turns == 2  # only q2 and q3
        assert se.client.embed_content.call_count == first_call_count + 2

    def test_appends_vectors_to_existing_npy(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("q1", "a1")))
        se.update_index()

        write_session(tmp_path, "sess_a", make_history(("q1", "a1"), ("q2", "a2")))
        se.update_index()

        matrix = np.load(tmp_path / "search_vectors" / "sess_a.npy")
        assert matrix.shape[0] == 2  # both turns present, no duplicates

    def test_cursor_advances_correctly(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("q1", "a1")))
        se.update_index()

        write_session(tmp_path, "sess_a", make_history(("q1", "a1"), ("q2", "a2")))
        se.update_index()

        meta = json.loads(se.index_file.read_text())
        assert meta["sess_a"]["indexed_turn_count"] == 4  # 2 exchanges = 4 raw turns

    def test_metadata_messages_merged_correctly(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("q1", "a1")))
        se.update_index()

        write_session(tmp_path, "sess_a", make_history(("q1", "a1"), ("q2", "a2")))
        se.update_index()

        meta = json.loads(se.index_file.read_text())
        texts = [m["text"] for m in meta["sess_a"]["messages"]]
        assert texts == ["q1", "q2"]

    def test_migration_from_legacy_no_indexed_turn_count(self, tmp_path):
        """
        Legacy entries (from old rebuild_index) have messages but no
        indexed_turn_count. The cursor should be inferred from the last
        turn_index so nothing gets re-embedded.
        """
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("q1", "a1")))

        # Write legacy-style metadata manually (no indexed_turn_count)
        legacy_meta = {
            "sess_a": {
                "display_name": "Legacy",
                "filename": "sess_a.json",
                "messages": [{"text": "q1", "turn_index": 0}],
                # no indexed_turn_count
            }
        }
        se.index_file.write_text(json.dumps(legacy_meta))

        sessions, turns = se.update_index()
        # Session is already fully indexed — nothing new to embed
        assert turns == 0
        assert se.client.embed_content.call_count == 0

    def test_embed_failure_skips_turn_but_continues(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("q1", "a1"), ("q2", "a2")))

        # Make embed fail on first call, succeed on second
        se.client.embed_content.side_effect = [Exception("quota"), fake_embed("q2")]
        sessions, turns = se.update_index()

        # q1 was skipped, q2 was indexed
        assert turns == 1


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_returns_empty_when_no_index(self, tmp_path):
        se = make_se(tmp_path)
        results = se.search("anything")
        assert results == []

    def test_returns_empty_when_index_empty_json(self, tmp_path):
        se = make_se(tmp_path)
        se.index_file.write_text("")
        results = se.search("anything")
        assert results == []

    def test_finds_relevant_result(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("japan travel tips", "here are some")))
        se.update_index()

        results = se.search("japan travel tips")
        assert len(results) == 1
        assert results[0]["matched_text"] == "japan travel tips"
        assert results[0]["score"] > 0.99  # same text → near 1.0

    def test_result_contains_required_fields(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("hello", "hi")), display_name="My Chat")
        se.update_index()

        results = se.search("hello")
        r = results[0]
        assert "score" in r
        assert "session_name" in r
        assert "filename" in r
        assert "matched_text" in r
        assert "turn_no" in r
        assert r["session_name"] == "My Chat"
        assert r["filename"] == "sess_a.json"

    def test_sorted_by_score_descending(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(
            ("python programming tips", "ok"),
            ("cooking recipes", "ok"),
            ("travel to japan", "ok"),
        ))
        se.update_index()

        results = se.search("python programming tips")
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_top_n_limits_results(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(
            ("q1", "a1"), ("q2", "a2"), ("q3", "a3"),
            ("q4", "a4"), ("q5", "a5"), ("q6", "a6"),
        ))
        se.update_index()
        results = se.search("q1", top_n=3)
        assert len(results) <= 3

    def test_turn_no_is_exchange_number(self, tmp_path):
        """turn_no should reflect the exchange number (1-based), not raw index."""
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(
            ("first question", "first answer"),
            ("second question", "second answer"),
        ))
        se.update_index()

        results = se.search("second question")
        # "second question" is turn_index=2 (raw), exchange no. = (2//2)+1 = 2
        second = next(r for r in results if r["matched_text"] == "second question")
        assert second["turn_no"] == 2

    def test_skips_session_with_missing_npy(self, tmp_path):
        """If .npy is missing for an indexed session, that session is skipped gracefully."""
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("hello", "hi")))
        se.update_index()

        # Delete the .npy manually
        (tmp_path / "search_vectors" / "sess_a.npy").unlink()

        results = se.search("hello")
        assert results == []

    def test_zero_query_vector_returns_empty(self, tmp_path):
        """A zero query vector should not cause a division error."""
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("hello", "hi")))
        se.update_index()

        se.client.embed_content.side_effect = lambda text, task_type: [0.0] * DIM
        results = se.search("anything")
        assert results == []

    def test_searches_across_multiple_sessions(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("tokyo trip", "great")), display_name="A")
        write_session(tmp_path, "sess_b", make_history(("paris visit", "nice")), display_name="B")
        se.update_index()

        results = se.search("tokyo trip", top_n=5)
        session_names = {r["session_name"] for r in results}
        assert "A" in session_names


# ---------------------------------------------------------------------------
# delete_session
# ---------------------------------------------------------------------------

class TestDeleteSession:
    def test_removes_npy_file(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("hello", "hi")))
        se.update_index()
        assert (tmp_path / "search_vectors" / "sess_a.npy").exists()

        se.delete_session("sess_a")
        assert not (tmp_path / "search_vectors" / "sess_a.npy").exists()

    def test_removes_metadata_entry(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("hello", "hi")))
        se.update_index()

        se.delete_session("sess_a")
        meta = json.loads(se.index_file.read_text())
        assert "sess_a" not in meta

    def test_delete_nonexistent_session_does_not_crash(self, tmp_path):
        se = make_se(tmp_path)
        se.delete_session("sess_ghost")  # should not raise

    def test_delete_leaves_other_sessions_intact(self, tmp_path):
        se = make_se(tmp_path)
        write_session(tmp_path, "sess_a", make_history(("hello", "hi")))
        write_session(tmp_path, "sess_b", make_history(("world", "ok")))
        se.update_index()

        se.delete_session("sess_a")
        meta = json.loads(se.index_file.read_text())
        assert "sess_b" in meta
        assert (tmp_path / "search_vectors" / "sess_b.npy").exists()
