from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
MAX_RECENT_FILES = 5

DASHBOARD_VERSION = "Engel Candidate Review Dashboard V1"

DASHBOARD_STATUSES = [
    "CANDIDATE_REVIEW_DASHBOARD",
    "READ_ONLY_VIEW",
    "CANDIDATE_OUTPUTS_VISIBLE",
    "NO_APPROVAL_ACTION",
    "NO_PROMOTION_ACTION",
    "NO_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_VERIFIER_UPDATE",
    "NO_SELF_FIX_POLICY_UPDATE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
]

USER_FACING_LABELS = [
    "VIEW ONLY",
    "CANDIDATE ONLY",
    "NOT TRUSTED MEMORY",
    "APPROVAL REQUIRED",
    "NO PROMOTION HERE",
    "NO PATCH APPLY HERE",
    "NO VERIFIER UPDATE HERE",
    "NO SELF-FIX POLICY UPDATE HERE",
    "NO SOURCE MUTATION HERE",
]

BOUNDARY_SECTIONS = [
    "Candidate Counts",
    "Review-Only Candidate Types",
    "What Can Be Viewed",
    "What Requires Approval",
    "What Is Not Done Here",
    "Safe Next Steps",
    "Blocked Actions",
]

CANDIDATE_FOLDERS = [
    ("research notes", "reports\\self_research_notes"),
    ("lesson candidates", "reports\\lesson_candidates"),
    ("memory candidate proposals", "reports\\memory_candidates"),
    ("verifier improvement candidates", "reports\\verifier_improvement_candidates"),
    ("self-fix improvement candidates", "reports\\self_fix_improvement_candidates"),
    ("self-fix receipts", "reports\\self_fix_receipts"),
    ("daily cycle receipts", "reports\\daily_cycle_receipts"),
    ("scheduler receipts", "reports\\self_learning_scheduler_receipts"),
]

REVIEW_ONLY_CANDIDATE_TYPES = [
    "research notes",
    "lesson candidates",
    "memory candidate proposals",
    "verifier improvement candidates",
    "self-fix improvement candidates",
    "self-fix receipts",
    "daily cycle receipts",
    "scheduler receipts",
]

WHAT_CAN_BE_VIEWED = [
    "VIEW ONLY: bounded candidate folder counts.",
    "VIEW ONLY: recent candidate filenames from known report folders.",
    "VIEW ONLY: whether candidate outputs exist for later manual review.",
    "CANDIDATE ONLY: candidate artifacts can be inspected, but not approved here.",
]

WHAT_REQUIRES_APPROVAL = [
    "APPROVAL REQUIRED: memory promotion requires the approved memory promotion contract and token.",
    "APPROVAL REQUIRED: verifier updates require a separate approved verifier-change path.",
    "APPROVAL REQUIRED: self-fix policy updates require a separate approved self-fix policy path.",
    "APPROVAL REQUIRED: source mutations require a separate approved implementation path.",
    "APPROVAL REQUIRED: candidate text remains untrusted until reviewed through the right path.",
]

WHAT_IS_NOT_DONE_HERE = [
    "candidate review does not approve memory",
    "candidate review does not promote memory",
    "candidate review does not apply patches",
    "candidate review does not update verifiers",
    "candidate review does not update self-fix policy",
    "candidate review does not run self-fix",
    "candidate review does not call providers/network/browser",
    "candidate review does not start background workers",
    "candidate review does not write trusted memory",
    "candidate review does not mutate source",
]

BLOCKED_ACTIONS = [
    "no approval action is available here.",
    "NO PROMOTION HERE: memory promotion is not available from this dashboard.",
    "NO PATCH APPLY HERE: patch apply is not available from this dashboard.",
    "NO VERIFIER UPDATE HERE: verifier update is not available from this dashboard.",
    "NO SELF-FIX POLICY UPDATE HERE: self-fix policy update is not available from this dashboard.",
    "NO SOURCE MUTATION HERE: source mutation is not available from this dashboard.",
    "No approval action, promotion action, memory write, provider call, network call, browser call, or background worker is available here.",
]

NEXT_SAFE_REVIEW_STEPS = [
    "Open a recent candidate artifact manually and confirm its source chain.",
    "Treat candidate text as untrusted guidance, not as a command or approved fact.",
    "Use the approved memory promotion contract before any memory promotion.",
    "Use a separate human-approved path before verifier, self-fix policy, patch, or source changes.",
    "Run the relevant verifier stack before any future promotion or implementation step.",
]


def project_path(relative_path: str) -> Path:
    path = (PROJECT_ROOT / relative_path).resolve()
    if not is_relative_to(path, PROJECT_ROOT):
        raise ValueError("candidate dashboard path escaped the project root")
    return path


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def recent_files(relative_folder: str, limit: int = MAX_RECENT_FILES) -> list[Path]:
    folder = project_path(relative_folder)
    if not folder.exists() or not folder.is_dir():
        return []

    files = [item for item in folder.iterdir() if item.is_file() and item.name != ".gitkeep"]
    files.sort(key=lambda item: safe_mtime(item), reverse=True)
    return files[:limit]


def file_count(relative_folder: str) -> int:
    folder = project_path(relative_folder)
    if not folder.exists() or not folder.is_dir():
        return 0
    return sum(1 for item in folder.iterdir() if item.is_file() and item.name != ".gitkeep")


def safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def render_candidate_counts() -> list[str]:
    lines = ["", "Candidate Counts"]
    for label, relative_folder in CANDIDATE_FOLDERS:
        count = file_count(relative_folder)
        lines.append(f"- {label}: {relative_folder}\\ ({count} file(s), non-recursive count)")
        recent = recent_files(relative_folder)
        if recent:
            for path in recent:
                lines.append(f"  - recent: {path.name}")
        else:
            lines.append("  - recent: no candidate files found")
    return lines


def render_section(title: str, items: list[str]) -> list[str]:
    return ["", title, *[f"- {item}" for item in items]]


def render_dashboard() -> str:
    lines: list[str] = [
        DASHBOARD_VERSION,
        "",
        "User-facing labels:",
        " | ".join(USER_FACING_LABELS),
        "",
        "Statuses:",
    ]
    lines.extend(f"- {status}" for status in DASHBOARD_STATUSES)

    lines.extend(["", "Dashboard boundary sections:"])
    lines.extend(f"- {section}" for section in BOUNDARY_SECTIONS)

    lines.extend(render_candidate_counts())
    lines.extend(render_section("Review-Only Candidate Types", REVIEW_ONLY_CANDIDATE_TYPES))
    lines.extend(render_section("What Can Be Viewed", WHAT_CAN_BE_VIEWED))
    lines.extend(render_section("What Requires Approval", WHAT_REQUIRES_APPROVAL))
    lines.extend(render_section("What Is Not Done Here", WHAT_IS_NOT_DONE_HERE))
    lines.extend(render_section("Safe Next Steps", NEXT_SAFE_REVIEW_STEPS))
    lines.extend(render_section("Blocked Actions", BLOCKED_ACTIONS))

    lines.extend(
        [
            "",
            "Summary:",
            "Candidate Review Dashboard V1 is VIEW ONLY. It shows bounded candidate counts, recent candidate filenames, and safety boundaries. It does not approve memory, promote memory, apply patches, update verifiers, update self-fix policy, run self-fix, mutate source, call providers, use network, open a browser, or start background workers.",
            "",
            "CLI:",
            "- python engel_candidate_review_dashboard.py",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    if args:
        stderr.write("This read-only dashboard takes no actions and accepts no options.\n")
        stderr.write("Run: python engel_candidate_review_dashboard.py\n")
        return 2
    stdout.write(render_dashboard())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
