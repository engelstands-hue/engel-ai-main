#!/usr/bin/env python3
"""
Standalone Codex Status Viewer - Dashboard Edition

Local/offline/read-only utility for viewing safe Codex-related local metadata.

It does NOT:
- call OpenAI APIs
- call the network
- launch browsers except opening local folders with the OS file explorer
- modify files
- reveal secrets
- read live Codex rate limits from OpenAI servers

Run:
    python codexstatusviewer.py

Text summary:
    python codexstatusviewer.py --text

Self-test:
    python codexstatus_viewer.py --self-test
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


SENSITIVE_WORDS = [
    "token",
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "secret",
    "session",
    "refresh",
    "access",
    "credential",
    "password",
    "private_key",
    "client_secret",
    "auth",
]

ACTIVITY_FILES = [
    "history.jsonl",
    "logs_2.sqlite",
    "logs_2.sqlite-shm",
    "logs_2.sqlite-wal",
    "state_5.sqlite",
    "state_5.sqlite-shm",
    "state_5.sqlite-wal",
    "models_cache.json",
    "sandbox.log",
]

ACTIVITY_FOLDERS = [
    "log",
    "cache",
    "plugins",
    "skills",
    "rules",
    "generated_images",
    "sqlite",
    "memories",
]

RATE_LIMIT_NOTE = (
    "Live rate-limit percentages are account/server-side and may not be stored locally. "
    "This viewer shows local Codex config/session/project data only."
)

READ_ONLY_NOTE = (
    "Read-only dashboard: this viewer collects local file metadata and safe config previews only. "
    "It does not edit, delete, create, upload, or send files."
)


@dataclass
class LocalFileRecord:
    name: str
    path: Path
    item_type: str
    modified: str
    size_text: str
    size_bytes: int
    safety: str


@dataclass
class ProjectTrustRecord:
    path_text: str
    trust_level: str
    exists_now: bool
    status: str


@dataclass
class DashboardData:
    user_codex_path: Path
    user_codex_exists: bool
    user_codex_modified: str
    file_count: int
    folder_count: int
    newest_path: str
    newest_modified: str
    model: str
    reasoning_effort: str
    windows_sandbox: str
    trusted_projects: List[ProjectTrustRecord]
    local_files: List[LocalFileRecord]
    activity_files: List[LocalFileRecord]
    safe_config_preview: str
    safe_config_values: Dict[str, str]
    full_summary: str


def is_sensitive_text(text: str) -> bool:
    lower = text.lower()
    return any(word in lower for word in SENSITIVE_WORDS)


def redact_line(line: str) -> str:
    if is_sensitive_text(line):
        return "[REDACTED sensitive config line]"
    return line.rstrip("\n")


def safe_modified_time(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "unknown"


def safe_size_text(path: Path) -> Tuple[str, int]:
    try:
        if path.is_dir():
            return "", 0
        size = path.stat().st_size
    except Exception:
        return "unknown", 0

    if size < 1024:
        return f"{size} B", size
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB", size
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB", size
    return f"{size / (1024 * 1024 * 1024):.1f} GB", size


def safe_file_label(path: Path) -> str:
    name = path.name
    if is_sensitive_text(name):
        return "[REDACTED sensitive-looking filename]"
    return name


def safety_label(path: Path) -> str:
    name = path.name.lower()
    if is_sensitive_text(name):
        return "Sensitive-looking: hidden/redacted"
    if name.endswith(".sqlite") or name.endswith(".sqlite-wal") or name.endswith(".sqlite-shm"):
        return "Local database metadata only"
    if name.endswith(".jsonl"):
        return "Local history/activity artifact"
    if name.endswith(".toml"):
        return "Config preview redacted"
    if path.is_dir():
        return "Folder metadata only"
    return "Safe metadata only"


def read_text_safe(path: Path, max_chars: int = 200_000) -> str:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return raw[:max_chars]


def read_safe_config_preview(config_path: Path, max_lines: int = 120) -> str:
    if not config_path.exists() or not config_path.is_file():
        return "(No config.toml found.)"

    raw = read_text_safe(config_path)
    if not raw:
        return "(Unable to read config.toml safely or file is empty.)"

    lines = raw.splitlines()
    preview_lines = [redact_line(line) for line in lines[:max_lines]]

    if len(lines) > max_lines:
        preview_lines.append(f"... truncated after {max_lines} lines")

    if not preview_lines:
        return "(config.toml is empty.)"

    return "\n".join(preview_lines)


def parse_basic_config_values(config_text: str) -> Dict[str, str]:
    values: Dict[str, str] = {}

    current_section = ""

    for raw_line in config_text.splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if is_sensitive_text(line):
            continue

        section_match = re.match(r"^\[(.+?)\]$", line)
        if section_match:
            current_section = section_match.group(1).strip()
            continue

        key_value_match = re.match(r"^([A-Za-z0-9_.-]+)\s*=\s*(.+?)\s*$", line)
        if not key_value_match:
            continue

        key = key_value_match.group(1).strip()
        value = key_value_match.group(2).strip().strip('"')

        full_key = f"{current_section}.{key}" if current_section else key
        values[full_key] = value

        if key in {"model", "model_reasoning_effort"}:
            values[key] = value

        if current_section == "windows" and key == "sandbox":
            values["windows.sandbox"] = value

    return values


def parse_trusted_projects(config_text: str) -> List[ProjectTrustRecord]:
    projects: List[ProjectTrustRecord] = []

    project_pattern = re.compile(
        r"^\[projects\.'(.+?)'\]\s*$",
        re.IGNORECASE,
    )

    current_project: Optional[str] = None
    current_trust = ""

    def flush() -> None:
        nonlocal current_project, current_trust
        if current_project is None:
            return

        path_text = current_project
        normalized = path_text.lower().replace("/", "\\")

        exists_now = Path(path_text).exists()

        status = "Review"
        if exists_now:
            status = "Found"
        if normalized.startswith("d:\\engel"):
            status = "Active/Found" if exists_now else "Active path missing"
        if normalized.startswith("e:\\engel"):
            status = "Old/Review"
        if normalized in {"c:\\", "d:\\", "e:\\"}:
            status = "Broad trusted root / Review"

        projects.append(
            ProjectTrustRecord(
                path_text=path_text,
                trust_level=current_trust or "unknown",
                exists_now=exists_now,
                status=status,
            )
        )

        current_project = None
        current_trust = ""

    for raw_line in config_text.splitlines():
        line = raw_line.strip()

        match = project_pattern.match(line)
        if match:
            flush()
            current_project = match.group(1)
            continue

        if current_project is not None:
            trust_match = re.match(r'^trust_level\s*=\s*"?(.*?)"?\s*$', line, re.IGNORECASE)
            if trust_match:
                current_trust = trust_match.group(1)

    flush()
    return projects


def collect_local_files(folder: Path, max_items: int = 300) -> List[LocalFileRecord]:
    if not folder.exists() or not folder.is_dir():
        return []

    records: List[LocalFileRecord] = []

    try:
        children = sorted(folder.iterdir(), key=lambda p: p.name.lower())
    except Exception:
        return []

    for child in children[:max_items]:
        size_text, size_bytes = safe_size_text(child)
        records.append(
            LocalFileRecord(
                name=safe_file_label(child),
                path=child,
                item_type="Folder" if child.is_dir() else "File",
                modified=safe_modified_time(child),
                size_text=size_text,
                size_bytes=size_bytes,
                safety=safety_label(child),
            )
        )

    return records


def collect_activity_files(folder: Path) -> List[LocalFileRecord]:
    records: List[LocalFileRecord] = []

    for name in ACTIVITY_FILES:
        path = folder / name
        if path.exists():
            size_text, size_bytes = safe_size_text(path)
            records.append(
                LocalFileRecord(
                    name=safe_file_label(path),
                    path=path,
                    item_type="File",
                    modified=safe_modified_time(path),
                    size_text=size_text,
                    size_bytes=size_bytes,
                    safety="Local activity artifact; not live account usage",
                )
            )
        else:
            records.append(
                LocalFileRecord(
                    name=name,
                    path=path,
                    item_type="Missing",
                    modified="not found",
                    size_text="",
                    size_bytes=0,
                    safety="Not found",
                )
            )

    for name in ACTIVITY_FOLDERS:
        path = folder / name
        if path.exists():
            records.append(
                LocalFileRecord(
                    name=safe_file_label(path),
                    path=path,
                    item_type="Folder",
                    modified=safe_modified_time(path),
                    size_text="",
                    size_bytes=0,
                    safety="Local folder metadata only",
                )
            )
        else:
            records.append(
                LocalFileRecord(
                    name=name,
                    path=path,
                    item_type="Missing",
                    modified="not found",
                    size_text="",
                    size_bytes=0,
                    safety="Not found",
                )
            )

    return records


def newest_child(folder: Path) -> Tuple[str, str]:
    if not folder.exists() or not folder.is_dir():
        return "not found", "not found"

    newest: Optional[Path] = None
    newest_ts = -1.0

    try:
        children = list(folder.iterdir())
    except Exception:
        return "unknown", "unknown"

    for child in children:
        try:
            ts = child.stat().st_mtime
        except Exception:
            continue
        if ts > newest_ts:
            newest_ts = ts
            newest = child

    if newest is None:
        return "none", "none"

    return safe_file_label(newest), safe_modified_time(newest)


def build_dashboard_data() -> DashboardData:
    user_codex_path = Path.home() / ".codex"
    config_path = user_codex_path / "config.toml"

    config_text = read_text_safe(config_path) if config_path.exists() else ""
    config_values = parse_basic_config_values(config_text)
    trusted_projects = parse_trusted_projects(config_text)
    local_files = collect_local_files(user_codex_path)
    activity_files = collect_activity_files(user_codex_path)

    file_count = sum(1 for record in local_files if record.item_type == "File")
    folder_count = sum(1 for record in local_files if record.item_type == "Folder")
    newest_name, newest_modified = newest_child(user_codex_path)

    model = config_values.get("model", "unknown")
    reasoning_effort = config_values.get("model_reasoning_effort", "unknown")
    windows_sandbox = config_values.get("windows.sandbox", "unknown")

    data = DashboardData(
        user_codex_path=user_codex_path,
        user_codex_exists=user_codex_path.exists(),
        user_codex_modified=safe_modified_time(user_codex_path) if user_codex_path.exists() else "not found",
        file_count=file_count,
        folder_count=folder_count,
        newest_path=newest_name,
        newest_modified=newest_modified,
        model=model,
        reasoning_effort=reasoning_effort,
        windows_sandbox=windows_sandbox,
        trusted_projects=trusted_projects,
        local_files=local_files,
        activity_files=activity_files,
        safe_config_preview=read_safe_config_preview(config_path),
        safe_config_values=config_values,
        full_summary="",
    )

    data.full_summary = build_full_summary(data)
    return data


def build_full_summary(data: DashboardData) -> str:
    lines: List[str] = []

    lines.append("Standalone Codex Status Viewer - Dashboard Summary")
    lines.append("=" * 70)
    lines.append("")
    lines.append(RATE_LIMIT_NOTE)
    lines.append(READ_ONLY_NOTE)
    lines.append("")
    lines.append(f"Computer: {platform.node()}")
    lines.append(f"OS: {platform.platform()}")
    lines.append(f"User home: {Path.home()}")
    lines.append("")
    lines.append("Overview")
    lines.append("-" * 70)
    lines.append(f"User .codex path: {data.user_codex_path}")
    lines.append(f"User .codex exists: {data.user_codex_exists}")
    lines.append(f"Modified: {data.user_codex_modified}")
    lines.append(f"File count: {data.file_count}")
    lines.append(f"Folder count: {data.folder_count}")
    lines.append(f"Newest local item: {data.newest_path}")
    lines.append(f"Newest local item modified: {data.newest_modified}")
    lines.append("")
    lines.append("Config")
    lines.append("-" * 70)
    lines.append(f"Model: {data.model}")
    lines.append(f"Reasoning effort: {data.reasoning_effort}")
    lines.append(f"Windows sandbox: {data.windows_sandbox}")
    lines.append("")
    lines.append("Trusted Projects")
    lines.append("-" * 70)
    lines.append(f"Trusted project count: {len(data.trusted_projects)}")
    for project in data.trusted_projects:
        lines.append(
            f"- {project.path_text} | trust={project.trust_level} | "
            f"exists={project.exists_now} | status={project.status}"
        )
    lines.append("")
    lines.append("Activity Files")
    lines.append("-" * 70)
    for record in data.activity_files:
        lines.append(
            f"- {record.name} | {record.item_type} | modified={record.modified} | "
            f"size={record.size_text} | {record.safety}"
        )
    lines.append("")
    lines.append("Safety")
    lines.append("-" * 70)
    lines.append("Read-only: Yes")
    lines.append("Network calls: No")
    lines.append("Browser automation: No")
    lines.append("Secrets redacted: Yes")
    lines.append("Live rate limits: Not locally readable unless Codex exposes/stores them locally")
    lines.append("")
    lines.append("Safe Config Preview")
    lines.append("-" * 70)
    lines.append(data.safe_config_preview)

    return "\n".join(lines)


def open_folder(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Folder does not exist: {path}")

    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def run_self_test() -> int:
    print("[self-test] collecting dashboard data")
    data = build_dashboard_data()

    if not isinstance(data.user_codex_path, Path):
        print("[self-test] failed: user_codex_path is not a Path")
        return 1

    print("[self-test] checking redaction")
    test_lines = [
        "normal_setting = true",
        "api_key = abc123",
        "Authorization: Bearer abc123",
        "password = bad",
        "session_token = bad",
        "auth = bad",
    ]
    redacted = [redact_line(line) for line in test_lines]

    if redacted[0] != "normal_setting = true":
        print("[self-test] failed: normal line was changed incorrectly")
        return 1

    for line in redacted[1:]:
        if "abc123" in line or "bad" in line:
            print("[self-test] failed: sensitive value was not redacted")
            return 1

    print("[self-test] checking config parser")
    sample_config = '''
model = "gpt-5.5"
model_reasoning_effort = "xhigh"

[projects.'d:\\engel app']
trust_level = "trusted"

[projects.'e:\\engel app']
trust_level = "trusted"

[windows]
sandbox = "elevated"
'''
    values = parse_basic_config_values(sample_config)
    projects = parse_trusted_projects(sample_config)

    if values.get("model") != "gpt-5.5":
        print("[self-test] failed: model parser")
        return 1

    if values.get("model_reasoning_effort") != "xhigh":
        print("[self-test] failed: reasoning parser")
        return 1

    if values.get("windows.sandbox") != "elevated":
        print("[self-test] failed: windows sandbox parser")
        return 1

    if len(projects) != 2:
        print("[self-test] failed: trusted projects parser")
        return 1

    if not any(project.status == "Old/Review" for project in projects):
        print("[self-test] failed: old E:\\ Engel path warning")
        return 1

    print("[self-test] checking summary")
    summary = build_full_summary(data)
    if RATE_LIMIT_NOTE not in summary:
        print("[self-test] failed: rate-limit note missing")
        return 1

    if "Network calls: No" not in summary:
        print("[self-test] failed: safety note missing")
        return 1

    print("[self-test] read-only behavior: no write operations are implemented")
    print("[self-test] passed")
    return 0


def rows_to_text(headers: List[str], rows: List[List[str]]) -> str:
    widths = [len(header) for header in headers]

    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], min(len(str(cell)), 80))

    def trim(cell: str, width: int) -> str:
        text = str(cell)
        if len(text) > width:
            return text[: max(0, width - 3)] + "..."
        return text

    line = " | ".join(header.ljust(widths[index]) for index, header in enumerate(headers))
    sep = "-+-".join("-" * width for width in widths)

    output = [line, sep]
    for row in rows:
        output.append(
            " | ".join(trim(str(cell), widths[index]).ljust(widths[index]) for index, cell in enumerate(row))
        )

    return "\n".join(output)


def run_tkinter_gui() -> None:
    import tkinter as tk
    from tkinter import messagebox
    from tkinter.scrolledtext import ScrolledText
    from tkinter import ttk

    root = tk.Tk()
    root.title("Standalone Codex Status Viewer")
    root.geometry("1180x780")

    data_holder: Dict[str, DashboardData] = {"data": build_dashboard_data()}

    top_frame = tk.Frame(root)
    top_frame.pack(fill="x", padx=12, pady=(10, 4))

    title = tk.Label(
        top_frame,
        text="Standalone Codex Status Viewer",
        font=("Segoe UI", 17, "bold"),
    )
    title.pack(anchor="w")

    note = tk.Label(
        top_frame,
        text=RATE_LIMIT_NOTE,
        wraplength=1120,
        justify="left",
    )
    note.pack(anchor="w", pady=(2, 6))

    cards_frame = tk.Frame(root)
    cards_frame.pack(fill="x", padx=12, pady=(0, 8))

    card_labels: Dict[str, tk.Label] = {}

    def make_card(parent: tk.Frame, key: str, title_text: str) -> None:
        frame = tk.Frame(parent, relief="groove", bd=1, padx=10, pady=8)
        frame.pack(side="left", fill="x", expand=True, padx=(0, 8))

        tk.Label(frame, text=title_text, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        value = tk.Label(frame, text="", font=("Segoe UI", 11), wraplength=180, justify="left")
        value.pack(anchor="w")
        card_labels[key] = value

    make_card(cards_frame, "found", "User .codex")
    make_card(cards_frame, "model", "Model")
    make_card(cards_frame, "reasoning", "Reasoning")
    make_card(cards_frame, "projects", "Trusted Projects")
    make_card(cards_frame, "activity", "Last Local Activity")
    make_card(cards_frame, "usage", "Live Usage")

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=12, pady=8)

    overview_text = ScrolledText(notebook, wrap="word", font=("Consolas", 10))
    config_text = ScrolledText(notebook, wrap="word", font=("Consolas", 10))
    projects_text = ScrolledText(notebook, wrap="word", font=("Consolas", 10))
    files_text = ScrolledText(notebook, wrap="word", font=("Consolas", 10))
    activity_text = ScrolledText(notebook, wrap="word", font=("Consolas", 10))
    safety_text = ScrolledText(notebook, wrap="word", font=("Consolas", 10))

    for widget in [overview_text, config_text, projects_text, files_text, activity_text, safety_text]:
        widget.configure(state="normal")

    notebook.add(overview_text, text="Overview")
    notebook.add(config_text, text="Config")
    notebook.add(projects_text, text="Trusted Projects")
    notebook.add(files_text, text="Local Files")
    notebook.add(activity_text, text="Activity Files")
    notebook.add(safety_text, text="Safety")

    def set_text(widget: ScrolledText, text_value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text_value)
        widget.configure(state="normal")

    def overview_summary(data: DashboardData) -> str:
        return "\n".join(
            [
                "Overview",
                "=" * 70,
                "",
                f"Computer: {platform.node()}",
                f"OS: {platform.platform()}",
                f"User home: {Path.home()}",
                "",
                f"User .codex path: {data.user_codex_path}",
                f"User .codex exists: {data.user_codex_exists}",
                f"User .codex modified: {data.user_codex_modified}",
                f"File count: {data.file_count}",
                f"Folder count: {data.folder_count}",
                f"Newest local item: {data.newest_path}",
                f"Newest local item modified: {data.newest_modified}",
                "",
                RATE_LIMIT_NOTE,
                "",
                READ_ONLY_NOTE,
            ]
        )

    def config_summary(data: DashboardData) -> str:
        lines = [
            "Config",
            "=" * 70,
            "",
            f"model: {data.model}",
            f"model_reasoning_effort: {data.reasoning_effort}",
            f"windows.sandbox: {data.windows_sandbox}",
            "",
            "Safe Config Values",
            "-" * 70,
        ]

        safe_items = [
            (key, value)
            for key, value in sorted(data.safe_config_values.items())
            if not is_sensitive_text(key) and not is_sensitive_text(value)
        ]

        if safe_items:
            for key, value in safe_items:
                lines.append(f"{key}: {value}")
        else:
            lines.append("(No safe config values parsed.)")

        lines.extend(
            [
                "",
                "Safe Config Preview",
                "-" * 70,
                data.safe_config_preview,
            ]
        )
        return "\n".join(lines)

    def projects_summary(data: DashboardData) -> str:
        rows = [
            [
                project.path_text,
                project.trust_level,
                "Yes" if project.exists_now else "No",
                project.status,
            ]
            for project in data.trusted_projects
        ]
        if not rows:
            return "Trusted Projects\n" + "=" * 70 + "\n\n(No trusted project entries found.)"

        return (
            "Trusted Projects\n"
            + "=" * 70
            + "\n\n"
            + rows_to_text(["Path", "Trust Level", "Exists Now", "Status"], rows)
        )

    def files_summary(data: DashboardData) -> str:
        rows = [
            [
                record.name,
                record.item_type,
                record.modified,
                record.size_text,
                record.safety,
            ]
            for record in data.local_files
        ]
        if not rows:
            return "Local Files\n" + "=" * 70 + "\n\n(No local files listed.)"

        return (
            "Local Files\n"
            + "=" * 70
            + "\n\n"
            + rows_to_text(["Name", "Type", "Modified", "Size", "Safety"], rows)
        )

    def activity_summary(data: DashboardData) -> str:
        rows = [
            [
                record.name,
                record.item_type,
                record.modified,
                record.size_text,
                record.safety,
            ]
            for record in data.activity_files
        ]

        return (
            "Activity Files\n"
            + "=" * 70
            + "\n\n"
            + "These are local activity artifacts only. They are not live account usage or live rate-limit counters.\n\n"
            + rows_to_text(["Name", "Type", "Modified", "Size", "Meaning"], rows)
        )

    def safety_summary() -> str:
        return "\n".join(
            [
                "Safety",
                "=" * 70,
                "",
                "Read-only: Yes",
                "Network calls: No",
                "OpenAI API calls: No",
                "Provider calls: No",
                "Browser automation: No",
                "Secrets redacted: Yes",
                "Sensitive-looking filenames: Hidden/redacted",
                "config.toml: Safe preview only",
                "auth.json: Existence/metadata only; contents not displayed",
                "history/log/state files: Metadata only by default",
                "Live rate limits: Not locally readable unless Codex exposes/stores them locally",
                "",
                RATE_LIMIT_NOTE,
                "",
                READ_ONLY_NOTE,
            ]
        )

    def refresh() -> None:
        data = build_dashboard_data()
        data_holder["data"] = data

        card_labels["found"].configure(text="Found" if data.user_codex_exists else "Missing")
        card_labels["model"].configure(text=data.model)
        card_labels["reasoning"].configure(text=data.reasoning_effort)
        card_labels["projects"].configure(text=str(len(data.trusted_projects)))
        card_labels["activity"].configure(text=f"{data.newest_path}\n{data.newest_modified}")
        card_labels["usage"].configure(text="Server-side\nNot locally readable")

        set_text(overview_text, overview_summary(data))
        set_text(config_text, config_summary(data))
        set_text(projects_text, projects_summary(data))
        set_text(files_text, files_summary(data))
        set_text(activity_text, activity_summary(data))
        set_text(safety_text, safety_summary())

    def current_tab_text() -> str:
        selected = notebook.select()
        widget = root.nametowidget(selected)
        if isinstance(widget, ScrolledText):
            return widget.get("1.0", "end").strip()
        return ""

    def copy_current_tab() -> None:
        root.clipboard_clear()
        root.clipboard_append(current_tab_text())
        messagebox.showinfo("Copied", "Current tab summary copied to clipboard.")

    def copy_full_summary() -> None:
        data = data_holder["data"]
        root.clipboard_clear()
        root.clipboard_append(data.full_summary)
        messagebox.showinfo("Copied", "Full summary copied to clipboard.")

    def open_user_codex() -> None:
        try:
            open_folder(Path.home() / ".codex")
        except Exception as exc:
            messagebox.showerror("Unable to open folder", str(exc))

    button_frame = tk.Frame(root)
    button_frame.pack(fill="x", padx=12, pady=(0, 12))

    tk.Button(button_frame, text="Refresh", command=refresh).pack(side="left", padx=(0, 8))
    tk.Button(button_frame, text="Open User .codex Folder", command=open_user_codex).pack(side="left", padx=(0, 8))
    tk.Button(button_frame, text="Copy Current Tab Summary", command=copy_current_tab).pack(side="left", padx=(0, 8))
    tk.Button(button_frame, text="Copy Full Summary", command=copy_full_summary).pack(side="left", padx=(0, 8))
    tk.Button(button_frame, text="Close", command=root.destroy).pack(side="right")

    refresh()
    root.mainloop()


def run_pyside6_gui() -> bool:
    try:
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import (
            QApplication,
            QHBoxLayout,
            QLabel,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QTabWidget,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except Exception:
        return False

    class CodexStatusWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("Standalone Codex Status Viewer")
            self.resize(1220, 820)
            self.data = build_dashboard_data()

            central = QWidget()
            root_layout = QVBoxLayout(central)

            title = QLabel("Standalone Codex Status Viewer")
            title_font = QFont()
            title_font.setPointSize(17)
            title_font.setBold(True)
            title.setFont(title_font)
            root_layout.addWidget(title)

            note = QLabel(RATE_LIMIT_NOTE)
            note.setWordWrap(True)
            root_layout.addWidget(note)

            self.cards_layout = QHBoxLayout()
            root_layout.addLayout(self.cards_layout)

            self.card_labels: Dict[str, QLabel] = {}
            self._make_card("found", "User .codex")
            self._make_card("model", "Model")
            self._make_card("reasoning", "Reasoning")
            self._make_card("projects", "Trusted Projects")
            self._make_card("activity", "Last Local Activity")
            self._make_card("usage", "Live Usage")

            self.tabs = QTabWidget()
            root_layout.addWidget(self.tabs, stretch=1)

            self.overview_text = self._make_text_tab("Overview")
            self.config_text = self._make_text_tab("Config")
            self.projects_text = self._make_text_tab("Trusted Projects")
            self.files_text = self._make_text_tab("Local Files")
            self.activity_text = self._make_text_tab("Activity Files")
            self.safety_text = self._make_text_tab("Safety")

            buttons = QHBoxLayout()
            root_layout.addLayout(buttons)

            refresh_button = QPushButton("Refresh")
            refresh_button.clicked.connect(self.refresh)
            buttons.addWidget(refresh_button)

            open_button = QPushButton("Open User .codex Folder")
            open_button.clicked.connect(self.open_user_codex)
            buttons.addWidget(open_button)

            copy_tab_button = QPushButton("Copy Current Tab Summary")
            copy_tab_button.clicked.connect(self.copy_current_tab)
            buttons.addWidget(copy_tab_button)

            copy_full_button = QPushButton("Copy Full Summary")
            copy_full_button.clicked.connect(self.copy_full_summary)
            buttons.addWidget(copy_full_button)

            buttons.addStretch(1)

            close_button = QPushButton("Close")
            close_button.clicked.connect(self.close)
            buttons.addWidget(close_button)

            self.setCentralWidget(central)
            self.refresh()

        def _make_card(self, key: str, title_text: str) -> None:
            box = QWidget()
            layout = QVBoxLayout(box)
            title = QLabel(title_text)
            title_font = QFont()
            title_font.setBold(True)
            title.setFont(title_font)
            value = QLabel("")
            value.setWordWrap(True)
            layout.addWidget(title)
            layout.addWidget(value)
            self.cards_layout.addWidget(box)
            self.card_labels[key] = value

        def _make_text_tab(self, title: str) -> QTextEdit:
            text = QTextEdit()
            text.setReadOnly(True)
            mono = QFont("Consolas")
            mono.setPointSize(10)
            text.setFont(mono)
            self.tabs.addTab(text, title)
            return text

        def overview_summary(self) -> str:
            data = self.data
            return "\n".join(
                [
                    "Overview",
                    "=" * 70,
                    "",
                    f"Computer: {platform.node()}",
                    f"OS: {platform.platform()}",
                    f"User home: {Path.home()}",
                    "",
                    f"User .codex path: {data.user_codex_path}",
                    f"User .codex exists: {data.user_codex_exists}",
                    f"User .codex modified: {data.user_codex_modified}",
                    f"File count: {data.file_count}",
                    f"Folder count: {data.folder_count}",
                    f"Newest local item: {data.newest_path}",
                    f"Newest local item modified: {data.newest_modified}",
                    "",
                    RATE_LIMIT_NOTE,
                    "",
                    READ_ONLY_NOTE,
                ]
            )

        def config_summary(self) -> str:
            data = self.data
            lines = [
                "Config",
                "=" * 70,
                "",
                f"model: {data.model}",
                f"model_reasoning_effort: {data.reasoning_effort}",
                f"windows.sandbox: {data.windows_sandbox}",
                "",
                "Safe Config Values",
                "-" * 70,
            ]

            safe_items = [
                (key, value)
                for key, value in sorted(data.safe_config_values.items())
                if not is_sensitive_text(key) and not is_sensitive_text(value)
            ]

            if safe_items:
                for key, value in safe_items:
                    lines.append(f"{key}: {value}")
            else:
                lines.append("(No safe config values parsed.)")

            lines.extend(
                [
                    "",
                    "Safe Config Preview",
                    "-" * 70,
                    data.safe_config_preview,
                ]
            )
            return "\n".join(lines)

        def projects_summary(self) -> str:
            data = self.data
            rows = [
                [
                    project.path_text,
                    project.trust_level,
                    "Yes" if project.exists_now else "No",
                    project.status,
                ]
                for project in data.trusted_projects
            ]
            if not rows:
                return "Trusted Projects\n" + "=" * 70 + "\n\n(No trusted project entries found.)"

            return (
                "Trusted Projects\n"
                + "=" * 70
                + "\n\n"
                + rows_to_text(["Path", "Trust Level", "Exists Now", "Status"], rows)
            )

        def files_summary(self) -> str:
            data = self.data
            rows = [
                [
                    record.name,
                    record.item_type,
                    record.modified,
                    record.size_text,
                    record.safety,
                ]
                for record in data.local_files
            ]
            if not rows:
                return "Local Files\n" + "=" * 70 + "\n\n(No local files listed.)"

            return (
                "Local Files\n"
                + "=" * 70
                + "\n\n"
                + rows_to_text(["Name", "Type", "Modified", "Size", "Safety"], rows)
            )

        def activity_summary(self) -> str:
            data = self.data
            rows = [
                [
                    record.name,
                    record.item_type,
                    record.modified,
                    record.size_text,
                    record.safety,
                ]
                for record in data.activity_files
            ]

            return (
                "Activity Files\n"
                + "=" * 70
                + "\n\n"
                + "These are local activity artifacts only. They are not live account usage or live rate-limit counters.\n\n"
                + rows_to_text(["Name", "Type", "Modified", "Size", "Meaning"], rows)
            )

        def safety_summary(self) -> str:
            return "\n".join(
                [
                    "Safety",
                    "=" * 70,
                    "",
                    "Read-only: Yes",
                    "Network calls: No",
                    "OpenAI API calls: No",
                    "Provider calls: No",
                    "Browser automation: No",
                    "Secrets redacted: Yes",
                    "Sensitive-looking filenames: Hidden/redacted",
                    "config.toml: Safe preview only",
                    "auth.json: Existence/metadata only; contents not displayed",
                    "history/log/state files: Metadata only by default",
                    "Live rate limits: Not locally readable unless Codex exposes/stores them locally",
                    "",
                    RATE_LIMIT_NOTE,
                    "",
                    READ_ONLY_NOTE,
                ]
            )

        def refresh(self) -> None:
            self.data = build_dashboard_data()

            self.card_labels["found"].setText("Found" if self.data.user_codex_exists else "Missing")
            self.card_labels["model"].setText(self.data.model)
            self.card_labels["reasoning"].setText(self.data.reasoning_effort)
            self.card_labels["projects"].setText(str(len(self.data.trusted_projects)))
            self.card_labels["activity"].setText(f"{self.data.newest_path}\n{self.data.newest_modified}")
            self.card_labels["usage"].setText("Server-side\nNot locally readable")

            self.overview_text.setPlainText(self.overview_summary())
            self.config_text.setPlainText(self.config_summary())
            self.projects_text.setPlainText(self.projects_summary())
            self.files_text.setPlainText(self.files_summary())
            self.activity_text.setPlainText(self.activity_summary())
            self.safety_text.setPlainText(self.safety_summary())

        def copy_current_tab(self) -> None:
            widget = self.tabs.currentWidget()
            if isinstance(widget, QTextEdit):
                QApplication.clipboard().setText(widget.toPlainText())
                QMessageBox.information(self, "Copied", "Current tab summary copied to clipboard.")

        def copy_full_summary(self) -> None:
            QApplication.clipboard().setText(self.data.full_summary)
            QMessageBox.information(self, "Copied", "Full summary copied to clipboard.")

        def open_user_codex(self) -> None:
            try:
                open_folder(Path.home() / ".codex")
            except Exception as exc:
                QMessageBox.critical(self, "Unable to open folder", str(exc))

    app = QApplication.instance() or QApplication(sys.argv)
    window = CodexStatusWindow()
    window.show()
    app.exec()
    return True


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Standalone local/offline Codex Status Viewer")
    parser.add_argument("--self-test", action="store_true", help="Run built-in self-test and exit")
    parser.add_argument("--text", action="store_true", help="Print full dashboard summary to terminal")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.self_test:
        return run_self_test()

    if args.text:
        print(build_dashboard_data().full_summary)
        return 0

    if run_pyside6_gui():
        return 0

    run_tkinter_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())