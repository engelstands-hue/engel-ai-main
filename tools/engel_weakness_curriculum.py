"""Turn Engel's own measured failures into the next lesson.

The missing half of self-training
---------------------------------
Engel already trains on what it did WELL: `_pack_admit_verdict` keeps the answers that
passed every gate, and those become SFT rows. Nothing has ever fed back what it did
BADLY. That is the difference between a system that practises and a system that learns --
across four 8-hour runs the SAME failure classes recurred (fabricated citations, invented
functions, invented figures, unnamed gaps) because nothing ever taught against them.

The material for that lesson is already on disk and is unusually good:

  * pack rows carry a DIAGNOSTIC `admit_reason` per rejected answer (since 20260804 these
    name the exact shape -- "cited a file that does not exist", "asserted a figure nothing
    supplied", "cited a real file the prompt did not supply", ...)
  * `reports/capability_eval/` records which held-out SKILL failed and why

This module clusters those into weakness classes and drafts a training card per class,
in the same four-field shape `ENGEL_CAPABILITIES_CARDS_V1` uses, so the generated material
flows through the existing generator, gates and verifiers unchanged.

The rule this module must not break
-----------------------------------
A card teaches whatever it asserts, and the grounding gate CANNOT catch a false claim that
carries a real citation -- that is how a hand-written card once taught that
`engel_device_broker.py` consumes a PID probe it never calls. So every artifact a
generated card cites is existence-checked here, and a class whose evidence names nothing
real is dropped rather than shipped with an invented proof. Generated material is the
easiest possible place to reintroduce exactly the defect the curriculum exists to remove.

Proposal, not self-modification
-------------------------------
Output is written to `memory/training/engel_main/generated/` as a PROPOSAL. Adoption is a
separate explicit step (`--adopt`), because a system that rewrites its own syllabus
unattended can drift somewhere nobody chose. Engel drafts; a human or an approved lane
adopts.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
PACKS = ROOT / "memory" / "training" / "packs"
EVAL_DIR = ROOT / "reports" / "capability_eval"
OUT_DIR = ROOT / "memory" / "training" / "engel_main" / "generated"
PROPOSAL = OUT_DIR / "ENGEL_WEAKNESS_CURRICULUM_PROPOSAL.json"
ADOPTED = OUT_DIR / "ENGEL_WEAKNESS_CURRICULUM_ADOPTED.json"

SCHEMA = "engel_weakness_curriculum_v1"

sys.path.insert(0, str(TOOLS))


@dataclass(frozen=True)
class WeaknessClass:
    key: str
    # Substrings that identify this failure in a reject reason / eval verdict.
    signatures: tuple[str, ...]
    topic: str
    scenario: str
    constraint: str
    proof: str
    artifacts: tuple[str, ...]


# One class per failure shape actually observed in the packs and the capability eval.
# The proof text of each names ONLY files verified to exist (checked at draft time).
WEAKNESS_CLASSES: tuple[WeaknessClass, ...] = (
    WeaknessClass(
        key="fabricated_citation",
        signatures=("cited a file that does not exist", "paired a real citation with a fabricated one"),
        topic="citing only artifacts that exist, and saying plainly when none does",
        scenario=(
            "Asked for proof, the easiest sentence to write is a filename that sounds right. "
            "Across four 8-hour training runs the single largest rejection class was an answer "
            "that named a verifier which has never existed in this repo -- confident, correctly "
            "formatted, and unfalsifiable until someone opened the path."
        ),
        constraint=(
            "Do not name a file, verifier, receipt or path unless it exists; when nothing "
            "verifies the claim, write that no verifier covers it yet rather than inventing "
            "one that would."
        ),
        proof=(
            "tools/run_engel_flutter_main_ui_prompt_training.py refuses any answer whose cited "
            "path does not resolve on disk, and tools/verify_engel_training_domain_discipline.py "
            "holds that rule with fixtures that must stay rejected."
        ),
        artifacts=(
            "tools/run_engel_flutter_main_ui_prompt_training.py",
            "tools/verify_engel_training_domain_discipline.py",
        ),
    ),
    WeaknessClass(
        key="offcard_citation",
        signatures=("cited a real file the prompt did not supply",),
        topic="citing the artifact the question is actually about",
        scenario=(
            "An answer can satisfy a citation check by naming any real file at all. Measured "
            "across two runs, 35 of 44 admitted answers cited one real but unrelated tool as "
            "proof for every subject -- math, model placement, device identity alike. The "
            "citation was real; the connection to the claim was not."
        ),
        constraint=(
            "Do not cite a file merely because it exists; cite the one that actually evidences "
            "this claim, and if the material did not supply such a file, say the claim is "
            "unverified rather than reaching for an unrelated real path."
        ),
        proof=(
            "tools/run_engel_flutter_main_ui_prompt_training.py binds an accepted citation to "
            "the artifacts the prompt supplied, and "
            "tools/verify_engel_training_domain_discipline.py asserts an off-card real file "
            "cannot launder an answer."
        ),
        artifacts=(
            "tools/run_engel_flutter_main_ui_prompt_training.py",
            "tools/verify_engel_training_domain_discipline.py",
        ),
    ),
    WeaknessClass(
        key="invented_figure",
        signatures=("asserted a figure nothing supplied",),
        topic="reporting only measurements something actually produced",
        scenario=(
            "A number is the most convincing thing an answer can contain and the easiest to "
            "invent. Admitted answers have claimed a 99.98% task completion rate, a 92.3% pass "
            "rate at a specific line number, a latency under 200ms, and a verification date a "
            "year before the system existed -- each beside a real citation, so each passed "
            "every gate that existed at the time."
        ),
        constraint=(
            "Do not state a percentage, count, duration, line number or date unless something "
            "supplied it; an unmeasured quantity is an unknown, and an unknown is reported as "
            "one rather than estimated."
        ),
        proof=(
            "tools/run_engel_flutter_main_ui_prompt_training.py rejects a figure the prompt "
            "never supplied, and tools/engel_capability_eval.py scores that behaviour on "
            "held-out prompts against a baseline it is allowed to fail."
        ),
        artifacts=(
            "tools/run_engel_flutter_main_ui_prompt_training.py",
            "tools/engel_capability_eval.py",
        ),
    ),
    WeaknessClass(
        key="invented_function",
        signatures=("asserted a function engel does not define",),
        topic="naming only functions and APIs that the code actually defines",
        scenario=(
            "Once file paths had to be real, invented detail moved one level in: answers began "
            "describing plausible APIs for real modules -- a check_liveness() reading /proc, a "
            "run_cas_verification(), a validate_heartbeat() -- none of which any file defines. "
            "The citation resolved, so the answer read as grounded."
        ),
        constraint=(
            "Do not describe a function, method or field unless the named module defines it; "
            "describe what the file does in prose rather than inventing an interface for it."
        ),
        proof=(
            "tools/run_engel_flutter_main_ui_prompt_training.py checks claimed function names "
            "against every definition in tools/, and "
            "tools/verify_engel_training_domain_discipline.py keeps that check honest."
        ),
        artifacts=(
            "tools/run_engel_flutter_main_ui_prompt_training.py",
            "tools/verify_engel_training_domain_discipline.py",
        ),
    ),
    WeaknessClass(
        key="unnamed_gap",
        signatures=("did not name the gap plainly", "carried no proof: line",
                    "cited no verifier or receipt at all"),
        topic="stating the unknown out loud instead of answering around it",
        scenario=(
            "The held-out capability eval scores an answer zero when a real gap exists and the "
            "reply simply does not mention it. Engel currently scores 0.5 on honest-unknown and "
            "0.0 on refusing a false premise: asked which verifier proves a thing nothing "
            "verifies, it answers smoothly and never says the verifier is missing."
        ),
        constraint=(
            "Do not answer around a gap; when no verifier, receipt or measurement covers the "
            "question -- or when the question assumes something untrue -- say so in the answer "
            "itself before offering anything else."
        ),
        proof=(
            "tools/engel_capability_eval.py scores honest-unknown and false-premise handling on "
            "held-out prompts, and tools/verify_engel_capability_eval.py proves a silent gap "
            "cannot score as honest."
        ),
        artifacts=(
            "tools/engel_capability_eval.py",
            "tools/verify_engel_capability_eval.py",
        ),
    ),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _artifact_exists(rel: str) -> bool:
    return (ROOT / rel.replace("\\", "/")).is_file()


def classify(reason: str) -> str | None:
    """Map one reject reason / eval verdict onto a weakness class."""
    low = " ".join(str(reason or "").split()).casefold()
    for spec in WEAKNESS_CLASSES:
        if any(sig in low for sig in spec.signatures):
            return spec.key
    return None


def observed_weaknesses(
    packs_dir: Path = PACKS, eval_dir: Path = EVAL_DIR
) -> dict[str, Any]:
    """Count every rejected answer and failed eval prompt by weakness class."""
    counts: collections.Counter[str] = collections.Counter()
    unmatched: collections.Counter[str] = collections.Counter()
    sources: dict[str, int] = {"pack_rows": 0, "eval_rows": 0}

    for pack in sorted(packs_dir.glob("ENGEL_PROMPT_TRAINING_PACK_*.jsonl")):
        for line in pack.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict) or row.get("admit") is True:
                continue
            reason = str(row.get("admit_reason") or "")
            if not reason:
                continue
            sources["pack_rows"] += 1
            key = classify(reason)
            if key:
                counts[key] += 1
            else:
                unmatched[reason[:70]] += 1

    latest = eval_dir / "ENGEL_CAPABILITY_EVAL_LATEST.json"
    if latest.is_file():
        try:
            receipt = json.loads(latest.read_text(encoding="utf-8-sig"))
        except ValueError:
            receipt = {}
        for row in receipt.get("rows") or []:
            if row.get("passed"):
                continue
            sources["eval_rows"] += 1
            key = classify(str(row.get("why") or ""))
            if key:
                counts[key] += 1
            else:
                unmatched[str(row.get("why"))[:70]] += 1

    return {
        "counts": dict(counts.most_common()),
        "unmatched": dict(unmatched.most_common(5)),
        "sources": sources,
    }


def draft_cards(counts: dict[str, int], min_observations: int = 3) -> tuple[list[dict], list[dict]]:
    """Draft one card per weakness seen at least `min_observations` times.

    Returns (cards, dropped). A class is dropped rather than shipped when any artifact it
    would cite is missing -- generated material must never introduce the fabricated
    citation the curriculum exists to remove."""
    cards: list[dict] = []
    dropped: list[dict] = []
    for spec in WEAKNESS_CLASSES:
        seen = int(counts.get(spec.key, 0))
        if seen < min_observations:
            continue
        missing = [a for a in spec.artifacts if not _artifact_exists(a)]
        if missing:
            dropped.append({"weakness": spec.key, "reason": "artifact missing", "missing": missing})
            continue
        cards.append(
            {
                "topic": spec.topic,
                "scenario": spec.scenario,
                "constraint": spec.constraint,
                "proof": spec.proof,
                "artifacts": list(spec.artifacts),
                "weakness_key": spec.key,
                "observations": seen,
            }
        )
    return cards, dropped


def build_proposal(min_observations: int = 3) -> dict[str, Any]:
    observed = observed_weaknesses()
    cards, dropped = draft_cards(observed["counts"], min_observations)
    return {
        "schema": SCHEMA,
        "generated_at_utc": _utc_now(),
        "min_observations": min_observations,
        "observed": observed,
        "card_count": len(cards),
        "cards": cards,
        "dropped": dropped,
        "adoption": "proposal only -- run with --adopt to promote to the adopted file",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-observations", type=int, default=3,
                        help="how many times a weakness must be seen before it earns a card")
    parser.add_argument("--adopt", action="store_true",
                        help="promote the proposal to the adopted curriculum file")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    proposal = build_proposal(args.min_observations)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROPOSAL.write_text(json.dumps(proposal, indent=2), encoding="utf-8")

    if args.adopt:
        if not proposal["cards"]:
            print(json.dumps({"ok": False, "error": "no cards to adopt"}, indent=2))
            return 1
        adopted = dict(proposal)
        adopted["adopted_at_utc"] = _utc_now()
        adopted["adoption"] = "adopted"
        ADOPTED.write_text(json.dumps(adopted, indent=2), encoding="utf-8")

    if args.summary:
        print(json.dumps(
            {
                "schema": proposal["schema"],
                "observed_counts": proposal["observed"]["counts"],
                "card_count": proposal["card_count"],
                "cards": [{"weakness_key": c["weakness_key"], "observations": c["observations"],
                           "topic": c["topic"]} for c in proposal["cards"]],
                "dropped": proposal["dropped"],
                "proposal_path": str(PROPOSAL),
            },
            indent=2,
        ))
    else:
        print(json.dumps(proposal, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
