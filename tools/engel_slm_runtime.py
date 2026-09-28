"""In-process serving for Engel's receipt-trained SLMs -- the missing hot-path half.

engel_slm_trainer.py produces kilobyte classifiers whose stated purpose is
"inference in milliseconds inside the chat hot path" -- and until 2026-07-31
nothing loaded them: four trained artifacts sat in models-active/slm with zero
references from the chat service. This runtime closes that gap, under three
contracts a reviewer should be able to challenge:

1. GATES ARE ENFORCED BY CODE, NOT MEMORY. A task serves only when the roster's
   v2 LATEST_TRAINING.json records it as having met BOTH mandatory gates and
   authenticates the canonical artifact path and bytes. A stale, swapped,
   unpinned, below-gate, or leakage-rejected file is refused before deserialization.
2. NEVER BLOCK A TURN. warm() loads artifacts and the embedding backend on a
   background thread; until it finishes, every call answers None ("no opinion")
   in microseconds. A chat turn must never pay a model-load.
3. FAIL OPEN, ADVISORY ONLY. Missing deps (the ROG python has no sklearn/
   joblib/sentence_transformers -- by design), missing artifacts, or a predict
   error all yield None. Callers treat None as advisory-absent; deterministic
   gates keep deciding. This mirrors the Governor's route fail-open contract.

Feature construction MIRRORS the trainer exactly (a serving skew here is a
silent accuracy collapse): nomic embeddings + structural_features for reply
tasks on the embedding backend; bare TF-IDF (no structural augment) on the
fallback backend. structural_features is imported from the trainer -- single
source, same rule as the contract-echo markers.

2026-08-01: train_admit joins the roster, labelled from the prompt-training packs.
Its consumer is the prompt-training runner, NOT the chat service: the runner records
admit_score() beside its own authoritative verdict as a shadow prediction, so the two
can be compared before anyone proposes the model decide anything.

Verifier: tools/verify_engel_slm_runtime.py.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import engel_slm_roster as roster
from engel_local_tokenizer import NOMIC_DIRS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# First existing directory wins: explicit override, the CT roster home, then a
# ROG-side mirror for local runs.
_DEFAULT_MODEL_DIRS = (
    os.environ.get("ENGEL_SLM_MODEL_DIR", ""),
    "/opt/engel/models-active/slm",
    str(ROOT / "runtime" / "slm_models"),
)

TRAINING_REPORT_NAME = "LATEST_TRAINING.json"
SERVABLE_TASKS = roster.KNOWN_TASKS
# Tasks whose features augment the embedding with reply-shape numbers. Kept as one
# tuple mirroring engel_slm_trainer.REPLY_SHAPE_TASKS: if these two lists ever drift,
# serving silently feeds the classifier a different feature width than it trained on.
REPLY_SHAPE_TASKS = roster.REPLY_SHAPE_TASKS
_INTENT_CACHE_MAX = 32


class EngelSlmRuntime:
    def __init__(self, model_dir: str | Path | None = None) -> None:
        self._explicit_dir = str(model_dir) if model_dir else ""
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._warm_thread: threading.Thread | None = None
        self._artifacts: dict[str, Any] = {}
        self._eligibility: dict[str, bool] = {}
        self._training_report: dict[str, Any] = {}
        self._embedder: Any = None
        self._intent_cache: dict[str, dict[str, Any]] = {}
        self.last_error = ""

    # ------------------------------------------------------------------ paths
    def model_dir(self) -> Path | None:
        candidates = (
            [self._explicit_dir] if self._explicit_dir else list(_DEFAULT_MODEL_DIRS)
        )
        for candidate in candidates:
            if candidate and Path(candidate).is_dir():
                return Path(candidate)
        return None

    # ------------------------------------------------------------- gate logic
    def load_report(self) -> dict[str, Any]:
        directory = self.model_dir()
        if directory is None:
            return {}
        path = directory / TRAINING_REPORT_NAME
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 -- absent report => nothing serves
            self.last_error = f"training report unreadable: {type(exc).__name__}"
            return {}
        return report if isinstance(report, dict) else {}

    def eligibility(self) -> dict[str, bool]:
        """{task: may_serve}. A task is servable ONLY when its latest training
        result says ok=True -- which the trainer sets only when both mandatory
        gates passed. No report => nothing serves (fail closed on eligibility;
        an unaudited model must not enter the hot path)."""
        report = self.load_report()
        eligibility = {task: False for task in SERVABLE_TASKS}
        for result in report.get("results") or []:
            if not isinstance(result, dict):
                continue
            task = str(result.get("task") or "")
            if task in eligibility:
                eligibility[task] = result.get("ok") is True
        return eligibility

    def _report_results(self, report: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {
            str(result.get("task") or ""): result
            for result in report.get("results") or []
            if isinstance(result, dict) and str(result.get("task") or "") in SERVABLE_TASKS
        }

    def _validated_artifact_payload(
        self,
        task: str,
        directory: Path,
        path: Path,
        report: dict[str, Any],
        result: dict[str, Any],
    ) -> tuple[Path, bytes] | None:
        """Authenticate an artifact's report, canonical path, and bytes.

        Joblib artifacts are pickle-capable. Nothing may call ``joblib.load`` until
        this method has accepted the report and hashed the exact immutable byte
        buffer that will be deserialized. Legacy reports have no cryptographic
        binding, so they remain readable as history but are not executable.
        """
        if report.get("schema") != roster.TRAINING_REPORT_SCHEMA:
            self.last_error = f"{task}: executable artifact requires a v2 training report"
            return None
        if str(result.get("task") or "") != task:
            self.last_error = f"{task}: training report result does not identify the task"
            return None

        expected_name = f"engel_slm_{task}.joblib"
        recorded_name = (
            str(result.get("artifact") or "").replace("\\", "/").rsplit("/", 1)[-1]
        )
        if recorded_name != expected_name:
            self.last_error = f"{task}: training report artifact path is not canonical"
            return None
        try:
            model_root = directory.resolve(strict=True)
            resolved_path = path.resolve(strict=True)
        except OSError as exc:
            self.last_error = f"{task}: artifact path failed: {type(exc).__name__}: {exc}"
            return None
        if resolved_path.parent != model_root or resolved_path.name != expected_name:
            self.last_error = f"{task}: artifact escaped the canonical model directory"
            return None

        expected_hash = str(result.get("artifact_sha256") or "").casefold()
        if len(expected_hash) != 64 or any(
            ch not in "0123456789abcdef" for ch in expected_hash
        ):
            self.last_error = f"{task}: v2 report omitted a valid artifact_sha256"
            return None
        try:
            payload = resolved_path.read_bytes()
        except OSError as exc:
            self.last_error = f"{task}: artifact read failed: {type(exc).__name__}: {exc}"
            return None
        if hashlib.sha256(payload).hexdigest() != expected_hash:
            self.last_error = f"{task}: artifact sha256 does not match the training report"
            return None
        return resolved_path, payload

    def _artifact_matches_report(
        self,
        task: str,
        artifact: dict[str, Any],
    ) -> bool:
        """Validate the deserialized contract after bytes were authenticated."""
        if str(artifact.get("task") or "") != task:
            self.last_error = f"{task}: artifact declares task {artifact.get('task')!r}"
            return False
        spec = roster.task_spec(task)
        if artifact.get("schema") != roster.ARTIFACT_SCHEMA:
            self.last_error = f"{task}: v2 report points to an unversioned artifact"
            return False
        if artifact.get("task_contract_version") != spec.contract_version:
            self.last_error = f"{task}: artifact task contract version mismatch"
            return False
        return True

    # -------------------------------------------------------------- seams
    # Kept as small named methods so the verifier can drive the full predict
    # path with fakes on a machine that has none of the ML dependencies.
    def _load_artifact(self, path: Path, payload: bytes) -> Any:
        import joblib  # lazy: absent on ROG by design

        # Deserialize the same immutable bytes authenticated above. ``path`` stays
        # in this seam so dependency-free verifiers can identify the fake task.
        return joblib.load(io.BytesIO(payload))

    def _load_embedder(self) -> Any:
        from engel_local_transformer import load_embedder

        return load_embedder()

    def _embed(self, texts: list[str]) -> Any:
        return self._embedder.encode(texts, batch_size=16, show_progress_bar=False)

    # ------------------------------------------------------------- warm-up
    def warm(self, background: bool = True) -> None:
        """Load eligible artifacts (and the embedder when any needs it) without
        ever making a chat turn wait. Idempotent."""
        if self._ready.is_set():
            return
        if background:
            with self._lock:
                if self._warm_thread is None or not self._warm_thread.is_alive():
                    self._warm_thread = threading.Thread(
                        target=self._warm_inner,
                        name="engel-slm-runtime-warm",
                        daemon=True,
                    )
                    self._warm_thread.start()
            return
        self._warm_inner()

    def reload(self, expected_report_sha256: str, background: bool = True) -> bool:
        """Load a new authenticated roster off to the side, then swap it in.

        Reload is explicit and hash-bound.  The currently serving roster remains intact
        until a complete candidate runtime has authenticated and loaded every head the
        report declares eligible. A bad report, missing dependency, corrupt artifact, or
        partial release therefore cannot create a mixed/partial live roster. Callers may
        schedule the work so no chat turn waits.
        """
        expected = str(expected_report_sha256 or "").strip().casefold()
        if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
            self.last_error = "reload requires the expected 64-hex training-report sha256"
            return False
        directory = self.model_dir()
        if directory is None:
            self.last_error = "reload refused: no SLM model directory present"
            return False
        report_path = directory / TRAINING_REPORT_NAME
        try:
            before = hashlib.sha256(report_path.read_bytes()).hexdigest()
        except OSError as exc:
            self.last_error = f"reload report unreadable: {type(exc).__name__}: {exc}"
            return False
        if before != expected:
            self.last_error = "reload report sha256 does not match the requested release"
            return False

        outcome = {"swapped": False}

        def load_and_swap() -> None:
            candidate = EngelSlmRuntime(directory)
            candidate._warm_inner()
            expected_tasks = {
                task for task, allowed in candidate._eligibility.items() if allowed
            }
            loaded_tasks = set(candidate._artifacts)
            missing_tasks = sorted(expected_tasks - loaded_tasks)
            unexpected_tasks = sorted(loaded_tasks - expected_tasks)
            if not expected_tasks:
                self.last_error = (
                    candidate.last_error
                    or "reload refused: candidate report declares no eligible heads"
                )
                return
            if loaded_tasks != expected_tasks:
                detail = candidate.last_error or "eligible artifact did not load"
                self.last_error = (
                    "reload refused: candidate roster is incomplete; "
                    f"expected={sorted(expected_tasks)!r}, "
                    f"loaded={sorted(loaded_tasks)!r}, "
                    f"missing={missing_tasks!r}, "
                    f"unexpected={unexpected_tasks!r}; {detail}"
                )
                return
            if not candidate.is_ready():
                self.last_error = (
                    candidate.last_error
                    or "reload refused: complete candidate roster is not ready"
                )
                return
            try:
                after = hashlib.sha256(report_path.read_bytes()).hexdigest()
            except OSError as exc:
                self.last_error = f"reload report recheck failed: {type(exc).__name__}: {exc}"
                return
            if after != expected:
                self.last_error = "reload report changed while candidate artifacts were loading"
                return
            with self._lock:
                self._artifacts = candidate._artifacts
                self._eligibility = candidate._eligibility
                self._training_report = candidate._training_report
                self._embedder = candidate._embedder
                self._intent_cache.clear()
                self.last_error = candidate.last_error
                self._ready.set()
                outcome["swapped"] = True

        if background:
            with self._lock:
                if self._warm_thread is not None and self._warm_thread.is_alive():
                    self.last_error = "reload refused: another warm/reload is already running"
                    return False
                self._warm_thread = threading.Thread(
                    target=load_and_swap,
                    name="engel-slm-runtime-reload",
                    daemon=True,
                )
                self._warm_thread.start()
            return True
        load_and_swap()
        return outcome["swapped"]

    def _warm_inner(self) -> None:
        try:
            directory = self.model_dir()
            if directory is None:
                self.last_error = "no SLM model directory present"
                return
            report = self.load_report()
            self._training_report = report
            eligibility = {task: False for task in SERVABLE_TASKS}
            for task, result in self._report_results(report).items():
                eligibility[task] = result.get("ok") is True
            self._eligibility = eligibility
            report_results = self._report_results(report)
            loaded: dict[str, Any] = {}
            needs_embedder = False
            for task, allowed in eligibility.items():
                if not allowed:
                    continue
                path = directory / f"engel_slm_{task}.joblib"
                if not path.is_file():
                    continue
                validated = self._validated_artifact_payload(
                    task, directory, path, report, report_results.get(task, {})
                )
                if validated is None:
                    continue
                validated_path, payload = validated
                try:
                    artifact = self._load_artifact(validated_path, payload)
                except Exception as exc:  # noqa: BLE001 -- one bad artifact never sinks the rest
                    self.last_error = f"{task}: {type(exc).__name__}: {exc}"
                    continue
                if isinstance(artifact, dict) and self._artifact_matches_report(task, artifact):
                    loaded[task] = artifact
                    if str(artifact.get("backend") or "").startswith("nomic"):
                        needs_embedder = True
            if needs_embedder and loaded:
                try:
                    self._embedder = self._load_embedder()
                except Exception as exc:  # noqa: BLE001
                    self.last_error = f"embedder: {type(exc).__name__}: {exc}"
                    # Embedding-backend artifacts cannot serve without it.
                    loaded = {
                        task: artifact
                        for task, artifact in loaded.items()
                        if not str(artifact.get("backend") or "").startswith("nomic")
                    }
            self._artifacts = loaded
            if loaded:
                self._ready.set()
        except Exception as exc:  # noqa: BLE001 -- warm-up must never propagate
            self.last_error = f"warm: {type(exc).__name__}: {exc}"

    def is_ready(self) -> bool:
        return self._ready.is_set()

    def status(self) -> dict[str, Any]:
        return {
            "ready": self.is_ready(),
            "model_dir": str(self.model_dir() or ""),
            "eligibility": dict(self._eligibility),
            "loaded_tasks": sorted(self._artifacts),
            "embedder_loaded": self._embedder is not None,
            "last_error": self.last_error,
            "roster": roster.roster_snapshot(self._training_report.get("results") or []),
        }

    # ------------------------------------------------------------- features
    def _features(self, task: str, texts: list[str], artifact: dict[str, Any]) -> Any:
        backend = str(artifact.get("backend") or "")
        if backend.startswith("nomic"):
            dense = self._embed(texts)
            # Mirror the trainer: structural augmentation applies to reply-shape
            # tasks on the EMBEDDING backend only (the tfidf path never augments).
            if task in REPLY_SHAPE_TASKS:
                import numpy as np

                from engel_slm_trainer import structural_features  # single source

                extra = np.asarray(
                    [structural_features(t) for t in texts], dtype="float32"
                )
                return np.hstack([np.asarray(dense, dtype="float32"), extra])
            return dense
        vectorizer = artifact.get("vectorizer")
        if vectorizer is None:
            raise ValueError(f"{task}: tfidf backend artifact without a vectorizer")
        return vectorizer.transform(texts)

    # ------------------------------------------------------------- serving
    def intent(self, prompt: str) -> dict[str, Any] | None:
        """Route intent for a prompt: {'label', 'confidence', 'backend',
        'latency_ms'} or None (not ready / not eligible / any failure)."""
        if not self._ready.is_set():
            return None
        artifact = self._artifacts.get("intent_router")
        if not isinstance(artifact, dict):
            return None
        text = str(prompt or "").strip()
        if not text:
            return None
        cache_key = text[:2000]
        cached = self._intent_cache.get(cache_key)
        if cached is not None:
            return dict(cached)
        started = time.perf_counter()
        try:
            features = self._features("intent_router", [text], artifact)
            clf = artifact.get("classifier")
            probabilities = clf.predict_proba(features)[0]
            best = int(max(range(len(probabilities)), key=probabilities.__getitem__))
            result = {
                "label": str(clf.classes_[best]),
                "confidence": round(float(probabilities[best]), 4),
                "backend": str(artifact.get("backend") or ""),
                "latency_ms": round((time.perf_counter() - started) * 1000.0, 1),
            }
        except Exception as exc:  # noqa: BLE001 -- advisory absent, never an error into a turn
            self.last_error = f"intent: {type(exc).__name__}: {exc}"
            return None
        if len(self._intent_cache) >= _INTENT_CACHE_MAX:
            self._intent_cache.clear()
        self._intent_cache[cache_key] = result
        return dict(result)

    def _single_label_score(self, task: str, text: str) -> dict[str, Any] | None:
        if not self._ready.is_set():
            return None
        artifact = self._artifacts.get(task)
        if not isinstance(artifact, dict) or not text.strip():
            return None
        started = time.perf_counter()
        try:
            features = self._features(task, [text], artifact)
            clf = artifact.get("classifier")
            probabilities = clf.predict_proba(features)[0]
            best = int(max(range(len(probabilities)), key=probabilities.__getitem__))
            return {
                "label": str(clf.classes_[best]),
                "confidence": round(float(probabilities[best]), 4),
                "backend": str(artifact.get("backend") or ""),
                "latency_ms": round((time.perf_counter() - started) * 1000.0, 1),
            }
        except Exception as exc:  # noqa: BLE001 -- advisory absent, never a turn failure
            self.last_error = f"{task}: {type(exc).__name__}: {exc}"
            return None

    def route_advice(self, features: dict[str, Any]) -> dict[str, Any] | None:
        """Shadow-only route suggestion; deterministic Governor T0 still decides."""
        canonical = roster.canonical_route_features(features)
        if not canonical:
            return None
        return self._single_label_score("route_governor", roster.route_feature_text(canonical))

    def style_flags(self, prompt: str, reply: str) -> dict[str, Any] | None:
        """Predicted style-check failures for a reply. Only heads that met their
        per-head gate exist in the artifact, so every head here is servable.
        Returns {'failing_checks', 'checked', 'backend', 'latency_ms'} or None."""
        if not self._ready.is_set():
            return None
        artifact = self._artifacts.get("style_checks")
        if not isinstance(artifact, dict):
            return None
        heads = artifact.get("heads")
        if not isinstance(heads, dict) or not heads:
            return None
        text = f"PROMPT: {prompt or ''}\nREPLY: {reply or ''}"
        started = time.perf_counter()
        try:
            features = self._features("style_checks", [text], artifact)
            failing = []
            for check_name, clf in sorted(heads.items()):
                if str(clf.predict(features)[0]) == "fails":
                    failing.append(check_name)
            return {
                "failing_checks": failing,
                "checked": sorted(heads),
                "backend": str(artifact.get("backend") or ""),
                "latency_ms": round((time.perf_counter() - started) * 1000.0, 1),
            }
        except Exception as exc:  # noqa: BLE001
            self.last_error = f"style_flags: {type(exc).__name__}: {exc}"
            return None

    def reply_quality(self, prompt: str, reply: str) -> dict[str, Any] | None:
        """Shadow score from the gated reply_grader head."""
        prompt_text = str(prompt or "").strip()
        reply_text = str(reply or "").strip()
        if not prompt_text or not reply_text:
            return None
        return self._single_label_score(
            "reply_grader", f"PROMPT: {prompt_text}\nREPLY: {reply_text}"
        )

    def admit_score(self, prompt: str, reply: str) -> dict[str, Any] | None:
        """Would this reply have been admitted as training material?

        A learned second opinion on the Governor's admit question, trained on the
        prompt-training packs where the runner's own verdict is the label. Returns
        {'label' ('admit'|'reject'), 'confidence', 'backend', 'latency_ms'} or None.

        ADVISORY ONLY, and deliberately not wired into any gate. The runner's rule
        stays the authority on eligibility; this records a SHADOW prediction beside it
        so the two can be compared over a few hundred turns before anyone argues the
        model should decide anything. A classifier that quietly started admitting
        samples would be corrupting the corpus it was trained from.

        No cache here, unlike intent(): admit is asked once per turn on text that is
        different every time, so a cache would only be a memory leak with a hit rate
        of zero.
        """
        prompt_text = str(prompt or "").strip()
        reply_text = str(reply or "").strip()
        if not prompt_text or not reply_text:
            # The trainer skips pack rows missing either half, so a half-empty pair is
            # off-distribution: no opinion beats a confident guess about text it has
            # never seen.
            return None
        return self._single_label_score(
            "train_admit", f"PROMPT: {prompt_text}\nREPLY: {reply_text}"
        )

    def failure_outlook(
        self, goal: str, error_class: str, diagnostic: str
    ) -> dict[str, Any] | None:
        """Shadow prediction of whether one bounded Forge repair will succeed."""
        goal_text = str(goal or "").strip()
        class_text = str(error_class or "").strip()
        if not goal_text or not class_text or class_text == "none":
            return None
        text = (
            f"GOAL: {goal_text}\n"
            f"ERROR_CLASS: {class_text}\n"
            f"DIAGNOSTIC: {str(diagnostic or '').strip()}"
        )
        return self._single_label_score("failure_triage", text)


_RUNTIME: EngelSlmRuntime | None = None
_RUNTIME_LOCK = threading.Lock()


def get_slm_runtime() -> EngelSlmRuntime:
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            _RUNTIME = EngelSlmRuntime()
        return _RUNTIME
