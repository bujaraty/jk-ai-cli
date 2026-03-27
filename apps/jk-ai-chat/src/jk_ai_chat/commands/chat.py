from rich.console import Console
from jk_core.prompt_engine import assemble_prompt, get_required_vars
from jk_core.ai_client import GeminiClient
from jk_core.orchestrator import Orchestrator # <--- Import the Brain

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
    best_model = orch.pick_best_model(action="generateContent")

    if not best_model:
        console.print("[bold red]❌ Error:[/bold red] No healthy models found. Run 'jk-ai-init --probe'.")
        return

    model_id = best_model['id']
    console.print(f"[dim]🤖 Using Model: {model_id} (Score: {best_model['score']})[/dim]")

    # 2. PROMPT ASSEMBLY
    variables = {}
    required = get_required_vars(proj)
    for var in required:
        variables[var] = console.input(f"[bold yellow]Enter {var.replace('_', ' ').title()}: [/bold yellow]")

    system_instruction = assemble_prompt(proj, variables=variables)

    # 3. INTERACTION
    if not user_input:
        user_input = console.input("[bold cyan]You > [/bold cyan]")

    # 4. EXECUTION
    # We pass the model_id discovered by the Orchestrator to the Client
    client = GeminiClient(tier="free")

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

