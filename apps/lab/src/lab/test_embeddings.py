# apps/lab/src/lab/test_embeddings.py
from jk_core.ai_client import GeminiClient
from rich.console import Console

console = Console()

def test_vector():
    client = GeminiClient(tier="free")
    text = "I love learning about AI architecture."

    # CHANGE: Logic to try multiple embedding models
    candidates = ["models/text-embedding-004", "models/embedding-001",
                  "models/gemini-embedding-001"]

    for model in candidates:
        console.print(f"🧮 Trying: [cyan]{model}[/cyan]")
        try:
            vector = client.embed_content(text, model_name=model)
            console.print(f"✅ Success with {model}! Length: [bold green]{len(vector)}[/bold green]")
            console.print(f"🔢 Preview: [yellow]{vector[:3]}[/yellow]...")
            return # Exit if successful
        except LookupError:
            console.print(f"[yellow]⚠️  {model} not found, trying next...[/yellow]")
        except Exception as e:
            console.print(f"[red]❌ Unexpected Error:[/red] {e}")

if __name__ == "__main__":
    test_vector()

