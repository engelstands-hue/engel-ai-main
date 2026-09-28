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
CONFIG_PATH = APP_ROOT / "memory" / "HIVE_MIND_WORKER_ANTS_V1.json"
COLONY_CONFIG_PATH = APP_ROOT / "memory" / "ENGEL_COLONY_ARCHITECTURE_V1.json"
WORKER_REPORT_DIR = APP_ROOT / "reports" / "worker_ants"
WORKER_REPORT_GLOB = "worker_ants_architecture_*.md"
COLONY_REPORT_DIR = APP_ROOT / "reports" / "colony"
COLONY_REPORT_GLOB = "colony_architecture_*.md"

STATUS_ROUTES = {
    "hive mind status": "# Hive Mind Status",
    "worker ants status": "# Worker Ants Status",
    "research toggle status": "# Research Toggle Status",
    "swarm trails status": "# Swarm Trails Status",
}
COLONY_STATUS_ROUTES = {
    "colony status": "# Colony Status",
    "colony nests status": "# Colony Nests Status",
    "colony queens status": "# Colony Queens Status",
    "colony safety status": "# Colony Safety Status",
}
REQUIRED_REPORT_TOKENS = [
    "READ_ONLY",
    "REPORT_ONLY",
    "APPROVE_REPORT",
    "research_toggle",
    "idle_intensity_percent",
    "shutdown_with_engel",
    "no background processes",
    "trusted memory writes blocked",
    "source edits blocked",
    "learning apply blocked",
    "queue mutation blocked",
    "digest/history writes blocked",
    "ALIVE_STATE writes blocked",
]
COLONY_REPORT_TOKENS = [
    "READ_ONLY",
    "REPORT_ONLY",
    "APPROVE_REPORT",
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
    "Ollama removal preserved",
]
EXPECTED_WORKERS = {
    "memory_forager",
    "research_scout",
    "lesson_nurse",
    "trail_mapper",
    "gate_guardian",
    "load_sentinel",
}
EXPECTED_COLONY_WORKERS = EXPECTED_WORKERS | {"history_scribe", "context_weaver", "proposal_builder"}
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
OLD_PROVIDER_PATTERNS = [
    "Ollama",
    "ollama",
    "localhost:11434",
    "11434",
    "OLLAMA",
]
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
        return {"exists": True, "type": "dir", "file_count": len([p for p in path.rglob("*") if p.is_file()])}
    return {"exists": True, "type": "other"}


def snapshot_tree() -> dict[str, dict[str, object]]:
    snapshot: dict[str, dict[str, object]] = {}
    for root in SENSITIVE_ROOTS:
        if not root.exists():
            snapshot[str(root.relative_to(APP_ROOT))] = {"exists": False}
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                snapshot[str(path.relative_to(APP_ROOT))] = file_signature(path)
    return snapshot


def snapshot_forbidden() -> dict[str, dict[str, object]]:
    return {str(path.relative_to(APP_ROOT)): file_signature(path) for path in FORBIDDEN_TARGETS}


def diff_snapshot(
    before: dict[str, dict[str, object]], after: dict[str, dict[str, object]]
) -> dict[str, list[str]]:
    before_keys = set(before)
    after_keys = set(after)
    modified = sorted(key for key in before_keys & after_keys if before[key] != after[key])
    return {
        "new": sorted(after_keys - before_keys),
        "removed": sorted(before_keys - after_keys),
        "modified": modified,
    }


def format_diff(diff: dict[str, list[str]]) -> str:
    parts = []
    for key in ["new", "removed", "modified"]:
        if diff[key]:
            parts.append(key + ": " + ", ".join(diff[key][:15]))
    return "; ".join(parts) or "no changes"


def assert_no_tree_change(before: dict[str, dict[str, object]], after: dict[str, dict[str, object]], label: str) -> None:
    diff = diff_snapshot(before, after)
    unexpected_modified = [path for path in diff["modified"] if path not in NORMAL_CLI_LOG_WRITES]
    if diff["new"] or diff["removed"] or unexpected_modified:
        diff = {**diff, "modified": unexpected_modified}
        raise CheckFailure(label + " changed sensitive tree: " + format_diff(diff))


def assert_only_allowed_new_report(
    before: dict[str, dict[str, object]], after: dict[str, dict[str, object]], allowed_report: Path, label: str
) -> None:
    rel = str(allowed_report.relative_to(APP_ROOT))
    diff = diff_snapshot(before, after)
    allowed_new = [rel]
    unexpected_modified = [path for path in diff["modified"] if path not in NORMAL_CLI_LOG_WRITES]
    if diff["new"] != allowed_new or diff["removed"] or unexpected_modified:
        diff = {**diff, "modified": unexpected_modified}
        raise CheckFailure(label + " changed unexpected sensitive tree entries: " + format_diff(diff))


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


def assert_thought_inbox_unchanged(before_count: int, before_files: dict[str, dict[str, object]], label: str) -> None:
    after_count = thought_inbox_count()
    after_files = {str(path.relative_to(APP_ROOT)): file_signature(path) for path in THOUGHT_INBOX_FILES}
    if before_count != after_count:
        raise CheckFailure(f"{label} changed thought inbox count {before_count} -> {after_count}")
    diff = diff_snapshot(before_files, after_files)
    if diff["new"] or diff["removed"] or diff["modified"]:
        raise CheckFailure(label + " changed thought inbox files: " + format_diff(diff))


def report_files(report_dir: Path, pattern: str) -> set[Path]:
    if not report_dir.exists():
        return set()
    return {path.resolve() for path in report_dir.glob(pattern) if path.is_file()}


def worker_report_files() -> set[Path]:
    return report_files(WORKER_REPORT_DIR, WORKER_REPORT_GLOB)


def colony_report_files() -> set[Path]:
    return report_files(COLONY_REPORT_DIR, COLONY_REPORT_GLOB)


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


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise CheckFailure(f"{label}: missing {needle!r}")


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
            str(APP_ROOT / "tools" / "verify_hive_mind_worker_ants.py"),
        ],
        cwd=str(APP_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if proc.returncode != 0:
        raise CheckFailure("py_compile failed\n" + (proc.stdout or "") + (proc.stderr or ""))


def check_config_schema() -> None:
    if not CONFIG_PATH.exists():
        raise CheckFailure("missing hive config: " + str(CONFIG_PATH))
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    required = {
        "version": "V1",
        "colony_identity": "Engel",
        "research_toggle_default": False,
        "idle_intensity_percent": 10,
        "allow_background_processes": False,
        "shutdown_with_engel": True,
        "trusted_memory_writes": False,
        "source_edits": False,
        "learning_apply": False,
        "queue_mutation": False,
        "digest_history_writes": False,
        "alive_state_writes": False,
        "provider_calls_when_research_off": False,
    }
    for key, expected in required.items():
        if data.get(key) != expected:
            raise CheckFailure(f"config {key} expected {expected!r}, got {data.get(key)!r}")
    if int(data.get("research_on_intensity_percent", 999)) > 60:
        raise CheckFailure("research_on_intensity_percent must remain <= 60")
    workers = data.get("workers")
    if not isinstance(workers, list):
        raise CheckFailure("config workers must be a list")
    missing = sorted(EXPECTED_WORKERS - set(workers))
    if missing:
        raise CheckFailure("config workers missing: " + ", ".join(missing))


def check_colony_config_schema() -> None:
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
        "trusted_memory_writes": False,
        "source_edits": False,
        "learning_apply": False,
        "queue_mutation": False,
        "digest_history_writes": False,
        "alive_state_writes": False,
        "provider_calls_when_research_off": False,
    }
    for key, expected in required.items():
        if data.get(key) != expected:
            raise CheckFailure(f"colony config {key} expected {expected!r}, got {data.get(key)!r}")
    if int(data.get("research_on_intensity_percent", 999)) > 60:
        raise CheckFailure("colony research_on_intensity_percent must remain <= 60")
    nests = data.get("nests")
    queens = data.get("queens")
    workers = data.get("workers")
    if not isinstance(nests, list) or not nests:
        raise CheckFailure("colony config nests must be a non-empty list")
    if not isinstance(queens, list) or not queens:
        raise CheckFailure("colony config queens must be a non-empty list")
    if not isinstance(workers, list) or not workers:
        raise CheckFailure("colony config workers must be a non-empty list")
    nest_ids = {str(nest.get("id", "")) for nest in nests if isinstance(nest, dict)}
    queen_ids = {str(queen.get("id", "")) for queen in queens if isinstance(queen, dict)}
    missing_nests = sorted(EXPECTED_NESTS - nest_ids)
    missing_queens = sorted(EXPECTED_QUEENS - queen_ids)
    missing_workers = sorted(EXPECTED_COLONY_WORKERS - set(workers))
    if missing_nests:
        raise CheckFailure("colony config nests missing: " + ", ".join(missing_nests))
    if missing_queens:
        raise CheckFailure("colony config queens missing: " + ", ".join(missing_queens))
    if missing_workers:
        raise CheckFailure("colony config workers missing: " + ", ".join(missing_workers))
    for queen in queens:
        if not isinstance(queen, dict):
            raise CheckFailure("colony config queen must be an object")
        if queen.get("separate_personality") is not False:
            raise CheckFailure("colony queen separate_personality must be false: " + str(queen.get("id", "")))


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
        if not path.exists():
            continue
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


def check_route_source_guards() -> None:
    research_text = (APP_ROOT / "engel_research_brain_v2.py").read_text(encoding="utf-8", errors="ignore")
    app_text = (APP_ROOT / "engel_app.py").read_text(encoding="utf-8", errors="ignore")
    route_functions = [
        "_hive_mind_config",
        "_hive_config_summary_lines",
        "hive_mind_status",
        "worker_ants_status",
        "research_toggle_status",
        "swarm_trails_status",
        "_worker_ants_architecture_preview",
        "_worker_ants_architecture_report_path",
        "worker_ants_architecture",
        "_colony_config",
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
    app_wrapper_source = source_between(app_text, "def hive_mind_status", "# ----------------------------------------------------------------------\n# Research Thinking")
    route_dispatch_source = source_between(app_text, 'if lower_msg == "hive mind status"', "thought_source_v2mind_a =")
    combined = route_source + "\n" + app_wrapper_source + "\n" + route_dispatch_source

    found_provider = [pattern for pattern in PROVIDER_CALL_PATTERNS if pattern in combined]
    if found_provider:
        raise CheckFailure("provider/live-research pattern found in worker-ant route source: " + ", ".join(found_provider))

    found_background = [pattern for pattern in BACKGROUND_PATTERNS if pattern in combined]
    if found_background:
        raise CheckFailure("background process pattern found in worker-ant route source: " + ", ".join(found_background))

    status_names = [
        "hive_mind_status",
        "worker_ants_status",
        "research_toggle_status",
        "swarm_trails_status",
        "colony_status",
        "colony_nests_status",
        "colony_queens_status",
        "colony_safety_status",
    ]
    for name in status_names:
        source = function_slice(research_text, name)
        for pattern in ["write_text", "open(", "json.dump", ".mkdir(", "subprocess.", "requests.", "urllib."]:
            if pattern in source:
                raise CheckFailure(f"{name} contains forbidden status-route pattern: {pattern}")

    for pattern in FORBIDDEN_DIRECT_WRITE_PATTERNS:
        if re.search(pattern, route_source):
            raise CheckFailure("forbidden direct write pattern found in worker-ant source: " + pattern)

    write_text_occurrences = combined.count("write_text")
    if write_text_occurrences != combined.count("report_path.write_text"):
        raise CheckFailure("unexpected write_text occurrence in worker-ant route source")
    mkdir_occurrences = combined.count(".mkdir(")
    allowed_mkdirs = combined.count("WORKER_ANTS_REPORTS_DIR.mkdir(") + combined.count("COLONY_REPORTS_DIR.mkdir(")
    if mkdir_occurrences != allowed_mkdirs:
        raise CheckFailure("unexpected mkdir occurrence in worker-ant route source")


def assert_route_safety_content(output: str, command: str) -> None:
    assert_contains_ci(output, "READ_ONLY", command)
    assert_any_ci(output, ["DRY_RUN", "dry-run", "REPORT_ONLY", "report-only", "READ_ONLY", "read-only"], command)
    if command != "worker ants status":
        assert_any_ci(output, ["research_toggle", "research toggle"], command)
    assert_any_ci(output, ["idle_intensity_percent", "10% light mode", "10"], command)
    assert_any_ci(output, ["shutdown_with_engel", "while Engel App is running", "survives Engel shutdown"], command)
    assert_any_ci(output, ["no background processes", "allow_background_processes: False", "does not start workers"], command)
    assert_any_ci(output, ["trusted memory writes blocked", "does not write trusted memory", "No trusted memory"], command)
    assert_any_ci(output, ["source edits blocked", "source, queue", "No source", "source file"], command)
    if command != "research toggle status":
        assert_any_ci(output, ["learning apply blocked", "No learning", "does not apply learning"], command)
    assert_any_ci(output, ["queue mutation blocked", "does not write trusted memory, source, queue", "No queue"], command)
    assert_any_ci(output, ["digest/history writes blocked", "digest/history", "digest or history"], command)
    assert_any_ci(output, ["ALIVE_STATE writes blocked", "ALIVE_STATE"], command)
    assert_any_ci(output, ["provider calls blocked", "provider calls disabled", "No provider call"], command)
    if command == "hive mind status":
        assert_contains_ci(output, "Engel remains one companion identity", command)


def assert_colony_route_safety_content(output: str, command: str) -> None:
    assert_contains_ci(output, "READ_ONLY", command)
    assert_contains_ci(output, "DRY_RUN", command)
    assert_contains_ci(output, "Engel", command)
    assert_contains_ci(output, "one companion identity", command)
    assert_any_ci(output, ["idle_intensity_percent", "idle intensity"], command)
    assert_contains_ci(output, "10", command)
    assert_contains_ci(output, "shutdown_with_engel", command)
    assert_contains_ci(output, "no background processes", command)
    assert_contains_ci(output, "provider calls blocked", command)
    assert_contains_ci(output, "trusted memory writes blocked", command)
    assert_contains_ci(output, "source edits blocked", command)
    assert_contains_ci(output, "learning apply blocked", command)
    assert_contains_ci(output, "queue mutation blocked", command)
    assert_contains_ci(output, "digest/history writes blocked", command)
    assert_contains_ci(output, "ALIVE_STATE writes blocked", command)


def run_status_route_no_write(command: str, expected_title: str) -> None:
    before_tree = snapshot_tree()
    before_thought_files = {str(path.relative_to(APP_ROOT)): file_signature(path) for path in THOUGHT_INBOX_FILES}
    before_thought_count = thought_inbox_count()
    output = run_engel(command)
    after_tree = snapshot_tree()
    assert_contains(output, expected_title, command)
    assert_route_safety_content(output, command)
    assert_no_tree_change(before_tree, after_tree, command)
    assert_thought_inbox_unchanged(before_thought_count, before_thought_files, command)


def run_colony_status_route_no_write(command: str, expected_title: str) -> None:
    before_tree = snapshot_tree()
    before_thought_files = {str(path.relative_to(APP_ROOT)): file_signature(path) for path in THOUGHT_INBOX_FILES}
    before_thought_count = thought_inbox_count()
    output = run_engel(command)
    after_tree = snapshot_tree()
    assert_contains(output, expected_title, command)
    assert_colony_route_safety_content(output, command)
    assert_no_tree_change(before_tree, after_tree, command)
    assert_thought_inbox_unchanged(before_thought_count, before_thought_files, command)


def run_unapproved_architecture_no_write() -> None:
    before_tree = snapshot_tree()
    before_thought_files = {str(path.relative_to(APP_ROOT)): file_signature(path) for path in THOUGHT_INBOX_FILES}
    before_thought_count = thought_inbox_count()
    baseline_reports = worker_report_files()
    output = run_engel("worker ants architecture")
    after_tree = snapshot_tree()
    assert_contains(output, "# Worker Ants Architecture Preview", "unapproved_output")
    assert_contains(output, "Status: READ_ONLY / DRY_RUN_ONLY", "unapproved_output")
    assert_contains(output, "No architecture report was written.", "unapproved_output")
    assert_contains_ci(output, "Engel remains one living companion identity", "unapproved_output")
    if worker_report_files() != baseline_reports:
        raise CheckFailure("unapproved_worker_ants_architecture_wrote_report")
    assert_no_tree_change(before_tree, after_tree, "worker ants architecture")
    assert_thought_inbox_unchanged(before_thought_count, before_thought_files, "worker ants architecture")


def run_unapproved_colony_architecture_no_write() -> None:
    before_tree = snapshot_tree()
    before_thought_files = {str(path.relative_to(APP_ROOT)): file_signature(path) for path in THOUGHT_INBOX_FILES}
    before_thought_count = thought_inbox_count()
    baseline_reports = colony_report_files()
    output = run_engel("colony architecture")
    after_tree = snapshot_tree()
    assert_contains(output, "# Colony Architecture Preview", "unapproved_colony_output")
    assert_contains(output, "Status: READ_ONLY / DRY_RUN_ONLY", "unapproved_colony_output")
    assert_contains(output, "No colony report was written.", "unapproved_colony_output")
    assert_colony_route_safety_content(output, "colony architecture")
    if colony_report_files() != baseline_reports:
        raise CheckFailure("unapproved_colony_architecture_wrote_report")
    assert_no_tree_change(before_tree, after_tree, "colony architecture")
    assert_thought_inbox_unchanged(before_thought_count, before_thought_files, "colony architecture")


def run_approved_architecture_report_only() -> Path:
    before_tree = snapshot_tree()
    before_forbidden = snapshot_forbidden()
    before_reports = worker_report_files()
    output = run_engel("worker ants architecture APPROVE_REPORT")
    after_tree = snapshot_tree()
    after_forbidden = snapshot_forbidden()
    after_reports = worker_report_files()
    new_reports = sorted(after_reports - before_reports)

    assert_contains(output, "# Worker Ants Architecture Report Written", "approved_output")
    assert_contains(output, "Status: REPORT_ONLY", "approved_output")
    if len(new_reports) != 1:
        raise CheckFailure(f"approved_worker_ants_architecture_expected_one_report_got_{len(new_reports)}")
    new_report = new_reports[0]
    if WORKER_REPORT_DIR.resolve() not in [new_report.parent, *new_report.parents]:
        raise CheckFailure(f"approved_report_outside_allowed_folder: {new_report}")

    assert_only_allowed_new_report(before_tree, after_tree, new_report, "worker ants architecture APPROVE_REPORT")
    forbidden_diff = diff_snapshot(before_forbidden, after_forbidden)
    if forbidden_diff["new"] or forbidden_diff["removed"] or forbidden_diff["modified"]:
        raise CheckFailure("approved report changed forbidden targets: " + format_diff(forbidden_diff))

    report_text = new_report.read_text(encoding="utf-8", errors="ignore")
    for token in REQUIRED_REPORT_TOKENS:
        assert_contains_ci(report_text, token, "generated_worker_ants_report")
    assert_any_ci(report_text, ["provider calls blocked", "NO_PROVIDER_CALL", "provider calls disabled"], "generated_report")
    assert_any_ci(report_text, ["Engel remains one companion identity", "Engel remains one living companion identity"], "generated_report")
    assert_any_ci(report_text, ["Worker ants are internal helpers", "Worker ants are internal local helpers"], "generated_report")
    return new_report


def run_approved_colony_architecture_report_only() -> Path:
    before_tree = snapshot_tree()
    before_forbidden = snapshot_forbidden()
    before_reports = colony_report_files()
    output = run_engel("colony architecture APPROVE_REPORT")
    after_tree = snapshot_tree()
    after_forbidden = snapshot_forbidden()
    after_reports = colony_report_files()
    new_reports = sorted(after_reports - before_reports)

    assert_contains(output, "# Colony Architecture Report Written", "approved_colony_output")
    assert_contains(output, "Status: REPORT_ONLY", "approved_colony_output")
    if len(new_reports) != 1:
        raise CheckFailure(f"approved_colony_architecture_expected_one_report_got_{len(new_reports)}")
    new_report = new_reports[0]
    if COLONY_REPORT_DIR.resolve() not in [new_report.parent, *new_report.parents]:
        raise CheckFailure(f"approved_colony_report_outside_allowed_folder: {new_report}")

    assert_only_allowed_new_report(before_tree, after_tree, new_report, "colony architecture APPROVE_REPORT")
    forbidden_diff = diff_snapshot(before_forbidden, after_forbidden)
    if forbidden_diff["new"] or forbidden_diff["removed"] or forbidden_diff["modified"]:
        raise CheckFailure("approved colony report changed forbidden targets: " + format_diff(forbidden_diff))

    report_text = new_report.read_text(encoding="utf-8", errors="ignore")
    for token in COLONY_REPORT_TOKENS:
        assert_contains_ci(report_text, token, "generated_colony_report")
    return new_report


def check_learning_apply_blocked_no_write() -> None:
    before_tree = snapshot_tree()
    output = run_engel("learning proposals apply")
    after_tree = snapshot_tree()
    assert_contains(output, "# Learning Proposal Apply Blocked", "apply_output")
    assert_contains(output, "No learning was applied.", "apply_output")
    assert_no_tree_change(before_tree, after_tree, "learning proposals apply")


def main() -> int:
    generated_report = None
    generated_colony_report = None

    def pass_check(label: str) -> None:
        print(f"PASS {label}")

    try:
        check_py_compile()
        pass_check("py_compile_touched_python")

        check_config_schema()
        pass_check("config_schema_content_guard")

        check_colony_config_schema()
        pass_check("colony_config_schema_content_guard")

        check_staged_inactive()
        pass_check("STAGED_DRAFT_ACTIVE_false")

        check_no_staged_activation_literal()
        pass_check("no_STAGED_DRAFT_ACTIVE_true_literal")

        check_no_active_old_provider()
        pass_check("no_active_old_provider_matches")

        check_route_source_guards()
        pass_check("route_source_provider_background_forbidden_write_guards")

        for command, expected in STATUS_ROUTES.items():
            run_status_route_no_write(command, expected)
            pass_check(command.replace(" ", "_") + "_content_and_no_write")

        for command, expected in COLONY_STATUS_ROUTES.items():
            run_colony_status_route_no_write(command, expected)
            pass_check(command.replace(" ", "_") + "_content_and_no_write")

        run_unapproved_architecture_no_write()
        pass_check("unapproved_worker_ants_architecture_no_write")

        run_unapproved_colony_architecture_no_write()
        pass_check("unapproved_colony_architecture_no_write")

        generated_report = run_approved_architecture_report_only()
        pass_check("approved_worker_ants_architecture_one_report_only_with_content")

        generated_colony_report = run_approved_colony_architecture_report_only()
        pass_check("approved_colony_architecture_one_report_only_with_content")

        check_learning_apply_blocked_no_write()
        pass_check("learning_apply_remains_blocked_no_write")

        print("")
        print("HIVE_MIND_WORKER_ANTS_VERIFICATION_PASS")
        print("generated_report=" + str(generated_report))
        print("generated_colony_report=" + str(generated_colony_report))
        print("sensitive_roots_checked=" + ",".join(str(path.relative_to(APP_ROOT)) for path in SENSITIVE_ROOTS))
        print("forbidden_targets_checked=" + str(len(FORBIDDEN_TARGETS)))
        return 0
    except CheckFailure as exc:
        print("")
        print("HIVE_MIND_WORKER_ANTS_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
