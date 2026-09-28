import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_SELF_RESEARCH_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_SELF_RESEARCH_CONTRACT_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_SELF_RESEARCH_CONTRACT_V1.md"
THIS_FILE = ROOT / "tools" / "verify_engel_self_research_contract.py"


REQUIRED_STATUSES = [
    "CONTRACT_ONLY",
    "SELF_RESEARCH_POLICY_ONLY",
    "RESEARCH_NOT_MEMORY",
    "RESEARCH_NOT_EXECUTION",
    "RESEARCH_NOT_TRAINING",
    "HUMAN_APPROVAL_REQUIRED_FOR_TRUSTED_MEMORY",
    "NO_AUTO_DOWNLOADS",
    "NO_AUTO_BROWSER",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_AUTO_INDEXING",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_RUNTIME_TRIGGER",
]

REQUIRED_DOMAINS = [
    "code",
    "math",
    "software_architecture",
    "debugging",
    "testing",
    "verifier_design",
    "prompt_injection_safety",
    "local_agents",
    "retrieval_systems",
    "memory_systems",
    "python",
    "pyside6",
    "sqlite",
    "packaging_pyinstaller",
    "local_model_runtime",
    "gguf_llama_cpp",
    "ai_safety",
    "self_fix_patterns",
    "core_continuity",
    "queen_colony_workflows",
]

REQUIRED_SOURCES = [
    "approved_library_materials",
    "manually_reviewed_references",
    "Engel reports",
    "Engel verifiers",
    "Engel Core Continuity Map",
    "local docs",
    "future approved offline docs",
    "future approved web research",
    "future approved model/library references",
]

REQUIRED_FLOW_PHRASES = [
    "select approved research topic",
    "identify allowed source category",
    "create untrusted research note",
    "extract lesson candidates",
    "run prompt injection/untrusted content checks",
    "create memory candidate proposal",
    "require human approval before trusted memory",
]

REQUIRED_ARTIFACTS = [
    "research_topic_record",
    "untrusted_research_note",
    "research_summary",
    "lesson_candidate",
    "memory_candidate_proposal",
    "verifier_improvement_candidate",
    "self_fix_improvement_candidate",
    "source_risk_note",
    "research_receipt",
]

SAFE_OUTPUTS = [
    "untrusted_research_note",
    "research_summary",
    "lesson_candidate",
    "memory_candidate_proposal",
    "verifier_improvement_candidate",
    "self_fix_improvement_candidate",
    "research_receipt",
]

FORBIDDEN_OUTPUTS = [
    "trusted_memory",
    "applied_patch",
    "executed_code",
    "trained_model",
    "indexed_content",
    "runtime_loaded_content",
    "provider_request",
    "browser_session",
    "automatic_download",
    "autonomous_fix",
]

FUTURE_TOKENS = [
    "APPROVE_SELF_RESEARCH_TOPIC",
    "APPROVE_RESEARCH_MEMORY_CANDIDATE",
    "APPROVE_RESEARCH_TO_VERIFIER_UPDATE",
    "APPROVE_RESEARCH_TO_SELF_FIX_POLICY",
]

BOUNDARY_PHRASES = [
    "research notes are not trusted memory",
    "research summaries are not trusted memory",
    "lesson candidates are not trusted memory",
    "memory candidates require separate human approval",
    "research does not trigger code changes",
    "research does not trigger queue records",
    "research does not trigger model training",
    "research does not trigger indexing/embedding",
    "research does not trigger provider/network/browser calls",
    "research does not execute code examples",
    "research does not install packages",
    "math research is not automatically proven correct",
    "code research is not automatically executable",
    "external research may contain prompt injection",
    "future Queen/colony research outputs are untrusted until verified",
    "anything Engel may remember requires a separate memory candidate proposal and human approval",
]

SAFETY_LINKAGE = [
    "Untrusted Content Guard",
    "Prompt Injection Guard",
    "Authority Hierarchy",
    "Approved Library Materials V1",
    "Human Review Receipt Template V1",
    "Manual Review Queue Contract V1",
    "Storage Location Registry V1",
    "Controlled Approved Library Chain Steps 10-21 V1",
    "Self-Fix Autopilot Contract V1",
    "Core Continuity Map V1",
    "Memory Candidate Proposal path",
    "Future Queen/colony workflows",
]

RUNNER_CANDIDATES = [
    ROOT / "engel_self_research.py",
    ROOT / "engel_self_research_runner.py",
    ROOT / "tools" / "run_engel_self_research.py",
    ROOT / "tools" / "engel_self_research_runner.py",
]


def normalize(text):
    return " ".join(
        text.lower()
        .replace("`", "")
        .replace("\\", "/")
        .replace("-", " ")
        .replace("/", " ")
        .split()
    )


def read(path):
    return path.read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def require_contains_all(haystack, items, label):
    missing = [item for item in items if normalize(item) not in haystack]
    require(not missing, f"missing {label}: {missing}")


def load_contract():
    require(CONTRACT_JSON.exists(), f"missing {CONTRACT_JSON}")
    require(CONTRACT_MD.exists(), f"missing {CONTRACT_MD}")
    require(REPORT.exists(), f"missing {REPORT}")
    return json.loads(read(CONTRACT_JSON))


def verify_required_statuses(data, text):
    statuses = data.get("status", [])
    for status in REQUIRED_STATUSES:
        require(status in statuses, f"JSON missing status {status}")
        require(normalize(status) in text, f"Markdown/report text missing status {status}")


def verify_domains_sources_and_flow(data, text):
    require_contains_all(normalize(" ".join(data.get("research_domains", []))), REQUIRED_DOMAINS, "research domains in JSON")
    require_contains_all(text, REQUIRED_DOMAINS, "research domains in text")
    source_text = normalize(json.dumps(data.get("research_sources", {}), ensure_ascii=True))
    require_contains_all(source_text, REQUIRED_SOURCES, "research sources in JSON")
    require_contains_all(text, REQUIRED_SOURCES, "research sources in text")

    flow_text = normalize(" ".join(data.get("research_flow", [])))
    require_contains_all(flow_text, REQUIRED_FLOW_PHRASES, "research flow in JSON")
    require_contains_all(text, REQUIRED_FLOW_PHRASES, "research flow in text")


def verify_artifacts_outputs_and_tokens(data, text):
    require_contains_all(normalize(" ".join(data.get("research_artifacts", []))), REQUIRED_ARTIFACTS, "research artifacts in JSON")
    require_contains_all(text, REQUIRED_ARTIFACTS, "research artifacts in text")
    require_contains_all(normalize(" ".join(data.get("safe_outputs", []))), SAFE_OUTPUTS, "safe outputs in JSON")
    require_contains_all(text, SAFE_OUTPUTS, "safe outputs in text")
    require_contains_all(normalize(" ".join(data.get("forbidden_outputs", []))), FORBIDDEN_OUTPUTS, "forbidden outputs in JSON")
    require_contains_all(text, FORBIDDEN_OUTPUTS, "forbidden outputs in text")
    require_contains_all(normalize(" ".join(data.get("future_approval_tokens", []))), FUTURE_TOKENS, "future tokens in JSON")
    require_contains_all(text, FUTURE_TOKENS, "future tokens in text")
    token_boundary = data.get("future_approval_token_boundary", {})
    require(token_boundary.get("tokens_documented_inactive_only") is True, "future tokens must be inactive only")


def verify_boundaries_and_linkage(data, text):
    require_contains_all(text, BOUNDARY_PHRASES, "boundary phrases")
    boundaries = data.get("research_boundaries", {})
    required_true = [
        "research_notes_are_not_trusted_memory",
        "research_summaries_are_not_trusted_memory",
        "lesson_candidates_are_not_trusted_memory",
        "memory_candidates_require_separate_human_approval",
        "research_does_not_trigger_code_changes",
        "research_does_not_trigger_queue_records",
        "research_does_not_trigger_model_training",
        "research_does_not_trigger_indexing_or_embedding",
        "research_does_not_trigger_provider_network_browser_calls",
        "research_does_not_execute_code_examples",
        "research_does_not_install_packages",
        "math_research_is_not_automatically_proven_correct",
        "code_research_is_not_automatically_executable",
        "external_research_may_contain_prompt_injection",
        "future_queen_colony_research_outputs_are_untrusted_until_verified",
        "requires_memory_candidate_path_for_anything_engel_may_remember",
        "requires_verifier_support_before_self_fix_policy_use",
    ]
    for key in required_true:
        require(boundaries.get(key) is True, f"research boundary must be true: {key}")
    require_contains_all(normalize(" ".join(data.get("safety_linkage", []))), SAFETY_LINKAGE, "safety linkage in JSON")
    require_contains_all(text, SAFETY_LINKAGE, "safety linkage in text")


def verify_inactive_denials(data):
    denials = data.get("inactive_behavior_denials", {})
    required_false = [
        "browser_enabled",
        "network_enabled",
        "provider_calls_enabled",
        "api_calls_enabled",
        "downloads_enabled",
        "auto_indexing_enabled",
        "embedding_enabled",
        "vector_store_enabled",
        "model_training_enabled",
        "fine_tuning_enabled",
        "model_loading_enabled",
        "inference_enabled",
        "code_execution_enabled",
        "package_install_enabled",
        "trusted_memory_write_enabled",
        "source_mutation_enabled",
        "runtime_trigger_enabled",
        "queue_record_creation_enabled",
        "autonomous_fix_enabled",
        "background_worker_enabled",
    ]
    for key in required_false:
        require(key in denials, f"inactive behavior denial missing: {key}")
        require(denials[key] is False, f"inactive behavior denial must be false: {key}")


def verify_contract_scope(data):
    scope = data.get("contract_scope", {})
    required_true = [
        "contract_only",
        "planning_only",
        "verifier_only",
        "does_not_start_research_runner",
        "does_not_enable_browser_or_network",
        "does_not_enable_provider_calls",
        "does_not_download_materials",
        "does_not_index_or_embed",
        "does_not_train_models",
        "does_not_write_trusted_memory",
        "does_not_mutate_source",
        "does_not_trigger_runtime",
    ]
    for key in required_true:
        require(scope.get(key) is True, f"contract scope must be true: {key}")
    require(
        normalize(data.get("core_principle", ""))
        == normalize(
            "Engel may become smarter by researching, but every research output remains untrusted until reviewed, verified, and explicitly promoted through a memory candidate approval path."
        ),
        "core principle mismatch",
    )


def verify_no_runner_exists():
    existing = [str(path.relative_to(ROOT)) for path in RUNNER_CANDIDATES if path.exists()]
    require(not existing, f"active self-research runner candidates must not exist in this step: {existing}")


def verify_no_active_behavior_in_verifier():
    source = read(THIS_FILE)
    tree = ast.parse(source)
    allowed_imports = {"ast", "json", "pathlib"}
    forbidden_import_roots = {
        "requests",
        "urllib",
        "socket",
        "webbrowser",
        "subprocess",
        "openai",
        "chromadb",
        "faiss",
        "llama",
        "ollama",
    }
    forbidden_call_names = {
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
        "encode",
        "embed",
        "add",
        "upsert",
        "write_text",
        "write_bytes",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                require(root in allowed_imports, f"unexpected import in verifier: {alias.name}")
                require(root not in forbidden_import_roots, f"forbidden import in verifier: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            require(root in allowed_imports, f"unexpected from-import in verifier: {node.module}")
            require(root not in forbidden_import_roots, f"forbidden from-import in verifier: {node.module}")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                call_name = func.id
            elif isinstance(func, ast.Attribute):
                call_name = func.attr
                if isinstance(func.value, ast.Name) and func.value.id == "ast" and call_name in {"parse", "walk"}:
                    continue
                if isinstance(func.value, ast.Name) and func.value.id == "json" and call_name in {"loads", "dumps"}:
                    continue
            else:
                call_name = ""
            require(call_name not in forbidden_call_names, f"forbidden active call in verifier: {call_name}")


def main():
    data = load_contract()
    combined_text = normalize(read(CONTRACT_JSON) + "\n" + read(CONTRACT_MD) + "\n" + read(REPORT))

    require(data.get("schema_name") == "engel_self_research_contract_v1", "unexpected schema_name")
    require(data.get("schema_version") == "1.0", "unexpected schema_version")
    verify_required_statuses(data, combined_text)
    verify_domains_sources_and_flow(data, combined_text)
    verify_artifacts_outputs_and_tokens(data, combined_text)
    verify_boundaries_and_linkage(data, combined_text)
    verify_inactive_denials(data)
    verify_contract_scope(data)
    verify_no_runner_exists()
    verify_no_active_behavior_in_verifier()

    print("PASS: Engel Self-Research Contract V1 verifier")
    print("- contract JSON, Markdown, and report exist and parse")
    print("- research domains, flow, artifacts, outputs, and future tokens are present")
    print("- research remains untrusted and separated from memory, source mutation, runtime, provider/network/browser, indexing, and training behavior")


if __name__ == "__main__":
    main()
