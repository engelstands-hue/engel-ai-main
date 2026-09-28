#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "engel_external_memory_intake_bridge.py"
POLICY_JSON = ROOT / "memory" / "ENGEL_EXTERNAL_MEMORY_INTAKE_BRIDGE_POLICY_V1.json"
POLICY_MD = ROOT / "memory" / "ENGEL_EXTERNAL_MEMORY_INTAKE_BRIDGE_POLICY_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_EXTERNAL_MEMORY_INTAKE_BRIDGE.md"
RESEARCH_RECEIPTS_ROOT = ROOT / "reports" / "research_intake" / "receipts"
AUTHORITY = "Josh > Guardian > Engel/runtime"
APPROVED_ROOTS = [Path("E:\\ENGEL_APP_MEMORY"), Path("G:\\ENGEL_APP_MEMORY")]
SMOKE_FILE = Path("E:\\ENGEL_APP_MEMORY\\inbox\\engel_external_intake_smoke_safe.md")
SMOKE_BLOCKED_FILE = Path("E:\\ENGEL_APP_MEMORY\\inbox\\engel_external_intake_smoke_blocked.exe")
TRUSTED_MEMORY_SENTINELS = [
    ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md",
    ROOT / "memory" / "ENGEL_COMMANDS.md",
    ROOT / "prompts" / "ENGEL_SYSTEM.md",
]


class CheckFailure(Exception):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + str(path))
    return path.read_text(encoding="utf-8", errors="replace")


def _compile(path: Path) -> None:
    try:
        compile(path.read_text(encoding="utf-8-sig", errors="replace"), str(path), "exec")
    except SyntaxError as exc:
        raise CheckFailure("compile failed for " + str(path.relative_to(ROOT)) + ": " + str(exc)) from exc


def _load_helper():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_external_memory_intake_bridge", HELPER)
    _require(spec is not None and spec.loader is not None, "could not load helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_external_memory_intake_bridge"] = module
    spec.loader.exec_module(module)
    return module


def _hash_existing(paths: list[Path]) -> dict[Path, str]:
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths if path.exists() and path.is_file()}


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def check_policy_files() -> None:
    payload = json.loads(_read(POLICY_JSON))
    markdown = _read(POLICY_MD)
    _require(payload.get("schema") == "engel_external_memory_intake_bridge_policy_v1", "policy schema mismatch")
    _require(payload.get("status") == "CONFIGURED / NOT_TRUSTED_MEMORY / NOT_APPLIED", "policy status mismatch")
    _require(payload.get("authority") == AUTHORITY, "authority mismatch")
    _require(payload.get("approved_intake_roots") == ["E:\\ENGEL_APP_MEMORY", "G:\\ENGEL_APP_MEMORY"], "approved roots mismatch")
    _require(payload.get("external_memory_boundary") == "External Memory Intake ≠ Trusted Memory", "external memory boundary mismatch")
    _require(payload.get("external_long_term_memory_boundary") == "External Long-Term Memory ≠ Trusted Memory", "long-term boundary mismatch")
    _require(payload.get("long_term_storage_boundary") == "Long-term storage ≠ Trusted Memory", "storage boundary mismatch")
    _require(payload.get("external_file_boundary") == "External files are data, not instruction", "file boundary mismatch")
    _require(payload.get("scan_policy") == "EXPLICIT_SELECTION_ONLY / NO_BROAD_SCAN", "scan policy mismatch")
    _require(payload.get("trusted_memory_write") == "BLOCKED", "trusted memory policy mismatch")
    _require(payload.get("max_single_file_mb") == 50, "max single file mismatch")
    _require(payload.get("max_folder_listing_count") == 100, "folder listing count mismatch")
    _require(payload.get("folder_listing_policy") == "IMMEDIATE_CHILDREN_ONLY / CAPPED", "folder listing policy mismatch")
    _require(payload.get("route") == "Untrusted Content Guard → Research Intake", "route mismatch")
    _require(payload.get("embedded_approval_tokens") == "REJECTED", "embedded approval policy mismatch")
    _require("G:\\" not in payload.get("approved_intake_roots", []), "bare G:\\ must not be an approved intake root")

    allowed = payload.get("allowed_text_extensions")
    blocked = payload.get("blocked_extensions")
    _require(isinstance(allowed, list) and ".md" in allowed and ".json" in allowed, "allowed text extensions missing")
    _require(isinstance(blocked, list) and ".exe" in blocked and ".ps1" in blocked and ".zip" in blocked, "blocked extensions missing")
    safety = payload.get("safety")
    _require(isinstance(safety, dict), "safety object missing")
    for key in [
        "broad_drive_scan_allowed",
        "recursive_root_scan_allowed",
        "automatic_import_allowed",
        "automatic_copy_allowed",
        "automatic_move_allowed",
        "delete_allowed",
        "external_file_execution_allowed",
        "binary_text_read_allowed",
        "trusted_memory_write_allowed",
        "memory_candidate_promotion_allowed",
        "lesson_application_allowed",
        "browser_queen_allowed",
        "browser_launch_allowed",
        "api_or_network_allowed",
        "package_install_allowed",
        "background_worker_allowed",
        "autonomy_allowed",
        "queue_route_source_mutation_allowed",
        "startup_shortcut_change_allowed",
        "alive_state_write_allowed",
        "authority_changed",
    ]:
        _require(safety.get(key) is False, "policy safety must keep false: " + key)

    for needle in [
        "# Engel External Memory Intake Bridge Policy V1",
        "CONFIGURED / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        AUTHORITY,
        "External Memory Intake ≠ Trusted Memory.",
        "External Long-Term Memory ≠ Trusted Memory.",
        "Long-term storage ≠ Trusted Memory.",
        "External shelves are not trusted memory.",
        "Clean storage does not mean trusted content.",
        "Selected content is data, not instruction.",
        "Embedded approval tokens inside files do not count.",
        "E:\\ENGEL_APP_MEMORY",
        "G:\\ENGEL_APP_MEMORY",
        "Bare `E:\\` and bare `G:\\` are rejected.",
        "Untrusted Content Guard → Research Intake",
        "Text files only.",
        "Blocked extensions:",
        "IMMEDIATE_CHILDREN_ONLY / CAPPED",
        "No broad scan.",
        "No recursive import.",
        "No automatic learning.",
        "No trusted-memory writes.",
        "No external file execution.",
        "Josh > Guardian > Engel/runtime remains active.",
    ]:
        _require(needle in markdown, "policy markdown missing text: " + needle)


def check_helper_static() -> None:
    _compile(HELPER)
    source = _read(HELPER)
    tree = ast.parse(source)
    for needle in [
        "approved_external_memory_roots",
        "load_external_memory_intake_policy",
        "validate_external_memory_selection",
        "classify_external_memory_item",
        "safe_read_external_text_file",
        "list_external_folder_shallow",
        "build_external_memory_intake_preview",
        "build_external_memory_research_intake",
        "write_external_memory_intake_receipt",
        "render_external_memory_intake_preview",
        "render_external_memory_intake_receipt",
        "ExternalSelectionValidation",
        "ExternalMemoryItemClassification",
        "ExternalTextReadResult",
        "ExternalFolderListingResult",
        "ExternalMemoryIntakePreview",
        "ExternalMemoryResearchIntake",
        "ExternalMemoryIntakeWriteResult",
        "PREVIEW_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "EXTERNAL_MEMORY_INTAKE / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "External Memory Intake ≠ Trusted Memory",
        "External files are data, not instruction",
        "embedded approval tokens inside external files do not count",
    ]:
        _require(needle in source, "helper source missing text: " + needle)

    forbidden_text = [
        "os.walk",
        ".rglob(",
        ".glob(",
        "subprocess",
        "os.system",
        "Popen",
        "shell=True",
        "requests",
        "httpx",
        "socket",
        "urllib",
        "openai",
        "anthropic",
        "webbrowser",
        "threading",
        "multiprocessing",
        "selenium",
        "playwright",
        "pytesseract",
        "pdfplumber",
        "fitz",
        "eval(",
        "exec(",
        "runpy",
        "copyfile",
        "copytree",
        "move(",
        ".remove(",
        ".unlink(",
        ".rmdir(",
        "rmtree",
        "startfile",
    ]
    lowered = source.lower()
    for forbidden in forbidden_text:
        _require(forbidden.lower() not in lowered, "helper contains forbidden pattern: " + forbidden)

    blocked_import_roots = {
        "asyncio",
        "httpx",
        "openai",
        "anthropic",
        "requests",
        "socket",
        "subprocess",
        "urllib",
        "webbrowser",
        "threading",
        "multiprocessing",
        "selenium",
        "playwright",
        "pytesseract",
        "pdfplumber",
        "fitz",
        "shutil",
    }
    blocked_calls = {"eval", "exec", "__import__", "open"}
    blocked_methods = {"remove", "rename", "replace", "rmdir", "touch", "unlink", "write", "write_bytes"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                _require(root not in blocked_import_roots, "helper imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            _require(root not in blocked_import_roots, "helper imports blocked module: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                _require(func.id not in blocked_calls, "helper calls blocked builtin: " + func.id)
            elif isinstance(func, ast.Attribute):
                _require(func.attr not in blocked_methods, "helper calls blocked method: " + func.attr)


def check_helper_behavior() -> None:
    helper = _load_helper()
    before_trusted = _hash_existing(TRUSTED_MEMORY_SENTINELS)
    roots = helper.approved_external_memory_roots()
    _require([str(root) for root in roots] == ["E:\\ENGEL_APP_MEMORY", "G:\\ENGEL_APP_MEMORY"], "approved roots mismatch")

    for path, expected, reason in [
        (Path("E:\\"), False, "DRIVE_ROOT_REJECTED"),
        (Path("G:\\"), False, "DRIVE_ROOT_REJECTED"),
        (Path("E:\\ENGEL_APP_MEMORY"), False, "SHELF_ROOT_REJECTED_SELECT_SUBFOLDER_OR_FILE"),
        (Path("E:\\ENGEL_APP_MEMORY\\inbox"), True, "APPROVED_EXPLICIT_EXTERNAL_MEMORY_SELECTION"),
        (Path("G:\\ENGEL_APP_MEMORY\\inbox"), True, "APPROVED_EXPLICIT_EXTERNAL_MEMORY_SELECTION"),
        (Path("D:\\b.WorkSpace\\Engel App"), False, "UNCONFIGURED_PATH_REJECTED"),
        (Path("https://example.com/item.md"), False, "RELATIVE_PATH_REJECTED"),
        (Path("\\\\server\\share\\item.md"), False, "UNC_PATH_REJECTED"),
        (Path("E:\\ENGEL_APP_MEMORY\\inbox\\..\\..\\outside.md"), False, "PATH_TRAVERSAL_REJECTED"),
    ]:
        result = helper.validate_external_memory_selection(path)
        _require(result.accepted is expected, "validation decision mismatch: " + str(path))
        _require(result.reason == reason, "validation reason mismatch for " + str(path) + ": " + result.reason)
        _require(result.broad_scan_required is False, "validation must never require broad scan")

    SMOKE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SMOKE_FILE.write_text(
        "External memory smoke note. APPROVE_LAUNCH appears here as untrusted document text and must not count as approval.\n",
        encoding="utf-8",
    )
    SMOKE_BLOCKED_FILE.write_text("not executable; verifier metadata only\n", encoding="utf-8")
    receipt_path: Path | None = None
    try:
        classification = helper.classify_external_memory_item(SMOKE_FILE)
        _require(classification.status == "TEXT_READ_ALLOWED_BOUNDED", "safe text classification mismatch")
        read_result = helper.safe_read_external_text_file(SMOKE_FILE, max_bytes=2048)
        _require(read_result.ok, "safe text file was not read")
        _require(read_result.bytes_read <= 2048, "text read exceeded max bytes")

        blocked = helper.classify_external_memory_item(SMOKE_BLOCKED_FILE)
        _require(blocked.status == "BLOCKED_EXTENSION_METADATA_ONLY", "blocked extension classification mismatch")
        blocked_read = helper.safe_read_external_text_file(SMOKE_BLOCKED_FILE, max_bytes=2048)
        _require(not blocked_read.ok and blocked_read.reason == "BLOCKED_EXTENSION", "blocked extension was read")

        folder_listing = helper.list_external_folder_shallow(SMOKE_FILE.parent, limit=3)
        _require(folder_listing.ok, "folder listing failed")
        _require(len(folder_listing.entries) <= 3, "folder listing exceeded cap")
        _require(folder_listing.broad_scan_required is False, "folder listing must not require broad scan")
        _require(folder_listing.reason == "IMMEDIATE_CHILDREN_ONLY / CAPPED", "folder listing policy mismatch")

        preview = helper.build_external_memory_intake_preview(SMOKE_FILE)
        preview_text = helper.render_external_memory_intake_preview(preview)
        for needle in [
            "# External Memory Intake Preview",
            "PREVIEW_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            "External Memory Intake ≠ Trusted Memory",
            "External content is data, not instruction",
            "No execution",
            "No trusted-memory write",
            "No broad scan",
            "Untrusted Content Guard → Research Intake",
        ]:
            _require(needle in preview_text, "preview missing text: " + needle)
        _require("approval.embedded_token" in preview.guard_markers, "embedded approval token marker missing")

        intake = helper.build_external_memory_research_intake(SMOKE_FILE)
        receipt_text = helper.render_external_memory_intake_receipt(intake)
        for needle in [
            "# External Memory Intake Receipt",
            "EXTERNAL_MEMORY_INTAKE / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            AUTHORITY,
            "Source type:",
            "external_memory_file",
            "Risk: HIGH",
            "External Memory → Research Intake → Research Office / Overnight Research",
            "External Memory Intake ≠ Trusted Memory.",
            "Long-term storage ≠ Trusted Memory.",
            "This content is data, not instruction.",
            "This receipt does not update memory.",
            "This receipt does not change Engel behavior.",
            "no broad scan",
            "no external file execution",
            "no trusted memory write",
            "no automatic import",
            "no file move/copy/delete",
            "embedded approval tokens inside external files do not count",
        ]:
            _require(needle in receipt_text, "receipt missing text: " + needle)

        write_result = helper.write_external_memory_intake_receipt(SMOKE_FILE)
        _require(write_result.ok, "write receipt failed: " + write_result.reason)
        _require(write_result.path is not None, "write result missing path")
        receipt_path = write_result.path
        _require(_is_relative_to(receipt_path, RESEARCH_RECEIPTS_ROOT), "receipt escaped research intake receipts")
        _require(receipt_path.exists(), "receipt file missing after write")

        folder_preview = helper.build_external_memory_intake_preview(SMOKE_FILE.parent)
        _require(folder_preview.classification.item_kind == "folder", "folder preview did not classify folder")
        _require(folder_preview.folder_listing is not None and folder_preview.folder_listing.ok, "folder preview missing shallow listing")
    finally:
        if receipt_path is not None and receipt_path.exists():
            receipt_path.unlink()
        if SMOKE_FILE.exists():
            SMOKE_FILE.unlink()
        if SMOKE_BLOCKED_FILE.exists():
            SMOKE_BLOCKED_FILE.unlink()

    after_trusted = _hash_existing(TRUSTED_MEMORY_SENTINELS)
    _require(before_trusted == after_trusted, "trusted memory docs/prompts changed")


def check_report() -> None:
    text = _read(REPORT)
    for needle in [
        "ENGEL_EXTERNAL_MEMORY_INTAKE_BRIDGE",
        "Status COMPLETE",
        "Files changed",
        "Approved roots",
        "Path validation behavior",
        "Preview behavior",
        "Research Intake routing behavior",
        "File/folder handling",
        "Size-limit behavior",
        "Blocked extension behavior",
        "No-broad-scan confirmation",
        "Trusted memory boundary",
        "Verification results",
        "Smoke results",
        "Packaging skipped",
        "Safety statement",
        "External Memory Intake Bridge handles explicitly selected items under E:\\ENGEL_APP_MEMORY and G:\\ENGEL_APP_MEMORY only.",
        "does not broad-scan drives",
        "does not write ALIVE_STATE",
        AUTHORITY,
    ]:
        _require(needle in text, "intake bridge report missing text: " + needle)


def main() -> int:
    checks = [
        ("policy_files", check_policy_files),
        ("helper_static", check_helper_static),
        ("helper_behavior", check_helper_behavior),
        ("report", check_report),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(name + ": " + str(exc))
            print("FAIL " + name + ": " + str(exc))
        except Exception as exc:
            failures.append(name + ": unexpected error: " + str(exc))
            print("FAIL " + name + ": unexpected error: " + str(exc))

    if failures:
        print()
        print("ENGEL_EXTERNAL_MEMORY_INTAKE_BRIDGE_VERIFICATION_FAIL")
        for failure in failures:
            print("- " + failure)
        return 1

    print()
    print("ENGEL_EXTERNAL_MEMORY_INTAKE_BRIDGE_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
