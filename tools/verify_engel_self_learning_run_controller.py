from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_SELF_LEARNING_RUN_CONTROLLER_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_SELF_LEARNING_RUN_CONTROLLER_CONTRACT_V1.md"
MODULE = ROOT / "engel_self_learning_run_controller.py"
VERIFIER = ROOT / "tools" / "verify_engel_self_learning_run_controller.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_SELF_LEARNING_RUN_CONTROLLER_V1.md"
CORE_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
SYSTEM_INTEGRATION = ROOT / "engel_system_integration_status.py"
PROTECTED_REGISTRY = ROOT / "engel_protected_action_registry.py"

REQUIRED_STATUSES = [
    "SELF_LEARNING_RUN_CONTROLLER",
    "BOUNDED_LEARNING_RUNNER",
    "REAL_QUEUE_JOBS_ONLY",
    "REAL_SOURCE_REQUIRED",
    "SOURCE_FILE_MUST_EXIST",
    "CANDIDATE_LEARNING_ONLY",
    "UNTRUSTED_OUTPUTS_ONLY",
    "NOT_TRUSTED_MEMORY",
    "PASSWORD_GATE_REQUIRED_FOR_RUN",
    "PROTECTED_ACTION_REGISTRY_REQUIRED",
    "RECEIPTS_REQUIRED",
    "HUMAN_REVIEW_REQUIRED",
    "NO_FAKE_LEARNING_OUTPUTS",
    "NO_FAKE_QUEUE_RECORDS",
    "NO_MODEL_LOADING",
    "NO_INFERENCE",
    "NO_TRAINING",
    "NO_WSL_EXECUTION",
    "NO_HERMES_EXECUTION",
    "NO_ANDROID_CONNECTION",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
]

REQUIRED_CLI = ["--status", "--dry-run", "--run-once", "--job", "--password-prompt", "--summary", "--list-receipts"]

RUN_LIMITS = [
    "one job per run in V1",
    "explicit job file only",
    "job source file must exist",
    "job source must pass Learning Job Queue validation",
    "max input chars from job",
    "max runtime seconds from job",
    "no folder recursion",
    "no wildcard source discovery",
    "no URL fetch",
    "no model loading",
    "no WSL/Hermes/Android runtime",
    "no trusted memory write",
    "no source mutation",
    "no patch apply",
]

PIPELINE_STAGES = [
    "validate_learning_job_queue_job",
    "read_bounded_source_text",
    "generate_untrusted_research_note",
    "extract_lesson_candidate",
    "create_research_memory_candidate_proposal",
    "create_self_learning_run_receipt",
    "create_readable_run_summary",
    "leave_outputs_candidate_only",
]

OUTPUT_LABELS = ["UNTRUSTED", "CANDIDATE_ONLY", "NOT_TRUSTED_MEMORY", "HUMAN_REVIEW_REQUIRED", "NO_AUTOMATION_TRIGGERED"]

RECEIPT_FIELDS = [
    "receipt_id",
    "run_id",
    "created_at",
    "job_id",
    "topic_id",
    "source_path",
    "source_type",
    "source_review_status",
    "source_hash_if_computed",
    "outputs_created",
    "research_note_path",
    "lesson_candidate_path",
    "memory_candidate_proposal_path",
    "run_summary_path",
    "password_gate_checked",
    "protected_action_id",
    "max_input_chars",
    "max_runtime_seconds",
    "safety_boundary",
    "no_trusted_memory_write",
    "no_source_mutation",
    "no_patch_apply",
    "no_model_loading",
    "no_inference",
    "no_training",
    "no_wsl_execution",
    "no_hermes_execution",
    "no_android_connection",
    "no_provider_network_browser",
    "human_review_required",
    "final_status",
]

PROTECTED_ACTIONS = [
    "self_learning_run_controller_status",
    "self_learning_run_controller_dry_run",
    "self_learning_run_controller_run_once",
    "self_learning_run_controller_list_receipts",
]

FORBIDDEN_IMPORTS = {"requests", "urllib", "socket", "webbrowser", "openai", "subprocess", "threading", "multiprocessing"}


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
    spec = importlib.util.spec_from_file_location("engel_self_learning_run_controller", MODULE)
    require(spec is not None and spec.loader is not None, "could not load controller module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_self_learning_run_controller"] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [CONTRACT_JSON, CONTRACT_MD, MODULE, VERIFIER]:
        require(path.exists() and path.is_file(), "missing file: " + str(path.relative_to(ROOT)))


def check_contract() -> None:
    data = json.loads(read(CONTRACT_JSON))
    md = read(CONTRACT_MD)
    require(data.get("contract_name") == "Engel Self-Learning Run Controller Contract V1", "contract name mismatch")
    for status in REQUIRED_STATUSES:
        require(status in data.get("status", []), "contract JSON missing status: " + status)
        require(status in md, "contract Markdown missing status: " + status)
    for limit in RUN_LIMITS:
        require(limit in data.get("run_limits", []), "contract missing run limit: " + limit)
    for stage in PIPELINE_STAGES:
        require(stage in data.get("pipeline", []), "contract missing pipeline stage: " + stage)
    for label in OUTPUT_LABELS:
        require(label in data.get("output_labels", []), "contract missing output label: " + label)
    for field in RECEIPT_FIELDS:
        require(field in data.get("receipt_fields", []), "contract missing receipt field: " + field)
    for action in PROTECTED_ACTIONS:
        require(action in data.get("protected_action_ids", []), "contract missing protected action: " + action)
    for needle in [
        "Learning Job Queue -> Untrusted Research Note Generator",
        "No trusted memory write",
        "Fix Candidate Queue V1",
        "fake learning outputs",
    ]:
        require(needle in md or needle in json.dumps(data), "contract missing required text: " + needle)


def check_module_static() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for cli in REQUIRED_CLI:
        require(cli in source, "module missing CLI option: " + cli)
    for status in REQUIRED_STATUSES:
        require(status in source, "module missing status: " + status)
    for limit in RUN_LIMITS:
        require(limit in source, "module missing run limit: " + limit)
    for stage in PIPELINE_STAGES:
        require(stage in source, "module missing pipeline stage: " + stage)
    for label in OUTPUT_LABELS:
        require(label in source, "module missing output label: " + label)
    for field in RECEIPT_FIELDS:
        require(field in source, "module missing receipt field: " + field)
    for needle in [
        "learning_queue.load_job_json",
        "learning_queue.resolve_source",
        "require_runnable_job",
        "source file must exist",
        "NO_FAKE_LEARNING_OUTPUTS",
        "no_trusted_memory_write",
        "no_source_mutation",
        "no_patch_apply",
        "no_model_loading",
        "no_inference",
        "no_training",
        "no_wsl_execution",
        "no_hermes_execution",
        "no_android_connection",
        "no_provider_network_browser",
        "note_generator.build_research_note",
        "lesson_extractor.build_lesson_candidate",
        "memory_proposal.build_memory_candidate_proposal",
    ]:
        require(needle in source, "module missing implementation/boundary text: " + needle)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "module imports forbidden package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "module imports forbidden package: " + node.module)
        elif isinstance(node, ast.While):
            raise CheckFailure("module contains while loop")


def check_runtime() -> None:
    module = load_module()
    status = module.render_status()
    for label in REQUIRED_STATUSES:
        require(label in status, "status output missing: " + label)
    require("Receipt folder: reports\\self_learning_run_receipts" in status, "status missing receipt folder")
    require("Summary folder: reports\\self_learning_run_summaries" in status, "status missing summary folder")


def check_integration() -> None:
    if CORE_JSON.exists():
        data = json.loads(read(CORE_JSON))
        node = data.get("engel_self_learning_run_controller_v1")
        require(isinstance(node, dict), "Core Continuity missing self-learning run controller node")
        require(node.get("type") == "self_learning_run_controller", "Core Continuity node type mismatch")
        for status in [
            "SELF_LEARNING_RUN_CONTROLLER",
            "BOUNDED_LEARNING_RUNNER",
            "REAL_QUEUE_JOBS_ONLY",
            "REAL_SOURCE_REQUIRED",
            "CANDIDATE_LEARNING_ONLY",
            "UNTRUSTED_OUTPUTS_ONLY",
            "NOT_TRUSTED_MEMORY",
            "PASSWORD_GATE_REQUIRED_FOR_RUN",
            "RECEIPTS_REQUIRED",
            "NO_MODEL_LOADING",
            "NO_INFERENCE",
            "NO_TRUSTED_MEMORY_WRITE",
            "NO_SOURCE_MUTATION",
            "NO_PATCH_APPLY",
        ]:
            require(status in node.get("status", []), "Core Continuity node missing status: " + status)
    if SYSTEM_INTEGRATION.exists():
        text = read(SYSTEM_INTEGRATION)
        for needle in ["self_learning_run_controller", "Self-Learning Run Controller V1", "reports\\self_learning_run_receipts", "Fix Candidate Queue V1"]:
            require(needle in text or needle.replace("\\", "\\\\") in text, "System Integration missing: " + needle)
    if PROTECTED_REGISTRY.exists():
        text = read(PROTECTED_REGISTRY)
        for action in PROTECTED_ACTIONS:
            require(action in text, "Protected Action Registry missing action: " + action)


def main() -> int:
    try:
        check_files()
        check_contract()
        check_module_static()
        check_runtime()
        check_integration()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[OK] Engel Self-Learning Run Controller V1 verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
