"""Engel AI Main next-stage merge — read-only status surface.

Staged from the 2026-08-25 storage-pull. Live CT246 Qwen 7B LoRA stays in place.
Trading CLOB stays disarmed. Playwright MCP stays localhost-only and off by default.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
STAGE = ROOT / "runtime" / "next_stage"
COMPANION = ROOT / "runtime" / "gpu_models" / "engel-companion-002.gguf"
SKILL_REGISTRY = ROOT / "memory" / "skills" / "ENGEL_SAVED_SKILL_REGISTRY.json"
AGENT_REGISTRY = ROOT / "memory" / "agents" / "ENGEL_SAVED_AGENT_REGISTRY.json"

REQUIRED_SKILLS = (
    "engel-playwright-mcp",
    "engel-sub-engel-reconnect",
    "engel-market-regimes",
    "engel-learn-from-demonstration",
    "engel-training-agents-factory",
    "engel-companion-3b-lane",
    "engel-local-speech-whisper-piper",
    "engel-trading-desk-disarmed",
)
REQUIRED_AGENT = "engel-prototyper"

HARD_SKIP = (
    "POLYMARKET_PRIVATE_KEY stays unset",
    "Bridge gateway tokens and host-secrets were not copied",
    "June 21 Mistral Sub-Engel exe is not installed over live Qwen 7B",
    "Playwright MCP is not a live unrestricted-web Grok MCP",
    "Stripe Link is gated, not a default MCP",
)


def _bytes(path: Path) -> int:
    try:
        return int(path.stat().st_size) if path.is_file() else 0
    except OSError:
        return 0


def _dir_count(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for p in path.rglob("*") if p.is_file())


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def next_stage_inventory() -> dict[str, object]:
    manifest = _load_json(STAGE / "MANIFEST.json")
    lanes = _load_json(STAGE / "LANES.json")
    mcp = _load_json(STAGE / "mcp" / "engel_playwright_mcp.json")
    skills = _load_json(SKILL_REGISTRY).get("skills") or {}
    agents = _load_json(AGENT_REGISTRY).get("agents") or {}
    trade_src = STAGE / "trading_desk" / "trade.ts"
    trade_text = trade_src.read_text(encoding="utf-8", errors="replace") if trade_src.is_file() else ""
    companion_bytes = _bytes(COMPANION)
    return {
        "schema": "engel_next_stage_inventory_v1",
        "ok": bool(manifest.get("ok")) and companion_bytes > 2_000_000_000,
        "stage": str(STAGE),
        "live_7b_untouched": True,
        "clob_disarmed": (STAGE / "trading_desk" / "DISARMED.md").is_file()
        and "ENGEL_CLOB_DISARMED" in trade_text,
        "playwright_mcp_enabled_by_default": bool(mcp.get("enabled_by_default")),
        "playwright_unrestricted_web": bool(mcp.get("unrestricted_web")),
        "companion_gguf": {
            "path": str(COMPANION),
            "present": COMPANION.is_file(),
            "bytes": companion_bytes,
            "live": False,
            "note": "Daily Local / phone RAM lane. Not CT246 live 7B chat.",
        },
        "parts": {
            "playwright_mcp": _dir_count(STAGE / "playwright_mcp"),
            "trading_desk": _dir_count(STAGE / "trading_desk"),
            "training_agents": _dir_count(STAGE / "training_agents"),
            "hermes_sub_engel": _dir_count(STAGE / "hermes_sub_engel"),
            "datasets": _dir_count(STAGE / "datasets"),
            "extra_lora_ue5": _dir_count(STAGE / "extra_lora_ue5"),
            "speech": _dir_count(STAGE / "speech"),
            "engel_swarm": _dir_count(STAGE / "engel_swarm"),
            "sub_engel_gui": _dir_count(STAGE / "sub_engel_gui"),
            "linux_sandbox": _dir_count(STAGE / "linux_sandbox"),
            "linux_ornith": _dir_count(STAGE / "linux_ornith"),
            "gated": _dir_count(STAGE / "gated"),
            "skills_source": _dir_count(STAGE / "skills_source"),
        },
        "skills_present": [slug for slug in REQUIRED_SKILLS if slug in skills],
        "skills_missing": [slug for slug in REQUIRED_SKILLS if slug not in skills],
        "agent_present": REQUIRED_AGENT in agents,
        "lanes": lanes,
        "hard_skip": list(HARD_SKIP),
        "manifest_finished_at_utc": manifest.get("finished_at_utc"),
    }


def _lines_from_inventory(inv: dict[str, object]) -> list[str]:
    companion = inv.get("companion_gguf") if isinstance(inv.get("companion_gguf"), dict) else {}
    parts = inv.get("parts") if isinstance(inv.get("parts"), dict) else {}
    lines = [
        "Engel Next-Stage Merge",
        "",
        "Status: STAGED / LIVE_7B_UNTOUCHED / CLOB_DISARMED / MCP_OFF_BY_DEFAULT",
        "Stage: " + str(inv.get("stage") or STAGE),
        "Manifest finished: " + str(inv.get("manifest_finished_at_utc") or "unknown"),
        "",
        "Companion 3B GGUF: "
        + ("PRESENT" if companion.get("present") else "MISSING")
        + "  "
        + str(companion.get("bytes") or 0)
        + " bytes  live="
        + str(companion.get("live")),
        "CLOB disarmed: " + str(inv.get("clob_disarmed")),
        "Playwright MCP default-on: " + str(inv.get("playwright_mcp_enabled_by_default")),
        "Playwright unrestricted web: " + str(inv.get("playwright_unrestricted_web")),
        "Prototyper agent: " + ("PRESENT" if inv.get("agent_present") else "MISSING"),
        "",
        "Extracted parts (file counts):",
    ]
    for key, count in parts.items():
        lines.append(f"  - {key}: {count}")
    lines.extend(["", "Saved skills:"])
    for slug in inv.get("skills_present") or []:
        lines.append("  - " + str(slug))
    missing = list(inv.get("skills_missing") or [])
    if missing:
        lines.append("Missing skills: " + ", ".join(str(s) for s in missing))
    lines.extend(["", "Hard skip:"])
    for item in inv.get("hard_skip") or HARD_SKIP:
        lines.append("  - " + str(item))
    lines.extend(
        [
            "",
            "Safety:",
            "- READ_ONLY_STATUS_ONLY",
            "- NO_LIVE_7B_SWAP",
            "- NO_CLOB_POSTING",
            "- NO_PROVIDER_MODEL_NETWORK",
            "- NO_TRUSTED_MEMORY_WRITE",
            "- NO_BACKGROUND_WORKER",
        ]
    )
    return lines


def render_next_stage_status(payload: str = "") -> str:
    del payload
    return "\n".join(_lines_from_inventory(next_stage_inventory()))


def render_next_stage_inventory(payload: str = "") -> str:
    del payload
    inv = next_stage_inventory()
    return "\n".join(
        [
            "Engel Next-Stage Inventory",
            "",
            json.dumps(inv, indent=2),
            "",
            "Safety: READ_ONLY_STATUS_ONLY / NO_LIVE_7B_SWAP / NO_CLOB_POSTING",
        ]
    )


def render_next_stage_companion(payload: str = "") -> str:
    del payload
    inv = next_stage_inventory()
    companion = inv.get("companion_gguf") if isinstance(inv.get("companion_gguf"), dict) else {}
    return "\n".join(
        [
            "Engel Companion 3B Lane",
            "",
            "This is the merged Engel 3B GGUF for Daily Local / phone RAM.",
            "It does not replace live CT246 Qwen 2.5-7B-Instruct + khdeh9t1 LoRA.",
            "",
            "Path: " + str(companion.get("path") or COMPANION),
            "Present: " + str(companion.get("present")),
            "Bytes: " + str(companion.get("bytes") or 0),
            "Live chat: no",
            "Promotion token required to load over 7B: APPROVE_ENGEL_MODEL_PROMOTION_V1",
            "",
            "CT246 already has stock qwen2.5-3b-instruct and qwen2.5-coder-3b-instruct.",
            "Companion-002 is the Engel-merged 3B, staged beside those, not over them.",
            "",
            "Safety: READ_ONLY_STATUS_ONLY / NOT_LOADED / NOT_LIVE_7B",
        ]
    )


def render_next_stage_safety(payload: str = "") -> str:
    del payload
    inv = next_stage_inventory()
    return "\n".join(
        [
            "Engel Next-Stage Safety",
            "",
            "Live 7B chat: UNTOUCHED",
            "CLOB posting: DISARMED",
            "Playwright MCP: staged, localhost/file only, enabled_by_default=false",
            "Stripe Link: gated, not default MCP",
            "Secrets: not copied (gateway.json, box-secrets, host-secrets, POLYMARKET_PRIVATE_KEY)",
            "Old Mistral Sub-Engel installer: skipped",
            "Go stdlib / uapi dumps: skipped",
            "",
            "CLOB disarmed flag: " + str(inv.get("clob_disarmed")),
            "Playwright default-on: " + str(inv.get("playwright_mcp_enabled_by_default")),
            "Unrestricted web: " + str(inv.get("playwright_unrestricted_web")),
            "",
            "Hard skip:",
            *[("  - " + item) for item in HARD_SKIP],
            "",
            "Safety: READ_ONLY_STATUS_ONLY / NO_PROVIDER_MODEL_NETWORK / NO_QUEUE_MUTATION",
        ]
    )
