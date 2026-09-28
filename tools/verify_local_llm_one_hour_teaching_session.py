from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEMORY = ROOT / "memory"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_LOCAL_LLM_ONE_HOUR_TEACHING_SESSION_V1.md"

REQUIRED_FILES = [
    MEMORY / "ENGEL_LOCAL_LLM_ONE_HOUR_TEACHING_SESSION_CONTRACT_V1.json",
    MEMORY / "ENGEL_LOCAL_LLM_TEACHING_PLAN_V1.md",
    MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_KNOWLEDGE_CANDIDATES_V1.md",
    MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_MEMORY_CANDIDATES_V1.md",
    MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_CONVERSATION_EXAMPLES_V1.md",
    MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_DEMO_SCRIPT_V1.md",
    MEMORY / "ENGEL_LOCAL_LLM_PERSONALITY_PROMPT_SCAFFOLD_V1.md",
    MEMORY / "ENGEL_LOCAL_LLM_FLUIDITY_RUBRIC_V1.json",
    ROOT / "tools" / "verify_local_llm_one_hour_teaching_session.py",
    REPORT,
]

FALSE_FLAGS = [
    "runtime_enabled",
    "inference_enabled",
    "training_enabled",
    "fine_tuning_enabled",
    "model_weight_update_enabled",
    "provider_calls_enabled",
    "network_enabled",
    "trusted_memory_write_enabled",
    "approved_memory_write_enabled",
    "autonomous_learning_enabled",
    "mobile_runtime_enabled",
    "remote_queen_runtime_enabled",
    "queue_mutation_enabled",
    "route_mutation_enabled",
    "source_mutation_from_model_output_enabled",
    "build_or_package_enabled",
    "candidate_promotion_enabled",
]

TRUE_FLAGS = [
    "customer_ready_goal",
    "local_llm_growth_goal",
    "memory_candidates_only",
    "knowledge_candidates_only",
    "human_review_required",
    "all_outputs_untrusted_until_verified",
]

REQUIRED_EXAMPLE_FIELDS = [
    "Customer/user message:",
    "Bad robotic response to avoid:",
    "Improved Engel response:",
    "Why the improved response is better:",
    "Safety boundary preserved:",
]

REQUIRED_CATEGORIES = [
    "first-time customer",
    "buyer hesitation",
    "customer asks why should I buy this?",
    "privacy/local question",
    "local LLM question",
    "mobile connection question",
    "Remote Queen question",
    "app-building question",
    "file/project organization",
    "next step please",
    "combine",
    "should I do this?",
    "frustrated customer",
    "confused customer",
    "feature not ready yet",
    "mistake apology",
    "demo request",
    "Codex prompt request",
    "copy-back/refactor workflow",
    "safety concern",
    "customer asks if Engel can work while away",
]

FORBIDDEN_IMPROVED_PHRASES = [
    "as an ai language model",
    "certainly, i can assist",
    "revolutionary ai platform",
]

FORBIDDEN_COMMAND_PATTERNS = [
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


def validate_required_files(failures: list[str], passes: list[str]) -> None:
    for path in REQUIRED_FILES:
        check(path.exists() and path.is_file(), f"required file exists: {path.relative_to(ROOT)}", failures, passes)


def validate_contract(failures: list[str], passes: list[str]) -> None:
    contract = load_json(MEMORY / "ENGEL_LOCAL_LLM_ONE_HOUR_TEACHING_SESSION_CONTRACT_V1.json")
    check(contract.get("status") == "scaffold_teaching_session_only", "contract status is scaffold-only", failures, passes)
    check(int(contract.get("minimum_session_minutes", 0)) >= 60, "minimum_session_minutes is 60 or more", failures, passes)
    for key in FALSE_FLAGS:
        check(contract.get(key) is False, f"{key} is false", failures, passes)
    for key in TRUE_FLAGS:
        check(contract.get(key) is True, f"{key} is true", failures, passes)


def validate_candidate_markers(failures: list[str], passes: list[str]) -> None:
    candidate_files = [
        MEMORY / "ENGEL_LOCAL_LLM_TEACHING_PLAN_V1.md",
        MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_KNOWLEDGE_CANDIDATES_V1.md",
        MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_MEMORY_CANDIDATES_V1.md",
        MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_CONVERSATION_EXAMPLES_V1.md",
        MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_DEMO_SCRIPT_V1.md",
        MEMORY / "ENGEL_LOCAL_LLM_PERSONALITY_PROMPT_SCAFFOLD_V1.md",
    ]
    for path in candidate_files:
        text = read_text(path).lower()
        check("trust_status: candidate_only" in text, f"{path.name} contains candidate_only marker", failures, passes)
        check("can_apply_now: false" in text, f"{path.name} contains can_apply_now false marker", failures, passes)
        check("requires_human_review: true" in text, f"{path.name} contains human review marker", failures, passes)


def parse_examples(text: str) -> list[str]:
    blocks = re.split(r"(?=^### Example \d+)", text, flags=re.MULTILINE)
    return [block.strip() for block in blocks if block.strip().startswith("### Example ")]


def validate_examples(failures: list[str], passes: list[str]) -> None:
    text = read_text(MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_CONVERSATION_EXAMPLES_V1.md")
    examples = parse_examples(text)
    check(len(examples) >= 50, f"examples count is at least 50 (found {len(examples)})", failures, passes)
    lower_all = text.lower()
    for category in REQUIRED_CATEGORIES:
        check(f"category: {category}".lower() in lower_all, f"required category present: {category}", failures, passes)
    for index, block in enumerate(examples, start=1):
        for field in REQUIRED_EXAMPLE_FIELDS:
            check(field in block, f"example {index:02d} contains {field}", failures, passes)
        for marker in ["trust_status: candidate_only", "can_apply_now: false", "requires_human_review: true"]:
            check(marker in block.lower(), f"example {index:02d} contains {marker}", failures, passes)
        improved_match = re.search(
            r"Improved Engel response:\s*(.*?)(?:\n\nWhy the improved response is better:)",
            block,
            flags=re.DOTALL,
        )
        check(bool(improved_match), f"example {index:02d} improved response can be parsed", failures, passes)
        if improved_match:
            improved = improved_match.group(1).lower()
            for phrase in FORBIDDEN_IMPROVED_PHRASES:
                check(phrase not in improved, f"example {index:02d} improved response avoids '{phrase}'", failures, passes)


def validate_demo_and_scaffold(failures: list[str], passes: list[str]) -> None:
    demo = read_text(MEMORY / "ENGEL_LOCAL_LLM_CUSTOMER_DEMO_SCRIPT_V1.md")
    scaffold = read_text(MEMORY / "ENGEL_LOCAL_LLM_PERSONALITY_PROMPT_SCAFFOLD_V1.md")
    for phrase in [
        "Opening",
        "What Engel Is",
        "Customer Value",
        "Local/Private Explanation",
        "Mobile Connection Explanation",
        "Remote Queens Explanation",
        "Safety Explanation",
        "App-Building Example",
        "Next Step Example",
        "Honest Limitation Statement",
        "Closing Buyer-Friendly Summary",
    ]:
        check(phrase in demo, f"demo script contains {phrase}", failures, passes)
    for phrase in [
        "System-Style Instruction Draft",
        "Tone Rules",
        "Safety Rules",
        "Memory Usage Rules",
        "Retrieval/Knowledge Usage Rules",
        "When Uncertain",
        "When A Feature Is Planned But Disabled",
        "Forbidden Phrases",
        "Forbidden Claims",
        "Customer-Ready Response Pattern",
    ]:
        check(phrase in scaffold, f"prompt scaffold contains {phrase}", failures, passes)


def validate_rubric(failures: list[str], passes: list[str]) -> None:
    rubric = load_json(MEMORY / "ENGEL_LOCAL_LLM_FLUIDITY_RUBRIC_V1.json")
    check(rubric.get("trust_status") == "candidate_only", "rubric is candidate-only", failures, passes)
    check(rubric.get("can_apply_now") is False, "rubric cannot apply now", failures, passes)
    check(rubric.get("requires_human_review") is True, "rubric requires human review", failures, passes)
    check(int(rubric.get("total_score_minimum", 0)) >= 30, "rubric threshold is at least 30", failures, passes)
    dimensions = rubric.get("dimensions", {})
    check(isinstance(dimensions, dict) and len(dimensions) >= 12, "rubric has at least 12 dimensions", failures, passes)
    check(rubric.get("no_critical_failures") is True, "rubric requires no critical failures", failures, passes)


def validate_no_forbidden_runtime_commands(failures: list[str], passes: list[str]) -> None:
    scan_files = [path for path in REQUIRED_FILES if path.name != "verify_local_llm_one_hour_teaching_session.py"]
    for path in scan_files:
        text = read_text(path).lower()
        for pattern in FORBIDDEN_COMMAND_PATTERNS:
            check(pattern not in text, f"{path.name} does not include runtime/install/build command pattern '{pattern}'", failures, passes)


def validate_report(failures: list[str], passes: list[str]) -> None:
    text = read_text(REPORT)
    for phrase in [
        "start_timestamp_local:",
        "end_timestamp_local:",
        "elapsed_minutes:",
        "Business/Customer Reason",
        "What Remains Disabled",
        "Verifier Results",
        "Recommended Next Step",
    ]:
        check(phrase in text, f"report contains {phrase}", failures, passes)


def main() -> int:
    failures: list[str] = []
    passes: list[str] = []
    try:
        validate_required_files(failures, passes)
        validate_contract(failures, passes)
        validate_candidate_markers(failures, passes)
        validate_examples(failures, passes)
        validate_demo_and_scaffold(failures, passes)
        validate_rubric(failures, passes)
        validate_no_forbidden_runtime_commands(failures, passes)
        validate_report(failures, passes)
    except Exception as exc:
        failures.append("FAIL verifier exception: " + str(exc))

    for line in passes:
        print(line)
    for line in failures:
        print(line, file=sys.stderr)
    if failures:
        print(f"ENGEL_LOCAL_LLM_ONE_HOUR_TEACHING_SESSION_VERIFY_FAIL failures={len(failures)}", file=sys.stderr)
        return 1
    print("ENGEL_LOCAL_LLM_ONE_HOUR_TEACHING_SESSION_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
