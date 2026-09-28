from __future__ import annotations

from pathlib import Path
import py_compile
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
APP = ROOT / "engel_app.py"
BRIDGE = ROOT / "engel_ai_main_rust_research_bridge.py"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")


def final_function_body(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.rindex(marker)
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
        "import engel_ai_main_rust_research_bridge as rust_research_bridge",
        "_legacy_overnight_loop_on_python = overnight_loop_on",
        "return rust_research_bridge.overnight_loop_on()",
        "return rust_research_bridge.overnight_loop_once()",
        "return rust_research_bridge.overnight_loop_off()",
        "return rust_research_bridge.overnight_loop_status()",
    ]:
        require(needle in app, "engel_app.py missing: " + needle)

    for fn in [
        "overnight_loop_on",
        "overnight_loop_once",
        "overnight_loop_off",
        "overnight_loop_status",
    ]:
        body = final_function_body(app, fn)
        require("subprocess.Popen" not in body, fn + " must not start a Python process")
        require("subprocess.run" not in body, fn + " must not run process controls")
        require("taskkill" not in body.lower(), fn + " must not kill processes")

    for needle in [
        "Visible path: Engel Main chat -> Research command -> Rust research gate -> engel-ai-rs",
        "Status: BLOCKED_RUST_RESEARCH_RUNNER_NOT_ENABLED",
        "research-brain",
        "overnight-loop",
        "overnight-cleanup",
        "shell=False",
        "capture_output=True",
        "CARGO_HOME",
        "CARGO_TARGET_DIR",
        "no Python research loop was started",
        "no runner process was started",
    ]:
        require(needle in bridge, "bridge missing: " + needle)

    require(
        "tools\\verify_engel_main_rust_research_bridge.py" in codex,
        "codex verifier suite missing research bridge verifier",
    )


def check_runtime_contracts() -> None:
    import engel_app

    on_text = engel_app.overnight_loop_on()
    require("Status: BLOCKED_RUST_RESEARCH_RUNNER_NOT_ENABLED" in on_text, "overnight_loop_on did not block")
    require("no Python research loop was started" in on_text, "on path missing no-python proof")

    once_text = engel_app.overnight_loop_once()
    require("Status: BLOCKED_RUST_RESEARCH_RUNNER_NOT_ENABLED" in once_text, "overnight_loop_once did not block")
    require("no runner process was started" in once_text, "once path missing no-runner proof")

    off_text = engel_app.overnight_loop_off()
    require("Engel Main Rust Overnight Loop OFF" in off_text, "overnight_loop_off did not use Rust bridge")
    require("no Python process was killed" in off_text, "off path missing no-kill proof")

    status_text = engel_app.overnight_loop_status()
    require("Engel Main Rust Overnight Loop Status" in status_text, "status did not use Rust bridge")


def main() -> int:
    try:
        check_static_contracts()
        check_runtime_contracts()
    except CheckFailure as exc:
        print("ENGEL_MAIN_RUST_RESEARCH_BRIDGE_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_MAIN_RUST_RESEARCH_BRIDGE_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
