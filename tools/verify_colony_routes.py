from __future__ import annotations

import hashlib
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    APP_ROOT = Path.cwd()
else:
    try:
        APP_ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        APP_ROOT = Path.cwd()
ENGEL_APP = APP_ROOT / "engel_app.py"
COLONY_CONFIG_PATH = APP_ROOT / "memory" / "ENGEL_COLONY_ARCHITECTURE_V1.json"
COLONY_REPORT_DIR = APP_ROOT / "reports" / "colony"
COLONY_REPORT_GLOB = "colony_architecture_*.md"

COLONY_ROUTES = {
    "colony status": "# Colony Status",
    "colony nests status": "# Colony Nests Status",
    "colony queens status": "# Colony Queens Status",
    "colony safety status": "# Colony Safety Status",
}

EXPECTED_NESTS = {
    "chat_memory_nest",
    "thought_seed_nest",
    "research_report_nest",
    "approved_lesson_nest",
    "swarm_trail_nest",
    "project_history_nest",
    "guardian_nest",
}
EXPECTED_QUEENS = {
    "companion_queen",
    "memory_queen",
    "research_queen",
    "safety_queen",
    "load_queen",
}
EXPECTED_WORKERS = {
    "memory_forager",
    "research_scout",
    "lesson_nurse",
    "trail_mapper",
    "gate_guardian",
    "load_sentinel",
    "history_scribe",
    "context_weaver",
    "proposal_builder",
}
EXPECTED_FORBIDDEN = {
    "trusted_memory_writes",
    "source_edits",
    "learning_apply",
    "queue_mutation",
    "digest_history_writes",
    "alive_state_writes",
    "background_processes",
    "provider_calls_when_research_off",
}

ACTIVE_OLD_PROVIDER_FILES = [
    APP_ROOT / "engel_app.py",
    APP_ROOT / "engel_companion.py",
    APP_ROOT / "engel_research_brain_v2.py",
    APP_ROOT / "memory" / "ENGEL_COMMANDS.md",
    APP_ROOT / "memory" / "BRAIN_BACKENDS.json",
    APP_ROOT / "memory" / "BRAIN_BACKEND_LAYER_V1.md",
    APP_ROOT / "memory" / "OFFLINE_BRAIN_GUARD_V1.md",
    APP_ROOT / "memory" / "ENGEL_BRAIN_RULES.md",
    APP_ROOT / "prompts" / "ENGEL_SYSTEM.md",
]
OLD_PROVIDER_PATTERNS = [
    "Ollama",
    "ollama",
    "localhost:11434",
    "11434",
]
STAGED_ACTIVATION_FILES = [
    APP_ROOT / "engel_app.py",
    APP_ROOT / "engel_research_brain_v2.py",
]

SENSITIVE_ROOTS = [
    APP_ROOT / "memory",
    APP_ROOT / "reports",
]
NORMAL_CLI_LOG_WRITES = {
    "memory\\MAIN_AGENT_LOG.md",
}
THOUGHT_INBOX_FILES = [
    APP_ROOT / "memory" / "COMPANION_THOUGHT_INBOX_V2MIND_A.json",
    APP_ROOT / "reports" / "mind" / "COMPANION_THOUGHT_INBOX_V2MIND_A.md",
]
FORBIDDEN_TARGETS = [
    APP_ROOT / "memory" / "ALIVE_STATE.json",
    APP_ROOT / "memory" / "LEARNING_LOG.md",
    APP_ROOT / "memory" / "RESEARCH_NOTES.md",
    *THOUGHT_INBOX_FILES,
    APP_ROOT / "memory" / "OVERNIGHT_TOPIC_ROTATION.json",
    APP_ROOT / "memory" / "overnight_runner_single_instance_v2runnera.lock",
    APP_ROOT / "prompts" / "ENGEL_SYSTEM.md",
    APP_ROOT / "engel_app.py",
    APP_ROOT / "engel_research_brain_v2.py",
    APP_ROOT / "reports" / "overnight" / "OVERNIGHT_QUEUE.md",
    APP_ROOT / "reports" / "overnight" / "OVERNIGHT_RUNNER_STATUS.md",
    APP_ROOT / "reports" / "research" / "LEARNING_PROPOSALS.md",
    APP_ROOT / "reports" / "research" / "RESEARCH_QUEUE_CLEANUP_LATEST.md",
    APP_ROOT / "reports" / "research" / "NEXT_BEST_TOPIC.md",
    APP_ROOT / "reports" / "research" / "RESEARCH_DIGEST_LATEST.md",
    APP_ROOT / "reports" / "research" / "RESEARCH_TOPIC_HISTORY.md",
    APP_ROOT / "reports" / "research" / "learning_proposals_archive",
    APP_ROOT / "reports" / "OVERNIGHT_RESEARCH_LOOP_HISTORY.jsonl",
    APP_ROOT / "reports" / "OVERNIGHT_TOPIC_ROTATION_STATUS.md",
    APP_ROOT / "reports" / "overnight" / "proposal_harvest",
]

PROVIDER_CALL_PATTERNS = [
    "requests.",
    "urllib.",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "_chatgpt_",
    "_gemini_",
    "_brain_text_result",
    "ask_brain_provider",
    "research_search",
    "source_search",
    "research_completion_digest(",
    "research_runner",
    "research_goals_hook_select",
]
BACKGROUND_PATTERNS = [
    "subprocess.Popen",
    "threading.Thread",
    "multiprocessing",
    "schedule.",
    "while True",
    "daemon=True",
    "start_new_session",
    "DETACHED_PROCESS",
]
FORBIDDEN_DIRECT_WRITE_PATTERNS = [
    r"ALIVE_STATE_FILE\.(write_text|open|unlink|replace)",
    r"QUEUE_FILE\.(write_text|open|unlink|replace)",
    r"RESEARCH_DIGEST_LATEST_FILE\.(write_text|open|unlink|replace)",
    r"RESEARCH_TOPIC_HISTORY_FILE\.(write_text|open|unlink|replace)",
    r"PROPOSALS_FILE\.(write_text|open|unlink|replace)",
    r"ARCHIVE_DIR\.(mkdir|write_text|open|unlink|replace)",
    r"LEARNING_LOG\.(write_text|open)",
    r"RESEARCH_NOTES\.(write_text|open)",
    r"write_file\(",
    r"json\.dump\(",
]

COMMON_STATUS_TOKENS = [
    "READ_ONLY",
    "DRY_RUN",
    "Engel",
    "one companion identity",
    "research toggle",
    "10",
    "shutdown_with_engel",
    "no background processes",
    "provider calls blocked",
    "trusted memory writes blocked",
    "source edits blocked",
    "learning apply blocked",
    "queue mutation blocked",
    "digest/history writes blocked",
    "ALIVE_STATE writes blocked",
]
ROUTE_TOKENS = {
    "colony status": COMMON_STATUS_TOKENS + ["idle_intensity_percent"],
    "colony nests status": [
        "READ_ONLY",
        "DRY_RUN",
        "nests",
        "chat_memory_nest",
        "thought_seed_nest",
        "research_report_nest",
        "approved_lesson_nest",
        "swarm_trail_nest",
        "project_history_nest",
        "guardian_nest",
        "proposal_first",
        "approval_gated",
        "report_only",
    ],
    "colony queens status": [
        "READ_ONLY",
        "DRY_RUN",
        "queens",
        "companion_queen",
        "memory_queen",
        "research_queen",
        "safety_queen",
        "load_queen",
        "separate_personality=False",
        "one companion identity",
    ],
    "colony safety status": COMMON_STATUS_TOKENS
    + [
        "STAGED_DRAFT_ACTIVE",
        "False",
        "old-provider removal remains preserved",
    ],
    "colony architecture": [
        "READ_ONLY",
        "DRY_RUN",
        "No colony report was written",
        "nests",
        "queens",
        "workers",
        "swarm trails",
        "approval-gated",
        "shutdown_with_engel",
        "Engel remains one companion identity",
    ],
}
REPORT_TOKENS = [
    "READ_ONLY",
    "REPORT_ONLY",
    "APPROVE_REPORT",
    "Engel",
    "one Engel companion identity",
    "nests",
    "queens",
    "workers",
    "swarm trails",
    "research toggle",
    "idle intensity",
    "shutdown_with_engel",
    "no background processes",
    "provider calls blocked",
    "trusted memory writes blocked",
    "source edits blocked",
    "learning apply blocked",
    "queue mutation blocked",
    "digest/history writes blocked",
    "ALIVE_STATE writes blocked",
    "STAGED_DRAFT_ACTIVE False",
    "Ollama removal preserved",
    "ChatGPT/Gemini provider gates unchanged",
    "no autonomous behavior enabled",
]


class CheckFailure(Exception):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_signature(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"exists": False}
    if path.is_file():
        stat = path.stat()
        return {
            "exists": True,
            "type": "file",
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": sha256(path),
        }
    if path.is_dir():
        stat = path.stat()
        return {
            "exists": True,
            "type": "dir",
            "mtime_ns": stat.st_mtime_ns,
            "file_count": len([p for p in path.rglob("*") if p.is_file()]),
        }
    return {"exists": True, "type": "other"}


def snapshot_sensitive_tree() -> dict[str, dict[str, object]]:
    snapshot: dict[str, dict[str, object]] = {}
    for root in SENSITIVE_ROOTS:
        if not root.exists():
            snapshot[str(root.relative_to(APP_ROOT))] = {"exists": False}
            continue
        snapshot[str(root.relative_to(APP_ROOT))] = file_signature(root)
        for path in sorted(root.rglob("*")):
            if path.is_file() or path.is_dir():
                snapshot[str(path.relative_to(APP_ROOT))] = file_signature(path)
    return snapshot


def snapshot_forbidden() -> dict[str, dict[str, object]]:
    return {str(path.relative_to(APP_ROOT)): file_signature(path) for path in FORBIDDEN_TARGETS}


def diff_snapshot(
    before: dict[str, dict[str, object]], after: dict[str, dict[str, object]]
) -> dict[str, list[str]]:
    before_keys = set(before)
    after_keys = set(after)
    return {
        "new": sorted(after_keys - before_keys),
        "removed": sorted(before_keys - after_keys),
        "modified": sorted(key for key in before_keys & after_keys if before[key] != after[key]),
    }


def format_diff(diff: dict[str, list[str]]) -> str:
    parts = []
    for key in ["new", "removed", "modified"]:
        if diff[key]:
            parts.append(key + ": " + ", ".join(diff[key][:20]))
    return "; ".join(parts) or "no changes"


def assert_no_tree_change(before: dict[str, dict[str, object]], after: dict[str, dict[str, object]], label: str) -> None:
    diff = diff_snapshot(before, after)
    unexpected_modified = [path for path in diff["modified"] if path not in NORMAL_CLI_LOG_WRITES]
    if diff["new"] or diff["removed"] or unexpected_modified:
        diff = {**diff, "modified": unexpected_modified}
        raise CheckFailure(label + " changed sensitive tree: " + format_diff(diff))


def assert_only_allowed_colony_report(
    before: dict[str, dict[str, object]], after: dict[str, dict[str, object]], report: Path
) -> None:
    rel = str(report.relative_to(APP_ROOT))
    diff = diff_snapshot(before, after)
    allowed_new = {rel}
    allowed_modified = {str(COLONY_REPORT_DIR.relative_to(APP_ROOT)), str((APP_ROOT / "reports").relative_to(APP_ROOT))}
    unexpected_new = [path for path in diff["new"] if path not in allowed_new]
    unexpected_modified = [
        path for path in diff["modified"] if path not in NORMAL_CLI_LOG_WRITES and path not in allowed_modified
    ]
    if unexpected_new or diff["removed"] or unexpected_modified:
        scoped = {**diff, "new": unexpected_new, "modified": unexpected_modified}
        raise CheckFailure("approved colony report changed unexpected entries: " + format_diff(scoped))


def thought_inbox_count() -> int:
    path = APP_ROOT / "memory" / "COMPANION_THOUGHT_INBOX_V2MIND_A.json"
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CheckFailure("thought inbox JSON could not be read: " + str(exc))
    thoughts = data.get("thoughts", [])
    if not isinstance(thoughts, list):
        raise CheckFailure("thought inbox JSON has non-list thoughts")
    return len(thoughts)


def snapshot_thought_inbox() -> dict[str, dict[str, object]]:
    return {str(path.relative_to(APP_ROOT)): file_signature(path) for path in THOUGHT_INBOX_FILES}


def assert_thought_inbox_unchanged(before_count: int, before_files: dict[str, dict[str, object]], label: str) -> None:
    after_count = thought_inbox_count()
    after_files = snapshot_thought_inbox()
    if before_count != after_count:
        raise CheckFailure(f"{label} changed thought inbox count {before_count} -> {after_count}")
    diff = diff_snapshot(before_files, after_files)
    if diff["new"] or diff["removed"] or diff["modified"]:
        raise CheckFailure(label + " changed thought inbox files: " + format_diff(diff))


def colony_report_files() -> set[Path]:
    if not COLONY_REPORT_DIR.exists():
        return set()
    return {path.resolve() for path in COLONY_REPORT_DIR.glob(COLONY_REPORT_GLOB) if path.is_file()}


def run_engel(command: str) -> str:
    proc = subprocess.run(
        [sys.executable, str(ENGEL_APP)],
        input=command + "\nexit\n",
        cwd=str(APP_ROOT),
        capture_output=True,
        text=True,
        timeout=90,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise CheckFailure(f"{command}: Engel exited with {proc.returncode}\n{output}")
    return output


def assert_contains_ci(text: str, needle: str, label: str) -> None:
    if needle.lower() not in text.lower():
        raise CheckFailure(f"{label}: missing {needle!r}")


def assert_any_ci(text: str, needles: list[str], label: str) -> None:
    lower = text.lower()
    if not any(needle.lower() in lower for needle in needles):
        raise CheckFailure(f"{label}: missing one of {needles!r}")


def check_py_compile() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "py_compile",
            str(APP_ROOT / "engel_app.py"),
            str(APP_ROOT / "engel_companion.py"),
            str(APP_ROOT / "engel_research_brain_v2.py"),
            str(APP_ROOT / "tools" / "verify_colony_routes.py"),
        ],
        cwd=str(APP_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if proc.returncode != 0:
        raise CheckFailure("py_compile failed\n" + (proc.stdout or "") + (proc.stderr or ""))


def check_config_schema() -> None:
    if not COLONY_CONFIG_PATH.exists():
        raise CheckFailure("missing colony config: " + str(COLONY_CONFIG_PATH))
    data = json.loads(COLONY_CONFIG_PATH.read_text(encoding="utf-8"))
    required = {
        "version": "V1",
        "colony_identity": "Engel",
        "mode": "READ_ONLY",
        "report_only": True,
        "one_companion_identity": True,
        "research_toggle_default": False,
        "idle_intensity_percent": 10,
        "allow_background_processes": False,
        "shutdown_with_engel": True,
        "provider_calls_when_research_off": False,
        "trusted_memory_writes": False,
        "source_edits": False,
        "learning_apply": False,
        "queue_mutation": False,
        "digest_history_writes": False,
        "alive_state_writes": False,
    }
    for key, expected in required.items():
        if data.get(key) != expected:
            raise CheckFailure(f"colony config {key} expected {expected!r}, got {data.get(key)!r}")
    if int(data.get("research_on_intensity_percent", 999)) > 60:
        raise CheckFailure("research_on_intensity_percent must remain <= 60")
    nests = data.get("nests")
    queens = data.get("queens")
    workers = data.get("workers")
    forbidden = data.get("forbidden_without_explicit_approval")
    if not isinstance(nests, list) or not nests:
        raise CheckFailure("nests must be a non-empty list")
    if not isinstance(queens, list) or not queens:
        raise CheckFailure("queens must be a non-empty list")
    if not isinstance(workers, list) or not workers:
        raise CheckFailure("workers must be a non-empty list")
    if not isinstance(forbidden, list) or not forbidden:
        raise CheckFailure("forbidden_without_explicit_approval must be a non-empty list")
    nest_ids = {str(nest.get("id", "")) for nest in nests if isinstance(nest, dict)}
    queen_ids = {str(queen.get("id", "")) for queen in queens if isinstance(queen, dict)}
    missing_nests = sorted(EXPECTED_NESTS - nest_ids)
    missing_queens = sorted(EXPECTED_QUEENS - queen_ids)
    missing_workers = sorted(EXPECTED_WORKERS - set(workers))
    missing_forbidden = sorted(EXPECTED_FORBIDDEN - set(forbidden))
    if missing_nests:
        raise CheckFailure("missing colony nests: " + ", ".join(missing_nests))
    if missing_queens:
        raise CheckFailure("missing colony queens: " + ", ".join(missing_queens))
    if missing_workers:
        raise CheckFailure("missing colony workers: " + ", ".join(missing_workers))
    if missing_forbidden:
        raise CheckFailure("missing forbidden approvals: " + ", ".join(missing_forbidden))
    for queen in queens:
        if not isinstance(queen, dict):
            raise CheckFailure("queen entry must be an object")
        if queen.get("separate_personality") is not False:
            raise CheckFailure("queen separate_personality must be false: " + str(queen.get("id", "")))


def check_staged_inactive() -> None:
    sys.path.insert(0, str(APP_ROOT))
    module = importlib.import_module("engel_research_brain_v2")
    active = getattr(module, "STAGED_DRAFT_ACTIVE", None)
    if active is not False:
        raise CheckFailure(f"STAGED_DRAFT_ACTIVE expected False, got {active!r}")


def check_no_staged_activation_literal() -> None:
    regex = re.compile(r"STAGED_DRAFT_ACTIVE\s*=\s*True")
    matches = []
    for path in STAGED_ACTIVATION_FILES:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                matches.append(f"{path.relative_to(APP_ROOT)}:{lineno}:{line.strip()}")
    if matches:
        raise CheckFailure("unsafe staged activation literal found:\n" + "\n".join(matches))


def check_no_active_old_provider() -> None:
    regex = re.compile("|".join(re.escape(item) for item in OLD_PROVIDER_PATTERNS), re.IGNORECASE)
    matches = []
    for path in ACTIVE_OLD_PROVIDER_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                matches.append(f"{path.relative_to(APP_ROOT)}:{lineno}:{line.strip()}")
    if matches:
        raise CheckFailure("active old-provider matches found:\n" + "\n".join(matches[:20]))


def function_slice(text: str, name: str) -> str:
    match = re.search(r"(?m)^def " + re.escape(name) + r"\(", text)
    if not match:
        raise CheckFailure("function not found: " + name)
    next_match = re.search(r"(?m)^def \w+\(", text[match.end() :])
    if not next_match:
        return text[match.start() :]
    return text[match.start() : match.end() + next_match.start()]


def source_between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise CheckFailure("source marker not found: " + start_marker)
    end = text.find(end_marker, start)
    if end < 0:
        return text[start:]
    return text[start:end]


def check_source_slice_guards() -> None:
    research_text = (APP_ROOT / "engel_research_brain_v2.py").read_text(encoding="utf-8", errors="ignore")
    app_text = (APP_ROOT / "engel_app.py").read_text(encoding="utf-8", errors="ignore")
    route_functions = [
        "_colony_config",
        "_colony_bool",
        "_colony_list",
        "_colony_summary_lines",
        "_colony_blocked_lines",
        "_colony_nest_lines",
        "_colony_queen_lines",
        "_colony_worker_lines",
        "colony_status",
        "colony_nests_status",
        "colony_queens_status",
        "colony_safety_status",
        "_colony_architecture_preview",
        "_colony_architecture_report_path",
        "colony_architecture",
    ]
    route_source = "\n".join(function_slice(research_text, name) for name in route_functions)
    app_wrapper_source = source_between(app_text, "def colony_status", "# ----------------------------------------------------------------------\n# Research Thinking")
    route_dispatch_source = source_between(app_text, 'if lower_msg == "colony status"', "thought_source_v2mind_a =")
    combined = route_source + "\n" + app_wrapper_source + "\n" + route_dispatch_source

    provider_hits = [pattern for pattern in PROVIDER_CALL_PATTERNS if pattern in combined]
    if provider_hits:
        raise CheckFailure("provider/live-research pattern found in colony source slice: " + ", ".join(provider_hits))

    background_hits = [pattern for pattern in BACKGROUND_PATTERNS if pattern in combined]
    if background_hits:
        raise CheckFailure("background pattern found in colony source slice: " + ", ".join(background_hits))

    for pattern in FORBIDDEN_DIRECT_WRITE_PATTERNS:
        if re.search(pattern, route_source):
            raise CheckFailure("forbidden direct write pattern found in colony source slice: " + pattern)

    write_text_occurrences = combined.count("write_text")
    if write_text_occurrences != combined.count("report_path.write_text"):
        raise CheckFailure("unexpected write_text occurrence in colony source slice")
    mkdir_occurrences = combined.count(".mkdir(")
    if mkdir_occurrences != combined.count("COLONY_REPORTS_DIR.mkdir("):
        raise CheckFailure("unexpected mkdir occurrence in colony source slice")
    for status_name in ["colony_status", "colony_nests_status", "colony_queens_status", "colony_safety_status"]:
        source = function_slice(research_text, status_name)
        for pattern in ["write_text", "open(", "json.dump", ".mkdir(", "subprocess.", "requests.", "urllib."]:
            if pattern in source:
                raise CheckFailure(f"{status_name} contains forbidden status-route pattern: {pattern}")


def assert_route_tokens(output: str, command: str) -> None:
    for token in ROUTE_TOKENS[command]:
        assert_contains_ci(output, token, command)
    if command == "colony status":
        assert_any_ci(output, ["idle intensity", "idle_intensity_percent"], command)
    if command == "colony safety status":
        assert_any_ci(
            output,
            ["old-provider removal remains preserved", "Active old-provider removal remains preserved"],
            command,
        )


def run_route_no_write(command: str, expected_title: str) -> None:
    before_tree = snapshot_sensitive_tree()
    before_thought_files = snapshot_thought_inbox()
    before_thought_count = thought_inbox_count()
    output = run_engel(command)
    after_tree = snapshot_sensitive_tree()
    assert_contains_ci(output, expected_title, command)
    assert_route_tokens(output, command)
    assert_no_tree_change(before_tree, after_tree, command)
    assert_thought_inbox_unchanged(before_thought_count, before_thought_files, command)


def run_architecture_no_write() -> None:
    before_tree = snapshot_sensitive_tree()
    before_thought_files = snapshot_thought_inbox()
    before_thought_count = thought_inbox_count()
    before_reports = colony_report_files()
    output = run_engel("colony architecture")
    after_tree = snapshot_sensitive_tree()
    assert_contains_ci(output, "# Colony Architecture Preview", "colony architecture")
    assert_route_tokens(output, "colony architecture")
    if colony_report_files() != before_reports:
        raise CheckFailure("colony architecture wrote a report without APPROVE_REPORT")
    assert_no_tree_change(before_tree, after_tree, "colony architecture")
    assert_thought_inbox_unchanged(before_thought_count, before_thought_files, "colony architecture")


def run_architecture_approved_report_only() -> Path:
    before_tree = snapshot_sensitive_tree()
    before_forbidden = snapshot_forbidden()
    before_thought_files = snapshot_thought_inbox()
    before_thought_count = thought_inbox_count()
    before_reports = colony_report_files()
    output = run_engel("colony architecture APPROVE_REPORT")
    after_tree = snapshot_sensitive_tree()
    after_forbidden = snapshot_forbidden()
    after_reports = colony_report_files()
    new_reports = sorted(after_reports - before_reports)
    if len(new_reports) != 1:
        raise CheckFailure(f"expected exactly one new colony report, got {len(new_reports)}")
    report = new_reports[0]
    if report.parent.resolve() != COLONY_REPORT_DIR.resolve():
        raise CheckFailure("colony report was written outside reports\\colony: " + str(report))
    assert_contains_ci(output, "# Colony Architecture Report Written", "colony architecture APPROVE_REPORT")
    assert_contains_ci(output, "Status: REPORT_ONLY", "colony architecture APPROVE_REPORT")
    assert_only_allowed_colony_report(before_tree, after_tree, report)
    forbidden_diff = diff_snapshot(before_forbidden, after_forbidden)
    if forbidden_diff["new"] or forbidden_diff["removed"] or forbidden_diff["modified"]:
        raise CheckFailure("approved colony report changed forbidden targets: " + format_diff(forbidden_diff))
    assert_thought_inbox_unchanged(before_thought_count, before_thought_files, "colony architecture APPROVE_REPORT")

    report_text = report.read_text(encoding="utf-8", errors="ignore")
    for token in REPORT_TOKENS:
        assert_contains_ci(report_text, token, "generated colony report")
    return report


def check_learning_apply_blocked_no_write() -> None:
    before_tree = snapshot_sensitive_tree()
    output = run_engel("learning proposals apply")
    after_tree = snapshot_sensitive_tree()
    assert_contains_ci(output, "# Learning Proposal Apply Blocked", "learning proposals apply")
    assert_contains_ci(output, "No learning was applied.", "learning proposals apply")
    assert_no_tree_change(before_tree, after_tree, "learning proposals apply")


def main() -> int:
    generated_report = None

    def pass_check(label: str) -> None:
        print("PASS " + label)

    try:
        check_py_compile()
        pass_check("py_compile_colony_verifier_targets")

        check_config_schema()
        pass_check("colony_config_schema_content_guard")

        check_staged_inactive()
        pass_check("STAGED_DRAFT_ACTIVE_false")

        check_no_staged_activation_literal()
        pass_check("no_STAGED_DRAFT_ACTIVE_true_literal")

        check_no_active_old_provider()
        pass_check("no_active_old_provider_matches")

        check_source_slice_guards()
        pass_check("colony_source_slice_provider_background_forbidden_write_guards")

        for command, title in COLONY_ROUTES.items():
            run_route_no_write(command, title)
            pass_check(command.replace(" ", "_") + "_content_thought_guard_no_write")

        run_architecture_no_write()
        pass_check("colony_architecture_dry_run_no_write")

        generated_report = run_architecture_approved_report_only()
        pass_check("colony_architecture_approved_one_report_only_with_tokens")

        check_learning_apply_blocked_no_write()
        pass_check("learning_apply_remains_blocked_no_write")

        print("")
        print("COLONY_ROUTE_VERIFICATION_PASS")
        print("generated_colony_report=" + str(generated_report))
        print("sensitive_roots_checked=" + ",".join(str(path.relative_to(APP_ROOT)) for path in SENSITIVE_ROOTS))
        print("forbidden_targets_checked=" + str(len(FORBIDDEN_TARGETS)))
        return 0
    except CheckFailure as exc:
        print("")
        print("COLONY_ROUTE_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
