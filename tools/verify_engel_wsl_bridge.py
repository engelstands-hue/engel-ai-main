#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "engel_wsl_bridge.py"
ROUTES = ROOT / "engel_ai_update_routes.py"
ENTRY = ROOT / "engel_ai.py"
ROUTER = ROOT / "engel_communication_router.py"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CORE_MD = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md"
CORE_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
SYSTEM_INTEGRATION = ROOT / "engel_system_integration_status.py"
CODE_WORKSHOP = ROOT / "engel_code_workshop.py"
CODE_WORKSPACE = ROOT / "code_workspace"
APP = ROOT / "engel_app.py"

REQUIRED_STATUS_COMMAND_IDS = {
    "wsl.status",
    "wsl.version",
    "wsl.distros",
    "wsl.ubuntu.uname",
    "wsl.ubuntu.pwd",
    "wsl.ubuntu.python_version",
    "wsl.ubuntu.node_version",
    "wsl.ubuntu.git_version",
    "wsl.ubuntu.engel_path_exists",
    "wsl.ubuntu.list_mnt_d_workspace",
}

REQUIRED_STAGE3_ACTION_IDS = {
    "wsl.ubuntu.engel_evolution_lab_run_example",
    "wsl.ubuntu.engel_knowledge_graph_build",
    "wsl.ubuntu.engel_evolution_engine_run",
}

REQUIRED_INTERNAL_IDS = {
    "wsl.paths",
    "wsl.self_test",
}

HARD_BLOCKED_TOKENS = {
    "sudo",
    "su",
    "curl",
    "wget",
    "ssh",
    "scp",
    "rsync",
    "rm",
    "rmdir",
    "del",
    "mv",
    "cp",
    "chmod",
    "chown",
    "mount",
    "umount",
    "systemctl",
    "service",
    "nohup",
    "setsid",
    "npx",
    "docker",
    "powershell",
    "cmd.exe",
    "explorer.exe",
}

WSL_ROUTE_PHRASES = {
    "check wsl status": "engel.wsl.status",
    "wsl status": "engel.wsl.status",
    "ubuntu status": "engel.wsl.status",
    "is ubuntu installed": "engel.wsl.status",
    "is wsl installed": "engel.wsl.status",
    "show wsl distros": "engel.wsl.distros",
    "list wsl distros": "engel.wsl.distros",
    "check python in ubuntu": "engel.wsl.tools",
    "check node in ubuntu": "engel.wsl.tools",
    "check git in ubuntu": "engel.wsl.tools",
    "show linux tools": "engel.wsl.tools",
    "where is engel in ubuntu": "engel.wsl.paths",
    "where should ubuntu live": "engel.wsl.paths",
    "can ubuntu see engel": "engel.wsl.paths",
    "check /mnt/d engel path": "engel.wsl.paths",
    "run wsl self test": "engel.wsl.self_test",
    "ubuntu self test": "engel.wsl.self_test",
    "test wsl bridge": "engel.wsl.self_test",
}


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def import_bridge_guarded():
    require(BRIDGE.exists(), "engel_wsl_bridge.py missing")
    calls: list[object] = []

    def blocked_run(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("subprocess was called during import")

    spec = importlib.util.spec_from_file_location("engel_wsl_bridge_import_guard", BRIDGE)
    require(spec is not None and spec.loader is not None, "could not create bridge import spec")
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(subprocess, "run", side_effect=blocked_run):
        sys.modules[str(spec.name)] = module
        spec.loader.exec_module(module)
    require(not calls, "bridge executed a subprocess during import")
    return module


def fake_completed(argv, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)


def check_import_and_static_safety() -> None:
    module = import_bridge_guarded()
    source = read(BRIDGE)
    tree = ast.parse(source)
    require("APPROVED_WSL_COMMANDS" in source, "bridge missing command allowlist")
    require("CLI_COMMANDS" in source, "bridge missing bounded CLI command set")
    require("argparse" in source, "bridge missing bounded CLI parser")
    require("os.system" not in source, "bridge must not call os.system")
    require("subprocess.Popen" not in source, "bridge must not spawn background processes")

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_text = ast.unparse(node.func) if hasattr(ast, "unparse") else ""
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                    raise CheckFailure("bridge subprocess call enables shell execution")
            if func_text == "subprocess.run":
                keyword_names = {keyword.arg for keyword in node.keywords}
                require("timeout" in keyword_names, "subprocess.run call missing timeout")
                require("capture_output" in keyword_names, "subprocess.run call missing output capture")

    cli_commands = set(getattr(module, "CLI_COMMANDS"))
    require(cli_commands == {"status", "distros", "tools", "paths", "self-test", "json"}, "unexpected CLI command set")
    for forbidden in ["run", "exec", "shell", "command", "install", "sudo"]:
        require(forbidden not in cli_commands, "CLI exposes unsafe free-form/action command: " + forbidden)


def check_command_allowlist() -> None:
    module = import_bridge_guarded()
    commands = getattr(module, "APPROVED_WSL_COMMANDS")
    require(REQUIRED_STATUS_COMMAND_IDS.issubset(set(commands)), "approved status command id set incomplete")
    require(REQUIRED_STAGE3_ACTION_IDS.issubset(set(commands)), "approved Phase B action command id set incomplete")
    require(REQUIRED_INTERNAL_IDS.issubset(set(getattr(module, "INTERNAL_COMMAND_IDS"))), "internal command id set incomplete")
    validation_errors = module.validate_approved_commands()
    require(validation_errors == [], "allowlist validation failed: " + "; ".join(validation_errors))
    unknown = module.run_command_id("wsl.ubuntu.free_form_shell")
    require(unknown.status == "blocked", "unknown command id must be blocked")
    require(unknown.argv == (), "unknown command id must not get argv")

    for command_id, command in commands.items():
        argv = tuple(command.argv)
        require(argv, "allowlisted command has empty argv: " + command_id)
        require(argv[0] == "wsl.exe", "allowlisted command does not use wsl.exe: " + command_id)
        require(isinstance(argv, tuple), "allowlisted argv is not a tuple: " + command_id)
        require(command.timeout_seconds <= 120, "allowlisted command timeout too high: " + command_id)
        lowered = [str(part).casefold() for part in argv]
        for token in lowered:
            require(token not in HARD_BLOCKED_TOKENS, "hard-blocked token exposed in command " + command_id + ": " + token)
        joined = " ".join(lowered)
        if command_id in REQUIRED_STAGE3_ACTION_IDS:
            require(command.stage3_action is True, "Phase B action missing stage3_action flag: " + command_id)
            require(command.read_only is False, "Phase B action mislabeled read-only: " + command_id)
            require(command.mutates_files is True, "Phase B action must declare bounded mutation: " + command_id)
            require(command.writes_engel_source is False, "Phase B action must not mutate Engel source from WSL: " + command_id)
            require("/tmp/engel_phase_b" in joined, "Phase B action must write runtime output under /tmp/engel_phase_b: " + command_id)
        else:
            require(command.stage3_action is False, "status/help command mislabeled as Stage 3 action: " + command_id)
            require(command.read_only is True, "status/help command is not read-only: " + command_id)
            require(command.mutates_files is False, "status/help command mutates files: " + command_id)
            for phrase in ["pip install", "npm install", "python -m pip install", "apt install"]:
                require(phrase not in joined, "package/install sequence exposed outside Phase B action: " + command_id)


def check_missing_wsl_and_ubuntu_paths() -> None:
    module = import_bridge_guarded()

    def missing_runner(*args, **kwargs):
        raise FileNotFoundError("wsl.exe not found")

    status = module.collect_wsl_status(runner=missing_runner)
    require(status["wsl_available"] is False, "missing WSL was not reported safely")
    rendered = module.render_wsl_status(runner=missing_runner)
    require("WSL is not currently available" in rendered, "missing WSL message absent")
    require("No install was attempted" in rendered, "missing WSL install guard absent")

    calls: list[list[str]] = []

    def no_ubuntu_runner(argv, **kwargs):
        calls.append(list(argv))
        if list(argv)[:3] == ["wsl.exe", "-l", "-v"]:
            return fake_completed(argv, stdout="  NAME      STATE           VERSION\n  Debian    Stopped         2\n")
        return fake_completed(argv, stdout="WSL ready\n")

    tools = module.collect_tool_status(runner=no_ubuntu_runner)
    require(tools["wsl_available"] is True, "fake WSL should be available")
    require(tools["ubuntu_registered"] is False, "fake Ubuntu should be missing")
    require(tools["commands"] == {}, "Ubuntu tool commands should not run when Ubuntu is missing")
    require(any("Ubuntu is not installed" in warning for warning in tools["warnings"]), "missing Ubuntu warning absent")
    require(not any("-d" in call and "Ubuntu" in call for call in calls), "Ubuntu command ran despite missing distro")

    paths = module.collect_path_status(runner=no_ubuntu_runner)
    require(paths["windows_engel_project_path"] == r"D:\b.WorkSpace\Engel App", "Windows project path guard mismatch")
    require(paths["wsl_engel_project_path"] == "/mnt/d/b.WorkSpace/Engel App", "WSL project path guard mismatch")
    require(paths["preferred_ubuntu_storage_root"] == r"D:\WSL\Ubuntu", "preferred Ubuntu storage path mismatch")
    require(paths["ubuntu_must_not_live_inside_engel_repo"] is True, "Ubuntu repo placement guard missing")


def check_json_status_shape() -> None:
    module = import_bridge_guarded()

    def runner(argv, **kwargs):
        argv_list = list(argv)
        if argv_list[:3] == ["wsl.exe", "-l", "-v"]:
            return fake_completed(argv, stdout="  NAME      STATE           VERSION\n* Ubuntu    Running         2\n")
        if argv_list[-4:] == ["test", "-d", "/mnt/d/b.WorkSpace/Engel App"]:
            return fake_completed(argv, returncode=0)
        if argv_list[-2:] == ["python3", "--version"]:
            return fake_completed(argv, stdout="Python 3.12.0\n")
        if argv_list[-2:] == ["node", "--version"]:
            return fake_completed(argv, stdout="v22.0.0\n")
        if argv_list[-2:] == ["git", "--version"]:
            return fake_completed(argv, stdout="git version 2.45.0\n")
        return fake_completed(argv, stdout="ok\n")

    payload = module.collect_json_status(runner=runner)
    require(payload["bridge"] == "ENGEL_WSL_BRIDGE_V1", "JSON bridge id mismatch")
    require(payload["status"]["ubuntu_registered"] is True, "JSON Ubuntu detection mismatch")
    require(payload["path_status"]["ubuntu_can_see_engel_project"] is True, "JSON path visibility mismatch")
    require(payload["safety"]["allowlisted_commands_only"] is True, "JSON safety allowlist flag missing")
    require(payload["safety"]["status_routes_read_only"] is True, "JSON safety status route flag missing")
    require(payload["safety"]["phase_b_stage3_actions_available"] is True, "JSON safety Phase B flag missing")
    rendered = module.render_json_status(runner=runner)
    decoded = json.loads(rendered)
    require(decoded["bridge"] == "ENGEL_WSL_BRIDGE_V1", "rendered JSON bridge id mismatch")


def check_route_coverage() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import engel_ai_update_routes as routes
    from engel_communication_router import classify_user_input

    required_ids = {
        "engel.wsl.status",
        "engel.wsl.distros",
        "engel.wsl.tools",
        "engel.wsl.paths",
        "engel.wsl.self_test",
    }
    require(required_ids.issubset(set(routes.ROUTE_BY_ID)), "WSL route IDs not registered")
    require(len(routes.UPDATE_ROUTES) >= 60, "route count unexpectedly reduced")
    for route_id in required_ids:
        meta = routes.route_metadata(route_id)
        require(meta.get("target_module") == "engel_wsl_bridge", "WSL route target module mismatch: " + route_id)
        require(meta.get("read_only") is True, "WSL route not read-only: " + route_id)
        require(meta.get("status_only") is True, "WSL route not status-only: " + route_id)
        require(meta.get("safe_for_ai_route") is True, "WSL route not safe for AI route: " + route_id)
        require(meta.get("no_memory_promotion") is True, "WSL route allows memory promotion: " + route_id)
        require(meta.get("no_trusted_memory_write") is True, "WSL route allows trusted-memory write: " + route_id)
        require(meta.get("no_fix_apply") is True, "WSL route allows fix apply: " + route_id)
        require(meta.get("no_archive_mutation") is True, "WSL route allows archive mutation: " + route_id)
        require(meta.get("no_provider_model_network") is True, "WSL route allows provider/model/network: " + route_id)
        require(meta.get("no_background_worker") is True, "WSL route allows background worker: " + route_id)
        require(meta.get("no_visible_ui_change") is True, "WSL route allows UI change: " + route_id)

    for phrase, route_id in WSL_ROUTE_PHRASES.items():
        resolved = routes.resolve_update_route(phrase)
        require(resolved == route_id, "update route mismatch for phrase: " + phrase)
        intent = classify_user_input(phrase)
        require(intent.route_target == route_id, "communication router mismatch for phrase: " + phrase)
        require(intent.category == "ai_update_status_request", "WSL phrase should route as update/status request: " + phrase)


def run_existing_verifier(path: str, timeout: int = 120) -> None:
    result = subprocess.run(
        [sys.executable, path],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    require(result.returncode == 0, path + " failed: " + (result.stdout + result.stderr)[-2000:])


def check_current_engel_preservation() -> None:
    run_existing_verifier("tools\\verify_engel_ai_run_entry.py")
    run_existing_verifier("tools\\verify_engel_ai_update_routes.py")
    run_existing_verifier("tools\\verify_engel_code_companion.py", timeout=180)
    run_existing_verifier("tools\\verify_engel_ai_growth_gui_tabs.py")
    require(CODE_WORKSHOP.exists(), "Code Companion backend engel_code_workshop.py missing")
    require(CODE_WORKSPACE.exists(), "Code Companion sandbox folder missing")
    app_text = read(APP)
    require("WSL Bridge" not in app_text, "WSL UI was added to engel_app.py")


def check_documentation_and_full_verifier_hook() -> None:
    commands = read(COMMANDS)
    for needle in [
        "Engel AI WSL Bridge routes",
        "check wsl status",
        "show wsl distros",
        "check python in ubuntu",
        "where is engel in ubuntu",
        "run wsl self test",
        "engel_wsl_bridge.py",
        "allowlisted",
        "timeout-bounded",
        "Phase B",
    ]:
        require(needle in commands, "ENGEL_COMMANDS missing WSL bridge text: " + needle)
    core_md = read(CORE_MD)
    core_json = json.loads(read(CORE_JSON))
    require("Engel WSL Bridge V1" in core_md, "Core Continuity markdown missing WSL Bridge")
    require("controlled local bridge from Engel AI to WSL Ubuntu" in core_md, "Core Continuity markdown missing bridge summary")
    node = core_json.get("engel_wsl_bridge_v1")
    require(isinstance(node, dict), "Core Continuity JSON missing engel_wsl_bridge_v1")
    require(node.get("windows_engel_project_path") == r"D:\b.WorkSpace\Engel App", "Core Continuity JSON Windows path mismatch")
    require(node.get("preferred_ubuntu_storage_root") == r"D:\WSL\Ubuntu", "Core Continuity JSON Ubuntu path mismatch")
    require(node.get("wsl_engel_project_path") == "/mnt/d/b.WorkSpace/Engel App", "Core Continuity JSON WSL path mismatch")

    integration = read(SYSTEM_INTEGRATION)
    require("wsl_bridge" in integration, "System Integration missing WSL bridge system")
    require("Phase B" in integration, "System Integration missing WSL bridge Phase B boundary text")
    verify_script = read(ROOT / "scripts" / "codex_verify.ps1")
    require("tools\\verify_engel_wsl_bridge.py" in verify_script, "codex verifier script missing WSL bridge verifier")


def main() -> int:
    checks = [
        ("import_and_static_safety", check_import_and_static_safety),
        ("command_allowlist", check_command_allowlist),
        ("missing_wsl_and_ubuntu_paths", check_missing_wsl_and_ubuntu_paths),
        ("json_status_shape", check_json_status_shape),
        ("route_coverage", check_route_coverage),
        ("current_engel_preservation", check_current_engel_preservation),
        ("documentation_and_full_verifier_hook", check_documentation_and_full_verifier_hook),
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
            failures.append(f"{name}: unexpected error: {type(exc).__name__}: {exc}")
            print("FAIL " + name + ": unexpected error: " + type(exc).__name__ + ": " + str(exc))
    if failures:
        print("\nEngel WSL Bridge verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nEngel WSL Bridge verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
