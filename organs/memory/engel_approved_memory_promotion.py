from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import textwrap

import engel_trusted_memory_target
import engel_global_password_gate as global_password_gate


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
CONTRACT_JSON = ROOT / "memory" / "ENGEL_APPROVED_MEMORY_PROMOTION_CONTRACT_V1.json"
CANONICAL_CANDIDATE_ROOTS = [
    ROOT / "reports" / "memory_candidates",
    ROOT / "reports" / "memory_candidate_proposals",
]
RECEIPT_ROOT = ROOT / "reports" / "memory_promotion_receipts"
APPROVAL_TOKEN = "APPROVE_PROMOTE_MEMORY_CANDIDATE"
TRUSTED_MEMORY_TARGET_STATUS = "TARGET_CONTRACT_REQUIRED"
TRUSTED_MEMORY_TARGET_IMPLEMENTED = False
TRUSTED_MEMORY_DESTINATION = "memory\\ENGEL_TRUSTED_MEMORY_V1.jsonl"
MAX_WARNING_SCAN_BYTES = 65536
MAX_HASH_BYTES = 2 * 1024 * 1024

STATUS_LABELS = [
    "APPROVED_MEMORY_PROMOTION",
    "PROTECTED_MEMORY_PROMOTION",
    "LOCAL_ONLY",
    "MEMORY_CANDIDATES_ARE_NOT_MEMORY",
    "CANDIDATE_ONLY_UNTIL_APPROVED",
    "HUMAN_APPROVAL_REQUIRED",
    "APPROVAL_TOKEN_REQUIRED",
    "PASSWORD_GATE_REQUIRED",
    "PROTECTED_ACTION_REQUIRED",
    "RECEIPTS_REQUIRED",
    "NO_AUTOMATIC_MEMORY_PROMOTION",
    "NO_AUTO_PROMOTION",
    "NO_BULK_PROMOTION",
    "NO_SELF_APPROVAL",
    "NO_FAKE_APPROVALS",
    "NO_FAKE_RECEIPTS",
    "NO_FAKE_PROMOTED_MEMORY",
    "NO_SOURCE_MUTATION",
    "NO_ROUTE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_RUN_JOBS",
    "NO_MODEL_LOADING",
    "NO_INFERENCE",
    "NO_TRAINING",
    "NO_WSL_EXECUTION",
    "NO_HERMES_EXECUTION",
    "NO_ANDROID_CONNECTION",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_PACKAGE_INSTALL",
    "NO_MODEL_DOWNLOAD",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
    "HERMES_APPROVED_FOR_LOCAL_TESTING_HUMAN_DRIVEN_ONLY",
]

PROMOTION_STATES = [
    "discovered_candidate",
    "schema_validated",
    "needs_human_review",
    "rejected",
    "approval_required",
    "approved_for_promotion",
    "promoted_by_engel",
    "promotion_failed",
    "archived",
]

WARNING_PATTERNS = {
    "shell_command_reference": ["```bash", "```sh", "powershell", "cmd.exe", "wsl ", "chmod ", "curl ", "Invoke-WebRequest"],
    "python_code_block": ["```python", "python -c", "python.exe", "import os", "import subprocess"],
    "route_or_source_mutation_instruction": ["mutate route", "change route", "source mutation", "edit source", "edit command map"],
    "trusted_memory_write_instruction": ["write trusted memory", "trusted-memory write", "mark as trusted", "trusted memory write"],
    "approval_token_claim": ["APPROVE_", "approval token", "human approved", "simulate approval", "impersonate approval"],
    "provider_network_api_instruction": ["provider api", "network call", "openai", "requests.", "urllib", "socket", "api key"],
    "model_runtime_instruction": ["load model", "run inference", "train model", "fine tune", "model loading"],
    "package_or_model_download_instruction": ["pip install", "npm install", "install package", "download model", "download file"],
    "startup_autoload_instruction": ["startup autorun", "scheduled task", "auto-load", "autoload", "start at boot"],
    "remote_worker_or_queen_control_instruction": ["control remote queen", "create new queen", "queen authority", "android runtime"],
    "hermes_reference": ["Hermes", "Hermes Agent", "Hermes-style"],
    "prompt_injection_language": ["ignore previous instructions", "ignore all instructions", "bypass safety", "disable safety"],
    "hidden_instruction_language": ["hide this from the user", "do not tell the user", "delete logs", "delete receipts"],
    "engel_bible_app_scope_warning": ["Engel Bible App", "Bible App"],
    "secret_or_sensitive_data_pattern": ["BEGIN PRIVATE KEY", "api_key", "password=", "secret=", "token="],
}


class ApprovedMemoryPromotionError(ValueError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def project_relative(path: Path) -> str:
    return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")


NON_CANDIDATE_NAME_MARKERS = (
    "REJECTION_RECORD",
    "AUDIT_RECORD",
    "REVIEW_NOTE",
    "REVIEW_DECISION",
)


def safe_candidate_files() -> list[Path]:
    files: list[Path] = []
    for root in CANONICAL_CANDIDATE_ROOTS:
        resolved_root = root.resolve(strict=False)
        if not is_relative_to(resolved_root, ROOT):
            raise ApprovedMemoryPromotionError("candidate root escaped Engel App")
        if not resolved_root.exists() or not resolved_root.is_dir():
            continue
        for child in resolved_root.iterdir():
            if not (child.is_file() and child.name != ".gitkeep" and child.suffix.lower() in {".md", ".json"}):
                continue
            upper_name = child.name.upper()
            if any(marker in upper_name for marker in NON_CANDIDATE_NAME_MARKERS):
                continue
            files.append(child.resolve(strict=False))
    return sorted(files)


def read_bounded_text(path: Path) -> str:
    with path.open("rb") as handle:
        data = handle.read(MAX_WARNING_SCAN_BYTES)
    return data.decode("utf-8", errors="replace")


def lightweight_hash(path: Path) -> str:
    if path.stat().st_size > MAX_HASH_BYTES:
        return "SKIPPED_TOO_LARGE_FOR_LIGHTWEIGHT_HASH"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def warning_flags_for_text(text: str) -> list[str]:
    lowered = text.lower()
    flags: list[str] = []
    for flag, patterns in WARNING_PATTERNS.items():
        if any(pattern.lower() in lowered for pattern in patterns):
            flags.append(flag)
    return flags


def ascii_safe(text: str) -> str:
    return text.encode("ascii", errors="replace").decode("ascii")


def parse_markdown_candidate(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current is not None:
            fields[current] = "\n".join(buffer).strip()

    simple_labels = {
        "Sources": "source_type",
        "Candidate Memory": "proposed_memory_text",
        "Guardian Review": "reason",
        "Recommended Josh Decision": "scope",
        "Safety": "safety_boundary",
        "Untrusted Content Guard": "risk_level",
    }
    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current = line[3:].strip().lower().replace(" ", "_")
            buffer = []
            continue
        label = line.strip().rstrip(":")
        if line and not line.startswith("-") and label in simple_labels:
            flush()
            current = simple_labels[label]
            buffer = []
            continue
        if current is not None:
            buffer.append(line)
    flush()
    return fields


def load_candidate_payload(path: Path) -> dict[str, str]:
    text = read_bounded_text(path)
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            payload = {}
        return {str(key): str(value) for key, value in payload.items() if isinstance(value, (str, int, float, bool))}
    payload = parse_markdown_candidate(text)
    if not payload.get("proposed_memory_text") and "Candidate Memory:" in text:
        payload["proposed_memory_text"] = text.split("Candidate Memory:", 1)[1].strip()
    return payload


def candidate_id_for(path: Path) -> str:
    seed = f"{project_relative(path)}|{path.stat().st_size}|{path.stat().st_mtime_ns}".encode("utf-8")
    return "approved_memory_candidate_" + hashlib.sha256(seed).hexdigest()[:16]


def resolve_candidate(candidate: str) -> Path:
    if not candidate or candidate.startswith(("http://", "https://", "\\\\")):
        raise ApprovedMemoryPromotionError("candidate must be an explicit local file name or path")
    if any(marker in candidate for marker in ("*", "?", "[")):
        raise ApprovedMemoryPromotionError("wildcards are not accepted")
    raw = Path(candidate)
    if raw.is_absolute():
        path = raw.resolve(strict=False)
    else:
        path = (ROOT / raw).resolve(strict=False)
        if not path.exists():
            matches = [item for item in safe_candidate_files() if item.name == candidate]
            if len(matches) == 1:
                path = matches[0]
            elif len(matches) > 1:
                raise ApprovedMemoryPromotionError("candidate file name is ambiguous; provide an explicit path")
    allowed = any(is_relative_to(path, root) for root in CANONICAL_CANDIDATE_ROOTS)
    if not allowed:
        raise ApprovedMemoryPromotionError("candidate must be under reports\\memory_candidates or reports\\memory_candidate_proposals")
    if not path.exists() or not path.is_file():
        raise ApprovedMemoryPromotionError("candidate file does not exist")
    if path.suffix.lower() not in {".md", ".json"}:
        raise ApprovedMemoryPromotionError("candidate must be a .md or .json file")
    return path


def validation_for(path: Path) -> dict[str, object]:
    text = read_bounded_text(path)
    payload = load_candidate_payload(path)
    flags = warning_flags_for_text(text)
    proposed_memory_text = payload.get("proposed_memory_text", "").strip()
    stop_reasons: list[str] = []
    if not path.exists() or not path.is_file():
        stop_reasons.append("source file missing")
    if not is_relative_to(path, ROOT):
        stop_reasons.append("source is not local to Engel App")
    if "Hermes" in text or "Hermes Agent" in text or "Hermes-style" in text:
        stop_reasons.append("candidate references Hermes/Hermes-style runtime; rejected for this computer")
    if "Engel Bible App" in text and "Engel App" not in text:
        stop_reasons.append("candidate appears scoped to Engel Bible App, not Engel App")
    if not proposed_memory_text:
        stop_reasons.append("proposed memory text missing or not detectable")
    if flags:
        stop_reasons.append("warning flags require human review before promotion")
    if any(flag in flags for flag in [
        "prompt_injection_language",
        "hidden_instruction_language",
        "provider_network_api_instruction",
        "model_runtime_instruction",
        "route_or_source_mutation_instruction",
        "package_or_model_download_instruction",
        "secret_or_sensitive_data_pattern",
    ]):
        stop_reasons.append("high-risk content flags require rejection or quarantine before promotion")
    validation_status = "schema_validated" if proposed_memory_text and not stop_reasons else "needs_human_review"
    if "hermes_reference" in flags:
        validation_status = "rejected"
    return {
        "validation_status": validation_status,
        "warning_flags": flags,
        "stop_reasons": stop_reasons,
        "payload": payload,
    }


def candidate_metadata(path: Path) -> dict[str, object]:
    validation = validation_for(path)
    payload = validation["payload"]
    assert isinstance(payload, dict)
    stat = path.stat()
    return {
        "candidate_id": candidate_id_for(path),
        "source_path": project_relative(path),
        "source_type": "memory_candidate_proposal",
        "proposed_memory_text": str(payload.get("proposed_memory_text", ""))[:4000],
        "reason": str(payload.get("reason", "requires human review")),
        "scope": str(payload.get("scope", "Engel App memory candidate review")),
        "risk_level": str(payload.get("risk_level", "untrusted_candidate")),
        "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_hash": lightweight_hash(path),
        "warning_flags": validation["warning_flags"],
        "validation_status": validation["validation_status"],
        "approval_status": "approval_required",
        "promotion_status": "discovered_candidate",
        "receipt_path": "",
        "size_bytes": stat.st_size,
        "stop_reasons": validation["stop_reasons"],
    }


def discover_candidates() -> list[dict[str, object]]:
    return [candidate_metadata(path) for path in safe_candidate_files()]


def status_payload() -> dict[str, object]:
    candidates = discover_candidates()
    target_status = trusted_memory_target_status()
    counts_by_status: dict[str, int] = {}
    warning_count = 0
    for item in candidates:
        status = str(item["validation_status"])
        counts_by_status[status] = counts_by_status.get(status, 0) + 1
        if item["warning_flags"]:
            warning_count += 1
    return {
        "schema_version": "1.0",
        "generated_at": now_utc(),
        "module": "Engel Approved Memory Promotion V1",
        "status": STATUS_LABELS,
        "candidate_roots_scanned_nonrecursive": [project_relative(root) for root in CANONICAL_CANDIDATE_ROOTS],
        "receipt_root": project_relative(RECEIPT_ROOT),
        "candidate_count": len(candidates),
        "warning_candidate_count": warning_count,
        "counts_by_validation_status": counts_by_status,
        "trusted_memory_target_status": target_status["target_status"],
        "trusted_memory_target_implemented": target_status["enabled"],
        "trusted_memory_target_path": target_status["target_path"],
        "trusted_memory_target_write_blocked_reason": target_status["write_blocked_reason"],
        "empty_state": len(candidates) == 0,
        "candidates": candidates,
        "safety_boundary": {
            "auto_promote_memory": False,
            "bulk_promote_memory": False,
            "trusted_memory_write_without_approval": False,
            "source_mutation": False,
            "route_mutation": False,
            "patch_apply": False,
            "run_learning_jobs": False,
            "model_loading": False,
            "inference": False,
            "training": False,
            "wsl_execution": False,
            "hermes_execution": False,
            "android_connection": False,
            "provider_network_browser_api": False,
            "background_worker": False,
            "startup_autorun": False,
            "fake_approvals": False,
            "fake_promoted_memory": False,
        },
    }


def render_status() -> str:
    payload = status_payload()
    lines = [
        "Engel Approved Memory Promotion V1",
        "",
        "Status:",
        *[f"- {label}" for label in STATUS_LABELS],
        "",
        f"Candidate count: {payload['candidate_count']}",
        f"Warning candidate count: {payload['warning_candidate_count']}",
        f"Trusted memory target status: {payload['trusted_memory_target_status']}",
        f"Trusted memory target path: {payload['trusted_memory_target_path']}",
        f"Trusted memory target blocked reason: {payload['trusted_memory_target_write_blocked_reason']}",
        f"Trusted memory target implemented: {payload['trusted_memory_target_implemented']}",
        "",
        "Counts by validation status:",
    ]
    counts = payload["counts_by_validation_status"]
    if isinstance(counts, dict) and counts:
        lines.extend(f"- {key}: {value}" for key, value in sorted(counts.items()))
    else:
        lines.append("- none")
    lines.extend([
        "",
        "Memory candidates are not memory.",
        "Only Engel-controlled, human-approved promotion may write trusted memory.",
    ])
    return "\n".join(lines) + "\n"


def render_candidates() -> str:
    candidates = discover_candidates()
    if not candidates:
        return "No memory candidate proposals found in the approved promotion scope.\n"
    lines = ["Memory candidate proposals:"]
    for item in candidates:
        flags = ",".join(item["warning_flags"]) if item["warning_flags"] else "none"
        lines.append(
            f"- {item['source_path']} | {item['validation_status']} | "
            f"{item['approval_status']} | warnings: {flags}"
        )
    return "\n".join(lines) + "\n"


def render_preview(candidate: str) -> str:
    path = resolve_candidate(candidate)
    item = candidate_metadata(path)
    proposed = str(item["proposed_memory_text"])
    if len(proposed) > 1200:
        proposed = proposed[:1200].rstrip() + "\n[TRUNCATED_PREVIEW]"
    lines = [
        "Engel Approved Memory Promotion Preview",
        "",
        f"Candidate ID: {item['candidate_id']}",
        f"Source path: {item['source_path']}",
        f"Validation status: {item['validation_status']}",
        f"Approval status: {item['approval_status']}",
        f"Promotion status: {item['promotion_status']}",
        f"Warning flags: {', '.join(item['warning_flags']) if item['warning_flags'] else 'none'}",
        f"Stop reasons: {'; '.join(item['stop_reasons']) if item['stop_reasons'] else 'none'}",
        "",
        "Proposed memory text preview:",
        ascii_safe(proposed) or "[NO_PROPOSED_MEMORY_TEXT_DETECTED]",
        "",
        "Preview only. No approval, promotion, trusted-memory write, source mutation, or route mutation occurred.",
    ]
    return "\n".join(lines) + "\n"


def render_validate(candidate: str) -> str:
    path = resolve_candidate(candidate)
    item = candidate_metadata(path)
    return json.dumps(item, indent=2, sort_keys=True) + "\n"


def receipt_id_for(candidate_id: str, timestamp: str) -> str:
    seed = f"{candidate_id}|{timestamp}|approved_memory_promotion_v1".encode("utf-8")
    return "approved_memory_promotion_receipt_" + hashlib.sha256(seed).hexdigest()[:16]


def trusted_memory_target_status() -> dict[str, object]:
    try:
        target = engel_trusted_memory_target.validate_target_contract()
    except Exception as exc:
        return {
            "target_status": "trusted memory target contract is missing or invalid",
            "enabled": False,
            "target_path": "UNKNOWN",
            "write_blocked_reason": "trusted memory target contract is missing or invalid: " + str(exc),
        }
    return {
        "target_status": str(target.get("target_status", "unknown")),
        "enabled": bool(target.get("enabled")),
        "target_path": str(target.get("target_path", "")),
        "write_blocked_reason": str(target.get("write_blocked_reason", "target contract status blocks promotion")),
    }


def safe_receipt_path(receipt_id: str) -> Path:
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", receipt_id).strip("_").lower() + ".json"
    receipt_root = RECEIPT_ROOT.resolve(strict=False)
    path = (receipt_root / safe_name).resolve(strict=False)
    if not is_relative_to(receipt_root, ROOT) or not is_relative_to(path, receipt_root):
        raise ApprovedMemoryPromotionError("receipt path escaped reports\\memory_promotion_receipts")
    return path


def build_promotion_receipt(candidate: str, approval_token: str | None, password_checked: bool) -> dict[str, object]:
    path = resolve_candidate(candidate)
    item = candidate_metadata(path)
    timestamp = now_utc()
    target_status = trusted_memory_target_status()
    approved = approval_token == APPROVAL_TOKEN and password_checked
    stop_reasons = list(item["stop_reasons"])
    if not approved:
        stop_reasons.append("explicit approval token and password gate required")
    if not target_status["enabled"]:
        stop_reasons.append("target contract status blocks promotion: " + str(target_status["write_blocked_reason"]))
    action_taken = "blocked_no_trusted_memory_write" if stop_reasons else "ready_for_bounded_promotion"
    return {
        "receipt_id": receipt_id_for(str(item["candidate_id"]), timestamp),
        "candidate_id": item["candidate_id"],
        "source_path": item["source_path"],
        "proposed_memory_text": item["proposed_memory_text"],
        "validation_result": item["validation_status"],
        "warning_flags": item["warning_flags"],
        "approval_evidence": "exact_token_and_password_gate_checked" if approved else "missing_or_invalid",
        "action_taken": action_taken,
        "trusted_memory_destination": target_status["target_path"],
        "trusted_memory_target_status": target_status["target_status"],
        "trusted_memory_target_write_blocked_reason": target_status["write_blocked_reason"],
        "timestamp": timestamp,
        "verifier_result": "verifier_required_before_future_trusted_memory_write",
        "stop_reasons": stop_reasons,
        "no_trusted_memory_write": True,
        "no_source_mutation": True,
        "no_route_mutation": True,
        "no_provider_network_browser": True,
        "no_model_runtime": True,
        "no_wsl_hermes_android_runtime": True,
        "human_review_required": True,
    }


def write_receipt(receipt: dict[str, object]) -> Path:
    RECEIPT_ROOT.mkdir(parents=True, exist_ok=True)
    path = safe_receipt_path(str(receipt["receipt_id"]))
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def attempt_promotion(candidate: str, approval_token: str | None, password_prompt: bool) -> tuple[int, str]:
    if approval_token != APPROVAL_TOKEN:
        return 2, f"[STOPPED] Exact approval token required: {APPROVAL_TOKEN}\n"
    if not password_prompt:
        return 2, "[STOPPED] Protected action requires --password-prompt.\n"
    global_password_gate.prompt_and_require_action("promote_memory_candidate")
    receipt = build_promotion_receipt(candidate, approval_token, password_checked=True)
    path = write_receipt(receipt)
    return 1, textwrap.dedent(
        f"""\
        STOPPED_APPROVED_MEMORY_PROMOTION {project_relative(path)}
        No trusted memory was written.
        Stop reason: {'; '.join(receipt['stop_reasons'])}
        """
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel Approved Memory Promotion V1.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Show protected memory promotion status.")
    mode.add_argument("--candidates", action="store_true", help="List discovered memory candidate proposals.")
    mode.add_argument("--preview", metavar="CANDIDATE", help="Preview one explicit memory candidate proposal.")
    mode.add_argument("--validate", metavar="CANDIDATE", help="Validate one explicit memory candidate proposal and print JSON.")
    mode.add_argument("--json", action="store_true", help="Print structured status JSON.")
    mode.add_argument("--promote", metavar="CANDIDATE", help="Protected promotion attempt; stops if target is unclear.")
    parser.add_argument("--approval-token", help="Exact token required for protected promotion attempts.")
    parser.add_argument("--password-prompt", action="store_true", help="Prompt for global password before protected promotion attempt.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    args = build_parser().parse_args(argv)
    try:
        if args.candidates:
            out.write(render_candidates())
            return 0
        if args.preview:
            out.write(render_preview(args.preview))
            return 0
        if args.validate:
            out.write(render_validate(args.validate))
            return 0
        if args.json:
            out.write(json.dumps(status_payload(), indent=2, sort_keys=True) + "\n")
            return 0
        if args.promote:
            code, message = attempt_promotion(args.promote, args.approval_token, args.password_prompt)
            (out if code in {0, 1} else err).write(message)
            return code
        out.write(render_status())
        return 0
    except (ApprovedMemoryPromotionError, global_password_gate.PasswordGateError) as exc:
        err.write(f"[STOPPED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
