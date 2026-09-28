#!/usr/bin/env python3
"""Read-only Engel OS bridge for Engel AI / Agent Meeting Room.

The bridge makes the Engel OS workspace legible to Engel AI without starting
remote control, flashing media, installing packages, or touching disks. It
only inspects D:-local project files and stages a report under Engel App
runtime state.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ENGEL_APP_ROOT = Path(__file__).resolve().parent
DEFAULT_ENGEL_OS_ROOT = Path("D:/Engel OS")
RUNTIME_DIR = ENGEL_APP_ROOT / "runtime" / "meeting_room" / "engel_os"
REPORTS_DIR = ENGEL_APP_ROOT / "reports" / "meeting_rooms"
STATUS_PATH = RUNTIME_DIR / "engel_os_bridge_status.json"

BRIDGE_NAME = "Engel OS Bridge (read-only)"
BRIDGE_VERSION = "ENGEL_OS_BRIDGE_V1"

DOC_PATHS = {
    "handoff": "HANDOFF.md",
    "readme": "README.md",
    "ready_to_flash": "READY_TO_FLASH.md",
    "technical_plan": "ENGEL_OS_TECHNICAL_PLAN.md",
    "usb_flashing_guide": "docs/ENGEL_OS_USB_FLASHING_GUIDE.md",
    "sub_node_handoff": "reports/codex_bridge/HANDOFF_TO_ENGEL_AI_SUB_ENGEL_NODE.md",
    "packet_016_remote_control": "reports/codex_bridge/PACKET_016_SUB_ENGEL_REMOTE_CONTROL.md",
}

STAGING_FILES = {
    "iso": "releases/staging/engel-os-sub-node-live.iso",
    "sha256": "releases/staging/engel-os-sub-node-live.iso.sha256",
    "manifest": "releases/staging/engel-os-sub-node-live.manifest.json",
    "build_summary": "releases/staging/engel-os-sub-node-live.build-summary.json",
    "build_log": "releases/staging/engel-os-sub-node-live.build.log",
}

SAFETY_GATES = {
    "read_only_bridge": True,
    "usb_flash_requires_user_tool_choice": True,
    "disk_install_requires_local_approval_phrase": True,
    "remote_control_pair_gated": True,
    "remote_control_allowlist_only": True,
    "no_ssh": True,
    "no_raw_shell": True,
    "no_remote_install_format_partition": True,
    "no_provider_runtime_started": True,
    "no_model_runtime_started": True,
    "no_background_workers_started": True,
    "no_secrets_or_pairing_codes_recorded": True,
}

BLOCKED_BEHAVIOR = (
    "SSH",
    "raw shell or arbitrary command execution",
    "remote disk install, partition, format, erase, or flashing",
    "remote package install",
    "provider/API runtime startup",
    "model runtime startup",
    "background worker startup",
    "secret, Wi-Fi credential, pairing-code, or session-token capture",
)

REMOTE_ALLOWED_ACTIONS = (
    "node.status",
    "node.hardware",
    "node.safety",
    "node.controller",
    "net.status",
    "net.diagnose",
    "net.firmware",
    "install.status",
    "install.preflight",
    "install.list_disks",
    "ui.dashboard",
    "remote.status",
)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path, limit: int = 250_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _file_info(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": str(path)}
    stat = path.stat()
    return {
        "exists": True,
        "path": str(path),
        "size_bytes": stat.st_size,
        "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }


def _doc_markers(name: str, text: str) -> tuple[str, ...]:
    low = text.lower()
    marker_map: dict[str, tuple[str, ...]] = {
        "handoff": ("sub-engel os worker", "packet 016", "cluster role", "no ssh"),
        "readme": ("sub-engel os worker", "cluster pairing", "safety boundaries", "ssh server is not enabled"),
        "ready_to_flash": ("verify the iso", "identify the usb drive", "safe mode", "sub-engel os worker"),
        "technical_plan": ("sub-engel", "cluster", "approval gate", "safe mode"),
        "usb_flashing_guide": ("destructive", "sha256", "safe mode", "do not"),
        "sub_node_handoff": ("sub-engel cluster node", "engel_sub_node_remote_control.py", "allowed remote actions", "blocked behavior"),
        "packet_016_remote_control": ("allowlist", "pairing", "raw shell", "remote disk install"),
    }
    return tuple(marker for marker in marker_map.get(name, ()) if marker in low)


def _parse_expected_sha(path: Path) -> str:
    text = read_text(path, limit=2000).strip()
    if not text:
        return ""
    return text.split()[0].strip().lower()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _review_docs(root: Path) -> dict[str, dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}
    for name, rel in DOC_PATHS.items():
        path = root / rel
        text = read_text(path)
        docs[name] = {
            **_file_info(path),
            "markers_found": list(_doc_markers(name, text)),
        }
    return docs


def _review_iso(root: Path, compute_hash: bool = True) -> dict[str, Any]:
    paths = {name: root / rel for name, rel in STAGING_FILES.items()}
    expected = _parse_expected_sha(paths["sha256"])
    iso_info = _file_info(paths["iso"])
    build_summary = read_json(paths["build_summary"])
    actual = ""
    if compute_hash and paths["iso"].is_file():
        actual = _sha256(paths["iso"]).lower()
    return {
        "iso": iso_info,
        "sha256_file": _file_info(paths["sha256"]),
        "manifest": _file_info(paths["manifest"]),
        "build_summary_file": _file_info(paths["build_summary"]),
        "build_log": _file_info(paths["build_log"]),
        "expected_sha256": expected,
        "actual_sha256": actual,
        "sha256_verified": bool(expected and actual and expected == actual),
        "build_summary": {
            "packet": build_summary.get("packet", ""),
            "role": build_summary.get("role", ""),
            "build_exit_code": build_summary.get("build_exit_code", ""),
            "usb_flashed": bool(build_summary.get("usb_flashed", False)),
            "host_disk_mutation": bool(build_summary.get("host_disk_mutation", False)),
            "remote_control": build_summary.get("remote_control", ""),
            "install_workflow": build_summary.get("install_workflow", ""),
            "iso_size_bytes": build_summary.get("iso_size_bytes", iso_info.get("size_bytes", 0)),
        },
    }


def _remote_session_summary() -> dict[str, Any]:
    try:
        import engel_sub_node_remote_control as remote

        linux = remote.load_session("linux")
        windows = remote.load_session("windows")
    except Exception:
        linux = {}
        windows = {}

    def summarize(session: dict[str, Any]) -> dict[str, Any]:
        return {
            "paired": bool(session),
            "url": session.get("url", ""),
            "role": session.get("role", ""),
            "node_kind": session.get("node_kind", ""),
            "connection_family": session.get("connection_family", ""),
            "allowed_actions": session.get("allowed_actions", []),
            "paired_at_utc": session.get("paired_at_utc", ""),
            "expires_at_utc": session.get("expires_at_utc", ""),
            "token_recorded_in_report": False,
        }

    return {
        "linux_sub_engel": summarize(linux),
        "windows_sub_engel": summarize(windows),
        "controller_listener_started": False,
        "remote_call_performed": False,
    }


def review_engel_os_project(root: str | Path = DEFAULT_ENGEL_OS_ROOT, compute_hash: bool = True) -> dict[str, Any]:
    """Return current Engel OS hook-up status without mutating Engel OS."""
    os_root = Path(root)
    docs = _review_docs(os_root)
    iso = _review_iso(os_root, compute_hash=compute_hash)
    missing_docs = [name for name, data in docs.items() if not data.get("exists")]
    weak_docs = [name for name, data in docs.items() if data.get("exists") and not data.get("markers_found")]
    ok = (
        os_root.exists()
        and not missing_docs
        and bool(iso.get("iso", {}).get("exists"))
        and bool(iso.get("sha256_file", {}).get("exists"))
        and bool(iso.get("sha256_verified"))
    )
    return {
        "ok": ok,
        "bridge": BRIDGE_NAME,
        "bridge_version": BRIDGE_VERSION,
        "reviewed_at_utc": utc_stamp(),
        "engel_os_root": str(os_root),
        "documents": docs,
        "missing_documents": missing_docs,
        "documents_without_expected_markers": weak_docs,
        "iso": iso,
        "remote_control": {
            "allowed_actions": list(REMOTE_ALLOWED_ACTIONS),
            "blocked_behavior": list(BLOCKED_BEHAVIOR),
            "session_state": _remote_session_summary(),
        },
        "safety_gates": dict(SAFETY_GATES),
        "engelflow": {
            "meeting_room_skill": "Engel OS Bridge Skill",
            "meeting_room_agent": "Engel OS Bridge Agent",
            "sub_node_skill": "Sub-Engel Worker Skill",
            "verifier_skill": "Verification Skill",
            "safety_skill": "Safety Review Skill",
            "default_bridge": BRIDGE_NAME,
        },
    }


def _write_report(result: dict[str, Any], prompt: str, source: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = REPORTS_DIR / f"ENGEL_OS_BRIDGE_HOOKUP_{stamp}.md"
    iso = result.get("iso", {})
    summary = iso.get("build_summary", {}) if isinstance(iso, dict) else {}
    remote = result.get("remote_control", {})
    linux = ((remote.get("session_state") or {}).get("linux_sub_engel") or {}) if isinstance(remote, dict) else {}
    lines = [
        "# Engel OS Bridge Hookup Report",
        "",
        f"Created UTC: {utc_stamp()}",
        f"Source: {source}",
        f"Prompt: {prompt}",
        "",
        "## Current Hook",
        "",
        f"- Bridge: {result.get('bridge')}",
        f"- Engel OS root: {result.get('engel_os_root')}",
        f"- Meeting Room agent: {result.get('engelflow', {}).get('meeting_room_agent')}",
        f"- Meeting Room skill: {result.get('engelflow', {}).get('meeting_room_skill')}",
        "",
        "## ISO",
        "",
        f"- ISO path: {((iso.get('iso') or {}).get('path') if isinstance(iso, dict) else '')}",
        f"- ISO size bytes: {summary.get('iso_size_bytes', (iso.get('iso') or {}).get('size_bytes') if isinstance(iso, dict) else '')}",
        f"- Expected SHA256: {iso.get('expected_sha256', '') if isinstance(iso, dict) else ''}",
        f"- Actual SHA256: {iso.get('actual_sha256', '') if isinstance(iso, dict) else ''}",
        f"- SHA256 verified: {iso.get('sha256_verified', False) if isinstance(iso, dict) else False}",
        f"- Build packet: {summary.get('packet', '')}",
        f"- Build exit code: {summary.get('build_exit_code', '')}",
        f"- USB flashed by bridge: {summary.get('usb_flashed', False)}",
        f"- Host disk mutation: {summary.get('host_disk_mutation', False)}",
        "",
        "## Remote Control Status",
        "",
        f"- Linux Sub-Engel paired session stored: {linux.get('paired', False)}",
        f"- Node URL: {linux.get('url') or 'not paired'}",
        "- Remote control is pair-gated and allowlisted only.",
        "- No remote action was run by this bridge.",
        "",
        "Allowed remote actions:",
        "",
        *[f"- `{action}`" for action in REMOTE_ALLOWED_ACTIONS],
        "",
        "Blocked by design:",
        "",
        *[f"- {item}" for item in BLOCKED_BEHAVIOR],
        "",
        "## Safety Gates",
        "",
        *[f"- {key}: {value}" for key, value in sorted((result.get('safety_gates') or {}).items())],
        "",
        "## Document Review",
        "",
    ]
    for name, data in (result.get("documents") or {}).items():
        markers = ", ".join(data.get("markers_found") or []) or "none"
        lines.append(f"- {name}: exists={data.get('exists')} markers={markers}")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def stage_engel_os_hookup_packet(prompt: str, source: str = "Agent Meeting Room") -> dict[str, Any]:
    """Inspect Engel OS and stage a read-only bridge report."""
    result = review_engel_os_project(compute_hash=True)
    report_path = _write_report(result, prompt, source)
    payload = {
        **result,
        "prompt": str(prompt or ""),
        "source": source,
        "report_path": str(report_path),
        "status_path": str(STATUS_PATH),
    }
    write_json(STATUS_PATH, payload)
    return payload


def summarize_engel_os_bridge_result(result: dict[str, Any]) -> str:
    iso = result.get("iso") or {}
    summary = iso.get("build_summary") or {}
    remote = result.get("remote_control") or {}
    session_state = remote.get("session_state") or {}
    linux = session_state.get("linux_sub_engel") or {}
    return "\n".join([
        "Engel OS bridge checked D:\\Engel OS and staged a read-only hookup report.",
        f"ISO: {((iso.get('iso') or {}).get('path') or 'missing')}",
        f"SHA256 verified: {bool(iso.get('sha256_verified'))}",
        f"Build packet: {summary.get('packet', 'unknown')} | role: {summary.get('role', 'unknown')}",
        f"Sub-Engel paired session: {bool(linux.get('paired'))} ({linux.get('url') or 'not paired'})",
        f"Report: {result.get('report_path')}",
        "Blocked: SSH, raw shell, remote install/format/partition/flash, provider/model runtime, and background workers.",
    ])


def render_engel_os_bridge_status() -> str:
    if STATUS_PATH.is_file():
        status = read_json(STATUS_PATH)
    else:
        status = review_engel_os_project(compute_hash=False)
    return summarize_engel_os_bridge_result(status)


def main() -> int:
    result = stage_engel_os_hookup_packet("Manual Engel OS bridge status check.", source="CLI")
    print(summarize_engel_os_bridge_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
