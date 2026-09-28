#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "engel_ai_update_routes.py"
RUNNER = ROOT / "engel_minor_tools_runner.py"
BRIDGE = ROOT / "engel_wsl_bridge.py"
NATIVE_AGENT = ROOT / "engel_native_agent_main" / "agent_module.py"
NATIVE_AGENT_DASHBOARD = ROOT / "engel_native_agent_main" / "gui_futuristic_dashboard_final_popup.py"
VERIFY_SCRIPT = ROOT / "scripts" / "codex_verify.ps1"


PHASE_B_ROUTES = {
    "engel.native_agent.launch_dashboard": {
        "function": "render_native_agent_launch_dashboard",
        "target_module": "engel_minor_tools_runner",
    },
    "engel.native_agent.launch_agent": {
        "function": "render_native_agent_launch_agent",
        "target_module": "engel_minor_tools_runner",
    },
    "engel.ide.install_to_project": {
        "function": "render_ide_install_to_project",
        "target_module": "engel_minor_tools_runner",
    },
    "engel.evolution_lab.run_example": {
        "function": "render_evolution_lab_run_example",
        "target_module": "engel_minor_tools_runner",
    },
    "engel.knowledge_graph.build": {
        "function": "render_knowledge_graph_build",
        "target_module": "engel_minor_tools_runner",
    },
    "engel.evolution_engine.run": {
        "function": "render_evolution_engine_run",
        "target_module": "engel_minor_tools_runner",
    },
}

PHASE_B_WSL_COMMAND_IDS = {
    "wsl.ubuntu.engel_evolution_lab_run_example",
    "wsl.ubuntu.engel_knowledge_graph_build",
    "wsl.ubuntu.engel_evolution_engine_run",
}


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def import_module_guarded(path: Path, name: str):
    calls: list[object] = []

    def blocked_run(*args, **kwargs):
        calls.append(("run", args, kwargs))
        raise AssertionError("subprocess.run called during import")

    def blocked_popen(*args, **kwargs):
        calls.append(("Popen", args, kwargs))
        raise AssertionError("subprocess.Popen called during import")

    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "could not create import spec for " + str(path))
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(subprocess, "run", side_effect=blocked_run), mock.patch.object(subprocess, "Popen", side_effect=blocked_popen):
        sys.modules[name] = module
        spec.loader.exec_module(module)
    require(not calls, "module executed subprocess during import: " + str(path))
    return module


def check_route_metadata() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import engel_ai_update_routes as routes
    from engel_communication_router import classify_user_input

    aliases_to_check = {
        "engel native agent launch dashboard": "engel.native_agent.launch_dashboard",
        "engel native agent launch agent": "engel.native_agent.launch_agent",
        "engel ide install": "engel.ide.install_to_project",
        "engel evolution lab run example": "engel.evolution_lab.run_example",
        "engel knowledge graph build": "engel.knowledge_graph.build",
        "engel evolution engine run": "engel.evolution_engine.run",
    }

    for route_id, expected in PHASE_B_ROUTES.items():
        meta = routes.route_metadata(route_id)
        require(meta.get("route_id") == route_id, "Phase B route missing: " + route_id)
        require(meta.get("target_module") == expected["target_module"], "Phase B route target module mismatch: " + route_id)
        require(meta.get("target_function") == expected["function"], "Phase B route function mismatch: " + route_id)
        require(meta.get("read_only") is False, "Phase B route mislabeled read-only: " + route_id)
        require(meta.get("status_only") is False, "Phase B route mislabeled status-only: " + route_id)
        require(meta.get("safe_for_ai_route") is True, "Phase B route not marked route-safe: " + route_id)
        require(meta.get("no_trusted_memory_write") is True, "Phase B route may write trusted memory: " + route_id)
        require(meta.get("no_fix_apply") is True, "Phase B route may apply fixes: " + route_id)
        require(meta.get("no_archive_mutation") is True, "Phase B route may mutate archive: " + route_id)

    for phrase, expected_route in aliases_to_check.items():
        require(routes.resolve_update_route(phrase) == expected_route, "Phase B alias did not resolve: " + phrase)
        intent = classify_user_input(phrase)
        require(intent.route_target == expected_route, "Phase B communication route mismatch: " + phrase)
        require(intent.category == "ai_update_status_request", "Phase B route should remain in Engel AI route channel: " + phrase)


def check_runner_static_safety() -> None:
    source = read(RUNNER)
    tree = ast.parse(source)
    require("Phase B native invoke implementations" in source, "runner missing Phase B native invoke block")
    require("_start_background_process" in source, "runner missing bounded host process helper")
    require("_install_ide_config_to_engel_project" in source, "runner missing IDE Companion install helper")
    require("_wsl_bridge_call(\"wsl.ubuntu.engel_evolution_lab_run_example\"" in source, "Evolution Lab route does not use WSL bridge action ID")
    require("_wsl_bridge_call(\"wsl.ubuntu.engel_knowledge_graph_build\"" in source, "Knowledge Graph route does not use WSL bridge action ID")
    require("_wsl_bridge_call(\"wsl.ubuntu.engel_evolution_engine_run\"" in source, "Evolution Engine route does not use WSL bridge action ID")
    require("target = ENGEL_APP_ROOT" in source, "IDE Companion install target is not fixed to active Engel App root")
    require("backups" in source and "phase_b_ide_install" in source, "IDE Companion install backup path missing")

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_text = ast.unparse(node.func) if hasattr(ast, "unparse") else ""
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant):
                    require(keyword.value.value is False, "runner contains shell=True")
            if func_text == "subprocess.run":
                names = {keyword.arg for keyword in node.keywords}
                require("timeout" in names, "runner subprocess.run missing timeout")
                require("capture_output" in names, "runner subprocess.run missing capture_output")
            if func_text == "subprocess.Popen":
                names = {keyword.arg for keyword in node.keywords}
                require("shell" in names, "runner Popen missing explicit shell=False")
                require("stdin" in names, "runner Popen missing stdin guard")
                require("cwd" in names, "runner Popen missing cwd")

    import_module_guarded(RUNNER, "engel_minor_tools_runner_import_guard")


def check_wsl_phase_b_command_ids() -> None:
    module = import_module_guarded(BRIDGE, "engel_wsl_bridge_phase_b_guard")
    commands = getattr(module, "APPROVED_WSL_COMMANDS")
    require(PHASE_B_WSL_COMMAND_IDS.issubset(set(commands)), "WSL Phase B command IDs missing")
    for command_id in PHASE_B_WSL_COMMAND_IDS:
        command = commands[command_id]
        joined = " ".join(str(part) for part in command.argv)
        require(command.stage3_action is True, "WSL Phase B command missing stage3_action: " + command_id)
        require(command.read_only is False, "WSL Phase B command mislabeled read-only: " + command_id)
        require(command.mutates_files is True, "WSL Phase B command missing bounded mutation marker: " + command_id)
        require(command.writes_engel_source is False, "WSL Phase B command writes Engel source: " + command_id)
        require("/tmp/engel_phase_b" in joined, "WSL Phase B command does not write under /tmp/engel_phase_b: " + command_id)
        require("sudo" not in joined.casefold(), "WSL Phase B command contains sudo: " + command_id)
        require("curl" not in joined.casefold() and "wget" not in joined.casefold(), "WSL Phase B command contains arbitrary fetch: " + command_id)
        if command_id == "wsl.ubuntu.engel_knowledge_graph_build":
            require("--backend ollama" in joined, "Knowledge Graph Phase B command must pin the local Ollama backend")
            require("127.0.0.1:11434" in joined, "Knowledge Graph Phase B command must use loopback Ollama by default")
    require(module.validate_approved_commands() == [], "WSL bridge allowlist validation failed")


def check_native_agent_launch_config_patch() -> None:
    agent = read(NATIVE_AGENT)
    dashboard = read(NATIVE_AGENT_DASHBOARD)
    require("ENGEL_NATIVE_AGENT_CONFIG_PATH" in agent, "Native Agent does not honor branded config env var")
    require("ENGEL_NATIVE_AGENT_LOG_FILE" in agent, "Native Agent does not honor branded log env var")
    require("ENGEL_NATIVE_AGENT_CONFIG_PATH" in dashboard, "Native Agent dashboard does not honor branded config env var")
    require("D:/EngelNativeAgent/config.yaml" in agent, "Native Agent fallback config path removed")


def check_full_verifier_hook() -> None:
    script = read(VERIFY_SCRIPT)
    require("tools\\verify_engel_phase_b_native_invokes.py" in script, "Codex verifier script missing Phase B native invokes verifier")


def main() -> int:
    checks = [
        ("route_metadata", check_route_metadata),
        ("runner_static_safety", check_runner_static_safety),
        ("wsl_phase_b_command_ids", check_wsl_phase_b_command_ids),
        ("native_agent_launch_config_patch", check_native_agent_launch_config_patch),
        ("full_verifier_hook", check_full_verifier_hook),
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
        print("\nEngel Phase B native invokes verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nEngel Phase B native invokes verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
