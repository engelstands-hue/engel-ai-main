"""Engel GAIS layer - Governed AI System (pillars: deterministic core, stochastic
models, confidence of inference, hardware) mapped HONESTLY onto what Engel runs.

Pillar 3 is the new piece this module implements: `score_inference()` computes a
per-reply trust verdict from REAL measured signals already produced by Engel's
deterministic gates and advisory heads (sympy proof/refutation, SLM reply-quality
head, quick-lane confidence, semantic-quality gates, persona-guard markers).
There is no invented precision: with zero observable signals the verdict is
`trust_percent: None` / band "unverified", never a made-up percentage, and the
weights are declared `engineered_v1_uncalibrated` in every verdict until they are
actually fit against graded rows.

Contract (same as the service's other attach helpers): advisory-only, never
raises, never mutates the reply, bounded sub-millisecond cost on the hot path
(all inputs are already-computed receipt fields plus two stdlib marker scans).

`gais_capabilities()` follows the ModelExpress honesty pattern: every pillar
reports {available, reasons_unavailable[...]} probed on THIS host at call time -
a capability that cannot work says so with concrete reasons instead of being
stubbed to pretend it works. `consensus_agreement()` is the deterministic
agreement metric used by the on-demand cross-model consensus lane
(tools/engel_gais_consensus.py); it measures lexical + numeric convergence and
says so - convergence is evidence, not proof of truth.
"""

from __future__ import annotations

import difflib
import importlib.util
import math
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

SCHEMA = "engel_gais_inference_confidence_v1"
CAPABILITIES_SCHEMA = "engel_gais_capabilities_v1"
AGREEMENT_SCHEMA = "engel_gais_consensus_agreement_v1"
CALIBRATION = "engineered_v1_uncalibrated"

ROOT = Path(__file__).resolve().parents[1]

# Trust bands. "verified" is reachable ONLY through a deterministic proof
# (the sympy math lane serving a CAS-verified result); no accumulation of soft
# signals may claim it. "refuted" is reachable ONLY through a CAS-proven
# refutation. Everything else is graded evidence.
BAND_VERIFIED = "verified"
BAND_HIGH = "high"
BAND_MEDIUM = "medium"
BAND_LOW = "low"
BAND_REFUTED = "refuted"
BAND_UNVERIFIED = "unverified"

# Soft-signal trust is clamped away from both certainties on purpose: without a
# deterministic proof the verdict may never read as certainty, and without a
# refutation it may never read as impossibility.
SOFT_TRUST_FLOOR = 2.0
SOFT_TRUST_CEIL = 97.0
PROOF_TRUST = 99.0
REFUTED_TRUST_CEIL = 12.0


def _env_truth(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "") or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "enabled"}


def _env_float(name: str, default: float) -> float:
    try:
        value = float(str(os.environ.get(name, "") or "").strip() or default)
    except ValueError:
        return default
    # 'nan'/'inf' parse as floats but would silently break every comparison
    return value if math.isfinite(value) else default


def _sigmoid(x: float) -> float:
    if x >= 40.0:
        return 1.0
    if x <= -40.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def _label_of(value: Any) -> str:
    """Pull a classifier label out of whatever shape an advisory head returned."""
    if isinstance(value, str):
        return value.strip().casefold()
    if isinstance(value, dict):
        for key in ("label", "prediction", "verdict", "value"):
            got = value.get(key)
            if isinstance(got, str) and got.strip():
                return got.strip().casefold()
    return ""


def score_inference(
    receipt: dict[str, Any] | None,
    *,
    prompt: str = "",
    reply: str = "",
    source: str = "",
) -> dict[str, Any]:
    """Confidence-of-inference verdict from the signals a turn actually produced.

    Never raises; on any internal failure returns an ok:False verdict shell."""
    started = time.perf_counter()
    try:
        verdict = _score_inner(receipt if isinstance(receipt, dict) else {},
                               prompt=str(prompt or ""), reply=str(reply or ""),
                               source=str(source or ""))
    except Exception as exc:  # noqa: BLE001 - a verdict must never cost a turn
        verdict = {"schema": SCHEMA, "ok": False, "error": str(exc)[:200],
                   "trust_percent": None, "band": BAND_UNVERIFIED,
                   "abstain_recommended": False, "signals": [],
                   "signals_available": 0, "calibration": CALIBRATION}
    verdict["duration_ms"] = int((time.perf_counter() - started) * 1000)
    return verdict


def _score_inner(receipt: dict[str, Any], *, prompt: str, reply: str, source: str) -> dict[str, Any]:
    # Score the FINAL visible text: the meeting-room rewrite can replace the
    # reply after generation, and the receipt copy is authoritative.
    text = str(receipt.get("assistant_reply") or reply or "")
    signals: list[dict[str, Any]] = []

    def note(name: str, delta: float, detail: str) -> None:
        signals.append({"name": name, "logit_delta": round(delta, 3), "detail": detail})

    # ---- deterministic proof: the ONLY road to "verified" ----------------
    math_lane = receipt.get("math_lane")
    if (source == "ct_math_lane" and isinstance(math_lane, dict)
            and math_lane.get("verified") is True):
        return {
            "schema": SCHEMA, "ok": True,
            "trust_percent": PROOF_TRUST, "band": BAND_VERIFIED,
            "evidence_class": "deterministic_sympy_proof",
            "abstain_recommended": False,
            "signals": [{"name": "math_lane_cas_proof", "logit_delta": 0.0,
                         "detail": "result independently re-verified by the sympy lane "
                                   "before serving (proof short-circuits the logit sum)"}],
            "signals_available": 1,
            "calibration": "deterministic (no statistical calibration involved)",
        }

    refuted = False
    msv = receipt.get("math_serving_verdict")
    if isinstance(msv, dict) and msv.get("checked"):
        if msv.get("refuted"):
            refuted = True
            note("math_cas_refuted", -3.0,
                 "a mathematical claim in the reply is CAS-proven wrong")
        confirmed = int(msv.get("confirmed_count") or 0)
        if confirmed > 0 and not refuted:
            note("math_cas_confirmed", 0.9 * min(confirmed, 2),
                 f"{confirmed} extracted claim(s) independently confirmed by sympy")

    # ---- learned advisory heads (real trained heads, advisory by contract) --
    slm = receipt.get("slm_advisory")
    if isinstance(slm, dict) and slm.get("ready"):
        quality_label = _label_of(slm.get("reply_quality"))
        if quality_label == "clean":
            note("slm_reply_quality_clean", 0.7, "reply-grader head scored the reply clean")
        elif quality_label:
            note("slm_reply_quality_flagged", -0.9,
                 f"reply-grader head scored the reply {quality_label!r}")

    # ---- lane-native confidence / quality gates ---------------------------
    quick = receipt.get("quick_lane_confidence")
    if (isinstance(quick, (int, float)) and not isinstance(quick, bool)
            and math.isfinite(float(quick))):
        note("quick_lane_confidence", (max(0.0, min(1.0, float(quick))) - 0.5) * 2.2,
             f"quick-lane string heuristics scored {float(quick):.2f}")
    semantic = receipt.get("local_semantic_quality")
    if isinstance(semantic, dict):
        if semantic.get("ok") is True:
            note("semantic_quality_ok", 0.6, "big-lane semantic quality checks passed")
        failed = semantic.get("failed_checks")
        if isinstance(failed, (list, tuple)) and failed:
            note("semantic_quality_failed", -0.5 * min(len(failed), 3),
                 f"{len(failed)} semantic quality check(s) failed")
    gate_passed = receipt.get("provider_reply_quality_gate_passed")
    if gate_passed is True:
        note("provider_quality_gate_passed", 0.6, "provider-reply quality gate passed")
    elif gate_passed is False:
        note("provider_quality_gate_failed", -1.0, "provider-reply quality gate failed")
    if receipt.get("quality_gate_degraded") is True:
        note("quality_gate_degraded", -0.7, "reply served in degraded quality mode")

    humanizer = receipt.get("chat_humanizer")
    if isinstance(humanizer, dict) and humanizer.get("reply_was_weak_or_repeated"):
        note("humanizer_weak_or_repeated", -0.8,
             "humanizer judged the raw reply weak or repeated")

    # ---- deterministic marker scans on the final text (stdlib, sub-ms) -----
    try:
        from engel_persona_guard import looks_like_persona_leak

        if text and looks_like_persona_leak(text):
            note("persona_leak_markers", -1.2,
                 "final text still matches persona/frame recitation markers")
    except Exception:  # noqa: BLE001 - marker scan is optional evidence
        pass
    try:
        from engel_governor import looks_like_contract_echo

        if text and looks_like_contract_echo(text):
            note("contract_echo_markers", -1.2,
                 "final text recites training-contract wording")
    except Exception:  # noqa: BLE001
        pass

    if text and len(text.split()) < 3:
        note("degenerate_length", -0.6, "reply is under three words")

    # ---- honest aggregation ------------------------------------------------
    if not signals:
        return {
            "schema": SCHEMA, "ok": True,
            "trust_percent": None, "band": BAND_UNVERIFIED,
            "abstain_recommended": False,
            "signals": [], "signals_available": 0,
            "calibration": CALIBRATION,
            "note": "no verifier produced a signal for this turn; unscored is not wrong",
        }
    logit = sum(d for s in signals
                if math.isfinite(d := float(s.get("logit_delta") or 0.0)))
    trust = 100.0 * _sigmoid(logit)
    # band from the ROUNDED value so a displayed 75.0 is always the same band
    trust = round(max(SOFT_TRUST_FLOOR, min(SOFT_TRUST_CEIL, trust)), 1)
    if refuted:
        trust = min(trust, REFUTED_TRUST_CEIL)
        band = BAND_REFUTED
    elif trust >= 75.0:
        band = BAND_HIGH
    elif trust >= 45.0:
        band = BAND_MEDIUM
    else:
        band = BAND_LOW
    abstain_floor = _env_float("ENGEL_GAIS_ABSTAIN_FLOOR", 20.0)
    return {
        "schema": SCHEMA, "ok": True,
        "trust_percent": trust, "band": band,
        "abstain_recommended": bool(refuted or trust < abstain_floor),
        "signals": signals, "signals_available": len(signals),
        "calibration": CALIBRATION,
    }


# ---------------------------------------------------------------------------
# Consensus agreement metric (used by tools/engel_gais_consensus.py)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9_.]+")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(str(text or "").casefold()))


def _pair_score(a: str, b: str) -> float:
    # Token-level on purpose: character-level difflib gives ANY two English
    # sentences a ~0.15 noise floor (caught by the gate), while token-level
    # scores fully disjoint replies exactly 0.0.
    la = _TOKEN_RE.findall(str(a or "").casefold())
    lb = _TOKEN_RE.findall(str(b or "").casefold())
    if not la or not lb:
        return 0.0
    sa, sb = set(la), set(lb)
    jaccard = len(sa & sb) / len(sa | sb)
    ratio = difflib.SequenceMatcher(None, la, lb).ratio()
    return 0.5 * jaccard + 0.5 * ratio


def consensus_agreement(replies: list[str]) -> dict[str, Any]:
    """Deterministic pairwise agreement over voter replies.

    Measures lexical + numeric CONVERGENCE - agreeing models are evidence, not
    proof, and the receipt says so. Majority pick = the reply most similar to
    all the others (medoid), never a synthesized blend."""
    texts = [str(r or "") for r in (replies or [])]
    n = len(texts)
    if n < 2:
        return {"schema": AGREEMENT_SCHEMA, "ok": False,
                "reason": "agreement needs at least two replies", "voter_count": n}
    matrix: list[list[float]] = [[1.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            score = round(_pair_score(texts[i], texts[j]), 4)
            matrix[i][j] = matrix[j][i] = score
    means = [sum(row[k] for k in range(n) if k != i) / (n - 1) for i, row in enumerate(matrix)]
    pairs = [matrix[i][j] for i in range(n) for j in range(i + 1, n)]
    mean_pairwise = sum(pairs) / len(pairs)
    # numeric convergence: a number shared by every numeric reply is strong evidence
    number_sets = [set(_NUMBER_RE.findall(t)) for t in texts]
    numeric_sets = [s for s in number_sets if s]
    shared_numbers: set[str] = set()
    if len(numeric_sets) >= 2:
        shared_numbers = set.intersection(*numeric_sets)
    return {
        "schema": AGREEMENT_SCHEMA, "ok": True,
        "voter_count": n,
        "pairwise_matrix": matrix,
        "mean_pairwise_agreement": round(mean_pairwise, 4),
        "majority_index": max(range(n), key=lambda i: means[i]),
        "numeric_replies": len(numeric_sets),
        "shared_numbers": sorted(shared_numbers)[:12],
        "numbers_agree": bool(shared_numbers),
        "note": "agreement measures lexical/numeric convergence between voters, not truth",
    }


# ---------------------------------------------------------------------------
# Honest capability report (ModelExpress pattern)
# ---------------------------------------------------------------------------

def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:  # noqa: BLE001
        return False


def _gpu_count() -> int:
    try:
        proc = subprocess.run(["nvidia-smi", "--list-gpus"], capture_output=True,
                              text=True, timeout=6)
        if proc.returncode == 0:
            return len([ln for ln in proc.stdout.splitlines() if ln.strip()])
    except Exception:  # noqa: BLE001
        pass
    return 0


def gais_capabilities() -> dict[str, Any]:
    """Probe THIS host and report each GAIS pillar honestly."""
    tools = Path(__file__).resolve().parent

    def cap(available: bool, reasons: list[str]) -> dict[str, Any]:
        return {"available": bool(available),
                "reasons_unavailable": [] if available else reasons}

    det_components = {
        "persona_guard": _module_available("engel_persona_guard"),
        "governor_markers": _module_available("engel_governor"),
        "math_lane_script": (tools / "engel_math_lane.py").is_file(),
        "sandbox_gate": _module_available("engel_code_forge"),
    }
    det_missing = [k for k, v in det_components.items() if not v]

    models_active = Path("/opt/engel/models-active/llm")
    stoch_local = models_active.is_dir()

    sympy_here = _module_available("sympy")
    conf_components = {
        "receipt_signals": True,  # consumed from the live receipt, always present
        "persona_marker_scan": det_components["persona_guard"],
        "contract_echo_scan": det_components["governor_markers"],
        "cas_refutation_on_host": sympy_here,
    }
    gpus = _gpu_count()
    gpu_lane_url = str(os.environ.get("ENGEL_ROG_GPU_CHAT_URL", "") or
                       "http://127.0.0.1:8899/v1/chat/completions")
    # vantage-aware wording: the same fleet looks different from CT246 (CPU
    # container, GGUF store local, GPU over the reverse tunnel) and from the ROG
    # (CUDA GPU local, GGUF store remote) - the note must describe THIS host.
    if stoch_local:
        stoch_note = ("local GGUF lanes on this host: quick 1.5b / coder-3b / 7B+LoRA / "
                      "14B deep / qwen3-30B MoE; the CUDA big lane is the ROG llama.cpp "
                      "server over the reverse tunnel")
    elif gpus > 0:
        stoch_note = ("this host serves the CUDA llama.cpp big lane locally "
                      f"({gpus} GPU(s)); the CT246 GGUF lanes live on the server")
    else:
        stoch_note = "no local model store and no GPU; stochastic lanes are remote"
    if gpus > 0:
        hw_note = (f"local CUDA GPU(s): {gpus}; no ASIC/FPGA/NNP in this fleet - "
                   "that pillar 4 hardware does not exist here and is not claimed")
    else:
        hw_note = ("CPU-only host; the CUDA lane is reached over the reverse tunnel; "
                   "no ASIC/FPGA/NNP in this fleet - not claimed")
    return {
        "schema": CAPABILITIES_SCHEMA,
        "host_root": str(ROOT),
        "pillar_1_deterministic": {
            **cap(not det_missing, [f"missing component: {m}" for m in det_missing]),
            "components": det_components,
            "note": "logic-gated core = Governor routing + persona/echo guards + "
                    "sympy math lane + Code Forge sandbox gates, all enforced in code",
        },
        "pillar_2_stochastic": {
            **cap(stoch_local or gpus > 0,
                  ["neither /opt/engel/models-active/llm nor a local GPU lane is "
                   "present on this host"]),
            "note": stoch_note,
        },
        "pillar_3_confidence": {
            **cap(True, []),
            "components": {k: cap(v, ["module/import not available on this host"])
                           for k, v in conf_components.items()},
            "calibration": CALIBRATION,
            "note": "abstain_recommended is recommendation-only telemetry on the "
                    "receipt; no lane suppresses a reply because of it yet",
        },
        "pillar_4_hardware": {
            **cap(True, []),
            "local_gpu_count": gpus,
            "gpu_chat_lane_url": gpu_lane_url,
            "note": hw_note,
        },
        "consensus_lane": {
            **cap(True, []),
            "byzantine_fault_tolerant": False,
            "reasons_not_bft": [
                "BFT needs >=4 always-on independent voters; today's voters are the "
                "routed lane and the GPU lane (which can be the SAME llama.cpp process "
                "when the router offloads heavy chat to the GPU), the quick lane, and "
                "(batch-only, ~2 min/prompt, one-shot model reload) Nemotron",
                "cross-model agreement is served as an on-demand review lane "
                "(engel_gais_consensus), not a per-turn vote",
            ],
        },
    }


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------

def selftest() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool) -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if not ok:
            failures.append(name)

    proof = score_inference({"math_lane": {"verified": True}}, source="ct_math_lane")
    check("proof reaches band verified at 99", proof["band"] == BAND_VERIFIED and proof["trust_percent"] == PROOF_TRUST)
    refuted = score_inference({"math_serving_verdict": {"checked": True, "refuted": True}})
    check("CAS refutation forces refuted band + abstain",
          refuted["band"] == BAND_REFUTED and refuted["abstain_recommended"]
          and refuted["trust_percent"] <= REFUTED_TRUST_CEIL)
    empty = score_inference({})
    check("no signals -> trust None, unverified, no abstain",
          empty["trust_percent"] is None and empty["band"] == BAND_UNVERIFIED
          and not empty["abstain_recommended"])
    good = score_inference({
        "slm_advisory": {"ready": True, "reply_quality": {"label": "clean"}},
        "local_semantic_quality": {"ok": True, "failed_checks": []},
        "math_serving_verdict": {"checked": True, "refuted": False, "confirmed_count": 1},
    })
    bad = score_inference({
        "slm_advisory": {"ready": True, "reply_quality": "needed_repair"},
        "quality_gate_degraded": True,
        "chat_humanizer": {"reply_was_weak_or_repeated": True},
    })
    check("clean signals outrank degraded signals",
          isinstance(good["trust_percent"], float) and isinstance(bad["trust_percent"], float)
          and good["trust_percent"] > bad["trust_percent"])
    check("soft signals never reach certainty",
          good["trust_percent"] <= SOFT_TRUST_CEIL and bad["trust_percent"] >= SOFT_TRUST_FLOOR)
    garbage = score_inference({"slm_advisory": 7, "quick_lane_confidence": "x",
                               "math_serving_verdict": [1], "chat_humanizer": None},
                              reply=None)  # type: ignore[arg-type]
    check("garbage receipt never raises", isinstance(garbage, dict) and "band" in garbage)
    agree = consensus_agreement(["the answer is 42 by direct integration",
                                 "42 - integrate directly and you get 42",
                                 "the result equals 42"])
    check("agreeing voters converge with shared number",
          agree["ok"] and agree["numbers_agree"] and agree["mean_pairwise_agreement"] > 0.15)
    disagree = consensus_agreement(["the answer is 42", "quantum broccoli sings on mars"])
    check("disjoint voters score near zero",
          disagree["mean_pairwise_agreement"] < 0.05 and not disagree["numbers_agree"])
    check("single voter is honestly not a consensus", consensus_agreement(["x"])["ok"] is False)
    caps = gais_capabilities()
    check("capabilities carry all four pillars + consensus honesty",
          all(k in caps for k in ("pillar_1_deterministic", "pillar_2_stochastic",
                                  "pillar_3_confidence", "pillar_4_hardware", "consensus_lane"))
          and caps["consensus_lane"]["byzantine_fault_tolerant"] is False
          and caps["consensus_lane"]["reasons_not_bft"])
    loaded_receipt = {
        "slm_advisory": {"ready": True, "reply_quality": {"label": "clean"}},
        "local_semantic_quality": {"ok": True, "failed_checks": []},
        "provider_reply_quality_gate_passed": True,
        "quick_lane_confidence": 0.81,
        "math_serving_verdict": {"checked": True, "refuted": False, "confirmed_count": 1},
        "chat_humanizer": {"reply_was_weak_or_repeated": False},
        "assistant_reply": "The derivative of x**2 is 2*x, so at x=3 the slope is 6. " * 6,
    }
    t0 = time.perf_counter()
    for _ in range(200):
        score_inference(loaded_receipt, reply=loaded_receipt["assistant_reply"])
    check("200 fully-loaded verdicts under 1s", (time.perf_counter() - t0) < 1.0)
    print(f"engel_gais selftest: {11 - len(failures)}/11 passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(selftest())
