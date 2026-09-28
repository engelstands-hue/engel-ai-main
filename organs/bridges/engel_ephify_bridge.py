from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import threading
from pathlib import Path

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
EPHIFY_DISPLAY_NAME = "Ephify"
EPHIFY_COMMAND = "ephify"
EPHIFY_SOURCE = ROOT / "sandbox" / "Ephify"
# The user-facing Engel bridge is Ephify; the sandboxed upstream package still
# exposes its original Python module name internally.
UPSTREAM_MODULE = "graphify"
UPSTREAM_PIP_PACKAGE = "graphifyy"

_LOCK = threading.Lock()
_STATE: dict = {
    "running": False,
    "process": None,
    "subcommand": None,
    "cwd": None,
    "log_lines": [],
    "max_log_lines": 300,
}

_REQUIRED = [
    "networkx",
    "datasketch",
    "rapidfuzz",
    "tree_sitter",
]


def _ephify_installed() -> bool:
    return (EPHIFY_SOURCE / UPSTREAM_MODULE / "__main__.py").exists()


def _missing_deps() -> list[str]:
    missing = []
    for module_name in _REQUIRED:
        if importlib.util.find_spec(module_name) is None:
            missing.append(module_name)
    return missing


def _upstream_pip_target() -> str:
    return UPSTREAM_PIP_PACKAGE


def ephify_status() -> str:
    lines = [f"# {EPHIFY_DISPLAY_NAME} Bridge Status", ""]
    source_ready = _ephify_installed()
    missing = _missing_deps()

    lines.append(f"Sandbox source:     {'READY' if source_ready else 'NOT FOUND'}  [{EPHIFY_SOURCE}]")
    if missing:
        lines.append(f"Missing deps:       {', '.join(missing)}")
        lines.append("                    Install with: " + EPHIFY_COMMAND + " install-deps")
    else:
        lines.append("Dependencies:       ALL PRESENT")
    lines.append("")

    with _LOCK:
        if _STATE["running"]:
            lines.append(f"Current run: {EPHIFY_COMMAND} {_STATE['subcommand']}  (cwd={_STATE['cwd']})  RUNNING")
            lines.append("Recent output:")
            for line in _STATE["log_lines"][-15:]:
                lines.append("  " + line)
        else:
            lines.append("Current run: idle")

    lines += [
        "",
        "Commands:",
        f"  {EPHIFY_COMMAND} build [path]        - build knowledge graph for path (default: current dir)",
        f"  {EPHIFY_COMMAND} query <question>    - query the current graph",
        f"  {EPHIFY_COMMAND} explain <topic>     - explain a topic from the graph",
        f"  {EPHIFY_COMMAND} export <format>     - export (e.g. callflow-html)",
        f"  {EPHIFY_COMMAND} run <subcommand>    - run any raw upstream CLI subcommand",
        f"  {EPHIFY_COMMAND} stop                - stop the current run",
        f"  {EPHIFY_COMMAND} tail                - show last 50 lines of running output",
        f"  {EPHIFY_COMMAND} install-deps        - pip install upstream dependency package",
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


def _start_ephify(args: list[str], cwd: str | None = None) -> str:
    if not _ephify_installed():
        return f"{EPHIFY_DISPLAY_NAME} source not found at {EPHIFY_SOURCE}"
    missing = _missing_deps()
    if missing:
        return (
            f"{EPHIFY_DISPLAY_NAME} dependencies missing: " + ", ".join(missing) + "\n"
            f"Install with: {EPHIFY_COMMAND} install-deps"
        )
    with _LOCK:
        if _STATE["running"]:
            return f"{EPHIFY_DISPLAY_NAME} is already running: {_STATE['subcommand']}. Use '{EPHIFY_COMMAND} stop' first."

    env = os.environ.copy()
    env["PYTHONPATH"] = str(EPHIFY_SOURCE) + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [sys.executable, "-m", UPSTREAM_MODULE] + args
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd or os.getcwd(),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as exc:
        return f"Failed to start {EPHIFY_COMMAND}: {exc}"

    with _LOCK:
        _STATE.update({
            "running": True,
            "process": proc,
            "subcommand": " ".join(args),
            "cwd": cwd or os.getcwd(),
            "log_lines": [f"started: {EPHIFY_COMMAND} {' '.join(args)}"],
        })
    threading.Thread(target=_drain_output, args=(proc,), daemon=True).start()
    return f"Started: {EPHIFY_COMMAND} {' '.join(args)}\nUse '{EPHIFY_COMMAND} tail' to watch progress."


def ephify_build(path: str = ".") -> str:
    target = path or "."
    return _start_ephify([target], cwd=os.path.abspath(target))


def ephify_query(question: str) -> str:
    if not question.strip():
        return f"Usage: {EPHIFY_COMMAND} query <question>"
    return _start_ephify(["query", question])


def ephify_explain(topic: str) -> str:
    if not topic.strip():
        return f"Usage: {EPHIFY_COMMAND} explain <topic>"
    return _start_ephify(["explain", topic])


def ephify_export(fmt: str) -> str:
    if not fmt.strip():
        return f"Usage: {EPHIFY_COMMAND} export <format>  (e.g. callflow-html)"
    return _start_ephify(["export", fmt])


def ephify_raw(subcommand: str) -> str:
    parts = subcommand.strip().split()
    if not parts:
        return f"Usage: {EPHIFY_COMMAND} run <subcommand>"
    return _start_ephify(parts)


def ephify_stop() -> str:
    with _LOCK:
        proc = _STATE.get("process")
        subcommand = _STATE.get("subcommand")
        if not _STATE["running"] or not proc:
            return f"No {EPHIFY_COMMAND} run in progress."
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
    return f"Stopped {EPHIFY_COMMAND} {subcommand}."


def ephify_tail(n: int = 50) -> str:
    with _LOCK:
        lines = list(_STATE["log_lines"])
        running = _STATE["running"]
        subcommand = _STATE.get("subcommand")
    if not lines:
        return "No output yet."
    header = f"# {EPHIFY_COMMAND} {subcommand} ({'RUNNING' if running else 'STOPPED'})"
    return header + "\n" + "\n".join(lines[-n:])


def ephify_install_deps() -> str:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", _upstream_pip_target()],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        return "pip install timed out after 10 minutes."
    except Exception as exc:
        return f"pip install failed to start: {exc}"
    output = (proc.stdout or "") + (proc.stderr or "")
    tail = "\n".join(output.splitlines()[-15:])
    status = "SUCCESS" if proc.returncode == 0 else f"FAILED (exit {proc.returncode})"
    return f"{EPHIFY_COMMAND} dependency install -> {status}\n\n{tail}"


def handle_ephify_command(args: str) -> str:
    text = (args or "").strip()
    if not text or text == "status":
        return ephify_status()
    if text == "stop":
        return ephify_stop()
    if text == "tail":
        return ephify_tail()
    if text == "install-deps":
        return ephify_install_deps()
    if text.startswith("build"):
        rest = text[5:].strip()
        return ephify_build(rest or ".")
    if text.startswith("query"):
        return ephify_query(text[5:].strip())
    if text.startswith("explain"):
        return ephify_explain(text[7:].strip())
    if text.startswith("export"):
        return ephify_export(text[6:].strip())
    if text.startswith("run"):
        return ephify_raw(text[3:].strip())
    return f"Unknown {EPHIFY_COMMAND} subcommand: '{text}'. Try '{EPHIFY_COMMAND} status'."
