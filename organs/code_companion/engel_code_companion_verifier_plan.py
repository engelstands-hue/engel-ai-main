#!/usr/bin/env python3
"""Create a verifier plan from one explicit patch candidate.

The verifier plan is not executed by default and does not apply any patch.
"""

import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import re
import sys


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
INPUT_DIR = PROJECT_ROOT / "reports" / "patch_candidates"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "verifier_plans"
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+\.md$")

STATUSES = [
    "CODE_COMPANION_VERIFIER_PLAN",
    "VERIFIER_PLAN_ONLY",
    "FROM_PATCH_CANDIDATE",
    "NO_TEST_EXECUTION_BY_DEFAULT",
    "NO_PATCH_APPLY",
    "NO_SOURCE_MUTATION",
    "NO_COMMIT",
    "NO_VERIFIER_UPDATE",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
]

LABELS = [
    "VERIFIER_PLAN_ONLY",
    "NOT_EXECUTED",
    "NO_PATCH_APPLY",
    "NO_SOURCE_MUTATION",
    "HUMAN_REVIEW_REQUIRED",
    "VERIFY_BEFORE_USE",
]

PLAN_FIELDS = [
    "verifier_plan_id",
    "source_patch_candidate_id",
    "source_patch_candidate_path",
    "created_at",
    "risk_class",
    "targeted_verifiers",
    "guard_verifiers",
    "optional_gui_smoke",
    "optional_package_smoke",
    "final_process_sweep",
    "git_status_check",
    "focused_safety_scan_terms",
    "not_executed",
    "no_patch_apply",
    "no_source_mutation",
    "human_review_required",
]

GUARD_VERIFIERS = [
    "python tools\\verify_untrusted_content_guard.py",
    "python tools\\verify_prompt_injection_guard.py",
    "python tools\\verify_authority_hierarchy.py",
    "python tools\\verify_living_systems_documentation_drift.py",
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
        raise ValueError("Patch candidate file name must be a simple .md file name from reports\\patch_candidates\\.")
    if name == ".gitkeep" or ".." in name or ":" in name or "\\" in name or "/" in name or "*" in name or "?" in name:
        raise ValueError("Unsafe patch candidate file name rejected.")


def load_patch_candidate(name: str) -> tuple[Path, str]:
    reject_unsafe_name(name)
    path = INPUT_DIR / name
    if not path.exists() or not path.is_file():
        raise FileNotFoundError("Patch candidate file not found in reports\\patch_candidates\\: " + name)
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
    return values


def make_verifier_plan(patch_path: Path, patch_text: str) -> dict[str, object]:
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    source_patch_candidate_id = field_from_markdown(patch_text, "patch_candidate_id", patch_path.stem)
    risk_class = field_from_markdown(patch_text, "risk_class", "planning_only_low_risk")
    targeted = list_field(patch_text, "verification_commands") or [
        "python tools\\verify_engel_code_companion_patch_candidate.py",
        "python tools\\verify_engel_code_companion_verifier_plan.py",
    ]
    scan_terms = list_field(patch_text, "focused_safety_scan_terms") or FOCUSED_SAFETY_SCAN_TERMS
    likely_files = "\n".join(list_field(patch_text, "files_likely_involved")).lower()
    proposed = field_from_markdown(patch_text, "proposed_changes").lower()
    digest = hashlib.sha256((source_patch_candidate_id + created_at).encode("utf-8")).hexdigest()[:12]
    gui_hint = "Run source GUI smoke only if the reviewed patch candidate touches GUI/status surface files."
    package_hint = "Package smoke is not part of this plan unless a later approved package step explicitly requests it."
    if "gui" in likely_files or "dashboard" in proposed or "status surface" in proposed:
        gui_hint = "If GUI files are changed in a future approved patch, run source GUI smoke before any package step."
    if "package" in likely_files or "live" in proposed:
        package_hint = "If package files are changed in a future approved step, require separate package refresh approval and smoke."
    return {
        "verifier_plan_id": "code_companion_verifier_plan_" + digest,
        "source_patch_candidate_id": source_patch_candidate_id,
        "source_patch_candidate_path": relative_path(patch_path),
        "created_at": created_at,
        "risk_class": risk_class,
        "targeted_verifiers": targeted,
        "guard_verifiers": GUARD_VERIFIERS,
        "optional_gui_smoke": gui_hint,
        "optional_package_smoke": package_hint,
        "final_process_sweep": "After any future approved implementation, confirm no Engel, Python, package, model, provider, browser, queue, self-fix, or worker process remains running.",
        "git_status_check": "Run git status --short after future approved implementation and verification.",
        "focused_safety_scan_terms": scan_terms,
        "not_executed": True,
        "no_patch_apply": True,
        "no_source_mutation": True,
        "human_review_required": True,
    }


def render_verifier_plan(plan: dict[str, object]) -> str:
    lines = [
        "# Engel Code Companion Verifier Plan V1",
        "",
        "Status:",
        *["- " + status for status in STATUSES],
        "",
        "Labels:",
        *["- " + label for label in LABELS],
        "",
    ]
    for field in PLAN_FIELDS:
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
    print("Engel Code Companion Verifier Plan V1")
    print("Verifier plan id: " + str(plan["verifier_plan_id"]))
    print("Source patch candidate: " + str(plan["source_patch_candidate_path"]))
    print("Boundary: verifier plan only; not executed; no patch apply, no source mutation, no commit, no provider, network, browser, trusted memory, or background worker.")


def write_plan(plan: dict[str, object]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / (str(plan["verifier_plan_id"]) + ".md")
    path.write_text(render_verifier_plan(plan), encoding="utf-8", newline="\n")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a verifier plan from one explicit Code Companion patch candidate.")
    parser.add_argument("--patch-candidate", help="Simple file name from reports\\patch_candidates\\.")
    parser.add_argument("--dry-run", action="store_true", help="Print verifier plan summary without writing.")
    parser.add_argument("--write", action="store_true", help="Write verifier plan to reports\\verifier_plans\\.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.patch_candidate or not (args.dry_run or args.write):
        parser.print_help()
        print()
        print("Safe usage: --patch-candidate <patch-file-name> with --dry-run or --write.")
        return 0
    try:
        patch_path, patch_text = load_patch_candidate(args.patch_candidate)
        plan = make_verifier_plan(patch_path, patch_text)
    except (OSError, ValueError) as exc:
        print("Refused: " + str(exc))
        return 2
    if args.dry_run:
        print_plan(plan)
    if args.write:
        path = write_plan(plan)
        print("Wrote verifier plan: " + relative_path(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
