from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_DAILY_CYCLE_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_DAILY_CYCLE_CONTRACT_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_DAILY_CYCLE_CONTRACT_V1.md"
THIS_FILE = ROOT / "tools" / "verify_engel_daily_cycle_contract.py"

REQUIRED_STATUSES = [
    "CONTRACT_ONLY",
    "DAILY_CYCLE_POLICY",
    "FOREGROUND_COMMAND_ONLY",
    "BOUNDED_RUN_ONLY",
    "RECEIPT_REQUIRED",
    "NO_STARTUP_AUTORUN",
    "NO_ENDLESS_LOOP",
    "NO_BACKGROUND_WORKER",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_PACKAGE_REFRESH",
    "NO_UNAPPROVED_MEMORY_WRITE",
    "NO_UNAPPROVED_SOURCE_MUTATION",
]

DAILY_CYCLE_STEPS = [
    "check AI growth status",
    "run selected status surfaces",
    "run verifier stack",
    "optionally run bounded self-learning scheduler",
    "show candidate review dashboard",
    "check low-risk self-fix opportunities",
    "run low-risk self-fix dry-run first",
    "apply only pre-approved low-risk fixes if runner contract allows",
    "create receipts",
    "show research-to-fix summary",
    "stop",
]

BOUNDARIES = [
    "max one daily cycle per command invocation",
    "no persistent process",
    "no startup autorun",
    "no hidden background worker",
    "no provider/network/browser",
    "no model runtime",
    "no package refresh",
    "no high-risk self-fix",
    "no unapproved memory promotion",
    "no source mutation except approved low-risk self-fix classes",
    "all outputs receipt-based",
]

FUTURE_CLI = [
    "python engel_daily_cycle_runner.py --dry-run",
    "python engel_daily_cycle_runner.py --run",
]

RECEIPT_FIELDS = [
    "daily_cycle_run_id",
    "started_at",
    "completed_at",
    "mode",
    "status_checks_run",
    "verifiers_run",
    "learning_jobs_run",
    "candidates_seen",
    "self_fix_dry_runs",
    "self_fixes_applied",
    "receipts_created",
    "stopped",
    "stop_reason",
    "safety_boundary",
    "final_summary",
]

RUNNER_CANDIDATES = [
    ROOT / "engel_daily_cycle_runner.py",
    ROOT / "tools" / "engel_daily_cycle_runner.py",
    ROOT / "tools" / "run_engel_daily_cycle.py",
]
IMPLEMENTED_RUNNER = ROOT / "engel_daily_cycle_runner.py"
IMPLEMENTED_RUNNER_VERIFIER = ROOT / "tools" / "verify_engel_daily_cycle_runner.py"
IMPLEMENTED_RUNNER_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_DAILY_CYCLE_RUNNER_V1.md"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    require(path.exists(), "missing required file: " + str(path.relative_to(ROOT)))
    require(path.is_file(), "required path is not a file: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def normalize(text: str) -> str:
    return " ".join(
        text.lower()
        .replace("`", "")
        .replace("\\", "/")
        .replace("-", " ")
        .replace("_", " ")
        .split()
    )


def require_text(combined: str, needle: str, label: str) -> None:
    require(normalize(needle) in normalize(combined), label + " missing expected text: " + needle)


def load_contract() -> tuple[dict, str]:
    payload = json.loads(read(CONTRACT_JSON))
    combined = json.dumps(payload, sort_keys=True) + "\n" + read(CONTRACT_MD) + "\n" + read(REPORT)
    return payload, combined


def check_files() -> None:
    read(CONTRACT_JSON)
    read(CONTRACT_MD)
    read(REPORT)


def check_json_identity(payload: dict) -> None:
    require(payload.get("schema_name") == "engel_daily_cycle_contract_v1", "schema_name mismatch")
    require(payload.get("schema_version") == "1.0", "schema_version mismatch")
    require(payload.get("id") == "engel_daily_cycle_contract_v1", "id mismatch")
    require(payload.get("type") == "daily_cycle_contract", "type mismatch")


def check_statuses(payload: dict, combined: str) -> None:
    statuses = payload.get("status", [])
    require(isinstance(statuses, list), "status must be a list")
    for status in REQUIRED_STATUSES:
        require(status in statuses, "missing JSON status: " + status)
        require_text(combined, status, "status")


def check_cycle_steps(payload: dict, combined: str) -> None:
    steps = payload.get("required_daily_cycle_steps", [])
    require(steps == DAILY_CYCLE_STEPS, "daily cycle steps mismatch")
    for step in DAILY_CYCLE_STEPS:
        require_text(combined, step, "daily cycle step")


def check_boundaries(payload: dict, combined: str) -> None:
    boundaries = payload.get("required_boundaries", [])
    for boundary in BOUNDARIES:
        require(boundary in boundaries, "missing JSON boundary: " + boundary)
        require_text(combined, boundary, "boundary")

    scope = payload.get("contract_scope", {})
    for key in [
        "contract_only",
        "policy_only",
        "runner_not_implemented",
        "no_daily_cycle_runner_exists_in_this_step",
        "does_not_start_at_startup",
        "does_not_start_background_worker",
        "does_not_create_persistent_process",
        "does_not_run_learning_jobs",
        "does_not_run_self_fix",
        "does_not_write_trusted_memory",
        "does_not_mutate_source",
        "does_not_call_provider_network_browser",
        "does_not_start_model_runtime",
        "does_not_refresh_packages",
    ]:
        require(scope.get(key) is True, "contract scope flag must be true: " + key)

    denials = payload.get("inactive_behavior_denials", {})
    for key in [
        "daily_cycle_runner_implemented",
        "startup_autorun_enabled",
        "endless_loop_enabled",
        "background_worker_enabled",
        "provider_calls_enabled",
        "network_enabled",
        "browser_enabled",
        "model_runtime_enabled",
        "package_refresh_enabled",
        "unapproved_memory_write_enabled",
        "unapproved_source_mutation_enabled",
        "high_risk_self_fix_enabled",
    ]:
        require(denials.get(key) is False, "inactive behavior denial must be false: " + key)


def check_future_cli(payload: dict, combined: str) -> None:
    cli = payload.get("future_cli", [])
    require(cli == FUTURE_CLI, "future CLI mismatch")
    for command in FUTURE_CLI:
        require_text(combined, command, "future CLI")


def check_receipt_fields(payload: dict, combined: str) -> None:
    fields = payload.get("receipt_fields", [])
    require(fields == RECEIPT_FIELDS, "receipt fields mismatch")
    for field in RECEIPT_FIELDS:
        require_text(combined, field, "receipt field")


def check_stop_conditions(payload: dict, combined: str) -> None:
    stop_conditions = payload.get("stop_conditions", [])
    require(isinstance(stop_conditions, list) and len(stop_conditions) >= 10, "stop conditions must be a populated list")
    for phrase in [
        "daily cycle would start automatically",
        "daily cycle would become persistent",
        "daily cycle would exceed one cycle per command invocation",
        "daily cycle would start a hidden background worker",
        "daily cycle would call provider, network, or browser",
        "daily cycle would start model runtime",
        "daily cycle would refresh packages",
        "daily cycle would attempt high-risk self-fix",
        "daily cycle would promote memory without approval",
        "daily cycle would mutate source outside approved low-risk self-fix classes",
        "verifier stack fails",
        "risk is unsafe or unclear",
    ]:
        require_text(combined, phrase, "stop condition")


def check_no_unverified_runner_implementation_exists() -> None:
    existing = [str(path.relative_to(ROOT)) for path in RUNNER_CANDIDATES if path.exists()]
    if not existing:
        return
    require(existing == ["engel_daily_cycle_runner.py"], "unexpected daily cycle runner implementation candidate exists: " + ", ".join(existing))
    require(
        IMPLEMENTED_RUNNER_VERIFIER.exists() and IMPLEMENTED_RUNNER_VERIFIER.is_file(),
        "daily cycle runner exists without its verifier",
    )
    require(
        IMPLEMENTED_RUNNER_REPORT.exists() and IMPLEMENTED_RUNNER_REPORT.is_file(),
        "daily cycle runner exists without its report",
    )
    runner_text = IMPLEMENTED_RUNNER.read_text(encoding="utf-8", errors="replace")
    for status in [
        "DAILY_CYCLE_RUNNER",
        "FOREGROUND_COMMAND_ONLY",
        "BOUNDED_RUN_ONLY",
        "ONE_CYCLE_PER_INVOCATION",
        "NO_STARTUP_AUTORUN",
        "NO_ENDLESS_LOOP",
        "NO_BACKGROUND_WORKER",
    ]:
        require(status in runner_text, "implemented daily cycle runner missing status: " + status)


def check_verifier_ast_safety() -> None:
    source = read(THIS_FILE)
    tree = ast.parse(source)
    allowed_import_roots = {"ast", "json", "pathlib"}
    forbidden_calls = {
        "run",
        "Popen",
        "system",
        "startfile",
        "urlopen",
        "request",
        "connect",
        "download",
        "train",
        "fit",
        "encode",
        "embed",
        "write_text",
        "write_bytes",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                require(root in allowed_import_roots, "unexpected verifier import: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            require(root in allowed_import_roots or node.module == "__future__", "unexpected verifier import-from: " + str(node.module))
        elif isinstance(node, ast.While):
            raise CheckFailure("verifier contains a while loop")
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "ast" and name in {"parse", "walk"}:
                    continue
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "json" and name in {"loads", "dumps"}:
                    continue
            require(name not in forbidden_calls, "forbidden active call in verifier: " + name)


def main() -> int:
    try:
        check_files()
        payload, combined = load_contract()
        check_json_identity(payload)
        check_statuses(payload, combined)
        check_cycle_steps(payload, combined)
        check_boundaries(payload, combined)
        check_future_cli(payload, combined)
        check_receipt_fields(payload, combined)
        check_stop_conditions(payload, combined)
        check_no_unverified_runner_implementation_exists()
        check_verifier_ast_safety()
    except (CheckFailure, json.JSONDecodeError, SyntaxError) as exc:
        print("FAIL: Engel Daily Cycle Contract V1 verifier")
        print("- " + str(exc))
        return 1

    print("PASS: Engel Daily Cycle Contract V1 verifier")
    print("- contract JSON, Markdown, and report exist and parse")
    print("- daily cycle statuses, steps, boundaries, future CLI, and receipt fields are present")
    print("- no unverified daily cycle runner implementation exists")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
