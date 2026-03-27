from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from jk_core.prompt_engine import assemble_prompt, get_required_vars
from jk_core.ai_client import GeminiClient
from jk_core.orchestrator import Orchestrator

console = Console()

def chat_command(proj, user_input, tier="normal", latest=False):
    """
    Main Chat Logic:
    1. Orchestrator picks the best model based on Tier and Version flags.
    2. Prompt Engine assembles the Modular Prompt.
    3. GeminiClient sends the request.
    """
    # 1. ORCHESTRATION: Pick the model automatically
    orch = Orchestrator(provider="google", tier=tier, prefer_latest=latest)
    rankings = orch.get_rankings(action="generateContent")
    if not rankings:
        console.print("[bold red]❌ Error:[/bold red] No healthy models found.")
        return
    best_model = rankings[0]
    model_id = best_model['id']

    reasons_str = " • " + "\n • ".join(best_model['reasons'])
    model_info = Text.assemble(
        (f"Model: ", "bold cyan"), (f"{model_id}\n", "yellow"),
        (f"Score: ", "bold cyan"), (f"{best_model['score']}\n", "green"),
        (f"Logic:\n", "bold cyan"), (reasons_str, "dim white")
    )
    console.print(Panel(model_info, title="[bold magenta]Selection Logic[/bold magenta]", expand=False))

    # 2. INITIALIZE CLIENT
    # We initialize it early so we can get the key name for the prompt
    client = GeminiClient(tier="free")
    # Trigger the first key fetch if not already done
    try:
        client._refresh_client()
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return

    # 3. PROMPT ASSEMBLY
    variables = {}
    required = get_required_vars(proj)
    for var in required:
        variables[var] = console.input(f"[bold yellow]Enter {var.replace('_', ' ').title()}: [/bold yellow]")
    system_instruction = assemble_prompt(proj, variables=variables)

    # 4. INTERACTION
    if not user_input:
        key_label = f"({client.key_id})" if client.key_id else ""
        user_input = console.input(f"[bold cyan]You {key_label} > [/bold cyan]")

    # 4. EXECUTION
    with console.status(f"[bold yellow]Thinking...[/bold yellow]"):
        try:
            # Note: We need to update GeminiClient.generate to accept a model name!
            response = client.generate(
                prompt=user_input,
                system_instruction=system_instruction,
                model_name=model_id # <--- Pass the chosen model
            )
            console.print(f"\n[bold green]AI > [/bold green]{response}\n")
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")

