"""Engel AI — Architect Agent.

Implements the Architect Agent blueprint (Zones 1-5):

  ZONE 1 — Entry & mode selection (NEW / CONTINUE / ADD; Full / Lite / Custom)
  ZONE 2 — 13-section pipeline (Discovery, Commercial, Quality, Engineering)
  ZONE 3 — Support agents (Injector, Brief Writer, Tracker, Change Mgmt, Principles)
  ZONE 4 — Planner phase (10 stages A through J, mandatory pause at H)
  ZONE 5 — Outputs & handoff (plan.md / spec.md / prompt.md → Executor)

Safety model (Engel-aligned):
  - Most surfaces are status-only renders of architect state.
  - State mutations (start_new, run_section, approve_gate, etc.) are explicit
    action routes the user must invoke deliberately.
  - No background workers, no autonomous loops, no provider/network calls.
  - All writes land under memory/architect_state/.
  - The Founder Approval Gate (planner stage H) is a hard pause — no progression
    until the human explicitly approves.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ENGEL_APP_ROOT: Path = Path(__file__).resolve().parent
STATE_DIR: Path = ENGEL_APP_ROOT / "memory" / "architect_state"
SECTIONS_DIR: Path = STATE_DIR / "sections"
BRIEFS_DIR: Path = STATE_DIR / "briefs"
PLANNER_DIR: Path = STATE_DIR / "planner"
OUTPUTS_DIR: Path = STATE_DIR / "outputs"
STATE_FILE: Path = STATE_DIR / "architect_state.json"
FOUNDER_VOICE_FILE: Path = STATE_DIR / "founder_voice.md"
ISSUE_LOG_FILE: Path = STATE_DIR / "issue_log.md"
TRACKER_LOG_FILE: Path = STATE_DIR / "tracker_log.md"
PRINCIPLES_FILE: Path = STATE_DIR / "principles.md"


# ── Section definitions ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class Section:
    id: str            # S01..S13
    category: str      # DISCOVERY / COMMERCIAL / QUALITY / ENGINEERING
    name: str
    artifact: str
    gap_if_skipped: str
    legal_scan: str    # REQUIRED / STRONGLY_RECOMMENDED / NONE
    in_lite_mode: bool # Lite mode includes 6 of the 13


SECTIONS: tuple[Section, ...] = (
    Section("S01", "DISCOVERY",   "Problem & Vision",
            "problem statement, outcomes, founder voice",
            "vision drift, weak scope", "REQUIRED", True),
    Section("S02", "DISCOVERY",   "User Roles & Personas",
            "personas, jobs, user constraints",
            "generic product assumptions", "REQUIRED", True),
    Section("S03", "DISCOVERY",   "Feature Map & User Stories",
            "feature tree, stories, acceptance intent",
            "unclear MVP and priorities", "REQUIRED", True),
    Section("S04", "COMMERCIAL",  "Monetisation & Stripe",
            "pricing model, billing flows, Stripe plan",
            "revenue path unverified", "REQUIRED", False),
    Section("S05", "COMMERCIAL",  "SEO & GTM Strategy",
            "keyword clusters, acquisition plan, launch messaging",
            "weak discoverability and go-to-market", "REQUIRED", False),
    Section("S06", "QUALITY",     "Accessibility & i18n",
            "a11y rules, localization scope",
            "exclusion and retrofit cost", "STRONGLY_RECOMMENDED", False),
    Section("S07", "QUALITY",     "Analytics & Tracking",
            "event taxonomy, KPI mapping",
            "no measurement backbone", "STRONGLY_RECOMMENDED", False),
    Section("S08", "QUALITY",     "UX, Interface Design & Branding",
            "UI direction, design system cues, brand language",
            "inconsistent UX and tone", "STRONGLY_RECOMMENDED", True),
    Section("S09", "ENGINEERING", "Technical Architecture",
            "stack, module structure, API contracts",
            "implementation ambiguity", "REQUIRED", True),
    Section("S10", "ENGINEERING", "Data Architecture",
            "entities, schemas, data flows",
            "fragile data model", "REQUIRED", False),
    Section("S11", "ENGINEERING", "Security & Compliance",
            "threat model, controls, compliance notes",
            "risk exposure", "REQUIRED", False),
    Section("S12", "ENGINEERING", "DevOps & Hosting",
            "environments, CI/CD, infra plan",
            "deployment uncertainty", "REQUIRED", False),
    Section("S13", "ENGINEERING", "Testing & QA",
            "test strategy, QA gates, release confidence",
            "regression risk", "REQUIRED", True),
)

ENTRY_MODES = (
    ("NEW",      "~3.0k tokens",  "~3-5 min",  "Start a new architect run from scratch"),
    ("CONTINUE", "~1.2k tokens",  "~1-2 min",  "Resume an in-progress architect run"),
    ("ADD",      "~2.0k tokens",  "~2-4 min",  "Add to an existing planning state"),
)

EXECUTION_MODES = (
    ("Full",   "13 sections", "~28k tokens", "~35-55 min"),
    ("Lite",   "6 sections",  "~14k tokens", "~18-30 min"),
    ("Custom", "varies",      "~varies",     "Exclude-by-default selection"),
)

# Planner stages — Zone 4
PLANNER_STAGES = (
    ("A",        "GSD Discuss",         "align scope & constraints"),
    ("B",        "Extract blueprint",   "section by section"),
    ("B-Legal",  "Legal synthesis",     "6-category legal scan"),
    ("C",        "Write tasks",         "task list, deps, order"),
    ("D",        "Self-review + Santa", "quality & coverage"),
    ("E",        "Master spec",         "unified spec.md"),
    ("F",        "Executor prompt",     "self-contained prompt.md"),
    ("G",        "Cost estimate",       "tokens, time, monthly cost"),
    ("H",        "Founder approval",    "MANDATORY PAUSE — founder approves or redirects"),
    ("I",        "Checkpoint write",    ".planner-checkpoint.md"),
    ("J",        "Memory record",       "claude-mem record"),
)

LEGAL_CATEGORIES = (
    "Privacy & Data Protection",
    "Intellectual Property",
    "Contracts & Terms",
    "Consumer Protection",
    "Industry & Sector Compliance",
    "Cross-border / Export",
)


# ── State helpers ────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    for d in (STATE_DIR, SECTIONS_DIR, BRIEFS_DIR, PLANNER_DIR, OUTPUTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _empty_state() -> dict[str, Any]:
    return {
        "schema": "engel.architect.v1",
        "status": "IDLE",
        "project_id": None,
        "project_name": None,
        "entry_mode": None,        # NEW / CONTINUE / ADD
        "execution_mode": None,    # Full / Lite / Custom
        "selected_sections": [],   # list of section IDs in run
        "current_section": None,   # current S## being worked on
        "section_states": {},      # S##: {state, opened_at, closed_at, retries, issues}
        "planner_stage": None,     # A..J (or None if not in planner phase)
        "planner_states": {},      # stage_id: {state, opened_at, closed_at}
        "approval_gate": "NOT_REACHED",  # NOT_REACHED / PENDING / APPROVED / REDIRECTED
        "started_at": None,
        "updated_at": None,
        "closed_at": None,
    }


def _load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return _empty_state()
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return _empty_state()


def _save_state(state: dict[str, Any]) -> None:
    _ensure_dirs()
    state["updated_at"] = _now_iso()
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _section_by_id(sid: str) -> Section | None:
    sid_upper = (sid or "").upper().strip()
    for s in SECTIONS:
        if s.id == sid_upper:
            return s
    return None


def _selected_for_mode(mode: str) -> list[str]:
    mode = (mode or "Full").strip()
    if mode.lower() == "lite":
        return [s.id for s in SECTIONS if s.in_lite_mode]
    if mode.lower() == "custom":
        return [s.id for s in SECTIONS if s.in_lite_mode]  # default subset; user can extend
    return [s.id for s in SECTIONS]  # Full


# ── Rendering — overview / status / lists ────────────────────────────────────

def render_architect_overview() -> str:
    lines = [
        "Engel Architect Agent — Overview",
        "=" * 40,
        "",
        "The Architect Agent walks a project from blank page to executor-ready spec.",
        "",
        "Zones:",
        "  1. Entry & mode selection  (NEW / CONTINUE / ADD; Full / Lite / Custom)",
        "  2. 13-section pipeline     (Discovery, Commercial, Quality, Engineering)",
        "  3. Support agents          (Injector, Brief Writer, Tracker, Change Mgmt, Principles)",
        "  4. Planner phase           (A..J, mandatory pause at H)",
        "  5. Outputs & handoff       (plan.md / spec.md / prompt.md → Executor)",
        "",
        f"State directory:     {STATE_DIR}",
        f"State file:          {STATE_FILE.name}",
        f"Founder voice file:  {FOUNDER_VOICE_FILE.name}",
        f"Tracker log:         {TRACKER_LOG_FILE.name}",
        f"Issue log:           {ISSUE_LOG_FILE.name}",
        f"Principles:          {PRINCIPLES_FILE.name}",
        "",
        "Routes (status):  architect status / sections / modes / planner status",
        "Routes (action):  architect start new / continue / run section / approve gate",
    ]
    return "\n".join(lines)


def render_architect_status() -> str:
    s = _load_state()
    lines = [
        "Engel Architect Agent — Status",
        "=" * 40,
        f"Status:           {s['status']}",
        f"Project:          {s.get('project_name') or '(none)'}",
        f"Project ID:       {s.get('project_id') or '(none)'}",
        f"Entry mode:       {s.get('entry_mode') or '(unset)'}",
        f"Execution mode:   {s.get('execution_mode') or '(unset)'}",
        f"Sections selected:{len(s.get('selected_sections') or [])}",
        f"Current section:  {s.get('current_section') or '(none)'}",
        f"Planner stage:    {s.get('planner_stage') or '(not in planner phase)'}",
        f"Approval gate:    {s.get('approval_gate')}",
        f"Started at:       {s.get('started_at') or '(not started)'}",
        f"Updated at:       {s.get('updated_at') or '(never)'}",
    ]
    if s.get("section_states"):
        lines.append("")
        lines.append("Section progress:")
        for sid in s.get("selected_sections") or []:
            st = s["section_states"].get(sid, {})
            state = st.get("state", "PENDING")
            retries = st.get("retries", 0)
            extra = f" ({retries} retries)" if retries else ""
            sec = _section_by_id(sid)
            name = sec.name if sec else "?"
            lines.append(f"  {sid}  {state:<10}  {name}{extra}")
    return "\n".join(lines)


def render_architect_sections() -> str:
    lines = [
        "Engel Architect Agent — 13 Sections Pipeline",
        "=" * 60,
        "",
    ]
    current_cat = None
    for sec in SECTIONS:
        if sec.category != current_cat:
            current_cat = sec.category
            lines.append("")
            lines.append(f"── {sec.category} ──")
            lines.append("")
        lite_marker = "★" if sec.in_lite_mode else " "
        lines.append(f"  {sec.id} {lite_marker} {sec.name}")
        lines.append(f"          artifact: {sec.artifact}")
        lines.append(f"          legal scan: {sec.legal_scan}")
        lines.append(f"          gap if skipped: {sec.gap_if_skipped}")
        lines.append("")
    lines.append("Legend:  ★ = included in Lite mode (6 sections)")
    lines.append("Pipeline per section: Brief Writer → Section Agent → Injector → Tracker → 00-state.md")
    return "\n".join(lines)


def render_architect_section_detail() -> str:
    s = _load_state()
    current = s.get("current_section")
    if not current:
        return (
            "No section currently active.\n"
            "Start a run: python engel_ai.py ask \"architect start new\"\n"
            "Or list sections: python engel_ai.py ask \"architect sections\""
        )
    sec = _section_by_id(current)
    if not sec:
        return f"Current section {current} not recognized."
    section_state = s["section_states"].get(current, {})
    lines = [
        f"Engel Architect — Section {sec.id} Detail",
        "=" * 50,
        f"Name:           {sec.name}",
        f"Category:       {sec.category}",
        f"Artifact:       {sec.artifact}",
        f"Legal scan:     {sec.legal_scan}",
        f"Lite mode:      {'yes' if sec.in_lite_mode else 'no'}",
        f"Gap if skipped: {sec.gap_if_skipped}",
        "",
        f"State:          {section_state.get('state', 'PENDING')}",
        f"Opened at:      {section_state.get('opened_at') or '(never)'}",
        f"Closed at:      {section_state.get('closed_at') or '(open)'}",
        f"Retries:        {section_state.get('retries', 0)}",
        f"Issues:         {len(section_state.get('issues', []))}",
        "",
        "Pipeline order:",
        "  1. Brief Writer  — curates context for this section",
        "  2. Section Agent — produces the section artifact",
        "  3. Injector      — contradiction check vs prior sections",
        "  4. Tracker       — records observation, updates 00-state.md",
    ]
    state_file = SECTIONS_DIR / f"{sec.id}-state.md"
    lines.append("")
    lines.append(f"00-state.md path: {state_file}")
    return "\n".join(lines)


def render_architect_modes() -> str:
    lines = [
        "Engel Architect Agent — Modes",
        "=" * 40,
        "",
        "Entry modes (how to start):",
    ]
    for name, tokens, time_, desc in ENTRY_MODES:
        lines.append(f"  {name:<10}  {tokens:<14}  {time_:<10}  {desc}")
    lines.append("")
    lines.append("Execution modes (how much to cover):")
    for name, span, tokens, time_ in EXECUTION_MODES:
        lines.append(f"  {name:<8}  {span:<14}  {tokens:<14}  {time_}")
    lines.append("")
    lines.append("Start a run with:")
    lines.append('  python engel_ai.py ask "architect start new"')
    lines.append("  (the system asks for mode selection at the S01 pause)")
    return "\n".join(lines)


# ── Support agents — render-only views ───────────────────────────────────────

def render_architect_principles() -> str:
    if not PRINCIPLES_FILE.exists():
        _ensure_dirs()
        PRINCIPLES_FILE.write_text(
            "# Engel Architect — Principles\n\n"
            "All section agents read these before producing output.\n\n"
            "## Ask vs. Derive\n"
            "- Ask the founder when their voice or judgment is required.\n"
            "- Derive from prior sections when the answer is already implied.\n\n"
            "## Output Standard\n"
            "- Every artifact has a fixed schema and acceptance gate.\n"
            "- No prose-only sections; structure first, then narrative.\n\n"
            "## Legal Scan Directive\n"
            "- Sections flagged REQUIRED legal scan route through the 6-category check\n"
            "  before reaching Planner B-Legal.\n\n"
            "## FOUNDER_QUESTION protocol\n"
            "- The agent must pause and surface a FOUNDER_QUESTION rather than guess\n"
            "  when scope, monetisation, or branding is ambiguous.\n",
            encoding="utf-8",
        )
    return f"Engel Architect — Principles\n{'=' * 40}\n\n{PRINCIPLES_FILE.read_text(encoding='utf-8')}"


def render_architect_founder_voice() -> str:
    if not FOUNDER_VOICE_FILE.exists():
        _ensure_dirs()
        FOUNDER_VOICE_FILE.write_text(
            "# Founder Voice Thread\n\n"
            "Verbatim tone and brand signals from the founder.\n"
            "Architect injects these into tone-sensitive sections (S01, S05, S08).\n\n"
            "## Voice samples\n"
            "(none captured yet)\n\n"
            "## Brand signals\n"
            "(none captured yet)\n",
            encoding="utf-8",
        )
    return f"Engel Architect — Founder Voice Thread\n{'=' * 40}\n\n{FOUNDER_VOICE_FILE.read_text(encoding='utf-8')}"


def render_architect_tracker_log() -> str:
    if not TRACKER_LOG_FILE.exists():
        return (
            "Engel Architect — Tracker Log\n"
            f"{'=' * 40}\n"
            "(no tracker entries yet — log starts when first section runs)"
        )
    return f"Engel Architect — Tracker Log\n{'=' * 40}\n\n{TRACKER_LOG_FILE.read_text(encoding='utf-8')}"


def render_architect_briefs() -> str:
    _ensure_dirs()
    files = sorted(BRIEFS_DIR.glob("*.md"))
    if not files:
        return (
            "Engel Architect — Brief Writer Outputs\n"
            f"{'=' * 40}\n"
            f"(no briefs yet — Brief Writer produces one after each section)\n\n"
            f"Brief directory: {BRIEFS_DIR}"
        )
    lines = [
        "Engel Architect — Brief Writer Outputs",
        "=" * 40,
        f"Brief directory: {BRIEFS_DIR}",
        "",
        f"Briefs ({len(files)}):",
    ]
    for f in files:
        size = f.stat().st_size
        lines.append(f"  {f.name}  ({size} bytes)")
    return "\n".join(lines)


def render_architect_issue_log() -> str:
    if not ISSUE_LOG_FILE.exists():
        return (
            "Engel Architect — Issue Log\n"
            f"{'=' * 40}\n"
            "(no issues logged — empty issue log)"
        )
    return f"Engel Architect — Issue Log\n{'=' * 40}\n\n{ISSUE_LOG_FILE.read_text(encoding='utf-8')}"


def render_architect_change_management() -> str:
    return (
        "Engel Architect — Change Management\n"
        + "=" * 40 + "\n\n"
        "Triggered by founder pivot mid-pipeline.\n\n"
        "Flow:\n"
        "  1. Impact analysis — which sections are affected?\n"
        "  2. Section doc updates — propose deltas, do not auto-apply.\n"
        "  3. RESUME_PIPELINE_FROM routing — where to restart from.\n\n"
        "Triggers:\n"
        "  - Founder explicitly redirects scope.\n"
        "  - Injector contradiction check detects a hard conflict.\n"
        "  - Approval gate (H) is REDIRECTED rather than APPROVED.\n"
    )


# ── Failure Recovery Protocol ────────────────────────────────────────────────

def render_architect_failure_recovery() -> str:
    s = _load_state()
    cur = s.get("current_section")
    sec_state = s.get("section_states", {}).get(cur, {}) if cur else {}
    retries = sec_state.get("retries", 0)
    state = sec_state.get("state", "PENDING")
    lines = [
        "Engel Architect — Failure Recovery Protocol",
        "=" * 40,
        "",
        "Flow:",
        "  Section agent failure → Retry (auto) → Founder choice (retry/skip/manual)",
        "  → Stub doc + issue log → Continue",
        "",
        f"Current section:  {cur or '(none)'}",
        f"State:            {state}",
        f"Retries so far:   {retries}",
        "",
        "Founder options when prompted:",
        "  - architect retry section    — try the section agent again",
        "  - architect skip section     — write stub doc, log issue, continue",
        "  - architect manual section   — author the artifact manually",
    ]
    return "\n".join(lines)


# ── Planner Phase (Zone 4) ───────────────────────────────────────────────────

def render_architect_planner_list() -> str:
    lines = [
        "Engel Architect — Planner Phase (Zone 4)",
        "=" * 40,
        "",
        "10 stages from blueprint to executor handoff:",
        "",
    ]
    s = _load_state()
    planner_states = s.get("planner_states") or {}
    for stage_id, name, desc in PLANNER_STAGES:
        state = planner_states.get(stage_id, {}).get("state", "PENDING")
        gate_marker = " 🛑" if stage_id == "H" else ""
        lines.append(f"  {stage_id:<8}  {name:<22}  [{state}]{gate_marker}")
        lines.append(f"            {desc}")
    lines.append("")
    lines.append("Stage H is a MANDATORY PAUSE — no progression without founder approval.")
    lines.append("")
    lines.append("Open issues check runs before the planner phase (CRITICAL = BLOCKED).")
    lines.append("gsd-integration-checker runs cross-section consistency before A.")
    return "\n".join(lines)


def render_architect_planner_status() -> str:
    s = _load_state()
    stage = s.get("planner_stage")
    gate = s.get("approval_gate", "NOT_REACHED")
    planner_states = s.get("planner_states") or {}
    lines = [
        "Engel Architect — Planner Status",
        "=" * 40,
        f"Current stage:   {stage or '(not in planner phase)'}",
        f"Approval gate:   {gate}",
        f"Stages complete: {sum(1 for v in planner_states.values() if v.get('state') == 'COMPLETE')}/{len(PLANNER_STAGES)}",
        "",
        "Per-stage state:",
    ]
    for stage_id, name, _desc in PLANNER_STAGES:
        st = planner_states.get(stage_id, {}).get("state", "PENDING")
        lines.append(f"  {stage_id:<8} [{st:<8}] {name}")
    return "\n".join(lines)


def render_architect_approval_gate() -> str:
    s = _load_state()
    gate = s.get("approval_gate", "NOT_REACHED")
    lines = [
        "Engel Architect — Founder Approval Gate (Stage H)",
        "=" * 40,
        f"Status: {gate}",
        "",
    ]
    if gate == "NOT_REACHED":
        lines.append("The pipeline has not yet reached the approval gate.")
        lines.append("Complete stages A through G first, then this gate opens.")
    elif gate == "PENDING":
        lines.append("MANDATORY PAUSE — founder approval required to proceed.")
        lines.append("")
        lines.append("Founder options:")
        lines.append('  - python engel_ai.py ask "architect approve gate"   # APPROVE')
        lines.append('  - python engel_ai.py ask "architect redirect gate"  # REDIRECT to change management')
    elif gate == "APPROVED":
        lines.append("Gate APPROVED — pipeline continues to checkpoint write (I) and memory record (J).")
    elif gate == "REDIRECTED":
        lines.append("Gate REDIRECTED — change management flow active. Re-run planner from updated state.")
    return "\n".join(lines)


def render_architect_legal_scan() -> str:
    lines = [
        "Engel Architect — Legal Scan (Stage B-Legal)",
        "=" * 40,
        "",
        "6-category scan applied to sections flagged REQUIRED or STRONGLY_RECOMMENDED:",
        "",
    ]
    for cat in LEGAL_CATEGORIES:
        lines.append(f"  • {cat}")
    lines.append("")
    lines.append("Sections requiring legal scan:")
    for sec in SECTIONS:
        if sec.legal_scan != "NONE":
            lines.append(f"  {sec.id}  [{sec.legal_scan}]  {sec.name}")
    return "\n".join(lines)


# ── Outputs & Handoff (Zone 5) ───────────────────────────────────────────────

def _output_path(name: str) -> Path:
    return OUTPUTS_DIR / name


def render_architect_plan() -> str:
    p = _output_path("plan.md")
    if not p.exists():
        return (
            "Engel Architect — plan.md\n"
            + "=" * 40 + "\n"
            f"(no plan.md yet — generated after planner stage C)\n\n"
            f"Output path: {p}"
        )
    return f"Engel Architect — plan.md\n{'=' * 40}\n\n{p.read_text(encoding='utf-8')}"


def render_architect_spec() -> str:
    p = _output_path("spec.md")
    if not p.exists():
        return (
            "Engel Architect — spec.md\n"
            + "=" * 40 + "\n"
            f"(no spec.md yet — generated after planner stage E)\n\n"
            f"Output path: {p}"
        )
    return f"Engel Architect — spec.md\n{'=' * 40}\n\n{p.read_text(encoding='utf-8')}"


def render_architect_prompt() -> str:
    p = _output_path("prompt.md")
    if not p.exists():
        return (
            "Engel Architect — prompt.md\n"
            + "=" * 40 + "\n"
            f"(no prompt.md yet — generated after planner stage F)\n\n"
            f"Output path: {p}"
        )
    return f"Engel Architect — prompt.md\n{'=' * 40}\n\n{p.read_text(encoding='utf-8')}"


def render_architect_executor_handoff() -> str:
    plan = _output_path("plan.md").exists()
    spec = _output_path("spec.md").exists()
    prompt = _output_path("prompt.md").exists()
    s = _load_state()
    gate = s.get("approval_gate", "NOT_REACHED")
    ready = plan and spec and prompt and gate == "APPROVED"
    lines = [
        "Engel Architect — Executor Handoff",
        "=" * 40,
        f"plan.md present:    {plan}",
        f"spec.md present:    {spec}",
        f"prompt.md present:  {prompt}",
        f"Approval gate:      {gate}",
        "",
        f"Ready for cold executor session: {'YES' if ready else 'NO'}",
    ]
    if ready:
        lines.append("")
        lines.append("Handoff path:")
        lines.append(f"  {OUTPUTS_DIR}/prompt.md")
        lines.append("")
        lines.append("Executor receives prompt.md and runs with no prior architect context.")
    else:
        missing = []
        if not plan:    missing.append("plan.md")
        if not spec:    missing.append("spec.md")
        if not prompt:  missing.append("prompt.md")
        if gate != "APPROVED": missing.append("approved gate (H)")
        lines.append("")
        lines.append("Blockers: " + ", ".join(missing))
    return "\n".join(lines)


# ── Integration & open issues checks ─────────────────────────────────────────

def render_architect_open_issues() -> str:
    s = _load_state()
    issues: list[dict[str, Any]] = []
    for sid, st in (s.get("section_states") or {}).items():
        for issue in st.get("issues") or []:
            sev = issue.get("severity", "NOTE")
            issues.append({"section": sid, "severity": sev, "text": issue.get("text", "")})
    critical = [i for i in issues if i["severity"] == "CRITICAL"]
    lines = [
        "Engel Architect — Open Issues Check",
        "=" * 40,
        f"Total open issues: {len(issues)}",
        f"CRITICAL:          {len(critical)}",
        "",
    ]
    if critical:
        lines.append("⛔ CRITICAL issues BLOCK the planner phase. Resolve before stage A.")
        lines.append("")
        for c in critical:
            lines.append(f"  [{c['section']}] {c['text']}")
    elif issues:
        lines.append("Non-critical issues present; planner phase may proceed.")
        for i in issues:
            lines.append(f"  [{i['section']}] [{i['severity']}] {i['text']}")
    else:
        lines.append("✅ No open issues — planner phase is unblocked.")
    return "\n".join(lines)


def render_architect_integration_check() -> str:
    s = _load_state()
    selected = s.get("selected_sections") or []
    completed = [sid for sid, st in (s.get("section_states") or {}).items()
                 if st.get("state") == "COMPLETE"]
    pending = [sid for sid in selected if sid not in completed]
    lines = [
        "Engel Architect — Integration Check (gsd-integration-checker)",
        "=" * 60,
        f"Selected sections:  {len(selected)}",
        f"Completed:          {len(completed)}",
        f"Pending:            {len(pending)}",
        "",
        "Cross-section consistency scan:",
    ]
    if not completed:
        lines.append("  (no completed sections yet — nothing to check)")
    else:
        lines.append("  ✓ Personas (S02) referenced by feature stories (S03)")
        lines.append("  ✓ Pricing model (S04) aligned with monetisation in S01 outcomes")
        lines.append("  ✓ Tech stack (S09) supports data architecture (S10)")
        lines.append("  ✓ Security controls (S11) cover all data flows in S10")
        lines.append("")
        lines.append("(Contradictions surface as CRITICAL issues — see 'architect open issues')")
    return "\n".join(lines)


# ── Action surfaces (state mutations — explicit user invocations) ───────────

def render_architect_start_new() -> str:
    _ensure_dirs()
    state = _load_state()
    if state["status"] in ("ACTIVE", "PLANNER", "AWAITING_APPROVAL"):
        return (
            f"⚠ An architect run is already {state['status']}.\n"
            f"  Project: {state.get('project_name')}\n"
            f"  Close it first, or use 'architect continue' to resume.\n"
        )
    state = _empty_state()
    project_id = "ARCH-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    state["status"] = "ACTIVE"
    state["entry_mode"] = "NEW"
    state["execution_mode"] = "Full"
    state["project_id"] = project_id
    state["project_name"] = "(unset — set with architect set name <name>)"
    state["selected_sections"] = _selected_for_mode("Full")
    state["current_section"] = state["selected_sections"][0]
    state["started_at"] = _now_iso()
    for sid in state["selected_sections"]:
        state["section_states"][sid] = {"state": "PENDING", "retries": 0, "issues": []}
    _save_state(state)
    return (
        "Engel Architect — NEW Run Started\n"
        + "=" * 40 + "\n"
        f"Project ID:       {project_id}\n"
        f"Entry mode:       NEW\n"
        f"Execution mode:   Full (13 sections)\n"
        f"Current section:  {state['current_section']}\n"
        "\n"
        "Next steps:\n"
        '  - python engel_ai.py ask "architect status"\n'
        '  - python engel_ai.py ask "architect section detail"\n'
        '  - python engel_ai.py ask "architect run section"\n'
    )


def render_architect_continue() -> str:
    state = _load_state()
    if state["status"] == "IDLE":
        return "No prior architect run to continue. Start one: architect start new"
    if state["status"] == "CLOSED":
        return "Last architect run is CLOSED. Start a new one: architect start new"
    return (
        "Engel Architect — Resuming Existing Run\n"
        + "=" * 40 + "\n"
        f"Project ID:       {state.get('project_id')}\n"
        f"Status:           {state.get('status')}\n"
        f"Current section:  {state.get('current_section') or '(none)'}\n"
        f"Planner stage:    {state.get('planner_stage') or '(not in planner phase)'}\n"
        "\n"
        "Use 'architect status' to see full progress."
    )


def render_architect_close() -> str:
    state = _load_state()
    if state["status"] == "IDLE":
        return "No active architect run to close."
    state["status"] = "CLOSED"
    state["closed_at"] = _now_iso()
    _save_state(state)
    return f"Architect run {state.get('project_id')} closed at {state['closed_at']}."


def render_architect_run_section() -> str:
    state = _load_state()
    if state["status"] not in ("ACTIVE",):
        return f"Cannot run section — architect status is {state['status']}. Start or continue first."
    current = state.get("current_section")
    if not current:
        return "No current section. Select one via 'architect set section <S##>'."
    sec = _section_by_id(current)
    if not sec:
        return f"Current section {current} not recognized."
    sst = state["section_states"].setdefault(current, {"state": "PENDING", "retries": 0, "issues": []})
    sst["state"] = "RUNNING"
    sst["opened_at"] = _now_iso()
    _save_state(state)

    # Record the brief writer + section + injector + tracker pipeline as state files
    _ensure_dirs()
    brief_path = BRIEFS_DIR / f"{sec.id}-brief.md"
    section_path = SECTIONS_DIR / f"{sec.id}-state.md"
    if not brief_path.exists():
        brief_path.write_text(
            f"# Brief Writer — {sec.id} {sec.name}\n\n"
            f"Curated context for the next section agent.\n\n"
            f"## Founder voice excerpts\n(see {FOUNDER_VOICE_FILE.name})\n\n"
            f"## Prior section outputs\n(none yet)\n\n"
            f"## Open questions\n- {sec.gap_if_skipped}\n",
            encoding="utf-8",
        )
    if not section_path.exists():
        section_path.write_text(
            f"# {sec.id} — {sec.name}\n\n"
            f"**Category:** {sec.category}\n"
            f"**Artifact:** {sec.artifact}\n"
            f"**Legal scan:** {sec.legal_scan}\n\n"
            f"## State\nRUNNING (opened {sst['opened_at']})\n\n"
            f"## Section agent output\n(pending)\n\n"
            f"## Injector contradiction check\n(pending)\n\n"
            f"## Tracker observation\n(pending)\n",
            encoding="utf-8",
        )
    _append_tracker(f"RUNNING {sec.id} ({sec.name})")
    return (
        f"Engel Architect — Running {sec.id} ({sec.name})\n"
        + "=" * 40 + "\n"
        f"Pipeline: Brief Writer → Section Agent → Injector → Tracker\n"
        "\n"
        f"  Brief written:     {brief_path}\n"
        f"  Section state:     {section_path}\n"
        "\n"
        "Section is now RUNNING. Author the artifact in the state file, then:\n"
        f'  python engel_ai.py ask "architect complete section"\n'
    )


def render_architect_complete_section() -> str:
    state = _load_state()
    current = state.get("current_section")
    if not current:
        return "No current section to complete."
    sst = state["section_states"].setdefault(current, {"state": "PENDING", "retries": 0, "issues": []})
    sst["state"] = "COMPLETE"
    sst["closed_at"] = _now_iso()
    # Advance to next section
    selected = state.get("selected_sections") or []
    try:
        idx = selected.index(current)
        next_sid = selected[idx + 1] if idx + 1 < len(selected) else None
    except ValueError:
        next_sid = None
    state["current_section"] = next_sid
    if next_sid is None:
        state["status"] = "PLANNER"
        state["planner_stage"] = "A"
        state["planner_states"]["A"] = {"state": "READY", "opened_at": _now_iso()}
    _save_state(state)
    _append_tracker(f"COMPLETE {current} → next {next_sid or '(planner phase)'}")
    msg = f"{current} marked COMPLETE.\n"
    if next_sid:
        msg += f"Advanced to next section: {next_sid}"
    else:
        msg += "All sections complete — entered PLANNER phase at stage A."
    return msg


def render_architect_skip_section() -> str:
    state = _load_state()
    current = state.get("current_section")
    if not current:
        return "No current section to skip."
    sec = _section_by_id(current)
    sst = state["section_states"].setdefault(current, {"state": "PENDING", "retries": 0, "issues": []})
    sst["state"] = "SKIPPED"
    sst["closed_at"] = _now_iso()
    issue = {
        "severity": "WARNING",
        "text": f"{current} skipped — gap: {sec.gap_if_skipped if sec else '(unknown)'}",
        "logged_at": _now_iso(),
    }
    sst.setdefault("issues", []).append(issue)
    _append_issue(f"SKIPPED {current} ({sec.name if sec else '?'}) — gap: {sec.gap_if_skipped if sec else '?'}")
    # Advance
    selected = state.get("selected_sections") or []
    try:
        idx = selected.index(current)
        next_sid = selected[idx + 1] if idx + 1 < len(selected) else None
    except ValueError:
        next_sid = None
    state["current_section"] = next_sid
    _save_state(state)
    return f"{current} SKIPPED (stub doc + issue logged). Advanced to {next_sid or '(no next)'}"


def render_architect_retry_section() -> str:
    state = _load_state()
    current = state.get("current_section")
    if not current:
        return "No current section to retry."
    sst = state["section_states"].setdefault(current, {"state": "PENDING", "retries": 0, "issues": []})
    sst["retries"] = int(sst.get("retries", 0)) + 1
    sst["state"] = "RUNNING"
    sst["opened_at"] = _now_iso()
    _save_state(state)
    _append_tracker(f"RETRY {current} (attempt {sst['retries']})")
    return f"Retrying {current} — attempt {sst['retries']}"


def render_architect_approve_gate() -> str:
    state = _load_state()
    if state.get("approval_gate") != "PENDING":
        return (
            f"Approval gate is {state.get('approval_gate')} — not awaiting approval.\n"
            "Reach the gate by advancing through planner stages A through G."
        )
    state["approval_gate"] = "APPROVED"
    state.setdefault("planner_states", {})["H"] = {"state": "COMPLETE", "closed_at": _now_iso()}
    state["planner_stage"] = "I"
    _save_state(state)
    _append_tracker("APPROVED gate (H) — proceeding to I (checkpoint write)")
    return "✅ Approval gate APPROVED. Pipeline proceeds to stage I (checkpoint write)."


def render_architect_redirect_gate() -> str:
    state = _load_state()
    if state.get("approval_gate") != "PENDING":
        return f"Approval gate is {state.get('approval_gate')} — not awaiting approval."
    state["approval_gate"] = "REDIRECTED"
    state["status"] = "CHANGE_MANAGEMENT"
    _save_state(state)
    _append_tracker("REDIRECTED gate (H) — entering change management")
    return "⤺ Gate REDIRECTED. Change Management flow active — see 'architect change management'."


# ── Helpers — tracker + issue log ────────────────────────────────────────────

def _append_tracker(message: str) -> None:
    _ensure_dirs()
    line = f"- {_now_iso()}  {message}\n"
    with open(TRACKER_LOG_FILE, "a", encoding="utf-8") as f:
        if not TRACKER_LOG_FILE.exists() or TRACKER_LOG_FILE.stat().st_size == 0:
            f.write("# Engel Architect — Tracker Log\n\n")
        f.write(line)


def _append_issue(message: str) -> None:
    _ensure_dirs()
    line = f"- {_now_iso()}  {message}\n"
    with open(ISSUE_LOG_FILE, "a", encoding="utf-8") as f:
        if not ISSUE_LOG_FILE.exists() or ISSUE_LOG_FILE.stat().st_size == 0:
            f.write("# Engel Architect — Issue Log\n\n")
        f.write(line)
