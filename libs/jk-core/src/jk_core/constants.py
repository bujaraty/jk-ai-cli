from platformdirs import user_config_dir
from pathlib import Path

APP_NAME = "jk-ai-workspace"
CONFIG_DIR_NAME = "jk-ai"
SHARED_CONFIG_PATH = user_config_dir(CONFIG_DIR_NAME)
SESSIONS_DIR = Path(SHARED_CONFIG_PATH) / "sessions"
SEARCH_INDEX_PATH = Path(SHARED_CONFIG_PATH) / "search_index.json"
DEFAULT_MODEL = "gemini-flash-latest"

def ensure_dirs():
    """Call once at app startup to create required directories."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
