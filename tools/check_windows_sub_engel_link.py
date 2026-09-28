#!/usr/bin/env python3
"""Check the Windows Sub-Engel node link using the stored pair session.

Prints one JSON object: {"connected": bool, "reason": str}. Exit 0 when
connected, 1 otherwise. Used by scripts/Connect-EngelAllDevices.ps1 as the
primary (non-destructive) link check; the pair tool is only a fallback when
the stored session no longer works, since fresh pairing needs a pairing_code
from a new node-ready callback that only a node-side restart can produce.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    try:
        from engel_sub_node_remote_control import run_action

        result = run_action("node.status", node_kind="windows")
        ok = bool(result.get("ok"))
        hostname = ""
        try:
            raw = result.get("result") or {}
            stdout = raw.get("stdout") if isinstance(raw, dict) else ""
            hostname = str(json.loads(stdout).get("hostname") or "")
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass
        if ok:
            reason = "stored-session node.status ok" + (f" ({hostname})" if hostname else "")
        else:
            detail = str(result.get("error") or result.get("message") or "no detail")[:160]
            reason = f"stored session rejected: {detail}"
        print(json.dumps({"connected": ok, "reason": reason}))
        return 0 if ok else 1
    except Exception as error:  # noqa: BLE001 - report, never crash the connect pass
        print(json.dumps({"connected": False, "reason": f"link check error: {error}"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
