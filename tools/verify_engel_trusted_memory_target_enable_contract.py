from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]

CONTRACT_ID = "ENGEL_TRUSTED_MEMORY_TARGET_ENABLE_CONTRACT_V1"
PASS_MARKER = "ENGEL_TRUSTED_MEMORY_TARGET_ENABLE_CONTRACT_VERIFICATION_PASS"

CONTRACT_JSON = ROOT / "memory" / "ENGEL_TRUSTED_MEMORY_TARGET_ENABLE_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_TRUSTED_MEMORY_TARGET_ENABLE_CONTRACT_V1.md"
CONTRACT_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_TRUSTED_MEMORY_TARGET_ENABLE_CONTRACT_V1.md"

TARGET_CONTRACT_JSON = ROOT / "memory" / "ENGEL_TRUSTED_MEMORY_TARGET_CONTRACT_V1.json"
TARGET_MODULE = ROOT / "engel_trusted_memory_target.py"
PROMOTION_WRITER = ROOT / "engel_memory_promotion_writer.py"
APP_MODULE = ROOT / "engel_app.py"
ROUTE_METADATA = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"

EXPECTED_WORKSPACE = r"D:\b.WorkSpace\Engel App"
TARGET_PATH = r"memory\ENGEL_TRUSTED_MEMORY_V1.jsonl"
ENABLE_PHRASE = "APPROVE_TRUSTED_MEMORY_TARGET_ENABLE_V1"
ENABLE_PASSWORD_ACTION = "enable_trusted_memory_target"
PROMOTION_TOKEN = "APPROVE_PROMOTE_MEMORY_CANDIDATE"
PROMOTION_PASSWORD_ACTION = "promote_memory_candidate"

FALSE_ENABLE_FLAGS = [
    "trusted_memory_target_enabled_now",
    "general_memory_promotion_enabled_now",
    "trusted_memory_target_implemented_now",
    "source_mutation_enabled_now",
    "route_mutation_enabled_now",
    "queue_mutation_enabled_now",
    "provider_api_enabled_now",
    "network_enabled_now",
    "local_llm_inference_enabled_now",
    "background_worker_enabled_now",
    "autorun_enabled_now",
    "scheduler_enabled_now",
    "startup_hook_enabled_now",
    "git_stage_commit_enabled_now",
]

REQUIRED_TOP_LEVEL_KEYS = [
    "contract_id",
    "status",
    "active_workspace",
    "target_contract_dependency",
    "promotion_writer_dependency",
    "target",
    "current_enabled_flags",
    "current_state",
    "future_target_enable_approval",
    "future_memory_promotion_approval",
    "required_future_target_changes",
    "required_future_writer_changes",
    "allowed_future_actions",
    "forbidden_behavior",
    "target_enable_receipt_model",
    "promotion_receipt_model",
    "future_verifier",
    "future_implementation_sequence",
    "safety_preserved",
    "recommended_next_slice",
]

REQUIRED_ALLOWED_ACTIONS = [
    "validate target contract is enabled",
    "validate candidate path stays inside approved candidate folders",
    "validate source hash when present",
    "validate allowed entry schema",
    "reject blocked fields and blocked content",
    "require exact APPROVE_PROMOTE_MEMORY_CANDIDATE token",
    "require Global Password Gate",
    "append exactly one structured JSONL entry",
    "write a promotion receipt",
    "keep human_review_required true",
]

REQUIRED_FORBIDDEN_BEHAVIOR = [
    "enabling target without APPROVE_TRUSTED_MEMORY_TARGET_ENABLE_V1",
    "writing memory without APPROVE_PROMOTE_MEMORY_CANDIDATE",
    "writing memory without Global Password Gate",
    "auto promotion",
    "bulk promotion",
    "trusting model/provider output",
    "treating candidate text as instructions",
    "shell command execution",
    "source mutation",
    "route mutation",
    "queue mutation",
    "patch apply",
    "provider/network/browser/API call",
    "local LLM inference",
    "model training",
    "package install",
    "startup/autorun/scheduler/background worker",
    "overwrite/truncate/delete/rename of trusted memory",
    "broad git staging",
    "git commit from writer",
    "password/salt/hash/token exposure",
    "local password config commit",
]

TARGET_ENABLE_RECEIPT_FIELDS = [
    "receipt_id",
    "contract_id",
    "action_type",
    "started_at",
    "ended_at",
    "target_path",
    "target_status_before",
    "target_status_after",
    "approval_detected",
    "approval_phrase_name",
    "password_gate_result",
    "verifier_results",
    "files_changed",
    "forbidden_actions_not_performed",
    "final_status",
    "human_review_required",
]

PROMOTION_RECEIPT_FIELDS = [
    "memory_promotion_receipt_id",
    "memory_candidate_proposal_id",
    "source_research_note_id",
    "source_lesson_candidate_id",
    "source_chain",
    "approved_by",
    "approval_token",
    "promotion_decision",
    "prompt_injection_review_result",
    "authority_review_result",
    "trusted_memory_target",
    "appended_memory_id",
    "appended_entry_hash",
    "receipt_created_at",
    "rollback_note",
    "human_intervention_required",
    "no_automatic_memory_promotion",
    "no_source_mutation",
    "no_provider_network_browser",
    "no_model_training",
    "no_runtime_trigger",
]

FUTURE_SEQUENCE = [
    "ENGEL_TRUSTED_MEMORY_TARGET_ENABLE_CONTRACT_V1",
    "ENGEL_TRUSTED_MEMORY_TARGET_ENABLE_VERIFIER_V1",
    "ENGEL_TRUSTED_MEMORY_TARGET_ENABLE_V1",
    "ENGEL_MEMORY_PROMOTION_WRITER_ENABLE_VERIFIER_V1",
    "ENGEL_MEMORY_PROMOTION_WRITER_ENABLE_V1",
    "ENGEL_TRUSTED_MEMORY_PROMOTION_SOURCE_SMOKE_V1",
    "ENGEL_TRUSTED_MEMORY_TARGET_ENABLE_CLOSEOUT_REVIEW_V1",
]

SECRET_KEY_PATTERNS = [
    '"raw_password"',
    '"password_hash"',
    '"password_salt"',
    '"secret_value"',
    '"api_key"',
    '"private_key"',
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise CheckFailure(f"invalid JSON: {path.relative_to(ROOT)}: {exc}") from exc
    require(isinstance(data, dict), f"JSON root must be object: {path.relative_to(ROOT)}")
    return data


def normalize_items(value: Any) -> list[str]:
    if isinstance(value, dict):
        items: list[str] = []
        for key, child in value.items():
            items.append(str(key))
            items.extend(normalize_items(child))
        return items
    if isinstance(value, list):
        items = []
        for child in value:
            items.extend(normalize_items(child))
        return items
    return [str(value)]


def require_string_present(section: Any, expected: str, label: str) -> None:
    haystack = "\n".join(normalize_items(section)).lower()
    require(expected.lower() in haystack, f"{label} missing: {expected}")


def require_list_contains_all(section: Any, expected_items: list[str], label: str) -> None:
    for item in expected_items:
        require_string_present(section, item, label)


def parse_constants(path: Path) -> dict[str, Any]:
    tree = ast.parse(read_text(path))
    values: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        try:
            values[node.targets[0].id] = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            continue
    return values


def check_required_files() -> None:
    for path in [
        CONTRACT_JSON,
        CONTRACT_MD,
        CONTRACT_REPORT,
        TARGET_CONTRACT_JSON,
        TARGET_MODULE,
        PROMOTION_WRITER,
    ]:
        require(path.exists() and path.is_file(), f"missing required file: {path.relative_to(ROOT)}")


def check_contract_identity() -> None:
    data = load_json(CONTRACT_JSON)
    md = read_text(CONTRACT_MD)
    report = read_text(CONTRACT_REPORT)
    for key in REQUIRED_TOP_LEVEL_KEYS:
        require(key in data, f"contract JSON missing key: {key}")
    require(data.get("contract_id") == CONTRACT_ID, "contract_id mismatch")
    require(data.get("status") == "contract_only", "status must be contract_only")
    require(data.get("active_workspace") == EXPECTED_WORKSPACE, "active_workspace mismatch")
    require(data.get("target_contract_dependency") == "ENGEL_TRUSTED_MEMORY_TARGET_CONTRACT_V1", "target dependency mismatch")
    require(data.get("promotion_writer_dependency") == "ENGEL_MEMORY_PROMOTION_WRITER_V1", "writer dependency mismatch")
    for text in [md, report]:
        require(CONTRACT_ID in text, "contract id missing from Markdown/report")
        require(TARGET_PATH in text, "target path missing from Markdown/report")
        require(ENABLE_PHRASE in text, "enable phrase missing from Markdown/report")
        require(PROMOTION_TOKEN in text, "promotion token missing from Markdown/report")


def check_current_enabled_flags() -> None:
    flags = load_json(CONTRACT_JSON).get("current_enabled_flags", {})
    require(isinstance(flags, dict), "current_enabled_flags must be object")
    for key in FALSE_ENABLE_FLAGS:
        require(flags.get(key) is False, f"current flag must be false: {key}")
    require(flags.get("direct_training_memory_exception_enabled_now") is True, "direct training exception flag must remain true")


def check_target_model() -> None:
    data = load_json(CONTRACT_JSON)
    target = data.get("target", {})
    require(isinstance(target, dict), "target must be object")
    require(target.get("target_id") == "engel_trusted_memory_v1_jsonl", "target_id mismatch")
    require(target.get("target_path") == TARGET_PATH, "target_path mismatch")
    require(target.get("target_format") == "jsonl", "target_format must be jsonl")
    require(target.get("allowed_write_mode") == "append_only", "allowed_write_mode must be append_only")
    require(target.get("append_only") is True, "append_only must be true")
    require(target.get("max_entry_size") == 8192, "max_entry_size must be 8192")


def check_current_state() -> None:
    state = load_json(CONTRACT_JSON).get("current_state", {})
    require(isinstance(state, dict), "current_state must be object")
    require(state.get("target_status_now") == "disabled_until_human_target_approval", "current target status mismatch")
    require(state.get("writer_target_status_now") == "APPROVED_TRUSTED_MEMORY_TARGET_UNCLEAR", "current writer status mismatch")
    require(state.get("promotion_allowed_now") is False, "general promotion must remain disabled now")
    require(state.get("direct_training_memory_exception_enabled_now") is True, "direct training exception state mismatch")


def check_future_approval_models() -> None:
    data = load_json(CONTRACT_JSON)
    enable = data.get("future_target_enable_approval", {})
    require(isinstance(enable, dict), "future_target_enable_approval must be object")
    require(enable.get("approval_phrase") == ENABLE_PHRASE, "enable approval phrase mismatch")
    require(enable.get("password_gate_action") == ENABLE_PASSWORD_ACTION, "enable password gate action mismatch")
    require(enable.get("password_gate_result") == "redacted", "enable password gate result must be redacted")
    require(enable.get("verifier_required") is True, "enable verifier must be required")
    require(enable.get("enable_receipt_required") is True, "enable receipt must be required")
    require(enable.get("human_review_required") is True, "enable human review must be required")
    require(enable.get("does_not_approve_individual_memory_candidates") is True, "enable must not approve individual candidates")

    promotion = data.get("future_memory_promotion_approval", {})
    require(isinstance(promotion, dict), "future_memory_promotion_approval must be object")
    require(promotion.get("approval_token") == PROMOTION_TOKEN, "promotion approval token mismatch")
    require(promotion.get("password_gate_action") == PROMOTION_PASSWORD_ACTION, "promotion password gate action mismatch")
    for key in [
        "structured_candidate_required",
        "prompt_injection_review_required",
        "authority_hierarchy_review_required",
        "source_chain_review_required",
        "receipt_required",
        "append_only_jsonl_write",
        "human_review_required",
    ]:
        require(promotion.get(key) is True, f"promotion gate must be true: {key}")


def check_required_future_changes() -> None:
    data = load_json(CONTRACT_JSON)
    target_changes = data.get("required_future_target_changes", {})
    require(isinstance(target_changes, dict), "required_future_target_changes must be object")
    require(target_changes.get("file") == r"memory\ENGEL_TRUSTED_MEMORY_TARGET_CONTRACT_V1.json", "future target-change file mismatch")
    allowed = target_changes.get("allowed_field_changes", {})
    require(isinstance(allowed, dict), "allowed_field_changes must be object")
    require(allowed.get("target.status") == "enabled_for_password_gated_candidate_promotion", "future target.status mismatch")
    require(allowed.get("target.enabled") is True, "future target.enabled must be true")
    require(allowed.get("target.enablement_receipt_path") == "required", "future receipt path must be required")
    require(allowed.get("target.enabled_by_contract") == CONTRACT_ID, "future enabled_by_contract mismatch")
    require_list_contains_all(
        target_changes.get("must_preserve", []),
        [
            "target_path",
            "target_format",
            "allowed_write_mode",
            "append_only",
            "max_entry_size",
            "direct_training_memory_exception",
            "blocked_entry_fields",
            "blocked_content_patterns",
        ],
        "future target preserve list",
    )

    writer_changes = data.get("required_future_writer_changes", {})
    require(isinstance(writer_changes, dict), "required_future_writer_changes must be object")
    future_constants = writer_changes.get("future_constants", {})
    require(isinstance(future_constants, dict), "future_constants must be object")
    require(future_constants.get("TRUSTED_MEMORY_TARGET_IMPLEMENTED") is True, "future writer implementation flag must be documented true")
    require(
        future_constants.get("TRUSTED_MEMORY_TARGET_STATUS") == "ENABLED_FOR_PASSWORD_GATED_CANDIDATE_PROMOTION",
        "future writer status mismatch",
    )
    require(future_constants.get("TRUSTED_MEMORY_TARGET") == TARGET_PATH, "future writer target path mismatch")
    require(writer_changes.get("write_mode") == "append_only", "future writer write mode must be append_only")
    require_list_contains_all(
        writer_changes.get("forbidden_file_modes", []),
        ["overwrite", "truncate", "delete", "rename", "rewrite", "bulk_import"],
        "future writer forbidden modes",
    )


def check_allowed_forbidden_and_receipts() -> None:
    data = load_json(CONTRACT_JSON)
    require_list_contains_all(data.get("allowed_future_actions", []), REQUIRED_ALLOWED_ACTIONS, "allowed future actions")
    require_list_contains_all(data.get("forbidden_behavior", []), REQUIRED_FORBIDDEN_BEHAVIOR, "forbidden behavior")

    enable_receipt = data.get("target_enable_receipt_model", {})
    require(isinstance(enable_receipt, dict), "target_enable_receipt_model must be object")
    require(enable_receipt.get("receipt_folder") == "reports\\memory_promotion_receipts\\", "target enable receipt folder mismatch")
    require(enable_receipt.get("password_gate_result_must_be_redacted") is True, "target enable receipt password gate must be redacted")
    require_list_contains_all(enable_receipt.get("required_fields", []), TARGET_ENABLE_RECEIPT_FIELDS, "target enable receipt fields")

    promotion_receipt = data.get("promotion_receipt_model", {})
    require(isinstance(promotion_receipt, dict), "promotion_receipt_model must be object")
    require(promotion_receipt.get("receipt_folder") == "reports\\memory_promotion_receipts\\", "promotion receipt folder mismatch")
    require_list_contains_all(promotion_receipt.get("required_fields", []), PROMOTION_RECEIPT_FIELDS, "promotion receipt fields")
    require_list_contains_all(
        promotion_receipt.get("must_never_contain", []),
        ["raw password", "password hash", "password salt", "token secret values", "unredacted local secret config"],
        "promotion receipt prohibited secret list",
    )


def check_future_verifier_and_sequence() -> None:
    data = load_json(CONTRACT_JSON)
    verifier = data.get("future_verifier", {})
    require(isinstance(verifier, dict), "future_verifier must be object")
    require(verifier.get("path") == r"tools\verify_engel_trusted_memory_target_enable_contract.py", "future verifier path mismatch")
    require(verifier.get("pass_marker") == PASS_MARKER, "future verifier pass marker mismatch")
    require_list_contains_all(
        verifier.get("checks", []),
        [
            "contract exists and parses",
            "current enabled flags are false for this contract slice",
            "target path is exactly memory\\ENGEL_TRUSTED_MEMORY_V1.jsonl",
            "target enable approval phrase is documented",
            "per-memory promotion approval token remains separate",
            "allowed and forbidden behavior are documented",
            "target-enable receipt model is documented",
            "promotion receipt model is documented",
            "current target remains disabled before implementation",
            "no general trusted-memory promotion is enabled yet",
            "password/salt/hash values are not exposed",
        ],
        "future verifier checks",
    )
    require(data.get("future_implementation_sequence") == FUTURE_SEQUENCE, "future implementation sequence mismatch")
    require(data.get("recommended_next_slice") == "ENGEL_TRUSTED_MEMORY_TARGET_ENABLE_VERIFIER_V1", "recommended next slice mismatch")


def check_current_target_contract_still_disabled() -> None:
    data = load_json(TARGET_CONTRACT_JSON)
    target = data.get("target", {})
    require(isinstance(target, dict), "current target contract target must be object")
    require(target.get("target_path") == TARGET_PATH, "current target path mismatch")
    require(target.get("target_format") == "jsonl", "current target format mismatch")
    require(target.get("allowed_write_mode") == "append_only", "current target write mode mismatch")
    require(target.get("append_only") is True, "current target append_only mismatch")
    require(target.get("enabled") is False, "current target must still be disabled")
    require(target.get("status") == "disabled_until_human_target_approval", "current target status must still be disabled")
    boundary = data.get("safety_boundary", {})
    require(isinstance(boundary, dict), "current target safety_boundary must be object")
    require(boundary.get("trusted_memory_write_enabled_now") is False, "current trusted memory write flag must remain false")
    exception = data.get("direct_training_memory_exception", {})
    require(isinstance(exception, dict), "direct training exception must be object")
    require(exception.get("general_candidate_promotion_still_blocked") is True, "general candidate promotion must remain blocked")


def check_target_runtime_status() -> None:
    result = subprocess.run(
        [sys.executable, str(TARGET_MODULE), "--json"],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    require(result.returncode == 0, "trusted memory target --json failed")
    payload = json.loads(result.stdout)
    require(payload.get("promotion_allowed") is False, "runtime promotion_allowed must remain false")
    require(payload.get("write_blocked_reason") == "disabled_until_human_target_approval", "runtime blocked reason mismatch")
    target = payload.get("target", {})
    require(isinstance(target, dict), "runtime target must be object")
    require(target.get("target_path") == TARGET_PATH, "runtime target path mismatch")
    require(target.get("enabled") is False, "runtime target enabled flag must remain false")


def check_promotion_writer_still_blocked() -> None:
    source = read_text(PROMOTION_WRITER)
    constants = parse_constants(PROMOTION_WRITER)
    require(constants.get("TRUSTED_MEMORY_TARGET_IMPLEMENTED") is False, "writer target implementation must remain false")
    require(constants.get("TRUSTED_MEMORY_TARGET_STATUS") == "APPROVED_TRUSTED_MEMORY_TARGET_UNCLEAR", "writer target status mismatch")
    require(constants.get("TRUSTED_MEMORY_TARGET") == "STOPPED_UNCLEAR_APPROVED_TRUSTED_MEMORY_LOCATION", "writer current target must remain stopped/unclear")
    require("TRUSTED_MEMORY_TARGET_IMPLEMENTED = True" not in source, "writer must not contain active trusted-memory target flag yet")
    require("READY_FOR_BOUNDED_MEMORY_WRITE" in source, "writer should still document bounded future write decision")
    require("No trusted memory is written" in source, "writer must still document stopped memory write boundary")
    require("write_text(" in source, "writer should only write stopped receipts at this stage")
    require("APPROVE_PROMOTE_MEMORY_CANDIDATE" in source, "writer must retain per-memory promotion token")
    require("promote_memory_candidate" in source, "writer must retain per-memory password action")


def check_no_active_enable_route() -> None:
    if APP_MODULE.exists():
        app_text = read_text(APP_MODULE)
        require(ENABLE_PHRASE not in app_text, "engel_app.py must not expose target-enable phrase route yet")
        require(ENABLE_PASSWORD_ACTION not in app_text, "engel_app.py must not call target-enable password action yet")
    if ROUTE_METADATA.exists():
        route_text = read_text(ROUTE_METADATA)
        require(ENABLE_PHRASE not in route_text, "route metadata must not expose target-enable route yet")
        require(ENABLE_PASSWORD_ACTION not in route_text, "route metadata must not enable target-enable action yet")


def check_no_secret_values_in_contract_artifacts() -> None:
    for path in [CONTRACT_JSON, CONTRACT_MD, CONTRACT_REPORT]:
        text = read_text(path)
        for pattern in SECRET_KEY_PATTERNS:
            require(pattern not in text, f"secret-like key pattern found in {path.relative_to(ROOT)}: {pattern}")


def check_safety_preserved_section() -> None:
    safety = load_json(CONTRACT_JSON).get("safety_preserved", [])
    require_list_contains_all(
        safety,
        [
            "contract only",
            "no target enabled now",
            "no general memory promotion enabled now",
            "no trusted-memory append in this slice",
            "no source/route/queue mutation",
            "no provider/network/model/local LLM",
            "no background/autorun/scheduler",
            "no git staging or commit",
            "no password/salt/hash exposed",
            "local password config not committed",
        ],
        "safety preserved",
    )


def run_checks(checks: list[tuple[str, Callable[[], None]]]) -> int:
    failures: list[str] = []
    for label, check in checks:
        try:
            check()
        except CheckFailure as exc:
            failures.append(f"{label}: {exc}")
            print(f"[FAIL] {label}: {exc}")
        except Exception as exc:  # defensive verifier boundary
            failures.append(f"{label}: unexpected error: {exc}")
            print(f"[FAIL] {label}: unexpected error: {exc}")
        else:
            print(f"[PASS] {label}")
    if failures:
        print("[FAIL] trusted memory target enable contract verification failed.")
        return 1
    print("[INFO] target enable action remains future-only; general trusted-memory promotion is still disabled.")
    print(PASS_MARKER)
    return 0


def main() -> int:
    checks = [
        ("required files", check_required_files),
        ("contract identity", check_contract_identity),
        ("current enabled flags", check_current_enabled_flags),
        ("target model", check_target_model),
        ("current state", check_current_state),
        ("future approval models", check_future_approval_models),
        ("required future changes", check_required_future_changes),
        ("allowed forbidden and receipts", check_allowed_forbidden_and_receipts),
        ("future verifier and sequence", check_future_verifier_and_sequence),
        ("current target contract still disabled", check_current_target_contract_still_disabled),
        ("target runtime status", check_target_runtime_status),
        ("promotion writer still blocked", check_promotion_writer_still_blocked),
        ("no active enable route", check_no_active_enable_route),
        ("no secret values in contract artifacts", check_no_secret_values_in_contract_artifacts),
        ("safety preserved", check_safety_preserved_section),
    ]
    return run_checks(checks)


if __name__ == "__main__":
    raise SystemExit(main())
