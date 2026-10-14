#!/usr/bin/env python3
"""Each desk creates the next missing finish item and files it."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import engel_desk_finish_work as finish  # noqa: E402


def main() -> int:
    failures: list[str] = []

    def require(ok: bool, message: str) -> None:
        print("[PASS]" if ok else "[FAIL]", message)
        if not ok:
            failures.append(message)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "memory" / "training" / "engel_main" / "templates").mkdir(parents=True)
        (root / "memory" / "training" / "engel_main" / "templates" / "curricula_index.json").write_text(
            '{"curricula":[{"id":"local_notes","novelty_status":"open"}]}',
            encoding="utf-8",
        )
        first = finish.advance_desk_finish(root, "product")
        second = finish.advance_desk_finish(root, "product")
        third = finish.advance_desk_finish(root, "product")
        fourth = finish.advance_desk_finish(root, "product")
        require("Created the finish item" in first, "first pass creates the product finish item")
        require("Filed " in first, "the created item is filed")
        require("Not applied" not in first, "the created item does not wait for a question")
        require("Created the finish item" in second, "second pass opens the next missing part")
        require("finished-answer card" in second, "the next part is the finished-answer card")
        require("health" not in second.casefold(), "the next part is not a health check")
        require("phone lane map" in third, "the real item is the phone lane map")
        require("need from" not in third, "a receipt name is not the next item")
        require("already filed" in fourth, "a finished queue does not write another copy")
        path = root / "reports" / "desk_finish" / "product" / "FINISH_SLICE.md"
        require(path.is_file() and "The desk filed this slice" in path.read_text(encoding="utf-8"), "product slice is on disk")
        board = (root / "reports" / "desk_finish" / "board.json").read_text(encoding="utf-8")
        require('"trusted_memory_write": false' in board, "finish board is not trusted memory")
        require('"applied": true' in board, "board marks the filed item in use")
        desk_root = root / "desks" / "research"
        desk_root.mkdir(parents=True)
        research = finish.advance_desk_finish(desk_root, "research")
        require("Created the finish item" in research, "a desk sandbox files the item on Engel AI Main")
        require((root / "reports" / "desk_finish" / "research" / "EVIDENCE_CARD.md").is_file(), "research card lands on the main tree")
        training = finish.advance_desk_finish(root, "training")
        note = (root / "reports" / "desk_finish" / "training" / "NEXT_CURRICULUM.md").read_text(encoding="utf-8")
        require("No run was started" in note, "training note does not start a run")
        require("local_notes" in note, "training note names the curriculum")
        require("Created the finish item" in training, "training desk creates its note")
        builder = (finish.advance_desk_finish(root, "builder"))
        draft = (root / "reports" / "desk_finish" / "builder" / "NEXT_DRAFT.md").read_text(encoding="utf-8")
        require("The draft is filed" in draft, "builder draft is filed")
        require("Filed " in builder, "builder speech names the filed draft")
        ops_first = finish.advance_desk_finish(root, "ops")
        ops_next = finish.advance_desk_finish(root, "ops")
        require("idle watch" in ops_first, "ops still files its first candidate")
        require("swap-guard runbook" in ops_next, "ops then files the swap-guard upgrade")
        require("service" not in ops_next.casefold(), "ops does not file a service check")
        receipts = root / "reports" / "codex_bridge"
        receipts.mkdir(parents=True)
        (receipts / "EXAMPLE_RECEIPT.md").write_text("note\n", encoding="utf-8")
        after_receipt = finish.advance_desk_finish(root, "product")
        require("already filed" in after_receipt, "a new receipt name does not become the work item")
        found = list((root / "reports" / "desk_finish" / "product").glob("FOUND_*"))
        require(not found, "no receipt stub is filed")

    if failures:
        print(f"FAIL {len(failures)}")
        return 1
    print("PASS: Engel desk finish work")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
