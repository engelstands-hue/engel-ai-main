#!/usr/bin/env python3
"""Gates so Engel cannot call a print-only stub a finished user-facing app."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for entry in (str(ROOT), str(TOOLS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import engel_build_lane as build_lane
import engel_prompt_bridge_selection as selector
import run_engel_ui_chat_meeting_room_llm as ui_lane


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    prompt = "Create me a App for Elders"
    wrapped = (
        "Conical medium build: split work across Alpha, Beta, Gamma, Sub-Engel, "
        "then assemble on CT246. Create me a App for Elders"
    )
    require(
        build_lane.is_build_request(prompt) is not None,
        "elder app request is not a build order",
    )
    require(
        build_lane.is_user_facing_app_request(prompt) is True,
        "elder app request is not treated as a user-facing app",
    )
    lang, entry, _run, _tool, _bin = build_lane._infer_build_language_for_request(
        prompt.casefold()
    )
    require(lang == "web", f"underspecified app defaulted to {lang!r} instead of web")
    require(entry == "index.html", f"web entry mismatch: {entry!r}")
    py_lang, _py_entry, *_rest = build_lane._infer_build_language_for_request(
        "build me a python app called planner with tests"
    )
    require(py_lang == "python", f"explicit python app lost its language: {py_lang!r}")
    brief = build_lane.expand_underspecified_app_brief(prompt)
    require("emergency" in brief.casefold(), "elder brief missing emergency/help")
    require("reminders" in brief.casefold(), "elder brief missing reminders")
    require("contacts" in brief.casefold(), "elder brief missing contacts")
    stub_issues = build_lane._user_facing_app_completeness_issues(
        {
            "main.py": (
                "def run_app():\n"
                "    print('Engel AI Main App for Elders')\n\n"
                "if __name__ == '__main__':\n"
                "    run_app()\n"
            ),
            "README.md": "# Create me a App for Elders\n",
            "test_main.py": "import unittest\nfrom main import run_app\n",
        },
        "python",
        "main.py",
        prompt,
    )
    require(stub_issues, "print-only elder stub passed completeness")
    require(
        any("print-only" in item for item in stub_issues),
        f"print-only gate missing: {stub_issues}",
    )
    require(
        any("emergency" in item or "missing visible" in item for item in stub_issues),
        f"elder feature gate missing: {stub_issues}",
    )
    review = build_lane._static_review(
        {
            "main.py": "print('hi')\n",
        },
        "python",
        "main.py",
        prompt,
    )
    require(review.get("ok") is False, "static review accepted a print-only app")
    assignment = ui_lane._conical_operator_request_block(prompt)
    require("Implied requirements" in assignment, "phone assignment lost implied requirements")
    require("emergency" in assignment.casefold(), "phone assignment missing emergency/help")
    require(
        selector.infer_task_type(prompt) == "artifact-creation",
        selector.infer_task_type(prompt),
    )
    require(
        selector.infer_task_type(wrapped) == "artifact-creation",
        f"conical wrapper still classified as {selector.infer_task_type(wrapped)!r}",
    )
    require(
        "print('hi')" not in (TOOLS / "engel_build_lane.py").read_text(encoding="utf-8"),
        "build generator still shows print('hi') as the FILE example",
    )
    require(
        build_lane.strip_overwrite_rebuild_wording(
            "Overwrite and rebuild: Create me a App for Elders"
        )
        == "Create me a App for Elders",
        "rebuild wording still pollutes the workspace slug",
    )
    flutter_prompt = "Recreate this using Flutter."
    require(
        build_lane.is_build_request(flutter_prompt) is not None,
        "Flutter recreate request fell through to chat",
    )
    require(
        build_lane.is_recreate_this_request(flutter_prompt) is True,
        "Flutter recreate request is not a recreate-this order",
    )
    flutter_lang, flutter_entry, *_flutter_rest = (
        build_lane._infer_build_language_for_request(flutter_prompt.casefold())
    )
    require(
        flutter_lang == "flutter",
        f"Flutter recreate defaulted to {flutter_lang!r}",
    )
    require(flutter_entry == "lib/main.dart", f"Flutter entry mismatch: {flutter_entry!r}")
    require(
        selector.infer_task_type(flutter_prompt) == "artifact-creation",
        f"Flutter recreate classified as {selector.infer_task_type(flutter_prompt)!r}",
    )
    stub_flutter = build_lane._user_facing_app_completeness_issues(
        {
            "pubspec.yaml": "name: x\n",
            "lib/main.dart": "void main() { print('hi'); }\n",
        },
        "flutter",
        "lib/main.dart",
        flutter_prompt,
    )
    require(stub_flutter, "print-only Flutter stub passed completeness")
    review_flutter = build_lane._static_review(
        {
            "lib/main.dart": "void main() {}\n",
        },
        "flutter",
        "lib/main.dart",
        flutter_prompt,
    )
    require(review_flutter.get("ok") is False, "static review accepted a non-Flutter package")
    broken_prefs = build_lane._static_review(
        {
            "pubspec.yaml": "name: x\nflutter:\n  uses-material-design: true\n",
            "lib/main.dart": (
                "import 'package:flutter/material.dart';\n"
                "import 'package:shared_preferences/shared_preferences.dart';\n"
                "void main() => runApp(const MaterialApp(home: Text('x')));\n"
                "class S extends State<W> { final SharedPreferences prefs = await SharedPreferences.getInstance(); }\n"
            ),
        },
        "flutter",
        "lib/main.dart",
        flutter_prompt,
    )
    require(broken_prefs.get("ok") is False, "Flutter shared_preferences mismatch passed static review")
    print("ENGEL_UNDERSPECIFIED_APP_BUILD_GATES_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
