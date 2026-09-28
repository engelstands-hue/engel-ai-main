from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
ROUTE_ID = "engel.local_open_chat.bounded_run_execution"
REQUEST_ROUTE_ID = "engel.local_open_chat.bounded_run_request"
PERSISTENT_SESSION_STATUS_ROUTE_ID = "engel.persistent_chat_session.status"
PERSISTENT_SESSION_START_ROUTE_ID = "engel.persistent_chat_session.start"
PERSISTENT_SESSION_STOP_ROUTE_ID = "engel.persistent_chat_session.stop"
RUNTIME_NAME = "engel-ai-rs"
SOURCE_LABEL = "Engel AI Main UI Chat Window"
APPROVAL_TOKEN = "APPROVE_LOCAL_CHAT_BOUNDED_RUN_EXECUTION"
PERSISTENT_SESSION_APPROVAL_TOKEN = "APPROVE_LOCAL_CHAT_PERSISTENT_SESSION"
APPROVAL_TOKENS = (APPROVAL_TOKEN, PERSISTENT_SESSION_APPROVAL_TOKEN)
COMMAND_PREFIX = "local chat bounded run execute "
APPROVED_COMMAND_PREFIX = "local chat bounded run execute approved "
PERSISTENT_SESSION_START_COMMAND = "local chat persistent session start"
PERSISTENT_SESSION_START_APPROVED_COMMAND = "local chat persistent session start approved"
PERSISTENT_SESSION_STOP_COMMAND = "local chat persistent session stop"
PERSISTENT_SESSION_STOP_APPROVED_COMMAND = "local chat persistent session stop approved"
STATUS_COMMANDS = {
    "local chat bounded run execution status",
    "local chat bounded run execute status",
    "engel main rust local chat status",
}
PERSISTENT_SESSION_STATUS_COMMANDS = {
    "local chat persistent session status",
    "local chat persistent session controls status",
    "engel main rust persistent session status",
}
MAX_CAPTURE_CHARS = 18000


def _is_os_drive_path(path: Path) -> bool:
    try:
        return str(path.resolve()).lower().startswith("c:\\")
    except Exception:
        return str(path).lower().startswith("c:\\")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except Exception:
        return str(path)


def _rust_exe_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_value = os.environ.get("ENGEL_AI_RS_EXE", "").strip().strip('"')
    if env_value:
        candidates.append(Path(env_value))
    candidates.extend(
        [
            ROOT / "runtime" / "temp" / "engel-rust-rewrite" / "cargo-target" / "debug" / "engel-ai-rs.exe",
            ROOT / "rust" / "engel-core-rs" / "target" / "debug" / "engel-ai-rs.exe",
        ]
    )
    return candidates


def resolve_rust_exe() -> Path | None:
    for candidate in _rust_exe_candidates():
        try:
            if candidate.exists() and candidate.is_file() and not _is_os_drive_path(candidate):
                return candidate
        except Exception:
            continue
    return None


def _off_c_state_roots() -> dict[str, Path]:
    base = ROOT / "runtime" / "temp" / "engel-rust-rewrite" / "main-ui-env"
    return {
        "cargo_home": base / "cargo-home",
        "temp": base / "temp",
        "target": ROOT / "runtime" / "temp" / "engel-rust-rewrite" / "cargo-target",
    }


def _execution_env() -> dict[str, str]:
    env = os.environ.copy()
    roots = _off_c_state_roots()
    for path in roots.values():
        path.mkdir(parents=True, exist_ok=True)
        if _is_os_drive_path(path):
            raise RuntimeError("Refusing to use OS-drive runtime path: " + str(path))
    env["CARGO_HOME"] = str(roots["cargo_home"])
    env["TEMP"] = str(roots["temp"])
    env["TMP"] = str(roots["temp"])
    env["TMPDIR"] = str(roots["temp"])
    env["CARGO_TARGET_DIR"] = str(roots["target"])
    return env


def _bounded_text(text: str, max_chars: int = MAX_CAPTURE_CHARS) -> str:
    cleaned = str(text or "")
    for token in APPROVAL_TOKENS:
        cleaned = cleaned.replace(token, "[approval-token-redacted]")
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars] + "\n\n[output truncated by Engel Main Rust bridge]"


def render_status_report() -> str:
    exe = resolve_rust_exe()
    roots = _off_c_state_roots()
    lines = [
        "# Engel Main Rust Local Chat Bridge",
        "",
        "Status: " + ("READY" if exe else "BLOCKED"),
        "Visible path: Engel Main chat -> Human Command Mode -> Rust bridge -> engel-ai-rs",
        "Runtime: " + RUNTIME_NAME,
        "Rust route: " + ROUTE_ID,
        "Request route: " + REQUEST_ROUTE_ID,
        "Persistent session status route: " + PERSISTENT_SESSION_STATUS_ROUTE_ID,
        "Persistent session start route: " + PERSISTENT_SESSION_START_ROUTE_ID,
        "Persistent session stop route: " + PERSISTENT_SESSION_STOP_ROUTE_ID,
        "Source label: " + SOURCE_LABEL,
        "Executable: " + (_display_path(exe) if exe else "missing"),
        "",
        "Commands:",
        "- local chat bounded run execution status",
        "- local chat bounded run execute <prompt>",
        "- local chat bounded run execute approved <prompt>",
        "- local chat persistent session status",
        "- local chat persistent session start",
        "- local chat persistent session start approved",
        "- local chat persistent session stop",
        "- local chat persistent session stop approved",
        "",
        "Approval boundary:",
        "- unapproved execute command returns a blocked report",
        "- unapproved session start/stop returns a blocked report",
        "- approved commands delegate to Rust exact-token gates",
        "- approval tokens are redacted from bridge output",
        "",
        "Storage boundary:",
        "- cargo_home: " + str(roots["cargo_home"]),
        "- temp: " + str(roots["temp"]),
        "- target: " + str(roots["target"]),
        "- OS-drive runtime path allowed: false",
        "",
        "Safety:",
        "- output trust: UNTRUSTED LOCAL MODEL OUTPUT",
        "- provider/cloud: disabled",
        "- browser: disabled",
        "- trusted memory writes: disabled",
        "- source mutation: disabled",
    ]
    return "\n".join(lines)


def render_bounded_run_request_route_report() -> str:
    return "\n".join(
        [
            "# Rust Local Chat Bounded Run Request Route",
            "",
            "Route: " + REQUEST_ROUTE_ID,
            "Runtime: " + RUNTIME_NAME,
            "Bridge status: readback only",
            "Visible path: Engel Main chat -> Human Command Mode -> Rust bridge -> engel-ai-rs",
            "Execution: disabled on this report surface",
            "",
            "Use `local chat bounded run execute approved <prompt>` from Engel Main chat for a real bounded run.",
        ]
    )


def render_bounded_run_execution_route_report() -> str:
    return render_status_report()


def render_persistent_session_status_route_report() -> str:
    return run_persistent_session_status()


def render_persistent_session_start_route_report() -> str:
    return _blocked_session_control_report("start")


def render_persistent_session_stop_route_report() -> str:
    return _blocked_session_control_report("stop")


def _blocked_execute_report(prompt: str) -> str:
    _ = prompt
    return "\n".join(
        [
            "# Engel Main Rust Local Chat Bounded Execution",
            "",
            "Status: BLOCKED_APPROVAL_REQUIRED",
            "Visible path: Engel Main chat -> Human Command Mode -> Rust bridge -> engel-ai-rs",
            "Rust route: " + ROUTE_ID,
            "",
            "Use:",
            "- local chat bounded run execute approved <prompt>",
            "",
            "Safety:",
            "- no Rust process was started",
            "- no model was loaded",
            "- no inference was run",
            "- no provider/cloud/browser path was used",
            "- no trusted-memory write was enabled",
        ]
    )


def run_bounded_execution(prompt: str, approved: bool) -> str:
    prompt = str(prompt or "").strip()
    if not prompt:
        return "\n".join(
            [
                "# Engel Main Rust Local Chat Bounded Execution",
                "",
                "Status: BLOCKED_EMPTY_PROMPT",
                "Use: local chat bounded run execute approved <prompt>",
            ]
        )
    if not approved:
        return _blocked_execute_report(prompt)

    exe = resolve_rust_exe()
    if exe is None:
        return render_status_report() + "\n\nExecution blocked: Rust binary is missing from approved non-OS-drive paths."

    args = [
        str(exe),
        "local-chat",
        "bounded-run-execute",
        "--source",
        SOURCE_LABEL,
        "--approve",
        APPROVAL_TOKEN,
        prompt,
    ]
    try:
        result = subprocess.run(
            args,
            cwd=str(ROOT),
            env=_execution_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=240,
        )
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + "\n" + (exc.stderr or "")
        return "\n".join(
            [
                "# Engel Main Rust Local Chat Bounded Execution",
                "",
                "Status: TIMEOUT",
                "Visible path: Engel Main chat -> Human Command Mode -> Rust bridge -> engel-ai-rs",
                "Rust route: " + ROUTE_ID,
                "Output trust: UNTRUSTED LOCAL MODEL OUTPUT",
                "",
                _bounded_text(output),
            ]
        ).strip()
    except Exception as exc:
        return "\n".join(
            [
                "# Engel Main Rust Local Chat Bounded Execution",
                "",
                "Status: ERROR",
                "Visible path: Engel Main chat -> Human Command Mode -> Rust bridge -> engel-ai-rs",
                "Rust route: " + ROUTE_ID,
                "Error: " + str(exc),
            ]
        )

    combined = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    status = "EXECUTION_PASSED_OUTPUT_UNTRUSTED" if result.returncode == 0 else "EXECUTION_FAILED_OUTPUT_UNTRUSTED"
    lines = [
        "# Engel Main Rust Local Chat Bounded Execution",
        "",
        "Status: " + status,
        "Exit code: " + str(result.returncode),
        "Visible path: Engel Main chat -> Human Command Mode -> Rust bridge -> engel-ai-rs",
        "Runtime: " + RUNTIME_NAME,
        "Rust route: " + ROUTE_ID,
        "Source label: " + SOURCE_LABEL,
        "Executable: " + _display_path(exe),
        "Output trust: UNTRUSTED LOCAL MODEL OUTPUT",
        "",
        "Rust output:",
        _bounded_text(combined).strip(),
    ]
    return "\n".join(lines).strip()


def run_persistent_session_status() -> str:
    exe = resolve_rust_exe()
    if exe is None:
        return render_status_report() + "\n\nPersistent session status blocked: Rust binary is missing from approved non-OS-drive paths."
    args = [str(exe), "local-chat", "persistent-session-status"]
    try:
        result = subprocess.run(
            args,
            cwd=str(ROOT),
            env=_execution_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=60,
        )
    except Exception as exc:
        return "\n".join(
            [
                "# Engel Main Rust Persistent Session Status",
                "",
                "Status: ERROR",
                "Visible path: Engel Main chat -> Human Command Mode -> Rust bridge -> engel-ai-rs",
                "Rust route: " + PERSISTENT_SESSION_STATUS_ROUTE_ID,
                "Error: " + str(exc),
            ]
        )
    combined = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    status = "STATUS_READBACK_READY" if result.returncode == 0 else "STATUS_READBACK_FAILED"
    return "\n".join(
        [
            "# Engel Main Rust Persistent Session Status",
            "",
            "Status: " + status,
            "Exit code: " + str(result.returncode),
            "Visible path: Engel Main chat -> Human Command Mode -> Rust bridge -> engel-ai-rs",
            "Runtime: " + RUNTIME_NAME,
            "Rust route: " + PERSISTENT_SESSION_STATUS_ROUTE_ID,
            "Source label: " + SOURCE_LABEL,
            "Executable: " + _display_path(exe),
            "",
            "Rust output:",
            _bounded_text(combined).strip(),
        ]
    ).strip()


def _blocked_session_control_report(action: str) -> str:
    return "\n".join(
        [
            "# Engel Main Rust Persistent Session " + action.title(),
            "",
            "Status: BLOCKED_APPROVAL_REQUIRED",
            "Visible path: Engel Main chat -> Human Command Mode -> Rust bridge -> engel-ai-rs",
            "Rust route: "
            + (
                PERSISTENT_SESSION_START_ROUTE_ID
                if action == "start"
                else PERSISTENT_SESSION_STOP_ROUTE_ID
            ),
            "",
            "Use:",
            f"- local chat persistent session {action} approved",
            "",
            "Safety:",
            "- no Rust process was started",
            "- no session state was changed",
            "- no model was loaded",
            "- no inference was run",
            "- no provider/cloud/browser path was used",
            "- no trusted-memory write was enabled",
        ]
    )


def run_persistent_session_control(action: str, approved: bool) -> str:
    action = "stop" if str(action).lower().strip() == "stop" else "start"
    if not approved:
        return _blocked_session_control_report(action)
    exe = resolve_rust_exe()
    if exe is None:
        return render_status_report() + f"\n\nPersistent session {action} blocked: Rust binary is missing from approved non-OS-drive paths."
    route_id = (
        PERSISTENT_SESSION_START_ROUTE_ID if action == "start" else PERSISTENT_SESSION_STOP_ROUTE_ID
    )
    args = [
        str(exe),
        "local-chat",
        f"persistent-session-{action}",
        "--source",
        SOURCE_LABEL,
        "--approve",
        PERSISTENT_SESSION_APPROVAL_TOKEN,
    ]
    try:
        result = subprocess.run(
            args,
            cwd=str(ROOT),
            env=_execution_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=60,
        )
    except Exception as exc:
        return "\n".join(
            [
                "# Engel Main Rust Persistent Session " + action.title(),
                "",
                "Status: ERROR",
                "Visible path: Engel Main chat -> Human Command Mode -> Rust bridge -> engel-ai-rs",
                "Rust route: " + route_id,
                "Error: " + str(exc),
            ]
        )
    combined = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    status = "SESSION_CONTROL_PASSED" if result.returncode == 0 else "SESSION_CONTROL_FAILED"
    return "\n".join(
        [
            "# Engel Main Rust Persistent Session " + action.title(),
            "",
            "Status: " + status,
            "Exit code: " + str(result.returncode),
            "Visible path: Engel Main chat -> Human Command Mode -> Rust bridge -> engel-ai-rs",
            "Runtime: " + RUNTIME_NAME,
            "Rust route: " + route_id,
            "Source label: " + SOURCE_LABEL,
            "Executable: " + _display_path(exe),
            "",
            "Rust output:",
            _bounded_text(combined).strip(),
        ]
    ).strip()


def handle_human_command(text: str) -> str | None:
    msg = str(text or "").strip()
    lower = msg.lower()
    if lower in STATUS_COMMANDS:
        return render_status_report()
    if lower in PERSISTENT_SESSION_STATUS_COMMANDS:
        return run_persistent_session_status()
    if lower == PERSISTENT_SESSION_START_APPROVED_COMMAND:
        return run_persistent_session_control("start", approved=True)
    if lower == PERSISTENT_SESSION_START_COMMAND:
        return run_persistent_session_control("start", approved=False)
    if lower == PERSISTENT_SESSION_STOP_APPROVED_COMMAND:
        return run_persistent_session_control("stop", approved=True)
    if lower == PERSISTENT_SESSION_STOP_COMMAND:
        return run_persistent_session_control("stop", approved=False)
    if lower.startswith(APPROVED_COMMAND_PREFIX):
        return run_bounded_execution(msg[len(APPROVED_COMMAND_PREFIX):].strip(), approved=True)
    if lower.startswith(COMMAND_PREFIX):
        return run_bounded_execution(msg[len(COMMAND_PREFIX):].strip(), approved=False)
    return None
