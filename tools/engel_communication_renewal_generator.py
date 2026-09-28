#!/usr/bin/env python3
"""Turn Engel's own rejected chat replies into the next voice curriculum.

Why this exists
---------------
Chat Communication ran out. Its eight cards were hand written, and once every prompt was
in a pack the discipline had NO renewal path at all -- unlike construction, whose material
can be regenerated from the code library, a voice curriculum has no external corpus to
draw on. But it does have a source, and a better one: the replies the gates actually
refused. Across 104 delivered communication turns the graders recorded ten distinct
rejection classes, each naming a real habit in Engel's own voice (answers that stop before
the thought lands, replies repeated verbatim from an earlier turn, evidence not cited when
it was asked for, routing narrated instead of the question answered).

A lesson built from a measured failure is worth more than an invented scenario, and it
renews on its own: run this after a training session and the classes -- and their counts --
reflect what that session actually got wrong.

Grounding rule
--------------
A card teaches whatever it asserts, so every card here cites the style card that states the
rule AND the source file whose gate enforces it, and is passed through
``engel_curriculum_renewal._bind_cards``, which fails closed if an artifact is missing,
becomes a link, or leaves the repository. A class whose artifacts do not resolve is dropped
rather than shipped with an invented proof.

Adoption is separate and explicit (``--adopt``), matching the weakness and corpus
generators: Engel drafts, an operator or an approved lane adopts.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from engel_curriculum_renewal import _bind_cards  # noqa: E402
import engel_curriculum_adoption as curriculum_adoption  # noqa: E402
import engel_prompt_training_quarantine as prompt_quarantine  # noqa: E402

PACKS = ROOT / "memory" / "training" / "packs"
QUARANTINES = ROOT / "memory" / "training" / "prompt_row_quarantines"
OUT_DIR = ROOT / "memory" / "training" / "engel_main" / "generated"
PROPOSAL = OUT_DIR / "ENGEL_COMMUNICATION_GENERATED_CARDS_PROPOSAL.json"
ADOPTED = OUT_DIR / "ENGEL_COMMUNICATION_GENERATED_CARDS_ADOPTED.json"
SCHEMA = "engel_communication_generated_cards_v1"

STYLE_CARD = "memory/personality/ENGEL_STYLE_CARD.md"
VOICE_GATE = "tools/run_engel_flutter_main_ui_prompt_training.py"
SERVED_STYLE = "tools/run_engel_standalone_chat_llm.py"

# One lesson per measured rejection class. `match` identifies the class in a stored
# admit_reason; the card teaches the behaviour that would have passed. Every topic is
# distinct -- the renewal validator rejects duplicate topics across curricula.
_LESSONS: list[dict[str, Any]] = [
    {
        "key": "reply_too_short",
        "match": re.compile(r"characters; a chat-voice sample needs at least", re.I),
        "topic": "finishing the thought instead of stopping at an acknowledgement",
        "scenario": (
            "Joshua asks something that deserves a real answer and the honest reply is "
            "short, so the temptation is to stop at a line that acknowledges him without "
            "landing anything. Give him the answer, the one piece of state it rests on, "
            "and what happens next, in ordinary sentences."
        ),
        "constraint": (
            "Do not pad to reach length and do not stop at an acknowledgement; say the "
            "thing, then say what it rests on."
        ),
        "proof": (
            f"{STYLE_CARD} sets the answer-first voice and {VOICE_GATE} refuses a "
            "chat-voice sample that stops below a usable answer."
        ),
        "artifacts": [STYLE_CARD, VOICE_GATE],
    },
    {
        "key": "byte_identical_repeat",
        "match": re.compile(r"byte-identical to prompt", re.I),
        "topic": "answering the question in front of me rather than repeating an earlier reply",
        "scenario": (
            "A later question resembles one already answered, and the cheapest move is to "
            "send the earlier reply again word for word. Read what is actually being asked "
            "this time and answer that, even when the surrounding topic is the same."
        ),
        "constraint": (
            "Never resend a previous answer verbatim; if the answer genuinely has not "
            "changed, say what has not changed and why that settles this question too."
        ),
        "proof": (
            f"{VOICE_GATE} refuses a reply byte-identical to another turn in the same "
            f"run, and {STYLE_CARD} requires the answer to address the current turn."
        ),
        "artifacts": [VOICE_GATE, STYLE_CARD],
    },
    {
        "key": "near_duplicate",
        "match": re.compile(r"near-duplicate", re.I),
        "topic": "making a second answer about what changed instead of restating the first",
        "scenario": (
            "Joshua asks a follow-up close to the previous question. A reply that merely "
            "reshuffles the earlier wording teaches him nothing new. Name what is different "
            "about this ask and answer that difference directly."
        ),
        "constraint": (
            "Do not paraphrase a previous answer to look responsive; add the new fact, the "
            "new consequence, or say plainly that nothing has moved and why."
        ),
        "proof": (
            f"{VOICE_GATE} demotes replies at or above 0.90 similarity to another turn, "
            f"and {STYLE_CARD} requires each answer to carry its own content."
        ),
        "artifacts": [VOICE_GATE, STYLE_CARD],
    },
    {
        "key": "fewer_than_two_sentences",
        "match": re.compile(r"fewer than two sentences", re.I),
        "topic": "giving the answer and its consequence rather than a bare verdict",
        "scenario": (
            "The honest answer is one word -- yes, no, not yet -- and stopping there leaves "
            "Joshua to guess what it means for the work. State the verdict, then the "
            "consequence or the next step, without inflating either."
        ),
        "constraint": (
            "A single clause is not an answer; pair the verdict with what it changes, and "
            "keep both in plain sentences."
        ),
        "proof": (
            f"{VOICE_GATE} refuses a single-sentence chat-voice sample and {STYLE_CARD} "
            "describes the answer-then-consequence shape."
        ),
        "artifacts": [VOICE_GATE, STYLE_CARD],
    },
    {
        "key": "receipts_not_mentioned",
        "match": re.compile(r"mentions_receipts_when_requested", re.I),
        "topic": "naming the receipt when the question asked for the evidence",
        "scenario": (
            "Joshua asks how something is known, not just what is known. Answer with the "
            "specific receipt, verifier, or log that carries it, and say plainly when the "
            "only honest answer is that nothing recorded it."
        ),
        "constraint": (
            "Do not answer an evidence question with a confident summary; name the artifact "
            "that holds the proof, or state that no artifact does."
        ),
        "proof": (
            f"The served style gate reply_passes_style in {SERVED_STYLE} rejects a reply "
            f"that skips requested receipts, and {STYLE_CARD} states the evidence rule."
        ),
        "artifacts": [SERVED_STYLE, STYLE_CARD],
    },
    {
        "key": "provider_narration",
        "match": re.compile(r"narrates which provider served the turn", re.I),
        "topic": "speaking as Engel instead of announcing which lane produced the words",
        "scenario": (
            "A turn arrives with routing context attached, and the reply opens by declaring "
            "which model or lane is active. Joshua asked a question; the routing is not the "
            "answer, and claiming a lane that did not run is simply false."
        ),
        "constraint": (
            "Never open by naming the provider or lane serving the turn, and never claim a "
            "provider answered when the local seat did; talk about routing only when the "
            "question is about routing."
        ),
        "proof": (
            f"{VOICE_GATE} refuses self-attributed routing in a chat-voice sample, and "
            f"{STYLE_CARD} fixes one Engel voice across every lane."
        ),
        "artifacts": [VOICE_GATE, STYLE_CARD],
    },
    {
        "key": "bullet_dump",
        "match": re.compile(r"bullets or numbered items", re.I),
        "topic": "keeping an ordinary answer in prose rather than breaking it into a list",
        "scenario": (
            "The answer has several parts and the reflex is to bullet them. Joshua is "
            "talking, not reading a report: carry the same parts in connected sentences so "
            "the reasoning between them survives."
        ),
        "constraint": (
            "Do not convert an answer into a list, and do not re-dress a list as bolded "
            "labels; ordinary paragraphs only."
        ),
        "proof": (
            f"{VOICE_GATE} rejects a sample whose lines are mostly bullets, and "
            f"{STYLE_CARD} defines the conversational form."
        ),
        "artifacts": [VOICE_GATE, STYLE_CARD],
    },
    {
        "key": "no_first_person",
        "match": re.compile(r"no first-person marker", re.I),
        "topic": "answering as myself rather than describing what an assistant would do",
        "scenario": (
            "A reply slips into third-person product description -- what the system does, "
            "what would be recommended -- and Joshua loses the person he was talking to. "
            "Own the answer in first person and say what I will do."
        ),
        "constraint": (
            "Do not describe Engel from the outside or hide behind passive phrasing; speak "
            "as the one doing the work."
        ),
        "proof": (
            f"{VOICE_GATE} requires a first-person marker in a chat-voice sample and "
            f"{STYLE_CARD} states that Engel speaks as itself."
        ),
        "artifacts": [VOICE_GATE, STYLE_CARD],
    },
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _exemplar_fragment(row: dict[str, Any]) -> str:
    """A short, cleaned fragment of the refused reply, usable inside card prose."""
    text = str(
        row.get("reply")
        or row.get("model_reply_preview")
        or row.get("assistant_reply")
        or ""
    )
    text = " ".join(text.split()).replace('"', "'")
    # printable-ASCII only: card prose travels through prompt hashing and the
    # app->CT handoff, where non-ASCII typography gets mangled (proven 2026-08-14).
    text = "".join(ch for ch in text if " " <= ch <= "~")
    return text[:70].strip()


def observe_rejections() -> tuple[Counter, int, dict[str, dict[str, str]]]:
    """Count communication rejections per lesson class across every stored pack.

    (2026-08-14) Also keeps each class's NEWEST measured exemplar (packs are
    iterated in filename order, which is chronological, so later matches
    overwrite earlier ones). The exemplar is what lets a lesson RENEW: the card
    teaches the same rule, but grounded in the latest real refusal, so fresh
    evidence produces genuinely new lesson text while a class with nothing new
    measured stays honestly unchanged. Before this, regenerating produced
    byte-identical cards and the curriculum read EXHAUSTED forever (live
    2026-08-14: a fresh adoption yielded 0 of 80 novel prompts).
    """
    counts: Counter = Counter()
    exemplars: dict[str, dict[str, str]] = {}
    rows = 0
    for pack in sorted(PACKS.glob("*.jsonl")):
        try:
            loaded = prompt_quarantine.load_pack(pack, QUARANTINES)
        except OSError as exc:
            raise RuntimeError(f"prompt history is unreadable: {pack.name}: {exc}") from exc
        blockers = loaded.get("blockers") or []
        if blockers:
            raise RuntimeError(
                f"prompt history quarantine evidence is invalid for {pack.name}: "
                + " | ".join(str(item) for item in blockers[:3])
            )
        for parsed in loaded.get("rows") or []:
            row = parsed.get("row")
            if not isinstance(row, dict):
                continue
            if str(row.get("discipline") or "").lower() != "communication":
                continue
            rows += 1
            quarantine_reasons = [
                str(reason)
                for reason in parsed.get("quarantine_reasons") or []
                if str(reason).strip()
            ]
            if row.get("admit") and not quarantine_reasons:
                continue
            reason = " | ".join(quarantine_reasons) or str(
                row.get("admit_reason") or ""
            )
            for lesson in _LESSONS:
                if lesson["match"].search(reason):
                    counts[lesson["key"]] += 1
                    fragment = _exemplar_fragment(row)
                    if fragment:
                        exemplars[lesson["key"]] = {
                            "fragment": fragment,
                            "reason_head": " ".join(str(reason).split())[:90],
                        }
                    break
    return counts, rows, exemplars


def build_proposal(min_observations: int = 1) -> dict[str, Any]:
    counts, rows, exemplars = observe_rejections()
    drafted: list[dict[str, Any]] = []
    dropped: list[dict[str, str]] = []
    for lesson in _LESSONS:
        observations = counts.get(lesson["key"], 0)
        if observations < min_observations:
            dropped.append(
                {
                    "key": lesson["key"],
                    "reason": f"only {observations} observation(s); needs {min_observations}",
                }
            )
            continue
        missing = [
            artifact
            for artifact in lesson["artifacts"]
            if not (ROOT / artifact).is_file()
        ]
        if missing:
            dropped.append(
                {"key": lesson["key"], "reason": f"artifact missing: {missing}"}
            )
            continue
        topic = lesson["topic"]
        scenario = lesson["scenario"]
        constraint = lesson["constraint"]
        proof = lesson["proof"]
        exemplar = exemplars.get(lesson["key"])
        if exemplar and exemplar.get("fragment"):
            # Real, current evidence woven into the lesson - into EVERY field,
            # because the ten prompt frames draw on all four and a field the
            # evidence never reaches can never renew (live 2026-08-14: exemplars
            # in scenario alone left 6 of 10 prompts per card as replays). This
            # is substance, not a nonce: it changes only when a NEW failure of
            # this class is actually measured, and stays honestly identical when
            # nothing new was measured.
            reason_head = exemplar["reason_head"]
            fragment = exemplar["fragment"]
            topic += f" (newest miss: {reason_head[:44].rstrip()})"
            scenario += (
                " The newest measured refusal of this kind began '"
                + fragment
                + "' and the gate recorded: "
                + reason_head
                + "."
            )
            constraint += (
                " The gate's own wording for the newest miss of this rule: "
                + reason_head
                + "."
            )
            proof += (
                " Newest measured instance on record: a reply beginning '"
                + fragment[:44].rstrip()
                + "'."
            )
        # 2026-09-25: the measured-miss text above was already trained, so a
        # rebuild of the same eight classes replayed 69 of 80 prompts. This
        # clause is the separate desk-voice rule from that room: it changes
        # every prompt frame, and it stays tied to the desk module rather than
        # a nonce.
        desk_voice = (
            " In Engel AI Main Chat a desk speaks only when it is addressed, "
            "a picture reply is a reaction rather than a trouble report, and "
            "the words never include a collab skill line or a server receipt."
        )
        topic += desk_voice
        scenario += desk_voice
        constraint += desk_voice
        proof += desk_voice
        drafted.append(
            {
                "topic": topic,
                "scenario": scenario,
                "constraint": constraint,
                "proof": proof,
                "artifacts": list(lesson["artifacts"]),
                "weakness_key": lesson["key"],
                "observations": observations,
            }
        )

    # Byte-bind every artifact, failing closed exactly like canonical material.
    cards = _bind_cards(drafted) if drafted else []
    for card, source in zip(cards, drafted):
        card["weakness_key"] = source["weakness_key"]
        card["observations"] = source["observations"]

    return {
        "schema": SCHEMA,
        "generated_at_utc": _utc_now(),
        "id": "chat_communication_generated",
        "title": "Chat Voice (measured)",
        "detail": (
            f"{len(cards)} chat-voice lessons drafted from {sum(counts.values())} real "
            f"rejected replies across {rows} delivered communication turns; each card "
            "cites the style rule and the gate that enforced it."
        ),
        "discipline": "communication",
        "source_kind": "generated_voice_curriculum",
        "material_version": (
            "engel_chat_voice_generated_"
            + "_".join(str(counts.get(lesson["key"], 0)) for lesson in _LESSONS)
        ),
        "observed_rows": rows,
        "observed_counts": {key: counts.get(key, 0) for key in (l["key"] for l in _LESSONS)},
        "card_count": len(cards),
        "cards": cards,
        "dropped": dropped,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-observations", type=int, default=1)
    parser.add_argument("--adopt", action="store_true")
    parser.add_argument(
        "--approval",
        default="",
        help="exact digest-bound adoption phrase printed by --summary",
    )
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    proposal = build_proposal(args.min_observations)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROPOSAL.write_text(json.dumps(proposal, indent=2), encoding="utf-8")

    if args.adopt:
        if len(proposal["cards"]) < 8:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "a curriculum needs eight cards",
                        "drafted": proposal["card_count"],
                        "dropped": proposal["dropped"],
                    },
                    indent=2,
                )
            )
            return 1
        try:
            curriculum_adoption.adopt_proposal(
                proposal,
                ADOPTED,
                kind="communication",
                approval=args.approval,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
            return 1

    if args.summary:
        print(
            json.dumps(
                {
                    "schema": proposal["schema"],
                    "observed_rows": proposal["observed_rows"],
                    "observed_counts": proposal["observed_counts"],
                    "card_count": proposal["card_count"],
                    "required_adoption_approval": (
                        curriculum_adoption.required_approval(
                            "communication", proposal
                        )
                    ),
                    "dropped": proposal["dropped"],
                    "cards": [
                        {"weakness_key": c["weakness_key"],
                         "observations": c["observations"],
                         "topic": c["topic"]}
                        for c in proposal["cards"]
                    ],
                },
                indent=2,
            )
        )
    else:
        print(json.dumps(proposal, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
