"""Engel AI — batch runner for the Wave 2 vendored modules.

Ten new upstream projects were copied into Engel App on 2026-05-24 and
surfaced under the ``engel.<tool>.{status,features,docs}`` route pattern:

  engel_cli_anything_main/    ← CLI-Anything  (300+ tool plugin hub)
  engel_git_nexus_main/       ← GitNexus      (AI-powered git workflow)
  engel_octogent_main/        ← octogent      (8-agent orchestration swarm)
  engel_open_agents_main/     ← open-agents   (open-source agent framework)
  engel_airllm_main/          ← airllm        (memory-efficient local LLM inference)
  engel_jarvis_main/          ← OpenJarvis    (Jarvis-style assistant runtime)
  engel_chat_ui_main/         ← agent-chat-ui (streaming chat frontend)
  engel_ai_gallery_main/      ← ai-dev-gallery (AI capability gallery / demos)
  engel_cluster_main/         ← cluster       (multi-node cluster manager)
  engel_knowledge_graph_v2_main/ ← graphify-8 (v2 knowledge graph builder)

Public surface:
    render_new_tools_list()       — enumerate all ten
    render_<tool>_status()        — per-tool status
    render_<tool>_features()      — per-tool capabilities + commands
    render_<tool>_docs()          — per-tool README excerpt + doc index
"""
from __future__ import annotations

import os
from pathlib import Path

ENGEL_APP_ROOT: Path = Path(__file__).resolve().parent

_TOOLS = (
    ("cli_anything",       "engel_cli_anything_main",       "CLI-Anything",
     "300+ CLI tool plugin hub — any tool, any shell, any project"),
    ("git_nexus",          "engel_git_nexus_main",          "GitNexus",
     "AI-powered git workflow automation and commit intelligence"),
    ("octogent",           "engel_octogent_main",           "octogent",
     "8-agent orchestration swarm with unified task routing"),
    ("open_agents",        "engel_open_agents_main",        "open-agents",
     "Open-source multi-agent framework for tool-using LLM apps"),
    ("airllm",             "engel_airllm_main",             "AirLLM",
     "Memory-efficient local LLM inference (70B on 4GB VRAM)"),
    ("jarvis",             "engel_jarvis_main",             "OpenJarvis",
     "Jarvis-style personal AI assistant runtime"),
    ("chat_ui",            "engel_chat_ui_main",            "agent-chat-ui",
     "Streaming chat frontend with tool-call visualization"),
    ("ai_gallery",         "engel_ai_gallery_main",         "ai-dev-gallery",
     "AI capability gallery and interactive demos"),
    ("cluster",            "engel_cluster_main",            "cluster",
     "Multi-node cluster manager and job distributor"),
    ("knowledge_graph_v2", "engel_knowledge_graph_v2_main", "graphify-8",
     "Engel knowledge graph builder v2 (graphify-8 upstream)"),
)

_DISPLAY_NAMES = {
    "cli_anything":       "CLI-Anything Hub",
    "git_nexus":          "Git Nexus",
    "octogent":           "Octogent Swarm",
    "open_agents":        "Open Agents",
    "airllm":             "AirLLM",
    "jarvis":             "Jarvis",
    "chat_ui":            "Agent Chat UI",
    "ai_gallery":         "AI Dev Gallery",
    "cluster":            "Cluster Manager",
    "knowledge_graph_v2": "Knowledge Graph V2",
}

_FEATURES = {
    "cli_anything": [
        "300+ pre-built CLI tool plugins (blender, audacity, chromadb, QGIS, …)",
        "cli-hub meta-skill for routing any tool via natural language",
        "Plugin manifest with version pinning and validation",
        "Works offline — no cloud required",
    ],
    "git_nexus": [
        "AI-assisted commit message generation",
        "Branch strategy advisor",
        "PR review summarizer",
        "Git history knowledge extraction",
    ],
    "octogent": [
        "8-agent swarm with role specialization",
        "Unified task queue with priority routing",
        "Agent health monitoring and auto-restart",
        "Docker + local process support",
    ],
    "open_agents": [
        "Open-source multi-agent framework",
        "Tool-use and function-calling agents",
        "Memory-aware agent sessions",
        "Plugin/skill extension system",
    ],
    "airllm": [
        "Run 70B parameter models on 4GB VRAM",
        "Layer-wise quantization and offloading",
        "Compatible with HuggingFace model hub",
        "MacOS / Linux / Windows CPU+GPU support",
    ],
    "jarvis": [
        "Jarvis-style voice and text assistant",
        "Task planning and decomposition",
        "Calendar, reminder, and note integrations",
        "Pluggable skill system",
    ],
    "chat_ui": [
        "Streaming chat interface with real-time tokens",
        "Tool-call visualization and approval UI",
        "Multi-model selector",
        "History persistence and export",
    ],
    "ai_gallery": [
        "Interactive AI capability demos",
        "Windows AI SDK / WinML integration",
        "Local model benchmark runner",
        "Developer getting-started guides",
    ],
    "cluster": [
        "Multi-node cluster setup and management",
        "Job submission and result collection",
        "Node health monitoring",
        "Load balancing across workers",
    ],
    "knowledge_graph_v2": [
        "Build project knowledge graphs from source",
        "Mermaid + GraphViz diagram export",
        "Symbol-level relationship extraction",
        "28 translated README variants",
    ],
}

_KEY_DOCS = {
    "cli_anything":       ["README.md", "cli-hub/README.md", "cli-hub-meta-skill/README.md"],
    "git_nexus":          ["README.md", "ARCHITECTURE.md", "CHANGELOG.md"],
    "octogent":           ["README.md", "AGENTS.md", "packages/"],
    "open_agents":        ["README.md", "ARCHITECTURE.md", "GUARDRAILS.md"],
    "airllm":             ["README.md"],
    "jarvis":             ["README.md"],
    "chat_ui":            ["README.md"],
    "ai_gallery":         ["README.md"],
    "cluster":            ["README.md"],
    "knowledge_graph_v2": ["README.md"],
}


def _tool_path(folder: str) -> Path:
    return ENGEL_APP_ROOT / folder


def _exists(folder: str) -> bool:
    return _tool_path(folder).exists()


def _readme(folder: str, max_lines: int = 20) -> str:
    readme = _tool_path(folder) / "README.md"
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


def render_new_tools_list() -> str:
    lines = ["Engel AI — Wave 2 Integrated Tools", "=" * 40, ""]
    for slug, folder, upstream, tag in _TOOLS:
        present = "OK" if _exists(folder) else "MISSING"
        lines.append(f"  [{present}]  engel.{slug}.*  ←  {upstream}")
        lines.append(f"          {tag}")
        lines.append(f"          folder: {folder}/")
        lines.append("")
    lines.append(f"Total: {len(_TOOLS)} new tools")
    return "\n".join(lines)


def _render_tool_status(slug: str, folder: str, upstream: str, tag: str) -> str:
    root = _tool_path(folder)
    lines = [
        f"Engel {_DISPLAY_NAMES[slug]} — Status",
        "=" * 40,
        f"Upstream:  {upstream}",
        f"Folder:    {folder}/",
        f"Present:   {'YES' if root.exists() else 'NO — folder missing'}",
        f"Tag:       {tag}",
        "",
    ]
    if root.exists():
        try:
            items = [p.name for p in sorted(root.iterdir())][:12]
            lines.append("Top-level contents:")
            for item in items:
                lines.append(f"  {item}")
        except Exception:
            pass
    return "\n".join(lines)


def _render_tool_features(slug: str, upstream: str) -> str:
    lines = [
        f"Engel {_DISPLAY_NAMES[slug]} — Features",
        "=" * 40,
        f"Upstream: {upstream}",
        "",
        "Capabilities:",
    ]
    for feat in _FEATURES.get(slug, ["(no feature list yet)"]):
        lines.append(f"  • {feat}")
    return "\n".join(lines)


def _render_tool_docs(slug: str, folder: str, upstream: str) -> str:
    lines = [
        f"Engel {_DISPLAY_NAMES[slug]} — Docs",
        "=" * 40,
        f"Upstream: {upstream}",
        "",
        "Key doc files:",
    ]
    root = _tool_path(folder)
    for doc in _KEY_DOCS.get(slug, ["README.md"]):
        full = root / doc
        status = "exists" if full.exists() else "not found"
        lines.append(f"  {doc}  [{status}]")
    lines += ["", "README excerpt:", "", _readme(folder)]
    return "\n".join(lines)


# --- Public render functions (one per tool × status/features/docs) ---

def render_cli_anything_status() -> str:
    return _render_tool_status("cli_anything", "engel_cli_anything_main", "CLI-Anything", _TOOLS[0][3])

def render_cli_anything_features() -> str:
    return _render_tool_features("cli_anything", "CLI-Anything")

def render_cli_anything_docs() -> str:
    return _render_tool_docs("cli_anything", "engel_cli_anything_main", "CLI-Anything")


def render_git_nexus_status() -> str:
    return _render_tool_status("git_nexus", "engel_git_nexus_main", "GitNexus", _TOOLS[1][3])

def render_git_nexus_features() -> str:
    return _render_tool_features("git_nexus", "GitNexus")

def render_git_nexus_docs() -> str:
    return _render_tool_docs("git_nexus", "engel_git_nexus_main", "GitNexus")


def render_octogent_status() -> str:
    return _render_tool_status("octogent", "engel_octogent_main", "octogent", _TOOLS[2][3])

def render_octogent_features() -> str:
    return _render_tool_features("octogent", "octogent")

def render_octogent_docs() -> str:
    return _render_tool_docs("octogent", "engel_octogent_main", "octogent")


def render_open_agents_status() -> str:
    return _render_tool_status("open_agents", "engel_open_agents_main", "open-agents", _TOOLS[3][3])

def render_open_agents_features() -> str:
    return _render_tool_features("open_agents", "open-agents")

def render_open_agents_docs() -> str:
    return _render_tool_docs("open_agents", "engel_open_agents_main", "open-agents")


def render_airllm_status() -> str:
    return _render_tool_status("airllm", "engel_airllm_main", "AirLLM", _TOOLS[4][3])

def render_airllm_features() -> str:
    return _render_tool_features("airllm", "AirLLM")

def render_airllm_docs() -> str:
    return _render_tool_docs("airllm", "engel_airllm_main", "AirLLM")


def render_jarvis_status() -> str:
    return _render_tool_status("jarvis", "engel_jarvis_main", "OpenJarvis", _TOOLS[5][3])

def render_jarvis_features() -> str:
    return _render_tool_features("jarvis", "OpenJarvis")

def render_jarvis_docs() -> str:
    return _render_tool_docs("jarvis", "engel_jarvis_main", "OpenJarvis")


def render_chat_ui_status() -> str:
    return _render_tool_status("chat_ui", "engel_chat_ui_main", "agent-chat-ui", _TOOLS[6][3])

def render_chat_ui_features() -> str:
    return _render_tool_features("chat_ui", "agent-chat-ui")

def render_chat_ui_docs() -> str:
    return _render_tool_docs("chat_ui", "engel_chat_ui_main", "agent-chat-ui")


def render_ai_gallery_status() -> str:
    return _render_tool_status("ai_gallery", "engel_ai_gallery_main", "ai-dev-gallery", _TOOLS[7][3])

def render_ai_gallery_features() -> str:
    return _render_tool_features("ai_gallery", "ai-dev-gallery")

def render_ai_gallery_docs() -> str:
    return _render_tool_docs("ai_gallery", "engel_ai_gallery_main", "ai-dev-gallery")


def render_cluster_status() -> str:
    return _render_tool_status("cluster", "engel_cluster_main", "cluster", _TOOLS[8][3])

def render_cluster_features() -> str:
    return _render_tool_features("cluster", "cluster")

def render_cluster_docs() -> str:
    return _render_tool_docs("cluster", "engel_cluster_main", "cluster")


def render_knowledge_graph_v2_status() -> str:
    return _render_tool_status("knowledge_graph_v2", "engel_knowledge_graph_v2_main", "graphify-8", _TOOLS[9][3])

def render_knowledge_graph_v2_features() -> str:
    return _render_tool_features("knowledge_graph_v2", "graphify-8")

def render_knowledge_graph_v2_docs() -> str:
    return _render_tool_docs("knowledge_graph_v2", "engel_knowledge_graph_v2_main", "graphify-8")


# ── Wave 2 extended render functions ─────────────────────────────────────────

# GitNexus
def render_git_nexus_plugins() -> str:
    root = _tool_path("engel_git_nexus_main")
    integrations = [
        ("gitnexus-claude-plugin/", "Claude Code plugin — AI commit + PR analysis inside Claude"),
        ("gitnexus-cursor-integration/", "Cursor IDE integration — commit suggestion in-editor"),
        ("gitnexus-web/",              "Web dashboard — PR review and branch analytics"),
        ("gitnexus/",                  "Core CLI — gitnexus commit, branch, diff, history"),
    ]
    lines = ["Engel Git Nexus — Plugin Integrations", "=" * 40, ""]
    for folder, desc in integrations:
        path = root / folder.rstrip("/")
        present = "OK" if path.exists() else "missing"
        lines.append(f"  [{present}]  {folder}")
        lines.append(f"           {desc}")
        lines.append("")
    return "\n".join(lines)


def render_git_nexus_install() -> str:
    root = _tool_path("engel_git_nexus_main")
    return "\n".join([
        "Engel Git Nexus — Install",
        "=" * 40,
        f"Folder: {root}",
        "",
        "Prerequisites: Node.js 18+, pnpm",
        "",
        "Install steps:",
        "  cd engel_git_nexus_main",
        "  pnpm install",
        "  pnpm build",
        "",
        "Claude plugin install:",
        "  cp -r gitnexus-claude-plugin ~/.claude/plugins/gitnexus",
        "",
        "Cursor integration:",
        "  cp gitnexus-cursor-integration/.cursorrules <your-project>/",
        "",
        "Verify install:",
        "  pnpm gitnexus --version",
    ])


def render_git_nexus_analyze() -> str:
    root = _tool_path("engel_git_nexus_main")
    lines = ["Engel Git Nexus — Git Analysis Mode", "=" * 40, ""]
    lines.append("GitNexus can analyze any local git repository.")
    lines.append("")
    lines.append("Commands (run from your project root):")
    lines.append("  gitnexus commit            — AI-suggested commit message")
    lines.append("  gitnexus branch            — branch strategy advisor")
    lines.append("  gitnexus diff [--staged]   — AI diff summary")
    lines.append("  gitnexus history           — knowledge graph from git log")
    lines.append("  gitnexus pr                — PR description generator")
    lines.append("")
    lines.append(f"Engel folder: {root}")
    skills_dir = root / "gitnexus" / "skills"
    if skills_dir.exists():
        skills = [p.name for p in sorted(skills_dir.iterdir())][:8]
        lines.append(f"Skills found: {', '.join(skills)}")
    return "\n".join(lines)


# CLI-Anything
def render_cli_anything_plugins() -> str:
    root = _tool_path("engel_cli_anything_main")
    lines = ["Engel CLI-Anything — Plugin List", "=" * 40, ""]
    if root.exists():
        dirs = sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
        lines.append(f"Total plugin folders: {len(dirs)}")
        lines.append("")
        for d in dirs[:40]:
            lines.append(f"  {d}/")
        if len(dirs) > 40:
            lines.append(f"  … and {len(dirs) - 40} more")
    else:
        lines.append("Folder not found.")
    return "\n".join(lines)


def render_cli_anything_search() -> str:
    return "\n".join([
        "Engel CLI-Anything — Plugin Search",
        "=" * 40,
        "",
        "To find a plugin by tool name:",
        "  python engel_ai.py ask \"cli anything search <tool-name>\"",
        "",
        "Examples:",
        "  cli anything search blender",
        "  cli anything search chromadb",
        "  cli anything search comfyui",
        "",
        "Plugin folders follow the pattern:  <toolname>/  or  <toolname>-plugin/",
        "",
        "Direct folder browse:",
        "  ls engel_cli_anything_main/",
        "",
        "CLI-Hub meta-skill (natural language routing):",
        "  engel_cli_anything_main/cli-hub-meta-skill/",
    ])


def render_cli_anything_install() -> str:
    root = _tool_path("engel_cli_anything_main")
    hub = root / "cli-hub"
    return "\n".join([
        "Engel CLI-Anything — Install",
        "=" * 40,
        f"Folder: {root}",
        f"CLI-Hub present: {'YES' if hub.exists() else 'NO'}",
        "",
        "Install CLI-Hub (Python meta-skill):",
        "  cd engel_cli_anything_main/cli-hub",
        "  pip install -e .",
        "",
        "Verify:",
        "  python -c \"from cli_hub import cli_hub; print('ok')\"",
        "",
        "Individual plugin install:",
        "  cd engel_cli_anything_main/<plugin-name>",
        "  pip install -r requirements.txt   # if Python",
        "  npm install                        # if Node",
    ])


# open-agents
def render_open_agents_packages() -> str:
    root = _tool_path("engel_open_agents_main")
    lines = ["Engel open-agents — Monorepo Packages", "=" * 40, ""]
    packages_dir = root / "packages"
    apps_dir = root / "apps"
    if packages_dir.exists():
        pkgs = sorted(p.name for p in packages_dir.iterdir() if p.is_dir())
        lines.append(f"packages/ ({len(pkgs)} packages):")
        for p in pkgs:
            lines.append(f"  packages/{p}/")
    lines.append("")
    if apps_dir.exists():
        apps = sorted(p.name for p in apps_dir.iterdir() if p.is_dir())
        lines.append(f"apps/ ({len(apps)} apps):")
        for a in apps:
            lines.append(f"  apps/{a}/")
    return "\n".join(lines)


def render_open_agents_skills() -> str:
    root = _tool_path("engel_open_agents_main")
    lines = ["Engel open-agents — Skills Inventory", "=" * 40, ""]
    skills_lock = root / "skills-lock.json"
    if skills_lock.exists():
        try:
            import json
            data = json.loads(skills_lock.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for k, v in list(data.items())[:20]:
                    lines.append(f"  {k}: {v if isinstance(v, str) else '...'}")
            elif isinstance(data, list):
                for item in data[:20]:
                    lines.append(f"  {item}")
        except Exception as exc:
            lines.append(f"(could not parse skills-lock.json: {exc})")
    else:
        lines.append("skills-lock.json not found.")
        lines.append("")
        lines.append("Skills are defined in packages/ sub-packages.")
    return "\n".join(lines)


def render_open_agents_install() -> str:
    root = _tool_path("engel_open_agents_main")
    return "\n".join([
        "Engel open-agents — Install",
        "=" * 40,
        f"Folder: {root}",
        "",
        "Prerequisites: Bun (recommended) or Node.js 20+",
        "",
        "Install:",
        "  cd engel_open_agents_main",
        "  bun install",
        "",
        "Or with npm/pnpm:",
        "  npm install",
        "  pnpm install",
        "",
        "Build all packages:",
        "  bun run build",
        "",
        "Run an app:",
        "  cd apps/<app-name>",
        "  bun dev",
    ])


# Jarvis
def render_jarvis_install() -> str:
    root = _tool_path("engel_jarvis_main")
    return "\n".join([
        "Engel Jarvis — Install (OpenJarvis)",
        "=" * 40,
        f"Folder: {root}",
        "",
        "Prerequisites: Python 3.10+, pip",
        "",
        "Install:",
        "  cd engel_jarvis_main",
        "  pip install -e .",
        "",
        "Or from pypi (if published):",
        "  pip install openjarvis",
        "",
        "Rust components (optional, for performance):",
        "  cd rust/",
        "  cargo build --release",
        "",
        "Desktop UI (requires Node.js + Tauri):",
        "  cd frontend/",
        "  npm install",
        "  npm run tauri build",
    ])


def render_jarvis_start() -> str:
    root = _tool_path("engel_jarvis_main")
    return "\n".join([
        "Engel Jarvis — Start",
        "=" * 40,
        f"Folder: {root}",
        "",
        "CLI mode:",
        "  cd engel_jarvis_main",
        "  python -m openjarvis",
        "",
        "Or via Engel AI:",
        "  python engel_ai.py ask \"start jarvis\"",
        "",
        "Desktop UI (Tauri):",
        "  cd frontend/",
        "  npm run tauri dev",
        "",
        "Server/daemon mode:",
        "  python -m openjarvis --daemon",
        "  python -m openjarvis --port 8080",
    ])


def render_jarvis_skills() -> str:
    root = _tool_path("engel_jarvis_main")
    lines = ["Engel Jarvis — Skills", "=" * 40, ""]
    src = root / "src" / "openjarvis"
    if src.exists():
        subfolders = sorted(p.name for p in src.iterdir() if p.is_dir() and not p.name.startswith("_"))
        lines.append(f"openjarvis sub-modules ({len(subfolders)}):")
        for sf in subfolders:
            lines.append(f"  {sf}/")
    else:
        lines.append("src/openjarvis/ not found.")
    lines.append("")
    skills_dir = root / "src" / "openjarvis" / "intelligence"
    if skills_dir.exists():
        items = sorted(p.name for p in skills_dir.iterdir() if not p.name.startswith("_"))
        lines.append(f"Intelligence skills: {', '.join(items[:10])}")
    return "\n".join(lines)


# agent-chat-ui
def render_chat_ui_install() -> str:
    root = _tool_path("engel_chat_ui_main")
    return "\n".join([
        "Engel Agent Chat UI — Install",
        "=" * 40,
        f"Folder: {root}",
        "",
        "Prerequisites: Node.js 18+, pnpm",
        "",
        "Install:",
        "  cd engel_chat_ui_main",
        "  pnpm install",
        "",
        "Or with npm:",
        "  npm install",
        "",
        "Build for production:",
        "  pnpm build",
        "",
        "Note: Requires .env with NEXT_PUBLIC_API_URL pointing to your agent backend.",
    ])


def render_chat_ui_start() -> str:
    root = _tool_path("engel_chat_ui_main")
    env = root / ".env.example"
    env_content = ""
    if env.exists():
        try:
            env_content = env.read_text(encoding="utf-8")[:500]
        except Exception:
            pass
    lines = [
        "Engel Agent Chat UI — Start Dev Server",
        "=" * 40,
        f"Folder: {root}",
        "",
        "1. Copy env file:",
        "   cp .env.example .env",
        "   # Edit .env — set NEXT_PUBLIC_API_URL to your agent endpoint",
        "",
        "2. Install:",
        "   pnpm install",
        "",
        "3. Start:",
        "   pnpm dev",
        "   # Opens at http://localhost:3000",
        "",
        "Production:",
        "   pnpm build && pnpm start",
    ]
    if env_content:
        lines += ["", ".env.example:", env_content]
    return "\n".join(lines)


def render_chat_ui_config() -> str:
    root = _tool_path("engel_chat_ui_main")
    lines = ["Engel Agent Chat UI — Config", "=" * 40, ""]
    for fname in (".env.example", "next.config.mjs", "tailwind.config.js"):
        path = root / fname
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8")[:300]
                lines.append(f"── {fname} ──")
                lines.append(content)
                lines.append("")
            except Exception:
                lines.append(f"{fname}: (could not read)")
        else:
            lines.append(f"{fname}: not found")
    return "\n".join(lines)


# ai-dev-gallery
def render_ai_gallery_demos() -> str:
    root = _tool_path("engel_ai_gallery_main")
    lines = ["Engel AI Dev Gallery — Demos", "=" * 40, ""]
    samples = root / "AIDevGallery" / "Samples"
    if samples.exists():
        cats = sorted(p.name for p in samples.iterdir() if p.is_dir() and not p.name.startswith("."))
        lines.append(f"Demo categories ({len(cats)}):")
        for cat in cats:
            lines.append(f"  {cat}/")
        scenarios = samples / "scenarios.json"
        if scenarios.exists():
            try:
                import json
                data = json.loads(scenarios.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    lines.append(f"\nTotal scenarios: {len(data)}")
                    for s in data[:8]:
                        name = s.get("name", s.get("id", "?")) if isinstance(s, dict) else str(s)
                        lines.append(f"  • {name}")
                    if len(data) > 8:
                        lines.append(f"  … and {len(data) - 8} more")
            except Exception:
                pass
    else:
        lines.append("Samples/ not found — is the gallery folder correct?")
    return "\n".join(lines)


def render_ai_gallery_install() -> str:
    root = _tool_path("engel_ai_gallery_main")
    return "\n".join([
        "Engel AI Dev Gallery — Build",
        "=" * 40,
        f"Folder: {root}",
        "",
        "Prerequisites: Visual Studio 2022, .NET 9, Windows 11",
        "               Windows AI SDK / WinML (auto-restored via NuGet)",
        "",
        "Open in Visual Studio:",
        "  AIDevGallery.sln",
        "",
        "Build from CLI:",
        "  dotnet build AIDevGallery.sln --configuration Release",
        "",
        "Run:",
        "  dotnet run --project AIDevGallery/AIDevGallery.csproj",
        "",
        "NuGet restore (if needed):",
        "  dotnet restore AIDevGallery.sln",
    ])


def render_ai_gallery_requirements() -> str:
    return "\n".join([
        "Engel AI Dev Gallery — System Requirements",
        "=" * 40,
        "",
        "OS:         Windows 11 (build 22621+)",
        "Runtime:    .NET 9 SDK",
        "IDE:        Visual Studio 2022 17.9+",
        "AI Engine:  Windows AI SDK / WinML / DirectML",
        "GPU:        DirectML-compatible GPU recommended (CPU fallback available)",
        "",
        "NuGet packages (auto-restored):",
        "  Microsoft.AI.DirectML",
        "  Microsoft.ML.OnnxRuntime.DirectML",
        "  Microsoft.Windows.SDK.BuildTools",
        "",
        "Local models:",
        "  Gallery downloads ONNX models on first use per scenario.",
        "  Model cache: %LOCALAPPDATA%\\AIDevGallery\\models\\",
    ])


# cluster
def render_cluster_nodes() -> str:
    root = _tool_path("engel_cluster_main")
    lines = ["Engel Cluster — Node Configuration", "=" * 40, ""]
    examples_dir = root / "examples"
    if examples_dir.exists():
        examples = sorted(p.name for p in examples_dir.iterdir())
        lines.append(f"Example apps ({len(examples)}):")
        for ex in examples:
            lines.append(f"  {ex}")
    lines.append("")
    lib_dir = root / "lib"
    if lib_dir.exists():
        lib_items = sorted(p.name for p in lib_dir.iterdir())
        lines.append(f"Core lib modules: {', '.join(lib_items)}")
    lines.append("")
    lines.append("Node types supported:")
    lines.append("  Worker  — processes submitted jobs")
    lines.append("  Master  — dispatches jobs and collects results")
    lines.append("  Monitor — health-check and logging node")
    return "\n".join(lines)


def render_cluster_install() -> str:
    root = _tool_path("engel_cluster_main")
    return "\n".join([
        "Engel Cluster — Install",
        "=" * 40,
        f"Folder: {root}",
        "",
        "Prerequisites: Node.js 14+",
        "",
        "Install:",
        "  cd engel_cluster_main",
        "  npm install",
        "",
        "Global install:",
        "  npm install -g .",
        "",
        "Verify:",
        "  node index.js --help",
        "",
        "Run an example cluster:",
        "  node examples/basic.js",
    ])


def render_cluster_examples() -> str:
    root = _tool_path("engel_cluster_main")
    lines = ["Engel Cluster — Examples", "=" * 40, ""]
    examples_dir = root / "examples"
    if examples_dir.exists():
        for ex in sorted(examples_dir.iterdir()):
            lines.append(f"  {ex.name}")
            try:
                first = ex.read_text(encoding="utf-8", errors="replace").splitlines()
                for ln in first[:3]:
                    stripped = ln.strip()
                    if stripped and not stripped.startswith("//"):
                        lines.append(f"    {stripped[:80]}")
                        break
            except Exception:
                pass
        lines.append("")
        lines.append("Run any example:")
        lines.append("  cd engel_cluster_main && node examples/<name>.js")
    else:
        lines.append("examples/ not found.")
    return "\n".join(lines)
