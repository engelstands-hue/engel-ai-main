from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "engel_ai.py"
ROUTE_MODULE = ROOT / "engel_ai_update_routes.py"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CORE_MD = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md"
CORE_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
CORE_BUILDER = ROOT / "tools" / "build_engel_core_continuity_map.py"
CORE_VERIFIER = ROOT / "tools" / "verify_engel_core_continuity_map.py"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
RUN_ENTRY_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_RUN_ENTRY_V1.md"
CURRENT_REPORT = ROOT / "reports" / "codex_bridge" / "CONNECT_NEW_ENGEL_AI_SURFACES_PACKAGE_REFRESH.md"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def run_entry(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENTRY), *args],
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def check_files() -> None:
    for path in [
        ENTRY,
        ROUTE_MODULE,
        COMMANDS,
        CORE_MD,
        CORE_JSON,
        CORE_BUILDER,
        CORE_VERIFIER,
        CODEX_VERIFY,
        RUN_ENTRY_REPORT,
        CURRENT_REPORT,
    ]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path.relative_to(ROOT)))


def check_import_safe() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_ai", ENTRY)
    require(spec is not None and spec.loader is not None, "could not create engel_ai import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for attr in ["ask_engel_ai", "render_routes", "run_self_test", "chat_loop", "main"]:
        require(hasattr(module, attr), "engel_ai missing callable: " + attr)
    ok, rendered = module.run_self_test()
    require(ok is True, "run_self_test did not pass when called after import")
    require("Engel AI Run Entry V1 Self-Test" in rendered, "self-test render missing title")


def check_static_safety() -> None:
    source = read(ENTRY)
    tree = ast.parse(source)
    for needle in [
        "route_companion_text_or_command",
        "SELF_TEST_PHRASES",
        "AUTONOMY_ALLOWED",
        "BACKGROUND_WORK_ALLOWED",
        "PROVIDER_NETWORK_ALLOWED",
        "EXPLICIT_USER_ACTION_ONLY",
        "HOST_ROUTER_STATE: NO_MUTATION",
        "NO_MEMORY_PROMOTION",
        "NO_TRUSTED_MEMORY_WRITE",
        "if __name__ == \"__main__\"",
    ]:
        require(needle in source, "engel_ai.py missing safety/entry text: " + needle)

    forbidden_import_roots = {
        "requests",
        "urllib",
        "socket",
        "webbrowser",
        "subprocess",
        "threading",
        "multiprocessing",
        "shutil",
        "openai",
        "llama",
        "ollama",
    }
    forbidden_calls = {
        "write_text",
        "write_bytes",
        "unlink",
        "remove",
        "rename",
        "replace",
        "mkdir",
        "rmdir",
        "Popen",
        "run",
        "system",
        "startfile",
    }
    forbidden_names = {
        "promote_memory",
        "trusted_memory_write",
        "apply_fix",
        "approve_candidate",
        "archive_sync",
        "archive_copy",
        "archive_delete",
        "archive_migrate",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in forbidden_import_roots, "engel_ai imports forbidden package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in forbidden_import_roots, "engel_ai imports forbidden package: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                require(func.attr not in forbidden_calls, "engel_ai contains forbidden call: " + func.attr)
                require(func.attr not in forbidden_names, "engel_ai contains forbidden action call: " + func.attr)
            elif isinstance(func, ast.Name):
                require(func.id not in forbidden_calls, "engel_ai contains forbidden call: " + func.id)
                require(func.id not in forbidden_names, "engel_ai contains forbidden action call: " + func.id)


def check_cli_modes() -> None:
    ask_status = run_entry("ask", "what is engel status")
    require(ask_status.returncode == 0, "ask status route failed")
    require("Engel Progress Dashboard" in ask_status.stdout, "ask status output missing progress dashboard")
    require("NO_TRUSTED_MEMORY_WRITE" in ask_status.stdout, "ask status output missing trusted-memory guard")

    ask_memory = run_entry("ask", "check memory candidates")
    require(ask_memory.returncode == 0, "ask memory route failed")
    require("Engel Memory Candidate Inventory" in ask_memory.stdout, "ask memory output missing inventory")
    require("NO_MEMORY_PROMOTION" in ask_memory.stdout, "ask memory output missing promotion guard")

    ask_archive = run_entry("ask", "archive shelf status")
    require(ask_archive.returncode == 0, "ask archive route failed")
    require("Engel Archive Shelf Manager" in ask_archive.stdout, "ask archive output missing shelf manager")
    require("NO_ARCHIVE_MIGRATION" in ask_archive.stdout, "ask archive output missing archive mutation guard")

    ask_3d = run_entry("ask", "engel3d status")
    require(ask_3d.returncode == 0, "ask engel3d status route failed")
    require("Engel3D Office" in ask_3d.stdout, "ask engel3d output missing status title")

    routes = run_entry("routes")
    require(routes.returncode == 0, "routes mode failed")
    for needle in [
        "progress dashboard",
        "memory candidate inventory",
        "archive shelf manager",
        "Engel Agent",
        "Engel3D",
        "Engel Sandbox",
        "explicit user action route",
        "AUTONOMY_ALLOWED",
        "EXPLICIT_USER_ACTION_ONLY",
        "NO_MEMORY_PROMOTION",
    ]:
        require(needle in routes.stdout, "routes output missing: " + needle)

    self_test = run_entry("self-test")
    require(self_test.returncode == 0, "self-test mode failed")
    for needle in [
        "Engel AI Run Entry V1 Self-Test",
        "what is engel status",
        "check memory candidates",
        "archive shelf status",
        "is I drive required",
        "engel agent status",
        "engel3d status",
        "Result: PASS",
    ]:
        require(needle in self_test.stdout, "self-test output missing: " + needle)


def check_docs_and_registration() -> None:
    commands = read(COMMANDS)
    core_md = read(CORE_MD)
    core_json = read(CORE_JSON)
    builder = read(CORE_BUILDER)
    core_verifier = read(CORE_VERIFIER)
    codex = read(CODEX_VERIFY)
    current_report = read(CURRENT_REPORT)
    for needle in [
        "Engel AI run entry",
        "python engel_ai.py chat",
        "python engel_ai.py ask \"what is engel status\"",
        "python engel_ai.py routes",
        "python engel_ai.py self-test",
        "explicit user-invoked routes",
    ]:
        require(needle in commands, "ENGEL_COMMANDS missing run-entry text: " + needle)
    for needle in [
        "Engel AI Run Entry V1",
        "Safe local Engel AI run entrypoint",
        "engel_ai.py",
        "EXPLICIT_USER_ACTION_ROUTES_CONNECTED",
        "No hidden autonomy",
        "Explicit action routes are user-invoked only",
    ]:
        require(needle in core_md, "Core Continuity markdown missing run-entry text: " + needle)
        require(needle in builder or needle in core_verifier or needle in core_json, "Core Continuity source missing run-entry text: " + needle)
    require("engel_ai_run_entry_v1" in core_json, "Core Continuity JSON missing run-entry node")
    require("check_engel_ai_run_entry" in core_verifier, "Core Continuity verifier missing run-entry check")
    require("tools\\verify_engel_ai_run_entry.py" in codex, "codex_verify missing run-entry verifier")
    for needle in [
        "Connected New Engel AI surfaces",
        "Engel Agent",
        "Engel3D",
        "Engel Sandbox",
        "No hidden autonomy",
        "package refresh",
    ]:
        require(needle in current_report, "current New Engel AI report missing text: " + needle)


def main() -> int:
    try:
        check_files()
        check_import_safe()
        check_static_safety()
        check_cli_modes()
        check_docs_and_registration()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel AI run entry verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
