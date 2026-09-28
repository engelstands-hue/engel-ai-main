from __future__ import annotations

import ast
from pathlib import Path
import py_compile
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
APP = ROOT / "engel_app.py"
COMPANION = ROOT / "engel_companion.py"
BRIDGE = ROOT / "engel_ai_main_rust_local_chat_bridge.py"
ROUTES = ROOT / "engel_ai_update_routes.py"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")


def check_static_contracts() -> None:
    for path in [APP, COMPANION, BRIDGE, ROUTES, CODEX_VERIFY]:
        require(path.exists(), "missing path: " + str(path.relative_to(ROOT)))
        if path.suffix == ".py":
            py_compile.compile(str(path), doraise=True)
    ast.parse(read(BRIDGE))

    app = read(APP)
    bridge = read(BRIDGE)
    companion = read(COMPANION)
    routes = read(ROUTES)
    codex = read(CODEX_VERIFY)

    for needle in [
        "import engel_ai_main_rust_local_chat_bridge as rust_local_chat_bridge",
        "rust_local_chat_bridge.handle_human_command(msg)",
        "local chat bounded run execution status",
        "local chat bounded run execute approved <prompt>",
        "local chat persistent session status",
        "local chat persistent session start approved",
        "local chat persistent session stop approved",
        "lower.startswith(\"local chat bounded run execute \")",
    ]:
        require(needle in app, "engel_app.py missing: " + needle)

    for needle in [
        "Visible path: Engel Main chat -> Human Command Mode -> Rust bridge -> engel-ai-rs",
        "ROUTE_ID = \"engel.local_open_chat.bounded_run_execution\"",
        "REQUEST_ROUTE_ID = \"engel.local_open_chat.bounded_run_request\"",
        "PERSISTENT_SESSION_STATUS_ROUTE_ID = \"engel.persistent_chat_session.status\"",
        "PERSISTENT_SESSION_START_ROUTE_ID = \"engel.persistent_chat_session.start\"",
        "PERSISTENT_SESSION_STOP_ROUTE_ID = \"engel.persistent_chat_session.stop\"",
        "capture_output=True",
        "shell=False",
        "CARGO_HOME",
        "CARGO_TARGET_DIR",
        "TEMP",
        "TMPDIR",
        "APPROVAL_TOKEN",
        "PERSISTENT_SESSION_APPROVAL_TOKEN",
        "approval-token-redacted",
        "UNTRUSTED LOCAL MODEL OUTPUT",
        "Status: BLOCKED_APPROVAL_REQUIRED",
    ]:
        require(needle in bridge, "bridge module missing: " + needle)

    require(
        "APPROVE_LOCAL_CHAT_BOUNDED_RUN_EXECUTION" not in companion,
        "companion GUI must not store the Rust execution approval token",
    )
    require(
        "APPROVE_LOCAL_CHAT_PERSISTENT_SESSION" not in companion,
        "companion GUI must not store the Rust persistent session approval token",
    )
    require("subprocess.run(" not in companion, "companion GUI must not directly run the Rust process")

    for needle in [
        "ENGEL_LOCAL_OPEN_CHAT_BOUNDED_RUN_REQUEST_ROUTE_ID",
        "ENGEL_LOCAL_OPEN_CHAT_BOUNDED_RUN_EXECUTION_ROUTE_ID",
        "engel.local_open_chat.bounded_run_request",
        "engel.local_open_chat.bounded_run_execution",
        "engel.persistent_chat_session.status",
        "engel.persistent_chat_session.start",
        "engel.persistent_chat_session.stop",
        "render_bounded_run_request_route_report",
        "render_bounded_run_execution_route_report",
        "render_persistent_session_status_route_report",
        "render_persistent_session_start_route_report",
        "render_persistent_session_stop_route_report",
    ]:
        require(needle in routes, "route catalog missing: " + needle)

    require("tools\\verify_engel_main_rust_local_chat_bridge.py" in codex, "codex verifier suite missing bridge verifier")


def check_runtime_contracts() -> None:
    import engel_ai_main_rust_local_chat_bridge as bridge
    import engel_ai_update_routes
    import engel_app

    status = bridge.render_status_report()
    require(
        "Visible path: Engel Main chat -> Human Command Mode -> Rust bridge -> engel-ai-rs" in status,
        "status missing visible path",
    )
    require("OS-drive runtime path allowed: false" in status, "status missing no-C boundary")

    blocked = engel_app.handle_human_command_mode_cli("local chat bounded run execute verifier prompt")
    require("Status: BLOCKED_APPROVAL_REQUIRED" in blocked, "unapproved command did not block")
    require("no Rust process was started" in blocked, "blocked path missing no-process proof")

    session_blocked = engel_app.handle_human_command_mode_cli("local chat persistent session start")
    require("Status: BLOCKED_APPROVAL_REQUIRED" in session_blocked, "unapproved session start did not block")
    require("no session state was changed" in session_blocked, "blocked session path missing no-state-change proof")

    route_text = engel_ai_update_routes.render_update_route("engel.local_open_chat.bounded_run_execution")
    require("Engel Main Rust Local Chat Bridge" in route_text, "route catalog did not dispatch to bridge")
    request_text = engel_ai_update_routes.render_update_route("engel.local_open_chat.bounded_run_request")
    require("Execution: disabled on this report surface" in request_text, "request route report mismatch")
    session_start_text = engel_ai_update_routes.render_update_route("engel.persistent_chat_session.start")
    require("Status: BLOCKED_APPROVAL_REQUIRED" in session_start_text, "persistent session start route report mismatch")


def main() -> int:
    try:
        check_static_contracts()
        check_runtime_contracts()
    except CheckFailure as exc:
        print("ENGEL_MAIN_RUST_LOCAL_CHAT_BRIDGE_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_MAIN_RUST_LOCAL_CHAT_BRIDGE_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
