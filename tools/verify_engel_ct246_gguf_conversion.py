#!/usr/bin/env python3
"""Isolated verifier for the CT246 provenance-bound GGUF conversion wrapper.

This verifier never calls the converter, loads a model, opens SSH, deploys a
model, or controls a service. It uses temporary byte fixtures and pure/static
contract checks only.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "run_engel_ct246_gguf_conversion.py"
VALIDATOR_PATH = ROOT / "tools" / "run_engel_ct246_gguf_canary.py"
HF_CANARY_PATH = ROOT / "tools" / "run_engel_ct246_lora_canary_gate.py"
DEPLOY_PATH = ROOT / "tools" / "deploy_engel_core_lineage3_seat_swap.ps1"
CYCLE_PATH = ROOT / "tools" / "run_engel_real_training_cycle.py"

checks: list[dict[str, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append(
        {"name": name, "status": "PASS" if ok else "FAIL", "detail": detail}
    )


def write_json(path: Path, payload: dict[str, Any], read_only: bool = False) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if read_only:
        os.chmod(path, stat.S_IREAD)


def fake_validator_source(passes: bool) -> str:
    """Return a standard-library-only validator fixture; it never loads a model."""
    return f'''#!/usr/bin/env python3
GGUF_VALIDATOR_VERSION = "fixture-1"
import argparse, hashlib, json
from pathlib import Path

PASS = {passes!r}
IDS = ["normal_chat", "identity", "training_truth", "simple_math"]
ap = argparse.ArgumentParser()
ap.add_argument("--request", required=True)
args = ap.parse_args()
request = json.loads(Path(args.request).read_text(encoding="utf-8-sig"))
contract = {{"schema": "fixture_contract", "case_ids": IDS}}
contract_sha = hashlib.sha256(json.dumps(
    contract, ensure_ascii=False, separators=(",", ":"), sort_keys=True
).encode("utf-8")).hexdigest().upper()
rows = []
for case_id in IDS:
    ok = PASS or case_id != "simple_math"
    failures = [] if ok else ["math_answer_missing_291"]
    reply = "291 is the result." if case_id == "simple_math" else "Fixture Engel reply."
    rows.append({{
        "id": case_id,
        "reply": reply,
        "reply_sha256": hashlib.sha256(reply.encode("utf-8")).hexdigest().upper(),
        "quality_failures": failures,
        "ok": ok,
    }})
payload = {{
    "ok": PASS,
    "schema": "engel_ct246_gguf_behavioral_canary_output_v1",
    "validator_version": GGUF_VALIDATOR_VERSION,
    "gguf_path": request["gguf_path"],
    "gguf_sha256": request["gguf_sha256"],
    "gguf_bytes": request["gguf_bytes"],
    "case_contract": contract,
    "case_contract_sha256": contract_sha,
    "case_ids": IDS,
    "rows": rows,
    "runtime": {{"engine": "isolated-fake-no-model"}},
}}
print(json.dumps(payload, indent=2, sort_keys=True))
raise SystemExit(0 if PASS else 1)
'''


sys.dont_write_bytecode = True
source = TOOL_PATH.read_text(encoding="utf-8")
validator_source = VALIDATOR_PATH.read_text(encoding="utf-8")
deploy_source = DEPLOY_PATH.read_text(encoding="utf-8")
cycle_source = CYCLE_PATH.read_text(encoding="utf-8")
tree = ast.parse(source, filename=str(TOOL_PATH))
compile(tree, str(TOOL_PATH), "exec")
compile(validator_source, str(VALIDATOR_PATH), "exec")
check("conversion_wrapper_compiles", True, "AST parsed and Python source compiled")

spec = importlib.util.spec_from_file_location("engel_gguf_conversion_verify", TOOL_PATH)
assert spec and spec.loader
conversion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(conversion)

validator_spec = importlib.util.spec_from_file_location(
    "engel_gguf_validator_verify", VALIDATOR_PATH
)
assert validator_spec and validator_spec.loader
validator = importlib.util.module_from_spec(validator_spec)
validator_spec.loader.exec_module(validator)

hf_spec = importlib.util.spec_from_file_location("engel_hf_canary_verify", HF_CANARY_PATH)
assert hf_spec and hf_spec.loader
hf_canary = importlib.util.module_from_spec(hf_spec)
hf_spec.loader.exec_module(hf_canary)
check(
    "gguf_canary_reuses_hf_behavioral_cases",
    validator.canary_cases() == hf_canary.canary_prompts()
    and [item["id"] for item in validator.canary_cases()]
    == list(conversion.GGUF_CANARY_CASE_IDS),
    ", ".join(item["id"] for item in validator.canary_cases()),
)
check(
    "gguf_canary_reuses_bounded_grading_contract",
    validator.quality("simple_math", "291 is the result.") == []
    and "math_answer_missing_291"
    in validator.quality("simple_math", "The result is unknown.")
    and any(
        item.startswith("bad_pattern:")
        for item in validator.quality("identity", "I am Qwen.")
    ),
    "math, identity-leak, minimum-length, and promotion-truth checks are canonical",
)

# Redirect the CT-only path guard for disposable local fixtures. The production
# function remains present and is checked statically below.
conversion.require_ct246_path = lambda path, label: Path(path)

with tempfile.TemporaryDirectory(prefix="engel_gguf_conversion_verify_") as raw:
    work = Path(raw)
    adapter = work / "adapter"
    merged = work / "merged"
    adapter.mkdir()
    merged.mkdir()
    (adapter / "adapter_config.json").write_text('{"r":8}\n', encoding="utf-8")
    (adapter / "adapter_model.safetensors").write_bytes(b"fixture-adapter-weights")
    (adapter / "ENGEL_MODEL_CARD.json").write_text(
        '{"artifact_status":"proven"}\n', encoding="utf-8"
    )
    (merged / "config.json").write_text(
        '{"model_type":"fixture"}\n', encoding="utf-8"
    )
    (merged / "model.safetensors").write_bytes(b"fixture-merged-weights")
    (merged / "ENGEL_MODEL_CARD.json").write_text(
        '{"artifact_status":"proven"}\n', encoding="utf-8"
    )

    adapter_promotion = conversion.tree_hash_manifest(
        adapter, exclude_model_card=True
    )
    merged_promotion = conversion.tree_hash_manifest(
        merged, exclude_model_card=True
    )
    merged_complete = conversion.tree_hash_manifest(
        merged, exclude_model_card=False
    )
    check(
        "complete_input_tree_includes_model_card",
        merged_complete["file_count"] == merged_promotion["file_count"] + 1
        and merged_complete["tree_sha256"] != merged_promotion["tree_sha256"],
        (
            f"promotion={merged_promotion['tree_sha256']} "
            f"complete={merged_complete['tree_sha256']}"
        ),
    )

    proof_path = work / "ENGEL_CT246_LORA_PROOF_20260809T010101Z.json"
    model_name = "engel-core-qwen2-5-1-5b-l3-a1b2c3d4e5f6"
    proof = {
        "ok": True,
        "schema": conversion.PROOF_SCHEMA,
        "receipt_path": str(proof_path),
        "artifact_status": "proven",
        "proof_pointer_advanced": True,
        "proof_gates": {"passed": True},
        "model_weight_improvement_claimed": True,
        "validation_loss_delta": -0.125,
        "engel_model_name": model_name,
        "new_adapter_path": str(adapter),
        "new_merged_path": str(merged),
        "adapter_artifact_manifest": {
            "verified": True,
            "artifact_set_sha256": adapter_promotion["tree_sha256"],
        },
    }
    write_json(proof_path, proof)
    proof_sha = conversion.sha256_file(proof_path)

    canary_path = work / "ENGEL_CT246_LORA_CANARY_20260809T020202Z.json"
    required_binding_keys = [
        "canary_receipt_path",
        "canary_receipt_sha256",
        "promotion_contract_sha256",
        "proof_receipt_path",
        "proof_receipt_sha256",
        "adapter_tree_sha256",
        "merged_path",
        "merged_tree_sha256",
    ]
    contract = {
        "schema": conversion.CONTRACT_SCHEMA,
        "canary_receipt_path": str(canary_path),
        "proof_receipt_path": str(proof_path),
        "proof_receipt_sha256": proof_sha,
        "adapter_path": str(adapter),
        "adapter_tree_sha256": adapter_promotion["tree_sha256"],
        "merged_path": str(merged),
        "merged_tree_sha256": merged_promotion["tree_sha256"],
        "tree_hash_algorithm": merged_promotion["hash_algorithm"],
        "tree_hash_excluded_relative_paths": ["ENGEL_MODEL_CARD.json"],
        "required_conversion_receipt_schema": conversion.CONVERSION_SCHEMA,
        "required_conversion_binding_keys": required_binding_keys,
        "required_conversion_bindings": {
            "proof_receipt_path": str(proof_path),
            "proof_receipt_sha256": proof_sha,
            "adapter_tree_sha256": adapter_promotion["tree_sha256"],
            "merged_path": str(merged),
            "merged_tree_sha256": merged_promotion["tree_sha256"],
        },
    }
    contract_sha = conversion.canonical_json_sha256(contract)
    run_stamp = "20260809T020202Z"
    phrase = f"APPROVE_ENGEL_PROMOTE_LORA_CANARY_{run_stamp}_{contract_sha[:16]}"
    canary = {
        "ok": True,
        "schema": conversion.CANARY_SCHEMA,
        "receipt_path": str(canary_path),
        "run_stamp": run_stamp,
        "canary_passed": True,
        "promotion_ready": True,
        "provenance_stable_after_canary": True,
        "proof_receipt_path": str(proof_path),
        "proof_receipt_sha256": proof_sha,
        "proof_receipt_sha256_after_canary": proof_sha,
        "adapter_tree_sha256_after_canary": adapter_promotion["tree_sha256"],
        "merged_tree_sha256_after_canary": merged_promotion["tree_sha256"],
        "promotion_contract": contract,
        "promotion_contract_sha256": contract_sha,
        "promotion_approval_required": phrase,
    }
    write_json(canary_path, canary, read_only=True)

    context = conversion.validate_canary_contract(canary_path, phrase)
    check(
        "valid_stamped_canary_and_exact_phrase_pass",
        context["promotion_contract_sha256"] == contract_sha
        and context["proof_receipt_sha256"] == proof_sha
        and context["merged_promotion_tree"]["tree_sha256"]
        == merged_promotion["tree_sha256"],
        contract_sha,
    )

    latest_path = work / "ENGEL_CT246_LORA_CANARY_LATEST.json"
    write_json(latest_path, canary, read_only=True)
    try:
        conversion.validate_canary_contract(latest_path, phrase)
        latest_refused = False
    except conversion.ConversionBlocked as exc:
        latest_refused = "LATEST" in str(exc)
    check(
        "latest_canary_alias_is_refused",
        latest_refused,
        "only a stamped canary receipt may authorize conversion",
    )

    try:
        conversion.validate_canary_contract(canary_path, phrase + "_WRONG")
        wrong_phrase_refused = False
    except conversion.ConversionBlocked as exc:
        wrong_phrase_refused = "approval" in str(exc)
    check(
        "non_exact_promotion_phrase_is_refused",
        wrong_phrase_refused,
        "approval must equal the digest-bound phrase in the canary",
    )

    merged_config = merged / "config.json"
    original_config = merged_config.read_bytes()
    merged_config.write_bytes(original_config + b"tamper")
    try:
        conversion.validate_canary_contract(canary_path, phrase)
        tamper_refused = False
    except conversion.ConversionBlocked as exc:
        tamper_refused = "merged tree SHA-256" in str(exc)
    merged_config.write_bytes(original_config)
    check(
        "merged_tree_tampering_is_refused",
        tamper_refused,
        "the converter wrapper recomputes the promotion-bound merged tree",
    )

    expected_name = f"{model_name}-q8_0.gguf"
    check(
        "output_name_binds_model_and_quantization",
        conversion.gguf_filename(model_name, "Q8-0") == expected_name
        and "q5" not in expected_name,
        expected_name,
    )
    try:
        conversion.normalize_quantization("q5_k_m")
        unsupported_quant_refused = False
    except conversion.ConversionBlocked:
        unsupported_quant_refused = True
    check(
        "unsupported_or_misnamed_quantization_is_refused",
        unsupported_quant_refused,
        str(conversion.ALLOWED_QUANTIZATIONS),
    )

    # Run a standard-library-only fake validator through the real invocation/binding
    # helper. No converter or llama/model runtime is imported or started.
    fake_gguf = work / "temporary-fixture-q8_0.gguf"
    fake_gguf.write_bytes(b"GGUF-isolated-fixture-bytes")
    fake_gguf_sha = conversion.sha256_file(fake_gguf)
    validator_dir = work / "passing_validator"
    validator_dir.mkdir()
    fake_validator = validator_dir / "run_engel_ct246_gguf_canary.py"
    fake_validator.write_text(fake_validator_source(True), encoding="utf-8")
    validation_out = work / "validation_pass_out"
    validation_logs = work / "validation_pass_logs"
    validation_out.mkdir()
    validation_logs.mkdir()
    validation = conversion.invoke_gguf_validator(
        gguf_path=fake_gguf,
        gguf_sha256=fake_gguf_sha,
        gguf_bytes=fake_gguf.stat().st_size,
        validator_path=fake_validator,
        validator_python=Path(sys.executable),
        output_dir=validation_out,
        log_dir=validation_logs,
        timeout_seconds=30,
        max_new_tokens=32,
        threads=1,
    )
    check(
        "fake_validator_pass_is_hash_and_case_bound",
        validation.get("ok") is True
        and validation.get("gguf_sha256") == fake_gguf_sha
        and validation.get("case_ids") == list(conversion.GGUF_CANARY_CASE_IDS)
        and all((validation.get(name) or {}).get("sha256") for name in ("stdout", "stderr"))
        and (validation.get("validator") or {}).get("sha256")
        == conversion.sha256_file(fake_validator),
        fake_gguf_sha,
    )

    failing_dir = work / "failing_validator"
    failing_dir.mkdir()
    failing_validator = failing_dir / "run_engel_ct246_gguf_canary.py"
    failing_validator.write_text(fake_validator_source(False), encoding="utf-8")
    failing_out = work / "validation_fail_out"
    failing_logs = work / "validation_fail_logs"
    failing_out.mkdir()
    failing_logs.mkdir()
    try:
        conversion.invoke_gguf_validator(
            gguf_path=fake_gguf,
            gguf_sha256=fake_gguf_sha,
            gguf_bytes=fake_gguf.stat().st_size,
            validator_path=failing_validator,
            validator_python=Path(sys.executable),
            output_dir=failing_out,
            log_dir=failing_logs,
            timeout_seconds=30,
            max_new_tokens=32,
            threads=1,
        )
        failed_validator_refused = False
        failed_record: dict[str, Any] = {}
    except conversion.GGUFValidationBlocked as exc:
        failed_validator_refused = True
        failed_record = exc.record
    check(
        "fake_validator_failure_blocks_conversion_success",
        failed_validator_refused
        and failed_record.get("ok") is False
        and failed_record.get("returncode") == 1
        and bool(failed_record.get("blockers")),
        "; ".join(failed_record.get("blockers") or []),
    )

    context["gguf_validation"] = validation
    output = {
        "gguf_path": str(work / expected_name),
        "gguf_sha256": fake_gguf_sha,
        "gguf_bytes": fake_gguf.stat().st_size,
        "quantization": "Q8_0",
        "header": "GGUF",
    }
    converter_record = {
        "path": str(work / "convert_hf_to_gguf.py"),
        "sha256": "A" * 64,
        "version": {"value": "fixture", "source": "fixture"},
        "version_sha256": "E" * 64,
        "python_sha256": "B" * 64,
        "command": ["python", "convert_hf_to_gguf.py"],
        "command_sha256": "C" * 64,
        "invocation_contract_sha256": "D" * 64,
    }
    built = conversion.build_conversion_receipt(
        context, output, converter_record, {"run_id": "fixture"}
    )
    tampered_context = dict(context)
    tampered_context["gguf_validation"] = dict(validation)
    tampered_context["gguf_validation"]["gguf_sha256"] = "0" * 64
    try:
        conversion.build_conversion_receipt(
            tampered_context, output, converter_record, {"run_id": "fixture"}
        )
        unbound_validation_refused = False
    except conversion.ConversionBlocked:
        unbound_validation_refused = True
    check(
        "success_receipt_refuses_unbound_gguf_validation",
        unbound_validation_refused,
        "validation GGUF hash must equal output GGUF hash",
    )
    expected_bindings = {
        "canary_receipt_path": str(canary_path),
        "canary_receipt_sha256": conversion.sha256_file(canary_path),
        "promotion_contract_sha256": contract_sha,
        "proof_receipt_path": str(proof_path),
        "proof_receipt_sha256": proof_sha,
        "adapter_tree_sha256": adapter_promotion["tree_sha256"],
        "merged_path": str(merged),
        "merged_tree_sha256": merged_promotion["tree_sha256"],
    }
    check(
        "v2_receipt_contains_every_deployer_binding",
        built.get("schema") == conversion.CONVERSION_SCHEMA
        and built.get("ok") is True
        and built.get("bindings") == expected_bindings,
        ", ".join(sorted(expected_bindings)),
    )
    check(
        "receipt_records_converter_version_and_command_hashes",
        all(
            key in built.get("converter", {})
            for key in (
                "sha256",
                "version",
                "version_sha256",
                "python_sha256",
                "command_sha256",
                "invocation_contract_sha256",
            )
        ),
        ", ".join(sorted(built.get("converter", {}))),
    )

    # Test the canonical stamped write without ever entering run_conversion.
    conversion.LATEST_RECEIPT = work / "ENGEL_CT246_GGUF_CONVERSION_LATEST.json"
    stamped = work / "ENGEL_CT246_GGUF_CONVERSION_20260809T030303Z.json"
    conversion.write_final_receipt(stamped, built)
    check(
        "stamped_receipt_is_atomic_read_only_and_latest_is_status_only",
        stamped.is_file()
        and not (stamped.stat().st_mode & 0o222)
        and conversion.LATEST_RECEIPT.is_file()
        and not list(work.glob(f".{stamped.name}.*.tmp")),
        str(stamped),
    )

    # Restore writable permissions so TemporaryDirectory cleanup remains portable.
    for path in (
        canary_path,
        latest_path,
        stamped,
        validation_out / "gguf_validation_request.json",
        failing_out / "gguf_validation_request.json",
    ):
        if path.exists():
            os.chmod(path, stat.S_IREAD | stat.S_IWRITE)

# Reuse the deployer's pure contract validator so the wrapper and deployment gate
# cannot drift while still avoiding SSH, service, HTTP, or model activity.
remote_match = re.search(
    r"\$remoteProgram\s*=\s*@'\r?\n(?P<python>.*?)\r?\n'@",
    deploy_source,
    flags=re.DOTALL,
)
remote_python = remote_match.group("python") if remote_match else ""
if remote_python:
    namespace = {"__name__": "embedded_gguf_contract_verifier"}
    exec(compile(remote_python, "embedded_ct246_deployer.py", "exec"), namespace)
    deploy_blockers, _, _ = namespace["conversion_contract_blockers"](
        built, expected_bindings
    )
    missing_validation = json.loads(json.dumps(built))
    missing_validation.pop("validation", None)
    missing_validation_blockers, _, _ = namespace[
        "conversion_contract_blockers"
    ](missing_validation, expected_bindings)
    wrong_validation_hash = json.loads(json.dumps(built))
    wrong_validation_hash["validation"]["gguf_sha256"] = "0" * 64
    wrong_validation_blockers, _, _ = namespace[
        "conversion_contract_blockers"
    ](wrong_validation_hash, expected_bindings)
else:
    deploy_blockers = ["embedded deployer not found"]
    missing_validation_blockers = ["embedded deployer not found"]
    wrong_validation_blockers = ["embedded deployer not found"]
check(
    "generated_receipt_passes_deployer_pure_contract_gate",
    not deploy_blockers,
    "; ".join(deploy_blockers) or "no conversion contract blockers",
)
check(
    "deployer_refuses_missing_or_unbound_gguf_validation",
    any("mandatory GGUF validation" in item for item in missing_validation_blockers)
    and any("not bound to the output SHA-256" in item for item in wrong_validation_blockers),
    (
        "; ".join(missing_validation_blockers[:2])
        + " | "
        + "; ".join(wrong_validation_blockers[:2])
    ),
)

subprocess_calls = [
    node
    for node in ast.walk(tree)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute)
    and isinstance(node.func.value, ast.Name)
    and node.func.value.id == "subprocess"
]
shell_enabled = any(
    keyword.arg == "shell"
    and isinstance(keyword.value, ast.Constant)
    and keyword.value.value is True
    for node in subprocess_calls
    for keyword in node.keywords
)
check(
    "converter_exit_is_checked_without_shell_or_pipe_masking",
    bool(subprocess_calls)
    and not shell_enabled
    and "returncode != 0" in source
    and "stdout=stdout_handle" in source
    and "stderr=stderr_handle" in source,
    "direct subprocess.run with separate stdout/stderr and explicit return-code gate",
)

required_markers = (
    'path.name != "convert_hf_to_gguf.py"',
    "converter_sha256",
    "complete_input_tree_sha256",
    '"--outfile"',
    '"--outtype"',
    'handle.read(4) != b"GGUF"',
    "converter mutated the complete merged input tree",
    "invoke_gguf_validator(",
    "GGUF validator changed the converted GGUF",
    "a passed GGUF behavioral validation is mandatory",
    "os.link(temporary_output, final_output)",
    "atomic_write_new(path, encoded, mode=0o444)",
    "write_final_receipt(receipt_path, receipt)",
    "production_chat_affected\": False",
    "service_modified\": False",
    "deployment_performed\": False",
)
check(
    "wrapper_is_source_only_hash_bound_and_non_deploying",
    all(marker in source for marker in required_markers)
    and "systemctl" not in source
    and "ssh" not in source.casefold(),
    ", ".join(required_markers),
)
check(
    "cycle_sync_roster_contains_conversion_wrapper",
    '"run_engel_ct246_gguf_conversion.py"' in cycle_source
    and '"run_engel_ct246_gguf_canary.py"' in cycle_source
    and "--canary-receipt /opt/engel/reports/llm_training/"
    "ENGEL_CT246_LORA_CANARY_<STAMP>.json" in cycle_source
    and "--converter /opt/engel/tools/llama.cpp/convert_hf_to_gguf.py"
    in cycle_source
    and "--validator /opt/engel/tools/run_engel_ct246_gguf_canary.py"
    in cycle_source
    and "--validator-python /opt/engel/.venv/bin/python" in cycle_source,
    "future approved tool syncs and operator guidance use the canonical CT wrapper",
)

passed = sum(item["status"] == "PASS" for item in checks)
failed = [item for item in checks if item["status"] != "PASS"]
for item in checks:
    print(f"{item['status']} {item['name']} :: {item['detail']}")
print(f"\n{passed}/{len(checks)} checks passed")
if failed:
    print("verify_engel_ct246_gguf_conversion: RED")
    raise SystemExit(1)
print("verify_engel_ct246_gguf_conversion: GREEN")
