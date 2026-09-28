#!/usr/bin/env python3
"""Verify the Engel C-drive project-file cleanup packet.

The verifier checks that Engel-owned Claude project memory was copied into
the D: workspace, runtime bridge folders live under D:, and active source
does not depend on the old C: Claude-project or Temp bridge locations.
"""
from __future__ import annotations

import ast
import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
C_MEMORY = Path(r"C:\Users\ziese\.claude\projects\d--b-WorkSpace\memory")
D_MEMORY = ROOT / "memory"
REPORT = ROOT / "reports" / "c_drive_cleanup" / "ENGEL_C_DRIVE_PROJECT_FILE_CLEANUP.md"
RUNTIME_AGENT_BRIDGE = ROOT / "runtime" / "agent_bridge"
RUNTIME_MEETING_ROOM = ROOT / "runtime" / "meeting_room"

MIGRATED_MEMORY_FILES = (
    "MEMORY.md",
    "project_engel_android_workers.md",
    "project_engel_external_memory.md",
    "project_engel_meeting_room.md",
    "project_engel_wave2_integration.md",
)

FORBIDDEN_ACTIVE_PATTERNS = (
    r"C:\Users\ziese\.claude\projects\d--b-WorkSpace",
    r"C:/Users/ziese/.claude/projects/d--b-WorkSpace",
)

TEMP_BRIDGE_PATTERNS = (
    r"AppData\Local\Temp",
    r"AppData/Local/Temp",
)


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def _python_strings_excluding_docstrings(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    docstring_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                docstring_ids.add(id(body[0].value))
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstring_ids:
            values.append(node.value)
    return values


def _active_source_files() -> list[Path]:
    files: list[Path] = []
    for pattern in ("*.py", "*.spec", "scripts/*.ps1", "tools/*.py"):
        files.extend(ROOT.glob(pattern))
    return sorted(set(files))


def check_memory_copies() -> None:
    for name in MIGRATED_MEMORY_FILES:
        dst = D_MEMORY / name
        require(dst.exists() and dst.is_file(), f"missing D: memory copy: memory/{name}")
        src = C_MEMORY / name
        if src.exists():
            require(sha256(src) == sha256(dst), f"hash mismatch after copy: {name}")


def check_cleanup_report() -> None:
    require(REPORT.exists() and REPORT.is_file(), "missing C-drive cleanup report")
    text = REPORT.read_text(encoding="utf-8", errors="replace")
    for needle in (
        "CLEANUP_STATUS: COPIED_TO_D_ACTIVE_CACHE_LEFT_ON_C",
        "Meeting Room work is unblocked",
        "Files left on C:",
        "Runtime path references fixed",
    ):
        require(needle in text, f"cleanup report missing required statement: {needle}")


def check_runtime_dirs() -> None:
    for folder in (RUNTIME_AGENT_BRIDGE, RUNTIME_MEETING_ROOM):
        require(folder.exists() and folder.is_dir(), f"missing runtime folder: {folder}")
        require((folder / ".gitkeep").exists(), f"missing runtime placeholder: {folder / '.gitkeep'}")


def check_no_active_c_storage_paths() -> None:
    bad: list[str] = []
    for path in _active_source_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel == "tools/verify_engel_c_drive_cleanup.py":
            continue
        if path.suffix == ".py":
            values = _python_strings_excluding_docstrings(path)
        else:
            values = [path.read_text(encoding="utf-8", errors="replace")]
        for value in values:
            if any(pattern in value for pattern in FORBIDDEN_ACTIVE_PATTERNS):
                bad.append(f"{rel}: active C: Claude project storage path")
            if any(pattern in value for pattern in TEMP_BRIDGE_PATTERNS) and "engel_agent_main" in value:
                bad.append(f"{rel}: active Temp engel_agent_main bridge path")
    require(not bad, "forbidden active C: storage references: " + "; ".join(bad))


def check_docs_point_to_d_workspace() -> None:
    for name in ("project_engel_android_workers.md", "project_engel_meeting_room.md", "project_engel_wave2_integration.md"):
        text = (D_MEMORY / name).read_text(encoding="utf-8", errors="replace")
        require("D:\\b.WorkSpace\\Engel App" in text or "engel_" in text, f"copied project memory lacks D/workspace context: {name}")


def main() -> int:
    checks = (
        check_memory_copies,
        check_cleanup_report,
        check_runtime_dirs,
        check_no_active_c_storage_paths,
        check_docs_point_to_d_workspace,
    )
    failures: list[str] = []
    for check in checks:
        try:
            check()
            print(f"PASS  {check.__name__}")
        except Exception as exc:
            print(f"FAIL  {check.__name__}: {exc}")
            failures.append(f"{check.__name__}: {exc}")
    if failures:
        print()
        print("ENGEL_C_DRIVE_CLEANUP_VERIFY_FAIL")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print()
    print("ENGEL_C_DRIVE_CLEANUP_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
