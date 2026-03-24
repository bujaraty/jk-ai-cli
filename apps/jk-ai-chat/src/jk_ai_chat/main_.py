import os
from pathlib import Path
from platformdirs import user_config_dir, user_data_dir
from rich.console import Console

console = Console()
APP_NAME = "jk-ai"

def init_command():
    """Logic สำหรับคำสั่ง jk-ai-init"""
    console.print(f"[bold blue]🚀 Initializing {APP_NAME} system...[/bold blue]")

    # 1. กำหนด Path มาตรฐาน
    config_dir = Path(user_config_dir(APP_NAME))
    data_dir = Path(user_data_dir(APP_NAME))
    env_file = config_dir / ".env"

    # 2. สร้าง Folders (ถ้ายังไม่มี)
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"📁 Config folder: [yellow]{config_dir}[/yellow]")
    console.print(f"📁 Data folder:   [yellow]{data_dir}[/yellow]")

    # 3. สร้างไฟล์ .env เริ่มต้น (ถ้ายังไม่มี)
    if not env_file.exists():
        with open(env_file, "w") as f:
            f.write("# JK-AI Configuration\n")
            f.write("OPENAI_API_KEY=your_key_here\n")
            f.write("GEMINI_API_KEY=your_key_here\n")
        console.print(f"✨ Created default .env at: [green]{env_file}[/green]")
    else:
        console.print(f"ℹ️  .env already exists at: [dim]{env_file}[/dim]")

    console.print("\n[bold green]✅ System is ready![/bold green]")
    console.print(f"💡 [italic]Next step: Add your API keys in {env_file}[/italic]")

def main():
    # อันนี้คือของ jk-ai-cli (เดิม)
    print("hello chat")

