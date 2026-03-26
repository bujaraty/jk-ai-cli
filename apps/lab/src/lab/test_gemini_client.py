import sys
from jk_core.ai_client import GeminiClient
from jk_core.constants import SHARED_CONFIG_PATH
from pathlib import Path

def test_client():
    print("🚀 Testing GeminiClient with 'google-genai' SDK...")
    
    try:
        # 1. Initialize client using the shared library logic
        # It will automatically pick a key from your keys.yaml
        client = GeminiClient(tier="free")
        
        # 2. Test prompt
        prompt = "Hello, can you hear me? Respond with 'System Online' if you are working."
        system_instruction = "You are a helpful technical assistant."
        
        print(f"📡 Sending request to Gemini...")
        
        # 3. Generate response (this handles key rotation internally)
        response = client.generate(
            prompt=prompt, 
            system_instruction=system_instruction
        )
        
        print("\n--- AI Response ---")
        print(response)
        print("-------------------\n")
        print("✅ Success: GeminiClient is operational.")
        
    except RuntimeError as e:
        print(f"❌ Error: {e}")
        print(f"💡 Tip: Ensure your 'keys.yaml' in {SHARED_CONFIG_PATH} has a valid Gemini API Key.")
    except Exception as e:
        print(f"💥 Unexpected Error: {e}")

if __name__ == "__main__":
    test_client()

