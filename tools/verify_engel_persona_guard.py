#!/usr/bin/env python3
"""Gate for the persona layer: one guard, one marker source, every chat lane.

The chat service is ~14k lines and imports heavy runtime deps, so this verifies it by AST
rather than importing it - the same pattern verify_engel_discord_gif_relevance.py uses.

What it pins:
  1. The guard module itself behaves (delegates to its own selftest).
  2. `_apply_chat_humanizer` scrubs, and scrubs BEFORE the voice-bank capture.
  3. A scrubbed turn is NOT captured as a voice example.
  4. EVERY chat lane finalises through `_apply_chat_humanizer` - this is the claim that
     makes the persona layer "touch every chat lane", so it gets a test.
  5. The Discord bridge delegates instead of keeping a private marker list.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
CHAT_SERVICE = TOOLS / "engel_main_server_chat_http_service.py"
BRIDGE = TOOLS / "engel_discord_bridge.py"
GUARD = TOOLS / "engel_persona_guard.py"

# Every lane that finalises a reply. If a new lane appears, it must either show up here or
# it is bypassing the persona guard entirely.
EXPECTED_LANES = {
    "ct_main_chat_turn",
    "ct_quick_casual_model_receipt",
    "ct_provider_bridge_chat",
    "ct_fast_server_receipt",
    "ct_live_status_receipt",
    "ct_skill_agent_creation_receipt",
}

RESULTS: list[tuple[str, bool]] = []


def check(name: str, condition: bool) -> None:
    RESULTS.append((name, bool(condition)))


def find_function(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def called_names(node: ast.AST) -> list[str]:
    """Every called name, in source order."""
    out: list[str] = []
    for item in ast.walk(node):
        if isinstance(item, ast.Call):
            func = item.func
            if isinstance(func, ast.Name):
                out.append((func.lineno, func.id))
            elif isinstance(func, ast.Attribute):
                out.append((func.lineno, func.attr))
    return [name for _, name in sorted(out)]


def main() -> int:
    for path in (CHAT_SERVICE, BRIDGE, GUARD):
        check(f"{path.name} exists", path.exists())
    if not all(ok for _, ok in RESULTS):
        for name, ok in RESULTS:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        return 1

    # ---- 1. the guard's own behaviour ------------------------------------
    proc = subprocess.run(
        [sys.executable, str(GUARD), "--selftest"],
        capture_output=True, text=True, timeout=180, check=False,
    )
    check("persona guard selftest passes", proc.returncode == 0)
    if proc.returncode != 0:
        print(proc.stdout[-2000:])

    service_src = CHAT_SERVICE.read_text(encoding="utf-8", errors="replace")
    service_tree = ast.parse(service_src)

    # ---- 2 & 3. the chokepoint -------------------------------------------
    humanizer = find_function(service_tree, "_apply_chat_humanizer")
    check("_apply_chat_humanizer exists", humanizer is not None)
    if humanizer is not None:
        body_src = ast.get_source_segment(service_src, humanizer) or ""
        check("the chokepoint imports the shared guard",
              "from engel_persona_guard import scrub_persona_leak" in body_src)
        check("the chokepoint calls the scrubber", "scrub_persona_leak(" in body_src)

        order = called_names(humanizer)
        has_scrub = "scrub_persona_leak" in order
        has_capture = "_maybe_capture_voice_example" in order
        check("the chokepoint still captures voice examples", has_capture)
        if has_scrub and has_capture:
            check("scrubbing happens BEFORE the voice-bank capture",
                  order.index("scrub_persona_leak") < order.index("_maybe_capture_voice_example"))
        else:
            check("scrubbing happens BEFORE the voice-bank capture", False)

        # a leaked turn must not be captured as a voice sample
        check("a scrubbed turn is not captured into the voice bank",
              "if not persona_scrubbed:" in body_src)
        check("the scrub is fail-open (wrapped in try/except)",
              any(isinstance(node, ast.Try) for node in ast.walk(humanizer)))
        check("the receipt records when the guard fired", '"persona_guard"' in body_src)

    # ---- 4. every lane goes through it -----------------------------------
    lanes: set[str] = set()
    for node in ast.walk(service_tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "_apply_chat_humanizer":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    lanes.add(arg.value)
    check(f"all {len(EXPECTED_LANES)} known chat lanes finalise through the guard",
          EXPECTED_LANES.issubset(lanes))
    missing = EXPECTED_LANES - lanes
    if missing:
        print(f"    missing lanes: {sorted(missing)}")
    unknown = lanes - EXPECTED_LANES
    if unknown:
        # Not a failure - a new lane is fine, it just has to be acknowledged here.
        print(f"    NOTE new lane(s) now covered, add to EXPECTED_LANES: {sorted(unknown)}")

    # ---- 5. the bridge delegates -----------------------------------------
    bridge_src = BRIDGE.read_text(encoding="utf-8", errors="replace")
    bridge_tree = ast.parse(bridge_src)
    stripper = find_function(bridge_tree, "strip_peer_framing_echo")
    check("bridge strip_peer_framing_echo exists", stripper is not None)
    if stripper is not None:
        strip_src = ast.get_source_segment(bridge_src, stripper) or ""
        check("the bridge delegates to the shared guard",
              "from engel_persona_guard import scrub_persona_leak" in strip_src)
        check("the bridge no longer walks a private marker list",
              "_PEER_FRAMING_ECHO_MARKERS" not in strip_src)
        check("the bridge delegation is fail-open",
              any(isinstance(node, ast.Try) for node in ast.walk(stripper)))

    # ---- markers really are single-source --------------------------------
    sys.path.insert(0, str(TOOLS))
    try:
        import engel_persona_guard as guard

        markers = guard.persona_leak_markers()
        check("guard exposes a non-trivial marker set", len(markers) > 20)
        try:
            from engel_governor import CONTRACT_ECHO_MARKERS

            check("the governor's contract markers are included",
                  all(str(m).casefold() in markers for m in CONTRACT_ECHO_MARKERS))
        except Exception:
            check("governor markers unavailable but guard still loads (fail-open)", True)
    except Exception as exc:  # noqa: BLE001
        check(f"guard imports cleanly ({exc})", False)

    passed = sum(1 for _, ok in RESULTS if ok)
    for name, ok in RESULTS:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n{passed}/{len(RESULTS)} checks passed")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
