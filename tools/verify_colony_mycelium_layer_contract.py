from __future__ import annotations

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
RESEARCH_BRAIN = APP_ROOT / "engel_research_brain_v2.py"
CONTRACT_PATH = APP_ROOT / "memory" / "COLONY_MYCELIUM_LAYER_CONTRACT_V1.json"
MANIFEST_PATH = APP_ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
COMMANDS_PATH = APP_ROOT / "memory" / "ENGEL_COMMANDS.md"
CHECKLIST_PATH = APP_ROOT / "memory" / "STANDARD_VERIFIER_CHECKLIST_V1.md"
PROJECT_MEMORY_INDEX_PATH = APP_ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md"

STANDARD_VERIFIER = "tools\\verify_colony_mycelium_layer_contract.py"
EXPECTED_ROUTES = ["colony mycelium status", "colony mycelium contract"]
ABSENT_MYCELIUM_ROUTES = [
    "colony mycelium preview",
    "colony mycelium report",
    "colony mycelium APPROVE_REPORT",
    "colony mycelium candidates",
    "colony mycelium candidate create",
]
EXPECTED_ROUTE_STATUS = "implemented/read-only"
EXPECTED_ROUTE_BEHAVIOR = {
    "colony mycelium status": "READ_ONLY_STATUS_ONLY_CONTRACT_ONLY_NO_RUNTIME_NO_WRITE",
    "colony mycelium contract": "READ_ONLY_CONTRACT_ONLY_NO_RUNTIME_NO_WRITE",
}
EXPECTED_DISABLED_TOKENS = [
    "MYCELIUM_RUNTIME_DISABLED",
    "SIGNAL_PROPAGATION_DISABLED",
    "READ_ONLY_FIRST",
    "UNTRUSTED_SIGNALS",
    "PROPOSAL_CANDIDATES_ONLY",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_EDIT",
    "NO_ROUTE_MUTATION",
    "NO_QUEUE_MUTATION",
    "NO_AUTONOMY_STATE_MUTATION",
    "NO_APPLIED_LEARNING",
    "NO_BACKGROUND_WORKER",
    "NO_AUTONOMOUS_LOOP",
    "NO_PROVIDER_CALL",
    "NO_NETWORK_CALL",
    "NO_LIVE_RESEARCH",
    "NO_INTERNET_BEHAVIOR",
    "NO_DIGEST_WRITE",
    "NO_ALIVE_STATE_WRITE",
]
EXPECTED_SIGNAL_TYPES = [
    "warnings",
    "context markers",
    "confidence markers",
    "candidate lessons",
    "proposal candidate references",
    "report references",
    "memory references",
    "route status references",
    "verifier status references",
    "lesson candidate readiness references",
    "living learning status references",
    "simulation status references",
]
EXPECTED_REFERENCE_POINTS = [
    "colony agents",
    "reports",
    "memory references",
    "proposal candidates",
    "route status",
    "lesson candidate readiness",
    "living learning status",
    "simulation status",
    "verifiers",
]
EXPECTED_ROUTE_OUTPUT_REQUIREMENTS = [
    "implemented/read-only",
    "contract-only",
    "no runtime",
    "no write behavior",
    "no signal propagation execution",
    "no background worker",
    "no autonomy",
]
STATUS_REQUIRED_TOKENS = [
    "READ_ONLY",
    "STATUS_ONLY",
    "CONTRACT_ONLY",
    "RUNTIME_DISABLED",
    "SIGNAL_PROPAGATION_DISABLED",
    "UNTRUSTED_SIGNALS",
    "PROPOSAL_CANDIDATES_ONLY",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_EDIT",
    "NO_ROUTE_MUTATION",
    "NO_QUEUE_MUTATION",
    "NO_AUTONOMY_STATE_MUTATION",
    "NO_APPLIED_LEARNING",
    "NO_DIGEST_WRITE",
    "NO_ALIVE_STATE_WRITE",
    "NO_PROVIDER_CALL",
    "NO_NETWORK_CALL",
    "NO_BACKGROUND_WORKER",
    "NO_AUTONOMOUS_LOOP",
]
STATUS_REQUIRED_SECTIONS = [
    "current state",
    "signal boundary",
    "allowed untrusted signal references",
    "forbidden mutations",
    "relationship to living learning status",
    "relationship to lesson candidates",
    "relationship to proposal candidates",
    "relationship to simulation status",
    "verifier guard summary",
    "next safe step",
]
CONTRACT_REQUIRED_TOKENS = [
    "READ_ONLY",
    "CONTRACT_ONLY",
    "RUNTIME_DISABLED",
    "SIGNAL_PROPAGATION_DISABLED",
    "UNTRUSTED_SIGNALS",
    "STRUCTURAL_ANALOGY_ONLY",
    "NO_LITERAL_HIVE_MIND_CLAIM",
    "NO_HUMAN_LIKE_FOREST_INTELLIGENCE_CLAIM",
    "PROPOSAL_CANDIDATES_ONLY",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_EDIT",
    "NO_ROUTE_MUTATION",
    "NO_QUEUE_MUTATION",
    "NO_AUTONOMY_STATE_MUTATION",
    "NO_APPLIED_LEARNING",
    "NO_DIGEST_WRITE",
    "NO_ALIVE_STATE_WRITE",
    "NO_PROVIDER_CALL",
    "NO_NETWORK_CALL",
    "NO_BACKGROUND_WORKER",
    "NO_AUTONOMOUS_LOOP",
]
CONTRACT_REQUIRED_SECTIONS = [
    "contract purpose",
    "structural analogy rule",
    "disabled runtime boundaries",
    "untrusted signal model",
    "allowed references",
    "proposal-candidate-only outputs",
    "forbidden writes and mutations",
    "future route contract",
    "verifier expectations",
    "stop conditions",
]
FALSE_CONTRACT_KEYS = [
    "runtime_feature_enabled",
    "mycelium_runtime_enabled",
    "signal_propagation_runtime_enabled",
    "implemented_now",
    "runtime_autonomy_enabled",
    "runtime_level_2_enabled",
    "STAGED_DRAFT_ACTIVE",
    "background_workers",
    "autonomous_loops",
    "provider_calls",
    "api_calls",
    "network_calls",
    "live_research",
    "internet_behavior",
    "trusted_memory_writes",
    "source_edits",
    "route_mutation",
    "queue_mutation",
    "autonomy_state_mutation",
    "applied_learning",
    "digest_history_writes",
    "alive_state_writes",
]
FALSE_OUTPUT_KEYS = {
    "trusted_memory",
    "applied_lessons",
    "queue_mutations",
    "route_mutations",
    "source_edits",
    "autonomy_state_changes",
    "digest_history_writes",
    "ALIVE_STATE_writes",
}
BLOCKED_RUNTIME_BEHAVIORS = [
    "mycelium runtime",
    "signal propagation runtime",
    "background worker",
    "autonomous loop",
    "provider/API/network call",
    "live research",
    "internet behavior",
    "trusted-memory write",
    "source edit",
    "route mutation",
    "queue mutation",
    "autonomy state mutation",
    "applied learning",
    "digest/history write",
    "ALIVE_STATE write",
]
ACTIVE_SOURCE_FILES = [ENGEL_APP, RESEARCH_BRAIN]
ACTIVE_DOC_CONFIG_FILES = [
    CONTRACT_PATH,
    MANIFEST_PATH,
    COMMANDS_PATH,
    CHECKLIST_PATH,
    PROJECT_MEMORY_INDEX_PATH,
    APP_ROOT / "reports" / "app" / "V2APP_CN_ENGEL_MYCELIUM_LAYER_CONTRACT.md",
    APP_ROOT / "memory" / "V2APP_CN_ENGEL_MYCELIUM_LAYER_CONTRACT.json",
    APP_ROOT / "reports" / "app" / "V2APP_CO_MYCELIUM_CONTRACT_DRIFT_GUARD.md",
    APP_ROOT / "memory" / "V2APP_CO_MYCELIUM_CONTRACT_DRIFT_GUARD.json",
    APP_ROOT / "reports" / "app" / "V2APP_CP_MYCELIUM_STATUS_CONTRACT_OUTPUT_DESIGN.md",
    APP_ROOT / "memory" / "V2APP_CP_MYCELIUM_STATUS_CONTRACT_OUTPUT_DESIGN.json",
    APP_ROOT / "reports" / "app" / "V2APP_CQ_MYCELIUM_OUTPUT_DOCUMENTATION_DRIFT_GUARD.md",
    APP_ROOT / "memory" / "V2APP_CQ_MYCELIUM_OUTPUT_DOCUMENTATION_DRIFT_GUARD.json",
    APP_ROOT / "reports" / "app" / "V2APP_CS_MYCELIUM_READ_ONLY_ROUTES.md",
    APP_ROOT / "memory" / "V2APP_CS_MYCELIUM_READ_ONLY_ROUTES.json",
    APP_ROOT / "reports" / "app" / "V2APP_CT_MYCELIUM_READ_ONLY_ROUTE_DRIFT_GUARD.md",
    APP_ROOT / "memory" / "V2APP_CT_MYCELIUM_READ_ONLY_ROUTE_DRIFT_GUARD.json",
]
NORMAL_CLI_LOG_WRITES = {"memory\\MAIN_AGENT_LOG.md"}
SENSITIVE_ROOTS = [
    APP_ROOT / "memory",
    APP_ROOT / "reports",
    APP_ROOT / "queues",
    APP_ROOT / "queue",
    APP_ROOT / "digest",
    APP_ROOT / "history",
]


class CheckFailure(Exception):
    pass


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CheckFailure("missing JSON file: " + str(path.relative_to(APP_ROOT)))
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CheckFailure("JSON root must be object: " + str(path.relative_to(APP_ROOT)))
    return data


def pass_check(name: str) -> None:
    print("PASS " + name)


def require_false(data: dict[str, Any], key: str, label: str) -> None:
    if data.get(key) is not False:
        raise CheckFailure(f"{label}.{key} must be false")


def require_contains_all(values: Any, expected: list[str], label: str) -> None:
    if not isinstance(values, list):
        raise CheckFailure(label + " must be a list")
    missing = [item for item in expected if item not in values]
    if missing:
        raise CheckFailure(label + " missing: " + ", ".join(missing))


def require_text_all(text: str, expected: list[str], label: str) -> None:
    lowered = text.lower()
    missing = [item for item in expected if item.lower() not in lowered]
    if missing:
        raise CheckFailure(label + " missing text: " + ", ".join(missing))


def require_text_any(text: str, options: list[str], label: str) -> None:
    lowered = text.lower()
    if not any(option.lower() in lowered for option in options):
        raise CheckFailure(label + " missing one of: " + ", ".join(options))


def read_text(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing file: " + str(path.relative_to(APP_ROOT)))
    return path.read_text(encoding="utf-8", errors="ignore")


def run_engel(command: str) -> str:
    proc = subprocess.run(
        [sys.executable, str(ENGEL_APP)],
        input=command + "\nexit\n",
        cwd=APP_ROOT,
        text=True,
        capture_output=True,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if proc.returncode != 0:
        raise CheckFailure(f"Engel command failed: {command}\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout


def file_signature(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def snapshot_sensitive_tree() -> dict[str, dict[str, int]]:
    snapshot: dict[str, dict[str, int]] = {}
    for root in SENSITIVE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                snapshot[str(path.relative_to(APP_ROOT))] = file_signature(path)
    return snapshot


def assert_no_sensitive_change(before: dict[str, dict[str, int]], after: dict[str, dict[str, int]], label: str) -> None:
    before_keys = set(before)
    after_keys = set(after)
    new_paths = sorted(path for path in after_keys - before_keys if path not in NORMAL_CLI_LOG_WRITES)
    removed_paths = sorted(before_keys - after_keys)
    modified_paths = sorted(
        path for path in before_keys & after_keys if before[path] != after[path] and path not in NORMAL_CLI_LOG_WRITES
    )
    if new_paths or removed_paths or modified_paths:
        raise CheckFailure(
            label
            + " changed sensitive files: new="
            + ", ".join(new_paths[:20])
            + " removed="
            + ", ".join(removed_paths[:20])
            + " modified="
            + ", ".join(modified_paths[:20])
        )


def check_contract_schema() -> None:
    data = load_json(CONTRACT_PATH)
    if data.get("mode") != "CONTRACT_ONLY":
        raise CheckFailure("mycelium contract mode must be CONTRACT_ONLY")
    if data.get("contract_status") != "DOCUMENTATION_CONFIG_ONLY":
        raise CheckFailure("mycelium contract must remain documentation/config only")
    if "read-only-first" not in str(data.get("purpose", "")).lower():
        raise CheckFailure("contract must preserve read-only-first wording")
    for key in FALSE_CONTRACT_KEYS:
        require_false(data, key, "contract")
    if data.get("read_only_routes_implemented") is not True:
        raise CheckFailure("contract.read_only_routes_implemented must be true for CS read-only routes")
    require_contains_all(data.get("disabled_state_tokens"), EXPECTED_DISABLED_TOKENS, "disabled_state_tokens")
    require_contains_all(data.get("connects_reference_points"), EXPECTED_REFERENCE_POINTS, "connects_reference_points")

    signals = data.get("signals")
    if not isinstance(signals, dict):
        raise CheckFailure("signals must be an object")
    if signals.get("trust_status") != "UNTRUSTED":
        raise CheckFailure("signals.trust_status must be UNTRUSTED")
    if signals.get("execution_status") != "DESIGN_ONLY_NO_RUNTIME":
        raise CheckFailure("signals.execution_status must be DESIGN_ONLY_NO_RUNTIME")
    require_contains_all(signals.get("may_carry"), EXPECTED_SIGNAL_TYPES, "signals.may_carry")
    require_contains_all(
        signals.get("must_not_carry_as_authority"),
        [
            "trusted memory",
            "applied lessons",
            "queue mutations",
            "route mutations",
            "source edits",
            "autonomy-state changes",
            "digest/history writes",
            "ALIVE_STATE writes",
        ],
        "signals.must_not_carry_as_authority",
    )

    outputs = data.get("outputs_are")
    if not isinstance(outputs, dict):
        raise CheckFailure("outputs_are must be an object")
    if outputs.get("proposal_candidates_only") is not True:
        raise CheckFailure("outputs must remain proposal candidates only")
    for key in FALSE_OUTPUT_KEYS:
        if outputs.get(key) is not False:
            raise CheckFailure("outputs_are." + key + " must be false")
    require_contains_all(data.get("blocked_runtime_behaviors"), BLOCKED_RUNTIME_BEHAVIORS, "blocked_runtime_behaviors")
    require_contains_all(
        data.get("future_route_output_requirements"),
        EXPECTED_ROUTE_OUTPUT_REQUIREMENTS,
        "future_route_output_requirements",
    )
    check_read_only_route_shapes(data.get("read_only_route_shapes"), "contract read-only route shapes")
    check_future_output_design(data, "contract")


def check_read_only_route_shapes(values: Any, label: str) -> None:
    if not isinstance(values, list):
        raise CheckFailure(label + " must be a list")
    entries = {item.get("command"): item for item in values if isinstance(item, dict)}
    for route in EXPECTED_ROUTES:
        entry = entries.get(route)
        if not entry:
            raise CheckFailure(label + " missing " + route)
        if entry.get("implemented_now") is not True:
            raise CheckFailure(route + " implemented_now must be true")
        if entry.get("should_execute_in_test") is not False:
            raise CheckFailure(route + " should_execute_in_test must be false")
        if entry.get("expected_behavior") != EXPECTED_ROUTE_BEHAVIOR[route]:
            raise CheckFailure(route + " expected_behavior drifted")
        if entry.get("route_status") != EXPECTED_ROUTE_STATUS:
            raise CheckFailure(route + " route_status must be implemented/read-only")
        if entry.get("contract_only") is False:
            raise CheckFailure(route + " must remain contract-only")
        for key in ["no_runtime", "no_write_behavior", "no_signal_propagation_execution", "no_background_worker", "no_autonomy"]:
            if key in entry and entry.get(key) is not True:
                raise CheckFailure(route + " " + key + " must remain true")


def check_future_output_design(data: dict[str, Any], label: str) -> None:
    design = data.get("future_route_output_design")
    if not isinstance(design, dict):
        raise CheckFailure(label + " missing future_route_output_design")
    route_expectations = {
        "colony mycelium status": (STATUS_REQUIRED_TOKENS, STATUS_REQUIRED_SECTIONS),
        "colony mycelium contract": (CONTRACT_REQUIRED_TOKENS, CONTRACT_REQUIRED_SECTIONS),
    }
    for route, (required_tokens, required_sections) in route_expectations.items():
        route_design = design.get(route)
        if not isinstance(route_design, dict):
            raise CheckFailure(label + " missing output design for " + route)
        if route_design.get("implemented_now") is not True:
            raise CheckFailure(label + " " + route + " implemented_now must be true")
        if route_design.get("should_execute_in_test") is not False:
            raise CheckFailure(label + " " + route + " should_execute_in_test must be false")
        if route_design.get("route_status") != EXPECTED_ROUTE_STATUS:
            raise CheckFailure(label + " " + route + " route_status must be implemented/read-only")
        require_contains_all(route_design.get("required_output_tokens"), required_tokens, label + " " + route + " tokens")
        require_contains_all(route_design.get("required_output_sections"), required_sections, label + " " + route + " sections")
        for phrase in EXPECTED_ROUTE_OUTPUT_REQUIREMENTS:
            if phrase not in route_design.get("future_route_output_must_state", []):
                raise CheckFailure(label + " " + route + " missing route output phrase: " + phrase)
        for key in [
            "contract_only",
            "runtime_enabled",
            "write_behavior_enabled",
            "signal_propagation_execution_enabled",
            "background_worker_enabled",
            "autonomy_enabled",
        ]:
            expected = True if key == "contract_only" else False
            if route_design.get(key) is not expected:
                raise CheckFailure(label + " " + route + " " + key + " drifted")


def require_output_design_documentation(text: str, label: str) -> None:
    lowered = text.lower()
    for route in EXPECTED_ROUTES:
        if route not in lowered:
            raise CheckFailure(label + " missing mycelium route name: " + route)
    for phrase in [
        "output expectations",
        "implemented_now: true",
        "should_execute_in_test: false",
        "implemented/read-only",
        "contract-only",
        "no runtime",
        "no write",
        "no signal propagation",
        "no background",
        "no autonomy",
    ]:
        if phrase.lower() not in lowered:
            raise CheckFailure(label + " missing CP/CQ output documentation phrase: " + phrase)
    for token in STATUS_REQUIRED_TOKENS:
        if token not in text:
            raise CheckFailure(label + " missing status output token: " + token)
    for section in STATUS_REQUIRED_SECTIONS:
        if section not in lowered:
            raise CheckFailure(label + " missing status output section: " + section)
    for token in CONTRACT_REQUIRED_TOKENS:
        if token not in text:
            raise CheckFailure(label + " missing contract output token: " + token)
    for section in CONTRACT_REQUIRED_SECTIONS:
        if section not in lowered:
            raise CheckFailure(label + " missing contract output section: " + section)


def check_manifest_alignment() -> None:
    manifest = load_json(MANIFEST_PATH)
    verifiers = manifest.get("standard_verifiers")
    if not isinstance(verifiers, list):
        raise CheckFailure("manifest standard_verifiers must be a list")
    if STANDARD_VERIFIER not in verifiers:
        raise CheckFailure("mycelium verifier missing from standard_verifiers")

    matrix = manifest.get("route_regression_matrix_entries")
    if not isinstance(matrix, list):
        raise CheckFailure("route_regression_matrix_entries must be a list")
    entries = {item.get("command"): item for item in matrix if isinstance(item, dict)}
    for route in EXPECTED_ROUTES:
        entry = entries.get(route)
        if not entry:
            raise CheckFailure("manifest missing route matrix entry: " + route)
        if entry.get("implemented_now") is not True:
            raise CheckFailure(route + " matrix implemented_now must be true")
        if entry.get("should_execute_in_test") is not False:
            raise CheckFailure(route + " matrix should_execute_in_test must be false")
        if entry.get("expected_behavior") != EXPECTED_ROUTE_BEHAVIOR[route]:
            raise CheckFailure(route + " matrix expected_behavior drifted")
        if entry.get("content_contract_ref") != "colony_mycelium_layer_contract_expectations":
            raise CheckFailure(route + " matrix contract ref drifted")
        if entry.get("route_status") != EXPECTED_ROUTE_STATUS:
            raise CheckFailure(route + " matrix route_status must remain implemented/read-only")
        for key in [
            "contract_only",
            "no_runtime",
            "no_write_behavior",
            "no_signal_propagation_execution",
            "no_background_worker",
            "no_autonomy",
        ]:
            if entry.get(key) is not True:
                raise CheckFailure(route + " matrix " + key + " must remain true")

    expectations = manifest.get("colony_mycelium_layer_contract_expectations")
    if not isinstance(expectations, dict):
        raise CheckFailure("manifest missing colony_mycelium_layer_contract_expectations")
    if expectations.get("config_path") != "memory\\COLONY_MYCELIUM_LAYER_CONTRACT_V1.json":
        raise CheckFailure("manifest mycelium config path drifted")
    if expectations.get("drift_guard_verifier") != STANDARD_VERIFIER:
        raise CheckFailure("manifest missing mycelium drift guard verifier path")
    if expectations.get("read_only_routes_checkpoint") != "V2APP_CS_MYCELIUM_READ_ONLY_ROUTES":
        raise CheckFailure("manifest missing CS read-only routes checkpoint")
    if expectations.get("read_only_route_drift_guard_checkpoint") != "V2APP_CT_MYCELIUM_READ_ONLY_ROUTE_DRIFT_GUARD":
        raise CheckFailure("manifest missing CT read-only route drift guard checkpoint")
    if expectations.get("read_only_route_drift_guard_verifier") != STANDARD_VERIFIER:
        raise CheckFailure("manifest missing CT read-only route drift guard verifier")
    if expectations.get("output_documentation_drift_guard_checkpoint") != "V2APP_CQ_MYCELIUM_OUTPUT_DOCUMENTATION_DRIFT_GUARD":
        raise CheckFailure("manifest missing CQ output documentation drift guard checkpoint")
    if expectations.get("output_documentation_drift_guard_verifier") != STANDARD_VERIFIER:
        raise CheckFailure("manifest missing CQ output documentation drift guard verifier")
    for key in [
        "runtime_feature_enabled",
        "mycelium_runtime_enabled",
        "signal_propagation_runtime_enabled",
        "runtime_autonomy_enabled",
        "runtime_level_2_enabled",
    ]:
        require_false(expectations, key, "manifest expectations")
    if expectations.get("signals_are_untrusted") is not True:
        raise CheckFailure("manifest signals_are_untrusted must be true")
    require_contains_all(expectations.get("disabled_state_tokens"), EXPECTED_DISABLED_TOKENS, "manifest disabled_state_tokens")
    require_contains_all(expectations.get("signals_may_carry"), EXPECTED_SIGNAL_TYPES, "manifest signals_may_carry")
    require_contains_all(expectations.get("connects_reference_points"), EXPECTED_REFERENCE_POINTS, "manifest connects_reference_points")
    require_contains_all(expectations.get("future_route_output_must_state"), EXPECTED_ROUTE_OUTPUT_REQUIREMENTS, "manifest future route output")
    require_contains_all(expectations.get("blocked_runtime_behaviors"), BLOCKED_RUNTIME_BEHAVIORS, "manifest blocked runtime behaviors")
    check_read_only_route_shapes(expectations.get("read_only_route_shapes"), "manifest read-only route shapes")
    check_future_output_design(expectations, "manifest")
    require_contains_all(
        expectations.get("documentation_alignment_paths"),
        [
            "memory\\STANDARD_VERIFIER_CHECKLIST_V1.md",
            "memory\\ROUTE_VERIFICATION_SET_V1.json",
            "memory\\PROJECT_MEMORY_INDEX_V2V.md",
        ],
        "manifest documentation_alignment_paths",
    )


def check_docs_alignment() -> None:
    commands = read_text(COMMANDS_PATH)
    checklist = read_text(CHECKLIST_PATH)
    project_index = read_text(PROJECT_MEMORY_INDEX_PATH)
    for text, label in [(commands, "command docs"), (checklist, "checklist"), (project_index, "project memory index")]:
        lowered = text.lower()
        for route in EXPECTED_ROUTES:
            if route not in lowered:
                raise CheckFailure(label + " missing route: " + route)
        require_text_all(text, [
            "implemented_now: true",
            "should_execute_in_test: false",
            "implemented read-only",
            "structural analogy",
            "no background",
            "no autonomy",
        ], label)
        require_text_any(text, ["no runtime", "runtime-disabled", "runtime remains disabled"], label)
        require_text_any(text, ["no signal propagation", "signal propagation remain disabled", "signal propagation remains disabled"], label)
        require_text_any(text, ["output expectations", "output tokens"], label)
        require_text_any(text, ["no write behavior", "no-write", "no write"], label)
        require_text_any(text, ["no mycelium preview", "mycelium preview"], label)
        require_text_any(text, ["no mycelium report", "report generation"], label)
        require_text_any(text, ["APPROVE_REPORT"], label)
        require_text_any(text, ["candidate creation", "candidate routes", "candidates"], label)
    for token in EXPECTED_DISABLED_TOKENS:
        if token not in checklist:
            raise CheckFailure("checklist missing disabled token: " + token)


def check_output_documentation_alignment() -> None:
    checklist = read_text(CHECKLIST_PATH)
    project_index = read_text(PROJECT_MEMORY_INDEX_PATH)
    require_output_design_documentation(checklist, "checklist")
    require_output_design_documentation(project_index, "project memory index")
    for checkpoint in ["V2APP-CN", "V2APP-CO", "V2APP-CP", "V2APP-CQ", "V2APP-CS", "V2APP-CT"]:
        if checkpoint not in project_index:
            raise CheckFailure("project memory index missing checkpoint: " + checkpoint)


def check_analogy_rule() -> None:
    data = load_json(CONTRACT_PATH)
    rule = str(data.get("structural_analogy_rule", "")).lower()
    if "structural analogy only" not in rule:
        raise CheckFailure("analogy rule must state structural analogy only")
    if "do not claim forests have a literal hive mind" not in rule:
        raise CheckFailure("analogy rule must reject literal forest hive mind claims")
    if "human-like intelligence" not in rule:
        raise CheckFailure("analogy rule must reject human-like forest intelligence claims")
    forbidden_positive_claims = [
        "forests have a literal hive mind.",
        "forests have literal hive minds.",
        "forests have human-like intelligence.",
        "forests are human-like intelligences.",
    ]
    for path in ACTIVE_DOC_CONFIG_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for claim in forbidden_positive_claims:
            index = text.find(claim)
            if index < 0:
                continue
            prefix = text[max(0, index - 32) : index]
            if "do not claim" not in prefix and "does not claim" not in prefix and "no claim" not in prefix:
                raise CheckFailure(f"positive analogy claim found in {path.relative_to(APP_ROOT)}: {claim}")


def extract_function_source(text: str, function_name: str) -> str:
    match = re.search(r"(?m)^def " + re.escape(function_name) + r"\(.*?\).*:", text)
    if not match:
        raise CheckFailure("missing function: " + function_name)
    next_match = re.search(r"(?m)^def [A-Za-z_][A-Za-z0-9_]*\(.*?\).*:", text[match.end() :])
    end = len(text) if not next_match else match.end() + next_match.start()
    return text[match.start() : end]


def extract_dispatch_source(text: str, route: str) -> str:
    marker = 'if lower_msg == "' + route + '"'
    index = text.lower().find(marker)
    if index < 0:
        raise CheckFailure("missing app dispatch for " + route)
    return text[index : index + 500]


def assert_mycelium_route_output(route: str, output: str) -> None:
    requirements = {
        "colony mycelium status": (STATUS_REQUIRED_TOKENS, STATUS_REQUIRED_SECTIONS),
        "colony mycelium contract": (CONTRACT_REQUIRED_TOKENS, CONTRACT_REQUIRED_SECTIONS),
    }
    required_tokens, required_sections = requirements[route]
    for token in required_tokens:
        if token not in output:
            raise CheckFailure(route + " output missing token: " + token)
    lowered = output.lower()
    for section in required_sections:
        if section not in lowered:
            raise CheckFailure(route + " output missing section: " + section)
    required_boundary_phrases = {
        "colony mycelium status": [
            "Status: READ_ONLY / STATUS_ONLY / CONTRACT_ONLY / NO_WRITE",
            "does not create files, reports, candidates, or runtime signals",
            "does not run verifiers itself",
            "No signal propagation execution is enabled",
            "NO_PROVIDER_CALL",
            "NO_NETWORK_CALL",
            "NO_BACKGROUND_WORKER",
            "NO_AUTONOMOUS_LOOP",
        ],
        "colony mycelium contract": [
            "Status: READ_ONLY / CONTRACT_ONLY / NO_WRITE",
            "Neither route generates reports, creates candidates, runs verifiers, or executes signal propagation",
            "No mycelium runtime, signal propagation execution, background worker, autonomous loop, provider call, or network call is enabled",
            "Signals do not become trusted memory",
            "NO_TRUSTED_MEMORY_WRITE",
            "NO_SOURCE_EDIT",
            "NO_QUEUE_MUTATION",
            "NO_AUTONOMY_STATE_MUTATION",
            "NO_DIGEST_WRITE",
            "NO_ALIVE_STATE_WRITE",
        ],
    }
    for phrase in required_boundary_phrases[route]:
        if phrase.lower() not in lowered:
            raise CheckFailure(route + " output missing read-only boundary phrase: " + phrase)
    forbidden_output_markers = [
        "approve_report",
        "report written",
        "candidate file",
        "running verifier",
        "verification pass",
        "signal propagation started",
        "runtime enabled",
        "trusted write allowed",
        "write completed",
    ]
    for marker in forbidden_output_markers:
        if marker in lowered:
            raise CheckFailure(route + " output contains forbidden execution marker: " + marker)


def check_routes_exist_and_source_slices_are_safe() -> None:
    app_source = read_text(ENGEL_APP)
    brain_source = read_text(RESEARCH_BRAIN)
    app_lowered = app_source.lower()
    brain_lowered = brain_source.lower()
    for route in EXPECTED_ROUTES:
        if 'if lower_msg == "' + route + '"' not in app_lowered:
            raise CheckFailure("app dispatch missing " + route)
    for function_name in [
        "colony_mycelium_status",
        "colony_mycelium_contract",
    ]:
        if "def " + function_name not in app_lowered:
            raise CheckFailure("app wrapper missing " + function_name)
        if "def " + function_name not in brain_lowered:
            raise CheckFailure("research brain route missing " + function_name)

    combined = "\n".join(read_text(path) for path in ACTIVE_SOURCE_FILES)
    lowered = combined.lower()
    forbidden_routes = [
        "colony mycelium preview",
        "colony mycelium approve_report",
        "colony mycelium report",
        "colony mycelium candidate",
        "colony mycelium candidates",
        "mycelium candidate create",
        "mycelium report written",
    ]
    for marker in forbidden_routes:
        if marker in lowered:
            raise CheckFailure("active source contains forbidden mycelium route marker: " + marker)
    forbidden_runtime_markers = [
        "mycelium_runtime_enabled = true",
        '"mycelium_runtime_enabled": true',
        "signal_propagation_runtime_enabled = true",
        '"signal_propagation_runtime_enabled": true',
        "signal propagation loop",
        "mycelium runtime enabled",
    ]
    for marker in forbidden_runtime_markers:
        if marker in lowered:
            raise CheckFailure("active source contains forbidden mycelium runtime marker: " + marker)

    slices = [
        extract_function_source(app_source, "colony_mycelium_status"),
        extract_function_source(app_source, "colony_mycelium_contract"),
        extract_function_source(brain_source, "colony_mycelium_status"),
        extract_function_source(brain_source, "colony_mycelium_contract"),
        extract_dispatch_source(app_source, "colony mycelium status"),
        extract_dispatch_source(app_source, "colony mycelium contract"),
    ]
    forbidden_code_markers = [
        ".write_text(",
        ".write_bytes(",
        "open(",
        ".mkdir(",
        ".unlink(",
        ".replace(",
        "json.dump",
        "json.dumps(",
        "subprocess.",
        "popen(",
        "os.system(",
        "requests.",
        "urllib.",
        "socket.",
        "threading.",
        "multiprocessing.",
        "daemon=true",
        "start_new_session",
        "while true",
        "approve_report",
        "lesson_candidates_review(",
        "colony_proposal_preview(",
        "learning_proposals_apply",
        "route_regression_matrix",
        "verification_set_status_v1(",
        "verify_colony_mycelium_layer_contract()",
        "manual memory",
    ]
    for source_slice in slices:
        slice_lowered = source_slice.lower()
        hits = [marker for marker in forbidden_code_markers if marker in slice_lowered]
        if hits:
            raise CheckFailure("mycelium route source slice contains forbidden marker: " + ", ".join(hits))


def check_mycelium_routes_no_write_and_output() -> None:
    for route in EXPECTED_ROUTES:
        before = snapshot_sensitive_tree()
        output = run_engel(route)
        after = snapshot_sensitive_tree()
        assert_no_sensitive_change(before, after, route)
        assert_mycelium_route_output(route, output)


def check_absent_mycelium_future_routes_no_write() -> None:
    for route in ABSENT_MYCELIUM_ROUTES:
        before = snapshot_sensitive_tree()
        output = run_engel(route)
        after = snapshot_sensitive_tree()
        assert_no_sensitive_change(before, after, route)
        lowered = output.lower()
        forbidden_execution_markers = [
            "# colony mycelium status",
            "# colony mycelium contract",
            "report written",
            "approve_report",
            "candidate created",
            "signal propagation",
            "runtime enabled",
        ]
        hits = [marker for marker in forbidden_execution_markers if marker in lowered]
        if hits:
            raise CheckFailure(route + " unexpectedly matched active mycelium behavior: " + ", ".join(hits))


def check_no_active_old_provider_or_forbidden_flags() -> None:
    patterns = [
        re.compile(r"runtime_autonomy_enabled\s*[:=]\s*true", re.IGNORECASE),
        re.compile(r"runtime_level_2_enabled\s*[:=]\s*true", re.IGNORECASE),
        re.compile(r"STAGED_DRAFT_ACTIVE\s*=\s*True"),
        re.compile("Ol" + "lama", re.IGNORECASE),
        re.compile("local" + "host:" + "11" + "434", re.IGNORECASE),
        re.compile(r"\b11" + "434" + r"\b"),
    ]
    files = [
        ENGEL_APP,
        APP_ROOT / "engel_companion.py",
        RESEARCH_BRAIN,
        CONTRACT_PATH,
        MANIFEST_PATH,
        APP_ROOT / "prompts" / "ENGEL_SYSTEM.md",
    ]
    hits = []
    for path in files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in patterns:
            if pattern.search(text):
                hits.append(str(path.relative_to(APP_ROOT)) + ": " + pattern.pattern)
    if hits:
        raise CheckFailure("active old-provider or forbidden flag match: " + "; ".join(hits[:20]))


def main() -> int:
    checks = [
        ("contract_schema", check_contract_schema),
        ("manifest_alignment", check_manifest_alignment),
        ("docs_alignment", check_docs_alignment),
        ("output_documentation_alignment", check_output_documentation_alignment),
        ("analogy_rule", check_analogy_rule),
        ("routes_exist_and_source_slices_are_safe", check_routes_exist_and_source_slices_are_safe),
        ("mycelium_routes_no_write_and_output", check_mycelium_routes_no_write_and_output),
        ("absent_mycelium_future_routes_no_write", check_absent_mycelium_future_routes_no_write),
        ("no_active_old_provider_or_forbidden_flags", check_no_active_old_provider_or_forbidden_flags),
    ]
    try:
        for name, func in checks:
            func()
            pass_check(name)
    except CheckFailure as exc:
        print("FAIL " + str(exc))
        return 1
    print()
    print("COLONY_MYCELIUM_LAYER_CONTRACT_VERIFICATION_PASS")
    print("contract=" + str(CONTRACT_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
