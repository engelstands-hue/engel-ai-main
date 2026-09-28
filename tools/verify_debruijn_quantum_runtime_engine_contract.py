#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_TEXT = r"D:\b.WorkSpace\Engel App"

CONTRACT_ID = "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_CONTRACT_V1"
CONTRACT_JSON = ROOT / "memory" / f"{CONTRACT_ID}.json"
CONTRACT_MD = ROOT / "memory" / f"{CONTRACT_ID}.md"
CONTRACT_REPORT = ROOT / "reports" / "codex_bridge" / f"{CONTRACT_ID}.md"
IMPLEMENTATION_VERIFIER = ROOT / "tools" / "verify_debruijn_quantum_runtime_engine.py"
IMPLEMENTATION_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_V1.md"

PASS_MARKER = "DEBRUIJN_QUANTUM_RUNTIME_ENGINE_CONTRACT_VERIFICATION_PASS"

REQUIRED_FILES = [
    CONTRACT_JSON,
    CONTRACT_MD,
    CONTRACT_REPORT,
]

FALSE_NOW_FLAGS = [
    "runtime_enabled_now",
    "command_route_added_now",
    "apply_enabled_now",
    "build_promote_enabled_now",
    "autorun_enabled_now",
    "background_worker_enabled_now",
    "scheduler_enabled_now",
    "startup_hook_enabled_now",
    "provider_api_enabled_now",
    "network_enabled_now",
    "local_llm_inference_enabled_now",
    "trusted_memory_write_enabled_now",
    "source_mutation_enabled_now",
    "route_mutation_enabled_now",
    "queue_mutation_enabled_now",
    "package_install_enabled_now",
]

REQUIRED_KEYS = [
    "basis_state_model",
    "candidate_superposition_model",
    "transition_walk_model",
    "verifier_interference_model",
    "measurement_selection_model",
    "runtime_limits",
    "runtime_output_model",
    "receipt_model",
    "future_command_concept",
    "required_gates",
    "forbidden_behavior",
    "future_verifier",
    "future_implementation_sequence",
    "safety_preserved",
    "recommended_next_slice",
]

REQUIRED_BASIS_STATES = [
    "contract_present",
    "contract_missing",
    "verifier_present",
    "verifier_missing",
    "report_present",
    "report_missing",
    "route_metadata_present",
    "route_metadata_missing",
    "candidate_proposal_present",
    "proposal_untrusted",
    "approved_inactive",
    "runtime_disabled",
    "runtime_contract_defined",
    "apply_contract_missing",
    "build_contract_missing",
    "safety_gate_present",
    "password_gate_required",
]

REQUIRED_CANDIDATE_FIELDS = [
    "candidate_id",
    "state_path",
    "source_artifacts",
    "target_artifacts",
    "confidence_or_weight",
    "verifier_interference_result",
    "safety_flags",
    "human_review_required",
    "apply_allowed",
    "runtime_generated",
]

REQUIRED_TRANSITION_TERM_GROUPS = [
    ["missing_contract", "contract_candidate"],
    ["missing_verifier", "verifier_candidate"],
    ["missing_report", "report_candidate"],
    ["route_documentation_missing", "route_doc_candidate"],
    ["candidate_untrusted", "candidate_verified_for_review"],
    ["candidate_verified_for_review", "approved_apply_candidate", "future", "apply", "flow"],
    ["approved_apply_candidate", "applied_change", "future", "apply", "engine"],
]

RUNTIME_LIMIT_BOUNDS = {
    "max_scan_files": 10000,
    "max_candidate_states": 500,
    "max_transition_depth": 6,
    "max_runtime_seconds": 180,
    "max_output_bytes": 200000,
}

REQUIRED_INTERFERENCE_FIELDS = [
    "reinforced_by",
    "suppressed_by",
    "blocker_reasons",
    "review_required_reasons",
    "final_candidate_classification",
]

REQUIRED_SELECTION_FIELDS = [
    "selected_candidate_id",
    "ranked_candidates",
    "rejected_candidates",
    "review_required_candidates",
    "no_apply_performed",
    "next_required_gate",
]

REQUIRED_RECEIPT_FIELDS = [
    "receipt_id",
    "engine_id",
    "action_type",
    "started_at",
    "ended_at",
    "input_root",
    "model_contract_id",
    "runtime_contract_id",
    "files_scanned_count",
    "basis_states_count",
    "candidates_generated_count",
    "transition_paths_count",
    "verifier_interference_summary",
    "ranked_candidates",
    "outputs_written",
    "files_changed_by_runtime",
    "forbidden_actions_not_performed",
    "password_gate_required",
    "password_gate_result",
    "final_status",
    "human_review_required",
]

EXPECTED_FUTURE_COMMANDS = [
    "engel ai debruijn quantum runtime",
    "engel ai debruijn quantum runtime --dry-run",
    "engel ai debruijn quantum runtime APPROVE_DEBRUIJN_QUANTUM_RUNTIME_RUN_V1",
]

EXPECTED_SEQUENCE = [
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_CONTRACT_V1",
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_VERIFIER_V1",
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_V1",
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_SOURCE_SMOKE_V1",
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_CLOSEOUT_REVIEW_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_CONTRACT_V1",
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
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, sort_keys=True)
    text = text.lower().replace("\\", " ")
    text = re.sub(r"[^a-z0-9_]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_all(value: Any, terms: list[str]) -> bool:
    normalized = normalize(value)
    return all(normalize(term) in normalized for term in terms)


def require_terms(check: Check, label: str, value: Any, term_groups: list[list[str]]) -> None:
    local_failures = 0
    for terms in term_groups:
        if not contains_all(value, terms):
            check.fail(f"{label} missing terms {terms!r}")
            local_failures += 1
    if local_failures == 0:
        check.pass_(label)


def load_json(check: Check, path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        check.fail(f"{rel(path)} malformed JSON at line {exc.lineno}, column {exc.colno}")
        return None
    except OSError as exc:
        check.fail(f"{rel(path)} cannot be read: {exc}")
        return None
    if not isinstance(data, dict):
        check.fail(f"{rel(path)} top-level JSON must be an object")
        return None
    return data


def check_required_files(check: Check) -> None:
    for path in REQUIRED_FILES:
        if path.exists():
            check.pass_(f"required file exists {rel(path)}")
        else:
            check.fail(f"missing required file {rel(path)}")


def check_json_identity(check: Check, payload: dict[str, Any]) -> None:
    expected_values: dict[str, Any] = {
        "contract_id": CONTRACT_ID,
        "status": "contract_only",
        "active_workspace": WORKSPACE_TEXT,
        "engine_id": "debruijn_quantum_runtime_engine",
        "future_module": "engel_debruijn_quantum_runtime.py",
        "safety_preserved": True,
        "recommended_next_slice": "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_VERIFIER_V1",
    }
    local_failures = 0
    for key, expected in expected_values.items():
        if payload.get(key) != expected:
            check.fail(f"{key} expected {expected!r}, got {payload.get(key)!r}")
            local_failures += 1
    for key in FALSE_NOW_FLAGS:
        if payload.get(key) is not False:
            check.fail(f"{key} must be false now")
            local_failures += 1
    for key in REQUIRED_KEYS:
        if key not in payload:
            check.fail(f"missing required key {key}")
            local_failures += 1
    if local_failures == 0:
        check.pass_("json identity, disabled flags, and required keys")


def check_basis_state_model(check: Check, model: Any) -> None:
    if not isinstance(model, dict):
        check.fail("basis_state_model must be an object")
        return
    states = model.get("basis_states")
    if not isinstance(states, list):
        check.fail("basis_state_model.basis_states must be a list")
        return
    missing = [state for state in REQUIRED_BASIS_STATES if state not in states]
    if missing:
        check.fail(f"basis_state_model missing states {missing!r}")
    require_terms(
        check,
        "basis_state_model local file metadata rule",
        model,
        [["local", "files"], ["metadata"], ["does", "not", "edit", "files"]],
    )


def check_candidate_superposition_model(check: Check, model: Any) -> None:
    if not isinstance(model, dict):
        check.fail("candidate_superposition_model must be an object")
        return
    fields = model.get("candidate_required_fields")
    if not isinstance(fields, list):
        check.fail("candidate_superposition_model.candidate_required_fields must be a list")
        return
    missing = [field for field in REQUIRED_CANDIDATE_FIELDS if field not in fields]
    if missing:
        check.fail(f"candidate_superposition_model missing fields {missing!r}")
    required_values = model.get("required_field_values", {})
    for key, expected in {
        "human_review_required": True,
        "apply_allowed": False,
        "runtime_generated": True,
    }.items():
        if required_values.get(key) is not expected:
            check.fail(f"candidate_superposition_model required value {key} must be {expected!r}")
    require_terms(
        check,
        "candidate_superposition_model safety",
        model,
        [
            ["multiple", "possible", "structure", "paths"],
            ["untrusted_candidate"],
            ["must", "not", "apply", "candidates"],
            ["classical", "scoring", "metadata"],
            ["not", "actual", "quantum", "amplitudes"],
        ],
    )


def check_transition_walk_model(check: Check, model: Any) -> None:
    if not isinstance(model, dict):
        check.fail("transition_walk_model must be an object")
        return
    require_terms(check, "transition_walk_model transitions", model, REQUIRED_TRANSITION_TERM_GROUPS)
    require_terms(
        check,
        "transition_walk_model bounded local rules",
        model,
        [
            ["local", "files", "only"],
            ["bounded", "depth"],
            ["bounded", "candidate", "count"],
            ["no", "arbitrary", "file", "discovery", "beyond", "approved", "root"],
            ["no", "hidden", "provider"],
            ["no", "hidden", "model"],
            ["no", "source", "mutation"],
            ["runtime", "forbidden", "transitions", "approved_apply_candidate", "applied_change"],
        ],
    )


def check_runtime_limits(check: Check, limits: Any) -> None:
    if not isinstance(limits, dict):
        check.fail("runtime_limits must be an object")
        return
    local_failures = 0
    for key, upper_bound in RUNTIME_LIMIT_BOUNDS.items():
        value = limits.get(key)
        if not isinstance(value, int) or value > upper_bound:
            check.fail(f"runtime_limits.{key} must be an integer <= {upper_bound}, got {value!r}")
            local_failures += 1
    if local_failures == 0:
        check.pass_("runtime_limits bounded values")


def check_verifier_interference_model(check: Check, model: Any) -> None:
    if not isinstance(model, dict):
        check.fail("verifier_interference_model must be an object")
        return
    fields = model.get("interference_result_fields")
    if not isinstance(fields, list):
        check.fail("verifier_interference_model.interference_result_fields must be a list")
        return
    missing = [field for field in REQUIRED_INTERFERENCE_FIELDS if field not in fields]
    if missing:
        check.fail(f"verifier_interference_model missing fields {missing!r}")
    require_terms(
        check,
        "verifier_interference_model rules",
        model,
        [
            ["candidate", "proposal", "verifier", "suppresses", "unsafe", "proposals"],
            ["entanglement", "verifier", "reinforces", "complete"],
            ["backend", "status", "consistency"],
            ["untrusted", "content", "prompt", "injection"],
            ["authority", "hierarchy", "unauthorized", "authority"],
            ["password", "gate", "protected", "actions"],
            ["route", "metadata", "unsafe", "route", "mutations"],
            ["core", "continuity", "documented", "structure", "paths"],
        ],
    )


def check_measurement_selection_model(check: Check, model: Any) -> None:
    if not isinstance(model, dict):
        check.fail("measurement_selection_model must be an object")
        return
    fields = model.get("selection_output_fields")
    if not isinstance(fields, list):
        check.fail("measurement_selection_model.selection_output_fields must be a list")
        return
    missing = [field for field in REQUIRED_SELECTION_FIELDS if field not in fields]
    if missing:
        check.fail(f"measurement_selection_model missing fields {missing!r}")
    if model.get("required_output_values", {}).get("no_apply_performed") is not True:
        check.fail("measurement_selection_model must require no_apply_performed true")
    require_terms(
        check,
        "measurement_selection_model no execution boundary",
        model,
        [
            ["ranked", "report", "only", "candidate", "actions"],
            ["human", "review", "required"],
            ["apply", "separate", "approved", "apply", "engine"],
            ["build", "promote", "separate", "approved", "build", "promote", "engine"],
            ["not", "executed", "change"],
        ],
    )


def check_runtime_output_and_receipt_model(check: Check, output_model: Any, receipt_model: Any) -> None:
    require_terms(
        check,
        "runtime_output_model",
        output_model,
        [
            ["runtime", "status", "summary"],
            ["candidate", "state", "report"],
            ["ranked", "candidate", "action", "report"],
            ["runtime", "receipt", "json"],
            ["runtime", "receipt", "markdown"],
            ["apply", "candidate", "package", "untrusted"],
            ["not", "applyable", "yet"],
        ],
    )
    if not isinstance(receipt_model, dict):
        check.fail("receipt_model must be an object")
        return
    folder = str(receipt_model.get("receipt_folder", "")).rstrip("\\/")
    if folder != r"reports\debruijn_quantum_runtime_receipts":
        check.fail(f"receipt_model.receipt_folder mismatch: {folder!r}")
    fields = receipt_model.get("runtime_receipt_fields")
    if not isinstance(fields, list):
        check.fail("receipt_model.runtime_receipt_fields must be a list")
        return
    missing = [field for field in REQUIRED_RECEIPT_FIELDS if field not in fields]
    if missing:
        check.fail(f"receipt_model missing fields {missing!r}")
    require_terms(
        check,
        "receipt_model safety",
        receipt_model,
        [["password", "gate", "result"], ["redacted"], ["human_review_required"]],
    )


def check_future_command_concept(check: Check, concept: Any) -> None:
    if not isinstance(concept, dict):
        check.fail("future_command_concept must be an object")
        return
    commands = concept.get("future_commands")
    if commands != EXPECTED_FUTURE_COMMANDS:
        check.fail("future_command_concept.future_commands must match required commands exactly")
    if concept.get("status") != "contract_only":
        check.fail("future_command_concept.status must be contract_only")
    if concept.get("command_route_added_now") is not False:
        check.fail("future_command_concept.command_route_added_now must be false")
    require_terms(
        check,
        "future_command_concept rules",
        concept,
        [
            ["do", "not", "implement", "command", "this", "slice"],
            ["approval", "phrase", "prepare", "apply", "build"],
            ["global", "password", "gate"],
            ["fail", "closed", "verifiers", "fail"],
            ["write", "runtime", "receipt"],
            ["do", "not", "apply"],
            ["do", "not", "mutate", "source", "routes", "queues", "trusted", "memory"],
        ],
    )


def check_required_gates(check: Check, gates: Any) -> None:
    require_terms(
        check,
        "required_gates",
        gates,
        [
            ["runtime", "engine", "contract", "exists"],
            ["runtime", "apply", "build", "contract", "verifier", "passes"],
            ["de", "bruijn", "proposal", "verifier", "passes"],
            ["entanglement", "verifier", "passes"],
            ["backend", "status", "consistency", "verifier", "passes"],
            ["untrusted", "content", "verifier", "passes"],
            ["authority", "hierarchy", "passes"],
            ["prompt", "injection", "guard", "passes"],
            ["global", "password", "gate", "verifier", "passes"],
            ["local", "password", "config", "not", "committed"],
            ["no", "unsafe", "dirty", "state", "prepare", "apply", "candidate"],
        ],
    )


def check_forbidden_behavior(check: Check, forbidden: Any) -> None:
    require_terms(
        check,
        "forbidden_behavior",
        forbidden,
        [
            ["source", "edit"],
            ["route", "mutation"],
            ["queue", "mutation"],
            ["trusted", "memory", "write"],
            ["memory", "promotion"],
            ["proposal", "apply"],
            ["proposal", "trust"],
            ["package", "install"],
            ["provider"],
            ["network"],
            ["model"],
            ["local", "llm"],
            ["build", "promote"],
            ["git", "stage"],
            ["git", "commit"],
            ["git", "push"],
            ["background", "loop"],
            ["scheduler"],
            ["startup", "hook"],
            ["autonomous", "apply"],
            ["hidden", "execution", "candidate", "content"],
        ],
    )


def check_future_verifier_and_sequence(check: Check, verifier: Any, sequence: Any) -> None:
    require_terms(
        check,
        "future_verifier",
        verifier,
        [
            ["tools", "verify_debruijn_quantum_runtime_engine_contract", "py"],
            ["runtime_enabled_now", "false"],
            ["mutation", "provider", "background", "flags", "false"],
            ["basis", "state", "model"],
            ["superposition", "candidate", "model"],
            ["transition", "walk", "model"],
            ["verifier", "interference", "model"],
            ["measurement", "selection", "model"],
            ["runtime", "limits"],
            ["receipt", "model"],
            ["future", "command", "contract", "only"],
            ["forbidden", "behavior"],
            ["no", "runtime", "module", "route", "exists"],
        ],
    )
    if sequence == EXPECTED_SEQUENCE:
        check.pass_("future_implementation_sequence")
    else:
        check.fail("future_implementation_sequence does not match required ordered sequence")


def iter_active_scan_files() -> list[Path]:
    files: list[Path] = []
    files.extend(path for path in ROOT.glob("*.py") if path.is_file())
    tools_dir = ROOT / "tools"
    if tools_dir.exists():
        files.extend(
            path
            for path in tools_dir.glob("*.py")
            if path.is_file() and not path.name.startswith("verify_")
        )
    scripts_dir = ROOT / "scripts"
    if scripts_dir.exists():
        files.extend(path for path in scripts_dir.glob("*.ps1") if path.is_file())
    route_metadata = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
    if route_metadata.exists():
        files.append(route_metadata)
    return sorted(set(files))


def line_is_obviously_non_active(line: str) -> bool:
    lowered = line.lower()
    safe_markers = [
        "false",
        "forbidden",
        "must not",
        "do not",
        "never",
        "disabled",
        "future",
        "contract_only",
        "not implemented",
        "no ",
        "no_",
    ]
    return any(marker in lowered for marker in safe_markers)


def active_source_scan(check: Check) -> None:
    future_module = ROOT / "engel_debruijn_quantum_runtime.py"
    if future_module.exists():
        if IMPLEMENTATION_VERIFIER.exists() and IMPLEMENTATION_REPORT.exists():
            check.pass_("approved runtime module implementation present with verifier/report evidence")
        else:
            check.fail(f"runtime module exists without implementation verifier/report evidence: {rel(future_module)}")

    direct_active_patterns = [
        r"\bdebruijn_quantum_runtime_engine\b.*\b(run|start|execute|dispatch)\b",
        r"\bengel\s+ai\s+debruijn\s+quantum\s+runtime\b.*\b(route|handler|dispatch)\b",
        r"\bAPPROVE_DEBRUIJN_QUANTUM_RUNTIME_RUN_V1\b.*\b(route|handler|dispatch)\b",
        r"\bruntime_enabled_now\s*[:=]\s*true\b",
        r"\bcommand_route_added_now\s*[:=]\s*true\b",
        r"\bapply_enabled_now\s*[:=]\s*true\b",
        r"\bbuild_promote_enabled_now\s*[:=]\s*true\b",
        r"\btrusted_memory_write_enabled_now\s*[:=]\s*true\b",
        r"\bsource_mutation_enabled_now\s*[:=]\s*true\b",
        r"\broute_mutation_enabled_now\s*[:=]\s*true\b",
        r"\bqueue_mutation_enabled_now\s*[:=]\s*true\b",
        r"\bprovider_api_enabled_now\s*[:=]\s*true\b",
        r"\bnetwork_enabled_now\s*[:=]\s*true\b",
        r"\blocal_llm_inference_enabled_now\s*[:=]\s*true\b",
        r"\bbackground_worker_enabled_now\s*[:=]\s*true\b",
    ]
    debruijn_context_patterns = [
        r"\bauto_apply\b",
        r"\bauto_build\b",
        r"\bauto_promote\b",
        r"\bsubprocess\.[^(]*\(.*\b(runtime|apply|build)\b",
        r"\bgit\s+commit\b",
        r"\bgit\s+add\b",
        r"\bpyinstaller\b",
    ]

    scanned = 0
    for path in iter_active_scan_files():
        if set(path.parts) & EXCLUDED_DIRS:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError as exc:
            check.review(f"could not scan {rel(path)}: {exc}")
            continue
        scanned += 1
        for number, line in enumerate(lines, start=1):
            lowered = line.lower()
            if line_is_obviously_non_active(line):
                continue
            for pattern in direct_active_patterns:
                if re.search(pattern, lowered, flags=re.IGNORECASE):
                    check.fail(f"active runtime/apply/build pattern {pattern!r} at {rel(path)}:{number}")
            has_debruijn_runtime_context = (
                ("debruijn" in lowered or "de bruijn" in lowered)
                and ("runtime" in lowered or "apply" in lowered or "build" in lowered or "promote" in lowered)
            )
            if not has_debruijn_runtime_context:
                continue
            for pattern in debruijn_context_patterns:
                if re.search(pattern, lowered, flags=re.IGNORECASE):
                    check.fail(f"active De Bruijn runtime/apply/build pattern {pattern!r} at {rel(path)}:{number}")
    check.pass_(f"active source scan completed scanned={scanned}")


def main() -> int:
    check = Check()
    print("ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_CONTRACT_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: contract validation only; no runtime/apply/build execution, no routes, no provider/model/network calls, no mutations")

    check_required_files(check)
    payload = load_json(check, CONTRACT_JSON) if CONTRACT_JSON.exists() else None
    if payload is not None:
        check_json_identity(check, payload)
        check_basis_state_model(check, payload.get("basis_state_model"))
        check_candidate_superposition_model(check, payload.get("candidate_superposition_model"))
        check_transition_walk_model(check, payload.get("transition_walk_model"))
        check_runtime_limits(check, payload.get("runtime_limits"))
        check_verifier_interference_model(check, payload.get("verifier_interference_model"))
        check_measurement_selection_model(check, payload.get("measurement_selection_model"))
        check_runtime_output_and_receipt_model(check, payload.get("runtime_output_model"), payload.get("receipt_model"))
        check_future_command_concept(check, payload.get("future_command_concept"))
        check_required_gates(check, payload.get("required_gates"))
        check_forbidden_behavior(check, payload.get("forbidden_behavior"))
        check_future_verifier_and_sequence(check, payload.get("future_verifier"), payload.get("future_implementation_sequence"))
    active_source_scan(check)

    if check.review_required:
        check.info(f"review_required_findings={len(check.review_required)}")
    if check.failures:
        check.line("FAIL", f"failure_count={len(check.failures)}")
        return 1

    check.pass_("contract/model check result")
    check.pass_("runtime remains disabled and non-mutating")
    check.pass_("safety preserved")
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
