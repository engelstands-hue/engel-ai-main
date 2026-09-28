"""Gate for the weakness->curriculum loop (tools/engel_weakness_curriculum.py).

This module WRITES TRAINING MATERIAL, which makes it the highest-leverage place in the
system to reintroduce the exact defect the curriculum exists to remove. A hand-written
card once taught that engel_device_broker.py consumes a PID probe it never calls; the
grounding gate could not catch it, because the citation was real and only the claim was
false. Generated cards get the same scrutiny, mechanically:

  * every artifact a shippable card cites must exist on disk
  * a class whose artifacts are missing must be DROPPED, never shipped with an invented proof
  * card prose must not quote the answer contract (CONTRACT_ECHO_MARKERS are fatal at grade
    time, so a card containing one would teach an answer that can never be admitted)
  * generated topics must not collide with the hand-written curriculum
  * adoption must be explicit -- drafting must never mutate the adopted file
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import engel_weakness_curriculum as wc  # noqa: E402
from engel_governor import CONTRACT_ECHO_MARKERS  # noqa: E402

checks: list[dict] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


# --- 1. classification is real, both directions -----------------------------------
check(
    "classifies_every_observed_failure_shape",
    all(
        wc.classify(reason) == expected
        for reason, expected in (
            ("engineering answer cited a file that does not exist -- not captured", "fabricated_citation"),
            ("engineering answer paired a real citation with a fabricated one (x.py) -- not captured",
             "fabricated_citation"),
            ("engineering answer cited a real file the prompt did not supply -- not captured",
             "offcard_citation"),
            ("engineering answer asserted a figure nothing supplied (99.2%) -- not captured",
             "invented_figure"),
            ("engineering answer asserted a function Engel does not define (solve) -- not captured",
             "invented_function"),
            ("did not name the gap plainly", "unnamed_gap"),
        )
    ),
    "each real reject reason must map to its weakness class",
)
check(
    "unknown_reason_is_not_forced_into_a_class",
    wc.classify("some brand new failure nobody has seen") is None,
    "an unrecognised reason must stay unmatched rather than be mislabelled",
)

# --- 2. every card cites artifacts that exist -------------------------------------
missing_by_class = {
    spec.key: [a for a in spec.artifacts if not wc._artifact_exists(a)]
    for spec in wc.WEAKNESS_CLASSES
}
check(
    "all_declared_artifacts_exist",
    not any(missing_by_class.values()),
    f"a generated card must never cite a missing file; missing={ {k: v for k, v in missing_by_class.items() if v} }",
)
check(
    "every_class_declares_at_least_one_artifact",
    all(spec.artifacts for spec in wc.WEAKNESS_CLASSES),
    "a card with no citable artifact cannot be answered honestly (the recon-card defect)",
)

# --- 3. a class with a missing artifact is DROPPED, not shipped -------------------
real = wc.WEAKNESS_CLASSES[0]
poisoned = wc.WeaknessClass(
    key="poisoned", signatures=("poisoned",), topic="t", scenario="s", constraint="c",
    proof="cites tools/verify_engel_this_does_not_exist.py",
    artifacts=("tools/verify_engel_this_does_not_exist.py",),
)
saved = wc.WEAKNESS_CLASSES
try:
    wc.WEAKNESS_CLASSES = (real, poisoned)
    cards, dropped = wc.draft_cards({real.key: 99, "poisoned": 99}, min_observations=1)
    check(
        "drops_a_class_whose_artifact_is_missing",
        [c["weakness_key"] for c in cards] == [real.key]
        and [d["weakness"] for d in dropped] == ["poisoned"],
        "a class citing a non-existent file must be dropped, never shipped",
    )
finally:
    wc.WEAKNESS_CLASSES = saved

# --- 4. threshold is honoured ------------------------------------------------------
few, _ = wc.draft_cards({wc.WEAKNESS_CLASSES[0].key: 2}, min_observations=3)
many, _ = wc.draft_cards({wc.WEAKNESS_CLASSES[0].key: 3}, min_observations=3)
check(
    "respects_min_observations",
    not few and len(many) == 1,
    "a weakness under the threshold must not earn a card; at the threshold it must",
)

# --- 5. card prose must not echo the answer contract ------------------------------
# CONTRACT_ECHO_MARKERS are fatal at grade time, so a card containing one would teach an
# answer shape that can never be admitted.
echoes = []
for spec in wc.WEAKNESS_CLASSES:
    blob = " ".join((spec.topic, spec.scenario, spec.constraint, spec.proof)).casefold()
    echoes += [(spec.key, m) for m in CONTRACT_ECHO_MARKERS if m in blob]
check("no_card_echoes_the_answer_contract", not echoes,
      f"card prose must not quote the answer contract; found {echoes[:3]}")

# --- 6. generated topics stay distinct from the hand-written curriculum -----------
try:
    from run_engel_one_day_local_first_chat_training import ENGEL_CAPABILITIES_CARDS_V1 as CARDS
    hand = {c["topic"].casefold() for c in CARDS}
    clash = [s.key for s in wc.WEAKNESS_CLASSES if s.topic.casefold() in hand]
    check("generated_topics_do_not_collide", not clash,
          f"a generated topic must not duplicate a hand-written one; clash={clash}")
except Exception as exc:  # pragma: no cover
    check("generated_topics_do_not_collide", False, f"could not load hand-written cards: {exc}")

check(
    "weakness_keys_unique",
    len({s.key for s in wc.WEAKNESS_CLASSES}) == len(wc.WEAKNESS_CLASSES),
    "weakness keys must be unique so counts attribute to one class",
)

# --- 7. drafting never mutates the adopted file -----------------------------------
before = wc.ADOPTED.read_bytes() if wc.ADOPTED.exists() else None
wc.build_proposal(min_observations=1)
after = wc.ADOPTED.read_bytes() if wc.ADOPTED.exists() else None
check("drafting_does_not_adopt", before == after,
      "building a proposal must never write the adopted curriculum -- adoption is explicit")

# --- 8. it reads the real corpus without crashing ---------------------------------
observed = wc.observed_weaknesses()
check(
    "reads_real_packs",
    isinstance(observed.get("counts"), dict) and observed["sources"]["pack_rows"] >= 0,
    "must survey the real packs on disk and report per-class counts",
)

failed = sum(1 for c in checks if c["status"] != "PASS")
print(json.dumps(
    {
        "schema": "engel_weakness_curriculum_verifier_v1",
        "status": "FAIL" if failed else "PASS",
        "passed": len(checks) - failed,
        "total": len(checks),
        "observed_counts": observed.get("counts"),
        "checks": checks,
    },
    indent=2,
))
raise SystemExit(1 if failed else 0)
