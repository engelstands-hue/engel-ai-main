#!/usr/bin/env python3
"""Verify Desktop chat bridge and Octogent root resolution."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_octogent_root() -> None:
    from engel_project_paths import is_pyinstaller_temp_path, resolve_engel_app_root
    import engel_octogent_runner as octogent

    root = resolve_engel_app_root(__file__)
    require(root == ROOT, f"unexpected Engel root: {root}")
    require(not is_pyinstaller_temp_path(root), "Engel root resolved to PyInstaller temp")
    status = octogent.render_octogent_status()
    require(str(ROOT / "engel_octogent_main") in status, "Octogent status missing real project path")
    require("_MEI" not in status, "Octogent status leaked PyInstaller temp path")
    require(octogent._web_url() == "http://localhost:5173", "Octogent browser URL must be the web dashboard")
    require("API backend root can return" in status, "Octogent status must explain API root is not the UI")


def verify_desktop_bridge_reply() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS"] = "0"
    artifact_root = ROOT / "runtime" / "desktop_ui_bridge_connection"
    if artifact_root.exists():
        shutil.rmtree(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)
    os.environ["ENGEL_EXECUTABLE_RESULTS_DIR"] = str(artifact_root)

    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QApplication
    import engel_desktop_v2 as desktop

    class ProviderFallbackWorker(QObject):
        finished = Signal(str)

        def __init__(self, text: str, mode: str):
            super().__init__()

        def isRunning(self) -> bool:
            return False

        def start(self) -> None:
            self.finished.emit(
                "I hear you. I don't have a live AI connected right now - "
                "type 'browser ai connect claude' or 'commands'."
            )

    desktop._ChatWorker = ProviderFallbackWorker
    app = QApplication.instance() or QApplication([])
    panel = desktop.AgentChatPanel()
    panel.msg_input.setText("Use main PC to make a happy face on a PDF then save to the project folder")
    panel._send()
    app.processEvents()
    transcript = panel.transcript.toPlainText()
    require("Meeting Room:" in transcript, "Meeting Room handoff missing")
    require("Engel local bridge is connected" in transcript, "local bridge reply missing")
    require("live AI connected" not in transcript, "provider fallback leaked into UI")
    pdfs = list(artifact_root.glob("**/engel_result.pdf"))
    require(pdfs, "bridged UI prompt did not create PDF artifact")
    require(pdfs[0].read_bytes().startswith(b"%PDF-1.4"), "bridged PDF artifact is invalid")
    require(b"Engel visual: happy_face" in pdfs[0].read_bytes(), "bridged PDF artifact missing happy-face visual")


def main() -> None:
    verify_octogent_root()
    verify_desktop_bridge_reply()
    print("OK: Engel UI bridge connection verified")


if __name__ == "__main__":
    main()
