#!/usr/bin/env python3
"""Verify the De Bruijn Quantum approved build command V1 route is protected and bounded.

Mode: static + import-level smoke. No password is entered by this verifier and no actual
build is run by the smoke cases.
"""
from __future__ import annotations

import ast
import importlib.util
import io
import contextlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_TEXT = r"D:\b.WorkSpace\Engel App"
ENGEL_APP = ROOT / "engel_app.py"
COMMAND_DOC = ROOT / "memory" / "ENGEL_COMMANDS.md"
ROUTE_METADATA = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
BUILD_PROMOTE_MODULE = ROOT / "engel_debruijn_quantum_build_promote.py"
CONTRACT_JSON = ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_COMMAND_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_COMMAND_CONTRACT_V1.md"
BUILD_RECEIPT_DIR = ROOT / "reports" / "debruijn_quantum_build_receipts"

PASS_MARKER = "DEBRUIJN_QUANTUM_APPROVED_BUILD_COMMAND_VERIFICATION_PASS"

APPROVAL_PHRASE = "APPROVE_DEBRUIJN_QUANTUM_GRAPH_BUILD_V1"
COMMAND_PREFIX = "engel ai debruijn quantum build"
DISABLED_REASON = "APPROVED_BUILD_EXECUTION_NOT_IMPLEMENTED"

REQUIRED_HANDLER = "debruijn_quantum_approved_build_command_v1"
REQUIRED_PARSE_HELPER = "_debruijn_quantum_approved_build_parse_args_v1"
REQUIRED_REJECT_HELPER = "_debruijn_quantum_approved_build_reject_v1"
REQUIRED_SAFETY_HELPER = "_debruijn_quantum_approved_build_safety_lines_v1"

REQUIRED_SAFETY_FLAGS = [
    "fail_closed_on_gate_failure: true",
    "approved_build_execution_enabled_now: true",
    "pyinstaller_enabled_now: true",
    "live_write_enabled_now: false",
    "dist_write_enabled_now: false",
    "backup_write_enabled_now: false",
    "promote_enabled_now: false",
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
    "--promote",
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
        self.review: list[str] = []

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

    def review_required(self, msg: str) -> None:
        self.review.append(msg)
        self._emit("REVIEW_REQUIRED", msg)


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
    for helper in (REQUIRED_PARSE_HELPER, REQUIRED_REJECT_HELPER, REQUIRED_SAFETY_HELPER):
        if f"def {helper}" not in source:
            check.fail(f"helper {helper} missing from engel_app.py")
        else:
            check.pass_(f"helper {helper} defined")
    early_dispatch = f'debruijn_msg.startswith("{COMMAND_PREFIX}")'
    legacy_dispatch = f'msg.lower().startswith("{COMMAND_PREFIX}")'
    if early_dispatch not in source and legacy_dispatch not in source:
        check.fail("CLI dispatch for approved build command prefix is missing")
    elif early_dispatch not in source:
        check.fail("approved build command dispatch is not in the early De Bruijn fast path")
    else:
        check.pass_("CLI dispatch wires approved build command prefix to early De Bruijn fast path")

    dispatch_index = source.find(early_dispatch)
    prompt_guard_index = source.find("prompt_check = check_prompt_injection(msg)")
    human_mode_index = source.find("human_command_reply = handle_human_command_mode_cli(msg)")
    if (
        dispatch_index == -1
        or prompt_guard_index == -1
        or human_mode_index == -1
        or not (dispatch_index < prompt_guard_index < human_mode_index)
    ):
        check.fail("approved build command fast path must run before prompt guard and human-command routing")
    else:
        check.pass_("approved build command fast path runs before broader routing/LLM-adjacent command handling")
    if APPROVAL_PHRASE not in source:
        check.fail(f"approval phrase {APPROVAL_PHRASE} not present in engel_app.py")
    else:
        check.pass_("approval phrase constant present in engel_app.py")
    if DISABLED_REASON not in source:
        check.fail(f"disabled reason {DISABLED_REASON} not present in engel_app.py")
    else:
        check.pass_("disabled reason constant present in engel_app.py")
    return source


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def check_no_pyinstaller_or_git(check: Check, source: str) -> None:
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
        check.fail("allowed-pattern entry for approved build command missing")
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
        check.fail("route metadata entry for approved build command missing")
        return
    expected_safety = [
        "implemented_now",
        "fail_closed_on_gate_failure",
        "preflight_before_password",
        "password_gated_now",
        "fixed_script_allowlist_only",
        "pyinstaller_only_via_allowlisted_script",
        "actual_build_enabled_with_gate",
        "no_promote",
        "no_live_dist_backups_write",
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
    if entry.get("expected_behavior") != "APPROVED_BUILD_COMMAND_PROTECTED_APPROVED_GRAPH_BUILD_V1":
        check.fail("route metadata expected_behavior mismatch")
        return
    check.pass_("route metadata entry present with all protected build safety flags true")


def check_command_doc(check: Check) -> None:
    if not COMMAND_DOC.exists():
        check.fail(f"command doc missing: {COMMAND_DOC}")
        return
    text = COMMAND_DOC.read_text(encoding="utf-8", errors="ignore")
    if f"{COMMAND_PREFIX} {APPROVAL_PHRASE}" not in text:
        check.fail("approved build command not documented in ENGEL_COMMANDS.md")
        return
    check.pass_("approved build command documented in ENGEL_COMMANDS.md")


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
    inserted = False
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
        inserted = True
    spec = importlib.util.spec_from_file_location(
        "engel_app_verify_target_approved_build", ENGEL_APP
    )
    if spec is None or spec.loader is None:
        if inserted:
            sys.path.remove(root_str)
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
        ("engel ai debruijn quantum build", ["USAGE", DISABLED_REASON]),
        (
            f"engel ai debruijn quantum build WRONG_PHRASE candidate=foo.json",
            ["REJECTED", "exact approval phrase required"],
        ),
        (
            f"engel ai debruijn quantum build {APPROVAL_PHRASE} candidate=http://x",
            ["REJECTED", "external URL"],
        ),
        (
            f"engel ai debruijn quantum build {APPROVAL_PHRASE} candidate=../etc/x.json",
            ["REJECTED", "path traversal"],
        ),
        (
            f"engel ai debruijn quantum build {APPROVAL_PHRASE} candidate=foo.json --force",
            ["REJECTED", "forbidden flag"],
        ),
        (
            f"engel ai debruijn quantum build {APPROVAL_PHRASE} candidate=foo.json extra_token",
            ["REJECTED", "unknown extra argument"],
        ),
        (
            f"engel ai debruijn quantum build {APPROVAL_PHRASE} candidate=foo.json candidate=bar.json",
            ["REJECTED", "multiple candidate"],
        ),
        (
            f"engel ai debruijn quantum build {APPROVAL_PHRASE}",
            ["REJECTED", "candidate=<candidate_path>"],
        ),
    ]
    for cmd, needles in cases:
        out = handler(cmd)
        for needle in needles:
            if needle not in out:
                check.fail(f"smoke case {cmd!r} missing expected text {needle!r}")
                return
    check.pass_(f"handler smoke cases ({len(cases)}) all fail-closed with expected reasons")


def check_no_unexpected_build_artifacts(check: Check) -> None:
    for name in ("build", "dist", "live"):
        path = ROOT / name
        if path.exists() and any(path.iterdir() if path.is_dir() else []):
            check.info(f"existing {name}/ folder present (pre-existing, not verifier scope)")
    if BUILD_RECEIPT_DIR.exists():
        check.info(
            f"build receipt folder present: {BUILD_RECEIPT_DIR.name} (preflight-only evidence)"
        )


def main() -> int:
    check = Check()
    print("ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_COMMAND_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: static + import smoke; no password entry, no actual build, no provider/network/model, no git")
    if not check_workspace_root(check):
        return 1
    check_contract_files(check)
    source = check_engel_app_has_handler(check)
    if source is None:
        return 1
    check_no_pyinstaller_or_git(check, source)
    check_pattern_metadata(check, source)
    check_route_metadata(check)
    check_command_doc(check)
    check_forbidden_flags_constant(check, source)
    check_safety_strings(check, source)
    smoke_handler(check)
    check_no_unexpected_build_artifacts(check)
    if check.failures:
        print(f"FAIL approved build command verification failed with {len(check.failures)} issue(s)")
        return 1
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
