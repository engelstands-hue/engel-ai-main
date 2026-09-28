from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_ai_runtime_readiness as readiness


WINDOW_TITLE = "Engel AI Runtime Readiness Dashboard"
SAFETY_BADGES = [
    "READ ONLY",
    "NO INFERENCE",
    "NO MODEL LOAD",
    "NO CLOUD",
    "NO DOWNLOADS",
    "NO TRUSTED MEMORY WRITE",
    "NO AUTO-APPLY",
]


def _load_qt():
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QApplication,
            QHBoxLayout,
            QLabel,
            QMainWindow,
            QPushButton,
            QTabWidget,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        raise RuntimeError("PySide6 is required for the optional readiness dashboard GUI.") from exc
    return {
        "Qt": Qt,
        "QApplication": QApplication,
        "QHBoxLayout": QHBoxLayout,
        "QLabel": QLabel,
        "QMainWindow": QMainWindow,
        "QPushButton": QPushButton,
        "QTabWidget": QTabWidget,
        "QTextEdit": QTextEdit,
        "QVBoxLayout": QVBoxLayout,
        "QWidget": QWidget,
    }


class DashboardState:
    def __init__(self) -> None:
        self.payload = readiness.readiness_payload()

    def refresh(self) -> None:
        self.payload = readiness.readiness_payload()

    def summary_text(self) -> str:
        return readiness.render_status(self.payload)

    def raw_json(self) -> str:
        return json.dumps(self.payload, indent=2, sort_keys=True)


def build_window(qt: dict[str, object], state: DashboardState):
    QApplication = qt["QApplication"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QMainWindow = qt["QMainWindow"]
    QPushButton = qt["QPushButton"]
    QTabWidget = qt["QTabWidget"]
    QTextEdit = qt["QTextEdit"]
    QVBoxLayout = qt["QVBoxLayout"]
    QWidget = qt["QWidget"]

    class ReadinessWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle(WINDOW_TITLE)
            self.resize(1040, 720)
            self.state = state
            self.tabs = QTabWidget()
            self.preview_by_name: dict[str, object] = {}
            root = QWidget()
            layout = QVBoxLayout(root)

            badge_row = QHBoxLayout()
            for badge in SAFETY_BADGES:
                label = QLabel(badge)
                label.setObjectName("safetyBadge")
                badge_row.addWidget(label)
            badge_row.addStretch()
            layout.addLayout(badge_row)

            button_row = QHBoxLayout()
            self.refresh_button = QPushButton("Refresh")
            self.copy_summary_button = QPushButton("Copy Summary")
            self.copy_json_button = QPushButton("Copy JSON")
            self.close_button = QPushButton("Close")
            for button in [self.refresh_button, self.copy_summary_button, self.copy_json_button, self.close_button]:
                button_row.addWidget(button)
            button_row.addStretch()
            layout.addLayout(button_row)

            for name in [
                "Overview",
                "Models",
                "Libraries",
                "Runtime Safety",
                "Remote Worker",
                "Code Companion",
                "Next Actions",
                "Raw JSON",
            ]:
                editor = QTextEdit()
                editor.setReadOnly(True)
                self.preview_by_name[name] = editor
                self.tabs.addTab(editor, name)
            layout.addWidget(self.tabs)
            self.setCentralWidget(root)

            self.refresh_button.clicked.connect(self.refresh)
            self.copy_summary_button.clicked.connect(self.copy_summary)
            self.copy_json_button.clicked.connect(self.copy_json)
            self.close_button.clicked.connect(self.close)
            self.refresh()

        def _set_text(self, name: str, text: str) -> None:
            self.preview_by_name[name].setPlainText(text[:80_000])

        def refresh(self) -> None:
            self.state.refresh()
            payload = self.state.payload
            self._set_text("Overview", readiness.render_status(payload))
            self._set_text("Models", readiness.render_model_summary(payload))
            self._set_text("Libraries", readiness.render_library_summary(payload))
            self._set_text("Runtime Safety", readiness.render_safety_summary(payload))
            self._set_text("Remote Worker", readiness.render_remote_worker_summary(payload))
            self._set_text("Code Companion", readiness.render_code_companion_summary(payload))
            self._set_text("Next Actions", readiness.render_next_summary(payload))
            self._set_text("Raw JSON", self.state.raw_json())

        def copy_summary(self) -> None:
            QApplication.clipboard().setText(self.state.summary_text())

        def copy_json(self) -> None:
            QApplication.clipboard().setText(self.state.raw_json())

    return ReadinessWindow()


def main() -> int:
    qt = _load_qt()
    QApplication = qt["QApplication"]
    app = QApplication(sys.argv)
    window = build_window(qt, DashboardState())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
