from __future__ import annotations

import hashlib
import importlib
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
REPORT_DIR = APP_ROOT / "reports" / "learning_proposals"
REPORT_GLOB = "learning_proposals_build_*.md"
REQUIRED_TOKENS = [
    "REPORT_ONLY",
    "NOT_APPLIED",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_EDIT",
    "NO_QUEUE_WRITE",
    "NO_DIGEST_HISTORY_WRITE",
    "NO_ALIVE_STATE_WRITE",
]
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
FORBIDDEN_TARGETS = [
    APP_ROOT / "memory" / "ALIVE_STATE.json",
    APP_ROOT / "memory" / "LEARNING_LOG.md",
    APP_ROOT / "memory" / "RESEARCH_NOTES.md",
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
        children = []
        for child in sorted(path.rglob("*")):
            if child.is_file():
                rel = str(child.relative_to(path)).replace("\\", "/")
                stat = child.stat()
                children.append((rel, stat.st_size, stat.st_mtime_ns, sha256(child)))
        return {"exists": True, "type": "dir", "children": children}
    return {"exists": True, "type": "other"}


def snapshot_forbidden() -> dict[str, dict[str, object]]:
    return {str(path.relative_to(APP_ROOT)): file_signature(path) for path in FORBIDDEN_TARGETS}


def changed_forbidden(before: dict[str, dict[str, object]], after: dict[str, dict[str, object]]) -> list[str]:
    changed = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            changed.append(key)
    return changed


def report_files() -> set[Path]:
    if not REPORT_DIR.exists():
        return set()
    return {path.resolve() for path in REPORT_DIR.glob(REPORT_GLOB) if path.is_file()}


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


def assert_not_contains(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise CheckFailure(f"{label}: unexpected {needle!r}")


def check_staged_inactive() -> None:
    sys.path.insert(0, str(APP_ROOT))
    module = importlib.import_module("engel_research_brain_v2")
    active = getattr(module, "STAGED_DRAFT_ACTIVE", None)
    if active is not False:
        raise CheckFailure(f"STAGED_DRAFT_ACTIVE expected False, got {active!r}")


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


def main() -> int:
    results = []

    def pass_check(label: str) -> None:
        results.append(("PASS", label))
        print(f"PASS {label}")

    try:
        check_staged_inactive()
        pass_check("STAGED_DRAFT_ACTIVE_false")

        check_no_staged_activation_literal()
        pass_check("no_STAGED_DRAFT_ACTIVE_true_literal")

        check_no_active_old_provider()
        pass_check("no_active_old_provider_matches")

        baseline_reports = report_files()
        forbidden_before_unapproved = snapshot_forbidden()
        output = run_engel("learning proposals build")
        forbidden_after_unapproved = snapshot_forbidden()

        assert_contains(output, "# Learning Proposals Build Preview", "unapproved_output")
        assert_contains(output, "Status: DRY_RUN_ONLY", "unapproved_output")
        assert_contains(output, "No proposal file was written.", "unapproved_output")
        if report_files() != baseline_reports:
            raise CheckFailure("unapproved_command_wrote_report_file")
        changed = changed_forbidden(forbidden_before_unapproved, forbidden_after_unapproved)
        if changed:
            raise CheckFailure("unapproved_command_changed_forbidden_targets: " + ", ".join(changed))
        pass_check("unapproved_build_dry_run_no_write")

        before_approved_reports = report_files()
        forbidden_before_approved = snapshot_forbidden()
        output = run_engel("learning proposals build APPROVE_REPORT")
        forbidden_after_approved = snapshot_forbidden()
        after_approved_reports = report_files()
        new_reports = sorted(after_approved_reports - before_approved_reports)

        assert_contains(output, "# Learning Proposals Build Report Written", "approved_output")
        assert_contains(output, "Status: REPORT_ONLY", "approved_output")
        assert_contains(output, "NO_TRUSTED_MEMORY_WRITE", "approved_output")
        if len(new_reports) != 1:
            raise CheckFailure(f"approved_command_expected_one_report_got_{len(new_reports)}")
        new_report = new_reports[0]
        allowed_root = REPORT_DIR.resolve()
        if allowed_root not in [new_report.parent, *new_report.parents]:
            raise CheckFailure(f"approved_report_outside_allowed_folder: {new_report}")
        changed = changed_forbidden(forbidden_before_approved, forbidden_after_approved)
        if changed:
            raise CheckFailure("approved_command_changed_forbidden_targets: " + ", ".join(changed))

        report_text = new_report.read_text(encoding="utf-8", errors="ignore")
        for token in REQUIRED_TOKENS:
            assert_contains(report_text, token, "generated_report")
        assert_contains(report_text, "No learning was applied.", "generated_report")
        assert_contains(report_text, "No provider call was made.", "generated_report")
        pass_check("approved_build_created_exactly_one_report_with_required_tokens")

        before_apply_reports = report_files()
        forbidden_before_apply = snapshot_forbidden()
        apply_output = run_engel("learning proposals apply")
        forbidden_after_apply = snapshot_forbidden()
        assert_contains(apply_output, "# Learning Proposal Apply Blocked", "apply_output")
        assert_contains(apply_output, "No learning was applied.", "apply_output")
        assert_contains(apply_output, "No memory was changed.", "apply_output")
        assert_not_contains(apply_output, "# Learning Proposals Applied", "apply_output")
        if report_files() != before_apply_reports:
            raise CheckFailure("blocked_apply_created_report_file")
        changed = changed_forbidden(forbidden_before_apply, forbidden_after_apply)
        if changed:
            raise CheckFailure("blocked_apply_changed_forbidden_targets: " + ", ".join(changed))
        pass_check("learning_apply_remains_blocked_no_forbidden_write")

        print("")
        print("AX_ROUTE_SAFETY_TESTS_PASS")
        print("generated_report=" + str(new_report))
        print("forbidden_targets_checked=" + str(len(FORBIDDEN_TARGETS)))
        return 0
    except CheckFailure as exc:
        print("")
        print("AX_ROUTE_SAFETY_TESTS_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
