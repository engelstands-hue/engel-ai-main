#!/usr/bin/env python3
"""Gate for Engel's canonical SLM roster and artifact integrity.

Enforces the two standards the 2026-07-30 pass established, because two of three
trained candidates would have shipped on a bare accuracy number:

  1. A model must beat the MAJORITY-CLASS BASELINE by a real margin. `reply_grader`
     scored 77% accuracy on a dataset that is 75% one class — impressive-looking and
     worthless.
  2. A model must not be reproducing its own labelling rule. `failure_triage` scored
     F1 = 1.00 from 18 distinct inputs across 935 rows; the label was recoverable from
     the text, so a regex was the correct tool.

Deployable artifacts must identify their canonical task and match the exact SHA-256
recorded by the v2 training report before any pickle-capable loader sees their bytes.
A roster entry that cannot be tied to its receipt is an unaudited file, not a
servable model.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for candidate in (str(ROOT), str(ROOT / "tools")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

CHECKS: list[tuple[str, bool, str]] = []

# Directory the serving runtime actually resolved this roster from; set in main().
ARTIFACT_DIR: Path | None = None


SKIPPED: list[tuple[str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def skip(name: str, detail: str) -> None:
    """Record a check that could NOT run on this host, visibly and separately.

    Artifact integrity needs joblib (and the estimator's own library) to deserialize a
    bundle. Those live on CT246, which is where the roster is SERVED; the ROG workspace
    keeps a verified mirror for audit and has no joblib. Reporting FAIL there is a false
    red that trains everyone to ignore this gate, and silently passing would make it
    vacuous on the very host it is usually run from. So: say plainly that it did not run.
    A corrupt or swapped artifact still FAILS wherever the loader exists.
    """
    SKIPPED.append((name, detail))
    print(f"SKIP {name}  ({detail})")


def artifact_path(task: str) -> Path:
    """Where this host keeps the canonical artifact for a report task.

    Reports can carry an absolute path from another host. Never dereference that
    untrusted path: select the canonical filename inside the directory the serving
    runtime resolved, then validate the report's recorded basename separately.
    """
    if ARTIFACT_DIR is None:
        return Path(f"engel_slm_{task}.joblib")
    return ARTIFACT_DIR / f"engel_slm_{task}.joblib"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT), help="/opt/engel on CT246")
    args = parser.parse_args()
    root = Path(args.root)

    import engel_slm_roster as roster
    import engel_slm_trainer as trainer

    def validated_artifact_payload(
        task: str, entry: dict, artifact: Path
    ) -> bytes | None:
        """Authenticate report, canonical path, and exact bytes before joblib."""
        report_ok = (
            report.get("schema") == roster.TRAINING_REPORT_SCHEMA
            and str(entry.get("task") or "") == task
        )
        check(
            f"artifact_report_authenticates[{task}]",
            report_ok,
            str(report.get("schema") or "missing schema"),
        )
        if not report_ok:
            return None

        expected_name = f"engel_slm_{task}.joblib"
        recorded_name = (
            str(entry.get("artifact") or "").replace("\\", "/").rsplit("/", 1)[-1]
        )
        try:
            model_root = ARTIFACT_DIR.resolve(strict=True) if ARTIFACT_DIR else None
            resolved_artifact = artifact.resolve(strict=True)
            path_ok = (
                model_root is not None
                and recorded_name == expected_name
                and resolved_artifact.parent == model_root
                and resolved_artifact.name == expected_name
                and resolved_artifact.is_file()
            )
            path_detail = str(resolved_artifact)
        except OSError as exc:
            path_ok = False
            path_detail = f"{type(exc).__name__}: {exc}"
        check(f"artifact_path_matches_report[{task}]", path_ok, path_detail)
        if not path_ok:
            return None

        expected_hash = str(entry.get("artifact_sha256") or "").casefold()
        valid_expected_hash = len(expected_hash) == 64 and all(
            ch in "0123456789abcdef" for ch in expected_hash
        )
        try:
            payload = resolved_artifact.read_bytes()
            actual_hash = hashlib.sha256(payload).hexdigest()
        except OSError as exc:
            check(
                f"artifact_hash_matches_report[{task}]",
                False,
                f"{type(exc).__name__}: {exc}",
            )
            return None
        hash_ok = valid_expected_hash and actual_hash == expected_hash
        check(
            f"artifact_hash_matches_report[{task}]",
            hash_ok,
            f"expected={expected_hash or 'missing'} actual={actual_hash}",
        )
        return payload if hash_ok else None

    def load_verified_artifact(task: str, entry: dict, artifact: Path) -> dict | None:
        payload = validated_artifact_payload(task, entry, artifact)
        if payload is None:
            check(
                f"artifact_loads[{task}]",
                False,
                "refused before deserialization",
            )
            return None
        try:
            import joblib

            bundle = joblib.load(io.BytesIO(payload))
        except ModuleNotFoundError as exc:
            skip(f"artifact_loads[{task}]", f"no deserializer on this host: {exc}")
            return None
        except Exception as exc:  # noqa: BLE001
            check(f"artifact_loads[{task}]", False, f"{type(exc).__name__}: {exc}")
            return None
        if not isinstance(bundle, dict):
            check(
                f"artifact_loads[{task}]",
                False,
                f"expected dict, got {type(bundle).__name__}",
            )
            return None
        return bundle

    def check_artifact_contract(task: str, bundle: dict) -> None:
        check(
            f"artifact_contract_matches[{task}]",
            bundle.get("schema") == roster.ARTIFACT_SCHEMA
            and bundle.get("task") == task
            and bundle.get("task_contract_version")
            == roster.task_spec(task).contract_version,
        )

    # --- the leakage detector itself must work, or the gate is decorative ---
    leaky = trainer.leakage_report(["a"] * 500 + ["b"] * 435, ["live"] * 500 + ["quality"] * 435)
    check("leakage_detector_flags_lookup_table", leaky["leaking"] is True,
          f"{leaky['distinct_texts']} distinct texts")
    honest = trainer.leakage_report([f"prompt {i}" for i in range(900)],
                                    ["chat" if i % 3 else "build" for i in range(900)])
    check("leakage_detector_passes_real_task", honest["leaking"] is False,
          f"distinct_ratio={honest['distinct_ratio']}")

    check("gate_thresholds_declared",
          trainer.MIN_MACRO_F1 > 0 and trainer.MIN_LIFT_OVER_BASELINE > 0,
          f"macro_f1>={trainer.MIN_MACRO_F1}, lift>={trainer.MIN_LIFT_OVER_BASELINE}")

    # Structural features must be finite and fixed-width or the linear head breaks.
    widths = {len(trainer.structural_features(t)) for t in
              ("", "REPLY: hi", "REPLY: " + "x " * 900, "REPLY: ```code```\n- a\n- b")}
    check("structural_features_fixed_width", len(widths) == 1, str(widths))
    check("structural_features_finite",
          all(abs(v) < 1e6 for v in trainer.structural_features("REPLY: " + "x " * 5000)))

    # --- the training report must be honest about every model it recorded ---
    # Resolve the roster directory the way the SERVING RUNTIME does, instead of pinning
    # one path. engel_slm_runtime.model_dir() walks ENGEL_SLM_MODEL_DIR ->
    # /opt/engel/models-active/slm (CT) -> <root>/runtime/slm_models (ROG), and this
    # verifier used to hardcode the CT-shaped `models-active/slm`, which does not exist
    # on the ROG workspace. It therefore reported FAIL training_report_present against a
    # path the runtime never consults, while the real report sat in runtime/slm_models --
    # the same "assert the contract, not the string literal" failure that left two other
    # gates silently red. Falling back to the old literal keeps the check honest if the
    # runtime module is ever unavailable.
    global ARTIFACT_DIR
    report_path = None
    try:
        import engel_slm_runtime

        resolved_dir = engel_slm_runtime.EngelSlmRuntime().model_dir()
        if resolved_dir is not None:
            ARTIFACT_DIR = resolved_dir
            report_path = resolved_dir / engel_slm_runtime.TRAINING_REPORT_NAME
    except Exception:  # noqa: BLE001 -- a missing runtime must not mask the real check
        report_path = None
    if report_path is None:
        report_path = root / "models-active" / "slm" / "LATEST_TRAINING.json"
    if ARTIFACT_DIR is None:
        ARTIFACT_DIR = report_path.parent
    if not report_path.is_file():
        check("training_report_present", False, f"missing {report_path}")
    else:
        check("training_report_present", True, str(report_path))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        results = report.get("results") or []
        check("training_report_has_results", bool(results), f"{len(results)} entries")
        tasks = [str(entry.get("task") or "") for entry in results if isinstance(entry, dict)]
        check(
            "training_report_tasks_are_canonical",
            len(tasks) == len(set(tasks)) and set(tasks) <= set(roster.KNOWN_TASKS),
            str(tasks),
        )
        if report.get("schema") == roster.TRAINING_REPORT_SCHEMA:
            requested = report.get("requested_tasks") or []
            check(
                "v2_report_requested_tasks_match_results",
                list(requested) == tasks,
                f"requested={requested} results={tasks}",
            )
            roster_rows = report.get("roster") or []
            roster_tasks = [
                str(row.get("task") or "") for row in roster_rows if isinstance(row, dict)
            ]
            check(
                "v2_report_carries_the_complete_ordered_roster",
                roster_tasks == list(roster.KNOWN_TASKS),
                str(roster_tasks),
            )
        for entry in results:
            task = str(entry.get("task") or "?")
            metrics = entry.get("metrics") or {}
            per_check = entry.get("per_check") or {}
            if entry.get("ok") is True and per_check:
                # Multi-head model (one binary head per style check): the single-label
                # contract does not apply. Judge each SHIPPED head on its own metrics,
                # including recall on the class it exists to catch.
                shipped = [name for name, m in per_check.items() if m.get("shipped")]
                check(f"multihead_shipped_at_least_one[{task}]", bool(shipped),
                      f"{len(shipped)} of {len(per_check)}")
                weak = [
                    name
                    for name in shipped
                    if float(per_check[name].get("macro_f1") or 0) < trainer.MIN_MACRO_F1
                    or float(per_check[name].get("fails_recall") or 0) < 0.50
                    or (
                        "selected_ok" in entry
                        and float(per_check[name].get("lift_over_baseline") or 0)
                        < trainer.MIN_LIFT_OVER_BASELINE
                    )
                ]
                check(f"multihead_every_shipped_head_meets_gate[{task}]", not weak, str(weak))
                missing_baseline = [
                    name for name in shipped
                    if per_check[name].get("baseline_accuracy") is None
                ]
                check(f"multihead_heads_report_baseline[{task}]", not missing_baseline,
                      str(missing_baseline))
                check(f"shipped_model_not_leaking[{task}]",
                      (entry.get("leakage") or {}).get("leaking") is not True)
                artifact = artifact_path(task)
                if artifact.is_file():
                    bundle = load_verified_artifact(task, entry, artifact)
                    if bundle is not None:
                        heads = bundle.get("heads") or {}
                        check(f"artifact_loads[{task}]", bool(heads), f"{len(heads)} heads")
                        check(f"artifact_heads_match_report[{task}]",
                              set(heads) == set(shipped),
                              f"artifact={sorted(heads)} report={sorted(shipped)}")
                        check(f"artifact_declares_backend[{task}]", bool(bundle.get("backend")),
                              str(bundle.get("backend")))
                        check_artifact_contract(task, bundle)
                else:
                    check(f"artifact_loads[{task}]", False, f"missing {artifact}")
                continue
            if entry.get("ok") is True:
                check(
                    f"shipped_model_beats_baseline[{task}]",
                    float(metrics.get("lift_over_baseline") or 0) >= trainer.MIN_LIFT_OVER_BASELINE
                    and float(metrics.get("macro_f1") or 0) >= trainer.MIN_MACRO_F1,
                    f"macro_f1={metrics.get('macro_f1')} lift={metrics.get('lift_over_baseline')}",
                )
                check(
                    f"shipped_model_not_leaking[{task}]",
                    (entry.get("leakage") or {}).get("leaking") is not True,
                )
                check(
                    f"shipped_model_reports_baseline[{task}]",
                    metrics.get("majority_baseline_accuracy") is not None,
                    "a result without its baseline cannot be judged",
                )
                artifact = artifact_path(task)
                if artifact.is_file():
                    bundle = load_verified_artifact(task, entry, artifact)
                    if bundle is not None:
                        check(f"artifact_loads[{task}]", "classifier" in bundle)
                        check(f"artifact_declares_classes[{task}]", bool(bundle.get("classes")),
                              str(bundle.get("classes")))
                        check(f"artifact_declares_backend[{task}]", bool(bundle.get("backend")),
                              str(bundle.get("backend")))
                        check_artifact_contract(task, bundle)
                else:
                    check(f"artifact_loads[{task}]", False, f"missing {artifact}")
            else:
                # A rejected model must say WHY, so nobody re-runs it hoping for luck.
                check(
                    f"rejected_model_states_reason[{task}]",
                    bool(entry.get("status")),
                    str(entry.get("status"))[:80],
                )

    # (2026-08-07) Cycle-over-cycle progress must be MEASURED, not assumed: the majority
    # baseline says "better than nothing"; only scoring the incumbent artifact on the same
    # held-out split says "better than what Engel already ships". Source contract: the
    # comparison exists, reports honestly when it cannot compare, and candidate quality
    # remains distinct from the eligibility of the artifact actually selected on disk.
    # (2026-08-09, operator-directed after regressions repeated a second cycle) The
    # comparison now ALSO selects which bytes ship: an incumbent that beats the new
    # candidate on the same split keeps its seat. Style classifiers are selected as an
    # atomic bundle because TF-IDF heads cannot be mixed across different vocabularies.
    trainer_source = Path(trainer.__file__).read_text(encoding="utf-8")
    check(
        "trainer_scores_the_incumbent_on_the_same_split",
        "_compare_with_previous" in trainer_source
        and '"delta_vs_previous"' in trainer_source
        and '"delta_vs_previous_macro_f1"' in trainer_source,
        "single-label heads and every style check head report a delta vs the previous artifact",
    )
    check(
        "previous_comparison_is_honest_about_incomparability",
        '"no previous artifact"' in trainer_source
        and '"authenticated": False' in trainer_source
        and "feature backend changed" in trainer_source,
        "missing, unauthenticated, or backend-changed predecessors are reported, never scored wrongly",
    )
    check(
        "candidate_and_selected_quality_are_distinct",
        '"candidate_ok"' in trainer_source
        and '"selected_ok"' in trainer_source
        and '"selected_head"' in trainer_source
        and '"candidate_metrics"' in trainer_source
        and '"selected_metrics"' in trainer_source,
        "reports must not call a rejected candidate the selected artifact",
    )
    check(
        "incumbent_selection_prevents_unsafe_overwrite",
        '"incumbent_kept"' in trainer_source
        and '"shipped_head"' in trainer_source
        and 'if selection["selected_head"] == "candidate":' in trainer_source,
        "only a selected, gate-passing, comparable candidate may overwrite bytes",
    )
    check(
        "incumbent_defends_only_when_it_meets_both_gates",
        "_single_label_gate" in trainer_source
        and "MIN_LIFT_OVER_BASELINE" in trainer_source
        and "incumbent_bundle_ok" in trainer_source
        and '"dropped_incumbent_heads"' in trainer_source,
        "single-label and style incumbents require macro-F1 and lift on the current split",
    )

    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if SKIPPED:
        # Never fold skips into the pass count -- a reader must be able to see that
        # artifact integrity was NOT proven on this host.
        print(
            f"SKIPPED (not runnable here): {len(SKIPPED)} -- "
            + ", ".join(name for name, _ in SKIPPED)
        )
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
