from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_APPROVED_MEMORY_PROMOTION_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_APPROVED_MEMORY_PROMOTION_CONTRACT_V1.md"
VERIFIER = ROOT / "tools" / "verify_engel_approved_memory_promotion_contract.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_APPROVED_MEMORY_PROMOTION_CONTRACT_V1.md"

REQUIRED_STATUSES = [
    "CONTRACT_ONLY",
    "MEMORY_PROMOTION_POLICY",
    "WRITER_NOT_IMPLEMENTED",
    "HUMAN_APPROVAL_REQUIRED",
    "APPROVAL_TOKEN_REQUIRED",
    "SOURCE_CHAIN_REQUIRED",
    "PROMPT_INJECTION_REVIEW_REQUIRED",
    "AUTHORITY_REVIEW_REQUIRED",
    "CORE_CONTINUITY_LINKAGE_REQUIRED",
    "RECEIPT_REQUIRED",
    "NO_AUTOMATIC_MEMORY_PROMOTION",
]

REQUIRED_TOKEN = "APPROVE_PROMOTE_MEMORY_CANDIDATE"

PROMOTION_CONDITIONS = [
    "memory candidate proposal exists",
    "source research note exists",
    "source lesson candidate exists",
    "source chain is recorded",
    "prompt-injection review completed",
    "authority review completed",
    "uncertainty noted",
    "reason to remember is clear",
    "human approval token provided",
    "receipt will be created",
    "rollback note included",
]

RECEIPT_FIELDS = [
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
    "uncertainty_notes",
    "reason_to_remember",
    "core_continuity_linkage",
    "trusted_memory_target",
    "receipt_created_at",
    "rollback_note",
    "human_intervention_required",
    "no_automatic_memory_promotion",
    "no_source_mutation",
    "no_provider_network_browser",
    "no_model_training",
    "no_runtime_trigger",
]

BOUNDARY_TEXT = [
    "contract does not write memory",
    "writer not implemented",
    "token inactive until writer exists",
    "no automatic promotion",
    "no source mutation",
    "no provider/network/browser",
    "no model training",
    "no runtime trigger",
    "memory candidate proposal is not trusted memory",
    "human approval required",
    "prompt-injection review required",
    "authority review required",
    "Core Continuity linkage required",
    "receipt required",
    "rollback note required",
]

WRITER_CANDIDATES = [
    ROOT / "engel_approved_memory_promotion_writer.py",
    ROOT / "tools" / "engel_approved_memory_promotion_writer.py",
    ROOT / "tools" / "run_engel_approved_memory_promotion.py",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def combined_text() -> str:
    return "\n".join(read_text(path) for path in [CONTRACT_JSON, CONTRACT_MD, REPORT])


def check_files_exist() -> None:
    for path in [CONTRACT_JSON, CONTRACT_MD, VERIFIER, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))


def check_json_contract() -> None:
    data = json.loads(read_text(CONTRACT_JSON))
    require(data.get("id") == "engel_approved_memory_promotion_contract_v1", "contract id mismatch")
    require(data.get("type") == "approved_memory_promotion_contract", "contract type mismatch")
    for status in REQUIRED_STATUSES:
        require(status in data.get("status", []), "contract JSON missing status: " + status)
    token = data.get("future_approval_token", {})
    require(token.get("token") == REQUIRED_TOKEN, "contract JSON missing future approval token")
    require(token.get("active") is False, "future approval token must be inactive")
    require(token.get("inactive_until_writer_exists") is True, "future token must stay inactive until writer exists")
    for condition in PROMOTION_CONDITIONS:
        require(condition in data.get("promotion_conditions", []), "contract JSON missing condition: " + condition)
    for field in RECEIPT_FIELDS:
        require(field in data.get("receipt_fields", []), "contract JSON missing receipt field: " + field)
    boundary = data.get("boundary", {})
    for key in [
        "contract_does_not_write_memory",
        "writer_not_implemented",
        "token_inactive_until_writer_exists",
        "no_automatic_promotion",
        "no_source_mutation",
        "no_provider_network_browser",
        "no_model_training",
        "no_runtime_trigger",
        "memory_candidate_proposal_is_not_trusted_memory",
        "human_approval_required",
        "prompt_injection_review_required",
        "authority_review_required",
        "core_continuity_linkage_required",
        "receipt_required",
        "rollback_note_required",
    ]:
        require(boundary.get(key) is True, "contract JSON boundary missing/false: " + key)


def check_required_text() -> None:
    text = combined_text()
    for needle in REQUIRED_STATUSES + [REQUIRED_TOKEN] + PROMOTION_CONDITIONS + RECEIPT_FIELDS + BOUNDARY_TEXT:
        require(needle in text, "contract coverage missing: " + needle)
    for needle in [
        "This is contract-only",
        "writer is not implemented in this step",
        "does not write memory",
        "does not promote memory automatically",
        "does not mutate source",
        "does not call providers",
        "does not use network or browser behavior",
        "does not train models",
        "does not trigger runtime behavior",
    ]:
        require(needle in text, "contract missing explicit inactive boundary: " + needle)


def check_no_writer_implementation() -> None:
    existing = [str(path.relative_to(ROOT)) for path in WRITER_CANDIDATES if path.exists()]
    require(not existing, "approved memory promotion writer must not exist in this contract-only step: " + str(existing))


def check_verifier_has_no_active_behavior() -> None:
    tree = ast.parse(read_text(VERIFIER))
    forbidden_imports = {
        "requests",
        "urllib",
        "socket",
        "webbrowser",
        "openai",
        "subprocess",
        "glob",
        "shutil",
        "threading",
        "multiprocessing",
    }
    forbidden_calls = {
        "run",
        "Popen",
        "system",
        "startfile",
        "urlopen",
        "request",
        "connect",
        "download",
        "train",
        "fit",
        "write_text",
        "write_bytes",
        "unlink",
        "remove",
        "rename",
        "replace",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in forbidden_imports, "verifier imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in forbidden_imports, "verifier imports forbidden module: " + node.module)
        if isinstance(node, ast.Call):
            func = node.func
            call_name = ""
            if isinstance(func, ast.Name):
                call_name = func.id
            elif isinstance(func, ast.Attribute):
                call_name = func.attr
            require(call_name not in forbidden_calls, "verifier uses forbidden active call: " + call_name)


def main() -> int:
    try:
        check_files_exist()
        check_json_contract()
        check_required_text()
        check_no_writer_implementation()
        check_verifier_has_no_active_behavior()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel approved memory promotion contract verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
