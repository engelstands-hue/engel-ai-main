from __future__ import annotations

import shutil
from pathlib import Path

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
OH = ROOT / "external" / "openhuman-main"

_LIBS = {
    "agents":   OH / ".claude" / "agents",
    "commands": OH / ".claude" / "commands",
    "docs":     OH / "docs",
    "gitbooks": OH / "gitbooks",
}


def _present() -> bool:
    return OH.exists() and (OH / "Cargo.toml").exists()


def _have_pnpm() -> bool:
    return shutil.which("pnpm") is not None


def _have_cargo() -> bool:
    return shutil.which("cargo") is not None


def _list(category: str) -> list[str]:
    d = _LIBS.get(category)
    if not d or not d.exists():
        return []
    out = []
    for p in sorted(d.glob("**/*.md")):
        out.append(p.relative_to(d).with_suffix("").as_posix())
    return out


def _find(name: str) -> Path | None:
    name = name.strip().lower().replace("\\", "/")
    if name.endswith(".md"):
        name = name[:-3]
    for d in _LIBS.values():
        if not d.exists():
            continue
        for p in d.glob("**/*.md"):
            rel = p.relative_to(d).with_suffix("").as_posix().lower()
            if rel == name or p.stem.lower() == name:
                return p
    for p in OH.glob("*.md"):
        if p.stem.lower() == name:
            return p
    return None


def ehuman_status() -> str:
    lines = ["# Ehuman Bridge Status", ""]
    if not _present():
        lines.append(f"Source NOT FOUND at {OH}")
        return "\n".join(lines)

    lines.append(f"Source: {OH}")
    lines.append("")
    for cat in ("agents", "commands", "docs"):
        lines.append(f"  {cat}: {len(_list(cat))}")
    lines.append("")
    lines.append(f"pnpm:  {'installed' if _have_pnpm() else 'not installed (needed to build the app)'}")
    lines.append(f"cargo: {'installed' if _have_cargo() else 'not installed (needed to build the app)'}")
    lines += [
        "",
        "Ehuman is a Tauri desktop app — building it requires pnpm + cargo.",
        "This bridge mainly exposes its agent/prompt library as readable content.",
        "",
        "Commands:",
        "  ehuman status              — this page",
        "  ehuman list                — list everything",
        "  ehuman agents              — list Claude agent personas",
        "  ehuman commands            — list /commands",
        "  ehuman docs                — list internal docs",
        "  ehuman show <name>         — print full file content",
        "  ehuman prompt <name>       — wrap content as a system prompt",
        "  ehuman search <term>       — search markdown across the project",
    ]
    return "\n".join(lines)


def ehuman_list_category(category: str) -> str:
    items = _list(category)
    if not items:
        return f"No {category} found."
    return f"# {category.title()} ({len(items)})\n" + "\n".join(f"  - {i}" for i in items)


def ehuman_list_all() -> str:
    out = []
    for cat in ("agents", "commands", "docs"):
        items = _list(cat)
        out.append(f"## {cat} ({len(items)})")
        for i in items:
            out.append(f"  - {i}")
        out.append("")
    return "\n".join(out)


def ehuman_show(name: str) -> str:
    if not name.strip():
        return "Usage: ehuman show <name>"
    p = _find(name)
    if not p:
        return f"Not found: '{name}'. Try 'ehuman list'."
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"Failed to read {p.name}: {exc}"
    return f"# {p.relative_to(OH).as_posix()}\n\n{text}"


def ehuman_prompt(name: str) -> str:
    if not name.strip():
        return "Usage: ehuman prompt <name>"
    p = _find(name)
    if not p:
        return f"Not found: '{name}'. Try 'ehuman list'."
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"Failed to read {p.name}: {exc}"
    return (
        f"You are operating with the following persona/skill from Ehuman, "
        f"loaded from {p.relative_to(OH).as_posix()}.\n\n"
        f"---\n{text}\n---\n\n"
        f"Follow this guidance for the next response."
    )


def ehuman_search(term: str) -> str:
    term = term.strip().lower()
    if not term:
        return "Usage: ehuman search <term>"
    if not _present():
        return "Ehuman source not found."
    hits: list[tuple[str, int]] = []
    for d in _LIBS.values():
        if not d.exists():
            continue
        for p in d.glob("**/*.md"):
            try:
                t = p.read_text(encoding="utf-8", errors="replace").lower()
            except Exception:
                continue
            c = t.count(term)
            if c > 0:
                hits.append((p.relative_to(OH).as_posix(), c))
    if not hits:
        return f"No matches for '{term}'."
    hits.sort(key=lambda x: -x[1])
    out = [f"Matches for '{term}' ({len(hits)} files):"]
    for path, count in hits[:15]:
        out.append(f"  [{count:3d}]  {path}")
    return "\n".join(out)


def handle_ehuman_command(args: str) -> str:
    text = (args or "").strip()
    if not text or text == "status":
        return ehuman_status()
    if text == "list":
        return ehuman_list_all()
    if text in ("agents", "commands", "docs"):
        return ehuman_list_category(text)
    if text.startswith("show"):
        return ehuman_show(text[4:].strip())
    if text.startswith("prompt"):
        return ehuman_prompt(text[6:].strip())
    if text.startswith("search"):
        return ehuman_search(text[6:].strip())
    return f"Unknown ehuman subcommand: '{text}'. Try 'ehuman status'."
