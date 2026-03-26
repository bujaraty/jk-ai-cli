from platformdirs import user_config_dir

APP_NAME = "jk-ai-workspace"
CONFIG_DIR_NAME = "jk-ai"
SHARED_CONFIG_PATH = user_config_dir(CONFIG_DIR_NAME)
DEFAULT_MODEL = "gemini-flash-latest"
