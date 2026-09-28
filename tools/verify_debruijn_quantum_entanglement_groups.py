#!/usr/bin/env python3
from __future__ import annotations

import json
import py_compile
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PASS_MARKER = "DEBRUIJN_QUANTUM_ENTANGLEMENT_GROUP_VERIFICATION_PASS"

CONTRACT_JSON = ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1.md"
CORE_SOURCE = ROOT / "engel_debruijn_quantum_automation_file_structure.py"
CORE_VERIFIER = ROOT / "tools" / "verify_engel_debruijn_quantum_automation_file_structure.py"
CORE_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_V1.md"
COMMAND_DISCOVERY_REPORT = (
    ROOT
    / "reports"
    / "codex_bridge"
    / "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_COMMAND_DISCOVERY_V1.md"
)
COMMANDS_MD = ROOT / "memory" / "ENGEL_COMMANDS.md"
ROUTE_METADATA = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
HELPER_SOURCE = ROOT / "engel_debruijn_quantum_structure_status.py"
HELPER_VERIFIER = ROOT / "tools" / "verify_debruijn_quantum_structure_status_helper.py"
HELPER_REPORT = (
    ROOT / "reports" / "codex_bridge" / "ENGEL_DEBRUIJN_QUANTUM_STRUCTURE_BACKEND_STATUS_HELPER_V1.md"
)
BACKEND_COMMAND_VERIFIER = ROOT / "tools" / "verify_debruijn_quantum_backend_status_command.py"
BACKEND_COMMAND_REPORT = (
    ROOT / "reports" / "codex_bridge" / "ENGEL_DEBRUIJN_QUANTUM_BACKEND_STATUS_COMMAND_V1.md"
)
BACKEND_COMMAND_SMOKE = (
    ROOT / "reports" / "codex_bridge" / "ENGEL_DEBRUIJN_QUANTUM_BACKEND_STATUS_COMMAND_SOURCE_SMOKE_V1.md"
)
CANDIDATE_PROPOSAL_VERIFIER = ROOT / "tools" / "verify_debruijn_quantum_candidate_proposals.py"
CANDIDATE_PROPOSAL_REPORT = (
    ROOT / "reports" / "codex_bridge" / "ENGEL_DEBRUIJN_QUANTUM_CANDIDATE_PROPOSAL_VERIFIER_V1.md"
)
OUTPUT_ROOT = ROOT / "reports" / "debruijn_quantum_file_structure"

FALSE_CONTRACT_FLAGS = [
    "network_enabled",
    "provider_api_enabled",
    "quantum_provider_enabled",
    "real_quantum_execution_enabled",
    "model_inference_enabled",
    "background_worker_enabled",
    "startup_autorun_enabled",
    "file_mutation_enabled",
    "source_rewrite_enabled",
    "file_move_enabled",
    "file_delete_enabled",
    "trusted_memory_write_enabled",
    "route_mutation_enabled",
    "queue_mutation_enabled",
    "candidate_execution_enabled",
    "auto_collapse_enabled",
    "auto_approval_enabled",
    "apply_command_enabled",
]

ACTIVE_SOURCE_FILES = [
    CORE_SOURCE,
    HELPER_SOURCE,
    CORE_VERIFIER,
    HELPER_VERIFIER,
    BACKEND_COMMAND_VERIFIER,
    CANDIDATE_PROPOSAL_VERIFIER,
]

UNSAFE_ACTIVE_PATTERNS = [
    "apply_candidate_proposal",
    "apply_proposals",
    "trust_candidate_proposal",
    "promote_candidate_proposal",
    "execute_proposal_content",
    "run_proposal",
    "source_mutation_from_proposal",
    "route_mutation_from_proposal",
    "queue_mutation_from_proposal",
    "trusted_memory_from_proposal",
    "move_files_from_proposal",
    "delete_files_from_proposal",
    "rewrite_files_from_proposal",
    "provider_from_proposal",
    "network_from_proposal",
    "model_from_proposal",
    "quantum_from_proposal",
    "companion_card",
    "standalone_viewer",
    "create_ui",
]

SAFE_LINE_MARKERS = [
    "forbidden",
    "not allowed",
    "disallowed",
    "disabled",
    "false",
    "must not",
    "does not",
    "do not",
    "no ",
    "never",
    "_off",
    "_enabled",
    "fail closed",
    "fail-closed",
    "verifier",
    "pattern",
    "marker",
]


@dataclass
class GroupResult:
    group_id: str
    status: str
    risk_level: str
    required_files_present: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    optional_files_present: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class Verifier:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.review_required: list[str] = []
        self.groups: list[GroupResult] = []

    def line(self, level: str, message: str) -> None:
        print(f"{level} {message}")

    def fail(self, message: str) -> None:
        self.failures.append(message)
        self.line("FAIL", message)

    def review(self, message: str) -> None:
        self.review_required.append(message)
        self.line("REVIEW_REQUIRED", message)

    def pass_line(self, message: str) -> None:
        self.line("PASS", message)

    def info(self, message: str) -> None:
        self.line("INFO", message)


def rel(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def add_group(
    verifier: Verifier,
    group_id: str,
    required: list[Path],
    *,
    optional: list[Path] | None = None,
    condition: bool = True,
    skip_note: str = "",
    required_failure_is_blocker: bool = False,
) -> GroupResult:
    optional = optional or []
    if not condition:
        result = GroupResult(
            group_id=group_id,
            status="SKIP",
            risk_level="MEDIUM",
            notes=[skip_note or "Optional/future group not active."],
        )
        verifier.groups.append(result)
        verifier.info(f"{group_id} SKIP {result.notes[0]}")
        return result

    present = [rel(path) for path in required if path.exists()]
    missing = [rel(path) for path in required if not path.exists()]
    optional_present = [rel(path) for path in optional if path.exists()]
    if missing:
        risk = "BLOCKER" if required_failure_is_blocker else "HIGH"
        result = GroupResult(
            group_id=group_id,
            status="FAIL",
            risk_level=risk,
            required_files_present=present,
            missing_files=missing,
            optional_files_present=optional_present,
            notes=["Missing required files for active/required group."],
        )
        verifier.groups.append(result)
        message = f"{group_id} missing required files: {missing}"
        if required_failure_is_blocker:
            verifier.fail(message)
        else:
            verifier.fail(message)
        return result

    result = GroupResult(
        group_id=group_id,
        status="PASS",
        risk_level="LOW",
        required_files_present=present,
        optional_files_present=optional_present,
        notes=["Required files present."],
    )
    verifier.groups.append(result)
    verifier.pass_line(f"{group_id} required files present")
    return result


def check_groups(verifier: Verifier) -> None:
    add_group(
        verifier,
        "CORE_CONTRACT_GROUP",
        [CONTRACT_JSON, CONTRACT_MD, CORE_REPORT, CORE_SOURCE, CORE_VERIFIER],
        required_failure_is_blocker=True,
    )
    add_group(
        verifier,
        "COMMAND_DISCOVERY_GROUP",
        [COMMAND_DISCOVERY_REPORT, CORE_SOURCE, CORE_VERIFIER, COMMANDS_MD],
        condition=COMMAND_DISCOVERY_REPORT.exists(),
        skip_note="Command discovery report absent; discovery group is not active.",
    )
    add_group(
        verifier,
        "BACKEND_STATUS_HELPER_GROUP",
        [HELPER_SOURCE, HELPER_VERIFIER, HELPER_REPORT],
        condition=HELPER_SOURCE.exists() or HELPER_REPORT.exists() or HELPER_VERIFIER.exists(),
        skip_note="Backend status helper files absent; helper group is not active.",
    )
    backend_command_active = BACKEND_COMMAND_REPORT.exists() or BACKEND_COMMAND_VERIFIER.exists()
    backend_optional = [ROUTE_METADATA] if route_metadata_mentions_backend_command() else []
    add_group(
        verifier,
        "BACKEND_STATUS_COMMAND_GROUP",
        [BACKEND_COMMAND_VERIFIER, BACKEND_COMMAND_REPORT, BACKEND_COMMAND_SMOKE, ROOT / "engel_app.py", COMMANDS_MD],
        optional=backend_optional,
        condition=backend_command_active,
        skip_note="Backend status command verifier/report absent; command group remains future or incomplete evidence.",
    )
    add_group(
        verifier,
        "CANDIDATE_PROPOSAL_VERIFIER_GROUP",
        [CANDIDATE_PROPOSAL_VERIFIER, CANDIDATE_PROPOSAL_REPORT],
        optional=sorted(OUTPUT_ROOT.glob("candidate_fix_proposals_*.json")) if OUTPUT_ROOT.exists() else [],
        condition=CANDIDATE_PROPOSAL_VERIFIER.exists() or CANDIDATE_PROPOSAL_REPORT.exists(),
        skip_note="Candidate proposal verifier/report absent; proposal verifier group is not active.",
    )

    generated_present: list[str] = []
    if OUTPUT_ROOT.exists():
        for pattern in [
            ".gitkeep",
            "latest_status.json",
            "latest_status.md",
            "automation_receipt_*.md",
            "candidate_fix_proposals_*.json",
        ]:
            matches = sorted(OUTPUT_ROOT.glob(pattern))
            if matches:
                generated_present.extend(rel(path) for path in matches)
    result = GroupResult(
        group_id="GENERATED_OUTPUT_GROUP",
        status="PASS",
        risk_level="LOW",
        optional_files_present=generated_present,
        notes=["Generated outputs are optional and not required for source integrity."],
    )
    verifier.groups.append(result)
    verifier.pass_line(f"GENERATED_OUTPUT_GROUP optional files present={len(generated_present)}")


def route_metadata_mentions_backend_command() -> bool:
    if not ROUTE_METADATA.exists():
        return False
    try:
        text = read_text(ROUTE_METADATA).lower()
    except OSError:
        return False
    return "debruijn quantum status" in text or "debruijn_quantum_status" in text


def check_contract(verifier: Verifier) -> None:
    if not CONTRACT_JSON.exists():
        verifier.fail(f"contract alignment missing {rel(CONTRACT_JSON)}")
        return
    try:
        contract = json.loads(read_text(CONTRACT_JSON))
    except json.JSONDecodeError as exc:
        verifier.fail(f"contract JSON invalid line={exc.lineno} column={exc.colno}")
        return

    if contract.get("contract_id") != "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1":
        verifier.fail("contract_id mismatch")
    if contract.get("status") not in {"contract_only", "planning_only", "inactive_status_layer", "implemented"}:
        verifier.fail(f"contract status is not recognized: {contract.get('status')!r}")

    for key in FALSE_CONTRACT_FLAGS:
        if key in contract and contract.get(key) is not False:
            verifier.fail(f"contract flag {key} must be false when present")

    automation_modes = contract.get("automation_modes", {})
    candidate_proposal = automation_modes.get("candidate_proposal", {}) if isinstance(automation_modes, dict) else {}
    if candidate_proposal:
        if candidate_proposal.get("trust_status") != "untrusted_candidate":
            verifier.fail("candidate proposal automation mode is not untrusted_candidate")
        if candidate_proposal.get("apply_allowed") is not False:
            verifier.fail("candidate proposal automation mode apply_allowed must be false")

    verifier.pass_line("contract alignment result")


def contains_all(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return all(term.lower() in lower for term in terms)


def check_source_markers(verifier: Verifier) -> None:
    if CORE_SOURCE.exists():
        text = read_text(CORE_SOURCE)
        marker_sets = {
            "core quantum-inspired marker": ["quantum-inspired"],
            "core status/report/proposal boundary": ["status/report/proposal"],
            "core fail-closed forbidden command boundary": ["fail", "closed", "forbidden"],
            "core no apply/collapse/promote/trust/move/delete/rewrite": [
                "no apply/move/delete/trust/promote",
            ],
            "core no provider/network/model/real quantum": ["no quantum/provider/cloud api"],
        }
        for name, terms in marker_sets.items():
            if not contains_all(text, terms):
                verifier.review(f"{name} not clearly found in {rel(CORE_SOURCE)}")
        verifier.pass_line("core source marker checks completed")
    else:
        verifier.fail(f"missing core source {rel(CORE_SOURCE)}")

    if HELPER_SOURCE.exists():
        text = read_text(HELPER_SOURCE).lower()
        helper_markers = {
            "backend_only": "backend_only",
            "existing_reports_only": "existing_reports_only",
            "no ui": "ui_enabled",
            "no scan": "no scan",
            "no writes": "no files were written",
        }
        for label, term in helper_markers.items():
            if term not in text:
                verifier.review(f"helper marker {label!r} not clearly found in {rel(HELPER_SOURCE)}")
        verifier.pass_line("backend helper marker checks completed")

    if BACKEND_COMMAND_VERIFIER.exists():
        text = read_text(BACKEND_COMMAND_VERIFIER).lower()
        for term in ["backend", "status", "no scan", "no write", "no ui"]:
            if term not in text:
                verifier.review(f"backend command verifier marker {term!r} not clearly found")
        verifier.pass_line("backend command verifier marker checks completed")
    else:
        verifier.info("backend command verifier marker checks skipped; verifier file missing")


def line_is_safe_reference(line: str, is_verifier: bool) -> bool:
    lowered = line.lower()
    if is_verifier:
        return True
    return any(marker in lowered for marker in SAFE_LINE_MARKERS)


def active_source_scan(verifier: Verifier) -> None:
    scanned = 0
    likely_active_findings = 0
    for path in ACTIVE_SOURCE_FILES:
        if not path.exists():
            verifier.info(f"optional active source missing {rel(path)}")
            continue
        try:
            lines = read_text(path).splitlines()
        except OSError as exc:
            verifier.fail(f"cannot read active source {rel(path)}: {exc}")
            continue
        scanned += 1
        is_verifier = path.name.startswith("verify_")
        for line_number, line in enumerate(lines, start=1):
            lowered = line.lower()
            for pattern in UNSAFE_ACTIVE_PATTERNS:
                if pattern in lowered and not line_is_safe_reference(line, is_verifier):
                    likely_active_findings += 1
                    verifier.review(f"{rel(path)}:{line_number} potential active behavior pattern {pattern}")
    if likely_active_findings:
        verifier.fail(f"active source scan found likely active unsafe behavior count={likely_active_findings}")
    else:
        verifier.pass_line(f"active source scan result scanned={scanned}")


def compile_verifier_sources(verifier: Verifier) -> None:
    for path in [CORE_VERIFIER, HELPER_VERIFIER, CANDIDATE_PROPOSAL_VERIFIER]:
        if not path.exists():
            verifier.info(f"compile skip missing {rel(path)}")
            continue
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            verifier.fail(f"{rel(path)} py_compile failed: {exc}")
    verifier.pass_line("available verifier source compile checks completed")


def print_group_summaries(verifier: Verifier) -> None:
    print("ENTANGLEMENT_GROUP_SUMMARIES")
    for group in verifier.groups:
        print(
            json.dumps(
                {
                    "group_id": group.group_id,
                    "status": group.status,
                    "risk_level": group.risk_level,
                    "required_files_present": group.required_files_present,
                    "missing_files": group.missing_files,
                    "optional_files_present_count": len(group.optional_files_present),
                    "optional_files_present": group.optional_files_present[:25],
                    "notes": group.notes,
                },
                sort_keys=True,
            )
        )


def main() -> int:
    verifier = Verifier()
    print("ENGEL_DEBRUIJN_QUANTUM_ENTANGLEMENT_GROUP_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: structure verification only; no scan, repair, apply, trust, movement, provider, model, or mutation")

    check_groups(verifier)
    check_contract(verifier)
    check_source_markers(verifier)
    active_source_scan(verifier)
    compile_verifier_sources(verifier)
    print_group_summaries(verifier)

    if verifier.review_required:
        verifier.info(f"review_required findings={len(verifier.review_required)}")
    if verifier.failures:
        verifier.fail(f"failures={len(verifier.failures)}")
        return 1

    verifier.pass_line("group verification results")
    verifier.pass_line("generated output group status")
    verifier.pass_line("contract alignment result")
    verifier.pass_line("source marker result")
    verifier.pass_line("active source scan result")
    verifier.pass_line("safety preserved")
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
