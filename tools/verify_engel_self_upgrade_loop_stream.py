#!/usr/bin/env python3
"""Verifier for the self-upgrade loop stream (engel_self_upgrade_loop_stream.py).

Proves the UI visibility snapshot is evidence-backed and observe-only:
  1. Snapshot writes an atomic state.json with the schema + every section.
  2. Cycle entries mirror REAL cycle receipt files (id/status/stage ticks).
  3. Quorum/post-deploy sections count real receipts and expose the latest
     decision with its receipt path.
  4. Issue intake is visible (count + recent with symptom).
  5. Empty evidence dirs degrade honestly (zero counts, self_model absent).
  6. Port probes are skippable for tests (ENGEL_LOOP_STREAM_SKIP_PORT_PROBES)
     and the grok chat pipe is reported policy_off, never probed.

Fixtures are temp-dir only; emits {"ok": bool,...}; exit 0 pass / 1 fail.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import engel_self_upgrade_loop_stream as stream  # noqa: E402

CHECKS: list[dict] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"check": name, "ok": bool(ok), "detail": detail})


def main() -> int:
    fx = ROOT / "runtime" / "temp" / f"loop_stream_verify_{os.getpid()}"
    fx_report = fx / "reports" / "self_upgrade"
    (fx_report / "cycles").mkdir(parents=True, exist_ok=True)
    (fx_report / "issues").mkdir(parents=True, exist_ok=True)

    saved = {
        "report_root": stream.REPORT_ROOT,
        "out_dir": stream.OUT_DIR,
        "state_path": stream.STATE_PATH,
        "self_model": stream.SELF_MODEL_STATE,
        "primary_goal_root": stream.PRIMARY_GOAL_ROOT,
        "primary_goal_completion": stream.PRIMARY_GOAL_COMPLETION,
        "chat_memory": stream.PERSISTENT_CHAT_MEMORY,
        "env": os.environ.get("ENGEL_LOOP_STREAM_SKIP_PORT_PROBES"),
    }
    stream.REPORT_ROOT = fx_report
    stream.OUT_DIR = fx_report / "loop_stream"
    stream.STATE_PATH = stream.OUT_DIR / "state.json"
    stream.SELF_MODEL_STATE = fx / "self_model.json"
    stream.PRIMARY_GOAL_ROOT = fx
    stream.PRIMARY_GOAL_COMPLETION = fx_report / "goal_completion" / "latest.json"
    stream.PERSISTENT_CHAT_MEMORY = fx / "chat_memory.jsonl"
    os.environ["ENGEL_LOOP_STREAM_SKIP_PORT_PROBES"] = "1"

    try:
        # 5: empty evidence dirs degrade honestly --------------------------------
        state = stream.build_state()
        record("empty evidence dirs degrade honestly",
               state["cycles"] == [] and state["issues"]["count"] == 0
               and state["self_model"] == {"present": False}
               and state["quorum"]["count"] == 0,
               "")

        # fixtures ---------------------------------------------------------------
        (fx_report / "cycles" / "engel_cycle_fix1.json").write_text(json.dumps({
            "cycle_id": "engel_cycle_fix1", "mode": "execute",
            "final_status": "upgraded_verified", "started_at_utc": "2026-07-26T00:00:00Z",
            "stages": [{"stage": "intake", "ok": True}, {"stage": "quorum", "ok": True}],
        }), encoding="utf-8")
        (fx_report / "self_patch_quorum_1.json").write_text(json.dumps({
            "decision": "apply_authorized", "decided_at_utc": "2026-07-26T00:01:00Z"}), encoding="utf-8")
        (fx_report / "post_deploy_gate_1.json").write_text(json.dumps({
            "decision": "rolled_back", "created_at_utc": "2026-07-26T00:02:00Z"}), encoding="utf-8")
        (fx_report / "issues" / "engel_issue_fix1.json").write_text(json.dumps({
            "issue_id": "engel_issue_fix1", "source": "meeting_room", "severity": "medium",
            "symptom": "conical job x failed worker convergence"}), encoding="utf-8")
        (fx / "self_model.json").write_text(json.dumps({
            "state_revision": 7, "observed_at_utc": "2026-07-26T00:00:00Z",
            "operational_ready": False}), encoding="utf-8")

        result = stream.snapshot_to_stream()
        on_disk = json.loads(stream.STATE_PATH.read_text(encoding="utf-8"))

        # 1: schema + sections + atomic write ------------------------------------
        record("snapshot writes atomic state.json with schema + all sections",
               on_disk.get("schema") == "ENGEL_SELF_UPGRADE_LOOP_STREAM_V1"
               and all(k in on_disk for k in
                       ("cycles", "quorum", "post_deploy", "issues", "failure_ingest",
                        "self_model", "primary_goal_completion", "pipes", "broker",
                        "actor_note"))
               and not stream.STATE_PATH.with_suffix(".tmp").exists(),
               str(sorted(on_disk.keys())[:6]))

        # 2: cycles mirror real receipts -----------------------------------------
        cyc = on_disk["cycles"][0] if on_disk["cycles"] else {}
        record("cycle entries mirror the real cycle receipts",
               cyc.get("cycle_id") == "engel_cycle_fix1"
               and cyc.get("final_status") == "upgraded_verified"
               and cyc.get("stages") == [{"stage": "intake", "ok": True},
                                         {"stage": "quorum", "ok": True}],
               str(cyc)[:120])

        # 3: quorum + post-deploy latest decisions -------------------------------
        record("quorum and post-deploy sections expose the latest real decisions",
               on_disk["quorum"]["count"] == 1
               and on_disk["quorum"]["latest"]["decision"] == "apply_authorized"
               and on_disk["post_deploy"]["latest"]["decision"] == "rolled_back"
               and on_disk["post_deploy"]["latest"]["receipt"], "")

        # 4: issue intake visible -------------------------------------------------
        record("issue intake is visible with symptom text",
               on_disk["issues"]["count"] == 1
               and on_disk["issues"]["recent"][0]["issue_id"] == "engel_issue_fix1"
               and "failed worker" in on_disk["issues"]["recent"][0]["symptom"], "")

        # self-model freshness visible -------------------------------------------
        record("self-model revision and age are visible",
               on_disk["self_model"]["state_revision"] == 7
               and isinstance(on_disk["self_model"]["age_minutes"], int), "")

        # NT telemetry visible (2026-07-26 neuro audit) ---------------------------
        (fx / "chat_memory.jsonl").write_text(
            "\n".join(json.dumps(r) for r in [
                {"activation_depth": 2, "escalated_from": 1,
                 "quick_lane_escalated": True, "quick_lane_confidence": 0.5},
                {"activation_depth": 1, "quick_lane_confidence": 0.9,
                 "quick_lane_escalated": False},
                {"activation_depth": 0},
                {"activation_depth": 3, "escalated_from": 2},
            ]) + "\n", encoding="utf-8")
        nt = stream._nt_telemetry()
        record("NT telemetry aggregates depth/escalation/confidence from real records",
               nt["present"] is True and nt["depth_histogram"] == {"2": 1, "1": 1, "0": 1, "3": 1}
               and nt["escalations_by_origin"] == {"1": 1, "2": 1}
               and nt["quick_lane_escalated_count"] == 1
               and nt["quick_lane_confidence"]["count"] == 2
               and nt["labelled_fraction"] == 1.0,
               str(nt)[:140])
        stream.PERSISTENT_CHAT_MEMORY = fx / "missing.jsonl"
        record("NT telemetry degrades honestly when memory file is absent",
               stream._nt_telemetry() == {"present": False}, "")
        stream.PERSISTENT_CHAT_MEMORY = fx / "chat_memory.jsonl"

        # 6: probes skipped + policy_off honest ----------------------------------
        pipes = on_disk["pipes"]
        record("port probes skippable and grok chat reported policy_off",
               any(p.get("status") == "policy_off" and p.get("pipe") == "grok_chat" for p in pipes)
               and all(p.get("status") in {"policy_off", "not_probed"} for p in pipes),
               str([p.get("status") for p in pipes]))

        # A failed first endpoint must not leak a stale error onto a healthy pipe.
        saved_ports = stream.PIPE_PORTS
        saved_urlopen = stream.urllib.request.urlopen

        class FakeProbeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps({"ok": True}).encode("utf-8")

        def fake_urlopen(url, timeout):
            del timeout
            if ":31001/" in url:
                raise OSError("connection refused")
            return FakeProbeResponse()

        try:
            os.environ.pop("ENGEL_LOOP_STREAM_SKIP_PORT_PROBES", None)
            stream.PIPE_PORTS = (("alternate_endpoint", (31001, 31002)),)
            stream.urllib.request.urlopen = fake_urlopen
            alternate = next(
                p for p in stream._pipes()
                if p.get("pipe") == "alternate_endpoint"
            )
        finally:
            stream.PIPE_PORTS = saved_ports
            stream.urllib.request.urlopen = saved_urlopen
            os.environ["ENGEL_LOOP_STREAM_SKIP_PORT_PROBES"] = "1"
        record("healthy alternate endpoint clears stale top-level errors",
               alternate.get("status") == "up"
               and alternate.get("port") == 31002
               and alternate.get("route") == "/health"
               and "error" not in alternate
               and len(alternate.get("probe_failures") or []) == 2,
               str(alternate)[:180])
        record("state is observe-only by contract",
               "no dispatch" in on_disk["actor_note"] and result.get("schema") == on_disk["schema"], "")
    finally:
        stream.REPORT_ROOT = saved["report_root"]
        stream.OUT_DIR = saved["out_dir"]
        stream.STATE_PATH = saved["state_path"]
        stream.SELF_MODEL_STATE = saved["self_model"]
        stream.PRIMARY_GOAL_ROOT = saved["primary_goal_root"]
        stream.PRIMARY_GOAL_COMPLETION = saved["primary_goal_completion"]
        stream.PERSISTENT_CHAT_MEMORY = saved["chat_memory"]
        if saved["env"] is None:
            os.environ.pop("ENGEL_LOOP_STREAM_SKIP_PORT_PROBES", None)
        else:
            os.environ["ENGEL_LOOP_STREAM_SKIP_PORT_PROBES"] = saved["env"]
        shutil.rmtree(fx, ignore_errors=True)

    failed = [c for c in CHECKS if not c["ok"]]
    receipt = {
        "schema": "engel_self_upgrade_loop_stream_verifier_v1",
        "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
        "ok": not failed,
        "checks_total": len(CHECKS),
        "checks_passed": sum(1 for c in CHECKS if c["ok"]),
        "checks_failed": len(failed),
        "failed_checks": failed,
        "checks": CHECKS,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
