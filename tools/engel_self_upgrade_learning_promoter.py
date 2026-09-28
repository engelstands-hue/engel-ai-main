#!/usr/bin/env python3
"""Create candidate memory from verified Engel self-upgrade receipts.

This does not write trusted memory. It writes reviewable memory candidates only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_self_upgrade_system as system


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel self-upgrade candidate memory promoter.")
    parser.add_argument("--gate-receipt", required=True, help="Project-local gate receipt JSON.")
    parser.add_argument("--lesson", required=True, help="Lesson to write as untrusted candidate memory.")
    args = parser.parse_args(argv)
    try:
        receipt = system.read_json(system.resolve_report_path(args.gate_receipt))
        candidate = system.build_memory_candidate_from_gate(receipt, lesson=args.lesson)
        path = system.write_memory_candidate(candidate)
    except system.SelfUpgradeError as exc:
        print(f"ENGEL_SELF_UPGRADE_LEARNING_PROMOTER_ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, "memory_candidate_path": system.project_relative(path), "memory_candidate": candidate}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
