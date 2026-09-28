#!/usr/bin/env python3
"""Verify durable, authenticated Sub-Engel session renewal."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_sub_node_remote_control as remote  # noqa: E402
import engel_sub_node_meeting_bridge as meeting_bridge  # noqa: E402
import engel_windows_sub_node_agent as node  # noqa: E402
from tools import watch_windows_sub_engel_pairing as watcher  # noqa: E402
from tools import engel_renew_sub_sessions as ct_renewal  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def action_response(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "result": {
            "return_code": 0,
            "stdout": json.dumps(payload),
            "stderr": "",
        },
    }


def main() -> int:
    checks: list[str] = []
    invalid_summary = meeting_bridge._summary_from_session(
        "DESKTOP-TEST",
        {
            "url": "http://192.0.2.10:8776",
            "paired": False,
            "meeting_ready": False,
            "session_invalid": True,
            "last_auth_probe_ok": False,
            "last_auth_error": "invalid bearer token",
        },
        "Windows Sub-Engel",
        "windows_sub_engel",
    )
    valid_summary = meeting_bridge._summary_from_session(
        "DESKTOP-TEST",
        {
            "url": "http://192.0.2.10:8776",
            "paired": True,
            "meeting_ready": True,
            "session_invalid": False,
            "last_auth_probe_ok": True,
        },
        "Windows Sub-Engel",
        "windows_sub_engel",
    )
    require(
        invalid_summary.get("paired") is False
        and invalid_summary.get("meeting_ready") is False
        and invalid_summary.get("live_health_ok") is False,
        "invalid authenticated session was advertised as paired",
    )
    require(
        valid_summary.get("paired") is True
        and valid_summary.get("meeting_ready") is True
        and valid_summary.get("live_health_ok") is True,
        "valid authenticated session was not advertised as paired",
    )
    checks.append("meeting summary requires valid authenticated session evidence")
    require(node.SESSION_TTL_SECONDS >= 30 * 24 * 60 * 60, "node session TTL is shorter than 30 days")
    require("session.renew" in node.ALLOWED_ACTIONS, "node allowlist omits session.renew")
    require("session.renew" in node.ACTION_HANDLERS, "node handler omits session.renew")
    require("session.renew" in remote.ALLOWED_ACTIONS, "controller allowlist omits session.renew")
    node_receipt_source = inspect.getsource(node.action_session_renew).split("return json_action", 1)[0]
    watcher_renew_source = inspect.getsource(watcher.renew_expiring_sessions)
    require("session_token_hint" not in node_receipt_source, "node renewal receipt logs token hint material")
    require("session_token_hint" not in watcher_renew_source, "watcher renewal log records token hint material")
    checks.append("node and controller expose authenticated session renewal with a 30-day default")

    with tempfile.TemporaryDirectory(prefix="engel-session-renew-") as tmp_text:
        tmp = Path(tmp_text)
        original_state_dir = node.STATE_DIR
        node.STATE_DIR = tmp / "node-state"
        try:
            node.write_json(node.session_path(), {
                "role": node.ROLE,
                "node_os": "windows",
                "session_token_hash": node.sha256_text("old-token"),
                "session_token_hint": "****oken",
                "controller_name": "Engel AI Controller",
                "created_at_utc": node.utc_stamp(),
                "expires_at_utc": node.utc_stamp(node.utc_now() + timedelta(minutes=5)),
            })
            renewal_action = node.action_session_renew()
            renewed = json.loads(str(renewal_action.get("stdout") or "{}"))
            stored = node.read_json(node.session_path())
        finally:
            node.STATE_DIR = original_state_dir

        token = str(renewed.get("session_token") or "")
        require(renewed.get("ok") is True and token, "node did not return a renewed token")
        require(stored.get("session_token_hash") == node.sha256_text(token), "node did not persist the renewed token hash")
        require(stored.get("controller_name") == "Engel AI Controller", "node changed controller identity during renewal")
        require(node.parse_utc(str(renewed.get("expires_at_utc") or "")) >= node.utc_now() + timedelta(days=29), "renewed session is too short")
        checks.append("node rotates the token, stores only its hash, preserves the controller, and extends expiry")

        original_windows_dir = remote.WINDOWS_STATE_DIR
        original_windows_session = remote.WINDOWS_SESSION_PATH
        remote.WINDOWS_STATE_DIR = tmp / "controller" / "windows_sub_engel"
        remote.WINDOWS_SESSION_PATH = remote.WINDOWS_STATE_DIR / "session.json"
        controller_session = {
            "url": "http://192.0.2.10:8776",
            "hostname": "DESKTOP-TEST",
            "controller_name": "Engel AI Controller",
            "session_token": "old-token",
            "expires_at_utc": "2026-01-01T00:00:00Z",
        }
        response = action_response(renewed)
        try:
            remote.update_session_from_action("windows", controller_session, controller_session["url"], "session.renew", response)
            active = remote.read_json(remote.WINDOWS_SESSION_PATH)
            per_node = remote.read_json(remote.node_session_path("windows", "DESKTOP-TEST"))
        finally:
            remote.WINDOWS_STATE_DIR = original_windows_dir
            remote.WINDOWS_SESSION_PATH = original_windows_session
        require(active.get("session_token") == token, "controller active session did not rotate")
        require(per_node.get("session_token") == token, "controller per-node session did not rotate")
        require(active.get("expires_at_utc") == renewed.get("expires_at_utc"), "controller did not persist renewed expiry")
        checks.append("controller atomically updates active and per-node session records")

        original_windows_dir = remote.WINDOWS_STATE_DIR
        original_windows_session = remote.WINDOWS_SESSION_PATH
        original_request_json = remote.request_json
        remote.WINDOWS_STATE_DIR = tmp / "timeout-recovery" / "windows_sub_engel"
        remote.WINDOWS_SESSION_PATH = remote.WINDOWS_STATE_DIR / "session.json"
        pair_payload: dict[str, Any] = {}

        def timeout_then_auth(
            method: str,
            url: str,
            payload: dict[str, Any] | None = None,
            token: str | None = None,
            timeout: int = remote.DEFAULT_TIMEOUT,
        ) -> dict[str, Any]:
            del timeout
            if method == "POST" and url.endswith("/pair"):
                pair_payload.update(payload or {})
                return {"ok": False, "error": "timed out"}
            if method == "GET" and url.endswith("/actions"):
                require(
                    token == pair_payload.get("proposed_session_token"),
                    "timeout recovery probed with a different bearer",
                )
                return {
                    "ok": True,
                    "allowed_actions": ["node.status", "session.renew"],
                }
            raise AssertionError(f"unexpected timeout-recovery request: {method} {url}")

        remote.request_json = timeout_then_auth
        try:
            recovered = remote.pair_node(
                "http://192.0.2.10:8776",
                "PAIR1234",
                controller_name="Engel AI Main CT246",
                store=True,
                node_kind="windows",
            )
            recovered_session = remote.read_json(remote.WINDOWS_SESSION_PATH)
        finally:
            remote.request_json = original_request_json
            remote.WINDOWS_STATE_DIR = original_windows_dir
            remote.WINDOWS_SESSION_PATH = original_windows_session

        proposed = str(pair_payload.get("proposed_session_token") or "")
        require(len(proposed) >= 32, "controller did not propose a strong session bearer")
        require(
            recovered.get("ok") is True
            and recovered.get("pair_timeout_recovered") is True,
            "controller did not recover a committed pair after response timeout",
        )
        require(
            recovered_session.get("session_token") == proposed,
            "controller did not persist its timeout-recovered bearer",
        )
        require(
            "session_token" not in recovered,
            "safe pair result exposed the session bearer",
        )
        checks.append("controller-owned bearer recovers a committed pair after response timeout")

        original_state_dir = node.STATE_DIR
        node.STATE_DIR = tmp / "idempotent-node-state"
        try:
            proposed = "A" * 43
            first = node.create_session("Engel AI Main CT246", proposed)
            valid, _reason = node.current_session_valid(proposed)
            require(
                first.get("session_token") == proposed and valid,
                "node did not accept and hash the controller-proposed bearer",
            )
            require(
                node.current_session_record_is_live(),
                "node did not recognize its persisted live session",
            )
        finally:
            node.STATE_DIR = original_state_dir
        checks.append("node persists only the proposed bearer hash and recognizes a live session")

        helper_source = (
            ROOT / "tools" / "engel_pair_windows_sub_from_stdin.py"
        ).read_text(encoding="utf-8")
        watcher_source = inspect.getsource(watcher)
        require(
            "existing authenticated CT246 session preserved" in helper_source
            and "pairing_code_consumed" in helper_source,
            "CT246 pairing helper can still rotate an authenticated session",
        )
        require(
            "session_preserving_node_ready" in watcher_source
            and "pair_attempted" in watcher_source,
            "ROG watcher does not distinguish status-only node-ready callbacks",
        )
        checks.append("CT246 helper and ROG watcher preserve an authenticated session")
        ct_renewal_source = inspect.getsource(ct_renewal.renew_sessions)
        timer_source = (
            ROOT
            / "scripts"
            / "systemd"
            / "engel-sub-session-renewal.timer"
        ).read_text(encoding="utf-8")
        require(
            'remote.run_action(' in ct_renewal_source
            and '"session.renew"' in ct_renewal_source
            and '"secret_material_reported": False' in ct_renewal_source,
            "CT246 renewal owner does not rotate sessions without reporting secrets",
        )
        require(
            "session_renewal_owner" in watcher_source
            and '"ct246"' in watcher_source
            and "rog_local_session_renewal_disabled" in watcher_source,
            "ROG server-only watcher still owns session renewal",
        )
        require(
            "OnUnitActiveSec=12h" in timer_source
            and "Persistent=true" in timer_source,
            "CT246 renewal timer is not persistent and twice daily",
        )
        checks.append("CT246 owns durable renewal while ROG server-only renewal is disabled")

        original_list = watcher.remote.list_node_sessions
        original_health = watcher.fetch_health
        original_run = watcher.remote.run_action
        original_append_log = watcher.append_log
        future = (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat().replace("+00:00", "Z")
        watcher.remote.list_node_sessions = lambda _kind: [{
            "node_id": "DESKTOP-TEST",
            "session": {"url": "http://192.0.2.10:8776", "expires_at_utc": future},
        }]
        watcher.fetch_health = lambda _url: {"ok": True, "allowed_actions": ["session.renew"]}
        watcher.remote.run_action = lambda *_args, **_kwargs: response
        watcher.append_log = lambda *_args, **_kwargs: None
        try:
            keeper_state = watcher.renew_expiring_sessions({})
        finally:
            watcher.remote.list_node_sessions = original_list
            watcher.fetch_health = original_health
            watcher.remote.run_action = original_run
            watcher.append_log = original_append_log
        require(keeper_state.get("last_session_renewed") == 1, "watcher did not renew an expiring session")
        require(not any("token" in key.lower() for key in keeper_state), "watcher persisted token material in state")
        checks.append("ROG watcher renews near-expiry sessions without persisting token material in watcher state")

        original_subprocess_run = watcher.subprocess.run
        original_remote_run = watcher.remote.run_action
        watcher.subprocess.run = lambda *args, **kwargs: (_ for _ in ()).throw(
            watcher.subprocess.TimeoutExpired(cmd=args[0] if args else "test", timeout=1)
        )
        try:
            pair_timeout = (
                watcher.run_pair({})
                if inspect.signature(watcher.run_pair).parameters
                else watcher.run_pair()
            )
            watcher.remote.run_action = lambda *_args, **_kwargs: {
                "ok": False,
                "error": "timed out",
            }
            proof_timeout = watcher.run_live_proof("DESKTOP-TEST")
        finally:
            watcher.subprocess.run = original_subprocess_run
            watcher.remote.run_action = original_remote_run
        require(pair_timeout.get("returncode") == 124 and pair_timeout.get("timed_out") is True, "pair timeout escaped watcher")
        require(
            (
                proof_timeout.get("returncode") == 1
                and proof_timeout.get("error") == "timed out"
            )
            or (
                proof_timeout.get("returncode") == 124
                and proof_timeout.get("timed_out") is True
            ),
            "live-proof failure escaped watcher",
        )
        checks.append("pair timeout and live-proof failure become receipts instead of crashing the watcher")

        cold_import = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import runpy; "
                    f"runpy.run_path({str(ROOT / 'tools' / 'watch_windows_sub_engel_pairing.py')!r}, "
                    "run_name='engel_watcher_import_test')"
                ),
            ],
            cwd=str(tmp),
            capture_output=True,
            text=True,
            timeout=15,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        require(cold_import.returncode == 0, "watcher cold-start import failed: " + cold_import.stderr[-1000:])
        checks.append("watcher imports correctly when launched outside the repository working directory")

        original_urls = watcher.health_probe_urls
        original_health = watcher.fetch_health
        original_load_session = watcher.remote.load_session
        original_live_proof = watcher.run_live_proof
        watcher.health_probe_urls = lambda: ["http://192.0.2.10:8776"]
        probe_source = inspect.getsource(watcher.probe_known_nodes_for_auto_return)
        proof_action = (
            "direct_work.execute"
            if "direct_work.execute" in probe_source
            else "shared_room.process_pending_work_orders"
        )
        watcher.fetch_health = lambda _url: {
            "ok": True,
            "hostname": "DESKTOP-TEST",
            "node_root": "D:\\EngelWindowsSubNode",
            "allowed_actions": [proof_action],
        }
        watcher.remote.load_session = lambda *_args, **_kwargs: {
            "session_token": "expired-token",
            "expires_at_utc": "2026-01-01T00:00:00Z",
        }
        watcher.run_live_proof = lambda _node: (_ for _ in ()).throw(AssertionError("expired session must not stage proof work"))
        try:
            expired_state = watcher.probe_known_nodes_for_auto_return({})
        finally:
            watcher.health_probe_urls = original_urls
            watcher.fetch_health = original_health
            watcher.remote.load_session = original_load_session
            watcher.run_live_proof = original_live_proof
        require(expired_state.get("last_health_probe_status") == "session_expired_requires_pair", "expired session was not held before proof dispatch")
        checks.append("expired sessions cannot stage Sub proof work orders before re-pairing")

    print(json.dumps({
        "ok": True,
        "schema": "engel_sub_engel_session_renewal_verifier_v1",
        "check_count": len(checks),
        "checks": checks,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
