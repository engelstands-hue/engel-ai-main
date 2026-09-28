from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
LOOP = ROOT / "engel_research_to_fix_loop.py"
VERIFIER = ROOT / "tools" / "verify_engel_research_to_fix_loop.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_RESEARCH_TO_FIX_LOOP_V1.md"

REQUIRED_STATUSES = [
    "RESEARCH_TO_FIX_LOOP",
    "LOCAL_ONLY",
    "CANDIDATE_CHAIN_ONLY",
    "NO_VERIFIER_UPDATE",
    "NO_SELF_FIX_POLICY_UPDATE",
    "NO_RUNNER_ACTIVATION",
    "NO_PATCH_APPLY",
    "NO_SOURCE_MUTATION",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
]

REQUIRED_FOLDERS = [
    "reports\\self_research_notes",
    "reports\\lesson_candidates",
    "reports\\memory_candidates",
    "reports\\verifier_improvement_candidates",
    "reports\\self_fix_improvement_candidates",
]

REQUIRED_COMPONENTS = [
    "research notes",
    "lesson candidates",
    "memory candidate proposals",
    "verifier improvement candidates",
    "self-fix improvement candidates",
    "low-risk self-fix contract",
    "low-risk runner status",
    "Self-Learning Mini Runner V1",
    "Verifier Improvement Candidate V1",
    "Self-Fix Improvement Candidate V1",
    "Low-Risk Self-Fix Runner Contract V1",
    "Low-Risk Self-Fix Runner V1",
]

REQUIRED_BOUNDARIES = [
    "candidate-only boundary",
    "no apply boundary",
    "no verifier edits",
    "no self-fix policy edits",
    "no runner activation",
    "no patch apply",
    "no source mutation",
    "no trusted memory writes",
    "no provider/network/browser",
    "no background worker",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_loop() -> str:
    return LOOP.read_text(encoding="utf-8", errors="replace")


def load_loop():
    spec = importlib.util.spec_from_file_location("engel_research_to_fix_loop", LOOP)
    require(spec is not None and spec.loader is not None, "could not load research-to-fix loop module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_research_to_fix_loop"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [LOOP, VERIFIER, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))


def check_required_text() -> None:
    text = read_loop() + "\n" + REPORT.read_text(encoding="utf-8", errors="replace")
    for needle in REQUIRED_STATUSES + REQUIRED_FOLDERS + REQUIRED_COMPONENTS + REQUIRED_BOUNDARIES:
        require(needle in text, "research-to-fix loop missing required text: " + needle)
    for needle in [
        "--status",
        "--summary",
        "non-recursive counts",
        "recent file names",
        "next safe steps",
        "Status/summary only",
        "no apply behavior",
        "does not apply improvements automatically",
    ]:
        require(needle in text, "research-to-fix loop missing CLI/display text: " + needle)


def check_forbidden_active_behavior() -> None:
    tree = ast.parse(read_loop())
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
        "engel_verifier_improvement_candidate",
        "engel_self_fix_improvement_candidate",
        "engel_low_risk_self_fix_runner",
    }
    forbidden_attributes = {
        "walk",
        "rglob",
        "glob",
        "write_text",
        "write_bytes",
        "mkdir",
        "unlink",
        "remove",
        "rename",
        "replace",
        "start",
    }
    forbidden_names = {"exec", "eval", "__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                require(root_name not in forbidden_imports, "loop imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".")[0]
            require(root_name not in forbidden_imports, "loop imports forbidden module: " + node.module)
        if isinstance(node, ast.While):
            raise CheckFailure("loop contains while loop")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in forbidden_attributes, "loop uses forbidden call: " + node.func.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in forbidden_names, "loop uses forbidden call: " + node.func.id)


def check_runtime_smoke() -> None:
    module = load_loop()
    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--status"], stdout=out, stderr=err) == 0, "--status returned nonzero")
    status_output = out.getvalue()
    status_output_lower = status_output.lower()
    for needle in [
        "Engel Research-to-Fix Loop V1",
        "RESEARCH_TO_FIX_LOOP",
    ]:
        require(needle in status_output, "--status output missing: " + needle)
    for needle in [
        "research notes",
        "lesson candidates",
        "memory candidate proposals",
        "verifier improvement candidates",
        "self-fix improvement candidates",
        "low-risk self-fix",
        "candidate-only boundary",
        "no apply boundary",
    ]:
        require(needle in status_output_lower, "--status output missing: " + needle)

    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--summary"], stdout=out, stderr=err) == 0, "--summary returned nonzero")
    summary_output = out.getvalue()
    summary_output_lower = summary_output.lower()
    for needle in [
        "Engel Research-to-Fix Loop V1 Summary",
        "Total candidate files visible non-recursively",
        "NO_VERIFIER_UPDATE",
        "NO_SELF_FIX_POLICY_UPDATE",
    ]:
        require(needle in summary_output, "--summary output missing: " + needle)
    for needle in ["candidate-only boundary", "no apply boundary"]:
        require(needle in summary_output_lower, "--summary output missing: " + needle)

    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--status", "--summary"], stdout=out, stderr=err) == 2, "loop accepted mutually exclusive flags")


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_forbidden_active_behavior()
        check_runtime_smoke()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel research-to-fix loop verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
