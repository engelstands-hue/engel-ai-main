"""Static verifier for ENGEL_CUSTOMER_READY_PROMOTION_V1.

Checks that the promotion pass:
  - has its own contract JSON
  - lists the expected approved IDs
  - records Josh's approval phrase
  - keeps every still-disabled flag at false
  - produced the trusted memory + knowledge files
  - those trusted files contain every promoted ID
  - each promoted entry carries the trusted footer with the approval phrase
  - the candidate source files still exist (audit trail preserved)
  - the candidate source files carry the AUDIT BANNER stamp
  - the promotion report exists and says what was promoted

Does NOT touch runtime, networking, models, packages, or anything
outside D:\\b.WorkSpace.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # D:\b.WorkSpace
MEMORY = ROOT / "memory"
REPORTS = ROOT / "reports" / "codex_bridge"

CONTRACT_PATH = MEMORY / "ENGEL_CUSTOMER_READY_PROMOTION_CONTRACT_V1.json"
TRUSTED_MEMORY_PATH = MEMORY / "ENGEL_CUSTOMER_READY_TRUSTED_MEMORY_V1.md"
TRUSTED_KNOWLEDGE_PATH = MEMORY / "ENGEL_CUSTOMER_READY_TRUSTED_KNOWLEDGE_V1.md"
CANDIDATE_MEMORY_PATH = MEMORY / "ENGEL_CUSTOMER_READY_MEMORY_CANDIDATES_V1.md"
CANDIDATE_KNOWLEDGE_PATH = MEMORY / "ENGEL_CUSTOMER_READY_KNOWLEDGE_BASE_CANDIDATES_V1.md"
REPORT_PATH = REPORTS / "ENGEL_CUSTOMER_READY_PROMOTION_V1.md"

EXPECTED_MEMORY_IDS = [f"M-{i:02d}" for i in range(1, 13)]
EXPECTED_KNOWLEDGE_IDS = [f"K-{i:02d}" for i in range(1, 14)]

EXPECTED_APPROVAL_PHRASE = "Josh approves promotion of M-01..M-12, K-01..K-13 on 2026-05-18"
EXPECTED_APPROVAL_DATE = "2026-05-18"
EXPECTED_APPROVER = "Josh"

CONTRACT_FALSE_FLAGS = [
    "runtime_enabled",
    "inference_enabled",
    "training_enabled",
    "fine_tuning_enabled",
    "provider_calls_enabled",
    "autonomous_learning_enabled",
    "mobile_runtime_enabled",
    "remote_queen_runtime_enabled",
    "queue_mutation_enabled",
    "route_mutation_enabled",
    "source_mutation_enabled",
    "package_install_enabled",
    "exe_build_enabled",
    "network_enabled",
]


class Result:
    def __init__(self) -> None:
        self.passes: list[str] = []
        self.fails: list[str] = []

    def ok(self, msg: str) -> None:
        self.passes.append(msg)

    def fail(self, msg: str) -> None:
        self.fails.append(msg)

    def _ascii(self, s: str) -> str:
        return s.encode("ascii", "replace").decode("ascii")

    def report(self) -> int:
        print("=" * 72)
        print("ENGEL_CUSTOMER_READY_PROMOTION_V1 -- verifier")
        print("=" * 72)
        for line in self.passes:
            print(f"  PASS  {self._ascii(line)}")
        for line in self.fails:
            print(f"  FAIL  {self._ascii(line)}")
        print("-" * 72)
        print(f"Total: {len(self.passes)} pass | {len(self.fails)} fail")
        if self.fails:
            print("RESULT: FAIL")
            return 1
        print("RESULT: PASS")
        return 0


def check_files_exist(result: Result) -> dict:
    paths = {
        "contract": CONTRACT_PATH,
        "trusted_memory": TRUSTED_MEMORY_PATH,
        "trusted_knowledge": TRUSTED_KNOWLEDGE_PATH,
        "candidate_memory": CANDIDATE_MEMORY_PATH,
        "candidate_knowledge": CANDIDATE_KNOWLEDGE_PATH,
        "report": REPORT_PATH,
    }
    for key, path in paths.items():
        if path.exists() and path.is_file():
            result.ok(f"file exists: {path.relative_to(ROOT)}")
        else:
            result.fail(f"file MISSING: {path}")
    return paths


def check_contract(result: Result) -> None:
    if not CONTRACT_PATH.exists():
        return
    try:
        data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        result.fail(f"promotion contract JSON does not parse: {exc}")
        return
    result.ok("promotion contract JSON parses cleanly")

    if data.get("status") != "promotion_pass":
        result.fail(f"promotion contract status must be 'promotion_pass', got {data.get('status')!r}")
    else:
        result.ok("promotion contract status = promotion_pass")

    approval = data.get("human_approval", {})
    if approval.get("approver") != EXPECTED_APPROVER:
        result.fail(f"contract approver must be 'Josh', got {approval.get('approver')!r}")
    else:
        result.ok(f"contract approver = {EXPECTED_APPROVER}")

    if approval.get("approval_date") != EXPECTED_APPROVAL_DATE:
        result.fail(f"contract approval_date must be '{EXPECTED_APPROVAL_DATE}', got {approval.get('approval_date')!r}")
    else:
        result.ok(f"contract approval_date = {EXPECTED_APPROVAL_DATE}")

    if approval.get("approval_phrase") != EXPECTED_APPROVAL_PHRASE:
        result.fail("contract approval_phrase does not match expected phrase")
    else:
        result.ok("contract approval_phrase matches expected phrase")

    promoted = data.get("promoted_entries", {})
    if promoted.get("memory_candidates") != EXPECTED_MEMORY_IDS:
        result.fail(f"contract memory_candidates list does not match expected {EXPECTED_MEMORY_IDS}")
    else:
        result.ok("contract memory_candidates list correct (M-01..M-12)")

    if promoted.get("knowledge_candidates") != EXPECTED_KNOWLEDGE_IDS:
        result.fail(f"contract knowledge_candidates list does not match expected {EXPECTED_KNOWLEDGE_IDS}")
    else:
        result.ok("contract knowledge_candidates list correct (K-01..K-13)")

    still_disabled = data.get("still_disabled_for_this_pass", {})
    for flag in CONTRACT_FALSE_FLAGS:
        if still_disabled.get(flag) is False:
            result.ok(f"still_disabled flag {flag} = false")
        else:
            result.fail(f"still_disabled flag {flag} must be false, got {still_disabled.get(flag)!r}")


def check_trusted_file(result: Result, path: Path, expected_ids: list[str], label: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    for eid in expected_ids:
        # The section heading is "## M-XX ·" or "## K-XX ·" — match start of line.
        pattern = rf"^##\s+{re.escape(eid)}\s+"
        if re.search(pattern, text, flags=re.MULTILINE):
            result.ok(f"{label}: {eid} section present")
        else:
            result.fail(f"{label}: {eid} section MISSING")
        # Each section must contain a trusted footer with the approval phrase.
        footer_block_pattern = (
            rf"##\s+{re.escape(eid)}\s+.*?"
            r"trust_status:\s*trusted.*?"
            rf"promoted_id:\s*{re.escape(eid)}.*?"
            rf"approved_by:\s*{re.escape(EXPECTED_APPROVER)}.*?"
            rf"approved_at:\s*{re.escape(EXPECTED_APPROVAL_DATE)}.*?"
            r"approval_phrase:\s*"
            + re.escape(EXPECTED_APPROVAL_PHRASE)
        )
        if re.search(footer_block_pattern, text, flags=re.DOTALL):
            result.ok(f"{label}: {eid} footer has trusted + approver + date + phrase")
        else:
            result.fail(f"{label}: {eid} footer missing one of (trusted / approver / date / phrase)")


def check_candidate_audit_banner(result: Result, path: Path, label: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if "AUDIT BANNER" in text and EXPECTED_APPROVAL_PHRASE in text:
        result.ok(f"{label}: audit banner + approval phrase present at top")
    else:
        result.fail(f"{label}: audit banner OR approval phrase missing")


def check_report(result: Result) -> None:
    if not REPORT_PATH.exists():
        return
    text = REPORT_PATH.read_text(encoding="utf-8")
    if EXPECTED_APPROVAL_PHRASE in text:
        result.ok("report contains the approval phrase")
    else:
        result.fail("report missing the approval phrase")
    if "M-01" in text and "M-12" in text and "K-01" in text and "K-13" in text:
        result.ok("report references the full promoted ID range")
    else:
        result.fail("report does not reference the full promoted ID range (M-01..M-12, K-01..K-13)")
    if "no runtime" in text.lower() or "still disabled" in text.lower() or "no model" in text.lower():
        result.ok("report explicitly states no runtime / no model side-effect happened")
    else:
        result.fail("report must state that no runtime / no model side-effect occurred")


def main() -> int:
    result = Result()
    check_files_exist(result)
    check_contract(result)
    check_trusted_file(result, TRUSTED_MEMORY_PATH, EXPECTED_MEMORY_IDS, "trusted-memory")
    check_trusted_file(result, TRUSTED_KNOWLEDGE_PATH, EXPECTED_KNOWLEDGE_IDS, "trusted-knowledge")
    check_candidate_audit_banner(result, CANDIDATE_MEMORY_PATH, "candidate-memory")
    check_candidate_audit_banner(result, CANDIDATE_KNOWLEDGE_PATH, "candidate-knowledge")
    check_report(result)
    return result.report()


if __name__ == "__main__":
    sys.exit(main())
