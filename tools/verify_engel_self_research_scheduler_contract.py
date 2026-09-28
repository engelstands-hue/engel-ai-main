from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_SELF_RESEARCH_SCHEDULER_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_SELF_RESEARCH_SCHEDULER_CONTRACT_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_SELF_RESEARCH_SCHEDULER_CONTRACT_V1.md"
THIS_FILE = ROOT / "tools" / "verify_engel_self_research_scheduler_contract.py"

REQUIRED_STATUSES = [
    "CONTRACT_ONLY",
    "SELF_RESEARCH_SCHEDULER_POLICY",
    "SCHEDULER_NOT_IMPLEMENTED",
    "BOUNDED_LEARNING_JOBS_ONLY",
    "CANDIDATE_OUTPUTS_ONLY",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_VERIFIER_UPDATE",
    "NO_SELF_FIX_POLICY_UPDATE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_AUTO_DOWNLOADS",
    "NO_AUTO_INDEXING",
    "NO_MODEL_TRAINING",
    "NO_RUNTIME_TRIGGER",
    "NO_UNBOUNDED_BACKGROUND_LOOP",
]

POLICY_PHRASES = [
    "max 1 topic per job",
    "max 1 source per job",
    "max 1-3 jobs per scheduler run",
    "only explicit approved topic/source pairs",
    "local project sources only",
    "no external drives",
    "no URLs",
    "no live/staging paths",
    "no model folders",
    "no trusted-memory paths",
    "receipts required",
    "summary report required",
    "stop on unsafe path/source/risk",
    "no endless loop",
    "no startup auto-run",
]

JOB_FIELDS = [
    "scheduler_run_id",
    "job_id",
    "topic_id",
    "source_path",
    "mode",
    "output_note_path",
    "output_lesson_candidate_path",
    "output_memory_candidate_path",
    "receipt_path",
    "status",
    "stopped",
    "stop_reason",
    "safety_boundary",
    "verification_result",
]

BOUNDARY_PHRASES = [
    "scheduler not implemented in this step",
    "no active scheduler exists in this step",
    "no learning jobs are run by this contract",
    "no background worker is created",
    "no unbounded background loop is created",
    "no endless loop is allowed",
    "no startup auto-run is allowed",
    "no trusted memory write",
    "no source mutation",
    "no verifier update",
    "no self-fix policy update",
    "no provider calls",
    "no network",
    "no browser",
    "no automatic downloads",
    "no automatic indexing",
    "no model training",
    "no runtime trigger",
]

SCHEDULER_CANDIDATES = [
    ROOT / "engel_self_research_scheduler.py",
    ROOT / "engel_self_learning_scheduler.py",
    ROOT / "tools" / "run_engel_self_research_scheduler.py",
    ROOT / "tools" / "engel_self_research_scheduler.py",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    require(path.exists(), "missing required file: " + str(path.relative_to(ROOT)))
    require(path.is_file(), "required path is not a file: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def normalize(text: str) -> str:
    return " ".join(
        text.lower()
        .replace("`", "")
        .replace("\\", "/")
        .replace("-", " ")
        .replace("_", " ")
        .split()
    )


def require_text(combined: str, needle: str, label: str) -> None:
    require(normalize(needle) in normalize(combined), label + " missing expected text: " + needle)


def load_contract() -> tuple[dict, str]:
    payload = json.loads(read(CONTRACT_JSON))
    combined = json.dumps(payload, sort_keys=True) + "\n" + read(CONTRACT_MD) + "\n" + read(REPORT)
    return payload, combined


def check_files() -> None:
    read(CONTRACT_JSON)
    read(CONTRACT_MD)
    read(REPORT)


def check_statuses(payload: dict, combined: str) -> None:
    statuses = payload.get("status", [])
    require(isinstance(statuses, list), "status must be a list")
    for status in REQUIRED_STATUSES:
        require(status in statuses, "missing JSON status: " + status)
        require_text(combined, status, "status")


def check_scheduler_policy(payload: dict, combined: str) -> None:
    policy = payload.get("scheduler_policy", {})
    require(policy.get("max_topics_per_job") == 1, "max topics per job must be 1")
    require(policy.get("max_sources_per_job") == 1, "max sources per job must be 1")
    require(policy.get("min_jobs_per_scheduler_run") == 1, "min jobs per scheduler run must be 1")
    require(policy.get("max_jobs_per_scheduler_run") == 3, "max jobs per scheduler run must be 3")
    for key in [
        "only_explicit_approved_topic_source_pairs",
        "local_project_sources_only",
        "no_external_drives",
        "no_urls",
        "no_live_staging_paths",
        "no_model_folders",
        "no_trusted_memory_paths",
        "receipts_required",
        "summary_report_required",
        "stop_on_unsafe_path_source_or_risk",
        "no_endless_loop",
        "no_startup_auto_run",
        "candidate_outputs_only",
    ]:
        require(policy.get(key) is True, "scheduler policy flag must be true: " + key)
    for phrase in POLICY_PHRASES:
        require_text(combined, phrase, "scheduler policy")


def check_job_fields(payload: dict, combined: str) -> None:
    fields = payload.get("future_job_record_fields", [])
    require(fields == JOB_FIELDS, "future job record fields mismatch")
    for field in JOB_FIELDS:
        require_text(combined, field, "future job record field")


def check_boundaries(payload: dict, combined: str) -> None:
    scope = payload.get("contract_scope", {})
    for key in [
        "contract_only",
        "policy_only",
        "scheduler_not_implemented",
        "no_active_scheduler",
        "no_background_worker",
        "no_unbounded_background_loop",
        "does_not_run_learning_jobs",
        "does_not_start_at_startup",
        "does_not_write_trusted_memory",
        "does_not_mutate_source",
        "does_not_update_verifiers",
        "does_not_update_self_fix_policy",
    ]:
        require(scope.get(key) is True, "contract scope flag must be true: " + key)
    for phrase in BOUNDARY_PHRASES:
        require_text(combined, phrase, "boundary")

    denials = payload.get("inactive_behavior_denials", {})
    for key, value in denials.items():
        require(value is False, "inactive behavior denial must be false: " + key)
    for key in [
        "scheduler_implemented",
        "learning_jobs_run_by_this_contract",
        "background_loop_enabled",
        "unbounded_loop_enabled",
        "startup_auto_run_enabled",
        "trusted_memory_write_enabled",
        "source_mutation_enabled",
        "verifier_update_enabled",
        "self_fix_policy_update_enabled",
        "provider_calls_enabled",
        "network_enabled",
        "browser_enabled",
        "auto_downloads_enabled",
        "auto_indexing_enabled",
        "model_training_enabled",
        "runtime_trigger_enabled",
    ]:
        require(key in denials, "inactive behavior denial missing: " + key)


def check_stop_conditions(payload: dict, combined: str) -> None:
    stop_conditions = payload.get("stop_conditions", [])
    require(isinstance(stop_conditions, list) and len(stop_conditions) >= 10, "stop conditions must be a populated list")
    for phrase in [
        "topic/source pair is not explicit",
        "more than three jobs are requested for one scheduler run",
        "source path is outside the project root",
        "source path is an external drive",
        "source path is a URL",
        "source path is live or staging",
        "source path is a model folder",
        "source path is a trusted-memory path",
        "risk is unsafe or unclear",
        "any verifier or guard check fails",
    ]:
        require_text(combined, phrase, "stop condition")


def check_no_active_scheduler_exists() -> None:
    existing = [str(path.relative_to(ROOT)) for path in SCHEDULER_CANDIDATES if path.exists()]
    require(not existing, "active scheduler implementation candidate exists: " + ", ".join(existing))


def check_verifier_ast_safety() -> None:
    source = read(THIS_FILE)
    tree = ast.parse(source)
    allowed_import_roots = {"ast", "json", "pathlib"}
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
        "encode",
        "embed",
        "write_text",
        "write_bytes",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                require(root in allowed_import_roots, "unexpected verifier import: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            require(root in allowed_import_roots or node.module == "__future__", "unexpected verifier import-from: " + str(node.module))
        elif isinstance(node, ast.While):
            raise CheckFailure("verifier contains a while loop")
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "ast" and name in {"parse", "walk"}:
                    continue
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "json" and name in {"loads", "dumps"}:
                    continue
            require(name not in forbidden_calls, "forbidden active call in verifier: " + name)


def main() -> int:
    try:
        check_files()
        payload, combined = load_contract()
        require(payload.get("schema_name") == "engel_self_research_scheduler_contract_v1", "schema_name mismatch")
        require(payload.get("schema_version") == "1.0", "schema_version mismatch")
        check_statuses(payload, combined)
        check_scheduler_policy(payload, combined)
        check_job_fields(payload, combined)
        check_boundaries(payload, combined)
        check_stop_conditions(payload, combined)
        check_no_active_scheduler_exists()
        check_verifier_ast_safety()
    except (CheckFailure, json.JSONDecodeError, SyntaxError) as exc:
        print("FAIL: Engel Self-Research Scheduler Contract V1 verifier")
        print("- " + str(exc))
        return 1

    print("PASS: Engel Self-Research Scheduler Contract V1 verifier")
    print("- contract JSON, Markdown, and report exist and parse")
    print("- scheduler policy, limits, job fields, stop conditions, and boundaries are present")
    print("- no scheduler implementation or background loop behavior is enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
