#!/usr/bin/env python3
"""Prove the Governor decision plane keeps its contract (docs/ENGEL_GOVERNOR_DESIGN.md).

Four properties, each of which failed silently somewhere in Engel's history when
it was left unasserted:

  1. REPLAYABILITY -- T0 is a pure function of the feature dict: same features =>
     same outcome and same inputs_hash, with the clock frozen. A routing decision
     must be auditable months later from its receipt alone.
  2. FAIL-SAFE ASYMMETRY -- the per-class table is load-bearing: route fails OPEN
     (chat never breaks), allow/admit fail CLOSED (no action, no captured sample,
     on an unresolved verdict), persist fails closed on context-visibility only.
     A drive-by edit to the table must fail this sweep.
  3. METADATA NARROW-ONLY -- inbox metadata is the one new path into the decision
     plane. It may narrow capability, never widen it: unknown keys drop, clamps
     hold, a routing_hint can never claim a reserved lane, and nothing in the
     clamp output can enable a provider or grant an action.
  4. RECEIPT COMPLETENESS -- every verdict carries every contract field, and the
     echo-marker list is single-sourced here (the trainer imports it; a second
     copy would drift).

Exit 0 = contract holds. Non-zero = do not wire the Governor further.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import engel_governor as gov  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))


# ---------------------------------------------------------------------------
# 1. Replayability
# ---------------------------------------------------------------------------
def random_features(rng: random.Random) -> dict:
    lanes = sorted(gov.KNOWN_LANES) + ["", "bogus_lane"]
    return {
        "discipline": rng.choice(["math", "engineering", "aec", "", "poetry"]),
        "interactive": rng.choice([True, False, None]),
        "intent": rng.choice(["ask", "build", "status", ""]),
        "prompt_len": rng.randrange(0, 5000),
        "math_token_density": rng.random(),
        "explicit_lane_request": rng.choice(lanes),
        "is_code_artifact": rng.choice([True, False]),
        "context_bytes": rng.randrange(0, 60000),
        "caller": rng.choice(["chat_ui", "trainer", "cron"]),
        "routing_hint": rng.choice(lanes),
        "lane_health": {rng.choice(sorted(gov.KNOWN_LANES)): rng.choice([True, False])},
        "served": rng.choice([True, False]),
        "local_only_turn": rng.choice([True, False]),
        "contract_echo": rng.choice([True, False]),
        "has_result": rng.choice([True, False]),
        "has_check": rng.choice([True, False]),
        "has_independent_signal": rng.choice([True, False]),
        "has_concrete_relation": rng.choice([True, False]),
        "cas_refuted": rng.choice([True, False]),
        "proof_present": rng.choice([True, False]),
        "cites_real_artifact": rng.choice([True, False]),
        "persist_policy": rng.choice(["normal", "training", ""]),
        "echo": rng.choice([True, False]),
        "gate": rng.choice(["training_job", "sandbox", ""]),
        "gate_result": rng.choice([True, False, "true", 1, None]),
        "t0_uncertain": rng.choice([True, False]),
        "high_stakes": rng.choice([True, False]),
        "already_escalated": rng.choice([True, False]),
    }


class _FrozenPerfCounter:
    """time stub: if an outcome depended on the clock, freezing it would change
    nothing; the paired-run comparison below is what catches clock dependence."""

    @staticmethod
    def perf_counter() -> float:
        return 12345.0


def run_replayability() -> None:
    rng = random.Random(20260731)
    real_time = gov.time
    mismatches = 0
    try:
        for _ in range(500):
            feats = random_features(rng)
            for decision in gov.DECISION_CLASSES:
                gov.time = real_time
                first = gov.govern(decision, dict(feats))
                gov.time = _FrozenPerfCounter  # second run under a frozen clock
                second = gov.govern(decision, dict(feats))
                if (
                    first["outcome"] != second["outcome"]
                    or first["rule_id"] != second["rule_id"]
                    or first["inputs_hash"] != second["inputs_hash"]
                    or first["confidence"] != second["confidence"]
                ):
                    mismatches += 1
    finally:
        gov.time = real_time
    check(
        "replayability: 500 random feature dicts x 5 classes, identical outcome/rule/hash under a frozen clock",
        mismatches == 0,
        f"{mismatches} mismatches",
    )
    a = gov.features_hash({"b": 1, "a": 2})
    b = gov.features_hash({"a": 2, "b": 1})
    check("replayability: features_hash is key-order independent", a == b)
    check(
        "replayability: different features => different hash",
        gov.features_hash({"a": 1}) != gov.features_hash({"a": 2}),
    )


# ---------------------------------------------------------------------------
# 2. Fail-safe asymmetry
# ---------------------------------------------------------------------------
SPEC_FAILSAFE = {
    "route": "open",
    "allow": "closed",
    "admit": "closed",
    "persist": "closed_context",
    "escalate": "open",
}

EXPECTED_FAILSAFE_OUTCOME = {
    "route": gov.ROUTE_DEFER,
    "allow": "deny",
    "admit": False,
    "persist": "persist_no_context",
    "escalate": False,
}


def run_failsafe() -> None:
    check(
        "failsafe: _FAILSAFE table matches the design-spec literal (section 1.2)",
        gov._FAILSAFE == SPEC_FAILSAFE,
        f"got {gov._FAILSAFE}",
    )

    def _boom(_features: dict) -> tuple:
        raise RuntimeError("injected decider fault")

    originals = dict(gov._DECIDERS)
    try:
        for decision in gov.DECISION_CLASSES:
            gov._DECIDERS[decision] = _boom
            verdict = gov.govern(decision, {"anything": True})
            ok = (
                verdict["outcome"] == EXPECTED_FAILSAFE_OUTCOME[decision]
                and verdict["fallback_used"] is True
                and verdict["confidence"] == 0.0
                and verdict["rule_id"].endswith(("failsafe_open", "failsafe_closed", "failsafe_closed_context"))
            )
            check(
                f"failsafe: '{decision}' under an injected fault resolves {SPEC_FAILSAFE[decision]} "
                f"=> {EXPECTED_FAILSAFE_OUTCOME[decision]!r}",
                ok,
                f"verdict={verdict}",
            )
            gov._DECIDERS[decision] = originals[decision]
    finally:
        gov._DECIDERS.update(originals)

    # Non-dict features must not raise either -- they are an input fault, not a crash.
    for bad in (None, "text", 42, ["list"]):
        verdict = gov.govern("route", bad)
        check(
            f"failsafe: non-dict features {type(bad).__name__} still yields a verdict",
            verdict["decision"] == "route" and verdict["outcome"] == gov.ROUTE_DEFER,
            f"verdict={verdict}",
        )
    try:
        gov.govern("nonsense", {})
        check("failsafe: unknown decision class raises (caller bug, not runtime condition)", False)
    except ValueError:
        check("failsafe: unknown decision class raises (caller bug, not runtime condition)", True)


# ---------------------------------------------------------------------------
# 3. Metadata narrow-only
# ---------------------------------------------------------------------------
WHITELIST = {
    "training_discipline",
    "training_run_id",
    "interactive",
    "routing_hint",
    "persist_policy",
    "base_prompt",
}


def run_metadata() -> None:
    hostile = {
        "training_discipline": "math",
        "training_run_id": "r" * 999,
        "interactive": False,
        "routing_hint": gov.LANE_CODER,  # reserved -- must drop
        "persist_policy": "training",
        "base_prompt": "p" * 20000,
        # widening attempts -- every one must vanish
        "allow_provider_fallback": True,
        "provider": "openai",
        "local_only_training": False,
        "training_sample_eligible": True,
        "model_mode": "moe",
        "gate_result": True,
        "context_eligible": True,
        "echo": False,
        "lane": "anything",
    }
    clean = gov.clamp_inbox_metadata(hostile)
    check("metadata: output keys are a subset of the whitelist", set(clean) <= WHITELIST, f"got {sorted(clean)}")
    check(
        "metadata: no widening key survives (provider/gate/eligibility/model fields all dropped)",
        not (
            set(clean)
            & {
                "allow_provider_fallback",
                "provider",
                "local_only_training",
                "training_sample_eligible",
                "model_mode",
                "gate_result",
                "context_eligible",
                "echo",
                "lane",
            }
        ),
    )
    check("metadata: reserved-lane routing_hint is dropped", "routing_hint" not in clean)
    check(
        "metadata: training_run_id clamped to limit",
        len(clean.get("training_run_id", "")) == gov.TRAINING_RUN_ID_MAX_CHARS,
    )
    check(
        "metadata: base_prompt clamped to limit",
        len(clean.get("base_prompt", "")) == gov.BASE_PROMPT_MAX_CHARS,
    )
    check(
        "metadata: valid discipline/interactive/persist_policy survive the clamp",
        clean.get("training_discipline") == "math"
        and clean.get("interactive") is False
        and clean.get("persist_policy") == "training",
    )

    junk = gov.clamp_inbox_metadata(
        {
            "training_discipline": "poetry",
            "routing_hint": "not_a_lane",
            "interactive": "yes",
            "persist_policy": "forever",
            "training_run_id": 42,
            "base_prompt": 42,
        }
    )
    check("metadata: every out-of-range value falls back to absent", junk == {}, f"got {junk}")
    check("metadata: non-dict metadata clamps to empty", gov.clamp_inbox_metadata("x") == {})

    hint_ok = gov.clamp_inbox_metadata({"routing_hint": gov.LANE_SPARSE_MOE})
    check(
        "metadata: known non-reserved routing_hint survives",
        hint_ok.get("routing_hint") == gov.LANE_SPARSE_MOE,
    )
    # End-to-end: even a surviving hint cannot pull a code artifact off the coder lane.
    verdict = gov.govern("route", {"is_code_artifact": True, "routing_hint": gov.LANE_SPARSE_MOE})
    check(
        "metadata: reserved-lane guard outranks a surviving routing_hint",
        verdict["outcome"] == gov.LANE_CODER and verdict["rule_id"] == "route.reserved.code",
        f"verdict={verdict}",
    )


# ---------------------------------------------------------------------------
# Lane vocabulary must be REAL.
# ---------------------------------------------------------------------------
def run_lane_vocabulary() -> None:
    """Every lane the Governor can name must be a selected_provider/runtime_provider
    string the chat service actually stamps.

    Caught live (2026-07-31): 4 of the 6 lane constants were invented names
    ("engel_math_lane", "deepseek_r1_reasoner", "local_cuda_qwen_coder",
    "aligned_7b_default") sitting under a comment that claimed they matched the service.
    A route verdict naming a lane that exists nowhere is a silent no-op with an
    unauditable receipt -- the exact failure the Governor exists to prevent.

    The scan MUST read assignment forms as well as dict literals: the 14B lane's
    canonical id is set by `receipt["selected_provider"] = "ct_deep_local_specialist"`
    (service :12431), so a literal-only scan reports a real lane as invented and invites
    a "fix" that breaks the compare at :7544. That false positive happened here.
    """
    import re

    service = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "engel_main_server_chat_http_service.py"
    ).read_text(encoding="utf-8", errors="replace")
    real: set[str] = set()
    for pattern in (
        r'"selected_provider":\s*"([A-Za-z0-9_\-]+)"',
        r'\["selected_provider"\]\s*=\s*"([A-Za-z0-9_\-]+)"',
        r"\['selected_provider'\]\s*=\s*'([A-Za-z0-9_\-]+)'",
        r'"runtime_provider":\s*"([A-Za-z0-9_\-]+)"',
        r'\["runtime_provider"\]\s*=\s*"([A-Za-z0-9_\-]+)"',
    ):
        real |= set(re.findall(pattern, service))
    unknown = sorted(lane for lane in gov.KNOWN_LANES if lane not in real)
    check(
        "lanes: every KNOWN_LANES id is a real service lane",
        not unknown,
        f"not found in the chat service: {unknown}",
    )
    check(
        "lanes: the default lane is real",
        gov.LANE_DEFAULT in real,
        f"{gov.LANE_DEFAULT!r} is not a service lane id",
    )


# ---------------------------------------------------------------------------
# Route/admit/persist behaviour -- the rules the wire-up will rely on.
# ---------------------------------------------------------------------------
def run_rules() -> None:
    v = gov.govern("route", {"discipline": "math", "interactive": False})
    check(
        "route: non-interactive math selects the capable sparse-MoE lane",
        v["outcome"] == gov.LANE_SPARSE_MOE and v["rule_id"] == "route.discipline.math",
    )
    v = gov.govern("route", {"discipline": "math", "interactive": True})
    check(
        "route: interactive math defers to today's heuristics (latency unchanged)",
        v["outcome"] == gov.ROUTE_DEFER,
    )
    v = gov.govern("route", {"discipline": "math"})
    check("route: absent interactive defaults to interactive (defer)", v["outcome"] == gov.ROUTE_DEFER)
    v = gov.govern(
        "route",
        {"discipline": "math", "interactive": False, "lane_health": {gov.LANE_SPARSE_MOE: False}},
    )
    check(
        "route: unhealthy capable lane degrades to defer, receipted as lane_down",
        v["outcome"] == gov.ROUTE_DEFER and v["rule_id"] == "route.discipline.math.lane_down",
    )
    v = gov.govern("route", {"discipline": "engineering", "interactive": False, "context_bytes": 50000})
    check(
        "route: non-interactive engineering with deep context selects the 14B lane",
        v["outcome"] == gov.LANE_DEEP_LOCAL,
    )
    v = gov.govern("route", {"explicit_lane_request": gov.LANE_DEFAULT, "discipline": "math", "interactive": False})
    check(
        "route: operator-explicit lane always wins at confidence 1.0",
        v["outcome"] == gov.LANE_DEFAULT and v["confidence"] == 1.0,
    )

    base_admit = {
        "discipline": "math",
        "served": True,
        "local_only_turn": True,
        "contract_echo": False,
        "has_result": True,
        "has_check": True,
        "has_independent_signal": True,
        "has_concrete_relation": True,
        "cas_refuted": False,
    }
    check("admit: clean verified math sample is admitted", gov.govern("admit", base_admit)["outcome"] is True)
    for field, rule in (
        ("contract_echo", "admit.reject.contract_echo"),
        ("cas_refuted", "admit.math.reject.cas_refuted"),
    ):
        poisoned = dict(base_admit, **{field: True})
        v = gov.govern("admit", poisoned)
        check(f"admit: {field} rejects with rule {rule}", v["outcome"] is False and v["rule_id"] == rule)
    v = gov.govern("admit", dict(base_admit, local_only_turn=False))
    check(
        "admit: a provider/bridge turn is never captured",
        v["outcome"] is False and v["rule_id"] == "admit.reject.nonlocal_provider",
    )
    v = gov.govern(
        "admit",
        {"discipline": "engineering", "served": True, "local_only_turn": True, "proof_present": True, "cites_real_artifact": False},
    )
    check("admit: engineering without a real cited artifact is rejected", v["outcome"] is False)

    check(
        "persist: training turn persists without context eligibility",
        gov.govern("persist", {"persist_policy": "training"})["outcome"] == "persist_no_context",
    )
    check(
        "persist: echo reply is quarantined regardless of policy",
        gov.govern("persist", {"persist_policy": "normal", "echo": True})["outcome"] == "persist_no_context",
    )
    check(
        "persist: normal turn stays context-eligible",
        gov.govern("persist", {"persist_policy": "normal"})["outcome"] == "persist_context",
    )

    for value in (False, "true", 1, None):
        v = gov.govern("allow", {"gate": "training_job", "gate_result": value})
        check(
            f"allow: gate_result {value!r} (not literally True) denies",
            v["outcome"] == "deny",
        )
    check(
        "allow: literal True allows",
        gov.govern("allow", {"gate": "training_job", "gate_result": True})["outcome"] == "allow",
    )
    check(
        "escalate: one escalation per turn is enforced",
        gov.govern("escalate", {"t0_uncertain": True, "high_stakes": True, "already_escalated": True})["outcome"] is False,
    )
    check(
        "escalate: uncertain + high stakes escalates",
        gov.govern("escalate", {"t0_uncertain": True, "high_stakes": True})["outcome"] is True,
    )


# ---------------------------------------------------------------------------
# 4. Receipt completeness + single-source markers
# ---------------------------------------------------------------------------
def run_receipts() -> None:
    incomplete = 0
    for decision in gov.DECISION_CLASSES:
        verdict = gov.govern(decision, {"discipline": "math", "interactive": False})
        missing = [field for field in gov.VERDICT_FIELDS if field not in verdict]
        if missing or verdict["tier"] != "T0" or verdict["model_id"] != "" or not verdict["rule_id"]:
            incomplete += 1
    check("receipts: every verdict carries every contract field (T0, empty model_id, rule named)", incomplete == 0)

    record = gov.decision_receipt(
        gov.govern("route", {"discipline": "math", "interactive": False}),
        features={"discipline": "math"},
        outcome_observed={"status": "DONE", "admitted": True},
    )
    check(
        "receipts: decision_receipt carries schema + verdict + features + observed outcome",
        record.get("schema") == gov.DECISION_RECEIPT_SCHEMA
        and "verdict" in record
        and record.get("features") == {"discipline": "math"}
        and record.get("outcome_observed", {}).get("admitted") is True,
    )

    check(
        "markers: a known contract phrase is caught by looks_like_contract_echo",
        gov.looks_like_contract_echo("Answer ONLY in this filled-in form:") is True
        and gov.looks_like_contract_echo("x = 4, Check: 2*4 = 8") is False,
    )
    trainer_src = (TOOLS / "run_engel_flutter_main_ui_prompt_training.py").read_text(
        encoding="utf-8", errors="replace"
    )
    check(
        "markers: trainer imports the single-source list from engel_governor (no drifting copy)",
        "from engel_governor import CONTRACT_ECHO_MARKERS" in trainer_src
        and "_CONTRACT_ECHO_MARKERS = (" not in trainer_src,
    )


# ---------------------------------------------------------------------------
# 5. Service wire-up -- the actual _sparse_moe_route_decision seam.
# ---------------------------------------------------------------------------
def run_service_wireup() -> None:
    import os

    import engel_main_server_chat_http_service as svc

    # A conceptual teaching prompt: no digits, no prove/theorem keywords -- the
    # exact shape both legacy exclusions (digit gate + score threshold) miss.
    teaching_prompt = (
        "Explain why the chain rule works, then pose and solve one concrete "
        "algebra problem of your own, showing an independent Check."
    )
    training_request = {
        "metadata": {
            "training_discipline": "math",
            "training_run_id": "verify-governor",
            "interactive": False,
            "persist_policy": "training",
        }
    }
    os.environ.pop("ENGEL_GOVERNOR_ROUTING_ENABLED", None)
    route = svc._sparse_moe_route_decision(teaching_prompt, training_request)
    check(
        "wireup: declared non-interactive math turn selects sparse-MoE despite scoring 0 on legacy keywords",
        route.get("selected") is True
        and isinstance(route.get("governor"), dict)
        and route["governor"].get("rule_id") == "route.discipline.math",
        f"route={route}",
    )
    legacy = svc._sparse_moe_route_decision(teaching_prompt, {})
    check(
        "wireup: the same prompt without metadata keeps legacy behaviour (not selected)",
        legacy.get("selected") is not True and "governor" not in legacy,
        f"route={legacy}",
    )
    interactive_req = {
        "metadata": {"training_discipline": "math", "interactive": True}
    }
    route = svc._sparse_moe_route_decision(teaching_prompt, interactive_req)
    check(
        "wireup: interactive metadata never forces the heavy lane (latency path unchanged)",
        route.get("selected") is not True,
        f"route={route}",
    )
    os.environ["ENGEL_GOVERNOR_ROUTING_ENABLED"] = "0"
    try:
        route = svc._sparse_moe_route_decision(teaching_prompt, training_request)
        check(
            "wireup: kill switch off => byte-identical legacy routing even with metadata",
            route.get("selected") is not True and "governor" not in route,
            f"route={route}",
        )
    finally:
        os.environ.pop("ENGEL_GOVERNOR_ROUTING_ENABLED", None)
    deep_prompt = "Review this engineering context.\n" + ("x" * 25000)
    deep_request = {
        "metadata": {"training_discipline": "engineering", "interactive": False}
    }
    check(
        "wireup: non-interactive engineering with deep context reaches the 14B lane",
        svc._prompt_requests_deep_local_specialist(deep_prompt, deep_request) is True,
    )
    check(
        "wireup: the same deep prompt without metadata stays off the 14B lane",
        svc._prompt_requests_deep_local_specialist(deep_prompt, {}) is False,
    )
    small_eng = svc._sparse_moe_route_decision("Ground one claim in a real Engel component.", deep_request)
    check(
        "wireup: non-interactive engineering with small context selects sparse-MoE",
        small_eng.get("selected") is True
        and small_eng.get("governor", {}).get("rule_id") == "route.discipline.engineering",
        f"route={small_eng}",
    )
    hostile_request = {
        "metadata": {
            "training_discipline": "math",
            "interactive": False,
            "allow_provider_fallback": True,
            "local_only_training": False,
        }
    }
    context = svc._request_governor_context(hostile_request)
    check(
        "wireup: _request_governor_context strips widening keys before routing sees them",
        "allow_provider_fallback" not in context and "local_only_training" not in context,
        f"context={context}",
    )


def main() -> int:
    run_replayability()
    run_failsafe()
    run_metadata()
    run_lane_vocabulary()
    run_rules()
    run_receipts()
    run_service_wireup()
    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED:")
        for name in failed:
            print(f"  - {name}")
        return 1
    print("verify_engel_governor: GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
