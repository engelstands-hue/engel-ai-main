#!/usr/bin/env python3
"""Focused behavioral checks for scheduled prompt replay refusal and asset renewal."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import engel_prompt_novelty as novelty  # noqa: E402
import run_engel_flutter_main_ui_prompt_training as runner  # noqa: E402
import sync_engel_training_assets as assets  # noqa: E402


checks: list[dict[str, Any]] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append(
        {"name": name, "status": "PASS" if ok else "FAIL", "detail": detail}
    )


def pack_row(prompt: str, index: int = 1, *, stored_hash: str = "") -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema": novelty.PACK_ROW_SCHEMA,
        "run_id": "isolated_novelty_fixture",
        "prompt_index": index,
        "base_prompt": prompt,
        "admit": True,
    }
    if stored_hash:
        row["base_prompt_sha256"] = stored_hash
    return row


def write_pack(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    os.chmod(path, 0o444)


temp_root = ROOT / "runtime" / "temp"
temp_root.mkdir(parents=True, exist_ok=True)
work = Path(tempfile.mkdtemp(prefix="engel_prompt_novelty_verify_", dir=str(temp_root)))

try:
    packs = work / "packs"
    packs.mkdir()
    old_prompt = "Explain the verified deployment state and name the receipt that proves it."
    legacy_exact = hashlib.sha256(old_prompt.strip().encode("utf-8")).hexdigest()
    historical_pack = packs / "ENGEL_PROMPT_TRAINING_PACK_fixture_20260809.jsonl"
    write_pack(historical_pack, [pack_row(old_prompt, stored_hash=legacy_exact)])

    repeated = novelty.evaluate_scheduled_prompt_novelty(
        ["  EXPLAIN the verified deployment state\n and name the receipt that proves it.  "],
        packs,
    )
    check(
        "historical_repeat_blocks_before_run",
        repeated["ok"] is False
        and repeated["decision"] == "BLOCK"
        and repeated["replayed_prompt_count"] == 1
        and repeated["novel_prompt_count"] == 0,
        json.dumps(
            {
                "decision": repeated["decision"],
                "replayed": repeated["replayed_prompt_hashes"],
            },
            sort_keys=True,
        ),
    )
    check(
        "cosmetic_changes_do_not_fake_novelty",
        repeated["replayed_prompt_hashes"]
        == [novelty.canonical_base_prompt_sha256(old_prompt)]
        and repeated["canonicalization"] == novelty.CANONICALIZATION,
        "case and whitespace variants have one canonical base-prompt identity",
    )
    check(
        "legacy_stored_hash_is_validated_separately",
        repeated["history_stored_hash_scheme_counts"].get("legacy_exact_v0") == 1
        and not any("mismatch" in item for item in repeated["blockers"]),
        json.dumps(repeated["history_stored_hash_scheme_counts"], sort_keys=True),
    )

    new_prompt = (
        "Compare two newly supplied signed deployment receipts, identify the first "
        "diverging provenance edge, and specify the deterministic recheck."
    )
    novel = novelty.evaluate_scheduled_prompt_novelty([new_prompt], packs)
    check(
        "materially_novel_prompt_passes",
        novel["ok"] is True
        and novel["decision"] == "PASS"
        and novel["novel_prompt_count"] == 1
        and novel["replayed_prompt_count"] == 0,
        json.dumps(
            {
                "decision": novel["decision"],
                "novel": novel["novel_prompt_hashes"],
            },
            sort_keys=True,
        ),
    )
    check(
        "history_snapshot_and_sets_are_receipted",
        len(novel["history_pack_snapshot_sha256"]) == 64
        and len(novel["history_prompt_set_sha256"]) == 64
        and len(novel["planned_prompt_set_sha256"]) == 64
        and novel["history_pack_count"] == 1
        and novel["history_row_count"] == 1,
        (
            f"packs={novel['history_pack_count']} rows={novel['history_row_count']} "
            f"snapshot={novel['history_pack_snapshot_sha256']}"
        ),
    )

    duplicate = novelty.evaluate_scheduled_prompt_novelty(
        [new_prompt, "  " + new_prompt.upper() + "\n"], packs
    )
    check(
        "within_plan_duplicate_blocks",
        duplicate["ok"] is False
        and duplicate["in_plan_duplicate_count"] == 1,
        json.dumps(duplicate["in_plan_duplicate_hashes"], sort_keys=True),
    )

    corrupt_packs = work / "corrupt_packs"
    corrupt_packs.mkdir()
    (corrupt_packs / "ENGEL_PROMPT_TRAINING_PACK_corrupt.jsonl").write_text(
        "{not json}\n", encoding="utf-8"
    )
    os.chmod(
        corrupt_packs / "ENGEL_PROMPT_TRAINING_PACK_corrupt.jsonl",
        0o444,
    )
    corrupt = novelty.evaluate_scheduled_prompt_novelty([new_prompt], corrupt_packs)
    check(
        "corrupt_history_fails_closed",
        corrupt["ok"] is False
        and corrupt["blockers"]
        and "invalid JSON" in corrupt["blockers"][0],
        repr(corrupt["blockers"]),
    )

    claim_path = work / "prompt_run.lock"
    child_script = "\n".join(
        [
            "import sys",
            "from pathlib import Path",
            "sys.path.insert(0, sys.argv[1])",
            "import engel_prompt_novelty as novelty",
            "try:",
            "    with novelty.acquire_prompt_run_claim(Path(sys.argv[2]), sys.argv[3]):",
            "        print('ACQUIRED')",
            "except novelty.PromptRunClaimBlocked:",
            "    print('BLOCKED')",
            "    raise SystemExit(73)",
        ]
    )

    def child_claim(run_id: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-c",
                child_script,
                str(TOOLS),
                str(claim_path),
                run_id,
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

    with novelty.acquire_prompt_run_claim(claim_path, "parent_claim") as parent_claim:
        parent_claim.require_owner("parent_claim")
        blocked_child = child_claim("concurrent_child")
        check(
            "concurrent_process_is_refused_by_os_claim",
            blocked_child.returncode == 73
            and blocked_child.stdout.strip() == "BLOCKED"
            and parent_claim.held
            and parent_claim.owner_pid == os.getpid(),
            (
                f"child_exit={blocked_child.returncode} "
                f"stdout={blocked_child.stdout.strip()!r}"
            ),
        )
    released_child = child_claim("after_release_child")
    check(
        "process_exit_or_context_release_frees_claim",
        released_child.returncode == 0
        and released_child.stdout.strip() == "ACQUIRED",
        (
            f"child_exit={released_child.returncode} "
            f"stdout={released_child.stdout.strip()!r}"
        ),
    )

    reservation_case = work / "reservation_case"
    reservation_packs = reservation_case / "packs"
    reservation_dir = reservation_case / "prompt_use_reservations"
    reservation_packs.mkdir(parents=True)
    before_reservation = novelty.evaluate_scheduled_prompt_novelty(
        [new_prompt], reservation_packs, reservation_dir
    )
    reservation_claim_path = reservation_case / "claim.lock"
    with novelty.acquire_prompt_run_claim(
        reservation_claim_path, "pack_failure_run"
    ) as reservation_claim:
        reserved = novelty.publish_prompt_use_reservation(
            reservations_dir=reservation_dir,
            prompt_run_claim=reservation_claim,
            run_id="pack_failure_run",
            prompt_position=1,
            base_prompt=new_prompt,
            history_snapshot_sha256=before_reservation[
                "history_snapshot_sha256"
            ],
            history_pack_snapshot_sha256=before_reservation[
                "history_pack_snapshot_sha256"
            ],
            history_reservation_snapshot_sha256=before_reservation[
                "history_reservation_snapshot_sha256"
            ],
            planned_prompt_set_sha256=before_reservation[
                "planned_prompt_set_sha256"
            ],
        )
    after_missing_pack = novelty.evaluate_scheduled_prompt_novelty(
        [new_prompt], reservation_packs, reservation_dir
    )
    check(
        "delivered_prompt_with_pack_failure_remains_replay_blocked",
        not list(reservation_packs.glob("*.jsonl"))
        and after_missing_pack["ok"] is False
        and after_missing_pack["replayed_prompt_count"] == 1
        and after_missing_pack["history_valid_reservation_count"] == 1
        and any(
            occurrence.get("source") == "prompt_use_reservation"
            for occurrence in after_missing_pack["replayed"][0][
                "history_occurrences"
            ]
        )
        and reserved.get("immutable") is True,
        json.dumps(
            {
                "reservation": reserved.get("path"),
                "blockers": after_missing_pack.get("blockers"),
            },
            sort_keys=True,
        ),
    )

    malformed_case = work / "malformed_reservation_case"
    malformed_packs = malformed_case / "packs"
    malformed_dir = malformed_case / "prompt_use_reservations"
    malformed_packs.mkdir(parents=True)
    malformed_dir.mkdir()
    malformed_path = malformed_dir / (
        f"{novelty.RESERVATION_PREFIX}{'0' * 64}{novelty.RESERVATION_SUFFIX}"
    )
    malformed_path.write_text("{not json}\n", encoding="utf-8")
    os.chmod(malformed_path, 0o444)
    malformed_result = novelty.evaluate_scheduled_prompt_novelty(
        [new_prompt], malformed_packs, malformed_dir
    )
    check(
        "malformed_reservation_ledger_blocks_all_scheduled_delivery",
        malformed_result["ok"] is False
        and any(
            "invalid prompt-use reservation" in blocker
            for blocker in malformed_result["blockers"]
        ),
        repr(malformed_result["blockers"]),
    )

    conflict_case = work / "conflicting_reservation_case"
    conflict_packs = conflict_case / "packs"
    conflict_dir = conflict_case / "prompt_use_reservations"
    conflict_packs.mkdir(parents=True)
    conflict_preflight = novelty.evaluate_scheduled_prompt_novelty(
        [new_prompt], conflict_packs, conflict_dir
    )
    for conflicting_run in ("conflict_a", "conflict_b"):
        with novelty.acquire_prompt_run_claim(
            conflict_case / "claim.lock", conflicting_run
        ) as conflict_claim:
            novelty.publish_prompt_use_reservation(
                reservations_dir=conflict_dir,
                prompt_run_claim=conflict_claim,
                run_id=conflicting_run,
                prompt_position=1,
                base_prompt=new_prompt,
                history_snapshot_sha256=conflict_preflight[
                    "history_snapshot_sha256"
                ],
                history_pack_snapshot_sha256=conflict_preflight[
                    "history_pack_snapshot_sha256"
                ],
                history_reservation_snapshot_sha256=conflict_preflight[
                    "history_reservation_snapshot_sha256"
                ],
                planned_prompt_set_sha256=conflict_preflight[
                    "planned_prompt_set_sha256"
                ],
            )
    conflict_result = novelty.evaluate_scheduled_prompt_novelty(
        ["A third unrelated prompt."], conflict_packs, conflict_dir
    )
    check(
        "conflicting_reservation_ledger_fails_closed",
        conflict_result["ok"] is False
        and any(
            "reserved more than once" in blocker
            for blocker in conflict_result["blockers"]
        ),
        repr(conflict_result["blockers"]),
    )

    guard_path = work / "active.json"
    original_guard_path = runner.LOCAL_ONLY_TRAINING_SENTINEL
    try:
        runner.LOCAL_ONLY_TRAINING_SENTINEL = guard_path
        guard_path.write_text(
            json.dumps(
                {
                    "status": "RUNNING",
                    "run_id": "foreign_untrusted_run",
                    "launcher_pid": 999999,
                    "provider_policy": "local_only",
                    "expires_at_epoch": 9999999999,
                }
            ),
            encoding="utf-8",
        )
        guard_claim_path = work / "guard_prompt_run.lock"
        with novelty.acquire_prompt_run_claim(
            guard_claim_path, "bound_guard_run"
        ) as guard_claim:
            activated = runner._activate_local_only_guard(
                "bound_guard_run",
                9999999999,
                prompt_run_claim=guard_claim,
                scheduled_hours=1,
                requested_minutes=60,
                training_level="expert",
                level_profile={"profile_id": "expert", "guidance": "verify"},
                trainings_per_hour=1,
                cadence_seconds=3600,
            )
            active_payload = json.loads(guard_path.read_text(encoding="utf-8"))
            runner._finish_local_only_guard(
                "bound_guard_run",
                "COMPLETED",
                prompt_run_claim=guard_claim,
            )
            finished_payload = json.loads(guard_path.read_text(encoding="utf-8"))
        check(
            "active_guard_is_bound_to_exact_claim_run_and_pid",
            activated.get("owned") is True
            and active_payload.get("run_id") == "bound_guard_run"
            and active_payload.get("launcher_pid") == os.getpid()
            and active_payload.get("runner_pid") == os.getpid()
            and active_payload.get("prompt_run_claim", {}).get("owner_pid")
            == os.getpid()
            and Path(
                active_payload.get("prompt_run_claim", {}).get("claim_path", "")
            ).resolve()
            == guard_claim_path.resolve()
            and active_payload.get("superseded_guard", {}).get("run_id")
            == "foreign_untrusted_run"
            and finished_payload.get("status") == "COMPLETED",
            json.dumps(active_payload, sort_keys=True),
        )
    finally:
        runner.LOCAL_ONLY_TRAINING_SENTINEL = original_guard_path

    # Asset preparation uses two real reviewed alternate construction cards.  Put every
    # prompt from card one into history and prove the prepared template selects card two
    # unchanged rather than manufacturing a suffix or nonce for card one.
    alternate_cards = list(assets._curric.ENGEL_CHAT_COMMUNICATION_CARDS_V1[:2])
    used_prompts = assets.curriculum_prompts(alternate_cards[0], "communication")[0]
    prep_packs = work / "prep_packs"
    prep_packs.mkdir()
    write_pack(
        prep_packs / "ENGEL_PROMPT_TRAINING_PACK_used_card.jsonl",
        [pack_row(prompt, index) for index, prompt in enumerate(used_prompts, start=1)],
    )
    prepared_dir = work / "prepared_templates"
    source = {
        "id": "isolated_reviewed_alternate",
        "title": "Isolated Reviewed Alternate",
        "detail": "two real cards",
        "cards": alternate_cards,
        "version": "fixture_reviewed_material_v1",
        "discipline": "communication",
        "source_kind": "reviewed_alternate",
    }
    preparation = assets.prepare_novelty_templates(
        prepared_dir,
        packs_dir=prep_packs,
        sources=[source],
        maximum_cycles=8,
    )
    prepared_path = prepared_dir / "ENGEL_TEMPLATE_NOVELTY_READY_COMMUNICATION.json"
    prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
    prepared_cycle = prepared["cycle_prompt_sets"][0]
    expected_second_prompts = assets.curriculum_prompts(
        alternate_cards[1], "communication"
    )[0]
    check(
        "preparation_excludes_used_card_and_preserves_novel_card",
        preparation["ok"] is True
        and preparation["prepared_template_count"] == 1
        and preparation["prepared_cycle_count"] == 1
        and prepared_cycle["prompts"] == expected_second_prompts
        and prepared_cycle["source_card_index"] == 2,
        json.dumps(preparation["templates"], sort_keys=True),
    )
    historical_prep_hashes = set(
        novelty.load_prompt_history(prep_packs)["history_prompt_hashes"]
    )
    prepared_hashes = set(prepared_cycle["base_prompt_hashes"])
    check(
        "prepared_cycle_is_hash_disjoint_and_material_bound",
        not historical_prep_hashes.intersection(prepared_hashes)
        and prepared_cycle["material_card_sha256"]
        == novelty.material_card_sha256(alternate_cards[1])
        and prepared.get("novelty_policy")
        == "whole reviewed material cards only; no nonce, suffix, or cosmetic prompt mutation",
        f"history={len(historical_prep_hashes)} prepared={len(prepared_hashes)}",
    )
    anchored_card = {
        **alternate_cards[1],
        "documents": ["grounded.pdf"],
        "evidence_anchors": [
            {"document": "grounded.pdf", "section": "1004.1"}
        ],
    }
    changed_anchor_card = {
        **anchored_card,
        "evidence_anchors": [
            {"document": "grounded.pdf", "section": "1004.2"}
        ],
    }
    check(
        "material_hash_binds_exact_documents_and_evidence_anchors",
        novelty.material_card_sha256(anchored_card)
        != novelty.material_card_sha256(changed_anchor_card),
        "changing an AEC evidence section changes the material identity",
    )
    default_source_ids = {
        str(item.get("id") or "")
        for item in assets.novelty_material_sources()[0]
    }
    check(
        "legacy_field_cards_are_not_offered_as_quote_bound_aec",
        "construction_field_alternate" not in default_source_ids,
        "legacy field-coordination prompts name no exact corpus document/edition",
    )

    adopted_path = work / "ENGEL_WEAKNESS_CURRICULUM_ADOPTED.json"
    original_adopted_path = assets.WEAKNESS_ADOPTED_PATH
    adopted_card = dict(alternate_cards[1])
    adopted_payload = {
        "schema": "engel_weakness_curriculum_v1",
        "adoption": "adopted",
        "adopted_at_utc": "2026-08-10T00:00:00Z",
        "cards": [adopted_card],
    }
    try:
        assets.WEAKNESS_ADOPTED_PATH = adopted_path
        adopted_payload["cards"][0]["artifacts"] = [
            str((TOOLS / "verify_engel_prompt_novelty.py").resolve())
        ]
        adopted_path.write_text(json.dumps(adopted_payload), encoding="utf-8")
        unsafe_source, unsafe_problems = assets._load_adopted_weakness_source()
        check(
            "adopted_weakness_rejects_absolute_artifact",
            unsafe_source is None
            and any("unsafe or missing" in item for item in unsafe_problems),
            repr(unsafe_problems),
        )
        adopted_payload["cards"][0]["artifacts"] = [
            "tools/verify_engel_prompt_novelty.py"
        ]
        adopted_path.write_text(json.dumps(adopted_payload), encoding="utf-8")
        safe_source, safe_problems = assets._load_adopted_weakness_source()
        records = (
            safe_source["cards"][0].get("_grounding_artifact_records", [])
            if safe_source
            else []
        )
        check(
            "adopted_weakness_binds_safe_artifact_bytes",
            not safe_problems
            and len(records) == 1
            and records[0]["path"] == "tools/verify_engel_prompt_novelty.py"
            and len(records[0]["sha256"]) == 64,
            json.dumps(records, sort_keys=True),
        )
    finally:
        assets.WEAKNESS_ADOPTED_PATH = original_adopted_path

    runner_source = (TOOLS / "run_engel_flutter_main_ui_prompt_training.py").read_text(
        encoding="utf-8"
    )
    run_start = runner_source.index("def _run_training_claimed(")
    run_end = runner_source.index("def _new_prompt_training_run_id(", run_start)
    run_body = runner_source[run_start:run_end]
    claim_helper_start = runner_source.index("def _run_cli_with_claim(")
    main_start = runner_source.index("def main() -> int:")
    main_body = runner_source[main_start:]
    claim_helper = runner_source[claim_helper_start:main_start]
    check(
        "runner_gate_precedes_all_training_side_effects",
        run_body.index("_require_session_preflight(session_preflight)")
        < run_body.index("ensure_dirs()")
        and main_body.index("_require_session_preflight(prepared_session_preflight)")
        < main_body.index("with acquire_prompt_run_claim(")
        and claim_helper.index("_require_session_preflight(claimed_preflight)")
        < claim_helper.index("_freshen_stale_gpu_server()"),
        "read-only check is repeated under the claim before UI or optional GPU work",
    )
    check(
        "one_claim_covers_full_cli_run_without_nesting",
        main_body.index("with acquire_prompt_run_claim(")
        < main_body.index("_run_cli_with_claim(")
        and "_execute_claimed_training(" in claim_helper
        and "run_training(" not in claim_helper
        and "prompt_run_claim.require_owner(run_id)" in claim_helper
        and "prompt_run_claim.require_owner(run_id)" in run_body,
        "CLI claim spans claimed novelty recheck, freshness, delivery, and pack publication",
    )
    check(
        "write_ahead_reservation_is_immediately_before_delivery",
        run_body.index("_reserve_scheduled_prompt_before_delivery(")
        < run_body.index("result = send_prompt_through_flutter(")
        and run_body[run_body.index("_reserve_scheduled_prompt_before_delivery(") :]
        .index("result = send_prompt_through_flutter(")
        > 0
        and "require_scheduled_prompt_novelty(delivery_preflight)" in runner_source
        and "publish_prompt_use_reservation(" in runner_source,
        "each scheduled prompt is atomically consumed after a fresh history read and directly before send",
    )
    check(
        "session_and_future_packs_bind_novelty_hashes",
        '"session_preflight": _receipt_session_preflight(session_preflight)' in runner_source
        and "canonical_base_prompt_sha256(base_prompt) if base_prompt else \"\""
        in runner_source
        and '"history_snapshot_sha256"' in runner_source
        and '"prompt_use_reservation": prompt_use_reservation' in runner_source
        and "_publish_immutable_training_pack(pack_path, body)" in runner_source,
        "session stores history/reservation proof and packs remain canonical and immutable",
    )
finally:
    shutil.rmtree(work, ignore_errors=True)


failed = [item for item in checks if item["status"] != "PASS"]
print(
    json.dumps(
        {
            "schema": "engel_prompt_novelty_verifier_v1",
            "status": "FAIL" if failed else "PASS",
            "passed": len(checks) - len(failed),
            "total": len(checks),
            "checks": checks,
        },
        indent=2,
        sort_keys=True,
    )
)
raise SystemExit(1 if failed else 0)
