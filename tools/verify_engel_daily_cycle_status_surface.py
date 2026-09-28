from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SURFACE = ROOT / "engel_daily_cycle_status_surface.py"
VERIFIER = ROOT / "tools" / "verify_engel_daily_cycle_status_surface.py"
RECEIPT_DIR = ROOT / "reports" / "daily_cycle_receipts"

REQUIRED_STATUSES = [
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

REQUIRED_RUNNER_STATUS = [
    "DAILY_CYCLE_RUNNER",
    "FOREGROUND_COMMAND_ONLY",
    "BOUNDED_RUN_ONLY",
    "ONE_CYCLE_PER_INVOCATION",
    "RECEIPT_REQUIRED",
    "NO_ENDLESS_LOOP",
]

REQUIRED_DISPLAY_FIELDS = [
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

REQUIRED_BOUNDARIES = [
    "reports\\daily_cycle_receipts",
    "non-recursive receipt count",
    "Recent receipt names",
    "dry-run",
    "run",
    "stopped",
    "stop_reason",
    "verifiers_run",
    "learning_jobs_run",
    "candidates_seen",
    "self_fix_dry_runs",
    "self_fixes_applied",
    "final_summary",
    "no daily cycle execution",
    "no learning scheduler run",
    "no self-fix execution",
    "no memory promotion",
    "no source mutation",
    "no provider/network/browser",
    "no background worker",
    "no startup autorun",
    "no endless loop",
]

REQUIRED_CLI = [
    "python engel_daily_cycle_status_surface.py",
    "--list",
    "--show",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_surface() -> str:
    return SURFACE.read_text(encoding="utf-8", errors="replace")


def load_surface():
    spec = importlib.util.spec_from_file_location("engel_daily_cycle_status_surface", SURFACE)
    require(spec is not None and spec.loader is not None, "could not load daily cycle status surface module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_daily_cycle_status_surface"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [SURFACE, VERIFIER]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))
    require(RECEIPT_DIR.exists() and RECEIPT_DIR.is_dir(), "bounded daily cycle receipt folder missing")


def check_required_text() -> None:
    module = load_surface()
    text = read_surface() + "\n" + module.render_status_surface() + "\n" + module.render_receipt_list()
    for needle in REQUIRED_STATUSES + REQUIRED_RUNNER_STATUS + REQUIRED_DISPLAY_FIELDS + REQUIRED_BOUNDARIES + REQUIRED_CLI:
        require(needle in text, "daily cycle status surface missing required text: " + needle)
    for needle in [
        "READ_ONLY_VIEW / DAILY_CYCLE_STATUS_SURFACE / BOUNDED_REPORTS_ONLY",
        "Only a receipt file name is accepted, not a path.",
        "Path traversal and drive names are not accepted.",
        "Daily cycle receipt names must be safe .md file names.",
        "Receipt path escaped reports",
        "Display fields available in --show",
    ]:
        require(needle in text, "daily cycle status surface missing boundary text: " + needle)


def check_forbidden_active_behavior() -> None:
    source = read_surface()
    forbidden_text = [
        "run_daily_cycle(",
        "run_jobs_from_file(",
        "run_issue(",
        "subprocess.run",
        "Popen",
        "write_text(",
        "write_bytes(",
        "mkdir(",
        "unlink(",
        "remove(",
        "rename(",
        "replace(",
    ]
    for needle in forbidden_text:
        require(needle not in source, "viewer contains forbidden run/write behavior: " + needle)

    tree = ast.parse(source)
    forbidden_imports = {
        "requests",
        "urllib",
        "socket",
        "webbrowser",
        "openai",
        "subprocess",
        "glob",
        "shutil",
        "threading",
        "multiprocessing",
        "engel_daily_cycle_runner",
        "engel_bounded_self_learning_scheduler",
        "engel_low_risk_self_fix_runner",
        "engel_memory_promotion_writer",
    }
    forbidden_calls = {"exec", "eval", "__import__"}
    forbidden_attributes = {
        "walk",
        "rglob",
        "glob",
        "write_text",
        "write_bytes",
        "mkdir",
        "unlink",
        "remove",
        "rmdir",
        "rename",
        "replace",
        "touch",
        "run",
        "Popen",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                require(root_name not in forbidden_imports, "viewer imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".")[0]
            require(root_name not in forbidden_imports, "viewer imports forbidden module: " + node.module)
        if isinstance(node, ast.While):
            raise CheckFailure("viewer contains a while loop")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in forbidden_calls, "viewer uses forbidden dynamic call: " + node.func.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in forbidden_attributes, "viewer uses forbidden scan/run/mutation call: " + node.func.attr)


def check_runtime_smoke() -> None:
    module = load_surface()

    out = io.StringIO()
    err = io.StringIO()
    require(module.main([], stdout=out, stderr=err) == 0, "status surface no-argument smoke failed")
    output = out.getvalue()
    for needle in [
        "Engel Daily Cycle Status Surface V1",
        "DAILY_CYCLE_STATUS_SURFACE",
        "READ_ONLY_VIEW",
        "reports\\daily_cycle_receipts\\",
        "non-recursive receipt count",
        "Recent receipt names",
        "verifiers_run",
        "learning_jobs_run",
        "candidates_seen",
        "self_fix_dry_runs",
        "self_fixes_applied",
        "final_summary",
        "no startup autorun",
        "no endless loop",
    ]:
        require(needle in output, "status surface output missing: " + needle)

    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--list"], stdout=out, stderr=err) == 0, "--list smoke failed")
    list_output = out.getvalue()
    for needle in [
        "DAILY_CYCLE_STATUS_SURFACE",
        "READ_ONLY_VIEW",
        "RECEIPTS_VISIBLE",
        "reports\\daily_cycle_receipts\\",
        "Daily cycle receipts:",
    ]:
        require(needle in list_output, "--list output missing: " + needle)

    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--list", "--show", "receipt.md"], stdout=out, stderr=err) == 2, "viewer accepted --list with --show")

    for unsafe in [
        "https://example.com/receipt.md",
        "\\\\server\\share\\receipt.md",
        "..\\outside.md",
        "memory\\receipt.md",
        "receipt*.md",
        "G:\\ENGEL_APP_MEMORY\\receipt.md",
        "E:\\ENGEL_APP_MEMORY\\receipt.md",
    ]:
        try:
            module.resolve_receipt_path(unsafe)
        except module.DailyCycleStatusSurfaceError:
            continue
        raise CheckFailure("viewer accepted unsafe receipt name: " + unsafe)


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_forbidden_active_behavior()
        check_runtime_smoke()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel daily cycle status surface verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
