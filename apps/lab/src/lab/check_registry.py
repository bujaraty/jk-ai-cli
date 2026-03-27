from jk_core.model_registry import ModelRegistry

def test_registry():
    registry = ModelRegistry()
    print("🔄 Updating Model Registry cache...")
    
    models = registry.refresh_cache()
    print(f"✅ Discovered {len(models)} models in total.")

    # Example: Check for Image Generation models (Imagen)
    image_models = registry.get_models_by_action("createCachedContent")
    print(f"🎨 Found {len(image_models)} models supporting image generation:")
    for m in image_models:
        print(f" - {m['display_name']} ({m['id']})")

if __name__ == "__main__":
    test_registry()

