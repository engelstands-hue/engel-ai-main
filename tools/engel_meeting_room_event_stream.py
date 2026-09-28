#!/usr/bin/env python3
"""Engel Meeting Room Event Stream — a truthful projection of REAL work events.

Serves the Conical Agentic Sentient Self Upgrading System primary goal
(memory/ENGEL_PRIMARY_GOAL_V1.json), acceptance criterion:
    "Meeting Room displays real work state rather than heartbeat animation."

Every event this module emits is backed by a REAL receipt file that already
exists on CT246 disk — an android assignment/claim/result packet, a Sub-Engel
`<HOST>__<order>.done.json` return, a server-transport bus line, or a meeting order
record. There is NO synthetic heartbeat and NO fabricated progress: if there is
no receipt, there is no event. Each event carries `evidence_ref` (the exact file
that proves it) so a verifier can confirm the stream never invents state.

This is a DECISION / OBSERVE / PROJECT engine only. Reads real artifacts, emits
an ordered event list and a room-state summary the UI can render, and (via the
`snapshot` CLI) materializes the current projection to a durable append-only
JSONL for tailing/audit. It never dispatches, executes, mutates source, or
writes trusted memory. The forbidden device is SHOWN honestly if it appears in
the real artifacts (observation), but is flagged — routing TO it is the broker's
job to refuse, not this stream's job to hide.

Stages (each tied to a real artifact):
  order_submitted / order_completed        <- runtime/meeting_room/main_ui_orders/*.json
  android_assigned / android_claimed / android_returned
                                            <- remote_workers/communication_queen_assignments/{approved,claimed,returned}
  sub_engel_returned                        <- <server transport>/SUB_ENGEL_SENT_WORK/<HOST>__*.done*.json
  bus_<CHANNEL>                             <- <server transport>/engel_server_transport_bus.jsonl
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

ANDROID_ASSIGN_ROOT = ROOT / "remote_workers" / "communication_queen_assignments"
MEETING_ORDERS_DIR = ROOT / "runtime" / "meeting_room" / "main_ui_orders"

FORBIDDEN_DEVICE_IDS = {"desktop-fib17o7"}


def _server_transport_dir() -> "Path | None":
    path = Path(
        os.environ.get(
            "ENGEL_SUB_ENGEL_TRANSPORT_ROOT",
            str(ROOT / "run" / "sub_engel_transport"),
        )
    )
    return path if path.is_dir() else None


def _read_json(path: Path) -> "dict[str, Any] | None":
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _parse_utc(value: Any) -> "float | None":
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _iso(ts: "float | None") -> str:
    if ts is None:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _mtime(path: Path) -> "float | None":
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _is_forbidden(device_id: str) -> bool:
    return str(device_id or "").strip().lower() in FORBIDDEN_DEVICE_IDS


def _event(ts: "float | None", stage: str, device: str, order_id: str, evidence: Path,
           summary: str = "", packet_id: str = "", extra: "dict[str, Any] | None" = None) -> "dict[str, Any]":
    return {
        "ts": ts,
        "ts_utc": _iso(ts),
        "stage": stage,
        "device": device,
        "device_forbidden": _is_forbidden(device),
        "order_id": order_id,
        "packet_id": packet_id,
        "evidence_ref": str(evidence),
        "evidence_present": evidence.is_file(),
        "summary": summary[:220],
        **({"extra": extra} if extra else {}),
    }


def _meeting_order_events() -> "list[dict[str, Any]]":
    out: list[dict[str, Any]] = []
    if not MEETING_ORDERS_DIR.is_dir():
        return out
    for f in MEETING_ORDERS_DIR.glob("*.json"):
        d = _read_json(f)
        if not isinstance(d, dict):
            continue
        oid = str(d.get("order_id") or f.stem)
        created = _parse_utc(d.get("created_at")) or _mtime(f)
        out.append(_event(created, "order_submitted", "engel_ai_main", oid, f,
                          summary=str(d.get("order_text") or "")))
        completed = _parse_utc(d.get("completed_at"))
        if completed:
            out.append(_event(completed, "order_completed", "engel_ai_main", oid, f,
                              summary=str(d.get("main_reply_preview") or "completed")))
    return out


def _android_events() -> "list[dict[str, Any]]":
    out: list[dict[str, Any]] = []
    stage_map = {"_assignment.json": "android_assigned", "_claim.json": "android_claimed",
                 "_result.json": "android_returned"}
    for sub in ("approved", "claimed", "returned"):
        d = ANDROID_ASSIGN_ROOT / sub
        if not d.is_dir():
            continue
        for f in d.glob("*.json"):
            suffix = next((s for s in stage_map if f.name.endswith(s)), None)
            if suffix is None:
                continue
            stage = stage_map[suffix]
            doc = _read_json(f) or {}
            device = str(doc.get("worker_id") or doc.get("worker_device") or "").strip()
            packet = str(doc.get("packet_id") or "")
            ts = (_parse_utc(doc.get("timestamp_utc")) or _parse_utc(doc.get("stored_at_utc"))
                  or _mtime(f))
            summ = str(doc.get("result_type") or doc.get("claim_type") or doc.get("draft_text") or stage)
            out.append(_event(ts, stage, device, packet or f.stem, f, summary=summ, packet_id=packet))
    return out


def _sub_engel_events() -> "list[dict[str, Any]]":
    out: list[dict[str, Any]] = []
    room = _server_transport_dir()
    if room is None:
        return out
    orders = room / "SUB_ENGEL_WORK_ORDERS"
    if orders.is_dir():
        for f in orders.glob("*.json"):
            doc = _read_json(f) or {}
            selected = (
                doc.get("selected_node")
                if isinstance(doc.get("selected_node"), dict)
                else {}
            )
            host = str(
                doc.get("selected_stable_identity")
                or selected.get("node_id")
                or selected.get("hostname")
                or "DESKTOP-UE5A6GG"
            )
            oid = str(doc.get("order_id") or doc.get("id") or f.stem)
            ts = (
                _parse_utc(doc.get("dispatched_at_utc"))
                or _parse_utc(doc.get("created_at_utc"))
                or _mtime(f)
            )
            out.append(
                _event(
                    ts,
                    "sub_engel_assigned",
                    host,
                    oid,
                    f,
                    summary=str(doc.get("job_type") or "assigned"),
                )
            )
    receipts = room / "receipts"
    if receipts.is_dir():
        for f in receipts.glob("*.dispatch.json"):
            doc = _read_json(f) or {}
            host = str(
                doc.get("node_id")
                or doc.get("hostname")
                or "DESKTOP-UE5A6GG"
            )
            oid = str(doc.get("order_id") or doc.get("id") or f.stem)
            ts = (
                _parse_utc(doc.get("dispatched_at_utc"))
                or _parse_utc(doc.get("created_at_utc"))
                or _mtime(f)
            )
            out.append(
                _event(
                    ts,
                    "sub_engel_claimed",
                    host,
                    oid,
                    f,
                    summary=str(doc.get("event") or "authenticated dispatch"),
                )
            )
    sent = room / "SUB_ENGEL_SENT_WORK"
    if sent.is_dir():
        for f in sent.glob("*.done*.json"):
            name = f.name
            host = name.split("__", 1)[0].strip() if "__" in name else ""
            doc = _read_json(f) or {}
            oid = str(doc.get("order_id") or "")
            ts = _parse_utc(doc.get("completed_at_utc")) or _mtime(f)
            engine = str(doc.get("worker_engine") or "")
            status = str(doc.get("operator_status") or "")
            out.append(_event(ts, "sub_engel_returned", host or str(doc.get("hostname") or ""), oid, f,
                              summary=f"engine={engine} status={status}"))
    return out


def _bus_events(limit: int = 200) -> "list[dict[str, Any]]":
    out: list[dict[str, Any]] = []
    room = _server_transport_dir()
    if room is None:
        return out
    bus = room / "engel_shared_room_bus.jsonl"
    if not bus.is_file():
        return out
    try:
        lines = bus.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    except OSError:
        return out
    for line in lines:
        try:
            d = json.loads(line)
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        ch = str(d.get("channel") or "").strip()
        sender = str(d.get("sender") or "").strip()
        ts = _parse_utc(d.get("timestamp_utc"))
        out.append(_event(ts, f"bus_{ch or 'unknown'}", sender, "", bus,
                          summary=str(d.get("message") or "")))
    return out


def collect_events(limit: int = 120) -> "list[dict[str, Any]]":
    """All real work events across every source, newest first, evidence-backed."""
    events: list[dict[str, Any]] = []
    for fn in (_meeting_order_events, _android_events, _sub_engel_events, _bus_events):
        try:
            events.extend(fn())
        except Exception:
            continue
    # Sort newest first; events without a timestamp sink to the bottom deterministically.
    events.sort(key=lambda e: (e.get("ts") is not None, e.get("ts") or 0.0), reverse=True)
    return events[:limit]


def room_state(limit: int = 120) -> "dict[str, Any]":
    """The Meeting Room's REAL state for the UI: recent evidence-backed events,
    per-order lifecycle rollup, and per-device last real activity. No heartbeat."""
    events = collect_events(limit=limit)
    now = datetime.now(timezone.utc)

    # Per-order lifecycle: which stages have real evidence.
    orders: dict[str, dict[str, Any]] = {}
    for e in events:
        oid = e.get("order_id") or ""
        if not oid:
            continue
        rec = orders.setdefault(oid, {"order_id": oid, "stages": [], "last_ts_utc": "", "devices": set()})
        rec["stages"].append(e["stage"])
        if e.get("device"):
            rec["devices"].add(e["device"])
        if e.get("ts_utc") and e["ts_utc"] > rec["last_ts_utc"]:
            rec["last_ts_utc"] = e["ts_utc"]
    order_rollup = []
    for oid, rec in orders.items():
        rec["devices"] = sorted(rec["devices"])
        rec["stage_count"] = len(rec["stages"])
        rec["has_return_proof"] = any(s in ("android_returned", "sub_engel_returned", "order_completed")
                                      for s in rec["stages"])
        rec["stages"] = sorted(set(rec["stages"]))
        order_rollup.append(rec)
    order_rollup.sort(key=lambda r: r.get("last_ts_utc", ""), reverse=True)

    # Per-device last real activity (replaces the heartbeat animation).
    devices: dict[str, dict[str, Any]] = {}
    for e in events:
        dev = e.get("device") or ""
        if not dev:
            continue
        cur = devices.get(dev)
        if cur is None or (e.get("ts_utc") or "") > cur["last_activity_utc"]:
            devices[dev] = {
                "device": dev,
                "forbidden": e.get("device_forbidden", False),
                "last_stage": e["stage"],
                "last_activity_utc": e.get("ts_utc") or "",
                "last_evidence_ref": e.get("evidence_ref", ""),
            }

    # Wire in the device broker's CURRENT routing eligibility (guarded, fail-open)
    # so the room shows BOTH "who can be routed right now" (broker) and "what
    # really happened" (events) — the two conical pieces in one truthful view.
    broker_eligibility: dict[str, Any] = {"available": False}
    try:
        import engel_device_broker as _broker

        _decision = _broker.broker_decision()
        broker_eligibility = {
            "available": True,
            "eligible_device_ids": _decision.get("selected_device_ids", []),
            "candidate_count": _decision.get("candidate_count", 0),
            "forbidden_devices": _decision.get("forbidden_devices", []),
        }
    except Exception:
        broker_eligibility = {"available": False}

    worker_proof: dict[str, Any] = {
        "ok": False,
        "status": "worker proof unavailable",
    }
    try:
        from tools.engel_worker_live_claim_return_proof import (
            worker_live_claim_return_snapshot,
        )

        worker_proof = worker_live_claim_return_snapshot()
    except Exception as exc:
        worker_proof = {
            "ok": False,
            "status": "worker proof unavailable",
            "error": str(exc),
        }

    return {
        "schema": "engel_meeting_room_event_stream_state_v1",
        "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
        "generated_at_utc": now.isoformat(),
        "display_mode": "real_work_events_from_receipts",
        "heartbeat_animation": False,
        "broker_eligibility": broker_eligibility,
        "server_transport_present": _server_transport_dir() is not None,
        "shared_room_mounted": False,
        "transport_mode": "ct246_server",
        "event_count": len(events),
        "events_all_evidence_backed": all(e.get("evidence_present") for e in events),
        "order_count": len(order_rollup),
        "orders": order_rollup[:40],
        "device_activity": sorted(devices.values(), key=lambda d: d["last_activity_utc"], reverse=True),
        "worker_live_claim_return_proof": worker_proof,
        "recent_events": events[:40],
        "actor_note": "observe/project only; never dispatches, executes, or writes trusted memory",
    }


def snapshot_to_stream(out_path: "Path | None" = None) -> "dict[str, Any]":
    """Materialize the current projection to a durable append-only JSONL the UI
    can tail. Appends only NEW event fingerprints (idempotent across runs)."""
    out_path = out_path or (ROOT / "reports" / "meeting_room_event_stream" / "events.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    if out_path.is_file():
        try:
            for line in out_path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    seen.add(json.loads(line).get("fingerprint", ""))
                except Exception:
                    continue
        except OSError:
            pass
    appended = 0
    events = collect_events(limit=500)
    with out_path.open("a", encoding="utf-8") as fh:
        for e in reversed(events):  # append oldest-first so the log reads chronologically
            fp = f"{e.get('ts')}|{e.get('stage')}|{e.get('device')}|{e.get('order_id')}|{e.get('packet_id')}|{e.get('evidence_ref')}"
            import hashlib
            fpid = hashlib.sha1(fp.encode("utf-8")).hexdigest()[:16]
            if fpid in seen:
                continue
            seen.add(fpid)
            fh.write(json.dumps({**e, "fingerprint": fpid}, ensure_ascii=False) + "\n")
            appended += 1
    # Materialize the current room state to a stable path the UI reads to render
    # REAL work state (device activity + per-order lifecycle) instead of a
    # heartbeat animation. Written atomically so a reader never sees a partial.
    state_path = out_path.parent / "room_state.json"
    tmp = state_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(room_state(limit=120), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(state_path)
    return {"ok": True, "stream_path": str(out_path), "room_state_path": str(state_path),
            "appended": appended, "total_seen": len(seen)}


def _cli(argv: "list[str] | None" = None) -> int:
    import argparse
    import sys

    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Engel Meeting Room event stream (observe/project only)")
    sub = parser.add_subparsers(dest="cmd")
    st = sub.add_parser("state", help="print the real room state for the UI")
    st.add_argument("--limit", type=int, default=120)
    ev = sub.add_parser("events", help="print raw evidence-backed events")
    ev.add_argument("--limit", type=int, default=60)
    sub.add_parser("snapshot", help="append new events to the durable stream JSONL")
    args = parser.parse_args(argv)
    if args.cmd == "events":
        print(json.dumps(collect_events(args.limit), indent=2, ensure_ascii=False))
    elif args.cmd == "snapshot":
        print(json.dumps(snapshot_to_stream(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(room_state(getattr(args, "limit", 120)), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
