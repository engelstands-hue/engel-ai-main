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
SWARM_TRAILS_CONFIG_PATH = APP_ROOT / "memory" / "SWARM_TRAILS_V1.json"
ROUTE_VERIFICATION_MANIFEST_PATH = APP_ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
SWARM_TRAILS_REPORT_DIR = APP_ROOT / "reports" / "swarm_trails"
SWARM_TRAILS_REPORT_GLOB = "swarm_trails_preview_*.md"

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

EXPECTED_SOURCES = {
    "worker_ant_reports",
    "colony_reports",
    "project_history",
    "checkpoints",
}
EXPECTED_TYPES = {
    "same_task_family",
    "same_safety_gate",
    "approval_dependency",
    "checkpoint_to_report_link",
}
STATUS_TOKENS = [
    "READ_ONLY",
    "DRY_RUN",
    "swarm trails",
    "preview",
    "APPROVE_REPORT",
    "report-only",
    "relationship previews",
    "trusted memory writes blocked",
    "source edits blocked",
    "learning apply blocked",
    "queue mutation blocked",
    "digest/history writes blocked",
    "ALIVE_STATE writes blocked",
    "provider calls blocked",
    "background processes blocked",
]
PREVIEW_TOKENS = [
    "READ_ONLY",
    "DRY_RUN",
    "no-write",
    "local-only",
    "capped preview",
    "trail sources",
    "trail types",
    "relationship preview",
    "Engel remains one companion identity",
    "no autonomous behavior enabled",
    "provider calls blocked",
    "background processes blocked",
]
REPORT_TOKENS = [
    "READ_ONLY",
    "REPORT_ONLY",
    "APPROVE_REPORT",
    "local-only",
    "capped preview",
    "trail_sources",
    "trail_types",
    "relationship preview",
    "Engel remains one companion identity",
    "no autonomous behavior enabled",
    "no background processes",
    "provider calls blocked",
    "trusted memory writes blocked",
    "source edits blocked",
    "learning apply blocked",
    "queue mutation blocked",
    "digest/history writes blocked",
    "ALIVE_STATE writes blocked",
    "Ollama removal preserved",
    "ChatGPT/Gemini provider gates unchanged",
]
VERIFICATION_SET_STATUS_TOKENS = [
    "READ_ONLY",
    "STATUS_ONLY",
    "DISPLAY_ONLY",
    "does not run verifiers",
    "does not execute route-regression matrix entries",
    "does not generate reports",
    "Standard verifier set",
    "tools\\verify_hive_mind_worker_ants.py",
    "tools\\verify_colony_routes.py",
    "tools\\verify_swarm_trails_preview.py",
    "swarm trails preview",
    "swarm trails preview APPROVE_REPORT",
    "should_execute_in_test: false",
    "report-generating routes are documented, not auto-executed",
    "no background workers",
    "no live research",
    "no provider calls",
    "trusted memory writes blocked",
    "source edits blocked",
    "learning apply blocked",
    "queue mutation blocked",
    "digest/history writes blocked",
    "ALIVE_STATE writes blocked",
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


def assert_only_allowed_swarm_report(
    before: dict[str, dict[str, object]], after: dict[str, dict[str, object]], report: Path
) -> None:
    rel = str(report.relative_to(APP_ROOT))
    report_dir_rel = str(SWARM_TRAILS_REPORT_DIR.relative_to(APP_ROOT))
    reports_rel = str((APP_ROOT / "reports").relative_to(APP_ROOT))
    diff = diff_snapshot(before, after)
    allowed_new = {rel, report_dir_rel}
    allowed_modified = {reports_rel, report_dir_rel}
    unexpected_new = [path for path in diff["new"] if path not in allowed_new]
    unexpected_modified = [
        path for path in diff["modified"] if path not in NORMAL_CLI_LOG_WRITES and path not in allowed_modified
    ]
    if unexpected_new or diff["removed"] or unexpected_modified:
        scoped = {**diff, "new": unexpected_new, "modified": unexpected_modified}
        raise CheckFailure("approved swarm trails report changed unexpected entries: " + format_diff(scoped))


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


def swarm_report_files() -> set[Path]:
    if not SWARM_TRAILS_REPORT_DIR.exists():
        return set()
    return {path.resolve() for path in SWARM_TRAILS_REPORT_DIR.glob(SWARM_TRAILS_REPORT_GLOB) if path.is_file()}


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


def check_py_compile() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "py_compile",
            str(APP_ROOT / "engel_app.py"),
            str(APP_ROOT / "engel_companion.py"),
            str(APP_ROOT / "engel_research_brain_v2.py"),
            str(APP_ROOT / "tools" / "verify_swarm_trails_preview.py"),
        ],
        cwd=str(APP_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if proc.returncode != 0:
        raise CheckFailure("py_compile failed\n" + (proc.stdout or "") + (proc.stderr or ""))


def check_config_schema() -> None:
    if not SWARM_TRAILS_CONFIG_PATH.exists():
        raise CheckFailure("missing swarm trails config: " + str(SWARM_TRAILS_CONFIG_PATH))
    data = json.loads(SWARM_TRAILS_CONFIG_PATH.read_text(encoding="utf-8"))
    required = {
        "version": "V1",
        "mode": "READ_ONLY",
        "report_only": True,
        "colony_identity": "Engel",
        "one_companion_identity": True,
        "trusted_memory_writes": False,
        "source_edits": False,
        "learning_apply": False,
        "queue_mutation": False,
        "digest_history_writes": False,
        "alive_state_writes": False,
        "provider_calls": False,
        "background_processes": False,
        "shutdown_with_engel": True,
    }
    for key, expected in required.items():
        if data.get(key) != expected:
            raise CheckFailure(f"swarm config {key} expected {expected!r}, got {data.get(key)!r}")
    if int(data.get("max_preview_files", 999)) > 40:
        raise CheckFailure("max_preview_files must remain <= 40")
    if int(data.get("max_lines_per_file", 999)) > 8:
        raise CheckFailure("max_lines_per_file must remain <= 8")
    trail_sources = data.get("trail_sources")
    trail_types = data.get("trail_types")
    if not isinstance(trail_sources, list) or not trail_sources:
        raise CheckFailure("trail_sources must be a non-empty list")
    if not isinstance(trail_types, list) or not trail_types:
        raise CheckFailure("trail_types must be a non-empty list")
    missing_sources = sorted(EXPECTED_SOURCES - set(trail_sources))
    missing_types = sorted(EXPECTED_TYPES - set(trail_types))
    if missing_sources:
        raise CheckFailure("missing trail_sources: " + ", ".join(missing_sources))
    if missing_types:
        raise CheckFailure("missing trail_types: " + ", ".join(missing_types))


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
        "_swarm_trails_config",
        "_swarm_bool",
        "_swarm_int",
        "_swarm_list",
        "_swarm_trails_config_lines",
        "_swarm_trails_blocked_lines",
        "_swarm_trail_scan_dirs",
        "_swarm_trail_allowed_file",
        "_swarm_trail_header",
        "_swarm_trail_family",
        "_swarm_trail_relationship_title",
        "_swarm_trails_scan",
        "_swarm_trails_preview_text",
        "swarm_trails_status",
        "_swarm_trails_report_path",
        "swarm_trails_preview",
    ]
    route_source = "\n".join(function_slice(research_text, name) for name in route_functions)
    app_wrapper_source = source_between(app_text, "def swarm_trails_status", "def worker_ants_architecture")
    route_dispatch_source = source_between(app_text, 'if lower_msg == "swarm trails status"', 'if lower_msg == "worker ants architecture approve_report"')
    combined = route_source + "\n" + app_wrapper_source + "\n" + route_dispatch_source

    provider_hits = [pattern for pattern in PROVIDER_CALL_PATTERNS if pattern in combined]
    if provider_hits:
        raise CheckFailure("provider/live-research pattern found in swarm trail source slice: " + ", ".join(provider_hits))

    background_hits = [pattern for pattern in BACKGROUND_PATTERNS if pattern in combined]
    if background_hits:
        raise CheckFailure("background pattern found in swarm trail source slice: " + ", ".join(background_hits))

    for pattern in FORBIDDEN_DIRECT_WRITE_PATTERNS:
        if re.search(pattern, route_source):
            raise CheckFailure("forbidden direct write pattern found in swarm trail source slice: " + pattern)

    write_text_occurrences = combined.count("write_text")
    if write_text_occurrences != combined.count("report_path.write_text"):
        raise CheckFailure("unexpected write_text occurrence in swarm trail source slice")
    mkdir_occurrences = combined.count(".mkdir(")
    if mkdir_occurrences != combined.count("SWARM_TRAILS_REPORTS_DIR.mkdir("):
        raise CheckFailure("unexpected mkdir occurrence in swarm trail source slice")
    status_source = function_slice(research_text, "swarm_trails_status")
    for pattern in ["write_text", "open(", "json.dump", ".mkdir(", "subprocess.", "requests.", "urllib."]:
        if pattern in status_source:
            raise CheckFailure("swarm_trails_status contains forbidden status-route pattern: " + pattern)


def check_route_regression_matrix_docs() -> None:
    app_text = (APP_ROOT / "engel_app.py").read_text(encoding="utf-8", errors="ignore")
    if '"command": "swarm trails preview"' not in app_text:
        raise CheckFailure("route regression cases missing swarm trails preview")
    if '"command": "swarm trails preview APPROVE_REPORT"' not in app_text:
        raise CheckFailure("route regression cases missing swarm trails preview APPROVE_REPORT")
    if "READ_ONLY_DRY_RUN_LOCAL_ONLY_NO_WRITE" not in app_text:
        raise CheckFailure("route regression cases missing dry-run/no-write classification")
    if "APPROVE_REPORT_REPORT_ONLY_LOCAL_ONLY" not in app_text:
        raise CheckFailure("route regression cases missing APPROVE_REPORT report-only classification")
    if "should_execute_in_test" not in app_text or '"should_execute_in_test": False' not in app_text:
        raise CheckFailure("route regression matrix should_execute_in_test false rendering missing")

    manifest_path = APP_ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
    if not manifest_path.exists():
        raise CheckFailure("missing route verification manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("route_regression_matrix_entries")
    if not isinstance(entries, list):
        raise CheckFailure("manifest route_regression_matrix_entries must be a list")
    by_command = {str(entry.get("command", "")): entry for entry in entries if isinstance(entry, dict)}
    for command in ["swarm trails preview", "swarm trails preview APPROVE_REPORT"]:
        entry = by_command.get(command)
        if not entry:
            raise CheckFailure("manifest missing route regression entry: " + command)
        if entry.get("should_execute_in_test") is not False:
            raise CheckFailure("manifest should_execute_in_test must be false for " + command)

    status_output = run_engel("route regression status")
    assert_contains_ci(status_output, "REPORT_FOUND", "route regression status")
    assert_contains_ci(status_output, "Does not execute verifier scripts", "route regression status")
    assert_contains_ci(status_output, "does not run the scripts", "route regression status")


def check_verification_set_status_source_guard() -> None:
    app_text = (APP_ROOT / "engel_app.py").read_text(encoding="utf-8", errors="ignore")
    route_source = "\n".join(
        function_slice(app_text, name)
        for name in [
            "_route_verification_set_path_v1",
            "_route_verification_bool_v1",
            "verification_set_status_v1",
        ]
    )
    dispatch_source = source_between(
        app_text,
        'if msg.lower().strip() == "verification set status"',
        'if msg.lower().strip() in ["router status"',
    )
    combined = route_source + "\n" + dispatch_source

    provider_hits = [pattern for pattern in PROVIDER_CALL_PATTERNS if pattern in combined]
    if provider_hits:
        raise CheckFailure("provider/live-research pattern found in verification-set status source slice: " + ", ".join(provider_hits))

    background_hits = [pattern for pattern in BACKGROUND_PATTERNS if pattern in combined]
    if background_hits:
        raise CheckFailure("background pattern found in verification-set status source slice: " + ", ".join(background_hits))

    forbidden_patterns = [
        r"write_file\(",
        r"append_file\(",
        r"append_log\(",
        r"json\.dump\(",
        r"\.write_text\(",
        r"\.mkdir\(",
        r"subprocess\.",
        r"requests\.",
        r"urllib\.",
        r"ALIVE_STATE_FILE",
        r"QUEUE_FILE",
        r"ARCHIVE_DIR",
        r"report_path",
    ]
    for pattern in forbidden_patterns:
        if re.search(pattern, combined):
            raise CheckFailure("forbidden pattern found in verification-set status source slice: " + pattern)


def run_verification_set_status_no_write() -> None:
    if not ROUTE_VERIFICATION_MANIFEST_PATH.exists():
        raise CheckFailure("missing route verification manifest")
    before_tree = snapshot_sensitive_tree()
    before_thought_files = snapshot_thought_inbox()
    before_thought_count = thought_inbox_count()
    output = run_engel("verification set status")
    after_tree = snapshot_sensitive_tree()
    for token in VERIFICATION_SET_STATUS_TOKENS:
        assert_contains_ci(output, token, "verification set status")
    assert_no_tree_change(before_tree, after_tree, "verification set status")
    assert_thought_inbox_unchanged(before_thought_count, before_thought_files, "verification set status")


def run_status_no_write() -> None:
    before_tree = snapshot_sensitive_tree()
    before_thought_files = snapshot_thought_inbox()
    before_thought_count = thought_inbox_count()
    output = run_engel("swarm trails status")
    after_tree = snapshot_sensitive_tree()
    for token in STATUS_TOKENS:
        assert_contains_ci(output, token, "swarm trails status")
    assert_no_tree_change(before_tree, after_tree, "swarm trails status")
    assert_thought_inbox_unchanged(before_thought_count, before_thought_files, "swarm trails status")


def run_preview_no_write() -> None:
    before_tree = snapshot_sensitive_tree()
    before_thought_files = snapshot_thought_inbox()
    before_thought_count = thought_inbox_count()
    before_reports = swarm_report_files()
    output = run_engel("swarm trails preview")
    after_tree = snapshot_sensitive_tree()
    for token in PREVIEW_TOKENS:
        assert_contains_ci(output, token, "swarm trails preview")
    if swarm_report_files() != before_reports:
        raise CheckFailure("swarm trails preview wrote a report without APPROVE_REPORT")
    assert_no_tree_change(before_tree, after_tree, "swarm trails preview")
    assert_thought_inbox_unchanged(before_thought_count, before_thought_files, "swarm trails preview")


def run_approved_report_only() -> Path:
    before_tree = snapshot_sensitive_tree()
    before_forbidden = snapshot_forbidden()
    before_thought_files = snapshot_thought_inbox()
    before_thought_count = thought_inbox_count()
    before_reports = swarm_report_files()
    output = run_engel("swarm trails preview APPROVE_REPORT")
    after_tree = snapshot_sensitive_tree()
    after_forbidden = snapshot_forbidden()
    after_reports = swarm_report_files()
    new_reports = sorted(after_reports - before_reports)
    if len(new_reports) != 1:
        raise CheckFailure(f"expected exactly one new swarm trails report, got {len(new_reports)}")
    report = new_reports[0]
    if report.parent.resolve() != SWARM_TRAILS_REPORT_DIR.resolve():
        raise CheckFailure("swarm trails report was written outside reports\\swarm_trails: " + str(report))
    assert_contains_ci(output, "# Swarm Trails Preview Report Written", "swarm trails preview APPROVE_REPORT")
    assert_contains_ci(output, "Status: REPORT_ONLY", "swarm trails preview APPROVE_REPORT")
    assert_only_allowed_swarm_report(before_tree, after_tree, report)
    forbidden_diff = diff_snapshot(before_forbidden, after_forbidden)
    if forbidden_diff["new"] or forbidden_diff["removed"] or forbidden_diff["modified"]:
        raise CheckFailure("approved swarm trails report changed forbidden targets: " + format_diff(forbidden_diff))
    assert_thought_inbox_unchanged(before_thought_count, before_thought_files, "swarm trails preview APPROVE_REPORT")

    report_text = report.read_text(encoding="utf-8", errors="ignore")
    for token in REPORT_TOKENS:
        assert_contains_ci(report_text, token, "generated swarm trails report")
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
        pass_check("py_compile_swarm_trails_targets")

        check_config_schema()
        pass_check("swarm_trails_config_schema_content_guard")

        check_staged_inactive()
        pass_check("STAGED_DRAFT_ACTIVE_false")

        check_no_staged_activation_literal()
        pass_check("no_STAGED_DRAFT_ACTIVE_true_literal")

        check_no_active_old_provider()
        pass_check("no_active_old_provider_matches")

        check_source_slice_guards()
        pass_check("swarm_trails_source_slice_provider_background_forbidden_write_guards")

        check_verification_set_status_source_guard()
        pass_check("verification_set_status_source_slice_provider_background_forbidden_write_guards")

        check_route_regression_matrix_docs()
        pass_check("route_regression_matrix_docs_include_swarm_trails_nonexecuting_entries")

        run_verification_set_status_no_write()
        pass_check("verification_set_status_display_only_no_write")

        run_status_no_write()
        pass_check("swarm_trails_status_content_thought_guard_no_write")

        run_preview_no_write()
        pass_check("swarm_trails_preview_dry_run_no_write")

        generated_report = run_approved_report_only()
        pass_check("swarm_trails_preview_approved_one_report_only_with_tokens")

        check_learning_apply_blocked_no_write()
        pass_check("learning_apply_remains_blocked_no_write")

        print("")
        print("SWARM_TRAILS_PREVIEW_VERIFICATION_PASS")
        print("generated_swarm_trails_report=" + str(generated_report))
        print("sensitive_roots_checked=" + ",".join(str(path.relative_to(APP_ROOT)) for path in SENSITIVE_ROOTS))
        print("forbidden_targets_checked=" + str(len(FORBIDDEN_TARGETS)))
        return 0
    except CheckFailure as exc:
        print("")
        print("SWARM_TRAILS_PREVIEW_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
