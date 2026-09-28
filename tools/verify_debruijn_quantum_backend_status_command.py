#!/usr/bin/env python3
"""Verify the De Bruijn Quantum backend status command remains read-only."""

from __future__ import annotations

import ast
import hashlib
import py_compile
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "engel_app.py"
HELPER_PATH = ROOT / "engel_debruijn_quantum_structure_status.py"
COMMANDS_PATH = ROOT / "memory" / "ENGEL_COMMANDS.md"
ROUTE_SET_PATH = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
REPORT_ROOT = ROOT / "reports" / "debruijn_quantum_file_structure"

COMMAND = "engel ai debruijn quantum status"
SUCCESS = "DEBRUIJN_QUANTUM_BACKEND_STATUS_COMMAND_VERIFICATION_PASS"


class CheckFailure(Exception):
    pass


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def info(message: str) -> None:
    print("INFO " + message)


def passed(message: str) -> None:
    print("PASS " + message)


def fail(message: str) -> None:
    print("FAIL " + message)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)
    passed(message)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig")


def snapshot_reports() -> dict[str, tuple[int, int, str]]:
    snapshot: dict[str, tuple[int, int, str]] = {}
    if not REPORT_ROOT.exists():
        return snapshot
    for path in sorted(REPORT_ROOT.glob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        snapshot[path.name] = (stat.st_mtime_ns, stat.st_size, digest)
    return snapshot


def compile_app() -> None:
    py_compile.compile(str(APP_PATH), doraise=True)
    passed("engel_app.py compiles")


def find_function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise CheckFailure(f"missing function {name}")


def call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts = [func.attr]
        value = func.value
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            parts.append(value.id)
        return ".".join(reversed(parts))
    return ""


def verify_command_function(tree: ast.AST) -> None:
    fn = find_function(tree, "debruijn_quantum_backend_status_command_v1")
    imports = [
        node
        for node in ast.walk(fn)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    require(len(imports) == 1, "command function has exactly one local helper import")
    imported = imports[0]
    require(
        isinstance(imported, ast.ImportFrom)
        and imported.module == "engel_debruijn_quantum_structure_status",
        "command function imports only the backend status helper",
    )

    forbidden_call_fragments = {
        "subprocess",
        "os.system",
        "popen",
        "open",
        "write_text",
        "write_bytes",
        "mkdir",
        "touch",
        "unlink",
        "remove",
        "rmdir",
        "rmtree",
        "move",
        "copy",
        "replace",
        "rename",
        "scan_report",
        "propose_fixes",
    }
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            name = call_name(node).lower()
            if any(fragment in name for fragment in forbidden_call_fragments):
                raise CheckFailure(f"forbidden command handler call: {name}")
    passed("command handler has no write/subprocess/scan/propose/apply calls")


def verify_route_hook(source: str) -> None:
    require(COMMAND in source, "canonical command marker exists")
    require(
        'msg.lower().strip() == "engel ai debruijn quantum status"' in source,
        "canonical command has an exact route hook",
    )
    require(
        "debruijn_quantum_backend_status_command_v1() + \"\\n\"" in source,
        "route hook prints the backend status renderer only",
    )


def verify_docs_and_metadata() -> None:
    commands = read_text(COMMANDS_PATH)
    routes = read_text(ROUTE_SET_PATH)
    require(COMMAND in commands, "ENGEL_COMMANDS documents backend status command")
    for phrase in [
        "backend-only/read-only",
        "reads existing backend helper output only",
        "no UI/card/viewer",
        "no scan",
        "no files written",
        "no apply/move/delete/trust/promote",
    ]:
        require(phrase in commands, f"ENGEL_COMMANDS documents: {phrase}")
    require(COMMAND in routes, "route verification set includes backend status command")
    for phrase in [
        '"backend_only": true',
        '"existing_reports_only": true',
        '"no_ui": true',
        '"no_scan_run": true',
        '"no_files_written": true',
        '"no_apply": true',
        '"no_trusted_memory_write": true',
        '"no_route_mutation": true',
        '"no_queue_mutation": true',
    ]:
        require(phrase in routes, f"route metadata documents: {phrase}")


def verify_output_and_no_write() -> None:
    before = snapshot_reports()
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import engel_app; print(engel_app.debruijn_quantum_backend_status_command_v1())",
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=30,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    after = snapshot_reports()
    require(proc.returncode == 0, "backend status renderer executes successfully")
    if proc.stderr.strip():
        info("renderer stderr: " + proc.stderr.strip())
    output = proc.stdout
    for phrase in [
        "De Bruijn Quantum Backend Status",
        "backend_only:",
        "no UI",
        "no scan run",
        "no files written",
        "quantum-inspired only",
        "real quantum OFF",
        "provider/API OFF",
        "network OFF",
        "model inference OFF",
        "background worker OFF",
        "startup autorun OFF",
        "apply OFF",
        "file move/delete/rewrite OFF",
        "trusted memory write OFF",
        "route/queue mutation OFF",
        "no apply/move/delete/trust/promote behavior",
    ]:
        require(phrase in output, f"command output includes: {phrase}")
    require(before == after, "backend status renderer did not mutate De Bruijn reports")


def run_verifier(path: Path, marker: str | None = None) -> None:
    if not path.exists():
        raise CheckFailure(f"required verifier missing: {rel(path)}")
    proc = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=120,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if proc.stdout.strip():
        info(rel(path) + " stdout:\n" + proc.stdout.strip())
    if proc.stderr.strip():
        info(rel(path) + " stderr:\n" + proc.stderr.strip())
    require(proc.returncode == 0, f"{rel(path)} passed")
    if marker:
        require(marker in proc.stdout, f"{rel(path)} printed success marker")


def main() -> int:
    try:
        for path in [APP_PATH, HELPER_PATH, COMMANDS_PATH, ROUTE_SET_PATH]:
            require(path.exists(), f"required file exists: {rel(path)}")
        compile_app()
        source = read_text(APP_PATH)
        tree = ast.parse(source)
        verify_command_function(tree)
        verify_route_hook(source)
        verify_docs_and_metadata()
        verify_output_and_no_write()
        run_verifier(
            ROOT / "tools" / "verify_debruijn_quantum_structure_status_helper.py",
            "DEBRUIJN_QUANTUM_STRUCTURE_STATUS_HELPER_VERIFICATION_PASS",
        )
        run_verifier(
            ROOT / "tools" / "verify_engel_debruijn_quantum_automation_file_structure.py",
            "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_VERIFY_PASS",
        )
        run_verifier(ROOT / "tools" / "verify_route_metadata_contract.py")
        print(SUCCESS)
        return 0
    except Exception as exc:
        fail(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
