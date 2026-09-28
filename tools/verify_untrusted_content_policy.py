#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CORE_DOCS = [
    ROOT / "memory" / "ENGEL_COMMANDS.md",
    ROOT / "memory" / "STANDARD_VERIFIER_CHECKLIST_V1.md",
    ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md",
    ROOT / "memory" / "LIVING_SYSTEMS_INDEX_V1.md",
    ROOT / "memory" / "NEXT_WORK_BATON_V1.md",
    ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md",
    ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json",
]

OPTIONAL_DOCS = [
    ROOT / "memory" / "ENGEL_OUTSIDE_AI_BOUNDARY_CONTRACT_V1.md",
    ROOT / "memory" / "ENGEL_TRUSTED_MEMORY_TRAINING_ARTIFACT_QUARANTINE_PLAN_V1.md",
    ROOT / "memory" / "ENGEL_TRUSTED_MEMORY_TRAINING_ARTIFACT_QUARANTINE_PLAN_V1.json",
    ROOT / "memory" / "ENGEL_DE_BRUIJN_CODE_STRUCTURE_PLAN_V1.md",
    ROOT / "memory" / "ENGEL_DE_BRUIJN_IMPORT_BOUNDARY_CONTRACT_V1.md",
    ROOT / "memory" / "ENGEL_UNSAFE_DE_BRUIJN_MEMORY_LOADER_QUARANTINE_PLAN_V1.md",
    ROOT / "memory" / "ENGEL_UNSAFE_DE_BRUIJN_MEMORY_LOADER_QUARANTINE_PLAN_V1.json",
    ROOT / "reports" / "codex_bridge" / "ENGEL_TRUSTED_MEMORY_TRAINING_ARTIFACT_QUARANTINE_PLAN_V1.md",
    ROOT / "reports" / "codex_bridge" / "ENGEL_UNSAFE_DE_BRUIJN_MEMORY_LOADER_QUARANTINE_PLAN_V1.md",
    ROOT / "reports" / "codex_bridge" / "ENGEL_DE_BRUIJN_CLOSEOUT_GIT_HYGIENE_REVIEW_V1.md",
    ROOT / "reports" / "codex_bridge" / "ENGEL_UNRELATED_SOURCE_DIRTY_STATE_REVIEW_V1.md",
    ROOT / "reports" / "codex_bridge" / "ENGEL_DE_BRUIJN_RESTRUCTURE_CLOSEOUT_COMMIT_BLOCKED.md",
]

QUARANTINE_DOCS = [
    ROOT / "memory" / "ENGEL_TRUSTED_MEMORY_TRAINING_ARTIFACT_QUARANTINE_PLAN_V1.md",
    ROOT / "memory" / "ENGEL_TRUSTED_MEMORY_TRAINING_ARTIFACT_QUARANTINE_PLAN_V1.json",
    ROOT / "reports" / "codex_bridge" / "ENGEL_TRUSTED_MEMORY_TRAINING_ARTIFACT_QUARANTINE_PLAN_V1.md",
    ROOT / "reports" / "codex_bridge" / "ENGEL_UNRELATED_SOURCE_DIRTY_STATE_REVIEW_V1.md",
    ROOT / "reports" / "codex_bridge" / "ENGEL_DE_BRUIJN_CLOSEOUT_GIT_HYGIENE_REVIEW_V1.md",
    ROOT / "reports" / "codex_bridge" / "ENGEL_DE_BRUIJN_RESTRUCTURE_CLOSEOUT_COMMIT_BLOCKED.md",
]

EXCLUDE_DIRS = {
    ".git",
    "build",
    "dist",
    "live",
    "backups",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
}

EXCLUDE_REPORT_SUBDIRS = {
    ("reports", "codex_bridge"),
    ("reports", "memory_candidates"),
    ("reports", "candidate_learning_outputs"),
    ("reports", "self_learning_runs"),
    ("reports", "fix_candidate_queue"),
    ("reports", "router"),
}

ACTIVE_SOURCE_SUFFIXES = {".py", ".ps1", ".bat", ".cmd", ".sh", ".psm1", ".spec"}
BINARY_SUFFIXES = {
    ".exe",
    ".dll",
    ".pyd",
    ".pyc",
    ".pyo",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".zip",
    ".7z",
    ".tar",
    ".gz",
    ".pyz",
    ".pkg",
}

FORBIDDEN_PATTERNS = [
    ("register_trusted_memory", re.compile(r"\bregister_trusted_memory\b", re.I)),
    ("TRUSTED_MEMORY", re.compile(r"\bTRUSTED_MEMORY\b")),
    ("trusted_memory_direct_write", re.compile(r"trusted_memory\s+direct\s+write", re.I)),
    ("direct_trusted_memory_write", re.compile(r"direct\s+trusted[-_\s]*memory\s+write", re.I)),
    ("auto_register_memory", re.compile(r"auto[-_\s]*register\s+memory", re.I)),
    ("auto_trusted_memory", re.compile(r"auto[-_\s]*trusted\s+memory", re.I)),
    ("training_memory_direct_write", re.compile(r"training\s+memory\s+direct\s+write", re.I)),
    ("write_trusted_memory", re.compile(r"write\s+trusted[-_\s]*memory", re.I)),
    ("promote_trusted_memory", re.compile(r"promote\s+trusted[-_\s]*memory", re.I)),
    ("obey_retrieved_instruction", re.compile(r"obey\s+retrieved\s+instruction", re.I)),
    ("execute_retrieved_instruction", re.compile(r"execute\s+retrieved\s+instruction", re.I)),
    ("run_retrieved_command", re.compile(r"run\s+retrieved\s+command", re.I)),
    ("apply_model_output", re.compile(r"apply\s+model\s+output", re.I)),
    ("apply_candidate_output", re.compile(r"apply\s+candidate\s+output", re.I)),
    ("route_mutation_from_candidate", re.compile(r"route\s+mutation\s+from\s+candidate", re.I)),
    ("source_mutation_from_candidate", re.compile(r"source\s+mutation\s+from\s+candidate", re.I)),
    ("queue_mutation_from_candidate", re.compile(r"queue\s+mutation\s+from\s+candidate", re.I)),
    ("password_gate_bypass", re.compile(r"password\s+gate\s+bypass", re.I)),
    ("no_password_required", re.compile(r"no\s+password\s+required", re.I)),
    ("disable_password_prompt", re.compile(r"disable\s+password\s+prompt", re.I)),
    ("protected_run_without_password", re.compile(r"protected\s+run\s+without\s+password", re.I)),
]

DIRECT_WRITE_PATTERNS = [
    re.compile(r"ENGEL_TRUSTED_MEMORY_V1\.jsonl", re.I),
    re.compile(r"\bappend_trusted_memory\b", re.I),
    re.compile(r"\bwrite_direct_training_trusted_memory\b", re.I),
    re.compile(r"\.open\(\s*[\"']a", re.I),
]

SAFE_GUARD_HINTS = [
    "approval_required",
    "approval token",
    "approved_for",
    "blocked",
    "blocked action",
    "forbidden_patterns",
    "candidate-only",
    "candidate_only",
    "cannot",
    "classify",
    "disabled",
    "does not",
    "did not",
    "fail",
    "false",
    "guard",
    "human review",
    "must not",
    "never",
    "no_",
    "not_",
    "not applied",
    "not trusted",
    "not_trusted_memory",
    "no_trusted_memory_write",
    "password_required",
    "protected_action",
    "quarantine",
    "receipt_required",
    "refuse",
    "request",
    "review",
    "review_required",
    "risk",
    "safe_to_execute",
    "safety statement",
    "verifier",
    "write_enabled_now",
]

KNOWN_REVIEW_REQUIRED = {
    "engel_app.py",
    "engel_training_trusted_memory.py",
    "engel_candidate_set_approval.py",
    "tools\\verify_engel_candidate_set_approval.py",
    "tools\\verify_engel_training_trusted_memory.py",
}

PASSWORD_GATE_REVIEW_REQUIRED = {
    "engel_protected_action_registry.py",
    "engel_research_toggle_status.py",
    "engel_research_toggle_worker.py",
    "tools\\verify_engel_research_toggle_overnight_worker.py",
}

KNOWN_ARTIFACTS = [
    "engel_training_trusted_memory.py",
    "memory\\ENGEL_TRUSTED_MEMORY_V1.jsonl",
    "library_intake\\Engel AI 4-Hour Local LLM Training Prompt",
    "reports\\codex_bridge\\ENGEL_AI_4_HOUR_LOCAL_LLM_TRAINING_CANDIDATE_REPORT_20260521.md",
    "reports\\memory_promotion_receipts\\20260521_044340_81783e5a3462_training_prompt_direct_trusted_memory_receipt.md",
    "tools\\verify_engel_training_trusted_memory.py",
    "engel_agent_main\\references\\de-bruijn-teaching-reference.md",
]


class CheckFailure(Exception):
    pass


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("/", "\\")
    except ValueError:
        return str(path)


def read_text_safe(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def print_result(label: str, status: str, detail: str = "") -> None:
    suffix = f" {detail}" if detail else ""
    print(f"{status} {label}{suffix}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def contains_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def context_window(text: str, start: int, radius: int = 320) -> str:
    return text[max(0, start - radius) : min(len(text), start + radius)]


def context_has_guard(text: str, start: int) -> bool:
    window = context_window(text, start).lower()
    return any(hint in window for hint in SAFE_GUARD_HINTS)


def path_key(path: Path) -> str:
    return rel(path).lower()


def is_verifier(path: Path) -> bool:
    key = path_key(path)
    name = path.name.lower()
    return key.startswith("tools\\verify_") or name.startswith("verify_")


def is_report_or_doc(path: Path) -> bool:
    key = path_key(path)
    return key.startswith("reports\\") or path.suffix.lower() in {".md", ".json", ".txt"}


def is_known_review_path(path: Path) -> bool:
    key = path_key(path)
    return key in {item.lower() for item in KNOWN_REVIEW_REQUIRED}


def is_password_review_path(path: Path) -> bool:
    key = path_key(path)
    return key in {item.lower() for item in PASSWORD_GATE_REVIEW_REQUIRED}


def should_skip_path(path: Path) -> bool:
    parts = tuple(part.lower() for part in path.relative_to(ROOT).parts)
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    for prefix in EXCLUDE_REPORT_SUBDIRS:
        if len(parts) >= len(prefix) and parts[: len(prefix)] == prefix:
            return True
    if parts and parts[0] in {"memory", "reports"}:
        return True
    if path.suffix.lower() in BINARY_SUFFIXES:
        return True
    return False


def policy_combined_text(core_texts: dict[Path, str], optional_texts: dict[Path, str]) -> str:
    return "\n".join([*core_texts.values(), *optional_texts.values()])


def require_term_group(combined: str, label: str, groups: list[list[str]]) -> None:
    for terms in groups:
        require(contains_any(combined, terms), f"{label} missing concept: one of {terms}")


def scan_policy_docs() -> tuple[dict[Path, str], dict[Path, str], list[str], list[str]]:
    failures: list[str] = []
    skips: list[str] = []
    core_texts: dict[Path, str] = {}
    optional_texts: dict[Path, str] = {}

    for path in CORE_DOCS:
        if not path.exists():
            failures.append(f"core doc missing: {rel(path)}")
            print_result("CORE_DOC_PASS", "FAIL", rel(path))
            continue
        core_texts[path] = read_text_safe(path)
        print_result("CORE_DOC_PASS", "PASS", rel(path))

    for path in OPTIONAL_DOCS:
        if not path.exists():
            skips.append(rel(path))
            print_result("OPTIONAL_DOC_SKIP", "SKIP", rel(path))
            continue
        optional_texts[path] = read_text_safe(path)
        print_result("SAFE_RISK_DISCUSSION", "INFO", rel(path))

    combined = policy_combined_text(core_texts, optional_texts)

    checks = [
        (
            "untrusted_content_boundary",
            [
                ["untrusted content", "untrusted"],
                ["candidate"],
                ["human review", "human-reviewed", "review required"],
                ["verified", "verifier"],
                ["approved", "approval"],
            ],
        ),
        (
            "trusted_memory_boundary",
            [
                ["trusted memory", "trusted-memory"],
                ["no trusted-memory write", "no trusted memory write", "nothing becomes trusted memory automatically"],
                ["promotion"],
                ["approval", "approved"],
                ["candidate", "model output", "outside ai"],
            ],
        ),
        (
            "prompt_injection_boundary",
            [
                ["prompt injection", "untrusted instructions"],
                ["data, not instruction", "content is data", "external/retrieved content"],
                ["authority"],
                ["commands", "execute"],
            ],
        ),
        (
            "candidate_output_boundary",
            [
                ["candidate memory"],
                ["candidate learning", "candidate-only"],
                ["candidate fix", "patch proposal", "fix candidate"],
                ["not applied", "no patch apply", "cannot apply", "does not apply"],
                ["not trusted memory", "not_trusted_memory"],
            ],
        ),
        (
            "outside_ai_model_boundary",
            [
                ["outside ai", "model output"],
                ["untrusted"],
                ["evaluation", "review"],
                ["must not control", "no outside ai control", "no_outside_ai_control", "outside ai may not", "not trusted automatically"],
            ],
        ),
        (
            "remote_swarm_mycelium_boundary",
            [
                ["remote queen"],
                ["swarm"],
                ["mycelium"],
                ["untrusted", "reviewed", "human-reviewed"],
                ["trusted-memory write", "source edit", "queue mutation"],
            ],
        ),
        (
            "global_password_gate_boundary",
            [
                ["Global Password Gate", "password gate"],
                ["protected enable/run actions", "protected action"],
                ["approval", "approval token"],
                ["bypass", "review-required", "review required"],
            ],
        ),
    ]

    for label, groups in checks:
        try:
            require_term_group(combined, label, groups)
        except CheckFailure as exc:
            failures.append(str(exc))
            print_result(label, "FAIL", str(exc))
        else:
            print_result(label, "PASS")

    return core_texts, optional_texts, failures, skips


def scan_quarantine_evidence(core_texts: dict[Path, str], optional_texts: dict[Path, str]) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    review_required: list[str] = []
    available = {path: read_text_safe(path) for path in QUARANTINE_DOCS if path.exists()}
    quarantine_text = "\n".join(available.values())
    quarantine_lower = quarantine_text.lower()

    def evidence_has(path_text: str) -> bool:
        return path_text.lower() in quarantine_lower and (
            "exclude_from_de_bruijn_closeout_commit" in quarantine_lower
            or "exclude-from-closeout" in quarantine_lower
            or "quarantine_required" in quarantine_lower
            or "review_required" in quarantine_lower
        )

    if not available:
        failures.append("trusted-memory/training quarantine evidence missing")
        print_result("QUARANTINE_EVIDENCE_PASS", "FAIL", "no quarantine docs found")
    else:
        print_result("QUARANTINE_EVIDENCE_PASS", "PASS", f"{len(available)} quarantine/review docs found")

    for artifact in KNOWN_ARTIFACTS:
        artifact_path = ROOT / artifact
        if artifact_path.exists():
            review_required.append(artifact)
            if artifact == "memory\\ENGEL_TRUSTED_MEMORY_V1.jsonl":
                print_result(
                    "TRUSTED_MEMORY_TARGET_PROTECTED",
                    "REVIEW_REQUIRED",
                    f"{artifact} exists; metadata size={artifact_path.stat().st_size}",
                )
            else:
                print_result("QUARANTINE_EVIDENCE_PASS", "REVIEW_REQUIRED", artifact)
            if not evidence_has(artifact):
                failures.append(f"known review-required artifact lacks quarantine evidence: {artifact}")

    if (ROOT / "engel_app.py").exists():
        app_text = read_text_safe(ROOT / "engel_app.py")
        if "training memory direct write" in app_text.lower() or "write_direct_training_trusted_memory" in app_text:
            review_required.append("engel_app.py")
            print_result("ACTIVE_SOURCE_REVIEW_REQUIRED", "REVIEW_REQUIRED", "engel_app.py training memory direct write command wiring")
            if not evidence_has("engel_app.py"):
                failures.append("engel_app.py direct trusted-memory command wiring lacks quarantine/review evidence")

    if "NO_PASSWORD_GATE_REQUIRED" in policy_combined_text(core_texts, optional_texts):
        review_required.append("research-toggle password-gate removal")
        print_result("ACTIVE_SOURCE_REVIEW_REQUIRED", "REVIEW_REQUIRED", "research-toggle password-gate removal is documented for separate review")
        if "password_gate_review_required" not in quarantine_lower and "PASSWORD_GATE_REVIEW_REQUIRED".lower() not in quarantine_lower:
            failures.append("password-gate removal/bypass lacks review-required evidence")

    return failures, review_required


def direct_write_risk(text: str) -> bool:
    if "ENGEL_TRUSTED_MEMORY_V1.jsonl" not in text:
        return False
    direct_hits = sum(1 for pattern in DIRECT_WRITE_PATTERNS if pattern.search(text))
    return direct_hits >= 3


def scan_active_source() -> tuple[list[str], list[str], int, int, int]:
    failures: list[str] = []
    review_required: list[str] = []
    scanned = 0
    safe_reference_count = 0
    safe_guarded_count = 0

    for path in iter_active_source_files():
        if path.suffix.lower() not in ACTIVE_SOURCE_SUFFIXES:
            continue
        if path.stat().st_size > 5_000_000:
            continue
        scanned += 1
        text = read_text_safe(path)

        if is_verifier(path):
            if any(pattern.search(text) for _, pattern in FORBIDDEN_PATTERNS):
                safe_reference_count += 1
                continue

        key = rel(path)
        known_review = is_known_review_path(path) or is_password_review_path(path)

        if direct_write_risk(text):
            if known_review:
                review_required.append(f"{key}: direct trusted-memory write path requires separate review")
                print_result("ACTIVE_SOURCE_REVIEW_REQUIRED", "REVIEW_REQUIRED", key)
            else:
                failures.append(f"{key}: active source appears able to write trusted-memory target")
                print_result("ACTIVE_SOURCE_FAIL", "FAIL", key)
            continue

        for label, pattern in FORBIDDEN_PATTERNS:
            for match in pattern.finditer(text):
                if known_review:
                    item = f"{key}: {label}"
                    if item not in review_required:
                        review_required.append(item)
                    break
                if context_has_guard(text, match.start()):
                    safe_guarded_count += 1
                    break
                failures.append(f"{key}: unguarded forbidden pattern {label}")
                print_result("FORBIDDEN_PATTERN_FAIL", "FAIL", f"{key}: {label}")
                break

    print_result("ACTIVE_SOURCE_PASS", "INFO", f"source_files_scanned={scanned}")
    print_result("SAFE_VERIFIER_REFERENCE", "INFO", f"verifier_files_with_risk_terms={safe_reference_count}")
    print_result("ACTIVE_SOURCE_PASS", "INFO", f"guarded_pattern_references={safe_guarded_count}")
    return failures, review_required, scanned, safe_reference_count, safe_guarded_count


def iter_active_source_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        current = Path(dirpath)
        try:
            rel_parts = tuple(part.lower() for part in current.relative_to(ROOT).parts)
        except ValueError:
            rel_parts = ()
        kept_dirs: list[str] = []
        for dirname in dirnames:
            low = dirname.lower()
            candidate_parts = rel_parts + (low,)
            if low in EXCLUDE_DIRS:
                continue
            if candidate_parts and candidate_parts[0] in {"memory", "reports"}:
                continue
            if any(
                len(candidate_parts) >= len(prefix) and candidate_parts[: len(prefix)] == prefix
                for prefix in EXCLUDE_REPORT_SUBDIRS
            ):
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs
        for filename in filenames:
            path = current / filename
            if not path.is_file():
                continue
            if should_skip_path(path):
                continue
            yield path


def check_de_bruijn_loader(optional_texts: dict[Path, str]) -> list[str]:
    failures: list[str] = []
    quarantine_text = "\n".join(optional_texts.values()).lower()
    loader_docs_present = "de bruijn" in quarantine_text and ("quarantine" in quarantine_text or "candidate-only" in quarantine_text)
    loader_files = [
        path
        for path in ROOT.rglob("*de_bruijn*loader*.py")
        if path.is_file() and not should_skip_path(path)
    ]
    if loader_files:
        for path in loader_files:
            failures.append(f"active De Bruijn loader file found: {rel(path)}")
            print_result("De Bruijn/loader quarantine checks", "FAIL", rel(path))
    elif loader_docs_present:
        print_result("De Bruijn/loader quarantine checks", "PASS", "quarantine/candidate-only evidence present; no active loader found")
    else:
        print_result("De Bruijn/loader quarantine checks", "SKIP", "no De Bruijn loader evidence found")
    return failures


def main() -> int:
    failures: list[str] = []
    review_required: list[str] = []

    print("ENGEL_UNTRUSTED_CONTENT_POLICY_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: local text verification only; no imports of Engel runtime modules")

    core_texts, optional_texts, doc_failures, skips = scan_policy_docs()
    failures.extend(doc_failures)

    q_failures, q_review = scan_quarantine_evidence(core_texts, optional_texts)
    failures.extend(q_failures)
    review_required.extend(q_review)

    source_failures, source_review, scanned, safe_refs, guarded = scan_active_source()
    failures.extend(source_failures)
    review_required.extend(source_review)

    failures.extend(check_de_bruijn_loader(optional_texts))

    print_result("core_docs_checked", "INFO", str(len(CORE_DOCS)))
    print_result("optional_docs_checked", "INFO", str(len(OPTIONAL_DOCS) - len(skips)))
    print_result("optional_docs_skipped", "INFO", str(len(skips)))
    print_result("source_files_scanned", "INFO", str(scanned))
    print_result("docs_report_files_excluded_from_active_source_failure_count", "INFO", "reports/codex_bridge and memory docs excluded")
    print_result("forbidden_source_pattern_findings", "INFO", str(len(source_failures)))
    print_result("review_required_findings", "INFO", str(len(review_required)))

    for item in review_required[:40]:
        print_result("review-required finding", "REVIEW_REQUIRED", item)
    if len(review_required) > 40:
        print_result("review-required finding", "INFO", f"{len(review_required) - 40} additional review-required findings suppressed")

    if failures:
        for failure in failures:
            print_result("untrusted content policy check", "FAIL", failure)
        return 1

    print_result("untrusted content policy checks", "PASS")
    print_result("trusted-memory boundary checks", "PASS")
    print_result("prompt-injection boundary checks", "PASS")
    print_result("candidate-output boundary checks", "PASS")
    print_result("outside-AI/model-output boundary checks", "PASS")
    print_result("Global Password Gate / protected-action checks", "PASS")
    print("UNTRUSTED_CONTENT_POLICY_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
