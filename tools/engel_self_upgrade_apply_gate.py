#!/usr/bin/env python3
"""Gate Engel self-upgrade patch candidates without silently applying them."""

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
    parser = argparse.ArgumentParser(description="Engel self-upgrade apply gate.")
    parser.add_argument("candidate", help="Path to an Engel self-upgrade patch candidate JSON.")
    parser.add_argument("--verifier-result", action="append", default=[], help="Project-local verifier result file.")
    parser.add_argument("--approval-token", default="", help="Exact low-risk approval token, when applicable.")
    args = parser.parse_args(argv)
    try:
        candidate = system.load_patch_candidate(args.candidate)
        receipt = system.gate_candidate(
            candidate,
            verifier_results=args.verifier_result,
            approval_token=args.approval_token,
        )
        path = system.write_gate_receipt(receipt)
    except system.SelfUpgradeError as exc:
        print(f"ENGEL_SELF_UPGRADE_APPLY_GATE_ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, "gate_receipt_path": system.project_relative(path), "gate_receipt": receipt}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
