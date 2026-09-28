from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "engel_self_learning_mini_runner.py"
VERIFIER = ROOT / "tools" / "verify_engel_self_learning_mini_runner.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_SELF_LEARNING_MINI_RUNNER_V1.md"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_source() -> str:
    return RUNNER.read_text(encoding="utf-8", errors="replace")


def load_runner():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_self_learning_mini_runner", RUNNER)
    require(spec is not None and spec.loader is not None, "could not load runner module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_self_learning_mini_runner"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [RUNNER, VERIFIER, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))


def check_required_text() -> None:
    text = read_source()
    for needle in [
        "SELF_LEARNING_MINI_RUNNER",
        "LOCAL_ONLY",
        "ONE_TOPIC_ONE_SOURCE_ONLY",
        "CANDIDATE_LEARNING_ONLY",
        "UNTRUSTED_OUTPUTS_ONLY",
        "NOT_TRUSTED_MEMORY",
        "NO_TRUSTED_MEMORY_WRITE",
        "NO_SOURCE_MUTATION",
        "NO_VERIFIER_UPDATE",
        "NO_SELF_FIX_POLICY_UPDATE",
        "NO_PROVIDER_CALLS",
        "NO_NETWORK",
        "NO_BROWSER",
        "NO_AUTO_DOWNLOADS",
        "NO_AUTO_INDEXING",
        "NO_MODEL_TRAINING",
        "NO_RUNTIME_TRIGGER",
        "NO_BACKGROUND_WORKER",
        "--demo",
        "--topic-id",
        "--source",
        "--dry-run",
        "--write-candidates",
        "len(values) != 1",
        "one topic per run",
        "one source per run",
        "validate_source_path",
        "reject URLs",
        "reject UNC paths",
        "reject paths outside project root",
        "reject external drives",
        "reject wildcards",
        "reject live/staging artifacts",
        "reject model folders",
        "no folder scanning",
        "no trusted-memory paths",
    ]:
        require(needle in text, "runner missing required text: " + needle)
    for label in [
        "UNTRUSTED",
        "CANDIDATE_ONLY",
        "NOT_TRUSTED_MEMORY",
        "NO_AUTOMATION_TRIGGERED",
        "HUMAN_REVIEW_REQUIRED",
    ]:
        require(label in text, "runner missing output label: " + label)
    for field in [
        "self_learning_run_id",
        "topic_id",
        "source",
        "research_note_path",
        "lesson_candidate_path",
        "memory_candidate_proposal_path",
        "trust_status",
        "outputs_created",
        "safety_boundary",
        "next_safe_step",
    ]:
        require(field in text, "runner missing receipt field: " + field)


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
                require(root_name not in forbidden_imports, "runner imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".")[0]
            require(root_name not in forbidden_imports, "runner imports forbidden module: " + node.module)
        if isinstance(node, ast.While):
            raise CheckFailure("runner contains while loop")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in {"walk", "rglob", "unlink", "remove"}, "runner uses forbidden call: " + node.func.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in {"exec", "eval", "__import__"}, "runner uses forbidden call: " + node.func.id)


def check_runtime_smoke() -> None:
    runner = load_runner()
    out = io.StringIO()
    err = io.StringIO()
    require(runner.main([], stdout=out, stderr=err) == 0, "runner no-argument usage failed")
    require("SELF_LEARNING_MINI_RUNNER" in out.getvalue(), "runner usage missing status")
    out = io.StringIO()
    require(runner.main(["--demo"], stdout=out, stderr=err) == 0, "runner demo failed")
    demo_text = out.getvalue()
    for needle in ["UNTRUSTED", "CANDIDATE_ONLY", "NOT_TRUSTED_MEMORY", "HUMAN_REVIEW_REQUIRED"]:
        require(needle in demo_text, "runner demo missing label: " + needle)
    out = io.StringIO()
    topic_id = "SRT-01-01-python_error_handling_patterns_for_local_tools"
    require(
        runner.main(["--topic-id", topic_id, "--source", "memory\\ENGEL_SELF_RESEARCH_CONTRACT_V1.md", "--dry-run"], stdout=out, stderr=err) == 0,
        "runner dry-run failed",
    )
    dry_text = out.getvalue()
    require("DRY_RUN" in dry_text and "memory_candidate_proposal_id" in dry_text, "runner dry-run missing expected preview")
    out = io.StringIO()
    require(
        runner.main(["--topic-id", topic_id, "--topic-id", topic_id, "--source", "memory\\ENGEL_SELF_RESEARCH_CONTRACT_V1.md", "--dry-run"], stdout=out, stderr=err) == 1,
        "runner accepted repeated topic id",
    )
    out = io.StringIO()
    require(
        runner.main(["--topic-id", topic_id, "--source", "memory\\ENGEL_SELF_RESEARCH_CONTRACT_V1.md", "--source", "memory\\ENGEL_CORE_CONTINUITY_MAP_V1.md", "--dry-run"], stdout=out, stderr=err) == 1,
        "runner accepted repeated source",
    )


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_forbidden_active_behavior()
        check_runtime_smoke()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel self-learning mini runner verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
