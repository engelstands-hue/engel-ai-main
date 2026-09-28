#!/usr/bin/env python3
"""Verify the ROG-to-CT246 phone claim/return relay contract."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
RUST_SOURCE = ROOT / "rust" / "engel-core-rs" / "src" / "lan_receiver.rs"
TEMP_ROOT = ROOT / "runtime" / "test_temp"
for entry in (ROOT, TOOLS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import run_engel_ui_chat_meeting_room_llm as chat_wrapper  # noqa: E402


class FixtureResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FixtureResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return self.body


def phone_result(packet_id: str, worker_id: str, worker_device: str) -> dict[str, Any]:
    return {
        "result_version": "1",
        "packet_id": packet_id,
        "worker_id": worker_id,
        "worker_device": worker_device,
        "trust_level": "untrusted_until_engel_review",
        "result_type": "draft_notes",
        "draft_text": "Fixture result.",
        "requires_review": True,
        "trusted_memory_write": False,
        "auto_apply": False,
        "safe_to_auto_apply": False,
    }


def phone_claim(packet_id: str, worker_id: str, worker_device: str) -> dict[str, Any]:
    return {
        "timestamp_utc": "2026-07-28T19:10:00Z",
        "packet_id": packet_id,
        "worker_id": worker_id,
        "worker_device": worker_device,
        "claim_type": "append_only_protocol_record",
        "claim_mode": "untrusted_assignment_claim",
        "trust_level": "untrusted_assignment_record",
        "direct_control": False,
        "trusted_memory_write": False,
        "auto_apply": False,
        "safe_to_auto_apply": False,
        "runtime": "engel-ai-rs",
    }


def require(condition: bool, message: str, checks: list[str]) -> None:
    if not condition:
        raise AssertionError(message)
    checks.append(message)


def main() -> int:
    checks: list[str] = []
    rust_text = RUST_SOURCE.read_text(encoding="utf-8")
    require(
        "matching_claim(&root, &result)" in rust_text
        and '"claim": claim' in rust_text
        and '"claim_receipt_path": claim_receipt_path' in rust_text,
        "ROG relay returns the authoritative matching claim with each result",
        checks,
    )
    require(
        "returned-result lookup is loopback-only" in rust_text,
        "ROG claim/return lookup remains loopback-only",
        checks,
    )

    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    original_claimed = chat_wrapper.PHONE_CLAIMED_DIR
    original_returned = chat_wrapper.PHONE_RETURNED_DIR
    original_url = chat_wrapper.PHONE_RETURN_RELAY_URL
    original_urlopen = chat_wrapper.urllib.request.urlopen
    try:
        with tempfile.TemporaryDirectory(
            prefix="phone_claim_return_relay_",
            dir=TEMP_ROOT,
        ) as temp:
            temp_path = Path(temp)
            chat_wrapper.PHONE_CLAIMED_DIR = temp_path / "claimed"
            chat_wrapper.PHONE_RETURNED_DIR = temp_path / "returned"
            chat_wrapper.PHONE_RETURN_RELAY_URL = (
                "http://127.0.0.1:18765/queue/returned-result"
            )
            packet_id = "fixture-packet-001"
            worker_id = "android_worker_alpha"
            worker_device = "engel_remote_worker_flutter"
            result = phone_result(packet_id, worker_id, worker_device)
            claim = phone_claim(packet_id, worker_id, worker_device)
            relay_calls = 0

            def valid_urlopen(_url: str, timeout: float) -> FixtureResponse:
                nonlocal relay_calls
                relay_calls += 1
                require(timeout == 2.5, "relay lookup keeps a bounded timeout", checks)
                return FixtureResponse(
                    {
                        "ok": True,
                        "status": "returned_result",
                        "result": result,
                        "claim": claim,
                        "candidate_only": True,
                        "trusted_memory_write": False,
                        "auto_apply": False,
                    }
                )

            chat_wrapper.urllib.request.urlopen = valid_urlopen
            relayed = chat_wrapper._phone_result_for_packet(packet_id, worker_id)
            require(relayed is not None, "valid phone claim/return pair is accepted", checks)
            claim_path = Path(str(relayed["claim_path"]))
            result_path = Path(str(relayed["path"]))
            require(
                claim_path.is_file() and result_path.is_file(),
                "CT intake persists independent claim and return records",
                checks,
            )
            require(
                json.loads(claim_path.read_text(encoding="utf-8")) == claim
                and json.loads(result_path.read_text(encoding="utf-8")) == result,
                "persisted claim and return records preserve the authoritative payloads",
                checks,
            )

            def forbidden_urlopen(_url: str, timeout: float) -> FixtureResponse:
                raise AssertionError(f"cached pair unexpectedly queried relay at timeout={timeout}")

            chat_wrapper.urllib.request.urlopen = forbidden_urlopen
            cached = chat_wrapper._phone_result_for_packet(packet_id, worker_id)
            require(
                cached is not None and relay_calls == 1,
                "complete local claim/return pairs are reused without another relay call",
                checks,
            )

            bad_packet = "fixture-packet-002"
            bad_result = phone_result(bad_packet, worker_id, worker_device)
            bad_claim = phone_claim(bad_packet, worker_id, "different-device")
            chat_wrapper.urllib.request.urlopen = lambda _url, timeout: FixtureResponse(
                {"ok": True, "result": bad_result, "claim": bad_claim}
            )
            rejected = chat_wrapper._phone_result_for_packet(bad_packet, worker_id)
            require(
                rejected is None,
                "mismatched phone claim/return identity is rejected",
                checks,
            )
            require(
                not any(bad_packet in path.read_text(encoding="utf-8") for path in temp_path.rglob("*.json")),
                "rejected phone evidence is not persisted",
                checks,
            )
    finally:
        chat_wrapper.PHONE_CLAIMED_DIR = original_claimed
        chat_wrapper.PHONE_RETURNED_DIR = original_returned
        chat_wrapper.PHONE_RETURN_RELAY_URL = original_url
        chat_wrapper.urllib.request.urlopen = original_urlopen

    print(
        json.dumps(
            {
                "ok": True,
                "schema": "engel_phone_claim_return_relay_verifier_v1",
                "checks_passed": len(checks),
                "checks": checks,
                "source_mutation_performed": False,
                "trusted_memory_write": False,
                "provider_used": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
