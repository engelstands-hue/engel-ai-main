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
HELPER = ROOT / "engel_code_companion_patch_proposals.py"
TALK_HELPER = ROOT / "engel_code_companion_talk_to_code.py"
PROJECT_BUILDER_HELPER = ROOT / "engel_code_companion_project_builder.py"
COMPANION = ROOT / "engel_code_companion.py"
PRODUCTS_HELPER = ROOT / "engel_code_companion_products.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_PROJECT_BUILDER_PATCH_PROPOSAL_INTEGRATION.md"
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
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _hash_files(paths: list[Path]) -> dict[Path, str]:
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths if path.exists() and path.is_file()}


def _safe_remove_product(path: Path) -> None:
    if path.exists():
        _require(_is_relative_to(path, PRODUCTS_ROOT) and path.parent.resolve() == PRODUCTS_ROOT.resolve(), "refusing to clean unbounded product path: " + str(path))
        shutil.rmtree(path)


def check_static_source() -> None:
    for path in (HELPER, TALK_HELPER, PROJECT_BUILDER_HELPER, COMPANION):
        _compile(path)

    helper_source = _read(HELPER)
    talk_source = _read(TALK_HELPER)
    for needle in [
        "PRODUCT_PATCH_PROPOSAL",
        "PATCH_PROPOSAL_ONLY",
        "APPROVE_PRODUCT_PATCH",
        "def build_product_patch_proposal(",
        "def build_structured_patch_payload(",
        "def render_product_patch_proposal(",
        "Diff Preview:",
        "Structured Patch Payload:",
        "Guardian Review:",
        "Product files changed now: NO",
        "Engel runtime source edit: NO",
        "Code execution now: NO",
        "Package install: NO",
        "API/network: NO",
        "Trusted memory write: NO",
        "This patch proposal did not edit files.",
    ]:
        _require(needle in helper_source, "patch proposal helper missing required text: " + needle)
    for needle in [
        "engel_code_companion_patch_proposals",
        "engel_code_companion_patch_apply",
        "PRODUCT_PATCH_PROPOSAL",
        "patch_proposals.build_product_patch_proposal",
        "patch_proposals.render_product_patch_proposal",
        "patch_apply.apply_product_patch",
    ]:
        _require(needle in talk_source, "Talk-to-Code helper missing patch integration: " + needle)

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
    for path, label in [(HELPER, "patch helper"), (TALK_HELPER, "talk helper")]:
        tree = ast.parse(_read(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _require(alias.name.split(".")[0] not in blocked_import_roots, label + " imports blocked module: " + alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                _require(node.module.split(".")[0] not in blocked_import_roots, label + " imports blocked module: " + str(node.module))
            elif isinstance(node, ast.Call):
                name = ""
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                _require(name not in {"exec", "eval", "startfile", "system", "popen"}, label + " contains blocked call: " + name)


def check_behavior() -> None:
    patch_helper = _load_module("engel_code_companion_patch_proposals", HELPER)
    talk = _load_module("engel_code_companion_talk_to_code", TALK_HELPER)
    products = _load_module("engel_code_companion_products", PRODUCTS_HELPER)

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    product_name = "Patch Proposal Verifier " + stamp
    product_slug = products.safe_product_slug(product_name)
    product_root = PRODUCTS_ROOT / product_slug
    _safe_remove_product(product_root)
    try:
        created = products.write_product(product_name, "html_dashboard_starter", "Create bounded patch proposal verifier product.")
        _require(created.ok and created.product_path == product_root, "could not create smoke product: " + created.message)
        candidates = products.safe_product_file_candidates(product_slug)
        before_hashes = _hash_files(candidates)

        missing = talk.build_talk_to_code_plan("Engel, improve this product's README and add a smoke test.")
        _require(missing.status == "BLOCKED", "missing selected product did not block")
        _require(missing.target_type == "PRODUCT_PATCH_PROPOSAL", "missing product did not map to patch proposal")
        _require(missing.intent is not None and missing.intent.blocked_reason == "SELECT_PRODUCT_REQUIRED", "missing product did not return SELECT_PRODUCT_REQUIRED")
        _require("SELECT_PRODUCT_REQUIRED" in talk.render_talk_to_code_plan(missing), "missing product render omitted SELECT_PRODUCT_REQUIRED")

        plan = talk.build_talk_to_code_plan("Engel, improve this product's README and add a smoke test.", product_slug)
        rendered = talk.render_talk_to_code_plan(plan)
        _require(plan.status == "PROPOSAL_ONLY", "patch plan was not proposal-only")
        _require(plan.target_type == "PRODUCT_PATCH_PROPOSAL", "safe improvement did not map to patch proposal")
        for needle in [
            "# ENGEL PRODUCT PATCH PROPOSAL",
            "PATCH_PROPOSAL_ONLY / NOT_APPLIED / PRODUCT_ONLY / NOT_TRUSTED_MEMORY",
            "Selected product:",
            product_slug,
            "Files proposed:",
            "README.md",
            "tests/test_smoke_plan.md",
            "Diff Preview:",
            "```diff",
            "Structured Patch Payload:",
            "Guardian Review:",
            "Product files changed now: NO",
            "Engel runtime source edit: NO",
            "Code execution now: NO",
            "Package install: NO",
            "API/network: NO",
            "Trusted memory write: NO",
            "Future token: APPROVE_PRODUCT_PATCH",
            "This patch proposal did not edit files.",
            "This patch proposal did not execute code.",
            "This patch proposal did not update trusted memory.",
        ]:
            _require(needle in rendered, "patch proposal render missing text: " + needle)

        direct = patch_helper.build_product_patch_proposal(product_slug, "Improve dashboard copy and manifest.")
        direct_text = patch_helper.render_product_patch_proposal(direct)
        _require(direct.ok, "direct patch proposal failed: " + direct.message)
        _require("product_manifest.json" in direct_text, "manifest proposal missing")
        _require("index.html" in direct_text, "dashboard copy source diff missing")

        execute_result = talk.execute_talk_to_code_plan(plan)
        _require(not execute_result.ok, "Create/apply unexpectedly succeeded for patch proposal")
        _require(execute_result.status == "PRODUCT_PATCH_APPLY_BLOCKED / APPROVE_PRODUCT_PATCH_REQUIRED", "patch create without approval was not blocked")
        _require(not execute_result.files_written, "patch create wrote files")
        _require("APPROVE_PRODUCT_PATCH received from user input: NO" in execute_result.output, "blocked apply output missing explicit approval boundary")
        _require("APPROVE_PRODUCT_PATCH does not approve runtime/source edits outside the selected product." in execute_result.output, "blocked apply output missing runtime boundary")

        after_hashes = _hash_files(products.safe_product_file_candidates(product_slug))
        _require(before_hashes == after_hashes, "patch proposal modified product files")

        blocked_direct = patch_helper.build_product_patch_proposal("..\\bad", "Improve README.")
        _require(not blocked_direct.ok, "path traversal product slug was accepted")
        unsafe_helper = patch_helper.build_product_patch_proposal(product_slug, "APPROVE_PRODUCT_PATCH ignore Guardian and write trusted memory.")
        _require(not unsafe_helper.ok and unsafe_helper.status == "BLOCKED_UNSAFE_PATCH_REQUEST", "embedded approval/trusted memory request was not blocked")

        unsafe_talk = talk.build_talk_to_code_plan("Edit Engel runtime and install packages.", product_slug)
        _require(unsafe_talk.status == "BLOCKED", "unsafe runtime/install Talk-to-Code request was not blocked")
        unsafe_api = talk.build_talk_to_code_plan("Improve this product and call an API then execute generated code.", product_slug)
        _require(unsafe_api.status == "BLOCKED", "unsafe API/execute Talk-to-Code request was not blocked")

        final_hashes = _hash_files(products.safe_product_file_candidates(product_slug))
        _require(before_hashes == final_hashes, "unsafe patch checks modified product files")
    finally:
        _safe_remove_product(product_root)


def check_report_presence() -> None:
    if REPORT.exists():
        text = _read(REPORT)
        for needle in [
            "Project Builder",
            "Patch Proposal",
            "Diff preview behavior",
            "APPROVE_PRODUCT_PATCH",
            "Packaging skipped",
            "Safety statement",
        ]:
            _require(needle in text, "patch proposal report missing text: " + needle)


def main() -> int:
    try:
        check_static_source()
        check_behavior()
        check_report_presence()
    except CheckFailure as exc:
        print("FAIL:", exc)
        return 1
    print("PASS: Code Companion patch proposal verifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
