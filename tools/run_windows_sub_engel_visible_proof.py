#!/usr/bin/env python3
"""Run a device-visible proof action on paired Windows Sub-Engel nodes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clip(value: str, limit: int = 1200) -> str:
    value = str(value or "")
    return value if len(value) <= limit else value[:limit] + "..."


def result_stdout(response: dict[str, Any]) -> str:
    result = response.get("result") if isinstance(response, dict) else {}
    if isinstance(result, dict):
        return str(result.get("stdout") or "")
    return ""


def write_report(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Windows Sub-Engel Device Visible Proof",
        "",
        f"- Time UTC: `{utc_stamp()}`",
        f"- Nodes checked: `{len(rows)}`",
        f"- Visible proof OK: `{sum(1 for row in rows if row.get('visible_ok'))}`",
        f"- Needs update/restart: `{sum(1 for row in rows if row.get('needs_update'))}`",
        "",
        "## Results",
        "",
    ]
    for row in rows:
        lines.extend([
            f"### {row.get('node_id')}",
            "",
            f"- URL: `{row.get('url', '')}`",
            f"- Visible action OK: `{row.get('visible_ok')}`",
            f"- Node connected: `{row.get('connected')}`",
            f"- Needs updated foreground agent: `{row.get('needs_update')}`",
            f"- Message: {row.get('message', '')}",
            "",
        ])
        if row.get("stdout"):
            lines.extend(["```text", clip(str(row["stdout"]), 4000), "```", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    from engel_sub_node_remote_control import health, list_node_sessions, run_action, runtime_node_url

    rows: list[dict[str, Any]] = []
    sessions = list_node_sessions("windows")
    for item in sessions:
        node_id = str(item.get("node_id") or "unknown")
        session = item.get("session") if isinstance(item, dict) else {}
        url = runtime_node_url(session) if isinstance(session, dict) else ""
        health_result = health(url) if url else {"ok": False, "error": "missing_url"}
        visible = run_action("ui.visible_status", node_kind="windows", node_id=node_id)
        status = run_action("node.status", node_kind="windows", node_id=node_id)
        stdout = result_stdout(visible)
        error = str(visible.get("error") or "")
        allowed = visible.get("allowed_actions") if isinstance(visible, dict) else None
        old_agent = "allowlist" in error.lower() or (
            isinstance(allowed, list) and "ui.visible_status" not in allowed
        )
        rows.append({
            "node_id": node_id,
            "url": url,
            "visible_ok": bool(visible.get("ok")),
            "connected": bool(health_result.get("ok") or status.get("ok")),
            "needs_update": bool(status.get("ok")) and not bool(visible.get("ok")) and old_agent,
            "message": (
                "Device foreground window should now show ENGEL DEVICE-SIDE VISIBLE PROOF."
                if visible.get("ok")
                else "pairing refresh required: pair-gated command rejected the stored token"
                if "invalid bearer token" in error.lower()
                else error or "visible proof action failed"
            ),
            "stdout": stdout,
        })

    run_id = utc_stamp().replace("-", "").replace(":", "").replace("Z", "Z")
    report_path = ROOT / "reports" / "codex_bridge" / f"ENGEL_WINDOWS_SUB_ENGEL_VISIBLE_PROOF_{run_id}.md"
    write_report(report_path, rows)
    print(json.dumps({"ok": all(row.get("visible_ok") for row in rows), "report_path": str(report_path), "rows": rows}, indent=2))
    return 0 if rows and all(row.get("visible_ok") for row in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
