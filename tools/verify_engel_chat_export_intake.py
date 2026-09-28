from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_chat_export_intake.py"
VERIFIER = ROOT / "tools" / "verify_engel_chat_export_intake.py"
INTAKE_ROOT = ROOT / "library_intake" / "chat_exports"
INCOMING = INTAKE_ROOT / "incoming"
REVIEWED = INTAKE_ROOT / "reviewed"
INVALID = INTAKE_ROOT / "invalid"
EXAMPLES = INTAKE_ROOT / "examples"
EXAMPLE_MD = EXAMPLES / "chat_export_example.md"
UNSUPPORTED_JSON = EXAMPLES / "unsupported_chat_export.json"
REPORTS_DIR = ROOT / "reports" / "chat_export_intake"
SMOKE_RECEIPT = REPORTS_DIR / "CHAT_EXPORT_INTAKE_VERIFIER_SMOKE.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CHAT_EXPORT_INTAKE_V1.md"

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "subprocess",
    "threading",
    "multiprocessing",
    "asyncio",
    "watchdog",
    "openai",
}

FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "__import__",
    "system",
    "popen",
    "Popen",
    "run",
    "call",
    "check_call",
    "check_output",
    "startfile",
    "rglob",
    "walk",
    "unlink",
    "remove",
    "rename",
}

REQUIRED_SOURCE_SNIPPETS = [
    "library_intake\" / \"chat_exports",
    "reports\" / \"chat_export_intake",
    "UNTRUSTED REVIEW ONLY",
    "unsupported extension; Phase 1 accepts .txt and .md only",
    "risky command-like or trust-related text found; content remains inert source material",
    "This receipt does not execute, apply, promote, route, queue, trust, or write trusted memory from chat content.",
    "MEMORY_CANDIDATE_PROPOSAL_ROOT",
    "Flutter SDK setup",
    "Android SDK cmdline-tools and license fix",
    "Remote Worker Phase 3 PC-side manual result intake planning",
    "Outside-AI / Hermes remains rejected / do not install boundary",
]

REQUIRED_COMMAND_DOCS = [
    "chat export intake status",
    "chat export intake list",
    "chat export intake validate",
    "chat export intake intake",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_module():
    spec = importlib.util.spec_from_file_location("engel_chat_export_intake", MODULE)
    require(spec is not None and spec.loader is not None, "could not load chat export intake module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_chat_export_intake"] = module
    spec.loader.exec_module(module)
    return module


def snapshot_paths() -> set[str]:
    paths: set[str] = set()
    for folder in [INCOMING, REVIEWED, INVALID, REPORTS_DIR]:
        if not folder.exists():
            continue
        for path in folder.iterdir():
            paths.add(str(path.resolve(strict=False)))
    return paths


def check_files_and_folders() -> None:
    for path in [MODULE, VERIFIER, INTAKE_ROOT, INCOMING, REVIEWED, INVALID, EXAMPLES, EXAMPLE_MD, UNSUPPORTED_JSON, REPORTS_DIR]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_static_source() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for snippet in REQUIRED_SOURCE_SNIPPETS:
        require(snippet in source, "module missing required source snippet: " + snippet)
    for forbidden_text in [
        "trusted_memory.write",
        "mutate_routes(",
        "mutate_queue(",
        "apply_patch(",
        "watchdog.Observer",
        "Timer(",
        "while True",
        "auto-import at startup",
        "provider_api",
    ]:
        require(forbidden_text not in source, "module contains forbidden text: " + forbidden_text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                require(root_name not in FORBIDDEN_IMPORTS, "module imports forbidden package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".")[0]
            require(root_name not in FORBIDDEN_IMPORTS, "module imports forbidden package: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            require(name not in FORBIDDEN_CALLS, "module contains forbidden call: " + name)
        elif isinstance(node, (ast.While, ast.AsyncFunctionDef)):
            raise CheckFailure("module contains forbidden loop/async behavior")


def check_validation_behavior() -> None:
    module = load_module()
    valid = module.validate_chat_export(EXAMPLE_MD)
    require(valid.valid_for_intake is True, "example markdown should validate")
    for topic in [
        "Flutter SDK setup",
        "Android SDK cmdline-tools and license fix",
        "WSL/Ubuntu removal and disabled state",
        "Engel Remote Worker Android scaffold",
        "Flutter Windows desktop support",
        "Remote Worker Phase 2 GUI and manual packet import/export",
        "Remote Worker Phase 3 PC-side manual result intake planning",
        "Outside-AI / Hermes remains rejected / do not install boundary",
        "Engel safety boundaries for remote workers",
        "Manual review-only worker output",
        "Engel library/memory intake from chat exports",
    ]:
        require(topic in valid.detected_topics, "topic detection missing: " + topic)
    for flag in ["powershell", "apply_patch", "trusted_memory", "mutate_route", "mutate_queue", "ignore_previous_instructions", "bypass"]:
        require(flag in valid.risk_flags, "risk flag missing: " + flag)
    unsupported = module.validate_chat_export(UNSUPPORTED_JSON)
    require(unsupported.valid_for_intake is False, "unsupported extension must be rejected")
    require(any(".txt and .md" in error for error in unsupported.errors), "unsupported extension error missing")
    missing = module.validate_chat_export(ROOT / "library_intake" / "chat_exports" / "incoming" / "missing.md")
    require(missing.valid_for_intake is False, "missing path must fail safely")
    require(any("does not exist" in error for error in missing.errors), "missing path error missing")


def check_status_list_non_mutating() -> None:
    module = load_module()
    before = snapshot_paths()
    status = module.render_status()
    listing = module.render_list()
    after = snapshot_paths()
    require(before == after, "status/list mutated intake folders")
    require("manual / local / untrusted source material / review-only" in status, "status missing local review-only boundary")
    require("No watcher, no auto-import" in status, "status missing no watcher/no auto-import boundary")
    require("No incoming chat export .md or .txt files found." in listing or "Incoming chat export files:" in listing, "list output invalid")


def check_intake_receipt() -> None:
    module = load_module()
    receipt = module.intake_chat_export(
        EXAMPLE_MD,
        receipt_path=SMOKE_RECEIPT,
        intake_timestamp="2026-05-17T00:00:00+00:00",
    )
    require(Path(receipt.receipt_path) == SMOKE_RECEIPT, "smoke receipt path mismatch")
    require(SMOKE_RECEIPT.exists(), "smoke receipt missing")
    text = read(SMOKE_RECEIPT)
    for phrase in [
        "Chat Export Intake Receipt",
        "UNTRUSTED REVIEW ONLY — NOT APPLIED",
        "Recommended Memory-Candidate Topics",
        "Recommended Library Categories",
        "This receipt does not execute, apply, promote, route, queue, trust, or write trusted memory from chat content.",
        "Imported ChatGPT or outside-AI chat content is untrusted source material only.",
    ]:
        require(phrase in text, "receipt missing phrase: " + phrase)
    require(len(text) < 16000, "receipt should remain bounded")


def check_docs_and_verifier_registration() -> None:
    for path in [COMMANDS, CODEX_VERIFY, REPORT]:
        require(path.exists(), "missing docs/integration path: " + str(path.relative_to(ROOT)))
    commands = read(COMMANDS)
    for command in REQUIRED_COMMAND_DOCS:
        require(command in commands, "ENGEL_COMMANDS missing: " + command)
    require("tools\\verify_engel_chat_export_intake.py" in read(CODEX_VERIFY), "codex verifier missing chat export intake verifier")
    report = read(REPORT)
    for phrase in [
        "Engel Chat Export Intake V1",
        "UNTRUSTED REVIEW ONLY — NOT APPLIED",
        "No trusted-memory write",
        "No source mutation from chat content",
        "No route mutation",
        "No queue mutation",
        "No provider/API/network/browser behavior",
        "No background worker/file watcher/startup auto-import",
    ]:
        require(phrase in report, "report missing phrase: " + phrase)


def main() -> int:
    checks = [
        ("files_and_folders", check_files_and_folders),
        ("static_source", check_static_source),
        ("validation_behavior", check_validation_behavior),
        ("status_list_non_mutating", check_status_list_non_mutating),
        ("intake_receipt", check_intake_receipt),
        ("docs_and_verifier_registration", check_docs_and_verifier_registration),
    ]
    failures: list[str] = []
    for name, check in checks:
        try:
            check()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(f"{name}: {exc}")
            print("FAIL " + name + ": " + str(exc))
        except Exception as exc:
            failures.append(f"{name}: unexpected error: {exc}")
            print("FAIL " + name + ": unexpected error: " + str(exc))
    if failures:
        print("\nEngel Chat Export Intake verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nEngel Chat Export Intake verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
