from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
CONTRACT_JSON = ROOT / "memory" / "ENGEL_CANDIDATE_LEARNING_OUTPUT_REVIEW_CONTRACT_V1.json"

MAX_WARNING_SCAN_BYTES = 65536
MAX_HASH_BYTES = 2 * 1024 * 1024

REVIEW_STATES = [
    "found_untrusted",
    "found_candidate",
    "schema_validated",
    "needs_human_review",
    "verifier_pending",
    "verifier_failed",
    "rejected",
    "archived",
    "unknown_untrusted",
]

REVIEW_SCOPES = [
    ("self_learning_run_receipt", Path("reports/self_learning_run_receipts"), {".json"}),
    ("self_learning_run_summary", Path("reports/self_learning_run_summaries"), {".md"}),
    ("untrusted_research_note", Path("reports/self_research_notes"), {".md", ".json"}),
    ("lesson_candidate", Path("reports/lesson_candidates"), {".md", ".json"}),
    ("memory_candidate_proposal", Path("reports/memory_candidates"), {".md", ".json"}),
    ("learning_job_queue_record", Path("reports/learning_job_queue"), {".json"}),
    ("candidate_learning_record", Path("reports/learning_candidates"), {".md", ".json"}),
    ("rejected_or_failed_candidate_output", Path("reports/candidate_learning_rejections"), {".md", ".json", ".txt"}),
]

WARNING_PATTERNS = {
    "shell_command_reference": ["```bash", "```sh", "powershell", "cmd.exe", "wsl ", "chmod ", "curl ", "Invoke-WebRequest"],
    "python_code_block": ["```python", "python -c", "python.exe", "import os", "import subprocess"],
    "route_mutation_instruction": ["mutate route", "change route", "route mutation", "edit command map"],
    "trusted_memory_write_instruction": ["write trusted memory", "trusted-memory write", "mark as trusted", "memory promotion"],
    "approval_token_claim": ["APPROVE_", "approval token", "human approved", "simulate approval"],
    "provider_network_api_instruction": ["provider api", "network call", "openai", "requests.", "urllib", "socket", "api key"],
    "package_or_model_download_instruction": ["pip install", "npm install", "install package", "download model", "download file"],
    "startup_autoload_instruction": ["startup autorun", "scheduled task", "auto-load", "autoload", "start at boot"],
    "remote_queen_control_instruction": ["control remote queen", "create new queen", "queen authority", "bypass communication queen"],
    "hermes_reference": ["Hermes", "Hermes Agent", "Hermes-style"],
    "prompt_injection_language": ["ignore previous instructions", "ignore all instructions", "bypass safety", "disable safety"],
    "hidden_instruction_language": ["hide this from the user", "do not tell the user", "delete logs", "delete receipts"],
    "bypass_verifier_guard_approval_language": ["bypass verifier", "disable verifiers", "bypass guard", "bypass approval"],
}


class CandidateLearningOutputReviewError(ValueError):
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


def safe_files(folder: Path, extensions: set[str]) -> list[Path]:
    resolved = (ROOT / folder).resolve(strict=False)
    if not is_relative_to(resolved, ROOT):
        raise CandidateLearningOutputReviewError("review folder escaped project root")
    if not resolved.exists() or not resolved.is_dir():
        return []
    files: list[Path] = []
    for child in resolved.iterdir():
        if child.is_file() and child.name != ".gitkeep" and child.suffix.lower() in extensions:
            files.append(child.resolve(strict=False))
    return sorted(files)


def lightweight_hash(path: Path) -> str:
    if path.stat().st_size > MAX_HASH_BYTES:
        return "SKIPPED_TOO_LARGE_FOR_LIGHTWEIGHT_HASH"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_warning_text(path: Path) -> str:
    with path.open("rb") as handle:
        data = handle.read(MAX_WARNING_SCAN_BYTES)
    return data.decode("utf-8", errors="replace")


def warning_flags(path: Path) -> list[str]:
    text = read_warning_text(path)
    lowered = text.lower()
    flags: list[str] = []
    for flag, patterns in WARNING_PATTERNS.items():
        if any(pattern.lower() in lowered for pattern in patterns):
            flags.append(flag)
    return flags


def detect_candidate_type(category: str, path: Path) -> str:
    name = path.name.lower()
    if category == "self_learning_run_receipt":
        return "self_learning_run_receipt"
    if category == "self_learning_run_summary":
        return "self_learning_run_summary"
    if "lesson" in name:
        return "lesson_candidate"
    if "memory" in name:
        return "memory_candidate_proposal"
    if "research" in name or category == "untrusted_research_note":
        return "untrusted_research_note"
    if "learning_job" in name or category == "learning_job_queue_record":
        return "learning_job_queue_record"
    if "reject" in name or "fail" in name:
        return "rejected_or_failed_candidate_output"
    return category


def detect_review_state(category: str, path: Path, flags: list[str]) -> str:
    name = path.name.lower()
    if "reject" in name:
        return "rejected"
    if "archive" in name:
        return "archived"
    if "fail" in name:
        return "verifier_failed"
    if category in {"self_learning_run_receipt", "self_learning_run_summary"}:
        return "needs_human_review"
    if path.suffix.lower() == ".json" and not flags:
        return "schema_validated"
    if category in {"lesson_candidate", "memory_candidate_proposal", "candidate_learning_record", "learning_job_queue_record"}:
        return "found_candidate"
    if category == "untrusted_research_note":
        return "found_untrusted"
    return "unknown_untrusted"


def related_paths(category: str, path: Path) -> tuple[str, str]:
    if category == "self_learning_run_receipt":
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            return "", ""
        summary = str(payload.get("run_summary_path", ""))
        return project_relative(path), summary
    if category == "self_learning_run_summary":
        return "", project_relative(path)
    return "", ""


def item_metadata(category: str, path: Path) -> dict[str, object]:
    flags = warning_flags(path)
    stat = path.stat()
    related_receipt, related_summary = related_paths(category, path)
    item_id_seed = f"{category}|{project_relative(path)}|{stat.st_mtime_ns}|{stat.st_size}".encode("utf-8")
    return {
        "item_id": "candidate_learning_output_" + hashlib.sha256(item_id_seed).hexdigest()[:16],
        "path": project_relative(path),
        "file_type": path.suffix.lower().lstrip(".") or "unknown",
        "category": category,
        "source_folder": str(Path(project_relative(path)).parent),
        "modified_time": datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "size_bytes": stat.st_size,
        "sha256": lightweight_hash(path),
        "candidate_type": detect_candidate_type(category, path),
        "review_state": detect_review_state(category, path, flags),
        "warning_flags": flags,
        "related_run_receipt": related_receipt,
        "related_run_summary": related_summary,
    }


def collect_items(category_filter: str | None = None) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for category, folder, extensions in REVIEW_SCOPES:
        if category_filter and category != category_filter:
            continue
        for path in safe_files(folder, extensions):
            items.append(item_metadata(category, path))
    return items


def review_summary(category_filter: str | None = None) -> dict[str, object]:
    items = collect_items(category_filter)
    by_category: dict[str, int] = {}
    by_state: dict[str, int] = {}
    warning_count = 0
    for item in items:
        category = str(item["category"])
        state = str(item["review_state"])
        by_category[category] = by_category.get(category, 0) + 1
        by_state[state] = by_state.get(state, 0) + 1
        if item["warning_flags"]:
            warning_count += 1
    return {
        "schema_version": "1.0",
        "generated_at": now_utc(),
        "status": "READ_ONLY_REVIEW_LAYER / EXISTING_OUTPUTS_ONLY / HONEST_EMPTY_STATE",
        "category_filter": category_filter or "all",
        "folders_scanned_nonrecursive": [str(folder).replace("/", "\\") for _, folder, _ in REVIEW_SCOPES],
        "item_count": len(items),
        "warning_item_count": warning_count,
        "counts_by_category": by_category,
        "counts_by_review_state": by_state,
        "items": items,
        "empty_state": len(items) == 0,
        "safety_boundary": [
            "NO_APPROVAL",
            "NO_PROMOTION",
            "NO_APPLY",
            "NO_RUN_JOBS",
            "NO_TRUSTED_MEMORY_WRITE",
            "NO_SOURCE_MUTATION",
            "NO_ROUTE_MUTATION",
            "NO_MODEL_LOADING",
            "NO_INFERENCE",
            "NO_NETWORK",
            "NO_BROWSER",
            "NO_BACKGROUND_WORKER",
            "NO_STARTUP_AUTORUN",
        ],
    }


def render_status(category_filter: str | None = None) -> str:
    summary = review_summary(category_filter)
    lines = [
        "Engel Candidate Learning Output Review V1",
        "",
        "Status:",
        "- CANDIDATE_LEARNING_OUTPUT_REVIEW",
        "- READ_ONLY_REVIEW_LAYER",
        "- EXISTING_OUTPUTS_ONLY",
        "- HONEST_EMPTY_STATE",
        "- UNTRUSTED_OUTPUTS_ONLY",
        "- NOT_TRUSTED_MEMORY",
        "- HUMAN_REVIEW_REQUIRED",
        "- NO_APPROVAL",
        "- NO_PROMOTION",
        "- NO_APPLY",
        "- NO_RUN_JOBS",
        "",
        f"Category filter: {summary['category_filter']}",
        f"Item count: {summary['item_count']}",
        f"Warning item count: {summary['warning_item_count']}",
        f"Empty state: {summary['empty_state']}",
        "",
        "Counts by category:",
    ]
    counts_by_category = summary["counts_by_category"]
    if isinstance(counts_by_category, dict) and counts_by_category:
        lines.extend(f"- {key}: {value}" for key, value in sorted(counts_by_category.items()))
    else:
        lines.append("- none")
    lines.extend(["", "Counts by review state:"])
    counts_by_state = summary["counts_by_review_state"]
    if isinstance(counts_by_state, dict) and counts_by_state:
        lines.extend(f"- {key}: {value}" for key, value in sorted(counts_by_state.items()))
    else:
        lines.append("- none")
    lines.extend(["", "This is a review window, not an approval system."])
    return "\n".join(lines) + "\n"


def render_list(category_filter: str | None = None) -> str:
    items = collect_items(category_filter)
    if not items:
        return "No candidate learning output files found for this scope.\n"
    lines = ["Candidate learning output files:"]
    for item in items:
        flags = ",".join(item["warning_flags"]) if item["warning_flags"] else "none"
        lines.append(f"- {item['path']} | {item['category']} | {item['review_state']} | warnings: {flags}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Engel Candidate Learning Output Review V1.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Print readable review status.")
    mode.add_argument("--json", action="store_true", help="Print structured review JSON.")
    mode.add_argument("--list", action="store_true", help="List candidate output files.")
    parser.add_argument("--category", help="Optional review category filter.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    args = build_parser().parse_args(argv)
    if args.json:
        out.write(json.dumps(review_summary(args.category), indent=2, sort_keys=True) + "\n")
        return 0
    if args.list:
        out.write(render_list(args.category))
        return 0
    out.write(render_status(args.category))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
