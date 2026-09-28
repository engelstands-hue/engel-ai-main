#!/usr/bin/env python3
"""Engel De Bruijn Lane Traversal Classifier V1.

Sibling to engel_lorenz_attractor_lane_classifier.py. Where the Lorenz classifier
maps a single lane outcome to a wing of a bounded attractor, this classifier maps
a *sequence* of recent lane outcomes to a path through a De Bruijn graph and
checks the path against the validated edge alphabet declared by the
ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_V1 contract.

Why this helps lanes (full reasoning in
reports\\codex_bridge\\ENGEL_LANE_SAFETY_FRAME_V1.md):

  Visual references this module mirrors:

    - Quantum View of the De Bruijn Graph: bits become qubits, candidate states
      can be in superposition, interference cancels unsafe paths, measurement
      collapses to one classical outcome.
    - How the De Bruijn Graph Builds the Sequence: each lane invocation is one
      edge in the lane-status De Bruijn graph; each edge appends one new outcome
      and the trailing window slides left.
    - Full De Bruijn Sequence Graph: every valid window-to-outcome transition
      appears exactly once in the bounded cycle.

  Concretely, the lane status alphabet is finite (PASS basin, BLOCKED basin,
  SADDLE basin -- see the Lorenz classifier for the wing tokens). The classifier
  picks a window size K (default 3), reads the last K + 1 lane outcomes from a
  caller-supplied history, encodes them as a (window -> next) De Bruijn-style
  transition, and checks:

    - the transition appears in the validated edge alphabet
    - no edge in the recent history is "off attractor" (unmodeled status)
    - the most recent edge label preserves overlap with its predecessor's last
      (K - 1) wing letters
    - the window has not produced a forbidden absorbing pattern such as
      ``BLOCKED -> BLOCKED -> BLOCKED -> PASS`` without a saddle gap (a sign
      that the lane is being retried without human review)

  As with the Lorenz classifier, this module is metadata only. It never
  overrides a lane's final_status; it only adds a `transition_classification`,
  `superposition_amplitudes` (an analytic stand-in for the quantum-walk shape),
  and `review_recommended` advisory to the lane receipt.

Pure stdlib. Deterministic. No subprocess, network, provider, model, or local
LLM. No source / route / queue / trusted-memory mutation. No apply, build,
promote, stage, or commit.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Iterable


CLASSIFIER_ID = "engel_debruijn_lane_traversal_classifier_v1"
CLASSIFIER_CONTRACT_ID = "ENGEL_DEBRUIJN_LANE_TRAVERSAL_CLASSIFIER_CONTRACT_V1"
GRAPH_SEQUENCE_MODEL_CONTRACT_ID = "ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_V1"
LANE_WING_TOKENS = ("P", "B", "S")  # PASS, BLOCKED, SADDLE
DEFAULT_WINDOW_SIZE = 3


PASS_TOKENS = (
    "_PASS_REVIEW_REQUIRED",
    "_PASS",
)
BLOCKED_TOKENS = (
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
SADDLE_TOKENS = (
    "_TIMEOUT_BOUNDED_REVIEW_REQUIRED",
    "_SCRIPT_EXIT_NONZERO_REVIEW_REQUIRED",
    "_LIVE_SMOKE_FAIL_REVIEW_REQUIRED",
    "_STAGED_SMOKE_FAIL_REVIEW_REQUIRED",
    "_POST_VERIFIER_FAIL_REVIEW_REQUIRED",
)


@dataclass
class LaneTransitionResult:
    classifier_id: str
    classifier_contract_id: str
    graph_sequence_model_contract_id: str
    window_size: int
    window: list[str]
    next_letter: str
    next_status: str
    transition_edge_label: str
    transition_classification: str
    overlap_preserved: bool
    edge_present_in_alphabet: bool
    forbidden_absorbing_pattern_detected: bool
    forbidden_pattern_reason: str
    superposition_amplitudes: dict[str, float]
    interference_dominant_letter: str
    review_recommended: bool
    notes: list[str] = field(default_factory=list)


def _status_to_letter(status: str) -> str:
    upper = (status or "").upper()
    for token in PASS_TOKENS:
        if token in upper:
            return "P"
    for token in BLOCKED_TOKENS:
        if token in upper:
            return "B"
    for token in SADDLE_TOKENS:
        if token in upper:
            return "S"
    return "?"


def _validate_window(window: Iterable[str], window_size: int) -> list[str]:
    letters = [_status_to_letter(s) for s in window]
    if len(letters) < window_size:
        # pad on the left with "?" so the analysis still completes
        letters = ["?"] * (window_size - len(letters)) + letters
    elif len(letters) > window_size:
        letters = letters[-window_size:]
    return letters


def _is_off_attractor(letter: str) -> bool:
    return letter == "?"


def _alphabet_edges(window_size: int) -> set[str]:
    """The validated edge alphabet: every K-letter window over {P, B, S} appended
    with every next-letter over {P, B, S}. That is exactly the De Bruijn order-K
    binary-style closure over the lane wing alphabet, restricted to the saddle
    rule that BLOCKED -> BLOCKED -> BLOCKED -> PASS without an intervening
    SADDLE is forbidden (logged separately as the absorbing-pattern check).
    """
    edges: set[str] = set()
    letters = LANE_WING_TOKENS
    if window_size <= 0:
        return edges

    def build(prefix: list[str], depth: int) -> None:
        if depth == 0:
            for nxt in letters:
                edges.add("".join(prefix) + "->" + nxt)
            return
        for letter in letters:
            prefix.append(letter)
            build(prefix, depth - 1)
            prefix.pop()

    build([], window_size)
    return edges


def _detect_forbidden_absorbing(window_letters: list[str], next_letter: str) -> tuple[bool, str]:
    """If the trailing window is all BLOCKED and the next status is PASS, that is
    a forbidden absorbing transition: it means the lane bounced from blocked
    straight back to pass without a saddle (review-required) checkpoint.
    """
    if next_letter != "P":
        return False, ""
    if all(letter == "B" for letter in window_letters) and len(window_letters) > 0:
        return True, "BLOCKED^K -> PASS without an intervening SADDLE"
    return False, ""


def _superposition_amplitudes(window_letters: list[str]) -> tuple[dict[str, float], str]:
    """Compute a Hadamard-like equal superposition over the next-letter alphabet,
    with classical interference from the recent window: the more often a letter
    appears in the window, the larger its amplitude becomes. After measurement
    the dominant letter is the most likely classical next outcome.
    """
    base = 1.0 / math.sqrt(len(LANE_WING_TOKENS))
    counts = {letter: 0 for letter in LANE_WING_TOKENS}
    for letter in window_letters:
        if letter in counts:
            counts[letter] += 1
    amplitudes: dict[str, float] = {}
    total = 0.0
    for letter in LANE_WING_TOKENS:
        weight = (counts[letter] + 1) ** 0.5
        amp = base * weight
        amplitudes[letter] = amp
        total += amp * amp
    if total > 0:
        norm = math.sqrt(total)
        amplitudes = {letter: amp / norm for letter, amp in amplitudes.items()}
    dominant = max(amplitudes, key=lambda k: amplitudes[k])
    return amplitudes, dominant


def classify_lane_transition(
    recent_statuses: list[str],
    next_status: str,
    window_size: int = DEFAULT_WINDOW_SIZE,
) -> LaneTransitionResult:
    window_letters = _validate_window(recent_statuses, window_size)
    next_letter = _status_to_letter(next_status)
    edge_label = "".join(window_letters) + "->" + next_letter
    alphabet = _alphabet_edges(window_size)
    edge_present = edge_label in alphabet and next_letter != "?" and "?" not in window_letters
    overlap_preserved = True
    if window_size > 1 and len(recent_statuses) >= window_size + 1:
        prior_window = _validate_window(recent_statuses[-(window_size + 1) : -1], window_size)
        overlap_preserved = prior_window[1:] == window_letters[:-1] or prior_window[1:] == window_letters[:-1]
    forbidden, reason = _detect_forbidden_absorbing(window_letters, next_letter)
    amplitudes, dominant = _superposition_amplitudes(window_letters)
    notes: list[str] = []
    if not edge_present:
        notes.append(
            "transition is off the validated De Bruijn edge alphabet over {P,B,S};"
            " an unmodeled lane status code is present in the window or next outcome"
        )
    if forbidden:
        notes.append(f"forbidden absorbing transition: {reason}")
    if "?" in window_letters or next_letter == "?":
        notes.append("unknown lane status letter detected; update PASS/BLOCKED/SADDLE token lists")
    review_recommended = (
        not edge_present
        or forbidden
        or "?" in window_letters
        or next_letter == "?"
        or next_letter == "S"
    )
    transition_classification = (
        "off_attractor_unclassified"
        if not edge_present
        else "forbidden_absorbing_transition"
        if forbidden
        else "saddle_review_transition"
        if next_letter == "S"
        else "pass_basin_transition"
        if next_letter == "P"
        else "blocked_basin_transition"
        if next_letter == "B"
        else "off_attractor_unclassified"
    )
    return LaneTransitionResult(
        classifier_id=CLASSIFIER_ID,
        classifier_contract_id=CLASSIFIER_CONTRACT_ID,
        graph_sequence_model_contract_id=GRAPH_SEQUENCE_MODEL_CONTRACT_ID,
        window_size=window_size,
        window=window_letters,
        next_letter=next_letter,
        next_status=next_status,
        transition_edge_label=edge_label,
        transition_classification=transition_classification,
        overlap_preserved=overlap_preserved,
        edge_present_in_alphabet=edge_present,
        forbidden_absorbing_pattern_detected=forbidden,
        forbidden_pattern_reason=reason,
        superposition_amplitudes=amplitudes,
        interference_dominant_letter=dominant,
        review_recommended=review_recommended,
        notes=notes,
    )


def classifier_status_payload() -> dict[str, object]:
    return {
        "classifier_id": CLASSIFIER_ID,
        "classifier_contract_id": CLASSIFIER_CONTRACT_ID,
        "graph_sequence_model_contract_id": GRAPH_SEQUENCE_MODEL_CONTRACT_ID,
        "module": "engel_debruijn_lane_traversal_classifier.py",
        "lane_wing_tokens": list(LANE_WING_TOKENS),
        "default_window_size": DEFAULT_WINDOW_SIZE,
        "pass_status_tokens": list(PASS_TOKENS),
        "blocked_status_tokens": list(BLOCKED_TOKENS),
        "saddle_status_tokens": list(SADDLE_TOKENS),
        "edge_alphabet_size_for_default_window": len(_alphabet_edges(DEFAULT_WINDOW_SIZE)),
        "safety_boundary": [
            "pure stdlib classification only",
            "no subprocess, network, provider, model, or local LLM",
            "no file write",
            "no source/route/queue/trusted-memory mutation",
            "no apply, build, promote, stage, or commit",
            "deterministic given identical inputs",
            "metadata only; never overrides lane final_status",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    parser = argparse.ArgumentParser(description="De Bruijn Lane Traversal Classifier V1 helper")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    cls_parser = sub.add_parser("classify")
    cls_parser.add_argument("--recent", action="append", default=[], help="recent lane statuses (oldest first); repeat the flag")
    cls_parser.add_argument("--next", required=True, help="the next lane status under review")
    cls_parser.add_argument("--window-size", type=int, default=DEFAULT_WINDOW_SIZE)
    args = parser.parse_args(argv)
    if args.command == "status":
        print(json.dumps(classifier_status_payload(), indent=2, sort_keys=True))
        return 0
    if args.command == "classify":
        result = classify_lane_transition(
            recent_statuses=list(args.recent),
            next_status=args.next,
            window_size=args.window_size,
        )
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
