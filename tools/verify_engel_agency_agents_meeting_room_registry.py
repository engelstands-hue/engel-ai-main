#!/usr/bin/env python3
"""Verify Engel Agency Agents are registered for the Meeting Room."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engel_agency_agents_registry import (  # noqa: E402
    DEFAULT_SOURCE_ROOT,
    REGISTRY_PATH,
    build_registry,
    find_matching_agents,
    load_registry,
)


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def source_markdown_count() -> int:
    excluded = {".git", ".github", "examples", "integrations", "scripts", "__pycache__"}
    total = 0
    for directory in sorted(path for path in DEFAULT_SOURCE_ROOT.iterdir() if path.is_dir()):
        if directory.name in excluded:
            continue
        total += len(list(directory.glob("*.md")))
    return total


def main() -> int:
    try:
        payload = build_registry(DEFAULT_SOURCE_ROOT)
        registry = load_registry(auto_build=False)
        expected = source_markdown_count()
        require(REGISTRY_PATH.exists(), f"registry missing: {REGISTRY_PATH}")
        require(registry.get("agent_count") == expected, f"agent count mismatch: {registry.get('agent_count')} != {expected}")
        require(len(registry.get("agents", [])) == expected, "registry agents array length mismatch")
        missing_cards = [
            agent.get("engel_card_path")
            for agent in registry.get("agents", [])
            if not Path(str(agent.get("engel_card_path") or "")).exists()
        ]
        require(not missing_cards, f"copied card files missing: {missing_cards[:5]}")
        ai_matches = find_matching_agents("Use an AI engineer for production model deployment", limit=3)
        require(any("AI Engineer" in str(agent.get("name")) for agent in ai_matches), "AI Engineer matcher failed")
        sec_matches = find_matching_agents("Need a security review and threat model", limit=5)
        require(sec_matches, "security matcher returned no agents")
        print("ENGEL_AGENCY_AGENTS_MEETING_ROOM_VERIFY_PASS")
        print(f"agents={payload.get('agent_count')}")
        print(f"divisions={payload.get('division_count')}")
        print(f"registry={REGISTRY_PATH}")
        return 0
    except Exception as exc:
        print("ENGEL_AGENCY_AGENTS_MEETING_ROOM_VERIFY_FAIL")
        print(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
