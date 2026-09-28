from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PRODUCER = ROOT / "engel_communication_queen_assignment_producer.py"
LAN_MODULE = ROOT / "engel_remote_worker_lan_pairing.py"
VERIFIER = ROOT / "tools" / "verify_engel_communication_queen_assignment_producer.py"
PHASE5_VERIFIER = ROOT / "tools" / "verify_engel_remote_worker_auto_assignment.py"
ASSIGNMENT_ROOT = ROOT / "remote_workers" / "communication_queen_assignments"
APPROVED_DIR = ASSIGNMENT_ROOT / "approved"
CLAIMED_DIR = ASSIGNMENT_ROOT / "claimed"
RETURNED_DIR = ASSIGNMENT_ROOT / "returned"
INVALID_DIR = ASSIGNMENT_ROOT / "invalid"
RETIRED_DIR = ASSIGNMENT_ROOT / "retired"
EXAMPLES_DIR = ASSIGNMENT_ROOT / "examples"
EXAMPLE_PACKET = EXAMPLES_DIR / "communication_queen_assignment_example.json"
REPORT_DIR = ROOT / "reports" / "communication_queen_assignments"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_REMOTE_WORKER_PHASE_6_COMMUNICATION_QUEEN_ASSIGNMENT_PRODUCER.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"


REQUIRED_BLOCKED_ACTIONS = [
    "execute_commands",
    "write_trusted_memory",
    "mutate_queue",
    "mutate_routes",
    "mutate_source",
    "control_engel",
    "auto_apply_fixes",
    "provider_call",
    "browser_task",
    "download",
    "install_package",
]

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "subprocess",
    "threading",
    "multiprocessing",
    "asyncio",
    "watchdog",
    "smtplib",
    "openai",
}

FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "__import__",
    "system",
    "popen",
    "Popen",
    "run",
    "call",
    "check_call",
    "check_output",
    "startfile",
}


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_module(path: Path, name: str):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "could not load module: " + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def check_files_and_folders() -> None:
    for path in [
        PRODUCER,
        LAN_MODULE,
        VERIFIER,
        PHASE5_VERIFIER,
        ASSIGNMENT_ROOT,
        APPROVED_DIR,
        CLAIMED_DIR,
        RETURNED_DIR,
        INVALID_DIR,
        RETIRED_DIR,
        EXAMPLES_DIR,
        EXAMPLE_PACKET,
        REPORT_DIR,
        REPORT,
        COMMANDS,
        CODEX_VERIFY,
    ]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    source = read(PRODUCER)
    tree = ast.parse(source)
    for snippet in [
        "def status_payload",
        "def list_assignments",
        "def validate_assignment_packet",
        "def create_assignment",
        "def retire_assignment",
        "def write_receipt",
        "APPROVED FOR REMOTE WORKER ASSIGNMENT ONLY - UNTRUSTED RESULT REQUIRED",
        '"created_by": ENGEL_COMMUNICATION_ROUTER_NAME',
        '"approved_by": ENGEL_CORE_NAME',
        '"approval_scope": "remote_worker_assignment_only"',
        '"safe_to_auto_apply": False',
        '"not_trusted_memory": True',
        '"no_direct_control": True',
    ]:
        require(snippet in source, "producer missing required snippet: " + snippet)
    for forbidden in [
        "trusted_memory.write",
        "apply_patch(",
        "watchdog.Observer",
        "ScheduledTask",
        "provider_api",
        "start_server(",
        "start_worker(",
        "BOOT_COMPLETED",
        "WAKE_LOCK",
    ]:
        require(forbidden not in source, "producer contains forbidden text: " + forbidden)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                require(root_name not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".")[0]
            require(root_name not in FORBIDDEN_IMPORTS, "forbidden import: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            require(name not in FORBIDDEN_CALLS, "forbidden call: " + name)
        elif isinstance(node, (ast.AsyncFunctionDef, ast.AsyncFor, ast.AsyncWith)):
            raise CheckFailure("producer contains async/background-like construct")


def check_runtime_schema_and_create() -> None:
    producer = load_module(PRODUCER, "engel_communication_queen_assignment_producer")
    lan = load_module(LAN_MODULE, "engel_remote_worker_lan_pairing")
    with tempfile.TemporaryDirectory() as temp_name:
        temp_root = Path(temp_name)
        approved = temp_root / "approved"
        report_dir = temp_root / "reports"
        source_dir = temp_root / "source"
        approved.mkdir()
        report_dir.mkdir()
        source_dir.mkdir()

        source_path = source_dir / "notes.md"
        # Repoint roots for this isolated verifier smoke only.
        producer.ALLOWED_SOURCE_ROOTS = [source_dir.resolve()]
        source_path.write_text("Remote Worker review notes. Do not execute commands.", encoding="utf-8")
        packet, packet_path, receipt_path = producer.create_assignment(
            worker="android_worker_alpha",
            task_type="draft_notes",
            title="Verifier safe assignment smoke",
            instructions="Draft notes only. Do not execute commands.",
            source_path=str(source_path),
            approved_dir=approved,
            report_dir=report_dir,
        )
        require(packet_path.exists(), "create_assignment did not write packet")
        require(receipt_path.exists(), "create_assignment did not write receipt")
        errors = producer.validate_assignment_packet(packet)
        require(not errors, "created packet failed producer validation: " + repr(errors))
        phase5_errors = lan.validate_assignment_packet(packet)
        require(not phase5_errors, "created packet failed Phase 5 validation: " + repr(phase5_errors))
        for field, expected in {
            "created_by": "Engel Communication Router",
            "approved_by": "Engel Core",
            "approval_scope": "remote_worker_assignment_only",
            "assignment_mode": "remote_worker_auto",
            "requires_review": True,
            "safe_to_auto_apply": False,
            "not_trusted_memory": True,
            "no_direct_control": True,
        }.items():
            require(packet.get(field) == expected, f"created packet field mismatch: {field}")
        for action in REQUIRED_BLOCKED_ACTIONS:
            require(action in packet.get("blocked_actions", []), "created packet missing blocked action: " + action)
        require("execute" in packet.get("risk_flags", []), "risky command-like text should be flagged")
        receipt = read(receipt_path)
        require("APPROVED FOR REMOTE WORKER ASSIGNMENT ONLY - UNTRUSTED RESULT REQUIRED" in receipt, "receipt missing final decision")
        require("This assignment is not trusted memory." in receipt, "receipt missing trusted-memory boundary")
        require("does not authorize command execution" in receipt, "receipt missing command boundary")

        blocked = dict(packet)
        blocked["task_type"] = "execute_command"
        require(any("blocked task type" in error for error in producer.validate_assignment_packet(blocked)), "blocked task type was not rejected")
        unsafe = dict(packet)
        unsafe["safe_to_auto_apply"] = True
        require(any("safe_to_auto_apply" in error for error in producer.validate_assignment_packet(unsafe)), "safe_to_auto_apply true was not rejected")
        unsafe = dict(packet)
        unsafe["requires_review"] = False
        require(any("requires_review" in error for error in producer.validate_assignment_packet(unsafe)), "requires_review false was not rejected")
        unsafe = dict(packet)
        unsafe["blocked_actions"] = [action for action in REQUIRED_BLOCKED_ACTIONS if action != "install_package"]
        require(any("install_package" in error for error in producer.validate_assignment_packet(unsafe)), "missing blocked action was not rejected")

        huge_path = source_dir / "huge.md"
        huge_path.write_text("x" * (producer.MAX_TEXT_BYTES + 1), encoding="utf-8")
        try:
            producer.read_source_material(str(huge_path))
        except ValueError as exc:
            require("too large" in str(exc), "huge source should be rejected with size reason")
        else:
            raise CheckFailure("huge source was not rejected")

        retired_dir = temp_root / "retired"
        retired_path, retired_receipt = producer.retire_assignment(
            str(packet["packet_id"]),
            approved_dir=approved,
            retired_dir=retired_dir,
            report_dir=report_dir,
        )
        require(retired_path.exists() and not packet_path.exists(), "retire should move approved packet")
        require(retired_receipt.exists(), "retire should write receipt")


def check_status_list_and_examples() -> None:
    producer = load_module(PRODUCER, "engel_communication_queen_assignment_producer_examples")
    status = producer.status_payload()
    require(status.get("trusted_memory_write") is False, "status must keep trusted-memory writes false")
    require(status.get("auto_apply") is False, "status must keep auto-apply false")
    rows = producer.list_assignments(APPROVED_DIR)
    for row in rows:
        require(str(row.get("path", "")).endswith(".json") or row.get("path"), "list row should be bounded metadata")
    example = json.loads(EXAMPLE_PACKET.read_text(encoding="utf-8"))
    require(not producer.validate_assignment_packet(example), "example assignment should validate")
    require(EXAMPLE_PACKET.parent.name == "examples", "example assignment must stay under examples")
    # Live approved/ may contain real producer-created assignments (the producer
    # is no longer a one-shot test surface). Every .json here must be a
    # producer-validated packet — not a garbage or fixture-leftover file.
    live_json = [path for path in APPROVED_DIR.glob("*.json")]
    for path in live_json:
        payload = json.loads(path.read_text(encoding="utf-8"))
        errors = producer.validate_assignment_packet(payload)
        require(not errors, f"live approved assignment {path.name} failed validation: {errors}")


def check_docs_and_registration() -> None:
    commands = read(COMMANDS)
    report = read(REPORT)
    codex_verify = read(CODEX_VERIFY)
    for phrase in [
        "communication queen assignment status",
        "communication queen assignment list",
        "communication queen assignment validate",
        "communication queen assignment create",
        "communication queen assignment retire",
    ]:
        require(phrase in commands, "commands doc missing: " + phrase)
    for phrase in [
        "ENGEL_REMOTE_WORKER_PHASE_6_COMMUNICATION_QUEEN_ASSIGNMENT_PRODUCER",
        "Assignment schema",
        "Allowed task types",
        "Blocked task types",
        "Assignment approval is not trusted-memory approval",
        "Communication Queen may produce Remote Worker assignment packets",
    ]:
        require(phrase in report, "report missing phrase: " + phrase)
    require("tools\\verify_engel_communication_queen_assignment_producer.py" in codex_verify, "codex verifier missing producer verifier")


def main() -> int:
    checks = [
        check_files_and_folders,
        check_static_safety,
        check_runtime_schema_and_create,
        check_status_list_and_examples,
        check_docs_and_registration,
    ]
    failures: list[str] = []
    for check in checks:
        try:
            check()
            print(f"PASS {check.__name__}")
        except Exception as exc:  # noqa: BLE001 - verifier reports exact local failure
            failures.append(f"{check.__name__}: {exc}")
            print(f"FAIL {check.__name__}: {exc}")
    if failures:
        print("ENGEL_COMMUNICATION_QUEEN_ASSIGNMENT_PRODUCER_VERIFY_FAIL")
        return 1
    print("ENGEL_COMMUNICATION_QUEEN_ASSIGNMENT_PRODUCER_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
