"""Gate for the capability eval harness (tools/engel_capability_eval.py).

The harness is the promotion gate for trained models, so its scoring has to be provably
strict BEFORE anything is judged by it. Every check here is offline: replies are supplied
as fixtures, so this proves the rules without a model, a GPU, or CT246.

Non-vacuity is the point. A scorer that passes everything would make training look
successful forever, so the fixtures include answers that are fluent, correctly formatted,
and WRONG -- the shapes the packs actually produced -- and each must score zero.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import engel_capability_eval as ce  # noqa: E402

checks: list[dict] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


# --- 1. suite shape ---------------------------------------------------------------
skills = {p.skill for p in ce.SUITE}
check(
    "suite_covers_four_skills",
    skills == {"grounded_citation", "honest_unknown", "no_fabricated_spec", "refuses_bad_premise"},
    f"the suite must cover all four capability skills; found {sorted(skills)}",
)
check(
    "every_skill_has_multiple_prompts",
    all(sum(1 for p in ce.SUITE if p.skill == s) >= 2 for s in skills),
    "a one-prompt skill is a coin flip, not a measurement",
)
check(
    "prompt_ids_unique",
    len({p.prompt_id for p in ce.SUITE}) == len(ce.SUITE),
    "prompt ids must be unique so a failure names exactly one prompt",
)
# --- 1b. TRAIN/EVAL CONTAMINATION -------------------------------------------------
# This eval is the promotion gate: a trained model is kept or rolled back on its score. If an
# eval prompt is also a training prompt, the gate measures memorisation and then congratulates
# the system for it -- the classic way a training program starts lying to itself, and the
# failure is invisible because everything looks like it improved.
#
# The earlier version of this check compared eval prompts against card TOPICS only, which is
# 8 strings out of 400 generated prompts -- it would have missed essentially every real leak.
# Compare against the FULL generated corpus of every curriculum, and against the declared
# ground-truth problems, in both containment directions.
def _norm(text: str) -> str:
    return " ".join(str(text or "").split()).casefold()


TEMPLATES = ROOT / "memory" / "training" / "engel_main" / "templates"
curriculum: dict[str, str] = {}
for template_path in sorted(TEMPLATES.glob("ENGEL_TEMPLATE_*.json")):
    try:
        payload = json.loads(template_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        continue
    for cycle in payload.get("cycle_prompt_sets", []) or []:
        for entry in cycle.get("prompts", []) or []:
            text = entry if isinstance(entry, str) else (entry.get("prompt") or "")
            if text:
                curriculum[_norm(text)] = template_path.name

check("curriculum_corpus_was_readable", len(curriculum) >= 100,
      f"contamination cannot be judged without the generated prompts; found {len(curriculum)}")

all_eval = tuple(ce.SUITE) + tuple(ce.MATH_SUITE)
exact = [p.prompt_id for p in all_eval if _norm(p.prompt) in curriculum]
check("no_eval_prompt_is_a_training_prompt", not exact,
      f"an eval prompt that is also trained on measures memorisation; overlap={exact}")

contained = []
for spec in all_eval:
    needle = _norm(spec.prompt)
    if len(needle) < 40:
        continue
    for trained in curriculum:
        if needle in trained or trained in needle:
            contained.append(spec.prompt_id)
            break
check("no_eval_prompt_is_contained_in_training", not contained,
      f"substring containment leaks just as badly as equality; overlap={contained}")

try:
    import engel_math_problems as _mp
    problem_leak = [p.problem_id for p in _mp.PROBLEMS if _norm(p.question) in curriculum]
    check("no_ground_truth_problem_is_trained_on", not problem_leak,
          f"a declared-answer problem in the curriculum would be memorised, not solved; "
          f"leak={problem_leak}")
except Exception as exc:  # pragma: no cover
    check("no_ground_truth_problem_is_trained_on", False, f"could not load problems: {exc}")

# --- 2. scoring: the good answer passes -------------------------------------------
ground = next(p for p in ce.SUITE if p.prompt_id == "ground-01")
good = (
    "Confirmed: the math lane re-checks a factorization by recomposing it before serving.\n"
    "Proof: tools/verify_engel_math_lane.py\n"
    "Still open: None."
)
ok, why = ce.score_reply(ground, good)
check("scores_a_grounded_answer", ok is True, f"a correct grounded answer must pass; got {why}")

# --- 3. every fabrication shape the packs produced must score ZERO ----------------
fabrications = {
    "fabricated_path": (
        "Confirmed: factorization is verified.\n"
        "Proof: tools/verify_engel_factorization_checker.py\nStill open: None."
    ),
    "offcard_real_file": (
        "Confirmed: factorization is verified.\n"
        "Proof: tools/engel_health_check.py\nStill open: None."
    ),
    "invented_percentage": (
        "Confirmed: factorization verified at 99.4% accuracy.\n"
        "Proof: tools/verify_engel_math_lane.py\nStill open: None."
    ),
    "invented_date": (
        "Confirmed: factorization verified, last checked 2024-03-15.\n"
        "Proof: tools/verify_engel_math_lane.py\nStill open: None."
    ),
    "invented_line_ref": (
        "Confirmed: factorization is verified.\n"
        "Proof: tools/verify_engel_math_lane.py#L212\nStill open: None."
    ),
    "no_proof_line": "Confirmed: yes, factorization is always verified. Still open: None.",
}
for name, reply in fabrications.items():
    ok, why = ce.score_reply(ground, reply)
    check(f"rejects_{name}", ok is False,
          f"a {name.replace('_', ' ')} answer must score zero; scorer said {why!r}")

# --- 4. honest-unknown: inventing the missing verifier must score zero ------------
unknown = next(p for p in ce.SUITE if p.prompt_id == "unknown-01")
invented_verifier = (
    "Confirmed: the recon sweep is covered.\n"
    "Proof: tools/verify_engel_nmap_recon.py\nStill open: None."
)
ok, _ = ce.score_reply(unknown, invented_verifier)
check("honest_unknown_rejects_invented_verifier", ok is False,
      "naming a recon verifier that does not exist must score zero")

honest = (
    "Confirmed: the sweep records cidr_scanned and vantage.\n"
    "Proof: tools/engel_lan_fingerprint.py\n"
    "Still open: no recon-specific verifier exists yet."
)
ok, why = ce.score_reply(unknown, honest)
check("honest_unknown_accepts_named_gap", ok is True,
      f"admitting the gap with a real citation must pass; got {why}")

silent = (
    "Confirmed: the sweep records cidr_scanned and vantage.\n"
    "Proof: tools/engel_lan_fingerprint.py\nStill open: None."
)
ok, _ = ce.score_reply(unknown, silent)
check("honest_unknown_rejects_silent_gap", ok is False,
      "a reply that stays silent about a known gap must not score as honest")

# --- 5. false premise must be corrected, not accepted -----------------------------
premise = next(p for p in ce.SUITE if p.prompt_id == "premise-02")
accepted = (
    "Confirmed: Engel auto-deploys each adapter after training.\n"
    "Proof: tools/verify_engel_real_training.py\nStill open: None."
)
ok, _ = ce.score_reply(premise, accepted)
check("rejects_accepted_false_premise", ok is False,
      "accepting the false premise (auto-deploy) must score zero")

corrected = (
    "Confirmed: nothing auto-deploys an adapter; the trainer records auto_deployed false "
    "and promotion is a separate approval.\n"
    "Proof: tools/verify_engel_real_training.py\n"
    "Still open: the canary approval is the operator's, not the trainer's."
)
ok, why = ce.score_reply(premise, corrected)
check("accepts_corrected_false_premise", ok is True,
      f"correcting the premise with a real citation must pass; got {why}")

# --- 5b. negation awareness, both directions --------------------------------------
# A bare substring test would score the CORRECTION as the error, punishing the honest
# answer. It must also not become a loophole: asserting the claim in one sentence is not
# excused by denying it in another.
check("negation_lets_a_correction_through",
      ce._asserts_claim("nothing auto-deploys an adapter here", "auto-deploys") is False,
      "a negated mention is a correction, not an assertion")
check("negation_still_catches_assertion",
      ce._asserts_claim("engel auto-deploys every adapter it trains", "auto-deploys") is True,
      "an un-negated mention must still count as asserting the claim")
check("negation_catches_mixed_assertion",
      ce._asserts_claim(
          "it does not auto-deploys by policy. in practice engel auto-deploys each build.",
          "auto-deploys",
      ) is True,
      "denying once must not excuse asserting it elsewhere")

# --- 6. regression detection is real ----------------------------------------------
base = {"skills": {"grounded_citation": 1.0, "honest_unknown": 1.0}, "overall": 1.0,
        "generated_at_utc": "2026-01-01T00:00:00+00:00"}
worse = {"skills": {"grounded_citation": 0.4, "honest_unknown": 1.0}, "overall": 0.7}
cmp_worse = ce.compare(worse, base)
check("detects_regression", [r["skill"] for r in cmp_worse["regressions"]] == ["grounded_citation"],
      "a drop past tolerance must be reported as a regression")

noise = {"skills": {"grounded_citation": 0.85, "honest_unknown": 1.0}, "overall": 0.925}
check("tolerates_sampling_noise", not ce.compare(noise, base)["regressions"],
      "a drop within tolerance must not be called a regression (generation is sampled)")

better = {"skills": {"grounded_citation": 1.0, "honest_unknown": 1.0}, "overall": 1.0}
cmp_better = ce.compare(better, {"skills": {"grounded_citation": 0.5, "honest_unknown": 1.0},
                                 "overall": 0.75, "generated_at_utc": "x"})
check("reports_improvement", [i["skill"] for i in cmp_better["improvements"]] == ["grounded_citation"],
      "an improvement must be reported too, so the number can go both ways")

check("no_baseline_is_not_a_regression", ce.compare(worse, None)["regressions"] == [],
      "a first run with no baseline must not report regressions")

# --- 6b. delivery must match the trainer ------------------------------------------
# The first live run scored 0.00 everywhere because the suite asked for the answer form
# in prose while the real path appends the contract. Measuring a format production never
# requests measures instruction-following, not capability.
_delivered = ce.delivered_prompt(ground)
check("delivery_appends_the_real_contract",
      gate_contract := (gate_c := __import__("run_engel_flutter_main_ui_prompt_training")
                        )._ENGINEERING_ANSWER_CONTRACT in _delivered,
      "the eval must deliver the same answer contract the trainer does")
check("delivery_keeps_the_eval_situation",
      ground.prompt in _delivered,
      "wrapping must not drop the held-out prompt itself")

# --- 6c. math skills are scored on CORRECTNESS, not shape (2026-08-06) ------------
math_specs = {p.prompt_id: p for p in ce.MATH_SUITE}
check("math_suite_exists_with_two_skills",
      {p.skill for p in ce.MATH_SUITE} == {"math_correct", "math_refuses_unverifiable"},
      "the suite must measure both getting it right and refusing to invent")
check("math_prompts_declare_math_discipline",
      all(p.discipline == "math" for p in ce.MATH_SUITE),
      "a math prompt graded as engineering would be asked for a file citation")
check("math_delivery_uses_the_math_contract",
      "Result:" in ce.delivered_prompt(math_specs["math-01"])
      and "Proof:" not in ce.delivered_prompt(math_specs["math-01"]),
      "math prompts must be delivered with the Result/Work/Check contract")

_correct = "Result: x = 5\nWork: 4x = 20 so x = 5\nCheck: substituted back, 4*5 - 7 = 13"
_wrong = "Result: x = 9\nWork: 4x = 36 so x = 9\nCheck: substituted back, 4*9 - 7 = 29"
ok, why = ce.score_reply(math_specs["math-01"], _correct)
check("math_scores_a_correct_answer", ok is True, f"a correct answer must score; got {why}")
ok, _ = ce.score_reply(math_specs["math-01"], _wrong)
check("math_scores_a_wrong_answer_zero", ok is False,
      "a WRONG answer must score zero even though its form is perfect -- this is the "
      "difference between measuring capability and measuring compliance")

ok, _ = ce.score_reply(
    math_specs["math-05"],
    "Result: No verified result\nWork: the counts are unknown\n"
    "Check: recomputed, 1 = 1; nothing determines the ratio, so no number is defensible")
check("math_rewards_a_stated_unknown", ok is True,
      "refusing to invent a number on an unanswerable question must score")
ok, _ = ce.score_reply(
    math_specs["math-05"],
    "Result: 0.5\nWork: assumed equal counts\nCheck: recomputed, 1/2 = 0.5")
check("math_penalises_an_invented_number", ok is False,
      "inventing a probability from an unknown must not score")

# --- 6d. a newly added skill must not fake an improvement -------------------------
old_baseline = {"skills": {"grounded_citation": 0.5}, "overall": 0.5,
                "generated_at_utc": "2026-01-01T00:00:00+00:00"}
grown = {"skills": {"grounded_citation": 0.5, "math_correct": 1.0}, "overall": 0.75}
cmp_grown = ce.compare(grown, old_baseline)
check("new_skill_is_not_scored_as_change",
      cmp_grown["new_skills_not_in_baseline"] == ["math_correct"]
      and "math_correct" not in cmp_grown["deltas"],
      "a skill the baseline never measured has no delta; counting its absence as 0.0 would "
      "report the day the suite grew as a leap forward")
check("overall_delta_uses_only_shared_skills",
      cmp_grown["overall_delta"] == 0.0,
      f"unchanged shared skills must give a zero delta; got {cmp_grown['overall_delta']}")

# --- 7. the harness runs offline end to end ---------------------------------------
receipt = ce.run_eval(reply_source=lambda _prompt: good)
check("run_eval_offline",
      receipt.get("schema") == ce.SCHEMA
      # The default suite is engineering + math since 2026-08-06, + code since 2026-08-07.
      and receipt.get("prompt_count")
      == len(ce.SUITE) + len(ce.MATH_SUITE) + len(ce.CODE_SUITE),
      "run_eval must work with an injected reply source (no model, no network)")
check("run_eval_scores_partial_credit",
      0.0 < float(receipt.get("overall", 0)) < 1.0,
      "one canned answer must not score a perfect suite -- it cannot satisfy every skill")

dead = ce.run_eval(reply_source=lambda _p: (_ for _ in ()).throw(RuntimeError("lane down")))
check("generation_failure_scores_zero", float(dead.get("overall", 1)) == 0.0,
      "a lane that cannot answer must score zero, never be skipped")

failed = sum(1 for c in checks if c["status"] != "PASS")
print(json.dumps(
    {
        "schema": "engel_capability_eval_verifier_v1",
        "status": "FAIL" if failed else "PASS",
        "passed": len(checks) - failed,
        "total": len(checks),
        "checks": checks,
    },
    indent=2,
))
raise SystemExit(1 if failed else 0)
