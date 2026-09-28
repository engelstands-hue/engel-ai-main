#!/usr/bin/env python3
"""Verify Engel UI local system actions stay bounded and project-rooted."""
from __future__ import annotations

import py_compile
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_project_roots() -> None:
    import engel_adb_worker_manager as adb_mgr
    import engel_phone_wake_manager as wake_mgr
    import engel_remote_worker_lan_pairing as lan
    import engel_remote_worker_link_manager as link_mgr

    require(adb_mgr._APP_ROOT == ROOT, "ADB worker manager must resolve real Engel App root")
    require(wake_mgr.ROOT == ROOT, "phone wake manager must resolve real Engel App root")
    require(lan.PROJECT_ROOT == ROOT, "LAN pairing must resolve real Engel App root")
    require(link_mgr.PROJECT_ROOT == ROOT, "link manager must resolve real Engel App root")
    for path in (lan.PAIRING_ROOT, lan.REPORT_DIR, lan.ASSIGNMENT_ROOT, link_mgr.RUNTIME_ROOT):
        require(ROOT in path.parents, f"path escaped Engel root: {path}")


def verify_system_actions_with_mocks() -> None:
    import engel_adb_worker_manager as adb_mgr
    import engel_phone_wake_manager as wake_mgr
    import engel_remote_worker_link_manager as link_mgr
    import engel_ui_system_actions as actions

    require(actions.classify_ui_system_action("Pair android workers") == "connect_android_workers", "pair command not detected")
    require(actions.classify_ui_system_action("Pair phones they are connected to usb") == "connect_android_workers", "plain phone USB pair command not detected")
    require(actions.classify_ui_system_action("give me pairing code for wifi") == "show_lan_pairing_code", "plain WiFi pairing-code request not detected")
    require(actions.classify_ui_system_action("use usb connection to wake") == "wake_android_workers", "wake command not detected")
    require(
        actions.classify_ui_system_action(
            "Help me write clearer app wording for offline phone warnings and not-paired messages."
        ) == "",
        "language prompt about not-paired messages must not become a pairing command",
    )
    require(
        actions.classify_ui_system_action(
            "Help me write clearer app wording for ninth-wave future-device run that keeps Alpha and Beta behavior clear: offline phone warnings and not-paired messages."
        ) == "",
        "full LANG_483 prompt must not become a pairing command",
    )
    require(
        actions.classify_ui_system_action(
            "Help with app wording for waking phones and pairing them."
        ) == "",
        "language prompt about waking/pairing labels must not become a wake command",
    )

    old_ip = adb_mgr._pc_lan_ip
    old_pair = adb_mgr.render_adb_workers_lan_auto_pair
    old_link_status = link_mgr.link_status
    old_start = link_mgr.start_link
    old_ensure = getattr(link_mgr, "ensure_receiver_running", None)
    old_rotate = link_mgr.rotate_token
    old_ensure_token = getattr(link_mgr, "ensure_session_token", None)
    old_wake = wake_mgr.wake_all_stale
    try:
        adb_mgr._pc_lan_ip = lambda: "192.0.2.40"
        adb_mgr.render_adb_workers_lan_auto_pair = lambda payload: "\n".join([
            "# Engel ADB LAN Auto Pair",
            "- PASS Moto G Power 2025 (8GB) `android_worker_alpha` launched=True",
            "- PASS Moto G Fast (3GB) `android_worker_beta` launched=True",
        ])
        state = {"receiver_running": False, "host": "", "pairing_token_hint": None}

        def fake_link_status():
            return dict(state)

        def fake_start_link(host, port, allow_lan):
            state.update({"receiver_running": True, "host": host, "port": port, "allow_lan": allow_lan})
            return dict(state)

        link_mgr.link_status = fake_link_status
        link_mgr.start_link = fake_start_link
        link_mgr.ensure_receiver_running = fake_start_link
        # rotate_token() = force-rotate flow used by connect_android_workers
        link_mgr.rotate_token = lambda: {
            "pairing_code": "FORCED42",
            "pairing_token_hint": "******42",
            "expires_at_utc": "2026-05-28T08:00:00Z",
            "rotated": True,
        }
        # ensure_session_token() = reuse-if-valid flow used by show_lan_pairing_code.
        # Default mock: returns an EXISTING (not-rotated) session so phones already
        # paired keep working when the operator asks to see the code.
        link_mgr.ensure_session_token = lambda: {
            "pairing_code": "SECRET42",
            "pairing_token_hint": "******42",
            "expires_at_utc": "2026-05-28T08:00:00Z",
            "rotated": False,
        }
        result = actions.run_ui_system_action("give me pairing code for wifi")
        require(result.get("accepted") is True, "pairing-code action was not accepted")
        summary = str(result.get("summary") or "")
        require("Pairing code: SECRET42" in summary, "pairing-code action did not show the code")
        # 8-hour reuse promise: if the session was still valid, show-code must NOT
        # invalidate the phone that was already paired.
        require("existing active session (not invalidated)" in summary,
                "show-code path force-rotated when session was still valid (would drop paired phones)")
        require("FORCED42" not in summary,
                "show-code path called rotate_token (would force-rotate the session)")

        result = actions.run_ui_system_action("usb is connected pair Android worker")
        require(result.get("accepted") is True, "connect action was not accepted")
        summary = str(result.get("summary") or "")
        require("Worker connection lane is active" in summary, "connect action missing useful summary")
        require("not invalidated" in summary, "connect action should reuse active session when possible")
        require("SECRET42" not in summary, "connect action leaked pairing code")

        fake_result = SimpleNamespace(
            worker_id="android_worker_alpha",
            label="Moto G Power 2025",
            success=True,
            detail="wake ok",
            to_dict=lambda: {"worker_id": "android_worker_alpha", "success": True},
        )
        wake_mgr.wake_all_stale = lambda **kwargs: [fake_result]
        result = actions.run_ui_system_action("use usb connection to wake")
        require(result.get("accepted") is True, "wake action was not accepted")
        require("USB wake/provision lane finished" in str(result.get("summary") or ""), "wake action missing useful summary")
    finally:
        adb_mgr._pc_lan_ip = old_ip
        adb_mgr.render_adb_workers_lan_auto_pair = old_pair
        link_mgr.link_status = old_link_status
        link_mgr.start_link = old_start
        if old_ensure is not None:
            link_mgr.ensure_receiver_running = old_ensure
        link_mgr.rotate_token = old_rotate
        if old_ensure_token is not None:
            link_mgr.ensure_session_token = old_ensure_token
        wake_mgr.wake_all_stale = old_wake


def main() -> None:
    for module in (
        ROOT / "engel_android_worker_prompt_signals.py",
        ROOT / "engel_ui_system_actions.py",
        ROOT / "engel_remote_worker_lan_pairing.py",
        ROOT / "engel_remote_worker_link_manager.py",
        ROOT / "engel_adb_worker_manager.py",
        ROOT / "engel_phone_wake_manager.py",
        ROOT / "engel_desktop_v2.py",
    ):
        py_compile.compile(str(module), doraise=True)
    verify_project_roots()
    verify_system_actions_with_mocks()
    print("OK: Engel UI system actions verified")


if __name__ == "__main__":
    main()
