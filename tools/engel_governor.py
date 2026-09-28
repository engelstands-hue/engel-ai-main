"""Engel Governor -- the decision plane (T0).

Design: docs/ENGEL_GOVERNOR_DESIGN.md. This module DECIDES; it never executes.
It is pure by contract: no file writes, no network, no subprocess, no provider
calls, and the decision functions use no clock and no randomness -- the same
feature dict always produces the same outcome (that is what makes a routing
decision auditable months later via ``inputs_hash``). Callers compute the
features (including anything that needs disk or sympy, e.g. ``cas_refuted`` or
``cites_real_artifact``) and callers write the receipts.

Failure behaviour is per decision class (``_FAILSAFE``) and asymmetric on
purpose: a routing outage degrades to today's behaviour (fail-open), while
action gating and training-sample admission fail closed -- an uncaptured good
sample costs nothing, a captured bad one poisons the corpus.

Verifier: tools/verify_engel_governor.py.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

GOVERNOR_SCHEMA = "engel_governor_verdict_v1"
DECISION_RECEIPT_SCHEMA = "engel_governor_decision_v1"

DECISION_CLASSES = ("route", "allow", "admit", "persist", "escalate")

# The asymmetric fail-safe table from the design spec (section 1.2). The
# verifier asserts this literal, so a drive-by edit here fails the sweep.
_FAILSAFE = {
    "route": "open",
    "allow": "closed",
    "admit": "closed",
    "persist": "closed_context",
    "escalate": "open",
}

# ---------------------------------------------------------------------------
# Lane vocabulary -- these are the LITERAL selected_provider strings the chat
# service stamps on a receipt, verified against
# tools/engel_main_server_chat_http_service.py. They are not free-form labels:
# a route outcome is only actionable if the caller can match it to the lane the
# service actually reports, and a receipt is only auditable if the lane name in
# it appears somewhere else in the system.
#
# (2026-07-31) Corrected: 4 of these 6 previously carried invented names
# ("engel_math_lane", "deepseek_r1_reasoner", "local_cuda_qwen_coder",
# "aligned_7b_default") under a comment claiming they matched the service. They
# did not. Wired in as-was, those route verdicts would have named lanes that
# exist nowhere -- a silent no-op with an unauditable receipt.
#
# NOTE on the 14B: it carries TWO ids. The receipt builder stamps
# "main_server_deep_local_specialist", then the dispatch REASSIGNS
# selected_provider = "ct_deep_local_specialist" (service :12431), which is also
# the key in the activation-depth map (:9874) and the literal
# _prompt_requests_deep_local_specialist compares the Governor verdict against
# (:7544). The reassigned value is the canonical one, so that is what belongs
# here -- matching the receipt-builder name instead silently breaks that compare.
# verify_engel_governor.py asserts every id against the service source, reading
# BOTH the dict-literal and the assignment forms (a literal-only scan is what
# made the 14B look invented in the first place).
LANE_MATH_CAS = "math_lane"
LANE_SPARSE_MOE = "ct_sparse_moe_specialist"
LANE_DEEP_LOCAL = "ct_deep_local_specialist"
LANE_REASONER = "math_reasoning_specialist"
LANE_CODER = "main_server_code_lane_model"
LANE_DEFAULT = "local"

# "defer" is a first-class route outcome: the Governor has no opinion and the
# caller proceeds with today's heuristics unchanged. Interactive turns defer by
# default, which is what keeps chat latency byte-identical to legacy.
ROUTE_DEFER = "defer_to_heuristics"

KNOWN_LANES = frozenset(
    {
        LANE_MATH_CAS,
        LANE_SPARSE_MOE,
        LANE_DEEP_LOCAL,
        LANE_REASONER,
        LANE_CODER,
        LANE_DEFAULT,
    }
)
# Reserved lanes own their traffic by guard, not by hint: a routing_hint can
# never claim the code lane and never move a code artifact off it.
RESERVED_LANES = frozenset({LANE_CODER})

# (2026-08-01) "communication" joins the trusted set with the chat-communication
# curriculum. A discipline the clamp drops is not merely unlabelled: the turn loses
# its routing/persistence hint and CT246 grades it as construction, which is how a
# chat-voice answer would end up judged against an evidence-ledger bar it was never
# asked for. The value is still only a label -- it cannot enable a provider or admit
# a sample -- so widening it stays inside the clamp's narrow-only contract.
TRUSTED_DISCIPLINES = frozenset({"math", "engineering", "aec", "communication"})
TRUSTED_PERSIST_POLICIES = frozenset({"normal", "training"})
TRAINING_RUN_ID_MAX_CHARS = 128
BASE_PROMPT_MAX_CHARS = 8000

# Engineering turns with a large assembled context route to the long-context
# 14B rather than the sparse-MoE reasoner.
DEEP_CONTEXT_BYTES = 20_000

# ---------------------------------------------------------------------------
# Contract-echo markers -- SINGLE SOURCE. The trainer imports these; the
# service-side ingest guard uses them too. Two copies would drift, so the one
# definition lives here (design spec section 4.3).
# ---------------------------------------------------------------------------
CONTRACT_ECHO_MARKERS = (
    # older contract phrasings (persistent memory can replay them)
    "if you could not check it",
    "the residual or agreement it produced",
    "never put a stated result here",
    "do not restate these instructions",
    "one line with the answer",
    "substitute the answer back, differentiate back",
    "substitute the answer back into the original equation and show agreement",
    "the key steps.",
    "each claim tied to a real engel component",
    "name that verifier or receipt",
    "this line must appear",
    "in exactly this structure",
    "these four labeled lines",
    # current fill-in-form phrasings
    "answer only in this filled-in form",
    "do not describe the form",
    "repeat these instructions",
    "<your answer",
    "the key steps, briefly>",
    "the number you got>",
    "or 'no verified result' if you could not",
    "a claim tied to a real engel component",
    "a real file path or a verify",
    "if you cannot point to a real one",
)

# The prompt-training wrapper itself (engel_ui_prompt_training_support.build_training_prompt
# emits "Training depth: <level> (<profile>)\n<instruction>\n\nTraining task:\n<base>").
# The answer-contract markers above only describe how a turn must ANSWER, so a delivery that
# lost its metadata in transit -- older runs, or any path that did not set persist_policy --
# was stored as ordinary user chat and then RECALLED as something Joshua said. Measured
# 2026-08-13: 335 such rows were still context-eligible in the persistent store. These two
# phrases are the wrapper's own scaffolding and do not occur in real conversation, so they
# make the metadata-free discriminator work on the wrapper as well as on the contract.
TRAINING_WRAPPER_MARKERS = (
    "training depth:",
    "training task:",
)


def looks_like_contract_echo(text: Any) -> bool:
    """True when the text carries a distinctive answer-contract phrase.

    A small model sometimes RESTATES the injected contract instead of answering;
    those echoes mention every heading, so structural checks alone wrongly
    accept them. Case/whitespace-normalised substring match, no regex.
    """
    low = " ".join(str(text or "").split()).casefold()
    return bool(low) and any(marker in low for marker in CONTRACT_ECHO_MARKERS)


def looks_like_training_wrapper(text: Any) -> bool:
    """True when the text is a prompt-training DELIVERY wrapper, not real conversation.

    Deliberately separate from ``looks_like_contract_echo``: that predicate also gates
    training-sample admission, and widening it would quietly change what the pipeline
    accepts. This one exists for memory hygiene -- a wrapper that reached persistence
    without its metadata must still be withheld from recall.
    """
    low = " ".join(str(text or "").split()).casefold()
    return bool(low) and any(marker in low for marker in TRAINING_WRAPPER_MARKERS)


# ---------------------------------------------------------------------------
# Inbox metadata clamp -- the trust boundary (design spec section 3).
# ---------------------------------------------------------------------------
def clamp_inbox_metadata(metadata: Any) -> dict[str, Any]:
    """Whitelist-and-clamp UI-chat-inbox metadata. Narrow-only by construction:
    unknown keys are dropped, out-of-range values fall back to the default, and
    nothing in the output can enable a provider, disable a gate, mark a turn
    admissible, or grant an action -- the returned keys feed routing/persistence
    features only. ``base_prompt`` is persist-only (section 4.2 substitution).
    """
    clean: dict[str, Any] = {}
    if not isinstance(metadata, dict):
        return clean
    discipline = str(metadata.get("training_discipline") or "").strip().casefold()
    if discipline in TRUSTED_DISCIPLINES:
        clean["training_discipline"] = discipline
    run_id = metadata.get("training_run_id")
    if isinstance(run_id, str) and run_id.strip():
        clean["training_run_id"] = run_id.strip()[:TRAINING_RUN_ID_MAX_CHARS]
    if isinstance(metadata.get("interactive"), bool):
        clean["interactive"] = metadata["interactive"]
    hint = str(metadata.get("routing_hint") or "").strip().casefold()
    if hint in KNOWN_LANES and hint not in RESERVED_LANES:
        clean["routing_hint"] = hint
    policy = str(metadata.get("persist_policy") or "").strip().casefold()
    if policy in TRUSTED_PERSIST_POLICIES:
        clean["persist_policy"] = policy
    base_prompt = metadata.get("base_prompt")
    if isinstance(base_prompt, str) and base_prompt.strip():
        clean["base_prompt"] = base_prompt[:BASE_PROMPT_MAX_CHARS]
    return clean


# ---------------------------------------------------------------------------
# Verdict contract.
# ---------------------------------------------------------------------------
VERDICT_FIELDS = (
    "decision",
    "outcome",
    "confidence",
    "reason",
    "rule_id",
    "tier",
    "model_id",
    "fallback_used",
    "latency_ms",
    "inputs_hash",
)


def features_hash(features: Any) -> str:
    """sha256 over the canonical-JSON feature dict. Excludes nothing the
    decision saw and includes nothing it did not (latency is measured outside
    the decision), so same hash => same T0 outcome, replayable forever."""
    canonical = json.dumps(
        features if isinstance(features, dict) else {},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _verdict(
    decision: str,
    outcome: Any,
    confidence: float,
    reason: str,
    rule_id: str,
    *,
    fallback_used: bool,
    latency_ms: float,
    inputs_hash: str,
) -> dict[str, Any]:
    return {
        "schema": GOVERNOR_SCHEMA,
        "decision": decision,
        "outcome": outcome,
        "confidence": float(confidence),
        "reason": reason,
        "rule_id": rule_id,
        "tier": "T0",
        "model_id": "",
        "fallback_used": bool(fallback_used),
        "latency_ms": float(latency_ms),
        "inputs_hash": inputs_hash,
    }


# ---------------------------------------------------------------------------
# T0 deciders. Each returns (outcome, confidence, reason, rule_id) and is a
# pure function of the feature dict.
# ---------------------------------------------------------------------------
def _clean_lane(value: Any) -> str:
    lane = str(value or "").strip().casefold()
    return lane if lane in KNOWN_LANES else ""


def _lane_healthy(features: dict[str, Any], lane: str) -> bool:
    """Absent health data means healthy: lane_health is an optional veto, and
    treating unknown as unhealthy would silently disable every rule."""
    health = features.get("lane_health")
    if not isinstance(health, dict):
        return True
    return health.get(lane, True) is not False


def _decide_route(f: dict[str, Any]) -> tuple[Any, float, str, str]:
    explicit = _clean_lane(f.get("explicit_lane_request"))
    if explicit:
        return (
            explicit,
            1.0,
            "operator explicitly selected this lane; the Governor never overrides a human",
            "route.operator_explicit",
        )
    if f.get("is_code_artifact") is True:
        return (
            LANE_CODER,
            1.0,
            "code-artifact requests stay on the coder + conical build path",
            "route.reserved.code",
        )
    hint = _clean_lane(f.get("routing_hint"))
    if hint and hint not in RESERVED_LANES and _lane_healthy(f, hint):
        return (
            hint,
            0.9,
            "trusted local caller supplied a routing hint within its reach",
            "route.hint",
        )
    # interactive defaults True: a human is assumed to be waiting unless a
    # trusted caller says otherwise, so heavy lanes stay opt-in.
    interactive = f.get("interactive") is not False
    discipline = str(f.get("discipline") or "").strip().casefold()
    if not interactive and discipline == "math":
        if _lane_healthy(f, LANE_SPARSE_MOE):
            return (
                LANE_SPARSE_MOE,
                0.9,
                "non-interactive math turn: quality over latency, capable lane",
                "route.discipline.math",
            )
        return (
            ROUTE_DEFER,
            0.5,
            "capable math lane unhealthy; degrade to today's heuristics",
            "route.discipline.math.lane_down",
        )
    if not interactive and discipline == "engineering":
        context_bytes = f.get("context_bytes")
        deep = isinstance(context_bytes, (int, float)) and context_bytes >= DEEP_CONTEXT_BYTES
        lane = LANE_DEEP_LOCAL if deep else LANE_SPARSE_MOE
        if _lane_healthy(f, lane):
            return (
                lane,
                0.9,
                "non-interactive engineering turn routed by context size",
                "route.discipline.engineering.deep_context"
                if deep
                else "route.discipline.engineering",
            )
        return (
            ROUTE_DEFER,
            0.5,
            "capable engineering lane unhealthy; degrade to today's heuristics",
            "route.discipline.engineering.lane_down",
        )
    if not interactive and discipline == "aec":
        return (
            LANE_DEFAULT,
            0.9,
            "aec persona practice belongs to the aligned persona lane",
            "route.discipline.aec",
        )
    return (
        ROUTE_DEFER,
        0.5,
        "no Governor opinion; existing heuristics decide (legacy behaviour)",
        "route.defer",
    )


def _decide_admit(f: dict[str, Any]) -> tuple[Any, float, str, str]:
    """Absorbs the trainer's discipline-eligibility gates unchanged in
    behaviour (run_engel_flutter_main_ui_prompt_training._apply_discipline_
    eligibility); the trainer computes the booleans, this orders them."""
    discipline = str(f.get("discipline") or "aec").strip().casefold()
    if discipline not in ("math", "engineering", "communication"):
        ok = f.get("server_flag_eligible") is True
        return (
            ok,
            1.0,
            "aec admission passes through the server training flag unchanged",
            "admit.aec.server_flag",
        )
    if f.get("served") is not True:
        return (False, 1.0, "turn was not served cleanly (status not DONE)", "admit.reject.not_served")
    if f.get("local_only_turn") is not True:
        return (
            False,
            1.0,
            "turn escalated to a non-local provider; never captured for local training",
            "admit.reject.nonlocal_provider",
        )
    if f.get("contract_echo") is True:
        return (False, 1.0, "reply restates the answer contract instead of answering", "admit.reject.contract_echo")
    if discipline == "communication":
        # This lane inverts the other two: math and engineering admit an answer for the
        # structure it SHOWS, communication admits one for the structure it withholds,
        # because its accepted text is trained directly as Engel's chat voice and a
        # labelled answer here teaches Engel to answer Joshua in headings.
        if f.get("conversational_voice_ok") is True:
            return (
                True,
                1.0,
                "reply reads as Engel's own first-person chat prose",
                "admit.communication.accept",
            )
        return (
            False,
            1.0,
            "reply is scaffolded, filler, or not in Engel's chat voice",
            "admit.communication.reject.not_conversational",
        )
    if discipline == "math":
        structure = (
            f.get("has_result") is True
            and f.get("has_check") is True
            and f.get("has_independent_signal") is True
            and f.get("has_concrete_relation") is True
        )
        if not structure:
            return (
                False,
                1.0,
                "math answer lacks the verification discipline (Result/Check/independent method/concrete relation)",
                "admit.math.reject.structure",
            )
        if f.get("cas_refuted") is True:
            return (False, 1.0, "CAS proved an arithmetic relation in the answer false", "admit.math.reject.cas_refuted")
        return (True, 1.0, "math answer shows a concrete CAS-consistent independent Check", "admit.math.accept")
    if not (f.get("proof_present") is True and f.get("cites_real_artifact") is True):
        return (
            False,
            1.0,
            "engineering answer has no Proof line citing a real, existing artifact",
            "admit.engineering.reject.ungrounded",
        )
    return (True, 1.0, "engineering answer cites a real, existing verifier/receipt", "admit.engineering.accept")


def _decide_persist(f: dict[str, Any]) -> tuple[Any, float, str, str]:
    """persist and context_eligible are independent booleans; outcome encodes
    both. Records are always kept (receipts ARE the corpus) -- what varies is
    whether a later turn may load them into its prompt."""
    if f.get("echo") is True:
        return (
            "persist_no_context",
            1.0,
            "echo reply quarantined: kept for audit, never re-injected into context",
            "persist.echo_quarantine",
        )
    if str(f.get("persist_policy") or "").strip().casefold() == "training":
        return (
            "persist_no_context",
            1.0,
            "training turn: persist the record, withhold it from later context",
            "persist.training_turn",
        )
    return ("persist_context", 1.0, "normal turn persists and stays context-eligible", "persist.normal")


def _decide_allow(f: dict[str, Any]) -> tuple[Any, float, str, str]:
    """Action gating stays deterministic forever: the existing gates keep their
    implementations and report through here. gate_result must be literally True."""
    gate = str(f.get("gate") or "unknown").strip().casefold() or "unknown"
    if f.get("gate_result") is True:
        return ("allow", 1.0, f"deterministic gate '{gate}' passed", f"allow.gate.{gate}")
    return ("deny", 1.0, f"deterministic gate '{gate}' did not pass", f"allow.gate.{gate}")


def _decide_escalate(f: dict[str, Any]) -> tuple[Any, float, str, str]:
    if f.get("already_escalated") is True:
        return (False, 1.0, "one escalation per turn; already spent", "escalate.bounded")
    if f.get("t0_uncertain") is True and f.get("high_stakes") is True:
        return (True, 0.9, "T0 uncertain on a high-stakes call", "escalate.granted")
    return (False, 1.0, "escalation is an optimisation, not needed here", "escalate.not_needed")


_DECIDERS = {
    "route": _decide_route,
    "admit": _decide_admit,
    "persist": _decide_persist,
    "allow": _decide_allow,
    "escalate": _decide_escalate,
}

_FAILSAFE_OUTCOMES = {
    "route": (ROUTE_DEFER, "route.failsafe_open"),
    "allow": ("deny", "allow.failsafe_closed"),
    "admit": (False, "admit.failsafe_closed"),
    "persist": ("persist_no_context", "persist.failsafe_closed_context"),
    "escalate": (False, "escalate.failsafe_open"),
}


def govern(decision: str, features: Any) -> dict[str, Any]:
    """Answer one question. Unknown decision classes raise (that is a caller
    bug, not a runtime condition); anything the decider itself raises resolves
    through the per-class fail-safe with ``fallback_used=True``."""
    if decision not in DECISION_CLASSES:
        raise ValueError(f"unknown governor decision class: {decision!r}")
    feats = features if isinstance(features, dict) else {}
    inputs_hash = features_hash(feats)
    started = time.perf_counter()
    try:
        outcome, confidence, reason, rule_id = _DECIDERS[decision](feats)
        fallback = False
    except Exception as exc:  # noqa: BLE001 -- the fail-safe IS the handler
        outcome, rule_id = _FAILSAFE_OUTCOMES[decision]
        confidence = 0.0
        reason = f"decider failed ({type(exc).__name__}); {_FAILSAFE[decision]} fail-safe applied"
        fallback = True
    latency_ms = (time.perf_counter() - started) * 1000.0
    return _verdict(
        decision,
        outcome,
        confidence,
        reason,
        rule_id,
        fallback_used=fallback,
        latency_ms=latency_ms,
        inputs_hash=inputs_hash,
    )


def decision_receipt(
    verdict: dict[str, Any],
    features: Any = None,
    outcome_observed: Any = None,
) -> dict[str, Any]:
    """Pure serializer for a governor_decision receipt record. The CALLER
    appends it (reports/governor/governor_decisions.jsonl) and the caller
    stamps the timestamp -- this module never touches a clock for content."""
    record: dict[str, Any] = {
        "schema": DECISION_RECEIPT_SCHEMA,
        "verdict": dict(verdict or {}),
    }
    if isinstance(features, dict):
        record["features"] = dict(features)
    if outcome_observed is not None:
        record["outcome_observed"] = outcome_observed
    return record
