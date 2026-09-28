from __future__ import annotations

import ast
import importlib.util
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_REMOTE_WORKER_JOB_ASSIGNMENT_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_REMOTE_WORKER_JOB_ASSIGNMENT_CONTRACT_V1.md"
ASSIGNMENT_MODULE = ROOT / "engel_remote_worker_job_assignment.py"
SYSTEM_INTEGRATION = ROOT / "engel_system_integration_status.py"
CORE_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
CORE_MD = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_REMOTE_WORKER_JOB_ASSIGNMENT_V1.md"
REGISTRY_JSON = ROOT / "memory" / "ENGEL_ANDROID_REMOTE_WORKER_REGISTRY_V1.json"

WORKERS = {
    "android_worker_alpha": ["summarize_text", "draft_research_note", "classify_file"],
    "android_worker_beta": ["draft_candidate_json", "format_report_draft", "classify_file"],
    "android_worker_gamma": ["compute_small_local_task", "format_report_draft", "summarize_text"],
}

REQUIRED_STATUS_LABELS = [
    "COMMUNICATION_QUEEN_REMOTE_WORKER_JOB_ASSIGNMENT",
    "ASSIGNMENT_CONTRACT",
    "REAL_JOB_PACKETS_ONLY",
    "REAL_INPUT_FILE_REQUIRED",
    "SAFE_LOCAL_INPUTS_ONLY",
    "MANUAL_TRANSFER_ONLY",
    "COMMUNICATION_QUEEN_ROUTING_REQUIRED",
    "REMOTE_WORKER_NOT_QUEEN",
    "ANDROID_REMOTE_WORKERS_NOT_QUEENS",
    "PREPARED_FOR_MANUAL_TRANSFER_ONLY",
    "AWAITING_WORKER_STATUS_UNTIL_RETURNED_PACKET",
    "CANDIDATE_OUTPUTS_ONLY",
    "NO_PHONE_CONNECTION",
    "NO_ANDROID_RUNTIME_EXECUTION_FROM_ENGEL",
    "NO_WORKER_JOB_EXECUTION_FROM_ENGEL",
    "NO_FAKE_RETURNED_STATUS",
    "NO_FAKE_RETURNED_RESULT",
    "NO_FAKE_PROGRESS",
    "NO_COMPLETION_WITHOUT_RETURNED_PACKET",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PATCH_APPLY",
    "NO_PROVIDER_NETWORK_BROWSER",
    "NO_MODEL_RUNTIME",
    "HERMES_REJECTED_DO_NOT_INSTALL",
    "NO_HERMES_OLLAMA_LLAMA_CPP_PATH",
]

REQUIRED_PACKET_FIELDS = [
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
    "requires_human_review",
]

REQUIRED_STATES = [
    "requested",
    "validated",
    "rejected",
    "prepared_for_manual_transfer",
    "awaiting_manual_transfer",
    "awaiting_worker_status",
    "returned_to_engel",
    "blocked",
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
    for path in [CONTRACT_JSON, CONTRACT_MD, ASSIGNMENT_MODULE, REGISTRY_JSON]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path.relative_to(ROOT)))
    for worker_id in WORKERS:
        package = ROOT / "remote_workers" / worker_id
        require((package / "config" / "worker_identity.json").exists(), "worker identity missing: " + worker_id)
        require((package / "config" / "worker_capabilities.json").exists(), "worker capabilities missing: " + worker_id)
        require((package / "jobs").exists(), "worker jobs folder missing: " + worker_id)
        require((package / "inbox").exists(), "worker inbox folder missing: " + worker_id)


def check_contract() -> None:
    data = load_json(CONTRACT_JSON)
    text = read(CONTRACT_MD)
    require(data.get("contract_name") == "Communication Queen Remote Worker Job Assignment V1", "contract name mismatch")
    require(data.get("routing_layer") == "communication_queen_only", "routing layer mismatch")
    require(data.get("connection_mode") == "manual_transfer_v1", "connection mode mismatch")
    require(data.get("real_data_only") is True, "real_data_only must be true")
    require(data.get("fake_live_data_allowed") is False, "fake live data must be false")
    for label in REQUIRED_STATUS_LABELS:
        require(label in data.get("status_labels", []), "contract missing status label: " + label)
        require(label in text, "contract Markdown missing status label: " + label)
    for state in REQUIRED_STATES:
        require(state in data.get("assignment_status_states", []), "contract missing assignment state: " + state)
        require(state in text, "contract Markdown missing assignment state: " + state)
    for field in REQUIRED_PACKET_FIELDS:
        require(field in data.get("job_packet_schema", {}).get("required_fields", []), "contract missing job packet field: " + field)
        require(field in text, "contract Markdown missing job packet field: " + field)
    fixed = data.get("job_packet_schema", {}).get("fixed_values", {})
    for key in ["job_template", "trusted_memory_write", "source_mutation", "route_mutation", "patch_apply", "provider_network", "model_runtime"]:
        require(fixed.get(key) is False, "fixed packet flag must be false: " + key)
    for key in ["real_job", "offline_only", "manual_transfer_required", "on_device_autonomy_allowed", "approval_required_for_any_write", "requires_human_review"]:
        require(fixed.get(key) is True, "fixed packet flag must be true: " + key)
    require(fixed.get("status") == "prepared_for_manual_transfer", "fixed packet status mismatch")
    require(fixed.get("routed_by") == "communication_queen", "fixed routed_by mismatch")
    boundary = data.get("hard_safety_boundaries", {})
    for key in [
        "no_phone_connection",
        "no_android_runtime_execution_from_engel",
        "no_adb",
        "no_ssh",
        "no_live_connection_server",
        "no_cloud_sync",
        "no_worker_job_execution_from_engel",
        "no_fake_returned_status",
        "no_fake_returned_result",
        "no_fake_progress",
        "no_completion_without_returned_packet",
        "no_trusted_memory_write",
        "no_patch_apply",
        "no_source_mutation",
        "no_route_mutation",
        "no_provider_network_browser",
        "no_model_runtime",
        "hermes_rejected_do_not_install",
        "no_ollama",
        "no_llama_cpp",
        "no_background_worker",
        "no_startup_autorun",
    ]:
        require(boundary.get(key) is True, "contract boundary missing/false: " + key)
    for phrase in [
        "Communication Queen assigns",
        "Android Remote Workers are Remote Workers / Mobile Workers, not Queens",
        "Preview and status commands do not write",
        "Hermes remains rejected / do not install on this computer",
    ]:
        require(phrase in text, "contract Markdown missing: " + phrase)


def check_module_behavior() -> None:
    ast_check_imports(ASSIGNMENT_MODULE)
    module = load_module(ASSIGNMENT_MODULE, "engel_remote_worker_job_assignment")
    for worker_id, jobs in WORKERS.items():
        identity = module.validate_worker(worker_id)
        require(identity.get("queen_authority") is False, "worker has Queen authority: " + worker_id)
        require(
            identity.get("routing_layer") in ("engel_communication_router_only", "communication_queen_only"),
            "worker routing mismatch: " + worker_id,
        )
        for job in jobs:
            module.validate_job_type(worker_id, job)
    try:
        module.validate_job_type("android_worker_alpha", "draft_candidate_json")
    except Exception:
        pass
    else:
        raise CheckFailure("Alpha accepted a Beta-only job type")
    try:
        module.resolve_input_path("https://example.invalid/input.txt")
    except Exception:
        pass
    else:
        raise CheckFailure("URL input path was accepted")
    try:
        module.resolve_input_path("memory\\DOES_NOT_EXIST_FOR_ASSIGNMENT.txt")
    except Exception:
        pass
    else:
        raise CheckFailure("missing input file was accepted")
    sample = ROOT / "memory" / "ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.md"
    require(sample.exists(), "sample preview input missing")
    packet = module.preview_assignment(
        "android_worker_alpha",
        "summarize_text",
        str(sample),
        "Verifier Preview Assignment",
        "Summarize the assigned local input file and return candidate-only output.",
    )
    for field in REQUIRED_PACKET_FIELDS:
        require(field in packet, "preview packet missing field: " + field)
    require(packet.get("job_template") is False, "preview packet must not be template")
    require(packet.get("real_job") is True, "preview packet must be real_job true")
    require(packet.get("status") == "prepared_for_manual_transfer", "preview packet status mismatch")
    require(packet.get("assigned_worker_id") == "android_worker_alpha", "preview worker mismatch")
    require(packet.get("routed_by") == "engel_communication_router", "preview routing mismatch")
    require(packet.get("manual_transfer_required") is True, "preview manual transfer required")
    require(packet.get("trusted_memory_write") is False, "preview trusted memory flag must be false")
    require(packet.get("patch_apply") is False, "preview patch flag must be false")
    require(packet.get("provider_network") is False, "preview provider/network flag must be false")
    require(packet.get("model_runtime") is False, "preview model runtime flag must be false")
    safety = packet.get("assignment_safety", {})
    for key in ["no_phone_connection", "no_android_runtime_execution_from_engel", "no_worker_job_execution_from_engel", "no_fake_returned_status", "no_fake_returned_result", "no_fake_progress", "no_completion_without_returned_packet"]:
        require(safety.get(key) is True, "preview safety flag missing: " + key)
    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--status"], stdout=out, stderr=err) == 0, "--status failed")
    status_text = out.getvalue()
    for phrase in [
        "Engel Communication Router Remote Worker Job Assignment V1",
        "Routing layer: engel_communication_router_only",
        "Connection mode: manual_transfer_v1",
        "Prepared job packets:",
        "does not connect to phones",
        "Hermes remains rejected / do not install on this computer",
    ]:
        require(phrase in status_text, "status output missing: " + phrase)
    out = io.StringIO()
    require(module.main(["--preview", "--worker-id", "android_worker_beta", "--job-type", "classify_file", "--input-file", str(sample), "--title", "Verifier Preview"], stdout=out, stderr=err) == 0, "--preview failed")
    parsed = json.loads(out.getvalue())
    require(parsed.get("status") == "prepared_for_manual_transfer", "CLI preview status mismatch")


def check_no_active_forbidden_behavior() -> None:
    source = read(ASSIGNMENT_MODULE)
    forbidden_snippets = [
        "subprocess.",
        "os.system",
        "Popen",
        "requests.",
        "urllib.",
        "webbrowser.",
        "openai.",
        "threading.",
        "multiprocessing.",
        "mark_completed(",
        "returned_result_path.write",
        "returned_status_path.write",
    ]
    for snippet in forbidden_snippets:
        require(snippet not in source, "assignment module contains forbidden active snippet: " + snippet)
    require("status\": \"completed\"" not in source, "assignment module must not create completed status packets")
    require("real_result\": true" not in source, "assignment module must not create returned result packets")
    require("real_status\": true" not in source, "assignment module must not create returned status packets")


def check_system_integration_and_core() -> None:
    system_text = read(SYSTEM_INTEGRATION)
    for phrase in [
        "remote_worker_job_assignment",
        "Communication Queen Remote Worker Job Assignment V1",
        "engel_remote_worker_job_assignment.py",
        "memory\\\\ENGEL_REMOTE_WORKER_JOB_ASSIGNMENT_CONTRACT_V1.json",
        "tools\\\\verify_engel_remote_worker_job_assignment.py",
        "prepared_for_manual_transfer",
        "no phone connection",
        "no fake returned status/result/progress",
    ]:
        require(phrase in system_text, "System Integration missing: " + phrase)
    core = load_json(CORE_JSON)
    md = read(CORE_MD)
    node = core.get("communication_queen_remote_worker_job_assignment_v1")
    require(isinstance(node, dict), "Core Continuity assignment node missing")
    require(node.get("type") == "remote_worker_job_assignment", "Core Continuity assignment node type mismatch")
    for label in REQUIRED_STATUS_LABELS:
        require(label in node.get("status", []), "Core Continuity node missing status: " + label)
        require(label in md, "Core Continuity Markdown missing status: " + label)
    for path in [
        r"memory\ENGEL_REMOTE_WORKER_JOB_ASSIGNMENT_CONTRACT_V1.json",
        r"memory\ENGEL_REMOTE_WORKER_JOB_ASSIGNMENT_CONTRACT_V1.md",
        "engel_remote_worker_job_assignment.py",
        r"tools\verify_engel_remote_worker_job_assignment.py",
        r"reports\codex_bridge\ENGEL_REMOTE_WORKER_JOB_ASSIGNMENT_V1.md",
    ]:
        require(path in node.get("files", []), "Core Continuity node missing file: " + path)
    for key in [
        "remote_worker_job_assignment_phone_connection_enabled_by_map",
        "remote_worker_job_assignment_android_runtime_execution_enabled_by_map",
        "remote_worker_job_assignment_adb_enabled_by_map",
        "remote_worker_job_assignment_ssh_enabled_by_map",
        "remote_worker_job_assignment_live_connection_server_enabled_by_map",
        "remote_worker_job_assignment_cloud_sync_enabled_by_map",
        "remote_worker_job_assignment_worker_job_execution_from_engel_enabled_by_map",
        "remote_worker_job_assignment_fake_returned_status_enabled_by_map",
        "remote_worker_job_assignment_fake_returned_result_enabled_by_map",
        "remote_worker_job_assignment_fake_progress_enabled_by_map",
        "remote_worker_job_assignment_completion_without_returned_packet_enabled_by_map",
        "remote_worker_job_assignment_provider_network_browser_enabled_by_map",
        "remote_worker_job_assignment_model_runtime_enabled_by_map",
        "remote_worker_job_assignment_trusted_memory_write_enabled_by_map",
        "remote_worker_job_assignment_patch_apply_enabled_by_map",
        "remote_worker_job_assignment_source_mutation_enabled_by_map",
        "remote_worker_job_assignment_route_mutation_enabled_by_map",
        "remote_worker_job_assignment_background_worker_enabled_by_map",
        "remote_worker_job_assignment_startup_autorun_enabled_by_map",
    ]:
        require(core.get("safety", {}).get(key) is False, "Core safety flag should be false: " + key)


def check_commands_and_codex_verify() -> None:
    commands = read(ROOT / "memory" / "ENGEL_COMMANDS.md")
    for phrase in [
        "remote worker assignment status",
        "remote worker assign preview",
        "remote worker jobs prepared",
        "Communication Queen Remote Worker Job Assignment V1",
    ]:
        require(phrase in commands, "command docs missing: " + phrase)
    codex = read(ROOT / "scripts" / "codex_verify.ps1")
    require("tools\\verify_engel_remote_worker_job_assignment.py" in codex, "codex verifier script missing assignment verifier")


def check_report() -> None:
    require(REPORT.exists(), "assignment report missing")
    text = read(REPORT)
    for phrase in [
        "Communication Queen Remote Worker Job Assignment V1",
        "files changed",
        "assignment contract summary",
        "worker registry used",
        "worker roles recognized",
        "job packet schema",
        "assignment states",
        "no phone connection occurred",
        "no Android runtime was executed",
        "no fake returned results/progress were created",
        "no job was marked completed without real returned result",
        "no model runtime or Hermes/Ollama/llama.cpp path was added",
        "no network/provider/browser behavior occurred",
        "no trusted-memory write occurred",
        "no patch apply occurred",
        "verifier results",
        "packaging skipped",
        "working tree note",
    ]:
        require(phrase.lower() in text.lower(), "report missing: " + phrase)


def main() -> int:
    checks = [
        ("files_exist", check_files_exist),
        ("contract", check_contract),
        ("module_behavior", check_module_behavior),
        ("no_active_forbidden_behavior", check_no_active_forbidden_behavior),
        ("system_integration_and_core", check_system_integration_and_core),
        ("commands_and_codex_verify", check_commands_and_codex_verify),
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
        print("\nEngel Remote Worker Job Assignment verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nEngel Remote Worker Job Assignment verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
