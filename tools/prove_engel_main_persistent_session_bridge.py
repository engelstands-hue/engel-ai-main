from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    import engel_app

    commands = [
        "local chat persistent session start",
        "local chat persistent session start approved",
        "local chat persistent session status",
        "local chat persistent session stop approved",
    ]
    required = {
        "local chat persistent session start": [
            "Status: BLOCKED_APPROVAL_REQUIRED",
            "no session state was changed",
        ],
        "local chat persistent session start approved": [
            "Status: SESSION_CONTROL_PASSED",
            "PERSISTENT_SESSION_STARTED_WITHOUT_PERSISTENT_PROCESS",
            "runtime_process_started",
            "false",
        ],
        "local chat persistent session status": [
            "Status: STATUS_READBACK_READY",
            "PERSISTENT_CHAT_SUPERVISED_SESSION",
        ],
        "local chat persistent session stop approved": [
            "Status: SESSION_CONTROL_PASSED",
            "PERSISTENT_SESSION_STOPPED_NO_PROCESS_TO_KILL",
            "runtime_process_started",
            "false",
        ],
    }
    for command in commands:
        text = engel_app.handle_human_command_mode_cli(command)
        missing = [needle for needle in required[command] if needle not in text]
        if missing:
            print("ENGEL_MAIN_PERSISTENT_SESSION_PROOF_FAIL")
            print(command)
            print("missing: " + ", ".join(missing))
            print(text[:4000])
            return 1
        print("PASS " + command)
    print("ENGEL_MAIN_PERSISTENT_SESSION_PROOF_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
