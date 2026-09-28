from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "engel_candidate_review_dashboard.py"
VERIFIER = ROOT / "tools" / "verify_engel_candidate_review_dashboard.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CANDIDATE_REVIEW_DASHBOARD_V1.md"

REQUIRED_SECTIONS = [
    "Candidate Counts",
    "Review-Only Candidate Types",
    "What Can Be Viewed",
    "What Requires Approval",
    "What Is Not Done Here",
    "Safe Next Steps",
    "Blocked Actions",
]

REQUIRED_CANDIDATE_TYPES = [
    "research notes",
    "lesson candidates",
    "memory candidate proposals",
    "verifier improvement candidates",
    "self-fix improvement candidates",
    "self-fix receipts",
    "daily cycle receipts",
    "scheduler receipts",
]

REQUIRED_LABELS = [
    "VIEW ONLY",
    "CANDIDATE ONLY",
    "NOT TRUSTED MEMORY",
    "APPROVAL REQUIRED",
    "NO PROMOTION HERE",
    "NO PATCH APPLY HERE",
    "NO VERIFIER UPDATE HERE",
    "NO SELF-FIX POLICY UPDATE HERE",
    "NO SOURCE MUTATION HERE",
]

REQUIRED_BOUNDARY_TEXT = [
    "candidate review does not approve memory",
    "candidate review does not promote memory",
    "candidate review does not apply patches",
    "candidate review does not update verifiers",
    "candidate review does not update self-fix policy",
    "candidate review does not run self-fix",
    "candidate review does not call providers/network/browser",
    "candidate review does not start background workers",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_dashboard() -> str:
    return DASHBOARD.read_text(encoding="utf-8", errors="replace")


def load_dashboard():
    spec = importlib.util.spec_from_file_location("engel_candidate_review_dashboard", DASHBOARD)
    require(spec is not None and spec.loader is not None, "could not load dashboard module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_candidate_review_dashboard"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [DASHBOARD, VERIFIER, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))


def check_required_text() -> None:
    rendered = load_dashboard().render_dashboard()
    text = read_dashboard() + "\n" + REPORT.read_text(encoding="utf-8", errors="replace") + "\n" + rendered
    for needle in [
        "CANDIDATE_REVIEW_DASHBOARD",
        "READ_ONLY_VIEW",
        "CANDIDATE_OUTPUTS_VISIBLE",
        "NO_APPROVAL_ACTION",
        "NO_PROMOTION_ACTION",
        "NO_MEMORY_WRITE",
        "NO_SOURCE_MUTATION",
        "NO_VERIFIER_UPDATE",
        "NO_SELF_FIX_POLICY_UPDATE",
        "NO_PROVIDER_CALLS",
        "NO_NETWORK",
        "NO_BROWSER",
        "NO_BACKGROUND_WORKER",
        "reports\\self_research_notes",
        "reports\\lesson_candidates",
        "reports\\memory_candidates",
        "reports\\verifier_improvement_candidates",
        "reports\\self_fix_improvement_candidates",
        "reports\\self_fix_receipts",
        "reports\\daily_cycle_receipts",
        "reports\\self_learning_scheduler_receipts",
        "non-recursive",
        "recent file names",
        "recent candidate filenames",
        "VIEW ONLY",
        "CANDIDATE ONLY",
        "NOT TRUSTED MEMORY",
        "APPROVAL REQUIRED",
        "NO PROMOTION HERE",
        "NO PATCH APPLY HERE",
        "NO VERIFIER UPDATE HERE",
        "NO SELF-FIX POLICY UPDATE HERE",
        "NO SOURCE MUTATION HERE",
        "candidate review does not approve memory",
        "candidate review does not promote memory",
        "candidate review does not apply patches",
        "candidate review does not update verifiers",
        "candidate review does not update self-fix policy",
        "candidate review does not run self-fix",
        "candidate review does not call providers/network/browser",
        "candidate review does not start background workers",
        "no approval action",
        "promotion action",
        "no trusted memory write",
        "no source mutation",
        "no verifier update",
        "no self-fix policy update",
        "patch apply",
        "no provider/network/browser",
        "no background worker",
        "Safe Next Steps",
        "Blocked Actions",
        "python engel_candidate_review_dashboard.py",
    ] + REQUIRED_SECTIONS + REQUIRED_CANDIDATE_TYPES + REQUIRED_LABELS + REQUIRED_BOUNDARY_TEXT:
        require(needle in text, "dashboard coverage missing: " + needle)


def check_forbidden_active_behavior() -> None:
    tree = ast.parse(read_dashboard())
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
        "engel_verifier_improvement_candidate",
        "engel_self_fix_improvement_candidate",
        "engel_research_memory_candidate_proposal",
        "engel_memory_promotion_writer",
    }
    forbidden_attributes = {
        "walk",
        "rglob",
        "glob",
        "write_text",
        "write_bytes",
        "unlink",
        "remove",
        "rmdir",
        "rename",
        "replace",
        "mkdir",
        "start",
        "run",
    }
    forbidden_names = {"exec", "eval", "__import__", "approve", "promote", "apply", "commit"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                require(root_name not in forbidden_imports, "dashboard imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".")[0]
            require(root_name not in forbidden_imports, "dashboard imports forbidden module: " + node.module)
        if isinstance(node, ast.While):
            raise CheckFailure("dashboard contains while loop")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in forbidden_attributes, "dashboard uses forbidden call: " + node.func.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in forbidden_names, "dashboard uses forbidden call: " + node.func.id)


def check_runtime_smoke() -> None:
    module = load_dashboard()
    out = io.StringIO()
    err = io.StringIO()
    code = module.main([], stdout=out, stderr=err)
    output = out.getvalue()
    require(code == 0, "dashboard returned nonzero")
    for needle in [
        "Engel Candidate Review Dashboard V1",
        "CANDIDATE_REVIEW_DASHBOARD",
        "VIEW ONLY",
        "CANDIDATE ONLY",
        "NOT TRUSTED MEMORY",
        "APPROVAL REQUIRED",
        "NO PROMOTION HERE",
        "NO PATCH APPLY HERE",
        "NO VERIFIER UPDATE HERE",
        "NO SELF-FIX POLICY UPDATE HERE",
        "NO SOURCE MUTATION HERE",
        "reports\\self_research_notes",
        "reports\\lesson_candidates",
        "reports\\memory_candidates",
        "reports\\verifier_improvement_candidates",
        "reports\\self_fix_improvement_candidates",
        "reports\\self_fix_receipts",
        "reports\\daily_cycle_receipts",
        "reports\\self_learning_scheduler_receipts",
        "Candidate Counts",
        "Review-Only Candidate Types",
        "What Can Be Viewed",
        "What Requires Approval",
        "What Is Not Done Here",
        "Safe Next Steps",
        "Blocked Actions",
        "candidate review does not approve memory",
        "candidate review does not promote memory",
        "candidate review does not apply patches",
        "candidate review does not update verifiers",
        "candidate review does not update self-fix policy",
        "candidate review does not run self-fix",
        "candidate review does not call providers/network/browser",
        "candidate review does not start background workers",
    ]:
        require(needle in output, "dashboard output missing: " + needle)

    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--approve"], stdout=out, stderr=err) == 2, "dashboard accepted an action-like option")
    require("takes no actions" in err.getvalue(), "dashboard option rejection missing read-only text")


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_forbidden_active_behavior()
        check_runtime_smoke()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel candidate review dashboard verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
