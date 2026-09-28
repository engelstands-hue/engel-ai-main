from __future__ import annotations

from pathlib import Path


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()
MODEL_DIR = ROOT / "models" / "qwen2.5-0.5b-instruct"
MODEL_FILENAME = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
MODEL_PATH = MODEL_DIR / MODEL_FILENAME
MODEL_CARD_NOTE_PATH = MODEL_DIR / "MODEL_CARD_NOTE.md"
EXPECTED_FILENAME_NOTE_PATH = MODEL_DIR / "EXPECTED_MODEL_FILE.txt"


MODEL_CARD_NOTE = """# Qwen2.5-0.5B-Instruct GGUF Local Note

Status: MANUAL_INSTALL_ONLY / NOT_ENABLED

Expected model candidate:
- Qwen2.5-0.5B-Instruct GGUF
- Preferred quantization: Q4_K_M
- Alternate small quantization: Q4_0
- License: Apache-2.0

Expected local filename:
`qwen2.5-0.5b-instruct-q4_k_m.gguf`

Safety:
- This folder note does not enable the model.
- Engel does not auto-download this model.
- Engel does not install packages from this helper.
- Engel does not call a provider, API, cloud service, or network from this helper.
- Engel does not run inference from this helper.
- Model output must remain untrusted companion text until Guardian-routed.

Manual install:
1. Download the GGUF model manually from a trusted model publisher page.
2. Prefer Q4_K_M for the first local seed file, or Q4_0 if needed.
3. Place the file at the expected local path.
4. Add a verified SHA256 line to SHA256SUMS.txt when a trusted hash is available.
5. Run `python .\\tools\\verify_offline_seed_llm_contract.py`.

Future runtime requires a separate approved task.
"""


def main() -> int:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_CARD_NOTE_PATH.write_text(MODEL_CARD_NOTE, encoding="utf-8")
    EXPECTED_FILENAME_NOTE_PATH.write_text(
        "\n".join(
            [
                "Expected local seed LLM file:",
                str(MODEL_PATH),
                "",
                "This helper created folders and notes only.",
                "It did not download anything, install packages, modify runtime config, or enable inference.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print("Offline seed LLM folder scaffold prepared.")
    print("Model folder: " + str(MODEL_DIR))
    print("Expected model file: " + str(MODEL_PATH))
    print("MODEL_CARD_NOTE.md written: " + str(MODEL_CARD_NOTE_PATH))
    print("EXPECTED_MODEL_FILE.txt written: " + str(EXPECTED_FILENAME_NOTE_PATH))
    print()
    print("Manual step only: place the GGUF file at the expected path if you choose to install it.")
    print("No download, package install, runtime config write, inference, provider call, or network call was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
