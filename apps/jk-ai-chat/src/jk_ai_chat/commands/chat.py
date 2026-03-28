import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from jk_core.prompt_engine import assemble_prompt, get_required_vars
from jk_core.ai_client import GeminiClient
from jk_core.orchestrator import Orchestrator
from jk_core.session_manager import SessionManager

console = Console()

class ChatRouter:
    """
    Routes Slash Commands to specific logic.
    Each method handles a specific user intent.
    The cmd_<name> is ordered by name because it's easier to search that way.
    """
    def __init__(self, client, orchestrator, session_manager):
        self.client = client
        self.orch = orchestrator
        self.session = session_manager

    def handle(self, text: str) -> bool:
        """
        Routes commands. Returns True if handled, False if it's a regular message.
        """
        clean_text = text.strip().lower()

        exit_keywords = ["exit", "quit", "bye", "/exit", "/bye", "/quit"]
        if clean_text in exit_keywords:
            self.cmd_exit(None)

        if not text.startswith("/"):
            return False

        parts = text.split()
        cmd = parts[0].lower()
        args = parts[1:]

        # Dispatch Table
        commands = {
            "/branch": self.cmd_branch,
            "/copy": self.cmd_copy,
            "/latest": self.cmd_toggle_latest,
            "/model": self.cmd_model_info,
            "/name": self.cmd_name,
            "/new": self.cmd_new_chat,
            "/paste": self.cmd_paste,
            "/proj": self.cmd_switch_proj,
            "/reset": self.cmd_reset,
            "/resume": self.cmd_resume,
            "/retry": self.cmd_retry,
            "/save": self.cmd_save,
            "/stats": self.cmd_stats,
            "/switch": self.cmd_switch_tier,
            "/temp": self.cmd_set_temp,
            "/undo": self.cmd_undo,
        }

        func = commands.get(cmd)
        if func:
            func(args)
        else:
            console.print(f"[bold red]Unknown command:[/bold red] {cmd}")

        return True

    def cmd_branch(self, args):
        new_id = self.session.branch()
        console.print(f"[bold magenta]🌿 Branched to new session: {new_id}[/bold magenta]")

    def cmd_copy(self, args):
        """Copies the most recent AI response to the system clipboard."""
        pass

    def cmd_exit(self, args):
        """Terminates the application gracefully."""
        # Optional: Add logic to save current session before closing
        console.print("\n[bold yellow]👋 System offline. Goodbye![/bold yellow]")
        sys.exit(0)

    def cmd_model_info(self, args):
        """Shows detailed metadata of the currently active model."""
        pass

    def cmd_name(self, args):
        """/name [Session Name]: Sets the display name for current session."""
        if not args:
            console.print("[red]Usage: /name My Awesome Chat[/red]")
            return

        new_name = " ".join(args)
        self.session.set_display_name(new_name)
        console.print(f"🏷️  Session renamed to: [bold yellow]{new_name}[/bold yellow]")

    def cmd_new_chat(self, args):
        """
        State Management:
        Saves the current session to a file and starts a fresh one with a new ID.
        """
        console.print("[bold blue]Starting a new chat session...[/bold blue]")

    def cmd_paste(self, args):
        """Simulates a multi-line paste or injects a file into the prompt."""
        pass

    def cmd_reset(self, args):
        self.session.clear()
        console.print("[bold green]🧹 Session history cleared.[/bold green]")

    def cmd_resume(self, args):
        """
        Lists named sessions and loads the selected one.
        Usage: /resume [session_number_or_id]
        """
        meta = self.session._load_metadata()
        if not meta:
            console.print("[yellow]No saved sessions found. Use /name first.[/yellow]")
            return

        # 1. If no ID provided, show the list
        if not args:
            table = Table(title="Saved Sessions", show_lines=True)
            table.add_column("No.", justify="center", style="dim")
            table.add_column("Session ID", style="cyan")
            table.add_column("Name", style="bold yellow")

            # Map index to ID for easy selection
            self._session_map = {}
            for i, (sess_id, info) in enumerate(meta.items(), 1):
                self._session_map[str(i)] = sess_id
                table.add_row(str(i), sess_id, info['name'])

            console.print(table)
            console.print("[dim]Type '/resume [No.]' to load a session.[/dim]")
            return

        # 2. Try to load by Number or ID
        target_id = args[0]
        # Check if user typed a number from the map
        if hasattr(self, '_session_map') and target_id in self._session_map:
            target_id = self._session_map[target_id]

        if self.session.load(target_id):
            console.print(f"✅ [bold green]Resumed session:[/bold green] {self.session.display_name}")
            console.print(f"[dim]History: {len(self.session.history)} messages loaded.[/dim]")
        else:
            console.print(f"[bold red]Error:[/bold red] Session ID '{target_id}' not found.")

    def cmd_retry(self, args):
        """Deletes the last AI response and resends the last user prompt."""
        pass

    def cmd_save(self, args):
        """Exports the current conversation to a Markdown file."""
        pass

    def cmd_set_temp(self, args):
        """Adjusts the generation temperature (0.0 to 2.0)."""
        pass

    def cmd_stats(self, args):
        """Displays accumulated usage statistics for all keys/models."""
        # Implementation: Call your existing check_usage logic
        pass

    def cmd_switch_proj(self, args):
        """Swaps the Project Profile (Modular Prompts) for the next request."""
        pass

    def cmd_switch_tier(self, args):
        """Changes the Orchestrator tier (lite/normal/high) mid-session."""
        if args:
            self.orch.tier = args[0]
            console.print(f"✅ Tier switched to: [bold]{args[0]}[/bold]")

    def cmd_toggle_latest(self, args):
        """Toggles the 'prefer_latest' flag in the Orchestrator."""
        self.orch.prefer_latest = not self.orch.prefer_latest
        console.print(f"✨ Prefer Latest: [bold]{self.orch.prefer_latest}[/bold]")

    def cmd_undo(self, args):
        """Removes the last exchange (User + AI) from history."""
        self.session.undo()
        console.print("↩️  Last exchange removed from session.")


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

    session = SessionManager(system_instruction=system_instruction)
    router = ChatRouter(client, orch, session)
    while True:
        if not user_input:
            user_input = console.input(f"[bold cyan]You ({client.key_id}) > [/bold cyan]")
        # CHECK FOR COMMANDS
        if router.handle(user_input):
            user_input = None # Clear input and continue loop
            continue

        session.add_message("user", user_input)
        with console.status("[bold yellow]Thinking..."):
            try:
                response_text, meta = client.generate_with_history(
                    history=session.history, # <--- The full list from JSONL
                    system_instruction=session.system_instruction,
                    model_name=model_id
                )
#                response_text, meta = client.generate_with_meta(
#                    prompt=user_input,
#                    system_instruction=system_instruction,
#                    model_name=model_id
#                )
                console.print(f"\n[bold green]AI ({client.key_id}) > [/bold green]{response_text}\n")
                session.add_message("model", response_text)
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

