from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import textwrap


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
RECEIPT_DIR = PROJECT_ROOT / "reports" / "code_companion_patch_receipts"
MAX_RECENT_RECEIPTS = 20

VIEWER_STATUS = [
    "CODE_COMPANION_PATCH_RECEIPT_VIEWER",
    "READ_ONLY_VIEWER",
    "LOCAL_ONLY",
    "BOUNDED_RECEIPTS_ONLY",
    "NO_RECEIPT_MUTATION",
    "NO_PATCH_APPLY",
    "NO_SOURCE_MUTATION",
    "NO_COMMIT",
    "NO_VERIFIER_EXECUTION",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
]

DISPLAY_FIELDS = [
    "patch_run_id",
    "source_patch_candidate_id",
    "source_patch_candidate_path",
    "patch_class",
    "mode",
    "files_changed",
    "patch_summary",
    "verification_commands",
    "verification_result",
    "safety_scan_result",
    "commit_hash",
    "stopped",
    "stop_reason",
    "human_intervention_required",
    "rollback_notes",
    "no_trusted_memory_write",
    "no_provider_network_browser",
    "no_background_worker",
    "no_package_refresh",
    "no_route_startup_mutation",
]

BOUNDARY_TEXT = [
    "The viewer lists receipts from reports\\code_companion_patch_receipts\\ only.",
    "The viewer shows one explicitly named receipt from reports\\code_companion_patch_receipts\\ only.",
    "The viewer reads the receipt folder non-recursively.",
    "The viewer does not edit receipts, delete receipts, write receipts, apply patches, mutate source, commit changes, execute verifiers, write trusted memory, call providers, use network, open a browser, or start background workers.",
]


class PatchReceiptViewerError(ValueError):
    pass


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def reject_unsafe_receipt_name(receipt_file_name: str) -> None:
    if receipt_file_name.startswith("\\\\"):
        raise PatchReceiptViewerError("UNC receipt paths are not accepted.")
    if any(separator in receipt_file_name for separator in ("\\", "/")):
        raise PatchReceiptViewerError("Only a receipt file name is accepted, not a path.")
    if ".." in receipt_file_name or ":" in receipt_file_name:
        raise PatchReceiptViewerError("Path traversal and drive-qualified receipt paths are not accepted.")
    if any(marker in receipt_file_name for marker in ("*", "?", "[", "]")):
        raise PatchReceiptViewerError("Wildcard receipt names are not accepted.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.md", receipt_file_name):
        raise PatchReceiptViewerError("Code Companion patch receipt names must be safe .md file names.")


def resolve_receipt_path(receipt_file_name: str) -> Path:
    reject_unsafe_receipt_name(receipt_file_name)
    root = RECEIPT_DIR.resolve()
    path = (root / receipt_file_name).resolve()
    if not is_relative_to(path, root):
        raise PatchReceiptViewerError("Receipt path escaped reports\\code_companion_patch_receipts.")
    if not path.exists() or not path.is_file():
        raise PatchReceiptViewerError("Receipt does not exist in reports\\code_companion_patch_receipts.")
    return path


def list_receipt_names() -> list[str]:
    if not RECEIPT_DIR.exists() or not RECEIPT_DIR.is_dir():
        return []
    root = RECEIPT_DIR.resolve()
    files = []
    for path in RECEIPT_DIR.iterdir():
        resolved = path.resolve()
        if (
            path.is_file()
            and path.name != ".gitkeep"
            and path.suffix.lower() == ".md"
            and is_relative_to(resolved, root)
        ):
            files.append(path)
    files.sort(key=safe_mtime, reverse=True)
    return [path.name for path in files]


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


def render_receipt_list() -> str:
    names = list_receipt_names()
    lines = [
        "Engel Code Companion Patch Receipt Viewer V1",
        "",
        "Status:",
        *["- " + status for status in VIEWER_STATUS],
        "",
        "Receipt folder:",
        "- reports\\code_companion_patch_receipts\\",
        "- non-recursive receipt count: " + str(len(names)),
        "",
        "Safety boundary:",
        *["- " + item for item in BOUNDARY_TEXT],
        "",
        "Recent receipts:",
    ]
    if names:
        lines.extend("- " + name for name in names[:MAX_RECENT_RECEIPTS])
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def render_receipt_view(receipt_file_name: str) -> str:
    path = resolve_receipt_path(receipt_file_name)
    text = path.read_text(encoding="utf-8", errors="replace")
    sections = parse_receipt_sections(text)
    lines = [
        "Engel Code Companion Patch Receipt Viewer V1",
        "",
        "Status:",
        *["- " + status for status in VIEWER_STATUS],
        "",
        "File:",
        "- " + path.name,
        "",
        "Safety boundary:",
        *["- " + item for item in BOUNDARY_TEXT],
        "",
        "Displayed receipt fields:",
    ]
    for field in DISPLAY_FIELDS:
        value = sections.get(field, "(not present)")
        lines.extend(["", field + ":", textwrap.indent(value, "  ")])
    return "\n".join(lines).rstrip() + "\n"


def usage_text() -> str:
    return textwrap.dedent(
        """\
        Engel Code Companion Patch Receipt Viewer V1

        Status:
        CODE_COMPANION_PATCH_RECEIPT_VIEWER / READ_ONLY_VIEWER / LOCAL_ONLY / BOUNDED_RECEIPTS_ONLY

        Usage:
          python engel_code_companion_patch_receipt_viewer.py --list
          python engel_code_companion_patch_receipt_viewer.py --show <receipt-file-name>

        Boundary:
          Reads only reports\\code_companion_patch_receipts\\ non-recursively. No receipt
          mutation, patch apply, source mutation, commit, verifier execution,
          trusted-memory write, provider call, network, browser, or background worker.
        """
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only viewer for Code Companion patch receipts.")
    parser.add_argument("--list", action="store_true", help="List bounded Code Companion patch receipts.")
    parser.add_argument("--show", metavar="RECEIPT_FILE_NAME", help="Show one bounded receipt by safe file name.")
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
    except PatchReceiptViewerError as exc:
        err.write("[REJECTED] " + str(exc) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
