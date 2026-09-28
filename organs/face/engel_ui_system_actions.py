#!/usr/bin/env python3
"""Local Engel UI system actions for bounded worker connection requests."""
from __future__ import annotations

import json
import re
from typing import Any

from engel_android_worker_prompt_signals import (
    is_android_lan_pairing_request,
    mentions_android_worker_lane,
    normalize_prompt_low,
)


def _low(text: str) -> str:
    return normalize_prompt_low(text)


def classify_ui_system_action(text: str) -> str:
    low = _low(text)
    if not low.strip():
        return ""
    content_request = any(
        token in low
        for token in (
            "app wording",
            "write clearer",
            "clearer app wording",
            "error message",
            "error messages",
            "messages",
            "labels",
            "microcopy",
            "wording for",
            "help me write",
        )
    )
    if content_request:
        return ""
    if is_android_lan_pairing_request(text):
        return "show_lan_pairing_code"
    mentions_android_lane = mentions_android_worker_lane(low)
    if "wake" in low and any(token in low for token in ("usb", "android", "phone", "worker")):
        return "wake_android_workers"
    if re.search(r"\b(?:pair|connect)\b", low) and mentions_android_lane:
        return "connect_android_workers"
    return ""


def _compact_json(payload: dict[str, Any], limit: int = 900) -> str:
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _worker_rows_from_lan_auto_pair(text: str) -> list[str]:
    rows: list[str] = []
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if line.startswith("- PASS ") or line.startswith("- FAIL ") or line.startswith("No connected known"):
            rows.append(line)
    return rows


def _worker_modules() -> tuple[Any, Any]:
    """Load ADB + link-manager modules from the real workspace (not a stale bundle)."""
    names = (
        "engel_project_paths",
        "engel_remote_worker_lan_pairing",
        "engel_remote_worker_link_manager",
        "engel_adb_worker_manager",
    )
    try:
        from engel_project_paths import prefer_workspace_modules
    except ImportError:
        prefer_workspace_modules = _inline_prefer_workspace_modules
    prefer_workspace_modules(*names, caller_file=__file__)
    import engel_adb_worker_manager as adb_mgr
    import engel_remote_worker_link_manager as link_mgr

    return adb_mgr, link_mgr


def _inline_prefer_workspace_modules(*names: str, caller_file: Any | None = None) -> None:
    """Fallback for stale PyInstaller bundles whose engel_project_paths.py
    predates prefer_workspace_modules. Forces the workspace D: copy to win
    over the bundled _MEI / pyinstaller_tmp extract."""
    import os
    import sys

    candidate = None
    if caller_file is not None:
        directory = os.path.dirname(os.path.abspath(str(caller_file)))
        while directory and directory != os.path.dirname(directory):
            marker = os.path.join(directory, "engel_project_paths.py")
            lowered = directory.replace("\\", "/").lower()
            if os.path.isfile(marker) and "pyinstaller_tmp" not in lowered and "/_mei" not in lowered:
                candidate = directory
                break
            directory = os.path.dirname(directory)
    if not candidate:
        candidate = r"D:\b.WorkSpace\Engel App"
    if os.path.isdir(candidate):
        if candidate in sys.path:
            sys.path.remove(candidate)
        sys.path.insert(0, candidate)
    for name in names:
        module = sys.modules.get(name)
        if module is None:
            continue
        path_text = (getattr(module, "__file__", "") or "").replace("\\", "/").lower()
        if "pyinstaller_tmp" in path_text or "/_mei" in path_text:
            sys.modules.pop(name, None)


def _ensure_worker_link() -> tuple[str, int, dict[str, Any]]:
    adb_mgr, link_mgr = _worker_modules()
    host = adb_mgr._pc_lan_ip()
    port = 8765
    status = link_mgr.ensure_receiver_running(host, port, True)
    return host, port, status


def run_ui_system_action(text: str) -> dict[str, Any]:
    action = classify_ui_system_action(text)
    if not action:
        return {"accepted": False, "reason": "not a bounded Engel UI system action"}
    if action == "show_lan_pairing_code":
        return _show_lan_pairing_code()
    if action == "connect_android_workers":
        return _connect_android_workers()
    if action == "wake_android_workers":
        return _wake_android_workers()
    return {"accepted": False, "reason": f"unknown action: {action}"}


def _show_lan_pairing_code() -> dict[str, Any]:
    _adb_mgr, link_mgr = _worker_modules()
    host, port, _status = _ensure_worker_link()
    # Reuse the current session if it still has safe time left. The old
    # "always rotate on show code" path invalidated already-paired phones
    # every time the operator asked to see the code, so a phone that was
    # paired hours ago would drop the next time someone said "give me
    # pairing code". ensure_session_token() rotates only when there is no
    # session, or the current one is expired / about to expire.
    token = link_mgr.ensure_session_token()
    pairing_code = str(token.get("pairing_code") or "")
    expires_at = str(token.get("expires_at_utc") or "")
    rotated_now = bool(token.get("rotated"))
    state = link_mgr.link_status()
    code_source = "newly issued" if rotated_now else "existing active session (not invalidated)"
    summary_lines = [
        "WiFi/LAN worker pairing code is ready.",
        f"- LAN receiver: {host}:{port}",
        f"- Pairing code: {pairing_code}",
        f"- Expires: {expires_at}",
        f"- Code source: {code_source}",
        "- Valid for 8 hours from issue; paired phones keep the same code until expiry (6h+ continuity).",
        "- Enter this in the Engel Remote Worker Android app.",
        "- Safety: LAN pairing only; no WiFi ADB, no shell target, no phone control of Engel.",
    ]
    workers = state.get("workers") if isinstance(state, dict) else None
    if isinstance(workers, dict) and workers:
        for worker_id, record in sorted(workers.items()):
            if isinstance(record, dict) and record.get("last_seen_utc"):
                identity = record.get("identity") if isinstance(record.get("identity"), dict) else {}
                remote = identity.get("remote_address") or "LAN"
                summary_lines.append(f"- Seen: {worker_id} from {remote} at {record.get('last_seen_utc')}")
    return {
        "accepted": True,
        "action": "show_lan_pairing_code",
        "summary": "\n".join(summary_lines),
        "status": state,
    }


def _connect_android_workers() -> dict[str, Any]:
    adb_mgr, link_mgr = _worker_modules()
    host, port, status = _ensure_worker_link()
    token = link_mgr.ensure_session_token()
    pairing_code = str(token.get("pairing_code") or "")
    rotated_now = bool(token.get("rotated"))
    pair_text = adb_mgr.render_adb_workers_lan_auto_pair(f"{host}|{pairing_code}|{port}")
    rows = _worker_rows_from_lan_auto_pair(pair_text)
    final_status = link_mgr.link_status()
    token_action = (
        "Pairing token issued (new session) and pushed"
        if rotated_now
        else "Active pairing token reused (phones not invalidated) and pushed"
    )
    summary_lines = [
        "Worker connection lane is active.",
        f"- LAN receiver: {host}:{port}",
        f"- {token_action} to connected known Android worker apps through USB app-scoped storage.",
        "- Session stays valid up to 8 hours; worker continuity window is 6 hours.",
        "- Remote jobs/results stay on WiFi/LAN HTTP polling; USB is only provisioning/wake.",
        "- Safety: no WiFi ADB, no raw shell target, no job payload over USB, no phone control of Engel.",
    ]
    summary_lines.extend(rows or ["- No connected known worker phones found over USB. LAN receiver is ready for already-paired phones."])
    return {
        "accepted": True,
        "action": "connect_android_workers",
        "summary": "\n".join(summary_lines),
        "status": final_status,
    }


def _wake_android_workers() -> dict[str, Any]:
    _adb_mgr, link_mgr = _worker_modules()
    from engel_phone_wake_manager import wake_all_stale

    host, port, status = _ensure_worker_link()
    if not status.get("pairing_token_hint"):
        link_mgr.rotate_token()
    results = wake_all_stale(stale_after_seconds=0, apply=True, write_report=True)
    lines = [
        "USB wake/provision lane finished.",
        f"- LAN receiver: {host}:{port}",
        "- Wake only: refreshed app-scoped pairing config, woke screen, relaunched Engel Remote Worker app.",
        "- Jobs/results still move over WiFi/LAN; USB did not carry job payloads.",
    ]
    for result in results:
        mark = "PASS" if result.success else "FAIL"
        lines.append(f"- {mark} {result.worker_id} ({result.label}): {result.detail}")
    return {
        "accepted": True,
        "action": "wake_android_workers",
        "summary": "\n".join(lines),
        "results": [result.to_dict() for result in results],
    }
