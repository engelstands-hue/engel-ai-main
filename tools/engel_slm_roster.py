#!/usr/bin/env python3
"""Canonical contract for Engel AI Main's small-language-model roster.

The roster used to be copied by hand into the dataset builder, trainer, serving
runtime, real-training cycle, and Flutter UI.  Those copies drifted: a passing
``reply_grader`` had no serving method, ``failure_triage`` was still described as
shippable after its leakage rejection, and the Governor design's route head never
appeared in the runnable list.  This module is the Python source of truth.

Every learned head is advisory.  In particular, no SLM may grant an action,
promote memory, admit its own training sample, deploy a model, or override Josh / the
Guardian / deterministic gates.  ``route_governor`` and ``failure_triage`` begin in
data-collection state and cannot serve until the ordinary metric and leakage gates
record ``ok=true`` in the latest training report.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable

ROSTER_SCHEMA = "engel_slm_roster_v1"
TRAINING_REPORT_SCHEMA = "engel_slm_training_report_v2"
ARTIFACT_SCHEMA = "engel_slm_artifact_v2"


@dataclass(frozen=True)
class SlmTaskSpec:
    task: str
    display_name: str
    purpose: str
    input_contract: str
    labels: tuple[str, ...]
    stage: str
    default_train: bool
    runtime_method: str
    consumer: str
    dataset_source: str
    authority: str = "advisory_only"
    contract_version: int = 1


ROSTER: tuple[SlmTaskSpec, ...] = (
    SlmTaskSpec(
        task="intent_router",
        display_name="Intent Router",
        purpose="Recognizes whether a request is chat, build work, training, or Meeting Room work.",
        input_contract="prompt text",
        labels=("chat", "build", "training_job", "meeting_room"),
        stage="active",
        default_train=True,
        runtime_method="intent",
        consumer="Governor route features and SLM advisory receipts",
        dataset_source="local chat receipts",
    ),
    SlmTaskSpec(
        task="route_governor",
        display_name="Route Governor",
        purpose="Suggests the best local model lane from a bounded Governor feature record.",
        input_contract="canonical Governor route features",
        labels=(
            "defer_to_heuristics",
            "local",
            "main_server_code_lane_model",
            "ct_deep_local_specialist",
            "ct_sparse_moe_specialist",
            "math_lane",
            "math_reasoning_specialist",
        ),
        stage="collecting_data",
        default_train=False,
        runtime_method="route_advice",
        consumer="Governor shadow telemetry; deterministic T0 remains authoritative",
        dataset_source="governor route decisions embedded in local chat receipts",
    ),
    SlmTaskSpec(
        task="style_checks",
        display_name="Style Checks",
        purpose="Predicts which proven reply-style checks are likely to fail.",
        input_contract="prompt and original model reply",
        labels=("per-check fails", "per-check passes"),
        stage="active",
        default_train=True,
        runtime_method="style_flags",
        consumer="SLM advisory receipts",
        dataset_source="local chat style-score receipts",
    ),
    SlmTaskSpec(
        task="reply_grader",
        display_name="Reply Grader",
        purpose="Estimates whether the original reply is clean or needs repair.",
        input_contract="prompt and original model reply",
        labels=("clean", "needed_repair"),
        stage="active",
        default_train=True,
        runtime_method="reply_quality",
        consumer="SLM advisory receipts",
        dataset_source="local chat repair receipts",
    ),
    SlmTaskSpec(
        task="train_admit",
        display_name="Training Admission",
        purpose="Provides a shadow opinion on whether a reviewed reply is suitable training material.",
        input_contract="base prompt and reviewed reply",
        labels=("admit", "reject"),
        stage="shadow_candidate",
        default_train=True,
        runtime_method="admit_score",
        consumer="prompt-training pack shadow telemetry; deterministic admission remains authoritative",
        dataset_source="prompt-training packs containing both admitted and rejected completed turns",
    ),
    SlmTaskSpec(
        task="failure_triage",
        display_name="Failure Triage",
        purpose="Estimates whether one bounded Code Forge repair round is likely to fix an observed failure.",
        input_contract="goal, deterministic error class, and diagnostic tail",
        labels=("repair_succeeded", "repair_failed"),
        stage="collecting_data",
        default_train=False,
        runtime_method="failure_outlook",
        consumer="Code Forge round telemetry; retry bounds remain deterministic",
        dataset_source="Code Forge outcomes with observed fixed_by_next labels",
    ),
)

_BY_TASK = {spec.task: spec for spec in ROSTER}
KNOWN_TASKS = tuple(spec.task for spec in ROSTER)
DEFAULT_TRAIN_TASKS = tuple(spec.task for spec in ROSTER if spec.default_train)
REPLY_SHAPE_TASKS = tuple(
    task for task in KNOWN_TASKS if task in {"reply_grader", "style_checks", "train_admit"}
)

# Only features documented by the Governor's route contract may enter the learned
# route head.  Outcome, rule_id, approval values, and free-form request metadata are
# deliberately absent so the label cannot leak into the input and the SLM cannot
# acquire an authorization feature.
ROUTE_FEATURE_FIELDS = (
    "discipline",
    "interactive",
    "intent",
    "intent_confidence",
    "prompt_len",
    "math_token_density",
    "explicit_lane_request",
    "is_code_artifact",
    "context_bytes",
    "caller",
    "lane_health",
    "routing_hint",
)


def task_spec(task: str) -> SlmTaskSpec:
    try:
        return _BY_TASK[str(task)]
    except KeyError as exc:
        raise ValueError(f"unknown SLM task {task!r}; expected one of {', '.join(KNOWN_TASKS)}") from exc


def normalize_tasks(value: str | Iterable[str]) -> tuple[str, ...]:
    """Validate and de-duplicate an operator task selection, preserving order."""
    if isinstance(value, str):
        raw = [item.strip() for item in value.split(",")]
    else:
        raw = [str(item).strip() for item in value]
    requested = [item for item in raw if item]
    if requested == ["default"]:
        return DEFAULT_TRAIN_TASKS
    if requested == ["all"]:
        return KNOWN_TASKS
    if not requested:
        raise ValueError("at least one SLM task is required")
    unknown = sorted(set(requested) - set(KNOWN_TASKS))
    if unknown:
        raise ValueError(
            f"unknown SLM task(s): {', '.join(unknown)}; expected {', '.join(KNOWN_TASKS)}"
        )
    return tuple(dict.fromkeys(requested))


def default_training_csv() -> str:
    return ",".join(DEFAULT_TRAIN_TASKS)


def catalog() -> list[dict[str, Any]]:
    return [
        {
            **asdict(spec),
            "labels": list(spec.labels),
            "roster_schema": ROSTER_SCHEMA,
        }
        for spec in ROSTER
    ]


def roster_snapshot(results: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return every roster entry, even when the latest run did not select it."""
    by_task = {
        str(result.get("task") or ""): result
        for result in results
        if isinstance(result, dict) and str(result.get("task") or "") in _BY_TASK
    }
    snapshot: list[dict[str, Any]] = []
    for spec in ROSTER:
        result = by_task.get(spec.task)
        row = {
            **asdict(spec),
            "labels": list(spec.labels),
            "recorded_in_latest_run": result is not None,
            "eligible": bool(result and result.get("ok") is True),
            "training_status": (
                str(result.get("status") or "")
                if result is not None
                else "not selected in the latest training run"
            ),
        }
        snapshot.append(row)
    return snapshot


def canonical_route_features(features: Any) -> dict[str, Any]:
    if not isinstance(features, dict):
        return {}
    canonical: dict[str, Any] = {}
    for field in ROUTE_FEATURE_FIELDS:
        if field not in features:
            continue
        value = features.get(field)
        if isinstance(value, dict):
            # lane_health is the sole structured field.  Keep scalar status values
            # and stable key order; nested free-form content is not part of the model.
            canonical[field] = {
                str(key): nested
                for key, nested in sorted(value.items(), key=lambda item: str(item[0]))
                if isinstance(nested, (bool, int, float, str)) or nested is None
            }
        elif isinstance(value, (bool, int, float, str)) or value is None:
            canonical[field] = value
    return canonical


def route_feature_text(features: Any) -> str:
    return json.dumps(
        canonical_route_features(features),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
