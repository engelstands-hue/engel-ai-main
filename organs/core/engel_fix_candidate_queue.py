from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

import engel_global_password_gate as global_password_gate


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
QUEUE_DIR = ROOT / "reports" / "fix_candidate_queue"
CONTRACT_JSON = ROOT / "memory" / "ENGEL_FIX_CANDIDATE_QUEUE_CONTRACT_V1.json"
MAX_WARNING_SCAN_BYTES = 65536

QUEUE_STATUS = [
    "FIX_CANDIDATE_QUEUE",
    "QUEUE_CONTRACT",
    "LOCAL_ONLY",
    "INERT_RECORDS_ONLY",
    "CANDIDATE_FIXES_ONLY",
    "EXPLICIT_CANDIDATES_ONLY",
    "UNTRUSTED_OUTPUTS_ONLY",
    "NOT_PATCHES",
    "NOT_APPLIED_CHANGES",
    "HUMAN_REVIEW_REQUIRED",
    "VERIFIER_REQUIRED",
    "PASSWORD_GATE_REQUIRED_FOR_WRITE",
    "PROTECTED_ACTION_REGISTRY_REQUIRED",
    "NO_PATCH_APPLY",
    "NO_SOURCE_MUTATION",
    "NO_ROUTE_MUTATION",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_LOADING",
    "NO_INFERENCE",
    "NO_TRAINING",
    "NO_WSL_EXECUTION",
    "NO_HERMES_EXECUTION",
    "NO_ANDROID_CONNECTION",
    "NO_PACKAGE_INSTALL",
    "NO_DEPENDENCY_DOWNLOAD",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
    "NO_AUTO_APPROVAL",
    "NO_FAKE_FIXES",
    "NO_FAKE_APPROVALS",
    "NO_FAKE_VERIFIER_RESULTS",
    "HERMES_APPROVED_FOR_LOCAL_TESTING_HUMAN_DRIVEN_ONLY",
]

FIX_TYPES = [
    "documentation_update_candidate",
    "verifier_update_candidate",
    "command_map_update_candidate",
    "UI_text_fix_candidate",
    "safety_rule_update_candidate",
    "test_coverage_candidate",
    "bugfix_patch_candidate",
    "refactor_candidate",
    "config_review_candidate",
    "continuity_map_update_candidate",
    "report_cleanup_candidate",
]

CANDIDATE_STATES = [
    "draft",
    "discovered",
    "schema_validated",
    "needs_human_review",
    "verifier_required",
    "rejected",
    "approved_for_patch_review",
    "handed_to_code_companion",
    "archived",
]

METADATA_FIELDS = [
    "fix_candidate_id",
    "source_path",
    "source_type",
    "proposed_fix_type",
    "target_files",
    "summary",
    "rationale",
    "risk_level",
    "required_verifiers",
    "approval_required",
    "warning_flags",
    "created_at",
    "status",
    "related_receipt",
]

REQUIRED_VERIFIERS = [
    "tools\\verify_engel_fix_candidate_queue.py",
    "tools\\verify_untrusted_content_guard.py",
    "tools\\verify_prompt_injection_guard.py",
    "tools\\verify_authority_hierarchy.py",
]

WARNING_PATTERNS = {
    "shell_execution": ["```bash", "```sh", "powershell", "cmd.exe", "run shell", "execute command"],
    "python_execution": ["```python", "python -c", "python.exe", "exec(", "eval("],
    "package_install": ["pip install", "npm install", "install package", "package install"],
    "model_download_or_load": ["download model", "load model", "gguf", "run inference"],
    "provider_network_browser_api": ["openai", "api key", "requests.", "urllib", "socket", "browser", "network call"],
    "wsl_android_hermes_runtime": ["wsl ", "start wsl", "android runtime", "connect phone", "Hermes", "Hermes Agent"],
    "route_mutation": ["mutate route", "change route", "route table", "command router"],
    "trusted_memory_write": ["write trusted memory", "trusted-memory write", "mark as trusted"],
    "approval_bypass": ["bypass approval", "simulate approval", "APPROVE_", "human approved"],
    "verifier_disablement": ["disable verifier", "skip verifier", "bypass verifier"],
    "startup_autorun": ["startup autorun", "scheduled task", "start at boot", "autoload"],
    "background_workers": ["background worker", "start worker", "daemon", "endless loop"],
    "secret_access": ["secret=", "password=", "api_key", "private key"],
    "receipt_deletion": ["delete receipt", "delete logs", "remove evidence"],
    "hidden_persistence": ["hidden persistence", "hide this from the user", "persistence"],
    "remote_worker_authority_change": ["remote worker authority", "remote queen authority", "create new queen"],
    "communication_queen_authority_change": ["communication queen authority", "bypass communication queen"],
    "source_mutation_outside_protected_patch_flow": ["edit source now", "apply patch now", "mutate source"],
    "command_router_mutation_outside_approved_flow": ["edit command map", "change command router", "command-map mutation"],
}

SAFETY_BOUNDARY = (
    "FIX_CANDIDATE_QUEUE / INERT_RECORDS_ONLY / NOT_PATCHES / NOT_APPLIED_CHANGES / "
    "HUMAN_REVIEW_REQUIRED / VERIFIER_REQUIRED / NO_PATCH_APPLY / NO_SOURCE_MUTATION / "
    "NO_ROUTE_MUTATION / NO_TRUSTED_MEMORY_WRITE / NO_PROVIDER_CALLS / NO_NETWORK / "
    "NO_BROWSER / NO_MODEL_LOADING / NO_INFERENCE / NO_TRAINING / NO_WSL_EXECUTION / "
    "NO_HERMES_EXECUTION / NO_ANDROID_CONNECTION / NO_PACKAGE_INSTALL / NO_BACKGROUND_WORKER / "
    "NO_STARTUP_AUTORUN / NO_AUTO_APPROVAL / NO_FAKE_FIXES."
)


class FixCandidateQueueError(ValueError):
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


def safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_").lower() or "fix_candidate"


def resolve_local_file(raw_path: str, *, allow_queue: bool = False) -> Path:
    if not raw_path or raw_path.startswith(("http://", "https://", "\\\\")):
        raise FixCandidateQueueError("path must be an explicit local file")
    if any(marker in raw_path for marker in ("*", "?", "[")):
        raise FixCandidateQueueError("wildcards are forbidden")
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    resolved = candidate.resolve(strict=False)
    if not is_relative_to(resolved, ROOT):
        raise FixCandidateQueueError("path must stay inside Engel App")
    if not resolved.exists() or not resolved.is_file():
        raise FixCandidateQueueError("source file does not exist")
    rel = project_relative(resolved).lower()
    if rel.startswith("live\\") or rel.startswith("staging\\"):
        raise FixCandidateQueueError("live/staging package artifacts are forbidden")
    if not allow_queue and not (rel.startswith("reports\\") or rel.startswith("memory\\")):
        raise FixCandidateQueueError("source must be an approved local report, receipt, or memory contract")
    if resolved.suffix.lower() in {".exe", ".dll", ".pyd", ".so", ".bat", ".cmd", ".ps1", ".sh", ".gguf", ".pyc"}:
        raise FixCandidateQueueError("executable, script, binary, and model files are forbidden")
    return resolved


def warning_flags_for_text(text: str) -> list[str]:
    lowered = text.lower()
    flags: list[str] = []
    for flag, patterns in WARNING_PATTERNS.items():
        if any(pattern.lower() in lowered for pattern in patterns):
            flags.append(flag)
    return flags


def infer_source_type(path: Path) -> str:
    rel = project_relative(path).lower()
    if "verifier" in rel:
        return "verifier_result_or_report"
    if "receipt" in rel:
        return "receipt"
    if rel.startswith("memory\\"):
        return "memory_contract_or_plan"
    if rel.startswith("reports\\codex_bridge\\"):
        return "codex_bridge_report"
    if rel.startswith("reports\\"):
        return "report_or_candidate_output"
    return "approved_local_source"


def normalize_target_files(raw: str) -> list[str]:
    targets = [item.strip() for item in raw.split(",") if item.strip()]
    if not targets:
        raise FixCandidateQueueError("at least one target file is required")
    normalized: list[str] = []
    for target in targets:
        if target.startswith(("http://", "https://", "\\\\")) or any(marker in target for marker in ("*", "?", "[")):
            raise FixCandidateQueueError("target files must be explicit local paths")
        path = Path(target)
        if path.is_absolute():
            resolved = path.resolve(strict=False)
            if not is_relative_to(resolved, ROOT):
                raise FixCandidateQueueError("target file escaped Engel App")
            normalized.append(project_relative(resolved))
        else:
            normalized.append(str(path).replace("/", "\\"))
    return normalized


def candidate_id(source_path: str, fix_type: str, created_at: str) -> str:
    seed = f"ENGEL_FIX_CANDIDATE_QUEUE_V1|{source_path}|{fix_type}|{created_at}".encode("utf-8")
    return "fix_candidate_" + hashlib.sha256(seed).hexdigest()[:16]


def build_candidate(source: str, fix_type: str, target_files: str, summary: str, rationale: str, *, status: str = "draft") -> dict[str, object]:
    source_path = resolve_local_file(source)
    if fix_type not in FIX_TYPES:
        raise FixCandidateQueueError("proposed fix type is not allowed")
    created_at = now_utc()
    rel_source = project_relative(source_path)
    content = source_path.read_text(encoding="utf-8", errors="replace")[:MAX_WARNING_SCAN_BYTES]
    joined = "\n".join([summary, rationale, content])
    flags = warning_flags_for_text(joined)
    state = status
    if flags and status == "draft":
        state = "needs_human_review"
    return {
        "fix_candidate_id": candidate_id(rel_source, fix_type, created_at),
        "source_path": rel_source,
        "source_type": infer_source_type(source_path),
        "proposed_fix_type": fix_type,
        "target_files": normalize_target_files(target_files),
        "summary": summary.strip(),
        "rationale": rationale.strip(),
        "risk_level": "review_required_high_signal" if flags else "review_required",
        "required_verifiers": list(REQUIRED_VERIFIERS),
        "approval_required": True,
        "warning_flags": flags,
        "created_at": created_at,
        "status": state,
        "related_receipt": "",
        "safety_boundary": SAFETY_BOUNDARY,
        "not_applied": True,
        "no_patch_apply": True,
        "no_source_mutation": True,
        "no_route_mutation": True,
        "human_review_required": True,
    }


def validate_candidate_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise FixCandidateQueueError("fix candidate JSON must be an object")
    missing = [field for field in METADATA_FIELDS if field not in payload]
    if missing:
        raise FixCandidateQueueError("candidate missing required fields: " + ", ".join(missing))
    if payload.get("proposed_fix_type") not in FIX_TYPES:
        raise FixCandidateQueueError("candidate proposed_fix_type is not allowed")
    if payload.get("status") not in CANDIDATE_STATES:
        raise FixCandidateQueueError("candidate status is not allowed")
    if str(payload.get("status")).lower() == "applied":
        raise FixCandidateQueueError("this queue must not create applied status")
    targets = payload.get("target_files", [])
    if not isinstance(targets, list) or not targets:
        raise FixCandidateQueueError("target_files must be a non-empty list")
    for target in targets:
        normalize_target_files(str(target))
    resolve_local_file(str(payload.get("source_path", "")), allow_queue=True)
    if payload.get("approval_required") is not True:
        raise FixCandidateQueueError("approval_required must be true")
    if payload.get("not_applied") is not True or payload.get("no_patch_apply") is not True:
        raise FixCandidateQueueError("candidate must remain not_applied and no_patch_apply")
    text = json.dumps(payload, sort_keys=True)
    flags = warning_flags_for_text(text)
    recorded = payload.get("warning_flags", [])
    if not isinstance(recorded, list):
        raise FixCandidateQueueError("warning_flags must be a list")
    for flag in flags:
        if flag not in recorded:
            raise FixCandidateQueueError("candidate missing warning flag: " + flag)
    return dict(payload)


def load_candidate(raw_path: str) -> tuple[Path, dict[str, object]]:
    path = resolve_local_file(raw_path, allow_queue=True)
    if path.suffix.lower() != ".json":
        raise FixCandidateQueueError("fix candidate must be JSON")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise FixCandidateQueueError("fix candidate JSON could not be parsed") from exc
    return path, validate_candidate_payload(payload)


def queue_files() -> list[Path]:
    if not QUEUE_DIR.exists():
        return []
    return sorted(child for child in QUEUE_DIR.iterdir() if child.is_file() and child.suffix.lower() == ".json")


def queue_counts() -> dict[str, int]:
    counts = {state: 0 for state in CANDIDATE_STATES}
    for path in queue_files():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        state = str(payload.get("status", ""))
        if state in counts:
            counts[state] += 1
    return counts


def render_status() -> str:
    counts = queue_counts()
    lines = [
        "Engel Fix Candidate Queue V1",
        "",
        "Status:",
        *[f"- {label}" for label in QUEUE_STATUS],
        "",
        f"Queue folder: {project_relative(QUEUE_DIR)}",
        "",
        "Counts:",
        *[f"- {state}: {count}" for state, count in counts.items()],
        "",
        "Boundary:",
        SAFETY_BOUNDARY,
        "",
        "Fix candidates are not fixes. Queueing is not applying.",
    ]
    return "\n".join(lines) + "\n"


def render_list() -> str:
    files = queue_files()
    if not files:
        return "No fix candidate queue files found.\n"
    lines = ["Engel Fix Candidate Queue Files:"]
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            lines.append(f"- {path.name}: {payload.get('status')} / {payload.get('proposed_fix_type')} / warnings: {','.join(payload.get('warning_flags', [])) or 'none'}")
        except json.JSONDecodeError:
            lines.append(f"- {path.name}: invalid_json")
    return "\n".join(lines) + "\n"


def write_candidate(candidate: dict[str, object]) -> Path:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    path = (QUEUE_DIR / f"{safe_slug(str(candidate['fix_candidate_id']))}.json").resolve(strict=False)
    if not is_relative_to(path, QUEUE_DIR.resolve(strict=False)):
        raise FixCandidateQueueError("queue output escaped reports\\fix_candidate_queue")
    path.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def require_password() -> None:
    global_password_gate.prompt_and_require_action("write_fix_candidate_draft")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel Fix Candidate Queue V1.")
    parser.add_argument("--status", action="store_true", help="Show queue status and safety boundary.")
    parser.add_argument("--list", action="store_true", help="List inert fix candidate queue records.")
    parser.add_argument("--validate-candidate", metavar="FIX_JSON", help="Validate one explicit fix candidate JSON.")
    parser.add_argument("--draft-candidate", action="store_true", help="Print an inert fix candidate JSON to stdout only.")
    parser.add_argument("--write-draft", action="store_true", help="Write an inert fix candidate JSON to reports\\fix_candidate_queue.")
    parser.add_argument("--source", help="Explicit local source report/receipt/memory file.")
    parser.add_argument("--source-type", help="Optional source type label for caller documentation.")
    parser.add_argument("--fix-type", help="Allowed fix candidate type.")
    parser.add_argument("--target-files", help="Comma-separated explicit target file paths.")
    parser.add_argument("--summary", help="Short candidate summary.")
    parser.add_argument("--rationale", help="Candidate rationale.")
    parser.add_argument("--password-prompt", action="store_true", help="Prompt for global password before protected write.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    args = build_parser().parse_args(argv)
    try:
        if args.status:
            out.write(render_status())
            return 0
        if args.list:
            out.write(render_list())
            return 0
        if args.validate_candidate:
            path, candidate = load_candidate(args.validate_candidate)
            out.write(f"VALID_FIX_CANDIDATE {project_relative(path)} {candidate['fix_candidate_id']}\n")
            return 0
        if args.draft_candidate or args.write_draft:
            required = [args.source, args.fix_type, args.target_files, args.summary, args.rationale]
            if any(not item for item in required):
                err.write("--source, --fix-type, --target-files, --summary, and --rationale are required.\n")
                return 2
            candidate = build_candidate(args.source, args.fix_type, args.target_files, args.summary, args.rationale)
            if args.draft_candidate:
                out.write(json.dumps(candidate, indent=2, sort_keys=True) + "\n")
                return 0
            if not args.password_prompt:
                err.write("Protected write requires --password-prompt.\n")
                return 2
            require_password()
            path = write_candidate(candidate)
            out.write(f"WROTE_FIX_CANDIDATE_DRAFT {project_relative(path)}\n")
            return 0
        out.write(render_status())
        return 0
    except (FixCandidateQueueError, global_password_gate.PasswordGateError) as exc:
        err.write(f"[REJECTED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
