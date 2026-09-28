from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import textwrap


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
RECEIPT_DIR = PROJECT_ROOT / "reports" / "daily_cycle_receipts"
MAX_RECENT_RECEIPTS = 5

SURFACE_VERSION = "Engel Daily Cycle Status Surface V1"

SURFACE_STATUS = [
    "DAILY_CYCLE_STATUS_SURFACE",
    "READ_ONLY_VIEW",
    "RECEIPTS_VISIBLE",
    "LOCAL_ONLY",
    "BOUNDED_REPORTS_ONLY",
    "NO_DAILY_CYCLE_RUN",
    "NO_LEARNING_RUN",
    "NO_SELF_FIX_RUN",
    "NO_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
]

RUNNER_STATUS = [
    "DAILY_CYCLE_RUNNER",
    "FOREGROUND_COMMAND_ONLY",
    "BOUNDED_RUN_ONLY",
    "ONE_CYCLE_PER_INVOCATION",
    "RECEIPT_REQUIRED",
    "NO_STARTUP_AUTORUN",
    "NO_ENDLESS_LOOP",
    "NO_BACKGROUND_WORKER",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_PACKAGE_REFRESH",
    "NO_UNAPPROVED_MEMORY_WRITE",
    "NO_UNAPPROVED_SOURCE_MUTATION",
    "NO_HIGH_RISK_SELF_FIX",
]

DISPLAY_FIELDS = [
    "daily_cycle_run_id",
    "started_at",
    "completed_at",
    "mode",
    "status_checks_run",
    "verifiers_run",
    "learning_jobs_run",
    "candidates_seen",
    "self_fix_dry_runs",
    "self_fixes_applied",
    "receipts_created",
    "stopped",
    "stop_reason",
    "safety_boundary",
    "final_summary",
]

BOUNDARY_TEXT = [
    "The daily cycle status surface reads only reports\\daily_cycle_receipts\\.",
    "Receipt listing is non-recursive.",
    "Showing a receipt requires one explicit safe receipt file name.",
    "dry-run/run status is shown from the receipt mode field when receipts exist.",
    "The viewer does not run the daily cycle, run learning, run self-fix, promote memory, mutate source, call providers, use network, open a browser, start a background worker, start on startup, or start an endless loop.",
    "No-startup-autorun boundary is active.",
    "No-endless-loop boundary is active.",
]


class DailyCycleStatusSurfaceError(ValueError):
    pass


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def reject_unsafe_receipt_name(receipt_file_name: str) -> None:
    lowered = receipt_file_name.lower()
    if lowered.startswith(("http://", "https://")):
        raise DailyCycleStatusSurfaceError("URLs are not accepted as daily cycle receipt names.")
    if receipt_file_name.startswith("\\\\"):
        raise DailyCycleStatusSurfaceError("UNC paths are not accepted as daily cycle receipt names.")
    if any(marker in receipt_file_name for marker in ("*", "?", "[", "]")):
        raise DailyCycleStatusSurfaceError("Wildcard receipt names are not accepted.")
    if any(separator in receipt_file_name for separator in ("\\", "/")):
        raise DailyCycleStatusSurfaceError("Only a receipt file name is accepted, not a path.")
    if ".." in receipt_file_name or ":" in receipt_file_name:
        raise DailyCycleStatusSurfaceError("Path traversal and drive names are not accepted.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.md", receipt_file_name):
        raise DailyCycleStatusSurfaceError("Daily cycle receipt names must be safe .md file names.")


def resolve_receipt_path(receipt_file_name: str) -> Path:
    reject_unsafe_receipt_name(receipt_file_name)
    receipt_dir = RECEIPT_DIR.resolve(strict=False)
    candidate = (receipt_dir / receipt_file_name).resolve(strict=False)
    if not is_relative_to(candidate, receipt_dir):
        raise DailyCycleStatusSurfaceError("Receipt path escaped reports\\daily_cycle_receipts.")
    if not candidate.exists() or not candidate.is_file():
        raise DailyCycleStatusSurfaceError("Daily cycle receipt does not exist in reports\\daily_cycle_receipts.")
    return candidate


def safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def list_receipt_names() -> list[str]:
    if not RECEIPT_DIR.exists() or not RECEIPT_DIR.is_dir():
        return []
    receipt_dir = RECEIPT_DIR.resolve(strict=False)
    names: list[str] = []
    for path in RECEIPT_DIR.iterdir():
        resolved = path.resolve(strict=False)
        if path.is_file() and is_relative_to(resolved, receipt_dir) and path.suffix.lower() == ".md" and path.name != ".gitkeep":
            names.append(path.name)
    return sorted(names)


def recent_receipt_names(limit: int = MAX_RECENT_RECEIPTS) -> list[str]:
    names = list_receipt_names()
    paths = [RECEIPT_DIR / name for name in names]
    paths.sort(key=safe_mtime, reverse=True)
    return [path.name for path in paths[:limit]]


def parse_receipt_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current is not None:
            sections[current] = "\n".join(buffer).strip()

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            heading = line[3:].strip()
            current = heading if heading in DISPLAY_FIELDS else None
            buffer = []
            continue
        if current is not None:
            buffer.append(line)
    flush()
    return sections


def receipt_summary(receipt_file_name: str) -> list[str]:
    receipt_path = resolve_receipt_path(receipt_file_name)
    text = receipt_path.read_text(encoding="utf-8", errors="replace")
    sections = parse_receipt_sections(text)
    mode = sections.get("mode", "(not present)") or "(not present)"
    stopped = sections.get("stopped", "(not present)") or "(not present)"
    stop_reason = sections.get("stop_reason", "(not present)") or "(not present)"
    final_summary = sections.get("final_summary", "(not present)") or "(not present)"
    return [
        f"{receipt_path.name}",
        f"  mode: {mode}",
        f"  stopped: {stopped}",
        f"  stop_reason: {stop_reason}",
        f"  final_summary: {final_summary}",
    ]


def render_receipt_value(value: str) -> str:
    return value if value else "(not present)"


def render_receipt_view(receipt_file_name: str) -> str:
    receipt_path = resolve_receipt_path(receipt_file_name)
    text = receipt_path.read_text(encoding="utf-8", errors="replace")
    sections = parse_receipt_sections(text)
    lines = [
        SURFACE_VERSION,
        "READ_ONLY_VIEW / DAILY_CYCLE_STATUS_SURFACE / BOUNDED_REPORTS_ONLY",
        "",
        f"Receipt file: {receipt_path.name}",
        "",
        "Surface status:",
        *[f"- {status}" for status in SURFACE_STATUS],
        "",
        "Runner status:",
        *[f"- {status}" for status in RUNNER_STATUS],
        "",
        "Contract boundary:",
        *[f"- {boundary}" for boundary in BOUNDARY_TEXT],
        "",
        "Displayed receipt fields:",
    ]
    for field in DISPLAY_FIELDS:
        value = render_receipt_value(sections.get(field, ""))
        lines.extend(["", f"{field}:", textwrap.indent(value, "  ")])
    return "\n".join(lines).rstrip() + "\n"


def render_status_surface() -> str:
    names = list_receipt_names()
    recent = recent_receipt_names()
    lines = [
        SURFACE_VERSION,
        "",
        "Surface status:",
        *[f"- {status}" for status in SURFACE_STATUS],
        "",
        "Daily cycle runner status:",
        *[f"- {status}" for status in RUNNER_STATUS],
        "",
        "Contract boundary:",
        *[f"- {boundary}" for boundary in BOUNDARY_TEXT],
        "",
        "Receipt folder:",
        "- reports\\daily_cycle_receipts\\",
        f"- non-recursive receipt count: {len(names)}",
        "",
        "Recent receipt names:",
    ]
    if recent:
        lines.extend(f"- {name}" for name in recent)
    else:
        lines.append("- none")

    lines.extend(["", "Recent receipt summaries:"])
    if recent:
        for name in recent:
            lines.extend(receipt_summary(name))
    else:
        lines.extend(
            [
                "- no receipts found",
                "  mode: none",
                "  stopped: none",
                "  stop_reason: none",
                "  verifiers_run: none",
                "  learning_jobs_run: none",
                "  candidates_seen: none",
                "  self_fix_dry_runs: none",
                "  self_fixes_applied: none",
                "  final_summary: no daily cycle receipts are present yet",
            ]
        )

    lines.extend(
        [
            "",
            "Display fields available in --show:",
            *[f"- {field}" for field in DISPLAY_FIELDS],
            "",
            "Safety summary:",
            "- no daily cycle execution",
            "- no learning scheduler run",
            "- no self-fix execution",
            "- no memory promotion",
            "- no source mutation",
            "- no provider/network/browser",
            "- no background worker",
            "- no startup autorun",
            "- no endless loop",
            "",
            "CLI:",
            "- python engel_daily_cycle_status_surface.py",
            "- python engel_daily_cycle_status_surface.py --list",
            "- python engel_daily_cycle_status_surface.py --show <receipt-file-name>",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_receipt_list() -> str:
    names = list_receipt_names()
    lines = [
        SURFACE_VERSION,
        "DAILY_CYCLE_STATUS_SURFACE / READ_ONLY_VIEW / RECEIPTS_VISIBLE / BOUNDED_REPORTS_ONLY",
        "",
        "Receipt folder:",
        "- reports\\daily_cycle_receipts\\",
        f"- non-recursive receipt count: {len(names)}",
        "",
        "Daily cycle receipts:",
    ]
    if names:
        lines.extend(f"- {name}" for name in names)
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def usage_text() -> str:
    return textwrap.dedent(
        """\
        Engel Daily Cycle Status Surface V1

        Status:
        DAILY_CYCLE_STATUS_SURFACE / READ_ONLY_VIEW / RECEIPTS_VISIBLE / LOCAL_ONLY / BOUNDED_REPORTS_ONLY

        Usage:
          python engel_daily_cycle_status_surface.py
          python engel_daily_cycle_status_surface.py --list
          python engel_daily_cycle_status_surface.py --show <receipt-file-name>

        Boundary:
          Reads only reports\\daily_cycle_receipts\\ by explicit file name for --show.
          No daily cycle run, learning run, self-fix run, memory write, source mutation,
          provider call, network, browser, background worker, startup autorun, or endless loop.
        """
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True, description="Read-only status surface for Engel daily cycle receipts.")
    parser.add_argument("--list", action="store_true", help="List bounded daily cycle receipt files.")
    parser.add_argument("--show", metavar="RECEIPT_FILE_NAME", help="Show one bounded daily cycle receipt by file name.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list and args.show:
        err.write("Choose either --list or --show, not both.\n")
        return 2
    try:
        if args.show:
            out.write(render_receipt_view(args.show))
            return 0
        if args.list:
            out.write(render_receipt_list())
            return 0
        out.write(render_status_surface())
        return 0
    except DailyCycleStatusSurfaceError as exc:
        err.write(f"[REJECTED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
