"""Engel Agent Meeting Room bridge for the local Code Factory project.

This bridge keeps Code Factory inside Engel's normal order flow:
Engel AI Main UI -> Agent Meeting Room -> Code Factory Scout -> result back to
Engel. It does not call provider APIs, store secrets, push branches, or run the
Builder station automatically.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ENGEL_APP_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = ENGEL_APP_ROOT.parent
CODE_FACTORY_ROOT = WORKSPACE_ROOT / "code-factory"
BRIDGE_RUNTIME = ENGEL_APP_ROOT / "runtime" / "meeting_room" / "code_factory"
BRIDGE_LABEL = "ChatGPT Bridge (Engel no-API handoff)"
HOUR_LOOP_ROOT = BRIDGE_RUNTIME / "hour_loop"


def _ensure_code_factory_imports() -> None:
    if not CODE_FACTORY_ROOT.exists():
        raise RuntimeError(f"Code Factory project not found: {CODE_FACTORY_ROOT}")
    root = str(CODE_FACTORY_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _safe_id(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text or "").strip())
    return cleaned.strip("_")[:80] or "code_factory_order"


def _title_from_prompt(prompt: str) -> str:
    for line in str(prompt or "").splitlines():
        clean = line.strip().strip("#").strip()
        if clean:
            return clean[:96]
    return "Code Factory Meeting Room order"


def is_code_factory_hour_loop_request(prompt: str) -> bool:
    low = str(prompt or "").lower()
    return (
        "code factory" in low
        and (
            "one hour" in low
            or re.search(r"\b\d+(?:\.\d+)?\s*(?:hour|hours|hr|hrs|h)\b", low)
            or re.search(r"\b\d+(?:\.\d+)?\s*(?:min|mins|minute|minutes)\b", low)
        )
        and ("loop" in low or "run" in low)
    )


def _duration_from_prompt(prompt: str) -> int:
    override = os.environ.get("ENGEL_CODE_FACTORY_HOUR_LOOP_SECONDS", "").strip()
    if override:
        try:
            return max(1, int(float(override)))
        except ValueError:
            pass
    low = str(prompt or "").lower()
    hours = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:hour|hours|hr|hrs|h)\b", low)
    if hours:
        return max(1, int(float(hours.group(1)) * 3600))
    minutes = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:min|mins|minute|minutes)\b", low)
    if minutes:
        return max(1, int(float(minutes.group(1)) * 60))
    if "one hour" in low or "1 hour" in low or "60 min" in low or "60-minute" in low:
        return 3600
    return 3600


def _write_issue(prompt: str) -> tuple[str, Path]:
    stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S%f")
    issue_id = f"engel-code-factory-{stamp}"
    title = _title_from_prompt(prompt)
    issue_dir = BRIDGE_RUNTIME / "issues"
    issue_dir.mkdir(parents=True, exist_ok=True)
    path = issue_dir / f"{_safe_id(issue_id)}.md"
    body = str(prompt or "").strip() or title
    path.write_text(
        "\n".join(
            [
                "---",
                f"id: {issue_id}",
                f"title: {title}",
                "labels: [ready-for-factory, code-factory, meeting-room]",
                "priority: P2",
                "size: small",
                "status: new",
                "---",
                "",
                body,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return issue_id, path


def _build_config() -> Any:
    _ensure_code_factory_imports()
    from lib.config import Config

    return Config(
        factory_root=BRIDGE_RUNTIME,
        target_repo=CODE_FACTORY_ROOT,
        local_issues_dir=BRIDGE_RUNTIME / "issues",
        github_enabled=False,
        github_repo="",
        github_label="ready-for-factory",
        branch_prefix="factory/",
        open_pr_online=False,
        model_intake="engel-chatgpt-bridge",
        model_scout="engel-chatgpt-bridge",
        model_qa="engel-chatgpt-bridge",
        builder_cli="codex",
        builder_args=[],
        scout_interval_sec=1800,
        builder_max_retries=1,
        loop_sleep_sec=60,
        max_issues_per_cycle=100,
        builder_timeout_sec=1800,
        log_level="INFO",
        jsonl_log=BRIDGE_RUNTIME / "logs" / "events.jsonl",
        raw={},
    )


def run_code_factory_scout_packet(prompt: str, *, source: str = "Agent Meeting Room") -> dict[str, Any]:
    """Run a real Intake + Scout pass for one Engel UI work order.

    The result is a spec on disk. Builder/QA/Ship stay available for explicit
    operator runs, but this bridge does not start code-editing work by itself.
    """
    _ensure_code_factory_imports()
    from lib.logging import EventLog
    from stations import intake, scout

    issue_id, issue_path = _write_issue(prompt)
    cfg = _build_config()
    log = EventLog(cfg.jsonl_log, level=cfg.log_level)
    log.emit(
        "meeting_room",
        "code_factory_order",
        issue=issue_id,
        source=source,
        bridge=BRIDGE_LABEL,
    )

    refined = intake.run_intake(cfg, log, dry_run=False)
    specs = scout.run_scout(cfg, log, dry_run=False)
    spec_path = next((path for path in specs if path.stem == issue_id), None)
    if spec_path is None:
        candidate = cfg.specs_dir / f"{issue_id}.json"
        spec_path = candidate if candidate.exists() else (specs[-1] if specs else None)
    if spec_path is None:
        raise RuntimeError("Code Factory Scout did not write a spec")

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec_md = spec_path.with_suffix(".md")
    return {
        "ok": True,
        "bridge": BRIDGE_LABEL,
        "mode": "engel_meeting_room",
        "source": source,
        "issue_id": issue_id,
        "issue_path": str(issue_path),
        "refined_paths": [str(path) for path in refined],
        "spec_path": str(spec_path),
        "spec_markdown_path": str(spec_md),
        "summary": str(spec.get("summary") or ""),
        "files_to_modify": list(spec.get("files_to_modify") or []),
        "files_to_create": list(spec.get("files_to_create") or []),
        "tests": list(spec.get("tests") or []),
        "runtime_root": str(BRIDGE_RUNTIME),
        "safety": {
            "no_provider_api_key_required": True,
            "builder_not_started": True,
            "no_push": True,
            "outputs_under_d_workspace": True,
        },
    }


def start_code_factory_hour_loop_packet(prompt: str, *, source: str = "Agent Meeting Room") -> dict[str, Any]:
    """Start the explicit one-hour Code Factory loop worker.

    This is opt-in only. The regular Scout bridge stays Scout-only; the Builder
    station starts only when Engel Main UI sends a prompt that clearly asks for
    the one-hour Code Factory loop.
    """
    _ensure_code_factory_imports()
    stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S%f")
    run_id = f"engel-code-factory-hour-loop-{stamp}"
    run_root = HOUR_LOOP_ROOT / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    prompt_path = run_root / "prompt.txt"
    stdout_path = run_root / "worker.stdout.log"
    stderr_path = run_root / "worker.stderr.log"
    status_path = run_root / "status.json"
    prompt_path.write_text(str(prompt or "").strip() + "\n", encoding="utf-8")

    duration_sec = _duration_from_prompt(prompt)
    worker = ENGEL_APP_ROOT / "tools" / "run_code_factory_hour_loop_worker.py"
    if not worker.exists():
        raise RuntimeError(f"Code Factory hour-loop worker missing: {worker}")

    temp_root = ENGEL_APP_ROOT / "runtime" / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(CODE_FACTORY_ROOT) + os.pathsep + str(ENGEL_APP_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["TEMP"] = str(temp_root)
    env["TMP"] = str(temp_root)
    env["TMPDIR"] = str(temp_root)
    # Desktop V2's temp policy may set HOME to Engel runtime. Let Codex CLI use
    # the normal Windows profile for auth while temp files stay on D:.
    if str(env.get("HOME") or "").startswith(str(ENGEL_APP_ROOT)):
        env.pop("HOME", None)

    status_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "state": "starting",
                "source": source,
                "duration_sec": duration_sec,
                "prompt_path": str(prompt_path),
                "started_at": _dt.datetime.now().isoformat(timespec="seconds"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    stdout_fh = stdout_path.open("w", encoding="utf-8")
    stderr_fh = stderr_path.open("w", encoding="utf-8")
    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        [
            sys.executable,
            str(worker),
            "--run-root",
            str(run_root),
            "--prompt-file",
            str(prompt_path),
            "--duration-sec",
            str(duration_sec),
        ],
        cwd=str(ENGEL_APP_ROOT),
        stdout=stdout_fh,
        stderr=stderr_fh,
        env=env,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )

    return {
        "ok": True,
        "bridge": BRIDGE_LABEL,
        "mode": "engel_code_factory_hour_loop",
        "source": source,
        "run_id": run_id,
        "pid": proc.pid,
        "duration_sec": duration_sec,
        "run_root": str(run_root),
        "prompt_path": str(prompt_path),
        "status_path": str(status_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "safety": {
            "explicit_user_prompt_required": True,
            "local_only": True,
            "no_push": True,
            "temp_root": str(temp_root),
        },
    }


def summarize_hour_loop_result(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Code Factory duration loop started from Engel AI UI input.",
            f"Bridge: {result.get('bridge')}",
            f"Run: {result.get('run_id')}",
            f"PID: {result.get('pid')}",
            f"Duration target: {result.get('duration_sec')} seconds; if a Builder pass is active at the hour mark it will finish.",
            f"Status: {result.get('status_path')}",
            f"Run root: {result.get('run_root')}",
            "Factory stations: Intake -> Scout -> Builder -> QA -> Ship.",
            "Safety: local only, no push, no provider API key required by Intake/Scout/QA.",
        ]
    )


def summarize_bridge_result(result: dict[str, Any]) -> str:
    files = [str(item) for item in result.get("files_to_modify") or []]
    creates = [str(item) for item in result.get("files_to_create") or []]
    tests = [str(item) for item in result.get("tests") or []]
    lines = [
        "Code Factory Scout returned a Builder-ready spec.",
        f"Bridge: {result.get('bridge')}",
        f"Issue: {result.get('issue_id')}",
        f"Spec: {result.get('spec_path')}",
        f"Markdown: {result.get('spec_markdown_path')}",
    ]
    if files:
        lines.append("Modify: " + ", ".join(files[:4]))
    if creates:
        lines.append("Create: " + ", ".join(creates[:3]))
    if tests:
        lines.append("Tests: " + "; ".join(tests[:3]))
    lines.append("Builder was not auto-started; this was Scout-only and no API key was used.")
    return "\n".join(lines)
