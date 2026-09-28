from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "engel_self_fix_receipt_viewer.py"
VERIFIER = ROOT / "tools" / "verify_engel_self_fix_receipt_viewer.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_SELF_FIX_RECEIPT_VIEWER_V1.md"
RECEIPT_DIR = ROOT / "reports" / "self_fix_receipts"

REQUIRED_STATUSES = [
    "READ_ONLY_RECEIPT_VIEWER",
    "SELF_FIX_RECEIPTS_ONLY",
    "LOCAL_ONLY",
    "BOUNDED_REPORTS_ONLY",
    "NO_RECEIPT_MUTATION",
    "NO_FIX_EXECUTION",
    "NO_APPLY",
    "NO_COMMIT",
    "NO_SOURCE_MUTATION",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
]

REQUIRED_FIELDS = [
    "self_fix_run_id",
    "issue_detected",
    "classification",
    "allowed_low_risk_class",
    "mode",
    "files_changed",
    "patch_summary",
    "verification_commands",
    "verification_result",
    "safety_scan_result",
    "commit_hash",
    "rollback_notes",
    "stopped",
    "stop_reason",
    "human_intervention_required",
    "no_trusted_memory_write",
    "no_provider_network_browser",
    "no_background_worker",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_viewer() -> str:
    return VIEWER.read_text(encoding="utf-8", errors="replace")


def load_viewer():
    spec = importlib.util.spec_from_file_location("engel_self_fix_receipt_viewer", VIEWER)
    require(spec is not None and spec.loader is not None, "could not load receipt viewer module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_self_fix_receipt_viewer"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [VIEWER, VERIFIER, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))
    require(RECEIPT_DIR.exists() and RECEIPT_DIR.is_dir(), "bounded receipt folder missing")


def check_required_text() -> None:
    text = read_viewer() + "\n" + REPORT.read_text(encoding="utf-8", errors="replace")
    for needle in REQUIRED_STATUSES + REQUIRED_FIELDS:
        require(needle in text, "viewer missing required status/field: " + needle)
    for needle in [
        "--list",
        "--show",
        "reports\\self_fix_receipts",
        "non-recursive receipt count",
        "reads only `reports\\self_fix_receipts",
        "does not edit receipts",
        "delete receipts",
        "write receipts",
        "execute fixes",
        "apply patches",
        "commit changes",
        "write trusted memory",
        "call providers",
        "recursively scan folders",
        "background workers",
        "read-only",
    ]:
        require(needle in text, "viewer missing boundary or CLI text: " + needle)


def check_report_text() -> None:
    text = REPORT.read_text(encoding="utf-8", errors="replace")
    for needle in [
        "Engel Self-Fix Receipt Viewer V1",
        "Files Read First",
        "Files Created",
        "Viewer Behavior",
        "Read-Only Boundary",
        "Verification Results",
        "Smoke Result",
        "Focused Safety Scan",
        "Final Scoped Process Sweep",
        "Git Status Summary",
        "python engel_self_fix_receipt_viewer.py --list",
        "python engel_self_fix_receipt_viewer.py --show <receipt-file-name>",
    ]:
        require(needle in text, "receipt viewer report missing text: " + needle)


def check_forbidden_active_behavior() -> None:
    tree = ast.parse(read_viewer())
    forbidden_imports = {
        "requests",
        "urllib",
        "socket",
        "webbrowser",
        "openai",
        "subprocess",
        "glob",
        "shutil",
        "threading",
        "multiprocessing",
        "ctypes",
    }
    forbidden_calls = {"exec", "eval", "__import__"}
    forbidden_attributes = {
        "walk",
        "rglob",
        "glob",
        "unlink",
        "remove",
        "rmdir",
        "rename",
        "replace",
        "write_text",
        "mkdir",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                require(root_name not in forbidden_imports, "viewer imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".")[0]
            require(root_name not in forbidden_imports, "viewer imports forbidden module: " + node.module)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in forbidden_calls, "viewer uses forbidden dynamic call: " + node.func.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in forbidden_attributes, "viewer uses forbidden scan/mutation call: " + node.func.attr)


def check_runtime_smoke() -> None:
    module = load_viewer()
    out = io.StringIO()
    err = io.StringIO()
    require(module.main([], stdout=out, stderr=err) == 0, "viewer no-argument usage failed")
    require("READ_ONLY_RECEIPT_VIEWER" in out.getvalue(), "usage output missing receipt viewer status")

    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--list"], stdout=out, stderr=err) == 0, "viewer --list failed")
    output = out.getvalue()
    for needle in [
        "Engel Self-Fix Receipt Viewer V1",
        "READ_ONLY_RECEIPT_VIEWER",
        "SELF_FIX_RECEIPTS_ONLY",
        "reports\\self_fix_receipts\\",
        "non-recursive receipt count",
        "does not edit receipts",
        "does not edit receipts, delete receipts, write receipts",
    ]:
        require(needle in output, "viewer --list output missing: " + needle)

    for unsafe in [
        "https://example.com/receipt.md",
        "\\\\server\\share\\receipt.md",
        "..\\outside.md",
        "memory\\receipt.md",
        "receipt*.md",
        "G:\\ENGEL_APP_MEMORY\\receipt.md",
    ]:
        try:
            module.resolve_receipt_path(unsafe)
        except module.SelfFixReceiptViewerError:
            continue
        raise CheckFailure("viewer accepted unsafe receipt name: " + unsafe)


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_report_text()
        check_forbidden_active_behavior()
        check_runtime_smoke()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel self-fix receipt viewer verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
