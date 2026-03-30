"""
Tests for SessionManager.

All tests use tmp_path so nothing touches the real sessions directory.
SessionManager is instantiated with its base_dir redirected to tmp_path/sessions.
"""
import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch

from jk_core.session_manager import SessionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_sm(tmp_path, system_instruction="") -> SessionManager:
    """SessionManager with all paths redirected to tmp_path."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(exist_ok=True)
    with patch("jk_core.session_manager.SESSIONS_DIR", sessions_dir):
        sm = SessionManager(system_instruction=system_instruction)
    sm.base_dir = sessions_dir
    sm.metadata_file = sessions_dir / "metadata.json"
    return sm


def add_exchange(sm, user_text, ai_text, model_id="models/gemini-flash"):
    sm.add_message("user", user_text)
    sm.add_message("model", ai_text, model_id=model_id)


# ---------------------------------------------------------------------------
# add_message / basic save
# ---------------------------------------------------------------------------

class TestAddMessage:
    def test_adds_to_history(self, tmp_path):
        sm = make_sm(tmp_path)
        sm.add_message("user", "hello")
        assert len(sm.history) == 1
        assert sm.history[0]["role"] == "user"
        assert sm.history[0]["parts"] == ["hello"]

    def test_saves_to_file(self, tmp_path):
        sm = make_sm(tmp_path)
        sm.add_message("user", "hello")
        session_file = sm.base_dir / f"{sm.session_id}.json"
        assert session_file.exists()
        data = json.loads(session_file.read_text())
        assert data["history"][0]["parts"] == ["hello"]

    def test_model_id_stored_in_metadata(self, tmp_path):
        sm = make_sm(tmp_path)
        sm.add_message("model", "response", model_id="models/gemini-pro")
        assert sm.history[0]["metadata"]["model"] == "models/gemini-pro"

    def test_no_model_id_gives_empty_metadata(self, tmp_path):
        sm = make_sm(tmp_path)
        sm.add_message("user", "hi")
        assert sm.history[0]["metadata"] == {}


# ---------------------------------------------------------------------------
# undo
# ---------------------------------------------------------------------------

class TestUndo:
    def test_removes_last_exchange(self, tmp_path):
        sm = make_sm(tmp_path)
        add_exchange(sm, "first", "first response")
        add_exchange(sm, "second", "second response")
        assert len(sm.history) == 4
        sm.undo()
        assert len(sm.history) == 2
        assert sm.history[-1]["parts"] == ["first response"]

    def test_undo_on_single_message_does_nothing(self, tmp_path):
        sm = make_sm(tmp_path)
        sm.add_message("user", "only")
        sm.undo()
        assert len(sm.history) == 1  # nothing removed, need at least 2

    def test_undo_on_empty_history_does_nothing(self, tmp_path):
        sm = make_sm(tmp_path)
        sm.undo()
        assert sm.history == []

    def test_undo_persists_to_file(self, tmp_path):
        sm = make_sm(tmp_path)
        add_exchange(sm, "q", "a")
        sm.undo()
        data = json.loads((sm.base_dir / f"{sm.session_id}.json").read_text())
        assert data["history"] == []


# ---------------------------------------------------------------------------
# time_travel
# ---------------------------------------------------------------------------

class TestTimeTravel:
    def test_truncates_history_and_inserts_edit(self, tmp_path):
        sm = make_sm(tmp_path)
        add_exchange(sm, "first", "resp1")
        add_exchange(sm, "second", "resp2")
        # history: [user0, model1, user2, model3]
        # edit index 0 (the first user message)
        sm.time_travel(0, "edited first")
        assert len(sm.history) == 1
        assert sm.history[0]["role"] == "user"
        assert sm.history[0]["parts"] == ["edited first"]

    def test_mid_history_edit(self, tmp_path):
        sm = make_sm(tmp_path)
        add_exchange(sm, "first", "resp1")
        add_exchange(sm, "second", "resp2")
        add_exchange(sm, "third", "resp3")
        # edit index 2 (second user message)
        sm.time_travel(2, "new second")
        assert len(sm.history) == 3  # [user0, model1, new_user2]
        assert sm.history[2]["parts"] == ["new second"]

    def test_everything_after_edit_point_is_dropped(self, tmp_path):
        sm = make_sm(tmp_path)
        add_exchange(sm, "q1", "a1")
        add_exchange(sm, "q2", "a2")
        sm.time_travel(0, "new q1")
        texts = [m["parts"][0] for m in sm.history]
        assert "q2" not in texts
        assert "a1" not in texts
        assert "a2" not in texts


# ---------------------------------------------------------------------------
# branch
# ---------------------------------------------------------------------------

class TestBranch:
    def test_branch_creates_new_session_id(self, tmp_path):
        sm = make_sm(tmp_path)
        original_id = sm.session_id
        new_id = sm.branch()
        assert new_id != original_id
        assert original_id in new_id

    def test_branch_updates_display_name(self, tmp_path):
        sm = make_sm(tmp_path)
        sm.display_name = "My Chat"
        sm.branch()
        assert "Branch of" in sm.display_name

    def test_branch_saves_new_file(self, tmp_path):
        sm = make_sm(tmp_path)
        add_exchange(sm, "hi", "hello")
        sm.branch()
        session_file = sm.base_dir / f"{sm.session_id}.json"
        assert session_file.exists()


# ---------------------------------------------------------------------------
# is_eligible_for_autoname
# ---------------------------------------------------------------------------

class TestAutoname:
    def test_eligible_after_first_exchange(self, tmp_path):
        sm = make_sm(tmp_path)
        add_exchange(sm, "hi", "hello")
        assert sm.is_eligible_for_autoname() is True

    def test_not_eligible_if_already_named(self, tmp_path):
        sm = make_sm(tmp_path)
        sm.display_name = "Custom Name"
        add_exchange(sm, "hi", "hello")
        assert sm.is_eligible_for_autoname() is False

    def test_not_eligible_before_first_exchange(self, tmp_path):
        sm = make_sm(tmp_path)
        assert sm.is_eligible_for_autoname() is False

    def test_not_eligible_after_second_exchange(self, tmp_path):
        sm = make_sm(tmp_path)
        add_exchange(sm, "first", "resp1")
        add_exchange(sm, "second", "resp2")
        assert sm.is_eligible_for_autoname() is False


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------

class TestLoad:
    def test_loads_valid_session(self, tmp_path):
        sm = make_sm(tmp_path)
        add_exchange(sm, "hello", "world")
        original_id = sm.session_id

        sm2 = make_sm(tmp_path)
        result = sm2.load(original_id)
        assert result is True
        assert sm2.session_id == original_id
        assert len(sm2.history) == 2

    def test_returns_false_for_missing_file(self, tmp_path):
        sm = make_sm(tmp_path)
        assert sm.load("sess_nonexistent") is False

    def test_returns_false_for_corrupted_file(self, tmp_path):
        sm = make_sm(tmp_path)
        bad_file = sm.base_dir / "sess_bad.json"
        bad_file.write_text("")  # empty = corrupted
        assert sm.load("sess_bad") is False


# ---------------------------------------------------------------------------
# get_recent_sessions
# ---------------------------------------------------------------------------

class TestGetRecentSessions:
    def test_returns_sessions_sorted_by_updated_at(self, tmp_path):
        sm = make_sm(tmp_path)

        # Create two sessions with different timestamps
        add_exchange(sm, "older", "resp")
        older_id = sm.session_id

        time.sleep(0.01)  # ensure different timestamps
        sm2 = make_sm(tmp_path)
        add_exchange(sm2, "newer", "resp")

        # Both sessions share the same base_dir via the metadata file
        sm2.base_dir = sm.base_dir
        sm2.metadata_file = sm.metadata_file
        sm2._update_meta_entry()

        recent = sm.get_recent_sessions(limit=20)
        ids = [r[0] for r in recent]
        # Most recent should come first
        assert ids[0] == sm2.session_id

    def test_skips_missing_session_files(self, tmp_path):
        sm = make_sm(tmp_path)
        # Write a metadata entry pointing to a non-existent file
        meta = {"sess_ghost": {"name": "Ghost", "updated_at": int(time.time()), "message_count": 2}}
        sm._save_metadata(meta)
        recent = sm.get_recent_sessions()
        assert all(r[0] != "sess_ghost" for r in recent)

    def test_skips_corrupted_session_files(self, tmp_path):
        sm = make_sm(tmp_path)
        bad_file = sm.base_dir / "sess_corrupt.json"
        bad_file.write_text("")
        meta = {"sess_corrupt": {"name": "Bad", "updated_at": int(time.time()), "message_count": 1}}
        sm._save_metadata(meta)
        recent = sm.get_recent_sessions()
        assert all(r[0] != "sess_corrupt" for r in recent)

    def test_backfills_missing_message_count(self, tmp_path):
        sm = make_sm(tmp_path)
        add_exchange(sm, "q", "a")
        # Corrupt the metadata to remove message_count
        meta = sm._load_metadata()
        meta[sm.session_id].pop("message_count", None)
        meta[sm.session_id].pop("updated_at", None)
        sm._save_metadata(meta)

        recent = sm.get_recent_sessions()
        info = dict(recent)[sm.session_id]
        assert info["message_count"] == 2  # backfilled from history

    def test_respects_limit(self, tmp_path):
        sm = make_sm(tmp_path)
        # Create 5 sessions
        for i in range(5):
            s = make_sm(tmp_path)
            add_exchange(s, f"q{i}", f"a{i}")
        recent = sm.get_recent_sessions(limit=3)
        assert len(recent) <= 3
