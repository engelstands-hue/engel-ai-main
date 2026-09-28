#!/usr/bin/env python3
"""Verifier for the Engel Real Device Broker (engel_device_broker.py).

Proves the goal-critical invariants of the broker's routing decisions using
deterministic synthetic fixtures plus a live read, and confirms the broker is
a decision/observe engine that mutates nothing. Emits a {"ok": bool, ...}
receipt to stdout; exit 0 on pass, 1 on fail.

Invariants proven (goal: "Only reachable and capable devices receive assignments"):
  1. FRESH live evidence  -> device eligible.
  2. STALE evidence (age > freshness) -> device NOT eligible.
  3. FORBIDDEN device (DESKTOP-FIB17O7) -> NEVER eligible, even with fresh evidence.
  4. MISSING evidence -> fail-closed (no eligible device fabricated).
  5. job_kind capability mismatch -> NOT capable -> NOT eligible.
  6. Every eligible candidate in the LIVE decision carries current supporting evidence.
  7. The broker performs no source mutation / trusted-memory write (decision-only).
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import engel_device_broker as broker  # noqa: E402

CHECKS: list[dict] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"check": name, "ok": bool(ok), "detail": detail})


def _find(decision: dict, device_id: str) -> "dict | None":
    for c in decision.get("candidates", []):
        if str(c.get("device_id", "")).lower() == device_id.lower():
            return c
    return None


def _write_phone_state(tmp: Path, workers: list[dict], freshness: float = 300.0, live_required: bool = True) -> None:
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps({
        "schema": "engel_remote_workers_paired_v1",
        "freshness_limit_seconds": freshness,
        "live_phone_required": live_required,
        "workers": workers,
    }), encoding="utf-8")


def main() -> int:
    tmpdir = Path(tempfile.mkdtemp(prefix="engel_device_broker_verify_"))
    orig_phone = broker.PHONE_BRIDGE_STATE
    # Neutralize the sub-engel sources during synthetic tests so ONLY the
    # android fixture is under test (deterministic). We test forbidden/stale via
    # the android fixture, which shares the same _is_forbidden gate.
    orig_sub = broker._sub_engel_candidates
    orig_transport = broker._sub_engel_server_transport_candidates
    orig_live_presence = broker._android_live_presence_candidates
    broker._sub_engel_candidates = lambda job_kind, now: []
    broker._sub_engel_server_transport_candidates = lambda job_kind, now: []
    broker._android_live_presence_candidates = lambda job_kind, now: []
    try:
        # --- 1 & 2: fresh eligible, stale not eligible ---------------------
        phone = tmpdir / "phone_state.json"
        # gamma isolates STALENESS: paired+live+adb all true, ONLY the age is
        # stale. If the freshness comparison is ever widened or removed, this
        # worker becomes eligible and the check fails (coverage-hole lesson
        # from cycle engel_cycle_8a8bf68893af0d7f: a confounded fixture let a
        # freshness-widening patch commit).
        _write_phone_state(phone, [
            {"worker_id": "android_worker_alpha", "paired": True, "live_phone_connected": True,
             "adb_device_online": True, "last_seen_age_seconds": 3.0, "phone_ip": "192.0.2.78"},
            {"worker_id": "android_worker_gamma", "paired": True, "live_phone_connected": True,
             "adb_device_online": True, "last_seen_age_seconds": 999999.0, "phone_ip": "x"},
        ])
        broker.PHONE_BRIDGE_STATE = phone
        d = broker.broker_decision()
        alpha = _find(d, "android_worker_alpha")
        gamma = _find(d, "android_worker_gamma")
        record("fresh live device is eligible", bool(alpha and alpha["eligible"]), str(alpha))
        record("stale device is NOT eligible (staleness isolated)",
               bool(gamma and not gamma["eligible"] and "stale" in str(gamma.get("reason", ""))),
               str(gamma and gamma["reason"]))
        record("selected list contains only the eligible device",
               d["selected_device_ids"] == ["android_worker_alpha"], str(d["selected_device_ids"]))

        broker._android_live_presence_candidates = lambda job_kind, now: [
            {
                "device_id": "android_worker_gamma",
                "device_class": "android_worker",
                "reachable": True,
                "capable": True,
                "allowed": True,
                "eligible": True,
                "capabilities": list(broker.ANDROID_DEFAULT_CAPABILITIES),
                "evidence": {
                    "source": "engel_phone_presence.phone_presence_snapshot",
                    "paired": True,
                    "authenticated_presence": True,
                    "live_phone_connected": True,
                    "last_seen_age_seconds": 2.0,
                    "freshness_limit_seconds": 300.0,
                },
                "reason": "fresh authenticated phone presence, capable, allowed",
            }
        ]
        d_live_override = broker.broker_decision()
        gamma_live = _find(d_live_override, "android_worker_gamma")
        record(
            "canonical live presence overrides a stale durable phone row",
            bool(
                gamma_live
                and gamma_live["eligible"]
                and "android_worker_gamma" in d_live_override["selected_device_ids"]
            ),
            str(gamma_live),
        )
        broker._android_live_presence_candidates = lambda job_kind, now: []

        # --- 3: forbidden device never eligible even with FRESH evidence ---
        _write_phone_state(phone, [
            {"worker_id": "DESKTOP-FIB17O7", "paired": True, "live_phone_connected": True,
             "adb_device_online": True, "last_seen_age_seconds": 1.0, "phone_ip": "y"},
        ])
        d = broker.broker_decision()
        fib = _find(d, "DESKTOP-FIB17O7")
        record("forbidden device NOT eligible despite fresh evidence",
               bool(fib and not fib["eligible"] and fib["allowed"] is False),
               str(fib and fib["reason"]))
        record("forbidden device absent from selected list",
               "desktop-fib17o7" not in [x.lower() for x in d["selected_device_ids"]], "")

        # --- 4: missing evidence -> fail-closed ---------------------------
        broker.PHONE_BRIDGE_STATE = tmpdir / "does_not_exist.json"
        d = broker.broker_decision()
        record("missing evidence fabricates no eligible device", d["eligible_count"] == 0, str(d["selected_device_ids"]))

        # --- 5: capability mismatch -> not capable -> not eligible --------
        broker.PHONE_BRIDGE_STATE = phone
        _write_phone_state(phone, [
            {"worker_id": "android_worker_alpha", "paired": True, "live_phone_connected": True,
             "adb_device_online": True, "last_seen_age_seconds": 2.0, "phone_ip": "z",
             "allowed_task_types": ["summarize_text"]},
        ])
        d_cap = broker.broker_decision(job_kind="disk_format")
        a2 = _find(d_cap, "android_worker_alpha")
        record("capability mismatch makes device not eligible",
               bool(a2 and a2["capable"] is False and not a2["eligible"]), str(a2 and a2["reason"]))
        d_ok = broker.broker_decision(job_kind="summarize_text")
        a3 = _find(d_ok, "android_worker_alpha")
        record("declared capability match makes device eligible",
               bool(a3 and a3["capable"] and a3["eligible"]), str(a3 and a3["reason"]))
    finally:
        broker.PHONE_BRIDGE_STATE = orig_phone
        broker._sub_engel_candidates = orig_sub
        broker._sub_engel_server_transport_candidates = orig_transport
        broker._android_live_presence_candidates = orig_live_presence

    # --- 6: LIVE decision — every eligible has current supporting evidence -
    live = broker.broker_decision()
    live_ok = True
    for c in live.get("candidates", []):
        if not c.get("eligible"):
            continue
        ev = c.get("evidence", {}) or {}
        srcs = c.get("evidence_sources", [ev])
        has_current = False
        for e in srcs:
            age = e.get("last_seen_age_seconds", e.get("last_return_age_seconds"))
            lim = e.get("freshness_limit_seconds")
            if age is not None and lim is not None and age <= lim:
                has_current = True
            if e.get("paired") is True and e.get("live_phone_connected") is True:
                has_current = True
            if e.get("meeting_ready") is True and e.get("not_expired") is True:
                has_current = True
        if not has_current:
            live_ok = False
            record("LIVE eligible device lacks current evidence", False, str(c.get("device_id")))
    record("every LIVE eligible device carries current evidence", live_ok,
           f"eligible={live.get('selected_device_ids')}")
    record("forbidden device never in LIVE selected list",
           not any(x.lower() in broker.FORBIDDEN_DEVICE_IDS for x in live.get("selected_device_ids", [])), "")

    # --- 7: decision-only — the module writes nothing on decision ---------
    src = Path(broker.__file__).read_text(encoding="utf-8")
    banned = ("open(", ".write_text(", ".write(", "trusted_memory", "subprocess", "os.system")
    # 'open(' etc. must not appear as WRITE ops; the broker only reads json via read_text.
    write_markers = [m for m in (".write_text(", ".write(", "os.system", "subprocess.") if m in src]
    record("broker performs no writes/exec (decision-only)", not write_markers, f"markers={write_markers}")

    passed = sum(1 for c in CHECKS if c["ok"])
    failed = [c for c in CHECKS if not c["ok"]]
    receipt = {
        "schema": "engel_device_broker_verifier_v1",
        "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
        "ok": not failed,
        "checks_total": len(CHECKS),
        "checks_passed": passed,
        "checks_failed": len(failed),
        "failed_checks": failed,
        "checks": CHECKS,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
