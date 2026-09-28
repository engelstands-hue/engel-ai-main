#!/usr/bin/env python3
"""Verify ENGEL_LORENZ_ATTRACTOR_LANE_CLASSIFIER_CONTRACT_V1 and the classifier module.

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

CONTRACT_ID = "ENGEL_LORENZ_ATTRACTOR_LANE_CLASSIFIER_CONTRACT_V1"
CONTRACT_JSON = ROOT / "memory" / f"{CONTRACT_ID}.json"
CONTRACT_MD = ROOT / "memory" / f"{CONTRACT_ID}.md"
MODULE_PATH = ROOT / "engel_lorenz_attractor_lane_classifier.py"

PASS_MARKER = "ENGEL_LORENZ_ATTRACTOR_LANE_CLASSIFIER_VERIFICATION_PASS"

EXPECTED_PARAMS = {
    "SIGMA": 10.0,
    "RHO": 28.0,
    "BETA": 8.0 / 3.0,
}

REQUIRED_FUNCTIONS = ["classify_lane_trajectory", "classifier_status_payload", "main"]
REQUIRED_CLASSES = ["LorenzClassificationResult"]

REQUIRED_RESULT_FIELDS = [
    "classifier_id",
    "classifier_contract_id",
    "lane_id",
    "final_status",
    "sigma",
    "rho",
    "beta",
    "dt",
    "warmup_steps",
    "trajectory_steps",
    "initial_state",
    "final_state",
    "wing_classification",
    "bounded_attractor_invariant_ok",
    "sensitivity_indicator",
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
    if data.get("classifier_id") != "engel_lorenz_attractor_lane_classifier_v1":
        check.fail("classifier_id mismatch")
        return
    params = data.get("lorenz_parameters")
    if not isinstance(params, dict):
        check.fail("lorenz_parameters must be an object")
        return
    if params.get("sigma") != 10.0 or params.get("rho") != 28.0:
        check.fail("lorenz_parameters sigma/rho must be classic chaotic values 10.0 / 28.0")
        return
    beta = params.get("beta")
    if not isinstance(beta, (int, float)) or abs(beta - 8.0 / 3.0) > 1e-9:
        check.fail("lorenz_parameters beta must be 8/3")
        return
    check.pass_("contract declares classic Lorenz parameters sigma=10, rho=28, beta=8/3")


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


def check_required_constants_in_source(check: Check, source: str) -> None:
    for name, value in EXPECTED_PARAMS.items():
        needle = f"{name} = "
        if needle not in source:
            check.fail(f"classifier module missing constant declaration: {needle}")
            return
    if "SIGMA = 10.0" not in source:
        check.fail("SIGMA must equal 10.0 in classifier module")
        return
    if "RHO = 28.0" not in source:
        check.fail("RHO must equal 28.0 in classifier module")
        return
    if "BETA = 8.0 / 3.0" not in source:
        check.fail("BETA must equal 8.0 / 3.0 in classifier module")
        return
    check.pass_("classifier module declares Lorenz constants with classic values")


def _import_module() -> tuple[Any | None, str | None]:
    spec = importlib.util.spec_from_file_location("engel_lorenz_attractor_lane_classifier_verify_target", MODULE_PATH)
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
    if payload.get("classifier_id") != "engel_lorenz_attractor_lane_classifier_v1":
        check.fail("classifier_status_payload classifier_id mismatch")
        return
    check.pass_("classifier_status_payload reports correct classifier_id")

    scenarios = [
        {
            "name": "pass basin",
            "kwargs": dict(
                lane_id="approved_graph_build",
                final_status="BUILD_LANE_PASS_REVIEW_REQUIRED",
                candidate_hash="a1b2c3d4",
                edge_label="0001:src->tgt",
                pre_verifier_pass_count=8,
                pre_verifier_total=8,
            ),
            "expected_wing": "left_wing_pass_basin",
            "expected_review_recommended": False,
        },
        {
            "name": "blocked basin",
            "kwargs": dict(
                lane_id="approved_graph_build",
                final_status="BUILD_LANE_BLOCKED_SCRIPT_MISSING",
                candidate_hash="deadbeef",
                edge_label="0010:foo->bar",
                pre_verifier_pass_count=6,
                pre_verifier_total=8,
            ),
            "expected_wing": "right_wing_blocked_basin",
            "expected_review_recommended": False,
        },
        {
            "name": "saddle",
            "kwargs": dict(
                lane_id="approved_graph_promote",
                final_status="PROMOTE_LANE_LIVE_SMOKE_FAIL_REVIEW_REQUIRED",
                candidate_hash="00112233",
                edge_label="0011:wing->saddle",
                pre_verifier_pass_count=7,
                pre_verifier_total=8,
            ),
            "expected_wing": "saddle_review_required_transition",
            "expected_review_recommended": True,
        },
    ]
    for scenario in scenarios:
        result = module.classify_lane_trajectory(**scenario["kwargs"])
        result_dict = result.__dict__ if hasattr(result, "__dict__") else result
        for field in REQUIRED_RESULT_FIELDS:
            if field not in result_dict:
                check.fail(f"{scenario['name']} scenario: result missing field {field}")
                return
        if result.wing_classification != scenario["expected_wing"]:
            check.fail(
                f"{scenario['name']} scenario: expected wing {scenario['expected_wing']!r}, "
                f"got {result.wing_classification!r}"
            )
            return
        if result.review_recommended is not scenario["expected_review_recommended"]:
            check.fail(
                f"{scenario['name']} scenario: expected review_recommended"
                f"={scenario['expected_review_recommended']}, got {result.review_recommended}"
            )
            return
        if result.bounded_attractor_invariant_ok is not True:
            check.fail(f"{scenario['name']} scenario: trajectory left the bounded envelope")
            return
    check.pass_("classifier smoke: pass / blocked / saddle scenarios produce expected wing + review advice + bounded trajectories")

    # Determinism: identical inputs produce identical wing + sensitivity
    a = module.classify_lane_trajectory(**scenarios[0]["kwargs"])
    b = module.classify_lane_trajectory(**scenarios[0]["kwargs"])
    if a.wing_classification != b.wing_classification:
        check.fail("classifier not deterministic across two identical calls (wing)")
        return
    if abs(a.sensitivity_indicator - b.sensitivity_indicator) > 1e-12:
        check.fail("classifier not deterministic across two identical calls (sensitivity)")
        return
    check.pass_("classifier is deterministic across repeated calls with identical inputs")


def main() -> int:
    check = Check()
    print("ENGEL_LORENZ_ATTRACTOR_LANE_CLASSIFIER_VERIFIER")
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
    check_required_constants_in_source(check, source)
    smoke(check)
    if check.failures:
        print(f"FAIL Lorenz attractor lane classifier verification failed with {len(check.failures)} issue(s)")
        return 1
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
