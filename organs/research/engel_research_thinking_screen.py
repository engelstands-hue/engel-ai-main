"""Safe local Research Thinking Screen for Engel.

This screen is intentionally a passive GUI surface. It does not start research,
contact providers, open network connections, mutate Engel state, or run any
background work.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import (
        QApplication,
        QFrame,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSizePolicy,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import (
        QApplication,
        QFrame,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSizePolicy,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)


def _now_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_status_text() -> str:
    return "\n".join(
        [
            f"Last local refresh: {_now_local()}",
            f"Project root: {ROOT}",
            "",
            "Mode: local/offline-safe surface only.",
            "Full Research Thinking functionality: not implemented in this screen yet.",
            "",
            "Provider/API calls: not present.",
            "Network/browser/email behavior: not present.",
            "Old Ollama or local endpoint behavior: not present.",
            "Background workers: not started.",
            "Autonomy: not active.",
            "Queue mutation: not performed.",
            "Trusted-memory writes: not performed.",
            "Route behavior changes: not performed.",
            "Hidden downloads: not present.",
            "LLM inference: not enabled.",
            "",
            "Available local-only actions:",
            "- Refresh this displayed status.",
            "- Close this screen.",
            "",
            "Future integration note:",
            "Connect this surface only to approved local Research Thinking status records.",
        ]
    )


class ResearchThinkingScreen(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Engel Research Thinking Screen")
        self.setMinimumSize(780, 520)
        self.resize(860, 600)
        self._build_ui()
        self.refresh_local_status()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #071113;
                color: #e6fbff;
                font-family: Segoe UI, Arial, sans-serif;
                font-size: 14px;
            }
            QLabel#title {
                color: #ffffff;
                font-size: 28px;
                font-weight: 800;
                letter-spacing: 0px;
            }
            QLabel#subtitle {
                color: #8eeaff;
                font-size: 15px;
            }
            QFrame#banner {
                background: #082a23;
                border: 1px solid #37d67a;
                border-radius: 8px;
            }
            QLabel#bannerText {
                color: #c7ffcf;
                font-weight: 700;
            }
            QTextEdit {
                background: #031012;
                border: 1px solid #1d8e9f;
                border-radius: 8px;
                color: #dffbff;
                padding: 10px;
                selection-background-color: #145c67;
            }
            QPushButton {
                background: #0b3038;
                border: 1px solid #4ed8ee;
                border-radius: 7px;
                color: #ffffff;
                font-weight: 700;
                padding: 9px 16px;
            }
            QPushButton:hover {
                background: #104a55;
            }
            QPushButton:pressed {
                background: #08272d;
            }
            """
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(22, 22, 22, 22)
        root_layout.setSpacing(14)

        title = QLabel("Engel Research Thinking Screen")
        title.setObjectName("title")
        root_layout.addWidget(title)

        subtitle = QLabel("Local/offline-safe surface only.")
        subtitle.setObjectName("subtitle")
        root_layout.addWidget(subtitle)

        banner = QFrame()
        banner.setObjectName("banner")
        banner_layout = QVBoxLayout(banner)
        banner_layout.setContentsMargins(14, 12, 14, 12)
        banner_text = QLabel(
            "No provider, network, autonomy, or background worker is active."
        )
        banner_text.setObjectName("bannerText")
        banner_text.setWordWrap(True)
        banner_layout.addWidget(banner_text)
        root_layout.addWidget(banner)

        self.status_area = QTextEdit()
        self.status_area.setReadOnly(True)
        self.status_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        fixed_font = QFont("Consolas")
        fixed_font.setStyleHint(QFont.StyleHint.Monospace)
        fixed_font.setPointSize(10)
        self.status_area.setFont(fixed_font)
        root_layout.addWidget(self.status_area, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        self.refresh_button = QPushButton("Refresh Local Status")
        self.refresh_button.clicked.connect(self.refresh_local_status)
        button_row.addWidget(self.refresh_button)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        button_row.addWidget(self.close_button)

        root_layout.addLayout(button_row)

    def refresh_local_status(self) -> None:
        self.status_area.setPlainText(_safe_status_text())

    def _move_to_safe_screen_position(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        width = max(self.width(), self.minimumWidth())
        height = max(self.height(), self.minimumHeight())
        width = min(width, max(320, available.width()))
        height = min(height, max(260, available.height()))
        x = available.x() + max(0, (available.width() - width) // 2)
        y = available.y() + max(0, (available.height() - height) // 2)
        self.resize(width, height)
        self.move(x, y)

    def show_visible(self) -> None:
        self._move_to_safe_screen_position()
        self.showNormal()
        self.setWindowState(
            (self.windowState() & ~Qt.WindowState.WindowMinimized)
            | Qt.WindowState.WindowActive
        )
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(150, self.raise_)
        QTimer.singleShot(200, self.activateWindow)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    app = QApplication.instance() or QApplication(argv)
    window = ResearchThinkingScreen()
    window.show_visible()

    if "--smoke" in argv or os.environ.get("ENGEL_RESEARCH_THINKING_SCREEN_SMOKE"):
        window.refresh_local_status()
        QTimer.singleShot(800, app.quit)

    exit_code = app.exec()
    if "--smoke" in argv or os.environ.get("ENGEL_RESEARCH_THINKING_SCREEN_SMOKE"):
        print("RESEARCH_THINKING_SCREEN_SMOKE_PASS")
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
