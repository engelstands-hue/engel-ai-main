from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QPlainTextEdit,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_ROOT = PROJECT_ROOT / "reports"
MAX_PREVIEW_BYTES = 20 * 1024
MAX_ITEMS_PER_SECTION = 200
MAX_SCAN_DEPTH = 3
ALLOWED_PREVIEW_SUFFIXES = {".md", ".json", ".txt"}
SKIPPED_DIR_NAMES = {"build", ".dart_tool", "__pycache__", ".git"}

WINDOW_TITLE = "Engel Code Companion Review Surface"
UNTRUSTED_PREVIEW_BANNER = "UNTRUSTED READ-ONLY PREVIEW"
MISSING_ROLLBACK_TEXT = "Rollback section not available: no protected apply backup or rollback metadata found."

SAFETY_BADGES = [
    "READ ONLY",
    "NO APPLY",
    "NO ROLLBACK",
    "NO PASSWORD COLLECTION",
    "NO TOKEN COLLECTION",
]

BUTTON_LABELS = [
    "Refresh",
    "Open Preview",
    "Copy Path",
    "Show Folder Path",
    "Close",
]


@dataclass(frozen=True)
class ReviewSection:
    title: str
    roots: tuple[Path, ...]
    allowed_suffixes: tuple[str, ...] = (".md", ".json", ".txt")
    missing_text: str = "No review artifacts found for this section."


@dataclass(frozen=True)
class ArtifactItem:
    label: str
    path: Path | None
    note: str = ""


@dataclass(frozen=True)
class PreviewResult:
    path: str
    supported: bool
    truncated: bool
    text: str


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path.resolve(strict=False))


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def build_sections() -> list[ReviewSection]:
    return [
        ReviewSection(
            "Overview",
            tuple(),
            missing_text="Overview is computed from local Code Companion report folders.",
        ),
        ReviewSection(
            "Candidates",
            (REPORTS_ROOT / "code_companion_fix_candidates",),
            missing_text="No Phase 1 fix candidate records found.",
        ),
        ReviewSection(
            "Patch Plans",
            (REPORTS_ROOT / "code_companion_patch_plans",),
            missing_text="No Phase 2 patch plan previews found.",
        ),
        ReviewSection(
            "Patch Bundles",
            (REPORTS_ROOT / "code_companion_patch_bundles",),
            missing_text="No Phase 3 patch bundle drafts found.",
        ),
        ReviewSection(
            "Gates",
            (REPORTS_ROOT / "code_companion_patch_application_gates",),
            missing_text="No Phase 4 protected gate receipts found.",
        ),
        ReviewSection(
            "Dry Runs",
            (REPORTS_ROOT / "code_companion_patch_apply_dry_runs",),
            missing_text="No Phase 5 dry-run simulator records found.",
        ),
        ReviewSection(
            "Approvals",
            (REPORTS_ROOT / "code_companion_patch_apply_approvals",),
            missing_text="No Phase 6 approval receipts found.",
        ),
        ReviewSection(
            "Applies",
            (REPORTS_ROOT / "code_companion_patch_applies" / "receipts",),
            missing_text="No protected apply receipts found.",
        ),
        ReviewSection(
            "Backups / Rollback",
            (
                REPORTS_ROOT / "code_companion_patch_applies" / "backups",
                REPORTS_ROOT / "code_companion_patch_applies" / "rollback",
                REPORTS_ROOT / "code_companion_patch_rollbacks" / "receipts",
            ),
            missing_text=MISSING_ROLLBACK_TEXT,
        ),
        ReviewSection(
            "Verifier Results",
            (REPORTS_ROOT / "codex_bridge",),
            missing_text="No local Code Companion verifier/report references found.",
        ),
    ]


def bounded_files(root: Path, allowed_suffixes: Iterable[str], max_depth: int = MAX_SCAN_DEPTH) -> list[Path]:
    suffixes = {suffix.lower() for suffix in allowed_suffixes}
    if not root.exists() or not root.is_dir():
        return []

    results: list[Path] = []
    visited_folders = 0

    def scan(folder: Path, depth: int) -> None:
        nonlocal visited_folders
        if len(results) >= MAX_ITEMS_PER_SECTION or visited_folders >= MAX_ITEMS_PER_SECTION:
            return
        visited_folders += 1
        try:
            children = sorted(folder.iterdir(), key=lambda path: path.name.lower())
        except OSError:
            return
        for child in children:
            if len(results) >= MAX_ITEMS_PER_SECTION:
                break
            if child.is_dir():
                if depth < max_depth and child.name not in SKIPPED_DIR_NAMES:
                    scan(child, depth + 1)
                continue
            if child.name == ".gitkeep":
                continue
            if child.suffix.lower() in suffixes:
                results.append(child)

    scan(root, 0)
    return sorted(results, key=lambda path: project_relative(path).lower())


def collect_section_items(section: ReviewSection) -> list[ArtifactItem]:
    if section.title == "Overview":
        return []

    files: list[Path] = []
    for root in section.roots:
        files.extend(bounded_files(root, section.allowed_suffixes))

    if section.title == "Verifier Results":
        files = [
            path
            for path in files
            if path.name.startswith("ENGEL_CODE_COMPANION")
            or path.name.startswith("ENGEL_REMOTE_WORKER")
            or "VERIFY" in path.name.upper()
        ]

    if not files:
        return [ArtifactItem(section.missing_text, None, "missing")]

    return [ArtifactItem(project_relative(path), path, "untrusted local artifact") for path in files[:MAX_ITEMS_PER_SECTION]]


def section_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for section in build_sections():
        if section.title == "Overview":
            continue
        items = [item for item in collect_section_items(section) if item.path is not None]
        counts[section.title] = len(items)
    return counts


def rollback_status_text() -> str:
    section = next(section for section in build_sections() if section.title == "Backups / Rollback")
    has_items = any(item.path is not None for item in collect_section_items(section))
    return "Backup/rollback metadata available for review." if has_items else MISSING_ROLLBACK_TEXT


def preview_file(path: Path, max_bytes: int = MAX_PREVIEW_BYTES) -> PreviewResult:
    resolved = path.resolve(strict=False)
    display = project_relative(resolved)
    if not resolved.exists() or not resolved.is_file():
        return PreviewResult(display, False, False, "Preview unavailable: file is missing.")
    if not is_relative_to(resolved, PROJECT_ROOT):
        return PreviewResult(display, False, False, "Preview refused: path is outside Engel App.")
    if resolved.suffix.lower() not in ALLOWED_PREVIEW_SUFFIXES:
        return PreviewResult(display, False, False, "Preview unsupported: markdown, JSON, and text files only.")

    size = resolved.stat().st_size
    truncated = size > max_bytes
    with resolved.open("rb") as handle:
        raw = handle.read(max_bytes)
    text = raw.decode("utf-8", errors="replace")
    if truncated:
        text += "\n\n[preview truncated at " + str(max_bytes) + " bytes]"
    return PreviewResult(display, True, truncated, UNTRUSTED_PREVIEW_BANNER + "\n" + display + "\n\n" + text)


def render_overview_text() -> str:
    counts = section_counts()
    lines = [
        WINDOW_TITLE,
        "",
        "Safety badges:",
        ", ".join(SAFETY_BADGES),
        "",
        "Counts:",
    ]
    for section in build_sections():
        if section.title == "Overview":
            continue
        lines.append(f"- {section.title}: {counts.get(section.title, 0)}")
    lines.extend(
        [
            "",
            "Preview policy:",
            f"- Max preview bytes: {MAX_PREVIEW_BYTES}",
            "- Preview types: markdown, JSON, and text only.",
            "- Displayed content is untrusted text; links and commands are not executed.",
            "",
            rollback_status_text(),
        ]
    )
    return "\n".join(lines)


def render_cli_status() -> str:
    lines = [render_overview_text(), "", "Section roots:"]
    for section in build_sections():
        if section.title == "Overview":
            continue
        roots = ", ".join(project_relative(root) for root in section.roots)
        lines.append(f"- {section.title}: {roots}")
    return "\n".join(lines)


if PYSIDE6_AVAILABLE:

    class ReviewSurfaceWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle(WINDOW_TITLE)
            self.resize(1160, 760)
            self.tabs = QTabWidget()
            self.setCentralWidget(self.tabs)
            self.section_widgets: dict[str, tuple[ReviewSection, QListWidget, QPlainTextEdit, QLabel]] = {}
            self.build_tabs()
            self.refresh_all()

        def build_tabs(self) -> None:
            for section in build_sections():
                if section.title == "Overview":
                    self.tabs.addTab(self.build_overview_tab(), section.title)
                else:
                    self.tabs.addTab(self.build_section_tab(section), section.title)

        def build_overview_tab(self) -> QWidget:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            badge_row = QHBoxLayout()
            for badge in SAFETY_BADGES:
                label = QLabel(badge)
                label.setAlignment(Qt.AlignCenter)
                label.setStyleSheet(
                    "font-weight: 700; padding: 6px 10px; border: 1px solid #777; border-radius: 6px;"
                )
                badge_row.addWidget(label)
            badge_row.addStretch(1)
            layout.addLayout(badge_row)
            overview = QPlainTextEdit()
            overview.setReadOnly(True)
            overview.setObjectName("overview_read_only_text")
            overview.setPlainText(render_overview_text())
            layout.addWidget(overview)
            refresh = QPushButton("Refresh")
            refresh.clicked.connect(lambda: overview.setPlainText(render_overview_text()))
            layout.addWidget(refresh)
            return widget

        def build_section_tab(self, section: ReviewSection) -> QWidget:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            notice = QLabel(
                "Read-only local review. Artifact content is untrusted text; links and commands are not executed."
            )
            notice.setWordWrap(True)
            layout.addWidget(notice)

            row = QHBoxLayout()
            artifact_list = QListWidget()
            artifact_list.setObjectName(section.title.lower().replace(" ", "_").replace("/", "_") + "_artifact_list")
            preview = QPlainTextEdit()
            preview.setReadOnly(True)
            preview.setObjectName(section.title.lower().replace(" ", "_").replace("/", "_") + "_preview")
            row.addWidget(artifact_list, 2)
            row.addWidget(preview, 3)
            layout.addLayout(row)

            status = QLabel("Ready.")
            status.setWordWrap(True)
            layout.addWidget(status)

            button_row = QHBoxLayout()
            refresh = QPushButton("Refresh")
            open_preview = QPushButton("Open Preview")
            copy_path = QPushButton("Copy Path")
            show_folder = QPushButton("Show Folder Path")
            close_button = QPushButton("Close")
            for button in [refresh, open_preview, copy_path, show_folder, close_button]:
                button_row.addWidget(button)
            button_row.addStretch(1)
            layout.addLayout(button_row)

            refresh.clicked.connect(lambda checked=False, title=section.title: self.refresh_section(title))
            open_preview.clicked.connect(
                lambda checked=False, title=section.title: self.open_selected_preview(title)
            )
            artifact_list.itemDoubleClicked.connect(
                lambda item, title=section.title: self.open_selected_preview(title)
            )
            copy_path.clicked.connect(lambda checked=False, title=section.title: self.copy_selected_path(title))
            show_folder.clicked.connect(lambda checked=False, title=section.title: self.show_folder_path(title))
            close_button.clicked.connect(self.close)

            self.section_widgets[section.title] = (section, artifact_list, preview, status)
            return widget

        def refresh_all(self) -> None:
            for section in build_sections():
                if section.title != "Overview":
                    self.refresh_section(section.title)

        def refresh_section(self, title: str) -> None:
            section, artifact_list, preview, status = self.section_widgets[title]
            artifact_list.clear()
            for item in collect_section_items(section):
                list_item = QListWidgetItem(item.label)
                list_item.setData(Qt.UserRole, str(item.path) if item.path else "")
                artifact_list.addItem(list_item)
            preview.setPlainText(
                "Select an artifact and choose Open Preview. Preview is bounded, read-only, and untrusted."
            )
            status.setText(f"{title}: {artifact_list.count()} visible entries.")

        def selected_path(self, title: str) -> Path | None:
            _, artifact_list, _, _ = self.section_widgets[title]
            current = artifact_list.currentItem()
            if current is None:
                return None
            raw = current.data(Qt.UserRole)
            if not raw:
                return None
            return Path(raw)

        def open_selected_preview(self, title: str) -> None:
            _, _, preview, status = self.section_widgets[title]
            selected = self.selected_path(title)
            if selected is None:
                preview.setPlainText("No previewable artifact selected.")
                status.setText("No file selected.")
                return
            result = preview_file(selected)
            preview.setPlainText(result.text)
            status.setText(
                f"Preview loaded: {result.path}"
                + (" (truncated)" if result.truncated else "")
                + ("" if result.supported else " (unsupported)")
            )

        def copy_selected_path(self, title: str) -> None:
            selected = self.selected_path(title)
            if selected is None:
                QMessageBox.information(self, WINDOW_TITLE, "No file path selected.")
                return
            QApplication.clipboard().setText(project_relative(selected))

        def show_folder_path(self, title: str) -> None:
            section, _, preview, status = self.section_widgets[title]
            roots = "\n".join(project_relative(root) for root in section.roots)
            preview.setPlainText("Folder path(s):\n" + roots)
            status.setText("Folder path shown. No external file browser was launched.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Engel Code Companion review surface.")
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print read-only review surface status instead of launching the GUI.",
    )
    args = parser.parse_args(argv)

    if args.status:
        print(render_cli_status())
        return 0

    if not PYSIDE6_AVAILABLE:
        print("PySide6 is not available. Run with --status for a read-only console summary.")
        return 2

    app = QApplication([])
    window = ReviewSurfaceWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
