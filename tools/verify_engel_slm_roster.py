#!/usr/bin/env python3
"""Verify Engel AI Main's complete, bounded, single-source SLM roster.

This is the drift gate for the model list itself.  Runtime behavior and artifact
loading have their own verifier; this one proves that every producer, consumer,
and visible UI starts from the same six advisory heads, and that the two new data
lanes cannot learn an authorization outcome or their own label.
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for candidate in (str(ROOT), str(TOOLS)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import engel_slm_dataset_builder as datasets  # noqa: E402
import engel_slm_roster as roster  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    expected = (
        "intent_router",
        "route_governor",
        "style_checks",
        "reply_grader",
        "train_admit",
        "failure_triage",
    )
    check("canonical_roster_has_exactly_six_heads", roster.KNOWN_TASKS == expected, str(roster.KNOWN_TASKS))
    check(
        "default_training_set_is_bounded",
        roster.DEFAULT_TRAIN_TASKS
        == ("intent_router", "style_checks", "reply_grader", "train_admit"),
        str(roster.DEFAULT_TRAIN_TASKS),
    )
    check(
        "candidate_heads_are_not_default_trained",
        tuple(spec.task for spec in roster.ROSTER if not spec.default_train)
        == ("route_governor", "failure_triage"),
    )
    check(
        "every_head_has_a_complete_contract",
        all(
            spec.display_name
            and spec.purpose
            and spec.input_contract
            and spec.labels
            and spec.runtime_method
            and spec.consumer
            and spec.dataset_source
            and spec.contract_version > 0
            for spec in roster.ROSTER
        ),
    )
    check(
        "every_learned_head_is_advisory_only",
        all(spec.authority == "advisory_only" for spec in roster.ROSTER),
    )
    forbidden_authority = re.compile(
        r"(^|_)(allow|authorize|approval|deploy|permission|persist|promote|trusted_memory)($|_)"
    )
    check(
        "no_head_is_an_authority_model",
        not [spec.task for spec in roster.ROSTER if forbidden_authority.search(spec.task)],
    )

    check("normalize_default_uses_registry", roster.normalize_tasks("default") == roster.DEFAULT_TRAIN_TASKS)
    check("normalize_all_uses_registry", roster.normalize_tasks("all") == roster.KNOWN_TASKS)
    check(
        "normalize_selection_deduplicates_in_order",
        roster.normalize_tasks("reply_grader,intent_router,reply_grader")
        == ("reply_grader", "intent_router"),
    )
    try:
        roster.normalize_tasks("intent_router,unknown_head")
        rejected_unknown = False
    except ValueError:
        rejected_unknown = True
    check("unknown_head_fails_closed", rejected_unknown)

    snapshot = roster.roster_snapshot([{"task": "intent_router", "ok": True, "status": "ready"}])
    check(
        "partial_results_still_produce_a_complete_roster",
        [row["task"] for row in snapshot] == list(expected) and len(snapshot) == 6,
    )
    check(
        "unselected_heads_are_explicit",
        all(
            row["recorded_in_latest_run"] is False
            and row["eligible"] is False
            and "not selected" in row["training_status"]
            for row in snapshot[1:]
        ),
    )

    unsafe_features: dict[str, Any] = {
        "intent": "build",
        "prompt_len": 123,
        "lane_health": {"z": "ready", "a": "down", "nested": {"drop": True}},
        "outcome": "ct_deep_local_specialist",
        "rule_id": "force_route",
        "approval": "operator said yes",
        "gate_ok": True,
        "free_form": "must not enter training",
    }
    canonical = roster.canonical_route_features(unsafe_features)
    check(
        "route_features_drop_label_and_authority_fields",
        canonical
        == {
            "intent": "build",
            "prompt_len": 123,
            "lane_health": {"a": "down", "z": "ready"},
        },
        json.dumps(canonical, sort_keys=True),
    )
    check(
        "route_feature_text_is_stable",
        roster.route_feature_text(unsafe_features)
        == roster.route_feature_text({"prompt_len": 123, "intent": "build", "lane_health": {"a": "down", "z": "ready"}}),
    )

    route_receipt = {
        "_path": "chat.json",
        "governor_route_decision": {
            "features": unsafe_features,
            "verdict": {"decision": "route", "outcome": "ct_deep_local_specialist"},
        },
    }
    route_governor_row = {
        "_path": "governor.jsonl",
        "features": unsafe_features,
        "verdict": {"decision": "route", "outcome": "ct_deep_local_specialist"},
    }
    route_rows = datasets.build_route_governor([route_receipt], [route_governor_row])
    check("route_dataset_collapses_exact_duplicates", len(route_rows) == 1, str(route_rows))
    check(
        "route_dataset_keeps_only_canonical_features",
        bool(route_rows) and route_rows[0]["features"] == canonical,
    )

    forge_rows = [
        {"goal": "repair parser", "error_class": "assert", "error_tail": "expected x", "fixed_by_next": True},
        {"goal": "repair parser", "error_class": "assert", "error_tail": "expected x", "fixed_by_next": True},
        {"goal": "repair import", "error_class": "import", "error_tail": "module missing", "fixed_by_next": False},
        {"goal": "no observed outcome", "error_class": "runtime", "error_tail": "unknown"},
        {"goal": "successful run", "error_class": "none", "error_tail": "", "fixed_by_next": True},
    ]
    triage_rows = datasets.build_failure_triage(forge_rows)
    check("failure_triage_uses_observed_next_round_outcomes", len(triage_rows) == 2, str(triage_rows))
    check(
        "failure_triage_has_both_real_labels",
        {row["label"] for row in triage_rows} == {"repair_succeeded", "repair_failed"},
    )

    temp_parent = ROOT / "runtime" / "temp"
    temp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="engel_slm_roster_verify_", dir=temp_parent) as temp:
        fixture_root = Path(temp)
        out = fixture_root / "datasets"
        old_argv = sys.argv
        try:
            sys.argv = ["engel_slm_dataset_builder.py", "--root", str(fixture_root), "--out", str(out)]
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = datasets.main()
        finally:
            sys.argv = old_argv
        manifest = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
        check("dataset_builder_cli_succeeds", exit_code == 0)
        check("dataset_manifest_is_v2", manifest.get("schema") == "engel_slm_dataset_manifest_v2")
        check(
            "manifest_carries_complete_ordered_roster",
            [row.get("task") for row in manifest.get("roster", [])] == list(expected),
        )
        check(
            "builder_always_emits_every_roster_dataset",
            set(manifest.get("datasets", {})) == set(expected)
            and all((out / f"{task}.jsonl").is_file() for task in expected),
        )

    for path in (
        "tools/engel_slm_dataset_builder.py",
        "tools/engel_slm_trainer.py",
        "tools/engel_slm_runtime.py",
        "tools/run_engel_real_training_cycle.py",
    ):
        imported = source(path)
        check(
            f"registry_imported[{Path(path).name}]",
            "import engel_slm_roster as roster" in imported
            or "import engel_slm_roster as slm_roster" in imported,
        )

    cycle_source = source("tools/run_engel_real_training_cycle.py")
    check("cycle_pushes_registry_to_training_host", '"engel_slm_roster.py"' in cycle_source)
    check("mirror_only_selects_gate_passing_artifacts", "trained_ok" in cycle_source and "glob(\"*.joblib\")" not in cycle_source)

    # 2026-08-03: the Training section was split out of main.dart into
    # lib/training_section.dart ("part of 'main.dart'"), so the roster UI is
    # one Dart library spread across two files. Pin the whole library, not a
    # single file, or a pure file-move refactor reads as a contract break.
    flutter = source("engel_flutter_main/lib/main.dart") + source(
        "engel_flutter_main/lib/training_section.dart"
    )
    catalog_match = re.search(
        r"const List<Map<String, String>> _engelSlmRosterCatalog = \[(.*?)\n\];",
        flutter,
        flags=re.DOTALL,
    )
    flutter_tasks = tuple(re.findall(r"'task': '([^']+)'", catalog_match.group(1))) if catalog_match else ()
    check("flutter_catalog_matches_python_roster_order", flutter_tasks == expected, str(flutter_tasks))
    check(
        "flutter_roster_always_builds_from_catalog",
        "return _engelSlmRosterCatalog" in flutter
        and "_modelTrainingRosterSummary(roster.lines)" in flutter
        and "collecting" in flutter
        and "not trained" in flutter,
    )

    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
