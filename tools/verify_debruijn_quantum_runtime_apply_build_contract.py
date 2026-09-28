#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_TEXT = r"D:\b.WorkSpace\Engel App"

CONTRACT_ID = "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_APPLY_BUILD_CONTRACT_V1"
CONTRACT_JSON = ROOT / "memory" / f"{CONTRACT_ID}.json"
CONTRACT_MD = ROOT / "memory" / f"{CONTRACT_ID}.md"
CONTRACT_REPORT = ROOT / "reports" / "codex_bridge" / f"{CONTRACT_ID}.md"
RUNTIME_IMPLEMENTATION_VERIFIER = ROOT / "tools" / "verify_debruijn_quantum_runtime_engine.py"
RUNTIME_IMPLEMENTATION_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_V1.md"
APPLY_IMPLEMENTATION_VERIFIER = ROOT / "tools" / "verify_debruijn_quantum_apply_engine.py"
APPLY_IMPLEMENTATION_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_V1.md"

PASS_MARKER = "DEBRUIJN_QUANTUM_RUNTIME_APPLY_BUILD_CONTRACT_VERIFICATION_PASS"

REQUIRED_FILES = [
    CONTRACT_JSON,
    CONTRACT_MD,
    CONTRACT_REPORT,
]

REQUIRED_KEYS = [
    "runtime_engine_plan",
    "apply_engine_plan",
    "build_promote_engine_plan",
    "approval_phrases",
    "required_gates",
    "receipt_model",
    "lane_model",
    "forbidden_behavior",
    "future_implementation_sequence",
    "safety_preserved",
    "recommended_next_slice",
]

FALSE_NOW_FLAGS = [
    "runtime_enabled_now",
    "apply_enabled_now",
    "build_promote_enabled_now",
    "autorun_enabled_now",
    "background_worker_enabled_now",
    "trusted_memory_write_enabled_now",
    "source_mutation_enabled_now",
    "route_mutation_enabled_now",
    "queue_mutation_enabled_now",
    "provider_api_enabled_now",
    "network_enabled_now",
    "local_llm_inference_enabled_now",
]

EXPECTED_APPROVAL_PHRASES = {
    "runtime": "APPROVE_DEBRUIJN_QUANTUM_RUNTIME_RUN_V1",
    "apply": "APPROVE_DEBRUIJN_QUANTUM_APPLY_VERIFIED_PROPOSAL_V1",
    "build_promote": "APPROVE_DEBRUIJN_QUANTUM_BUILD_PROMOTE_V1",
}

EXPECTED_SEQUENCE = [
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_APPLY_BUILD_CONTRACT_V1",
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_APPLY_BUILD_VERIFIER_V1",
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_CONTRACT_V1",
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_V1",
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_SOURCE_SMOKE_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_CONTRACT_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_VERIFIER_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPROVED_APPLY_COMMAND_V1",
    "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_CONTRACT_V1",
    "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_VERIFIER_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_PROMOTE_COMMAND_V1",
]

FUTURE_MODULES = [
    "engel_debruijn_quantum_runtime.py",
    "engel_debruijn_quantum_apply.py",
    "engel_debruijn_quantum_build_promote.py",
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


class Check:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.review_required: list[str] = []
        self.infos: list[str] = []

    def line(self, level: str, message: str) -> None:
        print(f"{level} {message}")

    def fail(self, message: str) -> None:
        self.failures.append(message)
        self.line("FAIL", message)

    def review(self, message: str) -> None:
        self.review_required.append(message)
        self.line("REVIEW_REQUIRED", message)

    def info(self, message: str) -> None:
        self.infos.append(message)
        self.line("INFO", message)

    def passed(self, message: str) -> None:
        self.line("PASS", message)


def rel(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def normalize(value: Any) -> str:
    text = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    text = text.lower()
    text = text.replace("\\", " ")
    text = re.sub(r"[^a-z0-9_]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def require_terms(check: Check, label: str, value: Any, term_groups: list[list[str]]) -> None:
    normalized = normalize(value)
    for terms in term_groups:
        missing = [term for term in terms if normalize(term) not in normalized]
        if missing:
            check.fail(f"{label} missing terms {missing!r}")
    if not any(label in failure for failure in check.failures):
        check.passed(label)


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
            check.passed(f"required file exists {rel(path)}")
        else:
            check.fail(f"missing required file {rel(path)}")


def check_json_contract(check: Check, payload: dict[str, Any]) -> None:
    expected_values: dict[str, Any] = {
        "contract_id": CONTRACT_ID,
        "status": "contract_only",
        "active_workspace": WORKSPACE_TEXT,
        "user_intent": "runtime_apply_build_enabled_through_gated_phases",
        "runtime_planned": True,
        "apply_planned": True,
        "build_promote_planned": True,
        "safety_preserved": True,
        "recommended_next_slice": "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_APPLY_BUILD_VERIFIER_V1",
    }
    for key, expected in expected_values.items():
        actual = payload.get(key)
        if actual != expected:
            check.fail(f"{key} expected {expected!r}, got {actual!r}")
    for key in FALSE_NOW_FLAGS:
        if payload.get(key) is not False:
            check.fail(f"{key} must be false now")
    for key in REQUIRED_KEYS:
        if key not in payload:
            check.fail(f"missing required key {key}")
    if not check.failures:
        check.passed("json contract identity/current-disabled flags/required keys")


def check_runtime_plan(check: Check, plan: Any) -> None:
    if not isinstance(plan, dict):
        check.fail("runtime_engine_plan must be an object")
        return
    if plan.get("future_module") != "engel_debruijn_quantum_runtime.py":
        check.fail("runtime_engine_plan future_module mismatch")
    require_terms(
        check,
        "runtime_engine_plan purpose",
        plan.get("purpose", []),
        [
            ["load", "current", "local", "engel", "structure"],
            ["load", "de", "bruijn", "quantum", "view", "model"],
            ["compute", "basis", "states"],
            ["candidate", "superposition", "sets"],
            ["transition", "walk", "paths"],
            ["verifier", "interference", "scoring"],
            ["ranked", "candidate", "actions"],
            ["runtime", "receipts"],
        ],
    )
    require_terms(
        check,
        "runtime_engine_plan required properties",
        plan.get("required_properties", {}),
        [
            ["local", "offline", "default"],
            ["bounded"],
            ["receipt", "writing"],
            ["verifier", "gated"],
            ["global", "password", "gate"],
        ],
    )
    require_terms(
        check,
        "runtime_engine_plan forbidden behavior",
        plan.get("must_not", []),
        [
            ["auto", "apply"],
            ["auto", "build"],
            ["auto", "promote"],
            ["trusted", "memory"],
            ["provider", "network", "model"],
            ["background", "autonomous", "loops"],
        ],
    )


def check_apply_plan(check: Check, plan: Any) -> None:
    if not isinstance(plan, dict):
        check.fail("apply_engine_plan must be an object")
        return
    if plan.get("future_module") != "engel_debruijn_quantum_apply.py":
        check.fail("apply_engine_plan future_module mismatch")
    require_terms(
        check,
        "apply_engine_plan purpose",
        plan.get("purpose", []),
        [
            ["verified", "proposal"],
            ["approved", "de", "bruijn", "runtime", "proposal", "output"],
            ["human", "approval", "phrase"],
            ["global", "password", "gate"],
            ["pre", "apply", "verifiers"],
            ["allowlisted", "file", "structure", "changes"],
            ["apply", "receipt"],
            ["post", "apply", "verifiers"],
        ],
    )
    require_terms(
        check,
        "apply_engine_plan allowed actions",
        plan.get("allowed_future_apply_actions", []),
        [
            ["contract", "scaffold", "files"],
            ["report", "scaffold", "files"],
            ["verifier", "scaffold", "files"],
            ["documentation", "maps"],
            ["route", "metadata", "route", "verifier"],
            ["receipts", "reports"],
            ["candidate", "proposal", "files"],
            ["approved", "backend", "status", "docs"],
        ],
    )
    require_terms(
        check,
        "apply_engine_plan forbidden actions",
        plan.get("forbidden_without_higher_contract", []),
        [
            ["delete", "source"],
            ["rewrite", "arbitrary", "files"],
            ["edit", "trusted", "memory"],
            ["promote", "memory"],
            ["install", "packages"],
            ["provider", "network", "model"],
            ["agent", "autorun"],
            ["background", "workers"],
            ["build", "promote", "exes"],
            ["commit", "git", "changes", "automatically"],
        ],
    )


def check_build_plan(check: Check, plan: Any) -> None:
    if not isinstance(plan, dict):
        check.fail("build_promote_engine_plan must be an object")
        return
    if plan.get("future_module") != "engel_debruijn_quantum_build_promote.py":
        check.fail("build_promote_engine_plan future_module mismatch")
    require_terms(
        check,
        "build_promote_engine_plan purpose",
        plan.get("purpose", []),
        [
            ["approved", "apply", "clean", "verifier", "pass"],
            ["unsafe", "dirty", "files"],
            ["approved", "build", "commands"],
            ["smoke", "test", "staged", "live", "outputs"],
            ["build", "promote", "receipts"],
        ],
    )
    require_terms(
        check,
        "build_promote_engine_plan required gates",
        plan.get("required_before_build_promote", []),
        [
            ["explicit", "approval", "phrase"],
            ["global", "password", "gate"],
            ["full", "verifier", "stack"],
            ["generated", "untrusted", "proposal", "outputs"],
            ["local", "password", "config"],
            ["trusted", "memory", "training", "artifacts"],
            ["provider", "network", "model", "side", "effects"],
        ],
    )


def check_approval_phrases(check: Check, payload: dict[str, Any]) -> None:
    phrases = payload.get("approval_phrases")
    if not isinstance(phrases, dict):
        check.fail("approval_phrases must be an object")
        return
    for key, expected in EXPECTED_APPROVAL_PHRASES.items():
        if phrases.get(key) != expected:
            check.fail(f"approval phrase {key} expected {expected!r}, got {phrases.get(key)!r}")
    if not any("approval phrase" in failure for failure in check.failures):
        check.passed("approval_phrases")


def check_required_gates(check: Check, gates: Any) -> None:
    if not isinstance(gates, dict):
        check.fail("required_gates must be an object")
        return
    require_terms(
        check,
        "runtime_gate",
        gates.get("runtime_gate", []),
        [
            ["model", "contract", "exists"],
            ["runtime", "contract", "exists"],
            ["proposal", "verifier", "passes"],
            ["entanglement", "verifier", "passes"],
            ["backend", "status", "consistency", "passes"],
            ["untrusted", "content", "verifier", "passes"],
            ["authority", "hierarchy", "passes"],
            ["prompt", "injection", "guard", "passes"],
        ],
    )
    require_terms(
        check,
        "apply_gate",
        gates.get("apply_gate", []),
        [
            ["all", "runtime", "gates", "pass"],
            ["proposal", "verified_for_apply"],
            ["proposal", "human_review_required"],
            ["approval", "phrase", "present"],
            ["global", "password", "gate", "passes"],
            ["target", "paths", "inside", "workspace"],
            ["trusted", "memory", "mutation", "outside", "allowlist"],
            ["source", "mutation", "outside", "allowlist"],
            ["route", "mutation", "outside", "allowlist"],
            ["queue", "mutation", "outside", "allowlist"],
            ["pre", "apply", "verifier", "stack", "passes"],
        ],
    )
    require_terms(
        check,
        "build_promote_gate",
        gates.get("build_promote_gate", []),
        [
            ["all", "apply", "gates", "pass"],
            ["post", "apply", "verifier", "stack", "passes"],
            ["selective", "commit", "build", "plan", "exists"],
            ["build", "commands", "approved", "allowlist"],
            ["local", "password", "config"],
            ["generated", "de", "bruijn", "outputs"],
            ["unrelated", "dirty", "files"],
            ["explicit", "build", "approval", "phrase"],
            ["global", "password", "gate", "passes"],
        ],
    )


def check_receipt_model(check: Check, model: Any) -> None:
    if not isinstance(model, dict):
        check.fail("receipt_model must be an object")
        return
    expected_folders = {
        "runtime_receipt_folder": r"reports\debruijn_quantum_runtime_receipts",
        "apply_receipt_folder": r"reports\debruijn_quantum_apply_receipts",
        "build_promote_receipt_folder": r"reports\debruijn_quantum_build_promote_receipts",
    }
    for key, expected in expected_folders.items():
        actual = str(model.get(key, "")).rstrip("\\/")
        if actual != expected:
            check.fail(f"receipt_model {key} expected {expected!r}, got {actual!r}")
    required_fields = model.get("required_fields")
    if not isinstance(required_fields, list):
        check.fail("receipt_model required_fields must be a list")
        return
    for field in [
        "receipt_id",
        "action_type",
        "approval_phrase_detected",
        "password_gate_result_redacted",
        "input_proposal_path",
        "verifier_results",
        "files_read",
        "files_changed",
        "files_not_changed",
        "forbidden_actions_not_performed",
        "final_status",
        "human_review_required",
        "rollback_note_if_applicable",
    ]:
        if field not in required_fields:
            check.fail(f"receipt_model missing required field {field}")
    require_terms(
        check,
        "receipt_model redaction policies",
        model,
        [
            ["approval", "detected", "do", "not", "store", "raw"],
            ["redacted", "never", "store", "password", "salt", "hash", "raw", "secret"],
        ],
    )


def check_lane_model(check: Check, lanes: Any) -> None:
    if not isinstance(lanes, list):
        check.fail("lane_model must be a list")
        return
    by_id = {lane.get("lane_id"): lane for lane in lanes if isinstance(lane, dict)}
    for lane_id in [
        "runtime_report_only",
        "runtime_prepare_apply_candidate",
        "approved_apply",
        "post_apply_verify",
        "approved_build_promote",
    ]:
        if lane_id not in by_id:
            check.fail(f"lane_model missing {lane_id}")
    if by_id.get("runtime_report_only", {}).get("apply_allowed") is not False:
        check.fail("runtime_report_only must not allow apply")
    if by_id.get("runtime_prepare_apply_candidate", {}).get("apply_allowed") is not False:
        check.fail("runtime_prepare_apply_candidate must not allow apply")
    if by_id.get("approved_apply", {}).get("requires_future_implementation_contract") is not True:
        check.fail("approved_apply must require future implementation contract")
    if by_id.get("approved_build_promote", {}).get("requires_future_implementation_contract") is not True:
        check.fail("approved_build_promote must require future implementation contract")
    require_terms(
        check,
        "lane_model approval/password/verifier boundaries",
        lanes,
        [
            ["approved", "apply", "approval", "phrase", "password", "gate", "verifiers"],
            ["approved", "build", "promote", "clean", "verifier", "state", "explicit", "approval"],
        ],
    )


def check_forbidden_behavior(check: Check, forbidden: Any) -> None:
    require_terms(
        check,
        "forbidden_behavior",
        forbidden,
        [
            ["auto", "apply"],
            ["auto", "build"],
            ["auto", "promote"],
            ["trusted", "memory", "write"],
            ["delete", "source"],
            ["rewrite", "arbitrary", "files"],
            ["provider", "network", "model"],
            ["local", "llm", "inference"],
            ["autorun"],
            ["background", "worker"],
            ["scheduler"],
            ["install", "packages"],
            ["stage", "commit", "push"],
            ["route", "mutation", "outside"],
            ["queue", "mutation"],
            ["commit", "local", "password", "config"],
            ["trust", "generated", "proposal"],
            ["promote", "generated", "proposal"],
        ],
    )


def check_sequence(check: Check, sequence: Any) -> None:
    if sequence != EXPECTED_SEQUENCE:
        check.fail("future_implementation_sequence does not match required ordered sequence")
        return
    check.passed("future_implementation_sequence")


def skip_dir(path: Path) -> bool:
    parts = set(path.parts)
    return bool(parts & EXCLUDED_DIRS)


def source_like_memory_file(path: Path) -> bool:
    return path.name == "ROUTE_VERIFICATION_SET_V1.json"


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

    bounded: list[Path] = []
    for path in files:
        if skip_dir(path):
            continue
        if path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        if path == Path(__file__).resolve():
            continue
        bounded.append(path)
    return sorted(set(bounded))


def safe_line(line: str, path: Path) -> bool:
    lowered = line.lower()
    if path.name.startswith("verify_"):
        return True
    safe_markers = [
        "false",
        "forbidden",
        "not allowed",
        "must not",
        "never",
        "disabled",
        "future",
        "contract_only",
        "no_",
        "no ",
    ]
    return any(marker in lowered for marker in safe_markers)


def active_source_scan(check: Check) -> None:
    for module in FUTURE_MODULES:
        module_path = ROOT / module
        if module_path.exists():
            if (
                module == "engel_debruijn_quantum_runtime.py"
                and RUNTIME_IMPLEMENTATION_VERIFIER.exists()
                and RUNTIME_IMPLEMENTATION_REPORT.exists()
            ):
                check.passed("approved runtime module implementation present with verifier/report evidence")
            elif (
                module == "engel_debruijn_quantum_apply.py"
                and APPLY_IMPLEMENTATION_VERIFIER.exists()
                and APPLY_IMPLEMENTATION_REPORT.exists()
            ):
                check.passed("approved apply module implementation present with verifier/report evidence")
            else:
                check.fail(f"future runtime/apply/build module already exists without approved evidence: {rel(module_path)}")

    dangerous_regexes = [
        r"\bfrom\s+engel_debruijn_quantum_(runtime|apply|build_promote)\b",
        r"\bimport\s+engel_debruijn_quantum_(runtime|apply|build_promote)\b",
        r"\bdef\s+[a-zA-Z0-9_]*apply_verified_proposal\b",
        r"\bdef\s+[a-zA-Z0-9_]*build_promote\b",
        r"\bAPPROVE_DEBRUIJN_QUANTUM_APPLY_VERIFIED_PROPOSAL_V1\b.*\b(route|handler|command)\b",
        r"\bAPPROVE_DEBRUIJN_QUANTUM_BUILD_PROMOTE_V1\b.*\b(route|handler|command)\b",
        r"\bruntime_enabled_now\s*[:=]\s*true\b",
        r"\bapply_enabled_now\s*[:=]\s*true\b",
        r"\bbuild_promote_enabled_now\s*[:=]\s*true\b",
        r"\btrusted_memory_write_enabled_now\s*[:=]\s*true\b",
        r"\broute_mutation_enabled_now\s*[:=]\s*true\b",
        r"\bqueue_mutation_enabled_now\s*[:=]\s*true\b",
        r"\bprovider_api_enabled_now\s*[:=]\s*true\b",
        r"\bnetwork_enabled_now\s*[:=]\s*true\b",
        r"\blocal_llm_inference_enabled_now\s*[:=]\s*true\b",
        r"\bbackground_worker_enabled_now\s*[:=]\s*true\b",
    ]
    debruijn_build_regexes = [
        r"\bauto_apply\b",
        r"\bauto_build\b",
        r"\bauto_promote\b",
        r"\bpyinstaller\b",
        r"\bgit\s+commit\b",
        r"\bgit\s+add\b",
        r"\bsubprocess\.[^(]*\(.*(build|promote)",
    ]

    scanned = 0
    for path in iter_active_scan_files():
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError as exc:
            check.review(f"could not scan {rel(path)}: {exc}")
            continue
        scanned += 1
        path_text = rel(path)
        for number, line in enumerate(lines, start=1):
            lowered = line.lower()
            if safe_line(line, path):
                continue
            for pattern in dangerous_regexes:
                if re.search(pattern, lowered, flags=re.IGNORECASE):
                    check.fail(f"active runtime/apply/build pattern {pattern!r} at {path_text}:{number}")
            if "debruijn" in lowered or "de bruijn" in lowered:
                for pattern in debruijn_build_regexes:
                    if re.search(pattern, lowered, flags=re.IGNORECASE):
                        check.fail(f"active De Bruijn build/git pattern {pattern!r} at {path_text}:{number}")
    check.passed(f"active source scan result scanned={scanned}")


def main() -> int:
    check = Check()
    print("ENGEL_DEBRUIJN_QUANTUM_RUNTIME_APPLY_BUILD_CONTRACT_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: contract validation only; no runtime, apply, build, provider, model, route, queue, git, or trusted-memory mutation")

    check_required_files(check)
    payload = load_json(check, CONTRACT_JSON) if CONTRACT_JSON.exists() else None
    if payload is not None:
        check_json_contract(check, payload)
        check_runtime_plan(check, payload.get("runtime_engine_plan"))
        check_apply_plan(check, payload.get("apply_engine_plan"))
        check_build_plan(check, payload.get("build_promote_engine_plan"))
        check_approval_phrases(check, payload)
        check_required_gates(check, payload.get("required_gates"))
        check_receipt_model(check, payload.get("receipt_model"))
        check_lane_model(check, payload.get("lane_model"))
        check_forbidden_behavior(check, payload.get("forbidden_behavior"))
        check_sequence(check, payload.get("future_implementation_sequence"))
    active_source_scan(check)

    if check.review_required:
        check.line("INFO", f"review_required_findings={len(check.review_required)}")
    if check.failures:
        check.line("FAIL", f"failure_count={len(check.failures)}")
        return 1

    check.passed("contract check result")
    check.passed("runtime plan result")
    check.passed("apply plan result")
    check.passed("build/promote plan result")
    check.passed("approval phrase result")
    check.passed("required gates result")
    check.passed("receipt model result")
    check.passed("lane model result")
    check.passed("forbidden behavior result")
    check.passed("safety preserved")
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
