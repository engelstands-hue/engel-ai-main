#!/usr/bin/env python3
"""Pair CT246 with the approved Windows Sub-Engel node from a stdin payload."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_sub_node_remote_control as remote  # noqa: E402


EXPECTED_HOST = "DESKTOP-UE5A6GG"
EXPECTED_URL = "http://198.51.100.227:8776"
CONTROLLER_NAME = "Engel AI Main CT246"
MAX_STDIN_BYTES = 64 * 1024


def emit(payload: dict[str, Any]) -> int:
    payload.pop("session_token", None)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("pair_ok") and payload.get("proof_ok") else 1


def authenticated_node_status() -> tuple[dict[str, Any], dict[str, Any], bool]:
    response = remote.run_action(
        "node.status",
        node_kind="windows",
        node_id=EXPECTED_HOST,
    )
    proof = remote.decode_action_stdout(response)
    ok = bool(
        response.get("ok")
        and str(proof.get("hostname") or "") == EXPECTED_HOST
        and str(proof.get("node_root") or "").casefold()
        == r"d:\engelwindowssubnode".casefold()
        and proof.get("node_root_on_os_drive") is False
    )
    return response, proof, ok


def main() -> int:
    raw = sys.stdin.buffer.read(MAX_STDIN_BYTES + 1)
    if len(raw) > MAX_STDIN_BYTES:
        return emit({"ok": False, "pair_ok": False, "proof_ok": False, "error": "payload_too_large"})
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return emit({"ok": False, "pair_ok": False, "proof_ok": False, "error": "invalid_json"})
    if not isinstance(payload, dict):
        return emit({"ok": False, "pair_ok": False, "proof_ok": False, "error": "payload_must_be_object"})

    hostname = str(payload.get("computer_name") or "").strip()
    url = str(payload.get("url") or "").strip().rstrip("/")
    code = str(payload.get("pairing_code") or "").strip()
    if hostname != EXPECTED_HOST or url != EXPECTED_URL:
        return emit({
            "ok": False,
            "pair_ok": False,
            "proof_ok": False,
            "error": "unexpected_sub_identity",
            "expected_host": EXPECTED_HOST,
            "expected_url": EXPECTED_URL,
        })

    # --force (arg or "force": true in payload): consume the code and mint a fresh
    # session even when one already authenticates. Without it the existing session
    # is preserved and the code is left unused. pair_node commits atomically, so a
    # forced re-pair rotates the token on the node and this controller together.
    force = "--force" in sys.argv or payload.get("force") is True
    _existing_response, existing_proof, existing_ok = authenticated_node_status()
    if existing_ok and not force:
        session = remote.load_session("windows", EXPECTED_HOST)
        return emit({
            "ok": True,
            "pair_ok": True,
            "proof_ok": True,
            "status": "existing authenticated CT246 session preserved",
            "pairing_code_consumed": False,
            "hostname": EXPECTED_HOST,
            "url": EXPECTED_URL,
            "controller_name": str(
                session.get("controller_name") or CONTROLLER_NAME
            ),
            "expires_at_utc": str(session.get("expires_at_utc") or ""),
            "session_token_hint": str(session.get("session_token_hint") or ""),
            "proof_action": "node.status",
            "proof_result": existing_proof,
        })
    if not re.fullmatch(r"[A-Za-z0-9]{6,32}", code):
        return emit({"ok": False, "pair_ok": False, "proof_ok": False, "error": "invalid_pairing_code_shape"})

    pair_result = remote.pair_node(
        url,
        code,
        controller_name=CONTROLLER_NAME,
        store=True,
        node_kind="windows",
    )
    pair_ok = bool(pair_result.get("ok")) and str(pair_result.get("hostname") or "") == EXPECTED_HOST
    proof_result: dict[str, Any] = {}
    proof_ok = False
    if pair_ok:
        _response, proof_result, proof_ok = authenticated_node_status()

    return emit({
        "ok": pair_ok and proof_ok,
        "pair_ok": pair_ok,
        "proof_ok": proof_ok,
        "status": "new CT246 session paired" if pair_ok else "pairing failed",
        "pairing_code_consumed": pair_ok,
        "hostname": pair_result.get("hostname", ""),
        "url": EXPECTED_URL,
        "controller_name": CONTROLLER_NAME,
        "expires_at_utc": pair_result.get("expires_at_utc", ""),
        "session_token_hint": pair_result.get("session_token_hint", ""),
        "proof_action": "node.status",
        "proof_result": proof_result,
        "error": pair_result.get("error", ""),
    })


if __name__ == "__main__":
    raise SystemExit(main())
