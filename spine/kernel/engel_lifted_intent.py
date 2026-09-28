"""Engel HIPL/MIPL lifted-intent bridge.

HIPL is Engel's human-intended surface: the operator expresses a goal and later
reads what the machine actually understood and proved.  MIPL is a small,
machine-intended intermediate representation.  It is deliberately *not* an
executor and never grants authority.  Existing Engel routes, the Governor,
EngelScript, and the Agent Kernel retain execution ownership.

The shared object between both sides is a deterministic ``lifted_intent``.
Every completed bridge receipt hash-links the redacted human expression, the
lifted intent, the MIPL program, and the bounded machine result.  This gives
Engel a replayable answer to "what did you understand, what did you do, and
what proves it?" without asking an opaque model to authorize itself.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import engel_mipl


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
RECEIPT_DIR = ROOT / "reports" / "engel_lifted_intent"
LATEST_RECEIPT = RECEIPT_DIR / "LATEST.json"
MAX_EXPRESSION_CHARS = 16_384
MAX_RESULT_TEXT_CHARS = 800
MAX_PROOF_PATHS = 12

CONTRACT_SCHEMA = "engel_lifted_intent_contract_v1"
MIPL_SCHEMA = engel_mipl.IR_SCHEMA
RECEIPT_SCHEMA = "engel_lifted_intent_receipt_v1"

_ACTION_EFFECTS = frozenset(
    ("create", "mutate", "dispatch", "train", "remember", "install", "execute")
)
_EFFECT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("train", re.compile(r"\b(?:train|retrain|fine[- ]?tune|lora)\b", re.I)),
    ("install", re.compile(r"\b(?:install|deploy|promote|publish)\b", re.I)),
    (
        "dispatch",
        re.compile(
            r"\b(?:have|ask|tell|send|dispatch|assign|route)\b[^.!?]{0,90}"
            r"\b(?:worker|agent|device|phone|sub[- ]?engel|alpha|beta|gamma|fleet)\b",
            re.I,
        ),
    ),
    ("remember", re.compile(r"\b(?:remember|save to memory|trusted memory)\b", re.I)),
    (
        "mutate",
        re.compile(
            r"\b(?:fix|repair|change|edit|modify|delete|remove|replace|rename|"
            r"start|stop|restart|enable|disable|write to)\b",
            re.I,
        ),
    ),
    (
        "create",
        re.compile(
            r"\b(?:create|build|make|implement|develop|generate|write|scaffold)\b",
            re.I,
        ),
    ),
    (
        "inspect",
        re.compile(r"\b(?:check|inspect|verify|audit|review|diagnose|status|list|find|show)\b", re.I),
    ),
    (
        "answer",
        re.compile(r"^(?:what|how|why|when|where|which|who|explain|describe|tell me about)\b", re.I),
    ),
)

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passphrase|secret|token|api[ _-]?key|private[ _-]?key)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{8,}")
_OPENAI_STYLE_KEY = re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")
_WINDOWS_PATH = re.compile(r"\b[A-Za-z]:\\[^\r\n<>|\"]{1,240}")
_UNIX_PATH = re.compile(r"(?<!\w)/(?:[A-Za-z0-9._-]+/){1,12}[A-Za-z0-9._-]+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _one_line(value: Any, limit: int = MAX_EXPRESSION_CHARS) -> str:
    return " ".join(str(value or "").split())[:limit]


def redact_expression(value: Any) -> str:
    """Return bounded local receipt text with common credential forms removed."""
    text = str(value or "")[:MAX_EXPRESSION_CHARS]
    text = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", text)
    text = _BEARER.sub("Bearer [REDACTED]", text)
    text = _OPENAI_STYLE_KEY.sub("[REDACTED_API_KEY]", text)
    return text.strip()


def _effect(text: str) -> tuple[str, str]:
    for name, pattern in _EFFECT_RULES:
        match = pattern.search(text)
        if match:
            return name, f"effect.{name}:{match.group(0).casefold()}"
    return "converse", "effect.converse:default"


def _targets(text: str) -> list[str]:
    low = text.casefold()
    targets: list[str] = []
    for path in _WINDOWS_PATH.findall(text) + _UNIX_PATH.findall(text):
        clean = path.rstrip(".,;:)")
        if clean and clean not in targets:
            targets.append(clean)
    named = (
        ("fleet", ("every device", "all devices", "all workers", "whole fleet")),
        ("sub-engel", ("sub-engel", "sub engel")),
        ("android-alpha", ("alpha", "android worker alpha")),
        ("android-beta", ("beta", "android worker beta")),
        ("android-gamma", ("gamma", "android worker gamma")),
        ("engel-ai-main", ("engel ai main", "engel main")),
        ("training", ("training", "model training", "prompt training")),
    )
    for label, phrases in named:
        if any(phrase in low for phrase in phrases) and label not in targets:
            targets.append(label)
    return targets[:12] or ["unspecified"]


def _explicit_constraints(text: str) -> list[str]:
    constraints: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        clean = _one_line(sentence, 320)
        low = clean.casefold()
        if clean and any(
            marker in low
            for marker in (
                "must ", "should ", "only ", "do not ", "don't ", "never ",
                "without ", "keep ", "preserve ", "before ", "after ", "local-only",
                "local only", "exact ", "1-", "hours", "per hour",
            )
        ):
            constraints.append(clean)
    fixed = [
        "Existing Engel authority, Governor, and route gates remain authoritative.",
        "Intent classification does not grant approval or prove completion.",
        "A successful action requires a verifiable result or receipt.",
    ]
    for item in fixed:
        if item not in constraints:
            constraints.append(item)
    return constraints[:12]


def _acceptance_criteria(text: str, effect: str) -> list[str]:
    criteria = [
        "Return a bounded comprehension summary to the human-facing surface.",
        "Name the final status and the receipt or verifier that supports it.",
    ]
    low = text.casefold()
    if any(word in low for word in ("verify", "proof", "test", "receipt", "audit")):
        criteria.append("Preserve the requested verification evidence and failed checks.")
    if effect in _ACTION_EFFECTS:
        criteria.extend(
            (
                "Do not perform side effects unless the existing deterministic gate allows them.",
                "Do not report an intended or attempted action as a completed action.",
            )
        )
    else:
        criteria.append("Do not invent system state that no local source confirms.")
    return criteria


def _planner_advisory(text: str) -> dict[str, Any]:
    """Reuse the legacy deterministic planner as an advisory, never authority."""
    try:
        import engel_ai_intent_planner as planner

        plan = planner.build_plan(text)
        return {
            "available": True,
            "intent_type": str(plan.intent_type),
            "matched_route": str(plan.matched_route),
            "risk_level": str(plan.risk_level),
            "approval_required": bool(plan.approval_required),
            "blocked": bool(plan.blocked),
            "proceed_allowed": bool(plan.proceed_allowed),
            "advisory_only": True,
        }
    except Exception as exc:
        return {
            "available": False,
            "error": f"{type(exc).__name__}: {str(exc)[:160]}",
            "advisory_only": True,
        }


def create_intent_contract(
    expression: Any,
    *,
    caller: str = "engel_main",
    request_id: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Lift one human expression into deterministic shared intent + MIPL IR."""
    redacted = redact_expression(expression)
    normalized = _one_line(redacted).casefold()
    effect, rule_id = _effect(normalized)
    side_effect = effect in _ACTION_EFFECTS
    targets = _targets(redacted)
    constraints = _explicit_constraints(redacted)
    acceptance = _acceptance_criteria(redacted, effect)
    planner = _planner_advisory(redacted)
    expression_record = {
        "text": redacted,
        "normalized": normalized,
        "redacted": redacted != str(expression or "").strip(),
    }
    expression_hash = _hash(expression_record)
    lifted = {
        "objective": _one_line(redacted, 2_000),
        "effect": effect,
        "effect_rule_id": rule_id,
        "targets": targets,
        "constraints": constraints,
        "acceptance_criteria": acceptance,
        "side_effect_requested": side_effect,
        "approval_required": bool(side_effect or planner.get("approval_required")),
        "authority": "human_operator > guardian > governor > runtime",
        "ambiguity": "open" if targets == ["unspecified"] and effect not in ("answer", "converse") else "bounded",
        "planner_advisory": planner,
    }
    lifted_hash = _hash(lifted)
    mipl = engel_mipl.compile_intent_ir(
        expression_hash=expression_hash,
        lifted_intent_hash=lifted_hash,
        effect=effect,
        targets=targets,
        criteria=acceptance,
        approval_required=bool(side_effect or planner.get("approval_required")),
    )
    mipl_hash = _hash(mipl)
    contract_hash = _hash(
        {
            "expression_hash": expression_hash,
            "lifted_intent_hash": lifted_hash,
            "mipl_hash": mipl_hash,
        }
    )
    contract_id = "intent_" + contract_hash[:20]
    safe_metadata = {
        str(key)[:80]: _one_line(value, 240)
        for key, value in (metadata or {}).items()
        if str(key) in {"conversation_id", "training_run_id", "training_discipline", "interactive"}
    }
    return {
        "schema": CONTRACT_SCHEMA,
        "contract_id": contract_id,
        "created_at_utc": _now(),
        "caller": _one_line(caller, 120),
        "request_id": _one_line(request_id, 160),
        "metadata": safe_metadata,
        "hipl": {
            "language": "human-intended",
            "expression": expression_record,
            "return_channel": "comprehension",
        },
        "lifted_intent": lifted,
        "mipl": mipl,
        "hash_chain": {
            "expression_hash": expression_hash,
            "lifted_intent_hash": lifted_hash,
            "mipl_hash": mipl_hash,
            "contract_hash": contract_hash,
        },
    }


def _proof_paths(result: Mapping[str, Any]) -> list[str]:
    paths: list[str] = []

    def visit(value: Any, key: str = "") -> None:
        if len(paths) >= MAX_PROOF_PATHS:
            return
        if isinstance(value, Mapping):
            for child_key, child in value.items():
                visit(child, str(child_key))
        elif isinstance(value, list):
            for child in value[:20]:
                visit(child, key)
        elif isinstance(value, str) and (
            "path" in key.casefold()
            or "receipt" in key.casefold()
            or value.casefold().endswith((".json", ".jsonl", ".md", ".log"))
        ):
            clean = value.strip()[:500]
            if clean and clean not in paths:
                paths.append(clean)

    visit(result)
    return paths


def _result_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    nested = result.get("receipt") if isinstance(result.get("receipt"), Mapping) else {}
    status = str(result.get("status") or nested.get("status") or "unknown")[:240]
    reply = str(
        result.get("assistant_reply")
        or result.get("assistant_output_text")
        or nested.get("assistant_reply")
        or nested.get("assistant_output_text")
        or ""
    )
    engines = result.get("engines_used") or nested.get("engines_used") or []
    if not isinstance(engines, list):
        engines = [str(engines)] if engines else []
    return {
        "ok": bool(result.get("ok") is True or nested.get("ok") is True),
        "status": status,
        "summary": _one_line(reply, MAX_RESULT_TEXT_CHARS),
        "engines_used": [_one_line(value, 100) for value in engines[:8]],
        "proof_paths": _proof_paths(result),
    }


def validate_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Replay all deterministic hashes without trusting stored pass flags."""
    try:
        hipl = contract["hipl"]
        lifted = contract["lifted_intent"]
        mipl = contract["mipl"]
        chain = contract["hash_chain"]
        expression_hash = _hash(hipl["expression"])
        lifted_hash = _hash(lifted)
        mipl_hash = _hash(mipl)
        mipl_validation = engel_mipl.validate_ir(mipl)
        contract_hash = _hash(
            {
                "expression_hash": expression_hash,
                "lifted_intent_hash": lifted_hash,
                "mipl_hash": mipl_hash,
            }
        )
        checks = {
            "expression_hash": expression_hash == chain.get("expression_hash"),
            "lifted_intent_hash": lifted_hash == chain.get("lifted_intent_hash"),
            "mipl_hash": mipl_hash == chain.get("mipl_hash"),
            "contract_hash": contract_hash == chain.get("contract_hash"),
            "mipl_non_authorizing": mipl.get("execution_authorized") is False,
            "mipl_packet_integrity": mipl_validation.get("ok") is True,
        }
        return {"ok": all(checks.values()), "checks": checks}
    except (KeyError, TypeError, AttributeError) as exc:
        return {"ok": False, "checks": {}, "error": f"{type(exc).__name__}: {exc}"}


def complete_intent_receipt(
    contract: Mapping[str, Any],
    machine_result: Mapping[str, Any],
    *,
    write_receipt: bool = True,
) -> dict[str, Any]:
    """Bind the machine result back to HIPL and optionally persist atomically."""
    contract_copy = json.loads(json.dumps(contract, ensure_ascii=False))
    validation = validate_contract(contract_copy)
    result = _result_summary(machine_result)
    result_hash = _hash(result)
    contract_hash = str((contract_copy.get("hash_chain") or {}).get("contract_hash") or "")
    mipl_outcome = engel_mipl.compile_outcome_ir(
        request_hash=contract_hash,
        ok=result["ok"],
        status=result["status"],
        result_hash=result_hash,
        proof_paths=result["proof_paths"],
        error=result["summary"],
    )
    mipl_outcome_hash = _hash(mipl_outcome)
    mipl_outcome_validation = engel_mipl.validate_ir(mipl_outcome)
    audit_head = _hash(
        {
            "contract_hash": contract_hash,
            "result_hash": result_hash,
            "mipl_outcome_hash": mipl_outcome_hash,
        }
    )
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "finished_at_utc": _now(),
        "contract": contract_copy,
        "mipl_outcome": mipl_outcome,
        "machine_result": result,
        "hipl_comprehension": {
            "understood_objective": str((contract_copy.get("lifted_intent") or {}).get("objective") or ""),
            "effect": str((contract_copy.get("lifted_intent") or {}).get("effect") or ""),
            "status": result["status"],
            "succeeded": result["ok"],
            "proof_paths": result["proof_paths"],
            "honesty": "verified result" if result["proof_paths"] else "status reported; no proof path surfaced",
        },
        "verification": {
            "contract_valid": validation.get("ok") is True,
            "contract_checks": validation.get("checks", {}),
            "result_hash": result_hash,
            "mipl_outcome_hash": mipl_outcome_hash,
            "mipl_outcome_valid": mipl_outcome_validation.get("ok") is True,
            "audit_head": audit_head,
            "audit_complete": validation.get("ok") is True
            and mipl_outcome_validation.get("ok") is True
            and bool(result["status"]),
        },
    }
    if write_receipt:
        _write_receipt(receipt)
    return receipt


def _write_receipt(receipt: dict[str, Any]) -> None:
    try:
        RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
        contract = receipt.get("contract") or {}
        contract_id = str(contract.get("contract_id") or "intent_unknown")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = RECEIPT_DIR / f"INTENT_{stamp}_{contract_id[-12:]}.json"
        receipt["receipt_path"] = str(path)
        payload = json.dumps(receipt, indent=2, ensure_ascii=False)
        temp = path.with_suffix(".tmp")
        temp.write_text(payload, encoding="utf-8")
        temp.replace(path)
        latest_temp = LATEST_RECEIPT.with_suffix(".tmp")
        latest_temp.write_text(payload, encoding="utf-8")
        latest_temp.replace(LATEST_RECEIPT)
    except OSError as exc:
        receipt["receipt_path"] = ""
        receipt["write_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"


def attach_intent_to_response(
    payload: Mapping[str, Any],
    response: Mapping[str, Any],
    *,
    caller: str | None = None,
) -> dict[str, Any]:
    """Attach one HIPL/MIPL audit receipt to a worker response.

    A child Agent Kernel receipt may already own the intent contract.  In that
    case it is promoted instead of generating a misleading duplicate contract.
    """
    out = dict(response)
    nested = out.get("receipt") if isinstance(out.get("receipt"), Mapping) else {}
    existing_path = str(
        out.get("lifted_intent_receipt_path") or nested.get("lifted_intent_receipt_path") or ""
    )
    existing_summary = (
        out.get("lifted_intent")
        if isinstance(out.get("lifted_intent"), Mapping)
        else nested.get("lifted_intent")
    )
    if existing_path and isinstance(existing_summary, Mapping):
        out["lifted_intent"] = dict(existing_summary)
        out["lifted_intent_receipt_path"] = existing_path
        for key in ("lnt", "mipl_compiler", "slm_router_advisory"):
            if out.get(key) is None and nested.get(key) is not None:
                out[key] = nested.get(key)
        return out
    prompt = payload.get("prompt") or payload.get("text") or ""
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
    contract = create_intent_contract(
        prompt,
        caller=str(caller or payload.get("caller") or "engel_main_local_model_worker"),
        request_id=str(payload.get("id") or payload.get("request_id") or ""),
        metadata=metadata,
    )
    receipt = complete_intent_receipt(contract, out, write_receipt=True)
    lifted = contract["lifted_intent"]
    out["lifted_intent"] = {
        "contract_id": contract["contract_id"],
        "objective": lifted["objective"],
        "effect": lifted["effect"],
        "targets": lifted["targets"],
        "approval_required": lifted["approval_required"],
        "audit_head": receipt["verification"]["audit_head"],
    }
    out["lifted_intent_receipt_path"] = receipt.get("receipt_path", "")
    out["lifted_intent_audit_complete"] = receipt["verification"]["audit_complete"]
    return out


# intent_router labels vs deterministic LNT effects. Observation only.
_SLM_LNT_COMPAT = {
    "chat": frozenset({"converse", "answer", "inspect"}),
    "build": frozenset({"create", "mutate", "inspect", "execute"}),
    "training_job": frozenset({"train", "inspect"}),
    "meeting_room": frozenset({"dispatch", "inspect", "converse"}),
}


def observe_slm_vs_lnt(
    slm_advisory: Mapping[str, Any] | None,
    lnt_effect: Any,
) -> dict[str, Any]:
    """Compare SLM intent_router label to LNT effect without mutating hashes."""
    advisory = dict(slm_advisory) if isinstance(slm_advisory, Mapping) else {}
    intent = advisory.get("intent") if isinstance(advisory.get("intent"), Mapping) else {}
    label = str(intent.get("label") or "").strip().casefold()
    effect = str(lnt_effect or "").strip().casefold()
    expected = _SLM_LNT_COMPAT.get(label)
    observation = {
        "compared": bool(label and effect and expected is not None),
        "slm_label": label or None,
        "lnt_effect": effect or None,
        "compatible": bool(expected is not None and effect in expected),
        "does_not_mutate_hashes": True,
        "does_not_authorize_execution": True,
    }
    if not label:
        observation["reason"] = "slm_absent_or_unlabeled"
    elif expected is None:
        observation["reason"] = "unknown_slm_label"
    return observation


def stamp_slm_compiler_lnt(
    response: Mapping[str, Any],
    slm_advisory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind SLM router + MIPL compiler + LNT keys without recompiling."""
    out = dict(response)
    lifted = out.get("lifted_intent") if isinstance(out.get("lifted_intent"), Mapping) else {}
    advisory = dict(slm_advisory) if isinstance(slm_advisory, Mapping) else {}
    out["lnt"] = {
        "name": "lifted_intent",
        "contract_id": lifted.get("contract_id"),
        "effect": lifted.get("effect"),
        "approval_required": lifted.get("approval_required"),
        "audit_head": lifted.get("audit_head"),
        "execution_authorized": False,
    }
    out["mipl_compiler"] = {
        "compiler": "deterministic-standard-library",
        "language": str(getattr(engel_mipl, "LANGUAGE", "Engel MIPL")),
        "version": int(getattr(engel_mipl, "VERSION", 2) or 2),
        "profile": str(getattr(engel_mipl, "PROFILE", "mipl2-low-resource")),
        "execution_authorized": False,
        "dispatch_authorization": "external_gate_required",
        "receipt_path": out.get("lifted_intent_receipt_path") or "",
    }
    out["slm_router_advisory"] = {
        "ready": bool(advisory.get("ready")),
        "intent": advisory.get("intent"),
        "route_shadow": advisory.get("route_shadow"),
        "governor_outcome": advisory.get("governor_outcome"),
        "authority": "advisory_only",
        "does_not_authorize_mipl": True,
        "does_not_mutate_lnt": True,
        "does_not_select_model": True,
        "slm_vs_lnt": observe_slm_vs_lnt(advisory, lifted.get("effect")),
    }
    return out


def attach_slm_compiler_lnt(
    prompt: str,
    response: Mapping[str, Any],
    *,
    caller: str = "engel_ai_main",
    request_id: str = "",
    metadata: Mapping[str, Any] | None = None,
    slm_advisory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind SLM router advice beside MIPL compile + Lifted iNTent (LNT).

    The SLM never mutates the lifted intent or MIPL hashes. The compiler never
    grants execution. Fail-open: a missing SLM still compiles LNT/MIPL.
    """
    payload = {
        "prompt": prompt,
        "id": request_id,
        "caller": caller,
        "metadata": dict(metadata or {}),
    }
    out = attach_intent_to_response(payload, response, caller=caller)
    return stamp_slm_compiler_lnt(out, slm_advisory)


def load_latest_receipt() -> dict[str, Any] | None:
    try:
        value = json.loads(LATEST_RECEIPT.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError):
        return None
    return value if isinstance(value, dict) and value.get("schema") == RECEIPT_SCHEMA else None


def render_docs(_text: str = "") -> str:
    return "\n".join(
        (
            "Engel HIPL / MIPL Intent Bridge",
            "",
            "HIPL is the human-facing expression and comprehension surface. The shared lifted intent preserves the objective, targets, constraints, and proof criteria. Engel MIPL IR carries that contract toward the existing Governor and Agent Kernel.",
            "",
            "Safety:",
            "- MIPL is non-authorizing and cannot execute a route by itself.",
            "- Existing Guardian, Governor, approval, route, and sandbox gates remain authoritative.",
            "- Every completed bridge receipt hash-links expression -> intent -> MIPL -> result.",
            "- Common credential forms are redacted before local receipt persistence.",
            "",
            engel_mipl.render_reference(),
            "",
            "Commands: intent bridge status; latest lifted intent; lift intent <request>; compile mipl <request>.",
        )
    )


def render_status(_text: str = "") -> str:
    latest = load_latest_receipt()
    count = len(list(RECEIPT_DIR.glob("INTENT_*.json"))) if RECEIPT_DIR.is_dir() else 0
    if latest is None:
        return "Engel Intent Bridge\n\nStatus: READY\nReceipts: 0\nNo completed lifted intent has been recorded yet."
    contract = latest.get("contract") or {}
    lifted = contract.get("lifted_intent") or {}
    verification = latest.get("verification") or {}
    mipl = contract.get("mipl") or {}
    profile = engel_mipl.runtime_profile(mipl) if mipl else engel_mipl.runtime_profile()
    return "\n".join(
        (
            "Engel Intent Bridge",
            "",
            "Status: READY",
            f"Receipts: {count}",
            f"Latest: {contract.get('contract_id', '')}",
            f"Effect: {lifted.get('effect', '')}",
            f"Objective: {lifted.get('objective', '')}",
            f"Audit complete: {'yes' if verification.get('audit_complete') else 'no'}",
            f"MIPL: v{mipl.get('version', engel_mipl.VERSION)} · {profile.get('packet_count', 0)} packets · {profile.get('encoded_bytes', 0)} bytes",
            f"Receipt: {latest.get('receipt_path') or LATEST_RECEIPT}",
        )
    )


def render_latest(_text: str = "") -> str:
    latest = load_latest_receipt()
    if latest is None:
        return "No completed lifted intent has been recorded yet."
    contract = latest.get("contract") or {}
    lifted = contract.get("lifted_intent") or {}
    comprehension = latest.get("hipl_comprehension") or {}
    mipl = contract.get("mipl") or {}
    profile = engel_mipl.runtime_profile(mipl) if mipl else engel_mipl.runtime_profile()
    return "\n".join(
        (
            "Latest Lifted Intent",
            "",
            f"Human objective: {lifted.get('objective', '')}",
            f"Effect: {lifted.get('effect', '')}",
            "Targets: " + ", ".join(str(value) for value in lifted.get("targets", [])),
            f"Machine result: {comprehension.get('status', '')}",
            f"Succeeded: {'yes' if comprehension.get('succeeded') else 'no'}",
            f"MIPL: v{mipl.get('version', engel_mipl.VERSION)} · {profile.get('packet_count', 0)} packets · {profile.get('encoded_bytes', 0)} bytes",
            f"Proof: {', '.join(str(value) for value in comprehension.get('proof_paths', [])) or 'no proof path surfaced'}",
            f"Receipt: {latest.get('receipt_path') or LATEST_RECEIPT}",
        )
    )


def render_lift(text: str = "") -> str:
    expression = re.sub(
        r"^\s*(?:lift(?:ed)?\s+intent|intent\s+bridge\s+lift|(?:compile|write|assemble)\s+mipl)\s*[:,-]?\s*",
        "",
        str(text or ""),
        flags=re.I,
    ).strip()
    if not expression:
        return "Usage: lift intent <request>. This previews understanding only and runs nothing."
    contract = create_intent_contract(expression, caller="intent_bridge_preview")
    lifted = contract["lifted_intent"]
    mipl = contract["mipl"]
    profile = engel_mipl.runtime_profile(mipl)
    return "\n".join(
        (
            "Lifted Intent Preview (nothing executed)",
            "",
            f"Objective: {lifted['objective']}",
            f"Effect: {lifted['effect']}",
            "Targets: " + ", ".join(lifted["targets"]),
            f"Side effect requested: {'yes' if lifted['side_effect_requested'] else 'no'}",
            f"Approval/gate required: {'yes' if lifted['approval_required'] else 'no'}",
            f"Ambiguity: {lifted['ambiguity']}",
            f"MIPL: v{mipl['version']} · {profile['packet_count']} packets · {profile['encoded_bytes']} bytes",
            "Compiler: deterministic/local; no model, provider, network, or third-party package",
            f"Contract: {contract['contract_id']}",
        )
    )
