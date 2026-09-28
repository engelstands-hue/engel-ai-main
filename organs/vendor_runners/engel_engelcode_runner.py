"""Engel AI ↔ bundled engelcode (Rust TUI coding agent) integration runner.

Backs the ``engel.engelcode.*`` routes registered in
``engel_ai_update_routes``. The vendored tree at
``D:\\b.WorkSpace\\Engel App\\engelcode_main`` is a fork of
jcode, case-preservingly rebranded (jcode→engelcode across
JCODE/Jcode/jcode/JCode variants — 671 files, 7,392 textual
substitutions, 80 path renames). engelcode is a Rust workspace
(50+ crates) implementing a blazing-fast TUI coding agent
with multi-model, swarm coordination, and ~30 tools.

Runtime requirement: ``cargo`` must be on PATH (install via
https://rustup.rs/). First-time ``cargo build --release`` for
this workspace can take 10-30 minutes; subsequent builds are
incremental. Routes that need the toolchain or a built binary
degrade gracefully when those are missing.

Public surface:

    render_engelcode_status()     — toolchain + build presence
    render_engelcode_version()    — Cargo.toml version (no build)
    render_engelcode_crates()     — workspace crate inventory
    render_engelcode_build()      — cargo build --release (blocking)
    render_engelcode_invoke()     — run the built binary
    render_engelcode_bring_up()   — Rust install + build walkthrough
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

ENGELCODE_ROOT: Path = Path(__file__).resolve().parent / "engelcode_main"
RELEASE_BINARY = ENGELCODE_ROOT / "target" / "release" / (
    "engelcode.exe" if sys.platform == "win32" else "engelcode"
)
CARGO_TOML = ENGELCODE_ROOT / "Cargo.toml"
APPROVED_TEMP_ROOT = Path(r"D:\b.WorkSpace\Engel App\runtime\temp\engelcode")
APPROVED_CARGO_HOME = Path(r"D:\b.WorkSpace\Engel App\runtime\cargo-home")
APPROVED_RUSTUP_HOME = Path(r"D:\b.WorkSpace\Engel App\runtime\rustup-home")
APPROVED_ENGEL_HOME = Path(r"D:\b.WorkSpace\Engel App\runtime\engel-home")


def _path_on_os_drive(path: Path | str | None) -> bool:
    if path is None:
        return False
    text = str(path).replace("/", "\\").lower()
    return text.startswith("c:\\") or text.startswith("\\\\?\\c:\\")


def _approved_path(path: Path | str | None) -> Optional[str]:
    if not path:
        return None
    candidate = Path(path)
    if _path_on_os_drive(candidate):
        return None
    try:
        if candidate.is_file():
            return str(candidate)
    except OSError:
        return None
    return None


def _approved_env_exe(name: str) -> Optional[str]:
    return _approved_path(os.environ.get(name, "").strip())


def _join_approved_env_path(name: str, *parts: str) -> Optional[Path]:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    root = Path(value)
    if _path_on_os_drive(root):
        return None
    return root.joinpath(*parts)


def _which_approved(*names: str) -> Optional[str]:
    for name in names:
        approved = _approved_path(shutil.which(name))
        if approved:
            return approved
    return None


def _path_without_os_drive_entries() -> str:
    parts = []
    for item in os.environ.get("PATH", "").split(os.pathsep):
        if item and not _path_on_os_drive(item):
            parts.append(item)
    return os.pathsep.join(parts)


def _ensure_runtime_dirs() -> None:
    for path in (APPROVED_TEMP_ROOT, APPROVED_CARGO_HOME, APPROVED_RUSTUP_HOME, APPROVED_ENGEL_HOME):
        path.mkdir(parents=True, exist_ok=True)


def _subprocess_env() -> dict[str, str]:
    _ensure_runtime_dirs()
    env = os.environ.copy()
    env.update(
        {
            "TEMP": str(APPROVED_TEMP_ROOT),
            "TMP": str(APPROVED_TEMP_ROOT),
            "TMPDIR": str(APPROVED_TEMP_ROOT),
            "CARGO_HOME": str(APPROVED_CARGO_HOME),
            "RUSTUP_HOME": str(APPROVED_RUSTUP_HOME),
            "ENGEL_HOME": str(APPROVED_ENGEL_HOME),
            "HOME": str(APPROVED_ENGEL_HOME),
        }
    )
    env["PATH"] = _path_without_os_drive_entries()
    return env


_CARGO_FALLBACKS = (
    _approved_env_exe("ENGEL_CARGO_EXE"),
    _join_approved_env_path("CARGO_HOME", "bin", "cargo.exe"),
    APPROVED_CARGO_HOME / "bin" / "cargo.exe",
)
_RUSTC_FALLBACKS = (
    _approved_env_exe("ENGEL_RUSTC_EXE"),
    _join_approved_env_path("CARGO_HOME", "bin", "rustc.exe"),
    APPROVED_CARGO_HOME / "bin" / "rustc.exe",
    APPROVED_RUSTUP_HOME / "toolchains" / "stable-x86_64-pc-windows-msvc" / "bin" / "rustc.exe",
)


def _cargo_path() -> Optional[str]:
    found = _which_approved("cargo", "cargo.exe")
    if found:
        return found
    for p in _CARGO_FALLBACKS:
        approved = _approved_path(p)
        if approved:
            return approved
    return None


def _rustc_path() -> Optional[str]:
    found = _which_approved("rustc", "rustc.exe")
    if found:
        return found
    for p in _RUSTC_FALLBACKS:
        approved = _approved_path(p)
        if approved:
            return approved
    return None


def _read_version() -> str:
    if not CARGO_TOML.is_file():
        return "(Cargo.toml missing)"
    try:
        text = CARGO_TOML.read_text(encoding="utf-8")
    except OSError as exc:
        return f"(Cargo.toml read failed: {exc})"
    # First version = ... after [package] block
    m = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return m.group(1) if m else "(version not found)"


def _binary_present() -> bool:
    return RELEASE_BINARY.is_file()


def _wrap(title: str, body: str, *, configured: bool = True) -> str:
    safety = [
        "Safety:",
        f"- Engelcode tree: {ENGELCODE_ROOT}",
        "- Build & run happen in vendored tree only; host engel package untouched.",
        "- C drive is OS-only; Engelcode toolchains and subprocess temp/cache/home use approved non-C roots.",
        "- Autonomy and background work permitted (2026-05-19 ruling).",
    ]
    if not configured:
        safety.append("- Ask 'engelcode bring up' for the install walkthrough.")
    return f"{title}\n\n{body}\n\n" + "\n".join(safety)


def _ensure_tree() -> Optional[str]:
    if not ENGELCODE_ROOT.is_dir():
        return _wrap(
            "Engelcode — tree missing",
            f"Vendored tree not found at {ENGELCODE_ROOT}. Restore from engelcode_main.zip.",
            configured=False,
        )
    return None


def render_engelcode_status(_payload: str = "") -> str:
    missing = _ensure_tree()
    if missing:
        return missing
    lines = [
        f"Tree root         : {ENGELCODE_ROOT}",
        f"Cargo.toml version: {_read_version()}",
        f"cargo executable  : {_cargo_path() or 'NOT FOUND (non-C cargo required; C-side cargo ignored)'}",
        f"rustc executable  : {_rustc_path() or 'NOT FOUND'}",
        f"Release binary    : {'present at ' + str(RELEASE_BINARY) if _binary_present() else 'not built (run engelcode build)'}",
    ]
    return _wrap("Engelcode — status", "\n".join(lines))


def render_engelcode_version(_payload: str = "") -> str:
    missing = _ensure_tree()
    if missing:
        return missing
    return _wrap("Engelcode — version", f"engelcode {_read_version()} (from Cargo.toml)")


def render_engelcode_crates(_payload: str = "") -> str:
    missing = _ensure_tree()
    if missing:
        return missing
    if not CARGO_TOML.is_file():
        return _wrap("Engelcode — crates list unavailable", "Cargo.toml missing.")
    text = CARGO_TOML.read_text(encoding="utf-8", errors="replace")
    # Extract the workspace members list
    m = re.search(r"members\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if not m:
        return _wrap("Engelcode — crates list", "No [workspace] members block found.")
    members_block = m.group(1)
    members = [
        m.strip().strip('",').strip("'")
        for m in members_block.split(",")
        if m.strip() and m.strip() not in ('""', "''")
    ]
    members = [m for m in members if m]
    body = (
        f"Workspace members ({len(members)}):\n"
        + "\n".join(f"  - {m}" for m in members)
    )
    return _wrap("Engelcode — workspace crates", body)


def render_engelcode_build(_payload: str = "") -> str:
    missing = _ensure_tree()
    if missing:
        return missing
    cargo = _cargo_path()
    if not cargo:
        return _wrap(
            "Engelcode — build unavailable (Rust toolchain missing)",
            (
                "cargo is not on approved non-C PATH. Install Rust to a non-C toolchain root,\n"
                "set CARGO_HOME under F:, ensure non-C cargo is on PATH or set ENGEL_CARGO_EXE,\n"
                "then ask\n"
                "  engelcode build\n"
                "again. C-side Rust toolchains are ignored. First build pulls 100s of crates and may take 10-30 min."
            ),
            configured=False,
        )

    # Long-running. Capture combined output; cap stdout snippet.
    proc = subprocess.run(
        [cargo, "build", "--release"],
        cwd=str(ENGELCODE_ROOT),
        capture_output=True, text=True, check=False,
        encoding="utf-8", errors="replace",
        env=_subprocess_env(),
    )
    if proc.returncode != 0:
        return _wrap(
            "Engelcode — cargo build failed",
            ((proc.stderr or proc.stdout) or "(no output)")[-8000:],
        )
    return _wrap(
        "Engelcode — build complete",
        (
            f"cargo build --release finished cleanly.\n"
            f"Binary at: {RELEASE_BINARY}\n"
            f"Run via 'engelcode invoke' (or just 'engelcode')."
        ),
    )


def render_engelcode_invoke(payload: Optional[str] = "") -> str:
    missing = _ensure_tree()
    if missing:
        return missing
    if not _binary_present():
        return _wrap(
            "Engelcode — binary not built",
            "Release binary missing. Run 'engelcode build' first (takes 10-30 min on first build).",
            configured=False,
        )

    args = (payload or "").strip().split() if payload else []
    # Strip any leading trigger words ('engelcode', 'invoke', 'run', etc.)
    trim_leading = {"engelcode", "invoke", "run", "exec"}
    while args and args[0].lower() in trim_leading:
        args = args[1:]

    proc = subprocess.run(
        [str(RELEASE_BINARY), *args],
        cwd=str(ENGELCODE_ROOT),
        capture_output=True, text=True, check=False,
        encoding="utf-8", errors="replace",
        env=_subprocess_env(),
        timeout=120,
    )
    if proc.returncode != 0:
        return _wrap(
            f"Engelcode — invoke exit {proc.returncode}",
            ((proc.stdout or "") + "\n" + (proc.stderr or ""))[:8000],
        )
    body = (proc.stdout.rstrip() or proc.stderr.rstrip() or "(no output)")
    return _wrap("Engelcode — invoke result", body)


def render_engelcode_bring_up(_payload: str = "") -> str:
    cargo = _cargo_path()
    rustc = _rustc_path()
    body = (
        "Engelcode is a Rust workspace (50+ crates). Bring-up steps:\n"
        "\n"
        f"  1) Install Rust toolchain (current detection: cargo={cargo}, rustc={rustc})\n"
        "     Use a non-C toolchain root, set CARGO_HOME under F:, and put non-C cargo/rustc on PATH.\n"
        "     You may also set ENGEL_CARGO_EXE and ENGEL_RUSTC_EXE to explicit non-C executables.\n"
        "\n"
        "  2) Restart your shell so PATH picks up cargo/rustc.\n"
        "\n"
        "  3) Build via Engel AI:\n"
        "       engelcode build\n"
        "     (Or directly: cargo build --release inside engelcode_main/)\n"
        "     First build pulls hundreds of crates; expect 10-30 minutes.\n"
        "\n"
        f"  4) Once built, the binary is at {RELEASE_BINARY}\n"
        "     Run via:\n"
        "       engelcode invoke <args>\n"
        "     Or just execute the binary directly.\n"
        "\n"
        "  5) Workspace crate inventory:\n"
        "       engelcode crates\n"
    )
    return _wrap("Engelcode — Rust toolchain bring-up guide", body, configured=False)
