#!/usr/bin/env python3
"""Focused hostile checks for generated AEC asset-sync corpus binding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import sync_engel_training_assets as sync


ROOT = Path(__file__).resolve().parents[1]
CORPUS_SHA256 = "A" * 64
OTHER_SHA256 = "B" * 64
SUBSTANTIVE_QUOTE = (
    "This verified construction provision establishes a bounded requirement "
    "whose exact document, section, page, dimensions, exceptions, and related "
    "coordination conditions remain available for independent review before "
    "any sourced conclusion is accepted into the generated training material."
)
checks: list[tuple[str, bool, object]] = []


def check(name: str, condition: bool, detail: object) -> None:
    checks.append((name, bool(condition), detail))
    print(f"{'PASS' if condition else 'FAIL'} {name}: {detail}")


def cards() -> list[dict[str, Any]]:
    return [
        {
            "topic": f"Verified AEC topic {number}",
            "scenario": "Coordinate the cited condition without inventing facts.",
            "constraint": "Use only the supplied exact local evidence.",
            "proof": "Return the document, Section, exact quote, and open items.",
            "documents": [f"Code Volume {number}.pdf"],
            "evidence_anchors": [
                {
                    "document": f"Code Volume {number}.pdf",
                    "section": f"{number}01.1",
                }
            ],
        }
        for number in range(1, 9)
    ]


def bundle(_root: Path) -> dict[str, Any]:
    return {
        "ok": True,
        "bundle_sha256": CORPUS_SHA256,
        "blockers": [],
    }


def packet(
    anchors: list[dict[str, Any]],
    corpus_root: Path | None = None,
) -> dict[str, Any]:
    del corpus_root
    if any(anchor.get("section") == "MISSING" for anchor in anchors):
        return {
            "ok": False,
            "corpus_bundle_sha256": CORPUS_SHA256,
            "documents": [],
            "records": [],
            "blockers": ["hostile anchor is absent from the verified corpus"],
        }
    records = [
        {
            "document": anchor["document"],
            "section": anchor["section"],
            "page": ordinal,
            "quote": SUBSTANTIVE_QUOTE,
        }
        for ordinal, anchor in enumerate(anchors, start=1)
    ]
    return {
        "ok": True,
        "corpus_bundle_sha256": CORPUS_SHA256,
        "documents": list(
            dict.fromkeys(record["document"] for record in records)
        ),
        "records": records,
        "blockers": [],
    }


def main() -> int:
    original_bundle = sync.construction_corpus.verify_corpus_bundle
    original_packet = sync.construction_corpus.build_prompt_evidence_context
    try:
        sync.construction_corpus.verify_corpus_bundle = bundle
        sync.construction_corpus.build_prompt_evidence_context = packet

        valid_cards = cards()
        problem, binding = sync._generated_aec_cards_grounding(
            valid_cards,
            corpus_root=Path("mock-corpus"),
        )
        check(
            "every_card_is_rederived_and_bound_to_one_verified_bundle",
            problem is None
            and binding.get("verified") is True
            and binding.get("corpus_bundle_sha256") == CORPUS_SHA256
            and binding.get("card_count") == 8
            and binding.get("anchor_count") == 8
            and len(binding.get("documents") or []) == 8,
            {"problem": problem, "binding": binding},
        )

        bad_anchor_cards = cards()
        bad_anchor_cards[3]["evidence_anchors"][0]["section"] = "MISSING"
        bad_problem, _ = sync._generated_aec_cards_grounding(
            bad_anchor_cards,
            corpus_root=Path("mock-corpus"),
        )
        check(
            "hostile_bad_anchor_makes_asset_integrity_false",
            bool(bad_problem)
            and sync.generated_curricula_integrity_ok([str(bad_problem)]) is False,
            bad_problem,
        )

        scope_cards = cards()
        scope_cards[0]["documents"] = ["Different Volume.pdf"]
        scope_problem, _ = sync._generated_aec_cards_grounding(
            scope_cards,
            corpus_root=Path("mock-corpus"),
        )
        check(
            "declared_documents_must_exactly_cover_anchor_documents",
            bool(scope_problem) and "document scope" in str(scope_problem),
            scope_problem,
        )

        def incomplete_packet(
            anchors: list[dict[str, Any]],
            corpus_root: Path | None = None,
        ) -> dict[str, Any]:
            result = packet(anchors, corpus_root)
            result["records"] = []
            return result

        sync.construction_corpus.build_prompt_evidence_context = incomplete_packet
        coverage_problem, _ = sync._generated_aec_cards_grounding(
            cards(),
            corpus_root=Path("mock-corpus"),
        )
        check(
            "verified_packet_must_cover_every_declared_anchor",
            bool(coverage_problem) and "coverage is incomplete" in str(coverage_problem),
            coverage_problem,
        )

        def short_quote_packet(
            anchors: list[dict[str, Any]],
            corpus_root: Path | None = None,
        ) -> dict[str, Any]:
            result = packet(anchors, corpus_root)
            for record in result["records"]:
                record["quote"] = "short quote"
            return result

        sync.construction_corpus.build_prompt_evidence_context = short_quote_packet
        quote_problem, _ = sync._generated_aec_cards_grounding(
            cards(),
            corpus_root=Path("mock-corpus"),
        )
        check(
            "every_verified_anchor_requires_a_substantive_quote",
            bool(quote_problem) and "substantive quote" in str(quote_problem),
            quote_problem,
        )

        def wrong_bundle_packet(
            anchors: list[dict[str, Any]],
            corpus_root: Path | None = None,
        ) -> dict[str, Any]:
            result = packet(anchors, corpus_root)
            result["corpus_bundle_sha256"] = OTHER_SHA256
            return result

        sync.construction_corpus.build_prompt_evidence_context = wrong_bundle_packet
        digest_problem, _ = sync._generated_aec_cards_grounding(
            cards(),
            corpus_root=Path("mock-corpus"),
        )
        check(
            "card_evidence_and_bundle_digests_must_match",
            bool(digest_problem) and "different corpus bundle" in str(digest_problem),
            digest_problem,
        )

        sync.construction_corpus.build_prompt_evidence_context = packet
        template = sync.build_template(
            cards=valid_cards,
            version="generated-aec-test-v1",
            template_id="engel_generated_aec_test",
            discipline="aec",
            generated_grounding=binding,
        )
        index_fields = sync.generated_grounding_metadata(
            {"generated_grounding": binding}
        )
        check(
            "template_and_index_metadata_carry_the_exact_corpus_digest",
            template.get("generated_grounding") == binding
            and template.get("generated_corpus_bundle_sha256") == CORPUS_SHA256
            and index_fields.get("generated_grounding") == binding
            and index_fields.get("generated_corpus_bundle_sha256")
            == CORPUS_SHA256,
            {
                "template_digest": template.get(
                    "generated_corpus_bundle_sha256"
                ),
                "index_digest": index_fields.get(
                    "generated_corpus_bundle_sha256"
                ),
            },
        )

        source = (
            ROOT / "tools" / "sync_engel_training_assets.py"
        ).read_text(encoding="utf-8")
        check(
            "index_and_manifest_share_the_fail_closed_grounding_contract",
            source.count(
                "generated_curricula_integrity_ok(generated_curriculum_problems)"
            )
            == 2
            and '"generated_grounding": dict(' in source
            and '"generated_corpus_bundle_sha256": str(' in source,
            "curricula index, template receipt, and asset manifest are digest-bound",
        )
    finally:
        sync.construction_corpus.verify_corpus_bundle = original_bundle
        sync.construction_corpus.build_prompt_evidence_context = original_packet

    passed = sum(1 for _name, ok, _detail in checks if ok)
    print(f"SUMMARY {passed}/{len(checks)} checks passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
