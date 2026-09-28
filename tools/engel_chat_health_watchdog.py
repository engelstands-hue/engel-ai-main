#!/usr/bin/env python3
"""Restart the Engel chat service when it stops answering /health.

Why this exists: on 2026-08-13 `engel-main-chat.service` was reported `active` by systemd
while the app showed "Chat unavailable". The process had not crashed - it had 85 threads,
13.1 GB RSS and 2d01h of CPU over 2d03h elapsed (one core pegged flat) with a FULL accept
queue, so `/health` never answered and `Restart=always` never fired. It sat like that for
two days. systemd cannot see this: a wedged process is still "running".

So we probe the thing users actually depend on - the HTTP endpoint - and restart on
repeated failure. A single slow probe is not enough (a long local-model turn can starve
the loop briefly), so a restart needs FAIL_THRESHOLD consecutive failures, and restarts
are rate limited so a service that is crash-looping is not hammered.

Run from a systemd timer:
    python engel_chat_health_watchdog.py --once

Offline checks (no network, no systemd):
    python engel_chat_health_watchdog.py --selftest
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

HEALTH_URL = os.environ.get("ENGEL_CHAT_WATCHDOG_URL", "http://127.0.0.1:8765/health")
SERVICE = os.environ.get("ENGEL_CHAT_WATCHDOG_SERVICE", "engel-main-chat.service")
STATE_PATH = Path(
    os.environ.get("ENGEL_CHAT_WATCHDOG_STATE", "/opt/engel/run/chat_health_watchdog.json")
)
PROBE_TIMEOUT = float(os.environ.get("ENGEL_CHAT_WATCHDOG_TIMEOUT_SECONDS", "20") or "20")
FAIL_THRESHOLD = int(os.environ.get("ENGEL_CHAT_WATCHDOG_FAIL_THRESHOLD", "3") or "3")
RESTART_COOLDOWN = float(
    os.environ.get("ENGEL_CHAT_WATCHDOG_RESTART_COOLDOWN_SECONDS", "900") or "900"
)
# Warn only, and measured on RssAnon - NOT VmRSS. This service mmaps a multi-GB GGUF, so
# VmRSS reads ~33 GB of which ~17 GB is RssFile: reclaimable page cache, not a leak.
# Measured healthy on 2026-08-13: VmRSS 33.6 GB / RssAnon 15.9 GB / 72-90 threads, on a
# 40 GB container with ~23 GB available. Mild thread counts still do not separate wedge
# from healthy. After the 2026-09-10 OOM (~997–1184 threads, ~26–32 GiB anon), extreme
# thread/anon growth IS a restart trigger — do not wait for the kernel OOM-killer.
RSS_ANON_WARN_KB = int(
    os.environ.get("ENGEL_CHAT_WATCHDOG_RSS_ANON_WARN_KB", "18874368") or "18874368"
)  # 18 GiB
RSS_ANON_HARD_KB = int(
    os.environ.get("ENGEL_CHAT_WATCHDOG_RSS_ANON_HARD_KB", "20971520") or "20971520"
)  # 20 GiB — restart before ~26–32 GiB OOM
THREADS_HARD = int(os.environ.get("ENGEL_CHAT_WATCHDOG_THREADS_HARD", "350") or "350")
PRESSURE_RESTART_COOLDOWN = float(
    os.environ.get("ENGEL_CHAT_WATCHDOG_PRESSURE_RESTART_COOLDOWN_SECONDS", "1800") or "1800"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def log(message: str) -> None:
    print(f"[chat-watchdog] {message}", flush=True)


def read_state() -> dict[str, Any]:
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_state(state: dict[str, Any]) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        log(f"could not persist state: {exc}")


def probe_health(url: str = HEALTH_URL, timeout: float = PROBE_TIMEOUT) -> tuple[bool, str]:
    """True only when the endpoint answers with ok-ish JSON inside the timeout."""
    try:
        req = request.Request(url, headers={"Accept": "application/json"})
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            if resp.status != 200:
                return False, f"http {resp.status}"
    except error.HTTPError as exc:
        return False, f"http {exc.code}"
    except Exception as exc:  # timeout, refused, reset
        return False, f"unreachable: {exc}"
    body = raw.strip()
    if not body:
        return False, "empty body"
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return False, "non-json body"
    if isinstance(payload, dict) and payload.get("ok") is False:
        return False, "health reports ok=false"
    return True, "ok"


def should_restart(
    *,
    consecutive_failures: int,
    threshold: int,
    last_restart_epoch: float,
    now_epoch: float,
    cooldown: float,
) -> tuple[bool, str]:
    """Pure decision so the policy can be tested without touching systemd."""
    if consecutive_failures < threshold:
        return False, f"{consecutive_failures}/{threshold} consecutive failures"
    if last_restart_epoch and (now_epoch - last_restart_epoch) < cooldown:
        waited = int(now_epoch - last_restart_epoch)
        return False, f"cooldown active ({waited}s of {int(cooldown)}s since last restart)"
    return True, "threshold reached and cooldown clear"


def service_pid(service: str = SERVICE) -> int:
    try:
        out = subprocess.run(
            ["systemctl", "show", service, "-p", "MainPID", "--value"],
            capture_output=True, text=True, timeout=20, check=False,
        )
        return int((out.stdout or "0").strip() or 0)
    except Exception:
        return 0


def process_pressure(pid: int) -> dict[str, int]:
    """Memory/thread counters. RssAnon is the meaningful one - see RSS_ANON_WARN_KB."""
    stats = {"rss_kb": 0, "rss_anon_kb": 0, "threads": 0}
    if pid <= 0:
        return stats
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                stats["rss_kb"] = int(line.split()[1])
            elif line.startswith("RssAnon:"):
                stats["rss_anon_kb"] = int(line.split()[1])
            elif line.startswith("Threads:"):
                stats["threads"] = int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return stats


def restart_service(service: str = SERVICE) -> tuple[bool, str]:
    try:
        out = subprocess.run(
            ["systemctl", "restart", service],
            capture_output=True, text=True, timeout=180, check=False,
        )
    except Exception as exc:
        return False, str(exc)
    if out.returncode != 0:
        return False, (out.stderr or out.stdout or "restart failed").strip()[:300]
    return True, "restarted"


def should_restart_for_pressure(
    *,
    rss_anon_kb: int,
    threads: int,
    last_pressure_restart_epoch: float,
    now_epoch: float,
    cooldown: float = PRESSURE_RESTART_COOLDOWN,
    anon_hard_kb: int = RSS_ANON_HARD_KB,
    threads_hard: int = THREADS_HARD,
) -> tuple[bool, str]:
    """Restart on extreme growth even while /health still answers."""
    if last_pressure_restart_epoch and (now_epoch - last_pressure_restart_epoch) < cooldown:
        return False, "pressure cooldown active"
    if rss_anon_kb >= anon_hard_kb:
        return True, f"rss_anon_hard anon_mb={rss_anon_kb // 1024}"
    if threads >= threads_hard:
        return True, f"threads_hard threads={threads}"
    return False, "pressure ok"


def run_once() -> int:
    state = read_state()
    now = time.time()
    healthy, detail = probe_health()

    pid = service_pid()
    pressure = process_pressure(pid)
    if pressure["rss_anon_kb"] >= RSS_ANON_WARN_KB:
        log(
            f"WARNING private memory high: anon={pressure['rss_anon_kb'] // 1024} MB "
            f"(vmrss={pressure['rss_kb'] // 1024} MB incl. mmapped model) "
            f"threads={pressure['threads']} pid={pid} - headroom is going"
        )
    if pressure["threads"] >= max(120, THREADS_HARD // 2):
        log(
            f"WARNING thread growth: threads={pressure['threads']} "
            f"(hard={THREADS_HARD}) pid={pid}"
        )

    pressure_restart, pressure_reason = should_restart_for_pressure(
        rss_anon_kb=int(pressure["rss_anon_kb"] or 0),
        threads=int(pressure["threads"] or 0),
        last_pressure_restart_epoch=float(state.get("last_pressure_restart_epoch") or 0.0),
        now_epoch=now,
    )
    if pressure_restart:
        log(
            f"restarting {SERVICE} for growth circuit-breaker: {pressure_reason} "
            f"(pid={pid} healthy={healthy} detail={detail})"
        )
        ok, detail_restart = restart_service()
        state["last_pressure_restart_epoch"] = now
        state["last_restart_epoch"] = now
        state["last_restart_utc"] = utc_now()
        state["last_restart_ok"] = ok
        state["last_restart_detail"] = f"pressure:{pressure_reason}:{detail_restart}"
        state["restart_count"] = int(state.get("restart_count") or 0) + 1
        state["consecutive_failures"] = 0
        state["last_rss_kb"] = pressure["rss_kb"]
        state["last_rss_anon_kb"] = pressure["rss_anon_kb"]
        state["last_threads"] = pressure["threads"]
        write_state(state)
        if not ok:
            log(f"pressure restart FAILED: {detail_restart}")
            return 2
        time.sleep(15)
        healthy_after, detail_after = probe_health()
        log(
            f"post-pressure-restart health: "
            f"{'OK' if healthy_after else 'STILL FAILING'} ({detail_after})"
        )
        return 0 if healthy_after else 2

    if healthy:
        if int(state.get("consecutive_failures") or 0):
            log(f"recovered after {state.get('consecutive_failures')} failed probe(s)")
        state.update(
            {
                "consecutive_failures": 0,
                "last_ok_utc": utc_now(),
                "last_detail": detail,
                "last_rss_kb": pressure["rss_kb"],
                "last_rss_anon_kb": pressure["rss_anon_kb"],
                "last_threads": pressure["threads"],
            }
        )
        write_state(state)
        return 0

    failures = int(state.get("consecutive_failures") or 0) + 1
    state["consecutive_failures"] = failures
    state["last_fail_utc"] = utc_now()
    state["last_detail"] = detail
    log(f"health probe FAILED ({detail}) - {failures} consecutive")

    decision, reason = should_restart(
        consecutive_failures=failures,
        threshold=FAIL_THRESHOLD,
        last_restart_epoch=float(state.get("last_restart_epoch") or 0.0),
        now_epoch=now,
        cooldown=RESTART_COOLDOWN,
    )
    if not decision:
        log(f"not restarting: {reason}")
        write_state(state)
        return 1

    log(
        f"restarting {SERVICE}: {reason} "
        f"(pid={pid} rss={pressure['rss_kb'] // 1024} MB threads={pressure['threads']})"
    )
    ok, detail_restart = restart_service()
    state["last_restart_epoch"] = now
    state["last_restart_utc"] = utc_now()
    state["last_restart_ok"] = ok
    state["last_restart_detail"] = detail_restart
    state["restart_count"] = int(state.get("restart_count") or 0) + 1
    state["consecutive_failures"] = 0
    write_state(state)
    if not ok:
        log(f"restart FAILED: {detail_restart}")
        return 2
    time.sleep(15)
    healthy_after, detail_after = probe_health()
    log(f"post-restart health: {'OK' if healthy_after else 'STILL FAILING'} ({detail_after})")
    return 0 if healthy_after else 2


def selftest() -> int:
    checks: list[tuple[str, bool]] = []

    def check(name: str, condition: bool) -> None:
        checks.append((name, bool(condition)))

    ok, _ = should_restart(consecutive_failures=1, threshold=3,
                           last_restart_epoch=0, now_epoch=1000, cooldown=900)
    check("one failure does not restart", ok is False)

    ok, _ = should_restart(consecutive_failures=2, threshold=3,
                           last_restart_epoch=0, now_epoch=1000, cooldown=900)
    check("two failures do not restart", ok is False)

    ok, reason = should_restart(consecutive_failures=3, threshold=3,
                                last_restart_epoch=0, now_epoch=1000, cooldown=900)
    check("three failures restart", ok is True and "threshold" in reason)

    ok, reason = should_restart(consecutive_failures=5, threshold=3,
                                last_restart_epoch=900, now_epoch=1000, cooldown=900)
    check("cooldown blocks a rapid second restart", ok is False and "cooldown" in reason)

    ok, _ = should_restart(consecutive_failures=5, threshold=3,
                           last_restart_epoch=1, now_epoch=2000, cooldown=900)
    check("restart allowed once the cooldown lapses", ok is True)

    # the exact wedge signature: connection accepted, body never arrives -> empty body
    check("an empty body counts as unhealthy", probe_health("http://127.0.0.1:9", 0.2)[0] is False)

    # Healthy measured state must NOT warn: VmRSS is inflated by the mmapped GGUF, so a
    # threshold read off VmRSS would fire every two minutes and train everyone to ignore it.
    healthy_anon_kb = 15_859_400   # measured 2026-08-13 while /health was OK
    healthy_vmrss_kb = 33_609_052
    check("healthy private memory does not warn", healthy_anon_kb < RSS_ANON_WARN_KB)
    check("the warning is not read off VmRSS", healthy_vmrss_kb > RSS_ANON_WARN_KB)
    check("a genuine anon blowup would warn", 30_000_000 >= RSS_ANON_WARN_KB)
    ok_p, reason_p = should_restart_for_pressure(
        rss_anon_kb=healthy_anon_kb,
        threads=90,
        last_pressure_restart_epoch=0,
        now_epoch=1000,
    )
    check("healthy growth does not pressure-restart", ok_p is False)
    ok_p, reason_p = should_restart_for_pressure(
        rss_anon_kb=22_000_000,
        threads=90,
        last_pressure_restart_epoch=0,
        now_epoch=1000,
    )
    check("anon hard trips pressure restart", ok_p is True and "rss_anon_hard" in reason_p)
    ok_p, reason_p = should_restart_for_pressure(
        rss_anon_kb=healthy_anon_kb,
        threads=400,
        last_pressure_restart_epoch=0,
        now_epoch=1000,
    )
    check("thread hard trips pressure restart", ok_p is True and "threads_hard" in reason_p)
    ok_p, reason_p = should_restart_for_pressure(
        rss_anon_kb=22_000_000,
        threads=400,
        last_pressure_restart_epoch=900,
        now_epoch=1000,
        cooldown=1800,
    )
    check("pressure cooldown blocks rapid restart", ok_p is False and "cooldown" in reason_p)

    passed = sum(1 for _, good in checks if good)
    for name, good in checks:
        print(f"  [{'PASS' if good else 'FAIL'}] {name}")
    print(f"\n{passed}/{len(checks)} checks passed")
    return 0 if passed == len(checks) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="single probe pass (timer mode)")
    parser.add_argument("--selftest", action="store_true", help="offline policy checks")
    parser.add_argument("--status", action="store_true", help="print watchdog state and exit")
    args = parser.parse_args()

    if args.selftest:
        return selftest()
    if args.status:
        print(json.dumps(read_state(), indent=2, sort_keys=True))
        healthy, detail = probe_health()
        print(f"live probe: {'OK' if healthy else 'FAIL'} ({detail})")
        return 0
    return run_once()


if __name__ == "__main__":
    raise SystemExit(main())
