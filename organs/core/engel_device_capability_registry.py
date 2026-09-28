#!/usr/bin/env python3
"""Engel device capability registry for Meeting Room routing.

This is read-only routing metadata. It helps Engel agents choose the right
device/worker for a job without granting phones any extra authority.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from engel_android_worker_prompt_signals import is_android_lan_pairing_request
from engel_project_paths import resolve_engel_app_root


APP_ROOT = resolve_engel_app_root(__file__)
REMOTE_WORKERS_ROOT = APP_ROOT / "remote_workers"
PHONE_MAP_PATH = APP_ROOT / "memory" / "ENGEL_PHONE_DEVICE_MAP_V1.json"
REPORT_DIR = APP_ROOT / "reports" / "meeting_rooms"


JOB_KEYWORDS: dict[str, tuple[str, ...]] = {
    "summarize_text": ("summarize", "summary", "notes", "research note", "explain"),
    "draft_research_note": ("research note", "research draft", "source note"),
    "draft_candidate_json": ("json", "candidate json", "extract fields", "structured data"),
    "draft_code_artifact": (
        "code",
        "python",
        "dart",
        "script",
        "function",
        "snippet",
        "implementation",
        "game",
        "video game",
        "maze",
        "puzzle",
        "playable",
        "runner",
        "courier",
        "arcade",
        "canvas",
    ),
    "web_research_brief": ("internet", "web search", "search online", "research online", "lookup", "look up"),
    "format_report_draft": ("format report", "report draft", "pdf", "artifact", "layout"),
    "classify_file": ("classify", "label", "tag", "category"),
    "compute_small_local_task": ("compute", "calculate", "math", "small local task"),
}


PREFERRED_BY_JOB: dict[str, str] = {
    "summarize_text": "android_worker_alpha",
    "draft_research_note": "android_worker_alpha",
    "draft_code_artifact": "android_worker_alpha",
    "web_research_brief": "android_worker_alpha",
    "draft_candidate_json": "android_worker_beta",
    "format_report_draft": "android_worker_beta",
    "classify_file": "android_worker_beta",
    "compute_small_local_task": "android_worker_gamma",
}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _phone_map_by_worker() -> dict[str, dict[str, Any]]:
    payload = _read_json(PHONE_MAP_PATH)
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(payload, dict):
        return out
    for phone in payload.get("phones", []):
        if isinstance(phone, dict) and phone.get("assigned_worker_id"):
            out[str(phone["assigned_worker_id"])] = phone
    for worker in payload.get("unassigned_workers", []):
        if isinstance(worker, dict) and worker.get("worker_id"):
            out.setdefault(str(worker["worker_id"]), worker)
    return out


def load_device_capabilities() -> dict[str, dict[str, Any]]:
    """Return normalized worker capability records keyed by worker_id."""
    phone_map = _phone_map_by_worker()
    registry: dict[str, dict[str, Any]] = {}
    for config_path in sorted(REMOTE_WORKERS_ROOT.glob("android_worker_*/config/worker_capabilities.json")):
        worker_id = config_path.parent.parent.name
        caps = _read_json(config_path)
        if not isinstance(caps, dict):
            continue
        identity = _read_json(config_path.parent / "worker_identity.json")
        if not isinstance(identity, dict):
            identity = {}
        phone = phone_map.get(worker_id, {})
        allowed_jobs = list(caps.get("allowed_jobs") or caps.get("allowed_task_types") or [])
        blocked = list(caps.get("blocked_task_types") or [])
        device_label = phone.get("marketing_name") or identity.get("device_label") or phone.get("status") or "unassigned"
        registry[worker_id] = {
            "worker_id": worker_id,
            "worker_name": caps.get("worker_name") or identity.get("worker_name") or worker_id,
            "role": caps.get("role") or identity.get("role") or "",
            "device_label": device_label,
            "model": phone.get("model") or phone.get("marketing_name") or identity.get("phone_model") or "",
            "adb_serial": phone.get("adb_serial"),
            "android_release": phone.get("android_release"),
            "network_transport": "WiFi / LAN polling",
            "assigned": phone.get("status") != "no_phone_assigned",
            "allowed_jobs": allowed_jobs,
            "blocked_task_types": blocked,
            "candidate_outputs_only": bool(caps.get("candidate_outputs_only", True)),
            "safe_to_auto_apply": False,
            "trusted_memory_write": False,
            "source_mutation": False,
            "route_mutation": False,
            "provider_network": False,
            "best_for": _best_for(worker_id, allowed_jobs),
        }
    return registry


def _best_for(worker_id: str, allowed_jobs: list[str]) -> list[str]:
    labels = []
    for job in allowed_jobs:
        if job == "summarize_text":
            labels.append("summaries and research notes")
        elif job == "draft_candidate_json":
            labels.append("candidate JSON and field extraction")
        elif job == "draft_code_artifact":
            labels.append("candidate Python/code drafting")
        elif job == "web_research_brief":
            labels.append("bounded web research briefs")
        elif job == "format_report_draft":
            labels.append("report formatting drafts")
        elif job == "classify_file":
            labels.append("classification and labels")
        elif job == "compute_small_local_task":
            labels.append("small local compute")
    if worker_id == "android_worker_alpha" and "summaries and research notes" not in labels:
        labels.append("summaries and research notes")
    if worker_id == "android_worker_beta" and "candidate JSON and field extraction" not in labels:
        labels.append("candidate JSON and field extraction")
    return sorted(set(labels))


def infer_job_type_from_text(text: str, fallback: str = "summarize_text") -> str:
    low = str(text or "").lower()
    if is_android_lan_pairing_request(low):
        return "return_status"
    direct_file = any(
        needle in low
        for needle in ("make this file", "mkae this file", "create file", "write file", "put it here", "save file")
    )
    direct_language = any(
        needle in low
        for needle in (
            "app wording",
            "write clearer app wording",
            "clearer wording",
            "language for this app",
            "app language",
            "microcopy",
            "error message",
            "error messages",
            "result messages",
            "button labels",
            "status copy",
            "friendly text",
            "plain words",
            "short descriptions",
        )
    )
    language_command = low.strip().startswith(
        (
            "help me write",
            "help with app wording",
            "write clearer app wording",
            "lets work on the language",
            "let's work on the language",
        )
    )
    direct_pdf = "pdf" in low and any(
        needle in low
        for needle in ("make me a pdf", "make a pdf", "create a pdf", "write a pdf", "generate a pdf", "pdf report", "pdf field", "pdf safety", "pdf graph", "pdf about")
    )
    direct_search = any(
        needle in low
        for needle in ("search internet", "search online", "look online", "web search", "research online", "look up online")
    )
    direct_code = any(
        needle in low
        for needle in (
            "write code",
            "write me code",
            "right me code",
            "rite me code",
            "code for",
            "make code",
            "create code",
            "script for",
            "function for",
        )
    )
    direct_game = (
        "video game" in low
        or "create a game" in low
        or "create game" in low
        or bool(re.search(r"\b(?:create|make|build(?!-)|draft)\s+(?:a|an)?\s*[^.?!]{0,80}\b(?:maze|puzzle|playable|runner|courier|arcade)\b", low))
        or (
            any(re.search(rf"\b{verb}\b", low) for verb in ("create", "make", "build", "draft"))
            and any(
                needle in low
                for needle in (
                    " game",
                    "maze",
                    "puzzle",
                    "playable",
                    "runner",
                    "courier",
                    "arcade",
                    "canvas",
                )
            )
        )
    )
    if direct_file:
        return "summarize_text"
    if direct_pdf:
        return "format_report_draft"
    if direct_search:
        return "web_research_brief"
    if direct_code:
        return "draft_code_artifact"
    if direct_language and language_command:
        return "summarize_text"
    if direct_game:
        return "draft_code_artifact"
    if direct_language:
        return "summarize_text"
    if any(needle in low for needle in JOB_KEYWORDS["web_research_brief"]):
        return "web_research_brief"
    if any(needle in low for needle in JOB_KEYWORDS["draft_code_artifact"]):
        return "draft_code_artifact"
    if "candidate json" in low or " json" in low or "json " in low or "extract fields" in low or "structured data" in low:
        return "draft_candidate_json"
    if "format report" in low or "report draft" in low or "pdf" in low or "artifact" in low or "layout" in low:
        return "format_report_draft"
    if "classify" in low or "label" in low or "tag" in low or "category" in low:
        return "classify_file"
    if "compute" in low or "calculate" in low or "math" in low or "small local task" in low:
        return "compute_small_local_task"
    if "summarize" in low or "summary" in low or "research note" in low:
        return "summarize_text"
    for job, needles in JOB_KEYWORDS.items():
        if any(needle in low for needle in needles):
            return job
    return fallback


def select_worker_for_job(job_type: str, text: str = "", requested_worker: str | None = None) -> dict[str, Any] | None:
    registry = load_device_capabilities()
    if requested_worker and requested_worker in registry:
        return registry[requested_worker]
    inferred = infer_job_type_from_text(text, "summarize_text")
    if inferred != "summarize_text":
        job = inferred
    else:
        job = job_type if job_type and job_type != "classify_text" else inferred
    preferred = PREFERRED_BY_JOB.get(job)
    if (
        preferred
        and preferred in registry
        and registry[preferred].get("assigned", False)
        and job in registry[preferred].get("allowed_jobs", [])
    ):
        return registry[preferred]
    candidates = [
        record for record in registry.values()
        if job in record.get("allowed_jobs", []) and record.get("assigned", False)
    ]
    if candidates:
        return sorted(candidates, key=lambda item: item["worker_id"])[0]
    fallback = registry.get("android_worker_alpha")
    return fallback or (next(iter(registry.values())) if registry else None)


def render_device_capability_registry() -> str:
    registry = load_device_capabilities()
    lines = [
        "# Engel Device Capability Registry",
        "",
        "Use this before assigning Meeting Room work to a device.",
        "",
    ]
    if not registry:
        lines.append("No device capability records found.")
        return "\n".join(lines)
    for worker_id, record in sorted(registry.items()):
        lines += [
            f"## {record.get('worker_name', worker_id)}",
            f"- worker_id: `{worker_id}`",
            f"- device: `{record.get('device_label')}`",
            f"- model: `{record.get('model')}`",
            f"- transport: `{record.get('network_transport')}`",
            f"- assigned: `{record.get('assigned')}`",
            f"- allowed_jobs: `{', '.join(record.get('allowed_jobs', []))}`",
            f"- best_for: `{', '.join(record.get('best_for', []))}`",
            "- blocked: source mutation, route mutation, trusted memory, provider/network, model runtime, Engel control",
            "",
        ]
    return "\n".join(lines).rstrip()


def write_device_capability_report() -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / "ENGEL_DEVICE_CAPABILITY_REGISTRY.md"
    path.write_text(render_device_capability_registry() + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(render_device_capability_registry())
