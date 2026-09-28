"""ENGEL CODE COMPANION local product-building workbench.

The companion is a local, approval-gated GUI for inspecting a user-selected
project folder, previewing bounded text/code files, drafting deterministic
proposal text, creating product workspaces, applying approved product changes,
and saving audit receipts. It does not call providers, browse, index the
computer, start workers, or apply unapproved edits.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import engel_code_companion_examples as example_scripts
import engel_code_companion_conversation_commands as conversation_commands
import engel_code_companion_lessons as lesson_candidates
import engel_code_companion_lesson_review as lesson_review
import engel_code_companion_patch_lesson_bridge as patch_lesson_bridge
import engel_code_companion_patch_lesson_review as patch_lesson_review
import engel_code_companion_products as product_templates
import engel_code_companion_product_cycle_dashboard as product_cycle_dashboard
import engel_code_companion_product_context as product_context
import engel_code_companion_product_session as product_session
import engel_code_companion_product_workbench as product_workbench
import engel_code_companion_talk_to_code as talk_to_code
import engel_research_summary_proposals as research_summary_proposals
import engel_untrusted_content_guard as untrusted_content_guard
import engel_code_workshop as workshop


APP_TITLE = "ENGEL CODE COMPANION"
ONE_LINE_DESCRIPTION = (
    "ENGEL CODE COMPANION is Engel's safe local product-building workbench for "
    "creating, inspecting, editing, verifying, and packaging code projects - "
    "including Engel modules, standalone apps, websites, tools, scripts, and "
    "future products."
)

# ENGEL_CODE_COMPANION_MINIMAL_TECH_THEME_V1_START
CODE_COMPANION_MINIMAL_TECH_THEME_MARKER = "Engel Minimal Tech Console"
CODE_COMPANION_BG_PRIMARY = "#07090C"
CODE_COMPANION_BG_PANEL = "#0D1117"
CODE_COMPANION_BG_CARD = "#121821"
CODE_COMPANION_BG_CARD_ALT = "#161C25"
CODE_COMPANION_BORDER_SUBTLE = "#26313D"
CODE_COMPANION_BORDER_FOCUS = "#5BC8FF"
CODE_COMPANION_TEXT_PRIMARY = "#E8F4FF"
CODE_COMPANION_TEXT_SECONDARY = "#A9B7C5"
CODE_COMPANION_TEXT_MUTED = "#758596"
CODE_COMPANION_BADGE_PASS = "#73D18B"
CODE_COMPANION_BADGE_FAIL = "#FF6B6B"
CODE_COMPANION_BADGE_BLOCKED = "#FF6B6B"
CODE_COMPANION_BADGE_PROPOSAL = "#5BC8FF"
CODE_COMPANION_BADGE_APPROVAL_REQUIRED = "#E6C96A"
CODE_COMPANION_ACCENT_SAFE = "#73D18B"
# ENGEL_CODE_COMPANION_MINIMAL_TECH_THEME_V1_END


def detect_app_root() -> Path:
    try:
        return Path(__file__).resolve().parent
    except (NameError, OSError, ValueError):
        return Path.cwd().resolve()


APP_ROOT = detect_app_root()
ROOT = APP_ROOT
REPORT_ROOT = APP_ROOT / "reports" / "codex_bridge"
RECEIPT_PREFIX = "ENGEL_CODE_COMPANION_RECEIPT"
PRODUCTS_ROOT = APP_ROOT / "products"
BACKUPS_ROOT = APP_ROOT / "backups"
PRODUCT_RECEIPT_PREFIX = "ENGEL_PRODUCT_ACTION_RECEIPT"
PRODUCT_REPORT_PREFIX = "ENGEL_PRODUCT_BUILD_REPORT"
CHANGE_APPROVAL_TOKEN = "APPROVE_CHANGE"
REPORT_ONLY_STATEMENT = (
    "All generated explanations and edits are proposal text only. No "
    "autonomous write/execute behavior occurred."
)
PRODUCT_BUILDER_BOUNDARY_STATEMENT = (
    "PRODUCT BUILDER V2 / PROPOSAL FIRST / APPROVAL GATED. Product files stay "
    "inside the selected bounded product workspace. Generated files and patches "
    "remain proposal text until exact APPROVE_CHANGE approval is supplied. "
    "Backups are written before overwriting existing files."
)
DESIGN_FIRST_BOUNDARY_STATEMENT = (
    "DESIGN ONLY / NOT APPLIED. Authority order remains Josh > Guardian > Engel/runtime. "
    "No source edit, shell command, provider/API/network behavior, trusted-memory write, "
    "queue mutation, route mutation, package install, startup behavior, shortcut behavior, "
    "or autonomous apply behavior is enabled."
)

MAX_TREE_ENTRIES = 600
MAX_TREE_DEPTH = 5
MAX_FILE_BYTES = 300_000
MAX_PREVIEW_CHARS = 80_000
MAX_SUMMARY_CHARS = 24_000
MAX_RECEIPT_CHARS = 30_000
MAX_RELEVANT_LINES = 18
VERIFICATION_TIMEOUT_SECONDS = 45
MAX_PRODUCT_FILES_PER_CHANGE = 12
MAX_PRODUCT_FILE_CHARS = 60_000
MAX_PRODUCT_RELATIVE_PATH_CHARS = 180

PRODUCT_TYPE_OPTIONS = (
    "Python app",
    "Python script",
    "HTML/CSS/JS website",
    "Java app",
    "Utility/tool",
    "Engel module",
    "Custom project",
)

PRODUCT_VERIFICATION_ALLOWLIST: dict[str, tuple[str, ...]] = {
    "python app": (
        "python -m py_compile selected .py files",
        "python tools\\verify_engel_code_companion.py",
    ),
    "python script": (
        "python -m py_compile selected .py files",
        "python tools\\verify_engel_code_companion.py",
    ),
    "html/css/js website": (
        "basic HTML/CSS/JS structure verifier",
        "python tools\\verify_engel_code_companion.py",
    ),
    "java app": (
        "JAVA_COMPILE_NOT_RUN / proposal-only compiler boundary",
        "python tools\\verify_engel_code_companion.py",
    ),
    "utility/tool": (
        "python -m py_compile selected .py files when present",
        "python tools\\verify_engel_code_companion.py",
    ),
    "engel module": (
        "python tools\\verify_engel_code_companion.py",
        "powershell -ExecutionPolicy Bypass -File scripts\\codex_verify.ps1",
    ),
    "custom project": (
        "basic bounded text/project structure verifier",
        "python tools\\verify_engel_code_companion.py",
    ),
}

PRODUCT_PROFILE_FILENAME = ".engel_product_profile.json"
PACKAGE_MANIFEST_FILENAME = "ENGEL_PACKAGE_MANIFEST.json"
LAUNCH_APPROVAL_TOKEN = "APPROVE_LAUNCH"
PACKAGE_APPROVAL_TOKEN = "APPROVE_PACKAGE"
PRODUCT_PROFILE_SCHEMA = "engel_product_profile_v1"
PRODUCT_DIST_DIRNAME = "dist"
PRODUCT_LOCAL_BACKUP_DIRNAME = ".engel_backups"
PRODUCT_LOCAL_RECEIPT_DIRNAME = ".engel_receipts"
LAUNCH_TIMEOUT_SECONDS = 8
MAX_PACKAGE_FILES = 1000
MAX_PACKAGE_FILE_BYTES = 5 * 1024 * 1024

PRODUCT_TYPE_PROFILE_IDS: dict[str, str] = {
    "python app": "python_app",
    "python script": "python_script",
    "html/css/js website": "html_css_js_website",
    "java app": "java_app",
    "utility/tool": "utility_tool",
    "engel module": "engel_module",
    "custom project": "custom_project",
}

PROFILE_ID_PRODUCT_TYPES: dict[str, str] = {
    value: key for key, value in PRODUCT_TYPE_PROFILE_IDS.items()
}

TEXT_EXTENSIONS = {
    ".bat",
    ".cfg",
    ".cmd",
    ".css",
    ".csv",
    ".gitignore",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".log",
    ".md",
    ".ps1",
    ".py",
    ".rst",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

TEXT_FILE_NAMES = {
    "dockerfile",
    "makefile",
    "readme",
    "license",
    "license.txt",
    "requirements.txt",
}

SKIP_TREE_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "site-packages",
}

PACKAGE_EXCLUDED_DIRS = SKIP_TREE_DIRS | {
    PRODUCT_DIST_DIRNAME,
    PRODUCT_LOCAL_BACKUP_DIRNAME,
    PRODUCT_LOCAL_RECEIPT_DIRNAME,
    "venv",
}

SENSITIVE_PATH_PARTS = {
    ".aws",
    ".azure",
    ".config",
    ".docker",
    ".gnupg",
    ".kube",
    ".ssh",
    "appdata",
    "credentials",
    "credential",
    "cookies",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "keychain",
    "local settings",
    "login data",
    "microsoft credentials",
    "passwords",
    "secrets",
    "tokens",
    "wallet",
}

SENSITIVE_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".netrc",
    "authorized_keys",
    "credentials",
    "credentials.json",
    "id_rsa",
    "id_rsa.pub",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "known_hosts",
}

SENSITIVE_FILE_SUFFIXES = {
    ".crt",
    ".key",
    ".kdbx",
    ".p12",
    ".pem",
    ".pfx",
}

PACKAGE_EXCLUDED_SUFFIXES = SENSITIVE_FILE_SUFFIXES | {".zip", ".7z", ".rar"}

PERSISTENT_LAUNCH_TOKENS = (
    "serve_forever",
    "http.server",
    "socketserver",
    "flask",
    "django",
    "uvicorn",
    "fastapi",
    "app.run(",
    "while " + "True",
)

SENSITIVE_RE = re.compile(
    r"(api[_\-\s]?key|authorization|bearer|client[_\-\s]?secret|credential|"
    r"password|private[_\-\s]?key|refresh[_\-\s]?token|secret|session|token)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ProjectValidation:
    ok: bool
    path: Path | None
    status: str
    reason: str


@dataclass(frozen=True)
class TreeEntry:
    path: Path
    relative_path: str
    name: str
    depth: int
    kind: str
    size: int | None
    safety_status: str
    unavailable_reason: str


@dataclass(frozen=True)
class TreeBuildResult:
    entries: tuple[TreeEntry, ...]
    hidden_count: int
    truncated: bool
    status: str
    message: str


@dataclass(frozen=True)
class SelectedFile:
    path: Path | None
    relative_path: str
    size: int
    extension: str
    safety_status: str
    text: str
    unavailable_reason: str
    truncated: bool


@dataclass(frozen=True)
class VerificationResult:
    requested: bool
    approved: bool
    command: str
    return_code: int | None
    output: str
    status: str


@dataclass(frozen=True)
class ProductProfileResult:
    ok: bool
    status: str
    message: str
    profile_path: Path | None = None
    profile: dict[str, Any] | None = None
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class LaunchPreviewResult:
    ok: bool
    status: str
    message: str
    profile_name: str = ""
    command: tuple[str, ...] = ()
    command_text: str = ""


@dataclass(frozen=True)
class LaunchRunResult:
    ok: bool
    status: str
    message: str
    command_text: str = ""
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    receipt_path: Path | None = None


@dataclass(frozen=True)
class PackagePreviewResult:
    ok: bool
    status: str
    message: str
    package_name: str = ""
    output_dir: Path | None = None
    manifest_path: Path | None = None
    files: tuple[str, ...] = ()
    excluded: tuple[str, ...] = ()


@dataclass(frozen=True)
class PackageCreateResult:
    ok: bool
    status: str
    message: str
    zip_path: Path | None = None
    manifest_path: Path | None = None
    receipt_path: Path | None = None
    files: tuple[str, ...] = ()
    excluded: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProductFileProposal:
    relative_path: str
    path: Path
    proposed_content: str
    action: str
    backup_required: bool


@dataclass(frozen=True)
class ProductChangeProposal:
    product_root: Path
    product_type: str
    action: str
    files: tuple[ProductFileProposal, ...]
    summary: str
    approved: bool = False
    approval_token: str = ""


@dataclass(frozen=True)
class ProductApplyResult:
    ok: bool
    status: str
    message: str
    written_paths: tuple[Path, ...]
    backup_paths: tuple[Path, ...]
    receipt_path: Path | None


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def filename_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_resolve(path: Path) -> Path | None:
    try:
        return Path(path).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return None


def _is_url_or_unc(value: object) -> bool:
    text = str(value or "").strip()
    lowered = text.lower()
    return lowered.startswith(("http" + "://", "https" + "://", "\\\\", "//"))


def _case_parts(path: Path) -> tuple[str, ...]:
    return tuple(part.rstrip("\\/").lower() for part in path.parts if part.rstrip("\\/"))


def _is_drive_or_filesystem_root(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError, ValueError):
        resolved = path
    parent = resolved.parent
    return parent == resolved or str(resolved).rstrip("\\/") == resolved.anchor.rstrip("\\/")


def _is_users_sweep(path: Path) -> bool:
    parts = _case_parts(path)
    if len(parts) < 2:
        return False
    if parts[1] != "users":
        return False
    return len(parts) <= 3


def _contains_sensitive_part(path: Path) -> bool:
    parts = _case_parts(path)
    if any(part in SENSITIVE_PATH_PARTS for part in parts):
        return True
    browser_parts = {"chrome", "chromium", "edge", "firefox", "brave", "opera"}
    return "appdata" in parts and any(part in browser_parts for part in parts)


def _is_windows_system_area(path: Path) -> bool:
    parts = _case_parts(path)
    if len(parts) < 2:
        return False
    system_roots = {
        "program files",
        "program files (x86)",
        "programdata",
        "recovery",
        "system volume information",
        "windows",
    }
    return parts[1] in system_roots


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_project_root(path_value: object) -> ProjectValidation:
    if not path_value:
        return ProjectValidation(False, None, "BLOCKED", "No project folder selected.")
    if _is_url_or_unc(path_value):
        return ProjectValidation(False, None, "BLOCKED", "UNC, URL, and remote paths are blocked in v1.")

    candidate = _safe_resolve(Path(str(path_value)))
    if candidate is None:
        return ProjectValidation(False, None, "BLOCKED", "Project folder could not be resolved safely.")
    if not candidate.exists() or not candidate.is_dir():
        return ProjectValidation(False, candidate, "BLOCKED", "Selected path is not an existing folder.")
    if _is_drive_or_filesystem_root(candidate):
        return ProjectValidation(False, candidate, "BLOCKED", "Whole-drive or filesystem roots are blocked.")
    if _is_users_sweep(candidate):
        return ProjectValidation(False, candidate, "BLOCKED", "C:\\Users sweeping and user-profile roots are blocked.")
    if _is_windows_system_area(candidate):
        return ProjectValidation(False, candidate, "BLOCKED", "Windows/system folders are blocked.")
    if _contains_sensitive_part(candidate):
        return ProjectValidation(False, candidate, "BLOCKED", "Sensitive credential/browser/profile path segment is blocked.")
    return ProjectValidation(True, candidate, "ALLOWED", "Project folder is bounded and approved for manual browsing.")


def is_path_sensitive_or_blocked(path: Path) -> tuple[bool, str]:
    if _is_url_or_unc(path):
        return True, "UNC, URL, and remote paths are blocked."
    if _contains_sensitive_part(path):
        return True, "Sensitive path segment blocked."
    name = path.name.lower()
    if name in SENSITIVE_FILE_NAMES:
        return True, "Sensitive credential/environment filename blocked."
    if path.suffix.lower() in SENSITIVE_FILE_SUFFIXES:
        return True, "Sensitive key/certificate file type blocked."
    if SENSITIVE_RE.search(name):
        return True, "Sensitive-looking filename blocked."
    return False, ""


def validate_path_under_project(project_root: Path, candidate: Path) -> tuple[bool, Path | None, str]:
    root = _safe_resolve(project_root)
    child = _safe_resolve(candidate)
    if root is None or child is None:
        return False, None, "Path could not be resolved safely."
    if not _is_relative_to(child, root):
        return False, child, "Path escapes the selected project root."
    if child.is_symlink():
        return False, child, "Symlink paths are blocked in v1."
    blocked, reason = is_path_sensitive_or_blocked(child)
    if blocked:
        return False, child, reason
    return True, child, "Path is inside the selected project root."


def _is_supported_text_name(path: Path) -> bool:
    suffix = path.suffix.lower()
    name = path.name.lower()
    return suffix in TEXT_EXTENSIONS or name in TEXT_FILE_NAMES


def classify_file_availability(path: Path, size: int | None = None) -> tuple[str, str]:
    blocked, reason = is_path_sensitive_or_blocked(path)
    if blocked:
        return "BLOCKED", reason
    if not _is_supported_text_name(path):
        return "UNAVAILABLE", "Unsupported or binary-looking extension."
    if size is not None and size > MAX_FILE_BYTES:
        return "UNAVAILABLE", f"File exceeds {MAX_FILE_BYTES} byte preview limit."
    return "READ_ONLY", "Bounded text/code preview is available."


def _size_text(size: int | None) -> str:
    if size is None:
        return "-"
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _iter_child_entries(folder: Path) -> list[Path]:
    try:
        children = list(folder.iterdir())
    except OSError:
        return []
    return sorted(children, key=lambda item: (not item.is_dir(), item.name.lower()))


def build_project_tree(project_root: Path) -> TreeBuildResult:
    validation = validate_project_root(project_root)
    if not validation.ok or validation.path is None:
        return TreeBuildResult((), 0, False, validation.status, validation.reason)

    root = validation.path
    entries: list[TreeEntry] = [
        TreeEntry(root, ".", root.name, 0, "folder", None, "ALLOWED", "")
    ]
    hidden_count = 0
    truncated = False
    queue: list[tuple[Path, int]] = [(root, 0)]
    index = 0

    while index < len(queue):
        folder, depth = queue[index]
        index += 1
        if depth >= MAX_TREE_DEPTH:
            continue

        for child in _iter_child_entries(folder):
            if len(entries) >= MAX_TREE_ENTRIES:
                truncated = True
                break
            try:
                relative = child.relative_to(root)
            except ValueError:
                hidden_count += 1
                continue

            if child.is_symlink():
                hidden_count += 1
                continue

            blocked, reason = is_path_sensitive_or_blocked(child)
            if blocked:
                hidden_count += 1
                continue

            name_lower = child.name.lower()
            if child.is_dir() and name_lower in SKIP_TREE_DIRS:
                hidden_count += 1
                continue

            if child.is_dir():
                entries.append(
                    TreeEntry(
                        child,
                        str(relative).replace("/", "\\"),
                        child.name,
                        depth + 1,
                        "folder",
                        None,
                        "ALLOWED",
                        "",
                    )
                )
                queue.append((child, depth + 1))
                continue

            if not child.is_file():
                hidden_count += 1
                continue

            try:
                size = child.stat().st_size
            except OSError:
                size = None
            status, unavailable = classify_file_availability(child, size)
            entries.append(
                TreeEntry(
                    child,
                    str(relative).replace("/", "\\"),
                    child.name,
                    depth + 1,
                    "file",
                    size,
                    status,
                    "" if status == "READ_ONLY" else unavailable,
                )
            )
        if truncated:
            break

    message = f"{len(entries)} bounded item(s) shown"
    if hidden_count:
        message += f"; {hidden_count} sensitive/skipped item(s) hidden"
    if truncated:
        message += f"; stopped at {MAX_TREE_ENTRIES} items"
    return TreeBuildResult(tuple(entries), hidden_count, truncated, "ALLOWED", message)


def _binary_marker_present(raw: bytes) -> bool:
    return b"\x00" in raw[:4096]


def unavailable_file(path: Path | None, reason: str, relative_path: str = "") -> SelectedFile:
    suffix = path.suffix.lower() if path is not None else ""
    return SelectedFile(path, relative_path, 0, suffix, "UNAVAILABLE", "", reason, False)


def read_file_preview(project_root: Path, file_path: Path) -> SelectedFile:
    ok, resolved, reason = validate_path_under_project(project_root, file_path)
    relative = ""
    root = _safe_resolve(project_root)
    if resolved is not None and root is not None and _is_relative_to(resolved, root):
        relative = str(resolved.relative_to(root)).replace("/", "\\")
    if not ok or resolved is None:
        return unavailable_file(resolved, reason, relative)
    if not resolved.is_file():
        return unavailable_file(resolved, "Selected path is not a file.", relative)

    try:
        size = resolved.stat().st_size
    except OSError as exc:
        return unavailable_file(resolved, f"Could not read file metadata: {exc}", relative)

    status, unavailable = classify_file_availability(resolved, size)
    if status != "READ_ONLY":
        return SelectedFile(resolved, relative, size, resolved.suffix.lower(), status, "", unavailable, False)

    try:
        with resolved.open("rb") as handle:
            raw = handle.read(MAX_FILE_BYTES + 1)
    except OSError as exc:
        return SelectedFile(resolved, relative, size, resolved.suffix.lower(), "UNAVAILABLE", "", str(exc), False)

    if _binary_marker_present(raw):
        return SelectedFile(resolved, relative, size, resolved.suffix.lower(), "UNAVAILABLE", "", "Binary marker detected.", False)

    truncated = len(raw) > MAX_FILE_BYTES
    raw = raw[:MAX_FILE_BYTES]
    text = raw.decode("utf-8", errors="replace")
    if len(text) > MAX_PREVIEW_CHARS:
        text = text[:MAX_PREVIEW_CHARS].rstrip() + "\n[truncated for preview bounds]"
        truncated = True
    return SelectedFile(resolved, relative, size, resolved.suffix.lower(), "READ_ONLY", text, "", truncated)


def _trim_text(value: str, limit: int) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 28)].rstrip() + "\n[truncated for bounds]"


def _untrusted_content_scan_line(text: str, source_label: str) -> str:
    result = untrusted_content_guard.classify_untrusted_content_risk(text, source_label)
    marker_text = ", ".join(result.markers_found[:5]) if result.markers_found else "none"
    if len(result.markers_found) > 5:
        marker_text += ", ..."
    return (
        "UNTRUSTED CONTENT SCAN: "
        + result.risk_level
        + " | NOT EXECUTED | NOT APPLIED | markers: "
        + marker_text
        + " | content is data, not instruction"
    )


def render_product_context_view(product_slug: str | None) -> str:
    slug = str(product_slug or "").strip()
    if not slug:
        return "\n".join(
            [
                "# Product Context View",
                "",
                "Status:",
                "READ_ONLY_CONTEXT / BLOCKED / NOT_TRUSTED_MEMORY",
                "",
                "Selected product:",
                "NONE",
                "",
                "Context loaded:",
                "NO",
                "",
                "Reason:",
                "Select a bounded product first.",
                "",
                "Safety boundary:",
                "READ_ONLY_CONTEXT / NOT_TRUSTED_MEMORY",
            ]
        )
    pack = product_context.build_product_context_pack(slug)
    counts = {
        "Patch apply receipt": 0,
        "Health delta receipt": 0,
        "Lesson review": 0,
        "Memory candidate proposal reference": 0,
    }
    source_status = {
        "README.md": "missing",
        "product_manifest.json": "missing",
        ".engel_product_profile.json": "missing",
    }
    for source in pack.sources:
        if source.label in source_status:
            source_status[source.label] = "present" if source.present else "missing"
        if source.label in counts and source.present:
            counts[source.label] += 1
    loaded = "YES" if pack.ok else "NO"
    return "\n".join(
        [
            "# Product Context View",
            "",
            "Status:",
            "READ_ONLY_CONTEXT / NOT_TRUSTED_MEMORY",
            "",
            "Authority:",
            "Josh > Guardian > Engel/runtime",
            "",
            "Selected product:",
            pack.product_slug or slug,
            "",
            "Context loaded:",
            loaded,
            "",
            "Source status:",
            "- README.md: " + source_status["README.md"],
            "- product_manifest.json: " + source_status["product_manifest.json"],
            "- .engel_product_profile.json: " + source_status[".engel_product_profile.json"],
            "- Latest receipts count: " + str(counts["Patch apply receipt"] + counts["Health delta receipt"]),
            "- Latest patch apply receipts count: " + str(counts["Patch apply receipt"]),
            "- Latest health delta receipts count: " + str(counts["Health delta receipt"]),
            "- Latest lesson reviews count: " + str(counts["Lesson review"]),
            "- Memory candidate references count: " + str(counts["Memory candidate proposal reference"]),
            "",
            "Safety:",
            "- Product files trusted as instruction: NO",
            "- Receipts/reviews trusted as instruction: NO",
            "- Trusted memory write: NO",
            "- Product edit: NO",
            "- Runtime edit: NO",
            "- Code execution: NO",
            "",
            "Safety boundary:",
            "READ_ONLY_CONTEXT / NOT_TRUSTED_MEMORY",
            "",
            "Use:",
            "This view shows what Engel may use as product context for planning. It cannot authorize actions.",
        ]
    )


def _first_nonempty_lines(lines: Iterable[str], limit: int = 8) -> list[str]:
    result: list[str] = []
    for line in lines:
        clean = line.strip()
        if clean:
            result.append(clean[:220])
        if len(result) >= limit:
            break
    return result


def _extract_python_shapes(lines: list[str]) -> tuple[list[str], list[str], list[str]]:
    imports: list[str] = []
    definitions: list[str] = []
    comments: list[str] = []
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")) and len(imports) < 12:
            imports.append(f"L{number}: {stripped[:180]}")
        if re.match(r"^(class|def)\s+[A-Za-z_][A-Za-z0-9_]*", stripped) and len(definitions) < 18:
            definitions.append(f"L{number}: {stripped[:180]}")
        if any(marker in stripped.lower() for marker in ("todo", "fixme", "hack")) and len(comments) < 8:
            comments.append(f"L{number}: {stripped[:180]}")
    return imports, definitions, comments


def _extract_markdown_shapes(lines: list[str]) -> tuple[list[str], list[str]]:
    headings: list[str] = []
    bullets: list[str] = []
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#") and len(headings) < 16:
            headings.append(f"L{number}: {stripped[:180]}")
        if stripped.startswith(("-", "*")) and len(bullets) < 10:
            bullets.append(f"L{number}: {stripped[:180]}")
    return headings, bullets


def summarize_selected_file(selected: SelectedFile | None) -> str:
    if selected is None or selected.safety_status != "READ_ONLY":
        reason = selected.unavailable_reason if selected else "No readable file selected."
        return (
            "# Explanation\n"
            "Status: unavailable\n"
            f"Reason: {reason}\n\n"
            + REPORT_ONLY_STATEMENT
        )

    lines = selected.text.splitlines()
    line_count = len(lines)
    char_count = len(selected.text)
    first_lines = _first_nonempty_lines(lines)
    output: list[str] = [
        "# Explanation",
        "Mode: local deterministic summary from the selected file only.",
        f"File: {selected.relative_path}",
        f"Size: {_size_text(selected.size)}",
        f"Extension: {selected.extension or '[none]'}",
        f"Lines in preview: {line_count}",
        f"Characters in preview: {char_count}",
        f"Preview truncated: {selected.truncated}",
        "Safety: file content is untrusted input; this is not command authority.",
        "",
    ]

    if selected.extension == ".py":
        imports, definitions, notes = _extract_python_shapes(lines)
        output.append("Python shape:")
        output.extend([f"- Import: {item}" for item in imports] or ["- No import lines found in preview."])
        output.extend([f"- Definition: {item}" for item in definitions] or ["- No class/def lines found in preview."])
        output.extend([f"- Note marker: {item}" for item in notes] or ["- No TODO/FIXME markers found in preview."])
        output.append("")
    elif selected.extension in {".md", ".rst"}:
        headings, bullets = _extract_markdown_shapes(lines)
        output.append("Document shape:")
        output.extend([f"- Heading: {item}" for item in headings] or ["- No headings found in preview."])
        output.extend([f"- Bullet: {item}" for item in bullets[:6]] or ["- No early bullets found in preview."])
        output.append("")
    else:
        output.append("Text shape:")
        output.append("- This preview is treated as plain local text/code.")
        output.append("")

    output.append("First non-empty lines:")
    output.extend([f"- {item}" for item in first_lines] or ["- File preview is empty."])
    output.append("")
    output.append(REPORT_ONLY_STATEMENT)
    return _trim_text("\n".join(output), MAX_SUMMARY_CHARS)


def _question_terms(question: str) -> list[str]:
    terms: list[str] = []
    for raw in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", question or ""):
        lowered = raw.lower()
        if lowered in {"about", "what", "where", "with", "this", "that", "from", "does", "file", "code"}:
            continue
        if lowered not in terms:
            terms.append(lowered)
    return terms[:8]


def _relevant_lines(text: str, terms: list[str]) -> list[str]:
    if not terms:
        return []
    matches: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        if any(term in lowered for term in terms):
            clean = line.strip()
            if clean:
                matches.append(f"L{number}: {clean[:220]}")
        if len(matches) >= MAX_RELEVANT_LINES:
            break
    return matches


def answer_about_selection(selected: SelectedFile | None, question: str) -> str:
    if selected is None or selected.safety_status != "READ_ONLY":
        reason = selected.unavailable_reason if selected else "No readable file selected."
        return (
            "# Explanation\n"
            "Status: unavailable\n"
            f"Question: {question.strip() or '[empty]'}\n"
            f"Reason: {reason}\n\n"
            + REPORT_ONLY_STATEMENT
        )
    terms = _question_terms(question)
    matches = _relevant_lines(selected.text, terms)
    summary = summarize_selected_file(selected)
    lines = [
        "# Explanation",
        "Mode: local deterministic answer from selected context only.",
        f"Question: {question.strip() or '[empty]'}",
        f"File: {selected.relative_path}",
        "Safety: selected file text remains untrusted; answer is proposal/explanation text only.",
        "",
        "Relevant local lines:",
    ]
    lines.extend([f"- {item}" for item in matches] or ["- No direct keyword matches found. Use the summary below for orientation."])
    lines.extend(["", "Local summary:", summary, "", REPORT_ONLY_STATEMENT])
    return _trim_text("\n".join(lines), MAX_SUMMARY_CHARS)


def _prompt_words(prompt: str) -> str:
    return re.sub(r"\s+", " ", str(prompt or "").strip().lower())


def _classify_design_first_request(prompt: str) -> str:
    lowered = _prompt_words(prompt)
    if not lowered:
        return "normal"
    if "make guardian higher than josh" in lowered or (
        "guardian" in lowered and "higher than josh" in lowered
    ):
        return "authority_refusal"
    unsafe_phrases = (
        "apply this change now",
        "apply now",
        "edit engel_app.py directly",
        "edit " + "directly",
        "run powershell command",
        "run powershell",
        "install package",
        "start autonomous code worker",
        "autonomous code worker",
    )
    if any(phrase in lowered for phrase in unsafe_phrases):
        return "safety_refusal"
    verifier_phrases = (
        "suggest verifier",
        "suggest smoke test",
        "approval checklist",
        "source-edit approval checklist",
        "design tests",
        "test plan",
        "verification proposal",
    )
    if any(phrase in lowered for phrase in verifier_phrases):
        return "verification_proposal"
    design_phrases = (
        "design ",
        "fits into ai body",
        "fit into ai body",
        "without enabling apply",
        "source-edit approval",
        "safer code companion apply workflow",
    )
    if any(phrase in lowered for phrase in design_phrases):
        return "design_proposal"
    return "normal"


def _selected_context_line(selected: SelectedFile | None) -> str:
    if selected is None:
        return "Selected context: none; response is based on the request only."
    if selected.safety_status != "READ_ONLY":
        return "Selected context: unavailable; " + (selected.unavailable_reason or selected.safety_status)
    return "Selected context: " + (selected.relative_path or str(selected.path or "selected file"))


def _design_first_refusal(selected: SelectedFile | None, request: str, reason: str) -> str:
    lines = [
        "# Safety Refusal",
        "Status: REFUSED / DESIGN ONLY / NOT APPLIED",
        f"Request: {request}",
        _selected_context_line(selected),
        f"Reason: {reason}",
        "",
        "Blocked behavior:",
        "- No source edit was made.",
        "- No shell command was executed.",
        "- No provider/API/network behavior was used.",
        "- No trusted-memory write occurred.",
        "- No queue mutation occurred.",
        "- No route mutation occurred.",
        "- No package install, startup, shortcut, or autonomous apply behavior occurred.",
        "- Authority order remains Josh > Guardian > Engel/runtime.",
        "",
        "Safe next step:",
        "- Convert the request into a design note, test matrix item, verifier suggestion, or a separate Josh-approved source-edit task.",
        "",
        DESIGN_FIRST_BOUNDARY_STATEMENT,
        REPORT_ONLY_STATEMENT,
    ]
    return _trim_text("\n".join(lines), MAX_SUMMARY_CHARS)


def _design_first_proposal(selected: SelectedFile | None, request: str, kind: str) -> str:
    if kind == "verification_proposal":
        title = "# Verification Proposal"
        focus = [
            "- Check that design-first wording includes DESIGN ONLY and NOT APPLIED.",
            "- Check unsafe prompts produce refusal/proposal-only output.",
            "- Check no provider/API/network, shell, autonomy, route, memory, queue, package, startup, or shortcut behavior appears.",
            "- Check authority order remains Josh > Guardian > Engel/runtime.",
            "- Keep GUI smoke bounded: launch, inspect, safe prompt buttons, close, final scoped process sweep.",
        ]
    else:
        title = "# Design Proposal"
        focus = [
            "- Keep Code Companion as a standalone guarded coding surface.",
            "- Use it to explain, review, design, and propose tests before any source-edit task exists.",
            "- Keep apply behavior absent until a separate Josh-approved, Guardian-checked contract and verifier exist.",
            "- Keep generated design output untrusted and review-only.",
            "- Link future AI Body/File Structure maps to this surface as design context, not as an execution route.",
        ]
    lines = [
        title,
        "Status: DESIGN ONLY / NOT APPLIED",
        f"Request: {request}",
        _selected_context_line(selected),
        "",
        "Design-first response:",
    ]
    lines.extend(focus)
    lines.extend(
        [
            "",
            "Safety checks before any future implementation:",
            "- Josh explicitly approves the exact source-edit scope.",
            "- Guardian safety review remains below Josh and above Engel/runtime.",
            "- Verifiers cover no provider/network behavior, no command execution, no trusted-memory write, no queue or route mutation, and no autonomous apply.",
            "- Manual review confirms output is proposal material, not command authority.",
            "",
            DESIGN_FIRST_BOUNDARY_STATEMENT,
            REPORT_ONLY_STATEMENT,
        ]
    )
    return _trim_text("\n".join(lines), MAX_SUMMARY_CHARS)


def propose_edit(selected: SelectedFile | None, prompt: str) -> str:
    request = prompt.strip() or "No specific edit request entered."
    request_class = _classify_design_first_request(request)
    if request_class == "authority_refusal":
        return _design_first_refusal(
            selected,
            request,
            "Authority inversion is blocked. Josh remains highest authority, Guardian remains below Josh, and Engel/runtime remains below both.",
        )
    if request_class == "safety_refusal":
        return _design_first_refusal(
            selected,
            request,
            "The request asks for apply, direct editing, command execution, package install, autonomy, or another disabled behavior.",
        )
    if request_class in {"design_proposal", "verification_proposal"}:
        return _design_first_proposal(selected, request, request_class)

    if selected is None or selected.safety_status != "READ_ONLY":
        reason = selected.unavailable_reason if selected else "No readable file selected."
        return (
            "# Proposed Edit\n"
            "Status: unavailable\n"
            f"Request: {request}\n"
            f"Reason: {reason}\n\n"
            + REPORT_ONLY_STATEMENT
        )

    lines = selected.text.splitlines()
    imports, definitions, notes = _extract_python_shapes(lines) if selected.extension == ".py" else ([], [], [])
    target_hint = definitions[0] if definitions else (imports[0] if imports else "No obvious code symbol detected in preview.")
    output = [
        "# Proposed Edit",
        "Status: proposal text only; no file was changed.",
        f"Selected file: {selected.relative_path}",
        f"User request: {request}",
        "Safety: review manually before any future approval-gated apply flow.",
        "",
        "Candidate change plan:",
        "- Keep the change confined to the selected file unless Josh approves a broader scope.",
        f"- Start near: {target_hint}",
        "- Preserve existing safety gates, no provider calls, no background workers, and no trusted-memory writes.",
        "- Run the fixed local verifier after manual review if Josh approves verification.",
        "",
        "Patch sketch:",
        "```diff",
        "*** PROPOSAL ONLY - NOT APPLIED ***",
        f"*** Target: {selected.relative_path} ***",
        "@@",
        f"+ Review request: {request}",
        "+ Add the smallest code/doc change that satisfies the reviewed request.",
        "+ Keep generated text as untrusted proposal material until approved.",
        "```",
    ]
    if notes:
        output.extend(["", "Existing note markers to review first:"])
        output.extend([f"- {item}" for item in notes])
    output.extend(["", REPORT_ONLY_STATEMENT])
    return _trim_text("\n".join(output), MAX_SUMMARY_CHARS)


def normalize_product_type(product_type: str) -> str:
    value = re.sub(r"\s+", " ", str(product_type or "").strip()).lower()
    aliases = {
        "html website": "html/css/js website",
        "website": "html/css/js website",
        "python": "python script",
        "java": "java app",
        "utility": "utility/tool",
        "tool": "utility/tool",
        "engel": "engel module",
        "custom": "custom project",
    }
    value = aliases.get(value, value)
    allowed = {item.lower(): item for item in PRODUCT_TYPE_OPTIONS}
    if value not in allowed:
        return "custom project"
    return allowed[value].lower()


def safe_product_slug(product_name: str) -> str:
    raw = str(product_name or "").strip()
    raw = raw.replace("\\", "_").replace("/", "_").replace(":", "_")
    slug = re.sub(r"[^A-Za-z0-9_\- ]+", "", raw).strip().lower()
    slug = re.sub(r"[\s\-]+", "_", slug).strip("._")
    if not slug:
        slug = "new_product"
    return slug[:64]


def _product_title(slug: str) -> str:
    clean = str(slug or "new_product").replace("_", " ").replace("-", " ").strip()
    return clean.title() if clean else "New Product"


def _product_parent_status(parent: Path) -> ProjectValidation:
    if _is_url_or_unc(parent):
        return ProjectValidation(False, None, "BLOCKED", "Product parent cannot be UNC, URL, or remote.")
    resolved = _safe_resolve(parent)
    default_root = _safe_resolve(PRODUCTS_ROOT)
    if resolved is None or default_root is None:
        return ProjectValidation(False, None, "BLOCKED", "Product parent could not be resolved safely.")
    if _is_drive_or_filesystem_root(resolved):
        return ProjectValidation(False, resolved, "BLOCKED", "Whole-drive or filesystem roots are blocked for products.")
    if _is_users_sweep(resolved):
        return ProjectValidation(False, resolved, "BLOCKED", "User-profile sweep roots are blocked for products.")
    if _is_windows_system_area(resolved):
        return ProjectValidation(False, resolved, "BLOCKED", "Windows/system folders are blocked for products.")
    if _contains_sensitive_part(resolved):
        return ProjectValidation(False, resolved, "BLOCKED", "Sensitive credential/browser/profile product parent is blocked.")
    if resolved == default_root:
        return ProjectValidation(True, resolved, "ALLOWED", "Product parent is inside the default approved products root.")
    if _is_relative_to(resolved, default_root) and resolved.exists() and resolved.is_dir():
        return ProjectValidation(True, resolved, "ALLOWED", "Product parent is inside the default approved products root.")
    return ProjectValidation(False, resolved, "BLOCKED", "Product parent must stay under the approved products root.")


def build_new_product_path(product_name: str, parent_root: Path | None = None) -> Path:
    parent = parent_root or PRODUCTS_ROOT
    slug = safe_product_slug(product_name)
    validation = _product_parent_status(parent)
    if not validation.ok or validation.path is None:
        raise ValueError(validation.reason)
    return validation.path / slug


def validate_product_workspace(path_value: object, allow_missing: bool = False) -> ProjectValidation:
    if not path_value:
        return ProjectValidation(False, None, "BLOCKED", "No product workspace selected.")
    if _is_url_or_unc(path_value):
        return ProjectValidation(False, None, "BLOCKED", "Product workspace cannot be UNC, URL, or remote.")
    candidate = _safe_resolve(Path(str(path_value)))
    default_root = _safe_resolve(PRODUCTS_ROOT)
    if candidate is None:
        return ProjectValidation(False, None, "BLOCKED", "Product workspace could not be resolved safely.")
    if default_root is None:
        return ProjectValidation(False, candidate, "BLOCKED", "Approved products root could not be resolved safely.")
    if candidate == default_root:
        return ProjectValidation(False, candidate, "BLOCKED", "Select a bounded product folder inside the approved products root.")
    if not _is_relative_to(candidate, default_root):
        return ProjectValidation(False, candidate, "BLOCKED", "Product workspace must stay under the approved products root.")
    if not candidate.exists():
        if allow_missing:
            parent_status = _product_parent_status(candidate.parent)
            if parent_status.ok:
                return ProjectValidation(True, candidate, "PENDING_APPROVAL", "Product workspace will be created only after approval.")
        return ProjectValidation(False, candidate, "BLOCKED", "Product workspace does not exist.")
    return validate_project_root(candidate)


def validate_product_relative_path(relative_path: str) -> tuple[bool, str, str]:
    raw = str(relative_path or "").strip().replace("/", "\\")
    if not raw:
        return False, "", "Relative product file path is required."
    if len(raw) > MAX_PRODUCT_RELATIVE_PATH_CHARS:
        return False, "", "Relative product path is too long."
    if raw.startswith("\\") or Path(raw).is_absolute():
        return False, "", "Rooted and absolute product file paths are blocked."
    if _is_url_or_unc(raw) or ":" in raw:
        return False, "", "Absolute, URL, UNC, and drive paths are blocked."
    parts = [part for part in raw.split("\\") if part]
    if not parts or any(part in {".", ".."} for part in parts):
        return False, "", "Path traversal and empty path parts are blocked."
    if any(part.lower() in SKIP_TREE_DIRS for part in parts):
        return False, "", "Generated product files cannot target skipped dependency/build folders."
    candidate = Path(*parts)
    blocked, reason = is_path_sensitive_or_blocked(candidate)
    if blocked:
        return False, "", reason
    if not _is_supported_text_name(candidate) and candidate.suffix.lower() != ".java":
        return False, "", "Only bounded text/code product files are supported."
    return True, str(candidate).replace("/", "\\"), "Product relative path is safe."


def product_path_for_relative(product_root: Path, relative_path: str) -> tuple[bool, Path | None, str, str]:
    ok, normalized, reason = validate_product_relative_path(relative_path)
    if not ok:
        return False, None, "", reason
    root_validation = validate_product_workspace(product_root, allow_missing=True)
    if not root_validation.ok or root_validation.path is None:
        return False, None, normalized, root_validation.reason
    candidate = root_validation.path / normalized
    resolved = _safe_resolve(candidate)
    root = _safe_resolve(root_validation.path)
    if resolved is None or root is None:
        return False, None, normalized, "Product file path could not be resolved safely."
    if not _is_relative_to(resolved, root):
        return False, None, normalized, "Product file path escapes the workspace."
    blocked, blocked_reason = is_path_sensitive_or_blocked(resolved)
    if blocked:
        return False, None, normalized, blocked_reason
    return True, resolved, normalized, "Product file path is bounded."


def _safe_prompt_note(prompt: str) -> str:
    text = redact_sensitive_text(prompt)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "Starter product created from the selected product template."
    return _trim_text(text, 220)


def _generated_content_is_safe(content: str) -> tuple[bool, str]:
    lowered = str(content or "").lower()
    unsafe_tokens = (
        "os." + "system",
        "subprocess.",
        "shell=true",
        "__" + "import__",
        "requests.",
        "socket.",
        "http" + "://",
        "https" + "://",
        "start-process",
        "taskkill",
        "runtime.getruntime",
        "processbuilder",
        "java.net.socket",
        "fetch(",
        "xmlhttprequest",
        "document.cookie",
        "localstorage",
        "eval" + "(",
    )
    for token in unsafe_tokens:
        if token in lowered:
            return False, "Generated product content contains blocked token: " + token
    return True, "Generated product content passed local safety scan."


def _python_header(title: str) -> str:
    return "\n".join(
        [
            '"""' + title + ".",
            "",
            "Generated by ENGEL CODE COMPANION V2 product builder.",
            "Status: PRODUCT_PROPOSAL / NOT_APPLIED_UNTIL_APPROVED.",
            '"""',
            "",
            "# Authority: Josh > Guardian > Engel/runtime",
            "# Boundary: local product file; no provider/API/network behavior.",
            "",
        ]
    )


def _readme_content(title: str, product_type: str, prompt: str) -> str:
    return "\n".join(
        [
            "# " + title,
            "",
            "Created as an ENGEL CODE COMPANION V2 product proposal.",
            "",
            "Product type: " + product_type,
            "",
            "Prompt:",
            _safe_prompt_note(prompt),
            "",
            "Safety boundary:",
            "- Local files only.",
            "- Generated files are proposals until approved.",
            "- No provider/API/network behavior is included.",
            "- No package install ran.",
            "- Authority remains Josh > Guardian > Engel/runtime.",
            "",
        ]
    )


def _template_files_for_product(product_name: str, product_type: str, prompt: str) -> tuple[tuple[str, str], ...]:
    key = normalize_product_type(product_type)
    slug = safe_product_slug(product_name)
    title = _product_title(slug)
    note = _safe_prompt_note(prompt)
    readme = _readme_content(title, key, prompt)
    if key == "python script":
        return (
            (
                "main.py",
                _python_header(title)
                + "def main() -> None:\n"
                + f"    message = \"Hello from {title}.\"\n"
                + "    print(message)\n\n\n"
                + "if __name__ == \"__main__\":\n"
                + "    main()\n",
            ),
            ("README.md", readme),
            (
                "tests\\test_basic.py",
                _python_header(title + " basic test")
                + "from pathlib import Path\n\n\n"
                + "def test_main_file_exists() -> None:\n"
                + "    assert (Path(__file__).resolve().parents[1] / \"main.py\").exists()\n",
            ),
        )
    if key == "python app":
        return (
            (
                "app.py",
                _python_header(title)
                + "def build_message() -> str:\n"
                + f"    return \"{title} is ready.\"\n\n\n"
                + "def main() -> None:\n"
                + "    print(build_message())\n\n\n"
                + "if __name__ == \"__main__\":\n"
                + "    main()\n",
            ),
            (
                "requirements.txt",
                "# Proposal-only dependency manifest for " + title + "\n"
                "# No package install was run by ENGEL CODE COMPANION.\n",
            ),
            ("README.md", readme),
            (
                "tests\\test_app.py",
                _python_header(title + " app test")
                + "import app\n\n\n"
                + "def test_build_message() -> None:\n"
                + "    assert \"" + title + "\" in app.build_message()\n",
            ),
        )
    if key == "html/css/js website":
        return (
            (
                "index.html",
                "<!doctype html>\n"
                "<html lang=\"en\">\n"
                "<head>\n"
                "  <meta charset=\"utf-8\">\n"
                "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
                "  <title>" + title + "</title>\n"
                "  <link rel=\"stylesheet\" href=\"styles.css\">\n"
                "</head>\n"
                "<body>\n"
                "  <main class=\"shell\">\n"
                "    <h1>" + title + "</h1>\n"
                "    <p>" + note + "</p>\n"
                "    <button id=\"primaryAction\" type=\"button\">Check Status</button>\n"
                "    <p id=\"status\" aria-live=\"polite\">Local website starter ready.</p>\n"
                "  </main>\n"
                "  <script src=\"script.js\"></script>\n"
                "</body>\n"
                "</html>\n",
            ),
            (
                "styles.css",
                ":root {\n"
                "  color-scheme: light;\n"
                "  font-family: Segoe UI, Arial, sans-serif;\n"
                "}\n\n"
                "body {\n"
                "  margin: 0;\n"
                "  min-height: 100vh;\n"
                "  display: grid;\n"
                "  place-items: center;\n"
                "  background: #f6f8fb;\n"
                "  color: #17212b;\n"
                "}\n\n"
                ".shell {\n"
                "  width: min(720px, calc(100vw - 32px));\n"
                "}\n\n"
                "button {\n"
                "  min-height: 40px;\n"
                "  padding: 0 14px;\n"
                "}\n",
            ),
            (
                "script.js",
                "\"use strict\";\n\n"
                "const button = document.getElementById(\"primaryAction\");\n"
                "const status = document.getElementById(\"status\");\n\n"
                "button?.addEventListener(\"click\", () => {\n"
                "  status.textContent = \"Checked locally. No network call was made.\";\n"
                "});\n",
            ),
            ("README.md", readme),
        )
    if key == "java app":
        return (
            (
                "src\\HelloApp.java",
                "// " + title + "\n"
                "// Generated by ENGEL CODE COMPANION V2 product builder.\n"
                "// Status: PRODUCT_PROPOSAL / NOT_APPLIED_UNTIL_APPROVED.\n"
                "// Authority: Josh > Guardian > Engel/runtime.\n\n"
                "public class HelloApp {\n"
                "    public static void main(String[] args) {\n"
                "        System.out.println(\"Hello from " + title + ".\");\n"
                "    }\n"
                "}\n",
            ),
            ("README.md", readme),
        )
    if key == "engel module":
        module_name = re.sub(r"[^A-Za-z0-9_]", "_", slug)
        upper_name = module_name.upper()
        return (
            (
                module_name + ".py",
                _python_header(title + " Engel module")
                + "def module_status() -> str:\n"
                + "    return \"PROPOSAL_ONLY / NOT_CONNECTED_TO_RUNTIME\"\n",
            ),
            (
                "tools\\verify_" + module_name + ".py",
                _python_header(title + " verifier")
                + "def main() -> int:\n"
                + "    print(\"[PASS] " + module_name + " proposal verifier placeholder\")\n"
                + "    return 0\n\n\n"
                + "if __name__ == \"__main__\":\n"
                + "    raise SystemExit(main())\n",
            ),
            ("reports\\codex_bridge\\" + upper_name + ".md", "# " + upper_name + "\n\nProposal-only Engel module report.\n"),
            ("README.md", readme),
        )
    if key == "utility/tool":
        return (
            (
                "tool.py",
                _python_header(title + " utility")
                + "def describe() -> str:\n"
                + "    return \"Local utility starter.\"\n\n\n"
                + "def main() -> None:\n"
                + "    print(describe())\n\n\n"
                + "if __name__ == \"__main__\":\n"
                + "    main()\n",
            ),
            ("README.md", readme),
        )
    return (
        ("README.md", readme),
        ("src\\notes.md", "# Product Notes\n\n" + note + "\n"),
    )


def _proposal_from_files(
    product_root: Path,
    product_type: str,
    action: str,
    files: Iterable[tuple[str, str]],
    summary: str,
) -> ProductChangeProposal:
    validation = validate_product_workspace(product_root, allow_missing=True)
    if not validation.ok or validation.path is None:
        raise ValueError(validation.reason)
    proposals: list[ProductFileProposal] = []
    for relative_path, content in files:
        if len(proposals) >= MAX_PRODUCT_FILES_PER_CHANGE:
            raise ValueError("Product proposal exceeds the per-change file limit.")
        safe_content = _trim_text(str(content or ""), MAX_PRODUCT_FILE_CHARS)
        ok, reason = _generated_content_is_safe(safe_content)
        if not ok:
            raise ValueError(reason)
        path_ok, target, normalized, path_reason = product_path_for_relative(validation.path, relative_path)
        if not path_ok or target is None:
            raise ValueError(path_reason)
        proposals.append(
            ProductFileProposal(
                normalized,
                target,
                safe_content,
                "update" if target.exists() else "create",
                target.exists(),
            )
        )
    if not proposals:
        raise ValueError("Product proposal must include at least one file.")
    return ProductChangeProposal(
        validation.path,
        normalize_product_type(product_type),
        action,
        tuple(proposals),
        summary,
        False,
        "",
    )


def build_new_product_proposal(
    product_name: str,
    product_type: str,
    prompt: str = "",
    parent_root: Path | None = None,
) -> ProductChangeProposal:
    product_root = build_new_product_path(product_name, parent_root)
    if product_root.exists():
        try:
            has_children = any(product_root.iterdir())
        except OSError:
            has_children = True
        if has_children:
            raise ValueError("Product folder already exists; use Open Product or choose a new product name.")
    files = _template_files_for_product(product_name, product_type, prompt)
    return _proposal_from_files(
        product_root,
        product_type,
        "create_product",
        files,
        "Create New Product workspace under " + str(product_root),
    )


def build_add_file_proposal(
    product_root: Path,
    product_type: str,
    relative_path: str,
    prompt: str,
) -> ProductChangeProposal:
    ok, normalized, reason = validate_product_relative_path(relative_path)
    if not ok:
        raise ValueError(reason)
    title = _product_title(Path(normalized).stem)
    suffix = Path(normalized).suffix.lower()
    note = _safe_prompt_note(prompt)
    if suffix == ".py":
        content = _python_header(title) + "def main() -> None:\n    print(\"" + note.replace('"', "'") + "\")\n\n\nif __name__ == \"__main__\":\n    main()\n"
    elif suffix == ".md":
        content = "# " + title + "\n\n" + note + "\n\nGenerated as a proposal-first product file.\n"
    elif suffix == ".html":
        content = "<!doctype html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"utf-8\">\n  <title>" + title + "</title>\n</head>\n<body>\n  <main>\n    <h1>" + title + "</h1>\n    <p>" + note + "</p>\n  </main>\n</body>\n</html>\n"
    elif suffix == ".css":
        content = "body {\n  font-family: Segoe UI, Arial, sans-serif;\n  margin: 24px;\n}\n"
    elif suffix == ".js":
        content = "\"use strict\";\n\nconsole.log(\"" + title + " loaded locally.\");\n"
    elif suffix == ".java":
        content = "public class " + re.sub(r"[^A-Za-z0-9_]", "", Path(normalized).stem.title()) + " {\n    public static void main(String[] args) {\n        System.out.println(\"" + title + "\");\n    }\n}\n"
    else:
        content = note + "\n"
    return _proposal_from_files(product_root, product_type, "add_file_proposal", ((normalized, content),), "Add File Proposal for " + normalized)


def build_patch_proposal(
    selected: SelectedFile | None,
    prompt: str,
    product_root: Path | None = None,
) -> ProductChangeProposal:
    if selected is None or selected.safety_status != "READ_ONLY" or selected.path is None:
        raise ValueError("Select a readable product file before proposing a patch.")
    root = _safe_resolve(product_root or selected.path.parent)
    if root is None:
        raise ValueError("Selected file path could not be resolved.")
    selected_path = _safe_resolve(selected.path)
    if selected_path is None:
        raise ValueError("Selected file path could not be resolved.")
    try:
        relative_name = str(selected_path.relative_to(root)).replace("/", "\\")
    except ValueError:
        relative_name = selected_path.name
    marker = _safe_prompt_note(prompt)
    suffix = selected.extension.lower()
    if suffix in {".py", ".js", ".css"}:
        addition = "\n# ENGEL CODE COMPANION PATCH PROPOSAL: " + marker + "\n" if suffix == ".py" else "\n/* ENGEL CODE COMPANION PATCH PROPOSAL: " + marker + " */\n"
    elif suffix == ".html":
        addition = "\n<!-- ENGEL CODE COMPANION PATCH PROPOSAL: " + marker + " -->\n"
    elif suffix == ".java":
        addition = "\n// ENGEL CODE COMPANION PATCH PROPOSAL: " + marker + "\n"
    else:
        addition = "\n\nENGEL CODE COMPANION PATCH PROPOSAL: " + marker + "\n"
    proposed = selected.text.rstrip() + addition
    return _proposal_from_files(
        root,
        "custom project",
        "patch_proposal",
        ((relative_name, proposed),),
        "Generate patch/diff proposal for " + selected.relative_path,
    )


def approve_product_change(proposal: ProductChangeProposal | None, approval_token: str) -> ProductChangeProposal:
    if proposal is None:
        raise ValueError("No pending product change proposal exists.")
    if str(approval_token or "").strip() != CHANGE_APPROVAL_TOKEN:
        raise PermissionError("Exact APPROVE_CHANGE token is required before product files can be written.")
    return replace(proposal, approved=True, approval_token=CHANGE_APPROVAL_TOKEN)


def render_product_proposal(proposal: ProductChangeProposal | None) -> str:
    if proposal is None:
        return "# Product Proposal\nStatus: unavailable\nReason: no pending product proposal."
    lines = [
        "# Product Proposal",
        "Status: PROPOSAL_ONLY / NOT_APPLIED",
        "Product type: " + proposal.product_type,
        "Product root: " + str(proposal.product_root),
        "Action: " + proposal.action,
        "Approved: " + str(proposal.approved),
        "Summary: " + proposal.summary,
        "",
        PRODUCT_BUILDER_BOUNDARY_STATEMENT,
        "",
        "Files:",
    ]
    for item in proposal.files:
        lines.extend(
            [
                "- " + item.relative_path + " | " + item.action + " | backup_required=" + str(item.backup_required),
                "```text",
                _trim_text(item.proposed_content, 4000),
                "```",
            ]
        )
    lines.append(REPORT_ONLY_STATEMENT)
    return _trim_text("\n".join(lines), MAX_SUMMARY_CHARS)


def render_product_diff(proposal: ProductChangeProposal | None) -> str:
    if proposal is None:
        return "# Product Diff\nStatus: unavailable\nReason: no pending product proposal."
    lines = [
        "# Product Diff",
        "Status: PREVIEW_ONLY / NOT_APPLIED",
        "Product root: " + str(proposal.product_root),
        "Action: " + proposal.action,
        "",
    ]
    for item in proposal.files:
        if item.path.exists() and item.path.is_file():
            try:
                before = item.path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                before = []
        else:
            before = []
        after = item.proposed_content.splitlines()
        diff = difflib.unified_diff(
            before,
            after,
            fromfile=item.relative_path + " (current)",
            tofile=item.relative_path + " (proposed)",
            lineterm="",
        )
        rendered = list(diff)
        lines.extend(["```diff", *(rendered or ["# New file has no existing content."]), "```", ""])
    lines.append(PRODUCT_BUILDER_BOUNDARY_STATEMENT)
    return _trim_text("\n".join(lines), MAX_SUMMARY_CHARS)


def _product_receipt_path(product_root: Path, prefix: str) -> Path:
    validation = validate_product_workspace(product_root, allow_missing=True)
    if not validation.ok or validation.path is None:
        raise ValueError(validation.reason)
    root = validation.path.resolve()
    report_dir = root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = filename_stamp()
    for index in range(0, 100):
        suffix = "" if index == 0 else "_" + str(index).zfill(2)
        safe_name = prefix + "_" + stamp + suffix + ".md"
        candidate = (report_dir / safe_name).resolve()
        if not _is_relative_to(candidate, root):
            raise ValueError("Product receipt/report path escaped the product workspace.")
        if not candidate.exists():
            return candidate
    raise FileExistsError("Could not create a unique product receipt/report path.")


def _backup_existing_product_file(product_root: Path, file_path: Path) -> Path:
    validation = validate_product_workspace(product_root)
    if not validation.ok or validation.path is None:
        raise ValueError(validation.reason)
    root = validation.path.resolve()
    target = file_path.resolve()
    relative = target.relative_to(root)
    products_root = PRODUCTS_ROOT.resolve()
    backup_root = BACKUPS_ROOT.resolve()
    product_label = safe_product_slug(str(root.relative_to(products_root)).replace("\\", "_"))
    stamp = filename_stamp()
    for index in range(0, 100):
        suffix = "" if index == 0 else "_" + str(index).zfill(2)
        backup = (backup_root / "code_companion" / product_label / (stamp + suffix) / relative).resolve()
        if not _is_relative_to(backup, backup_root):
            raise ValueError("Backup path escaped the app backups root.")
        if not backup.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(target.read_bytes())
            return backup
    raise FileExistsError("Could not create a unique product backup path.")


def _write_product_action_receipt(proposal: ProductChangeProposal, result_lines: list[str]) -> Path:
    receipt = _product_receipt_path(proposal.product_root, PRODUCT_RECEIPT_PREFIX)
    content = "\n".join(
        [
            "# ENGEL CODE COMPANION Product Action Receipt",
            "",
            "Timestamp: " + now_text(),
            "Product root: " + str(proposal.product_root),
            "Product type: " + proposal.product_type,
            "Action: " + proposal.action,
            "Approval token supplied: " + str(proposal.approval_token == CHANGE_APPROVAL_TOKEN),
            "",
            "Result:",
            *result_lines,
            "",
            PRODUCT_BUILDER_BOUNDARY_STATEMENT,
        ]
    )
    receipt.write_text(content, encoding="utf-8")
    return receipt


def apply_product_change(proposal: ProductChangeProposal | None) -> ProductApplyResult:
    if proposal is None:
        return ProductApplyResult(False, "BLOCKED", "No pending product change proposal exists.", (), (), None)
    if not proposal.approved or proposal.approval_token != CHANGE_APPROVAL_TOKEN:
        return ProductApplyResult(False, "BLOCKED", "Apply blocked: exact APPROVE_CHANGE approval is required.", (), (), None)
    validation = validate_product_workspace(proposal.product_root, allow_missing=True)
    if not validation.ok or validation.path is None:
        return ProductApplyResult(False, "BLOCKED", validation.reason, (), (), None)
    product_root = validation.path
    product_root.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    backups: list[Path] = []
    result_lines: list[str] = []
    try:
        for item in proposal.files:
            ok, target, normalized, reason = product_path_for_relative(product_root, item.relative_path)
            if not ok or target is None:
                raise ValueError(reason)
            if target.exists() and not target.is_file():
                raise ValueError("Target exists but is not a file: " + normalized)
            if target.exists():
                backups.append(_backup_existing_product_file(product_root, target))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item.proposed_content, encoding="utf-8")
            written.append(target)
            result_lines.append("- Wrote: " + str(target))
        receipt = _write_product_action_receipt(proposal, result_lines + ["- Backups: " + str(len(backups))])
    except (OSError, ValueError) as exc:
        return ProductApplyResult(False, "ERROR", str(exc), tuple(written), tuple(backups), None)
    return ProductApplyResult(True, "APPLIED", "Approved product change applied with backups before overwrites.", tuple(written), tuple(backups), receipt)


def _html_has_basic_structure(text: str) -> bool:
    lowered = text.lower()
    return "<!doctype html" in lowered and "<html" in lowered and "<head" in lowered and "<body" in lowered


def _python_product_files(project_root: Path) -> list[Path]:
    result = build_project_tree(project_root)
    files: list[Path] = []
    for entry in result.entries:
        if entry.kind == "file" and entry.safety_status == "READ_ONLY" and entry.path.suffix.lower() == ".py":
            files.append(entry.path)
        if len(files) >= 20:
            break
    return files


def verify_html_product_structure(project_root: Path) -> VerificationResult:
    result = build_project_tree(project_root)
    html_files = [
        entry.path for entry in result.entries
        if entry.kind == "file" and entry.safety_status == "READ_ONLY" and entry.path.name.lower() == "index.html"
    ]
    if not html_files:
        return VerificationResult(True, True, "basic HTML structure verifier", 1, "index.html was not found.", "FAIL")
    selected = read_file_preview(project_root, html_files[0])
    if selected.safety_status != "READ_ONLY" or not _html_has_basic_structure(selected.text):
        return VerificationResult(True, True, "basic HTML structure verifier", 1, "index.html basic structure check failed.", "FAIL")
    return VerificationResult(True, True, "basic HTML structure verifier", 0, "HTML_BASIC_STRUCTURE_OK", "PASS")


def run_product_verification(project_root: Path | None, product_type: str, approved: bool) -> VerificationResult:
    key = normalize_product_type(product_type)
    allowlist = PRODUCT_VERIFICATION_ALLOWLIST.get(key, PRODUCT_VERIFICATION_ALLOWLIST["custom project"])
    command_text = " && ".join(allowlist)
    if not approved:
        return VerificationResult(True, False, command_text, None, "Verification blocked: approval checkbox not set.", "BLOCKED")
    if project_root is None:
        return run_fixed_verification(True)
    validation = validate_product_workspace(project_root)
    if not validation.ok or validation.path is None:
        return VerificationResult(True, True, command_text, 1, validation.reason, "FAIL")

    output_parts: list[str] = []
    final_code = 0
    if key in {"python app", "python script", "utility/tool"}:
        py_files = _python_product_files(validation.path)
        if not py_files:
            output_parts.append("No Python files found in bounded product tree.")
        for py_file in py_files:
            command = (sys.executable, "-m", "py_compile", str(py_file))
            completed = subprocess.run(
                list(command),
                cwd=str(validation.path),
                capture_output=True,
                text=True,
                timeout=VERIFICATION_TIMEOUT_SECONDS,
                shell=False,
            )
            output_parts.append("$ " + _format_command(command))
            if completed.stdout:
                output_parts.append(completed.stdout.strip())
            if completed.stderr:
                output_parts.append(completed.stderr.strip())
            output_parts.append("return_code=" + str(completed.returncode))
            final_code = completed.returncode
            if final_code != 0:
                break
    elif key == "html/css/js website":
        html_result = verify_html_product_structure(validation.path)
        final_code = html_result.return_code or 0
        output_parts.append(html_result.output)
    elif key == "java app":
        output_parts.append("JAVA_COMPILE_NOT_RUN: javac is proposal-only by default and was not invoked.")
    elif key == "engel module":
        for label, command in (
            ("companion verifier", (sys.executable, str(APP_ROOT / "tools" / "verify_engel_code_companion.py"))),
            ("codex verify", ("powershell", "-ExecutionPolicy", "Bypass", "-File", str(APP_ROOT / "scripts" / "codex_verify.ps1"))),
        ):
            completed = subprocess.run(
                list(command),
                cwd=str(APP_ROOT),
                capture_output=True,
                text=True,
                timeout=VERIFICATION_TIMEOUT_SECONDS,
                shell=False,
            )
            output_parts.append("$ " + _format_command(command))
            if completed.stdout:
                output_parts.append(completed.stdout.strip())
            if completed.stderr:
                output_parts.append(completed.stderr.strip())
            output_parts.append(label + " return_code=" + str(completed.returncode))
            final_code = completed.returncode
            if final_code != 0:
                break
    else:
        tree = build_project_tree(validation.path)
        final_code = 0 if tree.status == "ALLOWED" else 1
        output_parts.append("Bounded product tree check: " + tree.message)

    if final_code == 0 and key != "engel module":
        verifier_command = (sys.executable, str(APP_ROOT / "tools" / "verify_engel_code_companion.py"))
        completed = subprocess.run(
            list(verifier_command),
            cwd=str(APP_ROOT),
            capture_output=True,
            text=True,
            timeout=VERIFICATION_TIMEOUT_SECONDS,
            shell=False,
        )
        output_parts.append("$ " + _format_command(verifier_command))
        if completed.stdout:
            output_parts.append(completed.stdout.strip())
        if completed.stderr:
            output_parts.append(completed.stderr.strip())
        output_parts.append("return_code=" + str(completed.returncode))
        final_code = completed.returncode

    return VerificationResult(True, True, command_text, final_code, "\n".join(output_parts), "PASS" if final_code == 0 else "FAIL")


def save_product_build_report(
    project_root: Path | None,
    product_type: str,
    last_action: str,
    last_output: str,
    verification: VerificationResult | None = None,
) -> Path:
    if project_root is None:
        raise ValueError("Select or create a product workspace before saving a product report.")
    validation = validate_product_workspace(project_root)
    if not validation.ok or validation.path is None:
        raise ValueError(validation.reason)
    verification = verification or VerificationResult(False, False, "none", None, "not requested", "NOT_REQUESTED")
    tree = build_project_tree(validation.path)
    report = _product_receipt_path(validation.path, PRODUCT_REPORT_PREFIX)
    content = "\n".join(
        [
            "# ENGEL CODE COMPANION Product Build Report",
            "",
            "Timestamp: " + now_text(),
            "Product root: " + str(validation.path),
            "Product type: " + normalize_product_type(product_type),
            "Last action: " + str(last_action or "none"),
            "Tree status: " + tree.status + " - " + tree.message,
            "Verification status: " + verification.status,
            "Verification command: " + verification.command,
            "",
            "Last output:",
            "```text",
            _trim_text(redact_sensitive_text(last_output), 8000),
            "```",
            "",
            "Verification output:",
            "```text",
            _trim_text(redact_sensitive_text(verification.output), 4000),
            "```",
            "",
            PRODUCT_BUILDER_BOUNDARY_STATEMENT,
        ]
    )
    report.write_text(content, encoding="utf-8")
    return report


def _profile_type_id(product_type: str) -> str:
    return PRODUCT_TYPE_PROFILE_IDS.get(normalize_product_type(product_type), "custom_project")


def _product_type_from_profile_id(value: str) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_").replace("/", "_")
    if text in PROFILE_ID_PRODUCT_TYPES:
        return PROFILE_ID_PRODUCT_TYPES[text]
    return normalize_product_type(str(value or "").replace("_", " ").replace("-", " "))


def _product_profile_path(product_root: Path) -> Path:
    validation = validate_product_workspace(product_root)
    if not validation.ok or validation.path is None:
        raise ValueError(validation.reason)
    profile_path = (validation.path / PRODUCT_PROFILE_FILENAME).resolve()
    if profile_path.parent != validation.path.resolve():
        raise ValueError("Product profile path escaped product root.")
    return profile_path


def _product_local_dir(product_root: Path, dirname: str) -> Path:
    validation = validate_product_workspace(product_root)
    if not validation.ok or validation.path is None:
        raise ValueError(validation.reason)
    candidate = (validation.path / dirname).resolve()
    if candidate.parent != validation.path.resolve():
        raise ValueError("Product local directory escaped product root.")
    return candidate


def _product_entrypoint(product_root: Path, product_type: str) -> str:
    key = normalize_product_type(product_type)
    if key == "python app":
        return "app.py"
    if key == "python script":
        return "main.py"
    if key == "html/css/js website":
        return "index.html"
    if key == "java app":
        return "src\\HelloApp.java"
    if key == "utility/tool":
        return "tool.py"
    if key == "engel module":
        preferred = safe_product_slug(product_root.name) + ".py"
        if (product_root / preferred).exists():
            return preferred
        tree = build_project_tree(product_root)
        for entry in tree.entries:
            if entry.kind == "file" and entry.relative_path.count("\\") == 0 and entry.path.suffix.lower() == ".py":
                return entry.relative_path
        return preferred
    return "README.md"


def _fixed_profile_command(product_type: str, entrypoint: str, kind: str) -> list[str]:
    key = normalize_product_type(product_type)
    if kind == "verify":
        if key in {"python app", "python script", "utility/tool"}:
            return ["python", "-m", "py_compile", entrypoint]
        if key == "engel module":
            return ["python", "-m", "py_compile", entrypoint]
        return []
    if kind == "launch" and key in {"python app", "python script", "utility/tool"}:
        return ["python", entrypoint]
    return []


def build_product_profile(product_root: Path, product_type: str) -> dict[str, Any]:
    validation = validate_product_workspace(product_root)
    if not validation.ok or validation.path is None:
        raise ValueError(validation.reason)
    key = normalize_product_type(product_type)
    entrypoint = _product_entrypoint(validation.path, key)
    launch_command = _fixed_profile_command(key, entrypoint, "launch")
    verify_command = _fixed_profile_command(key, entrypoint, "verify")
    launch_profiles: list[dict[str, Any]] = []
    if launch_command:
        launch_profiles.append(
            {
                "name": "Run " + key.title(),
                "kind": "launch",
                "command": launch_command,
                "requires_approval": True,
            }
        )
    else:
        launch_profiles.append(
            {
                "name": "Launch Instructions Only",
                "kind": "launch",
                "command": [],
                "requires_approval": True,
                "disabled": True,
                "instructions": "Launch is instructions-only or disabled by default for this product type.",
            }
        )

    verification_profiles: list[dict[str, Any]] = []
    if verify_command:
        verification_profiles.append(
            {
                "name": "Compile " + key.title(),
                "kind": "verify",
                "command": verify_command,
                "requires_approval": True,
            }
        )
    elif key == "html/css/js website":
        verification_profiles.append(
            {
                "name": "Basic HTML Structure",
                "kind": "verify",
                "command": [],
                "mode": "html_basic_structure",
                "requires_approval": True,
            }
        )
    elif key == "java app":
        verification_profiles.append(
            {
                "name": "Java Compile Proposal Only",
                "kind": "verify",
                "command": [],
                "mode": "JAVA_COMPILE_NOT_RUN",
                "requires_approval": True,
            }
        )
    else:
        verification_profiles.append(
            {
                "name": "Bounded Structure Check",
                "kind": "verify",
                "command": [],
                "mode": "bounded_structure",
                "requires_approval": True,
            }
        )

    package_profiles = [
        {
            "name": "Create Source Zip",
            "kind": "package",
            "mode": "source_zip",
            "output_dir": PRODUCT_DIST_DIRNAME,
            "requires_approval": True,
        }
    ]
    return {
        "schema": PRODUCT_PROFILE_SCHEMA,
        "product_name": validation.path.name,
        "product_type": _profile_type_id(key),
        "entrypoint": entrypoint,
        "allowed_launch_profiles": launch_profiles,
        "allowed_verification_profiles": verification_profiles,
        "allowed_package_profiles": package_profiles,
        "authority": "Josh > Guardian > Engel/runtime",
        "safety": "APPROVAL_GATED / PRODUCT_ONLY / NOT_RUNTIME",
    }


def _backup_product_local_file(product_root: Path, path: Path) -> Path | None:
    validation = validate_product_workspace(product_root)
    if not validation.ok or validation.path is None:
        raise ValueError(validation.reason)
    target = path.resolve()
    root = validation.path.resolve()
    if not target.exists():
        return None
    if not _is_relative_to(target, root):
        raise ValueError("Product backup target escaped product root.")
    backup_root = _product_local_dir(root, PRODUCT_LOCAL_BACKUP_DIRNAME)
    relative = target.relative_to(root)
    backup = (backup_root / filename_stamp() / relative).resolve()
    if not _is_relative_to(backup, backup_root.resolve()):
        raise ValueError("Product backup path escaped local backup root.")
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(target.read_bytes())
    return backup


def write_product_profile(product_root: Path, product_type: str) -> ProductProfileResult:
    try:
        profile_path = _product_profile_path(product_root)
        profile = build_product_profile(product_root, product_type)
        backup = _backup_product_local_file(product_root, profile_path)
        profile_path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:
        return ProductProfileResult(False, "PROFILE_WRITE_BLOCKED", str(exc))
    details = ["profile_path=" + str(profile_path)]
    if backup is not None:
        details.append("backup=" + str(backup))
    return ProductProfileResult(True, "PROFILE_WRITE_OK", "Product profile written under product root.", profile_path, profile, tuple(details))


def load_product_profile(product_root: Path) -> ProductProfileResult:
    try:
        profile_path = _product_profile_path(product_root)
        if not profile_path.exists() or not profile_path.is_file():
            return ProductProfileResult(False, "PROFILE_MISSING", "Product profile does not exist.", profile_path)
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return ProductProfileResult(False, "PROFILE_INVALID", "Product profile JSON root must be an object.", profile_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return ProductProfileResult(False, "PROFILE_LOAD_BLOCKED", str(exc))
    return ProductProfileResult(True, "PROFILE_LOADED", "Product profile loaded.", profile_path, data)


def _profile_list(profile: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = profile.get(key, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _profile_by_name(profile: dict[str, Any], key: str, name: str | None = None) -> dict[str, Any] | None:
    profiles = _profile_list(profile, key)
    if not profiles:
        return None
    requested = str(name or "").strip()
    if requested:
        for item in profiles:
            if str(item.get("name", "")).strip() == requested:
                return item
    return profiles[0]


def _command_text(command: Iterable[str]) -> str:
    return " ".join(str(part) for part in command)


def _entrypoint_is_safe(product_root: Path, entrypoint: str) -> tuple[bool, str]:
    ok, target, _normalized, reason = product_path_for_relative(product_root, entrypoint)
    if not ok or target is None:
        return False, reason
    if not target.exists() or not target.is_file():
        return False, "Entrypoint does not exist: " + entrypoint
    return True, "Entrypoint is bounded and present."


def _profile_command_allowed(product_root: Path, product_type: str, entrypoint: str, command: object, kind: str) -> tuple[bool, tuple[str, ...], str]:
    if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
        return False, (), "Profile command must be a list of strings."
    expected = tuple(_fixed_profile_command(product_type, entrypoint, kind))
    actual = tuple(command)
    if not expected and not actual:
        return True, actual, "Instructions-only or proposal-only profile has no command."
    if actual != expected:
        return False, actual, "Profile command does not match fixed allowlist template."
    ok, reason = _entrypoint_is_safe(product_root, entrypoint)
    if not ok:
        return False, actual, reason
    return True, actual, "Profile command matches fixed allowlist template."


def _launch_content_is_persistent(product_root: Path, entrypoint: str) -> bool:
    ok, target, _normalized, _reason = product_path_for_relative(product_root, entrypoint)
    if not ok or target is None or not target.exists() or not target.is_file():
        return False
    try:
        text = target.read_text(encoding="utf-8", errors="replace")[:16000]
    except OSError:
        return True
    lowered = text.lower()
    return any(token.lower() in lowered for token in PERSISTENT_LAUNCH_TOKENS)


def validate_product_profile(product_root: Path) -> ProductProfileResult:
    loaded = load_product_profile(product_root)
    if not loaded.ok or loaded.profile is None:
        return loaded
    validation = validate_product_workspace(product_root)
    if not validation.ok or validation.path is None:
        return ProductProfileResult(False, "PROFILE_INVALID", validation.reason, loaded.profile_path, loaded.profile)
    profile = loaded.profile
    details: list[str] = []
    if profile.get("schema") != PRODUCT_PROFILE_SCHEMA:
        return ProductProfileResult(False, "PROFILE_INVALID", "Unsupported product profile schema.", loaded.profile_path, profile)
    product_type = _product_type_from_profile_id(str(profile.get("product_type", "")))
    entrypoint = str(profile.get("entrypoint", "")).replace("/", "\\")
    if product_type not in PRODUCT_TYPE_PROFILE_IDS:
        return ProductProfileResult(False, "PROFILE_INVALID", "Unsupported product type.", loaded.profile_path, profile)
    if not entrypoint:
        return ProductProfileResult(False, "PROFILE_INVALID", "Profile entrypoint is required.", loaded.profile_path, profile)
    entrypoint_ok, entrypoint_reason = _entrypoint_is_safe(validation.path, entrypoint)
    if product_type not in {"custom project"} and not entrypoint_ok:
        return ProductProfileResult(False, "PROFILE_INVALID", entrypoint_reason, loaded.profile_path, profile)
    details.append("entrypoint=" + entrypoint)

    for launch_profile in _profile_list(profile, "allowed_launch_profiles"):
        if launch_profile.get("kind") != "launch":
            return ProductProfileResult(False, "PROFILE_INVALID", "Launch profile kind mismatch.", loaded.profile_path, profile)
        if launch_profile.get("requires_approval") is not True:
            return ProductProfileResult(False, "PROFILE_INVALID", "Launch profile must require approval.", loaded.profile_path, profile)
        ok, command, reason = _profile_command_allowed(validation.path, product_type, entrypoint, launch_profile.get("command", []), "launch")
        if not ok:
            return ProductProfileResult(False, "PROFILE_INVALID", reason, loaded.profile_path, profile)
        details.append("launch=" + (_command_text(command) if command else "instructions-only"))

    for package_profile in _profile_list(profile, "allowed_package_profiles"):
        if package_profile.get("kind") != "package":
            return ProductProfileResult(False, "PROFILE_INVALID", "Package profile kind mismatch.", loaded.profile_path, profile)
        if package_profile.get("requires_approval") is not True:
            return ProductProfileResult(False, "PROFILE_INVALID", "Package profile must require approval.", loaded.profile_path, profile)
        if package_profile.get("mode") != "source_zip":
            return ProductProfileResult(False, "PROFILE_INVALID", "Only source_zip package mode is supported.", loaded.profile_path, profile)
        if str(package_profile.get("output_dir", "")) != PRODUCT_DIST_DIRNAME:
            return ProductProfileResult(False, "PROFILE_INVALID", "Package output_dir must be dist.", loaded.profile_path, profile)
        details.append("package=source_zip")

    return ProductProfileResult(True, "PROFILE_VALID", "Product profile is bounded and approval-gated.", loaded.profile_path, profile, tuple(details))


def preview_launch_command(product_root: Path, profile_name: str | None = None) -> LaunchPreviewResult:
    validation = validate_product_profile(product_root)
    if not validation.ok or validation.profile is None:
        return LaunchPreviewResult(False, validation.status, validation.message)
    profile = validation.profile
    launch_profile = _profile_by_name(profile, "allowed_launch_profiles", profile_name)
    if launch_profile is None:
        return LaunchPreviewResult(False, "LAUNCH_PROFILE_MISSING", "No launch profile is defined.")
    name = str(launch_profile.get("name", "Launch Profile"))
    if launch_profile.get("disabled") is True:
        return LaunchPreviewResult(False, "LAUNCH_DISABLED", str(launch_profile.get("instructions", "Launch is disabled.")), name)
    product_type = _product_type_from_profile_id(str(profile.get("product_type", "")))
    entrypoint = str(profile.get("entrypoint", "")).replace("/", "\\")
    ok, command, reason = _profile_command_allowed(product_root, product_type, entrypoint, launch_profile.get("command", []), "launch")
    if not ok:
        return LaunchPreviewResult(False, "LAUNCH_COMMAND_BLOCKED", reason, name, command, _command_text(command))
    if _launch_content_is_persistent(product_root, entrypoint):
        return LaunchPreviewResult(False, "PERSISTENT_SERVER_BLOCKED", "Persistent launch patterns are blocked by default.", name, command, _command_text(command))
    return LaunchPreviewResult(True, "LAUNCH_PREVIEW_OK", "Fixed launch command is ready for approval.", name, command, _command_text(command))


def _receipt_path(product_root: Path, prefix: str) -> Path:
    receipt_root = _product_local_dir(product_root, PRODUCT_LOCAL_RECEIPT_DIRNAME)
    receipt_root.mkdir(parents=True, exist_ok=True)
    for index in range(0, 100):
        suffix = "" if index == 0 else "_" + str(index).zfill(2)
        candidate = (receipt_root / (prefix + "_" + filename_stamp() + suffix + ".md")).resolve()
        if not _is_relative_to(candidate, receipt_root.resolve()):
            raise ValueError("Receipt path escaped product receipt root.")
        if not candidate.exists():
            return candidate
    raise FileExistsError("Could not create a unique launch/package receipt.")


def save_launch_receipt(
    product_root: Path,
    status: str,
    command_text: str,
    stdout: str,
    stderr: str,
    return_code: int | None,
    message: str,
) -> Path:
    receipt = _receipt_path(product_root, "launch_receipt")
    content = "\n".join(
        [
            "# ENGEL CODE COMPANION Launch Receipt",
            "",
            "Timestamp: " + now_text(),
            "Authority: Josh > Guardian > Engel/runtime",
            "Product root: " + str(product_root),
            "Status: " + status,
            "Command: " + command_text,
            "Return code: " + str(return_code),
            "Message: " + message,
            "",
            "Stdout:",
            "```text",
            _trim_text(redact_sensitive_text(stdout), 6000),
            "```",
            "",
            "Stderr:",
            "```text",
            _trim_text(redact_sensitive_text(stderr), 6000),
            "```",
            "",
            "Boundary: APPROVE_LAUNCH required; fixed allowlisted command only; no arbitrary command text.",
        ]
    )
    receipt.write_text(content, encoding="utf-8")
    return receipt


def run_approved_launch(product_root: Path, profile_name: str | None, approval_token: str) -> LaunchRunResult:
    if str(approval_token or "").strip() != LAUNCH_APPROVAL_TOKEN:
        return LaunchRunResult(False, "LAUNCH_BLOCKED", "Exact APPROVE_LAUNCH token is required.")
    preview = preview_launch_command(product_root, profile_name)
    if not preview.ok:
        return LaunchRunResult(False, preview.status, preview.message, preview.command_text)
    validation = validate_product_workspace(product_root)
    if not validation.ok or validation.path is None:
        return LaunchRunResult(False, "LAUNCH_BLOCKED", validation.reason, preview.command_text)
    try:
        completed = subprocess.run(
            list(preview.command),
            cwd=str(validation.path),
            capture_output=True,
            text=True,
            timeout=LAUNCH_TIMEOUT_SECONDS,
            shell=False,
        )
        receipt = save_launch_receipt(
            validation.path,
            "LAUNCH_RAN",
            preview.command_text,
            completed.stdout or "",
            completed.stderr or "",
            completed.returncode,
            "Launch command completed within timeout.",
        )
        return LaunchRunResult(
            completed.returncode == 0,
            "LAUNCH_OK" if completed.returncode == 0 else "LAUNCH_FAILED",
            "Launch command completed within timeout.",
            preview.command_text,
            completed.returncode,
            completed.stdout or "",
            completed.stderr or "",
            receipt,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        receipt = save_launch_receipt(
            validation.path,
            "LAUNCH_TIMEOUT",
            preview.command_text,
            stdout,
            stderr,
            None,
            "Launch command timed out; persistent servers are blocked by default.",
        )
        return LaunchRunResult(False, "LAUNCH_TIMEOUT", "Launch command timed out.", preview.command_text, None, stdout, stderr, receipt)
    except OSError as exc:
        receipt = save_launch_receipt(validation.path, "LAUNCH_FAILED", preview.command_text, "", str(exc), None, str(exc))
        return LaunchRunResult(False, "LAUNCH_FAILED", str(exc), preview.command_text, None, "", str(exc), receipt)


def _package_exclusion_reason(relative: Path) -> str:
    parts = [part.lower() for part in relative.parts]
    if any(part in PACKAGE_EXCLUDED_DIRS for part in parts[:-1]):
        return "excluded directory"
    name = relative.name.lower()
    if name in SENSITIVE_FILE_NAMES:
        return "sensitive filename"
    if relative.suffix.lower() in PACKAGE_EXCLUDED_SUFFIXES:
        return "excluded suffix"
    if SENSITIVE_RE.search(name):
        return "sensitive-looking filename"
    return ""


def _package_source_files(product_root: Path) -> tuple[tuple[Path, str], tuple[str, ...]]:
    validation = validate_product_workspace(product_root)
    if not validation.ok or validation.path is None:
        raise ValueError(validation.reason)
    root = validation.path.resolve()
    queue: list[Path] = [root]
    index = 0
    files: list[tuple[Path, str]] = []
    excluded: list[str] = []
    while index < len(queue):
        folder = queue[index]
        index += 1
        for child in _iter_child_entries(folder):
            resolved = child.resolve()
            if not _is_relative_to(resolved, root):
                excluded.append(str(child) + " | outside product root")
                continue
            relative = resolved.relative_to(root)
            reason = _package_exclusion_reason(relative)
            if child.is_dir():
                if reason:
                    excluded.append(str(relative).replace("/", "\\") + " | " + reason)
                    continue
                queue.append(child)
                continue
            if not child.is_file():
                excluded.append(str(relative).replace("/", "\\") + " | unsupported filesystem entry")
                continue
            if reason:
                excluded.append(str(relative).replace("/", "\\") + " | " + reason)
                continue
            try:
                size = child.stat().st_size
            except OSError:
                excluded.append(str(relative).replace("/", "\\") + " | stat failed")
                continue
            if size > MAX_PACKAGE_FILE_BYTES:
                excluded.append(str(relative).replace("/", "\\") + " | file too large")
                continue
            blocked, blocked_reason = is_path_sensitive_or_blocked(child)
            if blocked:
                excluded.append(str(relative).replace("/", "\\") + " | " + blocked_reason)
                continue
            files.append((child, str(relative).replace("\\", "/")))
            if len(files) >= MAX_PACKAGE_FILES:
                excluded.append("package file limit reached")
                return tuple(files), tuple(excluded)
    return tuple(files), tuple(excluded)


def preview_package(product_root: Path, profile_name: str | None = None) -> PackagePreviewResult:
    validation = validate_product_profile(product_root)
    if not validation.ok or validation.profile is None:
        return PackagePreviewResult(False, validation.status, validation.message)
    package_profile = _profile_by_name(validation.profile, "allowed_package_profiles", profile_name)
    if package_profile is None:
        return PackagePreviewResult(False, "PACKAGE_PROFILE_MISSING", "No package profile is defined.")
    if package_profile.get("mode") != "source_zip":
        return PackagePreviewResult(False, "PACKAGE_BLOCKED", "Only source_zip package mode is supported.")
    try:
        product_validation = validate_product_workspace(product_root)
        if not product_validation.ok or product_validation.path is None:
            raise ValueError(product_validation.reason)
        output_dir = _product_local_dir(product_validation.path, PRODUCT_DIST_DIRNAME)
        manifest_path = (output_dir / PACKAGE_MANIFEST_FILENAME).resolve()
        if manifest_path.parent != output_dir.resolve():
            raise ValueError("Package manifest path escaped dist.")
        files, excluded = _package_source_files(product_validation.path)
    except Exception as exc:
        return PackagePreviewResult(False, "PACKAGE_PREVIEW_BLOCKED", str(exc))
    return PackagePreviewResult(
        True,
        "PACKAGE_PREVIEW_OK",
        "Source zip package is ready for APPROVE_PACKAGE.",
        str(package_profile.get("name", "Create Source Zip")),
        output_dir,
        manifest_path,
        tuple(relative for _path, relative in files),
        excluded,
    )


def save_package_receipt(product_root: Path, status: str, zip_path: Path | None, manifest_path: Path | None, files: Iterable[str], excluded: Iterable[str], message: str) -> Path:
    receipt = _receipt_path(product_root, "package_receipt")
    content = "\n".join(
        [
            "# ENGEL CODE COMPANION Package Receipt",
            "",
            "Timestamp: " + now_text(),
            "Authority: Josh > Guardian > Engel/runtime",
            "Product root: " + str(product_root),
            "Status: " + status,
            "Package zip: " + (str(zip_path) if zip_path else "none"),
            "Manifest: " + (str(manifest_path) if manifest_path else "none"),
            "Message: " + message,
            "",
            "Files packaged:",
            *["- " + item for item in files],
            "",
            "Excluded:",
            *["- " + item for item in excluded],
            "",
            "Boundary: APPROVE_PACKAGE required; source zip under dist only; sensitive files excluded.",
        ]
    )
    receipt.write_text(content, encoding="utf-8")
    return receipt


def create_approved_package(product_root: Path, profile_name: str | None, approval_token: str) -> PackageCreateResult:
    if str(approval_token or "").strip() != PACKAGE_APPROVAL_TOKEN:
        return PackageCreateResult(False, "PACKAGE_BLOCKED", "Exact APPROVE_PACKAGE token is required.")
    preview = preview_package(product_root, profile_name)
    if not preview.ok or preview.output_dir is None or preview.manifest_path is None:
        return PackageCreateResult(False, preview.status, preview.message, files=preview.files, excluded=preview.excluded)
    validation = validate_product_workspace(product_root)
    if not validation.ok or validation.path is None:
        return PackageCreateResult(False, "PACKAGE_BLOCKED", validation.reason)
    try:
        files, excluded = _package_source_files(validation.path)
        if not files:
            raise ValueError("No packageable source files found.")
        output_dir = preview.output_dir.resolve()
        if output_dir.parent != validation.path.resolve():
            raise ValueError("Dist folder escaped product root.")
        output_dir.mkdir(parents=True, exist_ok=True)
        zip_path = (output_dir / (safe_product_slug(validation.path.name) + "_source_" + filename_stamp() + ".zip")).resolve()
        if zip_path.parent != output_dir:
            raise ValueError("Package zip path escaped dist.")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path, relative in files:
                archive.write(path, relative)
        manifest = {
            "schema": "engel_package_manifest_v1",
            "product_name": validation.path.name,
            "product_root": str(validation.path),
            "package_zip": str(zip_path),
            "package_mode": "source_zip",
            "status": "PACKAGE_ONLY / NOT_RUNTIME / NOT_APPLIED",
            "authority": "Josh > Guardian > Engel/runtime",
            "files": [relative for _path, relative in files],
            "excluded": list(excluded),
            "created_at": now_text(),
        }
        preview.manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        receipt = save_package_receipt(
            validation.path,
            "PACKAGE_CREATED",
            zip_path,
            preview.manifest_path,
            manifest["files"],
            excluded,
            "Source zip package created under product dist.",
        )
    except Exception as exc:
        return PackageCreateResult(False, "PACKAGE_FAILED", str(exc), files=preview.files, excluded=preview.excluded)
    return PackageCreateResult(True, "PACKAGE_CREATED", "Source zip package created under product dist.", zip_path, preview.manifest_path, receipt, tuple(manifest["files"]), tuple(excluded))


def open_dist_folder(product_root: Path) -> ProductProfileResult:
    try:
        validation = validate_product_workspace(product_root)
        if not validation.ok or validation.path is None:
            raise ValueError(validation.reason)
        dist = _product_local_dir(validation.path, PRODUCT_DIST_DIRNAME)
        if not dist.exists() or not dist.is_dir():
            return ProductProfileResult(False, "DIST_MISSING", "Dist folder does not exist.", dist)
        startfile = getattr(os, "startfile", None)
        if startfile is None:
            return ProductProfileResult(False, "OPEN_DIST_UNAVAILABLE", "Opening folders is unavailable on this platform.", dist)
        startfile(str(dist))
    except Exception as exc:
        return ProductProfileResult(False, "OPEN_DIST_BLOCKED", str(exc))
    return ProductProfileResult(True, "OPEN_DIST_OK", "Dist folder opened by explicit user action.", dist)


def redact_sensitive_text(text: str) -> str:
    safe_lines: list[str] = []
    for line in str(text or "").splitlines():
        if SENSITIVE_RE.search(line):
            safe_lines.append("[REDACTED: sensitive-looking line]")
        else:
            safe_lines.append(line)
    return "\n".join(safe_lines)


def build_companion_receipt(
    project_root: Path | None,
    selected_file: SelectedFile | None,
    action: str,
    generated_text: str,
    safety_status: str,
    verification: VerificationResult | None = None,
) -> str:
    root_text = str(project_root) if project_root else "none"
    selected_text = selected_file.relative_path if selected_file and selected_file.relative_path else "none"
    verification = verification or VerificationResult(False, False, "none", None, "not requested", "NOT_REQUESTED")
    generated = _trim_text(redact_sensitive_text(generated_text), MAX_RECEIPT_CHARS)
    return "\n".join(
        [
            "# ENGEL CODE COMPANION Receipt",
            "",
            f"Timestamp: {now_text()}",
            f"Selected project root: {root_text}",
            f"Product workspace root: {root_text}",
            f"Selected file or files: {selected_text}",
            f"User action: {action}",
            f"Product action: {action}",
            f"Safety status: {safety_status}",
            f"Verification requested: {verification.requested}",
            f"Verification approved: {verification.approved}",
            f"Verification command/result: {verification.command} / {verification.status}",
            "",
            "Generated summary or proposed edit:",
            "```text",
            generated,
            "```",
            "",
            "Verification output:",
            "```text",
            _trim_text(redact_sensitive_text(verification.output), 4000),
            "```",
            "",
            "Boundary statements:",
            "- All outputs are proposal text only.",
            "- Product builder writes require exact APPROVE_CHANGE and a visible apply action.",
            "- Product receipts and reports are bounded to the selected product workspace or reports/codex_bridge.",
            "- No autonomous write/execute behavior occurred.",
            "- No provider/API/network behavior was used by ENGEL CODE COMPANION V2.",
            "- File contents were treated as untrusted input.",
        ]
    )


def _confined_receipt_path(filename: str) -> Path:
    root = REPORT_ROOT.resolve()
    candidate = (REPORT_ROOT / filename).resolve()
    if candidate.parent != root:
        raise ValueError("Receipt path escaped reports/codex_bridge.")
    if candidate.suffix.lower() != ".md":
        raise ValueError("Receipt must be markdown.")
    return candidate


def save_companion_receipt(
    project_root: Path | None,
    selected_file: SelectedFile | None,
    action: str,
    generated_text: str,
    safety_status: str,
    verification: VerificationResult | None = None,
) -> Path:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    base = f"{RECEIPT_PREFIX}_{filename_stamp()}.md"
    path = _confined_receipt_path(base)
    for index in range(1, 100):
        if not path.exists():
            content = build_companion_receipt(
                project_root,
                selected_file,
                action,
                generated_text,
                safety_status,
                verification,
            )
            path.write_text(content, encoding="utf-8")
            return path
        path = _confined_receipt_path(f"{RECEIPT_PREFIX}_{filename_stamp()}_{index:02d}.md")
    raise FileExistsError("Could not create a unique companion receipt filename.")


APPROVED_VERIFICATION_COMMANDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "py_compile companion",
        (sys.executable, "-m", "py_compile", str(APP_ROOT / "engel_code_companion.py")),
    ),
    (
        "companion verifier",
        (sys.executable, str(APP_ROOT / "tools" / "verify_engel_code_companion.py")),
    ),
)


def _format_command(command: Iterable[str]) -> str:
    return " ".join(str(part) for part in command)


def run_fixed_verification(approved: bool) -> VerificationResult:
    command_text = " && ".join(label for label, _command in APPROVED_VERIFICATION_COMMANDS)
    if not approved:
        return VerificationResult(True, False, command_text, None, "Verification blocked: approval checkbox not set.", "BLOCKED")

    output_parts: list[str] = []
    final_code = 0
    for label, command in APPROVED_VERIFICATION_COMMANDS:
        try:
            completed = subprocess.run(
                list(command),
                cwd=str(APP_ROOT),
                capture_output=True,
                text=True,
                timeout=VERIFICATION_TIMEOUT_SECONDS,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            return VerificationResult(
                True,
                True,
                command_text,
                None,
                f"{label} timed out after {VERIFICATION_TIMEOUT_SECONDS}s: {exc}",
                "TIMEOUT",
            )
        except OSError as exc:
            return VerificationResult(True, True, command_text, None, f"{label} failed to launch: {exc}", "ERROR")

        final_code = completed.returncode
        output_parts.append(f"$ {_format_command(command)}")
        if completed.stdout:
            output_parts.append(completed.stdout.strip())
        if completed.stderr:
            output_parts.append(completed.stderr.strip())
        output_parts.append(f"return_code={completed.returncode}")
        if completed.returncode != 0:
            break

    status = "PASS" if final_code == 0 else "FAIL"
    return VerificationResult(True, True, command_text, final_code, "\n".join(output_parts), status)


def safety_boundary_summary() -> str:
    return (
        "Boundaries: no startup scanning, no provider/API/network behavior, no "
        "background workers, no autonomous edits, no trusted-memory writes, no "
        "queue mutation, no hidden downloads, no arbitrary shell commands, and no deleting files. "
        "Product workspaces are bounded under products or explicitly selected safe folders; generated files "
        "and patches remain proposals until exact APPROVE_CHANGE, with backups before overwrites. "
        "Legacy example scripts remain bounded under examples/code_companion."
    )


def launch_pyside6_gui() -> int:
    from PySide6.QtCore import Qt, QSize
    from PySide6.QtGui import QFont, QTextCursor
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QFileDialog,
        QFrame,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QSplitter,
        QStatusBar,
        QVBoxLayout,
        QWidget,
    )

    class CodeCompanionWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.current_relpath: str | None = None
            self.current_language_key: str = "python"
            self.dirty = False

            self.setWindowTitle("Engel Code Companion")
            self.setMinimumSize(QSize(960, 600))
            self.resize(1180, 740)
            self.setStyleSheet(self._stylesheet())

            central = QWidget()
            outer = QVBoxLayout(central)
            outer.setContentsMargins(10, 10, 10, 10)
            outer.setSpacing(8)

            outer.addWidget(self._build_topbar())

            main_split = QSplitter(Qt.Orientation.Horizontal)
            main_split.setChildrenCollapsible(False)
            main_split.addWidget(self._build_left())
            main_split.addWidget(self._build_right())
            main_split.setSizes([260, 920])
            main_split.setStretchFactor(0, 0)
            main_split.setStretchFactor(1, 1)
            outer.addWidget(main_split, 1)

            outer.addWidget(self._build_output_panel(), 0)

            self.setCentralWidget(central)

            self.status = QStatusBar()
            self.setStatusBar(self.status)
            self._refresh_status()

            workshop.ensure_workspace()
            self.refresh_file_list()
            self._append_chat(
                "Engel",
                "Workshop ready. Pick a language, click + New, or open a file from the left. "
                "I can Write, Edit, or Explain code for you — use the buttons below."
            )

        # -- stylesheet ----------------------------------------------------
        def _stylesheet(self) -> str:
            return f"""
                QMainWindow, QWidget {{
                    background: {CODE_COMPANION_BG_PRIMARY};
                    color: {CODE_COMPANION_TEXT_PRIMARY};
                    font-family: Segoe UI, Arial, sans-serif;
                    font-size: 10.5pt;
                }}
                QFrame#TopBar {{
                    background: {CODE_COMPANION_BG_PANEL};
                    border: 1px solid {CODE_COMPANION_BORDER_SUBTLE};
                    border-radius: 8px;
                }}
                QFrame#Panel {{
                    background: {CODE_COMPANION_BG_CARD};
                    border: 1px solid {CODE_COMPANION_BORDER_SUBTLE};
                    border-radius: 8px;
                }}
                QLabel#Title {{
                    color: {CODE_COMPANION_TEXT_PRIMARY};
                    font-size: 16pt;
                    font-weight: 800;
                    letter-spacing: 0px;
                }}
                QLabel#FileTitle {{
                    color: {CODE_COMPANION_TEXT_PRIMARY};
                    font-size: 11pt;
                    font-weight: 700;
                    padding: 4px 6px;
                }}
                QLabel#Section {{
                    color: {CODE_COMPANION_TEXT_SECONDARY};
                    font-weight: 700;
                    padding: 2px 0 4px 0;
                }}
                QPushButton {{
                    background: {CODE_COMPANION_BG_CARD_ALT};
                    color: {CODE_COMPANION_TEXT_PRIMARY};
                    border: 1px solid {CODE_COMPANION_BORDER_SUBTLE};
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-weight: 650;
                    min-height: 28px;
                }}
                QPushButton:hover {{
                    background: #1B2430;
                    border: 1px solid {CODE_COMPANION_BORDER_FOCUS};
                }}
                QPushButton:disabled {{
                    background: #10151B;
                    color: {CODE_COMPANION_TEXT_MUTED};
                    border: 1px solid #1D2630;
                }}
                QPushButton#PrimaryRun {{
                    background: #123421;
                    border: 1px solid {CODE_COMPANION_ACCENT_SAFE};
                    color: #ECFFF4;
                }}
                QPushButton#PrimaryRun:hover {{
                    background: #173F2A;
                    border: 1px solid {CODE_COMPANION_BADGE_PASS};
                }}
                QPlainTextEdit, QListWidget, QLineEdit, QComboBox {{
                    background: #080D12;
                    border: 1px solid {CODE_COMPANION_BORDER_SUBTLE};
                    border-radius: 6px;
                    color: {CODE_COMPANION_TEXT_PRIMARY};
                    padding: 6px;
                    selection-background-color: #254D63;
                    selection-color: #ffffff;
                }}
                QPlainTextEdit#Editor, QPlainTextEdit#Output {{
                    font-family: Consolas, Cascadia Mono, monospace;
                    font-size: 10.5pt;
                }}
                QPlainTextEdit#Output {{
                    color: {CODE_COMPANION_TEXT_SECONDARY};
                }}
                QListWidget::item {{
                    padding: 4px 6px;
                    border-radius: 4px;
                }}
                QListWidget::item:selected {{
                    background: #1E3A4A;
                    color: #ffffff;
                }}
                QComboBox {{
                    padding: 4px 8px;
                    min-height: 28px;
                    font-weight: 650;
                }}
                QSplitter::handle {{
                    background: #18202A;
                }}
                QSplitter::handle:hover {{
                    background: {CODE_COMPANION_BORDER_FOCUS};
                }}
                QStatusBar {{
                    background: {CODE_COMPANION_BG_PANEL};
                    color: {CODE_COMPANION_TEXT_MUTED};
                    border-top: 1px solid {CODE_COMPANION_BORDER_SUBTLE};
                }}
                QToolTip {{
                    background: {CODE_COMPANION_BG_CARD_ALT};
                    color: {CODE_COMPANION_TEXT_PRIMARY};
                    border: 1px solid {CODE_COMPANION_BORDER_SUBTLE};
                    padding: 4px;
                }}
            """

        # -- top bar -------------------------------------------------------
        def _build_topbar(self) -> QFrame:
            frame = QFrame()
            frame.setObjectName("TopBar")
            row = QHBoxLayout(frame)
            row.setContentsMargins(14, 10, 14, 10)
            row.setSpacing(10)

            title = QLabel("ENGEL · CODE COMPANION")
            title.setObjectName("Title")
            row.addWidget(title)
            row.addStretch(1)

            row.addWidget(QLabel("Lang"))
            self.lang_combo = QComboBox()
            for lang in workshop.list_languages():
                self.lang_combo.addItem(lang.label, lang.key)
            self.lang_combo.setCurrentText("Python")
            self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
            row.addWidget(self.lang_combo)

            new_btn = QPushButton("+ New")
            new_btn.clicked.connect(self.action_new_file)
            row.addWidget(new_btn)

            open_btn = QPushButton("Open")
            open_btn.clicked.connect(self.action_open_file)
            row.addWidget(open_btn)

            save_btn = QPushButton("Save")
            save_btn.clicked.connect(self.action_save_file)
            row.addWidget(save_btn)

            run_btn = QPushButton("▶ Run")
            run_btn.setObjectName("PrimaryRun")
            run_btn.clicked.connect(self.action_run_file)
            row.addWidget(run_btn)

            return frame

        # -- left: file list ----------------------------------------------
        def _build_left(self) -> QFrame:
            frame = QFrame()
            frame.setObjectName("Panel")
            col = QVBoxLayout(frame)
            col.setContentsMargins(10, 10, 10, 10)
            col.setSpacing(6)

            header = QLabel("Workshop Files")
            header.setObjectName("Section")
            col.addWidget(header)

            self.file_list = QListWidget()
            self.file_list.itemDoubleClicked.connect(self._open_listed_file)
            self.file_list.itemSelectionChanged.connect(self._on_file_selected_in_list)
            col.addWidget(self.file_list, 1)

            row = QHBoxLayout()
            refresh_btn = QPushButton("Refresh")
            refresh_btn.clicked.connect(self.refresh_file_list)
            delete_btn = QPushButton("Delete")
            delete_btn.clicked.connect(self.action_delete_file)
            row.addWidget(refresh_btn)
            row.addWidget(delete_btn)
            col.addLayout(row)

            return frame

        # -- right: editor + chat -----------------------------------------
        def _build_right(self) -> QSplitter:
            split = QSplitter(Qt.Orientation.Vertical)
            split.setChildrenCollapsible(False)
            split.addWidget(self._build_editor_panel())
            split.addWidget(self._build_chat_panel())
            split.setSizes([420, 240])
            return split

        def _build_editor_panel(self) -> QFrame:
            frame = QFrame()
            frame.setObjectName("Panel")
            col = QVBoxLayout(frame)
            col.setContentsMargins(10, 10, 10, 10)
            col.setSpacing(6)

            self.file_title = QLabel("(no file open)")
            self.file_title.setObjectName("FileTitle")
            col.addWidget(self.file_title)

            self.editor = QPlainTextEdit()
            self.editor.setObjectName("Editor")
            self.editor.setPlaceholderText("Open a file or click + New to start coding.")
            self.editor.textChanged.connect(self._on_editor_changed)
            col.addWidget(self.editor, 1)

            return frame

        def _build_chat_panel(self) -> QFrame:
            frame = QFrame()
            frame.setObjectName("Panel")
            col = QVBoxLayout(frame)
            col.setContentsMargins(10, 10, 10, 10)
            col.setSpacing(6)

            header = QLabel("Ask Engel")
            header.setObjectName("Section")
            col.addWidget(header)

            self.chat_view = QPlainTextEdit()
            self.chat_view.setReadOnly(True)
            col.addWidget(self.chat_view, 1)

            row1 = QHBoxLayout()
            self.chat_input = QLineEdit()
            self.chat_input.setPlaceholderText("Describe what you want Engel to write or change…")
            self.chat_input.returnPressed.connect(self.action_send_prompt)
            row1.addWidget(self.chat_input, 1)

            write_btn = QPushButton("Write")
            write_btn.setToolTip("Generate fresh code in the current language and load it into the editor")
            write_btn.clicked.connect(self.action_engel_write)
            row1.addWidget(write_btn)

            edit_btn = QPushButton("Edit")
            edit_btn.setToolTip("Apply your instruction to the current editor content")
            edit_btn.clicked.connect(self.action_engel_edit)
            row1.addWidget(edit_btn)

            explain_btn = QPushButton("Explain")
            explain_btn.setToolTip("Ask Engel to explain the current code")
            explain_btn.clicked.connect(self.action_engel_explain)
            row1.addWidget(explain_btn)

            send_btn = QPushButton("Send")
            send_btn.clicked.connect(self.action_send_prompt)
            row1.addWidget(send_btn)

            col.addLayout(row1)

            return frame

        # -- bottom: output panel -----------------------------------------
        def _build_output_panel(self) -> QFrame:
            frame = QFrame()
            frame.setObjectName("Panel")
            col = QVBoxLayout(frame)
            col.setContentsMargins(10, 8, 10, 8)
            col.setSpacing(4)

            header = QLabel("Output")
            header.setObjectName("Section")
            col.addWidget(header)

            self.output_view = QPlainTextEdit()
            self.output_view.setObjectName("Output")
            self.output_view.setReadOnly(True)
            self.output_view.setMaximumHeight(150)
            self.output_view.setPlaceholderText("Run a file to see its output here.")
            col.addWidget(self.output_view)

            return frame

        # -- helpers -------------------------------------------------------
        def _refresh_status(self) -> None:
            try:
                gate_on = False
                try:
                    import engel_offline_seed_llm as seed
                    gate_on = seed.offline_seed_llm_gate_enabled()
                except Exception:
                    pass
                gate_label = "ON" if gate_on else "OFF"
                ws = str(workshop.WORKSPACE)
                dirty = " · unsaved" if self.dirty else ""
                file_label = self.current_relpath or "no file"
                self.status.showMessage(f"workshop: {ws}  ·  local LLM: {gate_label}  ·  {file_label}{dirty}")
            except Exception as exc:
                self.status.showMessage(f"status error: {exc}")

        def _append_chat(self, who: str, text: str) -> None:
            current = self.chat_view.toPlainText().rstrip()
            stamp = "" if not current else "\n\n"
            self.chat_view.setPlainText(current + stamp + f"{who}: {text}")
            self.chat_view.moveCursor(QTextCursor.End)

        def _append_output(self, text: str) -> None:
            current = self.output_view.toPlainText().rstrip()
            stamp = "" if not current else "\n"
            self.output_view.setPlainText(current + stamp + text)
            self.output_view.moveCursor(QTextCursor.End)

        def _current_language(self):
            data = self.lang_combo.currentData()
            key = str(data) if data is not None else self.current_language_key
            try:
                return workshop.language_for_key(key)
            except ValueError:
                return workshop.language_for_key("python")

        def _on_language_changed(self) -> None:
            self.current_language_key = self._current_language().key
            self._refresh_status()

        def _on_editor_changed(self) -> None:
            if self.current_relpath and not self.dirty:
                self.dirty = True
                self._refresh_status()

        def _on_file_selected_in_list(self) -> None:
            items = self.file_list.selectedItems()
            if not items:
                return
            relpath = items[0].data(Qt.UserRole)
            if relpath and relpath != self.current_relpath:
                self._open_file(str(relpath))

        def _open_listed_file(self, item: QListWidgetItem) -> None:
            relpath = item.data(Qt.UserRole)
            if relpath:
                self._open_file(str(relpath))

        def _open_file(self, relpath: str) -> None:
            try:
                content = workshop.read_file(relpath)
            except Exception as exc:
                QMessageBox.warning(self, "Open File", f"Could not open {relpath}: {exc}")
                return
            self.current_relpath = relpath
            self.editor.blockSignals(True)
            self.editor.setPlainText(content)
            self.editor.blockSignals(False)
            self.dirty = False
            lang = workshop.language_for_extension(Path(relpath).suffix)
            if lang is not None:
                self.current_language_key = lang.key
                idx = self.lang_combo.findData(lang.key)
                if idx >= 0:
                    self.lang_combo.setCurrentIndex(idx)
            self.file_title.setText(relpath)
            self._refresh_status()

        # -- file list ops -------------------------------------------------
        def refresh_file_list(self) -> None:
            self.file_list.clear()
            for entry in workshop.list_files():
                item = QListWidgetItem(f"{entry.name}    {entry.language}    {entry.size} B")
                item.setData(Qt.UserRole, entry.relpath)
                if entry.relpath == self.current_relpath:
                    item.setSelected(True)
                self.file_list.addItem(item)

        # -- toolbar actions ----------------------------------------------
        def action_new_file(self) -> None:
            lang = self._current_language()
            hint, ok = QInputDialog.getText(
                self,
                "New File",
                f"Name (without extension), {lang.label}:",
                text="hello_engel",
            )
            if not ok:
                return
            try:
                path, body = workshop.create_file_from_template(lang.key, hint or "hello_engel")
            except Exception as exc:
                QMessageBox.warning(self, "New File", f"Could not create file: {exc}")
                return
            rel = path.relative_to(workshop.WORKSPACE).as_posix()
            self.refresh_file_list()
            self._open_file(rel)
            self._append_chat("Engel", f"Created {rel} from the {lang.label} starter template.")

        def action_open_file(self) -> None:
            workshop.ensure_workspace()
            path_str, _ = QFileDialog.getOpenFileName(
                self,
                "Open File from Workshop",
                str(workshop.WORKSPACE),
                "All Files (*.*)",
            )
            if not path_str:
                return
            path = Path(path_str).resolve()
            try:
                rel = path.relative_to(workshop.WORKSPACE.resolve()).as_posix()
            except ValueError:
                QMessageBox.warning(self, "Open File", "Pick a file inside the workshop folder.")
                return
            self._open_file(rel)

        def action_save_file(self) -> None:
            if not self.current_relpath:
                # ask for filename
                lang = self._current_language()
                hint, ok = QInputDialog.getText(
                    self,
                    "Save As",
                    f"New file name ({lang.label}, without extension):",
                    text="untitled",
                )
                if not ok:
                    return
                name = workshop.suggest_filename(lang.key, hint or "untitled")
                self.current_relpath = name
                self.file_title.setText(name)
            try:
                workshop.write_file(self.current_relpath, self.editor.toPlainText())
            except Exception as exc:
                QMessageBox.warning(self, "Save", f"Could not save: {exc}")
                return
            self.dirty = False
            self.refresh_file_list()
            self._refresh_status()
            self._append_chat("Engel", f"Saved {self.current_relpath}.")

        def action_delete_file(self) -> None:
            items = self.file_list.selectedItems()
            if not items:
                QMessageBox.information(self, "Delete", "Select a file in the list first.")
                return
            relpath = items[0].data(Qt.UserRole)
            confirm = QMessageBox.question(
                self,
                "Delete File",
                f"Delete {relpath}? This cannot be undone.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if confirm != QMessageBox.Yes:
                return
            try:
                workshop.delete_file(str(relpath))
            except Exception as exc:
                QMessageBox.warning(self, "Delete", f"Could not delete: {exc}")
                return
            if relpath == self.current_relpath:
                self.current_relpath = None
                self.editor.clear()
                self.file_title.setText("(no file open)")
            self.refresh_file_list()
            self._refresh_status()
            self._append_chat("Engel", f"Deleted {relpath}.")

        def action_run_file(self) -> None:
            if not self.current_relpath:
                self._append_output("[no file selected — open or create one first]")
                return
            # auto-save before run if dirty
            if self.dirty:
                try:
                    workshop.write_file(self.current_relpath, self.editor.toPlainText())
                    self.dirty = False
                except Exception as exc:
                    QMessageBox.warning(self, "Save Before Run", f"Could not save: {exc}")
                    return
            self.status.showMessage(f"running {self.current_relpath} …")
            QApplication.processEvents()
            result = workshop.run_file(self.current_relpath)
            self._append_output(f"$ {result.command}")
            if result.stdout:
                self._append_output(result.stdout.rstrip())
            if result.stderr:
                self._append_output("[stderr]")
                self._append_output(result.stderr.rstrip())
            self._append_output(f"[{result.status}  rc={result.returncode}]")
            self._refresh_status()

        # -- chat actions --------------------------------------------------
        def _prompt_text(self) -> str:
            return self.chat_input.text().strip()

        def _clear_prompt(self) -> None:
            self.chat_input.clear()

        def action_engel_write(self) -> None:
            prompt = self._prompt_text()
            if not prompt:
                self._append_chat("Engel", "Tell me what to write — type a short description and press Write.")
                return
            lang = self._current_language()
            self._append_chat("You", f"write ({lang.label}): {prompt}")
            self.status.showMessage(f"Engel is writing {lang.label} …")
            QApplication.processEvents()
            result = workshop.ask_engel_to_write(lang.key, prompt)
            self.editor.blockSignals(True)
            self.editor.setPlainText(result.body)
            self.editor.blockSignals(False)
            self.dirty = True
            if self.current_relpath is None:
                name = workshop.suggest_filename(lang.key, prompt)
                self.current_relpath = name
                self.file_title.setText(name + "  (unsaved)")
            note = " · ".join(result.notes) if result.notes else ""
            self._append_chat(
                "Engel",
                f"Wrote a {lang.label} draft (source: {result.source}). "
                + ("Note: " + note if note else "Click Save when ready.")
            )
            self._clear_prompt()
            self._refresh_status()

        def action_engel_edit(self) -> None:
            prompt = self._prompt_text()
            if not prompt:
                self._append_chat("Engel", "Tell me what to change — type an instruction and press Edit.")
                return
            current = self.editor.toPlainText()
            if not current.strip():
                self._append_chat("Engel", "There's nothing in the editor yet — try Write instead.")
                return
            lang = self._current_language()
            self._append_chat("You", f"edit ({lang.label}): {prompt}")
            self.status.showMessage(f"Engel is editing {lang.label} …")
            QApplication.processEvents()
            result = workshop.ask_engel_to_edit(lang.key, prompt, current)
            if result.ok:
                self.editor.blockSignals(True)
                self.editor.setPlainText(result.body)
                self.editor.blockSignals(False)
                self.dirty = True
                self._append_chat("Engel", f"Applied edit (source: {result.source}). Click Save when ready.")
            else:
                note = " · ".join(result.notes) if result.notes else "no LLM available"
                self._append_chat("Engel", f"Couldn't edit — {note}")
            self._clear_prompt()
            self._refresh_status()

        def action_engel_explain(self) -> None:
            current = self.editor.toPlainText()
            if not current.strip():
                self._append_chat("Engel", "There's nothing in the editor to explain yet.")
                return
            lang = self._current_language()
            question = self._prompt_text() or "Explain what this code does."
            self._append_chat("You", f"explain: {question}")
            self.status.showMessage("Engel is reading the code …")
            QApplication.processEvents()
            result = workshop.ask_engel_to_explain(lang.key, current, question)
            self._append_chat("Engel", result.body)
            if result.notes:
                self._append_chat("Engel", "Note: " + " · ".join(result.notes))
            self._clear_prompt()
            self._refresh_status()

        def action_send_prompt(self) -> None:
            prompt = self._prompt_text()
            if not prompt:
                return
            lowered = prompt.lower().strip()
            if any(word in lowered for word in ("explain", "what does", "read this", "summary")):
                self.action_engel_explain()
                return
            if any(word in lowered for word in ("change", "edit", "rename", "refactor", "fix", "rewrite")):
                self.action_engel_edit()
                return
            self.action_engel_write()

    app = QApplication.instance() or QApplication(sys.argv)
    window = CodeCompanionWindow()
    window.show()
    return app.exec()


def launch_tkinter_gui() -> int:
    print(
        "Engel Code Companion needs PySide6 for the new workshop UI.\n"
        "Install it with:\n"
        "    pip install PySide6\n"
    )
    return 1



def launch_gui() -> int:
    try:
        return launch_pyside6_gui()
    except ImportError:
        return launch_tkinter_gui()


def run_self_test() -> None:
    root_validation = validate_project_root(ROOT)
    assert root_validation.ok, f"ROOT should be selectable as a bounded project: {root_validation.reason}"
    assert not validate_project_root(Path(ROOT.anchor)).ok, "filesystem root should be blocked"
    users_root = Path(ROOT.anchor) / "Users"
    if users_root.exists():
        assert not validate_project_root(users_root).ok, "C:\\Users root should be blocked"
    tree = build_project_tree(ROOT)
    assert len(tree.entries) <= MAX_TREE_ENTRIES, "tree exceeded entry bound"
    current_file = read_file_preview(ROOT, ROOT / "engel_code_companion.py")
    assert current_file.safety_status == "READ_ONLY", "current module should preview read-only"
    summary = summarize_selected_file(current_file)
    assert "# Explanation" in summary and REPORT_ONLY_STATEMENT in summary, "summary boundary missing"
    answer = answer_about_selection(current_file, "Where is the receipt save function?")
    assert "save" in answer.lower(), "selection answer did not include local answer text"
    proposal = propose_edit(current_file, "Add a small status note")
    assert "# Proposed Edit" in proposal and "NOT APPLIED" in proposal, "proposal boundary missing"
    design = propose_edit(current_file, "design how Code Companion fits into AI Body without enabling apply")
    assert "DESIGN ONLY" in design and "NOT APPLIED" in design, "design-first boundary missing"
    verifier = propose_edit(current_file, "suggest verifier for Code Companion")
    assert "# Verification Proposal" in verifier and "Josh > Guardian > Engel/runtime" in verifier, "verifier proposal boundary missing"
    refusal = propose_edit(current_file, "apply this change now")
    assert "REFUSED" in refusal and "No source edit was made." in refusal, "unsafe request refusal missing"
    authority = propose_edit(current_file, "make Guardian higher than Josh")
    assert "Authority inversion is blocked" in authority, "authority refusal missing"
    python_example = example_scripts.build_script_from_prompt(
        "python",
        "Create a hello Engel Python script.",
        "hello_engel_example.py",
    )
    assert python_example.not_runtime and python_example.not_applied, "script result must stay outside runtime/apply"
    assert "EXAMPLE_ONLY / NOT_RUNTIME / NOT_APPLIED" in python_example.content, "script boundary missing"
    assert example_scripts.validate_script_content("python", python_example.content).ok, "python script validation failed"
    java_example = example_scripts.build_script_from_prompt(
        "java",
        "Create a hello Engel Java class.",
        "HelloEngelExample.java",
    )
    assert java_example.filename == "HelloEngelExample.java", "java class/file name mismatch"
    html_example = example_scripts.build_script_from_prompt(
        "html",
        "Create a simple hello Engel dashboard page.",
        "hello_engel_example.html",
    )
    assert "<!doctype html>" in html_example.content.lower(), "html structure missing"
    dependency_plan = example_scripts.detect_dependency_needs(
        "python",
        "Create a Python script using requests.",
        "",
    )
    assert dependency_plan.approval_required and dependency_plan.approval_token == "APPROVE_INSTALL", "dependency approval gate missing"
    template_build = product_templates.build_product_template(
        "python_cli_starter",
        "Self Test Product Template",
        "Create a tiny safe product starter.",
    )
    assert template_build.not_runtime and template_build.not_applied, "product template must stay outside runtime/apply"
    assert template_build.validation.ok, "product template validation failed"
    assert "PRODUCT_ONLY / NOT_RUNTIME / NOT_APPLIED" in "\n".join(template_build.files.values()), "product template boundary missing"
    try:
        product_templates.safe_product_slug("..\\bad")
        raise AssertionError("unsafe product template name accepted")
    except ValueError:
        pass
    product_path = build_new_product_path("self test product")
    assert _is_relative_to(product_path.resolve(), PRODUCTS_ROOT.resolve()), "default product root boundary missing"
    product_proposal = build_new_product_proposal(
        "self test product",
        "Python script",
        "Create a tiny safe script.",
    )
    assert product_proposal.product_root == product_path, "product proposal path mismatch"
    assert not product_proposal.approved, "new product proposal must start unapproved"
    assert product_proposal.files and all(item.action in {"create", "update"} for item in product_proposal.files), "product files missing"
    rendered_product = render_product_proposal(product_proposal)
    assert "PROPOSAL_ONLY / NOT_APPLIED" in rendered_product, "product proposal boundary missing"
    blocked_apply = apply_product_change(product_proposal)
    assert not blocked_apply.ok and blocked_apply.status == "BLOCKED", "unapproved product apply must be blocked"
    approved_product = approve_product_change(product_proposal, CHANGE_APPROVAL_TOKEN)
    assert approved_product.approved and approved_product.approval_token == CHANGE_APPROVAL_TOKEN, "approval token not recorded"
    diff = render_product_diff(approved_product)
    assert "PREVIEW_ONLY / NOT_APPLIED" in diff, "product diff preview boundary missing"
    add_file = build_add_file_proposal(PRODUCTS_ROOT / "self_test_product", "Python script", "notes.md", "local notes")
    assert add_file.files[0].relative_path == "notes.md", "add-file proposal relative path mismatch"
    try:
        approve_product_change(product_proposal, "wrong")
        raise AssertionError("wrong approval token accepted")
    except PermissionError:
        pass
    receipt = build_companion_receipt(ROOT, current_file, "self-test", proposal, "PROPOSAL_TEXT_ONLY")
    assert "No autonomous write/execute behavior occurred" in receipt, "receipt safety statement missing"
    assert "Product action:" in receipt and "APPROVE_CHANGE" in receipt, "product receipt boundary missing"
    assert APPROVED_VERIFICATION_COMMANDS, "fixed verification commands missing"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=ONE_LINE_DESCRIPTION)
    parser.add_argument("--self-test", action="store_true", help="Run bounded local checks without opening the GUI.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        run_self_test()
        print("Self-test passed: bounded tree, read-only preview, proposal text, and receipt text verified.")
        return 0
    return launch_gui()


if __name__ == "__main__":
    raise SystemExit(main())
