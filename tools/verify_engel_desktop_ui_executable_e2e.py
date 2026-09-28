#!/usr/bin/env python3
"""Exercise Engel Desktop chat input through Meeting Room to artifact output."""
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


def main() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS"] = "0"
    artifact_root = ROOT / "runtime" / "desktop_ui_executable_e2e"
    if artifact_root.exists():
        shutil.rmtree(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)
    os.environ["ENGEL_EXECUTABLE_RESULTS_DIR"] = str(artifact_root)

    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QApplication
    import engel_desktop_v2 as desktop

    class FakeChatWorker(QObject):
        finished = Signal(str)

        def __init__(self, text: str, mode: str):
            super().__init__()
            self.text = text
            self.mode = mode

        def isRunning(self) -> bool:
            return False

        def start(self) -> None:
            self.finished.emit(
                "I hear you. I don't have a live AI connected right now - "
                "type 'browser ai connect claude' or 'commands'."
            )

    desktop._ChatWorker = FakeChatWorker
    app = QApplication.instance() or QApplication([])
    panel = desktop.AgentChatPanel()
    prompt = "use main PC to make me a pdf about Engel executable results from the meeting room"
    panel.msg_input.setText(prompt)
    panel._send()
    app.processEvents()
    transcript = panel.transcript.toPlainText()
    require("Meeting Room:" in transcript, "UI transcript did not show Meeting Room handoff")
    require("Engel Result:" in transcript, "UI transcript did not show executable result")
    require("live AI connected" not in transcript, "UI leaked provider-fallback text after Meeting Room bridge")
    require("Engel local bridge is connected" in transcript, "UI did not show local bridge answer")
    pdfs = list(artifact_root.glob("**/engel_result.pdf"))
    require(pdfs, "UI E2E did not create a PDF artifact")
    require(pdfs[0].read_bytes().startswith(b"%PDF-1.4"), "UI E2E PDF artifact is invalid")
    require(b"Engel visual:" in pdfs[0].read_bytes(), "UI E2E PDF artifact missing embedded visual layer")
    print("OK: Engel Desktop UI executable E2E verified")


if __name__ == "__main__":
    main()
