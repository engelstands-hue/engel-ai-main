from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import textwrap

import engel_global_password_gate as global_password_gate


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
PATCH_CANDIDATE_DIR = PROJECT_ROOT / "reports" / "patch_candidates"
RECEIPT_DIR = PROJECT_ROOT / "reports" / "code_companion_patch_receipts"
RUNNER_VERSION = "ENGEL_CODE_COMPANION_LOW_RISK_PATCH_RUNNER_V1"
MAX_PATCH_TEXT_CHARS = 4000

RUNNER_STATUS = [
    "CODE_COMPANION_LOW_RISK_PATCH_RUNNER",
    "PREAPPROVED_LOW_RISK_PATCHES_ONLY",
    "EXPLICIT_PATCH_CANDIDATE_REQUIRED",
    "VERIFY_BEFORE_COMMIT",
    "RECEIPT_REQUIRED",
    "STOP_ON_HIGH_RISK",
    "STOP_ON_UNCLEAR_RISK",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PACKAGE_REFRESH",
    "NO_ROUTE_STARTUP_MUTATION",
    "NO_BACKGROUND_WORKER",
    "NO_COMMIT_AUTOMATION",
]

IMPLEMENTED_V1_PATCH_CLASSES = [
    "documentation_typo_or_label_fix",
    "generated_report_metadata_update",
    "codex_bridge_report_reference_update",
    "read_only_status_surface_label_fix",
]

DRY_RUN_ONLY_PATCH_CLASSES = [
    "report_hash_refresh",
    "verifier_expectation_update_for_existing_committed_contract",
    "core_continuity_report_only_index_update",
]

HIGH_RISK_STOP_CLASSES = [
    "runtime behavior change",
    "provider/network/browser activation",
    "model loading/inference",
    "trusted memory write",
    "route/startup mutation",
    "package refresh/live promotion",
    "GUI action button addition",
    "security/authority hierarchy change",
    "queue/runtime activation",
    "background worker/autonomous loop",
    "arbitrary refactor",
    "external drive access",
    "package manager change",
    "live/staging artifact mutation",
    "binary file mutation",
    "unknown source file mutation",
]

RECEIPT_FIELDS = [
    "patch_run_id",
    "source_patch_candidate_id",
    "source_patch_candidate_path",
    "patch_class",
    "mode",
    "files_changed",
    "patch_summary",
    "verification_commands",
    "verification_result",
    "safety_scan_result",
    "commit_hash",
    "stopped",
    "stop_reason",
    "human_intervention_required",
    "rollback_notes",
    "no_trusted_memory_write",
    "no_provider_network_browser",
    "no_background_worker",
    "no_package_refresh",
    "no_route_startup_mutation",
]

POST_APPLY_VERIFICATION_COMMANDS = [
    "python tools\\verify_engel_code_companion_low_risk_patch_runner.py",
    "python tools\\verify_engel_code_companion_patch_receipt_viewer.py",
    "python tools\\verify_engel_code_companion_patch_status_surface.py",
    "python tools\\verify_engel_code_companion_patch_candidate.py",
    "python tools\\verify_engel_code_companion_verifier_plan.py",
    "python tools\\verify_untrusted_content_guard.py",
    "python tools\\verify_prompt_injection_guard.py",
    "python tools\\verify_authority_hierarchy.py",
    "python tools\\verify_living_systems_documentation_drift.py",
]

READ_ONLY_STATUS_SURFACE_FILES = [
    "engel_code_companion_candidate_review_status.py",
    "engel_code_companion_patch_status_surface.py",
    "engel_ai_growth_dashboard.py",
    "engel_candidate_review_dashboard.py",
    "engel_low_risk_self_fix_status_surface.py",
    "engel_self_fix_receipt_viewer.py",
]

POSITIVE_HIGH_RISK_PATTERNS = [
    r"\bruntime behavior change\b",
    r"\bprovider/network/browser activation\b",
    r"\bactivate provider\b",
    r"\bcall provider\b",
    r"\bnetwork call\b",
    r"\bopen browser\b",
    r"\bmodel loading/inference\b",
    r"\bstart model\b",
    r"\bmodel runtime start\b",
    r"\bwrite trusted memory\b",
    r"\btrusted-memory write\b",
    r"\broute/startup mutation\b",
    r"\bstartup autorun\b",
    r"\bpackage refresh/live promotion\b",
    r"\bpackage refresh implementation\b",
    r"\blive promotion\b",
    r"\bgui action button addition\b",
    r"\badd action button\b",
    r"\bsecurity/authority hierarchy change\b",
    r"\bqueue/runtime activation\b",
    r"\bbackground worker/autonomous loop\b",
    r"\bstart worker\b",
    r"\barbitrary refactor\b",
    r"\bexternal drive access\b",
    r"\bpackage manager change\b",
    r"\blive/staging artifact mutation\b",
    r"\bbinary file mutation\b",
    r"\bunknown source file mutation\b",
]


class PatchRunnerError(ValueError):
    pass


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def relative_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("/", "\\")


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_patch_candidate_file_name(file_name: str) -> str:
    if any(separator in file_name for separator in ("\\", "/")):
        raise PatchRunnerError("Only a patch candidate file name is accepted, not a path.")
    if ".." in file_name or ":" in file_name:
        raise PatchRunnerError("Path traversal and drive names are not accepted.")
    if file_name.startswith("\\\\"):
        raise PatchRunnerError("UNC paths are not accepted.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.md", file_name):
        raise PatchRunnerError("Patch candidate names must be safe .md file names.")
    return file_name


def resolve_patch_candidate(file_name: str) -> Path:
    safe_name = safe_patch_candidate_file_name(file_name)
    root = PATCH_CANDIDATE_DIR.resolve()
    path = (root / safe_name).resolve()
    if not is_relative_to(path, root):
        raise PatchRunnerError("Patch candidate escaped reports\\patch_candidates.")
    if not path.exists() or not path.is_file():
        raise PatchRunnerError("Patch candidate was not found in reports\\patch_candidates.")
    return path


def parse_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current:
            sections[current] = "\n".join(buffer).strip()

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current = line[3:].strip().lower().replace("-", "_")
            buffer = []
            continue
        if current:
            buffer.append(line)
    flush()
    return sections


def section_value(sections: dict[str, str], *names: str) -> str:
    for name in names:
        value = sections.get(name.lower().replace("-", "_"), "").strip()
        if value:
            return value
    return ""


def first_line(value: str) -> str:
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped.removeprefix("- ").strip()
    return ""


def extract_patch_class(text: str, sections: dict[str, str]) -> tuple[str, str]:
    explicit = first_line(section_value(sections, "patch_class", "allowed_low_risk_patch_class"))
    if explicit:
        return explicit, "explicit patch_class"
    lowered = text.lower()
    found = [class_name for class_name in IMPLEMENTED_V1_PATCH_CLASSES + DRY_RUN_ONLY_PATCH_CLASSES if class_name in lowered]
    if len(found) == 1:
        return found[0], "single class name found in patch candidate text"
    if len(found) > 1:
        return "", "multiple low-risk classes found; human review required"
    return "", "no explicit implemented low-risk patch class found"


def high_risk_reason(text: str) -> str:
    for raw_line in text.lower().splitlines():
        line = raw_line.strip().removeprefix("- ").strip()
        if not line:
            continue
        if line.startswith(("no ", "not ", "does not ", "do not ", "blocked ", "without ")):
            continue
        for stop_class in HIGH_RISK_STOP_CLASSES:
            if stop_class.lower() in line:
                return "STOP_ON_HIGH_RISK: patch candidate names high-risk class: " + stop_class
        for pattern in POSITIVE_HIGH_RISK_PATTERNS:
            if re.search(pattern, line):
                return "STOP_ON_HIGH_RISK: patch candidate includes active high-risk intent: " + pattern
    return ""


def reject_unsafe_target_name(target_file: str) -> None:
    normalized = target_file.replace("/", "\\")
    lowered = normalized.lower()
    if not normalized or normalized.strip() != normalized:
        raise PatchRunnerError("Target file is missing or has unsafe whitespace.")
    if normalized.startswith("\\\\") or normalized.startswith("\\") or ":" in normalized:
        raise PatchRunnerError("Absolute, UNC, and drive-qualified target paths are not allowed.")
    if ".." in normalized:
        raise PatchRunnerError("Path traversal is not allowed in target paths.")
    if lowered.startswith(("live\\", "staging\\")):
        raise PatchRunnerError("live\\ and staging\\ artifacts are not patch runner targets.")
    for marker in ("*", "?", "[", "]"):
        if marker in normalized:
            raise PatchRunnerError("Wildcard target paths are not allowed.")


def resolve_target_path(target_file: str) -> Path:
    reject_unsafe_target_name(target_file)
    path = (PROJECT_ROOT / target_file).resolve()
    if not is_relative_to(path, PROJECT_ROOT.resolve()):
        raise PatchRunnerError("Target file escaped the project root.")
    if not path.exists() or not path.is_file():
        raise PatchRunnerError("Target file does not exist in the project.")
    if path.suffix.lower() in [".exe", ".dll", ".pyd", ".pyc", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".ico"]:
        raise PatchRunnerError("Binary file mutation is blocked.")
    return path


def target_allowed_for_class(path: Path, patch_class: str) -> tuple[bool, str]:
    rel = relative_path(path)
    lower_rel = rel.lower()
    reports_prefix = "reports\\codex_bridge\\"
    memory_prefix = "memory\\"
    if patch_class == "generated_report_metadata_update":
        return (
            lower_rel.startswith(reports_prefix) and lower_rel.endswith(".md"),
            "generated report metadata updates are limited to reports\\codex_bridge\\*.md",
        )
    if patch_class == "codex_bridge_report_reference_update":
        allowed = (
            lower_rel.startswith(reports_prefix) and lower_rel.endswith(".md")
        ) or lower_rel in [
            "memory\\engel_core_continuity_map_v1.md",
            "memory\\engel_core_continuity_map_v1.json",
        ]
        return allowed, "report reference updates are limited to reports\\codex_bridge\\*.md or Core Continuity docs"
    if patch_class == "documentation_typo_or_label_fix":
        allowed = (
            lower_rel.startswith(reports_prefix) and lower_rel.endswith(".md")
        ) or (
            lower_rel.startswith(memory_prefix) and path.suffix.lower() in [".md", ".json"]
        )
        return allowed, "documentation typo/label fixes are limited to reports\\codex_bridge\\*.md or memory\\*.md/json"
    if patch_class == "read_only_status_surface_label_fix":
        return (
            rel in READ_ONLY_STATUS_SURFACE_FILES,
            "read-only status label fixes are limited to known read-only status surface files",
        )
    return False, "patch class is not implemented by runner V1"


def validate_patch_text(find_text: str, replace_text: str) -> None:
    if not find_text or not replace_text:
        raise PatchRunnerError("Patch candidate must include non-empty find_text and replace_text sections.")
    if find_text == replace_text:
        raise PatchRunnerError("find_text and replace_text are identical.")
    if len(find_text) > MAX_PATCH_TEXT_CHARS or len(replace_text) > MAX_PATCH_TEXT_CHARS:
        raise PatchRunnerError("Patch text is too large for low-risk V1.")


def make_patch_run_id(source_id: str, mode: str, timestamp: str) -> str:
    seed = f"{RUNNER_VERSION}|{source_id}|{mode}|{timestamp}".encode("utf-8")
    return "code_companion_patch_run_" + hashlib.sha256(seed).hexdigest()[:16]


def verification_command_text() -> str:
    return "\n".join("- " + command for command in POST_APPLY_VERIFICATION_COMMANDS)


def build_receipt(
    source_id: str,
    source_path: Path,
    patch_class: str,
    mode: str,
    files_changed: list[str],
    patch_summary: str,
    stopped: bool,
    stop_reason: str,
) -> dict[str, object]:
    timestamp = now_utc()
    return {
        "patch_run_id": make_patch_run_id(source_id, mode, timestamp),
        "source_patch_candidate_id": source_id,
        "source_patch_candidate_path": relative_path(source_path),
        "patch_class": patch_class or "unknown",
        "mode": mode,
        "files_changed": files_changed,
        "patch_summary": patch_summary,
        "verification_commands": verification_command_text(),
        "verification_result": "not_run_by_runner_v1_no_shell_execution",
        "safety_scan_result": "runner_preflight_scan_passed" if not stopped else "runner_stopped_before_apply",
        "commit_hash": "not_committed_by_runner_v1",
        "stopped": stopped,
        "stop_reason": stop_reason,
        "human_intervention_required": stopped or mode != "apply",
        "rollback_notes": "Review git diff and revert manually if a human-approved rollback is needed.",
        "no_trusted_memory_write": True,
        "no_provider_network_browser": True,
        "no_background_worker": True,
        "no_package_refresh": True,
        "no_route_startup_mutation": True,
    }


def render_receipt(receipt: dict[str, object]) -> str:
    lines = [
        "# Engel Code Companion Patch Receipt V1",
        "",
        "Runner status:",
        *["- " + status for status in RUNNER_STATUS],
        "",
        "Receipt boundary:",
        "- receipt only",
        "- no trusted memory write",
        "- no provider/network/browser",
        "- no model runtime",
        "- no package refresh",
        "- no route/startup mutation",
        "- no background worker",
        "- no commit automation",
        "",
    ]
    for field in RECEIPT_FIELDS:
        value = receipt.get(field, "")
        if isinstance(value, list):
            rendered = "\n".join("- " + item for item in value) if value else "none"
        elif isinstance(value, bool):
            rendered = "true" if value else "false"
        else:
            rendered = str(value)
        lines.extend(["## " + field, rendered, ""])
    return "\n".join(lines).rstrip() + "\n"


def safe_receipt_filename(receipt: dict[str, object]) -> str:
    run_id = str(receipt["patch_run_id"])
    patch_class = re.sub(r"[^A-Za-z0-9_-]+", "_", str(receipt["patch_class"])).strip("_")
    return f"{run_id}_{patch_class}.md"


def write_receipt(receipt: dict[str, object]) -> Path:
    root = RECEIPT_DIR.resolve()
    if not is_relative_to(root, PROJECT_ROOT.resolve()):
        raise PatchRunnerError("Receipt directory escaped the project root.")
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    path = (root / safe_receipt_filename(receipt)).resolve()
    if not is_relative_to(path, root):
        raise PatchRunnerError("Receipt path escaped reports\\code_companion_patch_receipts.")
    path.write_text(render_receipt(receipt), encoding="utf-8", newline="\n")
    return path


def evaluate_patch_candidate(file_name: str, mode: str) -> dict[str, object]:
    source_path = resolve_patch_candidate(file_name)
    text = source_path.read_text(encoding="utf-8", errors="replace")
    sections = parse_sections(text)
    source_id = first_line(section_value(sections, "patch_candidate_id", "source_patch_candidate_id")) or source_path.stem
    patch_class, class_reason = extract_patch_class(text, sections)
    summary = section_value(sections, "patch_summary", "summary", "proposed_changes") or "No patch summary supplied."

    stop_reason = high_risk_reason(text)
    if not stop_reason and not patch_class:
        stop_reason = "STOP_ON_UNCLEAR_RISK: " + class_reason
    if not stop_reason and patch_class in DRY_RUN_ONLY_PATCH_CLASSES:
        stop_reason = "V1 dry-run only: " + patch_class + " is classified but not applied by runner V1."
    if not stop_reason and patch_class not in IMPLEMENTED_V1_PATCH_CLASSES:
        stop_reason = "STOP_ON_UNCLEAR_RISK: patch class is not implemented by runner V1."

    target_file = first_line(section_value(sections, "target_file", "target_path"))
    find_text = section_value(sections, "find_text", "before_text")
    replace_text = section_value(sections, "replace_text", "after_text")
    target_path: Path | None = None
    if not stop_reason:
        try:
            target_path = resolve_target_path(target_file)
            allowed, reason = target_allowed_for_class(target_path, patch_class)
            if not allowed:
                raise PatchRunnerError(reason)
            validate_patch_text(find_text, replace_text)
            current = target_path.read_text(encoding="utf-8", errors="replace")
            occurrences = current.count(find_text)
            if occurrences != 1:
                raise PatchRunnerError("find_text must match the target exactly once; found " + str(occurrences) + ".")
        except PatchRunnerError as exc:
            stop_reason = "STOP_ON_UNCLEAR_RISK: " + str(exc)

    files_changed: list[str] = []
    if mode == "apply" and not stop_reason and target_path is not None:
        current = target_path.read_text(encoding="utf-8", errors="replace")
        target_path.write_text(current.replace(find_text, replace_text, 1), encoding="utf-8", newline="\n")
        files_changed = [relative_path(target_path)]

    receipt = build_receipt(
        source_id=source_id,
        source_path=source_path,
        patch_class=patch_class,
        mode=mode,
        files_changed=files_changed,
        patch_summary=summary,
        stopped=bool(stop_reason),
        stop_reason=stop_reason,
    )
    return {
        "source_path": source_path,
        "source_id": source_id,
        "patch_class": patch_class,
        "mode": mode,
        "stopped": bool(stop_reason),
        "stop_reason": stop_reason,
        "files_changed": files_changed,
        "receipt": receipt,
        "receipt_path": "",
    }


def run_patch_candidate(file_name: str, mode: str) -> dict[str, object]:
    result = evaluate_patch_candidate(file_name, mode)
    if mode == "apply":
        receipt_path = write_receipt(result["receipt"])
        result["receipt_path"] = relative_path(receipt_path)
    return result


def render_result(result: dict[str, object]) -> str:
    lines = [
        "Engel Code Companion Low-Risk Patch Runner V1",
        "Status: " + " / ".join(RUNNER_STATUS),
        "",
        "Patch candidate:",
        "- " + relative_path(result["source_path"]),
        "- source_patch_candidate_id: " + str(result["source_id"]),
        "- patch_class: " + str(result["patch_class"] or "unknown"),
        "- mode: " + str(result["mode"]),
        "- stopped: " + ("true" if result["stopped"] else "false"),
        "- stop_reason: " + (str(result["stop_reason"]) if result["stop_reason"] else "none"),
        "- files_changed: " + (", ".join(result["files_changed"]) if result["files_changed"] else "none"),
        "- receipt_path: " + (str(result["receipt_path"]) if result["receipt_path"] else "not_written_for_dry_run"),
        "",
        "Receipt preview:",
        render_receipt(result["receipt"]).rstrip(),
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_status() -> str:
    lines = [
        "Engel Code Companion Low-Risk Patch Runner V1",
        "",
        "Status:",
        *["- " + status for status in RUNNER_STATUS],
        "",
        "Implemented V1 patch classes:",
        *["- " + class_name for class_name in IMPLEMENTED_V1_PATCH_CLASSES],
        "",
        "V1 dry-run-only patch classes:",
        *["- " + class_name for class_name in DRY_RUN_ONLY_PATCH_CLASSES],
        "",
        "High-risk stop classes:",
        *["- " + class_name for class_name in HIGH_RISK_STOP_CLASSES],
        "",
        "Bounded input and output:",
        "- input: reports\\patch_candidates\\<explicit-file-name>.md",
        "- receipts: reports\\code_companion_patch_receipts\\",
        "- no recursive scan",
        "",
        "V1 apply path boundary:",
        "- reports\\codex_bridge\\*.md",
        "- memory\\*.md",
        "- memory\\*.json",
        "- read-only status surface Python files for label/text constants only",
        "- no live\\ or staging\\ artifact mutation",
        "- no package files",
        "- no route/startup files",
        "- no provider/network/browser/model integration files",
        "",
        "Required explicit patch candidate fields:",
        "- patch_class",
        "- target_file",
        "- find_text",
        "- replace_text",
        "",
        "Receipt fields:",
        *["- " + field for field in RECEIPT_FIELDS],
        "",
        "CLI:",
        "- python engel_code_companion_low_risk_patch_runner.py --status",
        "- python engel_code_companion_low_risk_patch_runner.py --patch-candidate <patch-file-name> --dry-run",
        "- python engel_code_companion_low_risk_patch_runner.py --patch-candidate <patch-file-name> --apply --password-prompt",
        "",
        "Boundary:",
        "Runner V1 does not call providers, use network, open a browser, start model runtime, write trusted memory, refresh packages, mutate routes/startup, start background workers, execute verifiers, or commit automatically.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply only explicit, bounded, preapproved Code Companion low-risk patch candidates."
    )
    parser.add_argument("--status", action="store_true", help="Print runner status and safety boundary.")
    parser.add_argument("--patch-candidate", metavar="PATCH_FILE_NAME", help="Explicit patch candidate file name in reports\\patch_candidates.")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate the patch candidate without writing target files or receipts.")
    parser.add_argument("--apply", action="store_true", help="Apply a clearly classified V1 low-risk patch and write a receipt.")
    parser.add_argument("--password-prompt", action="store_true", help="Prompt for the global password before protected apply mode.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.status:
        out.write(render_status())
        return 0
    if not args.patch_candidate or (args.dry_run == args.apply):
        err.write("Choose --status or one explicit --patch-candidate with exactly one of --dry-run or --apply.\n")
        return 2
    mode = "apply" if args.apply else "dry-run"
    if args.apply and not args.password_prompt:
        err.write("Protected action requires --password-prompt.\n")
        return 2
    try:
        if args.apply:
            global_password_gate.prompt_and_require_action("run_code_companion_low_risk_patch_apply")
        result = run_patch_candidate(args.patch_candidate, mode)
    except global_password_gate.PasswordGateError as exc:
        err.write("[STOPPED] " + str(exc) + "\n")
        return 1
    except PatchRunnerError as exc:
        err.write("[REJECTED] " + str(exc) + "\n")
        return 1
    out.write(render_result(result))
    return 1 if result["stopped"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
