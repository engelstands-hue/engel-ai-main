#!/usr/bin/env python3
"""Quarantine persona-leak examples from the graded voice bank.

The bank (`memory/personality/engel_voice_examples.jsonl`) is what few-shot retrieval draws
on and what `export_finetune_pairs()` turns into style-LoRA training data. So an entry whose
"reply" is really Engel reciting its answer-contract is worse than useless: it teaches both
the retrieval layer and the next fine-tune that reciting IS Engel's voice.

`engel_persona_guard` now stops new ones being captured (`_apply_chat_humanizer` scrubs before
`_maybe_capture_voice_example`), but entries captured before that landed are still in the file.
This moves them out.

Uses the SAME markers as the live guard, so the bank can never be cleaned to a different
standard than the one replies are held to.

    python engel_persona_bank_quarantine.py --dry-run
    python engel_persona_bank_quarantine.py --apply
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

BANK = ROOT / "memory" / "personality" / "engel_voice_examples.jsonl"
REPORT_DIR = ROOT / "reports" / "persona_guard"

REPLY_KEYS = ("reply", "assistant_reply", "output", "response", "text")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def file_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def reply_of(row: dict[str, Any]) -> str:
    for key in REPLY_KEYS:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", default=str(BANK))
    parser.add_argument("--apply", action="store_true", help="rewrite the bank (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    bank_path = Path(args.bank)
    if not bank_path.exists():
        print(f"voice bank not found: {bank_path}")
        return 1

    try:
        from engel_persona_guard import looks_like_persona_leak
    except Exception as exc:  # noqa: BLE001
        print(f"cannot import engel_persona_guard: {exc}")
        return 1

    kept: list[str] = []
    quarantined: list[str] = []
    unparsed = 0

    for line in bank_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            unparsed += 1
            kept.append(line)  # never drop something we could not read
            continue
        if not isinstance(row, dict):
            kept.append(line)
            continue
        if looks_like_persona_leak(reply_of(row)):
            quarantined.append(line)
        else:
            kept.append(line)

    total = len(kept) + len(quarantined)
    print(f"bank         : {bank_path}")
    print(f"total entries: {total}")
    print(f"quarantine   : {len(quarantined)}")
    print(f"keep         : {len(kept)}")
    if unparsed:
        print(f"unparsed kept: {unparsed}")

    for line in quarantined[:5]:
        try:
            preview = reply_of(json.loads(line))
        except Exception:  # noqa: BLE001
            preview = line
        print(f"  - {' '.join(preview.split())[:130]}")
    if len(quarantined) > 5:
        print(f"  ... and {len(quarantined) - 5} more")

    if not quarantined:
        print("\nnothing to quarantine")
        return 0

    if not args.apply:
        print("\ndry run - pass --apply to rewrite the bank")
        return 0

    stamp = file_stamp()
    backup = bank_path.with_suffix(bank_path.suffix + f".bak_persona_{stamp}")
    shutil.copy2(bank_path, backup)
    quarantine_path = bank_path.with_name(f"engel_voice_examples.persona_quarantine_{stamp}.jsonl")
    quarantine_path.write_text("\n".join(quarantined) + "\n", encoding="utf-8")
    bank_path.write_text(("\n".join(kept) + "\n") if kept else "", encoding="utf-8")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    receipt = REPORT_DIR / f"ENGEL_PERSONA_BANK_QUARANTINE_{stamp}.json"
    receipt.write_text(
        json.dumps(
            {
                "schema": "engel_persona_bank_quarantine_v1",
                "quarantined_at_utc": utc_stamp(),
                "bank": str(bank_path),
                "backup": str(backup),
                "quarantine_file": str(quarantine_path),
                "total_before": total,
                "quarantined": len(quarantined),
                "kept": len(kept),
                "reason": "reply recites the persona/answer contract instead of answering",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nbackup     : {backup}")
    print(f"quarantined: {quarantine_path}")
    print(f"receipt    : {receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
