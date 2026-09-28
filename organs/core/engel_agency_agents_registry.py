"""Agency Agents registry for Engel Agent Meeting Room.

This module imports the external agency-agents Markdown catalog into Engel's
own memory/agent-card paths and exposes deterministic matching helpers for the
Meeting Room. It does not run agents or call providers; it only registers and
selects profiles for existing Engel routing surfaces.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from engel_project_paths import resolve_engel_app_root


ENGEL_APP_ROOT = resolve_engel_app_root(__file__)
DEFAULT_SOURCE_ROOT = Path(
    os.environ.get(
        "ENGEL_AGENCY_AGENTS_ROOT",
        r"D:\b.WorkSpace\agency-agents-main\agency-agents-main",
    )
)
REGISTRY_DIR = ENGEL_APP_ROOT / "memory" / "meeting_room"
REGISTRY_PATH = REGISTRY_DIR / "agency_agents_registry.json"
AGENT_CARD_ROOT = ENGEL_APP_ROOT / "agents" / "agency-agents"
REPORT_PATH = ENGEL_APP_ROOT / "reports" / "codex_bridge" / "ENGEL_AGENCY_AGENTS_MEETING_ROOM_REGISTRY.md"

_EXCLUDED_DIRS = {".git", ".github", "examples", "integrations", "scripts", "__pycache__"}
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "create", "for",
    "from", "get", "have", "i", "in", "into", "is", "it", "make", "meeting",
    "need", "of", "on", "or", "room", "run", "the", "this", "to", "use",
    "with", "work", "agent", "agents", "agency", "all", "these", "add",
}


def _now_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug or "agent"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    match = re.match(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n?", text, re.DOTALL)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, text[match.end():]


def _markdown_title(body: str, fallback: str) -> str:
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line.startswith("# "):
            return line.lstrip("#").strip()
    return fallback


def _first_paragraph(body: str) -> str:
    lines: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            if lines:
                break
            continue
        if line.startswith("#") or line.startswith("```") or line.startswith("---"):
            continue
        if line.startswith(("-", "*", ">")):
            continue
        lines.append(re.sub(r"\s+", " ", line))
    return " ".join(lines).strip()


def _tokens(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for token in re.findall(r"[a-z0-9][a-z0-9.+#-]*", str(text or "").lower()):
        token = token.strip("-")
        if len(token) < 3 or token in _STOPWORDS or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _load_divisions(source_root: Path) -> dict[str, dict[str, Any]]:
    path = source_root / "divisions.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(_read_text(path))
    except Exception:
        return {}
    if isinstance(raw, dict):
        return {str(k): dict(v) for k, v in raw.items() if isinstance(v, dict)}
    return {}


def _division_label(slug: str, divisions: dict[str, dict[str, Any]]) -> str:
    info = divisions.get(slug) or {}
    label = str(info.get("name") or info.get("label") or slug.replace("-", " ").title()).strip()
    return label or slug.replace("-", " ").title()


def _iter_agent_files(source_root: Path) -> list[Path]:
    if not source_root.exists():
        return []
    files: list[Path] = []
    for division_dir in sorted(path for path in source_root.iterdir() if path.is_dir()):
        if division_dir.name in _EXCLUDED_DIRS:
            continue
        for path in sorted(division_dir.glob("*.md")):
            files.append(path)
    return files


def _agent_record(path: Path, source_root: Path, divisions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    text = _read_text(path)
    meta, body = _parse_frontmatter(text)
    division = path.parent.name
    division_label = _division_label(division, divisions)
    name = str(meta.get("name") or _markdown_title(body, path.stem.replace("-", " ").title())).strip()
    if name.lower().endswith(" agent"):
        agent_label = f"Agency {name}"
    else:
        agent_label = f"Agency {name} Agent"
    description = str(meta.get("description") or _first_paragraph(body) or f"{name} specialist.").strip()
    agent_id = f"agency::{division}::{path.stem}"
    skill_label = f"Agency {division_label} Skill"
    copy_path = AGENT_CARD_ROOT / division / path.name
    body_excerpt = re.sub(r"\s+", " ", body).strip()[:3000]
    keyword_text = " ".join([
        agent_id,
        path.stem.replace("-", " "),
        name,
        agent_label,
        description,
        division,
        division_label,
        body_excerpt,
    ])
    return {
        "id": agent_id,
        "slug": path.stem,
        "name": name,
        "agent_label": agent_label,
        "skill_label": skill_label,
        "division": division,
        "division_label": division_label,
        "description": description,
        "color": str(meta.get("color") or (divisions.get(division) or {}).get("color") or ""),
        "vibe": str(meta.get("vibe") or ""),
        "source_path": str(path),
        "source_relpath": str(path.relative_to(source_root)),
        "engel_card_path": str(copy_path),
        "body_excerpt": body_excerpt,
        "keywords": _tokens(keyword_text)[:220],
        "search_text": " ".join(_tokens(keyword_text)[:260]),
        "meeting_room": {
            "station_id": agent_id,
            "agent": agent_label,
            "skill": skill_label,
            "equipment": "Local Engel AI (main PC)",
            "bridge": "Engel Chat Auto Route",
        },
    }


def build_registry(source_root: Path | str | None = None, copy_cards: bool = True) -> dict[str, Any]:
    source = Path(source_root) if source_root else DEFAULT_SOURCE_ROOT
    divisions = _load_divisions(source)
    agent_files = _iter_agent_files(source)
    records = [_agent_record(path, source, divisions) for path in agent_files]
    by_division: dict[str, int] = {}
    for record in records:
        by_division[record["division"]] = by_division.get(record["division"], 0) + 1
    if copy_cards:
        for record in records:
            src = Path(record["source_path"])
            dst = Path(record["engel_card_path"])
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    AGENT_CARD_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "engel_agency_agents_meeting_room_registry_v1",
        "generated_at_utc": _now_utc(),
        "source_root": str(source),
        "engel_card_root": str(AGENT_CARD_ROOT),
        "registry_path": str(REGISTRY_PATH),
        "agent_count": len(records),
        "division_count": len(by_division),
        "by_division": dict(sorted(by_division.items())),
        "agents": records,
    }
    REGISTRY_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_registry_report(payload)
    return payload


def load_registry(auto_build: bool = True) -> dict[str, Any]:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    if auto_build and DEFAULT_SOURCE_ROOT.exists():
        return build_registry(DEFAULT_SOURCE_ROOT)
    return {
        "schema": "engel_agency_agents_meeting_room_registry_v1",
        "generated_at_utc": "",
        "source_root": str(DEFAULT_SOURCE_ROOT),
        "engel_card_root": str(AGENT_CARD_ROOT),
        "agent_count": 0,
        "division_count": 0,
        "by_division": {},
        "agents": [],
    }


def _score_agent(query: str, query_tokens: list[str], agent: dict[str, Any]) -> int:
    low = query.lower()
    name = str(agent.get("name") or "").lower()
    agent_label = str(agent.get("agent_label") or "").lower()
    slug_text = str(agent.get("slug") or "").replace("-", " ").lower()
    division = str(agent.get("division") or "").replace("-", " ").lower()
    division_label = str(agent.get("division_label") or "").lower()
    description = str(agent.get("description") or "").lower()
    agent_tokens = set(str(token).lower() for token in agent.get("keywords", []))
    score = 0
    for phrase, weight in (
        (name, 80),
        (agent_label, 80),
        (slug_text, 60),
        (division_label, 30),
        (division, 24),
    ):
        if phrase and len(phrase) > 2 and phrase in low:
            score += weight
    for token in query_tokens:
        if token in agent_tokens:
            score += 4
        if token and token in name:
            score += 8
        if token and token in slug_text:
            score += 8
        if token and token in description:
            score += 3
        if token and (token in division or token in division_label):
            score += 5
    return score


def find_matching_agents(query: str, limit: int = 4, min_score: int = 8) -> list[dict[str, Any]]:
    registry = load_registry(auto_build=True)
    query_tokens = _tokens(query)
    if not query_tokens and "agency" not in str(query or "").lower():
        return []
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for agent in registry.get("agents", []):
        if not isinstance(agent, dict):
            continue
        score = _score_agent(str(query or ""), query_tokens, agent)
        if score >= min_score:
            scored.append((score, str(agent.get("agent_label") or ""), agent))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [agent for _score, _label, agent in scored[: max(0, int(limit))]]


def find_agent_by_station_labels(agent_label: str, skill_label: str = "") -> dict[str, Any] | None:
    label = str(agent_label or "").strip().lower()
    skill = str(skill_label or "").strip().lower()
    for agent in load_registry(auto_build=True).get("agents", []):
        if not isinstance(agent, dict):
            continue
        if label and label == str(agent.get("agent_label") or "").strip().lower():
            return agent
        if skill and skill == str(agent.get("skill_label") or "").strip().lower() and label in str(agent.get("agent_label") or "").strip().lower():
            return agent
    return None


def station_payload_for_agent(agent: dict[str, Any]) -> dict[str, str]:
    meeting = agent.get("meeting_room") if isinstance(agent.get("meeting_room"), dict) else {}
    return {
        "agent": str(meeting.get("agent") or agent.get("agent_label") or "Agency Specialist Agent"),
        "skill": str(meeting.get("skill") or agent.get("skill_label") or "Agency Specialist Skill"),
        "equipment": str(meeting.get("equipment") or "Local Engel AI (main PC)"),
        "bridge": str(meeting.get("bridge") or "Engel Chat Auto Route"),
    }


def station_context_for_labels(agent_label: str, skill_label: str = "") -> str:
    agent = find_agent_by_station_labels(agent_label, skill_label)
    if not agent:
        return ""
    return "\n".join([
        "Agency Agent Profile",
        f"Profile id: {agent.get('id')}",
        f"Division: {agent.get('division_label')} ({agent.get('division')})",
        f"Source card: {agent.get('engel_card_path')}",
        f"Description: {agent.get('description')}",
        f"Vibe: {agent.get('vibe') or '(none)'}",
        "",
        "Profile excerpt:",
        str(agent.get("body_excerpt") or "")[:1800],
    ]).strip()


def write_registry_report(payload: dict[str, Any]) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Engel Agency Agents Meeting Room Registry",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Source root: `{payload.get('source_root')}`",
        f"- Engel card root: `{payload.get('engel_card_root')}`",
        f"- Registry: `{payload.get('registry_path')}`",
        f"- Agents registered: {payload.get('agent_count')}",
        f"- Divisions registered: {payload.get('division_count')}",
        "",
        "## Division Counts",
    ]
    for division, count in (payload.get("by_division") or {}).items():
        lines.append(f"- `{division}`: {count}")
    lines.extend([
        "",
        "## Meeting Room Wiring",
        "- Engel owns a copied card for every Agency Agent under `agents/agency-agents/`.",
        "- `engel_agent_meeting_room.py` can auto-select matching Agency specialists by order text.",
        "- `engel_agent_meetingroom.py` can invite matching Agency specialists when opening a text meeting.",
        "- `engel3d_office_main/server/engel-gateway-adapter.js` seeds Agency specialists into the 3D office gateway from this registry.",
        "- Profiles are prompt context only; execution still goes through existing Engel bridges and approval gates.",
    ])
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return REPORT_PATH


def render_registry_summary() -> str:
    payload = load_registry(auto_build=True)
    lines = [
        "Engel Agency Agents registry",
        f"Agents: {payload.get('agent_count', 0)}",
        f"Divisions: {payload.get('division_count', 0)}",
        f"Registry: {REGISTRY_PATH}",
        f"Cards: {AGENT_CARD_ROOT}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    built = build_registry()
    print(render_registry_summary())
    print(f"Report: {REPORT_PATH}")
