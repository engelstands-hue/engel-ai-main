from __future__ import annotations

import os
import shutil
import subprocess
import threading
import webbrowser
from pathlib import Path

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
ENG3D_DISPLAY_NAME = "Eng3d"
ENG3D_COMMAND = "eng3d"
ENG3D_SOURCE = ROOT / "sandbox" / "Eng3d"
DOCS = ENG3D_SOURCE / "docs"

_LOCK = threading.Lock()
_STATE: dict = {
    "running": False,
    "process": None,
    "mode": None,
    "log_lines": [],
    "max_log_lines": 300,
    "url": "http://localhost:3000",
}


def _src_present() -> bool:
    return (ENG3D_SOURCE / "package.json").exists()


def _have(tool: str) -> bool:
    return shutil.which(tool) is not None


def _node_modules_present() -> bool:
    return (ENG3D_SOURCE / "node_modules").exists()


def _list_docs() -> list[str]:
    if not DOCS.exists():
        return []
    return [p.relative_to(DOCS).with_suffix("").as_posix() for p in sorted(DOCS.glob("**/*.md"))]


def _find_doc(name: str) -> Path | None:
    name = name.strip().lower().replace("\\", "/")
    if name.endswith(".md"):
        name = name[:-3]
    if not DOCS.exists():
        return None
    for path in DOCS.glob("**/*.md"):
        rel = path.relative_to(DOCS).with_suffix("").as_posix().lower()
        if rel == name or path.stem.lower() == name:
            return path
    return None


def eng3d_status() -> str:
    lines = [f"# {ENG3D_DISPLAY_NAME} Bridge Status", ""]
    lines.append(f"Sandbox source: {'READY' if _src_present() else 'NOT FOUND'}  [{ENG3D_SOURCE}]")
    lines.append(f"node:         {'installed' if _have('node') else 'NOT installed'}")
    lines.append(f"npm:          {'installed' if _have('npm') else 'NOT installed'}")
    node_modules = "present" if _node_modules_present() else f"MISSING (run {ENG3D_COMMAND} install)"
    lines.append(f"node_modules: {node_modules}")
    lines.append(f"Docs:         {len(_list_docs())} files")
    lines.append("")

    with _LOCK:
        if _STATE["running"]:
            lines.append(f"Current run: {_STATE['mode']}  RUNNING ({_STATE['url']})")
            for line in _STATE["log_lines"][-10:]:
                lines.append("  " + line)
        else:
            lines.append("Current run: idle")

    lines += [
        "",
        "Commands:",
        f"  {ENG3D_COMMAND} status              - this page",
        f"  {ENG3D_COMMAND} install             - npm install dependencies (slow first time)",
        f"  {ENG3D_COMMAND} dev                 - start dev server on localhost:3000",
        f"  {ENG3D_COMMAND} start               - start production server (needs prior '{ENG3D_COMMAND} build')",
        f"  {ENG3D_COMMAND} build               - next build",
        f"  {ENG3D_COMMAND} demo                - start the built-in demo gateway adapter",
        f"  {ENG3D_COMMAND} open                - open the 3D office in your browser",
        f"  {ENG3D_COMMAND} docs                - list internal spec docs",
        f"  {ENG3D_COMMAND} show <name>         - print a doc",
        f"  {ENG3D_COMMAND} stop                - stop the running server",
        f"  {ENG3D_COMMAND} tail                - show last 50 lines of output",
    ]
    return "\n".join(lines)


def _drain(proc: subprocess.Popen) -> None:
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


def _start(args: list[str], mode: str) -> str:
    if not _src_present():
        return f"{ENG3D_DISPLAY_NAME} source missing at {ENG3D_SOURCE}"
    if not _have("npm"):
        return "npm not installed. Install Node.js from https://nodejs.org first."
    with _LOCK:
        if _STATE["running"]:
            return f"{ENG3D_DISPLAY_NAME} is already running ({_STATE['mode']}). Use '{ENG3D_COMMAND} stop' first."

    # On Windows, npm is typically a .cmd shim; let the shell resolve it.
    use_shell = os.name == "nt"
    try:
        proc = subprocess.Popen(
            args,
            cwd=str(ENG3D_SOURCE),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            shell=use_shell,
        )
    except Exception as exc:
        return f"Failed to start: {exc}"

    with _LOCK:
        _STATE.update({
            "running": True,
            "process": proc,
            "mode": mode,
            "log_lines": [f"started: {' '.join(args)}"],
        })
    threading.Thread(target=_drain, args=(proc,), daemon=True).start()
    return f"Started {ENG3D_DISPLAY_NAME} ({mode}). Use '{ENG3D_COMMAND} tail' to watch, '{ENG3D_COMMAND} open' to view."


def eng3d_install() -> str:
    return _start(["npm", "install"], "npm install")


def eng3d_dev() -> str:
    if not _node_modules_present():
        return f"node_modules missing. Run '{ENG3D_COMMAND} install' first."
    return _start(["npm", "run", "dev"], "dev server")


def eng3d_start() -> str:
    if not _node_modules_present():
        return f"node_modules missing. Run '{ENG3D_COMMAND} install' first."
    return _start(["npm", "start"], "production server")


def eng3d_build() -> str:
    if not _node_modules_present():
        return f"node_modules missing. Run '{ENG3D_COMMAND} install' first."
    return _start(["npm", "run", "build"], "next build")


def eng3d_demo() -> str:
    if not _node_modules_present():
        return f"node_modules missing. Run '{ENG3D_COMMAND} install' first."
    return _start(["npm", "run", "demo-gateway"], "demo gateway")


def eng3d_open() -> str:
    url = _STATE["url"]
    try:
        webbrowser.open(url)
        return f"Opening {url} in your browser."
    except Exception as exc:
        return f"Failed to open browser: {exc}. URL: {url}"


def eng3d_stop() -> str:
    with _LOCK:
        proc = _STATE.get("process")
        mode = _STATE.get("mode")
        if not _STATE["running"] or not proc:
            return f"{ENG3D_DISPLAY_NAME} is not running."
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
    return f"Stopped {ENG3D_DISPLAY_NAME} ({mode})."


def eng3d_tail(n: int = 50) -> str:
    with _LOCK:
        lines = list(_STATE["log_lines"])
        running = _STATE["running"]
        mode = _STATE.get("mode")
    if not lines:
        return "No output yet."
    header = f"# {ENG3D_COMMAND} :: {mode} ({'RUNNING' if running else 'STOPPED'})"
    return header + "\n" + "\n".join(lines[-n:])


def eng3d_docs() -> str:
    items = _list_docs()
    if not items:
        return "No docs found."
    return f"# {ENG3D_DISPLAY_NAME} docs ({len(items)})\n" + "\n".join(f"  - {item}" for item in items)


def eng3d_show(name: str) -> str:
    if not name.strip():
        return f"Usage: {ENG3D_COMMAND} show <name>"
    path = _find_doc(name)
    if not path:
        return f"Not found: '{name}'. Try '{ENG3D_COMMAND} docs'."
    try:
        return f"# {path.relative_to(ENG3D_SOURCE).as_posix()}\n\n{path.read_text(encoding='utf-8', errors='replace')}"
    except Exception as exc:
        return f"Failed to read: {exc}"


def handle_eng3d_command(args: str) -> str:
    text = (args or "").strip()
    if not text or text == "status":
        return eng3d_status()
    if text == "install":
        return eng3d_install()
    if text == "dev":
        return eng3d_dev()
    if text == "start":
        return eng3d_start()
    if text == "build":
        return eng3d_build()
    if text == "demo":
        return eng3d_demo()
    if text == "open":
        return eng3d_open()
    if text == "stop":
        return eng3d_stop()
    if text == "tail":
        return eng3d_tail()
    if text == "docs":
        return eng3d_docs()
    if text.startswith("show"):
        return eng3d_show(text[4:].strip())
    return f"Unknown {ENG3D_COMMAND} subcommand: '{text}'. Try '{ENG3D_COMMAND} status'."
