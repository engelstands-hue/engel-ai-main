#!/usr/bin/env python3
"""Verify ENGEL_DEBRUIJN_LANE_TRAVERSAL_CLASSIFIER_CONTRACT_V1 and the classifier module.

Mode: static + import-level smoke. No subprocess, no network, no provider/model,
no source/route/queue/trusted-memory mutation, no apply/build/promote/stage/commit.
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

CONTRACT_ID = "ENGEL_DEBRUIJN_LANE_TRAVERSAL_CLASSIFIER_CONTRACT_V1"
CONTRACT_JSON = ROOT / "memory" / f"{CONTRACT_ID}.json"
CONTRACT_MD = ROOT / "memory" / f"{CONTRACT_ID}.md"
MODULE_PATH = ROOT / "engel_debruijn_lane_traversal_classifier.py"

PASS_MARKER = "ENGEL_DEBRUIJN_LANE_TRAVERSAL_CLASSIFIER_VERIFICATION_PASS"

REQUIRED_FUNCTIONS = ["classify_lane_transition", "classifier_status_payload", "main"]
REQUIRED_CLASSES = ["LaneTransitionResult"]

REQUIRED_RESULT_FIELDS = [
    "classifier_id",
    "classifier_contract_id",
    "graph_sequence_model_contract_id",
    "window_size",
    "window",
    "next_letter",
    "next_status",
    "transition_edge_label",
    "transition_classification",
    "overlap_preserved",
    "edge_present_in_alphabet",
    "forbidden_absorbing_pattern_detected",
    "forbidden_pattern_reason",
    "superposition_amplitudes",
    "interference_dominant_letter",
    "review_recommended",
    "notes",
]

FORBIDDEN_IMPORT_ROOTS = {
    "subprocess",
    "socket",
    "urllib",
    "requests",
    "http",
    "ftplib",
    "smtplib",
    "openai",
    "anthropic",
    "llama_cpp",
    "torch",
    "tensorflow",
}

FORBIDDEN_CALLS = {"eval", "exec", "compile", "os.system", "os.popen"}


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


def check_workspace(check: Check) -> bool:
    if ROOT.resolve(strict=False) != Path(WORKSPACE_TEXT).resolve(strict=False):
        check.fail(f"verifier must run inside {WORKSPACE_TEXT}; got {ROOT}")
        return False
    check.pass_(f"workspace root matches {WORKSPACE_TEXT}")
    return True


def check_files(check: Check) -> tuple[dict[str, Any], str] | None:
    for path in (CONTRACT_JSON, CONTRACT_MD, MODULE_PATH):
        if not path.exists():
            check.fail(f"required file missing: {path}")
            return None
    check.pass_("contract JSON, contract MD, and classifier module are all present")
    try:
        data = json.loads(CONTRACT_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        check.fail(f"contract JSON parse failed: {exc}")
        return None
    if not isinstance(data, dict):
        check.fail("contract JSON top-level value must be an object")
        return None
    source = MODULE_PATH.read_text(encoding="utf-8")
    return data, source


def check_contract_identity(check: Check, data: dict[str, Any]) -> None:
    if data.get("contract_id") != CONTRACT_ID:
        check.fail(f"contract_id mismatch: {data.get('contract_id')}")
        return
    if data.get("active_workspace") != WORKSPACE_TEXT:
        check.fail("active_workspace mismatch")
        return
    if data.get("classifier_id") != "engel_debruijn_lane_traversal_classifier_v1":
        check.fail("classifier_id mismatch")
        return
    alphabet = data.get("lane_wing_alphabet")
    if alphabet != ["P", "B", "S"]:
        check.fail(f"lane_wing_alphabet must be [P, B, S]; got {alphabet}")
        return
    if data.get("default_window_size") != 3:
        check.fail("default_window_size must be 3")
        return
    if data.get("graph_sequence_model_contract_id") != "ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_V1":
        check.fail("graph_sequence_model_contract_id must reference ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_V1")
        return
    check.pass_("contract declares lane wing alphabet {P,B,S} with default window size 3, referencing graph sequence model V1")


def check_required_result_fields(check: Check, data: dict[str, Any]) -> None:
    fields = data.get("required_result_fields")
    if not isinstance(fields, list):
        check.fail("required_result_fields must be a list")
        return
    missing = [f for f in REQUIRED_RESULT_FIELDS if f not in fields]
    if missing:
        check.fail(f"required_result_fields missing: {missing}")
        return
    check.pass_("contract declares all required result fields")


def check_module_ast(check: Check, source: str) -> None:
    try:
        tree = ast.parse(source, filename=str(MODULE_PATH))
    except SyntaxError as exc:
        check.fail(f"classifier module syntax error: {exc}")
        return
    classes = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    functions = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    for name in REQUIRED_CLASSES:
        if name not in classes:
            check.fail(f"classifier module missing class: {name}")
            return
    for name in REQUIRED_FUNCTIONS:
        if name not in functions:
            check.fail(f"classifier module missing function: {name}")
            return
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    check.fail(f"classifier module has forbidden import: {alias.name}")
                    return
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in FORBIDDEN_IMPORT_ROOTS:
                check.fail(f"classifier module has forbidden import: {node.module}")
                return
        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in FORBIDDEN_CALLS:
                check.fail(f"classifier module calls forbidden function: {name}")
                return
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    check.fail("classifier module passes shell=True somewhere")
                    return
    check.pass_("classifier module AST: required classes + functions present; no forbidden imports / calls / shell=True")


def _import_module() -> tuple[Any | None, str | None]:
    spec = importlib.util.spec_from_file_location("engel_debruijn_lane_traversal_classifier_verify_target", MODULE_PATH)
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


def smoke(check: Check) -> None:
    module, err = _import_module()
    if module is None:
        check.fail(f"could not import classifier module ({err})")
        return
    check.pass_("classifier module imports without side effects")
    payload = module.classifier_status_payload()
    if not isinstance(payload, dict):
        check.fail("classifier_status_payload must return a dict")
        return
    if payload.get("classifier_id") != "engel_debruijn_lane_traversal_classifier_v1":
        check.fail("classifier_status_payload classifier_id mismatch")
        return
    if payload.get("default_window_size") != 3:
        check.fail("default_window_size must be 3")
        return
    if payload.get("edge_alphabet_size_for_default_window") != 81:
        check.fail("edge alphabet for K=3 over {P,B,S} must have 3^4 = 81 edges")
        return
    check.pass_("classifier_status_payload reports correct identity, window size 3, and 81-edge alphabet")

    scenarios = [
        {
            "name": "pass-pass-pass -> pass",
            "kwargs": dict(
                recent_statuses=[
                    "BUILD_LANE_PASS_REVIEW_REQUIRED",
                    "BUILD_LANE_PASS_REVIEW_REQUIRED",
                    "BUILD_LANE_PASS_REVIEW_REQUIRED",
                ],
                next_status="BUILD_LANE_PASS_REVIEW_REQUIRED",
            ),
            "expected_classification": "pass_basin_transition",
            "expected_review_recommended": False,
            "expected_forbidden_absorbing": False,
        },
        {
            "name": "blocked-blocked-blocked -> pass (forbidden absorbing)",
            "kwargs": dict(
                recent_statuses=[
                    "BUILD_LANE_BLOCKED_SCRIPT_MISSING",
                    "BUILD_LANE_BLOCKED_SCRIPT_MISSING",
                    "BUILD_LANE_BLOCKED_SCRIPT_MISSING",
                ],
                next_status="BUILD_LANE_PASS_REVIEW_REQUIRED",
            ),
            "expected_classification": "forbidden_absorbing_transition",
            "expected_review_recommended": True,
            "expected_forbidden_absorbing": True,
        },
        {
            "name": "pass-saddle-blocked -> pass (normal)",
            "kwargs": dict(
                recent_statuses=[
                    "BUILD_LANE_PASS_REVIEW_REQUIRED",
                    "BUILD_LANE_TIMEOUT_BOUNDED_REVIEW_REQUIRED",
                    "BUILD_LANE_BLOCKED_SCRIPT_MISSING",
                ],
                next_status="BUILD_LANE_PASS_REVIEW_REQUIRED",
            ),
            "expected_classification": "pass_basin_transition",
            "expected_review_recommended": False,
            "expected_forbidden_absorbing": False,
        },
        {
            "name": "pass-pass-pass -> saddle (forces review)",
            "kwargs": dict(
                recent_statuses=[
                    "BUILD_LANE_PASS_REVIEW_REQUIRED",
                    "BUILD_LANE_PASS_REVIEW_REQUIRED",
                    "BUILD_LANE_PASS_REVIEW_REQUIRED",
                ],
                next_status="BUILD_LANE_LIVE_SMOKE_FAIL_REVIEW_REQUIRED",
            ),
            "expected_classification": "saddle_review_transition",
            "expected_review_recommended": True,
            "expected_forbidden_absorbing": False,
        },
        {
            "name": "off-attractor unknown status",
            "kwargs": dict(
                recent_statuses=[
                    "BUILD_LANE_PASS_REVIEW_REQUIRED",
                    "BUILD_LANE_PASS_REVIEW_REQUIRED",
                    "BUILD_LANE_PASS_REVIEW_REQUIRED",
                ],
                next_status="SOME_UNMODELED_STATUS_THAT_IS_NOT_IN_TOKEN_LISTS",
            ),
            "expected_classification": "off_attractor_unclassified",
            "expected_review_recommended": True,
            "expected_forbidden_absorbing": False,
        },
    ]
    for scenario in scenarios:
        result = module.classify_lane_transition(**scenario["kwargs"])
        result_dict = result.__dict__ if hasattr(result, "__dict__") else result
        for field in REQUIRED_RESULT_FIELDS:
            if field not in result_dict:
                check.fail(f"{scenario['name']} scenario: result missing field {field}")
                return
        if result.transition_classification != scenario["expected_classification"]:
            check.fail(
                f"{scenario['name']} scenario: expected classification {scenario['expected_classification']!r}, "
                f"got {result.transition_classification!r}"
            )
            return
        if result.review_recommended is not scenario["expected_review_recommended"]:
            check.fail(
                f"{scenario['name']} scenario: expected review_recommended"
                f"={scenario['expected_review_recommended']}, got {result.review_recommended}"
            )
            return
        if result.forbidden_absorbing_pattern_detected is not scenario["expected_forbidden_absorbing"]:
            check.fail(
                f"{scenario['name']} scenario: expected forbidden_absorbing"
                f"={scenario['expected_forbidden_absorbing']}, got {result.forbidden_absorbing_pattern_detected}"
            )
            return
        amps = result.superposition_amplitudes
        if not isinstance(amps, dict) or set(amps.keys()) != {"P", "B", "S"}:
            check.fail(f"{scenario['name']} scenario: superposition_amplitudes must be a dict keyed by P/B/S")
            return
        sumsq = sum(a * a for a in amps.values())
        if abs(sumsq - 1.0) > 1e-9:
            check.fail(f"{scenario['name']} scenario: superposition amplitudes are not unit-normalized; sum of squares = {sumsq}")
            return
    check.pass_("classifier smoke: 5 representative scenarios produce expected classifications and unit-normalized amplitudes")

    # Determinism check
    a = module.classify_lane_transition(**scenarios[1]["kwargs"])
    b = module.classify_lane_transition(**scenarios[1]["kwargs"])
    if a.transition_classification != b.transition_classification:
        check.fail("classifier not deterministic across two identical calls (classification)")
        return
    if a.transition_edge_label != b.transition_edge_label:
        check.fail("classifier not deterministic across two identical calls (edge label)")
        return
    check.pass_("classifier is deterministic across repeated calls with identical inputs")


def main() -> int:
    check = Check()
    print("ENGEL_DEBRUIJN_LANE_TRAVERSAL_CLASSIFIER_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: static + import smoke; no subprocess, no network, no provider/model, no mutations.")
    if not check_workspace(check):
        return 1
    bundle = check_files(check)
    if bundle is None:
        return 1
    data, source = bundle
    check_contract_identity(check, data)
    check_required_result_fields(check, data)
    check_module_ast(check, source)
    smoke(check)
    if check.failures:
        print(f"FAIL De Bruijn lane traversal classifier verification failed with {len(check.failures)} issue(s)")
        return 1
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
