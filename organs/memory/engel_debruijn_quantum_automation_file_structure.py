#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
DEFAULT_SCAN_ROOT = Path(r"D:\b.WorkSpace")
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "reports" / "debruijn_quantum_file_structure"

MAX_DEPTH = 6
MAX_FILES = 5000
MAX_REPORT_RECORDS = 500

NODES = {
    "000": "core_identity_authority_safety_system_integration",
    "001": "research_intake_office_reports_understanding",
    "010": "learning_lessons_memory_candidates_self_learning",
    "011": "verifiers_guards_tests_validation_safety_checks",
    "100": "agents_skills_queens_candidate_workers_inactive_registries",
    "101": "tools_utilities_scripts_local_helpers",
    "110": "reports_receipts_codex_bridge_audit_output",
    "111": "remote_boundaries_swarm_mycelium_cluster_external_interfaces",
}

TRANSITIONS = {
    "0001": "core_to_research",
    "0010": "research_to_learning",
    "0101": "learning_to_tooling",
    "1011": "tooling_to_verifier",
    "0110": "verifier_to_report",
    "1100": "report_to_core_review",
    "1000": "agent_to_core_approval",
    "0111": "verifier_to_remote_boundary",
    "1110": "remote_boundary_to_report_only",
    "0100": "learning_to_agent_candidate",
    "1001": "agent_candidate_to_research_review",
    "1101": "report_to_tooling_review",
    "1010": "tooling_to_learning_support",
}

TRANSITIONS_BY_NODE = {
    "000": ["0001"],
    "001": ["0010"],
    "010": ["0101"],
    "011": ["0110"],
    "100": ["1000"],
    "101": ["1011"],
    "110": ["1100"],
    "111": ["1110"],
    "unknown": [],
}

CLASSIFICATION_RULES = [
    (
        1,
        "011",
        "verifier_guard_test_validation",
        ["verify", "verifier", "guard", "test", "validation", "smoke", "pytest"],
    ),
    (
        2,
        "111",
        "remote_external_swarm_mycelium_cluster_boundary",
        ["remote", "external", "swarm", "mycelium", "cluster", "android", "mobile", "queen", "provider", "network"],
    ),
    (
        3,
        "000",
        "core_identity_authority_safety_system_integration",
        ["constitution", "authority", "safety", "system_integration", "core_continuity", "identity", "protected_action"],
    ),
    (
        4,
        "010",
        "learning_lesson_memory_candidate_self_learning",
        ["learning", "lesson", "memory_candidate", "candidate_learning", "self_learning", "trusted_memory"],
    ),
    (
        5,
        "001",
        "research_intake_office_understanding",
        ["research", "intake", "understanding", "browser_queen"],
    ),
    (
        6,
        "100",
        "agent_skill_queen_candidate_worker_inactive_registry",
        ["agent", "skill", "queen", "candidate_worker", "inactive_registry", "approved_inactive"],
    ),
    (
        7,
        "101",
        "tool_script_utility_helper",
        ["tool", "tools", "script", "utility", "helper", ".py", ".ps1", ".bat", ".cmd", ".sh"],
    ),
    (
        8,
        "110",
        "report_receipt_codex_bridge_audit",
        ["report", "reports", "receipt", "codex_bridge", "audit"],
    ),
]

EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "live",
    "staging",
    "backups",
    "release",
    "releases",
    "models",
    "model",
    "cache",
    "large_binary",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

HEAVY_SUFFIXES = {
    ".exe",
    ".dll",
    ".pyd",
    ".pyc",
    ".pyo",
    ".iso",
    ".bin",
    ".gguf",
    ".safetensors",
    ".pt",
    ".pth",
    ".onnx",
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".mp4",
    ".mkv",
}

FORBIDDEN_COMMANDS = {
    "apply",
    "collapse",
    "promote",
    "trust",
    "move",
    "delete",
    "rewrite",
    "repair",
    "autorun",
    "daemon",
    "watch",
    "schedule",
    "sync",
    "provider",
    "quantum-run",
}

DISCOVERY_COMMANDS = {"help", "examples", "commands", "safety"}

SAFE_COMMANDS = [
    "help",
    "examples",
    "commands",
    "safety",
    "status",
    "automation-status",
    "scan",
    "json",
    "automation-json",
    "entanglement",
    "scan-report",
    "propose-fixes",
]

MEASUREMENT_REQUIRED = [
    "schema_check",
    "authority_check",
    "prompt_injection_guard",
    "documentation_drift_check",
    "human_review",
]

AUTOMATION_ALLOWED = ["report", "propose_candidate_fix"]
AUTOMATION_FORBIDDEN = ["apply", "move", "delete", "trust", "promote", "execute"]


@dataclass(frozen=True)
class ScanLimits:
    max_depth: int = MAX_DEPTH
    max_files: int = MAX_FILES


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp_slug() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%dT%H%M%S") + f"{now.microsecond:06d}Z"


def project_relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(root.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def is_network_path(path_text: str) -> bool:
    return path_text.startswith("\\\\") or path_text.lower().startswith(("http://", "https://", "ftp://"))


def resolve_scan_root(root_text: str | None) -> Path:
    root = Path(root_text) if root_text else DEFAULT_SCAN_ROOT
    if is_network_path(str(root)):
        raise ValueError("Network roots are not allowed in V1.")
    return root.resolve(strict=False)


def depth_from_root(path: Path, root: Path) -> int:
    try:
        return len(path.resolve(strict=False).relative_to(root.resolve(strict=False)).parts)
    except ValueError:
        return 0


def should_skip_dir(path: Path) -> bool:
    name = path.name.lower()
    if name in EXCLUDED_DIR_NAMES:
        return True
    if path.is_symlink():
        return True
    if name.endswith(".iso"):
        return True
    return False


def should_skip_file(path: Path) -> bool:
    return path.is_symlink() or path.suffix.lower() in HEAVY_SUFFIXES


def candidate_tokens(path: Path, relative: str) -> str:
    return f"{relative.lower()} {path.name.lower()} {path.suffix.lower()}"


def classify_file(path: Path, relative: str) -> dict[str, Any]:
    token_text = candidate_tokens(path, relative)
    matches: list[tuple[int, str, str, list[str]]] = []
    for priority, node, label, tokens in CLASSIFICATION_RULES:
        found = [token for token in tokens if token in token_text]
        if found:
            matches.append((priority, node, label, found))

    if not matches:
        node = "unknown"
        matched_rules: list[str] = []
        classification_reason = ["No deterministic classification rule matched."]
        candidate_nodes: list[str] = []
        selected_priority = None
    else:
        matches.sort(key=lambda item: item[0])
        remote_match = next((item for item in matches if item[1] == "111"), None)
        verifier_match = next((item for item in matches if item[1] == "011"), None)
        if remote_match and verifier_match and any(token in token_text for token in ["remote", "external", "provider", "network", "mobile", "android"]):
            selected = remote_match
            classification_reason = [
                "Remote/external boundary verifier classified as higher-risk remote boundary."
            ]
        else:
            selected = matches[0]
            classification_reason = [f"Selected highest-priority matched rule: {selected[2]}."]
        selected_priority, node, _label, found_tokens = selected
        matched_rules = [f"{item[2]}:{','.join(item[3])}" for item in matches]
        candidate_nodes = sorted({item[1] for item in matches})
        classification_reason.append("Matched tokens: " + ", ".join(found_tokens))

    quantum_state = "unknown_unclassified" if node == "unknown" else "observed_untrusted"
    trust_status = "untrusted_observed"
    if "candidate" in token_text:
        quantum_state = "candidate_superposition"
        trust_status = "untrusted_candidate"
    if "approved_inactive" in token_text:
        quantum_state = "approved_inactive"
        trust_status = "reviewed_but_inactive"

    transition_codes = TRANSITIONS_BY_NODE.get(node, [])
    transition_labels = [TRANSITIONS[code] for code in transition_codes]

    return {
        "path": relative,
        "name": path.name,
        "extension": path.suffix.lower(),
        "debruijn_node": node,
        "node_label": NODES.get(node, "unknown_unclassified"),
        "matched_rules": matched_rules,
        "classification_reason": classification_reason,
        "candidate_nodes": candidate_nodes,
        "selected_priority": selected_priority,
        "transition_codes": transition_codes,
        "transition_labels": transition_labels,
        "quantum_state": quantum_state,
        "trust_status": trust_status,
        "candidate_status": "not_promoted",
        "human_review_required": True,
        "collapse_allowed": False,
        "runtime_enabled": False,
        "safe_to_execute": False,
        "entangled_group_id": None,
        "entangled_expected_files": [],
        "entangled_found_files": [],
        "missing_entangled_files": [],
        "measurement_required": MEASUREMENT_REQUIRED,
        "automation_actions_allowed": AUTOMATION_ALLOWED,
        "automation_actions_forbidden": AUTOMATION_FORBIDDEN,
    }


def group_id_for_contract_record(record: dict[str, Any]) -> str | None:
    path = record["path"].replace("/", "\\")
    name = record["name"]
    if name.startswith("ENGEL_") and ("_CONTRACT_V1" in name or "_CONTRACT_" in name):
        stem = name
        for suffix in [".json", ".md"]:
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
        return stem
    if path.startswith("reports\\codex_bridge\\ENGEL_"):
        stem = name[:-3] if name.endswith(".md") else name
        return stem
    if name.startswith("verify_") and name.endswith(".py"):
        return name[:-3]
    return None


def build_entanglement(records: list[dict[str, Any]], root: Path) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    commands_text = safe_read_known_doc(PROJECT_ROOT / "memory" / "ENGEL_COMMANDS.md")
    continuity_text = safe_read_known_doc(PROJECT_ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md")

    for record in records:
        group_id = group_id_for_contract_record(record)
        if not group_id:
            continue
        group = groups.setdefault(
            group_id,
            {
                "entangled_group_id": group_id,
                "expected_files": [
                    "contract_json",
                    "contract_markdown",
                    "verifier_python",
                    "codex_report",
                    "command_doc_entry",
                    "core_continuity_entry",
                ],
                "found_files": [],
                "missing_files": [],
                "status": "partial_group",
                "paths": [],
            },
        )
        path = record["path"]
        group["paths"].append(path)
        if path.startswith("memory\\") and path.endswith(".json"):
            group["found_files"].append("contract_json")
        elif path.startswith("memory\\") and path.endswith(".md"):
            group["found_files"].append("contract_markdown")
        elif path.startswith("tools\\verify_") and path.endswith(".py"):
            group["found_files"].append("verifier_python")
        elif path.startswith("reports\\codex_bridge\\") and path.endswith(".md"):
            group["found_files"].append("codex_report")

    for group_id, group in groups.items():
        if group_id in commands_text:
            group["found_files"].append("command_doc_entry")
        if group_id in continuity_text:
            group["found_files"].append("core_continuity_entry")
        group["found_files"] = sorted(set(group["found_files"]))
        group["missing_files"] = sorted(set(group["expected_files"]) - set(group["found_files"]))
        if not group["missing_files"]:
            group["status"] = "complete_group"
        elif "verifier_python" in group["missing_files"]:
            group["status"] = "missing_verifier"
        elif "codex_report" in group["missing_files"]:
            group["status"] = "missing_report"
        elif "contract_json" in group["missing_files"]:
            group["status"] = "missing_contract_json"
        elif "contract_markdown" in group["missing_files"]:
            group["status"] = "missing_contract_markdown"
        elif "command_doc_entry" in group["missing_files"]:
            group["status"] = "missing_command_doc_entry"
        elif "core_continuity_entry" in group["missing_files"]:
            group["status"] = "missing_core_continuity_entry"
        else:
            group["status"] = "needs_human_review"
        group["paths"] = sorted(set(group["paths"]))

    group_by_path: dict[str, dict[str, Any]] = {}
    for group in groups.values():
        for path in group["paths"]:
            group_by_path[path] = group
    for record in records:
        group = group_by_path.get(record["path"])
        if group:
            record["entangled_group_id"] = group["entangled_group_id"]
            record["entangled_expected_files"] = group["expected_files"]
            record["entangled_found_files"] = group["found_files"]
            record["missing_entangled_files"] = group["missing_files"]

    return sorted(groups.values(), key=lambda item: item["entangled_group_id"])


def safe_read_known_doc(path: Path) -> str:
    try:
        if path.exists() and path.is_file() and path.stat().st_size <= 1024 * 1024:
            return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return ""


def scan_root(root: Path, limits: ScanLimits) -> dict[str, Any]:
    started = utc_now()
    records: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    files_seen = 0
    scan_truncated = False
    truncation_reason = ""

    if not root.exists():
        return {
            "status": "status_report_only",
            "scan_started_at": started,
            "scan_completed_at": utc_now(),
            "root": str(root),
            "root_exists": False,
            "scan_truncated": False,
            "truncation_reason": "",
            "files_seen_count": 0,
            "files_reported_count": 0,
            "files_skipped_count": 0,
            "records": [],
            "entanglement_groups": [],
            "safety": safety_summary(),
        }

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        depth = depth_from_root(current, root)
        if depth > limits.max_depth:
            dirnames[:] = []
            continue
        kept_dirs = []
        for dirname in sorted(dirnames):
            child = current / dirname
            if should_skip_dir(child):
                skipped.append({"path": project_relative(child, root), "reason": "excluded_directory_or_symlink"})
            else:
                kept_dirs.append(dirname)
        dirnames[:] = kept_dirs
        for filename in sorted(filenames):
            path = current / filename
            if files_seen >= limits.max_files:
                scan_truncated = True
                truncation_reason = "max_files_reached"
                dirnames[:] = []
                break
            files_seen += 1
            relative = project_relative(path, root)
            try:
                if should_skip_file(path):
                    skipped.append({"path": relative, "reason": "excluded_heavy_binary_or_symlink"})
                    continue
                path.stat()
            except OSError as exc:
                skipped.append({"path": relative, "reason": f"metadata_error:{type(exc).__name__}"})
                continue
            records.append(classify_file(path, relative))
        if scan_truncated:
            break

    records.sort(key=lambda item: item["path"].lower())
    groups = build_entanglement(records, root)
    skipped.sort(key=lambda item: item["path"].lower())
    return {
        "status": "status_report_only",
        "scan_started_at": started,
        "scan_completed_at": utc_now(),
        "root": str(root),
        "root_exists": True,
        "scan_limits": {"max_depth": limits.max_depth, "max_files": limits.max_files},
        "scan_truncated": scan_truncated,
        "truncation_reason": truncation_reason,
        "files_seen_count": files_seen,
        "files_reported_count": len(records),
        "files_skipped_count": len(skipped),
        "records": records,
        "entanglement_groups": groups,
        "node_counts": node_counts(records),
        "safety": safety_summary(),
    }


def node_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {node: 0 for node in list(NODES) + ["unknown"]}
    for record in records:
        counts[record["debruijn_node"]] = counts.get(record["debruijn_node"], 0) + 1
    return dict(sorted(counts.items()))


def safety_summary() -> dict[str, bool]:
    return {
        "files_moved": False,
        "files_deleted": False,
        "source_files_rewritten": False,
        "candidate_content_executed": False,
        "trusted_memory_promoted": False,
        "routes_mutated": False,
        "live_queues_mutated": False,
        "provider_api_network_quantum_service_called": False,
        "real_quantum_computation_added": False,
        "model_inference_added": False,
        "background_worker_or_startup_autorun_added": False,
        "automatic_approval_or_collapse_added": False,
    }


def status_payload() -> dict[str, Any]:
    return {
        "contract_id": "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1",
        "status": "inactive_status_layer",
        "active_workspace": str(PROJECT_ROOT),
        "runtime_enabled": False,
        "automation_enabled": True,
        "automation_scope": "manual_scan_report_propose_only",
        "quantum_computation_mode": "quantum_inspired_only_no_real_quantum_execution",
        "default_scan_root": str(DEFAULT_SCAN_ROOT),
        "output_root": str(DEFAULT_OUTPUT_ROOT),
        "node_bits": 3,
        "transition_bits": 4,
        "human_approval_required": True,
        "safety": safety_summary(),
    }


def automation_payload() -> dict[str, Any]:
    payload = status_payload()
    payload["automation_modes"] = {
        "manual_status": {"writes_files": False},
        "manual_scan": {"writes_files": False},
        "manual_scan_report": {"writes_files": True, "output_root": str(DEFAULT_OUTPUT_ROOT)},
        "candidate_proposal": {"writes_files": True, "trust_status": "untrusted_candidate", "apply_allowed": False},
        "approved_apply_future": {"enabled": False},
    }
    payload["allowed_commands"] = SAFE_COMMANDS
    payload["forbidden_commands"] = sorted(FORBIDDEN_COMMANDS)
    return payload


def discovery_help_text() -> str:
    lines = [
        "Engel De Bruijn Quantum Automation File Structure",
        "",
        "Quantum-inspired only: this is a local trust/review model, not real quantum computation.",
        "Use one surface and ask for help when unsure:",
        "  python .\\engel_debruijn_quantum_automation_file_structure.py help",
        "",
        "Safe manual commands:",
        "  help, examples, commands, safety",
        "  status, automation-status",
        "  scan --root .",
        "  json --root .",
        "  automation-json --root .",
        "  entanglement --root .",
        "  scan-report --root .",
        "  propose-fixes --root .",
        "",
        "Write behavior:",
        "  scan-report writes reports only under reports\\debruijn_quantum_file_structure\\.",
        "  propose-fixes writes untrusted candidate proposals only.",
        "  proposal apply_allowed remains false.",
        "  help, examples, commands, safety, status, scan, json, automation-json, and entanglement do not write files.",
        "",
        "Forbidden commands fail closed:",
        "  " + ", ".join(sorted(FORBIDDEN_COMMANDS)),
        "",
        "Safety boundary:",
        "  manual scan/report/propose only; no apply/move/delete/trust/promote exists in V1.",
    ]
    return "\n".join(lines)


def discovery_examples_text() -> str:
    lines = [
        "Engel De Bruijn Quantum Automation File Structure examples",
        "",
        "Status:",
        "  python .\\engel_debruijn_quantum_automation_file_structure.py status",
        "",
        "Scan current root:",
        "  python .\\engel_debruijn_quantum_automation_file_structure.py scan --root .",
        "",
        "JSON scan:",
        "  python .\\engel_debruijn_quantum_automation_file_structure.py json --root .",
        "",
        "Scan report:",
        "  python .\\engel_debruijn_quantum_automation_file_structure.py scan-report --root .",
        "  scan-report writes reports only under reports\\debruijn_quantum_file_structure\\.",
        "",
        "Entanglement report:",
        "  python .\\engel_debruijn_quantum_automation_file_structure.py entanglement --root .",
        "",
        "Candidate proposals:",
        "  python .\\engel_debruijn_quantum_automation_file_structure.py propose-fixes --root .",
        "  propose-fixes writes untrusted candidate proposals only.",
        "  proposal apply_allowed remains false.",
    ]
    return "\n".join(lines)


def discovery_commands_text() -> str:
    command_notes = [
        ("help", "show safe help; writes no files"),
        ("examples", "show examples; writes no files"),
        ("commands", "list command behavior; writes no files"),
        ("safety", "show safety boundary; writes no files"),
        ("status", "show Markdown status; writes no files"),
        ("automation-status", "show JSON automation status; writes no files"),
        ("scan --root .", "scan and print Markdown summary; writes no files"),
        ("json --root .", "scan and print bounded JSON; writes no files"),
        ("automation-json --root .", "scan and print automation JSON; writes no files"),
        ("entanglement --root .", "scan and print entanglement groups; writes no files"),
        ("scan-report --root .", "write status reports and receipt only"),
        ("propose-fixes --root .", "write untrusted candidate proposals and receipt only"),
    ]
    lines = [
        "Engel De Bruijn Quantum Automation File Structure commands",
        "",
        "Safe command list:",
    ]
    lines.extend(f"- {command}: {note}" for command, note in command_notes)
    lines.extend(
        [
            "",
            "Forbidden commands fail closed:",
            "- " + ", ".join(sorted(FORBIDDEN_COMMANDS)),
            "",
            "No apply/move/delete/trust/promote behavior exists in V1.",
        ]
    )
    return "\n".join(lines)


def discovery_safety_text() -> str:
    lines = [
        "Engel De Bruijn Quantum Automation File Structure safety",
        "",
        "This is quantum-inspired only.",
        "There is no real quantum computation.",
        "There is no quantum/provider/cloud API.",
        "There are no network/provider calls.",
        "There is no model inference.",
        "There is no background worker.",
        "There is no startup autorun.",
        "There is no file move/delete/rewrite.",
        "There is no candidate execution.",
        "There is no trusted-memory write.",
        "There is no memory promotion.",
        "There is no route/queue mutation.",
        "There is no apply/collapse/trust/promote behavior.",
        "",
        "scan-report and propose-fixes are manual report/proposal surfaces only.",
        "Candidate proposals remain untrusted_candidate with apply_allowed false.",
    ]
    return "\n".join(lines)


def markdown_status() -> str:
    payload = status_payload()
    lines = [
        "# Engel De Bruijn Quantum Automation File Structure V1",
        "",
        f"status: {payload['status']}",
        f"automation_enabled: {str(payload['automation_enabled']).lower()}",
        f"automation_scope: {payload['automation_scope']}",
        "real_quantum_execution_enabled: false",
        "network_enabled: false",
        "provider_api_enabled: false",
        "model_inference_enabled: false",
        "background_worker_enabled: false",
        "startup_autorun_enabled: false",
        "file_mutation_enabled: false",
        "trusted_memory_write_enabled: false",
        "route_mutation_enabled: false",
        "queue_mutation_enabled: false",
        "human_approval_required: true",
    ]
    return "\n".join(lines)


def scan_summary_markdown(scan: dict[str, Any]) -> str:
    lines = [
        "# Engel De Bruijn Quantum Automation File Structure Scan",
        "",
        f"status: {scan['status']}",
        f"root: {scan['root']}",
        f"root_exists: {str(scan['root_exists']).lower()}",
        f"files_seen_count: {scan['files_seen_count']}",
        f"files_reported_count: {scan['files_reported_count']}",
        f"files_skipped_count: {scan['files_skipped_count']}",
        f"scan_truncated: {str(scan['scan_truncated']).lower()}",
        f"truncation_reason: {scan['truncation_reason']}",
        "",
        "## Node Counts",
    ]
    for node, count in scan.get("node_counts", {}).items():
        label = NODES.get(node, "unknown_unclassified")
        lines.append(f"- `{node}` {label}: {count}")
    lines.extend(
        [
            "",
            "## Safety Confirmation",
            "- No files were moved.",
            "- No files were deleted.",
            "- No source files were rewritten.",
            "- No candidate content was executed.",
            "- No trusted memory was promoted.",
            "- No routes were mutated.",
            "- No live queues were mutated.",
            "- No provider/API/network/quantum service was called.",
            "- No background worker or startup autorun was added.",
            "- No automatic approval or collapse occurred.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_proposals(scan: dict[str, Any]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for group in scan.get("entanglement_groups", []):
        missing = group.get("missing_files", [])
        if not missing:
            continue
        proposal_id = "debruijn_" + group["entangled_group_id"].lower()[:80]
        proposals.append(
            {
                "proposal_id": proposal_id,
                "proposal_type": "candidate_only_structure_fix",
                "created_at": utc_now(),
                "affected_files": group.get("paths", []),
                "detected_issue": group.get("status", "needs_human_review"),
                "missing_entangled_files": missing,
                "suggested_human_action": "Review and decide whether to create or document missing entangled files.",
                "suggested_files_to_create": [],
                "required_verifiers": [
                    "verify_engel_authority_hierarchy",
                    "verify_prompt_injection_guard",
                    "verify_untrusted_content_boundaries",
                    "verify_documentation_drift",
                    "verify_engel_core_continuity_map",
                ],
                "trust_status": "untrusted_candidate",
                "apply_allowed": False,
                "human_review_required": True,
                "runtime_enabled": False,
                "source_mutation_allowed": False,
                "trusted_memory_write_allowed": False,
                "route_mutation_allowed": False,
                "queue_mutation_allowed": False,
                "candidate_execution_allowed": False,
            }
        )
    proposals.sort(key=lambda item: item["proposal_id"])
    return proposals


def ensure_output_root(path: Path = DEFAULT_OUTPUT_ROOT) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_receipt(command: str, root: Path, scan: dict[str, Any], output_files: list[Path]) -> Path:
    output_root = ensure_output_root()
    receipt = output_root / f"automation_receipt_{timestamp_slug()}.md"
    output_file_labels = [
        str(path.relative_to(PROJECT_ROOT)).replace("/", "\\")
        for path in output_files
    ]
    lines = [
        "# Engel De Bruijn Quantum Automation Receipt",
        "",
        f"command_run: `{command}`",
        f"timestamp: `{utc_now()}`",
        f"root_scanned: `{root}`",
        f"scan_limits: `{scan.get('scan_limits', {})}`",
        f"files_seen: `{scan.get('files_seen_count', 0)}`",
        f"files_classified: `{scan.get('files_reported_count', 0)}`",
        f"files_skipped: `{scan.get('files_skipped_count', 0)}`",
        f"scan_truncated: `{scan.get('scan_truncated', False)}`",
        f"output_files_written: `{output_file_labels}`",
        "",
        "## Safety Confirmation",
        "",
        "- No files were moved.",
        "- No files were deleted.",
        "- No source files were rewritten.",
        "- No candidate content was executed.",
        "- No trusted memory was promoted.",
        "- No routes were mutated.",
        "- No live queues were mutated.",
        "- No provider/API/network/quantum service was called.",
        "- No background worker or startup autorun was added.",
        "- No automatic approval or collapse occurred.",
        "",
        "final_status: status_report_only",
    ]
    receipt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return receipt


def write_scan_report(root: Path, scan: dict[str, Any]) -> dict[str, Any]:
    output_root = ensure_output_root()
    json_path = output_root / "latest_status.json"
    md_path = output_root / "latest_status.md"
    public_scan = dict(scan)
    public_scan["records"] = scan.get("records", [])[:MAX_REPORT_RECORDS]
    public_scan["records_truncated_for_report"] = len(scan.get("records", [])) > MAX_REPORT_RECORDS
    json_path.write_text(json.dumps(public_scan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(scan_summary_markdown(scan), encoding="utf-8")
    receipt_path = write_receipt("scan-report", root, scan, [json_path, md_path])
    return {
        "status": "status_report_only",
        "output_files": [str(json_path), str(md_path), str(receipt_path)],
        "safety": safety_summary(),
    }


def write_candidate_proposals(root: Path, scan: dict[str, Any]) -> dict[str, Any]:
    output_root = ensure_output_root()
    proposal_path = output_root / f"candidate_fix_proposals_{timestamp_slug()}.json"
    proposals = build_proposals(scan)
    payload = {
        "status": "untrusted_candidate",
        "created_at": utc_now(),
        "root": str(root),
        "proposal_count": len(proposals),
        "apply_allowed": False,
        "human_review_required": True,
        "proposals": proposals,
        "safety": safety_summary(),
    }
    proposal_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt_path = write_receipt("propose-fixes", root, scan, [proposal_path])
    return {
        "status": "untrusted_candidate",
        "proposal_count": len(proposals),
        "output_files": [str(proposal_path), str(receipt_path)],
        "apply_allowed": False,
        "human_review_required": True,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Engel De Bruijn quantum-inspired file structure status layer")
    parser.add_argument(
        "command",
        nargs="?",
        default="help",
        help="help, examples, commands, safety, status, automation-status, scan, json, automation-json, entanglement, scan-report, propose-fixes",
    )
    parser.add_argument("--root", default=str(DEFAULT_SCAN_ROOT), help="Local root to scan. Defaults to D:\\b.WorkSpace")
    parser.add_argument("--max-depth", type=int, default=MAX_DEPTH)
    parser.add_argument("--max-files", type=int, default=MAX_FILES)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    command = args.command.strip().lower()
    if command in FORBIDDEN_COMMANDS:
        print(
            "SAFE_ERROR: command is not implemented in V1. "
            "This layer is status/report/proposal only; no apply/collapse/promote/trust/move/delete/rewrite/repair behavior exists.",
            file=sys.stderr,
        )
        return 2

    if command == "help":
        print(discovery_help_text())
        return 0
    if command == "examples":
        print(discovery_examples_text())
        return 0
    if command == "commands":
        print(discovery_commands_text())
        return 0
    if command == "safety":
        print(discovery_safety_text())
        return 0

    if command == "status":
        print(markdown_status())
        return 0
    if command == "automation-status":
        print(json.dumps(automation_payload(), indent=2, sort_keys=True))
        return 0

    try:
        root = resolve_scan_root(args.root)
    except ValueError as exc:
        print(f"SAFE_ERROR: {exc}", file=sys.stderr)
        return 2
    limits = ScanLimits(max_depth=max(0, args.max_depth), max_files=max(1, args.max_files))

    if command in {"scan", "json", "automation-json", "entanglement", "scan-report", "propose-fixes"}:
        scan = scan_root(root, limits)
        if command == "scan":
            print(scan_summary_markdown(scan))
            return 0
        if command == "json":
            public_scan = dict(scan)
            public_scan["records"] = scan.get("records", [])[:MAX_REPORT_RECORDS]
            public_scan["records_truncated_for_stdout"] = len(scan.get("records", [])) > MAX_REPORT_RECORDS
            print(json.dumps(public_scan, indent=2, sort_keys=True))
            return 0
        if command == "automation-json":
            payload = automation_payload()
            payload["scan"] = {
                "root": scan["root"],
                "files_seen_count": scan["files_seen_count"],
                "files_reported_count": scan["files_reported_count"],
                "files_skipped_count": scan["files_skipped_count"],
                "scan_truncated": scan["scan_truncated"],
                "node_counts": scan.get("node_counts", {}),
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if command == "entanglement":
            print(json.dumps({"status": "status_report_only", "entanglement_groups": scan.get("entanglement_groups", [])}, indent=2, sort_keys=True))
            return 0
        if command == "scan-report":
            print(json.dumps(write_scan_report(root, scan), indent=2, sort_keys=True))
            return 0
        if command == "propose-fixes":
            print(json.dumps(write_candidate_proposals(root, scan), indent=2, sort_keys=True))
            return 0

    print(
        "SAFE_ERROR: unsupported command. V1 supports help, examples, commands, safety, status, automation-status, scan, json, automation-json, entanglement, scan-report, and propose-fixes only.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
