#!/usr/bin/env python3
"""Single source of truth for "is PID X alive?" on Engel hosts.

Shelling out to `tasklist /FI "PID eq N"` for this is the bug that put a visible
terminal window on the operator's screen twice every 30 seconds (2026-07-29): each
call creates a console process, and with Windows Terminal as the default console
host that console is a real window even under CREATE_NO_WINDOW in some handoff
paths. It is also ~100x slower than asking the kernel.

So: open a handle and ask the kernel directly. No child process, no console,
correct answers for the edge cases that matter:

* access denied  -> the PID exists but is not ours to query -> RUNNING (pid 4, the
  Windows System process, is the canonical example; calling it dead would make a
  watchdog think its service crashed);
* handle opens   -> WaitForSingleObject(0): signalled means EXITED, timeout means
  alive. This avoids the STILL_ACTIVE(259) exit-code ambiguity entirely;
* POSIX          -> os.kill(pid, 0), with EPERM meaning alive-but-not-ours.

Import it (`from engel_process_liveness import pid_is_running`) instead of copying:
the 2026-07-30 sweep found three diverged private copies, two of them still
spawning consoles.
"""
from __future__ import annotations

import ctypes
import errno
import os

_SYNCHRONIZE = 0x00100000
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_ERROR_ACCESS_DENIED = 5
_WAIT_TIMEOUT = 0x102


def pid_is_running(pid: int) -> bool:
    """True when the process exists right now. Never spawns a child process."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            # HANDLE is pointer-sized; ctypes' default c_int return would truncate
            # it on 64-bit and hand CloseHandle a bogus value.
            kernel32.OpenProcess.restype = ctypes.c_void_p
            kernel32.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
            kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
            kernel32.WaitForSingleObject.restype = ctypes.c_ulong
            kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
            handle = kernel32.OpenProcess(
                _SYNCHRONIZE | _PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if not handle:
                return ctypes.get_last_error() == _ERROR_ACCESS_DENIED
            try:
                return kernel32.WaitForSingleObject(handle, 0) == _WAIT_TIMEOUT
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            # A liveness probe must never take its caller down; the conservative
            # answer for a probe that could not run is "not proven running".
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError as exc:
        return exc.errno == errno.EPERM


if __name__ == "__main__":
    import sys

    target = int(sys.argv[1]) if len(sys.argv) > 1 else os.getpid()
    alive = pid_is_running(target)
    print(f"pid {target} running: {alive}")
    raise SystemExit(0 if alive else 1)
