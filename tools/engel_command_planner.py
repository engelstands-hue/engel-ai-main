#!/usr/bin/env python3
"""
Engel AI Main — command planner for the confirm-before-execute action flow.

Turns a natural-language action request ("install matplotlib in the trig env",
"run the trig demo") into a REVIEWABLE PLAN of concrete commands. It NEVER runs
anything itself — the worker shows the plan to Joshua, waits for an explicit
confirmation, then runs each step through engel_sandbox (denylist + secret-strip +
timeout + output cap). Deliberately NARROW: pip installs into the Engel runtime
python, and running an existing workspace script. Anything it can't parse into a
clean, safe command returns None, so it falls back to normal chat.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PY = ROOT / "runtime" / "python310" / "python.exe"
WORKSPACES = ROOT / "workspaces"

# A valid pip requirement token: name, optional extras, optional ==version.
_PKG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[A-Za-z0-9,_-]+\])?(?:==[\w.\-]+)?$")
_STOPWORDS = {
    "and", "the", "a", "an", "please", "package", "packages", "module", "modules",
    "library", "libraries", "dependency", "dependencies", "into", "in", "to", "for",
    "my", "engel", "runtime", "python", "pip",
}


def _sandbox_denial(argv: list[str]) -> str | None:
    """Use the same denylist at plan time that execution uses at run time."""
    try:
        import engel_sandbox

        return engel_sandbox.is_denied(argv)
    except Exception:
        return None


def _blocked_step(cmd: str, reason: str) -> dict[str, Any]:
    return {
        "desc": f"blocked unsafe shell command: {cmd}",
        "argv": [],
        "cwd": str(ROOT),
        "tier": "blocked",
        "timeout": 0,
        "blocked": True,
        "reason": f"command matched deny pattern: {reason}",
    }


def _find_workspace(low: str) -> str | None:
    """Detect an existing workspace named in the request (e.g. 'trig env')."""
    if not WORKSPACES.is_dir():
        return None
    names = {p.name.lower(): p.name for p in WORKSPACES.iterdir() if p.is_dir()}
    for key, real in names.items():
        if key in low or key.replace("_", " ") in low or key.replace("_env", "") in low:
            return real
    if "trig" in low and "trig_env" in names:
        return names["trig_env"]
    return None


def _extract_packages(low: str) -> list[str]:
    # whole-word trigger so "installed" / "uninstall" / "installing" don't match.
    m = re.search(r"\b(?:pip3?\s+install|install|add)\b", low)
    if not m:
        return []
    tail = low[m.end():]
    # cut at a workspace/target clause: "... to/into/in/for the trig env"
    tail = re.split(r"\b(?:to|into|in|for)\b", tail)[0]
    tokens = re.split(r"[\s,]+", tail.strip())
    pkgs: list[str] = []
    for t in tokens:
        t = t.strip(".,!?;:")
        if not t or t in _STOPWORDS:
            continue
        if _PKG_RE.match(t):
            pkgs.append(t)
        else:
            break  # stop at the first non-package word so we don't grab prose
    # de-dup, keep order
    seen: set[str] = set()
    return [p for p in pkgs if not (p in seen or seen.add(p))]


def _venv_dir(ws: str) -> Path:
    return WORKSPACES / ws / ".venv"


def _venv_python(ws: str) -> Path:
    return _venv_dir(ws) / "Scripts" / "python.exe"


def _workspace_python(ws: str | None) -> str:
    """Run with the workspace's isolated venv if it has one, else the runtime."""
    if ws and _venv_python(ws).is_file():
        return str(_venv_python(ws))
    return str(RUNTIME_PY)


def _plan_pip_install(text: str, low: str) -> list[dict] | None:
    install_intent = bool(re.search(r"\b(?:pip3?\s+)?install\b", low))
    add_intent = bool(re.search(r"\badd\b", low)) and any(
        w in low for w in ("package", "library", "module", "dependency", "to the", " pip ")
    )
    if not (install_intent or add_intent):
        return None
    pkgs = _extract_packages(low)
    if not pkgs:
        return None
    # (2026-07-07 caveat fix) Install into a PER-WORKSPACE venv, never the shared
    # Engel runtime. --system-site-packages reuses numpy/sympy/scipy without a
    # reinstall, while new packages stay isolated to the workspace (runtime stays
    # clean). Bare installs with no named workspace land in a 'general' venv.
    ws = _find_workspace(low) or "general"
    venv_py = _venv_python(ws)
    steps: list[dict] = []
    if not venv_py.is_file():
        steps.append({
            "desc": f"create an isolated venv for workspace '{ws}' (reuses Engel base libs)",
            "argv": [str(RUNTIME_PY), "-m", "venv", "--system-site-packages", str(_venv_dir(ws))],
            "cwd": None, "tier": "restricted", "timeout": 120,
        })
    steps.append({
        "desc": f"pip install {' '.join(pkgs)} into workspace '{ws}' (isolated venv, runtime untouched)",
        "argv": [str(venv_py), "-m", "pip", "install", *pkgs],
        "cwd": None, "tier": "restricted", "timeout": 300,
    })
    return steps


def _plan_run_script(text: str, low: str) -> list[dict] | None:
    if not re.search(r"\b(run|execute|launch)\b", low):
        return None
    ws = _find_workspace(low)
    m = re.search(r"([A-Za-z0-9_.\\/-]+\.py)", text)
    target: Path | None = None
    if m:
        cand = m.group(1).replace("\\", "/")
        base = WORKSPACES / ws if ws else WORKSPACES
        for probe in (Path(cand), base / Path(cand).name, ROOT / cand):
            p = probe if probe.is_absolute() else (ROOT / probe)
            if p.is_file():
                target = p
                break
    elif ws and any(w in low for w in ("demo", "example", "it", "the demo")):
        p = WORKSPACES / ws / "demo.py"
        if p.is_file():
            target = p
    if target is None:
        return None
    # run with the owning workspace's venv python if it has one.
    owner: str | None = ws
    try:
        owner = target.relative_to(WORKSPACES).parts[0]
    except ValueError:
        pass
    py = _workspace_python(owner)
    note = " (workspace venv)" if py != str(RUNTIME_PY) else " (Engel runtime python)"
    return [{
        "desc": f"run {target.relative_to(ROOT)}{note}",
        "argv": [py, str(target)],
        "cwd": str(target.parent),
        "tier": "restricted", "timeout": 120,
    }]


# Known command-line executables. Used to broaden shell detection past the explicit
# "run the command: ..." markers WITHOUT grabbing ordinary prose: "run git status"
# is a command, "run the meeting" / "run through the plan" is not (meeting/through
# aren't executables). Every match is still confirm-gated + denylist-checked.
_SHELL_EXECUTABLES = frozenset({
    "git", "npm", "npx", "yarn", "pnpm", "pip", "pip3", "python", "python3", "py",
    "node", "deno", "bun", "cargo", "rustc", "rustup", "go", "dotnet", "java", "javac",
    "mvn", "gradle", "make", "cmake", "ninja", "docker", "docker-compose", "podman",
    "kubectl", "helm", "terraform", "flutter", "dart", "adb", "gh", "git-lfs",
    "ssh", "scp", "rsync", "sftp", "curl", "wget", "tar", "zip", "unzip", "7z", "gzip",
    "dir", "ls", "pwd", "cd", "mkdir", "rmdir", "echo", "cat", "type", "more", "less",
    "copy", "xcopy", "robocopy", "move", "ren", "rename", "touch", "tree",
    "where", "which", "whoami", "hostname", "uname", "date", "cal", "env", "set",
    "ipconfig", "ifconfig", "ip", "ping", "tracert", "traceroute", "nslookup", "dig",
    "netstat", "ss", "arp", "route", "tasklist", "taskkill", "ps", "top", "df", "du",
    "free", "systemctl", "service", "journalctl", "sc", "wmic",
    "pytest", "tox", "nox", "ruff", "black", "isort", "flake8", "mypy", "pylint",
    "eslint", "prettier", "tsc", "webpack", "vite", "rollup", "esbuild", "jest",
    "pwsh", "powershell", "cmd", "bash", "sh", "zsh", "grep", "rg", "find", "fd",
    "sed", "awk", "head", "tail", "wc", "sort", "uniq", "cut", "diff", "jq",
    "chmod", "chown", "cp", "mv", "rm", "mkfs", "mount",
})


def _plan_shell_command(text: str, low: str) -> list[dict] | None:
    # (2026-07-07 caveat fix + broadening) General shell commands from either:
    #   (a) an EXPLICIT command marker — "run the command: ...", "run `...`", ``` fence
    #   (b) "run/execute <known-cli> ..." where the first token is a real executable
    #       (so "run git status" / "execute npm install" are commands, but
    #        "run the meeting" / "run through the plan" fall through to chat).
    # Every match stays confirm-gated, and the sandbox denylist runs before execution.
    cmd: str | None = None
    m = (
        re.search(r"(?:run|execute)\s+(?:the\s+|this\s+)?command[:\s]+(.+)$", text, re.I)
        or re.search(r"(?:run|execute)\s*[:\s]\s*`([^`]+)`", text)
        or re.search(r"```(?:sh|bash|cmd|powershell|bat)?\s*(.+?)```", text, re.S)
    )
    if m:
        cmd = m.group(1).strip().strip("`").strip()
    else:
        m2 = re.search(r"\b(?:run|execute)\s+(.+)$", text, re.I)
        if m2:
            rest = m2.group(1).strip().strip("`").strip()
            first = re.split(r"\s+", rest, 1)[0].lower().strip("`'\".,:;")
            if first in _SHELL_EXECUTABLES:
                cmd = rest
    if not cmd or cmd.lower().endswith(".py"):
        return None  # .py runs go through _plan_run_script
    # pip installs are owned by _plan_pip_install (venv-isolated) — don't double-plan.
    if re.match(r"(?:python3?|py)\s+-m\s+pip\s+install\b", cmd, re.I) or re.match(r"pip3?\s+install\b", cmd, re.I):
        return None
    denial = _sandbox_denial(["cmd", "/c", cmd])
    if denial:
        return [_blocked_step(cmd, denial)]
    return [{
        "desc": f"run shell command: {cmd}",
        "argv": ["cmd", "/c", cmd],
        "cwd": str(ROOT), "tier": "restricted", "timeout": 180,
    }]


def plan_actions(prompt: str) -> dict | None:
    """Return {summary, steps:[{desc, argv, cwd, tier, timeout}]} or None."""
    text = str(prompt or "").strip()
    low = " " + text.lower() + " "
    steps: list[dict] = []
    for planner in (_plan_pip_install, _plan_run_script, _plan_shell_command):
        got = planner(text, low)
        if got:
            steps.extend(got)
    if not steps:
        return None
    summary = "; ".join(s["desc"] for s in steps)
    return {"summary": summary, "steps": steps}


if __name__ == "__main__":
    import json
    import sys

    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    q = " ".join(sys.argv[1:]) or "install matplotlib in the trig env"
    print(json.dumps(plan_actions(q), indent=2))
