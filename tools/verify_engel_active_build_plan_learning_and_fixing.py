from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PLAN_JSON = ROOT / "memory" / "ENGEL_ACTIVE_BUILD_PLAN_LEARNING_AND_FIXING_V1.json"
PLAN_MD = ROOT / "memory" / "ENGEL_ACTIVE_BUILD_PLAN_LEARNING_AND_FIXING_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_ACTIVE_BUILD_PLAN_LEARNING_AND_FIXING_V1.md"
SYSTEM_INTEGRATION = ROOT / "engel_system_integration_status.py"
CORE_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
CORE_MD = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md"
BUILDER = ROOT / "tools" / "build_engel_core_continuity_map.py"
CORE_VERIFIER = ROOT / "tools" / "verify_engel_core_continuity_map.py"

REQUIRED_STATUSES = [
    "ACTIVE_BUILD_PLAN",
    "LEARNING_AND_FIXING_PATH",
    "INTEGRATED_STATUS_PACKAGE_STEP_INCLUDED",
    "LLM_LIBRARY_NEXT",
    "PYTHON_LIBRARY_NEXT",
    "LEARNING_JOB_QUEUE_NEXT",
    "SELF_LEARNING_RUN_CONTROLLER_NEXT",
    "FIX_CANDIDATE_QUEUE_NEXT",
    "LEARNING_TO_FIX_CYCLE_NEXT",
    "PASSWORD_GATE_REQUIRED_FOR_WRITE_APPLY_RUN",
    "PROTECTED_ACTION_REGISTRY_REQUIRED",
    "RECEIPTS_REQUIRED",
    "VERIFIERS_REQUIRED",
    "HUMAN_REVIEW_REQUIRED_FOR_TRUSTED_MEMORY",
    "NO_PROVIDER_CALLS_BY_DEFAULT",
    "NO_NETWORK_BY_DEFAULT",
    "NO_BROWSER_BY_DEFAULT",
    "NO_MODEL_RUNTIME_BY_DEFAULT",
    "NO_TRUSTED_MEMORY_WRITE_BY_DEFAULT",
    "NO_UNBOUNDED_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN_BY_DEFAULT",
]

EXPECTED_STEP_IDS = [
    "01_integrated_status_wsl_runtime_package_refresh",
    "02_core_continuity_update_packaged_integrated_status_wsl_visibility",
    "03_engel_llm_and_python_library_intake_plan",
    "04_engel_learning_job_queue",
    "05_engel_self_learning_run_controller",
    "06_engel_fix_candidate_queue",
    "07_engel_learning_to_fix_cycle",
    "08_package_refresh_learning_fix_controls",
]

REQUIRED_STEP_FIELDS = [
    "step_id",
    "title",
    "purpose",
    "required_inputs",
    "outputs",
    "protected_actions",
    "required_verifiers",
    "safety_boundary",
    "definition_of_done",
    "next_step",
]

REQUIRED_RELATED_NODES = [
    "System Integration and Continuity Reconciliation V1",
    "WSL Ubuntu Runtime Dependency V1",
    "Manual Model Intake Evaluator V1",
    "Model Library Plan V1",
    "Non-Model Library Plan V1",
    "Approved Library Import Intake Contract V1",
    "Self-Learning Mini Runner",
    "Bounded Self-Learning Scheduler",
    "Code Companion Intelligence Loop",
    "Code Companion Low-Risk Patch Runner",
    "Global Password-Gated Action Layer",
    "Protected Action Registry",
    "Core Continuity Map V1",
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


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_plan() -> dict[str, object]:
    return json.loads(read(PLAN_JSON))


def check_files_exist() -> None:
    for path in [PLAN_JSON, PLAN_MD, SYSTEM_INTEGRATION, BUILDER, CORE_VERIFIER, CORE_JSON, CORE_MD]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path.relative_to(ROOT)))


def check_plan_content() -> None:
    plan = load_plan()
    md = read(PLAN_MD)
    require(plan.get("name") == "Engel Active Build Plan: Learning and Fixing V1", "plan name mismatch")
    require(plan.get("type") == "active_build_plan_learning_and_fixing", "plan type mismatch")
    statuses = plan.get("status")
    require(isinstance(statuses, list), "plan status list missing")
    for status in REQUIRED_STATUSES:
        require(status in statuses, "plan JSON missing status: " + status)
        require(status in md, "plan Markdown missing status: " + status)
    steps = plan.get("steps")
    require(isinstance(steps, list), "plan steps missing")
    require([str(step.get("step_id")) for step in steps] == EXPECTED_STEP_IDS, "plan steps are not in required order")
    for step in steps:
        for field in REQUIRED_STEP_FIELDS:
            require(field in step, f"step {step.get('step_id')} missing field: {field}")
        for field in ["required_inputs", "outputs", "protected_actions", "required_verifiers", "safety_boundary", "definition_of_done"]:
            require(isinstance(step.get(field), list) and step.get(field), f"step {step.get('step_id')} field must be non-empty list: {field}")
    for needle in [
        "Integrated Status + WSL Runtime Package Refresh",
        "Core Continuity update for packaged Integrated Status + WSL visibility",
        "Engel LLM and Python Library Intake Plan V1",
        "Engel Learning Job Queue V1",
        "Engel Self-Learning Run Controller V1",
        "Engel Fix Candidate Queue V1",
        "Engel Learning-to-Fix Cycle V1",
        "Package refresh for Learning/Fix controls",
        "Visibility work is now secondary",
        "Next work should enable bounded candidate learning and safe fix queues",
        "WSL supports local tooling only; it is not an AI model",
        "LLM/Python libraries feed learning, not trusted memory directly",
    ]:
        require(needle in md or needle in json.dumps(plan), "plan missing required explanation: " + needle)
    for boundary in [
        "NOT_AI_MODEL",
        "no model loading/inference during intake",
        "no pip/package install automation",
        "password required for write/apply/run",
        "contract required",
        "verifier required",
        "receipt required",
        "trusted memory still requires approval",
        "low-risk patch apply remains narrow",
    ]:
        require(boundary in md or boundary in json.dumps(plan), "plan missing boundary: " + boundary)
    related = plan.get("related_nodes")
    require(isinstance(related, list), "related nodes missing")
    for node in REQUIRED_RELATED_NODES:
        require(node in related, "related node missing: " + node)
    safety = plan.get("safety_boundary")
    require(isinstance(safety, dict), "safety boundary map missing")
    for key in [
        "provider_calls_by_default",
        "network_by_default",
        "browser_by_default",
        "model_runtime_by_default",
        "trusted_memory_write_by_default",
        "source_mutation_by_default",
        "patch_apply_by_default",
        "unbounded_background_worker",
        "startup_autorun_by_default",
    ]:
        require(safety.get(key) is False, "plan safety flag must be false: " + key)


def check_system_integration() -> None:
    source = read(SYSTEM_INTEGRATION)
    for needle in [
        "active_build_plan_learning_and_fixing",
        "Engel Active Build Plan: Learning and Fixing V1",
        "Integrated Status + WSL Runtime Package Refresh",
        "LLM Library and Python Library Intake",
        "Learning Job Queue / Self-Learning Run Controller / Fix Candidate Queue",
        "Next work should enable bounded candidate learning and safe fix queues",
    ]:
        require(needle in source, "System Integration missing active plan text: " + needle)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "System Integration imports forbidden package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "System Integration imports forbidden package: " + node.module)
        elif isinstance(node, ast.While):
            raise CheckFailure("System Integration contains while loop")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_system_integration_status", SYSTEM_INTEGRATION)
    require(spec is not None and spec.loader is not None, "could not load System Integration module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_system_integration_status"] = module
    spec.loader.exec_module(module)
    payload = module.integration_summary()
    systems = payload.get("systems", [])
    active = next((system for system in systems if system.get("system_id") == "active_build_plan_learning_and_fixing"), None)
    require(isinstance(active, dict), "System Integration payload missing active build plan")
    rendered = module.render_status()
    require("Engel Active Build Plan: Learning and Fixing V1" in rendered, "rendered status missing active build plan")
    require("Next work should enable bounded candidate learning and safe fix queues" in rendered, "rendered status missing learning/fixing next work")


def check_core_continuity() -> None:
    data = json.loads(read(CORE_JSON))
    md = read(CORE_MD)
    node = data.get("engel_active_build_plan_learning_and_fixing_v1")
    require(isinstance(node, dict), "Core Continuity active build plan node missing")
    require(node.get("type") == "active_build_plan_learning_and_fixing", "Core Continuity active build plan type mismatch")
    for status in [
        "ACTIVE_BUILD_PLAN",
        "LEARNING_AND_FIXING_PATH",
        "LLM_LIBRARY_NEXT",
        "PYTHON_LIBRARY_NEXT",
        "LEARNING_JOB_QUEUE_NEXT",
        "SELF_LEARNING_RUN_CONTROLLER_NEXT",
        "FIX_CANDIDATE_QUEUE_NEXT",
        "LEARNING_TO_FIX_CYCLE_NEXT",
        "PASSWORD_GATE_REQUIRED_FOR_WRITE_APPLY_RUN",
        "VERIFIERS_REQUIRED",
        "RECEIPTS_REQUIRED",
    ]:
        require(status in node.get("status", []), "Core Continuity node missing status: " + status)
        require(status in md, "Core Continuity Markdown missing status: " + status)
    require(len(node.get("steps", [])) == 8, "Core Continuity node must include 8 steps")
    for step_id in EXPECTED_STEP_IDS:
        require(any(step.get("step_id") == step_id for step in node.get("steps", [])), "Core Continuity node missing step: " + step_id)
    for related in REQUIRED_RELATED_NODES:
        require(related in node.get("related_nodes", []), "Core Continuity node missing related node: " + related)
    for needle in [
        "Engel Active Build Plan Learning and Fixing V1",
        "Visibility work is now secondary",
        "bounded candidate learning and safe fix queues",
        "WSL supports local tooling only",
        "LLM/Python libraries feed learning, not trusted memory directly",
    ]:
        require(needle in md, "Core Continuity Markdown missing active build plan text: " + needle)


def check_report_if_present() -> None:
    if not REPORT.exists():
        return
    text = read(REPORT)
    for needle in [
        "files read first",
        "files created",
        "files updated",
        "active build plan summary",
        "8 ordered steps",
        "System Integration update",
        "Core Continuity update",
        "verification results",
        "smoke results",
        "safety scan result",
        "does not package yet",
        "no provider/network/browser/model/trusted-memory/source-mutation/patch-apply/background-worker/startup behavior was added",
        "final process sweep",
        "git status",
    ]:
        require(needle in text, "report missing required section/text: " + needle)


def main() -> int:
    try:
        check_files_exist()
        check_plan_content()
        check_system_integration()
        check_core_continuity()
        check_report_if_present()
    except CheckFailure as exc:
        print("FAIL:", exc)
        return 1
    print("Engel active build plan learning/fixing verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
