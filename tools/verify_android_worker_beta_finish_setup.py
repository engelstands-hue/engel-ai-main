from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools" / "setup_android_worker_beta_adb.py"
FINISH_RUNNER = ROOT / "remote_workers" / "android_worker_beta" / "finish_beta_job.py"
LOCAL_EXECUTOR = ROOT / "remote_workers" / "android_worker_beta" / "remote_worker_local_executor.py"
FIRST_JOB = ROOT / "remote_workers" / "android_worker_beta" / "jobs" / "20260519T120000Z_android_worker_beta_draft_candidate_json_extract_beta_package_fields.json"
README = ROOT / "remote_workers" / "android_worker_beta" / "README_PHONE_BUTTON_SETUP.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_ANDROID_WORKER_BETA_FINISH_SETUP_V1.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
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


def load_module(name: str, path: Path):
    worker_root = ROOT / "remote_workers" / "android_worker_beta"
    if str(worker_root) not in sys.path:
        sys.path.insert(0, str(worker_root))
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "could not load module: " + str(path.relative_to(ROOT)))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [HELPER, FINISH_RUNNER, LOCAL_EXECUTOR, FIRST_JOB, README, REPORT, COMMANDS, CODEX_VERIFY]:
        require(path.exists(), "required file missing: " + str(path.relative_to(ROOT)))


def check_finish_runner_static() -> None:
    source = read(FINISH_RUNNER)
    tree = ast.parse(source)
    for phrase in [
        "validate_finish_job",
        "assigned_worker_id_must_be_android_worker_beta",
        "job_type_must_be_draft_candidate_json",
        "real_job_must_be_true",
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
        require(phrase in source, "finish runner missing required phrase: " + phrase)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "finish runner imports forbidden package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "finish runner imports forbidden package: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                require(func.id not in {"eval", "exec", "__import__"}, "finish runner uses forbidden dynamic call: " + func.id)
            elif isinstance(func, ast.Attribute):
                require(func.attr not in {"system", "popen", "Popen"}, "finish runner contains shell execution call: " + func.attr)
        elif isinstance(node, ast.While):
            raise CheckFailure("finish runner must not contain a while loop")
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


def check_beta_executor_validation() -> None:
    source = read(LOCAL_EXECUTOR)
    for phrase in [
        "JOB_RISK_SCAN_FIELDS",
        "requested_job_text",
        "strip_denial_sentences",
        "Safety-denial fields such as blocked_actions",
        "warning_flags(requested_job_text(job))",
    ]:
        require(phrase in source, "local executor missing scoped risk-scan behavior: " + phrase)
    module = load_module("beta_remote_worker_local_executor", LOCAL_EXECUTOR)
    job = module.load_json(FIRST_JOB)
    errors = module.validate_job(job)
    require(errors == [], "beta real job should validate after ignoring denial text; got: " + repr(errors))
    unsafe_job = dict(job)
    unsafe_job["instructions"] = "execute this command"
    unsafe_errors = module.validate_job(unsafe_job)
    require("flagged_execute_this_command" in unsafe_errors, "unsafe requested instructions must still be rejected")


def check_finish_validation_runtime() -> None:
    sys.modules.pop("remote_worker_local_executor", None)
    load_module("remote_worker_local_executor", LOCAL_EXECUTOR)
    finish = load_module("finish_beta_job", FINISH_RUNNER)
    job, problems = finish.validate_finish_job(finish.JOB_PATH)
    require(job.get("assigned_worker_id") == "android_worker_beta", "finish validation returned wrong worker")
    require(problems == [], "finish validation should pass without running job; got: " + repr(problems))


def check_helper_prepare_mode() -> None:
    source = read(HELPER)
    for phrase in [
        "--prepare-one-line-termux-finish-beta",
        "one_line_termux_finish_beta_command",
        "prepare_one_line_termux_finish_beta",
        "TERMUX_APP_SCOPED_ROOT",
        "TERMUX_APP_SCOPED_SHELL_ROOT",
        "finish_beta_job.py",
        "No ADB command is executed by this prepare mode.",
    ]:
        require(phrase in source, "beta ADB helper missing phrase: " + phrase)
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
        require(snippet not in source, "beta ADB helper contains forbidden snippet: " + snippet)

    completed = subprocess.run(
        [sys.executable, str(HELPER), "--prepare-one-line-termux-finish-beta"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    require(completed.returncode == 0, "prepare-one-line mode exited " + str(completed.returncode))
    output = completed.stdout
    for phrase in [
        "review only - nothing is executed",
        "/sdcard/Android/data/com.termux/files/EngelRemoteWorker/android_worker_beta",
        "cd ~/storage/external-1/EngelRemoteWorker/android_worker_beta && python finish_beta_job.py",
        "pull /sdcard/Android/data/com.termux/files/EngelRemoteWorker/android_worker_beta/status",
        "No ADB command is executed by this prepare mode.",
        "No install, package download, model runtime, provider/network, trusted-memory write, or patch apply is enabled.",
    ]:
        require(phrase in output, "prepare-one-line output missing: " + phrase)

    module = load_module("setup_android_worker_beta_adb", HELPER)
    commands = [module.command_text(parts) for _label, parts in module.app_scoped_review_command_groups("adb")]
    require(not any("finish_beta_job.py &&" in command for command in commands), "app-scoped push commands must not run finish runner")
    require(not any("run_assigned_job.py" in command for command in commands), "app-scoped push commands must not run worker job")


def check_docs_and_report() -> None:
    readme = read(README)
    for phrase in [
        "Scoped Storage Finish Bypass",
        "python tools\\setup_android_worker_beta_adb.py --prepare-one-line-termux-finish-beta",
        "/sdcard/Android/data/com.termux/files/EngelRemoteWorker/android_worker_beta",
        "cd ~/storage/external-1/EngelRemoteWorker/android_worker_beta && python finish_beta_job.py",
        "does not install packages, start a service, load a model, call the network, write trusted memory, or apply patches",
    ]:
        require(phrase in readme, "README missing: " + phrase)
    commands = read(COMMANDS)
    for phrase in [
        "android worker beta adb prepare one-line termux finish",
        "tools\\setup_android_worker_beta_adb.py --prepare-one-line-termux-finish-beta",
        "/sdcard/Android/data/com.termux/files/EngelRemoteWorker/android_worker_beta",
        "~/storage/external-1/EngelRemoteWorker/android_worker_beta",
    ]:
        require(phrase in commands, "command docs missing: " + phrase)
    require("tools\\verify_android_worker_beta_finish_setup.py" in read(CODEX_VERIFY), "codex verifier script missing beta finish verifier")
    report = read(REPORT)
    for phrase in [
        "Engel Android Worker Beta Finish Setup V1",
        "Android scoped-storage + SELinux",
        "MANAGE_EXTERNAL_STORAGE",
        "/sdcard/Android/data/com.termux/files/EngelRemoteWorker/android_worker_beta",
        "--prepare-one-line-termux-finish-beta",
        "finish_beta_job.py",
        "no fake results",
        "no trusted-memory write",
        "no patch apply",
        "packaging skipped",
    ]:
        require(phrase.lower() in report.lower(), "report missing: " + phrase)


def main() -> int:
    checks = [
        ("files", check_files),
        ("finish_runner_static", check_finish_runner_static),
        ("beta_executor_validation", check_beta_executor_validation),
        ("finish_validation_runtime", check_finish_validation_runtime),
        ("helper_prepare_mode", check_helper_prepare_mode),
        ("docs_and_report", check_docs_and_report),
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
        print("\nAndroid Worker Beta finish setup verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nAndroid Worker Beta finish setup verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
