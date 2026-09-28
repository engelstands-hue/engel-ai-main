#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "memory" / "ENGEL_MAIN_SERVER_MERGE_V1.json"
PROFILE_MD = ROOT / "memory" / "ENGEL_MAIN_SERVER_MERGE_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_MAIN_SERVER_MERGE_20260628.md"
MERGE_MODULE = ROOT / "engel_main_server_merge.py"
CHAT_WRAPPER = ROOT / "tools" / "run_engel_ui_chat_meeting_room_llm.py"
FLUTTER_MAIN = ROOT / "engel_flutter_main" / "lib" / "main.dart"
ROUTES = ROOT / "engel_ai_update_routes.py"
ROUTE_EXPLORER = ROOT / "engel_route_explorer.py"
SYNC_SCRIPT = ROOT / "scripts" / "Sync-EngelClusterRecordsToMainCt.ps1"
START_SCRIPT = ROOT / "scripts" / "Start-EngelMainServerMerged.ps1"
PERSISTENT_INSTALLER = ROOT / "scripts" / "Install-EngelMainPersistentAgenticSystem.ps1"
PERSISTENT_TUNNEL = ROOT / "scripts" / "Start-EngelMainServerChatTunnelPersistent.ps1"
ONE_SYSTEM_LAUNCHER = ROOT / "scripts" / "Start-EngelMainOneSystem.ps1"
ONE_SYSTEM_DEBUGGER = ROOT / "scripts" / "Test-EngelMainOneSystemConnections.ps1"
SHORTCUT_CREATOR = ROOT / "scripts" / "New-EngelMainDesktopShortcut.ps1"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    require(path.exists() and path.is_file(), "missing file: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict:
    data = json.loads(read(path))
    require(isinstance(data, dict), "JSON must be an object: " + str(path.relative_to(ROOT)))
    return data


def load_merge_module():
    spec = importlib.util.spec_from_file_location("engel_main_server_merge", MERGE_MODULE)
    require(spec is not None and spec.loader is not None, "could not load engel_main_server_merge")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_main_server_merge"] = module
    spec.loader.exec_module(module)
    return module


def check_profile() -> None:
    data = load_json(PROFILE)
    text = read(PROFILE_MD)
    require(data.get("schema") == "ENGEL_MAIN_SERVER_MERGE_V1", "schema mismatch")
    require("ACTIVE_CONTROLLER_SERVER_MERGE" in str(data.get("status")), "status must be active merge")
    controller = data.get("windows_controller_app")
    require(isinstance(controller, dict), "controller missing")
    require(controller.get("role") == "ROG controller UI / Queen access surface", "controller role mismatch")
    require(str(controller.get("current_release_exe", "")).endswith("EngelAIMain.exe"), "controller exe mismatch")
    server = data.get("server_runtime")
    require(isinstance(server, dict), "server missing")
    require(server.get("ct_id") == 246, "CT ID mismatch")
    require(server.get("ct_hostname") == "engel-ai-main", "CT hostname mismatch")
    require(server.get("ssh_host") == "192.0.2.50", "SSH host mismatch")
    require(server.get("ssh_port") == 24622, "SSH port mismatch")
    require(server.get("runtime_root") == "/opt/engel", "runtime root mismatch")
    contract = data.get("merge_contract")
    require(isinstance(contract, dict), "merge contract missing")
    require(contract.get("windows_app_is_primary_human_interface") is True, "Windows UI flag mismatch")
    require(contract.get("ct_246_is_server_runtime_home") is True, "CT runtime flag mismatch")
    require(contract.get("cluster_records_sync_to_ct") is True, "sync flag mismatch")
    require(contract.get("server_merge_does_not_create_vault_mount") is True, "vault mount safety mismatch")
    safety = data.get("safety")
    require(isinstance(safety, dict), "safety missing")
    for key, value in safety.items():
        require(value is False, "safety flag must be false: " + key)
    for needle in [
        "Windows Engel AI Main app",
        "CT `246`",
        "engel-ai-main",
        "ssh root@192.0.2.50 -p 24622",
        "/opt/engel",
        "http://127.0.0.1:8790",
        "Install-EngelMainPersistentAgenticSystem.ps1",
        "Start-EngelMainOneSystem.ps1",
        "Test-EngelMainOneSystemConnections.ps1",
        "No storage mutation",
    ]:
        require(needle in text, "profile markdown missing: " + needle)


def check_module_behavior() -> None:
    module = load_merge_module()
    status = module.server_merge_status_payload(live_probe=False)
    require(status.get("schema") == "engel_main_server_merge_status_v1", "status schema mismatch")
    require(status.get("ok") is True, "status not ok")
    require(status.get("server_peer") == "engel-ai-main CT 246", "server peer mismatch")
    require(status.get("ssh_route") == "ssh root@192.0.2.50 -p 24622", "ssh route mismatch")
    require(status.get("runtime_root") == "/opt/engel", "runtime root mismatch")
    require(status.get("tcp_probe_performed") is False, "default status must not probe")
    require(status.get("storage_mutation_performed") is False, "storage mutation must be false")
    rendered = module.render_server_merge_status(live_probe=False)
    require("Engel Main Server Merge" in rendered, "render missing title")
    require("Remote readback still requires SSH authentication" in rendered, "render missing auth note")


def check_integrations() -> None:
    chat = read(CHAT_WRAPPER)
    for needle in [
        "from engel_main_server_merge import server_merge_status_payload",
        "engel_main_server_merge",
        "engel_main_server_merge_enabled",
        "engel_main_server_peer",
        "engel_main_server_ssh_route",
    ]:
        require(needle in chat, "chat wrapper missing: " + needle)
    flutter = read(FLUTTER_MAIN)
    for needle in [
        "_engelMainServerRuntimeEnvironment",
        "ENGEL_MAIN_SERVER_ENABLED",
        "ENGEL_MAIN_SERVER_HOST",
        "ENGEL_MAIN_SERVER_SSH_PORT",
        "..._engelMainServerRuntimeEnvironment()",
    ]:
        require(needle in flutter, "Flutter main missing: " + needle)
    routes = read(ROUTES)
    for needle in [
        'ENGEL_MAIN_SERVER_MERGE_STATUS_ROUTE_ID = "engel.main_server_merge.status"',
        'target_module="engel_main_server_merge"',
        'target_function="render_server_merge_status"',
        "ENGEL_MAIN_SERVER_MERGE_STATUS_ROUTE_ID",
    ]:
        require(needle in routes, "routes missing: " + needle)
    explorer = read(ROUTE_EXPLORER)
    require("route_id.startswith(\"engel.main_server_merge\")" in explorer, "route explorer missing group")


def check_sync_and_launcher() -> None:
    sync = read(SYNC_SCRIPT)
    for needle in [
        "ENGEL_MAIN_SERVER_MERGE_V1.json",
        "ENGEL_MAIN_SERVER_MERGE_V1.md",
        "ENGEL_MAIN_SERVER_MERGE_20260628.md",
        "verify_engel_main_server_merge.py",
        "engel_main_server_merge.py",
        "engel_meeting_room_lan_server.py",
        "engel_agent_meeting_room.py",
    ]:
        require(needle in sync, "sync script missing: " + needle)
    launcher = read(START_SCRIPT)
    for needle in [
        "ENGEL_MAIN_SERVER_ENABLED",
        "ENGEL_MAIN_SERVER_HOST",
        "ENGEL_MAIN_SERVER_SSH_PORT",
        "ENGEL_MEETING_ROOM_SERVER_URL",
        "Start-Process",
        "Test-NetConnection",
    ]:
        require(needle in launcher, "launcher missing: " + needle)
    for forbidden in ["Remove-Item -Recurse", "Format-Volume", "lvcreate", "pct set", "wipefs", "mkfs"]:
        require(forbidden.lower() not in launcher.lower(), "launcher contains forbidden token: " + forbidden)
    verify = read(CODEX_VERIFY)
    require("tools\\verify_engel_main_server_merge.py" in verify, "codex verify missing merge verifier")
    installer = read(PERSISTENT_INSTALLER)
    for needle in [
        "ssh-keygen",
        "ENGEL_SSH_KEY_AUTHORIZED",
        "engel-main-chat.service",
        "engel-agent-meeting-room.service",
        "Register-ScheduledTask",
        "Start-EngelMainServerChatTunnelPersistent.ps1",
    ]:
        require(needle in installer, "persistent installer missing: " + needle)
    tunnel = read(PERSISTENT_TUNNEL)
    for needle in [
        "ExitOnForwardFailure=yes",
        "ServerAliveInterval=30",
        "24680",
        "8790",
        "Local\\EngelMainServerPersistentLink",
    ]:
        require(needle in tunnel, "persistent tunnel missing: " + needle)
    one_system = read(ONE_SYSTEM_LAUNCHER)
    for needle in [
        "Start-EngelMainServerChatTunnelPersistent.ps1",
        "Start-EngelMainServerMerged.ps1",
        "Test-EngelMainOneSystemConnections.ps1",
        "127.0.0.1:24680/health",
        "127.0.0.1:8790/health",
    ]:
        require(needle in one_system, "one-system launcher missing: " + needle)
    debugger = read(ONE_SYSTEM_DEBUGGER)
    for needle in [
        "engel-main-chat.service",
        "engel-agent-meeting-room.service",
        "ENGEL_ONE_SYSTEM_CONNECTIONS_",
        "desktop_shortcut",
    ]:
        require(needle in debugger, "one-system debugger missing: " + needle)
    shortcut = read(SHORTCUT_CREATOR)
    for needle in [
        "Engel AI Main - One System",
        "Start-EngelMainOneSystem.ps1",
        "WScript.Shell",
    ]:
        require(needle in shortcut, "shortcut creator missing: " + needle)


def check_report() -> None:
    text = read(REPORT)
    for needle in [
        "Engel Main Server Merge",
        "CT `246`",
        "engel-ai-main",
        "ssh root@192.0.2.50 -p 24622",
        "/opt/engel",
        "Install-EngelMainPersistentAgenticSystem.ps1",
        "Start-EngelMainOneSystem.ps1",
        "Test-EngelMainOneSystemConnections.ps1",
        "engel-agent-meeting-room.service",
        "http://127.0.0.1:8790",
        "does not create `/mnt/engel-vault`",
        "Verification",
    ]:
        require(needle in text, "report missing: " + needle)


def main() -> int:
    checks = [
        ("profile", check_profile),
        ("module_behavior", check_module_behavior),
        ("integrations", check_integrations),
        ("sync_and_launcher", check_sync_and_launcher),
        ("report", check_report),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print("PASS", name)
        except CheckFailure as exc:
            failures.append(f"{name}: {exc}")
            print("FAIL", name, exc)
    if failures:
        print("ENGEL_MAIN_SERVER_MERGE_VERIFY_FAIL")
        for failure in failures:
            print("-", failure)
        return 1
    print("ENGEL_MAIN_SERVER_MERGE_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
