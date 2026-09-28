#!/usr/bin/env python3
"""Build a fail-closed provider capability map from real completion evidence.

Configured credentials, reachable tunnels, and running CLI workers prove only
connection. Automatic routing requires a recent, quality-passed completion
through Engel's final provider chat lane with no newer failed attempt.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable
from urllib import request


ROOT = Path(os.environ.get("ENGEL_ROOT") or Path(__file__).resolve().parents[1])
STATE_PATH = Path(
    os.environ.get("ENGEL_PROVIDER_CAPABILITY_MAP_PATH")
    or ROOT / "run" / "self_update" / "providers" / "provider_capability_map.json"
)
INTEGRATED_RECEIPT_ROOT = ROOT / "reports" / "engel_standalone_chat_llm" / "chat_receipts"
AUTO_PROOF_MAX_AGE_SECONDS = int(
    os.environ.get("ENGEL_PROVIDER_AUTO_PROOF_MAX_AGE_SECONDS", str(24 * 3600))
)
HISTORY_MAX_AGE_SECONDS = int(
    os.environ.get("ENGEL_PROVIDER_HISTORY_MAX_AGE_SECONDS", str(14 * 86400))
)
MAP_MAX_AGE_SECONDS = int(os.environ.get("ENGEL_PROVIDER_MAP_MAX_AGE_SECONDS", "300"))
MAX_RECEIPTS_PER_ROOT = 800

PROVIDERS: dict[str, dict[str, Any]] = {
    "local": {
        "label": "CT246 Local LLM",
        "bridge_id": "local_llm",
        "direct_roots": [],
    },
    "openai": {
        "label": "ChatGPT/OpenAI",
        "bridge_id": "chatgpt",
        "direct_roots": ["reports/chatgpt_browser_bridge"],
    },
    "anthropic": {
        "label": "Claude/Anthropic",
        "bridge_id": "claude",
        "direct_roots": ["reports/claude_cli_bridge"],
    },
    "xai": {
        "label": "Grok/xAI",
        "bridge_id": "grok",
        "direct_roots": ["reports/grok_cli_bridge", "reports/grok_bridge"],
    },
    "gemini": {
        "label": "Gemini/Google",
        "bridge_id": "gemini",
        "direct_roots": ["reports/gemini_api_bridge"],
    },
    "codex": {
        "label": "Codex/OpenAI",
        "bridge_id": "codex",
        "direct_roots": ["reports/codex_cli_bridge"],
    },
    "nvidia": {
        "label": "NVIDIA NIM",
        "bridge_id": "nvidia_nim",
        "direct_roots": ["reports/nvidia_nim_bridge"],
    },
}

PROVIDER_ALIASES = {
    "local": "local",
    "local_llm": "local",
    "main_server_fast_local": "local",
    "openai": "openai",
    "chatgpt": "openai",
    "anthropic": "anthropic",
    "claude": "anthropic",
    "xai": "xai",
    "grok": "xai",
    "gemini": "gemini",
    "codex": "codex",
    "nvidia": "nvidia",
    "nim": "nvidia",
    "nvidia_nim": "nvidia",
    "nvidia-nim": "nvidia",
}

TASK_FAMILY_BY_ROUTE = {
    "chat_or_customer": "general_chat",
    "local_failure_general": "general_chat",
    "code_or_review": "coding_review",
    "current_or_social": "current_social",
    "google_or_long_context": "google_long_context",
}


class CapabilityMapError(ValueError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def atomic_write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return path


def fetch_json(url: str, timeout: float = 20.0) -> dict[str, Any]:
    with request.urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise CapabilityMapError(f"JSON object required from {url}")
    return payload


def normalize_provider(value: Any) -> str:
    text = str(value or "").strip().casefold().replace("-", "_")
    if text in PROVIDER_ALIASES:
        return PROVIDER_ALIASES[text]
    joined = text.replace("_", " ")
    if "chatgpt" in joined or "openai" in joined:
        return "openai"
    if "claude" in joined or "anthropic" in joined:
        return "anthropic"
    if "grok" in joined or "xai" in joined or "x.ai" in joined:
        return "xai"
    if "gemini" in joined:
        return "gemini"
    if "codex" in joined:
        return "codex"
    if "local" in joined or "llama" in joined:
        return "local"
    return ""


def _receipt_provider(payload: dict[str, Any], path: Path, direct_provider: str = "") -> str:
    if direct_provider:
        return direct_provider
    for key in ("selected_provider", "provider", "runtime_provider", "source"):
        provider = normalize_provider(payload.get(key))
        if provider:
            return provider
    return normalize_provider(path.name)


def _receipt_time(payload: dict[str, Any], path: Path) -> datetime:
    parsed = parse_utc(
        payload.get("updated_at_utc")
        or payload.get("completed_at_utc")
        or payload.get("created_at_utc")
    )
    return parsed or datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _reply_present(payload: dict[str, Any]) -> bool:
    return bool(str(payload.get("assistant_reply") or payload.get("assistant_output_text") or "").strip())


def _integrated_success(payload: dict[str, Any], provider: str) -> tuple[bool, bool]:
    if provider == "local":
        success = payload.get("ok") is True and _reply_present(payload)
        status = str(payload.get("status") or "").casefold()
        if "blocked" in status or "unavailable" in status or "failed" in status:
            success = False
        quality = bool(
            payload.get("chat_quality_gate_passed") is True
            or payload.get("quality_gate_passed") is True
            or payload.get("ok") is True
        )
        return success, bool(success and quality)

    success = bool(
        payload.get("ok") is True
        and payload.get("provider_bridge_used") is True
        and str(payload.get("status") or "").casefold() == "provider bridge replied"
        and _reply_present(payload)
    )
    final_quality = payload.get("provider_final_semantic_quality")
    quality = bool(
        payload.get("provider_reply_quality_gate_passed") is True
        and (
            not isinstance(final_quality, dict)
            or not final_quality
            or final_quality.get("ok") is True
        )
    )
    return success, bool(success and quality)


def _direct_success(payload: dict[str, Any]) -> bool:
    return bool(payload.get("ok") is True and _reply_present(payload))


def _task_family(payload: dict[str, Any], provider: str) -> str:
    route = str(payload.get("provider_bridge_route_reason") or "").strip().casefold()
    if route in TASK_FAMILY_BY_ROUTE:
        return TASK_FAMILY_BY_ROUTE[route]
    schema = str(payload.get("schema") or "").casefold()
    status = str(payload.get("status") or "").casefold()
    if provider == "local":
        if "code" in schema or "build" in schema or "code" in status or "build" in status:
            return "coding_build"
        if "arithmetic" in schema or "math" in status:
            return "math"
        if "chat" in schema or "chat" in status:
            return "general_chat"
    return "unknown"


def _sanitized_event(
    path: Path,
    payload: dict[str, Any],
    *,
    provider: str,
    source_kind: str,
    observed: datetime,
) -> dict[str, Any]:
    completed = _receipt_time(payload, path)
    if source_kind == "integrated":
        success, quality = _integrated_success(payload, provider)
    else:
        success = _direct_success(payload)
        quality = success
    model = str(payload.get("runtime_provider") or payload.get("model") or "")[:120]
    status = str(payload.get("status") or ("completion returned" if success else "completion failed"))[:180]
    return {
        "receipt_path": str(path),
        "receipt_sha256": sha256_file(path),
        "completed_at_utc": completed.isoformat().replace("+00:00", "Z"),
        "age_seconds": round(max(0.0, (observed - completed).total_seconds()), 1),
        "provider": provider,
        "source_kind": source_kind,
        "success": success,
        "quality_passed": quality,
        "automatic_route_qualified": bool(source_kind == "integrated" and success and quality),
        "model": model,
        "status": status,
        "task_family": _task_family(payload, provider),
        "latency_ms": int(payload.get("server_request_latency_ms") or payload.get("duration_ms") or 0),
    }


def _paths(root: Path) -> Iterable[tuple[Path, str, str]]:
    if INTEGRATED_RECEIPT_ROOT == ROOT / "reports" / "engel_standalone_chat_llm" / "chat_receipts":
        integrated_root = root / "reports" / "engel_standalone_chat_llm" / "chat_receipts"
    else:
        integrated_root = INTEGRATED_RECEIPT_ROOT
    if integrated_root.is_dir():
        for path in sorted(integrated_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:MAX_RECEIPTS_PER_ROOT]:
            yield path, "integrated", ""
    for provider, definition in PROVIDERS.items():
        for relative in definition["direct_roots"]:
            direct_root = root / relative
            if not direct_root.is_dir():
                continue
            for path in sorted(direct_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:MAX_RECEIPTS_PER_ROOT]:
                yield path, "direct", provider


def collect_events(root: Path, observed: datetime) -> dict[str, list[dict[str, Any]]]:
    events = {provider: [] for provider in PROVIDERS}
    seen: set[str] = set()
    for path, source_kind, direct_provider in _paths(root):
        key = str(path.resolve(strict=False)).casefold()
        if key in seen:
            continue
        seen.add(key)
        payload = read_json(path)
        if not payload:
            continue
        provider = _receipt_provider(payload, path, direct_provider)
        if provider not in events:
            continue
        event = _sanitized_event(
            path,
            payload,
            provider=provider,
            source_kind=source_kind,
            observed=observed,
        )
        if event["age_seconds"] <= HISTORY_MAX_AGE_SECONDS:
            events[provider].append(event)
    for provider in events:
        events[provider].sort(key=lambda item: item["completed_at_utc"], reverse=True)
    return events


def _connection_state(
    provider: str,
    bridge_registry: dict[str, Any],
    provider_status: dict[str, Any],
) -> tuple[bool, bool, list[str]]:
    definition = PROVIDERS[provider]
    bridges = bridge_registry.get("bridges") if isinstance(bridge_registry.get("bridges"), dict) else {}
    bridge = bridges.get(definition["bridge_id"]) if isinstance(bridges.get(definition["bridge_id"]), dict) else {}
    if provider == "local":
        return True, bridge.get("connected") is True, []
    provider_items = provider_status.get("providers") if isinstance(provider_status.get("providers"), dict) else {}
    status = provider_items.get(provider) if isinstance(provider_items.get(provider), dict) else {}
    enabled = bool(status.get("enabled") is True or bridge.get("enabled") is True)
    route = status.get("local_route") if isinstance(status.get("local_route"), dict) else {}
    direct_ready = bool(status.get("direct_api_ready") is True)
    route_ready = bool(status.get("local_route_ready") is True or route.get("ok") is True or route.get("usable") is True)
    connected = bool(
        bridge.get("connected") is True
        or status.get("connected") is True
        or (
            status.get("enabled") is True
            and (direct_ready or route_ready)
        )
    )
    route_failures: list[str] = []
    worker_state = (
        (route.get("worker_status") or {}).get("state", {})
        if isinstance(route.get("worker_status"), dict)
        else {}
    )
    if not connected:
        route_failures.append("current_connection_probe_failed")
    elif route and route.get("ok") is False and not direct_ready:
        route_failures.append("current_route_probe_failed")
    if worker_state and worker_state.get("last_probe_ok") is False and not direct_ready:
        route_failures.append("current_worker_completion_probe_failed")
    return enabled, connected, route_failures


def _public_evidence(event: dict[str, Any] | None) -> dict[str, Any]:
    if not event:
        return {}
    return {
        key: event[key]
        for key in (
            "receipt_path",
            "receipt_sha256",
            "completed_at_utc",
            "age_seconds",
            "source_kind",
            "success",
            "quality_passed",
            "automatic_route_qualified",
            "model",
            "status",
            "task_family",
            "latency_ms",
        )
    }


def _provider_capability(
    provider: str,
    events: list[dict[str, Any]],
    bridge_registry: dict[str, Any],
    provider_status: dict[str, Any],
) -> dict[str, Any]:
    enabled, connected, route_failures = _connection_state(provider, bridge_registry, provider_status)
    latest_attempt = events[0] if events else None
    successful = [event for event in events if event["success"] is True]
    qualified = [event for event in events if event["automatic_route_qualified"] is True]
    last_success = successful[0] if successful else None
    last_qualified = qualified[0] if qualified else None
    completion_fresh = bool(
        last_qualified and float(last_qualified["age_seconds"]) <= AUTO_PROOF_MAX_AGE_SECONDS
    )
    newer_failure = bool(
        latest_attempt
        and latest_attempt["success"] is not True
        and (
            last_qualified is None
            or latest_attempt["completed_at_utc"] > last_qualified["completed_at_utc"]
        )
    )
    degraded_reasons = list(route_failures)
    if not enabled:
        degraded_reasons.append("disabled")
    if enabled and not connected:
        degraded_reasons.append("not_connected")
    if not last_qualified:
        degraded_reasons.append("no_quality_passed_engel_completion")
    elif not completion_fresh:
        degraded_reasons.append("completion_proof_stale")
    if newer_failure:
        degraded_reasons.append("newer_completion_failure_after_last_success")

    automatic_routable = bool(
        provider != "local"
        and enabled
        and connected
        and completion_fresh
        and not newer_failure
        and not route_failures
    )
    degraded = bool(not completion_fresh) if provider == "local" else not automatic_routable
    strengths: dict[str, dict[str, Any]] = {}
    for event in qualified:
        family = str(event.get("task_family") or "unknown")
        if family == "unknown":
            continue
        item = strengths.setdefault(
            family,
            {"task_family": family, "successful_sample_count": 0, "last_success_at_utc": "", "models": []},
        )
        item["successful_sample_count"] += 1
        item["last_success_at_utc"] = max(item["last_success_at_utc"], event["completed_at_utc"])
        if event.get("model") and event["model"] not in item["models"]:
            item["models"].append(event["model"])

    attempts = len(events)
    successes = len(successful)
    quality_successes = len(qualified)
    return {
        "provider_id": provider,
        "label": PROVIDERS[provider]["label"],
        "bridge_id": PROVIDERS[provider]["bridge_id"],
        "enabled": enabled,
        "connected": connected,
        "completion_proven": completion_fresh and not newer_failure,
        "automatic_routable": automatic_routable,
        "explicit_attempt_allowed": bool(provider != "local" and enabled),
        "degraded": degraded,
        "outage": bool((enabled and not connected) or newer_failure or route_failures),
        "degraded_reasons": sorted(set(degraded_reasons)),
        "last_attempt": _public_evidence(latest_attempt),
        "last_success": _public_evidence(last_success),
        "last_automatic_route_proof": _public_evidence(last_qualified),
        "last_successful_model": str((last_success or {}).get("model") or ""),
        "evidence_window": {
            "window_seconds": HISTORY_MAX_AGE_SECONDS,
            "attempt_count": attempts,
            "completion_success_count": successes,
            "quality_passed_engel_completion_count": quality_successes,
            "failure_count": attempts - successes,
            "completion_success_rate": round(successes / attempts, 4) if attempts else 0.0,
        },
        "proven_task_families": [strengths[key] for key in sorted(strengths)],
    }


def build_capability_map(
    bridge_registry: dict[str, Any],
    provider_status: dict[str, Any],
    *,
    root: Path = ROOT,
    observed_at: datetime | None = None,
    persist: bool = True,
    state_path: Path = STATE_PATH,
) -> dict[str, Any]:
    observed = observed_at or datetime.now(timezone.utc)
    events = collect_events(root, observed)
    providers = {
        provider: _provider_capability(provider, events[provider], bridge_registry, provider_status)
        for provider in PROVIDERS
    }
    auto = [provider for provider, item in providers.items() if provider != "local" and item["automatic_routable"]]
    degraded = [provider for provider, item in providers.items() if item["degraded"]]
    outages = [provider for provider, item in providers.items() if item["outage"]]
    payload = {
        "schema": "ENGEL_PROVIDER_COMPLETION_CAPABILITY_MAP_V1",
        "ok": providers["local"]["completion_proven"],
        "status": "ready" if providers["local"]["completion_proven"] else "local completion proof missing or stale",
        "source_of_truth": "CT246 /opt/engel",
        "observed_at_utc": observed.isoformat().replace("+00:00", "Z"),
        "map_max_age_seconds": MAP_MAX_AGE_SECONDS,
        "automatic_completion_proof_max_age_seconds": AUTO_PROOF_MAX_AGE_SECONDS,
        "local_model_first": True,
        "provider_escalation_policy": "automatic providers only after local failure and only when automatic_routable; explicit owner selection may attempt a degraded enabled provider and must return honest failure",
        "providers": providers,
        "automatic_provider_ids": auto,
        "degraded_provider_ids": degraded,
        "outage_provider_ids": outages,
        "connection_is_not_completion": True,
        "prompt_or_reply_content_stored": False,
        "credential_metadata_stored": False,
        "mutation": {
            "provider_called": False,
            "service_restarted": False,
            "source_changed": False,
            "worker_command_sent": False,
            "storage_changed": False,
        },
    }
    payload["map_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if persist:
        atomic_write_json(state_path, payload)
    return payload


def validate_capability_map(payload: dict[str, Any], *, observed_at: datetime | None = None) -> list[str]:
    errors: list[str] = []
    observed = observed_at or datetime.now(timezone.utc)
    if payload.get("schema") != "ENGEL_PROVIDER_COMPLETION_CAPABILITY_MAP_V1":
        errors.append("schema mismatch")
    providers = payload.get("providers") if isinstance(payload.get("providers"), dict) else {}
    if set(providers) != set(PROVIDERS):
        errors.append("provider inventory mismatch")
    completed = parse_utc(payload.get("observed_at_utc"))
    if not completed or (observed - completed).total_seconds() > MAP_MAX_AGE_SECONDS:
        errors.append("capability map stale")
    for provider, item in providers.items():
        if not isinstance(item, dict):
            errors.append(f"{provider} entry invalid")
            continue
        if item.get("automatic_routable") is True and item.get("completion_proven") is not True:
            errors.append(f"{provider} routable without completion proof")
        if item.get("automatic_routable") is True and item.get("connected") is not True:
            errors.append(f"{provider} routable without connection")
        if item.get("completion_proven") is True:
            proof = item.get("last_automatic_route_proof") if isinstance(item.get("last_automatic_route_proof"), dict) else {}
            if proof.get("automatic_route_qualified") is not True:
                errors.append(f"{provider} completion proof is not route-qualified")
    forbidden_keys = {"prompt", "assistant_reply", "assistant_output_text", "secret_source", "value_length", "api_key", "access_token", "refresh_token"}

    def visit(value: Any, path: str = "") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).casefold() in forbidden_keys:
                    errors.append("forbidden key: " + (path + "." + str(key)).strip("."))
                visit(item, (path + "." + str(key)).strip("."))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{path}[{index}]")

    visit(payload)
    return sorted(set(errors))


def load_status(path: Path = STATE_PATH, *, observed_at: datetime | None = None) -> dict[str, Any]:
    payload = read_json(path)
    errors = validate_capability_map(payload, observed_at=observed_at)
    if errors:
        return {
            "schema": "ENGEL_PROVIDER_COMPLETION_CAPABILITY_MAP_STATUS_V1",
            "ok": False,
            "status": "stale or invalid",
            "errors": errors,
            "automatic_provider_ids": [],
            "state_path": str(path),
        }
    result = dict(payload)
    result["state_path"] = str(path)
    return result


def filter_automatic_candidates(
    candidates: Iterable[str],
    payload: dict[str, Any],
    *,
    observed_at: datetime | None = None,
) -> list[str]:
    if validate_capability_map(payload, observed_at=observed_at):
        return []
    providers = payload.get("providers") if isinstance(payload.get("providers"), dict) else {}
    result: list[str] = []
    for candidate in candidates:
        provider = normalize_provider(candidate)
        item = providers.get(provider) if isinstance(providers.get(provider), dict) else {}
        if provider and provider != "local" and item.get("automatic_routable") is True and provider not in result:
            result.append(provider)
    return result


def explicit_attempt_allowed(provider: str, payload: dict[str, Any]) -> bool:
    item = (payload.get("providers") or {}).get(normalize_provider(provider), {})
    return isinstance(item, dict) and item.get("explicit_attempt_allowed") is True


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") is True else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel provider completion capability map")
    parser.add_argument("command", choices=["observe", "status"])
    parser.add_argument("--bridge-registry-url", default="http://127.0.0.1:8765/bridges/registry")
    parser.add_argument("--provider-status-url", default="http://127.0.0.1:8765/providers/status")
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            return _emit(load_status())
        bridge_registry = fetch_json(args.bridge_registry_url)
        provider_status = fetch_json(args.provider_status_url)
        payload = build_capability_map(bridge_registry, provider_status)
        errors = validate_capability_map(payload)
        if errors:
            payload["ok"] = False
            payload["status"] = "invalid"
            payload["validation_errors"] = errors
        return _emit(payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _emit({"schema": "ENGEL_PROVIDER_COMPLETION_CAPABILITY_MAP_ERROR_V1", "ok": False, "status": "blocked", "error": str(exc)})


if __name__ == "__main__":
    raise SystemExit(main())
