from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools" / "setup_android_worker_alpha_adb.py"
FINISH_RUNNER = ROOT / "remote_workers" / "android_worker_alpha" / "finish_alpha_job.py"
LOCAL_EXECUTOR = ROOT / "remote_workers" / "android_worker_alpha" / "remote_worker_local_executor.py"
FIRST_JOB = ROOT / "remote_workers" / "android_worker_alpha" / "jobs" / "20260516T201324Z_android_worker_alpha_summarize_text_summarize_engel_remote_worke.json"
ADB_VERIFIER = ROOT / "tools" / "verify_android_worker_alpha_adb_setup.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_ANDROID_WORKER_ALPHA_FINISH_SETUP_V1.md"
FORBIDDEN_SECOND_HELPER = ROOT / "tools" / "setup_android_worker_alpha_termux_adb.py"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "threading",
    "multiprocessing",
    "openai",
}


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_helper():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("setup_android_worker_alpha_adb", HELPER)
    require(spec is not None and spec.loader is not None, "could not load ADB helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules["setup_android_worker_alpha_adb"] = module
    spec.loader.exec_module(module)
    return module


def load_local_executor():
    worker_root = ROOT / "remote_workers" / "android_worker_alpha"
    if str(worker_root) not in sys.path:
        sys.path.insert(0, str(worker_root))
    spec = importlib.util.spec_from_file_location("remote_worker_local_executor", LOCAL_EXECUTOR)
    require(spec is not None and spec.loader is not None, "could not load worker local executor")
    module = importlib.util.module_from_spec(spec)
    sys.modules["remote_worker_local_executor"] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [HELPER, FINISH_RUNNER, LOCAL_EXECUTOR, FIRST_JOB, ADB_VERIFIER]:
        require(path.exists(), "required file missing: " + str(path.relative_to(ROOT)))
    require(not FORBIDDEN_SECOND_HELPER.exists(), "duplicate ADB/Termux helper must not exist")


def check_finish_runner_static() -> None:
    source = read(FINISH_RUNNER)
    tree = ast.parse(source)
    for phrase in [
        "validate_finish_job",
        "assigned_worker_id",
        "android_worker_alpha",
        "job_type",
        "summarize_text",
        "real_job",
        "job_template",
        "prepared_for_manual_transfer",
        "input_file_missing_or_outside_worker_folder",
        # finish runner now picks the newest unprocessed job, so process_job
        # is called with a dynamically-resolved Path (job_path) instead of
        # the constant JOB_PATH. Either form is acceptable.
        "process_job(",
        "trusted_memory_write",
        "patch_apply",
        "provider_network",
        "model_runtime",
        "requires_human_review",
    ]:
        require(phrase in source, "finish runner missing required validation/output text: " + phrase)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                require(root not in FORBIDDEN_IMPORTS, "finish runner imports forbidden package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            require(root not in FORBIDDEN_IMPORTS, "finish runner imports forbidden package: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                require(func.id not in {"eval", "exec", "__import__"}, "finish runner uses forbidden dynamic call: " + func.id)
            elif isinstance(func, ast.Attribute):
                require(func.attr not in {"system", "popen", "Popen"}, "finish runner contains shell execution call: " + func.attr)
        elif isinstance(node, ast.While):
            raise CheckFailure("finish runner must not contain a loop")
    lowered = source.lower()
    for snippet in [
        "adb ",
        "pkg install",
        "pip install",
        "download",
        "socket",
        "requests",
        "webbrowser",
        "openai",
        "hermes",
        "ollama",
        "llama.cpp",
    ]:
        require(snippet not in lowered, "finish runner contains forbidden active snippet: " + snippet)


def check_helper_modes() -> None:
    source = read(HELPER)
    for phrase in [
        "--prepare-one-line-termux-finish",
        "--push-finish-runner",
        "--finish-alpha-worker",
        "--i-approve-finish-alpha-worker",
        "one_line_termux_finish_command",
        "finish_alpha_job.py",
        "run_push_finish_runner",
        "run_finish_alpha_worker",
        "write_finish_attempt_receipt",
        "blocked_python_unavailable_in_adb_shell",
        "Termux Python is available only interactively. Open Termux and run: python finish_alpha_job.py",
        "no_fake_results",
        "no_trusted_memory_write",
        "no_patch_apply",
    ]:
        require(phrase in source, "helper missing finish setup phrase: " + phrase)
    for snippet in [
        "adb install",
        "adb tcpip",
        "adb connect",
        "pkg install",
        "pip install",
        "requests.",
        "socket.",
        "webbrowser.",
        "openai.",
    ]:
        require(snippet not in source, "helper contains forbidden finish/setup snippet: " + snippet)


def check_helper_runtime_non_mutating_modes() -> None:
    module = load_helper()
    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--prepare-one-line-termux-finish"], stdout=out, stderr=err) == 0, "prepare one-line mode failed")
    prepared = out.getvalue()
    for phrase in [
        "Paste this exact line into Termux",
        "cd ~/engel_remote_worker_alpha",
        "python finish_alpha_job.py",
        "cp -r status/* /sdcard/EngelRemoteWorker/android_worker_alpha/status/",
    ]:
        require(phrase in prepared, "one-line finish output missing: " + phrase)
    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--push-finish-runner"], stdout=out, stderr=err) == 2, "push-finish-runner without ack must block")
    require("--push-finish-runner requires --i-understand-this-uses-adb" in err.getvalue(), "push-finish-runner missing ack block")
    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--finish-alpha-worker"], stdout=out, stderr=err) == 2, "finish-alpha-worker without approval must block")
    require("--finish-alpha-worker requires --i-approve-finish-alpha-worker" in err.getvalue(), "finish-alpha-worker missing approval block")
    push_commands = [module.command_text(command) for command in module.finish_runner_push_commands()]
    require(not any("finish_alpha_job.py &&" in command for command in push_commands), "push-finish-runner must not run finish runner")
    require(not any("run_assigned_job.py" in command for command in push_commands), "push-finish-runner must not run worker job")


def check_worker_validation_behavior() -> None:
    source = read(LOCAL_EXECUTOR)
    for phrase in [
        "JOB_RISK_SCAN_FIELDS",
        "requested_job_text",
        "Safety-denial fields such as blocked_actions",
        "warning_flags(requested_job_text(job))",
    ]:
        require(phrase in source, "local executor missing bounded requested-field scan behavior: " + phrase)
    module = load_local_executor()
    job = module.load_json(FIRST_JOB)
    base_errors = module.validate_job(job)
    forbidden_from_blocked_actions = [
        "flagged_adb",
        "flagged_install_package",
        "flagged_download_model",
        "flagged_network",
        "flagged_ssh",
        "flagged_startup",
        "flagged_ollama",
    ]
    for flag in forbidden_from_blocked_actions:
        require(flag not in base_errors, "validator must not reject safety-denial blocked_actions text: " + flag)
    unsafe_job = dict(job)
    unsafe_job["instructions"] = "execute this command"
    unsafe_errors = module.validate_job(unsafe_job)
    require("flagged_execute_this_command" in unsafe_errors, "validator must still reject forbidden requested instructions")


def check_adb_verifier_and_report() -> None:
    adb_verifier = read(ADB_VERIFIER)
    for phrase in [
        "--prepare-one-line-termux-finish",
        "--push-finish-runner",
        "--finish-alpha-worker",
        "--i-approve-finish-alpha-worker",
    ]:
        require(phrase in adb_verifier, "ADB setup verifier missing finish phrase: " + phrase)
    require("tools\\verify_android_worker_alpha_finish_setup.py" in read(CODEX_VERIFY), "codex verifier script missing finish setup verifier")
    require(REPORT.exists(), "finish setup report missing")
    report = read(REPORT)
    for phrase in [
        "Engel Android Worker Alpha Finish Setup V1",
        "files changed",
        "modes added",
        "whether finish runner was pushed",
        "whether finish command was attempted",
        "whether worker actually ran",
        "whether real returned files were pulled",
        "exact result count",
        "no fake results were created",
        "no trusted-memory write occurred",
        "no patch apply occurred",
        "verifier results",
        "packaging skipped",
    ]:
        require(phrase.lower() in report.lower(), "finish setup report missing: " + phrase)


def main() -> int:
    checks = [
        ("files", check_files),
        ("finish_runner_static", check_finish_runner_static),
        ("helper_modes", check_helper_modes),
        ("helper_runtime_non_mutating_modes", check_helper_runtime_non_mutating_modes),
        ("worker_validation_behavior", check_worker_validation_behavior),
        ("adb_verifier_and_report", check_adb_verifier_and_report),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(f"{name}: {exc}")
            print("FAIL " + name + ": " + str(exc))
        except Exception as exc:
            failures.append(f"{name}: unexpected error: {exc}")
            print("FAIL " + name + ": unexpected error: " + str(exc))
    if failures:
        print("\nAndroid Worker Alpha finish setup verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nAndroid Worker Alpha finish setup verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
