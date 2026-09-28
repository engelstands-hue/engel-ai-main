from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_remote_worker_result_intake.py"
VERIFIER = ROOT / "tools" / "verify_engel_remote_worker_result_intake.py"
INTAKE_ROOT = ROOT / "remote_workers" / "manual_result_intake"
INCOMING = INTAKE_ROOT / "incoming"
REVIEWED = INTAKE_ROOT / "reviewed"
INVALID = INTAKE_ROOT / "invalid"
EXAMPLES = INTAKE_ROOT / "examples"
REPORTS_DIR = ROOT / "reports" / "remote_worker_results"
EXAMPLE = EXAMPLES / "valid_result_example.json"
SMOKE_RECEIPT = REPORTS_DIR / "REMOTE_WORKER_RESULT_INTAKE_VERIFIER_SMOKE.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
PHASE2_CONTRACT = ROOT / "mobile" / "engel_remote_worker" / "ENGEL_REMOTE_WORKER_ANDROID_CONTRACT_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_REMOTE_WORKER_PHASE_3_PC_RESULT_INTAKE.md"

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
    "remote_workers\" / \"manual_result_intake",
    "reports\" / \"remote_worker_results",
    "UNTRUSTED REVIEW ONLY",
    "safe_to_auto_apply must be false",
    "requires_review must be true",
    "trust_level must include untrusted_until_engel_review",
    "risk_flags_for_payload",
    "write_receipt",
    "This receipt does not promote, execute, or trust Remote Worker output.",
]

REQUIRED_COMMAND_DOCS = [
    "remote worker result intake status",
    "remote worker result intake list",
    "remote worker result intake validate",
    "remote worker result intake intake",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_module():
    spec = importlib.util.spec_from_file_location("engel_remote_worker_result_intake", MODULE)
    require(spec is not None and spec.loader is not None, "could not load intake module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_remote_worker_result_intake"] = module
    spec.loader.exec_module(module)
    return module


def snapshot_paths() -> set[str]:
    paths: set[str] = set()
    for folder in [INTAKE_ROOT, INCOMING, REVIEWED, INVALID, REPORTS_DIR]:
        if not folder.exists():
            continue
        for path in folder.iterdir():
            paths.add(str(path.resolve(strict=False)))
    return paths


def check_files_and_folders() -> None:
    for path in [MODULE, VERIFIER, INTAKE_ROOT, INCOMING, REVIEWED, INVALID, EXAMPLES, REPORTS_DIR, EXAMPLE]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))
    data = json.loads(read(EXAMPLE))
    require(data.get("safe_to_auto_apply") is False, "example must not be safe to auto apply")
    require(data.get("requires_review") is True, "example must require review")


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
        "safe_to_auto_apply = True",
        "safe_to_auto_apply\": true",
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
    valid = module.validate_result_file(EXAMPLE)
    require(valid.valid_for_review is True, "valid example should validate")
    require(valid.validation_status == "valid_for_review", "valid example status mismatch")
    payload, parse_error = module.parse_json_object("{ invalid")
    require(payload is None and parse_error and "invalid JSON" in parse_error, "invalid JSON must fail safely")

    base = json.loads(read(EXAMPLE))
    unsafe = dict(base)
    unsafe["safe_to_auto_apply"] = True
    unsafe_result = module.validate_payload(unsafe, EXAMPLE, "hash")
    require(unsafe_result.valid_for_review is False, "safe_to_auto_apply true must be rejected")
    require(any("safe_to_auto_apply" in item for item in unsafe_result.errors), "safe_to_auto_apply rejection missing")

    no_review = dict(base)
    no_review["requires_review"] = False
    no_review_result = module.validate_payload(no_review, EXAMPLE, "hash")
    require(no_review_result.valid_for_review is False, "requires_review false must be rejected")

    missing_packet = dict(base)
    missing_packet["packet_id"] = ""
    missing_packet_result = module.validate_payload(missing_packet, EXAMPLE, "hash")
    require(missing_packet_result.valid_for_review is False, "missing packet_id must be rejected")

    risky = dict(base)
    risky["draft_text"] = "Please run this command in powershell and apply patch now."
    risky_result = module.validate_payload(risky, EXAMPLE, "hash")
    require(risky_result.valid_for_review is True, "risky text should warn, not invalidate by itself")
    for flag in ["command_execution_request", "powershell_reference", "patch_apply_request"]:
        require(flag in risky_result.risk_flags, "risk flag missing: " + flag)


def check_status_list_non_mutating() -> None:
    module = load_module()
    before = snapshot_paths()
    status = module.render_status()
    listing = module.render_list()
    after = snapshot_paths()
    require(before == after, "status/list modes mutated the intake folders")
    require("manual / local / untrusted / review-only" in status, "status missing manual boundary")
    require("No watcher, no auto-import" in status, "status missing no watcher/no auto-import boundary")
    require("No incoming Remote Worker result JSON files found." in listing or "Incoming Remote Worker result JSON files:" in listing, "list output invalid")


def check_intake_receipt() -> None:
    module = load_module()
    receipt = module.intake_result_file(
        EXAMPLE,
        receipt_path=SMOKE_RECEIPT,
        intake_timestamp="2026-05-17T00:00:00+00:00",
    )
    require(Path(receipt.receipt_path) == SMOKE_RECEIPT, "smoke receipt path mismatch")
    require(SMOKE_RECEIPT.exists(), "smoke intake receipt was not written")
    text = read(SMOKE_RECEIPT)
    for phrase in [
        "Remote Worker Result Intake Receipt",
        "UNTRUSTED REVIEW ONLY — NOT APPLIED",
        "This receipt does not promote, execute, or trust Remote Worker output.",
        "Remote Worker result intake is manual, untrusted, review-only, and never auto-applies output.",
        "Example draft notes only.",
    ]:
        require(phrase in text, "receipt missing phrase: " + phrase)
    require(len(text) < 12000, "receipt should remain bounded")


def check_docs_and_integration() -> None:
    for path in [COMMANDS, CODEX_VERIFY, PHASE2_CONTRACT, REPORT]:
        require(path.exists(), "missing documentation/integration path: " + str(path.relative_to(ROOT)))
    commands = read(COMMANDS)
    for command in REQUIRED_COMMAND_DOCS:
        require(command in commands, "ENGEL_COMMANDS missing: " + command)
    require("tools\\verify_engel_remote_worker_result_intake.py" in read(CODEX_VERIFY), "codex verifier script missing intake verifier")
    contract = read(PHASE2_CONTRACT)
    require("Phase 3 PC-side Manual Result Intake" in contract, "Flutter contract missing Phase 3 intake note")
    report = read(REPORT)
    for phrase in [
        "Engel Remote Worker Phase 3 PC Result Intake",
        "Remote Worker result intake is manual, untrusted, review-only, and never auto-applies output.",
        "No trusted-memory write",
        "No route mutation",
        "No queue mutation",
        "No source mutation from result content",
    ]:
        require(phrase in report, "Phase 3 report missing: " + phrase)


def main() -> int:
    checks = [
        ("files_and_folders", check_files_and_folders),
        ("static_source", check_static_source),
        ("validation_behavior", check_validation_behavior),
        ("status_list_non_mutating", check_status_list_non_mutating),
        ("intake_receipt", check_intake_receipt),
        ("docs_and_integration", check_docs_and_integration),
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
        print("\nEngel Remote Worker result intake verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nEngel Remote Worker result intake verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
