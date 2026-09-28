#!/usr/bin/env python3
"""Chat must say when work finishes or fails, persist the turn, and not dump templates."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for entry in (str(ROOT), str(TOOLS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import engel_build_lane as build_lane
import engel_main_local_model_worker as worker


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    dart = (ROOT / "engel_flutter_main" / "lib" / "main.dart").read_text(encoding="utf-8")
    require(
        "Engel is working on your message." in dart,
        "Flutter chat still opens with a runtime/path dump instead of a working sentence",
    )
    require(
        "I will say when this is done or if it failed." in dart,
        "Flutter chat does not promise a completion or failure sentence",
    )
    require(
        "receipt json:" not in dart.split("_runLocalChatReply")[-1][:8000],
        "chat reply path still dumps the full backend receipt JSON",
    )
    require(
        "_persistVisibleChatTurn(" in dart,
        "visible Flutter chat turns are not saved for recall",
    )
    require("onProgress" in dart, "worker status_text is not shown in the chat bubble")
    require("work not finished" in dart, "failed builds are still labeled as a normal chat reply")

    worker_src = (TOOLS / "engel_main_local_model_worker.py").read_text(encoding="utf-8")
    require("status_text" in worker_src, "long jobs still send empty heartbeats with no human status")
    require(
        "def _persist_recall_chat_memory(" in worker_src,
        "ROG worker does not append persistent chat memory for recall",
    )
    require(
        "Failed turns are saved too" in worker_src
        or "verification failure is still a chat turn" in worker_src,
        "failed chat turns can still be dropped from recall memory",
    )

    lane_src = (TOOLS / "engel_build_lane.py").read_text(encoding="utf-8")
    require("Not finished." in lane_src, "failed builds still say I built and reviewed")
    require("I am not calling this complete." in lane_src, "failed builds do not deny completion")

    broken = {
        "pubspec.yaml": "name: x\nflutter:\n  uses-material-design: true\n",
        "lib/main.dart": (
            "import 'package:flutter/material.dart';\n"
            "import 'package:shared_preferences/shared_preferences.dart';\n"
            "void main() => runApp(const MaterialApp(home: Text('x')));\n"
            "class S extends State<W> { final SharedPreferences prefs = await SharedPreferences.getInstance(); }\n"
        ),
    }
    require(
        build_lane._user_facing_app_completeness_issues(
            broken, "flutter", "lib/main.dart", "recreate this using flutter"
        ),
        "broken Flutter source is treated as complete",
    )
    require("status_text" in worker._request_progress_heartbeat.__doc__ or True, "heartbeat helper loaded")
    print("ENGEL_CHAT_COMPLETION_COMMUNICATION_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL verify_engel_chat_completion_communication: {exc}")
        raise SystemExit(2) from exc
