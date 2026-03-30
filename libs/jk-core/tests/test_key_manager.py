"""
Tests for KeyManager.

Uses tmp_path via the tmp_config fixture so no real keys.yaml or
state.json is ever touched. Keys are written directly to tmp_path
for each test that needs them.
"""
import json
import yaml
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from jk_core.key_manager import KeyManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_km(tmp_config):
    """KeyManager pointed at the temp directory."""
    km = KeyManager(provider="google", tier="free")
    km.config_dir = tmp_config
    km.keys_file  = tmp_config / "keys.yaml"
    km.state_file = tmp_config / "state.json"
    return km


def write_keys(tmp_path, keys: list):
    """Write a keys.yaml with the given list of {id, key} dicts."""
    data = {"google": {"free": keys}}
    (tmp_path / "keys.yaml").write_text(yaml.dump(data))


def write_state(tmp_path, state: dict):
    (tmp_path / "state.json").write_text(json.dumps(state))


def read_state(tmp_path) -> dict:
    return json.loads((tmp_path / "state.json").read_text())


def future(hours=10) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def past(hours=2) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


# ---------------------------------------------------------------------------
# _load_keys
# ---------------------------------------------------------------------------

class TestLoadKeys:
    def test_returns_empty_when_no_file(self, tmp_config):
        km = make_km(tmp_config)
        assert km._load_keys() == []

    def test_returns_keys_for_provider_and_tier(self, tmp_config):
        write_keys(tmp_config, [{"id": "k1", "key": "abc"}])
        km = make_km(tmp_config)
        keys = km._load_keys()
        assert len(keys) == 1
        assert keys[0]["id"] == "k1"

    def test_wrong_tier_returns_empty(self, tmp_config):
        write_keys(tmp_config, [{"id": "k1", "key": "abc"}])
        km = make_km(tmp_config)
        km.tier = "paid"
        assert km._load_keys() == []


# ---------------------------------------------------------------------------
# get_available_key
# ---------------------------------------------------------------------------

class TestGetAvailableKey:
    def test_returns_first_key_when_none_exhausted(self, tmp_config):
        write_keys(tmp_config, [
            {"id": "key_a", "key": "val_a"},
            {"id": "key_b", "key": "val_b"},
        ])
        km = make_km(tmp_config)
        val, kid = km.get_available_key(model_id="models/gemini-flash")
        assert val == "val_a"
        assert kid == "key_a"

    def test_skips_exhausted_key_returns_next(self, tmp_config):
        write_keys(tmp_config, [
            {"id": "key_a", "key": "val_a"},
            {"id": "key_b", "key": "val_b"},
        ])
        write_state(tmp_config, {
            "usage": {
                "key_a": {
                    "models": {
                        "models/gemini-flash": {"reset_at": future(10)}
                    }
                }
            }
        })
        km = make_km(tmp_config)
        val, kid = km.get_available_key(model_id="models/gemini-flash")
        assert kid == "key_b"

    def test_returns_none_when_all_exhausted(self, tmp_config):
        write_keys(tmp_config, [{"id": "key_a", "key": "val_a"}])
        write_state(tmp_config, {
            "usage": {
                "key_a": {
                    "models": {
                        "models/gemini-flash": {"reset_at": future(10)}
                    }
                }
            }
        })
        km = make_km(tmp_config)
        val, kid = km.get_available_key(model_id="models/gemini-flash")
        assert val is None
        assert kid is None

    def test_ignores_exhaustion_after_reset_time(self, tmp_config):
        """A key with a reset_at in the past should be treated as available."""
        write_keys(tmp_config, [{"id": "key_a", "key": "val_a"}])
        write_state(tmp_config, {
            "usage": {
                "key_a": {
                    "models": {
                        "models/gemini-flash": {"reset_at": past(2)}
                    }
                }
            }
        })
        km = make_km(tmp_config)
        val, kid = km.get_available_key(model_id="models/gemini-flash")
        assert kid == "key_a"

    def test_probe_mode_skips_exhaustion_check(self, tmp_config):
        """model_id=None should return a key even if models are exhausted."""
        write_keys(tmp_config, [{"id": "key_a", "key": "val_a"}])
        write_state(tmp_config, {
            "usage": {
                "key_a": {
                    "models": {
                        "models/gemini-flash": {"reset_at": future(10)}
                    }
                }
            }
        })
        km = make_km(tmp_config)
        val, kid = km.get_available_key(model_id=None)
        assert kid == "key_a"

    def test_exhaustion_on_different_model_does_not_block(self, tmp_config):
        """Key exhausted for model A should still be available for model B."""
        write_keys(tmp_config, [{"id": "key_a", "key": "val_a"}])
        write_state(tmp_config, {
            "usage": {
                "key_a": {
                    "models": {
                        "models/gemini-pro": {"reset_at": future(10)}
                    }
                }
            }
        })
        km = make_km(tmp_config)
        val, kid = km.get_available_key(model_id="models/gemini-flash")
        assert kid == "key_a"

    def test_corrupted_reset_at_treated_as_available(self, tmp_config):
        write_keys(tmp_config, [{"id": "key_a", "key": "val_a"}])
        write_state(tmp_config, {
            "usage": {
                "key_a": {
                    "models": {
                        "models/gemini-flash": {"reset_at": "not-a-date"}
                    }
                }
            }
        })
        km = make_km(tmp_config)
        val, kid = km.get_available_key(model_id="models/gemini-flash")
        assert kid == "key_a"

    def test_returns_none_when_no_keys_file(self, tmp_config):
        km = make_km(tmp_config)
        val, kid = km.get_available_key(model_id="models/gemini-flash")
        assert val is None


# ---------------------------------------------------------------------------
# mark_exhausted
# ---------------------------------------------------------------------------

class TestMarkExhausted:
    def test_sets_status_and_reset_at(self, tmp_config):
        km = make_km(tmp_config)
        km.mark_exhausted("key_a", "models/gemini-flash")
        state = read_state(tmp_config)
        entry = state["usage"]["key_a"]["models"]["models/gemini-flash"]
        assert entry["status"] == "exhausted"
        assert "reset_at" in entry

    def test_reset_at_is_future_08_utc(self, tmp_config):
        km = make_km(tmp_config)
        km.mark_exhausted("key_a", "models/gemini-flash")
        state = read_state(tmp_config)
        reset_at = datetime.fromisoformat(
            state["usage"]["key_a"]["models"]["models/gemini-flash"]["reset_at"]
        )
        now = datetime.now(timezone.utc)
        assert reset_at > now
        assert reset_at.hour == 8
        assert reset_at.minute == 0

    def test_does_not_affect_other_model(self, tmp_config):
        km = make_km(tmp_config)
        km.mark_exhausted("key_a", "models/gemini-flash")
        state = read_state(tmp_config)
        assert "models/gemini-pro" not in state["usage"]["key_a"]["models"]

    def test_does_not_affect_other_key(self, tmp_config):
        km = make_km(tmp_config)
        km.mark_exhausted("key_a", "models/gemini-flash")
        state = read_state(tmp_config)
        assert "key_b" not in state["usage"]


# ---------------------------------------------------------------------------
# _daily_reset_time
# ---------------------------------------------------------------------------

class TestDailyResetTime:
    def test_returns_today_08_if_before_08(self, tmp_config):
        km = make_km(tmp_config)
        before_reset = datetime(2026, 1, 1, 7, 0, 0, tzinfo=timezone.utc)
        result = km._daily_reset_time(before_reset)
        assert result.day == 1
        assert result.hour == 8

    def test_returns_tomorrow_08_if_after_08(self, tmp_config):
        km = make_km(tmp_config)
        after_reset = datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        result = km._daily_reset_time(after_reset)
        assert result.day == 2
        assert result.hour == 8

    def test_returns_tomorrow_08_exactly_at_08(self, tmp_config):
        km = make_km(tmp_config)
        at_reset = datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        result = km._daily_reset_time(at_reset)
        assert result.day == 2


# ---------------------------------------------------------------------------
# record_usage
# ---------------------------------------------------------------------------

class TestRecordUsage:
    def test_initialises_entry_on_first_call(self, tmp_config):
        km = make_km(tmp_config)
        km.record_usage("key_a", "models/gemini-flash", 10, 5)
        state = read_state(tmp_config)
        entry = state["usage"]["key_a"]["models"]["models/gemini-flash"]
        assert entry["request_count"] == 1
        assert entry["total_input_tokens"] == 10
        assert entry["total_output_tokens"] == 5

    def test_accumulates_across_calls(self, tmp_config):
        km = make_km(tmp_config)
        km.record_usage("key_a", "models/gemini-flash", 10, 5)
        km.record_usage("key_a", "models/gemini-flash", 20, 8)
        state = read_state(tmp_config)
        entry = state["usage"]["key_a"]["models"]["models/gemini-flash"]
        assert entry["request_count"] == 2
        assert entry["total_input_tokens"] == 30
        assert entry["total_output_tokens"] == 13

    def test_different_models_tracked_separately(self, tmp_config):
        km = make_km(tmp_config)
        km.record_usage("key_a", "models/gemini-flash", 10, 5)
        km.record_usage("key_a", "models/gemini-pro", 20, 8)
        state = read_state(tmp_config)
        models = state["usage"]["key_a"]["models"]
        assert models["models/gemini-flash"]["request_count"] == 1
        assert models["models/gemini-pro"]["request_count"] == 1

    def test_resets_counters_after_window_rolls_over(self, tmp_config):
        """Simulate: entry has a past reset_at → counters should reset on next record."""
        km = make_km(tmp_config)
        # Pre-populate with stale data from a previous window
        state = {
            "usage": {
                "key_a": {
                    "models": {
                        "models/gemini-flash": {
                            "request_count": 99,
                            "total_input_tokens": 5000,
                            "total_output_tokens": 2000,
                            "status": "active",
                            "last_used": past(25),
                            "window_start": past(25),
                            "reset_at": past(2),  # window already expired
                        }
                    }
                }
            }
        }
        write_state(tmp_config, state)
        km.record_usage("key_a", "models/gemini-flash", 10, 5)
        entry = read_state(tmp_config)["usage"]["key_a"]["models"]["models/gemini-flash"]
        # Should have reset then counted this one request
        assert entry["request_count"] == 1
        assert entry["total_input_tokens"] == 10
        assert entry["total_output_tokens"] == 5

    def test_does_not_reset_before_window_expires(self, tmp_config):
        """reset_at in the future → counters should keep accumulating."""
        km = make_km(tmp_config)
        state = {
            "usage": {
                "key_a": {
                    "models": {
                        "models/gemini-flash": {
                            "request_count": 5,
                            "total_input_tokens": 100,
                            "total_output_tokens": 50,
                            "status": "active",
                            "last_used": past(1),
                            "window_start": past(1),
                            "reset_at": future(10),  # still in current window
                        }
                    }
                }
            }
        }
        write_state(tmp_config, state)
        km.record_usage("key_a", "models/gemini-flash", 10, 5)
        entry = read_state(tmp_config)["usage"]["key_a"]["models"]["models/gemini-flash"]
        assert entry["request_count"] == 6
        assert entry["total_input_tokens"] == 110

    def test_window_start_recorded_on_first_call(self, tmp_config):
        km = make_km(tmp_config)
        km.record_usage("key_a", "models/gemini-flash", 10, 5)
        entry = read_state(tmp_config)["usage"]["key_a"]["models"]["models/gemini-flash"]
        assert "window_start" in entry

    def test_window_start_updated_after_reset(self, tmp_config):
        km = make_km(tmp_config)
        old_start = past(25)
        state = {
            "usage": {
                "key_a": {
                    "models": {
                        "models/gemini-flash": {
                            "request_count": 5,
                            "total_input_tokens": 100,
                            "total_output_tokens": 50,
                            "status": "active",
                            "last_used": old_start,
                            "window_start": old_start,
                            "reset_at": past(2),
                        }
                    }
                }
            }
        }
        write_state(tmp_config, state)
        km.record_usage("key_a", "models/gemini-flash", 10, 5)
        entry = read_state(tmp_config)["usage"]["key_a"]["models"]["models/gemini-flash"]
        assert entry["window_start"] != old_start

# ---------------------------------------------------------------------------
# _append_usage_history / usage_history.jsonl
# ---------------------------------------------------------------------------

class TestUsageHistory:
    def test_history_file_created_on_rollover(self, tmp_config):
        km = make_km(tmp_config)
        state = {
            "usage": {
                "key_a": {
                    "models": {
                        "models/gemini-flash": {
                            "request_count": 5,
                            "total_input_tokens": 100,
                            "total_output_tokens": 50,
                            "status": "active",
                            "last_used": past(25),
                            "window_start": past(25),
                            "reset_at": past(2),
                        }
                    }
                }
            }
        }
        write_state(tmp_config, state)
        km.record_usage("key_a", "models/gemini-flash", 10, 5)
        assert (tmp_config / "usage_history.jsonl").exists()

    def test_history_line_contains_correct_fields(self, tmp_config):
        km = make_km(tmp_config)
        state = {
            "usage": {
                "key_a": {
                    "models": {
                        "models/gemini-flash": {
                            "request_count": 5,
                            "total_input_tokens": 100,
                            "total_output_tokens": 50,
                            "status": "active",
                            "last_used": past(25),
                            "window_start": "2026-03-30T08:00:00+00:00",
                            "reset_at": past(2),
                        }
                    }
                }
            }
        }
        write_state(tmp_config, state)
        km.record_usage("key_a", "models/gemini-flash", 10, 5)

        lines = (tmp_config / "usage_history.jsonl").read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["date"] == "2026-03-30"
        assert record["key_id"] == "key_a"
        assert record["model_id"] == "models/gemini-flash"
        assert record["requests"] == 5
        assert record["input_tokens"] == 100
        assert record["output_tokens"] == 50

    def test_no_history_written_within_same_window(self, tmp_config):
        km = make_km(tmp_config)
        state = {
            "usage": {
                "key_a": {
                    "models": {
                        "models/gemini-flash": {
                            "request_count": 5,
                            "total_input_tokens": 100,
                            "total_output_tokens": 50,
                            "status": "active",
                            "last_used": past(1),
                            "window_start": past(1),
                            "reset_at": future(10),  # still in current window
                        }
                    }
                }
            }
        }
        write_state(tmp_config, state)
        km.record_usage("key_a", "models/gemini-flash", 10, 5)
        assert not (tmp_config / "usage_history.jsonl").exists()

    def test_multiple_rollovers_append_multiple_lines(self, tmp_config):
        """Each key/model rollover appends a separate line."""
        km = make_km(tmp_config)
        # Two models, both with expired windows
        state = {
            "usage": {
                "key_a": {
                    "models": {
                        "models/gemini-flash": {
                            "request_count": 3,
                            "total_input_tokens": 60,
                            "total_output_tokens": 30,
                            "status": "active",
                            "last_used": past(25),
                            "window_start": past(25),
                            "reset_at": past(2),
                        },
                        "models/gemini-pro": {
                            "request_count": 1,
                            "total_input_tokens": 200,
                            "total_output_tokens": 80,
                            "status": "active",
                            "last_used": past(25),
                            "window_start": past(25),
                            "reset_at": past(2),
                        },
                    }
                }
            }
        }
        write_state(tmp_config, state)
        km.record_usage("key_a", "models/gemini-flash", 10, 5)
        km.record_usage("key_a", "models/gemini-pro", 20, 8)

        lines = (tmp_config / "usage_history.jsonl").read_text().strip().split("\n")
        assert len(lines) == 2
        models_logged = {json.loads(l)["model_id"] for l in lines}
        assert "models/gemini-flash" in models_logged
        assert "models/gemini-pro" in models_logged

    def test_history_not_written_for_new_entry_without_reset_at(self, tmp_config):
        """Brand new entries have no reset_at yet — no history should be written."""
        km = make_km(tmp_config)
        km.record_usage("key_a", "models/gemini-flash", 10, 5)
        assert not (tmp_config / "usage_history.jsonl").exists()

    def test_corrupted_window_start_uses_unknown_date(self, tmp_config):
        km = make_km(tmp_config)
        state = {
            "usage": {
                "key_a": {
                    "models": {
                        "models/gemini-flash": {
                            "request_count": 1,
                            "total_input_tokens": 10,
                            "total_output_tokens": 5,
                            "status": "active",
                            "last_used": past(25),
                            "window_start": "not-a-date",
                            "reset_at": past(2),
                        }
                    }
                }
            }
        }
        write_state(tmp_config, state)
        km.record_usage("key_a", "models/gemini-flash", 10, 5)
        lines = (tmp_config / "usage_history.jsonl").read_text().strip().split("\n")
        record = json.loads(lines[0])
        assert record["date"] == "unknown"
