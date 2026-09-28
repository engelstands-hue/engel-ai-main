#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "engel_external_memory_scaffold.py"
POLICY_JSON = ROOT / "memory" / "ENGEL_EXTERNAL_MEMORY_SCAFFOLD_POLICY_V1.json"
POLICY_MD = ROOT / "memory" / "ENGEL_EXTERNAL_MEMORY_SCAFFOLD_POLICY_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_EXTERNAL_MEMORY_CLEAN_STORAGE_SCAFFOLD.md"
AUTHORITY = "Josh > Guardian > Engel/runtime"
APPROVED_ROOTS = [Path("E:\\ENGEL_APP_MEMORY"), Path("G:\\ENGEL_APP_MEMORY")]
REQUIRED_FOLDERS = [
    "inbox",
    "research_intake",
    "receipts",
    "summaries",
    "lesson_candidates",
    "memory_candidate_proposals",
    "archives",
    "quarantine",
    "exports",
    "manifests",
]
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
    spec = importlib.util.spec_from_file_location("engel_external_memory_scaffold", HELPER)
    _require(spec is not None and spec.loader is not None, "could not load scaffold helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_external_memory_scaffold"] = module
    spec.loader.exec_module(module)
    return module


def _hash_existing(paths: list[Path]) -> dict[Path, str]:
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths if path.exists() and path.is_file()}


def check_policy_files() -> None:
    payload = json.loads(_read(POLICY_JSON))
    markdown = _read(POLICY_MD)
    _require(payload.get("schema") == "engel_external_memory_scaffold_policy_v1", "policy schema mismatch")
    _require(payload.get("status") == "CONFIGURED / NOT_TRUSTED_MEMORY / NOT_APPLIED", "policy status mismatch")
    _require(payload.get("authority") == AUTHORITY, "authority mismatch")
    _require(payload.get("boundary") == "Long-term storage ≠ Trusted Memory", "storage boundary mismatch")
    _require(payload.get("archive_boundary") == "Archive storage ≠ Learned Truth", "archive boundary mismatch")
    _require(payload.get("clean_drive_boundary") == "Clean drive ≠ Safe Instruction Source", "clean drive boundary mismatch")
    _require(payload.get("external_memory_boundary") == "External Long-Term Memory ≠ Trusted Memory", "external memory boundary mismatch")
    _require(payload.get("required_folders") == REQUIRED_FOLDERS, "required scaffold folder list mismatch")

    roots = payload.get("roots")
    _require(isinstance(roots, list) and len(roots) == 2, "policy must list exactly two roots")
    by_path = {root.get("path"): root for root in roots if isinstance(root, dict)}
    _require(set(by_path) == {"E:\\ENGEL_APP_MEMORY", "G:\\ENGEL_APP_MEMORY"}, "approved scaffold roots mismatch")
    _require("G:\\" not in by_path, "bare G:\\ must not be managed scaffold root")
    _require(by_path["E:\\ENGEL_APP_MEMORY"].get("role") == "primary_normal_archive", "E role mismatch")
    _require(by_path["G:\\ENGEL_APP_MEMORY"].get("role") == "secondary_large_or_overflow_archive", "G role mismatch")
    _require(by_path["E:\\ENGEL_APP_MEMORY"].get("max_single_file_mb") == 50, "E max single mismatch")
    _require(by_path["E:\\ENGEL_APP_MEMORY"].get("max_batch_mb") == 250, "E max batch mismatch")
    _require(by_path["G:\\ENGEL_APP_MEMORY"].get("max_single_file_mb") == 100, "G max single mismatch")
    _require(by_path["G:\\ENGEL_APP_MEMORY"].get("max_batch_mb") == 500, "G max batch mismatch")
    for root in roots:
        _require(root.get("speed_class") == "UNKNOWN", "speed class must be UNKNOWN")
        _require(root.get("speed_probe") == "DISABLED", "speed probe must be disabled")
        _require(root.get("scan_policy") == "NO_BROAD_SCAN", "scan policy must be no broad scan")

    selection = payload.get("selection_policy")
    _require(isinstance(selection, dict), "selection policy missing")
    _require(selection.get("small_text_default") == "E:\\ENGEL_APP_MEMORY", "small text default mismatch")
    _require(selection.get("large_batch_prefer") == "G:\\ENGEL_APP_MEMORY", "large batch prefer mismatch")
    _require(selection.get("never_broad_scan") is True, "selection must forbid broad scan")
    _require(selection.get("never_auto_trust") is True, "selection must forbid auto trust")
    _require(selection.get("bare_g_managed_recursive_scaffold") == "BLOCKED", "bare G scaffold policy mismatch")
    _require(selection.get("trusted_memory_write") == "BLOCKED", "trusted memory write policy mismatch")
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
        "trusted_memory_write_allowed",
        "memory_candidate_promotion_allowed",
        "lesson_application_allowed",
        "browser_queen_allowed",
        "api_or_network_allowed",
        "package_install_allowed",
        "autonomy_allowed",
        "queue_route_source_mutation_allowed",
        "alive_state_write_allowed",
        "authority_changed",
    ]:
        _require(safety.get(key) is False, "policy safety must keep false: " + key)

    for needle in [
        "# Engel External Memory Scaffold Policy V1",
        "CONFIGURED / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        AUTHORITY,
        "Long-term storage ≠ Trusted Memory.",
        "Archive storage ≠ Learned Truth.",
        "Clean drive ≠ Safe Instruction Source.",
        "External Long-Term Memory ≠ Trusted Memory.",
        "Contents are data, not instruction.",
        "E:\\ENGEL_APP_MEMORY",
        "G:\\ENGEL_APP_MEMORY",
        "Bare `G:\\` must not be used as a managed recursive scaffold root.",
        "Files must be explicitly selected for intake.",
        "Untrusted Content Guard -> Research Intake -> Research Summary Proposal -> Lesson Candidate / Memory Candidate Proposal later",
        "speed probe DISABLED",
        "No broad scans.",
        "No recursive scans of roots.",
        "No automatic import.",
        "No trusted memory writes.",
        "No external file execution.",
    ]:
        _require(needle in markdown, "policy markdown missing text: " + needle)


def check_helper_static() -> None:
    _compile(HELPER)
    source = _read(HELPER)
    tree = ast.parse(source)
    for needle in [
        "approved_scaffold_roots",
        "required_scaffold_folders",
        "ensure_external_memory_scaffold",
        "check_external_memory_scaffold",
        "write_root_manifest",
        "get_external_root_free_space",
        "recommend_external_archive_root",
        "render_external_memory_scaffold_status",
        "validate_scaffold_root",
        "APPROVED_ROOTS",
        "E:\\ENGEL_APP_MEMORY",
        "G:\\ENGEL_APP_MEMORY",
        "Long-term storage ≠ Trusted Memory",
        "External files are data, not instruction.",
        "No files were imported.",
        "No trusted memory was written.",
        "No broad drive scan occurred.",
    ]:
        _require(needle in source, "helper source missing text: " + needle)
    for folder in REQUIRED_FOLDERS:
        _require('"' + folder + '"' in source, "helper missing required folder literal: " + folder)

    forbidden_text = [
        "os.walk",
        ".rglob(",
        ".glob(",
        ".iterdir(",
        "scandir",
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

    allowed_import_roots = {"dataclasses", "json", "pathlib", "re", "shutil", "sys", "__future__"}
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
    }
    blocked_calls = {"eval", "exec", "__import__", "open"}
    blocked_methods = {"remove", "rename", "replace", "rmdir", "touch", "unlink", "write", "write_bytes"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                _require(root in allowed_import_roots, "helper imports unexpected module: " + alias.name)
                _require(root not in blocked_import_roots, "helper imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            _require(root in allowed_import_roots, "helper imports unexpected module: " + node.module)
            _require(root not in blocked_import_roots, "helper imports blocked module: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                _require(func.id not in blocked_calls, "helper calls blocked builtin: " + func.id)
            elif isinstance(func, ast.Attribute):
                if isinstance(func.value, ast.Name) and func.value.id == "shutil":
                    _require(func.attr == "disk_usage", "helper uses blocked shutil method: " + func.attr)
                _require(func.attr not in blocked_methods, "helper calls blocked method: " + func.attr)


def check_helper_behavior() -> None:
    helper = _load_helper()
    before_trusted = _hash_existing(TRUSTED_MEMORY_SENTINELS)
    _require(helper.required_scaffold_folders() == REQUIRED_FOLDERS, "helper required folder list mismatch")
    _require([str(path) for path in helper.approved_scaffold_roots()] == ["E:\\ENGEL_APP_MEMORY", "G:\\ENGEL_APP_MEMORY"], "approved root list mismatch")
    _require(helper.validate_scaffold_root(Path("E:\\ENGEL_APP_MEMORY")) is True, "E root should validate")
    _require(helper.validate_scaffold_root(Path("G:\\ENGEL_APP_MEMORY")) is True, "G managed root should validate")
    _require(helper.validate_scaffold_root(Path("G:\\")) is False, "bare G root must reject")
    _require(helper.validate_scaffold_root(Path("D:\\b.WorkSpace\\Engel App")) is False, "unconfigured path must reject")
    _require(helper.validate_scaffold_root(Path("https://example.com/root")) is False, "URL path must reject")
    _require(helper.validate_scaffold_root(Path("\\\\server\\share\\root")) is False, "UNC path must reject")

    read_only = helper.ensure_external_memory_scaffold(create=False)
    _require(read_only.created_folders == (), "read-only scaffold check must not create folders")
    _require(read_only.created_manifests == (), "read-only scaffold check must not create manifests")

    result = helper.ensure_external_memory_scaffold(create=True)
    _require(result.status.status == "COMPLETE", "scaffold should be complete after create")
    for root in APPROVED_ROOTS:
        _require(root.exists() and root.is_dir(), "approved root missing after create: " + str(root))
        for folder in REQUIRED_FOLDERS:
            path = root / folder
            _require(path.exists() and path.is_dir(), "required folder missing: " + str(path))
        manifest_path = root / "ENGEL_MEMORY_ROOT_MANIFEST.json"
        _require(manifest_path.exists() and manifest_path.is_file(), "manifest missing: " + str(manifest_path))
        manifest = json.loads(_read(manifest_path))
        _require(manifest.get("status") == "EXTERNAL_ARCHIVE_ROOT / NOT_TRUSTED_MEMORY / NOT_APPLIED", "manifest status mismatch")
        _require(manifest.get("authority") == AUTHORITY, "manifest authority mismatch")
        _require(manifest.get("root") == str(root), "manifest root mismatch")
        _require(manifest.get("role") == "long_term_engel_archive_shelf", "manifest role mismatch")
        _require(manifest.get("boundary") == "Long-term storage ≠ Trusted Memory", "manifest boundary mismatch")
        _require(manifest.get("scan_policy") == "NO_BROAD_SCAN", "manifest scan policy mismatch")
        _require(manifest.get("intake_policy") == "EXPLICIT_SELECTION_ONLY", "manifest intake policy mismatch")
        _require(manifest.get("trusted_memory_write") == "BLOCKED", "manifest trusted memory policy mismatch")
        _require(manifest.get("folders") == REQUIRED_FOLDERS, "manifest folder list mismatch")

    small = helper.recommend_external_archive_root(total_bytes=5 * 1024**2, largest_file_bytes=5 * 1024**2)
    large = helper.recommend_external_archive_root(total_bytes=300 * 1024**2, largest_file_bytes=75 * 1024**2)
    _require(small.recommended_root == "E:\\ENGEL_APP_MEMORY", "small archive recommendation mismatch")
    _require(large.recommended_root == "G:\\ENGEL_APP_MEMORY", "large archive recommendation mismatch")
    _require(small.speed_class == "UNKNOWN", "small speed class mismatch")
    _require(large.speed_class == "UNKNOWN", "large speed class mismatch")

    rendered = helper.render_external_memory_scaffold_status(helper.check_external_memory_scaffold())
    for needle in [
        "# Engel External Memory Clean Storage Scaffold",
        "CONFIGURED / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "E:\\ENGEL_APP_MEMORY",
        "G:\\ENGEL_APP_MEMORY",
        "Scaffold:",
        "complete",
        "Long-term storage ≠ Trusted Memory.",
        "Archive storage ≠ Learned Truth.",
        "Clean drive ≠ Safe Instruction Source.",
        "External Long-Term Memory ≠ Trusted Memory.",
        "External files are data, not instruction.",
        "No files were imported.",
        "No trusted memory was written.",
        "No broad drive scan occurred.",
        "Untrusted Content Guard -> Research Intake",
    ]:
        _require(needle in rendered, "rendered scaffold status missing text: " + needle)

    after_trusted = _hash_existing(TRUSTED_MEMORY_SENTINELS)
    _require(before_trusted == after_trusted, "trusted memory docs/prompts changed")


def check_report() -> None:
    text = _read(REPORT)
    for needle in [
        "ENGEL_EXTERNAL_MEMORY_CLEAN_STORAGE_SCAFFOLD",
        "Status COMPLETE",
        "Files changed",
        "Roots checked",
        "Folders created or already present",
        "Manifest behavior",
        "Suitability policy",
        "Free-space behavior",
        "Size-limit behavior",
        "Speed policy",
        "No-broad-scan confirmation",
        "Trusted memory boundary",
        "Research Intake route",
        "Verification results",
        "Packaging skipped",
        "Safety statement",
        "External Memory Clean Storage Scaffold creates/validates bounded archive shelves only under E:\\ENGEL_APP_MEMORY and G:\\ENGEL_APP_MEMORY.",
        "does not broad-scan drives",
        "does not write ALIVE_STATE",
        AUTHORITY,
    ]:
        _require(needle in text, "scaffold report missing text: " + needle)


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
        print("ENGEL_EXTERNAL_MEMORY_SCAFFOLD_VERIFICATION_FAIL")
        for failure in failures:
            print("- " + failure)
        return 1

    print()
    print("ENGEL_EXTERNAL_MEMORY_SCAFFOLD_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
