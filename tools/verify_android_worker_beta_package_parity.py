"""Verify Android Worker Beta has structural parity with Alpha for the queen-choice + phone-UI layer.

This locks in that beta keeps the same set of files Alpha has, with beta-specific
identifiers (worker_id, preapproval token, allowed job types). Static-only checks;
no execution, no network, no source mutation.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BETA = ROOT / "remote_workers" / "android_worker_beta"
ALPHA = ROOT / "remote_workers" / "android_worker_alpha"

WORKER_ID = "android_worker_beta"
PREAPPROVAL_TOKEN = "APPROVE_ANDROID_WORKER_BETA_BOUNDED_JOB_CHOICES_V1"
ALLOWED_JOB_TYPES = {"draft_candidate_json", "format_report_draft", "classify_file"}

REQUIRED_BETA_FILES = [
    "config/worker_identity.json",
    "config/worker_capabilities.json",
    "config/worker_autonomy_policy.json",
    "config/queen_choice_policy.json",
    "config/preapproved_worker_actions.json",
    "communication_queen_choices.py",
    "queen_choice_bridge.py",
    "remote_worker_phone_ui.py",
    "start_remote_worker_ui.py",
    "remote_worker_runner.py",
    "remote_worker_local_executor.py",
    "remote_worker_status.py",
    "remote_worker_job_view.py",
    "run_assigned_job.py",
    "run_worker_status.py",
    "README_ANDROID_SETUP.md",
    "README_PHONE_BUTTON_SETUP.md",
]

REQUIRED_FOLDERS = [
    "inbox",
    "jobs",
    "outbox",
    "logs",
    "receipts",
    "status",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_files() -> None:
    for rel in REQUIRED_BETA_FILES:
        path = BETA / rel
        require(path.is_file(), "missing required beta file: " + rel)
    for folder in REQUIRED_FOLDERS:
        path = BETA / folder
        require(path.is_dir(), "missing required beta folder: " + folder)


def check_identity() -> None:
    identity = read_json(BETA / "config" / "worker_identity.json")
    require(identity.get("worker_id") == WORKER_ID, "worker_id must be android_worker_beta")
    require(identity.get("device_label") == "manual_transfer_device_beta", "device_label must be manual_transfer_device_beta")
    require(identity.get("routing_layer") == "communication_queen_only", "routing_layer must be communication_queen_only")
    require(identity.get("queen_authority") is False, "queen_authority must be false")
    require(identity.get("controls_engel") is False, "controls_engel must be false")
    # hermes_allowed moved out of this "must be false" list per
    # ENGEL_HERMES_POLICY_CHANGE_V1 (Hermes is now approved for local
    # install + human-driven testing). All other safety flags remain
    # locked-false.
    for field in ("trusted_memory_write", "source_mutation", "route_mutation", "patch_apply", "provider_network", "model_runtime", "startup_autorun"):
        require(identity.get(field) is False, field + " must be false")


def check_queen_choice_policy() -> None:
    policy = read_json(BETA / "config" / "queen_choice_policy.json")
    require(policy.get("worker_id") == WORKER_ID, "policy worker_id must be android_worker_beta")
    require(policy.get("preapproval_token") == PREAPPROVAL_TOKEN, "policy preapproval_token mismatch")
    require(policy.get("requires_target_worker_id") == WORKER_ID, "policy must target beta")
    require(set(policy.get("allowed_job_types", [])) == ALLOWED_JOB_TYPES, "policy allowed_job_types must match beta capabilities")
    for field in ("trusted_memory_write", "source_mutation", "route_mutation", "patch_apply", "provider_network", "model_runtime", "startup_autorun", "controls_engel"):
        require(policy.get(field) is False, "policy " + field + " must be false")


def check_preapproved_actions() -> None:
    actions = read_json(BETA / "config" / "preapproved_worker_actions.json")
    require(actions.get("worker_id") == WORKER_ID, "preapproved actions worker_id mismatch")
    require(actions.get("preapproval_token") == PREAPPROVAL_TOKEN, "preapproved actions token mismatch")
    require(actions.get("remote_worker_not_queen") is True, "preapproved actions must mark remote_worker_not_queen")
    blocked = set(actions.get("blocked_actions", []))
    for required_block in ("trusted_memory_write", "memory_promotion", "source_mutation", "route_mutation", "patch_apply", "package_install", "model_runtime", "ollama", "llama_cpp", "startup_autorun", "control_engel", "control_communication_queen"):
        require(required_block in blocked, "blocked_actions missing " + required_block)


def check_communication_queen_choices_module() -> None:
    if str(BETA) not in sys.path:
        sys.path.insert(0, str(BETA))
    spec = importlib.util.spec_from_file_location(
        "beta_communication_queen_choices", BETA / "communication_queen_choices.py"
    )
    require(spec is not None and spec.loader is not None, "could not load beta communication_queen_choices.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["beta_communication_queen_choices"] = module
    spec.loader.exec_module(module)
    require(module.WORKER_ID == WORKER_ID, "module WORKER_ID must be android_worker_beta")
    require(module.PREAPPROVAL_TOKEN == PREAPPROVAL_TOKEN, "module PREAPPROVAL_TOKEN mismatch")
    require(module.ALLOWED_JOB_TYPES == ALLOWED_JOB_TYPES, "module ALLOWED_JOB_TYPES must match beta capabilities")


def check_phone_ui_identifiers() -> None:
    ui_text = (BETA / "remote_worker_phone_ui.py").read_text(encoding="utf-8")
    require("Engel Android Worker Beta" in ui_text, "phone UI must display 'Engel Android Worker Beta' header")
    require("Android Worker Beta" in ui_text, "phone UI must reference 'Android Worker Beta'")
    require("android_worker_beta" in ui_text, "phone UI must reference 'android_worker_beta' worker id")
    require("candidate JSON worker" in ui_text, "phone UI must declare beta's candidate JSON worker role")


def check_readme() -> None:
    readme_text = (BETA / "README_PHONE_BUTTON_SETUP.md").read_text(encoding="utf-8")
    require("Android Worker Beta" in readme_text, "README must reference Android Worker Beta")
    require("android_worker_beta" in readme_text, "README must reference android_worker_beta path")
    require("EngelWorkerBetaUI" in readme_text, "README must reference EngelWorkerBetaUI Termux shortcut name")
    for blocked_term in ("trusted-memory write", "memory promotion", "patch apply", "Hermes", "Ollama", "llama.cpp"):
        require(blocked_term in readme_text, "README must document blocked: " + blocked_term)


def check_parity_with_alpha() -> None:
    # Every file beta has should also exist in alpha (alpha is the reference layout).
    # The reverse is not required — alpha has a finish_alpha_job.py that beta does not need.
    for rel in REQUIRED_BETA_FILES:
        if rel.startswith("config/") or rel.endswith(".md"):
            continue
        alpha_path = ALPHA / rel
        beta_path = BETA / rel
        require(alpha_path.is_file(), "alpha reference missing " + rel + " — package layout drift")
        require(beta_path.is_file(), "beta missing parity file " + rel)


def main() -> int:
    checks = [
        ("files", check_files),
        ("identity", check_identity),
        ("queen_choice_policy", check_queen_choice_policy),
        ("preapproved_actions", check_preapproved_actions),
        ("communication_queen_choices_module", check_communication_queen_choices_module),
        ("phone_ui_identifiers", check_phone_ui_identifiers),
        ("readme", check_readme),
        ("parity_with_alpha", check_parity_with_alpha),
    ]
    failures: list[str] = []
    for name, check in checks:
        try:
            check()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(name + ": " + str(exc))
            print("FAIL " + name + ": " + str(exc))
    if failures:
        print("[FAIL] Android Worker Beta package parity verifier failed.")
        return 1
    print("Android Worker Beta package parity verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
