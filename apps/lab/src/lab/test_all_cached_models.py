from jk_core.model_tester import ModelTester
from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console()

def run_bulk_test():
    tester = ModelTester(provider="google")

    with console.status("[bold green]Probing Text & Embedding models..."):
        # Explicit unpacking
        results, key_id = tester.sync_model_status()

    if not results:
        console.print("[bold red]❌ No models or keys found.[/bold red]")
        return

    console.print(f"\n🔑 [bold cyan]Active Key Used:[/bold cyan] [yellow]{key_id}[/yellow]\n")

    table = Table(title="Model Usability Report (Text/Embed)", show_lines=True)
    table.add_column("Model ID", style="cyan")
    table.add_column("Capabilities", style="magenta")
    table.add_column("Status", justify="center")
    table.add_column("Error Detail", style="dim red")

    for r in results:
        # Define the color based on status
        status_text = r['status']
        status_color = "green" if status_text == "PASS" else ("yellow" if status_text == "SKIPPED" else "red")

        # FIX: Create a Text object for Status with a style instead of markup tags
        status_cell = Text(status_text, style=status_color)

        # Capability string
        actions = r.get('actions', [])
        actions_str = ", ".join([a.replace("Content", "") for a in actions if "Content" in a]) or "Other"

        # FIX: Create a Text object for Error (ensures no markup is parsed)
        error_cell = Text(str(r.get('error', "-")))

        table.add_row(
            r['id'],
            actions_str,
            status_cell, # Safe: No more [color] tags
            error_cell   # Safe: Raw text only
        )

    console.print(table)

if __name__ == "__main__":
    run_bulk_test()

