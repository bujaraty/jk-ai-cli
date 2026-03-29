import sys
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from jk_core.prompt_engine import assemble_prompt, get_required_vars
from jk_core.ai_client import GeminiClient
from jk_core.orchestrator import Orchestrator
from jk_core.session_manager import SessionManager
from jk_core.search_engine import SearchEngine

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
        self.search_engine = SearchEngine(client)
        self._session_map = {}
        self._edit_map = {} # CHANGE: Initialize the map here

    def handle(self, text: str) -> bool:
        """
        Returns:
            - True: If a standard command was handled.
            - dict: If a Replay is triggered (contains future prompts).
            - False: If it's a regular message.
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
            "/edit": self.cmd_edit,
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
            "/search": self.cmd_search,
            "/stats": self.cmd_stats,
            "/switch": self.cmd_switch_tier,
            "/temp": self.cmd_set_temp,
            "/undo": self.cmd_undo,
        }

        func = commands.get(cmd)
        if func:
            return func(args)
        else:
            console.print(f"[bold red]Unknown command:[/bold red] {cmd}")
        return True

    def cmd_branch(self, args):
        new_id = self.session.branch()
        console.print(f"[bold magenta]🌿 Branched to new session: {new_id}[/bold magenta]")
        return True

    def cmd_copy(self, args):
        """Copies the most recent AI response to the system clipboard."""
        return True

    def cmd_edit(self, args):
        """Allows editing a past prompt with sequential numbering."""
        # 1. Map Display Number -> Real Index
        # This ensures users type '1', '2', '3' regardless of AI turns
        display_to_real = {}
        counter = 1

        if not args:
            table = Table(title="📜 History Timeline (Exchanges)", show_lines=True)
            # CHANGE: Explicitly add column names
            table.add_column("No.", justify="center", style="dim")
            table.add_column("Role", style="bold magenta")
            table.add_column("Content Preview", style="cyan")

            for real_idx, turn in enumerate(self.session.history):
                if turn['role'] == "user":
                    # CHANGE: Ensure we extract the string from the list ['text']
                    parts = turn.get('parts', [""])
                    raw_content = parts[0] if isinstance(parts, list) else parts

                    # Now we can safely call .replace() on the string
                    content = raw_content.replace("\n", " ")

                    if len(content) > 50:
                        content = content[:47] + "..."

                    display_to_real[str(counter)] = real_idx
                    table.add_row(str(counter), "YOU", content)
                    counter += 1

            # Store the map in the router instance so the next call can use it
            self._edit_map = display_to_real

            console.print(table)
            console.print("[dim]Usage: /edit [No.] to travel back to that point.[/dim]")
            return True

        # 2. Pick the index using the map
        display_idx = args[0]
        if hasattr(self, '_edit_map') and display_idx in self._edit_map:
            real_idx = self._edit_map[display_idx]
        else:
            # Fallback to raw index if not in map (or if user knows what they're doing)
            try:
                real_idx = int(display_idx)
            except ValueError:
                console.print("[red]Invalid selection.[/red]")
                return True

        # 3. Capture future prompts before truncating
        # We look for all 'user' turns that happen AFTER the real_idx
        idx = int(real_idx) # Ensure it's an int
        future_prompts = [m for m in self.session.history[idx+1:] if m['role'] == "user"]

        # CHANGE: Extract the string from the list ['text']
        parts = self.session.history[idx]['parts']
        original_text = parts[0] if isinstance(parts, list) else parts

        # 4. Open system editor
        new_text = click.edit(original_text)
        if not new_text or new_text.strip() == original_text.strip():
            console.print("[yellow]No changes saved.[/yellow]")
            return True

        # 5. Strategy Selection
        console.print("\n[bold magenta]🕰️ TIME TRAVEL INITIALIZED[/bold magenta]")
        choice = click.prompt(
            "Strategy", type=click.Choice(['t', 'r', 'b']), default='t',
            prompt_suffix="\n [t] Truncate\n [r] Replay\n [b] Branch & Truncate\n Choice: "
        )

        if choice == 'b':
            self.session.branch()

        # Perform the actual cut/edit in SessionManager
        self.session.time_travel(real_idx, new_text.strip())

        if choice in ['t', 'b']:
            return {"replay": True, "prompts": []}

        if choice == 'r':
            return {"replay": True, "prompts": future_prompts}


        console.print("✅ History updated.")
        return True

    def cmd_exit(self, args):
        """Terminates the application gracefully."""
        # Optional: Add logic to save current session before closing
        console.print("\n[bold yellow]👋 System offline. Goodbye![/bold yellow]")
        sys.exit(0)

    def cmd_model_info(self, args):
        """Shows detailed metadata of the currently active model."""
        return True

    def cmd_name(self, args):
        """/name [Session Name]: Sets the display name for current session."""
        if not args:
            console.print("[red]Usage: /name My Awesome Chat[/red]")
            return True

        new_name = " ".join(args)
        self.session.set_display_name(new_name)
        console.print(f"🏷️  Session renamed to: [bold yellow]{new_name}[/bold yellow]")
        return True

    def cmd_new_chat(self, args):
        """
        State Management:
        Saves the current session to a file and starts a fresh one with a new ID.
        """
        console.print("[bold blue]Starting a new chat session...[/bold blue]")
        return True

    def cmd_paste(self, args):
        """Simulates a multi-line paste or injects a file into the prompt."""
        return True

    def cmd_reset(self, args):
        self.session.clear()
        console.print("[bold green]🧹 Session history cleared.[/bold green]")
        return True

    def cmd_resume(self, args):
        """
        Lists named sessions and loads the selected one.
        Usage: /resume [session_number_or_id]
        """
        recent = self.session.get_recent_sessions(limit=20)
        if not recent:
            console.print("[yellow]No saved sessions found. Use /name first.[/yellow]")
            return True

        # 1. If no ID provided, show the list
        if not args:
            table = Table(title="🕒 Recently Active Sessions (Top 20)", show_lines=True)
            table.add_column("No.", justify="center", style="dim")
            table.add_column("Session ID", style="cyan")
            table.add_column("Name", style="bold yellow")

            self._session_map = {}
            for i, (sess_id, info) in enumerate(recent, 1):
                self._session_map[str(i)] = sess_id
                table.add_row(str(i), sess_id, info['name'])

            console.print(table)
            console.print("[dim]Type '/resume [No.]' to load a session.[/dim]")
            return True

        # 2. Try to load by Number or ID
        target_id = args[0]
        if hasattr(self, '_session_map') and target_id in self._session_map:
            target_id = self._session_map[target_id]

        if self.session.load(target_id):
            console.print(f"✅ [bold green]Resumed session:[/bold green] {self.session.display_name}")
            last_turns = self.session.get_last_turns(n=5)
            if last_turns:
                console.print("\n[bold dim]📜 Recent context (Last 5 exchanges):[/bold dim]")
                for turn in last_turns:
                    role_name = "You" if turn['role'] == "user" else "AI"
                    role_color = "cyan" if turn['role'] == "user" else "green"
                    content_raw = turn['parts'][0].strip().replace("\n", " ")

                    if len(content_raw) > 80:
                        content_raw = content_raw[:77] + "..."

                    line = Text.assemble(
                        (f" {role_name:3}: ", f"bold {role_color}"),
                        (content_raw, "default")
                    )
                    console.print(line)
                console.print("")

            console.print(f"[dim]Total History: {len(self.session.history)} messages loaded.[/dim]")
        else:
            console.print(f"[bold red]Error:[/bold red] Session ID '{target_id}' not found.")
        return True

    def cmd_retry(self, args):
        """Deletes the last AI response and resends the last user prompt."""
        return True

    def cmd_save(self, args):
        """Exports the current conversation to a Markdown file."""
        return True

    def cmd_search(self, args):
        """/search [query]: Semantic search with pinpoint accuracy."""
        query = " ".join(args)
        if not self.search_engine.index_file.exists():
            console.print("[yellow]Search index not found. Building it now...[/yellow]")
            with console.status("Embedding all sessions..."):
                self.search_engine.rebuild_index()
        results = self.search_engine.search(query)
        table = Table(title=f"🔍 Semantic Matches for: '{query}'", show_lines=True)
        table.add_column("Score", justify="right", style="green")
        table.add_column("Session / File", style="cyan")
        table.add_column("Matched Turn (The 'Why')", style="yellow")
        for r in results:
            table.add_row(
                f"{r['score']:.2f}",
                f"{r['session_name']}\n[dim]{r['filename']}[/dim]",
                f"Turn {r['turn_no']}: {r['matched_text'][:100]}..."
            )
        console.print(table)
        return True

    def cmd_set_temp(self, args):
        """Adjusts the generation temperature (0.0 to 2.0)."""
        return True

    def cmd_stats(self, args):
        """Displays accumulated usage statistics for all keys/models."""
        # Implementation: Call your existing check_usage logic
        return True

    def cmd_switch_proj(self, args):
        """Swaps the Project Profile (Modular Prompts) for the next request."""
        return True

    def cmd_switch_tier(self, args):
        """Changes the Orchestrator tier (lite/normal/high) mid-session."""
        if args:
            self.orch.tier = args[0]
            console.print(f"✅ Tier switched to: [bold]{args[0]}[/bold]")
        return True

    def cmd_toggle_latest(self, args):
        """Toggles the 'prefer_latest' flag in the Orchestrator."""
        self.orch.prefer_latest = not self.orch.prefer_latest
        console.print(f"✨ Prefer Latest: [bold]{self.orch.prefer_latest}[/bold]")
        return True

    def cmd_undo(self, args):
        """Removes the last exchange (User + AI) from history."""
        self.session.undo()
        console.print("↩️  Last exchange removed from session.")
        return True

def chat_command(proj, user_input, tier="normal", latest=False):
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

    def generate_with_fallback(current_history):
        # CHANGE: Iterate through all ranked candidates if the top one is exhausted
        for model_entry in rankings:
            target_mid = model_entry['id']
            try:
                # We show which model is currently being attempted
                with console.status(f"[bold yellow]Thinking ({target_mid.split('/')[-1]})..."):
                    return client.generate_with_history(
                        history=current_history,
                        system_instruction=session.system_instruction,
                        model_name=target_mid
                    ), target_mid
            except PermissionError as e:
                if "MODEL_EXHAUSTED" in str(e):
                    console.print(f"[dim yellow]⚠️  {target_mid} exhausted on all keys. Falling back...[/dim yellow]")
                    continue
                raise e
        raise RuntimeError("All available models and keys are truly exhausted.")

    while True:
        if not user_input:
            prompt_label = f"[bold cyan]You ({client.key_id} | {session.display_name}) > [/bold cyan]"
            user_input = console.input(prompt_label)

        cmd_result = router.handle(user_input)
        if isinstance(cmd_result, dict) and cmd_result.get("replay"):
            future_prompts = cmd_result["prompts"]
            # STEP A: Generate the FIRST response for the newly edited prompt
            try:
                # CHANGE: Applied fallback logic to Replay Step A
                (resp, meta), used_mid = generate_with_fallback(session.history)
                session.add_message("model", resp, model_id=used_mid)
                console.print(f"[bold green]AI ({client.key_id} | {used_mid.split('/')[-1]}) > [/bold green]{resp}\n")
            except Exception as e:
                console.print(f"[bold red]Replay Error:[/bold red] {e}")
                user_input = None; continue

            console.print(Panel("[bold yellow]🔄 REPLAY MODE ACTIVATED[/bold yellow]\nRegenerating conversation from the edited point...", border_style="yellow"))

            # STEP B: Replay the REST of the conversation
            for i, p_turn in enumerate(future_prompts, 1):
                p_text = p_turn['parts'][0] if isinstance(p_turn['parts'], list) else p_turn['parts']
                p_model = p_turn.get("metadata", {}).get("model", model_id)

                console.print(f"[bold cyan]You (Replay {i}/{len(future_prompts)}) > [/bold cyan]{p_text}")
                session.add_message("user", p_text)

                try:
                    # CHANGE: Applied fallback logic to Replay Step B
                    (resp, meta), used_mid = generate_with_fallback(session.history)
                    session.add_message("model", resp, model_id=used_mid)
                    console.print(f"[bold green]AI ({client.key_id} | {used_mid.split('/')[-1]}) > [/bold green]{resp}\n")
                except Exception as e:
                    console.print(f"[bold red]Replay Error:[/bold red] {e}")
                    break

            console.print("[bold green]✨ Replay complete. Timeline is now consistent.[/bold green]\n")
            user_input = None
            continue
        elif cmd_result:
            user_input = None
            continue

        session.add_message("user", user_input)
        with console.status("[bold yellow]Thinking..."):
            try:
                # CHANGE: Applied fallback logic to Normal Prompt execution
                (response_text, meta), used_mid = generate_with_fallback(session.history)
                session.add_message("model", response_text, model_id=model_id)
                console.print(f"\n[bold green]AI ({client.key_id}) > [/bold green]{response_text}\n")
                # --- NEW: Milestone 2 - Auto-Naming Logic ---
                if session.is_eligible_for_autoname():
                    # Use a fast 'lite' model for background tasks to save quota/time
                    with console.status("[dim]Generating session name...[/dim]"):
                        # We create a specific naming prompt based on the first pair
                        naming_prompt = (
                            "Summarize the user's intent in this conversation in "
                            "exactly 3 to 5 words. No punctuation. "
                            f"\nUser: {session.history[0]['parts'][0]}"
                            f"\nAI: {response_text[:100]}"
                        )

                        # Generate the title
                        title, _ = client.generate_with_meta(
                            prompt=naming_prompt,
                            system_instruction="You are a professional filing clerk. Give only the title.",
                            model_name=model_id # Or a lite model if you prefer
                        )

                        clean_title = title.strip().replace('"', '')
                        session.set_display_name(clean_title)
                        console.print(f"[dim]🏷️  Session auto-named: [bold]{clean_title}[/bold][/dim]")
                # --------------------------------------------
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
                session.history.pop()
                user_input = None

