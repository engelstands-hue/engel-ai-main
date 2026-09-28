#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("ENGEL_ROOT") or Path(__file__).resolve().parents[1])
if str(ROOT).startswith("\\\\?\\"):
    ROOT = Path(str(ROOT)[4:])
TOOLS = ROOT / "tools"
REPS_CMD = ROOT / "reps.cmd"
CLAUDE_REPS = ROOT / ".claude" / "reps" / "reps.py"
CT_REPS_URL = os.environ.get("ENGEL_CT246_REPS_URL", "http://127.0.0.1:24680/reps/status")

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run_recorder_status(timeout: int = 20) -> dict[str, Any]:
    command: list[str]
    if REPS_CMD.is_file():
        command = [str(REPS_CMD), "status"]
    elif CLAUDE_REPS.is_file():
        command = [sys.executable, str(CLAUDE_REPS), "status"]
    else:
        return {
            "ok": False,
            "available": False,
            "status": "missing",
            "message": "No reps.cmd or .claude/reps/reps.py recorder found.",
        }
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as exc:
        return {
            "ok": False,
            "available": True,
            "status": "error",
            "command": command,
            "error": str(exc),
        }
    return {
        "ok": result.returncode == 0,
        "available": True,
        "status": "ok" if result.returncode == 0 else "failed",
        "command": command,
        "returncode": result.returncode,
        "stdout_tail": (result.stdout or "")[-5000:],
        "stderr_tail": (result.stderr or "")[-2000:],
    }


def _read_ct_status(timeout: float = 2.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(CT_REPS_URL, timeout=timeout) as response:
            text = response.read(200_000).decode("utf-8", errors="replace")
    except (OSError, urllib.error.URLError) as exc:
        return {
            "ok": False,
            "reachable": False,
            "url": CT_REPS_URL,
            "error": str(exc),
        }
    try:
        payload = json.loads(text)
    except Exception:
        payload = {"raw": text[:2000]}
    return {
        "ok": True,
        "reachable": True,
        "url": CT_REPS_URL,
        "payload": payload,
    }


def _runtime_status() -> dict[str, Any]:
    from engel_universal_reps_runtime import status

    return status()


def status_payload() -> dict[str, Any]:
    runtime = _runtime_status()
    recorder = _run_recorder_status()
    ct_status = _read_ct_status()
    return {
        "schema": "engel_reps_system_bridge_status_v1",
        "ok": bool(runtime.get("ok") is True),
        "created_at_utc": _now(),
        "root": str(ROOT),
        "runtime": runtime,
        "recorder": recorder,
        "ct246_reps": ct_status,
        "commands": {
            "desktop": [
                "reps status",
                "reps recorder status",
                "reps record <lesson>",
                "reps cycle <lesson>",
                "reps cycle approve <lesson>",
            ],
            "rust": [
                "engel-ai-rs reps status",
                "engel-ai-rs reps recorder-status",
                "engel-ai-rs reps record <lesson>",
                "engel-ai-rs reps cycle <lesson>",
            ],
            "ct": [
                "GET /reps/status",
                "POST /reps/record",
                "POST /reps/evaluate",
                "POST /reps/propose",
                "POST /reps/signoff",
                "POST /reps/cycle",
            ],
        },
    }


def record_payload(lesson: str, *, source: str, lane: str, kind: str) -> dict[str, Any]:
    from engel_universal_reps_runtime import record_event

    return record_event(
        {
            "lane": lane,
            "source": source,
            "kind": kind,
            "lesson": lesson,
        }
    )


def cycle_payload(lesson: str, *, source: str, lane: str, kind: str, approved: bool = False) -> dict[str, Any]:
    from engel_universal_reps_runtime import run_cycle

    payload = {
        "lane": lane,
        "source": source,
        "kind": kind,
        "lesson": lesson,
        "force_propose": True,
    }
    if approved:
        payload["approved"] = True
        payload["decision"] = "approved"
    return run_cycle(payload)


def _count(value: dict[str, Any], key: str) -> str:
    return str(value.get(key, ""))


def render_status(payload: dict[str, Any]) -> str:
    runtime = payload.get("runtime") if isinstance(payload.get("runtime"), dict) else {}
    recorder = payload.get("recorder") if isinstance(payload.get("recorder"), dict) else {}
    ct_status = payload.get("ct246_reps") if isinstance(payload.get("ct246_reps"), dict) else {}
    template = runtime.get("template") if isinstance(runtime.get("template"), dict) else {}
    storage_policy = template.get("storage_policy") if isinstance(template.get("storage_policy"), dict) else {}
    ct_ssd = storage_policy.get("ct246_ssd_active") if isinstance(storage_policy.get("ct246_ssd_active"), dict) else {}
    server_hdd = storage_policy.get("server_hdd_archive") if isinstance(storage_policy.get("server_hdd_archive"), dict) else {}
    lines = [
        "# Engel R.E.P.S. Recorder",
        "",
        "Status: " + ("ready" if payload.get("ok") else "not ready"),
        "Provider-neutral runtime: " + str(runtime.get("provider_neutral") is True),
        "Claude-only: " + str(runtime.get("claude_only") is True),
        "Root: " + str(payload.get("root", "")),
        "State: " + str(runtime.get("state_path", "")),
        "Template present: " + str(bool(template)),
        "CT246 endpoint: " + ("reachable" if ct_status.get("reachable") else "not reachable"),
        "CT246 URL: " + str(ct_status.get("url", "")),
        "Recorder command: " + ("ready" if recorder.get("ok") else str(recorder.get("status", "unknown"))),
        "Storage policy: " + (
            f"source={storage_policy.get('source_of_truth')}; ROG={storage_policy.get('rog_role')}; "
            f"active={ct_ssd.get('path')}; archive={server_hdd.get('storage_id')}"
            if storage_policy
            else "not recorded"
        ),
        "",
        "Counts:",
        "- events: " + _count(runtime, "event_count_tail"),
        "- scorecards: " + _count(runtime, "scorecard_count_tail"),
        "- proposals: " + _count(runtime, "proposal_count_tail"),
        "- signoffs: " + _count(runtime, "signoff_count_tail"),
        "",
        "Recent events:",
    ]
    recent = runtime.get("recent_events") if isinstance(runtime.get("recent_events"), list) else []
    if recent:
        for event in recent[-6:]:
            if isinstance(event, dict):
                lines.append(
                    "- "
                    + str(event.get("event_id", ""))
                    + " | "
                    + str(event.get("lane", ""))
                    + " | "
                    + str(event.get("lesson", ""))
                )
    else:
        lines.append("- none")
    lines += [
        "",
        "UI commands:",
        "- `reps status`",
        "- `reps recorder status`",
        "- `reps record <lesson>`",
        "- `reps cycle <lesson>`",
        "- `reps cycle approve <lesson>`",
    ]
    if recorder.get("stdout_tail"):
        lines += ["", "Recorder tail:", str(recorder.get("stdout_tail", "")).strip()]
    if ct_status.get("error"):
        lines += ["", "CT246 readback note:", str(ct_status.get("error", ""))]
    return "\n".join(lines)


def render_result(title: str, payload: dict[str, Any]) -> str:
    lines = [
        "# " + title,
        "",
        "Status: " + ("ok" if payload.get("ok") else "failed"),
        "Schema: " + str(payload.get("schema", "")),
    ]
    for key in ("event_id", "scorecard_id", "proposal_id", "signoff_id", "cycle_id", "workspace_receipt_path"):
        if payload.get(key):
            lines.append(f"{key}: {payload.get(key)}")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if summary:
        lines += ["", "Summary:"]
        for key, value in summary.items():
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel REPS system bridge.")
    parser.add_argument("command", choices=["status", "recorder-status", "record", "cycle"])
    parser.add_argument("text", nargs="*", help="Lesson/prompt text for record or cycle.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--source", default="engel-ai-main-ui")
    parser.add_argument("--lane", default="ct246-engel-ai-main")
    parser.add_argument("--kind", default="operator_ui_reps")
    parser.add_argument("--approve", action="store_true", help="Record explicit Josh approval in the REPS sign-off receipt.")
    return parser


def main() -> int:
    args, unknown = build_parser().parse_known_args()
    if unknown:
        args.text.extend(unknown)
    text = " ".join(args.text).strip()
    if args.command == "status":
        payload = status_payload()
        rendered = render_status(payload)
    elif args.command == "recorder-status":
        payload = _run_recorder_status()
        rendered = "# R.E.P.S. Recorder Status\n\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    elif args.command == "record":
        if not text:
            payload = {"ok": False, "schema": "engel_reps_system_bridge_record_v1", "error": "record text required"}
        else:
            payload = record_payload(text, source=args.source, lane=args.lane, kind=args.kind)
        rendered = render_result("Engel R.E.P.S. Record", payload)
    else:
        if not text:
            payload = {"ok": False, "schema": "engel_reps_system_bridge_cycle_v1", "error": "cycle text required"}
        else:
            payload = cycle_payload(text, source=args.source, lane=args.lane, kind=args.kind, approved=args.approve)
        rendered = render_result("Engel R.E.P.S. Cycle", payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(rendered)
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
