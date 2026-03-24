import click
from jk_core.prompt_engine import assemble_prompt, get_required_vars

def run_interactive_test():
    project = "teaching"
    print(f"🚀 Testing Auto-Question for Project: [bold]{project}[/bold]\n")

    # 1. สมมติว่าได้ตัวแปรมาแค่บางส่วน (ขาด subject_name และ weeks)
    provided_vars = {
        "learning_objective": "Mastering Python",
        "student_group": "Undergraduates"
    }

    # 2. เช็คว่าต้องใช้ตัวแปรอะไรบ้าง
    required = get_required_vars(project)
    
    # 3. Auto-Question: ถ้าตัวไหนไม่มีใน provided_vars ให้ถาม User ทันที
    final_vars = provided_vars.copy()
    for var in required:
        if var not in final_vars or not final_vars[var]:
            # ใช้ click.prompt เพื่อหยุดรอรับค่าจาก Keyboard
            final_vars[var] = click.prompt(f"👉 Please enter [ {var} ]")

    # 4. ประกอบร่างหลังจากได้ค่าครบแล้ว
    try:
        prompt = assemble_prompt(project, variables=final_vars)
        print("\n✨ [Final Prompt Assembled] ✨")
        print(prompt)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_interactive_test()

