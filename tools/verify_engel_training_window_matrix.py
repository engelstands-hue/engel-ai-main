#!/usr/bin/env python3
"""Exhaustively verify every Training-window schedule and model-target contract.

This is a plan-only verifier. It proves that every curriculum, duration (1-8),
level, hourly frequency, and supported target selection produces a complete,
distinct schedule and a reachable trainer plan without spending eight hours or
rewriting model weights during CI.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for item in (ROOT, TOOLS):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import engel_ui_prompt_training_support as support  # noqa: E402
import run_engel_flutter_main_ui_prompt_training as prompt_runner  # noqa: E402
import run_engel_real_training_cycle as model_cycle  # noqa: E402


INDEX = (
    ROOT
    / "memory"
    / "training"
    / "engel_main"
    / "templates"
    / "curricula_index.json"
)
LAUNCHER = (
    ROOT / "memory" / "training" / "engel_main" / "run_hour_prompt_training.ps1"
)
FLUTTER_UI = ROOT / "engel_flutter_main" / "lib" / "main.dart"
TRAINING_SECTION = ROOT / "engel_flutter_main" / "lib" / "training_section.dart"
PROMPT_RUNNER = TOOLS / "run_engel_flutter_main_ui_prompt_training.py"
TARGET_CHOICES = ("slm", "llm", "slm,llm")
LEVELS = ("low", "medium", "high", "expert")
CANONICAL_CURRICULUM_IDS = (
    "capabilities",
    "math_school",
    "self_build",
    "construction",
    "chat_communication",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def plan_steps(targets: str) -> list[str]:
    run_id = "realtrain_window_matrix_plan"
    receipt: dict[str, Any] = {
        "run_id": run_id,
        "steps": [],
        "blockers": [],
        "packs": {
            "ct_stage_dir": f"{model_cycle.CT_CYCLE_RUN_DIR}/{run_id}/packs"
        },
    }
    args = argparse.Namespace(
        no_push_tools=False,
        targets=model_cycle.normalize_training_targets(targets),
        slm_tasks=model_cycle.DEFAULT_SLM_TASKS,
    )
    packs = {"files": 2}
    with contextlib.redirect_stdout(io.StringIO()):
        model_cycle.plan_remote_steps(
            receipt,
            {"target": "root@ct246"},
            args,
            packs,
        )
    return [str(item.get("step")) for item in receipt["steps"]]


def exercise_dispatch(targets: str, approval: str = "") -> tuple[list[str], dict[str, Any]]:
    """Run the real branch dispatcher with remote mutations replaced by evidence fakes."""
    calls: list[str] = []
    originals = {
        name: getattr(model_cycle, name)
        for name in (
            "resolve_ssh",
            "step_collect_packs",
            "step_resolve_ct_python",
            "inspect_construction_corpus_bundle",
            "push_files",
            "push_construction_corpus",
            "step_build_dataset",
            "step_slm_datasets",
            "step_slm_train",
            "step_slm_verify",
            "step_mirror_back",
            "step_slm_reload_pending",
            "step_llm_preflight",
            "step_llm_train",
            "finish",
        )
    }

    def mark(receipt: dict[str, Any], name: str, ok: bool = True) -> bool:
        calls.append(name)
        model_cycle.record(receipt, name, ok, "verification fake", 0.0)
        return ok

    def fake_collect(receipt: dict[str, Any], _args: argparse.Namespace) -> dict[str, Any]:
        mark(receipt, "collect_packs")
        selected_targets = list(_args.targets)
        return {
            "pack_dir": str(ROOT / "memory" / "training" / "packs"),
            "selected": [],
            "skipped_stale": 0,
            "files": 1,
            "physical_rows": 10,
            "logical_rows": 10,
            "rows": 10,
            "admitted": 8,
            "explicit_rows_by_target": {
                target: 10 for target in selected_targets
            },
            "admitted_by_target": {target: 8 for target in selected_targets},
            "target_exclusions": {
                "missing_or_malformed": 0,
                "not_selected": 0,
            },
            "selected_targets": selected_targets,
            "rejected": 2,
            "invalid_rows": 0,
            "admit_disagreements": 0,
            "legacy_admit_disagreements": 0,
            "current_admit_disagreements": 0,
            "quarantined": 0,
            "quarantine_files": [],
            "quarantine_blockers": [],
            "curriculum_contract": {"ok": True, "bindings": []},
            "curriculum_coverage": {
                "ok": True,
                "covered_curricula": list(CANONICAL_CURRICULUM_IDS),
                "missing_curricula": [],
            },
            "audit": {
                "files": 1,
                "physical_rows": 10,
                "logical_rows": 10,
                "rows": 10,
            },
            "by_discipline": {"engineering": 10},
            "by_status": {"DONE": 10},
            "errors": [],
        }

    def fake_push(
        receipt: dict[str, Any],
        _cfg: dict[str, Any],
        step: str,
        _files: Any,
        _remote_dir: str,
        **_kwargs: Any,
    ) -> bool:
        return mark(receipt, step)

    model_cycle.resolve_ssh = lambda: {"target": "root@ct246", "key": "", "port": ""}
    model_cycle.step_collect_packs = fake_collect
    model_cycle.step_resolve_ct_python = lambda receipt, _cfg: (
        mark(receipt, "resolve_ct_python") and "/opt/engel/.venv/bin/python"
    )
    model_cycle.inspect_construction_corpus_bundle = lambda _root, run_id: {
        "ok": True,
        "mode": "empty",
        "local_root": str(ROOT / "memory" / "training" / "construction_env"),
        "ct_root": model_cycle.ct_construction_corpus_dir(run_id),
        "bundle_sha256": "",
        "files": [],
        "blockers": [],
        "local_verified": True,
        "remote_verified": False,
    }
    model_cycle.push_files = fake_push
    model_cycle.push_construction_corpus = lambda receipt, _cfg, _plan: mark(
        receipt, "push_construction_corpus"
    )
    model_cycle.step_build_dataset = (
        lambda receipt, _cfg, _py, _rows, _packs, **_kwargs: mark(
            receipt, "build_dataset"
        )
    )
    model_cycle.step_slm_datasets = (
        lambda receipt, _cfg, _py, _packs, _data, _rows, **_kwargs: mark(
            receipt, "slm_datasets"
        )
    )
    model_cycle.step_slm_train = lambda receipt, _cfg, _py, _tasks, _candidate, _data: mark(
        receipt, "slm_train"
    )
    model_cycle.step_slm_verify = lambda receipt, _cfg, _py, _candidate: mark(
        receipt, "slm_verify"
    )
    model_cycle.step_mirror_back = lambda receipt, _cfg, _gate, _candidate: mark(
        receipt, "mirror_back"
    )
    def fake_reload_pending(receipt: dict[str, Any]) -> bool:
        receipt["blockers"].append("verification fake: serving reload pending")
        return mark(receipt, "slm_reload", False)

    model_cycle.step_slm_reload_pending = fake_reload_pending
    # (2026-08-06) The post-promotion capability gate makes a REAL call to the local chat
    # lane. This verifier exercises the scheduling matrix against stubbed steps, so left
    # unstubbed the gate would score zero here and turn every simulated dispatch into a
    # blocker. The gate is proven on its own in verify_engel_capability_eval.py; what
    # matters HERE is only that run_cycle dispatches it.
    model_cycle.step_capability_gate = lambda receipt, _snapshot: mark(
        receipt, "capability_gate"
    )
    model_cycle.step_llm_preflight = lambda receipt, _cfg, _py: mark(
        receipt, "llm_preflight"
    )
    model_cycle.step_llm_train = lambda receipt, _cfg, _py, _approval: mark(
        receipt, "llm_train"
    )

    def fake_finish(receipt: dict[str, Any], dataset_ok: bool = False) -> dict[str, Any]:
        receipt["status"] = (
            "PASS"
            if not receipt.get("blockers")
            else "PARTIAL"
            if dataset_ok
            else "FAIL"
        )
        receipt["dataset_ok"] = dataset_ok
        return receipt

    model_cycle.finish = fake_finish
    args = argparse.Namespace(
        since_hours=48.0,
        all=True,
        no_push_tools=False,
        no_ct=False,
        dry_run=False,
        slm_tasks=model_cycle.DEFAULT_SLM_TASKS,
        targets=model_cycle.normalize_training_targets(targets),
        llm_approval=approval,
    )
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            receipt = model_cycle.run_cycle(args)
    finally:
        for name, value in originals.items():
            setattr(model_cycle, name, value)
    return calls, receipt


def main() -> int:
    index = json.loads(INDEX.read_text(encoding="utf-8-sig"))
    curricula = index.get("curricula") if isinstance(index, dict) else []
    require(isinstance(curricula, list), "curricula index must contain a list")
    require(
        all(isinstance(curriculum, dict) for curriculum in curricula),
        "every curriculum entry must be an object",
    )
    curriculum_ids = [str(curriculum.get("id") or "").strip() for curriculum in curricula]
    require(
        len(curricula) == 5,
        f"curricula index must contain exactly five choices, got {len(curricula)}",
    )
    require(
        len(set(curriculum_ids)) == len(curriculum_ids),
        f"curricula index contains duplicate IDs: {curriculum_ids}",
    )
    require(
        tuple(curriculum_ids) == CANONICAL_CURRICULUM_IDS,
        "canonical curriculum IDs or picker order drifted: "
        f"expected {list(CANONICAL_CURRICULUM_IDS)}, got {curriculum_ids}",
    )
    require(
        index.get("all_curricula_ready") is True
        and int(index.get("total_topics") or 0) == 40
        and int(index.get("total_prompts") or 0) == 400,
        "five-curriculum index is not fully ready for 8h/80 prompts each",
    )
    require(
        int(index.get("curriculum_count") or 0) == 5,
        "curriculum_count must be exactly five",
    )

    combinations = 0
    entry_total = 0
    expected_combinations = 0
    hours_by_curriculum: dict[str, int] = {}
    for curriculum in curricula:
        require(isinstance(curriculum, dict), "curriculum entry must be an object")
        template = Path(str(curriculum.get("template_path") or ""))
        require(template.is_file(), f"missing curriculum template: {template}")
        topic_count = int(curriculum.get("topic_count") or 0)
        maximum_hours = int(curriculum.get("maximum_hours") or topic_count)
        prompt_count = int(curriculum.get("prompt_count") or 0)
        require(maximum_hours == 8, f"{template.name}: must offer eight hours")
        require(
            topic_count == 8,
            f"{template.name}: must bind eight distinct topics",
        )
        require(
            prompt_count == 80,
            f"{template.name}: must bind exactly 80 prompts",
        )
        require(
            curriculum.get("novelty_ready") is True
            and curriculum.get("novelty_fully_ready") is True
            and curriculum.get("novelty_status") == "READY"
            and int(curriculum.get("novel_hours_available") or 0) == 8
            and int(curriculum.get("novel_complete_cycle_count") or 0) == 8
            and int(curriculum.get("replayed_prompt_count") or 0) == 0,
            f"{template.name}: all eight hours must be currently novel",
        )
        require(
            str(curriculum.get("material_source") or "")
            in {"canonical_handwritten", "adopted_generated"},
            f"{template.name}: material provenance is missing",
        )
        require(
            bool(curriculum.get("generated_source_id"))
            == (
                curriculum.get("material_source") == "adopted_generated"
            ),
            f"{template.name}: generated source provenance is inconsistent",
        )
        curriculum_id = str(curriculum.get("id") or template.stem)
        hours_by_curriculum[curriculum_id] = maximum_hours
        expected_combinations += maximum_hours * len(LEVELS) * 10 * len(TARGET_CHOICES)
        for hours in range(1, maximum_hours + 1):
            for level in LEVELS:
                for per_hour in range(1, 11):
                    schedule = prompt_runner._load_training_schedule(
                        str(template),
                        "scheduled",
                        1,
                        hours,
                        level,
                        per_hour,
                    )
                    entries = schedule.get("entries") or []
                    hourly_cycles = schedule.get("hourly_cycles") or []
                    require(
                        len(entries) == hours * per_hour,
                        f"{template.name}/{hours}/{level}/{per_hour}: wrong entry count",
                    )
                    require(
                        len(hourly_cycles) == hours,
                        f"{template.name}/{hours}/{level}/{per_hour}: wrong hourly cycle count",
                    )
                    require(
                        {int(item.get("scheduled_hour") or 0) for item in entries}
                        == set(range(1, hours + 1)),
                        f"{template.name}/{hours}/{level}/{per_hour}: missing scheduled hour",
                    )
                    require(
                        len({str(item.get("material_topic") or "") for item in hourly_cycles})
                        == hours,
                        f"{template.name}/{hours}/{level}/{per_hour}: repeated hourly material",
                    )
                    require(
                        all(str(item.get("base_prompt") or "").strip() for item in entries),
                        f"{template.name}/{hours}/{level}/{per_hour}: empty prompt",
                    )
                    for targets in TARGET_CHOICES:
                        canonical = support.validate_training_targets(targets)
                        require(canonical == targets, f"target order drifted: {targets} -> {canonical}")
                        combinations += 1
                        entry_total += len(entries)
        if maximum_hours < 8:
            try:
                prompt_runner._load_training_schedule(
                    str(template),
                    "scheduled",
                    1,
                    maximum_hours + 1,
                    LEVELS[0],
                    1,
                )
            except RuntimeError as exc:
                require(
                    "requested" in str(exc)
                    and "template supports at most" in str(exc),
                    f"{template.name}: over-limit error is unclear: {exc}",
                )
            else:
                raise AssertionError(
                    f"{template.name}: accepted {maximum_hours + 1} hours by padding/replay"
                )

    require(combinations == expected_combinations, "matrix coverage drifted")
    for bad in ("", "cloud", "gguf", "slm,cloud", "slm,llm,other"):
        try:
            support.validate_training_targets(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsupported target was accepted: {bad!r}")

    slm_steps = plan_steps("slm")
    llm_steps = plan_steps("llm")
    both_steps = plan_steps("slm,llm")
    require("slm_train" in slm_steps and "llm_train" not in slm_steps, "SLM plan is wrong")
    require("llm_train" in llm_steps and "slm_train" not in llm_steps, "LLM plan is wrong")
    require("slm_train" in both_steps and "llm_train" in both_steps, "combined plan is incomplete")
    require(
        not model_cycle.llm_training_approval_valid("llm", ""),
        "LLM mutation accepted without approval",
    )
    require(
        model_cycle.llm_training_approval_valid(
            "llm", model_cycle.LLM_APPROVAL_PHRASE
        ),
        "exact LLM approval was rejected",
    )
    slm_calls, slm_receipt = exercise_dispatch("slm")
    llm_calls, llm_receipt = exercise_dispatch(
        "llm", model_cycle.LLM_APPROVAL_PHRASE
    )
    both_calls, both_receipt = exercise_dispatch(
        "slm,llm", model_cycle.LLM_APPROVAL_PHRASE
    )
    refused_calls, refused_receipt = exercise_dispatch("llm", "")
    require(
        "slm_train" in slm_calls and "llm_train" not in slm_calls,
        "actual SLM dispatch reached the wrong trainer",
    )
    require(
        "llm_train" in llm_calls and "slm_train" not in llm_calls,
        "actual LLM dispatch reached the wrong trainer",
    )
    require(
        "slm_train" in both_calls and "llm_train" in both_calls,
        "actual combined dispatch skipped a trainer",
    )
    require(
        "resolve_ct_python" not in refused_calls
        and refused_receipt.get("status") == "FAIL",
        "missing LLM approval did not fail before remote work",
    )
    require(llm_receipt.get("status") == "PASS", "LLM-only successful dispatch did not PASS")
    require(
        slm_receipt.get("status") == "PARTIAL"
        and both_receipt.get("status") == "PARTIAL",
        "an SLM filesystem release falsely claimed PASS before serving reload acknowledgement",
    )

    launcher = LAUNCHER.read_text(encoding="utf-8-sig")
    for marker in (
        "[ValidateRange(1, 8)]",
        # 2026-08-07: the launcher added senior depth tiers.  This gate used to
        # pin the old four-value literal and reported the expanded, safer
        # validation set as missing even though the guard was still present.
        "[ValidateSet('low', 'medium', 'high', 'expert', 'principal', 'distinguished', 'fellow')]",
        "[ValidateRange(1, 10)]",
        "[ValidateSet('slm', 'llm', 'slm,llm')]",
        "'--training-targets', $TrainingTargets",
    ):
        require(marker in launcher, f"launcher contract missing: {marker}")

    # The training feature lives in training_section.dart, a `part of` main.dart --
    # one library across two files. Read both: checking main.dart alone turned this
    # gate red the moment the section was extracted (2026-08-03), for markers that
    # had simply moved.
    ui_source = FLUTTER_UI.read_text(encoding="utf-8") + "\n" + TRAINING_SECTION.read_text(
        encoding="utf-8"
    )
    for marker in (
        "training-target-slm",
        "training-target-llm",
        "-TrainingTargets",
        "--targets",
        "--llm-approval",
        "engelLocalLlmTrainingApprovalPhrase",
        "Train Selected Models",
    ):
        require(marker in ui_source, f"Flutter training target wiring missing: {marker}")

    for marker in (
        "training_curriculum_id",
        "Review $_trainingHours-hour Prompt Training",
        "Test 3 Prompts",
        "--local-only",
        "Previous model cycle",
        "model-training-advanced-commands",
    ):
        require(marker in ui_source, f"Flutter training preflight wiring missing: {marker}")

    # A single failed prompt must not be reported as a dead run: the runner stops
    # only after repeated failures, and 'Training failed at prompt N' on a live run
    # made a 49/50 run look stopped at its one failure (2026-08-03).
    section_source = TRAINING_SECTION.read_text(encoding="utf-8")
    require(
        "did not pass — training continues" in section_source,
        "training UI no longer distinguishes a failed prompt from a failed run",
    )
    require(
        "} else if (active) {" in section_source,
        "training UI failure wording is not gated on the run still being active",
    )

    runner_source = PROMPT_RUNNER.read_text(encoding="utf-8")
    for marker in (
        "remaining_seconds = max(1, math.ceil(deadline - time.monotonic()))",
        "prompt_timeout = min(per_prompt_timeout, remaining_seconds)",
        'summary["completion_quality"]',
        'summary["training_pack_rejected"]',
        # a turn the app already finished must not hold the run to its full
        # per-prompt budget waiting for a receipt that is never coming
        "UI_CHAT_INBOX_FINISHED_GRACE_SECONDS",
        "_inbox_turn_finished(",
    ):
        require(marker in runner_source, f"prompt runner safety contract missing: {marker}")

    result = {
        "status": "PASS",
        "curricula": len(curricula),
        "hours": list(range(1, 9)),
        "maximum_hours_by_curriculum": hours_by_curriculum,
        "levels": list(LEVELS),
        "trainings_per_hour": list(range(1, 11)),
        "target_selections": list(TARGET_CHOICES),
        "schedule_target_combinations_verified": combinations,
        "scheduled_prompt_instances_checked": entry_total,
        "model_plans": {
            "slm": slm_steps,
            "llm": llm_steps,
            "slm,llm": both_steps,
        },
        "executed_dispatches_with_remote_fakes": {
            "slm": slm_calls,
            "llm": llm_calls,
            "slm,llm": both_calls,
            "llm_without_approval": refused_calls,
        },
        "llm_exact_approval_gate": True,
        "llm_auto_deploy": False,
        "selected_window_timeout_bounded": True,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
