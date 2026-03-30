"""
Shared pytest fixtures.

All tests that touch the filesystem use tmp_path so they never
read from or write to the real ~/.config/jk-ai directory.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """
    Redirects SHARED_CONFIG_PATH and all derived constants to a temp dir.
    Returns the temp Path so individual tests can pre-populate files.
    """
    monkeypatch.setattr("jk_core.constants.SHARED_CONFIG_PATH", str(tmp_path))
    monkeypatch.setattr("jk_core.constants.SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr("jk_core.constants.SEARCH_INDEX_PATH", tmp_path / "search_index.json")
    (tmp_path / "sessions").mkdir()
    return tmp_path


@pytest.fixture
def sample_models():
    """A realistic set of model entries for Orchestrator tests."""
    return [
        {
            "id": "models/gemini-2.5-flash",
            "display_name": "Gemini 2.5 Flash",
            "provider": "google",
            "capabilities": {"generateContent": {"status": "PASS"}},
        },
        {
            "id": "models/gemini-2.5-flash-lite",
            "display_name": "Gemini 2.5 Flash Lite",
            "provider": "google",
            "capabilities": {"generateContent": {"status": "PASS"}},
        },
        {
            "id": "models/gemini-2.5-pro",
            "display_name": "Gemini 2.5 Pro",
            "provider": "google",
            "capabilities": {"generateContent": {"status": "PASS"}},
        },
        {
            "id": "models/gemini-flash-latest",
            "display_name": "Gemini Flash Latest",
            "provider": "google",
            "capabilities": {"generateContent": {"status": "PASS"}},
        },
        {
            "id": "models/gemini-2.5-flash-preview",
            "display_name": "Gemini 2.5 Flash Preview",
            "provider": "google",
            "capabilities": {"generateContent": {"status": "PASS"}},
        },
        {
            "id": "models/gemini-2.5-pro-fail",
            "display_name": "Gemini 2.5 Pro (failing)",
            "provider": "google",
            "capabilities": {"generateContent": {"status": "FAIL"}},
        },
        {
            "id": "models/embed-001",
            "display_name": "Embed 001",
            "provider": "google",
            "capabilities": {"embedContent": {"status": "PASS"}},
        },
    ]


@pytest.fixture
def two_keys_yaml(tmp_path):
    """Writes a keys.yaml with two google/free keys and returns the path."""
    keys = {
        "google": {
            "free": [
                {"id": "key_a", "key": "fake-api-key-a"},
                {"id": "key_b", "key": "fake-api-key-b"},
            ]
        }
    }
    import yaml
    keys_file = tmp_path / "keys.yaml"
    keys_file.write_text(yaml.dump(keys))
    return tmp_path
