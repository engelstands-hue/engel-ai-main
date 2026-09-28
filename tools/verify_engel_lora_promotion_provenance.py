#!/usr/bin/env python3
"""Local-only verifier for the LoRA canary-to-deployment provenance contract."""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import tempfile
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANARY_PATH = ROOT / "tools" / "run_engel_ct246_lora_canary_gate.py"
DEPLOY_PATH = ROOT / "tools" / "deploy_engel_core_lineage3_seat_swap.ps1"

checks: list[dict[str, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


sys.dont_write_bytecode = True
canary_source = CANARY_PATH.read_text(encoding="utf-8")
deploy_source = DEPLOY_PATH.read_text(encoding="utf-8")
compile(canary_source, str(CANARY_PATH), "exec")
check("canary_compiles", True, "Python source compiles locally")

spec = importlib.util.spec_from_file_location("engel_lora_canary_verify", CANARY_PATH)
assert spec and spec.loader
canary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(canary)
canary.require_ct246_ssd_path = lambda path: None

with tempfile.TemporaryDirectory(prefix="engel_lora_provenance_verify_") as raw:
    work = Path(raw)
    tree = work / "adapter"
    tree.mkdir()
    (tree / "adapter_model.safetensors").write_bytes(b"adapter-v1")
    (tree / "adapter_config.json").write_text('{"r":8}\n', encoding="utf-8")
    first = canary.tree_hash_manifest(tree)
    (tree / "ENGEL_MODEL_CARD.json").write_text('{"status":"candidate"}\n', encoding="utf-8")
    second = canary.tree_hash_manifest(tree)
    check(
        "model_card_is_excluded_from_core_tree_hash",
        first["tree_sha256"] == second["tree_sha256"],
        first["tree_sha256"],
    )
    (tree / "adapter_model.safetensors").write_bytes(b"adapter-v2")
    third = canary.tree_hash_manifest(tree)
    check(
        "artifact_tampering_changes_tree_hash",
        third["tree_sha256"] != first["tree_sha256"],
        third["tree_sha256"],
    )

    atomic_path = work / "receipt.json"
    canary.write_json(atomic_path, {"ok": True})
    check(
        "atomic_json_leaves_no_temporary_file",
        json.loads(atomic_path.read_text(encoding="utf-8"))["ok"] is True
        and not list(work.glob(".receipt.json.*.tmp")),
        str(atomic_path),
    )

    immutable_path = work / "ENGEL_CT246_LORA_PROOF_20260809T010101Z.json"
    immutable_path.write_text('{"ok":true}\n', encoding="utf-8")
    payload, digest = canary.immutable_receipt(immutable_path, "fixture proof")
    check(
        "immutable_receipt_binds_exact_bytes",
        payload.get("ok") is True and len(digest) == 64,
        digest,
    )
    latest_path = work / "ENGEL_CT246_LORA_PROOF_LATEST.json"
    latest_path.write_text('{"ok":true}\n', encoding="utf-8")
    try:
        canary.immutable_receipt(latest_path, "fixture proof")
        latest_refused = False
    except RuntimeError:
        latest_refused = True
    check(
        "latest_alias_is_not_an_immutable_receipt",
        latest_refused,
        "LATEST aliases are refused for provenance binding",
    )

    contract = {
        "schema": canary.PROMOTION_CONTRACT_SCHEMA,
        "proof_receipt_sha256": digest,
        "adapter_tree_sha256": third["tree_sha256"],
    }
    check(
        "contract_digest_is_canonical",
        canary.canonical_json_sha256(contract)
        == canary.canonical_json_sha256(dict(reversed(list(contract.items())))),
        canary.canonical_json_sha256(contract),
    )

    merged = work / "merged"
    merged.mkdir()
    (merged / "config.json").write_text('{"model_type":"fixture"}\n', encoding="utf-8")
    legacy_proof = {
        "ok": True,
        "model_weight_improvement_claimed": True,
        "validation_loss_delta": -0.1,
        "receipt_path": str(immutable_path),
        "train_summary": {"adapter": str(tree), "merged": str(merged)},
    }
    legacy_check = canary.validate_proof(legacy_proof, immutable_path, digest)
    check(
        "legacy_unbound_proof_is_not_canary_ready",
        legacy_check["ok"] is False
        and any("artifact manifest" in item for item in legacy_check["blockers"]),
        "; ".join(legacy_check["blockers"]),
    )
    bound_proof = dict(legacy_proof)
    bound_proof.update({
        "artifact_status": "proven",
        "proof_pointer_advanced": True,
        "proof_gates": {"passed": True},
        "new_adapter_path": str(tree),
        "new_merged_path": str(merged),
        "adapter_artifact_manifest": {
            "verified": True,
            "artifact_set_sha256": third["tree_sha256"],
        },
    })
    bound_check = canary.validate_proof(bound_proof, immutable_path, digest)
    check(
        "bound_proven_receipt_is_canary_ready",
        bound_check["ok"] is True,
        "; ".join(bound_check["blockers"]) or "all proof provenance gates present",
    )

    # Exercise the complete canary contract path with a fake local subprocess result.
    # No transformer, SSH, HTTP, service, or model command is started.
    immutable_path.write_text(
        json.dumps(bound_proof, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    helper = work / "helper"
    helper.mkdir()
    (helper / "config.json").write_text('{"model_type":"fixture"}\n', encoding="utf-8")
    canary.REPORT_ROOT = work / "reports"
    canary.TRAIN_ROOT = work / "training"
    canary.LATEST_CANARY = canary.REPORT_ROOT / "ENGEL_CT246_LORA_CANARY_LATEST.json"
    canary.HELPER_MANIFEST = canary.REPORT_ROOT / "HELPER.json"
    canary.VENV_PY = work / "never-run-python"
    canary.stamp = lambda: "20260809T030303Z"
    expected_output = {
        "ok": True,
        "schema": "engel_ct246_transformers_lora_canary_outputs_v1",
        "candidate_model_path": str(merged),
        "rows": [{"id": "fixture", "ok": True}],
    }
    canary.subprocess.run = lambda *args, **kwargs: types.SimpleNamespace(
        returncode=0,
        stdout=json.dumps(expected_output),
        stderr="",
    )
    simulated = canary.run_canary(
        argparse.Namespace(
            approval=canary.CANARY_APPROVAL_PHRASE,
            proof_receipt=str(immutable_path),
            origin="isolated_verifier",
            helper_model=str(helper),
            max_new_tokens=8,
            torch_threads=1,
            canary_timeout_seconds=1,
        )
    )
    simulated_contract = simulated.get("promotion_contract") or {}
    check(
        "simulated_canary_mints_digest_bound_contract",
        simulated.get("ok") is True
        and simulated.get("provenance_stable_after_canary") is True
        and simulated.get("promotion_contract_sha256")
        == canary.canonical_json_sha256(simulated_contract)
        and str(simulated.get("promotion_approval_required") or "").endswith(
            str(simulated.get("promotion_contract_sha256"))[:16]
        ),
        str(simulated.get("promotion_approval_required") or ""),
    )

remote_match = re.search(
    r"\$remoteProgram\s*=\s*@'\r?\n(?P<python>.*?)\r?\n'@",
    deploy_source,
    flags=re.DOTALL,
)
remote_python = remote_match.group("python") if remote_match else ""
if remote_python:
    compile(remote_python, "embedded_ct246_lora_deployer.py", "exec")
check(
    "embedded_remote_deployer_compiles",
    bool(remote_python),
    "embedded Python extracted and compiled" if remote_python else "remote program missing",
)
if remote_python:
    namespace = {"__name__": "embedded_lora_deployer_verifier"}
    exec(compile(remote_python, "embedded_ct246_lora_deployer.py", "exec"), namespace)
    expected = {
        "canary_receipt_path": "/opt/engel/canary.json",
        "canary_receipt_sha256": "A" * 64,
        "promotion_contract_sha256": "B" * 64,
        "proof_receipt_path": "/opt/engel/proof.json",
        "proof_receipt_sha256": "C" * 64,
        "adapter_tree_sha256": "D" * 64,
        "merged_path": "/opt/engel/merged",
        "merged_tree_sha256": "E" * 64,
    }
    old_blockers, _, _ = namespace["conversion_contract_blockers"](
        {"schema": "engel_gguf_conversion_receipt_v1", "ok": True}, expected
    )
    validator_command = [
        "/opt/engel/.venv/bin/python",
        "/opt/engel/tools/run_engel_ct246_gguf_canary.py",
        "--request",
        "/opt/engel/llm_training/fixture/request.json",
    ]
    validator_command_sha = namespace["sha256_bytes"](
        json.dumps(
            validator_command, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    )
    validator_version = "fixture-1"
    case_ids = ["normal_chat", "identity", "training_truth", "simple_math"]
    case_rows = [
        {"id": case_id, "ok": True, "quality_failures": []}
        for case_id in case_ids
    ]
    validator_output = {
        "schema": namespace["GGUF_VALIDATOR_OUTPUT_SCHEMA"],
        "ok": True,
        "validator_version": validator_version,
        "gguf_sha256": "F" * 64,
        "gguf_bytes": 100,
        "case_ids": case_ids,
        "case_contract_sha256": "6" * 64,
        "rows": case_rows,
    }
    validation = {
        "schema": namespace["GGUF_VALIDATION_SCHEMA"],
        "ok": True,
        "gguf_sha256": "F" * 64,
        "gguf_bytes": 100,
        "validator": {
            "path": "/opt/engel/tools/run_engel_ct246_gguf_canary.py",
            "sha256": "1" * 64,
            "version": validator_version,
            "version_sha256": namespace["sha256_bytes"](
                validator_version.encode("utf-8")
            ),
            "python_sha256": "2" * 64,
            "command": validator_command,
            "command_sha256": validator_command_sha,
            "invocation_contract_sha256": "3" * 64,
        },
        "stdout": {"sha256": "4" * 64},
        "stderr": {"sha256": "5" * 64},
        "case_contract_sha256": "6" * 64,
        "case_ids": case_ids,
        "cases": case_rows,
        "validator_output_sha256": namespace["canonical_json_sha256"](
            validator_output
        ),
        "validator_output": validator_output,
    }
    valid_conversion = {
        "schema": namespace["CONVERSION_SCHEMA"],
        "ok": True,
        "bindings": expected,
        "validation": validation,
        "output": {
            "gguf_path": "/opt/engel/models-active/llm/test/test-q8_0.gguf",
            "gguf_sha256": "F" * 64,
            "gguf_bytes": 100,
            "quantization": "Q8_0",
        },
    }
    valid_blockers, _, _ = namespace["conversion_contract_blockers"](
        valid_conversion, expected
    )
else:
    old_blockers = ["remote program missing"]
    valid_blockers = ["remote program missing"]
check(
    "legacy_conversion_schema_is_refused_without_remote_actions",
    any("cannot prove provenance" in item for item in old_blockers),
    "; ".join(old_blockers),
)
check(
    "fully_bound_conversion_contract_passes_pure_validator",
    not valid_blockers,
    "; ".join(valid_blockers) or "no blockers",
)

required_canary_markers = (
    "proof_receipt_sha256",
    "adapter_tree_manifest",
    "merged_tree_manifest",
    "promotion_contract_sha256",
    "REQUIRED_CONVERSION_RECEIPT_SCHEMA",
    "provenance_stable_after_canary",
)
check(
    "canary_contract_contains_all_provenance_bindings",
    all(marker in canary_source for marker in required_canary_markers),
    ", ".join(required_canary_markers),
)

required_deploy_markers = (
    "engel_gguf_conversion_receipt_v2",
    "canary_receipt_sha256",
    "promotion_contract_sha256",
    "proof_receipt_sha256",
    "adapter_tree_sha256",
    "merged_tree_sha256",
    "actual GGUF SHA-256 differs",
    "os.O_EXCL",
    "os.replace",
    "rollback_override",
    "systemctl",
    "chat route did not execute the deployed local GGUF",
    "write_deployment_receipt",
)
check(
    "deployer_is_fail_closed_and_receipted",
    all(marker in deploy_source for marker in required_deploy_markers),
    ", ".join(required_deploy_markers),
)
check(
    "deployer_never_overwrites_a_q5_seat_with_q8_bytes",
    "engel-qwen2.5-1.5b-deepreason-q5_k_m.gguf" not in deploy_source
    and " cp " not in deploy_source,
    "deployment changes an atomic systemd route override, not model bytes",
)
check(
    "proof_and_conversion_inputs_must_be_immutable_names",
    "Assert-ImmutableCtReceiptPath" in deploy_source
    and "not a LATEST alias" in deploy_source,
    "PowerShell preflight refuses LATEST aliases before SSH",
)

passed = sum(item["status"] == "PASS" for item in checks)
failed = [item for item in checks if item["status"] != "PASS"]
for item in checks:
    print(f"{item['status']} {item['name']} :: {item['detail']}")
print(f"\n{passed}/{len(checks)} checks passed")
if failed:
    print("verify_engel_lora_promotion_provenance: RED")
    raise SystemExit(1)
print("verify_engel_lora_promotion_provenance: GREEN")
