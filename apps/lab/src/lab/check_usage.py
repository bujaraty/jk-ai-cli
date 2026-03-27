from jk_core.key_manager import KeyManager
from rich.console import Console
from rich.table import Table

console = Console()

def show_usage():
    km = KeyManager(provider="google")
    state = km._load_state()
    usage = state.get("usage", {})

    if not usage:
        console.print("[yellow]No usage data recorded yet.[/yellow]")
        return

    table = Table(title="📊 API Usage Statistics", show_lines=True)
    table.add_column("Key ID", style="cyan")
    table.add_column("Model", style="magenta")
    table.add_column("Requests", justify="right")
    table.add_column("In Tokens", justify="right", style="dim green")
    table.add_column("Out Tokens", justify="right", style="dim blue")

    for kid, data in usage.items():
        for mid, stats in data.get("models", {}).items():
            table.add_row(
                kid,
                mid.split("/")[-1], # Show short name
                str(stats["request_count"]),
                str(stats["total_input_tokens"]),
                str(stats["total_output_tokens"])
            )

    console.print(table)

if __name__ == "__main__":
    show_usage()

