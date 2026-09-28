#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "engel_memory_candidate_review_dashboard.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_MEMORY_CANDIDATE_REVIEW_DASHBOARD.md"
CANDIDATE_ROOT = ROOT / "reports" / "memory_candidate_proposals"
TRUSTED_MEMORY_SENTINELS = [
    ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md",
    ROOT / "memory" / "ENGEL_COMMANDS.md",
    ROOT / "memory" / "ENGEL_MEMORY_CANDIDATE_WORKFLOW_CONTRACT_V1.md",
    ROOT / "memory" / "ENGEL_MEMORY_CANDIDATE_WORKFLOW_CONTRACT_V1.json",
    ROOT / "prompts" / "ENGEL_SYSTEM.md",
]
RUNTIME_SENTINELS = [
    ROOT / "engel_app.py",
    ROOT / "engel_memory_candidate_proposals.py",
    ROOT / "engel_memory_candidate_review_dashboard.py",
]
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


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _hash_existing(paths: list[Path]) -> dict[Path, str]:
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths if path.exists() and path.is_file()}


def _candidate_files() -> set[Path]:
    if not CANDIDATE_ROOT.exists():
        return set()
    return {path for path in CANDIDATE_ROOT.glob("*.md") if path.is_file()}


def _load_helper():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_memory_candidate_review_dashboard", HELPER)
    _require(spec is not None and spec.loader is not None, "could not load dashboard helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_memory_candidate_review_dashboard"] = module
    spec.loader.exec_module(module)
    return module


def check_static_source() -> None:
    _compile(HELPER)
    source = _read(HELPER)
    tree = ast.parse(source)
    for needle in [
        "memory_candidate_proposals_root",
        "list_memory_candidate_proposals",
        "latest_memory_candidate_proposal",
        "render_memory_candidate_review_dashboard",
        "READ_ONLY_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "Trusted Memory Candidate",
        "Trusted Memory",
        "Review Dashboard",
        "BLOCKED / NOT_PERFORMED",
        "Guardian Review:",
        "Trusted memory write: NO",
        "Candidate content trusted as instruction: NO",
        AUTHORITY,
    ]:
        _require(needle in source, "dashboard helper missing text: " + needle)

    blocked_import_roots = {
        "asyncio",
        "httpx",
        "openai",
        "anthropic",
        "requests",
        "socket",
        "subprocess",
        "urllib",
        "webbrowser",
        "threading",
        "multiprocessing",
        "selenium",
        "playwright",
    }
    blocked_write_methods = {
        "mkdir",
        "open",
        "remove",
        "rename",
        "replace",
        "rmdir",
        "touch",
        "unlink",
        "write",
        "write_bytes",
        "write_text",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _require(alias.name.split(".")[0] not in blocked_import_roots, "dashboard imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _require(node.module.split(".")[0] not in blocked_import_roots, "dashboard imports blocked module: " + str(node.module))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                _require(func.id not in {"eval", "exec", "__import__", "open"}, "dashboard calls blocked builtin: " + func.id)
            elif isinstance(func, ast.Attribute):
                _require(func.attr not in blocked_write_methods, "dashboard calls write/mutation method: " + func.attr)


def check_behavior_read_only() -> None:
    helper = _load_helper()
    root = helper.memory_candidate_proposals_root()
    _require(root == CANDIDATE_ROOT, "candidate proposal root mismatch")
    _require(_is_relative_to(root, ROOT), "candidate root not under APP_ROOT")
    _require(str(root.relative_to(ROOT)).replace("/", "\\") == "reports\\memory_candidate_proposals", "candidate root path mismatch")

    before_trusted = _hash_existing(TRUSTED_MEMORY_SENTINELS)
    before_runtime = _hash_existing(RUNTIME_SENTINELS)
    before_candidates = _candidate_files()

    proposals = helper.list_memory_candidate_proposals()
    latest = helper.latest_memory_candidate_proposal()
    dashboard = helper.render_memory_candidate_review_dashboard()

    _require(isinstance(proposals, list), "list_memory_candidate_proposals must return a list")
    _require(latest is None or _is_relative_to(latest, CANDIDATE_ROOT), "latest candidate escaped candidate root")
    for proposal in proposals:
        _require(_is_relative_to(proposal.path, CANDIDATE_ROOT), "listed proposal escaped candidate root")
    for needle in [
        "# TRUSTED MEMORY CANDIDATE REVIEW",
        "READ_ONLY_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "Candidates:",
        "Latest:",
        "Source types:",
        "- product lesson reviews",
        "- research lesson reviews",
        "- research summary proposals",
        "Risk status:",
        "Review readiness:",
        "Trusted memory:",
        "BLOCKED / NOT_PERFORMED",
        "Guardian Review:",
        "- Trusted memory write: NO",
        "- Engel behavior change: NO",
        "- Runtime source edit: NO",
        "- Candidate content trusted as instruction: NO",
        "- Requires future Josh/Guardian trusted-memory workflow: YES",
        "Boundary:",
        "Trusted Memory Candidate \u2260 Trusted Memory.",
        "Review Dashboard \u2260 Trusted Memory.",
        "No trusted memory written.",
        "No candidates applied or promoted.",
        "No system prompt updated as accepted truth.",
        AUTHORITY,
    ]:
        _require(needle in dashboard, "dashboard missing text: " + needle)

    after_trusted = _hash_existing(TRUSTED_MEMORY_SENTINELS)
    after_runtime = _hash_existing(RUNTIME_SENTINELS)
    after_candidates = _candidate_files()
    _require(before_trusted == after_trusted, "trusted memory docs/prompts changed")
    _require(before_runtime == after_runtime, "runtime/source files changed")
    _require(before_candidates == after_candidates, "dashboard created or removed candidate files")


def check_report() -> None:
    text = _read(REPORT)
    for needle in [
        "ENGEL_MEMORY_CANDIDATE_REVIEW_DASHBOARD",
        "Status COMPLETE",
        "Files changed",
        "Dashboard behavior",
        "Trusted memory boundary",
        "Verification results",
        "Packaging skipped",
        "Safety statement",
        "Trusted Memory Candidate Review Dashboard is read-only status/review only",
        "does not write trusted memory",
        "does not write ALIVE_STATE",
        AUTHORITY,
    ]:
        _require(needle in text, "dashboard report missing text: " + needle)


def main() -> int:
    checks = [
        ("static_source", check_static_source),
        ("behavior_read_only", check_behavior_read_only),
        ("report", check_report),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(name + ": " + str(exc))
            print("FAIL " + name + ": " + str(exc))
        except Exception as exc:
            failures.append(name + ": unexpected error: " + str(exc))
            print("FAIL " + name + ": unexpected error: " + str(exc))

    if failures:
        print()
        print("ENGEL_MEMORY_CANDIDATE_REVIEW_DASHBOARD_VERIFICATION_FAIL")
        for failure in failures:
            print("- " + failure)
        return 1

    print()
    print("ENGEL_MEMORY_CANDIDATE_REVIEW_DASHBOARD_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
