import click
from jk_ai_chat.commands.init import init_command

@click.group(invoke_without_command=True)
@click.pass_context
def cli_group(ctx):
    """JK-AI CLI Suite"""
    if ctx.invoked_subcommand is None:
        from jk_ai_chat.commands.chat import chat_command
        chat_command()

@cli_group.command(name="init")
def init_sub():
    init_command()

