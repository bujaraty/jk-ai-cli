import yaml
from pathlib import Path
from jinja2 import Template

# หาตำแหน่งของโฟลเดอร์ prompts
PROMPT_BASE_DIR = Path(__file__).parent / "prompts"

def load_config():
    """โหลดไฟล์ config.yaml ที่ระบุชิ้นส่วนของแต่ละโปรเจกต์"""
    config_path = PROMPT_BASE_DIR / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found at {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def assemble_prompt(project_name, variables=None):
    """
    1. อ่านชิ้นส่วน (Components) ตามโปรเจกต์
    2. นำเนื้อหามาต่อกัน
    3. Render ด้วย Jinja2 ตามตัวแปรที่ส่งมา
    """
    config = load_config()
    project_cfg = config.get("projects", {}).get(project_name)

    if not project_cfg:
        raise ValueError(f"Project '{project_name}' not defined in config.yaml")

    components = project_cfg.get("components", [])
    combined_content = []

    # 1. ดึงเนื้อหาจากทุกไฟล์มาต่อกัน
    for comp_path in components:
        full_path = PROMPT_BASE_DIR / comp_path
        if full_path.exists():
            with open(full_path, "r", encoding="utf-8") as f:
                combined_content.append(f.read())
        else:
            print(f"⚠️ Warning: Component {comp_path} not found.")

    raw_prompt = "\n\n".join(combined_content)

    # 2. Render ด้วย Jinja2 (ถ้ามีตัวแปร)
    if variables:
        template = Template(raw_prompt)
        return template.render(**variables)
    
    return raw_prompt

def get_required_vars(project_name):
    """ดึงรายการ required_vars จาก config.yaml"""
    config = load_config()
    project_cfg = config.get("projects", {}).get(project_name, {})
    print(project_cfg)
    return project_cfg.get("required_vars", [])

