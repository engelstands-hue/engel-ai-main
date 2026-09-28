from __future__ import annotations

from pathlib import Path
import py_compile
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
APP = ROOT / "engel_app.py"
BRIDGE = ROOT / "engel_ai_main_rust_connectors_bridge.py"
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
    for path in [APP, BRIDGE]:
        require(path.exists(), "missing path: " + str(path.relative_to(ROOT)))
        py_compile.compile(str(path), doraise=True)

    app = read(APP)
    bridge = read(BRIDGE)
    codex = read(CODEX_VERIFY)

    for needle in [
        "import engel_ai_main_rust_connectors_bridge as rust_connectors_bridge",
        "return rust_connectors_bridge.account_login_plan(service)",
        "return rust_connectors_bridge.account_open_login_request(service, approval == \"APPROVE\")",
    ]:
        require(needle in app, "engel_app.py missing: " + needle)

    open_body = _function_body(app, "account_open_login")
    require("desktop_open_browser(" not in open_body, "account_open_login must not open a browser")
    require("webbrowser.open(" not in open_body, "account_open_login must not call webbrowser")

    for needle in [
        "Visible path: Engel Main chat -> Account command -> Rust connector gate -> engel-ai-rs",
        "OPEN_LOGIN_APPROVAL_TOKEN = \"APPROVE_ACCOUNT_LOGIN_OPEN_REQUEST\"",
        "connectors",
        "account-open-login-request",
        "capture_output=True",
        "shell=False",
        "CARGO_HOME",
        "CARGO_TARGET_DIR",
        "OS-drive runtime path allowed: false",
        "no browser was opened",
        "no OAuth flow was started",
        "approval-token-redacted",
    ]:
        require(needle in bridge, "bridge missing: " + needle)

    require(
        "tools\\verify_engel_main_rust_connectors_bridge.py" in codex,
        "codex verifier suite missing connector bridge verifier",
    )


def check_runtime_contracts() -> None:
    import engel_ai_main_rust_connectors_bridge as bridge
    import engel_app

    status = bridge.render_status_report()
    require("Status: READY" in status or "Status: BLOCKED" in status, "status malformed")
    require("OS-drive runtime path allowed: false" in status, "status missing no-C boundary")

    blocked = engel_app.account_open_login("gmail", "")
    require("Status: BLOCKED_APPROVAL_REQUIRED" in blocked, "unapproved open-login did not block")
    require("no browser was opened" in blocked, "blocked path missing no-browser proof")

    plan = engel_app.account_login_plan("gmail")
    require("Engel Main Rust Account Login Plan" in plan, "login plan did not use Rust bridge")

    approved = engel_app.account_open_login("gmail", "APPROVE")
    require(
        "Status: OPEN_LOGIN_REQUEST_WRITTEN_BY_RUST" in approved,
        "approved open-login did not write Rust request",
    )
    require("no browser was opened" in approved, "approved path missing no-browser proof")
    require(
        "APPROVE_ACCOUNT_LOGIN_OPEN_REQUEST" not in approved,
        "approved path leaked raw approval token",
    )


def main() -> int:
    try:
        check_static_contracts()
        check_runtime_contracts()
    except CheckFailure as exc:
        print("ENGEL_MAIN_RUST_CONNECTORS_BRIDGE_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_MAIN_RUST_CONNECTORS_BRIDGE_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
