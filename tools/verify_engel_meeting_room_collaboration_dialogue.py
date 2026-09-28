#!/usr/bin/env python3
"""Verify Meeting Room records visible multi-agent collaboration dialogue."""
from __future__ import annotations

import json
import py_compile
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    py_compile.compile(str(ROOT / "engel_agent_meeting_room.py"), doraise=True)

    import engel_agent_meeting_room as room

    prompt = (
        "Create a PDF about Engel prompt routing, include phone worker notes, "
        "and test the result."
    )
    staged = room.submit_order_from_engel_main_ui(prompt, source="collaboration verifier")
    require(staged.get("accepted"), f"order was not accepted: {staged}")

    completed = room.complete_order_from_engel_main_ui(
        str(staged["order_id"]),
        "Engel local bridge prepared the PDF plan after Meeting Room routing.",
        source="collaboration verifier",
    )
    require(completed.get("accepted"), f"order was not completed: {completed}")

    dialogue = completed.get("collaboration_dialogue")
    require(isinstance(dialogue, list) and len(dialogue) >= 3, "missing collaboration dialogue")
    names = {str(turn.get("name") or "") for turn in dialogue if isinstance(turn, dict)}
    require("Meeting Room Router" in names, "router did not speak in collaboration dialogue")
    require(any("Agent" in name for name in names), "no agent spoke in collaboration dialogue")
    require("Collaboration dialogue:" in str(completed.get("summary") or ""), "summary omitted dialogue")

    order_path = Path(str(completed.get("order_path") or ""))
    require(order_path.exists(), "order record missing")
    saved = json.loads(order_path.read_text(encoding="utf-8"))
    require(saved.get("collaboration_dialogue") == dialogue, "dialogue was not persisted")
    print("OK: Meeting Room collaboration dialogue verified")


if __name__ == "__main__":
    main()
