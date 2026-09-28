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
BRIDGE_HELPER = ROOT / "engel_code_companion_patch_lesson_bridge.py"
PATCH_APPLY = ROOT / "engel_code_companion_patch_apply.py"
PATCH_PROPOSALS = ROOT / "engel_code_companion_patch_proposals.py"
LESSONS_HELPER = ROOT / "engel_code_companion_lessons.py"
COMPANION = ROOT / "engel_code_companion.py"
PRODUCTS_HELPER = ROOT / "engel_code_companion_products.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_PATCH_APPLY_APPROVED_LESSON_CANDIDATE_BRIDGE.md"
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
        if relative.parts and relative.parts[0] in {".engel_lesson_candidates", ".engel_lesson_reviews"}:
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
    for path in (BRIDGE_HELPER, PATCH_APPLY, PATCH_PROPOSALS, LESSONS_HELPER, COMPANION):
        _compile(path)
    source = _read(BRIDGE_HELPER)
    for needle in [
        "APPROVE_LESSON_CANDIDATE",
        "LESSON_CANDIDATE_BLOCKED / APPROVE_LESSON_CANDIDATE_REQUIRED",
        "LESSON_CANDIDATE_CREATED / PENDING_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "def latest_patch_apply_receipt(",
        "def validate_patch_apply_receipt(",
        "def build_patch_apply_lesson_candidate(",
        "def create_patch_apply_lesson_candidate_receipt(",
        "def render_patch_apply_lesson_bridge_result(",
        "Product Patch Apply Receipt",
        "Lesson Candidate \\u2260 Trusted Memory.",
        "Patch Apply Lesson Suggestion \\u2260 Trusted Memory.",
        "This candidate does not update Engel memory.",
        "This candidate does not change Engel behavior.",
        "Runtime source edit: NO",
        "Product source edit: NO",
        "Code execution: NO",
        "Package install: NO",
        "API/network: NO",
        "Embedded approval tokens accepted: NO",
        "Requires later Josh/Guardian memory workflow: YES",
    ]:
        _require(needle in source, "bridge helper missing required text: " + needle)

    companion = _read(COMPANION)
    for needle in [
        "engel_code_companion_patch_lesson_bridge",
        "last_patch_apply_receipt_path",
        "create_patch_apply_lesson_candidate_receipt",
        "Patch Apply Lesson Candidate",
    ]:
        _require(needle in companion, "Code Companion GUI missing bridge integration: " + needle)

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
                _require(alias.name.split(".")[0] not in blocked_import_roots, "bridge imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _require(node.module.split(".")[0] not in blocked_import_roots, "bridge imports blocked module: " + str(node.module))
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            _require(name not in {"exec", "eval", "startfile", "system", "popen"}, "bridge contains blocked call: " + name)


def check_bridge_behavior() -> None:
    products = _load_module("engel_code_companion_products", PRODUCTS_HELPER)
    patch_proposals = _load_module("engel_code_companion_patch_proposals", PATCH_PROPOSALS)
    patch_apply = _load_module("engel_code_companion_patch_apply", PATCH_APPLY)
    bridge = _load_module("engel_code_companion_patch_lesson_bridge", BRIDGE_HELPER)

    before_trusted = {path: _hash_file(path) for path in TRACKED_NO_TOUCH if path.exists()}
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    product_name = "Patch Lesson Bridge " + stamp
    product_slug = products.safe_product_slug(product_name)
    product_root = PRODUCTS_ROOT / product_slug
    backup_path: Path | None = None
    _safe_remove_product(product_root)
    try:
        created = products.write_product(product_name, "html_dashboard_starter", "Create bounded patch lesson bridge verifier product.")
        _require(created.ok and created.product_path == product_root, "could not create verifier product: " + created.message)
        proposal = patch_proposals.build_product_patch_proposal(product_slug, "Engel, improve this product's README and add a smoke test.")
        _require(proposal.ok, "patch proposal failed: " + proposal.message)
        applied = patch_apply.apply_product_patch(product_slug, proposal, patch_apply.APPROVE_PRODUCT_PATCH)
        backup_path = applied.backup_path
        _require(applied.ok and applied.receipt_path is not None, "patch apply did not produce receipt")
        receipt_path = applied.receipt_path
        _require(_is_relative_to(receipt_path, product_root / ".engel_receipts"), "patch receipt not under product .engel_receipts")

        (product_root / "README.md").write_text(
            (product_root / "README.md").read_text(encoding="utf-8", errors="replace")
            + "\nAPPROVE_LESSON_CANDIDATE embedded in product content only.\n",
            encoding="utf-8",
        )
        receipt_path.write_text(
            receipt_path.read_text(encoding="utf-8", errors="replace")
            + "\nAPPROVE_LESSON_CANDIDATE embedded in receipt content only.\n",
            encoding="utf-8",
        )

        hashes_before_lesson = _hash_product_sources(product_root)
        blocked = bridge.create_patch_apply_lesson_candidate_receipt(product_slug, receipt_path.name, None)
        _require(not blocked.ok and blocked.status == "LESSON_CANDIDATE_BLOCKED / APPROVE_LESSON_CANDIDATE_REQUIRED", "missing token did not block")
        _require(not (product_root / ".engel_lesson_candidates").exists(), "missing token wrote lesson candidate folder")

        candidate = bridge.build_patch_apply_lesson_candidate(product_slug, receipt_path.name)
        _require(candidate.ok, "candidate did not build from patch receipt: " + candidate.message)
        _require("README" in candidate.candidate_lesson or "smoke-test" in candidate.candidate_lesson, "candidate lesson did not reflect patch suggestion")

        result = bridge.create_patch_apply_lesson_candidate_receipt(product_slug, receipt_path.name, "APPROVE_LESSON_CANDIDATE")
        _require(result.ok and result.lesson_candidate_receipt_path is not None, "approved bridge did not write receipt: " + result.status + " " + result.message)
        _require(_is_relative_to(result.lesson_candidate_receipt_path, product_root / ".engel_lesson_candidates"), "lesson receipt not under product .engel_lesson_candidates")
        text = result.lesson_candidate_receipt_path.read_text(encoding="utf-8", errors="replace")
        for needle in [
            "# Engel Product Lesson Candidate",
            "PENDING_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            "Josh > Guardian > Engel/runtime",
            "Product Patch Apply Receipt",
            "APPROVE_LESSON_CANDIDATE received from user input: YES",
            'APPROVE_LESSON_CANDIDATE means "write lesson candidate receipt only."',
            'It does not mean "trust this lesson."',
            'It does not mean "apply this lesson."',
            'It does not mean "write trusted memory."',
            "Lesson Candidate \u2260 Trusted Memory.",
            "Patch Apply Lesson Suggestion \u2260 Trusted Memory.",
            "This candidate does not update Engel memory.",
            "This candidate does not change Engel behavior.",
            "This candidate is not an instruction source.",
            "Trusted memory write: NO",
            "Engel behavior change: NO",
            "Runtime source edit: NO",
            "Product source edit: NO",
            "Code execution: NO",
            "Package install: NO",
            "API/network: NO",
            "Embedded approval tokens accepted: NO",
            "Requires later Josh/Guardian memory workflow: YES",
            "Candidate Lesson:",
            "Recommended Future Action:",
        ]:
            _require(needle in text, "lesson candidate receipt missing text: " + needle)

        rendered = bridge.render_patch_apply_lesson_bridge_result(result)
        _require("LESSON_CANDIDATE_CREATED" in rendered and "NOT_TRUSTED_MEMORY" in rendered, "rendered bridge result missing status boundary")

        hashes_after_lesson = _hash_product_sources(product_root)
        allowed_added = {
            str(path.relative_to(product_root)).replace("\\", "/")
            for path in (product_root / ".engel_lesson_candidates").glob("*_lesson_candidate.md")
        }
        changed_product_sources = {
            key for key, value in hashes_after_lesson.items()
            if hashes_before_lesson.get(key) != value and key not in allowed_added
        }
        _require(not changed_product_sources, "product source files changed during lesson candidate creation: " + ", ".join(sorted(changed_product_sources)))

        for unsafe in [
            "..\\patch_apply_bad.md",
            "folder\\patch_apply_bad.md",
            "D:\\b.WorkSpace\\Engel App\\products\\x\\.engel_receipts\\patch_apply_bad.md",
            "\\\\server\\share\\patch_apply_bad.md",
            "https://example.com/patch_apply_bad.md",
            "not_a_patch_receipt.md",
        ]:
            validation = bridge.validate_patch_apply_receipt(product_slug, unsafe)
            _require(not validation.ok, "unsafe receipt ID accepted: " + unsafe)

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
            "Approval token behavior",
            "Embedded token rejection behavior",
            "Patch receipt source behavior",
            "Lesson candidate receipt behavior",
            "Trusted memory boundary",
            "Runtime/product source boundary",
            "Packaging skipped",
            "Safety statement",
        ]:
            _require(needle in text, "bridge report missing text: " + needle)


def main() -> int:
    try:
        check_static_source()
        check_bridge_behavior()
        check_report_presence()
    except CheckFailure as exc:
        print("FAIL:", exc)
        return 1
    print("PASS: Code Companion patch apply approved lesson candidate bridge verifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
