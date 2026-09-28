#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "engel_code_companion_project_builder.py"
TALK_HELPER = ROOT / "engel_code_companion_talk_to_code.py"
COMPANION = ROOT / "engel_code_companion.py"
PRODUCTS_HELPER = ROOT / "engel_code_companion_products.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_TALK_TO_CODE_PROJECT_BUILDER.md"
PRODUCTS_ROOT = ROOT / "products"
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
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _safe_remove_product(path: Path) -> None:
    if path.exists():
        _require(_is_relative_to(path, PRODUCTS_ROOT) and path.parent.resolve() == PRODUCTS_ROOT.resolve(), "refusing to clean unbounded product path: " + str(path))
        shutil.rmtree(path)


def check_static_source() -> None:
    for path in (HELPER, TALK_HELPER, COMPANION):
        _compile(path)

    helper_source = _read(HELPER)
    talk_source = _read(TALK_HELPER)
    for needle in [
        "PROJECT_BUILDER_PLAN",
        "def build_project_builder_plan(",
        "def render_project_builder_plan(",
        "def create_project_builder_product(",
        "PLAN_ONLY",
        "NOT_TRUSTED_MEMORY",
        "NOT_APPLIED",
        "Guardian Review:",
        "Product-only creation: YES",
        "Runtime source edit: NO",
        "Code execution now: NO",
        "Package install: NO",
        "API/network: NO",
        "Trusted memory write: NO",
        "APP_ROOT/products",
    ]:
        _require(needle in helper_source, "Project Builder helper missing required text: " + needle)
    for needle in [
        "engel_code_companion_project_builder",
        "PROJECT_BUILDER_PLAN",
        "project_builder.build_project_builder_plan",
        "project_builder.create_project_builder_product",
        "project_builder.render_project_builder_plan",
    ]:
        _require(needle in talk_source, "Talk-to-Code helper missing Project Builder integration: " + needle)

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
    for path, label in [(HELPER, "project builder helper"), (TALK_HELPER, "talk helper")]:
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


def check_project_builder_behavior() -> None:
    helper = _load_module("engel_code_companion_project_builder", HELPER)
    talk = _load_module("engel_code_companion_talk_to_code", TALK_HELPER)
    products = _load_module("engel_code_companion_products", PRODUCTS_HELPER)

    template_cases = {
        "Engel, make me a simple habit tracker.": "html_dashboard",
        "Build a small dashboard for research notes.": "html_dashboard",
        "Create a Python CLI that organizes text files.": "python_cli",
        "Make a landing page for this product idea.": "static_landing_page",
        "Make a product plan for a future idea.": "markdown_product_plan",
    }
    for idea, expected_template in template_cases.items():
        plan = helper.build_project_builder_plan(idea)
        rendered = helper.render_project_builder_plan(plan)
        _require(plan.status == "READY_TO_CREATE", "safe idea did not become ready-to-create: " + idea)
        _require(plan.selected_template == expected_template, "template mismatch for idea: " + idea)
        _require(plan.save_root is not None and _is_relative_to(plan.save_root, PRODUCTS_ROOT), "Project Builder save root escaped products")
        for needle in [
            "# ENGEL PROJECT BUILDER PLAN",
            "PLAN_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            "Guardian Review:",
            "Runtime source edit: NO",
            "Product-only creation: YES",
            "Code execution now: NO",
            "Package install: NO",
            "API/network: NO",
            "Trusted memory write: NO",
            "Josh > Guardian > Engel/runtime preserved: YES",
            "Click Create only if Josh wants this bounded product scaffold generated.",
        ]:
            _require(needle in rendered, "Project Builder plan missing text: " + needle)

    empty = helper.build_project_builder_plan("")
    _require(empty.status == "BLOCKED" and "ASK_FOR_DETAILS_REQUIRED" in empty.blocked_reason, "empty idea did not ask for details/block")
    unsafe = helper.build_project_builder_plan("Edit Engel runtime and install packages.")
    _require(unsafe.status == "BLOCKED", "unsafe runtime/install idea was not blocked")
    network = helper.build_project_builder_plan("Create a dashboard that calls an API and executes generated code now.")
    _require(network.status == "BLOCKED", "API/execute idea was not blocked")
    traversal = helper.build_project_builder_plan("Build a dashboard called ..\\bad")
    _require(traversal.status == "BLOCKED" and "UNSAFE_PRODUCT_SLUG" in traversal.blocked_reason, "path-like slug was not blocked")

    natural = talk.build_talk_to_code_plan("Engel, make me a simple habit tracker dashboard.")
    natural_text = talk.render_talk_to_code_plan(natural)
    _require(natural.status == "READY_TO_CREATE", "natural Talk-to-Code Project Builder plan was not ready")
    _require(natural.target_type == "PROJECT_BUILDER_PLAN", "natural Talk-to-Code idea did not map to Project Builder")
    _require("# ENGEL PROJECT BUILDER PLAN" in natural_text, "Talk-to-Code did not render Project Builder plan")

    old_cli = talk.build_talk_to_code_plan(
        "Engel, create a small Python CLI product that says hello and has a README called Talk To Code Verifier CLI",
    )
    _require(old_cli.target_type == "python_cli_product", "legacy Talk-to-Code product flow was not preserved")
    old_script = talk.build_talk_to_code_plan("Engel, make a Python script called hello_engel_example.py")
    _require(old_script.target_type == "python_script", "legacy Talk-to-Code script flow was not preserved")

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    create_idea = "Engel, build a Project Builder verifier habit tracker dashboard " + stamp
    create_plan = helper.build_project_builder_plan(create_idea)
    _require(create_plan.save_root is not None, "create plan missing save root")
    product_root = create_plan.save_root
    _safe_remove_product(product_root)
    try:
        create_result = helper.create_project_builder_product(create_plan)
        _require(create_result.ok, "Project Builder create failed: " + create_result.message)
        _require(create_result.product_path == product_root, "Project Builder create path mismatch")
        _require(product_root.exists() and product_root.is_dir(), "created product root missing")
        _require(_is_relative_to(product_root, PRODUCTS_ROOT), "created product escaped products")
        for relative in ("README.md", "product_manifest.json", ".engel_product_profile.json", "index.html", "styles.css"):
            _require((product_root / relative).exists(), "created product missing: " + relative)
        _require(all(_is_relative_to(path, PRODUCTS_ROOT) for path in create_result.files_written), "created file escaped products")
        _require(create_result.validation_status == "PRODUCT_FILES_VALID", "Project Builder validation status mismatch")
        health = products.product_health_check(product_root.name)
        _require(health.ok and health.status == "PASS", "created product health did not pass: " + health.status)
        preview = products.preview_product_file(product_root.name, "README.md")
        _require(preview.ok and "Product-only scaffold" in preview.content, "created product preview failed")

        blocked_overwrite = helper.create_project_builder_product(create_plan)
        _require(not blocked_overwrite.ok and "APPROVE_CHANGE_REQUIRED" in blocked_overwrite.status, "overwrite without approval was not blocked")

        talk_create_plan = talk.build_talk_to_code_plan("Engel, create a Python CLI that organizes text files for verifier " + stamp)
        talk_root = Path(talk_create_plan.save_root)
        _safe_remove_product(talk_root)
        talk_result = talk.execute_talk_to_code_plan(talk_create_plan)
        _require(talk_result.ok and talk_result.path == talk_root, "Talk-to-Code Project Builder create failed: " + talk_result.message)
        _require(talk_result.path is not None and (talk_result.path / "README.md").exists(), "Talk-to-Code Project Builder README missing")
        _require(talk_result.path is not None and (talk_result.path / ".engel_product_profile.json").exists(), "Talk-to-Code Project Builder profile missing")
        _safe_remove_product(talk_root)
    finally:
        _safe_remove_product(product_root)


def check_report_presence() -> None:
    if REPORT.exists():
        text = _read(REPORT)
        for needle in [
            "Engel Talk-to-Code Project Builder",
            "Packaging skipped",
            "Project Builder behavior",
            "Product path boundary",
            "Trusted memory boundary",
        ]:
            _require(needle in text, "Project Builder report missing text: " + needle)


def main() -> int:
    try:
        check_static_source()
        check_project_builder_behavior()
        check_report_presence()
    except CheckFailure as exc:
        print("FAIL:", exc)
        return 1
    print("PASS: Code Companion Project Builder verifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
