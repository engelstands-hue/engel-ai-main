#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(os.environ.get("ENGEL_ROOT") or Path(__file__).resolve().parents[1])
DEFAULT_STATE_ROOT = ROOT / "run" / "self_update" / "local_llm_fast_fail"

_LOCK = threading.RLock()
_ACTIVE: dict[str, dict[str, Any]] = {}
_TIMED_OUT: set[str] = set()
_LAST_OUTCOME: dict[str, Any] = {}
_CIRCUIT_OPEN_UNTIL = 0.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return _now().strftime("%Y%m%dT%H%M%S%fZ") + f"_p{os.getpid()}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _state_root(value: str | Path | None = None) -> Path:
    return Path(value or os.environ.get("ENGEL_LOCAL_LLM_FAST_FAIL_ROOT") or DEFAULT_STATE_ROOT)


def _float_env(name: str, default: float, *, minimum: float, maximum: float) -> float:
    try:
        value = float(str(os.environ.get(name, "")).strip() or default)
    except (TypeError, ValueError):
        value = default
    return min(maximum, max(minimum, value))


def _int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(float(str(os.environ.get(name, "")).strip() or default))
    except (TypeError, ValueError):
        value = default
    return min(maximum, max(minimum, value))


def effective_timeout_seconds(requested: float | int | None, hard_cap: float | None = None) -> float:
    cap = hard_cap if hard_cap is not None else _float_env(
        "ENGEL_LOCAL_LLM_HARD_DEADLINE_SECONDS",
        45.0,
        minimum=5.0,
        maximum=120.0,
    )
    cap = max(0.01, float(cap))
    try:
        requested_value = float(requested if requested is not None else cap)
    except (TypeError, ValueError):
        requested_value = cap
    return max(0.01, min(requested_value, cap))


def _attempt_id(operation: str) -> str:
    seed = f"{operation}|{_iso()}|{time.perf_counter_ns()}|{os.getpid()}"
    return "local_llm_attempt_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _failure_receipts(
    *,
    state_root: Path,
    attempt_id: str,
    operation: str,
    failure_kind: str,
    timeout_seconds: float,
    elapsed_ms: int,
    fallback_allowed: bool,
    error: str = "",
) -> tuple[Path, Path]:
    created = _iso()
    issue_path = state_root / "issues" / f"ENGEL_LOCAL_LLM_ISSUE_{_stamp()}.json"
    fallback_path = state_root / "fallbacks" / f"ENGEL_LOCAL_LLM_FALLBACK_{_stamp()}.json"
    common = {
        "attempt_id": attempt_id,
        "operation": operation,
        "failure_kind": failure_kind,
        "timeout_seconds": round(timeout_seconds, 3),
        "elapsed_ms": elapsed_ms,
        "created_at_utc": created,
        "provider_called": False,
        "prompt_or_reply_stored": False,
        "credential_metadata_stored": False,
        "active_runtime_root": str(ROOT),
        "storage_mutation": False,
        "external_array_used": False,
    }
    issue = {
        "schema": "ENGEL_LOCAL_LLM_FAST_FAIL_ISSUE_V1",
        "ok": False,
        "status": "local LLM fast-fail issue recorded",
        **common,
        "error": str(error or "")[:1000],
    }
    fallback = {
        "schema": "ENGEL_LOCAL_LLM_FALLBACK_PROOF_V1",
        "ok": True,
        "status": "fallback decision pending",
        **common,
        "fallback_allowed": bool(fallback_allowed),
        "fallback_attempted": False,
        "fallback_completed": False,
        "provider_id": "",
        "finalized": False,
    }
    _write_json(issue_path, issue)
    _write_json(fallback_path, fallback)
    return issue_path, fallback_path


def _fast_failure(
    *,
    state_root: Path,
    attempt_id: str,
    operation: str,
    failure_kind: str,
    timeout_seconds: float,
    elapsed_ms: int,
    fallback_allowed: bool,
    error: str = "",
) -> dict[str, Any]:
    issue_path, fallback_path = _failure_receipts(
        state_root=state_root,
        attempt_id=attempt_id,
        operation=operation,
        failure_kind=failure_kind,
        timeout_seconds=timeout_seconds,
        elapsed_ms=elapsed_ms,
        fallback_allowed=fallback_allowed,
        error=error,
    )
    return {
        "schema": "ENGEL_LOCAL_LLM_FAST_FAIL_RESULT_V1",
        "ok": False,
        "completed": False,
        "timed_out": failure_kind == "timeout",
        "circuit_open": failure_kind == "circuit_open",
        "busy": failure_kind == "busy",
        "status": f"local LLM {failure_kind.replace('_', ' ')}",
        "attempt_id": attempt_id,
        "operation": operation,
        "timeout_seconds": round(timeout_seconds, 3),
        "elapsed_ms": elapsed_ms,
        "error": str(error or "")[:1000],
        "fallback_allowed": bool(fallback_allowed),
        "provider_called": False,
        "issue_receipt_path": str(issue_path),
        "fallback_proof_path": str(fallback_path),
    }


def run_with_deadline(
    operation: str,
    task: Callable[[], Any],
    *,
    requested_timeout: float | int | None,
    fallback_allowed: bool,
    state_root: str | Path | None = None,
    hard_cap: float | None = None,
    cooldown_seconds: float | None = None,
    max_in_flight: int | None = None,
    busy_wait_seconds: float | None = None,
) -> dict[str, Any]:
    """Run one local-model operation behind a wall-clock deadline and circuit.

    The task runs on a daemon thread so an uncooperative backend cannot hold the
    user request open. A timed-out task is never treated as a successful reply.
    """
    global _CIRCUIT_OPEN_UNTIL, _LAST_OUTCOME

    root = _state_root(state_root)
    timeout_seconds = effective_timeout_seconds(requested_timeout, hard_cap)
    cooldown = cooldown_seconds if cooldown_seconds is not None else _float_env(
        "ENGEL_LOCAL_LLM_TIMEOUT_COOLDOWN_SECONDS",
        30.0,
        minimum=0.0,
        maximum=300.0,
    )
    in_flight_limit = max_in_flight if max_in_flight is not None else _int_env(
        "ENGEL_LOCAL_LLM_MAX_IN_FLIGHT",
        1,
        minimum=1,
        maximum=4,
    )
    wait_busy = busy_wait_seconds if busy_wait_seconds is not None else _float_env(
        "ENGEL_LOCAL_LLM_BUSY_WAIT_SECONDS",
        12.0,
        minimum=0.0,
        maximum=30.0,
    )
    operation_name = str(operation or "local-chat")[:120]
    attempt_id = _attempt_id(operation_name)
    started = time.perf_counter()
    slot_deadline = time.monotonic() + max(0.0, float(wait_busy))

    while True:
        with _LOCK:
            now_mono = time.monotonic()
            if now_mono < _CIRCUIT_OPEN_UNTIL:
                result = _fast_failure(
                    state_root=root,
                    attempt_id=attempt_id,
                    operation=operation_name,
                    failure_kind="circuit_open",
                    timeout_seconds=timeout_seconds,
                    elapsed_ms=int((time.perf_counter() - started) * 1000),
                    fallback_allowed=fallback_allowed,
                    error="previous local-model timeout is still in cooldown",
                )
                _LAST_OUTCOME = dict(result)
                return result
            if len(_ACTIVE) < max(1, int(in_flight_limit)):
                _ACTIVE[attempt_id] = {
                    "operation": operation_name,
                    "started_at_utc": _iso(),
                    "timeout_seconds": round(timeout_seconds, 3),
                }
                break
            if now_mono >= slot_deadline:
                result = _fast_failure(
                    state_root=root,
                    attempt_id=attempt_id,
                    operation=operation_name,
                    failure_kind="busy",
                    timeout_seconds=timeout_seconds,
                    elapsed_ms=int((time.perf_counter() - started) * 1000),
                    fallback_allowed=fallback_allowed,
                    error="local-model in-flight limit reached",
                )
                _LAST_OUTCOME = dict(result)
                return result
        time.sleep(0.05)

    box: dict[str, Any] = {}
    done = threading.Event()

    def worker() -> None:
        global _LAST_OUTCOME
        try:
            box["value"] = task()
        except Exception as exc:  # the caller receives a bounded structured failure
            box["error"] = str(exc)
        finally:
            done.set()
            with _LOCK:
                _ACTIVE.pop(attempt_id, None)
                if attempt_id not in _TIMED_OUT:
                    _LAST_OUTCOME = {
                        "schema": "ENGEL_LOCAL_LLM_FAST_FAIL_RESULT_V1",
                        "ok": "error" not in box,
                        "completed": True,
                        "timed_out": False,
                        "attempt_id": attempt_id,
                        "operation": operation_name,
                        "status": "local LLM completed" if "error" not in box else "local LLM raised an error",
                        "elapsed_ms": int((time.perf_counter() - started) * 1000),
                    }

    thread = threading.Thread(
        target=worker,
        name=f"engel-local-llm-{attempt_id[-8:]}",
        daemon=True,
    )
    thread.start()
    finished = done.wait(timeout_seconds)
    if not finished:
        # Boundary grace: recover a task that completed while the deadline wait
        # was returning instead of discarding a finished reply. Kept proportional
        # and tiny so fail-fast timing still holds.
        finished = done.wait(min(0.1, timeout_seconds * 0.1))
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    if not finished:
        with _LOCK:
            _TIMED_OUT.add(attempt_id)
            _ACTIVE.pop(attempt_id, None)
            _CIRCUIT_OPEN_UNTIL = max(_CIRCUIT_OPEN_UNTIL, time.monotonic() + max(0.0, float(cooldown)))
        result = _fast_failure(
            state_root=root,
            attempt_id=attempt_id,
            operation=operation_name,
            failure_kind="timeout",
            timeout_seconds=timeout_seconds,
            elapsed_ms=elapsed_ms,
            fallback_allowed=fallback_allowed,
            error=f"hard deadline exceeded after {timeout_seconds:.3f}s",
        )
        with _LOCK:
            _LAST_OUTCOME = dict(result)
        return result

    if "error" in box:
        result = _fast_failure(
            state_root=root,
            attempt_id=attempt_id,
            operation=operation_name,
            failure_kind="error",
            timeout_seconds=timeout_seconds,
            elapsed_ms=elapsed_ms,
            fallback_allowed=fallback_allowed,
            error=str(box.get("error") or "local-model task failed"),
        )
        with _LOCK:
            _LAST_OUTCOME = dict(result)
        return result

    result = {
        "schema": "ENGEL_LOCAL_LLM_FAST_FAIL_RESULT_V1",
        "ok": True,
        "completed": True,
        "timed_out": False,
        "circuit_open": False,
        "busy": False,
        "status": "local LLM completed within deadline",
        "attempt_id": attempt_id,
        "operation": operation_name,
        "timeout_seconds": round(timeout_seconds, 3),
        "elapsed_ms": elapsed_ms,
        "fallback_allowed": bool(fallback_allowed),
        "provider_called": False,
        "result": box.get("value"),
        "issue_receipt_path": "",
        "fallback_proof_path": "",
    }
    with _LOCK:
        _LAST_OUTCOME = {key: value for key, value in result.items() if key != "result"}
    return result


def finalize_fallback_proof(
    initial_path: str | Path,
    *,
    fallback_attempted: bool,
    fallback_completed: bool,
    provider_id: str = "",
    reason: str = "",
    provider_called: bool | None = None,
) -> dict[str, Any]:
    """Create an append-only final fallback receipt; never rewrite the initial proof."""
    source_path = Path(initial_path)
    initial = _read_json(source_path)
    if not initial:
        return {
            "schema": "ENGEL_LOCAL_LLM_FALLBACK_FINAL_V1",
            "ok": False,
            "status": "initial fallback proof missing",
            "initial_path": str(source_path),
        }
    final_path = source_path.parent / "final" / f"ENGEL_LOCAL_LLM_FALLBACK_FINAL_{_stamp()}.json"
    payload = {
        "schema": "ENGEL_LOCAL_LLM_FALLBACK_FINAL_V1",
        "ok": True,
        "status": "fallback completed" if fallback_completed else "fallback not completed",
        "created_at_utc": _iso(),
        "attempt_id": str(initial.get("attempt_id") or ""),
        "failure_kind": str(initial.get("failure_kind") or ""),
        "initial_path": str(source_path),
        "initial_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "fallback_allowed": bool(initial.get("fallback_allowed") is True),
        "fallback_attempted": bool(fallback_attempted),
        "fallback_completed": bool(fallback_completed),
        "provider_id": str(provider_id or "")[:80],
        "reason": str(reason or "")[:1000],
        "provider_called": bool(fallback_attempted) if provider_called is None else bool(provider_called),
        "prompt_or_reply_stored": False,
        "credential_metadata_stored": False,
        "storage_mutation": False,
        "external_array_used": False,
    }
    _write_json(final_path, payload)
    payload["final_receipt_path"] = str(final_path)
    return payload


def _warm_status_url() -> str:
    explicit = str(os.environ.get("ENGEL_LOCAL_LLM_WARM_STATUS_URL") or "").strip()
    if explicit:
        return explicit
    chat_url = str(
        os.environ.get("ENGEL_ROG_GPU_CHAT_URL")
        or "http://127.0.0.1:8899/v1/chat/completions"
    ).strip()
    parsed = urllib.parse.urlsplit(chat_url)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/v1/models", "", ""))


def _probe_warm_service(timeout: float) -> dict[str, Any]:
    url = _warm_status_url()
    started = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read(200_000).decode("utf-8", errors="replace")
            status_code = int(getattr(response, "status", 200) or 200)
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {}
        models = payload.get("data") if isinstance(payload, dict) else []
        model_ids = [
            str(item.get("id") or "")[:200]
            for item in models
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        ] if isinstance(models, list) else []
        return {
            "ok": status_code == 200,
            "warm": status_code == 200,
            "status": "warm local model service ready" if status_code == 200 else "warm local model service not ready",
            "url": url,
            "status_code": status_code,
            "model_count": len(model_ids),
            "model_ids": model_ids[:8],
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return {
            "ok": False,
            "warm": False,
            "status": "warm local model service unavailable",
            "url": url,
            "error": str(exc)[:500],
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }


def status_snapshot(
    *,
    probe_warm: bool = True,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    with _LOCK:
        active = [dict({"attempt_id": key}, **value) for key, value in _ACTIVE.items()]
        circuit_remaining = max(0.0, _CIRCUIT_OPEN_UNTIL - time.monotonic())
        last = dict(_LAST_OUTCOME)
    warm = _probe_warm_service(
        _float_env("ENGEL_LOCAL_LLM_WARM_STATUS_TIMEOUT_SECONDS", 1.0, minimum=0.1, maximum=3.0)
    ) if probe_warm else {
        "ok": True,
        "warm": None,
        "status": "warm service probe skipped",
        "url": _warm_status_url(),
    }
    return {
        "schema": "ENGEL_LOCAL_LLM_FAST_FAIL_STATUS_V1",
        "ok": True,
        "status": "local LLM deadline controller ready",
        "source_of_truth": str(ROOT),
        "state_root": str(_state_root(state_root)),
        "hard_deadline_seconds": effective_timeout_seconds(None),
        "max_in_flight": _int_env("ENGEL_LOCAL_LLM_MAX_IN_FLIGHT", 1, minimum=1, maximum=4),
        "in_flight_count": len(active),
        "in_flight": active,
        "circuit_open": circuit_remaining > 0,
        "circuit_remaining_seconds": round(circuit_remaining, 3),
        "last_outcome": last,
        "warm_service": warm,
        "local_model_first": True,
        "provider_called": False,
        "prompt_or_reply_stored": False,
        "credential_metadata_stored": False,
        "active_runtime_root": str(ROOT),
        "external_array_used": False,
        "updated_at_utc": _iso(),
    }


def main() -> int:
    print(json.dumps(status_snapshot(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
