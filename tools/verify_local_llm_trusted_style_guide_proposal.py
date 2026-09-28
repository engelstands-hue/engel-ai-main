from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEMORY = ROOT / "memory"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_LOCAL_LLM_TRUSTED_STYLE_GUIDE_PROPOSAL_V1.md"
APPROVAL = MEMORY / "ENGEL_LOCAL_LLM_TRUSTED_STYLE_GUIDE_PROPOSAL_APPROVAL_V1.json"
PROPOSAL = MEMORY / "ENGEL_LOCAL_LLM_TRUSTED_STYLE_GUIDE_PROPOSAL_V1.md"
BRAIN_CONTEXT_CONTRACT = MEMORY / "ENGEL_BRAIN_PROVIDER_TRUSTED_CONTEXT_CONTRACT_V1.json"

SOURCE_MATERIALS = [
    MEMORY / "ENGEL_LOCAL_LLM_ONE_HOUR_TEACHING_SESSION_CONTRACT_V1.json",
    MEMORY / "ENGEL_LOCAL_LLM_TEACHING_PLAN_V1.md",
    MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_KNOWLEDGE_CANDIDATES_V1.md",
    MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_MEMORY_CANDIDATES_V1.md",
    MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_CONVERSATION_EXAMPLES_V1.md",
    MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_DEMO_SCRIPT_V1.md",
    MEMORY / "ENGEL_LOCAL_LLM_PERSONALITY_PROMPT_SCAFFOLD_V1.md",
    MEMORY / "ENGEL_LOCAL_LLM_FLUIDITY_RUBRIC_V1.json",
    ROOT / "reports" / "codex_bridge" / "ENGEL_LOCAL_LLM_ONE_HOUR_TEACHING_SESSION_V1.md",
]

FALSE_FLAGS = [
    "trusted_style_guide_enabled",
    "trusted_context_allowlist_updated",
    "runtime_enabled",
    "inference_enabled",
    "training_enabled",
    "fine_tuning_enabled",
    "model_weight_update_enabled",
    "provider_calls_enabled",
    "network_enabled",
    "trusted_memory_write_enabled",
    "approved_memory_write_enabled",
    "memory_write_enabled",
    "autonomous_learning_enabled",
    "mobile_runtime_enabled",
    "remote_queen_runtime_enabled",
    "queue_mutation_enabled",
    "route_mutation_enabled",
    "source_mutation_enabled",
    "source_mutation_from_model_output_enabled",
    "build_or_package_enabled",
    "candidate_promotion_enabled",
]

FORBIDDEN_RUNTIME_PATTERNS = [
    "ollama run",
    "ollama serve",
    "llama-cli.exe",
    "llama-server.exe",
    "rpc-server.exe",
    "start lm studio",
    "pip install",
    "npm install",
    "pyinstaller",
    "invoke-webrequest",
    "curl ",
    "start-process",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict:
    data = json.loads(read_text(path))
    if not isinstance(data, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return data


def check(condition: bool, message: str, failures: list[str], passes: list[str]) -> None:
    if condition:
        passes.append("PASS " + message)
    else:
        failures.append("FAIL " + message)


def validate_files(failures: list[str], passes: list[str]) -> None:
    for path in [APPROVAL, PROPOSAL, REPORT, *SOURCE_MATERIALS]:
        check(path.exists() and path.is_file(), f"required file exists: {path.relative_to(ROOT)}", failures, passes)


def validate_approval(failures: list[str], passes: list[str]) -> dict:
    data = load_json(APPROVAL)
    check(data.get("status") == "approved_for_trusted_style_guide_proposal_only", "approval scope is proposal-only", failures, passes)
    check(data.get("trusted_style_guide_proposal_created") is True, "proposal creation is recorded", failures, passes)
    check(data.get("all_outputs_remain_reviewable") is True, "outputs remain reviewable", failures, passes)
    for flag in FALSE_FLAGS:
        check(data.get(flag) is False, f"{flag} is false", failures, passes)
    return data


def validate_proposal(failures: list[str], passes: list[str]) -> None:
    text = read_text(PROPOSAL)
    lower = text.lower()
    for phrase in [
        "status: trusted_style_guide_proposal_only",
        "trust_status: proposal_only_not_trusted",
        "can_apply_now: false",
        "requires_human_review: true",
        "not trusted memory",
        "not active prompt authority",
        "not model training",
        "not runtime configuration",
        "Explicitly Not Enabled",
        "Before any trusted-style-guide promotion",
    ]:
        check(phrase.lower() in lower, f"proposal contains boundary phrase: {phrase}", failures, passes)
    for phrase in [
        "Engel helps you move complicated work forward without losing control",
        "Next safe step:",
        "Not active yet.",
        "Candidate means maybe useful, not trusted yet.",
        "No model weights changed.",
    ]:
        check(phrase.lower() in lower, f"proposal contains style phrase: {phrase}", failures, passes)


def validate_sources_still_candidate(failures: list[str], passes: list[str]) -> None:
    candidate_files = [
        MEMORY / "ENGEL_LOCAL_LLM_TEACHING_PLAN_V1.md",
        MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_KNOWLEDGE_CANDIDATES_V1.md",
        MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_MEMORY_CANDIDATES_V1.md",
        MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_CONVERSATION_EXAMPLES_V1.md",
        MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_DEMO_SCRIPT_V1.md",
        MEMORY / "ENGEL_LOCAL_LLM_PERSONALITY_PROMPT_SCAFFOLD_V1.md",
    ]
    for path in candidate_files:
        lower = read_text(path).lower()
        check("trust_status: candidate_only" in lower, f"{path.name} still marked candidate_only", failures, passes)
        check("can_apply_now: false" in lower, f"{path.name} still cannot apply now", failures, passes)
        check("requires_human_review: true" in lower, f"{path.name} still requires human review", failures, passes)


def validate_not_allowlisted(failures: list[str], passes: list[str]) -> None:
    if not BRAIN_CONTEXT_CONTRACT.exists():
        passes.append("PASS brain-provider trusted context contract absent; proposal cannot be allowlisted there")
        return
    data = load_json(BRAIN_CONTEXT_CONTRACT)
    allowed = data.get("allowed_source_files", [])
    serialized = json.dumps(allowed).lower()
    check("engel_local_llm_trusted_style_guide_proposal_v1.md" not in serialized, "proposal is not in brain-provider trusted context allowlist", failures, passes)


def validate_no_runtime_patterns(failures: list[str], passes: list[str]) -> None:
    for path in [APPROVAL, PROPOSAL, REPORT]:
        lower = read_text(path).lower()
        for pattern in FORBIDDEN_RUNTIME_PATTERNS:
            check(pattern not in lower, f"{path.name} does not include runtime/install/build pattern '{pattern}'", failures, passes)


def validate_report(failures: list[str], passes: list[str]) -> None:
    text = read_text(REPORT)
    for phrase in [
        "summary",
        "approval scope",
        "changed files",
        "not enabled",
        "verifier results",
        "recommended next step",
    ]:
        check(phrase.lower() in text.lower(), f"report contains {phrase}", failures, passes)


def main() -> int:
    failures: list[str] = []
    passes: list[str] = []
    try:
        validate_files(failures, passes)
        validate_approval(failures, passes)
        validate_proposal(failures, passes)
        validate_sources_still_candidate(failures, passes)
        validate_not_allowlisted(failures, passes)
        validate_no_runtime_patterns(failures, passes)
        validate_report(failures, passes)
    except Exception as exc:
        failures.append("FAIL verifier exception: " + str(exc))

    for line in passes:
        print(line)
    for line in failures:
        print(line, file=sys.stderr)
    if failures:
        print(f"ENGEL_LOCAL_LLM_TRUSTED_STYLE_GUIDE_PROPOSAL_VERIFY_FAIL failures={len(failures)}", file=sys.stderr)
        return 1
    print("ENGEL_LOCAL_LLM_TRUSTED_STYLE_GUIDE_PROPOSAL_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
