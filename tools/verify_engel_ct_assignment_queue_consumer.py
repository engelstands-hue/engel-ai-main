#!/usr/bin/env python3
"""Verify the CT assignment queue bridge contract and smoke path."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading


ROOT = Path(__file__).resolve().parents[1]
CONSUMER_PATH = ROOT / "tools" / "engel_ct_assignment_queue_consumer.py"
RUST_RECEIVER = ROOT / "rust" / "engel-core-rs" / "src" / "lan_receiver.rs"
TUNNEL_SCRIPT = ROOT / "scripts" / "Start-EngelMainServerChatTunnelPersistent.ps1"
INSTALLER_SCRIPT = ROOT / "scripts" / "Install-EngelCtAssignmentQueueConsumer.ps1"


def load_consumer():
    spec = importlib.util.spec_from_file_location("engel_ct_assignment_queue_consumer", CONSUMER_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load consumer module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def assert_contains(path: Path, needle: str) -> None:
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        raise AssertionError(f"{path} missing expected text: {needle}")


def valid_packet() -> dict:
    return {
        "packet_version": "1",
        "packet_id": "verify-ct-queue-bridge-001",
        "created_at": "2026-07-04T00:00:00Z",
        "created_by": "Engel Communication Router",
        "approved_by": "Engel Core",
        "approval_scope": "remote_worker_assignment_only",
        "assignment_mode": "remote_worker_auto",
        "trust_level": "untrusted_until_reviewed",
        "worker_target": "android_worker_alpha",
        "task_type": "return_status",
        "title": "Verifier queue bridge candidate",
        "instructions": "Return a short untrusted draft status only.",
        "allowed_outputs": ["draft_result_json"],
        "blocked_actions": [
            "execute_commands",
            "write_trusted_memory",
            "mutate_queue",
            "mutate_routes",
            "mutate_source",
            "control_engel",
            "auto_apply_fixes",
            "provider_call",
            "browser_task",
            "download",
            "install_package",
        ],
        "requires_review": True,
        "safe_to_auto_apply": False,
        "not_trusted_memory": True,
        "no_direct_control": True,
    }


class ImportHandler(BaseHTTPRequestHandler):
    seen_payloads: list[dict] = []

    def log_message(self, *_args):
        return

    def do_POST(self):
        if self.path != "/queue/import-assignment":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.seen_payloads.append(payload)
        body = json.dumps(
            {
                "accepted": True,
                "status": "imported_assignment",
                "approved_assignment_path": "remote_workers/communication_queen_assignments/approved/verify.json",
                "candidate_only": True,
                "requires_review": True,
                "safe_to_auto_apply": False,
                "trusted_memory_write": False,
                "auto_apply": False,
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def verify_static_contract() -> None:
    for path in (CONSUMER_PATH, RUST_RECEIVER, TUNNEL_SCRIPT, INSTALLER_SCRIPT):
        if not path.is_file():
            raise AssertionError(f"missing required file: {path}")
    assert_contains(RUST_RECEIVER, '("POST", "/queue/import-assignment")')
    assert_contains(RUST_RECEIVER, "queue_import_allowed")
    assert_contains(RUST_RECEIVER, "is_loopback")
    assert_contains(RUST_RECEIVER, "QUEUE_BRIDGE_FINAL_DECISION")
    assert_contains(RUST_RECEIVER, '"trusted_memory_write": false')
    assert_contains(RUST_RECEIVER, '"auto_apply": false')
    assert_contains(TUNNEL_SCRIPT, "QueueImportRemotePort")
    assert_contains(TUNNEL_SCRIPT, "18765")
    assert_contains(INSTALLER_SCRIPT, "engel-ct-assignment-queue-consumer.service")
    assert_contains(INSTALLER_SCRIPT, "engel-ct-assignment-queue-consumer.timer")
    assert_contains(INSTALLER_SCRIPT, "/opt/engel")


def verify_consumer_smoke() -> None:
    consumer = load_consumer()
    with tempfile.TemporaryDirectory(prefix="engel_ct_queue_verify_") as temp:
        root = Path(temp)
        approved = root / "remote_workers" / "communication_queen_assignments" / "approved"
        shipped = root / "remote_workers" / "communication_queen_assignments" / "shipped_to_rog"
        invalid = root / "remote_workers" / "communication_queen_assignments" / "invalid"
        receipts = root / "reports" / "ct_assignment_queue_consumer"
        approved.mkdir(parents=True)
        packet_path = approved / "verify.json"
        packet_path.write_text(json.dumps(valid_packet(), indent=2) + "\n", encoding="utf-8")

        server = ThreadingHTTPServer(("127.0.0.1", 0), ImportHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            config = consumer.ConsumerConfig(
                root=root,
                target_url=f"http://127.0.0.1:{server.server_port}/queue/import-assignment",
                approved_dir=approved,
                shipped_dir=shipped,
                invalid_dir=invalid,
                receipt_dir=receipts,
                timeout_seconds=3.0,
                dry_run=False,
            )
            result = consumer.consume_once(config, 10)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        if result["counts"].get("shipped") != 1:
            raise AssertionError(f"expected one shipped packet, got {result}")
        if packet_path.exists():
            raise AssertionError("approved packet was not moved after accepted import")
        if len(list(shipped.glob("*.json"))) != 1:
            raise AssertionError("shipped_to_rog does not contain the moved packet")
        receipt_files = list(receipts.glob("CT_ASSIGNMENT_QUEUE_CONSUMER_*.json"))
        if not receipt_files:
            raise AssertionError("consumer did not write a receipt")
        receipt = json.loads(receipt_files[0].read_text(encoding="utf-8"))
        if receipt.get("trusted_memory_write") is not False or receipt.get("auto_apply") is not False:
            raise AssertionError("receipt safety fields are wrong")
        if not ImportHandler.seen_payloads:
            raise AssertionError("test receiver saw no import payload")
        payload = ImportHandler.seen_payloads[-1]
        if payload.get("trusted_memory_write") is not False or payload.get("auto_apply") is not False:
            raise AssertionError("posted wrapper safety fields are wrong")


def main() -> int:
    verify_static_contract()
    verify_consumer_smoke()
    print("ENGEL_CT_ASSIGNMENT_QUEUE_CONSUMER_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
