#!/usr/bin/env python3
"""Engel Self-Upgrade Loop Stream — makes the governed loop VISIBLE.

Serves the Conical Agentic Sentient Self Upgrading System primary goal
(durable proof through the Engel AI Main user interface). OBSERVE/PROJECT
ONLY: reads the loop's real receipts and writes one UI-readable state file:

    reports/self_upgrade/loop_stream/state.json

Sections (every number traces to files on disk):
  cycles        — recent governed cycle receipts (stage ticks, final_status)
  quorum        — decision receipts count + latest decision
  post_deploy   — post-deploy gate receipts count + latest decision
  issues        — issue count + newest issues (failure->issue intake visible)
  failure_ingest— ledger totals (deduped conical failures already ingested)
  self_model    — revision + observation age (sentient freshness visible)
  pipes         — provider bridge pipe health from local loopback (bounded
                  2s probes; skipped when ENGEL_LOOP_STREAM_SKIP_PORT_PROBES=1)
  broker        — current device-broker eligibility (guarded import)

No dispatch, no source mutation, no trusted-memory write, no external hosts.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT_ROOT = ROOT / "reports" / "self_upgrade"
OUT_DIR = REPORT_ROOT / "loop_stream"
STATE_PATH = OUT_DIR / "state.json"
SELF_MODEL_STATE = ROOT / "memory" / "self_model" / "ENGEL_SELF_MODEL_V1.json"
PRIMARY_GOAL_ROOT = ROOT
PRIMARY_GOAL_COMPLETION = REPORT_ROOT / "goal_completion" / "latest.json"

# Loopback-only provider pipe ports. The bridges listen on the even ports on
# the ROG; CT246 reaches them on port+1 through the reverse tunnels — so each
# pipe is probed on BOTH and reported up if EITHER side answers (2026-07-27
# fix: CT snapshots showed 0 pipes up because only ROG ports were probed).
# grok chat 24880 stays OFF by operator policy: policy_off, never a failure.
PIPE_PORTS = (
    ("claude", (24882, 24883)),
    ("chatgpt", (24884, 24885)),
    ("gemini", (24886, 24887)),
    ("codex", (24888, 24889)),
    ("grok_headless", (24892, 24890)),
)
POLICY_OFF_PIPES = ({"pipe": "grok_chat", "port": 24880, "status": "policy_off",
                     "note": "grok.exe CLI stays OFF (operator policy); headless lane serves grok"},)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> "dict[str, Any] | None":
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _newest(dir_path: Path, pattern: str, limit: int) -> "list[Path]":
    if not dir_path.is_dir():
        return []
    files = sorted(dir_path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _cycles(limit: int = 6) -> "list[dict[str, Any]]":
    out = []
    for path in _newest(REPORT_ROOT / "cycles", "*.json", limit):
        data = _read_json(path)
        if not data:
            continue
        out.append({
            "cycle_id": data.get("cycle_id"),
            "mode": data.get("mode"),
            "final_status": data.get("final_status"),
            "started_at_utc": data.get("started_at_utc"),
            "stages": [{"stage": s.get("stage"), "ok": s.get("ok") is True}
                       for s in (data.get("stages") or []) if isinstance(s, dict)],
            "receipt": _rel(path),
        })
    return out


def _latest_decision(dir_path: Path, pattern: str, decision_key: str) -> "dict[str, Any]":
    files = _newest(dir_path, pattern, 200)
    latest = _read_json(files[0]) if files else None
    return {
        "count": len(files),
        "latest": {
            "decision": (latest or {}).get(decision_key),
            "at_utc": (latest or {}).get("decided_at_utc") or (latest or {}).get("created_at_utc"),
            "receipt": _rel(files[0]) if files else None,
        } if latest else None,
    }


def _issues(limit: int = 5) -> "dict[str, Any]":
    files = _newest(REPORT_ROOT / "issues", "*.json", 500)
    recent = []
    for path in files[:limit]:
        data = _read_json(path) or {}
        recent.append({
            "issue_id": data.get("issue_id"),
            "source": data.get("source"),
            "severity": data.get("severity"),
            "symptom": str(data.get("symptom") or "")[:140],
            "receipt": _rel(path),
        })
    return {"count": len(files), "recent": recent}


def _failure_ingest() -> "dict[str, Any]":
    ledger = _read_json(REPORT_ROOT / "conical_failure_ingest_ledger.json") or {}
    ingested = ledger.get("ingested") if isinstance(ledger.get("ingested"), dict) else {}
    return {"ingested_jobs": len(ingested)}


def _self_model() -> "dict[str, Any]":
    state = _read_json(SELF_MODEL_STATE)
    if not state:
        return {"present": False}
    age_minutes = None
    try:
        observed = str(state.get("observed_at_utc") or "").replace("Z", "+00:00")
        age_minutes = int((datetime.now(timezone.utc)
                           - datetime.fromisoformat(observed)).total_seconds() // 60)
    except (ValueError, TypeError):
        pass
    return {
        "present": True,
        "state_revision": state.get("state_revision"),
        "observed_at_utc": state.get("observed_at_utc"),
        "age_minutes": age_minutes,
        "operational_ready": state.get("operational_ready") is True,
    }


def _primary_goal_completion() -> "dict[str, Any]":
    """Refresh the ten-criterion owner-goal audit for UI projection."""
    try:
        from engel_primary_goal_completion_audit import build_audit, write_audit

        audit = build_audit(PRIMARY_GOAL_ROOT)
        path = write_audit(audit, PRIMARY_GOAL_ROOT)
        return {
            "present": True,
            "complete": audit.get("complete") is True,
            "criteria_total": int(audit.get("criteria_total") or 0),
            "criteria_proven": int(audit.get("criteria_proven") or 0),
            "criteria_not_proven": int(audit.get("criteria_not_proven") or 0),
            "checks": audit.get("checks") or [],
            "receipt": _rel(path),
        }
    except Exception as exc:
        return {
            "present": False,
            "complete": False,
            "criteria_total": 10,
            "criteria_proven": 0,
            "criteria_not_proven": 10,
            "error": str(exc)[:200],
        }


def _pipes() -> "list[dict[str, Any]]":
    out = [dict(p) for p in POLICY_OFF_PIPES]
    if os.environ.get("ENGEL_LOOP_STREAM_SKIP_PORT_PROBES") == "1":
        for name, ports in PIPE_PORTS:
            out.append({"pipe": name, "port": ports[0], "status": "not_probed"})
        return out
    for name, ports in PIPE_PORTS:
        entry: dict[str, Any] = {"pipe": name, "status": "down"}
        probe_failures: list[dict[str, Any]] = []
        for port in ports:
            for route in ("/health", "/status"):
                endpoint = f"http://127.0.0.1:{port}{route}"
                try:
                    with urllib.request.urlopen(endpoint, timeout=2.5) as resp:
                        body = json.loads(resp.read().decode("utf-8", errors="replace"))
                        entry["status"] = "up" if body.get("ok") else "responding_not_ok"
                        entry["port"] = port
                        entry["route"] = route
                        if entry["status"] == "up":
                            entry["healthy_endpoint"] = endpoint
                        break
                except Exception as exc:
                    probe_failures.append({
                        "port": port,
                        "route": route,
                        "error": str(exc)[:80],
                    })
            if entry["status"] == "up":
                break
        if probe_failures:
            entry["probe_failures"] = probe_failures
        if entry["status"] == "down" and probe_failures:
            entry["error"] = probe_failures[-1]["error"]
        out.append(entry)
    return out


PERSISTENT_CHAT_MEMORY = ROOT / "memory" / "persistent_chat" / "ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl"
NT_TAIL_RECORDS = 400


def _nt_telemetry() -> "dict[str, Any]":
    """(2026-07-26) Neuron-transfer visibility: depth histogram, escalation
    counts, and quick-lane confidence stats from the newest persistent chat
    memory records. Read-only; degrades honestly when the file is absent."""
    if not PERSISTENT_CHAT_MEMORY.is_file():
        return {"present": False}
    rows: list[dict[str, Any]] = []
    try:
        with PERSISTENT_CHAT_MEMORY.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue
    except Exception as exc:
        return {"present": False, "error": str(exc)[:120]}
    tail = rows[-NT_TAIL_RECORDS:]
    depth_hist: dict[str, int] = {}
    esc_from: dict[str, int] = {}
    confs: list[float] = []
    escalated = 0
    for r in tail:
        d = r.get("activation_depth")
        depth_hist[str(d)] = depth_hist.get(str(d), 0) + 1
        if r.get("escalated_from") is not None:
            esc_from[str(r["escalated_from"])] = esc_from.get(str(r["escalated_from"]), 0) + 1
        if r.get("quick_lane_escalated") is True:
            escalated += 1
        c = r.get("quick_lane_confidence")
        if isinstance(c, (int, float)):
            confs.append(float(c))
    confs.sort()
    n = len(confs)
    return {
        "present": True,
        "tail_records": len(tail),
        "depth_histogram": depth_hist,
        "labelled_fraction": round(
            sum(v for k, v in depth_hist.items() if k != "None") / max(1, len(tail)), 3),
        "escalations_by_origin": esc_from,
        "quick_lane_escalated_count": escalated,
        "quick_lane_confidence": {
            "count": n,
            "min": confs[0] if n else None,
            "median": confs[n // 2] if n else None,
            "p25": confs[n // 4] if n else None,
        },
    }


def _broker() -> "dict[str, Any]":
    try:
        from engel_device_broker import broker_decision

        decision = broker_decision()
        return {
            "available": True,
            "eligible_device_ids": decision.get("selected_device_ids"),
            "candidate_count": decision.get("candidate_count"),
            "forbidden_devices": decision.get("forbidden_devices"),
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)[:160]}


def _backlog_driver() -> "dict[str, Any]":
    """(2026-07-28) The baked-in movement lane: status counts via the driver's
    own reader plus the newest driver receipt, so the Tasks panel shows the
    backlog actually moving (or honestly not moving)."""
    section: "dict[str, Any]" = {}
    try:
        from engel_self_upgrade_backlog_driver import backlog_status

        status = backlog_status(REPORT_ROOT)
        section["counts"] = status.get("counts")
        section["open_top"] = [
            {
                "issue_id": row.get("issue_id"),
                "severity": row.get("severity"),
                "symptom": str(row.get("symptom") or "")[:100],
            }
            for row in (status.get("open_issues") or [])[:3]
        ]
    except Exception as exc:
        section["error"] = str(exc)[:160]
    receipts = _newest(REPORT_ROOT / "receipts", "ENGEL_BACKLOG_DRIVER_*.json", 5)
    if receipts:
        latest = _read_json(receipts[0]) or {}
        section["last_run"] = {
            "created_at_utc": latest.get("created_at_utc"),
            "command": latest.get("command"),
            "groom_actions": len(latest.get("groom_actions") or []),
            "draft_outcomes": [
                str(row.get("outcome") or "")
                for row in (latest.get("draft_results") or [])
            ],
            "backlog_after": latest.get("backlog_after"),
            "receipt": _rel(receipts[0]),
        }
    return section


def build_state() -> "dict[str, Any]":
    return {
        "schema": "ENGEL_SELF_UPGRADE_LOOP_STREAM_V1",
        "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
        "generated_at_utc": _now(),
        "cycles": _cycles(),
        "quorum": _latest_decision(REPORT_ROOT, "self_patch_quorum_*.json", "decision"),
        "post_deploy": _latest_decision(REPORT_ROOT, "post_deploy_gate_*.json", "decision"),
        "issues": _issues(),
        "failure_ingest": _failure_ingest(),
        "self_model": _self_model(),
        "primary_goal_completion": _primary_goal_completion(),
        "pipes": _pipes(),
        "broker": _broker(),
        "nt": _nt_telemetry(),
        "backlog_driver": _backlog_driver(),
        "actor_note": "observe/project only: reads receipts, probes loopback pipe health; "
                      "no dispatch, no mutation, no trusted-memory write",
    }


def snapshot_to_stream() -> "dict[str, Any]":
    state = build_state()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_PATH)
    return state


def _cli(argv: "list[str] | None" = None) -> int:
    import argparse

    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Engel self-upgrade loop stream (UI visibility snapshot)")
    parser.add_argument("command", choices=["snapshot", "print"], nargs="?", default="snapshot")
    args = parser.parse_args(argv)
    state = snapshot_to_stream() if args.command == "snapshot" else build_state()
    print(json.dumps({
        "ok": True,
        "state_path": _rel(STATE_PATH) if args.command == "snapshot" else None,
        "cycles": len(state["cycles"]),
        "issues": state["issues"]["count"],
        "pipes_up": sum(1 for p in state["pipes"] if p.get("status") == "up"),
        "self_model_revision": state["self_model"].get("state_revision"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
