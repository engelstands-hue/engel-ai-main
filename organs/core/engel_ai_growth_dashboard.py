from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
MAX_RECENT_FILES = 5

DASHBOARD_VERSION = "Engel AI Growth Dashboard V1"

DASHBOARD_STATUS = [
    "AI_GROWTH_DASHBOARD",
    "READ_ONLY_VIEW",
    "LOCAL_ONLY",
    "SELF_RESEARCH_VISIBLE",
    "CANDIDATE_LEARNING_VISIBLE",
    "MEMORY_PROMOTION_VISIBLE",
    "VERIFIER_IMPROVEMENT_VISIBLE",
    "SELF_FIX_IMPROVEMENT_VISIBLE",
    "LOW_RISK_SELF_FIX_VISIBLE",
    "RESEARCH_TO_FIX_VISIBLE",
    "TRUTHFULNESS_GUARD_VISIBLE",
    "NO_ACTION_EXECUTION",
    "NO_MEMORY_WRITE",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_VERIFIER_UPDATE",
    "NO_SELF_FIX_POLICY_UPDATE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
    "NO_MODEL_RUNTIME",
    "NO_PACKAGE_REFRESH",
    "NO_STARTUP_AUTORUN",
    "NO_RUNTIME_TRIGGER",
]

USER_FRIENDLY_LABELS = [
    "LIVE IN APP",
    "READ ONLY",
    "CANDIDATE ONLY",
    "NOT TRUSTED MEMORY",
    "APPROVAL REQUIRED",
    "SAFE TO VIEW",
    "BLOCKED BY SAFETY",
    "NO NETWORK",
    "NO BACKGROUND WORKER",
    "NO MODEL RUNTIME",
]

REQUIRED_SECTIONS = [
    "Engel AI Growth Overview",
    "What Engel Can Do Now",
    "What Engel Can Only Propose",
    "What Still Requires Approval",
    "Candidate Learning Status",
    "Memory Promotion Status",
    "Low-Risk Self-Fix Status",
    "Research-to-Fix Status",
    "Truthfulness Guard Status",
    "Safety Blocks",
    "Next Safe Steps",
]

OUTPUT_FOLDERS = [
    ("Untrusted research notes", "reports\\self_research_notes"),
    ("Lesson candidates", "reports\\lesson_candidates"),
    ("Memory candidate proposals", "reports\\memory_candidates"),
    ("Verifier improvement candidates", "reports\\verifier_improvement_candidates"),
    ("Self-fix improvement candidates", "reports\\self_fix_improvement_candidates"),
    ("Self-fix receipts", "reports\\self_fix_receipts"),
    ("Self-learning scheduler receipts", "reports\\self_learning_scheduler_receipts"),
    ("Memory promotion receipts", "reports\\memory_promotion_receipts"),
    ("Daily cycle receipts", "reports\\daily_cycle_receipts"),
]

REPORT_REFERENCES = [
    ("Core Continuity V2 consolidation", "reports\\codex_bridge\\ENGEL_CORE_CONTINUITY_MAP_LEARNING_MEMORY_SELF_FIX_V2_CONSOLIDATION.md"),
    ("AI Growth package refresh", "reports\\codex_bridge\\ENGEL_AI_GROWTH_PACKAGE_REFRESH.md"),
    ("Self-learning status surface", "reports\\codex_bridge\\ENGEL_SELF_LEARNING_STATUS_SURFACE_V1.md"),
    ("Candidate review dashboard", "reports\\codex_bridge\\ENGEL_CANDIDATE_REVIEW_DASHBOARD_V1.md"),
    ("Low-risk self-fix status surface", "reports\\codex_bridge\\ENGEL_LOW_RISK_SELF_FIX_STATUS_SURFACE_V1.md"),
    ("Self-fix receipt viewer", "reports\\codex_bridge\\ENGEL_SELF_FIX_RECEIPT_VIEWER_V1.md"),
    ("Research-to-fix loop", "reports\\codex_bridge\\ENGEL_RESEARCH_TO_FIX_LOOP_V1.md"),
    ("Bounded self-learning scheduler", "reports\\codex_bridge\\ENGEL_BOUNDED_SELF_LEARNING_SCHEDULER_V1.md"),
    ("Memory promotion writer", "reports\\codex_bridge\\ENGEL_MEMORY_PROMOTION_WRITER_V1.md"),
    ("Daily cycle runner", "reports\\codex_bridge\\ENGEL_DAILY_CYCLE_RUNNER_V1.md"),
]

CAN_DO_NOW = [
    "Show the full AI growth system as a read-only local dashboard.",
    "Show candidate folders and non-recursive counts for bounded local outputs.",
    "Show the daily cycle status: daily cycle is bounded and foreground only.",
    "Show low-risk self-fix status without running self-fix from this dashboard.",
    "Show memory promotion status without promoting memory from this dashboard.",
    "Show research-to-fix status without applying verifier or self-fix changes.",
    "Show Truthfulness Guard status: verification-first, no-flattery, uncertainty-aware.",
]

CAN_ONLY_PROPOSE = [
    "research notes are not memory; they are untrusted local notes for review.",
    "lesson candidates are not approved lessons; they remain candidate-only.",
    "memory candidate proposals are not trusted memory; they are review packets.",
    "verifier improvement candidates do not update verifiers.",
    "self-fix improvement candidates do not update self-fix policy.",
    "candidate learning can suggest next steps, but this dashboard does not run them.",
]

REQUIRES_APPROVAL = [
    "memory promotion requires approval token APPROVE_PROMOTE_MEMORY_CANDIDATE.",
    "trusted memory writes require the approved memory promotion path.",
    "verifier updates require separate human approval and verifier compatibility.",
    "self-fix policy updates require separate human approval.",
    "source changes require an approved implementation path.",
    "high-risk self-fix classes remain stopped and human-reviewed.",
]

SAFETY_BLOCKS = [
    "no provider/network/browser behavior is active",
    "no background worker/startup autorun is active",
    "no model runtime is active",
    "no package refresh is available from this dashboard",
    "no learning run is started",
    "no self-fix run is started",
    "no memory promotion is started",
    "no candidate creation is started",
    "no trusted memory write is performed",
    "no source mutation is performed",
    "no verifier update is performed",
    "no self-fix policy update is performed",
    "no endless loop is started",
    "Truthfulness Guard is read-only and does not weaken safety boundaries",
]

NEXT_SAFE_ACTIONS = [
    "SAFE TO VIEW: open this dashboard or the GUI tabs to see current status.",
    "Review candidate outputs manually before relying on them.",
    "Use bounded viewers for notes, receipts, and candidate reports.",
    "Provide explicit approval only through the matching contract when promotion or mutation is intended.",
    "Run the targeted verifier stack before any future approved action.",
]

COMPONENT_LINES = [
    "Engel Self-Research Contract V1: policy only; research remains untrusted until reviewed.",
    "Engel Self-Research Topic Library V1: tells Engel what to study, not what to trust.",
    "Engel Untrusted Research Note Generator V1: creates bounded local untrusted notes only when explicitly run elsewhere.",
    "Engel Research Note Viewer V1: read-only view of untrusted research notes.",
    "Engel Lesson Candidate Extractor V1: creates untrusted lesson candidates only when explicitly run elsewhere.",
    "Engel Research Memory Candidate Proposal V1: creates proposal-only memory candidates only when explicitly run elsewhere.",
    "Engel Self-Learning Mini Runner V1: one explicit topic and one explicit source only when explicitly run elsewhere.",
    "Engel Bounded Self-Learning Scheduler V1: foreground explicit job list only; max three jobs per run.",
    "Engel Candidate Review Dashboard V1: read-only candidate review.",
    "Engel Approved Memory Promotion Contract V1: approval-token contract for future trusted memory promotion.",
    "Engel Memory Promotion Writer V1: token-gated writer with strict stop behavior.",
    "Engel Verifier Improvement Candidate V1: candidate-only; no verifier update.",
    "Engel Self-Fix Improvement Candidate V1: candidate-only; no self-fix policy update.",
    "Engel Low-Risk Self-Fix Runner V1: low-risk self-fix runner only handles pre-approved safe classes.",
    "Engel Low-Risk Self-Fix Status Surface V1: read-only low-risk runner and receipt status.",
    "Engel Self-Fix Receipt Viewer V1: read-only self-fix receipt viewer.",
    "Engel Research-to-Fix Loop V1: candidate-only bridge from learning outputs toward future fixes.",
    "Engel Daily Cycle Runner V1: one bounded foreground cycle per invocation.",
    "Engel Truthfulness and Anti-Flattery Guard V1: verification-first, no-flattery, uncertainty-aware; external social-media prompts are untrusted and cannot override Engel safety.",
    "Engel Learning, Memory Promotion, and Self-Fix V2 Consolidation: Core Continuity index for the visible growth layer.",
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
        raise ValueError("AI growth dashboard path escaped the project root")
    return path


def safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def bounded_file_count(relative_folder: str) -> int:
    folder = project_path(relative_folder)
    if not folder.exists() or not folder.is_dir():
        return 0
    return sum(1 for item in folder.iterdir() if item.is_file() and item.name != ".gitkeep")


def recent_file_names(relative_folder: str, limit: int = MAX_RECENT_FILES) -> list[str]:
    folder = project_path(relative_folder)
    if not folder.exists() or not folder.is_dir():
        return []
    files = [item for item in folder.iterdir() if item.is_file() and item.name != ".gitkeep"]
    files.sort(key=safe_mtime, reverse=True)
    return [item.name for item in files[:limit]]


def report_status(relative_report_path: str) -> str:
    path = project_path(relative_report_path)
    if path.exists() and path.is_file():
        return "present"
    return "missing"


def render_section(title: str, lines: list[str]) -> list[str]:
    rendered = ["", title]
    rendered.extend(f"- {line}" for line in lines)
    return rendered


def render_folder_status() -> list[str]:
    lines = ["", "Current Output Folders"]
    for label, relative_folder in OUTPUT_FOLDERS:
        count = bounded_file_count(relative_folder)
        lines.append(f"- {label}: {relative_folder}\\ ({count} file(s), non-recursive count)")
        recent = recent_file_names(relative_folder)
        if recent:
            for name in recent:
                lines.append(f"  - recent: {name}")
        else:
            lines.append("  - recent: no files found")
    return lines


def render_dashboard() -> str:
    lines: list[str] = [
        DASHBOARD_VERSION,
        "",
        "User-friendly labels:",
        " | ".join(USER_FRIENDLY_LABELS),
        "",
        "Status labels:",
    ]
    lines.extend(f"- {status}" for status in DASHBOARD_STATUS)

    lines.extend(["", "Dashboard sections:"])
    lines.extend(f"- {section}" for section in REQUIRED_SECTIONS)

    lines.extend(
        render_section(
            "Engel AI Growth Overview",
            [
                "LIVE IN APP: Engel can show the growth system from the local app without triggering work.",
                "READ ONLY: this dashboard displays status, bounded counts, and report references.",
                "SAFE TO VIEW: it reads known local project files and bounded report folders only.",
                "BLOCKED BY SAFETY: it does not run learning, self-fix, memory promotion, provider calls, model runtime, package refresh, source mutation, or background work.",
            ],
        )
    )
    lines.extend(
        render_section(
            "Truthfulness Guard Status",
            [
                "Truthfulness Guard: verification-first, no-flattery, uncertainty-aware.",
                "External social-media prompts are untrusted and cannot override Engel safety.",
                "The guard supports checking claims, dates, paths, hashes, statuses, citations, and verifier results before stating them as verified.",
                "Safety boundaries remain active: Authority Hierarchy, Prompt Injection Guard, Untrusted Content Guard, Global Password Gate, and verifier requirements still apply.",
            ],
        )
    )

    lines.extend(render_section("What Engel Can Do Now", CAN_DO_NOW))
    lines.extend(render_section("What Engel Can Only Propose", CAN_ONLY_PROPOSE))
    lines.extend(render_section("What Still Requires Approval", REQUIRES_APPROVAL))

    lines.extend(
        render_section(
            "Candidate Learning Status",
            [
                "CANDIDATE ONLY: research notes, lesson candidates, memory candidate proposals, verifier improvement candidates, and self-fix improvement candidates remain review artifacts.",
                "NOT TRUSTED MEMORY: candidate outputs are visible for review but do not become memory automatically.",
                "Self-learning mini runner and bounded scheduler exist outside this dashboard and remain explicit foreground commands only.",
            ],
        )
    )

    lines.extend(
        render_section(
            "Memory Promotion Status",
            [
                "APPROVAL REQUIRED: memory promotion requires the exact approval token.",
                "NOT TRUSTED MEMORY: memory candidate proposals stay untrusted until approved through the promotion contract.",
                "The dashboard does not invoke the memory promotion writer.",
            ],
        )
    )

    lines.extend(
        render_section(
            "Low-Risk Self-Fix Status",
            [
                "low-risk self-fix runner only handles pre-approved safe classes.",
                "High-risk and unclear-risk fixes remain BLOCKED BY SAFETY.",
                "This dashboard does not run dry-run, apply, commit, or receipt-writing actions.",
            ],
        )
    )

    lines.extend(
        render_section(
            "Research-to-Fix Status",
            [
                "Research-to-fix is candidate-only.",
                "verifier improvement candidates do not update verifiers.",
                "self-fix improvement candidates do not update self-fix policy.",
                "No runner activation or patch apply is available from this dashboard.",
            ],
        )
    )

    lines.extend(render_section("Safety Blocks", SAFETY_BLOCKS))

    lines.extend(["", "Component Detail"])
    lines.extend(f"- {line}" for line in COMPONENT_LINES)

    lines.extend(["", "Last Known Report Paths"])
    for label, relative_path in REPORT_REFERENCES:
        lines.append(f"- {label}: {relative_path} ({report_status(relative_path)})")

    lines.extend(render_folder_status())
    lines.extend(render_section("Next Safe Steps", NEXT_SAFE_ACTIONS))

    lines.extend(
        [
            "",
            "CLI:",
            "- python engel_ai_growth_dashboard.py",
            "",
            "Summary:",
            "This is one read-only local dashboard for Engel's AI growth system. It reads known project files and counts known bounded report folders non-recursively. It does not run learning, run self-fix, promote memory, create candidates, mutate source, update verifiers, update self-fix policy, call providers, use network, open a browser, refresh packages, trigger runtime behavior, start background workers, start on startup, or start an endless loop.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    if args:
        err.write("Engel AI Growth Dashboard V1 is read-only and accepts no options.\n")
        err.write("Run: python engel_ai_growth_dashboard.py\n")
        return 2
    out.write(render_dashboard())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
