from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
RUNTIME_NAME = "engel-ai-rs"
SOURCE_LABEL = "Engel AI Main UI Chat Window"
OPEN_LOGIN_APPROVAL_TOKEN = "APPROVE_ACCOUNT_LOGIN_OPEN_REQUEST"
MAX_CAPTURE_CHARS = 12000


def _is_os_drive_path(path: Path) -> bool:
    try:
        return str(path.resolve()).lower().startswith("c:\\")
    except Exception:
        return str(path).lower().startswith("c:\\")


def _display_path(path: Path | None) -> str:
    if path is None:
        return "missing"
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
    cleaned = str(text or "").replace(OPEN_LOGIN_APPROVAL_TOKEN, "[approval-token-redacted]")
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars] + "\n\n[output truncated by Engel Main Rust connector bridge]"


def _run_rust(args: list[str], timeout: int = 90) -> tuple[int, str, Path | None]:
    exe = resolve_rust_exe()
    if exe is None:
        return 127, "Rust binary is missing from approved non-OS-drive paths.", None
    result = subprocess.run(
        [str(exe), *args],
        cwd=str(ROOT),
        env=_execution_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        timeout=timeout,
    )
    combined = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    return result.returncode, combined, exe


def render_status_report() -> str:
    exe = resolve_rust_exe()
    roots = _off_c_state_roots()
    return "\n".join(
        [
            "# Engel Main Rust Connector Bridge",
            "",
            "Status: " + ("READY" if exe else "BLOCKED"),
            "Visible path: Engel Main chat -> Account command -> Rust connector gate -> engel-ai-rs",
            "Runtime: " + RUNTIME_NAME,
            "Executable: " + _display_path(exe),
            "",
            "Commands:",
            "- account login-plan gmail",
            "- account open-login gmail APPROVE",
            "",
            "Safety:",
            "- approved open-login writes a Rust request/receipt only",
            "- no browser is opened by Python or Rust",
            "- no OAuth flow is started",
            "- no credentials are read or printed",
            "- no provider API call is made",
            "- approval token is redacted from bridge output",
            "",
            "Storage boundary:",
            "- cargo_home: " + str(roots["cargo_home"]),
            "- temp: " + str(roots["temp"]),
            "- target: " + str(roots["target"]),
            "- OS-drive runtime path allowed: false",
        ]
    )


def account_login_plan(service: str) -> str:
    code, output, exe = _run_rust(["connectors", "account-login-plan", str(service or "gmail")])
    status = "LOGIN_PLAN_WRITTEN_BY_RUST" if code == 0 else "LOGIN_PLAN_FAILED"
    return "\n".join(
        [
            "# Engel Main Rust Account Login Plan",
            "",
            "Status: " + status,
            "Exit code: " + str(code),
            "Visible path: Engel Main chat -> Account command -> Rust connector gate -> engel-ai-rs",
            "Runtime: " + RUNTIME_NAME,
            "Executable: " + _display_path(exe),
            "",
            "Rust output:",
            _bounded_text(output).strip(),
        ]
    ).strip()


def account_open_login_request(service: str, approved: bool) -> str:
    args = ["connectors", "account-open-login-request", str(service or "gmail"), "--source", SOURCE_LABEL]
    if approved:
        args.extend(["--approve", OPEN_LOGIN_APPROVAL_TOKEN])
    code, output, exe = _run_rust(args)
    if not approved:
        status = "BLOCKED_APPROVAL_REQUIRED"
    else:
        status = "OPEN_LOGIN_REQUEST_WRITTEN_BY_RUST" if code == 0 else "OPEN_LOGIN_REQUEST_FAILED"
    return "\n".join(
        [
            "# Engel Main Rust Account Open-Login Request",
            "",
            "Status: " + status,
            "Exit code: " + str(code),
            "Visible path: Engel Main chat -> Account command -> Rust connector gate -> engel-ai-rs",
            "Runtime: " + RUNTIME_NAME,
            "Executable: " + _display_path(exe),
            "",
            "Safety:",
            "- no browser was opened",
            "- no OAuth flow was started",
            "- no credentials were read or printed",
            "- no provider API call was made",
            "",
            "Rust output:",
            _bounded_text(output).strip(),
        ]
    ).strip()
