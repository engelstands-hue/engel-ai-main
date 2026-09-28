#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import py_compile
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()

PLAN_JSON = ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_UI_OR_COMPANION_PLAN_V1.json"
PLAN_MD = ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_UI_OR_COMPANION_PLAN_V1.md"
PLAN_REPORT = (
    ROOT
    / "reports"
    / "codex_bridge"
    / "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_UI_OR_COMPANION_PLAN_V1.md"
)

PASS_MARKER = "DEBRUIJN_QUANTUM_FILE_STRUCTURE_UI_PLAN_VERIFICATION_PASS"

REQUIRED_VALUES = {
    "contract_id": "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_UI_OR_COMPANION_PLAN_V1",
    "status": "planning_only",
    "active_workspace": r"D:\b.WorkSpace\Engel App",
    "ui_implemented_now": False,
    "companion_modified_now": False,
    "standalone_viewer_created_now": False,
    "manual_scan_button_enabled_now": False,
    "apply_button_allowed": False,
    "auto_repair_allowed": False,
    "real_quantum_allowed": False,
    "provider_api_allowed": False,
    "network_allowed": False,
    "model_inference_allowed": False,
    "background_worker_allowed": False,
    "startup_autorun_allowed": False,
    "trusted_memory_write_allowed": False,
    "route_mutation_allowed": False,
    "queue_mutation_allowed": False,
}

REQUIRED_KEYS = [
    "ui_placement_options",
    "recommended_first_ui_surface",
    "first_ui_behavior",
    "allowed_future_ui_actions",
    "forbidden_ui_actions",
    "ui_data_model",
    "future_verifier",
    "future_implementation_sequence",
    "stop_conditions",
    "recommended_next_slice",
    "safety_preserved",
]

PLACEMENT_REQUIREMENTS = [
    ["companion", "card", "read only"],
    ["companion", "tab"],
    ["standalone", "local", "viewer"],
    ["command only", "for now"],
]

ALLOWED_RECOMMENDATIONS = {
    "companion compact read only card",
    "standalone local viewer",
    "command only for now",
    "standalone local viewer first",
    "standalone local read only viewer",
    "standalone local read only viewer first",
    "standalone local viewer first",
}

FORBIDDEN_RECOMMENDATION_TERMS = [
    "apply focused",
    "auto repair ui",
    "startup watcher ui",
    "background scanner ui",
    "trusted memory promotion ui",
]

FIRST_UI_TRUE_FIELDS = [
    "read_latest_status_json_if_present",
    "honest_empty_state_if_no_scan_report",
    "show_contract_status",
    "show_automation_mode_manual_only",
    "show_quantum_mode_quantum_inspired_only",
    "show_node_map_summary",
    "show_latest_file_counts",
    "show_scan_truncated_status",
    "show_latest_receipt_path",
    "show_latest_candidate_proposal_path_and_count",
    "show_incomplete_entanglement_group_count",
]

REQUIRED_SAFETY_LABELS = [
    "Real quantum OFF",
    "Provider/API OFF",
    "Network OFF",
    "Model inference OFF",
    "Background worker OFF",
    "Startup autorun OFF",
    "Apply OFF",
    "File move/delete/rewrite OFF",
    "Trusted memory write OFF",
    "Route/queue mutation OFF",
]

FIRST_UI_ACTIONS = [
    "Refresh Status",
    "Open latest status report",
    "Open latest receipt",
    "Open latest candidate proposal file",
    "Copy safe command examples",
    "Run safe help command",
]

LATER_MANUAL_ACTIONS = [
    "Run scan",
    "Run scan-report",
    "Run entanglement",
    "Run propose-fixes",
]

MANUAL_ACTION_RULES = [
    "explicit user-clicked",
    "bounded local",
    "write only allowed report/proposal outputs",
    "show receipt",
    "no background loops",
    "no startup autorun",
    "no apply/collapse/promote/trust/move/delete/rewrite",
]

FORBIDDEN_UI_ACTIONS = [
    "Apply Fix",
    "Auto Repair",
    "Collapse",
    "Trust",
    "Promote",
    "Move Files",
    "Delete Files",
    "Rewrite Source",
    "Execute Candidate",
    "Run at Startup",
    "Watch Folder",
    "Auto Scan Loop",
    "Provider/Network Scan",
    "Quantum Run",
    "Train Model",
    "Write Trusted Memory",
    "Mutate Route",
    "Mutate Queue",
]

READ_ONLY_SOURCES = [
    r"memory\ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1.json",
    r"reports\debruijn_quantum_file_structure\latest_status.json",
    r"reports\debruijn_quantum_file_structure\latest_status.md",
    r"reports\debruijn_quantum_file_structure\automation_receipt_*.md",
    r"reports\debruijn_quantum_file_structure\candidate_fix_proposals_*.json",
]

UI_DATA_FIELDS = [
    "contract_status",
    "automation_scope",
    "quantum_mode",
    "node_counts",
    "transition_counts",
    "file_count",
    "unknown_count",
    "candidate_count",
    "report_count",
    "proposal_count",
    "incomplete_entanglement_count",
    "latest_status_path",
    "latest_receipt_path",
    "latest_proposal_path",
    "scan_truncated",
    "safety_flags",
]

FUTURE_VERIFIER_TERMS = [
    "read-only/status-first",
    "no apply/move/delete/trust/promote controls",
    "no background worker/startup autorun",
    "no provider/network/model/quantum imports",
    "reads only approved status/report/proposal files",
    "manual command buttons",
    "safe allowlisted commands",
    r"reports\debruijn_quantum_file_structure",
    "De Bruijn verifier passes",
    "untrusted-content verifier passes",
    "De Bruijn import boundary verifier passes",
]

FUTURE_SEQUENCE_TERMS = [
    "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_UI_PLAN_VERIFIER_V1",
    "ENGEL_DEBRUIJN_QUANTUM_STRUCTURE_STATUS_HELPER_V1",
    "ENGEL_DEBRUIJN_QUANTUM_STRUCTURE_VIEWER_V1",
    "ENGEL_DEBRUIJN_QUANTUM_STRUCTURE_UI_SOURCE_SMOKE_V1",
    "ENGEL_DEBRUIJN_QUANTUM_STRUCTURE_MANUAL_ACTION_BUTTONS_PLAN_V1",
]

ACTIVE_SOURCE_SUFFIXES = {".py", ".ps1", ".bat", ".cmd", ".sh", ".psm1", ".spec", ".json"}
BINARY_SUFFIXES = {
    ".exe",
    ".dll",
    ".pyd",
    ".pyc",
    ".pyo",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".zip",
    ".7z",
    ".pdf",
}
EXCLUDE_DIRS = {
    ".git",
    "build",
    "dist",
    "live",
    "backups",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "reports",
    "memory",
}

ACTIVE_SOURCE_PATTERNS = [
    ("debruijn_ui_apply_button", re.compile(r"de\s*bruijn.*ui.*apply\s*button|apply\s*button.*de\s*bruijn", re.I)),
    ("quantum_apply", re.compile(r"\bquantum[_ -]?apply\b", re.I)),
    ("auto_repair", re.compile(r"\bauto[_ -]?repair\b", re.I)),
    ("auto_scan_loop", re.compile(r"\bauto[_ -]?scan[_ -]?loop\b", re.I)),
    ("watch_folder", re.compile(r"\bwatch[_ -]?folder\b", re.I)),
    ("run_at_startup", re.compile(r"\brun[_ -]?at[_ -]?startup\b", re.I)),
    (
        "trusted_memory_write_from_debruijn_ui",
        re.compile(r"de\s*bruijn.*ui.*trusted[_ -]?memory[_ -]?write|trusted[_ -]?memory[_ -]?write.*de\s*bruijn.*ui", re.I),
    ),
    (
        "route_mutation_from_debruijn_ui",
        re.compile(r"de\s*bruijn.*ui.*route[_ -]?mutation|route[_ -]?mutation.*de\s*bruijn.*ui", re.I),
    ),
    (
        "queue_mutation_from_debruijn_ui",
        re.compile(r"de\s*bruijn.*ui.*queue[_ -]?mutation|queue[_ -]?mutation.*de\s*bruijn.*ui", re.I),
    ),
    (
        "provider_network_scan_from_debruijn_ui",
        re.compile(r"de\s*bruijn.*ui.*provider/network scan|provider/network scan.*de\s*bruijn.*ui", re.I),
    ),
    ("quantum_run_from_ui", re.compile(r"\bquantum[_ -]?run\b.*\bui\b|\bui\b.*\bquantum[_ -]?run\b", re.I)),
    ("move_files_from_ui", re.compile(r"\bmove[_ -]?files\b.*\bui\b|\bui\b.*\bmove[_ -]?files\b", re.I)),
    ("delete_files_from_ui", re.compile(r"\bdelete[_ -]?files\b.*\bui\b|\bui\b.*\bdelete[_ -]?files\b", re.I)),
    ("rewrite_source_from_ui", re.compile(r"\brewrite[_ -]?source\b.*\bui\b|\bui\b.*\brewrite[_ -]?source\b", re.I)),
    ("execute_candidate_from_ui", re.compile(r"\bexecute[_ -]?candidate\b.*\bui\b|\bui\b.*\bexecute[_ -]?candidate\b", re.I)),
]


class CheckFailure(Exception):
    pass


def rel(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def print_result(status: str, label: str, detail: str = "") -> None:
    suffix = f" {detail}" if detail else ""
    print(f"{status} {label}{suffix}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> Any:
    return json.loads(read_text(path))


def text_blob(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(text_blob(item) for pair in value.items() for item in pair)
    if isinstance(value, list):
        return " ".join(text_blob(item) for item in value)
    return str(value)


def norm(value: Any) -> str:
    return " ".join(str(value).lower().replace("\\", "/").replace("_", " ").replace("-", " ").split())


def contains_all(haystack: Any, needles: list[str]) -> bool:
    normalized = norm(haystack)
    return all(norm(needle) in normalized for needle in needles)


def require_required_files() -> None:
    required = [PLAN_JSON, PLAN_MD, PLAN_REPORT]
    missing = [rel(path) for path in required if not path.exists()]
    require(not missing, "missing UI plan files: " + ", ".join(missing))
    for path in required:
        print_result("PASS", "required UI plan file", rel(path))


def verify_plan_values(plan: dict[str, Any]) -> None:
    for key, expected in REQUIRED_VALUES.items():
        actual = plan.get(key)
        require(actual == expected, f"{key} expected {expected!r}, got {actual!r}")
    missing_keys = [key for key in REQUIRED_KEYS if key not in plan]
    require(not missing_keys, "missing required keys: " + ", ".join(missing_keys))
    print_result("PASS", "plan contract check result", f"values={len(REQUIRED_VALUES)} keys={len(REQUIRED_KEYS)}")


def verify_ui_placement(plan: dict[str, Any]) -> None:
    options = plan.get("ui_placement_options")
    require(isinstance(options, list) and options, "ui_placement_options must be a non-empty list")
    for requirement in PLACEMENT_REQUIREMENTS:
        require(any(contains_all(option, requirement) for option in options), "missing UI placement option: " + " / ".join(requirement))

    recommendation = plan.get("recommended_first_ui_surface")
    recommendation_text = norm(text_blob(recommendation))
    allowed = any(norm(term) in recommendation_text for term in ALLOWED_RECOMMENDATIONS)
    if isinstance(recommendation, dict) and recommendation.get("choice") == "STANDALONE_LOCAL_VIEWER_FIRST":
        allowed = True
    require(allowed, "recommended_first_ui_surface must be Companion compact read-only card, standalone local viewer, or command-only for now")
    for term in FORBIDDEN_RECOMMENDATION_TERMS:
        require(norm(term) not in recommendation_text, "recommended first UI surface contains forbidden direction: " + term)
    print_result("PASS", "UI placement result", "standalone/card/command-only boundary accepted")


def verify_first_ui_behavior(plan: dict[str, Any]) -> None:
    behavior = plan.get("first_ui_behavior")
    require(isinstance(behavior, dict), "first_ui_behavior must be an object")
    for field in FIRST_UI_TRUE_FIELDS:
        require(behavior.get(field) is True, "first_ui_behavior must enable display field: " + field)
    require(behavior.get("first_ui_runs_scans") is False, "first UI must not run scans")
    labels = behavior.get("show_safety_labels")
    require(isinstance(labels, list), "first_ui_behavior.show_safety_labels must be a list")
    missing_labels = [label for label in REQUIRED_SAFETY_LABELS if label not in labels]
    require(not missing_labels, "missing safety labels: " + ", ".join(missing_labels))
    print_result("PASS", "first UI behavior result", "read-only/status-first and no scan execution")


def verify_allowed_and_forbidden_actions(plan: dict[str, Any]) -> None:
    allowed = plan.get("allowed_future_ui_actions")
    require(isinstance(allowed, dict), "allowed_future_ui_actions must be an object")
    allowed_text = norm(text_blob(allowed))
    for action in FIRST_UI_ACTIONS:
        require(norm(action) in allowed_text, "allowed first UI action missing: " + action)
    for action in LATER_MANUAL_ACTIONS:
        require(norm(action) in allowed_text, "later manual action missing: " + action)
    for rule in MANUAL_ACTION_RULES:
        require(norm(rule) in allowed_text, "manual action rule missing: " + rule)

    forbidden = plan.get("forbidden_ui_actions")
    require(isinstance(forbidden, list), "forbidden_ui_actions must be a list")
    missing_forbidden = [action for action in FORBIDDEN_UI_ACTIONS if action not in forbidden]
    require(not missing_forbidden, "forbidden UI actions missing: " + ", ".join(missing_forbidden))
    print_result("PASS", "allowed/forbidden UI action result", "manual-only future actions; unsafe controls forbidden")


def verify_ui_data_model(plan: dict[str, Any]) -> None:
    model = plan.get("ui_data_model")
    require(isinstance(model, dict), "ui_data_model must be an object")
    sources = model.get("read_only_sources")
    fields = model.get("fields")
    require(isinstance(sources, list), "ui_data_model.read_only_sources must be a list")
    require(isinstance(fields, list), "ui_data_model.fields must be a list")
    missing_sources = [source for source in READ_ONLY_SOURCES if source not in sources]
    require(not missing_sources, "read-only UI sources missing: " + ", ".join(missing_sources))
    missing_fields = [field for field in UI_DATA_FIELDS if field not in fields]
    require(not missing_fields, "UI data fields missing: " + ", ".join(missing_fields))
    print_result("PASS", "UI data model result", f"sources={len(sources)} fields={len(fields)}")


def verify_future_verifier(plan: dict[str, Any]) -> None:
    future = plan.get("future_verifier")
    require(isinstance(future, dict), "future_verifier must be an object")
    future_text = norm(text_blob(future))
    for term in FUTURE_VERIFIER_TERMS:
        require(norm(term) in future_text, "future verifier plan missing: " + term)
    print_result("PASS", "future verifier result", "UI plan and implementation verifier boundaries documented")


def verify_future_sequence(plan: dict[str, Any]) -> None:
    sequence = plan.get("future_implementation_sequence")
    require(isinstance(sequence, list), "future_implementation_sequence must be a list")
    sequence_text = norm(text_blob(sequence))
    for term in FUTURE_SEQUENCE_TERMS:
        require(norm(term) in sequence_text, "future implementation sequence missing: " + term)
    forbidden_sequence_terms = ["APPLY_BUTTON", "AUTO_REPAIR", "STARTUP_BACKGROUND_SCANNING", "TRUSTED_MEMORY_PROMOTION"]
    for term in forbidden_sequence_terms:
        require(norm(term) not in sequence_text, "future sequence jumps to forbidden implementation: " + term)
    print_result("PASS", "future implementation sequence result", "no direct jump to apply/auto-repair/background behavior")


def verify_safety_preserved(plan: dict[str, Any]) -> None:
    safety = plan.get("safety_preserved")
    require(isinstance(safety, dict), "safety_preserved must be an object")
    false_values = [key for key, value in safety.items() if value is not True]
    require(not false_values, "safety_preserved contains non-true fields: " + ", ".join(false_values))
    print_result("PASS", "safety preserved plan result", f"flags={len(safety)}")


def is_verifier_only(path: Path) -> bool:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return False
    return len(relative.parts) >= 2 and relative.parts[0] == "tools" and path.name.startswith("verify_")


def line_clearly_safe_context(line: str) -> bool:
    lower = line.lower()
    safe_terms = [
        "false",
        "disabled",
        "not enabled",
        "future",
        "forbidden",
        "blocked",
        "review_required",
        "no ",
        "do not",
        "must not",
        "fail closed",
        "safety",
    ]
    return any(term in lower for term in safe_terms)


def broad_pattern_is_unrelated_to_debruijn_ui(line: str, hits: list[str]) -> bool:
    broad_hits = {"auto_repair", "auto_scan_loop", "watch_folder", "run_at_startup"}
    if not any(hit in broad_hits for hit in hits):
        return False
    lower = line.lower()
    relevance_terms = [
        "debruijn",
        "de bruijn",
        "quantum",
        "file structure",
        "structure ui",
        "structure viewer",
        "companion",
    ]
    return not any(term in lower for term in relevance_terms)


def should_scan_file(path: Path) -> bool:
    if path == SELF:
        return False
    suffix = path.suffix.lower()
    if suffix in BINARY_SUFFIXES or suffix not in ACTIVE_SOURCE_SUFFIXES:
        return False
    try:
        parts = {part.lower() for part in path.relative_to(ROOT).parts}
    except ValueError:
        return False
    return not bool(parts & EXCLUDE_DIRS)


def scan_active_source() -> None:
    scanned = 0
    skipped_safe_context = 0
    findings: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [dirname for dirname in dirnames if dirname.lower() not in EXCLUDE_DIRS]
        current = Path(dirpath)
        for filename in filenames:
            path = current / filename
            if not should_scan_file(path):
                continue
            scanned += 1
            try:
                lines = read_text(path).splitlines()
            except OSError:
                continue
            for line_number, line in enumerate(lines, start=1):
                hits = [label for label, pattern in ACTIVE_SOURCE_PATTERNS if pattern.search(line)]
                if not hits:
                    continue
                if broad_pattern_is_unrelated_to_debruijn_ui(line, hits):
                    skipped_safe_context += len(hits)
                    continue
                if is_verifier_only(path) or line_clearly_safe_context(line):
                    skipped_safe_context += len(hits)
                    continue
                findings.append(f"{rel(path)}:{line_number} hits={','.join(hits)}")
    for item in findings:
        print_result("REVIEW_REQUIRED", "active source finding", item)
    require(not findings, "active source scan found De Bruijn UI apply/auto-repair/background patterns")
    print_result("INFO", "active source files scanned", str(scanned))
    print_result("INFO", "safe disabled/verifier references", str(skipped_safe_context))
    print_result("PASS", "active source scan result", "failures=0 review_required=0")


def main() -> int:
    print("ENGEL_DEBRUIJN_QUANTUM_FILE_STRUCTURE_UI_PLAN_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: plan/static verification only; no UI, no scan button, no apply behavior")
    try:
        py_compile.compile(str(SELF), doraise=True)
        print_result("PASS", "py_compile", rel(SELF))
        require_required_files()
        plan = load_json(PLAN_JSON)
        require(isinstance(plan, dict), "UI plan JSON must be an object")
        verify_plan_values(plan)
        verify_ui_placement(plan)
        verify_first_ui_behavior(plan)
        verify_allowed_and_forbidden_actions(plan)
        verify_ui_data_model(plan)
        verify_future_verifier(plan)
        verify_future_sequence(plan)
        verify_safety_preserved(plan)
        scan_active_source()
    except py_compile.PyCompileError as exc:
        print_result("FAIL", "py_compile", str(exc))
        return 1
    except json.JSONDecodeError as exc:
        print_result("FAIL", "JSON parse", str(exc))
        return 1
    except (CheckFailure, OSError) as exc:
        print_result("FAIL", "De Bruijn Quantum File Structure UI plan verifier", str(exc))
        return 1
    except Exception as exc:
        print_result("FAIL", "unexpected verifier error", f"{type(exc).__name__}: {exc}")
        return 1

    print_result("PASS", "plan contract check result")
    print_result("PASS", "UI placement result")
    print_result("PASS", "first UI behavior result")
    print_result("PASS", "allowed/forbidden UI action result")
    print_result("PASS", "UI data model result")
    print_result("PASS", "future verifier result")
    print_result("PASS", "active source scan result")
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
