#!/usr/bin/env python3
"""Train Engel's small language models from the receipt-derived datasets.

Design decisions a reviewer should be able to challenge:

* These jobs (does this reply need repair? will a bounded repair work? which lane fits
  this prompt?) are CLASSIFICATION, so the model is a sentence embedding plus a linear
  head, not a fine-tuned generative model. It trains in seconds on CPU, the artifact
  is kilobytes, and inference is milliseconds inside the chat hot path.
* It must not touch the GPU. The RTX 2070 is ~86% full holding the chat model
  (7004/8192 MiB); fine-tuning there would either contend for VRAM or force a chat
  outage, and neither is worth it for a classifier.
* Features come from Engel's own local nomic-embed model when it loads, else a
  character n-gram TF-IDF fallback. Both are fully offline. The backend actually used
  is recorded, because "which features" changes how results should be read.
* Every report includes the MAJORITY-CLASS BASELINE. reply_grader is 75% "clean", so
  a model that always says "clean" scores 75% accuracy and is worthless -- accuracy
  alone would hide that, so per-class recall and macro-F1 decide pass/fail.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import tempfile
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# (2026-08-09, operator: local by construction.) The docstring said "fully offline" but a
# live probe caught sentence-transformers sending an unauthenticated HF Hub request while
# loading the LOCAL nomic dir. The runtime already pins these; the trainer now does too,
# before any transformers-family import can happen.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

import engel_slm_roster as roster

DEFAULT_ROOT = Path("/opt/engel")
NOMIC_DIR = "models-active/hf-src/nomic-embed-text-v1.5"
TRAINING_REPORT_NAME = "LATEST_TRAINING.json"

# A model that cannot beat "always guess the biggest class" by this margin is not
# worth deploying into a hot path.
MIN_MACRO_F1 = 0.60
MIN_LIFT_OVER_BASELINE = 0.03


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validated_run_id(value: str) -> str:
    run_id = str(value or "").strip()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if not run_id or len(run_id) > 128 or any(char not in allowed for char in run_id):
        raise ValueError("run_id must be 1-128 characters from [A-Za-z0-9._-]")
    return run_id


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


# Tasks that judge a REPLY given its prompt. They share one text layout because
# structural_features() splits on the "REPLY:" marker to isolate the reply half, and
# they all get the shape features that layout unlocks.
REPLY_SHAPE_TASKS = roster.REPLY_SHAPE_TASKS


def _text_for(row: dict[str, Any], task: str) -> str:
    if task in REPLY_SHAPE_TASKS:
        return f"PROMPT: {row.get('prompt', '')}\nREPLY: {row.get('reply', '')}"
    if task == "intent_router":
        return str(row.get("prompt", ""))
    if task == "route_governor":
        return roster.route_feature_text(row.get("features"))
    if task == "failure_triage":
        return (
            f"GOAL: {row.get('goal', '')}\n"
            f"ERROR_CLASS: {row.get('error_class', '')}\n"
            f"DIAGNOSTIC: {row.get('diagnostic', '')}"
        )
    raise ValueError(f"no text contract for SLM task {task!r}")


def _canonical_prompt_group(row: dict[str, Any], task: str) -> str:
    """Stable group key that keeps prompt duplicates on one side of a split."""
    prompt = str(row.get("prompt") or "")
    source = prompt if prompt.strip() else _text_for(row, task)
    normalized = unicodedata.normalize("NFKC", source)
    return " ".join(normalized.casefold().split())


def _grouped_train_test_indices(
    groups: list[str], labels: list[str] | None = None, test_size: float = 0.25
) -> tuple[list[int], list[int]]:
    """Deterministically split whole canonical-prompt groups.

    The former row-wise split let repeated prompts appear in both partitions. This
    standard-library splitter keeps groups intact and greedily approximates the target
    size and, for single-label tasks, the class distribution. It fails closed when a
    class exists in fewer than two prompt groups because no honest held-out score is
    possible in that case.
    """
    if not groups or not 0.0 < test_size < 1.0:
        raise ValueError("grouped split requires rows and 0 < test_size < 1")
    if labels is not None and len(labels) != len(groups):
        raise ValueError("group and label lengths differ")

    by_group: dict[str, list[int]] = {}
    for index, group in enumerate(groups):
        by_group.setdefault(group, []).append(index)
    if len(by_group) < 2:
        raise ValueError("fewer than two distinct canonical prompt groups")

    label_names = sorted(set(labels or []))
    group_label_counts: dict[str, dict[str, int]] = {}
    total_label_counts = {label: 0 for label in label_names}
    label_groups = {label: set() for label in label_names}
    for group, indices in by_group.items():
        counts = {label: 0 for label in label_names}
        for index in indices:
            if labels is not None:
                label = labels[index]
                counts[label] += 1
                total_label_counts[label] += 1
                label_groups[label].add(group)
        group_label_counts[group] = counts
    too_few = [label for label, values in label_groups.items() if len(values) < 2]
    if too_few:
        raise ValueError(
            "classes occur in fewer than two canonical prompt groups: "
            + ", ".join(too_few)
        )

    target_rows = max(1, round(len(groups) * test_size))
    target_labels = {
        label: total_label_counts[label] * test_size for label in label_names
    }
    ordered_groups = sorted(
        by_group,
        key=lambda value: (hashlib.sha256(value.encode("utf-8")).hexdigest(), value),
    )
    selected: set[str] = set()
    selected_label_counts = {label: 0 for label in label_names}
    selected_rows = 0

    def may_select(group: str) -> bool:
        remaining = set(by_group) - selected - {group}
        if not remaining:
            return False
        return all(
            any(candidate in label_groups[label] for candidate in remaining)
            for label in label_names
        )

    def score(group: str) -> tuple[float, float, str]:
        new_rows = selected_rows + len(by_group[group])
        row_error = abs(new_rows - target_rows) / max(1, len(groups))
        label_error = sum(
            abs(
                selected_label_counts[label]
                + group_label_counts[group][label]
                - target_labels[label]
            )
            / max(1, total_label_counts[label])
            for label in label_names
        )
        return label_error, row_error, group

    while True:
        has_every_test_label = all(selected_label_counts[label] > 0 for label in label_names)
        if selected and selected_rows >= target_rows and has_every_test_label:
            break
        candidates = [
            group for group in ordered_groups if group not in selected and may_select(group)
        ]
        if not candidates:
            raise ValueError("could not form a grouped split with every class on both sides")
        chosen = min(candidates, key=score)
        selected.add(chosen)
        selected_rows += len(by_group[chosen])
        for label in label_names:
            selected_label_counts[label] += group_label_counts[chosen][label]

    test_indices = sorted(index for group in selected for index in by_group[group])
    train_indices = sorted(set(range(len(groups))) - set(test_indices))
    train_groups = {groups[index] for index in train_indices}
    test_groups = {groups[index] for index in test_indices}
    if not train_indices or not test_indices or train_groups & test_groups:
        raise ValueError("grouped split produced an empty side or prompt overlap")
    if labels is not None:
        expected = set(labels)
        if {labels[index] for index in train_indices} != expected or {
            labels[index] for index in test_indices
        } != expected:
            raise ValueError("grouped split did not preserve every class on both sides")
    return train_indices, test_indices


def dataset_sha256(rows: list[dict[str, Any]]) -> str:
    """Stable fingerprint of the exact normalized rows supplied to a trainer."""
    digest = hashlib.sha256()
    for row in rows:
        digest.update(
            json.dumps(row, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        digest.update(b"\n")
    return digest.hexdigest()


def artifact_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class AuthenticatedIncumbent:
    """One immutable, report-authenticated incumbent snapshot.

    ``artifact`` is deserialized only from ``payload`` after the v2 report, canonical
    path, and SHA-256 have all been checked. Keeping the exact bytes beside the object
    also closes the selection-to-staging race: promotion writes this snapshot, never a
    second read from the mutable incumbent path.
    """

    path: Path
    payload: bytes
    artifact: dict[str, Any]
    report_result: dict[str, Any]
    sha256: str


def _authenticated_incumbent(
    directory: Path,
    task: str,
    expected_classes: set[str],
) -> tuple[AuthenticatedIncumbent | None, str]:
    """Authenticate and load an incumbent without exposing untrusted pickle bytes.

    A legacy/missing/ambiguous report is historical evidence, not executable authority.
    Every rejection happens before ``joblib.load``. On success, joblib sees only the
    immutable byte buffer whose digest matched the canonical v2 report.
    """

    expected_name = f"engel_slm_{task}.joblib"
    artifact_path = directory / expected_name
    report_path = directory / TRAINING_REPORT_NAME
    if not artifact_path.is_file() and not report_path.is_file():
        return None, "no previous artifact"

    try:
        model_root = directory.resolve(strict=True)
        resolved_report = report_path.resolve(strict=True)
    except OSError as exc:
        return None, f"incumbent report path failed: {type(exc).__name__}: {exc}"
    if (
        resolved_report.parent != model_root
        or resolved_report.name != TRAINING_REPORT_NAME
    ):
        return None, "incumbent report escaped the canonical model directory"

    try:
        report_bytes = resolved_report.read_bytes()
        report = json.loads(report_bytes.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 -- untrusted report fails closed
        return None, f"incumbent report unreadable: {type(exc).__name__}: {exc}"
    if not isinstance(report, dict) or report.get("schema") != roster.TRAINING_REPORT_SCHEMA:
        return None, "incumbent requires a canonical v2 training report"

    matches = [
        result
        for result in report.get("results") or []
        if isinstance(result, dict) and str(result.get("task") or "") == task
    ]
    if len(matches) != 1:
        return None, "incumbent report must contain exactly one canonical task result"
    result = matches[0]
    if result.get("ok") is not True or (
        "selected_ok" in result and result.get("selected_ok") is not True
    ):
        return None, "incumbent report does not mark the selected artifact eligible"

    recorded_name = (
        str(result.get("artifact") or "").replace("\\", "/").rsplit("/", 1)[-1]
    )
    if recorded_name != expected_name:
        return None, "incumbent report artifact path is not canonical"

    expected_hash = str(result.get("artifact_sha256") or "").casefold()
    if len(expected_hash) != 64 or any(
        character not in "0123456789abcdef" for character in expected_hash
    ):
        return None, "incumbent report omitted a valid artifact_sha256"

    try:
        resolved_artifact = artifact_path.resolve(strict=True)
    except OSError as exc:
        return None, f"incumbent artifact path failed: {type(exc).__name__}: {exc}"
    if resolved_artifact.parent != model_root or resolved_artifact.name != expected_name:
        return None, "incumbent artifact escaped the canonical model directory"
    try:
        payload = resolved_artifact.read_bytes()
    except OSError as exc:
        return None, f"incumbent artifact read failed: {type(exc).__name__}: {exc}"
    actual_hash = hashlib.sha256(payload).hexdigest()
    if actual_hash != expected_hash:
        return None, "incumbent artifact sha256 does not match the training report"

    try:
        import joblib

        loaded = joblib.load(io.BytesIO(payload))
    except Exception as exc:  # noqa: BLE001 -- authenticated bytes may still be corrupt
        return None, f"incumbent artifact unreadable: {type(exc).__name__}: {exc}"
    if not isinstance(loaded, dict):
        return None, "incumbent artifact is not a mapping"
    contract_error = _artifact_contract_error(loaded, task)
    if contract_error:
        return None, contract_error
    if set(loaded.get("classes") or []) != expected_classes:
        return None, "incumbent artifact class contract differs from the candidate"
    return (
        AuthenticatedIncumbent(
            path=resolved_artifact,
            payload=payload,
            artifact=loaded,
            report_result=result,
            sha256=actual_hash,
        ),
        "",
    )


def _stage_incumbent(incumbent: AuthenticatedIncumbent, destination: Path) -> None:
    """Atomically stage the same immutable bytes authenticated before selection."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(incumbent.payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def structural_features(text: str) -> list[float]:
    """Cheap shape features a sentence embedding throws away.

    Most style-gate failures are structural rather than semantic — a reply that reads
    as a product assistant, opens with a generic bootstrap, dumps code, or runs long.
    Embeddings normalise exactly that away, which is why the grader stalled near the
    majority-class baseline on embeddings alone.
    """
    reply = text.split("REPLY:", 1)[-1]
    low = reply.casefold()
    words = reply.split()
    lines = [line for line in reply.splitlines() if line.strip()]
    return [
        len(reply) / 4000.0,
        len(words) / 600.0,
        len(lines) / 40.0,
        reply.count("```") / 4.0,
        sum(1 for line in lines if line.lstrip().startswith(("-", "*", "•"))) / 20.0,
        sum(1 for line in lines if line.lstrip()[:2].rstrip(".").isdigit()) / 20.0,
        low.count("i can help") + low.count("how can i assist") + low.count("let me know"),
        low.count("as an ai") + low.count("language model"),
        low.count("engel"),
        low.count("receipt") + low.count("proof"),
        1.0 if low.strip().startswith(("i am", "i'm")) else 0.0,
        1.0 if reply.rstrip().endswith((".", "!", "?", "`")) else 0.0,
        low.count("?") / 5.0,
        low.count("joshua"),
    ]


class Featurizer:
    """Local embeddings when available, character n-grams otherwise."""

    def __init__(self, root: Path, prefer: str = "auto") -> None:
        self.backend = "tfidf_char"
        self.model = None
        self.vectorizer = None
        if prefer in ("auto", "embed"):
            try:
                from sentence_transformers import SentenceTransformer

                local = root / NOMIC_DIR
                if local.is_dir():
                    self.model = SentenceTransformer(
                        str(local),
                        trust_remote_code=False,
                        device="cpu",
                        local_files_only=True,
                    )
                    self.backend = "nomic_embed_text_v1_5_cpu"
            except Exception as exc:  # noqa: BLE001 - fallback is legitimate, not a crash
                self.load_error = f"{type(exc).__name__}: {exc}"

    def __init_structural__(self, use_structural: bool) -> None:
        self.use_structural = use_structural

    def _augment(self, dense, texts: list[str]):
        if not getattr(self, "use_structural", False):
            return dense
        import numpy as np

        extra = np.asarray([structural_features(t) for t in texts], dtype="float32")
        return np.hstack([np.asarray(dense, dtype="float32"), extra])

    def fit_transform(self, texts: list[str]):
        if self.model is not None:
            dense = self.model.encode(texts, batch_size=16, show_progress_bar=False)
            return self._augment(dense, texts)
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=60000
        )
        return self.vectorizer.fit_transform(texts)

    def transform(self, texts: list[str]):
        if self.model is not None:
            dense = self.model.encode(texts, batch_size=16, show_progress_bar=False)
            return self._augment(dense, texts)
        return self.vectorizer.transform(texts)


def leakage_report(texts: list[str], labels: list[str]) -> dict[str, Any]:
    """Catch a dataset whose label is recoverable from the input by construction.

    failure_triage scored F1 = 1.00 on its first run, which is not a win: it had only
    18 distinct input texts for 935 rows and every text mapped to exactly one label,
    so the classifier memorised a lookup table built from the labelling rule itself.
    A model like that adds an embedding dependency to reproduce a regex. Perfect
    separation is a symptom, so it is now measured and gated instead of celebrated.
    """
    by_text: dict[str, set[str]] = {}
    for text, label in zip(texts, labels):
        by_text.setdefault(text, set()).add(label)
    distinct = len(by_text)
    conflicting = sum(1 for values in by_text.values() if len(values) > 1)
    rows = max(1, len(texts))
    distinct_ratio = distinct / rows
    deterministic = conflicting == 0 and distinct < rows
    # Few distinct inputs AND no ambiguity anywhere = the label is a function of the
    # text. Genuine tasks have many distinct inputs and some inherent ambiguity.
    leaking = deterministic and distinct_ratio < 0.10
    return {
        "rows": len(texts),
        "distinct_texts": distinct,
        "distinct_ratio": round(distinct_ratio, 4),
        "texts_with_conflicting_labels": conflicting,
        "label_is_deterministic_function_of_text": deterministic,
        "leaking": leaking,
        "detail": (
            f"{distinct} distinct inputs for {len(texts)} rows with no ambiguity: the "
            "label is recoverable from the text, so a rule is the correct tool"
            if leaking
            else "no leakage signature"
        ),
    }


def _report(y_true: list[str], y_pred: list[str], labels: list[str]) -> dict[str, Any]:
    from sklearn.metrics import classification_report, confusion_matrix, f1_score

    counts: dict[str, int] = {}
    for label in y_true:
        counts[label] = counts.get(label, 0) + 1
    majority = max(counts, key=counts.get) if counts else ""
    baseline = (counts.get(majority, 0) / len(y_true)) if y_true else 0.0
    accuracy = sum(1 for a, b in zip(y_true, y_pred) if a == b) / max(1, len(y_true))
    macro_f1 = float(
        f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
    )
    return {
        "test_rows": len(y_true),
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "majority_class": majority,
        "majority_baseline_accuracy": round(baseline, 4),
        "lift_over_baseline": round(accuracy - baseline, 4),
        "per_class": classification_report(
            y_true, y_pred, labels=labels, zero_division=0, output_dict=True
        ),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        "confusion_labels": labels,
    }


def _incumbent_test_features(
    payload: dict[str, Any],
    candidate_backend: str,
    test_texts: list[str],
    candidate_x_test,
):
    incumbent_backend = str(payload.get("backend") or "")
    if incumbent_backend != candidate_backend:
        raise ValueError(
            f"feature backend changed ({incumbent_backend} -> {candidate_backend})"
        )
    if incumbent_backend == "tfidf_char":
        vectorizer = payload.get("vectorizer")
        if vectorizer is None:
            raise ValueError("previous TF-IDF artifact carries no vectorizer")
        return vectorizer.transform(test_texts)
    return candidate_x_test


def _artifact_contract_error(payload: dict[str, Any], task: str) -> str:
    if payload.get("schema") != roster.ARTIFACT_SCHEMA:
        return "previous artifact schema is not current"
    if str(payload.get("task") or "") != task:
        return f"previous artifact declares task {payload.get('task')!r}"
    if payload.get("task_contract_version") != roster.task_spec(task).contract_version:
        return "previous artifact task contract version mismatch"
    return ""


def _compare_with_previous(
    incumbent: AuthenticatedIncumbent | None,
    unavailable_reason: str,
    task: str,
    backend: str,
    test_texts: list[str],
    candidate_x_test,
    y_test: list[str],
    labels: list[str],
) -> dict[str, Any]:
    """Score the PREVIOUS artifact on this cycle's held-out split.

    (2026-08-07) The SLM equivalent of the LoRA lane's val_loss_before: the majority
    baseline only says "better than nothing" — nothing ever said "better than what Engel
    already HAS", so cycle-over-cycle progress was never measured. Embeddings are a
    deterministic function of text, so when the feature backend matches, the previous
    classifier scores the identical split and the delta is a direct progress reading.
    TF-IDF incumbents MUST transform raw test text through their own stored vectorizer;
    candidate matrices live in a different vocabulary even when both say ``tfidf_char``.
    Never raises: an incomparable, missing, or feature-shape-changed predecessor is
    reported as such rather than scored wrongly."""
    if incumbent is None:
        return {
            "compared": False,
            "authenticated": False,
            "reason": unavailable_reason or "no authenticated previous artifact",
        }
    payload = incumbent.artifact
    prev_clf = payload.get("classifier")
    if prev_clf is None:
        return {
            "compared": False,
            "authenticated": True,
            "reason": "previous artifact carries no classifier",
            "backend": payload.get("backend"),
        }
    try:
        previous_x_test = _incumbent_test_features(
            payload, backend, test_texts, candidate_x_test
        )
        prev_metrics = _report(
            y_test, list(prev_clf.predict(previous_x_test)), labels
        )
    except Exception as exc:
        return {
            "compared": False,
            "authenticated": True,
            "reason": f"previous classifier could not score: {exc}",
            "backend": payload.get("backend"),
        }
    return {
        "compared": True,
        "authenticated": True,
        "artifact_sha256": incumbent.sha256,
        "backend": payload.get("backend"),
        "trained_at_utc": payload.get("trained_at_utc"),
        "dataset_rows": payload.get("dataset_rows"),
        "metrics": prev_metrics,
        "macro_f1": prev_metrics["macro_f1"],  # compatibility for older receipts
        "accuracy": prev_metrics["accuracy"],
        "lift_over_baseline": prev_metrics["lift_over_baseline"],
    }


def _single_label_gate(metrics: dict[str, Any] | None) -> bool:
    return bool(
        metrics
        and float(metrics.get("macro_f1") or 0.0) >= MIN_MACRO_F1
        and float(metrics.get("lift_over_baseline") or 0.0)
        >= MIN_LIFT_OVER_BASELINE
    )


def _metric_rank(metrics: dict[str, Any] | None) -> tuple[float, float, float]:
    values = metrics or {}
    return (
        float(values.get("macro_f1") or 0.0),
        float(values.get("lift_over_baseline") or 0.0),
        float(values.get("accuracy") or 0.0),
    )


def _style_head_gate(metrics: dict[str, Any] | None) -> bool:
    fails = ((metrics or {}).get("per_class") or {}).get("fails") or {}
    return bool(
        _single_label_gate(metrics)
        and float(fails.get("recall") or 0.0) >= 0.50
    )


def _select_single_label_artifact(
    candidate_metrics: dict[str, Any],
    previous: dict[str, Any],
    had_incumbent: bool,
) -> dict[str, Any]:
    """Choose bytes conservatively and keep eligibility distinct from candidacy."""
    candidate_ok = _single_label_gate(candidate_metrics)
    incumbent_metrics = previous.get("metrics") if previous.get("compared") else None
    incumbent_ok = _single_label_gate(incumbent_metrics)

    if not had_incumbent:
        selected_head = "candidate" if candidate_ok else "none"
        reason = (
            "first candidate met the gate"
            if candidate_ok
            else "first candidate was below the gate; no artifact written"
        )
    elif not previous.get("compared"):
        selected_head = "incumbent"
        reason = "candidate was not comparable to the incumbent; incumbent bytes retained"
    elif not candidate_ok:
        selected_head = "incumbent"
        reason = "candidate was below the gate; incumbent bytes retained"
    elif not incumbent_ok:
        selected_head = "candidate"
        reason = "candidate met the gate and incumbent did not"
    elif _metric_rank(incumbent_metrics) >= _metric_rank(candidate_metrics):
        selected_head = "incumbent"
        reason = "incumbent met the gate and matched or beat the candidate"
    else:
        selected_head = "candidate"
        reason = "candidate met the gate and beat the incumbent"

    selected_metrics = (
        candidate_metrics
        if selected_head == "candidate"
        else incumbent_metrics if selected_head == "incumbent" else None
    )
    selected_ok = (
        candidate_ok
        if selected_head == "candidate"
        else incumbent_ok if selected_head == "incumbent" else False
    )
    return {
        "candidate_ok": candidate_ok,
        "selected_ok": bool(selected_ok),
        "selected_head": selected_head,
        "candidate_metrics": candidate_metrics,
        "selected_metrics": selected_metrics,
        "incumbent_ok": incumbent_ok,
        "selection_reason": reason,
    }


def train_single_label(
    task: str,
    rows: list[dict[str, Any]],
    root: Path,
    out_dir: Path,
    min_per_class: int,
    incumbent_dir: Path | None = None,
) -> dict[str, Any]:
    from sklearn.linear_model import LogisticRegression
    import joblib

    artifact = out_dir / f"engel_slm_{task}.joblib"
    incumbent_artifact = (incumbent_dir or out_dir) / artifact.name
    incumbent_present = incumbent_artifact.is_file()
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row.get("label"))] = counts.get(str(row.get("label")), 0) + 1
    keep = {label for label, count in counts.items() if count >= min_per_class}
    dropped = {label: count for label, count in counts.items() if label not in keep}
    usable = [row for row in rows if str(row.get("label")) in keep]
    if len(keep) < 2:
        return {
            "task": task,
            "ok": False,
            "candidate_ok": False,
            "selected_ok": False,
            "selected_head": "none",
            "candidate_metrics": None,
            "selected_metrics": None,
            "incumbent_kept": False,
            "incumbent_present": incumbent_present,
            "status": "not enough classes with sufficient examples to train",
            "class_counts": counts,
            "min_per_class": min_per_class,
            "artifact": str(artifact),
        }

    texts = [_text_for(row, task) for row in usable]
    labels = [str(row.get("label")) for row in usable]
    leakage = leakage_report(texts, labels)
    if leakage["leaking"]:
        # Refuse before spending minutes embedding: this task does not need a model.
        return {
            "task": task,
            "ok": False,
            "candidate_ok": False,
            "selected_ok": False,
            "selected_head": "none",
            "candidate_metrics": None,
            "selected_metrics": None,
            "incumbent_kept": False,
            "incumbent_present": incumbent_present,
            "status": "REJECTED for label leakage — use a deterministic rule, not an SLM",
            "leakage": leakage,
            "class_counts": counts,
            "artifact": str(artifact),
        }
    out_dir.mkdir(parents=True, exist_ok=True)
    groups = [_canonical_prompt_group(row, task) for row in usable]
    try:
        train_indices, test_indices = _grouped_train_test_indices(groups, labels)
    except ValueError as exc:
        return {
            "task": task,
            "ok": False,
            "candidate_ok": False,
            "selected_ok": False,
            "selected_head": "none",
            "candidate_metrics": None,
            "selected_metrics": None,
            "incumbent_kept": False,
            "incumbent_present": incumbent_present,
            "status": f"grouped split refused: {exc}; no artifact selected",
            "artifact": str(artifact),
            "dataset_sha256": dataset_sha256(usable),
            "dataset_rows": len(usable),
            "leakage": leakage,
        }

    train_texts = [texts[index] for index in train_indices]
    test_texts = [texts[index] for index in test_indices]
    y_train = [labels[index] for index in train_indices]
    y_test = [labels[index] for index in test_indices]
    featurizer = Featurizer(root)
    # Reply-quality tasks judge the SHAPE of a reply, so give them shape features too.
    featurizer.__init_structural__(task in REPLY_SHAPE_TASKS)
    started = time.perf_counter()
    # TF-IDF learns its vocabulary from training text only. The held-out prompts are
    # transformed after fitting, never admitted into document-frequency statistics.
    x_train = featurizer.fit_transform(train_texts)
    x_test = featurizer.transform(test_texts)
    # class_weight balanced: without it the 75%-clean prior makes the model ignore the
    # minority class that is the entire reason this model exists.
    clf = LogisticRegression(max_iter=2000, class_weight="balanced")
    clf.fit(x_train, y_train)
    y_pred = list(clf.predict(x_test))
    elapsed = time.perf_counter() - started

    metrics = _report(list(y_test), y_pred, sorted(keep))
    # Authenticate one immutable incumbent snapshot before any pickle-capable load.
    # The same bytes are used for comparison and, if selected, atomic staging.
    authenticated_incumbent, incumbent_auth_reason = _authenticated_incumbent(
        incumbent_artifact.parent,
        task,
        set(keep),
    )
    previous = _compare_with_previous(
        authenticated_incumbent,
        incumbent_auth_reason,
        task,
        featurizer.backend,
        test_texts,
        x_test,
        list(y_test),
        sorted(keep),
    )
    selection = _select_single_label_artifact(
        metrics, previous, authenticated_incumbent is not None
    )
    if selection["selected_head"] == "candidate":
        joblib.dump(
            {
                "schema": roster.ARTIFACT_SCHEMA,
                "task": task,
                "task_contract_version": roster.task_spec(task).contract_version,
                "backend": featurizer.backend,
                "classes": sorted(keep),
                "classifier": clf,
                "vectorizer": featurizer.vectorizer,
                "trained_at_utc": _now(),
                "dataset_sha256": dataset_sha256(usable),
                "dataset_rows": len(usable),
                "gate": {
                    "min_macro_f1": MIN_MACRO_F1,
                    "min_lift_over_baseline": MIN_LIFT_OVER_BASELINE,
                },
            },
            artifact,
        )
    elif selection["selected_head"] == "incumbent" and authenticated_incumbent:
        _stage_incumbent(authenticated_incumbent, artifact)
    incumbent_kept = bool(
        authenticated_incumbent and selection["selected_head"] == "incumbent"
    )
    result = {
        "task": task,
        # `ok` remains the compatibility field consumed by the runtime and equals
        # the eligibility of the bytes that actually remain selected on disk.
        "ok": selection["selected_ok"],
        **selection,
        "incumbent_kept": incumbent_kept,
        "incumbent_present": incumbent_present,
        "incumbent_authenticated": authenticated_incumbent is not None,
        "incumbent_auth_reason": incumbent_auth_reason or None,
        "shipped_head": (
            "new"
            if selection["selected_head"] == "candidate"
            else selection["selected_head"]
        ),
        "status": selection["selection_reason"],
        "candidate_feature_backend": featurizer.backend,
        "selected_feature_backend": (
            featurizer.backend
            if selection["selected_head"] == "candidate"
            else previous.get("backend")
            if selection["selected_head"] == "incumbent"
            else None
        ),
        "feature_backend": (
            featurizer.backend
            if selection["selected_head"] == "candidate"
            else previous.get("backend")
            if selection["selected_head"] == "incumbent"
            else ""
        ),
        "train_rows": len(y_train),
        "test_rows": len(y_test),
        "train_prompt_groups": len({groups[index] for index in train_indices}),
        "test_prompt_groups": len({groups[index] for index in test_indices}),
        "prompt_group_overlap": 0,
        "classes_trained": sorted(keep),
        "classes_dropped_too_few": dropped,
        "train_seconds": round(elapsed, 2),
        "artifact": str(artifact),
        "incumbent_artifact": str(incumbent_artifact),
        "task_contract_version": roster.task_spec(task).contract_version,
        "dataset_sha256": dataset_sha256(usable),
        "dataset_rows": len(usable),
        "gate": {"min_macro_f1": MIN_MACRO_F1, "min_lift": MIN_LIFT_OVER_BASELINE},
        "leakage": leakage,
        "metrics": selection["selected_metrics"] or {},
        "previous": previous,
        "delta_vs_previous": (
            {
                "macro_f1": round(
                    metrics["macro_f1"] - previous["metrics"]["macro_f1"], 4
                ),
                "accuracy": round(
                    metrics["accuracy"] - previous["metrics"]["accuracy"], 4
                ),
            }
            if previous.get("compared")
            else None
        ),
    }
    if selection["selected_head"] != "none" and artifact.is_file():
        selected_bytes = (
            authenticated_incumbent.payload
            if selection["selected_head"] == "incumbent" and authenticated_incumbent
            else None
        )
        result.update(
            {
                "artifact_bytes": (
                    len(selected_bytes) if selected_bytes is not None else artifact.stat().st_size
                ),
                "artifact_sha256": (
                    hashlib.sha256(selected_bytes).hexdigest()
                    if selected_bytes is not None
                    else artifact_sha256(artifact)
                ),
                "artifact_schema": roster.ARTIFACT_SCHEMA,
            }
        )
    return result


def train_style_checks(
    rows: list[dict[str, Any]],
    root: Path,
    out_dir: Path,
    min_positives: int,
    incumbent_dir: Path | None = None,
) -> dict[str, Any]:
    """One binary head per style check, sharing a single embedding pass.

    This is the fix for reply_grader's failure: a single "will this need repair" label
    conflated 46 failure modes over 601 positives (~13 each), which is under-determined.
    Predicting a SPECIFIC check is a narrower question with its own positives, and the
    chat service can act on it — knowing WHICH check will fail lets it repair precisely
    instead of regenerating blind. Checks without enough positives are skipped, not
    trained badly.
    """
    from sklearn.linear_model import LogisticRegression
    import joblib

    artifact = out_dir / "engel_slm_style_checks.joblib"
    incumbent_artifact = (incumbent_dir or out_dir) / artifact.name
    incumbent_present = incumbent_artifact.is_file()
    positives: dict[str, int] = {}
    for row in rows:
        for check_name in row.get("failing_checks") or []:
            positives[check_name] = positives.get(check_name, 0) + 1
    trainable = sorted(c for c, n in positives.items() if n >= min_positives)
    skipped = {c: n for c, n in positives.items() if n < min_positives}
    if not trainable:
        return {
            "task": "style_checks",
            "ok": False,
            "candidate_ok": False,
            "selected_ok": False,
            "selected_head": "none",
            "candidate_metrics": None,
            "selected_metrics": None,
            "incumbent_kept": False,
            "incumbent_present": incumbent_present,
            "status": f"no check reached {min_positives} positives; no artifact selected",
            "positives": positives,
            "artifact": str(artifact),
        }

    texts = [_text_for(row, "style_checks") for row in rows]
    groups = [_canonical_prompt_group(row, "style_checks") for row in rows]
    try:
        train_indices, test_indices = _grouped_train_test_indices(groups)
    except ValueError as exc:
        return {
            "task": "style_checks",
            "ok": False,
            "candidate_ok": False,
            "selected_ok": False,
            "selected_head": "none",
            "candidate_metrics": None,
            "selected_metrics": None,
            "incumbent_kept": False,
            "incumbent_present": incumbent_present,
            "status": f"grouped split refused: {exc}; no artifact selected",
            "artifact": str(artifact),
            "dataset_sha256": dataset_sha256(rows),
            "dataset_rows": len(rows),
        }

    train_texts = [texts[index] for index in train_indices]
    test_texts = [texts[index] for index in test_indices]
    featurizer = Featurizer(root)
    featurizer.__init_structural__(True)
    started = time.perf_counter()
    x_train = featurizer.fit_transform(train_texts)
    x_test = featurizer.transform(test_texts)

    authenticated_incumbent, incumbent_auth_reason = _authenticated_incumbent(
        incumbent_artifact.parent,
        "style_checks",
        {"fails", "passes"},
    )
    previous_load_reason = incumbent_auth_reason
    previous_payload = (
        authenticated_incumbent.artifact if authenticated_incumbent else None
    )
    had_incumbent = authenticated_incumbent is not None
    previous_heads = (
        previous_payload.get("heads")
        if previous_payload and isinstance(previous_payload.get("heads"), dict)
        else {}
    )
    previous_x_test = None
    if previous_payload is not None:
        try:
            previous_x_test = _incumbent_test_features(
                previous_payload, featurizer.backend, test_texts, x_test
            )
        except Exception as exc:  # noqa: BLE001 -- comparison failure is explicit
            previous_load_reason = str(exc)

    candidate_heads: dict[str, Any] = {}
    head_state: dict[str, dict[str, Any]] = {}
    check_names = sorted(set(trainable) | set(previous_heads))
    for check_name in check_names:
        all_labels = [
            "fails" if check_name in (row.get("failing_checks") or []) else "passes"
            for row in rows
        ]
        y_train = [all_labels[index] for index in train_indices]
        y_test = [all_labels[index] for index in test_indices]
        candidate_metrics = None
        candidate_classifier = None
        candidate_reason = "head did not reach the minimum positive count"
        if check_name in trainable:
            if set(y_train) != {"fails", "passes"}:
                candidate_reason = "grouped training split does not contain both classes"
            else:
                try:
                    candidate_classifier = LogisticRegression(
                        max_iter=2000, class_weight="balanced"
                    )
                    candidate_classifier.fit(x_train, y_train)
                    candidate_metrics = _report(
                        y_test,
                        list(candidate_classifier.predict(x_test)),
                        ["fails", "passes"],
                    )
                    candidate_reason = ""
                except Exception as exc:  # noqa: BLE001 -- one head cannot sink all
                    candidate_classifier = None
                    candidate_reason = f"candidate head could not score: {exc}"
        candidate_ok = _style_head_gate(candidate_metrics)
        if candidate_ok and candidate_classifier is not None:
            candidate_heads[check_name] = candidate_classifier

        incumbent_metrics = None
        incumbent_reason = "no incumbent head of this name"
        incumbent_head = previous_heads.get(check_name)
        if incumbent_head is not None:
            if previous_x_test is None:
                incumbent_reason = previous_load_reason or "incumbent features unavailable"
            else:
                try:
                    incumbent_metrics = _report(
                        y_test,
                        list(incumbent_head.predict(previous_x_test)),
                        ["fails", "passes"],
                    )
                    incumbent_reason = ""
                except Exception as exc:  # noqa: BLE001
                    incumbent_reason = f"incumbent head could not score: {exc}"
        incumbent_ok = _style_head_gate(incumbent_metrics)
        head_state[check_name] = {
            "candidate_classifier": candidate_classifier,
            "candidate_metrics": candidate_metrics,
            "candidate_ok": candidate_ok,
            "candidate_reason": candidate_reason,
            "incumbent_head": incumbent_head,
            "incumbent_metrics": incumbent_metrics,
            "incumbent_ok": incumbent_ok,
            "incumbent_reason": incumbent_reason,
        }

    incumbent_comparable = bool(previous_heads) and all(
        head_state[name]["incumbent_metrics"] is not None for name in previous_heads
    )
    incumbent_bundle_ok = bool(
        incumbent_comparable
        and all(head_state[name]["incumbent_ok"] for name in previous_heads)
    )
    candidate_bundle_ok = bool(candidate_heads)
    eligible_incumbent_heads = [
        name for name in previous_heads if head_state[name]["incumbent_ok"]
    ]
    candidate_covers_eligible = all(
        head_state[name]["candidate_ok"]
        and _metric_rank(head_state[name]["candidate_metrics"])
        >= _metric_rank(head_state[name]["incumbent_metrics"])
        for name in eligible_incumbent_heads
    )
    candidate_improves_bundle = (
        not incumbent_bundle_ok
        or bool(set(candidate_heads) - set(previous_heads))
        or any(
            _metric_rank(head_state[name]["candidate_metrics"])
            > _metric_rank(head_state[name]["incumbent_metrics"])
            for name in eligible_incumbent_heads
        )
    )

    if not had_incumbent:
        selected_head = "candidate" if candidate_bundle_ok else "none"
        selection_reason = (
            "first candidate bundle has eligible heads"
            if candidate_bundle_ok
            else "no candidate style head met every gate; no artifact written"
        )
    elif not incumbent_comparable:
        selected_head = "incumbent"
        selection_reason = (
            "candidate bundle was not comparable to every incumbent head; "
            "incumbent bytes retained"
        )
    elif not candidate_bundle_ok:
        selected_head = "incumbent"
        selection_reason = "candidate bundle had no eligible heads; incumbent bytes retained"
    elif candidate_covers_eligible and candidate_improves_bundle:
        selected_head = "candidate"
        selection_reason = "candidate bundle met the gates without regressing an eligible head"
    else:
        selected_head = "incumbent"
        selection_reason = "incumbent bundle retained to prevent a head regression"

    selected_ok = bool(
        candidate_bundle_ok
        if selected_head == "candidate"
        else incumbent_bundle_ok if selected_head == "incumbent" else False
    )
    selected_heads = (
        candidate_heads
        if selected_head == "candidate"
        else previous_heads if selected_head == "incumbent" else {}
    )
    if selected_head == "candidate":
        out_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "schema": roster.ARTIFACT_SCHEMA,
                "task": "style_checks",
                "task_contract_version": roster.task_spec(
                    "style_checks"
                ).contract_version,
                "backend": featurizer.backend,
                "structural_features": True,
                "heads": candidate_heads,
                "classes": ["fails", "passes"],
                "vectorizer": featurizer.vectorizer,
                "trained_at_utc": _now(),
                "dataset_sha256": dataset_sha256(rows),
                "dataset_rows": len(rows),
                "gate": {
                    "min_macro_f1": MIN_MACRO_F1,
                    "min_lift_over_baseline": MIN_LIFT_OVER_BASELINE,
                    "min_fails_recall": 0.50,
                },
            },
            artifact,
        )
    elif selected_head == "incumbent" and authenticated_incumbent:
        _stage_incumbent(authenticated_incumbent, artifact)

    per_check: dict[str, Any] = {}
    for check_name, state in head_state.items():
        selected_metrics = (
            state["candidate_metrics"]
            if selected_head == "candidate"
            else state["incumbent_metrics"]
            if selected_head == "incumbent"
            else None
        )
        selected_head_ok = (
            state["candidate_ok"]
            if selected_head == "candidate"
            else state["incumbent_ok"]
            if selected_head == "incumbent"
            else False
        )
        servable = bool(selected_ok and selected_head_ok)
        selected_fails = ((selected_metrics or {}).get("per_class") or {}).get(
            "fails"
        ) or {}
        per_check[check_name] = {
            "positives": positives.get(check_name, 0),
            "candidate_ok": state["candidate_ok"],
            "selected_ok": servable,
            "selected_head": selected_head,
            "candidate_metrics": state["candidate_metrics"],
            "selected_metrics": selected_metrics,
            "incumbent_ok": state["incumbent_ok"],
            "candidate_missing_reason": state["candidate_reason"] or None,
            "previous_missing_reason": state["incumbent_reason"] or None,
            "delta_vs_previous_macro_f1": (
                round(
                    state["candidate_metrics"]["macro_f1"]
                    - state["incumbent_metrics"]["macro_f1"],
                    4,
                )
                if state["candidate_metrics"] and state["incumbent_metrics"]
                else None
            ),
            # Compatibility fields describe the selected, actually servable head.
            "macro_f1": float((selected_metrics or {}).get("macro_f1") or 0.0),
            "fails_precision": round(
                float(selected_fails.get("precision") or 0.0), 3
            ),
            "fails_recall": round(float(selected_fails.get("recall") or 0.0), 3),
            "baseline_accuracy": (selected_metrics or {}).get(
                "majority_baseline_accuracy"
            ),
            "lift_over_baseline": (selected_metrics or {}).get("lift_over_baseline"),
            "shipped": servable,
            "shipped_head": (
                "new" if selected_head == "candidate" else selected_head
            ),
        }

    candidate_metrics = {
        "majority_baseline_accuracy": None,
        "macro_f1": max(
            (
                float((state["candidate_metrics"] or {}).get("macro_f1") or 0.0)
                for state in head_state.values()
            ),
            default=0.0,
        ),
        "heads_ok": sorted(candidate_heads),
        "note": "per-head candidate metrics are in per_check",
    }
    selected_metrics = {
        "majority_baseline_accuracy": None,
        "macro_f1": max(
            (entry["macro_f1"] for entry in per_check.values() if entry["shipped"]),
            default=0.0,
        ),
        "heads_ok": sorted(
            name for name, entry in per_check.items() if entry["shipped"]
        ),
        "note": "per-head selected metrics are in per_check",
    }
    dropped_incumbent_heads = (
        sorted(name for name in previous_heads if name not in candidate_heads)
        if selected_head == "candidate"
        else []
    )
    result = {
        "task": "style_checks",
        "ok": selected_ok,
        "candidate_ok": candidate_bundle_ok,
        "selected_ok": selected_ok,
        "selected_head": selected_head,
        "candidate_metrics": candidate_metrics,
        "selected_metrics": selected_metrics,
        "incumbent_ok": incumbent_bundle_ok,
        "incumbent_kept": had_incumbent and selected_head == "incumbent",
        "incumbent_present": incumbent_present,
        "incumbent_authenticated": authenticated_incumbent is not None,
        "incumbent_auth_reason": incumbent_auth_reason or None,
        "shipped_head": "new" if selected_head == "candidate" else selected_head,
        "dropped_incumbent_heads": dropped_incumbent_heads,
        "status": selection_reason,
        "candidate_feature_backend": featurizer.backend,
        "selected_feature_backend": (
            featurizer.backend
            if selected_head == "candidate"
            else previous_payload.get("backend")
            if selected_head == "incumbent" and previous_payload
            else None
        ),
        "feature_backend": (
            featurizer.backend
            if selected_head == "candidate"
            else str(previous_payload.get("backend") or "")
            if selected_head == "incumbent" and previous_payload
            else ""
        ),
        "train_rows": len(train_indices),
        "test_rows": len(test_indices),
        "train_prompt_groups": len({groups[index] for index in train_indices}),
        "test_prompt_groups": len({groups[index] for index in test_indices}),
        "prompt_group_overlap": 0,
        "heads_shipped": sorted(
            name for name, entry in per_check.items() if entry["shipped"]
        ),
        "selected_artifact_heads": sorted(selected_heads),
        "checks_skipped_too_few_positives": skipped,
        "per_check": per_check,
        "train_seconds": round(time.perf_counter() - started, 2),
        "artifact": str(artifact),
        "incumbent_artifact": str(incumbent_artifact),
        "task_contract_version": roster.task_spec("style_checks").contract_version,
        "dataset_sha256": dataset_sha256(rows),
        "dataset_rows": len(rows),
        "leakage": leakage_report(
            texts, ["|".join(row.get("failing_checks") or []) for row in rows]
        ),
        "metrics": selected_metrics,
        "gate": {
            "min_macro_f1": MIN_MACRO_F1,
            "min_lift_over_baseline": MIN_LIFT_OVER_BASELINE,
            "min_fails_recall": 0.50,
        },
        "previous": {
            "compared": incumbent_comparable,
            "reason": previous_load_reason or None,
            "heads": sorted(previous_heads),
        },
    }
    if selected_head != "none" and artifact.is_file():
        selected_bytes = (
            authenticated_incumbent.payload
            if selected_head == "incumbent" and authenticated_incumbent
            else None
        )
        result.update(
            {
                "artifact_bytes": (
                    len(selected_bytes) if selected_bytes is not None else artifact.stat().st_size
                ),
                "artifact_sha256": (
                    hashlib.sha256(selected_bytes).hexdigest()
                    if selected_bytes is not None
                    else artifact_sha256(artifact)
                ),
                "artifact_schema": roster.ARTIFACT_SCHEMA,
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Train Engel SLMs")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument(
        "--tasks",
        default=roster.default_training_csv(),
        help=(
            "comma separated canonical SLM tasks; use 'default' for the normal roster "
            "or 'all' to include data-collection candidates"
        ),
    )
    parser.add_argument("--min-per-class", type=int, default=40)
    parser.add_argument(
        "--data-dir",
        help=(
            "canonical input dataset directory; defaults to <root>/run/slm/datasets "
            "and is never written by the trainer"
        ),
    )
    parser.add_argument(
        "--out-dir",
        help=(
            "canonical output/staging directory; when supplied, every artifact and "
            "report write stays beneath this directory"
        ),
    )
    parser.add_argument(
        "--incumbent-dir",
        help="read-only incumbent artifact directory (defaults to --out-dir)",
    )
    parser.add_argument(
        "--run-id",
        help="stable lifecycle run identifier; required with --out-dir",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    data_dir = (
        Path(args.data_dir).resolve()
        if args.data_dir
        else (root / "run" / "slm" / "datasets").resolve()
    )
    staged_mode = bool(args.out_dir)
    if staged_mode and not args.run_id:
        parser.error("--out-dir requires --run-id")
    if args.run_id and not staged_mode:
        parser.error("--run-id requires --out-dir so a lifecycle run cannot write live")
    if args.incumbent_dir and not staged_mode:
        parser.error("--incumbent-dir requires --out-dir")
    out_dir = (
        Path(args.out_dir).resolve()
        if staged_mode
        else (root / "models-active" / "slm").resolve()
    )
    incumbent_dir = (
        Path(args.incumbent_dir).resolve() if args.incumbent_dir else out_dir
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        run_id = _validated_run_id(args.run_id or f"standalone-{stamp}")
    except ValueError as exc:
        parser.error(str(exc))
    try:
        requested_tasks = roster.normalize_tasks(args.tasks)
    except ValueError as exc:
        parser.error(str(exc))
    results = []
    for task in requested_tasks:
        path = data_dir / f"{task}.jsonl"
        if not path.is_file():
            results.append(
                {
                    "task": task,
                    "ok": False,
                    "candidate_ok": False,
                    "selected_ok": False,
                    "selected_head": "none",
                    "candidate_metrics": None,
                    "selected_metrics": None,
                    "status": f"missing dataset {path}",
                }
            )
            continue
        rows = _load_rows(path)
        if task == "style_checks":
            results.append(
                train_style_checks(
                    rows,
                    root,
                    out_dir,
                    args.min_per_class,
                    incumbent_dir=incumbent_dir,
                )
            )
        else:
            results.append(
                train_single_label(
                    task,
                    rows,
                    root,
                    out_dir,
                    args.min_per_class,
                    incumbent_dir=incumbent_dir,
                )
            )

    report = {
        "schema": roster.TRAINING_REPORT_SCHEMA,
        "roster_schema": roster.ROSTER_SCHEMA,
        "generated_at_utc": _now(),
        "run_id": run_id,
        "root": str(root),
        "data_dir": str(data_dir),
        "output_dir": str(out_dir),
        "incumbent_dir": str(incumbent_dir),
        "staged": staged_mode,
        "requested_tasks": list(requested_tasks),
        "results": results,
        "candidate_ok": [r["task"] for r in results if r.get("candidate_ok")],
        "selected_ok": [r["task"] for r in results if r.get("selected_ok")],
        "trained_ok": [r["task"] for r in results if r.get("ok")],
        "candidate_below_gate": [
            r["task"] for r in results if not r.get("candidate_ok")
        ],
        "below_gate": [r["task"] for r in results if not r.get("ok")],
        "roster": roster.roster_snapshot(results),
    }
    receipt_dir = out_dir / "reports" if staged_mode else root / "reports" / "slm"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    (receipt_dir / f"ENGEL_SLM_TRAINING_{stamp}.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    (out_dir / "LATEST_TRAINING.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["trained_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
