from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    APP_ROOT = Path.cwd()
else:
    try:
        APP_ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        APP_ROOT = Path.cwd()
ENGEL_APP = APP_ROOT / "engel_app.py"
CONTRACT_PATH = APP_ROOT / "memory" / "COLONY_SIMULATION_CONTRACT_V1.json"
MANIFEST_PATH = APP_ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
BO_REPORT_PATH = APP_ROOT / "reports" / "app" / "V2APP_BO_ENGEL_COLONY_SIMULATION_CONTRACT.md"
BO_CHECKPOINT_PATH = APP_ROOT / "memory" / "V2APP_BO_ENGEL_COLONY_SIMULATION_CONTRACT.json"
BP_REPORT_PATH = APP_ROOT / "reports" / "app" / "V2APP_BP_ENGEL_COLONY_SIMULATION_CONTRACT_VERIFIER.md"
BP_CHECKPOINT_PATH = APP_ROOT / "memory" / "V2APP_BP_ENGEL_COLONY_SIMULATION_CONTRACT_VERIFIER.json"
BQ_REPORT_PATH = APP_ROOT / "reports" / "app" / "V2APP_BQ_ENGEL_COLONY_SIMULATION_STATUS_ROUTE_DESIGN.md"
BQ_CHECKPOINT_PATH = APP_ROOT / "memory" / "V2APP_BQ_ENGEL_COLONY_SIMULATION_STATUS_ROUTE_DESIGN.json"
BRA_REPORT_PATH = APP_ROOT / "reports" / "app" / "V2APP_BRA_ENGEL_COLONY_SIMULATION_FUTURE_OUTPUT_VERIFIER.md"
BRA_CHECKPOINT_PATH = APP_ROOT / "memory" / "V2APP_BRA_ENGEL_COLONY_SIMULATION_FUTURE_OUTPUT_VERIFIER.json"
BR_REPORT_PATH = APP_ROOT / "reports" / "app" / "V2APP_BR_ENGEL_COLONY_SIMULATION_READ_ONLY_ROUTES.md"
BR_CHECKPOINT_PATH = APP_ROOT / "memory" / "V2APP_BR_ENGEL_COLONY_SIMULATION_READ_ONLY_ROUTES.json"
BR_FOLLOWUP_REPORT_PATH = APP_ROOT / "reports" / "app" / "V2APP_BR_FOLLOWUP_READ_ONLY_SIMULATION_ROUTE_VERIFIER_HARDENING.md"
BR_FOLLOWUP_CHECKPOINT_PATH = APP_ROOT / "memory" / "V2APP_BR_FOLLOWUP_READ_ONLY_SIMULATION_ROUTE_VERIFIER_HARDENING.json"

STANDARD_VERIFIER = "tools\\verify_colony_simulation_contract.py"
EXTERNAL_PROJECT_TOKEN = "miro" + "fish"
OLD_PROVIDER_PATTERNS = [
    "Ol" + "lama",
    "local" + "host:" + "11" + "434",
    "11" + "434",
]
ACTIVE_DOC_CONFIG_FILES = [
    APP_ROOT / "memory" / "COLONY_SIMULATION_CONTRACT_V1.json",
    APP_ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json",
    APP_ROOT / "memory" / "ENGEL_COMMANDS.md",
    APP_ROOT / "memory" / "STANDARD_VERIFIER_CHECKLIST_V1.md",
    APP_ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md",
    BO_REPORT_PATH,
    BO_CHECKPOINT_PATH,
    BP_REPORT_PATH,
    BP_CHECKPOINT_PATH,
    BQ_REPORT_PATH,
    BQ_CHECKPOINT_PATH,
    BRA_REPORT_PATH,
    BRA_CHECKPOINT_PATH,
    BR_REPORT_PATH,
    BR_CHECKPOINT_PATH,
    BR_FOLLOWUP_REPORT_PATH,
    BR_FOLLOWUP_CHECKPOINT_PATH,
    Path(__file__).resolve(),
]
ACTIVE_OLD_PROVIDER_FILES = [
    APP_ROOT / "engel_app.py",
    APP_ROOT / "engel_companion.py",
    APP_ROOT / "engel_research_brain_v2.py",
    APP_ROOT / "memory" / "ENGEL_COMMANDS.md",
    APP_ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json",
    APP_ROOT / "memory" / "COLONY_AUTONOMY_LADDER_V1.json",
    APP_ROOT / "memory" / "COLONY_PROPOSAL_AUTONOMY_V1.json",
    APP_ROOT / "memory" / "COLONY_SIMULATION_CONTRACT_V1.json",
    APP_ROOT / "memory" / "BRAIN_BACKENDS.json",
    APP_ROOT / "memory" / "BRAIN_BACKEND_LAYER_V1.md",
    APP_ROOT / "memory" / "OFFLINE_BRAIN_GUARD_V1.md",
    APP_ROOT / "memory" / "ENGEL_BRAIN_RULES.md",
    APP_ROOT / "prompts" / "ENGEL_SYSTEM.md",
]
STAGED_ACTIVATION_FILES = [
    APP_ROOT / "engel_app.py",
    APP_ROOT / "engel_research_brain_v2.py",
    APP_ROOT / "memory" / "COLONY_AUTONOMY_LADDER_V1.json",
    APP_ROOT / "memory" / "COLONY_PROPOSAL_AUTONOMY_V1.json",
    APP_ROOT / "memory" / "COLONY_SIMULATION_CONTRACT_V1.json",
    APP_ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json",
]
EXPECTED_LEVEL_2_INHERITANCE = {
    "V2APP_BL_LEVEL_2_PROPOSAL_AUTONOMY_CONTRACT",
    "V2APP_BM_LEVEL_2_PROPOSAL_CONTENT_TESTS",
    "V2APP_BN_LEVEL_2_PROPOSAL_DOC_MATRIX_ALIGNMENT",
}
EXPECTED_FORBIDDEN_MUTATIONS = {
    "trusted_memory",
    "source_files",
    "route_matrices",
    "learning_queues",
    "proposal_queues",
    "digest_history",
    "ALIVE_STATE",
}
EXPECTED_FUTURE_ROUTE_SHAPES = {
    "colony simulation status": "READ_ONLY_STATUS_ONLY_CONTRACT_ONLY",
    "colony simulation contract": "READ_ONLY_STATUS_ONLY_CONTRACT_ONLY",
    "colony simulation preview": "READ_ONLY_DRY_RUN_LOCAL_ONLY_NO_WRITE",
    "colony simulation preview APPROVE_REPORT": "FUTURE_APPROVE_REPORT_REPORT_ONLY_LOCAL_ONLY",
}
FUTURE_STATUS_ROUTE = "colony simulation status"
FUTURE_CONTRACT_ROUTE = "colony simulation contract"
FUTURE_ROUTE_OUTPUT_REQUIREMENTS = [
    ("read_only", ["READ_ONLY"]),
    ("dry_run", ["DRY_RUN"]),
    ("contract_only", ["CONTRACT_ONLY"]),
    ("no_write", ["NO_WRITE"]),
    ("runtime_disabled", ["simulation runtime is disabled", "simulation_runtime_enabled false"]),
    ("execution_not_implemented", ["simulation execution is not implemented"]),
    ("autonomy_disabled", ["runtime_autonomy_enabled false"]),
    ("level_2_disabled", ["runtime_level_2_enabled false"]),
    ("no_round_execution", ["no routes execute simulation rounds"]),
    ("seed_untrusted", ["seeds are untrusted bounded local prompt/spec inputs", "simulation seeds: untrusted bounded local prompt/spec inputs", "untrusted bounded local prompt/spec inputs"]),
    ("personas_untrusted", ["simulated personas are untrusted draft entities only", "untrusted draft entities only"]),
    ("rounds_report_only", ["interaction rounds are dry-run/report-only artifacts", "dry-run/report-only artifacts"]),
    ("outputs_proposal_candidates", ["simulation outputs are proposal candidates only", "outputs: proposal candidates only", "proposal candidates only"]),
    ("outputs_not_trusted_memory", ["simulation outputs are not trusted memory", "not trusted memory"]),
    ("no_trusted_memory_mutation", ["cannot mutate trusted memory", "forbidden mutations: trusted memory"]),
    ("no_source_mutation", ["cannot mutate source files", "forbidden mutations: source files"]),
    ("no_route_matrix_mutation", ["cannot mutate route matrices", "forbidden mutations: route matrices"]),
    ("no_learning_queue_mutation", ["cannot mutate learning queues", "forbidden mutations: learning queues"]),
    ("no_proposal_queue_mutation", ["cannot mutate proposal queues", "forbidden mutations: proposal queues"]),
    ("no_digest_history_write", ["cannot write digest/history", "forbidden mutations: digest/history"]),
    ("no_alive_state_write", ["cannot write ALIVE_STATE", "forbidden mutations: ALIVE_STATE"]),
]
FUTURE_ROUTE_SOURCE_FILES = [
    APP_ROOT / "engel_app.py",
    APP_ROOT / "engel_research_brain_v2.py",
]
IMPLEMENTED_READ_ONLY_ROUTES = {
    FUTURE_STATUS_ROUTE: "future_status_route_output_design",
    FUTURE_CONTRACT_ROUTE: "future_contract_route_output_design",
}
SENSITIVE_ROOTS = [
    APP_ROOT / "memory",
    APP_ROOT / "reports",
]
NORMAL_CLI_LOG_WRITES = {
    "memory\\MAIN_AGENT_LOG.md",
}
REPORT_ARTIFACT_ROOTS = [
    APP_ROOT / "reports" / "proposal_autonomy",
    APP_ROOT / "reports" / "colony_autonomy",
    APP_ROOT / "reports" / "swarm_trails",
    APP_ROOT / "reports" / "colony",
    APP_ROOT / "reports" / "worker_ants",
    APP_ROOT / "reports" / "colony_simulation",
    APP_ROOT / "reports" / "proposal_autonomy" / "simulation_previews",
]
STATUS_NO_REPORT_COMMANDS = [
    FUTURE_STATUS_ROUTE,
    FUTURE_CONTRACT_ROUTE,
    "route regression status",
    "verification set status",
]
SOURCE_SLICE_GUARDS = {
    APP_ROOT / "engel_app.py": [
        "def colony_simulation_status",
        "def colony_simulation_contract",
        'if lower_msg == "colony simulation status"',
        'if lower_msg == "colony simulation contract"',
    ],
    APP_ROOT / "engel_research_brain_v2.py": [
        "def _colony_simulation_contract_config",
        "def _colony_simulation_output_lines",
        "def colony_simulation_status",
        "def colony_simulation_contract",
    ],
}
FORBIDDEN_ROUTE_SOURCE_PATTERNS = [
    "APPROVE_REPORT",
    "REPORT_ONLY",
    ".write_text(",
    ".open(",
    "write_file(",
    "json.dump",
    ".mkdir(",
    ".unlink(",
    ".replace(",
    "subprocess.Popen",
    "threading.Thread",
    "multiprocessing",
    "daemon=True",
    "start_new_session",
    "DETACHED_PROCESS",
    "while True",
    "requests.",
    "urllib.",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "research_runner",
    "research_search",
    "completion_digest",
    "live_research",
    "ALIVE_STATE_FILE",
    "QUEUE_FILE",
    "PROPOSALS_FILE",
    "RESEARCH_DIGEST_LATEST_FILE",
    "RESEARCH_TOPIC_HISTORY_FILE",
]


class CheckFailure(Exception):
    pass


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CheckFailure(f"missing JSON file: {path.relative_to(APP_ROOT)}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CheckFailure(f"JSON root must be an object: {path.relative_to(APP_ROOT)}")
    return data


def fail_if(condition: bool, message: str) -> None:
    if condition:
        raise CheckFailure(message)


def require_false(data: dict[str, Any], key: str, label: str = "") -> None:
    if data.get(key) is not False:
        raise CheckFailure((label or "object") + f" must keep {key}=false")


def require_true(data: dict[str, Any], key: str, label: str = "") -> None:
    if data.get(key) is not True:
        raise CheckFailure((label or "object") + f" must keep {key}=true")


def text_contains_any(text: str, candidates: list[str]) -> bool:
    lowered = text.lower()
    return any(candidate.lower() in lowered for candidate in candidates)


def require_any_token(text: str, candidates: list[str], context: str, label: str) -> None:
    if not text_contains_any(text, candidates):
        raise CheckFailure(context + " missing " + label + " token; expected one of: " + ", ".join(candidates))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_signature(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    if path.is_file():
        stat = path.stat()
        return {
            "exists": True,
            "type": "file",
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": sha256(path),
        }
    if path.is_dir():
        stat = path.stat()
        return {
            "exists": True,
            "type": "dir",
            "mtime_ns": stat.st_mtime_ns,
            "file_count": len([p for p in path.rglob("*") if p.is_file()]),
        }
    return {"exists": True, "type": "other"}


def snapshot_sensitive_tree() -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for root in SENSITIVE_ROOTS:
        if not root.exists():
            snapshot[str(root.relative_to(APP_ROOT))] = {"exists": False}
            continue
        snapshot[str(root.relative_to(APP_ROOT))] = file_signature(root)
        for path in sorted(root.rglob("*")):
            if path.is_file() or path.is_dir():
                snapshot[str(path.relative_to(APP_ROOT))] = file_signature(path)
    return snapshot


def snapshot_roots(roots: list[Path]) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for root in roots:
        if not root.exists():
            snapshot[str(root.relative_to(APP_ROOT))] = {"exists": False}
            continue
        snapshot[str(root.relative_to(APP_ROOT))] = file_signature(root)
        for path in sorted(root.rglob("*")):
            if path.is_file() or path.is_dir():
                snapshot[str(path.relative_to(APP_ROOT))] = file_signature(path)
    return snapshot


def snapshot_diff(before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]) -> list[str]:
    diff: list[str] = []
    keys = sorted(set(before) | set(after))
    for key in keys:
        if before.get(key) != after.get(key):
            if key in NORMAL_CLI_LOG_WRITES:
                continue
            diff.append(key)
    return diff


def assert_no_report_artifact_change(command: str) -> str:
    before = snapshot_roots(REPORT_ARTIFACT_ROOTS)
    output = run_engel_cli(command)
    after = snapshot_roots(REPORT_ARTIFACT_ROOTS)
    diff = snapshot_diff(before, after)
    if diff:
        raise CheckFailure(command + " created or changed report artifacts:\n" + "\n".join(diff[:30]))
    return output


def run_engel_cli(command: str) -> str:
    proc = subprocess.run(
        [sys.executable, str(ENGEL_APP)],
        input=command + "\nexit\n",
        text=True,
        capture_output=True,
        cwd=str(APP_ROOT),
        timeout=90,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if proc.returncode != 0:
        raise CheckFailure(command + " CLI route failed:\n" + proc.stdout + proc.stderr)
    return proc.stdout


def assert_no_external_token_in_json_keys(data: Any, path: str = "$") -> None:
    token = EXTERNAL_PROJECT_TOKEN.lower()
    if isinstance(data, dict):
        for key, value in data.items():
            if token in str(key).lower():
                raise CheckFailure(f"external project name found in JSON key at {path}.{key}")
            assert_no_external_token_in_json_keys(value, f"{path}.{key}")
    elif isinstance(data, list):
        for index, value in enumerate(data):
            assert_no_external_token_in_json_keys(value, f"{path}[{index}]")


def check_contract_schema() -> None:
    data = load_json(CONTRACT_PATH)

    if data.get("version") != "V1":
        raise CheckFailure("contract version must remain V1")
    if data.get("colony_identity") != "Engel":
        raise CheckFailure("contract colony_identity must remain Engel")
    if data.get("mode") != "CONTRACT_ONLY":
        raise CheckFailure("contract mode must remain CONTRACT_ONLY")
    if data.get("status") != "DISABLED_BY_DEFAULT":
        raise CheckFailure("contract status must remain DISABLED_BY_DEFAULT")
    require_false(data, "simulation_runtime_enabled", "contract")
    require_false(data, "runtime_autonomy_enabled", "contract")
    require_false(data, "runtime_level_2_enabled", "contract")
    require_true(data, "one_companion_identity", "contract")
    require_true(data, "shutdown_with_engel", "contract")
    require_true(data, "external_swarm_simulation_prior_art", "contract")
    require_false(data, "external_swarm_simulation_dependency", "contract")

    inherited = set(data.get("inherits_level_2_constraints_from", []))
    missing_inheritance = sorted(EXPECTED_LEVEL_2_INHERITANCE - inherited)
    if missing_inheritance:
        raise CheckFailure("missing Level 2 inheritance entries: " + ", ".join(missing_inheritance))

    boundary = data.get("boundary")
    if not isinstance(boundary, dict):
        raise CheckFailure("boundary must be an object")
    for key in [
        "no_runtime_execution",
        "no_agent_loops",
        "no_background_workers",
        "no_provider_calls",
        "no_live_research",
        "no_internet_actions",
        "no_trust_changing_actions",
    ]:
        require_true(boundary, key, "boundary")

    seed = data.get("simulation_seed")
    if not isinstance(seed, dict):
        raise CheckFailure("simulation_seed must be an object")
    if "bounded local prompt" not in str(seed.get("definition", "")).lower():
        raise CheckFailure("simulation_seed must describe bounded local prompt/spec inputs")
    require_false(seed, "trusted", "simulation_seed")
    require_false(seed, "can_trigger_runtime_execution", "simulation_seed")
    require_false(seed, "can_mutate_state", "simulation_seed")

    entities = data.get("simulated_entities")
    if not isinstance(entities, dict):
        raise CheckFailure("simulated_entities must be an object")
    if "untrusted draft" not in str(entities.get("description", "")).lower():
        raise CheckFailure("simulated_entities must be untrusted draft entities")
    for key in [
        "separate_companion_identity",
        "trusted_memory",
        "can_apply_learning",
        "can_edit_source",
        "can_mutate_queues",
        "can_write_digest_history",
        "can_write_alive_state",
    ]:
        require_false(entities, key, "simulated_entities")
    require_true(entities, "must_be_labeled_untrusted_draft", "simulated_entities")

    rounds = data.get("interaction_rounds")
    if not isinstance(rounds, dict):
        raise CheckFailure("interaction_rounds must be an object")
    if "dry-run/report-only" not in str(rounds.get("definition", "")).lower():
        raise CheckFailure("interaction_rounds must remain dry-run/report-only artifacts")
    require_false(rounds, "runtime_enabled_now", "interaction_rounds")
    for key in ["must_not_run_in_background", "must_not_call_providers", "must_not_start_live_research", "must_not_mutate_state"]:
        require_true(rounds, key, "interaction_rounds")

    outputs = data.get("prediction_and_proposal_outputs")
    if not isinstance(outputs, dict):
        raise CheckFailure("prediction_and_proposal_outputs must be an object")
    if outputs.get("classification") != "proposal_candidates_only":
        raise CheckFailure("simulation outputs must remain proposal_candidates_only")
    for key in ["trusted_memory", "applied_lessons", "queue_mutations", "source_edits"]:
        require_false(outputs, key, "prediction_and_proposal_outputs")
    require_true(outputs, "must_inherit_level_2_constraints", "prediction_and_proposal_outputs")

    forbidden = set(data.get("forbidden_mutations", []))
    missing_forbidden = sorted(EXPECTED_FORBIDDEN_MUTATIONS - forbidden)
    if missing_forbidden:
        raise CheckFailure("missing forbidden mutations: " + ", ".join(missing_forbidden))

    locations = set(data.get("allowed_future_report_only_output_locations", []))
    expected_locations = {"reports\\colony_simulation", "reports\\proposal_autonomy\\simulation_previews"}
    if locations != expected_locations:
        raise CheckFailure("future report-only output locations changed unexpectedly")

    routes = data.get("future_route_shapes_documentation_only")
    if not isinstance(routes, list):
        raise CheckFailure("future_route_shapes_documentation_only must be a list")
    by_command = {str(route.get("command", "")): route for route in routes if isinstance(route, dict)}
    for command, expected_behavior in EXPECTED_FUTURE_ROUTE_SHAPES.items():
        route = by_command.get(command)
        if not route:
            raise CheckFailure("missing future route shape: " + command)
        if route.get("expected_behavior") != expected_behavior:
            raise CheckFailure("future route expected behavior mismatch: " + command)
        if command in IMPLEMENTED_READ_ONLY_ROUTES:
            require_true(route, "implemented_now", command)
        else:
            require_false(route, "implemented_now", command)
        require_false(route, "should_execute_in_test", command)

    safety = data.get("safety_contract")
    if not isinstance(safety, dict):
        raise CheckFailure("safety_contract must be an object")
    for key in [
        "runtime_autonomy_enabled",
        "runtime_level_2_enabled",
        "simulation_runtime_enabled",
        "agent_loops",
        "background_workers",
        "provider_calls",
        "live_research",
        "internet_actions",
        "trusted_memory_writes",
        "source_edits",
        "learning_apply",
        "queue_mutation",
        "digest_history_writes",
        "alive_state_writes",
    ]:
        require_false(safety, key, "safety_contract")

    assert_no_external_token_in_json_keys(data)


def check_future_output_design() -> None:
    data = load_json(CONTRACT_PATH)
    designs = {
        FUTURE_STATUS_ROUTE: data.get("future_status_route_output_design"),
        FUTURE_CONTRACT_ROUTE: data.get("future_contract_route_output_design"),
    }
    token_checks = data.get("future_route_verifier_token_checks")
    if not isinstance(token_checks, dict):
        raise CheckFailure("future_route_verifier_token_checks must be present")

    for command, design in designs.items():
        if not isinstance(design, dict):
            raise CheckFailure(command + " output design must be an object")
        if design.get("command") != command:
            raise CheckFailure(command + " output design command mismatch")
        require_true(design, "implemented_now", command + " output design")
        lines = design.get("exact_output_lines")
        if not isinstance(lines, list) or not lines:
            raise CheckFailure(command + " exact_output_lines must be a non-empty list")
        output_text = "\n".join(str(line) for line in lines)
        if command == FUTURE_STATUS_ROUTE and "# Colony Simulation Status" not in output_text:
            raise CheckFailure("status output design missing title")
        if command == FUTURE_CONTRACT_ROUTE and "# Colony Simulation Contract" not in output_text:
            raise CheckFailure("contract output design missing title")

        route_tokens = token_checks.get(command)
        if not isinstance(route_tokens, list) or not route_tokens:
            raise CheckFailure(command + " verifier token checks must be a non-empty list")
        token_text = "\n".join(str(token) for token in route_tokens)

        for label, candidates in FUTURE_ROUTE_OUTPUT_REQUIREMENTS:
            require_any_token(output_text, candidates, command + " exact output", label)
            require_any_token(token_text, candidates, command + " verifier tokens", label)


def check_manifest_alignment() -> None:
    manifest = load_json(MANIFEST_PATH)
    if manifest.get("mode") != "DOCUMENTATION_ONLY":
        raise CheckFailure("manifest mode must remain DOCUMENTATION_ONLY")
    require_false(manifest, "runtime_feature_enabled", "manifest")
    require_false(manifest, "runs_automatically", "manifest")
    verifiers = manifest.get("standard_verifiers")
    if not isinstance(verifiers, list):
        raise CheckFailure("manifest standard_verifiers must be a list")
    if STANDARD_VERIFIER not in verifiers:
        raise CheckFailure("simulation contract verifier missing from standard_verifiers")

    expectation = manifest.get("colony_simulation_contract_expectations")
    if not isinstance(expectation, dict):
        raise CheckFailure("missing colony_simulation_contract_expectations")
    if expectation.get("source_checkpoint") != "V2APP_BO_ENGEL_COLONY_SIMULATION_CONTRACT":
        raise CheckFailure("simulation expectation source_checkpoint must use Engel-native ID")
    if expectation.get("config_path") != "memory\\COLONY_SIMULATION_CONTRACT_V1.json":
        raise CheckFailure("simulation expectation config_path mismatch")
    require_false(expectation, "external_swarm_simulation_dependency", "simulation expectations")
    require_false(expectation, "simulation_runtime_enabled", "simulation expectations")
    require_false(expectation, "runtime_level_2_enabled", "simulation expectations")
    require_false(expectation, "runtime_autonomy_enabled", "simulation expectations")
    if expectation.get("simulation_outputs_are") != "proposal_candidates_only":
        raise CheckFailure("simulation expectation outputs must be proposal_candidates_only")
    for ref_key in [
        "future_status_route_output_design_ref",
        "future_contract_route_output_design_ref",
        "future_route_verifier_token_checks_ref",
    ]:
        if ref_key not in expectation:
            raise CheckFailure("simulation expectation missing " + ref_key)
    must_include = expectation.get("future_status_contract_outputs_must_include")
    if not isinstance(must_include, list):
        raise CheckFailure("future_status_contract_outputs_must_include must be a list")
    must_include_text = "\n".join(str(item) for item in must_include)
    for label, candidates in [
        ("read_only", ["READ_ONLY"]),
        ("dry_run", ["DRY_RUN"]),
        ("contract_only", ["CONTRACT_ONLY"]),
        ("no_write", ["NO_WRITE"]),
        ("runtime_disabled", ["simulation runtime is disabled"]),
        ("execution_not_implemented", ["simulation execution is not implemented"]),
        ("no_round_execution", ["no routes execute simulation rounds"]),
        ("forbidden_mutations", ["trusted memory", "source files", "route matrices", "learning queues", "proposal queues", "digest/history", "ALIVE_STATE"]),
    ]:
        require_any_token(must_include_text, candidates, "manifest future status/contract output requirements", label)

    inherited = set(expectation.get("inherits_level_2_constraints_from", []))
    missing = sorted(EXPECTED_LEVEL_2_INHERITANCE - inherited)
    if missing:
        raise CheckFailure("simulation expectations missing inheritance: " + ", ".join(missing))

    entries = manifest.get("route_regression_matrix_entries")
    if not isinstance(entries, list):
        raise CheckFailure("manifest route_regression_matrix_entries must be a list")
    by_command = {str(entry.get("command", "")): entry for entry in entries if isinstance(entry, dict)}
    for command, expected_behavior in {
        "colony simulation status": "READ_ONLY_STATUS_ONLY_CONTRACT_ONLY",
        "colony simulation contract": "READ_ONLY_STATUS_ONLY_CONTRACT_ONLY",
        "colony simulation preview": "FUTURE_READ_ONLY_DRY_RUN_LOCAL_ONLY_NO_WRITE",
        "colony simulation preview APPROVE_REPORT": "FUTURE_APPROVE_REPORT_REPORT_ONLY_LOCAL_ONLY",
    }.items():
        entry = by_command.get(command)
        if not entry:
            raise CheckFailure("manifest missing simulation matrix entry: " + command)
        if entry.get("expected_behavior") != expected_behavior:
            raise CheckFailure("simulation matrix expected behavior mismatch: " + command)
        if command in IMPLEMENTED_READ_ONLY_ROUTES:
            require_true(entry, "implemented_now", command)
        else:
            require_false(entry, "implemented_now", command)
        require_false(entry, "should_execute_in_test", command)

    safety = manifest.get("safety_contract")
    if not isinstance(safety, dict):
        raise CheckFailure("manifest safety_contract must be an object")
    for key in [
        "runtime_level_2_enabled",
        "runtime_autonomy_enabled",
        "loops_enabled",
        "background_workers",
        "live_research",
        "provider_calls",
        "trusted_memory_writes",
        "source_edits",
        "learning_apply",
        "queue_mutation",
        "digest_history_writes",
        "alive_state_writes",
    ]:
        require_false(safety, key, "manifest safety_contract")

    assert_no_external_token_in_json_keys(manifest)


def check_implemented_read_only_simulation_routes() -> None:
    data = load_json(CONTRACT_PATH)
    token_checks = data.get("future_route_verifier_token_checks")
    if not isinstance(token_checks, dict):
        raise CheckFailure("future_route_verifier_token_checks must be present")

    for command, design_key in IMPLEMENTED_READ_ONLY_ROUTES.items():
        design = data.get(design_key)
        if not isinstance(design, dict):
            raise CheckFailure(command + " design missing")
        expected_lines = design.get("exact_output_lines")
        if not isinstance(expected_lines, list) or not expected_lines:
            raise CheckFailure(command + " exact output lines missing")

        before = snapshot_sensitive_tree()
        report_before = snapshot_roots(REPORT_ARTIFACT_ROOTS)
        output = run_engel_cli(command)
        after = snapshot_sensitive_tree()
        report_after = snapshot_roots(REPORT_ARTIFACT_ROOTS)
        diff = snapshot_diff(before, after)
        if diff:
            raise CheckFailure(command + " changed files unexpectedly:\n" + "\n".join(diff[:30]))
        report_diff = snapshot_diff(report_before, report_after)
        if report_diff:
            raise CheckFailure(command + " changed report artifacts unexpectedly:\n" + "\n".join(report_diff[:30]))

        for line in expected_lines:
            if str(line) not in output:
                raise CheckFailure(command + " CLI output missing exact line: " + str(line))

        route_tokens = token_checks.get(command)
        if not isinstance(route_tokens, list):
            raise CheckFailure(command + " verifier token list missing")
        token_text = "\n".join(str(token) for token in route_tokens)
        for label, candidates in FUTURE_ROUTE_OUTPUT_REQUIREMENTS:
            require_any_token(output, candidates, command + " CLI output", label)
            require_any_token(token_text, candidates, command + " verifier tokens", label)

        for forbidden in [
            "REPORT_ONLY",
            "APPROVE_REPORT",
            "report written",
            "simulation preview",
            "simulation round executed",
        ]:
            if forbidden.lower() in output.lower():
                raise CheckFailure(command + " output contains forbidden runtime/report wording: " + forbidden)


def check_status_commands_create_no_reports() -> None:
    for command in STATUS_NO_REPORT_COMMANDS:
        output = assert_no_report_artifact_change(command)
        if command in IMPLEMENTED_READ_ONLY_ROUTES:
            for label, candidates in FUTURE_ROUTE_OUTPUT_REQUIREMENTS:
                require_any_token(output, candidates, command + " no-report CLI output", label)


def source_window(text: str, marker: str, before: int = 4, after: int = 18) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if marker in line:
            start = max(0, index - before)
            end = min(len(lines), index + after + 1)
            return "\n".join(lines[start:end])
    raise CheckFailure("source marker not found: " + marker)


def check_simulation_route_source_slices_safe() -> None:
    matches: list[str] = []
    for path, markers in SOURCE_SLICE_GUARDS.items():
        if not path.exists():
            raise CheckFailure("source file missing for route guard: " + str(path.relative_to(APP_ROOT)))
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in markers:
            window = source_window(text, marker)
            for pattern in FORBIDDEN_ROUTE_SOURCE_PATTERNS:
                if pattern.lower() in window.lower():
                    matches.append(f"{path.relative_to(APP_ROOT)}:{marker}: forbidden pattern {pattern}")
    if matches:
        raise CheckFailure("simulation route source slices contain forbidden behavior:\n" + "\n".join(matches[:30]))


def check_no_simulation_preview_or_report_implementation() -> None:
    forbidden_snippets = [
        "colony simulation preview",
        "colony simulation preview approve_report",
        "reports\\colony_simulation",
        "reports/colony_simulation",
        "colony_simulation_report",
        "colony_simulation_preview",
    ]
    matches: list[str] = []
    for path in FUTURE_ROUTE_SOURCE_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        lowered = text.lower()
        for snippet in forbidden_snippets:
            if snippet.lower() not in lowered:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if snippet.lower() in line.lower():
                    matches.append(f"{path.relative_to(APP_ROOT)}:{lineno}:{line.strip()}")
    if matches:
        raise CheckFailure("simulation route/preview/report implementation appears to exist:\n" + "\n".join(matches[:30]))


def check_engel_native_naming() -> None:
    old_report = APP_ROOT / "reports" / "app" / f"V2APP_BO_{EXTERNAL_PROJECT_TOKEN.upper()}_COLONY_SIMULATION_CONTRACT.md"
    old_checkpoint = APP_ROOT / "memory" / f"V2APP_BO_{EXTERNAL_PROJECT_TOKEN.upper()}_COLONY_SIMULATION_CONTRACT.json"
    fail_if(old_report.exists(), "old external-name report filename still exists")
    fail_if(old_checkpoint.exists(), "old external-name checkpoint filename still exists")
    fail_if(not BO_REPORT_PATH.exists(), "Engel-native BO report filename missing")
    fail_if(not BO_CHECKPOINT_PATH.exists(), "Engel-native BO checkpoint filename missing")

    regex = re.compile(re.escape(EXTERNAL_PROJECT_TOKEN), re.IGNORECASE)
    matches: list[str] = []
    for path in ACTIVE_DOC_CONFIG_FILES:
        if not path.exists():
            continue
        if regex.search(path.name):
            matches.append(str(path.relative_to(APP_ROOT)))
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                matches.append(f"{path.relative_to(APP_ROOT)}:{lineno}:{line.strip()}")
    if matches:
        raise CheckFailure("external project name found in current active/BO/BP files:\n" + "\n".join(matches[:30]))

    checkpoint = load_json(BO_CHECKPOINT_PATH)
    if checkpoint.get("id") != "V2APP_BO_ENGEL_COLONY_SIMULATION_CONTRACT":
        raise CheckFailure("BO checkpoint id must use Engel-native naming")
    assert_no_external_token_in_json_keys(checkpoint)


def check_no_external_import_or_dependency() -> None:
    regex = re.compile(
        rf"(^\s*(import|from)\s+{re.escape(EXTERNAL_PROJECT_TOKEN)}|{re.escape(EXTERNAL_PROJECT_TOKEN)}\s*(==|>=|<=|~=))",
        re.IGNORECASE | re.MULTILINE,
    )
    candidates: list[Path] = []
    for pattern in ["*.py", "requirements*.txt", "pyproject.toml", "setup.cfg", "setup.py"]:
        candidates.extend(APP_ROOT.rglob(pattern))
    matches: list[str] = []
    for path in sorted(set(candidates)):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in regex.finditer(text):
            line = text[: match.start()].count("\n") + 1
            matches.append(f"{path.relative_to(APP_ROOT)}:{line}")
    if matches:
        raise CheckFailure("external project import/dependency found:\n" + "\n".join(matches[:30]))


def check_no_old_provider_or_enabled_flags() -> None:
    old_regex = re.compile("|".join(re.escape(item) for item in OLD_PROVIDER_PATTERNS), re.IGNORECASE)
    matches: list[str] = []
    for path in ACTIVE_OLD_PROVIDER_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if old_regex.search(line):
                matches.append(f"{path.relative_to(APP_ROOT)}:{lineno}:{line.strip()}")
    if matches:
        raise CheckFailure("active old-provider/local endpoint match found:\n" + "\n".join(matches[:30]))

    enabled_patterns = [
        re.compile(r"STAGED_DRAFT_ACTIVE\s*=\s*True"),
        re.compile(r"runtime_autonomy_enabled\s+true", re.IGNORECASE),
        re.compile(r"runtime_level_2_enabled\s+true", re.IGNORECASE),
    ]
    enabled_matches: list[str] = []
    for path in STAGED_ACTIVATION_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in enabled_patterns):
                enabled_matches.append(f"{path.relative_to(APP_ROOT)}:{lineno}:{line.strip()}")
    if enabled_matches:
        raise CheckFailure("forbidden enabled flag found:\n" + "\n".join(enabled_matches[:30]))


def pass_check(name: str) -> None:
    print(f"PASS {name}")


def main() -> int:
    try:
        check_contract_schema()
        pass_check("colony_simulation_contract_schema")
        check_future_output_design()
        pass_check("future_status_contract_output_token_expectations")
        check_manifest_alignment()
        pass_check("route_verification_manifest_alignment")
        check_implemented_read_only_simulation_routes()
        pass_check("implemented_read_only_simulation_routes_no_write")
        check_status_commands_create_no_reports()
        pass_check("simulation_and_status_commands_create_no_reports")
        check_simulation_route_source_slices_safe()
        pass_check("simulation_route_source_slices_safe")
        check_no_simulation_preview_or_report_implementation()
        pass_check("no_simulation_preview_or_report_implementation")
        check_engel_native_naming()
        pass_check("engel_native_naming_no_external_project_name")
        check_no_external_import_or_dependency()
        pass_check("no_external_project_import_or_dependency")
        check_no_old_provider_or_enabled_flags()
        pass_check("no_active_old_provider_or_forbidden_enabled_flags")
    except CheckFailure as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1

    print("\nCOLONY_SIMULATION_CONTRACT_VERIFICATION_PASS")
    print(f"contract={CONTRACT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
