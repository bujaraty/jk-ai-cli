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
    """Phase 1: Basic setup of directories and config files."""
    from jk_core.constants import CONFIG_FILE_PATH, PROMPTS_DIR, DEFAULT_IMAGE_DIR
    console.print(f"[bold blue]🚀 Initializing {CONFIG_DIR_NAME} system...[/bold blue]")
    path = Path(SHARED_CONFIG_PATH)
    path.mkdir(parents=True, exist_ok=True)
    console.print(f"📁 Workspace initialized at: [yellow]{path}[/yellow]")

    # .env
    env_file = path / ".env"
    if not env_file.exists():
        with open(env_file, "w") as f:
            f.write("# JK-AI Configuration\n")
            f.write("OPENAI_API_KEY=your_key_here\n")
            f.write("GEMINI_API_KEY=your_key_here\n")
        console.print(f"✨ Created default .env at: [green]{env_file}[/green]")
    else:
        console.print(f"ℹ️  .env already exists at: [dim]{env_file}[/dim]")

    # prompts/ directory
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    console.print(f"📁 Prompts directory: [yellow]{PROMPTS_DIR}[/yellow]")

    # config.yaml — starter template if not present
    if not CONFIG_FILE_PATH.exists():
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(
                "# JK-AI Project Configuration\n"
                "# Each project defines its prompt components, variables, and image output dir.\n"
                "# Prompt component files live in: " + str(PROMPTS_DIR) + "\n\n"
                "projects:\n"
                "  cli-dev:\n"
                "    components: []\n"
                "    required_vars: []\n"
                "    image_dir: " + str(DEFAULT_IMAGE_DIR) + "\n\n"
                "  # Add more projects below:\n"
                "  # my-project:\n"
                "  #   components:\n"
                "  #     - base.md\n"
                "  #     - my_context.md\n"
                "  #   required_vars: []\n"
                "  #   image_dir: ~/Projects/my-project/images\n"
            )
        console.print(f"✨ Created starter config at: [green]{CONFIG_FILE_PATH}[/green]")
    else:
        console.print(f"ℹ️  config.yaml already exists at: [dim]{CONFIG_FILE_PATH}[/dim]")

    # Default image output directory
    DEFAULT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    console.print(f"🖼  Default image dir: [yellow]{DEFAULT_IMAGE_DIR}[/yellow]")

    console.print("\n[bold green]✅ System is ready![/bold green]")
    console.print(f"💡 [italic]Edit {CONFIG_FILE_PATH} to configure your projects.[/italic]")

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

