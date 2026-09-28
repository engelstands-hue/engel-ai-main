#!/usr/bin/env python3
"""Retire stale prompt-training rows without rewriting immutable pack evidence.

The live discipline gates prevent newly detected grounding/voice failures from being
admitted.  Historical packs remain byte-for-byte evidence, so this tool records later
policy exclusions in hash-bound, append-only sidecars.  Every downstream model lane
must consult those sidecars; a malformed or stale binding fails closed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
PACKS = ROOT / "memory" / "training" / "packs"
QUARANTINES = ROOT / "memory" / "training" / "prompt_row_quarantines"
RECEIPT_DIR = ROOT / "reports" / "real_training" / "fabricated_citation_quarantine"
QUARANTINE_TAG = "regrade_20260811_sidecar_v1"

sys.path.insert(0, str(ROOT / "tools"))
import engel_prompt_training_quarantine as quarantine  # noqa: E402
import run_engel_flutter_main_ui_prompt_training as runner  # noqa: E402


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_discipline(row: dict) -> str:
    return str(row.get("training_discipline") or row.get("discipline") or "").strip().lower()


_DISCIPLINE_GATES = {
    "engineering": lambda row: runner._engineering_answer_is_grounded(
        row.get("assistant_reply") or "", row.get("base_prompt") or ""
    ),
    "communication": lambda row: runner._communication_answer_is_conversational(
        row.get("assistant_reply") or "", row.get("base_prompt") or ""
    ),
}


def _gate_verdict(row: dict) -> tuple[bool, str]:
    gate = _DISCIPLINE_GATES.get(_row_discipline(row))
    if gate is None:
        return True, "no gate registered for this discipline"
    return gate(row)


def scan_pack(path: Path) -> list[dict]:
    """Return admitted rows that the current live gate for their discipline refuses."""

    hits: list[dict] = []
    text = path.read_bytes().decode("utf-8-sig", errors="replace")
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("admit") is not True:
            continue
        if _row_discipline(row) not in _DISCIPLINE_GATES:
            continue
        ok, reason = _gate_verdict(row)
        if ok:
            continue
        hits.append(
            {
                "line_number": line_number,
                "row_sha256": hashlib.sha256(stripped.encode("utf-8")).hexdigest(),
                "prompt_index": row.get("prompt_index"),
                "scheduled_hour": row.get("scheduled_hour"),
                "run_id": row.get("run_id"),
                "reason": reason,
            }
        )
    return hits


def quarantine_pack(path: Path, apply: bool, quarantine_dir: Path) -> dict:
    """Create a sidecar for new hits and prove the pack bytes did not change."""

    before = path.read_bytes()
    loaded = quarantine.load_pack(path, quarantine_dir)
    if not loaded["ok"]:
        return {
            "pack": path.name,
            "quarantined": 0,
            "newly_quarantined": 0,
            "rows": [],
            "blockers": loaded["blockers"],
        }
    existing_lines = {
        int(item["line_number"])
        for item in loaded["rows"]
        if item.get("quarantined") is True
    }
    hits = scan_pack(path)
    new_hits = [item for item in hits if int(item["line_number"]) not in existing_lines]
    result = {
        "pack": path.name,
        "pack_sha256": hashlib.sha256(before).hexdigest(),
        "quarantined": len(existing_lines) + len(new_hits),
        "already_quarantined": len(existing_lines),
        "newly_quarantined": len(new_hits),
        "rows": new_hits,
        "blockers": [],
    }
    if apply and new_hits:
        sidecar = quarantine.write_sidecar(
            pack_path=path,
            entries=new_hits,
            source_gate=QUARANTINE_TAG,
            quarantine_dir=quarantine_dir,
        )
        result["sidecar"] = str(sidecar)
    after = path.read_bytes()
    if after != before:
        raise RuntimeError(f"immutable training pack changed during quarantine: {path}")
    result["pack_bytes_unchanged"] = True
    return result


def _write_receipt(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    temporary = path.parent / f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp"
    linked = False
    try:
        with temporary.open("xb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        linked = True
        temporary.unlink()
        os.chmod(path, 0o444)
    except Exception:
        if linked and path.exists():
            try:
                os.chmod(path, 0o600)
                path.unlink()
            except OSError:
                pass
        raise
    finally:
        if temporary.exists():
            try:
                os.chmod(temporary, 0o600)
                temporary.unlink()
            except OSError:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write append-only sidecars")
    parser.add_argument("--packs-dir", default=str(PACKS))
    parser.add_argument("--quarantine-dir", default=str(QUARANTINES))
    parser.add_argument("--receipt-dir", default=str(RECEIPT_DIR))
    args = parser.parse_args()

    packs_dir = Path(args.packs_dir)
    quarantine_dir = Path(args.quarantine_dir)
    if not packs_dir.is_dir():
        print(json.dumps({"ok": False, "error": f"no pack dir: {packs_dir}"}, indent=2))
        return 1

    results = [
        quarantine_pack(path, args.apply, quarantine_dir)
        for path in sorted(packs_dir.glob("ENGEL_PROMPT_TRAINING_PACK_*.jsonl"))
    ]
    blockers = [
        f"{item['pack']}: {problem}"
        for item in results
        for problem in item.get("blockers") or []
    ]
    receipt = {
        "schema": "engel_fabricated_citation_quarantine_v2",
        "at_utc": _utc_now(),
        "mode": "apply_sidecars" if args.apply else "dry_run",
        "packs_scanned": len(results),
        "rows_newly_quarantined": sum(item["newly_quarantined"] for item in results),
        "source_packs_modified": 0,
        "blockers": blockers,
        "packs": [
            item
            for item in results
            if item["newly_quarantined"] or item["already_quarantined"] or item["blockers"]
        ],
    }
    if args.apply:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        out = Path(args.receipt_dir) / (
            f"ENGEL_FABRICATED_CITATION_QUARANTINE_{stamp}_p{os.getpid()}.json"
        )
        _write_receipt(out, receipt)
        receipt["receipt_path"] = str(out)
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())

