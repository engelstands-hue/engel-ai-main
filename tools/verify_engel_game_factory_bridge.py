#!/usr/bin/env python3
"""Verify Engel Game Factory bridge and generated game refinement contract."""
from __future__ import annotations

import json
import py_compile
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def assert_no_c_temp(value: object) -> None:
    text = json.dumps(value, indent=2) if not isinstance(value, str) else value
    forbidden = ("C:\\Users\\ziese\\AppData\\Local\\Temp", "AppData\\Local\\Temp")
    require(not any(item in text for item in forbidden), "Game Factory verifier found C: temp leakage")


def verify_bridge_packet() -> None:
    import engel_game_factory_bridge as bridge

    result = bridge.run_game_factory_refinement_packet(
        "Use the Game Factory to refine the latest Engel game with longer stages, better controls, dash, smoother jumping, weapon cycling, and expanded touch controls.",
        source="Verifier",
    )
    require(result.get("ok") is True, "Game Factory bridge did not return ok")
    require(result.get("bridge") == "Game Factory Scout (Engel Meeting Room)", "wrong bridge label")
    report = Path(str(result.get("report_path") or ""))
    status = Path(str(result.get("status_path") or ""))
    require(report.is_file(), f"missing bridge report: {report}")
    require(status.is_file(), f"missing bridge status: {status}")
    report_text = read(report)
    for needle in ("longer stage", "dash/sprint", "jump buffering", "weapon cycling", "No provider API key"):
        require(needle.lower() in report_text.lower(), f"bridge report missing {needle!r}")
    assert_no_c_temp(result)
    assert_no_c_temp(report_text)


def verify_generated_game_contract() -> None:
    from engel_ui_executable_results import execute_ui_result_request

    test_root = ROOT / "runtime" / "game_factory_verifier"
    if test_root.exists():
        shutil.rmtree(test_root)
    test_root.mkdir(parents=True, exist_ok=True)

    import os

    os.environ["ENGEL_EXECUTABLE_RESULTS_DIR"] = str(test_root)
    result = execute_ui_result_request(
        "Use the Game Factory to refine the latest Engel Ten Sector Rescue game. Make stages longer and improve controls with dash, smoother jumping, weapon cycling, and better touch controls.",
        meeting_summary="Meeting Room updated: Game Factory Scout Agent returned, Game Developer Agent assigned, UI Agent assigned, Verifier assigned",
        returned_previews=["Game Factory: longer stage parts and control polish contract ready"],
    )
    require(result.get("accepted") is True, f"game result not accepted: {result}")
    require(result.get("kind") == "game", f"wrong result kind: {result.get('kind')}")
    out_dir = Path(str(result.get("artifact_dir")))
    game_js = out_dir / "game.js"
    index = out_dir / "index.html"
    readme = out_dir / "README.md"
    require(game_js.is_file() and index.is_file() and readme.is_file(), "game artifact missing expected files")
    game_text = read(game_js)
    index_text = read(index)
    for needle in (
        "const PART_WIDTH = 1280",
        "controlUpgrades",
        "dashCd",
        "jumpBufferMs",
        "coyoteMs",
        "cycleWeapon()",
        "unlockedWeapons",
    ):
        require(needle in game_text, f"generated game missing {needle}")
    for needle in ('data-control="dash"', 'data-control="cycle"', "Shift dash/sprint", "Q cycle weapon"):
        require(needle in index_text, f"generated game HTML missing {needle}")
    require("longer parts per stage" in read(readme), "README missing longer stage refinement")
    assert_no_c_temp(result)


def main() -> None:
    for module in (
        ROOT / "engel_game_factory_bridge.py",
        ROOT / "engel_agent_meeting_room.py",
        ROOT / "engel_ui_executable_results.py",
    ):
        py_compile.compile(str(module), doraise=True)
    verify_bridge_packet()
    verify_generated_game_contract()
    print("OK: Engel Game Factory bridge verified")


if __name__ == "__main__":
    main()
