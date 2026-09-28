from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_LEARNING_JOB_QUEUE_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_LEARNING_JOB_QUEUE_CONTRACT_V1.md"
MODULE = ROOT / "engel_learning_job_queue.py"
VERIFIER = ROOT / "tools" / "verify_engel_learning_job_queue.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_LEARNING_JOB_QUEUE_V1.md"
CORE_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
SYSTEM_INTEGRATION = ROOT / "engel_system_integration_status.py"
PROTECTED_REGISTRY = ROOT / "engel_protected_action_registry.py"

REQUIRED_STATUSES = [
    "LEARNING_JOB_QUEUE",
    "QUEUE_CONTRACT",
    "LOCAL_ONLY",
    "CANDIDATE_LEARNING_ONLY",
    "EXPLICIT_JOBS_ONLY",
    "APPROVED_LOCAL_SOURCES_ONLY",
    "REAL_SOURCE_REQUIRED",
    "SOURCE_FILE_MUST_EXIST",
    "NO_FAKE_QUEUE_RECORDS",
    "NO_FAKE_APPROVALS",
    "UNTRUSTED_OUTPUTS_ONLY",
    "NOT_TRUSTED_MEMORY",
    "PASSWORD_GATE_REQUIRED_FOR_WRITE_RUN",
    "PROTECTED_ACTION_REGISTRY_REQUIRED",
    "HUMAN_REVIEW_REQUIRED",
    "RECEIPTS_REQUIRED",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_LOADING",
    "NO_INFERENCE",
    "NO_TRAINING",
    "NO_WSL_EXECUTION",
    "NO_HERMES_EXECUTION",
    "NO_ANDROID_CONNECTION",
    "NO_AUTO_DISCOVERY",
    "NO_RECURSIVE_SCAN",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
]

REQUIRED_CLI = [
    "--status",
    "--list",
    "--validate-job",
    "--draft-job",
    "--write-draft",
    "--queue-job",
    "--password-prompt",
]

REQUIRED_JOB_FIELDS = [
    "job_id",
    "created_at",
    "created_by",
    "topic_id",
    "topic_title",
    "source_path",
    "source_type",
    "source_review_status",
    "source_approval_reference",
    "learning_goal",
    "allowed_outputs",
    "forbidden_outputs",
    "max_input_chars",
    "max_runtime_seconds",
    "priority",
    "status",
    "safety_boundary",
    "required_verifiers",
    "receipt_required",
    "human_review_required",
    "labels",
]

REQUIRED_JOB_STATUSES = [
    "draft",
    "queued",
    "hold_source_not_approved",
    "hold_missing_topic",
    "hold_invalid_path",
    "hold_source_missing",
    "hold_forbidden_source_type",
    "ready_for_dry_run",
    "ready_for_candidate_learning",
    "completed_candidate_outputs",
    "stopped_unsafe",
    "rejected",
]

ALLOWED_SOURCE_TYPES = [
    "approved_python_doc",
    "approved_coding_reference",
    "approved_math_reference",
    "approved_security_reference",
    "approved_engel_manual",
    "approved_report_or_receipt",
    "approved_local_research_note",
    "approved_android_worker_reference",
    "approved_wsl_runtime_note",
    "approved_library_material",
]

FORBIDDEN_SOURCE_TYPES = [
    "raw_unreviewed_download",
    "model_file",
    "WSL_distro_filesystem",
    "WSL_tar",
    "executable_file",
    "binary_file",
    "live_package_artifact",
    "staging_package_artifact",
    "trusted_memory_file",
    "source_code_file_unless_explicitly_approved",
    "URL",
    "external_drive_unapproved",
    "phone_file",
    "android_runtime_file",
]

REQUIRED_LABELS = [
    "CANDIDATE_LEARNING_ONLY",
    "UNTRUSTED_OUTPUTS_ONLY",
    "NOT_TRUSTED_MEMORY",
    "HUMAN_REVIEW_REQUIRED",
    "NO_AUTOMATION_TRIGGERED",
]

PROTECTED_ACTIONS = [
    "create_learning_job_draft",
    "write_learning_job_draft",
    "queue_learning_job",
    "validate_learning_job",
    "list_learning_jobs",
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
}


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
    spec = importlib.util.spec_from_file_location("engel_learning_job_queue", MODULE)
    require(spec is not None and spec.loader is not None, "could not load queue module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_learning_job_queue"] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [CONTRACT_JSON, CONTRACT_MD, MODULE, VERIFIER]:
        require(path.exists() and path.is_file(), "missing required file: " + str(path.relative_to(ROOT)))


def check_contract() -> None:
    data = json.loads(read(CONTRACT_JSON))
    md_text = read(CONTRACT_MD)
    require(data.get("contract_name") == "Engel Learning Job Queue Contract V1", "contract name mismatch")
    require(data.get("queue_name") == "Engel Learning Job Queue V1", "queue name mismatch")
    for status in REQUIRED_STATUSES:
        require(status in data.get("status", []), "contract JSON missing status: " + status)
        require(status in md_text, "contract Markdown missing status: " + status)
    for field in REQUIRED_JOB_FIELDS:
        require(field in data.get("job_fields", []), "contract missing job field: " + field)
        require(field in md_text, "contract Markdown missing job field: " + field)
    for status in REQUIRED_JOB_STATUSES:
        require(status in data.get("job_status_values", []), "contract missing job status: " + status)
    for source_type in ALLOWED_SOURCE_TYPES:
        require(source_type in data.get("allowed_source_types", []), "contract missing allowed source type: " + source_type)
    for source_type in FORBIDDEN_SOURCE_TYPES:
        require(source_type in data.get("forbidden_source_types", []), "contract missing forbidden source type: " + source_type)
    for label in REQUIRED_LABELS:
        require(label in data.get("job_labels", []), "contract missing label: " + label)
    for action in PROTECTED_ACTIONS:
        require(action in data.get("protected_action_ids", []), "contract missing protected action: " + action)
    for needle in [
        "reports\\learning_job_queue",
        "reports\\learning_job_queue_receipts",
        "WSL distro folders and WSL tar files are forbidden",
        "Model files are forbidden",
        "No learning job is run",
        "Real source file required",
        "No fake queue records",
        "fake approvals",
        "D:\\b.WorkSpace\\Engel App\\engel_library\\approved_library",
        "Self-Learning Run Controller V1",
    ]:
        require(needle in md_text or needle in json.dumps(data), "contract missing required text: " + needle)


def check_module_static() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for cli in REQUIRED_CLI:
        require(cli in source, "module missing CLI option: " + cli)
    for status in REQUIRED_STATUSES:
        require(status in source, "module missing status: " + status)
    for field in REQUIRED_JOB_FIELDS:
        require(field in source, "module missing job field: " + field)
    for status in REQUIRED_JOB_STATUSES:
        require(status in source, "module missing job status: " + status)
    for source_type in ALLOWED_SOURCE_TYPES + FORBIDDEN_SOURCE_TYPES:
        require(source_type in source, "module missing source type: " + source_type)
    for label in REQUIRED_LABELS:
        require(label in source, "module missing required label: " + label)
    for needle in [
        "resolve_source",
        "wildcard source discovery is forbidden",
        "source must be one explicit file, not a folder",
        "source path does not exist",
        "Android runtime and phone files are forbidden sources",
        "WSL distro folders and tar files are forbidden sources",
        "model/trusted-memory paths are forbidden sources",
        "live package artifacts are forbidden sources",
        "staging package artifacts are forbidden sources",
        "write_learning_job_draft",
        "Protected write requires --password-prompt",
        "Protected queue action requires --password-prompt",
    ]:
        require(needle in source, "module missing safety implementation text: " + needle)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "module imports forbidden package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "module imports forbidden package: " + node.module)
        elif isinstance(node, ast.While):
            raise CheckFailure("module contains while loop")


def check_module_runtime() -> None:
    module = load_module()
    status = module.render_status()
    listing = module.render_list()
    for status_label in REQUIRED_STATUSES:
        require(status_label in status, "status output missing label: " + status_label)
    require("Queue folder: reports\\learning_job_queue" in status, "status output missing queue folder")
    require("Receipt folder: reports\\learning_job_queue_receipts" in status, "status output missing receipt folder")
    require("No learning job queue files found." in listing or "Engel Learning Job Queue Files:" in listing, "list output unexpected")


def check_core_and_system_integration() -> None:
    if CORE_JSON.exists():
        data = json.loads(read(CORE_JSON))
        node = data.get("engel_learning_job_queue_v1")
        require(isinstance(node, dict), "Core Continuity missing Engel Learning Job Queue V1 node")
        require(node.get("type") == "learning_job_queue", "Core Continuity learning queue type mismatch")
        for status in [
            "LEARNING_JOB_QUEUE",
            "CANDIDATE_LEARNING_ONLY",
            "EXPLICIT_JOBS_ONLY",
            "APPROVED_LOCAL_SOURCES_ONLY",
            "REAL_SOURCE_REQUIRED",
            "NO_FAKE_QUEUE_RECORDS",
            "UNTRUSTED_OUTPUTS_ONLY",
            "NOT_TRUSTED_MEMORY",
            "PASSWORD_GATE_REQUIRED_FOR_WRITE_RUN",
            "RECEIPTS_REQUIRED",
            "NO_PROVIDER_CALLS",
            "NO_NETWORK",
            "NO_BROWSER",
            "NO_MODEL_LOADING",
            "NO_INFERENCE",
            "NO_TRUSTED_MEMORY_WRITE",
            "NO_SOURCE_MUTATION",
            "NO_PATCH_APPLY",
        ]:
            require(status in node.get("status", []), "Core Continuity queue node missing status: " + status)
    if SYSTEM_INTEGRATION.exists():
        text = read(SYSTEM_INTEGRATION)
        for needle in ["learning_job_queue", "Engel Learning Job Queue V1", "Self-Learning Run Controller V1"]:
            require(needle in text, "System Integration missing queue text: " + needle)
        require(
            "reports\\learning_job_queue" in text or "reports\\\\learning_job_queue" in text,
            "System Integration missing queue folder text",
        )


def check_protected_registry() -> None:
    if not PROTECTED_REGISTRY.exists():
        return
    text = read(PROTECTED_REGISTRY)
    for action in PROTECTED_ACTIONS:
        require(action in text, "Protected Action Registry missing queue action: " + action)


def main() -> int:
    try:
        check_files()
        check_contract()
        check_module_static()
        check_module_runtime()
        check_core_and_system_integration()
        check_protected_registry()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[OK] Engel Learning Job Queue V1 verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
