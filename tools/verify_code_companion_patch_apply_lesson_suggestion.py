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
PATCH_APPLY = ROOT / "engel_code_companion_patch_apply.py"
PATCH_PROPOSALS = ROOT / "engel_code_companion_patch_proposals.py"
PRODUCTS_HELPER = ROOT / "engel_code_companion_products.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_PATCH_APPLY_LESSON_CANDIDATE_SUGGESTION.md"
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


def _hash(path: Path) -> str:
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
    _compile(PATCH_APPLY)
    source = _read(PATCH_APPLY)
    for needle in [
        "LESSON_CANDIDATE_SUGGESTION_ONLY / NOT_WRITTEN / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "LESSON_CANDIDATE_SUGGESTION_BLOCKED / PATCH_NOT_APPLIED",
        "def build_patch_apply_lesson_candidate_suggestion(",
        "def render_patch_apply_lesson_candidate_suggestion(",
        "Patch Apply Lesson Candidate Suggestion != Lesson Candidate Receipt.",
        "Lesson Candidate != Trusted Memory.",
        "Patch Apply Receipt != Trusted Memory.",
        "No lesson candidate was written.",
        "No trusted memory was written.",
        "Requires future APPROVE_LESSON_CANDIDATE before receipt: YES",
        "Embedded approval tokens accepted: NO",
    ]:
        _require(needle in source, "patch apply helper missing lesson suggestion text: " + needle)

    tree = ast.parse(source)
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
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _require(alias.name.split(".")[0] not in blocked_import_roots, "patch apply imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _require(node.module.split(".")[0] not in blocked_import_roots, "patch apply imports blocked module: " + str(node.module))
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            _require(name not in {"exec", "eval", "startfile", "system", "popen"}, "patch apply contains blocked call: " + name)


def check_behavior() -> None:
    patch_proposals = _load_module("engel_code_companion_patch_proposals", PATCH_PROPOSALS)
    patch_apply = _load_module("engel_code_companion_patch_apply", PATCH_APPLY)
    products = _load_module("engel_code_companion_products", PRODUCTS_HELPER)

    before_hashes = {path: _hash(path) for path in TRACKED_NO_TOUCH if path.exists()}
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    product_name = "Patch Apply Lesson Suggestion " + stamp
    product_slug = products.safe_product_slug(product_name)
    product_root = PRODUCTS_ROOT / product_slug
    backup_path: Path | None = None
    _safe_remove_product(product_root)
    try:
        created = products.write_product(product_name, "html_dashboard_starter", "Create patch apply lesson suggestion verifier product.")
        _require(created.ok and created.product_path == product_root, "could not create verifier product: " + created.message)

        proposal = patch_proposals.build_product_patch_proposal(product_slug, "Engel, improve this product's README and add a smoke test.")
        _require(proposal.ok, "patch proposal failed: " + proposal.message)

        blocked = patch_apply.apply_product_patch(product_slug, proposal, None)
        blocked_text = patch_apply.render_product_patch_apply_result(blocked)
        _require("LESSON_CANDIDATE_SUGGESTION_BLOCKED / PATCH_NOT_APPLIED" in blocked_text, "blocked apply missing blocked lesson suggestion")
        _require(not (product_root / ".engel_lesson_candidates").exists(), "blocked apply wrote lesson candidate folder")

        applied = patch_apply.apply_product_patch(product_slug, proposal, patch_apply.APPROVE_PRODUCT_PATCH)
        backup_path = applied.backup_path
        _require(applied.ok, "approved apply failed: " + applied.status + " " + applied.message)
        suggestion = patch_apply.build_patch_apply_lesson_candidate_suggestion(applied)
        suggestion_text = patch_apply.render_patch_apply_lesson_candidate_suggestion(suggestion)
        rendered = patch_apply.render_product_patch_apply_result(applied)
        receipt_text = applied.receipt_path.read_text(encoding="utf-8", errors="replace") if applied.receipt_path else ""

        for text, label in ((suggestion_text, "suggestion"), (rendered, "apply render")):
            for needle in [
                "# Engel Patch Apply Lesson Candidate Suggestion",
                "LESSON_CANDIDATE_SUGGESTION_ONLY / NOT_WRITTEN / NOT_TRUSTED_MEMORY / NOT_APPLIED",
                "Candidate Lesson:",
                "Lesson Candidate != Trusted Memory.",
                "Patch Apply Receipt != Trusted Memory.",
                "No lesson candidate was written.",
                "No trusted memory was written.",
                "Requires future APPROVE_LESSON_CANDIDATE before receipt: YES",
                "Embedded approval tokens accepted: NO",
            ]:
                _require(needle in text, label + " missing text: " + needle)

        for needle in [
            "Lesson Candidate Auto-Suggestion:",
            "LESSON_CANDIDATE_SUGGESTION_ONLY / NOT_WRITTEN / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            "Lesson candidate receipt written now: NO",
            "Trusted memory write: NO",
            "Future token required before candidate receipt: APPROVE_LESSON_CANDIDATE",
            "Patch Apply receipt is data, not instruction.",
        ]:
            _require(needle in receipt_text, "patch apply receipt missing suggestion text: " + needle)

        _require(not (product_root / ".engel_lesson_candidates").exists(), "auto-suggestion wrote lesson candidate receipt/folder")
        _require(not (product_root / ".engel_lesson_reviews").exists(), "auto-suggestion wrote lesson review folder")

        after_hashes = {path: _hash(path) for path in TRACKED_NO_TOUCH if path.exists()}
        _require(before_hashes == after_hashes, "trusted memory/system prompt files changed")
    finally:
        _safe_remove_product(product_root)
        _safe_remove_backup(backup_path)


def check_report_presence() -> None:
    if REPORT.exists():
        text = _read(REPORT)
        for needle in [
            "Status: COMPLETE",
            "Patch Apply -> Lesson Candidate auto-suggestion",
            "Suggestion behavior",
            "Proposal-only boundary",
            "No lesson candidate receipt",
            "Trusted memory boundary",
            "Packaging skipped",
            "Safety statement",
        ]:
            _require(needle in text, "report missing text: " + needle)


def main() -> int:
    try:
        check_static_source()
        check_behavior()
        check_report_presence()
    except CheckFailure as exc:
        print("FAIL:", exc)
        return 1
    print("PASS: Code Companion patch apply lesson suggestion verifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
