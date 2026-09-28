#!/usr/bin/env python3
"""Verify the De Bruijn Quantum approved promote command V1 route is protected and bounded.

Mode: static + import-level negative smoke. The verifier never enters a password and
never performs an actual promote; it validates fail-closed parsing and protected route
boundaries.
"""
from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_TEXT = r"D:\b.WorkSpace\Engel App"
ENGEL_APP = ROOT / "engel_app.py"
COMMAND_DOC = ROOT / "memory" / "ENGEL_COMMANDS.md"
ROUTE_METADATA = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
CONTRACT_JSON = ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_COMMAND_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_COMMAND_CONTRACT_V1.md"
PROMOTE_RECEIPT_DIR = ROOT / "reports" / "debruijn_quantum_promote_receipts"

PASS_MARKER = "DEBRUIJN_QUANTUM_APPROVED_PROMOTE_COMMAND_VERIFICATION_PASS"

APPROVAL_PHRASE = "APPROVE_DEBRUIJN_QUANTUM_GRAPH_PROMOTE_V1"
COMMAND_PREFIX = "engel ai debruijn quantum promote"
DISABLED_REASON = "PROMOTE_EXECUTION_NOT_IMPLEMENTED"

REQUIRED_HANDLER = "debruijn_quantum_approved_promote_command_v1"
REQUIRED_HELPERS = (
    "_debruijn_quantum_approved_promote_parse_args_v1",
    "_debruijn_quantum_approved_promote_reject_v1",
    "_debruijn_quantum_approved_promote_safety_lines_v1",
)

REQUIRED_SAFETY_FLAGS = [
    "fail_closed_on_gate_failure: true",
    "approved_promote_command_enabled_now: true",
    "actual_promote_enabled_now: true",
    "live_write_enabled_now: true",
    "dist_write_enabled_now: false",
    "backup_write_enabled_now: true",
    "build_execution_enabled_now: false",
    "pyinstaller_enabled_now: false",
    "git_stage_commit_enabled_now: false",
    "source_mutation_enabled_now: false",
    "route_mutation_enabled_now: false",
    "queue_mutation_enabled_now: false",
    "trusted_memory_write_enabled_now: false",
    "memory_promotion_enabled_now: false",
    "provider_api_enabled_now: false",
    "network_enabled_now: false",
    "local_llm_inference_enabled_now: false",
    "background_worker_enabled_now: false",
    "autorun_enabled_now: false",
    "scheduler_enabled_now: false",
    "startup_hook_enabled_now: false",
    "human_review_required: true",
]

REQUIRED_FORBIDDEN_FLAGS = [
    "--force",
    "--no-verify",
    "--no-password",
    "--no-gate",
    "--script",
    "--cmd",
    "--command",
    "--exec",
    "--shell",
    "--output",
    "--out",
    "--dest",
    "--destination",
    "--target",
    "--live",
    "--backup",
    "--build",
    "--provider",
    "--api-key",
    "--model",
    "--network",
    "--internet",
    "--url",
    "--allow-shell",
    "password=",
    "salt=",
    "hash=",
    "token=",
    "secret=",
]

FORBIDDEN_HANDLER_CALL_NAMES = {
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "os.system",
    "os.popen",
    "eval",
    "exec",
    "compile",
}

FORBIDDEN_HANDLER_LITERALS = [
    "shell=true",
    "git add",
    "git commit",
    "git push",
    "git stage",
    "PyInstaller.__main__",
    "from PyInstaller",
    "import PyInstaller",
    "pyinstaller.exe",
]


class Check:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def _emit(self, level: str, msg: str) -> None:
        safe = msg.encode("ascii", "backslashreplace").decode("ascii")
        print(f"{level} {safe}", flush=True)

    def pass_(self, msg: str) -> None:
        self._emit("PASS", msg)

    def info(self, msg: str) -> None:
        self._emit("INFO", msg)

    def fail(self, msg: str) -> None:
        self.failures.append(msg)
        self._emit("FAIL", msg)


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def check_workspace_root(check: Check) -> bool:
    if ROOT.resolve(strict=False) != Path(WORKSPACE_TEXT).resolve(strict=False):
        check.fail(f"verifier must run inside {WORKSPACE_TEXT}; got {ROOT}")
        return False
    check.pass_(f"workspace root matches {WORKSPACE_TEXT}")
    return True


def check_contract_files(check: Check) -> None:
    for path in (CONTRACT_JSON, CONTRACT_MD):
        if not path.exists():
            check.fail(f"contract file missing: {path}")
        else:
            check.pass_(f"contract file present: {path.name}")


def check_engel_app_has_handler(check: Check) -> str | None:
    if not ENGEL_APP.exists():
        check.fail("engel_app.py missing")
        return None
    source = ENGEL_APP.read_text(encoding="utf-8", errors="ignore")
    if f"def {REQUIRED_HANDLER}" not in source:
        check.fail(f"handler {REQUIRED_HANDLER} not defined in engel_app.py")
        return None
    check.pass_(f"handler {REQUIRED_HANDLER} defined in engel_app.py")
    for helper in REQUIRED_HELPERS:
        if f"def {helper}" not in source:
            check.fail(f"helper {helper} missing from engel_app.py")
        else:
            check.pass_(f"helper {helper} defined")
    if f'msg.lower().startswith("{COMMAND_PREFIX}")' not in source:
        check.fail("CLI dispatch for approved promote command prefix is missing")
    else:
        check.pass_("CLI dispatch wires approved promote command prefix to handler")
    if APPROVAL_PHRASE not in source:
        check.fail(f"approval phrase {APPROVAL_PHRASE} not present in engel_app.py")
    else:
        check.pass_("approval phrase constant present in engel_app.py")
    if DISABLED_REASON not in source:
        check.fail(f"disabled reason {DISABLED_REASON} not present in engel_app.py")
    else:
        check.pass_("disabled reason constant present in engel_app.py")
    return source


def check_no_forbidden_calls(check: Check, source: str) -> None:
    try:
        tree = ast.parse(source, filename=str(ENGEL_APP))
    except SyntaxError as exc:
        check.fail(f"engel_app.py syntax error: {exc}")
        return
    handler_func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == REQUIRED_HANDLER:
            handler_func = node
            break
    if handler_func is None:
        check.fail(f"handler function {REQUIRED_HANDLER} not found in AST")
        return
    bad_calls: list[str] = []
    for child in ast.walk(handler_func):
        if isinstance(child, ast.Call):
            name = _call_name(child.func)
            if name in FORBIDDEN_HANDLER_CALL_NAMES:
                bad_calls.append(name)
            for kw in child.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    bad_calls.append("shell=True kwarg")
    if bad_calls:
        check.fail(f"handler contains forbidden calls: {sorted(set(bad_calls))}")
        return
    start = source.index(f"def {REQUIRED_HANDLER}")
    end = source.find("\ndef ", start + 1)
    handler_block = source[start:end] if end != -1 else source[start:]
    lowered = handler_block.lower()
    for literal in FORBIDDEN_HANDLER_LITERALS:
        if literal.lower() in lowered:
            check.fail(f"handler contains forbidden literal {literal!r}")
            return
    check.pass_("handler body contains no subprocess/PyInstaller/git/shell calls")


def check_pattern_metadata(check: Check, source: str) -> None:
    needle = f'"pattern": "{COMMAND_PREFIX}", "match": "prefix"'
    if needle not in source:
        check.fail("allowed-pattern entry for approved promote command missing")
    else:
        check.pass_("allowed-pattern entry present")


def check_route_metadata(check: Check) -> None:
    if not ROUTE_METADATA.exists():
        check.fail(f"route metadata missing: {ROUTE_METADATA}")
        return
    data = json.loads(ROUTE_METADATA.read_text(encoding="utf-8"))
    entries = data.get("route_regression_matrix_entries", [])
    entry = next((e for e in entries if e.get("command") == COMMAND_PREFIX), None)
    if entry is None:
        check.fail("route metadata entry for approved promote command missing")
        return
    expected_safety = [
        "implemented_now",
        "fail_closed_on_gate_failure",
        "password_gated_now",
        "no_pyinstaller",
        "no_actual_build",
        "no_git_stage_commit",
        "no_source_mutation",
        "no_route_mutation",
        "no_queue_mutation",
        "no_trusted_memory_write",
        "no_memory_promotion",
        "no_apply",
        "no_candidate_execution",
        "no_provider_network_model_real_quantum",
        "no_background_autorun_scheduler",
    ]
    for key in expected_safety:
        if entry.get(key) is not True:
            check.fail(f"route metadata entry missing/false flag {key}")
            return
    if entry.get("expected_behavior") != "APPROVED_PROMOTE_COMMAND_PROTECTED_LIVE_PROMOTE_V1":
        check.fail("route metadata expected_behavior mismatch")
        return
    check.pass_("route metadata entry present with all safety flags true")


def check_command_doc(check: Check) -> None:
    if not COMMAND_DOC.exists():
        check.fail(f"command doc missing: {COMMAND_DOC}")
        return
    text = COMMAND_DOC.read_text(encoding="utf-8", errors="ignore")
    if f"{COMMAND_PREFIX} {APPROVAL_PHRASE}" not in text:
        check.fail("approved promote command not documented in ENGEL_COMMANDS.md")
        return
    check.pass_("approved promote command documented in ENGEL_COMMANDS.md")


def check_forbidden_flags_constant(check: Check, source: str) -> None:
    for flag in REQUIRED_FORBIDDEN_FLAGS:
        if flag not in source:
            check.fail(f"forbidden flag {flag!r} not listed in engel_app.py forbidden constant")
            return
    check.pass_("forbidden flag/secret arg constants all present")


def check_safety_strings(check: Check, source: str) -> None:
    for needle in REQUIRED_SAFETY_FLAGS:
        if needle not in source:
            check.fail(f"safety flag string missing in engel_app.py: {needle}")
            return
    check.pass_("required safety flag strings all present")


def _import_engel_app() -> tuple[Any | None, str | None]:
    root_str = str(ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    spec = importlib.util.spec_from_file_location(
        "engel_app_verify_target_approved_promote", ENGEL_APP
    )
    if spec is None or spec.loader is None:
        return None, "import spec build failed"
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[spec.name] = module
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            spec.loader.exec_module(module)
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    return module, None


def smoke_handler(check: Check) -> None:
    module, err = _import_engel_app()
    if module is None:
        check.fail(f"could not import engel_app module for smoke ({err})")
        return
    handler = getattr(module, REQUIRED_HANDLER, None)
    if handler is None:
        check.fail(f"engel_app does not expose {REQUIRED_HANDLER}")
        return
    check.pass_("engel_app module imports and exposes handler")

    cases = [
        ("engel ai debruijn quantum promote", ["USAGE", DISABLED_REASON]),
        (
            "engel ai debruijn quantum promote WRONG_PHRASE build_receipt=foo.json",
            ["REJECTED", "exact approval phrase required"],
        ),
        (
            f"engel ai debruijn quantum promote {APPROVAL_PHRASE} build_receipt=http://x",
            ["REJECTED", "external URL"],
        ),
        (
            f"engel ai debruijn quantum promote {APPROVAL_PHRASE} build_receipt=../etc/x.json",
            ["REJECTED", "path traversal"],
        ),
        (
            f"engel ai debruijn quantum promote {APPROVAL_PHRASE} build_receipt=foo.json --force",
            ["REJECTED", "forbidden flag"],
        ),
        (
            f"engel ai debruijn quantum promote {APPROVAL_PHRASE} build_receipt=foo.json --backup=evil",
            ["REJECTED", "forbidden flag"],
        ),
        (
            f"engel ai debruijn quantum promote {APPROVAL_PHRASE} build_receipt=foo.json extra_token",
            ["REJECTED", "unknown extra argument"],
        ),
        (
            f"engel ai debruijn quantum promote {APPROVAL_PHRASE} build_receipt=foo.json build_receipt=bar.json",
            ["REJECTED", "multiple build_receipt"],
        ),
        (
            f"engel ai debruijn quantum promote {APPROVAL_PHRASE}",
            ["REJECTED", "build_receipt=<receipt_path>"],
        ),
    ]
    for cmd, needles in cases:
        out = handler(cmd)
        for needle in needles:
            if needle not in out:
                check.fail(f"smoke case {cmd!r} missing expected text {needle!r}")
                return
    check.pass_(f"handler smoke cases ({len(cases)}) all fail-closed with expected reasons")


def main() -> int:
    check = Check()
    print("ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_COMMAND_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: static + import smoke; no shell, no promote, no PyInstaller, no provider/network/model, no git")
    if not check_workspace_root(check):
        return 1
    check_contract_files(check)
    source = check_engel_app_has_handler(check)
    if source is None:
        return 1
    check_no_forbidden_calls(check, source)
    check_pattern_metadata(check, source)
    check_route_metadata(check)
    check_command_doc(check)
    check_forbidden_flags_constant(check, source)
    check_safety_strings(check, source)
    smoke_handler(check)
    if PROMOTE_RECEIPT_DIR.exists():
        check.info(f"promote receipt folder present: {PROMOTE_RECEIPT_DIR.name} (preflight-only evidence)")
    if check.failures:
        print(f"FAIL approved promote command verification failed with {len(check.failures)} issue(s)")
        return 1
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
