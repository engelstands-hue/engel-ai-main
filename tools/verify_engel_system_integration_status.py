from __future__ import annotations

import ast
import importlib.util
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_system_integration_status.py"
VERIFIER = ROOT / "tools" / "verify_engel_system_integration_status.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_SYSTEM_INTEGRATION_AND_CONTINUITY_RECONCILIATION_V1.md"
MAP_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
MAP_MD = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md"
COMPANION = ROOT / "engel_companion.py"
RESEARCH_OFFICE = ROOT / "engel_research_office.py"
BUILDER = ROOT / "tools" / "build_engel_core_continuity_map.py"
CORE_VERIFIER = ROOT / "tools" / "verify_engel_core_continuity_map.py"

REQUIRED_STATUSES = [
    "SYSTEM_INTEGRATION_RECONCILIATION",
    "CONTINUITY_RECONCILIATION",
    "COMPLEXITY_REDUCTION_PASS",
    "STATUS_SURFACES_CONNECTED",
    "CORE_CONTINUITY_COVERAGE_CHECKED",
    "GUI_STATUS_COVERAGE_CHECKED",
    "VERIFIER_COVERAGE_CHECKED",
    "PROTECTED_ACTIONS_ALIGNED",
    "PASSWORD_GATE_ALIGNMENT_CHECKED",
    "CODE_COMPANION_ALIGNMENT_CHECKED",
    "AI_GROWTH_ALIGNMENT_CHECKED",
    "BACKGROUND_WORKER_ALIGNMENT_CHECKED",
    "RESEARCH_TOGGLE_ALIGNMENT_CHECKED",
    "TRUTHFULNESS_GUARD_ALIGNMENT_CHECKED",
    "NO_NEW_RUNTIME_BEHAVIOR",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION_BEYOND_REFACTOR",
    "NO_PACKAGE_REFRESH",
    "NO_BACKGROUND_WORKER_STARTED",
    "NO_STARTUP_AUTORUN_ENABLED",
]

REQUIRED_SECTIONS = [
    "AI Growth systems",
    "Self-Learning systems",
    "Daily Cycle systems",
    "Candidate Review systems",
    "Memory Promotion systems",
    "Research-to-Fix systems",
    "Code Companion systems",
    "Code Companion Patch systems",
    "Global Password / Protected Actions",
    "Background Worker / Startup",
    "Research Toggle Worker",
    "Remote Worker / Mobile",
    "Truthfulness Guard",
    "Core Continuity",
    "GUI Status Surfaces",
    "Verifier Coverage",
    "Runtime / Environment Dependencies",
    "Model Library / Offline Model Readiness",
    "Manual Downloads",
    "Manual Downloads / Non-Model Materials",
    "Optional Local Tooling Environment",
    "Approved Library / Intake",
    "Safety Boundaries",
    "Package Visibility Records",
    "Active Build Plan",
    "Missing or Optional Systems",
    "Next Safe Integration Steps",
]

REQUIRED_LABELS = [
    "CONNECTED",
    "AVAILABLE",
    "MISSING_OPTIONAL",
    "MISSING_REQUIRED",
    "NEEDS_CORE_CONTINUITY_LINK",
    "NEEDS_GUI_LINK",
    "NEEDS_VERIFIER_LINK",
    "READ_ONLY_STATUS",
    "SAFE_TO_VIEW",
    "ACTION_REQUIRES_PASSWORD",
    "ACTION_REQUIRES_CONTRACT",
    "ACTION_REQUIRES_VERIFIER",
]

REQUIRED_SYSTEM_IDS = [
    "ai_growth_dashboard",
    "self_learning_mini_runner",
    "bounded_self_learning_scheduler",
    "learning_job_queue",
    "self_learning_run_controller",
    "candidate_learning_output_review",
    "daily_cycle",
    "candidate_review_dashboard",
    "fix_candidate_queue",
    "memory_promotion",
    "trusted_memory_target_contract",
    "approved_memory_promotion",
    "research_to_fix_loop",
    "code_companion_intelligence_loop",
    "code_companion_patch_stack",
    "global_password_protected_actions",
    "background_worker_startup_contract",
    "research_toggle_worker",
    "multi_android_remote_workers_protocol",
    "remote_worker_job_assignment",
    "android_studio_remote_worker_setup",
    "android_remote_worker_plan",
    "truthfulness_anti_flattery_guard",
    "core_continuity",
    "gui_status_surfaces",
    "verifier_coverage",
    "wsl_ubuntu_runtime_dependency",
    "wsl_ubuntu_non_model_material",
    "wsl_ubuntu_optional_local_tooling",
    "manual_model_intake_evaluator",
    "manual_model_downloads_root",
    "llm_python_library_intake_plan",
    "manual_model_intake_approved_library_boundary",
    "outside_ai_boundary_rule",
    "manual_model_intake_safety_boundary",
    "package_visibility_records",
    "active_build_plan_learning_and_fixing",
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
    "glob",
    "shutil",
}

FORBIDDEN_CALL_ATTRS = {
    "write_text",
    "write_bytes",
    "unlink",
    "remove",
    "rename",
    "replace",
    "mkdir",
    "rmdir",
    "rglob",
    "glob",
    "walk",
}

FORBIDDEN_GUI_LABELS = [
    "Apply All",
    "Enable All",
    "Start All",
    "Run All",
    "Patch All",
    "Promote All",
    "Package Refresh",
    "Enable Startup",
    "Start Background Worker",
    "Bypass Password",
    "Disable Safety",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_system_integration_status", MODULE)
    require(spec is not None and spec.loader is not None, "could not load system integration status module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_system_integration_status"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [MODULE, VERIFIER, BUILDER, CORE_VERIFIER, COMPANION, RESEARCH_OFFICE]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path.relative_to(ROOT)))


def check_static_module() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for flag in ["--status", "--json", "--check-links"]:
        require(flag in source, "module missing CLI option: " + flag)
    for status in REQUIRED_STATUSES:
        require(status in source, "module missing required status: " + status)
    for section in REQUIRED_SECTIONS:
        require(section in source, "module missing required section: " + section)
    for label in REQUIRED_LABELS:
        require(label in source, "module missing required display label: " + label)
    for system_id in REQUIRED_SYSTEM_IDS:
        require(system_id in source, "module missing system id: " + system_id)
    for needle in [
        "This module checks explicit known local paths only.",
        "does not run workers",
        "does not run patch apply",
        "does not run package refresh",
        "No new runtime behavior.",
        "No provider calls.",
        "No startup autorun enabled.",
    ]:
        require(needle in source, "module missing read-only/safety text: " + needle)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "module imports forbidden package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "module imports forbidden package: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                require(func.attr not in FORBIDDEN_CALL_ATTRS, "module contains forbidden call: " + func.attr)
            elif isinstance(func, ast.Name):
                require(func.id not in {"eval", "exec", "__import__"}, "module uses forbidden dynamic call: " + func.id)
        elif isinstance(node, ast.While):
            raise CheckFailure("module contains while loop")


def check_runtime_behavior() -> None:
    module = load_module()
    payload = module.integration_summary()
    rendered = module.render_status()
    links = module.render_check_links()
    for status in REQUIRED_STATUSES:
        require(status in payload.get("status_labels", []), "payload missing status: " + status)
        require(status in rendered, "rendered status missing: " + status)
    for section in REQUIRED_SECTIONS:
        require(section in payload.get("sections", []), "payload missing section: " + section)
        require(section in rendered, "rendered status missing section: " + section)
    for label in REQUIRED_LABELS:
        require(label in payload.get("display_labels", []), "payload missing display label: " + label)
    system_ids = {str(system.get("system_id")) for system in payload.get("systems", [])}
    for system_id in REQUIRED_SYSTEM_IDS:
        require(system_id in system_ids, "payload missing system: " + system_id)
    require("hive_safety_password_gate" in system_ids, "optional Hive password gate system not inventoried")
    require("background_worker_registry" in system_ids, "optional background worker registry not inventoried")
    manual_model = next((system for system in payload.get("systems", []) if system.get("system_id") == "manual_model_intake_evaluator"), None)
    require(isinstance(manual_model, dict), "manual model intake evaluator is not inventoried")
    require("engel_manual_model_intake_evaluator.py" in manual_model.get("primary_files", []), "manual model intake evaluator helper path missing")
    require(r"tools\verify_engel_manual_model_intake_evaluator.py" in manual_model.get("verifier_files", []), "manual model intake evaluator verifier path missing")
    for report in [
        r"reports\codex_bridge\ENGEL_MANUAL_MODEL_INTAKE_EVALUATION_V1.md",
        r"reports\codex_bridge\ENGEL_MODEL_INTAKE_INTEGRATION_UPDATE.md",
    ]:
        require(report in manual_model.get("reports", []), "manual model intake evaluator missing report path: " + report)
    require(manual_model.get("review_output_folder") == "reports\\model_intake_reviews\\", "manual model intake review folder missing")
    require(manual_model.get("manual_downloads_root") == "/opt/engel/models-active", "active CT246 model root missing")
    require("no real model evaluated yet unless review files exist" in str(manual_model.get("current_state")), "manual model intake current state missing")
    for boundary in [
        "MODEL_INTAKE_REVIEW_ONLY",
        "EXPLICIT_CANDIDATE_PATH_REQUIRED",
        "MANUAL_DOWNLOADS_ONLY",
        "NO_MODEL_LOADING",
        "NO_INFERENCE",
        "NO_AUTO_MOVE",
        "NO_AUTO_DELETE",
        "WSL_UBUNTU_CLASSIFIED_NOT_MODEL",
    ]:
        require(boundary in str(manual_model.get("safety_boundary")), "manual model intake boundary missing: " + boundary)
    wsl_runtime = next((system for system in payload.get("systems", []) if system.get("system_id") == "wsl_ubuntu_runtime_dependency"), None)
    require(isinstance(wsl_runtime, dict), "WSL Ubuntu runtime dependency is not inventoried")
    for path in [
        "memory\\ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.md",
        "memory\\ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.json",
    ]:
        require(path in wsl_runtime.get("primary_files", []), "WSL Ubuntu primary file missing: " + path)
    require("tools\\verify_engel_wsl_ubuntu_runtime_dependency.py" in wsl_runtime.get("verifier_files", []), "WSL Ubuntu verifier missing")
    require("reports\\codex_bridge\\ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.md" in wsl_runtime.get("reports", []), "WSL Ubuntu report missing")
    require(wsl_runtime.get("core_continuity_node_expected") == "engel_wsl_ubuntu_runtime_dependency_v1", "WSL Ubuntu Core Continuity node expectation missing")
    require(wsl_runtime.get("manual_downloads_root") == "/mnt/engel-hdd-vault/wsl", "WSL Ubuntu Dell HDD archive root missing")
    for boundary in [
        "environment/runtime dependency",
        "stored under Dell HDD archive when mounted",
        "not trusted memory",
        "STAGE_2_AUTONOMY",
        "auto-run authorized",
        "STAGE_3_AUTONOMY",
        "auto-install authorized",
        "model loading authorized",
        "inference authorized",
        "training authorized",
    ]:
        require(boundary in str(wsl_runtime.get("safety_boundary")), "WSL Ubuntu boundary missing: " + boundary)
    for dropped in ("no auto-run", "no auto install", "no model loading", "no inference", "no training"):
        require(dropped not in str(wsl_runtime.get("safety_boundary")), f"WSL Ubuntu boundary must drop '{dropped}' under Stage 3")
    wsl_bridge = next((system for system in payload.get("systems", []) if system.get("system_id") == "wsl_bridge"), None)
    require(isinstance(wsl_bridge, dict), "WSL bridge is not inventoried")
    for path in [
        "engel_wsl_bridge.py",
        "engel_ai_update_routes.py",
        "engel_ai.py",
    ]:
        require(path in wsl_bridge.get("primary_files", []), "WSL bridge primary file missing: " + path)
    require("tools\\verify_engel_wsl_bridge.py" in wsl_bridge.get("verifier_files", []), "WSL bridge verifier missing")
    require("reports\\codex_bridge\\ENGEL_WSL_BRIDGE_V1.md" in wsl_bridge.get("reports", []), "WSL bridge report missing")
    require(wsl_bridge.get("core_continuity_node_expected") == "engel_wsl_bridge_v1", "WSL bridge Core Continuity node expectation missing")
    require(wsl_bridge.get("manual_downloads_root") == "D:\\WSL\\Ubuntu", "WSL bridge preferred Ubuntu root missing")
    for boundary in [
        "local WSL bridge",
        "status routes read-only-status-only",
        "Phase B Stage 3 action routes fixed allowlist IDs only",
        "allowlisted WSL commands only",
        "timeout-bounded",
        "no free-form shell",
        "no WSL install",
        "package-manager words contracted to fixed Stage 3 actions",
        "no sudo",
        "no hidden background worker",
        "no browser spawn",
        "no provider calls",
        "no arbitrary outbound network",
        "no Engel source mutation from WSL",
        "no trusted-memory write",
    ]:
        require(boundary in str(wsl_bridge.get("safety_boundary")), "WSL bridge boundary missing: " + boundary)
    require("MISSING_OPTIONAL" in rendered or "MISSING_OPTIONAL" in links, "optional missing systems are not reported honestly")
    require(payload["summary"]["missing_required_count"] == 0, "required system links should not be missing")
    learning_queue = next((system for system in payload.get("systems", []) if system.get("system_id") == "learning_job_queue"), None)
    require(isinstance(learning_queue, dict), "Learning Job Queue is not inventoried")
    for path in [
        "engel_learning_job_queue.py",
        r"memory\ENGEL_LEARNING_JOB_QUEUE_CONTRACT_V1.json",
        r"memory\ENGEL_LEARNING_JOB_QUEUE_CONTRACT_V1.md",
    ]:
        require(path in learning_queue.get("primary_files", []), "Learning Job Queue primary file missing: " + path)
    require(r"tools\verify_engel_learning_job_queue.py" in learning_queue.get("verifier_files", []), "Learning Job Queue verifier missing")
    require(r"reports\codex_bridge\ENGEL_LEARNING_JOB_QUEUE_V1.md" in learning_queue.get("reports", []), "Learning Job Queue report missing")
    require(learning_queue.get("core_continuity_node_expected") == "engel_learning_job_queue_v1", "Learning Job Queue Core Continuity node expectation missing")
    require(learning_queue.get("queue_folder") == "reports\\learning_job_queue\\", "Learning Job Queue folder missing")
    require(learning_queue.get("receipt_folder") == "reports\\learning_job_queue_receipts\\", "Learning Job Queue receipt folder missing")
    for needle in [
        "Learning Job Queue V1 available",
        "Self-Learning Run Controller V1",
        "LEARNING_JOB_QUEUE",
        "CANDIDATE_LEARNING_ONLY",
        "EXPLICIT_JOBS_ONLY",
        "APPROVED_LOCAL_SOURCES_ONLY",
        "REAL_SOURCE_REQUIRED",
        "NO_FAKE_QUEUE_RECORDS",
        "NOT_TRUSTED_MEMORY",
        "PASSWORD_GATE_REQUIRED_FOR_WRITE_RUN",
        "RECEIPTS_REQUIRED",
    ]:
        require(needle in str(learning_queue), "Learning Job Queue integration text missing: " + needle)
    run_controller = next((system for system in payload.get("systems", []) if system.get("system_id") == "self_learning_run_controller"), None)
    require(isinstance(run_controller, dict), "Self-Learning Run Controller is not inventoried")
    for path in [
        "engel_self_learning_run_controller.py",
        r"memory\ENGEL_SELF_LEARNING_RUN_CONTROLLER_CONTRACT_V1.json",
        r"memory\ENGEL_SELF_LEARNING_RUN_CONTROLLER_CONTRACT_V1.md",
    ]:
        require(path in run_controller.get("primary_files", []), "Self-Learning Run Controller primary file missing: " + path)
    require(r"tools\verify_engel_self_learning_run_controller.py" in run_controller.get("verifier_files", []), "Self-Learning Run Controller verifier missing")
    require(r"reports\codex_bridge\ENGEL_SELF_LEARNING_RUN_CONTROLLER_V1.md" in run_controller.get("reports", []), "Self-Learning Run Controller report missing")
    require(run_controller.get("core_continuity_node_expected") == "engel_self_learning_run_controller_v1", "Self-Learning Run Controller Core Continuity node expectation missing")
    require(run_controller.get("receipt_folder") == "reports\\self_learning_run_receipts\\", "Self-Learning Run Controller receipt folder missing")
    require(run_controller.get("summary_folder") == "reports\\self_learning_run_summaries\\", "Self-Learning Run Controller summary folder missing")
    for needle in [
        "Self-Learning Run Controller V1 available",
        "Fix Candidate Queue V1",
        "SELF_LEARNING_RUN_CONTROLLER",
        "BOUNDED_LEARNING_RUNNER",
        "REAL_QUEUE_JOBS_ONLY",
        "REAL_SOURCE_REQUIRED",
        "CANDIDATE_LEARNING_ONLY",
        "UNTRUSTED_OUTPUTS_ONLY",
        "NOT_TRUSTED_MEMORY",
        "PASSWORD_GATE_REQUIRED_FOR_RUN",
        "RECEIPTS_REQUIRED",
        "no trusted-memory write",
        "no source mutation",
        "no patch apply",
    ]:
        require(needle in str(run_controller), "Self-Learning Run Controller integration text missing: " + needle)
    output_review = next((system for system in payload.get("systems", []) if system.get("system_id") == "candidate_learning_output_review"), None)
    require(isinstance(output_review, dict), "Candidate Learning Output Review is not inventoried")
    for path in [
        "engel_candidate_learning_output_review.py",
        r"memory\ENGEL_CANDIDATE_LEARNING_OUTPUT_REVIEW_CONTRACT_V1.json",
        r"memory\ENGEL_CANDIDATE_LEARNING_OUTPUT_REVIEW_CONTRACT_V1.md",
    ]:
        require(path in output_review.get("primary_files", []), "Candidate Learning Output Review primary file missing: " + path)
    require(r"tools\verify_engel_candidate_learning_output_review.py" in output_review.get("verifier_files", []), "Candidate Learning Output Review verifier missing")
    require(r"reports\codex_bridge\ENGEL_CANDIDATE_LEARNING_OUTPUT_REVIEW_V1.md" in output_review.get("reports", []), "Candidate Learning Output Review report missing")
    require(output_review.get("core_continuity_node_expected") == "engel_candidate_learning_output_review_v1", "Candidate Learning Output Review Core Continuity node expectation missing")
    for needle in [
        "Candidate Learning Output Review V1 available",
        "read-only review window",
        "honest empty state",
        "CANDIDATE_LEARNING_OUTPUT_REVIEW",
        "READ_ONLY_REVIEW_LAYER",
        "EXISTING_OUTPUTS_ONLY",
        "NO_APPROVAL",
        "NO_PROMOTION",
        "NO_APPLY",
        "NO_RUN_JOBS",
        "no trusted-memory write",
        "no source mutation",
    ]:
        require(needle in str(output_review), "Candidate Learning Output Review integration text missing: " + needle)
    active_plan = next((system for system in payload.get("systems", []) if system.get("system_id") == "active_build_plan_learning_and_fixing"), None)
    require(isinstance(active_plan, dict), "active build plan is not inventoried")
    for path in [
        r"memory\ENGEL_ACTIVE_BUILD_PLAN_LEARNING_AND_FIXING_V1.json",
        r"memory\ENGEL_ACTIVE_BUILD_PLAN_LEARNING_AND_FIXING_V1.md",
    ]:
        require(path in active_plan.get("primary_files", []), "active build plan primary file missing: " + path)
    require(r"tools\verify_engel_active_build_plan_learning_and_fixing.py" in active_plan.get("verifier_files", []), "active build plan verifier missing")
    require(r"reports\codex_bridge\ENGEL_ACTIVE_BUILD_PLAN_LEARNING_AND_FIXING_V1.md" in active_plan.get("reports", []), "active build plan report missing")
    require(active_plan.get("core_continuity_node_expected") == "engel_active_build_plan_learning_and_fixing_v1", "active build plan Core Continuity node expectation missing")
    for needle in [
        "Integrated Status + WSL Runtime Package Refresh",
        "LLM Library and Python Library Intake",
        "Learning Job Queue",
        "Self-Learning Run Controller",
        "Fix Candidate Queue",
    ]:
        require(needle in str(active_plan.get("current_state")) or needle in rendered, "active build plan next path missing: " + needle)
    for boundary in [
        "LEARNING_AND_FIXING_PATH",
        "PASSWORD_GATE_REQUIRED_FOR_WRITE_APPLY_RUN",
        "PROTECTED_ACTION_REGISTRY_REQUIRED",
        "RECEIPTS_REQUIRED",
        "VERIFIERS_REQUIRED",
    ]:
        require(boundary in str(active_plan.get("safety_boundary")), "active build plan boundary missing: " + boundary)

    outside_ai = next((system for system in payload.get("systems", []) if system.get("system_id") == "outside_ai_boundary_rule"), None)
    require(isinstance(outside_ai, dict), "Outside-AI Boundary Rule is not inventoried")
    for path in [
        "engel_outside_ai_boundary.py",
        r"memory\ENGEL_OUTSIDE_AI_BOUNDARY_RULE_V1.json",
        r"memory\ENGEL_OUTSIDE_AI_BOUNDARY_RULE_V1.md",
    ]:
        require(path in outside_ai.get("primary_files", []), "Outside-AI Boundary primary file missing: " + path)
    require(r"tools\verify_engel_outside_ai_boundary.py" in outside_ai.get("verifier_files", []), "Outside-AI Boundary verifier missing")
    require(r"reports\codex_bridge\ENGEL_OUTSIDE_AI_BOUNDARY_RULE_V1.md" in outside_ai.get("reports", []), "Outside-AI Boundary report missing")
    require(outside_ai.get("core_continuity_node_expected") == "engel_outside_ai_boundary_rule_v1", "Outside-AI Boundary Core Continuity node expectation missing")
    for needle in [
        "Outside-AI Boundary V1 available",
        "Engel uses Tools/AI",
        "Tools/AI do not use Engel",
        "HERMES_APPROVED_FOR_LOCAL_TESTING_HUMAN_DRIVEN_ONLY",
        "NO_OUTSIDE_AI_CONTROL",
        "NO_BYPASS",
        "NO_TRUSTED_MEMORY_WRITE",
        "NO_REMOTE_QUEEN_CONTROL",
    ]:
        require(needle in str(outside_ai), "Outside-AI Boundary integration text missing: " + needle)

    multi_android = next((system for system in payload.get("systems", []) if system.get("system_id") == "multi_android_remote_workers_protocol"), None)
    require(isinstance(multi_android, dict), "Multi Android Remote Workers Protocol is not inventoried")
    for path in [
        "engel_multi_android_remote_workers.py",
        "engel_android_remote_worker_protocol.py",
        "engel_remote_worker_app_scaffold.py",
        r"memory\ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.json",
        r"memory\ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.md",
        r"memory\ENGEL_ANDROID_REMOTE_WORKER_REGISTRY_V1.json",
        r"remote_workers\android_worker_alpha",
        r"remote_workers\android_worker_beta",
        r"remote_workers\android_worker_gamma",
    ]:
        require(path in multi_android.get("primary_files", []), "Multi Android primary file/folder missing: " + path)
    require(r"tools\verify_engel_multi_android_remote_workers.py" in multi_android.get("verifier_files", []), "Multi Android verifier missing")
    require(r"reports\codex_bridge\ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.md" in multi_android.get("reports", []), "Multi Android report missing")
    require(multi_android.get("core_continuity_node_expected") == "engel_multi_android_remote_workers_protocol_v1", "Multi Android Core Continuity node expectation missing")
    for needle in [
        "Multi Android Remote Workers Protocol V1 available",
        "manual_transfer_v1",
        "real data only",
        "prepared / awaiting manual worker status",
        "Alpha/Beta/Gamma",
        "Communication Queen",
        "Remote Workers are not Queens",
        "old single-worker scaffold is superseded",
        "REAL_DATA_ONLY",
        "MANUAL_TRANSFER_MODE_ONLY",
        "ON_DEVICE_AUTONOMY_ALLOWED",
        "AUTONOMY_SCOPE_ASSIGNED_JOB_SANDBOX_ONLY",
        "COMMUNICATION_QUEEN_ROUTING_REQUIRED",
        "REMOTE_WORKER_NOT_QUEEN",
        "CANDIDATE_OUTPUTS_ONLY",
        "no phone connection",
        "no fake worker progress",
        "no trusted-memory write",
        "no patch apply",
        "no Hermes/Ollama/llama.cpp",
    ]:
        require(needle in str(multi_android) or needle in rendered, "Multi Android integration text missing: " + needle)

    assignment = next((system for system in payload.get("systems", []) if system.get("system_id") == "remote_worker_job_assignment"), None)
    require(isinstance(assignment, dict), "Remote Worker Job Assignment is not inventoried")
    for path in [
        "engel_remote_worker_job_assignment.py",
        r"memory\ENGEL_REMOTE_WORKER_JOB_ASSIGNMENT_CONTRACT_V1.json",
        r"memory\ENGEL_REMOTE_WORKER_JOB_ASSIGNMENT_CONTRACT_V1.md",
        r"memory\ENGEL_ANDROID_REMOTE_WORKER_REGISTRY_V1.json",
        r"remote_workers\android_worker_alpha",
        r"remote_workers\android_worker_beta",
        r"remote_workers\android_worker_gamma",
    ]:
        require(path in assignment.get("primary_files", []), "Remote Worker Assignment primary file/folder missing: " + path)
    require(r"tools\verify_engel_remote_worker_job_assignment.py" in assignment.get("verifier_files", []), "Remote Worker Assignment verifier missing")
    require(r"reports\codex_bridge\ENGEL_REMOTE_WORKER_JOB_ASSIGNMENT_V1.md" in assignment.get("reports", []), "Remote Worker Assignment report missing")
    require(assignment.get("core_continuity_node_expected") == "communication_queen_remote_worker_job_assignment_v1", "Remote Worker Assignment Core Continuity node expectation missing")
    for needle in [
        "Communication Queen Remote Worker Job Assignment V1 available",
        "Alpha/Beta/Gamma",
        "first real Alpha summarize_text packet",
        "real prepared_for_manual_transfer job packets",
        "real local input files",
        "COMMUNICATION_QUEEN_REMOTE_WORKER_JOB_ASSIGNMENT",
        "REAL_JOB_PACKETS_ONLY",
        "REAL_INPUT_FILE_REQUIRED",
        "SAFE_LOCAL_INPUTS_ONLY",
        "MANUAL_TRANSFER_ONLY",
        "COMMUNICATION_QUEEN_ROUTING_REQUIRED",
        "REMOTE_WORKER_NOT_QUEEN",
        "PREPARED_FOR_MANUAL_TRANSFER_ONLY",
        "CANDIDATE_OUTPUTS_ONLY",
        "no phone connection",
        "no Android runtime execution from Engel",
        "no worker job execution from Engel",
        "no fake returned status/result/progress",
        "no completion without returned packet",
        "no trusted-memory write",
        "no patch apply",
        "Hermes remains rejected / do not install",
    ]:
        require(needle in str(assignment) or needle in rendered, "Remote Worker Assignment integration text missing: " + needle)

    adb_setup = next((system for system in payload.get("systems", []) if system.get("system_id") == "android_studio_remote_worker_setup"), None)
    require(isinstance(adb_setup, dict), "Android Studio Remote Worker setup is not inventoried")
    for path in [
        "tools\\setup_android_worker_alpha_adb.py",
        r"memory\ENGEL_ANDROID_STUDIO_REMOTE_WORKER_SETUP_V1.json",
        r"memory\ENGEL_ANDROID_STUDIO_REMOTE_WORKER_SETUP_V1.md",
        r"memory\ENGEL_ANDROID_WORKER_ALPHA_PHONE_BUTTON_UI_V1.json",
        r"memory\ENGEL_ANDROID_WORKER_ALPHA_PHONE_BUTTON_UI_V1.md",
        r"remote_workers\android_worker_alpha\finish_alpha_job.py",
        r"remote_workers\android_worker_alpha\start_remote_worker_ui.py",
        r"remote_workers\android_worker_alpha\remote_worker_phone_ui.py",
        r"remote_workers\android_worker_alpha\termux_widget_shortcuts\EngelWorkerAlphaUI",
        r"remote_workers\android_worker_alpha\communication_queen_choices.py",
        r"remote_workers\android_worker_alpha\queen_choice_bridge.py",
        r"remote_workers\android_worker_alpha",
        r"remote_workers\android_worker_alpha\jobs\20260516T201324Z_android_worker_alpha_summarize_text_summarize_engel_remote_worke.json",
        r"reports\codex_bridge\ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.md",
    ]:
        require(path in adb_setup.get("primary_files", []), "Android Studio setup primary file/folder missing: " + path)
    require(r"tools\verify_android_worker_alpha_adb_setup.py" in adb_setup.get("verifier_files", []), "Android Studio setup verifier missing")
    require(r"tools\verify_android_worker_alpha_phone_button_ui.py" in adb_setup.get("verifier_files", []), "Android Worker Alpha phone button UI verifier missing")
    require(r"tools\verify_android_worker_alpha_finish_setup.py" in adb_setup.get("verifier_files", []), "Android Worker Alpha finish setup verifier missing")
    require(r"reports\codex_bridge\ENGEL_ANDROID_STUDIO_REMOTE_WORKER_SETUP_V1.md" in adb_setup.get("reports", []), "Android Studio setup report missing")
    require(r"reports\codex_bridge\ENGEL_ANDROID_WORKER_ALPHA_ON_DEVICE_RUN_EXTENSION_V1.md" in adb_setup.get("reports", []), "Android Worker Alpha on-device run extension report missing")
    require(r"reports\codex_bridge\ENGEL_ANDROID_WORKER_ALPHA_PHONE_BUTTON_UI_V1.md" in adb_setup.get("reports", []), "Android Worker Alpha phone button UI report missing")
    require(r"reports\codex_bridge\ENGEL_ANDROID_WORKER_ALPHA_FINISH_SETUP_V1.md" in adb_setup.get("reports", []), "Android Worker Alpha finish setup report missing")
    require(adb_setup.get("core_continuity_node_expected") == "android_studio_remote_worker_setup_v1", "Android Studio setup Core Continuity node expectation missing")
    for needle in [
        "Android Studio / ADB setup helper available",
        "bounded ADB file-transfer bridge",
        "check-python",
        "check-termux",
        "prepare-run-command",
        "prepare-phone-button-commands",
        "check-phone-ui",
        "push-phone-button-ui",
        "prepare-one-line-termux-finish",
        "push-finish-runner",
        "finish-alpha-worker",
        "--i-understand-this-uses-adb",
        "--i-approve-run-worker-on-phone",
        "--i-approve-finish-alpha-worker",
        "no second ADB/Termux hook",
        "COMPLETION_NOT_TRUSTED_UNTIL_PULL_VALIDATION",
        "RUN_WORKER_REQUIRES_EXPLICIT_APPROVAL",
        "no worker execution during push",
        "no fake status/result/progress/log/receipt",
        "phone button UI uses real local files",
        "bounded Communication Queen choices",
        "no phone control loop",
        "ANDROID_STUDIO_REMOTE_WORKER_SETUP",
        "ANDROID_WORKER_ALPHA_PHONE_BUTTON_UI",
        "ANDROID_WORKER_ALPHA_FINISH_SETUP",
        "ADB_FILE_TRANSFER_ONLY",
        "HUMAN_APPROVED_TRANSPORT_ONLY",
        "MANUAL_TRANSFER_BRIDGE",
        "TERMUX_WIDGET_SHORTCUT_TEMPLATE",
        "REAL_FILES_ONLY",
        "QUEEN_CHOICES_BOUNDED",
        "FINISH_WORKER_REQUIRES_EXPLICIT_APPROVAL",
        "ONE_LINE_TERMUX_FALLBACK_ONLY",
        "REMOTE_WORKER_NOT_QUEEN",
        "REAL_JOB_PACKET_ONLY",
        "REAL_INPUT_FILE_ONLY",
        "no job completion marking",
        "no Termux/app/package/model install automation",
        "no Hermes/Ollama/llama.cpp",
        "no model runtime",
        "no provider/network/browser",
        "no ADB wireless",
        "no trusted-memory write",
        "no patch apply",
    ]:
        require(needle in str(adb_setup) or needle in rendered, "Android Studio setup integration text missing: " + needle)

    android_worker = next((system for system in payload.get("systems", []) if system.get("system_id") == "android_remote_worker_plan"), None)
    require(isinstance(android_worker, dict), "Android Remote Worker Plan is not inventoried")
    for path in [
        r"memory\ENGEL_ANDROID_REMOTE_WORKER_PLAN_V1.json",
        r"memory\ENGEL_ANDROID_REMOTE_WORKER_PLAN_V1.md",
        "engel_android_remote_worker_contract.py",
    ]:
        require(path in android_worker.get("primary_files", []), "Android Remote Worker primary file missing: " + path)
    require(r"tools\verify_android_remote_worker_contract.py" in android_worker.get("verifier_files", []), "Android Remote Worker verifier missing")
    require(r"reports\codex_bridge\ENGEL_ANDROID_REMOTE_WORKER_PLAN_V1.md" in android_worker.get("reports", []), "Android Remote Worker report missing")
    for needle in [
        "scaffold-only",
        "controlled by Communication Queen",
        "not a Queen",
        "no runtime phone connection",
        "future Phase 2 manual JSON handoff",
        "CONTROLLED_BY_COMMUNICATION_QUEEN",
        "ROUTED_THROUGH_COMMUNICATION_QUEEN",
        "NOT_A_QUEEN",
    ]:
        require(needle in str(android_worker.get("current_state")) or needle in str(android_worker.get("safety_boundary")) or needle in rendered, "Android Remote Worker text missing: " + needle)

    llm_python = next((system for system in payload.get("systems", []) if system.get("system_id") == "llm_python_library_intake_plan"), None)
    require(isinstance(llm_python, dict), "LLM and Python Library Intake Plan is not inventoried")
    for path in [
        r"memory\ENGEL_LLM_AND_PYTHON_LIBRARY_INTAKE_PLAN_V1.json",
        r"memory\ENGEL_LLM_AND_PYTHON_LIBRARY_INTAKE_PLAN_V1.md",
    ]:
        require(path in llm_python.get("primary_files", []), "LLM/Python intake primary file missing: " + path)
    require(r"tools\verify_engel_llm_and_python_library_intake_plan.py" in llm_python.get("verifier_files", []), "LLM/Python intake verifier missing")
    require(r"reports\codex_bridge\ENGEL_LLM_AND_PYTHON_LIBRARY_INTAKE_PLAN_V1.md" in llm_python.get("reports", []), "LLM/Python intake report missing")
    for needle in [
        "model candidate intake path",
        "Python docs/reference intake path",
        "Model Library / Non-Model Library readiness path",
        "Android Remote Worker non-model reference boundary",
        "Manual LLM Candidate Review Batch V1",
        "Python Library Approved Materials Intake V1",
        "no model loading/inference/package install",
        "Android Remote Worker references are non-model/scaffold-only",
    ]:
        require(needle in str(llm_python.get("current_state")) or needle in str(llm_python.get("safety_boundary")) or needle in rendered, "LLM/Python intake text missing: " + needle)

    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--status"], stdout=out, stderr=err) == 0, "module --status failed")
    require("Engel System Integration and Continuity Reconciliation V1" in out.getvalue(), "status output missing title")
    out = io.StringIO()
    require(module.main(["--json"], stdout=out, stderr=err) == 0, "module --json failed")
    json_payload = json.loads(out.getvalue())
    require(json_payload["summary"]["systems_total"] == payload["summary"]["systems_total"], "json output summary mismatch")
    out = io.StringIO()
    require(module.main(["--check-links"], stdout=out, stderr=err) == 0, "module --check-links failed")
    require("Missing optional systems" in out.getvalue(), "check-links missing optional section")


def check_core_continuity() -> None:
    data = json.loads(read(MAP_JSON))
    md = read(MAP_MD)
    node = data.get("engel_system_integration_continuity_reconciliation_v1")
    require(isinstance(node, dict), "Core Continuity reconciliation node missing")
    require(node.get("type") == "system_integration_continuity_reconciliation", "reconciliation node type mismatch")
    for status in [
        "SYSTEM_INTEGRATION_RECONCILIATION",
        "CORE_CONTINUITY_COVERAGE_CHECKED",
        "GUI_STATUS_COVERAGE_CHECKED",
        "VERIFIER_COVERAGE_CHECKED",
        "PROTECTED_ACTIONS_ALIGNED",
        "NO_NEW_RUNTIME_BEHAVIOR",
        "NO_PACKAGE_REFRESH",
    ]:
        require(status in node.get("status", []), "reconciliation node missing status: " + status)
        require(status in md, "Core Continuity Markdown missing status: " + status)
    for related in [
        "Engel AI Growth Dashboard V1",
        "Engel Code Companion Intelligence Loop V1",
        "Engel Global Password-Gated Action Layer V1",
        "Protected Action Registry",
        "Engel Background Worker and Startup Autorun Contract V1",
        "Engel Research Toggle Overnight Worker V1",
        "Engel Truthfulness and Anti-Flattery Guard V1",
        "Engel Manual Model Intake Evaluator V1",
        "Engel WSL Ubuntu Runtime Dependency V1",
        "Prompt Injection Guard",
        "Untrusted Content Guard",
        "Authority Hierarchy",
    ]:
        require(related in node.get("related_nodes", []), "reconciliation node missing related node: " + related)
    for needle in [
        "Engel System Integration and Continuity Reconciliation V1",
        "connects previously added systems",
        "reduces drift and duplicate status surfaces",
        "does not enable new runtime behavior",
        "does not package",
        "preserves all safety boundaries",
        "missing optional systems are reported honestly",
    ]:
        require(needle in md, "Core Continuity Markdown missing reconciliation text: " + needle)


def check_gui_integration() -> None:
    for path in [COMPANION, RESEARCH_OFFICE]:
        text = read(path)
        require("System Integration" in text, path.name + " missing System Integration tab")
        require("system_integration_status" in text, path.name + " missing integration status module reference")
        require("system_integration_status.render_status()" in text, path.name + " missing integration render call")
        for label in FORBIDDEN_GUI_LABELS:
            require(label not in text, path.name + " contains forbidden GUI label: " + label)


def check_report_if_present() -> None:
    if not REPORT.exists():
        return
    text = read(REPORT)
    for needle in [
        "files read first",
        "systems inventoried",
        "files created",
        "files updated",
        "missing optional systems",
        "Core Continuity updates",
        "GUI/status updates",
        "verifier coverage summary",
        "status smoke results",
        "verification results",
        "focused safety scan result",
        "no new runtime behavior was added",
        "packaging skipped",
        "final scoped process sweep",
        "git status",
    ]:
        require(needle in text, "report missing section/detail: " + needle)


def main() -> int:
    checks = [
        ("files", check_files_exist),
        ("static_module", check_static_module),
        ("runtime_behavior", check_runtime_behavior),
        ("core_continuity", check_core_continuity),
        ("gui_integration", check_gui_integration),
        ("report", check_report_if_present),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(f"{name}: {exc}")
            print(f"FAIL {name}: {exc}")
        except Exception as exc:
            failures.append(f"{name}: unexpected error: {exc}")
            print(f"FAIL {name}: unexpected error: {exc}")
    if failures:
        print("\nEngel System Integration Status verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nEngel System Integration Status verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
