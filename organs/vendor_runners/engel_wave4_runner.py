"""Engel AI — Wave 4 vendored modules runner.

Five new upstream projects integrated on 2026-05-25:

  engel_claw3d_main/             ← Claw3D        (3D virtual office for AI agents)
  engel_cubesandbox_main/        ← CubeSandbox   (AI agent sandbox service, E2B-compatible)
  engel_darwinian_evolver_main/  ← DarwinEvolver (evolutionary code/prompt optimizer)
  engel_hermes_agent_main/       ← HermesAgent   (Nous Research self-improving agent)
  engel_localsend_main/          ← LocalSend     (cross-platform LAN file sharing)

Public surface:
    render_wave4_list()               — enumerate all five
    render_<tool>_status()            — per-tool folder status
    render_<tool>_features()          — capabilities
    render_<tool>_docs()              — README excerpt
    render_<tool>_install()           — install instructions
    render_<tool>_start()             — how to run (where applicable)
"""
from __future__ import annotations

import os
from pathlib import Path

ENGEL_APP_ROOT: Path = Path(__file__).resolve().parent

_TOOLS = (
    ("claw3d",             "engel_claw3d_main",            "Claw3D",         "3D virtual office for AI agent teams — walk through a live agent workspace"),
    ("cubesandbox",        "engel_cubesandbox_main",        "CubeSandbox",    "Instant, concurrent, E2B-compatible AI agent sandbox service"),
    ("darwinian_evolver",  "engel_darwinian_evolver_main",  "DarwinEvolver",  "LLM-based evolutionary optimizer for code and prompts"),
    ("hermes_agent",       "engel_hermes_agent_main",       "HermesAgent",    "Nous Research self-improving agent — skill creation, learning loop, Telegram/Discord"),
    ("localsend",          "engel_localsend_main",          "LocalSend",      "Cross-platform LAN file sharing — no internet, no cloud, AirDrop-style"),
)

_DISPLAY_NAMES = {
    "claw3d":            "Claw3D 3D Agent Office",
    "cubesandbox":       "CubeSandbox Agent Sandbox",
    "darwinian_evolver": "Darwinian Evolver",
    "hermes_agent":      "Hermes Agent (Nous Research)",
    "localsend":         "LocalSend LAN Share",
}

_FEATURES = {
    "claw3d": [
        "3D virtual office — walk through your AI agent team workspace",
        "OpenClaw Gateway, Hermes, HTTP custom, and demo runtime profiles",
        "Multi-agent beta with agent cards and collaboration views",
        "Agent standups, code review, PR shipping visualised in 3D",
        "Self-hosted — runs entirely on your own infrastructure",
        "Node.js 20+ frontend, Docker-ready, REST/WebSocket gateway",
    ],
    "cubesandbox": [
        "Instant sandbox startup — tens of milliseconds",
        "Hardware-level isolation between sandboxes",
        "E2B-compatible API — drop-in replacement for hosted sandboxes",
        "High concurrency / high density deployment",
        "CubeMaster orchestrator + CubeNet networking layer",
        "CubeProxy for secure external access",
    ],
    "darwinian_evolver": [
        "Maintain a population of solution organisms (code or prompts)",
        "Each iteration: select parents, mutate, score, survive",
        "Works with noisy evaluators and unreliable mutators",
        "Only needs: initial organism, evaluator, mutator",
        "Outputs results.jsonl + population snapshots",
        "uv-based — zero extra deps beyond Python",
    ],
    "hermes_agent": [
        "Self-improving agent — creates and refines skills from experience",
        "Closed learning loop with FTS5 session search and LLM recall",
        "Telegram, Discord, Slack, WhatsApp, Signal gateway",
        "Built-in cron scheduler — daily reports, nightly backups",
        "Subagent delegation for parallel workstreams",
        "Seven backends: local, Docker, SSH, Modal, Daytona, Singularity, Vercel",
        "Honcho dialectic user modeling — builds a model of you over time",
        "Compatible with agentskills.io open skill standard",
    ],
    "localsend": [
        "Send files to any device on the same LAN — no internet required",
        "Cross-platform: Windows, macOS, Linux, iOS, Android",
        "AirDrop-style automatic device discovery",
        "End-to-end encrypted transfer (HTTPS + TLS)",
        "Flutter-based — lightweight native UI on all platforms",
        "Open source, no accounts, no cloud dependency",
    ],
}

_KEY_DOCS = {
    "claw3d":            ["README.md", "ARCHITECTURE.md", "AGENTS.md", "MULTI_AGENT_BETA.md"],
    "cubesandbox":       ["README.md", "docs/guide/quickstart.md"],
    "darwinian_evolver": ["README.md", "pyproject.toml", "darwinian_evolver/"],
    "hermes_agent":      ["README.md", "AGENTS.md", "SKILL.md", "WARP.md"],
    "localsend":         ["README.md", "CONTRIBUTING.md"],
}

_INSTALL = {
    "claw3d": (
        "Requirements: Node.js 20+, npm 10+\n"
        "  git clone https://github.com/iamlukethedev/Claw3D\n"
        "  cd Claw3D && npm install && npm run dev\n"
        "  Or run via Docker: docker-compose up"
    ),
    "cubesandbox": (
        "Requirements: Docker, Go 1.21+\n"
        "  git clone https://github.com/tencentcloud/CubeSandbox\n"
        "  make build\n"
        "  See docs/guide/quickstart.md for cluster setup"
    ),
    "darwinian_evolver": (
        "Requirements: Python 3.11+, uv\n"
        "  pip install uv\n"
        "  uv run darwinian_evolver --help\n"
        "  uv run darwinian_evolver parrot --num_iterations 3 --output_dir /tmp/out"
    ),
    "hermes_agent": (
        "Linux / macOS / WSL2:\n"
        "  curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash\n"
        "Windows (PowerShell beta):\n"
        "  iex (irm https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1)\n"
        "After install: hermes init  →  hermes chat"
    ),
    "localsend": (
        "Flutter-based app — download prebuilt binaries from:\n"
        "  https://localsend.org  or  GitHub Releases\n"
        "Dev build:\n"
        "  flutter pub get && flutter run"
    ),
}

_START = {
    "claw3d":            "npm run dev  (opens http://localhost:3000, connect runtime in Settings)",
    "cubesandbox":       "make run  or  docker-compose up  (exposes E2B-compatible REST API)",
    "darwinian_evolver": "uv run darwinian_evolver <problem> --num_iterations N --output_dir PATH",
    "hermes_agent":      "hermes chat  (CLI TUI)  |  hermes gateway  (Telegram/Discord bridge)",
    "localsend":         "Launch the LocalSend app — devices on the same LAN auto-discover",
}


def _path(folder: str) -> Path:
    return ENGEL_APP_ROOT / folder


def _exists(folder: str) -> bool:
    return _path(folder).exists()


def _readme(folder: str, max_lines: int = 20) -> str:
    readme = _path(folder) / "README.md"
    if not readme.exists():
        return "(no README found)"
    try:
        lines = readme.read_text(encoding="utf-8", errors="replace").splitlines()
        snippet = "\n".join(lines[:max_lines])
        if len(lines) > max_lines:
            snippet += f"\n… ({len(lines) - max_lines} more lines)"
        return snippet
    except Exception as exc:
        return f"(could not read README: {exc})"


def render_wave4_list() -> str:
    lines = ["Engel AI — Wave 4 Integrated Tools", "=" * 40, ""]
    for slug, folder, upstream, tag in _TOOLS:
        present = "OK" if _exists(folder) else "MISSING"
        lines.append(f"  [{present}]  engel.{slug}.*  ←  {upstream}")
        lines.append(f"          {tag}")
        lines.append(f"          folder: {folder}/")
        lines.append("")
    lines.append(f"Total: {len(_TOOLS)} Wave 4 modules")
    return "\n".join(lines)


def _status(slug: str, folder: str, upstream: str, tag: str) -> str:
    p = _path(folder)
    if not p.exists():
        return f"{_DISPLAY_NAMES[slug]} — folder MISSING: {folder}/"
    files = [f.name for f in p.iterdir() if not f.name.startswith(".")]
    file_count = len(files)
    size_mb = sum(
        f.stat().st_size for f in p.rglob("*") if f.is_file()
    ) / (1024 * 1024)
    return (
        f"{_DISPLAY_NAMES[slug]}\n"
        f"  upstream : {upstream}\n"
        f"  folder   : {folder}/\n"
        f"  files    : {file_count} top-level items\n"
        f"  size     : {size_mb:.1f} MB\n"
        f"  tag      : {tag}\n"
        f"  route ns : engel.{slug}.*"
    )


def _features(slug: str) -> str:
    lines = [f"{_DISPLAY_NAMES[slug]} — Features", ""]
    for feat in _FEATURES.get(slug, []):
        lines.append(f"  • {feat}")
    return "\n".join(lines)


def _docs(slug: str, folder: str) -> str:
    lines = [f"{_DISPLAY_NAMES[slug]} — README", ""]
    lines.append(_readme(folder))
    return "\n".join(lines)


def _install(slug: str) -> str:
    return f"{_DISPLAY_NAMES[slug]} — Install\n\n{_INSTALL.get(slug, '(no install info)')}"


def _start(slug: str) -> str:
    cmd = _START.get(slug)
    if not cmd:
        return f"{_DISPLAY_NAMES[slug]} — no standalone start command documented."
    return f"{_DISPLAY_NAMES[slug]} — Start\n\n  {cmd}"


# ── Public render functions ──────────────────────────────────────────────────

def render_claw3d_status() -> str:
    return _status("claw3d", "engel_claw3d_main", "Claw3D", _TOOLS[0][3])

def render_claw3d_features() -> str:
    return _features("claw3d")

def render_claw3d_docs() -> str:
    return _docs("claw3d", "engel_claw3d_main")

def render_claw3d_install() -> str:
    return _install("claw3d")

def render_claw3d_start() -> str:
    return _start("claw3d")


def render_cubesandbox_status() -> str:
    return _status("cubesandbox", "engel_cubesandbox_main", "CubeSandbox", _TOOLS[1][3])

def render_cubesandbox_features() -> str:
    return _features("cubesandbox")

def render_cubesandbox_docs() -> str:
    return _docs("cubesandbox", "engel_cubesandbox_main")

def render_cubesandbox_install() -> str:
    return _install("cubesandbox")


def render_darwinian_evolver_status() -> str:
    return _status("darwinian_evolver", "engel_darwinian_evolver_main", "DarwinEvolver", _TOOLS[2][3])

def render_darwinian_evolver_features() -> str:
    return _features("darwinian_evolver")

def render_darwinian_evolver_docs() -> str:
    return _docs("darwinian_evolver", "engel_darwinian_evolver_main")

def render_darwinian_evolver_install() -> str:
    return _install("darwinian_evolver")

def render_darwinian_evolver_run() -> str:
    return _start("darwinian_evolver")


def render_hermes_agent_status() -> str:
    return _status("hermes_agent", "engel_hermes_agent_main", "HermesAgent", _TOOLS[3][3])

def render_hermes_agent_features() -> str:
    return _features("hermes_agent")

def render_hermes_agent_docs() -> str:
    return _docs("hermes_agent", "engel_hermes_agent_main")

def render_hermes_agent_install() -> str:
    return _install("hermes_agent")

def render_hermes_agent_start() -> str:
    return _start("hermes_agent")

def render_hermes_agent_skills() -> str:
    p = _path("engel_hermes_agent_main") / "SKILL.md"
    if not p.exists():
        return "HermesAgent SKILL.md not found."
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[:40]
        return "\n".join(lines)
    except Exception as exc:
        return f"Could not read SKILL.md: {exc}"


def render_localsend_status() -> str:
    return _status("localsend", "engel_localsend_main", "LocalSend", _TOOLS[4][3])

def render_localsend_features() -> str:
    return _features("localsend")

def render_localsend_docs() -> str:
    return _docs("localsend", "engel_localsend_main")

def render_localsend_install() -> str:
    return _install("localsend")
