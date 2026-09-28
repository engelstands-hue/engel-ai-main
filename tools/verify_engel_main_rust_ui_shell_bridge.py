from __future__ import annotations

from pathlib import Path
import py_compile
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
APP = ROOT / "engel_app.py"
BRIDGE = ROOT / "engel_ai_main_rust_ui_shell_bridge.py"
ROUTES = ROOT / "engel_ai_update_routes.py"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")


def _function_body(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.index(marker)
    next_def = source.find("\ndef ", start + len(marker))
    if next_def == -1:
        return source[start:]
    return source[start:next_def]


def check_static_contracts() -> None:
    for path in [APP, BRIDGE, ROUTES]:
        require(path.exists(), "missing path: " + str(path.relative_to(ROOT)))
        py_compile.compile(str(path), doraise=True)

    app = read(APP)
    bridge = read(BRIDGE)
    routes = read(ROUTES)
    codex = read(CODEX_VERIFY)

    for needle in [
        "import engel_ai_main_rust_ui_shell_bridge as rust_ui_shell_bridge",
        "rust_ui_shell_reply = rust_ui_shell_bridge.handle_human_command(msg)",
        "engel main rust ui bridge status",
        "ui shell command bridge",
        "engel main dev start approved",
    ]:
        require(needle in app, "engel_app.py missing: " + needle)

    for needle in [
        "VISIBLE_PATH = \"Engel Main chat -> UI/Main command -> Rust UI shell/Main gate -> engel-ai-rs\"",
        "ACTION_APPROVALS",
        "subprocess.run(",
        "shell=False",
        "CARGO_HOME",
        "CARGO_TARGET_DIR",
        "OS-drive runtime path allowed: false",
        "no Node, pnpm, Cargo, or Tauri command was started",
        "render_engel_main_dev_start",
        "render_ui_shell_command_bridge",
        "SYSTEM_READ_COMMANDS",
        "device cluster status",
        "runtime readiness cuda-x",
        "cosmos3 status",
        "runpod status",
        "runpod verify",
        "runpod stretch",
        "ENGEL_RUNPOD_STRETCH_LIVE_OK",
    ]:
        require(needle in bridge, "bridge missing: " + needle)

    require(
        'target_module="engel_ai_main_rust_ui_shell_bridge"' in routes,
        "Engel Main route metadata does not target the Rust UI shell bridge",
    )
    engel_main_dispatch = routes[
        routes.index("if route_id == ENGEL_MAIN_STATUS_ROUTE_ID:") :
        routes.index("if route_id == ENGEL_LAN_STATUS_ROUTE_ID:")
    ]
    require(
        "engel_engel_main_runner" not in engel_main_dispatch,
        "Engel Main update-route dispatch still imports the legacy runner",
    )
    require(
        "tools\\verify_engel_main_rust_ui_shell_bridge.py" in codex,
        "codex verifier suite missing UI shell bridge verifier",
    )


def check_runtime_contracts() -> None:
    import engel_ai_main_rust_ui_shell_bridge as bridge
    import engel_app

    status = bridge.render_status_report()
    require("Status: READY" in status or "Status: BLOCKED" in status, "status malformed")
    require("OS-drive runtime path allowed: false" in status, "status missing no-C boundary")

    ui_status = engel_app.handle_human_command_mode_cli("ui shell status")
    require("Engel UI Shell Rust Status" in ui_status, "ui shell status did not use Rust bridge")
    require("Visible path: " in ui_status, "ui shell status missing visible path")
    require("no Node, pnpm, Cargo, or Tauri command was started" in ui_status, "ui status missing no-process proof")

    main_status = engel_app.handle_human_command_mode_cli("engel main status")
    require("Engel Main Rust Status" in main_status, "engel main status did not use Rust bridge")

    device_cluster = engel_app.handle_human_command_mode_cli("device cluster status")
    require(
        "Engel Device Cluster Rust Status" in device_cluster,
        "device cluster status did not use Rust bridge",
    )
    require("RUST_DEVICE_CLUSTER_STATUS" in device_cluster, "device cluster status missing Rust marker")

    shared_room = engel_app.handle_human_command_mode_cli("shared room status")
    require("Engel Shared Room Rust Status" in shared_room, "shared room status did not use Rust bridge")
    require("RUST_SHARED_ROOM_STATUS" in shared_room, "shared room status missing Rust marker")

    runtime_readiness = engel_app.handle_human_command_mode_cli("runtime readiness status")
    require(
        "Engel Runtime Readiness Rust Status" in runtime_readiness,
        "runtime readiness status did not use Rust bridge",
    )
    require("RUST_RUNTIME_READINESS_STATUS" in runtime_readiness, "runtime readiness missing Rust marker")

    cosmos3 = engel_app.handle_human_command_mode_cli("cosmos3 status")
    require("Engel Cosmos3 Rust Status" in cosmos3, "cosmos3 status did not use Rust bridge")
    require("RUST_COSMOS3_STATUS" in cosmos3, "cosmos3 status missing Rust marker")

    runpod_status = engel_app.handle_human_command_mode_cli("runpod status")
    require("Engel RunPod Rust Status" in runpod_status, "runpod status did not use Rust bridge")
    require("RUST_RUNPOD_STATUS" in runpod_status, "runpod status missing Rust marker")
    require("api_key_value_visible: false" in runpod_status, "runpod status must not expose key values")

    runpod_verify = engel_app.handle_human_command_mode_cli("runpod verify")
    require("Engel RunPod Rust Verify" in runpod_verify, "runpod verify did not use Rust bridge")
    require("RUST_RUNPOD_VERIFY" in runpod_verify, "runpod verify missing Rust marker")

    dry = engel_app.handle_human_command_mode_cli("engel main dev start")
    require("RUST_MAIN_ACTION_GATE_DRY_RUN" in dry, "dev start did not return Rust dry-run gate")
    require("pnpm_dev_started" in dry, "dev start output missing Rust action payload")
    require("true" not in _extract_json_bool_line(dry, "pnpm_dev_started"), "dev start attempted pnpm")

    approved = engel_app.handle_human_command_mode_cli("engel main dev start approved")
    require(
        "RUST_MAIN_ACTION_GATE_APPROVED_MANUAL_ONLY" in approved,
        "approved dev start did not return manual-only Rust gate",
    )
    require("APPROVE_ENGEL_MAIN_DEV_START" not in approved, "approval token leaked in bridge output")
    require("manual_dev_start_required" in approved, "approved output missing manual-only marker")
    require("process_started" in approved, "approved output missing process-start proof")

    routed = engel_app.engel_ai_update_route_status("engel.engel_main.dev_start")
    require("Engel Main Rust Dev Start" in routed, "update-route fallback did not use Rust bridge")
    require("RUST_MAIN_ACTION_GATE_DRY_RUN" in routed, "update-route fallback did not return Rust dry-run")


def _extract_json_bool_line(text: str, key: str) -> str:
    for line in str(text or "").splitlines():
        if '"' + key + '"' in line or key + ":" in line:
            return line.strip()
    return ""


def main() -> int:
    try:
        check_static_contracts()
        check_runtime_contracts()
    except CheckFailure as exc:
        print("ENGEL_MAIN_RUST_UI_SHELL_BRIDGE_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_MAIN_RUST_UI_SHELL_BRIDGE_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
