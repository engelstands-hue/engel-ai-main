from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "engel_research_note_viewer.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_RESEARCH_NOTE_VIEWER_V1.md"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_source() -> str:
    return VIEWER.read_text(encoding="utf-8", errors="replace")


def load_module():
    spec = importlib.util.spec_from_file_location("engel_research_note_viewer", VIEWER)
    require(spec is not None and spec.loader is not None, "could not load viewer module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_research_note_viewer"] = module
    spec.loader.exec_module(module)
    return module


def check_required_text() -> None:
    require(VIEWER.exists(), "engel_research_note_viewer.py missing")
    text = read_source()
    for needle in [
        "READ_ONLY_VIEWER",
        "UNTRUSTED_RESEARCH_NOTE_VIEW_ONLY",
        "LOCAL_ONLY",
        "BOUNDED_REPORTS_ONLY",
        "NO_MEMORY_WRITE",
        "NO_PATCH_APPLY",
        "NO_SOURCE_MUTATION",
        "NO_EXECUTION",
        "NO_TRAINING",
        "NO_INDEXING",
        "NO_EMBEDDING",
        "NO_PROVIDER_CALLS",
        "NO_NETWORK",
        "NO_BROWSER",
        "NO_BACKGROUND_WORKER",
        "reports",
        "self_research_notes",
        "--list",
        "--show",
        "does not edit notes",
        "does not edit notes, delete notes, write memory",
    ]:
        require(needle in text, "viewer missing required text: " + needle)
    for field in [
        "research_note_id",
        "topic_id",
        "topic_title",
        "topic_category",
        "source_paths_or_references",
        "trust_status",
        "research_question",
        "short_summary",
        "key_observations",
        "uncertainty_notes",
        "source_risk_notes",
        "prompt_injection_risk_notes",
        "possible_lesson_candidates",
        "possible_verifier_improvement_candidates",
        "possible_self_fix_improvement_candidates",
        "possible_memory_candidate_summary",
        "memory_boundary",
        "execution_boundary",
        "training_boundary",
        "next_safe_manual_step",
        "required_review_before_use",
        "no_trusted_memory_write",
    ]:
        require(field in text, "viewer missing display field: " + field)


def check_report_text() -> None:
    require(REPORT.exists() and REPORT.is_file(), "ENGEL_RESEARCH_NOTE_VIEWER_V1.md report missing")
    text = REPORT.read_text(encoding="utf-8", errors="replace")
    for needle in [
        "Engel Research Note Viewer V1",
        "Files read first",
        "viewer behavior",
        "read-only boundary",
        "verification results",
        "smoke result",
        "safety scan result",
        "final process sweep",
        "git status",
        "READ_ONLY_VIEWER",
        "UNTRUSTED_RESEARCH_NOTE_VIEW_ONLY",
        "LOCAL_ONLY",
        "BOUNDED_REPORTS_ONLY",
        "NO_MEMORY_WRITE",
        "NO_PATCH_APPLY",
        "NO_SOURCE_MUTATION",
        "NO_EXECUTION",
        "NO_TRAINING",
        "NO_INDEXING",
        "NO_EMBEDDING",
        "NO_PROVIDER_CALLS",
        "NO_NETWORK",
        "NO_BROWSER",
        "NO_BACKGROUND_WORKER",
        "python engel_research_note_viewer.py --list",
        "python engel_research_note_viewer.py --show <note-file-name>",
        "reads only reports\\self_research_notes",
        "no edit/delete/write behavior",
        "no trusted memory write",
        "no provider/network/browser",
        "no indexing/training/execution",
        "no background worker",
    ]:
        require(needle in text, "viewer report missing text: " + needle)


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
                require(root_name not in forbidden_imports, "viewer imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".")[0]
            require(root_name not in forbidden_imports, "viewer imports forbidden module: " + node.module)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in {"walk", "rglob", "remove", "unlink", "write_text"}, "viewer uses forbidden call: " + node.func.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in {"exec", "eval", "__import__"}, "viewer uses forbidden call: " + node.func.id)


def check_runtime_smoke() -> None:
    module = load_module()
    out = io.StringIO()
    err = io.StringIO()
    require(module.main([], stdout=out, stderr=err) == 0, "viewer no-argument usage failed")
    require("READ_ONLY_VIEWER" in out.getvalue(), "viewer usage missing read-only status")
    out = io.StringIO()
    require(module.main(["--list"], stdout=out, stderr=err) == 0, "viewer --list failed")
    for unsafe in ["https://example.com/file.md", "..\\outside.md", "memory\\note.md", "note*.md", "G:\\ENGEL_APP_MEMORY\\note.md"]:
        try:
            module.resolve_note_path(unsafe)
        except module.ResearchNoteViewerError:
            continue
        raise CheckFailure("viewer accepted unsafe note name: " + unsafe)


def main() -> int:
    try:
        check_required_text()
        check_report_text()
        check_forbidden_active_behavior()
        check_runtime_smoke()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel research note viewer verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
