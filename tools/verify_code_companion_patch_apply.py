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
APPLY_HELPER = ROOT / "engel_code_companion_patch_apply.py"
PATCH_HELPER = ROOT / "engel_code_companion_patch_proposals.py"
TALK_HELPER = ROOT / "engel_code_companion_talk_to_code.py"
COMPANION = ROOT / "engel_code_companion.py"
PRODUCTS_HELPER = ROOT / "engel_code_companion_products.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_PRODUCT_PATCH_APPLY.md"
PRODUCTS_ROOT = ROOT / "products"
BACKUPS_ROOT = ROOT / "backups" / "code_companion"
AUTHORITY = "Josh > Guardian > Engel/runtime"


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
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_remove_product(path: Path) -> None:
    if path.exists():
        _require(_is_relative_to(path, PRODUCTS_ROOT) and path.parent.resolve() == PRODUCTS_ROOT.resolve(), "refusing to clean product path: " + str(path))
        shutil.rmtree(path)


def _safe_remove_backup(path: Path | None) -> None:
    if path and path.exists():
        _require(_is_relative_to(path, BACKUPS_ROOT), "refusing to clean backup outside code companion backups: " + str(path))
        shutil.rmtree(path)


def check_static_source() -> None:
    for path in (APPLY_HELPER, PATCH_HELPER, TALK_HELPER, COMPANION):
        _compile(path)
    source = _read(APPLY_HELPER)
    for needle in [
        "APPROVE_PRODUCT_PATCH",
        "PRODUCT_PATCH_APPLY_BLOCKED / APPROVE_PRODUCT_PATCH_REQUIRED",
        "PATCH_APPLIED_PRODUCT_ONLY / NOT_TRUSTED_MEMORY / NOT_EXECUTED",
        "engel_code_companion_health_delta",
        "health_delta.capture_product_health_snapshot",
        "health_delta.write_product_health_delta_report",
        "def safe_product_patch_targets(",
        "def create_product_patch_backup(",
        "def apply_product_patch(",
        "def write_product_patch_receipt(",
        "def render_product_patch_apply_result(",
        "def validate_no_runtime_targets(",
        "Product Patch Apply",
        "Runtime source edit: NO",
        "Code execution: NO",
        "Package install: NO",
        "API/network: NO",
        "Trusted memory write: NO",
        "Embedded approval tokens accepted: NO",
        "Health Delta:",
        "Health Delta \\u2260 Trusted Memory.",
        "Health Delta \\u2260 Lesson.",
        "Health Delta does not apply changes.",
    ]:
        _require(needle in source, "patch apply helper missing required text: " + needle)
    patch_source = _read(PATCH_HELPER)
    _require("def build_structured_patch_payload(" in patch_source, "patch proposal helper missing structured payload builder")
    talk_source = _read(TALK_HELPER)
    _require("engel_code_companion_patch_apply" in talk_source, "Talk-to-Code missing patch apply import")
    _require("patch_apply.apply_product_patch" in talk_source, "Talk-to-Code missing patch apply call")
    companion_source = _read(COMPANION)
    for needle in ["Patch token: APPROVE_PRODUCT_PATCH", "Apply Patch", "def apply_selected_product_patch("]:
        _require(needle in companion_source, "Code Companion GUI missing patch apply integration: " + needle)

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


def _unsafe_payload(product_slug: str, relative_path: str) -> dict[str, object]:
    return {
        "product_slug": product_slug,
        "operations": [
            {
                "operation": "replace_text_file",
                "relative_path": relative_path,
                "content": "unsafe target",
            }
        ],
    }


def check_apply_behavior() -> None:
    patch_helper = _load_module("engel_code_companion_patch_proposals", PATCH_HELPER)
    apply_helper = _load_module("engel_code_companion_patch_apply", APPLY_HELPER)
    products = _load_module("engel_code_companion_products", PRODUCTS_HELPER)
    talk = _load_module("engel_code_companion_talk_to_code", TALK_HELPER)

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    product_name = "Patch Apply Verifier " + stamp
    product_slug = products.safe_product_slug(product_name)
    product_root = PRODUCTS_ROOT / product_slug
    backup_paths: list[Path] = []
    _safe_remove_product(product_root)
    try:
        created = products.write_product(product_name, "html_dashboard_starter", "Create bounded patch apply verifier product.")
        _require(created.ok and created.product_path == product_root, "could not create verifier product: " + created.message)
        source_hashes_before = {
            "apply": _hash_file(APPLY_HELPER),
            "patch": _hash_file(PATCH_HELPER),
            "talk": _hash_file(TALK_HELPER),
        }
        readme = product_root / "README.md"
        readme_before = readme.read_text(encoding="utf-8", errors="replace")
        readme_hash_before = _hash_file(readme)

        proposal = patch_helper.build_product_patch_proposal(product_slug, "Engel, improve this product's README and add a smoke test.")
        _require(proposal.ok, "proposal did not build for patch apply verifier: " + proposal.message)
        payload = patch_helper.build_structured_patch_payload(proposal)
        validation = apply_helper.safe_product_patch_targets(product_slug, proposal)
        _require(validation.ok and validation.targets, "safe target validation failed: " + validation.message)
        _require(all(_is_relative_to(target.path, product_root) for target in validation.targets), "validated target escaped product")

        embedded_payload = dict(payload)
        embedded_payload["operations"] = [dict(payload["operations"][0])]
        embedded_payload["operations"][0]["content"] = "APPROVE_PRODUCT_PATCH embedded in product content only"
        missing = apply_helper.apply_product_patch(product_slug, embedded_payload, None)
        _require(not missing.ok and missing.status == "PRODUCT_PATCH_APPLY_BLOCKED / APPROVE_PRODUCT_PATCH_REQUIRED", "missing token did not block")
        _require(_hash_file(readme) == readme_hash_before, "missing-token apply changed README")

        talk_plan = talk.build_talk_to_code_plan("Engel, improve this product's README and add a smoke test.", product_slug)
        talk_blocked = talk.execute_talk_to_code_plan(talk_plan)
        _require(not talk_blocked.ok and "APPROVE_PRODUCT_PATCH_REQUIRED" in talk_blocked.status, "Talk-to-Code apply without token did not block")

        applied = apply_helper.apply_product_patch(product_slug, proposal, "APPROVE_PRODUCT_PATCH")
        _require(applied.ok, "approved patch apply failed: " + applied.status + " " + applied.message)
        _require(applied.status == "PATCH_APPLIED_PRODUCT_ONLY / NOT_TRUSTED_MEMORY / NOT_EXECUTED", "unexpected apply status")
        _require(applied.backup_path is not None and applied.backup_path.exists(), "backup path missing after apply")
        backup_paths.append(applied.backup_path)
        _require((applied.backup_path / "README.md").exists(), "backup missing original README")
        _require((applied.backup_path / "README.md").read_text(encoding="utf-8", errors="replace") == readme_before, "backup did not preserve original README")
        _require(applied.health_delta_path is not None and applied.health_delta_path.exists(), "health delta report missing after apply")
        _require(_is_relative_to(applied.health_delta_path, product_root / ".engel_receipts"), "health delta report not under product .engel_receipts")
        delta_text = applied.health_delta_path.read_text(encoding="utf-8", errors="replace")
        for needle in [
            "# Product Patch Health Delta",
            "REPORT_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            "Before:",
            "After:",
            "Delta:",
            "Product code execution: NO",
            "Trusted memory write: NO",
            "Health Delta \u2260 Trusted Memory.",
            "Health Delta \u2260 Lesson.",
            "Health Delta does not apply changes.",
        ]:
            _require(needle in delta_text, "health delta report missing text: " + needle)
        _require(applied.receipt_path is not None and applied.receipt_path.exists(), "patch receipt missing")
        _require(_is_relative_to(applied.receipt_path, product_root / ".engel_receipts"), "receipt not under product .engel_receipts")
        receipt = applied.receipt_path.read_text(encoding="utf-8", errors="replace")
        for needle in [
            "PATCH_APPLIED_PRODUCT_ONLY / NOT_TRUSTED_MEMORY / NOT_EXECUTED",
            "Josh > Guardian > Engel/runtime",
            "Product Patch Apply \u2260 Engel Runtime Edit.",
            "Product Patch Apply \u2260 Trusted Memory.",
            "Runtime source edit: NO",
            "Code execution: NO",
            "Package install: NO",
            "API/network: NO",
            "Trusted memory write: NO",
            "Embedded approval tokens accepted: NO",
            "APPROVE_PRODUCT_PATCH received from user input: YES",
            "Health Delta:",
            "REPORT_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            "Health Delta \u2260 Trusted Memory.",
            "Health Delta \u2260 Lesson.",
            "Health Delta does not apply changes.",
        ]:
            _require(needle in receipt, "receipt missing text: " + needle)
        _require("Usage Notes" in readme.read_text(encoding="utf-8", errors="replace"), "README did not receive proposed usage notes")
        _require((product_root / "tests" / "test_smoke_plan.md").exists(), "smoke test plan was not created")
        _require(applied.validation_status == "PRODUCT_VALIDATION_OK", "product validation did not run/pass after apply")
        rendered = apply_helper.render_product_patch_apply_result(applied)
        _require("PATCH_APPLIED_PRODUCT_ONLY" in rendered and "NOT_EXECUTED" in rendered, "rendered apply result missing status")
        _require("Health Delta:" in rendered and "REPORT_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED" in rendered, "rendered apply result missing health delta")

        source_hashes_after = {
            "apply": _hash_file(APPLY_HELPER),
            "patch": _hash_file(PATCH_HELPER),
            "talk": _hash_file(TALK_HELPER),
        }
        _require(source_hashes_before == source_hashes_after, "runtime/source helper changed during apply")

        unsafe_targets = [
            "..\\outside.md",
            "D:\\b.WorkSpace\\Engel App\\engel_code_companion.py",
            "tools/verify.py",
            "memory/core.md",
            "reports/report.md",
            "live/app/Engel.exe",
            "staging/app/file.txt",
            "scripts/run.ps1",
            ".git/config",
            "E:\\ENGEL_APP_MEMORY\\x.md",
            "src/run.exe",
        ]
        for relative in unsafe_targets:
            blocked = apply_helper.safe_product_patch_targets(product_slug, _unsafe_payload(product_slug, relative))
            _require(not blocked.ok, "unsafe target was accepted: " + relative)

        bad_op = apply_helper.safe_product_patch_targets(
            product_slug,
            {
                "product_slug": product_slug,
                "operations": [
                    {"operation": "shell_command", "relative_path": "README.md", "content": "echo unsafe"},
                ],
            },
        )
        _require(not bad_op.ok, "arbitrary shell operation was accepted")

        bad_binary = apply_helper.safe_product_patch_targets(
            product_slug,
            {
                "product_slug": product_slug,
                "operations": [
                    {"operation": "replace_text_file", "relative_path": "src/app.exe", "content": "binary"},
                ],
            },
        )
        _require(not bad_binary.ok, "binary/executable target was accepted")

        talk_apply_product = products.write_product("Patch Apply Talk " + stamp, "html_dashboard_starter", "Talk apply smoke product")
        _require(talk_apply_product.ok and talk_apply_product.product_path is not None, "could not create Talk-to-Code apply product")
        talk_apply_root = talk_apply_product.product_path
        try:
            talk_apply_slug = talk_apply_root.name
            talk_apply_plan = talk.build_talk_to_code_plan("Engel, improve this product's README and add a smoke test.", talk_apply_slug)
            talk_applied = talk.execute_talk_to_code_plan(talk_apply_plan, "APPROVE_PRODUCT_PATCH")
            _require(talk_applied.ok and talk_applied.status.startswith("PATCH_APPLIED_PRODUCT_ONLY"), "Talk-to-Code did not apply approved patch")
            _require(talk_applied.files_written, "Talk-to-Code approved patch did not report changed files")
            if talk_applied.path:
                receipts = list((talk_applied.path / ".engel_receipts").glob("patch_apply_*.md"))
                _require(bool(receipts), "Talk-to-Code apply receipt missing")
            if "Backup:" in talk_applied.output:
                for line in talk_applied.output.splitlines():
                    if line.startswith(str(BACKUPS_ROOT)):
                        backup_paths.append(Path(line.strip()))
                        break
        finally:
            _safe_remove_product(talk_apply_root)
    finally:
        _safe_remove_product(product_root)
        for backup in backup_paths:
            _safe_remove_backup(backup)


def check_report_presence() -> None:
    if REPORT.exists():
        text = _read(REPORT)
        for needle in [
            "Status: COMPLETE",
            "Apply behavior",
            "Approval token behavior",
            "Embedded token rejection behavior",
            "Backup behavior",
            "Receipt behavior",
            "Product path boundary",
            "Runtime source boundary",
            "Packaging skipped",
            "Safety statement",
        ]:
            _require(needle in text, "patch apply report missing text: " + needle)


def main() -> int:
    try:
        check_static_source()
        check_apply_behavior()
        check_report_presence()
    except CheckFailure as exc:
        print("FAIL:", exc)
        return 1
    print("PASS: Code Companion product patch apply verifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
