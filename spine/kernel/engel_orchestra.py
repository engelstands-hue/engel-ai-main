"""Engel Orchestra -- the Conductor's parallel section (v1).

Spec: docs/ENGEL_ORCHESTRA_DESIGN.md. Verifier: tools/verify_engel_orchestra.py.

The Conductor closed Engel's agent loop -- goal -> plan -> run -> observe ->
repair -> ledger -- but strictly serially, and its own design doc names the
remaining gap: "wiring engel_subagents.fan_out into conducted plans is a v2
candidate, after the loop itself has receipts behind it." The loop has receipts
behind it now, and the fan-out was still an island with zero production
callers. The Orchestra is the join: a multi-part goal splits into bounded
parallel Conductor lanes -- each lane a full conduct with its own receipt --
and the lane observations merge into one receipted, ledgered outcome.

Contract culture (same as Governor / EngelScript / Conductor):

* **No model calls in this module.** Decomposition and synthesis prompts are
  deterministic string builders; the LLM call is INJECTED (``draft_fn``) by
  the caller that owns a model lane. Without it the Orchestra still
  orchestrates explicit ``|``-separated parts -- degraded, never broken.
* **Bounded by construction.** At most ``MAX_LANES`` lanes; each lane inherits
  every Conductor bound unchanged; lane drafts share ONE lock (the local
  model allows one in-flight call); decomposition and synthesis are one
  injected call each.
* **Read-only by construction.** There is no ``allow_actions`` parameter.
  Parallel granted-action lanes are an explicit non-goal; action runs stay
  with the serial Conductor and its operator-grants gate.
* **Receipted + persistent.** Every orchestration writes
  reports/engel_orchestra/ORCHESTRA_*.json linking each lane's conduct
  receipt, and upserts a parent record (kind ``orchestra``) in
  memory/engel_goals/ next to the per-lane records the Conductor writes.
"""
from __future__ import annotations

import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

RECEIPT_DIR = ROOT / "reports" / "engel_orchestra"

MAX_LANES = 4
MAX_LEDGER_CONDUCTS = 10
MAX_LEDGER_PROBLEMS = 5
LANE_PROBLEM_CLIP = 4
OUTPUT_CLIP = 8
RESPONSE_CLIP = 400
SYNTHESIS_CLIP = 800

DraftFn = Callable[[str], str]

_LINE_NOISE_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Split -- the decomposition ladder. Deterministic first: the operator's own
# `|` split always wins; the injected drafter is only asked when there is no
# explicit split; with neither, the goal stays a single Conductor lane.
# ---------------------------------------------------------------------------
def decompose_prompt(goal: str) -> str:
    """One injected call turns a compound goal into lanes. The capability
    phrasebook is folded in so the split follows Engel's REAL parts, and the
    wording stays clear of the chat action lane's build vocabulary (the same
    live lesson as the script/conductor draft flows, 2026-07-31)."""
    goal_text = " ".join(str(goal or "").split())
    phrasebook = ""
    try:
        from engel_capability_index import capability_phrasebook_text

        phrasebook = capability_phrasebook_text(goal_text, limit=6)
    except Exception:  # noqa: BLE001 -- retrieval is best-effort, never a dependency
        phrasebook = ""
    parts = [
        "Split this goal into independent sub-goals that can each be checked "
        "on its own. Reply with ONLY the sub-goals, one per line: no numbering, "
        f"no explanation, at most {MAX_LANES} lines. Each line must be a "
        "self-contained instruction.",
    ]
    if phrasebook:
        parts += ["", phrasebook]
    parts += ["", "Goal: " + goal_text]
    return "\n".join(parts)


def parse_subgoals(reply: str) -> list[str]:
    """Usable sub-goal lines from a decomposition reply: bullets/numbering
    stripped, blanks and fragments dropped, order kept, clipped to MAX_LANES."""
    lanes: list[str] = []
    seen: set[str] = set()
    for raw in str(reply or "").splitlines():
        line = _LINE_NOISE_RE.sub("", raw).strip().strip("\"'")
        if len(line.split()) < 2:
            continue
        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        lanes.append(line)
        if len(lanes) >= MAX_LANES:
            break
    return lanes


def split_goal(
    goal: str, draft_fn: Optional[DraftFn] = None
) -> tuple[list[str], str]:
    """(subgoals, origin). Explicit `|` split > drafted split > single lane."""
    goal_text = str(goal or "").strip()
    if "|" in goal_text:
        parts = [part.strip() for part in goal_text.split("|") if part.strip()]
        if len(parts) >= 2:
            return parts, "operator split"
        goal_text = parts[0] if parts else ""
    if draft_fn is not None:
        reply = _call_draft(draft_fn, decompose_prompt(goal_text))
        lanes = parse_subgoals(reply)
        if len(lanes) >= 2:
            return lanes, "drafted split"
    return ([goal_text] if goal_text else []), "single lane"


def synthesis_prompt(goal: str, lane_summaries: list[str]) -> str:
    parts = [
        "These lane reports each answered part of the goal. Combine them into "
        "one short, plain answer to the goal. Reply with ONLY the answer.",
        "",
    ]
    parts.extend(lane_summaries)
    parts += ["", "Goal: " + " ".join(str(goal or "").split())]
    return "\n".join(parts)


def _call_draft(draft_fn: DraftFn, prompt: str) -> str:
    try:
        return str(draft_fn(prompt) or "")
    except Exception:  # noqa: BLE001 -- a drafter crash is a degraded turn, not a lost one
        return ""


def _serialized(draft_fn: Optional[DraftFn]) -> Optional[DraftFn]:
    """One model in flight: every lane's draft/repair call takes this lock, so
    route I/O overlaps while model calls queue -- the constraint that made
    fan-out a Conductor v1 non-goal, honored rather than removed."""
    if draft_fn is None:
        return None
    lock = threading.Lock()

    def locked(prompt: str) -> str:
        with lock:
            return draft_fn(prompt)

    return locked


# ---------------------------------------------------------------------------
# Lanes -- each lane is one full Conductor conduct, never anything less.
# ---------------------------------------------------------------------------
def _lane_record(index: int, subgoal: str, conduct_receipt: dict[str, Any]) -> dict[str, Any]:
    problems: list[str] = []
    executed = 0
    blocked = 0
    for round_rec in conduct_receipt.get("rounds", []):
        problems.extend(str(p) for p in round_rec.get("validate_errors", []) or [])
        observation = round_rec.get("observation", {}) or {}
        problems.extend(str(p) for p in observation.get("problems", []) or [])
        executed = int(observation.get("executed_routes", executed) or 0)
        blocked = int(observation.get("blocked_routes", blocked) or 0)
    status = str(conduct_receipt.get("status", ""))
    if status and status not in ("done",) and not problems:
        problems.append(status)
    output: list[str] = []
    for round_rec in conduct_receipt.get("rounds", []):
        output = [str(line)[:RESPONSE_CLIP] for line in round_rec.get("output", []) or []]
    return {
        "lane": index,
        "subgoal": subgoal,
        "slug": str(conduct_receipt.get("slug", "")),
        "status": status,
        "ok": bool(conduct_receipt.get("ok")),
        "rounds": len(conduct_receipt.get("rounds", [])),
        "executed_routes": executed,
        "blocked_routes": blocked,
        "problems": problems[-LANE_PROBLEM_CLIP:],
        "conduct_receipt": str(conduct_receipt.get("receipt_path", "")),
        "output": output[:OUTPUT_CLIP],
    }


def _conduct_lane(
    index: int,
    subgoal: str,
    draft_fn: Optional[DraftFn],
    router,
    intent_fn,
    write_receipt: bool,
) -> dict[str, Any]:
    import engel_conductor as ec

    try:
        receipt = ec.conduct(
            subgoal,
            draft_fn=draft_fn,
            allow_actions=False,
            router=router,
            intent_fn=intent_fn,
            write_receipt=write_receipt,
        )
    except Exception as exc:  # noqa: BLE001 -- one lane crashing must not sink the section
        receipt = {
            "slug": "",
            "status": f"lane crashed: {type(exc).__name__}: {str(exc)[:160]}",
            "ok": False,
            "rounds": [],
        }
    return _lane_record(index, subgoal, receipt)


# ---------------------------------------------------------------------------
# Governor -- the fan-out verdict is recorded per orchestration; read-only
# orchestration proceeds when the Governor is unavailable (the same
# route-class asymmetry the Conductor uses for read-only runs).
# ---------------------------------------------------------------------------
def _govern_fan_out(lanes: int) -> Optional[dict[str, Any]]:
    try:
        from engel_governor import govern

        return govern(
            "allow",
            {
                "gate": "orchestra_fan_out",
                "gate_result": 1 <= lanes <= MAX_LANES,
                "lanes": lanes,
                "read_only": True,
            },
        )
    except Exception:  # noqa: BLE001 -- absence is recorded, read-only proceeds
        return None


# ---------------------------------------------------------------------------
# The section.
# ---------------------------------------------------------------------------
def orchestrate(
    goal: str,
    *,
    draft_fn: Optional[DraftFn] = None,
    router=None,
    intent_fn=None,
    write_receipt: bool = True,
    max_lanes: int = MAX_LANES,
    synthesize: bool = True,
) -> dict[str, Any]:
    """Fan a goal into bounded parallel read-only Conductor lanes and merge
    the observations. Returns the orchestra receipt."""
    import engel_conductor as ec

    goal_text = " ".join(str(goal or "").split())
    receipt: dict[str, Any] = {
        "schema": "engel_orchestra_run_v1",
        "started_at_utc": _now(),
        "goal": goal_text,
        "slug": ec.goal_slug(goal_text),
        "mode": "read_only",
        "split_origin": "",
        "lanes": [],
        "status": "",
        "ok": False,
    }
    if not goal_text:
        receipt["status"] = "empty goal"
        return _finish(receipt, write_receipt, ledger=False)

    subgoals, origin = split_goal(goal_text, draft_fn)
    receipt["split_origin"] = origin
    bound = max(1, min(int(max_lanes), MAX_LANES))
    if len(subgoals) > bound:
        # An honest refusal, never a silent clip: the operator wrote the parts
        # and must see which ones would have been dropped.
        receipt["status"] = (
            f"too many lanes ({len(subgoals)}; the Orchestra conducts at most "
            f"{bound}) -- split the goal, or drop a part"
        )
        receipt["subgoals"] = subgoals
        return _finish(receipt, write_receipt, ledger=False)
    if not subgoals:
        receipt["status"] = "empty goal"
        return _finish(receipt, write_receipt, ledger=False)

    receipt["fan_out_verdict"] = _govern_fan_out(len(subgoals))

    locked_draft = _serialized(draft_fn)
    if len(subgoals) == 1:
        receipt["mode"] = "single_lane"
        lanes = [
            _conduct_lane(1, subgoals[0], locked_draft, router, intent_fn, write_receipt)
        ]
    else:
        with ThreadPoolExecutor(max_workers=min(bound, len(subgoals))) as pool:
            futures = [
                pool.submit(
                    _conduct_lane, index, subgoal, locked_draft, router,
                    intent_fn, write_receipt,
                )
                for index, subgoal in enumerate(subgoals, start=1)
            ]
            lanes = [future.result() for future in futures]
    receipt["lanes"] = lanes

    done = sum(1 for lane in lanes if lane["ok"])
    receipt["executed_routes"] = sum(lane["executed_routes"] for lane in lanes)
    receipt["blocked_routes"] = sum(lane["blocked_routes"] for lane in lanes)
    problems = [
        f"lane {lane['lane']} ({lane['slug'] or lane['subgoal'][:40]}): {problem}"
        for lane in lanes
        for problem in lane["problems"]
        if not lane["ok"]
    ]
    receipt["problems"] = problems
    receipt["ok"] = bool(lanes) and done == len(lanes)
    receipt["status"] = (
        "done" if receipt["ok"] else f"{done}/{len(lanes)} lanes done -- needs attention"
    )

    if synthesize and draft_fn is not None:
        summaries = [
            f"[lane {lane['lane']}: {lane['subgoal'][:80]}] "
            + " / ".join(lane["output"][:3] or [lane["status"]])
            for lane in lanes
        ]
        if summaries:
            synthesis = _call_draft(
                locked_draft or draft_fn, synthesis_prompt(goal_text, summaries)
            ).strip()
            if synthesis:
                receipt["synthesis"] = synthesis[:SYNTHESIS_CLIP]

    return _finish(receipt, write_receipt)


# ---------------------------------------------------------------------------
# Ledger -- the parent record sits next to the per-lane goal records the
# Conductor already upserts, kind-marked so the story renders honestly.
# ---------------------------------------------------------------------------
def _upsert_parent(receipt: dict[str, Any]) -> str:
    import engel_conductor as ec

    slug = str(receipt.get("slug", ""))
    if not slug:
        return ""
    record = ec.load_goal(slug) or {
        "schema": "engel_goal_v1",
        "slug": slug,
        "goal": receipt.get("goal", ""),
        "created_at_utc": _now(),
        "rounds_spent": 0,
        "conducts": [],
    }
    record["kind"] = "orchestra"
    record["goal"] = receipt.get("goal", "")
    record["status"] = receipt.get("status", "")
    record["ok"] = bool(receipt.get("ok"))
    try:
        prior_rounds = int(record.get("rounds_spent", 0))
    except (TypeError, ValueError):
        prior_rounds = 0
    record["rounds_spent"] = prior_rounds + sum(
        int(lane.get("rounds", 0) or 0) for lane in receipt.get("lanes", [])
    )
    raw_conducts = record.get("conducts")
    conducts = [str(p) for p in raw_conducts if p] if isinstance(raw_conducts, list) else []
    path = str(receipt.get("receipt_path", ""))
    if path:
        conducts.append(path)
    record["conducts"] = conducts[-MAX_LEDGER_CONDUCTS:]
    record["lane_slugs"] = [
        str(lane.get("slug", "")) for lane in receipt.get("lanes", [])
    ]
    record["last_problems"] = [
        str(p) for p in receipt.get("problems", [])
    ][-MAX_LEDGER_PROBLEMS:]
    record["updated_at_utc"] = _now()
    try:
        ec.GOAL_DIR.mkdir(parents=True, exist_ok=True)
        goal_path = ec.GOAL_DIR / f"{slug}.json"
        goal_path.write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return str(goal_path)
    except OSError:
        return ""


def _finish(
    receipt: dict[str, Any], write: bool, *, ledger: bool = True
) -> dict[str, Any]:
    receipt["finished_at_utc"] = _now()
    if write:
        try:
            RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            path = RECEIPT_DIR / f"ORCHESTRA_{stamp}.json"
            path.write_text(
                json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            receipt["receipt_path"] = str(path)
        except OSError as exc:
            receipt["receipt_write_error"] = str(exc)
    if ledger:
        receipt["ledger_path"] = _upsert_parent(receipt)
    return receipt


# ---------------------------------------------------------------------------
# Route render functions (engel.orchestra.*).
# ---------------------------------------------------------------------------
_ALIAS_PREFIXES = (
    "orchestrate engel goal",
    "engel orchestrate",
    "engel orchestra run",
    "engel orchestra",
)


def _payload(text: str) -> str:
    low = str(text or "").strip()
    for prefix in _ALIAS_PREFIXES:
        if low.casefold().startswith(prefix):
            return low[len(prefix):].strip()
    return ""


def render_orchestra_docs(text: str = "") -> str:
    return (
        "Engel Orchestra -- the Conductor's parallel section "
        "(docs/ENGEL_ORCHESTRA_DESIGN.md).\n"
        "A multi-part goal fans into bounded parallel Conductor lanes -- each\n"
        "lane a full conduct (plan, validate, run read-only, observe, repair\n"
        f"once) -- and the observations merge into one receipt. At most "
        f"{MAX_LANES} lanes;\nmodel calls stay one-in-flight; actions stay with "
        "the serial Conductor.\n\n"
        "Phrases:\n"
        "  engel orchestra <a> | <b> | <c>   fan explicit parts into lanes\n"
        "  engel orchestra <goal>            in the main chat, the local model\n"
        "                                    splits the goal into lanes first\n"
        "  engel orchestra status            recent orchestrations\n"
        "  engel orchestra docs              this reference\n\n"
        "Each lane's goal lands in the ledger, so a failed part re-enters with\n"
        "'continue engel goal <lane slug>'. Receipts: reports/engel_orchestra/."
    )


def render_orchestra_status(text: str = "") -> str:
    if not RECEIPT_DIR.is_dir():
        return (
            "Engel Orchestra: no orchestrations yet. Start one with "
            "'engel orchestra <a> | <b> | <c>'; receipts land in "
            "reports/engel_orchestra/."
        )
    paths = sorted(RECEIPT_DIR.glob("ORCHESTRA_*.json"), reverse=True)[:8]
    if not paths:
        return (
            "Engel Orchestra: no orchestrations yet. Start one with "
            "'engel orchestra <a> | <b> | <c>'."
        )
    lines = [f"Engel Orchestra -- recent orchestrations (newest first, {len(paths)} shown):"]
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        goal_line = " ".join(str(data.get("goal", "")).split())[:90]
        lines.append(
            f"  - [{data.get('status', '?')}] {len(data.get('lanes', []))} lane(s), "
            f"{data.get('executed_routes', 0)} route(s) -- {goal_line}"
        )
        lines.append(f"      receipt: {path.name}")
    return "\n".join(lines)


def render_orchestrate_result(receipt: dict[str, Any]) -> str:
    lines = [
        f"Engel Orchestra -- goal: {receipt.get('goal', '')}",
        f"Status: {receipt.get('status', '?')}  (split: {receipt.get('split_origin', '?')})",
    ]
    for lane in receipt.get("lanes", []):
        lines.append(
            f"Lane {lane.get('lane')}: {str(lane.get('subgoal', ''))[:90]}"
            f" -- [{lane.get('status', '?')}] "
            f"{lane.get('executed_routes', 0)} route(s), "
            f"{lane.get('blocked_routes', 0)} blocked"
        )
        for line in lane.get("output", [])[:3]:
            lines.append(f"    {str(line)[:RESPONSE_CLIP]}")
        for problem in lane.get("problems", [])[:2]:
            lines.append(f"    problem: {str(problem)[:200]}")
        if not lane.get("ok") and lane.get("slug"):
            lines.append(f"    re-enter with: continue engel goal {lane['slug']}")
    if receipt.get("synthesis"):
        lines.append("Combined answer:")
        lines.append(f"  {receipt['synthesis']}")
    if receipt.get("subgoals") and not receipt.get("lanes"):
        lines.append("Parts seen:")
        lines.extend(f"  - {str(part)[:90]}" for part in receipt["subgoals"])
    if receipt.get("receipt_path"):
        lines.append(f"Receipt: {receipt['receipt_path']}")
    return "\n".join(lines)


def render_orchestrate(text: str = "") -> str:
    payload = _payload(text)
    if not payload:
        return (
            "Usage: engel orchestra <part> | <part> | <part>\n"
            "       engel orchestra <saved plan> | <saved plan>\n"
            "The route surface orchestrates explicit parts deterministically\n"
            "(read-only, no drafting). In the main chat the same phrase also\n"
            "SPLITS a plain goal into lanes with the local model lane.\n"
            + render_orchestra_status()
        )
    return render_orchestrate_result(orchestrate(payload))
