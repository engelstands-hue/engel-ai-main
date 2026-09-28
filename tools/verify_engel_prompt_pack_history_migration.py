#!/usr/bin/env python3
"""Behavioral proof for recoverable immutable prompt-pack history migration."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import engel_prompt_novelty as novelty  # noqa: E402
import engel_prompt_training_quarantine as quarantine  # noqa: E402
import migrate_engel_prompt_pack_history as migration  # noqa: E402


PYTHON = ROOT / "runtime" / "python310" / "python.exe"
MIGRATOR = TOOLS / "migrate_engel_prompt_pack_history.py"
CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: Any = "") -> None:
    CHECKS.append((name, bool(condition), str(detail)))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def row(index: int, admit: bool, *, reply: str = "answer") -> dict[str, Any]:
    base_prompt = f"Prompt {index} with cafe"
    return {
        "schema": novelty.PACK_ROW_SCHEMA,
        "run_id": "synthetic_history_run",
        "prompt_index": index,
        "prompt_sha256": sha(base_prompt.encode("utf-8")),
        "base_prompt": base_prompt,
        "base_prompt_sha256": novelty.canonical_base_prompt_sha256(base_prompt),
        "assistant_reply": reply,
        "scheduled_hour": 1,
        "admit": admit,
        "admit_reason": "original gate" if admit else "original rejection",
        "discipline_eligibility_ok": admit,
        "training_sample_eligible": admit,
    }


def rendered(rows: list[dict[str, Any]], *, crlf: bool = False) -> bytes:
    ending = "\r\n" if crlf else "\n"
    return (
        ending.join(
            json.dumps(item, ensure_ascii=False, sort_keys=False, indent=None)
            for item in rows
        )
        + ending
    ).encode("utf-8")


def is_read_only(path: Path) -> bool:
    return not bool(path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def tree_state(root: Path) -> dict[str, tuple[str, int, int]]:
    result: dict[str, tuple[str, int, int]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        info = path.stat()
        result[path.relative_to(root).as_posix()] = (
            sha(path.read_bytes()),
            stat.S_IMODE(info.st_mode),
            info.st_mtime_ns,
        )
    return result


def invoke(
    root: Path,
    *,
    apply: bool = False,
    discard_promotions: bool = False,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    command = [
        str(PYTHON),
        str(MIGRATOR),
        "--packs-dir",
        str(root / "packs"),
        "--quarantine-dir",
        str(root / "quarantines"),
        "--snapshot-dir",
        str(root / "snapshots"),
        "--receipt-dir",
        str(root / "receipts"),
    ]
    if apply:
        command.append("--apply")
    if discard_promotions:
        command.append("--discard-unbound-promotions")
    process = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    try:
        payload = json.loads(process.stdout)
    except ValueError:
        payload = {"stdout": process.stdout, "stderr": process.stderr}
    return process, payload


def setup_demotion_case(root: Path) -> tuple[Path, bytes, bytes, Path]:
    packs = root / "packs"
    packs.mkdir(parents=True)
    name = "ENGEL_PROMPT_TRAINING_PACK_synthetic_demotion.jsonl"
    pack = packs / name
    original = [row(1, True, reply="trusted caf\u00e9 answer"), row(2, False)]
    current = [dict(item) for item in original]
    current[0].update(
        {
            "admit": False,
            "admit_reason": "old quarantine demotion",
            "discipline_eligibility_ok": False,
            "training_sample_eligible": False,
            "quarantined_at_utc": "2026-08-01T00:00:00+00:00",
            "quarantined_by": "old_mutator",
        }
    )
    current_bytes = rendered(current, crlf=True)
    pack.write_bytes(current_bytes)
    backup = packs / f"{name}.pre_fabricated_citation_quarantine_bak"
    backup.write_bytes(rendered(original, crlf=True))
    roster = packs / "ENGEL_PROMPT_TRAINING_PACK_roster_only.jsonl"
    roster.write_bytes(rendered([row(3, False)]))
    canonical = migration.canonical_pack_bytes(original)
    (packs / "ENGEL_PROMPT_TRAINING_PACK_LATEST.json").write_text(
        json.dumps(
            {
                "schema": "engel_prompt_training_pack_v1",
                "pack_path": str(pack),
                "pack_sha256": sha(canonical),
                "rows": len(original),
            }
        ),
        encoding="utf-8",
    )
    return pack, current_bytes, canonical, roster


def prove_dry_run_and_apply(parent: Path) -> None:
    root = parent / "demotion"
    pack, current_bytes, canonical, roster = setup_demotion_case(root)
    before = tree_state(root)
    dry_process, dry = invoke(root)
    after = tree_state(root)
    check("dry_run_exit_zero", dry_process.returncode == 0, dry)
    check("dry_run_reports_restore", dry.get("plans", [{}])[0].get("status") == "WOULD_RESTORE", dry)
    check("dry_run_writes_nothing", before == after)
    check(
        "writer_exact_ascii_canonicalization",
        canonical.isascii()
        and b"\r\n" not in canonical
        and canonical.endswith(b"\n"),
        canonical[:120],
    )

    apply_process, applied = invoke(root, apply=True)
    check("apply_exit_zero", apply_process.returncode == 0, applied)
    result = (applied.get("applied") or [{}])[0]
    check("sidecar_published_before_restore", result.get("pre_restore_sidecar_failed_closed") is True, result)
    check("sidecar_valid_after_restore", result.get("post_restore_sidecar_valid") is True, result)
    check("restored_bytes_exact", pack.read_bytes() == canonical, sha(pack.read_bytes()))
    snapshot = Path(str(result.get("snapshot_path") or ""))
    check("forensic_snapshot_exact", snapshot.is_file() and snapshot.read_bytes() == current_bytes, snapshot)
    receipt = json.loads(Path(result["receipt_path"]).read_text(encoding="utf-8"))
    check("receipt_binds_exact_hash", receipt.get("restored_pack_sha256") == sha(canonical), receipt)
    check("receipt_lists_demotion", receipt.get("demoted_line_numbers") == [1], receipt)
    check(
        "validated_roster_all_read_only",
        is_read_only(pack)
        and is_read_only(roster)
        and all(
            is_read_only(path)
            for path in (root / "packs").glob("*.jsonl.pre_*")
        )
        and applied.get("pack_roster_read_only") is True,
        applied,
    )
    loaded = quarantine.load_pack(pack, root / "quarantines")
    check(
        "restored_pack_exclusion_applies",
        loaded["ok"] and loaded["quarantined"] == 1,
        loaded["blockers"],
    )

    state_before_repeat = tree_state(root)
    repeat_process, repeat = invoke(root, apply=True)
    state_after_repeat = tree_state(root)
    repeated = (repeat.get("applied") or [{}])[0]
    check("repeat_exit_zero", repeat_process.returncode == 0, repeat)
    check("repeat_is_idempotent", repeated.get("status") == "ALREADY_APPLIED", repeated)
    check("repeat_writes_nothing", state_before_repeat == state_after_repeat)


def prove_unexpected_diff_refusal(parent: Path) -> None:
    root = parent / "unexpected"
    packs = root / "packs"
    packs.mkdir(parents=True)
    name = "ENGEL_PROMPT_TRAINING_PACK_unexpected.jsonl"
    original = [row(1, True, reply="original")]
    changed = [row(1, False, reply="unrelated content changed")]
    (packs / name).write_bytes(rendered(changed))
    (packs / f"{name}.pre_offcard_quarantine_bak").write_bytes(rendered(original))
    before = tree_state(root)
    process, payload = invoke(root)
    check("unexpected_diff_refused", process.returncode == 2, payload)
    check(
        "unexpected_diff_named",
        any("unexpected non-quarantine content drift" in item for item in payload.get("blockers", [])),
        payload,
    )
    check("refusal_writes_nothing", before == tree_state(root))


def prove_promotion_requires_explicit_discard(parent: Path) -> None:
    root = parent / "promotion"
    packs = root / "packs"
    packs.mkdir(parents=True)
    name = "ENGEL_PROMPT_TRAINING_PACK_promotion.jsonl"
    original = [row(1, False)]
    promoted = [dict(original[0])]
    promoted[0].update(
        {
            "admit": True,
            "admit_reason": "in-place regrade promotion",
            "discipline_eligibility_ok": True,
            "training_sample_eligible": True,
            "regrade_run": "legacy_regrade",
            "regraded_at_utc": "2026-08-07T00:00:00+00:00",
        }
    )
    pack = packs / name
    promoted_bytes = rendered(promoted, crlf=True)
    pack.write_bytes(promoted_bytes)
    backup = packs / f"{name}.pre_regrade_20260807.bak"
    backup.write_bytes(rendered(original))
    blocked_process, blocked = invoke(root)
    check("promotion_default_refusal", blocked_process.returncode == 2, blocked)
    check(
        "promotion_default_explains_override",
        any("--discard-unbound-promotions" in item for item in blocked.get("blockers", [])),
        blocked,
    )
    apply_process, applied = invoke(
        root, apply=True, discard_promotions=True
    )
    result = (applied.get("applied") or [{}])[0]
    check("explicit_promotion_discard_applies", apply_process.returncode == 0, applied)
    restored = json.loads(pack.read_text(encoding="utf-8").splitlines()[0])
    check("promotion_conservatively_removed", restored.get("admit") is False, restored)
    receipt = json.loads(Path(result["receipt_path"]).read_text(encoding="utf-8"))
    discarded = receipt.get("discarded_unbound_promotions") or []
    check(
        "promotion_discard_receipted",
        len(discarded) == 1
        and discarded[0].get("line_number") == 1
        and "in-place regrade promotion" in discarded[0].get("reason", ""),
        receipt,
    )
    snapshot = Path(result["snapshot_path"])
    check("promoted_bytes_forensically_preserved", snapshot.read_bytes() == promoted_bytes, snapshot)


def prove_prospective_binding_and_integrity(parent: Path) -> None:
    root = parent / "prospective"
    packs = root / "packs"
    quarantines = root / "quarantines"
    packs.mkdir(parents=True)
    name = "ENGEL_PROMPT_TRAINING_PACK_prospective.jsonl"
    pack = packs / name
    original = [row(1, True)]
    current = [dict(original[0])]
    current[0].update(
        {
            "admit": False,
            "admit_reason": "historical demotion",
            "discipline_eligibility_ok": False,
            "training_sample_eligible": False,
        }
    )
    canonical = migration.canonical_pack_bytes(original)
    pack.write_bytes(rendered(current))
    os.chmod(pack, 0o444)
    canonical_line = canonical.decode("utf-8").splitlines()[0]
    sidecar = quarantine.write_sidecar_for_bytes(
        pack_name=name,
        pack_bytes=canonical,
        entries=[
            {
                "line_number": 1,
                "row_sha256": sha(canonical_line.encode("utf-8")),
                "prompt_index": 1,
                "scheduled_hour": 1,
                "run_id": "synthetic_history_run",
                "reason": "historical demotion",
            }
        ],
        source_gate=migration.SOURCE_GATE,
        quarantine_dir=quarantines,
    )
    before = quarantine.load_pack(pack, quarantines)
    check(
        "prospective_sidecar_fails_closed_before_bytes_exist",
        not before["ok"]
        and any(
            "pack bytes changed after quarantine sidecar" in item
            for item in before["blockers"]
        ),
        before["blockers"],
    )
    os.chmod(pack, 0o600)
    pack.write_bytes(canonical)
    os.chmod(pack, 0o444)
    after = quarantine.load_pack(pack, quarantines)
    check(
        "prospective_sidecar_valid_after_exact_restore",
        after["ok"] and after["quarantined"] == 1,
        after["blockers"],
    )

    os.chmod(pack, 0o600)
    mutable_pack = quarantine.load_pack(pack, quarantines)
    check(
        "quarantine_loader_refuses_writable_pack",
        not mutable_pack["ok"]
        and any("stamped training pack is mutable" in item for item in mutable_pack["blockers"]),
        mutable_pack["blockers"],
    )
    history = novelty.load_prompt_history(packs, root / "reservations")
    check(
        "novelty_history_refuses_writable_pack",
        not history["ok"]
        and any("history pack is mutable" in item for item in history["problems"]),
        history["problems"],
    )
    os.chmod(pack, 0o444)

    os.chmod(sidecar, 0o600)
    mutable_sidecar = quarantine.load_pack(pack, quarantines)
    check(
        "quarantine_loader_refuses_writable_sidecar",
        not mutable_sidecar["ok"]
        and any("quarantine sidecar is mutable" in item for item in mutable_sidecar["blockers"]),
        mutable_sidecar["blockers"],
    )
    os.chmod(sidecar, 0o444)

    directory_pack = packs / "ENGEL_PROMPT_TRAINING_PACK_directory.jsonl"
    directory_pack.mkdir()
    non_regular = quarantine.load_pack(directory_pack, quarantines)
    check(
        "quarantine_loader_refuses_non_regular_pack",
        not non_regular["ok"]
        and any("regular file" in item for item in non_regular["blockers"]),
        non_regular["blockers"],
    )
    link = packs / "ENGEL_PROMPT_TRAINING_PACK_symlink.jsonl"
    try:
        os.symlink(pack, link)
    except OSError as exc:
        check("quarantine_loader_symlink_test_unavailable", True, exc)
    else:
        linked = quarantine.load_pack(link, quarantines)
        check(
            "quarantine_loader_refuses_symlink_pack",
            not linked["ok"] and any("non-symlink" in item for item in linked["blockers"]),
            linked["blockers"],
        )


def prove_latest_hash_assertion(parent: Path) -> None:
    root = parent / "bad_latest"
    setup_demotion_case(root)
    latest_path = root / "packs" / "ENGEL_PROMPT_TRAINING_PACK_LATEST.json"
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    latest["pack_sha256"] = "0" * 64
    latest_path.write_text(json.dumps(latest), encoding="utf-8")
    process, payload = invoke(root)
    check("latest_receipt_hash_mismatch_refused", process.returncode == 2, payload)
    check(
        "latest_receipt_hash_mismatch_explained",
        any("LATEST receipt hash" in item for item in payload.get("blockers", [])),
        payload,
    )


def main() -> int:
    workspace_temp = ROOT / ".codex_prompt_pack_history_verify"
    workspace_temp.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=workspace_temp) as temporary:
        parent = Path(temporary)
        prove_dry_run_and_apply(parent)
        prove_unexpected_diff_refusal(parent)
        prove_promotion_requires_explicit_discard(parent)
        prove_prospective_binding_and_integrity(parent)
        prove_latest_hash_assertion(parent)
    try:
        workspace_temp.rmdir()
    except OSError:
        pass
    for name, passed, detail in CHECKS:
        print(f"{'PASS' if passed else 'FAIL'} {name}" + (f": {detail}" if detail else ""))
    passed_count = sum(1 for _name, passed, _detail in CHECKS if passed)
    print(f"SUMMARY {passed_count}/{len(CHECKS)} checks passed")
    return 0 if passed_count == len(CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
