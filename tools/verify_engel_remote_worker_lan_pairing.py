from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_remote_worker_lan_pairing.py"
VERIFIER = ROOT / "tools" / "verify_engel_remote_worker_lan_pairing.py"
PAIRING_ROOT = ROOT / "remote_workers" / "lan_pairing"
LINK_MANAGER_ROOT = ROOT / "remote_workers" / "lan_link_manager"
REPORT_DIR = ROOT / "reports" / "remote_worker_lan_pairing"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_REMOTE_WORKER_PHASE_4_LAN_PAIRING.md"
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

REQUIRED_BLOCKED_ACTIONS = [
    "execute_commands",
    "mutate_source",
    "mutate_routes",
    "mutate_queue",
    "write_trusted_memory",
    "auto_apply",
    "control_engel",
    "packet_transfer",
    "result_upload",
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


def check_files() -> None:
    for path in [MODULE, VERIFIER, PAIRING_ROOT, REPORT_DIR, MAIN_DART, LAN_CLIENT_DART, WIDGET_TEST, CONTRACT]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_python_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for snippet in [
        'DEFAULT_HOST = "127.0.0.1"',
        "LAN bind requires --allow-lan",
        "TOKEN_TTL_SECONDS",
        "8 * 60 * 60",
        "secrets.choice",
        "MAX_REQUEST_BYTES = 4096",
        "UDP_DISCOVERY_PORT_OFFSET = 1",
        "start_udp_broadcaster(port)",
        "udp_discovery_targets",
        "sock.sendto(payload, (target, udp_port))",
        'name="engel-udp-discovery"',
        "daemon=True",
        '"direct_control": False',
        '"trusted_memory_write": False',
        '"auto_apply": False',
        '"packet_transfer": False',
        '"result_upload": False',
        "PAIRING STATUS ONLY - NO CONTROL GRANTED",
    ]:
        require(snippet in source, "LAN module missing required snippet: " + snippet)
    for forbidden in [
        "trusted_memory.write",
        "mutate_queue(",
        "mutate_routes(",
        "apply_patch(",
        "watchdog.Observer",
        "startup",
        "ScheduledTask",
        "provider_api",
        "firewall",
        "UPnP",
        "port_forward",
    ]:
        require(forbidden not in source, "LAN module contains forbidden text: " + forbidden)
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
            raise CheckFailure("LAN module contains async/background-like construct")


def check_runtime_behavior() -> None:
    module = load_module()
    ok, _ = module.validate_bind("127.0.0.1", False)
    require(ok, "localhost bind should be allowed")
    ok, reason = module.validate_bind("0.0.0.0", False)
    require(not ok and "--allow-lan" in reason, "LAN bind must require --allow-lan")
    ok, _ = module.validate_bind("0.0.0.0", True)
    require(ok, "LAN bind with explicit allow flag should be valid")

    code_a = module.generate_pairing_code()
    code_b = module.generate_pairing_code()
    require(code_a != code_b, "pairing token appears hard-coded")
    require(len(code_a) == module.TOKEN_LENGTH, "pairing token length mismatch")

    health = module.health_response()
    for field in ["direct_control", "trusted_memory_write", "auto_apply", "packet_transfer", "result_upload"]:
        require(health.get(field) is False, "/health safety field must be false: " + field)
    require(health.get("mode") == "pairing_only", "/health mode mismatch")

    missing_status, missing = module.validate_pair_payload({})
    require(missing_status == 400 and missing.get("paired") is False, "/pair must require pairing code")

    session = module.PairingSession(
        pairing_code="ABC12345",
        created_at_utc="2026-05-17T00:00:00Z",
        expires_at_utc="2026-05-17T00:15:00Z",
    )
    valid_payload = {
        "pairing_code": "ABC12345",
        "worker_device": "engel_remote_worker_flutter",
        "client_mode": "local_draft_mode",
    }
    status, response = module.validate_pair_payload(
        valid_payload,
        session=session,
        now=module.parse_utc("2026-05-17T00:05:00Z"),
    )
    require(status == 200 and response.get("paired") is True, "/pair valid payload should pair")
    require(response.get("mode") == "status_only", "/pair success must be status_only")
    for action in REQUIRED_BLOCKED_ACTIONS:
        require(action in response.get("blocked_actions", []), "blocked action missing: " + action)
    blocked_payload = dict(valid_payload)
    blocked_payload["execute_commands"] = True
    blocked_status, blocked = module.validate_pair_payload(
        blocked_payload,
        session=session,
        now=module.parse_utc("2026-05-17T00:05:00Z"),
    )
    require(blocked_status == 403 and blocked.get("paired") is False, "blocked request field must be rejected")
    expired_status, expired = module.validate_pair_payload(
        valid_payload,
        session=session,
        now=module.parse_utc("2026-05-17T00:16:00Z"),
    )
    require(expired_status == 403 and "expired" in expired.get("error", ""), "expired token must fail")

    LINK_MANAGER_ROOT.mkdir(parents=True, exist_ok=True)
    original_path = module.LINK_MANAGER_STATE_PATH
    backup = original_path.read_text(encoding="utf-8") if original_path.exists() else None
    try:
        continuity_state = {
            "workers": {
                "android_worker_alpha": {
                    "identity": {
                        "worker_id": "android_worker_alpha",
                        "worker_device": "engel_remote_worker_flutter",
                        "remote_address": "192.0.2.78",
                    },
                    "last_seen_utc": module.utc_stamp(),
                }
            }
        }
        original_path.write_text(json.dumps(continuity_state, indent=2), encoding="utf-8")
        drift_status, drift = module.validate_existing_worker_session(
            "engel_remote_worker_flutter",
            "android_worker_alpha",
            "192.0.2.99",
        )
        require(
            drift_status == 200 and drift.get("paired") is True,
            "existing worker session must survive LAN IP drift inside continuity window",
        )
    finally:
        if backup is not None:
            original_path.write_text(backup, encoding="utf-8")
        elif original_path.exists():
            original_path.unlink()

    source = read(MODULE)
    require("PAIRED_WORKER_CONTINUITY_SECONDS = 6 * 60 * 60" in source, "missing 6-hour worker continuity constant")
    require("get_or_create_session()" in source and "create_pairing_session()" in source, "session helpers missing")
    require(
        "session = get_or_create_session()" in source,
        "UDP discovery must not early-rotate pairing tokens",
    )


def check_flutter_ui() -> None:
    main = read(MAIN_DART)
    client = read(LAN_CLIENT_DART)
    tests = read(WIDGET_TEST)
    for phrase in [
        "LAN Pairing",
        "Test Health",
        "Test Pairing",
        "Clear Status",
        "Pairing is status-only.",
        "No direct Engel control.",
        "No trusted-memory write.",
        "No route/queue/source mutation.",
        "No command execution.",
        "Start the Engel-managed Dedicated Phone Link on the PC.",
    ]:
        require(phrase in main, "Flutter UI missing phrase: " + phrase)
    for phrase in [
        "HttpClient",
        "testHealth",
        "testPairing",
        "engel_remote_worker_flutter",
        "local_draft_mode",
        "Receiver reachable - pairing/status only.",
        "Paired as dedicated Engel Remote Worker - Engel controls phone worker mode; phone does not control Engel.",
    ]:
        require(phrase in client, "LAN client missing phrase: " + phrase)
    for forbidden in [
        "Stream.periodic",
        "autoReconnect",
        "while (true)",
        "Upload Result",
        "Download Packet",
        "Control Engel",
        "Run Route",
        "Apply Fix",
        "Sync Automatically",
    ]:
        require(forbidden not in main + client, "Flutter code contains forbidden phrase: " + forbidden)
    require("LAN Pairing page can be reached" in tests, "widget test missing LAN page coverage")


def check_docs_and_integration() -> None:
    commands = read(COMMANDS)
    for command in [
        "remote worker lan pairing status",
        "remote worker lan pairing token",
        "remote worker lan pairing serve localhost",
        "remote worker lan pairing serve lan",
    ]:
        require(command in commands, "ENGEL_COMMANDS missing: " + command)
    require("tools\\verify_engel_remote_worker_lan_pairing.py" in read(CODEX_VERIFY), "codex verifier missing LAN verifier")
    contract = read(CONTRACT)
    for phrase in [
        "Phase 4 Local LAN Pairing / Status Handshake",
        "Local LAN pairing/status only",
        "Manual receiver start",
        "No packet transfer/result upload",
        "No control",
        "No auto-sync/background behavior",
    ]:
        require(phrase in contract, "contract missing phrase: " + phrase)
    manifest = read(ANDROID_MANIFEST)
    if "android.permission.INTERNET" in manifest:
        report = read(REPORT)
        require(
            "Android INTERNET permission is present only for manual LAN pairing/status requests." in report,
            "report must document Android INTERNET permission boundary",
        )
    report = read(REPORT)
    for phrase in [
        "Phase 4 is LAN pairing/status only",
        "Default bind is localhost",
        "--allow-lan",
        "GET /health",
        "POST /pair",
        "Windows may prompt to allow Python on private networks",
        "does not transfer packets, upload results, execute commands, control Engel, or apply changes",
    ]:
        require(phrase in report, "report missing phrase: " + phrase)


def main() -> int:
    checks = [
        ("files", check_files),
        ("python_static_safety", check_python_static_safety),
        ("runtime_behavior", check_runtime_behavior),
        ("flutter_ui", check_flutter_ui),
        ("docs_and_integration", check_docs_and_integration),
    ]
    failures: list[str] = []
    for name, check in checks:
        try:
            check()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(f"{name}: {exc}")
            print("FAIL " + name + ": " + str(exc))
        except Exception as exc:
            failures.append(f"{name}: unexpected error: {exc}")
            print("FAIL " + name + ": unexpected error: " + str(exc))
    if failures:
        print("\nEngel Remote Worker LAN Pairing verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nEngel Remote Worker LAN Pairing verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
