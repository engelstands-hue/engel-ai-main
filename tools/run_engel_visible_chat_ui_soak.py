#!/usr/bin/env python3
"""Launch Engel AI Main and verify a visible Chat UI soak.

The Flutter app owns the UI driver through ENGEL_UI_CHAT_SOAK_ENABLED. This
script only launches the app with that guarded mode, waits the requested time,
and summarizes the same chat receipts created by the production Chat path.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
APP_EXE = ROOT / "engel_flutter_main" / "build" / "windows" / "x64" / "runner" / "Release" / "EngelAIMain.exe"
CHAT_RECEIPT_DIR = ROOT / "reports" / "engel_standalone_chat_llm" / "chat_receipts"
REPORT_DIR = ROOT / "reports" / "codex_bridge"
DEFAULT_TEMPLATE = ROOT / "memory" / "training" / "ENGEL_FAST_CHAT_SOAK_TEMPLATE_20260628.json"
PHONE_PAIRED_PATH = ROOT / "memory" / "phone_bridge" / "ENGEL_REMOTE_WORKERS_PAIRED.json"
PHONE_HEALTH_URL = "http://192.0.2.40:8765/health"
PHONE_CLUSTER_URL = "http://192.0.2.40:8765/cluster/status"
PHONE_FRESH_SECONDS = 300
CT_HOST = os.environ.get("ENGEL_MAIN_SERVER_HOST", "192.0.2.50")
CT_PORT = int(os.environ.get("ENGEL_MAIN_SERVER_SSH_PORT", "24622") or "24622")
CT_USER = os.environ.get("ENGEL_MAIN_SERVER_SSH_USER", "root")
CT_KEY_PATH = Path(os.environ.get("ENGEL_MAIN_SERVER_SSH_KEY", str(Path.home() / ".ssh" / "engel_ai_main_ct246_ed25519")))
CT_MEMORY_PATH = "/opt/engel/memory/persistent_chat/ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl"
MEETING_ROOM_EVENTS_URL = os.environ.get(
    "ENGEL_MEETING_ROOM_EVENTS_URL",
    "http://127.0.0.1:8790/room/events?since=0&limit=300",
)
EXPECTED_PHONE_IPS = {
    "android_worker_alpha": "192.0.2.78",
    "android_worker_beta": "192.0.2.83",
    "android_worker_gamma": "198.51.100.236",
}


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + f"_p{os.getpid()}"


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    # PowerShell/.NET writers emit 7-digit tick fractions (".8794662"), which
    # Python 3.10's fromisoformat rejects (it accepts only 3 or 6 digits).
    # Normalize any fraction to exactly 6 digits before parsing.
    text = re.sub(
        r"\.(\d{1,9})(?=[+-]\d{2}:\d{2}$|$)",
        lambda m: "." + m.group(1)[:6].ljust(6, "0"),
        text,
    )
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def phone_link_snapshot() -> dict[str, Any]:
    paired = load_json(PHONE_PAIRED_PATH)
    paired = paired if isinstance(paired, dict) else {}
    state = load_json(ROOT / "remote_workers" / "lan_link_manager" / "session_state.json")
    state = state if isinstance(state, dict) else {}
    health: dict[str, Any]
    try:
        with urllib.request.urlopen(PHONE_HEALTH_URL, timeout=4) as resp:
            parsed = json.loads(resp.read().decode("utf-8", errors="replace"))
        health = parsed if isinstance(parsed, dict) else {"ok": False, "status": "non-object health response"}
    except Exception as exc:
        health = {"ok": False, "status": "phone receiver health error", "error": str(exc)}
    try:
        with urllib.request.urlopen(PHONE_CLUSTER_URL, timeout=4) as resp:
            parsed_presence = json.loads(resp.read().decode("utf-8", errors="replace"))
        presence = parsed_presence if isinstance(parsed_presence, dict) else {}
    except Exception as exc:
        presence = {"ok": False, "error": str(exc)}
    presence_workers = presence.get("workers")
    presence_workers = presence_workers if isinstance(presence_workers, dict) else {}
    workers = paired.get("workers")
    workers = workers if isinstance(workers, list) else []
    live_workers = 0
    now = datetime.now(timezone.utc)
    worker_rows: list[dict[str, Any]] = []
    state_workers = state.get("workers")
    state_workers = state_workers if isinstance(state_workers, dict) else {}
    for worker in workers:
        if not isinstance(worker, dict):
            continue
        worker_id = str(worker.get("worker_id") or "")
        expected_ip = EXPECTED_PHONE_IPS.get(worker_id, "")
        state_worker = state_workers.get(worker_id)
        state_worker = state_worker if isinstance(state_worker, dict) else {}
        presence_worker = presence_workers.get(worker_id)
        presence_worker = presence_worker if isinstance(presence_worker, dict) else {}
        identity = state_worker.get("identity")
        identity = identity if isinstance(identity, dict) else {}
        presence_identity = presence_worker.get("identity")
        presence_identity = presence_identity if isinstance(presence_identity, dict) else {}
        observed = str(
            presence_identity.get("remote_address")
            or worker.get("observed_remote_address")
            or identity.get("remote_address")
            or ""
        )
        worker_last_seen = str(worker.get("last_seen") or "")
        state_last_seen = str(state_worker.get("last_seen_utc") or "")
        presence_last_seen = str(presence_worker.get("last_seen_utc") or "")
        worker_seen_at = parse_utc(worker_last_seen)
        state_seen_at = parse_utc(state_last_seen)
        presence_seen_at = parse_utc(presence_last_seen)
        seen_candidates = [
            (worker_seen_at, worker_last_seen),
            (state_seen_at, state_last_seen),
            (presence_seen_at, presence_last_seen),
        ]
        seen_candidates = [(seen, text) for seen, text in seen_candidates if seen is not None]
        seen_at, last_seen = max(seen_candidates, key=lambda item: item[0]) if seen_candidates else (None, "")
        age_seconds = None if seen_at is None else round((now - seen_at).total_seconds(), 1)
        transport = str(worker.get("transport") or "")
        adb_serial = str(worker.get("adb_serial") or "")
        adb_device_online = worker.get("adb_device_online") is True
        adb_reverse_active = worker.get("adb_reverse_active") is True
        verified_adb_reverse = (
            transport == "adb_reverse_usb"
            and observed == "127.0.0.1"
            and bool(adb_serial)
            and adb_device_online
            and adb_reverse_active
        )
        remote_ok = bool(observed == expected_ip or verified_adb_reverse)
        authenticated_presence_live = (
            presence.get("ok") is True
            and presence_worker
            and observed == expected_ip
            and age_seconds is not None
            and 0 <= age_seconds <= PHONE_FRESH_SECONDS
        )
        live = authenticated_presence_live or (
            worker.get("live_phone_connected") is True
            and expected_ip
            and remote_ok
            and age_seconds is not None
            and 0 <= age_seconds <= PHONE_FRESH_SECONDS
        )
        if live:
            live_workers += 1
        worker_rows.append(
            {
                "worker_id": worker_id,
                "phone_model": worker.get("phone_model"),
                "phone_ip": worker.get("phone_ip"),
                "expected_phone_ip": expected_ip,
                "observed_remote_address": observed,
                "paired": bool(authenticated_presence_live or worker.get("paired") is True),
                "live_phone_connected": live,
                "transport": transport or ("lan" if observed == expected_ip else "unknown"),
                "adb_serial": adb_serial,
                "adb_device_online": adb_device_online,
                "adb_reverse_active": adb_reverse_active,
                "last_seen": last_seen,
                "last_seen_age_seconds": age_seconds,
                "freshness_limit_seconds": PHONE_FRESH_SECONDS,
                "connection_reason": (
                    "fresh authenticated phone heartbeat"
                    if authenticated_presence_live
                    else worker.get("connection_reason") or worker.get("reason")
                ),
                "mode": worker.get("mode"),
            }
        )
    return {
        "paired_file": str(PHONE_PAIRED_PATH),
        "paired_file_exists": PHONE_PAIRED_PATH.exists(),
        "receiver_health_url": PHONE_HEALTH_URL,
        "receiver_health": health,
        "presence_url": PHONE_CLUSTER_URL,
        "presence": presence,
        "paired_worker_count": sum(1 for worker in worker_rows if worker.get("paired") is True),
        "live_phone_worker_count": live_workers,
        "live_phone_required": True,
        "workers": worker_rows,
    }


def clean_prompt_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def prompts_from_template(path: Path, mode: str) -> list[str]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        return []
    if mode == "smoke":
        prompts = clean_prompt_list(payload.get("smoke_prompts"))
        if prompts:
            return prompts
        return clean_prompt_list(payload.get("active_prompts"))[:3]
    cycle_sets = payload.get("cycle_prompt_sets")
    if isinstance(cycle_sets, list) and cycle_sets:
        selected = cycle_sets[0]
        if isinstance(selected, dict):
            prompts = clean_prompt_list(selected.get("prompts"))
            if prompts:
                return prompts
        if isinstance(selected, list):
            prompts = clean_prompt_list(selected)
            if prompts:
                return prompts
    return clean_prompt_list(payload.get("active_prompts"))


def paths_since(root: Path, since_epoch: float, pattern: str) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        [path for path in root.glob(pattern) if path.is_file() and path.stat().st_mtime >= since_epoch],
        key=lambda item: item.stat().st_mtime,
    )


def receipt_prompt(receipt: dict[str, Any]) -> str:
    value = receipt.get("prompt")
    if value:
        return str(value)
    nested = receipt.get("receipt")
    if isinstance(nested, dict):
        return str(nested.get("prompt") or "")
    return ""


def receipt_value(receipt: dict[str, Any], key: str) -> Any:
    if key in receipt:
        return receipt.get(key)
    nested = receipt.get("receipt")
    if isinstance(nested, dict):
        return nested.get(key)
    return None


def summarize_receipts(paths: list[Path], prompts: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prompt_set = {prompt.strip() for prompt in prompts}
    rows: list[dict[str, Any]] = []
    for path in paths:
        payload = load_json(path)
        if not isinstance(payload, dict):
            continue
        prompt = receipt_prompt(payload).strip()
        if prompt_set and prompt not in prompt_set:
            continue
        latency = receipt_value(payload, "latency_ms")
        server_latency = receipt_value(payload, "server_request_latency_ms")
        rows.append(
            {
                "path": str(path),
                "prompt": prompt,
                "ok": payload.get("ok"),
                "status": payload.get("status"),
                "runtime_provider": receipt_value(payload, "runtime_provider"),
                "selected_provider": receipt_value(payload, "selected_provider"),
                "main_server_chat_used": receipt_value(payload, "main_server_chat_used") is True,
                "fast_server_fallback_used": receipt_value(payload, "fast_server_fallback_used") is True,
                "meeting_room_server_used": receipt_value(payload, "meeting_room_server_used") is True,
                "persistent_chat_memory_appended": receipt_value(payload, "persistent_chat_memory_appended") is True,
                "latency_ms": int(latency or 0) if latency is not None else None,
                "server_request_latency_ms": int(server_latency or 0) if server_latency is not None else None,
            }
        )
    latencies = [row["latency_ms"] for row in rows if row.get("latency_ms") is not None]
    server_latencies = [row["server_request_latency_ms"] for row in rows if row.get("server_request_latency_ms") is not None]
    summary = {
        "receipt_count": len(rows),
        "ok_count": sum(1 for row in rows if row.get("ok") is True),
        "main_server_chat_used_count": sum(1 for row in rows if row.get("main_server_chat_used") is True),
        "fast_server_fallback_used_count": sum(1 for row in rows if row.get("fast_server_fallback_used") is True),
        "meeting_room_server_used_count": sum(1 for row in rows if row.get("meeting_room_server_used") is True),
        "persistent_chat_memory_appended_count": sum(1 for row in rows if row.get("persistent_chat_memory_appended") is True),
        "max_latency_ms": max(latencies or [0]),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
        "max_server_request_latency_ms": max(server_latencies or [0]),
        "avg_server_request_latency_ms": round(sum(server_latencies) / len(server_latencies), 2) if server_latencies else 0,
        "prompts_seen": sorted({row["prompt"] for row in rows if row.get("prompt")}),
    }
    return rows, summary


def ct_persistent_memory_hits(prompts: list[str], since_epoch: float) -> dict[str, Any]:
    """Verify that the visible UI prompts reached CT246 persistent memory.

    The current server-first chat path writes CT-side memory receipts, not the
    older Windows fallback receipt files. A visible UI PASS must therefore prove
    the exact prompt text exists in /opt/engel memory after this run started.
    """
    prompt_payload = base64.b64encode(json.dumps(prompts).encode("utf-8")).decode("ascii")
    since_iso = datetime.fromtimestamp(since_epoch - 2, tz=timezone.utc).isoformat()
    remote_script = f"""
import base64, json
from datetime import datetime, timezone
from pathlib import Path

prompts = json.loads(base64.b64decode({prompt_payload!r}).decode('utf-8'))
since_raw = {since_iso!r}
if since_raw.endswith('Z'):
    since_raw = since_raw[:-1] + '+00:00'
since = datetime.fromisoformat(since_raw).astimezone(timezone.utc)
path = Path({CT_MEMORY_PATH!r})
result = {{
    'ok': False,
    'path': str(path),
    'path_exists': path.is_file(),
    'prompt_count': len(prompts),
    'hits': {{}},
    'checked_tail_lines': 0,
}}
if path.is_file():
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()[-1000:]
    result['checked_tail_lines'] = len(lines)
    rows = []
    for line in lines:
        try:
            item = json.loads(line)
        except Exception:
            continue
        if not isinstance(item, dict):
            continue
        updated = str(item.get('updated_at_utc') or item.get('created_at_utc') or '').strip()
        if updated.endswith('Z'):
            updated = updated[:-1] + '+00:00'
        try:
            updated_at = datetime.fromisoformat(updated).astimezone(timezone.utc)
        except Exception:
            updated_at = None
        rows.append((item, updated_at))
    for prompt in prompts:
        matches = []
        for item, updated_at in rows:
            if item.get('prompt') != prompt:
                continue
            if updated_at is not None and updated_at < since:
                continue
            matches.append(item)
        latest = matches[-1] if matches else {{}}
        model_latest = {{}}
        for candidate in reversed(matches):
            if candidate.get('provider_api_enabled') is not None or candidate.get('provider') or candidate.get('runtime_provider'):
                model_latest = candidate
                break
        receipt_payload = {{}}
        receipt_path = str(latest.get('workspace_receipt_path') or '').strip()
        if receipt_path:
            try:
                receipt_file = Path(receipt_path)
                if receipt_file.is_file():
                    receipt_payload = json.loads(receipt_file.read_text(encoding='utf-8', errors='replace'))
            except Exception:
                receipt_payload = {{}}
        model_evidence = dict(receipt_payload) if isinstance(receipt_payload, dict) else {{}}
        for key, value in model_latest.items():
            if value is not None and value != '':
                model_evidence[key] = value
        model_provider = str(model_evidence.get('provider') or model_evidence.get('runtime_provider') or '').strip()
        model_selected = str(model_evidence.get('selected_provider') or model_evidence.get('selected_chat_provider') or '').strip()
        remote_name = (model_provider + ' ' + model_selected).casefold()
        remote_provider = any(term in remote_name for term in ('openai', 'anthropic', 'chatgpt', 'claude', 'gemini', 'grok', 'xai', 'codex'))
        model_path = str(model_evidence.get('model') or model_evidence.get('quick_model_path') or model_evidence.get('quick_casual_model_path') or '').strip()
        model_backed = bool(model_path) and ('gguf' in model_path.casefold() or 'llama-cpp' in model_provider.casefold())
        local_model_verified = model_evidence.get('provider_api_enabled') is False and not remote_provider and model_backed
        provider_pipeline_used = model_evidence.get('provider_api_enabled') is True or remote_provider
        training_sample_eligible = model_evidence.get('training_sample_eligible') is True
        escalated_from = model_evidence.get('escalated_from')
        if escalated_from is None:
            escalated_from = model_evidence.get('_engel_escalated_from')
        verified_local_first_escalation = bool(
            provider_pipeline_used
            and model_evidence.get('local_ct_lora_first_attempted') is True
            and model_evidence.get('local_ct_lora_first_failed') is True
            and str(escalated_from or '') == '2'
            and model_evidence.get('provider_reply_quality_gate_passed') is True
            and isinstance(model_evidence.get('provider_final_semantic_quality'), dict)
            and model_evidence.get('provider_final_semantic_quality', {{}}).get('ok') is True
            and training_sample_eligible
        )
        quality_status = str(model_evidence.get('status') or '').casefold()
        quality_gate_degraded = bool(
            model_evidence.get('quality_gate_degraded') is True
            or 'style check failed' in quality_status
            or 'quality check failed' in quality_status
        )
        static_fallback = 'fast-local' in model_provider.casefold() or 'fast-responder' in str(model_evidence.get('runtime_provider') or '').casefold()
        quality_verified = local_model_verified and not quality_gate_degraded and not static_fallback and training_sample_eligible
        routing_policy_verified = (local_model_verified and training_sample_eligible) or verified_local_first_escalation
        quality_or_verified_escalation = quality_verified or verified_local_first_escalation
        result['hits'][prompt] = {{
            'count': len(matches),
            'latest_status': latest.get('status'),
            'latest_provider': latest.get('provider'),
            'latest_selected_provider': latest.get('selected_provider'),
            'latest_runtime_provider': latest.get('runtime_provider'),
            'latest_updated_at_utc': latest.get('updated_at_utc') or latest.get('created_at_utc'),
            'latest_workspace_receipt_path': receipt_path,
            'latest_meeting_room_server_used': receipt_payload.get('meeting_room_server_used'),
            'latest_agent_meeting_room_used': receipt_payload.get('agent_meeting_room_used'),
            'latest_receipt_selected_provider': receipt_payload.get('selected_provider'),
            'latest_receipt_runtime_provider': receipt_payload.get('runtime_provider'),
            'latest_receipt_provider': receipt_payload.get('provider'),
            'local_model_verified': local_model_verified,
            'local_model_provider': model_provider,
            'local_model_selected_provider': model_selected,
            'local_model_provider_api_enabled': model_evidence.get('provider_api_enabled'),
            'local_model_network_enabled': model_evidence.get('network_enabled'),
            'local_model_path': model_path,
            'local_model_chat_context_scope': model_evidence.get('chat_context_scope'),
            'provider_pipeline_used': provider_pipeline_used,
            'training_sample_eligible': training_sample_eligible,
            'verified_local_first_escalation': verified_local_first_escalation,
            'escalated_from': escalated_from,
            'local_ct_lora_first_status': model_evidence.get('local_ct_lora_first_status'),
            'local_ct_lora_first_error': model_evidence.get('local_ct_lora_first_error'),
            'routing_policy_verified': routing_policy_verified,
            'quality_gate_degraded': quality_gate_degraded,
            'static_fallback': static_fallback,
            'quality_verified': quality_verified,
            'quality_or_verified_escalation': quality_or_verified_escalation,
            'assistant_reply_preview': str(model_evidence.get('assistant_reply') or model_evidence.get('assistant_output_text') or '')[:500],
        }}
    result['single_write_ok'] = all(
        result['hits'].get(prompt, {{}}).get('count', 0) == 1 for prompt in prompts
    )
    result['training_eligible_ok'] = all(
        result['hits'].get(prompt, {{}}).get('training_sample_eligible') is True
        for prompt in prompts
    )
    result['ok'] = result['single_write_ok'] and result['training_eligible_ok']
    result['local_only_ok'] = all(result['hits'].get(prompt, {{}}).get('local_model_verified') is True for prompt in prompts)
    result['quality_ok'] = all(result['hits'].get(prompt, {{}}).get('quality_verified') is True for prompt in prompts)
    result['local_first_or_verified_escalation_ok'] = all(
        result['hits'].get(prompt, {{}}).get('routing_policy_verified') is True
        for prompt in prompts
    )
    result['quality_or_verified_escalation_ok'] = all(
        result['hits'].get(prompt, {{}}).get('quality_or_verified_escalation') is True
        for prompt in prompts
    )
    result['verified_pipeline_escalation_count'] = sum(
        1 for prompt in prompts
        if result['hits'].get(prompt, {{}}).get('verified_local_first_escalation') is True
    )
print(json.dumps(result, sort_keys=True))
"""
    if not CT_KEY_PATH.exists():
        return {
            "ok": False,
            "path": CT_MEMORY_PATH,
            "error": f"missing CT SSH key: {CT_KEY_PATH}",
            "hits": {},
        }
    command = [
        "ssh",
        "-i",
        str(CT_KEY_PATH),
        "-p",
        str(CT_PORT),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        "-o",
        "StrictHostKeyChecking=accept-new",
        f"{CT_USER}@{CT_HOST}",
        "python3 - <<'PY'\n" + remote_script + "\nPY",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as exc:
        return {"ok": False, "path": CT_MEMORY_PATH, "error": str(exc), "hits": {}}
    stdout = completed.stdout.strip()
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "path": CT_MEMORY_PATH,
            "error": "CT memory check returned non-JSON",
            "exit_code": completed.returncode,
            "stdout_tail": stdout[-1000:],
            "stderr_tail": completed.stderr[-1000:],
            "hits": {},
        }
    if completed.returncode != 0:
        parsed["ok"] = False
        parsed["exit_code"] = completed.returncode
        parsed["stderr_tail"] = completed.stderr[-1000:]
    return parsed


def prompt_requests_meeting_room_dispatch(prompt: str) -> bool:
    low = str(prompt or "").casefold()
    terms = (
        "meeting room",
        "agent room",
        "server world",
        "3d room",
        "3d agent",
        "agent workspace",
        "minecraft",
        "all devices",
        "all agents",
        "alpha",
        "beta",
        "phone worker",
        "android worker",
        "sub-engel",
        "one job",
        "proof job",
        "work order",
        "show devices working",
        "collaborate",
        "room chat",
    )
    return any(term in low for term in terms)


def meeting_room_event_hits(prompts: list[str], since_epoch: float) -> dict[str, Any]:
    required = [prompt for prompt in prompts if prompt_requests_meeting_room_dispatch(prompt)]
    result: dict[str, Any] = {
        "ok": True,
        "url": MEETING_ROOM_EVENTS_URL,
        "required_prompt_count": len(required),
        "hits": {},
        "event_count": 0,
    }
    if not required:
        return result
    since = datetime.fromtimestamp(since_epoch - 2, tz=timezone.utc)
    try:
        with urllib.request.urlopen(MEETING_ROOM_EVENTS_URL, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        return {
            "ok": False,
            "url": MEETING_ROOM_EVENTS_URL,
            "required_prompt_count": len(required),
            "error": str(exc),
            "hits": {},
            "event_count": 0,
        }
    events = payload.get("events") if isinstance(payload, dict) else []
    if not isinstance(events, list):
        events = []
    result["event_count"] = len(events)
    parsed_events: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_time = parse_utc(event.get("created_at_utc"))
        if event_time is not None and event_time < since:
            continue
        if event.get("event_type") != "order.submit":
            continue
        event_payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        preview = str(event_payload.get("order_text_preview") or "")
        parsed_events.append(
            {
                "id": event.get("id"),
                "created_at_utc": event.get("created_at_utc"),
                "preview": preview,
                "accepted": event_payload.get("accepted"),
                "order_id": event_payload.get("order_id"),
            }
        )
    for prompt in required:
        matches = [event for event in parsed_events if prompt in str(event.get("preview") or "")]
        result["hits"][prompt] = {
            "count": len(matches),
            "latest": matches[-1] if matches else None,
        }
    result["ok"] = all(result["hits"].get(prompt, {}).get("count", 0) > 0 for prompt in required)
    return result


def stop_existing_engel() -> None:
    ps = r"""
$ErrorActionPreference = 'SilentlyContinue'
Get-Process EngelAIMain | Stop-Process -Force
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def kick_stack_controller() -> None:
    subprocess.run(
        ["schtasks", "/Run", "/TN", "EngelStackController"],
        capture_output=True,
        text=True,
        timeout=20,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def wait_for_main_server_health(seconds: float = 45.0) -> bool:
    deadline = time.monotonic() + max(1.0, seconds)
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:24680/health", timeout=3) as response:
                value = json.loads(response.read().decode("utf-8", errors="replace"))
            if isinstance(value, dict) and value.get("ok") is True:
                return True
        except Exception:
            pass
        time.sleep(2.0)
    return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run guarded visible Engel Chat UI soak.")
    parser.add_argument(
        "--minutes",
        type=float,
        default=None,
        help="soak duration; defaults to 5 for smoke mode, 60 otherwise",
    )
    parser.add_argument("--mode", choices=["smoke", "one-hour", "two-hour"], default="one-hour")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    parser.add_argument("--exe", default=str(APP_EXE))
    parser.add_argument(
        "--terminate-existing",
        action="store_true",
        default=True,
        help="stop old Engel windows before the run; default is on",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_false",
        dest="terminate_existing",
        help="debug only: leave existing Engel windows open and launch another instance",
    )
    parser.add_argument("--startup-wait", type=float, default=5.0)
    parser.add_argument(
        "--allow-verified-provider-escalation",
        action="store_true",
        help="accept a provider turn only when its CT receipt proves local failure first",
    )
    parser.add_argument(
        "--soak-start-delay",
        type=float,
        default=45.0,
        help="seconds the visible app waits for its persistent CT246 link before submitting prompt 1",
    )
    return parser


def soak_driver_reply_count(since_epoch: float) -> tuple[int, int]:
    """Count prompt_submitted / prompt_reply_finished events from the app-side
    soak driver logs (reports/codex_bridge/ENGEL_CHAT_UI_SOAK_*.jsonl). The
    modern server-first chat path does not write ENGEL_UI_CHAT_MEETING_ROOM
    receipts (that is the fallback lane's artifact), so the driver events are
    the primary proof that visible turns happened and got replies."""
    submitted = 0
    finished = 0
    try:
        for path in REPORT_DIR.glob("ENGEL_CHAT_UI_SOAK_*.jsonl"):
            if path.stat().st_mtime < since_epoch - 2:
                continue
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                name = event.get("event")
                if name == "prompt_submitted":
                    submitted += 1
                elif name == "prompt_reply_finished":
                    finished += 1
    except OSError:
        pass
    return submitted, finished


def main() -> int:
    args = build_parser().parse_args()
    if args.minutes is None:
        args.minutes = 5.0 if args.mode == "smoke" else 60.0
    exe = Path(args.exe).resolve()
    template = Path(args.template).resolve()
    if not exe.exists():
        raise SystemExit(f"Engel release exe missing: {exe}")
    prompts = prompts_from_template(template, args.mode)
    if not prompts:
        raise SystemExit(f"no prompts loaded from template: {template}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    CHAT_RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = f"engel_visible_chat_ui_soak_{args.mode}_{stamp()}"
    started_epoch = time.time()
    started_mono = time.monotonic()
    phone_link_before = phone_link_snapshot()
    if args.terminate_existing:
        stop_existing_engel()
        time.sleep(2.0)

    env = os.environ.copy()
    env.update(
        {
            "ENGEL_UI_CHAT_SOAK_ENABLED": "1",
            "ENGEL_UI_CHAT_SOAK_MODE": args.mode,
            "ENGEL_UI_CHAT_SOAK_MINUTES": str(args.minutes),
            "ENGEL_UI_CHAT_SOAK_START_DELAY_SECONDS": str(max(0.0, args.soak_start_delay)),
            "ENGEL_UI_CHAT_SOAK_TEMPLATE": str(template),
            "ENGEL_MAIN_SERVER_ENABLED": "1",
            "ENGEL_MAIN_SERVER_CHAT_URL": "http://127.0.0.1:24680",
            "ENGEL_MAIN_SERVER_CHAT_REQUIRED": "1",
            "ENGEL_MAIN_ALLOW_LAPTOP_LOCAL_FALLBACK": "0",
            "ENGEL_MEETING_ROOM_SERVER_URL": "http://127.0.0.1:8790",
        }
    )
    process = subprocess.Popen([str(exe)], cwd=str(exe.parent), env=env)
    kick_stack_controller()
    if not wait_for_main_server_health(45.0):
        process.terminate()
        raise RuntimeError("Engel stack did not restore the CT246 chat tunnel before the UI soak")
    time.sleep(max(0.0, args.startup_wait))

    deadline = started_mono + max(1.0, args.minutes * 60.0) + max(0.0, args.soak_start_delay)
    last_progress = 0.0
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        now = time.monotonic()
        if now - last_progress >= 30:
            receipts, summary = summarize_receipts(
                paths_since(CHAT_RECEIPT_DIR, started_epoch - 2, "ENGEL_UI_CHAT_MEETING_ROOM_*.json"),
                prompts,
            )
            driver_submitted, driver_finished = soak_driver_reply_count(started_epoch)
            print(
                json.dumps(
                    {
                        "event": "visible_chat_ui_soak_progress",
                        "run_id": run_id,
                        "elapsed_seconds": int(now - started_mono),
                        "seconds_to_deadline": int(max(0, deadline - now)),
                        "receipt_count": len(receipts),
                        "main_server_chat_used_count": summary["main_server_chat_used_count"],
                        "fast_server_fallback_used_count": summary["fast_server_fallback_used_count"],
                        "persistent_chat_memory_appended_count": summary["persistent_chat_memory_appended_count"],
                        "driver_prompts_submitted": driver_submitted,
                        "driver_replies_finished": driver_finished,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            last_progress = now
        time.sleep(2.0)

    receipt_paths = paths_since(CHAT_RECEIPT_DIR, started_epoch - 2, "ENGEL_UI_CHAT_MEETING_ROOM_*.json")
    rows, summary = summarize_receipts(receipt_paths, prompts)
    elapsed_seconds = round(time.monotonic() - started_mono, 3)
    phone_link_after = phone_link_snapshot()
    phones_live = int(phone_link_after.get("live_phone_worker_count") or 0) >= len(EXPECTED_PHONE_IPS)
    driver_submitted, driver_finished = soak_driver_reply_count(started_epoch)
    ct_memory = ct_persistent_memory_hits(prompts, started_epoch)
    ct_memory_ok = bool(ct_memory.get("ok"))
    ct_single_write_ok = bool(ct_memory.get("single_write_ok"))
    ct_training_eligible_ok = bool(ct_memory.get("training_eligible_ok"))
    local_only_ok = bool(ct_memory.get("local_only_ok"))
    ct_quality_ok = bool(ct_memory.get("quality_ok"))
    local_first_policy_ok = bool(ct_memory.get("local_first_or_verified_escalation_ok"))
    quality_policy_ok = bool(ct_memory.get("quality_or_verified_escalation_ok"))
    accepted_route_ok = local_first_policy_ok if args.allow_verified_provider_escalation else local_only_ok
    accepted_quality_ok = quality_policy_ok if args.allow_verified_provider_escalation else ct_quality_ok
    meeting_room_events = meeting_room_event_hits(prompts, started_epoch)
    meeting_room_events_ok = bool(meeting_room_events.get("ok"))
    # Two accepted proofs that visible turns really happened:
    #  - legacy fallback lane: MEETING_ROOM receipts for every prompt
    #  - modern server-first lane: the app driver's reply_finished events
    legacy_lane_ok = (
        summary["receipt_count"] >= len(prompts)
        and summary["main_server_chat_used_count"] >= len(prompts)
        and summary["persistent_chat_memory_appended_count"] >= len(prompts)
    )
    driver_lane_ok = driver_finished >= len(prompts)
    passed = (
        elapsed_seconds >= args.minutes * 60.0
        and (legacy_lane_ok or driver_lane_ok)
        and ct_memory_ok
        and ct_single_write_ok
        and ct_training_eligible_ok
        and accepted_route_ok
        and accepted_quality_ok
        and meeting_room_events_ok
        and phones_live
        and process.poll() is None
    )
    result = {
        "schema": "engel_visible_chat_ui_soak_report_v1",
        "ok": passed,
        "status": "PASS" if passed else "FAIL",
        "run_id": run_id,
        "mode": args.mode,
        "started_at_utc": datetime.fromtimestamp(started_epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "finished_at_utc": iso_now(),
        "requested_minutes": args.minutes,
        "elapsed_seconds": elapsed_seconds,
        "app_pid": process.pid,
        "app_still_running": process.poll() is None,
        "template": str(template),
        "prompt_count": len(prompts),
        "phone_link_before": phone_link_before,
        "phone_link_after": phone_link_after,
        "phones_live_required": True,
        "phones_live": phones_live,
        "driver_prompts_submitted": driver_submitted,
        "driver_replies_finished": driver_finished,
        "legacy_receipt_lane_ok": legacy_lane_ok,
        "driver_event_lane_ok": driver_lane_ok,
        "ct_persistent_memory_ok": ct_memory_ok,
        "ct_single_write_ok": ct_single_write_ok,
        "ct_training_eligible_ok": ct_training_eligible_ok,
        "local_only_model_receipts_ok": local_only_ok,
        "allow_verified_provider_escalation": args.allow_verified_provider_escalation,
        "local_first_or_verified_escalation_ok": local_first_policy_ok,
        "verified_pipeline_escalation_count": int(ct_memory.get("verified_pipeline_escalation_count") or 0),
        "ct_model_quality_ok": ct_quality_ok,
        "quality_or_verified_escalation_ok": quality_policy_ok,
        "ct_persistent_memory": ct_memory,
        "meeting_room_events_ok": meeting_room_events_ok,
        "meeting_room_events": meeting_room_events,
        "summary": summary,
        "receipts": rows,
    }
    json_path = REPORT_DIR / f"ENGEL_VISIBLE_CHAT_UI_SOAK_{run_id}.json"
    md_path = REPORT_DIR / f"ENGEL_VISIBLE_CHAT_UI_SOAK_{run_id}.md"
    write_json(json_path, result)
    md_path.write_text(
        "\n".join(
            [
                f"# Engel Visible Chat UI Soak {result['status']}",
                "",
                f"- Run: `{run_id}`",
                f"- Elapsed seconds: `{elapsed_seconds}`",
                f"- Prompt receipts: `{summary['receipt_count']}/{len(prompts)}`",
                f"- CT persistent memory: `{ct_memory_ok}`",
                f"- CT single-writer persistence: `{ct_single_write_ok}`",
                f"- CT training eligibility: `{ct_training_eligible_ok}`",
                f"- CT local-model quality gates: `{ct_quality_ok}`",
                f"- Local-first or verified escalation: `{local_first_policy_ok}`",
                f"- Verified provider escalations: `{int(ct_memory.get('verified_pipeline_escalation_count') or 0)}`",
                f"- Meeting room events: `{meeting_room_events_ok}` ({meeting_room_events.get('required_prompt_count', 0)} required)",
                f"- Server chat used: `{summary['main_server_chat_used_count']}`",
                f"- Persistent memory appended: `{summary['persistent_chat_memory_appended_count']}`",
                f"- Live phones: `{phone_link_after.get('live_phone_worker_count', 0)}/{len(EXPECTED_PHONE_IPS)}`",
                f"- Max latency ms: `{summary['max_latency_ms']}`",
                f"- Report JSON: `{json_path}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"event": "visible_chat_ui_soak_complete", "status": result["status"], "report": str(json_path)}, sort_keys=True), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
