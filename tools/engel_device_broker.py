#!/usr/bin/env python3
"""Engel Real Device Broker — evidence-backed, fail-closed device routing decisions.

Serves the Conical Agentic Sentient Self Upgrading System primary goal
(memory/ENGEL_PRIMARY_GOAL_V1.json), acceptance criterion:
    "Only reachable and capable devices receive assignments."

This module is a DECISION / OBSERVE engine ONLY. It reads the same real
evidence the fleet already produces — the paired-phone bridge state and the
Sub-Engel node summaries — and emits a routing DECISION with provenance for
each candidate device. It never dispatches, executes, opens a listener, writes
trusted memory, mutates source, or claims a device is usable without current
evidence. The existing dispatch code stays the actor; it may CONSULT this
broker so it never fans out to an unreachable, incapable, or forbidden device.

Fail-closed contract:
  - Missing / unreadable evidence  -> device is NOT eligible (never assumed up).
  - Stale evidence (age > freshness) -> NOT eligible.
  - Forbidden device (goal contract) -> NEVER eligible, even with fresh evidence.
  - job_kind given but not in the device's declared capabilities -> NOT capable.

Every eligible decision carries the exact evidence signals that justified it, so
a verifier (verify_engel_device_broker.py) can prove the decision matches reality.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

PHONE_BRIDGE_STATE = ROOT / "memory" / "phone_bridge" / "ENGEL_REMOTE_WORKERS_PAIRED.json"

# Goal contract forbids routing work to this retired node (never eligible).
FORBIDDEN_DEVICE_IDS = {"desktop-fib17o7"}

def _env_seconds(name: str, default: float) -> float:
    """A malformed override must degrade to the default, not kill the broker
    import (the dispatch gate must always be able to load)."""
    try:
        return float(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default


# Default freshness ceiling if the evidence file does not declare one.
# (2026-07-28, issue a69a3dca) Overridable for slow phones via env - the
# default stays 300s so a genuinely dead phone still goes stale on time.
DEFAULT_FRESHNESS_LIMIT_SECONDS = _env_seconds(
    "ENGEL_DEVICE_BROKER_FRESHNESS_SECONDS", 300.0
)

# Sub-Engel via the shared room has no live heartbeat — only return activity
# when it processes work. A recent return is a POSITIVE liveness signal; its
# absence is NOT proof of death (the node may be reachable-but-idle), so the
# broker treats a recent return as reachable and fails closed otherwise. Window
# is more lenient than the android live-heartbeat (sub-engel polls, not streams).
SUB_ENGEL_SHARED_ROOM_FRESHNESS_SECONDS = _env_seconds(
    "ENGEL_DEVICE_BROKER_SUB_ENGEL_FRESHNESS_SECONDS", 1800.0
)

# Declared capability floors per device class. A device is "capable" of a
# job_kind when the job_kind is in its declared capability set. These mirror the
# bounded task types the fleet already runs; a device's own evidence may narrow
# them further but never widen past what it declares.
ANDROID_DEFAULT_CAPABILITIES = ("summarize_text", "draft_candidate_json", "classify_file", "return_status")
SUB_ENGEL_DEFAULT_CAPABILITIES = ("return_status", "node_status", "local_llm_status", "diagnostics")


def _read_json(path: Path) -> "dict[str, Any] | None":
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _now() -> float:
    return time.time()


def _parse_utc(value: Any) -> "float | None":
    """Best-effort ISO-8601 -> epoch seconds; None if unparseable."""
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        from datetime import datetime

        return datetime.fromisoformat(text).timestamp()
    except Exception:
        return None


def _is_forbidden(device_id: str) -> bool:
    return str(device_id or "").strip().lower() in FORBIDDEN_DEVICE_IDS


def _capability_ok(job_kind: "str | None", capabilities: "tuple[str, ...]") -> bool:
    if not job_kind:
        return True  # no specific capability demanded
    return str(job_kind).strip().lower() in {c.lower() for c in capabilities}


def _android_candidates(job_kind: "str | None", now: float) -> "list[dict[str, Any]]":
    state = _read_json(PHONE_BRIDGE_STATE)
    out: list[dict[str, Any]] = []
    if not isinstance(state, dict):
        return out
    try:
        freshness = float(state.get("freshness_limit_seconds") or DEFAULT_FRESHNESS_LIMIT_SECONDS)
    except (TypeError, ValueError):
        freshness = DEFAULT_FRESHNESS_LIMIT_SECONDS
    live_required = bool(state.get("live_phone_required", True))
    workers = state.get("workers") if isinstance(state.get("workers"), list) else []
    for w in workers:
        if not isinstance(w, dict):
            continue
        wid = str(w.get("worker_id") or w.get("worker_name") or "").strip()
        # Age: prefer the recorded age; else derive from last_seen.
        age = w.get("last_seen_age_seconds")
        try:
            age = float(age) if age is not None else None
        except (TypeError, ValueError):
            age = None
        if age is None:
            seen = _parse_utc(w.get("last_seen"))
            age = (now - seen) if seen is not None else None
        paired = bool(w.get("paired"))
        live = bool(w.get("live_phone_connected"))
        adb_online = bool(w.get("adb_device_online"))
        declared = w.get("allowed_task_types")
        capabilities = tuple(declared) if isinstance(declared, list) and declared else ANDROID_DEFAULT_CAPABILITIES
        fresh = age is not None and age <= freshness
        reachable = paired and fresh and (live or not live_required)
        allowed = not _is_forbidden(wid)
        capable = _capability_ok(job_kind, capabilities)
        reasons = []
        if not paired:
            reasons.append("not paired")
        if age is None:
            reasons.append("no last-seen evidence")
        elif not fresh:
            reasons.append(f"stale ({age:.0f}s > {freshness:.0f}s)")
        if live_required and not live:
            reasons.append("phone not live-connected")
        if not allowed:
            reasons.append("forbidden device")
        if not capable:
            reasons.append(f"cannot do job_kind={job_kind}")
        out.append({
            "device_id": wid,
            "device_class": "android_worker",
            "reachable": bool(reachable),
            "capable": bool(capable),
            "allowed": bool(allowed),
            "eligible": bool(reachable and capable and allowed),
            "capabilities": list(capabilities),
            "evidence": {
                "source": str(PHONE_BRIDGE_STATE),
                "paired": paired,
                "live_phone_connected": live,
                "adb_device_online": adb_online,
                "last_seen_age_seconds": age,
                "freshness_limit_seconds": freshness,
                "live_required": live_required,
                "phone_ip": str(w.get("phone_ip") or ""),
                "transport": str(w.get("transport") or ""),
            },
            "reason": "; ".join(reasons) if reasons else "reachable, capable, allowed",
        })
    return out


def _android_live_presence_candidates(
    job_kind: "str | None",
    now: float,
) -> "list[dict[str, Any]]":
    """Use canonical live presence so stale durable rows cannot hide a phone."""
    del now
    try:
        from engel_phone_presence import phone_presence_snapshot

        snapshot = phone_presence_snapshot()
    except Exception:
        return []
    workers = snapshot.get("workers") if isinstance(snapshot, dict) else None
    if not isinstance(workers, dict):
        return []
    out: list[dict[str, Any]] = []
    for worker_id, raw in workers.items():
        if not isinstance(raw, dict):
            continue
        wid = str(raw.get("worker_id") or worker_id or "").strip()
        paired = raw.get("paired") is True
        authenticated = raw.get("authenticated_presence") is True
        live = raw.get("live") is True
        capabilities = ANDROID_DEFAULT_CAPABILITIES
        capable = _capability_ok(job_kind, capabilities)
        allowed = not _is_forbidden(wid)
        reachable = paired and authenticated and live
        reasons = []
        if not paired:
            reasons.append("not paired")
        if not authenticated:
            reasons.append("presence not authenticated")
        if not live:
            reasons.append(str(raw.get("reason") or "phone not live"))
        if not allowed:
            reasons.append("forbidden device")
        if not capable:
            reasons.append(f"cannot do job_kind={job_kind}")
        out.append(
            {
                "device_id": wid,
                "device_class": "android_worker",
                "reachable": bool(reachable),
                "capable": bool(capable),
                "allowed": bool(allowed),
                "eligible": bool(reachable and capable and allowed),
                "capabilities": list(capabilities),
                "evidence": {
                    "source": "engel_phone_presence.phone_presence_snapshot",
                    "paired": paired,
                    "authenticated_presence": authenticated,
                    "live_phone_connected": live,
                    "last_seen_age_seconds": raw.get("fresh_seconds"),
                    "freshness_limit_seconds": raw.get("freshness_limit_seconds"),
                    "phone_ip": str(raw.get("required_ip") or ""),
                    "observed_ip": str(raw.get("observed_ip") or ""),
                    "transport": str(raw.get("transport") or ""),
                    "adb_serial": str(raw.get("adb_serial") or ""),
                    "adb_reverse_verified": raw.get("adb_reverse_verified") is True,
                },
                "reason": "; ".join(reasons)
                if reasons
                else "fresh authenticated phone presence, capable, allowed",
            }
        )
    return out


def _sub_engel_candidates(job_kind: "str | None", now: float) -> "list[dict[str, Any]]":
    """Sub-Engel node candidates from the meeting-bridge node summaries. Import
    is done lazily and guarded so the broker still works (android-only) if the
    bridge module is unavailable in a given runtime."""
    out: list[dict[str, Any]] = []
    try:
        import engel_sub_node_meeting_bridge as bridge
    except Exception:
        return out
    try:
        summaries = bridge.windows_node_summaries()
    except Exception:
        summaries = []
    for node in summaries or []:
        if not isinstance(node, dict):
            continue
        nid = str(node.get("node_id") or node.get("hostname") or "").strip()
        paired = bool(node.get("paired"))
        meeting_ready = bool(node.get("meeting_ready"))
        # Health/expiry evidence when present.
        expires = node.get("expires_at_utc")
        not_expired = True
        if expires is not None:
            try:
                not_expired = bridge._not_expired(expires)
            except Exception:
                not_expired = False
        live_ok = node.get("live_health_ok")
        declared = node.get("allowed_actions")
        capabilities = tuple(declared) if isinstance(declared, list) and declared else SUB_ENGEL_DEFAULT_CAPABILITIES
        # Fail-closed: reachable requires paired + meeting_ready + not-expired.
        # A live health probe, if present and false, disqualifies; if absent,
        # paired+ready+unexpired is the evidence floor.
        reachable = paired and meeting_ready and not_expired and (live_ok is not False)
        allowed = not _is_forbidden(nid)
        capable = _capability_ok(job_kind, capabilities)
        reasons = []
        if not paired:
            reasons.append("not paired")
        if not meeting_ready:
            reasons.append("not meeting-ready")
        if not not_expired:
            reasons.append("session expired")
        if live_ok is False:
            reasons.append("live health probe failed")
        if not allowed:
            reasons.append("forbidden device")
        if not capable:
            reasons.append(f"cannot do job_kind={job_kind}")
        out.append({
            "device_id": nid,
            "device_class": "sub_engel_windows",
            "reachable": bool(reachable),
            "capable": bool(capable),
            "allowed": bool(allowed),
            "eligible": bool(reachable and capable and allowed),
            "capabilities": list(capabilities),
            "evidence": {
                "source": "engel_sub_node_meeting_bridge.windows_node_summaries",
                "paired": paired,
                "meeting_ready": meeting_ready,
                "not_expired": not_expired,
                "live_health_ok": live_ok,
                "expires_at_utc": str(expires or ""),
            },
            "reason": "; ".join(reasons) if reasons else "reachable, capable, allowed",
        })
    return out


def _server_transport_dir() -> "Path | None":
    """Resolve CT246-owned Sub-Engel transport receipts; fail closed if absent."""
    path = Path(
        os.environ.get(
            "ENGEL_SUB_ENGEL_TRANSPORT_ROOT",
            str(ROOT / "run" / "sub_engel_transport"),
        )
    )
    return path if path.is_dir() else None


def _sub_engel_server_transport_candidates(job_kind: "str | None", now: float) -> "list[dict[str, Any]]":
    """Sub-Engel liveness from recent CT246 transport returns. A `<HOST>__<order>.done.json`
    written inside the freshness window proves that HOST is alive and processing.
    Absence is not proof of death, so this only ever ADDS reachability evidence."""
    out: list[dict[str, Any]] = []
    room = _server_transport_dir()
    if room is None:
        return out
    sent = room / "SUB_ENGEL_SENT_WORK"
    if not sent.is_dir():
        return out
    freshest: dict[str, float] = {}
    try:
        for f in sent.glob("*.done*.json"):
            name = f.name
            if "__" not in name:
                continue
            host = name.split("__", 1)[0].strip()
            if not host:
                continue
            try:
                mtime = f.stat().st_mtime
            except OSError:
                continue
            if host not in freshest or mtime > freshest[host]:
                freshest[host] = mtime
    except OSError:
        return out
    for host, mtime in freshest.items():
        age = now - mtime
        fresh = age <= SUB_ENGEL_SHARED_ROOM_FRESHNESS_SECONDS
        allowed = not _is_forbidden(host)
        capable = _capability_ok(job_kind, SUB_ENGEL_DEFAULT_CAPABILITIES)
        reasons = []
        if not fresh:
            reasons.append(f"no recent server-transport return ({age:.0f}s > {SUB_ENGEL_SHARED_ROOM_FRESHNESS_SECONDS:.0f}s)")
        if not allowed:
            reasons.append("forbidden device")
        if not capable:
            reasons.append(f"cannot do job_kind={job_kind}")
        out.append({
            "device_id": host,
            "device_class": "sub_engel_server_transport",
            "reachable": bool(fresh),
            "capable": bool(capable),
            "allowed": bool(allowed),
            "eligible": bool(fresh and capable and allowed),
            "capabilities": list(SUB_ENGEL_DEFAULT_CAPABILITIES),
            "evidence": {
                "source": str(sent),
                "last_return_age_seconds": age,
                "freshness_limit_seconds": SUB_ENGEL_SHARED_ROOM_FRESHNESS_SECONDS,
                "signal": "recent server-transport return = alive; absence is not death",
            },
            "reason": "; ".join(reasons) if reasons else "recent server-transport return, capable, allowed",
        })
    return out


def _merge_candidates(rows: "list[dict[str, Any]]") -> "list[dict[str, Any]]":
    """Dedup by device_id: a device seen through two evidence sources is ONE
    candidate that is eligible if EITHER source proves it (OR of eligibility),
    keeping both evidence blocks for the verifier/audit."""
    by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in rows:
        did = str(row.get("device_id") or "").strip().lower()
        if not did:
            order.append("__blank__%d" % len(order))
            by_id[order[-1]] = row
            continue
        if did not in by_id:
            by_id[did] = dict(row)
            by_id[did]["evidence_sources"] = [row.get("evidence", {})]
            order.append(did)
        else:
            merged = by_id[did]
            merged["evidence_sources"].append(row.get("evidence", {}))
            for flag in ("reachable", "capable", "allowed", "eligible"):
                merged[flag] = bool(merged.get(flag)) or bool(row.get(flag))
            # allowed is an AND (any forbidden source forbids); recompute honestly
            merged["allowed"] = bool(merged.get("allowed")) and bool(row.get("allowed"))
            merged["eligible"] = merged["reachable"] and merged["capable"] and merged["allowed"]
            merged["reason"] = merged.get("reason", "") + " | " + row.get("reason", "")
    return [by_id[k] for k in order]


def broker_decision(job_kind: "str | None" = None) -> "dict[str, Any]":
    """Evaluate every candidate device against real evidence and return a routing
    decision. Pure: reads evidence, returns a record, writes nothing."""
    now = _now()
    raw: list[dict[str, Any]] = []
    for source_name, fn in (
        ("android_live_presence", _android_live_presence_candidates),
        ("android_worker", _android_candidates),
        ("sub_engel_windows", _sub_engel_candidates),
        ("sub_engel_server_transport", _sub_engel_server_transport_candidates),
    ):
        try:
            raw.extend(fn(job_kind, now))
        except Exception as exc:  # never let a candidate source crash the decision
            raw.append({"device_id": "", "device_class": source_name, "eligible": False,
                        "reachable": False, "capable": False, "allowed": True,
                        "evidence": {"error": str(exc)[:200]}, "reason": f"{source_name} evidence error"})
    candidates = _merge_candidates(raw)
    selected = [c["device_id"] for c in candidates if c.get("eligible") and c.get("device_id")]
    from datetime import datetime, timezone
    return {
        "schema": "engel_device_broker_decision_v1",
        "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
        "job_kind": job_kind,
        "decided_at_utc": datetime.now(timezone.utc).isoformat(),
        "forbidden_devices": sorted(FORBIDDEN_DEVICE_IDS),
        "candidate_count": len(candidates),
        "eligible_count": len(selected),
        "selected_device_ids": selected,
        "candidates": candidates,
        "actor_note": "decision/observe only; broker never dispatches, executes, or writes trusted memory",
        "provenance": {
            "phone_presence_source": "engel_phone_presence.phone_presence_snapshot",
            "phone_bridge_state": str(PHONE_BRIDGE_STATE),
            "phone_bridge_present": PHONE_BRIDGE_STATE.is_file(),
            "sub_engel_source": "engel_sub_node_meeting_bridge.windows_node_summaries",
        },
    }


def _cli(argv: "list[str] | None" = None) -> int:
    import argparse
    import sys

    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Engel real device broker (decision/observe only)")
    parser.add_argument("--job-kind", default=None, help="capability to require (e.g. summarize_text)")
    args = parser.parse_args(argv)
    print(json.dumps(broker_decision(args.job_kind), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
