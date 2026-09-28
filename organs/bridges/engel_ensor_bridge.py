from __future__ import annotations

from pathlib import Path

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
KIT = ROOT / "external" / "AI-ASSISTANT-CURSOR-main"

_CATEGORIES = {
    "agents": KIT / "agents",
    "workflows": KIT / "workflows",
    "skills": KIT / "skills",
    "docs": KIT / "docs",
}


def _kit_present() -> bool:
    return KIT.exists() and (KIT / "README.md").exists()


def _list_items(category: str) -> list[str]:
    d = _CATEGORIES.get(category)
    if not d or not d.exists():
        return []
    out = []
    for p in sorted(d.iterdir()):
        if p.is_file() and p.suffix == ".md":
            out.append(p.stem)
        elif p.is_dir():
            for sub in sorted(p.glob("**/*.md")):
                out.append(f"{p.name}/{sub.relative_to(p).with_suffix('')}".replace("\\", "/"))
    return out


def _find_item(name: str) -> Path | None:
    name = name.strip().lower().replace("\\", "/")
    if name.endswith(".md"):
        name = name[:-3]
    for cat_path in _CATEGORIES.values():
        if not cat_path.exists():
            continue
        for p in cat_path.glob("**/*.md"):
            rel = p.relative_to(cat_path).with_suffix("").as_posix().lower()
            if rel == name or p.stem.lower() == name:
                return p
    for p in KIT.glob("*.md"):
        if p.stem.lower() == name:
            return p
    return None


def ensor_status() -> str:
    lines = ["# Ensor AI Assistant Kit", ""]
    if not _kit_present():
        lines.append(f"Kit NOT FOUND at {KIT}")
        return "\n".join(lines)

    lines.append(f"Kit location: {KIT}")
    lines.append("")
    for cat in ("agents", "workflows", "skills"):
        items = _list_items(cat)
        lines.append(f"  {cat}: {len(items)}")
    lines.append("")
    lines += [
        "Commands:",
        "  ensor status              — this page",
        "  ensor list                — list everything",
        "  ensor agents              — list agent personas",
        "  ensor workflows           — list workflows",
        "  ensor skills              — list skills",
        "  ensor show <name>         — print full content of a file",
        "  ensor prompt <name>       — return content wrapped as a system prompt",
        "  ensor search <term>       — search content across the kit",
    ]
    return "\n".join(lines)


def ensor_list_category(category: str) -> str:
    items = _list_items(category)
    if not items:
        return f"No {category} found."
    return f"# {category.title()} ({len(items)})\n" + "\n".join(f"  - {i}" for i in items)


def ensor_list_all() -> str:
    out = []
    for cat in ("agents", "workflows", "skills"):
        items = _list_items(cat)
        out.append(f"## {cat} ({len(items)})")
        for i in items:
            out.append(f"  - {i}")
        out.append("")
    return "\n".join(out)


def ensor_show(name: str) -> str:
    if not name.strip():
        return "Usage: ensor show <name>"
    p = _find_item(name)
    if not p:
        return f"Not found: '{name}'. Try 'ensor list'."
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"Failed to read {p.name}: {exc}"
    rel = p.relative_to(KIT).as_posix()
    return f"# {rel}\n\n{text}"


def ensor_prompt(name: str) -> str:
    if not name.strip():
        return "Usage: ensor prompt <name>"
    p = _find_item(name)
    if not p:
        return f"Not found: '{name}'. Try 'ensor list'."
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"Failed to read {p.name}: {exc}"
    return (
        f"You are operating with the following persona/skill loaded from "
        f"{p.relative_to(KIT).as_posix()}.\n\n"
        f"---\n{text}\n---\n\n"
        f"Follow this guidance for the next response."
    )


def ensor_search(term: str) -> str:
    term = term.strip().lower()
    if not term:
        return "Usage: ensor search <term>"
    if not _kit_present():
        return "Ensor kit not found."
    hits: list[tuple[str, int]] = []
    for p in KIT.glob("**/*.md"):
        try:
            text = p.read_text(encoding="utf-8", errors="replace").lower()
        except Exception:
            continue
        count = text.count(term)
        if count > 0:
            hits.append((p.relative_to(KIT).as_posix(), count))
    if not hits:
        return f"No matches for '{term}'."
    hits.sort(key=lambda x: -x[1])
    out = [f"Matches for '{term}' ({len(hits)} files):"]
    for path, count in hits[:15]:
        out.append(f"  [{count:3d}]  {path}")
    return "\n".join(out)


def handle_ensor_command(args: str) -> str:
    text = (args or "").strip()
    if not text or text == "status":
        return ensor_status()
    if text == "list":
        return ensor_list_all()
    if text in ("agents", "workflows", "skills"):
        return ensor_list_category(text)
    if text.startswith("show"):
        return ensor_show(text[4:].strip())
    if text.startswith("prompt"):
        return ensor_prompt(text[6:].strip())
    if text.startswith("search"):
        return ensor_search(text[6:].strip())
    return f"Unknown ensor subcommand: '{text}'. Try 'ensor status'."
