"""Engel AI ↔ batch of six vendored minor tools.

Backs the ``engel.<tool>.{status,features,docs}`` routes and the
umbrella ``engel.minor_tools.list`` route registered in
``engel_ai_update_routes``. Each tool is a small upstream project
that was case-preservingly rebranded and dropped under Engel App
in one batch commit:

  engel_humanizer_main/   ← humanizer  (Claude Code skill for de-AI-ifying text)
  engel_native_agent_main/       ← CodexAgent
  engel_ide_companion_main/      ← AI-ASSISTANT-CURSOR (Cursor IDE config / rules)
  engel_evolution_lab_main/      ← darwinian_evolver (GA framework for evolving code/prompts)
  engel_knowledge_graph_main/    ← graphify-7  (graph/diagram tool, 28 translated READMEs)
  engel_evolution_engine_main/     ← evolver-main (@evomap/evolver, Node.js)

These tools are too small / heterogeneous to deserve full
build/run runners each, so they share one runner that surfaces:
  - status   (tree path + manifest + README excerpt)
  - features (curated ability list + primary commands + entry points)
  - docs     (README + key doc file paths the user can open directly)

Public surface:

    render_minor_tools_list()        — enumerate all six
    render_<tool>_status()           — per-tool status
    render_<tool>_features()         — per-tool ability + commands
    render_<tool>_docs()             — per-tool README excerpt + doc index
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

ENGEL_APP_ROOT: Path = Path(__file__).resolve().parent

# Tool descriptor: (route slug, folder name, upstream label, one-line tag)
_TOOLS = (
    ("humanizer", "engel_humanizer_main", "humanizer",
     "Claude Code skill that removes AI-generated writing markers"),
    ("native_agent", "engel_native_agent_main", "CodexAgent",
     "Engel Native Agent dashboard and notification runtime"),
    ("ide",       "engel_ide_companion_main",    "AI-ASSISTANT-CURSOR",
     "Cursor IDE rules / Composer 2.0 configuration"),
    ("evolution_lab", "engel_evolution_lab_main", "darwinian_evolver",
     "Engel evolution lab for code and prompt experiments"),
    ("knowledge_graph", "engel_knowledge_graph_main", "graphify-7",
     "Engel knowledge graph builder (with 28 translated READMEs)"),
    ("evolution_engine", "engel_evolution_engine_main", "evolver",
     "@evomap/evolver Node.js evolutionary framework"),
)

_BRAND_SLUG_BY_TOOL = {
    "humanizer": "humanizer",
    "native_agent": "native_agent",
    "ide": "ide",
    "evolution_lab": "evolution_lab",
    "knowledge_graph": "knowledge_graph",
    "evolution_engine": "evolution_engine",
}

_DISPLAY_NAME_BY_TOOL = {
    "humanizer": "Humanizer",
    "native_agent": "Native Agent",
    "ide": "IDE Companion",
    "evolution_lab": "Evolution Lab",
    "knowledge_graph": "Knowledge Graph",
    "evolution_engine": "Evolution Engine",
}


def _brand_slug(tool_slug: str) -> str:
    return _BRAND_SLUG_BY_TOOL.get(tool_slug, tool_slug)


def _display_name(tool_slug: str) -> str:
    return _DISPLAY_NAME_BY_TOOL.get(tool_slug, tool_slug.replace("_", " ").title())


def _tool_root(folder: str) -> Path:
    return ENGEL_APP_ROOT / folder


def _read_readme_excerpt(root: Path, lines: int = 8) -> str:
    for name in ("README.md", "Readme.md", "readme.md", "SKILL.md"):
        p = root / name
        if p.is_file():
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                return "\n".join(text.splitlines()[:lines]).strip()
            except OSError as exc:
                return f"(README read failed: {exc})"
    return "(no README found)"


def _detect_manifest(root: Path) -> str:
    candidates: list[tuple[str, Optional[str]]] = []
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8", errors="replace"))
            candidates.append(("package.json", f"name={data.get('name','?')} version={data.get('version','?')}"))
        except (OSError, json.JSONDecodeError):
            candidates.append(("package.json", "(parse failed)"))
    pyp = root / "pyproject.toml"
    if pyp.is_file():
        try:
            text = pyp.read_text(encoding="utf-8", errors="replace")
            m_name = re.search(r'^\s*name\s*=\s*"([^"]+)"', text, re.MULTILINE)
            m_ver = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.MULTILINE)
            candidates.append((
                "pyproject.toml",
                f"name={m_name.group(1) if m_name else '?'} version={m_ver.group(1) if m_ver else '?'}",
            ))
        except OSError:
            candidates.append(("pyproject.toml", "(read failed)"))
    skill = root / "SKILL.md"
    if skill.is_file():
        candidates.append(("SKILL.md", "Claude Code / OpenCode skill manifest"))
    cargo = root / "Cargo.toml"
    if cargo.is_file():
        try:
            text = cargo.read_text(encoding="utf-8", errors="replace")
            m_name = re.search(r'^\s*name\s*=\s*"([^"]+)"', text, re.MULTILINE)
            m_ver = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.MULTILINE)
            candidates.append((
                "Cargo.toml",
                f"name={m_name.group(1) if m_name else '?'} version={m_ver.group(1) if m_ver else '?'}",
            ))
        except OSError:
            candidates.append(("Cargo.toml", "(read failed)"))
    if not candidates:
        return "(no manifest file detected)"
    return "; ".join(f"{n}: {v}" for n, v in candidates)


def _wrap(title: str, body: str) -> str:
    return (
        f"{title}\n\n{body}\n\n"
        "Safety:\n"
        "- Status/features/docs routes are read-only enumeration of vendored trees.\n"
        "- Phase B invoke routes may run fixed, bounded subprocess actions through Engel AI.\n"
        "- Autonomy and background work permitted (2026-05-19 ruling).\n"
        "- No mutation of Engel App router state."
    )


def _render_tool(slug: str, folder: str, label: str, tagline: str) -> str:
    root = _tool_root(folder)
    brand_slug = _brand_slug(slug)
    display_name = _display_name(slug)
    if not root.is_dir():
        return _wrap(
            f"Engel {slug.title()} — tree missing",
            f"Vendored tree not found at {root}.\nThe '{slug}' route is registered but the folder was removed or never landed.",
        )
    file_count = sum(1 for _ in root.rglob("*") if _.is_file())
    size_mb = sum(p.stat().st_size for p in root.rglob("*") if p.is_file()) / (1024 * 1024)
    body = (
        f"Brand slug        : engel_{brand_slug}\n"
        f"Route slug        : {slug}\n"
        f"Folder            : {root}\n"
        f"Upstream label    : {label}\n"
        f"Tagline           : {tagline}\n"
        f"Files / size      : {file_count} files, {size_mb:.2f} MB\n"
        f"Manifest detected : {_detect_manifest(root)}\n"
        f"\n"
        f"--- README excerpt (first 8 lines) ---\n"
        f"{_read_readme_excerpt(root, lines=8)}"
    )
    return _wrap(f"Engel {display_name} - status", body)


def render_minor_tools_list(_payload: str = "") -> str:
    lines = [
        f"Engel App vendored 'minor tools' batch (six small projects):\n",
    ]
    for slug, folder, label, tagline in _TOOLS:
        root = _tool_root(folder)
        present = "✓" if root.is_dir() else "✗ MISSING"
        lines.append(f"  {present} engel_{_brand_slug(slug):<18} ({label})")
        lines.append(f"      {tagline}")
        lines.append(f"      route: engel.{_brand_slug(slug)}.status")
        lines.append("")
    lines.append("Ask 'engel <slug> status' for per-tool details "
                 "(e.g. 'engel humanizer status').")
    return _wrap("Engel Minor Tools — inventory", "\n".join(lines))


# Per-tool entry points (kept as separate functions so route dispatch is
# straightforward and each tool can be extended later without affecting the
# others).
def render_humanizer_status(_payload: str = "") -> str:
    return _render_tool("humanizer", "engel_humanizer_main", "humanizer",
                        "Claude Code skill that removes AI-generated writing markers")


def render_native_agent_status(_payload: str = "") -> str:
    return _render_tool("native_agent", "engel_native_agent_main", "CodexAgent",
                        "Engel Native Agent dashboard and notification runtime")


def render_ide_status(_payload: str = "") -> str:
    return _render_tool("ide", "engel_ide_companion_main", "AI-ASSISTANT-CURSOR",
                        "Engel IDE Companion rules and workflow configuration")


def render_evolution_lab_status(_payload: str = "") -> str:
    return _render_tool("evolution_lab", "engel_evolution_lab_main", "darwinian_evolver",
                        "Engel Evolution Lab for code and prompt experiments")


def render_knowledge_graph_status(_payload: str = "") -> str:
    return _render_tool("knowledge_graph", "engel_knowledge_graph_main", "graphify-7",
                        "Engel Knowledge Graph builder")


def render_evolution_engine_status(_payload: str = "") -> str:
    return _render_tool("evolution_engine", "engel_evolution_engine_main", "evolver",
                        "Engel Evolution Engine Node.js runtime")


# ---------------------------------------------------------------------------
# Features + docs surfaces (Stage 2 unified Engel AI capability coverage)
# ---------------------------------------------------------------------------

# Curated per-tool ability lists. Source: each tool's README/SKILL.md.
# Updated 2026-05-20 alongside Stage 2 autonomy.
_FEATURES = {
    "humanizer": {
        "tagline": "Remove signs of AI-generated writing from text.",
        "abilities": [
            "Detect AI-writing patterns: inflated symbolism, em-dash overuse, vague attributions, rule-of-three, AI vocabulary, passive voice, negative parallelisms, filler phrases.",
            "Rewrite problematic sections while preserving meaning and intended tone.",
            "Voice calibration: analyze a user writing sample and match style on rewrite.",
            "Final anti-AI pass: identify remaining tells, then revise to not be obviously AI.",
        ],
        "primary_commands": [
            "Claude Code: /engel_humanizer  [paste text]",
            "OpenCode:    /engel_humanizer  [paste text]",
            "Or ask the model directly: 'humanize this text: ...'",
        ],
        "entry_points": ["SKILL.md (the active skill file)", "README.md", "WARP.md"],
        "needs": ["Claude Code or OpenCode skill loader; install per README"],
    },
    "native_agent": {
        "tagline": "Engel Native Agent background runtime + GUI dashboard variants.",
        "abilities": [
            "Background notification agent: watches for critical keywords (ERROR / failed / CRITICAL) and fires desktop notifications via plyer.",
            "Multiple GUI dashboard variants (PyQt + futuristic Tk variants).",
            "Configurable via config.yaml (agent loop interval, dry_run flag, log file).",
        ],
        "primary_commands": [
            "Launch_Engel_Native_Agent_Dashboard.bat",
            "launch_dashboard.bat",
            "python agent_module.py  (loads config.yaml)",
            "python gui_futuristic_dashboard_final.py",
            "python gui_pyqt.py",
        ],
        "entry_points": [
            "agent_module.py",
            "gui.py",
            "gui_futuristic_dashboard_final.py",
            "gui_futuristic_dashboard_enhanced.py",
            "gui_pyqt.py",
            "config.yaml",
            "test_agent.py",
        ],
        "needs": [
            "pyyaml, plyer (for notifications)",
            "config.yaml at D:/EngelNativeAgent/config.yaml (hardcoded path — relocate or shim if config lives elsewhere)",
        ],
    },
    "ide": {
        "tagline": "Cursor IDE configuration repo: rules, agents, skills, workflows.",
        "abilities": [
            "Composer 2.0 orchestration patterns (multi-file refactors).",
            "MDC rule engineering (`.cursor/rules/*.mdc`, glob-pattern targeting).",
            "Background agent deployment (`@background` tag + agents-config.json).",
            "Semantic context optimization (`@Codebase`, `@Symbols`, `@Files`).",
            "Zero-interaction refinement (Tab-to-Accept).",
        ],
        "primary_commands": [
            "Copy .cursorrules into your project root.",
            "Copy contents of .cursor/ into project's .cursor/ folder.",
            "Reference SKILLS.md / AGENTS.md / CLAUDE.md for in-IDE prompts.",
        ],
        "entry_points": [
            ".cursorrules",
            ".cursor/",
            "agents/",
            "configs/",
            "skills/",
            "workflows/",
            "AGENTS.md",
            "CLAUDE.md",
            "SKILLS.md",
        ],
        "needs": ["Cursor IDE installed on the consuming workstation."],
    },
    "evolution_lab": {
        "tagline": "Darwin-Goedel-inspired GA framework for evolving code and prompts.",
        "abilities": [
            "Maintain a population of solutions (organisms) and evolve them across iterations.",
            "Drop-in components: Initial Organism / Evaluator / Mutator.",
            "Resilient to noisy evaluators and unreliable mutators (works at ~20% mutator success).",
            "JSON evolution log + per-iteration population snapshots.",
            "Browser visualizer (lineage_visualizer.html) for evolutionary history.",
        ],
        "primary_commands": [
            "uv run engel_darwin parrot --num_iterations 3 --output_dir /tmp/parrot_output",
            "uv run engel_darwin --help",
            "Custom problems: subclass Organism / Evaluator / Mutator (see problems/parrot.py).",
        ],
        "entry_points": [
            "engel_darwin/ (Python package)",
            "scripts/",
            "lineage_visualizer.html",
            "pyproject.toml",
            "README.md",
        ],
        "needs": ["uv (recommended) or Python 3.10+ with the engel_darwin package installed."],
    },
    "knowledge_graph": {
        "tagline": "Map a project (code/docs/PDFs/images/videos) into a knowledge graph.",
        "abilities": [
            "Index any folder into graph.html (browseable) + GRAPH_REPORT.md (highlights) + graph.json (full graph).",
            "Mermaid call-flow architecture export.",
            "Plug-in works in Claude Code, Codex, OpenCode, Cursor, Gemini CLI, GitHub Copilot CLI, Aider, and more.",
            "Query the graph instead of grepping files.",
            "28 translated READMEs covering major languages (zh, ja, ko, de, fr, es, hi, pt, ru, ar, ...).",
        ],
        "primary_commands": [
            "engel_graphify .                    (index current directory)",
            "engel_graphify export callflow-html (Mermaid architecture)",
            "/engel_graphify  (inside an AI coding assistant)",
        ],
        "entry_points": [
            "engel_graphify/ (Python package)",
            "tests/",
            "docs/ (architecture + translated READMEs)",
            "pyproject.toml",
            "ARCHITECTURE.md",
            "CHANGELOG.md",
        ],
        "needs": [
            "Python 3.10+",
            "Install: uv tool install engel_graphifyy && engel_graphify install  (PyPI package name is 'engel_graphifyy' — double y)",
        ],
    },
    "evolution_engine": {
        "tagline": "GEP-powered self-evolution engine for AI agents (Node.js).",
        "abilities": [
            "Encode agent experience as Genes and Capsules under the GEP protocol.",
            "Auditable, reusable evolution assets (vs ad-hoc prompt tweaks).",
            "CLI runs in any git repo; works as embedded engine or CLI.",
            "Two usage shapes: CLI Quick Start (99% of users) and Run from Source (contributors).",
            "Reference: arXiv 2604.15097 — gene-evolved CritPt agents lift 9.1%->18.57% and 17.7%->27.14%.",
        ],
        "primary_commands": [
            "npm install -g @evomap/engel_evolver",
            "engel_evolver  (run in any git repo)",
            "node index.js  (run from source)",
        ],
        "entry_points": [
            "index.js",
            "src/",
            "examples/",
            "test/",
            "package.json",
            "SKILL.md",
        ],
        "needs": ["Node.js >= 18, npm"],
    },
}

# Per-tool key documentation file paths (relative to each tool root).
_KEY_DOCS = {
    "humanizer": ["SKILL.md", "README.md", "WARP.md", "LICENSE"],
    "native_agent": ["README.md", "config.yaml", "native_agent_dashboard_prompt.txt", "agent_module.py", "test_agent.py"],
    "ide": ["README.md", "AGENTS.md", "CLAUDE.md", "SKILLS.md", ".cursorrules", "CONTRIBUTING.md", "SECURITY.md"],
    "evolution_lab": ["README.md", "pyproject.toml", "offload.toml", "LICENSE"],
    "knowledge_graph": ["README.md", "ARCHITECTURE.md", "CHANGELOG.md", "AGENTS.md", "SECURITY.md", "pyproject.toml"],
    "evolution_engine": ["README.md", "SKILL.md", "package.json", "CONTRIBUTING.md", "LICENSE"],
}

# Mapping: route slug -> vendored folder (mirrors _TOOLS but indexed)
_FOLDER_BY_SLUG = {slug: folder for (slug, folder, _label, _tag) in _TOOLS}


def _render_features(slug: str) -> str:
    info = _FEATURES.get(slug)
    folder = _FOLDER_BY_SLUG.get(slug)
    if info is None or folder is None:
        return _wrap(
            f"Engel {slug.title()} — features (UNKNOWN TOOL)",
            f"No feature record for slug '{slug}'. Check engel_minor_tools_runner._FEATURES.",
        )
    root = _tool_root(folder)
    brand_slug = _brand_slug(slug)
    display_name = _display_name(slug)
    body_lines = [
        f"Brand slug        : engel_{brand_slug}",
        f"Route slug        : {slug}",
        f"Folder            : {root}",
        f"Tagline           : {info['tagline']}",
        "",
        "Abilities:",
    ]
    for ability in info["abilities"]:
        body_lines.append(f"- {ability}")
    body_lines.append("")
    body_lines.append("Primary commands:")
    for cmd in info["primary_commands"]:
        body_lines.append(f"  $ {cmd}")
    body_lines.append("")
    body_lines.append("Entry points (files / folders):")
    for ep in info["entry_points"]:
        present = "✓" if (root / ep.split(" ")[0]).exists() else " "
        body_lines.append(f"  [{present}] {ep}")
    body_lines.append("")
    body_lines.append("Needs / prerequisites:")
    for need in info["needs"]:
        body_lines.append(f"- {need}")
    return _wrap(f"Engel {display_name} - features and abilities", "\n".join(body_lines))


def _render_docs(slug: str) -> str:
    folder = _FOLDER_BY_SLUG.get(slug)
    docs = _KEY_DOCS.get(slug)
    if folder is None or docs is None:
        return _wrap(
            f"Engel {slug.title()} — docs (UNKNOWN TOOL)",
            f"No docs record for slug '{slug}'. Check engel_minor_tools_runner._KEY_DOCS.",
        )
    root = _tool_root(folder)
    brand_slug = _brand_slug(slug)
    display_name = _display_name(slug)
    body_lines = [
        f"Brand slug    : engel_{brand_slug}",
        f"Route slug    : {slug}",
        f"Folder        : {root}",
        "",
        "Key documentation files:",
    ]
    for rel in docs:
        p = root / rel
        if p.is_file():
            size_kb = p.stat().st_size / 1024
            body_lines.append(f"  ✓ {rel}  ({size_kb:.1f} KB)  -> {p}")
        else:
            body_lines.append(f"  ✗ {rel}  (not present)")
    body_lines.append("")
    body_lines.append("README excerpt (first 12 lines):")
    body_lines.append("---")
    body_lines.append(_read_readme_excerpt(root, lines=12))
    body_lines.append("---")
    return _wrap(f"Engel {display_name} - documentation", "\n".join(body_lines))


def render_humanizer_features(_payload: str = "") -> str: return _render_features("humanizer")
def render_humanizer_docs(_payload: str = "") -> str: return _render_docs("humanizer")


def render_native_agent_features(_payload: str = "") -> str:
    return _render_features("native_agent")


def render_native_agent_docs(_payload: str = "") -> str:
    return _render_docs("native_agent")


def render_ide_features(_payload: str = "") -> str:
    return _render_features("ide")


def render_ide_docs(_payload: str = "") -> str:
    return _render_docs("ide")


def render_evolution_lab_features(_payload: str = "") -> str:
    return _render_features("evolution_lab")


def render_evolution_lab_docs(_payload: str = "") -> str:
    return _render_docs("evolution_lab")


def render_knowledge_graph_features(_payload: str = "") -> str:
    return _render_features("knowledge_graph")


def render_knowledge_graph_docs(_payload: str = "") -> str:
    return _render_docs("knowledge_graph")


def render_evolution_engine_features(_payload: str = "") -> str:
    return _render_features("evolution_engine")


def render_evolution_engine_docs(_payload: str = "") -> str:
    return _render_docs("evolution_engine")


# ---------------------------------------------------------------------------
# Unified capabilities inventory (all 12 vendored projects in one view)
# ---------------------------------------------------------------------------

# This list is the single read-only source of truth for "what can Engel do?"
# across all vendored upstreams. Keep route_prefix in sync with
# engel_ai_update_routes.UPDATE_ROUTES. If you add routes for a project,
# extend its entry below so the unified inventory stays accurate.
_VENDORED_INVENTORY = [
    # 6 main projects (their own runners)
    ("engel_agent",     "hermes-agent",      "engel_agent_main",
     "Engel AI's NATIVE agent core (Stage 4: hermes-agent absorbed). Capabilities are addressable both at the top-level engel.* namespace AND under the legacy engel.engel_agent.* nested form.",
     "engel.engel_agent.*  (17 routes — legacy nested) + engel.gateway.* / engel.cron.* / engel.memory.* / engel.skills.* / engel.sessions.* / engel.plugins.* / engel.toolsets / engel.doctor / engel.top.status / engel.version / engel.invoke / engel.identity (16 top-level native routes — Stage 4)"),
    ("engel3d",         "Claw3D",            "engel3d_office_main",
     "3D office viewer / scene builder. Start/stop server, build artifact.",
     "engel.engel3d.*  (4 routes: status / start / stop / build)"),
    ("engel_sandbox",   "CubeSandbox",       "engelsandbox_main",
     "E2B-compatible Linux/KVM microVM sandbox cluster. Dashboard + sandboxes CRUD + bring-up.",
     "engel.engel_sandbox.*  (6 routes: status / nodes / list / create / delete / bring_up)"),
    ("engelcode",       "jcode",             "engelcode_main",
     "Rust TUI coding agent. Cargo build/invoke + bring-up.",
     "engel.engelcode.*  (6 routes: status / version / crates / build / invoke / bring_up)"),
    ("engel_main",      "OpenHuman (Tauri)", "engel_main",
     "Tauri desktop companion with cron / memory / channels (telegram / discord / whatsapp_web) tools.",
     "engel.engel_main.*  (9 routes: status / version / binaries / install / build / dev_start / dev_stop / tauri_build / bring_up)"),
    ("engel_lan",       "LocalSend",         "engel_lan_main",
     "LAN file sharing (Flutter app + CLI receiver).",
     "engel.engel_lan.*  (8 routes: status / version / cli_help / cli_receive_start/stop / app_dev_start/stop / bring_up)"),
    # 6 minor tools (shared runner)
    ("engel_humanizer", "humanizer",         "engel_humanizer_main",
     "Claude Code skill that removes AI-generated writing patterns.",
     "engel.engel_humanizer.*  (4 routes: status / features / docs / invoke)"),
    ("engel_native_agent", "CodexAgent",     "engel_native_agent_main",
     "Background notification agent + multiple GUI dashboard variants.",
     "engel.native_agent.*  (5 routes: status / features / docs / launch_dashboard / launch_agent)"),
    ("engel_ide",       "AI-ASSISTANT-CURSOR", "engel_ide_companion_main",
     "Cursor IDE rules / agents / skills / workflows config repo.",
     "engel.ide.*  (4 routes: status / features / docs / install_to_project)"),
    ("engel_evolution_lab", "darwinian_evolver", "engel_evolution_lab_main",
     "Darwin-Goedel-inspired GA framework for evolving code and prompts.",
     "engel.evolution_lab.*  (5 routes: status / features / docs / help / run_example)"),
    ("engel_knowledge_graph", "graphify-7",  "engel_knowledge_graph_main",
     "Map a project (code/docs/PDFs/images/videos) into a knowledge graph.",
     "engel.knowledge_graph.*  (5 routes: status / features / docs / help / build)"),
    ("engel_evolution_engine", "evolver",    "engel_evolution_engine_main",
     "GEP-powered self-evolution engine for AI agents (Node.js).",
     "engel.evolution_engine.*  (5 routes: status / features / docs / help / run)"),
]


# ---------------------------------------------------------------------------
# Invoke / primary-action surfaces — capability parity with the upstream zips
# ---------------------------------------------------------------------------
# These routes either (a) return content that constitutes the capability
# directly (humanizer = a Claude skill prompt), or (b) provide the exact
# command sequence Engel would run to invoke that capability. They are
# safe-by-default for smoke testing: no auto-install, no auto-launch, no
# host mutation. Real execution happens via the WSL bridge's allowlisted
# read-only entries (see wsl.ubuntu.engel_*_help) or via explicit user invocation.


def _read_full(root: Path, name: str) -> str:
    p = root / name
    if p.is_file():
        return p.read_text(encoding="utf-8", errors="replace")
    return f"({name} not found at {p})"


def _clean_output(text: object, *, limit: int = 8000) -> str:
    value = str(text or "").replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(value) > limit:
        return value[-limit:] + "\n[output truncated]"
    return value


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            proc = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="replace",
                timeout=8,
            )
            return str(pid) in (proc.stdout or "")
        except OSError:
            return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _read_pid(path: Path) -> Optional[int]:
    if not path.is_file():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _python_import_check(root: Path, modules: tuple[str, ...]) -> str:
    proc = subprocess.run(
        [sys.executable, "-c", "import " + ", ".join(modules)],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        timeout=15,
    )
    if proc.returncode == 0:
        return ""
    return _clean_output(proc.stderr or proc.stdout or "Python dependency check failed.")


def _native_agent_env(root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["ENGEL_NATIVE_AGENT_CONFIG_PATH"] = str(root / "config.yaml")
    env["ENGEL_NATIVE_AGENT_LOG_FILE"] = str(root / "engel_native_agent.log")
    env["PYTHONPATH"] = str(root) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


def _start_background_process(
    *,
    title: str,
    root: Path,
    command: list[str],
    pid_file: Path,
    log_file: Path,
    env: dict[str, str] | None = None,
) -> str:
    if not root.is_dir():
        return _wrap(title + " failed", f"Vendored tree missing at {root}.")
    existing = _read_pid(pid_file)
    if existing is not None and _pid_alive(existing):
        return _wrap(title + " already running", f"Existing pid={existing}.\nPID file: {pid_file}\nLog file: {log_file}")
    creationflags = 0x00000008 | 0x00000200 if sys.platform == "win32" else 0
    try:
        with open(log_file, "ab") as logf:
            proc = subprocess.Popen(
                command,
                cwd=str(root),
                stdout=logf,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags if sys.platform == "win32" else 0,
                close_fds=True,
                shell=False,
                env=env,
            )
    except OSError as exc:
        return _wrap(title + " failed", f"Could not spawn fixed command: {exc}")
    pid_file.write_text(str(proc.pid), encoding="utf-8")
    return _wrap(
        title + " started",
        "\n".join(
            [
                "Command: " + " ".join(command),
                "Working dir: " + str(root),
                "PID: " + str(proc.pid),
                "PID file: " + str(pid_file),
                "Log file: " + str(log_file),
            ]
        ),
    )


def _bytes_equal(left: Path, right: Path) -> bool:
    try:
        return left.read_bytes() == right.read_bytes()
    except OSError:
        return False


def _copy_file_with_backup(src: Path, dst: Path, backup_root: Path, rel: Path, copied: list[str], unchanged: list[str], backed_up: list[str]) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_file() and _bytes_equal(src, dst):
        unchanged.append(str(dst))
        return
    if dst.exists():
        backup_path = backup_root / rel
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, backup_path)
        backed_up.append(str(backup_path))
    shutil.copy2(src, dst)
    copied.append(str(dst))


def _copy_tree_with_backups(src: Path, dst: Path, backup_root: Path, rel_prefix: Path, copied: list[str], unchanged: list[str], backed_up: list[str]) -> None:
    if not src.is_dir():
        return
    for item in src.rglob("*"):
        if item.is_file():
            rel = rel_prefix / item.relative_to(src)
            _copy_file_with_backup(item, dst / item.relative_to(src), backup_root, rel, copied, unchanged, backed_up)


def _install_ide_config_to_engel_project() -> str:
    source = _tool_root("engel_ide_companion_main")
    target = ENGEL_APP_ROOT
    if not source.is_dir():
        return _wrap("Engel IDE Companion install failed", f"Vendored tree missing at {source}.")
    stamp = time.strftime("%Y%m%dT%H%M%S")
    backup_root = ENGEL_APP_ROOT / "backups" / "phase_b_ide_install" / stamp
    copied: list[str] = []
    unchanged: list[str] = []
    backed_up: list[str] = []
    if (source / ".cursorrules").is_file():
        _copy_file_with_backup(source / ".cursorrules", target / ".cursorrules", backup_root, Path(".cursorrules"), copied, unchanged, backed_up)
    for src, dst, rel in [
        (source / ".cursor", target / ".cursor", Path(".cursor")),
        (source / "agents", target / "agents", Path("agents")),
        (source / "skills", target / ".claude" / "skills", Path(".claude") / "skills"),
        (source / "workflows", target / "workflows", Path("workflows")),
    ]:
        _copy_tree_with_backups(src, dst, backup_root, rel, copied, unchanged, backed_up)
    lines = [
        "Target project: " + str(target),
        "Source tree: " + str(source),
        "Files copied/updated: " + str(len(copied)),
        "Files already current: " + str(len(unchanged)),
        "Existing files backed up: " + str(len(backed_up)),
    ]
    if copied:
        lines.extend(["", "Copied/updated:"])
        lines.extend("- " + path for path in copied[:40])
    if backed_up:
        lines.extend(["", "Backups:"])
        lines.extend("- " + path for path in backed_up[:40])
    lines.extend(
        [
            "",
            "Installed surfaces:",
            "- .cursorrules",
            "- .cursor/",
            "- agents/",
            "- .claude/skills/",
            "- workflows/",
        ]
    )
    return _wrap("Engel IDE Companion install to active Engel project", "\n".join(lines))


def render_humanizer_invoke(_payload: str = "") -> str:
    """The humanizer's capability IS the SKILL.md prompt. Return it ready-to-apply."""
    root = _tool_root("engel_humanizer_main")
    skill = _read_full(root, "SKILL.md")
    body = (
        "Engel humanizer skill is delivered as a prompt — apply it to any AI-generated text\n"
        "via Claude Code, OpenCode, or any LLM that accepts skill-style instructions.\n"
        "\n"
        "How to use:\n"
        "  1. Paste the SKILL.md content below as the system / skill prompt.\n"
        "  2. Append your draft text after a 'Humanize this text:' marker.\n"
        "  3. The model returns the humanized rewrite.\n"
        "\n"
        "Direct slash-command usage (if the skill is installed):\n"
        "  /engel_humanizer  [paste text]\n"
        "\n"
        "----- BEGIN SKILL.md -----\n"
        f"{skill}\n"
        "----- END SKILL.md -----\n"
    )
    return _wrap("Engel Humanizer — invoke (skill prompt)", body)


def _render_native_agent_launch_dashboard_instructions(_payload: str = "") -> str:
    root = _tool_root("engel_native_agent_main")
    bat = root / "Launch_Engel_Native_Agent_Dashboard.bat"
    final_gui = root / "gui_futuristic_dashboard_final.py"
    pyqt_gui = root / "gui_pyqt.py"
    body = (
        "Engel Native Agent ships several GUI dashboard variants (PyQt6 + futuristic Tk).\n"
        "All require the agent_module.py config — by default it expects\n"
        "config.yaml at D:/EngelNativeAgent/config.yaml (hardcoded). The vendored\n"
        "config.yaml lives at:\n"
        f"  {root / 'config.yaml'}\n"
        "\n"
        "Launch commands (Windows host):\n"
        f"  cmd /c \"{bat}\"\n"
        f"  python \"{final_gui}\"\n"
        f"  python \"{pyqt_gui}\"\n"
        "\n"
        "Prerequisites:\n"
        "  - python -m pip install PyQt6 PyYAML plyer\n"
        "  - Either D:/EngelNativeAgent/config.yaml exists, OR the dashboard is\n"
        "    relaunched after pointing CONFIG_PATH at the vendored config.\n"
        "\n"
        "This route is read-only / descriptive. To actually launch, run one\n"
        "of the commands above in a Windows shell."
    )
    return _wrap("Engel Native Agent - dashboard launch instructions", body)


def _render_native_agent_launch_agent_instructions(_payload: str = "") -> str:
    root = _tool_root("engel_native_agent_main")
    body = (
        "Engel Native Agent (agent_module.py) is a background notification\n"
        "agent that watches for critical-keyword events and fires Plyer\n"
        "desktop notifications. It loops on config.agent.loop_interval_seconds.\n"
        "\n"
        "Launch (Windows host):\n"
        f"  python \"{root / 'agent_module.py'}\"\n"
        "\n"
        "Test (Windows host):\n"
        f"  python \"{root / 'test_agent.py'}\"\n"
        "\n"
        "Default config (from config.yaml):\n"
        "  - agent.dry_run: true\n"
        "  - agent.loop_interval_seconds: 60\n"
        "  - alerts.enabled: true, log_file: D:/EngelNativeAgent/engel_native_agent.log\n"
        "\n"
        "Prerequisites:\n"
        "  - python -m pip install PyYAML plyer\n"
        "  - config.yaml resolvable (default path is hardcoded — adjust or shim).\n"
        "\n"
        "Stage 3 authorizes both 'python -m pip install ...' (inside the\n"
        "recorded WSL Ubuntu distro) and process launch. For Windows host\n"
        "execution, run the command above manually."
    )
    return _wrap("Engel Native Agent - agent launch instructions", body)


def _render_ide_install_to_project_instructions(_payload: str = "") -> str:
    root = _tool_root("engel_ide_companion_main")
    body = (
        "Engel IDE Companion is a config repo for Cursor IDE. To activate its\n"
        "rules / agents / skills / workflows in any project, copy the\n"
        "relevant files into that project's root.\n"
        "\n"
        "Files / folders to copy (source → destination):\n"
        f"  {root / '.cursorrules'}             → <project>/.cursorrules\n"
        f"  {root / '.cursor'}                  → <project>/.cursor/\n"
        f"  {root / 'agents'}                   → <project>/agents/  (or your preferred path)\n"
        f"  {root / 'skills'}                   → <project>/.claude/skills/  (or ~/.claude/skills/)\n"
        f"  {root / 'workflows'}                → <project>/workflows/\n"
        "\n"
        "PowerShell (Windows):\n"
        f"  Copy-Item '{root}\\.cursorrules' '<project>\\.cursorrules'\n"
        f"  Copy-Item -Recurse '{root}\\.cursor' '<project>\\.cursor'\n"
        "\n"
        "Bash (Linux/macOS/WSL):\n"
        f"  cp '{root}/.cursorrules' <project>/.cursorrules\n"
        f"  cp -r '{root}/.cursor' <project>/.cursor\n"
        "\n"
        "After install, restart Cursor and verify rules apply via:\n"
        "  > Does this file comply with our rules?\n"
        "\n"
        "Companion docs Engel can also surface for the active project:\n"
        f"  - {root / 'CLAUDE.md'}      (Claude-side guidance)\n"
        f"  - {root / 'AGENTS.md'}      (agent registry)\n"
        f"  - {root / 'SKILLS.md'}      (Composer 2.0 / MDC / background agents)\n"
        "\n"
        "This route is descriptive — copies happen when the user (or another\n"
        "Engel route with explicit target payload) invokes the commands above."
    )
    return _wrap("Engel IDE Companion - install to a project", body)


def _wsl_bridge_call(command_id: str, friendly: str) -> str:
    """Helper: invoke a WSL bridge command and format the result. Degrades honestly."""
    try:
        import engel_wsl_bridge  # local import to avoid hard dependency at module load
        result = engel_wsl_bridge.run_command_id(command_id)
    except Exception as exc:  # pragma: no cover — bridge always present in tree
        return _wrap(
            f"{friendly} — bridge unavailable",
            f"engel_wsl_bridge failed to import or run: {type(exc).__name__}: {exc}",
        )
    payload = result.as_dict() if hasattr(result, "as_dict") else dict(result)
    status = payload.get("status", "unknown")
    rc = payload.get("returncode")
    stdout = (payload.get("stdout") or "").strip()
    stderr = (payload.get("stderr") or "").strip()
    err = (payload.get("error") or "").strip()
    body_lines = [
        f"Bridge command : {command_id}",
        f"argv           : {' '.join(payload.get('argv', []))}",
        f"Status         : {status}   (returncode={rc}, timeout={payload.get('timeout_seconds')}s)",
        "",
    ]
    if stdout:
        body_lines.append("stdout:")
        body_lines.append(stdout)
        body_lines.append("")
    if stderr:
        body_lines.append("stderr:")
        body_lines.append(stderr)
        body_lines.append("")
    if err:
        body_lines.append("error: " + err)
        body_lines.append("")
    if status in ("missing", "blocked") or rc not in (0, None):
        body_lines.append(
            "Hint: this tool may not yet be installed in the recorded WSL Ubuntu "
            "distro. Stage 3 authorizes installs; install instructions are in the "
            "matching `.features` route for this tool."
        )
    return _wrap(friendly, "\n".join(body_lines))


def _render_evolution_lab_help_instructions(_payload: str = "") -> str:
    return _wsl_bridge_call("wsl.ubuntu.engel_evolution_lab_help", "Engel Evolution Lab - CLI help")


def _render_evolution_lab_run_example_instructions(_payload: str = "") -> str:
    body = (
        "Engel Evolution Lab canonical example: the 'parrot' problem.\n"
        "\n"
        "Run inside the recorded WSL Ubuntu distro (Stage 3 authorizes the\n"
        "necessary `uv` invocation and any package installs uv triggers):\n"
        "\n"
        "  uv run engel_darwin parrot --num_iterations 3 --output_dir /tmp/parrot_output\n"
        "\n"
        "Output:\n"
        "  - /tmp/parrot_output/results.jsonl   evolution log\n"
        "  - /tmp/parrot_output/snapshots/      population snapshots per iteration\n"
        "\n"
        "After the run, open lineage_visualizer.html in a browser to inspect\n"
        "the evolutionary history (the visualizer is a static HTML viewer; you\n"
        "do not need a server).\n"
        "\n"
        "This route is read-only / descriptive — run the command above\n"
        "manually (or via a future engel.evolution_lab.run_now route that\n"
        "actually shells out via the WSL bridge)."
    )
    return _wrap("Engel Evolution Lab - run example (parrot)", body)


def _render_knowledge_graph_help_instructions(_payload: str = "") -> str:
    return _wsl_bridge_call("wsl.ubuntu.engel_knowledge_graph_help", "Engel Knowledge Graph - CLI help")


def _render_knowledge_graph_build_instructions(_payload: str = "") -> str:
    body = (
        "Engel Knowledge Graph maps a folder of code / docs / PDFs / images / videos\n"
        "into a navigable knowledge graph.\n"
        "\n"
        "Run inside the recorded WSL Ubuntu distro:\n"
        "\n"
        "  engel_graphify <folder>          (index the folder)\n"
        "  engel_graphify export callflow-html  (Mermaid architecture diagram)\n"
        "\n"
        "Outputs (written to <folder>/engel_graphify-out/):\n"
        "  - graph.html        browseable interactive graph\n"
        "  - GRAPH_REPORT.md   highlights / surprising connections / suggested Qs\n"
        "  - graph.json        full graph (query without re-reading files)\n"
        "\n"
        "Install (one-time, Stage 3 authorizes this inside the distro):\n"
        "  uv tool install engel_graphifyy && engel_graphify install\n"
        "  # or: pipx install engel_graphifyy && engel_graphify install\n"
        "  # PyPI package name is 'engel_graphifyy' (double y) — CLI command stays engel_graphify.\n"
        "\n"
        "Works in: Claude Code, Codex, OpenCode, Cursor, Gemini CLI, GitHub\n"
        "Copilot CLI, Aider, and more (slash command `/engel_graphify`)."
    )
    return _wrap("Engel Knowledge Graph - build a folder graph (commands)", body)


def _render_evolution_engine_help_instructions(_payload: str = "") -> str:
    return _wsl_bridge_call("wsl.ubuntu.engel_evolution_engine_help", "Engel Evolution Engine - CLI help")


def _render_evolution_engine_run_instructions(_payload: str = "") -> str:
    body = (
        "Engel Evolution Engine (GEP self-evolution engine, Node.js) — encodes agent\n"
        "experience as Genes and Capsules under the GEP protocol.\n"
        "\n"
        "Install (one-time, Stage 3 authorizes `npm install` inside the distro):\n"
        "  npm install -g @evomap/engel_evolver\n"
        "\n"
        "Run (inside any git repo you want to evolve):\n"
        "  cd <your-repo>\n"
        "  engel_evolver\n"
        "\n"
        "Run from source (contributors):\n"
        "  cd /mnt/d/b.WorkSpace/Engel\\ App/engel_evolution_engine_main\n"
        "  node index.js\n"
        "\n"
        "Reference paper: arXiv 2604.15097 — gene-evolved CritPt agents lift\n"
        "9.1% -> 18.57% and 17.7% -> 27.14% across 4,590 controlled trials.\n"
        "\n"
        "Requires: Node.js >= 18, npm. Both available inside the recorded\n"
        "WSL Ubuntu distro after `apt install nodejs npm` (Stage 3 authorized)."
    )
    return _wrap("Engel Evolution Engine - run instructions", body)


# Phase B native invoke implementations. These definitions intentionally
# override the earlier descriptive renderers while preserving the same Engel AI
# route IDs, aliases, and dispatch path.
def render_native_agent_launch_dashboard(_payload: str = "") -> str:
    root = _tool_root("engel_native_agent_main")
    missing = _python_import_check(root, ("yaml", "plyer", "PyQt6"))
    if missing:
        return _wrap(
            "Engel Native Agent dashboard launch blocked by missing Python dependency",
            "The route executed a bounded dependency preflight and did not start the dashboard.\n\n"
            "Missing/preflight output:\n"
            + missing
            + "\n\n"
            "Host install is intentionally not automatic here. Install PyQt6, PyYAML, and plyer on the host Python, then rerun this Engel AI route.",
        )
    return _start_background_process(
        title="Engel Native Agent dashboard",
        root=root,
        command=[sys.executable, str(root / "gui_futuristic_dashboard_final_popup.py")],
        pid_file=root / ".engel_native_agent_dashboard.pid",
        log_file=root / ".engel_native_agent_dashboard.log",
        env=_native_agent_env(root),
    )


def render_native_agent_launch_agent(_payload: str = "") -> str:
    root = _tool_root("engel_native_agent_main")
    missing = _python_import_check(root, ("yaml", "plyer"))
    if missing:
        return _wrap(
            "Engel Native Agent launch blocked by missing Python dependency",
            "The route executed a bounded dependency preflight and did not start the background agent.\n\n"
            "Missing/preflight output:\n"
            + missing
            + "\n\n"
            "Host install is intentionally not automatic here. Install PyYAML and plyer on the host Python, then rerun this Engel AI route.",
        )
    agent_code = (
        "from agent_module import start_agent, agent_status\n"
        "import time\n"
        "start_agent()\n"
        "print('Engel Native Agent started: ' + repr(agent_status), flush=True)\n"
        "while True:\n"
        "    time.sleep(60)\n"
    )
    return _start_background_process(
        title="Engel Native Agent background agent",
        root=root,
        command=[sys.executable, "-c", agent_code],
        pid_file=root / ".engel_native_agent.pid",
        log_file=root / ".engel_native_agent.log",
        env=_native_agent_env(root),
    )


def render_ide_install_to_project(_payload: str = "") -> str:
    return _install_ide_config_to_engel_project()


def render_evolution_lab_run_example(_payload: str = "") -> str:
    return _wsl_bridge_call("wsl.ubuntu.engel_evolution_lab_run_example", "Engel Evolution Lab - run example (parrot)")


def render_knowledge_graph_build(_payload: str = "") -> str:
    return _wsl_bridge_call("wsl.ubuntu.engel_knowledge_graph_build", "Engel Knowledge Graph - build")


def render_evolution_engine_run(_payload: str = "") -> str:
    return _wsl_bridge_call("wsl.ubuntu.engel_evolution_engine_run", "Engel Evolution Engine - run once")


def render_evolution_lab_help(_payload: str = "") -> str:
    return _wsl_bridge_call("wsl.ubuntu.engel_evolution_lab_help", "Engel Evolution Lab - CLI help")


def render_knowledge_graph_help(_payload: str = "") -> str:
    return _wsl_bridge_call("wsl.ubuntu.engel_knowledge_graph_help", "Engel Knowledge Graph - CLI help")


def render_evolution_engine_help(_payload: str = "") -> str:
    return _wsl_bridge_call("wsl.ubuntu.engel_evolution_engine_help", "Engel Evolution Engine - CLI help")


def render_capabilities_list(_payload: str = "") -> str:
    """Top-level inventory of every vendored Engel project + how to reach its features.

    One screen. Read-only. Single source of truth for "what does Engel do?"
    """
    lines = [
        "All 12 vendored projects, surfaced through Engel AI as one unified system:",
        "",
    ]
    for slug, upstream, folder, tagline, routes in _VENDORED_INVENTORY:
        root = _tool_root(folder)
        present = "✓" if root.is_dir() else "✗ MISSING"
        lines.append(f"  {present} {slug:<18} (← {upstream})")
        lines.append(f"      {tagline}")
        lines.append(f"      Routes: {routes}")
        lines.append("")
    lines.append("Also under engel.* :")
    lines.append("  - engel.progress_dashboard.status  — top-level Engel status")
    lines.append("  - engel.memory_candidate_inventory.status")
    lines.append("  - engel.archive_shelf_manager.status")
    lines.append("  - engel.wsl.*               — WSL allowlisted bridge (5 routes)")
    lines.append("  - engel.wsl_ubuntu.*        — WSL Ubuntu Runtime Dependency contract (Stage 2, 4 routes)")
    lines.append("  - engel.minor_tools.list    — inventory of the 6 minor tools (above)")
    lines.append("")
    lines.append("Ask 'engel <slug> features' for ability detail or 'engel <slug> docs' for README + key docs.")
    return _wrap("Engel AI — full vendored capabilities inventory", "\n".join(lines))
