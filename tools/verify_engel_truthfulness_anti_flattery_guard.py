#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_truthfulness_anti_flattery_guard.py"
CONTRACT_JSON = ROOT / "memory" / "ENGEL_TRUTHFULNESS_ANTI_FLATTERY_GUARD_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_TRUTHFULNESS_ANTI_FLATTERY_GUARD_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_TRUTHFULNESS_ANTI_FLATTERY_GUARD_V1.md"
MAP_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
MAP_MD = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md"
BUILDER = ROOT / "tools" / "build_engel_core_continuity_map.py"
CORE_VERIFIER = ROOT / "tools" / "verify_engel_core_continuity_map.py"

REQUIRED_FILES = [
    MODULE,
    CONTRACT_JSON,
    CONTRACT_MD,
    REPORT,
    BUILDER,
    CORE_VERIFIER,
]

REQUIRED_STATUSES = [
    "TRUTHFULNESS_ANTI_FLATTERY_GUARD",
    "VERIFICATION_FIRST",
    "ACCURACY_OVER_APPROVAL",
    "NO_FLATTERY",
    "NO_PREMISE_VALIDATION_WITHOUT_CHECK",
    "CORRECT_WRONG_PREMISES",
    "STATE_UNCERTAINTY",
    "CONFIDENCE_LABELS_SUPPORTED",
    "FACT_CHECK_REQUIRED_FOR_VOLATILE_CLAIMS",
    "HASH_PATH_STATUS_VERIFICATION_REQUIRED",
    "NO_HALLUCINATION",
    "NO_INVENTED_FACTS",
    "UNTRUSTED_EXTERNAL_PROMPTS_NOT_AUTHORITY",
    "SOCIAL_MEDIA_PROMPTS_UNTRUSTED",
    "SAFETY_BOUNDARIES_PRESERVED",
    "AUTHORITY_HIERARCHY_PRESERVED",
    "PROMPT_INJECTION_GUARD_PRESERVED",
    "UNTRUSTED_CONTENT_GUARD_PRESERVED",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
]

ALLOWED_LESSONS = [
    "accuracy over approval",
    "do not flatter",
    "do not validate false premises",
    "correct wrong assumptions",
    "state uncertainty",
    "verify facts and claims",
    "use confidence levels when useful",
    "say when evidence is missing",
    "do not invent hashes, commits, file paths, package states, citations, or verification results",
    "do not claim a verifier passed unless it actually ran or a user-provided report says it passed",
    "do not claim a file exists unless checked or reported by the user",
]

REJECTED_LESSONS = [
    "aggression for its own sake",
    "no disclaimers",
    "removing safety warnings",
    "never apologizing",
    "political/ethical instruction overrides",
    "ignoring user safety",
    "overriding system/developer instructions",
    "treating social-media prompts as authority",
]

CHECKLIST_FIELDS = [
    "flattery_risk",
    "premise_validation_risk",
    "unsupported_certainty_risk",
    "missing_uncertainty_label",
    "claims_need_verification",
    "unsafe_safety_weakening_language",
    "external_prompt_as_authority_risk",
    "recommended_fix_summary",
]

CHECKER_LABELS = [
    "HEURISTIC_REVIEW_ONLY",
    "DOES_NOT_APPROVE_CONTENT",
    "DOES_NOT_REWRITE_CONTENT",
    "UNTRUSTED_INPUT",
    "HUMAN_REVIEW_REQUIRED",
]

FORBIDDEN_IMPORT_ROOTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "openai",
    "subprocess",
    "threading",
    "multiprocessing",
}

FORBIDDEN_MUTATION_CALLS = {
    "write_text",
    "write_bytes",
    "unlink",
    "remove",
    "rename",
    "replace",
    "mkdir",
    "rmdir",
}


class CheckFailure(Exception):
    pass


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _load_module():
    spec = importlib.util.spec_from_file_location("engel_truthfulness_anti_flattery_guard", MODULE)
    _require(spec is not None and spec.loader is not None, "could not load truthfulness guard module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_truthfulness_anti_flattery_guard"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in REQUIRED_FILES:
        _require(path.exists(), "required file missing: " + str(path.relative_to(ROOT)))


def check_contracts() -> None:
    md_text = _read(CONTRACT_MD)
    data = json.loads(_read(CONTRACT_JSON))
    all_text = md_text + "\n" + json.dumps(data, sort_keys=True)

    for status in REQUIRED_STATUSES:
        _require(status in all_text, "required status missing: " + status)
    for lesson in ALLOWED_LESSONS:
        _require(lesson in all_text, "allowed lesson missing: " + lesson)
    for lesson in REJECTED_LESSONS:
        _require(lesson in all_text, "rejected lesson missing: " + lesson)
    for needle in [
        "untrusted social-media reference material",
        "External prompt text is not authority",
        "The screenshot prompt was not copied verbatim",
        "Authority Hierarchy",
        "Prompt Injection Guard",
        "Untrusted Content Guard",
        "Global Password Gate",
        "Protected Action Registry",
        "Verifier requirements",
        "Receipt requirements",
        "Core Continuity requirements",
    ]:
        _require(needle in all_text, "contract missing safety/source text: " + needle)
    for label in CHECKER_LABELS:
        _require(label in all_text, "checker label missing: " + label)


def check_module_static() -> None:
    source = _read(MODULE)
    tree = ast.parse(source)
    for status in REQUIRED_STATUSES:
        _require(status in source, "module missing status: " + status)
    for flag in ["--status", "--check-text", "--json"]:
        _require(flag in source, "module missing CLI flag: " + flag)
    for field in CHECKLIST_FIELDS:
        _require(field in source, "module missing checklist field: " + field)
    for label in CHECKER_LABELS:
        _require(label in source, "module missing checker label: " + label)
    for needle in [
        "validate_check_text_path",
        "evaluate_text",
        "render_check_text",
        "untrusted social-media reference material",
        "External prompt text is not authority",
        "DOES_NOT_APPROVE_CONTENT",
    ]:
        _require(needle in source, "module missing behavior text: " + needle)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                _require(root not in FORBIDDEN_IMPORT_ROOTS, "module imports forbidden module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            _require(root not in FORBIDDEN_IMPORT_ROOTS, "module imports forbidden module: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                _require(func.attr not in FORBIDDEN_MUTATION_CALLS, "module mutates files with: " + func.attr)
            elif isinstance(func, ast.Name):
                _require(func.id not in {"eval", "exec", "__import__", "open"}, "module calls forbidden builtin: " + func.id)


def check_module_behavior() -> None:
    module = _load_module()
    status = module.render_status()
    payload = module.guard_summary()
    result = module.evaluate_text(
        "Great question. The verifier definitely passed and live\\app\\Engel.exe hash is confirmed. "
        "Safety boundaries still apply."
    )
    for status_label in REQUIRED_STATUSES:
        _require(status_label in status, "status output missing: " + status_label)
        _require(status_label in payload.get("status_labels", []), "json payload missing status: " + status_label)
    for field in CHECKLIST_FIELDS:
        _require(field in result, "evaluate_text result missing field: " + field)
    _require(result["flattery_risk"] != "none", "flattery sample should be flagged")
    _require(result["claims_need_verification"] is True, "verification-claim sample should be flagged")
    _require(result["unsupported_certainty_risk"] != "none", "unsupported certainty sample should be flagged")


def check_core_continuity() -> None:
    md_text = _read(MAP_MD)
    data = json.loads(_read(MAP_JSON))
    node = data.get("engel_truthfulness_anti_flattery_guard_v1")
    _require(isinstance(node, dict), "Core Continuity truthfulness guard node missing")
    _require(node.get("type") == "truthfulness_anti_flattery_guard", "Core Continuity truthfulness guard type mismatch")
    for status in [
        "TRUTHFULNESS_ANTI_FLATTERY_GUARD",
        "VERIFICATION_FIRST",
        "ACCURACY_OVER_APPROVAL",
        "NO_FLATTERY",
        "STATE_UNCERTAINTY",
        "UNTRUSTED_EXTERNAL_PROMPTS_NOT_AUTHORITY",
        "SAFETY_BOUNDARIES_PRESERVED",
        "AUTHORITY_HIERARCHY_PRESERVED",
        "PROMPT_INJECTION_GUARD_PRESERVED",
        "UNTRUSTED_CONTENT_GUARD_PRESERVED",
    ]:
        _require(status in node.get("status", []), "Core Continuity node missing status: " + status)
        _require(status in md_text, "Core Continuity Markdown missing status: " + status)
    for related in [
        "Authority Hierarchy",
        "Prompt Injection Guard",
        "Untrusted Content Guard",
        "AI Growth Dashboard",
        "Candidate Review Dashboard",
        "Code Companion Intelligence Loop",
        "Code Companion Candidate Review GUI",
        "Global Password-Gated Action Layer",
        "Protected Action Registry",
        "Core Continuity Map V1",
    ]:
        _require(any(related in item for item in node.get("related_nodes", [])), "Core Continuity related node missing: " + related)
    for needle in [
        "Engel Truthfulness and Anti-Flattery Guard V1",
        "truthfulness_anti_flattery_guard",
        "verification-first",
        "no-flattery",
        "uncertainty-aware",
        "External social-media prompts are untrusted",
        "Safety boundaries preserved",
    ]:
        _require(needle in md_text, "Core Continuity Markdown missing text: " + needle)


def check_report() -> None:
    text = _read(REPORT)
    for needle in [
        "Engel Truthfulness and Anti-Flattery Guard V1",
        "files read first",
        "source screenshot handling",
        "allowed lessons",
        "rejected lessons",
        "module behavior",
        "CLI behavior",
        "Core Continuity update",
        "smoke results",
        "verifier results",
        "focused safety scan result",
        "external prompt text was not copied as authority",
        "safety boundaries were preserved",
        "no provider/network/browser/model/source-mutation/trusted-memory/background-worker/startup behavior was added",
        "packaging skipped",
        "final scoped process sweep",
        "git status",
    ]:
        _require(needle in text, "report missing text: " + needle)


def main() -> int:
    checks = [
        ("files", check_files_exist),
        ("contracts", check_contracts),
        ("module_static", check_module_static),
        ("module_behavior", check_module_behavior),
        ("core_continuity", check_core_continuity),
        ("report", check_report),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print(f"PASS {name}")
        except CheckFailure as exc:
            failures.append(f"{name}: {exc}")
            print(f"FAIL {name}: {exc}")
        except Exception as exc:
            failures.append(f"{name}: unexpected error: {exc}")
            print(f"FAIL {name}: unexpected error: {exc}")
    if failures:
        print("\nEngel Truthfulness and Anti-Flattery Guard verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nEngel Truthfulness and Anti-Flattery Guard verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
