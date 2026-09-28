from __future__ import annotations

import ast
import importlib.util
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PLAN_JSON = ROOT / "memory" / "ENGEL_ANDROID_REMOTE_WORKER_PLAN_V1.json"
PLAN_MD = ROOT / "memory" / "ENGEL_ANDROID_REMOTE_WORKER_PLAN_V1.md"
MODULE = ROOT / "engel_android_remote_worker_contract.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_ANDROID_REMOTE_WORKER_PLAN_V1.md"
ENGEL_COMMUNICATION_ROUTER_NAMES = {"Engel Communication Router", "Communication Queen"}

REQUIRED_FIELDS = [
    "plan_name",
    "schema_version",
    "purpose",
    "role",
    "device_type",
    "controlled_by",
    "routing_owner",
    "not_a_queen",
    "status",
    "communication_flow",
    "safety_boundaries",
    "allowed_task_types",
    "forbidden_task_types",
    "connection_phases",
    "task_packet_schema",
    "report_packet_schema",
    "approval_requirements",
    "verification_requirements",
    "android_ui_concept",
    "manual_controls",
    "safety_ui_text",
    "future_phases",
    "limitations",
]

REQUIRED_STATUSES = [
    "ANDROID_REMOTE_WORKER_PLAN",
    "REMOTE_WORKER",
    "MOBILE_WORKER",
    "ANDROID_PHONE",
    "NOT_A_QUEEN",
    "CONTROLLED_BY_COMMUNICATION_QUEEN",
    "ROUTED_THROUGH_COMMUNICATION_QUEEN",
    "SCAFFOLD_ONLY",
    "CONTRACT_DESIGN_STATUS_ONLY",
    "UNTRUSTED_WORKER_OUTPUT",
    "ENGEL_VERIFICATION_REQUIRED",
    "HUMAN_APPROVAL_REQUIRED",
    "NO_DIRECT_CORE_ACCESS",
    "NO_QUEUE_MUTATION",
    "NO_ROUTE_MUTATION",
    "NO_SOURCE_MUTATION",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK_RUNTIME",
    "NO_BROWSER_RUNTIME",
    "NO_BACKGROUND_WORKER",
    "NO_AUTONOMY",
    "NO_FAKE_LIVE_ANDROID_CONNECTION",
]

REQUIRED_TASK_FIELDS = [
    "packet_id",
    "created_at",
    "created_by",
    "routing_owner",
    "target_worker_id",
    "worker_type",
    "task_type",
    "title",
    "instructions",
    "input_text",
    "safety_level",
    "approval_token_required",
    "expires_at",
    "forbidden_actions",
    "expected_report_fields",
]

REQUIRED_REPORT_FIELDS = [
    "packet_id",
    "task_packet_id",
    "from_worker_id",
    "to",
    "completed_at",
    "status",
    "summary",
    "result_text",
    "warnings",
    "errors",
    "actions_taken",
    "actions_refused",
    "needs_engel_verification",
    "trusted_memory_write_requested",
    "queen_behavior_requested",
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


def is_engel_router_name(value: object) -> bool:
    return str(value) in ENGEL_COMMUNICATION_ROUTER_NAMES


def load_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_android_remote_worker_contract", MODULE)
    require(spec is not None and spec.loader is not None, "could not load contract module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_android_remote_worker_contract"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [PLAN_JSON, PLAN_MD, MODULE, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path.relative_to(ROOT)))


def check_json_contract() -> None:
    data = json.loads(read(PLAN_JSON))
    require(isinstance(data, dict), "plan JSON must be an object")
    for field in REQUIRED_FIELDS:
        require(field in data, "missing JSON field: " + field)
    require(data.get("role") == "remote_worker", "role must be remote_worker")
    require(data.get("device_type") == "android_phone", "device_type must be android_phone")
    require(is_engel_router_name(data.get("controlled_by")), "Engel Communication Router must be controller")
    require(is_engel_router_name(data.get("routing_owner")), "Engel Communication Router must be routing owner")
    require(data.get("not_a_queen") is True, "not_a_queen must be true")
    require(data.get("status") == "scaffold-only", "status must be scaffold-only")
    for status in REQUIRED_STATUSES:
        require(status in data.get("status_labels", []), "missing status label: " + status)
    for rule in [
        "Engel Core does not talk directly to Android Remote Workers.",
        "Android Remote Workers do not talk directly to Engel Core.",
        "All messages route through Communication Queen.",
        "Worker output is untrusted until verified.",
        "Worker output cannot write trusted memory.",
        "Worker output cannot approve itself.",
        "Worker output cannot command Engel directly.",
    ]:
        require(rule in data.get("architecture_rules", []), "missing architecture rule: " + rule)
    boundaries = data.get("safety_boundaries")
    require(isinstance(boundaries, dict), "safety_boundaries must be an object")
    for key in [
        "phone_is_not_a_queen",
        "communication_queen_controls_routing",
        "no_direct_core_access",
        "worker_output_untrusted_until_verified",
        "engel_verification_required",
        "human_approval_required",
        "no_runtime_phone_connection",
        "no_sockets",
        "no_network_runtime",
        "no_browser_runtime",
        "no_provider_calls",
        "no_background_worker",
        "no_autonomy",
        "no_queue_mutation",
        "no_route_mutation",
        "no_source_mutation",
        "no_trusted_memory_write",
        "no_fake_live_android_connection",
    ]:
        require(boundaries.get(key) is True, "safety boundary missing/false: " + key)
    task_schema = data.get("task_packet_schema")
    require(isinstance(task_schema, dict), "task_packet_schema missing")
    for field in REQUIRED_TASK_FIELDS:
        require(field in task_schema.get("required_fields", []), "task packet missing field: " + field)
    fixed_task = task_schema.get("fixed_values", {})
    require(is_engel_router_name(fixed_task.get("created_by")), "task created_by mismatch")
    require(is_engel_router_name(fixed_task.get("routing_owner")), "task routing owner mismatch")
    require(fixed_task.get("worker_type") == "android_remote_worker", "task worker type mismatch")
    report_schema = data.get("report_packet_schema")
    require(isinstance(report_schema, dict), "report_packet_schema missing")
    for field in REQUIRED_REPORT_FIELDS:
        require(field in report_schema.get("required_fields", []), "report packet missing field: " + field)
    fixed_report = report_schema.get("fixed_values", {})
    require(is_engel_router_name(fixed_report.get("to")), "report destination mismatch")
    require(fixed_report.get("needs_engel_verification") is True, "report must require Engel verification")
    require(fixed_report.get("trusted_memory_write_requested") is False, "report must not request trusted-memory writes")
    require(fixed_report.get("queen_behavior_requested") is False, "report must not request Queen behavior")
    require(data.get("plan_name") != "Android Remote Queen", "forbidden name used as active plan name")
    require(data.get("plan_name") != "Mobile Queen", "forbidden name used as active plan name")
    require("Remote Worker" in data.get("plan_name", ""), "active plan name must use Remote Worker")


def check_markdown_plan() -> None:
    text = read(PLAN_MD)
    for needle in [
        "Android Remote Worker",
        "Remote Worker",
        "Mobile Worker",
        "Communication Queen",
        "Not a Queen",
        "scaffold-only",
        "contract/design/status only",
        "Only Phase 1 is implemented now",
        "worker reports are untrusted until verified",
        "Reports require Engel verification and human approval",
    ]:
        require(needle in text, "Markdown missing: " + needle)
    for forbidden in ["Android Remote Queen", "Mobile Queen", "Remote Queen"]:
        index = text.find(forbidden)
        while index >= 0:
            window = text[max(0, index - 120): index + 160].lower()
            require("do not use" in window or "naming denials" in window or "forbidden task" in window, "forbidden name appears outside denial context: " + forbidden)
            index = text.find(forbidden, index + 1)


def check_module_static_and_runtime() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for option in ["--status", "--validate", "--json"]:
        require(option in source, "module missing CLI option: " + option)
    for blocked in ["phone connection", "socket", "API calls", "provider calls", "browser/network", "background workers", "queue mutation", "route mutation", "memory mutation", "source mutation", "trusted memory write", "fake live connection data"]:
        require(blocked in source, "module missing forbidden behavior note: " + blocked)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import from: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                require(func.id not in {"eval", "exec", "__import__"}, "forbidden dynamic call: " + func.id)

    module = load_module()
    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--validate"], stdout=out, stderr=err) == 0, "module --validate failed")
    require("validation PASSED" in out.getvalue(), "--validate missing PASS text")
    out = io.StringIO()
    require(module.main(["--status"], stdout=out, stderr=err) == 0, "module --status failed")
    require("Engel Android Remote Worker Plan V1" in out.getvalue(), "--status missing title")
    out = io.StringIO()
    require(module.main(["--json"], stdout=out, stderr=err) == 0, "module --json failed")
    payload = json.loads(out.getvalue())
    require(payload.get("role") == "remote_worker", "--json output role mismatch")


def check_report() -> None:
    text = read(REPORT)
    for needle in [
        "files read first",
        "files created",
        "files updated",
        "Android Remote Worker design summary",
        "Communication Queen routing boundary",
        "task packet schema summary",
        "report packet schema summary",
        "safety boundary",
        "verification commands",
        "verification results",
        "contract smoke results",
        "focused safety scan result",
        "remaining limitations",
        "next safe phase",
        "no runtime phone connection was added",
        "no network/API/browser/provider behavior was added",
        "no background worker/autonomy was added",
        "no trusted-memory/queue/route/source mutation was added",
        "phone is not a Queen",
        "packaging skipped",
        "final scoped process sweep",
        "git status",
    ]:
        require(needle in text, "report missing: " + needle)


def main() -> int:
    checks = [
        ("files", check_files_exist),
        ("json_contract", check_json_contract),
        ("markdown_plan", check_markdown_plan),
        ("module", check_module_static_and_runtime),
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
        print("\nAndroid Remote Worker contract verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nAndroid Remote Worker contract verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
