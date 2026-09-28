#!/usr/bin/env python3
"""Engel Sub-Engel auto-return worker — a controller-managed stack service (2026-07-12).

Runs the shared-room Sub-Engel node agent's auto-process loop on THIS machine so
Agent Meeting Room work orders targeting windows_sub_engel are answered even while
the dedicated node (DESKTOP-UE5A6GG) is offline. Registered as the scheduled task
`EngelSubEngelAutoReturn` (see scripts/Setup-EngelStackLifecycle.ps1) and listed in
tools/engel_stack_controller.py SERVICES, so it lives and dies with EngelAIMain.exe
like the rest of the stack.

Design notes (from the 2026-07-12 lifecycle recon):
- The scheduled-task lane passes NO environment, so the agent's env contract is
  pinned HERE with setdefault (operator env still wins).
- The agent loop runs IN-PROCESS (importlib from the shared-room copy), not as a
  child: the controller's teardown force-kill matches this process's
  engel_hidden_launch command line, and an in-process loop leaves no orphan child.
- The agent has no single-instance guard, so this wrapper holds a loopback port
  (MUTEX_PORT, also in STACK_PORTS for teardown reaping) as a cross-process mutex.
- Any non-OSError exception inside one order KILLS the agent's loop (known agent
  behavior) — the wrapper catches, logs, re-imports the agent (picking up newer
  shared-room code), and restarts the loop after a short backoff.
"""
from __future__ import annotations

import importlib.util
import os
import socket
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MUTEX_PORT = 8777  # loopback single-instance guard; listed in STACK_PORTS
AGENT_PATH = Path(
    os.environ.get(
        "ENGEL_WINDOWS_SUB_NODE_AGENT",
        str(
            ROOT
            / "workflows"
            / "sub_engel_nodes"
            / "standalone"
            / "agent"
            / "engel_windows_sub_node_agent.py"
        ),
    )
)


def _env_num(name: str, default: str, cast):
    # A malformed operator value must degrade to the pinned default, not crash
    # the service at import time (before the mutex/log preamble even runs).
    try:
        return cast(os.environ.get(name, default))
    except (TypeError, ValueError):
        return cast(default)


SCAN_INTERVAL_SECONDS = _env_num("ENGEL_SUB_AUTO_RETURN_INTERVAL", "30", float)
SCAN_LIMIT = _env_num("ENGEL_SUB_AUTO_RETURN_LIMIT", "5", int)
# cycles=0 means run until stopped; a finite override exists for smoke tests.
SCAN_CYCLES = _env_num("ENGEL_SUB_AUTO_RETURN_CYCLES", "0", int)
RESTART_BACKOFF_SECONDS = 20.0

# The agent's env contract (2026-07-11 verified working set). setdefault only —
# an operator-set variable always wins. All paths are on D:/G: (no-C rule; the
# agent's approved_env_path silently drops C: paths anyway).
_PACKAGED = ROOT / "runtime" / "package_build" / "EngelAI-SubEngel-Windows-App" / "EngelAI-SubEngel" / "_internal"
_ENV_CONTRACT = {
    "ENGEL_WINDOWS_SUB_NODE_ROOT": str(ROOT / "runtime" / "sub_engel_meeting_dispatch_auto_return_node"),
    "ENGEL_SUB_ENGEL_ENABLE_LLAMA_CPP_FALLBACK": "1",
    "ENGEL_SUB_ENGEL_LOCAL_HELPER_MANIFEST": str(_PACKAGED / "models" / "sub_engel_local_helper_model.json"),
    "ENGEL_SUB_ENGEL_LLM_CLI": str(_PACKAGED / "runtimes" / "llama.cpp" / "cuda" / "llama-cli.exe"),
    # 14 layers coexists with the :8899 GPU chat server on the 2070 (verified);
    # 4096 ctx keeps the one-shot KV cache ~0.5GB instead of 4GB (32k default).
    "ENGEL_SUB_ENGEL_LLM_GPU_LAYERS": "14",
    "ENGEL_SUB_ENGEL_LLM_CTX": "4096",
}


def _log(message: str) -> None:
    # stdout is runtime/logs/hidden_engel_sub_engel_auto_return_service.log under
    # the hidden-launch shim; keep output to state changes only (no rotation).
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(f"[{stamp}] {message}", flush=True)


def _acquire_mutex() -> "socket.socket | str":
    """The bound socket, or 'held' (another instance) / 'error' (transient bind
    failure — callers should retry, NOT exit, or the controller task-thrashes)."""
    guard = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        guard.bind(("127.0.0.1", MUTEX_PORT))
        guard.listen(1)
        return guard
    except OSError as exc:
        guard.close()
        if getattr(exc, "winerror", None) == 10048 or exc.errno in (48, 98):  # ADDRINUSE
            return "held"
        _log(f"mutex bind failed ({exc}) -- will retry")
        return "error"


def _load_agent():
    """Fresh import of the shared-room agent copy (the distribution point) so a
    crash-restart also picks up newer agent code."""
    spec = importlib.util.spec_from_file_location("engel_windows_sub_node_agent", AGENT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    for key, value in _ENV_CONTRACT.items():
        os.environ.setdefault(key, value)

    while True:
        guard = _acquire_mutex()
        if guard == "held":
            _log(f"another instance holds 127.0.0.1:{MUTEX_PORT} -- exiting (single-instance)")
            return 0
        if guard == "error":
            time.sleep(60)  # transient bind failure: stay alive so the task stays Running
            continue
        break

    _log(
        f"Sub-Engel auto-return service starting: interval={SCAN_INTERVAL_SECONDS}s "
        f"limit={SCAN_LIMIT} cycles={SCAN_CYCLES or 'forever'} agent={AGENT_PATH}"
    )
    try:
        while True:
            try:
                agent_present = AGENT_PATH.is_file()
            except OSError:
                agent_present = False  # wedged Drive mount must not crash the probe
            if not agent_present:
                _log(f"agent script not found at {AGENT_PATH} (Google Drive offline?) -- retry in 120s")
                try:
                    time.sleep(120)
                except KeyboardInterrupt:
                    _log("interrupt received while waiting for Drive -- stopping")
                    return 0
                continue
            try:
                agent = _load_agent()
                rc = agent.auto_process_work_orders_loop(
                    interval_seconds=SCAN_INTERVAL_SECONDS,
                    limit=SCAN_LIMIT,
                    cycles=SCAN_CYCLES,
                )
                # With cycles=0 the loop only RETURNS via its own KeyboardInterrupt
                # handler (operator stop) — restarting here would resurrect a
                # deliberately stopped worker 20s later. Treat any clean return
                # as an intentional stop.
                _log(f"agent loop finished (rc={rc}) -- exiting")
                return int(rc)
            except KeyboardInterrupt:
                _log("interrupt received -- stopping")
                return 0
            except Exception:
                if SCAN_CYCLES > 0:
                    _log("agent loop crashed in finite mode -- exiting 1:\n" + traceback.format_exc())
                    return 1
                _log("agent loop crashed -- restarting after backoff:\n" + traceback.format_exc())
            try:
                time.sleep(RESTART_BACKOFF_SECONDS)
            except KeyboardInterrupt:
                _log("interrupt received during backoff -- stopping")
                return 0
    finally:
        try:
            guard.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
