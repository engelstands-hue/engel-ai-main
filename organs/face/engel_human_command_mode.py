from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from engel_human_command_shared import (
    post_install_verifier_lines,
    post_install_verifier_sentence,
    human_command_now_stamp,
)


APPROVAL_TOKEN = "APPROVE_INSTALL"
FOLDER_SUMMARY_MAX_FILES = 200


def _resolve_project_root() -> Path:
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable).resolve()
        if exe_path.parent.name.lower() == "app" and exe_path.parent.parent.name.lower() == "live":
            return exe_path.parent.parent.parent
        return exe_path.parent
    return Path(__file__).resolve().parent


PROJECT_ROOT = _resolve_project_root()
REPORTS_ROOT = PROJECT_ROOT / "reports"
CODEX_REPORTS_ROOT = REPORTS_ROOT / "codex_bridge"
MODEL_INSTALL_ROOT = PROJECT_ROOT / "models" / "qwen2.5-0.5b-instruct"

ALLOWED_READ_ROOTS = (PROJECT_ROOT,)
ALLOWED_WRITE_ROOTS = (
    REPORTS_ROOT,
    CODEX_REPORTS_ROOT,
    PROJECT_ROOT / "reports" / "app",
    PROJECT_ROOT / "reports" / "security",
    PROJECT_ROOT / "reports" / "colony",
    PROJECT_ROOT / "reports" / "proposal_autonomy",
    PROJECT_ROOT / "assets",
    PROJECT_ROOT / "models",
)
CONDITIONAL_WRITE_ROOTS = (PROJECT_ROOT / "memory",)
BLOCKED_ROOTS = (
    Path(r"C:\Windows"),
    Path(r"C:\Program Files"),
    Path(r"C:\Program Files (x86)"),
    Path(r"C:\Users"),
)

BINARY_EXTENSIONS = {
    ".7z",
    ".bin",
    ".bmp",
    ".db",
    ".dll",
    ".exe",
    ".gif",
    ".gguf",
    ".ico",
    ".jpeg",
    ".jpg",
    ".msi",
    ".pdf",
    ".png",
    ".pyd",
    ".sqlite",
    ".webp",
    ".zip",
}

BLOCKED_COPY_EXTENSIONS = {
    ".bat",
    ".cmd",
    ".com",
    ".dll",
    ".exe",
    ".jar",
    ".js",
    ".msi",
    ".ps1",
    ".pyd",
    ".py",
    ".scr",
    ".sh",
    ".sys",
    ".vbs",
}

SOURCE_EDIT_EXTENSIONS = {
    ".bat",
    ".cmd",
    ".js",
    ".ps1",
    ".py",
    ".pyw",
    ".sh",
    ".spec",
    ".ts",
    ".vbs",
}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    status: str
    message: str
    path: str = ""
    source: str = ""
    destination: str = ""
    bounded: bool = True


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    status: str
    message: str
    path: str = ""
    source: str = ""
    destination: str = ""
    files_inspected: int = 0
    bounded: bool = True
    wrote_file: bool = False
    copied_file: bool = False
    installed_dependency: bool = False
    package_name: str = ""
    python_executable: str = ""
    report_path: str = ""


def _now_stamp() -> str:
    return human_command_now_stamp()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve(strict=False))
    except Exception:
        return str(path)


def _normcase_abs(path: Path) -> str:
    return os.path.normcase(os.path.abspath(str(path.resolve(strict=False))))


def is_url_like(value: str) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    return bool(re.match(r"^[a-z][a-z0-9+.-]*://", text))


def is_unc_path(value: str) -> bool:
    text = str(value or "").strip()
    if text.startswith("\\\\") or text.startswith("//"):
        return True
    try:
        return str(Path(text)).startswith("\\\\")
    except Exception:
        return False


def normalize_user_path(raw: str) -> Path:
    text = os.path.expandvars(str(raw or "").strip().strip('"').strip("'"))
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate


def is_under_root(path: Path, root: Path) -> bool:
    try:
        child = _normcase_abs(path)
        parent = _normcase_abs(root)
        return os.path.commonpath([child, parent]) == parent
    except Exception:
        return False


def is_blocked_root(path: Path) -> bool:
    raw = str(path)
    if is_url_like(raw) or is_unc_path(raw):
        return True
    for root in BLOCKED_ROOTS:
        if is_under_root(path, root):
            return True
    return False


def _has_symlink_escape(path: Path, allowed_roots: tuple[Path, ...]) -> bool:
    try:
        current = path if path.exists() else path.parent
        candidates = [current] + list(current.parents)
        for candidate in candidates:
            if not candidate.exists():
                continue
            if candidate.is_symlink():
                resolved = candidate.resolve(strict=True)
                if not any(is_under_root(resolved, root) for root in allowed_roots):
                    return True
            if any(_normcase_abs(candidate) == _normcase_abs(root) for root in allowed_roots):
                break
    except Exception:
        return True
    return False


def is_allowed_read_path(path: Path) -> bool:
    if is_blocked_root(path):
        return False
    if not any(is_under_root(path, root) for root in ALLOWED_READ_ROOTS):
        return False
    return not _has_symlink_escape(path, ALLOWED_READ_ROOTS)


def is_allowed_write_path(path: Path) -> bool:
    if is_blocked_root(path):
        return False
    if not any(is_under_root(path, root) for root in ALLOWED_WRITE_ROOTS):
        return False
    return not _has_symlink_escape(path, ALLOWED_WRITE_ROOTS)


def is_allowed_model_path(path: Path) -> bool:
    return is_allowed_write_path(path) and is_under_root(path, PROJECT_ROOT / "models")


def _looks_binary(path: Path) -> bool:
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    try:
        with path.open("rb") as handle:
            sample = handle.read(4096)
        return b"\x00" in sample
    except Exception:
        return True


def validate_read_file(path: str) -> ValidationResult:
    if is_url_like(path):
        return ValidationResult(False, "BLOCKED", "URL-like paths are not allowed for local file research.")
    if is_unc_path(path):
        return ValidationResult(False, "BLOCKED", "UNC/network paths are not allowed for local file research.")
    candidate = normalize_user_path(path)
    if is_blocked_root(candidate):
        return ValidationResult(False, "BLOCKED", "Blocked system, user, network, or URL-like root.", path=_display_path(candidate))
    if not is_allowed_read_path(candidate):
        return ValidationResult(False, "BLOCKED", "Read path is outside approved Engel read roots.", path=_display_path(candidate))
    if not candidate.exists() or not candidate.is_file():
        return ValidationResult(False, "BLOCKED", "Read target is not an existing local file.", path=_display_path(candidate))
    if _looks_binary(candidate):
        return ValidationResult(False, "BLOCKED", "Binary or non-text files are not parsed as text.", path=_display_path(candidate))
    return ValidationResult(True, "PASS", "Read file path approved.", path=_display_path(candidate))


def validate_read_folder(path: str) -> ValidationResult:
    if is_url_like(path):
        return ValidationResult(False, "BLOCKED", "URL-like paths are not allowed for local folder research.")
    if is_unc_path(path):
        return ValidationResult(False, "BLOCKED", "UNC/network paths are not allowed for local folder research.")
    candidate = normalize_user_path(path)
    if is_blocked_root(candidate):
        return ValidationResult(False, "BLOCKED", "Blocked system, user, network, or URL-like root.", path=_display_path(candidate))
    if not is_allowed_read_path(candidate):
        return ValidationResult(False, "BLOCKED", "Folder path is outside approved Engel read roots.", path=_display_path(candidate))
    if not candidate.exists() or not candidate.is_dir():
        return ValidationResult(False, "BLOCKED", "Read target is not an existing local folder.", path=_display_path(candidate))
    return ValidationResult(True, "PASS", "Read folder path approved.", path=_display_path(candidate))


def validate_write_path(path: str) -> ValidationResult:
    if is_url_like(path):
        return ValidationResult(False, "BLOCKED", "URL-like paths are not allowed for local writes.")
    if is_unc_path(path):
        return ValidationResult(False, "BLOCKED", "UNC/network paths are not allowed for local writes.")
    candidate = normalize_user_path(path)
    if is_blocked_root(candidate):
        return ValidationResult(False, "BLOCKED", "Blocked system, user, network, or URL-like root.", path=_display_path(candidate))
    if not is_allowed_write_path(candidate):
        return ValidationResult(False, "BLOCKED", "Write path is outside approved Engel write roots.", path=_display_path(candidate))
    if candidate.suffix.lower() in SOURCE_EDIT_EXTENSIONS:
        return ValidationResult(False, "BLOCKED", "Source/script writes require a separate source-edit approval route.", path=_display_path(candidate))
    if candidate.exists() and candidate.is_dir():
        return ValidationResult(False, "BLOCKED", "Write target is a folder, not a file.", path=_display_path(candidate))
    return ValidationResult(True, "PASS", "Write path approved.", path=_display_path(candidate))


def validate_copy_install(source: str, destination_folder: str) -> ValidationResult:
    if is_url_like(source) or is_url_like(destination_folder):
        return ValidationResult(False, "BLOCKED", "URL-like source or destination is not allowed for local install/copy.")
    if is_unc_path(source) or is_unc_path(destination_folder):
        return ValidationResult(False, "BLOCKED", "UNC/network source or destination is not allowed for local install/copy.")

    src = normalize_user_path(source)
    dst = normalize_user_path(destination_folder)

    if is_blocked_root(src):
        return ValidationResult(False, "BLOCKED", "Source is under a blocked system/user/network root.", source=_display_path(src), destination=_display_path(dst))
    if not src.exists() or not src.is_file():
        return ValidationResult(False, "BLOCKED", "Source must be an existing local file.", source=_display_path(src), destination=_display_path(dst))
    if src.suffix.lower() in BLOCKED_COPY_EXTENSIONS:
        return ValidationResult(False, "BLOCKED", "Executable/script/system install files are blocked in Human Command Mode.", source=_display_path(src), destination=_display_path(dst))
    if is_blocked_root(dst) or not is_allowed_write_path(dst):
        return ValidationResult(False, "BLOCKED", "Destination folder is outside approved Engel write roots.", source=_display_path(src), destination=_display_path(dst))
    if dst.exists() and not dst.is_dir():
        return ValidationResult(False, "BLOCKED", "Destination must be a folder.", source=_display_path(src), destination=_display_path(dst))
    return ValidationResult(True, "PASS", "Local install/copy path approved.", source=_display_path(src), destination=_display_path(dst))


def validate_dependency_package_name(package_name: str) -> ValidationResult:
    package = str(package_name or "").strip()
    if not package:
        return ValidationResult(False, "BLOCKED", "Package name is required.")
    if is_url_like(package) or package.lower().startswith("git+"):
        return ValidationResult(False, "BLOCKED", "URL and Git package installs require a separate approval task.")
    if any(token in package for token in [" ", "\t", "\r", "\n", ";", "&", "|", "`", '"', "'", "/", "\\", ":", "@"]):
        return ValidationResult(False, "BLOCKED", "Package name contains blocked shell, path, URL, or injection characters.")
    if package.lower().startswith("-r") or package.startswith("-") or "--" in package:
        return ValidationResult(False, "BLOCKED", "Pip flags and requirements-file arguments are not allowed.")
    if package.lower() in {"pip", "setuptools"}:
        return ValidationResult(False, "BLOCKED", "Core packaging tool mutation requires a separate approval task.")

    ident = r"[A-Za-z0-9][A-Za-z0-9._-]*"
    version = r"[A-Za-z0-9][A-Za-z0-9._!*+-]*"
    pattern = rf"^{ident}((==|!=|~=|>=|<=|>|<){version})?$"
    if not re.match(pattern, package):
        return ValidationResult(False, "BLOCKED", "Package name must be a simple Python package identifier with an optional version specifier.")
    return ValidationResult(True, "PASS", "Dependency package name approved.", path=package)


def summarize_file_bounded(path: str, max_chars: int = 12000) -> str:
    validation = validate_read_file(path)
    if not validation.ok:
        return "# File Research Blocked\n\n" + validation.message + "\n\nPath: " + validation.path

    candidate = Path(validation.path)
    try:
        text = candidate.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return "# File Research Error\n\n" + str(exc)

    bounded_text = text[: max(0, int(max_chars))]
    truncated = len(text) > len(bounded_text)
    lines = [
        "# Bounded File Research",
        "",
        "Path: " + validation.path,
        "Bytes: " + str(candidate.stat().st_size),
        "Characters inspected: " + str(len(bounded_text)),
        "Bounded: yes",
        "Truncated: " + ("yes" if truncated else "no"),
        "",
        "## Text Excerpt",
        "",
        bounded_text.strip() or "[empty file]",
    ]
    return "\n".join(lines)


def summarize_folder_bounded(path: str, max_files: int = FOLDER_SUMMARY_MAX_FILES) -> str:
    validation = validate_read_folder(path)
    if not validation.ok:
        return "# Folder Research Blocked\n\n" + validation.message + "\n\nPath: " + validation.path

    root = Path(validation.path)
    limit = max(1, min(int(max_files), FOLDER_SUMMARY_MAX_FILES))
    inspected: list[Path] = []
    skipped_binary = 0
    skipped_dirs = 0

    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if not name.startswith("__pycache__"))
        skipped_dirs += max(0, len(dirnames) - len(dirnames[:50]))
        for filename in sorted(filenames):
            file_path = Path(current) / filename
            if is_blocked_root(file_path) or not is_allowed_read_path(file_path):
                continue
            if file_path.suffix.lower() in BINARY_EXTENSIONS:
                skipped_binary += 1
                continue
            inspected.append(file_path)
            if len(inspected) >= limit:
                break
        if len(inspected) >= limit:
            break

    lines = [
        "# Bounded Folder Research",
        "",
        "Path: " + validation.path,
        "Files inspected: " + str(len(inspected)),
        "Max files: " + str(limit),
        "Bounded: yes",
        "Binary files skipped: " + str(skipped_binary),
        "Directory traversal: approved root only",
        "",
        "## Files",
    ]

    for item in inspected:
        rel = item.relative_to(root)
        try:
            size = item.stat().st_size
        except Exception:
            size = 0
        preview = ""
        if size <= 65536:
            try:
                sample = item.read_text(encoding="utf-8", errors="replace")[:240].replace("\r", " ").replace("\n", " ")
                preview = " | " + " ".join(sample.split())
            except Exception:
                preview = ""
        lines.append("- " + str(rel) + " | " + str(size) + " bytes" + preview)

    if skipped_dirs:
        lines += ["", "Note: folder walk stayed bounded and did not scan the whole drive."]
    return "\n".join(lines)


def _safe_report_name(report_name: str) -> str:
    base = Path(str(report_name or "").strip().replace("/", "_").replace("\\", "_")).name
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    if not base:
        base = "HUMAN_COMMAND_REPORT.md"
    if Path(base).suffix.lower() not in {".md", ".txt", ".json"}:
        base += ".md"
    return base


def write_report_safely(report_name: str, content: str, report_root: str = r"reports\codex_bridge") -> ActionResult:
    root = normalize_user_path(report_root)
    if is_blocked_root(root) or not is_allowed_write_path(root):
        return ActionResult(False, "BLOCKED", "Report root is outside approved Engel report roots.", path=_display_path(root))
    target = root / _safe_report_name(report_name)
    return write_file_safely(str(target), content, overwrite=False)


def write_file_safely(path: str, content: str, overwrite: bool = False) -> ActionResult:
    validation = validate_write_path(path)
    if not validation.ok:
        return ActionResult(False, validation.status, validation.message, path=validation.path)
    target = Path(validation.path)
    if target.exists() and not overwrite:
        return ActionResult(False, "REQUIRES_APPROVAL", "Target exists. Overwrite requires an explicit overwrite route.", path=_display_path(target))
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content), encoding="utf-8")
        return ActionResult(True, "PASS", "File written through guarded Human Command Mode.", path=_display_path(target), wrote_file=True)
    except Exception as exc:
        return ActionResult(False, "ERROR", str(exc), path=_display_path(target))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def copy_local_file_safely(source: str, destination_folder: str, overwrite: bool = False) -> ActionResult:
    validation = validate_copy_install(source, destination_folder)
    if not validation.ok:
        return ActionResult(False, validation.status, validation.message, source=validation.source, destination=validation.destination)

    src = Path(validation.source)
    dst_folder = Path(validation.destination)
    dst = dst_folder / src.name
    try:
        if src.resolve(strict=True) == dst.resolve(strict=False):
            return ActionResult(True, "PASS", "Local file is already installed at the destination. No copy or execution was performed.", source=_display_path(src), destination=_display_path(dst), copied_file=False)
    except Exception:
        pass
    if dst.exists() and not overwrite:
        try:
            same = src.stat().st_size == dst.stat().st_size and _sha256(src) == _sha256(dst)
        except Exception:
            same = False
        if same:
            return ActionResult(True, "PASS", "Matching destination file already exists. No copy or execution was performed.", source=_display_path(src), destination=_display_path(dst), copied_file=False)
        return ActionResult(False, "REQUIRES_APPROVAL", "Destination file exists. Overwrite requires an explicit overwrite route.", source=_display_path(src), destination=_display_path(dst))

    try:
        dst_folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return ActionResult(True, "PASS", "Local file copied into approved Engel folder. No execution was performed.", source=_display_path(src), destination=_display_path(dst), copied_file=True)
    except Exception as exc:
        return ActionResult(False, "ERROR", str(exc), source=_display_path(src), destination=_display_path(dst))


def install_model_file_safely(source: str) -> ActionResult:
    if is_url_like(source) or is_unc_path(source):
        return ActionResult(False, "BLOCKED", "Model install requires an existing local .gguf file, not a URL or network path.", source=str(source))
    src = normalize_user_path(source)
    if src.suffix.lower() != ".gguf":
        return ActionResult(False, "BLOCKED", "Model install accepts only local .gguf files.", source=_display_path(src), destination=_display_path(MODEL_INSTALL_ROOT))
    return copy_local_file_safely(str(src), str(MODEL_INSTALL_ROOT), overwrite=False)


def _roots_list(roots: tuple[Path, ...]) -> list[str]:
    return [_display_path(path) for path in roots]


def build_human_command_mode_status() -> str:
    return "\n".join([
        "# Engel Human Command Mode",
        "",
        "Human-commanded local actions: ENABLED",
        "Autonomy: BLOCKED",
        "Background workers: BLOCKED",
        "Model-command execution: BLOCKED",
        "Provider fallback: BLOCKED",
        "Remote Queen runtime: BLOCKED",
        "File research: APPROVED ROOTS ONLY",
        "Report writes: APPROVED REPORT ROOTS ONLY",
        "Local install/copy: APPROVED LOCAL FILES ONLY",
        "Human-approved dependency install: APPROVAL TOKEN REQUIRED",
        "Package/system install: SEPARATE APPROVAL REQUIRED",
        "Source edits: EXPLICIT APPROVAL REQUIRED",
        "Trusted memory writes: EXPLICIT APPROVAL REQUIRED",
    ])


def build_guarded_write_status() -> str:
    lines = [
        "# Guarded Write Status",
        "",
        "Allowed read roots:",
    ]
    lines += ["- " + item for item in _roots_list(ALLOWED_READ_ROOTS)]
    lines += ["", "Allowed write roots:"]
    lines += ["- " + item for item in _roots_list(ALLOWED_WRITE_ROOTS)]
    lines += [
        "",
        "Conditional memory write rules:",
        "- " + _display_path(PROJECT_ROOT / "memory") + " is restricted to explicit approved contract/checkpoint/docs writes.",
        "- Casual memory writes and model-generated trusted memory writes remain blocked.",
        "",
        "Blocked roots:",
        "- C:\\Windows",
        "- C:\\Program Files",
        "- C:\\Program Files (x86)",
        "- C:\\Users",
        "- UNC/network paths",
        "- URL-like paths",
        "",
        "Overwrite behavior:",
        "- Existing files are not overwritten unless a future explicit overwrite route approves it.",
        "",
        "Execution boundaries:",
        "- Arbitrary shell blocked.",
        "- Network/download install blocked unless separately approved.",
        "- Dependency install allowed only through APPROVE_INSTALL route.",
        "- Package-manager/system install requires separate explicit approval.",
        "- Local file/model/asset install-copy allowed through validated routes.",
    ]
    return "\n".join(lines)


def build_dependency_install_plan(package_name: str, reason: str) -> str:
    validation = validate_dependency_package_name(package_name)
    package = str(package_name or "").strip()
    if not validation.ok:
        return "# Dependency Install Plan Blocked\n\n" + validation.message
    reason_text = str(reason or "").strip() or "[reason required before install]"
    import_name = _import_name_for_package(package)
    command = [sys.executable, "-m", "pip", "install", package]
    verifier_lines = post_install_verifier_lines()
    return "\n".join([
        "# Dependency Install Plan",
        "",
        "Package: " + package,
        "Reason: " + reason_text,
        "Target Python executable: " + sys.executable,
        "Approval token required: " + APPROVAL_TOKEN,
        "",
        "Structured pip command:",
        json.dumps(command, indent=2),
        "",
        "Import test when practical:",
        "- python import name: " + import_name,
        "",
        "Post-install verifier commands:",
        *verifier_lines,
        "",
        "Rollback/uninstall command if needed:",
        json.dumps([sys.executable, "-m", "pip", "uninstall", package.split("==", 1)[0], "-y"], indent=2),
        "",
        "Safety boundaries:",
        "- No model output can trigger this install.",
        "- No arbitrary shell command is accepted.",
        "- No provider/API fallback, autonomy, background worker, trusted-memory write, queue mutation, route mutation, source edit, or applied learning is enabled.",
    ])


def build_package_install_requires_approval_message(package_name: str, reason: str = "") -> str:
    package = str(package_name or "").strip() or "<package>"
    reason_text = str(reason or "").strip() or "<reason>"
    return "\n".join([
        "# Package/System Install Blocked",
        "",
        "Package/system install requires separate approval.",
        "",
        "For Python dependency installs into Engel's active environment, use:",
        "install dependency " + package + " for " + reason_text + " " + APPROVAL_TOKEN,
        "",
        "System install requires a separate approved task with exact installer/source, rollback note, and verifier plan.",
    ])


def _base_package_name(package_name: str) -> str:
    return re.split(r"==|!=|~=|>=|<=|>|<", str(package_name or "").strip(), maxsplit=1)[0]


def _import_name_for_package(package_name: str) -> str:
    base = _base_package_name(package_name).lower()
    mapping = {
        "beautifulsoup4": "bs4",
        "llama-cpp-python": "llama_cpp",
        "opencv-python": "cv2",
        "pillow": "PIL",
        "pyyaml": "yaml",
        "scikit-learn": "sklearn",
    }
    return mapping.get(base, base.replace("-", "_"))


def _write_dependency_report(package_name: str, content: str) -> ActionResult:
    safe_package = re.sub(r"[^A-Za-z0-9._-]+", "_", _base_package_name(package_name)).strip("_") or "dependency"
    report_name = "HUMAN_COMMAND_DEPENDENCY_INSTALL_" + safe_package + "_" + _now_stamp() + ".md"
    return write_report_safely(report_name, content, r"reports\codex_bridge")


def _action_dict(result: ActionResult) -> dict[str, Any]:
    return asdict(result)


def run_approved_dependency_install(package_name: str, reason: str, approval_token: str) -> ActionResult:
    package = str(package_name or "").strip()
    reason_text = str(reason or "").strip()
    if str(approval_token or "").strip() != APPROVAL_TOKEN:
        return ActionResult(
            False,
            "REQUIRES_APPROVAL",
            "Dependency install requires exact approval token " + APPROVAL_TOKEN + ".",
            package_name=package,
            python_executable=sys.executable,
        )
    validation = validate_dependency_package_name(package)
    if not validation.ok:
        return ActionResult(False, validation.status, validation.message, package_name=package, python_executable=sys.executable)
    if not reason_text:
        return ActionResult(False, "REQUIRES_APPROVAL", "Dependency install reason is required.", package_name=package, python_executable=sys.executable)

    import_name = _import_name_for_package(package)
    already_available = importlib.util.find_spec(import_name) is not None and not re.search(r"==|!=|~=|>=|<=|>|<", package)
    command = [sys.executable, "-m", "pip", "install", package]
    stdout = ""
    stderr = ""
    return_code = 0
    installed = False
    status = "PASS"
    message = "Dependency already importable in active Engel Python environment. No pip install was run."

    if not already_available:
        try:
            import subprocess

            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=900,
                shell=False,
            )
            return_code = int(completed.returncode)
            stdout = str(completed.stdout or "")[-8000:]
            stderr = str(completed.stderr or "")[-8000:]
            installed = return_code == 0
            status = "PASS" if installed else "ERROR"
            message = "Dependency install completed." if installed else "Dependency install failed."
        except Exception as exc:
            return_code = -1
            stderr = str(exc)
            status = "ERROR"
            message = "Dependency install errored."

    import_ok = importlib.util.find_spec(import_name) is not None
    verifier_sentence = post_install_verifier_sentence()
    report_lines = [
        "# Human Command Dependency Install Report",
        "",
        "Status: " + status,
        "Package: " + package,
        "Reason: " + reason_text,
        "Approval token present: yes",
        "Python executable: " + sys.executable,
        "Structured command:",
        json.dumps(command, indent=2),
        "Pip was run: " + ("yes" if not already_available else "no"),
        "Return code: " + str(return_code),
        "Import test name: " + import_name,
        "Import test passed: " + ("yes" if import_ok else "no"),
        "",
        "Safety:",
        "- No shell command string was accepted.",
        "- No model output triggered this install.",
        "- No provider/API fallback, autonomy, background worker, trusted-memory write, queue mutation, route mutation, source edit, or applied learning was enabled.",
        "- Post-install verifiers are required externally: " + verifier_sentence + ".",
        "",
        "Stdout tail:",
        stdout or "[none]",
        "",
        "Stderr tail:",
        stderr or "[none]",
    ]
    report = _write_dependency_report(package, "\n".join(report_lines))
    ok = status == "PASS" and import_ok and report.ok
    final = ActionResult(
        ok,
        "PASS" if ok else status,
        message + " Import test " + ("passed." if import_ok else "failed."),
        installed_dependency=installed,
        package_name=package,
        python_executable=sys.executable,
        report_path=report.path,
        wrote_file=report.wrote_file,
    )
    _action_dict(final)
    return final
