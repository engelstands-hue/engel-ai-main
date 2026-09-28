"""
Verify the safe overnight research runtime contract.

This verifier is static and local. It does not start the loop, run the runner,
call providers, call the network, or mutate research queues.
"""

from __future__ import annotations

import py_compile
import re
from pathlib import Path


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()
APP = ROOT / "engel_app.py"
RESEARCH_BRAIN = ROOT / "engel_research_brain_v2.py"
LOOP = ROOT / "engel_overnight_loop.py"
RUNNER = ROOT / "engel_overnight_runner.py"
SUPPORT = ROOT / "engel_overnight_support.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _fail(message: str) -> None:
    raise SystemExit("FAIL: " + message)


def _require_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        _fail("missing required file: " + str(path))


def _require_tokens(text: str, tokens: list[str], label: str) -> None:
    missing = [token for token in tokens if token not in text]
    if missing:
        _fail(label + " missing required token(s): " + ", ".join(missing))


def _forbid_tokens(text: str, tokens: list[str], label: str) -> None:
    hits = [token for token in tokens if token in text]
    if hits:
        _fail(label + " contains forbidden token(s): " + ", ".join(hits))


def _forbid_regex(text: str, patterns: list[str], label: str) -> None:
    hits = []
    for pattern in patterns:
        if re.search(pattern, text, flags=re.I):
            hits.append(pattern)
    if hits:
        _fail(label + " contains forbidden pattern(s): " + ", ".join(hits))


def main() -> int:
    for path in [APP, RESEARCH_BRAIN, LOOP, RUNNER, SUPPORT]:
        _require_file(path)
        py_compile.compile(str(path), doraise=True)

    app = _read(APP)
    loop = _read(LOOP)
    runner = _read(RUNNER)
    state_file_write_token = "ALIVE_" + "STATE_FILE"

    _require_tokens(
        app,
        [
            "engel_overnight_loop.py",
            "engel_overnight_runner.py",
            "Overnight Research Startup Unavailable",
            "No research loop was started.",
            "No runner was started.",
        ],
        "engel_app.py",
    )

    _require_tokens(
        loop,
        [
            "engel_overnight_runner.py",
            "overnight_research_loop.pid",
            "overnight_research_loop.stop",
            "OVERNIGHT_RESEARCH_LOOP_STATUS.md",
            "OVERNIGHT_RUNNER_STATUS.md",
            "RUNNING_RESEARCH",
            "SLEEPING",
            "OFF",
            "BLOCKED_DUPLICATE",
        ],
        "engel_overnight_loop.py",
    )

    _require_tokens(
        runner,
        [
            "engel_research_brain_v2",
            "OVERNIGHT_RUNNER_STATUS.md",
            "overnight_runner_single_instance_v2runnera.lock",
            "research_brain_status",
            "research_queue_status",
            "research_next_best_topic",
            "learning_proposals_build",
            "learning_proposals_review",
            "research_completion_digest",
            "research_digest_latest",
            "No APPROVE token supplied by this runner.",
            "No APPROVE_REPORT token supplied by this runner.",
        ],
        "engel_overnight_runner.py",
    )

    forbidden_runner_tokens = [
        "overnight_auto_research",
        "research_full_cycle",
        "source_fetch",
        "research_discover",
        "research_brief_latest",
        "research_memory_extract_latest",
        "backup_stable",
        "requests" + ".",
        "urllib" + ".request",
        "web" + "browser",
        "pya" + "utogui",
        "sele" + "nium",
        "play" + "wright",
        "Popen(",
        state_file_write_token + ".write",
    ]
    _forbid_tokens(runner, forbidden_runner_tokens, "engel_overnight_runner.py")

    forbidden_loop_tokens = [
        "overnight_auto_research",
        "research_full_cycle",
        "source_fetch",
        "research_discover",
        "research_brief_latest",
        "requests" + ".",
        "urllib" + ".request",
        "web" + "browser",
        "pya" + "utogui",
        "sele" + "nium",
        "play" + "wright",
        state_file_write_token + ".write",
    ]
    _forbid_tokens(loop, forbidden_loop_tokens, "engel_overnight_loop.py")

    _forbid_regex(
        loop + "\n" + runner,
        [
            r"runtime_autonomy_enabled\s*[:=]\s*true",
            r"runtime_level_2_enabled\s*[:=]\s*true",
            r"STAGED_DRAFT_ACTIVE\s*=\s*True",
            "localhost:" + "11434",
            r"\b" + "O" + r"llama\b",
            r"scht" + r"asks\b",
            r"New-" + r"Service\b",
            r"Start-" + r"Service\b",
        ],
        "overnight runtime scripts",
    )

    print("PASS: overnight runtime scripts exist, compile, and preserve the safe staged runner contract.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
