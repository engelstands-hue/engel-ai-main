#!/usr/bin/env python3
"""Verify Engel's prompt-to-patch provenance ledger and cycle wiring."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile

import engel_prompt_patch_provenance as provenance


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    checks: list[str] = []
    with tempfile.TemporaryDirectory(prefix="engel-provenance-") as temp_text:
        root = Path(temp_text)
        ledger = root / "reports" / "self_upgrade" / "provenance" / "ledger.jsonl"
        entries = ledger.parent / "entries"
        issue = write_json(root / "reports" / "issue.json", {"issue_id": "issue-1"})
        review = write_json(
            root / "reports" / "review.json",
            {"returned_worker_count": 4},
        )
        candidate_path = write_json(
            root / "reports" / "candidate.json",
            {"candidate_id": "candidate-1"},
        )
        patch = write_json(
            root / "reports" / "patch.json",
            {"operations": [{"file": "tools/example.py"}]},
        )
        request = {
            "source": "owner_ui",
            "symptom": "The bounded fixture returns the wrong value.",
            "diagnosis": "The return literal is stale.",
            "patch_plan": "Replace the exact stale literal.",
            "lesson": "Verify the exact replacement before deployment.",
            "files_to_change": ["tools/example.py"],
        }
        candidate = {
            "candidate_id": "candidate-1",
            "risk_level": "low",
            "required_verifiers": ["tools/verify_example.py"],
            "distributed_review_worker_ids": [
                "android_worker_alpha",
                "android_worker_beta",
                "android_worker_gamma",
                "DESKTOP-UE5A6GG",
            ],
        }
        operations = [
            {
                "file": "tools/example.py",
                "old_text": "return False",
                "new_text": "return True",
            }
        ]
        first = provenance.record_cycle_provenance(
            cycle_id="cycle-1",
            actor="owner_joshua",
            request=request,
            issue_path=issue,
            distributed_review_path=review,
            candidate_path=candidate_path,
            patch_path=patch,
            candidate=candidate,
            operations=operations,
            root=root,
            ledger_path=ledger,
            entry_root=entries,
        )
        second = provenance.record_cycle_provenance(
            cycle_id="cycle-2",
            actor="owner_joshua",
            request={**request, "symptom": "A second bounded fixture is stale."},
            issue_path=issue,
            distributed_review_path=review,
            candidate_path=candidate_path,
            patch_path=patch,
            candidate={**candidate, "candidate_id": "candidate-2"},
            operations=operations,
            root=root,
            ledger_path=ledger,
            entry_root=entries,
        )
        verified = provenance.verify_ledger(
            root=root,
            ledger_path=ledger,
            entry_root=entries,
        )
        require(verified.get("ok") is True, f"valid ledger failed: {verified}")
        require(
            second.get("previous_entry_sha256") == first.get("entry_sha256"),
            "ledger entries are not hash chained",
        )
        require(
            first.get("secret_material_stored") is False
            and first.get("source_mutation_performed") is False,
            "provenance receipt claimed unsafe behavior",
        )
        checks.append("two immutable entries form a valid append-only hash chain")

        fixture_root = root / "runtime" / "temp" / "cycle_verify_12345"
        fixture_issue = write_json(
            fixture_root / "reports" / "issue.json",
            {"issue_id": "fixture-issue"},
        )
        fixture_review = write_json(
            fixture_root / "reports" / "review.json",
            {"returned_worker_count": 4},
        )
        fixture_candidate = write_json(
            fixture_root / "reports" / "candidate.json",
            {"candidate_id": "fixture-candidate"},
        )
        fixture_patch = write_json(
            fixture_root / "reports" / "patch.json",
            {"operations": [{"file": "tools/example.py"}]},
        )
        provenance.record_cycle_provenance(
            cycle_id="cycle-fixture",
            actor="verifier_fixture",
            request={**request, "symptom": "An ephemeral verifier fixture."},
            issue_path=fixture_issue,
            distributed_review_path=fixture_review,
            candidate_path=fixture_candidate,
            patch_path=fixture_patch,
            candidate={**candidate, "candidate_id": "fixture-candidate"},
            operations=operations,
            root=root,
            ledger_path=ledger,
            entry_root=entries,
        )
        shutil.rmtree(fixture_root)
        fixture_verified = provenance.verify_ledger(
            root=root,
            ledger_path=ledger,
            entry_root=entries,
        )
        require(
            fixture_verified.get("ok") is True
            and fixture_verified.get("production_entry_count") == 2
            and fixture_verified.get("fixture_entry_count") == 1,
            f"ephemeral fixture classification failed: {fixture_verified}",
        )
        checks.append(
            "deleted cycle-verifier references remain fixtures, not production proof"
        )

        original_issue = issue.read_text(encoding="utf-8")
        issue.write_text('{"issue_id":"tampered"}\n', encoding="utf-8")
        tampered = provenance.verify_ledger(
            root=root,
            ledger_path=ledger,
            entry_root=entries,
        )
        require(
            tampered.get("ok") is False
            and any("reference issue hash mismatch" in error for error in tampered["errors"]),
            "referenced evidence tampering was not detected",
        )
        issue.write_text(original_issue, encoding="utf-8")
        checks.append("referenced receipt tampering fails verification")

        original_patch = patch.read_bytes()
        patch.unlink()
        missing_production = provenance.verify_ledger(
            root=root,
            ledger_path=ledger,
            entry_root=entries,
        )
        require(
            missing_production.get("ok") is False
            and any(
                "reference patch is missing" in error
                for error in missing_production["errors"]
            ),
            "missing production evidence was treated as an ephemeral fixture",
        )
        patch.write_bytes(original_patch)
        checks.append("missing production evidence still fails verification")

        try:
            provenance.record_cycle_provenance(
                cycle_id="cycle-secret",
                actor="owner_joshua",
                request={
                    **request,
                    "symptom": "api_key=abcdefghijklmnopqrstuvwx",
                },
                issue_path=issue,
                distributed_review_path=review,
                candidate_path=candidate_path,
                patch_path=patch,
                candidate=candidate,
                operations=operations,
                root=root,
                ledger_path=ledger,
                entry_root=entries,
            )
        except provenance.ProvenanceError:
            secret_blocked = True
        else:
            secret_blocked = False
        require(secret_blocked, "secret-like prompt material entered the ledger")
        checks.append("secret-like prompt material is rejected before append")

        outside = Path(tempfile.gettempdir()) / "engel-provenance-outside.json"
        outside.write_text("{}\n", encoding="utf-8")
        try:
            provenance.confined_reference(outside, root=root)
        except provenance.ProvenanceError:
            outside_blocked = True
        else:
            outside_blocked = False
        finally:
            outside.unlink(missing_ok=True)
        require(outside_blocked, "evidence outside Engel root was accepted")
        checks.append("evidence references are confined to the Engel root")

    cycle_source = (
        Path(__file__).resolve().parent / "engel_conical_self_upgrade_cycle.py"
    ).read_text(encoding="utf-8")
    require(
        "record_cycle_provenance" in cycle_source
        and '"provenance"' in cycle_source
        and "failed_at_provenance" in cycle_source,
        "governed cycle does not fail closed through the provenance ledger",
    )
    checks.append("governed cycle requires provenance before quorum")
    cycle_verifier_source = (
        Path(__file__).resolve().parent
        / "verify_engel_conical_self_upgrade_cycle.py"
    ).read_text(encoding="utf-8")
    require(
        '"system_report_root": system.REPORT_ROOT' in cycle_verifier_source
        and "system.REPORT_ROOT = fx_reports" in cycle_verifier_source
        and 'system.REPORT_ROOT = saved["system_report_root"]'
        in cycle_verifier_source,
        "cycle verifier does not isolate and restore the system report root",
    )
    checks.append("cycle verifier isolates provenance fixtures from production")
    print(
        json.dumps(
            {
                "schema": "ENGEL_PROMPT_PATCH_PROVENANCE_VERIFIER_V1",
                "goal_id": provenance.GOAL_ID,
                "ok": True,
                "check_count": len(checks),
                "checks": checks,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
