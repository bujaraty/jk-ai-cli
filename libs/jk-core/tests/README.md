# jk-core tests

## Setup

Add pytest to `libs/jk-core/pyproject.toml` under `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "pyyaml"]
```

Then install:
```bash
uv sync --extra dev
```

## Running

From the workspace root:
```bash
# All tests
pytest libs/jk-core/tests/

# A single file
pytest libs/jk-core/tests/test_orchestrator.py

# Verbose with test names
pytest libs/jk-core/tests/ -v

# Stop on first failure
pytest libs/jk-core/tests/ -x
```

## Structure

```
tests/
  conftest.py            — shared fixtures (tmp_config, sample_models, two_keys_yaml)
  test_orchestrator.py   — scoring, tier preferences, ranking order
  test_key_manager.py    — exhaustion, daily reset, get_available_key, record_usage
  test_session_manager.py — time_travel, undo, branch, autoname, load, get_recent_sessions
```
