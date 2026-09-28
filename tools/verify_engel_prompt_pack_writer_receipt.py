#!/usr/bin/env python3
"""Verify the prompt runner's immutable session -> pack -> writer receipt chain.

This verifier is local-only. It creates synthetic canonical assets and prompt results in
an isolated workspace directory; it never opens Engel Main, contacts CT246, or loads a
model.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import run_engel_flutter_main_ui_prompt_training as runner  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def immutable_regular(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    return (
        stat.S_ISREG(info.st_mode)
        and not path.is_symlink()
        and not bool(info.st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    )


def build_assets(root: Path) -> tuple[Path, dict[str, Any], list[str]]:
    templates = root / "templates"
    templates.mkdir(parents=True)
    curricula: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    prompts_by_id: dict[str, list[str]] = {}
    for curriculum_id, title, discipline in runner.CANONICAL_CURRICULA:
        ordered_prompts: list[str] = []
        cycles: list[dict[str, Any]] = []
        for hour in range(1, 9):
            prompts = [
                f"{curriculum_id} hour {hour} prompt {within_hour}"
                for within_hour in range(1, 11)
            ]
            ordered_prompts.extend(prompts)
            cycles.append(
                {
                    "cycle": hour,
                    "scheduled_hour": hour,
                    "material_topic": f"{curriculum_id} topic {hour}",
                    "prompts": prompts,
                }
            )
        template = templates / f"{curriculum_id}.json"
        payload = {
            "material_version": f"{curriculum_id}_v1",
            "training_discipline": discipline,
            "maximum_scheduled_prompt_count": 80,
            "scheduled_controls": {"maximum_hours": 8},
            "cycle_prompt_sets": cycles,
        }
        template.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        binding = {
            "id": curriculum_id,
            "title": title,
            "discipline": discipline,
            "version": payload["material_version"],
            "template_path": str(template.resolve()),
            "template_sha256": sha256(template),
            "prompt_count": 80,
            "maximum_hours": 8,
            "novelty_fully_ready": True,
            "novel_hours_available": 8,
        }
        curricula.append(binding)
        by_id[curriculum_id] = binding
        prompts_by_id[curriculum_id] = ordered_prompts
    index = templates / "curricula_index.json"
    index.write_text(
        json.dumps(
            {
                "schema": "engel_training_curricula_index_v1",
                "curriculum_count": 5,
                "total_prompts": 400,
                "curricula": curricula,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return index, by_id["capabilities"], prompts_by_id["capabilities"]


def prompt_results(prompts: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for prompt_index, base_prompt in enumerate(prompts, start=1):
        reply = (
            f"Verified response for canonical item {prompt_index}: {base_prompt}. "
            f"The local evidence for item {prompt_index} was checked independently, "
            "and this distinct explanation records the outcome without using an action lane."
        )
        results.append(
            {
                "prompt_index": prompt_index,
                "scheduled_hour": ((prompt_index - 1) // 10) + 1,
                "material_topic": f"capabilities topic {((prompt_index - 1) // 10) + 1}",
                "training_level": "expert",
                "base_prompt": base_prompt,
                "delivered_prompt": (
                    "Expert training depth.\n\nTraining task:\n" + base_prompt
                ),
                "wrapper_receipt": {"assistant_reply": reply},
                "status": "DONE",
                "discipline": "engineering",
                "training_sample_eligible": True,
                "discipline_eligibility_ok": True,
                "local_only_training": True,
                "selected_provider": "local",
                "provider_bridge_used": False,
                "provider_api_enabled": False,
                "creation_job": False,
                "chat_only_no_android_or_sub_engel": True,
                "agent_meeting_room_used": False,
                "workspace_path": "",
            }
        )
    return results


def validate_chain(output: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    pack_path = Path(str(output.get("pack_path") or ""))
    receipt_path = Path(str(output.get("stamped_pack_receipt") or ""))
    session_path = Path(str(output.get("session_receipt") or ""))
    for label, path in (
        ("pack", pack_path),
        ("stamped receipt", receipt_path),
        ("session evidence", session_path),
    ):
        if not immutable_regular(path):
            problems.append(f"{label} is not an immutable regular file")
    try:
        stamped = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
        session = json.loads(session_path.read_text(encoding="utf-8-sig"))
        rows = [
            json.loads(line)
            for line in pack_path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
    except (OSError, ValueError, TypeError) as exc:
        return problems + [f"chain could not be parsed: {exc}"]
    if stamped.get("schema") != runner.PACK_STAMPED_RECEIPT_SCHEMA:
        problems.append("stamped receipt schema drifted")
    if session.get("schema") != runner.PACK_SESSION_EVIDENCE_SCHEMA:
        problems.append("session evidence schema drifted")
    if stamped.get("run_id") != output.get("run_id"):
        problems.append("receipt run id differs")
    pack = stamped.get("pack") if isinstance(stamped.get("pack"), dict) else {}
    if (
        pack.get("path") != str(pack_path.resolve())
        or pack.get("name") != pack_path.name
        or pack.get("sha256") != sha256(pack_path)
        or pack.get("bytes") != pack_path.stat().st_size
        or pack.get("rows") != len(rows)
    ):
        problems.append("pack bytes/path/row binding differs")
    bound_session = (
        stamped.get("session") if isinstance(stamped.get("session"), dict) else {}
    )
    if (
        bound_session.get("path") != str(session_path.resolve())
        or bound_session.get("sha256") != sha256(session_path)
        or bound_session.get("bytes") != session_path.stat().st_size
        or bound_session.get("run_id") != output.get("run_id")
    ):
        problems.append("session bytes/path/run binding differs")
    writer = stamped.get("writer") if isinstance(stamped.get("writer"), dict) else {}
    source = Path(str(writer.get("source_path") or ""))
    if (
        writer.get("schema") != runner.PACK_WRITER_IDENTITY_SCHEMA
        or writer.get("run_id") != output.get("run_id")
        or source.resolve() != Path(runner.__file__).resolve()
        or writer.get("source_sha256") != sha256(source)
        or writer.get("source_bytes") != source.stat().st_size
    ):
        problems.append("writer source identity differs")
    schedule = (
        stamped.get("schedule") if isinstance(stamped.get("schedule"), dict) else {}
    )
    if (
        schedule.get("scheduled_hours") != 8
        or schedule.get("trainings_per_hour") != 10
        or schedule.get("session_start_index") != 1
        or schedule.get("row_count") != 80
        or schedule.get("global_prompt_indexes") != list(range(1, 81))
    ):
        problems.append("schedule/index binding differs")
    for row in rows:
        if (
            row.get("run_id") != output.get("run_id")
            or row.get("session_receipt") != str(session_path.resolve())
            or row.get("session_receipt_sha256") != sha256(session_path)
            or row.get("pack_receipt") != str(receipt_path.resolve())
            or row.get("pack_writer_source_sha256") != writer.get("source_sha256")
        ):
            problems.append("a row differs from the evidence-chain binding")
            break
    return problems


def make_session(
    binding: dict[str, Any], prompts: list[str], run_id: str
) -> dict[str, Any]:
    current_binding = {
        "schema": runner.CURRICULUM_BINDING_SCHEMA,
        "curriculum_id": binding["id"],
        "curriculum_title": binding["title"],
        "discipline": binding["discipline"],
        "material_version": binding["version"],
        "template_path": binding["template_path"],
        "template_sha256": binding["template_sha256"],
    }
    return {
        "schema": "engel_ui_prompt_training_session_v1",
        "run_id": run_id,
        "mode": "scheduled",
        "template_path": binding["template_path"],
        "curriculum_binding": current_binding,
        "template_cycle": 1,
        "exact_template_cycle": True,
        "scheduled_hours": 8,
        "trainings_per_hour": 10,
        "start_index": 1,
        "training_level": "expert",
        "training_targets": "slm,llm",
        "hourly_cycles": [
            {
                "scheduled_hour": hour,
                "template_cycle": hour,
                "material_topic": f"capabilities topic {hour}",
                "selected_prompt_count": 10,
            }
            for hour in range(1, 9)
        ],
        "prompt_results": prompt_results(prompts),
        "summary": {"training_discipline": "engineering"},
        "status": "PASS",
        "blockers": [],
    }


def main() -> int:
    temp_parent = ROOT / "runtime" / "temp"
    temp_parent.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(
        prefix="engel_pack_writer_receipt_",
        dir=str(temp_parent),
    ) as temp_name:
        temp = Path(temp_name)
        index, binding, prompts = build_assets(temp / "assets")
        packs = temp / "packs"
        original_pack_dir = runner.PACKS_DIR
        original_index = runner.CURRICULA_INDEX_PATH
        original_prediction = runner._slm_admit_prediction
        try:
            writer_copy = temp / "writer_source_copy.py"
            writer_copy.write_bytes(b"writer-source-A\n")
            captured_writer = runner._capture_pack_writer_source(writer_copy)
            # Same byte count closes the easy loophole where a verifier checks only size.
            writer_copy.write_bytes(b"writer-source-B\n")
            writer_mutation_refused = False
            try:
                runner._pack_writer_identity(
                    "writer_receipt_fixture_run_001",
                    source_snapshot=captured_writer,
                )
            except RuntimeError as exc:
                writer_mutation_refused = "changed after module import" in str(exc)
            checks.append(
                {
                    "name": "loaded_writer_identity_refuses_a_to_b_source_swap",
                    "ok": writer_mutation_refused,
                }
            )

            runner.PACKS_DIR = packs
            runner.CURRICULA_INDEX_PATH = index
            runner._slm_admit_prediction = lambda _prompt, _reply: None
            run_id = "writer_receipt_fixture_run_001"
            session = make_session(binding, prompts, run_id)
            output = runner.write_training_pack(session)
            problems = validate_chain(output)
            checks.append(
                {
                    "name": "immutable_writer_session_pack_chain",
                    "ok": not problems,
                    "detail": problems,
                }
            )

            overwrite_refused = False
            try:
                runner.write_training_pack(session)
            except RuntimeError as exc:
                overwrite_refused = "overwrite" in str(exc)
            checks.append(
                {
                    "name": "stamped_chain_is_no_overwrite",
                    "ok": overwrite_refused,
                }
            )

            latest = Path(str(output["latest_receipt_path"]))
            latest.write_text('{"status_alias_only":true}\n', encoding="utf-8")
            checks.append(
                {
                    "name": "mutable_latest_is_not_chain_authority",
                    "ok": not validate_chain(output),
                }
            )

            receipt_path = Path(str(output["stamped_pack_receipt"]))
            original_receipt = receipt_path.read_bytes()
            tampered = json.loads(original_receipt.decode("utf-8"))
            tampered["pack"]["sha256"] = "0" * 64
            os.chmod(receipt_path, 0o600)
            receipt_path.write_text(
                json.dumps(tampered, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.chmod(receipt_path, 0o444)
            checks.append(
                {
                    "name": "receipt_pack_binding_tamper_is_detected",
                    "ok": bool(validate_chain(output)),
                }
            )
            os.chmod(receipt_path, 0o600)
            receipt_path.write_bytes(original_receipt)
            os.chmod(receipt_path, 0o444)
        finally:
            runner.PACKS_DIR = original_pack_dir
            runner.CURRICULA_INDEX_PATH = original_index
            runner._slm_admit_prediction = original_prediction
            for path in temp.rglob("*"):
                if path.is_file():
                    try:
                        os.chmod(path, 0o600)
                    except OSError:
                        pass

    failed = [check for check in checks if not check.get("ok")]
    print(
        json.dumps(
            {
                "schema": "engel_prompt_pack_writer_receipt_verification_v1",
                "status": "PASS" if not failed else "FAIL",
                "passed": len(checks) - len(failed),
                "total": len(checks),
                "checks": checks,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
