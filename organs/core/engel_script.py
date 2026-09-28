"""EngelScript -- Engel AI Main's own plan language (v1).

Spec: docs/ENGEL_SCRIPT_LANGUAGE.md. Verifier: tools/verify_engel_script.py.

Engel has a 490-route library, six model lanes, a served SLM roster, and a
Governor -- and, until this module, no way to COMPOSE them: a phrase invoked
exactly one route, and anything multi-step meant Python. EngelScript is the
composition layer, built as a plan notation rather than a general language:

* eight statement forms, one expression form, no loops, no nesting -- small
  enough for Engel's own models to emit and for a human to audit at a glance;
* deterministic and bounded: the step STRUCTURE of a run is a pure function of
  the source (only route outputs vary), capped at 64 statements / 16 KiB /
  120 s wall clock;
* safe by construction: every `route` step is classified through the real
  router (prompt-injection guard inherited) and checked against the route
  registry's OWN safety flags before it runs -- non-read-only routes are
  blocked and receipted, so a script can never do more than its phrases were
  already allowed to do, and from the phrase surface strictly less;
* receipted: every run writes reports/engel_script/ with the script's sha256,
  each step's route id / outcome / latency, and the final variables.

The router normalization layer lowercases text, flattens newlines, and strips
periods, so the phrase surface runs plans BY NAME from memory/engel_scripts/
(<name>.engel) and accepts `;` as an inline statement separator.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

SCRIPT_DIR = ROOT / "memory" / "engel_scripts"
RECEIPT_DIR = ROOT / "reports" / "engel_script"

MAX_STATEMENTS = 64
MAX_SOURCE_BYTES = 16384
MAX_VARS = 32
MAX_VALUE_CHARS = 16384
MAX_WALL_SECONDS = 120.0
RESPONSE_CLIP = 400

# Belt on top of the registry flags: a script step must return in seconds.
# These suffixes spawn cargo/npm/flutter or long-lived processes.
SLOW_ROUTE_SUFFIXES = (
    ".build", ".tauri_build", ".install", ".install_to_project", ".dev_start",
    ".app_dev_start", ".cli_receive_start", ".bring_up", ".gateway_start",
    ".start", ".stop",
)

_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_PLAN_NAME_RE = re.compile(r"^[a-z0-9_\-]+$")
_TOKEN_RE = re.compile(r'"([^"]*)"|\$([A-Za-z_][A-Za-z0-9_]*)|(\+)|(\S+)')


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Parsing. Statements are tuples:
#   ("plan", title) ("let", name, expr) ("route", expr)
#   ("ask_route", name, expr) ("ask_intent", name, expr) ("say", expr)
#   ("if", var, "contains"|"misses", literal, inner_statement)
# An expr is a tuple of terms: ("lit", text) | ("var", name).
# ---------------------------------------------------------------------------
class EngelScriptError(ValueError):
    pass


def _tokens(line: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    pos = 0
    for match in _TOKEN_RE.finditer(line):
        between = line[pos : match.start()].strip()
        if between:
            raise EngelScriptError(f"unparseable text {between!r}")
        pos = match.end()
        if match.group(1) is not None:
            out.append(("lit", match.group(1)))
        elif match.group(2) is not None:
            out.append(("var", match.group(2).lower()))
        elif match.group(3) is not None:
            out.append(("plus", "+"))
        else:
            out.append(("word", match.group(4).lower()))
    if line[pos:].strip():
        raise EngelScriptError(f"unparseable text {line[pos:].strip()!r}")
    if '"' in "".join(text for kind, text in out if kind == "word"):
        raise EngelScriptError("unbalanced quote")
    return out


def _parse_expr(tokens: list[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    if not tokens:
        raise EngelScriptError("expected an expression")
    terms: list[tuple[str, str]] = []
    expect_term = True
    for kind, text in tokens:
        if expect_term:
            if kind not in ("lit", "var"):
                raise EngelScriptError(f"expected a string or $variable, got {text!r}")
            terms.append((kind, text))
            expect_term = False
        else:
            if kind != "plus":
                raise EngelScriptError(f"expected '+' between terms, got {text!r}")
            expect_term = True
    if expect_term:
        raise EngelScriptError("expression ends with a dangling '+'")
    return tuple(terms)


def _parse_statement(tokens: list[tuple[str, str]], allow_if: bool = True) -> tuple:
    if not tokens:
        raise EngelScriptError("empty statement")
    kind, head = tokens[0]
    if kind == "word" and head == "plan":
        if len(tokens) != 2 or tokens[1][0] != "lit":
            raise EngelScriptError('plan takes exactly one "title"')
        return ("plan", tokens[1][1])
    if kind == "word" and head == "let":
        if len(tokens) < 4 or tokens[1][0] != "var" or tokens[2] != ("word", "="):
            raise EngelScriptError("let syntax: let $name = <expr>")
        return ("let", tokens[1][1], _parse_expr(tokens[3:]))
    if kind == "word" and head == "ask":
        if len(tokens) < 5 or tokens[1][0] != "var" or tokens[2] != ("word", "="):
            raise EngelScriptError("ask syntax: ask $name = route|intent <expr>")
        verb = tokens[3]
        if verb == ("word", "route"):
            return ("ask_route", tokens[1][1], _parse_expr(tokens[4:]))
        if verb == ("word", "intent"):
            return ("ask_intent", tokens[1][1], _parse_expr(tokens[4:]))
        raise EngelScriptError("ask supports only 'route' and 'intent'")
    if kind == "word" and head == "route":
        return ("route", _parse_expr(tokens[1:]))
    if kind == "word" and head == "say":
        return ("say", _parse_expr(tokens[1:]))
    if kind == "word" and head == "if":
        if not allow_if:
            raise EngelScriptError("if may not guard another if (no nesting)")
        if (
            len(tokens) < 6
            or tokens[1][0] != "var"
            or tokens[2][0] != "word"
            or tokens[2][1] not in ("contains", "misses")
            or tokens[3][0] != "lit"
            or tokens[4] != ("word", "then")
        ):
            raise EngelScriptError(
                'if syntax: if $name contains|misses "text" then <statement>'
            )
        inner = _parse_statement(tokens[5:], allow_if=False)
        if inner[0] == "plan":
            raise EngelScriptError("plan may not appear inside an if")
        return ("if", tokens[1][1], tokens[2][1], tokens[3][1], inner)
    raise EngelScriptError(f"unknown statement {head!r}")


def parse_engel_script(source: str) -> tuple[list[tuple], list[str]]:
    """Parse and statically validate. Returns (statements, errors); statements
    are complete only when errors is empty."""
    errors: list[str] = []
    statements: list[tuple] = []
    if len(source.encode("utf-8", errors="replace")) > MAX_SOURCE_BYTES:
        return [], [f"script exceeds {MAX_SOURCE_BYTES} bytes"]
    raw_lines: list[tuple[int, str]] = []
    for line_no, raw in enumerate(str(source or "").splitlines() or [""], start=1):
        no_comment = raw.split("#", 1)[0]
        for piece in no_comment.split(";"):
            if piece.strip():
                raw_lines.append((line_no, piece.strip()))
    if len(raw_lines) > MAX_STATEMENTS:
        return [], [f"script exceeds {MAX_STATEMENTS} statements"]
    defined: set[str] = set()
    for line_no, text in raw_lines:
        try:
            statement = _parse_statement(_tokens(text))
        except EngelScriptError as exc:
            errors.append(f"line {line_no}: {exc}")
            continue
        if statement[0] == "plan" and statements:
            errors.append(f"line {line_no}: plan must be the first statement")
            continue
        # Reading an unset variable is an error, not an empty string: a typo
        # must fail loudly at validation, never silently at run time.
        reads: list[str] = []
        writes: list[str] = []
        def _expr_reads(expr: tuple) -> None:
            for kind, text_ in expr:
                if kind == "var":
                    reads.append(text_)
        head = statement[0]
        if head == "let":
            _expr_reads(statement[2]); writes.append(statement[1])
        elif head in ("ask_route", "ask_intent"):
            _expr_reads(statement[2]); writes.append(statement[1])
        elif head in ("route", "say"):
            _expr_reads(statement[1])
        elif head == "if":
            reads.append(statement[1])
            inner = statement[4]
            if inner[0] == "let":
                _expr_reads(inner[2]); writes.append(inner[1])
            elif inner[0] in ("ask_route", "ask_intent"):
                _expr_reads(inner[2]); writes.append(inner[1])
            elif inner[0] in ("route", "say"):
                _expr_reads(inner[1])
        for name in reads:
            if name not in defined:
                errors.append(f"line {line_no}: ${name} is read before it is set")
        defined.update(writes)
        if len(defined) > MAX_VARS:
            errors.append(f"line {line_no}: more than {MAX_VARS} variables")
            break
        statements.append((line_no, statement))
    return statements, errors


# ---------------------------------------------------------------------------
# Route safety: registry flags decide BEFORE execution.
# ---------------------------------------------------------------------------
def _routes_by_id() -> dict[str, Any]:
    from engel_ai_update_routes import UPDATE_ROUTES

    return {route.route_id: route for route in UPDATE_ROUTES}


def route_step_safety(phrase: str) -> dict[str, Any]:
    """Classify a phrase and decide whether a script may execute it.
    Only registry routes whose OWN metadata says read_only + safe_for_ai_route +
    no_provider_model_network are allowed; slow-lane suffixes are refused as a
    belt. Everything else (known-commands, chat, unsafe, unknown) is blocked."""
    from engel_communication_router import classify_user_input

    intent = classify_user_input(phrase)
    if intent.category != "ai_update_status_request":
        return {
            "allowed": False,
            "route_id": intent.route_target or "",
            "reason": f"phrase is not a registry route (classified {intent.category})",
        }
    route = _routes_by_id().get(intent.route_target)
    if route is None:
        return {
            "allowed": False,
            "route_id": intent.route_target,
            "reason": "route id missing from the registry",
        }
    if not (route.read_only and route.safe_for_ai_route and route.no_provider_model_network):
        return {
            "allowed": False,
            "route_id": route.route_id,
            "reason": "route is not read-only/AI-safe by its own registry flags",
        }
    if any(route.route_id.endswith(suffix) for suffix in SLOW_ROUTE_SUFFIXES):
        return {
            "allowed": False,
            "route_id": route.route_id,
            "reason": "slow-lane route refused in script mode (must return in seconds)",
        }
    if route.route_id.startswith(
        (
            "engel.script",
            "engel.conductor",
            "engel.forge",
            "engel.orchestra",
            "engel.agent_kernel",
        )
    ):
        # No self-reference: a plan invoking the script engine (or the
        # Conductor, which invokes it, or the Orchestra, which fans conducts
        # out in parallel, or the Forge, which runs generated code in its own
        # loop) is unbounded recursion wearing a phrase's coat.
        return {
            "allowed": False,
            "route_id": route.route_id,
            "reason": "scripts may not invoke the script engine",
        }
    return {"allowed": True, "route_id": route.route_id, "reason": "read-only registry route"}


# ---------------------------------------------------------------------------
# Action grants -- the Governor's allow class, finally joined (default OFF).
# docs/ENGEL_CONDUCTOR_DESIGN.md section 3. Absent/empty/malformed grants file
# means zero grants, so behaviour without operator opt-in is byte-identical.
# ---------------------------------------------------------------------------
GRANTS_PATH = ROOT / "memory" / "engel_conductor_action_grants.json"


def load_action_grants() -> set[str]:
    """Route ids the OPERATOR has granted by hand. Fail-empty on any problem:
    a broken grants file must never widen what a script may do."""
    try:
        data = json.loads(GRANTS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    ids = data.get("granted_route_ids") if isinstance(data, dict) else None
    if not isinstance(ids, list):
        return set()
    return {str(item).strip() for item in ids if str(item).strip()}


def _action_grant_for(route_id: str) -> dict[str, Any]:
    """Decide whether ONE blocked step may run under an operator grant.
    Triple-gated: registry membership + the operator grants file + a Governor
    allow verdict, and the slow-lane / self-reference belts stay on. The
    Governor being unavailable DENIES (allow is fail-closed by design)."""
    route = _routes_by_id().get(str(route_id or ""))
    if route is None:
        return {"granted": False, "reason": "grants apply only to registry routes"}
    if any(route.route_id.endswith(suffix) for suffix in SLOW_ROUTE_SUFFIXES):
        return {"granted": False, "reason": "slow-lane route refused even under grant"}
    if route.route_id.startswith(
        (
            "engel.script",
            "engel.conductor",
            "engel.forge",
            "engel.orchestra",
            "engel.agent_kernel",
        )
    ):
        return {"granted": False, "reason": "the script engine is never grantable"}
    if route.route_id not in load_action_grants():
        return {"granted": False, "reason": "route id not in the operator grants file"}
    try:
        from engel_governor import govern

        verdict = govern(
            "allow",
            {
                "gate": "engel_script_action_grant",
                "gate_result": True,
                "route_id": route.route_id,
            },
        )
    except Exception:  # noqa: BLE001 -- allow is fail-closed: no Governor, no grant
        return {"granted": False, "reason": "governor unavailable; grants fail closed"}
    if verdict.get("outcome") != "allow":
        return {
            "granted": False,
            "reason": "governor denied the grant",
            "allow_verdict": verdict,
        }
    return {
        "granted": True,
        "reason": "operator grant + governor allow",
        "allow_verdict": verdict,
    }


def _default_router(phrase: str) -> tuple[bool, str]:
    from engel_communication_router import route_companion_text_or_command

    result = route_companion_text_or_command(phrase, context="ENGEL_SCRIPT")
    return bool(result.handled), str(result.response or "")


def _slm_intent(text: str) -> str:
    try:
        from engel_slm_runtime import get_slm_runtime

        runtime = get_slm_runtime()
        if not runtime.is_ready():
            return "unavailable"
        verdict = runtime.intent(text)
        return str(verdict.get("label")) if verdict else "unavailable"
    except Exception:  # noqa: BLE001 -- advisory primitive fails open
        return "unavailable"


# ---------------------------------------------------------------------------
# Execution.
# ---------------------------------------------------------------------------
def execute_engel_script(
    source: str,
    *,
    allow_actions: bool = False,
    router=None,
    intent_fn=None,
    max_seconds: float = MAX_WALL_SECONDS,
    write_receipt: bool = True,
) -> dict[str, Any]:
    """Run a script. Returns the run receipt (and writes it unless told not to).
    allow_actions is an explicit Python-caller flag for a future approval flow;
    every phrase-reachable surface passes False, and v1 blocks action routes
    regardless -- the flag is recorded so the Governor's allow class can gate a
    real grant later without a receipt-schema change."""
    router = router or _default_router
    intent_fn = intent_fn or _slm_intent
    statements, errors = parse_engel_script(source)
    receipt: dict[str, Any] = {
        "schema": "engel_script_run_v1",
        "started_at_utc": _now(),
        "script_sha256": hashlib.sha256(str(source or "").encode("utf-8")).hexdigest(),
        "allow_actions_requested": bool(allow_actions),
        "mode": "action_grants_enabled" if allow_actions else "read_only",
        "plan_title": "",
        "ok": False,
        "errors": list(errors),
        "steps": [],
        "output": [],
        "variables": {},
    }
    if errors:
        receipt["status"] = "validation failed"
        return _finish(receipt, write_receipt)
    variables: dict[str, str] = {}
    output: list[str] = []
    deadline = time.monotonic() + max(1.0, float(max_seconds))

    def _eval(expr: tuple) -> str:
        return "".join(
            variables[text] if kind == "var" else text for kind, text in expr
        )[:MAX_VALUE_CHARS]

    def _run_one(line_no: int, statement: tuple, guarded: bool) -> None:
        head = statement[0]
        step: dict[str, Any] = {"line": line_no, "kind": head, "guarded": guarded}
        started = time.perf_counter()
        if head == "plan":
            receipt["plan_title"] = statement[1]
            step["title"] = statement[1]
        elif head == "let":
            variables[statement[1]] = _eval(statement[2])
            step["var"] = statement[1]
        elif head == "say":
            line = _eval(statement[1])
            output.append(line)
            step["text"] = line[:RESPONSE_CLIP]
        elif head == "ask_intent":
            text = _eval(statement[2])
            label = intent_fn(text)
            variables[statement[1]] = label
            step.update({"var": statement[1], "label": label})
        elif head in ("route", "ask_route"):
            expr = statement[1] if head == "route" else statement[2]
            phrase = _eval(expr)
            safety = route_step_safety(phrase)
            step.update({"phrase": phrase[:RESPONSE_CLIP], "route_id": safety["route_id"]})
            allowed = bool(safety["allowed"])
            if not allowed and allow_actions:
                grant = _action_grant_for(safety["route_id"])
                if grant.get("granted"):
                    allowed = True
                    verdict = grant.get("allow_verdict", {})
                    step.update(
                        {
                            "granted": True,
                            "grant_reason": grant["reason"],
                            "allow_rule_id": str(verdict.get("rule_id", "")),
                        }
                    )
                else:
                    step["grant_denied_reason"] = grant.get("reason", "")
            if not allowed:
                step.update({"blocked": True, "reason": safety["reason"]})
                if head == "ask_route":
                    variables[statement[1]] = f"[blocked: {safety['reason']}]"
                    step["var"] = statement[1]
            else:
                ok, response = router(phrase)
                step.update({"blocked": False, "ok": bool(ok)})
                if head == "ask_route":
                    variables[statement[1]] = str(response or "")[:MAX_VALUE_CHARS]
                    step["var"] = statement[1]
                step["response_clip"] = str(response or "")[:RESPONSE_CLIP]
        step["elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 1)
        receipt["steps"].append(step)

    for line_no, statement in statements:
        if time.monotonic() > deadline:
            receipt["errors"].append(
                f"line {line_no}: wall-clock cap ({max_seconds:g}s) reached; run aborted"
            )
            break
        if statement[0] == "if":
            value = variables.get(statement[1], "")
            hit = (statement[3] in value) if statement[2] == "contains" else (statement[3] not in value)
            if hit:
                _run_one(line_no, statement[4], guarded=True)
            else:
                receipt["steps"].append(
                    {"line": line_no, "kind": "if", "matched": False, "elapsed_ms": 0.0}
                )
        else:
            _run_one(line_no, statement, guarded=False)

    receipt["output"] = output
    receipt["variables"] = {
        name: value[:RESPONSE_CLIP] for name, value in variables.items()
    }
    receipt["ok"] = not receipt["errors"]
    receipt["status"] = "completed" if receipt["ok"] else "completed with errors"
    return _finish(receipt, write_receipt)


def _finish(receipt: dict[str, Any], write: bool) -> dict[str, Any]:
    receipt["finished_at_utc"] = _now()
    if write:
        try:
            RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            path = RECEIPT_DIR / f"ENGEL_SCRIPT_RUN_{stamp}.json"
            path.write_text(
                json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            receipt["receipt_path"] = str(path)
        except Exception as exc:  # noqa: BLE001 -- a receipt-write failure is reported, not fatal
            receipt["receipt_write_error"] = str(exc)
    return receipt


# ---------------------------------------------------------------------------
# Plan library (run BY NAME: the router strips dots/newlines, so file paths
# cannot survive the phrase surface).
# ---------------------------------------------------------------------------
def load_plan(name: str) -> str | None:
    clean = str(name or "").strip().lower()
    if not _PLAN_NAME_RE.match(clean):
        return None
    path = (SCRIPT_DIR / f"{clean}.engel").resolve()
    try:
        path.relative_to(SCRIPT_DIR.resolve())
    except ValueError:
        return None
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def list_plans() -> list[str]:
    if not SCRIPT_DIR.is_dir():
        return []
    return sorted(p.stem for p in SCRIPT_DIR.glob("*.engel"))


# ---------------------------------------------------------------------------
# Route render functions (engel.script.*).
# ---------------------------------------------------------------------------
_ALIAS_PREFIXES = (
    "validate engel script", "engel script validate",
    "run engel script", "engel script run",
)


def _payload(text: str) -> str:
    low = str(text or "").strip()
    for prefix in _ALIAS_PREFIXES:
        if low.lower().startswith(prefix):
            return low[len(prefix):].strip()
    return ""


def render_engel_script_docs(text: str = "") -> str:
    return (
        "EngelScript v1 -- Engel AI Main's own plan language.\n"
        "Composes the 490-route library, the SLM roster, and the receipts culture\n"
        "into one auditable artifact. Full spec: docs/ENGEL_SCRIPT_LANGUAGE.md\n\n"
        "Statements (one per line; ';' also separates; '#' comments):\n"
        '  plan "title"                       name the run\n'
        "  let $name = <expr>                 bind a string\n"
        '  ask $name = route "<phrase>"       run a registry route, capture reply\n'
        '  route "<phrase>"                   run a route, discard capture\n'
        '  ask $name = intent "<text>"        SLM route-intent label (advisory)\n'
        '  if $name contains "t" then <stmt>  guard one statement (misses = negated)\n'
        "  say <expr>                         append to the visible output\n\n"
        'Expressions: "literals" and $variables joined with +.\n'
        "Safety: every route step is checked against the registry's own flags\n"
        "BEFORE running; non-read-only routes are blocked and receipted. Caps:\n"
        f"{MAX_STATEMENTS} statements, {MAX_SOURCE_BYTES} bytes, {MAX_VARS} vars, "
        f"{MAX_WALL_SECONDS:g}s.\n"
        "Run by name: 'run engel script <plan_name>' loads memory/engel_scripts/"
        "<plan_name>.engel.\nReceipts: reports/engel_script/."
    )


def render_engel_script_examples(text: str = "") -> str:
    plans = list_plans()
    lines = [
        "EngelScript example plans (memory/engel_scripts/):",
        *(f"  - {name}   (run engel script {name})" for name in plans),
        "",
        "Inline one-liner (';' separates statements):",
        '  run engel script ask $s = route "engel status"; say "status: " + $s',
        "",
        "Receipts land in reports/engel_script/.",
    ]
    if not plans:
        lines.insert(1, "  (none found)")
    return "\n".join(lines)


def resolve_body(body: str) -> tuple[str, str]:
    """(label, source) for a name-or-inline body. A bare plan name loads from
    memory/engel_scripts; anything else is inline source. Shared by the route
    surface (normalized payload) and the chat surface (raw text, which is the
    one place inline multi-line scripts survive)."""
    clean = str(body or "").strip()
    plan = load_plan(clean)
    if plan is not None:
        return f"plan '{clean.lower()}'", plan
    return "inline source", clean


def render_validate_body(body: str) -> str:
    label, source = resolve_body(body)
    statements, errors = parse_engel_script(source)
    lines = [f"EngelScript validation -- {label}"]
    if errors:
        lines.append(f"INVALID ({len(errors)} error(s)):")
        lines.extend(f"  - {error}" for error in errors)
        return "\n".join(lines)
    lines.append(f"VALID: {len(statements)} statement(s).")
    for line_no, statement in statements:
        if statement[0] in ("route", "ask_route"):
            expr = statement[1] if statement[0] == "route" else statement[2]
            literal_only = all(kind == "lit" for kind, _ in expr)
            if literal_only:
                phrase = "".join(part for _, part in expr)
                safety = route_step_safety(phrase)
                verdict = "would run" if safety["allowed"] else f"BLOCKED ({safety['reason']})"
                lines.append(f"  line {line_no}: route {phrase!r} -> {verdict}")
            else:
                lines.append(
                    f"  line {line_no}: route phrase uses variables -- checked at run time"
                )
    return "\n".join(lines)


def render_engel_script_validate(text: str = "") -> str:
    body = _payload(text)
    if not body:
        return (
            "Usage: validate engel script <plan_name or inline source>\n"
            + render_engel_script_examples()
        )
    return render_validate_body(body)


def render_engel_script_run(text: str = "") -> str:
    body = _payload(text)
    if not body:
        return (
            "Usage: run engel script <plan_name or inline source>\n"
            + render_engel_script_examples()
        )
    return render_run_body(body)


def render_run_body(body: str) -> str:
    label, source = resolve_body(body)
    receipt = execute_engel_script(source, allow_actions=False)
    lines = [f"EngelScript run -- {label} [{receipt['status']}]"]
    if receipt.get("plan_title"):
        lines[0] += f" -- {receipt['plan_title']}"
    for error in receipt["errors"]:
        lines.append(f"  error: {error}")
    for step in receipt["steps"]:
        if step.get("blocked"):
            lines.append(
                f"  line {step['line']}: BLOCKED {step.get('route_id') or step.get('phrase', '')}"
                f" -- {step.get('reason', '')}"
            )
    if receipt["output"]:
        lines.append("Output:")
        lines.extend(f"  {line}" for line in receipt["output"])
    else:
        lines.append("Output: (script produced no say lines)")
    executed = sum(
        1 for step in receipt["steps"] if step.get("kind") in ("route", "ask_route") and not step.get("blocked")
    )
    blocked = sum(1 for step in receipt["steps"] if step.get("blocked"))
    lines.append(
        f"Steps: {len(receipt['steps'])} total, {executed} route(s) executed, "
        f"{blocked} blocked. Receipt: {receipt.get('receipt_path', '(not written)')}"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Draft support: a model EMITS a plan, the validator referees, and a valid
# draft is saved as a named plan (candidate-output pattern -- never auto-run).
# The LLM call itself lives with the caller (the chat worker); this module
# stays deterministic.
# ---------------------------------------------------------------------------
# Wording is deliberately free of the chat action lane's build vocabulary
# (write/create/build/generate + "a script"/"a tool"): the 2026-07-31 live
# proof showed the drafting instruction itself being classified as a build
# order. The worker also passes chat_only for this call; this is the belt.
GRAMMAR_CARD = (
    "EngelScript grammar (reply with only the EngelScript text, nothing else):\n"
    'plan "short title"\n'
    'ask $name = route "<registry phrase>"   # e.g. "engel status", '
    '"android workers status", "system integration status"\n'
    'say "label: " + $name\n'
    'if $name contains "text" then say "note"   # misses = negated\n'
    "Rules: one statement per line; strings + $variables joined with +; no "
    "loops, no nesting, and there is NO else (use a second if with misses for "
    "the negative case); set a variable before reading it; at most 20 lines."
)


def draft_prompt(goal: str) -> str:
    """Grammar card + the REAL routes retrieved for this goal.

    Before the capability index existed, this card could only offer three
    hard-coded example phrases against a 517-route library, so a drafted plan
    was a guess. Now the top executable routes for the goal are retrieved and
    named, which is what lets a plan actually use Engel's parts. Retrieval is
    best-effort: if the index is unavailable the card degrades to the examples.
    """
    goal_text = str(goal or "").strip()
    phrasebook = ""
    try:
        from engel_capability_index import capability_phrasebook_text

        phrasebook = capability_phrasebook_text(goal_text, limit=6)
    except Exception:  # noqa: BLE001 -- drafting still works without retrieval
        phrasebook = ""
    parts = [
        "Compose an EngelScript plan for this goal. "
        "Reply with ONLY the EngelScript text: no explanation, no code fences.",
        "",
        GRAMMAR_CARD,
    ]
    if phrasebook:
        parts += ["", phrasebook]
    parts += ["", "Goal: " + goal_text]
    return "\n".join(parts)


_STATEMENT_HEAD_RE = re.compile(r'(?:plan\s+"|let\s+\$|ask\s+\$|route\s+"|say\s+"|if\s+\$)')


def _resplit_single_line_script(text: str) -> str:
    """Small local models emit the whole plan on ONE line despite instructions
    (observed live 2026-07-31). Re-break it: at whitespace OUTSIDE quoted
    literals, start a new line when the next token opens a statement. Quote-
    aware so 'say "plan your day"' never splits inside the literal."""
    out: list[str] = []
    in_quote = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '"':
            in_quote = not in_quote
            out.append(ch)
            i += 1
            continue
        if not in_quote and ch.isspace():
            rest = text[i:].lstrip()
            # `if ... then <stmt>` keeps its guarded statement on the SAME line.
            tail = "".join(out).rsplit("\n", 1)[-1]
            inside_if = tail.lstrip().lower().startswith("if ") and " then " not in tail.lower()
            stripped_tail = tail.rstrip().lower()
            if (
                _STATEMENT_HEAD_RE.match(rest)
                and out
                and not inside_if
                and not stripped_tail.endswith(" then")
                # `ask $x = route "..."`: the verb after '=' is the ask's own,
                # not a new statement.
                and not stripped_tail.endswith("=")
                # keep `... else say "..."` whole for the desugar pass below
                and not stripped_tail.endswith(" else")
            ):
                out.append("\n")
                i += len(text[i:]) - len(rest)
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def extract_script_from_reply(reply: str) -> str:
    """Pull the script out of a model reply: prefer a fenced block, else take
    the lines that look like statements (models narrate despite instructions),
    then re-split a one-line emission into statements."""
    text = str(reply or "").strip()
    fence = re.search(r"```(?:engelscript|engel|text)?\s*\n(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    else:
        keeps = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            head = stripped.split(None, 1)[0].lower()
            if head in ("plan", "let", "ask", "route", "say", "if", "#"):
                keeps.append(stripped)
        text = "\n".join(keeps) if keeps else text
    text = "\n".join(
        _resplit_single_line_script(line) if _STATEMENT_HEAD_RE.search(line[4:]) else line
        for line in text.splitlines()
    )
    return "\n".join(_desugar_else(line) for line in text.splitlines())


_ELSE_RE = re.compile(
    r'^(if\s+\$[A-Za-z_][A-Za-z0-9_]*\s+)(contains|misses)(\s+"[^"]*"\s+then\s+)'
    r"(.+?)\s+else\s+(.+)$",
    re.IGNORECASE,
)
_CONTAINS_MISSES_RE = re.compile(
    r'^(if\s+\$[A-Za-z_][A-Za-z0-9_]*\s+)contains(\s+"[^"]*")\s+misses(\s+then\s+.+)$',
    re.IGNORECASE,
)


def _desugar_else(line: str) -> str:
    """Models keep writing `else` (2 of 2 live drafts, 2026-07-31) though the
    grammar has none. Desugar it FAITHFULLY into the misses form:
    `if $x contains "y" then A else B` == the contains-guard for A plus the
    misses-guard for B. Semantics-preserving, so a drafted intent survives
    validation instead of failing on vocabulary the card told it not to use."""
    stripped = line.strip()
    mashed = _CONTAINS_MISSES_RE.match(stripped)
    if mashed:
        # Live 2026-09-20 drafts: `if $x contains "y" misses then B`
        return f"{mashed.group(1)}misses{mashed.group(2)}{mashed.group(3)}"
    match = _ELSE_RE.match(stripped)
    if not match:
        return line
    head, op, mid, then_branch, else_branch = match.groups()
    inverted = "misses" if op.lower() == "contains" else "contains"
    if " else " in f" {then_branch} " or " else " in f" {else_branch} ":
        return line  # nested else chains stay as-is and fail loudly
    return f"{head}{op}{mid}{then_branch}\n{head}{inverted}{mid}{else_branch}"


def render_draft_result(goal: str, model_reply: str) -> str:
    """Validate a model-drafted plan; save it as a runnable named draft ONLY
    when it parses clean. Never runs anything."""
    source = extract_script_from_reply(model_reply)
    if not source.strip():
        return "EngelScript draft: the model returned no usable script text."
    statements, errors = parse_engel_script(source)
    lines = [f"EngelScript draft for goal: {str(goal or '').strip()}", "", source, ""]
    if errors:
        lines.append(f"Draft is INVALID ({len(errors)} error(s)) -- not saved:")
        lines.extend(f"  - {error}" for error in errors)
        return "\n".join(lines)
    name = "draft_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ").lower()
    saved = ""
    try:
        SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        (SCRIPT_DIR / f"{name}.engel").write_text(source + "\n", encoding="utf-8")
        saved = name
    except OSError as exc:
        lines.append(f"(draft could not be saved: {exc})")
    lines.append(f"Draft is VALID ({len(statements)} statement(s)).")
    lines.append(render_validate_body(source).split("\n", 1)[-1])
    if saved:
        lines.append(f"Saved as plan '{saved}' -- run it with: run engel script {saved}")
    lines.append("Drafts never run automatically.")
    return "\n".join(lines)
