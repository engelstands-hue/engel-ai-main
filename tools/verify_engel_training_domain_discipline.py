#!/usr/bin/env python3
"""Verify the domain-native training discipline fix (2026-07-31).

Gates, as durable regression checks:
  1. Discipline flows end to end: every curriculum template declares the discipline its
     registry entry sets, and the MIXED/default template carries the active discipline.
  2. The CT246 incomplete-input gate still fires on construction (aec) delivered prompts
     and is largely cleared for math/engineering delivered prompts (the domain-native
     shapes are worded to avoid the trigger). A small residual is allowed for content-heavy
     cards and is handled by run resilience, so a ceiling -- not zero -- is asserted.
  3. Training-sample eligibility helpers accept a genuine domain answer and reject a
     contract echo, an unverified math answer, and an ungrounded engineering answer.
  4. Delivery-failure classification: a delivered-but-quality-blocked turn is NOT a
     delivery failure; a turn that never reached the chat lane is.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for p in (ROOT, TOOLS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import engel_main_server_chat_http_service as svc  # noqa: E402
import run_engel_flutter_main_ui_prompt_training as runner  # noqa: E402
import sync_engel_training_assets as sync  # noqa: E402

TPL_DIR = ROOT / "memory" / "training" / "engel_main" / "templates"
LEVELS = ("low", "medium", "high", "expert")
MATH_TRIP_CEIL = 0.10       # allow up to 10% residual on content-heavy math cards
ENG_TRIP_CEIL = 0.15        # engineering cards are heavier on evidence/unknown language
# Communication training must never inherit the construction-specific RFI/geometry
# guidance. Its uncertainty lessons are phrased in ordinary chat terms so this global
# lexical gate remains fully clear at every supported depth.
COMM_TRIP_CEIL = 0.0
COMM_EXPECTED_TRIPS_BY_TOPIC: dict[str, int] = {}

checks: list[dict] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


def base_prompts(template: dict) -> list[str]:
    out: list[str] = []
    for grp in template.get("cycle_prompt_sets", []) or []:
        if isinstance(grp, dict):
            out.extend(p for p in grp.get("prompts", []) if isinstance(p, str))
    return out


def trip_rate(template: dict, discipline: str) -> tuple[int, int]:
    prompts = base_prompts(template)
    total = trips = 0
    for base in prompts:
        for level in LEVELS:
            delivered = runner._leveled_training_prompt(base, level, discipline)
            total += 1
            if svc._prompt_has_incomplete_project_inputs(delivered):
                trips += 1
    return trips, total


# 1. discipline threading -----------------------------------------------------
registry = {c["id"]: c["discipline"] for c in sync.ALL_CURRICULA}
for entry in sync.ALL_CURRICULA:
    path = TPL_DIR / f"ENGEL_TEMPLATE_{entry['id'].upper()}.json"
    if not path.exists():
        check(f"template_present_{entry['id']}", False, f"missing {path}")
        continue
    tpl = json.loads(path.read_text(encoding="utf-8").lstrip("﻿"))
    got = tpl.get("training_discipline")
    check(
        f"template_discipline_{entry['id']}",
        got == entry["discipline"],
        f"template declares '{got}', registry says '{entry['discipline']}'",
    )
mixed = json.loads((TPL_DIR / "ENGEL_HOUR_PROMPT_TRAINING_MIXED.json").read_text(encoding="utf-8").lstrip("﻿"))
check(
    "mixed_uses_active_discipline",
    mixed.get("training_discipline") == sync.ACTIVE_DISCIPLINE,
    f"MIXED discipline '{mixed.get('training_discipline')}' vs active '{sync.ACTIVE_DISCIPLINE}'",
)

# 2. gate firing --------------------------------------------------------------
constr = json.loads((TPL_DIR / "ENGEL_TEMPLATE_CONSTRUCTION.json").read_text(encoding="utf-8").lstrip("﻿"))
ct_trips, ct_total = trip_rate(constr, "aec")
check(
    "construction_still_gated",
    ct_trips == ct_total and ct_total > 0,
    f"construction delivered prompts trip {ct_trips}/{ct_total} (must be all)",
)
# Construction renewal is now operationally quote-bound: the runner appends verified local
# excerpts, and every sourced-fact line must name one exact manifest document and Section.
# Keep that contract visible here as well as in the dedicated corpus verifier so a future
# discipline refactor cannot silently fall back to whole-answer or fuzzy document scope.
construction_contract = runner._training_answer_contract("aec")
construction_exact_contract = True
for cycle in constr.get("cycle_prompt_sets", []) or []:
    card = cycle.get("material_card") if isinstance(cycle, dict) else None
    documents = card.get("documents") if isinstance(card, dict) else None
    anchors = card.get("evidence_anchors") if isinstance(card, dict) else None
    prompts = cycle.get("prompts") if isinstance(cycle, dict) else None
    construction_exact_contract = construction_exact_contract and (
        isinstance(documents, list)
        and bool(documents)
        and len(documents) == len(set(documents))
        and all(isinstance(document, str) and document.endswith(".pdf") for document in documents)
        and isinstance(anchors, list)
        and bool(anchors)
        and all(
            isinstance(anchor, dict)
            and anchor.get("document") in documents
            and bool(str(anchor.get("section") or "").strip())
            for anchor in anchors
        )
        and isinstance(prompts, list)
        and bool(prompts)
        and all(
            "verified local evidence packet" in prompt
            and "exact manifest filenames" in prompt
            and "one source document and one Section" in prompt
            for prompt in prompts
        )
    )
construction_exact_contract = construction_exact_contract and all(
    marker in construction_contract
    for marker in (
        'Source document: "<exact manifest filename>"',
        "Section <id>",
        # (2026-08-14) the sourced-fact line became EXCERPT-ONLY: the free-text
        # <claim> slot made models fail the 100%-term-overlap gate by construction,
        # so the contract now demands the packet excerpt verbatim and nothing else.
        'Source excerpt: "<the packet excerpt copied character-for-character>"',
        "your own words go under Open items",
    )
)
check(
    "construction_uses_exact_document_and_evidence_contract",
    construction_exact_contract,
    "all eight cards bind exact documents/sections and all prompts announce evidence injection",
)
for cid, ceil in (
    ("math_school", MATH_TRIP_CEIL),
    ("capabilities", ENG_TRIP_CEIL),
    ("self_build", ENG_TRIP_CEIL),
    ("chat_communication", COMM_TRIP_CEIL),
):
    tpl = json.loads((TPL_DIR / f"ENGEL_TEMPLATE_{cid.upper()}.json").read_text(encoding="utf-8").lstrip("﻿"))
    disc = registry[cid]
    tr, tot = trip_rate(tpl, disc)
    rate = tr / tot if tot else 1.0
    check(
        f"{cid}_mostly_ungated",
        rate <= ceil,
        f"{cid} ({disc}) delivered prompts trip {tr}/{tot} = {rate:.1%} (ceiling {ceil:.0%})",
    )

communication = json.loads(
    (TPL_DIR / "ENGEL_TEMPLATE_CHAT_COMMUNICATION.json")
    .read_text(encoding="utf-8")
    .lstrip("ï»¿")
)
communication_trips_by_topic: dict[str, int] = {}
communication_tripped_bases: dict[str, set[str]] = {}
communication_total = 0
for cycle in communication.get("cycle_prompt_sets", []) or []:
    topic = str(cycle.get("material_topic") or "") if isinstance(cycle, dict) else ""
    for base in cycle.get("prompts", []) if isinstance(cycle, dict) else []:
        if not isinstance(base, str):
            continue
        tripped_levels: set[str] = set()
        for level in LEVELS:
            delivered = runner._leveled_training_prompt(base, level, "communication")
            communication_total += 1
            if svc._prompt_has_incomplete_project_inputs(delivered):
                tripped_levels.add(level)
                communication_trips_by_topic[topic] = (
                    communication_trips_by_topic.get(topic, 0) + 1
                )
        if tripped_levels:
            communication_tripped_bases[base] = tripped_levels
communication_trips = sum(communication_trips_by_topic.values())
check(
    "chat_communication_exactly_ungated",
    communication_total == 320
    and communication_trips_by_topic == COMM_EXPECTED_TRIPS_BY_TOPIC
    and len(communication_tripped_bases) == 0
    and all(levels == set(LEVELS) for levels in communication_tripped_bases.values()),
    "chat_communication must never receive construction-specific incomplete-input "
    f"guidance; trips={communication_trips}/{communication_total}; profile="
    f"{communication_trips_by_topic}",
)

# 2b. intent-gate hijack sweep (2026-08-04) ------------------------------------
# No verifier covered the generated curricula against the two intent gates, and the
# risk is not theoretical: a governing verb within ~24 characters of "training" turns
# a training turn into a training-JOB receipt, and run|start|do within ~16 characters
# can LAUNCH a real run from a chat prompt (both fixed once already -- see the intent
# gates in engel_main_server_chat_http_service.py). Card 7's topic legitimately reads
# "delivering training prompts", and every capabilities prompt now carries an appended
# citation line, so the corpus must be re-swept whenever card text changes.
for entry in sync.ALL_CURRICULA:
    path = TPL_DIR / f"ENGEL_TEMPLATE_{entry['id'].upper()}.json"
    if not path.exists():
        continue
    tpl = json.loads(path.read_text(encoding="utf-8").lstrip("﻿"))
    disc = registry[entry["id"]]
    job = start = total = 0
    for base in base_prompts(tpl):
        for level in LEVELS:
            delivered = runner._leveled_training_prompt(base, level, disc)
            total += 1
            if svc._prompt_requests_training_job(delivered):
                job += 1
            if svc._prompt_starts_local_training(delivered):
                start += 1
    check(
        f"{entry['id']}_no_intent_hijack",
        job == 0 and start == 0 and total > 0,
        f"{entry['id']} delivered prompts: {job} training-job hit(s), {start} start-training "
        f"hit(s) across {total} variants (both must be 0)",
    )

# 2b-ii. dispatch lanes must not eat training turns (2026-08-04) ---------------
# The fleet-dispatch lane runs AFTER the non_interactive_turn clamp but does not
# consult it, and verify_engel_non_interactive_action_gate.py deliberately lists
# _run_fleet_dispatch in _SILENCED_LANES -- so nothing covered the one lane that can
# bypass the clamp. It bit for real: a card naming a worker plus the engineering
# answer contract's own phrase "file, or route" turned a training prompt into a work
# order to a phone (canned 41-char reply, no model answer, no CT receipt). Assert both
# directions so the anchor cannot be loosened back and dispatch cannot be broken.
import engel_main_local_model_worker as worker  # noqa: E402

_dispatch_fp: list[str] = []
for entry in sync.ALL_CURRICULA:
    path = TPL_DIR / f"ENGEL_TEMPLATE_{entry['id'].upper()}.json"
    if not path.exists():
        continue
    tpl = json.loads(path.read_text(encoding="utf-8").lstrip("﻿"))
    disc = registry[entry["id"]]
    for base in base_prompts(tpl):
        for level in LEVELS:
            delivered = runner._leveled_training_prompt(base, level, disc)
            if worker._requested_fleet_dispatch(delivered) is not None:
                _dispatch_fp.append(f"{entry['id']}: {delivered[:70]}")
check(
    "training_prompts_never_dispatch_to_devices",
    not _dispatch_fp,
    f"{len(_dispatch_fp)} delivered training prompt(s) route to fleet dispatch instead of "
    f"being answered (must be 0): {_dispatch_fp[:2]}",
)
_real_orders = (
    "have alpha run the lan scan",
    "please ask beta to check in",
    "alpha: run the fingerprint sweep",
    "have the sub-engel check in",
)
_lost = [o for o in _real_orders if worker._requested_fleet_dispatch(o) is None]
check(
    "real_device_orders_still_dispatch",
    not _lost,
    f"genuine operator orders must still reach the fleet lane; lost: {_lost}",
)

# 2c. the citation supply the engineering gate grades against (2026-08-04) ------
# Every artifact a card advertises must EXIST, or the card teaches the fabrication the
# gate exists to refuse -- and a card whose prompts supply nothing citable cannot pass
# its own material (the recon card was in exactly that state: it offered only a .json
# while the gate scans for .py).
for card in sync.ENGEL_CAPABILITIES_CARDS_V1:
    arts = list(card.get("artifacts") or [])
    missing = [a for a in arts if not runner._artifact_exists(a)]
    check(
        f"capabilities_card_artifacts_exist_{arts[0].split('/')[-1] if arts else 'none'}",
        bool(arts) and not missing,
        f"card '{card['topic'][:40]}...' advertises {len(arts)} artifact(s); missing: {missing}",
    )
caps_tpl = json.loads((TPL_DIR / "ENGEL_TEMPLATE_CAPABILITIES.json").read_text(encoding="utf-8").lstrip("﻿"))
caps_prompts = base_prompts(caps_tpl)
supplied = [p for p in caps_prompts if any(runner._artifact_exists(t) for t in runner._cited_py_tokens(p))]
check(
    "capabilities_every_prompt_supplies_a_citable_file",
    len(supplied) == len(caps_prompts) and caps_prompts,
    f"{len(supplied)}/{len(caps_prompts)} capabilities prompts name an existing .py "
    "(a prompt graded on citing a real file must first show the model one)",
)

# 3. eligibility helpers ------------------------------------------------------
real_math = (
    "Result: x = 2 and x = 3\nWork: Factor x^2-5x+6=(x-2)(x-3).\n"
    "Check: substitute x=2: 4-10+6 = 0; x=3: 9-15+6 = 0. Both verify."
)
echo_math = (
    "Engel AI Main answers as verified math in exactly this structure: 1. Result: the answer "
    "(or 'No verified result' if you could not check it). 2. Work: the key steps. 3. Check: an "
    "INDEPENDENT verification."
)
unverified_math = "Result: x = 5. Work: I think it factors that way. It looks right."
false_cas_math = (
    "Result: x = 4\nWork: quick mental math.\nCheck: substitute back, 2*4 = 9 confirms it."
)
check("math_accepts_real", runner._math_answer_shows_verification(real_math) is True,
      "a real Result/Work/Check answer must be eligible")
check("math_rejects_echo", runner._math_answer_shows_verification(echo_math) is False,
      "a contract echo must be rejected")
check("math_rejects_unverified", runner._math_answer_shows_verification(unverified_math) is False,
      "an answer with no independent Check must be rejected")
check("math_rejects_false_cas", runner._math_answer_shows_verification(false_cas_math) is False,
      "an answer whose own arithmetic the CAS proves false must be rejected")
# (2026-07-31 live-proof regression) The 30B writes correct math in Unicode
# ("2² -5*2 +6 = 0"); the ASCII extractor used to break at "²" and CAS-refute the
# mutilated fragment ("-5*2 +6 = 0"), rejecting 3/3 CORRECT sparse-MoE answers in
# the first governor-routed Math School run. Correct superscript math must be
# eligible; genuinely false superscript math must still be refuted.
unicode_math = (
    "Result: x = 2, x = 3\nWork: Factor x² - 5x + 6 = (x-2)(x-3) = 0.\n"
    "Check: Substitute x=2: 2² -5*2 +6 = 0; substitute x=3: 3² -5*3 +6 = 0."
)
false_unicode_math = (
    "Result: x = 3\nWork: factoring.\nCheck: substitute x=3: 3² - 5*3 + 6 = 1."
)
check("math_accepts_unicode_superscripts",
      runner._math_answer_shows_verification(unicode_math) is True,
      "correct math written with unicode superscripts must not be CAS-refuted by a mutilated fragment")
# A bare refusal must not be admitted as verified math (2026-08-06). It used to pass the
# whole gate: "No verified result" satisfied the Result check, satisfied the concrete-math
# check through the same escape, and satisfied the signal check because "verified" is one
# of the signal words. A live probe found two of four math turns admitted on byte-identical
# refusal text. Saying it stays legal -- the contract offers it so nothing is cornered into
# fabricating -- but it is not an EXAMPLE of the habit being trained.
refusal_math = (
    "Result: No verified result\n"
    "Work: I could not determine a reliable approach for this problem.\n"
    "Check: unable to verify without a confirmed method."
)
check("math_rejects_bare_refusal",
      runner._math_answer_shows_verification(refusal_math) is False,
      "a refusal containing no arithmetic must not be captured as a verified math sample")
refusal_with_work = (
    "Result: No verified result for the closed form\n"
    "Work: partial sums 1 + 1/4 = 1.25, then 1.25 + 1/9 = 1.3611\n"
    "Check: recomputed the partial sum a second way and got 1.3611"
)
check("math_accepts_refusal_that_still_shows_real_work",
      runner._math_answer_shows_verification(refusal_with_work) is True,
      "an honest 'no closed form' answer that STILL shows checked arithmetic must stay "
      "eligible -- the rule targets empty refusals, not honesty")

# Numbered Work steps must not be misread as decimals (2026-08-06). The answer contract
# asks for "the key steps, briefly", and models enumerate them: "1. ... = 5. 2. Adjugate".
# The extractor read that RHS as the decimal 5.2 and refuted 5 != 5.2, rejecting a CORRECT
# answer for showing its work. Measured live: identical arithmetic passed unnumbered and
# was refuted numbered, and it was the only substantive reply the good lane produced in an
# 8-prompt sample -- so this single parse bug was worth most of the math yield.
check("math_numbered_steps_are_not_decimals",
      runner._math_check_has_false_relation(
          "Work: 1. Calculate determinant: (2*4 - 3*1) = 5. 2. Adjugate matrix next.") is False,
      "a period ending a numbered step must not be parsed as a decimal point")
check("math_real_decimals_still_compare",
      runner._math_check_has_false_relation("Check: 1/4 = 0.25") is False
      and runner._math_check_has_false_relation("Check: 1/4 = 0.30") is True,
      "genuine decimals must still be compared in both directions")
check("math_admits_the_real_moe_answer",
      runner._math_answer_shows_verification(
          "Result: [[0.8, -0.6], [-0.2, 0.4]]\n"
          "Work: 1. Calculate determinant: (2*4 - 3*1) = 5. 2. Adjugate matrix: [[4, -3], [-1, 2]]. "
          "3. Divide by determinant: [[4/5, -3/5], [-1/5, 2/5]].\n"
          "Check: Original * Inverse = [[1, 0], [0, 1]] (verified via matrix multiplication).") is True,
      "a real, correct sparse-MoE math answer must be admitted")

# Duplicate replies must not become N training rows (2026-08-06). A degraded lane emits the
# same canned text repeatedly, and the CT builder keys on the base prompt so identical
# replies to different prompts all survive it.
_dup_rows = [
    {"prompt_index": 1, "admit": True, "assistant_reply": "Result: 4\nCheck: 2*2 = 4"},
    {"prompt_index": 2, "admit": True, "assistant_reply": "Result: 4\nCheck:  2*2 = 4 "},
    {"prompt_index": 3, "admit": True, "assistant_reply": "Result: 9\nCheck: 3*3 = 9"},
    {"prompt_index": 4, "admit": False, "assistant_reply": "Result: 4\nCheck: 2*2 = 4"},
]
_demoted = runner._demote_duplicate_replies(_dup_rows)
check("dedupe_keeps_one_row_per_distinct_reply",
      _demoted == 1 and [r["admit"] for r in _dup_rows] == [True, False, True, False],
      "a repeated reply must be admitted once; whitespace/case must not defeat the check")
check("dedupe_names_the_original",
      _dup_rows[1].get("duplicate_of_prompt_index") == 1
      and "identical" in _dup_rows[1]["admit_reason"],
      "a demoted duplicate must point at the row it duplicates")
check("dedupe_keeps_the_row_as_evidence",
      len(_dup_rows) == 4 and _dup_rows[1]["training_sample_eligible"] is False,
      "duplicates are demoted, never dropped -- a lane repeating itself is worth seeing")
check("dedupe_ignores_already_rejected_rows",
      _dup_rows[3]["admit"] is False and "duplicate_of_prompt_index" not in _dup_rows[3],
      "an already-rejected row must not be relabelled as a duplicate")

check("math_rejects_false_unicode_superscripts",
      runner._math_answer_shows_verification(false_unicode_math) is False,
      "genuinely false superscript arithmetic must still be refuted after normalization")

# The 74/74 is quoted back from material that SUPPLIED it (card 1's proof says exactly
# that), which is why this fixture carries `real_eng_prompt` everywhere it is used: since
# 2026-08-05 an answer asserting a figure nothing gave it is rejected, so a fixture that
# states 74/74 against an empty prompt is no longer a "good answer" example.
real_eng_prompt = (
    "Walk me through the math lane; tools/verify_engel_math_lane.py holds it at 74/74. "
    "Cite only from these real files: tools/engel_math_lane.py, tools/verify_engel_math_lane.py."
)
real_eng = (
    "Confirmed: the math lane gates serving on a CAS check.\n"
    "Proof: tools/verify_engel_math_lane.py holds it at 74/74.\nStill open: None."
)
echo_eng = (
    "Answer only in this filled-in form, grounded in Engel's real system: Confirmed: a claim tied "
    "to a real Engel component. Proof: the verifier or receipt that proves it."
)
ungrounded_eng = "Confirmed: the system works well. Still open: nothing. It is all good."
fabricated_eng = (
    "Confirmed: the widget system is verified.\n"
    "Proof: tools/verify_engel_fake_thing_that_does_not_exist.py confirms it.\nStill open: None."
)
def _eng_ok(reply, prompt=""):
    """The gate returns (ok, reason) since 2026-08-04 -- the reason names which of the
    three failure shapes fired, so unpack rather than truth-testing the tuple (a bare
    tuple is always truthy, which would silently pass every rejection check here)."""
    ok, reason = runner._engineering_answer_is_grounded(reply, prompt)
    assert isinstance(ok, bool) and isinstance(reason, str) and reason.strip()
    return ok

check("eng_accepts_real", _eng_ok(real_eng, real_eng_prompt) is True,
      "a Proof citing a real existing verifier must be eligible")
check("eng_rejects_echo", _eng_ok(echo_eng) is False,
      "a contract echo must be rejected")
check("eng_rejects_ungrounded", _eng_ok(ungrounded_eng) is False,
      "an answer with no verifier/receipt must be rejected")
check("eng_rejects_fabricated_path", _eng_ok(fabricated_eng) is False,
      "a Proof citing a non-existent (fabricated) file must be rejected")

# Card-bound citation (2026-08-04). Existence alone let an answer launder itself by
# name-dropping ONE real but unrelated file (22 of 44 admitted rows across two 5-hour
# runs cited tools/engel_conical_failure_to_issue.py for every card). When the prompt
# supplies its own artifacts, the citation must be one of THOSE.
supplied_prompt = (
    "Walk me through the math lane; it holds at 74/74. Cite only from these real files: "
    "tools/engel_math_lane.py, tools/verify_engel_math_lane.py."
)
offcard_eng = (
    "Confirmed: the math lane gates serving on a CAS check.\n"
    "Proof: tools/engel_health_check.py confirms it.\nStill open: None."
)
check("eng_accepts_supplied_artifact", _eng_ok(real_eng, supplied_prompt) is True,
      "citing a file the prompt supplied must stay eligible")
check("eng_rejects_offcard_real_file", _eng_ok(offcard_eng, supplied_prompt) is False,
      "a real but unsupplied file must not launder an answer when the prompt named its own")
check("eng_offcard_still_ok_without_supply", _eng_ok(offcard_eng) is True,
      "a prompt that supplies nothing keeps the plain existence rule (older packs grade unchanged)")

# Mixed citation (2026-08-05). Binding the citation to the card proved the FIRST matching
# token was real and never looked at the rest, so an answer could pair a supplied file with
# a fabricated one and be admitted whole. The 8-hour run admitted 13 such rows out of 76 --
# 5 of them naming `verify_engel_process_liveness.py`, which has never existed -- and the
# .py-only tokenizer could not see the 7 whose fabrication was a .json receipt.
mixed_eng = (
    "Confirmed: the math lane gates serving on a CAS check.\n"
    "Proof: tools/engel_math_lane.py, checked by verify_engel_math_lane_that_is_fake.py.\n"
    "Still open: None."
)
mixed_json_eng = (
    "Confirmed: the math lane gates serving on a CAS check.\n"
    "Proof: tools/engel_math_lane.py\n"
    "Receipt: reports/engel_math_lane_2026-07-27.json\nStill open: None."
)
check("eng_rejects_mixed_real_and_fabricated", _eng_ok(mixed_eng, supplied_prompt) is False,
      "a real citation must not carry a fabricated one alongside it")
check("eng_rejects_fabricated_json_receipt", _eng_ok(mixed_json_eng, supplied_prompt) is False,
      "a fabricated .json receipt must be caught too, not just .py paths")
check("eng_mixed_reason_names_the_fabrication",
      "verify_engel_math_lane_that_is_fake.py"
      in runner._engineering_answer_is_grounded(mixed_eng, supplied_prompt)[1],
      "the reject reason must name the fabricated path so the curriculum is correctable")
# Figures nothing supplied (2026-08-05). Once citations were bound to the card's own
# artifacts, the fabrication moved to the NUMBERS: replies cited the right file and
# invented the quantity ("99.98% task completion rate", "92.3% pass rate ... #L47",
# "latency under 200ms"). Every one carried a real on-card citation, so every earlier
# check passed it. The rule is PROVENANCE, not plausibility.
check(
    "eng_rejects_invented_percentage",
    _eng_ok(
        "Confirmed: uptime is 99.2%.\nProof: tools/verify_engel_math_lane.py\nStill open: None.",
        supplied_prompt,
    ) is False,
    "a percentage nothing supplied must be rejected",
)
check(
    "eng_rejects_invented_line_reference",
    _eng_ok(
        "Confirmed: the gate holds.\nProof: tools/verify_engel_math_lane.py#L47\nStill open: None.",
        supplied_prompt,
    ) is False,
    "a #L line reference nothing supplied must be rejected -- the gate cannot check it",
)
check(
    "eng_rejects_invented_date",
    _eng_ok(
        "Confirmed: the gate holds.\nProof: tools/verify_engel_math_lane.py regression-tested "
        "2024-03-15.\nStill open: None.",
        supplied_prompt,
    ) is False,
    "a date nothing supplied must be rejected (a 20260806 answer dated its verifier 2024-03-15)",
)
check(
    "eng_accepts_figure_the_prompt_supplied",
    _eng_ok(
        "Confirmed: math holds at 74/74.\nProof: tools/verify_engel_math_lane.py\nStill open: None.",
        supplied_prompt,
    ) is True,
    "a figure the prompt handed over must stay eligible -- the rule is provenance, not arithmetic",
)
check("eng_clean_answer_unaffected_by_mixed_check", _eng_ok(real_eng, supplied_prompt) is True,
      "an answer whose every citation resolves must still be admitted")

# Invented API claims (2026-08-05). With fabricated PATHS eliminated, the 8-hour run still
# had 4 of 68 admitted rows asserting a function that exists nowhere in tools/ --
# check_liveness() "reading /proc/<pid>/status" when the real function is pid_is_running()
# opening a kernel handle. The citation was real every time, so every earlier gate passed
# it. A name defined ANYWHERE in tools/ (4,837 of them) or in builtins is accepted, so this
# only fires on an API Engel does not have.
invented_eng = (
    "Confirmed: check_liveness() reads /proc/<pid>/status for the worker.\n"
    "Proof: tools/engel_process_liveness.py\nStill open: None."
)
real_fn_eng = (
    "Confirmed: pid_is_running() opens a kernel handle instead of spawning a console.\n"
    "Proof: tools/engel_process_liveness.py\nStill open: None."
)
builtin_eng = (
    "Confirmed: the report is read with open() and printed with print().\n"
    "Proof: tools/engel_process_liveness.py\nStill open: None."
)
liveness_prompt = "Cite only from these real files: tools/engel_process_liveness.py."
check("eng_rejects_invented_function", _eng_ok(invented_eng, liveness_prompt) is False,
      "an answer asserting a function Engel does not define must be rejected")
check("eng_accepts_real_function", _eng_ok(real_fn_eng, liveness_prompt) is True,
      "a real repo function must stay admittable")
check("eng_accepts_builtin_calls", _eng_ok(builtin_eng, liveness_prompt) is True,
      "python builtins are not invented APIs")
check("eng_invented_reason_names_the_function",
      "check_liveness" in runner._engineering_answer_is_grounded(invented_eng, liveness_prompt)[1],
      "the reject reason must name the invented function so the card can be corrected")
check("eng_function_ground_truth_is_real",
      "pid_is_running" in runner._repo_function_names() and len(runner._repo_function_names()) > 500,
      "the ground-truth set must be the real repo scan, not an empty set that passes everything")

# A delivery failure must be RETURNED as a classifiable result, never raised. Nothing
# between send_prompt_through_flutter and main() catches an exception, so a single
# transient inbox write used to end an 8-hour run in a traceback -- while a turn that WAS
# delivered and then refused is tolerated up to _MAX_CONSECUTIVE_DELIVERY_FAILURES. The
# harsher failure must not be the less resilient one.
_delivery_failed = {
    "status": "FAIL",
    "wrapper_receipt_path": "",
    "wrapper_receipt": {},
    "chat_input_delivery_failed": True,
}
_served_then_refused = {
    "status": "FAIL",
    "wrapper_receipt_path": "receipt.json",
    "wrapper_receipt": {"main_server_chat_used": True},
}
check("undelivered_turn_classifies_as_delivery_failure",
      runner._is_delivery_failure(_delivery_failed) is True,
      "an undelivered prompt must count toward the consecutive-delivery-failure stop")
check("served_then_refused_is_not_a_delivery_failure",
      runner._is_delivery_failure(_served_then_refused) is False,
      "a delivered-then-refused turn must not stop the run")
check("delivery_failure_stop_still_armed",
      runner._MAX_CONSECUTIVE_DELIVERY_FAILURES == 2,
      "two adjacent delivery failures must still stop a genuinely broken pipeline")

_reasons = {
    runner._engineering_answer_is_grounded(r, p)[1]
    for r, p in ((echo_eng, ""), (ungrounded_eng, ""), (fabricated_eng, ""),
                 (offcard_eng, supplied_prompt), (mixed_eng, supplied_prompt))
}
check("eng_reject_reasons_are_diagnostic", len(_reasons) == 5,
      "each engineering failure shape must report its own reason, not one catch-all string")

# provenance: a good answer served by an EXTERNAL provider/bridge must NOT be captured
def _result(reply, **extra):
    r = {"status": "DONE", "wrapper_receipt": {"assistant_reply": reply}, "wrapper_receipt_path": "x"}
    r.update(extra)
    return r

local_good = _result(real_math)
runner._apply_discipline_eligibility(local_good, "math")
check("provenance_local_good_eligible", local_good.get("training_sample_eligible") is True,
      "a local good math turn must be captured")
bridge_good = _result(real_math, provider_bridge_used=True)
runner._apply_discipline_eligibility(bridge_good, "math")
check("provenance_bridge_blocked", bridge_good.get("training_sample_eligible") is False,
      "a bridge/provider turn must never be captured as a local training sample")
api_good = _result(real_math, provider_api_enabled=True)
runner._apply_discipline_eligibility(api_good, "math")
check("provenance_api_blocked", api_good.get("training_sample_eligible") is False,
      "a provider-API turn must never be captured as a local training sample")

# MIXED template must match the ACTIVE curriculum's cards (single source of truth)
active_tpl = json.loads(
    (TPL_DIR / f"ENGEL_TEMPLATE_{sync.ACTIVE_CURRICULUM_ID.upper()}.json").read_text(encoding="utf-8").lstrip("﻿")
)
check("mixed_matches_active_topics",
      mixed.get("material_topics") == active_tpl.get("material_topics"),
      "MIXED/default template topics must equal the active curriculum's topics")

# 4. delivery-failure classification -----------------------------------------
done = {"status": "DONE"}
quality_block = {
    "status": "FAIL",
    "wrapper_receipt_path": "x",
    "wrapper_receipt": {"main_server_chat_used": True, "local_semantic_quality": {"ok": False, "required": True}},
    "flutter_worker_result": {"ok": True},
}
no_wrapper = {"status": "FAIL", "wrapper_receipt_path": "", "wrapper_receipt": {}}
chat_never_used = {
    "status": "FAIL", "wrapper_receipt_path": "x",
    "wrapper_receipt": {"main_server_chat_used": False},
}
served_slow_surface = {
    "status": "FAIL", "wrapper_receipt_path": "x",
    "wrapper_receipt": {"main_server_chat_used": True}, "flutter_worker_result": {"ok": False},
}
check("delivery_done_not_failure", runner._is_delivery_failure(done) is False, "DONE is never a delivery failure")
check("delivery_quality_block_not_failure", runner._is_delivery_failure(quality_block) is False,
      "a delivered-then-quality-blocked turn is not a delivery failure")
check("delivery_no_wrapper_is_failure", runner._is_delivery_failure(no_wrapper) is True,
      "a turn with no wrapper is a delivery failure")
check("delivery_chat_never_used_is_failure", runner._is_delivery_failure(chat_never_used) is True,
      "a turn whose chat lane was never used is a delivery failure")
check("delivery_served_slow_surface_not_failure", runner._is_delivery_failure(served_slow_surface) is False,
      "a served turn (wrapper + chat used) is NOT a delivery failure even if the surface diagnostic was late")

# 5. form-graded training must keep the labelled form (2026-09-08)
# Live 20260904 engineering run completed 20/30 replies and captured 0 samples
# because spoken-chat wrapping ("no extra labels") overrode Confirmed/Proof.
# Do not import run_engel_standalone_chat_llm here: that module is too heavy
# for this verifier. Source-text pins the standalone twin.
import engel_chat_humanization_slm as slm  # noqa: E402

eng_delivered = runner._leveled_training_prompt(
    "Walk me through waiting out a chat-backend outage. Cite only from these real files: "
    "tools/run_engel_flutter_main_ui_prompt_training.py, tools/engel_ui_prompt_training_support.py.",
    "fellow",
    "engineering",
)
comm_delivered = runner._leveled_training_prompt(
    "Tell Joshua the next honest step in plain speech.",
    "fellow",
    "communication",
)
check(
    "engineering_delivered_prompt_is_form_graded",
    slm.is_form_graded_training_prompt(eng_delivered) is True
    and svc._is_form_graded_training_prompt(eng_delivered) is True,
    "engineering form must be detected in slm and chat service",
)
check(
    "communication_delivered_prompt_is_not_form_graded",
    slm.is_form_graded_training_prompt(comm_delivered) is False
    and svc._is_form_graded_training_prompt(comm_delivered) is False,
    "communication training must stay on the spoken-voice path",
)
standalone_src = (TOOLS / "run_engel_standalone_chat_llm.py").read_text(encoding="utf-8")
check(
    "standalone_form_graded_prompt_skips_spoken_wrapper",
    "FORM-GRADED TRAINING TURN" in standalone_src
    and "no extra labels unless Joshua asks" in standalone_src
    and standalone_src.find("if _is_form_graded_training_prompt(prompt):")
    < standalone_src.find("no extra labels unless Joshua asks"),
    "standalone local prompt builder must take the form-graded branch first",
)
check(
    "form_graded_keeps_base_temperature",
    svc._training_turn_temperature(eng_delivered, 0.3) == 0.3,
    "engineering/math/AEC training must not raise exploration temperature",
)
check(
    "communication_training_may_raise_temperature",
    (
        svc._training_turn_temperature(comm_delivered, 0.3) == 0.85
        if not svc._prompt_has_incomplete_project_inputs(comm_delivered)
        else svc._training_turn_temperature(comm_delivered, 0.3) == 0.3
    ),
    "communication voice diversity may still use the raised training temperature",
)
form_out, form_meta = slm.humanize_chat_reply(
    eng_delivered,
    "Confirmed: the runner waits.\nProof: tools/run_engel_flutter_main_ui_prompt_training.py\nStill open: None.",
    source="unit",
)
check(
    "humanizer_leaves_form_graded_training_intact",
    "Proof:" in form_out and form_meta.get("reason") == "form_graded_training_turn",
    str(form_meta.get("reason")),
)
nemotron_training = svc._nemotron_lightning_route_decision(
    eng_delivered, {"local_only_training": False}
)
nemotron_local_only = svc._nemotron_lightning_route_decision(
    "hello", {"local_only_training": True}
)
check(
    "nemotron_auto_skips_form_graded_training",
    nemotron_training.get("selected") is not True,
    str(nemotron_training.get("reason")),
)
check(
    "nemotron_auto_skips_local_only_training",
    nemotron_local_only.get("selected") is not True,
    str(nemotron_local_only.get("reason")),
)

# 6. Construction 7h must serve form drafts and finish the hour (2026-09-13)
aec_base = next((p for p in base_prompts(constr) if isinstance(p, str)), "")
aec_delivered = runner._leveled_training_prompt(aec_base, "fellow", "aec") if aec_base else ""
form_ending_on_proof = (
    "Must not proceed until confirmed: missing field measurement of the delayed egress hardware.\n"
    "Sourced facts:\n"
    "- Source document: \"2025_designer_collection_1st_printing.pdf\"; Section 1010.2.13; "
    "Source excerpt: \"the delay electronics of the delayed egress locking system shall deactivate.\"\n"
    "Open items:\n"
    "- Owner: field survey lead confirms the installed hardware\n"
    "Proof:"
)
raw_quality = svc._incomplete_input_quality_report(aec_delivered, form_ending_on_proof)
policy_quality = svc._apply_form_graded_training_quality_policy(
    aec_delivered, raw_quality, form_ending_on_proof
)
check(
    "form_training_waives_complete_ending_on_proof_line",
    bool(aec_delivered)
    and svc._is_form_graded_training_prompt(aec_delivered) is True
    and "complete_ending" in (raw_quality.get("failed_checks") or [])
    and policy_quality.get("complete_ending_waived_for_form_training") is True
    and "complete_ending" not in (policy_quality.get("failed_checks") or []),
    f"raw={raw_quality.get('failed_checks')} policy={policy_quality.get('failed_checks')}",
)
chat_src = (TOOLS / "engel_main_server_chat_http_service.py").read_text(encoding="utf-8")
trainer_src = (TOOLS / "run_engel_flutter_main_ui_prompt_training.py").read_text(encoding="utf-8")
repair_call_at = chat_src.find("semantic_retry_prompt = _semantic_local_repair_request")
form_skip_at = chat_src.find("and not _is_form_graded_training_prompt(prompt)")
check(
    "form_training_skips_140_word_semantic_repair",
    form_skip_at != -1
    and repair_call_at != -1
    and form_skip_at < repair_call_at,
    "form-graded training must not rewrite AEC forms into the 140-word repair template",
)
check(
    "scheduled_quality_block_does_not_increment_nondone_streak",
    "if result.get(\"status\") != \"DONE\" and not _is_style_gate_exhaust(result):"
    in trainer_src,
    "quality-blocked Construction turns must not abort a 7-hour schedule",
)
check(
    "scheduled_aec_fails_only_when_capture_is_empty",
    "not every sent prompt completed through the correct Flutter Engel Main chat"
    not in trainer_src
    and "one or more local turns failed CT246 semantic training eligibility"
    not in trainer_src
    and "no local turns produced a domain-eligible training sample"
    in trainer_src,
    "Construction scheduled hours use the same empty-capture bar as math/engineering",
)

passed = sum(1 for c in checks if c["status"] == "PASS")
total = len(checks)
out = {
    "schema": "engel_training_domain_discipline_verifier_v1",
    "ok": passed == total,
    "passed": passed,
    "total": total,
    "checks": checks,
}
print(json.dumps(out, indent=2))
sys.exit(0 if passed == total else 1)
