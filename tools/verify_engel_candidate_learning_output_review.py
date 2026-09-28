from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_CANDIDATE_LEARNING_OUTPUT_REVIEW_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_CANDIDATE_LEARNING_OUTPUT_REVIEW_CONTRACT_V1.md"
MODULE = ROOT / "engel_candidate_learning_output_review.py"
VERIFIER = ROOT / "tools" / "verify_engel_candidate_learning_output_review.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CANDIDATE_LEARNING_OUTPUT_REVIEW_V1.md"
CORE_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
SYSTEM_INTEGRATION = ROOT / "engel_system_integration_status.py"

REQUIRED_STATUSES = [
    "CANDIDATE_LEARNING_OUTPUT_REVIEW",
    "READ_ONLY_REVIEW_LAYER",
    "LOCAL_ONLY",
    "EXISTING_OUTPUTS_ONLY",
    "HONEST_EMPTY_STATE",
    "UNTRUSTED_OUTPUTS_ONLY",
    "CANDIDATE_ONLY",
    "NOT_TRUSTED_MEMORY",
    "HUMAN_REVIEW_REQUIRED",
    "NO_APPROVAL",
    "NO_PROMOTION",
    "NO_APPLY",
    "NO_RUN_JOBS",
    "NO_SOURCE_MUTATION",
    "NO_ROUTE_MUTATION",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_MODEL_LOADING",
    "NO_INFERENCE",
    "NO_TRAINING",
    "NO_WSL_EXECUTION",
    "NO_HERMES_EXECUTION",
    "NO_ANDROID_CONNECTION",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
    "NO_FAKE_LIVE_DATA",
    "NO_FAKE_APPROVALS",
    "HERMES_APPROVED_FOR_LOCAL_TESTING_HUMAN_DRIVEN_ONLY",
]

REVIEW_STATES = [
    "found_untrusted",
    "found_candidate",
    "schema_validated",
    "needs_human_review",
    "verifier_pending",
    "verifier_failed",
    "rejected",
    "archived",
    "unknown_untrusted",
]

FORBIDDEN_IMPORTS = {"requests", "urllib", "socket", "webbrowser", "openai", "subprocess", "threading", "multiprocessing", "shutil", "glob", "os"}
FORBIDDEN_CALL_NAMES = {"eval", "exec", "__import__"}
FORBIDDEN_ATTRS = {"write_text", "write_bytes", "unlink", "remove", "rename", "replace", "mkdir", "rmdir", "rglob", "glob", "walk"}
FORBIDDEN_PUBLIC_WORDS = ["approve_candidate", "promote_memory", "apply_fix", "run_job", "load_model", "run_inference"]


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
    spec = importlib.util.spec_from_file_location("engel_candidate_learning_output_review", MODULE)
    require(spec is not None and spec.loader is not None, "could not load review module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_candidate_learning_output_review"] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [CONTRACT_JSON, CONTRACT_MD, MODULE, VERIFIER]:
        require(path.exists() and path.is_file(), "missing file: " + str(path.relative_to(ROOT)))


def check_contract() -> None:
    data = json.loads(read(CONTRACT_JSON))
    md = read(CONTRACT_MD)
    require(data.get("contract_name") == "Engel Candidate Learning Output Review Contract V1", "contract name mismatch")
    for status in REQUIRED_STATUSES:
        require(status in data.get("status", []), "contract JSON missing status: " + status)
        require(status in md, "contract Markdown missing status: " + status)
    for state in REVIEW_STATES:
        require(state in data.get("review_states", []), "contract missing review state: " + state)
        require(state in md, "contract Markdown missing review state: " + state)
    for field in [
        "item_id",
        "path",
        "file_type",
        "category",
        "source_folder",
        "modified_time",
        "size_bytes",
        "sha256",
        "candidate_type",
        "review_state",
        "warning_flags",
    ]:
        require(field in data.get("metadata_fields", []), "contract missing metadata field: " + field)
    for flag in [
        "shell_command_reference",
        "python_code_block",
        "trusted_memory_write_instruction",
        "provider_network_api_instruction",
        "package_or_model_download_instruction",
        "remote_queen_control_instruction",
        "hermes_reference",
        "prompt_injection_language",
        "bypass_verifier_guard_approval_language",
    ]:
        require(flag in data.get("warning_flags", []), "contract missing warning flag: " + flag)
    boundaries = data.get("safety_boundary", {})
    for key in [
        "promote_memory",
        "approve_candidates",
        "apply_fixes",
        "mutate_source",
        "mutate_routes",
        "write_trusted_memory",
        "run_learning_jobs",
        "execute_candidate_code",
        "load_models",
        "run_inference",
        "train_models",
        "call_wsl",
        "run_hermes",
        "start_android_runtime",
        "call_providers_network_browser_api",
        "start_background_workers",
        "add_startup_autorun",
        "create_fake_live_data",
        "create_fake_approvals",
    ]:
        require(boundaries.get(key) is False, "contract boundary must be false: " + key)


def check_module_static() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for cli in ["--status", "--json", "--list", "--category"]:
        require(cli in source, "module missing CLI: " + cli)
    for status in [
        "CANDIDATE_LEARNING_OUTPUT_REVIEW",
        "READ_ONLY_REVIEW_LAYER",
        "EXISTING_OUTPUTS_ONLY",
        "HONEST_EMPTY_STATE",
        "NO_APPROVAL",
        "NO_PROMOTION",
        "NO_APPLY",
        "NO_RUN_JOBS",
    ]:
        require(status in source, "module missing status text: " + status)
    for forbidden in FORBIDDEN_PUBLIC_WORDS:
        require(forbidden not in source, "module exposes forbidden behavior word: " + forbidden)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "module imports forbidden package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "module imports forbidden package: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                require(func.id not in FORBIDDEN_CALL_NAMES, "module uses forbidden dynamic call: " + func.id)
            elif isinstance(func, ast.Attribute):
                if func.attr in {"read_text", "read_bytes", "open", "iterdir", "exists", "is_dir", "is_file", "stat", "replace"}:
                    continue
                require(func.attr not in FORBIDDEN_ATTRS, "module contains forbidden call: " + func.attr)
        elif isinstance(node, ast.While):
            raise CheckFailure("module contains while loop")


def check_runtime() -> None:
    module = load_module()
    status = module.render_status()
    payload = module.review_summary()
    listing = module.render_list()
    require(isinstance(payload, dict), "review summary did not return dict")
    require("items" in payload and isinstance(payload["items"], list), "review summary missing item list")
    require("empty_state" in payload, "review summary missing honest empty state")
    require("This is a review window, not an approval system." in status, "status missing review-window boundary")
    require("No candidate learning output files found" in listing or "Candidate learning output files:" in listing, "list output invalid")
    sample_path = ROOT / "reports" / "codex_bridge" / "ENGEL_OUTSIDE_AI_BOUNDARY_RULE_V1.md"
    if sample_path.exists():
        flags = module.warning_flags(sample_path)
        require("hermes_reference" in flags, "warning flags should detect Hermes references in sample report")


def check_integration() -> None:
    if REPORT.exists():
        require("Engel Candidate Learning Output Review V1" in read(REPORT), "report missing title")
    require(SYSTEM_INTEGRATION.exists(), "System Integration missing")
    system_text = read(SYSTEM_INTEGRATION)
    for needle in [
        "candidate_learning_output_review",
        "engel_candidate_learning_output_review.py",
        "tools\\verify_engel_candidate_learning_output_review.py",
        "NO_APPROVAL",
        "NO_PROMOTION",
        "NO_APPLY",
        "NO_RUN_JOBS",
    ]:
        require(needle in system_text or needle.replace("\\", "\\\\") in system_text, "System Integration missing: " + needle)
    require(CORE_JSON.exists(), "Core Continuity JSON missing")
    data = json.loads(read(CORE_JSON))
    node = data.get("engel_candidate_learning_output_review_v1")
    require(isinstance(node, dict), "Core Continuity missing Candidate Learning Output Review node")
    require(node.get("type") == "candidate_learning_output_review", "Core node type mismatch")
    for status in ["CANDIDATE_LEARNING_OUTPUT_REVIEW", "READ_ONLY_REVIEW_LAYER", "NO_APPROVAL", "NO_PROMOTION", "NO_APPLY", "NO_RUN_JOBS"]:
        require(status in node.get("status", []), "Core node missing status: " + status)
    for key in [
        "candidate_learning_output_review_approval_enabled_by_map",
        "candidate_learning_output_review_promotion_enabled_by_map",
        "candidate_learning_output_review_apply_enabled_by_map",
        "candidate_learning_output_review_run_jobs_enabled_by_map",
        "candidate_learning_output_review_trusted_memory_write_enabled_by_map",
        "candidate_learning_output_review_source_mutation_enabled_by_map",
        "candidate_learning_output_review_route_mutation_enabled_by_map",
        "candidate_learning_output_review_model_loading_enabled_by_map",
        "candidate_learning_output_review_inference_enabled_by_map",
        "candidate_learning_output_review_network_enabled_by_map",
        "candidate_learning_output_review_background_worker_enabled_by_map",
        "candidate_learning_output_review_startup_autorun_enabled_by_map",
    ]:
        require(data.get("safety", {}).get(key) is False, "Core safety flag should remain false: " + key)


def main() -> int:
    checks = [
        ("files", check_files),
        ("contract", check_contract),
        ("module_static", check_module_static),
        ("runtime", check_runtime),
        ("integration", check_integration),
    ]
    failures: list[str] = []
    for name, check in checks:
        try:
            check()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(name + ": " + str(exc))
            print("FAIL " + name + ": " + str(exc))
    if failures:
        print("\nEngel Candidate Learning Output Review verifier FAILED")
        return 1
    print("\nEngel Candidate Learning Output Review verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
