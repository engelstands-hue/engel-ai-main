from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
STATUS_MODULE = ROOT / "engel_code_companion_candidate_review_status.py"
VERIFIER = ROOT / "tools" / "verify_engel_code_companion_candidate_review_gui.py"
COMPANION = ROOT / "engel_companion.py"
RESEARCH_OFFICE = ROOT / "engel_research_office.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_CANDIDATE_REVIEW_GUI_V1.md"

REQUIRED_STATUSES = [
    "CODE_COMPANION_CANDIDATE_REVIEW_GUI",
    "READ_ONLY_GUI",
    "LOCAL_ONLY",
    "CANDIDATE_QUEUE_VISIBLE",
    "PATCH_CANDIDATES_VISIBLE",
    "VERIFIER_PLANS_VISIBLE",
    "GROWTH_BRIDGE_VISIBLE",
    "CANDIDATE_ONLY",
    "PLAN_ONLY",
    "NO_PATCH_APPLY",
    "NO_SOURCE_MUTATION",
    "NO_COMMIT",
    "NO_VERIFIER_EXECUTION",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
]

REQUIRED_GUI_LABELS = [
    "Code Companion",
    "Code Companion Review",
    "Code Companion Overview",
    "Growth Bridge Status",
    "Code Companion Candidates",
    "Patch Candidates",
    "Verifier Plans",
    "Candidate-Only Boundary",
    "Blocked Actions",
    "Next Safe Steps",
]

REQUIRED_FOLDER_REFERENCES = [
    r"reports\code_companion_candidates",
    r"reports\patch_candidates",
    r"reports\verifier_plans",
]

REQUIRED_BOUNDARY_TEXT = [
    "candidates are not patches",
    "patch candidates are not applied",
    "verifier plans are not executed",
    "no source mutation",
    "no commit",
    "no trusted memory write",
    "no provider/network/browser",
    "no background workers",
]

REQUIRED_BLOCKED_ACTIONS = [
    "patch apply",
    "source mutation",
    "commit",
    "verifier execution",
    "provider/network/browser call",
    "model runtime start",
    "trusted-memory write",
    "package refresh",
    "background worker",
    "startup autorun",
]

UNSAFE_ACTION_LABELS = [
    "Apply Patch",
    "Apply",
    "Commit",
    "Run Verifier",
    "Execute",
    "Promote Memory",
    "Start Model",
    "Open Browser",
    "Package Refresh",
    "Start Worker",
    "Auto Run",
]

FORBIDDEN_IMPORTS = {
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

FORBIDDEN_CALL_ATTRIBUTES = {
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
    "copy",
    "copyfile",
    "copytree",
    "move",
    "start",
    "run",
    "Popen",
}

FORBIDDEN_CALL_NAMES = {
    "exec",
    "eval",
    "__import__",
    "apply",
    "commit",
    "execute",
    "start_worker",
    "start_model",
}

FORBIDDEN_ACTIVE_TEXT = [
    "provider call",
    "network call",
    "browser call",
    "source mutation",
    "patch apply",
    "commit implementation",
    "trusted_memory write",
    "verifier execution implementation",
    "model runtime",
    "package refresh implementation",
    "background worker",
    "startup autorun",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_status_module():
    spec = importlib.util.spec_from_file_location("engel_code_companion_candidate_review_status", STATUS_MODULE)
    require(spec is not None and spec.loader is not None, "could not load status module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_code_companion_candidate_review_status"] = module
    spec.loader.exec_module(module)
    return module


def marked_code_companion_blocks(text: str) -> str:
    pattern = re.compile(
        r"# ENGEL_CODE_COMPANION_CANDIDATE_REVIEW_GUI_V1[^\n]*_START(?P<body>.*?)"
        r"# ENGEL_CODE_COMPANION_CANDIDATE_REVIEW_GUI_V1[^\n]*_END",
        re.DOTALL,
    )
    return "\n\n".join(match.group("body") for match in pattern.finditer(text))


def code_companion_context(text: str) -> str:
    lines = text.splitlines()
    selected: list[str] = []
    for index, line in enumerate(lines):
        if "Code Companion Review" in line or "code_companion_candidate_review_status" in line:
            start = max(0, index - 3)
            end = min(len(lines), index + 4)
            selected.extend(lines[start:end])
    return "\n".join(selected)


def check_files_exist() -> None:
    for path in [STATUS_MODULE, VERIFIER]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))


def check_required_text() -> None:
    module = load_status_module()
    rendered = module.render_status()
    combined = "\n".join(
        [
            read(STATUS_MODULE),
            read(COMPANION),
            read(RESEARCH_OFFICE),
            rendered,
        ]
    )
    for status in REQUIRED_STATUSES:
        require(status in combined, "required status missing: " + status)
    for label in REQUIRED_GUI_LABELS:
        require(label in combined, "required GUI label missing: " + label)
    for folder in REQUIRED_FOLDER_REFERENCES:
        require(folder in combined, "required bounded folder reference missing: " + folder)
    lower = combined.lower()
    for text in REQUIRED_BOUNDARY_TEXT:
        require(text in lower, "required boundary text missing: " + text)
    for action in REQUIRED_BLOCKED_ACTIONS:
        require(action in lower, "required blocked action missing: " + action)
    require("non-recursive count" in combined, "non-recursive count text missing")
    require("recent filenames" in combined, "recent filenames text missing")


def check_runtime_smoke() -> None:
    module = load_status_module()
    out = io.StringIO()
    err = io.StringIO()
    code = module.main([], stdout=out, stderr=err)
    output = out.getvalue()
    require(code == 0, "status module returned nonzero")
    for needle in REQUIRED_GUI_LABELS + REQUIRED_STATUSES:
        require(needle in output, "status output missing: " + needle)
    for folder in REQUIRED_FOLDER_REFERENCES:
        require(folder in output, "status output missing folder: " + folder)
    for action in REQUIRED_BLOCKED_ACTIONS:
        require(action in output.lower(), "status output missing blocked action: " + action)

    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--write"], stdout=out, stderr=err) == 2, "status module accepted an action-like option")
    require("read-only" in err.getvalue(), "option rejection missing read-only text")


def check_status_module_has_no_active_forbidden_behavior() -> None:
    tree = ast.parse(read(STATUS_MODULE))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                require(root_name not in FORBIDDEN_IMPORTS, "status module imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".")[0]
            require(root_name not in FORBIDDEN_IMPORTS, "status module imports forbidden module: " + node.module)
        if isinstance(node, ast.While):
            raise CheckFailure("status module contains while loop")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in FORBIDDEN_CALL_ATTRIBUTES, "status module uses forbidden call: " + node.func.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in FORBIDDEN_CALL_NAMES, "status module uses forbidden call: " + node.func.id)


def check_no_unsafe_gui_actions() -> None:
    gui_context = "\n".join(
        [
            marked_code_companion_blocks(read(COMPANION)),
            marked_code_companion_blocks(read(RESEARCH_OFFICE)),
            code_companion_context(read(COMPANION)),
            code_companion_context(read(RESEARCH_OFFICE)),
        ]
    )
    require("Code Companion Review" in gui_context, "Code Companion Review GUI context missing")
    forbidden_active_patterns = [
        r"\bQPushButton\b",
        r"\bQAction\b",
        r"\.clicked\.connect",
        r"\.triggered\.connect",
        r"\bsubprocess\b",
        r"\brequests\b",
        r"\burllib\b",
        r"\bsocket\b",
        r"\bwebbrowser\b",
        r"\bopenai\b",
        r"\bthreading\b",
        r"\bmultiprocessing\b",
        r"\.write_text\s*\(",
        r"\.write_bytes\s*\(",
        r"\.unlink\s*\(",
        r"\.rglob\s*\(",
        r"\.glob\s*\(",
    ]
    for pattern in forbidden_active_patterns:
        require(re.search(pattern, gui_context) is None, "Code Companion GUI context contains active pattern: " + pattern)

    active_label_lines = [
        line
        for line in gui_context.splitlines()
        if "QPushButton" in line
        or ".clicked.connect" in line
        or "QAction" in line
        or ".triggered.connect" in line
        or "addAction" in line
    ]
    for line in active_label_lines:
        for label in UNSAFE_ACTION_LABELS:
            require(label not in line, "unsafe action label appears in active GUI line: " + label)


def check_forbidden_text_only_in_denial_context() -> None:
    module_text = read(STATUS_MODULE)
    lower_lines = module_text.lower().splitlines()
    blocked_action_terms = [action.lower() for action in REQUIRED_BLOCKED_ACTIONS]
    denial_words = [
        "no_",
        "does not",
        "not ",
        "blocked",
        "blocked_actions",
        "candidate_only_boundary",
        "summary",
    ]
    for term in FORBIDDEN_ACTIVE_TEXT:
        hits = [line for line in lower_lines if term in line]
        for line in hits:
            require(
                any(word in line for word in denial_words) or any(action in line for action in blocked_action_terms),
                "forbidden behavior term appears outside denial context: " + term,
            )


def check_report_if_present() -> None:
    if not REPORT.exists():
        return
    report = read(REPORT)
    for needle in [
        "files read first",
        "files created",
        "files updated",
        "GUI/status behavior",
        "visible sections",
        "bounded folder count behavior",
        "blocked actions",
        "status module smoke result",
        "source GUI smoke result",
        "verification commands/results",
        "focused safety scan result",
        "packaging skipped",
        "final scoped process sweep result",
        "git status summary",
    ]:
        require(needle in report, "report missing required detail: " + needle)


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_runtime_smoke()
        check_status_module_has_no_active_forbidden_behavior()
        check_no_unsafe_gui_actions()
        check_forbidden_text_only_in_denial_context()
        check_report_if_present()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel Code Companion candidate review GUI verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
