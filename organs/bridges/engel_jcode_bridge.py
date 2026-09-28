from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
JCODE_SRC = ROOT / "external" / "jcode-master"
JCODE_BUILT = JCODE_SRC / "target" / "release" / ("jcode.exe" if os.name == "nt" else "jcode")

_LOCK = threading.Lock()
_STATE: dict = {
    "running": False,
    "process": None,
    "prompt": None,
    "log_lines": [],
    "max_log_lines": 300,
}


def _src_present() -> bool:
    return (JCODE_SRC / "Cargo.toml").exists()


def _find_binary() -> str | None:
    sys_bin = shutil.which("jcode")
    if sys_bin:
        return sys_bin
    if JCODE_BUILT.exists():
        return str(JCODE_BUILT)
    return None


def _have_cargo() -> bool:
    return shutil.which("cargo") is not None


def jcode_status() -> str:
    lines = ["# jcode Bridge Status", ""]
    binary = _find_binary()
    lines.append(f"Source tree: {'READY' if _src_present() else 'NOT FOUND'}  [{JCODE_SRC}]")
    if binary:
        lines.append(f"Binary:      FOUND at {binary}")
    else:
        lines.append("Binary:      NOT FOUND")
        if _have_cargo():
            lines.append("             Build with: jcode build")
        else:
            lines.append("             Install Rust (https://rustup.rs) then: jcode build")
            lines.append("             Or install jcode prebuilt and put it on PATH.")
    lines.append("")

    with _LOCK:
        if _STATE["running"]:
            lines.append(f"Current run: {_STATE['prompt']}  RUNNING")
            for ln in _STATE["log_lines"][-15:]:
                lines.append("  " + ln)
        else:
            lines.append("Current run: idle")

    lines += [
        "",
        "Commands:",
        "  jcode status                 — this page",
        "  jcode build                  — build jcode from external/jcode-master (needs cargo)",
        "  jcode version                — print jcode --version",
        "  jcode help                   — show jcode CLI help",
        "  jcode run <prompt>           — run jcode with a prompt (subprocess)",
        "  jcode raw <args>             — pass-through to jcode CLI",
        "  jcode stop                   — stop the current run",
        "  jcode tail                   — show last 50 lines of running output",
    ]
    return "\n".join(lines)


def _drain_output(proc: subprocess.Popen) -> None:
    if proc.stdout is None:
        return
    for raw in iter(proc.stdout.readline, ""):
        line = raw.rstrip("\n")
        with _LOCK:
            buf = _STATE["log_lines"]
            buf.append(line)
            if len(buf) > _STATE["max_log_lines"]:
                del buf[: len(buf) - _STATE["max_log_lines"]]
    with _LOCK:
        _STATE["running"] = False
        _STATE["process"] = None


def _start(args: list[str], label: str) -> str:
    binary = _find_binary()
    if not binary:
        return "jcode binary not found. Run 'jcode build' or install it on PATH."
    with _LOCK:
        if _STATE["running"]:
            return f"jcode is already running ({_STATE['prompt']}). Use 'jcode stop' first."
    cmd = [binary] + args
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as exc:
        return f"Failed to start jcode: {exc}"
    with _LOCK:
        _STATE.update({
            "running": True, "process": proc, "prompt": label,
            "log_lines": [f"started: {' '.join(cmd)}"],
        })
    threading.Thread(target=_drain_output, args=(proc,), daemon=True).start()
    return f"Started: jcode {' '.join(args)}\nUse 'jcode tail' to watch."


def jcode_version() -> str:
    binary = _find_binary()
    if not binary:
        return "jcode binary not found. Run 'jcode build' or install it on PATH."
    try:
        r = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=10)
        return (r.stdout + r.stderr).strip() or "(no output)"
    except Exception as exc:
        return f"Failed: {exc}"


def jcode_help() -> str:
    binary = _find_binary()
    if not binary:
        return "jcode binary not found."
    try:
        r = subprocess.run([binary, "--help"], capture_output=True, text=True, timeout=10)
        return (r.stdout + r.stderr).strip()[:2000] or "(no output)"
    except Exception as exc:
        return f"Failed: {exc}"


def jcode_build() -> str:
    if not _src_present():
        return f"jcode source not found at {JCODE_SRC}"
    if not _have_cargo():
        return "cargo not installed. Get Rust at https://rustup.rs then try again."
    with _LOCK:
        if _STATE["running"]:
            return "Another jcode run is in progress. Use 'jcode stop' first."

    cmd = ["cargo", "build", "--release", "--bin", "jcode"]
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(JCODE_SRC),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as exc:
        return f"Failed to start build: {exc}"
    with _LOCK:
        _STATE.update({
            "running": True, "process": proc, "prompt": "cargo build (release)",
            "log_lines": [f"building: {JCODE_SRC}"],
        })
    threading.Thread(target=_drain_output, args=(proc,), daemon=True).start()
    return "Building jcode (this may take 10+ minutes the first time). Use 'jcode tail' to watch."


def jcode_run(prompt: str) -> str:
    if not prompt.strip():
        return "Usage: jcode run <prompt>"
    return _start([prompt], f"run: {prompt[:60]}")


def jcode_raw(args: str) -> str:
    parts = args.strip().split()
    if not parts:
        return "Usage: jcode raw <args>"
    return _start(parts, f"raw: {args[:60]}")


def jcode_stop() -> str:
    with _LOCK:
        proc = _STATE.get("process")
        prompt = _STATE.get("prompt")
        if not _STATE["running"] or not proc:
            return "No jcode process running."
    try:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception as exc:
        return f"Failed to stop: {exc}"
    with _LOCK:
        _STATE["running"] = False
        _STATE["process"] = None
    return f"Stopped: {prompt}"


def jcode_tail(n: int = 50) -> str:
    with _LOCK:
        lines = list(_STATE["log_lines"])
        running = _STATE["running"]
        prompt = _STATE.get("prompt")
    if not lines:
        return "No output yet."
    header = f"# jcode :: {prompt} ({'RUNNING' if running else 'STOPPED'})"
    return header + "\n" + "\n".join(lines[-n:])


def handle_jcode_command(args: str) -> str:
    text = (args or "").strip()
    if not text or text == "status":
        return jcode_status()
    if text == "version":
        return jcode_version()
    if text == "help":
        return jcode_help()
    if text == "build":
        return jcode_build()
    if text == "stop":
        return jcode_stop()
    if text == "tail":
        return jcode_tail()
    if text.startswith("run"):
        return jcode_run(text[3:].strip())
    if text.startswith("raw"):
        return jcode_raw(text[3:].strip())
    # treat anything else as a prompt to jcode
    return jcode_run(text)
