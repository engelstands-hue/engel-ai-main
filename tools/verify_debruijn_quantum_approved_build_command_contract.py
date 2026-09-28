#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_TEXT = r"D:\b.WorkSpace\Engel App"

CONTRACT_ID = "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_COMMAND_CONTRACT_V1"
CONTRACT_JSON = ROOT / "memory" / f"{CONTRACT_ID}.json"
CONTRACT_MD = ROOT / "memory" / f"{CONTRACT_ID}.md"
CONTRACT_REPORT = ROOT / "reports" / "codex_bridge" / f"{CONTRACT_ID}.md"

PASS_MARKER = "DEBRUIJN_QUANTUM_APPROVED_BUILD_COMMAND_CONTRACT_VERIFICATION_PASS"

REQUIRED_FILES = [
    CONTRACT_JSON,
    CONTRACT_MD,
    CONTRACT_REPORT,
]

RELATED_FILES = [
    ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_ENGINE_CONTRACT_V1.json",
    ROOT / "tools" / "verify_debruijn_quantum_build_promote_engine_contract.py",
    ROOT / "engel_debruijn_quantum_build_promote.py",
    ROOT / "tools" / "verify_debruijn_quantum_build_promote_engine.py",
    ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_GRAPH_ALIGNMENT_CONTRACT_V1.json",
    ROOT / "tools" / "verify_debruijn_quantum_build_promote_graph_alignment_contract.py",
    ROOT / "memory" / "ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_V1.json",
    ROOT / "tools" / "verify_debruijn_graph_sequence_model.py",
    ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_GRAPH_ALIGNMENT_CONTRACT_V1.json",
    ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_GRAPH_ALIGNMENT_CONTRACT_V1.json",
    ROOT / "memory" / "ENGEL_COMMANDS.md",
    ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json",
    ROOT / "engel_app.py",
    ROOT / "scripts" / "codex_verify.ps1",
    ROOT / "memory" / "ENGEL_VERIFIER_TIMEOUT_LANE_CLASSIFICATION_CONTRACT_V1.json",
    ROOT / "tools" / "verify_verifier_timeout_lane_classification_contract.py",
]

FALSE_FLAGS = [
    "command_route_added_now",
    "approved_build_command_enabled_now",
    "pyinstaller_enabled_now",
    "build_execution_enabled_now",
    "live_write_enabled_now",
    "promote_enabled_now",
    "dist_write_enabled_now",
    "backup_write_enabled_now",
    "git_stage_commit_enabled_now",
    "source_mutation_enabled_now",
    "route_mutation_enabled_now",
    "queue_mutation_enabled_now",
    "trusted_memory_write_enabled_now",
    "memory_promotion_enabled_now",
    "provider_api_enabled_now",
    "network_enabled_now",
    "local_llm_inference_enabled_now",
    "background_worker_enabled_now",
    "autorun_enabled_now",
    "scheduler_enabled_now",
    "startup_hook_enabled_now",
]

REQUIRED_KEYS = [
    "current_enabled_flags",
    "future_route_syntax",
    "approved_build_input_requirements",
    "protected_action_gates",
    "fixed_command_allowlist",
    "approved_build_lane_behavior",
    "receipt_model",
    "timeout_lane_behavior",
    "selective_file_hygiene",
    "forbidden_behavior",
    "future_verifier",
    "future_implementation_sequence",
    "safety_preserved",
    "recommended_next_slice",
]

ROUTE_TERMS = [
    "engel ai debruijn quantum build APPROVE_DEBRUIJN_QUANTUM_GRAPH_BUILD_V1 candidate=<candidate_path>",
    "exact approval phrase",
    "candidate=<candidate_path>",
    "shell command strings",
    "script overrides",
    "output path overrides",
    "provider/model/network flags",
    "force flags",
    "wildcard args",
    "alternate approval phrases",
    "raw password in command text",
    "multiple candidate paths",
    "external URLs",
    "path traversal",
    "unknown arguments rejected",
    "extra arguments rejected",
    "contract-only",
    "no route added now",
]

INPUT_FIELDS = [
    "candidate_id",
    "source_node_state_id",
    "target_node_state_id",
    "edge_transition_id",
    "edge_label",
    "graph_sequence_model_contract_id",
    "runtime_receipt_path",
    "apply_receipt_path",
    "post_apply_verifier_results",
    "selective_file_list",
    "excluded_files",
    "build_command_id",
    "build_plan",
    "promote_plan",
    "approval_phrase_required: true",
    "password_gate_required: true",
    "human_review_required: true",
    "verified_for_build_promote: true",
]

INPUT_REQUIREMENTS = [
    "inside workspace",
    "structured JSON",
    "approved structured package",
    "not executable",
    "not treated as instructions",
    "no external URLs",
    "no path traversal",
    "no arbitrary shell commands",
    "no provider/model/network directives",
    "no local password config included",
    "no app lifecycle log included",
    "no code_workspace included unless explicitly approved",
    "no build/dist/live/backups source commit inclusion",
    "no untrusted generated outputs treated as source truth",
]

PROTECTED_GATES = [
    "approved build command contract exists",
    "approved build command verifier passes",
    "build/promote engine verifier passes",
    "build/promote engine contract verifier passes",
    "build/promote graph alignment verifier passes",
    "graph sequence model verifier passes",
    "runtime graph alignment verifier passes",
    "apply graph alignment verifier passes",
    "runtime engine verifier passes",
    "apply engine verifier passes",
    "authority hierarchy passes",
    "prompt injection guard passes",
    "untrusted-content verifier passes",
    "De Bruijn import boundary verifier passes",
    "Global Password Gate verifier passes",
    "scripts\\codex_verify.ps1 passes or has approved timeout-lane classification",
    "candidate path inside workspace",
    "candidate verified_for_build_promote true",
    "build command ID allowlisted",
    "exact approval phrase present",
    "Global Password Gate runtime password check passes, redacted",
    "selective file list validated",
    "exclusions validated",
    "no unsafe dirty files",
    "no staged unapproved files",
]

ALLOWLIST_TERMS = [
    "build_engel_main_exe",
    "build_engel_super_swarm_exe",
    "build_approved_packaged_artifacts",
    "exact script/command path",
    "exact arguments",
    "allowed working directory",
    "timeout seconds",
    "expected output paths",
    "forbidden output paths",
    "required pre-verifiers",
    "required post-verifiers",
    "arbitrary command execution",
    "command strings from user text",
    "command strings from candidate",
]

LANE_TERMS = [
    "run build-preflight first",
    "verify candidate eligibility",
    "verify password gate",
    "run only allowlisted build command ID",
    "write build receipt",
    "smoke staged artifact",
    "stop before live promotion",
    "require human review",
    "separate promote command only",
    "promote to live",
    "write live artifacts",
    "bypass verifier failure",
    "bypass timeout classification",
    "commit files",
    "stage git changes",
    "write trusted memory",
    "trust candidate automatically",
    "schedule future build",
    "start background build",
]

RECEIPT_TERMS = [
    "reports\\debruijn_quantum_build_receipts\\",
    "receipt_id",
    "engine_id",
    "lane_id",
    "action_type",
    "started_at",
    "ended_at",
    "input_build_candidate_path",
    "candidate_id",
    "candidate_hash",
    "source_node_state_id",
    "target_node_state_id",
    "edge_transition_id",
    "edge_label",
    "approval_detected",
    "approval_phrase_name",
    "password_gate_result",
    "selective_file_list",
    "excluded_files",
    "build_command_id",
    "build_command_allowlist_result",
    "pre_build_verifier_results",
    "timeout_lane_classification",
    "build_outputs",
    "staged_artifact_paths",
    "staged_smoke_result",
    "files_changed",
    "forbidden_actions_not_performed",
    "final_status",
    "human_review_required",
    "raw password",
    "password hash",
    "password salt",
    "token/secrets",
    "unredacted secret-like config",
]

TIMEOUT_TERMS = [
    "quick smoke check",
    "standard verifier stack",
    "long-running verifier stack",
    "receipt/report-only timeout classification",
    "bounded timeout is never silently ignored",
    "long-running timeout does not automatically mark workspace unsafe",
    "quick/standard lanes pass",
    "cleanup succeeds",
    "timeout review keeps human_review_required true",
    "failed cleanup blocks build",
]

SELECTIVE_HYGIENE_TERMS = [
    "local password config excluded",
    "app lifecycle log excluded",
    "code_workspace excluded unless explicitly approved",
    "build/dist/live/backups excluded from source commits",
    "trusted-memory/training artifacts excluded unless separate flow approves",
    "generated proposal outputs excluded unless approved as evidence",
    "untrusted generated outputs not source truth",
    "no broad git add .",
    "no broad git add -A",
    "no wildcard staging",
]

FORBIDDEN_TERMS = [
    "actual command route in this slice",
    "build execution in this slice",
    "PyInstaller execution in this slice",
    "live write",
    "promote",
    "arbitrary command execution",
    "shell command from user/candidate",
    "command from candidate content",
    "output path override",
    "provider/network/model/local LLM",
    "package install",
    "trusted-memory write",
    "memory promotion",
    "route/queue mutation",
    "unapproved source mutation",
    "background build",
    "scheduler/startup build",
    "build without approval phrase",
    "build without password gate",
    "build without verifier pass or approved timeout classification",
    "local password config commit",
    "password/salt/hash exposure",
    "broad git staging",
    "git history rewrite",
]

EXPECTED_SEQUENCE = [
    "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_COMMAND_CONTRACT_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_COMMAND_VERIFIER_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_COMMAND_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_COMMAND_SOURCE_SMOKE_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_COMMAND_CONTRACT_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_COMMAND_VERIFIER_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_COMMAND_V1",
    "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_COMMAND_CLOSEOUT_REVIEW_V1",
]

EXCLUDED_DIRS = {
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

SPECIAL_SCAN_FILES = {
    ROOT / "engel_app.py",
    ROOT / "memory" / "ENGEL_COMMANDS.md",
    ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json",
}

SCAN_SUFFIXES = {".py", ".ps1", ".json", ".toml", ".yaml", ".yml", ".bat", ".cmd", ".md"}

ACTIVE_PATTERNS = [
    ("De Bruijn approved build route", re.compile(r"engel\s+ai\s+debruijn\s+quantum\s+build", re.IGNORECASE)),
    ("approved build approval phrase route", re.compile(r"APPROVE_DEBRUIJN_QUANTUM_GRAPH_BUILD_V1", re.IGNORECASE)),
    ("approved build command true", re.compile(r"approved_build_command_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
    ("build execution true", re.compile(r"build_execution_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
    ("pyinstaller true", re.compile(r"pyinstaller_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
    ("live write true", re.compile(r"live_write_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
    ("dist write true", re.compile(r"dist_write_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
    ("backup write true", re.compile(r"backup_write_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
    ("git stage commit true", re.compile(r"git_stage_commit_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
    ("run approved graph build", re.compile(r"run[_\s-]*approved[_\s-]*graph[_\s-]*build", re.IGNORECASE)),
    ("approved_graph_build active route", re.compile(r"approved_graph_build[^\n]{0,120}(route|handler|execute|enabled)", re.IGNORECASE)),
    ("subprocess pyinstaller", re.compile(r"subprocess[^\n]{0,140}pyinstaller", re.IGNORECASE)),
    ("subprocess build", re.compile(r"subprocess[^\n]{0,140}\bbuild\b", re.IGNORECASE)),
    ("git add dot", re.compile(r"\bgit\s+add\s+\.", re.IGNORECASE)),
    ("git add all", re.compile(r"\bgit\s+add\s+-A\b", re.IGNORECASE)),
    ("git commit", re.compile(r"\bgit\s+commit\b", re.IGNORECASE)),
    ("package install", re.compile(r"\b(pip|uv|poetry|npm)\s+(install|add)\b", re.IGNORECASE)),
    ("provider network model", re.compile(r"provider.*network.*model|network.*model.*provider", re.IGNORECASE)),
    ("local llm", re.compile(r"local[_\s-]*llm", re.IGNORECASE)),
    ("background autorun scheduler", re.compile(r"background|autorun|scheduler|startup", re.IGNORECASE)),
]

SAFE_LINE_MARKERS = [
    "forbid",
    "forbidden",
    "must not",
    "do not",
    "never",
    "disabled",
    "future",
    "future-only",
    "contract",
    "contract_only",
    "review_required",
    "verifier",
    "scan",
    "pattern",
    "reject",
    "no ",
    "no_",
    "not implemented",
    "fail closed",
    "false",
    "preflight",
    "validation-only",
]


class Check:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.review_required: list[str] = []

    def line(self, level: str, message: str) -> None:
        safe_message = message.encode("ascii", "backslashreplace").decode("ascii")
        print(f"{level} {safe_message}", flush=True)

    def pass_(self, message: str) -> None:
        self.line("PASS", message)

    def fail(self, message: str) -> None:
        self.failures.append(message)
        self.line("FAIL", message)

    def info(self, message: str) -> None:
        self.line("INFO", message)

    def skip(self, message: str) -> None:
        self.line("SKIP", message)

    def review(self, message: str) -> None:
        self.review_required.append(message)
        self.line("REVIEW_REQUIRED", message)


def rel(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def normalize(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, ensure_ascii=True)
    text = text.lower().replace("\\", " ")
    text = re.sub(r"[^a-z0-9_.<>=:/-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def has_term(blob: str, term: str) -> bool:
    return normalize(term) in blob


def require_terms(check: Check, label: str, value: Any, terms: list[str]) -> None:
    blob = normalize(value)
    missing = [term for term in terms if not has_term(blob, term)]
    if missing:
        check.fail(f"{label} missing required terms: {', '.join(missing)}")
    else:
        check.pass_(f"{label} contains required terms")


def read_required(check: Check) -> dict[str, Any] | None:
    missing = [path for path in REQUIRED_FILES if not path.exists()]
    if missing:
        for path in missing:
            check.fail(f"required approved build command contract file missing: {rel(path)}")
        return None
    for path in REQUIRED_FILES:
        check.pass_(f"required approved build command contract file exists: {rel(path)}")
    try:
        data = json.loads(CONTRACT_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        check.fail(f"contract JSON is invalid: {exc}")
        return None
    if not isinstance(data, dict):
        check.fail("contract JSON top-level value must be an object")
        return None
    check.pass_("contract JSON parsed")
    return data


def inspect_related(check: Check) -> None:
    for path in RELATED_FILES:
        if path.exists():
            check.info(f"related file present for context: {rel(path)}")
        else:
            check.skip(f"related file not present: {rel(path)}")


def check_identity_and_flags(check: Check, data: dict[str, Any]) -> None:
    expected = {
        "contract_id": CONTRACT_ID,
        "status": "contract_only",
        "active_workspace": WORKSPACE_TEXT,
        "command_name": "engel ai debruijn quantum build",
        "approval_phrase": "APPROVE_DEBRUIJN_QUANTUM_GRAPH_BUILD_V1",
        "build_promote_engine_dependency": "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_ENGINE_CONTRACT_V1",
        "build_promote_graph_alignment_dependency": "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_GRAPH_ALIGNMENT_CONTRACT_V1",
    }
    for key, value in expected.items():
        if data.get(key) == value:
            check.pass_(f"{key} matches expected value")
        else:
            check.fail(f"{key} expected {value!r}, got {data.get(key)!r}")

    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        check.fail(f"contract JSON missing required keys: {', '.join(missing)}")
    else:
        check.pass_("contract JSON includes all required top-level keys")

    flags = data.get("current_enabled_flags")
    if not isinstance(flags, dict):
        check.fail("current_enabled_flags must be an object")
        flags = {}
    for flag in FALSE_FLAGS:
        if data.get(flag) is False and flags.get(flag) is False:
            check.pass_(f"{flag} is false at top level and in current_enabled_flags")
        else:
            check.fail(f"{flag} must be false at top level and in current_enabled_flags")


def check_contract_sections(check: Check, data: dict[str, Any]) -> None:
    require_terms(check, "future_route_syntax", data.get("future_route_syntax"), ROUTE_TERMS)
    require_terms(check, "approved_build_input_requirements fields", data.get("approved_build_input_requirements"), INPUT_FIELDS)
    require_terms(
        check,
        "approved_build_input_requirements candidate requirements",
        data.get("approved_build_input_requirements"),
        INPUT_REQUIREMENTS,
    )
    require_terms(check, "protected_action_gates", data.get("protected_action_gates"), PROTECTED_GATES)
    require_terms(check, "fixed_command_allowlist", data.get("fixed_command_allowlist"), ALLOWLIST_TERMS)
    require_terms(check, "approved_build_lane_behavior", data.get("approved_build_lane_behavior"), LANE_TERMS)
    require_terms(check, "receipt_model", data.get("receipt_model"), RECEIPT_TERMS)

    timeout_terms = list(TIMEOUT_TERMS)
    timeout_contract = ROOT / "memory" / "ENGEL_VERIFIER_TIMEOUT_LANE_CLASSIFICATION_CONTRACT_V1.json"
    if timeout_contract.exists():
        timeout_terms.append("ENGEL_VERIFIER_TIMEOUT_LANE_CLASSIFICATION_CONTRACT_V1")
    else:
        timeout_terms.append("required future dependency before real build command implementation")
    require_terms(check, "timeout_lane_behavior", data.get("timeout_lane_behavior"), timeout_terms)

    require_terms(check, "selective_file_hygiene", data.get("selective_file_hygiene"), SELECTIVE_HYGIENE_TERMS)
    require_terms(check, "forbidden_behavior", data.get("forbidden_behavior"), FORBIDDEN_TERMS)
    require_terms(
        check,
        "future_verifier",
        data.get("future_verifier"),
        [
            "tools\\verify_debruijn_quantum_approved_build_command_contract.py",
            "contract exists",
            "all current enabled flags false",
            "exact command syntax documented",
            "approval phrase documented",
            "only candidate arg allowed",
            "build input requirements documented",
            "protected-action gates documented",
            "fixed command allowlist documented",
            "receipt model documented",
            "timeout lane behavior documented",
            "selective file hygiene documented",
            "forbidden behavior documented",
            "no command route exists yet",
            "no build execution enabled",
            "no PyInstaller/live write behavior active",
        ],
    )


def check_sequence_and_safety(check: Check, data: dict[str, Any]) -> None:
    sequence = data.get("future_implementation_sequence")
    if not isinstance(sequence, list):
        check.fail("future_implementation_sequence must be a list")
    else:
        missing = [item for item in EXPECTED_SEQUENCE if item not in sequence]
        if missing:
            check.fail(f"future_implementation_sequence missing: {', '.join(missing)}")
        else:
            positions = [sequence.index(item) for item in EXPECTED_SEQUENCE]
            if positions == sorted(positions):
                check.pass_("future_implementation_sequence contains required ordered slices")
            else:
                check.fail("future_implementation_sequence contains required entries out of order")

    require_terms(
        check,
        "safety_preserved",
        data.get("safety_preserved"),
        [
            "contract_only",
            "no_approved_build_command_implemented",
            "no_route_added",
            "no_build_promote_source_changed",
            "no_build_command_run",
            "no_pyinstaller_run",
            "no_write_to_build_dist_live_backups",
            "no_staging_or_commit",
            "no_password_values_exposed",
        ],
    )

    if data.get("recommended_next_slice") == "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_COMMAND_VERIFIER_V1":
        check.pass_("recommended_next_slice points to approved build command verifier")
    else:
        check.fail("recommended_next_slice must be ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_COMMAND_VERIFIER_V1")


def should_scan(path: Path) -> bool:
    resolved = path.resolve(strict=False)
    if resolved == Path(__file__).resolve(strict=False):
        return False
    if resolved in {p.resolve(strict=False) for p in SPECIAL_SCAN_FILES if p.exists()}:
        return path.suffix.lower() in SCAN_SUFFIXES
    try:
        parts = resolved.relative_to(ROOT.resolve(strict=False)).parts
    except ValueError:
        return False
    if any(part in EXCLUDED_DIRS for part in parts):
        return False
    if len(parts) >= 2 and parts[0] == "tools" and path.name.startswith("verify_"):
        return False
    return path.suffix.lower() in SCAN_SUFFIXES


def safe_line(line: str) -> bool:
    lower = line.lower()
    return any(marker in lower for marker in SAFE_LINE_MARKERS)


def file_has_v1_fail_closed_marker(text: str) -> bool:
    """A file is recognised as the V1 fail-closed approved-build-command implementation
    surface if it contains the disabled-reason marker. When present, lines that look
    like the V1 wiring (route prefix constant, approval-phrase constant, dispatch
    startswith check, help bullet, allowed-pattern entry, route-metadata entry) are
    expected and must not be treated as active behavior. The runtime route verifier
    (verify_debruijn_quantum_approved_build_command.py) independently enforces that
    the V1 handler is fail-closed.
    """
    return "APPROVED_BUILD_EXECUTION_NOT_IMPLEMENTED" in text


V1_WIRING_LINE_MARKERS = [
    "approved_build_command_prefix_v1",
    "approved_build_command_approval_phrase_v1",
    "approved_build_command_contract_id_v1",
    "approved_build_disabled_reason_v1",
    "approved_build_forbidden_flags_v1",
    "debruijn_quantum_approved_build_command_v1",
    'debruijn_msg.startswith("engel ai debruijn quantum build")',
    'msg.lower().startswith("engel ai debruijn quantum build")',
    '"pattern": "engel ai debruijn quantum build"',
    "approved_build_command_fail_closed_preflight_only_v1",
    'expected_behavior": "approved_build_command_fail_closed_preflight_only_v1"',
    "engel ai debruijn quantum build approve_debruijn_quantum_graph_build_v1 candidate=<candidate_path>",
]


APPROVED_BUILD_LANE_V1_LINE_MARKERS = [
    "approved_build_lane_id",
    "approved_build_lane_contract_id",
    "approved_build_approval_phrase",
    "approved_build_lane_not_implemented",
    "approved_build_lane_blocked_script_missing",
    "approved_build_lane_blocked_pre_verifier",
    "approved_build_lane_blocked_password_gate",
    "approved_build_lane_blocked_timeout_lane_missing",
    "approved_build_lane_blocked_outside_allowlist",
    "def run_approved_graph_build(",
    "run_approved_graph_build(",
    "approval_phrase != approved_build_approval_phrase",
    "approval_phrase_name",
    "approved build lane v1",
    "build_lane_blocked_script_missing",
]


def line_is_v1_wiring(line: str) -> bool:
    lower = line.lower()
    return any(marker.lower() in lower for marker in V1_WIRING_LINE_MARKERS)


def line_is_approved_build_lane_v1_allowed(path: Path, line: str, file_text: str) -> bool:
    if path.name != "engel_debruijn_quantum_build_promote.py":
        return False
    lowered_text = file_text.lower()
    if "def run_approved_graph_build(" not in lowered_text:
        return False
    if "build_lane_blocked_script_missing" not in lowered_text:
        return False
    if "subprocess." in lowered_text:
        return False
    lower = line.lower()
    return any(marker in lower for marker in APPROVED_BUILD_LANE_V1_LINE_MARKERS)


def line_has_approved_build_context(line: str) -> bool:
    lower = line.lower()
    return (
        "debruijn" in lower
        or "approved_build" in lower
        or "approved graph build" in lower
        or "quantum graph build" in lower
        or "build_promote" in lower
        or "build/promote" in lower
    )


def active_source_scan(check: Check) -> None:
    findings: list[str] = []
    review_notes: list[str] = []
    scanned = 0

    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_DIRS and not name.startswith(".")]
        for special in SPECIAL_SCAN_FILES:
            if special.parent == Path(dirpath) and special.exists() and special.name not in filenames:
                filenames.append(special.name)
        for filename in filenames:
            path = Path(dirpath) / filename
            if not should_scan(path):
                continue
            scanned += 1
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError as exc:
                review_notes.append(f"could not read active source file {rel(path)}: {exc}")
                continue
            v1_fail_closed_file = file_has_v1_fail_closed_marker(text)
            for lineno, line in enumerate(text.splitlines(), start=1):
                if safe_line(line):
                    continue
                if v1_fail_closed_file and line_is_v1_wiring(line):
                    continue
                if line_is_approved_build_lane_v1_allowed(path, line, text):
                    continue
                for label, pattern in ACTIVE_PATTERNS:
                    if not pattern.search(line):
                        continue
                    if label in {
                        "package install",
                        "provider network model",
                        "local llm",
                        "background autorun scheduler",
                        "subprocess build",
                        "subprocess pyinstaller",
                        "git commit",
                        "git add dot",
                        "git add all",
                    } and not line_has_approved_build_context(line):
                        continue
                    location = f"{rel(path)}:{lineno}: {label}: {line.strip()[:160]}"
                    if line_has_approved_build_context(line) or "APPROVE_DEBRUIJN_QUANTUM_GRAPH_BUILD_V1" in line:
                        findings.append(location)
                    else:
                        review_notes.append(location)

    check.info(f"active source scan inspected {scanned} source/config files")
    for note in review_notes:
        check.review(f"active source scan review-only finding {note}")
    if findings:
        for finding in findings:
            check.fail(f"active approved build command behavior found: {finding}")
    else:
        check.pass_("active source scan found no active approved build command behavior")


def finish(check: Check) -> int:
    if check.review_required and not check.failures:
        check.info(f"review-required notes emitted: {len(check.review_required)}")
    if check.failures:
        check.info(f"verification failed with {len(check.failures)} failure(s)")
        return 1
    print(PASS_MARKER)
    return 0


def main() -> int:
    check = Check()
    print("ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_COMMAND_CONTRACT_VERIFIER")
    print(f"ROOT {ROOT}")
    print(
        "Mode: contract validation only; no approved build route, no build/promote execution, "
        "no PyInstaller, no build/dist/live/backups writes, no provider/model/network calls, no mutations"
    )

    if ROOT.resolve(strict=False) != Path(WORKSPACE_TEXT).resolve(strict=False):
        check.fail(f"verifier must run inside {WORKSPACE_TEXT}; resolved root is {ROOT}")
        return finish(check)

    data = read_required(check)
    inspect_related(check)
    if data is not None:
        check_identity_and_flags(check, data)
        check_contract_sections(check, data)
        check_sequence_and_safety(check, data)
    else:
        check.skip("contract schema checks skipped because required contract files are missing")

    active_source_scan(check)
    return finish(check)


if __name__ == "__main__":
    raise SystemExit(main())
