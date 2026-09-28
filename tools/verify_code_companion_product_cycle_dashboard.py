#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import importlib.util
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_HELPER = ROOT / "engel_code_companion_product_cycle_dashboard.py"
COMPANION = ROOT / "engel_code_companion.py"
PRODUCTS_HELPER = ROOT / "engel_code_companion_products.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_PRODUCT_IMPROVEMENT_CYCLE_DASHBOARD.md"
PRODUCTS_ROOT = ROOT / "products"
TRACKED_NO_TOUCH = (
    ROOT / "prompts" / "ENGEL_SYSTEM.md",
    ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md",
    ROOT / "memory" / "ENGEL_CORE_DIRECTION_AND_SAFETY_CONSTITUTION_V1.md",
)


class CheckFailure(Exception):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def _compile(path: Path) -> None:
    try:
        compile(path.read_text(encoding="utf-8-sig", errors="replace"), str(path), "exec")
    except SyntaxError as exc:
        raise CheckFailure("compile failed for " + str(path.relative_to(ROOT)) + ": " + str(exc)) from exc


def _load_module(name: str, path: Path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    _require(spec is not None and spec.loader is not None, "could not load module: " + name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def _hash_tree(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    if not root.exists():
        return hashes
    for path in root.rglob("*"):
        if path.is_file():
            hashes[str(path.relative_to(root)).replace("\\", "/")] = _hash_file(path)
    return hashes


def _safe_remove_product(path: Path) -> None:
    if path.exists():
        _require(_is_relative_to(path, PRODUCTS_ROOT) and path.parent.resolve() == PRODUCTS_ROOT.resolve(), "refusing product cleanup outside products: " + str(path))
        shutil.rmtree(path)


def check_static_source() -> None:
    for path in (DASHBOARD_HELPER, COMPANION):
        _compile(path)
    source = _read(DASHBOARD_HELPER)
    for needle in [
        "READ_ONLY_STATUS / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "BLOCKED / NOT_PERFORMED",
        "Health -> Improve -> Patch Proposal -> Patch Apply -> Lesson Candidate -> Lesson Review",
        "def build_product_cycle_dashboard(",
        "def render_product_cycle_dashboard(",
        "product_health_check",
        "build_product_improvement_proposal",
        "build_product_patch_proposal",
        "latest_patch_apply_receipt",
        "list_lesson_candidate_receipts",
        "Dashboard is read-only.",
        "Dashboard != Trusted Memory.",
        "Dashboard does not apply patches.",
        "Dashboard does not create lessons.",
        "Dashboard does not write trusted memory.",
        "Selected product only.",
        "No broad scans.",
    ]:
        _require(needle in source, "dashboard helper missing required text: " + needle)

    companion = _read(COMPANION)
    for needle in [
        "engel_code_companion_product_cycle_dashboard",
        'QPushButton("Cycle")',
        "def show_product_cycle_dashboard(",
        "Product Improvement Cycle",
        "Product cycle: READ ONLY / NOT TRUSTED MEMORY / NOT APPLIED",
    ]:
        _require(needle in companion, "Code Companion missing product cycle dashboard integration: " + needle)

    blocked_import_roots = {
        "asyncio",
        "httpx",
        "openai",
        "anthropic",
        "requests",
        "socket",
        "urllib",
        "websocket",
        "selenium",
        "playwright",
        "pyautogui",
        "threading",
        "multiprocessing",
        "subprocess",
    }
    blocked_calls = {
        "apply_product_patch",
        "create_patch_apply_lesson_candidate_receipt",
        "write_lesson_review_summary",
        "write_patch_lesson_review",
        "write_product",
        "write_text",
        "mkdir",
        "unlink",
        "rmdir",
        "rmtree",
        "copy",
        "copytree",
        "move",
        "exec",
        "eval",
        "startfile",
        "system",
        "popen",
        "run",
        "check_call",
        "check_output",
    }
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _require(alias.name.split(".")[0] not in blocked_import_roots, "dashboard helper imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _require(node.module.split(".")[0] not in blocked_import_roots, "dashboard helper imports blocked module: " + str(node.module))
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            _require(name not in blocked_calls, "dashboard helper contains blocked write/execute call: " + name)


def check_dashboard_behavior() -> None:
    products = _load_module("engel_code_companion_products", PRODUCTS_HELPER)
    dashboard = _load_module("engel_code_companion_product_cycle_dashboard", DASHBOARD_HELPER)

    before_trusted = {path: _hash_file(path) for path in TRACKED_NO_TOUCH if path.exists()}
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    product_name = "Product Cycle Dashboard " + stamp
    product_slug = products.safe_product_slug(product_name)
    product_root = PRODUCTS_ROOT / product_slug
    _safe_remove_product(product_root)
    try:
        created = products.write_product(product_name, "html_dashboard_starter", "Create bounded product cycle dashboard verifier product.")
        _require(created.ok and created.product_path == product_root, "could not create verifier product: " + created.message)

        before_product = _hash_tree(product_root)
        result = dashboard.build_product_cycle_dashboard(product_slug)
        _require(result.ok, "dashboard did not build for safe product: " + result.message)
        text = dashboard.render_product_cycle_dashboard(result)
        for needle in [
            "# Product Improvement Cycle",
            "READ_ONLY_STATUS / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            "Josh > Guardian > Engel/runtime",
            "Selected product:",
            product_slug,
            "Health -> Improve -> Patch Proposal -> Patch Apply -> Lesson Candidate -> Lesson Review",
            "Health \u2192 Improve \u2192 Patch Proposal \u2192 Patch Apply \u2192 Lesson Candidate \u2192 Lesson Review",
            "- Health:",
            "- Improvement proposal:",
            "- Patch proposal:",
            "- Patch apply receipt:",
            "- Lesson suggestion:",
            "- Lesson candidates:",
            "- Lesson reviews:",
            "BLOCKED / NOT_PERFORMED",
            "Next safe action:",
            "Selected product only.",
            "No broad scans.",
            "Dashboard is read-only.",
            "Dashboard != Trusted Memory.",
            "Dashboard does not apply patches.",
            "Dashboard does not create lessons.",
            "Dashboard does not write trusted memory.",
            "Dashboard does not edit product files.",
            "Dashboard does not execute code.",
        ]:
            _require(needle in text, "dashboard output missing required text: " + needle)
        _require(_hash_tree(product_root) == before_product, "dashboard modified product files")

        for unsafe in ["..\\unsafe", "D:\\b.WorkSpace\\Engel App\\products\\unsafe", "https://example.com/product", "missing product"]:
            blocked = dashboard.build_product_cycle_dashboard(unsafe)
            blocked_text = dashboard.render_product_cycle_dashboard(blocked)
            _require(not blocked.ok, "unsafe/missing product was not blocked: " + unsafe)
            _require("READ_ONLY_STATUS / BLOCKED / NOT_TRUSTED_MEMORY / NOT_APPLIED" in blocked_text, "blocked dashboard missing blocked status")

        after_trusted = {path: _hash_file(path) for path in TRACKED_NO_TOUCH if path.exists()}
        _require(before_trusted == after_trusted, "trusted memory/system prompt files changed")
    finally:
        _safe_remove_product(product_root)


def check_report_presence() -> None:
    if REPORT.exists():
        text = _read(REPORT)
        for needle in [
            "Status: COMPLETE",
            "Product Improvement Cycle Dashboard",
            "READ_ONLY_STATUS / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            "Health -> Improve -> Patch Proposal -> Patch Apply -> Lesson Candidate -> Lesson Review",
            "Dashboard is read-only",
            "Dashboard \u2260 Trusted Memory",
            "Trusted memory: BLOCKED / NOT_PERFORMED",
            "Packaging skipped",
        ]:
            _require(needle in text, "report missing required text: " + needle)


def main() -> int:
    try:
        check_static_source()
        check_dashboard_behavior()
        check_report_presence()
    except CheckFailure as exc:
        print("FAIL:", exc)
        return 1
    print("OK: Product Improvement Cycle dashboard is compact, read-only, product-bounded, and not trusted memory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
