"""Claude-free MCP allowlist desk — landscape gap #4 (read-only).

Guardian-gated registry of allowed local/xAI-open MCP server labels.
Does not connect to MCP servers, does not import Claude connectors,
does not call providers.

Contract: memory/ENGEL_MCP_ALLOWLIST_CONTRACT_V1.md
Routes: engel.mcp_allowlist.*
Verifier: tools/verify_engel_mcp_allowlist.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engel_project_paths import resolve_engel_app_root

ROOT = resolve_engel_app_root(__file__)
REGISTRY_PATH = ROOT / "memory" / "ENGEL_MCP_ALLOWLIST_REGISTRY_V1.json"
CONTRACT_PATH = ROOT / "memory" / "ENGEL_MCP_ALLOWLIST_CONTRACT_V1.md"

SCHEMA = "engel_mcp_allowlist_registry_v1"

# Seed allowlist: local Engel + open/xAI-oriented labels only. No Claude/Anthropic.
DEFAULT_ENTRIES: list[dict[str, Any]] = [
    {
        "id": "engel-local-tools",
        "label": "Engel local tool surface",
        "kind": "local",
        "transport": "in-process",
        "endpoint": "engel routes / skills",
        "allowed": True,
        "notes": "Default Engel route/skill tools. Not a remote MCP socket.",
    },
    {
        "id": "hermes-native-mcp-local",
        "label": "Hermes native MCP (local skills)",
        "kind": "local",
        "transport": "skill-pack",
        "endpoint": ".agents/skills/engel-hermes-native-mcp",
        "allowed": True,
        "notes": "Local skill documentation only until Josh approves a live MCP bind.",
    },
    {
        "id": "xai-open-mcp-pattern",
        "label": "xAI-style remote MCP pattern (docs only)",
        "kind": "pattern",
        "transport": "none",
        "endpoint": "docs only — no live server_url",
        "allowed": False,
        "notes": (
            "Tracked as a design pattern from xAI public docs. Live connect needs "
            "a separate Josh Bucket 3 approval. Claude MCP products are rejected."
        ),
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_registry() -> dict[str, Any]:
    if REGISTRY_PATH.is_file():
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    payload = {
        "schema": SCHEMA,
        "updated_at_utc": _now(),
        "policy": {
            "claude_anthropic": "rejected",
            "live_connect_default": False,
            "josh_gate_for_live_bind": "Bucket 3",
        },
        "entries": DEFAULT_ENTRIES,
    }
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return payload


def list_entries(*, allowed_only: bool = False) -> list[dict[str, Any]]:
    rows = list(load_registry().get("entries") or [])
    if allowed_only:
        return [row for row in rows if row.get("allowed") is True]
    return rows


def render_mcp_allowlist_docs(payload: str = "") -> str:
    del payload
    return "\n".join(
        [
            "Engel MCP Allowlist (Claude-free)",
            "",
            "Read-only Guardian desk for which MCP-shaped tools may ever be considered.",
            "Josh 2026-09-14: no Claude / Anthropic MCP products.",
            "This desk does not open sockets and does not auto-inject remote tools.",
            "",
            "Phrases: engel mcp allowlist | engel mcp allowlist status | engel mcp allowlist docs",
            f"Registry: {REGISTRY_PATH.relative_to(ROOT).as_posix()}",
            f"Contract: {CONTRACT_PATH.relative_to(ROOT).as_posix()}",
        ]
    )


def render_mcp_allowlist_status(payload: str = "") -> str:
    del payload
    registry = load_registry()
    entries = list(registry.get("entries") or [])
    allowed = [row for row in entries if row.get("allowed") is True]
    lines = [
        "Engel MCP Allowlist status",
        "",
        f"entries: {len(entries)}",
        f"allowed: {len(allowed)}",
        f"claude_anthropic: {registry.get('policy', {}).get('claude_anthropic')}",
        f"live_connect_default: {registry.get('policy', {}).get('live_connect_default')}",
        "",
    ]
    for row in entries:
        flag = "ALLOW" if row.get("allowed") else "DENY/PATTERN"
        lines.append(
            f"- [{flag}] {row.get('id')}: {row.get('label')} ({row.get('kind')})"
        )
        lines.append(f"  {row.get('notes')}")
    return "\n".join(lines)


def render_mcp_allowlist_list(payload: str = "") -> str:
    del payload
    return render_mcp_allowlist_status("")
