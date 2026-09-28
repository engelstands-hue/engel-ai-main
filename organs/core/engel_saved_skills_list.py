#!/usr/bin/env python3
"""Read-only renderer for the Engel saved-skill registry.

Backs the ``engel.skills.saved_list`` route. Reads
``memory/skills/ENGEL_SAVED_SKILL_REGISTRY.json`` (plus the creation-events
log) and reports every saved skill with its integrity state: file present,
sha256 match, mirror in sync.

Safety: pure read-only status. No registry writes, no file mutation, no
network, no provider calls, no background work. Missing files are reported,
never repaired.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
_REGISTRY_PATH = _ROOT / "memory" / "skills" / "ENGEL_SAVED_SKILL_REGISTRY.json"
_EVENTS_PATH = _ROOT / "memory" / "skills" / "ENGEL_SKILL_CREATION_EVENTS.jsonl"


def _load_registry() -> dict:
    try:
        data = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception:
        return {"_error": "registry unreadable"}
    return data if isinstance(data, dict) else {"_error": "registry not a dict"}


def _to_local(win_path: str) -> Path:
    """Map a registry D:\\ path onto this checkout, wherever it is mounted."""
    text = str(win_path or "").replace("\\", "/")
    marker = "b.WorkSpace/Engel App/"
    idx = text.find(marker)
    if idx >= 0:
        return _ROOT / text[idx + len(marker):]
    return Path(text)


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return ""


def _events_count() -> int:
    try:
        with _EVENTS_PATH.open(encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except Exception:
        return 0


def render_saved_skills_list(payload: str = "") -> str:
    del payload  # status route; no payload accepted
    lines = ["# Engel Saved Skills", ""]
    registry = _load_registry()

    if not registry:
        lines += [
            "Saved-skill registry not found.",
            "Expected: memory/skills/ENGEL_SAVED_SKILL_REGISTRY.json",
            "(Normal inside a packaged exe that does not bundle memory/.)",
        ]
        return "\n".join(lines)
    if "_error" in registry:
        return "\n".join(lines + ["Registry problem: " + str(registry["_error"])])

    skills = registry.get("skills")
    skills = skills if isinstance(skills, dict) else {}
    ok_count = 0
    rows: list[str] = []
    for key in sorted(skills):
        entry = skills[key] if isinstance(skills[key], dict) else {}
        skill_file = _to_local(str(entry.get("filePath", "")))
        flags: list[str] = []
        if entry.get("disabled"):
            flags.append("disabled")
        if not skill_file.is_file():
            flags.append("MISSING FILE")
        else:
            digest = _sha256(skill_file)
            if digest and digest != str(entry.get("skill_md_sha256", "")):
                flags.append("SHA MISMATCH")
            for mirror in entry.get("mirrors", []) or []:
                mirror_file = _to_local(str(mirror))
                if not mirror_file.is_file():
                    flags.append("mirror missing")
                elif mirror_file.read_bytes() != skill_file.read_bytes():
                    flags.append("mirror stale")
        state = "OK" if not flags else ", ".join(flags)
        if state == "OK":
            ok_count += 1
        name = str(entry.get("name", key))
        updated = str(entry.get("updated_at_utc", ""))[:10]
        rows.append(f"- {key} -- {name} [{state}] updated {updated}")

    lines.append(f"Registered skills: {len(skills)} ({ok_count} OK)")
    lines.append("Creation/update events logged: " + str(_events_count()))
    lines.append("")
    lines.extend(rows if rows else ["(registry contains no skills)"])
    lines += [
        "",
        "Registry: memory/skills/ENGEL_SAVED_SKILL_REGISTRY.json",
        "Primary root: skills/  |  Managed mirror: .agents/skills/",
        "",
        "Safety: READ_ONLY_STATUS_ONLY - reports integrity, never repairs.",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(render_saved_skills_list())
