from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import textwrap


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
RECEIPT_DIR = PROJECT_ROOT / "reports" / "self_fix_receipts"

VIEWER_STATUS = [
    "READ_ONLY_RECEIPT_VIEWER",
    "SELF_FIX_RECEIPTS_ONLY",
    "LOCAL_ONLY",
    "BOUNDED_REPORTS_ONLY",
    "NO_RECEIPT_MUTATION",
    "NO_FIX_EXECUTION",
    "NO_APPLY",
    "NO_COMMIT",
    "NO_SOURCE_MUTATION",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
]

DISPLAY_FIELDS = [
    "self_fix_run_id",
    "issue_detected",
    "classification",
    "allowed_low_risk_class",
    "mode",
    "files_changed",
    "patch_summary",
    "verification_commands",
    "verification_result",
    "safety_scan_result",
    "commit_hash",
    "rollback_notes",
    "stopped",
    "stop_reason",
    "human_intervention_required",
    "no_trusted_memory_write",
    "no_provider_network_browser",
    "no_background_worker",
]

BOUNDARY_TEXT = [
    "Self-fix receipts are displayed as local bounded report artifacts only.",
    "The viewer reads only reports\\self_fix_receipts\\ by explicit file name.",
    "The viewer does not edit receipts, delete receipts, write receipts, execute fixes, apply patches, commit changes, mutate source, write trusted memory, call providers, use network, open a browser, recursively scan folders, or start background workers.",
]


class SelfFixReceiptViewerError(ValueError):
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
        raise SelfFixReceiptViewerError("URLs are not accepted as self-fix receipt names.")
    if receipt_file_name.startswith("\\\\"):
        raise SelfFixReceiptViewerError("UNC paths are not accepted as self-fix receipt names.")
    if any(marker in receipt_file_name for marker in ("*", "?", "[", "]")):
        raise SelfFixReceiptViewerError("Wildcard receipt names are not accepted.")
    if any(separator in receipt_file_name for separator in ("\\", "/")):
        raise SelfFixReceiptViewerError("Only a receipt file name is accepted, not a path.")
    if ".." in receipt_file_name or ":" in receipt_file_name:
        raise SelfFixReceiptViewerError("Path traversal and drive names are not accepted.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.md", receipt_file_name):
        raise SelfFixReceiptViewerError("Self-fix receipt names must be safe .md file names.")


def resolve_receipt_path(receipt_file_name: str) -> Path:
    reject_unsafe_receipt_name(receipt_file_name)
    receipt_dir = RECEIPT_DIR.resolve()
    candidate = (receipt_dir / receipt_file_name).resolve()
    if not is_relative_to(candidate, receipt_dir):
        raise SelfFixReceiptViewerError("Receipt path escaped reports\\self_fix_receipts.")
    if not candidate.exists() or not candidate.is_file():
        raise SelfFixReceiptViewerError("Self-fix receipt does not exist in reports\\self_fix_receipts.")
    return candidate


def list_receipt_names() -> list[str]:
    if not RECEIPT_DIR.exists() or not RECEIPT_DIR.is_dir():
        return []
    receipt_dir = RECEIPT_DIR.resolve()
    names: list[str] = []
    for path in RECEIPT_DIR.iterdir():
        resolved = path.resolve()
        if path.is_file() and is_relative_to(resolved, receipt_dir) and path.suffix.lower() == ".md" and path.name != ".gitkeep":
            names.append(path.name)
    return sorted(names)


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


def render_receipt_view(receipt_file_name: str) -> str:
    receipt_path = resolve_receipt_path(receipt_file_name)
    text = receipt_path.read_text(encoding="utf-8", errors="replace")
    sections = parse_receipt_sections(text)
    lines = [
        "Engel Self-Fix Receipt Viewer V1",
        "READ_ONLY_RECEIPT_VIEWER / SELF_FIX_RECEIPTS_ONLY / LOCAL_ONLY / BOUNDED_REPORTS_ONLY",
        "",
        f"File: {receipt_path.name}",
        "",
        "Status labels:",
        *[f"- {status}" for status in VIEWER_STATUS],
        "",
        "Safety boundary:",
        *[f"- {item}" for item in BOUNDARY_TEXT],
        "",
        "Displayed receipt fields:",
    ]
    for field in DISPLAY_FIELDS:
        value = sections.get(field, "(not present)")
        lines.extend(["", f"{field}:", textwrap.indent(value, "  ")])
    return "\n".join(lines).rstrip() + "\n"


def render_receipt_list() -> str:
    names = list_receipt_names()
    lines = [
        "Engel Self-Fix Receipt Viewer V1",
        "READ_ONLY_RECEIPT_VIEWER / SELF_FIX_RECEIPTS_ONLY / LOCAL_ONLY / BOUNDED_REPORTS_ONLY",
        "",
        "Receipt folder:",
        "- reports\\self_fix_receipts\\",
        f"- non-recursive receipt count: {len(names)}",
        "",
        "Status labels:",
        *[f"- {status}" for status in VIEWER_STATUS],
        "",
        "Safety boundary:",
        *[f"- {item}" for item in BOUNDARY_TEXT],
        "",
        "Self-fix receipts:",
    ]
    if names:
        lines.extend(f"- {name}" for name in names)
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def usage_text() -> str:
    return textwrap.dedent(
        """\
        Engel Self-Fix Receipt Viewer V1

        Status:
        READ_ONLY_RECEIPT_VIEWER / SELF_FIX_RECEIPTS_ONLY / LOCAL_ONLY / BOUNDED_REPORTS_ONLY

        Usage:
          python engel_self_fix_receipt_viewer.py --list
          python engel_self_fix_receipt_viewer.py --show <receipt-file-name>

        Boundary:
          Reads only reports\\self_fix_receipts\\ by explicit file name. No receipt mutation,
          fix execution, apply, commit, source mutation, trusted-memory write, provider call,
          network, browser, recursive scan, or background worker behavior is enabled.
        """
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True, description="Read-only viewer for Engel low-risk self-fix receipts.")
    parser.add_argument("--list", action="store_true", help="List bounded self-fix receipt files.")
    parser.add_argument("--show", metavar="RECEIPT_FILE_NAME", help="Show one bounded self-fix receipt by file name.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.list and not args.show:
        out.write(usage_text())
        return 0
    if args.list and args.show:
        err.write("Choose either --list or --show, not both.\n")
        return 2
    try:
        if args.list:
            out.write(render_receipt_list())
            return 0
        out.write(render_receipt_view(args.show))
        return 0
    except SelfFixReceiptViewerError as exc:
        err.write(f"[REJECTED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
