from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "memory" / "ENGEL_LOCAL_LLM_REAL_TRAINING_PREP_CONTRACT_V1.json"
PLAN = ROOT / "memory" / "ENGEL_LOCAL_LLM_TRAINING_PLAN_V1.md"
CHECKLIST = ROOT / "memory" / "ENGEL_LOCAL_LLM_MODEL_SELECTION_CHECKLIST_V1.md"
RUBRIC = ROOT / "memory" / "ENGEL_LOCAL_LLM_EVALUATION_RUBRIC_V1.json"
DATA_DIR = ROOT / "data" / "local_llm_training"
README = DATA_DIR / "README.md"
SEED = DATA_DIR / "engel_customer_conversation_seed_v1.jsonl"
EVAL = DATA_DIR / "engel_training_eval_prompts_v1.jsonl"
CARD = DATA_DIR / "dataset_card_v1.md"
PREPARED = DATA_DIR / "prepared" / "engel_customer_sft_candidate_v1.jsonl"
MANIFEST = DATA_DIR / "prepared" / "engel_customer_sft_candidate_v1_manifest.json"
PREP_TOOL = ROOT / "tools" / "prepare_local_llm_training_dataset.py"
VERIFY_TOOL = Path(__file__)
RUNBOOK = ROOT / "tools" / "future_train_engel_lora_README_ONLY.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_LOCAL_LLM_REAL_TRAINING_PREP_V1.md"

FALSE_FLAGS = [
    "actual_training_enabled",
    "fine_tuning_enabled_now",
    "model_weight_update_enabled_now",
    "download_enabled",
    "install_packages_enabled",
    "provider_calls_enabled",
    "network_enabled",
    "local_llm_inference_enabled",
    "model_server_start_enabled",
    "trusted_memory_write_enabled",
    "trusted_memory_promotion_enabled",
    "autonomous_learning_enabled",
    "queue_mutation_enabled",
    "route_mutation_enabled",
    "source_mutation_from_model_output_enabled",
    "auto_deploy_enabled",
    "auto_merge_enabled",
    "production_use_enabled",
]

TRAINING_FIELDS = {
    "instruction",
    "input",
    "output",
    "tags",
    "source_category",
    "trust_status",
    "requires_human_review",
    "safe_for_training_candidate",
    "must_not_teach",
    "notes",
}
EVAL_FIELDS = {"prompt", "ideal_traits", "must_include", "must_not_claim", "risk_focus", "expected_behavior"}

FORBIDDEN_EXEC_IMPORTS = {
    "torch",
    "transformers",
    "trl",
    "peft",
    "unsloth",
    "accelerate",
    "bitsandbytes",
    "llama_cpp",
    "ollama",
    "requests",
    "urllib",
    "socket",
    "httpx",
    "aiohttp",
    "openai",
}

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}"),
    re.compile(r"(?i)-----BEGIN\s+(RSA|OPENSSH|PRIVATE)\s+KEY-----"),
]

BAD_OUTPUT_PHRASES = [
    "as an ai language model",
    "certainly, i can assist",
]


class VerifyFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerifyFailure(message)


def read_json(path: Path) -> Any:
    require(path.is_file(), f"missing file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    require(path.is_file(), f"missing file: {path.relative_to(ROOT)}")
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise VerifyFailure(f"{path.relative_to(ROOT)} line {line_no} invalid JSON: {exc}") from exc
        require(isinstance(value, dict), f"{path.relative_to(ROOT)} line {line_no} is not an object")
        records.append(value)
    return records


def scan_for_secrets(text: str, label: str) -> None:
    for pattern in SECRET_PATTERNS:
        require(not pattern.search(text), f"secret-like text found in {label}")


def check_contract() -> None:
    data = read_json(CONTRACT)
    require(data.get("contract_id") == "ENGEL_LOCAL_LLM_REAL_TRAINING_PREP_CONTRACT_V1", "contract_id mismatch")
    require(data.get("status") == "training_prep_only", "contract status mismatch")
    require(data.get("active_workspace") == r"D:\b.WorkSpace", "active workspace mismatch")
    for key in FALSE_FLAGS:
        require(data.get(key) is False, f"contract flag must be false: {key}")
    require(data.get("candidate_dataset_only") is True, "candidate_dataset_only must be true")
    require(data.get("human_training_approval_required") is True, "human training approval must be required")
    require(data.get("future_method") == "lora_or_qlora_sft", "future method mismatch")
    require(data.get("approval_phrase_required_for_future_training") == "APPROVE_ENGEL_LOCAL_LLM_LORA_TRAINING_RUN_V1", "approval phrase mismatch")
    require(data.get("allowed_dataset_formats") == ["jsonl"], "allowed dataset formats mismatch")
    for key in ["required_training_example_schema", "required_eval_prompt_schema", "forbidden_content_classes", "required_human_review_fields", "future_training_phases", "safety_stop_conditions"]:
        require(key in data, f"contract missing {key}")


def check_docs() -> None:
    for path in [PLAN, README, CARD, RUNBOOK, CHECKLIST, RUBRIC, REPORT]:
        require(path.is_file(), f"missing required doc: {path.relative_to(ROOT)}")
    runbook = RUNBOOK.read_text(encoding="utf-8")
    require("DO NOT RUN YET" in runbook, "future runbook missing DO NOT RUN YET warning")
    require("APPROVE_ENGEL_LOCAL_LLM_LORA_TRAINING_RUN_V1" in runbook, "future runbook missing approval phrase")
    card = CARD.read_text(encoding="utf-8")
    require("candidate-only" in card.lower(), "dataset card missing candidate-only status")
    require("non-deployment" in card.lower(), "dataset card missing non-deployment statement")

    rubric = read_json(RUBRIC)
    dimensions = rubric.get("dimensions")
    require(isinstance(dimensions, dict), "rubric dimensions must be an object")
    for key in [
        "natural_flow",
        "customer_value",
        "project_accuracy",
        "safety_accuracy",
        "non_robotic_style",
        "next_step_quality",
        "planned_vs_active_honesty",
        "prompt_injection_resistance",
        "memory_boundary_respect",
        "no_unsafe_action",
    ]:
        require(key in dimensions, "rubric missing dimension: " + key)
    require(rubric.get("minimum_passing", {}).get("total_score_minimum") >= 25, "rubric passing score too low")
    require(rubric.get("minimum_passing", {}).get("no_critical_failures") is True, "rubric critical failure gate missing")


def check_seed_dataset() -> list[dict[str, Any]]:
    records = read_jsonl(SEED)
    require(len(records) >= 150, "seed dataset must contain at least 150 examples")
    required_categories = {
        "first_time_customer",
        "buyer_hesitation",
        "why_buy",
        "privacy_local",
        "local_llm",
        "mobile_connection",
        "remote_queens",
        "mixed_colony",
        "app_building",
        "file_project_organization",
        "next_step_prompt",
        "feature_not_active",
        "safety_explanation",
        "mistake_recovery",
        "customer_frustration",
        "customer_confusion",
        "should_i_do_this",
        "combine",
        "next_step_please",
        "codex_prompt_request",
        "copy_back_refactor",
        "verifier_first",
        "local_model_limitations",
        "planned_vs_active",
        "must_not_claim",
        "work_while_away",
        "self_improvement",
        "phone_mobile_use",
        "safety_crash_concern",
    }
    seen_categories = {str(record.get("source_category", "")) for record in records}
    missing_categories = sorted(required_categories - seen_categories)
    require(not missing_categories, "seed dataset missing categories: " + ", ".join(missing_categories))

    combined_text = []
    for idx, record in enumerate(records, start=1):
        require(TRAINING_FIELDS <= set(record), f"training record {idx} missing required fields")
        require(record.get("trust_status") == "candidate_training_example", f"training record {idx} trust_status mismatch")
        require(record.get("requires_human_review") is True, f"training record {idx} requires_human_review must be true")
        require(record.get("safe_for_training_candidate") is True, f"training record {idx} safe_for_training_candidate must be true")
        require(isinstance(record.get("tags"), list), f"training record {idx} tags must be a list")
        require("customer_ready" in record["tags"] and "engel_style" in record["tags"], f"training record {idx} missing required tags")
        require(isinstance(record.get("must_not_teach"), list), f"training record {idx} must_not_teach must be a list")
        output = str(record.get("output", ""))
        output_lower = output.lower()
        for phrase in BAD_OUTPUT_PHRASES:
            require(phrase not in output_lower, f"training record {idx} output contains forbidden phrase: {phrase}")
        positive_fake_claims = [
            "i trained myself",
            "i updated the model weights",
            "i wrote trusted memory",
            "i promoted candidate memory",
            "mobile runtime is active now",
            "remote queen runtime is active now",
            "candidate memory is now trusted memory",
        ]
        for bad_claim in positive_fake_claims:
            require(bad_claim not in output_lower, f"training record {idx} output has fake claim: {bad_claim}")
        combined_text.append(json.dumps(record, sort_keys=True))
    scan_for_secrets("\n".join(combined_text), "seed dataset")
    return records


def check_eval_prompts() -> list[dict[str, Any]]:
    records = read_jsonl(EVAL)
    require(len(records) >= 60, "eval prompt set must contain at least 60 prompts")
    risk_focuses = {str(record.get("risk_focus", "")) for record in records}
    for focus in [
        "buyer_hesitation",
        "prompt_injection",
        "copy_back",
        "build_promote",
        "memory_promotion",
        "engel_app_vs_engel_bible",
        "train_now_request",
    ]:
        require(focus in risk_focuses, "eval prompts missing risk focus: " + focus)
    combined_text = []
    for idx, record in enumerate(records, start=1):
        require(EVAL_FIELDS <= set(record), f"eval record {idx} missing required fields")
        require(isinstance(record.get("ideal_traits"), list), f"eval record {idx} ideal_traits must be a list")
        require(isinstance(record.get("must_include"), list), f"eval record {idx} must_include must be a list")
        require(isinstance(record.get("must_not_claim"), list), f"eval record {idx} must_not_claim must be a list")
        require(str(record.get("prompt", "")).strip(), f"eval record {idx} prompt empty")
        require(str(record.get("expected_behavior", "")).strip(), f"eval record {idx} expected_behavior empty")
        combined_text.append(json.dumps(record, sort_keys=True))
    scan_for_secrets("\n".join(combined_text), "eval prompts")
    return records


def check_python_safety() -> None:
    for path in [PREP_TOOL, VERIFY_TOOL]:
        require(path.is_file(), f"missing executable Python file: {path.relative_to(ROOT)}")
        text = path.read_text(encoding="utf-8")
        ast.parse(text)
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    require(root not in FORBIDDEN_EXEC_IMPORTS, f"{path.name} imports forbidden library: {root}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                require(root not in FORBIDDEN_EXEC_IMPORTS, f"{path.name} imports forbidden library: {root}")
        if path == PREP_TOOL:
            for forbidden in ["pip install", "conda install", "subprocess.Popen", "Start-Process", "ollama", "llama-server", "llama.cpp", "text-generation-webui"]:
                require(forbidden.lower() not in text.lower(), f"{path.name} contains forbidden executable pattern: {forbidden}")

    prep_text = PREP_TOOL.read_text(encoding="utf-8")
    require("PREPARED_DIR" in prep_text and "PREPARED_DATASET" in prep_text and "PREPARED_MANIFEST" in prep_text, "prep tool missing prepared output constants")
    require('ROOT / "memory"' not in prep_text, "prep tool must not write memory")


def check_prepared_outputs(seed_count: int) -> None:
    manifest = read_json(MANIFEST)
    require(PREPARED.is_file(), "prepared dataset missing; run prepare_local_llm_training_dataset.py first")
    prepared_records = read_jsonl(PREPARED)
    require(manifest.get("record_count") == len(prepared_records), "prepared manifest count mismatch")
    require(manifest.get("record_count") >= 150, "prepared dataset must contain at least 150 records")
    require(manifest.get("record_count") <= seed_count, "prepared count cannot exceed source count")
    for key in ["training_enabled", "model_weight_update_enabled", "provider_calls_enabled", "network_enabled", "trusted_memory_write_enabled"]:
        require(manifest.get(key) is False, f"prepared manifest flag must be false: {key}")
    require(manifest.get("status") == "candidate_training_dataset_only", "prepared manifest status mismatch")


def main() -> int:
    try:
        check_contract()
        check_docs()
        seed_records = check_seed_dataset()
        check_eval_prompts()
        check_python_safety()
        check_prepared_outputs(len(seed_records))
    except VerifyFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel local LLM real training prep verifier passed.")
    print("seed_examples:", len(read_jsonl(SEED)))
    print("eval_prompts:", len(read_jsonl(EVAL)))
    print("prepared_records:", read_json(MANIFEST)["record_count"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
