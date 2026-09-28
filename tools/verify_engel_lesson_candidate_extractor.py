from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR = ROOT / "engel_lesson_candidate_extractor.py"
NOTE_DIR = ROOT / "reports" / "self_research_notes"
OUTPUT_DIR = ROOT / "reports" / "lesson_candidates"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_source() -> str:
    return EXTRACTOR.read_text(encoding="utf-8", errors="replace")


def load_module():
    spec = importlib.util.spec_from_file_location("engel_lesson_candidate_extractor", EXTRACTOR)
    require(spec is not None and spec.loader is not None, "could not load extractor module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_lesson_candidate_extractor"] = module
    spec.loader.exec_module(module)
    return module


def check_required_text() -> None:
    require(EXTRACTOR.exists(), "engel_lesson_candidate_extractor.py missing")
    require(NOTE_DIR.exists() and NOTE_DIR.is_dir(), "bounded input folder missing: reports\\self_research_notes")
    require(OUTPUT_DIR.exists() and OUTPUT_DIR.is_dir(), "bounded output folder missing: reports\\lesson_candidates")
    text = read_source()
    for needle in [
        "LESSON_CANDIDATE_ONLY",
        "FROM_UNTRUSTED_RESEARCH_NOTE",
        "NOT_TRUSTED_MEMORY",
        "NOT_APPROVED_LESSON",
        "NO_VERIFIER_UPDATE",
        "NO_SELF_FIX_POLICY_UPDATE",
        "NO_SOURCE_MUTATION",
        "NO_PATCH_APPLY",
        "NO_EXECUTION",
        "NO_TRAINING",
        "NO_INDEXING",
        "NO_EMBEDDING",
        "NO_PROVIDER_CALLS",
        "NO_NETWORK",
        "NO_BROWSER",
        "NO_BACKGROUND_WORKER",
        "HUMAN_REVIEW_REQUIRED",
        "NO_AUTOMATION_TRIGGERED",
        "reports",
        "self_research_notes",
        "lesson_candidates",
        "--note",
        "--dry-run",
        "--write",
    ]:
        require(needle in text, "extractor missing required text: " + needle)
    for field in [
        "lesson_candidate_id",
        "source_research_note_id",
        "source_note_path",
        "topic_id",
        "topic_title",
        "extracted_at",
        "trust_status",
        "candidate_summary",
        "candidate_details",
        "confidence",
        "evidence_from_note",
        "uncertainty_notes",
        "safety_notes",
        "possible_verifier_relevance",
        "possible_self_fix_relevance",
        "memory_candidate_possible",
        "required_review_before_use",
        "not_trusted_memory",
        "no_source_mutation",
        "no_verifier_update",
        "no_self_fix_policy_update",
    ]:
        require(field in text, "extractor missing candidate field: " + field)


def check_forbidden_active_behavior() -> None:
    tree = ast.parse(read_source())
    forbidden_imports = {
        "requests",
        "urllib",
        "socket",
        "webbrowser",
        "openai",
        "subprocess",
        "glob",
        "shutil",
        "threading",
        "multiprocessing",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                require(root_name not in forbidden_imports, "extractor imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".")[0]
            require(root_name not in forbidden_imports, "extractor imports forbidden module: " + node.module)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in {"walk", "rglob", "unlink", "remove"}, "extractor uses forbidden call: " + node.func.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in {"exec", "eval", "__import__"}, "extractor uses forbidden call: " + node.func.id)


def check_runtime_smoke() -> None:
    module = load_module()
    out = io.StringIO()
    err = io.StringIO()
    require(module.main([], stdout=out, stderr=err) == 0, "extractor no-argument usage failed")
    require("LESSON_CANDIDATE_ONLY" in out.getvalue(), "extractor usage missing candidate status")
    for unsafe in ["https://example.com/file.md", "..\\outside.md", "memory\\note.md", "note*.md", "G:\\ENGEL_APP_MEMORY\\note.md"]:
        try:
            module.resolve_note_path(unsafe)
        except module.LessonCandidateError:
            continue
        raise CheckFailure("extractor accepted unsafe note name: " + unsafe)


def main() -> int:
    try:
        check_required_text()
        check_forbidden_active_behavior()
        check_runtime_smoke()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel lesson candidate extractor verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
