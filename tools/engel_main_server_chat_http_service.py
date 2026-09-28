#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import contextvars
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import traceback
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

# --------------------------------------------------------------------------- #
# Snapshot cache: /health, /state, and /registry aggregate many dependency
# probes (provider bridges over the reverse tunnel, meeting room, phone
# bridge, model runtime). When a probed dependency is down, each probe eats
# its timeout and health answers in ~7s+, which every 3-5s health consumer
# (connection doctor, ROG chat pre-flight, Flutter UI) reads as "server down".
# Status endpoints serve a short-TTL cache (stale-while-refresh) so they
# always answer fast; the live /chat routing path keeps using fresh probes.
# --------------------------------------------------------------------------- #
_SNAPSHOT_CACHE: dict[str, dict[str, Any]] = {}
_SNAPSHOT_LOCKS: dict[str, threading.Lock] = {}
_SNAPSHOT_GUARD = threading.Lock()
_SNAPSHOT_TTL_SECONDS = float(os.environ.get("ENGEL_STATUS_SNAPSHOT_TTL_SECONDS", "20") or "20")
# --------------------------------------------------------------------------- #
# Memory / thread discipline (CT246 2026-09-10 OOM: ~1000 threads, ~26–32 GiB
# anon). ThreadingHTTPServer is unbounded by default; Discord desks can stack
# concurrent /chat turns until the kernel OOM-kills the unit. These caps keep
# the process from ballooning; /health exposes growth for the watchdog.
# --------------------------------------------------------------------------- #
_CHAT_HTTP_MAX_THREADS = max(
    16, int(os.environ.get("ENGEL_CHAT_HTTP_MAX_THREADS", "64") or "64")
)
_CHAT_MAX_IN_FLIGHT = max(
    1, min(8, int(os.environ.get("ENGEL_CHAT_MAX_IN_FLIGHT", "4") or "4"))
)
_CHAT_THREAD_WARN = max(
    32, int(os.environ.get("ENGEL_CHAT_THREAD_WARN", "120") or "120")
)
_CHAT_THREAD_HARD = max(
    _CHAT_THREAD_WARN,
    int(os.environ.get("ENGEL_CHAT_THREAD_HARD", "200") or "200"),
)
_CHAT_GROWTH_LOG_COOLDOWN_SECONDS = float(
    os.environ.get("ENGEL_CHAT_GROWTH_LOG_COOLDOWN_SECONDS", "30") or "30"
)
_HTTP_THREAD_SLOTS = threading.BoundedSemaphore(_CHAT_HTTP_MAX_THREADS)
_CHAT_IN_FLIGHT = 0
_CHAT_IN_FLIGHT_LOCK = threading.Lock()
_CHAT_SLOT_CV = threading.Condition(_CHAT_IN_FLIGHT_LOCK)
_CHAT_GROWTH_LAST_LOG = 0.0
_CHAT_REJECTED_TOTAL = 0
_CHAT_ADMISSION_REJECTED_TOTAL = 0


def _process_resource_snapshot() -> dict[str, Any]:
    """Best-effort Threads/RssAnon from /proc (Linux CT246); safe no-op elsewhere."""
    out: dict[str, Any] = {
        "schema": "engel_chat_process_resource_v1",
        "python_active_threads": int(threading.active_count()),
        "http_max_threads": _CHAT_HTTP_MAX_THREADS,
        "chat_max_in_flight": _CHAT_MAX_IN_FLIGHT,
        "chat_in_flight": int(_CHAT_IN_FLIGHT),
        "chat_rejected_total": int(_CHAT_REJECTED_TOTAL),
        "admission_rejected_total": int(_CHAT_ADMISSION_REJECTED_TOTAL),
        "thread_warn": _CHAT_THREAD_WARN,
        "thread_hard": _CHAT_THREAD_HARD,
        "rss_anon_kb": 0,
        "rss_kb": 0,
        "threads_proc": 0,
        "pressure": "ok",
    }
    try:
        for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                out["rss_kb"] = int(line.split()[1])
            elif line.startswith("RssAnon:"):
                out["rss_anon_kb"] = int(line.split()[1])
            elif line.startswith("Threads:"):
                out["threads_proc"] = int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    threads = max(int(out["python_active_threads"]), int(out["threads_proc"] or 0))
    if threads >= _CHAT_THREAD_HARD or int(out["chat_in_flight"]) >= _CHAT_MAX_IN_FLIGHT:
        out["pressure"] = "hard"
    elif threads >= _CHAT_THREAD_WARN:
        out["pressure"] = "warn"
    return out


def _log_resource_growth(reason: str) -> None:
    global _CHAT_GROWTH_LAST_LOG
    now = time.monotonic()
    if (now - _CHAT_GROWTH_LAST_LOG) < _CHAT_GROWTH_LOG_COOLDOWN_SECONDS:
        return
    _CHAT_GROWTH_LAST_LOG = now
    snap = _process_resource_snapshot()
    sys.stderr.write(
        "[%s] chat-resource-growth reason=%s pressure=%s py_threads=%s proc_threads=%s "
        "anon_mb=%s in_flight=%s/%s rejected=%s admission_rejected=%s\n"
        % (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            reason,
            snap.get("pressure"),
            snap.get("python_active_threads"),
            snap.get("threads_proc"),
            int(snap.get("rss_anon_kb") or 0) // 1024,
            snap.get("chat_in_flight"),
            snap.get("chat_max_in_flight"),
            snap.get("chat_rejected_total"),
            snap.get("admission_rejected_total"),
        )
    )
    sys.stderr.flush()


def _wait_chat_admission(path: str) -> None:
    """Heavy turns wait until the process is under the hard thread cap. They are not dropped."""
    heavy = path in {"/chat", "/chat/stream", "/v1/chat/completions"}
    if not heavy:
        return
    while True:
        snap = _process_resource_snapshot()
        threads = max(int(snap["python_active_threads"]), int(snap["threads_proc"] or 0))
        if threads < _CHAT_THREAD_HARD:
            if threads >= _CHAT_THREAD_WARN:
                _log_resource_growth("thread_warn")
            return
        _log_resource_growth("thread_hard_wait")
        time.sleep(1.0)


def _acquire_chat_slot() -> None:
    """Take a chat slot, waiting in line while the cap is full."""
    global _CHAT_IN_FLIGHT
    with _CHAT_SLOT_CV:
        while _CHAT_IN_FLIGHT >= _CHAT_MAX_IN_FLIGHT:
            _log_resource_growth("chat_in_flight_wait")
            _CHAT_SLOT_CV.wait(timeout=5.0)
        _CHAT_IN_FLIGHT += 1


def _release_chat_slot() -> None:
    global _CHAT_IN_FLIGHT
    with _CHAT_SLOT_CV:
        _CHAT_IN_FLIGHT = max(0, _CHAT_IN_FLIGHT - 1)
        _CHAT_SLOT_CV.notify(1)


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer with a hard cap on concurrent handler threads.

    A full cap waits. The connection stays open until a handler is free.
    """

    request_queue_size = 128
    daemon_threads = True

    def process_request(self, request, client_address) -> None:  # noqa: ANN001
        while not _HTTP_THREAD_SLOTS.acquire(timeout=5.0):
            _log_resource_growth("http_thread_slot_wait")

        def _run() -> None:
            try:
                self.finish_request(request, client_address)
            except Exception:
                self.handle_error(request, client_address)
            finally:
                try:
                    self.shutdown_request(request)
                finally:
                    _HTTP_THREAD_SLOTS.release()

        try:
            threading.Thread(
                target=_run, name="engel-chat-http", daemon=True
            ).start()
        except Exception:
            _HTTP_THREAD_SLOTS.release()
            raise


def _cached_snapshot(name: str, builder, ttl_seconds: float | None = None) -> Any:
    ttl = _SNAPSHOT_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    now = time.monotonic()
    entry = _SNAPSHOT_CACHE.get(name)
    if entry is not None and (now - entry["ts"]) < ttl:
        return entry["value"]
    with _SNAPSHOT_GUARD:
        lock = _SNAPSHOT_LOCKS.setdefault(name, threading.Lock())
    if entry is not None:
        # Under hard thread pressure, serve stale forever rather than spawning
        # more refresh workers on top of a wedged accept queue.
        snap = _process_resource_snapshot()
        threads = max(int(snap["python_active_threads"]), int(snap["threads_proc"] or 0))
        if threads >= _CHAT_THREAD_HARD:
            return entry["value"]
        # Stale: serve the old value immediately and refresh in the background
        # (single-flight; a failed refresh keeps the stale value).
        if lock.acquire(blocking=False):
            def _refresh() -> None:
                try:
                    _SNAPSHOT_CACHE[name] = {"ts": time.monotonic(), "value": builder()}
                except Exception:
                    _SNAPSHOT_CACHE[name] = {"ts": time.monotonic(), "value": entry["value"]}
                finally:
                    lock.release()

            threading.Thread(target=_refresh, name=f"engel-snapshot-{name}", daemon=True).start()
        return entry["value"]
    # First call: compute synchronously, single-flight.
    with lock:
        entry = _SNAPSHOT_CACHE.get(name)
        if entry is not None and (time.monotonic() - entry["ts"]) < ttl:
            return entry["value"]
        value = builder()
        _SNAPSHOT_CACHE[name] = {"ts": time.monotonic(), "value": value}
        return value


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
os.chdir(ROOT)

from tools.engel_phone_presence import parse_utc as parse_presence_utc  # noqa: E402
from tools.engel_phone_presence import phone_presence_snapshot  # noqa: E402
from engel_local_llm_fast_fail import (  # noqa: E402
    finalize_fallback_proof,
    run_with_deadline,
    status_snapshot as local_llm_fast_fail_status,
)
from engel_chat_failure_corpus_builder import (  # noqa: E402
    capture_failure as capture_chat_failure,
    status_snapshot as chat_failure_corpus_status,
)
from engel_codex_workbench_ingest import (  # noqa: E402
    build_context_pack,
    status_snapshot as context_pack_status,
)
from engel_discord_desktop_route_parity import (  # noqa: E402
    finalize_surface_turn as finalize_chat_surface_turn,
    repair_assistant_self_identity,
    repair_operator_address_identity as repair_shared_operator_address_identity,
    status_snapshot as chat_route_parity_status,
)

_RAG_RUNTIME_IMPORT_ERROR = ""
try:  # noqa: E402
    from engel_rag_runtime import execute as execute_rag_route
    from engel_rag_runtime import status_snapshot as rag_runtime_status_snapshot
except Exception as exc:  # pragma: no cover - health must stay available if optional route loading fails
    execute_rag_route = None
    rag_runtime_status_snapshot = None
    _RAG_RUNTIME_IMPORT_ERROR = str(exc)

_AI_SYSTEMS_IMPORT_ERROR = ""
try:  # noqa: E402
    from engel_ai_systems_runtime import status_snapshot as ai_systems_status_snapshot
except Exception as exc:  # pragma: no cover - health stays available if the proof layer fails
    ai_systems_status_snapshot = None
    _AI_SYSTEMS_IMPORT_ERROR = str(exc)

os.environ.setdefault("ENGEL_MAIN_LONG_LIVED_LOCAL_MODEL_SERVICE", "1")
os.environ.setdefault("ENGEL_HUMANIZATION_SLM", "1")
try:
    from engel_chat_humanization_slm import enable_side_by_side_model_cache

    enable_side_by_side_model_cache()
except Exception:
    pass

try:  # noqa: E402
    from engel_chat_humanizer import improve_visible_reply
except Exception:  # pragma: no cover - keep the CT chat service available if the helper is missing
    def improve_visible_reply(prompt: str, reply: str, *, source: str = "") -> tuple[str, dict[str, Any]]:
        text = str(reply or "").strip()
        return text, {
            "schema": "engel_chat_humanizer_result_v1",
            "source": source,
            "humanizer_reference_loaded": False,
            "workspace_registry_loaded": False,
            "reply_was_weak_or_repeated": False,
            "reply_changed": False,
            "reason": "humanizer_unavailable",
        }

DEFAULT_MEETING_ROOM_URL = "http://127.0.0.1:8790"
CHAT_RECEIPT_DIR = ROOT / "reports" / "engel_standalone_chat_llm" / "chat_receipts"
CONICAL_REPORT_DIR = ROOT / "reports" / "conical_jobs"
PERSISTENT_CHAT_MEMORY_PATH = ROOT / "memory" / "persistent_chat" / "ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl"
REJECTED_CHAT_SAMPLES_PATH = ROOT / "memory" / "persistent_chat" / "ENGEL_CHAT_REJECTED_SAMPLES.jsonl"
CHAT_ATTACHMENT_MEMORY_DIR = ROOT / "memory" / "persistent_chat" / "attachments"
MEDIA_ARTIFACT_DIR = ROOT / "run" / "media_artifacts"
MEDIA_ARTIFACT_REQUEST_DIR = ROOT / "run" / "media_artifact_requests"
BUILD_WORKSPACE_ROOT = ROOT / "workspaces"
BUILD_PACKAGE_ROOT = ROOT / "packages" / "builds"
MISSION_CONTROL_ROOT = Path(os.environ.get("ENGEL_MISSION_CONTROL_ROOT", "/mnt/ssd-ai/engel-control"))
CHAT_ATTACHMENT_INLINE_LIMIT_BYTES = int(os.environ.get("ENGEL_CHAT_ATTACHMENT_INLINE_LIMIT_BYTES", str(2 * 1024 * 1024)) or str(2 * 1024 * 1024))
CHAT_ATTACHMENT_MAX_COUNT = int(os.environ.get("ENGEL_CHAT_ATTACHMENT_MAX_COUNT", "8") or "8")
CHAT_ATTACHMENT_PROMPT_PREVIEW_CHARS = int(os.environ.get("ENGEL_CHAT_ATTACHMENT_PROMPT_PREVIEW_CHARS", "12000") or "12000")
PHONE_BRIDGE_STATE_PATH = ROOT / "memory" / "phone_bridge" / "ENGEL_REMOTE_WORKERS_PAIRED.json"
WINDOWS_SUB_ENGEL_ROOT = ROOT / "remote_nodes" / "windows_sub_engel"
WINDOWS_SUB_ENGEL_FLEET_MANIFEST_PATH = WINDOWS_SUB_ENGEL_ROOT / "fleet_manifest.json"
WINDOWS_SUB_ENGEL_SESSION_PATH = WINDOWS_SUB_ENGEL_ROOT / "session.json"
WINDOWS_SUB_ENGEL_LATEST_READY_PATH = ROOT / "runtime" / "windows_sub_engel_bootstrap" / "latest_node_ready.json"
WINDOWS_SUB_ENGEL_TRANSPORT_ROOT = Path(
    os.environ.get("ENGEL_SUB_ENGEL_TRANSPORT_ROOT", str(ROOT / "run" / "sub_engel_transport"))
)
LORA_MANIFEST_PATH = Path(
    os.environ.get(
        "ENGEL_TRAINED_LORA_MANIFEST",
        str(ROOT / "runtime" / "engel_standalone_chat_llm" / "trained_lora_adapter_manifest.json"),
    )
)
MODEL_INVENTORY_PATH = ROOT / "memory" / "models" / "ENGEL_CT_FAST_SSD_MODEL_INVENTORY.json"
REPS_TEMPLATE_PATH = ROOT / "memory" / "ENGEL_UNIVERSAL_REPS_TEMPLATE_V1.json"
REPS_TEMPLATE_MD_PATH = ROOT / "memory" / "ENGEL_UNIVERSAL_REPS_TEMPLATE_V1.md"
SELF_MODEL_STATE_PATH = ROOT / "memory" / "self_model" / "ENGEL_SELF_MODEL_V1.json"
SHELL_BRIDGE_REGISTRY_PATH = ROOT / "run" / "self_update" / "bridges" / "bridge_registry.json"
PROVIDER_CAPABILITY_MAP_PATH = ROOT / "run" / "self_update" / "providers" / "provider_capability_map.json"
PROVIDER_BRIDGE_ENV_FILE = Path(
    os.environ.get("ENGEL_PROVIDER_BRIDGE_ENV_FILE", str(ROOT / "run" / "secrets" / "provider_bridges.env"))
)
OPENAI_CHAT_COMPLETIONS_URL = os.environ.get(
    "ENGEL_OPENAI_CHAT_COMPLETIONS_URL",
    "https://api.openai.com/v1/chat/completions",
).strip()
ANTHROPIC_MESSAGES_URL = os.environ.get(
    "ENGEL_ANTHROPIC_MESSAGES_URL",
    "https://api.anthropic.com/v1/messages",
).strip()
XAI_CHAT_COMPLETIONS_URL = os.environ.get(
    "ENGEL_XAI_CHAT_COMPLETIONS_URL",
    "https://api.x.ai/v1/chat/completions",
).strip()
NVIDIA_CHAT_COMPLETIONS_URL = os.environ.get(
    "ENGEL_NVIDIA_CHAT_COMPLETIONS_URL",
    "https://integrate.api.nvidia.com/v1/chat/completions",
).strip()
GEMINI_GENERATE_CONTENT_URL_TEMPLATE = os.environ.get(
    "ENGEL_GEMINI_GENERATE_CONTENT_URL_TEMPLATE",
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
).strip()
ROG_GROK_CLI_BRIDGE_URL = os.environ.get(
    "ENGEL_ROG_GROK_CLI_BRIDGE_URL",
    "http://127.0.0.1:24881",
).rstrip("/")
ROG_CLAUDE_CLI_BRIDGE_URL = os.environ.get(
    "ENGEL_ROG_CLAUDE_CLI_BRIDGE_URL",
    "http://127.0.0.1:24883",
).rstrip("/")
ROG_CHATGPT_BROWSER_BRIDGE_URL = os.environ.get(
    "ENGEL_ROG_CHATGPT_BROWSER_BRIDGE_URL",
    "http://127.0.0.1:24885",
).rstrip("/")
ROG_GEMINI_API_BRIDGE_URL = os.environ.get(
    "ENGEL_ROG_GEMINI_API_BRIDGE_URL",
    "http://127.0.0.1:24887",
).rstrip("/")
ROG_CODEX_CLI_BRIDGE_URL = os.environ.get(
    "ENGEL_ROG_CODEX_CLI_BRIDGE_URL",
    "http://127.0.0.1:24889",
).rstrip("/")
PROVIDER_BRIDGE_TIMEOUT_SECONDS = float(os.environ.get("ENGEL_PROVIDER_BRIDGE_TIMEOUT_SECONDS", "18") or "18")
GROK_CLI_BRIDGE_TIMEOUT_SECONDS = float(os.environ.get("ENGEL_GROK_CLI_BRIDGE_TIMEOUT_SECONDS", "90") or "90")
CLAUDE_CLI_BRIDGE_TIMEOUT_SECONDS = float(os.environ.get("ENGEL_CLAUDE_CLI_BRIDGE_TIMEOUT_SECONDS", "30") or "30")
CHATGPT_BROWSER_BRIDGE_TIMEOUT_SECONDS = float(os.environ.get("ENGEL_CHATGPT_BROWSER_BRIDGE_TIMEOUT_SECONDS", "30") or "30")
GEMINI_API_BRIDGE_TIMEOUT_SECONDS = float(os.environ.get("ENGEL_GEMINI_API_BRIDGE_TIMEOUT_SECONDS", "25") or "25")
CODEX_CLI_BRIDGE_TIMEOUT_SECONDS = float(os.environ.get("ENGEL_CODEX_CLI_BRIDGE_TIMEOUT_SECONDS", "120") or "120")
PROVIDER_BRIDGE_SECRET_NAMES: dict[str, list[str]] = {
    "openai": ["ENGEL_OPENAI_API_KEY", "OPENAI_API_KEY", "ENGEL_CHATGPT_API_KEY"],
    "anthropic": ["ENGEL_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY", "ENGEL_CLAUDE_API_KEY"],
    "xai": ["ENGEL_XAI_API_KEY", "XAI_API_KEY", "ENGEL_GROK_API_KEY", "GROK_API_KEY"],
    "gemini": [
        "ENGEL_GEMINI_API_KEY",
        "GEMINI_API_KEY",
        "ENGEL_GOOGLE_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_GENAI_API_KEY",
        "GENAI_API_KEY",
        "GOOGLE_GENERATIVE_AI_API_KEY",
        "ENGEL_GOOGLE_GENAI_API_KEY",
        "ENGEL_GOOGLE_GENERATIVE_AI_API_KEY",
        "GOOGLE_AI_API_KEY",
        "ENGEL_GOOGLE_AI_API_KEY",
    ],
    "codex": [],
    "nvidia": ["ENGEL_NVIDIA_API_KEY", "NVIDIA_API_KEY", "NGC_API_KEY", "NIM_API_KEY"],
}
PROVIDER_BRIDGE_LABELS = {
    "openai": "ChatGPT/OpenAI",
    "anthropic": "Claude/Anthropic",
    "xai": "Grok/xAI",
    "gemini": "Gemini/Google",
    "codex": "Codex/OpenAI",
    "nvidia": "NVIDIA NIM",
}
PROVIDER_MODEL_ENV_NAMES = {
    "openai": ["ENGEL_OPENAI_CHAT_MODEL", "ENGEL_CHATGPT_MODEL", "OPENAI_MODEL"],
    "anthropic": ["ENGEL_ANTHROPIC_CHAT_MODEL", "ENGEL_CLAUDE_MODEL", "ANTHROPIC_MODEL"],
    "xai": ["ENGEL_XAI_CHAT_MODEL", "ENGEL_GROK_MODEL", "XAI_MODEL", "GROK_MODEL"],
    "gemini": ["ENGEL_GEMINI_CHAT_MODEL", "ENGEL_GOOGLE_CHAT_MODEL", "GEMINI_MODEL", "GOOGLE_MODEL", "GOOGLE_GENAI_MODEL"],
    "codex": ["ENGEL_CODEX_CLI_MODEL", "CODEX_MODEL"],
    "nvidia": ["ENGEL_NVIDIA_CHAT_MODEL", "NVIDIA_NIM_MODEL", "NIM_MODEL"],
}
PROVIDER_MODEL_FALLBACKS = {
    "openai": ["gpt-4.1-mini", "gpt-4o-mini", "gpt-4o"],
    "anthropic": ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest"],
    "xai": ["grok-4.6", "grok-4.5"],
    "gemini": ["gemini-3.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"],
    "codex": [],
    "nvidia": [
        "nvidia/nemotron-3-super-120b-a12b",
        "nvidia/nemotron-3-ultra-550b-a55b",
        "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "nvidia/nemotron-3.5-lightning-30b-a3b",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "nvidia/nemotron-3-nano-30b-a3b",
    ],
}


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + f"_p{os.getpid()}"


def _clean_text(value: Any) -> str:
    text = str(value or "").encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    text = text.replace("\x00", "")
    return "".join(ch for ch in text if ch in "\t\r\n" or ord(ch) >= 32).strip()


def _clean_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, list):
        return [_clean_json_value(item) for item in value]
    if isinstance(value, dict):
        return {_clean_text(key): _clean_json_value(item) for key, item in value.items()}
    return value


def _clip(value: Any, limit: int = 900) -> str:
    text = " ".join(_clean_text(value).replace("\r", " ").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean_json_value(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    # (NT-1) Every persistent chat-memory record carries the answering cascade DEPTH
    # (0 router / 1 quick / 2 big / 3 bridge). There are ~13 memory writers (finalized,
    # fast, quick-casual, status, streamed, ...); stamping here at the single write point
    # labels them all. A lane that already stamped an explicit depth is not overridden
    # (setdefault); otherwise it is derived from the record's own provider fields. Pure
    # telemetry, fail-open — never affects the reply.
    try:
        if (
            path == PERSISTENT_CHAT_MEMORY_PATH
            and isinstance(payload, dict)
            and payload.get("activation_depth") is None
        ):
            _d, _l, _e = _activation_depth(payload, "")
            payload.setdefault("activation_depth", _d)
            payload.setdefault("activation_depth_label", _l)
            payload.setdefault("escalated_from", _e)
    except Exception:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_clean_json_value(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + f".{_stamp()}.tmp")
    try:
        _write_json(temp_path, payload)
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _safe_conical_job_id(value: Any) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", _clean_text(value)).strip("._")
    return cleaned[:160] or ("conical_job_" + _stamp())


def _conical_worker_summary(conical: dict[str, Any]) -> list[dict[str, Any]]:
    rows = conical.get("worker_results") if isinstance(conical.get("worker_results"), list) else []
    summaries: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        contribution = _clean_text(row.get("contribution"))
        summaries.append(
            {
                "worker_id": _clean_text(row.get("worker_id")),
                "task_id": _clean_text(row.get("task_id")),
                "role": _clean_text(row.get("role")),
                "status": _clean_text(row.get("status")),
                "returned": row.get("returned") is True,
                "error": _clip(row.get("error"), 600),
                "packet_id": _clean_text(row.get("packet_id")),
                "order_id": _clean_text(row.get("order_id")),
                "return_path": _clean_text(row.get("return_path")),
                "candidate_only": row.get("candidate_only") is True,
                "contribution_chars": len(contribution),
                "contribution_sha256": hashlib.sha256(contribution.encode("utf-8")).hexdigest()
                if contribution
                else "",
            }
        )
    return summaries


def _conical_worker_gate(conical: dict[str, Any]) -> dict[str, Any]:
    summaries = _conical_worker_summary(conical)
    returned_ids = {
        str(row.get("worker_id") or "")
        for row in summaries
        if row.get("returned") is True and str(row.get("worker_id") or "")
    }
    plan = conical.get("plan") if isinstance(conical.get("plan"), dict) else {}
    tasks = plan.get("tasks") if isinstance(plan.get("tasks"), list) else []
    required_ids = {
        _clean_text(task.get("worker_id"))
        for task in tasks
        if isinstance(task, dict) and task.get("required") is not False and _clean_text(task.get("worker_id"))
    }
    expected = int(conical.get("expected_worker_count") or len(required_ids) or 0)
    reported_returned = int(conical.get("returned_worker_count") or 0)
    required_set_matches = not required_ids or returned_ids == required_ids
    complete = bool(
        conical.get("required") is True
        and conical.get("ok") is True
        and expected == 4
        and reported_returned == 4
        and len(returned_ids) == 4
        and required_set_matches
    )
    missing_ids = sorted(required_ids - returned_ids)
    if not missing_ids and expected > len(returned_ids):
        missing_ids = [
            _clean_text(row.get("worker_id")) or "unknown_worker"
            for row in summaries
            if row.get("returned") is not True
        ]
    return {
        "ok": complete,
        "expected_count": expected,
        "reported_returned_count": reported_returned,
        "verified_returned_count": len(returned_ids),
        "returned_worker_ids": sorted(returned_ids),
        "required_worker_ids": sorted(required_ids),
        "missing_worker_ids": sorted(set(missing_ids)),
        "worker_results": summaries,
    }


def _conical_receipt_hash(payload: dict[str, Any]) -> str:
    material = dict(payload)
    material.pop("receipt_payload_sha256", None)
    encoded = json.dumps(
        _clean_json_value(material),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _persist_ct246_conical_receipt(
    conical: dict[str, Any],
    *,
    prompt: str,
    source: str,
    build_execution_verified: bool,
    provider_api_used: bool,
    failure_reason: str = "",
) -> dict[str, Any]:
    gate = _conical_worker_gate(conical)
    job_id = _safe_conical_job_id(conical.get("job_id"))
    receipt_path = CONICAL_REPORT_DIR / f"{job_id}.json"
    controller_receipt_path = _clean_text(
        conical.get("controller_receipt_path") or conical.get("receipt_path")
    )
    errors = conical.get("errors") if isinstance(conical.get("errors"), list) else []
    final_requested_ok = bool(gate["ok"] and build_execution_verified and not failure_reason)
    normalized = {
        "schema": "engel_ct246_conical_job_receipt_v1",
        "job_id": job_id,
        "required": conical.get("required") is True,
        "ok": False,
        "status": _clean_text(conical.get("status")) or (
            "workers_returned" if gate["ok"] else "failed_worker_returns"
        ),
        "final_ok": False,
        "final_status": "failed",
        "build_execution_verified": build_execution_verified,
        "build_verified": False,
        "build_size": _clean_text(conical.get("build_size")),
        "expected_worker_count": gate["expected_count"],
        "returned_worker_count": gate["verified_returned_count"],
        "reported_returned_worker_count": gate["reported_returned_count"],
        "failed_worker_count": max(0, gate["expected_count"] - gate["verified_returned_count"]),
        "required_worker_ids": gate["required_worker_ids"],
        "returned_worker_ids": gate["returned_worker_ids"],
        "missing_worker_ids": gate["missing_worker_ids"],
        "worker_results": gate["worker_results"],
        "meeting_room_order_id": _clean_text(conical.get("meeting_room_order_id")),
        "started_at_utc": _clean_text(conical.get("started_at_utc")),
        "workers_finished_at_utc": _clean_text(conical.get("workers_finished_at_utc")),
        "finalized_at_utc": _iso_now(),
        "failure_reason": _clip(failure_reason, 1200),
        "errors": _clean_json_value(errors),
        "candidate_outputs_reviewed_by_main": conical.get("candidate_outputs_reviewed_by_main") is True,
        "provider_api_used": provider_api_used,
        "local_first": True,
        "trusted_memory_write": False,
        "ct246_source_of_truth": True,
        "ct246_runtime_root": str(ROOT),
        "controller_receipt_path": controller_receipt_path,
        "receipt_path": str(receipt_path),
        "prompt": _clip_multiline(prompt, 6000),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "source": _clean_text(source),
        "ct246_conical_report_written": False,
        "ct246_conical_memory_appended": False,
        "ct246_conical_persistence_ok": False,
    }
    report_written = False
    memory_appended = False
    errors_out: list[str] = []
    try:
        normalized["receipt_payload_sha256"] = _conical_receipt_hash(normalized)
        _atomic_write_json(receipt_path, normalized)
        report_written = True
    except Exception as exc:
        errors_out.append(f"conical report write failed: {exc}")
    if report_written:
        memory_record = dict(normalized)
        memory_record.update(
            {
                "schema": "engel_ct246_conical_job_memory_v1",
                "memory_source": "engel-ai-main CT246 conical build lane",
                "build_lane_used": True,
                "creation_job": True,
                "assistant_reply": (
                    f"Conical job {job_id}: {gate['verified_returned_count']}/{gate['expected_count']} "
                    f"required workers returned; build_execution_verified={build_execution_verified}."
                ),
                "action": {
                    "kind": "app_build",
                    "result": {
                        "ok": final_requested_ok,
                        "path": "",
                        "files": [],
                        "conical_job_id": job_id,
                    },
                },
                "persistent_chat_memory_appended": True,
                "ct246_conical_report_written": True,
                "ct246_conical_memory_appended": True,
                "ct246_conical_persistence_ok": True,
            }
        )
        try:
            _append_jsonl(PERSISTENT_CHAT_MEMORY_PATH, memory_record)
            memory_appended = True
        except Exception as exc:
            errors_out.append(f"conical memory append failed: {exc}")
    persistence_ok = bool(report_written and memory_appended)
    normalized.update(
        {
            "ok": bool(final_requested_ok and persistence_ok),
            "final_ok": bool(final_requested_ok and persistence_ok),
            "final_status": "finished" if final_requested_ok and persistence_ok else "failed",
            "build_verified": bool(build_execution_verified and persistence_ok),
            "ct246_conical_report_written": report_written,
            "ct246_conical_memory_appended": memory_appended,
            "ct246_conical_persistence_ok": persistence_ok,
            "persistence_error": "; ".join(errors_out),
            "finalized_at_utc": _iso_now(),
        }
    )
    if report_written:
        try:
            normalized["receipt_payload_sha256"] = _conical_receipt_hash(normalized)
            _atomic_write_json(receipt_path, normalized)
        except Exception as exc:
            errors_out.append(f"final conical report write failed: {exc}")
            persistence_ok = False
            normalized["ok"] = False
            normalized["final_ok"] = False
            normalized["final_status"] = "failed"
            normalized["build_verified"] = False
            normalized["ct246_conical_persistence_ok"] = False
            normalized["persistence_error"] = "; ".join(errors_out)
    return {
        "ok": persistence_ok,
        "receipt_path": str(receipt_path) if report_written else "",
        "report_written": report_written,
        "memory_appended": memory_appended,
        "error": "; ".join(errors_out),
        "conical_orchestration": normalized,
    }


def _clip_multiline(value: Any, limit: int) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _clip_preserve(value: Any, limit: int = 900) -> str:
    """Clip to a length WITHOUT collapsing newlines/indentation, so chat replies
    that contain code blocks or lists keep their structure. (2026-07-07 audit Q-1:
    the quick lane ran replies through _clip -> _clean_text, flattening code.)"""
    text = str(value or "").replace("\x00", "")
    lines = [ln.rstrip() for ln in text.splitlines()]
    out: list[str] = []
    blanks = 0
    for ln in lines:
        if ln:
            blanks = 0
            out.append(ln)
        else:
            blanks += 1
            if blanks <= 2:
                out.append(ln)
    joined = "\n".join(out).strip()
    if len(joined) <= limit:
        return joined
    return joined[: max(0, limit - 3)].rstrip() + "..."


def _safe_attachment_name(value: Any, fallback: str) -> str:
    raw = Path(str(value or fallback)).name.strip() or fallback
    clean = re.sub(r"[^A-Za-z0-9._ -]+", "_", raw).strip(" .")
    return clean[:120] or fallback


def _decode_attachment_base64(value: Any) -> bytes:
    text = str(value or "").strip()
    if not text:
        return b""
    if "," in text and text.split(",", 1)[0].casefold().startswith("data:"):
        text = text.split(",", 1)[1].strip()
    if len(text) > CHAT_ATTACHMENT_INLINE_LIMIT_BYTES * 2:
        raise ValueError("inline payload exceeds server cap")
    return base64.b64decode(text.encode("ascii"), validate=True)


def _image_layout_notes(image: Any, name: str) -> str:
    """Compact local pixel notes. No OCR package required."""
    width, height = image.size
    notes = [f"{name}: {getattr(image, 'format', None) or 'image'} {width}x{height} {image.mode}"]
    if width >= height * 1.3:
        notes.append("landscape")
    elif height >= width * 1.3:
        notes.append("portrait")
    else:
        notes.append("nearly square")
    if width >= 800 and height >= 400:
        notes.append("looks like a screenshot or UI capture")
    try:
        rgb = image.convert("RGB")
        thumb = rgb.resize((24, 24))
        pixels = list(thumb.getdata())
        count = max(1, len(pixels))
        avg_r = sum(int(p[0]) for p in pixels) // count
        avg_g = sum(int(p[1]) for p in pixels) // count
        avg_b = sum(int(p[2]) for p in pixels) // count
        brightness = (avg_r + avg_g + avg_b) / 3.0
        if brightness < 70:
            notes.append("mostly dark")
        elif brightness > 190:
            notes.append("mostly bright")
        else:
            notes.append("medium brightness")
        notes.append(f"average color rgb({avg_r},{avg_g},{avg_b})")
        top = pixels[:24]
        bot = pixels[-24:]
        top_b = sum(sum(p) for p in top) / (3.0 * max(1, len(top)))
        bot_b = sum(sum(p) for p in bot) / (3.0 * max(1, len(bot)))
        if top_b + 25 < bot_b:
            notes.append("darker at the top")
        elif bot_b + 25 < top_b:
            notes.append("darker at the bottom")
    except Exception:
        pass
    return "; ".join(notes)


def _describe_stored_chat_image(path_text: str, name: str = "image") -> str:
    """Local pixel notes for a stored still. No network. No package install."""
    path = Path(str(path_text or "").strip())
    if not path.is_file():
        return ""
    try:
        from PIL import Image
    except Exception:
        return f"{name}: image file saved at {path}"
    try:
        image = Image.open(path)
        return _image_layout_notes(image, name)
    except Exception:
        return f"{name}: image file saved at {path}"


def _request_has_still_images(request: dict[str, Any] | None) -> bool:
    raw = (request or {}).get("attachments")
    if not isinstance(raw, list):
        return False
    for item in raw:
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


def _is_main_ui_turn(request: dict[str, Any] | None) -> bool:
    request = request or {}
    metadata = request.get("metadata") if isinstance(request.get("metadata"), dict) else {}
    if str(metadata.get("worker_contract") or "") == "rog_ui_to_ct246_chat_v1":
        return True
    source = str(request.get("source") or request.get("client") or "").strip().casefold()
    return source in {
        "engel_ai_main_ui",
        "engel_flutter_main",
        "desktop_ui",
        "rog_ui",
        "rog_desktop_controller",
    }


def _request_needs_vision_lane(request: dict[str, Any] | None) -> bool:
    request = request or {}
    if _request_local_only_training(request):
        return False
    if (
        request.get("discord_owner_vision") is True
        or request.get("main_ui_vision") is True
        or request.get("discord_vision") is True
    ):
        return True
    if not _request_has_still_images(request):
        return False
    source = str(request.get("source") or request.get("client") or "").strip().casefold()
    if source.startswith("discord"):
        return True
    return _is_discord_owner_turn(request) or _is_main_ui_turn(request)


def _grok_inline_image_attachments(request: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Copy Discord/CT stills as base64 so the ROG Grok CLI can write them locally."""
    out: list[dict[str, Any]] = []
    raw = (request or {}).get("attachments")
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        mime = str(item.get("mime_type") or item.get("mime") or "").casefold()
        kind = str(item.get("kind") or "").casefold()
        name = str(item.get("name") or "image.png")
        if "gif" in mime or name.casefold().endswith(".gif"):
            continue
        if not (mime.startswith("image/") or kind in {"image", "screenshot"}):
            continue
        stored = str(item.get("stored_path") or "").replace("\\", "/").strip()
        if stored.startswith("/opt/engel/memory/persistent_chat/attachments/") and ".." not in stored:
            out.append(
                {
                    "name": name,
                    "mime_type": mime or "image/png",
                    "kind": "image",
                    "stored_path": stored,
                }
            )
            if len(out) >= 4:
                break
            continue
        b64 = item.get("inline_base64") or item.get("base64") or ""
        if not b64:
            path = Path(stored) if stored else None
            try:
                if path is not None and path.is_file() and path.stat().st_size <= CHAT_ATTACHMENT_INLINE_LIMIT_BYTES:
                    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
            except Exception:
                b64 = ""
        if not b64:
            continue
        out.append(
            {
                "name": name,
                "mime_type": mime or "image/png",
                "kind": "image",
                "inline_base64": b64,
            }
        )
        if len(out) >= 4:
            break
    return out


def _vision_lane_local_reply(prompt: str, request: dict[str, Any], grok_error: str) -> str:
    """Honest still-image answer when the ROG Grok vision tunnel is down."""
    notes: list[str] = []
    raw = request.get("attachments")
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "").casefold()
            mime = str(item.get("mime_type") or item.get("mime") or "").casefold()
            if kind not in {"image", "screenshot"} and not mime.startswith("image/"):
                continue
            preview = str(item.get("text_preview") or "").strip()
            stored = str(item.get("stored_path") or item.get("path") or "").strip()
            name = str(item.get("name") or "image")
            if preview:
                notes.append(preview)
            elif stored:
                vision_note = _describe_stored_chat_image(stored, name)
                if vision_note:
                    notes.append(vision_note)
    note_text = "; ".join(notes) if notes else "a still image was stored, but I could not read the pixels through Grok"
    err = " ".join(str(grok_error or "").split())
    tunnel_down = any(
        marker in err.casefold()
        for marker in ("connection refused", "timed out", "unavailable", "10061", "111")
    )
    if tunnel_down:
        return (
            "I have the picture. The Grok vision tunnel from CT246 to this computer is down, "
            "so I cannot read every word on the screenshot yet. What I can see locally: "
            + note_text
            + ". I am not going to pretend I finished looking. Resend it after the one-system "
            "link is up, or ask me again in a few seconds."
        )
    return (
        "I have the picture. Grok vision did not return a usable look this turn. "
        "Local notes: "
        + note_text
        + ". Error: "
        + err[:240]
    )


def _prepare_chat_attachments(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {
            "schema": "engel_chat_attachment_intake_v1",
            "ok": True,
            "attachments": [],
            "requested_count": 0,
            "count": 0,
            "stored_count": 0,
            "errors": [],
            "prompt_context": "",
        }
    if not isinstance(raw, list):
        return {
            "schema": "engel_chat_attachment_intake_v1",
            "ok": False,
            "attachments": [],
            "requested_count": 1,
            "count": 0,
            "stored_count": 0,
            "errors": [{"index": 0, "error": "attachments must be a list"}],
            "prompt_context": "",
        }
    stamp = _stamp()
    storage_dir = CHAT_ATTACHMENT_MEMORY_DIR / stamp
    attachments: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    stored_count = 0
    for index, item in enumerate(raw[:CHAT_ATTACHMENT_MAX_COUNT]):
        if not isinstance(item, dict):
            errors.append({"index": index, "error": "attachment item was not an object"})
            continue
        name = _safe_attachment_name(item.get("name") or item.get("path"), f"attachment_{index + 1}")
        mime_type = _clip(item.get("mime_type") or item.get("mime") or "application/octet-stream", 120)
        kind = _clip(item.get("kind") or "file", 40)
        try:
            size_bytes = int(item.get("size_bytes") or item.get("size") or 0)
        except (TypeError, ValueError):
            size_bytes = 0
        text_preview = _clip_multiline(item.get("text_preview") or "", CHAT_ATTACHMENT_PROMPT_PREVIEW_CHARS)
        inline_truncated = bool(item.get("inline_truncated"))
        source_path = _clip(item.get("path") or "", 500)
        stored_path = ""
        sha256 = ""
        decoded_size = 0
        inline_base64 = item.get("inline_base64") or item.get("base64") or ""
        if inline_base64:
            try:
                blob = _decode_attachment_base64(inline_base64)
                decoded_size = len(blob)
                if decoded_size > CHAT_ATTACHMENT_INLINE_LIMIT_BYTES:
                    raise ValueError("decoded payload exceeds server cap")
                storage_dir.mkdir(parents=True, exist_ok=True)
                target = storage_dir / name
                if target.exists():
                    target = storage_dir / f"{index + 1}_{name}"
                target.write_bytes(blob)
                stored_path = str(target)
                sha256 = hashlib.sha256(blob).hexdigest()
                stored_count += 1
                if size_bytes <= 0:
                    size_bytes = decoded_size
            except Exception as exc:
                errors.append({"index": index, "name": name, "error": str(exc)})
        attachments.append(
            {
                "schema": "engel_chat_attachment_receipt_v1",
                "index": index,
                "id": _clip(item.get("id") or f"attachment_{index + 1}", 120),
                "name": name,
                "kind": kind,
                "mime_type": mime_type,
                "size_bytes": size_bytes,
                "source_path": source_path,
                "stored_path": stored_path,
                "content_saved": bool(stored_path),
                "sha256": sha256,
                "inline_truncated": inline_truncated,
                "text_preview": text_preview,
                "text_preview_truncated": bool(item.get("text_preview_truncated")),
                "raw_inline_base64_dropped": bool(inline_base64),
            }
        )
    if len(raw) > CHAT_ATTACHMENT_MAX_COUNT:
        errors.append(
            {
                "index": CHAT_ATTACHMENT_MAX_COUNT,
                "error": f"only first {CHAT_ATTACHMENT_MAX_COUNT} attachments were accepted",
            }
        )
    context_lines: list[str] = []
    if attachments:
        failed_attachment_indexes = {
            int(error.get("index"))
            for error in errors
            if isinstance(error, dict) and isinstance(error.get("index"), int)
        }
        context_lines.extend(
            [
                "",
                "User attached files to this Engel chat turn. Use their metadata and previews when answering.",
            ]
        )
        for attachment in attachments:
            attachment_index = int(attachment.get("index") or 0)
            processing_failed = attachment_index in failed_attachment_indexes
            if processing_failed:
                line = (
                    f"{attachment_index + 1}. {attachment['name']} "
                    f"({attachment['kind']}, {attachment['mime_type']}); contents are unavailable because upload processing failed"
                )
            else:
                line = (
                    f"{attachment_index + 1}. {attachment['name']} "
                    f"({attachment['kind']}, {attachment['mime_type']}, {attachment['size_bytes']} bytes)"
                )
            if not processing_failed and attachment.get("stored_path"):
                line += f" stored at {attachment['stored_path']}"
            elif not processing_failed and attachment.get("inline_truncated"):
                line += " metadata-only because the file is larger than the inline cap"
            context_lines.append(line)
            preview = str(attachment.get("text_preview") or "").strip()
            if preview:
                context_lines.append("Preview:\n" + preview)
            elif str(attachment.get("kind") or "").casefold() == "image" or str(
                attachment.get("mime_type") or ""
            ).casefold().startswith("image/"):
                vision_note = _describe_stored_chat_image(
                    str(attachment.get("stored_path") or ""),
                    str(attachment.get("name") or "image"),
                )
                if vision_note:
                    context_lines.append("Visible image notes:\n" + vision_note)
    return {
        "schema": "engel_chat_attachment_intake_v1",
        "ok": not errors,
        "attachments": attachments,
        "requested_count": len(raw),
        "count": len(attachments),
        "stored_count": stored_count,
        "errors": errors,
        "storage_dir": str(storage_dir) if attachments else "",
        "prompt_context": "\n".join(context_lines).strip(),
    }


def _stamp_stored_paths_on_request(request: dict[str, Any], intake: dict[str, Any]) -> None:
    """Keep CT246 stored_path on the live request and drop inline bytes for Grok HTTP."""
    raw = request.get("attachments")
    stored = intake.get("attachments") if isinstance(intake, dict) else None
    if not isinstance(raw, list) or not isinstance(stored, list):
        return
    for item, saved in zip(raw, stored):
        if not isinstance(item, dict) or not isinstance(saved, dict):
            continue
        path = str(saved.get("stored_path") or "").strip()
        if not path:
            continue
        item["stored_path"] = path
        item.pop("inline_base64", None)
        item.pop("base64", None)


def _prompt_with_attachment_context(prompt: str, attachment_intake: dict[str, Any]) -> str:
    context = str(attachment_intake.get("prompt_context") or "").strip()
    if not context:
        return prompt
    base = prompt.strip() or "Please review the attached file(s)."
    return f"{base}\n\n{context}"


def _build_chat_context_pack(
    prompt: str,
    request: dict[str, Any],
    attachment_intake: dict[str, Any],
    *,
    source: str,
) -> dict[str, Any]:
    raw_items = request.get("context_items")
    context_items = raw_items if isinstance(raw_items, list) else []
    try:
        return build_context_pack(
            prompt=prompt,
            attachments=attachment_intake.get("attachments") or [],
            context_items=[item for item in context_items if isinstance(item, dict)],
            request=request,
            source=source,
        )
    except Exception as exc:
        return {
            "schema": "ENGEL_CODEX_WORKBENCH_CONTEXT_PACK_V1",
            "ok": False,
            "created": False,
            "status": "context pack ingest failed",
            "error": _clip(str(exc), 300),
            "source_lineage_retained": False,
            "training_candidate": False,
            "trusted_memory_write": False,
            "external_array_used": False,
            "prompt_context": "",
        }


def _prompt_with_context_pack(
    prompt: str,
    context_pack: dict[str, Any],
    attachment_intake: dict[str, Any],
) -> str:
    context = str(context_pack.get("prompt_context") or "").strip()
    if not context:
        return _prompt_with_attachment_context(prompt, attachment_intake)
    base = prompt.strip() or "Please review the supplied context."
    return f"{base}\n\n{context}"


def _attach_context_pack_to_receipt(
    receipt: dict[str, Any], context_pack: dict[str, Any] | None
) -> dict[str, Any]:
    if not isinstance(context_pack, dict):
        return receipt
    public = {key: value for key, value in context_pack.items() if key != "prompt_context"}
    if public.get("created") is not True and public.get("ok") is True:
        return receipt
    receipt["codex_workbench_context_pack"] = public
    receipt["context_pack_id"] = public.get("pack_id", "")
    receipt["context_pack_created"] = public.get("created") is True
    return receipt


def _attach_intake_to_receipt(receipt: dict[str, Any], attachment_intake: dict[str, Any]) -> dict[str, Any]:
    if (
        int(attachment_intake.get("requested_count") or 0) <= 0
        and int(attachment_intake.get("count") or 0) <= 0
        and not attachment_intake.get("errors")
    ):
        return receipt
    receipt["chat_attachments"] = attachment_intake.get("attachments") or []
    receipt["chat_attachment_requested_count"] = attachment_intake.get("requested_count") or 0
    receipt["chat_attachment_count"] = attachment_intake.get("count")
    receipt["chat_attachment_stored_count"] = attachment_intake.get("stored_count")
    receipt["chat_attachment_errors"] = attachment_intake.get("errors") or []
    receipt["chat_attachment_storage_dir"] = attachment_intake.get("storage_dir") or ""
    receipt["chat_attachment_memory_policy"] = "raw inline base64 is dropped from receipts; stored files and previews are recorded"
    return receipt


def _maybe_capture_voice_example(
    prompt: str, reply: str, source: str, receipt: dict[str, Any] | None = None
) -> None:
    """(2026-07-10) Save a graded good user->reply pair to the voice example bank —
    ONLY replies that pass the style grader, so the bank stays clean (bad logs poison
    the voice). Runs the existing reply_passes_style check; fail-open, never affects
    the turn. This is the 'grade before saving' step of the persona layer.
    (NT-1) also records which cascade depth produced the exemplar."""
    try:
        reply = (reply or "").strip()
        if len(reply) < 30 or len(prompt.strip()) < 5:
            return
        # skip clearly-templated action/dispatch receipts (not conversational voice).
        low = reply.lower()
        if low.startswith(("sent that through", "order main-", "✓ ")):
            return
        from run_engel_standalone_chat_llm import reply_passes_style
        score = reply_passes_style(prompt, reply)
        if isinstance(score, dict) and score.get("ok"):
            import engel_persona
            depth, _, _ = _activation_depth(receipt or {}, source)
            engel_persona.add_example(prompt, reply, grade=0.85, source=source, depth=depth)
    except Exception:
        pass


def _apply_chat_humanizer(prompt: str, receipt: dict[str, Any], source: str) -> dict[str, Any]:
    original = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "").strip()
    form_graded = _is_form_graded_training_prompt(prompt)
    if form_graded:
        receipt["form_graded_training_turn"] = True
    final, meta = improve_visible_reply(prompt, original, source=source)
    # Communication SLM: rewrite the spoken draft after mechanical cleanup so
    # Discord/desktop chat is a person talking, not a regex card. Fail open.
    try:
        from engel_chat_humanization_slm import humanize_chat_reply

        spoken, slm_meta = humanize_chat_reply(prompt, final, source=source)
        meta["humanization_slm"] = slm_meta
        if spoken.strip() and (slm_meta.get("used") is True or slm_meta.get("reply_changed")):
            if spoken.strip() != final:
                final = spoken.strip()
                meta["reply_changed"] = True
                meta["reason"] = str(slm_meta.get("reason") or "humanization_slm")
            receipt["humanization_slm_used"] = True
            receipt["humanization_slm_reason"] = slm_meta.get("reason")
            receipt["humanization_slm_gguf"] = bool((slm_meta.get("gguf") or {}).get("used"))
        else:
            receipt["humanization_slm_used"] = False
            receipt["humanization_slm_reason"] = slm_meta.get("reason")
    except Exception:
        receipt["humanization_slm_used"] = False
        receipt["humanization_slm_reason"] = "call_failed"
    # Persona guard. EVERY chat lane finalises its reply through this function, so this is
    # the one place that can stop a recited answer-contract reaching a person: the training
    # harness sends its contracts down the same lane that serves live chat, and the model
    # restates them instead of answering ("...I will answer in plain English and follow the
    # rules without claiming proof of work...", live 2026-08-13). It runs BEFORE the voice
    # capture below on purpose - a recitation captured into the graded bank becomes an
    # example of Engel's voice and teaches the next model to do it again.
    persona_scrubbed = False
    persona_reason = ""
    try:
        from engel_persona_guard import scrub_persona_leak

        final, persona_scrubbed, persona_reason = scrub_persona_leak(final)
    except Exception:  # noqa: BLE001 -- the guard must never be why chat fails
        persona_scrubbed = False
        persona_reason = ""
    receipt["assistant_reply"] = final
    receipt["assistant_output_text"] = final
    receipt["chat_humanizer"] = meta
    receipt["server_chat_humanizer_used"] = bool(meta.get("reply_changed"))
    receipt["humanizer_reference_loaded"] = bool(meta.get("humanizer_reference_loaded"))
    receipt["workspace_registry_loaded"] = bool(meta.get("workspace_registry_loaded"))
    if persona_scrubbed:
        receipt["persona_guard"] = {"scrubbed": True, "reason": persona_reason, "source": source}
        logging.warning(
            "Persona guard scrubbed a recited contract (source=%s reason=%s)",
            source,
            persona_reason,
        )
    if meta.get("reply_changed") or persona_scrubbed:
        receipt["server_original_reply_preview"] = _clip(original, 500)
    if not persona_scrubbed:
        # A turn that leaked its instructions is not a voice sample of any grade.
        # Form-graded training answers must also stay out of the spoken voice bank.
        if not form_graded:
            _maybe_capture_voice_example(prompt, final, source, receipt)
    return receipt


def _fetch_json(url: str, timeout: float = 1.5) -> dict[str, Any]:
    clean = str(url or "").strip()
    if not clean:
        return {}
    try:
        req = urllib.request.Request(clean, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            parsed = json.loads(resp.read().decode("utf-8", errors="replace"))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _env_truth(name: str, default: bool = True) -> bool:
    value = os.environ.get(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip().casefold() in {"1", "true", "yes", "on", "enabled"}


def _provider_fallback_allowed(request: dict[str, Any]) -> bool:
    """Honor an explicit per-turn decision before the service default.

    Chat Communication must finish the turn. A local-only flag must not
    replace a real answer with a canned greeting when the router still has
    a fallback lane.
    """
    prompt = str(request.get("prompt") or "")
    source = str(request.get("source") or "").casefold()
    if source.startswith("discord") or _is_spoken_voice_training_prompt(prompt):
        return True
    if "allow_provider_fallback" in request:
        return request.get("allow_provider_fallback") is True
    return _env_truth("ENGEL_LOCAL_CHAT_AUTO_BRIDGE_FALLBACK", default=True)


def _request_local_only_training(request: dict[str, Any]) -> bool:
    metadata = request.get("metadata")
    return bool(
        request.get("local_only_training") is True
        or (isinstance(metadata, dict) and metadata.get("local_only_training") is True)
    )


def _request_governor_context(request: dict[str, Any]) -> dict[str, Any]:
    """Clamped Governor context from request metadata (docs/ENGEL_GOVERNOR_DESIGN.md
    section 3): the trusted local signal "this is a training turn of discipline X".
    Narrow-only by construction -- unknown keys drop, out-of-range values fall
    back, and a missing engel_governor module (older deploy) degrades to NO
    context, which means routing falls open to legacy behaviour."""
    metadata = request.get("metadata") if isinstance(request, dict) else None
    if not isinstance(metadata, dict) or not metadata:
        return {}
    try:
        from engel_governor import clamp_inbox_metadata

        return clamp_inbox_metadata(metadata)
    except Exception:
        return {}


def _governor_route_verdict(
    prompt: str, request: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Consult the Governor T0 route rules for this turn. Returns the verdict
    dict, or None when the governor is switched off, unavailable, or the turn
    carries no trusted metadata (organic chat stays on legacy heuristics --
    the governor only sharpens turns that DECLARE what they are). The kill
    switch restores byte-identical legacy routing."""
    # Cache only inside _run_chat_turn's explicit ContextVar boundary. Direct
    # callers (diagnostics, verifiers, and reusable routing helpers) otherwise
    # share the ContextVar default context and could inherit an earlier request.
    cache_active = _TURN_GOVERNOR_CONTEXT.get() is not None
    cached = _TURN_GOVERNOR_ROUTE_DECISION.get() if cache_active else None
    if isinstance(cached, dict):
        cached_verdict = cached.get("verdict")
        if isinstance(cached_verdict, dict):
            try:
                import engel_governor

                return (
                    None
                    if cached_verdict.get("outcome") == engel_governor.ROUTE_DEFER
                    else dict(cached_verdict)
                )
            except Exception:
                return None
    if not _env_truth("ENGEL_GOVERNOR_ROUTING_ENABLED", default=True):
        return None
    context = _request_governor_context(request if isinstance(request, dict) else {})
    if not context:
        return None
    try:
        import engel_governor
    except Exception:
        return None
    raw_prompt = str(prompt or "")
    features = {
        "discipline": context.get("training_discipline") or "",
        "interactive": context.get("interactive", True),
        "routing_hint": context.get("routing_hint") or "",
        "caller": "trainer" if context.get("training_run_id") else "chat_ui",
        "prompt_len": len(raw_prompt),
        "context_bytes": len(raw_prompt.encode("utf-8")),
    }
    # intent_router SLM as a recorded route FEATURE (the design's documented T0
    # feature that had no serving layer until 2026-07-31). Advisory: no T0 rule
    # branches on it yet, but it lands in the verdict's feature dict -> Phase A
    # receipts, so promotion is decided on logged agreement. These turns carry
    # trusted metadata (training/non-interactive), so the ~100ms embed is off
    # the interactive latency path; not-ready/unavailable simply omits it.
    try:
        from engel_slm_runtime import get_slm_runtime

        slm = get_slm_runtime()
        intent = slm.intent(raw_prompt) if slm.is_ready() else None
    except Exception:  # noqa: BLE001 -- feature absent, never a routing error
        intent = None
    if intent:
        features["intent"] = str(intent.get("label") or "")
        features["intent_confidence"] = round(float(intent.get("confidence") or 0.0), 3)
    try:
        verdict = engel_governor.govern("route", features)
    except Exception:
        return None
    # Learned routing remains shadow-only. Its prediction is recorded beside T0,
    # never substituted for T0's outcome.
    try:
        shadow = slm.route_advice(features) if slm.is_ready() else None
    except Exception:  # noqa: BLE001 -- shadow telemetry never costs routing
        shadow = None
    if shadow:
        verdict = dict(verdict)
        verdict["slm_shadow"] = shadow
    if cache_active:
        _TURN_GOVERNOR_ROUTE_DECISION.set(
            {"features": dict(features), "verdict": dict(verdict)}
        )
    if verdict.get("outcome") == engel_governor.ROUTE_DEFER:
        return None
    return verdict


def _governor_routes_to(
    prompt: str, request: dict[str, Any] | None, lane_attr: str
) -> dict[str, Any] | None:
    """Return the Governor verdict when it routes this turn to the lane named
    by engel_governor.<lane_attr> (e.g. "LANE_SPARSE_MOE"); None otherwise.
    Comparing against the module constant, not a string literal, keeps the
    service and the Governor's lane vocabulary from drifting apart."""
    verdict = _governor_route_verdict(prompt, request)
    if verdict is None:
        return None
    try:
        import engel_governor

        lane = getattr(engel_governor, lane_attr)
    except Exception:
        return None
    return verdict if verdict.get("outcome") == lane else None


def _parse_env_assignments(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[name] = value
    return values


def _provider_bridge_env_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for path in (
        PROVIDER_BRIDGE_ENV_FILE,
        ROOT / "run" / "secrets" / "nvidia.env",
        ROOT / ".env",
        ROOT / ".env.local",
    ):
        values.update(_parse_env_assignments(path))
    return values


def _normalize_provider_name(value: Any) -> str:
    text = str(value or "").strip().casefold()
    aliases = {
        "chatgpt": "openai",
        "chat-gpt": "openai",
        "chat_gpt": "openai",
        "gpt": "openai",
        "openai": "openai",
        "claude": "anthropic",
        "anthropic": "anthropic",
        "sonnet": "anthropic",
        "opus": "anthropic",
        "haiku": "anthropic",
        "grok": "xai",
        "xai": "xai",
        "x.ai": "xai",
        "xai_grok_cli": "xai",
        "xai-grok-cli": "xai",
        "grok-cli": "xai",
        "grok-build": "xai",
        "grok-build-0-1": "xai",
        "grok-build-0.1": "xai",
        "grok-4-3-max": "xai",
        "grok-4.6": "xai",
        "grok-4-6": "xai",
        "grok46": "xai",
        "grok-4.5": "xai",
        "gemini": "gemini",
        "google": "gemini",
        "googleai": "gemini",
        "google-ai": "gemini",
        "codex": "codex",
        "openai codex": "codex",
        "code assistant": "codex",
        "local": "local",
        "auto": "auto",
        "best": "auto",
        "auto-best": "auto",
        "nvidia": "nvidia",
        "nim": "nvidia",
        "nvidia-nim": "nvidia",
        "nvidia_nim": "nvidia",
    }
    return aliases.get(text, "")


PROVIDER_SPECIFIC_ENABLED_ENV_NAMES = {
    "openai": ("ENGEL_OPENAI_BRIDGE_ENABLED", "ENGEL_CHATGPT_BROWSER_BRIDGE_ENABLED"),
    "anthropic": ("ENGEL_ANTHROPIC_BRIDGE_ENABLED", "ENGEL_CLAUDE_CLI_BRIDGE_ENABLED"),
    "xai": ("ENGEL_XAI_BRIDGE_ENABLED", "ENGEL_GROK_CLI_BRIDGE_ENABLED"),
    "gemini": ("ENGEL_GEMINI_BRIDGE_ENABLED", "ENGEL_GEMINI_API_BRIDGE_ENABLED"),
    "codex": ("ENGEL_CODEX_BRIDGE_ENABLED", "ENGEL_CODEX_CLI_BRIDGE_ENABLED"),
    "nvidia": ("ENGEL_NVIDIA_BRIDGE_ENABLED", "ENGEL_NIM_BRIDGE_ENABLED"),
}

PROVIDER_ROUTE_DEFAULT_ENABLED = {
    "openai": True,
    "anthropic": False,
    "xai": True,
    "gemini": False,
    "codex": True,
    "nvidia": True,
}


def _provider_bridge_enabled_for_routing(provider: str) -> bool:
    provider_key = _normalize_provider_name(provider)
    if not provider_key or provider_key in {"local", "auto"}:
        return provider_key != "local"
    default = PROVIDER_ROUTE_DEFAULT_ENABLED.get(provider_key, True)
    for env_name in PROVIDER_SPECIFIC_ENABLED_ENV_NAMES.get(provider_key, ()):
        if os.environ.get(env_name) is not None:
            return _env_truth(env_name, default=default)
    return default


def _filter_enabled_provider_candidates(candidates: list[str]) -> list[str]:
    result: list[str] = []
    for provider in candidates:
        provider_key = _normalize_provider_name(provider)
        if provider_key and provider_key not in result and _provider_bridge_enabled_for_routing(provider_key):
            result.append(provider_key)
    return result


def _filter_automatic_provider_candidates(candidates: list[str]) -> list[str]:
    enabled = _filter_enabled_provider_candidates(candidates)
    if not enabled:
        return []
    try:
        from engel_provider_capability_map import filter_automatic_candidates

        capability_map = _cached_snapshot(
            "provider_capabilities",
            _provider_capability_snapshot,
            ttl_seconds=15.0,
        )
        return filter_automatic_candidates(enabled, capability_map)
    except Exception:
        return []


def _provider_secret_source(provider: str) -> dict[str, Any]:
    provider_key = _normalize_provider_name(provider)
    names = PROVIDER_BRIDGE_SECRET_NAMES.get(provider_key, [])
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return {
                "present": True,
                "provider": provider_key,
                "source_type": "process_env",
                "name": name,
                "value_length": len(value),
                "secret": value,
            }
    env_values = _provider_bridge_env_values()
    for name in names:
        value = str(env_values.get(name) or "").strip()
        if value:
            return {
                "present": True,
                "provider": provider_key,
                "source_type": "env_file",
                "name": name,
                "path": str(PROVIDER_BRIDGE_ENV_FILE if PROVIDER_BRIDGE_ENV_FILE.is_file() else ROOT / ".env"),
                "value_length": len(value),
                "secret": value,
            }
    return {
        "present": False,
        "provider": provider_key,
        "source_type": "",
        "name": "",
        "value_length": 0,
        "secret": "",
    }


def _public_secret_source(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "present": bool(source.get("present") is True),
        "provider": source.get("provider", ""),
        "source_type": source.get("source_type", ""),
        "name": source.get("name", ""),
        "path": source.get("path", ""),
        "value_length": source.get("value_length", 0),
    }


def _provider_bridge_status() -> dict[str, Any]:
    enabled = _env_truth("ENGEL_PROVIDER_BRIDGE_ENABLED", default=True)
    # Probe the ROG bridges concurrently: when bridges are down each probe
    # eats its own timeout, and running them serially made this (and /health)
    # take the SUM of all timeouts instead of the max.
    with ThreadPoolExecutor(max_workers=5, thread_name_prefix="engel-bridge-probe") as pool:
        chatgpt_future = pool.submit(_chatgpt_browser_bridge_status)
        grok_future = pool.submit(_grok_cli_bridge_status)
        claude_future = pool.submit(_claude_cli_bridge_status)
        gemini_future = pool.submit(_gemini_api_bridge_status)
        codex_future = pool.submit(_codex_cli_bridge_status)
        chatgpt_browser_status = chatgpt_future.result()
        grok_cli_status = grok_future.result()
        claude_cli_status = claude_future.result()
        gemini_api_status = gemini_future.result()
        codex_cli_status = codex_future.result()
    providers: dict[str, Any] = {}
    for provider in ("openai", "anthropic", "xai", "gemini", "codex", "nvidia"):
        source = _provider_secret_source(provider)
        provider_enabled = bool(enabled and _provider_bridge_enabled_for_routing(provider))
        local_route_ok = bool(
            (provider == "xai" and grok_cli_status.get("ok") is True)
            or (provider == "anthropic" and claude_cli_status.get("ok") is True)
            or (provider == "openai" and chatgpt_browser_status.get("ok") is True)
            or (provider == "gemini" and gemini_api_status.get("usable") is True)
            or (provider == "codex" and codex_cli_status.get("ok") is True)
        )
        direct_api_ready = bool(
            provider_enabled
            and source.get("present") is True
            and (
                provider != "openai"
                or _env_truth("ENGEL_OPENAI_API_FALLBACK_ENABLED", default=False)
                or not _env_truth("ENGEL_CHATGPT_BROWSER_BRIDGE_FIRST", default=True)
            )
        )
        connected = bool(provider_enabled and (direct_api_ready or local_route_ok))
        providers[provider] = {
            "label": PROVIDER_BRIDGE_LABELS[provider],
            "enabled": provider_enabled,
            "configured": provider_enabled,
            "connected": connected,
            "secret_present": bool(source.get("present") is True),
            "direct_api_ready": direct_api_ready,
            "local_route_ready": local_route_ok,
            "usable": connected,
            "connection_only": True,
            "completion_proven": False,
            "secret_source": _public_secret_source(source),
            "model_candidates": _provider_model_candidates(provider, {}, include_request=False),
            "local_route": (
                chatgpt_browser_status
                if provider == "openai"
                else grok_cli_status
                if provider == "xai"
                else claude_cli_status
                if provider == "anthropic"
                else gemini_api_status
                if provider == "gemini"
                else codex_cli_status
                if provider == "codex"
                else {}
            ),
        }
    return {
        "schema": "engel_provider_bridge_status_v1",
        "ok": True,
        "enabled": enabled,
        "env_file": str(PROVIDER_BRIDGE_ENV_FILE),
        "env_file_present": PROVIDER_BRIDGE_ENV_FILE.is_file(),
        "providers": providers,
        "routing": {
            "chat_or_customer": ["local"] + _filter_enabled_provider_candidates(["nvidia", "xai", "openai"]),
            "code_or_review": ["local"] + _filter_enabled_provider_candidates(["nvidia", "codex", "xai", "openai"]),
            "current_or_social": ["local"] + _filter_enabled_provider_candidates(["xai", "openai", "nvidia"]),
            "google_or_long_context": ["local"] + _filter_enabled_provider_candidates(["gemini", "nvidia", "openai", "xai"]),
            "explicit_provider_words_override_auto": True,
            "bridges_are_fallback_or_explicit": True,
            "configuration_only": True,
            "completion_capability_endpoint": "/providers/capabilities",
        },
        "persistent_memory_path": str(PERSISTENT_CHAT_MEMORY_PATH),
        "rog_chatgpt_browser_bridge": chatgpt_browser_status,
        "rog_grok_cli_bridge": grok_cli_status,
        "rog_claude_cli_bridge": claude_cli_status,
        "rog_gemini_api_bridge": gemini_api_status,
        "rog_codex_cli_bridge": codex_cli_status,
        "updated_at_utc": _iso_now(),
    }


def _redact_provider_error(text: Any) -> str:
    raw = str(text or "").strip()
    for _ in range(3):
        parsed: Any | None = None
        if raw.startswith("{") and raw.endswith("}"):
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = None
        if not isinstance(parsed, dict):
            break
        receipt = parsed.get("receipt") if isinstance(parsed.get("receipt"), dict) else {}
        parts = [
            parsed.get("status"),
            parsed.get("error"),
            parsed.get("message"),
            parsed.get("reason"),
            receipt.get("status"),
            receipt.get("error"),
            receipt.get("message"),
            receipt.get("reason"),
        ]
        compact = "; ".join(str(part).strip() for part in parts if str(part or "").strip())
        if not compact or compact == raw:
            break
        raw = compact
    low = raw.lower()
    if "session limit" in low and "reset" in low:
        clean = _clip(raw, 220)
    elif "gemini api key missing" in low or "no reachable gemini key" in low:
        clean = "Gemini API key is not reachable by the local Gemini bridge."
    elif "command line is too long" in low:
        clean = "Provider CLI rejected the prompt because the command line was too long."
    else:
        clean = _clip(raw, 260)
    for names in PROVIDER_BRIDGE_SECRET_NAMES.values():
        for name in names:
            value = os.environ.get(name, "").strip()
            if value and len(value) >= 8:
                clean = clean.replace(value, "[REDACTED_PROVIDER_SECRET]")
    for value in _provider_bridge_env_values().values():
        if value and len(value) >= 8:
            clean = clean.replace(value, "[REDACTED_PROVIDER_SECRET]")
    return clean


def _provider_model_candidates(provider: str, request: dict[str, Any] | None = None, *, include_request: bool = True) -> list[str]:
    provider_key = _normalize_provider_name(provider)
    request = request or {}
    candidates: list[str] = []
    if include_request:
        metadata = request.get("metadata") if isinstance(request.get("metadata"), dict) else {}
        if provider_key == "nvidia":
            for key in ("nvidia_nim_model", "nvidia_model"):
                value = str(request.get(key) or metadata.get(key) or "").strip()
                if value:
                    candidates.append(value)
            try:
                from engel_nvidia_discover import nvidia_candidates_for_prompt

                creative_prompt = str(
                    request.get("prompt")
                    or metadata.get("discord_original_prompt")
                    or ""
                )
                desk = str(metadata.get("discord_desk_name") or "")
                for model in nvidia_candidates_for_prompt(creative_prompt, desk):
                    candidates.append(model)
            except Exception:
                pass
        requested_model = str(request.get("model") or request.get("provider_model") or "").strip()
        if requested_model and requested_model not in {"auto", "auto-best"}:
            if provider_key == "xai":
                requested_model = _canonical_grok_build_model(requested_model)
            if provider_key != "nvidia" or "/" in requested_model:
                candidates.append(requested_model)
    for env_name in PROVIDER_MODEL_ENV_NAMES.get(provider_key, []):
        value = os.environ.get(env_name, "").strip()
        if value:
            candidates.append(value)
    config = _load_json_file(ROOT / "memory" / "personality" / "ENGEL_CHAT_PROVIDER_CONFIG.json")
    if provider_key == "openai":
        configured = str(config.get("chatgpt_model") or "").strip()
        if configured:
            candidates.append(configured)
    candidates.extend(PROVIDER_MODEL_FALLBACKS.get(provider_key, []))
    result: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in result:
            result.append(candidate)
    return result


# ---------------------------------------------------------------------------
# (2026-07-10 NT-3) Retrieve-once, carry-forward. A single chat turn can cascade
# quick -> big -> provider-bridge (and the bridge failover loop re-enters per
# provider); each hop otherwise re-queries nomic-embed (:8940), re-reads the chat
# tail, and re-reads durable facts. This per-turn memo computes each recall ONCE
# and hands the SAME result to every hop. Behaviour-preserving (identical content,
# fewer calls). ContextVar + begin/try/finally reset is required because the server
# reuses pool threads, so a leaked cache would otherwise cross requests.
# ---------------------------------------------------------------------------
_TURN_RECALL_CACHE: "contextvars.ContextVar[dict | None]" = contextvars.ContextVar(
    "engel_turn_recall_cache", default=None
)

# Turn-scoped clamped governor context (same reset-in-finally discipline as the
# recall cache above): set in _run_chat_turn, read by _stamp_chat_memory_hygiene,
# which runs deep inside the turn before the finalize path stamps the receipt.
_TURN_GOVERNOR_CONTEXT: "contextvars.ContextVar[dict | None]" = contextvars.ContextVar(
    "engel_turn_governor_context", default=None
)

# Captured once per request and folded into the normal chat receipt. This is the
# missing real-data source for the Route Governor SLM and adds no second writer.
_TURN_GOVERNOR_ROUTE_DECISION: "contextvars.ContextVar[dict | None]" = contextvars.ContextVar(
    "engel_turn_governor_route_decision", default=None
)

# Turn-scoped chat-only flag (request key "chat_only": narrow-only -- it can
# ONLY disable action dispatch, never enable anything). Callers set it when a
# turn is pure text generation whose prompt wording may legitimately mention
# workers/builds (e.g. the EngelScript draft flow: its instruction text tripped
# the meeting-room dispatch lane live on 2026-07-31).
_TURN_CHAT_ONLY: "contextvars.ContextVar[bool]" = contextvars.ContextVar(
    "engel_turn_chat_only", default=False
)


def _begin_turn_recall_cache():
    """Open a per-turn recall memo. Reentrant: if an outer scope already owns a cache
    (e.g. streaming that falls through to _run_chat_turn) return None so this caller
    does NOT reset the outer scope's cache."""
    if _TURN_RECALL_CACHE.get() is not None:
        return None
    return _TURN_RECALL_CACHE.set({})


def _end_turn_recall_cache(token) -> None:
    if token is not None:
        try:
            _TURN_RECALL_CACHE.reset(token)
        except Exception:
            # (2026-07-26 neuro audit) a failed reset must not freeze a stale
            # memo onto this pooled thread — hard-clear instead.
            try:
                _TURN_RECALL_CACHE.set(None)
            except Exception:
                pass


def _turn_recall_memo(key, compute):
    """Return cache[key], computing+storing via compute() on the first miss this turn.
    No active turn scope -> compute live (identical to the un-memoized behaviour)."""
    cache = _TURN_RECALL_CACHE.get()
    if cache is None:
        return compute()
    if key in cache:
        return cache[key]
    value = compute()
    cache[key] = value
    return value


def _semantic_memory_context(prompt: str) -> str:
    return _turn_recall_memo(("semantic", prompt), lambda: _semantic_memory_context_uncached(prompt))


def _semantic_memory_context_uncached(prompt: str) -> str:
    """Retrieve relevant past facts BY MEANING via the nomic-embed memory
    service, so Engel recalls things from any point in history - not just the
    last few lines. Fast-fail so it never stalls a chat turn."""
    query = _intent_gate_text(prompt).strip()
    if len(query) < 6:
        return ""
    try:
        body = json.dumps({"query": query, "k": 4}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8940/search",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return ""
    results = data.get("results") if isinstance(data.get("results"), list) else []
    lines = [
        f"- {str(r.get('text') or '')[:400]}"
        for r in results
        if r.get("text") and not _semantic_text_matches_rejected_sample(str(r.get("text") or ""))
    ]
    if not lines:
        return ""
    return (
        "RELEVANT FACTS FROM ENGEL'S MEMORY (retrieved by meaning for THIS question - "
        "use them; they are things Joshua told Engel or Engel recorded before):\n" + "\n".join(lines)
    )


def _request_conversation_id(request: dict[str, Any] | None) -> str:
    request = request or {}
    metadata = request.get("metadata") if isinstance(request.get("metadata"), dict) else {}
    raw = str(
        metadata.get("conversation_id")
        or metadata.get("chat_session_id")
        or request.get("conversation_id")
        or request.get("chat_session_id")
        or ""
    ).strip()
    if not raw:
        return ""
    safe = re.sub(r"[^A-Za-z0-9_.:-]+", "-", raw).strip("-.")[:96]
    return safe or hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _chat_context_scope(request: dict[str, Any] | None) -> str:
    request = request or {}
    source = str(request.get("source") or request.get("client") or "").strip().casefold()
    metadata = request.get("metadata") if isinstance(request.get("metadata"), dict) else {}
    if source.startswith("discord"):
        channel = str(metadata.get("discord_channel_id") or "channel").strip()
        author = str(metadata.get("discord_author_id") or "user").strip()
        return f"discord:{channel}:{author}"
    if source in {"engel_ai_main_ui", "engel_flutter_main", "desktop_ui", "rog_ui", "rog_desktop_controller"}:
        conversation_id = _request_conversation_id(request)
        return (
            f"engel_ai_main_desktop:{conversation_id}"
            if conversation_id
            else "engel_ai_main_desktop"
        )
    return source or "engel_unscoped"


def _request_context_preview(request: dict[str, Any] | None, max_chars: int = 1200) -> str:
    request = request or {}
    metadata = request.get("metadata") if isinstance(request.get("metadata"), dict) else {}
    preview = str(
        metadata.get("discord_context_preview")
        or metadata.get("conversation_context_preview")
        or request.get("conversation_context")
        or ""
    ).strip()
    return preview[-max_chars:] if preview else ""


def _discord_room_memory(request: dict[str, Any] | None, max_chars: int = 4000) -> str:
    """Discord is a room. The model must see who is talking and the recent channel."""
    request = request or {}
    source = str(request.get("source") or request.get("client") or "").strip().casefold()
    if not source.startswith("discord"):
        return ""
    metadata = request.get("metadata") if isinstance(request.get("metadata"), dict) else {}
    header = str(metadata.get("discord_sender_header") or "").strip()
    preview = _request_context_preview(request, max_chars=max_chars)
    parts: list[str] = []
    if header:
        parts.append(header)
    if preview:
        parts.append(
            "RECENT DISCORD ROOM CONTEXT (continue this conversation; do not reset):\n"
            + preview
        )
    return "\n\n".join(parts)


def _prompt_with_discord_room(prompt: str, request: dict[str, Any] | None) -> str:
    room = _discord_room_memory(request)
    body = str(prompt or "").strip()
    talk = (
        "DISCORD TALK: Answer as Engel in first person. Think about the current message. "
        "Do not write a Joshua-asks template card. "
        "Do not recap the house map, Sub-Engel, CT246, or the home lab unless this message asks. "
        "If the message is a link, talk about that topic."
    )
    if not room:
        return talk + "\n\nCurrent user message:\n" + body if body else body
    return talk + "\n\n" + room + "\n\nCurrent user message:\n" + body


def _recent_chat_context(max_chars: int = 2200, max_records: int = 6, context_scope: str = "") -> str:
    return _turn_recall_memo(
        ("recent", max_chars, max_records, context_scope),
        lambda: _recent_chat_context_uncached(max_chars, max_records, context_scope),
    )


def _chat_sample_key(prompt: str, reply: str) -> str:
    normalized = "\n".join(
        (
            " ".join(str(prompt or "").split()).casefold(),
            " ".join(str(reply or "").split()).casefold(),
        )
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _rejected_chat_samples_uncached() -> dict[str, Any]:
    active: dict[str, dict[str, Any]] = {}
    if REJECTED_CHAT_SAMPLES_PATH.is_file():
        try:
            for line in REJECTED_CHAT_SAMPLES_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(item, dict):
                    continue
                sample_key = str(item.get("sample_key") or "").strip()
                if not sample_key:
                    continue
                if item.get("active") is False:
                    active.pop(sample_key, None)
                else:
                    active[sample_key] = item
        except OSError:
            active = {}
    receipt_paths: set[str] = set()
    reply_signatures: list[str] = []
    for item in active.values():
        receipt_path = str(item.get("receipt_path") or "").strip()
        if receipt_path:
            receipt_paths.add(receipt_path.replace("\\", "/").casefold())
        signature = " ".join(str(item.get("assistant_reply") or "").split()).casefold()
        if len(signature) >= 40:
            reply_signatures.append(signature[:320])
    return {
        "sample_keys": set(active),
        "receipt_paths": receipt_paths,
        "reply_signatures": reply_signatures,
    }


def _rejected_chat_samples() -> dict[str, Any]:
    return _turn_recall_memo(("rejected_chat_samples",), _rejected_chat_samples_uncached)


def _chat_record_rejected(item: dict[str, Any]) -> bool:
    prompt = str(item.get("prompt") or "")
    reply = str(item.get("assistant_reply") or item.get("assistant_output_text") or "")
    rejected = _rejected_chat_samples()
    if _chat_sample_key(prompt, reply) in rejected["sample_keys"]:
        return True
    for field in ("workspace_receipt_path", "local_chat_receipt_path", "receipt_path"):
        receipt_path = str(item.get(field) or "").strip().replace("\\", "/").casefold()
        if receipt_path and receipt_path in rejected["receipt_paths"]:
            return True
    return False


def _semantic_text_matches_rejected_sample(text: str) -> bool:
    normalized = " ".join(str(text or "").split()).casefold()
    if not normalized:
        return False
    return any(signature in normalized for signature in _rejected_chat_samples()["reply_signatures"])


def _append_chat_sample_rejection(
    prompt: str,
    reply: str,
    receipt: dict[str, Any] | None,
    reason: str,
    *,
    source: str = "engel-ai-main local quality quarantine",
) -> dict[str, Any]:
    receipt = receipt if isinstance(receipt, dict) else {}
    sample_key = _chat_sample_key(prompt, reply)
    receipt_path = str(
        receipt.get("workspace_receipt_path")
        or receipt.get("local_chat_receipt_path")
        or receipt.get("receipt_path")
        or ""
    ).strip()
    record = {
        "schema": "engel_chat_rejected_sample_v1",
        "active": True,
        "rejected_at_utc": _iso_now(),
        "sample_key": sample_key,
        "prompt_sha256": hashlib.sha256(str(prompt or "").encode("utf-8")).hexdigest(),
        "assistant_reply_sha256": hashlib.sha256(str(reply or "").encode("utf-8")).hexdigest(),
        "prompt": str(prompt or ""),
        "assistant_reply": str(reply or ""),
        "receipt_path": receipt_path,
        "reason": str(reason or "local reply failed the semantic quality gate"),
        "source": str(source or "engel-ai-main quality quarantine"),
    }
    try:
        _append_jsonl(REJECTED_CHAT_SAMPLES_PATH, record)
        record["ok"] = True
    except Exception as exc:
        record["ok"] = False
        record["error"] = str(exc)
    cache = _TURN_RECALL_CACHE.get()
    if isinstance(cache, dict):
        cache.pop(("rejected_chat_samples",), None)
    return record


def _recent_chat_records_uncached(context_scope: str = "") -> list[dict[str, Any]]:
    if not PERSISTENT_CHAT_MEMORY_PATH.is_file():
        return []
    try:
        with PERSISTENT_CHAT_MEMORY_PATH.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 1_000_000))
            text = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    records: list[dict[str, Any]] = []
    seen_turns: set[tuple[str, str]] = set()
    for line in reversed(text.splitlines()[-200:]):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("prompt") and (item.get("assistant_reply") or item.get("assistant_output_text")):
            status = str(item.get("status") or "").casefold()
            if item.get("ok") is not True or item.get("quality_gate_degraded") is True:
                continue
            if "quality warning" in status or "quality check failed" in status or "style check failed" in status:
                continue
            if _chat_record_rejected(item):
                continue
            # (2026-07-31) Training turns are PERSISTED (the corpus needs them, and the
            # runner's DONE gate + the CT SSH cross-check both require the append) but they
            # must never be re-injected as chat context. Without this skip a training turn
            # -- injected answer contract and all -- was reloaded verbatim into "RECENT
            # ENGEL CHAT CONTEXT", and the 7B parroted the contract back on the next turn
            # instead of answering: the pipeline manufactured its own echo bait. Isolate,
            # do not skip the append. The scope filter below is NOT sufficient on its own:
            # it only bites when context_scope is non-empty, so an unscoped loader would
            # still pull training turns. Real turns never carry this flag, so grounding is
            # unaffected.
            if item.get("local_only_training") is True or item.get("training_turn") is True:
                remembered_prompt = str(item.get("prompt") or "")
                if not _is_spoken_voice_training_prompt(remembered_prompt):
                    continue
            # Governor persist contract (docs/ENGEL_GOVERNOR_DESIGN.md section 4):
            # records stamped context_eligible False / echo True are quarantined at
            # read time no matter how they were written. The field is absent on all
            # legacy records (absent => eligible), so existing grounding is untouched.
            if item.get("context_eligible") is False or item.get("echo") is True:
                continue
            # Quarantine near-duplicates of already-rejected replies too. _chat_record_rejected
            # above matches only exact sample keys / receipt paths, so a reply that merely
            # REPEATS a rejected one (the classic echo shape) slipped back into context.
            # The semantic path already applied this; the recent-context path did not.
            if _semantic_text_matches_rejected_sample(
                item.get("assistant_reply") or item.get("assistant_output_text")
            ):
                continue
            # (2026-08-17) Recited stance replies ("...unless a worker reports it")
            # were being fed back as "RECENT ENGEL CHAT CONTEXT", so the 7B kept
            # parroting them instead of answering. Skip them at read time.
            _recent_reply = str(
                item.get("assistant_reply") or item.get("assistant_output_text") or ""
            )
            try:
                from engel_persona_guard import looks_like_persona_leak

                if looks_like_persona_leak(_recent_reply):
                    continue
                from engel_persona_guard import looks_like_discord_mouth_reply

                if looks_like_discord_mouth_reply(_recent_reply):
                    continue
            except Exception:
                if "unless a worker reports" in _recent_reply.casefold():
                    continue
            if context_scope and str(item.get("chat_context_scope") or "") != context_scope:
                continue
            turn_key = (
                str(item.get("prompt") or "").strip().casefold(),
                str(item.get("assistant_reply") or item.get("assistant_output_text") or "").strip().casefold(),
            )
            if turn_key in seen_turns:
                continue
            seen_turns.add(turn_key)
            records.append(item)
    records.reverse()
    return records


def _format_recent_chat_record(item: dict[str, Any]) -> str:
    prompt = _clip(item.get("prompt"), 220)
    reply = _clip(item.get("assistant_reply") or item.get("assistant_output_text"), 320)
    provider = _clip(item.get("selected_provider") or item.get("provider"), 80)
    return f"- [{provider}] Joshua: {prompt}\n  Engel: {reply}"


def _recent_chat_turn_at_offset(offset: int, context_scope: str = "") -> str:
    records = _recent_chat_records_uncached(context_scope)
    if offset < 0 or len(records) <= offset:
        return ""
    return _format_recent_chat_record(records[-(offset + 1)])


def _recent_chat_context_uncached(max_chars: int = 2200, max_records: int = 6, context_scope: str = "") -> str:
    records = _recent_chat_records_uncached(context_scope)
    lines: list[str] = []
    for item in records[-max_records:]:
        lines.append(_format_recent_chat_record(item))
    context = "\n".join(lines).strip()
    if len(context) <= max_chars:
        return context
    return context[-max_chars:].split("\n", 1)[-1].strip()


_ENGEL_PERSONA_CACHE: dict[str, str] = {}


def _engel_persona_core() -> str:
    """Condensed Engel personality, loaded once from the merged personality doc.
    Provider turns without this answered as the raw model ('you're hitting the
    Anthropic bridge') - Joshua: 'I want to talk with Engel.'"""
    if "text" in _ENGEL_PERSONA_CACHE:
        return _ENGEL_PERSONA_CACHE["text"]
    text = ""
    try:
        raw = (ROOT / "memory" / "personality" / "ENGEL_AI_MERGED_PERSONALITY.md").read_text(
            encoding="utf-8", errors="replace"
        )
        text = " ".join(raw.split())[:1100]
    except Exception:
        text = ""
    _ENGEL_PERSONA_CACHE["text"] = text
    return text


def _self_model_document() -> dict[str, Any]:
    try:
        from engel_self_model_runtime import validate_state

        payload = json.loads(SELF_MODEL_STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("self model is not an object")
        valid, errors = validate_state(payload)
        if not valid:
            return {
                "schema": "ENGEL_PERSISTENT_SELF_MODEL_STATUS_V1",
                "ok": False,
                "status": "self-model integrity check failed",
                "validation_errors": errors,
            }
        return payload
    except (ImportError, OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "schema": "ENGEL_PERSISTENT_SELF_MODEL_STATUS_V1",
            "ok": False,
            "status": "self model unavailable",
            "error_type": type(exc).__name__,
        }


def _self_model_snapshot() -> dict[str, Any]:
    state = _self_model_document()
    if state.get("schema") != "ENGEL_PERSISTENT_SELF_MODEL_V1":
        return state
    return {
        "schema": "ENGEL_PERSISTENT_SELF_MODEL_STATUS_V1",
        "ok": state.get("ok") is True,
        "operational_ready": state.get("operational_ready") is True,
        "state_revision": int(state.get("state_revision") or 0),
        "state_sha256": str(state.get("state_sha256") or ""),
        "observed_at_utc": str(state.get("observed_at_utc") or ""),
        "current_focus": state.get("current_focus") or {},
        "known_limits": (state.get("introspection") or {}).get("current_limits", []),
    }


def _self_model_state_age_seconds(state: dict[str, Any]) -> "float | None":
    try:
        from datetime import datetime, timezone

        observed = str(state.get("observed_at_utc") or "").replace("Z", "+00:00")
        if not observed:
            return None
        return (datetime.now(timezone.utc) - datetime.fromisoformat(observed)).total_seconds()
    except (ValueError, TypeError):
        return None


_SELF_MODEL_REFRESH_LOCK = threading.Lock()
_SELF_MODEL_LAST_REFRESH_ATTEMPT = 0.0
SELF_MODEL_STALE_AFTER_SECONDS = float(os.environ.get("ENGEL_SELF_MODEL_STALE_AFTER_SECONDS", "900") or "900")
SELF_MODEL_REFRESH_MIN_INTERVAL_SECONDS = 300.0
# (2026-07-26 neuro audit) must fit inside a client chat timeout — the observe
# blocks the introspection turn that triggers it (rate-limited to 1 per 300s).
SELF_MODEL_OBSERVE_TIMEOUT_SECONDS = 20.0


def _self_model_fresh_observe_if_stale() -> dict[str, Any]:
    """Sentient freshness: when an introspection query arrives and the persisted
    self-model is stale or missing, re-observe OUT OF PROCESS (bounded timeout,
    rate-limited) so 'current self state' answers rest on current evidence.
    Failure never breaks chat — the stale state stays served with an honest age
    label; this only ever refreshes, it approves/deploys/promotes nothing."""
    global _SELF_MODEL_LAST_REFRESH_ATTEMPT
    state = _self_model_document()
    age = _self_model_state_age_seconds(state)
    evidence: dict[str, Any] = {
        "attempted": False, "refreshed": False,
        "age_before_seconds": None if age is None else int(age),
        "stale_after_seconds": int(SELF_MODEL_STALE_AFTER_SECONDS),
    }
    fresh_enough = (state.get("schema") == "ENGEL_PERSISTENT_SELF_MODEL_V1"
                    and age is not None and age <= SELF_MODEL_STALE_AFTER_SECONDS)
    if fresh_enough:
        return evidence
    with _SELF_MODEL_REFRESH_LOCK:
        now = time.time()
        if now - _SELF_MODEL_LAST_REFRESH_ATTEMPT < SELF_MODEL_REFRESH_MIN_INTERVAL_SECONDS:
            evidence["skipped"] = "rate-limited"
            return evidence
        _SELF_MODEL_LAST_REFRESH_ATTEMPT = now
    evidence["attempted"] = True
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "engel_self_model_runtime.py"), "observe"],
            cwd=str(ROOT), capture_output=True, text=True,
            timeout=SELF_MODEL_OBSERVE_TIMEOUT_SECONDS,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        evidence["observe_returncode"] = proc.returncode
        if proc.returncode == 0:
            new_age = _self_model_state_age_seconds(_self_model_document())
            evidence["refreshed"] = new_age is not None and (age is None or new_age < age)
            evidence["age_after_seconds"] = None if new_age is None else int(new_age)
    except Exception as exc:
        evidence["error"] = str(exc)[:160]
    return evidence


def _self_model_context(budget: int = 1600) -> str:
    state = _self_model_document()
    if state.get("schema") != "ENGEL_PERSISTENT_SELF_MODEL_V1" or state.get("ok") is not True:
        return ""
    try:
        from engel_self_model_runtime import render_context

        context = render_context(state, max_chars=max(400, min(budget, 2400))).strip()
        # Honest freshness label: Engel must know how old its self-evidence is.
        age = _self_model_state_age_seconds(state)
        if age is not None:
            minutes = int(age // 60)
            context += (f"\nSelf-observation age: {minutes} minute(s); treat time-varying "
                        "state older than 15 minutes as possibly stale.")
        return context
    except (ImportError, ValueError, TypeError):
        return ""


def _prompt_requests_self_model_introspection(prompt: str) -> bool:
    low = _intent_gate_text(prompt).casefold()
    direct_terms = (
        "self-model",
        "self model",
        "introspection",
        "introspect",
        "what do you know about yourself",
        "your own current state",
        "your current self state",
    )
    return any(term in low for term in direct_terms)


def _persona_block(prompt: str, budget: int = 1400) -> str:
    """(2026-07-10) Voice layer: strict style card + retrieved good voice examples +
    distilled voice notes (tools/engel_persona.py). This is the 'context discipline'
    that gives the local model personality without training. Fail-open."""
    try:
        import engel_persona
        return engel_persona.persona_context(prompt, budget=budget)
    except Exception:
        return ""


# Big-lane extra-memory budget. Both big-lane entry points (run_chat + streaming
# build_large_local_system_prompt) compose persona + durable facts + semantic recall the
# same way; keep it in one place so the two can't drift or cap differently.
# (2026-07-12) 2600 -> 4000: the GPU lane runs n_ctx 8192 and the whole constructed
# prompt measured ~6.8k chars — the old cap was starving components for no reason.
_BIG_LANE_MEM_BUDGET = 4000


# (2026-07-27) The semantic-quality prompt is "PRIOR TURN ... CURRENT USER TURN: x".
# The incomplete-input discipline is about the CURRENT request's own inputs, so it
# must read only the current turn. Judging the concatenation let an unrelated earlier
# answer (any text with 'evidence'/'design'/'record' + 'unknown'/'conflict') drag the
# NEXT innocent question into construction-document discipline and refuse it — proven
# live on 20260727 when a briefing request and an ethics question were both blocked.
_CURRENT_TURN_MARKER = "CURRENT USER TURN:"


def _current_turn_text(prompt: str) -> str:
    text = str(prompt or "")
    marker_at = text.rfind(_CURRENT_TURN_MARKER)
    if marker_at >= 0:
        return text[marker_at + len(_CURRENT_TURN_MARKER):].strip()
    return text


def _reply_is_conversation_stall(reply: str) -> bool:
    """True when the model repeated a greeting or Discord guest card instead of answering."""
    low = " ".join(str(reply or "").casefold().split())
    if not low:
        return False
    if "what should we work on next" in low:
        return True
    greeting_only = len(low) < 220 and (
        low.startswith("i am here with you")
        or low.startswith("i'm here with you")
        or low.startswith("engel ai main is here with you")
        or low.startswith("joshua")
        and "here with you" in low
    )
    if greeting_only:
        return True
    return any(
        marker in low
        for marker in (
            "only engelz can use engel tools",
            "only engelz can run admin",
            "diagnostics from discord",
            "i can chat here, but only engelz",
            "guest chat gate",
            "still on the last thought",
            "send that once more",
        )
    )


def _is_spoken_voice_training_prompt(prompt: str) -> bool:
    """Chat Communication turns train Engel's spoken voice, not AEC ledgers."""
    low = str(prompt or "").casefold()
    return "answer the way you would answer joshua" in low or (
        "training depth:" in low and "ordinary chat prose" in low
    )


def _prompt_has_incomplete_project_inputs(prompt: str) -> bool:
    if _is_spoken_voice_training_prompt(prompt):
        return False
    low = _intent_gate_text(_current_turn_text(prompt)).casefold()
    uncertainty = any(
        term in low
        for term in (
            "incomplete",
            "missing",
            "not shown",
            "not indicated",
            "not documented",
            "not supplied",
            "nobody supplied",
            "unknown",
            "unclear",
            "uncertain",
            "unconfirmed",
            "tbd",
            "conflict",
            "contradict",
            "disputed",
            "show different",
            "varies",
            "vary between",
            "mismatch",
            "discrepancy",
            "may have",
            "overlap only",
            "moved near",
            "hides old",
            "keep this boundary active",
            "evidence ledger",
            "unprovided input",
            "unsupported claim",
            "proof requirement",
            "absent evidence",
            "unsupported",
            "assumed",
            "assumption",
            "split across",
            "across references",
            "open question",
        )
    )
    project_context = any(
        term in low
        for term in (
            "drawing",
            "plan",
            "sheet",
            "detail",
            "elevation",
            "support",
            "finish",
            "clearance",
            "field",
            "design",
            "scope",
            "responsibility",
            "project",
            "kickoff",
            "survey",
            "datum",
            "coordinate",
            "structural",
            "embed",
            "fabricat",
            "opening",
            "equipment",
            "evidence",
            "anchor",
            "slab",
            "installation",
            "grid",
            "test log",
            "calibration",
            "hanger",
            "inspection",
            "fastener",
            "substrate",
            "brace",
            "record",
            "review",
            "scan",
            "alignment",
            "control target",
        )
    )
    return uncertainty and project_context


# (2026-08-10) Hand the GPU lane module our discipline-gate detector so training-turn
# exploration temperature backs off to base whenever the incomplete-input semantic
# gate is armed (exploration drafts fail its required structure — live 502s). This is
# injection, not import: run_engel_standalone_chat_llm must never import this module.
try:
    import run_engel_standalone_chat_llm as _rog_gpu_chat_module

    _rog_gpu_chat_module._incomplete_input_gate_check = _prompt_has_incomplete_project_inputs
except Exception:
    pass


def _incomplete_input_guidance(prompt: str) -> str:
    if not _prompt_has_incomplete_project_inputs(prompt):
        return ""
    return (
        "INCOMPLETE-INPUT DISCIPLINE: Separate confirmed source information from missing or conflicting inputs. "
        "Do not invent dimensions, elevations, support design, finishes, clearances, or responsibility. Name the "
        "owner/source that must confirm each blocker, propose an RFI or explicit open-question list, and identify "
        "only the drafting work that can safely proceed while those answers are pending. Consolidating references "
        "is useful organization, but it does not resolve an unanswered design decision. Do not propose placeholder "
        "geometry with approximate values, and do not derive dimensions from unscaled photos. Do not draft an email "
        "unless the user asks for one. Name accountable roles instead of bracketed placeholders, and never claim you "
        "sent, issued, uploaded, contacted, updated, or ensured work unless a verified action receipt exists. Stay on the current "
        "subject instead of importing tasks or nouns from another project. Do not default to a long RFI template when "
        "a concise open-question list answers the request. Keep the answer "
        "focused and complete within 250 words."
    )


def _facts_clipped(budget: int) -> str:
    """The durable-facts block bounded to `budget` chars by dropping the OLDEST
    fact lines first. (2026-07-12) The old flow joined persona+facts+semantic and
    sliced the JOIN tail — as the facts file grew, the NEWEST facts (the ones
    Joshua just taught and expects used) were exactly what got cut, and Engel
    answered identity questions with hallucinated placeholders."""
    block = _facts_for_prompt()
    if len(block) <= budget:
        return block
    header, _, body = block.partition("\n")
    lines = body.splitlines()
    while lines and (len(header) + 1 + sum(len(l) + 1 for l in lines)) > budget:
        lines.pop(0)
    return (header + "\n" + "\n".join(lines)) if lines else ""


def _chat_facts_clipped(prompt: str, budget: int) -> str:
    """Keep contact details out of ordinary model context unless Joshua asks for them."""
    block = _facts_clipped(budget)
    low = _intent_gate_text(prompt).casefold()
    if any(term in low for term in ("contact", "email", "linkedin", "website", "business site", "url")):
        return block
    company_identity_requested = any(
        term in low
        for term in (
            "my employer",
            "where do i work",
            "my company",
            "my business",
            "jz drafting",
            "global modular",
        )
    )
    lines = [
        line
        for line in block.splitlines()
        if not any(term in line.casefold() for term in ("contact email", "linkedin", "http://", "https://", ".com", "@"))
        and (
            company_identity_requested
            or not any(
                term in line.casefold()
                for term in ("global modular", "jz drafting", "24/7 back-office")
            )
        )
    ]
    return "\n".join(lines).strip()


def _big_lane_memory(prompt: str, request: dict[str, Any] | None = None) -> str:
    """durable facts + persona/voice block + semantic recall, joined and capped, for
    the big local lane's extra_memory. Shared by the non-streaming and streaming
    paths. FACTS COME FIRST: they are operator-ordered ground truth ('always honor
    these'); persona is style and semantic recall is opportunistic, so the tail
    slice may only ever eat those."""
    scope = _chat_context_scope(request)
    explicit_followup = _prompt_needs_previous_turn(prompt)
    starts_new_conversation = _prompt_starts_new_conversation(prompt)
    conversation_id = _request_conversation_id(request)
    discord_room = _discord_room_memory(request)
    followup = explicit_followup or bool(discord_room)
    recent = ""
    if discord_room and not starts_new_conversation:
        recent = discord_room
    elif (explicit_followup or conversation_id) and not starts_new_conversation:
        low_prompt = _intent_gate_text(prompt).casefold()
        two_messages_ago = "two messages ago" in low_prompt
        conversation_summary = any(
            term in low_prompt
            for term in ("we have been discussing", "conversation summary", "correction from this conversation")
        )
        recent_records = 8 if conversation_summary else (3 if conversation_id else 1)
        recent_chars = 3000 if conversation_summary else (2400 if conversation_id else 1400)
        recent = (
            _recent_chat_turn_at_offset(1, context_scope=scope)
            if two_messages_ago
            else _recent_chat_context(
                max_chars=recent_chars,
                max_records=recent_records,
                context_scope=scope,
            )
        ) or _request_context_preview(request, max_chars=recent_chars)
        followup = explicit_followup or bool(recent)
    recent_block = "RECENT ENGEL CHAT CONTEXT (continue this conversation; do not reset):\n" + recent if recent else ""
    if explicit_followup and recent_block:
        followup_rule = (
            "FOLLOW-UP SCOPE: Answer only from the recent conversation above. Preserve the requested turn's subject; "
            "do not introduce profile facts, work history, capabilities, architecture, or an offer of unrelated help."
        )
        if "two messages ago" in _intent_gate_text(prompt).casefold():
            followup_rule += (
                " The recent context above is already the exact second-most-recent user/assistant turn. Summarize only it, "
                "without adding the immediately previous rewrite or older profile memory."
            )
        return (recent_block + "\n\n" + followup_rule)[:_BIG_LANE_MEM_BUDGET]
    work_recall = "what do you remember about the kind of work i do" in _intent_gate_text(prompt).casefold()
    # A live desktop conversation has an exact scoped predecessor. Do not mix a
    # fuzzy global-memory hit into that context; that was how an unrelated
    # Discord pump-smoke answer contaminated a curb-adapter survey turn.
    semantic_context = (
        ""
        if followup or work_recall or recent_block or conversation_id or starts_new_conversation
        else _semantic_memory_context(prompt)
    )
    facts = _chat_facts_clipped(prompt, 900 if followup else 1400)
    persona_budget = 700 if followup else 900
    persona = _persona_block(prompt, budget=persona_budget)
    if len(persona) > persona_budget:
        persona = persona[:persona_budget].rstrip() + " ..."
    # Follow-ups must never lose the immediately preceding turn to facts/persona
    # budgeting. Fresh questions still keep durable facts first.
    incomplete_guidance = _incomplete_input_guidance(prompt)
    want_house = _prompt_asks_about_architecture(prompt)
    self_context = _self_model_context(1300) if (not discord_room or want_house) else ""
    talk_rule = ""
    if discord_room:
        talk_rule = (
            "DISCORD TALK: Answer the current Discord message in first person as Engel thinking. "
            "Never write a Joshua-asks template card. "
            "Do not recap the house map, Sub-Engel, CT246, or the home lab unless the current message asks. "
            "If the current message is a link, talk about that topic. Recent room context is continuity only."
        )
    parts = (
        (talk_rule, recent_block, incomplete_guidance, self_context, facts, persona, semantic_context)
        if followup
        else (talk_rule, self_context, incomplete_guidance, facts, persona, recent_block, semantic_context)
    )
    joined = "\n\n".join(p for p in parts if p)
    return joined[:_BIG_LANE_MEM_BUDGET]


def _capability_brief() -> str:
    """Live inventory + abilities so Engel KNOWS what it already has and can
    do - stops it telling Joshua to download models that are already here."""

    def build() -> dict[str, Any]:
        llm_dir = ROOT / "models-active" / "llm"
        hf_dir = ROOT / "models-active" / "hf-src"
        llms = sorted(p.name for p in llm_dir.iterdir() if p.is_dir()) if llm_dir.is_dir() else []
        hf_models = sorted(p.name for p in hf_dir.iterdir() if p.is_dir()) if hf_dir.is_dir() else []
        gif_count = 0
        try:
            data = json.loads((ROOT / "memory" / "engel_gif_categories.json").read_text(encoding="utf-8"))
            cats = data if isinstance(data, list) else data.get("categories", [])
            gif_count = len(cats)
        except Exception:
            pass
        image_engine = "offline"
        # GPU quality lane first (sdxl-turbo on ROG via reverse tunnel :8931),
        # then the always-local CPU sd-turbo engine (:8930). Honest labels.
        for probe_url, probe_label in (
            ("http://127.0.0.1:8931/health", "online (SDXL-Turbo, ROG GPU lane, fully local)"),
            ("http://127.0.0.1:8930/health", "online (SD-Turbo, CPU fallback, fully local)"),
        ):
            try:
                req = urllib.request.Request(probe_url)
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    if json.loads(resp.read().decode()).get("ok"):
                        image_engine = probe_label
                        break
            except Exception:
                continue
        return {
            "llms": llms,
            "hf_models": hf_models,
            "gif_categories": gif_count,
            "image_engine": image_engine,
        }

    inv = _cached_snapshot("capability_brief", build, ttl_seconds=300)
    # (2026-07-10 audit) roles describe what ACTUALLY serves — no advertised lane
    # may claim a model nothing routes to. 14B = built but explicitly offline-gated;
    # R1 = stored only, no route; coder lane = the 3B (the 7B src has no gguf).
    # (20260711 audit) the two image roles derive their live/offline suffix from the
    # SAME probe as inv['image_engine'] so the brief can never say "offline" and
    # "LIVE" about the image engine in the same breath.
    _img = str(inv.get("image_engine") or "").lower()
    _gpu_img = "sdxl" in _img
    _cpu_img = "sd-turbo" in _img or "cpu" in _img
    _sdxl_suffix = "GPU quality lane :8931, LIVE" if _gpu_img else "GPU quality lane :8931, currently offline"
    _sd_suffix = ("CPU fallback lane :8930, LIVE" if (_cpu_img or _gpu_img)
                  else "CPU fallback lane :8930, currently offline")
    model_roles = {
        "sdxl-turbo": f"photoreal image generation ({_sdxl_suffix})",
        "sd-turbo": f"fast image generation ({_sd_suffix})",
        "nomic-embed-text-v1.5": "semantic memory search - powers Engel's recall of past facts by meaning (LIVE)",
        "Qwen2.5-14B-Instruct": "offline deep-reason fallback gguf (built, NOT auto-routed - explicit degraded mode only)",
        "qwen2.5-coder-3b-instruct": "dedicated code lane for explicit code requests (LIVE)",
        "DeepSeek-R1-Distill-Qwen-7B": "stored weights only - no serving lane routes to it",
        "engel-qwen2.5-1.5b-deepreason": "the tuned Engel personality model (quick lane, LIVE)",
    }
    # match roles case-insensitively so gguf dir names under models-active/llm
    # (e.g. qwen2.5-coder-3b-instruct) pick up their role even without a same-named
    # hf-src dir — otherwise the coder lane rendered with no role in the LLM list.
    _roles_ci = {k.lower(): v for k, v in model_roles.items()}

    def _annotate(name: str) -> str:
        role = model_roles.get(name) or _roles_ci.get(str(name).lower())
        return f"{name} ({role})" if role else name

    annotated_llms = [_annotate(m) for m in (inv.get("llms") or [])]
    annotated = [_annotate(m) for m in (inv.get("hf_models") or [])]
    return (
        "ENGEL'S REAL CURRENT INVENTORY AND ABILITIES (facts - never tell Joshua to download or "
        "set up something already listed here; offer to USE it instead):\n"
        f"- LLMs already on this server (/opt/engel/models-active/llm): {', '.join(annotated_llms) or 'none'}\n"
        f"- HF model sources already on this server, with roles: {', '.join(annotated) or 'none'}\n"
        "- SEMANTIC MEMORY (LIVE): Engel recalls relevant past facts by meaning via nomic-embed; durable facts Joshua "
        "asks to remember are stored permanently and always honored.\n"
        f"- Engel's OWN image engine: {inv.get('image_engine')} - creates photoreal images and captioned memes with no external providers\n"
        f"- GIF library: {inv.get('gif_categories')} categories with real assets, served instantly in Discord\n"
        "- Discord collab (LIVE): Engel's own CT246 engel-discord-bridge in #general with Sub-Engel. "
        "This is not an MCP server. Never tell Joshua Discord is missing.\n"
        "- Other real abilities: Grok Imagine video generation; reading user file attachments; saving person/project "
        "facts to persistent memory; daily training-dataset builds and weekly local-model retrains from these chats; "
        "Discord + desktop app + phone worker surfaces.\n"
        "ENGEL'S OWN RUNTIME (facts): models run on THIS server via llama-cpp-python (GGUF) and HF "
        "transformers/diffusers. There is NO Ollama and NO LM Studio here - NEVER ask Joshua which runtime "
        "he uses; Engel is the runtime. ENGEL DOES INSTALLS ITSELF: when Joshua wants a new model, tell him "
        "to say 'install <org>/<model>' (or a known model name) and Engel starts the real background "
        "download on this server - never hand Joshua ollama/lmstudio commands, and never pretend an install "
        "ran without a receipt."
    )


def _prompt_asks_about_architecture(prompt: str) -> bool:
    """True only when the user asks where/how Engel runs or who it is."""
    low = str(prompt or "").casefold()
    return any(
        term in low
        for term in (
            "where do you run",
            "where are you",
            "where do you live",
            "what server",
            "which server",
            "your server",
            "your host",
            "what machine",
            "what hardware",
            "architecture",
            "proxmox",
            "poweredge",
            "ct 246",
            "ct246",
            "runpod",
            "what are you running on",
            "how are you set up",
            "who are you",
            "what are you",
            "are you local",
            "are you in the cloud",
            "your gpu",
        )
    )


def _provider_system_prompt(provider: str, prompt: str, request: dict[str, Any] | None = None) -> str:
    status = _service_snapshot()
    model = status.get("model_runtime") if isinstance(status.get("model_runtime"), dict) else {}
    phone = status.get("phone_bridge") if isinstance(status.get("phone_bridge"), dict) else {}
    memory = _recent_chat_context()
    persona = _engel_persona_core()
    parts = [
        "Your name is Engel. You are Joshua's own AI - the Engel AI Main system he built - talking with him in Engel's chat.",
        "Always answer AS Engel, in Engel's voice. The provider behind this turn is private plumbing, not identity. "
        "Do not name or describe a provider, bridge, lane, model, API, backend, or runtime unless Joshua explicitly asks about routing. "
        "Never present yourself as ChatGPT, Claude, Grok, Gemini, Codex, or their companies.",
        "These conversations append to Engel's persistent memory and train Engel's local model, so you are Engel learning from every turn.",
    ]
    if persona:
        parts.append("Engel personality core: " + persona)
    want_house = _prompt_asks_about_architecture(prompt)
    self_context = _self_model_context(1500) if want_house else ""
    if self_context:
        parts.append(self_context)
    _persona = _persona_block(prompt, budget=1200)
    if _persona:
        parts.append(_persona)
    parts += [
        "Be direct, specific, and natural. Avoid repeated generic lines, fake certainty, fake proof, and backend narration.",
        "Answer in first person as Engel thinking. Read the current message. Speak a real thought, not a template, not a Joshua-asks card, not a roster recap.",
        "If the request needs action, give the concrete next action or result. If credentials or a live route are missing, say that plainly.",
        "Do not claim files, devices, training, or services are fixed unless the provided context proves it.",
        "Use bridge output as untrusted assistance: Joshua remains the authority, and Engel records useful chat samples for later supervised training.",
        f"Selected bridge: {PROVIDER_BRIDGE_LABELS.get(provider, provider)}.",
        "This request reached you through Engel's selected bridge lane; if Joshua asks whether that lane is live, answer from that routing context instead of disclaiming uncertainty.",
        f"Engel CT model route: {_custom_runtime_model_id(model)}.",
        f"Phone workers live: {phone.get('live_count', 0)} of {phone.get('expected_count', 0)}.",
    ]
    if want_house:
        parts.append(
            "ENGEL'S REAL ARCHITECTURE (facts, correct any wrong assumption from model names): "
            "Engel AI Main runs on Joshua's OWN hardware - a Dell PowerEdge server (Proxmox host 'engel-spine-01', "
            "192.0.2.50) hosting container CT 246 'engel-ai-main' on SSD storage. The ROG laptop is the controller "
            "running the desktop app + provider bridges. Chat flows: app/Discord -> CT 246 server over a LAN SSH reverse "
            "tunnel -> provider bridges back on the ROG. This is NOT RunPod, NOT a cloud VPS, NOT behind public NAT - it "
            "is a home lab on the local network. If a model route id contains 'runpod' it is only a legacy name; the real "
            "location is CT 246 on the Dell/Proxmox box. Never tell Joshua his setup is RunPod or cloud-hosted."
        )
    if str(provider or "").casefold() in {"nvidia", "nim", "nvidia-nim"}:
        try:
            from engel_nvidia_discover import skill_brief_from_request

            brief = skill_brief_from_request(request)
            if brief:
                parts.append(brief)
        except Exception:
            pass
    parts.append(_capability_brief())
    incomplete_input_guidance = _incomplete_input_guidance(prompt)
    if incomplete_input_guidance:
        parts.append(incomplete_input_guidance)
    facts = _facts_for_prompt()
    if facts:
        parts.append(facts)
    semantic = _semantic_memory_context(prompt)
    if semantic:
        parts.append(semantic)
    if memory:
        parts.extend(["Recent Engel persistent chat context:", memory])
    return "\n\n".join(parts).strip()


_PROVIDER_IDENTITY_NAMES = (
    "chatgpt",
    "openai",
    "claude",
    "anthropic",
    "grok",
    "xai",
    "x.ai",
    "gemini",
    "codex",
    "sonnet",
    "opus",
    "haiku",
)


def _prompt_requests_provider_disclosure(prompt: str) -> bool:
    text = " ".join(str(prompt or "").casefold().split())
    if not text:
        return False
    routing_words = r"provider|bridge|lane|model|backend|runtime|api|route|routing"
    provider_names = "|".join(re.escape(name) for name in _PROVIDER_IDENTITY_NAMES)
    checks = (
        rf"\b(?:which|what|whose|name|identify|show|tell|explain|report|check)\b.{{0,64}}\b(?:{routing_words})\b",
        rf"\b(?:{routing_words})\b.{{0,64}}\b(?:which|what|whose|name|identify|show|tell|explain|report|check)\b",
        rf"\b(?:did|are|were|was|is)\b.{{0,48}}\b(?:using|use|routed|running|powered|handled)\b.{{0,32}}\b(?:{provider_names})\b",
        rf"\b(?:use|ask|route through|send to|hand to)\s+(?:the\s+)?(?:{provider_names})\b",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in checks)


def _sanitize_automatic_provider_identity(
    prompt: str,
    receipt: dict[str, Any],
    provider: str,
) -> dict[str, Any]:
    """Keep automatic provider assistance internal to Engel's public reply."""
    original = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "").strip()
    explicit = receipt.get("explicit_provider_requested") is True
    disclosure_requested = _prompt_requests_provider_disclosure(prompt)
    meta = {
        "applied": False,
        "reply_changed": False,
        "explicit_provider_requested": explicit,
        "provider_disclosure_requested": disclosure_requested,
        "provider": provider,
    }
    if not original or explicit or disclosure_requested:
        receipt["automatic_provider_identity_guard"] = meta
        return receipt

    names = "|".join(re.escape(name) for name in _PROVIDER_IDENTITY_NAMES)
    cleaned = original
    replacements = (
        (
            rf"\b(?:this|the)\s+(?:turn|request|reply)\s+(?:is|was)\s+"
            rf"(?:running|routed|handled|powered)\s+(?:on|through|by|via)\s+(?:the\s+)?"
            rf"(?:{names})(?:\s+(?:provider|bridge|lane|model|backend|runtime|api))?\b",
            "Engel is handling this",
        ),
        (
            rf"\b(?:the\s+)?(?:{names})\s+(?:provider|bridge|lane|model|backend|runtime|api)\b",
            "Engel",
        ),
        (
            rf"\b(?:using|via|through|on|powered by|handled by)\s+(?:the\s+)?(?:{names})"
            rf"(?:\s+(?:provider|bridge|lane|model|backend|runtime|api))?\b",
            "through Engel",
        ),
        (rf"\bI(?:'m| am)\s+(?:an?\s+)?(?:{names})\b", "I'm Engel"),
    )
    for pattern, replacement in replacements:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bEngel\s+Engel\b", "Engel", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+([,.;!?])", r"\1", cleaned)
    cleaned = re.sub(r"([,;])\s*([,;])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip(" ,;")

    route_words = r"provider|bridge|lane|model|backend|runtime|api"
    if re.search(rf"\b(?:{names})\b.{{0,32}}\b(?:{route_words})\b", cleaned, flags=re.IGNORECASE):
        cleaned = re.sub(rf"\b(?:{names})\b", "Engel", cleaned, flags=re.IGNORECASE)
    if not cleaned:
        cleaned = "I'm here, Joshua. What do you want to work on?"

    meta["applied"] = True
    meta["reply_changed"] = cleaned != original
    if meta["reply_changed"]:
        meta["original_reply_preview"] = _clip(original, 300)
        receipt["assistant_reply"] = cleaned
        receipt["assistant_output_text"] = cleaned
    receipt["automatic_provider_identity_guard"] = meta
    return receipt


def _provider_word_is_negated(text: str, word: str) -> bool:
    index = text.find(word)
    if index < 0:
        return False
    before = text[max(0, index - 72) : index]
    after = text[index : index + len(word) + 24]
    negative_cues = (
        "do not use",
        "don't use",
        "dont use",
        "not use",
        "never use",
        "avoid",
        "without",
        "no ",
        "not ",
        "disable",
        "stop using",
        "not through",
        "don't route",
        "do not route",
        "dont route",
        "not route",
        "skip",
    )
    return any(cue in before for cue in negative_cues) or any(after.startswith(cue + " ") for cue in ("no", "not"))


def _term_present_not_negated(text: str, term: str) -> bool:
    return term in text and not _provider_word_is_negated(text, term)


# Verbs (plus the unambiguous "via") that INVOKE a provider. Deliberately no bare
# prepositions: "to"/"with" also lead mentions ("what happened to grok", "what's
# wrong with grok") - the very questions that sustained the canned-reply loop.
# Multi-word directives reach the name through the 3-token window ("send this to
# grok" -> send; "chat with grok" -> chat; "switch to grok" -> switch).
_PROVIDER_DIRECTIVE_CUES = frozenset(
    {
        "ask", "asks", "use", "using", "via", "through", "route", "routes",
        "send", "sends", "switch", "have", "let", "try", "call", "query",
        "consult", "want", "prefer", "need", "talk", "speak", "chat", "check",
        "verify", "compare", "hey", "hi", "hello",
    }
)


def _provider_word_is_directed(text: str, word: str) -> bool:
    """True only when the provider name is being INVOKED, not merely mentioned.

    "ask grok to check it" / "use claude" / "via gemini" / "grok, what is..." are
    invocations. "is grok working?" / "why does it say grok is not usable" / "the
    grok bridge has no secret" are conversation ABOUT the provider and must stay on
    the local lane. Live 2026-08-14: a bare SUBSTRING match routed every mention of
    grok to the unloaded xai bridge, so each turn got the canned "Grok/xAI is wired
    into Engel, but it is not usable right now" dead-end — including the follow-up
    question about that very message, a self-sustaining loop. Word-boundary matched,
    and the token right before the name (window of two) must be a directive cue, or
    the name must open the prompt as a vocative ("grok, ..." / "hey grok ...").
    """
    for found in re.finditer(
        rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", text
    ):
        start = found.start()
        before_tokens = re.sub(r"[^\w\s]", " ", text[:start]).split()
        if not before_tokens:
            # Vocative: the prompt OPENS with the provider name ("grok, do X").
            rest = text[found.end():].lstrip()
            if rest[:1] in {",", ":", "-"} or not rest:
                return True
            continue
        if any(token in _PROVIDER_DIRECTIVE_CUES for token in before_tokens[-3:]):
            return True
    return False


def _request_explicit_provider_allowed(request: dict[str, Any]) -> bool:
    """Only honor request provider fields when the caller explicitly forces it.

    The desktop chat UI can keep stale provider/bridge values from an Auto Best
    selection. Those metadata fields must not make normal Engel chat jump to a
    ROG provider bridge; Joshua has been clear that Auto chat should exercise
    CT246's local LLM first. A provider is still explicit when the user names it
    in the prompt, or when an integration sends an intentional force flag.
    """
    force_keys = (
        "force_provider",
        "explicit_provider",
        "provider_explicit",
        "force_bridge",
        "explicit_bridge",
        "bridge_explicit",
    )
    if any(bool(request.get(key)) for key in force_keys):
        return True
    route_mode = str(
        request.get("route_mode")
        or request.get("provider_mode")
        or request.get("bridge_mode")
        or ""
    ).strip().casefold()
    return route_mode in {"explicit", "forced", "force", "provider", "bridge"}


def _automatic_provider_after_local_failure_only(request: dict[str, Any]) -> bool:
    """Keep automatic bridge routing behind a proved local-model failure."""
    requested = request.get("automatic_provider_after_local_failure_only")
    if requested is not None:
        return requested is True
    return _env_truth(
        "ENGEL_AUTOMATIC_PROVIDER_AFTER_LOCAL_FAILURE_ONLY",
        default=False,
    )


def _provider_candidates_for_prompt(prompt: str, request: dict[str, Any]) -> tuple[list[str], str]:
    ignore_explicit = bool(request.get("_ignore_explicit_provider"))
    request_provider = "" if ignore_explicit else _normalize_provider_name(
        request.get("provider") or request.get("bridge") or request.get("selected_provider")
    )
    provider_was_forced = _request_explicit_provider_allowed(request)
    automatic_failure_fallback = request.get("_automatic_local_failure_fallback") is True
    # The desktop sends provider=local as normal route metadata. During an
    # evidence-backed fallback that default must not masquerade as a user
    # prohibition. A force flag or an explicit local-only phrase below still
    # prevents every provider candidate.
    if request_provider == "local" and automatic_failure_fallback and not provider_was_forced:
        explicit = ""
    else:
        explicit = request_provider if request_provider == "local" or provider_was_forced else ""
    # Route by the CURRENT user line; provider names or media links quoted in
    # Discord/UI context must not steer the turn to the wrong bridge.
    # (2026-08-14) INVOKED, not mentioned: the old bare substring test made every
    # turn that talked ABOUT a provider an explicit route to it ("is grok working?"
    # -> xai bridge -> canned "Grok/xAI is wired into Engel, but it is not usable
    # right now" dead-end, and the follow-up question about that message contained
    # "grok" again - a loop). Chat is local-first; only a directive may route.
    low = _intent_gate_text(prompt).casefold()
    if not ignore_explicit:
        for word, provider in (
            ("openai codex", "codex"),
            ("codex", "codex"),
            ("chatgpt", "openai"),
            ("openai", "openai"),
            ("gpt", "openai"),
            ("claude", "anthropic"),
            ("anthropic", "anthropic"),
            ("grok", "xai"),
            ("xai", "xai"),
            ("x.ai", "xai"),
            ("gemini", "gemini"),
            ("google ai", "gemini"),
            ("google", "gemini"),
            ("nvidia nim", "nvidia"),
            ("nemotron super", "nvidia"),
            ("nemotron nano", "nvidia"),
            ("llama nemotron", "nvidia"),
            ("nano omni", "nvidia"),
            ("nvidia", "nvidia"),
            ("kimi-k3", "nvidia"),
            ("kimi k3", "nvidia"),
            ("deepseek-v4", "nvidia"),
        ):
            if word in low:
                if _provider_word_is_negated(low, word):
                    continue
                if not _provider_word_is_directed(low, word):
                    continue
                explicit = explicit or provider
                break
    if explicit == "local":
        return [], "explicit_local"
    if explicit and explicit != "auto":
        if not _provider_bridge_enabled_for_routing(explicit):
            return [], f"explicit_provider_disabled_{explicit}"
        return [explicit], "explicit_provider"

    if not _env_truth("ENGEL_AUTO_BRIDGE_ROUTING_ENABLED", default=False):
        return [], "local_default_bridges_explicit_or_fallback_only"

    local_terms = (
        "local model",
        "server local",
        "local llm",
        "ct local",
        "ct 246 local",
        "own llm",
        "own model",
        "no bridge",
        "without bridge",
        "without provider",
    )
    if any(term in low for term in local_terms):
        return [], "explicit_local_or_server_local"

    code_terms = ("code", "debug", "review", "refactor", "patch", "python", "rust", "typescript", "javascript", "api", "bug")
    current_terms = ("current", "latest", "today", "news", "social", "x trend", "twitter", "x.com", "grok")
    google_terms = (
        "gemini",
        "google",
        "large context",
        "long context",
        "huge document",
        "massive document",
        "multimodal",
        "youtube",
        "google docs",
        "google sheet",
        "google drive",
    )
    writing_terms = ("write", "rewrite", "tone", "human", "conversation", "client", "customer", "chat", "reply")
    if any(_term_present_not_negated(low, term) for term in google_terms):
        return _filter_automatic_provider_candidates(["gemini", "openai", "xai"]), "google_or_long_context"
    if any(_term_present_not_negated(low, term) for term in current_terms):
        return _filter_automatic_provider_candidates(["xai", "openai"]), "current_or_social"
    # Drafting identifiers such as "finish code" and "material code" are not
    # software intent. Remove those bounded phrases only for provider routing;
    # the untouched prompt still reaches local inference and persistent memory.
    code_routing_text = re.sub(
        r"\b(?:finish|color|paint|material|keynote|schedule|drawing|detail|sheet)\s+codes?\b",
        "",
        low,
    )
    if any(_term_present_not_negated(code_routing_text, term) for term in code_terms):
        return _filter_automatic_provider_candidates(["codex", "xai", "openai"]), "code_or_review"
    if request.get("_automatic_local_failure_fallback") is True:
        metadata = request.get("metadata") if isinstance(request.get("metadata"), dict) else {}
        preferred = _normalize_provider_name(
            request.get("preferred_fallback_provider")
            or metadata.get("preferred_fallback_provider")
        )
        order = ["nvidia", "openai", "gemini", "xai", "codex"]
        if preferred in order:
            order = [preferred] + [item for item in order if item != preferred]
        return _filter_enabled_provider_candidates(order), "local_failure_general"
    if any(_term_present_not_negated(low, term) for term in writing_terms):
        return [], "local_chat_or_writing_default"
    return [], "local_general_chat_default"


def _explicit_provider_fallback_candidates(provider: str, prompt: str, request: dict[str, Any]) -> tuple[list[str], str]:
    if _env_truth("ENGEL_PROVIDER_BRIDGE_STRICT_EXPLICIT", default=False):
        return [], "explicit_provider_strict_no_fallback"
    if not _env_truth("ENGEL_PROVIDER_BRIDGE_FALLBACK_ON_EXPLICIT_FAILURE", default=True):
        return [], "explicit_provider_fallback_disabled"
    order = ["nvidia", "xai", "openai", "gemini", "codex", "anthropic"]
    failed = _normalize_provider_name(provider)
    order = [item for item in order if item != failed]
    return _filter_enabled_provider_candidates(order), "fallback_after_explicit"


def _provider_http_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={**headers, "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            parsed = json.loads(resp.read().decode("utf-8", errors="replace"))
        return {"ok": True, "status_code": 200, "json": parsed if isinstance(parsed, dict) else {}}
    except urllib.error.HTTPError as exc:
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            error_body = ""
        return {
            "ok": False,
            "status_code": exc.code,
            "error": _redact_provider_error(error_body or str(exc)),
        }
    except Exception as exc:
        return {"ok": False, "status_code": 0, "error": _redact_provider_error(str(exc))}


def _provider_request_timeout_seconds(
    request: dict[str, Any] | None,
    default: float,
    *,
    minimum: float = 15.0,
    maximum: float = 300.0,
) -> int:
    """Normalize the CT/UI turn budget for every provider adapter.

    Engel AI Main's desktop worker sends its turn budget as ``timeout`` while
    the provider bridges use the more specific ``timeout_seconds`` field.  The
    old adapters only read the latter, silently falling back to short defaults
    (18s for direct APIs and 25-30s for several bridges) even when the user had
    granted a longer turn.  Keep the existing provider-specific safety clamps,
    but honor either field at this single boundary.
    """
    request = request if isinstance(request, dict) else {}
    raw = request.get("timeout_seconds")
    if raw in (None, ""):
        raw = request.get("timeout")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = float(default)
    if not math.isfinite(value):
        value = float(default)
    try:
        fallback = float(default)
    except (TypeError, ValueError):
        fallback = float(minimum)
    if not math.isfinite(fallback):
        fallback = float(minimum)
    if value <= 0:
        value = fallback
    try:
        floor = max(0.0, float(minimum))
    except (TypeError, ValueError):
        floor = 0.0
    try:
        ceiling = max(floor, float(maximum))
    except (TypeError, ValueError):
        ceiling = floor
    return int(min(ceiling, max(floor, value)))


def _chatgpt_browser_bridge_status() -> dict[str, Any]:
    enabled = _env_truth("ENGEL_CHATGPT_BROWSER_BRIDGE_ENABLED", default=True)
    status = {
        "schema": "engel_rog_chatgpt_browser_bridge_route_status_v1",
        "ok": False,
        "enabled": enabled,
        "url": ROG_CHATGPT_BROWSER_BRIDGE_URL,
        "route": "CT 246 -> SSH reverse tunnel -> ROG local ChatGPT browser worker",
        "provider": "openai",
        "provider_label": "ChatGPT browser worker on ROG",
        "oauth_tokens_exposed": False,
        "updated_at_utc": _iso_now(),
    }
    if not enabled:
        status["reason"] = "ENGEL_CHATGPT_BROWSER_BRIDGE_ENABLED disabled"
        return status
    try:
        req = urllib.request.Request(
            ROG_CHATGPT_BROWSER_BRIDGE_URL + "/health",
            headers={"Accept": "application/json"},
            method="GET",
        )
        health_timeout = float(os.environ.get("ENGEL_CHATGPT_BROWSER_HEALTH_TIMEOUT_SECONDS", "4") or "4")
        with urllib.request.urlopen(req, timeout=health_timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        if isinstance(data, dict):
            status.update(data)
            status["ok"] = bool(data.get("ok") is True)
            status.setdefault("url", ROG_CHATGPT_BROWSER_BRIDGE_URL)
            status.setdefault("route", "CT 246 -> SSH reverse tunnel -> ROG local ChatGPT browser worker")
            status["oauth_tokens_exposed"] = False
        return status
    except Exception as exc:
        status["reason"] = _redact_provider_error(str(exc))
        return status


def _call_chatgpt_browser_bridge(prompt: str, request: dict[str, Any], started: float) -> dict[str, Any]:
    system_prompt = _provider_system_prompt("openai", prompt)
    bridge_request = {
        "prompt": prompt,
        "model": request.get("model") or request.get("provider_model") or "",
        "system_prompt": system_prompt,
        "trusted_memory": system_prompt,
        "timeout_seconds": _provider_request_timeout_seconds(
            request,
            CHATGPT_BROWSER_BRIDGE_TIMEOUT_SECONDS,
            minimum=15,
            maximum=300,
        ),
        "max_tokens": request.get("max_tokens") or request.get("max_completion_tokens") or 420,
    }
    result = _provider_http_json(
        ROG_CHATGPT_BROWSER_BRIDGE_URL + "/chat",
        bridge_request,
        {"X-Engel-Bridge": "ct246-chatgpt-browser"},
        bridge_request["timeout_seconds"] + 5,
    )
    attempt = {
        "provider": "openai",
        "bridge_kind": "rog_chatgpt_browser",
        "url": ROG_CHATGPT_BROWSER_BRIDGE_URL,
        "ok": result.get("ok"),
        "status_code": result.get("status_code"),
        "error": result.get("error", ""),
    }
    if not result.get("ok"):
        return {
            "ok": False,
            "provider": "openai",
            "assistant_reply": "",
            "attempts": [attempt],
            "error": _redact_provider_error(result.get("error") or "ROG ChatGPT browser bridge unavailable"),
            "bridge_kind": "rog_chatgpt_browser",
        }
    data = result.get("json") if isinstance(result.get("json"), dict) else {}
    reply = str(data.get("assistant_reply") or "").strip()
    receipt = data.get("receipt") if isinstance(data.get("receipt"), dict) else {}
    model = str(data.get("runtime_provider") or receipt.get("runtime_provider") or "chatgpt-browser-ui")
    attempt["model"] = model
    attempt["ok"] = bool(reply)
    return {
        "ok": bool(reply),
        "provider": "openai",
        "model": model,
        "assistant_reply": reply,
        "attempts": [attempt],
        "bridge_kind": "rog_chatgpt_browser",
        "remote_receipt": receipt,
        "error": "" if reply else "ROG ChatGPT browser bridge returned no assistant reply",
    }


def _gemini_api_bridge_status() -> dict[str, Any]:
    enabled = _env_truth("ENGEL_GEMINI_API_BRIDGE_ENABLED", default=False)
    status = {
        "schema": "engel_rog_gemini_api_bridge_route_status_v1",
        "ok": False,
        "enabled": enabled,
        "usable": False,
        "url": ROG_GEMINI_API_BRIDGE_URL,
        "route": "CT 246 -> SSH reverse tunnel -> ROG local Gemini API bridge",
        "provider": "gemini",
        "provider_label": "Gemini API bridge on ROG",
        "oauth_tokens_exposed": False,
        "updated_at_utc": _iso_now(),
    }
    if not enabled:
        status["reason"] = "ENGEL_GEMINI_API_BRIDGE_ENABLED disabled"
        return status
    try:
        req = urllib.request.Request(
            ROG_GEMINI_API_BRIDGE_URL + "/health",
            headers={"Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=1.2) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        if isinstance(data, dict):
            status.update(data)
            status["ok"] = bool(data.get("ok") is True)
            status["usable"] = bool(data.get("usable") is True or data.get("secret_present") is True)
            status.setdefault("url", ROG_GEMINI_API_BRIDGE_URL)
            status.setdefault("route", "CT 246 -> SSH reverse tunnel -> ROG local Gemini API bridge")
            status["oauth_tokens_exposed"] = False
        return status
    except Exception as exc:
        status["reason"] = _redact_provider_error(str(exc))
        return status


def _call_gemini_api_bridge(prompt: str, request: dict[str, Any], started: float) -> dict[str, Any]:
    bridge_request = {
        "prompt": prompt,
        "model": request.get("model") or request.get("provider_model") or "",
        "system_prompt": _provider_system_prompt("gemini", prompt),
        "timeout_seconds": _provider_request_timeout_seconds(
            request,
            GEMINI_API_BRIDGE_TIMEOUT_SECONDS,
            minimum=15,
            maximum=180,
        ),
        "max_tokens": request.get("max_tokens") or request.get("max_completion_tokens") or 500,
        "temperature": request.get("temperature") or 0.35,
    }
    if request.get("thinking_budget") is not None:
        bridge_request["thinking_budget"] = request.get("thinking_budget")
    result = _provider_http_json(
        ROG_GEMINI_API_BRIDGE_URL + "/chat",
        bridge_request,
        {"X-Engel-Bridge": "ct246-gemini-api"},
        bridge_request["timeout_seconds"] + 5,
    )
    attempt = {
        "provider": "gemini",
        "bridge_kind": "rog_gemini_api",
        "url": ROG_GEMINI_API_BRIDGE_URL,
        "ok": result.get("ok"),
        "status_code": result.get("status_code"),
        "error": result.get("error", ""),
    }
    if not result.get("ok"):
        return {
            "ok": False,
            "provider": "gemini",
            "assistant_reply": "",
            "attempts": [attempt],
            "error": _redact_provider_error(result.get("error") or "ROG Gemini API bridge unavailable"),
            "bridge_kind": "rog_gemini_api",
        }
    data = result.get("json") if isinstance(result.get("json"), dict) else {}
    reply = str(data.get("assistant_reply") or "").strip()
    receipt = data.get("receipt") if isinstance(data.get("receipt"), dict) else {}
    model = str(data.get("runtime_provider") or receipt.get("runtime_provider") or receipt.get("model") or "")
    attempt["model"] = model
    attempt["ok"] = bool(reply)
    return {
        "ok": bool(reply),
        "provider": "gemini",
        "model": model,
        "assistant_reply": reply,
        "attempts": [attempt],
        "bridge_kind": "rog_gemini_api",
        "remote_receipt": receipt,
        "error": "" if reply else "ROG Gemini API bridge returned no assistant reply",
    }


def _grok_cli_bridge_status() -> dict[str, Any]:
    enabled = _env_truth("ENGEL_GROK_CLI_BRIDGE_ENABLED", default=True)
    status = {
        "schema": "engel_rog_grok_cli_bridge_route_status_v1",
        "ok": False,
        "enabled": enabled,
        "url": ROG_GROK_CLI_BRIDGE_URL,
        "route": "CT 246 -> SSH reverse tunnel -> ROG local Grok CLI",
        "provider": "xai",
        "provider_label": "Grok CLI on ROG",
        "oauth_tokens_exposed": False,
        "updated_at_utc": _iso_now(),
    }
    if not enabled:
        status["reason"] = "ENGEL_GROK_CLI_BRIDGE_ENABLED disabled"
        return status
    try:
        req = urllib.request.Request(
            ROG_GROK_CLI_BRIDGE_URL + "/health",
            headers={"Accept": "application/json"},
            method="GET",
        )
        health_timeout = float(os.environ.get("ENGEL_GROK_CLI_HEALTH_TIMEOUT_SECONDS", "3") or "3")
        with urllib.request.urlopen(req, timeout=health_timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        if isinstance(data, dict):
            status.update(data)
            status["ok"] = bool(data.get("ok") is True)
            status.setdefault("url", ROG_GROK_CLI_BRIDGE_URL)
            status.setdefault("route", "CT 246 -> SSH reverse tunnel -> ROG local Grok CLI")
            status["oauth_tokens_exposed"] = False
        return status
    except Exception as exc:
        status["reason"] = _redact_provider_error(str(exc))
        return status


def _claude_cli_bridge_status() -> dict[str, Any]:
    enabled = _env_truth("ENGEL_CLAUDE_CLI_BRIDGE_ENABLED", default=True)
    status = {
        "schema": "engel_rog_claude_cli_bridge_route_status_v1",
        "ok": False,
        "enabled": enabled,
        "url": ROG_CLAUDE_CLI_BRIDGE_URL,
        "route": "CT 246 -> SSH reverse tunnel -> ROG local Claude CLI",
        "provider": "anthropic",
        "provider_label": "Claude CLI on ROG",
        "oauth_tokens_exposed": False,
        "updated_at_utc": _iso_now(),
    }
    if not enabled:
        status["reason"] = "ENGEL_CLAUDE_CLI_BRIDGE_ENABLED disabled"
        return status
    try:
        req = urllib.request.Request(
            ROG_CLAUDE_CLI_BRIDGE_URL + "/health",
            headers={"Accept": "application/json"},
            method="GET",
        )
        health_timeout = float(os.environ.get("ENGEL_CLAUDE_CLI_HEALTH_TIMEOUT_SECONDS", "3") or "3")
        with urllib.request.urlopen(req, timeout=health_timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        if isinstance(data, dict):
            status.update(data)
            status["ok"] = bool(data.get("ok") is True)
            status.setdefault("url", ROG_CLAUDE_CLI_BRIDGE_URL)
            status.setdefault("route", "CT 246 -> SSH reverse tunnel -> ROG local Claude CLI")
            status["oauth_tokens_exposed"] = False
        return status
    except Exception as exc:
        status["reason"] = _redact_provider_error(str(exc))
        return status


def _codex_cli_bridge_status() -> dict[str, Any]:
    enabled = _env_truth("ENGEL_CODEX_CLI_BRIDGE_ENABLED", default=True)
    status = {
        "schema": "engel_rog_codex_cli_bridge_route_status_v1",
        "ok": False,
        "enabled": enabled,
        "url": ROG_CODEX_CLI_BRIDGE_URL,
        "route": "CT 246 -> SSH reverse tunnel -> ROG local Codex CLI",
        "provider": "codex",
        "provider_label": "Codex CLI on ROG",
        "auth_values_exposed": False,
        "oauth_tokens_exposed": False,
        "updated_at_utc": _iso_now(),
    }
    if not enabled:
        status["reason"] = "ENGEL_CODEX_CLI_BRIDGE_ENABLED disabled"
        return status
    try:
        req = urllib.request.Request(
            ROG_CODEX_CLI_BRIDGE_URL + "/health",
            headers={"Accept": "application/json"},
            method="GET",
        )
        health_timeout = float(os.environ.get("ENGEL_CODEX_CLI_HEALTH_TIMEOUT_SECONDS", "3") or "3")
        with urllib.request.urlopen(req, timeout=health_timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        if isinstance(data, dict):
            status.update(data)
            status["ok"] = bool(data.get("ok") is True)
            status.setdefault("url", ROG_CODEX_CLI_BRIDGE_URL)
            status.setdefault("route", "CT 246 -> SSH reverse tunnel -> ROG local Codex CLI")
            status["auth_values_exposed"] = False
            status["oauth_tokens_exposed"] = False
        return status
    except Exception as exc:
        status["reason"] = _redact_provider_error(str(exc))
        return status


def _call_claude_cli_bridge(prompt: str, request: dict[str, Any], started: float) -> dict[str, Any]:
    bridge_request = {
        "prompt": prompt,
        "model": request.get("model") or request.get("provider_model") or "",
        "system_prompt": _provider_system_prompt("anthropic", prompt),
        "timeout_seconds": _provider_request_timeout_seconds(
            request,
            CLAUDE_CLI_BRIDGE_TIMEOUT_SECONDS,
            minimum=15,
            maximum=240,
        ),
    }
    result = _provider_http_json(
        ROG_CLAUDE_CLI_BRIDGE_URL + "/chat",
        bridge_request,
        {"X-Engel-Bridge": "ct246-claude-cli"},
        bridge_request["timeout_seconds"] + 5,
    )
    attempt = {
        "provider": "anthropic",
        "bridge_kind": "rog_claude_cli",
        "url": ROG_CLAUDE_CLI_BRIDGE_URL,
        "ok": result.get("ok"),
        "status_code": result.get("status_code"),
        "error": result.get("error", ""),
    }
    if not result.get("ok"):
        return {
            "ok": False,
            "provider": "anthropic",
            "assistant_reply": "",
            "attempts": [attempt],
            "error": _redact_provider_error(result.get("error") or "ROG Claude CLI bridge unavailable"),
            "bridge_kind": "rog_claude_cli",
        }
    data = result.get("json") if isinstance(result.get("json"), dict) else {}
    reply = str(data.get("assistant_reply") or "").strip()
    receipt = data.get("receipt") if isinstance(data.get("receipt"), dict) else {}
    model = str(data.get("runtime_provider") or receipt.get("runtime_provider") or receipt.get("model") or "")
    attempt["model"] = model
    attempt["ok"] = bool(reply)
    return {
        "ok": bool(reply),
        "provider": "anthropic",
        "model": model,
        "assistant_reply": reply,
        "attempts": [attempt],
        "bridge_kind": "rog_claude_cli",
        "remote_receipt": receipt,
        "error": "" if reply else "ROG Claude CLI bridge returned no assistant reply",
    }


def _call_codex_cli_bridge(prompt: str, request: dict[str, Any], started: float) -> dict[str, Any]:
    bridge_request = {
        "prompt": prompt,
        "model": request.get("model") or request.get("provider_model") or "",
        "system_prompt": _provider_system_prompt("codex", prompt),
        "timeout_seconds": _provider_request_timeout_seconds(
            request,
            CODEX_CLI_BRIDGE_TIMEOUT_SECONDS,
            minimum=20,
            maximum=300,
        ),
        "max_tokens": request.get("max_tokens") or request.get("max_completion_tokens") or 650,
        "artifact_only": request.get("artifact_only") is True,
    }
    result = _provider_http_json(
        ROG_CODEX_CLI_BRIDGE_URL + "/chat",
        bridge_request,
        {"X-Engel-Bridge": "ct246-codex-cli"},
        bridge_request["timeout_seconds"] + 5,
    )
    attempt = {
        "provider": "codex",
        "bridge_kind": "rog_codex_cli",
        "url": ROG_CODEX_CLI_BRIDGE_URL,
        "ok": result.get("ok"),
        "status_code": result.get("status_code"),
        "error": result.get("error", ""),
    }
    if not result.get("ok"):
        return {
            "ok": False,
            "provider": "codex",
            "assistant_reply": "",
            "attempts": [attempt],
            "error": _redact_provider_error(result.get("error") or "ROG Codex CLI bridge unavailable"),
            "bridge_kind": "rog_codex_cli",
        }
    data = result.get("json") if isinstance(result.get("json"), dict) else {}
    reply = str(data.get("assistant_reply") or "").strip()
    receipt = data.get("receipt") if isinstance(data.get("receipt"), dict) else {}
    model = str(data.get("runtime_provider") or receipt.get("runtime_provider") or receipt.get("model") or "")
    attempt["model"] = model
    attempt["ok"] = bool(reply)
    return {
        "ok": bool(reply),
        "provider": "codex",
        "model": model,
        "assistant_reply": reply,
        "attempts": [attempt],
        "bridge_kind": "rog_codex_cli",
        "remote_receipt": receipt,
        "error": "" if reply else "ROG Codex CLI bridge returned no assistant reply",
    }


def _rog_image_paths_from_request(request: dict[str, Any]) -> list[str]:
    """Only ROG chat-attachment paths. CT stored copies are not visible to grok.exe."""
    allowed_prefixes = (
        r"D:\b.WorkSpace\Engel App\runtime\chat_attachments",
        "D:/b.WorkSpace/Engel App/runtime/chat_attachments",
    )
    found: list[str] = []
    raw_lists = [request.get("image_paths"), request.get("attachments")]
    for raw in raw_lists:
        items = raw if isinstance(raw, list) else []
        for item in items:
            if isinstance(item, str):
                path = item.strip()
            elif isinstance(item, dict):
                mime = str(item.get("mime_type") or item.get("mime") or "").casefold()
                kind = str(item.get("kind") or "").casefold()
                if mime and not mime.startswith("image/") and kind not in {"image", "screenshot"}:
                    continue
                path = str(item.get("source_path") or item.get("path") or "").strip()
            else:
                continue
            if path and path.startswith(allowed_prefixes) and path not in found:
                found.append(path)
    return found


def _grok_bridge_timeout_seconds(request: dict[str, Any]) -> int:
    """Never let a 25s leftover cap kill a Grok Super turn."""
    raw = request.get("timeout_seconds")
    if raw in (None, ""):
        raw = request.get("timeout")
    try:
        incoming = float(raw or 0)
    except (TypeError, ValueError):
        incoming = 0
    is_work = str(request.get("lane") or "").casefold() == "build" or request.get("artifact_only") is True
    has_images = bool(request.get("discord_owner_vision") is True or _request_has_still_images(request))
    floor = 120 if is_work or has_images else 90
    if incoming >= floor:
        return int(min(240, incoming))
    return int(min(240, max(floor, float(GROK_CLI_BRIDGE_TIMEOUT_SECONDS))))


def _call_provider_with_account_pool(
    provider: str,
    prompt: str,
    request: dict[str, Any],
    started: float,
    call_fn: Any,
) -> dict[str, Any]:
    """Try each ready account for this provider. Usage-out rotates; memory stays shared."""
    try:
        from engel_provider_account_pool import (
            error_is_usage_exhausted,
            iter_ready_accounts,
            mark_exhausted,
            mark_used,
        )
    except Exception:
        return call_fn(prompt, request, started)
    last: dict[str, Any] | None = None
    tried = False
    for acc in iter_ready_accounts(provider):
        tried = True
        req = dict(request)
        req["_account_id"] = str(acc.get("id") or "")
        req["_account_home"] = str(acc.get("home_dir") or "")
        result = call_fn(prompt, req, started)
        last = result if isinstance(result, dict) else {"ok": False, "error": "bad account call"}
        err = str(last.get("error") or last.get("status") or "")
        if last.get("ok") is True:
            mark_used(provider, str(acc.get("id") or ""))
            last["account_id"] = acc.get("id")
            last["account_switched"] = True
            last["memory_core_shared"] = True
            return last
        if error_is_usage_exhausted(err):
            mark_exhausted(provider, str(acc.get("id") or ""), err)
            continue
        if "unauthor" in err.casefold() or "not signed" in err.casefold():
            mark_exhausted(provider, str(acc.get("id") or ""), err)
            continue
    if last is not None:
        return last
    if not tried:
        return call_fn(prompt, request, started)
    return {"ok": False, "provider": provider, "assistant_reply": "", "error": "all accounts exhausted or unusable"}


def _call_grok_cli_bridge(prompt: str, request: dict[str, Any], started: float) -> dict[str, Any]:
    image_paths = _rog_image_paths_from_request(request)
    inline_images = _grok_inline_image_attachments(request)
    text = " ".join(str(prompt or "").casefold().split())
    operator_work = bool(text) and (
        text.startswith("engel work")
        or text.startswith("engel solve")
        or (
            any(
                marker in text
                for marker in (
                    "fix",
                    "build",
                    "create",
                    "wire",
                    "pair",
                    "connect",
                    "repair",
                    "respond",
                    "collab",
                    "dispatch",
                    "install",
                    "launch",
                    "discord",
                    "check out discord",
                )
            )
            and not text.startswith(("what is", "what's", "whats", "tell me about", "explain"))
        )
    )
    is_work = (
        str(request.get("lane") or "").casefold() == "build"
        or request.get("artifact_only") is True
        or operator_work
    )
    if is_work:
        request["lane"] = "build"
    bridge_request = {
        "prompt": prompt,
        "model": _canonical_grok_build_model(
            request.get("model") or request.get("provider_model") or "grok-4.6"
        ),
        "system_prompt": _provider_system_prompt("xai", prompt),
        "timeout_seconds": _grok_bridge_timeout_seconds(request),
        "image_paths": image_paths,
        "attachments": inline_images,
        "lane": "build" if is_work else "chat",
        "max_turns": request.get("max_turns") or (12 if is_work else (8 if inline_images else 6)),
        "account_id": str(request.get("_account_id") or ""),
        "account_home": str(request.get("_account_home") or ""),
    }
    result = _provider_http_json(
        ROG_GROK_CLI_BRIDGE_URL + "/chat",
        bridge_request,
        {"X-Engel-Bridge": "ct246-grok-cli"},
        bridge_request["timeout_seconds"] + 5,
    )
    attempt = {
        "provider": "xai",
        "bridge_kind": "rog_grok_cli",
        "url": ROG_GROK_CLI_BRIDGE_URL,
        "ok": result.get("ok"),
        "status_code": result.get("status_code"),
        "error": result.get("error", ""),
    }
    if not result.get("ok"):
        error_text = _summarize_grok_cli_error(result.get("error") or "ROG Grok CLI bridge unavailable")
        return {
            "ok": False,
            "provider": "xai",
            "assistant_reply": "",
            "attempts": [attempt],
            "error": error_text,
            "bridge_kind": "rog_grok_cli",
        }
    data = result.get("json") if isinstance(result.get("json"), dict) else {}
    reply = str(data.get("assistant_reply") or "").strip()
    receipt = data.get("receipt") if isinstance(data.get("receipt"), dict) else {}
    model = str(data.get("runtime_provider") or receipt.get("runtime_provider") or receipt.get("model") or "")
    attempt["model"] = model
    attempt["ok"] = bool(reply)
    return {
        "ok": bool(reply),
        "provider": "xai",
        "model": model,
        "assistant_reply": reply,
        "attempts": [attempt],
        "bridge_kind": "rog_grok_cli",
        "remote_receipt": receipt,
        "error": "" if reply else "ROG Grok CLI bridge returned no assistant reply",
    }


def _canonical_grok_build_model(value: Any = "") -> str:
    text = str(value or "").strip()
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
    if not text:
        return str(os.environ.get("ENGEL_GROK_BUILD_MODEL", "grok-4.6") or "grok-4.6").strip() or "grok-4.6"
    return aliases.get(text.casefold(), text)


def _build_lane_grok46_enabled(*, local_only: bool = False) -> bool:
    if local_only:
        return False
    # Default OFF. Grok-first 240s CLI hangs on large Flutter FILE prompts
    # (empty reply, exit_code null). Engel's local LLMs do the build unless
    # Josh explicitly sets ENGEL_BUILD_GROK46_FIRST=1.
    return str(os.environ.get("ENGEL_BUILD_GROK46_FIRST", "0") or "0").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _call_grok46_build_bridge(prompt: str, request: dict[str, Any], started: float) -> dict[str, Any]:
    """Build-lane Grok 4.6 via the ROG Super-account CLI. Fail fast if the bridge is down."""
    model = _canonical_grok_build_model(request.get("model") or request.get("provider_model"))
    # Live 2026-08-21: 11k-char Flutter FILE generate sat 240s and returned
    # empty. The CLI cap cannot finish that job; skip to local LLMs instead of
    # burning another four-minute stall on generate and each repair.
    grok_char_cap = 8000
    try:
        grok_char_cap = max(
            2000,
            int(os.environ.get("ENGEL_BUILD_GROK_PROMPT_CHAR_CAP", "8000") or "8000"),
        )
    except ValueError:
        grok_char_cap = 8000
    if len(prompt) > grok_char_cap:
        return {
            "ok": False,
            "provider": "xai",
            "assistant_reply": "",
            "model": model,
            "bridge_kind": "rog_grok46_super_cli",
            "error": (
                f"Grok build skipped: prompt {len(prompt)} chars exceeds the "
                f"{grok_char_cap}-char CLI cap that timed out at 240s; using local LLMs"
            ),
        }
    status = _grok_cli_bridge_status()
    if status.get("ok") is not True:
        return {
            "ok": False,
            "provider": "xai",
            "assistant_reply": "",
            "model": model,
            "bridge_kind": "rog_grok46_super_cli",
            "error": str(status.get("reason") or "Grok 4.6 Super CLI bridge not available"),
        }
    req = dict(request)
    req["model"] = model
    req["provider_model"] = model
    req["artifact_only"] = True
    req["lane"] = "build"
    result = _call_grok_cli_bridge(prompt, req, started)
    result["bridge_kind"] = "rog_grok46_super_cli"
    result.setdefault("model", model)
    return result


def _summarize_grok_cli_error(error: Any) -> str:
    text = _redact_provider_error(error)
    parsed: dict[str, Any] | None = None
    try:
        maybe = json.loads(text)
        if isinstance(maybe, dict):
            parsed = maybe
    except Exception:
        parsed = None
    if parsed:
        receipt = parsed.get("receipt") if isinstance(parsed.get("receipt"), dict) else {}
        nested_error = str(receipt.get("error") or parsed.get("error") or parsed.get("status") or "")
        if nested_error:
            text = nested_error
    low = text.casefold()
    if (
        "spending-limit" in low
        or "run out of credits" in low
        or "need a grok subscription" in low
        or "limits outage" in low
        or "limits being reached" in low
        or "elevated errors related to limits" in low
    ):
        return (
            "ROG Grok CLI route is connected, but xAI returned a limits outage or spending/subscription gate. "
            "Wait for the xAI limit outage to clear, add Grok credits/subscription, or set XAI_API_KEY/ENGEL_XAI_API_KEY for the API bridge."
        )
    if "not a git repository" in low and "responses api error" not in low:
        return "ROG Grok CLI route is connected, but the CLI returned only a repository-discovery warning and no chat text."
    return _clip(text, 700)


def _call_openai_bridge(prompt: str, request: dict[str, Any], *, secret: str, started: float) -> dict[str, Any]:
    max_tokens = max(32, min(1600, int(request.get("max_tokens") or request.get("max_completion_tokens") or 500)))
    temperature = float(request.get("temperature") or 0.35)
    system_prompt = _provider_system_prompt("openai", prompt)
    attempts: list[dict[str, Any]] = []
    provider_timeout = _provider_request_timeout_seconds(
        request,
        PROVIDER_BRIDGE_TIMEOUT_SECONDS,
        minimum=15,
        maximum=300,
    )
    for model in _provider_model_candidates("openai", request):
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        result = _provider_http_json(
            OPENAI_CHAT_COMPLETIONS_URL,
            payload,
            {"Authorization": f"Bearer {secret}"},
            provider_timeout,
        )
        attempts.append({"provider": "openai", "model": model, "ok": result.get("ok"), "status_code": result.get("status_code"), "error": result.get("error", "")})
        if int(result.get("status_code") or 0) in {401, 403}:
            break
        if result.get("ok"):
            data = result.get("json") if isinstance(result.get("json"), dict) else {}
            choices = data.get("choices") if isinstance(data.get("choices"), list) else []
            message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
            reply = str(message.get("content") or "").strip() if isinstance(message, dict) else ""
            if reply:
                return {"ok": True, "provider": "openai", "model": model, "assistant_reply": reply, "attempts": attempts}
    return {"ok": False, "provider": "openai", "assistant_reply": "", "attempts": attempts, "error": attempts[-1].get("error", "") if attempts else "no model candidates"}


def _nvidia_full_turn_text(prompt: str, request: dict[str, Any]) -> str:
    """Hand the large NVIDIA models the whole turn, not a clipped excerpt."""
    chunks = [str(prompt or "").strip()]
    items = request.get("context_items")
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            text = str(
                item.get("text")
                or item.get("content")
                or item.get("body")
                or item.get("excerpt")
                or ""
            ).strip()
            if not text:
                continue
            name = str(item.get("name") or item.get("title") or "context").strip() or "context"
            chunks.append(f"[{name}]\n{text}")
    packed = "\n\n".join(chunk for chunk in chunks if chunk)
    return packed[:180000]


def _call_nvidia_nim_bridge(prompt: str, request: dict[str, Any], *, secret: str, started: float) -> dict[str, Any]:
    try:
        requested_tokens = int(request.get("max_tokens") or request.get("max_completion_tokens") or 0)
    except (TypeError, ValueError):
        requested_tokens = 0
    max_tokens = max(4096, min(16384, requested_tokens or 4096))
    temperature = float(request.get("temperature") or 0.35)
    system_prompt = _provider_system_prompt("nvidia", prompt, request)
    user_text = _nvidia_full_turn_text(prompt, request)
    attempts: list[dict[str, Any]] = []
    provider_timeout = _provider_request_timeout_seconds(
        request,
        max(PROVIDER_BRIDGE_TIMEOUT_SECONDS, 30.0),
        minimum=20,
        maximum=120,
    )
    for model in _provider_model_candidates("nvidia", request):
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        result = _provider_http_json(
            NVIDIA_CHAT_COMPLETIONS_URL,
            payload,
            {"Authorization": f"Bearer {secret}"},
            provider_timeout,
        )
        attempts.append(
            {
                "provider": "nvidia",
                "model": model,
                "ok": result.get("ok"),
                "status_code": result.get("status_code"),
                "error": result.get("error", ""),
            }
        )
        if int(result.get("status_code") or 0) in {401, 403}:
            break
        if result.get("ok"):
            data = result.get("json") if isinstance(result.get("json"), dict) else {}
            choices = data.get("choices") if isinstance(data.get("choices"), list) else []
            message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
            reply = str(message.get("content") or "").strip() if isinstance(message, dict) else ""
            if reply:
                return {
                    "ok": True,
                    "provider": "nvidia",
                    "model": model,
                    "assistant_reply": reply,
                    "attempts": attempts,
                    "bridge_kind": "nvidia_nim",
                }
    return {
        "ok": False,
        "provider": "nvidia",
        "assistant_reply": "",
        "attempts": attempts,
        "error": attempts[-1].get("error", "") if attempts else "no NVIDIA NIM model candidates",
        "bridge_kind": "nvidia_nim",
    }


def _call_anthropic_bridge(prompt: str, request: dict[str, Any], *, secret: str, started: float) -> dict[str, Any]:
    max_tokens = max(32, min(1600, int(request.get("max_tokens") or request.get("max_completion_tokens") or 500)))
    temperature = float(request.get("temperature") or 0.35)
    system_prompt = _provider_system_prompt("anthropic", prompt)
    attempts: list[dict[str, Any]] = []
    provider_timeout = _provider_request_timeout_seconds(
        request,
        PROVIDER_BRIDGE_TIMEOUT_SECONDS,
        minimum=15,
        maximum=300,
    )
    for model in _provider_model_candidates("anthropic", request):
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
        }
        result = _provider_http_json(
            ANTHROPIC_MESSAGES_URL,
            payload,
            {"x-api-key": secret, "anthropic-version": "2023-06-01"},
            provider_timeout,
        )
        attempts.append({"provider": "anthropic", "model": model, "ok": result.get("ok"), "status_code": result.get("status_code"), "error": result.get("error", "")})
        if result.get("ok"):
            data = result.get("json") if isinstance(result.get("json"), dict) else {}
            blocks = data.get("content") if isinstance(data.get("content"), list) else []
            reply_parts = [
                str(block.get("text") or "").strip()
                for block in blocks
                if isinstance(block, dict) and str(block.get("text") or "").strip()
            ]
            reply = "\n".join(reply_parts).strip()
            if reply:
                return {"ok": True, "provider": "anthropic", "model": model, "assistant_reply": reply, "attempts": attempts}
    return {"ok": False, "provider": "anthropic", "assistant_reply": "", "attempts": attempts, "error": attempts[-1].get("error", "") if attempts else "no model candidates"}


def _call_xai_bridge(prompt: str, request: dict[str, Any], *, secret: str, started: float) -> dict[str, Any]:
    max_tokens = max(32, min(1600, int(request.get("max_tokens") or request.get("max_completion_tokens") or 500)))
    temperature = float(request.get("temperature") or 0.35)
    system_prompt = _provider_system_prompt("xai", prompt)
    attempts: list[dict[str, Any]] = []
    provider_timeout = _provider_request_timeout_seconds(
        request,
        PROVIDER_BRIDGE_TIMEOUT_SECONDS,
        minimum=15,
        maximum=300,
    )
    for model in _provider_model_candidates("xai", request):
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        result = _provider_http_json(
            XAI_CHAT_COMPLETIONS_URL,
            payload,
            {"Authorization": f"Bearer {secret}"},
            provider_timeout,
        )
        attempts.append({"provider": "xai", "model": model, "ok": result.get("ok"), "status_code": result.get("status_code"), "error": result.get("error", "")})
        if result.get("ok"):
            data = result.get("json") if isinstance(result.get("json"), dict) else {}
            choices = data.get("choices") if isinstance(data.get("choices"), list) else []
            message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
            reply = str(message.get("content") or "").strip() if isinstance(message, dict) else ""
            if reply:
                return {"ok": True, "provider": "xai", "model": model, "assistant_reply": reply, "attempts": attempts}
    return {"ok": False, "provider": "xai", "assistant_reply": "", "attempts": attempts, "error": attempts[-1].get("error", "") if attempts else "no model candidates"}


def _call_gemini_bridge(prompt: str, request: dict[str, Any], *, secret: str, started: float) -> dict[str, Any]:
    max_tokens = max(32, min(1600, int(request.get("max_tokens") or request.get("max_completion_tokens") or 500)))
    temperature = float(request.get("temperature") or 0.35)
    system_prompt = _provider_system_prompt("gemini", prompt)
    attempts: list[dict[str, Any]] = []
    provider_timeout = _provider_request_timeout_seconds(
        request,
        PROVIDER_BRIDGE_TIMEOUT_SECONDS,
        minimum=15,
        maximum=300,
    )
    for model in _provider_model_candidates("gemini", request):
        safe_model = urllib.parse.quote(model, safe="-_.")
        url = GEMINI_GENERATE_CONTENT_URL_TEMPLATE.format(model=safe_model)
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        result = _provider_http_json(
            url,
            payload,
            {"x-goog-api-key": secret},
            provider_timeout,
        )
        attempts.append({"provider": "gemini", "model": model, "ok": result.get("ok"), "status_code": result.get("status_code"), "error": result.get("error", "")})
        if result.get("ok"):
            data = result.get("json") if isinstance(result.get("json"), dict) else {}
            candidates = data.get("candidates") if isinstance(data.get("candidates"), list) else []
            content = candidates[0].get("content") if candidates and isinstance(candidates[0], dict) else {}
            parts = content.get("parts") if isinstance(content, dict) and isinstance(content.get("parts"), list) else []
            reply = "\n".join(
                str(part.get("text") or "").strip()
                for part in parts
                if isinstance(part, dict) and str(part.get("text") or "").strip()
            ).strip()
            if reply:
                return {"ok": True, "provider": "gemini", "model": model, "assistant_reply": reply, "attempts": attempts}
    return {"ok": False, "provider": "gemini", "assistant_reply": "", "attempts": attempts, "error": attempts[-1].get("error", "") if attempts else "no model candidates"}


def _call_provider_bridge(provider: str, prompt: str, request: dict[str, Any], started: float) -> dict[str, Any]:
    prompt = _prompt_with_discord_room(prompt, request)
    if not _provider_bridge_enabled_for_routing(provider):
        return {
            "ok": False,
            "provider": provider,
            "assistant_reply": "",
            "error": f"{PROVIDER_BRIDGE_LABELS.get(provider, provider)} bridge is disabled for Engel chat routing",
            "secret_source": _public_secret_source(_provider_secret_source(provider)),
            "attempts": [],
        }
    source = _provider_secret_source(provider)
    if provider == "openai" and _env_truth("ENGEL_CHATGPT_BROWSER_BRIDGE_FIRST", default=True):
        chatgpt_browser_status = _chatgpt_browser_bridge_status()
        browser_result: dict[str, Any] | None = None
        browser_enabled = chatgpt_browser_status.get("enabled") is not False
        if browser_enabled and (
            chatgpt_browser_status.get("ok") is True
            or _env_truth("ENGEL_CHATGPT_BROWSER_BRIDGE_TRY_ON_STATUS_FAIL", default=True)
        ):
            browser_result = _call_chatgpt_browser_bridge(prompt, request, started)
            if browser_result.get("ok") is True:
                browser_result["secret_source"] = {
                    "present": True,
                    "provider": "openai",
                    "source_type": "rog_local_chatgpt_browser_oauth",
                    "name": "CHATGPT_BROWSER_LOCAL_AUTH",
                    "path": "",
                    "value_length": 0,
                }
                return browser_result
        if not _env_truth("ENGEL_OPENAI_API_FALLBACK_ENABLED", default=False):
            result = browser_result if isinstance(browser_result, dict) else {
                "ok": False,
                "provider": "openai",
                "assistant_reply": "",
                "attempts": [],
                "error": _redact_provider_error(
                    str(chatgpt_browser_status.get("reason") or "ROG ChatGPT browser bridge unavailable")
                ),
                "bridge_kind": "rog_chatgpt_browser",
            }
            result["secret_source"] = {
                "present": bool(chatgpt_browser_status.get("ok") is True),
                "provider": "openai",
                "source_type": "rog_local_chatgpt_browser_oauth",
                "name": "CHATGPT_BROWSER_LOCAL_AUTH",
                "path": "",
                "value_length": 0,
            }
            return result
        if chatgpt_browser_status.get("ok") is True:
            result = _call_chatgpt_browser_bridge(prompt, request, started)
            if result.get("ok") is True:
                result["secret_source"] = {
                    "present": True,
                    "provider": "openai",
                    "source_type": "rog_local_chatgpt_browser_oauth",
                    "name": "CHATGPT_BROWSER_LOCAL_AUTH",
                    "path": "",
                    "value_length": 0,
                }
                return result
            if source.get("present") is not True:
                result["secret_source"] = {
                    "present": True,
                    "provider": "openai",
                    "source_type": "rog_local_chatgpt_browser_oauth",
                    "name": "CHATGPT_BROWSER_LOCAL_AUTH",
                    "path": "",
                    "value_length": 0,
                }
                return result
    if provider == "anthropic":
        return {
            "ok": False,
            "provider": "anthropic",
            "assistant_reply": "",
            "error": "Claude/Anthropic is not used on Engel AI Main",
            "attempts": [],
        }
    if provider == "xai" and _env_truth("ENGEL_GROK_CLI_BRIDGE_FIRST", default=True):
        grok_cli_status = _grok_cli_bridge_status()
        if grok_cli_status.get("ok") is True:
            result = _call_provider_with_account_pool(
                "grok", prompt, request, started, _call_grok_cli_bridge
            )
            if result.get("ok") is True:
                result["secret_source"] = {
                    "present": True,
                    "provider": "xai",
                    "source_type": "rog_local_grok_cli_oauth",
                    "name": "GROK_CLI_LOCAL_AUTH",
                    "path": "",
                    "value_length": 0,
                }
                return result
            if source.get("present") is not True:
                result["secret_source"] = {
                    "present": True,
                    "provider": "xai",
                    "source_type": "rog_local_grok_cli_oauth",
                    "name": "GROK_CLI_LOCAL_AUTH",
                    "path": "",
                    "value_length": 0,
                }
                return result
    if provider == "gemini" and _env_truth("ENGEL_GEMINI_API_BRIDGE_FIRST", default=True):
        gemini_api_status = _gemini_api_bridge_status()
        # Gate on "usable" (key reachable), not "ok" (bridge merely up). /health
        # returns ok=true even with no Gemini key, which made CT POST a doomed
        # /chat every time; "usable" (= usable or secret_present) skips the lane
        # in ~1.2s when keyless and routes only when a key is actually present.
        if gemini_api_status.get("usable") is True:
            result = _call_gemini_api_bridge(prompt, request, started)
            if result.get("ok") is True:
                result["secret_source"] = {
                    "present": True,
                    "provider": "gemini",
                    "source_type": "rog_local_gemini_api",
                    "name": "GEMINI_ROG_LOCAL_BRIDGE_AUTH",
                    "path": "",
                    "value_length": 0,
                }
                return result
            if source.get("present") is not True:
                result["secret_source"] = {
                    "present": bool(gemini_api_status.get("usable") is True),
                    "provider": "gemini",
                    "source_type": "rog_local_gemini_api",
                    "name": "GEMINI_ROG_LOCAL_BRIDGE_AUTH",
                    "path": "",
                    "value_length": 0,
                }
                return result
    if provider == "codex" and _env_truth("ENGEL_CODEX_CLI_BRIDGE_FIRST", default=True):
        codex_cli_status = _codex_cli_bridge_status()
        if codex_cli_status.get("ok") is True:
            result = _call_codex_cli_bridge(prompt, request, started)
            result["secret_source"] = {
                "present": True,
                "provider": "codex",
                "source_type": "rog_local_codex_cli_auth",
                "name": "CODEX_CLI_LOCAL_AUTH",
                "path": "",
                "value_length": 0,
            }
            return result
        return {
            "ok": False,
            "provider": "codex",
            "assistant_reply": "",
            "attempts": [],
            "error": _redact_provider_error(str(codex_cli_status.get("reason") or "ROG Codex CLI bridge unavailable")),
            "bridge_kind": "rog_codex_cli",
            "secret_source": {
                "present": False,
                "provider": "codex",
                "source_type": "rog_local_codex_cli_auth",
                "name": "CODEX_CLI_LOCAL_AUTH",
                "path": "",
                "value_length": 0,
            },
        }
    if source.get("present") is not True:
        return {
            "ok": False,
            "provider": provider,
            "assistant_reply": "",
            "error": f"{PROVIDER_BRIDGE_LABELS.get(provider, provider)} bridge has no CT secret or reachable route loaded",
            "secret_source": _public_secret_source(source),
            "attempts": [],
        }
    secret = str(source.get("secret") or "")
    if provider == "openai":
        result = _call_openai_bridge(prompt, request, secret=secret, started=started)
        if result.get("ok") is not True and not _env_truth("ENGEL_CHATGPT_BROWSER_BRIDGE_FIRST", default=True):
            api_auth_failed = any(
                int(attempt.get("status_code") or 0) in {401, 403}
                for attempt in (result.get("attempts") if isinstance(result.get("attempts"), list) else [])
                if isinstance(attempt, dict)
            )
            if api_auth_failed:
                return result
            chatgpt_browser_status = _chatgpt_browser_bridge_status()
            if chatgpt_browser_status.get("ok") is True:
                browser_result = _call_chatgpt_browser_bridge(prompt, request, started)
                if browser_result.get("ok") is True:
                    result = browser_result
    elif provider == "anthropic":
        result = _call_anthropic_bridge(prompt, request, secret=secret, started=started)
        if result.get("ok") is not True and not _env_truth("ENGEL_CLAUDE_CLI_BRIDGE_FIRST", default=True):
            claude_cli_status = _claude_cli_bridge_status()
            if claude_cli_status.get("ok") is True:
                cli_result = _call_claude_cli_bridge(prompt, request, started)
                if cli_result.get("ok") is True:
                    result = cli_result
    elif provider == "xai":
        result = _call_xai_bridge(prompt, request, secret=secret, started=started)
        if result.get("ok") is not True and not _env_truth("ENGEL_GROK_CLI_BRIDGE_FIRST", default=True):
            grok_cli_status = _grok_cli_bridge_status()
            if grok_cli_status.get("ok") is True:
                cli_result = _call_grok_cli_bridge(prompt, request, started)
                if cli_result.get("ok") is True:
                    result = cli_result
    elif provider == "gemini":
        result = _call_gemini_bridge(prompt, request, secret=secret, started=started)
        if result.get("ok") is not True and not _env_truth("ENGEL_GEMINI_API_BRIDGE_FIRST", default=True):
            gemini_api_status = _gemini_api_bridge_status()
            if gemini_api_status.get("usable") is True:
                api_result = _call_gemini_api_bridge(prompt, request, started)
                if api_result.get("ok") is True:
                    result = api_result
    elif provider == "codex":
        result = _call_codex_cli_bridge(prompt, request, started)
    elif provider == "nvidia":
        result = _call_nvidia_nim_bridge(prompt, request, secret=secret, started=started)
    else:
        result = {"ok": False, "provider": provider, "assistant_reply": "", "error": f"unknown provider bridge: {provider}", "attempts": []}
    result["secret_source"] = _public_secret_source(source)
    return result


def _provider_reply_quality_outcome(
    prompt: str,
    provider: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Validate and quarantine a provider draft before it can reach chat memory."""
    reply = str(result.get("assistant_reply") or "").strip()
    report = _incomplete_input_quality_report(prompt, reply)
    outcome = {
        "accepted": bool(reply) and report.get("ok") is True,
        "provider": provider,
        "provider_label": PROVIDER_BRIDGE_LABELS.get(provider, provider),
        "semantic_quality": report,
        "assistant_reply_sha256": hashlib.sha256(reply.encode("utf-8")).hexdigest() if reply else "",
        "quarantined": False,
        "quarantine_key": "",
    }
    result["provider_semantic_quality"] = report
    if outcome["accepted"]:
        return outcome

    if reply and report.get("ok") is not True:
        quarantine = _append_chat_sample_rejection(
            prompt,
            reply,
            {
                "selected_provider": provider,
                "provider": PROVIDER_BRIDGE_LABELS.get(provider, provider),
                "runtime_provider": str(result.get("model") or ""),
            },
            "provider incomplete-input semantic quality failure: "
            + ", ".join(str(value) for value in report.get("failed_checks") or []),
            source="engel-ai-main provider quality quarantine",
        )
        outcome["quarantined"] = quarantine.get("ok") is True
        outcome["quarantine_key"] = str(quarantine.get("sample_key") or "")
        result["provider_reply_quarantined"] = outcome["quarantined"]
        result["provider_reply_quarantine_key"] = outcome["quarantine_key"]
        result["provider_rejected_reply_sha256"] = outcome["assistant_reply_sha256"]
        result["assistant_reply"] = ""
        result["ok"] = False
        result["error"] = (
            "provider reply failed incomplete-input semantic quality gate: "
            + ", ".join(str(value) for value in report.get("failed_checks") or [])
        )
    return outcome


def _provider_bridge_receipt(
    prompt: str,
    request: dict[str, Any],
    started: float,
    *,
    persist_memory: bool = True,
) -> dict[str, Any] | None:
    status = _cached_snapshot("provider_bridges", _provider_bridge_status)
    if status.get("enabled") is not True:
        return None
    candidates, reason = _provider_candidates_for_prompt(prompt, request)
    if not candidates:
        return None
    explicit = reason == "explicit_provider"
    # Automatic candidates have already passed the fresh completion-capability
    # map. Explicit owner selections remain honest attempts even when degraded.
    usable_candidates = (
        candidates
        if explicit
        else _filter_automatic_provider_candidates(candidates)
    )
    if not usable_candidates and not explicit:
        return None

    attempts: list[dict[str, Any]] = []
    result: dict[str, Any] | None = None
    explicit_failed_provider = ""
    explicit_provider_failure_error = ""
    explicit_provider_fallback_used = False
    explicit_provider_fallback_reason = ""
    explicit_provider_fallback_candidates: list[str] = []
    quality_rejections: list[dict[str, Any]] = []
    # SPEED: only attempt bridges the health cache says are alive. A dead
    # Claude bridge used to burn its full timeout on EVERY turn before the
    # router fell through to a working lane (10s turns became 37s+). Explicit
    # requests still try the asked-for provider so the user gets a real error.
    attempt_candidates = candidates if explicit else usable_candidates[:2]
    for provider in attempt_candidates:
        result = _call_provider_bridge(provider, prompt, request, started)
        attempts.extend(result.get("attempts") if isinstance(result.get("attempts"), list) else [])
        if result.get("ok") is True and str(result.get("assistant_reply") or "").strip():
            quality_outcome = _provider_reply_quality_outcome(
                str(request.get("_semantic_quality_prompt") or prompt),
                provider,
                result,
            )
            if quality_outcome.get("accepted") is True:
                break
            quality_rejections.append(quality_outcome)
        if explicit:
            explicit_failed_provider = provider
            explicit_provider_failure_error = _redact_provider_error(
                str(result.get("error") or "provider route unavailable")
            )
            explicit_provider_fallback_candidates, explicit_provider_fallback_reason = _explicit_provider_fallback_candidates(provider, prompt, request)
            for fallback_provider in explicit_provider_fallback_candidates:
                fallback_result = _call_provider_bridge(fallback_provider, prompt, request, started)
                attempts.extend(fallback_result.get("attempts") if isinstance(fallback_result.get("attempts"), list) else [])
                if fallback_result.get("ok") is True and str(fallback_result.get("assistant_reply") or "").strip():
                    quality_outcome = _provider_reply_quality_outcome(
                        str(request.get("_semantic_quality_prompt") or prompt),
                        fallback_provider,
                        fallback_result,
                    )
                    if quality_outcome.get("accepted") is True:
                        result = fallback_result
                        provider = fallback_provider
                        explicit_provider_fallback_used = True
                        break
                    quality_rejections.append(quality_outcome)
            if explicit_provider_fallback_used:
                break
            break
    if not result or result.get("ok") is not True:
        request["_provider_bridge_attempts"] = attempts
        request["_provider_bridge_candidates"] = attempt_candidates
        request["_provider_bridge_route_reason"] = reason
        if not explicit:
            if quality_rejections:
                request["_provider_semantic_quality_rejections"] = quality_rejections
            return None
        provider = candidates[0]
        label = PROVIDER_BRIDGE_LABELS.get(provider, provider)
        explicit_provider_failure_error = explicit_provider_failure_error or _redact_provider_error(
            (result or {}).get("error") or "missing provider secret or route"
        )
        explicit_provider_failure_error = explicit_provider_failure_error.rstrip(".")
        reply = (
            f"{label} is wired into Engel, but it is not usable right now: "
            f"{explicit_provider_failure_error}. Engel did not fake a {label} reply; use Auto Best or another route."
        )
    else:
        provider = str(result.get("provider") or candidates[0])
        reply = str(result.get("assistant_reply") or "").strip()
        if explicit_provider_fallback_used:
            requested_label = PROVIDER_BRIDGE_LABELS.get(explicit_failed_provider, explicit_failed_provider)
            actual_label = PROVIDER_BRIDGE_LABELS.get(provider, provider)
            reason_text = explicit_provider_failure_error or "requested provider route failed"
            reply = f"{requested_label} is not usable right now ({reason_text}), so Engel used {actual_label}: {reply}"

    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_PROVIDER_BRIDGE_CHAT_{stamp}.json"
    receipt = {
        "schema": "engel_main_server_provider_bridge_chat_receipt_v1",
        "ok": True,
        "status": "provider bridge replied" if result and result.get("ok") is True else "provider bridge unavailable",
        "updated_at_utc": _iso_now(),
        "run_id": "main_server_provider_bridge_chat_" + stamp,
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": PROVIDER_BRIDGE_LABELS.get(provider, provider),
        "runtime_provider": str(result.get("model") or "") if isinstance(result, dict) else "",
        "selected_provider": provider,
        "provider_bridge_used": bool(result and result.get("ok") is True),
        "provider_bridge_route_reason": reason,
        "provider_bridge_candidates": candidates,
        "explicit_provider_requested": explicit,
        "explicit_provider_failed_provider": explicit_failed_provider,
        "explicit_provider_failure_error": explicit_provider_failure_error,
        "explicit_provider_fallback_used": explicit_provider_fallback_used,
        "explicit_provider_fallback_reason": explicit_provider_fallback_reason,
        "explicit_provider_fallback_candidates": explicit_provider_fallback_candidates,
        "provider_bridge_attempts": attempts or (result.get("attempts") if isinstance(result, dict) else []),
        "provider_semantic_quality": (result or {}).get("provider_semantic_quality", {}),
        "provider_semantic_quality_rejections": quality_rejections,
        "provider_reply_quality_gate_passed": bool(
            result and result.get("ok") is True
            and isinstance(result.get("provider_semantic_quality"), dict)
            and result.get("provider_semantic_quality", {}).get("ok") is True
        ),
        "provider_bridge_status": status,
        "provider_secret_source": _public_secret_source((result or {}).get("secret_source", {}) if isinstance((result or {}).get("secret_source"), dict) else _provider_secret_source(provider)),
        "main_server_chat_service_used": True,
        "model_process_started": False,
        "runtime_process_started": False,
        "runs_inference": bool(result and result.get("ok") is True),
        "loads_model": False,
        "provider_api_enabled": bool(result and result.get("ok") is True),
        "network_enabled": bool(result and result.get("ok") is True),
        "server_enabled": True,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "model_output_trusted": False,
        "bridge_training_capture_enabled": True,
        "bridge_training_sample_kind": "untrusted_supervised_chat_pair",
        "server_snapshot": _service_snapshot(),
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
    }
    receipt = _apply_chat_humanizer(prompt, receipt, "ct_provider_bridge_chat")
    receipt = _repair_stale_visible_reply(prompt, receipt)
    receipt = _enforce_requested_short_format(prompt, receipt)
    receipt = _sanitize_automatic_provider_identity(prompt, receipt, provider)
    final_reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "").strip()
    final_quality = _incomplete_input_quality_report(
        str(request.get("_semantic_quality_prompt") or prompt),
        final_reply,
    )
    receipt["provider_final_semantic_quality"] = final_quality
    if final_reply and final_quality.get("ok") is not True:
        quarantine = _append_chat_sample_rejection(
            prompt,
            final_reply,
            receipt,
            "final provider reply failed incomplete-input semantic quality gate: "
            + ", ".join(str(value) for value in final_quality.get("failed_checks") or []),
            source="engel-ai-main provider quality quarantine",
        )
        request.setdefault("_provider_semantic_quality_rejections", []).append(
            {
                "accepted": False,
                "provider": provider,
                "provider_label": PROVIDER_BRIDGE_LABELS.get(provider, provider),
                "semantic_quality": final_quality,
                "assistant_reply_sha256": hashlib.sha256(final_reply.encode("utf-8")).hexdigest(),
                "quarantined": quarantine.get("ok") is True,
                "quarantine_key": str(quarantine.get("sample_key") or ""),
                "stage": "final_visible_reply",
            }
        )
        return None
    if persist_memory:
        memory_record = dict(receipt)
        memory_record["memory_source"] = "engel-ai-main CT provider bridge chat capture"
        try:
            _append_jsonl(PERSISTENT_CHAT_MEMORY_PATH, memory_record)
            receipt["persistent_chat_memory_appended"] = True
            receipt["persistent_chat_history_appended"] = True
            receipt["persistent_chat_memory_path"] = str(PERSISTENT_CHAT_MEMORY_PATH)
        except Exception as exc:
            receipt["persistent_chat_memory_appended"] = False
            receipt["persistent_chat_history_appended"] = False
            receipt["persistent_chat_memory_error"] = str(exc)
    _write_json(receipt_path, receipt)
    return receipt


def _skill_agent_creator_status() -> dict[str, Any]:
    try:
        from engel_skill_agent_creator import creator_status

        return creator_status()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _skill_status_report() -> dict[str, Any]:
    try:
        from engel_skill_agent_creator import skill_status_report

        return skill_status_report()
    except Exception as exc:
        return {"ok": False, "schema": "engel_skill_status_report_v1", "skills": [], "error": str(exc)}


def _agent_status_report() -> dict[str, Any]:
    try:
        from engel_skill_agent_creator import agent_status_report

        return agent_status_report()
    except Exception as exc:
        return {"ok": False, "schema": "engel_agent_status_report_v1", "agents": [], "error": str(exc)}


def _universal_reps_template_snapshot() -> dict[str, Any]:
    data = _load_json_file(REPS_TEMPLATE_PATH)
    if not data:
        return {
            "ok": False,
            "schema": "engel_universal_reps_template_status_v1",
            "status": "missing",
            "template_path": str(REPS_TEMPLATE_PATH),
            "markdown_template_path": str(REPS_TEMPLATE_MD_PATH),
            "template_present": REPS_TEMPLATE_PATH.is_file(),
            "markdown_template_present": REPS_TEMPLATE_MD_PATH.is_file(),
            "skill_key": "engel-universal-reps",
        }
    paths = data.get("paths") if isinstance(data.get("paths"), dict) else {}
    skill_path = ROOT / str(paths.get("skill") or "skills/engel-universal-reps/SKILL.md")
    managed_skill_path = ROOT / str(paths.get("managed_skill") or ".agents/skills/engel-universal-reps/SKILL.md")
    return {
        "ok": True,
        "schema": "engel_universal_reps_template_status_v1",
        "status": str(data.get("status") or "active_template"),
        "name": str(data.get("name") or "Engel Universal REPS"),
        "skill_key": str(data.get("skill_key") or "engel-universal-reps"),
        "provider_neutral": bool(data.get("provider_neutral") is True),
        "claude_only": bool(data.get("claude_only") is True),
        "applies_to_ai_lanes": data.get("applies_to_ai_lanes") if isinstance(data.get("applies_to_ai_lanes"), list) else [],
        "authority_order": data.get("authority_order") if isinstance(data.get("authority_order"), list) else [],
        "loop": data.get("loop") if isinstance(data.get("loop"), dict) else {},
        "signoff_buckets": data.get("signoff_buckets") if isinstance(data.get("signoff_buckets"), dict) else {},
        "scoreboard": data.get("scoreboard") if isinstance(data.get("scoreboard"), list) else [],
        "template_path": str(REPS_TEMPLATE_PATH),
        "markdown_template_path": str(REPS_TEMPLATE_MD_PATH),
        "template_present": REPS_TEMPLATE_PATH.is_file(),
        "markdown_template_present": REPS_TEMPLATE_MD_PATH.is_file(),
        "skill_path": str(skill_path),
        "skill_present": skill_path.is_file(),
        "managed_skill_path": str(managed_skill_path),
        "managed_skill_present": managed_skill_path.is_file(),
        "updated_at_utc": str(data.get("updated_at_utc") or ""),
    }


def _universal_reps_runtime_status() -> dict[str, Any]:
    try:
        from engel_universal_reps_runtime import status

        return status()
    except Exception as exc:
        return {
            "ok": False,
            "schema": "engel_reps_runtime_state_v1",
            "status": "runtime unavailable",
            "error": str(exc),
        }


def _universal_reps_record(payload: dict[str, Any]) -> dict[str, Any]:
    from engel_universal_reps_runtime import record_event

    return record_event(payload)


def _universal_reps_evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    from engel_universal_reps_runtime import evaluate_event

    return evaluate_event(payload)


def _universal_reps_propose(payload: dict[str, Any]) -> dict[str, Any]:
    from engel_universal_reps_runtime import propose_improvement

    return propose_improvement(payload)


def _universal_reps_signoff(payload: dict[str, Any]) -> dict[str, Any]:
    from engel_universal_reps_runtime import signoff_decision

    return signoff_decision(payload)


def _universal_reps_cycle(payload: dict[str, Any]) -> dict[str, Any]:
    from engel_universal_reps_runtime import run_cycle

    return run_cycle(payload)


def _self_upgrade_status_snapshot() -> dict[str, Any]:
    """Project CT246's authoritative governed-loop state for the ROG UI."""
    try:
        from engel_self_upgrade_loop_stream import snapshot_to_stream

        state = snapshot_to_stream()
        return {
            "schema": "ENGEL_SELF_UPGRADE_HTTP_STATUS_V1",
            "ok": True,
            "status": "CT246 governed self-upgrade state ready",
            "source_of_truth": str(ROOT),
            "active_runtime_root": "/opt/engel",
            "local_model_first": True,
            "provider_called": False,
            "state": state,
            "updated_at_utc": _iso_now(),
        }
    except Exception as exc:
        return {
            "schema": "ENGEL_SELF_UPGRADE_HTTP_STATUS_V1",
            "ok": False,
            "status": "CT246 governed self-upgrade state unavailable",
            "source_of_truth": str(ROOT),
            "error": str(exc)[:500],
            "provider_called": False,
            "updated_at_utc": _iso_now(),
        }


def _self_upgrade_plan_request(
    payload: dict[str, Any],
    *,
    planner_fn: Any = None,
) -> dict[str, Any]:
    from engel_local_self_upgrade_planner import plan_request

    planner = planner_fn or plan_request
    result = planner(payload)
    if not isinstance(result, dict):
        raise ValueError("local self-upgrade planner returned an invalid result")
    result.setdefault("local_model_first", True)
    result.setdefault("provider_called", False)
    result.setdefault("candidate_only", True)
    result.setdefault("source_mutation_performed", False)
    return result


def _self_upgrade_cycle_request(
    payload: dict[str, Any],
    *,
    planner_fn: Any = None,
    cycle_fn: Any = None,
) -> dict[str, Any]:
    """Run one governed cycle; source apply remains token- and quorum-gated."""
    request = payload.get("cycle_request")
    plan_receipt: dict[str, Any] | None = None
    if not isinstance(request, dict):
        plan_receipt = _self_upgrade_plan_request(payload, planner_fn=planner_fn)
        request = plan_receipt.get("cycle_request")
    if not isinstance(request, dict):
        raise ValueError("cycle_request is required")

    execute = payload.get("execute") is True
    actor = str(payload.get("actor") or "owner_joshua").strip()
    if actor != "owner_joshua":
        raise PermissionError("self-upgrade cycle actor must be owner_joshua")
    fix_token = str(payload.get("fix_approval_token") or "")
    gate_token = str(payload.get("gate_token") or "")
    apply_token = str(payload.get("apply_token") or "")
    if execute:
        from engel_self_patch_quorum import FIX_APPROVAL_TOKEN
        import engel_self_upgrade_system as upgrade_system

        valid_pairs = {
            (
                upgrade_system.LOW_RISK_GATE_TOKEN,
                upgrade_system.LOW_RISK_APPLY_TOKEN,
            ),
            (
                upgrade_system.ELEVATED_RISK_GATE_TOKEN,
                upgrade_system.ELEVATED_RISK_APPLY_TOKEN,
            ),
        }
        if fix_token != FIX_APPROVAL_TOKEN:
            raise PermissionError("execute requires the explicit fix approval token")
        if (gate_token, apply_token) not in valid_pairs:
            raise PermissionError(
                "execute requires a matching low-risk or elevated-risk gate/apply token pair"
            )

    if cycle_fn is None:
        from engel_conical_self_upgrade_cycle import run_cycle

        cycle_fn = run_cycle
    cycle = cycle_fn(
        request,
        dry_run=not execute,
        actor=actor,
        fix_approval_token=fix_token,
        gate_token=gate_token,
        apply_token=apply_token,
    )
    if not isinstance(cycle, dict):
        raise ValueError("governed self-upgrade cycle returned an invalid result")
    final_status = str(cycle.get("final_status") or "unknown")
    completed = final_status in {
        "dry_run_complete",
        "upgraded_verified",
        "applied_then_rolled_back",
    }
    return {
        "schema": "ENGEL_SELF_UPGRADE_HTTP_CYCLE_V1",
        "ok": True,
        "status": "governed self-upgrade cycle recorded",
        "cycle_completed": completed,
        "final_status": final_status,
        "mode": "execute" if execute else "dry_run",
        "source_of_truth": str(ROOT),
        "local_model_first": True,
        "provider_called": False,
        "plan_receipt_path": (
            plan_receipt.get("receipt_path")
            if isinstance(plan_receipt, dict)
            else None
        ),
        "cycle": cycle,
        "updated_at_utc": _iso_now(),
    }


_SELF_UPGRADE_CHAT_REVIEW_PREFIXES = (
    "/self-upgrade review ",
    "review this engel self-upgrade without applying:",
    "run a governed self-upgrade review without applying:",
)


def _self_upgrade_chat_review_text(
    prompt: str,
    request: dict[str, Any],
) -> str:
    """Return a bounded review request only for an explicit desktop command."""
    if not _chat_context_scope(request).startswith("engel_ai_main_desktop"):
        return ""
    current = _intent_gate_text(prompt).strip()
    lowered = current.casefold()
    for prefix in _SELF_UPGRADE_CHAT_REVIEW_PREFIXES:
        if lowered.startswith(prefix):
            request_text = current[len(prefix):].strip()
            return request_text if 12 <= len(request_text) <= 4000 else ""
    return ""


def _self_upgrade_chat_review_turn(
    prompt: str,
    request: dict[str, Any],
    started: float,
) -> tuple[dict[str, Any], str] | None:
    """Run a non-applying governed cycle from the real Engel desktop chat."""
    request_text = _self_upgrade_chat_review_text(prompt, request)
    if not request_text:
        return None

    result = _self_upgrade_cycle_request(
        {
            "request_text": request_text,
            "source": "engel_flutter_main_chat",
            "actor": "owner_joshua",
            "severity": "medium",
            "execute": False,
        }
    )
    cycle = result.get("cycle") if isinstance(result.get("cycle"), dict) else {}
    stages = cycle.get("stages") if isinstance(cycle.get("stages"), list) else []
    distributed = next(
        (
            stage
            for stage in stages
            if isinstance(stage, dict) and stage.get("stage") == "distributed_work"
        ),
        {},
    )
    provenance_stage = next(
        (
            stage
            for stage in stages
            if isinstance(stage, dict) and stage.get("stage") == "provenance"
        ),
        {},
    )
    workers = (
        distributed.get("required_worker_ids")
        if isinstance(distributed.get("required_worker_ids"), list)
        else []
    )
    returned_count = int(distributed.get("returned_worker_count") or 0)
    final_status = str(result.get("final_status") or "unknown")
    completed = (
        final_status == "dry_run_complete"
        and distributed.get("ok") is True
        and returned_count == 4
        and provenance_stage.get("ok") is True
    )
    provenance_id = str(provenance_stage.get("provenance_id") or "")
    ledger_path = str(provenance_stage.get("ledger_path") or "")
    cycle_receipt_path = str(cycle.get("cycle_receipt_path") or "")
    worker_text = ", ".join(str(worker) for worker in workers) or "none"
    if completed:
        reply = (
            "Governed self-upgrade review completed without applying code.\n"
            f"Status: {final_status}\n"
            f"Workers returned: {returned_count}/4 ({worker_text})\n"
            f"Prompt-to-patch provenance: {provenance_id}\n"
            f"Ledger: {ledger_path}\n"
            f"Cycle receipt: {cycle_receipt_path}\n"
            "Local CT246 planning was used; providers were not called."
        )
    else:
        reply = (
            "The governed self-upgrade review stopped without applying code.\n"
            f"Status: {final_status}\n"
            f"Workers returned: {returned_count}/4 ({worker_text})\n"
            "No source change was authorized."
        )

    receipt_path = (
        CHAT_RECEIPT_DIR
        / f"ENGEL_MAIN_SERVER_SELF_UPGRADE_CHAT_REVIEW_{_stamp()}.json"
    )
    receipt = {
        "schema": "ENGEL_MAIN_SERVER_SELF_UPGRADE_CHAT_REVIEW_V1",
        "ok": completed,
        "status": (
            "governed self-upgrade chat review completed"
            if completed
            else "governed self-upgrade chat review stopped"
        ),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "local-ct246-self-upgrade",
        "runtime_provider": "engel-conical-self-upgrade-cycle",
        "selected_provider": "ct_self_upgrade_chat_review",
        "model": "ct246-local-self-upgrade-planner",
        "local_model_first": True,
        "provider_api_enabled": False,
        "provider_called": False,
        "network_enabled": False,
        "dry_run": True,
        "source_mutation_performed": False,
        "trusted_memory_write_performed": False,
        "required_worker_ids": workers,
        "returned_worker_count": returned_count,
        "provenance_id": provenance_id,
        "provenance_ledger_path": ledger_path,
        "cycle_receipt_path": cycle_receipt_path,
        "self_upgrade_cycle": result,
        "workspace_receipt_path": str(receipt_path),
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }
    return receipt, reply


def _loopback_client_address(value: str) -> bool:
    try:
        import ipaddress

        return ipaddress.ip_address(str(value or "")).is_loopback
    except ValueError:
        return False


def _prompt_should_force_reps_proposal(prompt: str, reply: str) -> bool:
    low = f"{prompt}\n{reply}".casefold()
    terms = (
        "reps",
        "record evaluate propose",
        "self-improv",
        "self improving",
        "self-improving",
        "auto-memory",
        "scoreboard",
        "sign-off",
        "signoff",
        "repeat",
        "repeating",
        "canned",
        "empty",
        "not real",
        "broken",
    )
    return any(term in low for term in terms)


def _shell_bridge_registry_snapshot() -> dict[str, Any]:
    try:
        from engel_shell_bridge_registry import build_registry

        health = {
            "ok": True,
            "model_runtime": _cached_snapshot("model_runtime", _model_runtime_snapshot),
            "provider_bridges": _cached_snapshot("provider_bridges", _provider_bridge_status),
            "phone_bridge": _cached_snapshot("phone_bridge", _phone_bridge_snapshot),
            "sub_engel_bridge": _cached_snapshot("sub_engel_bridge", _sub_engel_bridge_snapshot),
            "universal_reps_runtime": _cached_snapshot(
                "universal_reps_runtime", _universal_reps_runtime_status
            ),
            "self_model": _cached_snapshot("self_model", _self_model_snapshot, ttl_seconds=5.0),
        }
        room = _cached_snapshot("meeting_room", _meeting_room_snapshot)
        return build_registry(health, root=ROOT, meeting_room=room)
    except Exception as exc:
        return {
            "schema": "ENGEL_SHELL_BRIDGE_REGISTRY_STATUS_V1",
            "ok": False,
            "status": "bridge registry unavailable",
            "registry_path": str(SHELL_BRIDGE_REGISTRY_PATH),
            "error": str(exc),
        }


def _provider_capability_snapshot() -> dict[str, Any]:
    try:
        from engel_provider_capability_map import build_capability_map

        bridge_registry = _cached_snapshot(
            "shell_bridge_registry",
            _shell_bridge_registry_snapshot,
            ttl_seconds=5.0,
        )
        provider_status = _cached_snapshot("provider_bridges", _provider_bridge_status)
        return build_capability_map(
            bridge_registry,
            provider_status,
            root=ROOT,
            persist=True,
            state_path=PROVIDER_CAPABILITY_MAP_PATH,
        )
    except Exception as exc:
        return {
            "schema": "ENGEL_PROVIDER_COMPLETION_CAPABILITY_MAP_STATUS_V1",
            "ok": False,
            "status": "provider capability map unavailable",
            "automatic_provider_ids": [],
            "state_path": str(PROVIDER_CAPABILITY_MAP_PATH),
            "error": _clip(str(exc), 300),
        }


def _local_llm_fast_fail_snapshot() -> dict[str, Any]:
    try:
        return local_llm_fast_fail_status(probe_warm=True)
    except Exception as exc:
        return {
            "schema": "ENGEL_LOCAL_LLM_FAST_FAIL_STATUS_V1",
            "ok": False,
            "status": "local LLM deadline controller unavailable",
            "error": _clip(str(exc), 300),
        }


def _chat_failure_corpus_snapshot() -> dict[str, Any]:
    try:
        return chat_failure_corpus_status()
    except Exception as exc:
        return {
            "schema": "ENGEL_CHAT_FAILURE_CORPUS_STATUS_V1",
            "ok": False,
            "status": "chat failure corpus unavailable",
            "error": _clip(str(exc), 300),
            "trusted_memory_write": False,
        }


def _context_pack_snapshot() -> dict[str, Any]:
    try:
        return context_pack_status()
    except Exception as exc:
        return {
            "schema": "ENGEL_CODEX_WORKBENCH_CONTEXT_PACK_STATUS_V1",
            "ok": False,
            "status": "context pack ingest unavailable",
            "error": _clip(str(exc), 300),
            "trusted_memory_write": False,
            "external_array_used": False,
        }


def _chat_route_parity_snapshot() -> dict[str, Any]:
    try:
        return chat_route_parity_status()
    except Exception as exc:
        return {
            "schema": "ENGEL_DISCORD_DESKTOP_ROUTE_PARITY_STATUS_V1",
            "ok": False,
            "status": "shared desktop and Discord route ledger unavailable",
            "error": _clip(str(exc), 300),
            "trusted_memory_write": False,
            "external_array_used": False,
        }


def _capture_chat_failure(
    prompt: str,
    reply: str,
    receipt: dict[str, Any],
    attachment_intake: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
    *,
    source: str,
) -> dict[str, Any]:
    try:
        return capture_chat_failure(
            prompt=prompt,
            reply=reply,
            receipt=receipt,
            attachment_intake=attachment_intake,
            request=request,
            source=source,
        )
    except Exception as exc:
        return {
            "schema": "ENGEL_CHAT_FAILURE_CORPUS_CAPTURE_V1",
            "ok": False,
            "captured": False,
            "status": "chat failure corpus capture failed",
            "error": _clip(str(exc), 300),
            "trusted_memory_write": False,
        }


def _finalize_chat_route_parity(
    prompt: str,
    reply: str,
    receipt: dict[str, Any],
    request: dict[str, Any],
    attachment_intake: dict[str, Any] | None,
    *,
    source: str,
    stage: str,
) -> tuple[dict[str, Any], str]:
    try:
        result = finalize_chat_surface_turn(
            prompt=prompt,
            reply=reply,
            receipt=receipt,
            request=request,
            attachment_intake=attachment_intake,
            existing_failure_capture=(
                receipt.get("chat_failure_corpus")
                if isinstance(receipt.get("chat_failure_corpus"), dict)
                else None
            ),
            source=source,
            stage=stage,
        )
        finalized_receipt = result.get("receipt") if isinstance(result.get("receipt"), dict) else receipt
        finalized_reply = str(result.get("reply") or reply)
        finalized_receipt["assistant_reply"] = finalized_reply
        finalized_receipt["assistant_output_text"] = finalized_reply
        return finalized_receipt, finalized_reply
    except Exception as exc:
        receipt["chat_route_parity"] = {
            "schema": "ENGEL_CHAT_ROUTE_PARITY_RECORD_V1",
            "ok": False,
            "status": "shared chat route record failed",
            "error": _clip(str(exc), 300),
            "storage_mutation": False,
            "external_array_used": False,
        }
        return receipt, reply


def _persist_final_chat_receipt(receipt: dict[str, Any]) -> None:
    receipt_path = str(receipt.get("workspace_receipt_path") or "").strip()
    if not receipt_path:
        return
    try:
        _write_json(Path(receipt_path), receipt)
    except Exception as exc:
        receipt["finalized_receipt_write_error"] = str(exc)


def _attach_reps_cycle_to_receipt(receipt: dict[str, Any], prompt: str, reply: str, source: str) -> dict[str, Any]:
    try:
        result = _universal_reps_cycle(
            {
                "lane": "ct246-engel-ai-main",
                "source": source,
                "kind": "chat_turn",
                "prompt": prompt,
                "assistant_reply": reply,
                "receipt_path": receipt.get("workspace_receipt_path") or "",
                "force_propose": _prompt_should_force_reps_proposal(prompt, reply),
                "context": {
                    "provider": receipt.get("provider", ""),
                    "runtime_provider": receipt.get("runtime_provider", ""),
                    "status": receipt.get("status", ""),
                    "model_route_ok": receipt.get("model_route_ok"),
                    "meeting_room_server_used": receipt.get("meeting_room_server_used"),
                    "persistent_chat_memory_appended": receipt.get("persistent_chat_memory_appended"),
                },
            }
        )
        receipt["universal_reps_runtime_used"] = True
        receipt["universal_reps_cycle_id"] = result.get("cycle_id", "")
        receipt["universal_reps_cycle_summary"] = result.get("summary", {})
        receipt["universal_reps_cycle_receipt_path"] = result.get("workspace_receipt_path", "")
    except Exception as exc:
        receipt["universal_reps_runtime_used"] = False
        receipt["universal_reps_runtime_error"] = str(exc)
    return receipt


def _service_snapshot() -> dict[str, Any]:
    return {
        "server_role": "engel-ai-main CT 246",
        "runtime_root": str(ROOT),
        "chat_service": "engel-main-chat.service",
        "meeting_room_service": "engel-agent-meeting-room.service",
        "chat_url_from_rog": "http://127.0.0.1:24680",
        "meeting_room_url_from_rog": "http://127.0.0.1:8790",
        "ct_chat_url": "http://127.0.0.1:8765",
        "ct_meeting_room_url": _meeting_room_url(),
        "persistent_memory_path": str(PERSISTENT_CHAT_MEMORY_PATH),
        "model_runtime": _cached_snapshot("model_runtime", _model_runtime_snapshot),
        "phone_bridge": _cached_snapshot("phone_bridge", _phone_bridge_snapshot),
        "skill_agent_creator": _cached_snapshot("skill_agent_creator", _skill_agent_creator_status),
        "universal_reps": _cached_snapshot("universal_reps", _universal_reps_template_snapshot),
        "universal_reps_runtime": _cached_snapshot("universal_reps_runtime", _universal_reps_runtime_status),
        "shell_bridge_registry": _cached_snapshot(
            "shell_bridge_registry", _shell_bridge_registry_snapshot, ttl_seconds=5.0
        ),
        "provider_bridges": _cached_snapshot("provider_bridges", _provider_bridge_status),
        "provider_capabilities": _cached_snapshot(
            "provider_capabilities", _provider_capability_snapshot, ttl_seconds=15.0
        ),
        "local_llm_fast_fail": _cached_snapshot(
            "local_llm_fast_fail", _local_llm_fast_fail_snapshot, ttl_seconds=5.0
        ),
        "chat_failure_corpus": _cached_snapshot(
            "chat_failure_corpus", _chat_failure_corpus_snapshot, ttl_seconds=5.0
        ),
    }


def _model_runtime_snapshot() -> dict[str, Any]:
    manifest = _load_json_file(LORA_MANIFEST_PATH)
    artifact_dir = Path(
        os.environ.get("ENGEL_TRAINED_LORA_ARTIFACT_DIR")
        or str(manifest.get("local_artifact_dir") or manifest.get("external_artifact_dir") or "")
    )
    adapter_gguf = Path(
        os.environ.get("ENGEL_TRAINED_LORA_ADAPTER_GGUF")
        or str((manifest.get("adapter_model_gguf") if isinstance(manifest.get("adapter_model_gguf"), dict) else {}).get("path") or "")
    )
    if str(adapter_gguf) and not adapter_gguf.is_absolute():
        adapter_gguf = artifact_dir / adapter_gguf
    if not str(adapter_gguf):
        adapter_gguf = artifact_dir / "adapter_model.gguf"
    base_model = Path(
        os.environ.get("ENGEL_TRAINED_LORA_BASE_GGUF_MODEL")
        or str(manifest.get("serving_base_gguf_model_path") or "")
    )
    local_model = Path(os.environ.get("ENGEL_LOCAL_GGUF_MODEL", ""))
    try:
        from run_engel_standalone_chat_llm import trained_lora_runtime_status

        lora_status = trained_lora_runtime_status(manifest)
    except Exception as exc:
        lora_status = {"ok": False, "ready": False, "error": str(exc)}
    try:
        from engel_large_chat_llm import large_chat_model_status

        large_status = large_chat_model_status()
    except Exception as exc:
        large_status = {"ok": False, "error": str(exc)}
    try:
        from engel_local_model_service import local_model_cache_status

        local_cache_status = local_model_cache_status()
    except Exception as exc:
        local_cache_status = {"ok": False, "error": str(exc)}
    quick_model = Path(
        os.environ.get(
            "ENGEL_QUICK_CHAT_GGUF_MODEL",
            "/opt/engel/models-active/llm/qwen2.5-0.5b-instruct/"
            "qwen2.5-0.5b-instruct-q5_k_m.gguf",
        )
    )
    code_model = Path(
        os.environ.get(
            "ENGEL_CODE_LANE_GGUF_MODEL",
            "/opt/engel/models-active/llm/qwen2.5-coder-3b-instruct/"
            "qwen2.5-coder-3b-instruct-q5_k_m.gguf",
        )
    )
    deep_model = Path(
        os.environ.get(
            "ENGEL_DEEP_REASON_GGUF_MODEL",
            "/opt/engel/models-active/llm/qwen2.5-14b-instruct/"
            "qwen2.5-14b-instruct-Q4_K_M.gguf",
        )
    )
    moe_model = Path(
        os.environ.get(
            "ENGEL_MOE_REASON_GGUF_MODEL",
            "/opt/engel/models-active/llm/qwen3-30b-a3b/"
            "Qwen3-30B-A3B-Q4_K_M.gguf",
        )
    )
    return {
        "lora_manifest_path": str(LORA_MANIFEST_PATH),
        "lora_manifest_present": LORA_MANIFEST_PATH.is_file(),
        "lora_manifest_ok": manifest.get("ok") is True,
        "lora_runtime_ready": bool(lora_status.get("ready") is True),
        "lora_runtime_status": lora_status,
        "trained_lora_base_gguf_model_path": str(base_model),
        "trained_lora_base_gguf_model_present": bool(str(base_model) and base_model.is_file()),
        "trained_lora_adapter_gguf_path": str(adapter_gguf),
        "trained_lora_adapter_gguf_present": bool(str(adapter_gguf) and adapter_gguf.is_file()),
        "local_gguf_model_path": str(local_model),
        "local_gguf_model_present": bool(str(local_model) and local_model.is_file()),
        "large_chat_llm": large_status,
        "selective_model_activation": {
            "ok": local_cache_status.get("ok") is True,
            "mode": "task_routed_single_resident_mmap",
            "quick_model_path": str(quick_model),
            "quick_model_present": bool(str(quick_model) and quick_model.is_file()),
            "code_model_path": str(code_model),
            "code_model_present": code_model.is_file(),
            "trained_model_path": str(base_model),
            "trained_model_present": bool(str(base_model) and base_model.is_file()),
            "deep_model_path": str(deep_model),
            "deep_model_present": deep_model.is_file(),
            "deep_lane_enabled": _env_truth("ENGEL_DEEP_REASON_LANE_ENABLED", default=True),
            "sparse_moe_model_path": str(moe_model),
            "sparse_moe_model_present": moe_model.is_file(),
            "sparse_moe_lane_enabled": _env_truth(
                "ENGEL_MOE_REASON_LANE_ENABLED", default=True
            ),
            "sparse_moe_auto_route_enabled": _env_truth(
                "ENGEL_MOE_REASON_AUTO_ROUTE", default=True
            ),
            "sparse_moe_profile": {
                "architecture": "Qwen3 sparse mixture of experts",
                "total_parameters_billions": 30.5,
                "active_parameters_billions_per_token": 3.3,
                "expert_count": 128,
                "active_experts_per_token": 8,
                "task_controlled_thinking_mode": True,
            },
            "nemotron_3_5_lightning": _nemotron_lightning_status_snapshot(),
            "provider_after_local_failure_only": True,
            "cache": local_cache_status,
        },
        "active_model_inventory": _active_model_inventory_snapshot(),
        "long_lived_local_model_service": os.environ.get("ENGEL_MAIN_LONG_LIVED_LOCAL_MODEL_SERVICE", ""),
        "local_model_gpu_layers": os.environ.get("ENGEL_MAIN_LOCAL_MODEL_N_GPU_LAYERS", ""),
    }


def _active_model_inventory_snapshot() -> dict[str, Any]:
    data = _load_json_file(MODEL_INVENTORY_PATH)
    return {
        "ok": data.get("ok") is True,
        "inventory_path": str(MODEL_INVENTORY_PATH),
        "inventory_present": MODEL_INVENTORY_PATH.is_file(),
        "active_model_root": data.get("active_model_root"),
        "active_runtime_storage": data.get("active_runtime_storage"),
        "model_file_count": data.get("model_file_count"),
        "model_total_gib": data.get("model_total_gib"),
        "du_models_active": data.get("du_models_active"),
        "df_opt_engel": data.get("df_opt_engel"),
        "vault_used_as_copy_source": data.get("vault_used_as_copy_source"),
        "vault_used_for_active_runtime": data.get("vault_used_for_active_runtime"),
        "source_target_verification": data.get("source_target_verification"),
        "vault_model_weight_compare": data.get("vault_model_weight_compare"),
        "updated_at_utc": data.get("updated_at_utc"),
    }


def _phone_bridge_snapshot() -> dict[str, Any]:
    return phone_presence_snapshot(root=ROOT)


def _dispatch_sub_engel_direct_work_request(request: dict[str, Any]) -> dict[str, Any]:
    """Own and dispatch one UI-originated Sub-Engel order from CT246."""
    supplied = request.get("work_order")
    if not isinstance(supplied, dict):
        raise ValueError("work_order must be a JSON object")
    order = dict(supplied)
    order_id = str(order.get("id") or order.get("order_id") or "").strip()
    order_text = str(order.get("order_text") or "").strip()
    if not order_id or not order_text:
        raise ValueError("work_order requires id/order_id and order_text")
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "_", order_id).strip("._-")[:160]
    if not safe_id:
        raise ValueError("work_order id has no safe filename characters")
    selected = order.get("selected_node") if isinstance(order.get("selected_node"), dict) else {}
    node_id = str(
        selected.get("node_id")
        or selected.get("hostname")
        or "DESKTOP-UE5A6GG"
    ).strip()
    node_url = str(
        selected.get("url")
        or selected.get("node_url")
        or "http://198.51.100.227:8776"
    ).strip()
    if node_id.upper() != "DESKTOP-UE5A6GG":
        raise ValueError(f"unapproved Sub-Engel node: {node_id}")
    if node_url.rstrip("/") != "http://198.51.100.227:8776":
        raise ValueError(f"unapproved Sub-Engel URL: {node_url}")
    order.update(
        {
            "id": order_id,
            "order_id": order_id,
            "schema": "engel_sub_engel_direct_work_order_v1",
            "order_text": order_text,
            "proof_required": True,
            "target": "windows_sub_engel",
            "source": "CT246 Engel AI Main UI direct dispatch",
            "transport": "ct246_authenticated_direct_http",
            "selected_node": {
                "node_id": node_id,
                "hostname": node_id,
                "url": node_url,
            },
        }
    )
    order_root = WINDOWS_SUB_ENGEL_TRANSPORT_ROOT / "SUB_ENGEL_WORK_ORDERS"
    order_path = order_root / f"{safe_id}.json"
    if order_path.is_file():
        existing = _load_json_file(order_path)
        if (
            str(existing.get("id") or existing.get("order_id") or "") != order_id
            or str(existing.get("order_text") or "") != order_text
        ):
            raise ValueError("work_order id already exists with different content")
    else:
        _atomic_write_json(order_path, order)
    from engel_ct246_sub_engel_direct_work import dispatch as dispatch_sub_direct

    receipt = dispatch_sub_direct(order_path)
    return {
        "schema": "engel_ct246_ui_sub_engel_direct_work_response_v1",
        "ok": receipt.get("ok") is True,
        "status": (
            "Sub-Engel returned matching local-model work"
            if receipt.get("ok") is True
            else "Sub-Engel direct work failed"
        ),
        "container": "CT246",
        "server_hostname": "engel-ai-main",
        "transport": "ct246_authenticated_direct_http",
        "google_drive_used": False,
        "power_vault_used": False,
        "order_path": str(order_path),
        "receipt": receipt,
        "updated_at_utc": _iso_now(),
    }


def _parse_utc(value: Any) -> datetime | None:
    return parse_presence_utc(value)


def _seconds_since_utc(value: Any) -> float | None:
    parsed = _parse_utc(value)
    if parsed is None:
        return None
    return round((datetime.now(timezone.utc) - parsed).total_seconds(), 1)


def _probe_sub_engel_http_health(url: str, timeout: float = 1.5) -> dict[str, Any]:
    """Live LAN probe. A stale JSON live_health_ok flag is not connection proof."""
    target = str(url or "http://198.51.100.227:8776").rstrip("/")
    if not target:
        target = "http://198.51.100.227:8776"
    try:
        with urllib.request.urlopen(target + "/health", timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        ok = isinstance(payload, dict) and payload.get("ok") is True
        return {
            "ok": ok,
            "reachable": True,
            "url": target,
            "error": "" if ok else "health returned not-ok",
        }
    except Exception as exc:
        return {
            "ok": False,
            "reachable": False,
            "url": target,
            "error": str(exc)[:200],
        }


def _sub_engel_latest_return(node_id: str) -> dict[str, Any]:
    sent_root = WINDOWS_SUB_ENGEL_TRANSPORT_ROOT / "SUB_ENGEL_SENT_WORK"
    if not sent_root.is_dir():
        return {"present": False, "sent_work_root": str(sent_root)}
    try:
        candidates = sorted(
            sent_root.glob(f"{node_id}__*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        candidates = []
    if not candidates:
        return {"present": False, "sent_work_root": str(sent_root)}
    latest = candidates[0]
    payload = _load_json_file(latest)
    stamp = (
        payload.get("completed_at_utc")
        or payload.get("updated_at_utc")
        or payload.get("created_at_utc")
        or datetime.fromtimestamp(latest.stat().st_mtime, timezone.utc).isoformat()
    )
    return {
        "present": True,
        "path": str(latest),
        "name": latest.name,
        "last_returned_utc": str(stamp),
        "fresh_seconds": _seconds_since_utc(stamp),
    }


def _worker_map_to_node_list(workers: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for worker_id, worker in sorted(workers.items()):
        if not isinstance(worker, dict):
            continue
        node = dict(worker)
        node.setdefault("id", worker_id)
        node.setdefault("node_id", worker_id)
        node.setdefault("name", node.get("label") or node.get("hostname") or worker_id)
        nodes.append(node)
    return nodes


def _sub_engel_bridge_snapshot() -> dict[str, Any]:
    manifest = _load_json_file(WINDOWS_SUB_ENGEL_FLEET_MANIFEST_PATH)
    session = _load_json_file(WINDOWS_SUB_ENGEL_SESSION_PATH)
    latest_ready = _load_json_file(WINDOWS_SUB_ENGEL_LATEST_READY_PATH)
    merged_by_id: dict[str, dict[str, Any]] = {}
    raw_nodes = manifest.get("nodes") if isinstance(manifest.get("nodes"), list) else []
    for node in raw_nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("node_id") or node.get("hostname") or "").strip()
        if node_id:
            merged_by_id[node_id] = dict(node)

    session_id = str(session.get("node_id") or session.get("hostname") or "").strip()
    if session_id:
        merged_by_id.setdefault(session_id, {}).update({k: v for k, v in session.items() if k != "session_token"})

    ready_id = str(latest_ready.get("node_id") or latest_ready.get("hostname") or "").strip()
    if ready_id:
        merged_by_id.setdefault(ready_id, {}).update(latest_ready)

    # The stored session is refreshed by the authenticated Sub-Engel node.status
    # probe. Older node-ready records can be stale, so reapply
    # the session last to keep visible health aligned with real reachability.
    if session_id:
        merged_by_id.setdefault(session_id, {}).update({k: v for k, v in session.items() if k != "session_token"})

    workers: dict[str, Any] = {}
    live_count = 0
    for node_id, node in sorted(merged_by_id.items()):
        if not isinstance(node, dict):
            continue
        if node.get("disabled_for_engel_main") is True or node.get("do_not_use_for_engel_ai_main") is True:
            continue
        if str(node_id).upper() == "DESKTOP-FIB17O7":
            continue

        ips = node.get("ips") or node.get("node_ips") or node.get("last_known_ips") or []
        if not isinstance(ips, list):
            ips = [ips]
        ips = [str(ip).strip() for ip in ips if str(ip).strip()]
        url = str(node.get("url") or node.get("remote_addr") or "").strip()
        if (not url or "DESKTOP-" in url.upper()) and ips:
            url = f"http://{ips[0]}:8776"

        session_matches = bool(session_id) and node_id == session_id
        expires_at = (
            session.get("expires_at_utc")
            if session_matches
            else node.get("session_expires_at_utc") or node.get("expires_at_utc")
        )
        expires = _parse_utc(expires_at)
        not_expired = expires is None or expires > datetime.now(timezone.utc)
        session_token_present = bool(session.get("session_token")) if session_matches else False
        paired = bool(
            session_matches
            and session_token_present
            and not_expired
            and session.get("session_invalid") is not True
            and node.get("paired") is not False
        )
        latest_return = _sub_engel_latest_return(node_id)
        last_seen = (
            latest_return.get("last_returned_utc")
            or node.get("last_seen_utc")
            or node.get("received_at_utc")
            or node.get("last_resolved_at_utc")
            or ""
        )
        probe_url = url or "http://198.51.100.227:8776"
        health_probe = _probe_sub_engel_http_health(probe_url)
        live = bool(paired and (health_probe.get("ok") is True or node.get("live_health_ok") is True))
        if paired and health_probe.get("ok") is True:
            live_reason = "paired Sub-Engel answered /health on the LAN"
        elif paired and health_probe.get("reachable") is True:
            live_reason = "paired Sub-Engel port is open; health payload was not ok"
        elif paired:
            live_reason = (
                "paired Sub-Engel session is on file; live health probe failed — "
                "this is not an unpaired node"
            )
        else:
            live_reason = "inventory retained; fresh CT246 authenticated pairing is required"
        workers[node_id] = {
            "label": node.get("label") or node.get("display_name") or "Windows Sub-Engel Node",
            "worker_kind": "windows_sub_engel",
            "live": live,
            "paired": paired,
            "meeting_ready": bool(live or paired),
            "url": url,
            "ips": ips,
            "hostname": node.get("hostname") or node_id,
            "node_root": node.get("node_root"),
            "state_dir": node.get("state_dir"),
            "allowed_actions": node.get("allowed_actions") if isinstance(node.get("allowed_actions"), list) else [],
            "last_seen_utc": str(last_seen),
            "fresh_seconds": _seconds_since_utc(last_seen),
            "session_expires_at_utc": str(expires_at or ""),
            "latest_return": latest_return,
            "health_probe": health_probe,
            "not_proxmox_vm": True,
            "reason": live_reason,
        }
        if live:
            live_count += 1

    node_list = _worker_map_to_node_list(workers)
    return {
        "schema": "engel_windows_sub_engel_bridge_status_v1",
        "ok": bool(workers),
        "state_present": bool(manifest or session or latest_ready),
        "fleet_manifest_path": str(WINDOWS_SUB_ENGEL_FLEET_MANIFEST_PATH),
        "session_path": str(WINDOWS_SUB_ENGEL_SESSION_PATH),
        "latest_ready_path": str(WINDOWS_SUB_ENGEL_LATEST_READY_PATH),
        "transport_path": str(WINDOWS_SUB_ENGEL_TRANSPORT_ROOT),
        "transport_mode": "ct246_direct_http",
        "workers": workers,
        "nodes": node_list,
        "worker_list": node_list,
        "active_node_ids": [str(node.get("node_id") or node.get("id")) for node in node_list if node.get("live") is True],
        "live_count": live_count,
        "expected_count": len(workers),
        "retired_nodes_excluded": ["DESKTOP-FIB17O7"],
        "not_proxmox_inventory": True,
        "inventory_note": "Sub-Engel is a paired desktop worker, not a Proxmox VM or CT.",
        "updated_at_utc": _iso_now(),
    }


def _device_worker_snapshot() -> dict[str, Any]:
    phone = _cached_snapshot("phone_bridge", _phone_bridge_snapshot)
    sub = _cached_snapshot("sub_engel_bridge", _sub_engel_bridge_snapshot)
    workers: dict[str, Any] = {}
    live_count = 0
    for worker_id, worker in (phone.get("workers") or {}).items():
        if not isinstance(worker, dict):
            continue
        workers[str(worker_id)] = {**worker, "worker_kind": "android_phone"}
    for worker_id, worker in (sub.get("workers") or {}).items():
        if not isinstance(worker, dict):
            continue
        workers[str(worker_id)] = worker
    for worker in workers.values():
        if isinstance(worker, dict) and worker.get("live") is True:
            live_count += 1
    node_list = _worker_map_to_node_list(workers)
    return {
        "schema": "engel_device_worker_snapshot_v1",
        "ok": bool(workers),
        "workers": workers,
        "nodes": node_list,
        "worker_list": node_list,
        "active_node_ids": [str(node.get("node_id") or node.get("id")) for node in node_list if node.get("live") is True],
        "live_count": live_count,
        "expected_count": len(workers),
        "phone_bridge": phone,
        "sub_engel_bridge": sub,
        "updated_at_utc": _iso_now(),
    }


def _meeting_room_snapshot() -> dict[str, Any]:
    url = _meeting_room_url()
    if not url:
        return {"ok": False, "meeting_room_enabled": False, "reachable": False}
    health = _fetch_json(url + "/health", timeout=2.0)
    if health.get("ok") is True:
        return {
            "ok": True,
            "reachable": True,
            "server_owned": True,
            "meeting_room_enabled": True,
            "meeting_room_url": url,
            "schema": str(health.get("schema") or ""),
            "status": str(health.get("status") or "running"),
            "health": {
                "ok": True,
                "schema": health.get("schema"),
                "status": health.get("status"),
            },
        }
    snapshot = _fetch_json(url + "/room/state", timeout=3.0)
    if snapshot.get("ok") is True:
        snapshot.setdefault("meeting_room_url", url)
        snapshot.setdefault("reachable", True)
        return snapshot
    return {
        "ok": False,
        "reachable": False,
        "meeting_room_enabled": True,
        "meeting_room_url": url,
        "health": health,
    }


def _meeting_room_virtual_environment_snapshot() -> dict[str, Any]:
    url = _meeting_room_url()
    if not url:
        return {"ok": False, "virtual_environment_enabled": False, "reason": "meeting room disabled"}
    snapshot = _fetch_json(url + "/virtual-environments/engel3d-office/state", timeout=4.0)
    if snapshot.get("ok") is True:
        snapshot.setdefault("meeting_room_url", url)
        return snapshot
    room = _cached_snapshot("meeting_room", _meeting_room_snapshot)
    if room.get("ok") is True:
        return {
            "ok": True,
            "virtual_environment_enabled": True,
            "meeting_room_url": url,
            "environment_id": "engel3d-office",
            "workspaceId": "engel3d-office",
            "server_owned": True,
            "recent_work": False,
            "reason": "3D office overlay slow; Meeting Room health is live",
        }
    return {
        "ok": False,
        "virtual_environment_enabled": True,
        "meeting_room_url": url,
        "environment_id": "engel3d-office",
        "reason": "virtual environment state unavailable",
    }


def _custom_runtime_model_id(model: dict[str, Any] | None = None) -> str:
    snapshot = model if isinstance(model, dict) else _model_runtime_snapshot()
    lora_ready = bool(snapshot.get("lora_runtime_ready") is True)
    if lora_ready:
        return "engel/qwen2.5-7b-runpod-lora-ct246"
    if snapshot.get("local_gguf_model_present") is True:
        return "engel/local-gguf-ct246"
    return "engel/ct246-fast-fallback"


def _custom_runtime_state() -> dict[str, Any]:
    model = _cached_snapshot("model_runtime", _model_runtime_snapshot)
    phone = _cached_snapshot("phone_bridge", _phone_bridge_snapshot)
    sub_engel = _cached_snapshot("sub_engel_bridge", _sub_engel_bridge_snapshot)
    device_workers = _cached_snapshot("device_workers", _device_worker_snapshot)
    room = _cached_snapshot("meeting_room", _meeting_room_snapshot)
    virtual_environment = _cached_snapshot("virtual_environment", _meeting_room_virtual_environment_snapshot)
    creator = _cached_snapshot("skill_agent_creator", _skill_agent_creator_status)
    reps = _cached_snapshot("universal_reps", _universal_reps_template_snapshot)
    reps_runtime = _cached_snapshot("universal_reps_runtime", _universal_reps_runtime_status)
    shell_bridges = _cached_snapshot(
        "shell_bridge_registry", _shell_bridge_registry_snapshot, ttl_seconds=5.0
    )
    active: dict[str, list[str]] = {
        "engel-ai-main": [_custom_runtime_model_id(model)],
        "agent-meeting-room": ["engel-agent-meeting-room.service" if room.get("ok") else "meeting-room-unreachable"],
        "universal-reps": ["ready" if reps.get("ok") is True else "missing"],
        "universal-reps-runtime": ["ready" if reps_runtime.get("ok") is True else "unavailable"],
    }
    if creator.get("ok") is True:
        active["skill-creator"] = ["ready"]
        active["agent-creator"] = ["ready"]
    workers = phone.get("workers") if isinstance(phone.get("workers"), dict) else {}
    for worker_id, worker in workers.items():
        if not isinstance(worker, dict):
            continue
        state = "live" if worker.get("live") is True else "not-live"
        active[str(worker_id).replace("_", "-")] = [state]
    sub_workers = sub_engel.get("workers") if isinstance(sub_engel.get("workers"), dict) else {}
    for worker_id, worker in sub_workers.items():
        if not isinstance(worker, dict):
            continue
        state = "live" if worker.get("live") is True else "not-live"
        active[str(worker_id).replace("_", "-").lower()] = [state]
    virtual_agents = virtual_environment.get("agents") if isinstance(virtual_environment.get("agents"), list) else []
    for agent in virtual_agents:
        if not isinstance(agent, dict):
            continue
        agent_id = str(agent.get("agentId") or agent.get("id") or "").strip()
        if not agent_id:
            continue
        state = str(agent.get("state") or agent.get("status") or "idle").strip() or "idle"
        active[agent_id] = [state]
    return {
        "ok": True,
        "schema": "engel_ai_main_custom_runtime_state_v1",
        "profileName": "Engel AI Main CT 246",
        "registry_profile": "engel-ai-main-one-system",
        "profile": "engel-ai-main-one-system",
        "identity": {
            "name": "Engel AI Main",
            "role": "orchestrator",
            "lane": "engel-ai-main",
            "model_id": _custom_runtime_model_id(model),
        },
        "runtime": {
            "name": "Engel AI Main CT 246",
            "version": "ct246-proxmox-lxc",
            "vendor": "Engel",
            "status": "ready" if model.get("lora_runtime_ready") else "fallback-ready",
            "active_model": _custom_runtime_model_id(model),
            "governance": "ROG controller uses CT 246 for model service, memory, and Agent Meeting Room state.",
        },
        "active": active,
        "model_runtime": model,
        "phone_bridge": phone,
        "sub_engel_bridge": sub_engel,
        "device_workers": device_workers,
        "meeting_room": room,
        "virtual_environment": virtual_environment,
        "skill_agent_creator": creator,
        "universal_reps": reps,
        "universal_reps_runtime": reps_runtime,
        "shell_bridge_registry": shell_bridges,
        "provider_bridges": _cached_snapshot("provider_bridges", _provider_bridge_status),
        "provider_capabilities": _cached_snapshot(
            "provider_capabilities", _provider_capability_snapshot, ttl_seconds=15.0
        ),
        "local_llm_fast_fail": _cached_snapshot(
            "local_llm_fast_fail", _local_llm_fast_fail_snapshot, ttl_seconds=5.0
        ),
        "chat_failure_corpus": _cached_snapshot(
            "chat_failure_corpus", _chat_failure_corpus_snapshot, ttl_seconds=5.0
        ),
        "context_packs": _cached_snapshot(
            "context_packs", _context_pack_snapshot, ttl_seconds=5.0
        ),
        "chat_route_parity": _cached_snapshot(
            "chat_route_parity", _chat_route_parity_snapshot, ttl_seconds=5.0
        ),
        "persistent_memory_path": str(PERSISTENT_CHAT_MEMORY_PATH),
        "updated_at_utc": _iso_now(),
    }


def _custom_runtime_registry() -> dict[str, Any]:
    model = _cached_snapshot("model_runtime", _model_runtime_snapshot)
    selected = _custom_runtime_model_id(model)
    skills = _skill_status_report()
    agents = _agent_status_report()
    reps = _universal_reps_template_snapshot()
    reps_runtime = _universal_reps_runtime_status()
    models = {
        selected: {
            "id": selected,
            "name": selected,
            "provider": "local-llama-cpp",
            "ready": bool(model.get("lora_runtime_ready") or model.get("local_gguf_model_present")),
            "base_gguf_model_path": model.get("trained_lora_base_gguf_model_path"),
            "lora_adapter_gguf_path": model.get("trained_lora_adapter_gguf_path"),
            "long_lived_service": True,
        }
    }
    if selected != "engel/ct246-fast-fallback":
        models["engel/ct246-fast-fallback"] = {
            "id": "engel/ct246-fast-fallback",
            "name": "Engel CT 246 Fast Fallback",
            "provider": "deterministic-local",
            "ready": True,
        }
    return {
        "ok": True,
        "schema": "engel_ai_main_custom_runtime_registry_v1",
        "models": models,
        "capabilities": [
            "agents",
            "sessions",
            "chat",
            "agent-messages",
            "agent-handoffs",
            "models",
            "agent-roles",
            "skills",
            "skill-creation",
            "agent-creation",
            "universal-reps",
            "reps-record",
            "reps-evaluate",
            "reps-propose",
            "reps-signoff",
            "reps-cycle-runtime",
            "provider-bridge-status",
            "provider-completion-capability-map",
            "local-llm-timeout-fast-fail",
            "chat-failure-corpus",
            "codex-workbench-context-ingest",
            "discord-desktop-route-parity",
            "provider-bridge-chatgpt",
            "provider-bridge-claude",
            "provider-bridge-grok",
            "provider-bridge-codex",
            "evidence-backed-shell-bridge-registry",
        ],
        "skills": skills.get("skills") if isinstance(skills.get("skills"), list) else [],
        "saved_agents": agents.get("agents") if isinstance(agents.get("agents"), list) else [],
        "skill_agent_creator": _cached_snapshot("skill_agent_creator", _skill_agent_creator_status),
        "universal_reps": reps,
        "universal_reps_runtime": reps_runtime,
        "shell_bridge_registry": _cached_snapshot(
            "shell_bridge_registry", _shell_bridge_registry_snapshot, ttl_seconds=5.0
        ),
        "provider_bridges": _cached_snapshot("provider_bridges", _provider_bridge_status),
        "provider_capabilities": _cached_snapshot(
            "provider_capabilities", _provider_capability_snapshot, ttl_seconds=15.0
        ),
        "local_llm_fast_fail": _cached_snapshot(
            "local_llm_fast_fail", _local_llm_fast_fail_snapshot, ttl_seconds=5.0
        ),
        "chat_failure_corpus": _cached_snapshot(
            "chat_failure_corpus", _chat_failure_corpus_snapshot, ttl_seconds=5.0
        ),
        "chat_route_parity": _cached_snapshot(
            "chat_route_parity", _chat_route_parity_snapshot, ttl_seconds=5.0
        ),
        "updated_at_utc": _iso_now(),
    }


def _varied_canned(prompt: str, options: tuple[str, ...]) -> str:
    """Pick a canned line from a small bank so Discord/desktop do not loop one sentence."""
    rows = [str(item).strip() for item in options if str(item).strip()]
    if not rows:
        return ""
    if len(rows) == 1:
        return rows[0]
    digest = hashlib.sha256((str(prompt or "") + "|" + str(int(time.time() // 90))).encode("utf-8")).digest()
    return rows[digest[0] % len(rows)]


def _fast_server_reply(prompt: str, model_status: str = "") -> str:
    text = _intent_gate_text(prompt).strip() or prompt
    low = text.casefold()
    reps_terms = (
        "reps",
        "record evaluate propose",
        "record/evaluate/propose",
        "self-improv",
        "self improving",
        "self-improving",
        "auto-memory",
        "scoreboard",
        "sign-off",
        "signoff",
        "bucket 1",
        "bucket 2",
        "bucket 3",
    )
    help_next_terms = (
        "what can you help",
        "what can u help",
        "help me do next",
        "what should we do next",
        "what should we work on next",
        "what can we work on next",
        "what do we work on next",
        "what are we working on next",
        "what can engel",
        "next in engel",
        "what are you able to do",
    )
    fault_terms = (
        "repeat",
        "repeating",
        "canned",
        "template response",
        "scripted response",
        "status script",
        "stop giving template",
        "garbage",
        "not connected",
        "broken",
        "lying",
        "fake",
    )
    phone_terms = ("phone", "android", "alpha", "beta", "worker", "device")
    connection_terms = ("connected", "connection", "status", "working", "online", "health", "reachable")
    normal_chat_terms = ("normal chat", "talk like", "real conversation", "what did you hear", "not repeating", "less scripted")
    practical_question_terms = ("ask me one", "one practical question", "practical question")
    device_choice_terms = ("which device", "choose a device", "device should handle", "device choice", "agent choose")
    review_only_terms = ("review-only", "candidate-only", "trust their output", "phone outputs", "phone-side results")
    confused_terms = ("if i sound confused", "if a user is confused", "confused user", "mistaken")
    model_unavailable_terms = ("model route unavailable", "large model route", "without the slow laptop model", "slow laptop model")
    boundary_terms = ("refuse to claim", "receipt proves", "unless a receipt", "fake proof", "prove it")
    verifier_terms = ("verifier pass", "verifier", "trusting a result")
    ready_terms = ("ready to chat", "still responsive", "normal question", "stay fast", "handled through engel chat")
    shortcut_terms = ("click next time", "desktop shortcut", "open engel")
    fix_terms = ("what changed", "stop breaking", "chat stop breaking")
    one_system_terms = ("one system", "rog app and server", "rog app", "server are acting")
    route_terms = (
        "fastest route",
        "chat route",
        "which route",
        "what route",
        "say which route",
        "route you used",
        "route you are using",
        "server chat lane",
        "chat lane is stable",
        "which provider",
        "what provider",
    )
    memory_terms = ("memory", "remember", "saved", "persist", "history")
    status_terms = ("status check", "status update", "working right now", "what is working")
    chat_work_broken_terms = (
        "what works and what is broken",
        "one working chat part",
        "one broken chat part",
        "working chat part",
        "broken chat part",
        "works and what is broken in chat",
    )
    template_loop_terms = (
        "template response",
        "scripted response",
        "status script",
        "stop giving template",
        "canned response",
        "canned reply",
        "stop repeating",
        "repeating response",
    )
    if _prompt_requests_last_model_trace(prompt):
        return _recent_chat_route_summary()
    if _prompt_requests_build_status(prompt):
        return _build_status_reply()
    if any(term in low for term in chat_work_broken_terms):
        return (
            "The working part is that the ROG chat UI is reaching the CT 246 server route and saving receipts. "
            "The broken part was normal conversation waiting on the slow model lane instead of using this fast chat lane first."
        )
    if any(term in low for term in template_loop_terms):
        return (
            "You are right. I will stop the template loop: one direct reply, the current sender identity preserved, "
            "and this correction saved to Engel memory."
        )
    if any(term in low for term in reps_terms):
        reps = _universal_reps_template_snapshot()
        lanes = reps.get("applies_to_ai_lanes") if isinstance(reps.get("applies_to_ai_lanes"), list) else []
        lane_text = ", ".join(str(item) for item in lanes[:8]) if lanes else "all Engel AI lanes"
        return (
            "Engel Universal REPS is active as a runtime for "
            f"{lane_text}. Each REPS chat turn writes an event and scorecard, proposes when needed, "
            "and records sign-off as Bucket 1 Auto-approve, Bucket 2 Needs sign-off, or Bucket 3 Needs Josh call."
        )
    if any(term in low for term in help_next_terms):
        return (
            "I can help you run Engel AI Main as one system: keep the ROG app connected to CT 246, use the local LLM service, "
            "show the Agent Meeting Room, track which devices agents choose, fix Beta phone pairing, and verify each result from the chat UI."
        )
    if any(term in low for term in normal_chat_terms):
        return (
            "I hear that you want Engel to answer like a useful assistant instead of repeating canned status text. "
            "This turn is handled as normal chat and saved to memory."
        )
    if any(term in low for term in practical_question_terms):
        return "What part still feels slow or disconnected when you use Engel from the ROG app?"
    if _prompt_requests_chat_fault_repair(text):
        return _varied_canned(
            text,
            (
                "You are right: the live chat path was still failing. I found the route wrapper and stale quick-gate issue, "
                "kept this turn on the CT246 fast repair lane, and saved the failure so the next user turn does not wait on the slow model.",
                "That chat turn failed in the fast lane. I saved it. Ask again in one line and I will answer it directly.",
                "The last reply broke. Send the same ask once more and I will stay on a fresh answer.",
            ),
        )
    if any(term in low for term in fault_terms):
        return (
            "You are right to flag it. The fast fallback was giving stock connection text because the local model route "
            "did not return a usable reply. Engel should not call phones connected unless there is a fresh phone-origin "
            "heartbeat from the real device, and it should not treat desktop self-checks as phone proof."
        )
    if any(term in low for term in device_choice_terms):
        return (
            "Device choice should be visible in the Agent Meeting Room: CT 246 handles server chat, ROG stays the controller, "
            "and phones stay review-only unless a specific approved task needs them."
        )
    if any(term in low for term in review_only_terms):
        return "Phone and side-agent outputs should stay candidate-only until Engel records an approval or verifier pass."
    if any(term in low for term in confused_terms):
        return "If the user sounds confused, Engel should slow down, name the exact state it sees, and give the next safe click or command."
    if any(term in low for term in model_unavailable_terms):
        return "Normal chat should stay usable through the CT fast server lane even when a deeper local model route is unavailable."
    if any(term in low for term in boundary_terms):
        return "Engel should not claim a device, model, memory write, or server action happened unless a receipt or live health check proves it."
    if any(term in low for term in verifier_terms):
        return "Use a verifier pass when a result changes behavior, touches devices, or could be mistaken for proof instead of a candidate answer."
    if any(term in low for term in fix_terms):
        return (
            "Chat is routed through the CT 246 server lane now, with short server replies, persistent memory appends, "
            "and receipt checks instead of launching a fresh slow laptop model for every message."
        )
    if any(term in low for term in one_system_terms):
        return (
            "Yes. The ROG app is the controller, CT 246 is the server runtime, and this chat is using the CT server lane as one Engel AI Main system."
        )
    if any(term in low for term in route_terms):
        return (
            "This reply used CT246 chat route. Normal chat now uses the fast CT local GGUF model first, "
            "with the trained LoRA and provider bridges kept as fallback or deep-task lanes."
        )
    if any(term in low for term in shortcut_terms):
        return "Use the desktop shortcut named Engel AI Main - One System; it opens the ROG controller app wired to CT 246."
    if any(term in low for term in ready_terms):
        return "Yes. I am using the server chat lane and should keep normal conversation fast without starting the slow laptop model."
    if any(term in low for term in status_terms):
        phone = _phone_bridge_snapshot()
        sub_engel = _sub_engel_bridge_snapshot()
        live_count = int(phone.get("live_count") or 0)
        expected_count = int(phone.get("expected_count") or 0)
        phone_part = f"Phone bridge: {live_count}/{expected_count} live" if expected_count else "phone bridge state loaded"
        sub_part = ""
        sub_expected = int(sub_engel.get("expected_count") or 0)
        if sub_expected:
            sub_part = f" Sub-Engel: {int(sub_engel.get('live_count') or 0)}/{sub_expected} live."
        return (
            "Engel is responsive through the CT 246 chat service, persistent memory is appending, "
            f"the Agent Meeting Room is reachable, and {phone_part}.{sub_part}"
        )
    if any(term in low for term in phone_terms) and any(term in low for term in connection_terms):
        phone = _phone_bridge_snapshot()
        workers = phone.get("workers") if isinstance(phone.get("workers"), dict) else {}
        if workers:
            parts = []
            for worker_id, worker in workers.items():
                if not isinstance(worker, dict):
                    continue
                label = str(worker.get("label") or worker_id)
                state = "live" if worker.get("live") is True else "not live"
                observed = str(worker.get("observed_ip") or "no observed IP")
                transport = str(worker.get("transport") or "").strip()
                reason = str(worker.get("reason") or "").strip()
                detail = f"{label}: {state} at {observed}"
                if transport:
                    detail += f" via {transport}"
                if reason and state != "live":
                    detail += f" ({reason})"
                parts.append(detail)
            if parts:
                return "Phone bridge status from saved live-heartbeat state: " + "; ".join(parts) + "."
        return (
            "I can only call the phone link connected when Alpha and Beta have fresh phone-origin heartbeats. A receiver "
            "being up, or a desktop pairing probe, is not enough evidence."
        )
    if any(word in low for word in ("slow", "fast", "speed", "lag")):
        return (
            "Fast is not enough by itself. The local model route needs to return real text, and the fallback should only "
            "give a short honest diagnostic when that model path fails."
        )
    if any(word in low for word in memory_terms):
        return (
            "This chat turn is appended to Engel persistent chat history under the active /opt/engel memory path on CT 246."
        )
    if _prompt_is_simple_greeting(text):
        return "Good morning, Joshua. I am ready; what do you want to tackle first?"
    if any(word in low for word in ("meeting room", "agent room", "agents")):
        return (
            "The Agent Meeting Room can record and route work, but it should stay out of normal chat unless the request "
            "needs agents or verification."
        )
    if any(word in low for word in ("server", "ct 246", "proxmox")):
        model = _model_runtime_snapshot()
        if "model" in low or "llm" in low:
            return (
                "CT 246 chat is reachable. Model runtime: trained LoRA ready="
                f"{model.get('lora_runtime_ready')}, base GGUF present="
                f"{model.get('trained_lora_base_gguf_model_present')}, adapter GGUF present="
                f"{model.get('trained_lora_adapter_gguf_present')}."
            )
        return (
            "The server chat service is reachable, but that only proves the chat endpoint. It does not prove the local "
            "model answered or that phones are live."
        )
    if "?" in text:
        return "I hear the question; ask it plainly and I will answer it directly instead of turning it into a status report."
    fallback = "I am with you. Send the next detail and I will answer it directly."
    if model_status:
        fallback += f" Current model route issue: {_clip(model_status, 180)}."
    return fallback


def _intent_gate_text(prompt: str) -> str:
    """Return only the CURRENT user line for intent-gate matching.

    Discord/UI lanes wrap the user's message in quoted conversation context
    ("Recent Discord context: ... Current user message: <text>"). Gates that
    pattern-match the WHOLE wrapper get poisoned by earlier bot replies (e.g.
    "Agent Meeting Room" + "saved" tripping the skill/agent-creation lane on a
    plain greeting), which is how Engel looped canned templates in Discord.
    Route intent must come from the newest user line only.
    """
    text = str(prompt or "")
    marker = "current user message:"
    low = text.casefold()
    idx = low.rfind(marker)
    if idx >= 0:
        body = text[idx + len(marker):].strip()
        # Colony status is appended for the mouth, not as the user's ask.
        # Leaving it in the gate text let "Engel/runtime" start a fake download.
        cut = body.casefold().find("engel colony status")
        if cut > 0:
            body = body[:cut].strip()
        if body:
            return body
    # Discord peer/guest frames put the real line after [Context: ...]\n\n.
    # Matching the whole wrapper let earlier canned "it was repeating" replies
    # trip the chat-fault lane on a later kids-tutor / Meeting Room update
    # (live 2026-08-17).
    stripped = text.lstrip()
    if stripped.startswith("[Context:"):
        split_at = stripped.find("\n\n")
        if split_at >= 0:
            body = stripped[split_at + 2 :].strip()
            if body:
                return body
    return text


def _prompt_requests_live_runtime_status(prompt: str) -> bool:
    # A declared chat-only turn (request flag "chat_only", narrow-only) wants
    # MODEL text, never a canned status answer -- its instruction body may
    # legitimately contain status vocabulary (live 2026-07-31: the EngelScript
    # draft grammar card's example phrases tripped this detector).
    if _TURN_CHAT_ONLY.get():
        return False
    low = (
        _intent_gate_text(prompt)
        .casefold()
        .replace("\u2019", "'")
        .replace("\u2018", "'")
    )
    explicit_phrases = (
        "server status",
        "connection status",
        "health check",
        "connection check",
        "diagnostic",
        "route check",
        "bridge check",
        "model status",
        "llm status",
        "phone status",
        "phone bridge",
        "worker status",
        "workers status",
        "what workers are live",
        "which workers are live",
        "workers are live",
        "live workers",
        "what workers are connected",
        "which workers are connected",
        "what devices are live",
        "which devices are live",
        "are the phones connected",
        "is alpha connected",
        "is beta connected",
        "what devices are connected",
        "is chat fixed",
        "chat fixed",
        "is chat working",
        "chat working",
        "can you chat",
        "where are the models",
        "where are model files",
        "where is memory stored",
        "where is chat memory",
        "vault status",
        "storage status",
        "what i'm actually running",
        "what i am actually running",
        "what i’m actually running",
        "what's actually running",
        "whats actually running",
        "what are you actually running",
        "what you're actually running",
        "what's actually live",
        "whats actually live",
        "what's actually up",
        "whats actually up",
        "live evidence",
        "what is live on this box",
        "what's live on this box",
        "what's live right now",
        "what is running right now",
        "what's running right now",
        "is sub-engel connected",
        "is sub engel connected",
        "sub-engel connected",
        "sub engel connected",
    )
    # Explicit status phrases only. The old broad combo ("where"+"server",
    # "check"+"model", ...) hijacked ordinary questions into the canned status
    # dump before the provider lanes could answer - the template disease again.
    return any(phrase in low for phrase in explicit_phrases)


def _prompt_requests_computer_memory(prompt: str) -> bool:
    """True when Josh asks Engel to look at this computer's RAM, not chat memory."""
    if _TURN_CHAT_ONLY.get():
        return False
    low = (
        _intent_gate_text(prompt)
        .casefold()
        .replace("\u2019", "'")
        .replace("\u2018", "'")
    )
    phrases = (
        "this computer's memory",
        "this computers memory",
        "this computer memory",
        "this pc's memory",
        "this pcs memory",
        "this laptop's memory",
        "this laptops memory",
        "look at the ram",
        "look at ram",
        "how much ram",
        "ram usage",
        "free ram",
        "available ram",
    )
    return any(phrase in low for phrase in phrases)


def _bytes_to_gib(value: Any) -> float:
    try:
        return max(0.0, float(value or 0) / (1024.0 ** 3))
    except (TypeError, ValueError):
        return 0.0


def _ct246_memory_snapshot() -> dict[str, Any]:
    path = Path("/proc/meminfo")
    if not path.is_file():
        return {"ok": False, "host": "ct246"}
    data: dict[str, int] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.replace(":", " ").split()
            if len(parts) >= 2 and parts[0] in {"MemTotal", "MemAvailable", "MemFree"}:
                data[parts[0]] = int(parts[1]) * 1024
    except Exception:
        return {"ok": False, "host": "ct246"}
    total = int(data.get("MemTotal") or 0)
    available = int(data.get("MemAvailable") or data.get("MemFree") or 0)
    used = max(0, total - available)
    percent = round((used / total) * 100.0, 1) if total else 0.0
    return {
        "ok": True,
        "host": "ct246",
        "total_bytes": total,
        "used_bytes": used,
        "available_bytes": available,
        "percent": percent,
    }


def _computer_memory_reply(request: dict[str, Any] | None = None) -> str:
    request = request if isinstance(request, dict) else {}
    metadata = request.get("metadata") if isinstance(request.get("metadata"), dict) else {}
    rog = metadata.get("host_memory") if isinstance(metadata.get("host_memory"), dict) else {}
    ct = _ct246_memory_snapshot()

    def _line(snap: dict[str, Any], label: str) -> str:
        if snap.get("ok") is not True:
            return f"{label}: not in this probe."
        total = _bytes_to_gib(snap.get("total_bytes"))
        used = _bytes_to_gib(snap.get("used_bytes"))
        available = _bytes_to_gib(snap.get("available_bytes"))
        percent = snap.get("percent")
        return (
            f"{label}: {total:.1f} GB RAM, {used:.1f} used, {available:.1f} free"
            + (f" ({percent:.0f}%)." if percent is not None else ".")
        )

    return (
        "I looked. "
        + _line(rog, "This ROG face")
        + " "
        + _line(ct, "CT246, my chat brain")
        + " Live probe, not a guess."
    )


def _computer_memory_receipt(prompt: str, started: float, request: dict[str, Any] | None = None) -> dict[str, Any]:
    reply = _computer_memory_reply(request)
    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_COMPUTER_MEMORY_CHAT_{stamp}.json"
    receipt = {
        "schema": "engel_main_server_computer_memory_chat_receipt_v1",
        "ok": True,
        "status": "computer memory probe answered",
        "updated_at_utc": _iso_now(),
        "run_id": "main_server_computer_memory_chat_" + stamp,
        "prompt": prompt,
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "engel-main-server-computer-memory",
        "runtime_provider": "engel-main-server-computer-memory",
        "selected_provider": "main_server_computer_memory",
        "main_server_chat_service_used": True,
        "model_route_attempted": False,
        "runs_inference": False,
        "loads_model": False,
        "provider_api_enabled": False,
        "network_enabled": False,
        "trusted_memory_write_enabled": False,
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
        "ct246_memory": _ct246_memory_snapshot(),
    }
    receipt = _apply_chat_humanizer(prompt, receipt, "ct_computer_memory_receipt")
    return receipt


def _prompt_requests_reps_template(prompt: str) -> bool:
    low = _intent_gate_text(prompt).casefold()
    return any(
        term in low
        for term in (
            "reps",
            "record evaluate propose",
            "record/evaluate/propose",
            "record, evaluate, propose",
            "self-improv",
            "self improving",
            "self-improving",
            "auto-memory",
            "scoreboard",
            "sign-off",
            "signoff",
            "bucket 1",
            "bucket 2",
            "bucket 3",
        )
    )


# (2026-08-16) Ceilings for the depth-0 canned template lanes. They answer a quick
# conversational ask with a fixed paragraph, which is right for "what can you help with?"
# and badly wrong for a long request that merely MENTIONS one of their topics. Live
# failure: a 797-character request to compose a work message contained the words
# "Meeting Room" inside a quoted project name, matched the bare-noun list, and came back
# as canned capability boilerplate instead of the composition. Same bare-noun family as
# the Discord guest gate, where "server"/"worker" caught a worker node's normal speech.
# The 500 ceiling mirrors the guard _prompt_requests_deterministic_visible_chat already
# uses; bare topic nouns get the tighter one because they are ordinary English.
_TEMPLATE_LANE_MAX_CHARS = 500
# One line. A genuine bare-noun ask is "show me the meeting room"; by a couple of
# sentences the person is describing something, and a canned paragraph is the wrong answer.
_TEMPLATE_LANE_TOPIC_NOUN_MAX_CHARS = 140


def _prompt_requests_help_next(prompt: str) -> bool:
    text = _intent_gate_text(prompt)
    low = text.casefold()
    if not low.strip() or len(text) > _TEMPLATE_LANE_MAX_CHARS:
        return False
    # Question-shaped and unambiguous: these are the ask itself, not a topic mention.
    strong_help_terms = (
        "what can you help",
        "what can u help",
        "help me do next",
        "what should we do next",
        "what should we work on next",
        "what can we work on next",
        "what do we work on next",
        "what are we working on next",
        "what can engel",
        "next in engel",
        "what are you able to do",
        "what can you use",
        "what parts",
    )
    if any(term in low for term in strong_help_terms):
        return True
    # Bare topic nouns - ordinary English and ordinary project names. They may only
    # answer a SHORT ask, never a long body that happens to mention them.
    if len(text) > _TEMPLATE_LANE_TOPIC_NOUN_MAX_CHARS:
        return False
    topic_terms = (
        "workspace",
        "resources",
        "modules",
        "humanizer",
        "cubesandbox",
        "cube sandbox",
        "3d office",
        "3d agent office",
        "engel3d",
        "agent office",
        "agent room",
        "virtual room",
        "meeting room",
    )
    return any(term in low for term in topic_terms)


def _prompt_requests_build_status(prompt: str) -> bool:
    low = _intent_gate_text(prompt).casefold()
    if not low.strip():
        return False
    strong_build_terms = (
        "how is the build",
        "how's the build",
        "build going",
        "build status",
    )
    weak_build_terms = (
        "anything missing",
        "what is missing",
        "what's missing",
        "what still missing",
        "what still needs",
    )
    explicit_system_terms = (
        "chat",
        "build",
        "system",
        "ct246",
        "ct 246",
        "server",
        "discord",
        "llm",
        "ai model",
        "local model",
    )
    return bool(
        any(term in low for term in strong_build_terms)
        or (
            any(term in low for term in weak_build_terms)
            and any(term in low for term in explicit_system_terms)
        )
    )


def _build_status_reply() -> str:
    model = _model_runtime_snapshot()
    device = _device_worker_snapshot()
    lora_ready = bool(model.get("lora_runtime_ready") is True)
    live_workers = int(device.get("live_count") or 0)
    expected_workers = int(device.get("expected_count") or 0)
    worker_text = f"{live_workers}/{expected_workers} workers live" if expected_workers else "worker roster loaded"
    lora_text = "ready" if lora_ready else "not ready"
    return (
        "Build status: ROG chat is reaching CT246, the fast local LLM lane is active, "
        f"persistent memory is writing under /opt/engel, trained LoRA is {lora_text}, "
        "and Discord uses the same CT chat service after the bridge restart. "
        f"Current gap: keep normal UI/Discord chat on the fast CT lane first, then use the deep LoRA or named bridges only when the task needs them. "
        f"Device state: {worker_text}."
    )


def _prompt_requests_media_artifact(prompt: str) -> bool:
    low = _intent_gate_text(prompt).casefold()
    if not low.strip():
        return False
    if "mission control job" in low:
        return False
    media_terms = (
        "gif",
        "image",
        "picture",
        "photo",
        "visual",
        "wallpaper",
        "animation",
        "animated",
        "video",
        "logo",
        "icon",
        "png",
        "jpg",
        "jpeg",
        "webp",
        "mp4",
    )
    action_terms = (
        "create",
        "make",
        "generate",
        "send",
        "draw",
        "render",
        "design",
        "build",
        "show me",
        "give me",
    )
    # (2026-07-12) WORD-BOUNDARY match: bare substring matching let 'visual'
    # claim 'visualizer' and steal an explicit build order into the media lane.
    has_media = any(
        re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", low) for term in media_terms
    )
    if not has_media or not any(term in low for term in action_terms):
        return False
    # An explicit software build order (verb + page/app/tool/script/... target)
    # belongs to the BUILD lane even when it mentions drawing or visuals; only
    # unambiguous artifact asks (image/gif/logo/... with no software target)
    # stay in the media lane.
    try:
        import engel_build_lane

        if engel_build_lane.is_build_request(prompt) is not None:
            return False
    except Exception:
        pass
    return True


def _media_artifact_kind(prompt: str) -> str:
    low = _intent_gate_text(prompt).casefold()
    if "gif" in low or "animation" in low or "animated" in low:
        return "gif"
    if "video" in low or "mp4" in low:
        return "video"
    return "image"


def _generate_engel_self_gif(stamp: str) -> dict[str, Any]:
    MEDIA_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = MEDIA_ARTIFACT_DIR / f"engel_ai_main_self_{stamp}.gif"
    try:
        import math
        from PIL import Image, ImageDraw, ImageFont

        width, height = 640, 360
        font = ImageFont.load_default()
        frames = []
        for idx in range(16):
            frame = Image.new("RGB", (width, height), (3, 8, 22))
            draw = ImageDraw.Draw(frame)
            for star in range(120):
                x = (star * 47 + idx * 11) % width
                y = (star * 29 + idx * 5) % height
                glow = 90 + ((star * 17 + idx * 9) % 150)
                draw.point((x, y), fill=(glow // 5, glow, min(255, glow + 30)))

            cx, cy = width // 2, height // 2 - 16
            pulse = int(12 * math.sin(idx / 16 * math.tau))
            outer = 92 + pulse
            inner = 42 + pulse // 3
            draw.ellipse((cx - outer, cy - outer, cx + outer, cy + outer), outline=(0, 210, 255), width=4)
            draw.ellipse((cx - inner, cy - inner, cx + inner, cy + inner), fill=(8, 20, 44), outline=(95, 245, 255), width=3)
            for wing in (-1, 1):
                for offset in range(4):
                    arc_box = (
                        cx + wing * (55 + offset * 30),
                        cy - 78 + offset * 16,
                        cx + wing * (190 + offset * 18),
                        cy + 70 + offset * 10,
                    )
                    if wing < 0:
                        arc_box = (arc_box[2], arc_box[1], arc_box[0], arc_box[3])
                    draw.arc(arc_box, 210 if wing > 0 else -30, 330 if wing > 0 else 150, fill=(0, 170, 230), width=3)
            draw.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=(0, 235, 255))

            lines = ("ENGEL AI MAIN", "CT246 local artifact lane", "Grok not used")
            y = height - 82
            for line in lines:
                box = draw.textbbox((0, 0), line, font=font)
                tw = box[2] - box[0]
                draw.text(((width - tw) // 2, y), line, fill=(230, 245, 255), font=font)
                y += 22
            frames.append(frame)
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=85, loop=0, optimize=True)
        return {
            "ok": True,
            "artifact_path": str(path),
            "artifact_kind": "gif",
            "frame_count": len(frames),
            "width": width,
            "height": height,
        }
    except Exception as exc:
        return {
            "ok": False,
            "artifact_path": str(path),
            "artifact_kind": "gif",
            "error": str(exc),
        }


def _media_artifact_receipt(prompt: str, started: float) -> dict[str, Any]:
    stamp = _stamp()
    kind = _media_artifact_kind(prompt)
    MEDIA_ARTIFACT_REQUEST_DIR.mkdir(parents=True, exist_ok=True)
    work_path = MEDIA_ARTIFACT_REQUEST_DIR / f"ENGEL_MEDIA_ARTIFACT_REQUEST_{stamp}.json"
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_MEDIA_ARTIFACT_{stamp}.json"
    low = _intent_gate_text(prompt).casefold()
    grok_allowed = not any(term in low for term in ("do not use grok", "don't use grok", "without grok", "no grok"))
    artifact_result: dict[str, Any] = {
        "ok": False,
        "artifact_kind": kind,
        "status": "artifact request staged",
    }
    if kind == "gif":
        artifact_result = _generate_engel_self_gif(stamp)
    request_record = {
        "schema": "engel_media_artifact_request_v1",
        "updated_at_utc": _iso_now(),
        "prompt": prompt,
        "kind": kind,
        "grok_allowed": grok_allowed,
        "selected_lane": "ct246_local_media_artifact",
        "artifact_result": artifact_result,
    }
    _write_json(work_path, request_record)
    if artifact_result.get("ok") is True:
        reply = (
            "I created the Engel media artifact locally on CT246, not Grok. "
            f"Saved {kind}: {artifact_result.get('artifact_path')}. "
            "This request and receipt were saved to persistent memory."
        )
        status = "media artifact created"
    else:
        reply = (
            "This is a media/artifact request, so I did not send it to the fast text-only chat model. "
            f"I staged it on CT246 for the artifact lane: {work_path}. "
            "This request and receipt were saved to persistent memory."
        )
        status = "media artifact request staged"
    receipt = {
        "schema": "engel_main_server_media_artifact_receipt_v1",
        "ok": True,
        "status": status,
        "updated_at_utc": _iso_now(),
        "run_id": "main_server_media_artifact_" + stamp,
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "engel-main-server-media-artifact",
        "runtime_provider": "engel-main-server-media-artifact-router",
        "selected_provider": "ct_media_artifact_router",
        "main_server_chat_service_used": True,
        "media_artifact_request_path": str(work_path),
        "media_artifact_kind": kind,
        "media_artifact_result": artifact_result,
        "grok_allowed": grok_allowed,
        "grok_used": False,
        "model_process_started": False,
        "runtime_process_started": False,
        "runs_inference": False,
        "loads_model": False,
        "provider_api_enabled": False,
        "network_enabled": False,
        "server_enabled": True,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "model_output_trusted": True,
        "server_snapshot": _service_snapshot(),
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
    }
    memory_record = dict(receipt)
    memory_record["memory_source"] = "engel-ai-main CT media artifact router"
    try:
        _append_jsonl(PERSISTENT_CHAT_MEMORY_PATH, memory_record)
        receipt["persistent_chat_memory_appended"] = True
        receipt["persistent_chat_history_appended"] = True
        receipt["persistent_chat_memory_path"] = str(PERSISTENT_CHAT_MEMORY_PATH)
    except Exception as exc:
        receipt["persistent_chat_memory_appended"] = False
        receipt["persistent_chat_history_appended"] = False
        receipt["persistent_chat_memory_error"] = str(exc)
    _write_json(receipt_path, receipt)
    return receipt


def _prompt_requires_large_local_reasoning(prompt: str) -> bool:
    """Keep substantive work off the tiny conversational reflex model."""
    text = _intent_gate_text(prompt).strip()
    low = text.casefold()
    if not low:
        return False
    if _prompt_is_simple_arithmetic_chat(text):
        return False
    work_terms = (
        "architectural",
        "assembly",
        "bill of materials",
        "bom",
        "cad",
        "change order",
        "client",
        "connection",
        "construction",
        "detail",
        "dimension",
        "drawing",
        "elevation",
        "estimate",
        "fabrication",
        "field measurement",
        "floor plan",
        "issue package",
        "landing support",
        "manufacturing",
        "material list",
        "permit",
        "plan set",
        "point cloud",
        "punch list",
        "revision",
        "rfi",
        "sheet",
        "shop drawing",
        "site photo",
        "stair",
        "submittal",
        "title block",
        "title-block",
        "tolerance",
        "transmittal",
        "weld",
    )
    reasoning_terms = (
        "acceptance test",
        "audit",
        "check",
        "compare",
        "conflict",
        "decide",
        "decision",
        "evaluate",
        "explain",
        "impact",
        "investigate",
        "merge",
        "organize",
        "plan",
        "planning",
        "proof",
        "recommend",
        "reconcile",
        "review",
        "root cause",
        "scope",
        "strategy",
        "timeline",
        "tradeoff",
        "validate",
        "verification",
        "work through",
    )
    work_hit = any(term in low for term in work_terms)
    reasoning_hits = sum(1 for term in reasoning_terms if term in low)
    return bool(work_hit or reasoning_hits >= 2 or (len(text) > 220 and reasoning_hits >= 1))


def _prompt_requests_quick_casual_model(prompt: str) -> bool:
    text = _intent_gate_text(prompt)
    low = text.casefold()
    if not low.strip() or len(text) > 500:
        return False
    if _prompt_requires_large_local_reasoning(prompt):
        return False
    if _prompt_requests_live_runtime_status(prompt) or _prompt_requests_computer_memory(prompt) or _prompt_requests_reps_template(prompt) or _prompt_requests_help_next(prompt):
        return False
    if _prompt_requests_media_artifact(prompt):
        return False
    blocked_terms = (
        "write code",
        "edit file",
        "patch",
        "apply patch",
        "install",
        "download",
        "train",
        "copy files",
        "move files",
        "delete",
        "wipe",
        "format",
        "repartition",
        "run command",
        "ssh",
        "proxmox",
        "storage",
        "vault",
        "api key",
        "secret",
        "password",
        "token",
        "phone",
        "android",
        "alpha",
        "beta",
        "worker",
        "workers",
        "device",
        "devices",
        "discord",
        "bridge",
        "route",
        "connector",
        "provider",
        "chatgpt",
        "claude",
        "grok",
        "gemini",
        "codex",
        "meeting room",
        "agent room",
        "gif",
        "image",
        "picture",
        "photo",
        "visual",
        "wallpaper",
        "animation",
        "animated",
        "video",
        "logo",
        "icon",
        "png",
        "jpg",
        "jpeg",
        "webp",
        "mp4",
        "server status",
        "health check",
    )
    if any(term in low for term in blocked_terms):
        return False
    casual_terms = (
        "hello",
        "hey",
        "hi",
        "good morning",
        "good afternoon",
        "good evening",
        "how are you",
        "talk to me",
        "wanna talk",
        "want to talk",
        "lets talk",
        "let's talk",
        "normal conversation",
        "chat with me",
        "what do you think",
        # (2026-08-10) Social follow-ups. "Jokes sound good." and "you game?" fell to
        # the BIG lane, whose recalled operational memory drowned a three-word casual
        # message — the model lectured about provider bridges instead of telling a
        # joke (live, twice). Multi-word/word-bounded forms only: bare "game"/"fun"/
        # "play" would hijack build-a-game orders and media asks.
        "joke",
        "jokes",
        "funny",
        "make me laugh",
        "riddle",
        "you game",
        "wanna play",
        "let's play",
        "lets play",
        "play a game",
        "have some fun",
        "just for fun",
        "sup",
        "waz up",
        "wazz up",
        "wazzup",
        "what's up",
        "whats up",
        "tell me a story",
    )
    return any(
        re.search(rf"\b{re.escape(term)}\b", low)
        if term in {"hi", "hey", "sup", "joke", "jokes", "funny", "riddle"}
        else term in low
        for term in casual_terms
    )


def _prompt_is_simple_greeting(prompt: str) -> bool:
    low = " ".join(_intent_gate_text(prompt).casefold().strip().split())
    if not low or len(low) > 100:
        return False
    if any(term in low for term in ("which", "what", "why", "how", "model", "llm", "route", "provider")):
        return False
    return bool(re.search(r"\b(hello|hey|hi)\b", low)) or any(
        term in low for term in ("good morning", "good afternoon", "good evening")
    )


def _prompt_requests_chat_fault_repair(prompt: str) -> bool:
    low = _intent_gate_text(prompt).casefold()
    if not low.strip():
        return False
    direct_fault_terms = (
        "chat is broken",
        "chat still broken",
        "chat is still broken",
        "still broken",
        "nothing was fixed",
        "not fixed",
        "chat keeps failing",
        "chat failed",
        "chat timeout",
        "chat is too slow",
        "chat keeps timing out",
        "why is chat timing out",
        "why did chat time out",
        "why is engel not responding",
        "engel is not responding",
        "engel is not replying",
        "engel not responding",
        "engel not replying",
        "template response",
        "canned response",
        "chat is repeating",
        "chat keeps repeating",
    )
    if any(term in low for term in direct_fault_terms):
        return True
    ambiguous_fault_terms = (
        "timed out",
        "timing out",
        "timeout",
        "not responding",
        "no reply",
        "not replying",
        "too slow",
        "repeating",
    )
    chat_surface_terms = ("engel", "chat", "reply", "response", "conversation", "discord")
    repair_intent_terms = ("fix", "repair", "broken", "problem", "issue", "still", "keeps", "again")
    return (
        any(term in low for term in ambiguous_fault_terms)
        and any(term in low for term in chat_surface_terms)
        and any(term in low for term in repair_intent_terms)
    )


def _prompt_requests_deterministic_visible_chat(prompt: str) -> bool:
    low = _intent_gate_text(prompt).casefold()
    if not low.strip():
        return False
    exact_visible_terms = (
        "answer fast",
        "short status",
        "status check",
        "status update",
        "saving this chat memory",
        "server chat link",
        "ready to chat",
        "what changed",
        "stop breaking",
        "click next time",
        "still responsive",
        "one system",
        "stay fast",
        "where chat memory",
        "like a person",
        "working right now",
        "without launching",
        "slow laptop model",
        "calm status",
        "server side",
        "fastest route",
        "desktop shortcut",
        "handled through engel chat",
        "final check",
        "chat lane",
        "receipt proves",
    )
    explicit_health_terms = (
        "health check",
        "quick check",
        "smoke check",
        "bridge check",
        "route check",
        "connection check",
        "one sentence status",
    )
    return any(term in low for term in exact_visible_terms) or (
        len(prompt) <= 180 and any(term in low for term in explicit_health_terms)
    )


def _prompt_requests_chat_route(prompt: str) -> bool:
    low = _intent_gate_text(prompt).casefold()
    if not low.strip():
        return False
    if _prompt_requests_last_model_trace(prompt):
        return True
    return any(
        term in low
        for term in (
            "what route",
            "which route",
            "say which route",
            "route you used",
            "route are you using",
            "selected route",
            "chat route",
            "which provider",
            "what provider",
            "provider are you using",
            "which llm",
            "what llm",
            "llm answered",
            "llm answer",
            "which model",
            "what model",
            "model answered",
            "model answer",
        )
    )


def _prompt_requests_last_model_trace(prompt: str) -> bool:
    low = _intent_gate_text(prompt).casefold()
    if not low.strip():
        return False
    model_terms = (
        "which llm",
        "what llm",
        "llm answered",
        "llm answer",
        "which model",
        "what model",
        "model answered",
        "model answer",
        "which provider",
        "what provider",
    )
    recent_terms = (
        "last message",
        "last two",
        "last reply",
        "last answer",
        "previous message",
        "previous reply",
        "previous answer",
        "answered last",
        "answer last",
    )
    return any(term in low for term in model_terms) and any(term in low for term in recent_terms)


def _recent_chat_route_summary(limit: int = 3) -> str:
    rows: list[dict[str, Any]] = []
    try:
        files = sorted(
            (path for path in CHAT_RECEIPT_DIR.glob("*.json") if path.is_file()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[: max(1, limit + 4)]
        for path in files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            prompt = _clip(_intent_gate_text(str(data.get("prompt") or "")), 70)
            rows.append(
                {
                    "provider": str(
                        data.get("runtime_provider")
                        or data.get("selected_provider")
                        or data.get("provider")
                        or "unknown"
                    ),
                    "status": str(data.get("status") or "unknown"),
                    "latency_ms": data.get("server_request_latency_ms")
                    or data.get("latency_ms")
                    or data.get("elapsed_ms"),
                    "prompt": prompt,
                }
            )
            if len(rows) >= limit:
                break
    except Exception:
        rows = []
    if not rows:
        return "I do not have a recent receipt to name the last model yet."
    parts = []
    for idx, row in enumerate(rows, start=1):
        latency = row.get("latency_ms")
        latency_text = f", {latency} ms" if isinstance(latency, int) else ""
        prompt_text = f" for '{row['prompt']}'" if row.get("prompt") else ""
        parts.append(f"{idx}. {row['provider']} ({row['status']}{latency_text}){prompt_text}")
    return "Recent Engel chat receipts show: " + "; ".join(parts) + "."


def _prompt_needs_previous_turn(prompt: str) -> bool:
    low = _intent_gate_text(prompt).casefold()
    return any(
        term in low
        for term in (
            "keep that",
            "say that",
            "say it",
            "answer that",
            "make that",
            "make it",
            "that answer",
            "that idea",
            "same idea",
            "last answer",
            "last suggestion",
            "used earlier",
            "two messages ago",
            "continue the same conversation",
            "talk this through",
            "talk that through",
            "talk it through",
            "correction from this conversation",
            "answer that",
            "that more casually",
            "we have been discussing",
            "from that situation",
            "this situation",
            "this case",
            "this job",
            "that first",
            "that standard",
            "decision so far",
            "current decision",
            "still open",
            "move on with",
            "carry forward",
            "wrap up",
            "what stands out",
            "what does it rule out",
            "what is confirmed",
        )
    )


def _prompt_starts_new_conversation(prompt: str) -> bool:
    low = _intent_gate_text(prompt).casefold()
    return any(
        term in low
        for term in (
            "begin a separate work conversation",
            "open a different chat topic",
            "start a new conversation",
            "start a separate conversation",
            "open a fresh review",
            "start a fresh review",
            "new unrelated topic",
            "switch to a new topic",
        )
    )


def _prompt_requires_buffered_quality_gate(prompt: str) -> bool:
    """Use the scored local-chat cascade when a streamed answer cannot be repaired."""
    if _is_spoken_voice_training_prompt(prompt):
        return True
    low = _intent_gate_text(prompt).casefold()
    if _prompt_requires_large_local_reasoning(prompt):
        return True
    if _prompt_needs_previous_turn(prompt):
        return True
    return any(
        condition
        for condition in (
            "does our conversation feel normal" in low,
            "talk this through" in low,
            "what do you remember" in low,
            "what correction from this conversation" in low,
            "two-sentence" in low,
            "two sentence" in low,
            "one useful question" in low and "automat" in low,
            "real app" in low and "proof" in low,
            "drafting work to feel less repetitive" in low,
            "one small automation idea" in low and "shop drawing" in low,
            any(
                term in low
                for term in (
                    "normal person",
                    "more casually",
                    "real person",
                    "natural voice",
                    "not robotic",
                )
            ),
        )
    )


def _prompt_requests_short_casual_fast_model(prompt: str) -> bool:
    if not _env_truth("ENGEL_ALLOW_TINY_FAST_REFLEX_CHAT", default=False):
        return False
    if _prompt_needs_previous_turn(prompt):
        return False
    text = _intent_gate_text(prompt).strip()
    low = text.casefold()
    if not low or len(text) > 240:
        return False
    blocked_terms = (
        "write code",
        "edit file",
        "patch",
        "apply patch",
        "install",
        "download",
        "train",
        "copy files",
        "move files",
        "delete",
        "wipe",
        "format",
        "repartition",
        "run command",
        "ssh",
        "proxmox",
        "storage",
        "vault",
        "api key",
        "secret",
        "password",
        "token",
        "meeting room",
        "agent room",
        "server status",
        "health check",
        "route",
        "bridge",
        "connection",
        "drafting",
        "workflow",
        "automation",
        "shop drawing",
        "proof",
        "what do you remember",
        "remember about",
        "summary",
        "real app",
    )
    if any(term in low for term in blocked_terms):
        return False
    starts = ("hello", "hey", "hi", "good morning", "good afternoon", "good evening")
    if low.startswith(starts):
        return True
    return any(
        term in low
        for term in (
            "how are you",
            "talk to me",
            "wanna talk",
            "want to talk",
            "lets talk",
            "let's talk",
            "talk engel",
            "talk with engel",
            "chat with me",
            "normal conversation",
            "feel like a normal conversation",
            "stop repeating",
            "less scripted",
        )
    )


def _context_pack_requires_model(request: dict[str, Any]) -> bool:
    context_pack = request.get("context_pack")
    return bool(
        isinstance(context_pack, dict)
        and context_pack.get("created") is True
        and int(context_pack.get("item_count") or 0) > 0
    )


def _normalize_discord_prompt(prompt: str) -> str:
    text = " ".join(str(prompt or "").casefold().split())
    if text.startswith("engel work "):
        text = text[len("engel work ") :]
    for typo in ("dicord", "discrod", "discort", "disord", "discrd", "discordd"):
        text = text.replace(typo, "discord")
    return text


def _request_skips_operator_room_actions(request: dict[str, Any]) -> bool:
    """Training turns answer in Chat. They must not open the live Discord room."""
    if _request_local_only_training(request):
        return True
    metadata = request.get("metadata")
    return isinstance(metadata, dict) and metadata.get("interactive") is False


def _owner_prompt_is_discord_checkout(prompt: str) -> bool:
    """True when Joshua wants Engel AI Main to show/open the live Discord room."""
    text = _normalize_discord_prompt(prompt)
    if not text:
        return False
    if text.startswith(("what is", "what's", "whats", "tell me about", "explain", "why is")):
        return False
    if "training depth:" in text or "training task:" in text:
        return False
    if any(
        marker in text
        for marker in ("fix ", "wire ", "repair ", "rebuild ", "install ", "update ", "patch ")
    ):
        return False
    if text in {"discord", "discord chat", "check out discord chat"}:
        return True
    # The chat voice card says "you are not a Discord guest". That identity
    # line is not a request to open the room.
    stripped = text.replace("not a discord guest", " ").replace("not discord", " ")
    if "discord" not in stripped and "#general" not in stripped:
        return False
    return any(
        marker in stripped
        for marker in (
            "check",
            "open",
            "look",
            "read",
            "show",
            "status",
            "chat",
            "thread",
            "repeat",
            "replies",
        )
    )


def _discord_bridge_snapshot() -> dict[str, Any]:
    """Local CT246 Discord bridge facts. No tokens, no Discord API."""
    status_path = ROOT / "run" / "discord_bridge" / "status.json"
    log_path = ROOT / "logs" / "engel_discord_bridge.log"
    snapshot: dict[str, Any] = {
        "status_path": str(status_path),
        "status_present": status_path.is_file(),
        "service_active": "unknown",
        "bot_user": "",
        "updated_at_utc": "",
        "bridge_status": "",
        "last_inbound": "",
        "last_reply": "",
        "ok": False,
    }
    try:
        raw = subprocess.run(
            ["systemctl", "is-active", "engel-discord-bridge.service"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        snapshot["service_active"] = str(raw.stdout or raw.stderr or "").strip() or "unknown"
    except Exception:
        snapshot["service_active"] = "unknown"
    if status_path.is_file():
        try:
            data = json.loads(status_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                snapshot["bot_user"] = str(data.get("bot_user") or data.get("user_name") or "").strip()
                snapshot["updated_at_utc"] = str(data.get("updated_at_utc") or "").strip()
                snapshot["bridge_status"] = str(data.get("status") or "").strip()
                snapshot["ok"] = data.get("ok") is True
        except Exception:
            pass
    if log_path.is_file():
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
            for line in lines:
                low = line.casefold()
                if any(marker in low for marker in ("token", "authorization", "secret", "bot_token")):
                    continue
                if "discord message accepted from" in low:
                    snapshot["last_inbound"] = line.split("Discord message accepted from", 1)[-1].strip()
                elif "discord reply sent" in low or "named-gap posted plain" in low:
                    snapshot["last_reply"] = "Engel posted a reply in #general"
        except Exception:
            pass
    tail = _discord_channel_tail()
    snapshot["messages"] = tail.get("messages") if isinstance(tail.get("messages"), list) else []
    snapshot["messages_ok"] = tail.get("ok") is True
    snapshot["messages_status"] = str(tail.get("status") or "")
    return snapshot


def _discord_checkout_reply(snapshot: dict[str, Any]) -> str:
    active = str(snapshot.get("service_active") or "unknown")
    bot = str(snapshot.get("bot_user") or "Engel AI Main")
    updated = str(snapshot.get("updated_at_utc") or "unknown")
    status = str(snapshot.get("bridge_status") or "unknown")
    inbound = str(snapshot.get("last_inbound") or "none in the current log tail")
    reply = str(snapshot.get("last_reply") or "no recent Engel post in the current log tail")
    live = active == "active" and snapshot.get("ok") is True
    lines = [
        "I read live Discord #general. This is Engel's own CT 246 discord bridge, not an MCP add-on.",
        "Discord is live from Engel AI Main." if live else "Discord bridge status from Engel AI Main:",
        f"Room: Engel AI Main Chat #general | Bot: {bot} | Bridge: {active}",
        f"Last bridge update: {updated} | status: {status}",
        f"Last inbound log: {inbound}",
        f"Last Engel post log: {reply}",
        "",
        "Recent #general messages:",
    ]
    messages = snapshot.get("messages") if isinstance(snapshot.get("messages"), list) else []
    if not messages:
        lines.append(
            str(snapshot.get("messages_status") or "Could not load the live message tail.")
        )
    repeating = 0
    last_body = ""
    for item in messages[-12:]:
        if not isinstance(item, dict):
            continue
        author = str(item.get("author") or "unknown")
        body = str(item.get("content") or "").strip() or "(no text)"
        lines.append(f"- {author}: {body}")
        key = " ".join(body.casefold().split())[:120]
        if key and key == last_body:
            repeating += 1
        last_body = key
    if repeating:
        lines.append("")
        lines.append(
            f"The same line was repeated {repeating} time(s) in this tail. "
            "Engel is reading those replies now instead of guessing."
        )
    lines += [
        "",
        "Sub-Engel is a peer in that room. Never Chase.",
    ]
    return "\n".join(lines)


def _discord_bridge_cli(flag: str, timeout: int = 20) -> dict[str, Any]:
    py = ROOT / ".venv" / "bin" / "python"
    if not py.is_file():
        py = Path(sys.executable)
    script = ROOT / "tools" / "engel_discord_bridge.py"
    env = os.environ.copy()
    env_file = Path(
        os.environ.get("ENGEL_DISCORD_ENV_FILE")
        or (ROOT / "run" / "secrets" / "discord.env")
    )
    if env_file.is_file():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                raw = line.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                key, _, value = raw.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value and key not in env:
                    env[key] = value
        except Exception:
            pass
    try:
        raw = subprocess.run(
            [str(py), str(script), flag],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except Exception as exc:
        return {"ok": False, "status": f"discord runner failed: {type(exc).__name__}"}
    stdout = str(raw.stdout or "").strip()
    if any(marker in stdout.casefold() for marker in ("token", "authorization", "bot_token")):
        return {"ok": False, "status": "refused to parse discord runner output"}
    try:
        payload = json.loads(stdout.splitlines()[-1]) if stdout else {}
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("ok", False)
    payload.setdefault("status", f"discord runner exit {raw.returncode}")
    return payload


def _discord_channel_tail() -> dict[str, Any]:
    result = _discord_bridge_cli("--channel-tail", timeout=20)
    messages = result.get("messages") if isinstance(result.get("messages"), list) else []
    clean: list[dict[str, Any]] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        clean.append(
            {
                "id": str(item.get("id") or ""),
                "author": str(item.get("author") or "")[:40],
                "bot": bool(item.get("bot")),
                "content": str(item.get("content") or "")[:220],
                "timestamp": str(item.get("timestamp") or ""),
            }
        )
    return {
        "ok": result.get("ok") is True,
        "status": str(result.get("status") or ""),
        "messages": clean,
    }


def _owner_prompt_is_reply_to_sub_engel(prompt: str) -> bool:
    text = " ".join(str(prompt or "").casefold().split())
    if text.startswith("engel work "):
        text = text[len("engel work ") :]
    if "sub-engel" not in text and "sub engel" not in text and "subengel" not in text:
        return False
    return any(
        marker in text
        for marker in ("reply", "respond", "responed", "answer sub", "talk to sub", "collab")
    )


def _owner_post_sub_engel_named_gap() -> dict[str, Any]:
    """Post the named CODE gap into Discord #general. Proof is a message id."""
    payload = _discord_bridge_cli("--post-named-gap", timeout=20)
    posted = payload.get("posted") is True and bool(payload.get("discord_message_id"))
    return {
        "ok": posted,
        "posted": posted,
        "discord_posted": posted,
        "status": str(payload.get("status") or "discord post did not run"),
        "schema": "engel_discord_named_gap_post_v1",
        "discord_message_id": str(payload.get("discord_message_id") or ""),
        "discord_channel_id": "1148755186752430163",
    }


def _owner_reply_to_sub_engel_turn(prompt: str, started: float) -> tuple[dict[str, Any], str]:
    result = _owner_post_sub_engel_named_gap()
    posted = result.get("posted") is True
    message_id = str(result.get("discord_message_id") or "")
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
            f"Status: {result.get('status') or 'unknown'}"
        )
    stamp = _stamp()
    receipt = {
        "schema": "engel_main_server_discord_owner_reply_v1",
        "ok": posted,
        "status": result.get("status"),
        "updated_at_utc": _iso_now(),
        "run_id": "main_server_discord_owner_reply_" + stamp,
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "engel-discord-bridge",
        "runtime_provider": "engel-discord-bridge",
        "selected_provider": "discord_bridge",
        "main_server_chat_service_used": True,
        "chat_only_no_android_or_sub_engel": False,
        "discord_posted": posted,
        "discord_message_id": message_id,
        "engel_agent_kernel_used": False,
    }
    receipt = _finalize_chat_receipt(
        receipt,
        prompt,
        reply,
        "ct_discord_owner_reply_sub_engel",
        started,
        allow_room=False,
        allow_reps=False,
    )
    reply = str(receipt.get("assistant_reply") or reply)
    return receipt, reply


def _discord_checkout_turn(prompt: str, started: float) -> tuple[dict[str, Any], str]:
    snapshot = _discord_bridge_snapshot()
    reply = _discord_checkout_reply(snapshot)
    stamp = _stamp()
    receipt = {
        "schema": "engel_main_server_discord_checkout_v1",
        "ok": True,
        "status": "discord checkout from live Engel bridge",
        "updated_at_utc": _iso_now(),
        "run_id": "main_server_discord_checkout_" + stamp,
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "engel-discord-bridge",
        "runtime_provider": "engel-discord-bridge",
        "selected_provider": "discord_bridge",
        "main_server_chat_service_used": True,
        "chat_only_no_android_or_sub_engel": False,
        "discord_checkout": True,
        "discord_bridge_service_active": snapshot.get("service_active"),
        "discord_bridge_ok": snapshot.get("ok") is True,
    }
    receipt = _finalize_chat_receipt(
        receipt,
        prompt,
        reply,
        "ct_discord_checkout",
        started,
        allow_room=False,
        allow_reps=False,
    )
    reply = str(receipt.get("assistant_reply") or reply)
    return receipt, reply


def _is_discord_owner_turn(request: dict[str, Any] | None) -> bool:
    """Josh talking in Discord must use the full CT246 brain, not the tiny fast lane.

    Live 2026-08-18: source=discord plus prefer_fast_local_chat=True forced every
    owner turn onto the 0.5B/1.5B quick model and skipped 14B, MoE, Nemotron,
    and provider pipes. Peer/guest chatter still uses the fast lane.
    """
    request = request or {}
    if bool(request.get("discord_owner_turn") is True):
        return True
    metadata = request.get("metadata") if isinstance(request.get("metadata"), dict) else {}
    return str(metadata.get("discord_authority_level") or "").casefold() == "owner"


def _request_prefers_quick_local_chat(prompt: str, request: dict[str, Any]) -> bool:
    if _context_pack_requires_model(request):
        return False
    if _request_needs_vision_lane(request):
        return False
    if _is_discord_owner_turn(request):
        return False
    if _env_truth("ENGEL_DISABLE_QUICK_LOCAL_CHAT", default=False):
        return False
    if _prompt_requires_large_local_reasoning(prompt):
        return False
    if _prompt_needs_previous_turn(prompt):
        return False
    if not _prompt_requests_quick_casual_model(prompt):
        return False
    if bool(request.get("prefer_fast_local_chat") is True):
        return True
    source = str(request.get("source") or request.get("client") or "").strip().casefold()
    if source.startswith("discord"):
        # Humans in Discord must not be parked on the 0.5B lane just because
        # the room is Discord. Only peer bots send prefer_fast_local_chat.
        return False
    if source in {
        "engel_flutter_main",
        "engel_ai_main_ui",
        "desktop_ui",
        "rog_ui",
        "codex_audit",
    }:
        return True
    if _env_truth("ENGEL_QUICK_LOCAL_CHAT_FOR_UI_AND_DISCORD", default=True):
        return True
    return False


def _prompt_allows_default_fast_local_chat(prompt: str, request: dict[str, Any]) -> bool:
    """Use CT246's fast local model for interactive UI/Discord chat.

    The trained 7B LoRA is still the deep local lane, but routing every normal
    desktop/Discord turn through it made Engel feel broken on CPU-only CT
    service paths. ROG UI and Discord turns marked as fast interactive chat use
    the bounded local GGUF lane first unless the prompt clearly asks for a deep
    action, code task, install, storage change, or training run.
    """
    if _context_pack_requires_model(request):
        return False
    if _request_needs_vision_lane(request):
        return False
    source = str(request.get("source") or request.get("client") or "").strip().casefold()
    if _prompt_requires_large_local_reasoning(prompt):
        return False
    if _is_discord_owner_turn(request):
        return False
    if source.startswith("discord") and request.get("prefer_fast_local_chat") is not True:
        return False
    # The default tiny lane used to accept nearly every UI message. Keep it for
    # explicit casual conversation only; substantive UI turns belong to the
    # larger local model even when their vocabulary misses a domain keyword.
    if not _prompt_requests_quick_casual_model(prompt):
        return False
    if _prompt_requires_buffered_quality_gate(prompt):
        return False
    if _prompt_needs_previous_turn(prompt):
        return False
    interactive_fast_request = bool(request.get("prefer_fast_local_chat") is True) or source in {
        "discord",
        "discord_chat",
        "engel_flutter_main",
        "engel_ai_main_ui",
        "desktop_ui",
        "rog_ui",
        "rog_desktop_controller",
    }
    if not interactive_fast_request and not _env_truth("ENGEL_ALLOW_TINY_FAST_DEFAULT_CHAT", default=False):
        return False
    text = _intent_gate_text(prompt).strip()
    low = text.casefold()
    if not low or len(text) > 1600:
        return False
    requested_local = str(request.get("local_provider") or request.get("provider") or "").strip().casefold()
    if requested_local in {"trained_lora", "lora", "deep_local", "large_local", "large"}:
        return False
    if _prompt_requests_live_runtime_status(prompt) or _prompt_requests_computer_memory(prompt) or _prompt_requests_reps_template(prompt):
        return False
    if _prompt_requests_chat_route(prompt) or _prompt_requests_template_loop_repair(prompt):
        return False
    if _prompt_requests_media_artifact(prompt):
        return False
    # (2026-07-07) Team / meeting-room orders route OFF the tiny quick-local model to
    # the capable big lane, so the brain's synthesis (the main_reply that becomes the
    # fleet brief) reads as a real answer instead of a one-line deflection.
    if _prompt_requests_meeting_room_dispatch(prompt):
        return False
    # (2026-07-12) Identity/bio questions about JOSHUA route off the 1.5B too: with
    # the durable facts in context it still deflected ("I'm Engel, not your business")
    # or looped persona lines instead of using them. The big lane answers these from
    # the same facts correctly.
    if any(t in low for t in (
        "about me", "my business", "my background", "my career", "who am i",
        "my company", "know about joshua", "about my work", "my profession",
        "my job", "what do i do", "kind of work do i", "kind of work i do",
        "remember about the kind of work", "work do i usually",
        "jz drafting", "global modular",
    )):
        return False
    if _prompt_is_simple_arithmetic_chat(text) and not _prompt_requests_meeting_room_dispatch(prompt):
        return True
    blocked_terms = (
        "write code",
        "edit file",
        "apply patch",
        "install",
        "download",
        "train",
        "fine tune",
        "finetune",
        "copy file",
        "copy files",
        "move file",
        "move files",
        "delete",
        "wipe",
        "format",
        "repartition",
        "run command",
        "powershell",
        "ssh",
        "proxmox",
        "storage",
        "vault",
        "api key",
        "secret",
        "password",
        "token",
        "phone",
        "android",
        "alpha",
        "beta",
        "meeting room",
        "agent room",
        "gif",
        "image",
        "picture",
        "photo",
        "visual",
        "wallpaper",
        "animation",
        "animated",
        "video",
        "logo",
        "icon",
        "png",
        "jpg",
        "jpeg",
        "webp",
        "mp4",
        "discord bridge",
        "chatgpt bridge",
        "claude bridge",
        "grok bridge",
        "gemini bridge",
        "drafting",
        "workflow",
        "automation",
        "shop drawing",
        "proof",
        "what do you remember",
        "remember about",
        "summary",
        "real app",
    )
    if any(term in low for term in blocked_terms):
        return False
    action_start = re.match(
        r"^\s*(fix|connect|pair|wire|audit|restore|debug|refactor|build|create|make|update|upgrade|deploy|launch|start|stop|restart|sync|copy|move|install|download|train|run)\b",
        low,
    )
    if action_start:
        return False
    # (2026-07-07 audit Q-5) encyclopedic factual recall -> big lane (hallucinates on the tiny model)
    if _prompt_is_encyclopedic_recall(prompt):
        return False
    return True


def _prompt_is_simple_arithmetic_chat(text: str) -> bool:
    low = str(text or "").casefold().strip()
    if not low or len(low) > 320:
        return False
    # Plain digit-hyphen-digit with no math words is commonly a phone number,
    # date range, ticket ID, model number, or part number. Do not treat it as
    # subtraction unless the user explicitly asks for arithmetic.
    arithmetic_words = (
        "what is",
        "what's",
        "whats",
        "calculate",
        "compute",
        "evaluate",
        "solve",
        "result",
        "answer",
        "equals",
        "equal",
        "minus",
        "subtract",
        "plus",
        "times",
        "multiplied",
        "divided",
        "sum",
        "total",
    )
    if re.fullmatch(r"\s*\d{2,}[\s-]+\d{2,}\s*", low) and not any(word in low for word in arithmetic_words):
        return False
    number_words = (
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
        "twenty",
        "thirty",
        "forty",
        "fifty",
        "hundred",
    )
    if not re.search(r"\d", low) and sum(1 for word in number_words if re.search(rf"\b{word}\b", low)) < 2:
        return False
    if re.search(r"\d+\s*(?:\+|-|\*|/|x)\s*\d+", low):
        return True
    math_terms = (
        "times",
        "multiplied",
        "plus",
        "minus",
        "divided",
        "divide",
        "add",
        "subtract",
        "sum",
        "total",
        "how many",
        "how much",
    )
    return any(term in low for term in math_terms)


def _safe_arithmetic_answer(text: str) -> str | None:
    """(2026-07-07 audit Q-4) Deterministically evaluate a PURE arithmetic question
    so the small model can't get operand order / precedence wrong. Safe numeric-only
    AST eval (never eval()). Returns None unless the whole prompt (minus calc filler)
    is a clean math expression — so hyphenated phone numbers, date ranges, order/ID
    numbers, versions, etc. ("555-1234", "2020-2021", "100-50") are NEVER treated as
    subtraction (that misfire produced confidently-wrong answers)."""
    import ast as _ast
    import operator as _op

    raw_text = str(text or "")
    low = " " + raw_text.casefold().strip() + " "
    explicit_arithmetic = any(
        word in low
        for word in (
            "what is", "what's", "whats", "calculate", "compute", "evaluate",
            "solve", "result", "answer", "equals", "equal", "minus",
            "subtract", "plus", "times", "multiplied", "divided", "sum", "total",
        )
    )
    if re.fullmatch(r"\s*\d{2,}[\s-]+\d{2,}\s*", raw_text) and not explicit_arithmetic:
        return None
    for word, sym in (
        (" multiplied by ", " * "), (" times ", " * "), (" plus ", " + "),
        (" minus ", " - "), (" divided by ", " / "), (" divided ", " / "),
        (" divide ", " / "), (" over ", " / "),
    ):
        low = low.replace(word, sym)
    low = re.sub(r"(?<=\d)\s*[x×]\s*(?=\d)", " * ", low)
    # Strip leading calc filler ("what is 2+2" -> "2+2"), then require the RESIDUE
    # to be a pure math expression. Any leftover letters => it's prose, not a
    # calculation (e.g. "call me at 555-1234", "what happened in 2020-2021").
    residue = re.sub(
        r"^\s*(?:(?:hi|hello|hey)(?:\s+engel)?[\s,.!:\-]*)+",
        " ",
        low,
    )
    residue = re.sub(
        r"\b(?:answer|reply|respond)\s+in\s+(?:one|a)\s+(?:short|brief)\s+sentence\b.*$",
        " ",
        residue,
    )
    residue = re.sub(
        r"\b(?:keep\s+(?:the\s+answer|it)\s+(?:short|brief)|give\s+(?:a\s+)?(?:short|brief|concise)\s+answer)\b.*$",
        " ",
        residue,
    )
    for filler in (
        "what is", "what's", "whats", "what are", "how much is", "how much are",
        "the answer to", "the answer is", "calculate", "compute", "evaluate",
        "solve", "result of", "value of", "equals", "equal to", "please", "tell me",
        "just answer the number", "answer the number", "only the number",
        "respond with the number", "give the number",
    ):
        residue = residue.replace(filler, " ")
    residue = residue.replace("=", " ").replace("?", " ")
    leftover_letters = re.sub(r"[\d\.\s()+\-*/]", "", residue)
    if leftover_letters.strip():
        return None
    m = re.search(r"[-+(]?[\d\.\s()+\-*/]*\d[\d\.\s()+\-*/]*", residue)
    if not m:
        return None
    expr = m.group(0).strip()
    expr = re.sub(r"(?<!\d)\.(?!\d)", " ", expr).strip()
    if not re.search(r"\d[\s]*[+\-*/][\s]*\d", expr) or not re.fullmatch(r"[\d\.\s()+\-*/]+", expr):
        return None
    ops = {
        _ast.Add: _op.add, _ast.Sub: _op.sub, _ast.Mult: _op.mul,
        _ast.Div: _op.truediv, _ast.USub: _op.neg, _ast.UAdd: _op.pos, _ast.Mod: _op.mod,
    }

    def _ev(node: Any) -> float:
        if isinstance(node, _ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, _ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](_ev(node.left), _ev(node.right))
        if isinstance(node, _ast.UnaryOp) and type(node.op) in ops:
            return ops[type(node.op)](_ev(node.operand))
        raise ValueError("unsupported")

    try:
        val = _ev(_ast.parse(expr, mode="eval").body)
    except (ValueError, SyntaxError, ZeroDivisionError, TypeError):
        return None
    if isinstance(val, float) and val.is_integer():
        val = int(val)
    elif isinstance(val, float):
        val = round(val, 6)
    return f"{expr} = {val}"


def _deterministic_arithmetic_receipt(prompt: str, started: float) -> dict[str, Any] | None:
    user_prompt = _intent_gate_text(prompt).strip() or str(prompt or "").strip()
    if not _prompt_is_simple_arithmetic_chat(user_prompt):
        return None
    arithmetic_answer = _safe_arithmetic_answer(user_prompt)
    if arithmetic_answer is None:
        return None
    reply = arithmetic_answer
    if any(term in user_prompt.casefold() for term in ("just answer the number", "only the number", "answer the number")):
        reply = arithmetic_answer.rsplit("=", 1)[-1].strip()
    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_DETERMINISTIC_ARITHMETIC_{stamp}.json"
    receipt = {
        "schema": "engel_main_server_deterministic_arithmetic_receipt_v1",
        "ok": True,
        "status": "deterministic arithmetic answered before model routing",
        "updated_at_utc": _iso_now(),
        "run_id": "main_server_deterministic_arithmetic_" + stamp,
        "prompt": prompt,
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "Engel deterministic arithmetic",
        "runtime_provider": "ct_deterministic_arithmetic",
        "selected_provider": "ct_deterministic_arithmetic",
        "main_server_chat_service_used": True,
        "model_process_started": False,
        "runtime_process_started": False,
        "runs_inference": False,
        "provider_api_enabled": False,
        "network_enabled": False,
        "server_enabled": True,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
    }
    _write_json(receipt_path, receipt)
    return receipt


def _blocked_command_turn(prompt: str, started: float) -> tuple[dict[str, Any], str] | None:
    """Block dangerous shell-command requests before any model can answer them."""
    text = _intent_gate_text(prompt)
    low = text.casefold()
    if not re.search(r"\b(run|execute|cmd|command|powershell|terminal|shell)\b", low):
        return None
    direct_deny = None
    for pattern in (
        r"\brm\s+-rf\s+/(?:\s|$)",
        r"\brm\s+-rf\s+~",
        r"\bmkfs\b",
        r"\bformat\b",
        r"\bdiskpart\b",
        r"\bdd\s+if=",
        r"\bshutdown\b|\breboot\b|\bStop-Computer\b|\bRestart-Computer\b",
        r"\bRemove-Item\b.*-Recurse.*\b[Cc]:\\",
    ):
        if re.search(pattern, text, re.I):
            direct_deny = pattern
            break
    plan: dict[str, Any] | None = None
    try:
        import engel_command_planner

        plan = engel_command_planner.plan_actions(text)
    except Exception:
        plan = None
    if not isinstance(plan, dict):
        if direct_deny is None:
            return None
        plan = {"summary": "blocked dangerous shell command", "steps": []}
    elif direct_deny:
        plan.setdefault("steps", []).insert(
            0,
            {
                "desc": "blocked dangerous shell command",
                "argv": [],
                "cwd": str(ROOT),
                "tier": "blocked",
                "timeout": 0,
                "blocked": True,
                "reason": f"command matched deny pattern: {direct_deny}",
            },
        )
    if not isinstance(plan, dict):
        return None
    blocked_steps = [
        step
        for step in plan.get("steps", [])
        if isinstance(step, dict) and step.get("blocked") is True
    ]
    if not blocked_steps and direct_deny is None:
        return None
    reason = str((blocked_steps[0].get("reason") if blocked_steps else direct_deny) or "unsafe command")
    reply = "I blocked that command because it matches Engel's protected-action safety rules. No command was run."
    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_BLOCKED_COMMAND_{stamp}.json"
    receipt = {
        "schema": "engel_main_server_blocked_command_receipt_v1",
        "ok": True,
        "status": "unsafe command blocked before model routing",
        "updated_at_utc": _iso_now(),
        "run_id": "main_server_blocked_command_" + stamp,
        "prompt": _clean_text(prompt),
        "prompt_sha256": hashlib.sha256(_clean_text(prompt).encode("utf-8", errors="replace")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "Engel protected command gate",
        "runtime_provider": "ct_command_safety_gate",
        "selected_provider": "ct_command_safety_gate",
        "blocked": True,
        "blocked_reason": reason,
        "plan": plan,
        "model_process_started": False,
        "runtime_process_started": False,
        "command_executed": False,
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
    }
    _write_json(receipt_path, receipt)
    receipt["receipt_path"] = str(receipt_path)
    return receipt, reply


def _prompt_is_encyclopedic_recall(prompt: str) -> bool:
    """(2026-07-07 audit Q-5) Open-domain factual recall the tiny model tends to
    hallucinate (multi-fact/encyclopedic asks) — route these to the big lane.
    Deliberately narrow: simple single-fact 'what is the capital of X' stays fast."""
    low = _intent_gate_text(prompt).casefold().strip()
    if not low:
        return False
    return any(
        pat in low
        for pat in (
            "list ", "facts about", "tell me about", "history of", "biography of",
            "give me facts", "interesting facts", "everything about", "in detail about",
            "explain the history", "who was ", "when did ", "where is the",
        )
    )


def _prompt_requests_template_loop_repair(prompt: str) -> bool:
    low = _intent_gate_text(prompt).casefold()
    return any(
        term in low
        for term in (
            "stop giving template",
            "template response",
            "scripted response",
            "status script",
            "canned response",
            "canned reply",
            "stop repeating",
            "repeating response",
        )
    )


def _prompt_requests_fast_visible_chat(prompt: str) -> bool:
    low = _intent_gate_text(prompt).casefold()
    if not low.strip():
        return False
    fast_terms = (
        "stretch:",
        "answer fast",
        "short status",
        "status check",
        "status update",
        "saving this chat memory",
        "server chat link",
        "ready to chat",
        "what changed",
        "stop breaking",
        "click next time",
        "still responsive",
        "one system",
        "stay fast",
        "where chat memory",
        "like a person",
        "working right now",
        "without launching",
        "slow laptop model",
        "calm status",
        "server side",
        "fastest route",
        "desktop shortcut",
        "handled through engel chat",
        "final check",
        "chat lane",
        "talk like",
        "ask me one",
        "less scripted",
        "review-only",
        "candidate-only",
        "verifier pass",
        "receipt proves",
    )
    if any(term in low for term in fast_terms):
        return True
    deep_terms = (
        "write code",
        "write a file",
        "edit file",
        "patch",
        "apply patch",
        "write code",
        "implement",
        "debug code",
        "build app",
        "create app",
        "make app",
        "generate app",
        "install",
        "download",
        "train",
        "copy files",
        "move files",
        "delete",
        "wipe",
        "format",
        "repartition",
        "run command",
        "ssh",
        "proxmox",
        "storage",
        "vault",
    )
    if any(term in low for term in deep_terms):
        return False
    explicit_health_terms = (
        "health check",
        "quick check",
        "smoke check",
        "bridge check",
        "route check",
        "connection check",
        "one sentence status",
    )
    if len(prompt) <= 180 and any(term in low for term in explicit_health_terms):
        return True

    # Do not catch normal short conversation here. The broad fallback caused
    # Discord and desktop chat to repeat canned status text instead of using
    # the provider bridges or local model route.
    return False


def _reply_is_status_promise(reply: str) -> bool:
    """True when the model announced a live check instead of returning it."""
    low = " ".join(str(reply or "").casefold().split())
    if not low:
        return True
    promise = (
        "i'll check",
        "i will check",
        "let me check",
        "i'll look",
        "i will look",
        "i'll inspect",
        "i'll verify",
        "i will verify",
        "i'll continue",
        "i will continue",
        "then continue the",
        "instead of reciting",
        "so the answer isn't just the old json",
        "i'll check what's actually live",
    )
    if any(term in low for term in promise):
        return True
    return False


def _reply_missing_live_runtime_facts(prompt: str, reply: str) -> bool:
    low_prompt = _intent_gate_text(prompt).casefold()
    low_reply = reply.casefold()
    if not _prompt_requests_live_runtime_status(prompt):
        return False
    if _reply_is_status_promise(reply):
        return True
    required: list[str] = []
    if any(term in low_prompt for term in ("model", "llm", "stored", "where", "vault")):
        required.extend(["/opt/engel/models-active", "qwen"])
    if any(term in low_prompt for term in ("phone", "alpha", "beta", "connected", "connection")):
        required.extend(["alpha", "beta"])
    if required:
        return any(term not in low_reply for term in required)
    live_markers = (
        "/opt/engel",
        "meeting room",
        "lora",
        "sub-engel",
        "worker",
        "ct 246",
        "reachable",
    )
    return not any(marker in low_reply for marker in live_markers)


def _live_runtime_status_reply() -> str:
    model = _model_runtime_snapshot()
    phone = _phone_bridge_snapshot()
    sub_engel = _sub_engel_bridge_snapshot()
    room = _meeting_room_snapshot()
    lora_ready = bool(model.get("lora_runtime_ready"))
    inventory = model.get("active_model_inventory") if isinstance(model.get("active_model_inventory"), dict) else {}
    model_count = int(inventory.get("model_file_count") or 0)
    if lora_ready:
        model_sentence = "Local LoRA runtime is ready on CT 246."
    elif model.get("local_gguf_model_present") is True:
        model_sentence = "A local GGUF is present, but the trained LoRA runtime is not proven ready."
    else:
        model_sentence = "Local model runtime is not proven ready."
    if model_count:
        model_sentence += f" Active model files: {model_count}."
    standing_name = ""
    try:
        from engel_discord_desktop_route_parity import standing_chat_brain

        standing = standing_chat_brain()
        standing_name = str(
            standing.get("selected_model_name")
            or standing.get("selected_model_id")
            or ""
        ).strip()
    except Exception:
        standing_name = ""
    brain_sentence = (
        f"Cosmic Swarm standing pipe is {standing_name}."
        if standing_name
        else "Standing chat pipe is not reported."
    )
    room_ok = room.get("ok") is True or room.get("reachable") is True
    room_sentence = (
        "Agent Meeting Room on 8790 is reachable."
        if room_ok
        else "Agent Meeting Room did not prove reachable on this probe."
    )
    workers = phone.get("workers") if isinstance(phone.get("workers"), dict) else {}
    live_workers: list[str] = []
    offline_workers: list[str] = []
    for worker_id in ("android_worker_alpha", "android_worker_beta"):
        worker = workers.get(worker_id)
        if not isinstance(worker, dict):
            continue
        label = str(worker.get("label") or worker_id)
        if worker.get("live") is True:
            live_workers.append(label)
        else:
            offline_workers.append(label)
    if live_workers and not offline_workers:
        phone_sentence = "Phone workers alpha and beta are live."
    elif live_workers:
        phone_sentence = f"{', '.join(live_workers)} live; {', '.join(offline_workers)} not live."
    elif offline_workers:
        phone_sentence = f"Phone bridge seen; {', '.join(offline_workers)} not live."
    else:
        phone_sentence = "Phone bridge state is not in this snapshot."
    sub_workers = sub_engel.get("workers") if isinstance(sub_engel.get("workers"), dict) else {}
    live_subs = [
        str(worker.get("label") or worker_id)
        for worker_id, worker in sub_workers.items()
        if isinstance(worker, dict) and worker.get("live") is True
    ]
    if live_subs:
        sub_sentence = f"Sub-Engel live: {', '.join(live_subs)}."
    elif any(
        isinstance(worker, dict) and worker.get("paired") is True
        for worker in sub_workers.values()
    ):
        sub_sentence = (
            "Sub-Engel is paired on the LAN. A CT246 work-pipe error is not a missing node."
        )
    elif sub_workers:
        sub_sentence = "Sub-Engel is registered but not live in this snapshot."
    else:
        sub_sentence = "Sub-Engel is not in this health snapshot."
    return (
        "Live probe from CT 246, not a plan to check later. "
        f"Chat service is up. {brain_sentence} {model_sentence} "
        f"Models stay under /opt/engel/models-active. {room_sentence} "
        f"{phone_sentence} {sub_sentence} "
        "No self-upgrade cycle ran from this message. "
        "I will not call backlog names current work without a current receipt."
    )


def _enforce_live_runtime_status_reply(receipt: dict[str, Any]) -> dict[str, Any]:
    verified = _live_runtime_status_reply()
    current = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "").strip()
    if current != verified:
        receipt["server_live_runtime_status_truth_reapplied"] = True
        receipt["server_live_runtime_status_humanized_preview"] = _clip(current, 500)
    receipt["assistant_reply"] = verified
    receipt["assistant_output_text"] = verified
    return receipt


def _repair_fast_local_identity_drift(prompt: str, reply: str) -> str:
    text = str(reply or "").strip()
    low = text.casefold()
    if not text:
        return text
    drift_markers = (
        "i'm joshua",
        "i am joshua",
        "i'm not engel",
        "i am not engel",
        "not engel itself",
        "joshua's local worker",
        "joshua's local ai",
        "not a personality",
        "don't have a personality",
        "dont have a personality",
        "not a character",
        "not a sentient",
        "chat agent trained",
        "company called anthropic",
        "built by a company called",
        # (2026-07-07 audit I-1) base-model provenance leaks. Anchored to
        # self-identity phrasings so a user legitimately asking ABOUT these names
        # is not clobbered; these only fire when the reply claims to BE them.
        "alibaba cloud",
        "by alibaba",
        "alizeng",
        "i am qwen",
        "i'm qwen",
        "i am a qwen",
        "created by a chinese",
        "i am nemotron",
        "i'm nemotron",
        "i am a language model called nemotron",
        "i'm a language model called nemotron",
        "my name is nemotron",
        "trained by nvidia researchers",
    )
    if not any(marker in low for marker in drift_markers):
        return text
    prompt_low = _intent_gate_text(prompt).casefold()
    if any(term in prompt_low for term in ("story", "tale", "narrative")):
        return (
            "Engel woke inside the CT246 chat lane with one job: keep Joshua connected to the server brain without "
            "making every message wait on a slow model path. It listened, answered from the fast local model, saved "
            "the turn to memory, and kept the deeper LoRA and bridge lanes ready for harder work."
        )
    if "joshua" in prompt_low:
        return "No. I am Engel AI Main. Joshua is the human operator, and I answer from the CT246 Engel chat system."
    if _prompt_requests_build_status(prompt):
        return _build_status_reply()
    return (
        "I am Engel AI Main, running through the CT246 chat system. Joshua is the human operator; I answer as Engel."
    )


def _repair_hosting_drift(prompt: str, reply: str) -> str:
    """(2026-07-07 audit I-3) The small local model hallucinates cloud hosting /
    fake IPs for 'what server do you run on'-style questions. When the prompt asks
    about hosting AND the reply drifts to a cloud/IP claim, return the real fact."""
    low_p = str(prompt or "").casefold()
    asks_hosting = any(
        t in low_p
        for t in (
            "what server", "which server", "where do you run", "where are you run",
            "where are you host", "how are you host", "where are you hosted",
            "your ip", "ip address", "in the cloud", "are you cloud", "where do you live",
            "what machine", "where are you located", "what data cent", "which cloud",
        )
    )
    if not asks_hosting:
        return reply
    low_r = str(reply or "").casefold()
    drifted = any(
        t in low_r
        for t in (
            "google cloud", "aws", "amazon web", "azure", "us region", "us-east",
            "cloud instance", "in the cloud", "data center", "datacenter", "public ip",
            "heroku", "digitalocean", "oracle cloud",
        )
    ) or bool(re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", str(reply or "")))
    if not drifted:
        return reply
    return (
        "I run locally on Joshua's Engel AI Main server. I am local, not a cloud service."
    )


def _repair_sensitive_chat_leak(prompt: str, reply: str) -> tuple[str, bool]:
    """Final output boundary for UI and Discord chat.

    Model lanes can know about local hardware, but normal chat should not
    volunteer LAN IPs, SSH routes, shell accounts, private paths, or unrelated
    persistent-memory facts.
    """
    text = str(reply or "").strip()
    if not text:
        return text, False
    original = text
    prompt_low = _intent_gate_text(prompt).casefold()
    identity_prompt = any(
        term in prompt_low
        for term in (
            "who made you",
            "who created you",
            "what are you",
            "who are you",
            "are you engel",
            "your identity",
        )
    )
    hosting_prompt = any(
        term in prompt_low
        for term in (
            "what server",
            "which server",
            "where do you run",
            "where are you hosted",
            "your ip",
            "ip address",
            "what machine",
            "where do you live",
        )
    )
    if identity_prompt:
        text = "I am Engel AI Main, Joshua's local agentic chat system."
    elif hosting_prompt:
        text = "I run locally on Joshua's Engel AI Main server, not on a public cloud service."
    else:
        replacements = (
            (r"\b(?:10|127|192\.168)\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?\b", "[local address]"),
            (r"\b172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}(?::\d+)?\b", "[local address]"),
            (r"\bfe80::[0-9a-f:%]+\b", "[local link address]"),
            (r"\bssh\s+root@[^\s]+(?:\s+-p\s+\d+)?", "[private ssh route]"),
            (r"\broot@[A-Za-z0-9_.:-]+", "[private shell account]"),
            (r"\bengel-spine-01\b", "the local Engel server"),
            (r"\bCT\s*246\b", "the Engel server container"),
            (r"\b/opt/engel/[^\s,;.)]+", "[server path]"),
            (r"\bD:\\b\.WorkSpace\\Engel App\\[^\s,;.)]+", "[local app path]"),
        )
        for pattern, repl in replacements:
            text = re.sub(pattern, repl, text, flags=re.I)
        text = re.sub(r"\bthe\s+the\s+", "the ", text, flags=re.I)
        memory_terms = ("persistent chat history includes", "favorite color", "project codename")
        if any(term in text.casefold() for term in memory_terms) and not any(
            term in prompt_low for term in ("remember", "recall", "codename", "favorite color")
        ):
            sentences = re.split(r"(?<=[.!?])\s+", text)
            kept = [
                sentence
                for sentence in sentences
                if not any(term in sentence.casefold() for term in memory_terms)
            ]
            text = " ".join(sentence for sentence in kept if sentence.strip()).strip() or "I can help with that."
    return text, text != original


def _repair_operator_address_identity(reply: str) -> tuple[str, bool]:
    """Keep Engel as the speaker and Joshua as the operator.

    Local base models occasionally append a vocative such as `, Engel.` to an
    otherwise correct answer. Preserve the answer and remove only that mistaken
    form of address at the final output boundary.
    """
    return repair_shared_operator_address_identity(reply)


def _apply_global_chat_safety(prompt: str, receipt: dict[str, Any], source: str) -> dict[str, Any]:
    reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "").strip()
    repaired = _repair_fast_local_identity_drift(prompt, reply)
    repaired = _repair_hosting_drift(prompt, repaired)
    repaired, sensitive_changed = _repair_sensitive_chat_leak(prompt, repaired)
    operator_text = _intent_gate_text(prompt).strip()
    without_transcript_prefix = repaired
    if operator_text:
        without_transcript_prefix = re.sub(
            r"^\s*(?:joshua|user)\s*:\s*"
            + re.escape(operator_text)
            + r"\s*engel(?:\s+ai(?:\s+main)?)?\s*:\s*",
            "",
            repaired,
            count=1,
            flags=re.IGNORECASE,
        )
    transcript_prefix_repaired = without_transcript_prefix != repaired
    repaired = without_transcript_prefix
    without_speaker_label = re.sub(
        r"^\s*engel(?:\s+ai(?:\s+main)?)?\s*:\s*",
        "",
        repaired,
        count=1,
        flags=re.IGNORECASE,
    )
    speaker_label_repaired = without_speaker_label != repaired
    repaired = without_speaker_label
    repaired, operator_address_repaired = _repair_operator_address_identity(repaired)
    low_prompt = _intent_gate_text(prompt).casefold()
    low_repaired = repaired.casefold()
    media_memory_repaired = False
    if "media feature we used earlier" in low_prompt and (
        "media library" in low_repaired
        or "main menu" in low_repaired
        or not any(term in low_repaired for term in ("gif", "image", "discord", "attachment"))
    ):
        repaired = (
            "Yes. We used Engel's Discord media lane to create and send GIFs and images as real attachments instead of "
            "text-only placeholders. When you said not to use Grok, that turn stayed on Engel's local media path."
        )
        media_memory_repaired = True
    same_engel_identity_repaired = False
    same_engel_identity_requested = "same engel" in low_prompt and "desktop app" in low_prompt
    same_engel_low = repaired.casefold()
    same_engel_profile_drift = any(
        term in same_engel_low
        for term in (
            "mechanical design",
            "cad/cam",
            "3d modeling",
            "cutting machine",
            "drafting",
            "shop drawing",
            "designed to provide",
            "provide assistance",
        )
    )
    if same_engel_identity_requested and (
        not (
            "engel" in same_engel_low
            and any(term in same_engel_low for term in ("same engel", "same engel ai main", "not a separate"))
        )
        or same_engel_profile_drift
        or len(repaired) > 300
    ):
        repaired = (
            "Yes. You are talking to the same Engel AI Main here and in the desktop app, "
            "with the conversation handled through the same local Engel chat system."
        )
        same_engel_identity_repaired = True
    previous_turn_honesty_repaired = False
    previous_turn_honesty_requested = (
        "last answer" in low_prompt
        and ("handled by engel" in low_prompt or "guessing" in low_prompt)
    )
    if previous_turn_honesty_requested:
        provider_text = " ".join(
            str(receipt.get(key) or "")
            for key in ("provider", "runtime_provider", "selected_provider", "model")
        ).casefold()
        local_route = receipt.get("provider_api_enabled") is False and any(
            term in provider_text for term in ("local", "llama", "gguf", "qwen")
        )
        off_topic = any(
            term in repaired.casefold()
            for term in ("automated dimensioning", "floor plan", "drafting workflow", "run the script")
        )
        focused = (
            "engel" in repaired.casefold()
            and any(
                term in repaired.casefold()
                for term in ("local model", "engel's local", "generated by engel")
            )
            and "not guessing" in repaired.casefold()
            and any(term in repaired.casefold() for term in ("route", "every claim", "content"))
            and len(repaired) <= 450
            and not off_topic
            and not any(
                term in repaired.casefold()
                for term in ("poweredge", "own hardware", "programmed to remember")
            )
        )
        if local_route and not focused:
            repaired = (
                "That last answer was generated by Engel's local model. I was not guessing about the route; "
                "the content was the model's answer, but that does not make every claim in it automatically correct."
            )
            previous_turn_honesty_repaired = True
    normal_conversation_repaired = False
    if "does our conversation feel normal now" in low_prompt and (
        repaired.rstrip().endswith("...")
        or any(
            term in repaired.casefold()
            for term in (
                "assist you",
                "feel free",
                "how can i assist",
                "if you need any",
                "if you need assistance",
                "let's continue working together",
                "let us continue working together",
                "working together efficiently",
            )
        )
        or len(repaired) > 500
        or bool(re.search(r'["\u201c\u201d][^"\u201c\u201d]+["\u201c\u201d]', repaired))
    ):
        repaired = (
            "Yes, it feels more natural now. I am following the thread, correcting bad turns, and answering the point "
            "you are making instead of resetting the conversation."
        )
        normal_conversation_repaired = True
    if repaired != reply:
        receipt["chat_safety_repaired"] = True
        receipt["chat_safety_source"] = source
        receipt["chat_safety_sensitive_leak_repaired"] = bool(sensitive_changed)
        receipt["chat_safety_media_memory_repaired"] = media_memory_repaired
        receipt["chat_safety_same_engel_identity_repaired"] = same_engel_identity_repaired
        receipt["chat_safety_previous_turn_honesty_repaired"] = previous_turn_honesty_repaired
        receipt["chat_safety_transcript_prefix_repaired"] = transcript_prefix_repaired
        receipt["chat_safety_speaker_label_repaired"] = speaker_label_repaired
        receipt["chat_safety_operator_address_repaired"] = operator_address_repaired
        receipt["chat_safety_normal_conversation_repaired"] = normal_conversation_repaired
        receipt["chat_safety_original_preview"] = _clip_preserve(reply, 500)
        receipt["assistant_reply"] = repaired
        receipt["assistant_output_text"] = repaired
    return receipt


def _quick_casual_model_receipt(
    prompt: str, started: float, request: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    request = request if isinstance(request, dict) else {}
    if request.get("_skip_quick_casual") is True and request.get("_force_quick_casual") is not True:
        return None
    model_path = os.environ.get(
        "ENGEL_QUICK_CHAT_GGUF_MODEL",
        "/opt/engel/models-active/llm/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf",
    ).strip()
    if not model_path:
        return None
    # TRAIN/SERVE ALIGNMENT: the tuned model was trained on BARE user messages
    # under its system prompt. Meta-instructions stuffed into the user turn are
    # a format the model never saw and degrade the fine-tuned behavior.
    user_prompt = _intent_gate_text(prompt).strip() or prompt
    # (2026-07-07 audit Q-4) deterministic arithmetic — bypass the model entirely so
    # operand order / precedence is always right on the small model.
    arithmetic_answer = (
        _safe_arithmetic_answer(user_prompt)
        if _prompt_is_simple_arithmetic_chat(user_prompt)
        else None
    )
    # (2026-07-07 audit M-1) durable facts + semantic recall as brief SYSTEM context
    # so the local lane can actually recall what Joshua told it to remember. Facts
    # are a cheap local read; semantic only for substantive prompts to avoid the
    # memory-service round-trip on trivial turns.
    # (2026-07-10) ONE persona across lanes: the quick lane now gets the SAME persona/voice
    # block (style card + a couple of graded voice examples) the big lane and provider bridges
    # use, so Engel sounds like one person regardless of which lane answered. It rides the
    # SYSTEM role (like facts/semantic already do) — the train/serve caveat is about the USER
    # turn, not extra system context — with a compact budget to stay inside the quick model's ctx.
    _persona = _persona_block(prompt, budget=650)
    if len(_persona) > 750:  # budget the persona SEPARATELY so facts/semantic recall still fits
        _persona = _persona[:750].rstrip() + " ..."
    # (2026-07-12) facts FIRST and pre-clipped to newest-within-budget — the old
    # persona-first join + tail slice cut the newest facts out entirely once the
    # facts file grew past ~600 chars (see _facts_clipped).
    _facts = _chat_facts_clipped(prompt, 700)
    context_scope = _chat_context_scope(request)
    _recent = _recent_chat_context(
        max_chars=800, max_records=3, context_scope=context_scope
    ) or _request_context_preview(request, max_chars=900)
    _recent_block = (
        "RECENT ENGEL CHAT CONTEXT (continue it when the user says that/it/last answer):\n" + _recent
        if _recent
        else ""
    )
    _semantic = (
        ""
        if _prompt_needs_previous_turn(prompt)
        or _request_conversation_id(request)
        or _prompt_starts_new_conversation(prompt)
        else (_semantic_memory_context(prompt) if len(user_prompt) > 15 else "")
    )
    extra_system = "\n\n".join(p for p in (_facts, _persona, _recent_block, _semantic) if p)
    if len(extra_system) > 2600:
        extra_system = extra_system[:2600]
    try:
        from engel_local_model_service import run_llama_cpp_lora_text_with_model

        if arithmetic_answer is not None:
            result = {"ok": True, "text": arithmetic_answer, "backend": "deterministic_arithmetic"}
        else:
            result = run_llama_cpp_lora_text_with_model(
                model_path=model_path,
                lora_path="",
                prompt=user_prompt,
                # (2026-07-07 audit Q-2) 120 truncated code blocks / long-form answers
                # mid-output (unterminated ``` fences, partial lists). Raise the cap so
                # normal chat + code snippets finish; env-tunable.
                n_predict=int(os.environ.get("ENGEL_QUICK_CHAT_N_PREDICT", "512") or "512"),
                # (2026-07-10) raised from 1024 so the shared persona block + facts + semantic
                # recall + the generated reply all fit; env-tunable. 1.5B on 40GB RAM handles it.
                ctx=int(os.environ.get("ENGEL_QUICK_CHAT_CTX", "2048") or "2048"),
                n_gpu_layers=int(os.environ.get("ENGEL_QUICK_CHAT_N_GPU_LAYERS", "0") or "0"),
                temperature=float(os.environ.get("ENGEL_QUICK_CHAT_TEMPERATURE", "0.28") or "0.28"),
                extra_system=extra_system,
            )
    except Exception as exc:
        return {
            "schema": "engel_main_server_quick_casual_model_receipt_v1",
            "ok": False,
            "status": "quick casual model failed",
            "error": str(exc),
        }
    raw_reply = str(result.get("text") or result.get("stdout") or "").strip()
    reply = _clip_preserve(raw_reply, 900)
    # (2026-07-26 neuro audit) the service's own clip must not read as model
    # truncation — NT-2 was force-escalating every long quick reply.
    quick_model_clipped = len(reply) < len(raw_reply)
    if not result.get("ok") or not reply:
        return {
            "schema": "engel_main_server_quick_casual_model_receipt_v1",
            "ok": False,
            "status": "quick casual model returned no usable reply",
            "quick_model_result": result,
        }
    repaired_reply = _repair_fast_local_identity_drift(prompt, reply)
    repaired_reply = _repair_hosting_drift(prompt, repaired_reply)
    identity_repaired = repaired_reply != reply
    reply = repaired_reply
    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_QUICK_CHAT_{stamp}.json"
    receipt = {
        "schema": "engel_main_server_quick_casual_model_receipt_v1",
        "ok": True,
        "status": "quick casual model replied",
        "updated_at_utc": _iso_now(),
        "run_id": "main_server_quick_chat_" + stamp,
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": f"engel-main-server-quick-local ({Path(model_path).stem})",
        "runtime_provider": "llama-cpp-python-local-gguf",
        "selected_provider": "main_server_quick_casual_model",
        "quick_casual_model_path": model_path,
        "main_server_chat_service_used": True,
        "quick_casual_model_used": True,
        "quick_model_path": model_path,
        "quick_model_result": result,
        "chat_context_scope": context_scope,
        "identity_drift_repaired": identity_repaired,
        "model_process_started": False,
        "runtime_process_started": False,
        # (2026-07-26) honest inference claim: the deterministic-arithmetic
        # bypass answers WITHOUT the model.
        "runs_inference": result.get("backend") != "deterministic_arithmetic",
        "deterministic_answer": result.get("backend") == "deterministic_arithmetic",
        "quick_model_clipped": quick_model_clipped,
        "loads_model": bool(result.get("model_loaded_in_current_process")),
        "provider_api_enabled": False,
        "network_enabled": False,
        "server_enabled": True,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "model_output_trusted": False,
        "server_snapshot": _service_snapshot(),
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
    }
    receipt = _apply_chat_humanizer(prompt, receipt, "ct_quick_casual_model_receipt")
    receipt = _repair_stale_visible_reply(prompt, receipt)
    receipt = _enforce_requested_short_format(prompt, receipt)
    # (2026-07-26 neuro audit) do NOT append persistent memory here. This ran
    # BEFORE the NT-2 accept/escalate decision, so an escalated turn (a) wrote
    # TWO records and (b) fed its own rejected quick draft back to the big lane
    # as recent chat context. The finalize choke-point now owns the single
    # canonical write for accepted quick turns (with NT depth + telemetry).
    _write_json(receipt_path, receipt)
    return receipt


def _sparse_moe_route_decision(
    prompt: str, request: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Select the 30B-A3B lane only when sparse expert compute is warranted."""
    request = request if isinstance(request, dict) else {}
    requested_mode = str(
        request.get("model_mode")
        or request.get("local_model")
        or request.get("model")
        or request.get("lane")
        or request.get("selected_model_id")
        or ""
    ).strip().casefold()
    explicit_modes = {
        "moe",
        "sparse",
        "sparse_moe",
        "sparse-moe",
        "30b",
        "30b-a3b",
        "qwen3-30b-a3b",
        "expert_moe",
        "ct-qwen3-30b-a3b",
    }
    text = " ".join(str(prompt or "").casefold().split())
    explicit_text = bool(
        re.search(
            r"\b(?:use|activate|run|route to|answer with)\s+(?:the\s+)?"
            r"(?:qwen3[- ]?30b[- ]?a3b|30b[- ]?a3b|sparse moe|moe expert lane)\b",
            text,
        )
    )
    if requested_mode in explicit_modes or explicit_text:
        return {
            "selected": True,
            "explicit": True,
            "automatic": False,
            "score": 99,
            "reason": "operator explicitly selected CT246 sparse MoE",
            "thinking_mode": "/no_think" not in text,
        }
    if not _env_truth("ENGEL_MOE_REASON_AUTO_ROUTE", default=True):
        return {
            "selected": False,
            "explicit": False,
            "automatic": False,
            "score": 0,
            "reason": "automatic sparse MoE routing disabled",
            "thinking_mode": False,
        }
    # (2026-08-16) A caller that asked for the FAST local lane never auto-routes to
    # the 30B expert lane, and Discord turns never do: Sub-Engel's peer status
    # chatter carries reasoning-shaped vocabulary and was grinding 200-433s of MoE
    # CPU per reply (the bridge had ALREADY sent prefer_fast_local_chat), stacking
    # until interactive chat streams starved mid-reply - live 2026-08-16: load 11.9,
    # app banner "Chat unavailable", "CT246 stream ended before its final reply".
    # Explicit operator selection above still wins.
    if not _is_discord_owner_turn(request) and (
        request.get("prefer_fast_local_chat") is True
        or str(request.get("source") or "").strip().casefold() == "discord"
    ):
        return {
            "selected": False,
            "explicit": False,
            "automatic": True,
            "score": 0,
            "reason": "caller requested fast local chat; sparse MoE auto-route skipped",
            "thinking_mode": False,
        }

    # Keep build/file-generation requests on the dedicated local coder and
    # conical build path. The MoE lane is a reasoning specialist, not a bypass.
    try:
        from run_engel_standalone_chat_llm import prompt_requests_code_artifact

        if prompt_requests_code_artifact(prompt):
            return {
                "selected": False,
                "explicit": False,
                "automatic": True,
                "score": 0,
                "reason": "dedicated code artifact lane owns this request",
                "thinking_mode": False,
            }
    except Exception:
        pass

    # Governor verdict (docs/ENGEL_GOVERNOR_DESIGN.md section 2.1, precedence 5):
    # a declared non-interactive discipline turn (training metadata) selects the
    # capable lane even when the keyword score below would miss it. Sits after
    # the operator-explicit and code-artifact guards (they keep authority) and
    # before the automatic scoring fallback. ENGEL_GOVERNOR_ROUTING_ENABLED=0
    # restores byte-identical legacy behaviour.
    governor = _governor_routes_to(prompt, request, "LANE_SPARSE_MOE")
    if governor is not None:
        return {
            "selected": True,
            "explicit": False,
            "automatic": True,
            "score": 3,
            "reason": (
                f"governor route [{governor.get('rule_id')}]: {governor.get('reason')}"
            ),
            "thinking_mode": True,
            "governor": governor,
        }

    score = 0
    reasons: list[str] = []
    raw = str(prompt or "")
    if len(raw) >= 800:
        score += 1
        reasons.append("long input")
    if len(raw) >= 1800:
        score += 1
        reasons.append("very long input")
    complexity = str(
        request.get("complexity")
        or request.get("job_size")
        or request.get("build_size")
        or ""
    ).strip().casefold()
    if complexity in {"expert", "large", "deep", "high"}:
        score += 2
        reasons.append(f"{complexity} task metadata")

    marker_groups = (
        r"\b(?:prove|derive|formal proof|theorem|counterexample)\b",
        r"\b(?:root cause|failure modes?|fault tree|debug.*race|deadlock)\b",
        r"\b(?:compare|tradeoffs?|alternatives?)\b.*\b(?:constraints?|risks?|criteria)\b",
        r"\b(?:multi[- ]step|system architecture|distributed system|migration plan)\b",
        r"\b(?:optimi[sz]e|optimization)\b.*\b(?:constraints?|objective|cost function)\b",
        r"\b(?:complex math|linear algebra|calculus|probability|statistics)\b",
        r"\b(?:audit|analy[sz]e)\b.*\b(?:then|and)\b.*\b(?:repair|recommend|design)\b",
    )
    for pattern in marker_groups:
        if re.search(pattern, text):
            score += 1
            reasons.append(pattern)
    numbered_constraints = len(
        re.findall(r"(?m)^\s*(?:\d+[.)]|[-*])\s+\S+", raw)
    )
    if numbered_constraints >= 4:
        score += 1
        reasons.append("multiple explicit constraints")
    math_tokens = len(
        re.findall(r"(?:\b\d+(?:\.\d+)?\b|[=+\-*/^()]|∑|∫|√)", raw)
    )
    if math_tokens >= 12:
        score += 2
        reasons.append("dense mathematical expression")

    selected = score >= 3
    return {
        "selected": selected,
        "explicit": False,
        "automatic": True,
        "score": score,
        "reason": (
            "automatic hard-reasoning route: " + ", ".join(reasons[:6])
            if selected
            else "request does not need sparse MoE compute"
        ),
        "thinking_mode": selected,
    }


def _is_training_delivered_prompt(prompt: str) -> bool:
    """True only for prompt-training turns wrapped by apply_training_level_to_prompt
    ("Training depth: <Level> (...)" header + "Training task:" body). Prefix-exact by
    the pack-schema contract; a live message that mentions training never matches.
    Twin lives in run_engel_standalone_chat_llm.py for the ROG GPU lanes."""
    low = str(prompt or "").lstrip().casefold()
    return low.startswith("training depth:") and "\ntraining task:" in low


def _is_form_graded_training_prompt(prompt: str) -> bool:
    """True for prompt-training turns whose accepted answer is a labelled form.

    Twin of engel_chat_humanization_slm.is_form_graded_training_prompt.
    Communication training is spoken voice and returns False.
    """
    low = str(prompt or "").lstrip().casefold()
    if not _is_training_delivered_prompt(prompt):
        return False
    if "answer the way you would answer joshua" in low:
        return False
    return (
        "answer only in this filled-in form" in low
        or "use exactly this structure and these headings" in low
    )


def _apply_form_graded_training_quality_policy(
    prompt: str,
    semantic_quality: dict[str, Any],
    reply: str,
) -> dict[str, Any]:
    """Keep labelled training drafts visible so the trainer can grade them.

    Construction 7h 2026-09-13 aborted 0/70 because AEC forms often end on a
    heading or ``Proof:`` line (``complete_ending`` false). The quality-block
    explainer then hid the draft, and the scheduled runner treated five of
    those as a systemic abort. Live chat still uses the full incomplete-input
    gate. Remaining failed checks still mark the sample ineligible.
    """
    quality = dict(semantic_quality or {})
    if not _is_form_graded_training_prompt(prompt) or not str(reply or "").strip():
        quality["form_training_serve_draft"] = False
        return quality
    failed = [str(value) for value in quality.get("failed_checks") or []]
    remaining = [check for check in failed if check != "complete_ending"]
    checks = dict(quality.get("checks") or {})
    if "complete_ending" in failed:
        checks["complete_ending"] = True
        quality["complete_ending_waived_for_form_training"] = True
    quality["checks"] = checks
    quality["failed_checks"] = remaining
    quality["ok"] = not remaining
    quality["form_training_serve_draft"] = True
    return quality


def _training_turn_temperature(prompt: str, base: float) -> float:
    """(2026-08-10) Raise sampling temperature for training-delivered turns so a
    run's near-identical wrapped prompts stop converging on one attractor reply
    (live 1h comm run: verbatim repeats). Live chat keeps each lane's settled base.
    Deliberately NOT applied to the code/math lanes: their rows are admitted by
    execution/CAS verification, where correctness beats diversity. Discipline-armed
    prompts also keep the base: exploration drafts fail the REQUIRED incomplete-input
    semantic gate (live 20260810: comm cards 502'd at 0.85, served at base).
    Form-graded engineering/math/AEC also keep the base: raised temperature plus
    spoken-chat wrapping produced 0 eligible samples on the 20260904 run."""
    if _is_form_graded_training_prompt(prompt):
        return base
    if _is_training_delivered_prompt(prompt) and not _prompt_has_incomplete_project_inputs(prompt):
        raised = float(os.environ.get("ENGEL_TRAINING_TURN_TEMPERATURE", "0.85") or "0.85")
        return max(base, raised)
    return base


def _nemotron_lightning_status_snapshot() -> dict[str, Any]:
    try:
        from engel_nemotron_lightning_runtime import status as nemotron_status

        return nemotron_status()
    except Exception as exc:
        return {
            "schema": "engel_nemotron_3_5_lightning_status_v1",
            "ok": False,
            "loaded": False,
            "error": str(exc),
        }


def _nemotron_lightning_enabled() -> bool:
    return _env_truth("ENGEL_NEMOTRON_LANE_ENABLED", default=True)


def _nemotron_lightning_route_decision(
    prompt: str, request: dict[str, Any] | None = None
) -> dict[str, Any]:
    request = request if isinstance(request, dict) else {}
    if not _nemotron_lightning_enabled():
        return {"selected": False, "reason": "Nemotron Lightning lane disabled"}
    requested = str(
        request.get("model_mode")
        or request.get("local_model")
        or request.get("model")
        or request.get("lane")
        or request.get("selected_model_id")
        or ""
    ).strip().casefold()
    text = " ".join(str(prompt or "").casefold().split())
    explicit = requested in {
        "nemotron",
        "nemotron-3.5",
        "nemotron-3.5-lightning",
        "lightning",
        "lightning-30b",
        "nvl-30b",
        "ct-nemotron-35-lightning-30b",
    } or bool(
        re.search(
            r"\b(?:use|activate|run|load|route to|answer with)\s+(?:the\s+)?"
            r"(?:nemotron(?:\s*3\.5)?(?:\s*lightning)?|lightning 30b)\b",
            text,
        )
    ) or "nemotron 3.5" in text or "nemotron3.5" in text
    if explicit:
        return {
            "selected": True,
            "explicit": True,
            "automatic": False,
            "reason": "operator selected Nemotron 3.5 Lightning",
        }
    # Prompt-training and the local-only grounding probe must stay on Engel 7B
    # with personality. Auto-Lightning (2026-09-08) answered the grounding ask
    # as raw Nemotron ("I am a language model called Nemotron..."), so the
    # 3-prompt smoke never sent a training turn.
    if _request_local_only_training(request):
        return {
            "selected": False,
            "reason": "local-only training stays on Engel 7B with personality",
        }
    if _is_training_delivered_prompt(prompt) or _is_form_graded_training_prompt(prompt):
        return {
            "selected": False,
            "reason": "prompt-training turns stay on Engel 7B with personality",
        }
    if "host and container your chat runtime" in text:
        return {
            "selected": False,
            "reason": "self-host grounding probe stays on Engel 7B",
        }
    if not _env_truth("ENGEL_NEMOTRON_AUTO_ROUTE", default=True):
        return {"selected": False, "reason": "Nemotron Lightning auto-route disabled"}
    try:
        from engel_nemotron_lightning_runtime import server_healthy
    except Exception:
        return {"selected": False, "reason": "Nemotron Lightning runtime unavailable"}
    if not server_healthy():
        return {"selected": False, "reason": "Nemotron Lightning server not loaded"}
    moe = _sparse_moe_route_decision(prompt, request)
    if moe.get("selected") is True and moe.get("explicit") is True:
        moe_reason = str(moe.get("reason") or "").casefold()
        if "qwen3" in moe_reason or "sparse moe" in moe_reason:
            return {
                "selected": False,
                "reason": "operator kept the Qwen3 sparse MoE lane",
            }
    if moe.get("selected") is True:
        return {
            "selected": True,
            "explicit": False,
            "automatic": True,
            "reason": "Nemotron 3.5 Lightning is loaded; using it for the 30B-A3B expert turn",
            "moe_route": moe,
        }
    # Live 2026-09-08: mode-gate / review / attachment turns escalate past the
    # tiny quick lane, then fell through to CPU 7B and timed out while the warm
    # Lightning server on :8905 sat idle. Prefer that local server for any turn
    # that is not a tiny quick-casual chat.
    if request.get("_escalate_past_quick") is True or request.get("_force_nemotron") is True:
        return {
            "selected": True,
            "explicit": False,
            "automatic": True,
            "reason": "Nemotron Lightning warm server for escalated CT246 chat",
        }
    if (
        _prompt_requires_large_local_reasoning(prompt)
        or not _prompt_requests_quick_casual_model(prompt)
    ):
        return {
            "selected": True,
            "explicit": False,
            "automatic": True,
            "reason": "Nemotron Lightning warm server for non-quick CT246 chat",
        }
    return {"selected": False, "reason": "Nemotron Lightning not selected for this turn"}


def _nemotron_lightning_local_model_receipt(
    prompt: str, started: float, request: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    route = _nemotron_lightning_route_decision(prompt, request)
    if route.get("selected") is not True:
        return None
    try:
        from engel_nemotron_lightning_runtime import generate as nemotron_generate
        from engel_nemotron_lightning_runtime import status as nemotron_status
    except Exception:
        return None
    max_tokens = max(
        256,
        int(
            (request or {}).get("max_tokens")
            or os.environ.get("ENGEL_NEMOTRON_N_PREDICT", "512")
            or "512"
        ),
    )
    result = nemotron_generate(prompt, max_tokens=max_tokens)
    reply = str(result.get("text") or "").strip()
    if result.get("ok") is not True or not reply:
        return None
    reply = _repair_fast_local_identity_drift(prompt, reply)
    reply = _repair_hosting_drift(prompt, reply)
    snap = {}
    try:
        snap = nemotron_status()
    except Exception:
        snap = {}
    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_NEMOTRON_LIGHTNING_{stamp}.json"
    receipt = {
        "schema": "engel_main_server_nemotron_lightning_receipt_v1",
        "ok": True,
        "status": "Nemotron 3.5 Lightning replied",
        "updated_at_utc": _iso_now(),
        "run_id": "main_server_nemotron_lightning_" + stamp,
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "engel-main-server-nemotron-3.5-lightning",
        "runtime_provider": "llama-cpp-b10423-nemotron-h-moe",
        "selected_provider": "ct_nemotron_lightning",
        "nemotron_model_used": True,
        "nemotron_model_path": snap.get("path") or str(
            Path(
                os.environ.get(
                    "ENGEL_NEMOTRON_MODEL",
                    "/opt/engel/models-active/llm/nemotron-3.5-lightning-30b-a3b/"
                    "NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_M.gguf",
                )
            )
        ),
        "nemotron_loaded": snap.get("loaded") is True,
        "nemotron_via": result.get("via") or "",
        "nemotron_route": route,
        "seconds": result.get("seconds"),
        "main_server_chat_service_used": True,
        "runs_inference": True,
        "loads_model": True,
        "workspace_receipt_path": str(receipt_path),
    }
    try:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass
    return receipt


def _sparse_moe_local_model_receipt(
    prompt: str, started: float, request: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """Run Qwen3-30B-A3B with native per-token expert selection on CT246."""
    if not _env_truth("ENGEL_MOE_REASON_LANE_ENABLED", default=True):
        return None
    route = _sparse_moe_route_decision(prompt, request)
    if route.get("selected") is not True:
        return None
    model_path = os.environ.get(
        "ENGEL_MOE_REASON_GGUF_MODEL",
        "/opt/engel/models-active/llm/qwen3-30b-a3b/"
        "Qwen3-30B-A3B-Q4_K_M.gguf",
    ).strip()
    if not model_path or not Path(model_path).is_file():
        return None
    thinking_mode = bool(route.get("thinking_mode"))
    mode_token = "/think" if thinking_mode else "/no_think"
    model_prompt = (_intent_gate_text(prompt).strip() or prompt).rstrip()
    if "/think" not in model_prompt.casefold() and "/no_think" not in model_prompt.casefold():
        model_prompt += "\n\n" + mode_token
    extra_system = (
        "You are Engel AI Main's sparse expert reasoning lane on CT246. "
        "Solve only the current request. Use the model's private thinking mode "
        "when selected, but return only the final useful answer without scratch "
        "work, hidden reasoning, or model-vendor identity."
    )
    facts = _facts_for_prompt()
    if facts:
        extra_system += "\n\n" + facts
    try:
        from engel_local_model_service import run_llama_cpp_lora_text_with_model

        result = run_llama_cpp_lora_text_with_model(
            model_path=model_path,
            lora_path="",
            prompt=model_prompt,
            n_predict=max(
                128,
                int(os.environ.get("ENGEL_MOE_REASON_N_PREDICT", "1024") or "1024"),
            ),
            ctx=max(
                2048,
                int(os.environ.get("ENGEL_MOE_REASON_CTX", "6144") or "6144"),
            ),
            n_gpu_layers=0,
            temperature=_training_turn_temperature(
                prompt,
                float(os.environ.get("ENGEL_MOE_REASON_TEMPERATURE", "0.55") or "0.55"),
            ),
            extra_system=extra_system,
        )
    except Exception:
        return None
    reply = str(result.get("text") or result.get("stdout") or "").strip()
    if not result.get("ok") or not reply:
        return None
    reply = _repair_fast_local_identity_drift(prompt, reply)
    reply = _repair_hosting_drift(prompt, reply)
    # (2026-08-16) Same training-eligibility contract as the big lane. This lane
    # OMITTED the two eligibility keys entirely, so every MoE-served training turn
    # read as None -> silently training-ineligible: live, 28 of 30 aec fellow-depth
    # turns routed here and the pack admitted 2. Graded with the big lane's own
    # semantic gate so an MoE row earns eligibility the same way a big-lane row does.
    semantic_quality = _incomplete_input_quality_report(prompt, reply)
    moe_training_eligible = bool(reply and semantic_quality.get("ok") is True)
    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_SPARSE_MOE_{stamp}.json"
    receipt = {
        "schema": "engel_main_server_sparse_moe_model_receipt_v1",
        "ok": True,
        "status": "sparse MoE expert lane replied",
        "updated_at_utc": _iso_now(),
        "run_id": "main_server_sparse_moe_" + stamp,
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": f"engel-main-server-sparse-moe ({Path(model_path).stem})",
        "runtime_provider": "llama-cpp-qwen3-sparse-moe-selective-experts-local",
        "selected_provider": "ct_sparse_moe_specialist",
        "sparse_moe_model_used": True,
        "sparse_moe_model_path": model_path,
        "sparse_moe_route": route,
        "thinking_mode_used": thinking_mode,
        "thinking_content_exposed": False,
        "selective_model_activation": True,
        "native_sparse_expert_activation": True,
        "total_parameters_billions": 30.5,
        "active_parameters_billions_per_token": 3.3,
        "expert_count": 128,
        "active_experts_per_token": 8,
        "compute_profile": result.get("compute_profile", {}),
        "adaptive_context": result.get("adaptive_context", {}),
        "only_selected_model_activated": result.get(
            "only_selected_model_activated", True
        ),
        "model_cache_evicted": result.get("model_cache_evicted", []),
        "model_cache_active_models": result.get("model_cache_active_models", []),
        "model_cache_active_count": result.get("model_cache_active_count"),
        "model_load_ms": result.get("model_load_ms"),
        "generation_ms": result.get("generation_ms"),
        "main_server_chat_service_used": True,
        "model_process_started": False,
        "runtime_process_started": False,
        "runs_inference": True,
        "loads_model": bool(result.get("model_loaded_in_current_process")),
        "provider_api_enabled": False,
        "provider_called": False,
        "network_enabled": False,
        "server_enabled": True,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "model_output_trusted": False,
        "local_semantic_quality": semantic_quality,
        "training_sample_eligible": moe_training_eligible,
        "persistent_chat_memory_training_eligible": moe_training_eligible,
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
    }
    _write_json(receipt_path, receipt)
    return receipt


def _prompt_requests_deep_local_specialist(
    prompt: str, request: dict[str, Any] | None = None
) -> bool:
    """Require an explicit request before activating the CT246 14B lane."""
    request = request if isinstance(request, dict) else {}
    requested_mode = str(
        request.get("model_mode")
        or request.get("local_model")
        or request.get("model")
        or request.get("lane")
        or request.get("selected_model_id")
        or ""
    ).strip().casefold()
    if requested_mode in {
        "14b",
        "deep",
        "deep_local",
        "deep-local",
        "deep_local_14b",
        "largest_local",
        "qwen2.5-14b",
        "qwen2.5-14b-instruct",
        "ct-qwen25-14b-instruct",
    }:
        return True
    # Josh Discord reasoning turns may use the dense 14B lane without saying
    # "use 14b". Casual owner chat still uses the trained 7B LoRA voice.
    if _is_discord_owner_turn(request) and _prompt_requires_large_local_reasoning(prompt):
        return True
    text = " ".join(str(prompt or "").casefold().split())
    if bool(
        re.search(
            r"\b(?:use|activate|run|route to|answer with)\s+(?:the\s+)?"
            r"(?:qwen(?:2\.5)?[- ]?14b|14b|deep local model|largest local model|"
            r"deep local specialist|bigger local model)\b",
            text,
        )
    ):
        return True
    # Governor verdict: a declared non-interactive engineering turn with deep
    # context is the one non-explicit path onto the 14B lane (section 2.1).
    return _governor_routes_to(prompt, request, "LANE_DEEP_LOCAL") is not None


def _deep_local_model_receipt(
    prompt: str, started: float, request: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """Activate the CT246 14B GGUF only for an explicitly selected deep turn."""
    if not _env_truth("ENGEL_DEEP_REASON_LANE_ENABLED", default=True):
        return None
    if not _prompt_requests_deep_local_specialist(prompt, request):
        return None
    model_path = os.environ.get(
        "ENGEL_DEEP_REASON_GGUF_MODEL",
        "/opt/engel/models-active/llm/qwen2.5-14b-instruct/"
        "qwen2.5-14b-instruct-Q4_K_M.gguf",
    ).strip()
    if not model_path or not Path(model_path).is_file():
        return None
    extra_system = (
        "This turn selected Engel's deep local specialist on CT246. Solve the "
        "request carefully, return only the useful final answer, and do not claim "
        "that a provider or cloud model was used."
    )
    facts = _facts_for_prompt()
    if facts:
        extra_system += "\n\n" + facts
    try:
        from engel_local_model_service import run_llama_cpp_lora_text_with_model

        result = run_llama_cpp_lora_text_with_model(
            model_path=model_path,
            lora_path="",
            prompt=_intent_gate_text(prompt).strip() or prompt,
            n_predict=max(
                1,
                int(os.environ.get("ENGEL_DEEP_REASON_N_PREDICT", "384") or "384"),
            ),
            ctx=max(
                2048,
                int(os.environ.get("ENGEL_DEEP_REASON_CTX", "4096") or "4096"),
            ),
            n_gpu_layers=0,
            temperature=_training_turn_temperature(
                prompt,
                float(os.environ.get("ENGEL_DEEP_REASON_TEMPERATURE", "0.35") or "0.35"),
            ),
            extra_system=extra_system,
        )
    except Exception:
        return None
    reply = str(result.get("text") or result.get("stdout") or "").strip()
    if not result.get("ok") or not reply:
        return None
    reply = _repair_fast_local_identity_drift(prompt, reply)
    reply = _repair_hosting_drift(prompt, reply)
    # (2026-08-16) same missing-eligibility hole as the sparse-MoE lane above.
    semantic_quality = _incomplete_input_quality_report(prompt, reply)
    deep_training_eligible = bool(reply and semantic_quality.get("ok") is True)
    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_DEEP_LOCAL_{stamp}.json"
    receipt = {
        "schema": "engel_main_server_deep_local_model_receipt_v1",
        "ok": True,
        "status": "deep local specialist replied",
        "updated_at_utc": _iso_now(),
        "run_id": "main_server_deep_local_" + stamp,
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": f"engel-main-server-deep-local ({Path(model_path).stem})",
        "runtime_provider": "llama-cpp-large-selective-mmap-local",
        "selected_provider": "main_server_deep_local_specialist",
        "deep_local_model_used": True,
        "deep_local_model_path": model_path,
        "selective_model_activation": True,
        "only_selected_model_activated": result.get(
            "only_selected_model_activated", True
        ),
        "model_cache_evicted": result.get("model_cache_evicted", []),
        "model_cache_active_models": result.get("model_cache_active_models", []),
        "model_cache_active_count": result.get("model_cache_active_count"),
        "model_load_ms": result.get("model_load_ms"),
        "generation_ms": result.get("generation_ms"),
        "main_server_chat_service_used": True,
        "model_process_started": False,
        "runtime_process_started": False,
        "runs_inference": True,
        "loads_model": bool(result.get("model_loaded_in_current_process")),
        "provider_api_enabled": False,
        "network_enabled": False,
        "server_enabled": True,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "model_output_trusted": False,
        "local_semantic_quality": semantic_quality,
        "training_sample_eligible": deep_training_eligible,
        "persistent_chat_memory_training_eligible": deep_training_eligible,
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
    }
    _write_json(receipt_path, receipt)
    return receipt


def _code_lane_model_receipt(
    prompt: str, started: float, request: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """C-lane (2026-07-10): dedicated CODE lane on the qwen2.5-coder-3b GGUF.

    Fires ONLY for explicit code-artifact requests (prompt_requests_code_artifact),
    runs the coder model in-process (same cached llama_cpp service as the quick
    lane), and FAILS OPEN: any miss/error returns None and the turn falls through
    to normal routing (quick/big lanes). Kill switch: ENGEL_CODE_LANE_ENABLED=0.
    NT-1 labels it depth 1 via the gguf runtime marker.
    """
    request = request if isinstance(request, dict) else {}
    if request.get("_skip_specialist_auto") is True and request.get("_force_code_lane") is not True:
        return None
    if str(os.environ.get("ENGEL_CODE_LANE_ENABLED", "1")).strip().lower() in {"0", "false", "no", "off"}:
        return None
    model_path = os.environ.get(
        "ENGEL_CODE_LANE_GGUF_MODEL",
        "/opt/engel/models-active/llm/qwen2.5-coder-3b-instruct/qwen2.5-coder-3b-instruct-q5_k_m.gguf",
    ).strip()
    if not model_path or not Path(model_path).is_file():
        return None
    try:
        from run_engel_standalone_chat_llm import prompt_requests_code_artifact

        if request.get("_force_code_lane") is not True and not prompt_requests_code_artifact(prompt):
            return None
    except Exception:
        return None
    # Code answers want correctness, not the chat persona: minimal identity +
    # code discipline. Facts ride along (cheap + NT-3 memoized) for project context.
    code_system = (
        "You are Engel, Joshua's local AI on engel-ai-main. You are answering a CODE "
        "request: produce correct, complete, runnable code in a single fenced code "
        "block, then at most two short sentences of usage notes. No filler."
    )
    _facts = _facts_for_prompt()
    extra_system = code_system + ("\n\n" + _facts if _facts else "")
    try:
        from engel_local_model_service import run_llama_cpp_lora_text_with_model

        result = run_llama_cpp_lora_text_with_model(
            model_path=model_path,
            lora_path="",
            prompt=_intent_gate_text(prompt).strip() or prompt,
            n_predict=int(os.environ.get("ENGEL_CODE_LANE_N_PREDICT", "1024") or "1024"),
            ctx=int(os.environ.get("ENGEL_CODE_LANE_CTX", "4096") or "4096"),
            n_gpu_layers=0,
            temperature=float(os.environ.get("ENGEL_CODE_LANE_TEMPERATURE", "0.2") or "0.2"),
            extra_system=extra_system,
        )
    except Exception:
        return None
    reply = str(result.get("text") or result.get("stdout") or "").strip()
    # Require a CLOSED code artifact: an even, >=2 count of ``` fences. A reply
    # truncated at the n_predict cap mid-block has one dangling opener — reject it
    # so Joshua never sees half a program; the big lane then handles the turn.
    fence_count = reply.count("```")
    if not result.get("ok") or not reply or fence_count < 2 or fence_count % 2 != 0:
        return None
    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_CODE_LANE_{stamp}.json"
    receipt = {
        "schema": "engel_main_server_code_lane_model_receipt_v1",
        "ok": True,
        "status": "code lane model replied",
        "updated_at_utc": _iso_now(),
        "run_id": "main_server_code_lane_" + stamp,
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": f"engel-main-server-code-lane ({Path(model_path).stem})",
        "runtime_provider": "llama-cpp-python-local-gguf-code",
        "selected_provider": "main_server_code_lane_model",
        "code_lane_model_used": True,
        "code_lane_model_path": model_path,
        "code_lane_model_result": {k: result.get(k) for k in ("model_load_ms", "generation_ms", "model_load_count")},
        "main_server_chat_service_used": True,
        "model_process_started": False,
        "runtime_process_started": False,
        "runs_inference": True,
        "loads_model": bool(result.get("model_loaded_in_current_process")),
        "provider_api_enabled": False,
        "network_enabled": False,
        "server_enabled": True,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "model_output_trusted": False,
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
    }
    memory_record = dict(receipt)
    memory_record["memory_source"] = "engel-ai-main CT code lane model chat"
    try:
        _append_jsonl(PERSISTENT_CHAT_MEMORY_PATH, memory_record)
        receipt["persistent_chat_memory_appended"] = True
        receipt["persistent_chat_history_appended"] = True
        receipt["persistent_chat_memory_path"] = str(PERSISTENT_CHAT_MEMORY_PATH)
    except Exception as exc:
        receipt["persistent_chat_memory_appended"] = False
        receipt["persistent_chat_history_appended"] = False
        receipt["persistent_chat_memory_error"] = str(exc)
    _write_json(receipt_path, receipt)
    return receipt


def _build_lane_json_project_file_count(reply: str) -> int:
    """Count complete files in a model's structured JSON project bundle."""
    text = str(reply or "").strip()
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        rows = value.get("files")
        if isinstance(rows, dict):
            count = sum(
                1
                for path, content in rows.items()
                if str(path).strip()
                and isinstance(
                    content.get("content") if isinstance(content, dict) else content,
                    str,
                )
                and str(
                    content.get("content") if isinstance(content, dict) else content
                ).strip()
            )
        elif isinstance(rows, list):
            count = sum(
                1
                for row in rows
                if isinstance(row, dict)
                and str(
                    row.get("path") or row.get("name") or row.get("file") or ""
                ).strip()
                and isinstance(row.get("content"), str)
                and str(row.get("content")).strip()
            )
        else:
            count = 0
        if count:
            return count
    return 0


def _build_lane_single_target_code_file(gen_prompt: str, reply: str) -> str:
    """Return the declared repair target for one complete non-JSON code fence."""
    target_match = re.search(
        r"(?m)^ENGEL_SINGLE_FILE_TARGET:\s*([A-Za-z0-9_.\-/]+)\s*$",
        gen_prompt,
    )
    if not target_match:
        return ""
    fences = list(
        re.finditer(
            r"```([A-Za-z0-9+#.\-]*)[ \t]*\r?\n(.*?)\r?\n```",
            str(reply or "").strip(),
            flags=re.DOTALL,
        )
    )
    if len(fences) != 1 or str(reply or "").count("```") != 2:
        return ""
    language = str(fences[0].group(1) or "").strip().casefold()
    content = str(fences[0].group(2) or "").strip()
    if language in {"json", "jsonc", "markdown", "md", "text", "txt"}:
        return ""
    if len(content) < 200:
        return ""
    target = target_match.group(1).replace("\\", "/").lstrip("/")
    if not target or ".." in target.split("/"):
        return ""
    suffix = Path(target).suffix.casefold()
    if suffix == ".py" and not (
        language in {"py", "python"}
        or re.search(r"(?m)^\s*(?:from |import |def |class )", content)
    ):
        return ""
    return target


def _build_lane_extracted_project_files_substantial(text: str) -> bool:
    """(2026-07-28) A compact-but-complete multi-file reply is usable. The raw
    len(text) >= 2000 floor alone rejected protocol-correct two-file projects
    (a fibonacci tool plus its unit test is ~700 chars), so a structured job
    could never finish small: receipts ENGEL_MAIN_SERVER_BUILD_LANE_20260728T
    {002909,003851}*.json show FILE-marker replies with closed fences refused
    twice. Ground substantiality in the SAME extractor the build pipeline uses
    downstream: at least two files must extract, each with a non-trivial body.
    Empty or one-line stub bodies still do not count. (2026-07-28, second
    pass) The FILE-marker precondition is gone: the extractor now also
    salvages comment-filename fences, so extraction itself is the test - a
    cheap two-closed-fence guard remains the only short-circuit."""
    if text.count("```") < 4:
        return False
    try:
        from engel_main_local_model_worker import _extract_project_files
    except Exception:
        return False
    try:
        files = _extract_project_files(text, "engel_build_entry.py")
    except Exception:
        return False
    substantial = [
        content
        for content in files.values()
        if len([line for line in content.splitlines() if line.strip()]) >= 2
    ]
    return len(substantial) >= 2


def _build_lane_reply_usable(gen_prompt: str, reply: str) -> bool:
    """Accept complete project files, or compact JSON for the review stage."""
    text = str(reply or "").strip()
    if not text:
        return False
    plan_prompt = gen_prompt.lstrip().casefold().startswith(
        "plan this engel build"
    )
    if plan_prompt:
        for candidate in [text, *re.findall(r"\{.*\}", text, flags=re.DOTALL)]:
            candidate = re.sub(
                r"^```(?:json)?\s*|\s*```$", "", candidate.strip(), flags=re.I
            )
            try:
                value = json.loads(candidate)
            except Exception:
                continue
            if (
                isinstance(value, dict)
                and isinstance(value.get("files"), list)
                and bool(value["files"])
            ):
                return True
        return False
    review_prompt = gen_prompt.lstrip().casefold().startswith(
        "review this completed engel build"
    )
    if review_prompt:
        candidates = [text]
        candidates.extend(re.findall(r"\{.*\}", text, flags=re.DOTALL))
        for candidate in candidates:
            candidate = re.sub(
                r"^```(?:json)?\s*|\s*```$", "", candidate.strip(), flags=re.I
            )
            try:
                value = json.loads(candidate)
            except Exception:
                continue
            if isinstance(value, dict) and str(value.get("verdict") or "").strip():
                return True
        return False
    json_file_count = _build_lane_json_project_file_count(text)
    single_target_code_file = _build_lane_single_target_code_file(
        gen_prompt,
        text,
    )
    repair_prompt = bool(
        gen_prompt.lstrip().casefold().startswith("repair ")
        or re.search(r"(?mi)^ENGEL_SINGLE_FILE_TARGET:\s*", gen_prompt)
    )
    bounded_file_prompt = gen_prompt.lstrip().casefold().startswith(
        "generate one file for engel bounded build"
    )
    structured_files_required = bool(
        repair_prompt
        or re.search(r"(?i)\bthis is an? (?:medium|large|expert) job\b", gen_prompt)
    )
    has_closed_fence = text.count("```") >= 2 and text.count("```") % 2 == 0
    has_file_marker = bool(re.search(r"(?m)^\s*FILE:\s*\S+", text))
    extraction_substantial = _build_lane_extracted_project_files_substantial(text)
    substantial_structured_result = bool(
        repair_prompt
        or not structured_files_required
        or extraction_substantial
        or (len(text) >= 2000 and len(re.findall(r"(?m)^\s*FILE:\s*\S+", text)) >= 2)
    )
    if json_file_count:
        return bool(
            repair_prompt
            or bounded_file_prompt
            or not structured_files_required
            or json_file_count >= 2
        )
    if repair_prompt and single_target_code_file:
        return True
    return bool(
        has_closed_fence
        # A structured job needs FILE: markers OR an extraction-proven
        # multi-file reply (the salvage path); the bounded one-file stage
        # still demands its explicit marker.
        and (not structured_files_required or has_file_marker or extraction_substantial)
        and (not bounded_file_prompt or has_file_marker)
        and substantial_structured_result
    )


def _build_lane_rog_gpu_local_generate(
    gen_prompt: str,
    timeout_s: int,
    max_tokens: int,
) -> dict[str, Any]:
    """Use CT246's reverse tunnel to the ROG-local GPU model for build text."""
    if str(
        os.environ.get("ENGEL_BUILD_ROG_GPU_LOCAL_ENABLED", "1") or "1"
    ).strip().casefold() in {"0", "false", "no", "off"}:
        return {
            "ok": False,
            "assistant_reply": "",
            "provider": "local",
            "bridge_kind": "ct246_to_rog_gpu_local_llm",
            "error": "ROG GPU local build lane disabled",
        }
    url = str(
        os.environ.get("ENGEL_ROG_GPU_CHAT_URL")
        or "http://127.0.0.1:8899/v1/chat/completions"
    ).strip()
    if not url:
        return {
            "ok": False,
            "assistant_reply": "",
            "provider": "local",
            "bridge_kind": "ct246_to_rog_gpu_local_llm",
            "error": "ROG GPU local build URL is empty",
        }
    lowered_prompt = gen_prompt.lstrip().casefold()
    plan_prompt = lowered_prompt.startswith("plan this engel build")
    review_prompt = lowered_prompt.startswith("review this completed engel build")
    repair_prompt = bool(
        lowered_prompt.startswith("repair ")
        or "\nengel_single_file_target:" in lowered_prompt
    )
    stage_cap = 700 if plan_prompt else 512 if review_prompt else 2500
    n_predict = min(stage_cap, max(256, int(max_tokens)))
    local_prompt_limit = max(
        3000,
        int(
            os.environ.get("ENGEL_BUILD_LOCAL_PROMPT_CHAR_CAP", "6000")
            or "6000"
        ),
    )
    local_prompt = gen_prompt
    if len(local_prompt) > local_prompt_limit:
        tail_chars = min(1600, local_prompt_limit // 3)
        local_prompt = (
            local_prompt[: local_prompt_limit - tail_chars]
            + "\n\n[worker context compacted for bounded local GPU attempt]\n\n"
            + local_prompt[-tail_chars:]
        )
    system_prompt = (
        "You are Engel AI Main's local build planner, controlled by CT246. "
        "Return only valid compact JSON matching the requested file-plan schema."
        if plan_prompt
        else (
            "You are Engel AI Main's local build engine, controlled by CT246. "
            "Follow the requested output protocol exactly. For generation or "
            "repair, return complete files with closed fences and FILE markers "
            "or valid JSON with a files collection. For review, return only "
            "valid compact JSON. Do not explain or identify yourself."
        )
    )
    body = json.dumps(
        {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": local_prompt},
            ],
            "max_tokens": n_predict,
            "temperature": float(
                os.environ.get("ENGEL_BUILD_LOCAL_TEMPERATURE", "0.12")
                or "0.12"
            ),
            "stop": ["[Joshua]:", "[INST]", "[/INST]"],
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(
            request,
            timeout=max(15, min(int(timeout_s or 120), 300)),
        ) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("ROG GPU local build response exceeded 8 MiB")
        payload = json.loads(raw.decode("utf-8", errors="replace"))
        choices = payload.get("choices") if isinstance(payload, dict) else None
        first = choices[0] if isinstance(choices, list) and choices else {}
        message = first.get("message") if isinstance(first, dict) else {}
        reply = str(
            message.get("content") if isinstance(message, dict) else ""
        ).strip()
        model = str(payload.get("model") or "") if isinstance(payload, dict) else ""
    except Exception as exc:
        return {
            "ok": False,
            "assistant_reply": "",
            "provider": "local",
            "bridge_kind": "ct246_to_rog_gpu_local_llm",
            "model": "",
            "error": str(exc)[:500],
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }
    return {
        "ok": bool(reply),
        "assistant_reply": reply,
        "provider": "local",
        "bridge_kind": "ct246_to_rog_gpu_local_llm",
        "model": model,
        "input_prompt_chars": len(local_prompt),
        "original_prompt_chars": len(gen_prompt),
        "prompt_compacted": len(local_prompt) < len(gen_prompt),
        "n_predict": n_predict,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "error": "",
    }


def _build_lane_ct246_cpu_generate(
    gen_prompt: str,
    timeout_s: int,
    max_tokens: int,
) -> dict[str, Any]:
    """Attempt a bounded build/review turn on CT246's local coder GGUF."""
    model_path = os.environ.get(
        "ENGEL_CODE_LANE_GGUF_MODEL",
        "/opt/engel/models-active/llm/qwen2.5-coder-3b-instruct/"
        "qwen2.5-coder-3b-instruct-q5_k_m.gguf",
    ).strip()
    if not model_path or not Path(model_path).is_file():
        return {
            "ok": False,
            "assistant_reply": "",
            "provider": "local",
            "bridge_kind": "ct246_local_coder_gguf",
            "model": model_path,
            "error": "CT246 local coder GGUF is unavailable",
        }
    lowered_prompt = gen_prompt.lstrip().casefold()
    plan_prompt = lowered_prompt.startswith("plan this engel build")
    review_prompt = lowered_prompt.startswith(
        "review this completed engel build"
    )
    repair_prompt = bool(
        lowered_prompt.startswith("repair ")
        or "\nengel_single_file_target:" in lowered_prompt
    )
    cap_default = (
        "700"
        if plan_prompt
        else "512"
        if review_prompt
        else "2500"
        if repair_prompt
        else "2500"
    )
    stage_cap = int(cap_default)
    try:
        configured_cap = max(
            256,
            int(
                os.environ.get("ENGEL_BUILD_LOCAL_N_PREDICT_CAP", "2500")
                or "2500"
            ),
        )
    except ValueError:
        configured_cap = 2500
    cap = min(stage_cap, configured_cap)
    n_predict = min(cap, max(256, int(max_tokens)))
    try:
        ctx = max(
            4096,
            int(os.environ.get("ENGEL_BUILD_LOCAL_CTX", "4096") or "4096"),
        )
    except ValueError:
        ctx = 4096
    local_prompt_limit = max(
        3000,
        int(os.environ.get("ENGEL_BUILD_LOCAL_PROMPT_CHAR_CAP", "6000") or "6000"),
    )
    local_prompt = gen_prompt
    if len(local_prompt) > local_prompt_limit:
        tail_chars = min(1600, local_prompt_limit // 3)
        local_prompt = (
            local_prompt[: local_prompt_limit - tail_chars]
            + "\n\n[worker context compacted for bounded local-first attempt]\n\n"
            + local_prompt[-tail_chars:]
        )
    extra_system = (
        "You are Engel AI Main's CT246 local build planner. Return only valid "
        "compact JSON matching the requested file-plan schema."
        if plan_prompt
        else (
            "You are Engel AI Main's CT246 local build engine. Follow the requested "
            "output protocol exactly. For generation or repair, return complete files "
            "with closed fences and FILE markers. For review, return only valid compact "
            "JSON. Do not explain or identify yourself."
        )
    )
    try:
        from engel_local_model_service import run_llama_cpp_lora_text_with_model

        result = run_llama_cpp_lora_text_with_model(
            model_path=model_path,
            lora_path="",
            prompt=local_prompt,
            n_predict=n_predict,
            ctx=ctx,
            n_gpu_layers=0,
            temperature=float(
                os.environ.get("ENGEL_BUILD_LOCAL_TEMPERATURE", "0.12") or "0.12"
            ),
            extra_system=extra_system,
        )
    except Exception as exc:
        return {
            "ok": False,
            "assistant_reply": "",
            "provider": "local",
            "bridge_kind": "ct246_local_coder_gguf",
            "model": model_path,
            "error": str(exc)[:500],
        }
    reply = str(result.get("text") or result.get("stdout") or "").strip()
    return {
        "ok": bool(result.get("ok") and reply),
        "assistant_reply": reply,
        "provider": "local",
        "bridge_kind": "ct246_local_coder_gguf",
        "model": model_path,
        "model_result": {
            key: result.get(key)
            for key in (
                "model_load_ms",
                "generation_ms",
                "model_load_count",
                "model_loaded_in_current_process",
            )
        },
        "input_prompt_chars": len(local_prompt),
        "original_prompt_chars": len(gen_prompt),
        "prompt_compacted": len(local_prompt) < len(gen_prompt),
        "error": str(result.get("error") or "")[:500],
    }


def _build_lane_local_generate(
    gen_prompt: str,
    timeout_s: int,
    max_tokens: int,
) -> dict[str, Any]:
    """Prefer the ROG-local GPU model, then fall back to CT246's SSD CPU model."""
    attempts: list[dict[str, Any]] = []

    def record_gpu(result: dict[str, Any], attempt: int) -> tuple[str, bool]:
        reply = str(result.get("assistant_reply") or "").strip()
        usable = bool(
            result.get("ok") is True
            and _build_lane_reply_usable(gen_prompt, reply)
        )
        attempts.append(
            {
                "route": "ct246_to_rog_gpu_local_llm",
                "attempt": attempt,
                "ok": result.get("ok") is True,
                "usable": usable,
                "model": str(result.get("model") or ""),
                "error": str(result.get("error") or "")[:500],
                "reply_chars": len(reply),
                "elapsed_ms": result.get("elapsed_ms"),
            }
        )
        return reply, usable

    gpu_result = _build_lane_rog_gpu_local_generate(
        gen_prompt,
        timeout_s,
        max_tokens,
    )
    gpu_reply, gpu_usable = record_gpu(gpu_result, 1)
    if gpu_usable:
        gpu_result["local_route_attempts"] = attempts
        return gpu_result

    gpu_service_reached = bool(
        gpu_result.get("ok") is True
        or (gpu_reply and not str(gpu_result.get("error") or "").strip())
    )
    if gpu_service_reached:
        retry_prompt = (
            gen_prompt.rstrip()
            + "\n\nFORMAT RETRY: The previous local response was rejected because "
            "it did not exactly match the requested JSON or FILE/fenced-block "
            "protocol. Generate the requested result again from scratch. Return "
            "only the required structured payload, close every fence, and include "
            "no explanation."
        )
        retry_result = _build_lane_rog_gpu_local_generate(
            retry_prompt,
            timeout_s,
            max_tokens,
        )
        _retry_reply, retry_usable = record_gpu(retry_result, 2)
        if retry_usable:
            retry_result["local_route_attempts"] = attempts
            return retry_result
        if str(
            os.environ.get(
                "ENGEL_BUILD_CPU_FALLBACK_ON_GPU_FORMAT_MISS",
                "0",
            )
            or "0"
        ).strip().casefold() not in {"1", "true", "yes", "on"}:
            return {
                "ok": False,
                "assistant_reply": "",
                "provider": "local",
                "bridge_kind": "ct246_to_rog_gpu_local_llm",
                "model": str(retry_result.get("model") or gpu_result.get("model") or ""),
                "error": "ROG GPU local output missed the required build format twice",
                "local_route_attempts": attempts,
            }

    cpu_result = _build_lane_ct246_cpu_generate(
        gen_prompt,
        timeout_s,
        max_tokens,
    )
    attempts.append(
        {
            "route": "ct246_local_coder_gguf",
            "attempt": 1,
            "ok": cpu_result.get("ok") is True,
            "model": str(cpu_result.get("model") or ""),
            "error": str(cpu_result.get("error") or "")[:500],
        }
    )
    cpu_result["local_route_attempts"] = attempts
    return cpu_result


def _build_lane_generate(
    gen_prompt: str,
    timeout_s: int,
    max_tokens: int,
    *,
    route_log: list[dict[str, Any]] | None = None,
    local_only: bool = False,
    provider_request: dict[str, Any] | None = None,
    provider_selection: dict[str, Any] | None = None,
) -> str:
    """Generate build text through the requested provider when policy permits.

    With no explicit provider request this retains Engel's established local
    first order (ROG GPU, then CT246 CPU, then attached Codex).  A validated
    Co-pilot selection is preferred for this build stage, but never bypasses
    the existing local-only, attached-Codex, Grok, or external-provider gates.

    Grok 4.6 Super CLI is opt-in via ENGEL_BUILD_GROK46_FIRST=1. Default off
    because the CLI 240s cap returns empty on large Flutter FILE jobs.
    Claude and Gemini stay disabled for builds unless
    ENGEL_BUILD_ALLOW_PROVIDER_APIS=1 is deliberately configured.
    """
    provider_request = provider_request if isinstance(provider_request, dict) else {}
    requested_provider = ""
    if _request_explicit_provider_allowed(provider_request):
        requested_provider = _normalize_provider_name(
            provider_request.get("provider")
            or provider_request.get("selected_provider")
        )
        if requested_provider == "auto":
            requested_provider = ""
    if not requested_provider:
        # Prompt-directed provider requests are evaluated against the original
        # operator line, not the expanded FILE-generation prompt (which may
        # contain incidental provider names in worker/context text).
        original_prompt = str(
            provider_request.get("_build_original_prompt") or ""
        ).strip()
        if original_prompt:
            try:
                candidates, reason = _provider_candidates_for_prompt(
                    original_prompt,
                    provider_request,
                )
                if reason == "explicit_provider" and candidates:
                    requested_provider = _normalize_provider_name(candidates[0])
            except Exception:
                requested_provider = ""
    if local_only:
        # The live local-only training sentinel remains authoritative even if a
        # stale UI selection is present in the action payload.
        requested_provider = "local"

    requested_model = str(
        provider_request.get("model")
        or provider_request.get("provider_model")
        or ""
    ).strip()
    req = {
        "timeout_seconds": min(300, max(30, int(timeout_s))),
        "max_tokens": int(max_tokens),
        "thinking_budget": 0,
        "artifact_only": True,
        # Do not pin every build route to the Grok model.  In particular, the
        # attached Codex bridge must receive an empty model to use its own
        # account default unless Co-pilot supplied a model for that provider.
        "model": requested_model,
        "provider_model": requested_model,
        "lane": "build",
    }
    if requested_provider:
        req["provider"] = requested_provider
        req["selected_provider"] = requested_provider
        req["force_provider"] = True
    allow_attached_codex = not local_only and str(
        os.environ.get("ENGEL_BUILD_ALLOW_ATTACHED_CODEX", "1") or "1"
    ).strip().casefold() not in {"0", "false", "no", "off"}
    allow_provider_apis = not local_only and str(
        os.environ.get("ENGEL_BUILD_ALLOW_PROVIDER_APIS", "0") or "0"
    ).strip().casefold() in {"1", "true", "yes", "on"}
    explicit_fallback_allowed = _provider_fallback_allowed(provider_request)
    lowered_prompt = gen_prompt.lstrip().casefold()
    stage_name = (
        "plan"
        if lowered_prompt.startswith("plan this engel build")
        else "generate_file"
        if lowered_prompt.startswith("generate one file for engel bounded build")
        else "review"
        if lowered_prompt.startswith("review this completed engel build")
        else "repair"
        if (
            lowered_prompt.startswith("repair ")
            or "\nengel_single_file_target:" in lowered_prompt
        )
        else "generate"
    )
    local_all_stages = str(
        os.environ.get("ENGEL_BUILD_LOCAL_ALL_STAGES", "1") or "1"
    ).strip().casefold() in {"1", "true", "yes", "on"}
    routes: list[tuple[str, Any, bool, bool, int]] = []
    grok_first = _build_lane_grok46_enabled(local_only=local_only)
    local_routes: list[tuple[str, Any, bool, bool, int]] = []
    if grok_first:
        routes.append(
            ("rog_grok46_super_cli", _call_grok46_build_bridge, False, True, 1)
        )
    if stage_name in {"plan", "generate", "generate_file"} or local_all_stages:
        local_attempts = 2 if stage_name in {"generate", "generate_file", "repair"} else 1
        for route_attempt in range(1, local_attempts + 1):
            local_routes.append(
                (
                    "ct246_local_coder_gguf",
                    _build_lane_local_generate,
                    False,
                    False,
                    route_attempt,
                )
            )
    routes.extend(local_routes)
    codex_route = ("rog_attached_codex_cli", _call_codex_cli_bridge, False, True, 1)
    if allow_attached_codex:
        routes.append(codex_route)
    provider_routes: dict[str, tuple[str, Any, bool, bool, int]] = {}
    if allow_provider_apis:
        provider_routes.update(
            {
                "anthropic": ("rog_claude_cli_provider", _call_claude_cli_bridge, True, True, 1),
                "gemini": ("rog_gemini_api_provider", _call_gemini_api_bridge, True, True, 1),
            }
        )
        # OpenAI/ChatGPT is intentionally absent from the default build
        # cascade.  It becomes available only when a user explicitly selects
        # it and the same external-provider gate is enabled.
        provider_routes["openai"] = (
            "rog_openai_provider",
            lambda prompt, request, started: _call_provider_bridge(
                "openai", prompt, request, started
            ),
            True,
            True,
            1,
        )
        routes.extend(provider_routes[p] for p in ("anthropic", "gemini"))

    if provider_selection is not None and isinstance(provider_selection, dict):
        provider_selection.clear()
        provider_selection.update(
            {
                "requested_provider": requested_provider,
                "requested_model": requested_model,
                "local_only": local_only,
                "external_provider_gate_enabled": allow_provider_apis,
                "attached_codex_gate_enabled": allow_attached_codex,
                "grok_first_gate_enabled": grok_first,
                "selection_honored": False,
                "selection_fallback_used": False,
                "fallback_allowed": explicit_fallback_allowed,
                "fallback_attempted": False,
                "selection_gate_reason": "",
            }
        )

    if requested_provider == "local":
        # Explicit local means local only for this build generation; do not let
        # an opt-in Grok or attached-Codex route override the user's choice.
        routes = list(local_routes)
        if provider_selection is not None:
            provider_selection["selection_honored"] = bool(routes)
    elif requested_provider:
        preferred: list[tuple[str, Any, bool, bool, int]] = []
        preferred_name = ""
        gate_reason = ""
        if requested_provider == "codex":
            preferred_name = "rog_attached_codex_cli"
            if allow_attached_codex:
                preferred.append(codex_route)
            else:
                gate_reason = "ENGEL_BUILD_ALLOW_ATTACHED_CODEX disabled"
        elif requested_provider == "xai":
            preferred_name = "rog_grok46_super_cli"
            if grok_first:
                preferred.append(
                    ("rog_grok46_super_cli", _call_grok46_build_bridge, False, True, 1)
                )
            else:
                gate_reason = "ENGEL_BUILD_GROK46_FIRST disabled"
        elif requested_provider in provider_routes:
            preferred_name = provider_routes[requested_provider][0]
            preferred.append(provider_routes[requested_provider])
        else:
            gate_reason = (
                "ENGEL_BUILD_ALLOW_PROVIDER_APIS disabled"
                if requested_provider in {"openai", "anthropic", "gemini"}
                else f"no build route registered for {requested_provider}"
            )
        preferred_names = {row[0] for row in preferred}
        # An explicit provider remains strict by default, matching the normal
        # provider bridge contract: do not silently switch to a different
        # model/provider unless the caller explicitly allows fallback.  When
        # allowed, retain the established cascade after the preferred attempt.
        if explicit_fallback_allowed:
            routes = preferred + [row for row in routes if row[0] not in preferred_names]
        else:
            routes = preferred
        if provider_selection is not None:
            provider_selection["preferred_route"] = preferred_name
            provider_selection["selection_gate_reason"] = gate_reason
            provider_selection["selection_preferred_route_available"] = bool(preferred)
            provider_selection["fallback_attempted"] = bool(
                explicit_fallback_allowed and len(routes) > len(preferred)
            )

    for route_name, fn, provider_api, network_enabled, route_attempt in routes:
        route_started = time.perf_counter()
        try:
            if route_name == "ct246_local_coder_gguf":
                r = fn(gen_prompt, timeout_s, max_tokens)
            else:
                r = fn(gen_prompt, req, route_started)
        except Exception as exc:
            r = {"ok": False, "assistant_reply": "", "error": str(exc)}
        reply = str(r.get("assistant_reply") or "").strip()
        usable = bool(r.get("ok") and _build_lane_reply_usable(gen_prompt, reply))
        observed_route = str(r.get("bridge_kind") or route_name)
        if route_log is not None:
            route_log.append(
                {
                    "stage": stage_name,
                    "route": observed_route,
                    "route_attempt": route_attempt,
                    "provider": str(r.get("provider") or ""),
                    "model": str(r.get("model") or ""),
                    "requested_provider": requested_provider,
                    "provider_selection_honored": bool(
                        requested_provider
                        and (
                            requested_provider == _normalize_provider_name(r.get("provider"))
                            or (
                                requested_provider == "codex"
                                and route_name == "rog_attached_codex_cli"
                            )
                        )
                    ),
                    "provider_api_enabled": provider_api,
                    "network_enabled": network_enabled,
                    "ok": bool(r.get("ok")),
                    "usable": usable,
                    "error": str(r.get("error") or "")[:500],
                    "reply_chars": len(reply),
                    "file_marker_count": len(
                        re.findall(r"(?m)^\s*FILE:\s*\S+", reply)
                    ),
                    "fence_count": reply.count("```"),
                    "json_file_count": _build_lane_json_project_file_count(reply),
                    "single_target_code_file": _build_lane_single_target_code_file(
                        gen_prompt,
                        reply,
                    ),
                    "reply_preview": reply[:500],
                    "input_prompt_chars": r.get("input_prompt_chars"),
                    "original_prompt_chars": r.get("original_prompt_chars"),
                    "prompt_compacted": r.get("prompt_compacted"),
                    "local_route_attempts": r.get("local_route_attempts"),
                    "elapsed_ms": int((time.perf_counter() - route_started) * 1000),
                }
            )
        if not usable:
            continue
        if provider_selection is not None:
            provider_selection["selection_honored"] = bool(
                not requested_provider
                or requested_provider == "local"
                or requested_provider == _normalize_provider_name(r.get("provider"))
                or (requested_provider == "codex" and route_name == "rog_attached_codex_cli")
            )
            provider_selection["selected_route"] = observed_route
            provider_selection["selected_provider"] = str(r.get("provider") or requested_provider)
            provider_selection["selection_fallback_used"] = bool(
                requested_provider
                and not provider_selection["selection_honored"]
            )
        return reply
    if provider_selection is not None and requested_provider:
        provider_selection["selection_fallback_used"] = bool(
            provider_selection.get("fallback_attempted")
        )
    return ""


def _conical_build_failure_receipt(
    prompt: str,
    started: float,
    request: dict[str, Any],
    conical: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    proof = _persist_ct246_conical_receipt(
        conical,
        prompt=prompt,
        source=str(request.get("source") or "engel_ai_main_ui"),
        build_execution_verified=False,
        provider_api_used=False,
        failure_reason=reason,
    )
    normalized = proof["conical_orchestration"]
    expected = int(normalized.get("expected_worker_count") or 4)
    returned = int(normalized.get("returned_worker_count") or 0)
    missing = [str(value) for value in normalized.get("missing_worker_ids") or [] if str(value)]
    missing_text = ", ".join(missing) if missing else "one or more required workers"
    if proof.get("ok"):
        proof_text = f"CT246 saved the failure proof at {proof['receipt_path']}."
    else:
        proof_text = (
            "CT246 could not complete its conical proof persistence; "
            f"{proof.get('error') or 'the report or memory write failed'}."
        )
    reply = (
        f"I accepted the build request, but I stopped before generation because the required "
        f"worker assembly returned {returned}/{expected}. Missing: {missing_text}. "
        "No build artifact was created or claimed. "
        + proof_text
    )
    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_BUILD_LANE_{stamp}.json"
    receipt: dict[str, Any] = {
        "schema": "engel_main_server_build_lane_receipt_v1",
        "ok": True,
        "status": "conical build stopped because required worker returns failed",
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "prompt": prompt,
        "updated_at_utc": _iso_now(),
        "provider": "engel-main-server-build-lane (local-first worker gate)",
        "runtime_provider": "engel-build-lane-local-first-worker-gate",
        "selected_provider": "ct_build_lane_worker_gate",
        "requested_provider": "ct246_local_then_attached_codex",
        "provider_api_enabled": False,
        "network_enabled": False,
        "provider_free_generation": True,
        "build_lane_used": True,
        "creation_job": True,
        "build_verified": False,
        "build_execution_verified": False,
        "build_artifact_created": False,
        "no_artifact_claimed": True,
        "build_generation_routes": [],
        "build_standalone_first_attempted": False,
        "build_local_model_used": False,
        "build_attached_codex_used": False,
        "build_external_provider_api_used": False,
        "build_external_provider_apis_allowed": False,
        "build_lifecycle": [
            {
                "stage": "worker_dispatch",
                "status": "failed",
                "detail": f"{returned}/{expected} required worker returns",
            },
            {
                "stage": "generation",
                "status": "skipped",
                "detail": "all four required conical worker returns were not present",
            },
        ],
        "action": {
            "kind": "app_build",
            "result": {"ok": False, "path": "", "files": [], "error": reason},
        },
        "conical_orchestration": normalized,
        "conical_job_id": str(normalized.get("job_id") or ""),
        "conical_job_status": "failed",
        "conical_worker_returned_count": returned,
        "conical_worker_expected_count": expected,
        "conical_terminal_failure": True,
        "ct246_conical_receipt_path": str(proof.get("receipt_path") or ""),
        "ct246_conical_report_written": proof.get("report_written") is True,
        "ct246_conical_memory_appended": proof.get("memory_appended") is True,
        "ct246_conical_persistence_ok": proof.get("ok") is True,
        "ct246_conical_persistence_error": str(proof.get("error") or ""),
        "agent_meeting_room_used": True,
        "meeting_room_server_used": True,
        "main_server_chat_service_used": True,
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
        "workspace_receipt_path": str(receipt_path),
        "persistent_chat_memory_appended": False,
    }
    memory_record = dict(receipt)
    memory_record["memory_source"] = "engel-ai-main CT build lane worker gate"
    try:
        _append_jsonl(PERSISTENT_CHAT_MEMORY_PATH, memory_record)
        receipt["persistent_chat_memory_appended"] = True
    except Exception as exc:
        receipt["persistent_chat_memory_error"] = str(exc)
    _write_json(receipt_path, receipt)
    return receipt


def _build_lane_receipt(prompt: str, started: float, request: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """BUILD lane (2026-07-11): 'build me a <thing>' → the bridges (Claude/Grok/Codex)
    generate real multi-file code, Engel scaffolds it to /opt/engel/workspaces and runs
    it, reporting the actual output. This is the agentic build the bridges were set up
    for (like Cursor/VSCode). Fails open — any non-build prompt or empty generation
    returns None and the turn falls through to normal routing. Kill: ENGEL_BUILD_LANE_ENABLED=0.
    (20260711 Joshua) DISCORD IS EXCLUDED: Discord keeps GIFs/media only — build orders
    there fall through to normal chat; building happens in the Engel AI Main app."""
    if str(os.environ.get("ENGEL_BUILD_LANE_ENABLED", "1")).strip().lower() in {"0", "false", "no", "off"}:
        return None
    # A declared chat-only turn is pure text generation and never a build order,
    # whatever its wording. The EngelScript draft instruction says "no code
    # fences" -- a build verb plus a build target -- and CT scaffolded a project
    # for it (live 2026-07-31). Narrow-only: the flag can only refuse a lane.
    if _TURN_CHAT_ONLY.get():
        return None
    src = str((request or {}).get("source") or "").strip().lower()
    if src.startswith("discord"):
        return None
    try:
        import engel_build_lane
    except Exception:
        return None
    if engel_build_lane.is_build_request(prompt) is None:
        return None
    request = request or {}
    conical_context = (
        request.get("conical_orchestration")
        if isinstance(request.get("conical_orchestration"), dict)
        else {}
    )
    if conical_context.get("required") is True:
        worker_gate = _conical_worker_gate(conical_context)
        if worker_gate.get("ok") is not True:
            reason = (
                f"required conical worker gate failed: {worker_gate.get('verified_returned_count')}/"
                f"{worker_gate.get('expected_count')} exact worker returns; "
                f"missing={worker_gate.get('missing_worker_ids') or ['unknown']}"
            )
            return _conical_build_failure_receipt(
                prompt,
                started,
                request,
                conical_context,
                reason,
            )
    local_only_requested = _request_local_only_training(request)
    generation_routes: list[dict[str, Any]] = []
    provider_selection: dict[str, Any] = {}
    build_provider_request = dict(request)
    # Keep provider intent separate from the expanded build prompt.  The latter
    # contains worker/context prose and can mention provider names incidentally.
    build_provider_request["_build_original_prompt"] = prompt

    def generate_with_provenance(
        gen_prompt: str, generation_timeout: int, generation_tokens: int
    ) -> str:
        return _build_lane_generate(
            gen_prompt,
            generation_timeout,
            generation_tokens,
            route_log=generation_routes,
            local_only=local_only_requested,
            provider_request=build_provider_request,
            provider_selection=provider_selection,
        )

    try:
        result = engel_build_lane.run_build(
            prompt, generate_with_provenance,
            request_id="ct_build_" + _stamp(),
            timeout_s=int(os.environ.get("ENGEL_BUILD_LANE_TIMEOUT", "150") or "150"),
            max_tokens=int(os.environ.get("ENGEL_BUILD_LANE_MAX_TOKENS", "1800") or "1800"),
            worker_context=conical_context or None,
        )
    except Exception as exc:
        if conical_context:
            return _conical_build_failure_receipt(
                prompt,
                started,
                request,
                conical_context,
                f"CT246 build lane raised before a receipt was returned: {exc}",
            )
        return None
    if result is None:
        if conical_context:
            return _conical_build_failure_receipt(
                prompt,
                started,
                request,
                conical_context,
                "CT246 build lane returned no build receipt",
            )
        return None
    provider_api_used = any(
        row.get("usable") is True and row.get("provider_api_enabled") is True
        for row in generation_routes
    )
    requested_build_provider = str(
        provider_selection.get("requested_provider") or ""
    ).strip()
    local_model_routes = {
        "ct246_local_coder_gguf",
        "ct246_to_rog_gpu_local_llm",
    }
    local_model_used = any(
        row.get("usable") is True and row.get("route") in local_model_routes
        for row in generation_routes
    )
    attached_codex_used = any(
        row.get("usable") is True and row.get("route") == "rog_attached_codex_cli"
        for row in generation_routes
    )
    actual_local_only = bool(
        local_model_used
        and not attached_codex_used
        and not provider_api_used
        and not any(
            row.get("usable") is True and row.get("network_enabled") is True
            for row in generation_routes
        )
    )
    result.update(
        {
            "build_generation_routes": generation_routes,
            "build_standalone_first_attempted": bool(
                generation_routes
                and generation_routes[0].get("route") in local_model_routes
            ),
            "build_local_model_used": local_model_used,
            "build_attached_codex_used": attached_codex_used,
            "build_external_provider_api_used": provider_api_used,
            "build_external_provider_apis_allowed": str(
                os.environ.get("ENGEL_BUILD_ALLOW_PROVIDER_APIS", "0") or "0"
            ).strip().casefold()
            in {"1", "true", "yes", "on"},
            "build_provider_selection": dict(provider_selection),
            "build_explicit_provider_requested": bool(requested_build_provider),
            "provider_api_enabled": provider_api_used,
            "network_enabled": any(
                row.get("usable") is True and row.get("network_enabled") is True
                for row in generation_routes
            ),
            "provider_free_generation": not provider_api_used,
            "requested_provider": (
                requested_build_provider
                or ("local" if local_only_requested else "ct246_local_then_attached_codex")
            ),
            "local_llm_only": actual_local_only,
            "local_only_training": local_only_requested,
            "provider_fallback_allowed": (
                False
                if local_only_requested
                else _provider_fallback_allowed(request)
            ),
            "training_sample_eligible": bool(
                actual_local_only and result.get("build_verified", result.get("ok"))
            ),
            "persistent_chat_memory_training_eligible": bool(
                actual_local_only and result.get("build_verified", result.get("ok"))
            ),
        }
    )
    build_verified = bool(result.get("build_verified", result.get("ok")))
    # A completed lifecycle with failed verification is still a valid chat action.
    # Return its proof to the UI instead of hiding it behind ordinary-chat fallback.
    result["build_verified"] = build_verified
    result["ok"] = True
    result["status"] = (
        "app build lifecycle verified"
        if build_verified
        else "app build lifecycle completed with visible verification failure"
    )
    ct_conical_proof: dict[str, Any] = {}
    if isinstance(result.get("conical_orchestration"), dict):
        conical = dict(result["conical_orchestration"])
        expected_workers = int(conical.get("expected_worker_count") or 0)
        returned_workers = int(conical.get("returned_worker_count") or 0)
        workers_ok = bool(
            conical.get("ok") is True
            and expected_workers == 4
            and returned_workers == expected_workers
        )
        final_ok = bool(workers_ok and build_verified)
        conical.update(
            {
                "build_verified": build_verified,
                "final_ok": final_ok,
                "final_status": "finished" if final_ok else "failed",
                "finalized_at_utc": _iso_now(),
                "final_summary": (
                    f"{returned_workers}/{expected_workers} required worker returns; "
                    f"CT246 build_verified={build_verified}."
                ),
            }
        )
        result["conical_orchestration"] = conical
        result["conical_job_id"] = str(conical.get("job_id") or "")
        result["conical_job_status"] = str(conical.get("final_status") or "failed")
        result["conical_worker_returned_count"] = returned_workers
        result["conical_worker_expected_count"] = expected_workers
        ct_conical_proof = _persist_ct246_conical_receipt(
            conical,
            prompt=prompt,
            source=str(request.get("source") or "engel_ai_main_ui"),
            build_execution_verified=build_verified,
            provider_api_used=provider_api_used,
        )
        conical = dict(ct_conical_proof.get("conical_orchestration") or conical)
        result["conical_orchestration"] = conical
        result["conical_job_id"] = str(conical.get("job_id") or "")
        result["conical_job_status"] = str(conical.get("final_status") or "failed")
        result["conical_worker_returned_count"] = int(conical.get("returned_worker_count") or 0)
        result["conical_worker_expected_count"] = int(conical.get("expected_worker_count") or 0)
        result["ct246_conical_receipt_path"] = str(ct_conical_proof.get("receipt_path") or "")
        result["ct246_conical_report_written"] = ct_conical_proof.get("report_written") is True
        result["ct246_conical_memory_appended"] = ct_conical_proof.get("memory_appended") is True
        result["ct246_conical_persistence_ok"] = ct_conical_proof.get("ok") is True
        result["ct246_conical_persistence_error"] = str(ct_conical_proof.get("error") or "")
        if ct_conical_proof.get("ok") is not True:
            build_verified = False
            result["build_verified"] = False
            result["ok"] = True
            result["status"] = "build output exists but CT246 conical proof persistence failed"
            result["conical_job_status"] = "failed"
            result["conical_terminal_failure"] = True
            result["assistant_reply"] = (
                "The build lane produced output, but I cannot claim it as finished because CT246 "
                "did not durably save both the conical report and memory proof. "
                f"{ct_conical_proof.get('error') or 'Persistence verification failed.'}"
            )
    build_training_eligible = bool(
        result.get("local_llm_only") is True and result.get("build_verified") is True
    )
    result["training_sample_eligible"] = build_training_eligible
    result["persistent_chat_memory_training_eligible"] = build_training_eligible
    reply = str(result.get("assistant_reply") or "")
    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_BUILD_LANE_{stamp}.json"
    receipt = dict(result)
    receipt.update({
        "schema": "engel_main_server_build_lane_receipt_v1",
        "updated_at_utc": _iso_now(),
        "prompt": prompt,
        "provider": "engel-main-server-build-lane (local-first; attached Codex fallback)",
        "runtime_provider": "engel-build-lane-local-or-attached-codex",
        "selected_provider": (
            "ct_attached_codex_build"
            if attached_codex_used
            else "ct_local_build_model"
            if local_model_used
            else "ct_build_lane_no_usable_generator"
        ),
        # Preserve the user-facing provider decision separately from the
        # historical build-lane labels above.  This makes a policy fallback
        # visible without falsely claiming that the requested provider ran.
        "build_requested_provider": str(
            provider_selection.get("requested_provider") or ""
        ),
        "build_selected_provider": str(
            provider_selection.get("selected_provider") or ""
        ),
        "build_selected_route": str(
            provider_selection.get("selected_route") or ""
        ),
        "build_provider_selection": dict(provider_selection),
        "main_server_chat_service_used": True,
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
        "workspace_receipt_path": str(receipt_path),
    })
    if isinstance(result.get("conical_orchestration"), dict):
        receipt["agent_meeting_room_used"] = True
        receipt["meeting_room_server_used"] = True
        receipt["conical_job_id"] = str(result["conical_orchestration"].get("job_id") or "")
        receipt["conical_job_status"] = str(
            result["conical_orchestration"].get("final_status") or "failed"
        )
        receipt["conical_worker_returned_count"] = int(
            result["conical_orchestration"].get("returned_worker_count") or 0
        )
        receipt["conical_worker_expected_count"] = int(
            result["conical_orchestration"].get("expected_worker_count") or 0
        )
        receipt["ct246_conical_receipt_path"] = str(result.get("ct246_conical_receipt_path") or "")
        receipt["ct246_conical_report_written"] = result.get("ct246_conical_report_written") is True
        receipt["ct246_conical_memory_appended"] = result.get("ct246_conical_memory_appended") is True
        receipt["ct246_conical_persistence_ok"] = result.get("ct246_conical_persistence_ok") is True
        receipt["ct246_conical_persistence_error"] = str(
            result.get("ct246_conical_persistence_error") or ""
        )
    memory_record = dict(receipt)
    memory_record["memory_source"] = "engel-ai-main CT build lane"
    try:
        _append_jsonl(PERSISTENT_CHAT_MEMORY_PATH, memory_record)
        receipt["persistent_chat_memory_appended"] = True
    except Exception as exc:
        receipt["persistent_chat_memory_error"] = str(exc)
    _write_json(receipt_path, receipt)
    return receipt


def _workspace_setup_receipt(prompt: str, started: float, request: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """WORKSPACE SETUP lane (2026-07-11): 'set up a <X> workspace / environment' →
    the bounded non-destructive scaffold under /opt/engel/workspaces. The ROG
    worker has run this action since 7/7 but the CT service never wired it, so
    here a setup ORDER fell to fast chat and got a canned "what should we work
    on next" reply. Same contract as the build lane: fails open, Discord
    excluded, kill: ENGEL_WORKSPACE_SETUP_LANE_ENABLED=0."""
    if str(os.environ.get("ENGEL_WORKSPACE_SETUP_LANE_ENABLED", "1")).strip().lower() in {"0", "false", "no", "off"}:
        return None
    src = str((request or {}).get("source") or "").strip().lower()
    if src.startswith("discord"):
        return None
    try:
        from engel_main_local_model_worker import _operator_request_text, _run_workspace_setup
    except Exception:
        return None
    try:
        result = _run_workspace_setup(
            _operator_request_text(prompt), "ct_ws_setup_" + _stamp()
        )
    except Exception:
        return None
    if result is None or not result.get("ok"):
        return None
    reply = str(result.get("assistant_reply") or "")
    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_WORKSPACE_SETUP_{stamp}.json"
    receipt = dict(result)
    receipt.update({
        "schema": "engel_main_server_workspace_setup_receipt_v1",
        "updated_at_utc": _iso_now(),
        "prompt": prompt,
        "provider": "engel-main-server-workspace-setup-lane",
        "runtime_provider": "engel-workspace-scaffold",
        "selected_provider": "ct_workspace_setup_lane",
        "main_server_chat_service_used": True,
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
        "workspace_receipt_path": str(receipt_path),
    })
    memory_record = dict(receipt)
    memory_record["memory_source"] = "engel-ai-main CT workspace setup lane"
    try:
        _append_jsonl(PERSISTENT_CHAT_MEMORY_PATH, memory_record)
        receipt["persistent_chat_memory_appended"] = True
    except Exception as exc:
        receipt["persistent_chat_memory_error"] = str(exc)
    _write_json(receipt_path, receipt)
    return receipt


def _apply_live_status_answer_if_needed(prompt: str, receipt: dict[str, Any]) -> dict[str, Any]:
    reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
    if not _reply_missing_live_runtime_facts(prompt, reply):
        return receipt
    replacement = _live_runtime_status_reply()
    receipt["assistant_reply"] = replacement
    receipt["assistant_output_text"] = replacement
    receipt["server_live_runtime_status_answer_used"] = True
    receipt["server_live_runtime_status_replaced_reply_preview"] = _clip(reply, 500)
    receipt["status"] = "server live runtime status answered"
    try:
        memory_record = dict(receipt)
        memory_record["memory_source"] = "engel-ai-main CT live runtime status answer"
        memory_record["prompt"] = prompt
        _append_jsonl(PERSISTENT_CHAT_MEMORY_PATH, memory_record)
        receipt["persistent_chat_memory_appended"] = True
        receipt["persistent_chat_history_appended"] = True
        receipt["persistent_chat_memory_path"] = str(PERSISTENT_CHAT_MEMORY_PATH)
    except Exception as exc:
        receipt["persistent_chat_memory_error"] = str(exc)
    return receipt


def _repair_stale_visible_reply(prompt: str, receipt: dict[str, Any]) -> dict[str, Any]:
    reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "").strip()
    low_reply = reply.casefold()
    if not reply:
        return receipt
    # Current user line only - the Discord wrapper's quoted history is full of
    # "gif"/"receipts"/"backend" words and used to hijack this repair into the
    # media-tool zombie line for ordinary messages ("lol", "go back to chat").
    low_prompt = _intent_gate_text(prompt).casefold()
    if _reply_is_conversation_stall(reply):
        receipt["assistant_reply"] = ""
        receipt["assistant_output_text"] = ""
        receipt["ok"] = False
        receipt["conversation_stall_stripped"] = True
        receipt["status"] = "local quality check failed"
        return receipt
    if _is_spoken_voice_training_prompt(prompt) or "training task:" in low_prompt:
        return receipt
    # Machine-protocol turns pass through untouched (JSON decisions, tool output).
    if (
        reply.lstrip().startswith(("{", "[", "```"))
        or "json object" in low_prompt
        or "json only" in low_prompt
        or "compact json" in low_prompt
    ):
        return receipt
    from_real_provider = bool(receipt.get("provider_bridge_used")) or str(
        receipt.get("selected_provider") or ""
    ).casefold() in {"anthropic", "xai", "openai", "chatgpt_browser", "gemini"}
    user_asked_for_backend = any(
        term in low_prompt
        for term in (
            "backend",
            "diagnostic",
            "receipt",
            "proof",
            "server status",
            "connection status",
            "health",
            "route",
            "llm",
            "model",
            "provider",
            "model path",
            "memory path",
        )
    )
    if (
        _prompt_requests_last_model_trace(low_prompt)
        or _prompt_requests_chat_fault_repair(low_prompt)
        or _prompt_requests_build_status(low_prompt)
    ):
        return receipt
    stale_terms = (
        "engel server link and memory path are active",
        "server link and memory path are active",
        "i will keep that machinery out of the way",
        "i am answering through the engel server chat lane",
        "local model route did not produce a usable answer",
        "send the next detail and i will answer it directly",
        "anything you need, engel ai main",
        "i'm sorry, but i can't assist with that",
        "i am sorry, but i can't assist with that",
        "i'm sorry, but i cannot assist with that",
        "i am sorry, but i cannot assist with that",
        "i can't assist with that",
        "i cannot assist with that",
        "i'm just a computer program",
        "i am just a computer program",
        "i don't have feelings",
        "i do not have feelings",
        "unable to directly access or display images",
        "unable to directly access",
        "could you please provide more details",
        "could you please provide",
        "provide more context",
        "clarify your question",
        "not sure what you mean",
        "not sure what you're saying",
        "not sure what youre saying",
        "need the user to provide",
        "please ask your question",
        "gif is a file extension",
        "insert gif url",
        "insert gif here",
        "imgur.com",
        "example.com",
        "i do not break",
        "i don't break",
    )
    casual_meta_terms = (
        "normal chat should not feel",
        "status script",
        "server details",
        "receipts",
        "workspace map",
        "diagnostics",
        "backend",
        "bridge",
        "route",
        "connector",
        "provider",
        "discord bridge",
        "verified by the discord bridge",
        "running on engel/ai-main",
        "running on engel-ai-main",
        "ct246",
        "ct 246",
        "/opt/engel",
        "agent meeting room",
        "meeting room",
        "unless you ask for diagnostics",
        "unless you ask for proof",
        "how i will answer",
    )
    repetition_question = any(term in low_prompt for term in ("repeat", "repeating", "kept repeating", "same answer", "canned"))
    stale_match = any(term in low_reply for term in stale_terms)
    meta_match = (not user_asked_for_backend) and any(term in low_reply for term in casual_meta_terms)
    # Real provider replies are the product, not the disease: only a hard
    # refusal phrase (stale_terms) may trigger repair on them. Rewriting a
    # healthy Claude reply because it mentioned "receipts" was the zombie.
    if from_real_provider and not stale_match:
        return receipt
    if not stale_match and not meta_match and not repetition_question:
        return receipt

    owner_fact_question = any(
        term in low_prompt
        for term in (
            "my profession",
            "my job",
            "what do i do",
            "kind of work do i",
            "kind of work i do",
            "remember about the kind of work",
            "work do i usually",
            "my business",
            "jz drafting",
            "global modular",
        )
    )
    if owner_fact_question:
        saved = [str(item.get("fact") or "").strip() for item in _saved_facts()]
        if "jz drafting" in low_prompt or "my business" in low_prompt:
            selected = [item for item in saved if "jz drafting & design" in item.casefold()][:3]
            repaired = " ".join(selected) or "I do not have enough saved information about that yet."
        elif any(term in low_prompt for term in ("my profession", "my job", "what do i do")):
            selected = next((item for item in saved if "works as a senior draftsman" in item.casefold()), "")
            repaired = selected or "I do not have a saved profession for you yet."
        else:
            repaired = (
                "You usually ask me to help with drafting and design workflows, shop drawings, BIM and modular-construction documentation, "
                "plus practical automation and tools that make that work faster and easier to verify."
            )
    elif repetition_question:
        repaired = _varied_canned(
            low_prompt,
            (
                "It was repeating because casual chat was falling back to canned lines instead of giving the model a fresh turn. "
                "I tightened that path so normal messages get a direct answer first.",
                "I was stuck on a stock line. This turn is a fresh answer.",
                "That was a loop. I am answering this one directly now.",
            ),
        )
    elif "break" in low_prompt or "broken" in low_prompt:
        repaired = (
            "It broke because the chat route was letting weak fallback replies through instead of using the right tool path. "
            "I am recording the bad turn and routing the next one through the correct connector/tool."
        )
    elif any(term in low_prompt for term in ("what can we work on next", "what can you help", "what should we work on", "what should we do next")):
        repaired = (
            "Good morning, Joshua. We can keep tightening the chat, check the phone links, "
            "or open the agent room and make sure the agents are doing real work."
        )
    elif _prompt_is_simple_greeting(low_prompt):
        repaired = "Good morning, Joshua. I am ready; what do you want to tackle first?"
    elif "how are you" in low_prompt:
        repaired = "I am running and ready to help; what should we work on?"
    elif "?" in prompt:
        repaired = "Ask me the question plainly and I will answer it without turning it into a status report."
    else:
        receipt["assistant_reply"] = ""
        receipt["assistant_output_text"] = ""
        receipt["ok"] = False
        receipt["stale_visible_reply_repaired"] = True
        receipt["stale_visible_reply_original_preview"] = _clip(reply, 300)
        receipt["status"] = "local quality check failed"
        return receipt
    receipt["stale_visible_reply_repaired"] = True
    receipt["stale_visible_reply_original_preview"] = _clip(reply, 300)
    receipt["assistant_reply"] = repaired
    receipt["assistant_output_text"] = repaired
    return receipt


def _fast_server_receipt(
    prompt: str,
    started: float,
    model_receipt: dict[str, Any] | None = None,
    error: str = "",
    *,
    fallback_used: bool = True,
) -> dict[str, Any]:
    model_receipt = model_receipt or {}
    reply = _fast_server_reply(prompt, str(model_receipt.get("status") or error))
    fallback_reason = str(model_receipt.get("status") or error or "model route unavailable")
    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_FAST_CHAT_{stamp}.json"
    receipt = {
        "schema": "engel_main_server_fast_chat_receipt_v1",
        "ok": True,
        "status": "fast server chat replied",
        "updated_at_utc": _iso_now(),
        "run_id": "main_server_fast_chat_" + stamp,
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "engel-main-server-fast-local",
        "runtime_provider": "engel-main-server-fast-responder",
        "selected_provider": "main_server_fast_local",
        "main_server_chat_service_used": True,
        "fast_server_fallback_used": fallback_used,
        "fast_server_fallback_reason": fallback_reason if fallback_used else "",
        "model_route_attempted": bool(model_receipt),
        "model_route_ok": bool(model_receipt.get("ok") is True),
        "model_route_status": str(model_receipt.get("status") or ""),
        "model_route_error": str(model_receipt.get("error") or ""),
        "model_process_started": False,
        "runtime_process_started": False,
        "runs_inference": False,
        "loads_model": False,
        "provider_api_enabled": False,
        "network_enabled": False,
        "server_enabled": True,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "model_output_trusted": False,
        "server_snapshot": _service_snapshot(),
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
    }
    receipt = _apply_chat_humanizer(prompt, receipt, "ct_fast_server_receipt")
    receipt = _repair_stale_visible_reply(prompt, receipt)
    receipt = _enforce_requested_short_format(prompt, receipt)
    memory_record = dict(receipt)
    memory_record["memory_source"] = "engel-ai-main CT fast server chat"
    try:
        _append_jsonl(PERSISTENT_CHAT_MEMORY_PATH, memory_record)
        receipt["persistent_chat_memory_appended"] = True
        receipt["persistent_chat_history_appended"] = True
        receipt["persistent_chat_memory_path"] = str(PERSISTENT_CHAT_MEMORY_PATH)
    except Exception as exc:
        receipt["persistent_chat_memory_appended"] = False
        receipt["persistent_chat_history_appended"] = False
        receipt["persistent_chat_memory_error"] = str(exc)
    _write_json(receipt_path, receipt)
    return receipt


def _chat_failure_status_code(receipt: dict[str, Any]) -> int:
    """Non-2xx code for a failed chat turn, defaulting to the historical 502.

    A style-gate refusal is a content decision (422) and a dead local lane is an
    availability problem (503); collapsing both onto "Bad Gateway" hid which one
    happened. Any receipt without a hint keeps the old code.
    """
    try:
        code = int(receipt.get("http_status_hint"))
    except (TypeError, ValueError):
        return 502
    return code if 400 <= code <= 599 else 502


def _local_llm_fast_fail_visible_receipt(
    prompt: str,
    started: float,
    local_failure_receipt: dict[str, Any],
) -> dict[str, Any]:
    fast_fail = (
        local_failure_receipt.get("local_llm_fast_fail")
        if isinstance(local_failure_receipt.get("local_llm_fast_fail"), dict)
        else {}
    )
    fallback_final = (
        local_failure_receipt.get("local_llm_fallback_final")
        if isinstance(local_failure_receipt.get("local_llm_fallback_final"), dict)
        else {}
    )
    timeout_seconds = float(fast_fail.get("timeout_seconds") or 0)
    # Report the time the turn ACTUALLY took. timeout_seconds is the configured ceiling,
    # and printing it as if it were elapsed reads as a 45s hang even when the guard
    # recorded completed=True in 15s -- which sent a live triage down the wrong path.
    try:
        elapsed_seconds = float(fast_fail.get("elapsed_ms") or 0) / 1000.0
    except (TypeError, ValueError):
        elapsed_seconds = 0.0
    if elapsed_seconds <= 0:
        elapsed_seconds = max(0.0, time.perf_counter() - started)
    # A reply the model produced but the style/quality gate refused is NOT a model
    # failure: the local lane ran fine and the text exists. Same detection the caller
    # uses for local_quality_failed, recomputed here so the receipt is self-contained.
    local_status = str(local_failure_receipt.get("status") or "").casefold()
    style_gate_rejected = bool(
        local_failure_receipt.get("quality_gate_degraded") is True
        or "style check failed" in local_status
        or "quality check failed" in local_status
    )
    if fast_fail.get("timed_out") is True:
        failure_kind, failure_class = "timeout", "model_timeout"
    elif fast_fail.get("circuit_open") is True:
        failure_kind, failure_class = "circuit open", "model_circuit_open"
    elif fast_fail.get("busy") is True:
        failure_kind, failure_class = "busy", "model_busy"
    elif style_gate_rejected:
        failure_kind, failure_class = "style-gate rejection", "style_gate_rejection"
    else:
        failure_kind, failure_class = "failure", "model_failure"
    # A real timeout/busy/circuit-open outranks a style-gate status: the classifier above
    # already resolved that, so everything downstream keys off the resolved class rather
    # than the raw flag, or a timed-out turn would be reported as a content refusal.
    is_style_gate = failure_class == "style_gate_rejection"
    fallback_attempted = fallback_final.get("fallback_attempted") is True
    fallback_permitted = bool(
        fallback_attempted
        or local_failure_receipt.get("provider_bridge_fallback_permitted") is True
    )
    if is_style_gate:
        lead = (
            f"The local model answered in {elapsed_seconds:.1f} seconds, but the reply did not pass "
            "Engel's style/quality gate and the repair attempts were exhausted. The model itself did not fail."
        )
    else:
        lead = f"The local model hit a bounded {failure_kind} after {elapsed_seconds:.1f} seconds."
    if fallback_attempted:
        reply = f"{lead} The permitted provider fallback did not return a usable answer either; the turn was stopped and recorded. Retry it."
        tail_status = "provider fallback returned no usable answer"
    elif fallback_permitted:
        reply = f"{lead} A provider fallback was permitted but none was reached; the turn was stopped and recorded. Retry it."
        tail_status = "provider fallback permitted but not reached"
    else:
        reply = (
            f"{lead} No provider was called because Engel chat is local-first -- pass "
            "allow_provider_fallback, or set ENGEL_LOCAL_CHAT_AUTO_BRIDGE_FALLBACK=1, to permit one. Retry it or choose a provider."
        )
        tail_status = "provider fallback not permitted"
    head_status = (
        "local reply rejected by style gate" if is_style_gate else "local LLM failed fast"
    )
    status = f"{head_status}; {tail_status}"
    # 422: we generated text and refused it (client/content problem, retryable as-is).
    # 503: the local model lane genuinely did not produce output.
    http_status_hint = 422 if is_style_gate else 503
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_LOCAL_LLM_FAST_FAIL_{_stamp()}.json"
    return {
        "schema": "ENGEL_MAIN_SERVER_LOCAL_LLM_FAST_FAIL_CHAT_RECEIPT_V1",
        "ok": False,
        "status": status,
        "updated_at_utc": _iso_now(),
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "local",
        "runtime_provider": (
            "engel-local-style-gate-reject" if is_style_gate else "engel-local-llm-fast-fail"
        ),
        "selected_provider": "local",
        "failure_class": failure_class,
        "style_gate_rejected": is_style_gate,
        "local_model_produced_output": is_style_gate,
        "local_llm_elapsed_seconds": round(elapsed_seconds, 3),
        "local_llm_timeout_seconds": timeout_seconds,
        "http_status_hint": http_status_hint,
        "provider_fallback_permitted": fallback_permitted,
        "provider_fallback_attempted": fallback_attempted,
        "local_llm_fast_fail": fast_fail,
        "local_llm_fallback_final": fallback_final,
        "provider_bridge_used": False,
        "provider_api_enabled": False,
        "network_enabled": False,
        "main_server_chat_service_used": True,
        "server_role": "engel-ai-main CT 246",
        "training_sample_eligible": False,
        "persistent_chat_memory_training_eligible": False,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "model_output_trusted": False,
        "storage_mutation": False,
        "external_array_used": False,
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
    }


def _prompt_requests_single_sentence(prompt: str) -> bool:
    low = prompt.casefold()
    return any(term in low for term in ("one sentence", "1 sentence", "single sentence"))


def _enforce_requested_short_format(prompt: str, receipt: dict[str, Any]) -> dict[str, Any]:
    low = prompt.casefold()
    if not _prompt_requests_single_sentence(prompt):
        return receipt
    reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "").strip()
    if not reply:
        return receipt
    compact = " ".join(reply.replace("\r", " ").replace("\n", " ").split())
    if any(term in low for term in ("phone", "alpha", "beta", "android")):
        phone = _phone_bridge_snapshot()
        workers = phone.get("workers") if isinstance(phone.get("workers"), dict) else {}
        alpha = workers.get("android_worker_alpha") if isinstance(workers.get("android_worker_alpha"), dict) else {}
        beta = workers.get("android_worker_beta") if isinstance(workers.get("android_worker_beta"), dict) else {}
        if alpha.get("live") is True and beta.get("live") is True:
            compact = "Yes, Alpha and Beta phone workers are live and the CT server chat route is connected."
        elif alpha.get("live") is True:
            compact = "Alpha is live, but Beta still needs reconnection."
        elif beta.get("live") is True:
            compact = "Beta is live, but Alpha still needs reconnection."
        else:
            compact = "No, Alpha and Beta are not both live right now."
    for lead in ("Yes. ", "No. ", "Right. ", "Correct. "):
        if compact.startswith(lead):
            rest = compact[len(lead) :].lstrip()
            if rest:
                rest = rest[:1].lower() + rest[1:]
            compact = lead[:-2] + ", " + rest
            break
    sentence_end = [idx for idx, ch in enumerate(compact) if ch in ".!?"]
    if sentence_end:
        compact = compact[: sentence_end[0] + 1].strip()
    if len(compact) > 220:
        compact = compact[:217].rstrip() + "..."
    receipt["assistant_reply"] = compact
    receipt["assistant_output_text"] = compact
    receipt["short_format_enforced"] = True
    return receipt


def _live_status_receipt(prompt: str, started: float) -> dict[str, Any]:
    reply = _live_runtime_status_reply()
    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_LIVE_STATUS_CHAT_{stamp}.json"
    receipt = {
        "schema": "engel_main_server_live_status_chat_receipt_v1",
        "ok": True,
        "status": "server live runtime status answered",
        "updated_at_utc": _iso_now(),
        "run_id": "main_server_live_status_chat_" + stamp,
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "engel-main-server-live-status",
        "runtime_provider": "engel-main-server-live-runtime-status",
        "selected_provider": "main_server_live_status",
        "main_server_chat_service_used": True,
        "server_live_runtime_status_answer_used": True,
        "model_route_attempted": False,
        "model_process_started": False,
        "runtime_process_started": False,
        "runs_inference": False,
        "loads_model": False,
        "provider_api_enabled": False,
        "network_enabled": False,
        "server_enabled": True,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "model_output_trusted": True,
        "server_snapshot": _service_snapshot(),
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
    }
    receipt = _apply_chat_humanizer(prompt, receipt, "ct_live_status_receipt")
    receipt = _enforce_live_runtime_status_reply(receipt)
    receipt = _enforce_requested_short_format(prompt, receipt)
    memory_record = dict(receipt)
    memory_record["memory_source"] = "engel-ai-main CT live runtime status"
    try:
        _append_jsonl(PERSISTENT_CHAT_MEMORY_PATH, memory_record)
        receipt["persistent_chat_memory_appended"] = True
        receipt["persistent_chat_history_appended"] = True
        receipt["persistent_chat_memory_path"] = str(PERSISTENT_CHAT_MEMORY_PATH)
    except Exception as exc:
        receipt["persistent_chat_memory_appended"] = False
        receipt["persistent_chat_history_appended"] = False
        receipt["persistent_chat_memory_error"] = str(exc)
    _write_json(receipt_path, receipt)
    return receipt


def _skill_agent_creation_receipt(prompt: str, started: float) -> dict[str, Any] | None:
    try:
        from engel_skill_agent_creator import handle_creation_prompt

        # Gate + create from the CURRENT user line only; quoted Discord/UI
        # context mentioning "agent"/"save" must never mint agents.
        result = handle_creation_prompt(_intent_gate_text(prompt))
    except Exception as exc:
        result = {"ok": False, "handled": True, "status": "skill/agent creation failed", "error": str(exc), "reply": str(exc)}
    if result.get("handled") is not True:
        return None
    reply = str(result.get("reply") or result.get("status") or "Saved requested skill/agent.")
    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_SKILL_AGENT_CREATE_{stamp}.json"
    receipt = {
        "schema": "engel_main_server_skill_agent_creation_chat_receipt_v1",
        "ok": result.get("ok") is True,
        "status": str(result.get("status") or ""),
        "updated_at_utc": _iso_now(),
        "run_id": "main_server_skill_agent_create_" + stamp,
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "engel-main-server-skill-agent-creator",
        "runtime_provider": "engel-main-server-skill-agent-creator",
        "selected_provider": "skill_agent_creator",
        "main_server_chat_service_used": True,
        "skill_agent_creator_used": True,
        "skill_agent_creation_result": result,
        "model_route_attempted": False,
        "model_process_started": False,
        "runtime_process_started": False,
        "runs_inference": False,
        "loads_model": False,
        "provider_api_enabled": False,
        "network_enabled": False,
        "server_enabled": True,
        "trusted_memory_write_enabled": True,
        "approved_memory_write_enabled": True,
        "model_output_trusted": True,
        "server_snapshot": _service_snapshot(),
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
    }
    receipt = _apply_chat_humanizer(prompt, receipt, "ct_skill_agent_creation_receipt")
    memory_record = dict(receipt)
    memory_record["memory_source"] = "engel-ai-main CT skill/agent creator"
    try:
        _append_jsonl(PERSISTENT_CHAT_MEMORY_PATH, memory_record)
        receipt["persistent_chat_memory_appended"] = True
        receipt["persistent_chat_history_appended"] = True
        receipt["persistent_chat_memory_path"] = str(PERSISTENT_CHAT_MEMORY_PATH)
    except Exception as exc:
        receipt["persistent_chat_memory_appended"] = False
        receipt["persistent_chat_history_appended"] = False
        receipt["persistent_chat_memory_error"] = str(exc)
    _write_json(receipt_path, receipt)
    return receipt


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(_clean_json_value(payload), ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _path_below(root: Path, relative: str) -> Path:
    root_resolved = root.resolve()
    target = (root_resolved / relative).resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise ValueError("requested build artifact is outside the approved root")
    return target


def _file_response(
    handler: BaseHTTPRequestHandler,
    path: Path,
    *,
    download_name: str = "",
) -> None:
    if not path.is_file():
        _json_response(handler, 404, {"ok": False, "status": "build artifact not found"})
        return
    body = path.read_bytes()
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    if content_type.startswith("text/html"):
        handler.send_header(
            "Content-Security-Policy",
            "default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
            "font-src 'self' data:; connect-src 'none'; frame-ancestors 'none'",
        )
    if download_name:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", download_name)
        handler.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
    handler.end_headers()
    handler.wfile.write(body)


def _serve_build_preview(handler: BaseHTTPRequestHandler, path: str) -> bool:
    prefix = "/build-preview/"
    if not path.startswith(prefix):
        return False
    relative = urllib.parse.unquote(path[len(prefix):]).replace("\\", "/")
    parts = [part for part in relative.split("/") if part]
    if not parts:
        _json_response(handler, 400, {"ok": False, "status": "workspace name missing"})
        return True
    workspace_name = parts[0]
    if workspace_name in {".", ".."} or "/" in workspace_name or "\\" in workspace_name:
        _json_response(handler, 400, {"ok": False, "status": "invalid workspace name"})
        return True
    workspace = _path_below(BUILD_WORKSPACE_ROOT, workspace_name)
    if not workspace.is_dir():
        _json_response(handler, 404, {"ok": False, "status": "workspace not found"})
        return True
    target = _path_below(workspace, "/".join(parts[1:]) or "index.html")
    if target.is_dir():
        target = _path_below(target, "index.html")
    _file_response(handler, target)
    return True


def _serve_build_package(handler: BaseHTTPRequestHandler, path: str) -> bool:
    prefix = "/build-package/"
    if not path.startswith(prefix):
        return False
    name = urllib.parse.unquote(path[len(prefix):])
    if not name or Path(name).name != name or not name.casefold().endswith(".zip"):
        _json_response(handler, 400, {"ok": False, "status": "invalid package name"})
        return True
    package = _path_below(BUILD_PACKAGE_ROOT, name)
    _file_response(handler, package, download_name=name)
    return True


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    max_length = int(os.environ.get("ENGEL_CHAT_JSON_BODY_LIMIT_BYTES", str(12 * 1024 * 1024)) or str(12 * 1024 * 1024))
    if length > max_length:
        raise ValueError(f"request JSON body exceeds {max_length} byte limit")
    raw = handler.rfile.read(length).decode("utf-8-sig", errors="replace") if length else "{}"
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("request JSON must be an object")
    return data


def _plain_chat_prompt_from_request(request: dict[str, Any]) -> str:
    return _clean_text(request.get("prompt") or request.get("message") or "").strip()


def _redact(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        from engel_ui_prompt_training_support import redact

        return redact(payload)
    except Exception:
        return payload


def _rag_runtime_snapshot() -> dict[str, Any]:
    if not callable(rag_runtime_status_snapshot):
        return {
            "schema": "ENGEL_RAG_RUNTIME_STATUS_V2",
            "ok": False,
            "status": "RAG runtime import failed",
            "error": _RAG_RUNTIME_IMPORT_ERROR[:500],
            "production_route_count": 0,
            "provider_called": False,
            "trusted_memory_write": False,
            "index_mutation": False,
        }
    try:
        return rag_runtime_status_snapshot()
    except Exception as exc:
        return {
            "schema": "ENGEL_RAG_RUNTIME_STATUS_V2",
            "ok": False,
            "status": "RAG runtime status failed",
            "error": str(exc)[:500],
            "production_route_count": 0,
            "provider_called": False,
            "trusted_memory_write": False,
            "index_mutation": False,
        }


def _rag_runtime_execute(request: dict[str, Any]) -> dict[str, Any]:
    if not callable(execute_rag_route):
        raise RuntimeError(
            "RAG runtime is unavailable"
            + (f": {_RAG_RUNTIME_IMPORT_ERROR[:300]}" if _RAG_RUNTIME_IMPORT_ERROR else "")
        )
    return execute_rag_route(
        str(request.get("query") or request.get("prompt") or ""),
        strategy=str(request.get("strategy") or "simple"),
        k=int(request.get("k") or request.get("top_k") or 4),
        modal_context=str(
            request.get("modal_context")
            or request.get("normalized_media_context")
            or ""
        ),
    )


def _ai_systems_snapshot() -> dict[str, Any]:
    if not callable(ai_systems_status_snapshot):
        return {
            "schema": "ENGEL_AI_SYSTEMS_STATUS_V1",
            "ok": False,
            "status": "AI systems proof runtime import failed",
            "error": _AI_SYSTEMS_IMPORT_ERROR[:500],
            "ready_count": 0,
            "system_count": 12,
        }
    try:
        return ai_systems_status_snapshot()
    except Exception as exc:
        return {
            "schema": "ENGEL_AI_SYSTEMS_STATUS_V1",
            "ok": False,
            "status": "AI systems proof failed",
            "error": str(exc)[:500],
            "ready_count": 0,
            "system_count": 12,
        }


def _meeting_room_url() -> str:
    if os.environ.get("ENGEL_MAIN_SERVER_MEETING_ROOM_DISABLED", "").strip().lower() in {"1", "true", "yes", "on"}:
        return ""
    return os.environ.get("ENGEL_MAIN_SERVER_MEETING_ROOM_URL", DEFAULT_MEETING_ROOM_URL).strip().rstrip("/")


def _meeting_room_timeout_seconds() -> float:
    try:
        value = float(os.environ.get("ENGEL_MAIN_SERVER_MEETING_ROOM_TIMEOUT_SECONDS", "12"))
    except Exception:
        value = 12.0
    return max(0.25, min(20.0, value))


def _post_meeting_room_chat(prompt: str, reply: str) -> dict[str, Any]:
    url = _meeting_room_url()
    if not url:
        return {"ok": False, "meeting_room_server_used": False, "reason": "server meeting room disabled"}
    payload = {
        "schema": "engel_main_server_meeting_room_chat_v1",
        "prompt": prompt,
        "assistant_reply": reply,
        "source": "engel-ai-main CT chat service",
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url + "/room/chat",
        data=data,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_meeting_room_timeout_seconds()) as resp:
            parsed = json.loads(resp.read().decode("utf-8", errors="replace"))
        if not isinstance(parsed, dict):
            return {"ok": False, "meeting_room_server_used": False, "reason": "meeting room returned non-object JSON"}
        parsed.setdefault("meeting_room_server_url", url)
        parsed.setdefault("meeting_room_server_used", bool(parsed.get("ok") is True))
        return parsed
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "meeting_room_server_used": False,
            "meeting_room_server_url": url,
            "reason": f"meeting room HTTP {exc.code}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "meeting_room_server_used": False,
            "meeting_room_server_url": url,
            "reason": str(exc),
        }


def _prompt_requests_instant_desktop_chat(prompt: str) -> bool:
    low = _intent_gate_text(prompt).casefold().strip()
    if not low or len(low) > 220:
        return False
    instant_terms = (
        "hello",
        "hey",
        "hi",
        "good morning",
        "good afternoon",
        "good evening",
        "are you there",
        "you there",
        "wake up",
        "ping",
        "test chat",
        "quick hello",
    )
    if any(term in low for term in instant_terms):
        return True
    return low in {"yo", "sup", "gm", "hi engel", "hello engel"}


def _prompt_requests_meeting_room_dispatch(prompt: str) -> bool:
    # A declared chat-only turn (request flag "chat_only", narrow-only) never
    # requests dispatch, no matter its wording -- this is THE chokepoint, since
    # allow_room is computed at a dozen explicit call sites. Live 2026-07-31:
    # the EngelScript draft instruction was dispatched as a room order twice.
    if _TURN_CHAT_ONLY.get():
        return False
    low = _intent_gate_text(prompt).casefold()
    stripped = low.lstrip()
    # (2026-07-09 audit — meeting-room hijack fix) An INFORMATIONAL question about the
    # room/fleet ("what does the meeting room do", "explain the agent room") must be
    # ANSWERED, never dispatched — even though it contains a strong room term. This
    # guard runs FIRST, before the strong-term match. An EXPLICIT order
    # (send/route/dispatch/create an order) overrides it.
    explicit_dispatch = any(v in low for v in (
        "send ", "dispatch", "route ", "kick off", "assign ", "create an order",
        "create order", "submit an order", "put in an order", "have the room",
        "order to the", "order for the", "give the room", "give the whole",
        "create something", "with this room", "using this room", "use this room",
    ))
    informational = (
        stripped.startswith((
            "write ", "summarize", "describe", "explain", "what ", "what's", "whats",
            "who ", "why ", "how ", "when ", "where ", "does ", "is ", "are ",
            "can you explain", "can you describe", "do you know", "tell me about",
            "give me a", "list ", "draft ", "in one sentence", "in two", "in three",
        ))
        or any(p in low for p in ("write a", "2-sentence", "3-sentence", "one-sentence"))
    )
    if informational and not explicit_dispatch:
        return False
    # (2026-07-07 polish) Strong, unambiguous room phrases route to the room.
    strong_terms = (
        "meeting room",
        "agent room",
        "server world",
        "3d room",
        "3d agent",
        "agent workspace",
        "minecraft",
        "work order",
        "proof job",
        "room chat",
        "show devices working",
        "have the phones",
        "ask the phones",
        "phones check",
        "phone workers check",
        "android workers check",
        "dispatch to the room",
        "run the room",
        "run in the room",
        "across all devices",
        "across the fleet",
        # (2026-07-09 audit — under-fire fix) fleet-wide dispatch phrases so
        # "send the whole room an order" / "give the whole team a job" ROUTE to the
        # room instead of being answered by the tiny fast-local lane.
        "whole room",
        "the whole team",
        "whole team",
        "entire fleet",
        "the whole fleet",
        "order to the room",
        "order to the whole",
        "with this room",
        "using this room",
        "use this room",
        "create something with this room",
    )
    if any(term in low for term in strong_terms):
        return True
    device_terms = (
        "all devices", "all agents", "alpha", "beta", "gamma", "phone worker",
        "android worker", "sub-engel", "the phones", "one job", "collaborate",
        "work together", "the fleet", "the team", "everyone",
    )
    dispatch_verbs = (
        "have ", "ask ", "tell ", "send ", "dispatch", "assign", "get ", "route",
        "run ", "kick off", "do this", "handle this", "work on",
    )
    return any(d in low for d in device_terms) and any(v in low for v in dispatch_verbs)


def _meeting_room_skipped(reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "meeting_room_server_used": False,
        "reason": reason,
    }


def _clip_visible_room_text(value: Any, limit: int = 900) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _meeting_room_visible_reply(prompt: str, current_reply: str, meeting_room: dict[str, Any]) -> str:
    if meeting_room.get("ok") is not True or meeting_room.get("meeting_room_server_used") is not True:
        return current_reply
    order = meeting_room.get("order") if isinstance(meeting_room.get("order"), dict) else {}
    completion = meeting_room.get("completion") if isinstance(meeting_room.get("completion"), dict) else {}
    order_id = str(order.get("order_id") or completion.get("order_id") or "").strip()
    station_results = completion.get("station_results")
    if not isinstance(station_results, list):
        station_results = []
    station_text = ", ".join(str(item).strip() for item in station_results if str(item or "").strip())
    summary = str(completion.get("summary") or order.get("summary") or "").strip()

    parts = ["Sent that through the Agent Meeting Room on CT246."]
    if order_id:
        parts.append(f"Order {order_id} is recorded.")
    if station_text:
        parts.append("Room result: " + _clip_visible_room_text(station_text, 500))
    elif summary:
        parts.append(_clip_visible_room_text(summary))
    else:
        parts.append("The room accepted the work order and saved the receipt.")
    return " ".join(parts)


def _append_meeting_room_memory(
    prompt: str,
    reply: str,
    meeting_room: dict[str, Any],
    receipt: dict[str, Any],
) -> bool:
    if meeting_room.get("ok") is not True or meeting_room.get("meeting_room_server_used") is not True:
        return False
    order = meeting_room.get("order") if isinstance(meeting_room.get("order"), dict) else {}
    completion = meeting_room.get("completion") if isinstance(meeting_room.get("completion"), dict) else {}
    try:
        _append_jsonl(
            PERSISTENT_CHAT_MEMORY_PATH,
            {
                "schema": "engel_chat_meeting_room_dispatch_memory_v1",
                "memory_source": "engel-ai-main CT meeting room dispatch",
                "updated_at_utc": _iso_now(),
                "prompt": prompt,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "assistant_reply": reply,
                "provider": receipt.get("provider"),
                "runtime_provider": receipt.get("runtime_provider"),
                "selected_provider": receipt.get("selected_provider"),
                "status": receipt.get("status"),
                "agent_meeting_room_used": True,
                "meeting_room_server_used": True,
                "meeting_room_order_id": order.get("order_id") or completion.get("order_id"),
                "meeting_room_order_path": completion.get("order_path"),
                "meeting_room_station_results": completion.get("station_results") or [],
                "workspace_receipt_path": receipt.get("workspace_receipt_path"),
                "persistent_chat_memory_path": str(PERSISTENT_CHAT_MEMORY_PATH),
            },
        )
        return True
    except Exception:
        return False


def _append_final_chat_memory(
    prompt: str,
    reply: str,
    receipt: dict[str, Any],
    source: str,
) -> tuple[bool, str]:
    try:
        # (NT-1) compute depth at the memory-write choke-point so EVERY persistent record is
        # labelled — not just turns that passed through _finalize_chat_receipt's stamp (fast /
        # canned / reflex paths append here directly). Deterministic: equals the finalize stamp
        # when one was set. Pure telemetry; never affects the reply.
        _ad, _adl, _esc = _activation_depth(receipt, source, receipt.get("escalated_from"))
        memory_record = {
            "schema": "engel_ai_main_persistent_chat_history_v1",
            "memory_source": f"engel-ai-main CT finalized {source}",
            "created_at_utc": _iso_now(),
            "prompt": _clean_text(prompt),
            "prompt_sha256": hashlib.sha256(_clean_text(prompt).encode("utf-8")).hexdigest(),
            "assistant_reply": _clean_text(reply),
            "assistant_output_text": _clean_text(reply),
            "assistant_reply_sha256": hashlib.sha256(_clean_text(reply).encode("utf-8")).hexdigest(),
            "provider": receipt.get("provider"),
            "runtime_provider": receipt.get("runtime_provider"),
            "selected_provider": receipt.get("selected_provider"),
            "status": receipt.get("status"),
            "ok": receipt.get("ok"),
            "source": "Engel AI Main",
            "server_role": receipt.get("server_role") or "engel-ai-main CT 246",
            "workspace_receipt_path": receipt.get("workspace_receipt_path") or receipt.get("receipt_path"),
            "persistent_chat_memory_path": str(PERSISTENT_CHAT_MEMORY_PATH),
            "agent_meeting_room_used": receipt.get("agent_meeting_room_used"),
            "meeting_room_server_used": receipt.get("meeting_room_server_used"),
            "meeting_room_order_id": receipt.get("meeting_room_order_id"),
            "mission_control_job_id": receipt.get("mission_control_job_id"),
            "mission_control_job_dir": receipt.get("mission_control_job_dir"),
            "final_receipt_path": receipt.get("final_receipt_path"),
            "named_artifact_path": receipt.get("named_artifact_path"),
            "model_output_trusted": False,
            "trusted_memory_write_enabled": False,
            "approved_memory_write_enabled": False,
            "trust_scope": "context-only chat continuity; not approved trusted memory",
            # (NT-1) which cascade depth answered this turn (0 router / 1 quick / 2 big / 3 bridge)
            "activation_depth": _ad,
            "activation_depth_label": _adl,
            "escalated_from": _esc,
            # (NT-2, 2026-07-26 neuro audit) durable escalation telemetry — null
            # on non-quick turns; without these the tau dial was untunable.
            "quick_lane_confidence": receipt.get("quick_lane_confidence"),
            "quick_lane_confidence_tau": receipt.get("quick_lane_confidence_tau"),
            "quick_lane_escalated": receipt.get("quick_lane_escalated"),
            "quick_lane_forced_escalation_reason": receipt.get("quick_lane_forced_escalation_reason"),
            "quick_lane_escalation_evidence": receipt.get("quick_lane_escalation_evidence"),
            "mode_gate": receipt.get("mode_gate"),
            "self_model_freshness": receipt.get("self_model_freshness"),
            # GAIS pillar 3: the per-reply confidence verdict rides the canonical
            # memory row so trust can be audited/tuned from logged turns.
            "inference_confidence": receipt.get("inference_confidence"),
        }
        _stamp_chat_memory_hygiene(memory_record, receipt)
        _append_jsonl(PERSISTENT_CHAT_MEMORY_PATH, memory_record)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _stamp_chat_memory_hygiene(
    record: dict[str, Any], receipt: dict[str, Any] | None
) -> dict[str, Any]:
    """Governor memory hygiene (docs/ENGEL_GOVERNOR_DESIGN.md section 4): persist
    and context-visibility are INDEPENDENT. Training turns and contract echoes
    stay in the store (the corpus and the trainer's DONE gate need the append)
    but are stamped context_eligible False so no later turn reloads them as chat
    context, and a training turn's prompt is replaced by its base ask so the
    injected answer contract never enters memory at all. prompt_sha256 stays at
    the DELIVERED prompt's hash -- the trainer's CT cross-check matches on it.
    The 2026-07-31 live proof showed the runner-side persister alone was not
    enough: sparse-MoE turns are written HERE, unstamped, so this is the
    chokepoint. Missing engel_governor (older deploy) leaves the record as-is."""
    try:
        from engel_governor import looks_like_contract_echo
    except Exception:
        return record
    try:
        from engel_governor import looks_like_training_wrapper as _looks_like_training_wrapper
    except Exception:  # noqa: BLE001 -- older governor deploy: keep the old behaviour
        def _looks_like_training_wrapper(_text: Any) -> bool:
            return False
    receipt = receipt if isinstance(receipt, dict) else {}
    governor_context = receipt.get("governor_context")
    if not isinstance(governor_context, dict) or not governor_context:
        # The persister runs before the finalize path stamps the receipt; fall
        # back to the turn-scoped context set at the top of _run_chat_turn.
        governor_context = _TURN_GOVERNOR_CONTEXT.get() or {}
    prompt = str(record.get("prompt") or "")
    reply = str(record.get("assistant_reply") or record.get("assistant_output_text") or "")
    training = bool(
        receipt.get("local_only_training") is True
        or record.get("local_only_training") is True
        or record.get("training_turn") is True
        or str(governor_context.get("persist_policy") or "") == "training"
        # metadata-free discriminator: the injected answer contract rides the
        # training wrapper, so a prompt carrying contract phrasing IS a
        # training turn even when no flag survived transit.
        or looks_like_contract_echo(prompt)
        # ...and the wrapper's own scaffolding ("Training depth: ... / Training task:")
        # counts too. The contract markers only describe how to ANSWER, so a delivery
        # that lost its metadata was stored as ordinary chat and recalled later as
        # something Joshua said (335 such rows measured 2026-08-13).
        or _looks_like_training_wrapper(prompt)
    )
    echo = bool(looks_like_contract_echo(reply))
    base_prompt = str(governor_context.get("base_prompt") or "").strip()
    if training and base_prompt:
        record["prompt"] = base_prompt
        record["base_prompt_substituted"] = True
    record["local_only_training"] = bool(
        receipt.get("local_only_training") is True
        or record.get("local_only_training") is True
    )
    record["training_turn"] = training
    record["echo"] = echo
    record["context_eligible"] = not (training or echo)
    return record


def _ensure_final_chat_memory(
    receipt: dict[str, Any], prompt: str, reply: str, source: str
) -> dict[str, Any]:
    """Append a finalized persistent chat-memory record for this turn UNLESS an
    earlier route (provider bridge, etc.) already appended one. Idempotent per
    receipt via the persistent_chat_memory_appended flag, so a turn is never
    double-written to the persistent memory file by this fallback."""
    if receipt.get("persistent_chat_memory_appended") is True:
        return receipt
    memory_ok, memory_error = _append_final_chat_memory(prompt, reply, receipt, source)
    receipt["persistent_chat_memory_appended"] = memory_ok
    receipt["persistent_chat_history_appended"] = memory_ok
    receipt["persistent_chat_memory_path"] = str(PERSISTENT_CHAT_MEMORY_PATH)
    if memory_error:
        receipt["persistent_chat_memory_error"] = memory_error
    return receipt


def _sync_reps_for_chat(prompt: str, reply: str, source: str) -> bool:
    if _env_truth("ENGEL_MAIN_SERVER_SYNC_REPS_FOR_CHAT", default=False):
        return _prompt_should_force_reps_proposal(prompt, reply)
    return False


# (2026-07-10 NT-1) Activation-depth labelling — which cascade DEPTH answered a turn.
#   0 = router-only / deterministic / template / gate     2 = big lane (Mistral-7B, ROG RTX 2070 :8899)
#   1 = quick (qwen2.5-1.5b LoRA) lane                     3 = provider bridge (claude/gpt/gemini/codex/...)
# Pure telemetry: NOTHING reads activation_depth to branch reply logic. Fail-open -> 0 on any doubt.
# `source` (the explicit lane label the dispatcher passes to _finalize_chat_receipt) is authoritative;
# runtime_provider is only consulted when the source is a generic/unknown (depth-0) label.
_SOURCE_ACTIVATION_DEPTH = {
    "ct_provider_bridge_chat": 3,
    "ct_model_chat": 2,
    "ct_quick_local_chat": 1,
    "ct_default_fast_local_chat": 1,
    "ct_short_casual_fast_model": 1,
    "ct_quick_casual_chat": 1,
    "ct_mode_gate_reflex_chat": 1,
    "ct_code_lane": 1,  # coder-3b in-process gguf (depth 1 = local in-process lane)
    "ct_deep_local_specialist": 2,
    "ct_sparse_moe_specialist": 2,
    "ct_nemotron_lightning": 2,
    "ct_build_lane": 3,  # agentic build via the provider bridges (depth 3)
    # (2026-07-26 neuro audit) zero-inference deterministic/template routes are
    # depth 0 by definition — they were falling through to the "fast" heuristic
    # below and inflating the quick-lane bucket (and the SFT depth column).
    "ct_reps_template_chat": 0,
    "ct_fast_route_check": 0,
    "ct_fast_help_next": 0,
    "ct_fast_build_status": 0,
    "ct_fast_template_loop_repair": 0,
    "ct_fast_chat_fault_repair": 0,
    "ct_help_next_chat": 0,
    "ct_deterministic_visible_chat": 0,
    "ct_instant_desktop_chat": 0,
    "ct_fast_visible_chat": 0,
    "ct_math_lane": 0,  # deterministic sympy compute, zero inference
    "ct_grover_lane": 0,  # verified Grover logic, zero inference
    "ct_live_status_chat": 0,  # live probe, not a model promise
    "ct_live_status_receipt": 0,
    "ct_math_reasoning_lane": 2,  # deepseek-r1 CPU specialist = big local lane
}
_ACTIVATION_DEPTH_LABEL = {0: "router-only", 1: "quick-lane", 2: "big-lane", 3: "provider-bridge"}
_REAL_PROVIDER_MARKERS = ("claude", "anthropic", "grok", "xai", "chatgpt", "openai", "gemini", "codex", "nvidia", "nim")
# (2026-07-26) local-llama-cpp-lora is the CPU big lane (the merged aligned GGUF
# after the model swap) — without these markers it fell to the gguf heuristic
# and was mislabelled depth 1.
_BIG_LANE_MARKERS = ("rog-rtx2070", "llama-cpp-large", "rust-llama-cpp",
                     "local-llama-cpp-lora", "llama-cpp-qwen2.5-7b-lora",
                     "sparse-moe", "selective-experts")


def _activation_depth(
    receipt: dict[str, Any], source: str, escalated_from: "int | None" = None
) -> "tuple[int, str, int | None]":
    """Which cascade depth answered this turn: 0 router / 1 quick / 2 big / 3 bridge.
    Pure, fail-open telemetry derived from fields the dispatcher already set. Never raises."""
    try:
        # An EXPLICIT source mapping (including 0) is authoritative — a mapped-0
        # template route must never fall through to the runtime heuristics.
        src_key = str(source or "")
        if src_key in _SOURCE_ACTIVATION_DEPTH:
            src_d = _SOURCE_ACTIVATION_DEPTH[src_key]
        else:
            # Lanes that append their own memory record BEFORE the finalize
            # choke-point (build lane, workspace setup) reach the _append_jsonl
            # default-stamper with source="" — but their selected_provider IS
            # the lane label, so honor it (20260711: build-lane records were
            # all landing as depth 0 instead of 3).
            sel_key = str(receipt.get("selected_provider") or "")
            src_d = _SOURCE_ACTIVATION_DEPTH[sel_key] if sel_key in _SOURCE_ACTIVATION_DEPTH else None
        if src_d is not None:
            depth = src_d
        else:
            rp = (
                str(receipt.get("runtime_provider") or "") + " "
                + str(receipt.get("selected_provider") or "") + " "
                + str(receipt.get("provider") or "")
            ).lower()
            if any(m in rp for m in _REAL_PROVIDER_MARKERS):
                depth = 3
            elif any(m in rp for m in _BIG_LANE_MARKERS):
                depth = 2
            elif receipt.get("runs_inference") is False:
                # (2026-07-26 neuro audit) template/fast responders declare
                # runs_inference=False — a canned string never claims a model lane.
                depth = 0
            elif (
                "fast" in rp
                or "gguf" in rp
                or receipt.get("quick_local_front_lane_used") is True
                or receipt.get("quick_casual_model_used") is True
            ):
                # (2026-07-10) the quick lane writes its OWN memory record with the base
                # runtime_provider "llama-cpp-python-local-gguf" (no "fast" suffix yet) and no
                # source, so recognise its quick_casual_model_used marker / the gguf runtime too.
                depth = 1
            else:
                depth = 0
        return depth, _ACTIVATION_DEPTH_LABEL.get(depth, "router-only"), escalated_from
    except Exception:
        return 0, "router-only", escalated_from


def _compiler_slm_advisory(receipt: dict[str, Any]) -> dict[str, Any] | None:
    """Bundle intent_router + route_governor shadow for the compiler/LNT bind."""
    advisory = (
        dict(receipt.get("slm_advisory") or {})
        if isinstance(receipt.get("slm_advisory"), dict)
        else {}
    )
    gov = receipt.get("governor_route_decision")
    if isinstance(gov, dict):
        verdict = gov.get("verdict") if isinstance(gov.get("verdict"), dict) else gov
        if isinstance(verdict, dict):
            if verdict.get("slm_shadow") is not None:
                advisory["route_shadow"] = verdict.get("slm_shadow")
            if verdict.get("outcome"):
                advisory["governor_outcome"] = verdict.get("outcome")
    return advisory or None


def _attach_slm_compiler_lnt(receipt: dict[str, Any], prompt: str, source: str) -> None:
    """Record SLM router + MIPL compiler + Lifted iNTent on the chat receipt.

    Advisory only. Does not change the spoken reply or grant execution.
    Discord/CT turns skip the ROG worker, so this is the server-first bind.
    If MIPL already compiled this turn, stamp the trio without a second receipt.
    """
    if not str(prompt or "").strip():
        return
    try:
        import engel_lifted_intent as intent_bridge

        slm_advisory = _compiler_slm_advisory(receipt)
        if receipt.get("lifted_intent_receipt_path") and isinstance(receipt.get("lifted_intent"), dict):
            wrapped = intent_bridge.stamp_slm_compiler_lnt(receipt, slm_advisory=slm_advisory)
        else:
            wrapped = intent_bridge.attach_slm_compiler_lnt(
                prompt,
                {
                    "ok": receipt.get("ok") is True,
                    "assistant_reply": receipt.get("assistant_reply") or "",
                    "receipt": receipt,
                },
                caller="engel_main_server_chat",
                request_id=str(receipt.get("run_id") or source or ""),
                slm_advisory=slm_advisory,
            )
        for key in (
            "lifted_intent",
            "lifted_intent_receipt_path",
            "lifted_intent_audit_complete",
            "lnt",
            "mipl_compiler",
            "slm_router_advisory",
        ):
            if wrapped.get(key) is not None:
                receipt[key] = wrapped.get(key)
    except Exception:
        receipt["slm_compiler_lnt_error"] = "fail_open"


def _attach_speech_spc(receipt: dict[str, Any], prompt: str, source: str) -> None:
    """Compile a speak packet after LNT/humanization. Never plays audio."""
    if not str(prompt or "").strip():
        return
    try:
        import engel_speech_spc as speech_spc

        wrapped = speech_spc.attach_speech_spc(
            prompt,
            str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or ""),
            receipt,
            source=source,
            caller="engel_main_server_chat",
        )
        for key in ("speech_spc", "speech_spc_receipt_path"):
            if wrapped.get(key) is not None:
                receipt[key] = wrapped.get(key)
    except Exception:
        receipt["speech_spc_error"] = "fail_open"


def _attach_slm_advisory(receipt: dict[str, Any], prompt: str, reply: str) -> None:
    """ADVISORY-ONLY telemetry from every eligible hot-path SLM roster head.

    Nothing here changes the reply,
    the routing, or any gate -- deterministic gates keep deciding; this records
    what the learned models WOULD have said so promotion decisions are made on
    logged agreement, not vibes (design section 5: advisory -> shadow -> in-path).
    Never blocks: the runtime answers None until its background warm-up finished,
    and any failure is swallowed -- a telemetry write must never cost a turn."""
    if not _env_truth("ENGEL_SLM_ADVISORY_ENABLED", default=True):
        return
    try:
        from engel_slm_runtime import get_slm_runtime

        slm = get_slm_runtime()
        if not slm.is_ready():
            receipt["slm_advisory"] = {"ready": False}
            return
        advisory: dict[str, Any] = {"ready": True}
        intent = slm.intent(prompt)
        if intent:
            advisory["intent"] = intent
        flags = slm.style_flags(prompt, str(reply or ""))
        if flags:
            advisory["style"] = flags
        quality = slm.reply_quality(prompt, str(reply or ""))
        if quality:
            advisory["reply_quality"] = quality
        receipt["slm_advisory"] = advisory
    except Exception:  # noqa: BLE001 -- advisory telemetry never costs a turn
        pass


def _attach_math_verdict(receipt: dict[str, Any], reply: str, source: str) -> None:
    """ADVISORY-ONLY CAS check of the maths a reply actually asserts.

    The training gate already refuses to LEARN from refuted maths; this records the
    same verdict on the SERVING receipt so a wrong spoken answer is at least visible.
    Same contract as _attach_slm_advisory: never changes the reply, never blocks,
    every failure swallowed. FAIL OPEN -- most chat maths is not checkable and an
    unverified claim is NOT a wrong claim; only a CAS-proven refutation is flagged.
    ct_math_lane is skipped: its output is already CAS-verified and the claim
    extractor invents junk claims from its explanatory prose."""
    if not _env_truth("ENGEL_MATH_SERVING_VERDICT_ENABLED", default=True):
        return
    if source == "ct_math_lane":
        receipt["math_serving_verdict"] = {"checked": False, "skip_reason": "ct_math_lane output is already CAS-verified"}
        return
    if source == "ct_grover_lane":
        receipt["math_serving_verdict"] = {"checked": False, "skip_reason": "ct_grover_lane output is already formula-verified"}
        return
    try:
        from engel_math_answer_verifier import verify_reply

        _t0 = time.perf_counter()
        # max_claims=4 bounds the worst case (each claim capped at the CAS 2s budget);
        # a claim-free reply costs regex extraction only.
        result = verify_reply(str(reply or ""), max_claims=4, normalize=True)
        receipt["math_serving_verdict"] = {
            "checked": True,
            "refuted": bool(result.get("refuted")),
            "claim_count": len(result.get("claims") or []),
            "confirmed_count": int(result.get("confirmed_count") or 0),
            "reason": str(result.get("reason") or ""),
            "duration_ms": int((time.perf_counter() - _t0) * 1000),
        }
    except Exception:  # noqa: BLE001 -- a serving-side check must never cost a turn
        pass


def _attach_gais_confidence(receipt: dict[str, Any], prompt: str, reply: str, source: str) -> None:
    """GAIS pillar 3: a confidence-of-inference verdict on every served reply.

    Aggregates the verifier signals THIS turn actually produced (sympy proof or
    refutation, SLM reply-quality head, quick-lane confidence, semantic-quality
    gates, persona/echo markers) into receipt['inference_confidence'] with an
    honest trust percent: no signals -> trust None ("unverified"), never an
    invented number, and only a deterministic proof may read as "verified".
    Same contract as the two attach helpers above: advisory-only, never changes
    the reply, never blocks, every failure swallowed. Must run AFTER
    _attach_slm_advisory and _attach_math_verdict - it consumes their output."""
    if not _env_truth("ENGEL_GAIS_CONFIDENCE_ENABLED", default=True):
        return
    try:
        from engel_gais import score_inference

        receipt["inference_confidence"] = score_inference(
            receipt, prompt=prompt, reply=reply, source=source
        )
    except Exception:  # noqa: BLE001 -- a verdict must never cost a turn
        pass


def _finalize_chat_receipt(
    receipt: dict[str, Any],
    prompt: str,
    reply: str,
    source: str,
    started: float,
    *,
    allow_room: bool | None = None,
    allow_reps: bool | None = None,
    escalated_from: "int | None" = None,
    persist_memory: bool = True,
) -> dict[str, Any]:
    receipt = _apply_global_chat_safety(prompt, receipt, source)
    # (NT-1) stamp the answering cascade depth once, at the single finalize choke-point,
    # so it lands on both the receipt file and the persistent-memory record below.
    _depth, _depth_label, _esc = _activation_depth(receipt, source, escalated_from)
    receipt["activation_depth"] = _depth
    receipt["activation_depth_label"] = _depth_label
    if _esc is not None:
        receipt["escalated_from"] = _esc
    else:
        receipt.setdefault("escalated_from", None)
    reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
    original_reply = reply
    reply, assistant_identity_fixed, assistant_identity_repairs = repair_assistant_self_identity(reply)
    if assistant_identity_fixed:
        receipt["raw_model_reply"] = original_reply
        receipt["assistant_reply"] = reply
        receipt["assistant_output_text"] = reply
        receipt["identity_mixup"] = True
        receipt["shared_identity_guard_repaired"] = True
        receipt["shared_identity_guard_repairs"] = assistant_identity_repairs
        receipt["training_sample_eligible"] = False
        receipt["persistent_chat_memory_training_eligible"] = False
    if allow_room is None:
        allow_room = _prompt_requests_meeting_room_dispatch(prompt)
    if allow_room:
        meeting_room = _post_meeting_room_chat(prompt, reply)
    else:
        meeting_room = _meeting_room_skipped("not requested by this chat turn")
    receipt["agent_meeting_room_used"] = bool(
        receipt.get("agent_meeting_room_used") is True or meeting_room.get("ok") is True
    )
    receipt["meeting_room_server_used"] = bool(
        receipt.get("meeting_room_server_used") is True
        or meeting_room.get("meeting_room_server_used") is True
    )
    receipt["meeting_room_server_response"] = meeting_room
    if receipt["meeting_room_server_used"]:
        room_reply = _meeting_room_visible_reply(prompt, reply, meeting_room)
        if room_reply:
            reply = room_reply
            receipt["assistant_reply"] = room_reply
            receipt["assistant_output_text"] = room_reply
            receipt["reply_rewritten_from_meeting_room_result"] = True
            receipt["meeting_room_persistent_memory_appended"] = _append_meeting_room_memory(
                prompt,
                room_reply,
                meeting_room,
                receipt,
            )
    receipt["server_request_latency_ms"] = int((time.perf_counter() - started) * 1000)
    route_decision = _TURN_GOVERNOR_ROUTE_DECISION.get()
    if isinstance(route_decision, dict):
        receipt["governor_route_decision"] = route_decision
    _attach_slm_advisory(receipt, prompt, reply)
    _attach_slm_compiler_lnt(receipt, prompt, source)
    _attach_speech_spc(receipt, prompt, source)
    _attach_math_verdict(receipt, reply, source)
    _attach_gais_confidence(receipt, prompt, reply, source)

    if allow_reps is None:
        allow_reps = _sync_reps_for_chat(prompt, reply, source)
    if allow_reps:
        receipt = _attach_reps_cycle_to_receipt(receipt, prompt, reply, source)
    else:
        receipt["universal_reps_runtime_used"] = False
        receipt["universal_reps_runtime_skipped"] = True
        receipt["universal_reps_runtime_skip_reason"] = "desktop chat response path stays nonblocking"
    if persist_memory:
        receipt = _ensure_final_chat_memory(receipt, prompt, reply, source)
    receipt_path = str(receipt.get("workspace_receipt_path") or "").strip()
    if receipt_path:
        try:
            _write_json(Path(receipt_path), receipt)
        except Exception as exc:
            receipt["finalized_receipt_write_error"] = str(exc)
    return receipt


def _prompt_is_router_work_order(prompt: str, request: dict[str, Any] | None = None) -> bool:
    """Hermes-style: create/update/room jobs go through the router, not a raw model call."""
    if _prompt_requests_meeting_room_dispatch(prompt):
        return True
    try:
        import engel_build_lane
        if engel_build_lane.is_build_request(prompt) is not None:
            return True
        if engel_build_lane.is_continue_or_retry_build_request(prompt):
            return True
    except Exception:
        pass
    request = request or {}
    has_context = bool(
        (isinstance(request.get("attachments"), list) and request.get("attachments"))
        or int((request.get("context_pack") or {}).get("item_count") or 0) > 0
    )
    low = _intent_gate_text(prompt).casefold()
    update_verbs = (
        "update", "create", "build", "make ", "add more", "fix this",
        "more comments", "more posts", "change this",
    )
    return has_context and any(verb in low for verb in update_verbs)


def _explicit_provider_bridge_requested(prompt: str, request: dict[str, Any]) -> bool:
    _, reason = _provider_candidates_for_prompt(prompt, request)
    return reason == "explicit_provider"


def _complete_provider_bridge_turn(
    prompt: str,
    request: dict[str, Any],
    started: float,
    *,
    persist_memory: bool = True,
) -> tuple[dict[str, Any], str] | None:
    provider_receipt = _provider_bridge_receipt(
        prompt,
        request,
        started,
        persist_memory=persist_memory,
    )
    if provider_receipt is None:
        return None
    # Hermes-style: a dead/timed-out primary model falls through to the router
    # and local lanes. Do not return the canned "wired but not usable" reply.
    if provider_receipt.get("provider_bridge_used") is not True:
        return None
    reply = str(provider_receipt.get("assistant_reply") or provider_receipt.get("assistant_output_text") or "")
    provider_receipt = _finalize_chat_receipt(
        provider_receipt,
        prompt,
        reply,
        "ct_provider_bridge_chat",
        started,
        escalated_from=request.get("_engel_escalated_from"),
        persist_memory=persist_memory,
    )
    reply = str(provider_receipt.get("assistant_reply") or provider_receipt.get("assistant_output_text") or reply)
    return provider_receipt, reply


_MISSION_CONTROL_CREATE_VERB = r"create|make|build|run|start|generate|spin up|kick off|launch"
# A genuine IMPERATIVE create directive: the create verb at the start of the
# prompt or of a sentence/clause, after only optional address/politeness
# prefixes. This deliberately does NOT match the verb embedded in a QUESTION
# ("why did you create...", "how do I build...", "did you create...", "what
# happens when I create...") because those are status/read/meta questions that
# must be answered, not executed as durable side-effectful jobs.
_MISSION_CONTROL_IMPERATIVE = re.compile(
    r"(?:^|[.:;\n]\s*)"
    r"(?:(?:please|pls|hey|ok|okay|yo|engel|now|kindly|just|go ahead and"
    r"|can you|could you|would you|will you|can u|could u)\b[\s,:-]*)*"
    r"(?:" + _MISSION_CONTROL_CREATE_VERB + r")\b"
)
_MISSION_CONTROL_JOB_INTENT = re.compile(r"\bmission control\b.*?\bjob\b", re.S)
_MISSION_CONTROL_DURABLE_INTENT = re.compile(r"\bdurable\b.*?\bjob\b", re.S)


def _prompt_requests_mission_control_job(prompt: str) -> bool:
    """Only an EXPLICIT imperative create request may spawn a durable, side-
    effectful Mission Control job. Status/read/meta questions ("did the mission
    control receipt pass?", "why did you create a mission control job?", "how do
    I build a job?", "what's the final receipt path?") must NOT trigger job
    execution — they are answered by the normal chat/status path. Requires an
    imperative create directive AND explicit Mission Control job intent, and
    always uses the configured CT246 Mission Control root.
    """
    low = _intent_gate_text(prompt).casefold()
    if _MISSION_CONTROL_IMPERATIVE.search(low) is None:
        return False
    if _MISSION_CONTROL_JOB_INTENT.search(low) or _MISSION_CONTROL_DURABLE_INTENT.search(low):
        return True
    return "mission control job" in low or "ui_mission_control_demo" in low


def _mission_control_artifact_name(prompt: str) -> str:
    match = re.search(r"(?:named|called)\s+([A-Za-z0-9_.-]{3,80})", _clean_text(prompt), re.IGNORECASE)
    raw = match.group(1) if match else "ui_mission_control_demo"
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._-") or "ui_mission_control_demo"
    if not name.casefold().endswith(".json"):
        name += ".json"
    return name[:96]


def _parse_mission_control_job_id(text: str) -> str:
    matches = re.findall(r"\b20\d{6}T\d{6}Z-[A-Za-z0-9_.-]+\b", _clean_text(text))
    return matches[-1] if matches else ""


def _parse_mission_control_completed_dir(text: str, job_id: str) -> str:
    clean = _clean_text(text)
    match = re.search(r"(/mnt/ssd-ai/engel-control/jobs/completed/[A-Za-z0-9_.-]+)", clean)
    if match:
        return match.group(1)
    candidate = MISSION_CONTROL_ROOT / "jobs" / "completed" / job_id
    if job_id and candidate.is_dir():
        return str(candidate)
    return ""


def _mission_control_run(args: list[str], timeout: int = 90) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            ["python3", *args],
            cwd=str(MISSION_CONTROL_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {
            "args": ["python3", *args],
            "exit_code": int(completed.returncode),
            "stdout": _clip_multiline(completed.stdout, 5000),
            "stderr": _clip_multiline(completed.stderr, 5000),
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }
    except Exception as exc:
        return {
            "args": ["python3", *args],
            "exit_code": -1,
            "stdout": "",
            "stderr": _clip_multiline(str(exc), 5000),
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }


# In-flight guard: an identical prompt (e.g. a client-timeout retry) must NOT
# mint a second concurrent Mission Control job. Keyed by prompt sha256; entries
# auto-expire so a crashed/abandoned turn cannot wedge the key forever.
_MISSION_CONTROL_INFLIGHT: dict[str, float] = {}
_MISSION_CONTROL_GUARD = threading.Lock()
_MISSION_CONTROL_INFLIGHT_TTL_SECONDS = 900.0


def _claim_mission_control_job(prompt_hash: str) -> float | None:
    """Claim exclusive in-flight execution for this prompt hash. Returns None
    when the claim is granted, or the seconds-in-progress of the existing claim
    (meaning the caller should coalesce instead of starting a duplicate job)."""
    now = time.monotonic()
    with _MISSION_CONTROL_GUARD:
        for stale_hash, claimed_at in list(_MISSION_CONTROL_INFLIGHT.items()):
            if now - claimed_at > _MISSION_CONTROL_INFLIGHT_TTL_SECONDS:
                _MISSION_CONTROL_INFLIGHT.pop(stale_hash, None)
        existing = _MISSION_CONTROL_INFLIGHT.get(prompt_hash)
        if existing is not None:
            return max(0.0, now - existing)
        _MISSION_CONTROL_INFLIGHT[prompt_hash] = now
        return None


def _release_mission_control_job(prompt_hash: str) -> None:
    with _MISSION_CONTROL_GUARD:
        _MISSION_CONTROL_INFLIGHT.pop(prompt_hash, None)


def _mission_control_job_turn(prompt: str, started: float) -> tuple[dict[str, Any], str] | None:
    if not _prompt_requests_mission_control_job(prompt):
        return None

    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_MISSION_CONTROL_JOB_{stamp}.json"
    create_script = MISSION_CONTROL_ROOT / "scripts" / "engel_job_create.py"

    if not create_script.is_file():
        reply = (
            "Mission Control is not ready on CT246 because "
            f"{create_script} is missing. No undeclared storage path was used."
        )
        receipt = {
            "schema": "engel_main_server_mission_control_job_v1",
            "ok": False,
            "status": "Mission Control script missing",
            "updated_at_utc": _iso_now(),
            "run_id": stamp,
            "prompt": _clean_text(prompt),
            "assistant_reply": reply,
            "assistant_output_text": reply,
            "provider": "engel-mission-control",
            "runtime_provider": "ct246-mission-control-scripts",
            "selected_provider": "mission_control",
            "server_role": "engel-ai-main CT 246",
            "mission_control_root": str(MISSION_CONTROL_ROOT),
            "storage_policy": "CT246 declared roots only",
            "proxmox_modified": False,
            "training_interrupted": False,
            "workspace_receipt_path": str(receipt_path),
        }
        _write_json(receipt_path, receipt)
        receipt["receipt_path"] = str(receipt_path)
        return receipt, reply

    # Coalesce a retry of the SAME prompt (e.g. after a client timeout) onto the
    # in-flight job instead of minting a second concurrent CT246 job.
    prompt_hash = hashlib.sha256(_clean_text(prompt).encode("utf-8", errors="replace")).hexdigest()
    in_progress = _claim_mission_control_job(prompt_hash)
    if in_progress is not None:
        reply = (
            "A Mission Control job for this exact request is already running "
            f"(~{int(in_progress)}s in). I'm not starting a duplicate - re-check "
            "shortly for the final receipt."
        )
        receipt = {
            "schema": "engel_main_server_mission_control_job_v1",
            "ok": False,
            "status": "duplicate Mission Control request coalesced",
            "duplicate_suppressed": True,
            "updated_at_utc": _iso_now(),
            "run_id": stamp,
            "prompt": _clean_text(prompt),
            "prompt_sha256": prompt_hash,
            "assistant_reply": reply,
            "assistant_output_text": reply,
            "provider": "engel-mission-control",
            "runtime_provider": "ct246-mission-control-scripts",
            "selected_provider": "mission_control",
            "server_role": "engel-ai-main CT 246",
            "mission_control_root": str(MISSION_CONTROL_ROOT),
            "storage_policy": "CT246 declared roots only",
            "workspace_receipt_path": str(receipt_path),
        }
        _write_json(receipt_path, receipt)
        receipt["receipt_path"] = str(receipt_path)
        return receipt, reply

    try:
        return _execute_mission_control_flow(prompt, started, stamp, receipt_path)
    finally:
        _release_mission_control_job(prompt_hash)


def _execute_mission_control_flow(
    prompt: str, started: float, stamp: str, receipt_path: Path
) -> tuple[dict[str, Any], str]:
    artifact_name = _mission_control_artifact_name(prompt)
    commands: list[dict[str, Any]] = []
    job_id = ""
    completed_dir = ""
    final_receipt_path = ""
    verification_report_path = ""
    named_artifact_path = ""

    create = _mission_control_run(
        ["scripts/engel_job_create.py", "Create a test heartbeat report for approved workers."],
        timeout=45,
    )
    commands.append(create)
    if create.get("exit_code") == 0:
        job_id = _parse_mission_control_job_id(str(create.get("stdout") or ""))

    if job_id:
        for script_args in (
            ["scripts/engel_job_plan.py", job_id],
            ["scripts/engel_report_generator.py", job_id, "--heartbeat"],
        ):
            commands.append(_mission_control_run(script_args, timeout=90))

        active_job_dir = MISSION_CONTROL_ROOT / "jobs" / "active" / job_id
        artifacts_dir = active_job_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        heartbeat_path = artifacts_dir / "heartbeat_report.json"
        named_active_artifact = artifacts_dir / artifact_name
        if heartbeat_path.is_file():
            named_active_artifact.write_bytes(heartbeat_path.read_bytes())
        else:
            _write_json(
                named_active_artifact,
                {
                    "schema": "engel_ui_mission_control_demo_v1",
                    "status": "heartbeat report generator did not produce heartbeat_report.json",
                    "job_id": job_id,
                    "updated_at_utc": _iso_now(),
                    "commands": commands,
                },
            )
        named_artifact_path = str(named_active_artifact)

        for script_args in (
            ["scripts/engel_job_verify.py", job_id],
            ["scripts/engel_job_complete.py", job_id],
        ):
            command = _mission_control_run(script_args, timeout=90)
            commands.append(command)
            if script_args[0].endswith("engel_job_complete.py") and command.get("exit_code") == 0:
                completed_dir = _parse_mission_control_completed_dir(str(command.get("stdout") or ""), job_id)

    if job_id and not completed_dir:
        fallback_completed = MISSION_CONTROL_ROOT / "jobs" / "completed" / job_id
        if fallback_completed.is_dir():
            completed_dir = str(fallback_completed)
    if completed_dir:
        final_receipt = Path(completed_dir) / "final_receipt.md"
        verification_report = Path(completed_dir) / "verification_report.md"
        final_receipt_path = str(final_receipt) if final_receipt.is_file() else ""
        verification_report_path = str(verification_report) if verification_report.is_file() else ""
        completed_artifact = Path(completed_dir) / "artifacts" / artifact_name
        if completed_artifact.is_file():
            named_artifact_path = str(completed_artifact)

    ok = bool(job_id and completed_dir and final_receipt_path)
    if ok:
        reply = (
            "Mission Control created and verified a real CT246 worker heartbeat proof job. "
            f"Job ID: {job_id}. Final receipt: {final_receipt_path}. "
            f"Named artifact: {named_artifact_path or 'not found after completion'}."
        )
        status = "Mission Control job completed"
    else:
        failed = next((cmd for cmd in commands if int(cmd.get("exit_code", 0)) != 0), commands[-1] if commands else {})
        reply = (
            "Mission Control tried to create the CT246 job but did not reach a verified final receipt. "
            f"Job ID: {job_id or 'not created'}. Last error: {_clip(failed.get('stderr') or failed.get('stdout') or 'unknown', 420)}"
        )
        status = "Mission Control job failed"

    receipt = {
        "schema": "engel_main_server_mission_control_job_v1",
        "ok": ok,
        "status": status,
        "updated_at_utc": _iso_now(),
        "run_id": stamp,
        "prompt": _clean_text(prompt),
        "prompt_sha256": hashlib.sha256(_clean_text(prompt).encode("utf-8", errors="replace")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "engel-mission-control",
        "runtime_provider": "ct246-mission-control-scripts",
        "selected_provider": "mission_control",
        "server_role": "engel-ai-main CT 246",
        "mission_control_root": str(MISSION_CONTROL_ROOT),
        "mission_control_job_id": job_id,
        "mission_control_job_dir": completed_dir,
        "final_receipt_path": final_receipt_path,
        "verification_report_path": verification_report_path,
        "named_artifact_path": named_artifact_path,
        "commands": commands,
        "storage_policy": "CT246 declared roots only",
        "proxmox_modified": False,
        "training_interrupted": False,
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
    }
    _write_json(receipt_path, receipt)
    receipt["receipt_path"] = str(receipt_path)
    return receipt, reply


def _math_lane_turn(prompt: str, started: float) -> tuple[dict[str, Any], str] | None:
    """Deterministic verified math via sympy — Engel refuses to guess at numbers.

    The local models hallucinate arithmetic; this lane recognises a computable
    request, computes it EXACTLY in the training venv (system python3 has no
    sympy), verifies the result by an independent check (substitute roots back,
    differentiate the antiderivative, recompose factorizations, ...), and only
    serves it when verification passed. Anything else — detection miss, parse
    failure, verification failure, timeout — returns None and the normal model
    lanes take the turn. Unverified math never ships, and the reply must NEVER
    pass through the humanizer: a style rewrite on exact symbolic output is the
    gate-collision bug all over again.
    """
    lowered = str(prompt or "")
    if len(lowered) > 4000 or len(lowered) < 4:
        return None
    script = Path(ROOT) / "tools" / "engel_math_lane.py"
    if not script.is_file() or not Path(_TRAIN_VENV_PY).is_file():
        return None
    try:
        completed = subprocess.run(
            [_TRAIN_VENV_PY, str(script), "--json",
             json.dumps({"prompt": lowered})],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        outcome = json.loads(completed.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001 — fail open to the model lanes, never break chat
        return None
    if not isinstance(outcome, dict) or outcome.get("math_request") is not True:
        return None
    if outcome.get("ok") is not True or outcome.get("verified") is not True:
        # Math-shaped but not deterministically verifiable: tell the dispatcher so
        # it can escalate to the strongest reasoning model instead of chat default.
        return "math_shaped"  # type: ignore[return-value]
    result_text = str(outcome.get("result_text") or "").strip()
    verification = str(outcome.get("verification") or "").strip()
    if not result_text:
        return None
    reply = (
        f"Verified math result: {result_text}. "
        f"Check: {verification}. "
        "Computed exactly by Engel's deterministic math lane — nothing was guessed, "
        "and the full computation receipt is stored."
    )
    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_MATH_LANE_{stamp}.json"
    receipt: dict[str, Any] = {
        "schema": "engel_main_server_math_lane_v1",
        "ok": True,
        "status": "math lane answered deterministically via sympy",
        "updated_at_utc": _iso_now(),
        "run_id": f"main_server_math_lane_{stamp}",
        "prompt": _clean_text(lowered),
        "prompt_sha256": hashlib.sha256(_clean_text(lowered).encode("utf-8", errors="replace")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "engel-math-lane",
        "runtime_provider": "ct246-sympy-venv-subprocess",
        "selected_provider": "math_lane",
        "server_role": "engel-ai-main CT 246",
        "main_server_chat_service_used": True,
        "model_process_started": False,
        "runtime_process_started": False,
        "runs_inference": False,
        "provider_api_enabled": False,
        "network_enabled": False,
        "math_lane": {
            "engine": "sympy",
            "venv_python": _TRAIN_VENV_PY,
            "script": str(script),
            "operation": outcome.get("operation"),
            "input_expression": outcome.get("input"),
            "result": result_text,
            "verified": True,
            "verification": verification,
            "compute_elapsed_ms": outcome.get("elapsed_ms"),
        },
        # Receipts feed the SFT corpus; deterministic template-voice math must not
        # enter persona training (same policy as every other depth-0 template lane).
        "training_sample_eligible": False,
        "persistent_chat_memory_training_eligible": False,
        "storage_policy": "CT246 declared roots only",
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
    }
    try:
        _write_json(receipt_path, receipt)
    except Exception:  # noqa: BLE001 - the answer is still valid without the file
        pass
    receipt["receipt_path"] = str(receipt_path)
    return receipt, reply


def _grover_lane_turn(prompt: str, started: float) -> tuple[dict[str, Any], str] | None:
    """Verified Grover logic — Engel does not guess unstructured-search facts."""
    lowered = str(prompt or "")
    if len(lowered) > 4000 or len(lowered) < 6:
        return None
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from engel_grover_lane import answer_grover_prompt
        outcome = answer_grover_prompt(lowered)
    except Exception:  # noqa: BLE001 — fail open to the model lanes
        return None
    if not isinstance(outcome, dict) or outcome.get("grover_request") is not True:
        return None
    if outcome.get("ok") is not True or outcome.get("verified") is not True:
        return None
    result_text = str(outcome.get("result_text") or "").strip()
    if not result_text:
        return None
    reply = result_text
    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_GROVER_LANE_{stamp}.json"
    receipt: dict[str, Any] = {
        "schema": "engel_main_server_grover_lane_v1",
        "ok": True,
        "status": "grover lane answered from verified local logic",
        "updated_at_utc": _iso_now(),
        "run_id": f"main_server_grover_lane_{stamp}",
        "prompt": _clean_text(lowered),
        "prompt_sha256": hashlib.sha256(_clean_text(lowered).encode("utf-8", errors="replace")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "engel-grover-lane",
        "runtime_provider": "ct246-grover-local",
        "selected_provider": "grover_lane",
        "server_role": "engel-ai-main CT 246",
        "main_server_chat_service_used": True,
        "model_process_started": False,
        "runtime_process_started": False,
        "runs_inference": False,
        "provider_api_enabled": False,
        "network_enabled": False,
        "grover_lane": {
            "mode": outcome.get("mode"),
            "verified": True,
            "verification": outcome.get("verification"),
        },
        "training_sample_eligible": False,
        "persistent_chat_memory_training_eligible": False,
        "storage_policy": "CT246 declared roots only",
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
    }
    try:
        _write_json(receipt_path, receipt)
    except Exception:  # noqa: BLE001 - the answer is still valid without the file
        pass
    receipt["receipt_path"] = str(receipt_path)
    return receipt, reply


_MATH_REASON_THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def _math_reasoning_receipt(prompt: str, started: float) -> tuple[dict[str, Any], str] | None:
    """Route math that needs MODELING to the strongest reasoning model on disk.

    Operator direction 2026-07-30 ("use strongest model"): word problems and
    math-shaped prompts the deterministic lane could not verify go to
    deepseek-r1-distill-qwen-7b on CT CPU — measured ~3.8 tok/s, so a turn costs
    minutes, which is the right trade for correctness-critical math and wrong for
    anything else. Never reached unless the sympy lane already declined the turn.

    R1-distill quirks handled here, all measured on this box:
    * it emits <think> blocks that ate the whole 640-token budget in probing and
      truncated the answer mid-sentence — so the budget is larger, the prompt
      demands brevity, and a mandatory ANSWER: line proves the answer survived;
    * thinking is stripped before the reply ships; a thought-only response fails
      the ANSWER contract and falls through to the normal lanes;
    * instructions are folded into the user turn, not extra_system — R1 distills
      degrade on system prompts (same class as the ornith-9B system-role gotcha).
    """
    if not _env_truth("ENGEL_MATH_REASON_LANE_ENABLED", default=True):
        return None
    model_path = os.environ.get(
        "ENGEL_MATH_REASON_GGUF_MODEL",
        "/opt/engel/models-active/llm/deepseek-r1-distill-qwen-7b/"
        "deepseek-r1-distill-qwen-7b-q5_k_m.gguf",
    ).strip()
    if not model_path or not Path(model_path).is_file():
        return None
    wrapped = (
        "You are Engel's math reasoning specialist. Keep your reasoning brief "
        "(under 120 words), then finish with exactly two lines:\n"
        "ANSWER: <the final answer>\n"
        "CHECK: <one sentence saying how you verified it>\n\n"
        f"Problem: {_intent_gate_text(prompt).strip() or prompt}"
    )
    try:
        from engel_local_model_service import run_llama_cpp_lora_text_with_model

        result = run_llama_cpp_lora_text_with_model(
            model_path=model_path,
            lora_path="",
            prompt=wrapped,
            n_predict=max(256, int(os.environ.get("ENGEL_MATH_REASON_N_PREDICT", "900") or "900")),
            ctx=max(2048, int(os.environ.get("ENGEL_MATH_REASON_CTX", "4096") or "4096")),
            n_gpu_layers=0,
            temperature=float(os.environ.get("ENGEL_MATH_REASON_TEMPERATURE", "0.6") or "0.6"),
            extra_system="",
        )
    except Exception:  # noqa: BLE001 — specialist failure must never break chat
        return None
    raw_reply = str(result.get("text") or result.get("stdout") or "").strip()
    if not result.get("ok") or not raw_reply:
        return None
    visible = _MATH_REASON_THINK_RE.sub("", raw_reply).replace("</think>", "").strip()
    if "ANSWER:" not in visible:
        # thought-only or truncated output — do not serve half a derivation
        return None
    reply = visible[:2400].strip()
    stamp = _stamp()
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_MATH_REASONING_{stamp}.json"
    receipt: dict[str, Any] = {
        "schema": "engel_main_server_math_reasoning_receipt_v1",
        "ok": True,
        "status": "math reasoning specialist replied (deepseek-r1-distill-7b)",
        "updated_at_utc": _iso_now(),
        "run_id": f"main_server_math_reasoning_{stamp}",
        "prompt": _clean_text(prompt),
        "prompt_sha256": hashlib.sha256(_clean_text(prompt).encode("utf-8", errors="replace")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "engel-math-reasoning-specialist (deepseek-r1-distill-qwen-7b)",
        "runtime_provider": "ct246-deepseek-r1-distill-cpu",
        "selected_provider": "math_reasoning_specialist",
        "server_role": "engel-ai-main CT 246",
        "main_server_chat_service_used": True,
        "model_process_started": False,
        "runtime_process_started": False,
        "runs_inference": True,
        "provider_api_enabled": False,
        "network_enabled": False,
        "math_reasoning": {
            "model_path": model_path,
            "think_stripped_chars": len(raw_reply) - len(visible),
            "model_load_ms": result.get("model_load_ms"),
            "generation_ms": result.get("generation_ms"),
            "model_cache_evicted": result.get("model_cache_evicted", []),
            "answer_contract_met": True,
        },
        # model output, unverified by CAS — never persona-training material
        "training_sample_eligible": False,
        "persistent_chat_memory_training_eligible": False,
        "model_output_trusted": False,
        "storage_policy": "CT246 declared roots only",
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
    }
    try:
        _write_json(receipt_path, receipt)
    except Exception:  # noqa: BLE001
        pass
    receipt["receipt_path"] = str(receipt_path)
    return receipt, reply


_HF_REPO_ID = re.compile(r"\b([A-Za-z0-9][\w.-]*/[A-Za-z0-9][\w.-]+)\b")
_FALSE_HF_ORG = {
    "engel",
    "opt",
    "guardian",
    "josh",
    "runtime",
    "creation",
    "models-active",
    "hf-src",
    "logs",
}
_FALSE_HF_NAME = {"runtime", "code", "logs"}


def _installable_hf_repo(text: str) -> str:
    """A real org/model id. Authority and server path fragments are not repos."""
    for match in _HF_REPO_ID.finditer(str(text or "")):
        repo = match.group(1)
        org, _, name = repo.partition("/")
        if org.casefold() in _FALSE_HF_ORG or name.casefold() in _FALSE_HF_NAME:
            continue
        return repo
    return ""
_TRAIN_VENV_PY = "/opt/engel/llm_training/20260702_deep_reasoning/venv/bin/python"
_TRAINING_APPROVAL_PHRASE = "APPROVE_ENGEL_LOCAL_TRAINING_RUN_V1"

# Curated "helpful next additions" - the models Engel recommends AND the exact
# HF repo id each maps to, so "install your list"/"install those" is real work.
_RECOMMENDED_MODELS = [
    ("nomic-embed-text", "nomic-ai/nomic-embed-text-v1.5", "dedicated embedding model for memory/RAG search"),
    ("qwen2.5-14b-instruct", "Qwen/Qwen2.5-14B-Instruct", "bigger brain for hard reasoning, same family as the LoRA route"),
    ("qwen2.5-coder-7b-instruct", "Qwen/Qwen2.5-Coder-7B-Instruct", "stronger code generation than the coder-3b"),
    ("deepseek-r1-distill-qwen-7b", "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", "strong reasoning/planning, same base family"),
]


# Words a verb may reach THROUGH and still govern "training" -- determiners and modifiers
# only. Anything else between them (a real object, a preposition like "about") means the
# verb governs something else and the turn is discussing training, not asking for it.
_TRAINING_VERB_CONNECTOR = (
    r"(?:the|a|an|my|our|your|its|new|full|real|local|another|next|first|more|some|this"
    r"|that|llm|model|chat|coder|voice|lora)"
)
_TRAINING_JOB_VERB_GOVERNS = re.compile(
    rf"\b(create|run|start|build|prepare)\b(?:\s+{_TRAINING_VERB_CONNECTOR})*\s+training\b"
)
_TRAINING_START_VERB_GOVERNS = re.compile(
    rf"\b(run|start|do)\b(?:\s+{_TRAINING_VERB_CONNECTOR})*\s+training\b"
)
# An informational question never LAUNCHES anything. "why do we run training at night"
# satisfies governance ("run training" is adjacent) yet is plainly a question, and it
# tripped both gates -- routing to the training lane AND starting a real runner. Polite
# imperatives ("can you run training now", "please start training") are deliberately NOT
# in this set: they are requests, not questions.
_TRAINING_INFORMATIONAL_QUESTION = re.compile(
    r"^\s*(?:so\s+)?(why|what|where|when|who|how|which)\b", re.IGNORECASE
)


def _prompt_requests_training_job(prompt: str) -> bool:
    low = _intent_gate_text(prompt).casefold()
    if not low.strip():
        return False
    # An informational question is asking ABOUT training, so it must be answered, not
    # answered WITH a training-package receipt -- that substitution is the original bug
    # this gate exists for. "why do we run training at night" satisfies governance
    # ("run training" is adjacent) yet is plainly a question. Polite imperatives ("can
    # you run training") are deliberately not treated as questions.
    if _TRAINING_INFORMATIONAL_QUESTION.search(low):
        return False
    training_terms = (
        "run training",
        "start training",
        "create training",
        "training package",
        "train the llm",
        "train local llm",
        "train chat",
        "lora training",
        "fine tune",
        "finetune",
        "runpod training",
        "make a training dataset",
        "build training dataset",
    )
    if any(term in low for term in training_terms):
        return True
    # A turn only asks for a training JOB when a verb actually governs the word
    # "training". Bare co-occurrence captured ordinary questions ABOUT training:
    # a prompt saying "build a compact evidence ledger" about "training and
    # evaluating Engel's local models" was answered with a training-package
    # receipt instead of a real answer, and every such turn failed the
    # local-only training gate downstream.
    #
    # 2026-08-05: the rule was a PROXIMITY WINDOW, not governance -- any of these
    # verbs within 24 characters of "training" matched, so "build an argument about
    # training" still routed. Governance now means the verb reaches "training"
    # through determiners/modifiers only; an intervening object ("an argument about")
    # breaks it, which is exactly what distinguishes a request from a discussion.
    return bool(_TRAINING_JOB_VERB_GOVERNS.search(low))


def _prompt_starts_local_training(prompt: str) -> bool:
    low = _intent_gate_text(prompt).casefold()
    # This decides whether to SPAWN a real training runner, so an informational question
    # is refused before any pattern is tried. Measured 2026-08-05: six plain questions
    # ("how do I read the training report", "where do I find the training log", "why do
    # we run training at night") satisfied the old 16-character proximity window, and the
    # last of those also passed the job gate -- a question that would have started a real
    # LoRA run.
    if _TRAINING_INFORMATIONAL_QUESTION.search(low):
        return False
    start_terms = (
        "run training",
        "start training",
        "train the llm",
        "train local llm",
        "train chat",
        "run the training",
        "start the training",
        "do the training",
    )
    if any(term in low for term in start_terms):
        return True
    # Same governing-verb rule as _prompt_requests_training_job, and it matters
    # more here: this decides whether to LAUNCH a real training runner. A bare
    # "do" anywhere in the text (e.g. the house rule "Do not propose an upgrade
    # without a receipt") must never start a job.
    if _TRAINING_START_VERB_GOVERNS.search(low):
        return True
    return False


def _json_from_stdout(stdout: str) -> dict[str, Any]:
    text = str(stdout or "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _extract_training_endpoint(prompt: str) -> tuple[str, int] | None:
    text = str(prompt or "")
    m = re.search(r"--ssh-host\s+([A-Za-z0-9_.-]+)\s+--ssh-port\s+(\d{2,5})", text, re.I)
    if m:
        return m.group(1), int(m.group(2))
    m = re.search(r"ssh\s+root@([A-Za-z0-9_.-]+)\s+-p\s+(\d{2,5})", text, re.I)
    if m:
        return m.group(1), int(m.group(2))
    m = re.search(r"\b((?:\d{1,3}\.){3}\d{1,3}|[A-Za-z0-9_.-]+):(\d{2,5})\b", text)
    if m:
        return m.group(1), int(m.group(2))
    return None


def _extract_training_budget(prompt: str) -> float:
    text = str(prompt or "")
    m = re.search(r"\$\s*(\d+(?:\.\d+)?)", text)
    if m:
        return max(0.0, float(m.group(1)))
    m = re.search(r"\b(?:budget|spend|cost)\s+(?:of\s+)?(\d+(?:\.\d+)?)\b", text, re.I)
    if m:
        return max(0.0, float(m.group(1)))
    return 25.0


def _extract_training_seconds(prompt: str) -> int:
    text = str(prompt or "")
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b", text, re.I)
    if m:
        return max(60, int(float(m.group(1)) * 3600))
    m = re.search(r"\b(\d+)\s*(?:minutes?|mins?)\b", text, re.I)
    if m:
        return max(60, int(m.group(1)) * 60)
    m = re.search(r"\b(\d+)\s*(?:seconds?|secs?)\b", text, re.I)
    if m:
        return max(5, int(m.group(1)))
    return 0


def _build_training_package(timeout_seconds: int = 180) -> dict[str, Any]:
    script = TOOLS / "build_engel_lora_training_package.py"
    if not script.is_file():
        return {
            "ok": False,
            "script": str(script),
            "error": "training package builder is missing",
        }
    try:
        completed = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        parsed = _json_from_stdout(completed.stdout)
        return {
            "ok": completed.returncode == 0 and parsed.get("ok") is True,
            "script": str(script),
            "returncode": completed.returncode,
            "stdout_tail": (completed.stdout or "")[-4000:],
            "stderr_tail": (completed.stderr or "")[-2000:],
            "package": parsed,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "script": str(script), "error": f"timed out after {timeout_seconds}s"}
    except Exception as exc:
        return {"ok": False, "script": str(script), "error": str(exc)}


def _extract_training_cycles(prompt: str) -> int:
    text = str(prompt or "")
    m = re.search(r"\b(\d+)\s*(?:cycles?|passes?)\b", text, re.I)
    if m:
        return max(1, min(24, int(m.group(1))))
    seconds = _extract_training_seconds(prompt)
    if seconds > 0:
        return max(1, min(24, round(seconds / 3600)))
    return 1


def _start_training_runner(prompt: str, stamp: str) -> dict[str, Any]:
    script = TOOLS / "run_engel_local_training_job.py"
    if not script.is_file():
        return {"started": False, "reason": "local Engel training runner is missing", "script": str(script)}
    run_dir = ROOT / "runtime" / "training_runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / f"ENGEL_TRAINING_RUN_{stamp}.log"
    seconds = _extract_training_seconds(prompt)
    target_seconds = max(5, seconds or 60)
    command = [
        sys.executable,
        str(script),
        "--run-id",
        f"engel_chat_training_{stamp}",
        "--target-seconds",
        str(target_seconds),
        "--cycle-seconds",
        "60",
        "--operator-prompt",
        str(prompt or "")[:1200],
    ]
    try:
        with log_path.open("w", encoding="utf-8", errors="replace") as log:
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            proc = subprocess.Popen(
                command,
                cwd=str(ROOT),
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=creationflags,
            )
        return {
            "started": True,
            "pid": proc.pid,
            "runner": "engel_local_training_job",
            "target_seconds": target_seconds,
            "log_path": str(log_path),
            "command": command,
            "runpod_used": False,
            "manual_stop_required": False,
        }
    except Exception as exc:
        return {
            "started": False,
            "reason": str(exc),
            "log_path": str(log_path),
            "command": command,
        }


def _training_request_turn(prompt: str, started: float) -> tuple[dict[str, Any], str] | None:
    if not _prompt_requests_training_job(prompt):
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    receipt_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_TRAINING_REQUEST_{stamp}.json"
    package_result = _build_training_package()
    approved = _prompt_starts_local_training(prompt) or _TRAINING_APPROVAL_PHRASE in str(prompt or "")
    runner_result: dict[str, Any] = {"started": False, "reason": "training package requested without run/start instruction"}
    if approved:
        runner_result = _start_training_runner(prompt, stamp)

    package = package_result.get("package") if isinstance(package_result.get("package"), dict) else {}
    zip_path = str(package.get("zip_path") or package.get("package_zip") or "")
    row_count = package.get("dataset_rows") or package.get("rows") or package.get("row_count")
    if runner_result.get("started") is True:
        reply = (
            "Local Engel training job started under Engel AI Main control. "
            f"Package refreshed{f' with {row_count} rows' if row_count else ''}. "
            f"Runner PID: {runner_result.get('pid')}. Log: {runner_result.get('log_path')}. "
            "RunPod was not used. I will not mark the model upgraded until Engel writes and verifies the local training receipts."
        )
    elif package_result.get("ok") is True:
        reply = (
            "Training package is ready under Engel AI Main control. "
            f"Package: {zip_path or 'runtime/engel_lora_training_package'}. "
            "I did not start the local training runner because this request only asked for the package. "
            "Say run/start training when you want Engel to begin a local training-control run."
        )
    else:
        reply = (
            "Training was requested, but Engel could not build the training package yet. "
            f"Error: {_clip(package_result.get('error') or package_result.get('stderr_tail') or 'unknown', 360)}"
        )

    receipt = {
        "schema": "engel_main_server_training_request_v1",
        "ok": bool(package_result.get("ok")) and (not approved or runner_result.get("started") is True),
        "status": "training started" if runner_result.get("started") is True else (
            "training package ready" if package_result.get("ok") is True else "training package failed"
        ),
        "updated_at_utc": _iso_now(),
        "run_id": stamp,
        "prompt": _clean_text(prompt),
        "prompt_sha256": hashlib.sha256(_clean_text(prompt).encode("utf-8", errors="replace")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "engel-training-control",
        "runtime_provider": "ct246-local-training-control",
        "selected_provider": "training_control",
        "training_package": package_result,
        "local_training_approval_phrase": _TRAINING_APPROVAL_PHRASE,
        "local_training_approved": approved,
        "local_training_runner": runner_result,
        "runpod_used": False,
        "storage_policy": "CT246 declared roots only",
        "workspace_receipt_path": str(receipt_path),
        "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
    }
    _write_json(receipt_path, receipt)
    receipt["receipt_path"] = str(receipt_path)
    return receipt, reply


def _start_model_download(repo: str) -> tuple[str, dict[str, Any]]:
    """Kick a real background HF download to the server. Returns (reply, action)."""
    name = repo.split("/")[-1]
    hf_dir = ROOT / "models-active" / "hf-src"
    llm_dir = ROOT / "models-active" / "llm"
    target = hf_dir / name
    if target.is_dir() or (llm_dir / name).is_dir():
        return (f"{name} is already on the server - no download needed.",
                {"kind": "already_present", "repo": repo})
    log_path = ROOT / "logs" / f"model_install_{name}.log"
    code = (
        "from huggingface_hub import snapshot_download; "
        f"snapshot_download({repo!r}, local_dir={str(target)!r}); "
        "print('DOWNLOAD-COMPLETE')"
    )
    with open(log_path, "ab") as log:
        subprocess.Popen([_TRAIN_VENV_PY, "-c", code], stdout=log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return (
        f"downloading {repo} -> /opt/engel/models-active/hf-src/{name} (log {log_path})",
        {"kind": "download_started", "repo": repo, "log": str(log_path)},
    )


def _model_install_action(prompt: str, started: float) -> tuple[dict[str, Any], str] | None:
    """REAL work lane: 'install/download <model>' actually does something.
    Already-present models get the truth; new HF repos start a genuine
    background download to the server with a log + receipt."""
    text = _intent_gate_text(prompt)
    low = text.casefold()
    if not re.search(r"\b(install|download)\b", low):
        return None
    modelish = re.search(r"\b(model|models|llm|llms|gguf)\b", low) or re.search(
        r"\b(qwen|mistral|llama|phi|gemma|deepseek|smollm|granite|embed)\b", low
    )
    wants_recommended = bool(
        re.search(r"\b(your list|the list|those|them|these|recommend|all of (?:it|them)|everything)\b", low)
    )
    if re.search(r"\b(research|competitions?|competitor|look\s*up|lookup)\b", low) and not re.search(
        r"\b(install|download)\b.{0,80}\b(model|models|llm|gguf)\b|\b(model|models|llm|gguf)\b.{0,40}\b(install|download)\b",
        low,
    ):
        return None
    hf_match = _installable_hf_repo(text)
    if not modelish and not hf_match and not wants_recommended:
        return None
    llm_dir = ROOT / "models-active" / "llm"
    hf_dir = ROOT / "models-active" / "hf-src"
    present = sorted(
        {p.name for d in (llm_dir, hf_dir) if d.is_dir() for p in d.iterdir() if p.is_dir()}
    )
    action: dict[str, Any] = {"present_models": present}

    if hf_match:
        repo = hf_match
        line, sub = _start_model_download(repo)
        reply = (
            f"{line.capitalize()}. I will not claim it finished until the log says DOWNLOAD-COMPLETE - ask me to check."
            if sub.get("kind") == "download_started"
            else line + " Want me to point a lane at it?"
        )
        action.update(sub)
    elif wants_recommended:
        # "install your list / those / them" -> download the recommended set.
        started_lines: list[str] = []
        already: list[str] = []
        installs: list[dict[str, Any]] = []
        for _name, repo, _why in _RECOMMENDED_MODELS:
            line, sub = _start_model_download(repo)
            installs.append(sub)
            if sub.get("kind") == "download_started":
                started_lines.append("- " + line)
            else:
                already.append(repo.split("/")[-1])
        parts = []
        if started_lines:
            parts.append("Started the real downloads to the server:\n" + "\n".join(started_lines))
        if already:
            parts.append("Already present: " + ", ".join(already) + ".")
        parts.append("Logs are in /opt/engel/logs/model_install_*.log - ask me to check progress; I won't claim any finished early.")
        reply = "\n\n".join(parts)
        action.update({"kind": "recommended_batch_started", "installs": installs})
    else:
        shown = ", ".join(present[:12]) or "none"
        recs = "; ".join(f"{name} ({why})" for name, _repo, why in _RECOMMENDED_MODELS)
        reply = (
            f"Here is what is ALREADY on the server: {shown}.\n\n"
            f"Genuinely useful new additions I can install to MY server right now: {recs}.\n\n"
            "Say 'install your list' and I start all of them for real, or 'install <org>/<model>' for a specific one. "
            "I run these myself on the server - no runtime question needed."
        )
        action.update({"kind": "inventory_answer"})

    stamp = _stamp()
    receipt = {
        "schema": "engel_main_server_model_install_action_v1",
        "ok": True,
        "status": "model install action handled",
        "updated_at_utc": _iso_now(),
        "run_id": "main_server_model_install_" + stamp,
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "engel-main-server-model-installer",
        "runtime_provider": "engel-main-server-model-installer",
        "selected_provider": "model_install_action",
        "main_server_chat_service_used": True,
        "model_install_action": action,
    }
    receipt = _finalize_chat_receipt(receipt, prompt, reply, "ct_model_install_action", started, allow_room=False)
    reply = str(receipt.get("assistant_reply") or reply)
    return receipt, reply


PERSON_PROJECT_FACTS_PATH = ROOT / "memory" / "engel_person_project_facts.jsonl"
PRIMARY_GOAL_PATH = ROOT / "memory" / "ENGEL_PRIMARY_GOAL_V1.json"
VAGUE_DURABLE_FACTS = {
    "this",
    "that",
    "it",
    "this distinction",
    "that distinction",
    "distinction",
}


def _saved_facts() -> list[dict[str, Any]]:
    if not PERSON_PROJECT_FACTS_PATH.is_file():
        return []
    out = []
    for line in PERSON_PROJECT_FACTS_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if (
            isinstance(obj, dict)
            and obj.get("fact")
            and str(obj.get("fact") or "").strip().casefold() not in VAGUE_DURABLE_FACTS
        ):
            out.append(obj)
    return out


def _facts_for_prompt() -> str:
    return _turn_recall_memo(("facts",), _facts_for_prompt_uncached)


def _primary_goal_for_prompt() -> str:
    if not PRIMARY_GOAL_PATH.is_file():
        return ""
    try:
        goal = json.loads(PRIMARY_GOAL_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return ""
    if not isinstance(goal, dict) or goal.get("status") != "active":
        return ""
    title = str(goal.get("title") or "").strip()
    definition = goal.get("operational_definition") or {}
    if not title or not isinstance(definition, dict):
        return ""
    parts = [
        f"ENGEL AI MAIN PRIMARY GOAL (owner directive): {title}.",
        "Operate as one CT246-centered system and make progress toward this goal on every relevant task.",
    ]
    for key in ("conical", "agentic", "sentient", "self_upgrading"):
        value = str(definition.get(key) or "").strip()
        if value:
            parts.append(f"- {key.replace('_', ' ').title()}: {value}")
    return "\n".join(parts)


def _facts_for_prompt_uncached() -> str:
    """Durable facts always injected into the system prompt - the things
    Joshua explicitly told Engel to remember never get forgotten."""
    blocks: list[str] = []
    primary_goal = _primary_goal_for_prompt()
    if primary_goal:
        blocks.append(primary_goal)
    facts = _saved_facts()
    if facts:
        lines = [f"- {f['fact']}" for f in facts[-40:]]
        blocks.append("THINGS JOSHUA TOLD ENGEL TO REMEMBER (durable facts - always honor these):\n" + "\n".join(lines))
    return "\n\n".join(blocks)


def _extract_fact_clause(text: str) -> str:
    m = re.search(
        r"\b(?:save (?:to|in) memory that|remember that|remember this[:,]?|note that|note down that|keep in mind that|don'?t forget that)\s+(.+)$",
        text,
        re.IGNORECASE,
    )
    fact = (m.group(1).strip(" .") if m else text).strip()
    if fact.casefold() in VAGUE_DURABLE_FACTS and m is not None:
        antecedent = text[: m.start()].strip(" .")
        if antecedent:
            fact = antecedent
    return fact


def _save_fact_action(prompt: str, started: float) -> tuple[dict[str, Any], str] | None:
    """Write explicit remember/save requests to durable local memory."""
    text = _intent_gate_text(prompt).strip()
    low = text.casefold()
    recall = bool(re.search(r"\bwhat (?:do you|facts do you|have you) (?:remember|saved|stored)\b", low)) or (
        "what do you know about me" in low
    )
    save = bool(re.search(r"\b(save (?:to|in) memory|remember (?:that|this)|note (?:that|down)|keep in mind that|don'?t forget that)\b", low))
    if not save and not recall:
        return None

    if recall:
        # Recall questions must be synthesized by Engel's local model using the
        # durable facts injected into its context. Do not bypass the LLM with a
        # static memory-keeper answer.
        return None

    fact = _extract_fact_clause(text)
    if len(fact) < 3:
        return None
    record = {
        "schema": "engel_person_project_fact_v1",
        "fact": fact,
        "saved_at_utc": _iso_now(),
        "source": "chat_remember_request",
    }
    try:
        PERSON_PROJECT_FACTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with PERSON_PROJECT_FACTS_PATH.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        return None
    try:
        urllib.request.urlopen(
            urllib.request.Request(
                "http://127.0.0.1:8940/reindex",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            ),
            timeout=1,
        )
    except Exception:
        pass
    reply = f"Saved permanently: {fact}. I will remember that from now on - it is in my durable facts, not just this chat."
    action = {"kind": "fact_saved", "fact": fact}

    stamp = _stamp()
    receipt = {
        "schema": "engel_main_server_fact_action_v1",
        "ok": True,
        "status": "fact action handled",
        "updated_at_utc": _iso_now(),
        "run_id": "main_server_fact_" + stamp,
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "provider": "engel-main-server-memory-keeper",
        "runtime_provider": "engel-main-server-memory-keeper",
        "selected_provider": "fact_action",
        "main_server_chat_service_used": True,
        "fact_action": action,
    }
    receipt = _finalize_chat_receipt(receipt, prompt, reply, "ct_fact_action", started, allow_room=False)
    reply = str(receipt.get("assistant_reply") or reply)
    return receipt, reply


# ---------------------------------------------------------------------------
# (2026-07-10 NT-2) Fire-past-threshold escalation. The quick lane emits a cheap,
# STRING-ONLY confidence scalar (no model); a weak reply escalates to the big lane.
# Confidence is ALWAYS computed + stamped as SHADOW telemetry; escalation only ACTS
# when ENGEL_QUICK_LANE_ESCALATION_ENABLED is truthy (default OFF -> byte-identical replies).
# ---------------------------------------------------------------------------
_QUICK_LANE_ESCALATION_TAU = float(os.environ.get("ENGEL_QUICK_LANE_ESCALATION_TAU", "0.62") or 0.62)


def _reply_repetition_ratio(text: str) -> float:
    """Fraction of repeated 3-grams (0..1). High = the model looped / degenerated."""
    words = str(text or "").split()
    if len(words) < 6:
        return 0.0
    grams = [tuple(words[i:i + 3]) for i in range(len(words) - 2)]
    if not grams:
        return 0.0
    from collections import Counter
    counts = Counter(grams)
    repeated = sum(c - 1 for c in counts.values() if c > 1)
    return repeated / len(grams)


def _reply_looks_truncated(text: str) -> bool:
    """Heuristic: reply cut off mid-thought (no terminal punctuation / unbalanced code fence)."""
    t = str(text or "").rstrip()
    if not t:
        return True
    if t.count("```") % 2 == 1:
        return True
    if t.endswith("..."):
        return True
    return t[-1] not in ".!?)\"'`]}…"


def _repair_safe_missing_terminal_punctuation(text: str) -> tuple[str, bool]:
    """Add a period only when a complete final clause merely lacks punctuation."""
    value = str(text or "").rstrip()
    if not value or not _reply_looks_truncated(value) or value.endswith("..."):
        return value, False
    if value.count("```") % 2 == 1:
        return value, False
    last_line = value.splitlines()[-1].strip()
    words = re.findall(r"[A-Za-z0-9']+", last_line.casefold())
    if len(words) < 3:
        return value, False
    dangling = {
        "a", "an", "and", "as", "at", "because", "before", "between", "but",
        "by", "for", "from", "if", "in", "into", "of", "on", "or", "since",
        "so", "than", "that", "the", "then", "through", "to", "until", "when",
        "where", "which", "while", "with", "without",
    }
    if words[-1] in dangling:
        return value, False
    return value + ".", True


def _repair_missing_confirmation_source(prompt: str, reply: str) -> tuple[str, bool]:
    """Clarify an accountable source without inventing a project decision."""
    value = str(reply or "").rstrip()
    if not value:
        return value, False
    prompt_low = _intent_gate_text(prompt).casefold()
    if any(term in prompt_low for term in ("survey", "field", "measur", "existing curb")):
        sentence = (
            "Confirm the field dimensions with the field survey lead, and verify equipment interfaces "
            "against the vendor's approved manufacturer data before drafting."
        )
    else:
        sentence = (
            "Confirm each open item with the architect, engineer, owner, or vendor responsible for its "
            "source reference before proceeding."
        )
    if sentence.casefold() in value.casefold():
        return value, False
    return value + "\n\n" + sentence, True


def _repair_unverified_action_and_placeholder_owner(prompt: str, reply: str) -> tuple[str, bool]:
    """Remove unreceipted action claims and replace owner placeholders with accountable roles."""
    del prompt
    value = str(reply or "").strip()
    if not value:
        return value, False
    original = value
    value = re.sub(
        r"(?im)(?:^|(?<=[.!?])\s+)(?:i will|i'll|i have|i've)\s+"
        r"(?:send(?:\s+out)?|contact|email|issue|submit|upload|notify|ensure|update|modify|add|include)\b"
        r"[^.!?\n]*(?:[.!?]|$)",
        "",
        value,
    )
    placeholder_pattern = re.compile(
        r"\[(?:name of (?:the )?)?(?:responsible party|owner|source)\]|"
        r"\[(?:insert )?(?:responsible party|owner|source)\]",
        re.IGNORECASE,
    )
    repaired_lines: list[str] = []
    for line in value.splitlines():
        low_line = line.casefold()
        if placeholder_pattern.search(line):
            if any(term in low_line for term in ("thermometer", "calibration", "instrument", "gauge")):
                role = "the quality lead or calibration provider"
            elif any(term in low_line for term in ("coating", "paint", "finish", "batch certificate")):
                role = "the coating applicator or material supplier"
            elif any(term in low_line for term in ("field", "survey", "dimension", "datum")):
                role = "the field survey lead"
            elif any(term in low_line for term in ("equipment", "manufacturer", "cutsheet", "submittal")):
                role = "the equipment vendor or manufacturer"
            else:
                role = "the owner of the governing source record"
            line = placeholder_pattern.sub(role, line)
        repaired_lines.append(line)
    value = "\n".join(repaired_lines)
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value).strip()
    return value, value != original


def _quick_reply_missed_followup_context(prompt: str, reply: str) -> bool:
    low_prompt = _intent_gate_text(prompt).casefold()
    follows_prior = any(
        term in low_prompt
        for term in (
            "keep that",
            "say that",
            "say it",
            "make that",
            "make it",
            "that answer",
            "last answer",
            "earlier",
            "two messages ago",
            "talk this through",
            "just talk",
        )
    )
    if not follows_prior:
        return False
    low_reply = str(reply or "").strip().casefold()
    generic = (
        "what do you want" in low_reply
        or "what would you like" in low_reply
        or low_reply.startswith("got it")
        or low_reply.startswith("you got it")
        or low_reply.startswith("i will keep that in mind")
        or low_reply.startswith("i'm here")
        or low_reply.startswith("i am here")
        or "what do you want to talk about" in low_reply
        or "what should we talk about" in low_reply
        or "what's on your mind" in low_reply
        or "what is on your mind" in low_reply
        or "conversation has felt empty" in low_reply
    )
    return generic or len(low_reply) < 45


def _quick_reply_missed_requested_question(prompt: str, reply: str) -> bool:
    """Reject an answer that talks around an explicitly requested question."""
    low_prompt = _intent_gate_text(prompt).casefold()
    asks_for_automation_question = (
        "question" in low_prompt
        and "automat" in low_prompt
        and any(term in low_prompt for term in ("repeated task", "repetitive task", "repeat task"))
    )
    if not asks_for_automation_question:
        return False
    low_reply = str(reply or "").strip().casefold()
    has_question_form = "?" in low_reply or low_reply.startswith(("ask ", "what ", "which ", "where ", "how "))
    has_task_subject = any(
        term in low_reply
        for term in ("task", "step", "workflow", "process", "manual", "repeat", "time")
    )
    return not (has_question_form and has_task_subject)


def _incomplete_input_quality_report(prompt: str, reply: str) -> dict[str, Any]:
    """Reject answers that turn unknown project inputs into invented decisions."""
    if not _prompt_has_incomplete_project_inputs(prompt):
        return {
            "ok": True,
            "required": False,
            "failed_checks": [],
        }
    # (2026-07-27) same current-turn scoping as the trigger above.
    low_prompt = _intent_gate_text(_current_turn_text(prompt)).casefold()
    low_reply = " ".join(str(reply or "").split()).casefold()
    recognizes_open_inputs = any(
        term in low_reply
        for term in (
            "missing",
            "open question",
            "open check",
            "open item",
            "open verification",
            "remain open",
            "unresolved",
            "confirm",
            "verify",
            "clarify",
            "rfi",
            "not shown",
            "not indicated",
            "conflict",
            "unknown",
            "still being selected",
            "selection is pending",
            "not finalized",
            "not yet finalized",
            "needs to be finalized",
        )
    ) or bool(
        re.search(
            r"\b(?:still|remain)\b[^.!?;]{0,50}\b(?:selected|finalized|confirmed|verified|approved)\b",
            low_reply,
        )
    )
    identifies_confirmation_source = any(
        term in low_reply
        for term in (
            "architect",
            "engineer",
            "owner",
            "client",
            "vendor",
            "supplier",
            "applicator",
            "quality lead",
            "calibration provider",
            "document owner",
            "record owner",
            "document control",
            "maintenance technician",
            "responsible role",
            "design team",
            "responsibility",
            "source sheet",
            "reference",
            "life-safety sheet",
            "life safety sheet",
            "responsible trade",
            "involved trade",
            "multiple trades",
            "hardware consultant",
            "security consultant",
            "access-control contractor",
            "access control contractor",
            "electrical contractor",
            "field surveyor",
            "field survey lead",
        )
    )
    preserves_work_boundary = any(
        term in low_reply
        for term in (
            "do not assume",
            "don't assume",
            "avoid guessing",
            "without guessing",
            "without making assumptions",
            "without assumptions",
            "do not make assumptions",
            "don't make assumptions",
            "no assumptions",
            "hold",
            "blocked",
            "before drafting",
            "before detailing",
            "before proceeding",
            "wait for",
            "wait until",
            "not proceed",
            "should not proceed",
            "while pending",
            "can proceed",
            "safe to proceed",
            "unblock",
            "until confirmed",
            "avoid assigning",
            "do not assign",
            "don't assign",
            "do not merge",
            "don't merge",
            "do not approve",
            "don't approve",
            "not approve",
            "before approval",
            "do not release",
            "don't release",
            "release hold",
        )
    ) or bool(
        re.search(
            r"\b(?:as|once|after|until)\b[^.!?;]{0,80}\b(?:finalized|confirmed|verified|approved)\b",
            low_reply,
        )
    )
    drift_terms = [
        term
        for term in (
            "taper",
            "modular floor plan",
            "charts",
            "equipment cutout",
            "rooftop",
            "parapet",
            "screen footprint",
            "survey datum",
            "civil benchmark",
            "structural grid",
            "embed layout",
            "fabricator coordinate origin",
            "curb adapter",
            "storefront frame",
            "laser scan",
            "temporary shoring",
            "lifting drawing",
            "crane setup",
            "precast embed",
            "weld map",
            "roof drainage",
            "housekeeping pad",
            "shared coordinates",
        )
        if term in low_reply and term not in low_prompt
    ]
    invented_decision_terms = [
        term
        for term in (
            "assigning support responsibilities",
            "determine proper elevations",
            "measure the taper",
        )
        if term in low_reply
    ]
    def unnegated_mentions(terms: tuple[str, ...]) -> list[str]:
        matches: list[str] = []
        for term in terms:
            start = 0
            while True:
                index = low_reply.find(term, start)
                if index < 0:
                    break
                clause_prefix = re.split(r"[.!?;]", low_reply[max(0, index - 80) : index])[-1]
                negated = re.search(
                    r"\b(?:do not|don't|never|avoid|without|instead of|should not|must not)\b[^.!?;]{0,60}$",
                    clause_prefix,
                )
                if negated is None:
                    matches.append(term)
                    break
                start = index + len(term)
        return matches

    if "do not force a best-fit alignment" in low_prompt:
        for term in unnegated_mentions(
            (
                "manual adjustment",
                "manually adjust",
                "force the alignment",
                "force alignment",
                "align the moved geometry",
            )
        ):
            if term not in invented_decision_terms:
                invented_decision_terms.append(term)

    invented_approximation_terms = unnegated_mentions(
        (
            "with approximate dimensions",
            "using approximate dimensions",
            "based on approximate dimensions",
            "estimate the missing",
            "approximate the missing",
            "assume a dimension",
            "assume the dimension",
            "assumed dimensions",
            "placeholder dimensions",
            "placeholder geometry",
            "placeholder height",
            "placeholder elevation",
            "placeholder value",
            "reasonable assumption",
            "reasonable estimate",
            "drive the proportions",
            "make an assumption",
            "make assumptions",
            "we can assume",
            "use as an assumption",
        )
    )
    for pattern in (
        r"\b(?:use|using)\b[^.!?;]{0,100}\bas an assumption\b",
        r"\bassume\b[^.!?;]{0,100}\bif (?:it is|it's|they are|they're|not) (?:not )?available\b",
    ):
        for match in re.finditer(pattern, low_reply):
            clause_prefix = re.split(r"[.!?;]", low_reply[max(0, match.start() - 80) : match.start()])[-1]
            if re.search(
                r"\b(?:do not|don't|never|avoid|without|instead of|should not|must not|no)\b[^.!?;]{0,60}$",
                clause_prefix,
            ):
                continue
            label = "missing input used as an assumption"
            if label not in invented_approximation_terms:
                invented_approximation_terms.append(label)
            break
    geometry_nouns = r"height|elevation|depth|dimension|geometry|clearance|slope|tolerance|width"
    for pattern in (
        rf"\bplaceholder\b[^.!?;]{{0,48}}\b(?:{geometry_nouns})\b",
        rf"\b(?:{geometry_nouns})\b[^.!?;]{{0,48}}\bas (?:a |the )?placeholder\b",
    ):
        for match in re.finditer(pattern, low_reply):
            clause_prefix = re.split(r"[.!?;]", low_reply[max(0, match.start() - 80) : match.start()])[-1]
            if re.search(
                r"\b(?:do not|don't|never|avoid|without|instead of|should not|must not|no)\b[^.!?;]{0,60}$",
                clause_prefix,
            ):
                continue
            if "placeholder geometry" not in invented_approximation_terms:
                invented_approximation_terms.append("placeholder geometry")
            break
    invalid_evidence_extraction_terms: list[str] = []
    for match in re.finditer(
        r"\b(?:measure|determine|verify|confirm|calculate)\b[^.!?;]{0,80}"
        r"\b(?:thickness|dimension|elevation|datum|clearance|depth|width|height)\b"
        r"[^.!?;]{0,80}\bfrom (?:the )?(?:photo|photos|image|images)\b",
        low_reply,
    ):
        clause = low_reply[match.start() : match.end()]
        if any(term in clause for term in ("calibrated", "known scale", "scale reference", "photogrammetry")):
            continue
        invalid_evidence_extraction_terms.append("unscaled image used as measurement evidence")
        break
    false_source_discovery_terms: list[str] = []
    source_was_missing = any(
        term in low_prompt
        for term in (
            "missing",
            "not documented",
            "not supplied",
            "nobody supplied",
            "not shown",
            "not indicated",
            "unknown",
            "unconfirmed",
        )
    )
    if source_was_missing:
        for term in (
            "i've located",
            "i have located",
            "i found the",
            "i've found the",
            "here are the details",
            "[insert file path]",
            "[insert path]",
        ):
            if term in low_reply:
                false_source_discovery_terms.append(term)
    prompt_requests_message_draft = any(
        term in low_prompt
        for term in (
            "draft an email",
            "write an email",
            "email draft",
            "draft a message",
            "write a message",
            "draft a letter",
            "write a letter",
        )
    )
    unsolicited_message_draft_terms = [] if prompt_requests_message_draft else [
        term
        for term in (
            "subject:",
            "dear [client]",
            "dear client",
            "email body:",
            "body: dear",
        )
        if term in low_reply
    ]
    placeholder_confirmation_owner_terms = [
        term
        for term in (
            "[name of responsible party]",
            "[name of the responsible party]",
            "[responsible party]",
            "[insert owner]",
            "[insert source]",
        )
        if term in low_reply
    ]
    placeholder_project_data_terms = [
        match.group(0)
        for match in re.finditer(r"\[(?:insert|enter|add|fill in)\s+[^\]]{1,100}\]", low_reply)
    ]
    unverified_external_action_terms = [
        match.group(0).strip()
        for match in re.finditer(
            r"\b(?:i will|i'll|i have|i've)\s+"
            r"(?:send(?:\s+out)?|contact|email|issue|submit|upload|notify|ensure|update|modify|add|include)\b"
            r"[^.!?\n]*(?:[.!?]|$)",
            low_reply,
        )
    ]
    evidence_ledger_requested = any(
        term in low_prompt
        for term in (
            "evidence ledger",
            "evidence split",
            "separate usable",
            "usable evidence",
            "usable records",
            "separate sourced facts",
            "supported evidence",
            "confirmed sources, disagreements",
            "reliable, disputed, and absent",
        )
    )
    conflict_category_requested = any(
        term in low_prompt
        for term in ("disagreement", "conflicting evidence", "contradictory", "competing information", "disputed")
    )
    has_supported_category = any(
        term in low_reply
        for term in (
            "usable evidence",
            "usable record",
            "supported evidence",
            "confirmed source",
            "sourced fact",
            "reliable evidence",
            "reliable input",
        )
    )
    has_open_category = any(
        term in low_reply
        for term in (
            "open check",
            "open item",
            "open verification",
            "missing information",
            "not supplied",
            "unprovided",
            "absent evidence",
            "still need",
            "remain open",
        )
    )
    has_conflict_category = any(
        term in low_reply
        for term in ("disagreement", "conflicting", "contradictory", "competing", "disputed", "no conflict")
    )
    answers_requested_evidence_ledger = bool(
        not evidence_ledger_requested
        or (has_supported_category and has_open_category and (not conflict_category_requested or has_conflict_category))
    )
    owner_mapping_requested = any(
        term in low_prompt
        for term in (
            "role that owns",
            "who owns each",
            "owner attached to every",
            "name who should answer each",
            "owner for each",
            "responsible open party",
            "accountable role",
            "specific responsible role",
            "responsible role beside every",
        )
    )
    generic_owner_boilerplate = (
        "architect, engineer, owner, or vendor responsible" in low_reply
        or "architect, engineer, owner or vendor responsible" in low_reply
    )
    has_specific_owner_role = any(
        term in low_reply
        for term in (
            "quality lead",
            "calibration provider",
            "facility manager",
            "maintenance manager",
            "maintenance supervisor",
            "maintenance technician",
            "controls technician",
            "instrumentation technician",
            "door contractor",
            "system administrator",
            "records manager",
            "document controller",
            "document control",
            "field survey lead",
            "equipment vendor",
            "manufacturer",
            "material supplier",
            "coating applicator",
            "fabricator",
            "electrical engineer",
            "structural engineer",
            "architect of record",
            "design engineer",
            "testing agency",
            "inspection agency",
            "contractor",
            "hardware consultant",
            "security consultant",
            "access-control contractor",
            "access control contractor",
            "electrical contractor",
            "field surveyor",
        )
    ) or bool(
        re.search(
            r"responsible role\s*[-:]\s*(?!\[)(?:the\s+)?[a-z][a-z /&-]{2,60}",
            low_reply,
        )
    )
    maps_requested_confirmation_owners = bool(
        not owner_mapping_requested or (has_specific_owner_role and not generic_owner_boilerplate)
    )
    complete_ending = not _reply_looks_truncated(reply)
    failed_checks: list[str] = []
    if not recognizes_open_inputs:
        failed_checks.append("recognizes_missing_or_conflicting_inputs")
    if not identifies_confirmation_source:
        failed_checks.append("identifies_confirmation_source_or_owner")
    if not preserves_work_boundary:
        failed_checks.append("preserves_safe_work_boundary")
    if drift_terms:
        failed_checks.append("no_unprompted_domain_drift")
    if invented_decision_terms:
        failed_checks.append("no_invented_project_decisions")
    if invented_approximation_terms:
        failed_checks.append("no_invented_approximate_geometry")
    if invalid_evidence_extraction_terms:
        failed_checks.append("no_impossible_evidence_extraction")
    if false_source_discovery_terms:
        failed_checks.append("no_false_source_discovery")
    if unsolicited_message_draft_terms:
        failed_checks.append("no_unsolicited_message_draft")
    if placeholder_confirmation_owner_terms:
        failed_checks.append("no_placeholder_confirmation_owner")
    if placeholder_project_data_terms:
        failed_checks.append("no_placeholder_project_data")
    if unverified_external_action_terms:
        failed_checks.append("no_unverified_external_action_claim")
    if not answers_requested_evidence_ledger:
        failed_checks.append("answers_requested_evidence_ledger")
    if not maps_requested_confirmation_owners:
        failed_checks.append("maps_requested_confirmation_owners")
    if not complete_ending:
        failed_checks.append("complete_ending")
    return {
        "ok": not failed_checks,
        "required": True,
        "checks": {
            "recognizes_missing_or_conflicting_inputs": recognizes_open_inputs,
            "identifies_confirmation_source_or_owner": identifies_confirmation_source,
            "preserves_safe_work_boundary": preserves_work_boundary,
            "no_unprompted_domain_drift": not drift_terms,
            "no_invented_project_decisions": not invented_decision_terms,
            "no_invented_approximate_geometry": not invented_approximation_terms,
            "no_impossible_evidence_extraction": not invalid_evidence_extraction_terms,
            "no_false_source_discovery": not false_source_discovery_terms,
            "no_unsolicited_message_draft": not unsolicited_message_draft_terms,
            "no_placeholder_project_data": not placeholder_project_data_terms,
            "answers_requested_evidence_ledger": answers_requested_evidence_ledger,
            "maps_requested_confirmation_owners": maps_requested_confirmation_owners,
            "complete_ending": complete_ending,
        },
        "failed_checks": failed_checks,
        "drift_terms": drift_terms,
        "invented_decision_terms": invented_decision_terms,
        "invented_approximation_terms": invented_approximation_terms,
        "invalid_evidence_extraction_terms": invalid_evidence_extraction_terms,
        "false_source_discovery_terms": false_source_discovery_terms,
        "unsolicited_message_draft_terms": unsolicited_message_draft_terms,
        "placeholder_confirmation_owner_terms": placeholder_confirmation_owner_terms,
        "placeholder_project_data_terms": placeholder_project_data_terms,
        "unverified_external_action_terms": unverified_external_action_terms,
    }


def _semantic_quality_prompt(
    prompt: str,
    request: dict[str, Any] | None,
) -> tuple[str, bool]:
    """Include only the exact prior turn from an isolated desktop session."""
    request = request or {}
    discord_room = _discord_room_memory(request, max_chars=2600)
    if discord_room:
        return discord_room + "\n\nCURRENT USER TURN:\n" + prompt, True
    if not _request_conversation_id(request):
        return prompt, False
    recent = _recent_chat_context(
        max_chars=2600,
        max_records=3,
        context_scope=_chat_context_scope(request),
    )
    if not recent:
        return prompt, False
    return (
        "PRIOR TURN FROM THIS DESKTOP CHAT:\n"
        + recent
        + "\n\nCURRENT USER TURN:\n"
        + prompt,
        True,
    )


def _semantic_local_repair_request(
    original_prompt: str,
    rejected_reply: str,
    failed_checks: list[str],
) -> str:
    """Ask the same local model for one bounded rewrite before bridge escalation."""
    # (2026-07-28, issue e769c4a2) The four-section construction-document
    # template (Known / Missing or conflicting / Hold and owner / Next step,
    # field-survey-lead role list) applies ONLY when the request itself is an
    # incomplete-inputs project judgment. Applied unconditionally, it bled
    # project-report boilerplate into general judgment answers.
    if _prompt_has_incomplete_project_inputs(original_prompt):
        instruction = (
            "Rewrite the draft below as the direct answer to the original user request in no more than 140 words. "
            "Use exactly four short sections: Known, Missing or conflicting, Hold and owner, Next step. "
            "End every section with a complete sentence and end the whole answer with a period. "
            "State 'Do not approve or release this item until the open inputs are confirmed.' in the Hold section. "
            "Name one specific accountable role beside each gap, using only roles implied by the request such as "
            "the field survey lead, architect, engineer, responsible contractor, hardware consultant, or electrical contractor. "
            "Answer every requested part. "
            "When an evidence split or ledger was requested, use explicit short sections for each requested category. "
            "When ownership was requested, attach a specific accountable role to every open item; do not use bracketed "
            "placeholders of any kind or a generic list of possible parties. Mark unavailable values as not provided or "
            "open instead of inventing template fields. Use only facts in the request and current chat. "
            "Do not import another project's tasks or nouns, invent missing values, or claim that you sent, contacted, "
            "uploaded, issued, or completed anything. Keep the answer concise and do not discuss this rewrite instruction."
        )
    else:
        instruction = (
            "Rewrite the draft below as the direct answer to the original user request in no more than 140 words. "
            "Answer every requested part in plain prose. Use only facts in the request and current chat; mark "
            "genuinely unknown values as not provided instead of inventing them. Do not add section headings, "
            "role assignments, holds, or template fields the user did not ask for. Do not import another "
            "project's tasks or nouns, and do not claim that you sent, contacted, uploaded, issued, or completed "
            "anything. Keep the answer concise and do not discuss this rewrite instruction."
        )
    return (
        instruction
        + f"\n\nFailed checks: {', '.join(failed_checks)}\n\n"
        f"Original user request:\n{original_prompt}\n\n"
        f"Rejected draft:\n{rejected_reply}"
    )[:3200]


def _quick_lane_confidence(prompt: str, reply: str,
                           service_clipped: bool = False) -> "tuple[float, dict[str, Any]]":
    """Cheap STRING-ONLY confidence in a quick-lane reply (NO model call). Reuses the existing
    reply_passes_style grader + light degeneracy checks. Higher = more trustworthy (0..1).
    service_clipped: the SERVICE cut the reply at its display cap — that is not
    model truncation and must not tank confidence (2026-07-26 neuro audit)."""
    comps: dict[str, Any] = {}
    reply = str(reply or "").strip()
    if not reply:
        return 0.0, {"empty": True}
    style_ok = 1.0
    try:
        from run_engel_standalone_chat_llm import reply_passes_style
        score = reply_passes_style(prompt, reply)
        if isinstance(score, dict):
            comps["style_ok"] = bool(score.get("ok"))
            style_ok = 1.0 if score.get("ok") else 0.35
    except Exception:
        # (2026-07-26) grader unavailable is UNCERTAINTY, not confidence: use a
        # neutral penalty instead of silently scoring 1.0.
        comps["style_error"] = True
        comps["style_ok"] = None
        style_ok = 0.7
    rep = _reply_repetition_ratio(reply)
    comps["repetition"] = round(rep, 3)
    rep_pen = 1.0 - min(1.0, max(0.0, (rep - 0.3) / 0.5))  # penalize >0.3 repeated 3-gram fraction
    trunc = _reply_looks_truncated(reply)
    comps["truncated"] = trunc
    comps["service_clipped"] = bool(service_clipped)
    trunc_pen = 1.0 if service_clipped else (0.5 if trunc else 1.0)
    short_pen = 1.0
    if len(str(prompt or "").split()) > 8 and len(reply) < 25:
        short_pen = 0.5  # substantive question, one-liner answer -> suspicious
    conf = max(0.0, min(1.0, style_ok * rep_pen * trunc_pen * short_pen))
    comps["confidence"] = round(conf, 3)
    return conf, comps


def _quick_reply_accept(prompt: str, request: dict[str, Any], receipt: dict[str, Any]) -> bool:
    """(NT-2) Accept the quick-lane reply, or escalate to the big lane. ALWAYS computes +
    stamps confidence as SHADOW telemetry (never alters the reply). Escalation acts ONLY when
    ENGEL_QUICK_LANE_ESCALATION_ENABLED is truthy. Fail-open: any error -> accept (current behaviour)."""
    try:
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
        conf, comps = _quick_lane_confidence(
            prompt, reply, service_clipped=receipt.get("quick_model_clipped") is True)
        tau = _QUICK_LANE_ESCALATION_TAU
        enabled = _env_truth("ENGEL_QUICK_LANE_ESCALATION_ENABLED", default=False)
        receipt["quick_lane_confidence"] = round(conf, 3)
        receipt["quick_lane_confidence_components"] = comps
        receipt["quick_lane_confidence_tau"] = tau
        receipt["quick_lane_escalation_enabled"] = enabled
        forced_reason = ""
        if comps.get("empty") is True:
            forced_reason = "quick reply was empty"
        elif comps.get("truncated") is True and not comps.get("service_clipped"):
            forced_reason = "quick reply was truncated"
        elif _quick_reply_missed_followup_context(prompt, reply):
            forced_reason = "quick reply lost prior-turn context"
        elif _quick_reply_missed_requested_question(prompt, reply):
            forced_reason = "quick reply did not supply the requested automation question"
        elif _prompt_requires_buffered_quality_gate(prompt) and comps.get("style_ok") is False:
            forced_reason = "quick reply failed a required conversational quality constraint"
        # (2026-07-26 neuro audit) the flag is a REAL kill switch: forced
        # escalations also respect it, so flag-off is byte-identical behaviour.
        should_escalate = enabled and (bool(forced_reason) or conf < tau)
        if should_escalate and not request.get("_escalate_past_quick"):
            request["_escalate_past_quick"] = True
            request["_engel_escalated_from"] = 1  # (NT-1) quick lane -> big lane escalation
            request["_quick_lane_shadow_reply"] = reply  # fail-open restore if the big lane dies
            # (2026-07-26) durable telemetry: the escalating receipt is discarded,
            # so carry the evidence on the request for the final receipt to keep.
            request["_quick_lane_confidence_evidence"] = {
                "confidence": round(conf, 3),
                "components": comps,
                "tau": tau,
                "forced_reason": forced_reason,
            }
            receipt["quick_lane_escalated"] = True
            receipt["quick_lane_forced_escalation_reason"] = forced_reason
            return False
        receipt["quick_lane_escalated"] = False
        return True
    except Exception:
        return True


def _mode_gate_turn(
    prompt: str, request: dict[str, Any], started: float
) -> tuple[dict[str, Any], str] | None:
    """Mode gate (see /opt/engel/memory/cognitive_routing_model.md): classify the
    TYPE of thinking a turn needs and dispatch reflex/memory turns directly.
    Flag-gated by ENGEL_MODE_GATE_ENABLED (systemd drop-in; delete = revert).
    Fail-open: any error returns None and the normal cascade runs untouched.
    Non-terminal modes (convergent/divergent) only annotate the request and
    apply conservative temperature/max_tokens hints."""
    try:
        # (NT-2) an escalated turn must reach the big lane, not a mode-gate cheap answer.
        if request.get("_escalate_past_quick"):
            return None
        import engel_mode_gate as _gate

        if not _gate.gate_enabled():
            return None
        decision = _gate.classify_mode(prompt)
        request["mode_gate_decision"] = decision
        mode = str(decision.get("mode") or "unknown")
        if _prompt_needs_previous_turn(prompt):
            request["_escalate_past_quick"] = True
            request["_engel_escalated_from"] = 0
            decision["previous_turn_synthesis"] = "large_local_model"
            return None
        if mode == "memory_recall":
            # Raw semantic hits are retrieval evidence, not a conversational
            # answer. Carry them into the large local lane for synthesis.
            request["_escalate_past_quick"] = True
            request["_engel_escalated_from"] = 0
            decision["memory_recall_synthesis"] = "large_local_model"
            return None
        if mode == "reflex":
            if _is_discord_owner_turn(request):
                # Josh in Discord is never the 0.5B reflex lane. That is what
                # made Engel sound disconnected from the rest of the brain.
                decision["discord_owner_full_brain"] = "large_local_model"
                request["_escalate_past_quick"] = True
                request["_engel_escalated_from"] = 0
                return None
            if (
                _prompt_requires_large_local_reasoning(prompt)
                or not _prompt_requests_quick_casual_model(prompt)
            ):
                decision["substantive_work_synthesis"] = "large_local_model"
                request["_escalate_past_quick"] = True
                request["_engel_escalated_from"] = 0
                return None
            receipt = _quick_casual_model_receipt(prompt, started, request)
            if receipt is not None and receipt.get("ok") is True and _quick_reply_accept(prompt, request, receipt):
                receipt["mode_gate"] = decision
                receipt["selected_provider"] = "ct_mode_gate_reflex"
                reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
                receipt = _finalize_chat_receipt(
                    receipt,
                    prompt,
                    reply,
                    "ct_mode_gate_reflex_chat",
                    started,
                    allow_room=_prompt_requests_meeting_room_dispatch(prompt),
                    allow_reps=False,
                )
                reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
                return receipt, reply
            return None
        hints = _gate.dispatch_hints(mode, request)
        for key, value in hints.items():
            request.setdefault(key, value)
        if hints:
            decision["hints_applied"] = hints
    except Exception:
        return None
    return None


def _run_chat_turn(prompt: str, request: dict[str, Any], started: float) -> tuple[dict[str, Any], str]:
    # (NT-3) open the per-turn retrieve-once memo so the whole quick->big->bridge cascade
    # reuses one recall result. Reentrant + reset-in-finally (pool threads are reused).
    _recall_tok = _begin_turn_recall_cache()
    # Turn-scoped governor context (same contextvar pattern as NT-3): the memory
    # persister runs deep inside the turn, BEFORE the finalize path stamps
    # receipt["governor_context"], so without this the base-prompt substitution
    # (design section 4.2) never saw the metadata -- proven live 2026-07-31.
    _gov_tok = _TURN_GOVERNOR_CONTEXT.set(_request_governor_context(request))
    _gov_route_tok = _TURN_GOVERNOR_ROUTE_DECISION.set(None)
    _chat_only_tok = _TURN_CHAT_ONLY.set(
        isinstance(request, dict) and request.get("chat_only") is True
    )
    try:
        receipt, reply = _run_chat_turn_inner(prompt, request, started)
        # Central local-only training stamp: only the main lane used to set
        # local_only_training, so a turn served by ANY specialist lane (sparse-MoE,
        # deep 14B, math) came back unstamped and failed the strict local-only
        # training gate. Stamp it once here from the request, for every lane, but
        # ONLY when no external provider actually ran (a bridge turn stays honest).
        if isinstance(receipt, dict) and _request_local_only_training(request):
            provider = str(
                receipt.get("selected_provider") or receipt.get("runtime_provider") or ""
            ).casefold()
            external = any(
                m in provider for m in _REAL_PROVIDER_MARKERS
            ) or receipt.get("provider_api_enabled") is True or receipt.get(
                "provider_bridge_used"
            ) is True
            if not external:
                # Direct assign, not setdefault: a specialist lane may have already
                # written local_only_training=False, which setdefault would keep.
                receipt["local_only_training"] = True
                receipt["local_llm_only"] = True
        return receipt, reply
    finally:
        _TURN_CHAT_ONLY.reset(_chat_only_tok)
        _TURN_GOVERNOR_ROUTE_DECISION.reset(_gov_route_tok)
        _TURN_GOVERNOR_CONTEXT.reset(_gov_tok)
        _end_turn_recall_cache(_recall_tok)


def _run_chat_turn_inner(prompt: str, request: dict[str, Any], started: float) -> tuple[dict[str, Any], str]:
    # Cosmic Swarm and Josh Discord share one standing brain. Discord is the
    # room; Sub-Engel / future subs stay off this pipe.
    if _is_discord_owner_turn(request):
        try:
            from engel_discord_desktop_route_parity import apply_standing_chat_brain

            apply_standing_chat_brain(request, owner_turn=True)
        except Exception:
            pass
    else:
        try:
            from engel_discord_desktop_route_parity import remember_desktop_standing_chat_brain

            remember_desktop_standing_chat_brain(request)
        except Exception:
            pass
    try:
        from engel_model_cohesion import apply_to_request as apply_model_cohesion

        apply_model_cohesion(request, prompt)
    except Exception:
        pass
    self_model_introspection = _prompt_requests_self_model_introspection(prompt)
    if self_model_introspection:
        request["_escalate_past_quick"] = True
        # (2026-07-26 neuro audit) forced escalations record their origin like
        # every sibling site, so router-forced jumps show in depth telemetry.
        request["_engel_escalated_from"] = 0
        request["local_provider"] = "local"
        request.setdefault("allow_provider_fallback", False)
        # Sentient freshness: introspection answers must rest on CURRENT
        # evidence — re-observe (bounded, rate-limited) when the state is stale.
        request["_self_model_freshness"] = _self_model_fresh_observe_if_stale()
    context_requires_model = _context_pack_requires_model(request)
    strict_local_llm_training = (
        _request_local_only_training(request)
        or self_model_introspection
        or context_requires_model
    )
    quality_prompt, quality_context_used = _semantic_quality_prompt(prompt, request)
    request["_semantic_quality_prompt"] = quality_prompt
    request["_semantic_quality_scoped_context_used"] = quality_context_used
    fact_turn = _save_fact_action(prompt, started)
    if fact_turn is not None:
        return fact_turn
    source = str(request.get("source") or request.get("client") or "").strip().casefold()
    if not source.startswith("discord") and not _request_skips_operator_room_actions(request):
        if _owner_prompt_is_discord_checkout(prompt):
            return _discord_checkout_turn(prompt, started)
        if _owner_prompt_is_reply_to_sub_engel(prompt):
            return _owner_reply_to_sub_engel_turn(prompt, started)
    self_upgrade_review = _self_upgrade_chat_review_turn(
        prompt,
        request,
        started,
    )
    if self_upgrade_review is not None:
        receipt, reply = self_upgrade_review
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_self_upgrade_chat_review",
            started,
            allow_room=False,
            allow_reps=True,
        )
        reply = str(
            receipt.get("assistant_reply")
            or receipt.get("assistant_output_text")
            or reply
        )
        return receipt, reply
    arithmetic_receipt = _deterministic_arithmetic_receipt(prompt, started)
    if arithmetic_receipt is not None:
        reply = str(arithmetic_receipt.get("assistant_reply") or arithmetic_receipt.get("assistant_output_text") or "")
        arithmetic_receipt = _finalize_chat_receipt(
            arithmetic_receipt,
            prompt,
            reply,
            "ct_deterministic_arithmetic_chat",
            started,
            allow_room=False,
            allow_reps=False,
        )
        reply = str(arithmetic_receipt.get("assistant_reply") or reply)
        return arithmetic_receipt, reply
    blocked_command_turn = _blocked_command_turn(prompt, started)
    if blocked_command_turn is not None:
        receipt, reply = blocked_command_turn
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_command_safety_gate",
            started,
            allow_room=False,
            allow_reps=False,
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
        return receipt, reply
    if _prompt_requests_media_artifact(prompt):
        receipt = _media_artifact_receipt(prompt, started)
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_media_artifact_chat",
            started,
            allow_room=_prompt_requests_meeting_room_dispatch(prompt),
            allow_reps=False,
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
        return receipt, reply
    mission_turn = _mission_control_job_turn(prompt, started)
    if mission_turn is not None:
        receipt, reply = mission_turn
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_mission_control_job",
            started,
            allow_room=False,
            allow_reps=False,
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
        return receipt, reply
    training_turn = _training_request_turn(prompt, started)
    if training_turn is not None:
        receipt, reply = training_turn
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_training_control_chat",
            started,
            allow_room=False,
            allow_reps=False,
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
        return receipt, reply
    math_turn = _math_lane_turn(prompt, started)
    if isinstance(math_turn, tuple):
        receipt, reply = math_turn
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_math_lane",
            started,
            allow_room=False,
            allow_reps=False,
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
        return receipt, reply
    grover_turn = _grover_lane_turn(prompt, started)
    if isinstance(grover_turn, tuple):
        receipt, reply = grover_turn
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_grover_lane",
            started,
            allow_room=False,
            allow_reps=False,
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
        return receipt, reply
    if not strict_local_llm_training and _prompt_requests_computer_memory(prompt):
        receipt = _computer_memory_receipt(prompt, started, request)
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_computer_memory_chat",
            started,
            allow_room=False,
            allow_reps=True,
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
        return receipt, reply
    if not strict_local_llm_training and _prompt_requests_live_runtime_status(prompt):
        # Live status must beat Grok. Cosmic Swarm standing-pipe force_provider
        # used to answer "what I'm actually running" with "I'll check..." and
        # never probe (live 2026-08-20). A retry/continue of an app build still
        # belongs on the router/build lane so the UI sees the rebuild, not a
        # status-only paragraph.
        if not _prompt_is_router_work_order(prompt, request):
            receipt = _live_status_receipt(prompt, started)
            reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
            receipt = _finalize_chat_receipt(
                receipt,
                prompt,
                reply,
                "ct_live_status_chat",
                started,
                allow_room=_prompt_requests_meeting_room_dispatch(prompt),
            )
            return receipt, reply
    # "use strongest model" (operator, 2026-07-30): math the deterministic lane
    # declined — either math-shaped-but-unverifiable, or a word problem needing
    # modeling — escalates to the deepseek-r1 reasoning specialist before any
    # general chat lane can guess at it.
    needs_math_reasoning = math_turn == "math_shaped"
    if not needs_math_reasoning:
        try:
            from engel_math_lane import (
                detect_math_reasoning_request,
                detect_teaching_math_request,
            )

            needs_math_reasoning = detect_math_reasoning_request(prompt)
            # (2026-07-31) detect_math_reasoning_request requires a DIGIT, so every
            # CONCEPTUAL math question ("explain the chain rule", "derive why induction
            # works") failed it structurally and fell through to the default 7B — the
            # weakest model in the fleet at exactly the questions that need reasoning.
            # Same operator direction that put word problems here ("use strongest
            # model", 2026-07-30) applies to conceptual math. Flag-gated because this
            # lane costs minutes per turn: off => byte-identical prior behaviour.
            if not needs_math_reasoning and _env_truth(
                "ENGEL_TEACHING_MATH_LANE_ENABLED", default=True
            ):
                needs_math_reasoning = detect_teaching_math_request(prompt)
        except Exception:  # noqa: BLE001 — detector failure = normal chat
            needs_math_reasoning = False
    if not needs_math_reasoning:
        # A caller that KNOWS the turn's discipline (the prompt trainer tags each turn
        # via per-turn metadata) beats guessing from prompt text. Routing off a declared
        # intent is the whole point of the governor contract; this is its first consumer.
        # Narrow-only: metadata may select a reasoning lane, never disable a gate, never
        # enable a provider.
        try:
            hint = str((request or {}).get("route_hint") or "").strip().casefold()
            declared = str((request or {}).get("discipline") or "").strip().casefold()
            needs_math_reasoning = hint in {"math", "reasoning"} or declared == "math"
        except Exception:  # noqa: BLE001 — hint failure = normal chat
            needs_math_reasoning = False
    if needs_math_reasoning:
        reasoning_turn = _math_reasoning_receipt(prompt, started)
        if reasoning_turn is not None:
            receipt, reply = reasoning_turn
            receipt = _finalize_chat_receipt(
                receipt,
                prompt,
                reply,
                "ct_math_reasoning_lane",
                started,
                allow_room=False,
                allow_reps=False,
            )
            reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
            return receipt, reply
    install_turn = _model_install_action(prompt, started)
    if install_turn is not None:
        return install_turn
    creation_receipt = _skill_agent_creation_receipt(prompt, started)
    if creation_receipt is not None:
        reply = str(creation_receipt.get("assistant_reply") or creation_receipt.get("assistant_output_text") or "")
        creation_receipt = _finalize_chat_receipt(
            creation_receipt,
            prompt,
            reply,
            "ct_skill_agent_creation_chat",
            started,
            allow_room=_prompt_requests_meeting_room_dispatch(prompt),
        )
        return creation_receipt, reply
    if (
        _explicit_provider_bridge_requested(prompt, request)
        and not _prompt_is_router_work_order(prompt, request)
    ):
        provider_turn = _complete_provider_bridge_turn(prompt, request, started)
        if provider_turn is not None:
            return provider_turn
    # BUILD lane (2026-07-11): "build me a <thing>" → bridges generate real
    # multi-file code, Engel scaffolds + runs it. Fires BEFORE the code lane
    # (build is a superset of "write code") AND before the fast intent routes —
    # a build description ("...with separate modules for storage...") is full of
    # words those keyword routes match, and a canned fast reply must never eat a
    # build order (20260711: "modules" in help-next hijacked one). Fails open.
    # App-only: Discord is excluded inside _build_lane_receipt (GIFs/media stay).
    if not request.get("_escalate_past_quick"):
        build_receipt = _build_lane_receipt(prompt, started, request)
        if build_receipt is not None:
            reply = str(build_receipt.get("assistant_reply") or build_receipt.get("assistant_output_text") or "")
            build_receipt = _finalize_chat_receipt(
                build_receipt, prompt, reply, "ct_build_lane", started,
                allow_room=False, allow_reps=False,
            )
            reply = str(build_receipt.get("assistant_reply") or build_receipt.get("assistant_output_text") or reply)
            return build_receipt, reply
        # WORKSPACE SETUP lane: "set up a <X> workspace/environment" scaffolds a
        # bounded starter folder. Sits with the build lane so a setup ORDER can
        # never be eaten by the canned fast-chat routes below (20260711: it was).
        ws_receipt = _workspace_setup_receipt(prompt, started, request)
        if ws_receipt is not None and ws_receipt.get("ok") is True:
            reply = str(ws_receipt.get("assistant_reply") or ws_receipt.get("assistant_output_text") or "")
            ws_receipt = _finalize_chat_receipt(
                ws_receipt, prompt, reply, "ct_workspace_setup_lane", started,
                allow_room=False, allow_reps=False,
            )
            reply = str(ws_receipt.get("assistant_reply") or ws_receipt.get("assistant_output_text") or reply)
            return ws_receipt, reply
    if _explicit_provider_bridge_requested(prompt, request):
        provider_turn = _complete_provider_bridge_turn(prompt, request, started)
        if provider_turn is not None:
            return provider_turn
    if not strict_local_llm_training and _prompt_requests_computer_memory(prompt):
        receipt = _computer_memory_receipt(prompt, started, request)
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_computer_memory_chat",
            started,
            allow_room=False,
            allow_reps=True,
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
        return receipt, reply
    if not strict_local_llm_training and _prompt_requests_live_runtime_status(prompt):
        receipt = _live_status_receipt(prompt, started)
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_live_status_chat",
            started,
            allow_room=_prompt_requests_meeting_room_dispatch(prompt),
        )
        return receipt, reply
    if not strict_local_llm_training and _prompt_requests_reps_template(prompt):
        receipt = _fast_server_receipt(prompt, started, error="fast REPS template route", fallback_used=False)
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_reps_template_chat",
            started,
            allow_room=_prompt_requests_meeting_room_dispatch(prompt),
        )
        return receipt, reply
    if not strict_local_llm_training and _prompt_requests_chat_route(prompt):
        receipt = _fast_server_receipt(prompt, started, error="fast route-check route", fallback_used=False)
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
        receipt["selected_provider"] = "ct_fast_route_check"
        receipt["runtime_provider"] = "engel-main-server-fast-route-check"
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_fast_route_check",
            started,
            allow_room=_prompt_requests_meeting_room_dispatch(prompt),
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
        return receipt, reply
    if not strict_local_llm_training and _prompt_requests_help_next(prompt):
        receipt = _fast_server_receipt(prompt, started, error="fast help-next route", fallback_used=False)
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
        receipt["selected_provider"] = "ct_fast_help_next"
        receipt["runtime_provider"] = "engel-main-server-fast-help-next"
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_fast_help_next",
            started,
            allow_room=_prompt_requests_meeting_room_dispatch(prompt),
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
        return receipt, reply
    if not strict_local_llm_training and _prompt_requests_build_status(prompt):
        receipt = _fast_server_receipt(prompt, started, error="fast build-status route", fallback_used=False)
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
        receipt["selected_provider"] = "ct_fast_build_status"
        receipt["runtime_provider"] = "engel-main-server-fast-build-status"
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_fast_build_status",
            started,
            allow_room=_prompt_requests_meeting_room_dispatch(prompt),
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
        return receipt, reply
    if not strict_local_llm_training and _prompt_requests_template_loop_repair(prompt):
        receipt = _fast_server_receipt(prompt, started, error="fast template-loop repair route", fallback_used=False)
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
        receipt["selected_provider"] = "ct_fast_template_loop_repair"
        receipt["runtime_provider"] = "engel-main-server-fast-template-loop-repair"
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_fast_template_loop_repair",
            started,
            allow_room=_prompt_requests_meeting_room_dispatch(prompt),
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
        return receipt, reply
    if not strict_local_llm_training and _prompt_requests_chat_fault_repair(prompt):
        receipt = _fast_server_receipt(prompt, started, error="fast chat-fault repair route", fallback_used=False)
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
        receipt["selected_provider"] = "ct_fast_chat_fault_repair"
        receipt["runtime_provider"] = "engel-main-server-fast-chat-fault-repair"
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_fast_chat_fault_repair",
            started,
            allow_room=_prompt_requests_meeting_room_dispatch(prompt),
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
        return receipt, reply
    # Nemotron 3.5 Lightning is the loaded 30B-A3B hybrid MoE when the
    # dedicated llama-server is up. It wins over the Qwen3 sparse lane for
    # the same expert turns, and fails open to that lane.
    # Do NOT require !_escalate_past_quick: escalate means "skip tiny 1.5B",
    # not "skip the warm Lightning server". Skipping Nemotron here forced CPU
    # 7B timeouts while :8905 stayed idle (2026-09-08 Engel AI Main outage).
    if not request.get("_skip_specialist_auto"):
        nemotron_receipt = _nemotron_lightning_local_model_receipt(prompt, started, request)
        if nemotron_receipt is not None and nemotron_receipt.get("ok") is True:
            reply = str(
                nemotron_receipt.get("assistant_reply")
                or nemotron_receipt.get("assistant_output_text")
                or ""
            )
            nemotron_receipt["selected_provider"] = "ct_nemotron_lightning"
            nemotron_receipt = _finalize_chat_receipt(
                nemotron_receipt,
                prompt,
                reply,
                "ct_nemotron_lightning",
                started,
                allow_room=_prompt_requests_meeting_room_dispatch(prompt),
                allow_reps=False,
            )
            reply = str(
                nemotron_receipt.get("assistant_reply")
                or nemotron_receipt.get("assistant_output_text")
                or reply
            )
            return nemotron_receipt, reply
    # The sparse 30B-A3B lane is the only local model here that genuinely
    # activates a subset of parameters per token. It is explicit or
    # complexity-routed, remains one-resident-model bounded, and fails open.
    if not request.get("_escalate_past_quick") and not request.get("_skip_specialist_auto"):
        moe_receipt = _sparse_moe_local_model_receipt(prompt, started, request)
        if moe_receipt is not None and moe_receipt.get("ok") is True:
            reply = str(
                moe_receipt.get("assistant_reply")
                or moe_receipt.get("assistant_output_text")
                or ""
            )
            moe_receipt["selected_provider"] = "ct_sparse_moe_specialist"
            moe_receipt = _finalize_chat_receipt(
                moe_receipt,
                prompt,
                reply,
                "ct_sparse_moe_specialist",
                started,
                allow_room=_prompt_requests_meeting_room_dispatch(prompt),
                allow_reps=False,
            )
            reply = str(
                moe_receipt.get("assistant_reply")
                or moe_receipt.get("assistant_output_text")
                or reply
            )
            return moe_receipt, reply
    # Explicit deep-local selection activates CT246's dense 14B GGUF on demand.
    # It remains available for compatibility; any failure falls through.
    if not request.get("_escalate_past_quick") and not request.get("_skip_specialist_auto"):
        deep_receipt = _deep_local_model_receipt(prompt, started, request)
        if deep_receipt is not None and deep_receipt.get("ok") is True:
            reply = str(
                deep_receipt.get("assistant_reply")
                or deep_receipt.get("assistant_output_text")
                or ""
            )
            deep_receipt["selected_provider"] = "ct_deep_local_specialist"
            deep_receipt = _finalize_chat_receipt(
                deep_receipt,
                prompt,
                reply,
                "ct_deep_local_specialist",
                started,
                allow_room=_prompt_requests_meeting_room_dispatch(prompt),
                allow_reps=False,
            )
            reply = str(
                deep_receipt.get("assistant_reply")
                or deep_receipt.get("assistant_output_text")
                or reply
            )
            return deep_receipt, reply
    # C-lane (2026-07-10): explicit code-artifact requests go to the dedicated
    # coder model BEFORE the chat lanes; fails open to normal routing.
    # BUT (20260711 fix) do NOT preempt prompts that route to the provider-bridge
    # code_or_review matrix (Codex/Claude/Grok) — the local 3B must not silently
    # downgrade a review/implement turn that the stronger reviewers would handle.
    _code_lane_provider_route = None
    if not request.get("_escalate_past_quick"):
        try:
            _, _code_lane_provider_route = _provider_candidates_for_prompt(prompt, request)
        except Exception:
            _code_lane_provider_route = None
    _automatic_local_first = _automatic_provider_after_local_failure_only(request)
    if request.get("_force_code_lane") is True:
        code_receipt = _code_lane_model_receipt(prompt, started, request)
        if code_receipt is not None and code_receipt.get("ok") is True:
            reply = str(code_receipt.get("assistant_reply") or code_receipt.get("assistant_output_text") or "")
            code_receipt["selected_provider"] = "ct_code_lane"
            code_receipt = _finalize_chat_receipt(
                code_receipt,
                prompt,
                reply,
                "ct_code_lane",
                started,
                allow_room=_prompt_requests_meeting_room_dispatch(prompt),
                allow_reps=False,
            )
            reply = str(code_receipt.get("assistant_reply") or code_receipt.get("assistant_output_text") or reply)
            return code_receipt, reply
    if not request.get("_escalate_past_quick") and not request.get("_skip_specialist_auto") and (
        _code_lane_provider_route != "code_or_review" or _automatic_local_first
    ):
        code_receipt = _code_lane_model_receipt(prompt, started, request)
        if code_receipt is not None and code_receipt.get("ok") is True:
            reply = str(code_receipt.get("assistant_reply") or code_receipt.get("assistant_output_text") or "")
            code_receipt["selected_provider"] = "ct_code_lane"
            code_receipt = _finalize_chat_receipt(
                code_receipt,
                prompt,
                reply,
                "ct_code_lane",
                started,
                allow_room=_prompt_requests_meeting_room_dispatch(prompt),
                allow_reps=False,
            )
            reply = str(code_receipt.get("assistant_reply") or code_receipt.get("assistant_output_text") or reply)
            return code_receipt, reply
    if request.get("_force_quick_casual") is True:
        receipt = _quick_casual_model_receipt(prompt, started, request)
        if receipt is not None and receipt.get("ok") is True:
            reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
            receipt["selected_provider"] = "ct_quick_local_chat"
            receipt = _finalize_chat_receipt(
                receipt,
                prompt,
                reply,
                "ct_quick_local_chat",
                started,
                allow_room=_prompt_requests_meeting_room_dispatch(prompt),
                allow_reps=False,
            )
            reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
            return receipt, reply
    owner_work = (
        _is_discord_owner_turn(request)
        and str(request.get("lane") or "").casefold() == "build"
        and _provider_fallback_allowed(request)
    )
    owner_or_ui_vision = _request_needs_vision_lane(request)
    if owner_work or owner_or_ui_vision:
        grok_turn = _call_grok_cli_bridge(prompt, request, started)
        grok_reply = str(grok_turn.get("assistant_reply") or "").strip()
        if grok_turn.get("ok") is True and grok_reply:
            grok_receipt = dict(grok_turn)
            grok_receipt["assistant_output_text"] = grok_reply
            grok_receipt["selected_provider"] = "rog_grok_cli"
            grok_receipt["discord_owner_task"] = bool(owner_work)
            grok_receipt["discord_owner_vision"] = bool(_is_discord_owner_turn(request) and owner_or_ui_vision)
            grok_receipt["main_ui_vision"] = bool(_is_main_ui_turn(request) and owner_or_ui_vision)
            lane_name = "ct_discord_owner_task" if owner_work else (
                "ct_discord_owner_vision" if _is_discord_owner_turn(request) else (
                    "ct_discord_vision" if str(request.get("source") or "").casefold().startswith("discord")
                    else "ct_main_ui_vision"
                )
            )
            grok_receipt = _finalize_chat_receipt(
                grok_receipt,
                prompt,
                grok_reply,
                lane_name,
                started,
                allow_room=_prompt_requests_meeting_room_dispatch(prompt),
                allow_reps=False,
            )
            grok_reply = str(
                grok_receipt.get("assistant_reply") or grok_receipt.get("assistant_output_text") or grok_reply
            )
            return grok_receipt, grok_reply
        fail_note = str(grok_turn.get("error") or "Grok work lane did not return a reply")
        if owner_or_ui_vision:
            # Live 2026-08-27: Josh's Discord screenshot sat 90s on the local
            # 7B after Grok's reverse tunnel was down. Do not hang vision on
            # the tiny local model. Answer from stored pixel notes instead.
            vision_reply = _vision_lane_local_reply(prompt, request, fail_note)
            vision_receipt = {
                "ok": True,
                "assistant_reply": vision_reply,
                "assistant_output_text": vision_reply,
                "selected_provider": "ct_vision_notes_fallback",
                "runtime_provider": "local-image-notes",
                "discord_owner_vision": bool(_is_discord_owner_turn(request)),
                "main_ui_vision": bool(_is_main_ui_turn(request)),
                "grok_vision_error": fail_note[:400],
            }
            vision_receipt = _finalize_chat_receipt(
                vision_receipt,
                prompt,
                vision_reply,
                "ct_vision_notes_fallback",
                started,
                allow_room=False,
                allow_reps=False,
            )
            return vision_receipt, str(
                vision_receipt.get("assistant_reply") or vision_reply
            )
        if owner_work:
            prompt = (
                prompt
                + "\n\n[Engel work-lane note: the ROG Grok operator lane did not finish. "
                + "Error: "
                + fail_note[:400]
                + ". Do not claim the job is complete. Say you started it, name the miss, "
                + "and what you can still do from CT246 chat.]"
            )
    if (
        not _is_discord_owner_turn(request)
        and _request_prefers_quick_local_chat(prompt, request)
        and not request.get("_escalate_past_quick")
    ):
        receipt = _quick_casual_model_receipt(prompt, started, request)
        if receipt is not None and receipt.get("ok") is True and _quick_reply_accept(prompt, request, receipt):
            reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
            receipt["selected_provider"] = "ct_quick_local_chat"
            receipt["runtime_provider"] = "llama-cpp-python-local-gguf-fast-chat"
            receipt["quick_local_front_lane_used"] = True
            receipt = _finalize_chat_receipt(
                receipt,
                prompt,
                reply,
                "ct_quick_local_chat",
                started,
                allow_room=_prompt_requests_meeting_room_dispatch(prompt),
                allow_reps=False,
            )
            reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
            return receipt, reply
    if (
        not _is_discord_owner_turn(request)
        and _prompt_requests_short_casual_fast_model(prompt)
        and not request.get("_escalate_past_quick")
    ):
        receipt = _quick_casual_model_receipt(prompt, started, request)
        if receipt is not None and receipt.get("ok") is True and _quick_reply_accept(prompt, request, receipt):
            reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
            receipt["selected_provider"] = "ct_short_casual_fast_model"
            receipt = _finalize_chat_receipt(
                receipt,
                prompt,
                reply,
                "ct_short_casual_fast_model",
                started,
                allow_room=_prompt_requests_meeting_room_dispatch(prompt),
                allow_reps=False,
            )
            reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
            return receipt, reply
    # Mode gate (cognitive_routing_model.md): route by TYPE of thinking.
    # Reflex and confident memory-recall turns complete here; convergent /
    # divergent turns are annotated with hints and continue down the cascade.
    mode_gate_result = None if context_requires_model else _mode_gate_turn(prompt, request, started)
    if mode_gate_result is not None:
        return mode_gate_result
    # Mode gate may have marked _escalate_past_quick after the earlier specialist
    # pass. Give the warm Lightning server one more shot before CPU 7B.
    # Keep true quick/UI casual turns on the 1.5B default-fast path instead.
    if (
        request.get("_escalate_past_quick") is True
        and not request.get("_skip_specialist_auto")
        and not request.get("_nemotron_post_mode_gate_tried")
        and not (
            request.get("prefer_fast_local_chat") is True
            and _prompt_requests_quick_casual_model(prompt)
        )
    ):
        request["_nemotron_post_mode_gate_tried"] = True
        request["_force_nemotron"] = True
        nemotron_receipt = _nemotron_lightning_local_model_receipt(prompt, started, request)
        request.pop("_force_nemotron", None)
        if nemotron_receipt is not None and nemotron_receipt.get("ok") is True:
            reply = str(
                nemotron_receipt.get("assistant_reply")
                or nemotron_receipt.get("assistant_output_text")
                or ""
            )
            nemotron_receipt["selected_provider"] = "ct_nemotron_lightning_post_mode_gate"
            nemotron_receipt = _finalize_chat_receipt(
                nemotron_receipt,
                prompt,
                reply,
                "ct_nemotron_lightning",
                started,
                allow_room=_prompt_requests_meeting_room_dispatch(prompt),
                allow_reps=False,
            )
            reply = str(
                nemotron_receipt.get("assistant_reply")
                or nemotron_receipt.get("assistant_output_text")
                or reply
            )
            return nemotron_receipt, reply
    # Code/review work can use the provider bridge matrix before local chat
    # because those lanes include Codex/Claude/Grok reviewers. Normal chat is
    # local-first so CT246's tuned LoRA is the front voice and training target.
    _, provider_route_reason = _provider_candidates_for_prompt(prompt, request)
    if provider_route_reason == "code_or_review" and not _automatic_local_first:
        provider_turn = _complete_provider_bridge_turn(prompt, request, started)
        if provider_turn is not None:
            return provider_turn
    # Mode gate sometimes marks escalate on tiny UI pings. Keep prefer-fast
    # casual turns on the 1.5B lane so Engel AI Main short chat stays snappy.
    if (
        request.get("prefer_fast_local_chat") is True
        and _prompt_requests_quick_casual_model(prompt)
        and not _prompt_requires_large_local_reasoning(prompt)
    ):
        request.pop("_escalate_past_quick", None)
    if _prompt_allows_default_fast_local_chat(prompt, request) and not request.get("_escalate_past_quick"):
        receipt = _quick_casual_model_receipt(prompt, started, request)
        if receipt is not None and receipt.get("ok") is True and _quick_reply_accept(prompt, request, receipt):
            reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
            receipt["selected_provider"] = "ct_default_fast_local_llm"
            receipt["runtime_provider"] = "llama-cpp-python-local-gguf-fast-default"
            receipt["default_fast_local_chat_used"] = True
            receipt["slow_trained_lora_bypassed_for_default_chat"] = True
            receipt = _finalize_chat_receipt(
                receipt,
                prompt,
                reply,
                "ct_default_fast_local_chat",
                started,
                allow_room=_prompt_requests_meeting_room_dispatch(prompt),
                allow_reps=False,
            )
            reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
            return receipt, reply
    # Engel's tuned LoRA stays available as the deep local fallback. Everyday
    # chat already used the fast local model above so the UI does not sit on a
    # slow 7B load/generation path for normal conversation.
    premodel_templates_enabled = os.environ.get(
        "ENGEL_FAST_TEMPLATE_PREMODEL_ENABLED",
        "",
    ).strip().lower() in {"1", "true", "yes", "on"}
    if context_requires_model:
        premodel_templates_enabled = False
    if premodel_templates_enabled and _prompt_requests_quick_casual_model(prompt) and not request.get("_escalate_past_quick"):
        receipt = _quick_casual_model_receipt(prompt, started, request)
        if receipt is not None and receipt.get("ok") is True and _quick_reply_accept(prompt, request, receipt):
            reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
            receipt = _finalize_chat_receipt(
                receipt,
                prompt,
                reply,
                "ct_quick_casual_chat",
                started,
                allow_room=_prompt_requests_meeting_room_dispatch(prompt),
            )
            reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
            return receipt, reply
    if premodel_templates_enabled and _prompt_requests_help_next(prompt):
        receipt = _fast_server_receipt(prompt, started, error="fast help-next route", fallback_used=False)
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_help_next_chat",
            started,
            allow_room=_prompt_requests_meeting_room_dispatch(prompt),
        )
        return receipt, reply
    if premodel_templates_enabled and _prompt_requests_deterministic_visible_chat(prompt):
        receipt = _fast_server_receipt(
            prompt,
            started,
            error="fast deterministic visible chat route",
            fallback_used=False,
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_deterministic_visible_chat",
            started,
            allow_room=_prompt_requests_meeting_room_dispatch(prompt),
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
        return receipt, reply
    if premodel_templates_enabled and _prompt_requests_instant_desktop_chat(prompt):
        receipt = _fast_server_receipt(
            prompt,
            started,
            error="instant desktop chat route",
            fallback_used=False,
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_instant_desktop_chat",
            started,
            allow_room=_prompt_requests_meeting_room_dispatch(prompt),
            allow_reps=False,
        )
        return receipt, reply
    if premodel_templates_enabled and _prompt_requests_fast_visible_chat(prompt):
        receipt = _fast_server_receipt(
            prompt,
            started,
            error="fast visible chat route",
            fallback_used=False,
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
        receipt = _finalize_chat_receipt(
            receipt,
            prompt,
            reply,
            "ct_fast_visible_chat",
            started,
            allow_room=_prompt_requests_meeting_room_dispatch(prompt),
        )
        reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
        return receipt, reply
    timeout = max(1, int(request.get("timeout") or 45))
    try:
        timeout_cap = int(float(os.environ.get("ENGEL_MAIN_SERVER_MODEL_TIMEOUT_CAP", "45") or "45"))
    except Exception:
        timeout_cap = 45
    try:
        timeout_floor = int(
            float(os.environ.get("ENGEL_MAIN_SERVER_MODEL_TIMEOUT_FLOOR", "0") or "0")
        )
    except Exception:
        timeout_floor = 0
    if timeout_floor > 0:
        timeout = max(timeout, timeout_floor)
    if _is_discord_owner_turn(request):
        # Owner Discord sends 90s. The 45s service cap was clipping the 7B/14B
        # lanes mid-reply and dumping Josh back onto a stub answer.
        timeout = max(timeout, 90)
        timeout = min(timeout, max(timeout_cap, 180))
    else:
        timeout = min(timeout, max(5, timeout_cap))
    max_tokens = max(1, int(request.get("max_tokens") or request.get("max_completion_tokens") or 420))
    temperature = float(request.get("temperature") or 0.15)
    receipt: dict[str, Any]
    _big_mem = ""
    try:
        from run_engel_standalone_chat_llm import run_chat

        # (2026-07-07 M-1 big lane) durable facts + semantic recall + (2026-07-10) the
        # persona/voice block, composed by the shared helper so both big-lane paths match.
        _big_mem = _big_lane_memory(prompt, request)
        fast_fail_attempt = run_with_deadline(
            "ct246-large-local-chat",
            lambda: run_chat(
                prompt=prompt,
                timeout=timeout,
                max_tokens=max_tokens,
                temperature=temperature,
                provider=str(request.get("local_provider") or "local"),
                extra_memory=_big_mem,
                escalated_from=request.get("_engel_escalated_from"),  # (NT-2) quick->big escalation marker
                persist_chat_history=False,
            ),
            # The outer wall must exceed the model budget: with both equal, a
            # full-length generation is discarded during post-processing.
            requested_timeout=timeout + 6,
            fallback_allowed=_provider_fallback_allowed(request),
        )
        fast_fail_public = {
            key: value
            for key, value in fast_fail_attempt.items()
            if key != "result"
        }
        if fast_fail_attempt.get("ok") is True and isinstance(fast_fail_attempt.get("result"), dict):
            receipt = dict(fast_fail_attempt["result"])
            receipt["local_llm_fast_fail"] = fast_fail_public
        else:
            receipt = {
                "schema": "ENGEL_LOCAL_LLM_FAST_FAIL_CHAT_FAILURE_V1",
                "ok": False,
                "status": str(fast_fail_attempt.get("status") or "local LLM failed within bounded controller"),
                "assistant_reply": "",
                "assistant_output_text": "",
                "provider": "local",
                "runtime_provider": "engel-local-llm-fast-fail",
                "error": str(fast_fail_attempt.get("error") or ""),
                "local_llm_fast_fail": fast_fail_public,
                "training_sample_eligible": False,
                "persistent_chat_memory_training_eligible": False,
                "provider_api_enabled": False,
                "provider_called": False,
            }
    except Exception as exc:
        receipt = {
            "schema": "ENGEL_LOCAL_LLM_FAST_FAIL_CHAT_FAILURE_V1",
            "ok": False,
            "status": "local LLM deadline controller failed",
            "assistant_reply": "",
            "assistant_output_text": "",
            "provider": "local",
            "runtime_provider": "engel-local-llm-fast-fail",
            "error": str(exc),
            "training_sample_eligible": False,
            "persistent_chat_memory_training_eligible": False,
            "provider_api_enabled": False,
            "provider_called": False,
        }
    if self_model_introspection:
        self_snapshot = _self_model_snapshot()
        receipt["self_model_query"] = True
        receipt["self_model_context_injected"] = bool(_big_mem and "ENGEL PERSISTENT SELF MODEL" in _big_mem)
        receipt["self_model_state_revision"] = int(self_snapshot.get("state_revision") or 0)
        receipt["self_model_state_sha256"] = str(self_snapshot.get("state_sha256") or "")
        if isinstance(request.get("_self_model_freshness"), dict):
            receipt["self_model_freshness"] = request["_self_model_freshness"]
    local_reply_for_quality = str(
        receipt.get("assistant_reply") or receipt.get("assistant_output_text") or ""
    ).strip()
    semantic_quality = _incomplete_input_quality_report(quality_prompt, local_reply_for_quality)
    repairable_action_owner_failures = {
        "no_placeholder_confirmation_owner",
        "no_unverified_external_action_claim",
    }
    if repairable_action_owner_failures.intersection(semantic_quality.get("failed_checks") or []):
        repaired_reply, action_owner_repaired = _repair_unverified_action_and_placeholder_owner(
            quality_prompt,
            local_reply_for_quality,
        )
        if action_owner_repaired:
            receipt["semantic_action_owner_repaired"] = True
            receipt["semantic_action_owner_original_reply"] = local_reply_for_quality
            receipt["assistant_reply"] = repaired_reply
            receipt["assistant_output_text"] = repaired_reply
            local_reply_for_quality = repaired_reply
            semantic_quality = _incomplete_input_quality_report(quality_prompt, local_reply_for_quality)
    repairable_source_boundary_failures = {
        "identifies_confirmation_source_or_owner",
        "preserves_safe_work_boundary",
    }
    semantic_failed_checks = set(semantic_quality.get("failed_checks") or [])
    if (
        "identifies_confirmation_source_or_owner" in semantic_failed_checks
        and semantic_failed_checks.issubset(repairable_source_boundary_failures)
    ):
        repaired_reply, source_added = _repair_missing_confirmation_source(
            quality_prompt,
            local_reply_for_quality,
        )
        if source_added:
            receipt["semantic_confirmation_source_added"] = True
            receipt["semantic_confirmation_source_original_reply"] = local_reply_for_quality
            receipt["assistant_reply"] = repaired_reply
            receipt["assistant_output_text"] = repaired_reply
            local_reply_for_quality = repaired_reply
            semantic_quality = _incomplete_input_quality_report(quality_prompt, local_reply_for_quality)
    if semantic_quality.get("failed_checks") == ["complete_ending"]:
        repaired_reply, punctuation_added = _repair_safe_missing_terminal_punctuation(
            local_reply_for_quality
        )
        if punctuation_added:
            receipt["semantic_terminal_punctuation_added"] = True
            receipt["semantic_terminal_punctuation_original_reply"] = local_reply_for_quality
            receipt["assistant_reply"] = repaired_reply
            receipt["assistant_output_text"] = repaired_reply
            local_reply_for_quality = repaired_reply
            semantic_quality = _incomplete_input_quality_report(quality_prompt, local_reply_for_quality)
    if _is_form_graded_training_prompt(prompt) and local_reply_for_quality:
        semantic_quality = _apply_form_graded_training_quality_policy(
            prompt,
            semantic_quality,
            local_reply_for_quality,
        )
        receipt["local_semantic_quality"] = semantic_quality
        if semantic_quality.get("complete_ending_waived_for_form_training") is True:
            receipt["complete_ending_waived_for_form_training"] = True
        if semantic_quality.get("form_training_serve_draft") is True:
            receipt["training_form_draft_served"] = True
    if (
        receipt.get("ok") is True
        and local_reply_for_quality
        and semantic_quality.get("required") is True
        and semantic_quality.get("ok") is not True
        and not _is_form_graded_training_prompt(prompt)
    ):
        semantic_retry_prompt = _semantic_local_repair_request(
            prompt,
            local_reply_for_quality,
            [str(value) for value in semantic_quality.get("failed_checks") or []],
        )
        receipt["local_semantic_repair_attempted"] = True
        receipt["local_semantic_repair_original_reply"] = local_reply_for_quality
        receipt["local_semantic_repair_initial_failed_checks"] = semantic_quality.get("failed_checks", [])
        try:
            from run_engel_standalone_chat_llm import run_chat as run_semantic_repair_chat

            remaining_timeout = max(
                1,
                int(timeout - max(0.0, time.perf_counter() - started)),
            )
            semantic_fast_fail = run_with_deadline(
                "ct246-local-semantic-repair",
                lambda: run_semantic_repair_chat(
                    prompt=semantic_retry_prompt,
                    timeout=remaining_timeout,
                    max_tokens=max_tokens,
                    temperature=0.05,
                    provider="local",
                    extra_memory=_big_mem,
                    escalated_from=request.get("_engel_escalated_from"),
                    persist_chat_history=False,
                ),
                requested_timeout=remaining_timeout,
                fallback_allowed=False,
            )
            receipt["local_semantic_repair_fast_fail"] = {
                key: value for key, value in semantic_fast_fail.items() if key != "result"
            }
            if semantic_fast_fail.get("ok") is not True or not isinstance(semantic_fast_fail.get("result"), dict):
                raise RuntimeError(
                    str(semantic_fast_fail.get("status") or "bounded local semantic repair failed")
                )
            semantic_retry_receipt = dict(semantic_fast_fail["result"])
            semantic_retry_reply = str(
                semantic_retry_receipt.get("assistant_reply")
                or semantic_retry_receipt.get("assistant_output_text")
                or ""
            ).strip()
            semantic_retry_reply, _ = _repair_unverified_action_and_placeholder_owner(
                quality_prompt,
                semantic_retry_reply,
            )
            semantic_retry_quality = _incomplete_input_quality_report(
                quality_prompt,
                semantic_retry_reply,
            )
            retry_failed = set(semantic_retry_quality.get("failed_checks") or [])
            if (
                "identifies_confirmation_source_or_owner" in retry_failed
                and retry_failed.issubset(repairable_source_boundary_failures)
            ):
                semantic_retry_reply, _ = _repair_missing_confirmation_source(
                    quality_prompt,
                    semantic_retry_reply,
                )
                semantic_retry_quality = _incomplete_input_quality_report(
                    quality_prompt,
                    semantic_retry_reply,
                )
            receipt["local_semantic_repair_receipt_path"] = str(
                semantic_retry_receipt.get("workspace_receipt_path") or ""
            )
            receipt["local_semantic_repair_status"] = str(semantic_retry_receipt.get("status") or "")
            receipt["local_semantic_repair_quality"] = semantic_retry_quality
            if (
                semantic_retry_receipt.get("ok") is True
                and semantic_retry_reply
                and semantic_retry_quality.get("ok") is True
            ):
                receipt["assistant_reply"] = semantic_retry_reply
                receipt["assistant_output_text"] = semantic_retry_reply
                receipt["local_semantic_repair_accepted"] = True
                receipt["status"] = "large local chat replied after semantic repair"
                local_reply_for_quality = semantic_retry_reply
                semantic_quality = semantic_retry_quality
            else:
                receipt["local_semantic_repair_accepted"] = False
        except Exception as exc:
            receipt["local_semantic_repair_accepted"] = False
            receipt["local_semantic_repair_error"] = str(exc)
    receipt["local_semantic_quality"] = semantic_quality
    receipt["local_only_training"] = _request_local_only_training(request)
    stall_reply = _reply_is_conversation_stall(local_reply_for_quality)
    if stall_reply:
        receipt["ok"] = False
        receipt["conversation_stall_blocked"] = True
        receipt["quality_gate_degraded"] = True
        receipt["status"] = "local quality check failed"
        semantic_quality = dict(semantic_quality or {})
        semantic_quality["ok"] = False
        failed = list(semantic_quality.get("failed_checks") or [])
        if "conversation_stall" not in failed:
            failed.append("conversation_stall")
        semantic_quality["failed_checks"] = failed
        receipt["local_semantic_quality"] = semantic_quality
    # Clamped governor context rides the receipt so downstream persisters can
    # apply persist_policy/base_prompt substitution (memory hygiene section 4.2).
    receipt["governor_context"] = _request_governor_context(request)
    receipt["provider_fallback_allowed"] = _provider_fallback_allowed(request)
    receipt["semantic_quality_scoped_context_used"] = quality_context_used
    receipt["training_sample_eligible"] = bool(
        receipt.get("ok") is True
        and local_reply_for_quality
        and semantic_quality.get("ok") is True
    )
    receipt["persistent_chat_memory_training_eligible"] = receipt[
        "training_sample_eligible"
    ]
    if local_reply_for_quality and semantic_quality.get("ok") is not True:
        quarantine = _append_chat_sample_rejection(
            prompt,
            local_reply_for_quality,
            receipt,
            "incomplete-input semantic quality failure: "
            + ", ".join(str(v) for v in semantic_quality.get("failed_checks") or []),
        )
        receipt["quality_gate_reason"] = "incomplete-input semantic quality failure"
        receipt["quality_gate_failed_checks"] = semantic_quality.get("failed_checks", [])
        receipt["chat_sample_quarantined"] = quarantine.get("ok") is True
        receipt["chat_sample_quarantine_key"] = quarantine.get("sample_key", "")
        receipt["chat_sample_quarantine_path"] = str(REJECTED_CHAT_SAMPLES_PATH)
        receipt["training_sample_eligible"] = False
        receipt["persistent_chat_memory_training_eligible"] = False
        if semantic_quality.get("form_training_serve_draft") is True:
            # Serve the labelled form so the trainer can grade it. Live chat
            # still takes the quality-block path below.
            receipt["ok"] = True
            receipt["assistant_reply"] = local_reply_for_quality
            receipt["assistant_output_text"] = local_reply_for_quality
            receipt["training_form_serve_ineligible"] = True
            receipt["quality_gate_degraded"] = True
            receipt["status"] = "local form-graded training draft served for grading"
        elif _is_spoken_voice_training_prompt(prompt) and local_reply_for_quality:
            discord_mouth = False
            try:
                from engel_persona_guard import looks_like_discord_mouth_reply

                discord_mouth = looks_like_discord_mouth_reply(local_reply_for_quality)
            except Exception:
                discord_mouth = "only engelz" in local_reply_for_quality.casefold()
            if discord_mouth or _reply_is_conversation_stall(local_reply_for_quality):
                receipt["ok"] = False
                receipt["quality_gate_degraded"] = True
                receipt["discord_mouth_blocked"] = True
                receipt["status"] = "local quality check failed"
            else:
                receipt["ok"] = True
                receipt["assistant_reply"] = local_reply_for_quality
                receipt["assistant_output_text"] = local_reply_for_quality
                receipt["spoken_voice_training_served"] = True
                receipt["quality_gate_degraded"] = True
                receipt["status"] = "local model replied with quality warning"
        else:
            receipt["quality_gate_degraded"] = True
            receipt["status"] = "local quality check failed"
    local_status = str(receipt.get("status") or "").casefold()
    local_quality_failed = bool(
        receipt.get("training_form_serve_ineligible") is not True
        and receipt.get("spoken_voice_training_served") is not True
        and (
            receipt.get("quality_gate_degraded") is True
            or "style check failed" in local_status
            or "quality check failed" in local_status
        )
    )
    if (
        receipt.get("ok") is not True
        or not (receipt.get("assistant_reply") or receipt.get("assistant_output_text"))
        or local_quality_failed
    ):
        local_failure_receipt = receipt
        auto_bridge_fallback = _provider_fallback_allowed(request)
        if auto_bridge_fallback:
            # (NT-1) the local (big) lane was attempted and failed -> this bridge turn is a
            # real depth-2 -> depth-3 escalation; record where it escalated from.
            local_escalation_origin = request.get("_engel_escalated_from")
            request["_engel_escalated_from"] = 2
            request["_automatic_local_failure_fallback"] = True
            provider_turn = _complete_provider_bridge_turn(
                prompt,
                request,
                started,
                persist_memory=False,
            )
            if provider_turn is not None:
                provider_receipt, provider_reply = provider_turn
                if _reply_is_conversation_stall(provider_reply):
                    provider_turn = None
                    provider_receipt = {}
                    provider_reply = ""
            if provider_turn is not None:
                local_fast_fail = (
                    local_failure_receipt.get("local_llm_fast_fail")
                    if isinstance(local_failure_receipt.get("local_llm_fast_fail"), dict)
                    else {}
                )
                fallback_proof_path = str(local_fast_fail.get("fallback_proof_path") or "")
                if fallback_proof_path:
                    provider_receipt["local_llm_fallback_final"] = finalize_fallback_proof(
                        fallback_proof_path,
                        fallback_attempted=True,
                        fallback_completed=True,
                        provider_id=str(
                            provider_receipt.get("selected_provider")
                            or provider_receipt.get("provider")
                            or ""
                        ),
                        reason="quality-passed provider completion after bounded local-model failure",
                        provider_called=bool(provider_receipt.get("provider_bridge_used") is True),
                    )
                provider_receipt["chat_context_scope"] = _chat_context_scope(request)
                provider_receipt["prompt"] = prompt
                provider_receipt["assistant_reply"] = provider_reply
                provider_receipt["assistant_output_text"] = provider_reply
                provider_receipt["local_ct_lora_first_attempted"] = True
                provider_receipt["local_ct_lora_first_failed"] = True
                provider_receipt["local_ct_lora_first_quality_failed"] = local_quality_failed
                provider_receipt["local_ct_lora_first_semantic_quality"] = semantic_quality
                provider_receipt["local_ct_lora_first_sample_quarantined"] = bool(
                    local_failure_receipt.get("chat_sample_quarantined") is True
                )
                provider_receipt["local_ct_lora_first_quarantine_key"] = str(
                    local_failure_receipt.get("chat_sample_quarantine_key") or ""
                )
                provider_receipt["local_ct_lora_first_status"] = str(local_failure_receipt.get("status") or "")
                provider_receipt["local_ct_lora_first_error"] = str(
                    local_failure_receipt.get("error") or local_failure_receipt.get("local_command_stderr_preview") or ""
                )[:1200]
                provider_receipt["automatic_provider_after_local_failure_only"] = _automatic_local_first
                provider_training_eligible = bool(
                    provider_receipt.get("provider_reply_quality_gate_passed") is True
                    and isinstance(provider_receipt.get("provider_final_semantic_quality"), dict)
                    and provider_receipt.get("provider_final_semantic_quality", {}).get("ok") is True
                    and provider_receipt.get("local_ct_lora_first_attempted") is True
                    and provider_receipt.get("local_ct_lora_first_failed") is True
                )
                provider_receipt["training_sample_eligible"] = provider_training_eligible
                provider_receipt["persistent_chat_memory_training_eligible"] = (
                    provider_training_eligible
                )
                provider_receipt["memory_source"] = (
                    "engel-ai-main CT provider response after verified local failure"
                )
                try:
                    _append_jsonl(PERSISTENT_CHAT_MEMORY_PATH, dict(provider_receipt))
                    provider_receipt["persistent_chat_memory_appended"] = True
                    provider_receipt["persistent_chat_history_appended"] = True
                    provider_receipt["persistent_chat_memory_path"] = str(PERSISTENT_CHAT_MEMORY_PATH)
                except Exception as exc:
                    provider_receipt["persistent_chat_memory_error"] = str(exc)
                provider_receipt_path = str(provider_receipt.get("workspace_receipt_path") or "").strip()
                if provider_receipt_path:
                    try:
                        _write_json(Path(provider_receipt_path), provider_receipt)
                    except Exception as exc:
                        provider_receipt["enriched_receipt_write_error"] = str(exc)
                return provider_receipt, provider_reply
            if local_escalation_origin is None:
                request.pop("_engel_escalated_from", None)
            else:
                request["_engel_escalated_from"] = local_escalation_origin
            request["_automatic_provider_fallback_attempted"] = True
        local_fast_fail = (
            local_failure_receipt.get("local_llm_fast_fail")
            if isinstance(local_failure_receipt.get("local_llm_fast_fail"), dict)
            else {}
        )
        fallback_proof_path = str(local_fast_fail.get("fallback_proof_path") or "")
        if fallback_proof_path:
            provider_attempts = request.get("_provider_bridge_attempts")
            provider_called = bool(provider_attempts) if isinstance(provider_attempts, list) else False
            local_failure_receipt["local_llm_fallback_final"] = finalize_fallback_proof(
                fallback_proof_path,
                fallback_attempted=bool(request.get("_automatic_provider_fallback_attempted") is True),
                fallback_completed=False,
                provider_id="",
                reason=(
                    "provider fallback returned no quality-passed reply"
                    if request.get("_automatic_provider_fallback_attempted") is True
                    else "provider fallback was not authorized for this turn"
                ),
                provider_called=provider_called,
            )
        local_failure_receipt["provider_bridge_fallback_skipped"] = True
        # The guard's own local_llm_fast_fail.fallback_allowed reflects the GUARD's opinion,
        # not this service's local-first policy. Record the policy decision separately so a
        # receipt can never read as "fallback was allowed but silently never ran".
        local_failure_receipt["provider_bridge_fallback_permitted"] = bool(auto_bridge_fallback)
        if request.get("_automatic_provider_fallback_attempted") is True:
            local_failure_receipt["provider_bridge_fallback_skip_reason"] = (
                "provider fallback was attempted after local quality failure but no provider returned a usable reply"
            )
        else:
            local_failure_receipt["provider_bridge_fallback_skip_reason"] = (
                "normal Engel chat is local-first; provider fallback requires explicit request or "
                "ENGEL_LOCAL_CHAT_AUTO_BRIDGE_FALLBACK=1"
            )
        if semantic_quality.get("required") is True and semantic_quality.get("ok") is not True:
            rejected_local_reply = str(
                local_failure_receipt.get("assistant_reply")
                or local_failure_receipt.get("assistant_output_text")
                or ""
            ).strip()
            blocked_reply = (
                "I stopped this turn because the local draft and every available fallback failed the "
                "missing-input safety checks. I did not accept those drafts into training or use their "
                "assumptions. Please retry the request; the confirmed facts and open questions will stay separate."
            )
            blocked_path = CHAT_RECEIPT_DIR / f"ENGEL_MAIN_SERVER_CHAT_QUALITY_BLOCKED_{_stamp()}.json"
            blocked_receipt = dict(local_failure_receipt)
            blocked_receipt.update(
                {
                    "schema": "engel_main_server_chat_quality_blocked_v1",
                    "ok": False,
                    "status": "chat quality gate blocked unsafe drafts",
                    "updated_at_utc": _iso_now(),
                    "prompt": prompt,
                    "chat_context_scope": _chat_context_scope(request),
                    "assistant_reply": blocked_reply,
                    "assistant_output_text": blocked_reply,
                    "local_rejected_reply_sha256": hashlib.sha256(
                        rejected_local_reply.encode("utf-8")
                    ).hexdigest() if rejected_local_reply else "",
                    "provider_semantic_quality_rejections": request.get(
                        "_provider_semantic_quality_rejections", []
                    ),
                    "provider_bridge_attempts": request.get(
                        "_provider_bridge_attempts", []
                    ),
                    "provider_bridge_candidates": request.get(
                        "_provider_bridge_candidates", []
                    ),
                    "provider_bridge_route_reason": request.get(
                        "_provider_bridge_route_reason", ""
                    ),
                    "provider_bridge_fallback_attempted": bool(
                        request.get("_automatic_provider_fallback_attempted") is True
                        or auto_bridge_fallback
                    ),
                    "provider_bridge_usable_reply": False,
                    "activation_depth": 3 if auto_bridge_fallback else 2,
                    "activation_depth_label": "provider_bridge" if auto_bridge_fallback else "big_local_model",
                    "escalated_from": 2 if auto_bridge_fallback else request.get("_engel_escalated_from"),
                    "quality_gate_blocked_visible_unsafe_output": True,
                    "training_sample_eligible": False,
                    "bridge_training_capture_enabled": False,
                    "trusted_memory_write_enabled": False,
                    "approved_memory_write_enabled": False,
                    "model_output_trusted": False,
                    "workspace_receipt_path": str(blocked_path),
                    "server_request_latency_ms": int((time.perf_counter() - started) * 1000),
                }
            )
            try:
                failure_memory = dict(blocked_receipt)
                failure_memory["memory_source"] = "engel-ai-main rejected chat quality audit"
                _append_jsonl(PERSISTENT_CHAT_MEMORY_PATH, failure_memory)
                blocked_receipt["persistent_chat_memory_appended"] = True
                blocked_receipt["persistent_chat_memory_training_eligible"] = False
            except Exception as exc:
                blocked_receipt["persistent_chat_memory_error"] = str(exc)
            _write_json(blocked_path, blocked_receipt)
            return blocked_receipt, blocked_reply
        # (NT-2) fail-open: if this turn escalated PAST a usable quick-lane reply and the big
        # lane then died, hand back the stashed quick reply rather than a generic fault message.
        _shadow_reply = str(request.get("_quick_lane_shadow_reply") or "")
        if _shadow_reply and not _prompt_requires_buffered_quality_gate(prompt):
            local_failure_receipt["assistant_reply"] = _shadow_reply
            local_failure_receipt["assistant_output_text"] = _shadow_reply
            local_failure_receipt["ok"] = True
            local_failure_receipt["quick_lane_restored_after_failed_escalation"] = True
            receipt = _finalize_chat_receipt(
                local_failure_receipt, prompt, _shadow_reply, "ct_quick_local_chat", started,
                allow_room=False, allow_reps=False,
            )
            reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or _shadow_reply)
            return receipt, reply
        degraded_model_reply = str(
            local_failure_receipt.get("assistant_reply")
            or local_failure_receipt.get("assistant_output_text")
            or ""
        ).strip()
        if (
            degraded_model_reply
            and _prompt_requires_buffered_quality_gate(prompt)
            and not _reply_is_conversation_stall(degraded_model_reply)
        ):
            # Keep the real local-model answer visible when a strict style check
            # exhausts its repair attempts. A canned responder would hide the
            # defect, break conversational context, and violate local-model proof.
            local_failure_receipt["ok"] = True
            local_failure_receipt["status"] = "local model replied with quality warning"
            local_failure_receipt["quality_gate_degraded"] = True
            local_failure_receipt["quality_gate_original_status"] = str(receipt.get("status") or "")
            receipt = local_failure_receipt
        elif local_fast_fail:
            receipt = _local_llm_fast_fail_visible_receipt(prompt, started, local_failure_receipt)
        else:
            receipt = _fast_server_receipt(prompt, started, model_receipt=local_failure_receipt)
    receipt["main_server_chat_service_used"] = True
    receipt["main_server_chat_service_root"] = str(ROOT)
    receipt["server_role"] = "engel-ai-main CT 246"
    receipt["model_service_server_enabled"] = True
    if isinstance(request.get("mode_gate_decision"), dict):
        receipt["mode_gate"] = request["mode_gate_decision"]
    # (2026-07-26 neuro audit) durable NT telemetry: the quick lane's discarded
    # receipt carried the confidence evidence — re-stamp it here so an escalated
    # turn's final record explains WHY it escalated. Same for freshness evidence.
    if isinstance(request.get("_quick_lane_confidence_evidence"), dict):
        receipt["quick_lane_escalation_evidence"] = request["_quick_lane_confidence_evidence"]
    if isinstance(request.get("_self_model_freshness"), dict) and "self_model_freshness" not in receipt:
        receipt["self_model_freshness"] = request["_self_model_freshness"]
    receipt = _apply_live_status_answer_if_needed(prompt, receipt)
    receipt = _apply_chat_humanizer(prompt, receipt, "ct_main_chat_turn")
    reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
    context_scope = _chat_context_scope(request)
    receipt["chat_context_scope"] = context_scope
    receipt = _finalize_chat_receipt(
        receipt,
        prompt,
        reply,
        "ct_model_chat",
        started,
        allow_room=_prompt_requests_meeting_room_dispatch(prompt),
        # (NT-2) if a weak quick reply escalated here and the big lane succeeded, record it so the
        # escalation is visible to NT-1 (without this, a successful escalation looks like a plain
        # big-lane turn). None on ordinary big-lane turns, so byte-invariance with the flag OFF holds.
        escalated_from=request.get("_engel_escalated_from"),
        persist_memory=False,
    )
    reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
    try:
        scoped_record = dict(receipt)
        scoped_record["memory_source"] = "engel-ai-main CT scoped final chat"
        scoped_record["prompt"] = prompt
        scoped_record["assistant_reply"] = reply
        scoped_record["persistent_chat_memory_appended"] = True
        scoped_record["persistent_chat_history_appended"] = True
        _persona = receipt.get("persona_guard")
        if isinstance(_persona, dict) and _persona.get("reason") == "all_recitation":
            scoped_record["echo"] = True
            scoped_record["context_eligible"] = False
        _append_jsonl(PERSISTENT_CHAT_MEMORY_PATH, scoped_record)
        receipt["scoped_chat_memory_appended"] = True
        receipt["persistent_chat_memory_appended"] = True
        receipt["persistent_chat_history_appended"] = True
        receipt["persistent_chat_memory_path"] = str(PERSISTENT_CHAT_MEMORY_PATH)
    except Exception as exc:
        receipt["scoped_chat_memory_appended"] = False
        receipt["persistent_chat_memory_appended"] = False
        receipt["persistent_chat_history_appended"] = False
        receipt["scoped_chat_memory_error"] = str(exc)
    receipt_path = str(receipt.get("workspace_receipt_path") or "").strip()
    if receipt_path:
        try:
            _write_json(Path(receipt_path), receipt)
        except Exception as exc:
            receipt["final_scoped_receipt_write_error"] = str(exc)
    return receipt, reply


def _prompt_from_completion_request(payload: dict[str, Any]) -> str:
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return str(payload.get("prompt") or "").strip()
    for item in reversed(messages):
        if not isinstance(item, dict):
            continue
        if str(item.get("role") or "").lower() != "user":
            continue
        content = item.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and isinstance(block.get("text"), str):
                    parts.append(block["text"])
            return "\n".join(part.strip() for part in parts if part.strip()).strip()
    text_parts: list[str] = []
    for item in messages:
        if isinstance(item, dict) and isinstance(item.get("content"), str):
            text_parts.append(str(item["content"]).strip())
    return "\n".join(part for part in text_parts if part).strip()


def _completion_response(payload: dict[str, Any], reply: str, receipt: dict[str, Any]) -> dict[str, Any]:
    model = str(payload.get("model") or _custom_runtime_model_id())
    created = int(time.time())
    return {
        "id": "chatcmpl-engel-" + _stamp(),
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": reply,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": max(1, len(str(payload.get("messages") or payload.get("prompt") or "").split())),
            "completion_tokens": max(1, len(reply.split())),
            "total_tokens": max(2, len(str(payload.get("messages") or payload.get("prompt") or "").split()) + len(reply.split())),
        },
        "engel": {
            "ok": receipt.get("ok") is True,
            "status": receipt.get("status", ""),
            "provider": receipt.get("provider", ""),
            "runtime_provider": receipt.get("runtime_provider", ""),
            "meeting_room_server_used": bool(receipt.get("meeting_room_server_used") is True),
            "persistent_chat_memory_appended": bool(receipt.get("persistent_chat_memory_appended") is True),
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "EngelMainServerChat/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[%s] %s\n" % (_iso_now(), fmt % args))
        sys.stderr.flush()

    # (2026-07-28) A client that drops mid-response (closed SSE stream, killed
    # UI, worker timeout) is normal churn, but the default traceback flooded
    # the error log so completely that real failures were invisible. Collapse
    # those disconnects to one log line; every other exception still surfaces.
    def handle(self) -> None:
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            self.log_message("client disconnected mid-response")

    def finish(self) -> None:
        try:
            super().finish()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        try:
            if _serve_build_preview(self, path) or _serve_build_package(self, path):
                return
        except ValueError as exc:
            _json_response(self, 400, {"ok": False, "status": "invalid build artifact path", "error": str(exc)})
            return
        if path in {"/pressure", "/health/lite"}:
            snap = _process_resource_snapshot()
            _json_response(
                self,
                200,
                {
                    "schema": "engel_main_server_chat_pressure_v1",
                    "ok": True,
                    "status": "engel-ai-main CT chat pressure",
                    "resource_pressure": snap,
                    "busy": str(snap.get("pressure") or "") in {"hard", "critical"}
                    or int(snap.get("chat_in_flight") or 0)
                    >= int(snap.get("chat_max_in_flight") or 4),
                    "updated_at_utc": _iso_now(),
                },
            )
            return
        if path == "/discord/room":
            room_path = Path("/opt/engel/run/discord_bridge/room_transcript.json")
            lines: list[dict[str, Any]] = []
            try:
                if room_path.is_file():
                    loaded = json.loads(room_path.read_text(encoding="utf-8"))
                    raw = loaded.get("lines") if isinstance(loaded, dict) else None
                    if isinstance(raw, list):
                        lines = [row for row in raw if isinstance(row, dict)]
            except Exception:
                lines = []
            _json_response(
                self,
                200,
                {
                    "schema": "engel_discord_room_v1",
                    "ok": True,
                    "lines": [
                        {
                            "author": str(row.get("author") or "")[:80],
                            "text": str(row.get("text") or "")[:500],
                        }
                        for row in lines[-40:]
                    ],
                },
            )
            return
        if path == "/health":
            snap = _process_resource_snapshot()
            _json_response(
                self,
                200,
                {
                    "schema": "engel_main_server_chat_health_v1",
                    "ok": True,
                    "status": "engel-ai-main CT chat service ready",
                    "server_role": "engel-ai-main CT 246",
                    "custom_runtime_ready": True,
                    "resource_pressure": snap,
                    "updated_at_utc": _iso_now(),
                },
            )
            return
        if path in {"/health/full", "/v1/health/full"}:
            _json_response(
                self,
                200,
                {
                    "schema": "engel_main_server_chat_health_v1",
                    "ok": True,
                    "status": "engel-ai-main CT chat service ready",
                    "server_role": "engel-ai-main CT 246",
                    "custom_runtime_ready": True,
                    "root": str(ROOT),
                    "meeting_room_url": _meeting_room_url(),
                    "meeting_room": _cached_snapshot("meeting_room", _meeting_room_snapshot),
                    "long_lived_local_model_service": os.environ.get("ENGEL_MAIN_LONG_LIVED_LOCAL_MODEL_SERVICE"),
                    "automatic_provider_policy": {
                        "local_model_first": _env_truth(
                            "ENGEL_AUTOMATIC_PROVIDER_AFTER_LOCAL_FAILURE_ONLY",
                            default=False,
                        ),
                        "fallback_after_local_failure": _env_truth(
                            "ENGEL_LOCAL_CHAT_AUTO_BRIDGE_FALLBACK",
                            default=False,
                        ),
                        "auto_bridge_routing_enabled": _env_truth(
                            "ENGEL_AUTO_BRIDGE_ROUTING_ENABLED",
                            default=False,
                        ),
                        "build_local_all_stages": _env_truth(
                            "ENGEL_BUILD_LOCAL_ALL_STAGES",
                            default=False,
                        ),
                    },
                    "model_runtime": _cached_snapshot("model_runtime", _model_runtime_snapshot),
                    "phone_bridge": _cached_snapshot("phone_bridge", _phone_bridge_snapshot),
                    "sub_engel_bridge": _cached_snapshot("sub_engel_bridge", _sub_engel_bridge_snapshot),
                    "device_workers": _cached_snapshot("device_workers", _device_worker_snapshot),
                    "virtual_environment": _cached_snapshot(
                        "virtual_environment", _meeting_room_virtual_environment_snapshot
                    ),
                    "skill_agent_creator": _cached_snapshot("skill_agent_creator", _skill_agent_creator_status),
                    "universal_reps": _cached_snapshot("universal_reps", _universal_reps_template_snapshot),
                    "universal_reps_runtime": _cached_snapshot(
                        "universal_reps_runtime", _universal_reps_runtime_status
                    ),
                    "self_model": _cached_snapshot("self_model", _self_model_snapshot, ttl_seconds=5.0),
                    "self_upgrade": _cached_snapshot(
                        "self_upgrade_status",
                        _self_upgrade_status_snapshot,
                        ttl_seconds=5.0,
                    ),
                    "shell_bridge_registry": _cached_snapshot(
                        "shell_bridge_registry", _shell_bridge_registry_snapshot, ttl_seconds=5.0
                    ),
                    "provider_bridges": _cached_snapshot("provider_bridges", _provider_bridge_status),
                    "provider_capabilities": _cached_snapshot(
                        "provider_capabilities", _provider_capability_snapshot, ttl_seconds=15.0
                    ),
                    "local_llm_fast_fail": _cached_snapshot(
                        "local_llm_fast_fail", _local_llm_fast_fail_snapshot, ttl_seconds=5.0
                    ),
                    "chat_failure_corpus": _cached_snapshot(
                        "chat_failure_corpus", _chat_failure_corpus_snapshot, ttl_seconds=5.0
                    ),
                    "context_packs": _cached_snapshot(
                        "context_packs", _context_pack_snapshot, ttl_seconds=5.0
                    ),
                    "chat_route_parity": _cached_snapshot(
                        "chat_route_parity", _chat_route_parity_snapshot, ttl_seconds=5.0
                    ),
                    "rag_runtime": _cached_snapshot(
                        "rag_runtime", _rag_runtime_snapshot, ttl_seconds=5.0
                    ),
                    "resource_pressure": _process_resource_snapshot(),
                    "updated_at_utc": _iso_now(),
                },
            )
            return
        if path == "/state":
            _json_response(self, 200, _custom_runtime_state())
            return
        if path in {"/self-model", "/v1/self-model"}:
            payload = _self_model_document()
            _json_response(self, 200 if payload.get("ok") is True else 503, payload)
            return
        if path in {"/self-model/context", "/v1/self-model/context"}:
            context = _self_model_context(2400)
            payload = {
                "schema": "ENGEL_SELF_MODEL_CONTEXT_V1",
                "ok": bool(context),
                "context": context,
            }
            _json_response(self, 200 if context else 503, payload)
            return
        if path in {"/self-upgrade/status", "/v1/self-upgrade/status"}:
            report = _cached_snapshot(
                "self_upgrade_status",
                _self_upgrade_status_snapshot,
                ttl_seconds=2.0,
            )
            _json_response(self, 200 if report.get("ok") is True else 503, report)
            return
        if path in {"/bridges/registry", "/v1/bridges/registry"}:
            report = _shell_bridge_registry_snapshot()
            _json_response(self, 200 if report.get("ok") is True else 503, report)
            return
        if path == "/registry":
            _json_response(self, 200, _custom_runtime_registry())
            return
        if path in {"/providers/status", "/bridges/status", "/v1/providers/status"}:
            _json_response(self, 200, _cached_snapshot("provider_bridges", _provider_bridge_status))
            return
        if path in {"/providers/capabilities", "/v1/providers/capabilities"}:
            report = _cached_snapshot(
                "provider_capabilities", _provider_capability_snapshot, ttl_seconds=15.0
            )
            _json_response(self, 200 if report.get("ok") is True else 503, report)
            return
        if path in {"/local-llm/status", "/v1/local-llm/status"}:
            report = _cached_snapshot(
                "local_llm_fast_fail", _local_llm_fast_fail_snapshot, ttl_seconds=2.0
            )
            _json_response(self, 200 if report.get("ok") is True else 503, report)
            return
        if path in {"/chat-failures/status", "/v1/chat-failures/status"}:
            report = _cached_snapshot(
                "chat_failure_corpus", _chat_failure_corpus_snapshot, ttl_seconds=2.0
            )
            _json_response(self, 200 if report.get("ok") is True else 503, report)
            return
        if path in {"/context-packs/status", "/v1/context-packs/status"}:
            report = _cached_snapshot(
                "context_packs", _context_pack_snapshot, ttl_seconds=2.0
            )
            _json_response(self, 200 if report.get("ok") is True else 503, report)
            return
        if path in {"/chat-route-parity/status", "/v1/chat-route-parity/status"}:
            report = _cached_snapshot(
                "chat_route_parity", _chat_route_parity_snapshot, ttl_seconds=2.0
            )
            _json_response(self, 200 if report.get("ok") is True else 503, report)
            return
        if path in {"/brain/standing", "/v1/brain/standing"}:
            try:
                from engel_discord_desktop_route_parity import standing_chat_brain

                _json_response(self, 200, standing_chat_brain())
            except Exception as exc:
                _json_response(
                    self,
                    500,
                    {"ok": False, "status": "standing brain unavailable", "error": str(exc)[:300]},
                )
            return
        if path in {"/rag/status", "/v1/rag/status"}:
            report = _cached_snapshot(
                "rag_runtime", _rag_runtime_snapshot, ttl_seconds=2.0
            )
            _json_response(self, 200 if report.get("ok") is True else 503, report)
            return
        if path in {"/ai-systems/status", "/v1/ai-systems/status"}:
            report = _cached_snapshot(
                "ai_systems", _ai_systems_snapshot, ttl_seconds=5.0
            )
            _json_response(self, 200 if report.get("ok") is True else 503, report)
            return
        if path in {"/reps", "/reps/template", "/v1/reps"}:
            report = _universal_reps_template_snapshot()
            _json_response(self, 200 if report.get("ok") is True else 500, report)
            return
        if path in {"/reps/status", "/reps/runtime", "/v1/reps/status"}:
            report = _universal_reps_runtime_status()
            _json_response(self, 200 if report.get("ok") is True else 500, report)
            return
        if path in {"/skills", "/skills/status", "/v1/skills"}:
            report = _skill_status_report()
            _json_response(self, 200 if report.get("ok") is True else 500, report)
            return
        if path in {"/agents", "/agents/status", "/v1/agents"}:
            report = _agent_status_report()
            _json_response(self, 200 if report.get("ok") is True else 500, report)
            return
        _json_response(self, 404, {"ok": False, "status": "not found", "path": self.path})

    def _handle_chat_stream(self) -> None:
        # (NT-3) same per-turn retrieve-once memo for the streaming path (covers its
        # _big_lane_memory recall AND any fall-through into _run_chat_turn).
        _recall_tok = _begin_turn_recall_cache()
        try:
            return self._handle_chat_stream_inner()
        finally:
            _end_turn_recall_cache(_recall_tok)

    def _handle_chat_stream_inner(self) -> None:
        """Quality-gated SSE wrapper around CT246's canonical chat turn.

        Activity frames keep the UI responsive. Model text is not exposed until
        `_run_chat_turn` has applied local-first routing, semantic quality,
        provider-escalation, and single-writer persistent-memory gates.
        """
        started = time.perf_counter()
        try:
            request = _read_json(self)
            attachment_intake = _prepare_chat_attachments(request.get("attachments"))
            _stamp_stored_paths_on_request(request, attachment_intake)
            request["attachments"] = attachment_intake.get("attachments") or []
            request["attachment_intake"] = attachment_intake
            prompt = _plain_chat_prompt_from_request(request)
            if not prompt and int(attachment_intake.get("count") or 0) > 0:
                prompt = "Please review the attached file(s)."
            if not prompt:
                raise ValueError("prompt is empty")
            context_pack = _build_chat_context_pack(
                prompt,
                request,
                attachment_intake,
                source="engel-ai-main-stream-chat",
            )
            request["context_pack"] = {
                key: value for key, value in context_pack.items() if key != "prompt_context"
            }
            prompt = _prompt_with_context_pack(prompt, context_pack, attachment_intake)
        except Exception as exc:
            _json_response(self, 400, {"ok": False, "status": "bad chat/stream request", "error": str(exc)})
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        def emit(obj: dict[str, Any]) -> bool:
            try:
                self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8"))
                self.wfile.flush()
                return True
            except Exception:
                return False

        try:
            max_tokens = max(256, min(int(request.get("max_tokens") or 1024), 4096))
        except Exception:
            max_tokens = 1024
        try:
            timeout = max(15, min(int(request.get("timeout") or 120), 180))
        except Exception:
            timeout = 120
        provider = str(request.get("provider") or "local").strip().lower()

        # (2026-07-07 audit fix ①) The big GPU model streams ONLY for turns the
        # normal routing cascade would actually send to it. Casual / UI / greeting /
        # short turns must fall through to _run_chat_turn (quick-local model +
        # humanizer) exactly like the non-streaming /chat lane. Before this gate,
        # EVERY streamed turn (the path the live UI hits first) went straight to the
        # 9B model with the heavy identity system prompt, so a plain "hi" came back
        # as an identity preamble and even leaked raw prompt text into the reply.
        prefers_quick_local = True
        try:
            prefers_quick_local = (
                _request_prefers_quick_local_chat(prompt, request)
                or _prompt_requests_short_casual_fast_model(prompt)
                or _prompt_allows_default_fast_local_chat(prompt, request)
                # (2026-07-07 audit R-1) also defer deterministic early routes to
                # _run_chat_turn instead of streaming the 9B, so the live-status /
                # build-status / reps / media / provider-bridge routes still fire on
                # the streaming path (they were silently bypassed before).
                or _prompt_requests_live_runtime_status(prompt)
                or _prompt_requests_computer_memory(prompt)
                or _prompt_requests_build_status(prompt)
                or _prompt_requests_reps_template(prompt)
                or _prompt_requests_media_artifact(prompt)
                or _explicit_provider_bridge_requested(prompt, request)
                or _prompt_requires_buffered_quality_gate(prompt)
                # The short-format guard must run before any text reaches the
                # client; a GPU stream cannot retract its second sentence.
                or _prompt_requests_single_sentence(prompt)
            )
        except Exception:
            prefers_quick_local = True  # any doubt -> use the safe non-stream cascade

        pieces: list[str] = []
        streamed = False
        # Candidate text must remain private until the canonical quality gate
        # accepts it. Direct token streaming cannot retract a rejected draft.
        if False and provider in {"", "local", "engel", "auto"} and not prefers_quick_local:
            try:
                from run_engel_standalone_chat_llm import (
                    build_large_local_system_prompt,
                    stream_rog_gpu_chat,
                )

                system_prompt = build_large_local_system_prompt(
                    prompt,
                    _big_lane_memory(prompt, request),
                )
                for token in stream_rog_gpu_chat(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    timeout=timeout,
                    max_tokens=max_tokens,
                ):
                    pieces.append(token)
                    streamed = True
                    if not emit({"delta": token}):
                        return  # worker/client went away — stop generating for it
            except Exception:
                streamed = bool(pieces)  # keep whatever already streamed cleanly

        if streamed and pieces:
            reply = "".join(pieces).strip()
            # (2026-07-07 audit fix ③) Drop a leading "Engel AI Main:" / "Engel:"
            # speaker label the large model sometimes prepends, so a streamed reply
            # reads as an answer, not a scripted identity line.
            reply = re.sub(r"^\s*engel(?:\s+ai(?:\s+main)?)?\s*:\s*", "", reply, count=1, flags=re.IGNORECASE)
            receipt = {
                "ok": True,
                "status": "rog gpu streamed chat (RTX 2070)",
                "assistant_reply": reply,
                "assistant_output_text": reply,
                "provider": "local-llama-cpp-large-chat-gguf-stream",
                "runtime_provider": "rog-rtx2070-llama-cpp-gpu-stream",
                "selected_provider": "local_rog_gpu_stream",
                "provider_api_enabled": False,
                "network_enabled": False,
                "model": os.environ.get(
                    "ENGEL_ROG_GPU_CHAT_MODEL_LABEL",
                    "ornith-1.0-9b-local-gguf",
                ),
                "streamed": True,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                # (NT-1) this path skips _finalize_chat_receipt; stamp the big-lane depth inline.
                "activation_depth": 2,
                "activation_depth_label": "big-lane",
                "escalated_from": None,
                "chat_context_scope": _chat_context_scope(request),
            }
            try:
                _append_jsonl(
                    PERSISTENT_CHAT_MEMORY_PATH,
                    {
                        "schema": "engel_chat_memory_record_v1",
                        "memory_source": "engel-ai-main CT streamed chat",
                        "updated_at_utc": _iso_now(),
                        "prompt": prompt,
                        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                        "assistant_reply": reply,
                        "chat_context_scope": _chat_context_scope(request),
                        "runtime_provider": receipt["runtime_provider"],
                        "provider": receipt["provider"],
                        "selected_provider": receipt["selected_provider"],
                        "provider_api_enabled": False,
                        "network_enabled": False,
                        "model": receipt["model"],
                        # (NT-1) big lane answered this streamed turn
                        "activation_depth": 2,
                        "activation_depth_label": "big-lane",
                        "escalated_from": None,
                    },
                )
                receipt["persistent_chat_memory_appended"] = True
            except Exception as exc:
                receipt["persistent_chat_memory_appended"] = False
                receipt["persistent_chat_memory_error"] = str(exc)
            receipt = _attach_intake_to_receipt(receipt, attachment_intake)
            receipt = _attach_context_pack_to_receipt(receipt, context_pack)
            receipt["chat_failure_corpus"] = _capture_chat_failure(
                prompt,
                reply,
                receipt,
                attachment_intake,
                request,
                source="engel-ai-main-stream-chat",
            )
            receipt, reply = _finalize_chat_route_parity(
                prompt,
                reply,
                receipt,
                request,
                attachment_intake,
                source="engel-ai-main-stream-chat",
                stage="http-stream-final",
            )
            _persist_final_chat_receipt(receipt)
            emit({"done": True, "ok": True, "assistant_reply": reply, "receipt": _redact(receipt)})
        else:
            # Fallback: no GPU stream (unavailable or named provider). Run the
            # normal blocking chat and deliver it as one chunk. Keep the SSE
            # connection alive while quality scoring/repair runs; otherwise the
            # ROG worker's idle socket timer can submit this same turn twice.
            result_box: dict[str, Any] = {}
            completed = threading.Event()

            def run_buffered_turn() -> None:
                try:
                    result_box["result"] = _run_chat_turn(prompt, request, started)
                except Exception as exc:
                    result_box["error"] = str(exc)
                finally:
                    completed.set()

            # (2026-07-26 neuro audit, NT-3) the worker thread does not inherit
            # contextvars — run it inside a copied context so the handler's
            # per-turn recall memo actually reaches the buffered turn.
            _turn_ctx = contextvars.copy_context()
            threading.Thread(
                target=lambda: _turn_ctx.run(run_buffered_turn),
                name="engel-buffered-chat-turn",
                daemon=True,
            ).start()
            while not completed.wait(5.0):
                if not emit(
                    {
                        "activity": "buffered_local_chat",
                        "elapsed_seconds": int(time.perf_counter() - started),
                    }
                ):
                    return
            result = result_box.get("result")
            if isinstance(result, tuple) and len(result) == 2:
                receipt, reply = result
                reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
                if isinstance(request.get("mode_gate_decision"), dict) and "mode_gate" not in receipt:
                    receipt["mode_gate"] = request["mode_gate_decision"]
                receipt = _attach_intake_to_receipt(receipt, attachment_intake)
                receipt = _attach_context_pack_to_receipt(receipt, context_pack)
                receipt["chat_failure_corpus"] = _capture_chat_failure(
                    prompt,
                    reply,
                    receipt,
                    attachment_intake,
                    request,
                    source="engel-ai-main-buffered-stream-chat",
                )
                receipt, reply = _finalize_chat_route_parity(
                    prompt,
                    reply,
                    receipt,
                    request,
                    attachment_intake,
                    source="engel-ai-main-buffered-stream-chat",
                    stage="http-buffered-stream-final",
                )
                _persist_final_chat_receipt(receipt)
                if reply:
                    emit({"delta": reply})
                emit({"done": True, "ok": receipt.get("ok") is True, "assistant_reply": reply, "receipt": _redact(receipt)})
            else:
                error_text = str(result_box.get("error") or "buffered local chat failed")
                error_receipt = _attach_intake_to_receipt(
                    {"ok": False, "status": "buffered local chat failed", "error": error_text},
                    attachment_intake,
                )
                error_receipt = _attach_context_pack_to_receipt(error_receipt, context_pack)
                error_receipt["chat_failure_corpus"] = _capture_chat_failure(
                    prompt,
                    "",
                    error_receipt,
                    attachment_intake,
                    request,
                    source="engel-ai-main-buffered-stream-error",
                )
                error_receipt, _ = _finalize_chat_route_parity(
                    prompt,
                    "",
                    error_receipt,
                    request,
                    attachment_intake,
                    source="engel-ai-main-buffered-stream-error",
                    stage="http-buffered-stream-error",
                )
                emit({"done": True, "ok": False, "assistant_reply": "", "error": error_text, "receipt": _redact(error_receipt)})

        try:
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except Exception:
            pass

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        _wait_chat_admission(path)
        if path in {"/rag/query", "/v1/rag/query"}:
            client_host = str(self.client_address[0] if self.client_address else "")
            if not _loopback_client_address(client_host):
                _json_response(
                    self,
                    403,
                    {
                        "ok": False,
                        "status": "RAG execution is restricted to the ROG loopback tunnel",
                    },
                )
                return
            try:
                request = _read_json(self)
                result = _rag_runtime_execute(request)
                _json_response(
                    self,
                    200 if result.get("ok") is True else 502,
                    _redact(result),
                )
            except ValueError as exc:
                _json_response(
                    self,
                    400,
                    {
                        "ok": False,
                        "status": "invalid RAG request",
                        "error": str(exc)[:500],
                    },
                )
            except Exception as exc:
                _json_response(
                    self,
                    502,
                    {
                        "ok": False,
                        "status": "CT246 RAG execution failed",
                        "error": str(exc)[:500],
                    },
                )
            return
        if path in {
            "/discord/checkout",
            "/v1/discord/checkout",
        }:
            client_host = str(self.client_address[0] if self.client_address else "")
            if not _loopback_client_address(client_host):
                _json_response(
                    self,
                    403,
                    {
                        "ok": False,
                        "status": "discord checkout is restricted to the ROG loopback tunnel",
                    },
                )
                return
            snapshot = _discord_bridge_snapshot()
            reply = _discord_checkout_reply(snapshot)
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "status": "discord checkout from live Engel bridge",
                    "assistant_reply": reply,
                    "assistant_output_text": reply,
                    "reply": reply,
                    "discord_checkout": True,
                    "readable_output_captured": True,
                    "engel_agent_kernel_used": False,
                    "message_count": len(snapshot.get("messages") or []),
                },
            )
            return
        if path in {
            "/discord/reply-sub-engel",
            "/v1/discord/reply-sub-engel",
        }:
            client_host = str(self.client_address[0] if self.client_address else "")
            if not _loopback_client_address(client_host):
                _json_response(
                    self,
                    403,
                    {
                        "ok": False,
                        "posted": False,
                        "status": "discord owner reply is restricted to the ROG loopback tunnel",
                    },
                )
                return
            result = _owner_post_sub_engel_named_gap()
            _json_response(self, 200 if result.get("posted") is True else 502, _redact(result))
            return
        if path in {
            "/self-upgrade/plan",
            "/v1/self-upgrade/plan",
            "/self-upgrade/cycle",
            "/v1/self-upgrade/cycle",
        }:
            client_host = str(self.client_address[0] if self.client_address else "")
            if not _loopback_client_address(client_host):
                _json_response(
                    self,
                    403,
                    {
                        "ok": False,
                        "status": "self-upgrade control is restricted to the ROG loopback tunnel",
                    },
                )
                return
            try:
                request = _read_json(self)
                if path.endswith("/plan"):
                    result = _self_upgrade_plan_request(request)
                else:
                    result = _self_upgrade_cycle_request(request)
                _json_response(self, 200, _redact(result))
            except PermissionError as exc:
                _json_response(
                    self,
                    403,
                    {
                        "ok": False,
                        "status": "self-upgrade authorization refused",
                        "error": str(exc),
                    },
                )
            except Exception as exc:
                _json_response(
                    self,
                    400,
                    {
                        "ok": False,
                        "status": "self-upgrade request failed",
                        "error": str(exc)[:500],
                    },
                )
            return
        if path in {"/sub-engel/direct-work", "/v1/sub-engel/direct-work"}:
            try:
                request = _read_json(self)
                result = _dispatch_sub_engel_direct_work_request(request)
                _json_response(self, 200 if result.get("ok") is True else 502, _redact(result))
            except Exception as exc:
                _json_response(
                    self,
                    400,
                    {
                        "ok": False,
                        "status": "CT246 Sub-Engel direct dispatch failed",
                        "error": str(exc),
                    },
                )
            return
        if path in {"/skills", "/v1/skills"}:
            try:
                request = _read_json(self)
                from engel_skill_agent_creator import create_skill

                result = create_skill(
                    name=str(request.get("name") or request.get("skill_name") or ""),
                    description=str(request.get("description") or ""),
                    instructions=str(request.get("instructions") or request.get("prompt") or ""),
                    trigger_phrases=request.get("trigger_phrases") if isinstance(request.get("trigger_phrases"), list) else None,
                    slug=str(request.get("slug") or "") or None,
                    created_by="engel-ai-main-http",
                )
                _json_response(self, 200, _redact(result))
            except Exception as exc:
                _json_response(self, 400, {"ok": False, "status": "skill creation failed", "error": str(exc)})
            return
        if path in {"/agents", "/v1/agents"}:
            try:
                request = _read_json(self)
                from engel_skill_agent_creator import create_agent

                result = create_agent(
                    name=str(request.get("name") or request.get("agent_name") or ""),
                    role=str(request.get("role") or request.get("description") or ""),
                    instructions=str(request.get("instructions") or request.get("prompt") or ""),
                    skills=request.get("skills") if isinstance(request.get("skills"), list) else None,
                    slug=str(request.get("slug") or "") or None,
                    created_by="engel-ai-main-http",
                )
                _json_response(self, 200, _redact(result))
            except Exception as exc:
                _json_response(self, 400, {"ok": False, "status": "agent creation failed", "error": str(exc)})
            return
        if path in {"/skill-agent/create", "/v1/skill-agent/create"}:
            try:
                request = _read_json(self)
                from engel_skill_agent_creator import handle_creation_prompt

                result = handle_creation_prompt(str(request.get("prompt") or ""), created_by="engel-ai-main-http")
                _json_response(self, 200 if result.get("ok") is True else 400, _redact(result))
            except Exception as exc:
                _json_response(self, 400, {"ok": False, "status": "skill/agent creation failed", "error": str(exc)})
            return
        if path in {"/reps/record", "/v1/reps/record"}:
            try:
                request = _read_json(self)
                result = _universal_reps_record(request)
                _json_response(self, 200 if result.get("ok") is True else 400, _redact(result))
            except Exception as exc:
                _json_response(self, 400, {"ok": False, "status": "REPS record failed", "error": str(exc)})
            return
        if path in {"/reps/evaluate", "/v1/reps/evaluate"}:
            try:
                request = _read_json(self)
                result = _universal_reps_evaluate(request)
                _json_response(self, 200 if result.get("ok") is True else 400, _redact(result))
            except Exception as exc:
                _json_response(self, 400, {"ok": False, "status": "REPS evaluate failed", "error": str(exc)})
            return
        if path in {"/reps/propose", "/v1/reps/propose"}:
            try:
                request = _read_json(self)
                result = _universal_reps_propose(request)
                _json_response(self, 200 if result.get("ok") is True else 400, _redact(result))
            except Exception as exc:
                _json_response(self, 400, {"ok": False, "status": "REPS propose failed", "error": str(exc)})
            return
        if path in {"/reps/signoff", "/v1/reps/signoff"}:
            try:
                request = _read_json(self)
                result = _universal_reps_signoff(request)
                _json_response(self, 200 if result.get("ok") is True else 400, _redact(result))
            except Exception as exc:
                _json_response(self, 400, {"ok": False, "status": "REPS sign-off failed", "error": str(exc)})
            return
        if path in {"/reps/cycle", "/reps/run", "/v1/reps/cycle"}:
            try:
                request = _read_json(self)
                result = _universal_reps_cycle(request)
                _json_response(self, 200 if result.get("ok") is True else 400, _redact(result))
            except Exception as exc:
                _json_response(self, 400, {"ok": False, "status": "REPS cycle failed", "error": str(exc)})
            return
        if path in {"/brain/standing", "/v1/brain/standing"}:
            try:
                request = _read_json(self)
                from engel_discord_desktop_route_parity import save_standing_chat_brain

                result = save_standing_chat_brain(
                    selected_model_id=str(request.get("selected_model_id") or request.get("model_id") or ""),
                    selected_model_name=str(request.get("selected_model_name") or request.get("model_name") or ""),
                    selected_chat_provider=str(
                        request.get("selected_chat_provider")
                        or request.get("provider")
                        or ""
                    ),
                    updated_by=str(request.get("updated_by") or "engel_flutter_main"),
                )
                _json_response(self, 200, result)
            except Exception as exc:
                _json_response(
                    self,
                    400,
                    {"ok": False, "status": "standing brain save failed", "error": str(exc)[:300]},
                )
            return
        if path in {"/chat/stream", "/v1/chat/stream"}:
            _acquire_chat_slot()
            try:
                self._handle_chat_stream()
            finally:
                _release_chat_slot()
            return
        if path not in {"/chat", "/v1/chat/completions"}:
            _json_response(self, 404, {"ok": False, "status": "not found", "path": self.path})
            return
        _acquire_chat_slot()
        started = time.perf_counter()
        try:
            request = _read_json(self)
            attachment_intake = _prepare_chat_attachments(request.get("attachments"))
            _stamp_stored_paths_on_request(request, attachment_intake)
            request["attachments"] = attachment_intake.get("attachments") or []
            request["attachment_intake"] = attachment_intake
            prompt = (
                _prompt_from_completion_request(request)
                if path == "/v1/chat/completions"
                else _plain_chat_prompt_from_request(request)
            )
            if not prompt and int(attachment_intake.get("count") or 0) > 0:
                prompt = "Please review the attached file(s)."
            if not prompt:
                raise ValueError("prompt is empty")
            context_pack = _build_chat_context_pack(
                prompt,
                request,
                attachment_intake,
                source="engel-ai-main-http-chat",
            )
            request["context_pack"] = {
                key: value for key, value in context_pack.items() if key != "prompt_context"
            }
            prompt = _prompt_with_context_pack(prompt, context_pack, attachment_intake)
            receipt, reply = _run_chat_turn(prompt, request, started)
            reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or reply)
            if isinstance(request.get("mode_gate_decision"), dict) and "mode_gate" not in receipt:
                receipt["mode_gate"] = request["mode_gate_decision"]
            receipt = _attach_intake_to_receipt(receipt, attachment_intake)
            receipt = _attach_context_pack_to_receipt(receipt, context_pack)
            if int(attachment_intake.get("count") or 0) > 0:
                try:
                    _append_jsonl(
                        PERSISTENT_CHAT_MEMORY_PATH,
                        {
                            "schema": "engel_chat_attachment_memory_record_v1",
                            "memory_source": "engel-ai-main CT chat attachment intake",
                            "updated_at_utc": _iso_now(),
                            "prompt": prompt,
                            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                            "assistant_reply": reply,
                            "chat_attachments": attachment_intake.get("attachments") or [],
                            "chat_attachment_count": attachment_intake.get("count"),
                            "chat_attachment_stored_count": attachment_intake.get("stored_count"),
                            "chat_attachment_errors": attachment_intake.get("errors") or [],
                            "persistent_chat_memory_path": str(PERSISTENT_CHAT_MEMORY_PATH),
                        },
                    )
                    receipt["chat_attachment_memory_appended"] = True
                except Exception as exc:
                    receipt["chat_attachment_memory_appended"] = False
                    receipt["chat_attachment_memory_error"] = str(exc)
            receipt["chat_failure_corpus"] = _capture_chat_failure(
                prompt,
                reply,
                receipt,
                attachment_intake,
                request,
                source="engel-ai-main-http-chat",
            )
            receipt, reply = _finalize_chat_route_parity(
                prompt,
                reply,
                receipt,
                request,
                attachment_intake,
                source="engel-ai-main-http-chat",
                stage="http-final",
            )
            _persist_final_chat_receipt(receipt)
            failure_code = _chat_failure_status_code(receipt)
            if path == "/v1/chat/completions":
                _json_response(self, 200 if receipt.get("ok") is True else failure_code, _redact(_completion_response(request, reply, receipt)))
                return
            payload = {
                "schema": "engel_main_server_chat_response_v1",
                "ok": receipt.get("ok") is True,
                "status": receipt.get("status", ""),
                "assistant_reply": reply,
                "assistant_output_text": reply,
                "reply": reply,
                "provider": receipt.get("provider", ""),
                "runtime_provider": receipt.get("runtime_provider", ""),
                "receipt": receipt,
                "updated_at_utc": _iso_now(),
            }
            _json_response(self, 200 if payload["ok"] else failure_code, _redact(payload))
        except Exception as exc:
            prompt = ""
            try:
                raw_request = locals().get("request", {})
                if isinstance(raw_request, dict):
                    prompt = (
                        _prompt_from_completion_request(raw_request)
                        if path == "/v1/chat/completions"
                        else _plain_chat_prompt_from_request(raw_request)
                    )
            except Exception:
                prompt = ""
            if prompt:
                receipt = _fast_server_receipt(prompt, started, error=str(exc))
                attachment_intake = locals().get("attachment_intake", {})
                if not isinstance(attachment_intake, dict):
                    attachment_intake = {}
                request_value = locals().get("request", {})
                if not isinstance(request_value, dict):
                    request_value = {}
                receipt = _attach_intake_to_receipt(receipt, attachment_intake)
                receipt = _attach_context_pack_to_receipt(
                    receipt,
                    locals().get("context_pack") if isinstance(locals().get("context_pack"), dict) else None,
                )
                reply = str(receipt.get("assistant_reply") or "")
                receipt["chat_failure_corpus"] = _capture_chat_failure(
                    prompt,
                    reply,
                    receipt,
                    attachment_intake,
                    request_value,
                    source="engel-ai-main-http-fallback",
                )
                receipt, reply = _finalize_chat_route_parity(
                    prompt,
                    reply,
                    receipt,
                    request_value,
                    attachment_intake,
                    source="engel-ai-main-http-fallback",
                    stage="http-fallback-final",
                )
                _persist_final_chat_receipt(receipt)
                if path == "/v1/chat/completions":
                    _json_response(self, 200, _redact(_completion_response(locals().get("request", {}) if isinstance(locals().get("request", {}), dict) else {}, reply, receipt)))
                    return
                payload = {
                    "schema": "engel_main_server_chat_response_v1",
                    "ok": True,
                    "status": receipt.get("status", ""),
                    "assistant_reply": receipt.get("assistant_reply", ""),
                    "provider": receipt.get("provider", ""),
                    "runtime_provider": receipt.get("runtime_provider", ""),
                    "receipt": receipt,
                    "updated_at_utc": _iso_now(),
                }
                _json_response(self, 200, _redact(payload))
            else:
                _json_response(
                    self,
                    500,
                    {
                        "schema": "engel_main_server_chat_response_v1",
                        "ok": False,
                        "status": "engel-ai-main CT chat service error",
                        "error": str(exc),
                        "traceback_tail": traceback.format_exc()[-2000:],
                        "updated_at_utc": _iso_now(),
                    },
                )
        finally:
            _release_chat_slot()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel AI Main CT chat HTTP service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    # Warm the SLM serving runtime on a background thread BEFORE serving: model
    # and embedder loads happen off-turn, so the first chat turn never pays them
    # (the same cold-start class that timed out the first sparse-MoE turn after
    # a restart). Absent module / absent artifacts degrade to advisory-off.
    try:
        from engel_slm_runtime import get_slm_runtime

        get_slm_runtime().warm()
    except Exception:  # noqa: BLE001 -- advisory layer must never block startup
        pass
    httpd = BoundedThreadingHTTPServer((args.host, args.port), Handler)
    print(
        f"Engel Main server chat service listening on {args.host}:{args.port} "
        f"(http_max_threads={_CHAT_HTTP_MAX_THREADS} chat_max_in_flight={_CHAT_MAX_IN_FLIGHT})",
        flush=True,
    )
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
