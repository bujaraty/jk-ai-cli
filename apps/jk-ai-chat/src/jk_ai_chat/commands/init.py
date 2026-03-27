from rich.console import Console
from jk_core.model_registry import ModelRegistry
from jk_core.model_tester import ModelTester
from jk_core.constants import SHARED_CONFIG_PATH
from jk_core.constants import CONFIG_DIR_NAME
from rich.table import Table
from rich.text import Text
from pathlib import Path

console = Console()
APP_NAME = "jk-ai"

def ensure_folders():
    """Phase 1: Basic setup of directories and empty files."""
    console.print(f"[bold blue]🚀 Initializing {CONFIG_DIR_NAME} system...[/bold blue]")
    path = Path(SHARED_CONFIG_PATH)
    path.mkdir(parents=True, exist_ok=True)
    console.print(f"📁 Workspace initialized at: [yellow]{path}[/yellow]")

    env_file = path / ".env"
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
    console.print(f"💡 [italic]Next step: Please ensures to have your API keys in {env_file}[/italic]")

def run_system_probe():
    # Phase 1: Discovery
    registry = ModelRegistry()
    console.print("[bold blue]🔍 Step 1: Discovering models from Google...[/bold blue]")
    try:
        registry.refresh_cache()
    except Exception as e:
        console.print(f"[bold red]❌ Discovery failed:[/bold red] {e}")
        return

    # Phase 2: Synchronization (Probing)
    tester = ModelTester()
    console.print("[bold blue]🧪 Step 2: Syncing model status (Probing)...[/bold blue]")
    with console.status("[bold green]Probing capabilities..."):
        results, key_id = tester.sync_model_status()

    # Phase 3: Reporting
    console.print(f"\n🔑 [bold cyan]Active Key Used:[/bold cyan] [yellow]{key_id}[/yellow]\n")

    table = Table(title="Action-Level Usability Report", show_lines=True)
    table.add_column("Model ID", style="cyan")
    table.add_column("Action", style="magenta")
    table.add_column("Status", justify="center")
    table.add_column("Error Detail", style="dim red")

    for r in results:
        status_text = r['status']
        status_color = "green" if status_text == "PASS" else "red"

        status_cell = Text(status_text, style=status_color)
        error_cell = Text(str(r.get('error', "-")))

        table.add_row(r['id'], r['action'], status_cell, error_cell)

    console.print(table)
    console.print("\n[bold green]✅ System initialization and probing complete![/bold green]")

    return results, key_id

def init_command(probe: bool):
    """The main coordinator for the jk-ai-init command."""
    ensure_folders()
    
    if probe:
        run_system_probe()
    else:
        console.print("\n[dim]Tip: Run 'jk-ai-init --probe' to verify your API keys and models.[/dim]")

