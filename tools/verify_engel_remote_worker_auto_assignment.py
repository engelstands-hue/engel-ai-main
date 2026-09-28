from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_remote_worker_lan_pairing.py"
VERIFIER = ROOT / "tools" / "verify_engel_remote_worker_auto_assignment.py"
ASSIGNMENT_ROOT = ROOT / "remote_workers" / "communication_queen_assignments"
APPROVED_DIR = ASSIGNMENT_ROOT / "approved"
CLAIMED_DIR = ASSIGNMENT_ROOT / "claimed"
RETURNED_DIR = ASSIGNMENT_ROOT / "returned"
INVALID_DIR = ASSIGNMENT_ROOT / "invalid"
EXAMPLES_DIR = ASSIGNMENT_ROOT / "examples"
EXAMPLE_PACKET = EXAMPLES_DIR / "approved_assignment_example.json"
AUTO_REPORT_DIR = ROOT / "reports" / "remote_worker_auto_assignment"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_REMOTE_WORKER_PHASE_5_COMMUNICATION_QUEEN_AUTO_ASSIGNMENT.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
CONTRACT = ROOT / "mobile" / "engel_remote_worker" / "ENGEL_REMOTE_WORKER_ANDROID_CONTRACT_V1.md"
MAIN_DART = ROOT / "mobile" / "engel_remote_worker" / "lib" / "main.dart"
LAN_CLIENT_DART = ROOT / "mobile" / "engel_remote_worker" / "lib" / "lan_pairing_client.dart"
WIDGET_TEST = ROOT / "mobile" / "engel_remote_worker" / "test" / "widget_test.dart"
ANDROID_MANIFEST = ROOT / "mobile" / "engel_remote_worker" / "android" / "app" / "src" / "main" / "AndroidManifest.xml"


FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "webbrowser",
    "subprocess",
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

REQUIRED_PACKET_BLOCKED_ACTIONS = [
    "execute_commands",
    "write_trusted_memory",
    "mutate_queue",
    "mutate_routes",
    "mutate_source",
    "control_engel",
    "auto_apply_fixes",
]

WORKER_BLOCKED_ACTIONS = [
    "execute_commands",
    "mutate_source",
    "mutate_routes",
    "mutate_queue",
    "write_trusted_memory",
    "auto_apply",
    "control_engel",
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
    spec = importlib.util.spec_from_file_location("engel_remote_worker_lan_pairing", MODULE)
    require(spec is not None and spec.loader is not None, "could not load LAN pairing module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_remote_worker_lan_pairing"] = module
    spec.loader.exec_module(module)
    return module


def valid_packet() -> dict[str, object]:
    return {
        "packet_version": "1",
        "packet_id": "phase5-valid-001",
        "created_by": "Engel Communication Router",
        "approved_by": "Engel Core",
        "assignment_mode": "remote_worker_auto",
        "trust_level": "untrusted_until_reviewed",
        "worker_target": "android_worker_alpha",
        "task_type": "draft_notes",
        "title": "Draft review notes",
        "instructions": "Prepare draft notes only. Do not execute commands.",
        "allowed_outputs": ["draft_result_json"],
        "blocked_actions": list(REQUIRED_PACKET_BLOCKED_ACTIONS),
        "requires_review": True,
        "safe_to_auto_apply": False,
    }


def valid_result(packet_id: str = "phase5-valid-001") -> dict[str, object]:
    return {
        "result_version": "1",
        "packet_id": packet_id,
        "worker_device": "engel_remote_worker_flutter",
        "worker_id": "android_worker_alpha",
        "trust_level": "untrusted_until_engel_review",
        "result_type": "auto_worker_acknowledgement",
        "draft_text": "Acknowledged for review only. No commands executed.",
        "requires_review": True,
        "safe_to_auto_apply": False,
        "auto_generated": True,
    }


def check_files() -> None:
    for path in [
        MODULE,
        VERIFIER,
        ASSIGNMENT_ROOT,
        APPROVED_DIR,
        CLAIMED_DIR,
        RETURNED_DIR,
        INVALID_DIR,
        EXAMPLES_DIR,
        EXAMPLE_PACKET,
        AUTO_REPORT_DIR,
        REPORT,
        COMMANDS,
        CODEX_VERIFY,
        CONTRACT,
        MAIN_DART,
        LAN_CLIENT_DART,
        WIDGET_TEST,
    ]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_python_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for snippet in [
        'DEFAULT_HOST = "127.0.0.1"',
        "LAN bind requires --allow-lan",
        "AUTO_ALLOWED_ACTIONS",
        "validate_assignment_packet",
        "next_assignment_response",
        "validate_returned_result",
        "store_returned_result",
        "UDP_DISCOVERY_PORT_OFFSET = 1",
        "start_udp_broadcaster(port)",
        "udp_discovery_targets",
        "sock.sendto(payload, (target, udp_port))",
        'name="engel-udp-discovery"',
        "daemon=True",
        "UNTRUSTED REVIEW ONLY - NOT APPLIED",
        '"trusted_memory_write": False',
        '"auto_apply": False',
    ]:
        require(snippet in source, "LAN protocol missing required snippet: " + snippet)
    for forbidden in [
        "trusted_memory.write",
        "mutate_routes(",
        "apply_patch(",
        "watchdog.Observer",
        "ScheduledTask",
        "provider_api",
        "BOOT_COMPLETED",
        "WAKE_LOCK",
        "firewall",
        "UPnP",
        "port_forward",
    ]:
        require(forbidden not in source, "LAN protocol contains forbidden text: " + forbidden)
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
            raise CheckFailure("LAN protocol contains async/background-like construct")


def check_runtime_behavior() -> None:
    module = load_module()
    ok, _ = module.validate_bind("127.0.0.1", False)
    require(ok, "default localhost bind should be allowed")
    ok, reason = module.validate_bind("0.0.0.0", False)
    require(not ok and "--allow-lan" in reason, "LAN bind must require --allow-lan")

    status = module.worker_status_response()
    require(status.get("mode") == "bounded_auto_worker", "worker status must be bounded_auto_worker")
    for field in ["direct_control", "trusted_memory_write", "auto_apply"]:
        require(status.get(field) is False, "worker status safety field must be false: " + field)
    for action in WORKER_BLOCKED_ACTIONS:
        require(action in status.get("blocked_actions", []), "worker status missing blocked action: " + action)
    for action in ["poll_approved_assignment", "return_untrusted_result"]:
        require(action in status.get("allowed_actions", []), "worker status missing allowed action: " + action)

    missing_status, missing_response = module.validate_pairing_auth("", "engel_remote_worker_flutter")
    require(missing_status != 200 and missing_response.get("paired") is False, "worker endpoints must require pairing")

    with tempfile.TemporaryDirectory() as temp_name:
        temp_root = Path(temp_name)
        empty = temp_root / "empty"
        empty.mkdir()
        packet, packet_path, errors = module.next_valid_assignment(directory=empty)
        require(packet is None and packet_path is None, "empty approved folder must produce no work")

        valid_dir = temp_root / "approved"
        valid_dir.mkdir()
        valid_path = valid_dir / "valid.json"
        valid_path.write_text(json.dumps(valid_packet()), encoding="utf-8")
        packet, packet_path, errors = module.next_valid_assignment(directory=valid_dir)
        require(packet is not None and packet_path == valid_path and not errors, "valid assignment should be accepted")

        bad = valid_packet()
        bad["safe_to_auto_apply"] = True
        require(
            any("safe_to_auto_apply" in error for error in module.validate_assignment_packet(bad)),
            "safe_to_auto_apply true packet must be rejected",
        )
        bad = valid_packet()
        bad["requires_review"] = False
        require(
            any("requires_review" in error for error in module.validate_assignment_packet(bad)),
            "requires_review false packet must be rejected",
        )
        bad = valid_packet()
        bad["blocked_actions"] = [action for action in REQUIRED_PACKET_BLOCKED_ACTIONS if action != "control_engel"]
        require(
            any("control_engel" in error for error in module.validate_assignment_packet(bad)),
            "packet missing required blocked action must be rejected",
        )
        bad = valid_packet()
        bad["task_type"] = "execute_command"
        require(
            any("blocked task type" in error for error in module.validate_assignment_packet(bad)),
            "blocked task type must be rejected",
        )

        result = valid_result()
        require(not module.validate_returned_result(result), "valid untrusted result should validate")
        bad_result = valid_result()
        bad_result["safe_to_auto_apply"] = True
        require(
            any("safe_to_auto_apply" in error for error in module.validate_returned_result(bad_result)),
            "safe_to_auto_apply true result must be rejected",
        )
        bad_result = valid_result()
        bad_result["requires_review"] = False
        require(
            any("requires_review" in error for error in module.validate_returned_result(bad_result)),
            "requires_review false result must be rejected",
        )

        returned_dir = temp_root / "returned"
        report_dir = temp_root / "reports"
        result_path, receipt_path = module.store_returned_result(
            dict(result),
            remote_address="127.0.0.1",
            returned_dir=returned_dir,
            report_dir=report_dir,
        )
        stored = json.loads(result_path.read_text(encoding="utf-8"))
        receipt = receipt_path.read_text(encoding="utf-8")
        require(stored.get("storage_decision") == module.AUTO_FINAL_DECISION, "stored result must be review-only")
        require("UNTRUSTED REVIEW ONLY - NOT APPLIED" in receipt, "receipt must state untrusted review-only decision")
        require("does not execute, apply, promote, route, queue, trust" in receipt, "receipt must block apply/trust behavior")


def check_example_packet() -> None:
    payload = json.loads(EXAMPLE_PACKET.read_text(encoding="utf-8"))
    module = load_module()
    require(not module.validate_assignment_packet(payload), "example approved assignment should validate")
    require(payload.get("packet_id") != "phase5-valid-001", "example packet should not be a verifier temp record")
    require(EXAMPLE_PACKET.parent.name == "examples", "example packet must not be placed in live approved folder")


def check_flutter_auto_ui() -> None:
    main = read(MAIN_DART)
    client = read(LAN_CLIENT_DART)
    tests = read(WIDGET_TEST)
    for phrase in [
        "Auto Worker",
        "Auto Mode",
        "Paired required",
        "Check Now",
        "Pause Auto Mode",
        "Review required",
        "No direct Engel control.",
        "Communication Queen approved packets only.",
        "safe_to_auto_apply",
        "requires_review",
    ]:
        require(phrase in main, "Flutter Auto Worker UI missing phrase: " + phrase)
    for phrase in [
        "/worker/status",
        "/worker/next-assignment",
        "/worker/return-result",
        "returnDraftResult",
        "'safe_to_auto_apply': false",
        "'requires_review': true",
        # worker_id is now config-driven (read from per-phone
        # worker_identity.json in the app's external-app-scoped folder)
        # with android_worker_alpha as the back-compat default. The
        # Flutter LAN client must still expose the worker_id field and
        # default to android_worker_alpha when no config is present.
        "'worker_id': workerId",
        "_defaultWorkerId = 'android_worker_alpha'",
    ]:
        require(phrase in client, "Flutter LAN client missing phrase: " + phrase)
    for phrase in ["Auto Worker page can be reached", "Pause Auto Mode", "No direct Engel control."]:
        require(phrase in tests, "Widget tests missing Auto Worker coverage: " + phrase)
    for forbidden in [
        "Isolate.spawn",
        "Workmanager",
        "BOOT_COMPLETED",
        "WAKE_LOCK",
        "Apply Fix",
        "Execute",
        "Run Route",
        "Control Engel",
        "Write Memory",
        "Upload Result",
        "Download Packet",
    ]:
        require(forbidden not in main, "Flutter UI contains forbidden phrase: " + forbidden)
        require(forbidden not in client, "Flutter client contains forbidden phrase: " + forbidden)
    if ANDROID_MANIFEST.exists():
        manifest = read(ANDROID_MANIFEST)
        for forbidden in ["android.permission.WAKE_LOCK", "BOOT_COMPLETED", "<service", "<receiver"]:
            require(forbidden not in manifest, "Android manifest contains forbidden background behavior: " + forbidden)


def check_docs_and_registration() -> None:
    commands = read(COMMANDS)
    contract = read(CONTRACT)
    report = read(REPORT)
    verify = read(CODEX_VERIFY)
    for phrase in [
        "remote worker auto assignment status",
        "remote worker auto assignment next",
        "remote worker auto assignment return result",
    ]:
        require(phrase in commands, "commands doc missing: " + phrase)
    for phrase in [
        "Phase 5 Communication Queen Approved Auto-Assignment",
        "Auto Mode is user-enabled",
        "No Android background service",
        "safe_to_auto_apply: false",
    ]:
        require(phrase in contract, "contract missing Phase 5 phrase: " + phrase)
    for phrase in [
        "ENGEL_REMOTE_WORKER_PHASE_5_COMMUNICATION_QUEEN_AUTO_ASSIGNMENT",
        "Communication Queen integration boundary",
        "Auto Mode behavior",
        "poll for approved Communication Queen packets and return untrusted results only",
    ]:
        require(phrase in report, "report missing phrase: " + phrase)
    require("tools\\verify_engel_remote_worker_auto_assignment.py" in verify, "codex verifier missing Phase 5 verifier")


def main() -> int:
    checks = [
        check_files,
        check_python_static_safety,
        check_runtime_behavior,
        check_example_packet,
        check_flutter_auto_ui,
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
        print("ENGEL_REMOTE_WORKER_AUTO_ASSIGNMENT_VERIFY_FAIL")
        return 1
    print("ENGEL_REMOTE_WORKER_AUTO_ASSIGNMENT_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
