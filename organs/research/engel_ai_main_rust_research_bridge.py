from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
RUNTIME_NAME = "engel-ai-rs"
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
    env_value = os.environ.get("ENGEL_AI_RS_EXE", "").strip().strip('"')
    candidates = [Path(env_value)] if env_value else []
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
    cleaned = str(text or "").replace("APPROVE_OVERNIGHT_LOOP_CLEANUP", "[approval-token-redacted]")
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars] + "\n\n[output truncated by Engel Main Rust research bridge]"


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


def _blocked(action: str) -> str:
    return "\n".join(
        [
            "# Engel Main Rust Research Gate",
            "",
            "Status: BLOCKED_RUST_RESEARCH_RUNNER_NOT_ENABLED",
            "Requested action: " + action,
            "Visible path: Engel Main chat -> Research command -> Rust research gate -> engel-ai-rs",
            "",
            "Safety:",
            "- no Python research loop was started",
            "- no runner process was started",
            "- no provider, network, or browser path was used",
            "- no trusted-memory write, source mutation, route mutation, or queue mutation was enabled",
            "",
            "Use `overnight loop status` for readback or `research-brain overnight-cleanup` for stale marker cleanup.",
        ]
    )


def overnight_loop_status() -> str:
    code, output, exe = _run_rust(["research-brain", "overnight-loop"])
    status = "STATUS_READBACK_READY" if code == 0 else "STATUS_READBACK_FAILED"
    return "\n".join(
        [
            "# Engel Main Rust Overnight Loop Status",
            "",
            "Status: " + status,
            "Exit code: " + str(code),
            "Visible path: Engel Main chat -> Research command -> Rust research gate -> engel-ai-rs",
            "Runtime: " + RUNTIME_NAME,
            "Executable: " + _display_path(exe),
            "",
            "Rust output:",
            _bounded_text(output).strip(),
        ]
    ).strip()


def overnight_loop_on() -> str:
    return _blocked("overnight loop on")


def overnight_loop_once() -> str:
    return _blocked("overnight loop once")


def overnight_loop_off() -> str:
    code, output, exe = _run_rust(["research-brain", "overnight-cleanup", "--json"])
    status = "STOP_REQUEST_REPLACED_WITH_RUST_STATUS_CLEANUP_DRY_RUN" if code == 0 else "STOP_REQUEST_STATUS_FAILED"
    return "\n".join(
        [
            "# Engel Main Rust Overnight Loop OFF",
            "",
            "Status: " + status,
            "Exit code: " + str(code),
            "Visible path: Engel Main chat -> Research command -> Rust research gate -> engel-ai-rs",
            "Runtime: " + RUNTIME_NAME,
            "Executable: " + _display_path(exe),
            "",
            "Safety:",
            "- no Python process was killed by this bridge",
            "- no runner process was started",
            "- Rust cleanup is dry-run unless a separate exact approval token is used",
            "",
            "Rust output:",
            _bounded_text(output).strip(),
        ]
    ).strip()
