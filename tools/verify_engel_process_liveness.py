"""Prove the PID liveness probe's contract: kernel-handle truth, no child processes.

Why this exists
---------------
`engel_process_liveness.pid_is_running` is the single source of truth for "is PID X
alive?" on Engel hosts, and until 2026-08-05 nothing verified it. That gap was not
neutral: the worker-liveness training card honestly said "no verifier covers this yet",
and in the first 8-hour run to reach that card the model answered by INVENTING this
file's name -- `verify_engel_process_liveness.py` appeared in 5 of 10 replies as a
confident fabrication. The curriculum can only stop teaching invention by making the
honest answer citable, so this verifier exists and proves the contract the probe's
docstring states:

* a live PID reads RUNNING;
* an exited PID reads DEAD (WaitForSingleObject, not the STILL_ACTIVE ambiguity);
* access-denied reads RUNNING (PID 4 on Windows: not ours to query is not dead);
* garbage input (zero, negative, non-numeric, None) reads DEAD, never raises;
* the probe itself NEVER spawns a child process -- shelling out to tasklist is the
  bug that put a console window on the operator's screen twice every 30 seconds
  (2026-07-29), and the no-child rule is asserted statically against the source.

The one child process HERE belongs to the verifier, not the probe: it is the target
whose life and death the probe is graded on, and it is spawned with CREATE_NO_WINDOW
so the check never repeats the console bug it guards against.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from engel_process_liveness import pid_is_running  # noqa: E402

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

checks = 0
failures: list[str] = []


def check(name: str, ok: bool, detail: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(f"{name}: {detail}")


def main() -> int:
    # 1. The calling process is, by construction, alive.
    check(
        "self_pid_reads_running",
        pid_is_running(os.getpid()) is True,
        "the probe reported the verifier's own PID as dead",
    )

    # 2/3. One child target: alive while sleeping, dead after wait() reaps it.
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        creationflags=CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        check(
            "live_child_reads_running",
            pid_is_running(child.pid) is True,
            f"child {child.pid} is sleeping yet the probe reported it dead",
        )
    finally:
        child.terminate()
        child.wait(timeout=15)
    # The handle-based wait answers immediately after exit; one short settle only.
    time.sleep(0.2)
    check(
        "exited_child_reads_dead",
        pid_is_running(child.pid) is False,
        f"child {child.pid} exited (reaped by wait) yet the probe reported it running",
    )

    # 4. Garbage input is DEAD, never an exception.
    for label, bogus in (("zero", 0), ("negative", -7), ("string", "not-a-pid"), ("none", None)):
        try:
            verdict = pid_is_running(bogus)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001 - the contract is "never raises"
            check(f"garbage_{label}_never_raises", False, f"raised {type(exc).__name__}: {exc}")
            continue
        check(
            f"garbage_{label}_reads_dead",
            verdict is False,
            f"pid_is_running({bogus!r}) returned {verdict!r}, expected False",
        )

    # 5. Access denied means RUNNING. PID 4 is the Windows System process: it exists
    # on every boot and OpenProcess on it fails with ERROR_ACCESS_DENIED for a normal
    # caller. Calling it dead would make a watchdog restart a service that never died.
    if os.name == "nt":
        check(
            "access_denied_reads_running",
            pid_is_running(4) is True,
            "PID 4 (System) reported dead -- access-denied must mean alive",
        )
    else:
        check(
            "posix_init_reads_running",
            pid_is_running(1) is True,
            "PID 1 reported dead -- EPERM must mean alive",
        )

    # 6. The probe never spawns a child process. Static, so a regression to tasklist
    # (or any subprocess use) fails here even on a host where the window would be
    # invisible. The probe's own docstring may NAME tasklist while telling this story,
    # so the assertion targets code, not prose.
    source = (TOOLS / "engel_process_liveness.py").read_text(encoding="utf-8")
    code_lines = [
        line
        for line in source.splitlines()
        if not line.lstrip().startswith("#") and '"""' not in line
    ]
    # Strip the module docstring block: everything before the first import.
    first_import = next(
        (i for i, line in enumerate(code_lines) if line.startswith(("import ", "from "))), 0
    )
    code = "\n".join(code_lines[first_import:])
    for marker in ("subprocess", "tasklist", "os.system", "Popen"):
        check(
            f"probe_source_free_of_{marker.replace('.', '_')}",
            marker not in code,
            f"the probe's code references {marker!r} -- the no-child-process contract is broken",
        )

    ok = not failures
    print(
        json.dumps(
            {
                "checks": checks,
                "failures": failures,
                "ok": ok,
                "status": "PASS" if ok else "FAIL",
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
