#!/usr/bin/env python3
"""Shared desktop/Discord route ledger, identity guard, and failure path."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import threading
from typing import Any

from engel_chat_failure_corpus_builder import capture_failure, redact_text


ROOT = Path(os.environ.get("ENGEL_ROOT") or Path(__file__).resolve().parents[1])
ROUTE_ROOT = Path(
    os.environ.get("ENGEL_CHAT_ROUTE_PARITY_ROOT")
    or ROOT / "run" / "self_update" / "chat_route_parity"
)
LEDGER_PATH = ROUTE_ROOT / "route_ledger.jsonl"
STATUS_PATH = ROUTE_ROOT / "status.json"
SHARED_ROUTE_CONTRACT = "ENGEL_SHARED_CHAT_ROUTE_LEDGER_V1"
SHARED_IDENTITY_GUARD = "ENGEL_SHARED_CHAT_IDENTITY_GUARD_V1"
DISCORD_IDENTITY_LOCK = "ENGEL_DISCORD_CURRENT_SENDER_IDENTITY_V1"
DISCORD_OWNER_ID = str(os.environ.get("ENGEL_DISCORD_OWNER_USER_ID") or "DISCORD_OWNER_USER_ID")
DISCORD_CHASE_ID = "189914577100603392"
DESKTOP_SOURCES = {
    "desktop_ui",
    "engel_ai_main_ui",
    "engel_flutter_main",
    "rog_desktop_controller",
    "rog_ui",
}
_LOCK = threading.RLock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _clip(value: Any, limit: int = 300) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[: max(0, limit - 3)].rstrip() + "..."


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            lock_acquired = False
            try:
                import fcntl  # Linux/CT246 cross-process lock.

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                lock_acquired = True
            except (ImportError, OSError):
                pass
            try:
                handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            finally:
                if lock_acquired:
                    try:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)  # type: ignore[name-defined]
                    except OSError:
                        pass


def request_surface(request: dict[str, Any] | None, receipt: dict[str, Any] | None = None) -> str:
    request = request if isinstance(request, dict) else {}
    receipt = receipt if isinstance(receipt, dict) else {}
    source = str(request.get("source") or request.get("client") or "").strip().casefold()
    scope = str(receipt.get("chat_context_scope") or "").strip().casefold()
    if source.startswith("discord") or scope.startswith("discord:"):
        return "discord"
    if source in DESKTOP_SOURCES or scope.startswith("engel_ai_main_desktop"):
        return "desktop"
    return "other"


def surface_identity(
    request: dict[str, Any] | None,
    receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request = request if isinstance(request, dict) else {}
    receipt = receipt if isinstance(receipt, dict) else {}
    metadata = request.get("metadata") if isinstance(request.get("metadata"), dict) else {}
    surface = request_surface(request, receipt)
    if surface == "desktop":
        return {
            "schema": SHARED_IDENTITY_GUARD,
            "surface": surface,
            "sender_id": "rog-owner",
            "resolved_actor": "joshua",
            "authority_level": "owner",
            "addressed_as": "Joshua",
            "identity_lock_valid": True,
        }
    if surface == "discord":
        sender_id = str(metadata.get("discord_author_id") or "").strip()
        lock_valid = str(metadata.get("discord_identity_lock") or "") == DISCORD_IDENTITY_LOCK
        claimed_actor = str(metadata.get("discord_resolved_actor") or "unknown_discord_user").strip()
        claimed_authority = str(metadata.get("discord_authority_level") or "guest").strip().casefold()
        owner = bool(
            lock_valid
            and sender_id == DISCORD_OWNER_ID
            and claimed_actor == "joshua"
            and claimed_authority == "owner"
        )
        actor = (
            "joshua"
            if owner
            else (
                claimed_actor
                if lock_valid and claimed_actor.casefold() not in {"joshua", "josh"}
                else "unknown_discord_user"
            )
        )
        addressed_as = str(metadata.get("discord_addressed_as") or "").strip()
        if not addressed_as:
            addressed_as = "Joshua" if owner else str(metadata.get("discord_author_display_name") or "Discord user").strip()
        # Sub-Engel is not Chase. Sender id is ground truth: never map this bot to
        # Chase/Lokal or a generic Discord guest even if its nick says Chase.
        if sender_id == "1537474262242168842":
            return {
                "schema": SHARED_IDENTITY_GUARD,
                "surface": surface,
                "sender_id": sender_id,
                "resolved_actor": "sub_engel",
                "authority_level": "peer_bot",
                "addressed_as": "Sub-Engel",
                "identity_lock_valid": lock_valid,
            }
        if sender_id == DISCORD_CHASE_ID:
            return {
                "schema": SHARED_IDENTITY_GUARD,
                "surface": surface,
                "sender_id": sender_id,
                "resolved_actor": "chase_lokal",
                "authority_level": "trusted_guest",
                "addressed_as": "Chase/Lokal",
                "identity_lock_valid": lock_valid,
            }
        return {
            "schema": SHARED_IDENTITY_GUARD,
            "surface": surface,
            "sender_id": sender_id,
            "resolved_actor": actor or "unknown_discord_user",
            "authority_level": "owner" if owner else "guest",
            "addressed_as": addressed_as or "Discord user",
            "identity_lock_valid": lock_valid,
        }
    return {
        "schema": SHARED_IDENTITY_GUARD,
        "surface": surface,
        "sender_id": "",
        "resolved_actor": "unknown_user",
        "authority_level": "guest",
        "addressed_as": "",
        "identity_lock_valid": False,
    }


def repair_joshua_chase_fusion(reply: str) -> tuple[str, bool, list[str]]:
    """Joshua is never Chase. Chase is never the owner."""
    original = str(reply or "")
    repaired = original
    repairs: list[str] = []
    substitutions = (
        (
            r"\bjoshua(?:\s+ziese)?\s*\(\s*chase(?:/lokal)?\s*\)\s+is\s+(?:the\s+)?owner\b",
            "Joshua is the owner",
            "joshua_chase_owner_fusion_repaired",
        ),
        (
            r"\bjoshua(?:\s+ziese)?\s*\(\s*chase(?:/lokal)?\s*\)",
            "Joshua",
            "joshua_chase_name_fusion_repaired",
        ),
        (
            r"\bchase(?:/lokal)?\s*\(\s*joshua(?:\s+ziese)?\s*\)",
            "Chase",
            "chase_joshua_name_fusion_repaired",
        ),
        (
            r"\bchase(?:/lokal)?\s+is\s+(?:the\s+)?owner\b",
            "Chase is a guest; Joshua is the owner",
            "chase_owner_claim_repaired",
        ),
    )
    for pattern, replacement, repair_name in substitutions:
        updated = re.sub(pattern, replacement, repaired, flags=re.IGNORECASE)
        if updated != repaired:
            repaired = updated
            if repair_name not in repairs:
                repairs.append(repair_name)
    return repaired, repaired != original, repairs


def repair_operator_address_identity(reply: str) -> tuple[str, bool]:
    """Keep Engel as the speaker instead of addressing the listener as Engel."""
    original = str(reply or "").strip()
    repaired = re.sub(
        r",\s*engel(?:\s+ai(?:\s+main)?)?\s*([.!?])?$",
        lambda match: match.group(1) or "",
        original,
        count=1,
        flags=re.IGNORECASE,
    ).strip()
    repaired = re.sub(
        r"^\s*(?:hello|hi|hey)\s+engel(?:\s+ai(?:\s+main)?)?\s*,\s*",
        "",
        repaired,
        count=1,
        flags=re.IGNORECASE,
    ).strip()
    return repaired, repaired != original


def repair_assistant_self_identity(reply: str) -> tuple[str, bool, list[str]]:
    """Keep Joshua as the operator and Engel AI Main as the assistant speaker."""
    original = str(reply or "").strip()
    repaired = original
    repairs: list[str] = []
    substitutions = (
        (r"\bI\s+am\s+(?:Joshua|Josh)\b", "I am Engel AI Main", "assistant_self_claim_repaired"),
        (r"\bI['\u2019]m\s+(?:Joshua|Josh)\b", "I'm Engel AI Main", "assistant_self_claim_repaired"),
        (r"\b(?:you\s+can\s+)?call\s+me\s+(?:Joshua|Josh)\b", "I will call you Joshua", "assistant_name_claim_repaired"),
        (r"\byou\s+can\s+find\s+me\s+as\s+(?:Joshua|Josh)\b", "I will address you as Joshua", "assistant_name_claim_repaired"),
    )
    for pattern, replacement, repair_name in substitutions:
        updated = re.sub(pattern, replacement, repaired, count=1, flags=re.IGNORECASE)
        if updated != repaired:
            repaired = updated
            if repair_name not in repairs:
                repairs.append(repair_name)
    return repaired, repaired != original, repairs


def repair_surface_identity(
    reply: str,
    identity: dict[str, Any],
) -> dict[str, Any]:
    original = str(reply or "").strip()
    repaired, speaker_listener_fixed = repair_operator_address_identity(original)
    repairs: list[str] = ["engel_vocative_removed"] if speaker_listener_fixed else []
    repaired, fusion_fixed, fusion_repairs = repair_joshua_chase_fusion(repaired)
    if fusion_fixed:
        repairs.extend(item for item in fusion_repairs if item not in repairs)
    repaired, assistant_identity_fixed, assistant_repairs = repair_assistant_self_identity(repaired)
    if assistant_identity_fixed:
        repairs.extend(item for item in assistant_repairs if item not in repairs)
    actor = str(identity.get("resolved_actor") or "unknown_user")
    addressed_as = str(identity.get("addressed_as") or "").strip()
    if actor != "joshua":
        replacement = addressed_as if addressed_as and addressed_as.casefold() not in {"discord user", "unknown"} else "the current Discord user"
        direct_address = re.sub(
            r",\s*(?:joshua|josh)\s*([.!?])?$",
            lambda match: f", {replacement}{match.group(1) or ''}",
            repaired,
            count=1,
            flags=re.IGNORECASE,
        )
        if direct_address != repaired:
            repairs.append("non_owner_joshua_vocative_repaired")
            repaired = direct_address
        leading_address = re.sub(
            r"^\s*(?:hello|hi|hey)\s+(?:joshua|josh)\s*,\s*",
            f"Hello {replacement}, ",
            repaired,
            count=1,
            flags=re.IGNORECASE,
        )
        if leading_address != repaired:
            repairs.append("non_owner_joshua_greeting_repaired")
            repaired = leading_address
        identity_claim = re.sub(
            r"\byou\s+are\s+(?:joshua|josh)\b",
            f"you are {replacement}",
            repaired,
            count=1,
            flags=re.IGNORECASE,
        )
        if identity_claim != repaired:
            repairs.append("non_owner_joshua_claim_repaired")
            repaired = identity_claim
    elif re.search(r"\byou\s+are\s+engel(?:\s+ai(?:\s+main)?)?\b", repaired, re.IGNORECASE):
        repaired = re.sub(
            r"\byou\s+are\s+engel(?:\s+ai(?:\s+main)?)?\b",
            "you are Joshua",
            repaired,
            count=1,
            flags=re.IGNORECASE,
        )
        repairs.append("owner_identity_inversion_repaired")
    if actor == "joshua":
        chase_claim = re.sub(
            r"\byou\s+are\s+chase(?:/lokal)?\b",
            "you are Joshua",
            repaired,
            count=1,
            flags=re.IGNORECASE,
        )
        if chase_claim != repaired:
            repairs.append("owner_called_chase_repaired")
            repaired = chase_claim
    return {
        "schema": SHARED_IDENTITY_GUARD,
        "ok": True,
        "surface": identity.get("surface", "other"),
        "resolved_actor": actor,
        "authority_level": identity.get("authority_level", "guest"),
        "identity_lock_valid": identity.get("identity_lock_valid") is True,
        "reply": repaired,
        "changed": repaired != original,
        "repairs": repairs,
    }


def record_route_event(
    *,
    prompt: str,
    reply: str,
    receipt: dict[str, Any],
    request: dict[str, Any],
    identity_guard: dict[str, Any],
    failure_capture: dict[str, Any] | None,
    source: str,
    stage: str,
    ledger_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(ledger_path or LEDGER_PATH)
    prompt_redacted, prompt_redactions = redact_text(prompt, limit=600)
    reply_redacted, reply_redactions = redact_text(reply, limit=600)
    surface = request_surface(request, receipt)
    created_at = _now_iso()
    seed = "|".join(
        (
            created_at,
            surface,
            stage,
            _sha256(str(prompt or "")),
            _sha256(str(reply or "")),
            str(receipt.get("workspace_receipt_path") or ""),
        )
    )
    failure_capture = failure_capture if isinstance(failure_capture, dict) else {}
    selected_route = str(receipt.get("selected_provider") or receipt.get("provider") or "")
    runtime_route = str(receipt.get("runtime_provider") or "")
    route_kind = str(receipt.get("route_kind") or "model_chat")
    provider_bridge_used = receipt.get("provider_bridge_used") is True
    local_model_first = receipt.get("local_model_first") is True
    if (
        not local_model_first
        and route_kind == "model_chat"
        and not provider_bridge_used
        and receipt.get("provider_api_enabled") is not True
    ):
        local_model_first = any(
            token in f"{selected_route} {runtime_route}".casefold()
            for token in ("local", "llama", "ollama", "vllm")
        )
    event = {
        "schema": SHARED_ROUTE_CONTRACT,
        "event_id": "chat_route_" + _sha256(seed)[:20],
        "created_at_utc": created_at,
        "surface": surface,
        "source": _clip(source, 120),
        "stage": _clip(stage, 100),
        "chat_context_scope": _clip(receipt.get("chat_context_scope"), 180),
        "prompt_sha256": _sha256(str(prompt or "")),
        "reply_sha256": _sha256(str(reply or "")),
        "prompt_redacted": prompt_redacted,
        "reply_redacted": reply_redacted,
        "redaction_count": prompt_redactions + reply_redactions,
        "route": {
            "requested_provider": _clip(request.get("provider") or receipt.get("requested_provider_arg"), 100),
            "selected_provider": _clip(selected_route, 120),
            "runtime_provider": _clip(runtime_route, 160),
            "provider_api_enabled": receipt.get("provider_api_enabled") is True,
            "provider_bridge_used": provider_bridge_used,
            "local_model_first": local_model_first,
            "route_kind": _clip(route_kind, 80),
        },
        "identity_guard": {
            "contract": SHARED_IDENTITY_GUARD,
            "resolved_actor": identity_guard.get("resolved_actor", "unknown_user"),
            "authority_level": identity_guard.get("authority_level", "guest"),
            "identity_lock_valid": identity_guard.get("identity_lock_valid") is True,
            "changed": identity_guard.get("changed") is True,
            "repairs": identity_guard.get("repairs", []),
        },
        "failure_path": {
            "captured": failure_capture.get("captured") is True,
            "event_id": str(failure_capture.get("event_id") or ""),
            "failure_types": failure_capture.get("failure_types", []),
            "corpus_path": str(failure_capture.get("corpus_path") or ""),
            "eval_candidate": failure_capture.get("captured") is True,
            "training_candidate": False,
            "trusted_memory_write": False,
        },
        "workspace_receipt_path": _clip(receipt.get("workspace_receipt_path"), 500),
        "storage_mutation": False,
        "external_array_used": False,
    }
    _append_jsonl(path, event)
    if path.resolve(strict=False) == LEDGER_PATH.resolve(strict=False):
        try:
            status_snapshot()
        except Exception:
            pass
    return {
        "schema": "ENGEL_CHAT_ROUTE_PARITY_RECORD_V1",
        "ok": True,
        "status": "shared chat route recorded",
        "event_id": event["event_id"],
        "surface": surface,
        "stage": stage,
        "ledger_path": str(path),
        "identity_guard": event["identity_guard"],
        "failure_path": event["failure_path"],
        "storage_mutation": False,
        "external_array_used": False,
    }


def finalize_surface_turn(
    *,
    prompt: str,
    reply: str,
    receipt: dict[str, Any] | None,
    request: dict[str, Any] | None,
    attachment_intake: dict[str, Any] | None = None,
    existing_failure_capture: dict[str, Any] | None = None,
    source: str,
    stage: str,
    ledger_path: str | Path | None = None,
    corpus_path: str | Path | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    mutable_receipt = dict(receipt) if isinstance(receipt, dict) else {}
    request = request if isinstance(request, dict) else {}
    identity = surface_identity(request, mutable_receipt)
    guard = repair_surface_identity(reply, identity)
    visible_reply = str(guard.get("reply") or "")
    if guard.get("changed") is True:
        mutable_receipt["identity_mixup"] = True
        mutable_receipt["shared_identity_guard_repaired"] = True
        mutable_receipt["training_sample_eligible"] = False
        mutable_receipt["persistent_chat_memory_training_eligible"] = False
        mutable_receipt["raw_model_reply"] = str(reply or "")
        mutable_receipt["assistant_reply"] = visible_reply
        mutable_receipt["assistant_output_text"] = visible_reply
    mutable_receipt["shared_identity_guard"] = {
        key: value for key, value in guard.items() if key != "reply"
    }
    failure = existing_failure_capture if isinstance(existing_failure_capture, dict) else None
    if failure is None or guard.get("changed") is True:
        failure = capture_failure(
            prompt=prompt,
            reply=visible_reply,
            receipt=mutable_receipt,
            attachment_intake=attachment_intake,
            request=request,
            source=source,
            corpus_path=corpus_path,
            root=root,
        )
    route = record_route_event(
        prompt=prompt,
        reply=visible_reply,
        receipt=mutable_receipt,
        request=request,
        identity_guard=guard,
        failure_capture=failure,
        source=source,
        stage=stage,
        ledger_path=ledger_path,
    )
    mutable_receipt["chat_route_parity"] = route
    mutable_receipt["chat_failure_corpus"] = failure
    return {
        "schema": "ENGEL_DISCORD_DESKTOP_ROUTE_PARITY_FINALIZE_V1",
        "ok": True,
        "reply": visible_reply,
        "receipt": mutable_receipt,
        "identity_guard": guard,
        "failure_capture": failure,
        "route_event": route,
    }


def _read_tail(path: Path, tail_bytes: int = 2_000_000) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - tail_bytes))
            text = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("schema") == SHARED_ROUTE_CONTRACT:
            rows.append(item)
    return rows


def status_snapshot(ledger_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(ledger_path or LEDGER_PATH)
    rows = _read_tail(path)
    surfaces = Counter(str(row.get("surface") or "other") for row in rows)
    stages = Counter(str(row.get("stage") or "unknown") for row in rows)
    failure_events = sum(
        1
        for row in rows
        if isinstance(row.get("failure_path"), dict) and row["failure_path"].get("captured") is True
    )
    payload = {
        "schema": "ENGEL_DISCORD_DESKTOP_ROUTE_PARITY_STATUS_V1",
        "ok": True,
        "status": "shared desktop and Discord route ledger ready",
        "route_contract": SHARED_ROUTE_CONTRACT,
        "identity_guard_contract": SHARED_IDENTITY_GUARD,
        "ledger_path": str(path),
        "event_count": len(rows),
        "surface_counts": dict(sorted(surfaces.items())),
        "stage_counts": dict(sorted(stages.items())),
        "desktop_seen": surfaces.get("desktop", 0) > 0,
        "discord_seen": surfaces.get("discord", 0) > 0,
        "desktop_discord_parity_observed": surfaces.get("desktop", 0) > 0 and surfaces.get("discord", 0) > 0,
        "failure_event_count": failure_events,
        "latest_event_id": str(rows[-1].get("event_id") or "") if rows else "",
        "same_issue_eval_path": True,
        "training_candidate": False,
        "trusted_memory_write": False,
        "storage_mutation": False,
        "external_array_used": False,
        "updated_at_utc": _now_iso(),
    }
    if ledger_path is None:
        _write_json(STATUS_PATH, payload)
    return payload


SHARED_CHAT_BRAIN_SCHEMA = "engel_shared_chat_brain_v1"
SHARED_CHAT_BRAIN_PATH = ROOT / "memory" / "personality" / "ENGEL_SHARED_CHAT_BRAIN.json"
STANDING_CHAT_CONFIG_PATH = ROOT / "memory" / "personality" / "ENGEL_CHAT_PROVIDER_CONFIG.json"
SHARED_CHAT_SURFACES = ("engel_flutter_main", "discord")
_UI_PROVIDER_CHOICES = {"local", "codex", "openai", "anthropic", "xai", "gemini", "nvidia"}
_GROK_MODEL_IDS = {
    "grok-4.6",
    "grok-4-6",
    "grok-4-3-max",
    "grok-4-3-fast",
    "grok-4-3-reasoning",
    "grok-4-3-vision",
    "grok-build-0-1",
}


def _normalize_standing_provider(value: Any) -> str:
    provider = str(value or "").strip().casefold()
    if provider in {"xai_grok_cli", "xai-grok-cli", "grok"}:
        return "xai"
    if provider in {"nvidia", "nim", "nvidia-nim", "nvidia_nim"}:
        return "nvidia"
    if provider in {"chatgpt", "openai-api"}:
        return "openai"
    if provider in _UI_PROVIDER_CHOICES or provider in {"auto", ""}:
        return provider or "auto"
    return "auto"


def _standing_api_model(model_id: str, provider: str) -> str:
    mid = str(model_id or "").strip()
    if mid in _GROK_MODEL_IDS or provider == "xai":
        return "grok-4.6" if mid in _GROK_MODEL_IDS or provider == "xai" else mid
    if provider in {"local", "auto", ""}:
        return ""
    return mid


def standing_chat_brain() -> dict[str, Any]:
    """One standing pipe for Cosmic Swarm chat and Josh Discord.

    Discord is a room, not a second Engel. Sub-Engel and future subs stay on
    the fast local lane so they cannot steal the owner brain.
    """
    shared: dict[str, Any] = {}
    config: dict[str, Any] = {}
    try:
        if SHARED_CHAT_BRAIN_PATH.is_file():
            loaded = json.loads(SHARED_CHAT_BRAIN_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                shared = loaded
    except Exception:
        shared = {}
    try:
        if STANDING_CHAT_CONFIG_PATH.is_file():
            loaded = json.loads(STANDING_CHAT_CONFIG_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                config = loaded
    except Exception:
        config = {}
    model_id = str(
        shared.get("selected_model_id") or config.get("selected_model_id") or "auto-best"
    ).strip()
    model_name = str(
        shared.get("selected_model_name") or config.get("selected_model_name") or model_id
    ).strip()
    provider = _normalize_standing_provider(
        shared.get("selected_chat_provider") or config.get("selected_chat_provider") or "auto"
    )
    model = _standing_api_model(model_id, provider)
    force = provider in _UI_PROVIDER_CHOICES and provider != "local"
    return {
        "schema": SHARED_CHAT_BRAIN_SCHEMA,
        "ok": True,
        "surfaces": list(SHARED_CHAT_SURFACES),
        "selected_model_id": model_id,
        "selected_model_name": model_name or "Auto Best",
        "selected_chat_provider": provider,
        "model": model,
        "force": force,
        "owner_uses_standing_pipe": True,
        "peers_use_fast_local": True,
        "future_subs_use_fast_local": True,
        "path": str(SHARED_CHAT_BRAIN_PATH),
        "updated_at_utc": str(shared.get("updated_at_utc") or ""),
        "updated_by": str(shared.get("updated_by") or ""),
    }


def save_standing_chat_brain(
    *,
    selected_model_id: str = "",
    selected_model_name: str = "",
    selected_chat_provider: str = "",
    updated_by: str = "engel-ai-main",
) -> dict[str, Any]:
    provider = _normalize_standing_provider(selected_chat_provider)
    model_id = str(selected_model_id or "").strip() or (
        "grok-4.6" if provider == "xai" else "auto-best"
    )
    model_name = str(selected_model_name or "").strip() or model_id
    payload = {
        "schema": SHARED_CHAT_BRAIN_SCHEMA,
        "ok": True,
        "surfaces": list(SHARED_CHAT_SURFACES),
        "selected_model_id": model_id,
        "selected_model_name": model_name,
        "selected_chat_provider": provider,
        "owner_uses_standing_pipe": True,
        "peers_use_fast_local": True,
        "future_subs_use_fast_local": True,
        "updated_by": str(updated_by or "engel-ai-main")[:80],
        "updated_at_utc": _now_iso(),
    }
    _write_json(SHARED_CHAT_BRAIN_PATH, payload)
    payload["path"] = str(SHARED_CHAT_BRAIN_PATH)
    return payload


def remember_desktop_standing_chat_brain(request: dict[str, Any] | None) -> dict[str, Any] | None:
    """When Cosmic Swarm sends an explicit pipe, Discord must follow it."""
    request = request if isinstance(request, dict) else {}
    if request_surface(request) != "desktop":
        return None
    if not (
        request.get("force_provider") is True
        or request.get("explicit_provider") is True
    ):
        return None
    provider = _normalize_standing_provider(
        request.get("provider") or request.get("selected_provider") or ""
    )
    if provider not in _UI_PROVIDER_CHOICES or provider == "local":
        return None
    metadata = request.get("metadata") if isinstance(request.get("metadata"), dict) else {}
    return save_standing_chat_brain(
        selected_model_id=str(
            metadata.get("standing_chat_model_id")
            or request.get("model")
            or request.get("provider_model")
            or ""
        ),
        selected_model_name=str(metadata.get("standing_chat_model_name") or ""),
        selected_chat_provider=provider,
        updated_by="engel_flutter_main",
    )


def apply_standing_chat_brain(payload: dict[str, Any], *, owner_turn: bool) -> dict[str, Any]:
    """Josh Discord uses the Cosmic Swarm standing pipe. Peers do not."""
    if not isinstance(payload, dict) or not owner_turn:
        return payload
    standing = standing_chat_brain()
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        payload["metadata"] = metadata
    metadata["shared_engel_brain"] = True
    metadata["discord_is_room_not_second_brain"] = True
    metadata["standing_chat_model_id"] = standing["selected_model_id"]
    metadata["standing_chat_model_name"] = standing["selected_model_name"]
    metadata["standing_chat_provider"] = standing["selected_chat_provider"]
    metadata["discord_brain"] = standing["selected_model_name"]
    payload["prefer_fast_local_chat"] = False
    payload["discord_owner_turn"] = True
    payload["allow_provider_fallback"] = True
    if payload.get("force_provider") is True:
        return payload
    # Cosmic Swarm may have Grok selected. That is the shared picker, not an
    # explicit "use Grok now" order. Forcing a dead Grok pipe silences Josh
    # in Discord (live 2026-09-06: Wikipedia link -> TimeoutError fail card).
    payload["automatic_provider_after_local_failure_only"] = True
    if standing.get("force") is True:
        metadata["preferred_standing_provider"] = standing["selected_chat_provider"]
        if standing.get("model"):
            metadata["preferred_standing_model"] = standing["model"]
    return payload


if __name__ == "__main__":
    print(json.dumps(status_snapshot(), indent=2, sort_keys=True))
