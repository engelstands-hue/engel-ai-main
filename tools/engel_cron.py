#!/usr/bin/env python3
"""
Engel AI Main — cron / scheduled agent turns.

Ported from OpenClaw (MIT) cron subsystem (dist/store-*.d.ts CronJob/CronSchedule/
CronPayload + DESIGN-cron-on-exit.md). A durable job store fires work on a
schedule:

  schedule.kind  : at (once) | every (interval s) | cron (5-field + tz-naive) | on-exit
  payload.kind   : agentTurn (a prompt run through the multi-AI failover loop)
                 | command   (raw argv subprocess)
                 | systemEvent (a logged wake message)
  wake           : now | next-heartbeat

The "on-exit" kind is OpenClaw's durable "wake me when X finishes, then keep
going" primitive: watch a command/process, and fire the payload once when it
exits (one-shot, persisted fail-closed before firing so a restart can't double-
fire). agentTurn payloads route through engel_agent_failover_loop, so a scheduled
job automatically escalates across every AI Engel has.

Reimplemented natively in Python; MIT-attributed. No OpenClaw runtime dependency.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

CRON_DIR = ROOT / "runtime" / "cron"
STORE_PATH = CRON_DIR / "engel_cron_jobs.json"
RUNS_DIR = CRON_DIR / "runs"
LOG_PATH = CRON_DIR / "engel_cron.log"

SCHEDULE_KINDS = ("at", "every", "cron", "on-exit")
PAYLOAD_KINDS = ("agentTurn", "command", "systemEvent")
WAKE_MODES = ("now", "next-heartbeat")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(msg: str) -> None:
    try:
        CRON_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(f"[{_iso()}] {msg}\n")
    except Exception:
        pass


# --- basic 5-field cron matcher: "min hour dom month dow" with * , */n , a-b , a,b,c ---
def _cron_field_matches(spec: str, value: int, lo: int, hi: int) -> bool:
    spec = spec.strip()
    if spec == "*":
        return True
    for part in spec.split(","):
        part = part.strip()
        if part.startswith("*/"):
            try:
                step = int(part[2:])
                if step > 0 and (value - lo) % step == 0:
                    return True
            except ValueError:
                pass
        elif "-" in part:
            try:
                a, b = (int(x) for x in part.split("-", 1))
                if a <= value <= b:
                    return True
            except ValueError:
                pass
        else:
            try:
                if int(part) == value:
                    return True
            except ValueError:
                pass
    return False


def _cron_matches(expr: str, dt: datetime) -> bool:
    fields = expr.split()
    if len(fields) != 5:
        return False
    mn, hr, dom, mon, dow = fields
    return (
        _cron_field_matches(mn, dt.minute, 0, 59)
        and _cron_field_matches(hr, dt.hour, 0, 23)
        and _cron_field_matches(dom, dt.day, 1, 31)
        and _cron_field_matches(mon, dt.month, 1, 12)
        and _cron_field_matches(dow, dt.weekday() + 1 if dt.weekday() < 6 else 0, 0, 7)  # Mon=1..Sun=0/7
    )


@dataclass
class CronJob:
    id: str
    name: str
    schedule: dict            # {kind, at_ms?/every_s?/cron?/exit_command?}
    payload: dict             # {kind, prompt?/argv?/text?}
    chain: Optional[list] = None   # failover chain override for agentTurn
    enabled: bool = True
    wake: str = "next-heartbeat"
    state: dict = field(default_factory=lambda: {
        "next_run_ms": 0, "last_run_ms": 0, "consecutive_errors": 0, "runs": 0, "fired": False,
    })


class CronStore:
    def __init__(self, path: Path = STORE_PATH):
        self.path = path
        self.jobs: dict[str, CronJob] = {}
        self.load()

    def load(self) -> None:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                for j in data.get("jobs", []):
                    self.jobs[j["id"]] = CronJob(**j)
        except Exception as exc:
            _log(f"store load error: {exc}")

    def save(self) -> None:
        CRON_DIR.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"schema": "engel_cron_store_v1",
                                   "jobs": [asdict(j) for j in self.jobs.values()]}, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def add(self, job: CronJob) -> None:
        self.jobs[job.id] = job
        self.save()

    def remove(self, job_id: str) -> bool:
        if job_id in self.jobs:
            del self.jobs[job_id]
            self.save()
            return True
        return False


def _due(job: CronJob, now_ms: int) -> bool:
    if not job.enabled:
        return False
    kind = job.schedule.get("kind")
    st = job.state
    if kind == "at":
        return not st.get("fired") and now_ms >= int(job.schedule.get("at_ms") or 0)
    if kind == "every":
        interval = int(job.schedule.get("every_s") or 0) * 1000
        if interval <= 0:
            return False
        return now_ms >= (st.get("last_run_ms") or 0) + interval
    if kind == "cron":
        # Catch-up semantics (2026-08-16): fire when the most recent matching
        # minute within the last 24h has not been served yet. The original
        # exact-minute match required a tick to land INSIDE the scheduled minute,
        # and the stack controller's sparse one-pass heartbeat never did - the
        # goal planner's daily tick sat registered for six days with zero runs.
        # Still at most once per matching occurrence.
        occurrence = _latest_cron_occurrence(str(job.schedule.get("cron") or ""))
        if occurrence is None:
            return False
        return st.get("last_cron_minute") != occurrence
    return False  # on-exit is handled by the watcher, not the tick


def _latest_cron_occurrence(expr: str, now_dt: "datetime | None" = None) -> "str | None":
    """Minute-key of the most recent minute matching expr within the last 24h."""
    if not expr:
        return None
    probe = (now_dt or datetime.now()).replace(second=0, microsecond=0)
    for _ in range(24 * 60):
        if _cron_matches(expr, probe):
            return probe.strftime("%Y%m%d%H%M")
        probe -= timedelta(minutes=1)
    return None


def fire(job: CronJob) -> dict:
    """Execute a job's payload. Returns a run receipt."""
    kind = job.payload.get("kind")
    started = time.perf_counter()
    receipt: dict[str, Any] = {"job_id": job.id, "name": job.name, "payload_kind": kind, "at_utc": _iso()}
    try:
        if kind == "agentTurn":
            import engel_agent_failover_loop as fl
            prompt = str(job.payload.get("prompt") or "")
            result = fl.run_with_failover(prompt, chain=job.chain, timeout_s=90, max_tokens=1024)
            receipt.update({"ok": result.ok, "reply": result.reply, "lane": result.lane,
                            "provider": result.provider, "iterations": result.iterations,
                            "elapsed_ms": result.elapsed_ms, "status": result.status})
        elif kind == "command":
            argv = job.payload.get("argv") or []
            cp = subprocess.run(argv, capture_output=True, text=True, timeout=int(job.payload.get("timeout") or 300), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            receipt.update({"ok": cp.returncode == 0, "returncode": cp.returncode,
                            "stdout_tail": (cp.stdout or "")[-1200:], "stderr_tail": (cp.stderr or "")[-800:]})
        elif kind == "systemEvent":
            receipt.update({"ok": True, "wake_text": str(job.payload.get("text") or ""), "note": "system wake event logged"})
        else:
            receipt.update({"ok": False, "error": f"unknown payload kind: {kind}"})
    except Exception as exc:
        receipt.update({"ok": False, "error": str(exc)[:400]})
    receipt["run_ms"] = int((time.perf_counter() - started) * 1000)
    # durable run receipt
    try:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        (RUNS_DIR / f"{job.id}_{stamp}.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    except Exception:
        pass
    _log(f"fired {job.name} ({kind}) ok={receipt.get('ok')} {receipt.get('status','')}")
    return receipt


def tick(store: CronStore) -> list[dict]:
    """One scheduler tick: run every due at/every/cron job, update state, persist."""
    now = _now_ms()
    fired_receipts = []
    for job in list(store.jobs.values()):
        if not _due(job, now):
            continue
        receipt = fire(job)
        st = job.state
        st["last_run_ms"] = now
        st["runs"] = int(st.get("runs", 0)) + 1
        st["consecutive_errors"] = 0 if receipt.get("ok") else int(st.get("consecutive_errors", 0)) + 1
        if job.schedule.get("kind") == "at":
            st["fired"] = True
            job.enabled = False
        if job.schedule.get("kind") == "cron":
            # record the SERVED occurrence, not "now": with catch-up in _due, a
            # now-stamp would never equal the occurrence key and the job would
            # re-fire on every tick until the next real occurrence.
            st["last_cron_minute"] = _latest_cron_occurrence(
                str(job.schedule.get("cron") or "")
            ) or datetime.now().strftime("%Y%m%d%H%M")
        store.save()
        fired_receipts.append(receipt)
    return fired_receipts


def watch_exit(store: CronStore, job_id: str) -> dict:
    """OpenClaw on-exit: spawn/await the job's exit_command, then fire the payload
    ONCE. Persisted fail-closed (mark fired before firing) so a restart can't
    double-fire."""
    job = store.jobs.get(job_id)
    if not job or job.schedule.get("kind") != "on-exit":
        return {"ok": False, "error": "not an on-exit job"}
    if job.state.get("fired"):
        return {"ok": False, "error": "already fired"}
    cmd = job.schedule.get("exit_command") or []
    _log(f"on-exit watcher armed for {job.name}: {cmd}")
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) if cmd else None
        exit_code = cp.returncode if cp else 0
    except Exception as exc:
        exit_code = -1
        _log(f"on-exit watch error {job.name}: {exc}")
    # fail-closed: persist fired BEFORE firing the payload
    job.state["fired"] = True
    job.enabled = False
    store.save()
    receipt = fire(job)
    receipt["watched_exit_code"] = exit_code
    return receipt


# --- CLI --------------------------------------------------------------------
def _cli(argv: Optional[list[str]] = None) -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Engel cron — scheduled agent turns (ported from OpenClaw).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add")
    a.add_argument("--name", required=True)
    a.add_argument("--schedule", required=True, help="at:<iso>|every:<seconds>|cron:<m h dom mon dow>|on-exit:<cmd...>")
    a.add_argument("--payload", required=True, help="agentTurn:<prompt>|command:<argv...>|systemEvent:<text>")
    a.add_argument("--chain", default="", help="failover chain override for agentTurn")

    sub.add_parser("list")
    r = sub.add_parser("remove"); r.add_argument("id")
    rn = sub.add_parser("run"); rn.add_argument("id")
    sub.add_parser("tick")
    d = sub.add_parser("daemon"); d.add_argument("--interval", type=int, default=30)
    w = sub.add_parser("watch-exit"); w.add_argument("id")
    args = ap.parse_args(argv)
    store = CronStore()

    if args.cmd == "add":
        skind, _, sval = args.schedule.partition(":")
        pkind, _, pval = args.payload.partition(":")
        schedule: dict[str, Any] = {"kind": skind}
        if skind == "at":
            schedule["at_ms"] = int(datetime.fromisoformat(sval).timestamp() * 1000)
        elif skind == "every":
            schedule["every_s"] = int(sval)
        elif skind == "cron":
            schedule["cron"] = sval
        elif skind == "on-exit":
            schedule["exit_command"] = sval.split()
        else:
            print("bad schedule kind"); return 2
        payload: dict[str, Any] = {"kind": pkind}
        if pkind == "agentTurn":
            payload["prompt"] = pval
        elif pkind == "command":
            payload["argv"] = pval.split()
        elif pkind == "systemEvent":
            payload["text"] = pval
        else:
            print("bad payload kind"); return 2
        job = CronJob(id="cron-" + uuid.uuid4().hex[:8], name=args.name, schedule=schedule, payload=payload,
                      chain=[c.strip() for c in args.chain.split(",") if c.strip()] or None)
        store.add(job)
        print(f"added {job.id}: {job.name} [{skind}] -> {pkind}")
    elif args.cmd == "list":
        if not store.jobs:
            print("(no cron jobs)")
        for j in store.jobs.values():
            print(f"  {j.id}  {'ON ' if j.enabled else 'off'}  [{j.schedule.get('kind')}] -> {j.payload.get('kind')}  runs={j.state.get('runs')}  {j.name}")
    elif args.cmd == "remove":
        print("removed" if store.remove(args.id) else "not found")
    elif args.cmd == "run":
        job = store.jobs.get(args.id)
        print(json.dumps(fire(job), indent=2) if job else "not found")
    elif args.cmd == "tick":
        fired = tick(store)
        print(f"tick fired {len(fired)} job(s)")
        for r in fired:
            print(f"  {r.get('name')} ok={r.get('ok')} {r.get('status','')}")
    elif args.cmd == "watch-exit":
        print(json.dumps(watch_exit(store, args.id), indent=2))
    elif args.cmd == "daemon":
        print(f"engel cron daemon: tick every {args.interval}s (Ctrl-C to stop)")
        while True:
            try:
                tick(store)
                store.load()  # pick up external add/remove
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("stopped"); break
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
