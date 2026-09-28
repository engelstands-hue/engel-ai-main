"""Engel Agent Kernel -- one entry point for Engel's native agentic systems.

The project already had the parts of a strong local agent, but an operator had
to name the mechanism: ``engel goal`` for the Conductor, ``engel orchestra``
for fan-out, or ``forge code`` for proven Python.  The older agent harness is a
tool registry whose ``run_agent`` path never consumes that registry.  This
module is the missing dispatch spine.

``run_goal`` chooses the smallest proven engine for the work:

* exact safe registry phrase -> one EngelScript route (no model call);
* FHERMA / cuPQC polynomial GPU challenge -> local verified multiply plus CUDA;
* pure-computation Python task -> Code Forge;
* clearly multi-part task -> heterogeneous parallel lanes;
* everything else -> Conductor.

Every path keeps the existing safety authority.  Direct routes must pass
EngelScript's registry gate, conducted lanes are read-only, generated code is
accepted only by the Forge's AST gate and sandbox tests, model calls are
injected by the caller, and the whole dispatch is Governor-receipted.  The
kernel never schedules itself, deploys artifacts, or enables an external
provider.

Spec: docs/ENGEL_AGENT_KERNEL_DESIGN.md.
Verifier: tools/verify_engel_agent_kernel.py.
"""
from __future__ import annotations

import hashlib
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

RECEIPT_DIR = ROOT / "reports" / "engel_agent_kernel"
MAX_LANES = 4
MAX_STORY_CHARS = 1200
MAX_OUTPUT_LINES = 8

ModelFn = Callable[[str], str]

_PREFIXES = (
    "engel agent work ",
    "engel agent do ",
    "engel agent run ",
    "engel agent task ",
    "engel work ",
    "engel solve ",
)
_EXPLICIT_ENGINES = frozenset(
    ("auto", "direct", "conductor", "orchestra", "forge", "challenge")
)

# The Forge deliberately supports a narrow, safe kernel: Python pure
# computation.  App/build/deploy asks stay with the Conductor and the existing
# build lane; routing them to the Forge would produce a convincing but useless
# two-file algorithm artifact.
_CODE_CREATE_RE = re.compile(
    r"\b(?:write|create|implement|code|program|develop|fix|repair|refactor|test)\b",
    re.IGNORECASE,
)
_CODE_OBJECT_RE = re.compile(
    r"\b(?:python|function|class|algorithm|parser|validator|serializer|"
    r"data\s+transform|library|module|unit\s+tests?|utility|calculation)\b",
    re.IGNORECASE,
)
_NON_FORGE_RE = re.compile(
    r"\b(?:app|application|flutter|website|web\s+app|server|service|api|database|"
    r"deploy|install|package|docker|container|gui|desktop|android|ios|cluster)\b",
    re.IGNORECASE,
)
_COMPOUND_RE = re.compile(
    r"\b(?:and\s+also|and\s+then|as\s+well\s+as|in\s+parallel|plus)\b",
    re.IGNORECASE,
)
_OPERATIONAL_RE = re.compile(
    r"\b(?:check|show|status|inspect|verify|audit|report|list|find|diagnose)\b",
    re.IGNORECASE,
)

# Companion Chat (Auto Best) must answer creative HTML/game asks. The Conductor
# is read-only EngelScript and cannot emit a playable page, so stealing the
# turn always surfaces "Task needs attention" with fake route asks.
_COMPANION_CREATE_RE = re.compile(
    r"\b(?:create|make|write|draw|invent)\b",
    re.IGNORECASE,
)
_COMPANION_ARTIFACT_RE = re.compile(
    r"\b(?:html|css|webpage|web\s+page|website|game|poem|story|song)\b",
    re.IGNORECASE,
)
_COMPANION_KEEP_KERNEL_RE = re.compile(
    r"\b(?:python|flutter|android|deploy|install|pair|connect|"
    r"function|class|algorithm|parser|validator)\b",
    re.IGNORECASE,
)

# Conversational phrases that should use a known read-only registry route instead
# of falling into Conductor EngelScript drafting.
_ANDROID_WORKER_STATUS_RE = re.compile(
    r"\b(?:android|phone)\s+workers?\b.*\b(?:not\s+connected|disconnected|offline|status|fix|connect|pair|usb)\b"
    r"|\b(?:fix|check|connect|pair)\b.*\b(?:android|phone)\s+workers?\b"
    r"|\bandroid\s+worker\s+(?:is\s+)?(?:not\s+connected|offline|disconnected)\b"
    r"|\b(?:android\s+)?(?:worker\s+)?(?:alpha|beta|gamma)\b.*\b(?:ip|address|bad\s+address|offline|not\s+connected|pair|usb|status|fix)\b"
    r"|\b(?:bad\s+address|wrong\s+ip|ip\s+bad)\b.*\b(?:alpha|beta|gamma|android|phone|worker)\b"
    r"|\bbeta\s+is\s+show\s+ip\b",
    re.IGNORECASE,
)


def _canonical_direct_goal(goal: str) -> str:
    """Map common human wording onto an exact safe registry phrase when possible."""
    text = _one_line(goal)
    if not text:
        return text
    if _ANDROID_WORKER_STATUS_RE.search(text):
        return "android workers status"
    return text


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _one_line(value: Any) -> str:
    return " ".join(str(value or "").split())


def extract_goal(text: str) -> str:
    """Remove a kernel trigger while preserving the task's original case."""
    raw = str(text or "").strip()
    low = raw.casefold()
    for prefix in _PREFIXES:
        if low.startswith(prefix):
            return raw[len(prefix):].strip()
    return raw


def _prompt_guard(goal: str) -> dict[str, Any]:
    """Use Engel's real prompt guard before any model sees the goal."""
    try:
        from engel_prompt_injection_guard import check_prompt_injection

        verdict = check_prompt_injection(goal)
        status = str(getattr(verdict, "verdict", "allow") or "allow")
        return {
            "ok": status not in ("block", "review"),
            "verdict": status,
            "score": float(getattr(verdict, "score", 0.0) or 0.0),
            "reason": str(getattr(verdict, "reason", "") or ""),
        }
    except Exception as exc:  # a missing safety gate must never widen capability
        return {
            "ok": False,
            "verdict": "unavailable",
            "score": 0.0,
            "reason": f"prompt guard unavailable: {type(exc).__name__}",
        }


def _direct_safety(goal: str) -> dict[str, Any]:
    try:
        from engel_script import route_step_safety

        return dict(route_step_safety(goal))
    except Exception as exc:
        return {
            "allowed": False,
            "route_id": "",
            "reason": f"route safety unavailable: {type(exc).__name__}",
        }


def _is_polynomial_gpu_challenge(goal: str) -> bool:
    from engel_polynomial_gpu_challenge import looks_like_challenge

    return looks_like_challenge(goal)


def _is_forge_task(goal: str) -> bool:
    text = _one_line(goal)
    if not text or _NON_FORGE_RE.search(text):
        return False
    return bool(_CODE_CREATE_RE.search(text) and _CODE_OBJECT_RE.search(text))


def _has_compound_shape(goal: str) -> bool:
    text = str(goal or "").strip()
    if len([part for part in text.split("|") if part.strip()]) >= 2:
        return True
    usable_lines = [line.strip(" -*\t") for line in text.splitlines() if len(line.split()) >= 2]
    if len(usable_lines) >= 2:
        return True
    return bool(_COMPOUND_RE.search(text))


def select_engine(goal: str, requested: str = "auto") -> dict[str, Any]:
    """Pure, deterministic engine selection.  It never calls a model."""
    goal_text = _one_line(extract_goal(goal))
    wanted = str(requested or "auto").strip().casefold()
    if wanted not in _EXPLICIT_ENGINES:
        wanted = "auto"
    canonical = _canonical_direct_goal(goal_text)
    direct = _direct_safety(canonical)
    if wanted != "auto":
        engine = wanted
        reason = f"caller explicitly selected {wanted}"
        if wanted == "direct" and direct.get("allowed") is not True:
            engine = "conductor"
            reason = "requested direct path was not a safe registry route; narrowed to Conductor"
        return {"engine": engine, "reason": reason, "direct_safety": direct, "canonical_goal": canonical}
    if _is_polynomial_gpu_challenge(goal_text):
        return {
            "engine": "challenge",
            "reason": "FHERMA negacyclic kernel is the wired rank-7 board result",
            "direct_safety": direct,
            "canonical_goal": canonical,
        }
    if direct.get("allowed") is True:
        reason = "goal resolves to one read-only AI-safe registry route"
        if canonical != goal_text:
            reason = "conversational goal mapped to one read-only AI-safe registry route"
        return {
            "engine": "direct",
            "reason": reason,
            "direct_safety": direct,
            "canonical_goal": canonical,
        }
    forge_task = _is_forge_task(goal_text)
    compound = _has_compound_shape(goal_text)
    # A mixed request such as "check models and also implement a parser" is
    # heterogeneous work, not one large code prompt.  Let the Orchestra split
    # it so the status lane can take the direct fast path while only the code
    # lane enters the Forge.
    if compound and forge_task and _OPERATIONAL_RE.search(goal_text):
        return {
            "engine": "orchestra",
            "reason": "mixed operational and code work needs heterogeneous lanes",
            "direct_safety": direct,
            "canonical_goal": canonical,
        }
    if forge_task:
        return {
            "engine": "forge",
            "reason": "pure-computation Python creation task fits the Code Forge contract",
            "direct_safety": direct,
            "canonical_goal": canonical,
        }
    if compound:
        return {
            "engine": "orchestra",
            "reason": "goal has independent parts that can overlap",
            "direct_safety": direct,
            "canonical_goal": canonical,
        }
    return {
        "engine": "conductor",
        "reason": "single operational goal needs plan-run-observe",
        "direct_safety": direct,
        "canonical_goal": canonical,
    }


def should_yield_to_companion_chat(
    goal: str, selection: Optional[dict[str, Any]] = None
) -> bool:
    """True when Chat/Auto Best should answer instead of the Agent Kernel.

    HTML/game/page creation is not a registry route and is not Code Forge
    Python. Conductor drafts cannot create those artifacts.
    """
    text = _one_line(extract_goal(goal))
    if not text:
        return False
    sel = selection or select_engine(text)
    engine = str(sel.get("engine") or "")
    if engine in ("direct", "forge"):
        return False
    if not (_COMPANION_CREATE_RE.search(text) and _COMPANION_ARTIFACT_RE.search(text)):
        return False
    if _COMPANION_KEEP_KERNEL_RE.search(text):
        return False
    return engine in ("conductor", "orchestra")


def _govern_dispatch(engine: str, lanes: int, contains_forge: bool) -> Optional[dict[str, Any]]:
    try:
        from engel_governor import govern

        return govern(
            "allow",
            {
                "gate": "agent_kernel_dispatch",
                "gate_result": engine in _EXPLICIT_ENGINES and 1 <= lanes <= MAX_LANES,
                "engine": engine,
                "lanes": lanes,
                "read_only": not contains_forge,
                "sandboxed_forge": contains_forge,
            },
        )
    except Exception:
        return None


def _output_from_script(receipt: dict[str, Any]) -> list[str]:
    return [str(line)[:MAX_STORY_CHARS] for line in receipt.get("output", [])[:MAX_OUTPUT_LINES]]


def _output_from_conduct(receipt: dict[str, Any]) -> list[str]:
    output: list[str] = []
    for round_rec in receipt.get("rounds", []) or []:
        lines = round_rec.get("output", []) or []
        output = [str(line)[:MAX_STORY_CHARS] for line in lines[:MAX_OUTPUT_LINES]]
    return output


def _direct_lane(
    index: int,
    goal: str,
    *,
    router=None,
    intent_fn=None,
    write_receipt: bool,
) -> dict[str, Any]:
    import engel_script as es

    # json.dumps emits a quoted EngelScript string and safely escapes any quote
    # in the phrase.  The route is classified again inside the executor.
    phrase = json.dumps(_one_line(goal), ensure_ascii=False)
    source = f'plan "Agent kernel fast path"\nask $result = route {phrase}\nsay $result\n'
    receipt = es.execute_engel_script(
        source,
        allow_actions=False,
        router=router,
        intent_fn=intent_fn,
        write_receipt=write_receipt,
    )
    problems = [str(error) for error in receipt.get("errors", []) or []]
    for step in receipt.get("steps", []) or []:
        if step.get("blocked"):
            problems.append(str(step.get("reason") or "route blocked"))
        elif step.get("kind") in ("route", "ask_route") and step.get("ok") is False:
            problems.append("route reported failure")
    return {
        "lane": index,
        "goal": goal,
        "engine": "direct",
        "ok": bool(receipt.get("ok")) and not problems,
        "status": "done" if bool(receipt.get("ok")) and not problems else "needs attention",
        "problems": problems,
        "output": _output_from_script(receipt),
        "executed_routes": sum(
            1
            for step in receipt.get("steps", []) or []
            if step.get("kind") in ("route", "ask_route") and not step.get("blocked")
        ),
        "child_receipt": str(receipt.get("receipt_path", "")),
    }


def _conduct_lane(
    index: int,
    goal: str,
    *,
    draft_fn: Optional[ModelFn],
    router=None,
    intent_fn=None,
    write_receipt: bool,
) -> dict[str, Any]:
    import engel_conductor as ec

    receipt = ec.conduct(
        goal,
        draft_fn=draft_fn,
        allow_actions=False,
        router=router,
        intent_fn=intent_fn,
        write_receipt=write_receipt,
    )
    problems: list[str] = []
    executed = 0
    for round_rec in receipt.get("rounds", []) or []:
        problems.extend(str(value) for value in round_rec.get("validate_errors", []) or [])
        observation = round_rec.get("observation", {}) or {}
        problems.extend(str(value) for value in observation.get("problems", []) or [])
        executed = int(observation.get("executed_routes", executed) or 0)
    if not receipt.get("ok") and not problems:
        problems.append(str(receipt.get("status") or "conduct did not finish"))
    return {
        "lane": index,
        "goal": goal,
        "engine": "conductor",
        "ok": bool(receipt.get("ok")),
        "status": str(receipt.get("status", "")),
        "problems": problems[-6:],
        "output": _output_from_conduct(receipt),
        "executed_routes": executed,
        "slug": str(receipt.get("slug", "")),
        "child_receipt": str(receipt.get("receipt_path", "")),
    }


def _forge_lane(
    index: int,
    goal: str,
    *,
    generate_fn: Optional[ModelFn],
    write_receipt: bool,
) -> dict[str, Any]:
    import engel_code_forge as cf

    if generate_fn is None:
        return {
            "lane": index,
            "goal": goal,
            "engine": "forge",
            "ok": False,
            "status": "no code model available",
            "problems": ["the Forge needs an injected local code-generation function"],
            "output": [],
            "executed_routes": 0,
            "child_receipt": "",
        }
    receipt = cf.forge(goal, generate_fn=generate_fn, write_receipt=write_receipt)
    problems: list[str] = []
    for round_rec in receipt.get("rounds", []) or []:
        problems = [str(value) for value in round_rec.get("problems", []) or []]
    if not receipt.get("ok") and not problems:
        problems.append(str(receipt.get("status") or "forge did not finish"))
    artifacts = [str(value) for value in receipt.get("artifacts", []) or []]
    output = (["Proven artifacts: " + ", ".join(artifacts)] if artifacts else [])
    return {
        "lane": index,
        "goal": goal,
        "engine": "forge",
        "ok": bool(receipt.get("ok")),
        "status": str(receipt.get("status", "")),
        "problems": problems[-6:],
        "output": output,
        "executed_routes": 0,
        "rounds": len(receipt.get("rounds", []) or []),
        "artifacts": artifacts,
        "child_receipt": str(receipt.get("receipt_path", "")),
    }


def _locked_models(
    draft_fn: Optional[ModelFn], generate_fn: Optional[ModelFn]
) -> tuple[Optional[ModelFn], Optional[ModelFn]]:
    """Honor CT's one-heavy-model-in-flight contract across every lane."""
    lock = threading.Lock()

    def wrap(fn: Optional[ModelFn]) -> Optional[ModelFn]:
        if fn is None:
            return None

        def call(prompt: str) -> str:
            with lock:
                try:
                    return str(fn(prompt) or "")
                except Exception:
                    return ""

        return call

    return wrap(draft_fn), wrap(generate_fn or draft_fn)


def _challenge_lane(index: int, goal: str, *, write_receipt: bool) -> dict[str, Any]:
    import engel_polynomial_gpu_challenge as challenge

    receipt = challenge.complete(goal, write_receipt=write_receipt)
    problems = [str(value) for value in receipt.get("problems", []) or []]
    if not receipt.get("ok") and not problems:
        problems.append(str(receipt.get("status") or "polynomial challenge did not finish"))
    return {
        "lane": index,
        "goal": goal,
        "engine": "challenge",
        "ok": bool(receipt.get("ok")),
        "status": str(receipt.get("status", "")),
        "problems": problems[-6:],
        "output": [str(line) for line in receipt.get("output", []) or []],
        "executed_routes": 0,
        "artifacts": [str(value) for value in receipt.get("artifacts", []) or []],
        "child_receipt": str(receipt.get("receipt_path", "")),
    }


def _run_lane(
    index: int,
    goal: str,
    *,
    draft_fn: Optional[ModelFn],
    generate_fn: Optional[ModelFn],
    router=None,
    intent_fn=None,
    write_receipt: bool,
    forced_engine: str = "auto",
) -> dict[str, Any]:
    selection = select_engine(goal, forced_engine)
    engine = selection["engine"]
    lane_goal = str(selection.get("canonical_goal") or goal)
    if engine != "direct":
        lane_goal = goal
    try:
        if engine == "direct":
            lane = _direct_lane(
                index, lane_goal, router=router, intent_fn=intent_fn,
                write_receipt=write_receipt,
            )
        elif engine == "forge":
            lane = _forge_lane(
                index, goal, generate_fn=generate_fn, write_receipt=write_receipt
            )
        elif engine == "challenge":
            lane = _challenge_lane(index, goal, write_receipt=write_receipt)
        else:
            lane = _conduct_lane(
                index, goal, draft_fn=draft_fn, router=router,
                intent_fn=intent_fn, write_receipt=write_receipt,
            )
    except Exception as exc:
        lane = {
            "lane": index,
            "goal": goal,
            "engine": engine,
            "ok": False,
            "status": f"lane crashed: {type(exc).__name__}",
            "problems": [str(exc)[:300]],
            "output": [],
            "executed_routes": 0,
            "child_receipt": "",
        }
    lane["selection_reason"] = str(selection.get("reason", ""))
    return lane


def _split_goal(goal: str, draft_fn: Optional[ModelFn]) -> tuple[list[str], str]:
    import engel_orchestra as eo

    return eo.split_goal(goal, draft_fn=draft_fn)


def _synthesis_prompt(goal: str, lanes: list[dict[str, Any]]) -> str:
    summaries = []
    for lane in lanes:
        story = " / ".join(lane.get("output", [])[:3] or [lane.get("status", "")])
        summaries.append(
            f"[lane {lane['lane']} | {lane['engine']} | {lane['goal'][:100]}] {story[:500]}"
        )
    return "\n".join(
        [
            "Combine these verified lane reports into one short answer to the goal. "
            "Do not invent success; preserve every failure. Reply with only the answer.",
            "",
            *summaries,
            "",
            "Goal: " + _one_line(goal),
        ]
    )


def run_goal(
    goal: str,
    *,
    draft_fn: Optional[ModelFn] = None,
    generate_fn: Optional[ModelFn] = None,
    router=None,
    intent_fn=None,
    requested_engine: str = "auto",
    write_receipt: bool = True,
    synthesize: bool = True,
) -> dict[str, Any]:
    """Run one goal through Engel's native agentic spine."""
    goal_text = _one_line(extract_goal(goal))
    receipt: dict[str, Any] = {
        "schema": "engel_agent_kernel_run_v1",
        "started_at_utc": _now(),
        "goal": goal_text,
        "selection": {},
        "lanes": [],
        "status": "",
        "ok": False,
    }
    if not goal_text:
        receipt["status"] = "empty goal"
        return _finish(receipt, write_receipt)

    # HIPL -> lifted intent -> MIPL is the semantic contract above dispatch.
    # It describes the goal and proof obligations but carries no execution
    # authority; the prompt guard, Governor, and child engines still decide.
    try:
        import engel_lifted_intent as intent_bridge

        receipt["lifted_intent_contract"] = intent_bridge.create_intent_contract(
            goal_text,
            caller="engel_agent_kernel",
        )
    except Exception as exc:
        receipt["lifted_intent_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"

    guard = _prompt_guard(goal_text)
    receipt["prompt_guard"] = guard
    if not guard["ok"]:
        receipt["status"] = f"goal refused by prompt guard ({guard['verdict']})"
        return _finish(receipt, write_receipt)

    selection = select_engine(goal_text, requested_engine)
    receipt["selection"] = selection
    engine = str(selection["engine"])

    locked_draft, locked_generate = _locked_models(draft_fn, generate_fn)
    if engine == "orchestra":
        subgoals, origin = _split_goal(goal_text, locked_draft)
        receipt["split_origin"] = origin
    else:
        subgoals = [goal_text]
        receipt["split_origin"] = "single engine"
    if not subgoals:
        receipt["status"] = "goal produced no executable lanes"
        return _finish(receipt, write_receipt)
    if len(subgoals) > MAX_LANES:
        receipt["status"] = f"too many lanes ({len(subgoals)}; maximum {MAX_LANES})"
        receipt["subgoals"] = subgoals
        return _finish(receipt, write_receipt)

    planned_engines = (
        [select_engine(part)["engine"] for part in subgoals]
        if engine == "orchestra"
        else [engine]
    )
    contains_forge = engine == "forge" or "forge" in planned_engines
    verdict = _govern_dispatch(engine, len(subgoals), contains_forge)
    receipt["dispatch_verdict"] = verdict
    # Allow is fail-closed for code execution.  Read-only route/conductor work
    # keeps the Governor design's fail-open availability behavior.
    if verdict is not None and verdict.get("outcome") != "allow":
        receipt["status"] = "dispatch denied by Governor"
        return _finish(receipt, write_receipt)
    if verdict is None and contains_forge:
        receipt["status"] = "Governor unavailable; Forge dispatch denied"
        return _finish(receipt, write_receipt)

    if len(subgoals) == 1:
        lane = _run_lane(
            1,
            subgoals[0],
            draft_fn=locked_draft,
            generate_fn=locked_generate,
            router=router,
            intent_fn=intent_fn,
            write_receipt=write_receipt,
            forced_engine=engine if engine != "orchestra" else "auto",
        )
        lanes = [lane]
    else:
        with ThreadPoolExecutor(max_workers=min(MAX_LANES, len(subgoals))) as pool:
            futures = [
                pool.submit(
                    _run_lane,
                    index,
                    subgoal,
                    draft_fn=locked_draft,
                    generate_fn=locked_generate,
                    router=router,
                    intent_fn=intent_fn,
                    write_receipt=write_receipt,
                    forced_engine="auto",
                )
                for index, subgoal in enumerate(subgoals, start=1)
            ]
            lanes = [future.result() for future in futures]
    receipt["lanes"] = lanes
    receipt["engines_used"] = sorted({str(lane.get("engine", "")) for lane in lanes})
    receipt["executed_routes"] = sum(int(lane.get("executed_routes", 0) or 0) for lane in lanes)
    receipt["artifacts"] = [
        artifact
        for lane in lanes
        for artifact in lane.get("artifacts", []) or []
    ]
    done = sum(1 for lane in lanes if lane.get("ok") is True)
    receipt["ok"] = done == len(lanes)
    receipt["status"] = (
        "done" if receipt["ok"] else f"{done}/{len(lanes)} lanes done -- needs attention"
    )
    receipt["problems"] = [
        f"lane {lane['lane']} ({lane['engine']}): {problem}"
        for lane in lanes
        if not lane.get("ok")
        for problem in lane.get("problems", []) or [lane.get("status", "failed")]
    ]

    if synthesize and locked_draft is not None and len(lanes) > 1:
        try:
            receipt["synthesis"] = str(locked_draft(_synthesis_prompt(goal_text, lanes)) or "")[
                :MAX_STORY_CHARS
            ]
        except Exception:
            receipt["synthesis"] = ""
    return _finish(receipt, write_receipt)


def _finish(receipt: dict[str, Any], write: bool) -> dict[str, Any]:
    receipt["finished_at_utc"] = _now()
    path: Path | None = None
    if write:
        try:
            RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            digest = hashlib.sha256(str(receipt.get("goal", "")).encode("utf-8")).hexdigest()[:8]
            path = RECEIPT_DIR / f"AGENT_{stamp}_{digest}.json"
            receipt["receipt_path"] = str(path)
        except OSError as exc:
            receipt["receipt_path"] = ""
            receipt["receipt_write_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    contract = receipt.get("lifted_intent_contract")
    if isinstance(contract, dict):
        try:
            import engel_lifted_intent as intent_bridge

            intent_receipt = intent_bridge.complete_intent_receipt(
                contract,
                receipt,
                write_receipt=write,
            )
            lifted = contract.get("lifted_intent") or {}
            receipt["lifted_intent"] = {
                "contract_id": contract.get("contract_id", ""),
                "objective": lifted.get("objective", ""),
                "effect": lifted.get("effect", ""),
                "targets": lifted.get("targets", []),
                "approval_required": lifted.get("approval_required", False),
                "audit_head": (intent_receipt.get("verification") or {}).get("audit_head", ""),
            }
            receipt["lifted_intent_receipt_path"] = intent_receipt.get("receipt_path", "")
            receipt["lifted_intent_audit_complete"] = bool(
                (intent_receipt.get("verification") or {}).get("audit_complete")
            )
            if hasattr(intent_bridge, "stamp_slm_compiler_lnt"):
                receipt = intent_bridge.stamp_slm_compiler_lnt(receipt)
        except (OSError, ImportError, TypeError, ValueError) as exc:
            receipt["lifted_intent_write_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    if path is not None:
        try:
            temp = path.with_suffix(".tmp")
            temp.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
            temp.replace(path)
        except OSError as exc:
            receipt["receipt_path"] = ""
            receipt["receipt_write_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return receipt


def list_runs(limit: int = 12) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not RECEIPT_DIR.is_dir():
        return records
    for path in sorted(RECEIPT_DIR.glob("AGENT_*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("schema") == "engel_agent_kernel_run_v1":
            records.append(data)
        if len(records) >= max(1, int(limit)):
            break
    return records


def render_agent_result(receipt: dict[str, Any]) -> str:
    lines = [
        "Engel Agent Kernel",
        "",
        f"Goal: {receipt.get('goal', '')}",
        f"Status: {receipt.get('status', '')}",
        f"Selected: {(receipt.get('selection') or {}).get('engine', '')} -- "
        f"{(receipt.get('selection') or {}).get('reason', '')}",
    ]
    for lane in receipt.get("lanes", []) or []:
        mark = "OK" if lane.get("ok") else "ATTENTION"
        lines.append(
            f"Lane {lane.get('lane')} [{lane.get('engine')}] {mark}: {lane.get('goal', '')}"
        )
        for story in lane.get("output", [])[:3] or []:
            lines.append("  " + str(story))
        for problem in lane.get("problems", [])[:3] or []:
            lines.append("  Problem: " + str(problem))
    if receipt.get("synthesis"):
        lines.extend(["", str(receipt["synthesis"])])
    if receipt.get("artifacts"):
        lines.append("Artifacts: " + ", ".join(str(value) for value in receipt["artifacts"]))
    lines.append("Receipt: " + str(receipt.get("receipt_path") or "not written"))
    return "\n".join(lines)


def render_agent_docs(_text: str = "") -> str:
    return (
        "Engel Agent Kernel -- one goal, automatic native dispatch.\n\n"
        "Say: engel work <goal>\n"
        "The kernel uses the fastest safe path: an exact read-only route, a local "
        "verified kernel for the FHERMA polynomial GPU challenge, the Code "
        "Forge for pure Python, the Conductor for one operational goal, or parallel "
        "lanes for a compound goal. Every child loop and the final handoff are receipted.\n\n"
        "Examples:\n"
        "  engel work phone workers status\n"
        "  engel work check phones | check storage | check models\n"
        "  engel work implement a Python parser with unit tests\n\n"
        "Boundaries: local model callbacks only; direct routes read-only; conducted "
        "actions disabled; Forge artifacts sandboxed and never deployed; four lanes max."
    )


def render_agent_status(_text: str = "") -> str:
    runs = list_runs()
    lines = ["Engel Agent Kernel status", "", f"Receipts: {len(runs)} recent"]
    if not runs:
        lines.append("No kernel run has been receipted yet.")
    for run in runs:
        lines.append(
            f"- {run.get('status', '')}: {run.get('goal', '')[:90]} "
            f"[{', '.join(run.get('engines_used', []) or [])}]"
        )
    return "\n".join(lines)


def render_agent_work(text: str = "") -> str:
    goal = extract_goal(text)
    if not goal:
        return render_agent_docs()
    return render_agent_result(run_goal(goal))
