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
HELPER = ROOT / "engel_code_companion_product_workbench.py"
COMPANION = ROOT / "engel_code_companion.py"
CYCLE_DASHBOARD = ROOT / "engel_code_companion_product_cycle_dashboard.py"
CONTINUE_HELPER = ROOT / "engel_code_companion_continue_product.py"
PRODUCTS_HELPER = ROOT / "engel_code_companion_products.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_PRODUCT_WORKBENCH_POLISH.md"
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
    for path in (HELPER, COMPANION, CYCLE_DASHBOARD, CONTINUE_HELPER):
        _compile(path)
    source = _read(HELPER)
    for needle in [
        "READ_ONLY_STATUS / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "READ_ONLY_STATUS / BLOCKED / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "BLOCKED / NOT_PERFORMED",
        "Browser Queen: NOT USED",
        "Generated code execution: BLOCKED",
        "Runtime source edit: BLOCKED",
        "def build_product_workbench_status(",
        "def render_product_workbench_status(",
        "def recommend_next_safe_product_action(",
        "def summarize_product_boundaries(",
        "cycle_dashboard.build_product_cycle_dashboard",
        "continue_product.build_continue_product_plan",
        "Selected product:",
        "Next safe action:",
        "Primary flow:",
        "Workbench is read-only.",
        "Workbench != Trusted Memory.",
        "Workbench does not apply patches.",
        "Workbench does not create lesson candidates.",
        "Workbench does not create memory candidates.",
        "Workbench does not edit product files.",
        "Workbench does not execute generated code.",
        "Workbench does not call APIs/network.",
    ]:
        _require(needle in source, "workbench helper missing required text: " + needle)

    companion = _read(COMPANION)
    for needle in [
        "engel_code_companion_product_workbench",
        "product_workbench_label",
        "def update_product_workbench_status(",
        "Selected Product:",
        "Next Safe Action:",
        "Primary Flow:",
        "Trusted Memory BLOCKED",
        "Runtime Source Edit BLOCKED",
        "Generated Code Execution BLOCKED",
        "Browser Queen NOT USED",
    ]:
        _require(needle in companion, "Code Companion missing Product Workbench integration: " + needle)

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
        "write_code_companion_memory_candidate_handoff",
        "write_product",
        "write_text",
        "write_bytes",
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
                _require(alias.name.split(".")[0] not in blocked_import_roots, "workbench imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _require(node.module.split(".")[0] not in blocked_import_roots, "workbench imports blocked module: " + str(node.module))
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            _require(name not in blocked_calls, "workbench helper contains blocked write/execute call: " + name)


def check_workbench_behavior() -> None:
    products = _load_module("engel_code_companion_products", PRODUCTS_HELPER)
    helper = _load_module("engel_code_companion_product_workbench", HELPER)

    before_trusted = {path: _hash_file(path) for path in TRACKED_NO_TOUCH if path.exists()}
    no_product = helper.build_product_workbench_status(None)
    no_product_text = helper.render_product_workbench_status(no_product)
    for needle in [
        "# Engel Product Workbench",
        "READ_ONLY_STATUS / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "NOT_TRUSTED_MEMORY",
        "NOT_APPLIED",
        "Selected product:",
        "NONE",
        "Next safe action:",
        "Describe a product idea or select a product.",
        "Runtime source edit: BLOCKED",
        "Generated code execution: BLOCKED",
        "Trusted memory write: BLOCKED / NOT_PERFORMED",
        "Browser Queen: NOT USED",
        "Workbench is read-only.",
        "Workbench != Trusted Memory.",
    ]:
        _require(needle in no_product_text, "missing no-product workbench text: " + needle)

    for unsafe in ["..\\unsafe", "D:\\b.WorkSpace\\Engel App\\products\\unsafe", "https://example.com/product", "missing product"]:
        blocked = helper.build_product_workbench_status(unsafe)
        blocked_text = helper.render_product_workbench_status(blocked)
        _require(not blocked.ok, "unsafe/missing product was not blocked: " + unsafe)
        _require("READ_ONLY_STATUS / BLOCKED / NOT_TRUSTED_MEMORY / NOT_APPLIED" in blocked_text, "blocked workbench missing blocked status")
        _require("Select a bounded product under products." in blocked.next_safe_action, "blocked workbench missing safe next action")

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    product_name = "Product Workbench " + stamp
    product_slug = products.safe_product_slug(product_name)
    product_root = PRODUCTS_ROOT / product_slug
    _safe_remove_product(product_root)
    try:
        created = products.write_product(product_name, "html_dashboard_starter", "Create bounded product workbench verifier product.")
        _require(created.ok and created.product_path == product_root, "could not create verifier product: " + created.message)
        before_product = _hash_tree(product_root)
        status = helper.build_product_workbench_status(product_slug)
        text = helper.render_product_workbench_status(status)
        for needle in [
            "# Engel Product Workbench",
            "READ_ONLY_STATUS / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            product_slug,
            "Current state:",
            "Health:",
            "Patch:",
            "Lesson suggestion:",
            "Lesson candidates:",
            "Lesson reviews:",
            "Next safe action:",
            "Primary flow:",
            "Talk to Engel -> Plan -> Create/Patch/Review",
            "Runtime source edit: BLOCKED",
            "Generated code execution: BLOCKED",
            "Trusted memory write: BLOCKED / NOT_PERFORMED",
            "Browser Queen: NOT USED",
            "Workbench does not apply patches.",
            "Workbench does not create lesson candidates.",
            "Workbench does not create memory candidates.",
            "Workbench does not edit product files.",
            "Workbench does not execute generated code.",
            "Workbench does not call APIs/network.",
        ]:
            _require(needle in text, "workbench output missing text: " + needle)
        recommendation = helper.recommend_next_safe_product_action(product_slug)
        _require(recommendation, "recommend_next_safe_product_action returned empty text")
        _require("trusted" not in recommendation.lower() or "BLOCKED" in text, "next action must not imply trust")
        _require(_hash_tree(product_root) == before_product, "workbench modified product files")
        after_trusted = {path: _hash_file(path) for path in TRACKED_NO_TOUCH if path.exists()}
        _require(before_trusted == after_trusted, "trusted memory/system prompt files changed")
    finally:
        _safe_remove_product(product_root)


def check_report_presence() -> None:
    if REPORT.exists():
        text = _read(REPORT)
        for needle in [
            "Status COMPLETE",
            "Engel AI Product Workbench polish",
            "READ_ONLY_STATUS / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            "Next safe action",
            "Trusted memory",
            "Browser Queen: NOT USED",
            "Packaging skipped",
            "Safety statement",
        ]:
            _require(needle in text, "workbench report missing text: " + needle)


def main() -> int:
    try:
        check_static_source()
        check_workbench_behavior()
        check_report_presence()
    except CheckFailure as exc:
        print("FAIL:", exc)
        return 1
    print("PASS: Code Companion Product Workbench verifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
