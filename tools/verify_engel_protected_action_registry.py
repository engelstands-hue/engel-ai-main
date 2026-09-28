from __future__ import annotations

import ast
import importlib.util
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "engel_protected_action_registry.py"
REGISTRY_JSON = ROOT / "memory" / "ENGEL_PROTECTED_ACTION_REGISTRY_V1.json"
REGISTRY_MD = ROOT / "memory" / "ENGEL_PROTECTED_ACTION_REGISTRY_V1.md"
VERIFIER = ROOT / "tools" / "verify_engel_protected_action_registry.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_GLOBAL_PASSWORD_GATED_ACTION_LAYER_V1.md"

REQUIRED_CATEGORIES = [
    "Engel AI / Learning",
    "Memory Promotion",
    "Low-Risk Self-Fix",
    "Code Companion",
    "Verifier / Safety",
    "Packaging / Live App",
    "Provider / Browser / Model",
    "Background / Startup",
    "Password / Permission System",
]

REQUIRED_ACTIONS = [
    "run_bounded_self_learning_scheduler",
    "run_daily_cycle",
    "run_daily_cycle_with_learning_jobs",
    "create_learning_job_draft",
    "write_learning_job_draft",
    "queue_learning_job",
    "validate_learning_job",
    "list_learning_jobs",
    "self_learning_run_controller_status",
    "self_learning_run_controller_dry_run",
    "self_learning_run_controller_run_once",
    "self_learning_run_controller_list_receipts",
    "enable_research_toggle_overnight_worker",
    "disable_research_toggle_overnight_worker",
    "run_research_toggle_worker_dry_run",
    "run_research_toggle_worker_once",
    "run_research_toggle_worker_overnight",
    "research_toggle_worker_kill_switch",
    "generate_research_note_write",
    "extract_lesson_candidate_write",
    "create_memory_candidate_proposal_write",
    "promote_memory_candidate",
    "enable_trusted_memory_target",
    "change_memory_promotion_contract",
    "write_trusted_memory",
    "run_low_risk_self_fix_dry_run",
    "run_low_risk_self_fix_apply",
    "view_self_fix_receipts",
    "clear_stale_pid_file",
    "run_code_companion_candidate_finder_write",
    "create_patch_candidate_write",
    "create_verifier_plan_write",
    "run_code_companion_low_risk_patch_dry_run",
    "run_code_companion_low_risk_patch_apply",
    "view_code_companion_patch_receipts",
    "run_verifier_stack",
    "update_verifier_candidate",
    "apply_verifier_update",
    "change_authority_hierarchy",
    "change_prompt_injection_guard",
    "change_untrusted_content_guard",
    "package_refresh",
    "live_exe_promotion",
    "package_smoke",
    "live_process_cleanup",
    "enable_provider_calls",
    "enable_network",
    "enable_browser",
    "enable_model_runtime",
    "run_local_model_inference",
    "start_background_worker",
    "enable_startup_autorun",
    "run_scheduled_cycle",
    "remote_queen_worker_activation",
    "configure_global_password_gate",
    "change_global_password_gate",
    "view_protected_action_registry",
    "update_protected_action_registry",
]

REQUIRED_FIELDS = [
    "action_id",
    "display_name",
    "category",
    "risk_level",
    "password_required",
    "approval_token_required",
    "contract_required",
    "verifier_required",
    "receipt_required",
    "dry_run_required_first",
    "allowed_in_gui",
    "allowed_in_cli",
    "current_state",
    "blocked_reason",
    "required_contracts",
    "required_verifiers",
    "required_receipt_folder",
    "safety_boundary",
    "forbidden_without_extra_approval",
    "notes",
]

BLOCKED_ACTIONS = [
    "enable_provider_calls",
    "enable_network",
    "enable_browser",
    "enable_model_runtime",
    "run_local_model_inference",
    "start_background_worker",
    "enable_startup_autorun",
    "remote_queen_worker_activation",
    "package_refresh",
    "live_exe_promotion",
    "change_authority_hierarchy",
    "change_prompt_injection_guard",
    "change_untrusted_content_guard",
    "update_protected_action_registry",
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
    "chromadb",
    "faiss",
    "llama",
    "ollama",
}


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_registry():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_protected_action_registry", REGISTRY)
    require(spec is not None and spec.loader is not None, "could not load protected action registry")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_protected_action_registry"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [REGISTRY, REGISTRY_JSON, REGISTRY_MD, VERIFIER]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path.relative_to(ROOT)))


def check_required_text() -> None:
    combined = read(REGISTRY) + "\n" + read(REGISTRY_JSON) + "\n" + read(REGISTRY_MD)
    for needle in [
        "PROTECTED_ACTION_REGISTRY",
        "STRICT_ACTION_ALLOWLIST",
        "CANONICALIZE_BEFORE_VALIDATE",
        "ACTION_SPECIFIC_CONTRACTS_STILL_REQUIRED",
        "AUTHORITY_HIERARCHY_STILL_REQUIRED",
        "GUARDS_STILL_REQUIRED",
        "BLOCKED_ACTIONS_REMAIN_BLOCKED",
        "--list",
        "--show",
        "--json",
        "Registry only; no action execution",
        "Blocked actions remain blocked even with password",
    ]:
        require(needle in combined, "protected action registry missing text: " + needle)
    for category in REQUIRED_CATEGORIES:
        require(category in combined, "protected action registry missing category: " + category)
    for action_id in REQUIRED_ACTIONS:
        require(action_id in combined, "protected action registry missing action: " + action_id)
    for field in REQUIRED_FIELDS:
        require(field in combined, "protected action registry missing field: " + field)


def check_ast_safety() -> None:
    tree = ast.parse(read(REGISTRY))
    forbidden_names = {"exec", "eval", "__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "registry imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "registry imports forbidden module: " + node.module)
        if isinstance(node, ast.While):
            raise CheckFailure("registry contains while loop")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in forbidden_names, "registry uses forbidden dynamic execution call: " + node.func.id)


def check_runtime_registry() -> None:
    registry = load_registry()
    actions = registry.list_actions()
    action_by_id = {str(action["action_id"]): action for action in actions}
    require(len(actions) >= len(REQUIRED_ACTIONS), "registry action count is too small")
    for action_id in REQUIRED_ACTIONS:
        require(action_id in action_by_id, "runtime registry missing action: " + action_id)
        action = action_by_id[action_id]
        for field in REQUIRED_FIELDS:
            require(field in action, "runtime action missing field: " + action_id + " / " + field)
    for blocked in BLOCKED_ACTIONS:
        action = action_by_id[blocked]
        require(action["risk_level"] == "blocked", "blocked action risk mismatch: " + blocked)
        require(action["current_state"] == "blocked", "blocked action state mismatch: " + blocked)
        require(bool(action["blocked_reason"]), "blocked action missing reason: " + blocked)
    summary = registry.registry_summary()
    require(summary["blocked_count"] >= len(BLOCKED_ACTIONS), "registry blocked count too small")
    require(summary["action_count"] == len(actions), "registry action count summary mismatch")

    out = io.StringIO()
    err = io.StringIO()
    require(registry.main(["--list"], stdout=out, stderr=err) == 0, "registry --list failed")
    require("run_code_companion_low_risk_patch_apply" in out.getvalue(), "registry list missing Code Companion apply action")

    out = io.StringIO()
    err = io.StringIO()
    require(registry.main(["--show", "enable_network"], stdout=out, stderr=err) == 0, "registry --show failed")
    require("risk_level: blocked" in out.getvalue(), "registry --show did not show blocked risk")

    out = io.StringIO()
    err = io.StringIO()
    require(registry.main(["--json"], stdout=out, stderr=err) == 0, "registry --json failed")
    payload = json.loads(out.getvalue())
    require(payload["summary"]["action_count"] == len(actions), "registry JSON action count mismatch")


def check_memory_registry() -> None:
    data = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    for action_id in REQUIRED_ACTIONS:
        require(action_id in data.get("action_ids", []), "registry memory JSON missing action id: " + action_id)
    for blocked in BLOCKED_ACTIONS:
        require(blocked in data.get("blocked_action_ids", []), "registry memory JSON missing blocked action: " + blocked)
    md = read(REGISTRY_MD)
    for category in REQUIRED_CATEGORIES:
        require(category in md, "registry Markdown missing category: " + category)


def check_report_if_present() -> None:
    if not REPORT.exists():
        return
    text = read(REPORT)
    for needle in [
        "protected action registry summary",
        "Engel AI protected actions",
        "Code Companion protected actions",
        "blocked actions remain blocked",
    ]:
        require(needle in text, "global password report missing registry text: " + needle)


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_ast_safety()
        check_runtime_registry()
        check_memory_registry()
        check_report_if_present()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel protected action registry verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
