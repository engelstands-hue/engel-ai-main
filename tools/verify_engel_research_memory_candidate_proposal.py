from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "engel_research_memory_candidate_proposal.py"
LESSON_DIR = ROOT / "reports" / "lesson_candidates"
OUTPUT_DIR = ROOT / "reports" / "memory_candidates"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_source() -> str:
    return PROPOSAL.read_text(encoding="utf-8", errors="replace")


def load_module():
    spec = importlib.util.spec_from_file_location("engel_research_memory_candidate_proposal", PROPOSAL)
    require(spec is not None and spec.loader is not None, "could not load proposal module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_research_memory_candidate_proposal"] = module
    spec.loader.exec_module(module)
    return module


def check_required_text() -> None:
    require(PROPOSAL.exists(), "engel_research_memory_candidate_proposal.py missing")
    require(LESSON_DIR.exists() and LESSON_DIR.is_dir(), "bounded input folder missing: reports\\lesson_candidates")
    require(OUTPUT_DIR.exists() and OUTPUT_DIR.is_dir(), "bounded output folder missing: reports\\memory_candidates")
    text = read_source()
    for needle in [
        "MEMORY_CANDIDATE_PROPOSAL_ONLY",
        "FROM_LESSON_CANDIDATE",
        "HUMAN_APPROVAL_REQUIRED",
        "NOT_TRUSTED_MEMORY",
        "NO_TRUSTED_MEMORY_WRITE",
        "NO_SOURCE_MUTATION",
        "NO_PATCH_APPLY",
        "NO_VERIFIER_UPDATE",
        "NO_SELF_FIX_POLICY_UPDATE",
        "NO_EXECUTION",
        "NO_TRAINING",
        "NO_INDEXING",
        "NO_EMBEDDING",
        "NO_PROVIDER_CALLS",
        "NO_NETWORK",
        "NO_BROWSER",
        "NO_BACKGROUND_WORKER",
        "NO_AUTOMATION_TRIGGERED",
        "reports",
        "lesson_candidates",
        "memory_candidates",
        "--lesson",
        "--dry-run",
        "--write",
    ]:
        require(needle in text, "proposal tool missing required text: " + needle)
    for field in [
        "memory_candidate_proposal_id",
        "source_lesson_candidate_id",
        "source_research_note_id",
        "topic_id",
        "topic_title",
        "proposed_at",
        "trust_status",
        "proposed_memory_summary",
        "reason_to_remember",
        "evidence_chain",
        "source_references",
        "safety_notes",
        "uncertainty_notes",
        "prompt_injection_review_needed",
        "authority_review_needed",
        "suggested_core_continuity_linkage",
        "required_human_approval",
        "required_verifier_compatibility",
        "not_trusted_memory",
        "no_trusted_memory_write",
        "no_source_mutation",
    ]:
        require(field in text, "proposal tool missing proposal field: " + field)


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
                require(root_name not in forbidden_imports, "proposal imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".")[0]
            require(root_name not in forbidden_imports, "proposal imports forbidden module: " + node.module)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in {"walk", "rglob", "unlink", "remove"}, "proposal uses forbidden call: " + node.func.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in {"exec", "eval", "__import__"}, "proposal uses forbidden call: " + node.func.id)


def check_runtime_smoke() -> None:
    module = load_module()
    out = io.StringIO()
    err = io.StringIO()
    require(module.main([], stdout=out, stderr=err) == 0, "proposal no-argument usage failed")
    require("MEMORY_CANDIDATE_PROPOSAL_ONLY" in out.getvalue(), "proposal usage missing proposal status")
    for unsafe in ["https://example.com/file.md", "..\\outside.md", "memory\\lesson.md", "lesson*.md", "G:\\ENGEL_APP_MEMORY\\lesson.md"]:
        try:
            module.resolve_lesson_path(unsafe)
        except module.MemoryCandidateProposalError:
            continue
        raise CheckFailure("proposal accepted unsafe lesson name: " + unsafe)


def main() -> int:
    try:
        check_required_text()
        check_forbidden_active_behavior()
        check_runtime_smoke()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel research memory candidate proposal verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
