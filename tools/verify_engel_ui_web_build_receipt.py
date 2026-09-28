#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import run_engel_flutter_main_ui_prompt_training as training


def main() -> int:
    original_dir = training.CHAT_RECEIPT_DIR
    prompt = "Build me a self-contained web page called drawing_review_board."
    record = {
        "ok": True,
        "build_lane_used": True,
        "provider_api_enabled": True,
        "action": {
            "kind": "app_build",
            "language": "web",
            "result": {
                "ok": True,
                "created": True,
                "kind": "project",
                "entry": "index.html",
                "files": ["README.md", "index.html"],
                "path": "/opt/engel/workspaces/drawing_review_board",
                "run_hint": "open index.html in a browser",
            },
            "run": None,
        },
    }
    with tempfile.TemporaryDirectory() as temp_dir:
        training.CHAT_RECEIPT_DIR = Path(temp_dir)
        try:
            receipt_path = training._write_ct_memory_chat_receipt(
                {"ok": True, "path": "/tmp/chat.jsonl", "record": record},
                prompt,
                "web-build-verifier",
                1,
            )
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        finally:
            training.CHAT_RECEIPT_DIR = original_dir
    assert receipt["build_artifact_verified"] is True
    assert receipt["workspace_files"] == ["README.md", "index.html"]
    assert receipt["workspace_run_ran"] is None
    print("VERIFY_ENGEL_UI_WEB_BUILD_RECEIPT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
