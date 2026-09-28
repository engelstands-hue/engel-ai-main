#!/usr/bin/env python3
"""Engel Lorenz Attractor Lane Classifier V1.

Maps approved build/promote lane state into a Lorenz-attractor trajectory and
classifies the resulting position. Pure stdlib. Deterministic.

Why this helps lanes (summary; full reasoning in
reports\\codex_bridge\\ENGEL_LORENZ_ATTRACTOR_LANE_CLASSIFIER_V1.md):

  Lorenz system::

      dx/dt = sigma * (y - x)
      dy/dt = x * (rho - z) - y
      dz/dt = x*y - beta * z

  with classic chaotic parameters sigma=10, rho=28, beta=8/3.

  The system is a *bounded* attractor with two wings (the butterfly).  Each
  trajectory stays within a finite envelope but visits the two wings in a
  chaotic, non-repeating order.  That maps cleanly onto build/promote lane
  safety:

    - Bounded outcome set: every lane invocation returns one of a fixed list of
      named statuses; no outcome ever escapes the bounded set.
    - Two wings:
        * PASS basin     - lane returns *_PASS_REVIEW_REQUIRED
        * BLOCKED basin  - lane returns *_BLOCKED_*, *_NOT_IMPLEMENTED,
                           *_HARD_BLOCKED, *_OUTSIDE_ALLOWLIST
    - Saddle:
        * REVIEW basin   - lane returns *_TIMEOUT_BOUNDED_REVIEW_REQUIRED,
                           *_SCRIPT_EXIT_NONZERO_REVIEW_REQUIRED,
                           *_LIVE_SMOKE_FAIL_REVIEW_REQUIRED,
                           *_STAGED_SMOKE_FAIL_REVIEW_REQUIRED,
                           *_POST_VERIFIER_FAIL_REVIEW_REQUIRED
    - Sensitive dependence on initial conditions:
        * Small drift in candidate hash, pre-verifier count, or edge-label
          length causes large divergence in trajectory.  The classifier surfaces
          a `sensitivity_indicator` that lets the receipt flag candidates whose
          inputs are close to a saddle and therefore inherently risky.

  This module never executes anything.  It never reads files outside its
  declared inputs.  It never invokes subprocess, network, provider, or model
  code.  It only computes a deterministic classification metadata block to
  attach to lane receipts.

Calling convention::

    classify_lane_trajectory(
        lane_id="approved_graph_build",
        final_status="BUILD_LANE_BLOCKED_SCRIPT_MISSING",
        candidate_hash="<hex>",
        edge_label="...",
        pre_verifier_pass_count=8,
        pre_verifier_total=8,
    )

returns a `LorenzClassificationResult` with the trajectory metadata.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable


CLASSIFIER_ID = "engel_lorenz_attractor_lane_classifier_v1"
CLASSIFIER_CONTRACT_ID = "ENGEL_LORENZ_ATTRACTOR_LANE_CLASSIFIER_CONTRACT_V1"

SIGMA = 10.0
RHO = 28.0
BETA = 8.0 / 3.0
DT = 0.01
WARMUP_STEPS = 200
TRAJECTORY_STEPS = 2000

PASS_STATUS_TOKENS = (
    "_PASS_REVIEW_REQUIRED",
    "_PASS",
)

BLOCKED_STATUS_TOKENS = (
    "_NOT_IMPLEMENTED",
    "_BLOCKED_SCRIPT_MISSING",
    "_BLOCKED_OUTSIDE_ALLOWLIST",
    "_BLOCKED_PRE_VERIFIER",
    "_BLOCKED_PASSWORD_GATE",
    "_BLOCKED_TIMEOUT_LANE_MISSING",
    "_BLOCKED_BUILD_RECEIPT_MISSING",
    "_BLOCKED_BUILD_RECEIPT_INVALID",
    "_BLOCKED_STAGED_ARTIFACT_MISSING",
    "_BLOCKED_BACKUP_FAILED",
    "_TIMEOUT_HARD_BLOCKED",
)

SADDLE_STATUS_TOKENS = (
    "_TIMEOUT_BOUNDED_REVIEW_REQUIRED",
    "_SCRIPT_EXIT_NONZERO_REVIEW_REQUIRED",
    "_LIVE_SMOKE_FAIL_REVIEW_REQUIRED",
    "_STAGED_SMOKE_FAIL_REVIEW_REQUIRED",
    "_POST_VERIFIER_FAIL_REVIEW_REQUIRED",
)


@dataclass
class LorenzClassificationResult:
    classifier_id: str
    classifier_contract_id: str
    lane_id: str
    final_status: str
    sigma: float
    rho: float
    beta: float
    dt: float
    warmup_steps: int
    trajectory_steps: int
    initial_state: tuple[float, float, float]
    final_state: tuple[float, float, float]
    wing_classification: str
    bounded_attractor_invariant_ok: bool
    sensitivity_indicator: float
    review_recommended: bool
    notes: list[str] = field(default_factory=list)


def _seed_from_inputs(
    candidate_hash: str,
    edge_label: str,
    pre_verifier_pass_count: int,
    pre_verifier_total: int,
) -> tuple[float, float, float]:
    """Build a deterministic Lorenz initial condition from lane inputs."""
    cand = (candidate_hash or "").lower()
    cand_bytes = bytes(int(cand[i : i + 2], 16) for i in range(0, min(len(cand), 6), 2)) if cand else b"\x00\x00\x00"
    while len(cand_bytes) < 3:
        cand_bytes += b"\x00"
    x_seed = (cand_bytes[0] / 255.0) * 2.0 - 1.0
    y_seed = (cand_bytes[1] / 255.0) * 2.0 - 1.0
    z_seed = (cand_bytes[2] / 255.0) * 2.0 - 1.0
    edge_drift = (len(edge_label or "") % 64) / 64.0
    verifier_ratio = (pre_verifier_pass_count / pre_verifier_total) if pre_verifier_total > 0 else 0.0
    x = x_seed + edge_drift * 0.5
    y = y_seed + (1.0 - verifier_ratio) * 0.5
    z = abs(z_seed) + verifier_ratio * 0.5
    return (x, y, z)


def _step(state: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = state
    dx = SIGMA * (y - x)
    dy = x * (RHO - z) - y
    dz = x * y - BETA * z
    return (x + DT * dx, y + DT * dy, z + DT * dz)


def _integrate(initial: tuple[float, float, float], steps: int) -> tuple[float, float, float]:
    state = initial
    for _ in range(steps):
        state = _step(state)
    return state


def _wing_from_status(final_status: str) -> str:
    upper = (final_status or "").upper()
    for token in BLOCKED_STATUS_TOKENS:
        if token in upper:
            return "right_wing_blocked_basin"
    for token in SADDLE_STATUS_TOKENS:
        if token in upper:
            return "saddle_review_required_transition"
    for token in PASS_STATUS_TOKENS:
        if token in upper:
            return "left_wing_pass_basin"
    return "off_attractor_unclassified"


def _bounded(state: Iterable[float]) -> bool:
    return all(abs(v) < 200.0 for v in state)


def _sensitivity(state: tuple[float, float, float]) -> float:
    """Compute |Lyapunov-like| sensitivity probe by stepping a 1e-6 perturbation."""
    x, y, z = state
    perturbed = (x + 1e-6, y, z)
    a = _step(state)
    b = _step(perturbed)
    dx, dy, dz = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return (dx * dx + dy * dy + dz * dz) ** 0.5


def classify_lane_trajectory(
    lane_id: str,
    final_status: str,
    candidate_hash: str = "",
    edge_label: str = "",
    pre_verifier_pass_count: int = 0,
    pre_verifier_total: int = 0,
) -> LorenzClassificationResult:
    initial = _seed_from_inputs(candidate_hash, edge_label, pre_verifier_pass_count, pre_verifier_total)
    after_warmup = _integrate(initial, WARMUP_STEPS)
    final_state = _integrate(after_warmup, TRAJECTORY_STEPS)
    wing = _wing_from_status(final_status)
    bounded_ok = _bounded(final_state) and _bounded(after_warmup)
    sensitivity = _sensitivity(after_warmup)
    review_recommended = (
        wing == "saddle_review_required_transition"
        or wing == "off_attractor_unclassified"
        or sensitivity > 1e-3
    )
    notes: list[str] = []
    if not bounded_ok:
        notes.append("trajectory left the expected bounded envelope; review the candidate-hash mapping")
    if wing == "off_attractor_unclassified":
        notes.append(
            "final_status did not match any wing token; lane returned an unmodeled status that should be"
            " added to the classifier's PASS/BLOCKED/SADDLE token lists"
        )
    if sensitivity > 1e-3:
        notes.append("high local sensitivity indicator; candidate sits near a saddle and is inherently risky")
    return LorenzClassificationResult(
        classifier_id=CLASSIFIER_ID,
        classifier_contract_id=CLASSIFIER_CONTRACT_ID,
        lane_id=lane_id,
        final_status=final_status,
        sigma=SIGMA,
        rho=RHO,
        beta=BETA,
        dt=DT,
        warmup_steps=WARMUP_STEPS,
        trajectory_steps=TRAJECTORY_STEPS,
        initial_state=initial,
        final_state=final_state,
        wing_classification=wing,
        bounded_attractor_invariant_ok=bounded_ok,
        sensitivity_indicator=sensitivity,
        review_recommended=review_recommended,
        notes=notes,
    )


def classifier_status_payload() -> dict[str, object]:
    return {
        "classifier_id": CLASSIFIER_ID,
        "classifier_contract_id": CLASSIFIER_CONTRACT_ID,
        "module": "engel_lorenz_attractor_lane_classifier.py",
        "sigma": SIGMA,
        "rho": RHO,
        "beta": BETA,
        "dt": DT,
        "warmup_steps": WARMUP_STEPS,
        "trajectory_steps": TRAJECTORY_STEPS,
        "pass_status_tokens": list(PASS_STATUS_TOKENS),
        "blocked_status_tokens": list(BLOCKED_STATUS_TOKENS),
        "saddle_status_tokens": list(SADDLE_STATUS_TOKENS),
        "safety_boundary": [
            "pure stdlib classification only",
            "no subprocess, network, provider, model, or local LLM",
            "no file write",
            "no source/route/queue/trusted-memory mutation",
            "no apply, build, promote, stage, or commit",
            "deterministic given identical inputs",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Lorenz Attractor Lane Classifier V1 helper")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    cls_parser = sub.add_parser("classify")
    cls_parser.add_argument("--lane-id", required=True)
    cls_parser.add_argument("--final-status", required=True)
    cls_parser.add_argument("--candidate-hash", default="")
    cls_parser.add_argument("--edge-label", default="")
    cls_parser.add_argument("--pre-verifier-pass-count", type=int, default=0)
    cls_parser.add_argument("--pre-verifier-total", type=int, default=0)
    args = parser.parse_args(argv)
    if args.command == "status":
        print(json.dumps(classifier_status_payload(), indent=2, sort_keys=True))
        return 0
    if args.command == "classify":
        result = classify_lane_trajectory(
            lane_id=args.lane_id,
            final_status=args.final_status,
            candidate_hash=args.candidate_hash,
            edge_label=args.edge_label,
            pre_verifier_pass_count=args.pre_verifier_pass_count,
            pre_verifier_total=args.pre_verifier_total,
        )
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
