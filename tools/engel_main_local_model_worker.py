#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
from pathlib import Path
import sys
import threading
import time
import traceback
from typing import Any
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
LOCAL_ONLY_TRAINING_SENTINEL = (
    ROOT / "runtime" / "one_hour_local_only_chat_training" / "active.json"
)
LOCAL_WRAPPER_RECEIPT_DIR = ROOT / "reports" / "engel_standalone_chat_llm" / "chat_receipts"


def _belt_wrapper_payload(receipt: dict) -> dict:
    """Shape a CT fast-chat receipt into the wrapper contract the training runner
    accepts as DONE - derived the same way the runner's own CT-memory recovery
    receipt derives it (_write_ct_memory_chat_receipt), read from that code, not
    assumed: ok must be exactly True, creation_job derives from the build action,
    chat_only_no_android_or_sub_engel is its negation, and main_server_chat_used
    is what the delivery-failure classifier checks. assistant_reply stays inline
    because _wrapper_reply_text grades from the raw file."""
    action = receipt.get("action") if isinstance(receipt.get("action"), dict) else {}
    creation_job = bool(
        receipt.get("build_lane_used") is True
        or action.get("kind") in ("app_build", "workspace_scaffold")
    )
    payload = dict(receipt)
    payload["ok"] = receipt.get("ok") is True
    payload.setdefault("status", "unknown")
    payload["creation_job"] = creation_job
    payload.setdefault("chat_only_no_android_or_sub_engel", not creation_job)
    payload.setdefault("main_server_chat_used", True)
    return payload


def _persist_local_wrapper_receipt(receipt: Any) -> None:
    """Belt to the CT-memory braces: a local wrapper receipt per served chat turn.

    (2026-08-14) The CT-first worker never wrote ENGEL_UI_CHAT_MEETING_ROOM_*.json
    for its own served turns - those files only ever came from the (since-closed)
    fleet-dispatch misroute and from manual doctor runs, so after 2026-08-03 every
    training DONE depended entirely on the runner's SSH probe into CT persistent
    memory. That probe is the designed lane and stays; this file is the local
    first-choice evidence the runner's wrapper glob checks BEFORE falling back to
    SSH. JSON only - CT already appends persistent memory server-side, so writing
    memory here would double-record the turn. Never allowed to fail a chat turn.
    """
    try:
        if not isinstance(receipt, dict) or not receipt:
            return
        # A receipt that would classify FAIL is worse than no receipt at all: the
        # runner consumes wrapper receipts BEFORE its CT-memory probe, so a bad
        # one SHADOWS the good recovery path (live 2026-08-15: two marathon legs
        # died this way). Only persist receipts that satisfy the DONE contract.
        payload = _belt_wrapper_payload(receipt)
        if payload.get("ok") is not True:
            return
        import hashlib

        LOCAL_WRAPPER_RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        digest = hashlib.sha256(body.encode("utf-8", errors="replace")).hexdigest()[:8]
        stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime()) + f"{time.time_ns() % 1_000_000:06d}Z"
        path = LOCAL_WRAPPER_RECEIPT_DIR / (
            f"ENGEL_UI_CHAT_MEETING_ROOM_{stamp}_p{os.getpid()}_{digest}.json"
        )
        tmp = path.with_suffix(".tmp")
        tmp.write_text(body, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        # Receipt persistence is evidence, not a dependency of the reply path.
        pass


PERSISTENT_CHAT_MEMORY_PATH = (
    ROOT / "memory" / "persistent_chat" / "ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl"
)


def _persist_recall_chat_memory(prompt: str, receipt: Any) -> None:
    """Append-only recall copy on the ROG disk. Not trusted core memory.

    CT246 already writes /opt/engel/memory/persistent_chat. Laptop recall has
    to see the same turn locally or Josh cannot ask Engel what just happened.
    Failed turns are saved too — a verification failure is still a chat turn.
    """
    try:
        if not isinstance(receipt, dict) or not receipt:
            return
        reply = str(
            receipt.get("assistant_reply")
            or receipt.get("assistant_output_text")
            or receipt.get("reply")
            or ""
        ).strip()
        text = str(prompt or "").strip()
        if not text and not reply:
            return
        import hashlib
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        record = {
            "schema": "engel_ai_main_persistent_chat_history_v1",
            "memory_source": "engel-flutter-main worker recall",
            "created_at_utc": now,
            "updated_at_utc": now,
            "prompt": text,
            "prompt_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "assistant_reply": reply,
            "assistant_output_text": reply,
            "assistant_reply_sha256": hashlib.sha256(reply.encode("utf-8")).hexdigest(),
            "ok": receipt.get("ok"),
            "status": receipt.get("status"),
            "build_verified": receipt.get("build_verified"),
            "provider": receipt.get("provider"),
            "runtime_provider": receipt.get("runtime_provider"),
            "selected_provider": receipt.get("selected_provider"),
            "workspace_receipt_path": receipt.get("workspace_receipt_path")
            or receipt.get("receipt_path"),
            "persistent_chat_memory_path": str(PERSISTENT_CHAT_MEMORY_PATH),
            "model_output_trusted": False,
            "trusted_memory_write_enabled": False,
            "approved_memory_write_enabled": False,
            "trust_scope": "context-only chat continuity; not approved trusted memory",
        }
        PERSISTENT_CHAT_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with PERSISTENT_CHAT_MEMORY_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
os.chdir(ROOT)

# The Flutter app reads this process's stdout with a STRICT utf8 decoder.
# When spawned with pipes on Windows, Python defaults stdout to cp1252, so a
# single typographic character (curly quote in a Claude reply) produced bytes
# Dart could not decode - the reply line was dropped and the chat bubble spun
# until the 300s timeout (2026-07-01 freeze). Force UTF-8 on both streams.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

# Enables the in-process llama_cpp path in run_engel_standalone_chat_llm.py.
os.environ.setdefault("ENGEL_MAIN_LONG_LIVED_LOCAL_MODEL_SERVICE", "1")

from engel_ui_prompt_training_support import redact  # noqa: E402

# OpenClaw-ported (MIT) engines reused natively in Engel:
#   - engel_agent_failover_loop: multi-AI failover run loop ("long-run using other AI")
#   - engel_verbose: 7-level logger + /verbose /trace /usage /tools directives
# Optional import so a missing module never takes down the worker.
try:
    import engel_agent_failover_loop as _failover  # noqa: E402
    import engel_verbose as _ev  # noqa: E402

    _VERBOSE_STATE = _ev.SessionVerboseState()
    _VLOG = _ev.EngelLogger()
    _FAILOVER_AVAILABLE = True
except Exception:  # pragma: no cover
    _failover = None
    _ev = None
    _VERBOSE_STATE = None
    _VLOG = None
    _FAILOVER_AVAILABLE = False


def _clean_text(value: Any) -> str:
    """Return text that can always be encoded as UTF-8.

    Windows clipboard/UI history can occasionally hand Python isolated UTF-16
    surrogate code units. json.dumps(..., ensure_ascii=False).encode("utf-8")
    then crashes before Engel can reach CT246. Replace invalid code units at the
    worker boundary so one bad pasted character cannot break chat.
    """
    return str(value or "").encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def _clean_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, list):
        return [_clean_json_value(item) for item in value]
    if isinstance(value, dict):
        return {_clean_text(key): _clean_json_value(item) for key, item in value.items()}
    return value


def _request_id(payload: dict[str, Any]) -> str:
    value = _clean_text(payload.get("id") or "").strip()
    return value or str(int(time.time() * 1000))


def _response(payload: dict[str, Any]) -> None:
    # ensure_ascii=True: the protocol line must survive ANY pipe encoding -
    # non-ASCII stays escaped as \uXXXX and decodes identically in Dart.
    sys.stdout.write(json.dumps(_clean_json_value(redact(payload)), ensure_ascii=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _heartbeat_status_text(elapsed_s: int) -> str:
    """Operator-facing progress, not a path dump or canned runtime card."""
    if elapsed_s < 20:
        return "Engel is working on your message."
    if elapsed_s < 60:
        return "Still working. Checking workers and starting the job."
    if elapsed_s < 180:
        return "This is taking a few minutes. I will say when it is done or if it failed."
    minutes = max(1, elapsed_s // 60)
    return (
        f"Still working after {minutes} minute"
        f"{'s' if minutes != 1 else ''}. I have not finished yet."
    )


@contextlib.contextmanager
def _request_progress_heartbeat(
    request_id: str,
    *,
    enabled: bool,
    interval_seconds: float = 15.0,
):
    """Keep Flutter's idle watchdog attached during one long CT246 action."""
    if not enabled or not request_id:
        yield
        return
    stop = threading.Event()
    started = time.time()

    def emit() -> None:
        while not stop.wait(max(0.05, interval_seconds)):
            elapsed_s = int(time.time() - started)
            # Empty delta resets Flutter's idle watchdog. status_text is the
            # visible working sentence so Josh is not left on a runtime dump.
            _response(
                {
                    "id": request_id,
                    "delta": "",
                    "progress": "ct246_action_running",
                    "status_text": _heartbeat_status_text(elapsed_s),
                }
            )

    thread = threading.Thread(
        target=emit,
        name=f"engel-ct246-heartbeat-{request_id[-24:]}",
        daemon=True,
    )
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=2.0)


def _server_chat_url() -> str:
    base = str(os.environ.get("ENGEL_MAIN_SERVER_CHAT_URL") or "http://127.0.0.1:24680").strip().rstrip("/")
    return base + "/chat"


def _local_only_training_active(now_epoch: float | None = None) -> bool:
    """Return true only for a live, bounded Engel-owned local-only session."""
    try:
        payload = json.loads(
            LOCAL_ONLY_TRAINING_SENTINEL.read_text(encoding="utf-8-sig")
        )
    except (OSError, ValueError, TypeError):
        return False
    if not isinstance(payload, dict):
        return False
    if str(payload.get("status") or "").upper() != "RUNNING":
        return False
    if str(payload.get("provider_policy") or "").casefold() != "local_only":
        return False
    try:
        expires_at_epoch = float(payload.get("expires_at_epoch") or 0)
    except (TypeError, ValueError):
        return False
    return expires_at_epoch > float(time.time() if now_epoch is None else now_epoch)


def _clamped_inbox_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Clamp UI-chat-inbox training metadata through the Governor whitelist
    before it rides to CT246. The metadata declares "this is a training turn of
    discipline X" (routing + memory hygiene). Narrow-only: unknown keys drop,
    out-of-range values fall back, and on any failure the answer is NO metadata
    rather than unclamped metadata."""
    raw = payload.get("metadata")
    if not isinstance(raw, dict) or not raw:
        return {}
    try:
        from engel_governor import clamp_inbox_metadata

        return clamp_inbox_metadata(raw)
    except Exception:
        return {}


def _merge_inbox_metadata(
    request_payload: dict[str, Any], inbox_metadata: dict[str, Any] | None
) -> None:
    """Merge clamped inbox metadata UNDER the worker's own keys so
    worker_source/worker_contract/conversation_id can never be overridden
    from the inbox side."""
    if not inbox_metadata:
        return
    merged = dict(inbox_metadata)
    existing = request_payload.get("metadata")
    if isinstance(existing, dict):
        merged.update(existing)
    request_payload["metadata"] = merged


def _attachments_have_still_images(attachments: list[dict[str, Any]] | None) -> bool:
    if not attachments:
        return False
    for item in attachments:
        if not isinstance(item, dict):
            continue
        mime = str(item.get("mime_type") or item.get("mime") or "").casefold()
        kind = str(item.get("kind") or "").casefold()
        name = str(item.get("name") or item.get("path") or "").casefold()
        if "gif" in mime or name.endswith(".gif"):
            continue
        if mime.startswith("image/") or kind in {"image", "screenshot"}:
            return True
    return False


def _apply_image_vision_lane(
    request_payload: dict[str, Any], attachments: list[dict[str, Any]] | None
) -> None:
    """Josh attaching a still in Engel AI Main must reach the Grok vision lane."""
    if _local_only_training_active():
        return
    if not _attachments_have_still_images(attachments):
        return
    request_payload["allow_provider_fallback"] = True
    request_payload["main_ui_vision"] = True
    request_payload["prefer_fast_local_chat"] = False
    try:
        request_payload["timeout"] = max(int(request_payload.get("timeout") or 0), 180)
    except (TypeError, ValueError):
        request_payload["timeout"] = 180
    metadata = request_payload.setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata["main_ui_vision"] = True


def _enforce_local_only_training(request_payload: dict[str, Any]) -> None:
    if not _local_only_training_active():
        return
    request_payload["provider"] = "local"
    request_payload["selected_provider"] = "local"
    request_payload["allow_provider_fallback"] = False
    request_payload["local_only_training"] = True
    metadata = request_payload.setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata["local_only_training"] = True
        metadata["provider_policy"] = "local_only"


def _apply_main_ui_local_failure_fallback(request_payload: dict[str, Any]) -> None:
    """Cosmic Swarm Chat may use NVIDIA NIM only after a proved local miss."""
    if request_payload.get("local_only_training") is True:
        return
    if request_payload.get("force_provider") is True:
        return
    request_payload["allow_provider_fallback"] = True
    request_payload["automatic_provider_after_local_failure_only"] = True
    request_payload["preferred_fallback_provider"] = "nvidia"
    metadata = request_payload.setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata["preferred_fallback_provider"] = "nvidia"
        metadata.setdefault("host_memory", _rog_host_memory_snapshot())


def _rog_host_memory_snapshot() -> dict[str, Any]:
    try:
        import psutil

        vm = psutil.virtual_memory()
        return {
            "ok": True,
            "host": "rog_face",
            "total_bytes": int(vm.total),
            "used_bytes": int(vm.used),
            "available_bytes": int(vm.available),
            "percent": float(vm.percent),
        }
    except Exception as exc:
        return {"ok": False, "host": "rog_face", "error": str(exc)[:200]}


# (2026-07-27) Chat-box provider picker: the desktop dropdown sends
# provider + force_provider=true, mirroring the CT246 force-key contract in
# _request_explicit_provider_allowed. Only these normalized names are honored;
# "auto"/"" keep the local-first default, and a live local-only training
# sentinel still overrides everything via _enforce_local_only_training.
_UI_PROVIDER_CHOICES = {"local", "codex", "openai", "anthropic", "xai", "gemini", "nvidia"}


def _ui_forced_provider(payload: dict[str, Any]) -> str:
    """The face cannot pin a provider. The automatic router selects the lane."""
    del payload
    return ""


def _stamp_catalog_selection(request_payload: dict[str, Any], payload: dict[str, Any]) -> None:
    """Chat is auto-best. A picker id is recorded and does not pin the turn."""
    metadata = request_payload.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        request_payload["metadata"] = metadata
    router_lane = payload.get("automatic_router_lane") is True
    requested = str(payload.get("selected_model_id") or "").strip()
    if requested:
        metadata["requested_model_id"] = requested
    if requested in {"jev-latest", "jev"}:
        metadata["jev_router"] = True
        request_payload["jev_router"] = True
    if router_lane:
        request_payload["automatic_router_lane"] = True
        metadata["automatic_router_lane"] = True
        if requested:
            request_payload["selected_model_id"] = requested
            metadata["selected_model_id"] = requested
    else:
        request_payload["selected_model_id"] = "auto-best"
        metadata["selected_model_id"] = "auto-best"
        metadata["automatic_model_route"] = True
        request_payload.pop("force_provider", None)
    for key in ("thinking_enabled", "reasoning_effort", "engel_task_kind"):
        value = payload.get(key)
        if value in (None, ""):
            continue
        request_payload[key] = value
        metadata[key] = value


def _ui_requested_model(payload: dict[str, Any]) -> str:
    text = _clean_text(str(payload.get("model") or payload.get("provider_model") or "")).strip()
    if not text or text.casefold() in {"auto", "auto-best"}:
        return ""
    aliases = {
        "grok-4.6": "grok-4.6",
        "grok-4-6": "grok-4.6",
        "grok46": "grok-4.6",
        "grok-4-3-max": "grok-4.6",
        "grok-build": "grok-4.6",
        "grok-build-0-1": "grok-4.6",
        "grok-build-0.1": "grok-4.6",
        "grok-4.5": "grok-4.5",
    }
    return aliases.get(text.casefold(), text)


def _server_prompt_override_for_truth_route(prompt: str) -> str:
    """Keep the ROG UI honest while CT rolls forward.

    Older CT service builds already have deterministic live-status routes for
    "phone status" and "connection status", but they miss natural user wording
    like "what workers are live right now?"  The desktop worker translates only
    those status intents to the existing CT truth route so the reply still comes
    from CT and still appends to CT persistent memory.
    """
    prompt = _clean_text(prompt)
    low = prompt.casefold()
    if not low.strip():
        return prompt
    if _requested_app_build(prompt) is not None or _requested_workspace_setup(prompt) is not None:
        return prompt
    room_terms = (
        "meeting room",
        "agent room",
        "server world",
        "3d room",
        "3d agent",
        "agent workspace",
        "all devices",
        "all agents",
        "sub-engel",
        "one job",
        "proof job",
        "work order",
        "with this room",
        "using this room",
        "use this room",
    )
    if any(term in low for term in room_terms):
        return prompt
    worker_terms = (
        "what workers are live",
        "which workers are live",
        "workers are live",
        "live workers",
        "what workers are connected",
        "which workers are connected",
        "what devices are live",
        "which devices are live",
        "what devices are connected",
        "phone worker",
        "android worker",
    )
    phone_terms = ("phone", "phones", "android")
    status_terms = ("status", "connected", "connection", "online", "offline")
    # (2026-07-07 audit fix ②) Only rewrite SHORT, bare live-status checks. The old
    # rule OR'd ordinary words ("alpha"/"beta"/"working"/"live" + "can you chat"/
    # "health check") and silently rewrote real conversation ("how do I get my
    # phone online", "is the beta feature working yet", "can you chat about the
    # weather") into a canned status query, discarding the user's actual message.
    words = low.split()
    is_bare_status_check = len(words) <= 8 and not any(
        marker in low
        for marker in ("how ", "why ", "help", "about ", "explain", "tell me", "what do", "should i")
    )
    if is_bare_status_check and (
        any(term in low for term in worker_terms)
        or (
            any(term in low for term in phone_terms)
            and any(term in low for term in status_terms)
        )
    ):
        return "phone status"
    chat_terms = (
        "is chat fixed",
        "chat fixed",
        "is chat working",
        "connection status",
        "server status",
    )
    if is_bare_status_check and any(term in low for term in chat_terms):
        return "connection status"
    return prompt


def _prompt_explicitly_names_provider(prompt: str) -> bool:
    low = _clean_text(prompt).casefold()
    return any(
        term in low
        for term in (
            "chatgpt",
            "openai",
            "gpt",
            "claude",
            "anthropic",
            "grok",
            "xai",
            "x.ai",
            "gemini",
            "google ai",
            "codex",
        )
    )


# --- confirm-before-execute action flow (2026-07-07) -----------------------
# A pending plan awaiting the operator's yes/no, held in module state for this
# worker session (one process per Flutter chat session).
# EngelScript chat commands (docs/ENGEL_SCRIPT_LANGUAGE.md). Cheap regex gate
# first; the language module and route registry import lazily only on a hit so
# the chat hot path never pays their import graph.
_ENGEL_SCRIPT_CHAT_RE = re.compile(
    r"^\s*(?:(run|validate|draft)\s+engel\s+script\b(.*)"
    r"|engel\s+script\s+(docs|help|language|examples|plans)\s*)$",
    re.IGNORECASE | re.DOTALL,
)

# Capability search in the main chat: "what can you do about X". Answered
# locally from the route registry -- Engel knowing its own parts must not
# depend on the CT lane being up.
_ENGEL_CAPABILITY_CHAT_RE = re.compile(
    r"^\s*(?:what\s+can\s+(?:you|engel)\s+do\s+about|engel\s+capabilities\s+for"
    r"|capability\s+search|find\s+engel\s+route\s+for|which\s+route)\b(.*)$",
    re.IGNORECASE | re.DOTALL,
)

_ENGEL_INTENT_BRIDGE_CHAT_RE = re.compile(
    r"^\s*(?:intent\s+bridge\s+(?:docs|help|status|latest)"
    r"|(?:hipl|mipl)\s+(?:docs|help|status)"
    r"|mipl\s+agents?\s+(?:docs|help|skills|status|list|preview|create|activate|grant|run)\b.*"
    r"|latest\s+lifted\s+intent|lift(?:ed)?\s+intent\b.*"
    r"|(?:compile|write|assemble)\s+mipl\b.*)$",
    re.IGNORECASE | re.DOTALL,
)

_ENGEL_SPEECH_SPC_CHAT_RE = re.compile(
    r"^\s*(?:speech\s+spc\s+(?:docs|help|status|latest|compile)\b.*"
    r"|spc\s+(?:docs|help|status|latest|compile)\b.*"
    r"|compile\s+speech\b.*)$",
    re.IGNORECASE | re.DOTALL,
)


def _engel_speech_spc_chat_intercept(
    prompt: str, request_id: str
) -> "dict[str, Any] | None":
    text_in = str(prompt or "").strip()
    if not _ENGEL_SPEECH_SPC_CHAT_RE.match(text_in):
        return None
    try:
        import engel_speech_spc as speech_spc

        reply = speech_spc.render_chat(text_in)
        return {
            "id": request_id,
            "ok": True,
            "status": "engel speech packet compiler",
            "schema": "engel_main_local_model_worker_response_v1",
            "assistant_reply": reply,
            "assistant_output_text": reply,
            "reply": reply,
            "engel_speech_spc_used": True,
            "provider_api_enabled": False,
            "network_enabled": False,
            "readable_output_captured": True,
        }
    except Exception as exc:
        return {
            "id": request_id,
            "ok": False,
            "status": f"engel speech spc error: {type(exc).__name__}",
            "schema": "engel_main_local_model_worker_response_v1",
            "assistant_reply": f"Speech SPC failed open: {type(exc).__name__}: {exc}",
            "assistant_output_text": f"Speech SPC failed open: {type(exc).__name__}: {exc}",
            "reply": f"Speech SPC failed open: {type(exc).__name__}: {exc}",
            "provider_api_enabled": False,
            "network_enabled": False,
        }


def _engel_intent_bridge_chat_intercept(
    prompt: str, request_id: str
) -> "dict[str, Any] | None":
    text_in = str(prompt or "").strip()
    if not _ENGEL_INTENT_BRIDGE_CHAT_RE.match(text_in):
        return None
    try:
        low = text_in.casefold()
        if low.startswith(("mipl agent ", "mipl agents ")):
            import engel_mipl_agent_work as agent_work

            reply = agent_work.render_chat(text_in)
            status = "engel mipl agent work"
        else:
            import engel_lifted_intent as intent_bridge

            if low.startswith(
            ("lift intent", "lifted intent", "compile mipl", "write mipl", "assemble mipl")
            ) and low not in {
                "lifted intent help",
            }:
                reply = intent_bridge.render_lift(text_in)
                status = "engel lifted intent preview"
            elif "latest" in low:
                reply = intent_bridge.render_latest(text_in)
                status = "engel intent bridge latest"
            elif "status" in low:
                reply = intent_bridge.render_status(text_in)
                status = "engel intent bridge status"
            else:
                reply = intent_bridge.render_docs(text_in)
                status = "engel intent bridge docs"
        return {
            "id": request_id,
            "ok": True,
            "status": status,
            "schema": "engel_main_local_model_worker_response_v1",
            "assistant_reply": reply,
            "assistant_output_text": reply,
            "reply": reply,
            "engel_intent_bridge_used": True,
            "engel_mipl_agent_work_used": low.startswith(("mipl agent ", "mipl agents ")),
            "provider_api_enabled": False,
            "network_enabled": False,
        }
    except Exception as exc:
        reply = f"Engel Intent Bridge failed: {type(exc).__name__}: {exc}"
        return {
            "id": request_id,
            "ok": False,
            "status": "engel intent bridge error",
            "schema": "engel_main_local_model_worker_response_v1",
            "assistant_reply": reply,
            "assistant_output_text": reply,
            "provider_api_enabled": False,
            "network_enabled": False,
        }


def _engel_capability_chat_intercept(
    prompt: str, request_id: str
) -> "dict[str, Any] | None":
    match = _ENGEL_CAPABILITY_CHAT_RE.match(str(prompt or ""))
    if not match:
        return None
    try:
        import engel_capability_index as ci

        text = ci.render_capability_search(str(prompt or "").strip())
    except Exception as exc:  # noqa: BLE001 -- never eat a chat turn
        text = f"Engel capability search failed: {type(exc).__name__}: {exc}"
    return {
        "id": request_id,
        "ok": True,
        "status": "engel capability search",
        "schema": "engel_main_local_model_worker_response_v1",
        "assistant_reply": text,
        "assistant_output_text": text,
        "reply": text,
        "engel_capability_search_used": True,
        "provider_api_enabled": False,
        "network_enabled": False,
    }


# Engel's native Agent Kernel: one simple goal surface over the capability
# index, EngelScript, Conductor, Orchestra, Code Forge, and Governor.  This is
# intentionally before the older bundled-agent route: "engel agent do ..."
# should use Engel Main's own proven parts in Main chat, not leave the process
# for an unrelated provider-driven subprocess.
_ENGEL_AGENT_KERNEL_STATUS_RE = re.compile(
    r"^\s*(?:engel\s+work\s+status|engel\s+agent\s+kernel\s+(?:status|runs))"
    r"\b.*$",
    re.IGNORECASE | re.DOTALL,
)
_ENGEL_AGENT_KERNEL_DOCS_RE = re.compile(
    r"^\s*(?:engel\s+agent\s+kernel(?:\s+(?:docs|help))?|engel\s+work\s+help"
    r"|what\s+is\s+the\s+engel\s+agent\s+kernel)\s*[.!?]?\s*$",
    re.IGNORECASE,
)
_ENGEL_AGENT_KERNEL_RUN_RE = re.compile(
    r"^\s*(?:engel\s+work|engel\s+solve|engel\s+agent\s+(?:work|do|run|task)"
    r"|agent\s+(?:do|run|task)|ask\s+engel\s+agent|tell\s+engel\s+agent"
    r"|run\s+engel\s+agent)\b(.*)$",
    re.IGNORECASE | re.DOTALL,
)


def _normalize_discord_prompt(prompt: str) -> str:
    text = " ".join(str(prompt or "").casefold().split())
    if text.startswith("engel work "):
        text = text[len("engel work ") :]
    for typo in ("dicord", "discrod", "discort", "disord", "discrd", "discordd"):
        text = text.replace(typo, "discord")
    return text


def _owner_wants_discord_checkout(prompt: str) -> bool:
    text = _normalize_discord_prompt(prompt)
    if not text:
        return False
    if text.startswith(("what is", "what's", "whats", "tell me about", "explain", "why is")):
        return False
    if any(marker in text for marker in ("fix ", "wire ", "repair ", "rebuild ", "install ", "update ", "patch ")):
        return False
    if text in {"discord", "discord chat", "check out discord chat"}:
        return True
    # The chat voice card says "you are not a Discord guest". That identity
    # line is not a request to open the room. Training prompts carry it on
    # every turn, and the old check treated them as Discord checkout.
    stripped = text.replace("not a discord guest", " ").replace("not discord", " ")
    if "discord" not in stripped and "#general" not in stripped:
        return False
    return any(
        marker in stripped
        for marker in ("check", "open", "look", "read", "show", "status", "chat", "thread", "repeat", "replies")
    )


def _owner_discord_checkout_chat_intercept(
    prompt: str, request_id: str
) -> "dict[str, Any] | None":
    """Joshua asked Engel to read live Discord. Do not send this to Grok or the kernel."""
    if not _owner_wants_discord_checkout(prompt):
        return None
    if _owner_wants_discord_reply_to_sub_engel(prompt):
        return None
    base = str(os.environ.get("ENGEL_MAIN_SERVER_CHAT_URL") or "http://127.0.0.1:24680").strip().rstrip("/")
    url = base + "/discord/checkout"
    try:
        req = urllib.request.Request(
            url,
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json", "X-Engel-Bridge": "rog-discord-checkout"},
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        reply = str(
            payload.get("assistant_reply")
            or payload.get("assistant_output_text")
            or payload.get("reply")
            or ""
        ).strip()
        ok = payload.get("ok") is True and bool(reply)
        status = str(payload.get("status") or "discord checkout")
    except Exception as exc:
        reply = (
            "Did not read live Discord #general. "
            f"Checkout failed: {type(exc).__name__}."
        )
        ok = False
        status = "discord checkout failed"
    if not reply:
        reply = "Did not read live Discord #general."
        ok = False
    return {
        "id": request_id,
        "ok": ok,
        "status": status,
        "schema": "engel_main_local_model_worker_response_v1",
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "reply": reply,
        "engel_agent_kernel_used": False,
        "discord_checkout": True,
        "provider_api_enabled": False,
        "network_enabled": False,
        "readable_output_captured": True,
    }


def _owner_wants_discord_reply_to_sub_engel(prompt: str) -> bool:
    text = " ".join(str(prompt or "").casefold().split())
    if text.startswith("engel work "):
        text = text[len("engel work ") :]
    if "sub-engel" not in text and "sub engel" not in text and "subengel" not in text:
        return False
    return any(
        marker in text
        for marker in ("reply", "respond", "responed", "answer sub", "talk to sub", "collab")
    )


def _owner_reply_to_sub_engel_chat_intercept(
    prompt: str, request_id: str
) -> "dict[str, Any] | None":
    """Joshua asked Engel AI Main to reply to Sub-Engel. Post in Discord or admit failure."""
    if not _owner_wants_discord_reply_to_sub_engel(prompt):
        return None
    base = str(os.environ.get("ENGEL_MAIN_SERVER_CHAT_URL") or "http://127.0.0.1:24680").strip().rstrip("/")
    url = base + "/discord/reply-sub-engel"
    posted = False
    message_id = ""
    status = "discord owner reply did not run"
    try:
        req = urllib.request.Request(
            url,
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json", "X-Engel-Bridge": "rog-owner-reply-sub-engel"},
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        posted = payload.get("posted") is True and bool(payload.get("discord_message_id"))
        message_id = str(payload.get("discord_message_id") or "")
        status = str(payload.get("status") or status)
    except Exception as exc:
        posted = False
        status = f"discord owner reply failed: {type(exc).__name__}"
    if posted:
        reply = (
            "Posted in Discord #general to Sub-Engel.\n"
            "I named the CODE gap: work the last job Engel already named in Discord "
            "(catalog-land packs, then one done receipt). Stop looping engine.self_learn.\n"
            f"Discord message id: {message_id}\n"
            "This is done only because that message was actually posted."
        )
    else:
        reply = (
            "Did NOT post to Discord. I will not mark this done.\n"
            f"Status: {status}"
        )
    return {
        "id": request_id,
        "ok": posted,
        "status": status,
        "schema": "engel_main_local_model_worker_response_v1",
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "reply": reply,
        "engel_agent_kernel_used": False,
        "discord_posted": posted,
        "discord_message_id": message_id,
        "provider_api_enabled": False,
        "network_enabled": False,
        "readable_output_captured": True,
    }


_KERNEL_MODULE_MTIME: float | None = None


def _load_agent_kernel():
    """Reload Engel Agent Kernel when the D: source file changes.

    Cosmic Swarm keeps this worker alive across chat turns. Without a reload,
    kernel route maps (Android worker status, etc.) stay stuck at process start.
    """
    import importlib

    import engel_agent_kernel as kernel

    global _KERNEL_MODULE_MTIME
    kernel_path = ROOT / "engel_agent_kernel.py"
    try:
        mtime = kernel_path.stat().st_mtime
    except OSError:
        mtime = None
    if mtime is not None and (
        _KERNEL_MODULE_MTIME is None or mtime > _KERNEL_MODULE_MTIME
    ):
        kernel = importlib.reload(kernel)
        _KERNEL_MODULE_MTIME = mtime
    return kernel


def _engel_agent_kernel_chat_intercept(
    prompt: str, request_id: str
) -> "dict[str, Any] | None":
    text_in = str(prompt or "")
    # Form-graded prompt training can mention "code", "fix", or "write" inside
    # a building-code excerpt. Cosmic Swarm then prefixes "engel work ", which
    # would steal the turn from CT246 (live 2026-09-13: Construction hour 5,
    # Section 102.2 "this code", 0 wrappers, 21s kernel reject).
    if _is_training_delivery(text_in):
        return None

    def _reply(text: str, status: str) -> dict[str, Any]:
        return {
            "id": request_id,
            "ok": True,
            "status": status,
            "schema": "engel_main_local_model_worker_response_v1",
            "assistant_reply": text,
            "assistant_output_text": text,
            "reply": text,
            "engel_agent_kernel_used": True,
            "provider_api_enabled": False,
            "network_enabled": False,
        }

    try:
        kernel = _load_agent_kernel()

        if _ENGEL_AGENT_KERNEL_STATUS_RE.match(text_in):
            return _reply(kernel.render_agent_status(), "engel agent kernel ledger")
        if _ENGEL_AGENT_KERNEL_DOCS_RE.match(text_in):
            return _reply(kernel.render_agent_docs(), "engel agent kernel docs")
        match = _ENGEL_AGENT_KERNEL_RUN_RE.match(text_in)
        raw_goal = (match.group(1) or "").strip() if match else text_in.strip()
        android_status_ask = bool(
            getattr(kernel, "_ANDROID_WORKER_STATUS_RE", None)
            and kernel._ANDROID_WORKER_STATUS_RE.search(raw_goal)
        )
        if not match and not android_status_ask:
            return None
        goal = raw_goal
        if (
            _owner_wants_discord_reply_to_sub_engel(text_in)
            or _owner_wants_discord_reply_to_sub_engel(goal)
            or _owner_wants_discord_checkout(text_in)
            or _owner_wants_discord_checkout(goal)
        ):
            return None
        if not goal:
            return _reply(kernel.render_agent_docs(), "engel agent kernel usage")
        if getattr(kernel, "should_yield_to_companion_chat", None) and kernel.should_yield_to_companion_chat(
            goal
        ):
            # Let Chat: Auto Best / the model router answer creative HTML/game
            # asks. Conductor cannot produce those artifacts and fails closed.
            return None

        def _draft(prompt_text: str) -> str:
            receipt = _main_server_fast_chat(
                prompt=prompt_text,
                timeout=180,
                max_tokens=520,
                temperature=0.2,
                progress_request_id=request_id,
                chat_only=True,
                generation_seconds=170,
            )
            if isinstance(receipt, dict):
                return str(
                    receipt.get("assistant_reply")
                    or receipt.get("assistant_output_text")
                    or ""
                )
            return ""

        def _generate(prompt_text: str) -> str:
            reply = ""
            for _attempt in (1, 2):
                receipt = _main_server_fast_chat(
                    prompt=prompt_text,
                    timeout=180,
                    max_tokens=1200,
                    temperature=0.2,
                    progress_request_id=request_id,
                    chat_only=True,
                    generation_seconds=170,
                )
                reply = (
                    str(
                        receipt.get("assistant_reply")
                        or receipt.get("assistant_output_text")
                        or ""
                    )
                    if isinstance(receipt, dict)
                    else ""
                )
                if not _looks_like_lane_non_answer(reply):
                    return reply
            return reply

        with _request_progress_heartbeat(request_id, enabled=True):
            kernel_receipt = kernel.run_goal(
                goal,
                draft_fn=_draft,
                generate_fn=_generate,
            )
        kernel_response = _reply(
            kernel.render_agent_result(kernel_receipt),
            f"engel agent kernel {kernel_receipt.get('status', 'ran')}",
        )
        kernel_response["receipt"] = kernel_receipt
        kernel_response["lifted_intent"] = kernel_receipt.get("lifted_intent", {})
        kernel_response["lifted_intent_receipt_path"] = kernel_receipt.get(
            "lifted_intent_receipt_path", ""
        )
        return kernel_response
    except Exception as exc:  # a kernel bug must never consume the chat turn
        return _reply(
            f"Engel Agent Kernel failed: {type(exc).__name__}: {exc}",
            "engel agent kernel error",
        )


def _engel_script_chat_intercept(
    prompt: str, request_id: str, payload: dict[str, Any]
) -> "dict[str, Any] | None":
    match = _ENGEL_SCRIPT_CHAT_RE.match(str(prompt or ""))
    if not match:
        return None

    def _reply(text: str, status: str) -> dict[str, Any]:
        return {
            "id": request_id,
            "ok": True,
            "status": status,
            "schema": "engel_main_local_model_worker_response_v1",
            "assistant_reply": text,
            "assistant_output_text": text,
            "reply": text,
            "engel_script_used": True,
            "provider_api_enabled": False,
            "network_enabled": False,
        }

    try:
        import engel_script as es
    except Exception as exc:  # noqa: BLE001 -- missing module degrades to normal chat
        return _reply(
            f"EngelScript is not available on this host ({type(exc).__name__}).",
            "engel script unavailable",
        )
    try:
        verb = (match.group(1) or "").lower()
        body = (match.group(2) or "").strip()
        bare = (match.group(3) or "").lower()
        if bare in ("docs", "help", "language"):
            return _reply(es.render_engel_script_docs(), "engel script docs")
        if bare in ("examples", "plans"):
            return _reply(es.render_engel_script_examples(), "engel script examples")
        if verb == "validate":
            if not body:
                return _reply(es.render_engel_script_validate(), "engel script usage")
            return _reply(es.render_validate_body(body), "engel script validated")
        if verb == "run":
            if not body:
                return _reply(es.render_engel_script_run(), "engel script usage")
            return _reply(es.render_run_body(body), "engel script ran")
        if verb == "draft":
            if not body:
                return _reply(
                    "Usage: draft engel script <goal in plain words>",
                    "engel script usage",
                )
            with _request_progress_heartbeat(request_id, enabled=True):
                receipt = _main_server_fast_chat(
                    prompt=es.draft_prompt(body),
                    timeout=180,
                    max_tokens=420,
                    temperature=0.2,
                    progress_request_id=request_id,
                    chat_only=True,
                    generation_seconds=170,
                )
            model_reply = ""
            if isinstance(receipt, dict):
                model_reply = str(
                    receipt.get("assistant_reply")
                    or receipt.get("assistant_output_text")
                    or ""
                )
            if not model_reply.strip():
                return _reply(
                    "EngelScript draft: the local model lane returned no reply "
                    "(is CT246 chat up?). Nothing was drafted.",
                    "engel script draft unavailable",
                )
            return _reply(
                es.render_draft_result(body, model_reply), "engel script drafted"
            )
    except Exception as exc:  # noqa: BLE001 -- a script-surface bug must never eat a chat turn
        return _reply(
            f"EngelScript command failed: {type(exc).__name__}: {exc}",
            "engel script error",
        )
    return None


# The Conductor in the MAIN chat surface (docs/ENGEL_CONDUCTOR_DESIGN.md):
# "engel goal <text>" runs the full loop -- retrieve, draft with the local
# model lane, validate, run read-only, observe, repair once -- and persists
# the goal in the ledger. The drafter call is chat_only with the long
# generation budget: the drafting instruction text must never trip the build
# detector (same live lesson as the script draft flow, 2026-07-31).
# Tolerant of trailing filler ON PURPOSE: end-anchoring this meant "engel goal
# status please" missed the status branch, hit the goal branch, and opened a
# PHANTOM goal named "status please" -- drafting a plan for it, running it, and
# writing it permanently into the ledger (2026-08-01 review, reproduced on both
# the worker chain and classify_user_input).
_ENGEL_CONDUCTOR_STATUS_RE = re.compile(
    r"^\s*(?:engel\s+goals?\s+(?:status|ledger|list)|list\s+engel\s+goals"
    r"|engel\s+goals)\b.*$",
    re.IGNORECASE | re.DOTALL,
)
_ENGEL_CONDUCTOR_DOCS_RE = re.compile(
    r"^\s*(?:engel\s+conductor(?:\s+(?:docs|help))?|what\s+is\s+the\s+engel\s+conductor)"
    r"\s*[.!?]?\s*$",
    re.IGNORECASE,
)
_ENGEL_CONDUCTOR_GOAL_RE = re.compile(
    r"^\s*(?:(continue)\s+engel\s+goal|conduct\s+engel\s+goal|engel\s+goal)\b(.*)$",
    re.IGNORECASE | re.DOTALL,
)


def _engel_conductor_chat_intercept(
    prompt: str, request_id: str
) -> "dict[str, Any] | None":
    text_in = str(prompt or "")

    def _reply(text: str, status: str) -> dict[str, Any]:
        return {
            "id": request_id,
            "ok": True,
            "status": status,
            "schema": "engel_main_local_model_worker_response_v1",
            "assistant_reply": text,
            "assistant_output_text": text,
            "reply": text,
            "engel_conductor_used": True,
            "provider_api_enabled": False,
            "network_enabled": False,
        }

    try:
        if _ENGEL_CONDUCTOR_STATUS_RE.match(text_in):
            import engel_conductor as ec

            return _reply(ec.render_goal_status(), "engel goal ledger")
        if _ENGEL_CONDUCTOR_DOCS_RE.match(text_in):
            import engel_conductor as ec

            return _reply(ec.render_conductor_docs(), "engel conductor docs")
        match = _ENGEL_CONDUCTOR_GOAL_RE.match(text_in)
        if not match:
            return None
        import engel_conductor as ec

        body = (match.group(2) or "").strip()
        if not body:
            return _reply(ec.render_conduct(""), "engel conductor usage")

        def _draft(prompt_text: str) -> str:
            receipt = _main_server_fast_chat(
                prompt=prompt_text,
                timeout=180,
                max_tokens=420,
                temperature=0.2,
                progress_request_id=request_id,
                chat_only=True,
                generation_seconds=170,
            )
            if isinstance(receipt, dict):
                return str(
                    receipt.get("assistant_reply")
                    or receipt.get("assistant_output_text")
                    or ""
                )
            return ""

        with _request_progress_heartbeat(request_id, enabled=True):
            if match.group(1):
                conduct_receipt = ec.continue_goal(body, draft_fn=_draft)
            else:
                conduct_receipt = ec.conduct(body, draft_fn=_draft)
        return _reply(
            ec.render_conduct_result(conduct_receipt),
            f"engel goal {conduct_receipt.get('status', 'conducted')}",
        )
    except Exception as exc:  # noqa: BLE001 -- a conductor bug must never eat a chat turn
        return _reply(
            f"Engel Conductor failed: {type(exc).__name__}: {exc}",
            "engel conductor error",
        )


# The Orchestra in the MAIN chat surface (docs/ENGEL_ORCHESTRA_DESIGN.md):
# "engel orchestra <goal>" fans the goal into bounded parallel Conductor
# lanes -- the local model lane splits a plain goal, drafts/repairs each
# lane's plan (serialized through the Orchestra's one-in-flight lock), and
# synthesizes the lane outputs into one answer. Status/docs answer locally.
# The status branch is checked BEFORE the run branch and tolerates trailing
# filler -- the Conductor's phantom-goal lesson (2026-08-01) applies here
# verbatim: "engel orchestra status please" must never become a goal.
_ENGEL_ORCHESTRA_STATUS_RE = re.compile(
    r"^\s*(?:engel\s+orchestra\s+(?:status|runs|ledger)|list\s+engel\s+orchestra\s+runs)\b.*$",
    re.IGNORECASE | re.DOTALL,
)
_ENGEL_ORCHESTRA_DOCS_RE = re.compile(
    r"^\s*(?:engel\s+orchestra(?:\s+(?:docs|help))?|what\s+is\s+the\s+engel\s+orchestra)"
    r"\s*[.!?]?\s*$",
    re.IGNORECASE,
)
_ENGEL_ORCHESTRA_RUN_RE = re.compile(
    r"^\s*(?:orchestrate\s+engel\s+goal|engel\s+orchestrate|engel\s+orchestra)\b(.*)$",
    re.IGNORECASE | re.DOTALL,
)


def _engel_orchestra_chat_intercept(
    prompt: str, request_id: str
) -> "dict[str, Any] | None":
    text_in = str(prompt or "")

    def _reply(text: str, status: str) -> dict[str, Any]:
        return {
            "id": request_id, "ok": True, "status": status,
            "schema": "engel_main_local_model_worker_response_v1",
            "assistant_reply": text,
            "assistant_output_text": text,
            "reply": text,
            "engel_orchestra_used": True,
            "provider_api_enabled": False,
            "network_enabled": False,
        }

    try:
        if _ENGEL_ORCHESTRA_STATUS_RE.match(text_in):
            import engel_orchestra as eo

            return _reply(eo.render_orchestra_status(), "engel orchestra ledger")
        if _ENGEL_ORCHESTRA_DOCS_RE.match(text_in):
            import engel_orchestra as eo

            return _reply(eo.render_orchestra_docs(), "engel orchestra docs")
        match = _ENGEL_ORCHESTRA_RUN_RE.match(text_in)
        if not match:
            return None
        import engel_orchestra as eo

        body = (match.group(1) or "").strip()
        if not body:
            return _reply(eo.render_orchestrate(""), "engel orchestra usage")

        def _draft(prompt_text: str) -> str:
            receipt = _main_server_fast_chat(
                prompt=prompt_text,
                timeout=180,
                max_tokens=420,
                temperature=0.2,
                progress_request_id=request_id,
                chat_only=True,
                generation_seconds=170,
            )
            if isinstance(receipt, dict):
                return str(
                    receipt.get("assistant_reply")
                    or receipt.get("assistant_output_text")
                    or ""
                )
            return ""

        with _request_progress_heartbeat(request_id, enabled=True):
            orchestra_receipt = eo.orchestrate(body, draft_fn=_draft)
        return _reply(
            eo.render_orchestrate_result(orchestra_receipt),
            f"engel orchestra {orchestra_receipt.get('status', 'orchestrated')}",
        )
    except Exception as exc:  # noqa: BLE001 -- an orchestra bug must never eat a chat turn
        return _reply(
            f"Engel Orchestra failed: {type(exc).__name__}: {exc}",
            "engel orchestra error",
        )


# The Code Forge in the MAIN chat surface (docs/ENGEL_CODE_FORGE_DESIGN.md):
# "forge code <task>" generates Python + its tests, gates them, RUNS them in
# the sandbox, and repairs from the real stderr -- the loop that turns
# emitted text into proven code. The generator call is chat_only with the
# long budget so the task wording can never trip the build lane.
_ENGEL_FORGE_STATUS_RE = re.compile(
    r"^\s*(?:engel\s+forge\s+status|forge\s+status|list\s+forges|engel\s+forges)"
    r"\s*[.!?]?\s*$",
    re.IGNORECASE,
)
_ENGEL_FORGE_DOCS_RE = re.compile(
    r"^\s*(?:engel\s+(?:code\s+)?forge(?:\s+(?:docs|help))?"
    r"|what\s+is\s+the\s+engel\s+forge)\s*[.!?]?\s*$",
    re.IGNORECASE,
)
# "engel code forge <task>" must be an alternative here: without it that
# phrasing matched NO forge regex (the docs one is end-anchored, so trailing
# task text killed it) and fell through to _requested_app_build, turning a
# forge request into a real CT246 app-build order (2026-08-01 review,
# reproduced against the live regexes).
_ENGEL_FORGE_CODE_RE = re.compile(
    r"^\s*(?:forge\s+code|engel\s+code\s+forge|engel\s+forge\s+code|engel\s+forge)"
    r"\b(.*)$",
    re.IGNORECASE | re.DOTALL,
)


# Replies that are the LANE talking about itself rather than answering. A
# forge round costs a full generation, so spending one on lane noise is waste:
# the closure below retries these once instead of handing the Forge a
# non-answer to "repair". Observed live 2026-08-01: a code generation was
# refused by the persona style/quality gate (a gate tuned for conversational
# prose, applied to source code) and came back as this meta-message.
_LANE_NON_ANSWER_MARKERS = (
    "did not pass engel's style/quality gate",
    "the repair attempts were exhausted",
    "no finished result is being claimed",
    "i blocked that command",
)


def _unusable_chat_receipt(receipt: dict[str, Any] | None) -> bool:
    """True when CT returned a stall, style-gate card, or empty miss instead of an answer."""
    if not isinstance(receipt, dict):
        return True
    reply = " ".join(
        str(
            receipt.get("assistant_reply")
            or receipt.get("assistant_output_text")
            or ""
        ).split()
    ).casefold()
    status = str(receipt.get("status") or "").casefold()
    if not reply:
        return True
    if receipt.get("ok") is not True:
        return True
    if receipt.get("style_gate_rejected") is True:
        return True
    markers = (
        "did not pass engel's style/quality gate",
        "rejected by style gate",
        "provider fallback not permitted",
        "still on the last thought",
        "send that once more",
        "ct246 did not return a usable chat reply",
        "quality gate blocked",
        "only engelz can use engel tools",
        "only engelz can run admin",
        "diagnostics from discord",
        "i can chat here, but only engelz",
        "guest chat gate",
    )
    haystack = f"{status} {reply}"
    return any(marker in haystack for marker in markers)


def _looks_like_lane_non_answer(reply: str) -> bool:
    low = " ".join(str(reply or "").split()).casefold()
    if not low:
        return True
    if "file:" in low or "```" in low or "def " in low:
        return False  # it carried code; let the Forge judge it
    return any(marker in low for marker in _LANE_NON_ANSWER_MARKERS)


def _engel_forge_chat_intercept(
    prompt: str, request_id: str
) -> "dict[str, Any] | None":
    text_in = str(prompt or "")

    def _reply(text: str, status: str) -> dict[str, Any]:
        return {
            "id": request_id,
            "ok": True,
            "status": status,
            "schema": "engel_main_local_model_worker_response_v1",
            "assistant_reply": text,
            "assistant_output_text": text,
            "reply": text,
            "engel_forge_used": True,
            "provider_api_enabled": False,
            "network_enabled": False,
        }

    try:
        if _ENGEL_FORGE_STATUS_RE.match(text_in):
            import engel_code_forge as cf

            return _reply(cf.render_forge_status(), "engel forge status")
        if _ENGEL_FORGE_DOCS_RE.match(text_in):
            import engel_code_forge as cf

            return _reply(cf.render_forge_docs(), "engel forge docs")
        match = _ENGEL_FORGE_CODE_RE.match(text_in)
        if not match:
            return None
        import engel_code_forge as cf

        task = (match.group(1) or "").strip()
        if not task:
            return _reply(cf.render_forge(""), "engel forge usage")

        def _generate(prompt_text: str) -> str:
            reply = ""
            for _attempt in (1, 2):
                receipt = _main_server_fast_chat(
                    prompt=prompt_text,
                    timeout=180,
                    max_tokens=1200,
                    temperature=0.2,
                    progress_request_id=request_id,
                    chat_only=True,
                    generation_seconds=170,
                )
                reply = (
                    str(
                        receipt.get("assistant_reply")
                        or receipt.get("assistant_output_text")
                        or ""
                    )
                    if isinstance(receipt, dict)
                    else ""
                )
                if not _looks_like_lane_non_answer(reply):
                    return reply
            return reply

        with _request_progress_heartbeat(request_id, enabled=True):
            forge_receipt = cf.forge(task, generate_fn=_generate)
        return _reply(
            cf.render_forge_result(forge_receipt),
            f"engel forge {forge_receipt.get('status', 'ran')}",
        )
    except Exception as exc:  # noqa: BLE001 -- a forge bug must never eat a chat turn
        return _reply(
            f"Engel Code Forge failed: {type(exc).__name__}: {exc}",
            "engel forge error",
        )


_PENDING_ACTION: dict[str, Any] | None = None
_CONFIRM_WORDS = frozenset((
    "yes", "y", "yep", "yeah", "yup", "confirm", "confirmed", "do it", "run it",
    "go ahead", "proceed", "ok do it", "okay do it", "yes please", "run", "sure",
))
_DENY_WORDS = frozenset((
    "no", "n", "nope", "cancel", "stop", "don't", "dont", "nevermind",
    "never mind", "abort", "not now", "no thanks", "cancel it",
))


def _is_confirm(prompt: str) -> bool:
    low = _clean_text(prompt).strip().casefold().strip(".!? ")
    return low in _CONFIRM_WORDS or low.startswith(
        ("yes ", "confirm", "run it", "do it", "go ahead", "proceed", "yes,")
    )


def _is_deny(prompt: str) -> bool:
    low = _clean_text(prompt).strip().casefold().strip(".!? ")
    return low in _DENY_WORDS or low.startswith(
        ("no ", "no,", "cancel", "stop ", "abort", "don't", "dont", "never mind", "nevermind")
    )


def _is_info_question(prompt: str) -> bool:
    low = _clean_text(prompt).strip().casefold()
    return low.startswith((
        "what ", "how ", "why ", "is ", "are ", "does ", "do ", "which ",
        "when ", "where ", "who ", "explain", "tell me about",
    ))


def _plan_confirm_reply(plan: dict[str, Any]) -> str:
    lines = ["I can do that. Here's the plan — nothing runs until you say yes:"]
    for i, s in enumerate(plan.get("steps", []), 1):
        lines.append(f"  {i}. {s.get('desc')}")
    lines.append("Reply 'yes' to run it, or 'no' to cancel.")
    return "\n".join(lines)


def _plan_blocked_reply(plan: dict[str, Any]) -> str:
    lines = ["I blocked that command before execution because it matches a protected-action rule:"]
    for i, s in enumerate(plan.get("steps", []), 1):
        lines.append(f"  {i}. {s.get('desc')}")
        if s.get("reason"):
            lines.append(f"     Reason: {s.get('reason')}")
    return "\n".join(lines)


def _run_execution_plan(plan: dict[str, Any], request_id: str) -> dict[str, Any]:
    """Run a CONFIRMED plan's steps through the sandbox (denylist + secret-strip +
    timeout + output cap). Stops at the first failure. Returns a worker response."""
    try:
        import engel_sandbox
    except Exception as exc:
        reply = f"I couldn't load the sandbox to run it: {str(exc)[:160]}"
        return {
            "id": request_id, "ok": False, "status": "exec sandbox error",
            "schema": "engel_main_local_model_worker_response_v1",
            "assistant_reply": reply, "assistant_output_text": reply,
            "provider_api_enabled": False, "network_enabled": True,
        }
    results: list[dict[str, Any]] = []
    all_ok = True
    for step in plan.get("steps", []):
        r = engel_sandbox.run_sandboxed(
            list(step.get("argv") or []),
            tier=str(step.get("tier") or "restricted"),
            timeout=int(step.get("timeout") or 180),
            cwd=step.get("cwd"),
        )
        ok = bool(r.get("ok"))
        results.append({
            "desc": step.get("desc"), "ok": ok, "returncode": r.get("returncode"),
            "blocked": r.get("blocked"), "error": r.get("error"),
            "stdout_tail": (r.get("stdout") or "")[-600:],
            "stderr_tail": (r.get("stderr") or "")[-600:],
        })
        if not ok:
            all_ok = False
            break
    lines = ["Done — it ran cleanly:" if all_ok else "I ran it but hit a problem:"]
    for res in results:
        mark = "OK" if res["ok"] else ("BLOCKED" if res.get("blocked") else "FAILED")
        lines.append(f"  [{mark}] {res['desc']}")
        if not res["ok"]:
            detail = res.get("error") or res.get("stderr_tail") or res.get("stdout_tail") or "no detail"
            lines.append(f"        {str(detail)[:300]}")
    reply = "\n".join(lines)
    return {
        "id": request_id, "ok": all_ok, "status": "command execution",
        "schema": "engel_main_local_model_worker_response_v1",
        "assistant_reply": reply, "assistant_output_text": reply,
        "action": {"kind": "command_exec", "results": results},
        "provider_api_enabled": False, "network_enabled": True,
    }


# --- fleet dispatch through the AGENT MEETING ROOM (2026-07-07) ----------------
# Wire the chat worker to the existing meeting-room dispatch (engel_agent_meeting_
# room.dispatch_station_work) so a fleet-targeted request ("have alpha summarize X",
# "send this to the Sub-Engel") is staged to that device as a bounded, validated job
# with auto-return — instead of trying to run it locally. This is the correct fleet
# vehicle (per Joshua): phones/Sub-Engel already round-trip work this way.
_FLEET_STATIONS = {
    "alpha": {"name": "Android Worker Alpha", "equipment": "Android App Worker (WiFi)",
              "bridge": "Android Worker Job Packet", "skill_label": "Android Worker Skill"},
    "beta": {"name": "Android Worker Beta", "equipment": "Android App Worker (WiFi)",
             "bridge": "Android Worker Job Packet", "skill_label": "Android Worker Skill"},
    "gamma": {"name": "Android Worker Gamma", "equipment": "Android App Worker (WiFi)",
              "bridge": "Android Worker Job Packet", "skill_label": "Android Worker Skill"},
    "sub-engel": {"name": "Sub-Engel OS Worker", "equipment": "Sub-Engel OS Worker",
                  "bridge": "Sub-Engel Auto Route", "skill_label": "Sub-Engel Skill"},
}


def _requested_fleet_dispatch(prompt: str) -> dict[str, str] | None:
    """Detect 'have/ask/tell/send/dispatch <alpha|beta|gamma|sub-engel> [to] <task>'
    (or '<worker>: <task>') and return {target, task}. Info-questions are left to chat."""
    import re
    text = _clean_text(prompt).strip()
    low = text.casefold()
    if not low or low.startswith((
        "what ", "how ", "why ", "is ", "are ", "does ", "which ", "who ", "status",
    )):
        return None
    target = None
    for key in ("sub-engel", "sub engel", "subengel", "alpha", "beta", "gamma"):
        if re.search(rf"\b{re.escape(key)}\b", low):
            target = "sub-engel" if key.startswith("sub") else key
            break
    if target is None:
        # (20260711) Collective fleet orders ("all devices", "every worker") must
        # reach the SAME multi-device dispatcher — without this they fell through
        # to plain chat and the model just TALKED about dispatching.
        for key in (
            "all devices", "all workers", "every worker", "every device",
            "whole room", "whole fleet", "all phones", "all three phone",
            "phone workers", "android workers",
        ):
            if key in low:
                target = "fleet"
                break
    if target is None:
        return None
    # Match actual dispatch verbs as WORDS. The old substring checks treated
    # "unassigned device" as an `assign` order and the standard Training answer
    # form's "file, or route" as a `route` order. A review prompt containing
    # "every device" therefore became fleet work and returned no model answer.
    dispatch_verb = r"(?:have|ask|tell|give|get|dispatch|send|assign|route|use)"
    if target == "fleet":
        # A collective noun is common in technical questions ("fingerprinting
        # every device"). Treat it as an order only when a dispatch verb opens
        # the request, or immediately follows the collective target. This also
        # prevents a later answer-contract word such as "file, or route" from
        # changing the request's lane.
        has_intent = bool(
            re.match(
                rf"^\s*(?:please\s+)?(?:(?:can|could|would|will)\s+you\s+)?"
                rf"{dispatch_verb}\b",
                low,
            )
            or re.match(
                rf"^\s*(?:please\s+)?(?:for\s+)?(?:all|every|the whole)\s+"
                rf"(?:devices?|workers?|phones?|fleet|room)\b[^.!?]{{0,24}}"
                rf"\b{dispatch_verb}\b",
                low,
            )
        )
    else:
        # (2026-08-04) The named-target branch kept the bare whole-text verb search
        # the fleet branch above was fixed out of on 20260711, so the SAME answer
        # contract phrase ("file, or route") still flipped the lane whenever a
        # prompt's prose happened to mention a worker by name -- a training prompt
        # about worker liveness became a real work order to a phone, answered with a
        # canned 41-char line and no model reply. Require the verb to OPEN the
        # request or sit next to the named target, exactly as the fleet branch does.
        near = r"[^.!?]{0,24}"
        worker = r"(?:alpha|beta|gamma|sub[-\s]?engel)"
        has_intent = bool(
            re.match(
                rf"^\s*(?:please\s+)?(?:(?:can|could|would|will)\s+you\s+)?"
                rf"{dispatch_verb}\b",
                low,
            )
            or re.search(rf"\b{dispatch_verb}\b{near}\b{worker}\b", low)
            or re.search(rf"\b{worker}\b{near}\b{dispatch_verb}\b", low)
            or any(v in low for v in (
                "on alpha", "on beta", "on gamma", "on the sub", "have the sub",
            ))
            or re.search(rf"{worker}\s*[:,]", low)
        )
    if not has_intent:
        return None
    task = re.sub(
        r"^\s*(please\s+)?(have|ask|tell|give|get|dispatch(?:\s+to)?|send(?:\s+to)?|"
        r"assign(?:\s+to)?|route(?:\s+to)?|on the|on)\s+(the\s+)?"
        r"(alpha|beta|gamma|sub[-\s]?engel|desktop)\s*(worker)?\s*(to|:|,|please)?\s*",
        "", text, flags=re.I,
    ).strip(" :,-")
    if not task or task.casefold() == text.casefold():
        m = re.search(r"(?:alpha|beta|gamma|sub[-\s]?engel|desktop)\s*[:,]\s*(.+)$", text, flags=re.I)
        task = m.group(1).strip() if m else text
    return {"target": target, "task": task or text}


def _run_fleet_dispatch(prompt: str, request_id: str) -> dict[str, Any] | None:
    """Dispatch a fleet-targeted request through the meeting room; None if not one."""
    fd = _requested_fleet_dispatch(prompt)
    if fd is None:
        return None
    # Use the same multi-device dispatcher as the visible UI wrapper. The old
    # shortcut selected only the first named target, so "all phones and Sub"
    # became Sub-only and explicit Gamma work could drift to another worker.
    try:
        from run_engel_ui_chat_meeting_room_llm import (  # noqa: E402
            _run_explicit_device_work_request,
        )

        receipt = _run_explicit_device_work_request(prompt, time.perf_counter())
        reply = str(
            receipt.get("assistant_reply")
            or receipt.get("assistant_output_text")
            or ""
        )
        return {
            "id": request_id,
            "ok": receipt.get("ok") is True,
            "status": str(receipt.get("status") or "fleet dispatch"),
            "schema": "engel_main_local_model_worker_response_v1",
            "assistant_reply": reply,
            "assistant_output_text": reply,
            "receipt": receipt,
            "action": {
                "kind": "fleet_dispatch",
                "target": "multi-device"
                if _prompt_mentions_multiple_fleet_targets(prompt)
                else fd["target"],
                "dispatch_status": str(receipt.get("status") or ""),
            },
            "provider_api_enabled": False,
            "network_enabled": True,
        }
    except Exception:
        pass
    target, task = fd["target"], fd["task"]
    station = _FLEET_STATIONS.get(target)
    if not station:
        return None
    try:
        import engel_agent_meeting_room as _mr
        status, reply = _mr.dispatch_station_work(station, "", task)
    except Exception as exc:
        status, reply = "error", f"{type(exc).__name__}: {str(exc)[:180]}"
    label = {"alpha": "Alpha", "beta": "Beta", "gamma": "Gamma",
             "sub-engel": "the Sub-Engel"}.get(target, target)
    out = f"Dispatched to {label} through the agent meeting room ({status}).\n{reply}"
    return {
        "id": request_id,
        "ok": status in ("Assigned", "Returned"),
        "status": "fleet dispatch",
        "schema": "engel_main_local_model_worker_response_v1",
        "assistant_reply": out,
        "assistant_output_text": out,
        "action": {"kind": "fleet_dispatch", "target": target, "dispatch_status": status},
        "provider_api_enabled": False,
        "network_enabled": True,
    }


def _prompt_mentions_multiple_fleet_targets(prompt: str) -> bool:
    low = _clean_text(prompt).casefold()
    return any(
        phrase in low
        for phrase in (
            "all devices",
            "all workers",
            "all phones",
            "all three phone",
            "phones and sub",
            "phone workers and sub",
        )
    )


# (2026-08-09) Training-delivered prompts wrap the ask in a depth header and an answer
# contract. Those marks mean PRACTICE TEXT: the turn must produce prose to be graded,
# never execute a build or scaffold — "code assertions (checkable in the corpus)" beside
# "calculation package" tripped the verb+target detector in BOTH 8h construction runs
# (conical stop 20260808 turn 31; build-lifecycle failure 20260809 turn 31). Same
# precedent as the skill-creator hijack fix (20260808): gate the DETECTOR, not call sites.
_TRAINING_DELIVERY_MARKS = (
    "training depth:",
    "training task:",
    "answer only in this filled-in form",
    "use exactly this structure",
    "answer the way you would answer",
)


def _is_training_delivery(text: str) -> bool:
    low = str(text or "").casefold()
    return any(mark in low for mark in _TRAINING_DELIVERY_MARKS)


def _requested_workspace_setup(prompt: str) -> str | None:
    """(2026-07-07) Detect an imperative 'set up / create the <X> environment /
    workspace / project' order so Engel actually SCAFFOLDS it (a bounded,
    non-destructive action) instead of only replying with words. Questions ABOUT
    environments are left to the chat model. Returns the description or None."""
    text = _clean_text(prompt).strip()
    if _is_training_delivery(text):
        return None
    low = text.casefold()
    if not low:
        return None
    question_starts = (
        "what ", "how ", "why ", "is ", "are ", "does ", "do ", "which ",
        "can you explain", "explain ", "tell me about", "summarize ",
        "summary ", "report ", "list ", "review ",
    )
    if any(low.startswith(q) for q in question_starts):
        return None
    # A real app/tool build may mention its internal projects or workspace. The
    # executable build lane owns those requests; setup only owns bare scaffolds.
    if _requested_app_build(text) is not None:
        return None
    verbs = (
        "set up", "setup", "set-up", "create", "scaffold", "spin up", "spin-up",
        "initialize", "initialise", "make ", "build ", "generate ", "stand up",
    )
    targets = (
        "environment", "workspace", "project", "dev env", "coding env",
        "programming env",
    )
    if any(v in low for v in verbs) and any(t in low for t in targets):
        return text
    return None


# "…, overwrite" in a build/setup order = rebuild the existing workspace in place.
# Shared with engel_build_lane (which imports it); stripped from the description so
# the slug still matches the original order's dir.
_OVERWRITE_RX = re.compile(r"(?i)[,;]?\s*(?<![a-z0-9_])overwrite(?:\s+it)?(?![a-z0-9_])")


def _run_workspace_setup(prompt: str, request_id: str) -> dict[str, Any] | None:
    """Execute the scaffold action for a setup order; returns a worker response
    dict, or None if this prompt is not a setup order."""
    desc = _requested_workspace_setup(prompt)
    if desc is None:
        return None
    want_overwrite = bool(_OVERWRITE_RX.search(desc))
    if want_overwrite:
        desc = re.sub(r"\s{2,}", " ", _OVERWRITE_RX.sub("", desc)).strip(" ,.;")
    try:
        import engel_workspace_scaffold as _scaffold
        res = _scaffold.scaffold(desc, overwrite=want_overwrite)
    except Exception as exc:  # never let an action crash the chat turn
        res = {"ok": False, "error": str(exc)[:200]}
    if res.get("ok"):
        path = str(res.get("path", ""))
        folder = Path(path).name
        files = ", ".join(res.get("files", []))
        if res.get("already_exists"):
            reply = (
                f"That workspace already exists at {path} (files: {files}). I left it "
                f"untouched — repeat the setup order with the word 'overwrite' and I'll replace it."
            )
        else:
            run_hint = "demo.py" if res.get("kind") == "math_trig" else "main.py"
            # This action also serves the CT246 chat service — the run command
            # must match the HOST the workspace landed on, not assume Windows.
            if os.name == "nt":
                runner = f"runtime\\python310\\python.exe workspaces\\{folder}\\{run_hint}"
            else:
                runner = f"python3 workspaces/{folder}/{run_hint}"
            reply = (
                f"Done — I set up a {res.get('kind')} workspace at {path}. "
                f"Files: {files}. Run it:  {runner}"
            )
    else:
        reply = f"I couldn't set that up: {res.get('error', 'unknown error')}"
    return {
        "id": request_id,
        "ok": bool(res.get("ok")),
        "status": "workspace setup action",
        "schema": "engel_main_local_model_worker_response_v1",
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "action": {"kind": "workspace_scaffold", "result": res},
        "provider_api_enabled": False,
        "network_enabled": False,
    }


_BUILD_TARGETS = (
    "game", "app", "application", "tool", "script", "program", "website", "web app",
    "web page", "webpage", "api", "cli", "bot", "calculator", "clone", "widget",
    "dashboard", "simulator", "generator", "converter", "utility", "gui", "snake",
    "pong", "tic tac toe", "tic-tac-toe", "quiz", "timer", "stopwatch", "todo",
    "to-do", "maze", "guessing game", "hangman",
    # (2026-07-11 soak) project-shaped nouns that fell through to the code lane
    # ("build me a json pretty PRINTER" / "matrix multiplication DEMO" got code
    # as text instead of a built workspace). Word-boundary matched like the rest,
    # so prose like "client update" still can't false-trigger.
    "demo", "parser", "formatter", "printer", "checker", "tracker", "analyzer",
    # (2026-07-12 UI marathon) more software-artifact "-er/-or" nouns that fell
    # through ("drawing register EXPORTER ... csv WRITER" got code-as-text).
    # Kept to unambiguously-software words — prose-common nouns like report/log/
    # plan/schedule are deliberately EXCLUDED so "write a report" stays prose.
    "exporter", "importer", "writer", "reader", "viewer", "editor", "manager",
    "scheduler", "estimator", "configurator", "visualizer", "validator",
    "monitor", "organizer", "calculator", "counter", "summarizer",
    # (2026-08-14) unambiguous FILE-artifact targets. "Lets make a pdf with hello
    # world then a 3d one spinning" fell through to the quick chat lane, which asked
    # WHICH TOOL to use (Acrobat/Word/Blender) instead of building the thing —
    # side-by-side receipt ENGEL_CHAT_COMPARE_20260814T054727Z.json. A pdf /
    # spreadsheet / qr code is always a produced artifact, never prose, so these
    # carry none of the report/log/plan ambiguity that keeps prose nouns out.
    "pdf", "spreadsheet", "qr code",
    # (2026-08-21) "Recreate this using Flutter" fell through to Grok narration
    # because Flutter was neither a language nor a build target.
    "flutter",
)

# (2026-07-09; consolidated 2026-07-10) ONE language table for the build lane. Previously
# three parallel tables (_LANG_TABLE / _LANG_LABEL / _RUN_PLANS) keyed by the same 11 keys,
# which drifted (java's shown command didn't match what ran). Detection is IN ORDER
# (typescript / javascript before java so "javascript" never matches "java"). Per row:
#   key      - language id
#   names    - phrase fragments that select this language. Bare " go " false-matched the
#              English verb, so Go needs "golang"/"in go"/"go program"/... instead.
#   label    - the "generate <label>" phrasing for the gen prompt.
#   entry    - default entry filename.
#   run      - human run-command shown in the reply; may use {entry} and {stem}.
#   tool     - toolchain label for the caveat (None => no install needed).
#   bin      - check-binary; if not on PATH the reply shows an install caveat (None => ok).
#   compile  - argv for a compile step, or None (interpreted). {entry}/{exe} filled in.
#   run_argv - argv actually executed. {py}/{entry}/{exe}/{stem} filled in.
_LANGS = [
    # (2026-07-11) ts-node dropped: `npx ts-node` self-installed at run time then
    # crashed on a ts-node/TypeScript version clash (CT246). Node ≥22.18 strips
    # types natively, so plain `node main.ts` runs on BOTH hosts (ROG node 24,
    # CT246 node 22.23 — verified). Label steers generation to erasable-types
    # syntax (native stripping rejects enums/namespaces/parameter properties).
    {"key": "typescript", "names": ("typescript", " ts ", "in ts", ".ts"), "label": "TypeScript for Node.js (type annotations only — no enums, no namespaces, no parameter properties, no npm packages; it runs via Node's native type stripping)",
     "entry": "main.ts", "run": "node {entry}", "tool": "Node.js 22.18+", "bin": "node",
     "compile": None, "run_argv": ["node", "{entry}"]},
    {"key": "javascript", "names": ("javascript", " js ", "in js", "node.js", "nodejs", " node "), "label": "JavaScript for Node.js (no npm packages)",
     "entry": "main.js", "run": "node {entry}", "tool": "Node.js", "bin": "node",
     "compile": None, "run_argv": ["node", "{entry}"]},
    {"key": "web", "names": ("website", "web page", "webpage", "web app", "html page", "landing page", " html", " css "), "label": "a self-contained website using plain HTML, CSS and JavaScript (no frameworks or CDNs)",
     "entry": "index.html", "run": "open index.html in a browser", "tool": None, "bin": None,
     "compile": None, "run_argv": None},
    {"key": "flutter", "names": ("flutter", " dart app", "in dart", " dart "), "label": "a Flutter app in Dart (Material widgets, local persistence only, no extra pub packages except shared_preferences, no network)",
     "entry": "lib/main.dart", "run": "flutter run", "tool": "Flutter SDK", "bin": "flutter",
     "compile": None, "run_argv": None},
    {"key": "rust", "names": ("rust", "cargo"), "label": "Rust (std only, single crate)",
     "entry": "main.rs", "run": "rustc {entry} -o app && ./app   (or cargo run)", "tool": "the Rust toolchain", "bin": "rustc",
     "compile": ["rustc", "{entry}", "-o", "{exe}"], "run_argv": ["{exe}"]},
    {"key": "go", "names": ("golang", "in go", "go program", "go app", "go code", "go script", "go file", "go server", "go cli", ".go"), "label": "Go (standard library only)",
     "entry": "main.go", "run": "go run {entry}", "tool": "the Go toolchain", "bin": "go",
     "compile": None, "run_argv": ["go", "run", "{entry}"]},
    {"key": "java", "names": ("java",), "label": "Java (a single Main class, JDK only)",
     "entry": "Main.java", "run": "javac {entry} && java {stem}", "tool": "a JDK", "bin": "javac",
     "compile": ["javac", "{entry}"], "run_argv": ["java", "{stem}"]},
    {"key": "cpp", "names": ("c++", "cpp"), "label": "C++ (standard library only)",
     "entry": "main.cpp", "run": "g++ {entry} -o app && ./app", "tool": "g++ (MinGW)", "bin": "g++",
     "compile": ["g++", "{entry}", "-o", "{exe}"], "run_argv": ["{exe}"]},
    {"key": "c", "names": ("c program", "in c ", "c language", "c code"), "label": "C (standard library only)",
     "entry": "main.c", "run": "gcc {entry} -o app && ./app", "tool": "gcc (MinGW)", "bin": "gcc",
     "compile": ["gcc", "{entry}", "-o", "{exe}"], "run_argv": ["{exe}"]},
    {"key": "bash", "names": ("bash", "shell script", ".sh"), "label": "a Bash shell script",
     "entry": "script.sh", "run": "bash {entry}", "tool": None, "bin": "bash",
     "compile": None, "run_argv": ["bash", "{entry}"]},
    {"key": "ruby", "names": ("ruby",), "label": "Ruby (standard library only)",
     "entry": "main.rb", "run": "ruby {entry}", "tool": "Ruby", "bin": "ruby",
     "compile": None, "run_argv": ["ruby", "{entry}"]},
    {"key": "python", "names": ("python", " py ", "in py", ".py"), "label": "Python (standard library only, no pip installs)",
     "entry": "main.py",
     # run hint is operator-facing: ROG shows the app runtime python, CT246 (Linux) python3
     "run": ("runtime\\python310\\python.exe {entry}" if os.name == "nt" else "python3 {entry}"),
     "tool": None, "bin": None,
     "compile": None, "run_argv": ["{py}", "{entry}"]},
]

# extra places to look for a toolchain binary beyond PATH (installed for the user but
# not always on the app-spawned worker's PATH).
_TOOLCHAIN_HINT_DIRS = [
    r"C:\Program Files\nodejs",
    r"C:\Users\ziese\.cargo\bin",
    r"D:\a.WorkSpace\bin",
    r"C:\Ruby34-x64\bin",
    r"D:\toolchains\go\bin",
    r"D:\toolchains\mingw64\bin",
    r"D:\b.WorkSpace\flutter_windows_3.41.9-stable\flutter\bin",
    r"D:\b.WorkSpace\flutter_local_sdk\bin",
]


def _toolchain_present(binary: "str | None") -> bool:
    """True if a toolchain binary is runnable — on PATH or in a known install dir."""
    if not binary:
        return True
    import shutil
    if shutil.which(binary):
        return True
    for d in _TOOLCHAIN_HINT_DIRS:
        for ext in ("", ".exe", ".cmd", ".bat"):
            try:
                if os.path.isfile(os.path.join(d, binary + ext)):
                    return True
            except Exception:
                pass
    return False

# derived from the single _LANGS table above (no more drift between the three)
_LANG_LABEL = {L["key"]: L["label"] for L in _LANGS}


def _infer_build_language(low: str) -> "tuple[str, str, str, str | None, str | None]":
    """Return (lang_key, default_entry, run_template, toolchain_label, check_binary)
    from the request text. Defaults to Python (runs on the Engel runtime)."""
    for L in _LANGS:
        if any(n in low for n in L["names"]):
            return L["key"], L["entry"], L["run"], L["tool"], L["bin"]
    _py = next(L for L in _LANGS if L["key"] == "python")
    return "python", _py["entry"], _py["run"], _py["tool"], _py["bin"]


def _operator_request_text(text: str) -> str:
    """(20260711) The Flutter app wraps code-ish prompts in a capability preamble
    ("Engel code capability context: <language list> ... Operator request follows:
    <request>"). Everything the build lane decides from the prompt — detection,
    the project name/description, and the LANGUAGE — must come from the OPERATOR
    request, never the wrapper (a wrapped build once scaffolded to
    workspaces\\engel_code_capability_context_preferred_langua... and the
    wrapper's language list made a python request build C++)."""
    m = re.search(r"(?is)\boperator request follows:\s*", text)
    return text[m.end():].strip() if m else text


def _requested_app_build(prompt: str) -> str | None:
    """(2026-07-09) Detect 'create/make/build/write me a <game/app/tool/...>' — a
    request to actually GENERATE a small runnable program, not just talk about one.
    Distinct from _requested_workspace_setup (which only sets up an empty skeleton
    for an 'environment/workspace/project'). Questions ABOUT code are left to chat."""
    if _is_training_delivery(_clean_text(prompt)):
        return None
    text = _operator_request_text(_clean_text(prompt).strip())
    low = text.casefold()
    if not low:
        return None
    build_verbs = (
        "create", "make ", "build ", "write ", "code ", "generate", "develop",
        "program ", "implement", "give me a", "give me an", "put together",
        "recreate", "rebuild", "port ", "convert", "rewrite",
    )
    if re.search(
        r"\b(?:recreate|rebuild|port|convert|rewrite)\b",
        low,
    ) and re.search(r"\b(?:this|it|that)\b", low) and re.search(
        r"\b(?:flutter|dart)\b",
        low,
    ):
        return text
    # UI retry/continue must beat the question-prefix skip. "Check again
    # Sub-Engel... Then Continue." resumes the last app build. An explicit
    # "recreate this using Flutter" line above keeps the operator's own text.
    try:
        import engel_build_lane as _build_lane

        continued = _build_lane.resolve_continued_build_request(text)
        if continued:
            return continued
    except Exception:
        pass
    if low.startswith((
        "what ", "how do", "how does", "how can", "why ", "is ", "are ", "does ",
        "explain ", "tell me about", "can you explain", "do you ", "should i",
    )):
        return None
    if not any(v in low for v in build_verbs):
        return None
    # Build targets are words/phrases, not arbitrary substrings. Without this
    # boundary, "client update" matched the `cli` target and became a project.
    if not any(
        re.search(rf"(?<![a-z0-9_]){re.escape(target)}(?![a-z0-9_])", low)
        for target in _BUILD_TARGETS
    ):
        return None
    return text


def _requested_router_work_order(prompt: str, attachments: list[dict[str, Any]] | None = None) -> bool:
    """Create/update/room jobs belong on the CT action router, not a one-shot chat model."""
    text = _operator_request_text(_clean_text(prompt))
    low = text.casefold()
    if not low:
        return False
    if _requested_app_build(text) is not None or _requested_workspace_setup(text) is not None:
        return True
    room = any(
        term in low
        for term in (
            "meeting room",
            "agent room",
            "with this room",
            "using this room",
            "use this room",
            "create something with this room",
        )
    )
    create = any(term in low for term in ("create", "make ", "build ", "dispatch", "send "))
    if room and create:
        return True
    if attachments and any(
        term in low for term in ("update", "create", "build", "add more", "more comments", "more posts", "fix this")
    ):
        return True
    try:
        import engel_build_lane as _build_lane

        if _build_lane.is_continue_or_retry_build_request(text):
            return True
    except Exception:
        pass
    return False


def _extract_project_files(text: str, default_entry: str) -> "dict[str, str]":
    """Pull one or MORE files out of a model reply. Multi-file protocol:
        FILE: <relative/path>
        ```<lang>
        <contents>
        ```
    (repeated). If the reply is a single fenced block (or just looks like code), it
    becomes the default entry file. Returns {relpath: contents}."""
    if not text:
        return {}
    files: dict[str, str] = {}
    # Split on FILE: markers so each file owns everything up to the NEXT marker. The old
    # single non-greedy regex stopped at the first ``` inside a file body, truncating any
    # file that itself contains a fenced code block (markdown generators, READMEs, etc.).
    # The protocol marker is intentionally case-sensitive. Generated JavaScript
    # commonly contains object properties such as `file: "fallback.txt"`; treating
    # those as FILE markers truncates the owning source file and fabricates a path.
    parts = re.split(r"(?m)^[ \t]*FILE:[ \t]*", text)
    if len(parts) > 1:
        for seg in parts[1:]:
            nl = seg.find("\n")
            if nl < 0:
                continue
            rel = seg[:nl].strip().strip('`"\'').replace("\\", "/").lstrip("/")
            body = seg[nl + 1:]
            # greedy fence match -> stops at the LAST ``` in this file's segment, so inner
            # fences are kept; fall back to the raw segment if it wasn't fenced.
            fm = re.search(r"```[a-zA-Z0-9+#.\-]*[ \t]*\n(.*)\n[ \t]*```", body, re.S)
            content = fm.group(1) if fm else re.sub(
                r"\A\s*```[a-zA-Z0-9+#.\-]*[ \t]*\r?\n", "", body, count=1
            )
            if rel and ".." not in rel.split("/"):
                files[rel] = content.rstrip("\n") + "\n"
    if files:
        return files
    # Local coder models sometimes follow a structured repair request with a
    # JSON file bundle instead of FILE markers. Treat only an exact
    # {"files": [{"path": ..., "content": ...}]}-shaped object as project
    # output; arbitrary JSON remains ordinary source for the default entry.
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if not isinstance(candidate, dict):
            continue
        rows = candidate.get("files")
        json_files: dict[str, str] = {}
        if isinstance(rows, dict):
            iterable = [
                {
                    "path": path,
                    "content": (
                        content.get("content")
                        if isinstance(content, dict)
                        else content
                    ),
                }
                for path, content in rows.items()
            ]
        elif isinstance(rows, list):
            iterable = rows
        else:
            iterable = []
        for row in iterable:
            if not isinstance(row, dict):
                continue
            rel = str(
                row.get("path")
                or row.get("name")
                or row.get("file")
                or ""
            ).strip().strip('`"\'').replace("\\", "/").lstrip("/")
            content = row.get("content")
            if (
                rel
                and ".." not in rel.split("/")
                and ":" not in rel.split("/", 1)[0]
                and isinstance(content, str)
                and content.strip()
            ):
                json_files[rel] = content.rstrip("\n") + "\n"
        if json_files:
            return json_files
    # (2026-07-28) Salvage the dominant local-coder failure shape: multiple
    # fenced blocks whose FIRST line is a comment naming the file
    # (```python\n# fibonacci.py\n...```) with no FILE: markers anywhere.
    # Receipts ENGEL_MAIN_SERVER_BUILD_LANE_20260728T{002909,003851}*.json show
    # the 3B coder emitting exactly this instead of the FILE: protocol.
    # All-or-nothing: every fence must carry a filename-comment head, so code
    # examples embedded in prose never get mis-salvaged as project files.
    fence_blocks = re.findall(
        r"```[a-zA-Z0-9+#.\-]*[ \t]*\r?\n(.*?)\n[ \t]*```", text, re.S
    )
    if len(fence_blocks) >= 2:
        comment_name = re.compile(
            r"^\s*(?:#|//|--|;|<!--)\s*([\w./\\-]+\.[A-Za-z0-9]{1,8})\s*(?:-->)?\s*$"
        )
        salvage: dict[str, str] = {}
        for block in fence_blocks:
            head, _, body = block.partition("\n")
            named = comment_name.match(head)
            rel = named.group(1).replace("\\", "/").lstrip("/") if named else ""
            if not rel or ".." in rel.split("/") or not body.strip():
                salvage = {}
                break
            salvage[rel] = body.rstrip("\n") + "\n"
        if len(salvage) >= 2:
            return salvage
    m = re.search(r"```[a-zA-Z0-9+#.\-]*\s*\n(.*?)```", text, re.S)
    if m:
        return {default_entry: m.group(1).rstrip("\n") + "\n"}
    if re.search(r"^\s*(?:import |from |def |class |function |package |fn |#include|"
                 r"<!doctype|<html|public class|using |const |let |echo |print\()", text, re.I | re.M):
        return {default_entry: text.strip("\n") + "\n"}
    return {}


# signals that a generated program WAITS for keyboard input — those can't be auto-run
# to completion (they'd hang on empty stdin), so Engel reports the run command instead.
_INTERACTIVE_SIGNALS = (
    "input(", "raw_input(", "sys.stdin",
    "scanf", "getchar", "gets(", "fgets", "std::cin", "cin>>", "cin >>",
    "bufio.newreader", "fmt.scan",
    "new scanner(", "bufferedreader", "system.in", "console.readline",
    "readline", "process.stdin", "prompt(",
    "io::stdin", "read_line",
    "stdin.gets", "gets.chomp", "$stdin", "\nread ", "read -",
)

# per-language run plan: (compile_argv | None, run_argv). Tokens {py} {entry} {exe}
# {stem} are substituted. None compile = interpreted or go-run (compile+run in one).
# (compile_argv, run_argv) per language, derived from _LANGS so the shown run command and
# the actually-executed argv can never drift apart again. Web has no run plan (open in browser).
_RUN_PLANS = {L["key"]: (L["compile"], L["run_argv"]) for L in _LANGS if L["run_argv"]}


def _project_is_interactive(files: "dict[str, str]", lang: str = "") -> bool:
    blob = ("\n".join(files.values())).lower()
    signals = _INTERACTIVE_SIGNALS
    if lang == "bash":
        # Bash commonly uses `while read` over a pipe/process substitution. Run
        # Bash under the existing empty-stdin timeout instead of classifying all
        # read commands as interactive and skipping proof entirely.
        signals = tuple(sig for sig in signals if sig not in {"\nread ", "read -"})
    return any(sig in blob for sig in signals)


# markers that identify the real entry point inside a file body
_ENTRY_MARKERS = (
    "if __name__", "def main(", "func main(", "public static void main",
    "int main(", "fn main(", "function main(", "<!doctype", "<html",
    "void main(", "runApp(",
)


def _pick_entry(files: "dict[str, str]", default_entry: str) -> str:
    """Choose the file to compile/run for a multi-file project. Picking the first
    extracted file (dict order) runs a helper/module instead of the program, so:
    prefer the language default name, then a conventional entry (main/index/app/…)
    of the right extension, then a file with an entry marker in its body, then any
    file of the right extension, and only then fall back to the first file."""
    names = list(files.keys())
    if default_entry in files:
        return default_entry
    dext = Path(default_entry).suffix.lower()
    conventional = ("main", "index", "app", "__main__", "program", "server", "run")
    for want in conventional:
        for rel in names:
            p = Path(rel)
            if p.suffix.lower() == dext and p.stem.lower() == want:
                return rel
    for rel in names:
        body = files[rel].lower()
        if Path(rel).suffix.lower() == dext and any(mk in body for mk in _ENTRY_MARKERS):
            return rel
    for rel in names:
        if Path(rel).suffix.lower() == dext:
            return rel
    return next(iter(files))


def _resolve_bin(name: str, search_path: str) -> str:
    import shutil
    return shutil.which(name, path=search_path) or shutil.which(name) or name


# env-var names whose VALUE could be a secret; stripped before we run model-written code
_SECRET_ENV_HINTS = (
    "KEY", "SECRET", "TOKEN", "PASSWORD", "PASSWD", "CREDENTIAL", "APIKEY",
    "PRIVATE", "COOKIE", "BEARER", "CLIENT_SECRET", "ACCESS_KEY", "AUTH_",
)


def _safe_child_env() -> "dict[str, str]":
    """os.environ minus anything that looks like a secret. Generated programs are
    third-party code — they must not be able to read Engel's API keys/tokens out of
    the environment. Prefer engel_sandbox.safe_env() if present; else strip by name."""
    try:
        import engel_sandbox
        if hasattr(engel_sandbox, "safe_env"):
            return dict(engel_sandbox.safe_env())
    except Exception:
        pass
    env: "dict[str, str]" = {}
    for k, v in os.environ.items():
        if any(h in k.upper() for h in _SECRET_ENV_HINTS):
            continue
        env[k] = v
    return env


def _run_bounded(argv, cwd, env, timeout, creation):
    """subprocess.run-alike that kills the WHOLE process tree on timeout. On Windows a
    plain subprocess timeout only terminates the direct child; a compiler that forked a
    linker, or a program that spawned helpers, leaks those grandchildren. Returns
    (returncode|None, stdout, stderr, timed_out)."""
    group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = subprocess.Popen(
        argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        creationflags=creation | group,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
        return proc.returncode, out or "", err or "", False
    except subprocess.TimeoutExpired:
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, creationflags=creation)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            out, err = proc.communicate(timeout=5)
        except Exception:
            out, err = "", ""
        return None, out or "", err or "", True


def _execute_project(lang: str, dest_path: str, entry: str, timeout: int = 15) -> dict:
    """Compile (if needed) + RUN a just-built project inside its workspace, bounded by
    a timeout + empty stdin + output cap, with the Engel toolchain dirs on PATH and the
    Go cache off C:. Returns {ran, output, exit_code, compile_error, timed_out}."""
    plan = _RUN_PLANS.get(lang)
    if lang == "web" or not plan:
        return {"ran": False, "note": "not runnable in a terminal"}
    dest = Path(dest_path)
    env = _safe_child_env()
    extra = os.pathsep.join(d for d in _TOOLCHAIN_HINT_DIRS if os.path.isdir(d))
    env["PATH"] = ((extra + os.pathsep) if extra else "") + os.environ.get("PATH", "")
    if os.name == "nt":
        # Keep the Go cache off C: (ROG no-C rule). On Linux these Windows paths
        # leaked through and broke go entirely ('GOPATH entry is relative: "D"').
        env.setdefault("GOCACHE", r"D:\toolchains\gocache")
        env.setdefault("GOPATH", r"D:\toolchains\gopath")
    else:
        # The secret-stripped child env carries no $HOME, and go REFUSES to run
        # without a resolvable cache dir — pin both under the app root.
        env.setdefault("GOCACHE", str(ROOT / "runtime" / "temp" / "gocache"))
        env.setdefault("GOPATH", str(ROOT / "runtime" / "temp" / "gopath"))
    exe = str(dest / "app.exe")
    subst = {"py": sys.executable, "entry": entry, "exe": exe, "stem": Path(entry).stem}

    def _fill(argv: "list[str]") -> "list[str]":
        out = []
        for a in argv:
            for k, v in subst.items():
                a = a.replace("{" + k + "}", v)
            out.append(a)
        return out

    creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    compile_argv, run_argv = plan
    if compile_argv:
        cargv = _fill(compile_argv)
        cargv[0] = _resolve_bin(cargv[0], env["PATH"])
        try:
            rc, cout, cerr, ctimed = _run_bounded(cargv, str(dest), env, 45, creation)
        except Exception as exc:
            return {"ran": False, "compile_error": str(exc)[:400]}
        if ctimed:
            return {"ran": False, "compile_error": "compile timed out (45s)"}
        if rc != 0:
            return {"ran": False, "compile_error": (cerr or cout or "compile failed").strip()[:1200]}
    rargv = _fill(run_argv)
    rargv[0] = _resolve_bin(rargv[0], env["PATH"])
    # (2026-07-12) Generated python projects sometimes use a PACKAGE layout with
    # RELATIVE imports (pkg/main.py, `from .mod import X`). Running that entry as
    # a plain script dies with "attempted relative import with no known parent
    # package" — run it as a module (python -m pkg.main, cwd=workspace) instead.
    if lang == "python":
        entry_path = dest / entry
        nested = "/" in entry.replace("\\", "/")
        try:
            relative_imports = nested and bool(
                re.search(r"(?m)^\s*from\s+\.", entry_path.read_text(encoding="utf-8", errors="replace"))
            )
        except Exception:
            relative_imports = False
        if relative_imports:
            dotted = entry.replace("\\", "/").rsplit(".py", 1)[0].replace("/", ".")
            rargv = [rargv[0], "-m", dotted]
    try:
        rc, rout, rerr, timed = _run_bounded(rargv, str(dest), env, timeout, creation)
    except Exception as exc:
        return {"ran": False, "compile_error": str(exc)[:300]}
    if timed:
        return {"ran": True, "timed_out": True, "output": (rout or "")[:1500]}
    out = rout or ""
    if (rerr or "").strip():
        out += ("\n[stderr] " + rerr.strip())
    return {"ran": True, "timed_out": False, "exit_code": rc, "output": out[:1800]}


def _run_app_build(prompt: str, request_id: str, payload: dict[str, Any]) -> "dict[str, Any] | None":
    """Generate a real, runnable program for a 'create me a <thing>' request and
    write it into a new workspace. Returns None (fall through to normal chat) if the
    request isn't a build order or code generation fails."""
    desc = _requested_app_build(prompt)
    if desc is None:
        return None
    low = _operator_request_text(_clean_text(prompt)).casefold()
    lang, entry, run_tmpl, toolchain, check_bin = _infer_build_language(low)
    lang_label = _LANG_LABEL.get(lang, _LANG_LABEL["python"])
    gen_prompt = (
        f"The user asked Engel to build this: {desc}\n\n"
        f"Build it in {lang_label}. Make it complete and genuinely runnable.\n"
        "If it needs MORE THAN ONE file, output EACH file exactly like this:\n"
        "FILE: <relative/path>\n```\n<file contents>\n```\n"
        "Repeat for every file. If a single file is enough, output ONE fenced code "
        "block. Output ONLY the code/files — no explanation before or after."
    )
    timeout = min(max(30, int(payload.get("timeout") or 90)), 120)
    max_tokens = max(1600, int(payload.get("max_tokens") or 1600))
    text = ""
    if _FAILOVER_AVAILABLE:
        try:
            res_gen = _failover.run_with_failover(
                gen_prompt,
                chain=["rog-gpu", "gemini-api", "codex-cli", "claude-cli", "chatgpt-browser"],
                timeout_s=timeout, max_tokens=max_tokens,
            )
            if res_gen.ok:
                text = res_gen.reply or ""
        except Exception:
            text = ""
    files = _extract_project_files(text, entry)
    if not files or sum(len(c) for c in files.values()) < 40:
        return None  # no usable code generated -> fall through to normal chat
    entry_actual = _pick_entry(files, entry)
    run_hint = run_tmpl.replace("{entry}", entry_actual).replace("{stem}", Path(entry_actual).stem)

    def _regenerate_from_error(failure: str, previous: dict[str, str]) -> dict[str, str]:
        """One bounded repair: hand the compiler/runtime's OWN words back to
        the model. Before this, this fallback path observed a compile error and
        told the operator to ask for a rebuild -- the error text existed, was
        shown to a human, and was never given to the thing that could act on
        it. CT's build lane already repairs this way
        (engel_build_lane._verification_issues); this makes the ROG fallback
        behave the same if it is ever reached. NOTE: by policy this helper runs
        only AFTER CT246 (verify_engel_worker_ct_build_policy), so this is
        hardening for the degraded path, not the primary build lane."""
        if not _FAILOVER_AVAILABLE:
            return {}
        listing = "\n".join(
            f"FILE: {name}\n```\n{body.rstrip()}\n```" for name, body in previous.items()
        )[:12000]
        repair = (
            f"The {lang_label} project you just wrote FAILED. Fix it.\n\n"
            f"What failed:\n{failure.strip()[:1500]}\n\n"
            f"Previous files:\n{listing}\n\n"
            "Output the corrected files in the same FILE: format, complete "
            "contents for every file you change. Output ONLY the code/files."
        )
        try:
            res_fix = _failover.run_with_failover(
                repair,
                chain=["rog-gpu", "gemini-api", "codex-cli", "claude-cli", "chatgpt-browser"],
                timeout_s=timeout,
                max_tokens=max_tokens,
            )
        except Exception:  # noqa: BLE001 -- a failed repair keeps the first result
            return {}
        if not res_fix.ok:
            return {}
        fixed = _extract_project_files(res_fix.reply or "", entry)
        if not fixed or sum(len(c) for c in fixed.values()) < 40:
            return {}
        return fixed
    try:
        import engel_workspace_scaffold as _scaffold
        res = _scaffold.write_project(desc, files, run_hint=run_hint)
    except Exception as exc:  # never let a build crash the chat turn
        res = {"ok": False, "error": str(exc)[:200]}
    run_result = None
    if res.get("ok"):
        path = str(res.get("path", ""))
        nfiles = len([f for f in res.get("files", []) if f != "README.md"])
        have_tool = _toolchain_present(check_bin)
        run_cmd = res.get("run_hint", run_hint)
        if res.get("already_exists"):
            reply = (
                f"That project already exists at {path}. I left it untouched — say "
                f"'overwrite' if you want me to rebuild it."
            )
        else:
            base = f"Done — I built a {lang} project ({nfiles} file{'s' if nfiles != 1 else ''}) at {path}."
            interactive = _project_is_interactive(files, lang)
            # (2026-07-09) BUILD-AND-RUN: execute non-interactive programs and show the
            # real output in chat. Interactive ones (games waiting for input) would hang,
            # so we hand back the run command instead. Web opens in a browser.
            if lang != "web" and have_tool and not interactive:
                run_result = _execute_project(lang, path, entry_actual, timeout=15)
            # OBSERVE -> REPAIR (one round): a compile error is evidence, not a
            # dead end. Rewrite the SAME workspace and re-execute so the reply
            # reports what actually happened after the fix.
            repair_note = ""
            if run_result and run_result.get("compile_error"):
                fixed = _regenerate_from_error(str(run_result.get("compile_error") or ""), files)
                if fixed:
                    fixed_entry = _pick_entry(fixed, entry_actual)
                    try:
                        res_fix = _scaffold.write_project(
                            desc, fixed, run_hint=run_hint, overwrite=True,
                            exact_name=True, name=Path(path).name,
                        )
                    except Exception as exc:  # noqa: BLE001 -- keep the first result
                        res_fix = {"ok": False, "error": str(exc)[:200]}
                    if res_fix.get("ok"):
                        files = fixed
                        entry_actual = fixed_entry
                        res = res_fix
                        path = str(res_fix.get("path", path))
                        nfiles = len([f for f in res_fix.get("files", []) if f != "README.md"])
                        base = (
                            f"Done — I built a {lang} project ({nfiles} "
                            f"file{'s' if nfiles != 1 else ''}) at {path}."
                        )
                        run_result = _execute_project(lang, path, entry_actual, timeout=15)
                        repair_note = (
                            " (first attempt didn't compile; I read the error, "
                            "rewrote it, and re-ran)"
                        )
            if run_result and run_result.get("ran") and not run_result.get("timed_out"):
                out = (run_result.get("output") or "").strip() or "(the program produced no output)"
                reply = f"{base}{repair_note} I ran it — output:\n\n{out}"
            elif run_result and run_result.get("timed_out"):
                out = (run_result.get("output") or "").strip()
                reply = (
                    f"{base} I ran it but it didn't finish within 15s (long-running or waiting for input)."
                    + (f" Partial output:\n\n{out}" if out else f" Run it yourself:  {run_cmd}")
                )
            elif run_result and run_result.get("compile_error"):
                tried = (
                    "I read the error and rewrote it once; it still fails."
                    if repair_note
                    else "I couldn't rewrite it automatically (no repair lane returned code)."
                )
                reply = (
                    f"{base} But it didn't compile:\n\n"
                    f"{run_result['compile_error'].strip()[:800]}\n\n{tried}"
                )
            elif interactive:
                tool = "" if have_tool else f"  (install {toolchain} first)"
                reply = f"{base} It's interactive — run it yourself to use it:\n  {run_cmd}{tool}"
            else:
                tool = "" if have_tool else f"  (install {toolchain} to run it)"
                reply = f"{base} Run it with:  {run_cmd}{tool}"
    else:
        reply = f"I generated the code but couldn't save it: {res.get('error', 'unknown error')}"
    return {
        "id": request_id,
        "ok": bool(res.get("ok")),
        "status": "app build action",
        "schema": "engel_main_local_model_worker_response_v1",
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "action": {"kind": "app_build", "language": lang, "result": res, "run": run_result},
        "provider_api_enabled": True,
        "network_enabled": True,
    }


_LAST_FAST_CHAT_TRANSPORT_ERROR = ""


def _router_fallback_allowed() -> bool:
    """Laptop and next-model fallbacks stay on unless explicitly turned off.

    The old Flutter default passed ``0``. That value now means on. Only
    ``off`` or ``disabled`` keeps a missed CT246 turn from trying the next lane.
    """
    raw = str(os.environ.get("ENGEL_MAIN_ALLOW_LAPTOP_LOCAL_FALLBACK") or "1").strip().lower()
    return raw not in {"off", "disabled"}


def _fallback_catalog_ids(selected_model_id: str) -> list[str]:
    try:
        from engel_model_cohesion import fallback_ids_for

        return list(fallback_ids_for(selected_model_id))
    except Exception:
        return [
            "ct-qwen25-7b-instruct",
            "nvidia-nemotron-3-super-120b",
            "grok-4.6",
        ]


def _nvidia_api_model_for_catalog(catalog: dict[str, Any] | None) -> str:
    selected = str((catalog or {}).get("selected_model_id") or "").strip()
    if not selected:
        return ""
    try:
        from engel_model_cohesion import lookup_catalog

        sel = lookup_catalog(selected)
    except Exception:
        return ""
    if str(sel.get("provider") or "") != "nvidia":
        return ""
    return str(sel.get("api_model") or "")


def _nvidia_secret() -> str:
    for name in ("ENGEL_NVIDIA_API_KEY", "NVIDIA_API_KEY", "NGC_API_KEY", "NIM_API_KEY"):
        value = str(os.environ.get(name) or "").strip()
        if value:
            return value
    path = ROOT / "run" / "secrets" / "nvidia.env"
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return ""
    wanted = {"ENGEL_NVIDIA_API_KEY", "NVIDIA_API_KEY", "NGC_API_KEY", "NIM_API_KEY"}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() in wanted:
            token = value.strip().strip("'").strip('"')
            if token:
                return token
    return ""


def _nvidia_turn_text(prompt: str, context_items: list[dict[str, Any]] | None) -> str:
    chunks = [str(prompt or "").strip()]
    for item in context_items or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("content") or item.get("body") or item.get("excerpt") or "").strip()
        if not text:
            continue
        name = str(item.get("name") or item.get("title") or "context").strip() or "context"
        chunks.append(f"[{name}]\n{text}")
    return "\n\n".join(chunk for chunk in chunks if chunk)[:180000]


def _nvidia_large_model_chat(
    prompt: str,
    context_items: list[dict[str, Any]] | None,
    max_tokens: int,
) -> dict[str, Any] | None:
    """Ask the NVIDIA integrate API large models, and keep the full turn."""
    secret = _nvidia_secret()
    if not secret:
        return None
    user_text = _nvidia_turn_text(prompt, context_items)
    if not user_text:
        return None
    try:
        budget = max(4096, min(16384, int(max_tokens or 0) or 4096))
    except (TypeError, ValueError):
        budget = 4096
    url = str(
        os.environ.get("ENGEL_NVIDIA_CHAT_COMPLETIONS_URL")
        or "https://integrate.api.nvidia.com/v1/chat/completions"
    ).strip()
    models = (
        "nvidia/nemotron-3-super-120b-a12b",
        "nvidia/nemotron-3-ultra-550b-a55b",
    )
    for model in models:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Your name is Engel. Answer as Engel. "
                        "Use every part of the user message. Do not drop context, names, numbers, or excerpts."
                    ),
                },
                {"role": "user", "content": user_text},
            ],
            "temperature": 0.35,
            "max_tokens": budget,
            "stream": False,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {secret}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except Exception:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        choices = data.get("choices") if isinstance(data, dict) else None
        message = choices[0].get("message") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
        reply = str(message.get("content") or "").strip() if isinstance(message, dict) else ""
        if not reply:
            continue
        return {
            "ok": True,
            "status": "nvidia large model kept the full turn",
            "assistant_reply": reply,
            "assistant_output_text": reply,
            "prompt": user_text,
            "provider": "nvidia",
            "model": model,
            "bridge_kind": "nvidia_nim",
            "provider_bridge_used": True,
        }
    return None


def _main_server_fast_chat(
    prompt: str,
    timeout: int,
    max_tokens: int,
    temperature: float,
    attachments: list[dict[str, Any]] | None = None,
    context_items: list[dict[str, Any]] | None = None,
    conversation_id: str = "",
    progress_request_id: str = "",
    ui_provider: str = "",
    ui_model: str = "",
    inbox_metadata: dict[str, Any] | None = None,
    chat_only: bool = False,
    generation_seconds: int = 0,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """generation_seconds: explicit budget for a KNOWN-long generation (the
    EngelScript draft flow). The default caps -- 45 s server-side, 90 s socket
    -- are tuned for short conversational turns; a richer prompt legitimately
    needs longer, and silently inheriting the chat cap turned a working draft
    into "the local model lane returned no reply" (live 2026-07-31). Raising
    the budget is opt-in per call, so ordinary chat latency is untouched."""
    global _LAST_FAST_CHAT_TRANSPORT_ERROR
    _LAST_FAST_CHAT_TRANSPORT_ERROR = ""
    if str(os.environ.get("ENGEL_MAIN_SERVER_ENABLED") or "1").strip().lower() in {"0", "false", "no", "off"}:
        return None
    operator_prompt = _operator_request_text(prompt)
    # chat_only: the caller KNOWS this is a pure chat generation (e.g. the
    # EngelScript draft flow, whose instruction text legitimately contains
    # build-verb vocabulary). Skip action detection entirely -- the 2026-07-31
    # live proof showed the draft prompt tripping _requested_app_build and
    # launching a conical 4-worker build assembly for a text reply.
    server_prompt = (
        operator_prompt
        if chat_only
        else _server_prompt_override_for_truth_route(operator_prompt)
    )
    action_request = bool(
        not chat_only
        and (
            _requested_app_build(operator_prompt) is not None
            or _requested_workspace_setup(operator_prompt) is not None
        )
    )
    conical_orchestration: dict[str, Any] = {}
    if not chat_only and _requested_app_build(operator_prompt) is not None:
        try:
            from run_engel_ui_chat_meeting_room_llm import _run_conical_build_orchestration

            conical_orchestration = _run_conical_build_orchestration(operator_prompt)
        except Exception as exc:
            conical_orchestration = {
                "schema": "engel_conical_build_orchestration_v1",
                "required": True,
                "ok": False,
                "status": "failed_orchestration_start",
                "final_status": "failed",
                "error": str(exc),
                "expected_worker_count": 4,
                "returned_worker_count": 0,
            }

    def _conical_transport_failure(error: str) -> dict[str, Any] | None:
        global _LAST_FAST_CHAT_TRANSPORT_ERROR
        _LAST_FAST_CHAT_TRANSPORT_ERROR = str(error or "")
        if not conical_orchestration:
            return None
        failed: dict[str, Any] = {
            "schema": "engel_main_local_model_worker_response_v1",
            "ok": False,
            "status": "conical build failed before CT246 returned a build receipt",
            "build_verified": False,
            "assistant_reply": (
                "The build failed because the CT246 build lane did not return a valid receipt. "
                "No finished result is being claimed."
            ),
            "assistant_output_text": (
                "The build failed because the CT246 build lane did not return a valid receipt. "
                "No finished result is being claimed."
            ),
            "reply": (
                "The build failed because the CT246 build lane did not return a valid receipt. "
                "No finished result is being claimed."
            ),
            "main_server_chat_service_used": False,
            "main_server_chat_url": _server_chat_url(),
            "main_server_chat_error": error,
        }
        try:
            from run_engel_ui_chat_meeting_room_llm import _finalize_conical_build_orchestration

            finalized = _finalize_conical_build_orchestration(conical_orchestration, failed)
        except Exception as exc:
            finalized = dict(conical_orchestration)
            finalized.update(
                {
                    "final_ok": False,
                    "final_status": "failed",
                    "build_verified": False,
                    "finalization_error": str(exc),
                }
            )
        failed["conical_orchestration"] = finalized
        failed["conical_job_id"] = str(finalized.get("job_id") or "")
        failed["conical_job_status"] = "failed"
        failed["conical_worker_returned_count"] = int(finalized.get("returned_worker_count") or 0)
        failed["conical_worker_expected_count"] = int(finalized.get("expected_worker_count") or 4)
        failed["agent_meeting_room_used"] = True
        failed["meeting_room_server_used"] = True
        return failed

    request_payload = {
        "prompt": server_prompt,
        "source": "engel_ai_main_ui",
        "client": "rog_desktop_controller",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "timeout": min(
            max(3, timeout),
            generation_seconds
            if generation_seconds > 0
            else (1800 if action_request else 90),
        ),
        "prefer_fast_local_chat": True,
        "metadata": {
            "worker_source": "engel_desktop_local_model_worker_fast_proxy",
            "worker_contract": "rog_ui_to_ct246_chat_v1",
            "conversation_id": conversation_id,
        },
    }
    if chat_only:
        # Narrow-only signal for CT: this turn is pure text generation; the
        # service must not dispatch meeting-room orders or action lanes on the
        # prompt's wording (the EngelScript draft flow's goal text is operator
        # prose and may legitimately mention workers/builds).
        request_payload["chat_only"] = True
    _merge_inbox_metadata(request_payload, inbox_metadata)
    _stamp_catalog_selection(request_payload, catalog or {})
    router_lane = bool((catalog or {}).get("automatic_router_lane") is True)
    if not ui_provider and router_lane:
        nvidia_model = _nvidia_api_model_for_catalog(catalog)
        if nvidia_model:
            ui_provider = "nvidia"
            ui_model = nvidia_model
    if ui_provider and router_lane:
        # Chat-box provider picker: an intentional dropdown choice is the
        # explicit force contract CT246 honors (force_provider key).
        request_payload["provider"] = ui_provider
        request_payload["selected_provider"] = ui_provider
        request_payload["force_provider"] = True
        if ui_model:
            request_payload["model"] = ui_model
            request_payload["provider_model"] = ui_model
    elif not _prompt_explicitly_names_provider(prompt):
        # Engel AI Main's desktop chat should be Engel first: ROG UI -> CT246
        # local model. Provider bridges remain available only when the user
        # explicitly names one.
        request_payload["provider"] = "local"
        request_payload["selected_provider"] = "local"
    _enforce_local_only_training(request_payload)
    _apply_main_ui_local_failure_fallback(request_payload)
    if attachments:
        request_payload["attachments"] = attachments
    _apply_image_vision_lane(request_payload, attachments)
    if context_items:
        request_payload["context_items"] = context_items
    if conical_orchestration:
        request_payload["conical_orchestration"] = conical_orchestration
    body = json.dumps(_clean_json_value(request_payload), ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        _server_chat_url(),
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    # Real provider turns through CT regularly take 30-60s (Claude CLI bridge
    # hit 44.6s on 2026-07-01); the old 25s cap aborted turns the server was
    # about to answer and shoved them into the slower fallback lanes.
    try:
        default_cap = "2100" if action_request else "90"
        cap = int(float(os.environ.get("ENGEL_WORKER_SERVER_CHAT_TIMEOUT_CAP", default_cap) or default_cap))
    except ValueError:
        cap = 2100 if action_request else 90
    if action_request:
        cap = max(cap, 2100)
    if _attachments_have_still_images(attachments):
        cap = max(cap, 210)
    if generation_seconds > 0:
        # The socket must outlive the server's own budget, or a generation that
        # succeeds on CT still reads as a transport failure here.
        cap = max(cap, generation_seconds + 30)
    socket_timeout = min(max(3, timeout), max(10, cap))
    if action_request:
        # A medium local build can legitimately span several bounded inference
        # calls. Keep the HTTP request attached for the full CT action window;
        # the heartbeat above prevents Flutter from treating that wait as idle.
        socket_timeout = min(max(max(3, timeout), 2100), max(2100, cap))
    try:
        with _request_progress_heartbeat(
            progress_request_id,
            enabled=action_request,
        ):
            with urllib.request.urlopen(req, timeout=socket_timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        # CT246 intentionally returns a non-2xx response when every generated
        # draft fails its semantic quality gate. Preserve that safe, audited
        # response instead of treating it as a transport failure and looking
        # for an unaudited route outside Engel.
        try:
            raw = exc.read().decode("utf-8", errors="replace")
        except Exception:
            raw = ""
        if not raw:
            return _conical_transport_failure(str(exc))
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return _conical_transport_failure(str(exc))
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _conical_transport_failure(f"invalid CT246 JSON response: {exc}")
    if not isinstance(parsed, dict):
        return _conical_transport_failure("CT246 response was not a JSON object")
    reply = str(
        parsed.get("assistant_reply")
        or parsed.get("reply")
        or parsed.get("assistant_output_text")
        or ""
    ).strip()
    if not reply:
        receipt = parsed.get("receipt")
        if isinstance(receipt, dict):
            reply = str(
                receipt.get("assistant_reply")
                or receipt.get("reply")
                or receipt.get("assistant_output_text")
                or ""
            ).strip()
    if not reply:
        return _conical_transport_failure("CT246 response contained no assistant reply")
    receipt = parsed.get("receipt") if isinstance(parsed.get("receipt"), dict) else parsed
    normalized = dict(receipt)
    normalized.update(
        {
            "ok": parsed.get("ok") is True or normalized.get("ok") is True,
            "status": str(parsed.get("status") or normalized.get("status") or "server chat replied"),
            "assistant_reply": reply,
            "assistant_output_text": reply,
            "reply": reply,
            "provider": str(parsed.get("provider") or normalized.get("provider") or "engel-main-server"),
            "runtime_provider": str(parsed.get("runtime_provider") or normalized.get("runtime_provider") or ""),
            "long_lived_local_model_worker_used": True,
            "model_service_transport": "stdio_jsonl",
            "model_service_server_enabled": True,
            "main_server_chat_service_used": True,
            "main_server_chat_url": _server_chat_url(),
            "worker_original_prompt": prompt,
            "worker_server_prompt": server_prompt,
            "worker_server_prompt_override_used": server_prompt != prompt,
            "worker_forced_ct_local_provider": not _prompt_explicitly_names_provider(prompt),
            "worker_request_latency_ms": int((time.perf_counter() - started) * 1000),
        }
    )
    if conical_orchestration:
        ct_conical_receipt_path = str(normalized.get("ct246_conical_receipt_path") or "")
        ct_conical_persistence_ok = normalized.get("ct246_conical_persistence_ok") is True
        try:
            from run_engel_ui_chat_meeting_room_llm import _finalize_conical_build_orchestration

            conical_orchestration = _finalize_conical_build_orchestration(
                conical_orchestration,
                normalized,
            )
        except Exception as exc:
            conical_orchestration = dict(conical_orchestration)
            conical_orchestration.update(
                {
                    "final_ok": False,
                    "final_status": "failed",
                    "build_verified": normalized.get("build_verified") is True,
                    "finalization_error": str(exc),
                }
            )
        normalized["conical_orchestration"] = conical_orchestration
        normalized["conical_job_id"] = str(conical_orchestration.get("job_id") or "")
        normalized["conical_job_status"] = str(conical_orchestration.get("final_status") or "failed")
        normalized["conical_worker_returned_count"] = int(conical_orchestration.get("returned_worker_count") or 0)
        normalized["conical_worker_expected_count"] = int(conical_orchestration.get("expected_worker_count") or 4)
        conical_orchestration["ct246_receipt_path"] = ct_conical_receipt_path
        conical_orchestration["ct246_conical_persistence_ok"] = ct_conical_persistence_ok
        conical_orchestration["ct246_source_of_truth"] = bool(ct_conical_receipt_path)
        normalized["agent_meeting_room_used"] = True
        normalized["meeting_room_server_used"] = True
        normalized["chat_only_no_android_or_sub_engel"] = False
        worker_summary = (
            f"Worker assembly: {normalized['conical_worker_returned_count']}/"
            f"{normalized['conical_worker_expected_count']} required workers returned; "
            f"final conical status: {normalized['conical_job_status'].upper()}."
        )
        current_reply = str(normalized.get("assistant_reply") or normalized.get("assistant_output_text") or "").rstrip()
        normalized["assistant_reply"] = current_reply + "\n\n" + worker_summary
        normalized["assistant_output_text"] = normalized["assistant_reply"]
        normalized["reply"] = normalized["assistant_reply"]
        receipt_path_text = str(conical_orchestration.get("receipt_path") or "").strip()
        if receipt_path_text:
            try:
                receipt_path = Path(receipt_path_text)
                receipt_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = receipt_path.with_suffix(receipt_path.suffix + ".tmp")
                temp_path.write_text(
                    json.dumps(conical_orchestration, indent=2, sort_keys=True),
                    encoding="utf-8",
                )
                os.replace(temp_path, receipt_path)
                normalized["conical_final_receipt_written"] = True
                normalized["conical_final_receipt_path"] = str(receipt_path)
            except Exception as exc:
                normalized["conical_final_receipt_written"] = False
                normalized["conical_final_receipt_error"] = str(exc)
    return normalized


def _server_chat_stream_url() -> str:
    base = str(os.environ.get("ENGEL_MAIN_SERVER_CHAT_URL") or "http://127.0.0.1:24680").strip().rstrip("/")
    return base + "/chat/stream"


def _stream_server_chat(
    prompt: str,
    request_id: str,
    timeout: int,
    max_tokens: int,
    temperature: float,
    attachments: list[dict[str, Any]] | None = None,
    context_items: list[dict[str, Any]] | None = None,
    conversation_id: str = "",
    ui_provider: str = "",
    ui_model: str = "",
    inbox_metadata: dict[str, Any] | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Stream a chat turn from CT246's SSE endpoint, emitting one stdout JSONL
    `{"id","delta"}` line per token as it arrives so the Flutter UI can render
    the reply live. Returns the final response dict, or None on a clean connect
    failure BEFORE any token (caller then falls back to the blocking lane). A
    mid-stream drop after tokens returns what was received (never None) so the
    blocking lane can't produce a duplicate second reply."""
    if str(os.environ.get("ENGEL_MAIN_SERVER_ENABLED") or "1").strip().lower() in {"0", "false", "no", "off"}:
        return None
    server_prompt = _server_prompt_override_for_truth_route(
        _operator_request_text(prompt)
    )
    request_payload: dict[str, Any] = {
        "prompt": server_prompt,
        "source": "engel_ai_main_ui",
        "client": "rog_desktop_controller",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "timeout": min(max(3, timeout), 210 if _attachments_have_still_images(attachments) else 180),
        "stream": True,
        "prefer_fast_local_chat": True,
        "metadata": {
            "worker_source": "engel_desktop_local_model_worker_stream_proxy",
            "worker_contract": "rog_ui_to_ct246_chat_v1",
            "conversation_id": conversation_id,
        },
    }
    _merge_inbox_metadata(request_payload, inbox_metadata)
    _stamp_catalog_selection(request_payload, catalog or {})
    router_lane = bool((catalog or {}).get("automatic_router_lane") is True)
    if ui_provider and router_lane:
        request_payload["provider"] = ui_provider
        request_payload["selected_provider"] = ui_provider
        request_payload["force_provider"] = True
        if ui_model:
            request_payload["model"] = ui_model
            request_payload["provider_model"] = ui_model
    elif not _prompt_explicitly_names_provider(prompt):
        request_payload["provider"] = "local"
        request_payload["selected_provider"] = "local"
    _enforce_local_only_training(request_payload)
    _apply_main_ui_local_failure_fallback(request_payload)
    if attachments:
        request_payload["attachments"] = attachments
    _apply_image_vision_lane(request_payload, attachments)
    if context_items:
        request_payload["context_items"] = context_items
    body = json.dumps(_clean_json_value(request_payload), ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        _server_chat_stream_url(),
        data=body,
        headers={"Accept": "text/event-stream", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        cap = int(float(os.environ.get("ENGEL_WORKER_SERVER_CHAT_TIMEOUT_CAP", "180") or "180"))
    except ValueError:
        cap = 180
    started = time.perf_counter()
    pieces: list[str] = []
    got_delta = False
    got_activity = False
    final_receipt: dict[str, Any] | None = None
    final_reply = ""
    final_ok = False
    # (2026-07-07 audit Res-1) Cap the stream connect/first-token socket timeout well
    # below the client's per-turn deadline so a HUNG CT (TCP-up but unresponsive)
    # surfaces fast and leaves budget for the blocking /chat + multi-AI failover,
    # instead of the client hard-killing the worker mid-turn. Healthy streams keep
    # tokens flowing far faster than this gap, so they are unaffected.
    try:
        stream_socket_cap = int(os.environ.get("ENGEL_WORKER_STREAM_SOCKET_TIMEOUT", "25") or "25")
    except ValueError:
        stream_socket_cap = 25
    try:
        resp = urllib.request.urlopen(req, timeout=min(max(10, timeout), stream_socket_cap))
    except (OSError, urllib.error.URLError, TimeoutError):
        return None  # clean connect failure -> caller falls back to blocking /chat
    try:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            if obj.get("activity") and not obj.get("done"):
                got_activity = True
                # Empty deltas are progress-only frames: Flutter resets its idle
                # watchdog without rendering text or completing the request.
                _response({"id": request_id, "delta": ""})
                continue
            if "delta" in obj and not obj.get("done"):
                token = str(obj.get("delta") or "")
                if token:
                    pieces.append(token)
                    got_delta = True
                    _response({"id": request_id, "delta": token})
            if obj.get("done"):
                final_receipt = obj.get("receipt") if isinstance(obj.get("receipt"), dict) else {}
                final_reply = str(obj.get("assistant_reply") or "".join(pieces)).strip()
                final_ok = obj.get("ok") is True
    except Exception:
        if not got_delta:
            if got_activity:
                return {
                    "id": request_id,
                    "ok": False,
                    "status": "acknowledged CT246 stream ended before its final reply",
                    "schema": "engel_main_local_model_worker_response_v1",
                    "assistant_reply": "",
                    "assistant_output_text": "",
                    "done": True,
                    "streamed": True,
                    "provider_api_enabled": False,
                    "network_enabled": True,
                    "model_service_server_enabled": True,
                    "duplicate_blocking_retry_suppressed": True,
                }
            return None  # no acknowledgement or token -> safe to try blocking once
    finally:
        try:
            resp.close()
        except Exception:
            pass
    if final_receipt is None and not got_delta:
        if got_activity:
            return {
                "id": request_id,
                "ok": False,
                "status": "acknowledged CT246 stream closed without a final reply",
                "schema": "engel_main_local_model_worker_response_v1",
                "assistant_reply": "",
                "assistant_output_text": "",
                "done": True,
                "streamed": True,
                "provider_api_enabled": False,
                "network_enabled": True,
                "model_service_server_enabled": True,
                "duplicate_blocking_retry_suppressed": True,
            }
        return None
    reply = final_reply or "".join(pieces).strip()
    # (2026-07-07 audit Res-2) A `done` frame with an empty reply or ok:false is a
    # CT failure, not a success — fall back to the blocking/failover lane instead of
    # surfacing an empty/error bubble. Only bail when nothing streamed live; if we
    # already emitted tokens, returning None would let the fallback double-reply.
    # A canonical `done` frame is authoritative even when ok:false. Returning
    # None here would retry the same turn through `/chat`, persist it twice, and
    # hide the quality block behind a static fallback response.
    receipt = dict(final_receipt or {})
    receipt.setdefault("assistant_reply", reply)
    receipt.setdefault("assistant_output_text", reply)
    receipt.setdefault("runtime_provider", "rog-rtx2070-llama-cpp-gpu-stream")
    receipt["long_lived_local_model_worker_used"] = True
    receipt["model_service_transport"] = "stdio_jsonl_stream"
    receipt["main_server_chat_service_used"] = True
    receipt["main_server_chat_url"] = _server_chat_stream_url()
    receipt["worker_request_latency_ms"] = int((time.perf_counter() - started) * 1000)
    return {
        "id": request_id,
        # A safe quality-block message is still a failed turn and must never be
        # promoted merely because it contains visible text.
        "ok": bool(final_ok),
        "status": receipt.get("status", "engel streamed chat reply"),
        "schema": "engel_main_local_model_worker_response_v1",
        "receipt": receipt,
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "done": True,
        "streamed": True,
        "provider_api_enabled": False,
        "network_enabled": True,
        "model_service_server_enabled": True,
    }


def _run_failover_chat(prompt: str, request_id: str, timeout: int, max_tokens: int,
                       chain: "list[str] | None" = None) -> "dict[str, Any] | None":
    """Route a chat turn through the OpenClaw-ported multi-AI failover loop: keep
    working by escalating across every AI Engel has (GPU direct + provider
    bridges) instead of failing on one lane. Verbose failover trace is written to
    STDERR (the Flutter activity feed renders it) when /verbose or /trace is on;
    a /usage footer is appended when enabled. Returns None if the whole chain
    fails, so the caller can fall through to its existing error handling."""
    if not _FAILOVER_AVAILABLE:
        return None
    # Default chain excludes ct246-local when this is the CT-failure fallback;
    # callers that want the full chain pass it explicitly.
    chain = chain or ["rog-gpu", "gemini-api", "grok-cli", "claude-cli", "codex-cli", "chatgpt-browser"]
    show = bool(_VERBOSE_STATE) and (_VERBOSE_STATE.verbose != "off" or _VERBOSE_STATE.trace != "off")

    def on_event(ev: dict) -> None:
        line = _ev.format_failover_event(ev)
        try:
            _VLOG.log("debug", line, evt=ev.get("event"), lane=ev.get("lane", ""))
        except Exception:
            pass
        if show:
            try:
                sys.stderr.write(line + "\n")
                sys.stderr.flush()
            except Exception:
                pass

    try:
        result = _failover.run_with_failover(
            prompt, chain=chain, timeout_s=min(max(15, timeout), 90),
            max_tokens=max_tokens, on_event=on_event,
        )
    except Exception as exc:
        try:
            sys.stderr.write(f"failover loop error: {exc}\n")
        except Exception:
            pass
        return None
    if not result.ok or not result.reply:
        return None
    reply = result.reply
    if _VERBOSE_STATE and _VERBOSE_STATE.usage != "off":
        footer = _ev.format_usage_footer(
            len(prompt.split()), len(reply.split()), level=_VERBOSE_STATE.usage,
            lane=result.provider, latency_ms=result.elapsed_ms,
        )
        if footer:
            reply = f"{reply}\n\n{footer}"
    return {
        "id": request_id,
        "ok": True,
        "status": f"failover reply via {result.provider}",
        "schema": "engel_main_local_model_worker_response_v1",
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "receipt": {
            "ok": True,
            "assistant_reply": reply,
            "provider": result.provider,
            "runtime_provider": result.lane,
            "failover_used": True,
            "failover_iterations": result.iterations,
            "failover_attempts": [a.__dict__ for a in result.attempts],
            "latency_ms": result.elapsed_ms,
            "status": result.status,
        },
        "provider_api_enabled": True,
        "network_enabled": True,
        "model_service_server_enabled": True,
        "failover_used": True,
    }


def _handle(payload: dict[str, Any]) -> dict[str, Any]:
    request_id = _request_id(payload)
    command = str(payload.get("command") or "chat").strip().lower()
    if command == "ping":
        return {
            "id": request_id,
            "ok": True,
            "status": "engel main local model worker ready",
            "schema": "engel_main_local_model_worker_response_v1",
            "long_lived_local_model_service": True,
            "model_service_transport": "stdio_jsonl",
            "model_service_server_enabled": True,
            "provider_api_enabled": False,
            "network_enabled": True,
        }
    if command in {"stop", "shutdown", "exit"}:
        return {
            "id": request_id,
            "ok": True,
            "status": "engel main local model worker stopping",
            "schema": "engel_main_local_model_worker_response_v1",
            "stop": True,
            "provider_api_enabled": False,
            "network_enabled": False,
        }
    if command != "chat":
        return {
            "id": request_id,
            "ok": False,
            "status": f"unknown worker command: {command}",
            "schema": "engel_main_local_model_worker_response_v1",
            "provider_api_enabled": False,
            "network_enabled": False,
        }
    prompt = _clean_text(payload.get("prompt") or "").strip()
    if not prompt:
        return {
            "id": request_id,
            "ok": False,
            "status": "empty prompt",
            "schema": "engel_main_local_model_worker_response_v1",
            "provider_api_enabled": False,
            "network_enabled": False,
        }
    raw_context_items = payload.get("context_items")
    context_items = [
        _clean_json_value(item)
        for item in raw_context_items
        if isinstance(item, dict)
    ] if isinstance(raw_context_items, list) else []
    # OpenClaw-ported verbose directives: /verbose /trace /usage /tools (aliases
    # /v /t). A directive turn just updates session verbosity and acks — no model
    # call — so the operator can toggle the live failover trace mid-conversation.
    if _FAILOVER_AVAILABLE:
        _ack = _ev.apply_directive(_VERBOSE_STATE, prompt)
        if _ack is not None:
            return {
                "id": request_id,
                "ok": True,
                "status": "verbose directive applied",
                "schema": "engel_main_local_model_worker_response_v1",
                "assistant_reply": (
                    f"✓ {_ack}   (verbose={_VERBOSE_STATE.verbose} "
                    f"trace={_VERBOSE_STATE.trace} usage={_VERBOSE_STATE.usage} "
                    f"tools={_VERBOSE_STATE.tools})"
                ),
                "assistant_output_text": f"✓ {_ack}",
                "provider_api_enabled": False,
                "network_enabled": False,
            }
    # Trusted inbox metadata, clamped by the Governor, rides training/automation
    # turns. It is read HERE, above the action lanes, because a turn that declares
    # interactive=false has no operator to answer a confirm gate: a plan handed to
    # one strands the caller until its timeout. (2026-08-03: a training prompt whose
    # material named verify_engel_lan_fingerprint.py was read as "run this", and the
    # run burned 781s on the confirm gate before failing the prompt.)
    inbox_metadata = _clamped_inbox_metadata(payload)
    non_interactive_turn = inbox_metadata.get("interactive") is False
    # (2026-07-07) ACTION LANES — resolved before any model call.
    global _PENDING_ACTION
    # (a) an outstanding execution plan is awaiting the operator's yes/no.
    if _PENDING_ACTION is not None:
        if non_interactive_turn:
            # An automated turn did not author this plan and cannot approve or
            # cancel it. Drop it and answer the turn normally: consuming it would
            # let prompt text that merely looks like "yes"/"no" execute or reply
            # with a confirmation the caller never asked for.
            _PENDING_ACTION = None
        else:
            if _is_confirm(prompt):
                plan = _PENDING_ACTION
                _PENDING_ACTION = None
                return _run_execution_plan(plan, request_id)
            if _is_deny(prompt):
                _PENDING_ACTION = None
                reply = "Okay — cancelled. I didn't run anything."
                return {
                    "id": request_id, "ok": True, "status": "action cancelled",
                    "schema": "engel_main_local_model_worker_response_v1",
                    "assistant_reply": reply, "assistant_output_text": reply,
                    "provider_api_enabled": False, "network_enabled": False,
                }
            _PENDING_ACTION = None  # neither yes nor no -> operator moved on; drop it.
    # (a2) fleet-targeted request ("have alpha …", "send to the Sub-Engel") ->
    # dispatch through the agent meeting room (bounded job + auto-return), NOT local.
    operator_prompt = _operator_request_text(prompt)
    continued_build = _requested_app_build(operator_prompt)
    if continued_build and continued_build != operator_prompt:
        # Keep the UI bubble as Josh typed it; the worker/CT action lane must
        # resume the last app build instead of streaming the retry to Grok.
        prompt = continued_build
        operator_prompt = _operator_request_text(continued_build)
    intent_bridge_reply = _engel_intent_bridge_chat_intercept(
        operator_prompt, request_id
    )
    if intent_bridge_reply is not None:
        return intent_bridge_reply
    speech_spc_reply = _engel_speech_spc_chat_intercept(operator_prompt, request_id)
    if speech_spc_reply is not None:
        return speech_spc_reply
    # Training turns include "you are not a Discord guest" plus ordinary words
    # like "read" and "chat". Those must reach the model. Discord checkout and
    # a Sub-Engel reply are operator actions, not training answers.
    if not non_interactive_turn:
        discord_checkout_reply = _owner_discord_checkout_chat_intercept(
            operator_prompt, request_id
        )
        if discord_checkout_reply is not None:
            return discord_checkout_reply
        sub_engel_reply = _owner_reply_to_sub_engel_chat_intercept(
            operator_prompt, request_id
        )
        if sub_engel_reply is not None:
            return sub_engel_reply
    # One native agent entry point. It selects the smallest proven engine and
    # keeps every handoff under the child system's existing receipt/gate.
    # Non-interactive training must reach CT246 even if the UI prefixed
    # "engel work" because a card mentioned "code" or "fix".
    if not non_interactive_turn:
        kernel_reply = _engel_agent_kernel_chat_intercept(operator_prompt, request_id)
        if kernel_reply is not None:
            return kernel_reply
    # EngelScript in the MAIN chat surface: docs/examples/validate/run answer
    # deterministically and locally (the route library lives on this ROG host,
    # not on CT), and the chat sees RAW text -- the one surface where inline
    # multi-line scripts survive (the route layer's normalization strips
    # quotes/newlines). `draft` asks the local model to EMIT a plan and the
    # validator referees it; drafts are saved, never auto-run.
    script_reply = _engel_script_chat_intercept(operator_prompt, request_id, payload)
    if script_reply is not None:
        return script_reply
    capability_reply = _engel_capability_chat_intercept(operator_prompt, request_id)
    if capability_reply is not None:
        return capability_reply
    # The Conductor owns "engel goal ..." BEFORE the fleet/build detectors: a
    # goal's wording ("engel goal build me a fleet report") must reach the
    # loop, not accidentally trip a raw build/dispatch lane.
    conductor_reply = _engel_conductor_chat_intercept(operator_prompt, request_id)
    if conductor_reply is not None:
        return conductor_reply
    # The Orchestra owns "engel orchestra ..." BEFORE the fleet/build
    # detectors for the same reason: a multi-part goal's wording must reach
    # the parallel lanes, not trip a raw build/dispatch path.
    orchestra_reply = _engel_orchestra_chat_intercept(operator_prompt, request_id)
    if orchestra_reply is not None:
        return orchestra_reply
    # The Forge owns "forge code ..." BEFORE the build detectors: forging is a
    # sandboxed, tested, non-deploying loop and must never become an app-build
    # order just because the task text says "write"/"create".
    forge_reply = _engel_forge_chat_intercept(operator_prompt, request_id)
    if forge_reply is not None:
        return forge_reply
    # Fleet-targeted non-build work goes directly to the Meeting Room. A build
    # naming phones/Sub-Engel must continue into CT246's conical build lane.
    if _requested_app_build(operator_prompt) is None:
        # Use only the operator request, not capability/Training wrappers. The
        # wrappers contain instructional words such as "route" and "proof"
        # that are metadata, not an instruction to dispatch device workers.
        _fleet = _run_fleet_dispatch(operator_prompt, request_id)
        if _fleet is not None:
            return _fleet
    # Build and workspace orders belong to CT246. Do not execute the duplicate ROG
    # implementations here before the server route: the laptop is Engel's UI and
    # controller, not the canonical build host. CT246 owns the workspace, receipt,
    # persistent-memory row, and run proof. The helper functions remain in this
    # module because the CT service imports them, but this ROG worker never invokes
    # them as a pre-server shortcut.
    if _requested_app_build(operator_prompt) is not None:
        build_timeout = max(1, int(payload.get("timeout") or 300))
        build_max_tokens = max(1, int(payload.get("max_tokens") or 420))
        build_temperature = float(payload.get("temperature") or 0.15)
        raw_build_attachments = payload.get("attachments")
        build_attachments = (
            [
                _clean_json_value(item)
                for item in raw_build_attachments
                if isinstance(item, dict)
            ]
            if isinstance(raw_build_attachments, list)
            else []
        )
        # Conical orchestration waits for Sub-Engel and three phone workers
        # before the CT246 build request starts. Keep Flutter's idle watchdog
        # attached across that entire action, not only the later HTTP wait.
        with _request_progress_heartbeat(request_id, enabled=True):
            build_receipt = _main_server_fast_chat(
                prompt=prompt,
                timeout=build_timeout,
                max_tokens=build_max_tokens,
                temperature=build_temperature,
                attachments=build_attachments,
                context_items=context_items,
                progress_request_id="",
            )
        if build_receipt is not None:
            return {
                "id": request_id,
                "ok": build_receipt.get("ok") is True,
                "status": build_receipt.get("status", ""),
                "schema": "engel_main_local_model_worker_response_v1",
                "receipt": build_receipt,
                "provider_api_enabled": False,
                "network_enabled": True,
                "model_service_server_enabled": True,
            }
        return {
            "id": request_id,
            "ok": False,
            "status": "ct246 build route unavailable",
            "schema": "engel_main_local_model_worker_response_v1",
            "assistant_reply": "CT246 did not return a usable build receipt.",
            "assistant_output_text": "CT246 did not return a usable build receipt.",
            "provider_api_enabled": False,
            "network_enabled": True,
            "model_service_server_enabled": True,
        }
    # (c) install / run request -> build a PLAN and ask before running anything.
    # Only an interactive turn can be asked. A declared non-interactive caller
    # (training, automation) gets the normal chat answer instead: it can neither
    # approve the plan nor abandon the turn, so a gate here reads to the caller as
    # a hang, not as a question.
    if not _is_info_question(prompt) and not non_interactive_turn:
        try:
            import engel_command_planner
            # Capability/context wrappers are system metadata, not operator
            # intent. Feeding them to the planner can turn words such as
            # "install" from a language catalog into a false approval gate.
            _plan = engel_command_planner.plan_actions(
                _operator_request_text(prompt)
            )
        except Exception:
            _plan = None
        if _plan is not None:
            if any(bool(step.get("blocked")) for step in _plan.get("steps", [])):
                reply = _plan_blocked_reply(_plan)
                return {
                    "id": request_id, "ok": False, "status": "action blocked",
                    "schema": "engel_main_local_model_worker_response_v1",
                    "assistant_reply": reply, "assistant_output_text": reply,
                    "action": {"kind": "blocked_plan", "plan": _plan},
                    "provider_api_enabled": False, "network_enabled": False,
                }
            _PENDING_ACTION = _plan
            reply = _plan_confirm_reply(_plan)
            return {
                "id": request_id, "ok": True, "status": "action plan awaiting confirm",
                "schema": "engel_main_local_model_worker_response_v1",
                "assistant_reply": reply, "assistant_output_text": reply,
                "action": {"kind": "pending_plan", "plan": _plan},
                "provider_api_enabled": False, "network_enabled": False,
            }
    timeout = max(1, int(payload.get("timeout") or 300))
    max_tokens = max(1, int(payload.get("max_tokens") or 420))
    temperature = float(payload.get("temperature") or 0.15)
    raw_attachments = payload.get("attachments")
    attachments = [
        _clean_json_value(item) for item in raw_attachments if isinstance(item, dict)
    ] if isinstance(raw_attachments, list) else []
    conversation_id = _clean_text(payload.get("conversation_id") or "").strip()[:128]
    started = time.perf_counter()
    # All desktop chat, including an old payload.failover request, stays inside
    # CT246's canonical router. CT246 owns local-first inference, audited bridge
    # escalation, quality gating, and persistent memory; running the worker's
    # independent provider chain would split Engel into an unaudited second chat.
    stream_requested = payload.get("stream") is True or str(payload.get("stream") or "").strip().lower() in {"1", "true", "yes", "on"}
    # CT246's streaming endpoint is for token chat; executable build/workspace
    # actions live on the non-streamed /chat endpoint. Keep normal chat streaming,
    # but send action-shaped prompts through the CT action lane so they produce
    # files, run proof, persistent memory, and a workspace receipt instead of a
    # code-only streamed answer.
    operator_prompt = _operator_request_text(prompt)
    server_action_request = bool(
        _requested_app_build(operator_prompt) is not None
        or _requested_workspace_setup(operator_prompt) is not None
        or _requested_router_work_order(operator_prompt, attachments)
    )
    # Chat-box provider picker choice (dropdown -> force contract) must travel
    # on action requests too. CT246 still applies the build-lane policy gates
    # (local-first defaults, attached-Codex permission, and explicit external
    # provider flags), but dropping the validated choice here made a user's
    # selected provider impossible to honor for build/workspace work.
    ui_provider = _ui_forced_provider(payload)
    ui_model = _ui_requested_model(payload) if ui_provider else ""
    # inbox_metadata was clamped once above the action lanes (the confirm gate
    # depends on it) and rides to CT246 unchanged from here.
    if stream_requested and not server_action_request:
        streamed = _stream_server_chat(
            prompt=prompt,
            request_id=request_id,
            timeout=timeout,
            max_tokens=max_tokens,
            temperature=temperature,
            attachments=attachments,
            context_items=context_items,
            conversation_id=conversation_id,
            ui_provider=ui_provider,
            ui_model=ui_model,
            inbox_metadata=inbox_metadata,
            catalog=payload,
        )
        if streamed is not None:
            # Re-enabled 2026-08-15 after the offline contract proof (10/10 through
            # the runner's real summarize->status->grading->delivery path, fixture
            # prove_belt_receipt.py): payloads now derive the DONE-contract fields
            # the same way the runner's own CT-memory recovery receipt does, and a
            # receipt that would classify FAIL is never persisted at all.
            _persist_local_wrapper_receipt(
                streamed.get("receipt") if isinstance(streamed, dict) else None
            )
            _persist_recall_chat_memory(
                prompt,
                streamed.get("receipt") if isinstance(streamed, dict) else streamed,
            )
            return streamed
    first_fast_receipt = _main_server_fast_chat(
        prompt=prompt,
        timeout=timeout,
        max_tokens=max_tokens,
        temperature=temperature,
        attachments=attachments,
        context_items=context_items,
        conversation_id=conversation_id,
        progress_request_id=request_id,
        ui_provider=ui_provider,
        ui_model=ui_model,
        inbox_metadata=inbox_metadata,
        catalog=payload,
    )
    fast_receipt = (
        None if _unusable_chat_receipt(first_fast_receipt) else first_fast_receipt
    )
    if fast_receipt is None and _router_fallback_allowed():
        transport_error = str(_LAST_FAST_CHAT_TRANSPORT_ERROR or "").casefold()
        connection_miss = any(
            token in transport_error
            for token in (
                "timed out",
                "timeout",
                "urlerror",
                "urlopen",
                "connection",
                "refused",
                "unreachable",
                "winerror",
            )
        )
        selected_model_id = "auto-best"
        if not connection_miss:
            fallback_ids = _fallback_catalog_ids(selected_model_id)
            try:
                from engel_jev_decision import order_fallback_with_jev

                fallback_ids = order_fallback_with_jev(prompt, fallback_ids)
            except Exception:
                pass
            for fallback_id in fallback_ids:
                if fallback_id == selected_model_id:
                    continue
                retry_catalog = dict(payload)
                retry_catalog["selected_model_id"] = fallback_id
                retry_catalog["selected_model_name"] = fallback_id
                retry_catalog["automatic_router_lane"] = True
                retry_receipt = _main_server_fast_chat(
                    prompt=prompt,
                    timeout=min(timeout, 45),
                    max_tokens=max_tokens,
                    temperature=temperature,
                    attachments=attachments,
                    context_items=context_items,
                    conversation_id=conversation_id,
                    progress_request_id=request_id,
                    ui_provider="",
                    ui_model="",
                    inbox_metadata=inbox_metadata,
                    catalog=retry_catalog,
                )
                if not _unusable_chat_receipt(retry_receipt):
                    retry_receipt["router_fallback_model_id"] = fallback_id
                    retry_receipt["router_fallback_from_model_id"] = selected_model_id
                    fast_receipt = retry_receipt
                    break
    if fast_receipt is None and _router_fallback_allowed() and not _local_only_training_active():
        nvidia_receipt = _nvidia_large_model_chat(prompt, context_items, max_tokens)
        if not _unusable_chat_receipt(nvidia_receipt):
            fast_receipt = nvidia_receipt
    if fast_receipt is None and isinstance(first_fast_receipt, dict):
        fast_receipt = first_fast_receipt
    if fast_receipt is not None:
        _persist_local_wrapper_receipt(fast_receipt)
        _persist_recall_chat_memory(prompt, fast_receipt)
        return {
            "id": request_id,
            "ok": fast_receipt.get("ok") is True,
            "status": fast_receipt.get("status", ""),
            "schema": "engel_main_local_model_worker_response_v1",
            "receipt": fast_receipt,
            "provider_api_enabled": False,
            "network_enabled": True,
            "model_service_server_enabled": True,
        }
    if not _router_fallback_allowed():
        return {
            "id": request_id,
            "ok": False,
            "status": "ct246 server chat route unavailable; laptop fallback disabled",
            "schema": "engel_main_local_model_worker_response_v1",
            "assistant_reply": (
                "CT246 did not return a usable chat reply, and laptop fallback is disabled so Engel does not split into a separate local model."
            ),
            "assistant_output_text": (
                "CT246 did not return a usable chat reply, and laptop fallback is disabled so Engel does not split into a separate local model."
            ),
            "provider_api_enabled": False,
            "network_enabled": True,
            "model_service_server_enabled": True,
            "main_server_chat_service_required": True,
            "main_server_chat_url": _server_chat_url(),
        }
    # Keep stdout as JSONL protocol only. Any incidental logs from model/runtime
    # libraries go to stderr and are shown in the Flutter receipt panel.
    # The fallback runs under a hard wall-clock deadline: browser-lane or
    # network-drive stalls inside run_ui_chat must never freeze the desktop
    # chat bubble (2026-07-01: a wedged fallback spun past 250s with no reply).
    fallback_timeout = min(timeout, int(os.environ.get("ENGEL_LOCAL_WORKER_FALLBACK_TIMEOUT", "45") or "45"))
    deadline = float(os.environ.get("ENGEL_LOCAL_WORKER_FALLBACK_DEADLINE", "75") or "75")
    result_box: dict[str, Any] = {}

    def _fallback_worker() -> None:
        try:
            with contextlib.redirect_stdout(sys.stderr):
                from run_engel_ui_chat_meeting_room_llm import run as run_ui_chat  # noqa: E402

                result_box["receipt"] = run_ui_chat(prompt, fallback_timeout, min(max_tokens, 320), temperature)
        except Exception as exc:  # surfaced as an honest failure below
            result_box["error"] = str(exc)
            result_box["traceback_tail"] = traceback.format_exc()[-2000:]

    thread = threading.Thread(target=_fallback_worker, name="engel-local-fallback", daemon=True)
    thread.start()
    thread.join(timeout=max(10.0, deadline))
    if thread.is_alive():
        return {
            "id": request_id,
            "ok": False,
            "status": "engel chat lanes stalled: server lane failed and the local fallback "
            f"exceeded its {int(deadline)}s deadline; no reply was produced",
            "schema": "engel_main_local_model_worker_response_v1",
            "receipt": {
                "ok": False,
                "status": "local fallback lane deadline exceeded",
                "assistant_reply": "",
                "main_server_chat_attempted": True,
                "main_server_chat_used": False,
                "local_fallback_deadline_seconds": deadline,
                "local_fallback_deadline_exceeded": True,
            },
            "provider_api_enabled": False,
            "network_enabled": False,
            "model_service_server_enabled": False,
        }
    if "receipt" not in result_box:
        return {
            "id": request_id,
            "ok": False,
            "status": "engel local fallback lane failed",
            "schema": "engel_main_local_model_worker_response_v1",
            "error": str(result_box.get("error") or "fallback returned no receipt"),
            "traceback_tail": str(result_box.get("traceback_tail") or ""),
            "provider_api_enabled": False,
            "network_enabled": False,
            "model_service_server_enabled": False,
        }
    receipt = result_box["receipt"]
    receipt["long_lived_local_model_worker_used"] = True
    receipt["model_service_transport"] = "stdio_jsonl"
    receipt["model_service_server_enabled"] = False
    receipt["worker_request_latency_ms"] = int((time.perf_counter() - started) * 1000)
    return {
        "id": request_id,
        "ok": receipt.get("ok") is True,
        "status": receipt.get("status", ""),
        "schema": "engel_main_local_model_worker_response_v1",
        "receipt": receipt,
        "provider_api_enabled": False,
        "network_enabled": False,
        "model_service_server_enabled": False,
    }


def main() -> int:
    _response(
        {
            "id": "startup",
            "ok": True,
            "status": "engel main local model worker started",
            "schema": "engel_main_local_model_worker_response_v1",
            "long_lived_local_model_service": True,
            "model_service_transport": "stdio_jsonl",
            "model_service_server_enabled": True,
            "provider_api_enabled": False,
            "network_enabled": True,
        }
    )
    for raw in sys.stdin:
        line = raw.strip().lstrip("\ufeffï»¿")
        if not line:
            continue
        request_id = "unknown"
        try:
            parsed = json.loads(line)
            if not isinstance(parsed, dict):
                raise ValueError("request must be a JSON object")
            request_id = _request_id(parsed)
            response = _handle(parsed)
            # Every human-facing chat turn returns through the same HIPL
            # comprehension bridge. Worker ping/stop protocol messages are not
            # human intent and must never replace the latest operator receipt.
            if str(parsed.get("command") or "chat").strip().lower() == "chat":
                try:
                    import engel_lifted_intent

                    intent_payload = dict(parsed)
                    intent_payload["prompt"] = _operator_request_text(
                        str(parsed.get("prompt") or parsed.get("text") or "")
                    )
                    response = engel_lifted_intent.attach_slm_compiler_lnt(
                        str(intent_payload.get("prompt") or ""),
                        response,
                        caller="engel_main_local_model_worker",
                        request_id=str(parsed.get("id") or parsed.get("request_id") or ""),
                    )
                except Exception as intent_exc:
                    response = dict(response)
                    response["lifted_intent_error"] = (
                        f"{type(intent_exc).__name__}: {str(intent_exc)[:200]}"
                    )
        except Exception as exc:
            response = {
                "id": request_id,
                "ok": False,
                "status": "engel main local model worker error",
                "schema": "engel_main_local_model_worker_response_v1",
                "error": str(exc),
                "traceback_tail": traceback.format_exc()[-2000:],
                "provider_api_enabled": False,
                "network_enabled": False,
                "model_service_server_enabled": False,
            }
        _response(response)
        if response.get("stop"):
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
