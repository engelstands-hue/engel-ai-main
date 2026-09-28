#!/usr/bin/env python3
"""Behavioral proof that model training consumes one current pack from all five curricula."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import run_engel_real_training_cycle as cycle  # noqa: E402
import run_engel_flutter_main_ui_prompt_training as prompt_runner  # noqa: E402
import sync_engel_training_assets as assets  # noqa: E402


checks: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: object) -> None:
    checks.append((name, bool(condition), str(detail)))
    print(f"{'PASS' if condition else 'FAIL'} {name}: {detail}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_assets(root: Path) -> tuple[Path, Path, dict[str, dict[str, object]]]:
    templates = root / "templates"
    templates.mkdir(parents=True)
    bindings: list[dict[str, object]] = []
    by_id: dict[str, dict[str, object]] = {}
    for curriculum_id, title, discipline in cycle.CANONICAL_CURRICULA:
        version = f"{curriculum_id}_verified_v1"
        template = templates / f"ENGEL_TEMPLATE_{curriculum_id.upper()}.json"
        payload = {
            "schema": "engel_main_scheduled_prompt_training_template_v2",
            "material_version": version,
            "training_discipline": discipline,
            "maximum_scheduled_prompt_count": 80,
            "cycle_prompt_sets": [
                {
                    "prompts": [
                        f"{curriculum_id} hour {hour} prompt {number}"
                        for number in range(1, 11)
                    ]
                }
                for hour in range(1, 9)
            ],
        }
        write_json(template, payload)
        binding = {
            "id": curriculum_id,
            "title": title,
            "discipline": discipline,
            "version": version,
            "template_path": str(template.resolve()),
            "template_sha256": sha256(template),
            "prompt_count": 80,
            "maximum_hours": 8,
        }
        bindings.append(binding)
        by_id[curriculum_id] = binding
    index = templates / "curricula_index.json"
    write_json(
        index,
        {
            "schema": "engel_training_curricula_index_v1",
            "curriculum_count": 5,
            "total_prompts": 400,
            "all_curricula_ready": True,
            "curricula": [
                {
                    **binding,
                    "novelty_fully_ready": True,
                    "novel_hours_available": 8,
                }
                for binding in bindings
            ],
        },
    )
    manifest = root / "training_assets_manifest.json"
    write_json(
        manifest,
        {
            "schema": "engel_main_training_assets_manifest_v1",
            "ok": True,
            "asset_integrity_ok": True,
            "all_five_curricula_ready": True,
            "curriculum_bindings": bindings,
        },
    )
    return index, manifest, by_id


def row_for(
    binding: dict[str, object],
    number: int,
    *,
    run_id: str | None = None,
    session_start_index: int = 1,
    session_receipt: str = "fixture-session.json",
    session_receipt_sha256: str = "0" * 64,
    pack_receipt: str = "fixture-pack.receipt.json",
    writer_source_sha256: str = "0" * 64,
    training_targets: str = "slm,llm",
    training_level: str = "fellow",
) -> dict[str, object]:
    hour = (number - 1) // 10 + 1
    within_hour = (number - 1) % 10 + 1
    base = f"{binding['id']} hour {hour} prompt {within_hour}"
    delivered = "Training task:\n" + base
    return {
        "schema": cycle.PACK_ROW_SCHEMA,
        "run_id": run_id or str(binding["id"]),
        "created_at_utc": "2026-08-11T00:00:00Z",
        "session_receipt": session_receipt,
        "session_receipt_sha256": session_receipt_sha256,
        "pack_receipt": pack_receipt,
        "pack_writer_source_sha256": writer_source_sha256,
        "prompt_index": number,
        "discipline": binding["discipline"],
        "curriculum_template": binding["template_path"],
        "curriculum_id": binding["id"],
        "curriculum_title": binding["title"],
        "curriculum_material_version": binding["version"],
        "curriculum_template_path": binding["template_path"],
        "curriculum_template_sha256": binding["template_sha256"],
        "material_topic": f"topic {(number - 1) // 10 + 1}",
        "training_level": training_level,
        "training_targets": training_targets,
        "scheduled_hours": 8,
        "trainings_per_hour": 10,
        "session_start_index": session_start_index,
        "scheduled_hour": (number - 1) // 10 + 1,
        "base_prompt": base,
        "delivered_prompt": delivered,
        "assistant_reply": (
            "This is a substantive locally verified fixture answer with enough detail "
            "to remain above the minimum reply threshold for deterministic testing."
        ),
        "base_prompt_sha256": cycle.canonical_base_prompt_sha256(base),
        "base_prompt_hash_canonicalization": cycle.BASE_PROMPT_CANONICALIZATION,
        "prompt_sha256": hashlib.sha256(delivered.encode()).hexdigest(),
        "status": "DONE",
        "admit": True,
        "admit_reason": "fixture current policy admit",
        "training_sample_eligible": True,
        "discipline_eligibility_ok": True,
        "local_only_training": True,
        "selected_provider": "local",
        "response_kind": "chat",
        "action_lane_used": False,
        "contract_echo": False,
    }


def write_read_only(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        os.chmod(path, 0o600)
    path.write_bytes(body)
    os.chmod(path, 0o444)


def writer_curriculum_binding(binding: dict[str, object]) -> dict[str, object]:
    return {
        "schema": cycle.CURRICULUM_BINDING_SCHEMA,
        "curriculum_id": binding["id"],
        "curriculum_title": binding["title"],
        "discipline": binding["discipline"],
        "material_version": binding["version"],
        "template_path": binding["template_path"],
        "template_sha256": binding["template_sha256"],
    }


def write_pack(
    path: Path,
    binding: dict[str, object],
    count: int = 80,
    *,
    start_index: int = 1,
    training_targets: str = "slm,llm",
    training_level: str = "fellow",
    hourly_cycles: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    prefix = "ENGEL_PROMPT_TRAINING_PACK_"
    suffix = ".jsonl"
    if not path.name.startswith(prefix) or not path.name.endswith(suffix):
        raise ValueError(f"fixture pack name is not canonical: {path.name}")
    run_id = path.name[len(prefix) : -len(suffix)]
    receipt_path = path.with_suffix(cycle.PACK_RECEIPT_SUFFIX)
    session_path = path.parent / f"{cycle.PACK_SESSION_PREFIX}{run_id}.json"
    source = Path(prompt_runner.__file__).resolve(strict=True)
    source_bytes = source.read_bytes()
    writer = {
        "schema": cycle.PACK_WRITER_IDENTITY_SCHEMA,
        "run_id": run_id,
        "entrypoint": "write_training_pack",
        "source_relative_path": cycle.PROMPT_PACK_WRITER_RELATIVE_PATH,
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_bytes": len(source_bytes),
        "captured_at": "module_import",
        "completion_reverified": True,
    }
    cycles = hourly_cycles or [
        {
            "scheduled_hour": hour,
            "template_cycle": hour,
            "material_topic": f"{binding['id']} topic {hour}",
            "selected_prompt_count": 10,
            "source_prompt_count": 10,
            "source_prompt_positions": list(range(1, 11)),
            "trainings_per_hour": 10,
        }
        for hour in range(1, 9)
    ]
    session_body = {
        "schema": "engel_ui_prompt_training_session_v1",
        "run_id": run_id,
        "mode": "scheduled",
        "template_path": binding["template_path"],
        "curriculum_binding": writer_curriculum_binding(binding),
        "template_cycle": 1,
        "exact_template_cycle": True,
        "scheduled_hours": 8,
        "trainings_per_hour": 10,
        "start_index": start_index,
        "training_level": training_level,
        "training_targets": training_targets,
        "hourly_cycles": cycles,
        "prompt_results": [],
        "summary": {"training_discipline": binding["discipline"]},
        "status": "PASS",
        "blockers": [],
    }
    session_payload = {
        "schema": cycle.PACK_SESSION_EVIDENCE_SCHEMA,
        "run_id": run_id,
        "created_at_utc": "2026-08-11T00:00:00Z",
        "writer": writer,
        "session": session_body,
    }
    session_bytes = (
        json.dumps(session_payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode()
    write_read_only(session_path, session_bytes)
    session_sha256 = hashlib.sha256(session_bytes).hexdigest()
    numbers = list(range(start_index, start_index + count))
    rows = [
        row_for(
            binding,
            number,
            run_id=run_id,
            session_start_index=start_index,
            session_receipt=str(session_path.resolve()),
            session_receipt_sha256=session_sha256,
            pack_receipt=str(receipt_path.resolve()),
            writer_source_sha256=writer["source_sha256"],
            training_targets=training_targets,
            training_level=training_level,
        )
        for number in numbers
    ]
    pack_bytes = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    ).encode()
    write_read_only(path, pack_bytes)
    schedule = {
        "mode": "scheduled",
        "scheduled_hours": 8,
        "trainings_per_hour": 10,
        "session_start_index": start_index,
        "training_targets": training_targets,
        "training_level": training_level,
        "template_cycle": 1,
        "exact_template_cycle": True,
        "expected_plan_prompt_count": 80,
        "row_count": len(rows),
        "prompt_index_count": len(numbers),
        "prompt_index_min": min(numbers) if numbers else None,
        "prompt_index_max": max(numbers) if numbers else None,
        "global_prompt_indexes": numbers,
        "hourly_cycles": cycles,
    }
    receipt = {
        "schema": cycle.PACK_STAMPED_RECEIPT_SCHEMA,
        "run_id": run_id,
        "created_at_utc": "2026-08-11T00:00:00Z",
        "receipt_path": str(receipt_path.resolve()),
        "writer": writer,
        "pack": {
            "path": str(path.resolve()),
            "name": path.name,
            "sha256": hashlib.sha256(pack_bytes).hexdigest(),
            "bytes": len(pack_bytes),
            "rows": len(rows),
            "mode": "0444",
        },
        "session": {
            "path": str(session_path.resolve()),
            "name": session_path.name,
            "sha256": session_sha256,
            "bytes": len(session_bytes),
            "mode": "0444",
            "schema": cycle.PACK_SESSION_EVIDENCE_SCHEMA,
            "run_id": run_id,
        },
        "curriculum_binding": writer_curriculum_binding(binding),
        "schedule": schedule,
    }
    receipt_bytes = (
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    write_read_only(receipt_path, receipt_bytes)
    return {
        "path": path,
        "receipt_path": receipt_path,
        "session_path": session_path,
        "rows": rows,
        "pack_sha256": hashlib.sha256(pack_bytes).hexdigest(),
        "receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "session_sha256": session_sha256,
    }


def fake_assess(row: dict[str, object], **_: object) -> dict[str, object]:
    required = cycle.training_dataset.PACK_REQUIRED_FIELDS
    if not required.issubset(row):
        return {"disposition": "exclude", "reason": "missing required fixture field"}
    return {"disposition": "admit", "reason": "fixture current policy admit"}


def restore_writable(root: Path) -> None:
    for path in root.rglob("*"):
        try:
            os.chmod(path, 0o700 if path.is_dir() else 0o600)
        except OSError:
            pass


def main() -> int:
    runtime_temp = ROOT / "runtime" / "temp"
    runtime_temp.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="five_curriculum_handoff_", dir=runtime_temp))
    saved = {
        "PACK_DIR": cycle.PACK_DIR,
        "QUARANTINE_DIR": cycle.QUARANTINE_DIR,
        "CURRICULA_INDEX_PATH": cycle.CURRICULA_INDEX_PATH,
        "TRAINING_ASSET_MANIFEST_PATH": cycle.TRAINING_ASSET_MANIFEST_PATH,
        "REPORT_DIR": cycle.REPORT_DIR,
    }
    try:
        stable_template = temp / "stable_template.json"
        first_payload = {"updated_at_utc": "first", "material": {"value": 1}}
        assets.safe_write_stable_template(stable_template, first_payload)
        stable_bytes = stable_template.read_bytes()
        assets.safe_write_stable_template(
            stable_template,
            {"updated_at_utc": "second", "material": {"value": 1}},
        )
        no_op_bytes = stable_template.read_bytes()
        assets.safe_write_stable_template(
            stable_template,
            {"updated_at_utc": "third", "material": {"value": 2}},
        )
        changed_bytes = stable_template.read_bytes()
        check(
            "no_op_sync_preserves_campaign_template_bytes",
            stable_bytes == no_op_bytes and changed_bytes != stable_bytes,
            {
                "stable_sha256": hashlib.sha256(stable_bytes).hexdigest(),
                "changed_sha256": hashlib.sha256(changed_bytes).hexdigest(),
            },
        )

        index, manifest, bindings = build_assets(temp / "assets")
        packs = temp / "packs"
        quarantines = temp / "quarantines"
        reports = temp / "reports"
        packs.mkdir()
        quarantines.mkdir()
        reports.mkdir()
        cycle.PACK_DIR = packs
        cycle.QUARANTINE_DIR = quarantines
        cycle.CURRICULA_INDEX_PATH = index
        cycle.TRAINING_ASSET_MANIFEST_PATH = manifest
        cycle.REPORT_DIR = reports

        contract = cycle.load_current_curriculum_contract(index, manifest)
        check("exact_five_asset_contract_passes", contract["ok"], contract["errors"])

        probed_template = Path(str(bindings["capabilities"]["template_path"])).resolve()
        original_read_bytes = Path.read_bytes
        template_reads = {"count": 0}

        def swap_after_first_template_read(path: Path) -> bytes:
            if path.resolve() == probed_template:
                template_reads["count"] += 1
                if template_reads["count"] > 1:
                    return b'{"schema":"hostile_second_read"}\n'
            return original_read_bytes(path)

        with mock.patch.object(
            Path,
            "read_bytes",
            swap_after_first_template_read,
        ):
            same_buffer_contract = cycle.load_current_curriculum_contract(
                index,
                manifest,
            )
        check(
            "curriculum_template_hash_and_parse_share_one_buffer",
            same_buffer_contract["ok"] is True
            and template_reads["count"] == 1,
            {
                "template_reads": template_reads["count"],
                "errors": same_buffer_contract["errors"],
            },
        )

        sample = row_for(bindings["capabilities"], 1)
        sample.pop("discipline_eligibility_ok")
        real_assessment = cycle.training_dataset.assess_prompt_training_pack_row(sample)
        check(
            "cycle_and_builder_share_missing_discipline_verdict",
            cycle.contract_admit(sample)[0] is False
            and real_assessment["disposition"] != "admit",
            real_assessment,
        )

        write_pack(packs / "ENGEL_PROMPT_TRAINING_PACK_capabilities.jsonl", bindings["capabilities"])
        with mock.patch.object(
            cycle.training_dataset,
            "assess_prompt_training_pack_row",
            side_effect=fake_assess,
        ):
            one = cycle.collect_current_five_packs(
                0, True, "slm,llm", index_path=index, manifest_path=manifest
            )
            check(
                "one_current_pack_cannot_train_models",
                one["curriculum_coverage"]["ok"] is False
                and one["curriculum_coverage"]["covered_curriculum_ids"] == ["capabilities"],
                one["curriculum_coverage"]["covered_curriculum_ids"],
            )

            index_payload = json.loads(index.read_text(encoding="utf-8"))
            index_payload["all_curricula_ready"] = False
            for item in index_payload["curricula"]:
                if item["id"] == "capabilities":
                    item["novelty_fully_ready"] = False
                    item["novel_hours_available"] = 0
            write_json(index, index_payload)
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_payload["all_five_curricula_ready"] = False
            write_json(manifest, manifest_payload)
            post_first_contract = cycle.load_current_curriculum_contract(
                index, manifest
            )
            original_runner_index = prompt_runner.CURRICULA_INDEX_PATH
            try:
                prompt_runner.CURRICULA_INDEX_PATH = index
                remaining_binding = prompt_runner._load_canonical_curriculum_binding(
                    str(bindings["math_school"]["template_path"])
                )
                try:
                    prompt_runner._load_canonical_curriculum_binding(
                        str(bindings["capabilities"]["template_path"])
                    )
                    consumed_refused = False
                except RuntimeError:
                    consumed_refused = True
            finally:
                prompt_runner.CURRICULA_INDEX_PATH = original_runner_index
            check(
                "first_pack_then_resync_keeps_remaining_campaign_runnable",
                post_first_contract["ok"] is True
                and remaining_binding["curriculum_id"] == "math_school"
                and consumed_refused,
                {
                    "contract_errors": post_first_contract["errors"],
                    "remaining": remaining_binding["curriculum_id"],
                    "consumed_refused": consumed_refused,
                },
            )

            capabilities_pack = (
                packs / "ENGEL_PROMPT_TRAINING_PACK_CAPABILITIES.jsonl"
            )
            loaded_race = cycle.prompt_quarantine.load_pack(
                capabilities_pack, cycle.QUARANTINE_DIR
            )
            loaded_race["pack_sha256"] = "0" * 64
            with mock.patch.object(
                cycle.prompt_quarantine, "load_pack", return_value=loaded_race
            ):
                raced_summary = cycle.validate_pack(
                    capabilities_pack,
                    "slm,llm",
                    curriculum_binding=post_first_contract["bindings_by_id"][
                        "capabilities"
                    ],
                )
            check(
                "pack_hash_change_during_validation_blocks_coverage",
                raced_summary["coverage_eligible"] is False
                and "pack bytes changed while they were being validated"
                in raced_summary["quarantine_blockers"],
                raced_summary["quarantine_blockers"],
            )

            for curriculum_id, _, _ in cycle.CANONICAL_CURRICULA[1:]:
                write_pack(
                    packs / f"ENGEL_PROMPT_TRAINING_PACK_{curriculum_id}.jsonl",
                    bindings[curriculum_id],
                )
            complete = cycle.collect_current_five_packs(
                0, True, "slm,llm", index_path=index, manifest_path=manifest
            )
            check(
                "five_complete_current_packs_pass",
                complete["curriculum_coverage"]["ok"] is True
                and complete["files"] == 5
                and complete["rows"] == 400,
                {
                    "files": complete["files"],
                    "rows": complete["rows"],
                    "covered": complete["curriculum_coverage"]["covered_curriculum_ids"],
                },
            )
            check(
                "every_selected_lane_has_each_curriculum",
                all(
                    item["admitted_by_target"].get("slm", 0) > 0
                    and item["admitted_by_target"].get("llm", 0) > 0
                    for item in complete["curriculum_coverage"]["items"]
                ),
                complete["admitted_by_target"],
            )
            check(
                "operational_counts_equal_shared_assessment",
                complete["admitted"] == 400
                and complete["admitted_by_target"] == {"slm": 400, "llm": 400},
                complete["admitted_by_target"],
            )

            # A recovery launch emits a second immutable physical pack. Prove that the
            # model hand-off treats the two receipts as one exact logical 1..80 chain,
            # while transferring every physical source and authority file.
            resume_packs = temp / "resume_packs"
            resume_packs.mkdir()
            cycle.PACK_DIR = resume_packs
            try:
                first_segment = write_pack(
                    resume_packs
                    / "ENGEL_PROMPT_TRAINING_PACK_capabilities_resume_a.jsonl",
                    bindings["capabilities"],
                    28,
                    start_index=1,
                )
                second_segment = write_pack(
                    resume_packs
                    / "ENGEL_PROMPT_TRAINING_PACK_capabilities_resume_b.jsonl",
                    bindings["capabilities"],
                    52,
                    start_index=29,
                )
                for curriculum_id, _, _ in cycle.CANONICAL_CURRICULA[1:]:
                    write_pack(
                        resume_packs
                        / f"ENGEL_PROMPT_TRAINING_PACK_{curriculum_id}_resume.jsonl",
                        bindings[curriculum_id],
                    )
                resumed = cycle.collect_current_five_packs(
                    0,
                    True,
                    "slm,llm",
                    index_path=index,
                    manifest_path=manifest,
                )
                resumed_capabilities = next(
                    item
                    for item in resumed["selected"]
                    if item["curriculum_id"] == "capabilities"
                )
                check(
                    "interrupted_then_resumed_chain_covers_exact_five",
                    resumed["curriculum_coverage"]["ok"] is True
                    and resumed["files"] == 6
                    and resumed["physical_rows"] == 400
                    and resumed["logical_rows"] == 400
                    and resumed_capabilities["segment_count"] == 2
                    and resumed_capabilities["segment_prompt_indexes"]
                    == list(range(1, 81)),
                    {
                        "files": resumed["files"],
                        "physical_rows": resumed["physical_rows"],
                        "logical_rows": resumed["logical_rows"],
                        "segments": resumed_capabilities["segment_count"],
                    },
                )
                descriptor = resumed_capabilities["segment_chain"]
                check(
                    "segment_chain_hash_binds_pack_receipt_and_session_evidence",
                    resumed_capabilities["segment_chain_sha256"]
                    == cycle.canonical_json_sha256(descriptor)
                    and len(descriptor["segments"]) == 2
                    and all(
                        segment["sha256"]
                        and segment["pack_receipt"]["sha256"]
                        and segment["session_evidence"]["sha256"]
                        for segment in descriptor["segments"]
                    ),
                    descriptor,
                )

                current_binding = post_first_contract["bindings_by_id"][
                    "capabilities"
                ]
                strict_first = cycle.validate_pack(
                    first_segment["path"],
                    "slm,llm",
                    current_binding,
                )
                strict_second = cycle.validate_pack(
                    second_segment["path"],
                    "slm,llm",
                    current_binding,
                )
                check(
                    "partial_segment_never_counts_alone",
                    strict_first["segment_eligible"] is True
                    and strict_first["coverage_eligible"] is False
                    and cycle.complete_segment_chains([strict_first]) == [],
                    strict_first["coverage_problems"],
                )

                gap = write_pack(
                    resume_packs
                    / "ENGEL_PROMPT_TRAINING_PACK_capabilities_gap.jsonl",
                    bindings["capabilities"],
                    51,
                    start_index=30,
                )
                overlap = write_pack(
                    resume_packs
                    / "ENGEL_PROMPT_TRAINING_PACK_capabilities_overlap.jsonl",
                    bindings["capabilities"],
                    53,
                    start_index=28,
                )
                drift = write_pack(
                    resume_packs
                    / "ENGEL_PROMPT_TRAINING_PACK_capabilities_schedule_drift.jsonl",
                    bindings["capabilities"],
                    52,
                    start_index=29,
                    training_level="expert",
                )
                strict_gap = cycle.validate_pack(
                    gap["path"], "slm,llm", current_binding
                )
                strict_overlap = cycle.validate_pack(
                    overlap["path"], "slm,llm", current_binding
                )
                strict_drift = cycle.validate_pack(
                    drift["path"], "slm,llm", current_binding
                )
                check(
                    "segment_gap_overlap_and_schedule_drift_are_refused",
                    not cycle.complete_segment_chains(
                        [strict_first, strict_gap]
                    )
                    and not cycle.complete_segment_chains(
                        [strict_first, strict_overlap]
                    )
                    and not cycle.complete_segment_chains(
                        [strict_first, strict_drift]
                    ),
                    {
                        "gap": strict_gap["segment_prompt_indexes"][:2],
                        "overlap": strict_overlap["segment_prompt_indexes"][:2],
                        "schedule_hashes": [
                            strict_first["schedule_identity_sha256"],
                            strict_drift["schedule_identity_sha256"],
                        ],
                    },
                )

                cap_transfer = cycle.selected_pack_transfer_plan(
                    {"selected": [resumed_capabilities]}
                )
                copied_argv: list[list[str]] = []
                remote_dir = "/opt/engel/run/fixture/packs"
                remote_hashes = {
                    f"{remote_dir}/{Path(entry['path']).name}": entry["sha256"]
                    for entry in cap_transfer["receipt"]
                }

                def capture_copy(argv: list[str], _: float) -> dict[str, object]:
                    copied_argv.append(list(argv))
                    return {
                        "ok": True,
                        "stdout": "",
                        "stderr": "",
                        "returncode": 0,
                    }

                transfer_receipt = {"steps": [], "blockers": [], "warnings": []}
                with mock.patch.object(
                    cycle,
                    "ssh_run",
                    return_value={
                        "ok": True,
                        "stdout": "",
                        "stderr": "",
                        "returncode": 0,
                    },
                ), mock.patch.object(
                    cycle,
                    "run_local",
                    side_effect=capture_copy,
                ), mock.patch.object(
                    cycle,
                    "remote_sha256",
                    return_value={"ok": True, "hashes": remote_hashes},
                ):
                    resume_transfer_ok = cycle.push_files(
                        transfer_receipt,
                        {"target": "fixture"},
                        "push_packs",
                        cap_transfer["paths"],
                        remote_dir,
                        expected_hashes=cap_transfer["expected_hashes"],
                        batch_copy=True,
                    )
                copied_sources = set(copied_argv[0][:-1]) if copied_argv else set()
                expected_sources = {
                    str(path) for path in cap_transfer["paths"]
                }
                check(
                    "resume_transfer_batches_two_packs_two_receipts_two_sessions",
                    resume_transfer_ok is True
                    and cap_transfer["segment_count"] == 2
                    and cap_transfer["evidence_file_count"] == 4
                    and len(cap_transfer["paths"]) == 6
                    and len(copied_argv) == 1
                    and expected_sources.issubset(copied_sources)
                    and all(str(path) not in {"", "."} for path in cap_transfer["paths"]),
                    {
                        "paths": [str(path) for path in cap_transfer["paths"]],
                        "copy_calls": len(copied_argv),
                    },
                )

                drift_path = Path(
                    resumed_capabilities["segments"][1]["pack_receipt_path"]
                )
                original_drift_bytes = drift_path.read_bytes()
                os.chmod(drift_path, 0o600)
                drift_path.write_bytes(original_drift_bytes + b" ")
                os.chmod(drift_path, 0o444)
                remote_attempts = {"count": 0}

                def unexpected_remote(*_: object, **__: object) -> dict[str, object]:
                    remote_attempts["count"] += 1
                    return {
                        "ok": True,
                        "stdout": "",
                        "stderr": "",
                        "returncode": 0,
                    }

                drift_receipt = {"steps": [], "blockers": [], "warnings": []}
                with mock.patch.object(
                    cycle,
                    "ssh_run",
                    side_effect=unexpected_remote,
                ), mock.patch.object(
                    cycle,
                    "run_local",
                    side_effect=unexpected_remote,
                ):
                    drift_transfer_ok = cycle.push_files(
                        drift_receipt,
                        {"target": "fixture"},
                        "push_packs",
                        cap_transfer["paths"],
                        remote_dir,
                        expected_hashes=cap_transfer["expected_hashes"],
                        batch_copy=True,
                    )
                check(
                    "receipt_drift_blocks_before_any_remote_action",
                    drift_transfer_ok is False
                    and remote_attempts["count"] == 0,
                    {
                        "remote_attempts": remote_attempts["count"],
                        "blockers": drift_receipt["blockers"],
                    },
                )
                os.chmod(drift_path, 0o600)
                drift_path.write_bytes(original_drift_bytes)
                os.chmod(drift_path, 0o444)

                latest_full = write_pack(
                    resume_packs
                    / "ENGEL_PROMPT_TRAINING_PACK_capabilities_zz_latest_full.jsonl",
                    bindings["capabilities"],
                )
                newest = cycle.collect_current_five_packs(
                    0,
                    True,
                    "slm,llm",
                    index_path=index,
                    manifest_path=manifest,
                )
                newest_capabilities = next(
                    item
                    for item in newest["selected"]
                    if item["curriculum_id"] == "capabilities"
                )
                check(
                    "newest_complete_chain_is_selected_deterministically",
                    newest_capabilities["segment_count"] == 1
                    and newest_capabilities["path"]
                    == str(latest_full["path"]),
                    {
                        "segment_count": newest_capabilities["segment_count"],
                        "path": newest_capabilities["path"],
                    },
                )
            finally:
                cycle.PACK_DIR = packs

            substituted = packs / "ENGEL_PROMPT_TRAINING_PACK_capabilities.jsonl"
            os.chmod(substituted, 0o600)
            substituted_rows = [
                json.loads(line)
                for line in substituted.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            substituted_base = "copied metadata around unrelated prompt content"
            substituted_rows[0]["base_prompt"] = substituted_base
            substituted_rows[0]["base_prompt_sha256"] = (
                cycle.canonical_base_prompt_sha256(substituted_base)
            )
            substituted_rows[0]["delivered_prompt"] = (
                "Training task:\n" + substituted_base
            )
            substituted_rows[0]["prompt_sha256"] = hashlib.sha256(
                substituted_rows[0]["delivered_prompt"].encode()
            ).hexdigest()
            substituted.write_text(
                "".join(
                    json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                    for row in substituted_rows
                ),
                encoding="utf-8",
            )
            os.chmod(substituted, 0o444)
            selected_capabilities = next(
                item
                for item in complete["selected"]
                if item["curriculum_id"] == "capabilities"
            )
            remote_attempts = {"count": 0}

            def count_remote(*_: object, **__: object) -> dict[str, object]:
                remote_attempts["count"] += 1
                return {"ok": True, "stdout": "", "stderr": "", "returncode": 0}

            transfer_receipt = {"steps": [], "blockers": [], "warnings": []}
            with mock.patch.object(
                cycle, "ssh_run", side_effect=count_remote
            ), mock.patch.object(cycle, "run_local", side_effect=count_remote):
                transferred = cycle.push_files(
                    transfer_receipt,
                    {"target": "fixture"},
                    "push_packs",
                    [substituted],
                    "/opt/engel/run/fixture/packs",
                    expected_hashes={
                        str(substituted.resolve()): selected_capabilities[
                            "pack_sha256"
                        ]
                    },
                )
            check(
                "pack_mutation_after_selection_blocks_before_remote_copy",
                transferred is False and remote_attempts["count"] == 0,
                {
                    "remote_attempts": remote_attempts["count"],
                    "blockers": transfer_receipt["blockers"],
                },
            )
            substituted_result = cycle.collect_current_five_packs(
                0, True, "slm,llm", index_path=index, manifest_path=manifest
            )
            check(
                "copied_binding_cannot_substitute_prompt_content",
                substituted_result["curriculum_coverage"]["ok"] is False
                and "capabilities"
                not in substituted_result["curriculum_coverage"][
                    "covered_curriculum_ids"
                ],
                substituted_result["curriculum_coverage"]["covered_curriculum_ids"],
            )
            os.chmod(substituted, 0o600)
            write_pack(substituted, bindings["capabilities"])

            bad = packs / "ENGEL_PROMPT_TRAINING_PACK_math_school.jsonl"
            os.chmod(bad, 0o600)
            write_pack(bad, bindings["math_school"], 79)
            incomplete = cycle.collect_current_five_packs(
                0, True, "slm,llm", index_path=index, manifest_path=manifest
            )
            check(
                "seventy_nine_row_pack_is_refused",
                incomplete["curriculum_coverage"]["ok"] is False
                and "math_school"
                not in incomplete["curriculum_coverage"]["covered_curriculum_ids"],
                incomplete["curriculum_coverage"]["covered_curriculum_ids"],
            )

            remote_calls = {"count": 0}
            original_resolve = cycle.step_resolve_ct_python

            def forbidden_remote(*_: object, **__: object) -> str:
                remote_calls["count"] += 1
                raise AssertionError("remote resolution occurred before all-five coverage")

            cycle.step_resolve_ct_python = forbidden_remote
            try:
                with mock.patch.object(
                    cycle,
                    "inspect_construction_corpus_bundle",
                    return_value={
                        "ok": True,
                        "mode": "empty",
                        "files": [],
                        "bundle_sha256": "",
                        "blockers": [],
                        "local_root": str(temp / "corpus"),
                        "ct_root": "/tmp/corpus",
                    },
                ):
                    receipt = cycle.run_cycle(
                        SimpleNamespace(
                            since_hours=0,
                            all=True,
                            targets="slm",
                            dry_run=False,
                            no_ct=False,
                        )
                    )
            finally:
                cycle.step_resolve_ct_python = original_resolve
            check(
                "coverage_block_precedes_every_remote_call",
                remote_calls["count"] == 0
                and receipt["status"] == "FAIL"
                and any(
                    step["step"] == "remote_cycle_aborted" for step in receipt["steps"]
                ),
                {"remote_calls": remote_calls["count"], "status": receipt["status"]},
            )

        template = Path(str(bindings["self_build"]["template_path"]))
        template.write_text(template.read_text(encoding="utf-8") + " ", encoding="utf-8")
        drift = cycle.load_current_curriculum_contract(index, manifest)
        check(
            "template_byte_drift_invalidates_current_contract",
            drift["ok"] is False
            and any("template bytes" in error for error in drift["errors"]),
            drift["errors"],
        )
    finally:
        for name, value in saved.items():
            setattr(cycle, name, value)
        cycle._ACTIVE_CYCLE_DEADLINE_MONOTONIC = None
        restore_writable(temp)
        shutil.rmtree(temp, ignore_errors=True)

    failed = [name for name, ok, _ in checks if not ok]
    print(f"SUMMARY {len(checks) - len(failed)}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
