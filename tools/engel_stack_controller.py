#!/usr/bin/env python3
"""
Engel stack lifecycle controller (python port, 2026-07-09).

Runs every minute from the EngelStackController task UNDER PYTHONW via
engel_hidden_launch — a GUI-subsystem process, so unlike the old powershell.exe
action it can never flash a console window on each tick (the "window keeps
opening and shutting every minute" Joshua saw).

Behavior (same contract as Control-EngelStack.ps1, now superseded):
  EngelAIMain.exe running -> ensure every SERVICES task is running
  EngelAIMain.exe closed  -> stop them all (frees the ~4.7 GB GPU model)

All child commands (tasklist/schtasks) run with CREATE_NO_WINDOW so they are
window-free too. One log line per state change.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "runtime" / "logs" / "engel_stack_controller.log"
STATE = ROOT / "runtime" / "state" / "engel_stack_controller.json"
APP_DOWN_GRACE_SECONDS = 90
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW

# start order: tunnels + model first, then bridges/broker. stop order = reversed.
SERVICES = [
    "EngelRogGpuModelServer",
    "EngelRogGpuImageServer",  # sdxl-turbo GPU image lane :8931 (sequential offload, coexists with :8899)
    "EngelGpuTunnelSvc",       # wait-wrapper tunnel (replaces the broken conhost EngelRogGpuTunnel)
    "EngelChatLinkSvc",        # wait-wrapper chat+bridge link (replaces EngelMainServerPersistentLink)
    "EngelGeminiApiBridge",
    # EngelClaudeCliBridge removed — operator disconnected Claude from Engel
    "EngelCodexCliBridge",
    "EngelChatGptBrowserBridge",
    "EngelGrokImagineService",
    "EngelGrokHeadlessBroker",
    # ModelExpress metadata broker :24894. Registration needs the elevated setup
    # script, so until that runs task_state() reports "missing" and the loop below
    # skips it instead of retrying every tick.
    "EngelModelExpressServer",
]


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=30,
                          creationflags=NO_WINDOW)


STACK_PORTS = [8899, 8931, 24680, 24884, 24886, 24888, 24890, 24892, 24894]  # 24882 Claude bridge removed


def _force_kill_stack() -> tuple[int, int]:
    """schtasks /End sets a task to Ready but does NOT reliably kill the whole tree —
    the conhost->powershell->ssh tunnels orphan, and stray direct-python bridges from
    old wrapper launches never lived in a task at all. So on teardown we kill by PORT
    OWNERSHIP (whatever holds a stack port) plus any persistent CT246 ssh tunnel — this
    catches every mechanism. Safe: only runs when EngelAIMain.exe is closed; never kills
    this controller (own PID). Returns (killed, failed) — failed counts higher-integrity
    orphans (e.g. the old pid-8600 chat tunnel) that need an elevated sweep instead."""
    import os
    self_pid = os.getpid()
    ports = ",".join(str(p) for p in STACK_PORTS)
    # Two phases so a reconnect loop can't respawn its ssh after we kill it:
    #  1) kill the PARENTS — tunnel powershell loops + service/tunnel launchers (by
    #     signature), except this controller (own pid).
    #  2) kill the ssh tunnels + anything still holding a stack port.
    ps = (
        f"$self={self_pid};$k=0;$f=0;$ports=@({ports}); "
        # $_.ProcessId -ne $PID excludes the SWEEP powershell itself: its own
        # -Command string contains every signature below, so phase 1 used to
        # kill it mid-pipeline and phase 2 (ssh + port owners) never ran
        # (20260712 review, reproduced). 'EngelAI-SubEngel' reaps a mid-flight
        # packaged llama-cli.exe one-shot (no port, no other signature).
        "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $self -and $_.ProcessId -ne $PID -and $_.CommandLine -and ("
        "  $_.CommandLine -match 'TunnelPersistent' -or "
        "  $_.CommandLine -match 'engel_hidden_launch' -or "
        "  $_.CommandLine -match 'engel_run_hidden' -or "
        "  $_.CommandLine -match 'EngelAI-SubEngel') } | "
        "  ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -EA Stop; $k++ } catch { $f++ } }; "
        "Start-Sleep -Milliseconds 400; "
        "$t=@(); "
        "$t += (Get-CimInstance Win32_Process -Filter \"Name='ssh.exe'\" | "
        "  Where-Object { $_.CommandLine -match 'engel_ai_main_ct246' -and $_.CommandLine -match ' -N' } | Select-Object -Expand ProcessId); "
        "$t += (Get-NetTCPConnection -State Listen -EA SilentlyContinue | Where-Object { $ports -contains $_.LocalPort } | Select-Object -Expand OwningProcess); "
        "$t | Sort-Object -Unique | Where-Object { $_ -and $_ -ne $self } | "
        "  ForEach-Object { try { Stop-Process -Id $_ -Force -EA Stop; $k++ } catch { $f++ } }; "
        "\"$k $f\""
    )
    cp = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                        capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
    parts = (cp.stdout or "").split()
    killed = int(parts[0]) if len(parts) >= 1 and parts[0].isdigit() else 0
    failed = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0
    return killed, failed


def _log(msg: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n")
    except Exception:
        pass


def _load_state() -> dict:
    try:
        value = json.loads(STATE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _save_state(payload: dict) -> None:
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass


def engel_app_running() -> "bool | None":
    """True = app open, False = app closed, None = UNKNOWN (couldn't read the
    process table). (20260711 fix) the old code returned False on any tasklist
    failure/timeout, which routed straight into the FULL TEARDOWN branch — a
    single hung tasklist tick (AV scan, load spike) while the app was open would
    kill the llama :8899 model, the sdxl :8931 server, and both tunnels mid-turn.
    Tri-state: an unreadable process table must NEVER be treated as 'app closed'."""
    try:
        cp = _run(["tasklist", "/FI", "IMAGENAME eq EngelAIMain.exe", "/FO", "CSV", "/NH"])
        return "EngelAIMain.exe" in (cp.stdout or "")
    except Exception as exc:
        _log(f"engel_app_running: could not read process table ({str(exc)[:80]}); skipping this tick")
        return None


def task_state(name: str) -> str:
    try:
        cp = _run(["schtasks", "/Query", "/TN", name, "/FO", "CSV", "/NH"])
        line = (cp.stdout or "").strip().splitlines()
        if not line:
            return "missing"
        # CSV: "name","next run","status"
        return line[0].rsplit('","', 1)[-1].strip('"').strip().lower()
    except Exception:
        return "unknown"


def main() -> int:
    up = engel_app_running()
    if up is None:
        # unknown state: neither start nor tear down — wait for the next tick.
        return 0
    if up:
        _save_state({"app_state": "up", "down_since": "", "updated_at": datetime.now().isoformat()})
        # (2026-08-10 review) Drive Engel's OWN cron store from this heartbeat. The
        # engel_cron module shipped with the OpenClaw port but nothing ever called
        # tick() on this host, so every registered job (including the goal planner's
        # daily start-scheduled-goals tick) was decorative. Guarded and quick: due
        # command payloads launch their work detached, so a slow job can never stall
        # this controller pass; any error is logged and skipped, never fatal.
        try:
            sys.path.insert(0, str(ROOT / "tools"))
            import engel_cron

            fired = engel_cron.tick(engel_cron.CronStore())
            if fired:
                _log(f"cron -> fired {len(fired)} due job(s)")
        except Exception as exc:  # noqa: BLE001 — the stack loop must never die on cron
            _log(f"cron tick error (skipped): {str(exc)[:160]}")
        for s in SERVICES:
            state_now = task_state(s)
            if state_now == "missing":
                # Task not registered (registration is permission-gated and only the
                # elevated setup script may create it). Retrying every 60s would fail
                # every 60s and flood the log, so skip until it exists.
                continue
            if state_now != "running":
                cp = _run(["schtasks", "/Run", "/TN", s])
                if cp.returncode == 0:
                    _log(f"Engel up  -> started {s}")
                else:
                    _log(f"Engel up  -> FAILED start {s}: {(cp.stderr or cp.stdout or '').strip()[:120]}")
    else:
        state = _load_state()
        now = datetime.now()
        down_since_text = str(state.get("down_since") or "")
        try:
            down_since = datetime.fromisoformat(down_since_text) if down_since_text else None
        except ValueError:
            down_since = None
        if down_since is None:
            _save_state(
                {
                    "app_state": "down_grace",
                    "down_since": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            )
            _log(f"Engel down -> waiting {APP_DOWN_GRACE_SECONDS}s restart grace before stack teardown")
            return 0
        if (now - down_since).total_seconds() < APP_DOWN_GRACE_SECONDS:
            return 0
        stopped_any = False
        for s in reversed(SERVICES):
            if task_state(s) == "running":
                _run(["schtasks", "/End", "/TN", s])
                _log(f"Engel down -> stopped {s}")
                stopped_any = True
        # schtasks /End leaves orphans (tunnels, some bridges) — force-kill by port.
        # Always sweep when the app is down so a prior partial teardown is finished too.
        killed, failed = _force_kill_stack()
        if killed or failed or stopped_any:
            msg = f"Engel down -> force-killed {killed} lingering stack process(es)"
            if failed:
                msg += f"; {failed} needed elevation (higher-integrity orphan, e.g. old pid-8600 tunnel)"
            _log(msg)
        _save_state(
            {
                "app_state": "down_teardown_complete",
                "down_since": down_since.isoformat(),
                "updated_at": now.isoformat(),
            }
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
