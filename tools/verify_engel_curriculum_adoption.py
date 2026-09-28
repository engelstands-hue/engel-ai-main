#!/usr/bin/env python3
"""Behavioral checks for hash-bound generated-curriculum adoption."""

from __future__ import annotations

import json
import shutil
import stat
import tempfile
from pathlib import Path

import engel_curriculum_adoption as adoption


ROOT = Path(__file__).resolve().parents[1]
checks: list[tuple[str, bool, object]] = []


def check(name: str, condition: bool, detail: object) -> None:
    checks.append((name, bool(condition), detail))
    print(f"{'PASS' if condition else 'FAIL'} {name}: {detail}")


def main() -> int:
    temp = Path(tempfile.mkdtemp(prefix="engel_curriculum_adoption_", dir=ROOT / "runtime" / "temp"))
    try:
        adopted_path = temp / "ENGEL_TEST_GENERATED_CARDS_ADOPTED.json"
        proposal = {
            "schema": "engel_test_generated_cards_v1",
            "generated_at_utc": "2026-08-11T00:00:00Z",
            "id": "test_generated",
            "discipline": "engineering",
            "material_version": "test-v1",
            "card_count": 8,
            "cards": [
                {
                    "topic": f"topic {number}",
                    "scenario": "a grounded scenario",
                    "constraint": "a bounded constraint",
                    "proof": "a named proof",
                }
                for number in range(1, 9)
            ],
        }
        phrase = adoption.required_approval("test", proposal)
        check(
            "approval_phrase_is_digest_bound_and_deterministic",
            phrase == adoption.required_approval("test", dict(proposal))
            and phrase.startswith("APPROVE_ENGEL_ADOPT_TEST_"),
            phrase,
        )
        try:
            adoption.adopt_proposal(
                proposal, adopted_path, kind="test", approval=""
            )
            wrong_refused = False
        except ValueError as exc:
            wrong_refused = phrase in str(exc)
        check(
            "bare_adopt_is_refused_before_write",
            wrong_refused and not adopted_path.exists(),
            {"refused": wrong_refused, "exists": adopted_path.exists()},
        )
        adopted, receipt_path = adoption.adopt_proposal(
            proposal, adopted_path, kind="test", approval=phrase
        )
        verified, receipt, problems = adoption.verify_adoption(
            adopted_path, expected_kind="test"
        )
        check(
            "approved_adoption_has_an_immutable_receipt",
            verified == adopted
            and receipt is not None
            and not problems
            and receipt_path.is_file()
            and not bool(receipt_path.stat().st_mode & stat.S_IWUSR),
            {"receipt": str(receipt_path), "problems": problems},
        )
        check(
            "receipt_does_not_overclaim_signer_identity",
            receipt.get("authorization_semantics")
            == "explicit_digest_confirmation_not_cryptographic_identity",
            receipt.get("authorization_semantics"),
        )
        adopted_again, receipt_again = adoption.adopt_proposal(
            {**proposal, "generated_at_utc": "2026-08-12T00:00:00Z"},
            adopted_path,
            kind="test",
            approval=phrase,
        )
        check(
            "semantic_no_op_adoption_reuses_exact_receipt",
            adopted_again == adopted and receipt_again == receipt_path,
            receipt_again,
        )

        original_adopted = adopted_path.read_bytes()
        mutated = dict(json.loads(original_adopted))
        mutated["cards"][0]["topic"] = "silently replaced topic"
        adopted_path.write_text(json.dumps(mutated), encoding="utf-8")
        _, _, mutation_problems = adoption.verify_adoption(
            adopted_path, expected_kind="test"
        )
        check(
            "adopted_content_mutation_is_rejected",
            any("SHA-256" in problem for problem in mutation_problems),
            mutation_problems,
        )
        adopted_path.write_bytes(original_adopted)

        receipt_original = receipt_path.read_bytes()
        receipt_path.chmod(0o666)
        receipt_path.write_bytes(receipt_original + b" ")
        _, _, receipt_problems = adoption.verify_adoption(
            adopted_path, expected_kind="test"
        )
        check(
            "mutable_or_rewritten_receipt_is_rejected",
            any("read-only" in problem or "invalid" in problem for problem in receipt_problems),
            receipt_problems,
        )
        receipt_path.write_bytes(receipt_original)
        receipt_path.chmod(0o444)

        orphan = temp / "ORPHAN_ADOPTED.json"
        orphan.write_text(
            json.dumps(
                {
                    **proposal,
                    "adoption": "adopted",
                    "adopted_at_utc": "2026-08-11T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )
        _, _, orphan_problems = adoption.verify_adoption(
            orphan, expected_kind="test"
        )
        check(
            "self_asserted_adopted_json_is_not_authority",
            bool(orphan_problems),
            orphan_problems,
        )

        generator_sources = [
            (ROOT / "tools" / "engel_construction_corpus_card_generator.py").read_text(
                encoding="utf-8"
            ),
            (ROOT / "tools" / "engel_communication_renewal_generator.py").read_text(
                encoding="utf-8"
            ),
        ]
        check(
            "both_generators_require_the_shared_approval_contract",
            all(
                '"--approval"' in source
                and "curriculum_adoption.adopt_proposal(" in source
                for source in generator_sources
            ),
            "construction + communication",
        )
        sync_source = (
            ROOT / "tools" / "sync_engel_training_assets.py"
        ).read_text(encoding="utf-8")
        check(
            "asset_sync_authenticates_before_overlay",
            "curriculum_adoption.verify_adoption(" in sync_source
            and "if payload is None or adoption_problems:" in sync_source,
            "unreceipted or drifted adoption is excluded from canonical slots",
        )
    finally:
        for path in sorted(temp.rglob("*"), reverse=True):
            try:
                if path.is_file():
                    path.chmod(0o666)
            except OSError:
                pass
        shutil.rmtree(temp, ignore_errors=True)

    passed = sum(1 for _, ok, _ in checks if ok)
    print(f"SUMMARY {passed}/{len(checks)} checks passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
