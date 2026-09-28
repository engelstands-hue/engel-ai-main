#!/usr/bin/env python3
"""Create a Code Companion patch candidate plan from one explicit candidate.

The output is a plan-only artifact. This tool never edits source, applies a
patch, runs a verifier, or commits.
"""

import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import re
import sys


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
INPUT_DIR = PROJECT_ROOT / "reports" / "code_companion_candidates"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "patch_candidates"
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+\.md$")

STATUSES = [
    "CODE_COMPANION_PATCH_CANDIDATE",
    "PATCH_CANDIDATE_ONLY",
    "FROM_CODE_COMPANION_CANDIDATE",
    "PLAN_ONLY",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_COMMIT",
    "NO_VERIFIER_UPDATE",
    "NO_SELF_FIX_POLICY_UPDATE",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_BACKGROUND_WORKER",
]

LABELS = [
    "PATCH_CANDIDATE_ONLY",
    "PLAN_ONLY",
    "NOT_APPLIED",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_COMMIT",
    "HUMAN_REVIEW_REQUIRED",
    "VERIFY_BEFORE_USE",
]

PATCH_FIELDS = [
    "patch_candidate_id",
    "source_candidate_id",
    "source_candidate_path",
    "created_at",
    "title",
    "risk_class",
    "files_likely_involved",
    "proposed_changes",
    "do_not_touch",
    "verification_commands",
    "focused_safety_scan_terms",
    "rollback_notes",
    "commit_plan",
    "definition_of_done",
    "safety_boundary",
    "not_applied",
    "no_source_mutation",
    "no_patch_apply",
    "human_review_required",
]

FOCUSED_SAFETY_SCAN_TERMS = [
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "openai",
    "provider call",
    "network call",
    "browser call",
    "source mutation",
    "patch apply",
    "trusted_memory write",
    "model runtime",
    "background worker",
    "startup autorun",
]


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("/", "\\")
    except ValueError:
        return str(path)


def reject_unsafe_name(name: str) -> None:
    if not SAFE_NAME.fullmatch(name):
        raise ValueError("Candidate file name must be a simple .md file name from reports\\code_companion_candidates\\.")
    if name == ".gitkeep" or ".." in name or ":" in name or "\\" in name or "/" in name or "*" in name or "?" in name:
        raise ValueError("Unsafe candidate file name rejected.")


def load_candidate(name: str) -> tuple[Path, str]:
    reject_unsafe_name(name)
    path = INPUT_DIR / name
    if not path.exists() or not path.is_file():
        raise FileNotFoundError("Candidate file not found in reports\\code_companion_candidates\\: " + name)
    return path, path.read_text(encoding="utf-8")


def field_from_markdown(text: str, field: str, default: str = "") -> str:
    pattern = re.compile(r"^## " + re.escape(field) + r"\s*\n(.*?)(?=\n## |\Z)", re.MULTILINE | re.DOTALL)
    match = pattern.search(text)
    if not match:
        return default
    return match.group(1).strip()


def list_field(text: str, field: str) -> list[str]:
    raw = field_from_markdown(text, field)
    values = []
    for line in raw.splitlines():
        item = line.strip()
        if item.startswith("- "):
            values.append(item[2:].strip())
        elif item:
            values.append(item)
    return values or ["Human review required before any file is selected."]


def make_patch_candidate(candidate_path: Path, candidate_text: str) -> dict[str, object]:
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    source_candidate_id = field_from_markdown(candidate_text, "code_companion_candidate_id", candidate_path.stem)
    title = field_from_markdown(candidate_text, "title", "Code Companion candidate review")
    risk_class = field_from_markdown(candidate_text, "risk_class", "planning_only_low_risk")
    digest = hashlib.sha256((source_candidate_id + created_at).encode("utf-8")).hexdigest()[:12]
    return {
        "patch_candidate_id": "code_companion_patch_candidate_" + digest,
        "source_candidate_id": source_candidate_id,
        "source_candidate_path": relative_path(candidate_path),
        "created_at": created_at,
        "title": "Patch plan for: " + title,
        "risk_class": risk_class,
        "files_likely_involved": list_field(candidate_text, "likely_files_involved"),
        "proposed_changes": [
            "Review the source candidate and decide whether a future human-approved patch is warranted.",
            "If warranted, draft a minimal change list in a separate human review step.",
            "Do not apply this plan automatically; it is proposal text only.",
        ],
        "do_not_touch": [
            "live\\app package artifacts",
            "staging package artifacts",
            "trusted memory files",
            "provider/network/browser integrations",
            "model files",
            "package manager files",
            "unrelated source files",
        ],
        "verification_commands": list_field(candidate_text, "suggested_verification_commands"),
        "focused_safety_scan_terms": FOCUSED_SAFETY_SCAN_TERMS,
        "rollback_notes": "No rollback required because this patch candidate does not mutate source or apply a patch.",
        "commit_plan": "No commit is performed by this tool. A future approved runner or human may create a separate commit plan.",
        "definition_of_done": "Human review confirms the plan is useful, bounded, and verifier-ready before any implementation.",
        "safety_boundary": (
            "PATCH_CANDIDATE_ONLY / PLAN_ONLY / NOT_APPLIED. No source mutation, no patch apply, "
            "no commit, no verifier update, no self-fix policy update, no trusted memory write, "
            "no provider/network/browser/model runtime, and no background worker."
        ),
        "not_applied": True,
        "no_source_mutation": True,
        "no_patch_apply": True,
        "human_review_required": True,
    }


def render_patch_candidate(plan: dict[str, object]) -> str:
    lines = [
        "# Engel Code Companion Patch Candidate V1",
        "",
        "Status:",
        *["- " + status for status in STATUSES],
        "",
        "Labels:",
        *["- " + label for label in LABELS],
        "",
    ]
    for field in PATCH_FIELDS:
        value = plan[field]
        lines.append("## " + field)
        if isinstance(value, list):
            lines.extend("- " + str(item) for item in value)
        elif isinstance(value, bool):
            lines.append("true" if value else "false")
        else:
            lines.append(str(value))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def print_plan(plan: dict[str, object]) -> None:
    print("Engel Code Companion Patch Candidate V1")
    print("Patch candidate id: " + str(plan["patch_candidate_id"]))
    print("Source candidate: " + str(plan["source_candidate_path"]))
    print("Risk class: " + str(plan["risk_class"]))
    print("Boundary: plan only; no source mutation, patch apply, commit, verifier update, self-fix policy update, trusted memory, provider, network, browser, model runtime, or background worker.")


def write_plan(plan: dict[str, object]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / (str(plan["patch_candidate_id"]) + ".md")
    path.write_text(render_patch_candidate(plan), encoding="utf-8", newline="\n")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a plan-only Code Companion patch candidate from one explicit candidate.")
    parser.add_argument("--candidate", help="Simple file name from reports\\code_companion_candidates\\.")
    parser.add_argument("--dry-run", action="store_true", help="Print patch candidate summary without writing.")
    parser.add_argument("--write", action="store_true", help="Write patch candidate plan to reports\\patch_candidates\\.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.candidate or not (args.dry_run or args.write):
        parser.print_help()
        print()
        print("Safe usage: --candidate <candidate-file-name> with --dry-run or --write.")
        return 0
    try:
        candidate_path, candidate_text = load_candidate(args.candidate)
        plan = make_patch_candidate(candidate_path, candidate_text)
    except (OSError, ValueError) as exc:
        print("Refused: " + str(exc))
        return 2
    if args.dry_run:
        print_plan(plan)
    if args.write:
        path = write_plan(plan)
        print("Wrote patch candidate plan: " + relative_path(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
