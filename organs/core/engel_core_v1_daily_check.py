from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import engel_browser_queen_status
import engel_core_v1_dashboard_status

try:
    import engel_memory_candidate_review_dashboard as memory_candidate_dashboard
except ImportError:  # pragma: no cover - optional helper can be absent in older builds.
    memory_candidate_dashboard = None


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
SNAPSHOT_STATUS = "MANUAL_SNAPSHOT / READ_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED"
TRUSTED_MEMORY_STATUS = "BLOCKED / NOT_PERFORMED"
SNAPSHOT_ROOT = APP_ROOT / "reports" / "core_status_snapshots"
CONTINUITY_PATH = APP_ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"


@dataclass(frozen=True)
class CoreStatusSnapshot:
    generated_at: str
    status: str
    authority: str
    core_status: str
    git_status_summary: str
    verifier_status_summary: str
    products_count: str
    research_intake_count: str
    research_summary_count: str
    lesson_candidates_count: str
    lesson_reviews_count: str
    research_lesson_candidates_count: str
    research_lesson_reviews_count: str
    memory_candidates_count: str
    browser_queen_status: str
    browser_queen_path: str
    trusted_memory_status: str
    untrusted_content_guard: str
    prompt_injection_guard: str
    next_safe_step: str


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_count(value: object) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "UNKNOWN"


def _read_continuity() -> dict[str, Any]:
    if not CONTINUITY_PATH.exists():
        return {}
    try:
        payload = json.loads(CONTINUITY_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _git_status_summary() -> str:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(APP_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN / git status unavailable"
    if result.returncode != 0:
        return "UNKNOWN / git status failed"
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return "CLEAN"
    preview = "; ".join(lines[:5])
    if len(lines) > 5:
        preview += f"; ... ({len(lines) - 5} more)"
    return f"DIRTY / {len(lines)} item(s): {preview}"


def _verifier_status_summary() -> str:
    checks = {
        "Core V1 dashboard": APP_ROOT / "reports" / "codex_bridge" / "ENGEL_CORE_V1_DASHBOARD_COMMAND_CENTER.md",
        "Core continuity": APP_ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json",
        "Browser Queen contract": APP_ROOT / "reports" / "codex_bridge" / "ENGEL_BROWSER_QUEEN_DISABLED_STATUS_PANEL.md",
        "Memory candidate workflow": APP_ROOT / "reports" / "codex_bridge" / "ENGEL_TRUSTED_MEMORY_CANDIDATE_WORKFLOW.md",
        "Memory candidate dashboard": APP_ROOT / "reports" / "codex_bridge" / "ENGEL_MEMORY_CANDIDATE_REVIEW_DASHBOARD.md",
    }
    present = [name for name, path in checks.items() if path.exists()]
    missing = [name for name, path in checks.items() if not path.exists()]
    summary = f"LAST_KNOWN_REPORTS_PRESENT {len(present)}/{len(checks)}"
    if missing:
        summary += " / missing: " + ", ".join(missing)
    return summary


def _memory_candidate_count(continuity: dict[str, Any]) -> str:
    if memory_candidate_dashboard is not None:
        try:
            proposals = memory_candidate_dashboard.list_memory_candidate_proposals()
            return str(len(proposals))
        except Exception:
            pass
    return _safe_count(continuity.get("memory_candidate_proposals_count"))


def _next_safe_step(git_status_summary: str, memory_candidates_count: str) -> str:
    if git_status_summary.startswith("DIRTY"):
        return "Review git status and keep generated artifacts uncommitted unless Josh explicitly approves."
    try:
        candidate_count = int(str(memory_candidates_count).replace(",", ""))
    except ValueError:
        candidate_count = 0
    if candidate_count > 0:
        return "Review Trusted Memory Candidate proposals read-only; do not apply or promote candidates."
    return "Run the next targeted verifier for Josh's requested change; keep Browser Queen and trusted-memory writes blocked."


def build_core_v1_status_snapshot() -> CoreStatusSnapshot:
    continuity = _read_continuity()
    core = engel_core_v1_dashboard_status.get_core_v1_dashboard_status()
    browser = engel_browser_queen_status.get_browser_queen_status()
    git_summary = _git_status_summary()
    memory_candidates = _memory_candidate_count(continuity)
    trusted_memory = str(core.get("trusted_memory_status") or continuity.get("memory_candidate_trusted_memory_status") or TRUSTED_MEMORY_STATUS)
    if trusted_memory == "BLOCKED":
        trusted_memory = TRUSTED_MEMORY_STATUS

    return CoreStatusSnapshot(
        generated_at=_timestamp(),
        status=SNAPSHOT_STATUS,
        authority=AUTHORITY,
        core_status=str(core.get("core_status", continuity.get("continuity_status", "UNKNOWN"))),
        git_status_summary=git_summary,
        verifier_status_summary=_verifier_status_summary(),
        products_count=_safe_count(core.get("products_count", continuity.get("products_count"))),
        research_intake_count=_safe_count(core.get("research_intake_receipts_count", continuity.get("research_intake_receipts_count"))),
        research_summary_count=_safe_count(core.get("research_summary_proposals_count", continuity.get("research_summary_proposals_count"))),
        lesson_candidates_count=_safe_count(core.get("lesson_candidates_count", continuity.get("lesson_candidates_count"))),
        lesson_reviews_count=_safe_count(core.get("lesson_reviews_count", continuity.get("lesson_reviews_count"))),
        research_lesson_candidates_count=_safe_count(core.get("research_lesson_candidates_count", continuity.get("research_lesson_candidates_count"))),
        research_lesson_reviews_count=_safe_count(core.get("research_lesson_reviews_count", continuity.get("research_lesson_reviews_count"))),
        memory_candidates_count=memory_candidates,
        browser_queen_status=str(browser.get("status", core.get("browser_queen_status", "DISABLED"))),
        browser_queen_path="Research Intake",
        trusted_memory_status=trusted_memory,
        untrusted_content_guard="ACTIVE",
        prompt_injection_guard="ACTIVE",
        next_safe_step=_next_safe_step(git_summary, memory_candidates),
    )


def render_core_v1_status_snapshot(snapshot: CoreStatusSnapshot) -> str:
    return "\n".join(
        [
            "# Engel Core V1 Status Snapshot",
            "",
            "Status:",
            snapshot.status,
            "",
            "Authority:",
            snapshot.authority,
            "",
            "Generated:",
            snapshot.generated_at,
            "",
            "Core:",
            "Core status: " + snapshot.core_status,
            "Products: " + snapshot.products_count,
            "Research intake: " + snapshot.research_intake_count + " receipts / " + snapshot.research_summary_count + " summaries",
            "Lessons: "
            + snapshot.lesson_candidates_count
            + " product candidates / "
            + snapshot.lesson_reviews_count
            + " product reviews / "
            + snapshot.research_lesson_candidates_count
            + " research candidates / "
            + snapshot.research_lesson_reviews_count
            + " research reviews",
            "Memory candidates: " + snapshot.memory_candidates_count,
            "",
            "Git status:",
            snapshot.git_status_summary,
            "",
            "Verifier status:",
            snapshot.verifier_status_summary,
            "",
            "Browser Queen:",
            snapshot.browser_queen_status + " \u2192 " + snapshot.browser_queen_path,
            "",
            "Trusted memory:",
            snapshot.trusted_memory_status,
            "",
            "Guards:",
            "Untrusted Content Guard: " + snapshot.untrusted_content_guard,
            "Prompt Injection Guard: " + snapshot.prompt_injection_guard,
            "",
            "Next safe step:",
            snapshot.next_safe_step,
            "",
            "Boundary:",
            "Manual snapshot only.",
            "This is not a scheduler.",
            "This is not background work.",
            "This is not autonomy.",
            "No trusted memory write.",
            "No lesson/candidate apply.",
            "No API/network/browser behavior.",
            "",
            "Authority preserved:",
            AUTHORITY,
        ]
    ) + "\n"


def _is_safe_snapshot_path(path: Path) -> bool:
    try:
        path.resolve().relative_to(SNAPSHOT_ROOT.resolve())
        return path.suffix.lower() == ".md" and not path.exists()
    except (OSError, RuntimeError, ValueError):
        return False


def write_core_v1_status_snapshot(snapshot: CoreStatusSnapshot) -> Path:
    SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_ROOT / f"{snapshot.generated_at}_core_v1_status_snapshot.md"
    if not _is_safe_snapshot_path(path):
        raise ValueError("snapshot path is not bounded under reports\\core_status_snapshots")
    path.write_text(render_core_v1_status_snapshot(snapshot), encoding="utf-8")
    return path


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    print(render_core_v1_status_snapshot(build_core_v1_status_snapshot()))
