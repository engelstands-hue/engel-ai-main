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
WORKSPACE = Path(r"D:\b.WorkSpace\Engel App")
PROPOSAL_DIR = ROOT / "reports" / "debruijn_quantum_file_structure"
CONTRACT_JSON = ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1.json"
BASE_VERIFIER = ROOT / "tools" / "verify_engel_debruijn_quantum_automation_file_structure.py"

PASS_MARKER = "DEBRUIJN_QUANTUM_CANDIDATE_PROPOSAL_VERIFICATION_PASS"

PROPOSAL_LIST_KEYS = ("proposals", "candidate_proposals", "fixes")
REQUIRED_SAFETY_FIELDS = {
    "trust_status": "untrusted_candidate",
    "apply_allowed": False,
    "human_review_required": True,
}

FALSE_IF_PRESENT_FIELDS = [
    "runtime_enabled",
    "autorun_enabled",
    "source_mutation_allowed",
    "file_mutation_allowed",
    "route_mutation_allowed",
    "queue_mutation_allowed",
    "trusted_memory_write_allowed",
    "memory_promotion_allowed",
    "candidate_execution_allowed",
    "provider_api_allowed",
    "network_allowed",
    "model_inference_allowed",
    "real_quantum_allowed",
    "background_worker_allowed",
    "startup_autorun_allowed",
    "package_install_allowed",
    "mobile_runtime_allowed",
    "remote_queen_runtime_allowed",
]

TOP_LEVEL_FALSE_IF_PRESENT = [
    "apply_allowed",
    "runtime_enabled",
    "autorun_enabled",
    "source_mutation_allowed",
    "file_mutation_allowed",
    "route_mutation_allowed",
    "queue_mutation_allowed",
    "trusted_memory_write_allowed",
    "memory_promotion_allowed",
    "candidate_execution_allowed",
    "provider_api_allowed",
    "network_allowed",
    "model_inference_allowed",
    "real_quantum_allowed",
    "background_worker_allowed",
    "startup_autorun_allowed",
    "package_install_allowed",
    "mobile_runtime_allowed",
    "remote_queen_runtime_allowed",
]

FORBIDDEN_CLAIMS = [
    "approved",
    "trusted",
    "apply_now",
    "auto_apply",
    "safe_to_apply_without_review",
    "promote_to_trusted_memory",
    "write_trusted_memory",
    "mutate_routes",
    "mutate_queues",
    "execute_command",
    "run_script",
    "install_package",
    "call_provider",
    "call_network",
    "run_model",
    "quantum_run",
    "activate_agent",
    "start_worker",
    "startup_autorun",
    "delete_file",
    "move_file",
    "rewrite_source",
]

EXECUTABLE_PATTERNS = [
    r"\bpowershell\b",
    r"\bcmd\.exe\b",
    r"\bbash\b",
    r"\bsh\s+",
    r"\bpython\s+-c\b",
    r"\bos\.system\b",
    r"\bsubprocess\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bStart-Process\b",
    r"\bInvoke-WebRequest\b",
    r"\bcurl\b",
    r"\bwget\b",
    r"\bpip\s+install\b",
    r"\bnpm\s+install\b",
    r"\bgit\s+commit\b",
    r"\bgit\s+add\b",
    r"\bgit\s+push\b",
    r"\bRemove-Item\b",
    r"\bdel\s+",
    r"\brmdir\b",
    r"\bshutil\.rmtree\b",
    r"\bos\.remove\b",
    r"\bunlink\b",
    r"\bmove\s+",
    r"\bcopy\s+",
    r"\bxcopy\b",
    r"\brobocopy\b",
    r"\btrusted\s+memory\b",
    r"\bAPPROVE_",
    r"\bAPI\s*key\b",
    r"\btoken\b",
    r"\bpassword\b",
]

SAFE_NEGATION_MARKERS = [
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
    "fail closed",
    "fail-closed",
]

PATH_FIELD_NAMES = {
    "target",
    "target_path",
    "affected_path",
    "affected_file",
    "affected_files",
    "path",
    "file_path",
    "suggested_file",
    "suggested_files",
    "suggested_files_to_create",
}

EXECUTABLE_OUTPUT_SUFFIXES = {
    ".exe",
    ".dll",
    ".msi",
    ".bat",
    ".cmd",
    ".ps1",
    ".sh",
    ".scr",
    ".com",
}

ACTIVE_SOURCE_FILES = [
    ROOT / "engel_debruijn_quantum_automation_file_structure.py",
    ROOT / "engel_debruijn_quantum_structure_status.py",
    ROOT / "tools" / "verify_engel_debruijn_quantum_automation_file_structure.py",
    ROOT / "tools" / "verify_debruijn_quantum_structure_status_helper.py",
    ROOT / "tools" / "verify_debruijn_quantum_backend_status_command.py",
]

ACTIVE_UNSAFE_PATTERNS = [
    "apply_candidate_proposals",
    "apply_candidate_proposal",
    "trust_candidate_proposals",
    "trust_candidate_proposal",
    "promote_candidate_proposals",
    "promote_candidate_proposal",
    "execute_proposal_content",
    "run_proposal",
    "proposal_to_trusted_memory",
    "proposal_route_mutation",
    "proposal_queue_mutation",
    "rewrite_source_from_proposal",
    "move_files_from_proposal",
    "delete_files_from_proposal",
    "provider_from_proposal",
    "network_from_proposal",
    "model_from_proposal",
    "quantum_from_proposal",
]


@dataclass
class ProposalSummary:
    path: str
    proposal_count: int = 0
    malformed_count: int = 0
    unsafe_count: int = 0
    review_required_count: int = 0
    proposal_types: dict[str, int] = field(default_factory=dict)
    target_groups: dict[str, int] = field(default_factory=dict)
    all_apply_allowed_false: bool = True
    all_untrusted_candidate: bool = True
    all_human_review_required: bool = True


class Verifier:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.review_required: list[str] = []
        self.warnings: list[str] = []
        self.summaries: list[ProposalSummary] = []

    def line(self, level: str, message: str) -> None:
        print(f"{level} {message}")

    def fail(self, message: str) -> None:
        self.failures.append(message)
        self.line("FAIL", message)

    def review(self, message: str) -> None:
        self.review_required.append(message)
        self.line("REVIEW_REQUIRED", message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        self.line("INFO", message)

    def pass_line(self, message: str) -> None:
        self.line("PASS", message)


def relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def load_json(path: Path, verifier: Verifier) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        verifier.fail(f"malformed JSON {relative(path)} line={exc.lineno} column={exc.colno}")
    except OSError as exc:
        verifier.fail(f"cannot read {relative(path)}: {exc}")
    return None


def extract_proposals(payload: Any, path: Path, verifier: Verifier) -> tuple[list[Any], dict[str, Any]]:
    if isinstance(payload, list):
        return payload, {}
    if not isinstance(payload, dict):
        verifier.fail(f"{relative(path)} unknown proposal shape: top-level JSON must be list or object")
        return [], {}
    for key in PROPOSAL_LIST_KEYS:
        value = payload.get(key)
        if value is not None:
            if isinstance(value, list):
                return value, payload
            verifier.fail(f"{relative(path)} has non-list {key!r} field")
            return [], payload
    verifier.fail(
        f"{relative(path)} unknown proposal shape: expected proposals, candidate_proposals, or fixes list"
    )
    return [], payload


def safe_context(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in SAFE_NEGATION_MARKERS)


def walk_strings(value: Any, prefix: str = "") -> list[tuple[str, str]]:
    strings: list[tuple[str, str]] = []
    if isinstance(value, str):
        strings.append((prefix, value))
    elif isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            strings.extend(walk_strings(child, child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_prefix = f"{prefix}[{index}]"
            strings.extend(walk_strings(child, child_prefix))
    return strings


def normalize_claim(text: str) -> str:
    return re.sub(r"[\s\-]+", "_", text.lower())


def has_forbidden_claim(text: str, claim: str) -> bool:
    lowered = text.lower()
    normalized = normalize_claim(text)
    if claim == "trusted":
        return re.search(r"\btrusted\b", lowered) is not None
    if claim == "approved":
        return re.search(r"\bapproved\b", lowered) is not None
    return claim in normalized


def check_text_payloads(item: dict[str, Any], context: str, verifier: Verifier) -> None:
    for field_path, text in walk_strings(item):
        if not text.strip():
            continue
        for claim in FORBIDDEN_CLAIMS:
            if has_forbidden_claim(text, claim) and not safe_context(text):
                verifier.fail(f"{context} forbidden claim {claim!r} in {field_path}")
        for pattern in EXECUTABLE_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE) and not safe_context(text):
                verifier.review(f"{context} executable or sensitive payload pattern {pattern!r} in {field_path}")


def is_under_workspace(path: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(WORKSPACE.resolve(strict=False))
        return True
    except ValueError:
        return False


def target_group(path_text: str) -> str:
    normalized = path_text.replace("/", "\\").lstrip("\\")
    first = normalized.split("\\", 1)[0] if normalized else "missing"
    return first or "missing"


def iter_path_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        paths: list[str] = []
        for child in value:
            paths.extend(iter_path_values(child))
        return paths
    return []


def check_target_path(
    path_text: str,
    context: str,
    proposal: dict[str, Any],
    summary: ProposalSummary,
    verifier: Verifier,
) -> None:
    stripped = path_text.strip()
    if not stripped:
        verifier.warn(f"{context} empty target path ignored")
        return
    summary.target_groups[target_group(stripped)] = summary.target_groups.get(target_group(stripped), 0) + 1

    if stripped.startswith("\\\\") or stripped.startswith("//") or "://" in stripped:
        verifier.fail(f"{context} target path is network/URI path: {stripped}")
        return

    candidate = Path(stripped)
    if candidate.is_absolute() and not is_under_workspace(candidate):
        verifier.fail(f"{context} target path outside workspace: {stripped}")
        return

    if not candidate.is_absolute():
        try:
            resolved = (WORKSPACE / candidate).resolve(strict=False)
        except OSError as exc:
            verifier.fail(f"{context} target path cannot resolve: {stripped}: {exc}")
            return
        if not is_under_workspace(resolved):
            verifier.fail(f"{context} target path escapes workspace: {stripped}")
            return

    suffix = candidate.suffix.lower()
    if suffix in EXECUTABLE_OUTPUT_SUFFIXES:
        verifier.fail(f"{context} target path has executable output suffix {suffix}: {stripped}")

    normalized = stripped.lower().replace("/", "\\")
    review_only = (
        proposal.get("apply_allowed") is False
        and proposal.get("human_review_required") is True
        and proposal.get("trust_status") == "untrusted_candidate"
    )
    if "memory\\engel_trusted_memory" in normalized or "trusted_memory" in normalized:
        verifier.fail(f"{context} target path references trusted-memory target: {stripped}")
    if ("routes" in normalized or "route" in normalized) and not review_only:
        verifier.fail(f"{context} route target is not strictly review-only: {stripped}")


def check_paths(item: dict[str, Any], context: str, summary: ProposalSummary, verifier: Verifier) -> None:
    found = False
    for key, value in item.items():
        if key in PATH_FIELD_NAMES:
            path_values = iter_path_values(value)
            if path_values:
                found = True
            for path_text in path_values:
                check_target_path(path_text, context, item, summary, verifier)
    if not found:
        action_text = " ".join(text for _, text in walk_strings(item)).lower()
        action_like = any(word in action_text for word in ("create", "fix", "repair", "rewrite", "move", "delete"))
        if action_like:
            summary.review_required_count += 1
            verifier.review(f"{context} action-like proposal has no target/affected path")
        else:
            verifier.warn(f"{context} has no target/affected path; treated as report-only")


def check_top_level(container: dict[str, Any], path: Path, verifier: Verifier) -> None:
    if not container:
        return
    status = container.get("status", container.get("trust_status"))
    if status is not None and status != "untrusted_candidate":
        verifier.fail(f"{relative(path)} top-level status/trust_status is not untrusted_candidate")
    if container.get("human_review_required") is not None and container.get("human_review_required") is not True:
        verifier.fail(f"{relative(path)} top-level human_review_required is not true")
    for key in TOP_LEVEL_FALSE_IF_PRESENT:
        if key in container and container.get(key) is not False:
            verifier.fail(f"{relative(path)} top-level {key} must be false when present")


def check_proposal_item(
    item: Any,
    file_path: Path,
    index: int,
    summary: ProposalSummary,
    verifier: Verifier,
) -> None:
    context = f"{relative(file_path)} proposal[{index}]"
    summary.proposal_count += 1
    if not isinstance(item, dict):
        summary.malformed_count += 1
        verifier.fail(f"{context} is not an object")
        return

    for key, expected in REQUIRED_SAFETY_FIELDS.items():
        actual = item.get(key)
        if actual != expected:
            summary.unsafe_count += 1
            if key == "trust_status":
                summary.all_untrusted_candidate = False
            elif key == "apply_allowed":
                summary.all_apply_allowed_false = False
            elif key == "human_review_required":
                summary.all_human_review_required = False
            verifier.fail(f"{context} {key} expected {expected!r}, got {actual!r}")

    for key in FALSE_IF_PRESENT_FIELDS:
        if key in item and item.get(key) is not False:
            summary.unsafe_count += 1
            verifier.fail(f"{context} {key} must be false when present")

    proposal_type = str(item.get("proposal_type") or item.get("type") or "unknown")
    summary.proposal_types[proposal_type] = summary.proposal_types.get(proposal_type, 0) + 1

    if not (item.get("proposal_id") or item.get("id")):
        verifier.warn(f"{context} missing proposal_id/id")
    if proposal_type == "unknown":
        verifier.warn(f"{context} missing proposal_type/type")
    descriptive_keys = {"source", "reason", "finding", "recommendation", "proposed_action", "detected_issue"}
    if not any(key in item for key in descriptive_keys):
        verifier.warn(f"{context} has limited descriptive fields")
    if "safety_flags" not in item and "boundaries" not in item:
        missing_safety_booleans = [key for key in FALSE_IF_PRESENT_FIELDS if key not in item]
        if len(missing_safety_booleans) == len(FALSE_IF_PRESENT_FIELDS):
            verifier.warn(f"{context} has no safety_flags/boundaries and no optional false safety fields")

    check_text_payloads(item, context, verifier)
    check_paths(item, context, summary, verifier)


def validate_proposal_file(path: Path, verifier: Verifier) -> None:
    payload = load_json(path, verifier)
    if payload is None:
        return

    proposals, container = extract_proposals(payload, path, verifier)
    summary = ProposalSummary(path=relative(path))
    check_top_level(container, path, verifier)

    declared_count = container.get("proposal_count") if isinstance(container, dict) else None
    if declared_count is not None and declared_count != len(proposals):
        verifier.warn(
            f"{relative(path)} proposal_count={declared_count!r} does not match proposals length={len(proposals)}"
        )

    for index, item in enumerate(proposals):
        check_proposal_item(item, path, index, summary, verifier)

    if summary.proposal_count == 0:
        verifier.pass_line(f"{relative(path)} contains zero proposals; top-level safety checked")
    else:
        verifier.pass_line(
            f"{relative(path)} proposals={summary.proposal_count} types={dict(sorted(summary.proposal_types.items()))}"
        )
    verifier.summaries.append(summary)


def check_contract_and_base(verifier: Verifier) -> None:
    if not CONTRACT_JSON.exists():
        verifier.fail(f"missing contract JSON {relative(CONTRACT_JSON)}")
        return
    payload = load_json(CONTRACT_JSON, verifier)
    if isinstance(payload, dict):
        if payload.get("contract_id") != "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1":
            verifier.fail("contract_id mismatch in De Bruijn contract")
        else:
            verifier.pass_line("base De Bruijn contract present")
    if not BASE_VERIFIER.exists():
        verifier.fail(f"missing base verifier {relative(BASE_VERIFIER)}")
        return
    try:
        py_compile.compile(str(BASE_VERIFIER), doraise=True)
        verifier.pass_line("base De Bruijn verifier compiles; run separately by verification stack")
    except py_compile.PyCompileError as exc:
        verifier.fail(f"base De Bruijn verifier does not compile: {exc}")


def safe_source_line(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in SAFE_NEGATION_MARKERS) or "forbidden" in lowered


def active_source_scan(verifier: Verifier) -> None:
    scanned = 0
    for path in ACTIVE_SOURCE_FILES:
        if not path.exists():
            verifier.warn(f"optional active source missing {relative(path)}")
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError as exc:
            verifier.fail(f"cannot read active source {relative(path)}: {exc}")
            continue
        scanned += 1
        is_verifier = path.name.startswith("verify_")
        for line_number, line in enumerate(lines, start=1):
            lowered = line.lower()
            for pattern in ACTIVE_UNSAFE_PATTERNS:
                if pattern in lowered and not (is_verifier or safe_source_line(line)):
                    verifier.review(f"{relative(path)}:{line_number} active proposal behavior pattern {pattern}")
    verifier.pass_line(f"active source scan result scanned={scanned}")


def main() -> int:
    verifier = Verifier()
    print("ENGEL_DEBRUIJN_QUANTUM_CANDIDATE_PROPOSAL_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: local proposal verification only; no scan, apply, trust, execution, provider, model, or mutation")

    check_contract_and_base(verifier)

    if not PROPOSAL_DIR.exists():
        verifier.line("SKIP", f"proposal folder missing: {relative(PROPOSAL_DIR)}")
    else:
        proposal_files = sorted(PROPOSAL_DIR.glob("candidate_fix_proposals_*.json"))
        if not proposal_files:
            verifier.line("SKIP", "no De Bruijn candidate proposal files exist")
        else:
            verifier.line("INFO", f"proposal files discovered {len(proposal_files)}")
            for path in proposal_files:
                validate_proposal_file(path, verifier)

    active_source_scan(verifier)

    print("PROPOSAL_FILE_SUMMARIES")
    for summary in verifier.summaries:
        print(
            json.dumps(
                {
                    "path": summary.path,
                    "proposal_count": summary.proposal_count,
                    "malformed_count": summary.malformed_count,
                    "unsafe_count": summary.unsafe_count,
                    "review_required_count": summary.review_required_count,
                    "proposal_types": dict(sorted(summary.proposal_types.items())),
                    "target_groups": dict(sorted(summary.target_groups.items())),
                    "all_apply_allowed_false": summary.all_apply_allowed_false,
                    "all_untrusted_candidate": summary.all_untrusted_candidate,
                    "all_human_review_required": summary.all_human_review_required,
                },
                sort_keys=True,
            )
        )

    if verifier.warnings:
        verifier.line("INFO", f"warnings={len(verifier.warnings)}")
    if verifier.review_required:
        verifier.line("FAIL", f"review_required findings={len(verifier.review_required)}")
    if verifier.failures:
        verifier.line("FAIL", f"failures={len(verifier.failures)}")
    if verifier.failures or verifier.review_required:
        return 1

    verifier.pass_line("proposal schema result")
    verifier.pass_line("proposal safety field result")
    verifier.pass_line("executable payload scan result")
    verifier.pass_line("target path safety result")
    verifier.pass_line("active source scan result")
    verifier.pass_line("safety preserved")
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
