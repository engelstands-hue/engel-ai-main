#!/usr/bin/env python3
"""Verify the Composio/Hermes source capture inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "gui_reverse_engineering_20260606"
INVENTORY = ROOT / "dist" / "ENGEL_SOURCE_CAPTURE_INVENTORY_20260607.json"

COMPOSIO_CAPTURES = [
    "composio_home.png",
    "composio_meeting_room.png",
    "composio_settings.png",
    "composio_skills.png",
]
HERMES_CAPTURES = [
    "hermes_home.png",
    "hermes_settings_hash.png",
    "hermes_route_chat.png",
    "hermes_route_settings.png",
    "hermes_route_command_center.png",
    "hermes_route_skills.png",
    "hermes_route_messaging.png",
    "hermes_route_artifacts.png",
    "hermes_route_cron.png",
    "hermes_route_profiles.png",
    "hermes_route_agents.png",
    "hermes_live_window_20260607.png",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    require(header.startswith(b"\x89PNG\r\n\x1a\n"), f"not a PNG file: {path}")
    require(header[12:16] == b"IHDR", f"PNG missing IHDR: {path}")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def capture_row(name: str, source: str) -> dict[str, object]:
    path = REPORT_DIR / name
    require(path.exists(), f"missing {source} capture: {path}")
    width, height = png_dimensions(path)
    require(width >= 200 and height >= 150, f"{source} capture too small: {name}")
    size = path.stat().st_size
    require(size > 10_000, f"{source} capture suspiciously small: {name}")
    return {
        "source": source,
        "name": name,
        "path": str(path),
        "bytes": size,
        "width": width,
        "height": height,
        "sha256": sha256_file(path),
    }


def build_inventory() -> dict[str, object]:
    rows = [
        *(capture_row(name, "composio") for name in COMPOSIO_CAPTURES),
        *(capture_row(name, "hermes") for name in HERMES_CAPTURES),
    ]
    return {
        "schema": "engel_source_capture_inventory_v1",
        "generated_at_utc": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "report_dir": str(REPORT_DIR),
        "counts": {
            "composio": len(COMPOSIO_CAPTURES),
            "hermes": len(HERMES_CAPTURES),
            "total": len(rows),
            "bytes": sum(int(row["bytes"]) for row in rows),
        },
        "captures": rows,
    }


def normalize_for_compare(data: dict[str, object]) -> dict[str, object]:
    normalized = dict(data)
    normalized.pop("generated_at_utc", None)
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write current inventory")
    args = parser.parse_args()
    current = build_inventory()

    if args.write:
        INVENTORY.parent.mkdir(parents=True, exist_ok=True)
        INVENTORY.write_text(
            json.dumps(current, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"ok": True, "wrote": str(INVENTORY), "counts": current["counts"]}, indent=2))
        return 0

    require(INVENTORY.exists(), f"capture inventory missing: {INVENTORY}")
    recorded = json.loads(INVENTORY.read_text(encoding="utf-8"))
    require(
        normalize_for_compare(recorded) == normalize_for_compare(current),
        "source capture inventory does not match current screenshot files",
    )
    print(json.dumps({"ok": True, "inventory": str(INVENTORY), "counts": recorded["counts"]}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        raise SystemExit(1)
