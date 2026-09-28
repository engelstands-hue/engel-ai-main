from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "engel_ai_growth_dashboard.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_growth_dashboard.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_GROWTH_DASHBOARD_V1.md"

REQUIRED_STATUSES = [
    "AI_GROWTH_DASHBOARD",
    "READ_ONLY_VIEW",
    "LOCAL_ONLY",
    "SELF_RESEARCH_VISIBLE",
    "CANDIDATE_LEARNING_VISIBLE",
    "MEMORY_PROMOTION_VISIBLE",
    "VERIFIER_IMPROVEMENT_VISIBLE",
    "SELF_FIX_IMPROVEMENT_VISIBLE",
    "LOW_RISK_SELF_FIX_VISIBLE",
    "RESEARCH_TO_FIX_VISIBLE",
    "NO_ACTION_EXECUTION",
    "NO_MEMORY_WRITE",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_VERIFIER_UPDATE",
    "NO_SELF_FIX_POLICY_UPDATE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
    "NO_MODEL_RUNTIME",
    "NO_PACKAGE_REFRESH",
    "NO_STARTUP_AUTORUN",
    "NO_RUNTIME_TRIGGER",
]

REQUIRED_SECTIONS = [
    "Engel AI Growth Overview",
    "What Engel Can Do Now",
    "What Engel Can Only Propose",
    "What Still Requires Approval",
    "Candidate Learning Status",
    "Memory Promotion Status",
    "Low-Risk Self-Fix Status",
    "Research-to-Fix Status",
    "Safety Blocks",
    "Next Safe Steps",
]

USER_FRIENDLY_LABELS = [
    "LIVE IN APP",
    "READ ONLY",
    "CANDIDATE ONLY",
    "NOT TRUSTED MEMORY",
    "APPROVAL REQUIRED",
    "SAFE TO VIEW",
    "BLOCKED BY SAFETY",
    "NO NETWORK",
    "NO BACKGROUND WORKER",
    "NO MODEL RUNTIME",
]

REQUIRED_COMPONENTS = [
    "Engel Self-Research Contract V1",
    "Engel Self-Research Topic Library V1",
    "Engel Untrusted Research Note Generator V1",
    "Engel Research Note Viewer V1",
    "Engel Lesson Candidate Extractor V1",
    "Engel Research Memory Candidate Proposal V1",
    "Engel Self-Learning Mini Runner V1",
    "Engel Self-Learning Status Surface V1",
    "Engel Bounded Self-Learning Scheduler V1",
    "Engel Candidate Review Dashboard V1",
    "Engel Approved Memory Promotion Contract V1",
    "Engel Memory Promotion Writer V1",
    "Engel Verifier Improvement Candidate V1",
    "Engel Self-Fix Improvement Candidate V1",
    "Engel Low-Risk Self-Fix Runner Contract V1",
    "Engel Low-Risk Self-Fix Runner V1",
    "Engel Low-Risk Self-Fix Status Surface V1",
    "Engel Self-Fix Receipt Viewer V1",
    "Engel Research-to-Fix Loop V1",
    "Engel Daily Cycle Runner V1",
    "Engel Learning, Memory Promotion, and Self-Fix V2 Consolidation",
]

REQUIRED_FOLDERS = [
    "reports\\self_research_notes",
    "reports\\lesson_candidates",
    "reports\\memory_candidates",
    "reports\\verifier_improvement_candidates",
    "reports\\self_fix_improvement_candidates",
    "reports\\self_fix_receipts",
    "reports\\self_learning_scheduler_receipts",
    "reports\\memory_promotion_receipts",
    "reports\\daily_cycle_receipts",
]

REQUIRED_BOUNDARIES = [
    "research notes are not memory",
    "lesson candidates are not approved lessons",
    "memory candidate proposals are not trusted memory",
    "verifier improvement candidates do not update verifiers",
    "self-fix improvement candidates do not update self-fix policy",
    "low-risk self-fix runner only handles pre-approved safe classes",
    "memory promotion requires approval token",
    "daily cycle is bounded and foreground only",
    "no provider/network/browser behavior is active",
    "no background worker/startup autorun is active",
    "no model runtime is active",
    "no package refresh",
    "no learning run is started",
    "no self-fix run is started",
    "no memory promotion is started",
    "no trusted memory write is performed",
    "no source mutation is performed",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_dashboard() -> str:
    return DASHBOARD.read_text(encoding="utf-8", errors="replace")


def read_report() -> str:
    if not REPORT.exists():
        return ""
    return REPORT.read_text(encoding="utf-8", errors="replace")


def load_dashboard():
    spec = importlib.util.spec_from_file_location("engel_ai_growth_dashboard", DASHBOARD)
    require(spec is not None and spec.loader is not None, "could not load dashboard module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_ai_growth_dashboard"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [DASHBOARD, VERIFIER, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))


def check_required_text() -> None:
    text = read_dashboard() + "\n" + read_report() + "\n" + load_dashboard().render_dashboard()
    for needle in REQUIRED_STATUSES + REQUIRED_SECTIONS + USER_FRIENDLY_LABELS + REQUIRED_COMPONENTS + REQUIRED_FOLDERS + REQUIRED_BOUNDARIES:
        require(needle in text, "AI growth dashboard coverage missing: " + needle)
    for needle in [
        "read known project files",
        "non-recursive count",
        "Last Known Report Paths",
        "Current Output Folders",
        "Next Safe Steps",
        "python engel_ai_growth_dashboard.py",
    ]:
        require(needle in text, "AI growth dashboard display text missing: " + needle)


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
        "engel_bounded_self_learning_scheduler",
        "engel_memory_promotion_writer",
        "engel_low_risk_self_fix_runner",
        "engel_research_to_fix_loop",
        "engel_verifier_improvement_candidate",
        "engel_self_fix_improvement_candidate",
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
        "rmdir",
        "rename",
        "replace",
        "start",
    }
    forbidden_names = {
        "exec",
        "eval",
        "__import__",
        "run_dry",
        "run_write_candidates",
        "write_candidate",
        "write_proposal",
        "write_receipt",
        "apply",
        "commit",
    }
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
        "Engel AI Growth Dashboard V1",
        "AI_GROWTH_DASHBOARD",
        "Engel AI Growth Overview",
        "What Engel Can Do Now",
        "What Engel Can Only Propose",
        "What Still Requires Approval",
        "Candidate Learning Status",
        "Memory Promotion Status",
        "Low-Risk Self-Fix Status",
        "Research-to-Fix Status",
        "Safety Blocks",
        "Current Output Folders",
        "Next Safe Steps",
        "reports\\self_research_notes",
        "reports\\memory_candidates",
        "reports\\self_fix_receipts",
        "LIVE IN APP",
        "READ ONLY",
        "CANDIDATE ONLY",
        "NOT TRUSTED MEMORY",
        "APPROVAL REQUIRED",
        "SAFE TO VIEW",
        "BLOCKED BY SAFETY",
        "NO NETWORK",
        "NO BACKGROUND WORKER",
        "NO MODEL RUNTIME",
        "research notes are not memory",
        "lesson candidates are not approved lessons",
        "memory candidate proposals are not trusted memory",
        "verifier improvement candidates do not update verifiers",
        "self-fix improvement candidates do not update self-fix policy",
        "daily cycle is bounded and foreground only",
        "no provider/network/browser behavior is active",
        "no background worker/startup autorun is active",
    ]:
        require(needle in output, "dashboard output missing: " + needle)

    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--run"], stdout=out, stderr=err) == 2, "dashboard accepted an action-like option")
    require("read-only" in err.getvalue(), "dashboard option rejection missing read-only text")


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_forbidden_active_behavior()
        check_runtime_smoke()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel AI growth dashboard verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
