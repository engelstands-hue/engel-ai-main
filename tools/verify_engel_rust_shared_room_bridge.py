#!/usr/bin/env python3
"""Verify Python shared Drive room helper through the Rust bridge."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
VERIFY_ROOT = ROOT / "runtime" / "rust_shared_room_bridge_verifier"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_inside(path: Path, root: Path) -> None:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    path_text = str(resolved_path).removeprefix("\\\\?\\").lower()
    root_text = str(resolved_root).removeprefix("\\\\?\\").lower().rstrip("\\/")
    require(
        path_text == root_text
        or path_text.startswith(root_text + "\\")
        or path_text.startswith(root_text + "/"),
        f"{resolved_path} escaped {resolved_root}",
    )


def main() -> int:
    sys.path.insert(0, str(ROOT))
    if VERIFY_ROOT.exists():
        shutil.rmtree(VERIFY_ROOT)
    VERIFY_ROOT.mkdir(parents=True, exist_ok=True)

    old_runtime = os.environ.get("ENGEL_SHARED_ROOM_RUNTIME")
    old_strict = os.environ.get("ENGEL_SHARED_ROOM_RUST_STRICT")
    os.environ["ENGEL_SHARED_ROOM_RUNTIME"] = "rust"
    os.environ["ENGEL_SHARED_ROOM_RUST_STRICT"] = "1"
    try:
        import engel_shared_drive_room as room
        from engel_rust_shared_room_bridge import tail_via_rust

        initialized = room.init_room(
            VERIFY_ROOT,
            google_doc_url="https://docs.example/engel-shared-room",
            connector_status="verifier connector ok",
        )
        require(initialized.get("ok") is True, f"init failed: {initialized}")
        require(initialized.get("runtime") == "engel-ai-rs", f"init not Rust-backed: {initialized}")
        require(
            initialized.get("google_doc_url") == "https://docs.example/engel-shared-room",
            f"init lost google_doc_url: {initialized}",
        )
        require(
            initialized.get("connector_status") == "verifier connector ok",
            f"init lost connector_status: {initialized}",
        )

        appended = room.append_message(
            sender="Rust Shared Room Bridge Verifier",
            channel="RUST_SHARED_ROOM_BRIDGE_VERIFY",
            message="hello from the Rust shared-room bridge verifier",
            root=VERIFY_ROOT,
        )
        require(appended.get("ok") is True, f"append failed: {appended}")
        require(appended.get("runtime") == "engel-ai-rs", f"append not Rust-backed: {appended}")
        bus = Path(str(appended.get("bus") or ""))
        live_doc = Path(str(appended.get("live_doc") or ""))
        assert_inside(bus, VERIFY_ROOT)
        assert_inside(live_doc, VERIFY_ROOT)
        require(bus.is_file(), f"bus missing: {bus}")
        require(live_doc.is_file(), f"live doc missing: {live_doc}")

        status = room.status(VERIFY_ROOT)
        require(status.get("ok") is True, f"status failed: {status}")
        require(status.get("runtime") == "engel-ai-rs", f"status not Rust-backed: {status}")
        require(status.get("room_exists") is True, f"room missing in status: {status}")
        require(status.get("bus_exists") is True, f"bus missing in status: {status}")
        require(status.get("live_doc_exists") is True, f"live doc missing in status: {status}")
        require(int(status.get("message_count") or 0) == 1, f"bad message_count: {status}")
        require(
            "hello from the Rust shared-room bridge verifier" in str(status.get("latest_message") or ""),
            f"latest message mismatch: {status}",
        )

        tail = tail_via_rust(VERIFY_ROOT, limit=5, channel="RUST_SHARED_ROOM_BRIDGE_VERIFY")
        require(tail.get("ok") is True, f"tail failed: {tail}")
        require(tail.get("runtime") == "engel-ai-rs", f"tail not Rust-backed: {tail}")
        require(int(tail.get("returned_messages") or 0) == 1, f"tail wrong count: {tail}")
        messages = tail.get("messages")
        require(isinstance(messages, list) and messages, f"tail missing messages: {tail}")
        require(
            messages[0].get("message") == "hello from the Rust shared-room bridge verifier",
            f"tail message mismatch: {tail}",
        )

        payload = {
            "ok": True,
            "runtime": "engel-ai-rs",
            "verification": "python shared Drive room Rust bridge",
            "mutates_live_drive_room": False,
            "verify_root": str(VERIFY_ROOT),
            "room_dir": status.get("room_dir"),
            "bus": str(bus),
            "live_doc": str(live_doc),
            "message_count": status.get("message_count"),
            "returned_messages": tail.get("returned_messages"),
            "google_doc_url": initialized.get("google_doc_url"),
            "connector_status": initialized.get("connector_status"),
        }
        print(json.dumps(payload, indent=2))
        return 0
    finally:
        if old_runtime is None:
            os.environ.pop("ENGEL_SHARED_ROOM_RUNTIME", None)
        else:
            os.environ["ENGEL_SHARED_ROOM_RUNTIME"] = old_runtime
        if old_strict is None:
            os.environ.pop("ENGEL_SHARED_ROOM_RUST_STRICT", None)
        else:
            os.environ["ENGEL_SHARED_ROOM_RUST_STRICT"] = old_strict
        if VERIFY_ROOT.exists():
            shutil.rmtree(VERIFY_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
