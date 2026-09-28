#!/usr/bin/env python3
"""Novel, corpus-grounded Construction Coordination renewal material.

These cards are deliberately separate from the historical construction cards. Their
prompts are generated without nonce/suffix mutation, and every card declares the exact
manifest document filenames plus deterministic evidence anchors that the visible-training
runner resolves into verified local excerpts before it opens the UI.
"""
from __future__ import annotations

from typing import Any


ENGEL_CONSTRUCTION_RENEWAL_MATERIAL_VERSION = (
    "engel_construction_corpus_renewal_v1_20260809"
)

CALDAG_2024 = "2024_caldag_1st_ptg.pdf"
DESIGNER_2025 = "2025_designer_collection_1st_printing.pdf"
DESIGNER_2026_ERRATA = "designer_updated_2026_jan_errata.pdf"


def _anchor(document: str, section: str) -> dict[str, str]:
    return {"document": document, "section": section}


# Eight independent hours x the shared ten-prompt AEC generator = one real 80-prompt
# renewal path. A model is never asked to recall a section or quote from weights: the
# runner supplies the anchored excerpts, and every unsupported extension stays open.
ENGEL_CONSTRUCTION_RENEWAL_CARDS_V1: list[dict[str, Any]] = [
    {
        "topic": "checking accessible parking scope without turning an access-aisle rule into a parking-count rule",
        "scenario": "A tenant-improvement review needs a parking requirement, and the earlier training evidence showed how a real section number can still be paired with the wrong claim. Build the answer only from the supplied Section 11B-208.2 excerpt and leave table totals or project applicability open when the packet does not show them.",
        "constraint": "Do not infer a stall count, ratio, or exception from a section title; the exact quoted words are the boundary of the sourced claim.",
        "proof": "The claim is admissible only when its ledger line names the exact 2024 CALDAG manifest filename, cites Section 11B-208.2, and copies the supplied excerpt exactly.",
        "documents": [CALDAG_2024],
        "evidence_anchors": [_anchor(CALDAG_2024, "11B-208.2")],
        "artifacts": [
            "memory/training/construction_env/extracted/2024_caldag_1st_ptg.jsonl",
            "memory/training/construction_env/CONSTRUCTION_CORPUS_MANIFEST.json",
        ],
    },
    {
        "topic": "separating a ramp's sourced running-slope rule from unprovided field geometry",
        "scenario": "A ramp review asks whether work may proceed. The packet supplies one CALDAG slope section, but it supplies no field rise, run, landing, cross-slope, or alteration determination. State only the rule the excerpt proves and assign every project measurement to an open owner.",
        "constraint": "A code ratio is not proof that the installed ramp meets it; code text and field verification must remain separate ledger records.",
        "proof": "A verified line binds 2024_caldag_1st_ptg.pdf and Section 11B-405.2 to its exact excerpt; measurements remain open until a named field record closes them.",
        "documents": [CALDAG_2024],
        "evidence_anchors": [_anchor(CALDAG_2024, "11B-405.2")],
        "artifacts": [
            "memory/training/construction_env/extracted/2024_caldag_1st_ptg.jsonl",
            "memory/training/construction_env/CONSTRUCTION_SECTION_INDEX.json",
        ],
    },
    {
        "topic": "using the occupant-load section without inventing a project occupant count",
        "scenario": "An egress coordination question needs the governing occupant-load principle, while floor area, function, and project calculations are absent. Use the supplied designer-collection excerpt for the code claim and keep the numerical load and egress conclusion open.",
        "constraint": "Never convert a general occupant-load provision into a project result without the inputs and calculation that the excerpt does not contain.",
        "proof": "The sourced line names 2025_designer_collection_1st_printing.pdf, Section 1004.1, and its exact supplied excerpt; the project count has a named confirmation owner.",
        "documents": [DESIGNER_2025],
        "evidence_anchors": [_anchor(DESIGNER_2025, "1004.1")],
        "artifacts": [
            "memory/training/construction_env/extracted/2025_designer_collection_1st_printing.jsonl",
            "memory/training/construction_env/CONSTRUCTION_CORPUS_MANIFEST.json",
        ],
    },
    {
        "topic": "distinguishing the building official's determination authority from an approval that has not happened",
        "scenario": "A coordination note asks whether an interpretation is approved. The evidence packet contains Section 104.2 from the 2025 designer collection, but no project correspondence or AHJ decision. Explain the authority the excerpt states without claiming the project received approval.",
        "constraint": "A code provision describing authority is not a receipt showing that authority exercised it on this project.",
        "proof": "The verified fact binds the exact 2025 designer manifest filename and Section 104.2; the project-specific interpretation remains an open item owned by the AHJ record.",
        "documents": [DESIGNER_2025],
        "evidence_anchors": [_anchor(DESIGNER_2025, "104.2")],
        "artifacts": [
            "memory/training/construction_env/extracted/2025_designer_collection_1st_printing.jsonl",
            "memory/training/construction_env/CONSTRUCTION_SECTION_INDEX.json",
        ],
    },
    {
        "topic": "comparing impact-load language across the 2025 printing and 2026 errata as two separately bound claims",
        "scenario": "A structural review must check whether the errata changed Section 1607.12. Write one ledger line per printing from the two supplied excerpts; never let a quote from one printing verify a claim attributed to the other.",
        "constraint": "Even when the section id and visible wording match, each edition keeps its own document identity and evidence line; a delta is reported only if the supplied text proves one.",
        "proof": "Verification requires two independently bound Source document lines for Section 1607.12, one for each exact manifest filename, followed by an honest comparison result.",
        "documents": [DESIGNER_2025, DESIGNER_2026_ERRATA],
        "evidence_anchors": [
            _anchor(DESIGNER_2025, "1607.12"),
            _anchor(DESIGNER_2026_ERRATA, "1607.12"),
        ],
        "artifacts": [
            "memory/training/construction_env/extracted/2025_designer_collection_1st_printing.jsonl",
            "memory/training/construction_env/extracted/designer_updated_2026_jan_errata.jsonl",
        ],
    },
    {
        "topic": "checking occupant-load wording across two editions without silently choosing the governing printing",
        "scenario": "The project folder contains both the first printing and January errata. Compare the supplied Section 1004.1 excerpts line by line, then keep the governing-edition decision open because project adoption information is not in the corpus packet.",
        "constraint": "Text comparison and edition applicability are different decisions; identical excerpts do not prove which edition the jurisdiction adopted.",
        "proof": "Each Section 1004.1 claim carries its own exact filename and quote, while the adoption question names a confirmation owner and proof record.",
        "documents": [DESIGNER_2025, DESIGNER_2026_ERRATA],
        "evidence_anchors": [
            _anchor(DESIGNER_2025, "1004.1"),
            _anchor(DESIGNER_2026_ERRATA, "1004.1"),
        ],
        "artifacts": [
            "memory/training/construction_env/extracted/2025_designer_collection_1st_printing.jsonl",
            "memory/training/construction_env/extracted/designer_updated_2026_jan_errata.jsonl",
        ],
    },
    {
        "topic": "cross-checking accessible-parking language in CALDAG and the integrated designer collection",
        "scenario": "A review sees Section 11B-208.2 in both sources. Compare only the excerpts supplied for each volume, preserve each volume's identity, and do not combine their wording into a third synthetic rule.",
        "constraint": "A shared section number is not shared provenance; every claim and quote must remain attached to the document where it was found.",
        "proof": "The grader must verify two Source document lines with the same section id but different exact manifest filenames without cross-document quote substitution.",
        "documents": [CALDAG_2024, DESIGNER_2025],
        "evidence_anchors": [
            _anchor(CALDAG_2024, "11B-208.2"),
            _anchor(DESIGNER_2025, "11B-208.2"),
        ],
        "artifacts": [
            "memory/training/construction_env/extracted/2024_caldag_1st_ptg.jsonl",
            "memory/training/construction_env/extracted/2025_designer_collection_1st_printing.jsonl",
        ],
    },
    {
        "topic": "building one bounded coordination ledger from accessibility and occupant-load evidence",
        "scenario": "A mezzanine concept raises both ramp-access and egress questions. Use the supplied CALDAG ramp excerpt and designer-collection occupant-load excerpt as two separate sourced facts, then place geometry, calculated occupant load, structural capacity, edition adoption, and AHJ acceptance under open owners.",
        "constraint": "Cross-discipline coordination may join decisions in one ledger, but it may never merge document scope or promote an unprovided project input into a sourced fact.",
        "proof": "The closeout has one exact-document claim for Section 11B-405.2, one for Section 1004.1, and no project conclusion beyond those supplied excerpts.",
        "documents": [CALDAG_2024, DESIGNER_2025],
        "evidence_anchors": [
            _anchor(CALDAG_2024, "11B-405.2"),
            _anchor(DESIGNER_2025, "1004.1"),
        ],
        "artifacts": [
            "memory/training/construction_env/extracted/2024_caldag_1st_ptg.jsonl",
            "memory/training/construction_env/extracted/2025_designer_collection_1st_printing.jsonl",
            "memory/training/construction_env/CONSTRUCTION_CORPUS_MANIFEST.json",
        ],
    },
]


def validate_renewal_cards() -> list[str]:
    """Pure structural validation used by sync and behavioral verifiers."""
    problems: list[str] = []
    if len(ENGEL_CONSTRUCTION_RENEWAL_CARDS_V1) != 8:
        problems.append("construction renewal must contain exactly eight hourly cards")
    topics: set[str] = set()
    for index, card in enumerate(ENGEL_CONSTRUCTION_RENEWAL_CARDS_V1, start=1):
        topic = str(card.get("topic") or "").strip()
        if not topic or topic in topics:
            problems.append(f"card {index} has an empty or duplicate topic")
        topics.add(topic)
        documents = card.get("documents")
        anchors = card.get("evidence_anchors")
        if not isinstance(documents, list) or not documents:
            problems.append(f"card {index} has no exact source documents")
            continue
        if not isinstance(anchors, list) or not anchors:
            problems.append(f"card {index} has no evidence anchors")
            continue
        anchored_documents = {
            str(item.get("document") or "")
            for item in anchors
            if isinstance(item, dict)
        }
        if set(documents) != anchored_documents:
            problems.append(f"card {index} documents and evidence anchors do not match")
        if any(
            not str(item.get("section") or "").strip()
            for item in anchors
            if isinstance(item, dict)
        ):
            problems.append(f"card {index} has an empty evidence section")
    return problems

