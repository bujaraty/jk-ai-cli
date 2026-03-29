from jk_core.ai_client import GeminiClient
from jk_core.search_engine import SearchEngine
from rich.console import Console

console = Console()

def test_search():
    client = GeminiClient(tier="free")
    engine = SearchEngine(client)
    
    console.print("[blue]🔍 Rebuilding Search Index...[/blue]")
    count = engine.rebuild_index()
    console.print(f"✅ Indexed {count} sessions.")

    query = "Something about travel or Japan"
    console.print(f"\n🔎 Searching for: [italic]'{query}'[/italic]")
    results = engine.search(query)

    for r in results:
        console.print(f" ⭐ [cyan]{r['display_name']}[/cyan] (Sim: [yellow]{r['score']:.4f}[/yellow])")

if __name__ == "__main__":
    test_search()

