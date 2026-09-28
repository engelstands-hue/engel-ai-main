#!/usr/bin/env python3
"""Gate for the goal planning + calendar layer (tools/engel_goal_planner.py).

The dangerous failure directions: a meter that claims done when the world has not
said so, a projection invented without cadence, and a scheduled start that launches
without the goal loop's safety envelope (agent + fixed completion checks)."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import engel_goal_planner as gp  # noqa: E402

checks: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


def goal(slug: str, status: str, ok: bool, rounds: int, hours_ago: float = 48.0,
         updated_hours_ago: float = 1.0) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "schema": "engel_goal_v1", "slug": slug, "goal": slug.replace("_", " "),
        "status": status, "ok": ok, "rounds_spent": rounds,
        "created_at_utc": (now - timedelta(hours=hours_ago)).isoformat(),
        "updated_at_utc": (now - timedelta(hours=updated_hours_ago)).isoformat(),
    }


with tempfile.TemporaryDirectory() as td:
    gdir = Path(td)
    gp.GOAL_DIR = gdir
    gp.PLAN_PATH = gdir / "ENGEL_GOAL_PLAN.json"
    mojibake_times = (
        "NVIDIA "
        + "\u00d7".encode("utf-8").decode("cp1252").encode("utf-8").decode("cp1252")
        + " Fair"
    )
    titled = goal("mojibake_goal", "done", True, 1)
    titled["goal"] = mojibake_times
    for record in (
        goal("finished_goal", "done", True, 12),
        goal("running_goal", "running", False, 10),
        goal("stalled_goal", "no planner available", False, 0),
        goal("fresh_goal", "running", False, 0),
        goal("claims_done_goal", "done", False, 25),  # done WITHOUT ok -- not a success
        goal("rejected_goal", "draft rejected: not Engelscript", False, 4),
        goal("invalid_goal", "plan invalid", False, 12),
        titled,
    ):
        (gdir / f"{record['slug']}.json").write_text(json.dumps(record), encoding="utf-8")

    plan = gp.plan(gdir)
    goals = plan["goals"]

    check("done_only_from_terminal_success",
          goals["finished_goal"]["progress_percent"] == 100
          and goals["finished_goal"]["progress_state"] == "done",
          "status=done + ok=true reads 100%")
    check("done_claim_without_ok_never_100",
          goals["claims_done_goal"]["progress_percent"] < 100,
          f"got {goals['claims_done_goal']['progress_percent']}% "
          "(a done status without ok=true is not a success)")
    check("estimate_capped_below_100",
          0 < goals["running_goal"]["progress_percent"] <= 95
          and "rounds" in goals["running_goal"]["progress_basis"],
          f"{goals['running_goal']['progress_percent']}% with basis stated")
    check("stalled_reads_zero",
          goals["stalled_goal"]["progress_state"] == "No planner"
          and goals["stalled_goal"]["progress_percent"] == 0)
    check("unprojectable_is_honestly_empty",
          goals["fresh_goal"]["projected_finish_date"] == ""
          and goals["fresh_goal"]["projected_finish_projectable"] is False,
          "no cadence -> no invented date")
    check("cadence_projection_is_a_real_date",
          len(goals["running_goal"]["projected_finish_date"]) == 10
          and goals["running_goal"]["projected_finish_projectable"] is True,
          goals["running_goal"]["projected_finish_basis"])

    gp.set_schedule("running_goal", start="2026-09-01", due="2026-09-20", goal_dir=gdir)
    replanned = gp.plan(gdir)["goals"]["running_goal"]
    check("operator_dates_survive_replan",
          replanned["operator_start_date"] == "2026-09-01"
          and replanned["operator_due_date"] == "2026-09-20")
    try:
        gp.set_schedule("running_goal", start="not-a-date", goal_dir=gdir)
        check("bad_date_rejected", False, "accepted a malformed date")
    except ValueError:
        check("bad_date_rejected", True)

    month = gp.calendar_view(2026, 9, gdir)
    dated = [d for d in month["days"]]
    check("calendar_events_sit_on_real_dates_only",
          "2026-09-01" in dated and "2026-09-20" in dated
          and all(d.startswith("2026-09") for d in dated),
          f"days: {dated}")

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    gp.set_schedule("running_goal", start=yesterday, goal_dir=gdir)
    ticked = gp.tick(gdir, launch=False)
    check("tick_refuses_specless_start",
          not ticked["due"]
          and any("launch spec" in s["reason"] for s in ticked["skipped"]),
          "a start date without agent+checks cannot launch")
    gp.set_schedule("running_goal", agent="planner-probe",
                    checks_json='[{"kind": "file_exists", "target": "reports/x.json"}]',
                    goal_dir=gdir)
    ticked2 = gp.tick(gdir, launch=False)
    check("tick_marks_fully_specified_goal_due",
          ticked2["due"] == ["running_goal"])
    check("done_goal_never_ticks",
          all(s != "finished_goal" for s in ticked2["due"]))
    check("rejected_draft_is_not_a_live_meter",
          goals["rejected_goal"]["progress_state"] == "Rejected"
          and goals["rejected_goal"]["progress_percent"] == 16
          and goals["rejected_goal"]["progress_state"] != "in_progress"
          and goals["rejected_goal"]["projected_finish_projectable"] is False
          and goals["rejected_goal"]["projected_finish_basis"] == "",
          goals["rejected_goal"]["progress_basis"])
    check("invalid_plan_is_not_a_live_meter",
          goals["invalid_goal"]["progress_state"] == "Invalid plan"
          and goals["invalid_goal"]["progress_percent"] == 48
          and goals["invalid_goal"]["projected_finish_date"] == "")
    check("mojibake_title_repairs_on_the_plan",
          goals["mojibake_goal"]["goal"] == "NVIDIA \u00d7 Fair",
          goals["mojibake_goal"]["goal"])
    burst = gp.GoalRecord(
        slug="burst",
        goal="burst",
        status="running",
        ok=False,
        rounds_spent=4,
        created_at=datetime.now(timezone.utc) - timedelta(seconds=8),
        updated_at=datetime.now(timezone.utc),
        path=Path("burst.json"),
    )
    burst_projection = gp.project_finish(burst)
    check("burst_cadence_does_not_invent_a_date",
          burst_projection["projectable"] is False
          and burst_projection["date"] == "",
          burst_projection["basis"])
    check("plain_title_is_not_rewritten",
          gp.repair_mojibake("Check Storage on server") == "Check Storage on server")
    finished = gp.finish_goal(
        "rejected_goal", "the address answers on the phone", goal_dir=gdir)
    finished_plan = gp.plan(gdir)["goals"]["rejected_goal"]
    check("josh_finish_completes_the_goal",
          finished["ok"] is True
          and finished_plan["progress_state"] == "done"
          and finished_plan["progress_percent"] == 100
          and finished_plan["finished_by"] == "josh"
          and "address answers" in finished_plan["progress_basis"])
    try:
        gp.finish_goal("invalid_goal", "  ", goal_dir=gdir)
        check("blank_finish_is_refused", False, "accepted an empty finish note")
    except ValueError:
        check("blank_finish_is_refused", True)
    talked = gp.record_turn("invalid_goal", "Look at the server disk next", goal_dir=gdir)
    talked_plan = gp.plan(gdir)["goals"]["invalid_goal"]
    check("a_talk_turn_does_not_finish",
          talked["ok"] is False
          and talked_plan["progress_state"] == "with Josh"
          and talked_plan["progress_percent"] == 0
          and talked_plan["interaction"][-1]["text"] == "Look at the server disk next")

failed = sum(1 for c in checks if c["status"] != "PASS")
print(json.dumps({"schema": "engel_goal_planner_verifier_v1",
                  "status": "FAIL" if failed else "PASS",
                  "passed": len(checks) - failed, "total": len(checks),
                  "checks": checks}, indent=2))
raise SystemExit(1 if failed else 0)
