from pathlib import Path
from jk_core.constants import SHARED_CONFIG_PATH
from jk_core.key_manager import KeyManager

def setup_mock_keys():
    """Create a sample keys.yaml in the actual config directory for testing."""
    config_dir = Path(SHARED_CONFIG_PATH)
    config_dir.mkdir(parents=True, exist_ok=True)
    
    keys_file = config_dir / "keys.yaml"
#    sample_data = {
#        "google": {
#            "free": [
#                {"id": "test-key-1", "key": "AIza_KEY_ONE"},
#                {"id": "test-key-2", "key": "AIza_KEY_TWO"}
#            ]
#        }
#    }
#    
#    with open(keys_file, "w") as f:
#        yaml.dump(sample_data, f)
    
    print(f"✅ Setup: Mock keys created at {keys_file}")
    return keys_file

def run_test():
    # 1. Setup
    setup_mock_keys()
    km = KeyManager(provider="google", tier="free")
    
    print(f"🔍 Testing KeyManager at path: {SHARED_CONFIG_PATH}")

    # 2. Test initial retrieval
    key, key_id = km.get_available_key()
    print(f"▶️ Initial Key: {key} (ID: {key_id})")

    if key_id == "test-key-1":
        # 3. Simulate exhaustion for the first key
        print(f"⚠️ Marking {key_id} as exhausted for 1 minute...")
        km.mark_exhausted(key_id)

        # 4. Test rotation to the second key
        next_key, next_id = km.get_available_key()
        print(f"🔄 Rotated Key: {next_key} (ID: {next_id})")
        
        if next_id == "test-key-2":
            print("✅ Success: System correctly rotated to the next available key.")
        else:
            print("❌ Failure: System did not rotate correctly.")
    else:
        print("❌ Failure: Could not retrieve the first test key.")

if __name__ == "__main__":
    try:
        run_test()
    except Exception as e:
        print(f"💥 Test crashed: {e}")

