from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "engel_self_fix_improvement_candidate.py"
VERIFIER = ROOT / "tools" / "verify_engel_self_fix_improvement_candidate.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_SELF_FIX_IMPROVEMENT_CANDIDATE_V1.md"
LESSON_DIR = ROOT / "reports" / "lesson_candidates"
MEMORY_PROPOSAL_DIR = ROOT / "reports" / "memory_candidates"
VERIFIER_CANDIDATE_DIR = ROOT / "reports" / "verifier_improvement_candidates"
OUTPUT_DIR = ROOT / "reports" / "self_fix_improvement_candidates"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_source() -> str:
    return TOOL.read_text(encoding="utf-8", errors="replace")


def load_tool():
    spec = importlib.util.spec_from_file_location("engel_self_fix_improvement_candidate", TOOL)
    require(spec is not None and spec.loader is not None, "could not load self-fix improvement candidate module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_self_fix_improvement_candidate"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [TOOL, VERIFIER, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))
    for path in [LESSON_DIR, MEMORY_PROPOSAL_DIR, VERIFIER_CANDIDATE_DIR, OUTPUT_DIR]:
        require(path.exists() and path.is_dir(), "required bounded folder missing: " + str(path))
    require((OUTPUT_DIR / ".gitkeep").exists(), "bounded output folder placeholder missing")


def check_required_text() -> None:
    text = read_source() + "\n" + REPORT.read_text(encoding="utf-8", errors="replace")
    for needle in [
        "SELF_FIX_IMPROVEMENT_CANDIDATE_ONLY",
        "FROM_UNTRUSTED_RESEARCH_CHAIN",
        "NO_SELF_FIX_POLICY_UPDATE",
        "NO_SELF_FIX_RUNNER_ACTIVATION",
        "NO_VERIFIER_UPDATE",
        "NO_SOURCE_MUTATION",
        "NO_PATCH_APPLY",
        "NOT_TRUSTED_MEMORY",
        "HUMAN_REVIEW_REQUIRED",
        "NO_PROVIDER_CALLS",
        "NO_NETWORK",
        "NO_BROWSER",
        "NO_BACKGROUND_WORKER",
        "NO_RUNTIME_TRIGGER",
        "NO_AUTOMATION_TRIGGERED",
        "reports",
        "lesson_candidates",
        "memory_candidates",
        "verifier_improvement_candidates",
        "self_fix_improvement_candidates",
        "--lesson",
        "--memory-proposal",
        "--verifier-candidate",
        "--dry-run",
        "--write",
        "not self-fix policy updates",
        "not source patches",
        "not verifier updates",
        "not trusted memory",
        "do not activate a self-fix runner",
        "low-risk self-fix class",
        "high-risk stop class",
        "verifier-before-fix behavior",
        "receipt/rollback behavior",
        "escalation behavior",
        "future runner design",
    ]:
        require(needle in text, "self-fix improvement candidate missing text: " + needle)
    for field in [
        "self_fix_improvement_candidate_id",
        "source_input_type",
        "source_input_id",
        "source_input_path",
        "topic_id",
        "topic_title",
        "created_at",
        "trust_status",
        "candidate_summary",
        "candidate_details",
        "self_fix_relevance",
        "related_low_risk_classes",
        "related_high_risk_stop_classes",
        "suggested_runner_boundary",
        "suggested_verification_requirement",
        "suggested_receipt_requirement",
        "escalation_notes",
        "uncertainty_notes",
        "safety_notes",
        "required_human_review",
        "required_core_continuity_review",
        "not_trusted_memory",
        "no_self_fix_policy_update",
        "no_self_fix_runner_activation",
        "no_source_mutation",
        "no_patch_apply",
    ]:
        require(field in text, "self-fix improvement candidate missing field: " + field)


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
    forbidden_attributes = {"walk", "rglob", "unlink", "remove", "rename"}
    forbidden_names = {"exec", "eval", "__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                require(root_name not in forbidden_imports, "tool imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".")[0]
            require(root_name not in forbidden_imports, "tool imports forbidden module: " + node.module)
        if isinstance(node, ast.While):
            raise CheckFailure("tool contains while loop")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in forbidden_attributes, "tool uses forbidden call: " + node.func.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in forbidden_names, "tool uses forbidden call: " + node.func.id)


def first_lesson_candidate_name() -> str:
    for path in sorted(LESSON_DIR.iterdir()):
        if path.is_file() and path.suffix.lower() == ".md" and path.name != ".gitkeep":
            return path.name
    raise CheckFailure("no lesson candidate markdown file available for dry-run smoke")


def check_runtime_smoke() -> None:
    module = load_tool()
    out = io.StringIO()
    err = io.StringIO()
    require(module.main([], stdout=out, stderr=err) == 0, "tool no-argument usage failed")
    require("SELF_FIX_IMPROVEMENT_CANDIDATE_ONLY" in out.getvalue(), "tool usage missing required status")

    lesson_name = first_lesson_candidate_name()
    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--lesson", lesson_name, "--dry-run"], stdout=out, stderr=err) == 0, "lesson dry-run failed")
    dry_text = out.getvalue()
    for needle in [
        "SELF_FIX_IMPROVEMENT_CANDIDATE_ONLY",
        "FROM_UNTRUSTED_RESEARCH_CHAIN",
        "NO_SELF_FIX_POLICY_UPDATE",
        "NO_SELF_FIX_RUNNER_ACTIVATION",
        "NO_VERIFIER_UPDATE",
        "NO_SOURCE_MUTATION",
        "NOT_TRUSTED_MEMORY",
        "NO_AUTOMATION_TRIGGERED",
        "self_fix_improvement_candidate_id",
        "source_input_type",
        "source_input_id",
        "candidate_details",
        "suggested_runner_boundary",
    ]:
        require(needle in dry_text, "lesson dry-run missing required text: " + needle)

    for unsafe in [
        "https://example.com/file.md",
        "..\\outside.md",
        "memory\\lesson.md",
        "lesson*.md",
        "G:\\ENGEL_APP_MEMORY\\lesson.md",
        "E:\\ENGEL_APP_MEMORY\\lesson.md",
    ]:
        try:
            module.resolve_bounded_input(module.LESSON_DIR, unsafe, "Lesson candidate")
        except module.SelfFixImprovementCandidateError:
            continue
        raise CheckFailure("tool accepted unsafe input name: " + unsafe)


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_forbidden_active_behavior()
        check_runtime_smoke()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel self-fix improvement candidate verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
