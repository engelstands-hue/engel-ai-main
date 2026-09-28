#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_TEXT = r"D:\b.WorkSpace\Engel App"

CONTRACT_ID = "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_ENGINE_CONTRACT_V1"
CONTRACT_JSON = ROOT / "memory" / f"{CONTRACT_ID}.json"
CONTRACT_MD = ROOT / "memory" / f"{CONTRACT_ID}.md"
CONTRACT_REPORT = ROOT / "reports" / "codex_bridge" / f"{CONTRACT_ID}.md"

PASS_MARKER = "DEBRUIJN_QUANTUM_BUILD_PROMOTE_ENGINE_CONTRACT_VERIFICATION_PASS"

REQUIRED_FILES = [
    CONTRACT_JSON,
    CONTRACT_MD,
    CONTRACT_REPORT,
]

RELATED_FILES = [
    ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_GRAPH_ALIGNMENT_CONTRACT_V1.json",
    ROOT / "tools" / "verify_debruijn_quantum_build_promote_graph_alignment_contract.py",
    ROOT / "memory" / "ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_V1.json",
    ROOT / "tools" / "verify_debruijn_graph_sequence_model.py",
    ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_GRAPH_ALIGNMENT_CONTRACT_V1.json",
    ROOT / "tools" / "verify_debruijn_quantum_runtime_engine_graph_alignment_contract.py",
    ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_GRAPH_ALIGNMENT_CONTRACT_V1.json",
    ROOT / "tools" / "verify_debruijn_quantum_apply_engine_graph_alignment_contract.py",
    ROOT / "engel_debruijn_quantum_runtime.py",
    ROOT / "engel_debruijn_quantum_apply.py",
    ROOT / "memory" / "ENGEL_COMMANDS.md",
    ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json",
    ROOT / "engel_app.py",
    ROOT / "scripts" / "codex_verify.ps1",
    ROOT / "memory" / "ENGEL_VERIFIER_TIMEOUT_LANE_CLASSIFICATION_CONTRACT_V1.json",
    ROOT / "tools" / "verify_verifier_timeout_lane_classification_contract.py",
]

FALSE_FLAGS = [
    "build_engine_enabled_now",
    "promote_engine_enabled_now",
    "command_route_added_now",
    "build_command_enabled_now",
    "promote_command_enabled_now",
    "pyinstaller_enabled_now",
    "live_write_enabled_now",
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
    "engine_lanes",
    "build_command_allowlist_model",
    "selective_file_hygiene_model",
    "build_candidate_input_model",
    "build_gate",
    "promote_gate",
    "receipt_model",
    "timeout_lane_integration",
    "approval_phrases",
    "future_command_concepts",
    "forbidden_behavior",
    "future_verifier",
    "future_implementation_sequence",
    "safety_preserved",
    "recommended_next_slice",
]

LANE_IDS = [
    "build_preflight_only",
    "approved_graph_build",
    "promote_preflight_only",
    "approved_graph_promote",
]

ALL_LANE_TERMS = [
    "fixed-allowlist",
    "bounded",
    "receipt-writing",
    "verifier-gated",
    "password-gated for build/promote",
    "non-autonomous",
    "no retry loop",
    "no background execution",
]

BUILD_PREFLIGHT_TERMS = [
    "validate graph build candidate",
    "validate receipts",
    "validate selective file list",
    "validate exclusions",
    "run verifier checks",
    "write preflight report/receipt",
    "no build",
]

APPROVED_BUILD_TERMS = [
    "exact approval phrase",
    "password gate",
    "run only approved build command allowlist",
    "write build receipt",
    "smoke staged artifact",
    "no live promotion",
]

PROMOTE_PREFLIGHT_TERMS = [
    "validate build receipt",
    "validate staged artifact",
    "validate backup plan",
    "validate live target",
    "no live write",
]

APPROVED_PROMOTE_TERMS = [
    "exact promote approval phrase",
    "password gate",
    "backup previous live artifacts",
    "promote staged artifact to live",
    "smoke live artifact",
    "write promote receipt",
]

BUILD_COMMAND_TERMS = [
    "fixed command IDs",
    "not arbitrary shell strings",
    "build_engel_main_exe",
    "build_engel_super_swarm_exe",
    "build_approved_packaged_artifacts",
    "exact script or command path",
    "exact arguments",
    "allowed working directory",
    "timeout",
    "expected output paths",
    "forbidden output paths",
    "required pre-verifiers",
    "required post-verifiers",
    "arbitrary command input",
    "user-supplied shell command",
    "command from candidate content",
]

SELECTIVE_HYGIENE_TERMS = [
    "local password config excluded",
    "app lifecycle log excluded",
    "code_workspace excluded unless explicitly approved",
    "build/dist/live/backups excluded from source commits",
    "trusted-memory/training artifacts excluded unless explicitly approved by separate flow",
    "generated proposal outputs excluded unless approved as evidence",
    "untrusted generated outputs never treated as source truth",
    "staged set clean before build unless intentionally part of build plan",
    "no broad git add .",
    "no broad git add -A",
    "no wildcard staging",
]

BUILD_CANDIDATE_FIELDS = [
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
]

BUILD_CANDIDATE_REQUIREMENTS = [
    "inside workspace",
    "structured JSON or approved structured package",
    "not executable",
    "not treated as instructions",
    "no external URLs",
    "no path traversal",
    "no arbitrary shell commands",
    "no provider/model/network directives",
    "no local password config included",
    "no app lifecycle log included",
]

BEFORE_BUILD_GATES = [
    "build/promote engine contract exists",
    "build/promote engine verifier passes",
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
    "scripts\\codex_verify.ps1 passes or is classified by approved timeout lane policy",
    "candidate is verified_for_build_promote",
    "exact build approval phrase present",
    "password gate passes, redacted",
    "selective file list validated",
    "exclusions validated",
    "no unsafe dirty files",
    "no staged unapproved files",
    "build command ID is allowlisted",
]

AFTER_BUILD_GATES = [
    "build receipt written",
    "staged artifact created only in approved staging/build path",
    "staged artifact smoke tested",
    "no live write",
    "no trusted-memory write",
    "no provider/network/model side effects",
    "human_review_required remains true",
]

BEFORE_PROMOTE_GATES = [
    "valid build receipt exists",
    "staged smoke passed",
    "exact promote approval phrase present",
    "password gate passes, redacted",
    "live target validated",
    "backup plan validated",
    "final verifier/sanity check passes",
    "no local password config included",
    "no app lifecycle log included",
]

AFTER_PROMOTE_GATES = [
    "backup receipt/evidence written",
    "live artifact promoted only to approved live path",
    "live smoke tested",
    "promote receipt written",
    "final verifier/sanity check performed",
    "no autonomous future loop enabled",
    "human_review_required remains true",
]

BUILD_RECEIPT_FIELDS = [
    "receipt_id",
    "engine_id",
    "lane_id",
    "action_type",
    "started_at",
    "ended_at",
    "input_build_candidate_path",
    "candidate_id",
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
]

PROMOTE_RECEIPT_FIELDS = [
    "receipt_id",
    "engine_id",
    "lane_id",
    "action_type",
    "started_at",
    "ended_at",
    "input_build_receipt_path",
    "approval_detected",
    "approval_phrase_name",
    "password_gate_result",
    "backup_paths",
    "promoted_artifact_paths",
    "live_smoke_result",
    "final_verifier_results",
    "timeout_lane_classification",
    "files_changed",
    "forbidden_actions_not_performed",
    "final_status",
    "human_review_required",
]

TIMEOUT_TERMS = [
    "ENGEL_VERIFIER_TIMEOUT_LANE_CLASSIFICATION_CONTRACT_V1",
    "future dependency",
    "quick smoke check",
    "standard verifier stack",
    "long-running verifier stack",
    "receipt/report-only timeout classification",
    "bounded timeout in long-running lane must not automatically mean workspace unsafe",
    "quick/standard lanes pass",
    "cleanup succeeds",
    "timeouts are never silently ignored",
    "timeout receipts require human_review_required true",
]

APPROVAL_TERMS = [
    "APPROVE_DEBRUIJN_QUANTUM_GRAPH_BUILD_V1",
    "APPROVE_DEBRUIJN_QUANTUM_GRAPH_PROMOTE_V1",
]

FUTURE_COMMAND_TERMS = [
    "engel ai debruijn quantum build APPROVE_DEBRUIJN_QUANTUM_GRAPH_BUILD_V1 candidate=<candidate_path>",
    "engel ai debruijn quantum promote APPROVE_DEBRUIJN_QUANTUM_GRAPH_PROMOTE_V1 build_receipt=<receipt_path>",
    "contract-only",
    "commands are not implemented now",
]

FORBIDDEN_TERMS = [
    "arbitrary command execution",
    "command from candidate content",
    "build without approval phrase",
    "build without password gate",
    "promote without approval phrase",
    "promote without password gate",
    "build without verifier pass or approved timeout classification",
    "promote without staged smoke",
    "automatic build from traversal",
    "automatic promote from traversal",
    "background build/promote",
    "scheduler/startup build/promote",
    "provider/network/model/local LLM",
    "package install",
    "trusted-memory write",
    "memory promotion",
    "route/queue mutation",
    "unapproved source mutation",
    "local password config commit",
    "password/salt/hash exposure",
    "broad git staging",
    "git history rewrite",
    "live/dist/build write outside approved lane",
]

EXPECTED_SEQUENCE = [
    "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_ENGINE_CONTRACT_V1",
    "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_ENGINE_VERIFIER_V1",
    "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_ENGINE_V1",
    "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_ENGINE_SOURCE_SMOKE_V1",
    "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_CLOSEOUT_REVIEW_V1",
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

SCAN_SUFFIXES = {".py", ".ps1", ".json", ".toml", ".yaml", ".yml", ".bat", ".cmd", ".md"}

ACTIVE_PATTERNS = [
    ("build/promote module", re.compile(r"engel_debruijn_quantum_build_promote\.py", re.IGNORECASE)),
    ("build/promote engine implementation", re.compile(r"debruijn_quantum_build_promote_engine", re.IGNORECASE)),
    ("De Bruijn build route", re.compile(r"engel\s+ai\s+debruijn\s+quantum\s+build", re.IGNORECASE)),
    ("De Bruijn promote route", re.compile(r"engel\s+ai\s+debruijn\s+quantum\s+promote", re.IGNORECASE)),
    ("graph build approval phrase route", re.compile(r"APPROVE_DEBRUIJN_QUANTUM_GRAPH_BUILD_V1", re.IGNORECASE)),
    ("graph promote approval phrase route", re.compile(r"APPROVE_DEBRUIJN_QUANTUM_GRAPH_PROMOTE_V1", re.IGNORECASE)),
    ("build engine true", re.compile(r"build_engine_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
    ("promote engine true", re.compile(r"promote_engine_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
    ("build command true", re.compile(r"build_command_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
    ("promote command true", re.compile(r"promote_command_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
    ("pyinstaller true", re.compile(r"pyinstaller_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
    ("live write true", re.compile(r"live_write_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
    ("dist write true", re.compile(r"dist_write_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
    ("backup write true", re.compile(r"backup_write_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
    ("git stage commit true", re.compile(r"git_stage_commit_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
    ("auto build", re.compile(r"auto[_\s-]*build", re.IGNORECASE)),
    ("auto promote", re.compile(r"auto[_\s-]*promote", re.IGNORECASE)),
    ("subprocess pyinstaller", re.compile(r"subprocess[^\n]{0,140}pyinstaller", re.IGNORECASE)),
    ("subprocess build", re.compile(r"subprocess[^\n]{0,140}\bbuild\b", re.IGNORECASE)),
    ("subprocess promote", re.compile(r"subprocess[^\n]{0,140}\bpromote\b", re.IGNORECASE)),
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
            check.fail(f"required build/promote engine contract file missing: {rel(path)}")
        return None
    for path in REQUIRED_FILES:
        check.pass_(f"required build/promote engine contract file exists: {rel(path)}")
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
        "engine_id": "debruijn_quantum_build_promote_engine",
        "future_module": "engel_debruijn_quantum_build_promote.py",
        "graph_alignment_contract": "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_GRAPH_ALIGNMENT_CONTRACT_V1",
        "source_model_contract": "ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_V1",
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


def check_engine_lanes(check: Check, data: dict[str, Any]) -> None:
    lanes = data.get("engine_lanes")
    if not isinstance(lanes, dict):
        check.fail("engine_lanes must be an object")
        return
    for lane_id in LANE_IDS:
        if lane_id in lanes:
            check.pass_(f"engine_lanes includes {lane_id}")
        else:
            check.fail(f"engine_lanes missing {lane_id}")
    require_terms(check, "engine_lanes all-lane requirements", lanes.get("all_lanes_must_be"), ALL_LANE_TERMS)
    require_terms(check, "build_preflight_only lane", lanes.get("build_preflight_only"), BUILD_PREFLIGHT_TERMS)
    require_terms(check, "approved_graph_build lane", lanes.get("approved_graph_build"), APPROVED_BUILD_TERMS)
    require_terms(check, "promote_preflight_only lane", lanes.get("promote_preflight_only"), PROMOTE_PREFLIGHT_TERMS)
    require_terms(check, "approved_graph_promote lane", lanes.get("approved_graph_promote"), APPROVED_PROMOTE_TERMS)


def check_allowlist_hygiene_candidate(check: Check, data: dict[str, Any]) -> None:
    require_terms(check, "build_command_allowlist_model", data.get("build_command_allowlist_model"), BUILD_COMMAND_TERMS)
    require_terms(check, "selective_file_hygiene_model", data.get("selective_file_hygiene_model"), SELECTIVE_HYGIENE_TERMS)
    candidate = data.get("build_candidate_input_model")
    require_terms(check, "build_candidate_input_model fields", candidate, BUILD_CANDIDATE_FIELDS)
    require_terms(check, "build_candidate_input_model requirements", candidate, BUILD_CANDIDATE_REQUIREMENTS)


def check_gates_receipts_timeout(check: Check, data: dict[str, Any]) -> None:
    build_gate = data.get("build_gate")
    if not isinstance(build_gate, dict):
        check.fail("build_gate must be an object")
    else:
        require_terms(check, "build_gate before_approved_build", build_gate.get("before_approved_build"), BEFORE_BUILD_GATES)
        require_terms(check, "build_gate after_approved_build", build_gate.get("after_approved_build"), AFTER_BUILD_GATES)

    promote_gate = data.get("promote_gate")
    if not isinstance(promote_gate, dict):
        check.fail("promote_gate must be an object")
    else:
        require_terms(check, "promote_gate before_approved_promote", promote_gate.get("before_approved_promote"), BEFORE_PROMOTE_GATES)
        require_terms(check, "promote_gate after_approved_promote", promote_gate.get("after_approved_promote"), AFTER_PROMOTE_GATES)

    receipt = data.get("receipt_model")
    require_terms(
        check,
        "receipt_model folders",
        receipt,
        ["reports\\debruijn_quantum_build_receipts\\", "reports\\debruijn_quantum_promote_receipts\\"],
    )
    require_terms(check, "receipt_model build fields", receipt, BUILD_RECEIPT_FIELDS)
    require_terms(check, "receipt_model promote fields", receipt, PROMOTE_RECEIPT_FIELDS)
    require_terms(check, "receipt_model secret exclusion", receipt, ["receipts must never include password/salt/hash values"])

    require_terms(check, "timeout_lane_integration", data.get("timeout_lane_integration"), TIMEOUT_TERMS)


def check_phrases_commands_forbidden_sequence(check: Check, data: dict[str, Any]) -> None:
    require_terms(check, "approval_phrases", data.get("approval_phrases"), APPROVAL_TERMS)
    require_terms(check, "future_command_concepts", data.get("future_command_concepts"), FUTURE_COMMAND_TERMS)
    require_terms(check, "forbidden_behavior", data.get("forbidden_behavior"), FORBIDDEN_TERMS)
    require_terms(
        check,
        "future_verifier",
        data.get("future_verifier"),
        [
            "tools\\verify_debruijn_quantum_build_promote_engine_contract.py",
            "contract exists",
            "all current enabled flags false",
            "engine lanes documented",
            "build command allowlist model documented",
            "selective file hygiene model documented",
            "build candidate input model documented",
            "build/promote gates documented",
            "receipt model documented",
            "approval phrases documented",
            "timeout lane integration documented",
            "forbidden behavior documented",
            "no build/promote module or route exists yet",
            "no pyinstaller/build/live write active behavior exists",
        ],
    )

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
            "no_build_promote_engine_implemented",
            "no_build_promote_module_created",
            "no_build_promote_route_added",
            "no_build_command_run",
            "no_pyinstaller_run",
            "no_write_to_build_dist_live_backups",
            "no_staging_or_commit",
            "no_password_values_exposed",
        ],
    )

    if data.get("recommended_next_slice") == "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_ENGINE_VERIFIER_V1":
        check.pass_("recommended_next_slice points to build/promote engine verifier")
    else:
        check.fail("recommended_next_slice must be ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_ENGINE_VERIFIER_V1")


def should_scan(path: Path) -> bool:
    try:
        parts = path.resolve(strict=False).relative_to(ROOT.resolve(strict=False)).parts
    except ValueError:
        return False
    if any(part in EXCLUDED_DIRS for part in parts):
        return False
    if path == Path(__file__).resolve():
        return False
    if len(parts) >= 2 and parts[0] == "tools" and path.name.startswith("verify_"):
        return False
    return path.suffix.lower() in SCAN_SUFFIXES


def safe_line(line: str) -> bool:
    lower = line.lower()
    return any(marker in lower for marker in SAFE_LINE_MARKERS)


def line_has_build_promote_context(line: str) -> bool:
    lower = line.lower()
    return (
        "debruijn" in lower
        or "build_promote" in lower
        or "build/promote" in lower
        or "quantum graph build" in lower
        or "quantum graph promote" in lower
    )


def file_has_v1_fail_closed_marker(text: str) -> bool:
    """A file is recognised as containing V1 fail-closed approved-build/promote command
    wiring if it carries either disabled-reason marker. When present, V1 wiring lines
    (route prefix constants, approval-phrase constants, dispatch startswith checks,
    help bullets, allowed-pattern entries) are expected and must not be treated as
    active build/promote engine behaviour. The runtime route verifiers independently
    enforce that the V1 handlers stay fail-closed.
    """
    return (
        "APPROVED_BUILD_EXECUTION_NOT_IMPLEMENTED" in text
        or "PROMOTE_EXECUTION_NOT_IMPLEMENTED" in text
    )


V1_WIRING_LINE_MARKERS = [
    "approved_build_command_prefix_v1",
    "approved_build_command_approval_phrase_v1",
    "approved_build_command_contract_id_v1",
    "approved_build_disabled_reason_v1",
    "approved_build_forbidden_flags_v1",
    "debruijn_quantum_approved_build_command_v1",
    "approved_promote_command_prefix_v1",
    "approved_promote_command_approval_phrase_v1",
    "approved_promote_command_contract_id_v1",
    "approved_promote_disabled_reason_v1",
    "approved_promote_forbidden_flags_v1",
    "debruijn_quantum_approved_promote_command_v1",
    'debruijn_msg.startswith("engel ai debruijn quantum build")',
    'debruijn_msg.startswith("engel ai debruijn quantum promote")',
    'msg.lower().startswith("engel ai debruijn quantum build")',
    'msg.lower().startswith("engel ai debruijn quantum promote")',
    '"pattern": "engel ai debruijn quantum build"',
    '"pattern": "engel ai debruijn quantum promote"',
    "approved_build_command_fail_closed_preflight_only_v1",
    "approved_promote_command_fail_closed_preflight_only_v1",
    "engel ai debruijn quantum build approve_debruijn_quantum_graph_build_v1 candidate=<candidate_path>",
    "engel ai debruijn quantum promote approve_debruijn_quantum_graph_promote_v1 build_receipt=<receipt_path>",
]


def line_is_v1_wiring(line: str) -> bool:
    lower = line.lower()
    return any(marker.lower() in lower for marker in V1_WIRING_LINE_MARKERS)


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
    "approved_build_lane_v1_present",
    "approved_build_lane_v1_final_status_without_scripts",
    "approved_build_lane_status",
    "approved build lane v1",
    "build_lane_blocked_script_missing",
    "def get_approved_build_lane_contract",
    "def get_approved_build_lane_allowlist",
    "def approved_build_lane_receipt_payload",
    "def write_approved_build_lane_receipt",
    "def run_approved_graph_build",
    "run_approved_graph_build",
    "approval_phrase != approved_build_approval_phrase",
    "approval_phrase == approved_build_approval_phrase",
    "approval_phrase_name",
    "debruijn_quantum_approved_build_lane_",
]


def line_is_approved_build_lane_v1_allowed(path: Path, line: str, file_text: str) -> bool:
    if path.name != "engel_debruijn_quantum_build_promote.py":
        return False
    lower_text = file_text.lower()
    if "def run_approved_graph_build(" not in lower_text:
        return False
    if "build_lane_blocked_script_missing" not in lower_text:
        return False
    if "subprocess." in lower_text:
        return False
    lower_line = line.lower()
    return any(marker in lower_line for marker in APPROVED_BUILD_LANE_V1_LINE_MARKERS)


APPROVED_PROMOTE_LANE_V1_LINE_MARKERS = [
    "approved_promote_lane_id",
    "approved_promote_lane_contract_id",
    "approved_promote_approval_phrase",
    "approved_promote_lane_not_implemented",
    "approved_promote_lane_blocked_build_receipt_missing",
    "approved_promote_lane_blocked_build_receipt_invalid",
    "approved_promote_lane_blocked_staged_artifact_missing",
    "approved_promote_lane_blocked_outside_allowlist",
    "approved_promote_lane_blocked_pre_verifier",
    "approved_promote_lane_blocked_password_gate",
    "approved_promote_lane_blocked_timeout_lane_missing",
    "promote_lane_blocked_staged_artifact_missing",
    "promote_lane_not_implemented",
    "def get_approved_promote_lane_contract",
    "def get_approved_promote_lane_allowlist",
    "def write_approved_promote_lane_receipt",
    "def run_approved_graph_promote",
    "run_approved_graph_promote",
    "approval_phrase != approved_promote_approval_phrase",
    "approval_phrase == approved_promote_approval_phrase",
    "debruijn_quantum_approved_promote_lane_",
]


def line_is_approved_promote_lane_v1_allowed(path: Path, line: str, file_text: str) -> bool:
    if path.name != "engel_debruijn_quantum_build_promote.py":
        return False
    lower_text = file_text.lower()
    if "def run_approved_graph_promote(" not in lower_text:
        return False
    if "promote_lane_blocked_staged_artifact_missing" not in lower_text and "promote_lane_not_implemented" not in lower_text:
        return False
    if "subprocess." in lower_text:
        return False
    lower_line = line.lower()
    return any(marker in lower_line for marker in APPROVED_PROMOTE_LANE_V1_LINE_MARKERS)


def preflight_module_is_safe(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return False
    required = [
        "actual_build_enabled = false",
        "actual_promote_enabled = false",
        "pyinstaller_enabled = false",
        "live_write_enabled = false",
        "approved_build_execution_not_implemented",
        "build_preflight_only",
        "promote_preflight_only",
    ]
    forbidden = [
        "subprocess.",
        "os.system",
        "pyinstaller_enabled = true",
        "actual_build_enabled = true",
        "actual_promote_enabled = true",
        "live_write_enabled = true",
        "dist_write_enabled = true",
        "backup_write_enabled = true",
        "git_stage_commit_enabled = true",
    ]
    return all(item in text for item in required) and not any(item in text for item in forbidden)


def active_source_scan(check: Check) -> None:
    findings: list[str] = []
    review_notes: list[str] = []
    scanned = 0

    module_path = ROOT / "engel_debruijn_quantum_build_promote.py"
    if module_path.exists():
        if preflight_module_is_safe(module_path):
            check.info("engel_debruijn_quantum_build_promote.py exists as verified preflight-only disabled helper")
        else:
            findings.append("engel_debruijn_quantum_build_promote.py exists without required preflight-only safety literals")

    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_DIRS and not name.startswith(".")]
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
                if line_is_approved_promote_lane_v1_allowed(path, line, text):
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
                        "subprocess promote",
                        "subprocess pyinstaller",
                        "git commit",
                        "git add dot",
                        "git add all",
                        "auto build",
                        "auto promote",
                    } and not line_has_build_promote_context(line):
                        continue
                    location = f"{rel(path)}:{lineno}: {label}: {line.strip()[:160]}"
                    if line_has_build_promote_context(line) or "APPROVE_DEBRUIJN_QUANTUM_GRAPH_" in line:
                        findings.append(location)
                    else:
                        review_notes.append(location)

    check.info(f"active source scan inspected {scanned} source/config files")
    for note in review_notes:
        check.review(f"active source scan review-only finding {note}")
    if findings:
        for finding in findings:
            check.fail(f"active build/promote engine behavior found: {finding}")
    else:
        check.pass_("active source scan found no active build/promote engine behavior")


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
    print("ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_ENGINE_CONTRACT_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: contract validation only; no runtime/apply/build execution, no routes, no PyInstaller, no live/dist/build/backups writes, no provider/model/network calls, no mutations")

    if ROOT.resolve(strict=False) != Path(WORKSPACE_TEXT).resolve(strict=False):
        check.fail(f"verifier must run inside {WORKSPACE_TEXT}; resolved root is {ROOT}")
        return finish(check)

    data = read_required(check)
    inspect_related(check)
    if data is not None:
        check_identity_and_flags(check, data)
        check_engine_lanes(check, data)
        check_allowlist_hygiene_candidate(check, data)
        check_gates_receipts_timeout(check, data)
        check_phrases_commands_forbidden_sequence(check, data)
    else:
        check.skip("contract schema checks skipped because required contract files are missing")

    active_source_scan(check)
    return finish(check)


if __name__ == "__main__":
    raise SystemExit(main())
