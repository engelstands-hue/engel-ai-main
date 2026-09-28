"""Send ONE command through the real Engel AI Desktop V2 chat UI.

This drives the genuine ``AgentChatPanel._send()`` handler — the exact code path
a human triggers by typing in the Agent Chat box and pressing Enter. The order
is staged to the real Agent Meeting Room via ``submit_order_from_engel_main_ui``
and the reply returned via ``complete_order_from_engel_main_ui``. Nothing is
faked; the transcript printed at the end is the real UI output.

Usage:
    runtime\\python310\\python.exe tools\\engel_ui_send_once.py "your command here"
    ... [--mode auto|local] [--timeout 180]
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))
os.chdir(APP_ROOT)
os.environ.setdefault("ENGEL_OFFLINE_SEED_LLM_ENABLED", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

try:
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
except Exception:  # pragma: no cover
    from PySide6.QtCore import QTimer  # type: ignore
    from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout  # type: ignore


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Send one command through the real Engel UI chat")
    ap.add_argument("text", help="the command to type into the Agent Chat box")
    ap.add_argument("--mode", choices=["auto", "local"], default="auto")
    ap.add_argument("--timeout", type=float, default=180.0)
    args = ap.parse_args(argv)

    import engel_desktop_v2 as dv2

    app = QApplication.instance() or QApplication(sys.argv)
    try:
        app.setStyleSheet(dv2.STYLESHEET)
    except Exception:
        pass

    host = QWidget()
    host.setWindowTitle("Engel AI - one-shot UI send")
    host.resize(560, 600)
    lay = QVBoxLayout(host)
    panel = dv2.AgentChatPanel()
    lay.addWidget(panel)
    host.show()
    try:
        panel._set_mode(args.mode)
    except Exception:
        pass

    state = {"sent": False, "snapshot": 0, "send_time": 0.0, "done": False}

    def tick():
        thread = getattr(panel, "_chat_thread", None)
        busy = thread is not None and thread.isRunning()
        enabled = bool(panel.send_btn.isEnabled())
        if not state["sent"]:
            if busy or not enabled:
                return
            state["snapshot"] = len(panel.transcript.toPlainText())
            state["send_time"] = time.time()
            state["sent"] = True
            panel.msg_input.setText(args.text)
            panel._send()  # the genuine UI handler
            return
        if state["done"]:
            return
        if (busy or not enabled) and (time.time() - state["send_time"]) < args.timeout:
            return
        # completed (or timed out)
        full = panel.transcript.toPlainText()
        new = full[state["snapshot"]:].strip()
        timed_out = (busy or not enabled)
        print("=" * 70)
        print("ENGEL UI TRANSCRIPT (real _send path):")
        print(new or "(no transcript captured)")
        print("=" * 70)
        if timed_out:
            print("[note] step timed out after %.0fs" % args.timeout)
        state["done"] = True
        QTimer.singleShot(300, app.quit)

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(2000)
    app.exec() if hasattr(app, "exec") else app.exec_()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
