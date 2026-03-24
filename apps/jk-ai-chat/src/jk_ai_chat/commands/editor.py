import os

def edit_command():
    """เปิดไฟล์หลักของโปรเจกต์ขึ้นมาแก้ไขพร้อมกันใน Vim"""
    # ลิสต์ไฟล์ที่อยากเปิด (แก้ Path ให้ตรงกับโครงสร้างจริง)
    files_to_edit = [
      #  "apps/jk-ai-chat/src/jk_ai_chat/cli.py",
        "apps/lab/src/lab/test_auto_question.py",
#        "apps/lab/src/lab/test_prompts.py",
        "libs/jk-core/src/jk_core/prompt_engine.py",
        "apps/lab/pyproject.toml",
        "apps/jk-ai-chat/src/jk_ai_chat/commands/editor.py",
        "apps/jk-ai-chat/src/jk_ai_chat/commands/chat.py",
        "tmp.py",
        "libs/jk-core/src/jk_core/constants.py",
        "apps/jk-ai-chat/src/jk_ai_chat/entrypoints.py",
        "apps/jk-ai-chat/pyproject.toml",
        "apps/lab/src/lab/gemini_api.py",
    ]
    
    # ตรวจสอบว่าไฟล์มีอยู่จริงไหม (กัน Error)
    existing_files = [f for f in files_to_edit if os.path.exists(f)]
    
    if not existing_files:
        print("❌ ไม่พบไฟล์ที่ระบุในรายการ")
        return

    # Option A: เปิดแบบแบ่งหน้าต่าง (Split) - ใช้คำสั่ง vim -o (Horizontal) หรือ -O (Vertical)
    # Option B: เปิดแบบแยก Tabs - ใช้คำสั่ง vim -p
    os.system(f"vim -o2 -O2 {' '.join(existing_files)}")
