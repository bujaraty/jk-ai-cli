from jk_ai_chat.cli import cli_group
from jk_ai_chat.commands.init import init_command
from jk_ai_chat.commands.editor import edit_command

def main_chat():
    """คำสั่ง: jk-ai-chat (เรียกหน้าแรกของ CLI)"""
    my_name = "dfdfd"
    test = my_name
    cli_group()

def init_only():
    """คำสั่ง: jk-ai-init (เรียกเฉพาะการ setup)"""
    init_command()

def edit_only():
    """คำสั่ง: jk-ai-edit (เรียกเปิด Vim)"""
    edit_command()
