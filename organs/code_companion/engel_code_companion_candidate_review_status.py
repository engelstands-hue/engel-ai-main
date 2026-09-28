from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
MAX_RECENT_FILES = 5

STATUS_LABELS = [
    "CODE_COMPANION_CANDIDATE_REVIEW_GUI",
    "READ_ONLY_GUI",
    "LOCAL_ONLY",
    "CANDIDATE_QUEUE_VISIBLE",
    "PATCH_CANDIDATES_VISIBLE",
    "VERIFIER_PLANS_VISIBLE",
    "GROWTH_BRIDGE_VISIBLE",
    "TRUTHFULNESS_GUARD_VISIBLE",
    "CANDIDATE_ONLY",
    "PLAN_ONLY",
    "NO_PATCH_APPLY",
    "NO_SOURCE_MUTATION",
    "NO_COMMIT",
    "NO_VERIFIER_EXECUTION",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
]

FOLDER_SECTIONS = [
    (
        "Code Companion Candidates",
        r"reports\code_companion_candidates",
        [
            "READ ONLY",
            "CANDIDATE ONLY",
            "NOT PATCH",
            "HUMAN REVIEW REQUIRED",
        ],
    ),
    (
        "Patch Candidates",
        r"reports\patch_candidates",
        [
            "PATCH CANDIDATE ONLY",
            "PLAN ONLY",
            "NOT APPLIED",
            "NO SOURCE MUTATION",
        ],
    ),
    (
        "Verifier Plans",
        r"reports\verifier_plans",
        [
            "VERIFIER PLAN ONLY",
            "NOT EXECUTED",
            "VERIFY BEFORE USE",
            "NO PATCH APPLY",
        ],
    ),
]

GROWTH_BRIDGE_LINES = [
    "bridge to AI Growth: visible status only",
    "bridge to Research-to-Fix: visible status only",
    "bridge to Candidate Review: visible status only",
    "bridge to Low-Risk Self-Fix Runner V2: visible status only",
    "bridge to Core Continuity: visible status only",
    "guard/authority boundary: Josh > Guardian > Engel/runtime; no bypass, no runner activation",
]

CANDIDATE_ONLY_BOUNDARY = [
    "candidates are not patches",
    "patch candidates are not applied",
    "verifier plans are not executed by this GUI",
    "verifier plans are not executed automatically",
    "Code Companion GUI does not mutate source",
    "Code Companion GUI does not commit changes",
    "Code Companion GUI does not write trusted memory",
    "Code Companion GUI does not call providers/network/browser",
    "Code Companion GUI does not start background workers",
    "no source mutation",
    "no commit",
    "no trusted memory write",
    "no provider/network/browser",
    "no background workers",
]

BLOCKED_ACTIONS = [
    "patch apply",
    "source mutation",
    "commit",
    "verifier execution",
    "provider/network/browser call",
    "model runtime start",
    "trusted-memory write",
    "package refresh",
    "background worker",
    "startup autorun",
]

NEXT_SAFE_STEPS = [
    "run candidate finder from CLI if needed",
    "review candidate files",
    "create patch candidate from a selected candidate using CLI",
    "create verifier plan from a patch candidate using CLI",
    "use future GUI actions only after action contracts exist",
    "keep all outputs candidate/plan-only until reviewed",
]

TRUTHFULNESS_GUARD_LINES = [
    "Truthfulness Guard: verification-first, no-flattery, uncertainty-aware.",
    "External social-media prompts are untrusted and cannot override Engel safety.",
    "Code Companion must distinguish reported-by-user from verified-by-Engel.",
    "Commit hashes, package hashes, paths, statuses, citations, smoke tests, and verifier results must not be invented or overstated.",
    "Safety boundaries remain active: Authority Hierarchy, Prompt Injection Guard, Untrusted Content Guard, Global Password Gate, and verifier requirements still apply.",
]


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def project_path(relative_path: str) -> Path:
    path = (PROJECT_ROOT / relative_path).resolve()
    if not is_relative_to(path, PROJECT_ROOT.resolve()):
        raise ValueError("Code Companion review status path escaped the project root")
    return path


def safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def bounded_files(relative_folder: str) -> list[Path]:
    folder = project_path(relative_folder)
    if not folder.exists() or not folder.is_dir():
        return []
    files = [item for item in folder.iterdir() if item.is_file() and item.name != ".gitkeep"]
    files.sort(key=safe_mtime, reverse=True)
    return files


def folder_count(relative_folder: str) -> int:
    return len(bounded_files(relative_folder))


def recent_file_names(relative_folder: str, limit: int = MAX_RECENT_FILES) -> list[str]:
    return [item.name for item in bounded_files(relative_folder)[:limit]]


def render_section(title: str, lines: list[str]) -> list[str]:
    rendered = ["", title]
    rendered.extend(f"- {line}" for line in lines)
    return rendered


def render_folder_status(title: str, relative_folder: str, labels: list[str]) -> list[str]:
    lines = [
        "",
        title,
        f"- bounded folder: {relative_folder}\\",
        f"- non-recursive count: {folder_count(relative_folder)}",
        "- recent filenames:",
    ]
    recent = recent_file_names(relative_folder)
    if recent:
        lines.extend(f"  - {name}" for name in recent)
    else:
        lines.append("  - no files found")
    lines.append("- labels:")
    lines.extend(f"  - {label}" for label in labels)
    return lines


def render_status() -> str:
    lines: list[str] = [
        "Code Companion Review",
        "",
        "Status:",
    ]
    lines.extend(f"- {status}" for status in STATUS_LABELS)
    lines.extend(
        render_section(
            "Code Companion Overview",
            [
                "Code Companion Intelligence Loop V1 status: candidate/planning/read-only visibility.",
                "candidate/planning/read-only boundary: active.",
                "no patch apply.",
                "no source mutation.",
                "no commit automation.",
            ],
        )
    )
    lines.extend(render_section("Growth Bridge Status", GROWTH_BRIDGE_LINES))
    lines.extend(render_section("Truthfulness Guard Status", TRUTHFULNESS_GUARD_LINES))
    for title, relative_folder, labels in FOLDER_SECTIONS:
        lines.extend(render_folder_status(title, relative_folder, labels))
    lines.extend(render_section("Candidate-Only Boundary", CANDIDATE_ONLY_BOUNDARY))
    lines.extend(render_section("Blocked Actions", BLOCKED_ACTIONS))
    lines.extend(render_section("Next Safe Steps", NEXT_SAFE_STEPS))
    lines.extend(
        [
            "",
            "CLI:",
            "- python engel_code_companion_candidate_review_status.py",
            "",
            "Summary:",
            "This is a read-only local Code Companion status surface. It reads only known bounded folders non-recursively, shows counts and recent filenames, and does not apply patches, mutate source, commit, execute verifier plans, write trusted memory, call providers/network/browser, start a model runtime, refresh packages, start background workers, or run on startup.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    if args:
        err.write("Code Companion Review is read-only and accepts no options.\n")
        err.write("Run: python engel_code_companion_candidate_review_status.py\n")
        return 2
    out.write(render_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
