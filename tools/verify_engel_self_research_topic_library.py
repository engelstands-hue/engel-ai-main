import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOPIC_JSON = ROOT / "memory" / "ENGEL_SELF_RESEARCH_TOPIC_LIBRARY_V1.json"
TOPIC_MD = ROOT / "memory" / "ENGEL_SELF_RESEARCH_TOPIC_LIBRARY_V1.md"
THIS_FILE = ROOT / "tools" / "verify_engel_self_research_topic_library.py"


REQUIRED_STATUSES = [
    "TOPIC_LIBRARY_ONLY",
    "SELF_RESEARCH_PLANNING_ONLY",
    "RESEARCH_TOPICS_NOT_MEMORY",
    "RESEARCH_TOPICS_NOT_EXECUTION",
    "RESEARCH_TOPICS_NOT_TRAINING",
    "HUMAN_APPROVAL_REQUIRED_FOR_TRUSTED_MEMORY",
    "NO_AUTO_RESEARCH_LOOP",
    "NO_AUTO_DOWNLOADS",
    "NO_AUTO_BROWSER",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_AUTO_INDEXING",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_RUNTIME_TRIGGER",
]

REQUIRED_CATEGORIES = [
    "coding_and_software_engineering",
    "math_and_reasoning",
    "debugging_and_testing",
    "verifier_and_guard_design",
    "core_continuity_and_project_memory",
    "local_agent_architecture",
    "prompt_injection_and_untrusted_content_safety",
    "retrieval_and_memory_systems",
    "python_and_pyside6_app_development",
    "sqlite_and_local_data_design",
    "packaging_and_release_stability",
    "offline_model_runtime_and_gguf",
    "self_fix_and_autopilot_patterns",
    "queen_colony_swarm_mycelium_architecture",
    "user_experience_and_human_error_reduction",
    "security_boundaries_and_authority_hierarchy",
    "research_methodology_and_citation_quality",
    "math_code_cross_training",
    "performance_and_resource_safety",
    "long_term_archive_and_library_management",
]

REQUIRED_TOPIC_FIELDS = [
    "topic_id",
    "title",
    "category",
    "priority",
    "difficulty",
    "purpose",
    "why_engel_needs_this",
    "expected_benefit",
    "safe_source_types",
    "related_existing_engel_systems",
    "suggested_research_questions",
    "expected_outputs",
    "forbidden_outputs",
    "safety_notes",
    "memory_boundary",
    "self_fix_relevance",
    "verifier_relevance",
    "math_relevance",
    "code_relevance",
    "queen_colony_relevance",
    "status",
]

PRIORITY_VALUES = ["critical", "high", "medium", "low"]
DIFFICULTY_VALUES = ["beginner", "intermediate", "advanced", "expert"]
STATUS_VALUES = [
    "proposed",
    "approved_for_future_research",
    "blocked_until_sources_available",
    "needs_human_topic_review",
    "archived_topic",
    "superseded_topic",
]

SAFE_SOURCE_TYPES = [
    "approved_library_materials",
    "manually_reviewed_reference",
    "Engel_reports",
    "Engel_verifiers",
    "Engel_core_continuity_map",
    "Engel_source_code",
    "local_offline_docs",
    "future_approved_web_research",
    "future_approved_model_reference",
    "future_approved_math_reference",
    "future_approved_coding_reference",
]

SAFE_OUTPUTS = [
    "untrusted_research_note",
    "research_summary",
    "lesson_candidate",
    "verifier_improvement_candidate",
    "self_fix_improvement_candidate",
    "memory_candidate_proposal",
    "source_risk_note",
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
    "route_mutation",
    "startup_mutation",
    "background_worker_action",
]

FIRST_STUDY_PHASES = ["Phase 1", "Phase 2", "Phase 3"]
BOUNDARY_PHRASES = [
    "topics are not research results",
    "topics are not trusted memory",
    "topics are not instructions to browse/download",
    "research outputs remain untrusted",
    "memory candidate proposal required",
]

REQUIRED_CROSS_LINKS = [
    "Engel Self-Research Contract V1",
    "Approved Library Materials V1",
    "Storage Location Registry V1",
    "Controlled Approved Library Chain Steps 10-21 V1",
    "Core Continuity Map V1",
    "Untrusted Content Guard",
    "Prompt Injection Guard",
    "Authority Hierarchy",
    "Memory Candidate Proposal path",
    "Self-Fix Autopilot Contract V1",
    "Future Queen/colony workflows",
]


def normalize(text):
    return " ".join(
        str(text)
        .lower()
        .replace("`", "")
        .replace("\\", "/")
        .replace("-", " ")
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


def load_library():
    require(TOPIC_JSON.exists(), f"missing {TOPIC_JSON}")
    require(TOPIC_MD.exists(), f"missing {TOPIC_MD}")
    return json.loads(read(TOPIC_JSON))


def verify_statuses(data, text):
    statuses = data.get("status", [])
    for status in REQUIRED_STATUSES:
        require(status in statuses, f"JSON missing status {status}")
        require(normalize(status) in text, f"Markdown/JSON text missing status {status}")


def verify_categories(data, text):
    categories = data.get("topic_categories", [])
    require_contains_all(normalize(" ".join(categories)), REQUIRED_CATEGORIES, "topic categories in JSON")
    require_contains_all(text, REQUIRED_CATEGORIES, "topic categories in text")
    topic_categories = {topic.get("category") for topic in data.get("topics", [])}
    missing = [category for category in REQUIRED_CATEGORIES if category not in topic_categories]
    require(not missing, f"categories missing topic records: {missing}")


def verify_topic_records(data):
    topics = data.get("topics", [])
    require(isinstance(topics, list), "topics must be a list")
    require(len(topics) >= 60, f"expected at least 60 topics, found {len(topics)}")
    require(data.get("topic_count") == len(topics), "topic_count must match topics length")
    seen_ids = set()
    for index, topic in enumerate(topics, start=1):
        missing_fields = [field for field in REQUIRED_TOPIC_FIELDS if field not in topic]
        require(not missing_fields, f"topic {index} missing fields: {missing_fields}")
        require(topic["topic_id"] not in seen_ids, f"duplicate topic_id {topic['topic_id']}")
        seen_ids.add(topic["topic_id"])
        require(topic["category"] in REQUIRED_CATEGORIES, f"topic {topic['topic_id']} has unknown category")
        require(topic["priority"] in PRIORITY_VALUES, f"topic {topic['topic_id']} has invalid priority")
        require(topic["difficulty"] in DIFFICULTY_VALUES, f"topic {topic['topic_id']} has invalid difficulty")
        require(topic["status"] in STATUS_VALUES, f"topic {topic['topic_id']} has invalid status")
        questions = topic.get("suggested_research_questions", [])
        require(3 <= len(questions) <= 7, f"topic {topic['topic_id']} must have 3-7 research questions")
        require_contains_all(normalize(" ".join(topic.get("safe_source_types", []))), SAFE_SOURCE_TYPES, f"safe source types for {topic['topic_id']}")
        require_contains_all(normalize(" ".join(topic.get("expected_outputs", []))), SAFE_OUTPUTS, f"expected outputs for {topic['topic_id']}")
        require_contains_all(normalize(" ".join(topic.get("forbidden_outputs", []))), FORBIDDEN_OUTPUTS, f"forbidden outputs for {topic['topic_id']}")
        require(normalize("not trusted memory") in normalize(topic.get("memory_boundary", "")), f"topic {topic['topic_id']} missing memory boundary wording")


def verify_outputs_sources_and_sequence(data, text):
    require_contains_all(normalize(" ".join(data.get("safe_source_types", []))), SAFE_SOURCE_TYPES, "safe source types in JSON")
    require_contains_all(text, SAFE_SOURCE_TYPES, "safe source types in text")
    require_contains_all(normalize(" ".join(data.get("expected_outputs", []))), SAFE_OUTPUTS, "safe outputs in JSON")
    require_contains_all(text, SAFE_OUTPUTS, "safe outputs in text")
    require_contains_all(normalize(" ".join(data.get("forbidden_outputs", []))), FORBIDDEN_OUTPUTS, "forbidden outputs in JSON")
    require_contains_all(text, FORBIDDEN_OUTPUTS, "forbidden outputs in text")
    sequence = data.get("first_study_sequence", {})
    for phase in FIRST_STUDY_PHASES:
        require(phase in sequence, f"missing first-study sequence {phase}")
        require(normalize(phase) in text, f"Markdown missing {phase}")
        require(sequence[phase], f"{phase} must not be empty")
    require_contains_all(text, BOUNDARY_PHRASES, "boundary statements")
    require_contains_all(normalize(" ".join(data.get("cross_links", []))), REQUIRED_CROSS_LINKS, "cross-links in JSON")
    require_contains_all(text, REQUIRED_CROSS_LINKS, "cross-links in text")


def verify_library_boundaries(data):
    boundaries = data.get("library_boundaries", {})
    required_true = [
        "topics_are_not_research_results",
        "topics_are_not_trusted_memory",
        "topics_are_not_instructions_to_browse_or_download",
        "topics_are_not_permission_to_mutate_source",
        "topics_are_not_permission_to_run_code",
        "topics_are_not_permission_to_train_models",
        "topics_are_not_permission_to_index_or_embed_content",
        "topics_are_not_permission_to_start_background_research_loops",
        "research_outputs_remain_untrusted_until_reviewed",
        "memory_candidate_proposal_required_for_anything_engel_may_remember",
        "human_approval_required_for_trusted_memory",
    ]
    for key in required_true:
        require(boundaries.get(key) is True, f"library boundary must be true: {key}")
    denials = data.get("inactive_behavior_denials", {})
    required_false = [
        "auto_research_loop_enabled",
        "browser_enabled",
        "network_enabled",
        "provider_calls_enabled",
        "api_calls_enabled",
        "downloads_enabled",
        "package_installs_enabled",
        "model_inference_enabled",
        "model_training_enabled",
        "auto_indexing_enabled",
        "embedding_enabled",
        "trusted_memory_write_enabled",
        "source_mutation_enabled",
        "queue_mutation_enabled",
        "route_startup_changes_enabled",
        "background_workers_enabled",
    ]
    for key in required_false:
        require(key in denials, f"inactive behavior denial missing: {key}")
        require(denials[key] is False, f"inactive behavior denial must be false: {key}")


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
                if isinstance(func.value, ast.Name) and func.value.id == "json" and call_name in {"loads"}:
                    continue
            else:
                call_name = ""
            require(call_name not in forbidden_call_names, f"forbidden active call in verifier: {call_name}")


def main():
    data = load_library()
    combined_text = normalize(read(TOPIC_JSON) + "\n" + read(TOPIC_MD))
    require(data.get("schema_name") == "ENGEL_SELF_RESEARCH_TOPIC_LIBRARY_V1", "unexpected schema_name")
    require(data.get("schema_version") == "1.0", "unexpected schema_version")
    verify_statuses(data, combined_text)
    verify_categories(data, combined_text)
    verify_topic_records(data)
    verify_outputs_sources_and_sequence(data, combined_text)
    verify_library_boundaries(data)
    verify_no_active_behavior_in_verifier()
    print("PASS: Engel Self-Research Topic Library V1 verifier")
    print(f"- topic records: {len(data.get('topics', []))}")
    print("- categories, fields, safe outputs, forbidden outputs, first-study sequence, and boundaries are present")
    print("- no active browser/network/provider/download/indexing/training/source-mutation/trusted-memory behavior is enabled")


if __name__ == "__main__":
    main()
