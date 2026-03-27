from jk_core.orchestrator import Orchestrator
from rich.console import Console
from rich.table import Table

console = Console()

def debug_combinations(action="generateContent"):
    # Testing combinations: Tier x Latest Flag
    test_cases = [
        ("lite", False),
        ("lite", True),
        ("normal", False),
        ("normal", True),
        ("high", False),
        ("high", True)
    ]

    for tier, latest in test_cases:
        console.print(f"\n[bold blue]🧪 Tier: {tier.upper()} | Latest: {latest}[/bold blue]")

        orch = Orchestrator(provider="google", tier=tier, prefer_latest=latest)
        rankings = orch.get_rankings(action)

        if not rankings:
            console.print("[red]❌ No models found.[/red]")
            continue

        table = Table(show_lines=True)
        table.add_column("Rank", justify="center")
        table.add_column("Model ID", style="cyan")
        table.add_column("Score", justify="right", style="bold yellow")
        table.add_column("Logic Breakdown")

        for i, r in enumerate(rankings[:10], 1):
            table.add_row(str(i), r['id'], str(r['score']), ", ".join(r['reasons']))

        console.print(table)
        winner = rankings[0]
        console.print(f"🏆 [green]Winner:[/green] {winner['id']}\n")

if __name__ == "__main__":
    debug_combinations()

