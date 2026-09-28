#!/usr/bin/env python3
"""Focused behavioral proof for SLM split, feature, and selection safety.

This verifier never trains a real model and never opens Engel's artifact directory.
It drives the trainer with tiny in-memory fakes and temporary placeholder files.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import pickle
import sys
import tempfile
import types
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for candidate in (str(ROOT), str(TOOLS)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import engel_slm_trainer as trainer  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []
HOSTILE_PICKLE_EXECUTED = False


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))


def metrics(macro_f1: float, lift: float, accuracy: float = 0.8) -> dict[str, Any]:
    return {
        "test_rows": 4,
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "majority_class": "chat",
        "majority_baseline_accuracy": accuracy - lift,
        "lift_over_baseline": lift,
        "per_class": {
            "fails": {"precision": 0.9, "recall": 0.9},
            "passes": {"precision": 0.9, "recall": 0.9},
        },
        "confusion_matrix": [],
        "confusion_labels": [],
    }


def write_v2_report(
    directory: Path,
    task: str,
    artifact: Path,
    artifact_hash: str | None = None,
) -> None:
    report = {
        "schema": trainer.roster.TRAINING_REPORT_SCHEMA,
        "results": [
            {
                "task": task,
                "ok": True,
                "selected_ok": True,
                "artifact": str(artifact),
                "artifact_sha256": artifact_hash
                or hashlib.sha256(artifact.read_bytes()).hexdigest(),
            }
        ],
    }
    (directory / trainer.TRAINING_REPORT_NAME).write_text(
        json.dumps(report), encoding="utf-8"
    )


def trip_hostile_pickle() -> dict[str, Any]:
    global HOSTILE_PICKLE_EXECUTED
    HOSTILE_PICKLE_EXECUTED = True
    return {}


class HostilePickle:
    def __reduce__(self):
        return trip_hostile_pickle, ()


def run_offline_and_group_checks() -> None:
    source = Path(trainer.__file__).read_text(encoding="utf-8")
    check(
        "offline: environment flags are forced, not inherited from a permissive value",
        all(
            os.environ.get(name) == "1"
            for name in (
                "HF_HUB_OFFLINE",
                "TRANSFORMERS_OFFLINE",
                "HF_DATASETS_OFFLINE",
                "HF_HUB_DISABLE_TELEMETRY",
            )
        )
        and 'local_files_only=True' in source
        and 'trust_remote_code=False' in source,
    )

    rows = []
    for label in ("build", "chat"):
        for prompt_number in range(6):
            for _duplicate in range(2):
                rows.append(
                    {
                        "prompt": f"  SAME {label} PROMPT {prompt_number}  ",
                        "label": label,
                    }
                )
    groups = [trainer._canonical_prompt_group(row, "intent_router") for row in rows]
    labels = [row["label"] for row in rows]
    train_indices, test_indices = trainer._grouped_train_test_indices(groups, labels)
    train_groups = {groups[index] for index in train_indices}
    test_groups = {groups[index] for index in test_indices}
    check(
        "split: canonical prompt duplicates never cross train and test",
        train_groups.isdisjoint(test_groups)
        and {labels[index] for index in train_indices} == {"build", "chat"}
        and {labels[index] for index in test_indices} == {"build", "chat"},
        f"overlap={sorted(train_groups & test_groups)}",
    )


class RecordingVectorizer:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[list[str]] = []

    def transform(self, texts: list[str]):
        self.calls.append(list(texts))
        if self.fail:
            raise ValueError("incumbent vocabulary unavailable")
        return [("incumbent", text) for text in texts]


class IncumbentClassifier:
    def predict(self, features):
        assert all(row[0] == "incumbent" for row in features)
        return ["INCUMBENT"] * len(features)


class FakeFeaturizer:
    instances: list["FakeFeaturizer"] = []

    def __init__(self, _root: Path) -> None:
        self.backend = "tfidf_char"
        self.vectorizer = object()
        self.fit_texts: list[str] = []
        self.test_texts: list[str] = []
        self.__class__.instances.append(self)

    def __init_structural__(self, _use_structural: bool) -> None:
        return None

    def fit_transform(self, texts: list[str]):
        self.fit_texts = list(texts)
        return [("candidate-train", text) for text in texts]

    def transform(self, texts: list[str]):
        self.test_texts = list(texts)
        return [("candidate-test", text) for text in texts]


class FakeLogisticRegression:
    def __init__(self, **_kwargs: Any) -> None:
        pass

    def fit(self, _features, _labels) -> None:
        return None

    def predict(self, features):
        return ["CANDIDATE"] * len(features)


class FakeJoblib(types.ModuleType):
    def __init__(
        self,
        vectorizer: RecordingVectorizer,
        mutate_source_after_load: Path | None = None,
    ) -> None:
        super().__init__("joblib")
        self.vectorizer = vectorizer
        self.mutate_source_after_load = mutate_source_after_load
        self.dump_calls = 0
        self.load_payloads: list[bytes] = []

    def load(self, source) -> dict[str, Any]:
        if not isinstance(source, io.BytesIO):
            raise AssertionError("incumbent loader received a mutable filesystem path")
        self.load_payloads.append(source.getvalue())
        if self.mutate_source_after_load is not None:
            self.mutate_source_after_load.write_bytes(b"mutated-after-authentication")
        return {
            "schema": trainer.roster.ARTIFACT_SCHEMA,
            "task": "intent_router",
            "task_contract_version": trainer.roster.task_spec(
                "intent_router"
            ).contract_version,
            "backend": "tfidf_char",
            "classes": ["build", "chat"],
            "classifier": IncumbentClassifier(),
            "vectorizer": self.vectorizer,
            "trained_at_utc": "incumbent",
            "dataset_rows": 8,
        }

    def dump(self, _payload: dict[str, Any], path: Path) -> None:
        self.dump_calls += 1
        path.write_bytes(b"candidate-overwrite")


class FakeStyleJoblib(FakeJoblib):
    def load(self, source) -> dict[str, Any]:
        if not isinstance(source, io.BytesIO):
            raise AssertionError("style incumbent loader received a mutable path")
        self.load_payloads.append(source.getvalue())
        if self.mutate_source_after_load is not None:
            self.mutate_source_after_load.write_bytes(b"mutated-after-authentication")
        return {
            "schema": trainer.roster.ARTIFACT_SCHEMA,
            "task": "style_checks",
            "task_contract_version": trainer.roster.task_spec(
                "style_checks"
            ).contract_version,
            "backend": "tfidf_char",
            "classes": ["fails", "passes"],
            "heads": {"no_generic_bootstrap": IncumbentClassifier()},
            "vectorizer": self.vectorizer,
            "trained_at_utc": "incumbent",
            "dataset_rows": 12,
        }


def rows_for_training() -> list[dict[str, str]]:
    rows = []
    for label in ("build", "chat"):
        for prompt_number in range(4):
            for duplicate in range(2):
                rows.append(
                    {
                        "prompt": f"prompt {label} {prompt_number}",
                        "label": label,
                        "duplicate": str(duplicate),
                    }
                )
    return rows


def run_fake_training(
    candidate_is_good: bool,
    incumbent_vectorizer_fails: bool,
    mutate_source_after_load: bool = False,
    authenticate_incumbent: bool = True,
):
    vectorizer = RecordingVectorizer(fail=incumbent_vectorizer_fails)
    sklearn_package = types.ModuleType("sklearn")
    linear_module = types.ModuleType("sklearn.linear_model")
    linear_module.LogisticRegression = FakeLogisticRegression
    sklearn_package.linear_model = linear_module

    saved_modules = {
        name: sys.modules.get(name)
        for name in ("joblib", "sklearn", "sklearn.linear_model")
    }
    saved_featurizer = trainer.Featurizer
    saved_report = trainer._report
    FakeFeaturizer.instances.clear()
    try:
        sys.modules["sklearn"] = sklearn_package
        sys.modules["sklearn.linear_model"] = linear_module
        trainer.Featurizer = FakeFeaturizer

        def fake_report(_y_true, predictions, _labels):
            if predictions and predictions[0] == "INCUMBENT":
                return metrics(0.86, 0.20, 0.90)
            return metrics(0.82, 0.18, 0.88) if candidate_is_good else metrics(0.40, -0.10, 0.50)

        trainer._report = fake_report
        with tempfile.TemporaryDirectory(prefix="engel_slm_selection_") as tmpdir:
            incumbent_dir = Path(tmpdir) / "live"
            incumbent_dir.mkdir()
            out_dir = Path(tmpdir) / "stage"
            artifact = incumbent_dir / "engel_slm_intent_router.joblib"
            artifact.write_bytes(b"incumbent-bytes")
            write_v2_report(
                incumbent_dir,
                "intent_router",
                artifact,
                None if authenticate_incumbent else "0" * 64,
            )
            fake_joblib = FakeJoblib(
                vectorizer,
                artifact if mutate_source_after_load else None,
            )
            sys.modules["joblib"] = fake_joblib
            before = artifact.read_bytes()
            result = trainer.train_single_label(
                "intent_router",
                rows_for_training(),
                Path(tmpdir),
                out_dir,
                min_per_class=1,
                incumbent_dir=incumbent_dir,
            )
            after = artifact.read_bytes()
            staged_path = out_dir / artifact.name
            staged = staged_path.read_bytes() if staged_path.is_file() else None
        return (
            result,
            fake_joblib,
            vectorizer,
            FakeFeaturizer.instances[-1],
            before,
            after,
            staged,
        )
    finally:
        trainer.Featurizer = saved_featurizer
        trainer._report = saved_report
        for name, module in saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def run_hostile_pickle_check() -> None:
    global HOSTILE_PICKLE_EXECUTED
    HOSTILE_PICKLE_EXECUTED = False
    with tempfile.TemporaryDirectory(prefix="engel_slm_hostile_incumbent_") as tmpdir:
        directory = Path(tmpdir)
        artifact = directory / "engel_slm_intent_router.joblib"
        artifact.write_bytes(pickle.dumps(HostilePickle()))
        write_v2_report(
            directory,
            "intent_router",
            artifact,
            "0" * 64,
        )
        incumbent, reason = trainer._authenticated_incumbent(
            directory,
            "intent_router",
            {"build", "chat"},
        )
    check(
        "incumbent auth: mismatched hostile pickle is never deserialized",
        incumbent is None
        and HOSTILE_PICKLE_EXECUTED is False
        and "sha256" in reason,
        reason,
    )


def run_selection_checks() -> None:
    result, joblib, vectorizer, featurizer, before, after, staged = run_fake_training(
        candidate_is_good=False, incumbent_vectorizer_fails=False
    )
    check(
        "features: candidate fits training text only and transforms held-out text later",
        bool(featurizer.fit_texts)
        and bool(featurizer.test_texts)
        and set(featurizer.fit_texts).isdisjoint(featurizer.test_texts),
    )
    check(
        "incumbent: stored TF-IDF vectorizer receives raw held-out text",
        vectorizer.calls == [featurizer.test_texts],
        f"calls={vectorizer.calls}",
    )
    check(
        "selection: below-gate candidate cannot overwrite eligible incumbent",
        joblib.dump_calls == 0
        and before == after
        and staged == before
        and result["candidate_ok"] is False
        and result["selected_ok"] is True
        and result["selected_head"] == "incumbent"
        and result["ok"] == result["selected_ok"]
        and result["metrics"] == result["selected_metrics"],
        str(result),
    )

    blocked, joblib, _vectorizer, _featurizer, before, after, staged = run_fake_training(
        candidate_is_good=True, incumbent_vectorizer_fails=True
    )
    check(
        "selection: incomparable candidate cannot overwrite incumbent",
        joblib.dump_calls == 0
        and before == after
        and staged == before
        and blocked["candidate_ok"] is True
        and blocked["selected_ok"] is False
        and blocked["selected_head"] == "incumbent"
        and blocked["ok"] == blocked["selected_ok"],
        str(blocked),
    )

    toctou = run_fake_training(
        candidate_is_good=False,
        incumbent_vectorizer_fails=False,
        mutate_source_after_load=True,
    )
    mutated_result, mutated_joblib, _, _, original, mutated, staged = toctou
    check(
        "incumbent staging: source mutation cannot change authenticated staged bytes",
        mutated_joblib.load_payloads == [original]
        and mutated == b"mutated-after-authentication"
        and staged == original
        and mutated_result["selected_head"] == "incumbent"
        and mutated_result["incumbent_authenticated"] is True
        and mutated_result["artifact_sha256"]
        == hashlib.sha256(original).hexdigest(),
        str(mutated_result),
    )

    standalone = run_fake_training(
        candidate_is_good=True,
        incumbent_vectorizer_fails=False,
        authenticate_incumbent=False,
    )
    replacement, replacement_joblib, _, _, before, after, staged = standalone
    check(
        "selection: passing candidate may replace an unauthenticated incumbent",
        replacement_joblib.load_payloads == []
        and replacement_joblib.dump_calls == 1
        and before == after
        and staged == b"candidate-overwrite"
        and replacement["candidate_ok"] is True
        and replacement["selected_ok"] is True
        and replacement["selected_head"] == "candidate"
        and replacement["incumbent_authenticated"] is False,
        str(replacement),
    )

    refused = run_fake_training(
        candidate_is_good=False,
        incumbent_vectorizer_fails=False,
        authenticate_incumbent=False,
    )
    no_selection, refused_joblib, _, _, before, after, staged = refused
    check(
        "selection: below-gate candidate cannot retain an unauthenticated incumbent",
        refused_joblib.load_payloads == []
        and refused_joblib.dump_calls == 0
        and before == after
        and staged is None
        and no_selection["candidate_ok"] is False
        and no_selection["selected_ok"] is False
        and no_selection["selected_head"] == "none"
        and no_selection["incumbent_authenticated"] is False,
        str(no_selection),
    )
    check(
        "style gate: macro-F1 without lift is ineligible",
        not trainer._style_head_gate(metrics(0.90, 0.0, 0.90)),
    )


def run_style_bundle_check() -> None:
    vectorizer = RecordingVectorizer()
    fake_joblib = FakeStyleJoblib(vectorizer)
    sklearn_package = types.ModuleType("sklearn")
    linear_module = types.ModuleType("sklearn.linear_model")
    linear_module.LogisticRegression = FakeLogisticRegression
    sklearn_package.linear_model = linear_module
    saved_modules = {
        name: sys.modules.get(name)
        for name in ("joblib", "sklearn", "sklearn.linear_model")
    }
    saved_featurizer = trainer.Featurizer
    saved_report = trainer._report
    FakeFeaturizer.instances.clear()
    try:
        sys.modules["joblib"] = fake_joblib
        sys.modules["sklearn"] = sklearn_package
        sys.modules["sklearn.linear_model"] = linear_module
        trainer.Featurizer = FakeFeaturizer

        def fake_report(_y_true, predictions, _labels):
            if predictions and predictions[0] == "INCUMBENT":
                return metrics(0.86, 0.20, 0.90)
            return metrics(0.40, -0.10, 0.50)

        trainer._report = fake_report
        rows = [
            {
                "prompt": f"style prompt {index}",
                "reply": f"style reply {index}",
                "failing_checks": ["no_generic_bootstrap"] if index % 2 == 0 else [],
            }
            for index in range(12)
        ]
        with tempfile.TemporaryDirectory(prefix="engel_slm_style_selection_") as tmpdir:
            out_dir = Path(tmpdir) / "models"
            out_dir.mkdir()
            artifact = out_dir / "engel_slm_style_checks.joblib"
            artifact.write_bytes(b"incumbent-style-bytes")
            write_v2_report(out_dir, "style_checks", artifact)
            before = artifact.read_bytes()
            result = trainer.train_style_checks(
                rows, Path(tmpdir), out_dir, min_positives=1
            )
            after = artifact.read_bytes()
    finally:
        trainer.Featurizer = saved_featurizer
        trainer._report = saved_report
        for name, module in saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    head = result["per_check"]["no_generic_bootstrap"]
    check(
        "style selection: below-gate candidate bundle preserves eligible incumbent",
        fake_joblib.dump_calls == 0
        and before == after
        and result["candidate_ok"] is False
        and result["selected_ok"] is True
        and result["selected_head"] == "incumbent"
        and result["ok"] == result["selected_ok"]
        and head["candidate_ok"] is False
        and head["selected_ok"] is True
        and head["selected_head"] == "incumbent"
        and head["candidate_metrics"] != head["selected_metrics"]
        and vectorizer.calls == [FakeFeaturizer.instances[-1].test_texts],
        str(result),
    )


def run_cli_staging_check() -> None:
    saved_argv = list(sys.argv)
    saved_train = trainer.train_single_label
    calls: list[tuple[Path, Path]] = []
    try:
        with tempfile.TemporaryDirectory(prefix="engel_slm_cli_stage_") as tmpdir:
            root = Path(tmpdir) / "root"
            data_dir = Path(tmpdir) / "cycle" / "slm_datasets"
            data_dir.mkdir(parents=True)
            (data_dir / "intent_router.jsonl").write_text("{}\n", encoding="utf-8")
            stage = Path(tmpdir) / "stage"
            incumbent = Path(tmpdir) / "live"
            incumbent.mkdir()

            def fake_train(
                task,
                _rows,
                _root,
                out_dir,
                _minimum,
                incumbent_dir=None,
            ):
                calls.append((out_dir, incumbent_dir))
                selected = metrics(0.80, 0.10, 0.85)
                return {
                    "task": task,
                    "ok": True,
                    "candidate_ok": True,
                    "selected_ok": True,
                    "selected_head": "candidate",
                    "candidate_metrics": selected,
                    "selected_metrics": selected,
                    "status": "fake staged selection",
                }

            trainer.train_single_label = fake_train
            sys.argv = [
                "engel_slm_trainer.py",
                "--root",
                str(root),
                "--tasks",
                "intent_router",
                "--data-dir",
                str(data_dir),
                "--out-dir",
                str(stage),
                "--incumbent-dir",
                str(incumbent),
                "--run-id",
                "cycle-20260809-test",
            ]
            with redirect_stdout(io.StringIO()):
                exit_code = trainer.main()
            report = json.loads(
                (stage / "LATEST_TRAINING.json").read_text(encoding="utf-8")
            )
            history = list((stage / "reports").glob("ENGEL_SLM_TRAINING_*.json"))
            check(
                "cli staging: run id and canonical directories bind every write to stage",
                exit_code == 0
                and report["run_id"] == "cycle-20260809-test"
                and Path(report["data_dir"]) == data_dir.resolve()
                and Path(report["output_dir"]) == stage.resolve()
                and Path(report["incumbent_dir"]) == incumbent.resolve()
                and report["staged"] is True
                and calls == [(stage.resolve(), incumbent.resolve())]
                and len(history) == 1
                and not (root / "reports").exists(),
                str(report),
            )
    finally:
        sys.argv = saved_argv
        trainer.train_single_label = saved_train


def main() -> int:
    run_offline_and_group_checks()
    run_hostile_pickle_check()
    run_selection_checks()
    run_style_bundle_check()
    run_cli_staging_check()
    failed = [name for name, ok, _detail in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED:")
        for name in failed:
            print(f"  - {name}")
        return 1
    print("verify_engel_slm_selection: GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
