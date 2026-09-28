from __future__ import annotations

from pathlib import Path

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
# External folder kept as-is (third-party source name we don't own).
ENGIZER = ROOT / "external" / "humanizer-main"
SKILL = ENGIZER / "SKILL.md"


def _present() -> bool:
    return SKILL.exists()


def _load_skill() -> str:
    try:
        return SKILL.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"(failed to load SKILL.md: {exc})"


def engize_status() -> str:
    lines = ["# Engize Bridge Status", ""]
    if not _present():
        lines.append(f"SKILL.md NOT FOUND at {SKILL}")
        return "\n".join(lines)
    size = SKILL.stat().st_size
    lines += [
        f"Skill: {SKILL}  ({size:,} bytes)",
        "",
        "Removes signs of AI-generated writing from text — strips em-dashes,",
        "robotic phrasing, hedges, and other LLM tells while preserving meaning.",
        "",
        "Commands:",
        "  engize status              — this page",
        "  engize show                — print the full SKILL.md",
        "  engize <text>              — return the skill wrapped around your text,",
        "                                 ready to paste to a brain provider",
    ]
    return "\n".join(lines)


def engize_show() -> str:
    if not _present():
        return "Engize SKILL.md not found."
    return f"# SKILL.md\n\n{_load_skill()}"


def engize_apply(text: str) -> str:
    if not text.strip():
        return "Usage: engize <text>  (or paste a longer block on the next line)"
    if not _present():
        return "Engize SKILL.md not found in external/humanizer-main/"
    skill = _load_skill()
    return (
        "Apply the engize skill below to the user's text.\n\n"
        "--- SKILL ---\n"
        f"{skill}\n"
        "--- END SKILL ---\n\n"
        "--- TEXT TO ENGIZE ---\n"
        f"{text}\n"
        "--- END TEXT ---\n\n"
        "Return only the engized text, no preamble."
    )


def handle_engize_command(args: str) -> str:
    text = (args or "").strip()
    if not text or text == "status":
        return engize_status()
    if text == "show":
        return engize_show()
    return engize_apply(text)
