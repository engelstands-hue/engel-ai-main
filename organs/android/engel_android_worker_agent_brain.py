#!/usr/bin/env python3
"""Per-phone Agent + Brain bindings for Engel Android remote workers.

Read-only registry helpers. Does not enable on-device model_runtime, Discord on
the phone, trusted-memory writes, or phone control of Engel.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engel_project_paths import resolve_engel_app_root

APP_ROOT = resolve_engel_app_root(__file__)
MAP_PATH = APP_ROOT / "memory" / "ENGEL_ANDROID_WORKER_AGENT_BRAIN_MAP_V1.json"

WORKER_IDS = (
    "android_worker_alpha",
    "android_worker_beta",
    "android_worker_gamma",
)


def load_agent_brain_map() -> dict[str, Any]:
    try:
        data = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def worker_bindings() -> dict[str, dict[str, Any]]:
    payload = load_agent_brain_map()
    workers = payload.get("workers")
    if not isinstance(workers, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for worker_id, record in workers.items():
        if isinstance(record, dict) and str(record.get("worker_id") or worker_id):
            out[str(record.get("worker_id") or worker_id)] = record
    return out


def binding_for_worker(worker_id: str) -> dict[str, Any]:
    return dict(worker_bindings().get(str(worker_id), {}) or {})


def binding_for_serial(serial: str) -> dict[str, Any]:
    needle = str(serial or "").strip()
    if not needle:
        return {}
    for record in worker_bindings().values():
        if str(record.get("adb_serial") or "") == needle:
            return dict(record)
    return {}


def identity_overlay(worker_id: str) -> dict[str, Any]:
    """Fields merged into worker_identity.json for phone HUD + provisioning."""
    record = binding_for_worker(worker_id)
    if not record:
        return {}
    return {
        "agent_id": record.get("agent_id"),
        "agent_name": record.get("agent_name"),
        "brain_id": record.get("brain_id"),
        "brain_label": record.get("brain_label"),
        "brain_lane": record.get("brain_lane"),
        "meeting_room_label": record.get("meeting_room_label"),
        "agent_brain_schema": "ENGEL_ANDROID_WORKER_AGENT_BRAIN_MAP_V1",
        "controls_engel": False,
        "discord_on_phone": False,
        "model_runtime": False,
    }


def status_lines() -> list[str]:
    lines = [
        "# Android Worker Agent + Brain Map",
        "",
        f"Map: `{MAP_PATH.name}`",
        "Authority: Josh > Guardian > Engel/runtime",
        "Phone does not control Engel. Discord never installs on phones.",
        "",
    ]
    bindings = worker_bindings()
    if not bindings:
        lines.append("No worker bindings loaded.")
        return lines
    for worker_id in WORKER_IDS:
        record = bindings.get(worker_id) or {}
        lines.append(f"## {worker_id}")
        lines.append(f"  Agent:  {record.get('agent_name') or '(missing)'}")
        lines.append(f"  Brain:  {record.get('brain_label') or '(missing)'} [{record.get('brain_id') or '?'}]")
        lines.append(f"  Lane:   {record.get('brain_lane') or '(missing)'}")
        lines.append(f"  Serial: {record.get('adb_serial') or '(missing)'}")
        lines.append(f"  Role:   {record.get('role') or '(missing)'}")
        lines.append("")
    return lines


def render_android_worker_agent_brain_status(payload: str = "") -> str:
    del payload  # status-only
    return "\n".join(status_lines()).rstrip() + "\n"


def pair_status_fields(worker_id: str) -> dict[str, Any]:
    """Status-only Agent+Brain fields for LAN /pair and /worker/status."""
    record = binding_for_worker(worker_id)
    if not record:
        return {
            "agent_assigned": False,
            "agent_name": None,
            "brain_label": None,
            "discord_on_phone": False,
            "controls_engel": False,
        }
    return {
        "agent_assigned": True,
        "agent_id": record.get("agent_id"),
        "agent_name": record.get("agent_name"),
        "brain_id": record.get("brain_id"),
        "brain_label": record.get("brain_label"),
        "brain_lane": record.get("brain_lane"),
        "discord_on_phone": False,
        "controls_engel": False,
        "model_runtime_on_phone": False,
    }
