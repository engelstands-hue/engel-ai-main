#!/usr/bin/env python3
"""Persistent browser-backed ChatGPT worker for Engel AI Main.

This keeps the legacy `engel_browser_ai_bridge` alive outside short-lived
training/chat commands. Engel-owned state is kept under D:/b.WorkSpace.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "runtime" / "browser_ai_chatgpt_bridge"
REQUEST_DIR = RUNTIME_DIR / "requests"
RESPONSE_DIR = RUNTIME_DIR / "responses"
LOG_PATH = RUNTIME_DIR / "worker.log"
STATE_PATH = RUNTIME_DIR / "state.json"
PID_PATH = RUNTIME_DIR / "worker.pid"
BROWSER_PROFILE_DIR = ROOT / "browser_profile" / "chatgpt"
BROWSER_CACHE_DIR = ROOT / "runtime" / "ms-playwright"
BROWSER_VENV_PYTHON = ROOT / "runtime" / "browser_ai_venv" / "Scripts" / "python.exe"
HUMANIZER_SKILL_PATH = ROOT / "engel_humanizer_main" / "SKILL.md"
DEFAULT_TIMEOUT_SECONDS = 180
ENGEL_HUMANIZER_RULES = [
    "Answer directly; do not open with chatbot filler such as 'great question' or 'I hope this helps'.",
    "Use natural sentence rhythm. Mix short direct sentences with only the detail Joshua needs.",
    "Avoid product-demo language, significance inflation, rule-of-three padding, and vague AI-sounding summaries.",
    "When Joshua is frustrated, acknowledge the issue plainly, take responsibility in first person, then say the next concrete action.",
    "Do not turn normal conversation into backend status, release proof, or architecture unless Joshua asks for that.",
]


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_mkdirs() -> None:
    for path in (RUNTIME_DIR, REQUEST_DIR, RESPONSE_DIR, BROWSER_CACHE_DIR, ROOT / "runtime" / "temp"):
        path.mkdir(parents=True, exist_ok=True)


def is_os_drive(path: Path) -> bool:
    return path.drive.lower() == "c:"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if is_os_drive(path):
        raise RuntimeError(f"refusing to write Engel browser bridge state on C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for attempt in range(20):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if attempt >= 19:
                break
            time.sleep(0.1 * (attempt + 1))
    try:
        tmp_text = tmp.read_text(encoding="utf-8")
        with path.open("w", encoding="utf-8") as handle:
            handle.write(tmp_text)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
    except PermissionError as exc:
        append_log(f"state write skipped; file locked: {path}: {exc}")
    finally:
        tmp.unlink(missing_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def update_state(**updates: Any) -> None:
    try:
        state = read_json(STATE_PATH)
        state.update(updates)
        state["updated_at_utc"] = iso_now()
        write_json(STATE_PATH, state)
    except Exception as exc:
        append_log(f"state update failed: {exc}")


def append_log(message: str) -> None:
    if is_os_drive(LOG_PATH):
        return
    safe_mkdirs()
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"{iso_now()} {message}\n")


# Kernel-handle liveness probe (2026-07-29 fix for the console window that flashed on
# the operator's screen every poll). The implementation moved to
# engel_process_liveness so the other pollers stop re-growing diverged copies;
# importing keeps `pid_is_running` available under its old name here.
from engel_process_liveness import pid_is_running  # noqa: E402


def current_worker_pid() -> int:
    try:
        return int(PID_PATH.read_text(encoding="utf-8").strip())
    except Exception:
        return 0


def browser_env() -> dict[str, str]:
    env = os.environ.copy()
    env["ENGEL_APP_ROOT"] = str(ROOT)
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(BROWSER_CACHE_DIR)
    env["ENGEL_BROWSER_AI_HEADLESS"] = os.environ.get("ENGEL_BROWSER_AI_HEADLESS", "1")
    env["ENGEL_BROWSER_AI_HIDE_MODE"] = os.environ.get("ENGEL_BROWSER_AI_HIDE_MODE", "offscreen")
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    temp_dir = ROOT / "runtime" / "temp"
    env["TEMP"] = str(temp_dir)
    env["TMP"] = str(temp_dir)
    env["TMPDIR"] = str(temp_dir)
    return env


def worker_python() -> Path:
    configured = os.environ.get("ENGEL_BROWSER_AI_PYTHON", "").strip()
    if configured:
        return Path(configured)
    return BROWSER_VENV_PYTHON


def browser_hidden() -> bool:
    return os.environ.get("ENGEL_BROWSER_AI_HEADLESS", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def browser_hide_mode() -> str:
    return os.environ.get("ENGEL_BROWSER_AI_HIDE_MODE", "offscreen").strip().lower() or "offscreen"


def browser_true_headless() -> bool:
    return browser_hidden() and browser_hide_mode() == "headless"


def start_worker(wait_seconds: float = 20.0) -> dict[str, Any]:
    safe_mkdirs()
    state = read_json(STATE_PATH)
    state_pid = int(state.get("worker_pid") or 0)
    if state.get("ready") is True and pid_is_running(state_pid):
        return {
            "ok": True,
            "already_running": True,
            "worker_pid": state_pid,
            "state_path": str(STATE_PATH),
            "log_path": str(LOG_PATH),
        }
    pid = current_worker_pid()
    if pid_is_running(pid):
        return {
            "ok": True,
            "already_running": True,
            "worker_pid": pid,
            "state_path": str(STATE_PATH),
            "log_path": str(LOG_PATH),
        }

    py = worker_python()
    if not py.exists():
        return {
            "ok": False,
            "status": "browser worker python missing",
            "python": str(py),
            "expected_setup": "runtime/browser_ai_venv with playwright installed",
        }

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    log = LOG_PATH.open("a", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            [str(py), str(Path(__file__).resolve()), "worker"],
            cwd=str(ROOT),
            env=browser_env(),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            creationflags=creationflags,
            close_fds=False,
        )
    finally:
        log.close()

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        state = read_json(STATE_PATH)
        state_pid = int(state.get("worker_pid") or 0)
        if state.get("ready") is True and pid_is_running(state_pid):
            return {
                "ok": True,
                "already_running": False,
                "worker_pid": state_pid,
                "launcher_pid": proc.pid,
                "state_path": str(STATE_PATH),
                "log_path": str(LOG_PATH),
            }
        if proc.poll() is not None:
            return {
                "ok": False,
                "status": "browser worker exited during startup",
                "worker_pid": proc.pid,
                "return_code": proc.returncode,
                "log_path": str(LOG_PATH),
            }
        time.sleep(0.25)

    return {
        "ok": False,
        "status": "browser worker did not become ready before timeout",
        "worker_pid": proc.pid,
        "state_path": str(STATE_PATH),
        "log_path": str(LOG_PATH),
    }


def normalize_reply(raw: str) -> str:
    text = str(raw or "").replace("\r\n", "\n").strip()
    if text.startswith("[ChatGPT (OpenAI)]"):
        text = text.split("\n", 1)[1].strip() if "\n" in text else ""
    return text.strip()


def humanizer_instruction_block() -> str:
    if not HUMANIZER_SKILL_PATH.exists():
        return ""
    return (
        "Engel humanizer reference is active from "
        f"{HUMANIZER_SKILL_PATH}. Apply these voice rules:\n- "
        + "\n- ".join(ENGEL_HUMANIZER_RULES)
    )


def looks_like_bridge_failure(raw: str, reply: str) -> bool:
    lower = (raw + "\n" + reply).lower()
    failure_terms = [
        "input not found",
        "make sure you are logged in",
        "browser ai error",
        "response received but text could not be extracted",
        "target page, context or browser has been closed",
        "connect failed",
        "no page",
    ]
    return any(term in lower for term in failure_terms)


def looks_like_stale_browser_session(raw: str, reply: str) -> bool:
    lower = (raw + "\n" + reply).lower()
    stale_terms = [
        "target page, context or browser has been closed",
        "page has been closed",
        "context has been closed",
        "browser has been closed",
        "no page",
    ]
    return any(term in lower for term in stale_terms)


def build_browser_prompt(
    *,
    prompt: str,
    personality: str = "",
    trusted_memory: str = "",
    max_tokens: int = 420,
) -> str:
    parts = [
        "You are powering Engel AI Main inside Joshua's local Engel workspace.",
        "Reply as Engel AI Main in first person. Sound like a capable person, not a computer status panel.",
        "Do not say you are ChatGPT or OpenAI unless Joshua directly asks what provider is behind this turn.",
        "Do not pretend to be human. Be honest that you are Engel AI Main.",
        "Do not claim tests, training, device pairing, worker returns, files, or completion unless the prompt includes real receipt evidence.",
        f"Keep the answer within about {max(80, max_tokens)} tokens unless code or detailed work is explicitly requested.",
    ]
    humanizer = humanizer_instruction_block()
    if humanizer:
        parts.extend(["", humanizer])
    if personality:
        parts.extend(["", "Engel personality context:", personality.strip()[:1600]])
    if trusted_memory:
        parts.extend(["", "Trusted Engel memory relevant to this chat:", trusted_memory.strip()[:1000]])
    parts.extend(["", "Joshua says:", prompt.strip()])
    return "\n".join(parts).strip()


def process_request(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        return {"ok": False, "status": "empty prompt"}

    import engel_browser_ai_bridge

    started = time.perf_counter()
    connect_text = ""
    connected_before = bool(engel_browser_ai_bridge._SESSION.get("ready"))
    if not connected_before:
        connect_text = engel_browser_ai_bridge.browser_ai_connect("chatgpt")

    browser_prompt = build_browser_prompt(
        prompt=prompt,
        personality=str(payload.get("personality") or ""),
        trusted_memory=str(payload.get("trusted_memory") or ""),
        max_tokens=int(payload.get("max_tokens") or 420),
    )
    raw = engel_browser_ai_bridge.browser_ai_send(browser_prompt)
    reply = normalize_reply(raw)
    failed = looks_like_bridge_failure(raw, reply)
    reconnect_attempted = False
    reconnect_output = ""
    raw_first = raw
    reply_first = reply
    failed_first = failed
    if failed and looks_like_stale_browser_session(raw, reply):
        reconnect_attempted = True
        try:
            engel_browser_ai_bridge.browser_ai_disconnect()
        except Exception:
            pass
        reconnect_output = engel_browser_ai_bridge.browser_ai_connect("chatgpt")
        raw = engel_browser_ai_bridge.browser_ai_send(browser_prompt)
        reply = normalize_reply(raw)
        failed = looks_like_bridge_failure(raw, reply)
    return {
        "ok": bool(reply) and not failed,
        "status": "chatgpt browser replied" if reply and not failed else "chatgpt browser needs attention",
        "provider": "chatgpt-browser-ui-engel-voice",
        "runtime_provider": "browser-ai-chatgpt-visible-ui",
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "raw_browser_reply": raw,
        "raw_browser_reply_first": raw_first,
        "assistant_reply_first": reply_first,
        "browser_ai_first_attempt_failed": failed_first,
        "browser_ai_reconnect_attempted": reconnect_attempted,
        "browser_ai_reconnect_output": reconnect_output,
        "browser_ai_connect_output": connect_text,
        "browser_connected_before_request": connected_before,
        "browser_connected_after_request": bool(engel_browser_ai_bridge._SESSION.get("ready")),
        "browser_profile_path": str(BROWSER_PROFILE_DIR),
        "browser_cache_path": str(BROWSER_CACHE_DIR),
        "browser_visible": not browser_hidden(),
        "browser_hidden": browser_hidden(),
        "browser_hide_mode": browser_hide_mode(),
        "browser_true_headless": browser_true_headless(),
        "provider_api_enabled": False,
        "network_enabled": True,
        "server_enabled": False,
        "runs_inference": True,
        "loads_model": False,
        "runtime_process_started": True,
        "runtime_process_exited": False,
        "model_process_started": False,
        "trusted_memory_write_enabled": True,
        "approved_memory_write_enabled": False,
        "model_output_trusted": bool(reply) and not failed,
        "humanizer_reference_path": str(HUMANIZER_SKILL_PATH),
        "humanizer_reference_loaded": HUMANIZER_SKILL_PATH.exists(),
        "humanizer_voice_rules_active": HUMANIZER_SKILL_PATH.exists(),
        "local_command_elapsed_ms": int((time.perf_counter() - started) * 1000),
    }


def worker_loop() -> int:
    safe_mkdirs()
    os.environ.update(browser_env())
    # Singleton claim that survives the same-instant spawn race. Two workers can
    # be launched within milliseconds (start_worker() both see no live worker
    # before either writes its pid). A plain O_EXCL create + "unlink stale and
    # retry" has a TOCTOU hole: on a STALE pid file both racers clear+recreate it
    # and both believe they won, then fight over the one Chromium profile and
    # keep killing the hidden session. Instead: (1) if a LIVE different worker
    # already owns the pid, exit now (steady-state fast path); (2) otherwise
    # atomically write our pid over any absent/stale file with os.replace; (3)
    # settle briefly and re-read — whoever's pid is on disk last is the sole
    # owner, and every other racer sees a different pid and exits. Two workers
    # launched together deterministically collapse to exactly one.
    my_pid = os.getpid()
    existing_pid = current_worker_pid()
    if existing_pid and existing_pid != my_pid and pid_is_running(existing_pid):
        append_log(f"worker pid={my_pid} exiting; existing worker pid={existing_pid} is active")
        return 0
    try:
        claim_tmp = PID_PATH.with_name(f"worker.pid.claim.{my_pid}")
        claim_tmp.write_text(str(my_pid), encoding="utf-8")
        os.replace(str(claim_tmp), str(PID_PATH))  # atomic
    except Exception as exc:
        append_log(f"worker pid={my_pid} could not write pid file: {exc}")
        return 0
    time.sleep(0.5)
    owner_pid = current_worker_pid()
    if owner_pid != my_pid:
        append_log(f"worker pid={my_pid} lost singleton race to pid={owner_pid}; exiting")
        return 0
    write_json(
        STATE_PATH,
        {
            "schema": "engel_chatgpt_browser_worker_state_v1",
            "ready": True,
            "worker_pid": os.getpid(),
            "started_at_utc": iso_now(),
            "last_heartbeat_utc": iso_now(),
            "browser_profile_path": str(BROWSER_PROFILE_DIR),
            "browser_cache_path": str(BROWSER_CACHE_DIR),
            "browser_hidden": browser_hidden(),
            "browser_hide_mode": browser_hide_mode(),
            "browser_true_headless": browser_true_headless(),
        },
    )
    append_log(f"worker ready pid={os.getpid()}")
    while True:
        write_json(
            STATE_PATH,
            {
                **read_json(STATE_PATH),
                "ready": True,
                "worker_pid": os.getpid(),
                "last_heartbeat_utc": iso_now(),
                "browser_hidden": browser_hidden(),
                "browser_hide_mode": browser_hide_mode(),
                "browser_true_headless": browser_true_headless(),
            },
        )
        requests = sorted(REQUEST_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
        if not requests:
            time.sleep(0.25)
            continue
        request_path = requests[0]
        payload = read_json(request_path)
        request_id = str(payload.get("request_id") or request_path.stem)
        response_path = RESPONSE_DIR / f"{request_id}.json"
        try:
            if payload.get("kind") == "stop":
                response = {"ok": True, "status": "worker stopping", "worker_pid": os.getpid()}
                write_json(response_path, response)
                request_path.unlink(missing_ok=True)
                append_log("worker stop requested")
                return 0
            response = process_request(payload)
            response.update(
                {
                    "request_id": request_id,
                    "worker_pid": os.getpid(),
                    "request_path": str(request_path),
                    "response_path": str(response_path),
                    "worker_log_path": str(LOG_PATH),
                    "updated_at_utc": iso_now(),
                }
            )
        except Exception as exc:
            response = {
                "ok": False,
                "status": "chatgpt browser worker error",
                "error": str(exc),
                "request_id": request_id,
                "worker_pid": os.getpid(),
                "request_path": str(request_path),
                "response_path": str(response_path),
                "worker_log_path": str(LOG_PATH),
                "updated_at_utc": iso_now(),
                "provider_api_enabled": False,
                "network_enabled": True,
            }
            append_log(f"request {request_id} error: {exc}")
        write_json(response_path, response)
        request_path.unlink(missing_ok=True)


def send_chatgpt_browser_prompt(
    *,
    prompt: str,
    personality: str = "",
    trusted_memory: str = "",
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_tokens: int = 420,
) -> dict[str, Any]:
    safe_mkdirs()
    start = start_worker()
    if not start.get("ok"):
        return {
            "ok": False,
            "status": "chatgpt browser worker unavailable",
            "worker_start": start,
            "provider_api_enabled": False,
            "network_enabled": True,
        }

    request_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid.uuid4().hex[:8]
    request_path = REQUEST_DIR / f"{request_id}.json"
    response_path = RESPONSE_DIR / f"{request_id}.json"
    payload = {
        "schema": "engel_chatgpt_browser_request_v1",
        "kind": "chat",
        "request_id": request_id,
        "created_at_utc": iso_now(),
        "prompt": prompt,
        "personality": personality,
        "trusted_memory": trusted_memory,
        "max_tokens": max_tokens,
    }
    write_json(request_path, payload)
    deadline = time.time() + max(1, timeout)
    while time.time() < deadline:
        if response_path.exists():
            response = read_json(response_path)
            response.setdefault("worker_start", start)
            response.setdefault("request_id", request_id)
            response.setdefault("request_path", str(request_path))
            response.setdefault("response_path", str(response_path))
            response.setdefault("browser_profile_path", str(BROWSER_PROFILE_DIR))
            response.setdefault("browser_cache_path", str(BROWSER_CACHE_DIR))
            response.setdefault("browser_hidden", browser_hidden())
            response.setdefault("browser_hide_mode", browser_hide_mode())
            response.setdefault("browser_true_headless", browser_true_headless())
            response.setdefault("worker_log_path", str(LOG_PATH))
            update_state(
                last_probe_at_utc=iso_now(),
                last_probe_ok=response.get("ok") is True,
                last_probe_status=str(response.get("status") or ""),
                last_probe_request_id=request_id,
                last_probe_response_path=str(response_path),
            )
            return response
        time.sleep(0.25)
    timeout_response = {
        "ok": False,
        "status": "chatgpt browser response timeout",
        "request_id": request_id,
        "request_path": str(request_path),
        "response_path": str(response_path),
        "worker_start": start,
        "worker_pid": start.get("worker_pid"),
        "worker_log_path": str(LOG_PATH),
        "browser_profile_path": str(BROWSER_PROFILE_DIR),
        "browser_cache_path": str(BROWSER_CACHE_DIR),
        "browser_hidden": browser_hidden(),
        "browser_hide_mode": browser_hide_mode(),
        "browser_true_headless": browser_true_headless(),
        "provider_api_enabled": False,
        "network_enabled": True,
    }
    update_state(
        last_probe_at_utc=iso_now(),
        last_probe_ok=False,
        last_probe_status="chatgpt browser response timeout",
        last_probe_request_id=request_id,
        last_probe_response_path=str(response_path),
    )
    return timeout_response


def stop_worker(timeout: int = 10) -> dict[str, Any]:
    safe_mkdirs()
    pid = current_worker_pid()
    if not pid_is_running(pid):
        return {"ok": True, "status": "browser worker already stopped", "worker_pid": pid}
    request_id = "stop_" + uuid.uuid4().hex[:8]
    request_path = REQUEST_DIR / f"{request_id}.json"
    response_path = RESPONSE_DIR / f"{request_id}.json"
    write_json(request_path, {"kind": "stop", "request_id": request_id, "created_at_utc": iso_now()})
    deadline = time.time() + timeout
    while time.time() < deadline:
        if response_path.exists():
            return read_json(response_path)
        time.sleep(0.25)
    return {"ok": False, "status": "stop request timed out", "worker_pid": pid}


def status_payload() -> dict[str, Any]:
    pid = current_worker_pid()
    return {
        "ok": True,
        "schema": "engel_chatgpt_browser_worker_status_v1",
        "worker_pid": pid,
        "worker_running": pid_is_running(pid),
        "state": read_json(STATE_PATH),
        "state_path": str(STATE_PATH),
        "pid_path": str(PID_PATH),
        "log_path": str(LOG_PATH),
        "browser_profile_path": str(BROWSER_PROFILE_DIR),
        "browser_cache_path": str(BROWSER_CACHE_DIR),
        "browser_hidden": browser_hidden(),
        "browser_hide_mode": browser_hide_mode(),
        "browser_true_headless": browser_true_headless(),
        "browser_python_path": str(worker_python()),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel ChatGPT browser worker")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("worker")
    sub.add_parser("start")
    sub.add_parser("status")
    sub.add_parser("stop")
    send = sub.add_parser("send")
    send.add_argument("prompt", nargs="?", default="")
    send.add_argument("--prompt", dest="prompt_option", default="")
    send.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    send.add_argument("--max-tokens", type=int, default=420)
    send.add_argument("--personality", default="")
    send.add_argument("--trusted-memory", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "worker":
        return worker_loop()
    if args.command == "start":
        print(json.dumps(start_worker(), indent=2))
        return 0
    if args.command == "status":
        print(json.dumps(status_payload(), indent=2))
        return 0
    if args.command == "stop":
        result = stop_worker()
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    if args.command == "send":
        prompt = (args.prompt_option or args.prompt or "").strip()
        result = send_chatgpt_browser_prompt(
            prompt=prompt,
            personality=args.personality,
            trusted_memory=args.trusted_memory,
            timeout=args.timeout,
            max_tokens=args.max_tokens,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
