#!/bin/bash

echo "🏗️  Creating Full JK-AI Workspace Structure..."

# 1. สร้างโฟลเดอร์หลักทั้งหมด
mkdir -p apps/jk-ai-chat/src/jk_ai_chat/commands
mkdir -p apps/lab/src/lab
mkdir -p libs/jk-core/src/jk_core

# 2. สร้างไฟล์ __init__.py (เพื่อให้ Python มองเป็น Package)
touch apps/jk-ai-chat/src/jk_ai_chat/__init__.py
touch apps/jk-ai-chat/src/jk_ai_chat/commands/__init__.py
touch apps/lab/src/lab/__init__.py
touch libs/jk-core/src/jk_core/__init__.py

# 3. สร้างไฟล์สำหรับระบบ Entrypoints และ CLI (apps/jk-ai-chat)
touch apps/jk-ai-chat/src/jk_ai_chat/entrypoints.py
touch apps/jk-ai-chat/src/jk_ai_chat/cli.py
touch apps/jk-ai-chat/src/jk_ai_chat/commands/chat.py
touch apps/jk-ai-chat/src/jk_ai_chat/commands/init.py
touch apps/jk-ai-chat/src/jk_ai_chat/commands/editor.py

# 4. สร้างไฟล์สำหรับ Shared Logic (libs/jk-core)
touch libs/jk-core/src/jk_core/config.py
touch libs/jk-core/src/jk_core/constants.py
touch libs/jk-core/src/jk_core/ai_client.py

# 5. สร้างไฟล์เริ่มต้นสำหรับ Lab (apps/lab)
touch apps/lab/src/lab/gemini_api.py
touch apps/lab/src/lab/openai_api.py

# 6. สร้างไฟล์ระบบที่ Root
touch .env
touch README.md
touch .gitignore

echo "✅ Full structure created successfully!"
echo "📂 Use 'py_dev_tree' to verify the result."

