#!/usr/bin/env python3
"""Pure deterministic checks for scheduled Engel UI prompt training."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from engel_ui_prompt_training_support import (  # noqa: E402
    DEFAULT_TRAININGS_PER_HOUR,
    TRAINING_LEVELS,
    apply_training_level_to_prompt,
    balanced_training_positions,
    fuzzy_prompt_match,
    prompt_bank,
    select_balanced_training_prompts,
    training_level_profile,
    training_report_path,
    validate_training_hours,
    validate_training_level,
    validate_trainings_per_hour,
)
from sync_engel_training_assets import build_template, wrapper_script  # noqa: E402
import run_engel_flutter_main_ui_prompt_training as prompt_runner  # noqa: E402
from run_engel_flutter_main_ui_prompt_training import (  # noqa: E402
    _load_training_schedule,
    validate_template_cycle,
)


RUNNER_PATH = TOOLS / "run_engel_flutter_main_ui_prompt_training.py"
CANONICAL_ROOT = ROOT / "memory" / "training" / "engel_main"
GENERATED_WRAPPER_PATH = CANONICAL_ROOT / "run_hour_prompt_training.ps1"
GENERATED_TEMPLATE_PATH = (
    CANONICAL_ROOT / "templates" / "ENGEL_HOUR_PROMPT_TRAINING_MIXED.json"
)


def _raises(function: Callable[..., Any], *args: Any) -> bool:
    try:
        function(*args)
    except (TypeError, ValueError):
        return True
    return False


def _check(name: str, condition: bool, detail: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": "PASS" if condition else "FAIL",
        "detail": detail,
    }


def main() -> int:
    runner_source = RUNNER_PATH.read_text(encoding="utf-8")
    runner_tree = ast.parse(runner_source, filename=str(RUNNER_PATH))
    template = build_template()
    cycles = template.get("cycle_prompt_sets")
    cycles = cycles if isinstance(cycles, list) else []
    topics = [
        str(item.get("material_topic") or "")
        for item in cycles
        if isinstance(item, dict)
    ]
    prompt_hashes = [
        hashlib.sha256(
            "\n".join(str(prompt) for prompt in item.get("prompts") or []).encode(
                "utf-8"
            )
        ).hexdigest()
        for item in cycles
        if isinstance(item, dict)
    ]

    checks: list[dict[str, Any]] = []
    valid_hours = [validate_training_hours(value) for value in range(1, 9)]
    checks.append(
        _check(
            "hours_validation",
            valid_hours == list(range(1, 9))
            and _raises(validate_training_hours, 0)
            and _raises(validate_training_hours, 9)
            and _raises(validate_training_hours, "1.5"),
            "only whole scheduled hours 1 through 8 are accepted",
        )
    )
    checks.append(
        _check(
            "level_validation",
            tuple(validate_training_level(value.upper()) for value in TRAINING_LEVELS)
            == TRAINING_LEVELS
            and _raises(validate_training_level, "master"),
            "low, medium, high, and expert normalize; unsupported levels fail",
        )
    )
    valid_hourly_counts = [
        validate_trainings_per_hour(value) for value in range(1, 11)
    ]
    checks.append(
        _check(
            "trainings_per_hour_validation",
            valid_hourly_counts == list(range(1, 11))
            and DEFAULT_TRAININGS_PER_HOUR == 6
            and _raises(validate_trainings_per_hour, 0)
            and _raises(validate_trainings_per_hour, 11)
            and _raises(validate_trainings_per_hour, "2.5")
            and _raises(validate_trainings_per_hour, True),
            "independent hourly count accepts only whole values 1 through 10 and defaults to 6",
        )
    )
    checks.append(
        _check(
            "eight_distinct_hourly_cycles",
            len(cycles) == 8
            and len(set(topics)) == 8
            and all(topics)
            and len(set(prompt_hashes)) == 8
            and all(
                isinstance(item, dict)
                and item.get("fresh_material") is True
                and len(item.get("prompts") or []) == 10
                for item in cycles
            ),
            "template has eight unique fresh material cards and ten-prompt cycles",
        )
    )
    with tempfile.TemporaryDirectory(prefix="engel_topic_plan_") as raw_temp:
        template_path = Path(raw_temp) / "partial_curriculum.json"
        template_path.write_text(
            json.dumps(template, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        rotated = _load_training_schedule(
            str(template_path),
            "scheduled",
            7,
            3,
            "expert",
            10,
        )
    rotated_cycles = [
        int(item.get("template_cycle") or 0)
        for item in rotated.get("hourly_cycles") or []
    ]
    rotated_topics = [
        str(item.get("material_topic") or "")
        for item in rotated.get("hourly_cycles") or []
    ]
    checks.append(
        _check(
            "partial_topic_plan_rotates_from_exact_start_cycle",
            validate_template_cycle(7) == 7
            and _raises(validate_template_cycle, 0)
            and _raises(validate_template_cycle, 9)
            and rotated_cycles == [7, 8, 1]
            and rotated_topics == [topics[6], topics[7], topics[0]],
            "a partial curriculum starting at cycle 7 launches cycles/topics 7, 8, 1 exactly",
        )
    )
    original_novelty_evaluator = prompt_runner.evaluate_scheduled_prompt_novelty
    novelty_calls = 0

    def _block_displayed_cycle(_prompts: list[str], _packs: Path) -> dict[str, Any]:
        nonlocal novelty_calls
        novelty_calls += 1
        return {
            "decision": "BLOCK",
            "ok": False,
            "replayed_prompt_count": 10,
        }

    try:
        prompt_runner.evaluate_scheduled_prompt_novelty = _block_displayed_cycle
        exact_template_path = (
            CANONICAL_ROOT / "templates" / "ENGEL_TEMPLATE_CAPABILITIES.json"
        )
        exact_preflight = prompt_runner._prepare_session_preflight(
            mode="scheduled",
            template_path=str(exact_template_path),
            template_cycle=7,
            scheduled_hours=3,
            training_level="expert",
            trainings_per_hour=10,
            start_index=1,
            exact_template_cycle=True,
        )
    finally:
        prompt_runner.evaluate_scheduled_prompt_novelty = original_novelty_evaluator
    checks.append(
        _check(
            "exact_topic_consent_never_auto_advances",
            novelty_calls == 1
            and exact_preflight.get("template_cycle_effective") == 7
            and exact_preflight.get("template_cycle_contract") == "EXACT"
            and exact_preflight.get("prompt_novelty_auto_advance") == {},
            "a replay discovered after confirmation blocks the displayed cycle instead of silently switching topics",
        )
    )
    profile_checks = []
    first_cycle_prompts = list(cycles[0]["prompts"]) if cycles else []
    transformed_prompts: dict[str, str] = {}
    for level in TRAINING_LEVELS:
        profile = training_level_profile(level)
        transformed = apply_training_level_to_prompt(
            first_cycle_prompts[0] if first_cycle_prompts else "sample",
            level,
        )
        transformed_prompts[level] = transformed
        profile_checks.append(
            # (2026-08-08) The ladder floor is expert with the HISTORICAL rank 4 kept, so
            # depth_rank in old receipts stays truthful; new tiers extend 5..7 upward.
            profile["depth_rank"] == TRAINING_LEVELS.index(level) + 4
            and len(profile["guidance"]) >= 40
            and len(profile["prompt_instruction"]) >= 80
            and first_cycle_prompts[0] in transformed
            and f"Training depth: {level.title()}" in transformed
            and not {
                "prompt_positions",
                "prompts_per_hour",
                "cadence_seconds",
            }.intersection(profile)
        )
    checks.append(
        _check(
            "independent_material_level_profiles",
            all(profile_checks)
            and len(set(transformed_prompts.values())) == len(TRAINING_LEVELS),
            "each level materially rewrites every prompt with distinct depth guidance and owns no count or cadence",
        )
    )
    expected_positions = {
        1: [1],
        2: [1, 10],
        3: [1, 6, 10],
        4: [1, 4, 7, 10],
        5: [1, 3, 6, 8, 10],
        6: [1, 3, 5, 6, 8, 10],
        7: [1, 3, 4, 6, 7, 9, 10],
        8: [1, 2, 4, 5, 6, 7, 9, 10],
        9: [1, 2, 3, 4, 6, 7, 8, 9, 10],
        10: list(range(1, 11)),
    }
    balanced_checks = []
    for count, positions in expected_positions.items():
        selected = select_balanced_training_prompts(first_cycle_prompts, count)
        balanced_checks.append(
            balanced_training_positions(count) == positions
            and [position for position, _prompt in selected] == positions
            and len(selected) == count
        )
    checks.append(
        _check(
            "balanced_independent_hourly_selection",
            all(balanced_checks),
            "each 1-10 hourly count selects deterministic positions spread across the ten-prompt cycle",
        )
    )

    scheduled_wrapper = wrapper_script(1, "scheduled")
    smoke_wrapper = wrapper_script(1, "smoke")
    checks.append(
        _check(
            "lifecycle_uses_selected_template_material_version",
            "$TemplatePayload = Get-Content -LiteralPath $Template" in scheduled_wrapper
            and "$MaterialVersion = [string]$TemplatePayload.material_version"
            in scheduled_wrapper
            and scheduled_wrapper.count("material_version = $MaterialVersion") >= 2,
            "launcher controls and lifecycle bind material_version from the selected template",
        )
    )
    checks.append(
        _check(
            "scheduled_wrapper_controls",
            all(
                token in scheduled_wrapper
                for token in (
                    "[ValidateRange(1, 8)]",
                    "[ValidateRange(1, 10)]",
                    "[ValidateRange(1, 80)]",
                    "[ValidateSet('low', 'medium', 'high', 'expert', 'principal', 'distinguished', 'fellow')]",
                    "$PlanPrompts = if ('scheduled' -eq 'smoke')",
                    "$RequestedPrompts = [int]($PlanPrompts - $StartIndex + 1)",
                    "$RequestedPrompts * $CadenceSeconds",
                    "'--mode', 'scheduled'",
                    "'--hours', [string]$Hours",
                    "'--training-level', $TrainingLevel",
                    "'--trainings-per-hour', [string]$TrainingsPerHour",
                    "'--template-cycle', [string]$TemplateCycle",
                    "'--exact-template-cycle'",
                    "'--start-index', [string]$StartIndex",
                    "template_cycle_contract = 'EXACT'",
                    "training_level_guidance",
                    "trainings_per_hour",
                    "distinct_hourly_cycles",
                )
            ),
            "wrapper validates and forwards hours, depth, frequency, and the exact displayed template cycle",
        )
    )
    # Execute the real CLI through argument validation.  The deliberately missing
    # template is the safe stop boundary: a correct 5h/10ph resume at prompt 34 must
    # pass duration validation with 17 prompts / 102 minutes remaining, then stop before
    # any UI, guard, claim, or writable action because the template cannot be resolved
    # through the exact-five canonical binding.
    resume_base = [
        sys.executable,
        str(RUNNER_PATH),
        "--mode",
        "scheduled",
        "--hours",
        "5",
        "--training-level",
        "expert",
        "--trainings-per-hour",
        "10",
        "--start-index",
        "34",
        "--template",
        str(ROOT / "runtime" / "missing_resume_regression_template.json"),
    ]
    resume_valid = subprocess.run(
        [*resume_base, "--minutes", "102"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    resume_valid_output = (resume_valid.stdout or "") + (resume_valid.stderr or "")
    resume_wrong_budget = subprocess.run(
        [*resume_base, "--minutes", "300"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    resume_wrong_output = (
        (resume_wrong_budget.stdout or "") + (resume_wrong_budget.stderr or "")
    )
    checks.append(
        _check(
            "resume_cli_preserves_plan_identity_and_remaining_cadence",
            resume_valid.returncode != 0
            and "FileNotFoundError" in resume_valid_output
            and "remaining scheduled-plan budget" not in resume_valid_output
            and resume_wrong_budget.returncode != 0
            and (
                "remaining scheduled-plan budget "
                "(expected 102 for prompt 34 of 50)"
            )
            in resume_wrong_output,
            "the executable runner accepts 5h/50-prompt plan identity with prompt 34, "
            "17 prompts, 102 remaining minutes, and the original 360-second cadence",
        )
    )
    checks.append(
        _check(
            "single_valid_lifecycle_receipt",
            "engel_main_prompt_training_launch_lifecycle_v2" in scheduled_wrapper
            and "launch_started" in scheduled_wrapper
            and "launch_finished" in scheduled_wrapper
            and "Add-Content -LiteralPath $Receipt" not in scheduled_wrapper
            and scheduled_wrapper.count(
                "Set-Content -LiteralPath $Receipt -Encoding UTF8"
            )
            == 2,
            "one JSON lifecycle object is replaced atomically at start and finish",
        )
    )
    checks.append(
        _check(
            "os_claim_and_python_guard_ownership",
            "$PerPromptTimeout * $RequestedPrompts" in scheduled_wrapper
            or (
                "[int]$Hours * [int]$TrainingsPerHour" in scheduled_wrapper
                and "requested_prompts = $RequestedPrompts" in scheduled_wrapper
            ),
            "launcher retains the bounded prompt-count controls",
        )
    )
    checks.append(
        _check(
            "launcher_cannot_overwrite_active_guard",
            "prompt_run_claim_owner = 'python_runner_os_lock'" in scheduled_wrapper
            and "active_guard_owner = 'python_runner'" in scheduled_wrapper
            and "_p$PID" in scheduled_wrapper
            and "'--launcher-pid', [string]$PID" in scheduled_wrapper
            and "'--launcher-log', $Log" in scheduled_wrapper
            and "'--lifecycle-receipt', $Receipt" in scheduled_wrapper
            and "$Sentinel" not in scheduled_wrapper
            and "$sentinelStart" not in scheduled_wrapper
            and "guard_owner = 'wrapper'" not in scheduled_wrapper
            and "completion_owner = 'wrapper'" not in scheduled_wrapper
            and "Set-Content -LiteralPath $Sentinel" not in scheduled_wrapper,
            "unique PowerShell lifecycle metadata is passed to the Python-owned guard",
        )
    )
    checks.append(
        _check(
            "missing_selected_template_fails_closed",
            "Curriculum template is required; refusing to substitute another curriculum."
            in scheduled_wrapper
            and "Selected curriculum template no longer exists" in scheduled_wrapper
            and "falling back to default" not in scheduled_wrapper,
            "launcher never swaps a vanished operator-selected curriculum for MIXED",
        )
    )
    training_ui_source = (ROOT / "engel_flutter_main" / "lib" / "training_section.dart").read_text(
        encoding="utf-8"
    )
    sync_source = (TOOLS / "sync_engel_training_assets.py").read_text(
        encoding="utf-8"
    )
    checks.append(
        _check(
            "canonical_picker_exposes_novelty_availability",
            '"novel_hours_available": novel_run_hours' in sync_source
            and '"novel_hours_start_cycle": novel_run_start_cycle' in sync_source
            and '"novelty_ready": can_run_fresh' in sync_source
            and '"novelty_fully_ready": fully_ready' in sync_source
            and '"novelty_status": novelty_status' in sync_source
            # Availability must be the longest consecutive novel run, not a
            # prefix from cycle 1 (a spent first hour used to read as USED).
            and "cycle_novelty[(start + run) % cycle_count]" in sync_source
            and "novel_run_hours >= 1" in sync_source
            and "curricula_index.extend(" not in sync_source
            and "_curriculumNoveltyReady" in training_ui_source
            and "PREPARE NEW" in training_ui_source
            # Partly-spent material states what is LEFT (count + tooltip) instead
            # of reading as fully used.
            and "still novel" in training_ui_source
            and "unused prompts" in training_ui_source
            and "selectablePrompts" in training_ui_source
            and "no unused hours left" in training_ui_source
            and "fresh" in training_ui_source,
            "five canonical choices show history-backed ready/partial/exhausted state, "
            "run their remaining fresh hours, and cannot start used material",
        )
    )
    checks.append(
        _check(
            "scheduled_runner_accepts_remaining_novel_hours",
            "selected curriculum has no unused novel hour left" in runner_source
            and "requested {scheduled_hours}h but only {available} unused novel" in runner_source
            and "complete novel 8-hour/80-prompt plan" not in runner_source
            and 'item.get("novelty_ready") is False' in runner_source
            and "novel_hours < 1" in runner_source,
            "a 1-hour leftover curriculum must be able to start; the runner must not demand a fully unused 8-hour plan",
        )
    )
    claim_main = runner_source[runner_source.index("def main() -> int:") :]
    claim_helper = runner_source[
        runner_source.index("def _run_cli_with_claim(") : runner_source.index(
            "def main() -> int:"
        )
    ]
    checks.append(
        _check(
            "claim_precedes_novelty_recheck_and_gpu_mutation",
            claim_main.index("with acquire_prompt_run_claim(")
            < claim_main.index("_run_cli_with_claim(")
            and claim_helper.index("_require_session_preflight(claimed_preflight)")
            < claim_helper.index("_freshen_stale_gpu_server()")
            and "prompt_run_claim.require_owner(run_id)" in claim_helper
            and 'local_only_guard.get("owned") is True' in runner_source,
            "one kernel claim covers claimed novelty check, optional GPU action, guard, and run",
        )
    )
    checks.append(
        _check(
            "smoke_mode_preserved",
            "'--mode', 'smoke'" in smoke_wrapper
            and "$Minutes = if ('smoke' -eq 'smoke') {\n  3.0" in smoke_wrapper
            and "$PlanPrompts = if ('smoke' -eq 'smoke') { 3 }" in smoke_wrapper,
            "smoke launcher remains short and uses the existing mode",
        )
    )

    string_literals = {
        node.value
        for node in ast.walk(runner_tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    checks.append(
        _check(
            "progress_events_and_scheduled_mode",
            {
                "scheduled",
                "flutter_training_started",
                "flutter_prompt_started",
                "flutter_prompt_complete",
                "flutter_training_complete",
                "trainings_per_hour",
            }.issubset(string_literals)
            and "def _is_delivery_failure(" in runner_source
            and "consecutive_delivery_failures >= _MAX_CONSECUTIVE_DELIVERY_FAILURES"
            in runner_source,
            "runner emits start/complete events and stops paced runs only after repeated "
            "delivery failures, not on a delivered-but-quality-blocked turn",
        )
    )
    checks.append(
        _check(
            "atomic_clipboard_submission",
            "Set-Clipboard -Value $raw" in runner_source
            and "SendWait('^v')" in runner_source
            and "Escape-SendKeys" not in runner_source
            and "atomic clipboard submission failed" in runner_source,
            "full prompt is pasted atomically instead of typed character by character",
        )
    )

    sample = (
        "Help me start a bounded coordination review with confirmed inputs, open "
        "inputs, named owners, evidence, and a safe closeout action."
    )
    checks.append(
        _check(
            "bounded_fuzzy_prompt_matching",
            fuzzy_prompt_match(sample, sample)["kind"] == "exact"
            and fuzzy_prompt_match(sample, sample[1:])["kind"]
            == "small_prefix_loss"
            and fuzzy_prompt_match(sample, sample[16:])["matched"] is True
            and fuzzy_prompt_match(sample, sample[17:])["matched"] is False
            and fuzzy_prompt_match(sample, "completely unrelated input")["matched"]
            is False
            and "record_epoch + 5 < since_epoch or record_epoch - 5 > until_epoch"
            in runner_source
            and "inspect.getsource(fuzzy_prompt_match)" in runner_source,
            "a 1-16 character prefix loss matches only inside the fresh timestamp window",
        )
    )
    checks.append(
        _check(
            "scheduled_report_routing",
            training_report_path("scheduled").name
            == "ENGEL_UI_PROMPT_TRAINING_SCHEDULED_REPORT.md"
            and training_report_path("one-hour").name
            == "ENGEL_UI_PROMPT_TRAINING_ONE_HOUR_REPORT.md"
            and training_report_path("smoke").name
            == "ENGEL_UI_PROMPT_TRAINING_SMOKE_REPORT.md",
            "scheduled mode has its own report while legacy routes remain stable",
        )
    )

    generated_template: dict[str, Any] = {}
    try:
        loaded = json.loads(
            GENERATED_TEMPLATE_PATH.read_text(encoding="utf-8-sig")
        )
        if isinstance(loaded, dict):
            generated_template = loaded
    except (OSError, ValueError, TypeError):
        generated_template = {}
    expected_template = dict(template)
    generated_template_without_time = dict(generated_template)
    expected_template.pop("updated_at_utc", None)
    generated_template_without_time.pop("updated_at_utc", None)
    try:
        generated_wrapper = GENERATED_WRAPPER_PATH.read_text(encoding="utf-8")
    except OSError:
        generated_wrapper = ""
    checks.append(
        _check(
            "generated_assets_synced",
            generated_wrapper == scheduled_wrapper
            and generated_template_without_time == expected_template,
            "canonical wrapper and template exactly reflect the reviewed generators",
        )
    )

    schedule_nodes = [
        node
        for node in runner_tree.body
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name
            in {
                "_load_template_prompts",
                "_load_training_schedule",
                # resolves the curriculum discipline the template declares
                "_resolve_template_discipline",
                # wraps apply_training_level_to_prompt to append the answer contract
                "_leveled_training_prompt",
                # selects the discipline-appropriate answer contract
                "_training_answer_contract",
            }
        )
        or (
            # ...and the module constants those functions read. This verifier does not
            # import the runner (importing chdirs to ROOT), so the literals are lifted
            # out of the AST instead.
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id
                in {
                    "_TRAINING_ANSWER_CONTRACT",
                    "_MATH_ANSWER_CONTRACT",
                    "_ENGINEERING_ANSWER_CONTRACT",
                    # the chat-voice discipline's contract (2026-08-01); every contract the
                    # _DISCIPLINE_ANSWER_CONTRACTS dict names must be lifted with it, or the
                    # exec below dies on a NameError instead of checking anything
                    "_COMMUNICATION_ANSWER_CONTRACT",
                    "_DISCIPLINE_ANSWER_CONTRACTS",
                    "_KNOWN_DISCIPLINES",
                }
                for target in node.targets
            )
        )
    ]
    schedule_module = ast.fix_missing_locations(
        ast.Module(body=schedule_nodes, type_ignores=[])
    )
    schedule_namespace: dict[str, Any] = {
        "Any": Any,
        "Path": Path,
        "hashlib": hashlib,
        "apply_training_level_to_prompt": apply_training_level_to_prompt,
        "prompt_bank": prompt_bank,
        "select_balanced_training_prompts": select_balanced_training_prompts,
        "training_level_profile": training_level_profile,
        "validate_training_hours": validate_training_hours,
        "validate_trainings_per_hour": validate_trainings_per_hour,
        "_load_json": lambda path: json.loads(
            Path(path).read_text(encoding="utf-8-sig")
        ),
        # Schedule mechanics are tested without the operator corpus. The corpus verifier
        # separately proves real extraction/binding; this deterministic stub proves the
        # schedule injects and propagates the already-verified packet for all 80 entries.
        "_aec_evidence_for_card": lambda card: {
            "ok": True,
            "prompt_context": "Verified local evidence packet: schedule verifier fixture",
            "corpus_bundle_sha256": "A" * 64,
            "expected_documents": list((card or {}).get("documents") or []),
            "records": list((card or {}).get("evidence_anchors") or []),
        },
    }
    exec(compile(schedule_module, str(RUNNER_PATH), "exec"), schedule_namespace)
    actual_schedule_ok = True
    schedule_signatures: dict[tuple[str, int], tuple[int, ...]] = {}
    level_prompt_samples: dict[str, str] = {}
    for level in TRAINING_LEVELS:
        for hourly_count in (1, 3, 6, 10):
            actual_schedule = schedule_namespace["_load_training_schedule"](
                str(GENERATED_TEMPLATE_PATH),
                "scheduled",
                1,
                8,
                level,
                hourly_count,
            )
            schedule_signatures[(level, hourly_count)] = tuple(
                item["source_prompt_index"]
                for item in actual_schedule["entries"]
                if item["scheduled_hour"] == 1
            )
            level_prompt_samples[level] = actual_schedule["entries"][0]["prompt"]
            actual_schedule_ok = bool(
                actual_schedule_ok
                and len(actual_schedule["hourly_cycles"]) == 8
                and len(actual_schedule["entries"]) == 8 * hourly_count
                and actual_schedule["trainings_per_hour"] == hourly_count
                and {
                    item["scheduled_hour"] for item in actual_schedule["entries"]
                }
                == set(range(1, 9))
                and all(
                    item["prompt"] != item["base_prompt"]
                    and item["base_prompt"] in item["prompt"]
                    for item in actual_schedule["entries"]
                )
                and (
                    actual_schedule.get("discipline") != "aec"
                    or all(
                        "Verified local evidence packet" in item["prompt"]
                        and item.get("aec_evidence_bundle_sha256") == "A" * 64
                        and item.get("aec_expected_documents")
                        for item in actual_schedule["entries"]
                    )
                )
            )
    count_independent_of_level = all(
        len(
            {
                schedule_signatures[(level, hourly_count)]
                for level in TRAINING_LEVELS
            }
        )
        == 1
        for hourly_count in (1, 3, 6, 10)
    )
    checks.append(
        _check(
            "runner_builds_independent_level_and_count_schedule",
            actual_schedule_ok
            and count_independent_of_level
            and len(set(level_prompt_samples.values())) == len(TRAINING_LEVELS),
            "actual runner schedules hours*count prompts, keeps positions level-independent, and applies level text to every entry",
        )
    )

    failures = [item for item in checks if item["status"] != "PASS"]
    payload = {
        "schema": "engel_training_schedule_verifier_v2",
        "status": "PASS" if not failures else "FAIL",
        "passed": len(checks) - len(failures),
        "total": len(checks),
        "checks": checks,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
