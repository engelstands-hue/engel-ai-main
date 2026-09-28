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
REVIEW_HELPER = ROOT / "engel_code_companion_patch_lesson_review.py"
LESSON_REVIEW_HELPER = ROOT / "engel_code_companion_lesson_review.py"
PATCH_BRIDGE_HELPER = ROOT / "engel_code_companion_patch_lesson_bridge.py"
PATCH_APPLY_HELPER = ROOT / "engel_code_companion_patch_apply.py"
PATCH_PROPOSALS_HELPER = ROOT / "engel_code_companion_patch_proposals.py"
PRODUCTS_HELPER = ROOT / "engel_code_companion_products.py"
COMPANION = ROOT / "engel_code_companion.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_PATCH_LESSON_CANDIDATE_REVIEW_INTEGRATION.md"
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


def _hash_product_sources(product_root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in product_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(product_root)
        if relative.parts and relative.parts[0] == ".engel_lesson_reviews":
            continue
        hashes[str(relative).replace("\\", "/")] = _hash_file(path)
    return hashes


def _safe_remove_product(path: Path) -> None:
    if path.exists():
        _require(_is_relative_to(path, PRODUCTS_ROOT) and path.parent.resolve() == PRODUCTS_ROOT.resolve(), "refusing product cleanup outside products: " + str(path))
        shutil.rmtree(path)


def _safe_remove_backup(path: Path | None) -> None:
    if path and path.exists():
        _require(_is_relative_to(path, BACKUPS_ROOT), "refusing backup cleanup outside code companion backups: " + str(path))
        shutil.rmtree(path)


def check_static_source() -> None:
    for path in (REVIEW_HELPER, LESSON_REVIEW_HELPER, COMPANION):
        _compile(path)
    source = _read(REVIEW_HELPER)
    for needle in [
        "def list_patch_lesson_candidates(",
        "def read_patch_lesson_candidate(",
        "def build_patch_lesson_review(",
        "def render_patch_lesson_review(",
        "def write_patch_lesson_review(",
        "READY_FOR_JOSH_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "# Engel Patch Lesson Review",
        "Patch-generated lesson candidate",
        "Lesson Candidate \\u2260 Trusted Memory.",
        "Lesson Review \\u2260 Trusted Memory.",
        "READY_FOR_JOSH_REVIEW \\u2260 Trusted Memory.",
        "This review does not update Engel memory.",
        "This review does not change Engel behavior.",
        "Trusted memory write: NO",
        "Engel behavior change: NO",
        "Runtime source edit: NO",
        "Product source edit: NO",
        "Code execution: NO",
        "Package install: NO",
        "API/network: NO",
        "Requires future Josh/Guardian memory workflow: YES",
        "Keep for future memory-candidate review",
        "Request more product evidence",
        "No automatic action taken",
    ]:
        _require(needle in source, "patch lesson review helper missing required text: " + needle)

    companion = _read(COMPANION)
    for needle in [
        "engel_code_companion_patch_lesson_review",
        "is_patch_lesson_candidate_id",
        "write_patch_lesson_review",
        "Patch Lesson Review",
    ]:
        _require(needle in companion, "Code Companion GUI missing patch lesson review integration: " + needle)

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
                _require(alias.name.split(".")[0] not in blocked_import_roots, "patch lesson review imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _require(node.module.split(".")[0] not in blocked_import_roots, "patch lesson review imports blocked module: " + str(node.module))
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            _require(name not in {"exec", "eval", "startfile", "system", "popen"}, "patch lesson review contains blocked call: " + name)


def check_patch_review_behavior() -> None:
    products = _load_module("engel_code_companion_products", PRODUCTS_HELPER)
    patch_proposals = _load_module("engel_code_companion_patch_proposals", PATCH_PROPOSALS_HELPER)
    patch_apply = _load_module("engel_code_companion_patch_apply", PATCH_APPLY_HELPER)
    patch_bridge = _load_module("engel_code_companion_patch_lesson_bridge", PATCH_BRIDGE_HELPER)
    patch_review = _load_module("engel_code_companion_patch_lesson_review", REVIEW_HELPER)
    lesson_review = _load_module("engel_code_companion_lesson_review", LESSON_REVIEW_HELPER)

    before_trusted = {path: _hash_file(path) for path in TRACKED_NO_TOUCH if path.exists()}
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    product_name = "Patch Lesson Review " + stamp
    product_slug = products.safe_product_slug(product_name)
    product_root = PRODUCTS_ROOT / product_slug
    backup_path: Path | None = None
    _safe_remove_product(product_root)
    try:
        created = products.write_product(product_name, "html_dashboard_starter", "Create bounded patch lesson review verifier product.")
        _require(created.ok and created.product_path == product_root, "could not create verifier product: " + created.message)
        proposal = patch_proposals.build_product_patch_proposal(product_slug, "Engel, improve this product's README and add a smoke test.")
        _require(proposal.ok, "patch proposal failed: " + proposal.message)
        applied = patch_apply.apply_product_patch(product_slug, proposal, patch_apply.APPROVE_PRODUCT_PATCH)
        backup_path = applied.backup_path
        _require(applied.ok and applied.receipt_path is not None, "patch apply did not produce receipt")
        bridge_result = patch_bridge.create_patch_apply_lesson_candidate_receipt(product_slug, applied.receipt_path.name, "APPROVE_LESSON_CANDIDATE")
        _require(bridge_result.ok and bridge_result.lesson_candidate_receipt_path is not None, "patch lesson candidate was not created")

        summaries = patch_review.list_patch_lesson_candidates(product_slug)
        _require(len(summaries) == 1, "patch lesson candidate listing did not find exactly one candidate")
        candidate_id = summaries[0].candidate_id
        read_result = patch_review.read_patch_lesson_candidate(candidate_id)
        _require(read_result.ok and read_result.source_patch_receipt_path == applied.receipt_path, "patch lesson candidate read/source mismatch")

        hashes_before_review = _hash_product_sources(product_root)
        review = patch_review.build_patch_lesson_review(candidate_id)
        _require(review.ok, "patch lesson review did not build: " + review.message)
        rendered = patch_review.render_patch_lesson_review(review)
        for needle in [
            "# Engel Patch Lesson Review",
            "READY_FOR_JOSH_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            "Josh > Guardian > Engel/runtime",
            "Patch-generated lesson candidate",
            "Lesson Candidate \u2260 Trusted Memory.",
            "Lesson Review \u2260 Trusted Memory.",
            "READY_FOR_JOSH_REVIEW \u2260 Trusted Memory.",
            "This review does not update Engel memory.",
            "This review does not change Engel behavior.",
            "Trusted memory write: NO",
            "Engel behavior change: NO",
            "Runtime source edit: NO",
            "Product source edit: NO",
            "Code execution: NO",
            "Package install: NO",
            "API/network: NO",
            "Requires future Josh/Guardian memory workflow: YES",
            "Keep for future memory-candidate review",
            "Reject",
            "Request more product evidence",
            "Request another product patch",
            "No automatic action taken",
        ]:
            _require(needle in rendered, "patch lesson review output missing text: " + needle)

        write_result = patch_review.write_patch_lesson_review(candidate_id)
        _require(write_result.ok and write_result.review_path is not None, "patch lesson review was not written")
        _require(_is_relative_to(write_result.review_path, product_root / ".engel_lesson_reviews"), "review path escaped product review folder")
        _require(lesson_review.is_safe_lesson_review_path(write_result.review_path), "review path failed existing lesson review safety check")
        review_text = write_result.review_path.read_text(encoding="utf-8", errors="replace")
        _require("# Engel Patch Lesson Review" in review_text, "written review did not use patch review renderer")
        _require("READY_FOR_JOSH_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED" in review_text, "written review missing status")

        hashes_after_review = _hash_product_sources(product_root)
        _require(hashes_before_review == hashes_after_review, "product files changed during patch lesson review")

        generic_summary = lesson_review.build_lesson_review_summary(candidate_id)
        _require(generic_summary.ok, "existing lesson review summary did not handle patch-generated candidate")

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
            "Patch lesson candidate listing",
            "Lesson Review behavior",
            "READY_FOR_JOSH_REVIEW",
            "Trusted memory boundary",
            "Runtime/product source boundary",
            "Verification results",
            "GUI smoke results",
            "Packaging skipped",
            "Safety statement",
        ]:
            _require(needle in text, "patch lesson review report missing text: " + needle)


def main() -> int:
    try:
        check_static_source()
        check_patch_review_behavior()
        check_report_presence()
    except CheckFailure as exc:
        print("FAIL:", exc)
        return 1
    print("PASS: Code Companion patch lesson candidate review verifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
