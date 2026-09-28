#!/usr/bin/env python3
"""Google Drive for desktop shared-room fallback for Engel nodes.

This module does not use Google API credentials. It uses the local Google Drive
for desktop mount so Engel Main, Codex, and Sub-Engel nodes signed into the same
Drive account can exchange simple append-only messages.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
from typing import Any


ROOM_FOLDER_NAME = "ENGEL_SHARED_NODE_ROOM"
LIVE_DOC_NAME = "Engel_Shared_Node_Room_LIVE.md"
BUS_FILE_NAME = "engel_shared_room_bus.jsonl"
CONFIG_PATH = Path(__file__).resolve().parent / "runtime" / "google_drive_shared_room.json"


def _rust_shared_room_runtime_requested() -> bool:
    runtime = os.environ.get("ENGEL_SHARED_ROOM_RUNTIME", "").strip().lower()
    use_rust = os.environ.get("ENGEL_SHARED_ROOM_USE_RUST", "").strip().lower()
    return runtime in {"rust", "rs", "engel-ai-rs", "engel_rs"} or use_rust in {
        "1",
        "true",
        "yes",
        "on",
    }


def _rust_shared_room_strict() -> bool:
    return os.environ.get("ENGEL_SHARED_ROOM_RUST_STRICT", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _rust_shared_room_failure(action: str, exc: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "error": f"Rust shared-room {action} bridge failed ({type(exc).__name__}: {exc})",
        "runtime": "engel-ai-rs",
    }


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    for key in ("ENGEL_SHARED_ROOM_ROOT", "ENGEL_GOOGLE_DRIVE_ROOT", "GOOGLE_DRIVE_ROOT"):
        raw = os.environ.get(key)
        if raw:
            roots.append(Path(raw))
    home = Path.home()
    roots.extend([
        home / "Google Drive" / "My Drive",
        home / "My Drive",
    ])
    if os.name == "nt":
        for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
            roots.append(Path(f"{letter}:\\My Drive"))
    return roots


def find_drive_roots() -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    for root in _candidate_roots():
        try:
            resolved = root.resolve()
        except OSError:
            resolved = root
        key = str(resolved).lower()
        if key in seen:
            continue
        if root.exists() and root.is_dir():
            found.append(root)
            seen.add(key)
    return found


def room_paths(root: str | Path | None = None) -> dict[str, Path]:
    if root:
        drive_root = Path(root)
    else:
        roots = find_drive_roots()
        drive_root = roots[0] if roots else Path("")
    room_dir = drive_root / ROOM_FOLDER_NAME if str(drive_root) else Path("")
    return {
        "drive_root": drive_root,
        "room_dir": room_dir,
        "live_doc": room_dir / LIVE_DOC_NAME if str(room_dir) else Path(""),
        "bus": room_dir / BUS_FILE_NAME if str(room_dir) else Path(""),
    }


def shared_room_dir() -> Path:
    """The ENGEL_SHARED_NODE_ROOM directory on whichever drive Google Drive is
    actually mounted. Drive letters vary per machine (it is G: here, not the old
    hardcoded H:), so resolve dynamically; fall back to G: if none is found.
    (2026-07-07: replaces scattered hardcoded H:\\My Drive defaults that made the
    Sub-Engel dispatch prover false-alarm with FileNotFoundError.)"""
    roots = find_drive_roots()
    base = roots[0] if roots else Path("G:\\My Drive")
    return base / ROOM_FOLDER_NAME


def initial_live_doc() -> str:
    return "\n".join([
        "# Engel Shared Node Room",
        "",
        f"Created UTC: {utc_stamp()}",
        "Owner account: redacted@example.com",
        "Transport: Google Drive for desktop synced folder",
        "",
        "## Protocol",
        "",
        "1. Engel Main appends INPUT messages.",
        "2. A node appends CLAIM when it starts work.",
        "3. The node appends RESULT with evidence or BLOCKER.",
        "4. Engel Main reads the result and saves it back into the main chat/meeting room.",
        "",
        "## Live Messages",
        "",
    ])


def init_room(
    root: str | Path | None = None,
    google_doc_url: str = "",
    connector_status: str = "",
) -> dict[str, Any]:
    if _rust_shared_room_runtime_requested():
        try:
            from engel_rust_shared_room_bridge import init_room_via_rust

            rust_result = init_room_via_rust(root, google_doc_url, connector_status)
            if rust_result.get("ok") or _rust_shared_room_strict():
                return rust_result
        except Exception as exc:
            if _rust_shared_room_strict():
                return _rust_shared_room_failure("init", exc)
    paths = room_paths(root)
    drive_root = paths["drive_root"]
    if not str(drive_root) or not drive_root.exists():
        return {
            "ok": False,
            "error": "Google Drive for desktop My Drive folder was not found",
            "checked_roots": [str(p) for p in _candidate_roots()],
        }
    room_dir = paths["room_dir"]
    room_dir.mkdir(parents=True, exist_ok=True)
    live_doc = paths["live_doc"]
    bus = paths["bus"]
    if not live_doc.exists():
        live_doc.write_text(initial_live_doc(), encoding="utf-8")
    if not bus.exists():
        bus.write_text("", encoding="utf-8")
    config = {
        "updated_at_utc": utc_stamp(),
        "drive_root": str(drive_root),
        "room_dir": str(room_dir),
        "live_doc": str(live_doc),
        "bus": str(bus),
        "google_doc_url": google_doc_url,
        "connector_status": connector_status,
        "transport": "google_drive_for_desktop_synced_folder",
    }
    write_json(CONFIG_PATH, config)
    return {"ok": True, **config}


def append_message(
    sender: str,
    message: str,
    channel: str = "input",
    root: str | Path | None = None,
) -> dict[str, Any]:
    if _rust_shared_room_runtime_requested():
        try:
            from engel_rust_shared_room_bridge import append_message_via_rust

            rust_result = append_message_via_rust(sender, message, channel, root)
            if rust_result.get("ok") or _rust_shared_room_strict():
                return rust_result
        except Exception as exc:
            if _rust_shared_room_strict():
                return _rust_shared_room_failure("append", exc)
    room = init_room(root)
    if not room.get("ok"):
        return room
    timestamp = utc_stamp()
    record = {
        "timestamp_utc": timestamp,
        "sender": sender or socket.gethostname(),
        "channel": channel or "input",
        "message": message or "",
    }
    bus = Path(str(room["bus"]))
    with bus.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    live_doc = Path(str(room["live_doc"]))
    block = "\n".join([
        f"### {timestamp} - {record['channel']} - {record['sender']}",
        "",
        record["message"].rstrip(),
        "",
    ])
    with live_doc.open("a", encoding="utf-8") as fh:
        fh.write(block)
    return {"ok": True, "record": record, "live_doc": str(live_doc), "bus": str(bus)}


def status(root: str | Path | None = None) -> dict[str, Any]:
    if _rust_shared_room_runtime_requested():
        try:
            from engel_rust_shared_room_bridge import status_via_rust

            rust_result = status_via_rust(root)
            if rust_result.get("ok") or _rust_shared_room_strict():
                return rust_result
        except Exception as exc:
            if _rust_shared_room_strict():
                return _rust_shared_room_failure("status", exc)
    config = read_json(CONFIG_PATH)
    paths = room_paths(root or config.get("drive_root") or None)
    drive_root = paths["drive_root"]
    live_doc = paths["live_doc"]
    bus = paths["bus"]
    roots = find_drive_roots()
    latest_message = ""
    message_count = 0
    if bus.exists():
        try:
            lines = bus.read_text(encoding="utf-8").splitlines()
            message_count = len([line for line in lines if line.strip()])
            latest_message = lines[-1] if lines else ""
        except OSError:
            latest_message = ""
    return {
        "ok": bool(str(drive_root) and drive_root.exists()),
        "drive_roots": [str(p) for p in roots],
        "drive_root": str(drive_root),
        "room_dir": str(paths["room_dir"]),
        "room_exists": paths["room_dir"].exists(),
        "live_doc": str(live_doc),
        "live_doc_exists": live_doc.exists(),
        "bus": str(bus),
        "bus_exists": bus.exists(),
        "message_count": message_count,
        "latest_message": latest_message,
        "google_doc_url": str(config.get("google_doc_url") or ""),
        "connector_status": str(config.get("connector_status") or ""),
        "updated_at_utc": utc_stamp(),
    }


def print_json(data: dict[str, Any]) -> int:
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0 if data.get("ok", True) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel shared Google Drive room helper")
    sub = parser.add_subparsers(dest="command", required=True)
    init_parser = sub.add_parser("init")
    init_parser.add_argument("--root", default="")
    init_parser.add_argument("--google-doc-url", default="")
    init_parser.add_argument("--connector-status", default="")
    append_parser = sub.add_parser("append")
    append_parser.add_argument("--root", default="")
    append_parser.add_argument("--sender", default=socket.gethostname())
    append_parser.add_argument("--channel", default="input")
    append_parser.add_argument("--message", required=True)
    status_parser = sub.add_parser("status")
    status_parser.add_argument("--root", default="")
    args = parser.parse_args(argv)
    if args.command == "init":
        return print_json(init_room(args.root or None, args.google_doc_url, args.connector_status))
    if args.command == "append":
        return print_json(append_message(args.sender, args.message, args.channel, args.root or None))
    if args.command == "status":
        return print_json(status(args.root or None))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
