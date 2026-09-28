"""
Loader script for Engel AI De Bruijn memory with auto-registration
- Reads JSON memory file
- Loads images
- Registers memory into Engel AI trusted memory system automatically
"""

import json
from pathlib import Path

# Paths to memory files
# Prefer colocated files in D:\b.WorkSpace
ROOT_DIR = Path(r"D:\b.WorkSpace")
JSON_MEMORY = ROOT_DIR / "engel_memory_de_bruijn_quantum_expanded.json"
IMAGES_DIR = ROOT_DIR / "images"

# Load JSON memory
try:
    with JSON_MEMORY.open('r', encoding='utf-8') as f:
        engel_memory = json.load(f)
except FileNotFoundError:
    raise FileNotFoundError(f"Memory JSON file not found: {JSON_MEMORY}")
except json.JSONDecodeError as e:
    raise ValueError(f"Invalid JSON content: {e}")

# Verify images exist
images = engel_memory.get('images', [])
for img_path in images:
    img_file = Path(img_path)
    if not img_file.exists():
        print(f"Warning: Image file not found: {img_file}")

# Auto-register memory into Engel AI system
# Replace this function with Engel's API call or memory registration method
try:
    from engel_ai_system import register_trusted_memory
    register_trusted_memory(engel_memory)
    print("✅ Engel AI memory auto-registered successfully.")
except ImportError:
    # Fallback if API not available
    TRUSTED_MEMORY = engel_memory
    print("⚠ Engel AI memory loaded into variable TRUSTED_MEMORY (auto-registration not available).")

print(f"- JSON memory: {JSON_MEMORY}")
print(f"- Images loaded: {[str(Path(img)) for img in images]}")
