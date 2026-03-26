from rich.console import Console
from jk_core.prompt_engine import assemble_prompt, get_required_vars
from jk_core.ai_client import GeminiClient

console = Console()

def chat_command(proj, user_input):
    """Start a chat session or send a single prompt."""

    # 1. Initialize AI Client
    client = GeminiClient(tier="free")

    # 2. Get required variables for the project (Auto-Question)
    required = get_required_vars(proj)
    variables = {}
    for var in required:
        variables[var] = click.prompt(f"Enter {var.replace('_', ' ').title()}")

    # 3. Assemble the System Prompt
    system_instruction = assemble_prompt(proj, variables=variables)

    # 4. Handle Input (Single shot or Interactive)
    if not user_input:
        user_input = console.input("[bold cyan]You > [/bold cyan]")

    with console.status(f"[bold yellow]Gemini is thinking ({proj})...[/bold yellow]"):
        try:
            response = client.generate(
                prompt=user_input,
                system_instruction=system_instruction
            )
            console.print(f"\n[bold green]AI > [/bold green]{response}\n")
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")


