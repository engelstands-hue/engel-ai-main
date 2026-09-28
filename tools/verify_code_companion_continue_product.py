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
HELPER = ROOT / "engel_code_companion_continue_product.py"
TALK_HELPER = ROOT / "engel_code_companion_talk_to_code.py"
COMPANION = ROOT / "engel_code_companion.py"
PRODUCTS_HELPER = ROOT / "engel_code_companion_products.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_TALK_TO_CODE_CONTINUE_PRODUCT_FLOW.md"
PRODUCTS_ROOT = ROOT / "products"


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


def _hash_tree(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    if not root.exists():
        return hashes
    for path in root.rglob("*"):
        if path.is_file():
            hashes[str(path.relative_to(root)).replace("\\", "/")] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _safe_remove_product(path: Path) -> None:
    if path.exists():
        _require(_is_relative_to(path, PRODUCTS_ROOT) and path.parent.resolve() == PRODUCTS_ROOT.resolve(), "refusing to clean unbounded product path: " + str(path))
        shutil.rmtree(path)


def check_static_source() -> None:
    for path in (HELPER, TALK_HELPER, COMPANION):
        _compile(path)

    source = _read(HELPER)
    for needle in [
        "CONTINUE_PRODUCT_PLAN",
        "PLAN_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "SELECT_PRODUCT_REQUIRED",
        "BLOCKED_UNSAFE_CONTINUE_PRODUCT_REQUEST",
        "def is_continue_product_request(",
        "def build_continue_product_plan(",
        "def render_continue_product_plan(",
        "cycle_dashboard.build_product_cycle_dashboard",
        "patch_proposals.build_product_patch_proposal",
        "# ENGEL CONTINUE PRODUCT PLAN",
        "Current state:",
        "Recommended next action:",
        "Guardian Review:",
        "Product files changed now: NO",
        "Runtime source edit: NO",
        "Code execution: NO",
        "Package install: NO",
        "API/network: NO",
        "Trusted memory write: NO",
        "Continue Product Plan != Applied Change.",
        "No patches were applied.",
        "No lesson candidates were created.",
        "No trusted memory was written.",
    ]:
        _require(needle in source, "continue product helper missing required text: " + needle)

    talk_source = _read(TALK_HELPER)
    for needle in [
        "engel_code_companion_continue_product",
        "CONTINUE_PRODUCT_PLAN",
        "def _is_continue_product_request(",
        "continue_product.build_continue_product_plan",
        "continue_product.render_continue_product_plan",
        "CONTINUE_PRODUCT_PLAN_ONLY / NOT_APPLIED",
    ]:
        _require(needle in talk_source, "Talk-to-Code helper missing continue-product integration: " + needle)

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
        "write_product",
        "write_text",
        "mkdir",
        "unlink",
        "rmtree",
        "copy",
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
                _require(alias.name.split(".")[0] not in blocked_import_roots, "continue helper imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _require(node.module.split(".")[0] not in blocked_import_roots, "continue helper imports blocked module: " + str(node.module))
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            _require(name not in blocked_calls, "continue helper contains blocked write/execute call: " + name)


def check_continue_behavior() -> None:
    helper = _load_module("engel_code_companion_continue_product", HELPER)
    talk = _load_module("engel_code_companion_talk_to_code", TALK_HELPER)
    products = _load_module("engel_code_companion_products", PRODUCTS_HELPER)

    for phrase in [
        "Engel, continue this product.",
        "What should we do next with this app?",
        "Improve this product's instructions.",
        "Add a small next feature proposal.",
        "Make this product more complete.",
    ]:
        _require(helper.is_continue_product_request(phrase), "continue intent not recognized by helper: " + phrase)
        _require(talk.classify_talk_to_code_intent(phrase).intent_type == "CONTINUE_PRODUCT_PLAN", "Talk-to-Code did not classify continue intent: " + phrase)

    missing = talk.build_talk_to_code_plan("Engel, continue this product.")
    _require(missing.status == "BLOCKED", "missing selected product did not block")
    _require(missing.intent is not None and missing.intent.blocked_reason == "SELECT_PRODUCT_REQUIRED", "missing selected product did not return SELECT_PRODUCT_REQUIRED")
    missing_text = talk.render_talk_to_code_plan(missing)
    _require("SELECT_PRODUCT_REQUIRED" in missing_text, "missing selected product output omitted SELECT_PRODUCT_REQUIRED")

    unsafe = talk.build_talk_to_code_plan("Engel, continue this product and edit Engel runtime, install packages, call an API.")
    _require(unsafe.status == "BLOCKED", "unsafe continue request was not blocked")

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    product_name = "Continue Product Verifier " + stamp
    product_slug = products.safe_product_slug(product_name)
    product_root = PRODUCTS_ROOT / product_slug
    _safe_remove_product(product_root)
    try:
        created = products.write_product(product_name, "html_dashboard_starter", "Create bounded continue product verifier product.")
        _require(created.ok and created.product_path == product_root, "could not create smoke product: " + created.message)
        before_hashes = _hash_tree(product_root)

        plan = talk.build_talk_to_code_plan("Engel, continue this product.", product_slug)
        rendered = talk.render_talk_to_code_plan(plan)
        _require(plan.status == "PROPOSAL_ONLY", "continue product plan should be proposal-only")
        _require(plan.target_type == "CONTINUE_PRODUCT_PLAN", "continue product target type mismatch")
        for needle in [
            "# ENGEL CONTINUE PRODUCT PLAN",
            "PLAN_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            "Selected product:",
            product_slug,
            "Current state:",
            "- Health:",
            "- Patch proposal:",
            "- Patch apply receipt:",
            "- Lesson suggestion:",
            "- Lesson candidates:",
            "- Lesson reviews:",
            "- Trusted memory: BLOCKED / NOT_PERFORMED",
            "Recommended next action:",
            "Guardian Review:",
            "Product files changed now: NO",
            "Runtime source edit: NO",
            "Code execution: NO",
            "Package install: NO",
            "API/network: NO",
            "Trusted memory write: NO",
            "Approval required before apply: YES",
            "Continue Product Plan != Applied Change.",
            "No patches were applied.",
            "No lesson candidates were created.",
            "No trusted memory was written.",
        ]:
            _require(needle in rendered, "continue product plan missing text: " + needle)

        patch_plan = talk.build_talk_to_code_plan("Improve this product's instructions.", product_slug)
        patch_text = talk.render_talk_to_code_plan(patch_plan)
        _require(patch_plan.target_type == "CONTINUE_PRODUCT_PLAN", "instruction request did not stay in continue product flow")
        _require("Patch proposal preview:" in patch_text, "continue flow did not route to patch proposal preview")
        _require("# ENGEL PRODUCT PATCH PROPOSAL" in patch_text, "patch proposal preview missing")
        _require("PATCH_PROPOSAL_ONLY / NOT_APPLIED / PRODUCT_ONLY / NOT_TRUSTED_MEMORY" in patch_text, "patch proposal boundary missing")

        feature_plan = helper.build_continue_product_plan("Add a small next feature proposal.", product_slug)
        _require(feature_plan.ok and feature_plan.action_kind == "product_plan_extension", "next feature request did not route to product plan extension")
        feature_text = helper.render_continue_product_plan(feature_plan)
        _require("product_plan_extension" in feature_text, "product plan extension output missing action kind")

        result = talk.execute_talk_to_code_plan(plan)
        _require(not result.ok, "continue product execute unexpectedly applied work")
        _require(result.status == "CONTINUE_PRODUCT_PLAN_ONLY / NOT_APPLIED", "continue product execute status mismatch")
        _require(not result.files_written, "continue product execute wrote files")
        _require("# ENGEL CONTINUE PRODUCT PLAN" in result.output, "continue product execute output missing plan")

        after_hashes = _hash_tree(product_root)
        _require(before_hashes == after_hashes, "continue product flow modified product files")
    finally:
        _safe_remove_product(product_root)


def check_report_presence() -> None:
    if REPORT.exists():
        text = _read(REPORT)
        for needle in [
            "Status: COMPLETE",
            "Continue Product Plan",
            "PLAN_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            "SELECT_PRODUCT_REQUIRED",
            "Patch proposal",
            "Packaging skipped",
            "Safety statement",
        ]:
            _require(needle in text, "continue product report missing text: " + needle)


def main() -> int:
    try:
        check_static_source()
        check_continue_behavior()
        check_report_presence()
    except CheckFailure as exc:
        print("FAIL:", exc)
        return 1
    print("PASS: Talk-to-Code Continue Product flow verifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
