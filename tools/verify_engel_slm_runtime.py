#!/usr/bin/env python3
"""Prove the SLM serving runtime keeps its three contracts (engel_slm_runtime.py).

The roster's trained artifacts sat unserved because there was no runtime; the
runtime is only safe to exist if these hold:

  1. GATES BY CODE -- a task serves ONLY when v2 LATEST_TRAINING.json records
     ok=true and authenticates its canonical artifact path and bytes. No report =>
     nothing.
  2. NEVER BLOCK -- before warm-up finishes every call answers None in
     microseconds; warm-up runs off-thread; a load failure never propagates.
  3. FAIL OPEN -- missing deps (this ROG python has no sklearn/joblib), missing
     artifacts, or predict errors yield None, never an exception into a turn.

The full predict path is driven through the loader/embedder seams with pure-python
fakes, so this verifier needs none of the ML stack. Wire-in checks assert the chat
service actually consults the runtime (warm at startup, intent feature in the
governor verdict, advisory telemetry at finalize) -- an unwired runtime is the
exact defect this build removes.

Exit 0 = safe to serve.
"""
from __future__ import annotations

import hashlib
import json
import pickle
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for _p in (ROOT, TOOLS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import engel_slm_runtime as rt  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))


REPORT = {
    "schema": rt.roster.TRAINING_REPORT_SCHEMA,
    "results": [
        {"task": "intent_router", "ok": True},
        {"task": "route_governor", "ok": True},
        {"task": "style_checks", "ok": True},
        {"task": "train_admit", "ok": True},
        {"task": "reply_grader", "ok": True},
        {"task": "failure_triage", "ok": False, "status": "REJECTED for label leakage"},
    ],
}


class FakeVectorizer:
    def transform(self, texts):
        return [[float(len(t))] for t in texts]


class FakeClassifier:
    classes_ = ["build", "chat", "meeting_room"]

    def predict_proba(self, features):
        return [[0.05, 0.90, 0.05]]

    def predict(self, features):
        return ["chat"]


class FakeAdmitClassifier:
    classes_ = ["admit", "reject"]

    def predict_proba(self, features):
        return [[0.82, 0.18]]

    def predict(self, features):
        return ["admit"]


class FakeReplyClassifier:
    classes_ = ["clean", "needed_repair"]

    def predict_proba(self, features):
        return [[0.78, 0.22]]


class FakeRouteClassifier:
    classes_ = ["defer_to_heuristics", "local"]

    def predict_proba(self, features):
        return [[0.08, 0.92]]


class FakeFailureClassifier:
    classes_ = ["repair_failed", "repair_succeeded"]

    def predict_proba(self, features):
        return [[0.30, 0.70]]


class FakeFailsHead:
    def predict(self, features):
        return ["fails"]


class FakePassesHead:
    def predict(self, features):
        return ["passes"]


def _mark_hostile_pickle_deserialized(sentinel: str) -> dict:
    Path(sentinel).write_text("unsafe deserialization reached", encoding="utf-8")
    return {}


class HostilePickle:
    """Payload whose reducer leaves durable proof if a loader touches it."""

    def __init__(self, sentinel: Path) -> None:
        self.sentinel = sentinel

    def __reduce__(self):
        return (_mark_hostile_pickle_deserialized, (str(self.sentinel),))


def artifact_for(task: str) -> dict:
    contract = {
        "schema": rt.roster.ARTIFACT_SCHEMA,
        "task_contract_version": rt.roster.task_spec(task).contract_version,
    }
    if task == "style_checks":
        return {
            **contract,
            "task": task,
            "backend": "tfidf_char",
            "heads": {"no_wrong_identity": FakeFailsHead(), "not_code_dump": FakePassesHead()},
            "vectorizer": FakeVectorizer(),
        }
    classifiers = {
        "train_admit": FakeAdmitClassifier(),
        "reply_grader": FakeReplyClassifier(),
        "route_governor": FakeRouteClassifier(),
        "failure_triage": FakeFailureClassifier(),
    }
    return {
        **contract,
        "task": task,
        "backend": "tfidf_char",
        "classifier": classifiers.get(task, FakeClassifier()),
        "vectorizer": FakeVectorizer(),
    }


def make_dir(tmp: Path, tasks: tuple[str, ...], report: dict | None) -> Path:
    directory = tmp / f"slm_{'_'.join(tasks) or 'empty'}"
    directory.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        (directory / f"engel_slm_{task}.joblib").write_bytes(b"placeholder")
    if report is not None:
        local_report = json.loads(json.dumps(report))
        for result in local_report.get("results") or []:
            task = str(result.get("task") or "")
            artifact = directory / f"engel_slm_{task}.joblib"
            if artifact.is_file():
                result["artifact"] = str(artifact)
                result["artifact_sha256"] = hashlib.sha256(
                    artifact.read_bytes()
                ).hexdigest()
        (directory / rt.TRAINING_REPORT_NAME).write_text(
            json.dumps(local_report), encoding="utf-8"
        )
    return directory


def fake_loader(runtime: rt.EngelSlmRuntime) -> None:
    runtime._load_artifact = lambda path, _payload: artifact_for(  # type: ignore[method-assign]
        path.name.replace("engel_slm_", "").replace(".joblib", "")
    )


def run_gate_enforcement(tmp: Path) -> None:
    directory = make_dir(
        tmp,
        tuple(rt.SERVABLE_TASKS),
        REPORT,
    )
    runtime = rt.EngelSlmRuntime(directory)
    eligibility = runtime.eligibility()
    check(
        "gates: eligibility follows the training report exactly",
        eligibility
        == {
            "intent_router": True,
            "route_governor": True,
            "style_checks": True,
            "train_admit": True,
            "reply_grader": True,
            "failure_triage": False,
        },
        f"got {eligibility}",
    )
    fake_loader(runtime)
    runtime.warm(background=False)
    check(
        "gates: only report-eligible artifacts load even when every roster file exists",
        runtime.is_ready()
        and sorted(runtime._artifacts)
        == ["intent_router", "reply_grader", "route_governor", "style_checks", "train_admit"],
        f"loaded={sorted(runtime._artifacts)}",
    )

    no_report = rt.EngelSlmRuntime(make_dir(tmp, ("intent_router",), None))
    fake_loader(no_report)
    no_report.warm(background=False)
    check(
        "gates: no training report => nothing serves (an unaudited model never enters the hot path)",
        not no_report.is_ready() and no_report.intent("hello") is None,
        f"status={no_report.status()}",
    )

    # The pack-fed newcomer gets the same treatment as every other roster entry: a
    # below-gate train_admit must not score anything just because its file shipped.
    below_gate = dict(REPORT)
    below_gate["results"] = [
        {"task": "intent_router", "ok": True},
        {"task": "train_admit", "ok": False, "status": "trained but BELOW the gate"},
    ]
    refused = rt.EngelSlmRuntime(
        make_dir(tmp / "below_gate", ("intent_router", "train_admit"), below_gate)
    )
    fake_loader(refused)
    refused.warm(background=False)
    check(
        "gates: a below-gate train_admit is refused even with its artifact on disk",
        refused.eligibility().get("train_admit") is False
        and "train_admit" not in refused._artifacts
        and refused.admit_score("a prompt", "a reply") is None,
        f"loaded={sorted(refused._artifacts)}",
    )

    # Executable artifacts are v2-only: legacy reports have no cryptographic binding.
    v2_dir = make_dir(tmp / "v2_hash", ("intent_router",), None)
    artifact_path = v2_dir / "engel_slm_intent_router.joblib"
    v2_report = {
        "schema": rt.roster.TRAINING_REPORT_SCHEMA,
        "results": [
            {
                "task": "intent_router",
                "ok": True,
                "artifact": str(artifact_path),
                "artifact_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
            }
        ],
    }
    (v2_dir / rt.TRAINING_REPORT_NAME).write_text(json.dumps(v2_report), encoding="utf-8")
    pinned = rt.EngelSlmRuntime(v2_dir)
    pinned._load_artifact = lambda _path, _payload: artifact_for(  # type: ignore[method-assign]
        "intent_router"
    )
    pinned.warm(background=False)
    check("gates: a correctly pinned v2 artifact loads", pinned.is_ready())
    prior_artifacts = dict(pinned._artifacts)
    reload_ok = pinned.reload("0" * 64, background=False)
    check(
        "gates: reload is hash-bound and preserves the serving roster on mismatch",
        reload_ok is False
        and pinned._artifacts == prior_artifacts
        and "sha256" in pinned.last_error,
        pinned.last_error,
    )

    sentinel = tmp / "hostile_pickle_was_deserialized"
    artifact_path.write_bytes(pickle.dumps(HostilePickle(sentinel)))
    mismatched = rt.EngelSlmRuntime(v2_dir)
    mismatched._load_artifact = (  # type: ignore[method-assign]
        lambda _path, payload: pickle.loads(payload)
    )
    mismatched.warm(background=False)
    check(
        "gates: a mismatched hostile pickle is refused before deserialization",
        not mismatched.is_ready()
        and "sha256" in mismatched.last_error
        and not sentinel.exists(),
        mismatched.last_error,
    )

    path_sentinel = tmp / "noncanonical_path_pickle_was_deserialized"
    path_payload = pickle.dumps(HostilePickle(path_sentinel))
    artifact_path.write_bytes(path_payload)
    v2_report["results"][0].update(
        {
            "artifact": str(v2_dir / "wrong-name.joblib"),
            "artifact_sha256": hashlib.sha256(path_payload).hexdigest(),
        }
    )
    (v2_dir / rt.TRAINING_REPORT_NAME).write_text(
        json.dumps(v2_report), encoding="utf-8"
    )
    noncanonical = rt.EngelSlmRuntime(v2_dir)
    noncanonical._load_artifact = (  # type: ignore[method-assign]
        lambda _path, payload: pickle.loads(payload)
    )
    noncanonical.warm(background=False)
    check(
        "gates: a noncanonical report path is refused before deserialization",
        not noncanonical.is_ready()
        and "path" in noncanonical.last_error
        and not path_sentinel.exists(),
        noncanonical.last_error,
    )

    legacy_sentinel = tmp / "legacy_pickle_was_deserialized"
    legacy_payload = pickle.dumps(HostilePickle(legacy_sentinel))
    artifact_path.write_bytes(legacy_payload)
    v2_report["schema"] = "engel_slm_training_report_v1"
    v2_report["results"][0].update(
        {
            "artifact": str(artifact_path),
            "artifact_sha256": hashlib.sha256(legacy_payload).hexdigest(),
        }
    )
    (v2_dir / rt.TRAINING_REPORT_NAME).write_text(
        json.dumps(v2_report), encoding="utf-8"
    )
    legacy = rt.EngelSlmRuntime(v2_dir)
    legacy._load_artifact = (  # type: ignore[method-assign]
        lambda _path, payload: pickle.loads(payload)
    )
    legacy.warm(background=False)
    check(
        "gates: an unpinned legacy report is refused before deserialization",
        not legacy.is_ready()
        and "v2 training report" in legacy.last_error
        and not legacy_sentinel.exists(),
        legacy.last_error,
    )


def run_reload_atomicity(tmp: Path) -> None:
    """Prove off-side reload is all-or-nothing for report-eligible heads."""
    release_report = {
        "schema": rt.roster.TRAINING_REPORT_SCHEMA,
        "results": [
            {"task": "intent_router", "ok": True},
            {"task": "style_checks", "ok": True},
            {"task": "failure_triage", "ok": False},
        ],
    }

    def report_digest(directory: Path) -> str:
        return hashlib.sha256(
            (directory / rt.TRAINING_REPORT_NAME).read_bytes()
        ).hexdigest()

    def serving_runtime(directory: Path) -> tuple[rt.EngelSlmRuntime, dict]:
        runtime = rt.EngelSlmRuntime(directory)
        old_artifacts = {
            "intent_router": {"release": "serving-old-intent"},
            "style_checks": {"release": "serving-old-style"},
        }
        old_state = {
            "artifacts": old_artifacts,
            "eligibility": {"intent_router": True, "style_checks": True},
            "report": {"release": "serving-old"},
            "embedder": object(),
            "cache": {"old prompt": {"label": "chat"}},
        }
        runtime._artifacts = old_state["artifacts"]
        runtime._eligibility = old_state["eligibility"]
        runtime._training_report = old_state["report"]
        runtime._embedder = old_state["embedder"]
        runtime._intent_cache = old_state["cache"]
        runtime._ready.set()
        return runtime, old_state

    def state_preserved(runtime: rt.EngelSlmRuntime, old_state: dict) -> bool:
        return (
            runtime._artifacts is old_state["artifacts"]
            and runtime._eligibility is old_state["eligibility"]
            and runtime._training_report is old_state["report"]
            and runtime._embedder is old_state["embedder"]
            and runtime._intent_cache is old_state["cache"]
            and runtime.is_ready()
        )

    original_loader = rt.EngelSlmRuntime._load_artifact
    try:
        rt.EngelSlmRuntime._load_artifact = (  # type: ignore[method-assign]
            lambda _self, path, _payload: artifact_for(
                path.name.replace("engel_slm_", "").replace(".joblib", "")
            )
        )

        # Report says two heads may serve, but only one file shipped. The candidate
        # may become internally "ready" with that one head; reload must still reject it.
        missing_dir = make_dir(
            tmp / "reload_missing",
            ("intent_router",),
            release_report,
        )
        missing_runtime, missing_old = serving_runtime(missing_dir)
        missing_ok = missing_runtime.reload(
            report_digest(missing_dir), background=False
        )
        check(
            "reload: a missing eligible head cannot replace the serving roster",
            missing_ok is False
            and state_preserved(missing_runtime, missing_old)
            and "incomplete" in missing_runtime.last_error
            and "style_checks" in missing_runtime.last_error,
            missing_runtime.last_error,
        )

        corrupt_dir = make_dir(
            tmp / "reload_corrupt",
            ("intent_router", "style_checks"),
            release_report,
        )

        def corrupt_one(_self, path: Path, _payload: bytes):
            if "style_checks" in path.name:
                raise RuntimeError("fixture corrupt eligible head")
            return artifact_for("intent_router")

        rt.EngelSlmRuntime._load_artifact = corrupt_one  # type: ignore[method-assign]
        corrupt_runtime, corrupt_old = serving_runtime(corrupt_dir)
        corrupt_ok = corrupt_runtime.reload(
            report_digest(corrupt_dir), background=False
        )
        check(
            "reload: a corrupt eligible head cannot replace the serving roster",
            corrupt_ok is False
            and state_preserved(corrupt_runtime, corrupt_old)
            and "incomplete" in corrupt_runtime.last_error
            and "style_checks" in corrupt_runtime.last_error
            and "corrupt" in corrupt_runtime.last_error,
            corrupt_runtime.last_error,
        )

        # The exact-set rule must not block a complete authenticated release.
        complete_dir = make_dir(
            tmp / "reload_complete",
            ("intent_router", "style_checks"),
            release_report,
        )
        rt.EngelSlmRuntime._load_artifact = (  # type: ignore[method-assign]
            lambda _self, path, _payload: artifact_for(
                path.name.replace("engel_slm_", "").replace(".joblib", "")
            )
        )
        complete_runtime, complete_old = serving_runtime(complete_dir)
        complete_ok = complete_runtime.reload(
            report_digest(complete_dir), background=False
        )
        check(
            "reload: a complete exact eligible roster swaps atomically",
            complete_ok is True
            and set(complete_runtime._artifacts) == {"intent_router", "style_checks"}
            and complete_runtime._artifacts is not complete_old["artifacts"]
            and complete_runtime._intent_cache == {}
            and complete_runtime.is_ready(),
            complete_runtime.last_error,
        )
    finally:
        rt.EngelSlmRuntime._load_artifact = original_loader


def run_never_block(tmp: Path) -> None:
    runtime = rt.EngelSlmRuntime(tmp / "nonexistent")
    started = time.perf_counter()
    results = [runtime.intent("x") for _ in range(200)]
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    check(
        "never-block: 200 not-ready calls answer None in well under a turn budget",
        all(r is None for r in results) and elapsed_ms < 200.0,
        f"{elapsed_ms:.1f} ms",
    )
    check(
        "never-block: warm() on a missing dir neither raises nor blocks readiness state",
        (runtime.warm(background=False) is None) and not runtime.is_ready(),
    )


def run_fail_open(tmp: Path) -> None:
    directory = make_dir(tmp, ("intent_router", "style_checks"), REPORT)
    runtime = rt.EngelSlmRuntime(directory)

    def exploding_loader(path: Path, _payload: bytes):
        if "intent_router" in path.name:
            raise RuntimeError("corrupt artifact")
        return artifact_for("style_checks")

    runtime._load_artifact = exploding_loader  # type: ignore[method-assign]
    runtime.warm(background=False)
    check(
        "fail-open: one corrupt artifact never sinks the rest",
        runtime.is_ready()
        and sorted(runtime._artifacts) == ["style_checks"]
        and runtime.intent("hello") is None
        and "intent_router" in runtime.last_error,
        f"loaded={sorted(runtime._artifacts)} err={runtime.last_error}",
    )

    embed_dir = make_dir(tmp / "embed", ("intent_router",), REPORT)
    embed_runtime = rt.EngelSlmRuntime(embed_dir)
    embed_runtime._load_artifact = lambda path, _payload: {  # type: ignore[method-assign]
        "task": "intent_router",
        "backend": "nomic_embed_text_v1_5_cpu",
        "classifier": FakeClassifier(),
        "vectorizer": None,
    }

    def no_embedder():
        raise FileNotFoundError("no nomic on this host")

    embed_runtime._load_embedder = no_embedder  # type: ignore[method-assign]
    embed_runtime.warm(background=False)
    check(
        "fail-open: embedding-backend artifact without an embedder is excluded, not crashed",
        not embed_runtime.is_ready() and embed_runtime.intent("hello") is None,
        f"status={embed_runtime.status()}",
    )


def run_predict_path(tmp: Path) -> None:
    directory = make_dir(
        tmp,
        ("intent_router", "route_governor", "style_checks", "reply_grader"),
        REPORT,
    )
    runtime = rt.EngelSlmRuntime(directory)
    fake_loader(runtime)
    runtime.warm(background=False)
    intent = runtime.intent("please build me a small tool")
    check(
        "predict: intent returns label/confidence/backend/latency from the gated artifact",
        isinstance(intent, dict)
        and intent.get("label") == "chat"
        and abs(float(intent.get("confidence", 0)) - 0.90) < 1e-6
        and intent.get("backend") == "tfidf_char"
        and "latency_ms" in intent,
        f"intent={intent}",
    )
    check("predict: empty prompt is refused, not embedded", runtime.intent("  ") is None)

    def poisoned(*_args, **_kwargs):
        raise RuntimeError("must not re-featurize a cached prompt")

    runtime._features = poisoned  # type: ignore[method-assign]
    cached = runtime.intent("please build me a small tool")
    check(
        "predict: repeated prompt is served from the per-turn cache (route + advisory share one embed)",
        isinstance(cached, dict) and cached.get("label") == "chat",
        f"cached={cached}",
    )
    fresh = runtime.intent("a different prompt entirely")
    check(
        "predict: a featurizer error on a fresh prompt fails open to None",
        fresh is None and "intent" in runtime.last_error,
    )

    flags = rt.EngelSlmRuntime(directory)
    fake_loader(flags)
    flags.warm(background=False)
    style = flags.style_flags("prompt", "reply text")
    check(
        "predict: style_flags reports failing heads and the checked set (gated heads only)",
        isinstance(style, dict)
        and style.get("failing_checks") == ["no_wrong_identity"]
        and style.get("checked") == ["no_wrong_identity", "not_code_dump"],
        f"style={style}",
    )

    reply = flags.reply_quality("prompt", "a complete reply")
    check(
        "predict: the now-gated reply_grader has a real serving method",
        isinstance(reply, dict)
        and reply.get("label") == "clean"
        and abs(float(reply.get("confidence", 0)) - 0.78) < 1e-6,
        f"reply={reply}",
    )

    route = flags.route_advice(
        {"discipline": "engineering", "interactive": False, "outcome": "must_drop"}
    )
    check(
        "predict: route_governor scores canonical features and cannot receive an outcome field",
        isinstance(route, dict)
        and route.get("label") == "local"
        and "outcome" not in rt.roster.canonical_route_features(
            {"discipline": "engineering", "outcome": "must_drop"}
        ),
        f"route={route}",
    )

    admit_runtime = rt.EngelSlmRuntime(make_dir(tmp, ("train_admit",), REPORT))
    fake_loader(admit_runtime)
    admit_runtime.warm(background=False)
    admit = admit_runtime.admit_score("explain the receipt rule", "x" * 400)
    check(
        "predict: admit_score returns label/confidence/backend/latency from the gated artifact",
        isinstance(admit, dict)
        and admit.get("label") == "admit"
        and abs(float(admit.get("confidence", 0)) - 0.82) < 1e-6
        and admit.get("backend") == "tfidf_char"
        and "latency_ms" in admit,
        f"admit={admit}",
    )
    check(
        "predict: admit_score refuses a half-empty pair (off-distribution, so no opinion)",
        admit_runtime.admit_score("", "a reply") is None
        and admit_runtime.admit_score("a prompt", "   ") is None,
    )

    admit_runtime._features = poisoned  # type: ignore[method-assign]
    check(
        "predict: an admit_score featurizer error fails open to None (never an exception into a turn)",
        admit_runtime.admit_score("fresh prompt", "fresh reply") is None
        and "train_admit" in admit_runtime.last_error,
        f"err={admit_runtime.last_error}",
    )

    failure_report = {
        "schema": rt.roster.TRAINING_REPORT_SCHEMA,
        "results": [{"task": "failure_triage", "ok": True}],
    }
    failure_runtime = rt.EngelSlmRuntime(
        make_dir(tmp / "failure", ("failure_triage",), failure_report)
    )
    fake_loader(failure_runtime)
    failure_runtime.warm(background=False)
    outlook = failure_runtime.failure_outlook(
        "build a parser", "assert", "expected 4 but received 3"
    )
    check(
        "predict: failure_triage exposes a bounded Forge repair outlook",
        isinstance(outlook, dict) and outlook.get("label") == "repair_succeeded",
        f"outlook={outlook}",
    )
    check(
        "predict: failure_triage refuses success/no-goal inputs as off-distribution",
        failure_runtime.failure_outlook("goal", "none", "") is None
        and failure_runtime.failure_outlook("", "assert", "failed") is None,
    )


def run_single_source_and_wireup() -> None:
    runtime_src = (TOOLS / "engel_slm_runtime.py").read_text(encoding="utf-8")
    check(
        "single-source: reply-shape features import from engel_slm_trainer (no drifting copy)",
        "from engel_slm_trainer import structural_features" in runtime_src
        and "def structural_features" not in runtime_src,
    )
    # Serving skew has no symptom: the classifier just gets quietly worse. The two
    # lists deciding WHICH tasks get shape features must therefore agree exactly.
    import engel_slm_trainer as trainer  # noqa: PLC0415 -- dependency-free import

    check(
        "single-source: trainer and runtime agree on which tasks get structural features",
        tuple(trainer.REPLY_SHAPE_TASKS) == tuple(rt.REPLY_SHAPE_TASKS),
        f"trainer={trainer.REPLY_SHAPE_TASKS} runtime={rt.REPLY_SHAPE_TASKS}",
    )
    service_src = (TOOLS / "engel_main_server_chat_http_service.py").read_text(
        encoding="utf-8"
    )
    check(
        "wireup: service warms the runtime at startup (loads happen off-turn)",
        "get_slm_runtime().warm()" in service_src,
    )
    check(
        "wireup: finalize attaches slm_advisory behind the ENGEL_SLM_ADVISORY_ENABLED kill switch",
        "_attach_slm_advisory(receipt, prompt, reply)" in service_src
        and 'ENGEL_SLM_ADVISORY_ENABLED' in service_src
        and 'advisory["reply_quality"]' in service_src,
    )
    check(
        "wireup: governor route features carry intent + intent_confidence (Phase A corpus enrichment)",
        'features["intent"]' in service_src
        and 'features["intent_confidence"]' in service_src,
    )
    advisory_fn = service_src.split("def _attach_slm_advisory", 1)[1].split("\ndef ", 1)[0]
    check(
        "wireup: advisory is telemetry-only -- it never touches the reply or any eligibility flag",
        "assistant_reply" not in advisory_fn
        and "training_sample_eligible" not in advisory_fn
        and 'receipt["slm_advisory"]' in advisory_fn,
    )
    check(
        "wireup: route decisions and route SLM disagreements land in ordinary chat receipts",
        'receipt["governor_route_decision"]' in service_src
        and "slm.route_advice(features)" in service_src,
    )
    forge_src = (ROOT / "engel_code_forge.py").read_text(encoding="utf-8")
    check(
        "wireup: Code Forge records failure-triage telemetry without using it as a retry gate",
        "runtime.failure_outlook(" in forge_src
        and 'round_rec["slm_failure_triage"] = outlook' in forge_src,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="engel_slm_runtime_") as tmpdir:
        tmp = Path(tmpdir)
        run_gate_enforcement(tmp)
        run_reload_atomicity(tmp)
        run_never_block(tmp)
        run_fail_open(tmp)
        run_predict_path(tmp)
    run_single_source_and_wireup()
    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED:")
        for name in failed:
            print(f"  - {name}")
        return 1
    print("verify_engel_slm_runtime: GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
