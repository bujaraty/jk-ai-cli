APP_NAME = "jk-ai-workspace"
DEFAULT_MODEL = "gpt-4o"
CONFIG_DIR_NAME = "jk-ai"

from platformdirs import user_config_dir
SHARED_CONFIG_PATH = user_config_dir(CONFIG_DIR_NAME)
