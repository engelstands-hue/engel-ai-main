#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HELPER = ROOT / "engel_memory_archive_status.py"
RESEARCH_DATA = ROOT / "engel_research_office_data.py"
APP = ROOT / "engel_app.py"
CONTRACT = ROOT / "memory" / "ENGEL_EXTERNAL_LONG_TERM_MEMORY_ROOTS_V1.json"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_B_WORKSTATION_MEMORY_ARCHIVE_PATH_FIX.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    require(path.exists(), "missing required file: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def compile_file(path: Path) -> None:
    try:
        compile(read(path), str(path), "exec")
    except SyntaxError as exc:
        raise CheckFailure("compile failed for " + str(path.relative_to(ROOT)) + ": " + str(exc)) from exc


def load_helper():
    spec = importlib.util.spec_from_file_location("engel_memory_archive_status", HELPER)
    require(spec is not None and spec.loader is not None, "could not load helper spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_memory_archive_status"] = module
    spec.loader.exec_module(module)
    return module


def check_static_source() -> None:
    compile_file(HELPER)
    compile_file(RESEARCH_DATA)
    compile_file(APP)
    compile_file(ROOT / "tools" / "verify_engel_memory_archive_status.py")

    helper_source = read(HELPER)
    research_source = read(RESEARCH_DATA)
    app_source = read(APP)
    tree = ast.parse(helper_source)

    for needle in [
        "CONFIGURED_EXTERNAL_ARCHIVE_PATHS",
        r"E:\ENGEL_APP_MEMORY",
        r"F:\ENGEL_APP_MEMORY",
        r"G:\ENGEL_APP_MEMORY",
        r"I:\ENGEL_APP_MEMORY",
        "DEPRECATED_ARCHIVE_PATHS",
        "external_archive_required",
        "missing_external_archive_is_failure",
        "archive_migration_enabled",
        "archive_sync_enabled",
        "trusted_memory_write_enabled",
        "source_patch_apply_enabled",
        "queue_route_mutation_enabled",
        r"D:\b.WorkSpace\Engel App",
        "ACTIVE_MEMORY_ROOT",
        "PROJECT_LOCAL_ARCHIVE_FALLBACK",
    ]:
        require(needle in helper_source, "helper missing required text: " + needle)

    require(r'ENGEL_LONG_TERM_MEMORY_DRIVE = r"I:\ENGEL_APP_MEMORY"' not in research_source, "research office still treats I archive as active constant")
    require("build_memory_archive_snapshot()" in research_source, "research office must delegate archive snapshot to helper")
    require("render_memory_archive_status()" in research_source, "research office must delegate archive render to helper")
    require("D:\\\\b.WorkSpace\\\\Engel App" in app_source, "app fallback must name active b.WorkSpace root")

    forbidden_text = [
        "shutil",
        "copyfile",
        "copytree",
        ".write_text(",
        ".write_bytes(",
        ".unlink(",
        ".remove(",
        ".rename(",
        ".mkdir(",
        "subprocess",
        "Popen",
        "os.system",
        "shell=True",
        "requests",
        "httpx",
        "socket",
        "openai",
        "anthropic",
        "webbrowser",
        "eval(",
        "exec(",
    ]
    lowered = helper_source.lower()
    for forbidden in forbidden_text:
        require(forbidden.lower() not in lowered, "helper contains forbidden mutation/runtime pattern: " + forbidden)

    blocked_imports = {"shutil", "subprocess", "requests", "httpx", "socket", "openai", "anthropic", "webbrowser"}
    blocked_methods = {"write_text", "write_bytes", "unlink", "remove", "rename", "mkdir", "rmdir", "touch"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in blocked_imports, "helper imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in blocked_imports, "helper imports blocked module: " + node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in blocked_methods, "helper calls blocked mutation method: " + node.func.attr)


def check_contract() -> None:
    payload = json.loads(read(CONTRACT))
    require(payload.get("active_app_root") == r"D:\b.WorkSpace\Engel App", "contract active app root mismatch")
    require(payload.get("active_work_root") == r"D:\b.WorkSpace\Engel App", "contract active work root mismatch")
    require(payload.get("active_memory_root") == r"D:\b.WorkSpace\Engel App\memory", "contract active memory root mismatch")
    require(payload.get("project_local_archive_fallback") == r"D:\b.WorkSpace\Engel App\memory\ENGEL_APP_MEMORY", "contract fallback mismatch")
    require(payload.get("external_archive_required") is False, "external archive must not be required")
    require(payload.get("external_archive_default_path") is None, "external archive default path must be null")
    require(payload.get("missing_external_archive_is_failure") is False, "missing external archive must not fail")
    require(payload.get("archive_migration_enabled") is False, "archive migration must be disabled")
    require(payload.get("archive_sync_enabled") is False, "archive sync must be disabled")
    require(payload.get("trusted_memory_write_enabled") is False, "trusted memory write must be disabled")
    require(r"I:\ENGEL_APP_MEMORY" in payload.get("deprecated_paths", []), "deprecated I archive path missing")

    roots = payload.get("external_roots", [])
    by_path = {root.get("path"): root for root in roots if isinstance(root, dict)}
    for path in [r"E:\ENGEL_APP_MEMORY", r"F:\ENGEL_APP_MEMORY", r"G:\ENGEL_APP_MEMORY"]:
        require(path in by_path, "configured external archive root missing: " + path)
        require(by_path[path].get("scan_policy") == "NO_BROAD_SCAN", "scan policy mismatch for " + path)
        require(by_path[path].get("trusted_memory_write") == "BLOCKED", "trusted memory policy mismatch for " + path)
    require(r"I:\ENGEL_APP_MEMORY" not in by_path, "deprecated I archive path must not be an active root")


def check_behavior() -> None:
    helper = load_helper()
    old_i = "I:" + "\\ENGEL_APP_MEMORY"
    old_active_root = "D:" + "\\Engel App"
    old_shelf_phrase = "cold archive" + " / long-term memory shelf"
    snapshot = helper.build_memory_archive_snapshot()
    rendered = helper.render_memory_archive_status()
    missing_snapshot = helper.build_memory_archive_snapshot(r"Z:\ENGEL_APP_MEMORY")
    missing_rendered = helper.render_memory_archive_status(r"Z:\ENGEL_APP_MEMORY")

    require(snapshot.get("external_archive_required") is False, "default snapshot must not require external archive")
    require(snapshot.get("missing_external_archive_is_failure") is False, "default snapshot must not fail missing external archive")
    for path in [r"E:\ENGEL_APP_MEMORY", r"F:\ENGEL_APP_MEMORY", r"G:\ENGEL_APP_MEMORY"]:
        require(path in snapshot.get("configured_external_archive_paths", []), "default configured roots missing " + path)
        if Path(path).exists():
            require(path in snapshot.get("available_archive_roots", []), "existing archive root not shown available: " + path)
            require((path + " | available") in rendered, "rendered status does not show available root: " + path)

    require(missing_snapshot.get("archive_status") == "optional_unavailable", "missing explicit archive must be optional_unavailable")
    require(missing_snapshot.get("missing_external_archive_is_failure") is False, "missing explicit archive must not fail")
    require("optional_unavailable" in missing_rendered, "missing render must show optional_unavailable")

    for text in [rendered, missing_rendered]:
        require(r"D:\b.WorkSpace\Engel App" in text, "rendered status missing active work root")
        require(r"D:\b.WorkSpace\Engel App\memory" in text, "rendered status missing active memory root")
        require(r"D:\b.WorkSpace\Engel App\memory\ENGEL_APP_MEMORY" in text, "rendered status missing project fallback")
        require("NO_ARCHIVE_MIGRATION" in text, "rendered status missing migration safety")
        require("NO_ARCHIVE_COPY" in text, "rendered status missing copy safety")
        require("NO_ARCHIVE_SYNC" in text, "rendered status missing sync safety")
        require("NO_ARCHIVE_DELETE" in text, "rendered status missing delete safety")
        require("NO_TRUSTED_MEMORY_WRITE" in text, "rendered status missing trusted-memory safety")
        require("NO_SOURCE_PATCH_APPLY" in text, "rendered status missing source patch safety")
        require((old_i + ": missing") not in text, "rendered status still reports I archive as missing dependency")
        require((old_i + " marker present") not in text, "rendered status still reports I marker")
        require((old_i + " top-level folders/files") not in text, "rendered status still reports I counts")
        require(("active work stays on " + old_active_root) not in text, "rendered status still names old active root")
        require(old_shelf_phrase not in text, "rendered status still uses old I archive wording")


def check_route_output() -> None:
    spec = importlib.util.spec_from_file_location("engel_research_office_data", RESEARCH_DATA)
    require(spec is not None and spec.loader is not None, "could not load research office data")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_research_office_data"] = module
    spec.loader.exec_module(module)
    text = module.render_long_term_memory_drive_status()
    connections = module.render_engel_mind_connections_status(ROOT)
    old_i = "I:" + "\\ENGEL_APP_MEMORY"
    old_active_root = "D:" + "\\Engel App"

    for output in [text, connections]:
        require((old_i + ": missing") not in output, "route output reports I archive as missing")
        require((old_i + " marker present") not in output, "route output reports I marker")
        require((old_i + " top-level folders/files") not in output, "route output reports I counts")
        require(("active work stays on " + old_active_root) not in output, "route output names old active work root")
        require(r"D:\b.WorkSpace\Engel App" in output, "route output missing active b.WorkSpace root")
    require("Configured external archive roots are available." in text, "long-term status must show available E/F/G roots")


def check_registration_and_report() -> None:
    codex = read(CODEX_VERIFY)
    require(r"tools\verify_engel_memory_archive_status.py" in codex, "codex verifier missing archive verifier")
    report = read(REPORT)
    for needle in [
        "Removed the false requirement that b.workstation must have I:\\ENGEL_APP_MEMORY",
        "E:\\ENGEL_APP_MEMORY",
        "F:\\ENGEL_APP_MEMORY",
        "G:\\ENGEL_APP_MEMORY",
        "D:\\b.WorkSpace\\Engel App",
        "optional",
        "No archive migration",
        "No trusted-memory promotion",
        "No copy/sync/delete",
        "No package build",
    ]:
        require(needle in report, "report missing text: " + needle)


def main() -> int:
    checks = [
        ("static_source", check_static_source),
        ("contract", check_contract),
        ("behavior", check_behavior),
        ("route_output", check_route_output),
        ("registration_and_report", check_registration_and_report),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(name + ": " + str(exc))
            print("FAIL " + name + ": " + str(exc))
        except Exception as exc:
            failures.append(name + ": unexpected error: " + str(exc))
            print("FAIL " + name + ": unexpected error: " + str(exc))

    if failures:
        print()
        print("ENGEL_MEMORY_ARCHIVE_STATUS_VERIFY_FAIL")
        for failure in failures:
            print("- " + failure)
        return 1

    print()
    print("ENGEL_MEMORY_ARCHIVE_STATUS_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
