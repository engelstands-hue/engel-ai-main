"""Engel AI — Wave 3 vendored modules runner.

Five new upstream projects integrated on 2026-05-25:

  engel_gstack_main/        ← gstack     (multi-agent CLI orchestration + gbrain)
  engel_lfm2_main/          ← LFM2       (Liquid Foundation Model Python SDK)
  engel_lfm2_code_review_main/ ← LFM2-CodeReview  (LFM2-24B code review agent)
  engel_lfm2_mobile_main/   ← LFM2.5-mobile (LFM2.5 mobile inference + training)
  engel_lfm2_vision_main/   ← LFM2-Vision (private vision model server)

Public surface:
    render_wave3_list()           — enumerate all five
    render_<tool>_status()        — per-tool folder status
    render_<tool>_features()      — capabilities
    render_<tool>_docs()          — README excerpt
    render_<tool>_install()       — install instructions
    render_<tool>_start()         — how to run (where applicable)
"""
from __future__ import annotations

import os
from pathlib import Path

ENGEL_APP_ROOT: Path = Path(__file__).resolve().parent

_TOOLS = (
    ("gstack",          "engel_gstack_main",           "gstack",           "Multi-agent CLI orchestration + gbrain context graph"),
    ("lfm2",            "engel_lfm2_main",             "LFM2",             "Liquid Foundation Model 2 — Python SDK and inference library"),
    ("lfm2_code_review","engel_lfm2_code_review_main", "LFM2-CodeReview",  "LFM2-24B code review agent (TypeScript monorepo)"),
    ("lfm2_mobile",     "engel_lfm2_mobile_main",      "LFM2.5-Mobile",    "LFM2.5-1.2B mobile inference, training, and log viewer"),
    ("lfm2_vision",     "engel_lfm2_vision_main",      "LFM2-Vision",      "Private vision model server (Python backend + HTML frontend)"),
)

_DISPLAY_NAMES = {
    "gstack":           "GStack Agent Framework",
    "lfm2":             "LFM2 SDK",
    "lfm2_code_review": "LFM2 Code Review Agent",
    "lfm2_mobile":      "LFM2.5 Mobile",
    "lfm2_vision":      "LFM2 Vision Server",
}

_FEATURES = {
    "gstack": [
        "Multi-agent CLI orchestration with conductor.json config",
        "gbrain — persistent context graph for agent memory",
        "100+ skill scripts (design, code, browse, review, sync, …)",
        "Claude, Codex, and custom LLM backends",
        "Browser skills for automated web interaction",
        "Canary / careful / unfreeze safety patterns",
    ],
    "lfm2": [
        "Liquid Foundation Model 2 Python SDK",
        "Simple inference: model.generate(prompt)",
        "Compatible with HuggingFace hub weights",
        "Minimal dependencies — CPU and GPU supported",
    ],
    "lfm2_code_review": [
        "LFM2-24B powered code review agent",
        "TypeScript / Bun monorepo with apps/",
        "Automated PR review, commit message suggestions",
        "Visualised review output with screenshots",
    ],
    "lfm2_mobile": [
        "LFM2.5-1.2B Instruct mobile actions model",
        "inference.py — run on-device inference",
        "train.py — fine-tune with LoRA on mobile datasets",
        "view_logs.py — training log visualiser",
    ],
    "lfm2_vision": [
        "Private LFM2 vision-language model server",
        "Python backend (uv / FastAPI) + HTML frontend",
        "Image + text multimodal input",
        "start.sh / start_server.py one-command launch",
    ],
}

_KEY_DOCS = {
    "gstack":           ["README.md", "ARCHITECTURE.md", "CLAUDE.md", "SKILL.md", "ETHOS.md"],
    "lfm2":             ["README.md", "example.py", "requirements.txt"],
    "lfm2_code_review": ["README.md", "AGENTS.md", "package.json"],
    "lfm2_mobile":      ["README.md", "inference.py", "train.py"],
    "lfm2_vision":      ["README.md", "CLAUDE.md", "backend/main.py", "start.sh"],
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


def render_wave3_list() -> str:
    lines = ["Engel AI — Wave 3 Integrated Tools", "=" * 40, ""]
    for slug, folder, upstream, tag in _TOOLS:
        present = "OK" if _exists(folder) else "MISSING"
        lines.append(f"  [{present}]  engel.{slug}.*  ←  {upstream}")
        lines.append(f"          {tag}")
        lines.append(f"          folder: {folder}/")
        lines.append("")
    lines.append(f"Total: {len(_TOOLS)} Wave 3 modules")
    return "\n".join(lines)


def _status(slug: str, folder: str, upstream: str, tag: str) -> str:
    root = _path(folder)
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
        items = sorted(p.name for p in root.iterdir() if not p.name.startswith("."))[:14]
        lines.append("Top-level contents:")
        for item in items:
            lines.append(f"  {item}")
    return "\n".join(lines)


def _features(slug: str, upstream: str) -> str:
    lines = [f"Engel {_DISPLAY_NAMES[slug]} — Features", "=" * 40, f"Upstream: {upstream}", "", "Capabilities:"]
    for feat in _FEATURES.get(slug, ["(no feature list yet)"]):
        lines.append(f"  • {feat}")
    return "\n".join(lines)


def _docs(slug: str, folder: str, upstream: str) -> str:
    lines = [f"Engel {_DISPLAY_NAMES[slug]} — Docs", "=" * 40, f"Upstream: {upstream}", "", "Key doc files:"]
    root = _path(folder)
    for doc in _KEY_DOCS.get(slug, ["README.md"]):
        full = root / doc
        lines.append(f"  {doc}  [{'exists' if full.exists() else 'not found'}]")
    lines += ["", "README excerpt:", "", _readme(folder)]
    return "\n".join(lines)


# ─── GStack ──────────────────────────────────────────────────────────────────

def render_gstack_status() -> str:
    return _status("gstack", "engel_gstack_main", "gstack", _TOOLS[0][3])

def render_gstack_features() -> str:
    return _features("gstack", "gstack")

def render_gstack_docs() -> str:
    return _docs("gstack", "engel_gstack_main", "gstack")

def render_gstack_install() -> str:
    root = _path("engel_gstack_main")
    return "\n".join([
        "Engel GStack — Install",
        "=" * 40,
        f"Folder: {root}",
        "",
        "Prerequisites: Bun (or Node 20+), Python 3.11+",
        "",
        "Install:",
        "  cd engel_gstack_main",
        "  bun install",
        "",
        "Setup (first run):",
        "  bun run setup",
        "",
        "Configure conductor.json (agent skills / LLM backend):",
        "  cp conductor.json.example conductor.json",
        "  # Edit: set model, provider, skill list",
        "",
        "Claude plugin (optional):",
        "  cp .claude/ to your project root",
    ])

def render_gstack_skills() -> str:
    root = _path("engel_gstack_main")
    lines = ["Engel GStack — Skills", "=" * 40, ""]
    skill_dirs = [
        "agents", "autoplan", "benchmark", "browse", "browser-skills",
        "canary", "careful", "claude", "codex", "design", "design-html",
        "design-review", "sync-gbrain",
    ]
    for sd in skill_dirs:
        p = root / sd
        lines.append(f"  {'[OK]' if p.exists() else '[--]'}  {sd}/")
    lines.append("")
    gbrain = root / "gbrain"
    if not gbrain.exists():
        # gbrain might be a command, not a folder
        lines.append("gbrain: context graph tool (run 'gbrain' after install)")
    else:
        lines.append(f"gbrain: {gbrain}")
    return "\n".join(lines)


# ─── LFM2 SDK ────────────────────────────────────────────────────────────────

def render_lfm2_status() -> str:
    return _status("lfm2", "engel_lfm2_main", "LFM2", _TOOLS[1][3])

def render_lfm2_features() -> str:
    return _features("lfm2", "LFM2")

def render_lfm2_docs() -> str:
    return _docs("lfm2", "engel_lfm2_main", "LFM2")

def render_lfm2_install() -> str:
    root = _path("engel_lfm2_main")
    return "\n".join([
        "Engel LFM2 SDK — Install",
        "=" * 40,
        f"Folder: {root}",
        "",
        "Install (editable):",
        "  cd engel_lfm2_main",
        "  pip install -e .",
        "",
        "Or from requirements:",
        "  pip install -r requirements.txt",
        "",
        "Quick test:",
        "  python example.py",
        "",
        "HuggingFace weights (if needed):",
        "  huggingface-cli download liquid-ai/LFM2-1.2B",
    ])

def render_lfm2_example() -> str:
    root = _path("engel_lfm2_main")
    ex = root / "example.py"
    lines = ["Engel LFM2 SDK — Example", "=" * 40, ""]
    if ex.exists():
        try:
            content = ex.read_text(encoding="utf-8")
            lines.append(content[:600])
        except Exception:
            lines.append("(could not read example.py)")
    else:
        lines.append("example.py not found in engel_lfm2_main/")
    return "\n".join(lines)


# ─── LFM2 Code Review Agent ──────────────────────────────────────────────────

def render_lfm2_code_review_status() -> str:
    return _status("lfm2_code_review", "engel_lfm2_code_review_main", "LFM2-CodeReview", _TOOLS[2][3])

def render_lfm2_code_review_features() -> str:
    return _features("lfm2_code_review", "LFM2-CodeReview")

def render_lfm2_code_review_docs() -> str:
    return _docs("lfm2_code_review", "engel_lfm2_code_review_main", "LFM2-CodeReview")

def render_lfm2_code_review_install() -> str:
    root = _path("engel_lfm2_code_review_main")
    return "\n".join([
        "Engel LFM2 Code Review Agent — Install",
        "=" * 40,
        f"Folder: {root}",
        "",
        "Prerequisites: Bun",
        "",
        "Install:",
        "  cd engel_lfm2_code_review_main",
        "  bun install",
        "",
        "Build:",
        "  bun run build",
        "",
        "Run review on a file:",
        "  bun run review <file>",
        "  bun run review --pr <pr-number>",
    ])

def render_lfm2_code_review_apps() -> str:
    root = _path("engel_lfm2_code_review_main")
    lines = ["Engel LFM2 Code Review — Apps", "=" * 40, ""]
    apps = root / "apps"
    if apps.exists():
        app_list = sorted(p.name for p in apps.iterdir() if p.is_dir())
        lines.append(f"apps/ ({len(app_list)}):")
        for a in app_list:
            lines.append(f"  apps/{a}/")
    else:
        lines.append("apps/ not found.")
    return "\n".join(lines)


# ─── LFM2.5 Mobile ───────────────────────────────────────────────────────────

def render_lfm2_mobile_status() -> str:
    return _status("lfm2_mobile", "engel_lfm2_mobile_main", "LFM2.5-Mobile", _TOOLS[3][3])

def render_lfm2_mobile_features() -> str:
    return _features("lfm2_mobile", "LFM2.5-Mobile")

def render_lfm2_mobile_docs() -> str:
    return _docs("lfm2_mobile", "engel_lfm2_mobile_main", "LFM2.5-Mobile")

def render_lfm2_mobile_install() -> str:
    root = _path("engel_lfm2_mobile_main")
    return "\n".join([
        "Engel LFM2.5 Mobile — Install",
        "=" * 40,
        f"Folder: {root}",
        "",
        "Prerequisites: Python 3.10+, PyTorch",
        "",
        "Install dependencies:",
        "  cd engel_lfm2_mobile_main",
        "  pip install torch transformers accelerate peft",
        "",
        "Run inference:",
        "  python inference.py",
        "",
        "Fine-tune (LoRA):",
        "  python train.py",
        "",
        "View training logs:",
        "  python view_logs.py",
    ])

def render_lfm2_mobile_inference() -> str:
    root = _path("engel_lfm2_mobile_main")
    inf = root / "inference.py"
    lines = ["Engel LFM2.5 Mobile — Inference Script", "=" * 40, ""]
    if inf.exists():
        try:
            content = inf.read_text(encoding="utf-8")
            lines.append(content[:800])
        except Exception:
            lines.append("(could not read inference.py)")
    else:
        lines.append("inference.py not found.")
    return "\n".join(lines)


# ─── LFM2 Vision Server ───────────────────────────────────────────────────────

def render_lfm2_vision_status() -> str:
    return _status("lfm2_vision", "engel_lfm2_vision_main", "LFM2-Vision", _TOOLS[4][3])

def render_lfm2_vision_features() -> str:
    return _features("lfm2_vision", "LFM2-Vision")

def render_lfm2_vision_docs() -> str:
    return _docs("lfm2_vision", "engel_lfm2_vision_main", "LFM2-Vision")

def render_lfm2_vision_install() -> str:
    root = _path("engel_lfm2_vision_main")
    return "\n".join([
        "Engel LFM2 Vision Server — Install",
        "=" * 40,
        f"Folder: {root}",
        "",
        "Prerequisites: Python 3.11+, uv",
        "",
        "Install backend:",
        "  cd engel_lfm2_vision_main/backend",
        "  uv sync",
        "",
        "Or with pip:",
        "  pip install -r backend/requirements.txt  # if present",
        "",
        "Start server (one command):",
        "  cd engel_lfm2_vision_main",
        "  ./start.sh",
        "  # or: python start_server.py",
        "",
        "Frontend: open backend/index.html in browser after server starts.",
    ])

def render_lfm2_vision_start() -> str:
    root = _path("engel_lfm2_vision_main")
    lines = ["Engel LFM2 Vision Server — Start", "=" * 40, f"Folder: {root}", ""]
    start_sh = root / "start.sh"
    start_py = root / "start_server.py"
    if start_sh.exists():
        try:
            content = start_sh.read_text(encoding="utf-8")
            lines.append("start.sh:")
            lines.append(content[:400])
        except Exception:
            pass
    elif start_py.exists():
        try:
            content = start_py.read_text(encoding="utf-8")
            lines.append("start_server.py:")
            lines.append(content[:400])
        except Exception:
            pass
    else:
        lines.append("No start script found.")
    lines += ["", "Run from Engel:", "  python engel_ai.py ask \"lfm2 vision start\""]
    return "\n".join(lines)
