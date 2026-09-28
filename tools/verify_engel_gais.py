"""Offline gate for the Engel GAIS layer (confidence of inference + consensus).

Properties proven, each in both directions where a direction exists:
  1. HONESTY OF THE TRUST NUMBER - "verified" is reachable only through a
     deterministic proof; a CAS refutation always forces the refuted band and an
     abstain recommendation; zero signals yields trust None, never an invented
     percentage; soft signals are clamped away from both certainties.
  2. MONOTONICITY - adding positive evidence never lowers trust, adding negative
     evidence never raises it.
  3. NEVER-BLOCKS CONTRACT - garbage receipts of every shape return a verdict
     dict without raising, and the per-verdict cost stays bounded (the scorer
     runs on the interactive path of EVERY chat lane).
  4. CONSENSUS METRIC - convergent voters score high with shared numbers
     surfaced, disjoint voters score near zero, fewer than two voters is
     honestly not a consensus, and the majority pick is the medoid.
  5. LIVE-PATH WIRING - the CT chat service source actually calls the attach
     helper at the finalize chokepoint AFTER the two verdicts it consumes, and
     the canonical memory schema carries the verdict key.
No model, no network.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import engel_gais  # noqa: E402

checks: list[dict[str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


# ---- 1. honesty of the trust number --------------------------------------
proof = engel_gais.score_inference({"math_lane": {"verified": True}}, source="ct_math_lane")
check("proof -> verified band at PROOF_TRUST",
      proof["band"] == "verified" and proof["trust_percent"] == engel_gais.PROOF_TRUST)
not_proof = engel_gais.score_inference({"math_lane": {"verified": True}}, source="ct_main_chat_turn")
check("math_lane block WITHOUT the math-lane source is not a proof",
      not_proof["band"] != "verified")
unverified_lane = engel_gais.score_inference({"math_lane": {"verified": False}}, source="ct_math_lane")
check("unverified math_lane result is not a proof", unverified_lane["band"] != "verified")

stacked = engel_gais.score_inference({
    "slm_advisory": {"ready": True, "reply_quality": {"label": "clean"}},
    "local_semantic_quality": {"ok": True},
    "provider_reply_quality_gate_passed": True,
    "quick_lane_confidence": 0.99,
    "math_serving_verdict": {"checked": True, "refuted": False, "confirmed_count": 2},
})
check("stacked soft evidence still cannot claim verified",
      stacked["band"] == "high" and stacked["trust_percent"] <= engel_gais.SOFT_TRUST_CEIL)

refuted = engel_gais.score_inference({
    "math_serving_verdict": {"checked": True, "refuted": True},
    "slm_advisory": {"ready": True, "reply_quality": {"label": "clean"}},
    "local_semantic_quality": {"ok": True},
})
check("CAS refutation overrides positive soft evidence",
      refuted["band"] == "refuted" and refuted["trust_percent"] <= engel_gais.REFUTED_TRUST_CEIL)
check("refutation recommends abstaining", refuted["abstain_recommended"] is True)

empty = engel_gais.score_inference({})
check("zero signals -> trust None + unverified band",
      empty["trust_percent"] is None and empty["band"] == "unverified")
check("zero signals does NOT recommend abstaining (unscored is not wrong)",
      empty["abstain_recommended"] is False)
check("verdict declares its calibration honestly",
      empty["calibration"] == engel_gais.CALIBRATION and stacked["calibration"] == engel_gais.CALIBRATION)

# ---- 2. monotonicity -------------------------------------------------------
base_receipt = {"slm_advisory": {"ready": True, "reply_quality": {"label": "clean"}}}
base = engel_gais.score_inference(base_receipt)
more_positive = engel_gais.score_inference({**base_receipt, "local_semantic_quality": {"ok": True}})
check("adding positive evidence never lowers trust",
      more_positive["trust_percent"] >= base["trust_percent"])
more_negative = engel_gais.score_inference({**base_receipt, "quality_gate_degraded": True})
check("adding negative evidence never raises trust",
      more_negative["trust_percent"] <= base["trust_percent"])
low_only = engel_gais.score_inference({
    "slm_advisory": {"ready": True, "reply_quality": "needed_repair"},
    "quality_gate_degraded": True,
    "provider_reply_quality_gate_passed": False,
    "chat_humanizer": {"reply_was_weak_or_repeated": True},
})
check("heavy negative evidence lands in low band + abstain",
      low_only["band"] == "low" and low_only["abstain_recommended"] is True,
      f"trust={low_only['trust_percent']}")
check("soft floor holds under maximal negativity",
      low_only["trust_percent"] >= engel_gais.SOFT_TRUST_FLOOR)

# ---- 3. never-blocks contract ----------------------------------------------
garbage_shapes = [
    None,
    {"slm_advisory": 7, "quick_lane_confidence": "x", "math_serving_verdict": [1]},
    {"math_lane": "yes", "local_semantic_quality": ["a"], "chat_humanizer": 0},
    {"quick_lane_confidence": float("nan")},
]
garbage_ok = True
for shape in garbage_shapes:
    verdict = engel_gais.score_inference(shape)  # type: ignore[arg-type]
    if not (isinstance(verdict, dict) and "band" in verdict and "duration_ms" in verdict):
        garbage_ok = False
    trust = verdict.get("trust_percent")
    if trust is not None and not (isinstance(trust, float) and trust == trust):
        garbage_ok = False  # NaN or wrong type would poison receipts/JSON
check("every garbage receipt shape returns a finite (or None) verdict without raising", garbage_ok)

# time the scorer on a RECEIPT shape carrying every signal it consumes (an
# earlier draft timed a verdict dict here, which exercises almost nothing)
loaded_receipt = {
    "slm_advisory": {"ready": True, "reply_quality": {"label": "clean"}},
    "local_semantic_quality": {"ok": True, "failed_checks": ["one"]},
    "provider_reply_quality_gate_passed": True,
    "quick_lane_confidence": 0.81,
    "math_serving_verdict": {"checked": True, "refuted": False, "confirmed_count": 2},
    "chat_humanizer": {"reply_was_weak_or_repeated": True},
    "quality_gate_degraded": True,
    "assistant_reply": "The derivative of x**2 is 2*x, so at x=3 the slope is 6. " * 8,
}
probe = engel_gais.score_inference(loaded_receipt, reply=loaded_receipt["assistant_reply"])
check("loaded receipt actually exercises the signal set",
      probe["signals_available"] >= 7, f"signals={probe['signals_available']}")
t0 = time.perf_counter()
for _ in range(500):
    engel_gais.score_inference(loaded_receipt, reply=loaded_receipt["assistant_reply"])
elapsed = time.perf_counter() - t0
check("500 fully-loaded verdicts under 2.5s (hot-path bound)", elapsed < 2.5, f"{elapsed:.2f}s")

# ---- 4. consensus metric ----------------------------------------------------
agree = engel_gais.consensus_agreement([
    "the integral evaluates to 42 after substitution",
    "after substituting you get exactly 42",
    "result: 42",
])
check("convergent voters agree with the shared number surfaced",
      agree["ok"] and agree["numbers_agree"] and "42" in agree["shared_numbers"]
      and agree["mean_pairwise_agreement"] > 0.15)
disjoint = engel_gais.consensus_agreement(["alpha bravo charlie", "delta echo foxtrot golf"])
check("disjoint voters score exactly-zero-ish (token-level metric)",
      disjoint["mean_pairwise_agreement"] < 0.05 and not disjoint["numbers_agree"])
check("one voter is honestly not a consensus",
      engel_gais.consensus_agreement(["only me"])["ok"] is False)
check("zero voters is honestly not a consensus",
      engel_gais.consensus_agreement([])["ok"] is False)
medoid = engel_gais.consensus_agreement([
    "the answer is 7 by direct count",
    "the answer is 7, counted directly",
    "purple elephants dance at midnight",
])
check("majority pick is the medoid, not the outlier", medoid["majority_index"] in (0, 1))
conflicting = engel_gais.consensus_agreement(["the answer is 7", "the answer is 9"])
check("conflicting numbers do not fake numeric agreement",
      conflicting["numbers_agree"] is False)

# ---- 5. live-path wiring -----------------------------------------------------
service_src = (ROOT / "tools" / "engel_main_server_chat_http_service.py").read_text(
    encoding="utf-8", errors="replace")
check("service defines _attach_gais_confidence with the kill switch",
      "def _attach_gais_confidence(" in service_src
      and 'ENGEL_GAIS_CONFIDENCE_ENABLED", default=True' in service_src)
slm_call = service_src.find("_attach_slm_advisory(receipt, prompt, reply)")
math_call = service_src.find("_attach_math_verdict(receipt, reply, source)", slm_call)
gais_call = service_src.find("_attach_gais_confidence(receipt, prompt, reply, source)", slm_call)
check("chokepoint calls gais AFTER the two verdicts it consumes",
      -1 < slm_call < math_call < gais_call)
check("canonical memory schema carries inference_confidence",
      '"inference_confidence": receipt.get("inference_confidence")' in service_src)
consensus_src = (ROOT / "tools" / "engel_gais_consensus.py").read_text(
    encoding="utf-8", errors="replace")
check("consensus receipt is honest about not being BFT",
      '"byzantine_fault_tolerant": False' in consensus_src
      and "not a per-turn vote" in consensus_src)
check("numeric conflict vetoes consensus_reached in the CLI",
      "numeric_conflict = bool(" in consensus_src
      and "not numeric_conflict" in consensus_src)
check("consensus receipt admits routed/gpu can be one process",
      "self-correlation" in consensus_src)
caps = engel_gais.gais_capabilities()
check("capabilities report all four pillars with availability + reasons",
      all(isinstance(caps.get(k), dict) and "available" in caps[k]
          for k in ("pillar_1_deterministic", "pillar_2_stochastic",
                    "pillar_3_confidence", "pillar_4_hardware")))
check("consensus capability declares why it is not BFT",
      caps["consensus_lane"]["byzantine_fault_tolerant"] is False
      and len(caps["consensus_lane"]["reasons_not_bft"]) >= 2)

failed = [c for c in checks if c["status"] != "PASS"]
print(json.dumps({
    "schema": "engel_gais_verifier_v1",
    "status": "FAIL" if failed else "PASS",
    "passed": len(checks) - len(failed),
    "total": len(checks),
    "failed": [c["name"] for c in failed],
    "checks": checks,
}, indent=2))
raise SystemExit(1 if failed else 0)
