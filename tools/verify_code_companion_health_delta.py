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
HEALTH_DELTA_HELPER = ROOT / "engel_code_companion_health_delta.py"
PATCH_APPLY_HELPER = ROOT / "engel_code_companion_patch_apply.py"
PATCH_PROPOSALS_HELPER = ROOT / "engel_code_companion_patch_proposals.py"
PRODUCTS_HELPER = ROOT / "engel_code_companion_products.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_PATCH_HEALTH_DELTA.md"
PRODUCTS_ROOT = ROOT / "products"
BACKUPS_ROOT = ROOT / "backups" / "code_companion"
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


def _safe_remove_product(path: Path) -> None:
    if path.exists():
        _require(_is_relative_to(path, PRODUCTS_ROOT) and path.parent.resolve() == PRODUCTS_ROOT.resolve(), "refusing product cleanup outside products: " + str(path))
        shutil.rmtree(path)


def _safe_remove_backup(path: Path | None) -> None:
    if path and path.exists():
        _require(_is_relative_to(path, BACKUPS_ROOT), "refusing backup cleanup outside code companion backups: " + str(path))
        shutil.rmtree(path)


def check_static_source() -> None:
    for path in (HEALTH_DELTA_HELPER, PATCH_APPLY_HELPER):
        _compile(path)
    source = _read(HEALTH_DELTA_HELPER)
    for needle in [
        "REPORT_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "def capture_product_health_snapshot(",
        "products.product_health_check",
        "def build_product_health_delta(",
        "def render_product_health_delta(",
        "def write_product_health_delta_report(",
        "# Product Patch Health Delta",
        "Before:",
        "After:",
        "Delta:",
        "improved",
        "unchanged",
        "needs review",
        "Product code execution: NO",
        "Runtime edit: NO",
        "Trusted memory write: NO",
        "Lesson applied: NO",
        "Health Delta \\u2260 Trusted Memory.",
        "Health Delta \\u2260 Lesson.",
        "Health Delta does not apply changes.",
    ]:
        _require(needle in source, "health delta helper missing required text: " + needle)
    apply_source = _read(PATCH_APPLY_HELPER)
    for needle in [
        "engel_code_companion_health_delta",
        "health_delta.capture_product_health_snapshot",
        "health_delta.build_product_health_delta",
        "health_delta.write_product_health_delta_report",
        "health_delta_path",
        "health_delta_status",
    ]:
        _require(needle in apply_source, "patch apply missing health delta integration: " + needle)

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
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _require(alias.name.split(".")[0] not in blocked_import_roots, "health delta imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _require(node.module.split(".")[0] not in blocked_import_roots, "health delta imports blocked module: " + str(node.module))
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            _require(name not in {"exec", "eval", "startfile", "system", "popen", "run", "check_call", "check_output"}, "health delta contains blocked execute call: " + name)


def check_delta_behavior() -> None:
    products = _load_module("engel_code_companion_products", PRODUCTS_HELPER)
    patch_proposals = _load_module("engel_code_companion_patch_proposals", PATCH_PROPOSALS_HELPER)
    health_delta = _load_module("engel_code_companion_health_delta", HEALTH_DELTA_HELPER)
    patch_apply = _load_module("engel_code_companion_patch_apply", PATCH_APPLY_HELPER)

    before_trusted = {path: _hash_file(path) for path in TRACKED_NO_TOUCH if path.exists()}
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    product_name = "Health Delta Verifier " + stamp
    product_slug = products.safe_product_slug(product_name)
    product_root = PRODUCTS_ROOT / product_slug
    backup_path: Path | None = None
    _safe_remove_product(product_root)
    try:
        created = products.write_product(product_name, "html_dashboard_starter", "Create bounded health delta verifier product.")
        _require(created.ok and created.product_path == product_root, "could not create verifier product: " + created.message)

        before = health_delta.capture_product_health_snapshot(product_slug)
        _require(before.product_slug == product_slug and before.item_statuses, "before health snapshot was not captured")
        proposal = patch_proposals.build_product_patch_proposal(product_slug, "Engel, improve this product's README and add a smoke test.")
        _require(proposal.ok, "patch proposal failed: " + proposal.message)
        applied = patch_apply.apply_product_patch(product_slug, proposal, patch_apply.APPROVE_PRODUCT_PATCH)
        backup_path = applied.backup_path
        _require(applied.ok, "patch apply failed: " + applied.status + " " + applied.message)
        _require(applied.health_delta_path is not None and applied.health_delta_path.exists(), "health delta report was not written by patch apply")
        _require(_is_relative_to(applied.health_delta_path, product_root / ".engel_receipts"), "health delta report escaped product receipts")

        after = health_delta.capture_product_health_snapshot(product_slug)
        _require(after.product_slug == product_slug and after.item_statuses, "after health snapshot was not captured")
        delta = health_delta.build_product_health_delta(product_slug, before, after)
        _require(delta.ok, "health delta did not build: " + delta.message)
        rendered = health_delta.render_product_health_delta(delta)
        for needle in [
            "# Product Patch Health Delta",
            "REPORT_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            "Josh > Guardian > Engel/runtime",
            "Before:",
            "After:",
            "Delta:",
            "Recommended next safe action:",
            "Product code execution: NO",
            "Runtime edit: NO",
            "Trusted memory write: NO",
            "Lesson applied: NO",
            "Health Delta \u2260 Trusted Memory.",
            "Health Delta \u2260 Lesson.",
            "Health Delta does not apply changes.",
            "No product code was executed.",
            "No trusted memory was written.",
        ]:
            _require(needle in rendered, "rendered health delta missing text: " + needle)
        _require(delta.delta_status in {"improved", "unchanged", "needs review"}, "unexpected delta status")

        written_text = applied.health_delta_path.read_text(encoding="utf-8", errors="replace")
        _require("# Product Patch Health Delta" in written_text, "written health delta missing title")
        _require("REPORT_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED" in written_text, "written health delta missing status")

        receipt_text = applied.receipt_path.read_text(encoding="utf-8", errors="replace") if applied.receipt_path else ""
        _require("Health Delta:" in receipt_text, "patch apply receipt missing health delta section")
        _require("Health Delta \u2260 Trusted Memory." in receipt_text, "patch apply receipt missing health delta boundary")

        after_trusted = {path: _hash_file(path) for path in TRACKED_NO_TOUCH if path.exists()}
        _require(before_trusted == after_trusted, "trusted memory/system prompt files changed")
    finally:
        _safe_remove_product(product_root)
        _safe_remove_backup(backup_path)


def check_report_presence() -> None:
    if REPORT.exists():
        text = _read(REPORT)
        for needle in [
            "Status: COMPLETE",
            "Product Patch Health Delta",
            "REPORT_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            "Health Delta \u2260 Trusted Memory",
            "Health Delta \u2260 Lesson",
            "No product code execution",
            "Packaging skipped",
        ]:
            _require(needle in text, "report missing required text: " + needle)


def main() -> int:
    try:
        check_static_source()
        check_delta_behavior()
        check_report_presence()
    except CheckFailure as exc:
        print("FAIL:", exc)
        return 1
    print("PASS: Code Companion patch health delta verifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
