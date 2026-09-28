#!/usr/bin/env python3
"""Gate for the Engel next-stage storage-pull merge."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import engel_next_stage_runner as runner  # noqa: E402
from engel_ai_update_routes import resolve_update_route  # noqa: E402

STAGE = ROOT / "runtime" / "next_stage"
COMPANION = ROOT / "runtime" / "gpu_models" / "engel-companion-002.gguf"
ROUTES = ROOT / "engel_ai_update_routes.py"
EXPLORER = ROOT / "engel_route_explorer.py"
TRADE = STAGE / "trading_desk" / "trade.ts"
MCP = STAGE / "mcp" / "engel_playwright_mcp.json"
SKILL_REG = ROOT / "memory" / "skills" / "ENGEL_SAVED_SKILL_REGISTRY.json"
AGENT_REG = ROOT / "memory" / "agents" / "ENGEL_SAVED_AGENT_REGISTRY.json"

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def main() -> int:
    manifest = json.loads((STAGE / "MANIFEST.json").read_text(encoding="utf-8"))
    check("manifest_ok", bool(manifest.get("ok")))
    check("companion_present", COMPANION.is_file(), str(_size(COMPANION)))
    check("companion_size", _size(COMPANION) > 2_000_000_000)
    check("disarmed_md", (STAGE / "trading_desk" / "DISARMED.md").is_file())
    trade = TRADE.read_text(encoding="utf-8", errors="replace") if TRADE.is_file() else ""
    check("trade_clob_flag", "ENGEL_CLOB_DISARMED" in trade)
    check("trade_post_guard", "No live orders" in trade or "CLOB is DISARMED" in trade)
    mcp = json.loads(MCP.read_text(encoding="utf-8")) if MCP.is_file() else {}
    check("mcp_off", mcp.get("enabled_by_default") is False)
    check("mcp_no_unrestricted", mcp.get("unrestricted_web") is False)
    origins = list(mcp.get("allowed_origins") or [])
    check("mcp_localhost_only", origins == ["http://127.0.0.1", "http://localhost"])
    check("skills_source_market", (STAGE / "skills_source" / "market-regimes.SKILL.md").is_file())
    check(
        "skills_source_demo",
        (STAGE / "skills_source" / "learn-from-demonstration.SKILL.md").is_file(),
    )
    skills = (json.loads(SKILL_REG.read_text(encoding="utf-8")).get("skills") or {}) if SKILL_REG.is_file() else {}
    for slug in runner.REQUIRED_SKILLS:
        check("skill_" + slug, slug in skills)
    agents = (json.loads(AGENT_REG.read_text(encoding="utf-8")).get("agents") or {}) if AGENT_REG.is_file() else {}
    check("agent_prototyper", runner.REQUIRED_AGENT in agents)
    hermes = ROOT / "workflows" / "sub_engel_nodes" / "hermes_patch" / "Reconnect-SubEngel-NoC.ps1"
    check("hermes_patch_copied", hermes.is_file())
    routes = ROUTES.read_text(encoding="utf-8")
    explorer = EXPLORER.read_text(encoding="utf-8")
    check("route_status_const", "engel.next_stage.status" in routes)
    check("explorer_group", 'startswith("engel.next_stage")' in explorer)
    check(
        "alias_status",
        resolve_update_route("next stage status") == "engel.next_stage.status",
    )
    check(
        "alias_companion",
        resolve_update_route("companion 3b status") == "engel.next_stage.companion",
    )
    check(
        "alias_safety",
        resolve_update_route("next stage safety") == "engel.next_stage.safety",
    )
    status = runner.render_next_stage_status()
    check("status_mentions_untouched", "LIVE_7B_UNTOUCHED" in status)
    check("status_mentions_disarmed", "CLOB_DISARMED" in status)
    leaked = _secret_hits(STAGE)
    check("no_secret_files", not leaked, ",".join(leaked[:5]))
    failed = [name for name, ok, _ in CHECKS if not ok]
    print("RESULT " + ("PASS" if not failed else "FAIL") + f" {len(CHECKS) - len(failed)}/{len(CHECKS)}")
    return 0 if not failed else 1


def _size(path: Path) -> int:
    try:
        return int(path.stat().st_size) if path.is_file() else 0
    except OSError:
        return 0


def _secret_hits(root: Path) -> list[str]:
    needles = ("gateway.json", "box-secrets", "host-secrets", "POLYMARKET_PRIVATE_KEY")
    hits: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        text_name = str(path.relative_to(root)).replace("\\", "/")
        if any(n.lower() in name or n.lower() in text_name.lower() for n in needles if n != "POLYMARKET_PRIVATE_KEY"):
            hits.append(text_name)
            continue
        if path.suffix.lower() in {".md", ".json", ".ts", ".js", ".txt", ".yaml"}:
            try:
                blob = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "POLYMARKET_PRIVATE_KEY" in blob and "Do not set POLYMARKET_PRIVATE_KEY" not in blob and "Stay DISARMED" not in blob and "DISARMED" not in blob:
                hits.append(text_name)
    return hits


if __name__ == "__main__":
    raise SystemExit(main())
