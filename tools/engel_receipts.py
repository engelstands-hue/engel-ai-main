#!/usr/bin/env python3
"""Shared receipt discipline for Engel AI Main tools.

Every important Engel action (browse, sign-in, image/video generation, CLI
account login, ...) should leave a plain, consistently-shaped receipt so that
after a context handoff nobody has to guess what happened.

Two artifacts per action:
  1. A full per-action receipt JSON under
       reports\\engel_action_receipts\\<category>\\<ts>_<action>.json
     plus a stable LATEST.json in that category folder.
  2. One compact line appended to the single unified tape
       memory\\engel_action_log.jsonl
     This is THE file to read after a compaction: one line per action,
     newest at the bottom, greppable.

Rules: Engel-owned state stays on D:/F: (never C:). Secret-looking values are
redacted before they are written. This module never prints to stdout (so it is
safe to call from tools whose stdout is parsed by the Flutter UI) and never
raises into the caller -- receipt failure must not break the real action.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS_ROOT = ROOT / "reports" / "engel_action_receipts"
ACTION_LOG = ROOT / "memory" / "engel_action_log.jsonl"

_SECRET_HINT = re.compile(
    r"(api[_-]?key|secret|token|password|passwd|credential|cookie|bearer|authorization)",
    re.IGNORECASE,
)
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _is_c(p: Path) -> bool:
    return str(p.drive).lower() == "c:"


def _safe(name: str) -> str:
    return _UNSAFE.sub("_", (name or "action")).strip("_")[:48] or "action"


def _redact(obj):
    """Defensively blank secret-looking string values by key name."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(v, str) and len(v) > 8 and _SECRET_HINT.search(str(k)):
                out[k] = "[REDACTED]"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


def write_action_receipt(
    category: str,
    action: str,
    ok: bool,
    status: str = "",
    payload=None,
    summary: str | None = None,
    artifacts=None,
    pid: int | None = None,
) -> str:
    """Write a per-action receipt + append one line to the unified action log.

    Returns the receipt path (or "" if writing was skipped/failed). Never raises.
    """
    try:
        if _is_c(RECEIPTS_ROOT) or _is_c(ACTION_LOG):
            return ""  # never write Engel receipts on C:
        ts = datetime.now(timezone.utc)
        stamp = ts.strftime("%Y%m%dT%H%M%S%fZ")
        cat_dir = RECEIPTS_ROOT / _safe(category)
        cat_dir.mkdir(parents=True, exist_ok=True)
        ACTION_LOG.parent.mkdir(parents=True, exist_ok=True)

        receipt = {
            "schema": "engel_action_receipt_v1",
            "ts_utc": ts.isoformat(),
            "category": category,
            "action": action,
            "ok": bool(ok),
            "status": status,
            "summary": summary or status,
            "artifacts": list(artifacts or []),
            "pid": int(pid) if pid is not None else os.getpid(),
            "c_drive_used": False,
            "payload": _redact(payload) if payload is not None else None,
        }
        path = cat_dir / f"{stamp}_{_safe(action)}.json"
        body = json.dumps(receipt, indent=2)
        path.write_text(body, encoding="utf-8")
        (cat_dir / "LATEST.json").write_text(body, encoding="utf-8")

        line = {
            "schema": "engel_action_log_v1",
            "ts_utc": ts.isoformat(),
            "category": category,
            "action": action,
            "ok": bool(ok),
            "status": (status or "")[:200],
            "summary": (summary or status or "")[:200],
            "receipt_path": str(path),
            "artifacts": list(artifacts or []),
            "pid": receipt["pid"],
        }
        with ACTION_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        return str(path)
    except Exception:
        return ""  # receipt discipline must never break the real action


def read_recent_actions(limit: int = 12):
    """Tail the unified action log (newest last). Returns a list of dicts."""
    try:
        if not ACTION_LOG.exists():
            return []
        lines = ACTION_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        out = []
        for ln in lines[-limit:]:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
    except Exception:
        return []
