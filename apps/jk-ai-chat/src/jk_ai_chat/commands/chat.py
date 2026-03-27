from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
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
    client = GeminiClient(tier="free")
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
#
#    # 4. INTERACTION
#    if not user_input:
#        key_label = f"({client.key_id})" if client.key_id else ""
#        user_input = console.input(f"[bold cyan]You {key_label} > [/bold cyan]")


    while True:
        if not user_input:
            user_input = console.input(f"[bold cyan]You ({client.key_id}) > [/bold cyan]")

        if user_input.lower() in ["exit", "quit", "/bye"]:
            break

        with console.status("[bold yellow]Thinking..."):
            try:
                response_text, meta = client.generate_with_meta(
                    prompt=user_input,
                    system_instruction=system_instruction,
                    model_name=model_id
                )

                console.print(f"\n[bold green]AI ({client.key_id}) > [/bold green]{response_text}\n")

                # --- NEW: Last Request vs. Accumulated Statistics ---
                # 1. Fetch the updated state from disk
                state = client.km._load_state()
                acc = state.get("usage", {}).get(client.key_id, {}).get("models", {}).get(model_id, {})

                # 2. Build Last Request Panel
                last_req_info = (
                    f"In:  [green]{meta.prompt_token_count}[/green]\n"
                    f"Out: [blue]{meta.candidates_token_count}[/blue]\n"
                    f"Tot: [yellow]{meta.total_token_count}[/yellow]"
                )
                p1 = Panel(last_req_info, title="[bold]Last Request[/bold]", border_style="dim", expand=False)

                # 3. Build Accumulated Panel (Global)
                acc_info = (
                    f"Reqs: [magenta]{acc.get('request_count', 0)}[/magenta]\n"
                    f"In:   [green]{acc.get('total_input_tokens', 0)}[/green]\n"
                    f"Out:  [blue]{acc.get('total_output_tokens', 0)}[/blue]"
                )
                p2 = Panel(acc_info, title="[bold]Accumulated (Global)[/bold]", border_style="dim", expand=False)

                # 4. Display side-by-side
                console.print(Columns([p1, p2]))
                # ----------------------------------------------------

                user_input = None # Clear for next loop iteration

            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {e}")
                break

