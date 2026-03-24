from jk_core.prompt_engine import assemble_prompt, get_required_vars

def test_teaching_prompt():
    print("🧪 Testing: Prompt Assembly for 'teaching' project")
    
    # 1. จำลองข้อมูลที่ปกติจะรับจาก CLI
    variables = {
            #        "subject_name": "Modern AI Architecture",
        "learning_objective": "Understand modular prompt design",
        "weeks": 12,
        "student_group": "Graduate Computer Science"
    }

    # 2. เช็คตัวแปรที่ต้องการ
    required = get_required_vars("teaching")
    print(f"📋 Required vars: {required}")

    # 3. ประกอบร่าง
    try:
        full_prompt = assemble_prompt("teaching", variables=variables)
        print("\n--- RESULTING PROMPT ---")
        print(full_prompt)
        print("------------------------\n")
        print("✅ Test Passed!")
    except Exception as e:
        print(f"❌ Test Failed: {e}")

if __name__ == "__main__":
    test_teaching_prompt()

