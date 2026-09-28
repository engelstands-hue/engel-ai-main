from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SURFACE = ROOT / "engel_self_learning_status_surface.py"
VERIFIER = ROOT / "tools" / "verify_engel_self_learning_status_surface.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_SELF_LEARNING_STATUS_SURFACE_V1.md"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_surface() -> str:
    return SURFACE.read_text(encoding="utf-8", errors="replace")


def load_surface():
    spec = importlib.util.spec_from_file_location("engel_self_learning_status_surface", SURFACE)
    require(spec is not None and spec.loader is not None, "could not load status surface module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_self_learning_status_surface"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [SURFACE, VERIFIER, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))


def check_required_text() -> None:
    text = read_surface() + "\n" + REPORT.read_text(encoding="utf-8", errors="replace")
    for needle in [
        "STATUS_SURFACE_ONLY",
        "READ_ONLY_VIEW",
        "SELF_LEARNING_CHAIN_VISIBLE",
        "CANDIDATE_OUTPUTS_VISIBLE",
        "NO_LEARNING_RUN",
        "NO_MEMORY_WRITE",
        "NO_SOURCE_MUTATION",
        "NO_VERIFIER_UPDATE",
        "NO_SELF_FIX_POLICY_UPDATE",
        "NO_PROVIDER_CALLS",
        "NO_NETWORK",
        "NO_BROWSER",
        "NO_BACKGROUND_WORKER",
        "Untrusted Research Note Generator V1",
        "Research Note Viewer V1",
        "Lesson Candidate Extractor V1",
        "Research Memory Candidate Proposal V1",
        "Self-Learning Mini Runner V1",
        "reports\\self_research_notes",
        "reports\\lesson_candidates",
        "reports\\memory_candidates",
        "one-topic/one-source rule",
        "untrusted/candidate-only boundary",
        "no trusted memory boundary",
        "no source/verifier/self-fix mutation boundary",
        "no learning run",
        "no generated artifacts",
        "no provider/network/browser",
        "no recursive scan",
        "python engel_self_learning_status_surface.py",
    ]:
        require(needle in text, "status surface coverage missing: " + needle)


def check_forbidden_active_behavior() -> None:
    tree = ast.parse(read_surface())
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
        "engel_self_learning_mini_runner",
        "engel_untrusted_research_note_generator",
        "engel_lesson_candidate_extractor",
        "engel_research_memory_candidate_proposal",
    }
    forbidden_names = {
        "write_text",
        "unlink",
        "remove",
        "rename",
        "replace",
        "mkdir",
        "rmdir",
        "rglob",
        "glob",
        "walk",
        "run_dry",
        "run_write_candidates",
        "write_note",
        "write_candidate",
        "write_proposal",
        "write_receipt",
        "build_note_from_topic_and_source",
        "build_lesson_candidate",
        "build_memory_candidate_proposal",
        "exec",
        "eval",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                require(root_name not in forbidden_imports, "surface imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".")[0]
            require(root_name not in forbidden_imports, "surface imports forbidden module: " + node.module)
        if isinstance(node, ast.While):
            raise CheckFailure("surface contains while loop")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in forbidden_names, "surface uses forbidden call: " + node.func.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in forbidden_names, "surface uses forbidden call: " + node.func.id)


def check_runtime_smoke() -> None:
    module = load_surface()
    out = io.StringIO()
    code = module.main([], stdout=out)
    output = out.getvalue()
    require(code == 0, "status surface returned nonzero")
    for needle in [
        "Engel Self-Learning Mini Runner Status Surface V1",
        "STATUS_SURFACE_ONLY",
        "Untrusted Research Note Generator V1",
        "reports\\self_research_notes",
        "one-topic/one-source rule",
        "no trusted memory boundary",
        "no learning run",
    ]:
        require(needle in output, "status surface output missing: " + needle)


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_forbidden_active_behavior()
        check_runtime_smoke()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel self-learning status surface verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
