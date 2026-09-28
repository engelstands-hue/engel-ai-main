"""Engel Conductor -- the loop that closes (v1).

Spec: docs/ENGEL_CONDUCTOR_DESIGN.md. Verifier: tools/verify_engel_conductor.py.

Engel had every organ of an agent and no circulatory system: a planner that
ends by printing "Drafts never run automatically.", an executor whose
``allow_actions`` flag was recorded and ignored, a Governor whose ``allow``
class had zero production callers, receipts nothing ever read back, and no
goal state that survived a chat turn. The Conductor is the component
docs/ENGEL_SCRIPT_LANGUAGE.md section 5 said must exist outside the language:
the thing that decides to run a plan -- and then reads what happened.

The loop: goal -> retrieve -> plan -> validate -> run -> observe -> repair ->
ledger. Same contract culture as the Governor and EngelScript:

* **No model calls in this module.** The draft/repair LLM call is INJECTED
  (``draft_fn``) by the caller that owns a model lane (the chat worker). With
  no ``draft_fn`` the Conductor still conducts saved plans -- degraded, never
  broken, and fully deterministic.
* **Bounded by construction.** At most ``MAX_ROUNDS`` plan-run rounds per
  conduct; each repair is granted through ``govern("escalate", ...)`` -- one
  escalation, spent thereafter. Script caps are inherited unchanged.
* **Receipted.** Every conduct writes reports/engel_conductor/ with each
  round's plan sha256, run receipt path, observation, and Governor verdicts.
* **Persistent.** Every conduct upserts memory/engel_goals/<slug>.json, so a
  goal outlives the process and ``continue engel goal <slug>`` re-enters it
  with its history folded into the repair prompt.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

GOAL_DIR = ROOT / "memory" / "engel_goals"
RECEIPT_DIR = ROOT / "reports" / "engel_conductor"

MAX_ROUNDS = 2
MAX_LEDGER_CONDUCTS = 10
MAX_LEDGER_PROBLEMS = 5
SOURCE_CLIP = 2000
RESPONSE_CLIP = 400

_SLUG_RE = re.compile(r"[^a-z0-9]+")

DraftFn = Callable[[str], str]

_STATEMENT_HEADS = frozenset({"plan", "let", "ask", "route", "say", "if"})

# Timeout-humanized / NL prose markers observed live in Conductor drafts
# (e.g. CONDUCT_20260906T114113318193Z): must never be applied as plans.
_NON_SCRIPT_MARKERS = (
    "i stopped this turn",
    "fallback failed",
    "missing-input safety",
    "please retry the request",
    "every available fallback",
    "not positive training",
    "chatgpt/openai",
)


def _first_content_head(source: str) -> str:
    for line in str(source or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return stripped.split(None, 1)[0].lower()
    return ""


def _engelscript_shaped(source: str) -> bool:
    """True iff every non-comment content line opens with an EngelScript verb
    and at least one such line exists. Pure NL / timeout humanize fails."""
    saw = False
    for line in str(source or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        head = stripped.split(None, 1)[0].lower()
        if head not in _STATEMENT_HEADS:
            return False
        saw = True
    return saw


def _non_engelscript_reject_problems(source: str) -> list[str]:
    """Structured reject reasons when a draft is not valid EngelScript shape.

    Used BEFORE parse/repair/execute so timeout-humanized prose
    (unknown statement 'chatgpt/openai' / 'i' / "i'm" / 'the' / 'engel')
    never enters plan apply or execute_routes.
    """
    text = str(source or "").strip()
    if not text:
        return ["draft rejected: empty script"]
    if _engelscript_shaped(text):
        return []
    head = _first_content_head(text) or "(empty)"
    low = text.casefold()
    markers = [m for m in _NON_SCRIPT_MARKERS if m in low]
    problems = [
        "draft rejected: not Engelscript",
        (
            f"first token {head!r} is not an EngelScript statement head "
            f"(plan/let/ask/route/say/if)"
        ),
    ]
    if markers:
        problems.append("timeout/humanize or NL markers: " + ", ".join(markers[:4]))
    return problems



def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_SLUG_DIGEST_RE = re.compile(r"^(.*)_([0-9a-f]{8})$")


def goal_slug(goal: str) -> str:
    """Stable ledger key for a goal. Idempotent on its own output, so a slug
    the operator copies from 'engel goal status' round-trips unchanged.

    A short digest of the FULL text is appended because plain truncation
    collided: two different long goals ("...report the results for alpha" and
    "...for beta") produced the same 60-char key, so conducting the second
    silently overwrote the first's ledger record and its recorded problems."""
    text = " ".join(str(goal or "").split())
    slug = _SLUG_RE.sub("_", text.casefold()).strip("_")
    if not slug:
        return ""
    if _SLUG_DIGEST_RE.match(slug) and len(slug) <= 61:
        return slug  # already a slug we produced; keep round-tripping stable
    digest = hashlib.sha256(text.casefold().encode("utf-8")).hexdigest()[:8]
    return f"{slug[:52].rstrip('_')}_{digest}"


# ---------------------------------------------------------------------------
# Goal ledger -- the state that survives a turn.
# ---------------------------------------------------------------------------
def load_goal(slug: str) -> Optional[dict[str, Any]]:
    clean = goal_slug(slug)
    if not clean:
        return None
    path = GOAL_DIR / f"{clean}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def list_goals() -> list[dict[str, Any]]:
    if not GOAL_DIR.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in GOAL_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("schema") == "engel_goal_v1":
            records.append(data)
    records.sort(key=lambda rec: str(rec.get("updated_at_utc", "")), reverse=True)
    return records


def _upsert_goal(slug: str, goal_text: str, receipt: dict[str, Any]) -> str:
    record = load_goal(slug) or {
        "schema": "engel_goal_v1",
        "slug": slug,
        "goal": goal_text,
        "created_at_utc": _now(),
        "rounds_spent": 0,
        "conducts": [],
    }
    record["goal"] = goal_text
    record["status"] = receipt.get("status", "")
    record["ok"] = bool(receipt.get("ok"))
    # A hand-edited or foreign ledger file must degrade to a fresh record, the
    # way load_goal already does -- not raise ValueError out of conduct() and
    # leave that slug permanently unusable from the chat surface.
    try:
        prior_rounds = int(record.get("rounds_spent", 0))
    except (TypeError, ValueError):
        prior_rounds = 0
    record["rounds_spent"] = prior_rounds + len(receipt.get("rounds", []))
    raw_conducts = record.get("conducts")
    conducts = [str(p) for p in raw_conducts if p] if isinstance(raw_conducts, list) else []
    path = str(receipt.get("receipt_path", ""))
    if path:
        conducts.append(path)
    record["conducts"] = conducts[-MAX_LEDGER_CONDUCTS:]
    problems: list[str] = []
    for round_rec in receipt.get("rounds", []):
        problems.extend(round_rec.get("validate_errors", []))
        problems.extend(round_rec.get("observation", {}).get("problems", []))
    record["last_problems"] = problems[-MAX_LEDGER_PROBLEMS:]
    record["updated_at_utc"] = _now()
    try:
        GOAL_DIR.mkdir(parents=True, exist_ok=True)
        goal_path = GOAL_DIR / f"{slug}.json"
        goal_path.write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        # (2026-08-10, operator: Engel adds its own goals to the calendar.) Replan
        # immediately so a goal Engel was just asked to work on appears in the Goals
        # window and on the month planner without waiting for the daily tick.
        # Best-effort: the ledger write above is the truth; a planner hiccup must
        # never fail the conduct.
        try:
            import sys as _sys

            tools_dir = str(Path(__file__).resolve().parent / "tools")
            if tools_dir not in _sys.path:
                _sys.path.insert(0, tools_dir)
            import engel_goal_planner as _planner

            _planner.plan()
        except Exception:  # noqa: BLE001 -- calendar visibility is advisory here
            pass
        return str(goal_path)
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Observation -- the read-back nothing else in the system performed.
# ---------------------------------------------------------------------------
def observe_run(run_receipt: dict[str, Any]) -> dict[str, Any]:
    """Turn a script run receipt into problems a repair round can act on."""
    problems: list[str] = []
    blocked_phrases: list[str] = []
    steps = run_receipt.get("steps", []) if isinstance(run_receipt, dict) else []
    for step in steps:
        if step.get("blocked"):
            phrase = str(step.get("phrase", ""))
            blocked_phrases.append(phrase)
            problems.append(
                f"line {step.get('line')}: route step was blocked -- "
                f"{step.get('reason', 'no reason recorded')} (phrase: {phrase!r})"
            )
        elif step.get("kind") in ("route", "ask_route") and step.get("ok") is False:
            problems.append(
                f"line {step.get('line')}: route ran but reported failure "
                f"(phrase: {step.get('phrase', '')!r})"
            )
    for error in run_receipt.get("errors", []) if isinstance(run_receipt, dict) else []:
        problems.append(f"run error: {error}")
    executed = sum(
        1
        for step in steps
        if step.get("kind") in ("route", "ask_route") and not step.get("blocked")
    )
    if not problems and not executed:
        # A plan that ran no routes proved nothing. Small local models emit
        # exactly this when they narrate instead of planning (`plan "check the
        # fleet"` + `say "the fleet is healthy"`), and reporting it as done
        # meant Engel claimed a goal was achieved having done nothing -- with
        # the repair round that exists to catch it never firing.
        problems.append(
            "the plan executed no routes -- nothing was checked, so nothing is proven"
        )
    return {
        "ok": bool(run_receipt.get("ok")) and not problems,
        "problems": problems,
        "blocked_phrases": blocked_phrases,
        "executed_routes": executed,
        "blocked_routes": len(blocked_phrases),
    }


# ---------------------------------------------------------------------------
# Repair prompt -- deterministic string builder; the model call stays with the
# caller, exactly like engel_script.draft_prompt.
# ---------------------------------------------------------------------------
def _alternatives_for(goal: str) -> str:
    try:
        from engel_capability_index import capability_phrasebook_text

        return capability_phrasebook_text(str(goal or ""), limit=6)
    except Exception:  # noqa: BLE001 -- retrieval is best-effort, never a dependency
        return ""


def repair_prompt(
    goal: str, source: str, problems: list[str], alternatives: str = ""
) -> str:
    from engel_script import GRAMMAR_CARD

    parts = [
        "The previous EngelScript plan for this goal did not succeed. Compose a "
        "corrected plan. Reply with ONLY the EngelScript text: no explanation, "
        "no code fences.",
        "",
        GRAMMAR_CARD,
        "",
        "Previous plan:",
        str(source or "").strip(),
        "",
        "What went wrong:",
    ]
    parts.extend(f"- {problem}" for problem in problems[:8])
    if alternatives:
        parts += ["", alternatives]
    parts += ["", "Goal: " + " ".join(str(goal or "").split())]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Governor -- verdicts are recorded per round; read-only runs proceed when the
# Governor is unavailable (route-class asymmetry), granted-action runs do not.
# ---------------------------------------------------------------------------
def _govern(decision: str, features: dict[str, Any]) -> Optional[dict[str, Any]]:
    try:
        from engel_governor import govern

        return govern(decision, features)
    except Exception:  # noqa: BLE001 -- absence is handled per decision class
        return None


# ---------------------------------------------------------------------------
# The loop.
# ---------------------------------------------------------------------------
def conduct(
    goal: str,
    *,
    draft_fn: Optional[DraftFn] = None,
    allow_actions: bool = False,
    router=None,
    intent_fn=None,
    write_receipt: bool = True,
    max_rounds: int = MAX_ROUNDS,
    history: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Drive one goal as far as the bounds permit. Returns the conduct receipt.

    ``allow_actions`` reaches ``execute_engel_script`` unchanged; the per-step
    grant (operator grants file + Governor allow, fail-closed) lives in
    engel_script so the phrase surface and the Conductor share one gate."""
    import engel_script as es

    goal_text = " ".join(str(goal or "").split())
    receipt: dict[str, Any] = {
        "schema": "engel_conductor_run_v1",
        "started_at_utc": _now(),
        "goal": goal_text,
        "slug": goal_slug(goal_text),
        "mode": "granted_actions" if allow_actions else "read_only",
        "rounds": [],
        "status": "",
        "ok": False,
    }
    if not goal_text:
        receipt["status"] = "empty goal"
        return _finish(receipt, write_receipt, ledger=False)

    suggestions = _alternatives_for(goal_text)

    # PLAN: a goal that names a saved plan conducts it directly; otherwise the
    # injected drafter composes one; otherwise be honest about having neither.
    source = es.load_plan(goal_text)
    origin = f"saved plan '{goal_text.casefold()}'" if source is not None else ""
    if source is None:
        saved_by_slug = es.load_plan(receipt["slug"])
        if saved_by_slug is not None:
            source, origin = saved_by_slug, f"saved plan '{receipt['slug']}'"
    if source is None and draft_fn is not None:
        prompt = (
            repair_prompt(goal_text, "", list(history), suggestions)
            if history
            else es.draft_prompt(goal_text)
        )
        source = es.extract_script_from_reply(_call_draft(draft_fn, prompt))
        origin = "drafted"
        if not source.strip():
            receipt["status"] = "draft produced nothing"
            return _finish(receipt, write_receipt)
    if source is None:
        receipt["status"] = "no planner available"
        receipt["suggestions"] = suggestions
        return _finish(receipt, write_receipt)

    repair_spent = False
    round_no = 0
    while round_no < max(1, int(max_rounds)):
        round_no += 1
        round_rec: dict[str, Any] = {
            "round": round_no,
            "origin": origin,
            "plan_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "source_clip": source[:SOURCE_CLIP],
        }
        receipt["rounds"].append(round_rec)

        # Reject non-EngelScript drafts BEFORE parse/repair/apply. Timeout-
        # humanized NL prose must not become a plan or call execute_routes.
        if "draft" in str(origin).casefold():
            reject_problems = _non_engelscript_reject_problems(source)
            if reject_problems:
                round_rec["validate_errors"] = reject_problems
                receipt["status"] = "draft rejected: not Engelscript"
                receipt["problems"] = list(reject_problems)
                break

        _statements, errors = es.parse_engel_script(source)
        if errors:
            round_rec["validate_errors"] = errors
            repaired = _try_repair(
                round_rec, goal_text, source, errors, suggestions,
                draft_fn, repair_spent, round_no, max_rounds,
            )
            if repaired is None:
                receipt["status"] = "plan invalid"
                break
            source, origin, repair_spent = repaired, "repaired draft", True
            continue

        # The conduct-level allow verdict: deterministic gate, receipted. The
        # per-step grant inside engel_script decides each action individually.
        allow_verdict = _govern(
            "allow",
            {
                "gate": "conductor_run",
                "gate_result": (not allow_actions) or bool(es.load_action_grants()),
                "read_only": not allow_actions,
            },
        )
        round_rec["allow_verdict"] = allow_verdict
        if allow_actions and (
            allow_verdict is None or allow_verdict.get("outcome") != "allow"
        ):
            receipt["status"] = "action run denied"
            break

        run_receipt = es.execute_engel_script(
            source,
            allow_actions=allow_actions,
            router=router,
            intent_fn=intent_fn,
            write_receipt=write_receipt,
        )
        round_rec["run_receipt_path"] = run_receipt.get("receipt_path", "")
        round_rec["output"] = list(run_receipt.get("output", []))[:12]
        observation = observe_run(run_receipt)
        round_rec["observation"] = observation

        if observation["ok"]:
            receipt["status"] = "done"
            receipt["ok"] = True
            break

        repaired = _try_repair(
            round_rec, goal_text, source, observation["problems"], suggestions,
            draft_fn, repair_spent, round_no, max_rounds,
        )
        if repaired is None:
            receipt["status"] = "needs attention"
            break
        source, origin, repair_spent = repaired, "repaired draft", True

    if not receipt["status"]:
        receipt["status"] = "needs attention"
    return _finish(receipt, write_receipt)


def _call_draft(draft_fn: DraftFn, prompt: str) -> str:
    try:
        return str(draft_fn(prompt) or "")
    except Exception:  # noqa: BLE001 -- a drafter crash is a degraded turn, not a lost one
        return ""


def _try_repair(
    round_rec: dict[str, Any],
    goal_text: str,
    source: str,
    problems: list[str],
    suggestions: str,
    draft_fn: Optional[DraftFn],
    repair_spent: bool,
    round_no: int,
    max_rounds: int,
) -> Optional[str]:
    """One Governor-bounded repair: returns the new source, or None when no
    repair is possible (no drafter, rounds exhausted, escalation spent)."""
    if draft_fn is None or round_no >= max(1, int(max_rounds)):
        return None
    verdict = _govern(
        "escalate",
        {
            "already_escalated": repair_spent,
            "t0_uncertain": True,
            "high_stakes": True,
        },
    )
    round_rec["escalate_verdict"] = verdict
    if verdict is None or verdict.get("outcome") is not True:
        return None
    import engel_script as es

    repaired = es.extract_script_from_reply(
        _call_draft(draft_fn, repair_prompt(goal_text, source, problems, suggestions))
    )
    return repaired if repaired.strip() else None


def _finish(
    receipt: dict[str, Any], write: bool, *, ledger: bool = True
) -> dict[str, Any]:
    receipt["finished_at_utc"] = _now()
    if write:
        try:
            RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            path = RECEIPT_DIR / f"CONDUCT_{stamp}.json"
            path.write_text(
                json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            receipt["receipt_path"] = str(path)
        except OSError as exc:
            receipt["receipt_write_error"] = str(exc)
    if ledger and receipt.get("slug"):
        receipt["ledger_path"] = _upsert_goal(
            receipt["slug"], receipt["goal"], receipt
        )
    return receipt


def continue_goal(
    slug_text: str,
    *,
    draft_fn: Optional[DraftFn] = None,
    allow_actions: bool = False,
    router=None,
    intent_fn=None,
    write_receipt: bool = True,
) -> dict[str, Any]:
    """Re-enter a goal from the ledger, its recorded problems folded into the
    next draft so the model repairs instead of starting blind."""
    record = load_goal(slug_text)
    if record is None:
        known = ", ".join(rec.get("slug", "?") for rec in list_goals()[:8]) or "(none)"
        return {
            "schema": "engel_conductor_run_v1",
            "goal": str(slug_text or ""),
            "slug": goal_slug(slug_text),
            "status": "unknown goal",
            "ok": False,
            "rounds": [],
            "known_goals": known,
        }
    raw_problems = record.get("last_problems")
    history = (
        [str(p) for p in raw_problems] if isinstance(raw_problems, list) else []
    )
    return conduct(
        str(record.get("goal", "")),
        draft_fn=draft_fn,
        allow_actions=allow_actions,
        router=router,
        intent_fn=intent_fn,
        write_receipt=write_receipt,
        history=history or None,
    )


# ---------------------------------------------------------------------------
# Route render functions (engel.conductor.*).
# ---------------------------------------------------------------------------
_CONDUCT_PREFIXES = (
    "continue engel goal",
    "conduct engel goal",
    "engel goal",
)


def _payload(text: str) -> tuple[str, bool]:
    """(payload, is_continue) for a conduct phrase."""
    low = str(text or "").strip()
    for prefix in _CONDUCT_PREFIXES:
        if low.casefold().startswith(prefix):
            return low[len(prefix):].strip(), prefix.startswith("continue")
    return "", False


def render_conductor_docs(text: str = "") -> str:
    return (
        "Engel Conductor -- the loop that closes (docs/ENGEL_CONDUCTOR_DESIGN.md).\n"
        "Goal -> retrieve -> plan -> validate -> run -> observe -> repair -> ledger,\n"
        "bounded (max 2 rounds, Governor-receipted) and persistent "
        "(memory/engel_goals/).\n\n"
        "Phrases:\n"
        "  engel goal <goal or saved plan name>   conduct a goal now\n"
        "  continue engel goal <slug>             re-enter a goal from the ledger\n"
        "  engel goal status                      the goal ledger, rendered\n"
        "  engel conductor docs                   this reference\n\n"
        "The route surface conducts saved plans deterministically (read-only).\n"
        "In the main chat the same phrase also DRAFTS a plan with the local\n"
        "model lane and repairs it once from the run's own receipt.\n"
        "Action steps stay blocked unless the operator lists the route id in\n"
        "memory/engel_conductor_action_grants.json AND the Governor's allow\n"
        "class passes the grant -- absent file, nothing is grantable.\n"
        "Receipts: reports/engel_conductor/."
    )


def render_goal_status(text: str = "") -> str:
    goals = list_goals()
    if not goals:
        return (
            "Engel goal ledger: empty. Start one with 'engel goal <text>'; "
            "conducted goals persist in memory/engel_goals/."
        )
    lines = [f"Engel goal ledger ({len(goals)} goal(s), newest first):"]
    for rec in goals[:12]:
        status = str(rec.get("status", "?"))
        lines.append(
            f"  - {rec.get('slug', '?')}  [{status}]  rounds={rec.get('rounds_spent', 0)}"
            f"  updated={str(rec.get('updated_at_utc', ''))[:19]}"
        )
        goal_line = " ".join(str(rec.get("goal", "")).split())
        if goal_line:
            lines.append(f"      goal: {goal_line[:120]}")
        for problem in rec.get("last_problems", [])[-2:]:
            lines.append(f"      last: {str(problem)[:140]}")
    lines.append("Re-enter one with: continue engel goal <slug>")
    return "\n".join(lines)


def render_conduct_result(receipt: dict[str, Any]) -> str:
    lines = [
        f"Engel Conductor -- goal: {receipt.get('goal', '')}",
        f"Status: {receipt.get('status', '?')}"
        + (f"  (slug: {receipt.get('slug', '')})" if receipt.get("slug") else ""),
    ]
    if receipt.get("known_goals"):
        lines.append(f"Known goals: {receipt['known_goals']}")
    for round_rec in receipt.get("rounds", []):
        head = f"Round {round_rec.get('round')}: {round_rec.get('origin', '')}"
        errors = round_rec.get("validate_errors")
        if errors:
            lines.append(f"{head} -- INVALID ({len(errors)} error(s))")
            lines.extend(f"    - {error}" for error in errors[:4])
            continue
        observation = round_rec.get("observation", {})
        lines.append(
            f"{head} -- ran: {observation.get('executed_routes', 0)} route(s), "
            f"{observation.get('blocked_routes', 0)} blocked"
        )
        for line in round_rec.get("output", [])[:8]:
            lines.append(f"    {str(line)[:RESPONSE_CLIP]}")
        for problem in observation.get("problems", [])[:4]:
            lines.append(f"    problem: {str(problem)[:200]}")
    if receipt.get("suggestions"):
        lines.append(receipt["suggestions"])
        lines.append(
            "No saved plan matched and no drafting lane is attached to this "
            "surface -- in the main chat, 'engel goal <text>' drafts a plan too."
        )
    if receipt.get("status") == "needs attention" and receipt.get("slug"):
        lines.append(f"Re-enter later with: continue engel goal {receipt['slug']}")
    if receipt.get("receipt_path"):
        lines.append(f"Receipt: {receipt['receipt_path']}")
    return "\n".join(lines)


def render_conduct(text: str = "") -> str:
    payload, is_continue = _payload(text)
    if not payload:
        return (
            "Usage: engel goal <goal or saved plan name>\n"
            "       continue engel goal <slug>\n" + render_goal_status()
        )
    if is_continue:
        return render_conduct_result(continue_goal(payload))
    return render_conduct_result(conduct(payload))
