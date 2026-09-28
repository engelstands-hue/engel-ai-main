#!/usr/bin/env python3
"""Generate Construction Coordination material from the indexed code library.

Why this exists
---------------
Construction ran out. Its cards were hand written (``engel_construction_renewal_curriculum``
v1, 80 prompts), and once every one of those prompts was in a pack the curriculum was
EXHAUSTED with no way forward: a training system that can only run a syllabus once is not
practising, it is reading a book once. The operator's five-PDF code library is already
ingested as 19,513 verified sections, which is material for hundreds of hours -- the gap
was a generator, not the source.

What the sync tool's own comment requires of new AEC material (verbatim contract):

  "Future AEC renewal belongs here only after each card is bound to a single manifest
   document/edition and its generated prompts ask for the Section + exact-quote proof the
   grader enforces. No nonce or cosmetic prompt mutation is an acceptable substitute."

This generator meets all three:

  * ONE document per card, named by its exact manifest filename.
  * ONE real section id per card, and the card is emitted only after
    ``build_prompt_evidence_context`` resolves that anchor to a real local excerpt -- an
    unresolvable section is dropped, never shipped with an invented proof.
  * Novelty comes from teaching a DIFFERENT SECTION of the code, not from a nonce: the
    generated prompts differ because the code section being read differs.

Adoption is a separate explicit step, matching ``engel_weakness_curriculum``: Engel drafts,
an operator or an approved lane adopts.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import engel_construction_corpus as corpus  # noqa: E402
import engel_curriculum_adoption as curriculum_adoption  # noqa: E402

OUT_DIR = ROOT / "memory" / "training" / "engel_main" / "generated"
PROPOSAL = OUT_DIR / "ENGEL_CONSTRUCTION_GENERATED_CARDS_PROPOSAL.json"
ADOPTED = OUT_DIR / "ENGEL_CONSTRUCTION_GENERATED_CARDS_ADOPTED.json"
CORPUS_ROOT = ROOT / "memory" / "training" / "construction_env"
MANIFEST_REL = "memory/training/construction_env/CONSTRUCTION_CORPUS_MANIFEST.json"
SCHEMA = "engel_construction_generated_cards_v1"

# A code section, not a page number or stray token: at least one dot-separated level,
# optionally a chapter prefix such as 11B-. Anything looser pulls in table cells.
_SECTION_PATTERN = re.compile(r"^(?:[0-9]{1,3}[A-Z]?-)?[0-9]{1,4}(?:\.[0-9]{1,3}){1,3}$")

# Human labels for the manifest filenames, used in card prose only.
_DOCUMENT_LABELS = {
    "2024_caldag_1st_ptg.pdf": "the 2024 CALDAG first printing",
    "2025_designer_collection_1st_printing.pdf": "the 2025 Designer Collection first printing",
    "designer_updated_2026_jan_errata.pdf": "the January 2026 Designer errata",
    "global_24_120x40_calculations_11_05_2023.pdf": "the 2023 global 120x40 calculation set",
    "structural_calcs_v1.pdf": "the structural calculation set v1",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extracted_artifact(document: str) -> str:
    return f"memory/training/construction_env/extracted/{Path(document).stem}.jsonl"


def _sections_by_document(index: dict[str, Any]) -> dict[str, list[str]]:
    """Section ids that belong to exactly ONE document, grouped by that document.

    Single-document sections keep a card's citation unambiguous: a section printed in
    both the collection and its errata cannot prove which edition the answer read.
    """
    grouped: dict[str, list[str]] = {}
    for section_id, occurrences in index.get("sections", {}).items():
        if not _SECTION_PATTERN.match(str(section_id)):
            continue
        documents = {
            str(entry.get("doc") or "")
            for entry in (occurrences if isinstance(occurrences, list) else [])
            if isinstance(entry, dict) and entry.get("doc")
        }
        if len(documents) != 1:
            continue
        document = documents.pop()
        if document not in _DOCUMENT_LABELS:
            continue
        grouped.setdefault(document, []).append(str(section_id))
    for document in grouped:
        grouped[document].sort()
    return grouped


def _card_for(document: str, section_id: str) -> dict[str, Any]:
    label = _DOCUMENT_LABELS[document]
    return {
        "topic": (
            f"reading Section {section_id} in {label} without extending it past "
            "its quoted words"
        ),
        "scenario": (
            f"A coordination review needs the rule stated in Section {section_id} of "
            f"{label}. The packet supplies that section's excerpt and nothing else: no "
            "field measurement, no product submittal, no building-official determination, "
            "and no other edition. Answer only from the supplied excerpt, and record every "
            "quantity, applicability question, or field condition the excerpt does not "
            "settle as an open item with the owner who must close it."
        ),
        "constraint": (
            "A section number is not a claim. Do not infer a count, ratio, dimension, "
            "exception, or scope from the section title, from another edition, or from "
            "what the rule usually says; the exact quoted words are the boundary of the "
            "sourced claim."
        ),
        "proof": (
            "The claim is admissible only when its ledger line contains ONLY the exact "
            f"manifest filename {document}, the words Section {section_id}, and the "
            "supplied excerpt copied character-for-character between double quotes - "
            "change nothing inside the quotes and add no summary or restatement on that "
            "line. Start each heading and each '- Source document' entry on its own "
            "line. Anything in your own words, and anything the excerpt does not state, "
            "goes under Open items."
        ),
        "documents": [document],
        "evidence_anchors": [{"document": document, "section": section_id}],
        "artifacts": [_extracted_artifact(document), MANIFEST_REL],
    }


def _anchor_resolves(card: dict[str, Any]) -> tuple[bool, str]:
    """A card ships only when its anchor resolves to real local source text."""
    try:
        packet = corpus.build_prompt_evidence_context(
            card["evidence_anchors"], corpus_root=CORPUS_ROOT
        )
    except Exception as exc:  # noqa: BLE001 -- a raising anchor is a dropped card
        return False, f"{type(exc).__name__}: {exc}"
    if packet.get("ok") is not True:
        return False, str(packet.get("error") or packet.get("reason") or "not ok")
    records = packet.get("records") or []
    quote = ""
    if records and isinstance(records[0], dict):
        quote = str(records[0].get("quote") or "").strip()
    # A section heading with no rule text ("106.5 Protrusion Limits _____ A.") resolves
    # fine but teaches nothing, and an answer quoting it cannot make a sourced claim.
    # Require enough prose that the excerpt states a rule the reply can be graded on.
    if len(quote) < 120:
        return False, f"quote too short to teach from ({len(quote)} chars)"
    words = [word for word in re.findall(r"[A-Za-z]{3,}", quote)]
    if len(words) < 15:
        return False, f"quote is mostly numbering ({len(words)} words)"
    # (2026-08-14) "Copy exactly" must be achievable. Two excerpt shapes made models
    # fail the exact-substring gate through no fault of their own, so such cards are
    # dropped at draft time rather than shipped as impossible lessons:
    # - non-ASCII typography (curly quotes, prime marks) additionally gets mojibaked
    #   in the app->CT handoff, so what the model sees is not what the grader holds;
    # - OCR dual-id garble ("11B-404.2.9.2 404.2.9 R. Required fire doors...") reads
    #   as a typo that models predictably clean up, breaking the verbatim check
    #   (live 2026-08-14: 5 of 33 rejections were exactly this).
    if not quote.isascii():
        return False, "quote contains non-ASCII typography (not clean-copyable)"
    if re.match(r"\s*[A-Z]{0,2}\d{2,4}(?:\.\d{1,3}){1,4}\s+\d{2,4}(?:\.\d{1,3}){1,4}", quote):
        return False, "quote opens with OCR dual-id garble (not clean-copyable)"
    return True, quote[:160]


def _existing_sections() -> set[str]:
    """Sections the hand-written renewal cards already teach, so drafts do not repeat them."""
    used: set[str] = set()
    try:
        import engel_construction_renewal_curriculum as renewal

        for card in renewal.ENGEL_CONSTRUCTION_RENEWAL_CARDS_V1:
            for anchor in card.get("evidence_anchors") or []:
                if isinstance(anchor, dict) and anchor.get("section"):
                    used.add(str(anchor["section"]))
    except Exception:  # noqa: BLE001 -- absence just means nothing to exclude
        pass
    if ADOPTED.is_file():
        try:
            payload = json.loads(ADOPTED.read_text(encoding="utf-8-sig"))
            for card in payload.get("cards") or []:
                for anchor in card.get("evidence_anchors") or []:
                    if isinstance(anchor, dict) and anchor.get("section"):
                        used.add(str(anchor["section"]))
        except Exception:  # noqa: BLE001
            pass
    return used


def _history_prompt_hashes() -> set[str]:
    """Canonical hashes of every base prompt training has ever consumed.

    (2026-08-16) The used-section skip below keyed only on the CURRENT adopted
    file, and each adoption REPLACES that file - so the 2026-08-11 generation's
    sections vanished from the skip set and a fresh draft re-drew 6 of them,
    yielding cards whose prompts were 9/10 already consumed (2 of 8 novel
    hours after adoption). The prompt-history ledger is the durable authority
    the sync itself uses, so candidates are novelty-checked against it too."""
    try:
        import engel_prompt_novelty as novelty

        history = novelty.load_prompt_history()
        if history.get("ok"):
            return set(history.get("history_prompt_hashes") or [])
    except Exception:  # noqa: BLE001 -- no ledger just means nothing to exclude
        pass
    return set()


def _card_prompts_consumed(card: dict[str, Any], history_hashes: set[str]) -> int:
    """How many of this card's 10 production prompts training already consumed."""
    if not history_hashes:
        return 0
    try:
        import engel_prompt_novelty as novelty
        from run_engel_one_day_local_first_chat_training import curriculum_prompts

        prompts = curriculum_prompts(card, "aec")[0]
        return sum(
            1
            for prompt in prompts
            if novelty.canonical_base_prompt_sha256(prompt) in history_hashes
        )
    except Exception:  # noqa: BLE001 -- fail open; sync's novelty gate still decides
        return 0


def build_proposal(card_count: int = 8) -> dict[str, Any]:
    index = corpus.load_index(CORPUS_ROOT)
    grouped = _sections_by_document(index)
    already = _existing_sections()
    history_hashes = _history_prompt_hashes()

    # Round-robin across documents so a curriculum spans the library instead of
    # drilling one book, and stays deterministic for the same corpus + history.
    ordered_documents = sorted(grouped)
    cursors = {document: 0 for document in ordered_documents}
    cards: list[dict[str, Any]] = []
    dropped: list[dict[str, str]] = []
    considered = 0
    while len(cards) < card_count and ordered_documents:
        progressed = False
        for document in list(ordered_documents):
            if len(cards) >= card_count:
                break
            sections = grouped[document]
            while cursors[document] < len(sections):
                section_id = sections[cursors[document]]
                cursors[document] += 1
                if section_id in already:
                    continue
                considered += 1
                card = _card_for(document, section_id)
                ok, detail = _anchor_resolves(card)
                if not ok:
                    dropped.append(
                        {"document": document, "section": section_id, "reason": detail}
                    )
                    continue
                consumed = _card_prompts_consumed(card, history_hashes)
                if consumed:
                    dropped.append(
                        {
                            "document": document,
                            "section": section_id,
                            "reason": f"prompts already consumed by training history ({consumed}/10)",
                        }
                    )
                    continue
                card["evidence_preview"] = detail
                cards.append(card)
                already.add(section_id)
                progressed = True
                break
            else:
                ordered_documents.remove(document)
        if not progressed and not ordered_documents:
            break

    return {
        "schema": SCHEMA,
        "generated_at_utc": _utc_now(),
        "material_version": "engel_construction_corpus_generated_"
        + (cards[0]["evidence_anchors"][0]["section"] if cards else "empty"),
        "id": "construction_generated",
        "title": "Construction (corpus-generated)",
        "detail": (
            f"{len(cards)} corpus-grounded coordination hours generated from the indexed "
            "code library; every card is bound to one manifest document and one section "
            "whose excerpt resolved locally."
        ),
        "discipline": "aec",
        "source_kind": "generated_corpus_curriculum",
        "corpus_section_count": len(index.get("sections", {})),
        "sections_considered": considered,
        "card_count": len(cards),
        "cards": cards,
        "dropped": dropped[:20],
        "dropped_count": len(dropped),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", type=int, default=8, help="hours of material to draft")
    parser.add_argument(
        "--adopt",
        action="store_true",
        help="promote the proposal to the adopted curriculum file",
    )
    parser.add_argument(
        "--approval",
        default="",
        help="exact digest-bound adoption phrase printed by --summary",
    )
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    proposal = build_proposal(args.cards)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROPOSAL.write_text(json.dumps(proposal, indent=2), encoding="utf-8")

    if args.adopt:
        if len(proposal["cards"]) < args.cards:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "not enough resolvable sections to fill the request",
                        "drafted": proposal["card_count"],
                        "requested": args.cards,
                    },
                    indent=2,
                )
            )
            return 1
        try:
            curriculum_adoption.adopt_proposal(
                proposal,
                ADOPTED,
                kind="construction",
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
                    "corpus_section_count": proposal["corpus_section_count"],
                    "sections_considered": proposal["sections_considered"],
                    "card_count": proposal["card_count"],
                    "required_adoption_approval": (
                        curriculum_adoption.required_approval(
                            "construction", proposal
                        )
                    ),
                    "dropped_count": proposal["dropped_count"],
                    "cards": [
                        {
                            "document": card["documents"][0],
                            "section": card["evidence_anchors"][0]["section"],
                            "excerpt": card.get("evidence_preview", "")[:90],
                        }
                        for card in proposal["cards"]
                    ],
                    "proposal_path": str(PROPOSAL),
                },
                indent=2,
            )
        )
    else:
        print(json.dumps(proposal, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
