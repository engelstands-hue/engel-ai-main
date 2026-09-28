#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "engel_code_companion_readme_manifest_proposals.py"
PRODUCTS_HELPER = ROOT / "engel_code_companion_products.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_README_MANIFEST_PROPOSALS.md"
PRODUCT_SLUG = "python_cli_hello"


class CheckFailure(Exception):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_module(name: str, path: Path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    _require(spec is not None and spec.loader is not None, "could not load module: " + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_hashes(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            hashes[str(path.relative_to(root)).replace("\\", "/")] = _file_hash(path)
    return hashes


def check_required_files() -> None:
    for path in (HELPER, PRODUCTS_HELPER, REPORT):
        _require(path.exists(), "required file missing: " + str(path))
        _require(path.is_file(), "required path is not a file: " + str(path))


def check_static_source() -> None:
    source = _read(HELPER)
    tree = ast.parse(source)
    required = [
        "PROPOSAL_ONLY / NOT_APPLIED / PRODUCT_ONLY",
        "README/Manifest Proposal != Applied Change.",
        "def build_readme_manifest_proposal(",
        "def render_readme_manifest_proposal(",
        "README proposal:",
        "Manifest proposal:",
        "Product files changed now: NO",
        "Runtime source edit: NO",
        "Code execution: NO",
        "Approval required before apply: YES",
    ]
    for needle in required:
        _require(needle in source, "helper missing required text: " + needle)

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    blocked_imports = {
        "requests",
        "urllib",
        "socket",
        "subprocess",
        "webbrowser",
        "threading",
        "multiprocessing",
        "selenium",
        "playwright",
        "pyautogui",
    }
    _require(not (set(imports) & blocked_imports), "blocked import found in helper")

    blocked_write_needles = [
        ".write_text(",
        ".write_bytes(",
        ".mkdir(",
        ".unlink(",
        ".rename(",
        "shutil.",
        "os.remove",
        "os.system",
        "Popen",
        "shell=True",
        "def apply",
        "apply_readme",
        "apply_manifest",
    ]
    for needle in blocked_write_needles:
        _require(needle not in source, "write/apply behavior found in helper: " + needle)


def check_behavior() -> None:
    helper = _load_module("engel_code_companion_readme_manifest_proposals", HELPER)
    products = _load_module("engel_code_companion_products", PRODUCTS_HELPER)

    product_path = products.product_path_for_slug(PRODUCT_SLUG)
    _require(product_path.exists(), "expected verifier product missing: " + str(product_path))
    before_product = _tree_hashes(product_path)
    before_runtime = {
        "helper": _file_hash(HELPER),
        "products": _file_hash(PRODUCTS_HELPER),
    }

    proposal = helper.build_readme_manifest_proposal(PRODUCT_SLUG)
    rendered = helper.render_readme_manifest_proposal(proposal)

    _require(proposal.ok, "proposal should be generated for existing product")
    _require(proposal.status == "PROPOSAL_ONLY / NOT_APPLIED / PRODUCT_ONLY", "unexpected proposal status")
    _require(proposal.readme is not None, "README proposal missing")
    _require(proposal.manifest is not None, "manifest proposal missing")
    _require("README proposal:" in rendered, "README proposal section missing")
    _require("Manifest proposal:" in rendered, "Manifest proposal section missing")
    _require("README diff:" in rendered and "--- README.md" in rendered, "README diff missing")
    _require("Manifest diff:" in rendered and "--- product_manifest.json" in rendered, "manifest diff missing")
    _require("Guardian Review:" in rendered, "Guardian Review missing")
    _require("- Product files changed now: NO" in rendered, "product file no-change boundary missing")
    _require("- Runtime source edit: NO" in rendered, "runtime boundary missing")
    _require("- Code execution: NO" in rendered, "execution boundary missing")
    _require("- API/network: NO" in rendered, "API/network boundary missing")
    _require("- Approval required before apply: YES" in rendered, "approval-before-apply boundary missing")
    _require("README/Manifest Proposal != Applied Change." in rendered, "proposal boundary missing")

    parsed_manifest = json.loads(proposal.manifest.proposed_content)
    _require(parsed_manifest["slug"] == PRODUCT_SLUG, "proposed manifest slug mismatch")
    _require(parsed_manifest["status"] == "PRODUCT_ONLY / NOT_RUNTIME / NOT_APPLIED", "proposed manifest status mismatch")
    _require(parsed_manifest["authority"] == "Josh > Guardian > Engel/runtime", "proposed manifest authority mismatch")
    _require(parsed_manifest["proposal_status"] == "PROPOSAL_ONLY / NOT_APPLIED / PRODUCT_ONLY", "proposal manifest status missing")

    unsafe_ids = [
        "..\\python_cli_hello",
        "../python_cli_hello",
        "C:\\temp\\python_cli_hello",
        "\\\\server\\share",
        "https://example.test/product",
        "python_cli_hello/README.md",
    ]
    for unsafe in unsafe_ids:
        blocked = helper.build_readme_manifest_proposal(unsafe)
        blocked_text = helper.render_readme_manifest_proposal(blocked)
        _require(not blocked.ok, "unsafe product identifier was not blocked: " + unsafe)
        _require("README_MANIFEST_PROPOSAL_BLOCKED" in blocked_text, "blocked proposal status missing for: " + unsafe)

    after_product = _tree_hashes(product_path)
    after_runtime = {
        "helper": _file_hash(HELPER),
        "products": _file_hash(PRODUCTS_HELPER),
    }
    _require(before_product == after_product, "product files changed while building README/manifest proposal")
    _require(before_runtime == after_runtime, "runtime/source files changed while building README/manifest proposal")


def check_report() -> None:
    report = _read(REPORT)
    required = [
        "Status: COMPLETE",
        "README/Manifest Proposal != Applied Change",
        "PROPOSAL_ONLY / NOT_APPLIED / PRODUCT_ONLY",
        "No README or manifest files were edited",
        "No runtime source files were changed",
        "No product code was executed",
        "No API/network behavior was added",
        "Packaging skipped",
    ]
    for needle in required:
        _require(needle in report, "report missing required text: " + needle)


def main() -> int:
    checks = (
        check_required_files,
        check_static_source,
        check_behavior,
        check_report,
    )
    for check in checks:
        check()
    print("PASS: Code Companion README/manifest proposal verifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
