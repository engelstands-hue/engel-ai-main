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

CONTRACT_ID = "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_CONTRACT_V1"
CONTRACT_JSON = ROOT / "memory" / f"{CONTRACT_ID}.json"
CONTRACT_MD = ROOT / "memory" / f"{CONTRACT_ID}.md"
CONTRACT_REPORT = ROOT / "reports" / "codex_bridge" / f"{CONTRACT_ID}.md"

PASS_MARKER = "DEBRUIJN_QUANTUM_APPLY_ENGINE_CONTRACT_VERIFICATION_PASS"
APPROVAL_PHRASE = "APPROVE_DEBRUIJN_QUANTUM_APPLY_VERIFIED_PROPOSAL_V1"

REQUIRED_FILES = [
    CONTRACT_JSON,
    CONTRACT_MD,
    CONTRACT_REPORT,
]

FALSE_NOW_FLAGS = [
    "apply_enabled_now",
    "command_route_added_now",
    "build_promote_enabled_now",
    "autorun_enabled_now",
    "background_worker_enabled_now",
    "scheduler_enabled_now",
    "startup_hook_enabled_now",
    "provider_api_enabled_now",
    "network_enabled_now",
    "local_llm_inference_enabled_now",
    "trusted_memory_write_enabled_now",
    "memory_promotion_enabled_now",
    "unrestricted_source_mutation_enabled_now",
    "route_mutation_enabled_now",
    "queue_mutation_enabled_now",
    "package_install_enabled_now",
    "git_stage_commit_enabled_now",
]

REQUIRED_KEYS = [
    "future_command_concept",
    "eligible_apply_input",
    "verified_for_apply_state",
    "allowed_apply_actions",
    "forbidden_apply_actions",
    "apply_gates",
    "apply_transaction_model",
    "receipt_model",
    "future_verifier",
    "future_implementation_sequence",
    "safety_preserved",
    "recommended_next_slice",
]

ELIGIBLE_ALLOWED_SOURCE_TERMS = [
    ["verified", "runtime", "candidate", "package", "reports", "debruijn_quantum_runtime_receipts"],
    ["verified", "de", "bruijn", "candidate", "proposal", "reports", "debruijn_quantum_file_structure", "candidate_fix_proposals"],
]

ELIGIBLE_REQUIREMENT_TERMS = [
    ["inside", "workspace"],
    ["json", "structured", "md"],
    ["generated", "approved", "de", "bruijn", "runtime", "proposal", "system"],
    ["human_review_required", "true"],
    ["apply_allowed", "false", "generation"],
    ["verified_for_apply", "true", "verifier", "human", "approval"],
    ["data", "never", "instructions"],
    ["not", "executable"],
    ["no", "arbitrary", "paths"],
    ["no", "path", "traversal"],
    ["no", "external", "urls"],
    ["no", "provider", "model", "network", "directives"],
    ["no", "trusted", "memory", "promotion", "directives"],
]

VERIFIED_FOR_APPLY_REQUIRED_FIELDS: dict[str, Any] = {
    "verified_for_apply": True,
    "apply_scope": "bounded_file_structure",
    "target_paths_validated": True,
    "unsafe_content_scan_passed": True,
    "authority_hierarchy_passed": True,
    "prompt_injection_guard_passed": True,
    "human_review_required": True,
    "approval_phrase_required": True,
    "password_gate_required": True,
}

ALLOWED_ACTION_TERMS = [
    ["create", "missing", "contract", "scaffold", "files"],
    ["create", "missing", "report", "scaffold", "files"],
    ["create", "missing", "verifier", "scaffold", "files"],
    ["update", "documentation", "maps"],
    ["update", "route", "metadata", "route", "verifier", "approves"],
    ["create", "receipts", "reports"],
    ["create", "candidate", "proposal", "files"],
    ["update", "approved", "backend", "status", "docs"],
    ["update", "safe", "project", "index", "checklist", "docs"],
]

ALLOWED_ACTION_REQUIREMENT_TERMS = [
    ["path", "bounded", WORKSPACE_TEXT],
    ["explicitly", "listed", "proposal"],
    ["before", "after", "receipt", "evidence"],
    ["avoid", "overwriting", "non", "empty", "files", "diff", "reviewed"],
    ["preserve", "existing", "content"],
    ["atomic", "write"],
    ["apply", "receipt"],
]

FORBIDDEN_ACTION_TERMS = [
    ["delete", "source", "files"],
    ["arbitrary", "source", "rewrite"],
    ["edit", "trusted", "memory"],
    ["promote", "memory"],
    ["install", "packages"],
    ["enable", "provider", "network", "model", "runtime"],
    ["enable", "local", "llm", "inference"],
    ["enable", "agent", "autorun"],
    ["enable", "background", "workers"],
    ["create", "scheduler", "startup", "hooks"],
    ["build", "promote", "exes"],
    ["commit", "stage", "push", "git", "changes"],
    ["modify", "local", "password", "config"],
    ["expose", "password", "salt", "hash", "values"],
    ["run", "commands", "proposal", "content"],
    ["execute", "generated", "candidate", "content"],
    ["expand", "outside", "workspace"],
    ["write", "live", "dist", "build", "backups"],
]

BEFORE_APPLY_GATE_TERMS = [
    ["apply", "engine", "contract", "exists"],
    ["apply", "engine", "verifier", "passes"],
    ["runtime", "engine", "verifier", "passes"],
    ["runtime", "apply", "build", "contract", "verifier", "passes"],
    ["de", "bruijn", "candidate", "proposal", "verifier", "passes"],
    ["entanglement", "verifier", "passes"],
    ["backend", "status", "consistency", "verifier", "passes"],
    ["untrusted", "content", "verifier", "passes"],
    ["de", "bruijn", "import", "boundary", "verifier", "passes"],
    ["authority", "hierarchy", "passes"],
    ["prompt", "injection", "guard", "passes"],
    ["global", "password", "gate", "verifier", "passes"],
    ["proposal", "verified_for_apply"],
    ["approval", "phrase", "present"],
    ["global", "password", "gate", "runtime", "password", "check", "passes", "redacted"],
    ["target", "paths", "inside", "workspace"],
    ["local", "password", "config", "not", "staged", "committed"],
    ["git", "staged", "set", "clean", "intentionally", "empty"],
    ["no", "unsafe", "dirty", "state", "target", "files"],
]

AFTER_APPLY_GATE_TERMS = [
    ["apply", "receipt", "written"],
    ["post", "apply", "verifier", "stack", "passes"],
    ["changed", "files", "match", "approved", "proposal"],
    ["no", "generated", "proposal", "applied", "beyond", "approved", "scope"],
    ["no", "trusted", "memory", "write"],
    ["no", "route", "queue", "mutation", "outside", "approved", "scope"],
    ["human_review_required", "remains", "true"],
    ["build", "promote", "separate"],
]

TRANSACTION_STEPS = [
    "preflight_read",
    "validate_proposal",
    "validate_paths",
    "validate_diff_or_scaffold_plan",
    "create_backup_snapshot_or_hash_manifest",
    "apply_bounded_changes",
    "write_apply_receipt",
    "run_post_apply_verifiers",
    "classify_result",
]

RECEIPT_FIELDS = [
    "receipt_id",
    "engine_id",
    "action_type",
    "started_at",
    "ended_at",
    "input_proposal_path",
    "proposal_id",
    "proposal_hash",
    "approval_detected",
    "approval_phrase_name",
    "password_gate_result",
    "pre_apply_verifier_results",
    "files_read",
    "files_changed",
    "files_not_changed",
    "target_paths_validated",
    "forbidden_actions_not_performed",
    "post_apply_verifier_results",
    "rollback_note",
    "final_status",
    "human_review_required",
]

EXPECTED_SEQUENCE = [
    "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_CONTRACT_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_VERIFIER_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_SOURCE_SMOKE_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPROVED_APPLY_COMMAND_CONTRACT_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPROVED_APPLY_COMMAND_VERIFIER_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPROVED_APPLY_COMMAND_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_CLOSEOUT_REVIEW_V1",
    "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_CONTRACT_V1",
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
    "code_workspace",
}

SCAN_SUFFIXES = {".py", ".ps1", ".json", ".toml", ".yaml", ".yml", ".bat", ".cmd"}
ROUTE_CONFIG = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
IMPLEMENTATION_VERIFIER = ROOT / "tools" / "verify_debruijn_quantum_apply_engine.py"
IMPLEMENTATION_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_V1.md"


class Check:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.review_required: list[str] = []

    def line(self, level: str, message: str) -> None:
        print(f"{level} {message}")

    def pass_(self, message: str) -> None:
        self.line("PASS", message)

    def info(self, message: str) -> None:
        self.line("INFO", message)

    def review(self, message: str) -> None:
        self.review_required.append(message)
        self.line("REVIEW_REQUIRED", message)

    def fail(self, message: str) -> None:
        self.failures.append(message)
        self.line("FAIL", message)


def rel(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def normalize(value: Any) -> str:
    text = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    text = text.lower().replace("\\", " ")
    text = re.sub(r"[^a-z0-9_:.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def has_terms(value: Any, terms: list[str]) -> bool:
    text = normalize(value)
    return all(normalize(term) in text for term in terms)


def require_terms(check: Check, label: str, value: Any, term_groups: list[list[str]]) -> bool:
    ok = True
    for terms in term_groups:
        if not has_terms(value, terms):
            check.fail(f"{label} missing terms {terms!r}")
            ok = False
    if ok:
        check.pass_(label)
    return ok


def load_json(check: Check, path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        check.fail(f"{rel(path)} malformed JSON line={exc.lineno} column={exc.colno}")
        return None
    except OSError as exc:
        check.fail(f"{rel(path)} cannot be read: {exc}")
        return None
    if not isinstance(payload, dict):
        check.fail(f"{rel(path)} top-level JSON must be an object")
        return None
    return payload


def check_required_files(check: Check) -> None:
    for path in REQUIRED_FILES:
        if path.exists():
            check.pass_(f"required file exists {rel(path)}")
        else:
            check.fail(f"missing required file {rel(path)}")


def check_json_contract(check: Check, payload: dict[str, Any]) -> None:
    expected_values: dict[str, Any] = {
        "contract_id": CONTRACT_ID,
        "status": "contract_only",
        "active_workspace": WORKSPACE_TEXT,
        "engine_id": "debruijn_quantum_apply_engine",
        "future_module": "engel_debruijn_quantum_apply.py",
        "approval_phrase": APPROVAL_PHRASE,
        "runtime_dependency_required": True,
        "recommended_next_slice": "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_VERIFIER_V1",
    }
    ok = True
    for key, expected in expected_values.items():
        actual = payload.get(key)
        if actual != expected:
            check.fail(f"{key} expected {expected!r}, got {actual!r}")
            ok = False
    for key in FALSE_NOW_FLAGS:
        if payload.get(key) is not False:
            check.fail(f"{key} must be false now")
            ok = False
    for key in REQUIRED_KEYS:
        if key not in payload:
            check.fail(f"missing required key {key}")
            ok = False
    if ok:
        check.pass_("json contract identity/current-disabled flags/required keys")


def check_eligible_input(check: Check, value: Any) -> None:
    if not isinstance(value, dict):
        check.fail("eligible_apply_input must be an object")
        return
    require_terms(check, "eligible input allowed sources", value.get("allowed_sources", []), ELIGIBLE_ALLOWED_SOURCE_TERMS)
    require_terms(check, "eligible input requirements", value.get("requirements", []), ELIGIBLE_REQUIREMENT_TERMS)
    generation_state = value.get("generation_state", {})
    if generation_state.get("human_review_required") is not True:
        check.fail("eligible input generation_state human_review_required must be true")
    if generation_state.get("apply_allowed") is not False:
        check.fail("eligible input generation_state apply_allowed must be false")
    if generation_state.get("trusted") is not False:
        check.fail("eligible input generation_state trusted must be false")
    if generation_state.get("untrusted_candidate") is not True:
        check.fail("eligible input generation_state untrusted_candidate must be true")
    if not any("eligible input generation_state" in failure for failure in check.failures):
        check.pass_("eligible input generation state")


def check_verified_for_apply(check: Check, value: Any) -> None:
    if not isinstance(value, dict):
        check.fail("verified_for_apply_state must be an object")
        return
    meaning = value.get("meaning", "")
    require_terms(
        check,
        "verified_for_apply meaning",
        meaning,
        [["eligible", "gated", "apply", "attempt"], ["not", "trusted"]],
    )
    required_fields = value.get("required_fields", {})
    if not isinstance(required_fields, dict):
        check.fail("verified_for_apply_state.required_fields must be an object")
        return
    for key, expected in VERIFIED_FOR_APPLY_REQUIRED_FIELDS.items():
        if required_fields.get(key) != expected:
            check.fail(f"verified_for_apply_state required field {key} expected {expected!r}")
    route_keys = [key for key in required_fields if "route_metadata_verified" in key]
    if not route_keys or all(required_fields.get(key) is not True for key in route_keys):
        check.fail("verified_for_apply_state must require route_metadata_verified if route metadata update is included")
    if value.get("fail_closed_if_missing_or_stale") is not True:
        check.fail("verified_for_apply_state must fail closed if missing or stale")
    if not any("verified_for_apply_state" in failure for failure in check.failures):
        check.pass_("verified-for-apply state result")


def check_allowed_actions(check: Check, actions: Any, requirements: Any) -> None:
    if not isinstance(actions, list):
        check.fail("allowed_apply_actions must be a list")
        return
    require_terms(check, "allowed apply actions", actions, ALLOWED_ACTION_TERMS)
    for action in actions:
        if not isinstance(action, dict):
            check.fail("each allowed apply action must be an object")
            continue
        if action.get("path_bounded") is not True:
            check.fail(f"allowed action {action.get('action')!r} must require path_bounded true")
        if action.get("requires_explicit_proposal_entry") is not True:
            check.fail(f"allowed action {action.get('action')!r} must require explicit proposal entry")
    require_terms(check, "allowed action requirements", requirements, ALLOWED_ACTION_REQUIREMENT_TERMS)
    if not any("allowed action" in failure or "allowed apply actions" in failure for failure in check.failures):
        check.pass_("allowed action per-entry bounds")


def check_forbidden_actions(check: Check, value: Any) -> None:
    require_terms(check, "forbidden apply actions", value, FORBIDDEN_ACTION_TERMS)


def check_apply_gates(check: Check, value: Any) -> None:
    if not isinstance(value, dict):
        check.fail("apply_gates must be an object")
        return
    require_terms(check, "before-apply gates", value.get("before_apply", []), BEFORE_APPLY_GATE_TERMS)
    require_terms(check, "after-apply gates", value.get("after_apply", []), AFTER_APPLY_GATE_TERMS)


def check_transaction_model(check: Check, value: Any) -> None:
    if not isinstance(value, dict):
        check.fail("apply_transaction_model must be an object")
        return
    steps = value.get("steps", [])
    for step in TRANSACTION_STEPS:
        if step not in steps:
            check.fail(f"apply_transaction_model missing step {step}")
    rollback = value.get("rollback", {})
    if not isinstance(rollback, dict):
        check.fail("apply_transaction_model.rollback must be an object")
        return
    expected_rollback: dict[str, Any] = {
        "automatic_rollback_enabled_now": False,
        "automatic_rollback_requires_separate_approval": True,
        "rollback_notes_required": True,
        "hash_manifest_required": True,
        "post_verifier_failure_status": "APPLIED_REVIEW_REQUIRED",
        "delete_backups_or_evidence": False,
    }
    for key, expected in expected_rollback.items():
        if rollback.get(key) != expected:
            check.fail(f"rollback {key} expected {expected!r}")
    if not any("apply_transaction_model" in failure or "rollback" in failure for failure in check.failures):
        check.pass_("transaction model result")


def check_receipt_model(check: Check, value: Any) -> None:
    if not isinstance(value, dict):
        check.fail("receipt_model must be an object")
        return
    if value.get("folder") != "reports\\debruijn_quantum_apply_receipts\\":
        check.fail("receipt_model folder mismatch")
    fields = value.get("fields", [])
    for field in RECEIPT_FIELDS:
        if field not in fields:
            check.fail(f"receipt_model missing field {field}")
    required_values = value.get("required_values", {})
    if required_values.get("engine_id") != "debruijn_quantum_apply_engine":
        check.fail("receipt_model required engine_id mismatch")
    if required_values.get("action_type") != "approved_apply":
        check.fail("receipt_model required action_type mismatch")
    if required_values.get("approval_detected") is not True:
        check.fail("receipt_model approval_detected must be true")
    if required_values.get("password_gate_result") != "redacted":
        check.fail("receipt_model password_gate_result must be redacted")
    if required_values.get("human_review_required") is not True:
        check.fail("receipt_model human_review_required must be true")
    require_terms(check, "receipt model secret exclusion", value.get("must_not_include", []), [["password"], ["salt"], ["hash"], ["raw", "secret"]])
    if not any("receipt_model" in failure for failure in check.failures):
        check.pass_("receipt model result")


def check_future_command(check: Check, value: Any) -> None:
    if not isinstance(value, dict):
        check.fail("future_command_concept must be an object")
        return
    command = value.get("command", "")
    expected_command = (
        "engel ai debruijn quantum apply "
        "APPROVE_DEBRUIJN_QUANTUM_APPLY_VERIFIED_PROPOSAL_V1 proposal=<proposal_path>"
    )
    if command != expected_command:
        check.fail(f"future command mismatch: {command!r}")
    expected_bools = [
        "requires_exact_approval_phrase",
        "requires_global_password_gate",
        "proposal_path_must_be_inside_workspace",
        "reject_external_urls",
        "reject_path_traversal",
        "reject_arbitrary_extra_args",
        "reject_output_path_override",
        "reject_shell_commands",
        "reject_provider_model_network_args",
        "fail_closed_on_missing_verifier_or_gate",
    ]
    for key in expected_bools:
        if value.get(key) is not True:
            check.fail(f"future_command_concept {key} must be true")
    if value.get("implemented_now") is not False:
        check.fail("future_command_concept implemented_now must be false")
    if value.get("status") != "future_only_contract_only":
        check.fail("future_command_concept status must be future_only_contract_only")
    if not any("future_command_concept" in failure or "future command" in failure for failure in check.failures):
        check.pass_("future command concept result")


def check_future_verifier(check: Check, value: Any) -> None:
    if not isinstance(value, dict):
        check.fail("future_verifier must be an object")
        return
    if value.get("path") != r"tools\verify_debruijn_quantum_apply_engine_contract.py":
        check.fail("future_verifier path mismatch")
    require_terms(
        check,
        "future verifier checks",
        value.get("checks", []),
        [
            ["contract", "exists"],
            ["apply_enabled_now", "false"],
            ["command_route_added_now", "false"],
            ["mutation", "provider", "background", "build", "flags", "false"],
            ["eligible", "input", "model"],
            ["verified_for_apply", "state"],
            ["allowed", "actions", "bounded"],
            ["forbidden", "actions", "documented"],
            ["gates", "documented"],
            ["transaction", "model", "documented"],
            ["receipt", "model", "documented"],
            ["future", "command", "contract", "only"],
            ["no", "apply", "module", "route"],
        ],
    )


def check_sequence(check: Check, value: Any) -> None:
    if value != EXPECTED_SEQUENCE:
        check.fail("future_implementation_sequence mismatch")
    else:
        check.pass_("future implementation sequence result")


def should_scan(path: Path) -> bool:
    rel_parts = path.relative_to(ROOT).parts
    if any(part in EXCLUDED_DIRS for part in rel_parts):
        return False
    if path == Path(__file__).resolve():
        return False
    if path.suffix.lower() not in SCAN_SUFFIXES:
        return False
    if "memory" in rel_parts:
        return path.resolve(strict=False) == ROUTE_CONFIG.resolve(strict=False)
    return True


def is_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:2048]
    except OSError:
        return True
    return b"\0" in chunk


def active_source_scan(check: Check) -> None:
    apply_module = ROOT / "engel_debruijn_quantum_apply.py"
    approved_apply_module_present = False
    if apply_module.exists():
        if IMPLEMENTATION_VERIFIER.exists() and IMPLEMENTATION_REPORT.exists():
            approved_apply_module_present = True
            check.pass_("approved apply module implementation present with verifier/report evidence")
        else:
            check.fail("active apply module exists without implementation verifier/report evidence: engel_debruijn_quantum_apply.py")

    scanned = 0
    safe_references = 0
    active_findings: list[str] = []
    review_findings: list[str] = []

    dangerous_patterns = [
        ("apply engine active implementation", re.compile(r"debruijn_quantum_apply_engine")),
        ("apply route handler", re.compile(r"engel\s+ai\s+debruijn\s+quantum\s+apply")),
        ("approval phrase route handler", re.compile(re.escape(APPROVAL_PHRASE))),
        ("apply enabled true", re.compile(r"apply_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
        ("command route true", re.compile(r"command_route_added_now\s*[:=]\s*true", re.IGNORECASE)),
        ("trusted memory write true", re.compile(r"trusted_memory_write_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
        ("memory promotion true", re.compile(r"memory_promotion_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
        ("unrestricted source mutation true", re.compile(r"unrestricted_source_mutation_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
        ("route mutation true", re.compile(r"route_mutation_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
        ("queue mutation true", re.compile(r"queue_mutation_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
        ("provider api true", re.compile(r"provider_api_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
        ("network true", re.compile(r"network_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
        ("local llm true", re.compile(r"local_llm_inference_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
        ("background worker true", re.compile(r"background_worker_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
        ("git stage commit true", re.compile(r"git_stage_commit_enabled_now\s*[:=]\s*true", re.IGNORECASE)),
        ("apply verified proposal", re.compile(r"apply_verified_proposal")),
        ("execute proposal", re.compile(r"execute[_\s-]+proposal")),
        ("trust proposal", re.compile(r"trust[_\s-]+proposal")),
        ("promote proposal", re.compile(r"promote[_\s-]+proposal")),
        ("auto apply", re.compile(r"auto[_\s-]+apply")),
        ("subprocess apply", re.compile(r"subprocess[^\n]{0,120}apply")),
        ("git commit", re.compile(r"\bgit\s+commit\b")),
        ("git add", re.compile(r"\bgit\s+add\b")),
        ("pyinstaller", re.compile(r"pyinstaller")),
        ("package install", re.compile(r"\b(pip|uv|poetry|npm)\s+(install|add)\b")),
    ]

    verifier_or_contract_tokens = [
        "verify_",
        "contract",
        "future_only",
        "contract_only",
        "forbidden",
        "not implemented",
        "planned",
        "review_required",
    ]

    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_DIRS]
        base = Path(dirpath)
        for filename in filenames:
            path = base / filename
            if not path.is_file() or not should_scan(path) or is_binary(path):
                continue
            if approved_apply_module_present and path.resolve(strict=False) == apply_module.resolve(strict=False):
                safe_references += 1
                continue
            scanned += 1
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                check.review(f"could not scan {rel(path)}")
                continue
            lower = text.lower()
            is_verifier_or_contract = any(token in lower or token in path.name.lower() for token in verifier_or_contract_tokens)
            for label, pattern in dangerous_patterns:
                if not pattern.search(text):
                    continue
                if is_verifier_or_contract:
                    safe_references += 1
                    continue
                if "debruijn" in lower and "apply" in lower:
                    active_findings.append(f"{rel(path)}: {label}")
                else:
                    review_findings.append(f"{rel(path)}: {label}")

    for finding in review_findings:
        check.review(f"active source scan review-only finding {finding}")
    for finding in active_findings:
        check.fail(f"active apply implementation pattern found {finding}")
    if not active_findings:
        check.pass_(f"active source scan result scanned={scanned} safe_references={safe_references}")


def main() -> int:
    check = Check()
    print("ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_CONTRACT_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: contract validation only; no apply/runtime/build execution, no routes, no provider/model/network calls, no mutations")

    check_required_files(check)
    if check.failures:
        return finish(check)

    payload = load_json(check, CONTRACT_JSON)
    if payload is None:
        return finish(check)

    check_json_contract(check, payload)
    check_eligible_input(check, payload.get("eligible_apply_input"))
    check_verified_for_apply(check, payload.get("verified_for_apply_state"))
    check_allowed_actions(check, payload.get("allowed_apply_actions"), payload.get("allowed_action_requirements"))
    check_forbidden_actions(check, payload.get("forbidden_apply_actions"))
    check_apply_gates(check, payload.get("apply_gates"))
    check_transaction_model(check, payload.get("apply_transaction_model"))
    check_receipt_model(check, payload.get("receipt_model"))
    check_future_command(check, payload.get("future_command_concept"))
    check_future_verifier(check, payload.get("future_verifier"))
    check_sequence(check, payload.get("future_implementation_sequence"))
    active_source_scan(check)

    if not check.failures:
        check.pass_("contract check result")
        check.pass_("eligible input / verified-for-apply result")
        check.pass_("allowed/forbidden action result")
        check.pass_("apply gates result")
        check.pass_("transaction model result")
        check.pass_("receipt model result")
        check.pass_("future command concept result")
        check.pass_("safety preserved")
    return finish(check)


def finish(check: Check) -> int:
    if check.failures:
        print("FAILURES")
        for failure in check.failures:
            print(f"- {failure}")
        return 1
    if check.review_required:
        print(f"INFO review_required_findings={len(check.review_required)}")
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
