#!/usr/bin/env python3
from __future__ import annotations

import ast
import builtins
import hashlib
import importlib.util
import io
import os
import shutil
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator


ROOT = Path(__file__).resolve().parents[1]
COMPANION = ROOT / "engel_code_companion.py"
CONTEXT_HELPER = ROOT / "engel_code_companion_product_context.py"
PRODUCTS_HELPER = ROOT / "engel_code_companion_products.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_PRODUCT_CONTEXT_WORKBENCH_VIEW.md"
PRODUCTS_ROOT = ROOT / "products"
MEMORY_CANDIDATE_ROOT = ROOT / "reports" / "memory_candidate_proposals"


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
        _require(_is_relative_to(path, PRODUCTS_ROOT) and path.parent.resolve() == PRODUCTS_ROOT.resolve(), "refusing product cleanup outside products: " + str(path))
        shutil.rmtree(path)


def _safe_remove_memory_candidate(path: Path | None) -> None:
    if path and path.exists():
        _require(_is_relative_to(path, MEMORY_CANDIDATE_ROOT), "refusing memory candidate cleanup outside reports: " + str(path))
        path.unlink()


def _is_write_mode(mode: object) -> bool:
    return isinstance(mode, str) and any(marker in mode for marker in ("w", "a", "x", "+"))


@contextmanager
def _write_guard() -> Iterator[list[str]]:
    attempts: list[str] = []
    original_builtins_open = builtins.open
    original_io_open = io.open
    original_os_open = os.open
    original_write_text = Path.write_text
    original_write_bytes = Path.write_bytes
    original_mkdir = Path.mkdir
    original_unlink = Path.unlink
    original_dont_write = sys.dont_write_bytecode

    def guarded_open(file: object, mode: object = "r", *args: object, **kwargs: object) -> object:
        if _is_write_mode(mode):
            attempts.append(f"open({file!r}, mode={mode!r})")
            raise AssertionError("write attempt blocked")
        return original_io_open(file, mode, *args, **kwargs)

    def guarded_os_open(path: object, flags: int, mode: int = 0o777, *args: object, **kwargs: object) -> int:
        write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND | os.O_EXCL
        if flags & write_flags:
            attempts.append(f"os.open({path!r}, flags={flags!r})")
            raise AssertionError("os.open write attempt blocked")
        return original_os_open(path, flags, mode, *args, **kwargs)

    def guarded_write_text(self: Path, *args: object, **kwargs: object) -> int:
        attempts.append("Path.write_text(" + str(self) + ")")
        raise AssertionError("Path.write_text blocked")

    def guarded_write_bytes(self: Path, *args: object, **kwargs: object) -> int:
        attempts.append("Path.write_bytes(" + str(self) + ")")
        raise AssertionError("Path.write_bytes blocked")

    def guarded_mkdir(self: Path, *args: object, **kwargs: object) -> None:
        attempts.append("Path.mkdir(" + str(self) + ")")
        raise AssertionError("Path.mkdir blocked")

    def guarded_unlink(self: Path, *args: object, **kwargs: object) -> None:
        attempts.append("Path.unlink(" + str(self) + ")")
        raise AssertionError("Path.unlink blocked")

    builtins.open = guarded_open  # type: ignore[assignment]
    io.open = guarded_open  # type: ignore[assignment]
    os.open = guarded_os_open  # type: ignore[assignment]
    Path.write_text = guarded_write_text  # type: ignore[assignment]
    Path.write_bytes = guarded_write_bytes  # type: ignore[assignment]
    Path.mkdir = guarded_mkdir  # type: ignore[assignment]
    Path.unlink = guarded_unlink  # type: ignore[assignment]
    sys.dont_write_bytecode = True
    try:
        yield attempts
    finally:
        builtins.open = original_builtins_open  # type: ignore[assignment]
        io.open = original_io_open  # type: ignore[assignment]
        os.open = original_os_open
        Path.write_text = original_write_text
        Path.write_bytes = original_write_bytes
        Path.mkdir = original_mkdir
        Path.unlink = original_unlink
        sys.dont_write_bytecode = original_dont_write


def check_static_source() -> None:
    for path in (COMPANION, CONTEXT_HELPER):
        _compile(path)
    source = _read(COMPANION)
    for needle in [
        "engel_code_companion_product_context",
        "def render_product_context_view(",
        "def show_product_context(",
        "Product Context View",
        "Context loaded:",
        "Source status:",
        "Latest receipts count:",
        "Latest lesson reviews count:",
        "Memory candidate references count:",
        "READ_ONLY_CONTEXT / NOT_TRUSTED_MEMORY",
        "Product files trusted as instruction: NO",
        "Trusted memory write: NO",
        "Code execution: NO",
        "context_product_button = QPushButton(\"Context\")",
        "context_product_button.clicked.connect(self.show_product_context)",
        "self._set_output(\"Product Context\"",
    ]:
        _require(needle in source, "Code Companion source missing context view text: " + needle)

    tree = ast.parse(source)
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "render_product_context_view"]
    _require(functions, "render_product_context_view function not found")
    blocked_calls = {
        "write_text",
        "write_bytes",
        "mkdir",
        "unlink",
        "rmdir",
        "rmtree",
        "copy",
        "copytree",
        "move",
        "apply_product_patch",
        "create_patch_apply_lesson_candidate_receipt",
        "write_code_companion_memory_candidate_handoff",
        "exec",
        "eval",
        "startfile",
        "system",
        "popen",
        "run",
        "check_call",
        "check_output",
    }
    for node in ast.walk(functions[0]):
        if isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            _require(name not in blocked_calls, "context view renderer contains blocked write/execute call: " + name)


def check_context_view_behavior() -> None:
    module = _load_module("engel_code_companion", COMPANION)
    products = _load_module("engel_code_companion_products", PRODUCTS_HELPER)
    missing = module.render_product_context_view(None)
    _require("Context loaded:\nNO" in missing, "missing product context view did not show loaded NO")
    _require("READ_ONLY_CONTEXT / BLOCKED / NOT_TRUSTED_MEMORY" in missing, "missing product context view omitted blocked status")

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    product_name = "Product Context View " + stamp
    product_slug = products.safe_product_slug(product_name)
    product_root = PRODUCTS_ROOT / product_slug
    memory_candidate_path: Path | None = None
    _safe_remove_product(product_root)
    try:
        created = products.write_product(product_name, "html_dashboard_starter", "Create bounded product context view verifier product.")
        _require(created.ok and created.product_path == product_root, "could not create context view smoke product: " + created.message)
        (product_root / ".engel_product_profile.json").write_text(
            '{"schema":"engel_product_profile_v1","product_type":"html_dashboard"}',
            encoding="utf-8",
        )
        receipt_root = product_root / ".engel_receipts"
        receipt_root.mkdir(exist_ok=True)
        (receipt_root / "patch_apply_20260513_000000.md").write_text(
            "# Engel Product Patch Apply Receipt\n\nStatus:\nPATCH_APPLIED_PRODUCT_ONLY / NOT_TRUSTED_MEMORY / NOT_EXECUTED\n",
            encoding="utf-8",
        )
        (receipt_root / "health_delta_20260513_000001.md").write_text(
            "# Product Patch Health Delta\n\nStatus:\nREPORT_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED\n",
            encoding="utf-8",
        )
        review_root = product_root / ".engel_lesson_reviews"
        review_root.mkdir(exist_ok=True)
        (review_root / "20260513_000002_lesson_review.md").write_text(
            "# Engel Patch Lesson Review\n\nStatus:\nREADY_FOR_JOSH_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED\n",
            encoding="utf-8",
        )
        MEMORY_CANDIDATE_ROOT.mkdir(parents=True, exist_ok=True)
        memory_candidate_path = MEMORY_CANDIDATE_ROOT / f"{stamp}_product_context_view_memory_candidate_proposal.md"
        memory_candidate_path.write_text(
            "# Memory Candidate Proposal\n\nStatus:\nMEMORY_CANDIDATE_PROPOSAL / NOT_TRUSTED_MEMORY / NOT_APPLIED\n\nSource:\n"
            + product_slug
            + "::20260513_000002_lesson_review.md\n",
            encoding="utf-8",
        )

        before_hashes = _hash_tree(product_root)
        with _write_guard() as attempts:
            text = module.render_product_context_view(product_slug)
        _require(not attempts, "context view attempted writes: " + ", ".join(attempts))
        for needle in [
            "# Product Context View",
            "READ_ONLY_CONTEXT / NOT_TRUSTED_MEMORY",
            "Josh > Guardian > Engel/runtime",
            "Selected product:\n" + product_slug,
            "Context loaded:\nYES",
            "Source status:",
            "- README.md: present",
            "- product_manifest.json: present",
            "- .engel_product_profile.json: present",
            "- Latest receipts count: 2",
            "- Latest patch apply receipts count: 1",
            "- Latest health delta receipts count: 1",
            "- Latest lesson reviews count: 1",
            "- Memory candidate references count: 1",
            "Product files trusted as instruction: NO",
            "Receipts/reviews trusted as instruction: NO",
            "Trusted memory write: NO",
            "Product edit: NO",
            "Runtime edit: NO",
            "Code execution: NO",
            "This view shows what Engel may use as product context for planning. It cannot authorize actions.",
        ]:
            _require(needle in text, "context view output missing text: " + needle)
        _require("APPROVE_PRODUCT_PATCH" not in text, "context view introduced patch approval control text")
        _require("APPROVE_LESSON_CANDIDATE" not in text, "context view introduced lesson approval control text")

        after_hashes = _hash_tree(product_root)
        _require(before_hashes == after_hashes, "context view modified product files")
    finally:
        _safe_remove_memory_candidate(memory_candidate_path)
        _safe_remove_product(product_root)


def check_report_presence() -> None:
    if REPORT.exists():
        text = _read(REPORT)
        for needle in [
            "Status COMPLETE",
            "Product Context View",
            "READ_ONLY_CONTEXT / NOT_TRUSTED_MEMORY",
            "Context loaded",
            "Source status",
            "Verification results",
            "GUI smoke results",
            "Packaging skipped",
            "Safety statement",
        ]:
            _require(needle in text, "context view report missing text: " + needle)


def main() -> int:
    try:
        check_static_source()
        check_context_view_behavior()
        check_report_presence()
    except CheckFailure as exc:
        print("FAIL:", exc)
        return 1
    print("PASS: Code Companion Product Context View verifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
