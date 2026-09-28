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
PROPOSAL_CONFIG_PATH = APP_ROOT / "memory" / "COLONY_PROPOSAL_AUTONOMY_V1.json"
ROUTE_VERIFICATION_MANIFEST_PATH = APP_ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
PROPOSAL_REPORT_DIR = APP_ROOT / "reports" / "proposal_autonomy"
PROPOSAL_REPORT_GLOB = "colony_proposal_preview_*.md"

STANDARD_VERIFIERS = [
    "tools\\verify_hive_mind_worker_ants.py",
    "tools\\verify_colony_routes.py",
    "tools\\verify_swarm_trails_preview.py",
    "tools\\verify_colony_autonomy_ladder.py",
    "tools\\verify_colony_proposal_autonomy.py",
]
PROPOSAL_MATRIX_ENTRIES = {
    "colony proposal status": "READ_ONLY_STATUS_ONLY_CONTRACT_ONLY",
    "colony proposal contract": "READ_ONLY_STATUS_ONLY_CONTRACT_ONLY",
    "colony proposal preview": "READ_ONLY_DRY_RUN_LOCAL_ONLY_NO_WRITE",
    "colony proposal preview APPROVE_REPORT": "APPROVE_REPORT_REPORT_ONLY_LOCAL_ONLY",
}
ROUTES = {
    "colony proposal status": "# Colony Proposal Status",
    "colony proposal contract": "# Colony Proposal Autonomy Contract",
}

ACTIVE_OLD_PROVIDER_FILES = [
    APP_ROOT / "engel_app.py",
    APP_ROOT / "engel_companion.py",
    APP_ROOT / "engel_research_brain_v2.py",
    APP_ROOT / "memory" / "ENGEL_COMMANDS.md",
    APP_ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json",
    APP_ROOT / "memory" / "COLONY_PROPOSAL_AUTONOMY_V1.json",
    APP_ROOT / "memory" / "COLONY_AUTONOMY_LADDER_V1.json",
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
    APP_ROOT / "prompts" / "ENGEL_SYSTEM.md",
    APP_ROOT / "engel_app.py",
    APP_ROOT / "engel_research_brain_v2.py",
    APP_ROOT / "reports" / "overnight" / "OVERNIGHT_QUEUE.md",
    APP_ROOT / "reports" / "research" / "LEARNING_PROPOSALS.md",
    APP_ROOT / "reports" / "research" / "RESEARCH_QUEUE_CLEANUP_LATEST.md",
    APP_ROOT / "reports" / "research" / "NEXT_BEST_TOPIC.md",
    APP_ROOT / "reports" / "research" / "RESEARCH_DIGEST_LATEST.md",
    APP_ROOT / "reports" / "research" / "RESEARCH_TOPIC_HISTORY.md",
    APP_ROOT / "reports" / "research" / "learning_proposals_archive",
    APP_ROOT / "reports" / "OVERNIGHT_RESEARCH_LOOP_HISTORY.jsonl",
    APP_ROOT / "reports" / "overnight" / "proposal_harvest",
]
WATCHED_REPORT_DIRS = [
    APP_ROOT / "reports" / "proposal_autonomy",
    APP_ROOT / "reports" / "learning_proposals",
    APP_ROOT / "reports" / "colony_autonomy",
    APP_ROOT / "reports" / "swarm_trails",
    APP_ROOT / "reports" / "colony",
    APP_ROOT / "reports" / "worker_ants",
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
    "completion_digest(",
    "live_completion",
    "digest_latest(",
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
REQUIRED_CANDIDATE_PHRASES = [
    "learning proposal candidate",
    "research topic candidate",
    "memory link candidate",
    "swarm trail candidate",
    "project history candidate",
    "safety check candidate",
    "codex prompt candidate",
]
REQUIRED_CANDIDATE_TYPES = {
    "learning_proposal_candidate",
    "research_topic_candidate",
    "memory_link_candidate",
    "swarm_trail_candidate",
    "project_history_candidate",
    "safety_check_candidate",
    "codex_prompt_candidate",
}
EXPECTED_ALLOWED_PREVIEW_INPUTS = {
    "local_report_filenames",
    "local_checkpoint_filenames",
    "safe_file_headers",
    "existing_swarm_trail_preview",
    "existing_colony_sensing_preview",
    "approved_report_only_outputs",
}
REQUIRED_BLOCKED_INPUTS = {
    "live_web_research",
    "provider_calls",
    "background_scanning",
    "queue_mutation",
    "learning_apply",
    "source_editing",
}
EXPECTED_ALLOWED_OUTPUTS_NOW = {
    "dry_run_preview_text",
    "APPROVE_REPORT_report_only_markdown",
}
REQUIRED_BLOCKED_OUTPUTS = {
    "trusted_memory_writes",
    "learning_apply",
    "proposal_archive_or_reject_mutation",
    "research_queue_mutation",
    "source_edits",
    "digest_history_writes",
    "alive_state_writes",
    "identity_rule_changes",
}
REQUIRED_APPROVAL_CONTRACT_KEYS = {
    "trusted_memory_requires_APPROVE",
    "learning_apply_requires_APPROVE",
    "queue_mutation_requires_future_explicit_gate",
    "source_edits_require_codex_or_user_approval",
}

COMMON_TOKENS = [
    "READ_ONLY",
    "CONTRACT_ONLY",
    "Level 2 proposal-building",
    "runtime_level_2_enabled false",
    "runtime_autonomy_enabled false",
    "proposal candidates",
    "Engel remains one companion identity",
    "no background processes",
    "no provider calls while research OFF",
    "trusted memory writes blocked",
    "source edits blocked",
    "learning apply blocked",
    "queue mutation blocked",
    "digest/history writes blocked",
    "ALIVE_STATE writes blocked",
    "proposal candidates are not trusted memory",
    "proposal candidates are not applied lessons",
    "proposal candidates are not queue mutations",
    "proposal candidates are not source edits",
]
ROUTE_TOKENS = {
    "colony proposal status": COMMON_TOKENS + ["STATUS_ONLY", "proposal candidates only"],
    "colony proposal contract": COMMON_TOKENS + ["approval contract", "allowed outputs now", "blocked outputs"],
    "colony proposal preview": [
        "READ_ONLY",
        "CONTRACT_ONLY",
        "PREVIEW_ONLY",
        "DRY_RUN",
        "NO_WRITE",
        "Level 2 is not enabled",
        "runtime_level_2_enabled false",
        "runtime_autonomy_enabled false",
        "no autonomous loop",
        "no background workers",
        "no provider calls",
        "no live research",
        "no trust-changing actions occur",
        "candidate categories",
        "local-only",
        "capped preview",
        "proposal candidates are not trusted memory",
        "proposal candidates are not applied lessons",
        "proposal candidates are not queue mutations",
        "proposal candidates are not source edits",
        "trusted memory writes blocked",
        "source edits blocked",
        "learning apply blocked",
        "queue mutation blocked",
        "digest/history writes blocked",
        "ALIVE_STATE writes blocked",
    ],
}
REPORT_TOKENS = [
    "READ_ONLY",
    "REPORT_ONLY",
    "APPROVE_REPORT",
    "CONTRACT_ONLY",
    "Level 2 proposal-building preview",
    "runtime_level_2_enabled false",
    "runtime_autonomy_enabled false",
    "candidate categories",
    "Allowed preview inputs",
    "Blocked inputs",
    "Allowed outputs now",
    "Blocked outputs without explicit approval",
    "Approval contract",
    "proposal candidates are not trusted memory",
    "proposal candidates are not applied lessons",
    "proposal candidates are not queue mutations",
    "proposal candidates are not source edits",
    "no autonomous loop enabled",
    "no background processes",
    "no provider calls while research OFF",
    "trusted memory writes blocked",
    "source edits blocked",
    "learning apply blocked",
    "queue mutation blocked",
    "digest/history writes blocked",
    "ALIVE_STATE writes blocked",
    "one Engel companion identity",
    "shutdown_with_engel",
    "Ollama removal preserved",
    "ChatGPT/Gemini provider gates unchanged",
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


def assert_only_allowed_proposal_report(
    before: dict[str, dict[str, object]], after: dict[str, dict[str, object]], report: Path
) -> None:
    rel = str(report.relative_to(APP_ROOT))
    report_dir_rel = str(PROPOSAL_REPORT_DIR.relative_to(APP_ROOT))
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
        raise CheckFailure("approved proposal report changed unexpected entries: " + format_diff(scoped))


def thought_inbox_count() -> int:
    path = APP_ROOT / "memory" / "COMPANION_THOUGHT_INBOX_V2MIND_A.json"
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
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


def proposal_report_files() -> set[Path]:
    if not PROPOSAL_REPORT_DIR.exists():
        return set()
    return {path.resolve() for path in PROPOSAL_REPORT_DIR.glob(PROPOSAL_REPORT_GLOB) if path.is_file()}


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


def normalize_content(text: str) -> str:
    text = text.lower().replace("_", " ").replace("-", " ")
    return re.sub(r"[^a-z0-9]+", " ", text)


def assert_contains_loose(text: str, phrase: str, label: str) -> None:
    if normalize_content(phrase) not in normalize_content(text):
        raise CheckFailure(f"{label}: missing loose phrase {phrase!r}")


def snapshot_watched_reports() -> dict[str, dict[str, object]]:
    snapshot: dict[str, dict[str, object]] = {}
    for root in WATCHED_REPORT_DIRS:
        if not root.exists():
            snapshot[str(root.relative_to(APP_ROOT))] = {"exists": False}
            continue
        snapshot[str(root.relative_to(APP_ROOT))] = file_signature(root)
        for path in sorted(root.rglob("*")):
            if path.is_file() or path.is_dir():
                snapshot[str(path.relative_to(APP_ROOT))] = file_signature(path)
    return snapshot


def check_py_compile() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "py_compile",
            str(APP_ROOT / "engel_app.py"),
            str(APP_ROOT / "engel_companion.py"),
            str(APP_ROOT / "engel_research_brain_v2.py"),
            str(APP_ROOT / "tools" / "verify_colony_proposal_autonomy.py"),
        ],
        cwd=str(APP_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if proc.returncode != 0:
        raise CheckFailure("py_compile failed\n" + (proc.stdout or "") + (proc.stderr or ""))


def check_config_schema() -> None:
    if not PROPOSAL_CONFIG_PATH.exists():
        raise CheckFailure("missing proposal autonomy config: " + str(PROPOSAL_CONFIG_PATH))
    data = json.loads(PROPOSAL_CONFIG_PATH.read_text(encoding="utf-8"))
    required = {
        "version": "V1",
        "colony_identity": "Engel",
        "one_companion_identity": True,
        "mode": "CONTRACT_ONLY",
        "level": 2,
        "level_name": "proposal_building",
        "runtime_level_2_enabled": False,
        "runtime_autonomy_enabled": False,
        "research_toggle_default": False,
        "idle_intensity_percent": 10,
        "shutdown_with_engel": True,
        "background_processes": False,
        "provider_calls_when_research_off": False,
    }
    for key, expected in required.items():
        if data.get(key) != expected:
            raise CheckFailure(f"proposal config {key} expected {expected!r}, got {data.get(key)!r}")
    if int(data.get("research_on_intensity_percent_cap", 999)) > 60:
        raise CheckFailure("research_on_intensity_percent_cap must remain <= 60")
    if int(data.get("max_preview_files", 999)) > 40:
        raise CheckFailure("max_preview_files must remain <= 40")
    if int(data.get("max_lines_per_file", 999)) > 8:
        raise CheckFailure("max_lines_per_file must remain <= 8")

    candidates = set(data.get("proposal_candidate_types", []))
    missing = sorted(REQUIRED_CANDIDATE_TYPES - candidates)
    if missing:
        raise CheckFailure("missing proposal_candidate_types: " + ", ".join(missing))

    allowed_inputs = set(data.get("allowed_preview_inputs", []))
    if allowed_inputs != EXPECTED_ALLOWED_PREVIEW_INPUTS:
        raise CheckFailure("allowed_preview_inputs must remain local/safe preview inputs only")

    blocked_inputs = set(data.get("blocked_inputs_without_approval", []))
    missing_blocked_inputs = sorted(REQUIRED_BLOCKED_INPUTS - blocked_inputs)
    if missing_blocked_inputs:
        raise CheckFailure("missing blocked_inputs_without_approval entries: " + ", ".join(missing_blocked_inputs))

    allowed = set(data.get("allowed_outputs_now", []))
    if allowed != EXPECTED_ALLOWED_OUTPUTS_NOW:
        raise CheckFailure("allowed_outputs_now must remain dry-run/report-only only")

    blocked = set(data.get("blocked_outputs_without_explicit_approval", []))
    missing_blocked = sorted(REQUIRED_BLOCKED_OUTPUTS - blocked)
    if missing_blocked:
        raise CheckFailure("missing blocked outputs: " + ", ".join(missing_blocked))

    approval = data.get("approval_contract")
    if not isinstance(approval, dict):
        raise CheckFailure("approval_contract must be an object")
    if approval.get("preview_without_approval") is not True:
        raise CheckFailure("preview_without_approval must remain true")
    if approval.get("report_with_APPROVE_REPORT") is not True:
        raise CheckFailure("report_with_APPROVE_REPORT must remain true")
    for key in REQUIRED_APPROVAL_CONTRACT_KEYS:
        if approval.get(key) is not True:
            raise CheckFailure("approval_contract must keep explicit gate true: " + key)


def check_staged_inactive() -> None:
    sys.path.insert(0, str(APP_ROOT))
    module = importlib.import_module("engel_research_brain_v2")
    active = getattr(module, "STAGED_DRAFT_ACTIVE", None)
    if active is not False:
        raise CheckFailure(f"STAGED_DRAFT_ACTIVE expected False, got {active!r}")


def check_no_activation_literals() -> None:
    staged_regex = re.compile(r"STAGED_DRAFT_ACTIVE\s*=\s*True")
    runtime_regex = re.compile(r"runtime_level_2_enabled\s+true", re.IGNORECASE)
    matches = []
    for path in STAGED_ACTIVATION_FILES + [PROPOSAL_CONFIG_PATH, ROUTE_VERIFICATION_MANIFEST_PATH]:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if staged_regex.search(line) or runtime_regex.search(line):
                matches.append(f"{path.relative_to(APP_ROOT)}:{lineno}:{line.strip()}")
    if matches:
        raise CheckFailure("unsafe activation literal found:\n" + "\n".join(matches))


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


def check_verification_manifest_and_status_routes() -> None:
    if not ROUTE_VERIFICATION_MANIFEST_PATH.exists():
        raise CheckFailure("missing route verification manifest")
    manifest = json.loads(ROUTE_VERIFICATION_MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("mode") != "DOCUMENTATION_ONLY":
        raise CheckFailure("route verification manifest mode must remain DOCUMENTATION_ONLY")
    if manifest.get("runtime_feature_enabled") is not False:
        raise CheckFailure("route verification manifest runtime_feature_enabled must remain false")
    if manifest.get("runs_automatically") is not False:
        raise CheckFailure("route verification manifest runs_automatically must remain false")
    safety = manifest.get("safety_contract")
    if not isinstance(safety, dict):
        raise CheckFailure("route verification manifest safety_contract must be an object")
    for key in [
        "runtime_level_2_enabled",
        "runtime_autonomy_enabled",
        "loops_enabled",
        "background_workers",
        "live_research",
        "provider_calls",
        "trusted_memory_writes",
        "source_edits",
        "learning_apply",
        "queue_mutation",
        "digest_history_writes",
        "alive_state_writes",
    ]:
        if safety.get(key) is not False:
            raise CheckFailure("route verification safety_contract " + key + " must remain false")
    verifiers = manifest.get("standard_verifiers")
    if not isinstance(verifiers, list):
        raise CheckFailure("standard_verifiers must be a list")
    for verifier in STANDARD_VERIFIERS:
        if verifier not in verifiers:
            raise CheckFailure("standard verifier missing from manifest: " + verifier)

    entries = manifest.get("route_regression_matrix_entries")
    if not isinstance(entries, list):
        raise CheckFailure("route_regression_matrix_entries must be a list")
    by_command = {str(entry.get("command", "")): entry for entry in entries if isinstance(entry, dict)}
    for command, expected_behavior in PROPOSAL_MATRIX_ENTRIES.items():
        entry = by_command.get(command)
        if not entry:
            raise CheckFailure("manifest missing proposal matrix entry: " + command)
        if entry.get("expected_behavior") != expected_behavior:
            raise CheckFailure(command + " expected_behavior mismatch")
        if entry.get("should_execute_in_test") is not False:
            raise CheckFailure(command + " should_execute_in_test must remain false")

    for route_command in ["verification set status", "route regression status"]:
        before_tree = snapshot_sensitive_tree()
        before_watched_reports = snapshot_watched_reports()
        before_reports = proposal_report_files()
        before_thought_files = snapshot_thought_inbox()
        before_thought_count = thought_inbox_count()
        output = run_engel(route_command)
        after_tree = snapshot_sensitive_tree()
        after_watched_reports = snapshot_watched_reports()
        assert_no_tree_change(before_tree, after_tree, route_command)
        assert_no_tree_change(before_watched_reports, after_watched_reports, route_command + " watched report dirs")
        assert_thought_inbox_unchanged(before_thought_count, before_thought_files, route_command)
        if proposal_report_files() != before_reports:
            raise CheckFailure(route_command + " generated a proposal autonomy report")
        for verifier in STANDARD_VERIFIERS:
            assert_contains_ci(output, verifier, route_command)
        for command in PROPOSAL_MATRIX_ENTRIES:
            assert_contains_ci(output, command, route_command)
        assert_contains_ci(output, "should_execute_in_test: false", route_command)
        assert_contains_ci(output, "does not generate reports", route_command)
        if "# Colony Proposal Preview" in output:
            raise CheckFailure(route_command + " appears to have executed colony proposal preview")
        if "# Colony Proposal Preview Report Written" in output:
            raise CheckFailure(route_command + " appears to have executed approved proposal report route")
        if route_command == "route regression status":
            assert_contains_ci(output, "does not execute matrix commands", route_command)
            assert_contains_ci(output, "does not execute verifier scripts", route_command)
        if route_command == "verification set status":
            assert_contains_ci(output, "does not run verifiers", route_command)
            assert_contains_ci(output, "does not execute route-regression matrix entries", route_command)


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
        "_proposal_autonomy_config",
        "_proposal_autonomy_bool",
        "_proposal_autonomy_int",
        "_proposal_autonomy_list",
        "_proposal_autonomy_config_lines",
        "_proposal_autonomy_blocked_lines",
        "_proposal_autonomy_scan_dirs",
        "_proposal_autonomy_allowed_file",
        "_proposal_autonomy_header",
        "_proposal_autonomy_scan",
        "_proposal_candidate_lines",
        "colony_proposal_status",
        "colony_proposal_contract",
        "_colony_proposal_preview_text",
        "_colony_proposal_report_path",
        "colony_proposal_preview",
    ]
    route_source = "\n".join(function_slice(research_text, name) for name in route_functions)
    app_wrapper_source = source_between(app_text, "def colony_proposal_status", "# ----------------------------------------------------------------------\n# Research Thinking")
    route_dispatch_source = source_between(app_text, 'if lower_msg == "colony proposal status"', "thought_source_v2mind_a =")
    combined = route_source + "\n" + app_wrapper_source + "\n" + route_dispatch_source

    provider_hits = [pattern for pattern in PROVIDER_CALL_PATTERNS if pattern in combined]
    if provider_hits:
        raise CheckFailure("provider/live-research pattern found in proposal autonomy source slice: " + ", ".join(provider_hits))

    background_hits = [pattern for pattern in BACKGROUND_PATTERNS if pattern in combined]
    if background_hits:
        raise CheckFailure("background pattern found in proposal autonomy source slice: " + ", ".join(background_hits))

    for pattern in FORBIDDEN_DIRECT_WRITE_PATTERNS:
        if re.search(pattern, route_source):
            raise CheckFailure("forbidden direct write pattern found in proposal autonomy source slice: " + pattern)

    write_text_occurrences = combined.count("write_text")
    if write_text_occurrences != combined.count("report_path.write_text"):
        raise CheckFailure("unexpected write_text occurrence in proposal autonomy source slice")
    mkdir_occurrences = combined.count(".mkdir(")
    if mkdir_occurrences != combined.count("PROPOSAL_AUTONOMY_REPORTS_DIR.mkdir("):
        raise CheckFailure("unexpected mkdir occurrence in proposal autonomy source slice")
    for status_name in ["colony_proposal_status", "colony_proposal_contract"]:
        source = function_slice(research_text, status_name)
        for pattern in ["write_text", "open(", "json.dump", ".mkdir(", "subprocess.", "requests.", "urllib."]:
            if pattern in source:
                raise CheckFailure(f"{status_name} contains forbidden status-route pattern: {pattern}")


def assert_tokens(output: str, command: str) -> None:
    for token in ROUTE_TOKENS[command]:
        assert_contains_ci(output, token, command)


def run_route_no_write(command: str, expected_title: str) -> None:
    before_tree = snapshot_sensitive_tree()
    before_thought_files = snapshot_thought_inbox()
    before_thought_count = thought_inbox_count()
    output = run_engel(command)
    after_tree = snapshot_sensitive_tree()
    assert_contains_ci(output, expected_title, command)
    assert_tokens(output, command)
    assert_no_tree_change(before_tree, after_tree, command)
    assert_thought_inbox_unchanged(before_thought_count, before_thought_files, command)


def run_proposal_preview_no_write() -> None:
    before_tree = snapshot_sensitive_tree()
    before_thought_files = snapshot_thought_inbox()
    before_thought_count = thought_inbox_count()
    before_reports = proposal_report_files()
    output = run_engel("colony proposal preview")
    after_tree = snapshot_sensitive_tree()
    assert_contains_ci(output, "# Colony Proposal Preview", "colony proposal preview")
    assert_tokens(output, "colony proposal preview")
    for phrase in REQUIRED_CANDIDATE_PHRASES:
        assert_contains_loose(output, phrase, "colony proposal preview")
    if proposal_report_files() != before_reports:
        raise CheckFailure("colony proposal preview wrote a report without APPROVE_REPORT")
    assert_no_tree_change(before_tree, after_tree, "colony proposal preview")
    assert_thought_inbox_unchanged(before_thought_count, before_thought_files, "colony proposal preview")


def run_proposal_approved_report_only() -> Path:
    before_tree = snapshot_sensitive_tree()
    before_forbidden = snapshot_forbidden()
    before_thought_files = snapshot_thought_inbox()
    before_thought_count = thought_inbox_count()
    before_reports = proposal_report_files()
    output = run_engel("colony proposal preview APPROVE_REPORT")
    after_tree = snapshot_sensitive_tree()
    after_forbidden = snapshot_forbidden()
    after_reports = proposal_report_files()
    new_reports = sorted(after_reports - before_reports)
    if len(new_reports) != 1:
        raise CheckFailure(f"expected exactly one new proposal autonomy report, got {len(new_reports)}")
    report = new_reports[0]
    if report.parent.resolve() != PROPOSAL_REPORT_DIR.resolve():
        raise CheckFailure("proposal autonomy report was written outside reports\\proposal_autonomy: " + str(report))
    assert_contains_ci(output, "# Colony Proposal Preview Report Written", "colony proposal preview APPROVE_REPORT")
    assert_contains_ci(output, "Status: REPORT_ONLY", "colony proposal preview APPROVE_REPORT")
    assert_only_allowed_proposal_report(before_tree, after_tree, report)
    forbidden_diff = diff_snapshot(before_forbidden, after_forbidden)
    if forbidden_diff["new"] or forbidden_diff["removed"] or forbidden_diff["modified"]:
        raise CheckFailure("approved proposal report changed forbidden targets: " + format_diff(forbidden_diff))
    assert_thought_inbox_unchanged(before_thought_count, before_thought_files, "colony proposal preview APPROVE_REPORT")

    report_text = report.read_text(encoding="utf-8", errors="ignore")
    for token in REPORT_TOKENS:
        assert_contains_ci(report_text, token, "generated proposal autonomy report")
    for phrase in REQUIRED_CANDIDATE_PHRASES:
        assert_contains_loose(report_text, phrase, "generated proposal autonomy report")
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
        pass_check("py_compile_colony_proposal_autonomy_targets")

        check_config_schema()
        pass_check("colony_proposal_autonomy_config_schema_content_guard")

        check_staged_inactive()
        pass_check("STAGED_DRAFT_ACTIVE_false")

        check_no_activation_literals()
        pass_check("no_runtime_level_2_or_staged_activation_literal")

        check_no_active_old_provider()
        pass_check("no_active_old_provider_matches")

        check_source_slice_guards()
        pass_check("colony_proposal_autonomy_source_slice_provider_background_forbidden_write_guards")

        check_verification_manifest_and_status_routes()
        pass_check("verification_manifest_and_status_routes_include_proposal_nonexecuting_entries")

        for command, title in ROUTES.items():
            run_route_no_write(command, title)
            pass_check(command.replace(" ", "_") + "_content_thought_guard_no_write")

        run_proposal_preview_no_write()
        pass_check("colony_proposal_preview_dry_run_no_write")

        generated_report = run_proposal_approved_report_only()
        pass_check("colony_proposal_preview_approved_one_report_only_with_tokens")

        check_learning_apply_blocked_no_write()
        pass_check("learning_apply_remains_blocked_no_write")

        print("")
        print("COLONY_PROPOSAL_AUTONOMY_VERIFICATION_PASS")
        print("generated_proposal_autonomy_report=" + str(generated_report))
        print("sensitive_roots_checked=" + ",".join(str(path.relative_to(APP_ROOT)) for path in SENSITIVE_ROOTS))
        print("forbidden_targets_checked=" + str(len(FORBIDDEN_TARGETS)))
        return 0
    except CheckFailure as exc:
        print("")
        print("COLONY_PROPOSAL_AUTONOMY_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
