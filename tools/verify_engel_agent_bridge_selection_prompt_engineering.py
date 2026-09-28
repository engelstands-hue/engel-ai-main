#!/usr/bin/env python3
"""Verify prompt-engineering bridge selection is merged into Meeting Room."""
from __future__ import annotations

import json
import py_compile
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULE = ROOT / "engel_prompt_bridge_selection.py"
MEETING_ROOM = ROOT / "engel_agent_meeting_room.py"
MEMORY_SPEC = ROOT / "memory" / "ENGEL_AGENT_MEETING_ROOM_BRIDGE_SELECTION_PROMPT_ENGINEERING_V1.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def verify_memory_spec() -> None:
    require(MEMORY_SPEC.is_file(), f"missing memory spec: {MEMORY_SPEC}")
    text = read(MEMORY_SPEC).lower()
    for needle in (
        "clear communication",
        "four-stage",
        "few-shot",
        "enterprise prompt",
        "research prompt",
        "general chat prompt",
        "model / bridge selection guide",
        "quick decision guide",
        "no fake connected workers",
        "no c: project storage",
    ):
        require(needle in text, f"memory spec missing {needle!r}")


def verify_module_matrix() -> None:
    import engel_prompt_bridge_selection as selector

    expected_keys = {
        "chatgpt",
        "claude",
        "gemini",
        "grok",
        "deepseek",
        "llama",
        "perplexity",
        "image",
        "video",
        "music",
        "voice",
        "cursor",
        "claude_code",
        "codex",
        "game_factory",
        "trading_dashboard",
        "engel_local",
    }
    require(expected_keys.issubset(selector.BRIDGE_PROFILES), "bridge profile matrix incomplete")
    cases = [
        ("write a long document and improve the app language", "Claude-style", "long-document-writing", "Enterprise"),
        ("fix a backend Python function with math edge cases", "ChatGPT / GPT-style", "coding", "Enterprise"),
        ("summarize a massive Google Docs folder", "Gemini-style", "google-long-context", "General Chat"),
        ("research current X/Twitter social trends", "Grok-style", "social-current-events", "Research"),
        ("choose a cheap API at scale open source model", "DeepSeek-style", "budget-api-scale", "General Chat"),
        ("keep this private and local only with no provider", "LLaMA/local model", "privacy-local", "Enterprise"),
        ("research with sources and citations", "Perplexity-style", "research", "Research"),
        ("create a yellow happy face image", "Image-generation bridge", "image-creation", "Enterprise"),
        ("build this in the terminal with pyinstaller", "Claude Code-style", "terminal-coding", "Enterprise"),
        ("send this repo task to Codex cloud coding", "Codex-style", "cloud-coding", "Enterprise"),
        ("use the Game Factory to refine this playable game with better controls", "Game Factory multi-bridge", "game-development", "Enterprise"),
        ("review the Engel dashboard SnapTrade safety rules and paper trading bridge", "Trading Dashboard bridge", "trading-dashboard", "Enterprise"),
        ("Create me a App for Elders", "Local Engel AI", "artifact-creation", "Enterprise"),
        ("Recreate this using Flutter.", "Local Engel AI", "artifact-creation", "Enterprise"),
    ]
    for prompt, bridge, task_type, prompt_type in cases:
        decision = selector.build_prompt_route_decision(prompt)
        require(decision.preferred_bridge == bridge, f"{prompt!r} bridge {decision.preferred_bridge!r} != {bridge!r}")
        require(decision.task_type == task_type, f"{prompt!r} task {decision.task_type!r} != {task_type!r}")
        require(decision.prompt_type == prompt_type, f"{prompt!r} prompt {decision.prompt_type!r} != {prompt_type!r}")
        require("hidden chain-of-thought" in " ".join(decision.prompt_notes), "reasoning policy missing")
        require(any("No provider/model/network/device control" in limit for limit in decision.safety_limits),
                "provider/device safety limit missing")
        require(decision.required_output, "required output missing")
    packet = selector.build_route_prompt_packet("make a pdf", selector.build_prompt_route_decision("make a pdf"))
    require("<engel_meeting_room_route>" in packet, "route packet missing XML-like wrapper")
    require("<preferred_bridge>" in packet and "<safety_limits>" in packet, "route packet missing fields")
    game_decision = selector.build_prompt_route_decision(
        "Use the Game Factory to refine the latest Engel game with longer stages and better controls"
    )
    require(game_decision.bridge_key == "game_factory", "game route must use Game Factory multi-bridge profile")
    require("multi-bridge" in game_decision.preferred_bridge.lower(), "game preferred bridge must make multi-bridge visible")
    require("Game Factory Scout" in game_decision.meeting_bridge, "game meeting bridge must point to Game Factory Scout")
    wrapped = (
        "Conical medium build: split work across Alpha, Beta, Gamma, Sub-Engel, "
        "then assemble on CT246. Create me a App for Elders"
    )
    wrapped_decision = selector.build_prompt_route_decision(wrapped)
    require(
        wrapped_decision.task_type == "artifact-creation",
        f"conical wrapper still stole app-build routing: {wrapped_decision.task_type!r}",
    )
    require(
        wrapped_decision.bridge_key == "engel_local",
        f"elder app build left Local Engel AI: {wrapped_decision.bridge_key!r}",
    )


def verify_meeting_room_integration() -> None:
    source = read(MEETING_ROOM)
    for needle in (
        "build_prompt_route_decision",
        "prompt_route",
        "prompt_route_packet",
        "Bridge Selection / Prompt Route",
        "_latest_prompt_route_ui_text",
        "format_prompt_route_summary",
    ):
        require(needle in source, f"Meeting Room integration missing {needle}")

    import engel_agent_meeting_room as room

    state = room.RoomState(created_at="test")
    rows = room._ensure_order_stations(
        state,
        "Merge the prompt engineering markdown into bridge selection rules.",
    )
    require(rows, "prompt engineering order selected no stations")
    selected_agents = [state.participants[row].type_label for row in rows]
    selected_skills = [state.participants[row].skill_label for row in rows]
    require(
        "Prompt Engineer Agent" in selected_agents,
        f"prompt engineering route did not pick Prompt Engineer Agent: {selected_agents}",
    )
    require(
        "Prompt Engineering Skill" in selected_skills,
        f"prompt engineering route did not pick Prompt Engineering Skill: {selected_skills}",
    )

    tmp_dir = ROOT / "runtime" / "prompt_bridge_selection_verifier"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    old_load = room._load_state
    old_save = room._save_state
    old_order_path = room._order_path
    try:
        test_state = room.RoomState(created_at="test")

        def fake_load():
            return test_state

        def fake_save(state):
            (tmp_dir / "room_state.json").write_text(json.dumps(room.asdict(state), indent=2), encoding="utf-8")

        def fake_order_path(order_id: str):
            return tmp_dir / f"{order_id}.json"

        room._load_state = fake_load
        room._save_state = fake_save
        room._order_path = fake_order_path
        result = room.submit_order_from_engel_main_ui(
            "Research current Android worker WiFi reliability and create a verifier plan",
            source="Verifier",
        )
    finally:
        room._load_state = old_load
        room._save_state = old_save
        room._order_path = old_order_path

    require(result.get("accepted") is True, "Meeting Room submit did not accept test order")
    route = result.get("prompt_route")
    require(isinstance(route, dict), "submit result missing prompt_route")
    require(route.get("prompt_type") == "Research", "submit route did not classify research")
    require("Bridge route:" in result.get("summary", ""), "summary missing bridge route")
    order_path = tmp_dir / f"{result['order_id']}.json"
    payload = json.loads(order_path.read_text(encoding="utf-8"))
    require("prompt_route_packet" in payload, "order record missing route packet")
    require("No fake connected workers" in payload["prompt_route_packet"], "route packet missing safety limits")


def verify_no_forbidden_runtime_startup() -> None:
    source = read(MODULE)
    forbidden = (
        "requests.",
        "httpx.",
        "webbrowser.",
        "subprocess.",
        "OpenAI(",
        "Anthropic(",
        "snapshot_download",
    )
    for needle in forbidden:
        require(needle not in source, f"selector must not start/call external runtime: {needle}")


def main() -> None:
    py_compile.compile(str(MODULE), doraise=True)
    py_compile.compile(str(MEETING_ROOM), doraise=True)
    verify_memory_spec()
    verify_module_matrix()
    verify_meeting_room_integration()
    verify_no_forbidden_runtime_startup()
    print("ENGEL_AGENT_BRIDGE_SELECTION_PROMPT_ENGINEERING_VERIFY_PASS")


if __name__ == "__main__":
    main()
