import base64
import zipfile
from pathlib import Path

# --- Paths ---
ROOT = Path(__file__).resolve().parent
BASE64_FILE = ROOT / "codex_usage_coffee.b64"
ZIP_FILE = ROOT / "codex_usage_coffee.zip"
DEST_FOLDER = ROOT  # extracted files go here

# --- Decode Base64 to ZIP ---
b64_data = BASE64_FILE.read_text(encoding="utf-8").strip()
zip_bytes = base64.b64decode(b64_data)
ZIP_FILE.write_bytes(zip_bytes)

# --- Extract ZIP ---
with zipfile.ZipFile(ZIP_FILE, "r") as zip_ref:
    zip_ref.extractall(DEST_FOLDER)

# --- Clean up ZIP ---
ZIP_FILE.unlink()

print("[✔] Codex Usage Coffee project successfully extracted!")
