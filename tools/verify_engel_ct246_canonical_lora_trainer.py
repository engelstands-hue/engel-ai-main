#!/usr/bin/env python3
"""Static/local verifier for the canonical CT246 LoRA trainer handoff.

This verifier never imports torch, opens SSH, or starts training. It parses the
canonical trainer as source and exercises only the proof runner's stdlib atomic
installer against an isolated temporary target.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
TRAINER = TOOLS / "engel_ct246_train_lora.py"
PROOF_RUNNER = TOOLS / "run_engel_ct246_local_lora_proof.py"
CYCLE = TOOLS / "run_engel_real_training_cycle.py"

checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append((name, bool(ok), detail))


def runtime_error(callable_: Any) -> str:
    """Return the fail-closed error text, or an empty string if no error occurred."""
    try:
        callable_()
    except RuntimeError as exc:
        return str(exc)
    return ""


def call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts = [func.attr]
        value = func.value
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            parts.append(value.id)
        return ".".join(reversed(parts))
    return ""


trainer_source = TRAINER.read_text(encoding="utf-8")
trainer_tree = ast.parse(trainer_source, filename=str(TRAINER))
check("canonical_trainer_parses", True, f"{TRAINER.name}: {len(trainer_source)} bytes")

forced_offline: dict[str, str] = {}
for node in ast.walk(trainer_tree):
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        continue
    target = node.targets[0]
    if not isinstance(target, ast.Subscript):
        continue
    if not (
        isinstance(target.value, ast.Attribute)
        and isinstance(target.value.value, ast.Name)
        and target.value.value.id == "os"
        and target.value.attr == "environ"
    ):
        continue
    key = target.slice
    if isinstance(key, ast.Constant) and isinstance(key.value, str):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            forced_offline[key.value] = node.value.value
expected_offline = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
}
check(
    "offline_environment_is_forced",
    all(forced_offline.get(key) == value for key, value in expected_offline.items())
    and "environ.setdefault" not in trainer_source,
    repr(forced_offline),
)

pretrained_calls: list[tuple[str, bool]] = []
for node in ast.walk(trainer_tree):
    if not isinstance(node, ast.Call) or not call_name(node).endswith("from_pretrained"):
        continue
    local_only = any(
        keyword.arg == "local_files_only"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is True
        for keyword in node.keywords
    )
    pretrained_calls.append((call_name(node), local_only))
check(
    "all_hf_loads_are_local_only",
    len(pretrained_calls) == 3 and all(item[1] for item in pretrained_calls),
    repr(pretrained_calls),
)
check(
    "model_and_resume_paths_fail_closed",
    "def require_local_model_directory" in trainer_source
    and 'args.model, "base model", ("config.json",)' in trainer_source
    and '"adapter_config.json", "adapter_model.safetensors"' in trainer_source,
    "base config and local adapter files are required before loading",
)

remove_unused_false = False
for node in ast.walk(trainer_tree):
    if not isinstance(node, ast.Call) or call_name(node) != "TrainingArguments":
        continue
    remove_unused_false = any(
        keyword.arg == "remove_unused_columns"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is False
        for keyword in node.keywords
    )
check(
    "negative_column_survives_trainer",
    remove_unused_false,
    "TrainingArguments(remove_unused_columns=False)",
)

functions = {
    node.name: node
    for node in trainer_tree.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
}
self_test_calls = [
    call_name(node)
    for node in ast.walk(functions.get("self_test", ast.Pass()))
    if isinstance(node, ast.Call)
]
check(
    "negative_aware_loss_and_self_test_retained",
    "negative_aware_loss" in functions
    and "self_test" in functions
    and self_test_calls.count("negative_aware_loss") >= 4
    and "likely-negatives cost more" in trainer_source
    and "clamp keeps finite" in trainer_source,
    f"negative_aware_loss calls in self_test={self_test_calls.count('negative_aware_loss')}",
)

# Execute only the three stdlib split helpers, extracted from the AST. Importing the
# canonical trainer itself would import torch; this proves behavior on a workstation
# with no ML runtime while still executing the canonical function bodies.
split_helper_names = {
    "normalize_negative_prompt",
    "canonical_negative_reply",
    "split_negative_prompt_groups",
}
split_helper_nodes = [
    node
    for node in trainer_tree.body
    if isinstance(node, ast.FunctionDef) and node.name in split_helper_names
]
split_module = ast.Module(body=split_helper_nodes, type_ignores=[])
ast.fix_missing_locations(split_module)
split_namespace: dict[str, Any] = {"hashlib": hashlib, "re": re}
exec(compile(split_module, str(TRAINER), "exec"), split_namespace)
split_negative = split_namespace["split_negative_prompt_groups"]

negative_fixture = [
    {"user": "Alpha prompt", "assistant": "reject alpha one", "marker": "first"},
    {"user": " alpha   PROMPT ", "assistant": "reject alpha two"},
    # Canonical exact-pair repeat: stable-first must keep the first marker.
    {"user": "ALPHA PROMPT", "assistant": "reject  alpha one", "marker": "later"},
    {"user": "Beta prompt", "assistant": "reject beta one"},
    {"user": " beta prompt ", "assistant": "reject beta two"},
    {"user": "Gamma prompt", "assistant": "reject gamma"},
    {"user": "Delta prompt", "assistant": "reject delta"},
    {"user": "Epsilon prompt", "assistant": "reject epsilon"},
]
negative_train, negative_eval, split_stats = split_negative(
    negative_fixture, training_enabled=True
)
train_hashes = {
    row["_negative_prompt_group_sha256"] for row in negative_train
}
eval_hashes = {
    row["_negative_prompt_group_sha256"] for row in negative_eval
}
all_split_rows = negative_train + negative_eval
alpha_rows = [
    row
    for row in all_split_rows
    if split_namespace["normalize_negative_prompt"](row["user"]) == "alpha prompt"
]
check(
    "negative_prompt_groups_never_cross_and_pairs_dedupe_stably",
    not train_hashes.intersection(eval_hashes)
    and split_stats["duplicate_pairs_dropped"] == 1
    and len(alpha_rows) == 2
    and next(row for row in alpha_rows if row["assistant"] == "reject alpha one")[
        "marker"
    ]
    == "first"
    and split_stats["train_groups"] == len(train_hashes)
    and split_stats["eval_groups"] == len(eval_hashes),
    repr(split_stats),
)

reversed_train, reversed_eval, reversed_stats = split_negative(
    list(reversed(negative_fixture)), training_enabled=True
)
check(
    "negative_group_assignment_is_deterministic_and_balanced",
    split_stats["train_group_hashes"] == reversed_stats["train_group_hashes"]
    and split_stats["eval_group_hashes"] == reversed_stats["eval_group_hashes"]
    and abs(split_stats["train_rows"] - split_stats["eval_rows"])
    <= max(2, len(alpha_rows))
    and {
        row["_negative_prompt_group_sha256"] for row in reversed_train
    }.isdisjoint(
        {row["_negative_prompt_group_sha256"] for row in reversed_eval}
    ),
    repr(split_stats),
)

one_group = [
    {"user": "Only prompt", "assistant": "first rejection"},
    {"user": " only   PROMPT ", "assistant": "second rejection"},
]
small_train, small_eval, small_stats = split_negative(
    one_group, training_enabled=True
)
disabled_train, disabled_eval, disabled_stats = split_negative(
    negative_fixture, training_enabled=False
)
check(
    "negative_split_fails_closed_to_held_out",
    not small_train
    and len(small_eval) == 2
    and small_stats["held_out_all"] is True
    and "fewer than two" in small_stats["held_out_all_reason"]
    and not disabled_train
    and len(disabled_eval) == split_stats["usable_unique_pairs"]
    and disabled_stats["held_out_all"] is True,
    f"small={small_stats}; disabled={disabled_stats}",
)
schedule_nodes = [
    node
    for node in trainer_tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "budgeted_training_schedule"
]
schedule_module = ast.Module(body=schedule_nodes, type_ignores=[])
ast.fix_missing_locations(schedule_module)
schedule_namespace: dict[str, Any] = {}
exec(compile(schedule_module, str(TRAINER), "exec"), schedule_namespace)
scheduled_steps, scheduled_warmup = schedule_namespace["budgeted_training_schedule"](
    10_000.0, 0.0
)
check(
    "budgeted_schedule_matches_the_deadline",
    "def budgeted_training_schedule" in trainer_source
    and "max_steps=max_steps" in trainer_source
    and "warmup_steps=warmup_steps" in trainer_source
    and "gradient_accumulation_steps=2" in trainer_source
    and scheduled_steps == 170
    and scheduled_warmup == 8,
    f"steps={scheduled_steps} warmup={scheduled_warmup}",
)
check(
    "negative_split_evidence_is_written_to_summary",
    '"negative_split": negative_split' in trainer_source
    and '"negative_train_kept_group_hashes"' in trainer_source
    and '"negative_eval_kept_group_hashes"' in trainer_source
    and "_random.Random" not in trainer_source,
    "raw and post-sequence-filter group hashes are recorded; row shuffle is absent",
)

proof_source = PROOF_RUNNER.read_text(encoding="utf-8")
proof_tree = ast.parse(proof_source, filename=str(PROOF_RUNNER))
proof_functions = {
    node.name: node for node in proof_tree.body if isinstance(node, ast.FunctionDef)
}
preflight = proof_functions.get("preflight")
first_preflight_call = ""
if preflight and preflight.body and isinstance(preflight.body[0], ast.Assign):
    value = preflight.body[0].value
    if isinstance(value, ast.Call):
        first_preflight_call = call_name(value)
check(
    "proof_preflight_installs_canonical_first",
    first_preflight_call == "install_canonical_trainer"
    and 'CANONICAL_TRAINER = ROOT / "tools" / "engel_ct246_train_lora.py"'
    in proof_source,
    f"first preflight call={first_preflight_call or '<none>'}",
)
check(
    "trainer_install_is_atomic_and_hash_verified",
    "os.replace(temporary, target)" in proof_source
    and "os.fsync(writer.fileno())" in proof_source
    and "sha256_file(temporary) != source_hash" in proof_source
    and "installed_hash != source_hash" in proof_source,
    "stage hash, fsync, atomic replace, and installed hash are all present",
)

spec = importlib.util.spec_from_file_location("engel_lora_proof_static", PROOF_RUNNER)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {PROOF_RUNNER}")
proof: Any = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)
original_source = proof.CANONICAL_TRAINER
original_target = proof.TRAIN_SCRIPT
original_guard = proof.require_ct246_ssd_path
with tempfile.TemporaryDirectory(
    prefix="engel_canonical_lora_install_", dir=str(ROOT / "runtime" / "temp")
) as temp_name:
    temp = Path(temp_name)
    target = temp / "scripts" / "train_lora.py"
    target.parent.mkdir(parents=True)
    target.write_text("stale unreviewed trainer\n", encoding="utf-8")
    try:
        proof.CANONICAL_TRAINER = TRAINER
        proof.TRAIN_SCRIPT = target
        proof.require_ct246_ssd_path = lambda path: None
        first = proof.install_canonical_trainer()
        first_bytes = target.read_bytes()
        second = proof.install_canonical_trainer()
        expected_hash = hashlib.sha256(TRAINER.read_bytes()).hexdigest().upper()
        leftovers = list(target.parent.glob(".train_lora.py.*.tmp"))
        check(
            "atomic_installer_replaces_and_verifies_stale_target",
            first.get("installed") is True
            and first.get("verified") is True
            and first.get("canonical_sha256") == expected_hash
            and first.get("installed_sha256") == expected_hash
            and first_bytes == TRAINER.read_bytes()
            and not leftovers,
            repr(first),
        )
        check(
            "atomic_installer_is_idempotent",
            second.get("installed") is False
            and second.get("verified") is True
            and target.read_bytes() == first_bytes,
            repr(second),
        )
    finally:
        proof.CANONICAL_TRAINER = original_source
        proof.TRAIN_SCRIPT = original_target
        proof.require_ct246_ssd_path = original_guard

# Exercise the resume contract using only tiny local text fixtures. This neither
# imports the ML stack nor invokes a trainer, model, service, subprocess, or network.
with tempfile.TemporaryDirectory(
    prefix="engel_lora_pointer_contract_", dir=str(ROOT / "runtime" / "temp")
) as temp_name:
    temp = Path(temp_name)
    ct_root = (temp / "ct246").resolve()
    base_model = ct_root / "models-active" / "base"
    out_dir = ct_root / "proof_runs" / "run-1" / "out"
    adapter = out_dir / "adapter"
    merged = out_dir / "merged"
    reports = ct_root / "reports"
    pointers = ct_root / "adapters"
    for directory in (base_model, adapter, merged, reports, pointers):
        directory.mkdir(parents=True, exist_ok=True)
    (base_model / "config.json").write_text(
        '{"model_type":"fixture"}\n', encoding="utf-8"
    )
    (adapter / "adapter_model.safetensors").write_bytes(b"adapter-fixture-v1")
    (adapter / "adapter_config.json").write_text(
        '{"base_model_name_or_path":"fixture"}\n', encoding="utf-8"
    )
    (merged / "config.json").write_text(
        '{"model_type":"fixture-merged"}\n', encoding="utf-8"
    )
    summary_path = out_dir / "train_summary.json"
    summary_path.write_text('{"val_loss_delta":-0.1}\n', encoding="utf-8")
    receipt_path = reports / "ENGEL_CT246_LORA_PROOF_20260809T000000Z.json"
    pointer_path = pointers / "PROOF_LATEST.json"

    def temp_ct_guard(path: Path) -> None:
        resolved = Path(path).resolve(strict=False)
        try:
            resolved.relative_to(ct_root)
        except ValueError as exc:
            raise RuntimeError(f"refusing path outside fixture CT root: {resolved}") from exc

    proof.require_ct246_ssd_path = temp_ct_guard
    try:
        receipt: dict[str, Any] = {
            "schema": proof.PROOF_RECEIPT_SCHEMA,
            "ok": True,
            "artifact_status": "proven",
            "proof_pointer_advanced": True,
            "proof_gates": {
                "adapter_artifacts_verified": True,
                "evaluation_suite": True,
                "evaluation_artifacts_verified": True,
                "validation_loss_improved": True,
                "passed": True,
            },
            "run_stamp": "20260809T000000Z",
            "started_at_utc": "2026-08-09T00:00:00+00:00",
            "receipt_path": str(receipt_path),
            "base_model": str(base_model.resolve()),
            "adapter_lineage": 1,
            "resumed_from": None,
            "new_adapter_path": str(adapter.resolve()),
            "new_merged_path": str(merged.resolve()),
            "train_summary": {"adapter": str(adapter), "merged": str(merged)},
        }
        receipt["adapter_artifact_manifest"] = proof.artifact_hash_manifest(
            adapter,
            required_relative_paths=("adapter_model.safetensors",),
        )
        receipt["core_hashes"] = proof.core_hashes(
            receipt, base_model, summary_path
        )
        model_name = proof.engel_model_name(
            base_model,
            1,
            receipt["adapter_artifact_manifest"]["artifact_set_sha256"],
        )
        receipt["engel_model_name"] = model_name
        proof.finalize_model_card_artifacts(
            out_dir,
            model_name,
            receipt,
            base_model,
            artifact_status="proven",
        )
        proof.write_json(receipt_path, receipt)
        pointer = proof.adapter_pointer_payload(
            receipt,
            out_dir,
            base_model,
            model_name,
            artifact_status="proven",
        )
        proof.write_json(pointer_path, pointer)

        loaded = proof.load_proven_resume_pointer(pointer_path, base_model)
        check(
            "v3_proven_pointer_resumes_only_after_all_hashes_verify",
            loaded.get("adapter") == str(adapter.resolve())
            and loaded.get("lineage") == 1
            and loaded.get("hash_verified") is True
            and loaded.get("model_cards_hash_verified") is True
            and loaded.get("receipt_hash_verified") is True,
            repr(loaded),
        )

        card_path = adapter / proof.MODEL_CARD_NAME
        original_card = card_path.read_bytes()
        card_path.write_bytes(original_card + b"\n")
        card_error = runtime_error(
            lambda: proof.load_proven_resume_pointer(pointer_path, base_model)
        )
        card_path.write_bytes(original_card)
        check(
            "resume_rejects_model_card_rewrite_after_finalization",
            "model-card" in card_error,
            card_error or "pointer unexpectedly loaded",
        )

        original_receipt = receipt_path.read_bytes()
        receipt_path.write_bytes(original_receipt + b" ")
        receipt_error = runtime_error(
            lambda: proof.load_proven_resume_pointer(pointer_path, base_model)
        )
        receipt_path.write_bytes(original_receipt)
        check(
            "resume_rejects_mutated_stamped_receipt",
            "receipt sha256 binding mismatch" in receipt_error,
            receipt_error or "pointer unexpectedly loaded",
        )

        legacy_path = pointers / "LEGACY.json"
        proof.write_json(
            legacy_path,
            {"adapter": str(adapter), "model": str(base_model), "lineage": 1},
        )
        legacy_error = runtime_error(
            lambda: proof.load_proven_resume_pointer(legacy_path, base_model)
        )
        check(
            "resume_rejects_legacy_unhashed_pointer",
            "legacy/unversioned" in legacy_error,
            legacy_error or "pointer unexpectedly loaded",
        )

        unhashed = json.loads(json.dumps(pointer))
        unhashed.pop("run_receipt_sha256", None)
        unhashed["resume_bindings"].pop("run_receipt_sha256", None)
        unhashed_path = pointers / "UNHASHED.json"
        proof.write_json(unhashed_path, unhashed)
        unhashed_error = runtime_error(
            lambda: proof.load_proven_resume_pointer(unhashed_path, base_model)
        )
        check(
            "resume_rejects_v3_pointer_without_receipt_hash",
            "receipt sha256 binding mismatch" in unhashed_error,
            unhashed_error or "pointer unexpectedly loaded",
        )

        outside = temp / "outside-ct246"
        outside_adapter = outside / "adapter"
        outside_merged = outside / "merged"
        outside_adapter.mkdir(parents=True)
        outside_merged.mkdir(parents=True)
        off_root = json.loads(json.dumps(pointer))
        off_root["adapter"] = str(outside_adapter)
        off_root["merged"] = str(outside_merged)
        off_root_path = pointers / "OFF_ROOT.json"
        proof.write_json(off_root_path, off_root)
        off_root_error = runtime_error(
            lambda: proof.load_proven_resume_pointer(off_root_path, base_model)
        )
        check(
            "resume_rejects_adapter_paths_outside_ct246_root",
            "outside fixture CT root" in off_root_error,
            off_root_error or "pointer unexpectedly loaded",
        )

        missing_off_root = temp / "outside-missing-pointer.json"
        missing_pointer_error = runtime_error(
            lambda: proof.load_proven_resume_pointer(
                missing_off_root, base_model
            )
        )
        check(
            "resume_rejects_off_root_pointer_even_when_missing",
            "outside fixture CT root" in missing_pointer_error,
            missing_pointer_error or "off-root missing pointer was treated as fresh",
        )
    finally:
        proof.require_ct246_ssd_path = original_guard

cycle_source = CYCLE.read_text(encoding="utf-8")
cycle_tree = ast.parse(cycle_source, filename=str(CYCLE))
tool_files: tuple[str, ...] = ()
for node in cycle_tree.body:
    if not isinstance(node, ast.Assign):
        continue
    if not any(isinstance(target, ast.Name) and target.id == "CT_TOOL_FILES" for target in node.targets):
        continue
    value = ast.literal_eval(node.value)
    if isinstance(value, tuple):
        tool_files = value
check(
    "training_cycle_pushes_canonical_trainer",
    "engel_ct246_train_lora.py" in tool_files,
    repr(tool_files),
)

for name, ok, detail in checks:
    print(f"{'PASS' if ok else 'FAIL'} {name} :: {detail}")
failed = [name for name, ok, _ in checks if not ok]
print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
print(
    "verify_engel_ct246_canonical_lora_trainer: "
    + ("GREEN" if not failed else "RED")
)
raise SystemExit(1 if failed else 0)
