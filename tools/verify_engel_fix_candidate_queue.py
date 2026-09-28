from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_FIX_CANDIDATE_QUEUE_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_FIX_CANDIDATE_QUEUE_CONTRACT_V1.md"
MODULE = ROOT / "engel_fix_candidate_queue.py"
VERIFIER = ROOT / "tools" / "verify_engel_fix_candidate_queue.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_FIX_CANDIDATE_QUEUE_V1.md"
CORE_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
SYSTEM_INTEGRATION = ROOT / "engel_system_integration_status.py"

REQUIRED_STATUSES = [
    "FIX_CANDIDATE_QUEUE",
    "QUEUE_CONTRACT",
    "LOCAL_ONLY",
    "INERT_RECORDS_ONLY",
    "CANDIDATE_FIXES_ONLY",
    "EXPLICIT_CANDIDATES_ONLY",
    "UNTRUSTED_OUTPUTS_ONLY",
    "NOT_PATCHES",
    "NOT_APPLIED_CHANGES",
    "HUMAN_REVIEW_REQUIRED",
    "VERIFIER_REQUIRED",
    "PASSWORD_GATE_REQUIRED_FOR_WRITE",
    "PROTECTED_ACTION_REGISTRY_REQUIRED",
    "NO_PATCH_APPLY",
    "NO_SOURCE_MUTATION",
    "NO_ROUTE_MUTATION",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_LOADING",
    "NO_INFERENCE",
    "NO_TRAINING",
    "NO_WSL_EXECUTION",
    "NO_HERMES_EXECUTION",
    "NO_ANDROID_CONNECTION",
    "NO_PACKAGE_INSTALL",
    "NO_DEPENDENCY_DOWNLOAD",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
    "NO_AUTO_APPROVAL",
    "NO_FAKE_FIXES",
    "NO_FAKE_APPROVALS",
    "NO_FAKE_VERIFIER_RESULTS",
    "HERMES_APPROVED_FOR_LOCAL_TESTING_HUMAN_DRIVEN_ONLY",
]
REQUIRED_CLI = ["--status", "--list", "--validate-candidate", "--draft-candidate", "--write-draft", "--password-prompt"]
REQUIRED_FIELDS = ["fix_candidate_id", "source_path", "source_type", "proposed_fix_type", "target_files", "summary", "rationale", "risk_level", "required_verifiers", "approval_required", "warning_flags", "created_at", "status", "related_receipt"]
FORBIDDEN_IMPORTS = {"requests", "urllib", "socket", "webbrowser", "openai", "subprocess", "threading", "multiprocessing", "shutil", "glob", "os"}


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
    spec = importlib.util.spec_from_file_location("engel_fix_candidate_queue", MODULE)
    require(spec is not None and spec.loader is not None, "could not load fix candidate queue module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_fix_candidate_queue"] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [CONTRACT_JSON, CONTRACT_MD, MODULE, VERIFIER]:
        require(path.exists() and path.is_file(), "missing required file: " + str(path.relative_to(ROOT)))


def check_contract() -> None:
    data = json.loads(read(CONTRACT_JSON))
    md = read(CONTRACT_MD)
    require(data.get("queue_name") == "Engel Fix Candidate Queue V1", "queue name mismatch")
    for status in REQUIRED_STATUSES:
        require(status in data.get("status", []), "contract missing status: " + status)
        require(status in md, "contract markdown missing status: " + status)
    for field in REQUIRED_FIELDS:
        require(field in data.get("metadata_fields", []), "contract missing field: " + field)
        require(field in md, "contract markdown missing field: " + field)
    for state in ["draft", "discovered", "schema_validated", "needs_human_review", "verifier_required", "rejected", "approved_for_patch_review", "handed_to_code_companion", "archived"]:
        require(state in data.get("candidate_states", []), "contract missing state: " + state)
    require("applied" not in data.get("candidate_states", []), "contract must not create applied state")
    boundary = data.get("boundary", {})
    for key in ["apply_patches", "edit_source_files", "edit_routes", "edit_trusted_memory", "call_providers_network_browser_api", "call_wsl_hermes_android", "load_models", "run_inference", "train_models", "install_packages", "download_dependencies", "start_workers", "add_startup_autorun", "approve_candidates_automatically", "mark_candidates_as_applied", "create_fake_fixes", "create_fake_approvals", "create_fake_verifier_results"]:
        require(boundary.get(key) is False, "contract boundary must be false: " + key)


def check_module_static() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for cli in REQUIRED_CLI:
        require(cli in source, "module missing CLI: " + cli)
    for status in REQUIRED_STATUSES:
        require(status in source, "module missing status: " + status)
    for field in REQUIRED_FIELDS:
        require(field in source, "module missing metadata field: " + field)
    for needle in [
        "NO_PATCH_APPLY",
        "NO_SOURCE_MUTATION",
        "Fix candidates are not fixes",
        "Queueing is not applying",
        "this queue must not create applied status",
        "Protected write requires --password-prompt",
        "global_password_gate.prompt_and_require_action",
    ]:
        require(needle in source, "module missing boundary text: " + needle)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "module imports forbidden package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "module imports forbidden package: " + node.module)
        elif isinstance(node, ast.While):
            raise CheckFailure("module contains while loop")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            require(name not in {"eval", "exec", "__import__", "Popen", "system", "startfile", "rglob", "walk", "unlink", "rename", "remove"}, "module contains forbidden call: " + name)


def check_runtime() -> None:
    module = load_module()
    status = module.render_status()
    listing = module.render_list()
    for label in REQUIRED_STATUSES:
        require(label in status, "status missing label: " + label)
    require("Queue folder: reports\\fix_candidate_queue" in status, "status missing queue folder")
    require("No fix candidate queue files found." in listing or "Engel Fix Candidate Queue Files:" in listing, "list output invalid")
    flags = module.warning_flags_for_text("pip install x; disable verifier; apply patch now; Hermes Agent; delete receipts; api key")
    for flag in ["package_install", "verifier_disablement", "source_mutation_outside_protected_patch_flow", "wsl_android_hermes_runtime", "receipt_deletion", "provider_network_browser_api"]:
        require(flag in flags, "warning flag missing: " + flag)


def check_integration() -> None:
    if REPORT.exists():
        require("Engel Fix Candidate Queue V1" in read(REPORT), "report missing title")
    require(SYSTEM_INTEGRATION.exists(), "System Integration missing")
    system_text = read(SYSTEM_INTEGRATION)
    for needle in ["fix_candidate_queue", "engel_fix_candidate_queue.py", "tools\\\\verify_engel_fix_candidate_queue.py"]:
        require(needle in system_text, "System Integration missing: " + needle)
    require(CORE_JSON.exists(), "Core Continuity JSON missing")
    data = json.loads(read(CORE_JSON))
    node = data.get("engel_fix_candidate_queue_v1")
    require(isinstance(node, dict), "Core Continuity missing fix candidate queue node")
    require(node.get("type") == "fix_candidate_queue", "Core node type mismatch")
    for status in ["FIX_CANDIDATE_QUEUE", "INERT_RECORDS_ONLY", "NOT_PATCHES", "NO_PATCH_APPLY", "NO_SOURCE_MUTATION", "NO_ROUTE_MUTATION", "NO_TRUSTED_MEMORY_WRITE"]:
        require(status in node.get("status", []), "Core node missing status: " + status)
    safety = data.get("safety", {})
    for key in ["fix_candidate_queue_patch_apply_enabled_by_map", "fix_candidate_queue_source_mutation_enabled_by_map", "fix_candidate_queue_route_mutation_enabled_by_map", "fix_candidate_queue_trusted_memory_write_enabled_by_map", "fix_candidate_queue_provider_calls_enabled_by_map", "fix_candidate_queue_network_enabled_by_map", "fix_candidate_queue_browser_enabled_by_map", "fix_candidate_queue_model_loading_enabled_by_map", "fix_candidate_queue_background_worker_enabled_by_map", "fix_candidate_queue_startup_autorun_enabled_by_map"]:
        require(safety.get(key) is False, "Core safety flag should remain false: " + key)


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
    print("[PASS] Engel Fix Candidate Queue V1 verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
