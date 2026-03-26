import click
from jk_ai_chat.commands.chat import chat_command
from jk_ai_chat.commands.init import init_command

@click.command()
@click.option('--proj', default='cli-dev', help='Project profile to use')
@click.argument('user_input', required=False)
def main_chat(proj, user_input):
    """Main Entrypoint: Open AI Chat directly"""
    chat_command(proj, user_input)

def init_only():
    """Main Entrypoint: Initialize system"""
    init_command()

