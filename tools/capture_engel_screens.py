from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import time
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT_ROOT = APP_ROOT / "reports" / "screenshots"


def _timestamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _process_events(app, cycles: int = 8) -> None:
    for _ in range(cycles):
        app.processEvents()
        time.sleep(0.05)


def _save_widget(app, widget, path: Path) -> dict[str, object]:
    widget.show()
    _process_events(app)
    pixmap = widget.grab()
    ok = bool(pixmap.save(str(path)))
    size = path.stat().st_size if path.exists() else 0
    return {
        "path": str(path),
        "ok": ok and size > 0,
        "bytes": size,
        "width": pixmap.width(),
        "height": pixmap.height(),
    }


def capture_screens(output_dir: Path) -> list[dict[str, object]]:
    sys.path.insert(0, str(APP_ROOT))

    from engel_desktop_v2 import HAS_QT, QApplication, EngelDesktopV2, STYLESHEET

    if not HAS_QT:
        raise RuntimeError("Qt is not available; install PyQt6 or PySide6.")

    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(["capture_engel_screens"])
    app.setStyleSheet(STYLESHEET)

    results: list[dict[str, object]] = []
    desktop = EngelDesktopV2()
    desktop.resize(1280, 760)

    tabs = [
        ("desktop_goals", 0),
        ("desktop_models", 1),
        ("desktop_routes", 2),
    ]
    for label, index in tabs:
        desktop.right_tabs.setCurrentIndex(index)
        _process_events(app)
        results.append(_save_widget(app, desktop, output_dir / f"{label}.png"))

    try:
        from engel_agent_meeting_room import AgentMeetingRoomWindow

        meeting = AgentMeetingRoomWindow()
        meeting.resize(1280, 760)
        results.append(_save_widget(app, meeting, output_dir / "agent_meeting_room.png"))
        meeting.close()
    except Exception as exc:
        results.append(
            {
                "path": str(output_dir / "agent_meeting_room.png"),
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        from engel_research_thinking_screen import ResearchThinkingScreen

        thinking = ResearchThinkingScreen()
        thinking.resize(720, 520)
        results.append(_save_widget(app, thinking, output_dir / "research_thinking_screen.png"))
        thinking.close()
    except Exception as exc:
        results.append(
            {
                "path": str(output_dir / "research_thinking_screen.png"),
                "ok": False,
                "error": str(exc),
            }
        )

    desktop.close()
    _process_events(app, cycles=2)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture Engel GUI surfaces for QA.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=SCREENSHOT_ROOT / f"polish_{_timestamp()}",
        help="Directory for PNG screenshots and manifest.",
    )
    parser.add_argument(
        "--offscreen",
        action="store_true",
        help="Request Qt offscreen rendering before importing Qt.",
    )
    args = parser.parse_args(argv)

    if args.offscreen:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    results = capture_screens(args.output_dir)
    manifest = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "app_root": str(APP_ROOT),
        "screens": results,
    }
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    failures = [item for item in results if not item.get("ok")]
    print(json.dumps(manifest, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
