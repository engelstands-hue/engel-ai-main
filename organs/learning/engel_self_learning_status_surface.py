from __future__ import annotations

from pathlib import Path
import sys
import textwrap


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)

SURFACE_STATUS = [
    "STATUS_SURFACE_ONLY",
    "READ_ONLY_VIEW",
    "SELF_LEARNING_CHAIN_VISIBLE",
    "CANDIDATE_OUTPUTS_VISIBLE",
    "NO_LEARNING_RUN",
    "NO_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_VERIFIER_UPDATE",
    "NO_SELF_FIX_POLICY_UPDATE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
]

CHAIN_COMPONENTS = [
    ("Untrusted Research Note Generator V1", "creates bounded local untrusted research notes only when explicitly run elsewhere"),
    ("Research Note Viewer V1", "displays untrusted research notes read-only"),
    ("Lesson Candidate Extractor V1", "creates untrusted lesson candidates only when explicitly run elsewhere"),
    ("Research Memory Candidate Proposal V1", "creates proposal-only memory candidates only when explicitly run elsewhere"),
    ("Self-Learning Mini Runner V1", "connects one explicit topic and one explicit source only when explicitly run elsewhere"),
]

CANDIDATE_FOLDERS = [
    ("research_notes", "reports\\self_research_notes"),
    ("lesson_candidates", "reports\\lesson_candidates"),
    ("memory_candidates", "reports\\memory_candidates"),
]

BOUNDARIES = [
    "one-topic/one-source rule",
    "untrusted/candidate-only boundary",
    "no trusted memory boundary",
    "no source/verifier/self-fix mutation boundary",
    "status surface does not run learning",
    "status surface creates no generated artifacts",
    "status surface writes no trusted memory",
    "status surface starts no background worker",
]

FORBIDDEN_BEHAVIOR = [
    "no learning run",
    "no generated artifacts",
    "no source mutation",
    "no memory write",
    "no provider/network/browser",
    "no recursive scan",
    "no background worker",
]


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def bounded_file_count(relative_folder: str) -> int:
    folder = (PROJECT_ROOT / relative_folder).resolve()
    root = PROJECT_ROOT.resolve()
    if not is_relative_to(folder, root):
        return 0
    if not folder.exists() or not folder.is_dir():
        return 0
    count = 0
    for child in folder.iterdir():
        if child.is_file() and child.name != ".gitkeep":
            count += 1
    return count


def render_status_surface() -> str:
    lines = [
        "Engel Self-Learning Mini Runner Status Surface V1",
        "",
        "Status:",
        *[f"- {status}" for status in SURFACE_STATUS],
        "",
        "Pipeline:",
    ]
    for name, purpose in CHAIN_COMPONENTS:
        lines.append(f"- {name}: {purpose}")
    lines.extend(["", "Bounded candidate output folders:"])
    for label, relative_folder in CANDIDATE_FOLDERS:
        lines.append(f"- {relative_folder} ({label}): {bounded_file_count(relative_folder)} file(s), non-recursive count")
    lines.extend(["", "Boundaries:"])
    lines.extend(f"- {item}" for item in BOUNDARIES)
    lines.extend(["", "Forbidden behavior preserved:"])
    lines.extend(f"- {item}" for item in FORBIDDEN_BEHAVIOR)
    lines.extend(
        [
            "",
            "CLI:",
            "python engel_self_learning_status_surface.py",
            "",
            "Summary:",
            "This is a read-only status surface. It does not run the self-learning mini runner, create notes, create lesson candidates, create memory candidate proposals, mutate source, update verifiers, update self-fix policy, call providers, use network, open a browser, scan recursively, or start background workers.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None, stdout=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    if argv:
        out.write(
            textwrap.dedent(
                """\
                Engel Self-Learning Mini Runner Status Surface V1
                This status surface takes no options. It prints read-only status only.

                """
            )
        )
    out.write(render_status_surface())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
