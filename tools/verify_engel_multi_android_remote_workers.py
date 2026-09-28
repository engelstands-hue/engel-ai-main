from __future__ import annotations

import ast
import importlib.util
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_JSON = ROOT / "memory" / "ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.json"
PROTOCOL_MD = ROOT / "memory" / "ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.md"
REGISTRY_JSON = ROOT / "memory" / "ENGEL_ANDROID_REMOTE_WORKER_REGISTRY_V1.json"
PROTOCOL_MODULE = ROOT / "engel_android_remote_worker_protocol.py"
STATUS_MODULE = ROOT / "engel_multi_android_remote_workers.py"
SCAFFOLD_MODULE = ROOT / "engel_remote_worker_app_scaffold.py"
SYSTEM_INTEGRATION = ROOT / "engel_system_integration_status.py"
CORE_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
CORE_MD = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.md"

WORKERS = {
    "android_worker_alpha": {
        "name": "Android Worker Alpha",
        "role": "research note worker",
        "allowed": [
            "summarize_text",
            "draft_research_note",
            "classify_file",
            "return_status",
            "return_logs",
            "return_receipt",
        ],
    },
    "android_worker_beta": {
        "name": "Android Worker Beta",
        "role": "candidate JSON worker",
        "allowed": [
            "draft_candidate_json",
            "format_report_draft",
            "classify_file",
            "return_status",
            "return_logs",
            "return_receipt",
        ],
    },
    "android_worker_gamma": {
        "name": "Android Worker Gamma",
        "role": "small local compute / report formatting worker",
        "allowed": [
            "compute_small_local_task",
            "format_report_draft",
            "summarize_text",
            "return_status",
            "return_logs",
            "return_receipt",
        ],
    },
}

REQUIRED_PACKAGE_FILES = [
    "config/worker_identity.json",
    "config/worker_capabilities.json",
    "config/worker_autonomy_policy.json",
    "jobs/.gitkeep",
    "inbox/.gitkeep",
    "outbox/.gitkeep",
    "logs/.gitkeep",
    "receipts/.gitkeep",
    "status/.gitkeep",
    "README_ANDROID_SETUP.md",
    "remote_worker_status.py",
    "remote_worker_job_view.py",
    "remote_worker_runner.py",
    "remote_worker_local_executor.py",
    "run_worker_status.py",
    "run_assigned_job.py",
]

REQUIRED_SAFETY_STATES = [
    "protocol_defined",
    "multi_worker_registry_defined",
    "real_data_only",
    "manual_setup_required",
    "manual_transfer_mode_only",
    "on_device_autonomy_allowed",
    "autonomy_scope_assigned_job_sandbox_only",
    "no_phone_connection",
    "no_android_runtime_execution_from_engel",
    "communication_queen_routing_required",
    "remote_worker_not_queen",
    "candidate_outputs_only",
    "no_trusted_memory_write",
    "no_patch_apply",
    "no_provider_network",
    "no_model_runtime",
    "no_startup_autorun",
    "no_fake_worker_progress",
]

REQUIRED_WORKER_FLAGS = {
    "queen_authority": False,
    "routing_layer": "communication_queen_only",
    "trusted_memory_write": False,
    "source_mutation": False,
    "route_mutation": False,
    "patch_apply": False,
    "provider_network": False,
    "startup_autorun": False,
    "model_runtime": False,
    # hermes_allowed lifted from "must be False" per ENGEL_HERMES_POLICY_CHANGE_V1
    # (Hermes approved for local install + human-driven testing on this
    # workstation). All other safety flags remain locked-false.
    "hermes_allowed": True,
    "controls_engel": False,
    "candidate_outputs_only": True,
    "on_device_autonomy": True,
    "autonomy_scope": "assigned_job_sandbox_only",
    "can_self_assign_jobs": False,
    "can_create_jobs": False,
    "can_route_jobs": False,
    "can_control_engel": False,
}

JOB_FIELDS = [
    "job_id",
    "job_title",
    "job_type",
    "job_template",
    "real_job",
    "created_at",
    "assigned_worker_id",
    "created_by",
    "routed_by",
    "priority",
    "status",
    "input_files",
    "instructions",
    "allowed_actions",
    "blocked_actions",
    "expected_outputs",
    "receipt_required",
    "log_required",
    "max_runtime_hint",
    "max_input_size",
    "max_output_size",
    "offline_only",
    "manual_transfer_required",
    "on_device_autonomy_allowed",
    "autonomy_scope",
    "trusted_memory_write",
    "source_mutation",
    "route_mutation",
    "patch_apply",
    "provider_network",
    "model_runtime",
    "approval_required_for_any_write",
]

STATUS_FIELDS = [
    "worker_id",
    "worker_name",
    "device_label",
    "job_id",
    "job_title",
    "job_status",
    "progress_percent",
    "status_message",
    "current_step",
    "started_at",
    "updated_at",
    "completed_at",
    "blocked_reason",
    "output_ready",
    "receipt_path",
    "log_path",
    "safety_flags",
    "manual_transfer_mode",
    "on_device_autonomy",
    "autonomy_scope",
    "real_status",
    "source",
]

RESULT_FIELDS = [
    "worker_id",
    "worker_name",
    "job_id",
    "job_status",
    "summary",
    "output_files",
    "candidate_outputs",
    "log_files",
    "receipt_files",
    "warnings",
    "safety_flags",
    "requires_human_review",
    "trusted_memory_write",
    "source_mutation",
    "route_mutation",
    "patch_apply",
    "provider_network",
    "model_runtime",
    "on_device_autonomy_used",
    "autonomy_scope",
    "real_result",
    "source",
]

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "openai",
    "subprocess",
    "threading",
    "multiprocessing",
    "shutil",
    "glob",
}

ENGEL_READ_ONLY_MODULES = [PROTOCOL_MODULE, STATUS_MODULE, SCAFFOLD_MODULE]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict[str, object]:
    data = json.loads(read(path))
    require(isinstance(data, dict), "JSON root is not object: " + str(path.relative_to(ROOT)))
    return data


def load_module(path: Path, name: str):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "could not load module: " + path.name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def ast_check_imports(path: Path) -> ast.AST:
    source = read(path)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, f"{path.name} imports forbidden package {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, f"{path.name} imports forbidden package {node.module}")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                require(func.id not in {"eval", "exec", "__import__"}, f"{path.name} uses forbidden dynamic call {func.id}")
    return tree


def check_files_exist() -> None:
    for path in [PROTOCOL_JSON, PROTOCOL_MD, REGISTRY_JSON, PROTOCOL_MODULE, STATUS_MODULE, SCAFFOLD_MODULE, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path.relative_to(ROOT)))
    for worker_id in WORKERS:
        package = ROOT / "remote_workers" / worker_id
        require(package.exists() and package.is_dir(), "worker package missing: " + worker_id)
        for relative in REQUIRED_PACKAGE_FILES:
            require((package / relative).exists(), f"{worker_id} missing {relative}")


def check_protocol_contract() -> None:
    data = load_json(PROTOCOL_JSON)
    require(data.get("protocol_name") == "Engel Multi Android Remote Workers Protocol V1", "protocol name mismatch")
    require(data.get("routing_layer") == "communication_queen_only", "routing layer mismatch")
    require(data.get("connection_mode") == "manual_transfer_v1", "connection mode mismatch")
    require(data.get("real_data_only") is True, "real_data_only must be true")
    require(data.get("fake_live_data_allowed") is False, "fake_live_data_allowed must be false")
    require(data.get("phone_connection_enabled") is False, "phone connection must be disabled")
    require(data.get("android_runtime_execution_from_engel") is False, "Android runtime execution from Engel must be disabled")
    for state in REQUIRED_SAFETY_STATES:
        require(state in data.get("status_labels", []), "missing status label: " + state)
    for field in JOB_FIELDS:
        require(field in data.get("job_packet_schema", {}).get("required_fields", []), "missing job packet field: " + field)
    for field in STATUS_FIELDS:
        require(field in data.get("status_packet_schema", {}).get("required_fields", []), "missing status packet field: " + field)
    for field in RESULT_FIELDS:
        require(field in data.get("result_packet_schema", {}).get("required_fields", []), "missing result packet field: " + field)
    template = data.get("template_rule", {})
    require(template.get("job_template") is True, "template rule must mark job_template true")
    require(template.get("real_job") is False, "template rule must mark real_job false")
    require(template.get("status") == "template_only", "template rule must mark template_only")
    require(template.get("excluded_from_real_status_counts") is True, "templates must be excluded from real counts")
    require(template.get("must_not_count_as_completed_work") is True, "templates must not count as completed work")
    boundary = data.get("safety_boundary", {})
    for key in [
        "manual_transfer_mode_only",
        "real_data_only",
        "no_fake_live_worker_data",
        "no_fake_jobs",
        "no_fake_progress",
        "no_fake_results",
        "no_phone_connection",
        "no_android_runtime_execution_from_engel",
        "no_adb_automation",
        "no_ssh",
        "no_socket_server",
        "no_cloud_sync",
        "no_provider_network_browser",
        "no_model_runtime",
        "no_hermes",
        "no_ollama",
        "no_llama_cpp",
        "no_trusted_memory_write",
        "no_patch_apply",
        "no_source_mutation",
        "no_route_mutation",
        "no_background_worker",
        "no_startup_autorun",
    ]:
        require(boundary.get(key) is True, "protocol boundary missing/false: " + key)


def check_registry() -> None:
    data = load_json(REGISTRY_JSON)
    require(data.get("routing_layer") == "communication_queen_only", "registry routing layer mismatch")
    require(data.get("connection_mode") == "manual_transfer_v1", "registry connection mode mismatch")
    require(data.get("real_data_only") is True, "registry real_data_only must be true")
    require(data.get("fake_live_data_allowed") is False, "registry fake live data must be false")
    require(data.get("active_jobs") == [], "registry must not seed active jobs")
    workers = data.get("workers", [])
    require(isinstance(workers, list), "registry workers must be a list")
    android_workers = [entry for entry in workers if isinstance(entry, dict) and entry.get("worker_id") in WORKERS]
    require(len(android_workers) == 3, "registry must list the three Android workers")
    ids = {entry.get("worker_id") for entry in android_workers}
    require(set(WORKERS) == ids, "registry worker ids mismatch")
    for entry in android_workers:
        require(entry.get("current_job_id") == "", "registry must not seed current job id")
        require(entry.get("last_status_path") == "", "registry must not seed returned status")
        require(entry.get("last_result_path") == "", "registry must not seed returned result")


def check_worker_package(worker_id: str, expected: dict[str, object]) -> None:
    package = ROOT / "remote_workers" / worker_id
    identity = load_json(package / "config" / "worker_identity.json")
    capabilities = load_json(package / "config" / "worker_capabilities.json")
    policy = load_json(package / "config" / "worker_autonomy_policy.json")
    require(identity.get("worker_id") == worker_id, "identity worker id mismatch")
    require(identity.get("worker_name") == expected["name"], "worker name mismatch")
    require(identity.get("role") == expected["role"], "worker role mismatch")
    for key, value in REQUIRED_WORKER_FLAGS.items():
        require(identity.get(key) == value, f"{worker_id} flag mismatch: {key}")
    require(set(expected["allowed"]).issubset(set(identity.get("allowed_task_types") or [])), "identity missing baseline allowed jobs")
    require(set(expected["allowed"]).issubset(set(capabilities.get("allowed_jobs") or [])), "capabilities missing baseline allowed jobs")
    blocked_tasks = capabilities.get("blocked_task_types", [])
    # hermes_runtime removed from required-blocked list per
    # ENGEL_HERMES_POLICY_CHANGE_V1. Ollama / llama_cpp / engel_control /
    # worker_routing all stay blocked for worker autonomy boundary.
    for blocked in ["ollama_runtime", "llama_cpp_runtime", "engel_control", "worker_routing"]:
        require(any(blocked in str(item) for item in blocked_tasks), f"{worker_id} missing blocked task {blocked}")
    for field in [
        "on_device_autonomy",
        "requires_assigned_job_packet",
        "requires_worker_id_match",
        "max_runtime_hint_required",
        "requires_receipt",
        "requires_log",
        "candidate_outputs_only",
        "no_engel_control",
        "no_network",
        "no_model_runtime",
        "no_package_install",
        "no_startup_autorun",
    ]:
        require(policy.get(field) is True, f"{worker_id} policy field must be true: {field}")
    require(policy.get("autonomy_scope") == "assigned_job_sandbox_only", "policy autonomy scope mismatch")
    for blocked in [
        "execute arbitrary shell from job packet",
        "install packages",
        "download files",
        "download models",
        "start network server",
        "expose SSH",
        "run background daemon",
        "schedule boot startup",
        "delete receipts",
        "delete logs",
        "mark output trusted",
        "mark memory promoted",
        "mark patch applied",
        "impersonate approval",
    ]:
        require(blocked in policy.get("blocked_local_actions", []), f"{worker_id} policy missing blocked action: {blocked}")
    readme = read(package / "README_ANDROID_SETUP.md")
    for needle in [
        "Remote Worker",
        "not a Queen",
        "Communication Queen assigns and routes jobs",
        "Manual transfer mode only",
        "No live connection",
        "No startup autorun",
        "Hermes remains rejected / do not install",
        "No Ollama",
        "No llama.cpp",
        "No model runtime",
        "No provider/network/browser behavior",
        "Worker outputs are candidate-only",
        "Returned results require human review",
        "Install Termux from F-Droid manually",
        "Do not enable boot/startup automation",
    ]:
        require(needle in readme, f"{worker_id} README missing: {needle}")


def check_worker_scripts(worker_id: str) -> None:
    package = ROOT / "remote_workers" / worker_id
    runner = package / "remote_worker_runner.py"
    executor = package / "remote_worker_local_executor.py"
    status = package / "remote_worker_status.py"
    job_view = package / "remote_worker_job_view.py"
    for path in [runner, executor, status, job_view, package / "run_worker_status.py", package / "run_assigned_job.py"]:
        ast_check_imports(path)
    runner_text = read(runner)
    executor_text = read(executor)
    combined = runner_text + "\n" + executor_text
    for needle in [
        "job_template",
        "real_job",
        "assigned_worker_id does not match this worker",
        "job_type is not allowed for this worker",
        "communication_queen",
        "trusted_memory_write",
        "source_mutation",
        "route_mutation",
        "patch_apply",
        "provider_network",
        "model_runtime",
        "summarize_text",
        "classify_file",
        "draft_research_note",
        "draft_candidate_json",
        "format_report_draft",
        "compute_small_local_task",
        "candidate_outputs_only",
        "requires_human_review",
    ]:
        require(needle in combined, f"{worker_id} runner/executor missing: {needle}")
    for forbidden in ["subprocess.", "os.system", "Popen", "requests.", "urllib.", "socket.", "webbrowser.", "openai."]:
        require(forbidden not in combined, f"{worker_id} runner contains forbidden active behavior: {forbidden}")
    for folder in ["jobs", "inbox", "outbox", "logs", "receipts", "status"]:
        require((package / folder / ".gitkeep").exists(), f"{worker_id} missing .gitkeep for {folder}")
    require("No real returned status packets found" in read(status), "status UI must show honest empty status")
    require("Template-only jobs ignored" in read(job_view), "job view must ignore templates")


def check_engel_status_modules() -> None:
    for path in ENGEL_READ_ONLY_MODULES:
        tree = ast_check_imports(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute):
                    require(func.attr not in {"write_text", "write_bytes", "unlink", "remove", "rename", "replace", "mkdir", "rmdir"}, f"{path.name} should be read-only but calls {func.attr}")
                elif isinstance(func, ast.Name):
                    require(func.id not in {"open"}, f"{path.name} should not use open")
            elif isinstance(node, ast.While):
                raise CheckFailure(path.name + " contains while loop")
    status_module = load_module(STATUS_MODULE, "engel_multi_android_remote_workers")
    out = io.StringIO()
    err = io.StringIO()
    require(status_module.main(["--status"], stdout=out, stderr=err) == 0, "multi-worker --status failed")
    status_text = out.getvalue()
    for needle in [
        "Engel Multi Android Remote Workers Protocol V1",
        "Real data only: True",
        "Fake live data allowed: False",
        "Current selected job",
        "Remote Workers",
        "Engel Communication Router routing is required.",
        "not Queens",
        "No phone connection",
    ]:
        require(needle in status_text, "status output missing: " + needle)
    require(
        "Workers configured / no assigned jobs." in status_text
        or "Job packet prepared / awaiting manual worker status." in status_text
        or "Returned candidate output requires human review." in status_text
        or "Result not returned yet." in status_text,
        "status output must show honest no-job, prepared-job, waiting, or returned state",
    )
    out = io.StringIO()
    require(status_module.main(["--json"], stdout=out, stderr=err) == 0, "multi-worker --json failed")
    payload = json.loads(out.getvalue())
    require(payload.get("worker_package_count") == 3, "status JSON must see three packages")
    require(isinstance(payload.get("real_job_count"), int) and payload.get("real_job_count") >= 0, "status JSON real job count invalid")
    require(isinstance(payload.get("returned_status_count"), int) and payload.get("returned_status_count") >= 0, "status JSON returned status count invalid")
    require(isinstance(payload.get("returned_result_count"), int) and payload.get("returned_result_count") >= 0, "status JSON returned result count invalid")
    require(
        payload.get("overall_state") in {
            "Workers configured / no assigned jobs.",
            "Job packet prepared / awaiting manual worker status.",
            "Result not returned yet.",
            "Returned candidate output requires human review.",
        },
        "overall empty/prepared/waiting/returned state mismatch",
    )
    require(payload.get("fake_live_data_allowed") is False, "status JSON fake live data must be false")
    scaffold = load_module(SCAFFOLD_MODULE, "engel_remote_worker_app_scaffold")
    manifest = scaffold.package_manifest()
    require(manifest.get("package_count") == 3, "scaffold manifest package count mismatch")
    for package in manifest.get("packages", []):
        require(package.get("ready_for_manual_transfer") is True, "package should be ready for manual transfer")


def check_markdown_and_docs() -> None:
    text = read(PROTOCOL_MD)
    for needle in [
        "replaces the old single Android Remote Worker scaffold",
        "Communication Queen assigns and routes jobs",
        "Android devices are not Queens",
        "No fake live workers",
        "manual transfer",
        "job_template: true",
        "real_job: false",
        "status: template_only",
        "Status Packet Schema",
        "Result Packet Schema",
        "Android-Side Worker Status UI Scaffold",
        "Engel-Side Multi-Worker Status Surface",
        "No LLM inference is enabled",
        "Hermes remains rejected / do not install",
        "Do not install Ollama",
        "Do not install llama.cpp",
    ]:
        require(needle in text, "protocol Markdown missing: " + needle)


def check_system_integration_and_core_continuity() -> None:
    system_text = read(SYSTEM_INTEGRATION)
    for needle in [
        "multi_android_remote_workers_protocol",
        "Engel Multi Android Remote Workers Protocol V1",
        "engel_multi_android_remote_workers.py",
        "memory\\\\ENGEL_ANDROID_REMOTE_WORKER_REGISTRY_V1.json",
        "tools\\\\verify_engel_multi_android_remote_workers.py",
        "manual_transfer_v1",
        "real data only",
        "prepared / awaiting manual worker status",
        "Communication Queen",
        "Remote Workers are not Queens",
    ]:
        require(needle in system_text, "System Integration missing: " + needle)
    core = load_json(CORE_JSON)
    md = read(CORE_MD)
    node = core.get("engel_multi_android_remote_workers_protocol_v1")
    require(isinstance(node, dict), "Core Continuity node missing")
    require(node.get("type") == "multi_android_remote_workers_protocol", "Core Continuity node type mismatch")
    for state in REQUIRED_SAFETY_STATES:
        require(state in node.get("status", []), "Core Continuity node missing status: " + state)
        require(state in md, "Core Continuity Markdown missing status: " + state)
    for safety_key in [
        "multi_android_remote_workers_phone_connection_enabled_by_map",
        "multi_android_remote_workers_android_runtime_execution_enabled_by_map",
        "multi_android_remote_workers_adb_automation_enabled_by_map",
        "multi_android_remote_workers_ssh_enabled_by_map",
        "multi_android_remote_workers_live_connection_server_enabled_by_map",
        "multi_android_remote_workers_cloud_sync_enabled_by_map",
        "multi_android_remote_workers_provider_network_browser_enabled_by_map",
        "multi_android_remote_workers_model_runtime_enabled_by_map",
        "multi_android_remote_workers_trusted_memory_write_enabled_by_map",
        "multi_android_remote_workers_patch_apply_enabled_by_map",
        "multi_android_remote_workers_source_mutation_enabled_by_map",
        "multi_android_remote_workers_route_mutation_enabled_by_map",
        "multi_android_remote_workers_background_worker_enabled_by_map",
        "multi_android_remote_workers_startup_autorun_enabled_by_map",
        "multi_android_remote_workers_fake_live_data_enabled_by_map",
        "multi_android_remote_workers_fake_progress_enabled_by_map",
        "multi_android_remote_workers_fake_results_enabled_by_map",
    ]:
        require(core.get("safety", {}).get(safety_key) is False, "Core safety flag should be false: " + safety_key)


def check_report() -> None:
    text = read(REPORT).lower()
    for needle in [
        "files changed",
        "real worker package folders created",
        "Alpha/Beta/Gamma worker roles",
        "on-device autonomy policy",
        "assigned-job sandbox boundary",
        "real-data-only rule",
        "protocol summary",
        "worker registry summary",
        "Communication Queen routing behavior",
        "job packet schema",
        "status packet schema",
        "result packet schema",
        "Android-side worker app/status UI scaffold",
        "Engel-side multi-worker UI/status surface",
        "manual Android setup instructions",
        "no fake live worker data was created",
        "no fake jobs/progress/results were created",
        "no phone was connected",
        "no Android runtime was executed from Engel",
        "no network/provider/browser behavior was added",
        "no model loading/inference/training occurred",
        "no Hermes/Ollama/llama.cpp install path was added",
        "no trusted-memory write occurred",
        "no patch/source/route mutation occurred beyond requested protocol/docs",
        "verifier results",
        "packaging skipped",
        "working tree note",
    ]:
        require(needle.lower() in text, "report missing: " + needle)


def main() -> int:
    checks = [
        ("files_exist", check_files_exist),
        ("protocol_contract", check_protocol_contract),
        ("registry", check_registry),
        ("worker_packages", lambda: [check_worker_package(worker_id, expected) for worker_id, expected in WORKERS.items()]),
        ("worker_scripts", lambda: [check_worker_scripts(worker_id) for worker_id in WORKERS]),
        ("engel_status_modules", check_engel_status_modules),
        ("markdown_and_docs", check_markdown_and_docs),
        ("system_integration_and_core_continuity", check_system_integration_and_core_continuity),
        ("report", check_report),
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
        print("\nEngel Multi Android Remote Workers verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nEngel Multi Android Remote Workers verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
