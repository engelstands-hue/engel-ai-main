from __future__ import annotations

import ast
import importlib.util
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCHEDULER = ROOT / "engel_bounded_self_learning_scheduler.py"
VERIFIER = ROOT / "tools" / "verify_engel_bounded_self_learning_scheduler.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_BOUNDED_SELF_LEARNING_SCHEDULER_V1.md"
RECEIPT_DIR = ROOT / "reports" / "self_learning_scheduler_receipts"

REQUIRED_STATUSES = [
    "BOUNDED_SELF_LEARNING_SCHEDULER",
    "FOREGROUND_COMMAND_ONLY",
    "EXPLICIT_JOB_LIST_ONLY",
    "MAX_THREE_JOBS_PER_RUN",
    "ONE_TOPIC_ONE_SOURCE_PER_JOB",
    "CANDIDATE_OUTPUTS_ONLY",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_VERIFIER_UPDATE",
    "NO_SELF_FIX_POLICY_UPDATE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_AUTO_DOWNLOADS",
    "NO_AUTO_INDEXING",
    "NO_MODEL_TRAINING",
    "NO_RUNTIME_TRIGGER",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
]

RECEIPT_FIELDS = [
    "scheduler_run_id",
    "jobs_requested",
    "jobs_run",
    "jobs_stopped",
    "output_paths",
    "safety_boundary",
    "verification_summary",
    "stopped",
    "stop_reason",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_source() -> str:
    return SCHEDULER.read_text(encoding="utf-8", errors="replace")


def load_scheduler():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_bounded_self_learning_scheduler", SCHEDULER)
    require(spec is not None and spec.loader is not None, "could not load scheduler module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_bounded_self_learning_scheduler"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [SCHEDULER, VERIFIER, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path.relative_to(ROOT)))
    require(RECEIPT_DIR.exists() and RECEIPT_DIR.is_dir(), "scheduler receipt folder missing")


def check_required_text() -> None:
    text = read_source() + "\n" + REPORT.read_text(encoding="utf-8", errors="replace")
    text_lower = " ".join(text.lower().split())
    for needle in REQUIRED_STATUSES + RECEIPT_FIELDS:
        require(needle in text, "scheduler missing required status/field: " + needle)
    for needle in [
        "--demo",
        "--jobs",
        "--dry-run",
        "--write-candidates",
        "--password-prompt",
        "engel_global_password_gate",
        "run_bounded_self_learning_scheduler",
        "Protected action requires --password-prompt.",
        "MAX_JOBS_PER_RUN = 3",
        "len(payload) > MAX_JOBS_PER_RUN",
        "EXPLICIT_JOB_LIST_ONLY",
        "ONE_TOPIC_ONE_SOURCE_PER_JOB",
        "max three jobs per run",
        "one topic and one source per job",
        "No implicit topic selection",
        "no startup integration",
        "no background worker",
        "reports\\self_learning_scheduler_receipts",
        "topic_id",
        "source",
    ]:
        require(" ".join(needle.lower().split()) in text_lower, "scheduler missing required CLI/rule text: " + needle)


def check_report_text() -> None:
    text = REPORT.read_text(encoding="utf-8", errors="replace")
    for needle in [
        "Engel Bounded Self-Learning Scheduler V1",
        "Files Read First",
        "Files Created",
        "Scheduler Behavior",
        "CLI Behavior",
        "Smoke Results",
        "Verification Results",
        "Focused Safety Scan",
        "python engel_bounded_self_learning_scheduler.py --demo",
        "python engel_bounded_self_learning_scheduler.py --jobs <project-local-json> --dry-run",
        "python engel_bounded_self_learning_scheduler.py --jobs <project-local-json> --write-candidates",
    ]:
        require(needle in text, "scheduler report missing text: " + needle)


def check_forbidden_active_behavior() -> None:
    tree = ast.parse(read_source())
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
        "ctypes",
    }
    forbidden_calls = {"exec", "eval", "__import__", "Popen", "system", "startfile"}
    forbidden_attributes = {"walk", "rglob", "glob", "unlink", "remove", "rename"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in forbidden_imports, "scheduler imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in forbidden_imports, "scheduler imports forbidden module: " + node.module)
        if isinstance(node, ast.While):
            raise CheckFailure("scheduler contains a while loop")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in forbidden_calls, "scheduler uses forbidden call: " + node.func.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in forbidden_attributes, "scheduler uses forbidden scan/mutation call: " + node.func.attr)


def write_temp_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def check_runtime_smoke() -> None:
    scheduler = load_scheduler()
    safe_jobs = ROOT / "scheduler_verifier_temp_jobs.json"
    too_many_jobs = ROOT / "scheduler_verifier_temp_many_jobs.json"
    unsafe_jobs = ROOT / "scheduler_verifier_temp_unsafe_jobs.json"
    try:
        out = io.StringIO()
        err = io.StringIO()
        require(scheduler.main([], stdout=out, stderr=err) == 0, "scheduler usage failed")
        require("BOUNDED_SELF_LEARNING_SCHEDULER" in out.getvalue(), "usage missing scheduler status")

        out = io.StringIO()
        err = io.StringIO()
        require(scheduler.main(["--demo"], stdout=out, stderr=err) == 0, "scheduler demo failed")
        demo = out.getvalue()
        for needle in ["DEMO_ONLY", "FOREGROUND_COMMAND_ONLY", "MAX_THREE_JOBS_PER_RUN", "NO_BACKGROUND_WORKER"]:
            require(needle in demo, "demo missing text: " + needle)

        write_temp_json(
            safe_jobs,
            [
                {
                    "topic_id": "SRT-01-01-python_error_handling_patterns_for_local_tools",
                    "source": "memory\\ENGEL_SELF_RESEARCH_CONTRACT_V1.md",
                }
            ],
        )
        out = io.StringIO()
        err = io.StringIO()
        require(scheduler.main(["--jobs", str(safe_jobs.relative_to(ROOT)), "--dry-run"], stdout=out, stderr=err) == 0, "scheduler safe dry-run failed")
        dry = out.getvalue()
        require("jobs_requested: 1" in dry and "jobs_run: 1" in dry and "DRY_RUN_NOT_WRITTEN" in dry, "dry-run output missing expected summary")

        out = io.StringIO()
        err = io.StringIO()
        require(
            scheduler.main(["--jobs", str(safe_jobs.relative_to(ROOT)), "--write-candidates"], stdout=out, stderr=err) == 2,
            "write-candidates without password prompt was not refused",
        )
        require("Protected action requires --password-prompt." in err.getvalue(), "missing password prompt refusal missing")

        write_temp_json(
            too_many_jobs,
            [
                {"topic_id": "SRT-01-01-python_error_handling_patterns_for_local_tools", "source": "memory\\ENGEL_SELF_RESEARCH_CONTRACT_V1.md"},
                {"topic_id": "SRT-01-01-python_error_handling_patterns_for_local_tools", "source": "memory\\ENGEL_SELF_RESEARCH_CONTRACT_V1.md"},
                {"topic_id": "SRT-01-01-python_error_handling_patterns_for_local_tools", "source": "memory\\ENGEL_SELF_RESEARCH_CONTRACT_V1.md"},
                {"topic_id": "SRT-01-01-python_error_handling_patterns_for_local_tools", "source": "memory\\ENGEL_SELF_RESEARCH_CONTRACT_V1.md"},
            ],
        )
        out = io.StringIO()
        err = io.StringIO()
        require(scheduler.main(["--jobs", str(too_many_jobs.relative_to(ROOT)), "--dry-run"], stdout=out, stderr=err) == 1, "scheduler accepted more than three jobs")

        write_temp_json(
            unsafe_jobs,
            [
                {
                    "topic_id": "SRT-01-01-python_error_handling_patterns_for_local_tools",
                    "source": "https://example.com/source.md",
                }
            ],
        )
        out = io.StringIO()
        err = io.StringIO()
        require(scheduler.main(["--jobs", str(unsafe_jobs.relative_to(ROOT)), "--dry-run"], stdout=out, stderr=err) == 1, "scheduler accepted unsafe URL source")
        require("jobs_stopped: 1" in out.getvalue(), "unsafe source did not stop job")
    finally:
        for path in [safe_jobs, too_many_jobs, unsafe_jobs]:
            if path.exists():
                path.unlink()


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_report_text()
        check_forbidden_active_behavior()
        check_runtime_smoke()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel bounded self-learning scheduler verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
