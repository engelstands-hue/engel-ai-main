"""Local/offline Codex status viewer for Engel App.

This module is intentionally read-only. It inspects local filesystem metadata
and redacted config previews only; it does not call providers, use the network,
start workers, or modify Codex/Engel files.
"""

from __future__ import annotations

import argparse
import builtins
import io
import os
import re
import stat as stat_module
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    APP_ROOT = Path.cwd()
else:
    try:
        APP_ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        APP_ROOT = Path.cwd()
USER_CODEX_PATH = Path.home() / ".codex"
ENGEL_CODEX_FOLDERS = (
    ("Engel App", APP_ROOT / ".codex"),
    ("EngelBible", Path(r"D:\EngelBible\.codex")),
    ("Engel App Bible", Path(r"D:\Engel App Bible\.codex")),
    ("EngelStandalone", Path(r"D:\EngelStandalone\.codex")),
)

NOTE_TEXT = (
    "Live rate-limit percentages are account/server-side and may not be stored "
    "locally. This viewer shows local Codex config/session/project data only."
)

SENSITIVE_RE = re.compile(
    r"(token|api[_\-\s]?key|authorization|bearer|secret|session|refresh|"
    r"access|credential|password)",
    re.IGNORECASE,
)

MAX_FILE_ENTRIES = 120
MAX_FILE_DEPTH = 1
MAX_CONFIG_PREVIEW_LINES = 80
MAX_CONFIG_LINE_CHARS = 220


@dataclass(frozen=True)
class SafeFileEntry:
    relative_path: str
    kind: str
    size: str
    modified: str


@dataclass(frozen=True)
class CodexFolderStatus:
    label: str
    path: Path
    exists: bool
    modified: str
    config_exists: bool
    config_modified: str
    safe_entries: tuple[SafeFileEntry, ...]
    hidden_entry_count: int
    file_list_truncated: bool
    config_preview: tuple[str, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class CodexStatus:
    generated_at: str
    user_folder: CodexFolderStatus
    project_folders: tuple[CodexFolderStatus, ...]
    note: str


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _safe_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _safe_modified(path: Path) -> str:
    try:
        timestamp = path.stat().st_mtime
    except OSError:
        return "unavailable"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def _size_text(size: int | None) -> str:
    if size is None:
        return "-"
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _kind_from_mode(mode: int) -> str:
    if stat_module.S_ISDIR(mode):
        return "folder"
    if stat_module.S_ISREG(mode):
        return "file"
    if stat_module.S_ISLNK(mode):
        return "link"
    return "other"


def _is_sensitive_path(relative_path: Path) -> bool:
    return any(SENSITIVE_RE.search(part) for part in relative_path.parts)


def redact_config_line(line: str) -> str:
    """Redact any config line that contains a sensitive-looking keyword."""
    clean_line = line.rstrip("\r\n")
    if SENSITIVE_RE.search(clean_line):
        return "[REDACTED: sensitive-looking config line]"
    return clean_line


def read_config_preview(config_path: Path) -> tuple[str, ...]:
    if not _safe_is_file(config_path):
        return ("config.toml: missing",)

    lines: list[str] = []
    try:
        with config_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                if line_number > MAX_CONFIG_PREVIEW_LINES:
                    lines.append("... [preview truncated]")
                    break
                safe_line = redact_config_line(raw_line)
                if len(safe_line) > MAX_CONFIG_LINE_CHARS:
                    safe_line = safe_line[:MAX_CONFIG_LINE_CHARS - 16] + " ... [truncated]"
                lines.append(f"{line_number:03d}: {safe_line}")
    except OSError as exc:
        return (f"config.toml: unavailable ({exc.__class__.__name__})",)

    return tuple(lines or ("config.toml: empty",))


def list_safe_file_entries(root: Path) -> tuple[tuple[SafeFileEntry, ...], int, bool]:
    if not _safe_exists(root):
        return (), 0, False

    entries: list[SafeFileEntry] = []
    hidden_count = 0
    queue: list[tuple[Path, int]] = [(root, 0)]
    queue_index = 0

    while queue_index < len(queue):
        current, depth = queue[queue_index]
        queue_index += 1
        try:
            children = sorted(current.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            continue

        for child in children:
            try:
                relative_path = child.relative_to(root)
            except ValueError:
                continue

            if _is_sensitive_path(relative_path):
                hidden_count += 1
                continue

            if len(entries) >= MAX_FILE_ENTRIES:
                return tuple(entries), hidden_count, True

            rel_text = str(relative_path).replace("/", "\\")
            try:
                stat_result = os.lstat(child)
            except OSError:
                entries.append(SafeFileEntry(rel_text, "unavailable", "-", "unavailable"))
                continue

            kind = _kind_from_mode(stat_result.st_mode)
            size = stat_result.st_size if kind == "file" else None
            modified = datetime.fromtimestamp(stat_result.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            entries.append(SafeFileEntry(rel_text, kind, _size_text(size), modified))

            if kind == "folder" and depth < MAX_FILE_DEPTH:
                queue.append((child, depth + 1))

    return tuple(entries), hidden_count, False


def collect_folder_status(label: str, path: Path, include_file_list: bool) -> CodexFolderStatus:
    exists = _safe_exists(path)
    config_path = path / "config.toml"
    config_exists = _safe_is_file(config_path)
    notes: list[str] = []

    if not exists:
        notes.append("Folder is not present on this machine.")

    if include_file_list:
        safe_entries, hidden_count, truncated = list_safe_file_entries(path)
    else:
        safe_entries, hidden_count, truncated = (), 0, False

    if hidden_count:
        notes.append(f"{hidden_count} sensitive-looking path(s) were hidden from the file list.")
    if truncated:
        notes.append(f"Safe file list stopped at {MAX_FILE_ENTRIES} entries.")

    return CodexFolderStatus(
        label=label,
        path=path,
        exists=exists,
        modified=_safe_modified(path) if exists else "missing",
        config_exists=config_exists,
        config_modified=_safe_modified(config_path) if config_exists else "missing",
        safe_entries=safe_entries,
        hidden_entry_count=hidden_count,
        file_list_truncated=truncated,
        config_preview=read_config_preview(config_path),
        notes=tuple(notes),
    )


def collect_codex_status() -> CodexStatus:
    return CodexStatus(
        generated_at=_now_text(),
        user_folder=collect_folder_status("User .codex", USER_CODEX_PATH, include_file_list=True),
        project_folders=tuple(
            collect_folder_status(label, path, include_file_list=False)
            for label, path in ENGEL_CODEX_FOLDERS
        ),
        note=NOTE_TEXT,
    )


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def build_folder_summary_lines(folder: CodexFolderStatus) -> list[str]:
    lines = [
        f"{folder.label}",
        f"Path: {folder.path}",
        f"Exists: {_yes_no(folder.exists)}",
        f"Last modified: {folder.modified}",
        f"config.toml exists: {_yes_no(folder.config_exists)}",
        f"config.toml last modified: {folder.config_modified}",
    ]
    for note in folder.notes:
        lines.append(f"Note: {note}")
    return lines


def build_file_list_text(folder: CodexFolderStatus) -> str:
    lines = [
        f"Safe file list for {folder.path}",
        "Sensitive-looking paths are hidden; file contents are not shown here.",
        "",
    ]
    if not folder.exists:
        lines.append("Folder is missing.")
        return "\n".join(lines)
    if not folder.safe_entries:
        lines.append("No safe entries found.")
        return "\n".join(lines)
    for entry in folder.safe_entries:
        lines.append(
            f"{entry.relative_path} | {entry.kind} | {entry.size} | modified {entry.modified}"
        )
    if folder.hidden_entry_count:
        lines.append("")
        lines.append(f"Hidden sensitive-looking path count: {folder.hidden_entry_count}")
    if folder.file_list_truncated:
        lines.append(f"List truncated after {MAX_FILE_ENTRIES} safe entries.")
    return "\n".join(lines)


def build_config_preview_text(status: CodexStatus) -> str:
    sections: list[str] = []
    for folder in (status.user_folder, *status.project_folders):
        sections.extend(
            [
                folder.label,
                f"Path: {folder.path / 'config.toml'}",
                f"Exists: {_yes_no(folder.config_exists)}",
                "",
                *folder.config_preview,
                "",
                "-" * 72,
                "",
            ]
        )
    return "\n".join(sections).rstrip()


def build_text_summary(status: CodexStatus) -> str:
    lines = [
        "Engel Codex Status Viewer Summary",
        f"Generated: {status.generated_at}",
        "",
        "User Codex Folder",
        *build_folder_summary_lines(status.user_folder),
        "",
        "Engel Project Codex Folders",
    ]
    for folder in status.project_folders:
        lines.extend(["", *build_folder_summary_lines(folder)])

    lines.extend(
        [
            "",
            "User .codex Safe File List",
            build_file_list_text(status.user_folder),
            "",
            "Safe Config Preview",
            build_config_preview_text(status),
            "",
            "Note",
            status.note,
        ]
    )
    return "\n".join(lines)


def open_local_folder(path: Path) -> tuple[bool, str]:
    if not _safe_exists(path):
        return False, f"Folder does not exist: {path}"
    if os.name == "nt" and hasattr(os, "startfile"):
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except OSError as exc:
            return False, f"Could not open folder: {exc}"
        return True, f"Opened folder: {path}"
    return False, "Open folder is implemented for Windows Explorer on this tool."


def _show_qt_message(parent: object, title: str, message: str) -> None:
    from PySide6.QtWidgets import QMessageBox

    QMessageBox.information(parent, title, message)


def launch_pyside6_gui() -> int:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QPushButton,
        QPlainTextEdit,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )

    class CodexStatusWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.status = collect_codex_status()
            self.setWindowTitle("Engel Codex Status Viewer")
            self.resize(980, 720)

            root = QWidget()
            layout = QVBoxLayout(root)

            title = QLabel("Engel Codex Status Viewer")
            title.setStyleSheet("font-size: 18px; font-weight: 600;")
            layout.addWidget(title)

            self.note_label = QLabel(NOTE_TEXT)
            self.note_label.setWordWrap(True)
            self.note_label.setStyleSheet("padding: 8px; background: #f4f6f8;")
            layout.addWidget(self.note_label)

            button_row = QHBoxLayout()
            refresh_button = QPushButton("Refresh")
            open_user_button = QPushButton("Open User .codex Folder")
            open_engel_button = QPushButton("Open Engel App .codex Folder")
            copy_button = QPushButton("Copy Summary")
            close_button = QPushButton("Close")
            button_row.addWidget(refresh_button)
            button_row.addWidget(open_user_button)
            button_row.addWidget(open_engel_button)
            button_row.addStretch(1)
            button_row.addWidget(copy_button)
            button_row.addWidget(close_button)
            layout.addLayout(button_row)

            self.project_table = QTableWidget(0, 6)
            self.project_table.setHorizontalHeaderLabels(
                ["Label", "Path", "Exists", "Config", "Folder Modified", "Config Modified"]
            )
            self.project_table.horizontalHeader().setStretchLastSection(True)
            self.project_table.setSelectionBehavior(QTableWidget.SelectRows)
            self.project_table.setEditTriggers(QTableWidget.NoEditTriggers)

            self.summary_text = QPlainTextEdit()
            self.files_text = QPlainTextEdit()
            self.config_text = QPlainTextEdit()
            self.note_text = QPlainTextEdit()
            for text_widget in (
                self.summary_text,
                self.files_text,
                self.config_text,
                self.note_text,
            ):
                text_widget.setReadOnly(True)
                text_widget.setLineWrapMode(QPlainTextEdit.NoWrap)

            tabs = QTabWidget()
            summary_tab = QWidget()
            summary_layout = QVBoxLayout(summary_tab)
            summary_layout.addWidget(self.project_table)
            summary_layout.addWidget(self.summary_text)
            tabs.addTab(summary_tab, "Summary")
            tabs.addTab(self.files_text, "User Safe Files")
            tabs.addTab(self.config_text, "Config Preview")
            tabs.addTab(self.note_text, "Note")
            layout.addWidget(tabs)

            self.setCentralWidget(root)

            refresh_button.clicked.connect(self.refresh)
            open_user_button.clicked.connect(lambda: self.open_folder(self.status.user_folder.path))
            open_engel_button.clicked.connect(lambda: self.open_folder(ENGEL_CODEX_FOLDERS[0][1]))
            copy_button.clicked.connect(self.copy_summary)
            close_button.clicked.connect(self.close)

            self.refresh()

        def refresh(self) -> None:
            self.status = collect_codex_status()
            self.note_label.setText(self.status.note)
            self.summary_text.setPlainText("\n".join(build_folder_summary_lines(self.status.user_folder)))
            self.files_text.setPlainText(build_file_list_text(self.status.user_folder))
            self.config_text.setPlainText(build_config_preview_text(self.status))
            self.note_text.setPlainText(self.status.note)
            self._populate_project_table()

        def _populate_project_table(self) -> None:
            rows = (self.status.user_folder, *self.status.project_folders)
            self.project_table.setRowCount(len(rows))
            for row, folder in enumerate(rows):
                values = [
                    folder.label,
                    str(folder.path),
                    _yes_no(folder.exists),
                    _yes_no(folder.config_exists),
                    folder.modified,
                    folder.config_modified,
                ]
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if column in (2, 3):
                        item.setTextAlignment(Qt.AlignCenter)
                    self.project_table.setItem(row, column, item)
            self.project_table.resizeColumnsToContents()

        def open_folder(self, path: Path) -> None:
            ok, message = open_local_folder(path)
            if not ok:
                _show_qt_message(self, "Open Folder", message)

        def copy_summary(self) -> None:
            QApplication.clipboard().setText(build_text_summary(self.status))
            _show_qt_message(self, "Copy Summary", "Summary copied to clipboard with redactions applied.")

    app = QApplication.instance() or QApplication(sys.argv)
    window = CodexStatusWindow()
    window.show()
    return app.exec()


def launch_tkinter_gui() -> int:
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    root.title("Engel Codex Status Viewer")
    root.geometry("980x720")

    status_holder = {"status": collect_codex_status()}

    outer = ttk.Frame(root, padding=10)
    outer.pack(fill="both", expand=True)

    title = ttk.Label(outer, text="Engel Codex Status Viewer", font=("Segoe UI", 14, "bold"))
    title.pack(anchor="w")

    note_label = ttk.Label(outer, text=NOTE_TEXT, wraplength=900, padding=(0, 8, 0, 8))
    note_label.pack(fill="x")

    button_row = ttk.Frame(outer)
    button_row.pack(fill="x", pady=(0, 8))

    notebook = ttk.Notebook(outer)
    notebook.pack(fill="both", expand=True)

    summary_frame = ttk.Frame(notebook)
    files_frame = ttk.Frame(notebook)
    config_frame = ttk.Frame(notebook)
    note_frame = ttk.Frame(notebook)
    notebook.add(summary_frame, text="Summary")
    notebook.add(files_frame, text="User Safe Files")
    notebook.add(config_frame, text="Config Preview")
    notebook.add(note_frame, text="Note")

    columns = ("label", "path", "exists", "config", "modified", "config_modified")
    project_table = ttk.Treeview(summary_frame, columns=columns, show="headings", height=6)
    headings = {
        "label": "Label",
        "path": "Path",
        "exists": "Exists",
        "config": "Config",
        "modified": "Folder Modified",
        "config_modified": "Config Modified",
    }
    widths = {
        "label": 120,
        "path": 310,
        "exists": 70,
        "config": 70,
        "modified": 150,
        "config_modified": 150,
    }
    for column in columns:
        project_table.heading(column, text=headings[column])
        project_table.column(column, width=widths[column], anchor="w")
    project_table.pack(fill="x", pady=(0, 8))

    def make_text(parent: ttk.Frame) -> tk.Text:
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")
        text = tk.Text(frame, wrap="none", yscrollcommand=scrollbar.set)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=text.yview)
        return text

    summary_text = make_text(summary_frame)
    files_text = make_text(files_frame)
    config_text = make_text(config_frame)
    note_text = make_text(note_frame)

    def set_text(widget: tk.Text, text: str) -> None:
        widget.config(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.config(state="disabled")

    def refresh() -> None:
        status_holder["status"] = collect_codex_status()
        status = status_holder["status"]
        note_label.config(text=status.note)
        project_table.delete(*project_table.get_children())
        for folder in (status.user_folder, *status.project_folders):
            project_table.insert(
                "",
                "end",
                values=(
                    folder.label,
                    str(folder.path),
                    _yes_no(folder.exists),
                    _yes_no(folder.config_exists),
                    folder.modified,
                    folder.config_modified,
                ),
            )
        set_text(summary_text, "\n".join(build_folder_summary_lines(status.user_folder)))
        set_text(files_text, build_file_list_text(status.user_folder))
        set_text(config_text, build_config_preview_text(status))
        set_text(note_text, status.note)

    def open_folder(path: Path) -> None:
        ok, message = open_local_folder(path)
        if not ok:
            messagebox.showinfo("Open Folder", message)

    def copy_summary() -> None:
        root.clipboard_clear()
        root.clipboard_append(build_text_summary(status_holder["status"]))
        messagebox.showinfo("Copy Summary", "Summary copied to clipboard with redactions applied.")

    ttk.Button(button_row, text="Refresh", command=refresh).pack(side="left", padx=(0, 6))
    ttk.Button(
        button_row,
        text="Open User .codex Folder",
        command=lambda: open_folder(status_holder["status"].user_folder.path),
    ).pack(side="left", padx=(0, 6))
    ttk.Button(
        button_row,
        text="Open Engel App .codex Folder",
        command=lambda: open_folder(ENGEL_CODEX_FOLDERS[0][1]),
    ).pack(side="left", padx=(0, 6))
    ttk.Button(button_row, text="Copy Summary", command=copy_summary).pack(side="right", padx=(6, 0))
    ttk.Button(button_row, text="Close", command=root.destroy).pack(side="right")

    refresh()
    root.mainloop()
    return 0


def launch_gui() -> int:
    try:
        return launch_pyside6_gui()
    except ImportError:
        return launch_tkinter_gui()


def _is_write_mode(mode: object) -> bool:
    if not isinstance(mode, str):
        return False
    return any(marker in mode for marker in ("w", "a", "x", "+"))


@contextmanager
def _write_guard() -> Iterator[list[str]]:
    attempts: list[str] = []
    original_builtins_open = builtins.open
    original_io_open = io.open
    original_os_open = os.open
    original_write_text = Path.write_text
    original_write_bytes = Path.write_bytes

    def guarded_open(file: object, mode: object = "r", *args: object, **kwargs: object) -> object:
        if _is_write_mode(mode):
            attempts.append(f"open({file!r}, mode={mode!r})")
            raise AssertionError(f"write attempt blocked for {file!r}")
        return original_io_open(file, mode, *args, **kwargs)

    def guarded_os_open(path: object, flags: int, mode: int = 0o777, *args: object, **kwargs: object) -> int:
        write_flags = (
            os.O_WRONLY
            | os.O_RDWR
            | os.O_CREAT
            | os.O_TRUNC
            | os.O_APPEND
            | os.O_EXCL
        )
        if flags & write_flags:
            attempts.append(f"os.open({path!r}, flags={flags!r})")
            raise AssertionError(f"os.open write attempt blocked for {path!r}")
        return original_os_open(path, flags, mode, *args, **kwargs)

    def guarded_write_text(self: Path, *args: object, **kwargs: object) -> int:
        attempts.append(f"Path.write_text({self!s})")
        raise AssertionError(f"Path.write_text blocked for {self!s}")

    def guarded_write_bytes(self: Path, *args: object, **kwargs: object) -> int:
        attempts.append(f"Path.write_bytes({self!s})")
        raise AssertionError(f"Path.write_bytes blocked for {self!s}")

    builtins.open = guarded_open  # type: ignore[assignment]
    io.open = guarded_open  # type: ignore[assignment]
    os.open = guarded_os_open  # type: ignore[assignment]
    Path.write_text = guarded_write_text  # type: ignore[assignment]
    Path.write_bytes = guarded_write_bytes  # type: ignore[assignment]
    try:
        yield attempts
    finally:
        builtins.open = original_builtins_open  # type: ignore[assignment]
        io.open = original_io_open  # type: ignore[assignment]
        os.open = original_os_open  # type: ignore[assignment]
        Path.write_text = original_write_text  # type: ignore[assignment]
        Path.write_bytes = original_write_bytes  # type: ignore[assignment]


def run_self_test() -> None:
    status = collect_codex_status()
    assert status.user_folder.path == USER_CODEX_PATH, "user .codex path was not collected"
    assert len(status.project_folders) == len(ENGEL_CODEX_FOLDERS), "project paths were not collected"
    assert all(folder.path.name == ".codex" for folder in status.project_folders), "bad project .codex path"

    safe_line = redact_config_line("model = 'gpt-local-status'")
    redacted_lines = [
        redact_config_line("token = 'abc123'"),
        redact_config_line("api_key = 'abc123'"),
        redact_config_line("authorization = 'Bearer abc123'"),
        redact_config_line("session_refresh = 'abc123'"),
        redact_config_line("credential_password = 'abc123'"),
    ]
    assert safe_line == "model = 'gpt-local-status'", "non-sensitive line was changed"
    assert all("abc123" not in line for line in redacted_lines), "redaction leaked a test secret"
    assert all(line.startswith("[REDACTED:") for line in redacted_lines), "redaction marker missing"

    with _write_guard() as attempts:
        guarded_status = collect_codex_status()
        build_text_summary(guarded_status)
        build_file_list_text(guarded_status.user_folder)
        build_config_preview_text(guarded_status)
    assert not attempts, f"write operations were attempted: {attempts}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local/offline Engel Codex status viewer.")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run read-only collection/redaction checks without launching the GUI.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        run_self_test()
        print("Self-test passed: paths collected, redaction verified, no writes observed.")
        return 0
    return launch_gui()


if __name__ == "__main__":
    raise SystemExit(main())
