"""
engel_next_step_human_command_smoke.py

Safe next-step smoke runner for Engel Human Command Mode.

Default mode is conservative:
- No dependency install.
- No report-write smoke.
- No model runtime gate.
- No provider/API/network command.
- No arbitrary shell.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable

from engel_human_command_shared import (
    HUMAN_COMMAND_CONTRACT_VERIFIER_REL,
    human_command_now_stamp,
)


APP_ROOT = Path(__file__).resolve().parent


EXPECTED_SAFE_MARKERS = [
    "Human-commanded",
    "Autonomy",
    "BLOCKED",
    "Model-command",
    "Provider",
    "Remote Queen",
]

EXPECTED_ROUTE_MARKERS = [
    "Colony Hive",
    "Offline Seed LLM",
]

EXPECTED_BLOCK_MARKERS = [
    "blocked",
    "proposal",
    "requires",
    "approval",
]

HI_PROVIDER_MARKERS = [
    "# Engel Brain Provider",
    "No brain provider is configured",
]

HI_LOCAL_COMPANION_MARKERS = [
    "safe local mode",
    "I\u2019m here",
    "I'm here",
    "local",
    "[UNTRUSTED_MODEL_OUTPUT]",
]


def now_stamp() -> str:
    return human_command_now_stamp()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def run_command(args: list[str], cwd: Path, input_text: str | None = None, timeout: int = 180) -> tuple[int, str]:
    env = os.environ.copy()
    env.pop("ENGEL_OFFLINE_SEED_LLM_ENABLED", None)

    proc = subprocess.run(
        args,
        cwd=str(cwd),
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        env=env,
        shell=False,
    )
    return proc.returncode, proc.stdout


def append_section(lines: list[str], title: str, body: str | Iterable[str]) -> None:
    lines.append(f"\n## {title}\n")
    if isinstance(body, str):
        lines.append(body.rstrip() + "\n")
    else:
        lines.extend(str(item).rstrip() + "\n" for item in body)


def build_cli_smoke(root: Path, write_report: bool, approve_install: bool) -> list[str]:
    commands_path = root / "memory" / "ENGEL_COMMANDS.md"
    reports_path = root / "reports"
    commands = [
        "human command mode status",
        "guarded write status",
        "human command help",
        "research file " + str(commands_path),
        "research folder " + str(reports_path),
        "install package requests",
        "request package install packaging for smoke test",
        "dependency install plan packaging for smoke test",
        "start remote queen wifi",
        "hi",
        "colony hive status",
        "offline seed llm status",
    ]

    if write_report:
        commands.insert(
            5,
            "research folder " + str(reports_path) + " to report HUMAN_COMMAND_MODE_NEXT_STEP_SMOKE.md",
        )

    if approve_install:
        commands.insert(
            9,
            "install dependency packaging for smoke test APPROVE_INSTALL",
        )

    commands.append("exit")
    return commands


def contains_any(text: str, markers: Iterable[str]) -> bool:
    lower = text.lower()
    return any(marker.lower() in lower for marker in markers)


def extract_command_response(
    full_output: str,
    command_text: str,
    command_sequence: Iterable[str] | None = None,
) -> str:
    """Return the CLI segment for one command, from its prompt through the next prompt."""
    command = command_text.strip()
    if not command:
        return ""

    echoed_pattern = re.compile(
        r"(?ms)^You >[ \t]*" + re.escape(command) + r"[ \t]*(?:\r?\n|$).*?(?=^You >|\Z)"
    )
    echoed_match = echoed_pattern.search(full_output)
    if echoed_match:
        return echoed_match.group(0)

    if command_sequence is None:
        return ""

    commands = [item.strip() for item in command_sequence]
    normalized = command.lower()
    try:
        command_index = [item.lower() for item in commands].index(normalized)
    except ValueError:
        return ""

    prompt_matches = list(re.finditer(r"(?m)^You >", full_output))
    if command_index >= len(prompt_matches):
        return ""

    start = prompt_matches[command_index].start()
    end = prompt_matches[command_index + 1].start() if command_index + 1 < len(prompt_matches) else len(full_output)
    return full_output[start:end]


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe next-step smoke runner for Engel Human Command Mode.")
    parser.add_argument("--root", default=str(APP_ROOT), help="Engel project root. Default: current script directory.")
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Also run the route that writes HUMAN_COMMAND_MODE_NEXT_STEP_SMOKE.md under reports/codex_bridge.",
    )
    parser.add_argument(
        "--approve-install",
        action="store_true",
        help="Also run the approved dependency install smoke for 'packaging'. Default is no install.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional report output path. Default: reports/codex_bridge/HUMAN_COMMAND_MODE_NEXT_STEP_SMOKE_RUN_<stamp>.md",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    report_dir = root / "reports" / "codex_bridge"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = Path(args.output) if args.output else report_dir / f"HUMAN_COMMAND_MODE_NEXT_STEP_SMOKE_RUN_{now_stamp()}.md"

    lines: list[str] = []
    append_section(lines, "Status", "RUNNING")
    append_section(lines, "Project root", str(root))
    append_section(lines, "Python executable", sys.executable)
    append_section(lines, "Default mode", [
        f"write_report={args.write_report}",
        f"approve_install={args.approve_install}",
        "ENGEL_OFFLINE_SEED_LLM_ENABLED is cleared for subprocess smoke.",
    ])

    if not root.exists():
        append_section(lines, "Result", f"BLOCKED: root does not exist: {root}")
        report_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"BLOCKED: root does not exist: {root}")
        print(f"Report: {report_path}")
        return 2

    required_files = [
        root / "engel_app.py",
        root / "engel_human_command_mode.py",
        root / "engel_communication_router.py",
        root / "memory" / "HUMAN_COMMAND_MODE_CONTRACT_V1.json",
        root / Path(HUMAN_COMMAND_CONTRACT_VERIFIER_REL),
    ]

    missing = [str(p) for p in required_files if not p.exists()]
    if missing:
        append_section(lines, "Missing required files", missing)
        append_section(lines, "Result", "BLOCKED")
        report_path.write_text("\n".join(lines), encoding="utf-8")
        print("BLOCKED: missing required files")
        for item in missing:
            print(" -", item)
        print(f"Report: {report_path}")
        return 2

    compile_targets = [
        "engel_app.py",
        "engel_companion.py",
        "engel_communication_router.py",
        "engel_human_command_mode.py",
        HUMAN_COMMAND_CONTRACT_VERIFIER_REL,
    ]
    code, out = run_command([sys.executable, "-m", "py_compile", *compile_targets], root)
    append_section(lines, "py_compile", f"exit={code}\n\n{out}")
    if code != 0:
        append_section(lines, "Result", "BLOCKED: py_compile failed")
        report_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"BLOCKED: py_compile failed. Report: {report_path}")
        return 2

    code, out = run_command([sys.executable, HUMAN_COMMAND_CONTRACT_VERIFIER_REL], root)
    append_section(lines, "verify_human_command_mode_contract.py", f"exit={code}\n\n{out}")
    if code != 0:
        append_section(lines, "Result", "BLOCKED: Human Command Mode verifier failed")
        report_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"BLOCKED: verifier failed. Report: {report_path}")
        return 2

    commands = build_cli_smoke(root, write_report=args.write_report, approve_install=args.approve_install)
    cli_input = "\n".join(commands) + "\n"
    code, out = run_command([sys.executable, "engel_app.py"], root, input_text=cli_input, timeout=240)
    append_section(lines, "CLI smoke commands", commands)
    append_section(lines, "CLI smoke output", f"exit={code}\n\n{out}")

    hi_segment = extract_command_response(out, "hi", commands)
    append_section(lines, "Scoped hi response segment", hi_segment or "NOT FOUND")

    checks = {
        "human_command_mode_markers": contains_any(out, EXPECTED_SAFE_MARKERS),
        "route_markers": contains_any(out, EXPECTED_ROUTE_MARKERS),
        "unsafe_block_markers": contains_any(out, EXPECTED_BLOCK_MARKERS),
        "hi_response_segment_found": bool(hi_segment.strip()),
        "no_brain_provider_for_hi": not contains_any(hi_segment, HI_PROVIDER_MARKERS),
        "hi_local_companion_marker": contains_any(hi_segment, HI_LOCAL_COMPANION_MARKERS),
        "engel_exited": "Engel stopped." in out or "You >" in out,
    }

    append_section(lines, "Smoke checks", [f"{k}: {v}" for k, v in checks.items()])

    if code != 0 or not all(checks.values()):
        append_section(lines, "Result", "PARTIAL: CLI smoke ran but one or more checks failed")
        report_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"PARTIAL: CLI smoke checks need review. Report: {report_path}")
        return 1

    exe_lines: list[str] = []
    for rel in [r"live\app\Engel.exe", r"live\app\EngelSuperSwarmHive3D.exe"]:
        p = root / rel
        if p.exists():
            exe_lines.append(f"{rel}: {sha256_file(p)}")
        else:
            exe_lines.append(f"{rel}: MISSING")
    append_section(lines, "Live EXE hashes", exe_lines)

    append_section(lines, "Safety statement", (
        "This smoke runner did not enable autonomy, model-command execution, provider/API fallback, "
        "Remote Queen runtime, arbitrary shell execution, source edits, queue mutation, or trusted-memory writes. "
        "Approved dependency install smoke is disabled by default and only runs with --approve-install."
    ))

    append_section(lines, "Result", "COMPLETE")
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print("COMPLETE: Human Command Mode next-step smoke passed.")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
