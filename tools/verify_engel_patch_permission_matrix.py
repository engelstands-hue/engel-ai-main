#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "engel_patch_permission_matrix.py"
TEST_ROOT = ROOT / "runtime" / "tests" / "engel_patch_permission_matrix"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_module():
    spec = importlib.util.spec_from_file_location("engel_patch_permission_matrix", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load permission matrix")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = load_module()
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)
    TEST_ROOT.mkdir(parents=True)
    try:
        matrix = module.build_matrix()
        require(matrix["ok"] is True, "matrix build failed")
        require(len(matrix["actors"]) >= 10, "actor coverage incomplete")
        require(len(matrix["actions"]) >= 16, "action coverage incomplete")

        for actor in ("local_llm", "codex_bridge", "provider_bridge", "sub_engel", "android_worker", "ct246_engel_ai_main"):
            decision = module.decide(matrix, actor=actor, action="approve_protected")
            require(decision["allowed"] is False, f"{actor} could approve protected action")

        non_owner_chat = module.decide(matrix, actor="discord_non_owner", action="chat")
        non_owner_tool = module.decide(matrix, actor="discord_non_owner", action="run_verifier")
        require(non_owner_chat["allowed"] is True, "Discord non-owner chat should remain available")
        require(non_owner_tool["allowed"] is False, "Discord non-owner received tool authority")

        candidate = module.decide(matrix, actor="ct246_engel_ai_main", action="create_candidate_patch")
        require(candidate["allowed"] is True, "CT246 should create candidate patches")

        missing_proof = module.decide(
            matrix,
            actor="ct246_engel_ai_main",
            action="deploy_low_risk",
            context={"risk": "low", "verifier_passed": True},
        )
        require(missing_proof["allowed"] is False, "low-risk deploy passed without sync/rollback proof")
        low_risk = module.decide(
            matrix,
            actor="ct246_engel_ai_main",
            action="deploy_low_risk",
            context={
                "risk": "low",
                "verifier_passed": True,
                "source_sync_proven": True,
                "rollback_ready": True,
            },
        )
        require(low_risk["allowed"] is True, "verified low-risk deploy should proceed")

        model_without_owner = module.decide(
            matrix,
            actor="ct246_engel_ai_main",
            action="promote_model",
            context={"canary_passed": True, "negative_eval_passed": True, "rollback_ready": True},
        )
        require(model_without_owner["allowed"] is False, "model promotion passed without owner")

        direct_memory = module.decide(
            matrix,
            actor="ct246_engel_ai_main",
            action="write_trusted_memory",
            context={"direct_owner_memory_request": True, "receipt_required": True},
        )
        require(direct_memory["allowed"] is True, "direct owner memory request should be honored")

        bounded_worker = module.decide(
            matrix,
            actor="android_worker",
            action="execute_bounded_worker_task",
            context={
                "bounded_task": True,
                "worker_paired": True,
                "worker_capability_proven": True,
                "receipt_required": True,
            },
        )
        require(bounded_worker["allowed"] is True, "paired capable Android worker was blocked")

        output = TEST_ROOT / "patch_permission_matrix.json"
        module.write_json(output, matrix)
        loaded = json.loads(output.read_text(encoding="utf-8"))
        require(loaded["schema"] == "ENGEL_PATCH_PERMISSION_MATRIX_V1", "matrix persistence failed")

        print("PASS actor_action_coverage")
        print("PASS provider_worker_no_approval")
        print("PASS discord_chat_only_boundary")
        print("PASS low_risk_completion_conditions")
        print("PASS protected_action_conditions")
        print("PASS direct_owner_memory_request")
        print("PASS bounded_worker_execution")
        print("ENGEL_PATCH_PERMISSION_MATRIX_VERIFY_PASS")
        return 0
    finally:
        if TEST_ROOT.exists():
            shutil.rmtree(TEST_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())

