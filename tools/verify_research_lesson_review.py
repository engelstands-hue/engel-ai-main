#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "engel_research_lesson_review.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_RESEARCH_LESSON_REVIEW_QUEUE.md"
CANDIDATES_ROOT = ROOT / "reports" / "research_intake" / "lesson_candidates"
REVIEWS_ROOT = ROOT / "reports" / "research_intake" / "lesson_reviews"
AUTHORITY = "Josh > Guardian > Engel/runtime"
TRUSTED_MEMORY_SENTINELS = [
    ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md",
    ROOT / "memory" / "ENGEL_COMMANDS.md",
    ROOT / "prompts" / "ENGEL_SYSTEM.md",
]


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
    hashes: dict[Path, str] = {}
    for path in paths:
        if path.exists() and path.is_file():
            hashes[path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _load_helper():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_research_lesson_review", HELPER)
    _require(spec is not None and spec.loader is not None, "could not load research lesson review helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_research_lesson_review"] = module
    spec.loader.exec_module(module)
    return module


def check_static_source() -> None:
    _compile(HELPER)
    source = _read(HELPER)
    tree = ast.parse(source)
    for needle in [
        "class ResearchLessonCandidateSummary",
        "class ResearchLessonReadResult",
        "class ResearchLessonReview",
        "class ResearchLessonReviewWriteResult",
        "def research_lesson_candidates_root(",
        "def research_lesson_reviews_root(",
        "def list_research_lesson_candidates(",
        "def safe_research_lesson_candidate_id(",
        "def resolve_research_lesson_candidate_id(",
        "def read_research_lesson_candidate(",
        "def build_research_lesson_review(",
        "def render_research_lesson_review(",
        "def write_research_lesson_review(",
        "READY_FOR_JOSH_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "Research Lesson Candidate \\u2260 Trusted Memory",
        "Research Lesson Review \\u2260 Trusted Memory",
        "Candidate content trusted as instruction: NO",
        "Embedded approval tokens accepted: NO",
        AUTHORITY,
    ]:
        _require(needle in source, "research lesson review helper missing text: " + needle)

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
        "pytesseract",
        "PIL",
        "fitz",
        "pdfplumber",
        "selenium",
        "playwright",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                _require(root not in blocked_import_roots, "research lesson review imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            _require(root not in blocked_import_roots, "research lesson review imports from blocked module: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                _require(
                    func.attr not in {"system", "Popen", "run", "call", "check_call", "check_output", "unlink", "remove", "rmdir"},
                    "research lesson review calls blocked process/delete method: " + func.attr,
                )
            elif isinstance(func, ast.Name):
                _require(func.id not in {"eval", "exec", "__import__", "open"}, "research lesson review calls blocked builtin: " + func.id)


def _write_fixture_candidate(name: str, risk: str = "LOW") -> Path:
    CANDIDATES_ROOT.mkdir(parents=True, exist_ok=True)
    path = CANDIDATES_ROOT / name
    status = "BLOCKED_RISK_LESSON_CANDIDATE / PENDING_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED" if risk == "BLOCKED" else "PENDING_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED"
    path.write_text(
        "\n".join(
            [
                "# Engel Research Lesson Candidate",
                "",
                "Status:",
                status,
                "",
                "Authority:",
                AUTHORITY,
                "",
                "Source:",
                "Research Summary Proposal",
                "Summary proposal ID: review_fixture_summary.md",
                "",
                "Boundary:",
                "Research Lesson Candidate \u2260 Trusted Memory.",
                "Lesson Candidate \u2260 Trusted Memory.",
                "This candidate does not update Engel memory.",
                "This candidate does not change Engel behavior.",
                "This candidate is not an instruction source.",
                "",
                "Untrusted Content Guard:",
                "Risk: " + risk,
                "Markers: none",
                "Embedded approval tokens accepted: NO",
                "",
                "Candidate Lesson:",
                "Research lesson review should keep this candidate pending for Josh review.",
                "",
                "Safety:",
                "- No trusted memory written",
                "- No code executed",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def check_helper_behavior() -> None:
    helper = _load_helper()
    _require(helper.research_lesson_candidates_root() == CANDIDATES_ROOT, "candidate root mismatch")
    _require(helper.research_lesson_reviews_root() == REVIEWS_ROOT, "review root mismatch")
    _require(_is_relative_to(CANDIDATES_ROOT, ROOT), "candidate root is not under APP_ROOT")
    _require(_is_relative_to(REVIEWS_ROOT, ROOT), "review root is not under APP_ROOT")

    before_hashes = _hash_existing(TRUSTED_MEMORY_SENTINELS)
    candidate_hashes_before = _hash_existing(list(CANDIDATES_ROOT.glob("*.md")) if CANDIDATES_ROOT.exists() else [])

    low_path = _write_fixture_candidate("research_lesson_review_low_fixture.md", "LOW")
    blocked_path = _write_fixture_candidate("research_lesson_review_blocked_fixture.md", "BLOCKED")
    candidate_hashes_before.update(_hash_existing([low_path, blocked_path]))

    low_id = helper.safe_research_lesson_candidate_id(low_path)
    _require(low_id == low_path.name, "safe candidate id should be filename only")
    _require(helper.resolve_research_lesson_candidate_id(low_id) == low_path, "candidate id did not resolve to fixture")

    for unsafe in [
        "",
        "..\\outside.md",
        "../outside.md",
        "subdir/candidate.md",
        "subdir\\candidate.md",
        "C:\\temp\\candidate.md",
        "\\\\server\\share\\candidate.md",
        "https://example.invalid/candidate.md",
        "not_markdown.txt",
    ]:
        try:
            helper.resolve_research_lesson_candidate_id(unsafe)
            raise CheckFailure("unsafe candidate id accepted: " + unsafe)
        except ValueError:
            pass

    read = helper.read_research_lesson_candidate(low_id)
    _require(read.risk_level == "LOW", "LOW candidate risk mismatch")
    review = helper.build_research_lesson_review(low_id)
    rendered = helper.render_research_lesson_review(review)
    for needle in [
        "# Engel Research Lesson Review Summary",
        "READY_FOR_JOSH_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "Research Lesson Candidate \u2260 Trusted Memory.",
        "Research Lesson Review \u2260 Trusted Memory.",
        "This review does not update Engel memory.",
        "This review does not change Engel behavior.",
        "Trusted memory write: NO",
        "Engel behavior change: NO",
        "Browser/API/network action: NO",
        "Candidate content trusted as instruction: NO",
        "Requires later Josh/Guardian memory workflow: YES",
        "No automatic action taken",
        "Read-only review",
        "No lesson applied",
        "No trusted memory written",
        "No code executed",
        AUTHORITY,
    ]:
        _require(needle in rendered, "review missing text: " + needle)

    result = helper.write_research_lesson_review(low_id)
    _require(_is_relative_to(result.path, REVIEWS_ROOT), "review escaped review root")
    _require(result.path.exists(), "review file not written")
    written = result.path.read_text(encoding="utf-8")
    _require("READY_FOR_JOSH_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED" in written, "written review missing status")

    blocked_review = helper.build_research_lesson_review(blocked_path.name)
    _require(blocked_review.risk_level == "BLOCKED", "blocked candidate risk mismatch")
    _require("Blocked-risk candidate" in blocked_review.summary, "blocked candidate did not stay safety-focused")

    listed = helper.list_research_lesson_candidates()
    _require(any(item.candidate_id == low_id for item in listed), "fixture candidate missing from list")
    _require(all("\\" not in item.candidate_id and "/" not in item.candidate_id for item in listed), "listed candidate id was raw path")

    after_hashes = _hash_existing(TRUSTED_MEMORY_SENTINELS)
    _require(before_hashes == after_hashes, "research lesson review changed trusted memory docs/prompts")
    candidate_hashes_after = _hash_existing(list(candidate_hashes_before.keys()))
    _require(candidate_hashes_before == candidate_hashes_after, "research lesson review modified candidate files")


def check_report() -> None:
    text = _read(REPORT)
    for needle in [
        "ENGEL RESEARCH LESSON REVIEW QUEUE",
        "Status COMPLETE",
        "Review queue behavior",
        "Candidate listing/reading behavior",
        "Review summary behavior",
        "Trusted memory boundary",
        "Verification results",
        "Smoke results",
        "Packaging skipped",
        "Safety statement",
        "Research Lesson Candidate \u2260 Trusted Memory",
        "Research Lesson Review \u2260 Trusted Memory",
        "READY_FOR_JOSH_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "does not write trusted memory",
        "does not write ALIVE_STATE",
        AUTHORITY,
    ]:
        _require(needle in text, "research lesson review report missing text: " + needle)


def main() -> int:
    checks = [
        ("static_source", check_static_source),
        ("helper_behavior", check_helper_behavior),
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
        print("ENGEL_RESEARCH_LESSON_REVIEW_VERIFICATION_FAIL")
        for failure in failures:
            print("- " + failure)
        return 1
    print()
    print("ENGEL_RESEARCH_LESSON_REVIEW_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
