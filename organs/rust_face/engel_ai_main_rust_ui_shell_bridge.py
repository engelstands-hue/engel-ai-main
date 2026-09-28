from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
RUNTIME_NAME = "engel-ai-rs"
VISIBLE_PATH = "Engel Main chat -> UI/Main command -> Rust UI shell/Main gate -> engel-ai-rs"
MAX_CAPTURE_CHARS = 16000
DEFAULT_MEMORY_ROOT = ROOT / "runtime" / "engel_memory"

ACTION_APPROVALS = {
    "install": "APPROVE_ENGEL_MAIN_INSTALL",
    "build": "APPROVE_ENGEL_MAIN_BUILD",
    "dev-start": "APPROVE_ENGEL_MAIN_DEV_START",
    "dev-stop": "APPROVE_ENGEL_MAIN_DEV_STOP",
    "tauri-build": "APPROVE_ENGEL_MAIN_TAURI_BUILD",
}

MAIN_READ_COMMANDS = {
    "engel main status": ["engel-main", "status"],
    "engel desktop status": ["engel-main", "status"],
    "engel companion status": ["engel-main", "status"],
    "show engel main": ["engel-main", "status"],
    "engel main health": ["engel-main", "status"],
    "engel main version": ["engel-main", "version"],
    "engel companion version": ["engel-main", "version"],
    "engel main binaries": ["engel-main", "binaries"],
    "engel main bins": ["engel-main", "binaries"],
    "list engel main binaries": ["engel-main", "binaries"],
    "engel main bring up": ["engel-main", "bring-up"],
    "engel companion bring up": ["engel-main", "bring-up"],
    "bring up engel main": ["engel-main", "bring-up"],
    "engel main setup": ["engel-main", "bring-up"],
    "engel main guide": ["engel-main", "bring-up"],
    "engel main verify": ["engel-main", "verify"],
}

MAIN_ACTION_COMMANDS = {
    "engel main install": "install",
    "install engel main": "install",
    "engel main deps install": "install",
    "pnpm install engel main": "install",
    "engel main build": "build",
    "engel companion build": "build",
    "build engel main": "build",
    "compile engel main": "build",
    "engel main web build": "build",
    "engel main dev start": "dev-start",
    "engel main start": "dev-start",
    "start engel main": "dev-start",
    "launch engel main": "dev-start",
    "engel main dev": "dev-start",
    "open engel companion": "dev-start",
    "engel main dev stop": "dev-stop",
    "engel main stop": "dev-stop",
    "stop engel main": "dev-stop",
    "kill engel main": "dev-stop",
    "close engel companion": "dev-stop",
    "engel main tauri build": "tauri-build",
    "engel companion tauri build": "tauri-build",
    "build engel main desktop": "tauri-build",
    "engel main full build": "tauri-build",
    "engel main desktop build": "tauri-build",
}

UI_SHELL_COMMANDS = {
    "ui shell status": ["ui-shell", "status"],
    "engel ui shell status": ["ui-shell", "status"],
    "ui shell command bridge": ["ui-shell", "command-bridge"],
    "engel ui shell command bridge": ["ui-shell", "command-bridge"],
    "ui shell verify": ["ui-shell", "verify"],
    "engel ui shell verify": ["ui-shell", "verify"],
    "verify ui shell": ["ui-shell", "verify"],
}

SYSTEM_READ_COMMANDS = {
    "device cluster status": (
        "Engel Device Cluster Rust Status",
        ["device-cluster", "status"],
        "RUST_DEVICE_CLUSTER_STATUS",
    ),
    "device cluster verify": (
        "Engel Device Cluster Rust Verify",
        ["device-cluster", "verify"],
        "RUST_DEVICE_CLUSTER_VERIFY",
    ),
    "shared room status": (
        "Engel Shared Room Rust Status",
        ["shared-room", "status"],
        "RUST_SHARED_ROOM_STATUS",
    ),
    "shared room tail": (
        "Engel Shared Room Rust Tail",
        ["shared-room", "tail", "--limit", "5"],
        "RUST_SHARED_ROOM_TAIL",
    ),
    "runtime readiness status": (
        "Engel Runtime Readiness Rust Status",
        ["runtime-readiness", "status"],
        "RUST_RUNTIME_READINESS_STATUS",
    ),
    "ai runtime readiness status": (
        "Engel Runtime Readiness Rust Status",
        ["runtime-readiness", "status"],
        "RUST_RUNTIME_READINESS_STATUS",
    ),
    "runtime readiness cuda-x": (
        "Engel Runtime Readiness CUDA-X Rust Status",
        ["runtime-readiness", "cuda-x"],
        "RUST_RUNTIME_READINESS_CUDA_X",
    ),
    "cuda-x readiness": (
        "Engel Runtime Readiness CUDA-X Rust Status",
        ["runtime-readiness", "cuda-x"],
        "RUST_RUNTIME_READINESS_CUDA_X",
    ),
    "cosmos3 status": (
        "Engel Cosmos3 Rust Status",
        ["cosmos3", "status"],
        "RUST_COSMOS3_STATUS",
    ),
    "cosmos 3 status": (
        "Engel Cosmos3 Rust Status",
        ["cosmos3", "status"],
        "RUST_COSMOS3_STATUS",
    ),
    "cosmos3 collection": (
        "Engel Cosmos3 Rust Collection",
        ["cosmos3", "collection"],
        "RUST_COSMOS3_COLLECTION",
    ),
    "runpod status": (
        "Engel RunPod Rust Status",
        ["runpod", "status"],
        "RUST_RUNPOD_STATUS",
    ),
    "run pod status": (
        "Engel RunPod Rust Status",
        ["runpod", "status"],
        "RUST_RUNPOD_STATUS",
    ),
    "engel runpod status": (
        "Engel RunPod Rust Status",
        ["runpod", "status"],
        "RUST_RUNPOD_STATUS",
    ),
    "runpod init": (
        "Engel RunPod Rust Init",
        ["runpod", "init"],
        "RUST_RUNPOD_INIT",
    ),
    "setup runpod for engel": (
        "Engel RunPod Rust Init",
        ["runpod", "init"],
        "RUST_RUNPOD_INIT",
    ),
    "runpod preflight": (
        "Engel RunPod Rust Preflight Plan",
        ["runpod", "preflight-plan"],
        "RUST_RUNPOD_PREFLIGHT_PLAN",
    ),
    "runpod verify": (
        "Engel RunPod Rust Verify",
        ["runpod", "verify"],
        "RUST_RUNPOD_VERIFY",
    ),
}

RUNPOD_LIVE_COMMANDS = {
    "runpod stretch",
    "engel runpod stretch",
    "runpod live stretch",
    "stretch runpod",
    "test runpod",
    "engel runpod test",
}


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
    f_root = DEFAULT_MEMORY_ROOT
    base = (
        f_root
        if f_root.drive and Path(f_root.drive + "/").exists()
        else ROOT / "runtime" / "temp" / "engel-rust-rewrite" / "main-ui-env"
    )
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
    memory_root = DEFAULT_MEMORY_ROOT if DEFAULT_MEMORY_ROOT.drive and Path(DEFAULT_MEMORY_ROOT.drive + "/").exists() else ROOT / "runtime" / "engel_memory"
    env.setdefault("ENGEL_HOME", str(memory_root / "engel-home"))
    env.setdefault("ENGEL_RUNPOD_ROOT", str(memory_root / "runpod"))
    env.setdefault("ENGEL_RUNPOD_API_KEY_FILE", str(memory_root / "secrets" / "runpod_api_key.txt"))
    return env


def _bounded_text(text: str, max_chars: int = MAX_CAPTURE_CHARS) -> str:
    cleaned = str(text or "")
    for token in ACTION_APPROVALS.values():
        cleaned = cleaned.replace(token, "[approval-token-redacted]")
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars] + "\n\n[output truncated by Engel Main Rust UI shell bridge]"


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


def _python_exe() -> Path | str:
    repo_python = ROOT / "runtime" / "python310" / "python.exe"
    if repo_python.exists() and repo_python.is_file() and not _is_os_drive_path(repo_python):
        return repo_python
    return os.environ.get("PYTHON", "python")


def _run_python_tool(args: list[str], timeout: int = 300) -> tuple[int, str, Path | None]:
    exe = _python_exe()
    exe_path = exe if isinstance(exe, Path) else None
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
    return result.returncode, combined, exe_path


def _rust_report(title: str, args: list[str], status_ok: str = "RUST_UI_SHELL_RESULT") -> str:
    code, output, exe = _run_rust(args)
    status = status_ok if code == 0 else "RUST_UI_SHELL_FAILED"
    return "\n".join(
        [
            "# " + title,
            "",
            "Status: " + status,
            "Command marker: " + status_ok,
            "Exit code: " + str(code),
            "Visible path: " + VISIBLE_PATH,
            "Runtime: " + RUNTIME_NAME,
            "Executable: " + _display_path(exe),
            "",
            "Safety:",
            "- no Python legacy runner was used",
            "- no Node, pnpm, Cargo, or Tauri command was started",
            "- no dev server was started or stopped",
            "- no provider, model, network, or browser call was made",
            "- no trusted-memory, route, source, or queue mutation was enabled",
            "",
            "Rust output:",
            _bounded_text(output).strip(),
        ]
    ).strip()


def render_runpod_stretch() -> str:
    code, output, exe = _run_python_tool(["tools/run_engel_runpod_stretch.py"], timeout=420)
    status = "ENGEL_RUNPOD_STRETCH_LIVE_OK" if code == 0 else "ENGEL_RUNPOD_STRETCH_LIVE_FAILED"
    return "\n".join(
        [
            "# Engel RunPod Live Stretch",
            "",
            "Status: " + status,
            "Exit code: " + str(code),
            "Visible path: Engel Main chat -> UI/Main command -> Rust UI shell bridge -> Engel Agent provider resolver -> RunPod OpenAI-compatible endpoint",
            "Runtime: " + RUNTIME_NAME,
            "Python: " + _display_path(exe),
            "",
            "Safety:",
            "- explicit live RunPod inference test requested by operator",
            "- API key value is not printed",
            "- receipts stay under D:\\b.WorkSpace\\Engel App\\runtime\\runpod\\receipts and sync to CT246 reports",
            "- no C: storage is used for Engel RunPod config, secrets, or receipts",
            "- no Pod is created, stopped, or terminated",
            "",
            "Stretch output:",
            _bounded_text(output).strip(),
        ]
    ).strip()


def render_status_report() -> str:
    exe = resolve_rust_exe()
    roots = _off_c_state_roots()
    return "\n".join(
        [
            "# Engel Main Rust UI Shell Bridge",
            "",
            "Status: " + ("READY" if exe else "BLOCKED"),
            "Visible path: " + VISIBLE_PATH,
            "Runtime: " + RUNTIME_NAME,
            "Executable: " + _display_path(exe),
            "",
            "Commands:",
            "- ui shell status",
            "- ui shell command bridge",
            "- ui shell verify",
            "- engel main status",
            "- engel main version",
            "- engel main binaries",
            "- engel main bring up",
            "- engel main install",
            "- engel main build",
            "- engel main dev start",
            "- engel main dev stop",
            "- engel main tauri build",
            "- device cluster status",
            "- device cluster verify",
            "- shared room status",
            "- runtime readiness status",
            "- runtime readiness cuda-x",
            "- cosmos3 status",
            "- runpod status",
            "- runpod init",
            "- runpod preflight",
            "- runpod verify",
            "- runpod stretch",
            "- append `approved` to an Engel Main action command for a Rust manual-required gate response",
            "",
            "Storage boundary:",
            "- cargo_home: " + str(roots["cargo_home"]),
            "- temp: " + str(roots["temp"]),
            "- target: " + str(roots["target"]),
            "- OS-drive runtime path allowed: false",
        ]
    )


def _main_action_args(action: str, approved: bool) -> list[str]:
    args = ["engel-main", action, "--json"]
    if approved:
        args.extend(["--apply", "--approve", ACTION_APPROVALS[action]])
    return args


def _render_main_action(action: str, approved: bool = False) -> str:
    status = "RUST_MAIN_ACTION_GATE_APPROVED_MANUAL_ONLY" if approved else "RUST_MAIN_ACTION_GATE_DRY_RUN"
    title = "Engel Main Rust " + action.replace("-", " ").title()
    return _rust_report(title, _main_action_args(action, approved), status)


def render_engel_main_status() -> str:
    return _rust_report("Engel Main Rust Status", ["engel-main", "status"], "RUST_MAIN_STATUS")


def render_engel_main_version() -> str:
    return _rust_report("Engel Main Rust Version", ["engel-main", "version"], "RUST_MAIN_VERSION")


def render_engel_main_binaries() -> str:
    return _rust_report("Engel Main Rust Binaries", ["engel-main", "binaries"], "RUST_MAIN_BINARIES")


def render_engel_main_bring_up() -> str:
    return _rust_report("Engel Main Rust Bring-Up", ["engel-main", "bring-up"], "RUST_MAIN_BRING_UP")


def render_engel_main_install(approved: bool = False) -> str:
    return _render_main_action("install", approved)


def render_engel_main_build(approved: bool = False) -> str:
    return _render_main_action("build", approved)


def render_engel_main_dev_start(approved: bool = False) -> str:
    return _render_main_action("dev-start", approved)


def render_engel_main_dev_stop(approved: bool = False) -> str:
    return _render_main_action("dev-stop", approved)


def render_engel_main_tauri_build(approved: bool = False) -> str:
    return _render_main_action("tauri-build", approved)


def render_ui_shell_status() -> str:
    return _rust_report("Engel UI Shell Rust Status", ["ui-shell", "status"], "RUST_UI_SHELL_STATUS")


def render_ui_shell_command_bridge() -> str:
    return _rust_report(
        "Engel UI Shell Rust Command Bridge",
        ["ui-shell", "command-bridge"],
        "RUST_UI_SHELL_COMMAND_BRIDGE",
    )


def render_ui_shell_verify() -> str:
    return _rust_report("Engel UI Shell Rust Verify", ["ui-shell", "verify"], "RUST_UI_SHELL_VERIFY")


def _is_approved_action(raw: str, action: str) -> bool:
    lower = raw.lower()
    token = ACTION_APPROVALS[action]
    return lower.endswith(" approved") or lower.endswith(" approve") or token.lower() in lower


def handle_human_command(text: str) -> str | None:
    raw = str(text or "").strip()
    lower = raw.lower()
    if not lower:
        return None
    if lower in {"engel main rust ui bridge status", "rust ui shell bridge status"}:
        return render_status_report()
    if lower in UI_SHELL_COMMANDS:
        args = UI_SHELL_COMMANDS[lower]
        if args[-1] == "status":
            return render_ui_shell_status()
        if args[-1] == "command-bridge":
            return render_ui_shell_command_bridge()
        return render_ui_shell_verify()
    if lower in RUNPOD_LIVE_COMMANDS:
        return render_runpod_stretch()
    if lower in SYSTEM_READ_COMMANDS:
        title, args, status_ok = SYSTEM_READ_COMMANDS[lower]
        return _rust_report(title, args, status_ok)
    if lower in MAIN_READ_COMMANDS:
        args = MAIN_READ_COMMANDS[lower]
        if args[-1] == "status":
            return render_engel_main_status()
        if args[-1] == "version":
            return render_engel_main_version()
        if args[-1] == "binaries":
            return render_engel_main_binaries()
        if args[-1] == "bring-up":
            return render_engel_main_bring_up()
        return _rust_report("Engel Main Rust Verify", args, "RUST_MAIN_VERIFY")
    for command, action in MAIN_ACTION_COMMANDS.items():
        if lower == command or lower.startswith(command + " "):
            approved = _is_approved_action(raw, action)
            return _render_main_action(action, approved)
    return None
