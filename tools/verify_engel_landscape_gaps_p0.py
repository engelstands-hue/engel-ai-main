#!/usr/bin/env python3
"""Verifier for landscape-gap P0 organs: routines, compaction, presence, MCP allowlist."""
from __future__ import annotations

import ast
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "tools"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import engel_routines as routines  # noqa: E402
import engel_context_compaction as compaction  # noqa: E402
import engel_mcp_allowlist as mcp  # noqa: E402
import engel_grok_bot as grok_bot  # noqa: E402
import engel_artifact_cards as artifacts  # noqa: E402
from engel_ai_update_routes import resolve_update_route  # noqa: E402
from engel_route_explorer import _group_for_route  # noqa: E402


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passes = 0

    def check(self, condition: bool, name: str, detail: str = "") -> None:
        if condition:
            self.passes += 1
            print("PASS " + name + ((" -- " + detail) if detail else ""))
        else:
            self.failures.append(name + ((": " + detail) if detail else ""))
            print("FAIL " + name + ((" -- " + detail) if detail else ""))


def _no_forbidden(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    blocked = {"socket", "requests", "http.client", "urllib.request", "subprocess"}
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in blocked:
                    hits.append("import " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in blocked:
                hits.append("from " + node.module)
    return hits


def main() -> int:
    checks = Checks()
    required = {
        "engel.routines.docs": "engel routines docs",
        "engel.routines.status": "engel routines status",
        "engel.routines.list": "list engel routines",
        "engel.routines.create": "create engel routine",
        "engel.routines.due": "engel routines due",
        "engel.routines.stage": "stage engel routine",
        "engel.routines.pause": "pause engel routine",
        "engel.compaction.docs": "engel compaction docs",
        "engel.compaction.status": "engel compaction status",
        "engel.compaction.compact": "compact engel thread",
        "engel.mcp_allowlist.docs": "engel mcp allowlist docs",
        "engel.mcp_allowlist.status": "engel mcp allowlist status",
        "engel.mcp_allowlist.list": "list engel mcp allowlist",
        "engel.grok_bot.presence": "grok bot presence",
    }
    for route_id, phrase in required.items():
        resolved = resolve_update_route(phrase)
        checks.check(resolved == route_id, f"route_{route_id}", f"got {resolved}")

    checks.check(
        _group_for_route("engel.routines.status") == "Routines",
        "explorer_group_routines",
    )
    checks.check(
        _group_for_route("engel.compaction.status") == "Context Compaction",
        "explorer_group_compaction",
    )
    checks.check(
        _group_for_route("engel.mcp_allowlist.status") == "MCP Allowlist",
        "explorer_group_mcp",
    )

    for path in (
        ROOT / "engel_routines.py",
        ROOT / "engel_context_compaction.py",
        ROOT / "engel_mcp_allowlist.py",
    ):
        hits = _no_forbidden(path)
        checks.check(not hits, f"no_network_{path.name}", str(hits))

    with tempfile.TemporaryDirectory() as tmp:
        # Point routine state into temp by monkeypatching paths
        routines.STATE_DIR = Path(tmp) / "routines"
        routines.ROUTINE_DIR = routines.STATE_DIR / "defs"
        routines.STAGED_DIR = routines.STATE_DIR / "staged"
        routines.REGISTRY_PATH = routines.STATE_DIR / "registry.json"
        routines.RECEIPT_DIR = Path(tmp) / "reports"
        row = routines.create_routine(
            "Gap Audit Brief",
            "interval_minutes:5",
            "Stage a status ask for tunnel health.",
        )
        checks.check(row["safety"]["auto_execute"] is False, "routine_no_auto_execute")
        checks.check(routines._is_due(row) is True, "routine_interval_due")
        staged = routines.stage_routine(row["slug"])
        checks.check(
            staged["staged"]["meeting_room_send_job"] is False,
            "routine_stage_no_send_job",
        )
        checks.check(
            "NOT auto-run" in staged["staged"]["order_text"],
            "routine_stage_text_marks_manual",
        )
        paused = routines.pause_routine(row["slug"], paused=True)
        checks.check(paused["paused"] is True, "routine_pause")
        checks.check(routines._is_due(paused) is False, "paused_not_due")

        compaction.STATE_DIR = Path(tmp) / "compaction"
        compaction.RECEIPT_DIR = Path(tmp) / "compaction_reports"
        receipt = compaction.compact_messages(
            [
                {"role": "system", "content": "local engel"},
                {"role": "user", "content": "status?"},
                {"role": "assistant", "content": "tunnels ok"},
            ],
            thread_id="test-thread",
        )
        checks.check(receipt["provider"] == "local_only", "compaction_local_only")
        checks.check(receipt["input_message_count"] == 3, "compaction_count")
        checks.check(Path(receipt["receipt_path"]).is_file(), "compaction_receipt_file")

    registry = mcp.load_registry()
    checks.check(
        registry["policy"]["claude_anthropic"] == "rejected",
        "mcp_claude_rejected",
    )
    blob = str(registry).casefold()
    checks.check("claude mcp 2026" not in blob, "mcp_no_claude_product_ids")
    checks.check(any(row.get("allowed") for row in registry["entries"]), "mcp_has_allow")

    presence = grok_bot.probe_bot_presence()
    checks.check(any(row.get("id") == "cluster" for row in presence), "presence_cluster")
    text = grok_bot.render_grok_bot_presence("")
    checks.check("Presence" in text or "presence" in text.casefold(), "presence_render")

    card = artifacts.make_artifact_card(
        "routine_staged",
        "Routine staged",
        "Draft only",
        status="staged",
        refs=["runtime/routines/staged"],
    )
    checks.check(card["schema"] == artifacts.SCHEMA, "artifact_schema")
    checks.check("[artifact:" in artifacts.render_artifact_card(card), "artifact_render")

    for contract in (
        ROOT / "memory" / "ENGEL_ROUTINES_CONTRACT_V1.md",
        ROOT / "memory" / "ENGEL_CONTEXT_COMPACTION_CONTRACT_V1.md",
        ROOT / "memory" / "ENGEL_MCP_ALLOWLIST_CONTRACT_V1.md",
    ):
        checks.check(contract.is_file(), f"contract_{contract.name}")

    print(
        f"\npassed={checks.passes} failed={len(checks.failures)}"
    )
    for item in checks.failures:
        print("FAIL_DETAIL " + item)
    return 1 if checks.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
