"""Engel AI — Agent Meeting Room

A structured multi-agent collaboration space combining:
  • Debate mode  — agents take turns contributing perspectives
  • Task handoff — agenda items flow through research→plan→execute→review
  • Shared whiteboard — persistent scratchpad all agents can read/write

Storage:
  memory/ENGEL_MEETING_ROOM.json      — meeting state + agenda
  memory/ENGEL_MEETING_WHITEBOARD.md  — shared agent notes
  memory/meeting_transcripts/          — one file per meeting session

All write operations that mutate state are gated through the standard
Engel approval pattern — no autonomous agent loops are started here.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGEL_APP_ROOT: Path = Path(__file__).resolve().parent
MEMORY_DIR: Path = ENGEL_APP_ROOT / "memory"
MEETING_STATE_FILE: Path = MEMORY_DIR / "ENGEL_MEETING_ROOM.json"
WHITEBOARD_FILE: Path = MEMORY_DIR / "ENGEL_MEETING_WHITEBOARD.md"
TRANSCRIPTS_DIR: Path = MEMORY_DIR / "meeting_transcripts"

_AGENT_ROLES = {
    "researcher":  "Gathers facts, context, and relevant information on the topic",
    "planner":     "Structures the approach and breaks work into ordered steps",
    "executor":    "Carries out tasks and produces concrete outputs",
    "reviewer":    "Evaluates output quality, catches issues, summarises results",
    "facilitator": "Drives the agenda, ensures all voices are heard, closes items",
    "specialist":  "Provides a focused Agency Agent profile for the meeting topic",
}

_DEFAULT_AGENTS = [
    {"name": "HermesAgent",   "role": "executor",    "module": "engel_agent_main"},
    {"name": "JarvisAgent",   "role": "researcher",  "module": "engel_jarvis_main"},
    {"name": "OctogentSwarm", "role": "planner",     "module": "engel_octogent_main"},
    {"name": "OpenAgents",    "role": "reviewer",    "module": "engel_open_agents_main"},
    {"name": "GitNexus",      "role": "facilitator", "module": "engel_git_nexus_main"},
]


def _agency_agents_for_topic(topic: str, limit: int = 6) -> list[dict[str, Any]]:
    try:
        from engel_agency_agents_registry import find_matching_agents
        matches = find_matching_agents(topic, limit=limit)
    except Exception:
        return []
    agents: list[dict[str, Any]] = []
    for match in matches:
        card_path = Path(str(match.get("engel_card_path") or ""))
        try:
            module = str(card_path.relative_to(ENGEL_APP_ROOT))
        except Exception:
            module = str(card_path)
        agents.append({
            "name": str(match.get("agent_label") or match.get("name") or "Agency Specialist Agent"),
            "role": "specialist",
            "module": module,
            "agency_agent_id": str(match.get("id") or ""),
            "division": str(match.get("division") or ""),
        })
    return agents


def _meeting_agents_for_topic(topic: str) -> list[dict[str, Any]]:
    agents = [dict(agent) for agent in _DEFAULT_AGENTS]
    seen = {str(agent.get("name") or "").lower() for agent in agents}
    for agent in _agency_agents_for_topic(topic):
        key = str(agent.get("name") or "").lower()
        if key and key not in seen:
            agents.append(agent)
            seen.add(key)
    return agents


def _load_state() -> dict[str, Any]:
    if MEETING_STATE_FILE.exists():
        try:
            return json.loads(MEETING_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "status": "IDLE",
        "meeting_id": None,
        "opened_at": None,
        "topic": None,
        "agents": _DEFAULT_AGENTS,
        "agenda": [],
        "transcript": [],
        "whiteboard_version": 0,
    }


def _save_state(state: dict[str, Any]) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    MEETING_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── Public render functions ───────────────────────────────────────────────────

def render_meeting_room_status() -> str:
    state = _load_state()
    lines = [
        "Engel Agent Meeting Room — Status",
        "=" * 40,
        f"State:      {state['status']}",
        f"Meeting ID: {state['meeting_id'] or '(none)'}",
        f"Opened at:  {state['opened_at'] or '(not open)'}",
        f"Topic:      {state['topic'] or '(none)'}",
        "",
        f"Agents invited: {len(state['agents'])}",
    ]
    for ag in state["agents"]:
        lines.append(f"  {ag['name']:<18}  role: {ag['role']}")
    lines += [
        "",
        f"Agenda items:   {len(state['agenda'])}",
        f"Transcript entries: {len(state['transcript'])}",
        f"Whiteboard exists:  {'YES' if WHITEBOARD_FILE.exists() else 'NO'}",
        "",
        "Quick commands:",
        "  python engel_ai.py ask \"meeting room agenda\"",
        "  python engel_ai.py ask \"meeting room whiteboard\"",
        "  python engel_ai.py ask \"meeting room transcript\"",
        "  python engel_ai.py ask \"open meeting room\"",
    ]
    return "\n".join(lines)


def render_meeting_room_agenda() -> str:
    state = _load_state()
    lines = [
        "Engel Agent Meeting Room — Agenda",
        "=" * 40,
        f"Meeting: {state['meeting_id'] or '(no active meeting)'}",
        f"Topic:   {state['topic'] or '(none)'}",
        "",
    ]
    agenda = state.get("agenda", [])
    if not agenda:
        lines.append("No agenda items yet.")
        lines.append("")
        lines.append("To open a meeting with agenda items:")
        lines.append("  python engel_ai.py ask \"open meeting room\"")
    else:
        _STATUS_ICONS = {"pending": "○", "in_progress": "►", "done": "✓", "blocked": "✗"}
        for i, item in enumerate(agenda, 1):
            icon = _STATUS_ICONS.get(item.get("status", "pending"), "?")
            owner = item.get("owner", "unassigned")
            lines.append(f"  {i}. {icon} [{item.get('status','pending'):>11}]  {item['title']}")
            lines.append(f"      Owner: {owner}")
            if item.get("notes"):
                lines.append(f"      Notes: {item['notes'][:80]}")
    return "\n".join(lines)


def render_meeting_room_transcript() -> str:
    state = _load_state()
    transcript = state.get("transcript", [])
    lines = [
        "Engel Agent Meeting Room — Transcript",
        "=" * 40,
        f"Meeting: {state['meeting_id'] or '(none)'}",
        f"Entries: {len(transcript)}",
        "",
    ]
    if not transcript:
        lines.append("No transcript entries yet.")
        lines.append("")
        lines.append("Entries are added as agents contribute to the discussion.")
    else:
        for entry in transcript[-20:]:
            ts = entry.get("timestamp", "")[:16]
            agent = entry.get("agent", "?")
            role = entry.get("role", "")
            text = entry.get("text", "")
            lines.append(f"[{ts}] {agent} ({role}):")
            for ln in text.splitlines():
                lines.append(f"  {ln}")
            lines.append("")
        if len(transcript) > 20:
            lines.append(f"… ({len(transcript) - 20} earlier entries not shown)")
    transcripts_dir = TRANSCRIPTS_DIR
    if transcripts_dir.exists():
        saved = sorted(transcripts_dir.glob("*.json"), reverse=True)
        if saved:
            lines += ["", f"Saved transcripts: {len(saved)}"]
            for f in saved[:5]:
                lines.append(f"  {f.name}")
    return "\n".join(lines)


def render_meeting_room_whiteboard() -> str:
    lines = [
        "Engel Agent Meeting Room — Whiteboard",
        "=" * 40,
        f"File: {WHITEBOARD_FILE}",
        "",
    ]
    if WHITEBOARD_FILE.exists():
        try:
            content = WHITEBOARD_FILE.read_text(encoding="utf-8")
            lines.append(content if content.strip() else "(whiteboard is empty)")
        except Exception as exc:
            lines.append(f"(could not read whiteboard: {exc})")
    else:
        lines.append("(whiteboard not yet created)")
        lines.append("")
        lines.append("The whiteboard is a shared Markdown scratchpad.")
        lines.append("Agents write notes here; all agents can read it.")
        lines.append("")
        lines.append("Create/initialise:")
        lines.append("  python engel_ai.py ask \"open meeting room\"")
    return "\n".join(lines)


def render_meeting_room_agents() -> str:
    state = _load_state()
    lines = [
        "Engel Agent Meeting Room — Invited Agents",
        "=" * 40,
        "",
    ]
    for ag in state.get("agents", _DEFAULT_AGENTS):
        folder = ENGEL_APP_ROOT / ag.get("module", "")
        present = "OK" if (ag.get("module") and folder.exists()) else "missing"
        lines.append(f"  {ag['name']}")
        lines.append(f"    Role:    {ag['role']} — {_AGENT_ROLES.get(ag['role'], '')}")
        lines.append(f"    Module:  {ag.get('module', '?')}  [{present}]")
        lines.append("")
    lines.append("Agent roles:")
    for role, desc in _AGENT_ROLES.items():
        lines.append(f"  {role:<12} {desc}")
    return "\n".join(lines)


def render_meeting_room_open(topic: str = "") -> str:
    state = _load_state()
    if state["status"] == "ACTIVE":
        return "\n".join([
            "Engel Agent Meeting Room — Already Open",
            "=" * 40,
            f"A meeting is already active: {state['meeting_id']}",
            f"Topic: {state['topic']}",
            "",
            "Close it first:",
            "  python engel_ai.py ask \"close meeting room\"",
        ])
    meeting_id = f"MEET-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    topic = topic or "General collaboration session"
    meeting_agents = _meeting_agents_for_topic(topic)
    default_agenda = [
        {"title": "Review shared context",    "status": "pending", "owner": "HermesAgent",   "notes": ""},
        {"title": "Define objectives",         "status": "pending", "owner": "OctogentSwarm", "notes": ""},
        {"title": "Research phase",            "status": "pending", "owner": "JarvisAgent",   "notes": ""},
        {"title": "Build / execute",           "status": "pending", "owner": "HermesAgent",   "notes": ""},
        {"title": "Review + validate output",  "status": "pending", "owner": "OpenAgents",    "notes": ""},
        {"title": "Write meeting summary",     "status": "pending", "owner": "GitNexus",      "notes": ""},
    ]
    new_state = {
        "status": "ACTIVE",
        "meeting_id": meeting_id,
        "opened_at": _now_iso(),
        "topic": topic,
        "agents": meeting_agents,
        "agenda": default_agenda,
        "transcript": [
            {
                "timestamp": _now_iso(),
                "agent": "Facilitator",
                "role": "facilitator",
                "text": f"Meeting {meeting_id} opened. Topic: {topic}",
            }
        ],
        "whiteboard_version": 0,
    }
    _save_state(new_state)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    WHITEBOARD_FILE.write_text(
        f"# Engel Agent Meeting Room — Whiteboard\n\n"
        f"**Meeting:** {meeting_id}  \n"
        f"**Topic:** {topic}  \n"
        f"**Opened:** {_now_iso()}\n\n"
        f"---\n\n"
        f"## Shared Notes\n\n"
        f"_(agents add notes here as the meeting progresses)_\n",
        encoding="utf-8",
    )
    return "\n".join([
        "Engel Agent Meeting Room — Opened",
        "=" * 40,
        f"Meeting ID: {meeting_id}",
        f"Topic:      {topic}",
        f"Opened at:  {new_state['opened_at']}",
        "",
        f"Agents invited: {len(new_state['agents'])}",
        f"Agenda items:   {len(default_agenda)}",
        "",
        "Whiteboard initialised at:",
        f"  {WHITEBOARD_FILE}",
        "",
        "Next steps:",
        "  python engel_ai.py ask \"meeting room agenda\"      — view agenda",
        "  python engel_ai.py ask \"meeting room whiteboard\"  — shared notes",
        "  python engel_ai.py ask \"meeting room transcript\"  — discussion log",
        "  python engel_ai.py ask \"close meeting room\"       — end and save",
    ])


def render_meeting_room_close() -> str:
    state = _load_state()
    if state["status"] != "ACTIVE":
        return "\n".join([
            "Engel Agent Meeting Room — No Active Meeting",
            "=" * 40,
            "No meeting is currently active.",
            "",
            "Open one with:",
            "  python engel_ai.py ask \"open meeting room\"",
        ])
    meeting_id = state["meeting_id"]
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    ts_file = TRANSCRIPTS_DIR / f"{meeting_id}.json"
    ts_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    state["status"] = "CLOSED"
    state["transcript"].append({
        "timestamp": _now_iso(),
        "agent": "Facilitator",
        "role": "facilitator",
        "text": f"Meeting {meeting_id} closed. Transcript saved.",
    })
    _save_state({
        **state,
        "status": "IDLE",
        "meeting_id": None,
        "opened_at": None,
        "topic": None,
        "agenda": [],
        "transcript": [],
    })
    done = sum(1 for a in state.get("agenda", []) if a.get("status") == "done")
    total = len(state.get("agenda", []))
    return "\n".join([
        "Engel Agent Meeting Room — Closed",
        "=" * 40,
        f"Meeting {meeting_id} has been closed.",
        f"Agenda: {done}/{total} items completed",
        f"Transcript entries: {len(state['transcript'])}",
        "",
        f"Transcript saved to:",
        f"  {ts_file}",
        "",
        "Whiteboard preserved at:",
        f"  {WHITEBOARD_FILE}",
    ])


def render_meeting_room_add_note(note: str = "") -> str:
    state = _load_state()
    if state["status"] != "ACTIVE":
        return "No active meeting. Open one first: python engel_ai.py ask \"open meeting room\""
    if not note:
        return "Provide a note: python engel_ai.py ask \"meeting add note <text>\""
    ts = _now_iso()
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    existing = WHITEBOARD_FILE.read_text(encoding="utf-8") if WHITEBOARD_FILE.exists() else ""
    WHITEBOARD_FILE.write_text(
        existing + f"\n### Note @ {ts}\n\n{note}\n",
        encoding="utf-8",
    )
    state["whiteboard_version"] = state.get("whiteboard_version", 0) + 1
    state["transcript"].append({
        "timestamp": ts,
        "agent": "Human",
        "role": "facilitator",
        "text": f"[whiteboard note] {note}",
    })
    _save_state(state)
    return "\n".join([
        "Engel Agent Meeting Room — Note Added",
        "=" * 40,
        f"Whiteboard version: {state['whiteboard_version']}",
        f"Note: {note[:120]}",
        "",
        "View whiteboard:",
        "  python engel_ai.py ask \"meeting room whiteboard\"",
    ])
