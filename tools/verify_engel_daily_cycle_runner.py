from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "engel_daily_cycle_runner.py"
VERIFIER = ROOT / "tools" / "verify_engel_daily_cycle_runner.py"
CONTRACT_VERIFIER = ROOT / "tools" / "verify_engel_daily_cycle_contract.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_DAILY_CYCLE_RUNNER_V1.md"
RECEIPT_DIR = ROOT / "reports" / "daily_cycle_receipts"

REQUIRED_STATUSES = [
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
    "NO_HIGH_RISK_SELF_FIX",
]

RECEIPT_FIELDS = [
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
    "one-cycle boundary",
    "max one daily cycle per command invocation",
    "foreground command only",
    "no startup autorun",
    "no endless loop",
    "no background worker",
    "no provider/network/browser",
    "no model runtime",
    "no package refresh",
    "no unapproved memory write",
    "no high-risk self-fix",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_runner_source() -> str:
    return RUNNER.read_text(encoding="utf-8", errors="replace")


def read_report() -> str:
    return REPORT.read_text(encoding="utf-8", errors="replace")


def load_runner():
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    spec = importlib.util.spec_from_file_location("engel_daily_cycle_runner", RUNNER)
    require(spec is not None and spec.loader is not None, "could not load daily cycle runner module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_daily_cycle_runner"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [RUNNER, VERIFIER, CONTRACT_VERIFIER, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))
    require(RECEIPT_DIR.exists() and RECEIPT_DIR.is_dir(), "bounded daily cycle receipt folder missing")
    require((RECEIPT_DIR / ".gitkeep").exists(), "bounded daily cycle receipt placeholder missing")


def check_required_text() -> None:
    text = read_runner_source() + "\n" + read_report()
    for status in REQUIRED_STATUSES:
        require(status in text, "runner missing required status: " + status)
    for field in RECEIPT_FIELDS:
        require(field in text, "runner missing receipt field: " + field)
    for boundary in REQUIRED_BOUNDARIES:
        require(boundary in text, "runner missing boundary: " + boundary)
    for needle in [
        "--dry-run",
        "--run",
        "--status-only",
        "--jobs",
        "--password-prompt",
        "engel_global_password_gate",
        "run_daily_cycle",
        "Protected action requires --password-prompt.",
        "reports",
        "daily_cycle_receipts",
        "Engel AI Growth Dashboard V1",
        "Engel Candidate Review Dashboard V1",
        "Research-to-Fix",
        "stale_pid_cleanup",
        "run_or_list_verifiers",
    ]:
        require(needle in text, "runner missing CLI/component text: " + needle)


def check_ast_safety() -> None:
    tree = ast.parse(read_runner_source())
    forbidden_imports = {
        "requests",
        "urllib",
        "socket",
        "webbrowser",
        "openai",
        "glob",
        "shutil",
        "threading",
        "multiprocessing",
    }
    forbidden_dynamic_names = {"exec", "eval", "__import__"}
    forbidden_attributes = {"walk", "rglob", "glob", "startfile"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in forbidden_imports, "runner imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in forbidden_imports, "runner imports forbidden module: " + node.module)
        if isinstance(node, ast.While):
            raise CheckFailure("runner contains a while loop")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in forbidden_dynamic_names, "runner uses forbidden dynamic execution call: " + node.func.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in forbidden_attributes, "runner uses forbidden scan/start call: " + node.func.attr)


def check_runtime_smoke() -> None:
    module = load_runner()

    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--status-only"], stdout=out, stderr=err) == 0, "--status-only failed")
    status_text = out.getvalue()
    for needle in ["DAILY_CYCLE_RUNNER", "ONE_CYCLE_PER_INVOCATION", "NO_BACKGROUND_WORKER", "python engel_daily_cycle_runner.py --dry-run"]:
        require(needle in status_text, "status-only output missing: " + needle)

    rendered, stopped = module.run_daily_cycle("dry-run", write_receipt=False)
    require(stopped is False, "dry-run internal smoke stopped unexpectedly")
    for needle in [
        "Engel Daily Cycle Runner V1",
        "Daily Cycle Verifier Stack",
        "Dry-run lists verifier commands without running them",
        "Low-Risk Self-Fix Dry-Run",
        "daily_cycle_run_id",
        "self_fix_dry_runs: 1",
        "self_fixes_applied: 0",
        "one foreground bounded daily cycle completed and stopped",
    ]:
        require(needle in rendered, "dry-run smoke missing: " + needle)

    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--dry-run", "--run"], stdout=out, stderr=err) == 2, "runner accepted multiple modes")

    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--run"], stdout=out, stderr=err) == 2, "run without password prompt was not refused")
    require("Protected action requires --password-prompt." in err.getvalue(), "missing password prompt refusal missing")


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_ast_safety()
        check_runtime_smoke()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel daily cycle runner verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
