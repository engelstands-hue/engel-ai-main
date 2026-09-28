from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_remote_worker_link_manager.py"
GUI = ROOT / "tools" / "engel_remote_worker_link_manager_gui.py"
VERIFIER = ROOT / "tools" / "verify_engel_remote_worker_link_manager.py"
LAN_PAIRING = ROOT / "engel_remote_worker_lan_pairing.py"
RUNTIME_ROOT = ROOT / "remote_workers" / "lan_link_manager"
RUNTIME_GITIGNORE = RUNTIME_ROOT / ".gitignore"
REPORT_DIR = ROOT / "reports" / "remote_worker_lan_link_manager"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_REMOTE_WORKER_PHASE_12_ENGEL_CONTROLLED_PHONE_LINK_MANAGER.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
FLUTTER_MAIN = ROOT / "mobile" / "engel_remote_worker" / "lib" / "main.dart"
FLUTTER_CLIENT = ROOT / "mobile" / "engel_remote_worker" / "lib" / "lan_pairing_client.dart"
ANDROID_MANIFEST = ROOT / "mobile" / "engel_remote_worker" / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
CLAIM_LOCK_VERIFIER = ROOT / "tools" / "verify_engel_remote_worker_claim_lock.py"

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "threading",
    "multiprocessing",
    "asyncio",
    "http",
    "ftplib",
    "smtplib",
    "openai",
    "anthropic",
}

FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "__import__",
    "compile",
    "system",
    "startfile",
    "run",
    "call",
    "check_call",
    "check_output",
}

REQUIRED_COMMANDS = [
    "remote worker link manager status",
    "remote worker link manager start",
    "remote worker link manager stop",
    "remote worker link manager restart",
    "remote worker link manager token",
    "remote worker link manager pair-status",
    "remote worker link manager phone-status",
    "remote worker link manager enable-auto-worker",
    "remote worker link manager disable-auto-worker",
    "remote worker link manager check-now",
    "remote worker link manager rust-control-bridge-status",
    "remote worker link manager enable-rust-control-bridge",
    "remote worker link manager disable-rust-control-bridge",
    "remote worker link manager rust-bridge-soak-status",
    "remote worker link manager enable-rust-bridge-soak",
    "remote worker link manager disable-rust-bridge-soak",
]

FORBIDDEN_BUTTON_LABELS = [
    "Phone Controls Engel",
    "Apply Patch",
    "Execute Command",
    "Run Route",
    "Write Memory",
    "Trust Result",
    "Bypass Verifier",
    "Open Firewall Automatically",
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
    spec = importlib.util.spec_from_file_location("engel_remote_worker_link_manager", MODULE)
    require(spec is not None and spec.loader is not None, "could not load link manager module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_remote_worker_link_manager"] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [MODULE, GUI, VERIFIER, LAN_PAIRING, RUNTIME_ROOT, RUNTIME_GITIGNORE, REPORT_DIR, REPORT]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))
    ignored = read(RUNTIME_GITIGNORE)
    require("session_state.json" in ignored, "session state must be ignored")
    require("link_manager.log" in ignored, "link manager log must be ignored")


def check_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for forbidden in [
        "netsh",
        "New-NetFirewallRule",
        "schtasks",
        "Register-ScheduledTask",
        "sc.exe",
        "CreateService",
        "Start-Service",
        "docker",
        "wsl.exe",
        "hermes",
        "shell=True",
    ]:
        require(forbidden.lower() not in source.lower(), "module contains forbidden runtime text: " + forbidden)
    for needle in [
        "Engel controls phone",
        "phone_does_not_control_engel",
        "Dedicated Engel Remote Worker",
        "safe_to_auto_apply",
        "auto_apply",
        "trusted_memory_write",
        "provider_calls",
        "validate_start",
        "LAN bind requires --allow-lan",
        "shell=False",
        "started_by_link_manager",
        "CLAIM_LOCK_VERIFIER",
    ]:
        require(needle in source, "module missing safety/control text: " + needle)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                require(root not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            require(root not in FORBIDDEN_IMPORTS, "forbidden import: " + node.module)
        elif isinstance(node, (ast.While, ast.AsyncFunctionDef)):
            raise CheckFailure("module contains forbidden hidden worker shape")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            require(name not in FORBIDDEN_CALLS, "module contains forbidden call: " + name)


def check_runtime_behavior() -> None:
    module = load_module()
    status = json.loads(module.status_text())
    require(status.get("link_status") in {"stopped", "running"}, "status missing link state")
    require(status.get("phone_role") == "Dedicated Engel Remote Worker", "status missing phone role")
    require(status.get("control_direction") == "Engel controls phone", "status missing control direction")
    require(status.get("phone_does_not_control_engel") is True, "phone authority boundary missing")
    require(status.get("auto_apply") is False, "status must keep auto_apply false")
    require(status.get("trusted_memory_write") is False, "status must block trusted-memory writes")
    require(status.get("firewall_automation") is False, "status must not automate firewall")
    try:
        module.start_link("0.0.0.0", 8765, False)
    except module.LinkManagerError as exc:
        require("--allow-lan" in str(exc), "LAN bind refusal must require --allow-lan")
    else:
        raise CheckFailure("LAN bind without --allow-lan was allowed")

    with tempfile.TemporaryDirectory() as temp_name:
        temp_root = Path(temp_name)
        original_state = module.STATE_PATH
        original_runtime = module.RUNTIME_ROOT
        original_report = module.REPORT_DIR
        original_log = module.LOG_PATH
        try:
            module.RUNTIME_ROOT = temp_root / "runtime"
            module.STATE_PATH = module.RUNTIME_ROOT / "session_state.json"
            module.LOG_PATH = module.RUNTIME_ROOT / "link_manager.log"
            module.REPORT_DIR = temp_root / "reports"
            enabled = module.enable_auto_worker()
            require(enabled.get("auto_worker_enabled") is True, "enable-auto-worker did not set visible state")
            require(enabled.get("phone_does_not_control_engel") is True, "enable-auto-worker weakened authority")
            require(enabled.get("auto_apply") is False, "enable-auto-worker enabled auto-apply")
            checked = module.check_now()
            require(checked.get("check_now_requested") is True, "check-now did not set bounded request")
            disabled = module.disable_auto_worker()
            require(disabled.get("auto_worker_enabled") is False, "disable-auto-worker did not clear state")
        finally:
            module.STATE_PATH = original_state
            module.RUNTIME_ROOT = original_runtime
            module.REPORT_DIR = original_report
            module.LOG_PATH = original_log

    original_claim = module.CLAIM_LOCK_VERIFIER
    try:
        module.CLAIM_LOCK_VERIFIER = ROOT / "tools" / "missing_claim_lock_for_verifier.py"
        try:
            module.enable_auto_worker()
        except module.LinkManagerError as exc:
            require("claim-lock" in str(exc).lower(), "missing claim-lock refusal must be explicit")
        else:
            raise CheckFailure("enable-auto-worker did not refuse without claim lock")
    finally:
        module.CLAIM_LOCK_VERIFIER = original_claim


def check_lan_pairing_protocol_integration() -> None:
    source = read(LAN_PAIRING)
    for needle in [
        "LINK_MANAGER_STATE_PATH",
        "link_manager_state",
        "link_manager_controls",
        "Engel controls phone",
        "phone_does_not_control_engel",
        "update_link_manager_seen",
    ]:
        require(needle in source, "LAN pairing missing Link Manager integration: " + needle)
    require("safe_to_auto_apply" in source, "LAN pairing must preserve safe_to_auto_apply false fields")
    require("auto_apply" in source, "LAN pairing must preserve auto_apply false fields")


def check_gui_and_flutter() -> None:
    gui = read(GUI)
    for needle in [
        "Engel Dedicated Phone Link",
        "Link status",
        "Phone role: Dedicated Engel Remote Worker",
        "Control direction: Engel controls phone",
        "Phone does not control Engel",
        "LAN ONLY",
        "ENGEL -> PHONE CONTROL ONLY",
        "PHONE CANNOT CONTROL ENGEL",
        "NO AUTO-APPLY",
        "RESULTS UNTRUSTED UNTIL REVIEW",
        "Start Link",
        "Stop Link",
        "Restart Link",
        "Rotate Token",
        "Copy Pairing Info",
        "Refresh Status",
        "Check Phone Now",
        "Enable Auto Worker",
        "Disable Auto Worker",
        "Pause Worker",
    ]:
        require(needle in gui, "GUI missing required visible text/button: " + needle)
    for label in FORBIDDEN_BUTTON_LABELS:
        require(label not in gui, "GUI contains forbidden button label: " + label)

    flutter = read(FLUTTER_MAIN) + "\n" + read(FLUTTER_CLIENT)
    for needle in [
        "Dedicated Engel Phone mode.",
        "Controlled by Engel PC.",
        "Phone does not control Engel.",
        "Engel controls phone worker mode",
        "dedicated_engel_phone_foreground",
    ]:
        require(needle in flutter, "Flutter missing dedicated phone text/status: " + needle)
    manifest = read(ANDROID_MANIFEST).lower()
    for forbidden in ["receiver", "boot_completed", "wake_lock", "foreground_service"]:
        require(forbidden not in manifest, "Android manifest contains forbidden background capability: " + forbidden)


def check_docs_and_registration() -> None:
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_remote_worker_link_manager.py" in codex, "codex verifier missing Link Manager verifier")
    report = read(REPORT)
    for needle in [
        "Remote Worker Phase 12",
        "Engel controls dedicated phone",
        "phone does not control Engel",
        "Files changed",
        "PC Link Manager commands",
        "GUI changes",
        "Flutter changes",
        "Runtime folders",
        "Token/session git-ignore behavior",
        "Auto-start setting behavior",
        "Start/stop lifecycle",
        "Phase 9 dependency",
        "Verification results",
        "Full codex verifier result",
        "Phase 12 gives Engel controlled local management",
    ]:
        require(needle in report, "Phase 12 report missing: " + needle)
    require(CLAIM_LOCK_VERIFIER.exists(), "claim-lock verifier should exist for this phase")


def main() -> int:
    checks = [
        ("files", check_files),
        ("static_safety", check_static_safety),
        ("runtime_behavior", check_runtime_behavior),
        ("lan_pairing_protocol_integration", check_lan_pairing_protocol_integration),
        ("gui_and_flutter", check_gui_and_flutter),
        ("docs_and_registration", check_docs_and_registration),
    ]
    failures: list[str] = []
    for name, check in checks:
        try:
            check()
            print("PASS", name)
        except CheckFailure as exc:
            print("FAIL", name, "-", exc)
            failures.append(f"{name}: {exc}")
    if failures:
        print("\nEngel Remote Worker Link Manager verifier FAILED")
        for failure in failures:
            print("-", failure)
        return 1
    print("\nEngel Remote Worker Link Manager verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
