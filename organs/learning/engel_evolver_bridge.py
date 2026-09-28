from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
EXTERNAL = ROOT / "external"
PY_EVOLVER = EXTERNAL / "darwinian_evolver-main"
JS_EVOLVER = EXTERNAL / "evolver-main"

_LOCK = threading.Lock()
_STATE: dict = {
    "running": False,
    "process": None,
    "kind": None,
    "problem": None,
    "log_lines": [],
    "max_log_lines": 200,
}


def _py_evolver_installed() -> bool:
    return (PY_EVOLVER / "darwinian_evolver" / "__main__.py").exists()


def _js_evolver_installed() -> bool:
    return (JS_EVOLVER / "index.js").exists()


def _node_available() -> bool:
    return shutil.which("node") is not None


def evolver_status() -> str:
    lines = ["# Evolver Bridge Status", ""]
    py_ok = _py_evolver_installed()
    js_ok = _js_evolver_installed()
    node_ok = _node_available()

    lines.append(f"Darwinian (Python): {'READY' if py_ok else 'NOT FOUND'}  [{PY_EVOLVER}]")
    lines.append(f"Evolver (Node.js):  {'READY' if js_ok else 'NOT FOUND'}  [{JS_EVOLVER}]")
    lines.append(f"Node runtime:       {'AVAILABLE' if node_ok else 'NOT INSTALLED'}")
    lines.append("")

    with _LOCK:
        if _STATE["running"]:
            lines.append(f"Current run: {_STATE['kind']} :: {_STATE['problem']}  (RUNNING)")
            lines.append(f"Recent output ({len(_STATE['log_lines'])} lines buffered):")
            for ln in _STATE["log_lines"][-15:]:
                lines.append("  " + ln)
        else:
            lines.append("Current run: idle")

    lines += [
        "",
        "Commands:",
        "  evolve list                       — list darwinian problems",
        "  evolve run <problem> [iters]      — start a darwinian evolution",
        "  evolve node <subcommand> [args]   — call evolver-main (Node) directly",
        "  evolve stop                       — stop the current run",
        "  evolve tail                       — show last 50 lines of running output",
    ]
    return "\n".join(lines)


def evolver_list() -> str:
    if not _py_evolver_installed():
        return f"Darwinian evolver not found at {PY_EVOLVER}"
    registry = PY_EVOLVER / "darwinian_evolver" / "problems" / "registry.py"
    if not registry.exists():
        return f"Registry file missing: {registry}"
    import re
    text = registry.read_text(encoding="utf-8", errors="replace")
    names = re.findall(r'"([a-z_][a-z0-9_]*)"\s*:\s*make_', text)
    if not names:
        return "Could not parse problem names from registry."
    out = ["Available darwinian problems:"] + [f"  {n}" for n in sorted(set(names))]
    if sys.version_info < (3, 11):
        out += [
            "",
            f"Warning: Python {sys.version_info.major}.{sys.version_info.minor} detected.",
            "darwinian_evolver requires Python 3.11+ to actually run.",
            "Listing works but 'evolve run' will fail until you upgrade.",
        ]
    return "\n".join(out)


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


def evolver_run(problem: str, iterations: int = 5) -> str:
    if not _py_evolver_installed():
        return f"Darwinian evolver not found at {PY_EVOLVER}"
    with _LOCK:
        if _STATE["running"]:
            return f"An evolution is already running: {_STATE['kind']}::{_STATE['problem']}. Use 'evolve stop' first."

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PY_EVOLVER) + os.pathsep + env.get("PYTHONPATH", "")

    cmd = [
        sys.executable, "-m", "darwinian_evolver",
        problem,
        "--num_iterations", str(iterations),
    ]
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(PY_EVOLVER),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as exc:
        return f"Failed to start evolver: {exc}"

    with _LOCK:
        _STATE.update({
            "running": True, "process": proc,
            "kind": "darwinian", "problem": problem,
            "log_lines": [f"started: {' '.join(cmd)}"],
        })
    threading.Thread(target=_drain_output, args=(proc,), daemon=True).start()
    return f"Started darwinian evolution: {problem} ({iterations} iterations). Use 'evolve tail' to watch."


def evolver_node(subcommand: str) -> str:
    if not _js_evolver_installed():
        return f"Evolver-main not found at {JS_EVOLVER}"
    if not _node_available():
        return "Node.js not installed. Install Node.js to use the evolver-main subsystem."
    with _LOCK:
        if _STATE["running"]:
            return f"An evolution is already running: {_STATE['kind']}::{_STATE['problem']}. Use 'evolve stop' first."

    parts = subcommand.strip().split()
    cmd = ["node", "index.js"] + parts
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(JS_EVOLVER),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as exc:
        return f"Failed to start node evolver: {exc}"

    with _LOCK:
        _STATE.update({
            "running": True, "process": proc,
            "kind": "evolver-node", "problem": subcommand,
            "log_lines": [f"started: {' '.join(cmd)}"],
        })
    threading.Thread(target=_drain_output, args=(proc,), daemon=True).start()
    return f"Started evolver-node: {subcommand}. Use 'evolve tail' to watch."


def evolver_stop() -> str:
    with _LOCK:
        proc = _STATE.get("process")
        kind = _STATE.get("kind")
        problem = _STATE.get("problem")
        if not _STATE["running"] or not proc:
            return "No evolution running."
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
    return f"Stopped {kind}::{problem}."


def evolver_tail(n: int = 50) -> str:
    with _LOCK:
        lines = list(_STATE["log_lines"])
        running = _STATE["running"]
        kind = _STATE.get("kind")
        problem = _STATE.get("problem")
    if not lines:
        return "No output yet."
    header = f"# {kind}::{problem} ({'RUNNING' if running else 'STOPPED'})"
    return header + "\n" + "\n".join(lines[-n:])


def handle_evolve_command(args: str) -> str:
    """Top-level router for 'evolve ...' chat commands."""
    text = (args or "").strip()
    if not text or text == "status":
        return evolver_status()
    if text == "list":
        return evolver_list()
    if text == "stop":
        return evolver_stop()
    if text == "tail":
        return evolver_tail()
    if text.startswith("run"):
        rest = text[3:].strip().split()
        if not rest:
            return "Usage: evolve run <problem> [iterations]"
        problem = rest[0]
        iters = 5
        if len(rest) > 1:
            try:
                iters = int(rest[1])
            except ValueError:
                return f"Iterations must be an integer, got '{rest[1]}'"
        return evolver_run(problem, iters)
    if text.startswith("node"):
        rest = text[4:].strip()
        if not rest:
            return "Usage: evolve node <subcommand> [args]"
        return evolver_node(rest)
    return f"Unknown evolve subcommand: '{text}'. Try 'evolve status'."
