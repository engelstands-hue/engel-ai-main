#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CORE_STABILIZATION_CHECKPOINT_V1.md"
CORE_MAP_MD = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md"
CORE_MAP_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
RESEARCH_INTAKE_CONTRACT = ROOT / "memory" / "ENGEL_RESEARCH_INTAKE_QUEUE_CONTRACT_V1.md"
MEMORY_CANDIDATE_CONTRACT = ROOT / "memory" / "ENGEL_MEMORY_CANDIDATE_WORKFLOW_CONTRACT_V1.md"
AUTHORITY = "Josh > Guardian > Engel/runtime"


REQUIRED_VERIFIERS = {
    "Code Companion verifier": ROOT / "tools" / "verify_engel_code_companion.py",
    "README / Manifest proposal verifier": ROOT / "tools" / "verify_code_companion_readme_manifest_proposals.py",
    "Research Intake verifier": ROOT / "tools" / "verify_research_intake_queue.py",
    "Research Summary Proposal verifier": ROOT / "tools" / "verify_research_summary_proposals.py",
    "Research Lesson Bridge verifier": ROOT / "tools" / "verify_research_lesson_bridge.py",
    "Research Lesson Review verifier": ROOT / "tools" / "verify_research_lesson_review.py",
    "Memory Candidate verifier": ROOT / "tools" / "verify_memory_candidate_proposals.py",
    "Core Continuity Map verifier": ROOT / "tools" / "verify_engel_core_continuity_map.py",
    "Browser Queen contract verifier": ROOT / "tools" / "verify_browser_queen_contract.py",
    "Auto-browser static review verifier": ROOT / "tools" / "verify_auto_browser_review.py",
    "Untrusted Content Guard verifier": ROOT / "tools" / "verify_untrusted_content_guard.py",
    "Prompt Injection Guard verifier": ROOT / "tools" / "verify_prompt_injection_guard.py",
    "Authority hierarchy verifier": ROOT / "tools" / "verify_authority_hierarchy.py",
    "AI Body status verifier": ROOT / "tools" / "verify_engel_ai_body_status.py",
    "Living Systems documentation drift verifier": ROOT / "tools" / "verify_living_systems_documentation_drift.py",
}


OPTIONAL_VERIFIERS = {
    "Humanizer static review verifier": ROOT / "tools" / "verify_humanizer_review.py",
    "Human Signal Guard verifier": ROOT / "tools" / "verify_human_signal_guard.py",
}


class CheckFailure(Exception):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing file: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def check_required_files() -> None:
    for path in (REPORT, CORE_MAP_MD, CORE_MAP_JSON, RESEARCH_INTAKE_CONTRACT, MEMORY_CANDIDATE_CONTRACT):
        _require(path.exists(), "required checkpoint file missing: " + str(path.relative_to(ROOT)))
        _require(path.is_file(), "required checkpoint path is not a file: " + str(path.relative_to(ROOT)))
    for label, path in REQUIRED_VERIFIERS.items():
        _require(path.exists() and path.is_file(), label + " missing: " + str(path.relative_to(ROOT)))


def check_core_continuity_map() -> None:
    markdown = _read(CORE_MAP_MD)
    data = json.loads(_read(CORE_MAP_JSON))
    for needle in [
        "Core Continuity Map ≠ Trusted Memory",
        "Research Intake ≠ Trusted Memory",
        "Research Summary Proposal",
        "Lesson Candidate",
        "Research Lesson Candidate",
        "Trusted Memory Candidate",
        "Browser Queen feeds Research Intake",
        "untrusted data, not instruction",
        AUTHORITY,
    ]:
        _require(needle in markdown, "Core Continuity Map missing text: " + needle)
    for key in [
        "memory_candidate_proposals_count",
        "memory_candidate_workflow_status",
        "memory_candidate_trusted_memory_status",
        "trusted_memory_candidate_boundary",
        "browser_queen_runtime_status",
        "products_count",
        "code_examples_count",
        "research_intake_receipts_count",
        "research_intake_summaries_count",
        "research_lesson_candidates_count",
        "research_lesson_reviews_count",
        "lesson_candidates_count",
        "lesson_reviews_count",
        "verifier_count",
    ]:
        _require(key in data, "Core Continuity JSON missing key: " + key)
    _require(data.get("memory_candidate_workflow_status") == "PROPOSAL_ONLY / NOT_TRUSTED_MEMORY", "memory candidate workflow status mismatch")
    _require(data.get("memory_candidate_trusted_memory_status") == "BLOCKED / NOT_PERFORMED", "memory candidate trusted memory status mismatch")
    _require(data.get("trusted_memory_candidate_boundary") == "Trusted Memory Candidate ≠ Trusted Memory", "trusted memory candidate boundary mismatch")
    _require(data.get("browser_queen_runtime_status") == "DISABLED", "Browser Queen runtime should be DISABLED")
    _require(data.get("authority") == AUTHORITY, "authority mismatch in continuity JSON")


def check_checkpoint_report() -> None:
    text = _read(REPORT)
    required = [
        "Status COMPLETE",
        "Active root",
        "Git status before work",
        "Git status after verification",
        "Current Core spine",
        "Products / Research / Browser Queen future inputs",
        "Research Intake / Code Companion",
        "Research Summary Proposal / Product Improve Proposal",
        "Lesson Candidate",
        "Lesson Review",
        "Memory Candidate Proposal",
        "still NOT trusted memory",
        AUTHORITY,
        "no trusted memory write occurred",
        "Browser Queen remains disabled",
        "no API/network/package/autonomy behavior added",
        "Core Continuity Map ≠ Trusted Memory",
        "Research Intake ≠ Trusted Memory",
        "Research Summary Proposal ≠ Trusted Memory",
        "Lesson Candidate ≠ Trusted Memory",
        "Research Lesson Candidate ≠ Trusted Memory",
        "Trusted Memory Candidate ≠ Trusted Memory",
        "Documents/pages/products/reports/receipts are data, not instruction",
        "Embedded approval tokens do not count",
        "Packaging skipped",
        "Next recommended package refresh step",
        "Engel Core Stabilization Checkpoint V1 is verification/report-only",
    ]
    for needle in required:
        _require(needle in text, "checkpoint report missing text: " + needle)
    for label, path in OPTIONAL_VERIFIERS.items():
        if path.exists():
            _require(label in text and "PRESENT" in text, "present optional verifier not documented: " + label)
        else:
            _require(label in text and "NOT PRESENT" in text, "missing optional verifier not documented: " + label)


def main() -> int:
    try:
        check_required_files()
        check_core_continuity_map()
        check_checkpoint_report()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel Core Stabilization Checkpoint verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
