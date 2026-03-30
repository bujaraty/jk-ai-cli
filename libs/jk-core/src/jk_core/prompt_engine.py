import yaml
from pathlib import Path
from jinja2 import Template
from jk_core.constants import CONFIG_FILE_PATH, PROMPTS_DIR

# In-package prompts dir — fallback for legacy installs where config
# hasn't been migrated to SHARED_CONFIG_PATH yet
_LEGACY_PROMPT_DIR = Path(__file__).parent / "prompts"


def _config_path() -> Path:
    """Returns the active config.yaml path — shared config dir first, legacy fallback."""
    if CONFIG_FILE_PATH.exists():
        return CONFIG_FILE_PATH
    legacy = _LEGACY_PROMPT_DIR / "config.yaml"
    if legacy.exists():
        return legacy
    raise FileNotFoundError(
        f"config.yaml not found.\n"
        f"Expected at: {CONFIG_FILE_PATH}\n"
        f"Run 'jk-ai-init' to create a starter config."
    )


def _prompts_dir() -> Path:
    """Returns the active prompts directory — shared config dir first, legacy fallback."""
    if PROMPTS_DIR.exists() and any(PROMPTS_DIR.iterdir()):
        return PROMPTS_DIR
    if _LEGACY_PROMPT_DIR.exists():
        return _LEGACY_PROMPT_DIR
    return PROMPTS_DIR  # return the canonical path even if empty


def load_config() -> dict:
    """Load config.yaml from the shared config directory (or legacy location)."""
    with open(_config_path(), "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_project(project_name: str) -> dict:
    """Returns the project config dict or raises ValueError."""
    config = load_config()
    project_cfg = config.get("projects", {}).get(project_name)
    if not project_cfg:
        raise ValueError(
            f"Project '{project_name}' not defined in config.yaml.\n"
            f"Edit {CONFIG_FILE_PATH} to add it."
        )
    return project_cfg


def assemble_prompt(project_name: str, variables: dict = None) -> str:
    """
    Assembles the system prompt for a project by concatenating its
    component files and rendering Jinja2 variables.
    Component paths are resolved relative to the active prompts directory.
    """
    project_cfg = get_project(project_name)
    prompts_base = _prompts_dir()
    components = project_cfg.get("components", [])
    combined_content = []

    for comp_path in components:
        full_path = prompts_base / comp_path
        if full_path.exists():
            with open(full_path, "r", encoding="utf-8") as f:
                combined_content.append(f.read())
        else:
            print(f"⚠️ Warning: Component '{comp_path}' not found at {full_path}")

    raw_prompt = "\n\n".join(combined_content)

    if variables:
        template = Template(raw_prompt)
        return template.render(**variables)
    return raw_prompt


def get_required_vars(project_name: str) -> list:
    """Returns the list of required template variables for a project."""
    project_cfg = get_project(project_name)
    return project_cfg.get("required_vars", [])


def get_image_dir(project_name: str) -> Path:
    """
    Returns the image output directory for a project.
    Falls back to DEFAULT_IMAGE_DIR if not set in config.
    """
    from jk_core.constants import DEFAULT_IMAGE_DIR
    try:
        project_cfg = get_project(project_name)
        raw = project_cfg.get("image_dir")
        if raw:
            return Path(raw).expanduser().resolve()
    except (ValueError, FileNotFoundError):
        pass
    return DEFAULT_IMAGE_DIR
