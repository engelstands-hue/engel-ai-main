#!/usr/bin/env python3
"""Withhold already-stored training wrappers and lane framing from chat recall.

`_append_final_chat_memory` stamps every new turn with `context_eligible`, and turns that
are a training delivery or an echoed contract are stamped False so recall skips them. Two
classes of row predate or slipped past that:

  * training WRAPPERS whose metadata did not survive transit. The old metadata-free
    discriminator only knew the answer-CONTRACT phrasing, not the wrapper's own
    "Training depth: ... / Training task:" scaffolding, so those rows were stored as
    ordinary user chat. Measured 2026-08-13: 335 still context-eligible.
  * Discord PEER FRAMING that the bridge folds into the user turn. Engel recalled it as
    something Joshua said: 'I only know what Joshua said about it: "you are replying to
    Sub-Engel, a peer worker node on another machine - not Joshua."'

This does NOT delete history. It only sets `context_eligible: false` (plus a reason), which
is exactly what the live path would have written had the discriminator known these shapes.
Rows are rewritten in place with a backup and a receipt.

    python engel_chat_memory_hygiene_repair.py --dry-run
    python engel_chat_memory_hygiene_repair.py --apply
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

MEMORY = ROOT / "memory" / "persistent_chat" / "ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl"
REPORT_DIR = ROOT / "reports" / "persona_guard"

# Lane framing the Discord bridge folds into the user turn. Kept here rather than imported
# from the persona guard: that module's marker set is tuned for scrubbing REPLY text and
# includes short phrases ("do not invent", "is replying to") that would be too eager to
# apply to stored prompts.
LANE_FRAMING_MARKERS = (
    "context, not part of the message",
    "[context: you are replying to",
    "a peer worker node on another machine",
    "nothing runs from this lane",
    "nothing can run from this lane",
)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def file_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def classify(prompt: str) -> str:
    """Return why this row should be withheld from recall, or "" to keep it eligible."""
    low = " ".join(str(prompt or "").split()).casefold()
    if not low:
        return ""
    try:
        from engel_governor import looks_like_contract_echo, looks_like_training_wrapper

        if looks_like_training_wrapper(low):
            return "training_wrapper"
        if looks_like_contract_echo(low):
            return "answer_contract"
    except Exception:
        pass
    if any(marker in low for marker in LANE_FRAMING_MARKERS):
        return "lane_framing"
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory", default=str(MEMORY))
    parser.add_argument("--apply", action="store_true", help="rewrite the store (default dry-run)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    path = Path(args.memory)
    if not path.exists():
        print(f"memory store not found: {path}")
        return 1

    out_lines: list[str] = []
    changed = 0
    reasons: dict[str, int] = {}
    total = 0
    examples: list[str] = []

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.rstrip("\n")
            if not stripped.strip():
                continue
            total += 1
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError:
                out_lines.append(stripped)  # never rewrite what we cannot read
                continue
            if not isinstance(row, dict):
                out_lines.append(stripped)
                continue

            if row.get("context_eligible") is False:
                out_lines.append(stripped)
                continue

            reason = classify(str(row.get("prompt") or ""))
            if not reason:
                out_lines.append(stripped)
                continue

            row["context_eligible"] = False
            row["context_withheld_reason"] = reason
            row["context_withheld_at_utc"] = utc_stamp()
            if reason in {"training_wrapper", "answer_contract"}:
                row.setdefault("training_turn", True)
            changed += 1
            reasons[reason] = reasons.get(reason, 0) + 1
            if len(examples) < 4:
                examples.append(f"[{reason}] {' '.join(str(row.get('prompt') or '').split())[:110]}")
            out_lines.append(json.dumps(row, sort_keys=True))

    print(f"store  : {path}")
    print(f"rows   : {total}")
    print(f"withhold: {changed}")
    for reason, count in sorted(reasons.items()):
        print(f"  {reason:18} {count}")
    for line in examples:
        print(f"  - {line}")

    if not changed:
        print("\nnothing to repair")
        return 0
    if not args.apply:
        print("\ndry run - pass --apply to rewrite")
        return 0

    stamp = file_stamp()
    backup = path.with_suffix(path.suffix + f".bak_hygiene_{stamp}")
    shutil.copy2(path, backup)
    tmp = path.with_suffix(path.suffix + f".tmp_{stamp}")
    tmp.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    tmp.replace(path)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    receipt = REPORT_DIR / f"ENGEL_CHAT_MEMORY_HYGIENE_{stamp}.json"
    receipt.write_text(
        json.dumps(
            {
                "schema": "engel_chat_memory_hygiene_repair_v1",
                "repaired_at_utc": utc_stamp(),
                "store": str(path),
                "backup": str(backup),
                "rows_total": total,
                "rows_withheld": changed,
                "reasons": reasons,
                "note": "context_eligible set to false only; no history deleted",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nbackup : {backup}")
    print(f"receipt: {receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
