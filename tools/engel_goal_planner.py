#!/usr/bin/env python3
"""Planning + calendar layer over Engel's goal store.

The agentic goal machinery already exists: `engel_agent_goal_loop.py` runs a goal
multi-turn and ONLY a completion predicate on disk -- never the agent's own claim --
ends it. What it has never had is a FACE: no progress meter, no calendar, and no way for
Engel to schedule when a goal should start or to record when it projects one finishing.

This module is that layer, and it inherits the goal loop's single hard rule:

  A cadence estimate NEVER claims completion. Rounds spent can PROJECT a finish date,
  but the meter only reads 100% when the goal record's own status is a real terminal
  success (`status == "done"` and `ok is True`). An agent that has spent 24 of 25 rounds
  is at "24/25 rounds", not "96% done" -- because the world, not the round counter,
  decides done.

What it produces (all under memory/engel_goals/, no C-drive, offline):

  ENGEL_GOAL_PLAN.json     per-goal planning: operator start/due targets (authoritative),
                           Engel's projected finish (cadence-derived, honestly null when
                           unprojectable), and a progress reading with its BASIS so the UI
                           can show WHY a bar is where it is.
  calendar view (--calendar YYYY-MM)   a month grid the Goals window renders: each day
                           carries the goal events that fall on it (start / projected
                           finish / operator due / done), never a guessed date.

"Engel writes itself to the calendar" is `plan()`: it recomputes every goal's projected
finish from its own observed round cadence and writes it, so the calendar always reflects
what Engel currently expects. Operator-set start/due dates are preserved across replans;
Engel only ever fills the projection it is entitled to compute.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GOAL_DIR = ROOT / "memory" / "engel_goals"
PLAN_PATH = GOAL_DIR / "ENGEL_GOAL_PLAN.json"

PLAN_SCHEMA = "engel_goal_plan_v1"
CALENDAR_SCHEMA = "engel_goal_calendar_month_v1"
GOAL_SCHEMA = "engel_goal_v1"

# The goal loop's ceiling (engel_agent_goal_loop.MAX_TURN_CEILING). A rounds budget is a
# CEILING, never a target, so it is only ever used to bound a cadence ESTIMATE -- and the
# estimate is capped strictly below 100 so it can never masquerade as completion.
ROUNDS_CEILING = 25
_ESTIMATE_CAP = 95

# Terminal states a goal record reports. Only DONE is a success; the rest are honest ends
# that must show as stalled/failed, never as a high progress number.
# "rejected" / "invalid" cover records the goal loop already refused
# ("draft rejected: not Engelscript", "plan invalid"). Those were falling through
# into the in-progress estimate and drawing a live meter for work that had stopped.
_DONE_OK = "done"
_STALLED_MARKERS = (
    "no planner",
    "failed",
    "blocked",
    "error",
    "refused",
    "cannot",
    "rejected",
    "invalid",
    "not engelscript",
)


def _is_stalled_status(status: str) -> bool:
    return _refusal_label(status) is not None


def _refusal_label(status: str) -> str | None:
    """Short chip the Goals window can show. A refused record is not one shared
    'stalled' stamp: the label names why it stopped."""
    low = status.casefold()
    if "not engelscript" in low or "rejected" in low:
        return "Rejected"
    if "invalid" in low:
        return "Invalid plan"
    if "no planner" in low:
        return "No planner"
    if any(marker in low for marker in ("failed", "blocked", "error", "refused", "cannot")):
        return "Stopped"
    return None


def _refusal_detail(status: str) -> str:
    low = status.casefold()
    if "not engelscript" in low:
        return "The draft was not Engelscript."
    if "invalid" in low:
        return "The plan did not parse."
    if "no planner" in low:
        return "No planner was available."
    return f"The goal record says {status}."


def repair_mojibake(text: str) -> str:
    """Undo UTF-8 that was decoded as Windows-1252, a few times.

    The NVIDIA goal title stored the multiplication sign × as the double-decoded
    sequence that renders like 'Ãƒâ€”'. Plain text has none of those markers, so
    a normal title is left alone.
    """
    current = str(text or "")
    for _ in range(3):
        if not any(marker in current for marker in ("\u00c3", "\u00c2", "\u00e2\u20ac")):
            break
        try:
            nxt = current.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        if not nxt or nxt == current:
            break
        current = nxt
    return current


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat()


def _parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        # bare date (YYYY-MM-DD) from an operator target
        try:
            dt = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    return dt.replace(tzinfo=dt.tzinfo or timezone.utc)


def _date_key(dt: datetime | None) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d") if dt else ""


@dataclass
class GoalRecord:
    slug: str
    goal: str
    status: str
    ok: bool
    rounds_spent: int
    created_at: datetime | None
    updated_at: datetime | None
    path: Path
    raw: dict[str, Any] = field(default_factory=dict)


def _load_goal(path: Path) -> GoalRecord | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict) or doc.get("schema") != GOAL_SCHEMA:
        return None
    return GoalRecord(
        slug=str(doc.get("slug") or path.stem),
        goal=str(doc.get("goal") or ""),
        status=str(doc.get("status") or ""),
        ok=bool(doc.get("ok")),
        rounds_spent=int(doc.get("rounds_spent") or 0),
        created_at=_parse_dt(doc.get("created_at_utc")),
        updated_at=_parse_dt(doc.get("updated_at_utc")),
        path=path,
        raw=doc,
    )


def load_goals(goal_dir: Path | None = None) -> list[GoalRecord]:
    root = goal_dir or GOAL_DIR
    if not root.is_dir():
        return []
    goals = [_load_goal(p) for p in sorted(root.glob("*.json")) if p.name != PLAN_PATH.name]
    return [g for g in goals if g is not None]


def compute_progress(goal: GoalRecord) -> dict[str, Any]:
    """Honest progress reading. Completion comes ONLY from the goal's terminal success;
    everything else is an explicitly-labelled cadence estimate, capped below 100."""
    status_low = goal.status.casefold()
    if status_low == _DONE_OK and goal.ok:
        note = str(goal.raw.get("finished_note") or "").strip()
        if str(goal.raw.get("finished_by") or "") == "josh" and note:
            return {"percent": 100, "state": "done",
                    "basis": f"Finished by Josh. {note}"}
        return {"percent": 100, "state": "done",
                "basis": "Finished. The goal record reports status=done and ok=true."}
    if status_low == "with josh":
        return {"percent": 0, "state": "with Josh",
                "basis": "Josh opened this goal. It stays open until Josh marks it finished."}
    refusal = _refusal_label(goal.status)
    if refusal:
        # Rounds already spent stay on the bar. The chip names the refusal.
        # Percent still cannot reach 100: only status=done and ok=true does that.
        detail = _refusal_detail(goal.status)
        if goal.rounds_spent <= 0:
            return {
                "percent": 0,
                "state": refusal,
                "basis": f"{detail} No rounds were spent.",
            }
        fraction = min(goal.rounds_spent / ROUNDS_CEILING, 1.0)
        percent = min(int(round(fraction * 100)), _ESTIMATE_CAP)
        return {
            "percent": percent,
            "state": refusal,
            "basis": (
                f"{detail} {goal.rounds_spent} of {ROUNDS_CEILING} rounds spent. "
                "This is not a finished goal."
            ),
        }
    # In progress: estimate from rounds spent against the ceiling, never reaching 100.
    if goal.rounds_spent <= 0:
        return {"percent": 0, "state": "not_started",
                "basis": "no rounds spent yet"}
    fraction = min(goal.rounds_spent / ROUNDS_CEILING, 1.0)
    percent = min(int(round(fraction * 100)), _ESTIMATE_CAP)
    return {
        "percent": percent,
        "state": "in_progress",
        "basis": (
            f"{goal.rounds_spent} of {ROUNDS_CEILING} rounds spent. "
            "This is a pace estimate, not a finished goal."
        ),
    }


def project_finish(goal: GoalRecord, now: datetime | None = None) -> dict[str, Any]:
    """Cadence-derived projected finish. Honestly null when it cannot be computed:
    a finished goal has no projection, and a goal with no measured round cadence
    (zero rounds, or no time elapsed) gets an explicit 'unprojectable' rather than an
    invented date. Never a guess."""
    now = now or _now()
    status_low = goal.status.casefold()
    if status_low == _DONE_OK and goal.ok:
        return {"date": _date_key(goal.updated_at), "basis": "already done",
                "projectable": False}
    if status_low == "with josh":
        return {"date": "", "basis": "", "projectable": False}
    if _is_stalled_status(goal.status):
        # Empty basis: the Goals window prints this line under the meter, and a
        # second "stopped (...)" repeats the chip.
        return {"date": "", "basis": "", "projectable": False}
    if goal.rounds_spent <= 0 or not goal.created_at or not goal.updated_at:
        return {"date": "", "basis": "no measured round cadence yet", "projectable": False}
    elapsed = (goal.updated_at - goal.created_at).total_seconds()
    if elapsed <= 0:
        return {"date": "", "basis": "no measurable elapsed time", "projectable": False}
    per_round = elapsed / goal.rounds_spent
    # A few seconds between rounds is not a pace. Printing it as 0.0h/round
    # put a finish date on the calendar for work that had no measured cadence.
    if per_round < 60:
        return {
            "date": "",
            "basis": "rounds landed too close together to measure a pace",
            "projectable": False,
        }
    rounds_left = max(ROUNDS_CEILING - goal.rounds_spent, 1)
    projected = now + timedelta(seconds=per_round * rounds_left)
    hours = per_round / 3600
    if hours >= 1:
        pace = f"{hours:.1f}h"
    else:
        pace = f"{max(int(round(per_round / 60)), 1)}m"
    return {
        "date": _date_key(projected),
        "basis": f"{rounds_left} rounds left at {pace} per round",
        "projectable": True,
    }


def _load_plan() -> dict[str, Any]:
    if PLAN_PATH.is_file():
        try:
            doc = json.loads(PLAN_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(doc, dict):
                return doc
        except (OSError, ValueError):
            pass
    return {"schema": PLAN_SCHEMA, "goals": {}}


def _valid_date_arg(value: str) -> str:
    """An operator start/due date must be a real YYYY-MM-DD or empty (to clear)."""
    text = str(value or "").strip()
    if not text:
        return ""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) or _parse_dt(text) is None:
        raise ValueError(f"date must be YYYY-MM-DD, got {value!r}")
    return text


def set_schedule(slug: str, *, start: str | None = None, due: str | None = None,
                 agent: str | None = None, checks_json: str | None = None,
                 max_turns: int | None = None, goal_dir: Path | None = None,
                 allow_new: bool = False, goal_text: str = "",
                 repeat_weekly: bool | None = None) -> dict[str, Any]:
    """Operator sets a goal's start/due date and (for a scheduled START) its launch spec.

    A start date alone cannot launch anything: the goal loop requires an authored agent
    and at least one completion check fixed BEFORE the run (its core safety rule), so a
    schedulable entry stores exactly that. Authoritative over Engel's projection;
    preserved across replans. Passing '' clears a field. `allow_new` lets the operator
    schedule a goal that has no record yet (first run creates it)."""
    known = {g.slug for g in load_goals(goal_dir)}
    if slug not in known and not allow_new:
        raise ValueError(f"unknown goal slug {slug!r} (use --new to schedule a fresh goal)")
    plan_doc = _load_plan()
    entry = plan_doc["goals"].setdefault(slug, {})
    if goal_text:
        entry["goal"] = goal_text
    if start is not None:
        entry["operator_start_date"] = _valid_date_arg(start)
    if due is not None:
        entry["operator_due_date"] = _valid_date_arg(due)
    if repeat_weekly is not None:
        entry["repeat_weekly"] = bool(repeat_weekly)
    if agent is not None:
        entry["launch_agent"] = str(agent).strip()
    if checks_json is not None:
        checks = json.loads(checks_json) if checks_json.strip() else []
        if not isinstance(checks, list):
            raise ValueError("checks must be a JSON list of completion-check objects")
        entry["launch_checks"] = checks
    if max_turns is not None:
        entry["launch_max_turns"] = max(1, min(int(max_turns), ROUNDS_CEILING))
    entry["updated_at_utc"] = _iso()
    _write_plan(plan_doc)
    return entry


def tick(goal_dir: Path | None = None, now: datetime | None = None,
         launch: bool = True) -> dict[str, Any]:
    """Start goals whose operator start date has arrived. Called by the cron lane.

    Launches AT MOST ONE goal per tick (no stampedes), only when the entry carries a
    complete launch spec (agent + checks), has not been launched before, and the goal is
    not already done. The launched run is the ordinary goal loop -- authored agent,
    fixed completion predicate, action grants default-off -- so a scheduled start has
    exactly the same safety envelope as a hand-started one. Every decision is recorded."""
    import subprocess

    now = now or _now()
    today = _date_key(now)
    plan_doc = _load_plan()
    done_slugs = {
        g.slug for g in load_goals(goal_dir)
        if g.status.casefold() == _DONE_OK and g.ok
    }
    result: dict[str, Any] = {"schema": "engel_goal_tick_v1", "date": today,
                              "due": [], "launched": None, "skipped": []}
    for slug, entry in sorted(plan_doc.get("goals", {}).items()):
        start = str(entry.get("operator_start_date") or "")
        if not start or start > today:
            continue
        if entry.get("launched_at_utc"):
            continue
        if slug in done_slugs:
            result["skipped"].append({"slug": slug, "reason": "already done"})
            continue
        agent = str(entry.get("launch_agent") or "")
        checks = entry.get("launch_checks") or []
        if not agent or not checks:
            result["skipped"].append(
                {"slug": slug,
                 "reason": "start date arrived but no launch spec (agent + checks required)"})
            continue
        result["due"].append(slug)
    if launch and result["due"]:
        slug = result["due"][0]
        entry = plan_doc["goals"][slug]
        command = [
            _python_exe(), str(ROOT / "tools" / "engel_agent_goal_loop.py"),
            "--agent", str(entry["launch_agent"]),
            "--goal", str(entry.get("goal") or slug),
            "--max-turns", str(entry.get("launch_max_turns") or 6),
        ]
        for check in entry["launch_checks"]:
            command += ["--check", json.dumps(check)]
        # DETACHED on purpose: the tick is driven by the stack controller's heartbeat,
        # and a goal run can take an hour -- blocking the heartbeat would stall every
        # other stack service. The goal loop writes its own receipt; tomorrow's replan
        # reads the goal record it updates.
        try:
            log_path = GOAL_DIR / f"launch_{slug}_{_now().strftime('%Y%m%dT%H%M%SZ')}.log"
            with log_path.open("w", encoding="utf-8") as log:
                subprocess.Popen(
                    command, stdout=log, stderr=subprocess.STDOUT, cwd=str(ROOT),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            entry["launched_at_utc"] = _iso(now)
            entry["launch_log"] = str(log_path)
            result["launched"] = {"slug": slug, "log": str(log_path)}
        except Exception as exc:  # noqa: BLE001 -- a failed launch is a recorded fact
            entry["launch_error"] = f"{type(exc).__name__}: {exc}"
            result["launched"] = {"slug": slug, "error": entry["launch_error"]}
        _write_plan(plan_doc)
    return result


def _python_exe() -> str:
    """An interpreter that exists when fired from a headless heartbeat with no venv
    on PATH. Prefer the app's own runtime python, fall back to this process's."""
    import sys

    bundled = ROOT / "runtime" / "python310" / "python.exe"
    return str(bundled) if bundled.is_file() else sys.executable


CRON_JOB_ID = "engel-goal-planner-daily-tick"


def register_cron(hour: int = 7) -> dict[str, Any]:
    """Register the daily tick with Engel's own cron lane, idempotently."""
    import engel_cron

    store = engel_cron.CronStore()
    if CRON_JOB_ID in store.jobs:
        return {"registered": False, "reason": "already registered", "job_id": CRON_JOB_ID}
    job = engel_cron.CronJob(
        id=CRON_JOB_ID,
        name="Goal planner daily tick (scheduled goal starts + calendar replan)",
        schedule={"kind": "cron", "cron": f"0 {int(hour)} * * *"},
        payload={"kind": "command",
                 "argv": [_python_exe(), str(ROOT / "tools" / "engel_goal_planner.py"), "--tick"]},
        enabled=True,
    )
    store.add(job)
    return {"registered": True, "job_id": CRON_JOB_ID, "hour_utc": int(hour)}


def _write_plan(plan: dict[str, Any]) -> None:
    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    plan["updated_at_utc"] = _iso()
    PLAN_PATH.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    _sync_plan_to_ct()


def _sync_plan_to_ct() -> None:
    """Mirror the plan to CT so the Server World office Kanban reads the same truth
    as the Goals window. Best-effort: a sync miss never fails a plan write; the
    office states 'not synced yet' honestly until the next successful push.
    Disable with ENGEL_GOAL_PLAN_CT_SYNC=0."""
    import os
    import subprocess

    if str(os.environ.get("ENGEL_GOAL_PLAN_CT_SYNC", "1")).lower() in {"0", "false", "off"}:
        return
    key = Path.home() / ".ssh" / "engel_ai_main_ct246_ed25519"
    if not key.is_file():
        return
    try:
        subprocess.run(
            ["scp", "-i", str(key), "-P", "24622", "-o", "BatchMode=yes",
             "-o", "ConnectTimeout=5", str(PLAN_PATH),
             "root@192.0.2.50:/opt/engel/memory/engel_goals/ENGEL_GOAL_PLAN.json"],
            capture_output=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:  # noqa: BLE001 — advisory mirror only
        pass


_SLUG_RE = re.compile(r"^[a-z0-9_]{1,80}$")


def _goal_record_path(slug: str, goal_dir: Path | None = None) -> Path:
    if not _SLUG_RE.fullmatch(slug):
        raise ValueError(f"bad goal slug {slug!r}")
    return (goal_dir or GOAL_DIR) / f"{slug}.json"


def _interaction_face(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    face: list[dict[str, str]] = []
    for item in raw[-12:]:
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get("text") or "").split())
        if not text:
            continue
        face.append({
            "role": str(item.get("role") or "josh"),
            "kind": str(item.get("kind") or "note"),
            "text": text[:500],
            "at": str(item.get("at") or ""),
        })
    return face


def _load_mutable_goal(slug: str, goal_dir: Path | None = None) -> tuple[dict[str, Any], Path]:
    path = _goal_record_path(slug, goal_dir)
    if path.is_file():
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(doc, dict) or doc.get("schema") != GOAL_SCHEMA:
            raise ValueError(f"{slug} is not a goal record")
        return doc, path
    plan_doc = _load_plan()
    prior = (plan_doc.get("goals") or {}).get(slug)
    if not isinstance(prior, dict) or not str(prior.get("goal") or "").strip():
        raise ValueError(f"unknown goal {slug}")
    return {
        "schema": GOAL_SCHEMA,
        "slug": slug,
        "goal": str(prior.get("goal")),
        "status": "with Josh",
        "ok": False,
        "rounds_spent": 0,
        "created_at_utc": _iso(),
        "conducts": [],
        "interaction": [],
    }, path


def _append_goal_turn(doc: dict[str, Any], *, kind: str, text: str) -> None:
    turns = doc.get("interaction")
    if not isinstance(turns, list):
        turns = []
    turns.append({"role": "josh", "kind": kind, "text": text, "at": _iso()})
    doc["interaction"] = turns[-40:]
    doc["updated_at_utc"] = _iso()


def _write_goal_doc(path: Path, doc: dict[str, Any], goal_dir: Path | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    plan(goal_dir)


def record_turn(slug: str, text: str, goal_dir: Path | None = None) -> dict[str, Any]:
    """Josh adds one line on a goal. This does not finish it and does not launch a run."""
    said = " ".join(str(text or "").split())
    if not said:
        raise ValueError("say what you want to add")
    doc, path = _load_mutable_goal(slug, goal_dir)
    _append_goal_turn(doc, kind="note", text=said)
    if str(doc.get("status") or "").casefold() != _DONE_OK:
        doc["status"] = "with Josh"
        doc["ok"] = False
    _write_goal_doc(path, doc, goal_dir)
    return {"slug": slug, "status": doc.get("status"), "ok": False, "text": said}


def finish_goal(slug: str, note: str, goal_dir: Path | None = None) -> dict[str, Any]:
    """Josh marks a goal finished. The note is the completion, not an agent claim.

    A blank note is refused. Nothing here launches work or calls a provider.
    """
    said = " ".join(str(note or "").split())
    if len(said) < 3:
        raise ValueError("say what finished, in a few words")
    doc, path = _load_mutable_goal(slug, goal_dir)
    _append_goal_turn(doc, kind="finish", text=said)
    doc["status"] = _DONE_OK
    doc["ok"] = True
    doc["finished_by"] = "josh"
    doc["finished_note"] = said
    _write_goal_doc(path, doc, goal_dir)
    return {"slug": slug, "status": "done", "ok": True, "finished_by": "josh", "finished_note": said}


def plan(goal_dir: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Recompute every goal's projection + progress and write the plan. This is how
    'Engel writes itself to the calendar': projections come from Engel's own observed
    cadence; operator-set start/due dates are read and preserved, never overwritten."""
    now = now or _now()
    existing = _load_plan()
    goals_out: dict[str, Any] = {}
    for goal in load_goals(goal_dir):
        prior = existing.get("goals", {}).get(goal.slug, {})
        progress = compute_progress(goal)
        projection = project_finish(goal, now=now)
        goals_out[goal.slug] = {
            "slug": goal.slug,
            "goal": repair_mojibake(goal.goal),
            "status": goal.status,
            "rounds_spent": goal.rounds_spent,
            "progress_percent": progress["percent"],
            "progress_state": progress["state"],
            "progress_basis": progress["basis"],
            "operator_start_date": str(prior.get("operator_start_date") or ""),
            "operator_due_date": str(prior.get("operator_due_date") or ""),
            "repeat_weekly": bool(prior.get("repeat_weekly")),
            "launch_agent": str(prior.get("launch_agent") or ""),
            "launch_checks": prior.get("launch_checks") or [],
            "launch_max_turns": prior.get("launch_max_turns"),
            "launched_at_utc": str(prior.get("launched_at_utc") or ""),
            "projected_finish_date": projection["date"],
            "projected_finish_basis": projection["basis"],
            "projected_finish_projectable": projection["projectable"],
            "created_at_utc": _iso(goal.created_at) if goal.created_at else "",
            "updated_at_utc": _iso(goal.updated_at) if goal.updated_at else "",
            "finished_by": str(goal.raw.get("finished_by") or ""),
            "finished_note": str(goal.raw.get("finished_note") or ""),
            "interaction": _interaction_face(goal.raw.get("interaction")),
        }
    # Operator-placed entries with no run record yet (goals and weekly tasks composed
    # in the Goals window) stay on the plan as honestly "scheduled": zero progress,
    # no invented projection, visible on the calendar. When a run later creates the
    # goal record under the same slug, the record's truth takes over above.
    for slug, prior in existing.get("goals", {}).items():
        if slug in goals_out or not isinstance(prior, dict):
            continue
        if not (prior.get("goal") or prior.get("operator_start_date")
                or prior.get("operator_due_date")):
            continue
        goals_out[slug] = {
            "slug": slug,
            "goal": repair_mojibake(str(prior.get("goal") or slug.replace("_", " "))),
            "status": "scheduled",
            "rounds_spent": 0,
            "progress_percent": 0,
            "progress_state": "scheduled",
            "progress_basis": "operator-scheduled; no run recorded yet",
            "operator_start_date": str(prior.get("operator_start_date") or ""),
            "operator_due_date": str(prior.get("operator_due_date") or ""),
            "repeat_weekly": bool(prior.get("repeat_weekly")),
            "launch_agent": str(prior.get("launch_agent") or ""),
            "launch_checks": prior.get("launch_checks") or [],
            "launched_at_utc": str(prior.get("launched_at_utc") or ""),
            "projected_finish_date": "",
            "projected_finish_basis": "not started",
            "projected_finish_projectable": False,
            "created_at_utc": str(prior.get("updated_at_utc") or ""),
            "updated_at_utc": str(prior.get("updated_at_utc") or ""),
            "finished_by": "",
            "finished_note": "",
            "interaction": _interaction_face(prior.get("interaction")),
        }
    out = {"schema": PLAN_SCHEMA, "goals": goals_out,
           "goal_count": len(goals_out), "generated_at_utc": _iso(now)}
    _write_plan(out)
    return out


def calendar_view(year: int, month: int, goal_dir: Path | None = None,
                  now: datetime | None = None) -> dict[str, Any]:
    """A month grid the Goals window renders. Each event sits on a real date only:
    an operator start, an operator due, Engel's projected finish, or a done stamp.
    A goal with no dated anything contributes nothing -- no filler."""
    if not (1 <= month <= 12) or not (1970 <= year <= 3000):
        raise ValueError("year/month out of range")
    plan_doc = plan(goal_dir, now=now)  # always render against a fresh plan
    days: dict[str, list[dict[str, Any]]] = {}

    def add(date_str: str, slug: str, goal: str, kind: str) -> None:
        if not date_str:
            return
        dt = _parse_dt(date_str)
        if dt is None or dt.year != year or dt.month != month:
            return
        days.setdefault(_date_key(dt), []).append(
            {"slug": slug, "goal": goal, "kind": kind})

    for slug, entry in plan_doc["goals"].items():
        goal_text = str(entry.get("goal") or slug)
        start = str(entry.get("operator_start_date") or "")
        if entry.get("repeat_weekly") and start:
            # A weekly task repeats on its start date's weekday, from the start date
            # forward. Real derived dates only -- never before the anchor.
            anchor = _parse_dt(start)
            if anchor is not None:
                days_in_month = (datetime(year + (month == 12), month % 12 + 1, 1)
                                 - timedelta(days=1)).day
                for day in range(1, days_in_month + 1):
                    candidate = datetime(year, month, day, tzinfo=timezone.utc)
                    if (candidate.weekday() == anchor.weekday()
                            and candidate.date() >= anchor.date()):
                        add(candidate.strftime("%Y-%m-%d"), slug, goal_text, "weekly")
        else:
            add(start, slug, goal_text, "start")
        add(entry.get("operator_due_date"), slug, goal_text, "due")
        if str(entry.get("progress_state")) == "done":
            add(entry.get("projected_finish_date"), slug, goal_text, "done")
        elif entry.get("projected_finish_projectable"):
            add(entry.get("projected_finish_date"), slug, goal_text, "projected_finish")

    return {
        "schema": CALENDAR_SCHEMA,
        "year": year,
        "month": month,
        "days": {k: days[k] for k in sorted(days)},
        "event_count": sum(len(v) for v in days.values()),
        "generated_at_utc": _iso(now),
    }


def status_summary(goal_dir: Path | None = None) -> dict[str, Any]:
    doc = plan(goal_dir)
    goals = list(doc["goals"].values())
    return {
        "goal_count": len(goals),
        "done": sum(1 for g in goals if g["progress_state"] == "done"),
        "in_progress": sum(1 for g in goals if g["progress_state"] == "in_progress"),
        "stalled": sum(
            1 for g in goals
            if g["progress_state"] in {
                "stalled", "Stopped", "Rejected", "Invalid plan", "No planner",
            }
        ),
        "scheduled": sum(1 for g in goals if g["operator_start_date"]),
        "projected": sum(1 for g in goals if g["projected_finish_projectable"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="recompute + write the plan")
    parser.add_argument("--status", action="store_true", help="one-line planning summary")
    parser.add_argument("--calendar", default="", help="month view for YYYY-MM")
    parser.add_argument("--set", default="", help="goal slug to schedule")
    parser.add_argument("--start", default=None, help="operator start date YYYY-MM-DD ('' clears)")
    parser.add_argument("--due", default=None, help="operator due date YYYY-MM-DD ('' clears)")
    parser.add_argument("--agent", default=None, help="authored agent for a scheduled start")
    parser.add_argument("--checks", default=None,
                        help="JSON list of goal-loop completion checks for a scheduled start")
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--goal-text", default="", help="goal wording for a --new schedule")
    parser.add_argument("--new", action="store_true",
                        help="allow scheduling a goal that has no record yet")
    parser.add_argument("--weekly", action="store_true",
                        help="repeat on the start date's weekday (weekly task)")
    parser.add_argument("--add", default="",
                        help="place a new goal/task by TITLE (slug derived); combine "
                             "with --start/--due/--weekly; used by the Goals window")
    parser.add_argument("--turn", default="", help="goal slug Josh is talking to")
    parser.add_argument("--say", default="", help="Josh's line for --turn")
    parser.add_argument("--finish", default="", help="goal slug Josh is marking finished")
    parser.add_argument("--note", default="", help="what finished, for --finish")
    parser.add_argument("--tick", action="store_true",
                        help="start goals whose operator start date has arrived (cron lane)")
    parser.add_argument("--register-cron", action="store_true",
                        help="register the daily tick in Engel's cron store")
    args = parser.parse_args(argv)

    if args.finish:
        print(json.dumps(finish_goal(args.finish, args.note), indent=2))
    elif args.turn:
        print(json.dumps(record_turn(args.turn, args.say), indent=2))
    elif args.add:
        title = args.add.strip()
        slug = re.sub(r"[^a-z0-9]+", "_", title.casefold()).strip("_")[:60] or "goal"
        entry = set_schedule(
            slug, start=args.start, due=args.due, allow_new=True, goal_text=title,
            repeat_weekly=args.weekly or None)
        plan()  # make it visible to the window immediately
        print(json.dumps({"slug": slug, **entry}, indent=2))
    elif args.set:
        print(json.dumps(set_schedule(
            args.set, start=args.start, due=args.due, agent=args.agent,
            checks_json=args.checks, max_turns=args.max_turns,
            allow_new=args.new, goal_text=args.goal_text,
            repeat_weekly=args.weekly or None), indent=2))
    elif args.tick:
        # (2026-08-16) the daily tick is the Goals window's ONLY automatic entry
        # point, and its caption promises "Engel replans daily" - so the tick
        # both starts due goals AND recomputes the plan/projections. Before this,
        # the tick launched starts only and the calendar's plan stamp went stale
        # the moment nothing was due (live: stamp sat at 2026-08-15T01:45Z while
        # the caption promised daily replans).
        tick_result = tick()
        replanned = plan()
        tick_result["replanned"] = True
        tick_result["replan_generated_at_utc"] = str(
            replanned.get("generated_at_utc") or replanned.get("updated_at_utc") or ""
        )
        print(json.dumps(tick_result, indent=2))
    elif args.register_cron:
        print(json.dumps(register_cron(), indent=2))
    elif args.calendar:
        year, month = (int(x) for x in args.calendar.split("-")[:2])
        print(json.dumps(calendar_view(year, month), indent=2))
    elif args.status:
        print(json.dumps(status_summary(), indent=2))
    else:
        print(json.dumps(plan(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
