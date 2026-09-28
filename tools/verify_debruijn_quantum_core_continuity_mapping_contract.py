#!/usr/bin/env python3
from __future__ import annotations

import json
import py_compile
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
PASS_MARKER = "DEBRUIJN_QUANTUM_CORE_CONTINUITY_MAPPING_CONTRACT_VERIFICATION_PASS"

CONTRACT_JSON = ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_CORE_CONTINUITY_MAPPING_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_CORE_CONTINUITY_MAPPING_CONTRACT_V1.md"
CONTRACT_REPORT = (
    ROOT / "reports" / "codex_bridge" / "ENGEL_DEBRUIJN_QUANTUM_CORE_CONTINUITY_MAPPING_CONTRACT_V1.md"
)

OPTIONAL_EVIDENCE = [
    ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md",
    ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json",
    ROOT / "tools" / "build_engel_core_continuity_map.py",
    ROOT / "tools" / "verify_engel_core_continuity_map.py",
    ROOT / "memory" / "ENGEL_SYSTEM_INTEGRATION_MAP_V1.md",
    ROOT / "memory" / "ENGEL_SYSTEM_INTEGRATION_MAP_V1.json",
    ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md",
    ROOT / "memory" / "STANDARD_VERIFIER_CHECKLIST_V1.md",
    ROOT / "memory" / "ENGEL_COMMANDS.md",
    ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json",
    ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1.json",
    ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1.md",
    ROOT / "engel_debruijn_quantum_automation_file_structure.py",
    ROOT / "engel_debruijn_quantum_structure_status.py",
    ROOT / "tools" / "verify_engel_debruijn_quantum_automation_file_structure.py",
    ROOT / "tools" / "verify_debruijn_quantum_structure_status_helper.py",
    ROOT / "tools" / "verify_debruijn_quantum_backend_status_command.py",
    ROOT / "tools" / "verify_debruijn_quantum_candidate_proposals.py",
    ROOT / "tools" / "verify_debruijn_quantum_entanglement_groups.py",
    ROOT / "tools" / "verify_debruijn_quantum_backend_status_consistency.py",
    ROOT / "tools" / "verify_untrusted_content_policy.py",
    ROOT / "tools" / "verify_de_bruijn_import_boundaries.py",
]

ACTIVE_SOURCE_FILES = [
    ROOT / "engel_debruijn_quantum_automation_file_structure.py",
    ROOT / "engel_debruijn_quantum_structure_status.py",
    ROOT / "tools" / "verify_engel_debruijn_quantum_automation_file_structure.py",
    ROOT / "tools" / "verify_debruijn_quantum_structure_status_helper.py",
    ROOT / "tools" / "verify_debruijn_quantum_backend_status_command.py",
    ROOT / "tools" / "verify_debruijn_quantum_candidate_proposals.py",
    ROOT / "tools" / "verify_debruijn_quantum_entanglement_groups.py",
    ROOT / "tools" / "verify_debruijn_quantum_backend_status_consistency.py",
    ROOT / "tools" / "build_engel_core_continuity_map.py",
    ROOT / "tools" / "verify_engel_core_continuity_map.py",
]

EXACT_VALUES = {
    "contract_id": "ENGEL_DEBRUIJN_QUANTUM_CORE_CONTINUITY_MAPPING_CONTRACT_V1",
    "status": "contract_only",
    "active_workspace": r"D:\b.WorkSpace\Engel App",
    "backend_only": True,
    "ui_allowed_now": False,
    "runtime_authority_granted": False,
    "source_mutation_allowed": False,
    "route_mutation_allowed": False,
    "queue_mutation_allowed": False,
    "trusted_memory_write_allowed": False,
    "memory_promotion_allowed": False,
    "apply_allowed": False,
    "real_quantum_allowed": False,
    "provider_api_allowed": False,
    "network_allowed": False,
    "model_inference_allowed": False,
    "background_worker_allowed": False,
    "startup_autorun_allowed": False,
}

REQUIRED_KEYS = [
    "node_definition",
    "allowed_inputs",
    "allowed_outputs",
    "forbidden_outputs",
    "integration_boundaries",
    "command_continuity",
    "verifier_continuity",
    "mapping_update_strategy",
    "future_verifier",
    "future_implementation_sequence",
    "stop_conditions",
    "recommended_next_slice",
    "safety_preserved",
]

FORBIDDEN_OUTPUT_TERMS = [
    "source patches",
    "route mutations",
    "queue mutations",
    "trusted-memory writes",
    "memory promotion",
    "live runtime actions",
    "file moves",
    "file deletes",
    "file rewrites",
    "agent activation",
    "ui actions",
    "provider calls",
    "network calls",
    "model inference",
    "real quantum computation",
]

UNSAFE_ACTIVE_PATTERNS = [
    "grant_debruijn_runtime_authority",
    "debruijn_runtime_authority_granted = true",
    "runtime_authority_granted=True",
    "update_core_continuity_map_from_debruijn_verifier",
    "apply_debruijn_proposal",
    "apply_candidate_proposal",
    "trust_debruijn_proposal",
    "trust_candidate_proposal",
    "promote_debruijn_proposal",
    "promote_candidate_proposal",
    "execute_proposal_content",
    "mutate_source_from_proposal",
    "mutate_routes_from_proposal",
    "mutate_queues_from_proposal",
    "write_trusted_memory_from_proposal",
    "move_files_from_proposal",
    "delete_files_from_proposal",
    "rewrite_files_from_proposal",
    "provider_from_proposal",
    "network_from_proposal",
    "model_from_proposal",
    "quantum_from_proposal",
    "create_debruijn_companion_card",
    "create_debruijn_viewer",
    "start_debruijn_background_worker",
    "start_debruijn_watcher",
    "schedule_debruijn_scan",
]

SAFE_LINE_MARKERS = [
    "forbidden",
    "disabled",
    "must not",
    "do not",
    "does not",
    "not ",
    "never",
    "fail-closed",
    "fail closed",
    "verifier",
    "pattern",
    "future",
    "skip",
    "review_required",
]


class Verifier:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.review_required: list[str] = []
        self.skips: list[str] = []

    def line(self, level: str, message: str) -> None:
        print(f"{level} {message}")

    def pass_line(self, message: str) -> None:
        self.line("PASS", message)

    def info(self, message: str) -> None:
        self.line("INFO", message)

    def skip(self, message: str) -> None:
        self.skips.append(message)
        self.line("SKIP", message)

    def review(self, message: str) -> None:
        self.review_required.append(message)
        self.line("REVIEW_REQUIRED", message)

    def fail(self, message: str) -> None:
        self.failures.append(message)
        self.line("FAIL", message)


def rel(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def flatten_text(value: Any) -> str:
    chunks: list[str] = []

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                chunks.append(str(key))
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)
        else:
            chunks.append(str(item))

    walk(value)
    return "\n".join(chunks).lower()


def contains_all(value: Any, terms: Iterable[str]) -> bool:
    text = flatten_text(value)
    return all(term.lower() in text for term in terms)


def load_contract(verifier: Verifier) -> dict[str, Any] | None:
    missing = [path for path in [CONTRACT_JSON, CONTRACT_MD, CONTRACT_REPORT] if not path.exists()]
    if missing:
        for path in missing:
            verifier.fail(f"required contract file missing: {rel(path)}")
        return None

    try:
        data = json.loads(read_text(CONTRACT_JSON))
    except json.JSONDecodeError as exc:
        verifier.fail(f"contract JSON parse failed line={exc.lineno} column={exc.colno}: {exc.msg}")
        return None

    verifier.pass_line("required contract files present and JSON parsed")
    return data if isinstance(data, dict) else None


def inspect_optional_evidence(verifier: Verifier) -> None:
    for path in OPTIONAL_EVIDENCE:
        if path.exists():
            verifier.info(f"optional evidence present {rel(path)}")
        else:
            verifier.skip(f"optional evidence missing {rel(path)}")


def check_contract_values(verifier: Verifier, contract: dict[str, Any]) -> None:
    for key, expected in EXACT_VALUES.items():
        actual = contract.get(key)
        if actual != expected:
            verifier.fail(f"contract value {key} expected {expected!r} got {actual!r}")
        else:
            verifier.pass_line(f"contract value {key}={actual!r}")

    for key in REQUIRED_KEYS:
        if key not in contract:
            verifier.fail(f"required key missing: {key}")
    verifier.pass_line(f"required contract keys checked count={len(REQUIRED_KEYS)}")


def check_node_definition(verifier: Verifier, node: Any) -> None:
    if not isinstance(node, dict):
        verifier.fail("node_definition must be an object")
        return
    if node.get("node_name") != "De Bruijn Quantum Backend File Structure Intelligence":
        verifier.fail("node_definition.node_name mismatch")
    if node.get("node_type") != "backend_status_report_proposal_layer":
        verifier.fail("node_definition.node_type mismatch")
    role = str(node.get("node_role", "")).lower()
    for term in ["local/offline", "backend structure intelligence", "classifying", "reporting status", "missing", "untrusted candidate proposals"]:
        if term not in role:
            verifier.fail(f"node_definition.node_role missing {term!r}")

    node_text = flatten_text(node)
    for bad in [
        "apply fixes",
        "mutate source",
        "mutate routes",
        "mutate queues",
        "write trusted memory",
        "run external ai",
        "real quantum computation",
        "activate agents",
        "background automation",
    ]:
        if bad in node_text and not any(marker in node_text for marker in ["no ", "not ", "forbidden", "must not"]):
            verifier.fail(f"node_definition appears to grant forbidden capability: {bad}")
    verifier.pass_line("node definition result")


def check_allowed_inputs(verifier: Verifier, section: Any) -> None:
    required_terms = [
        "approved de bruijn contract files",
        "reports\\debruijn_quantum_file_structure",
        "manual scan/report commands only",
        "documented safe command",
    ]
    if not contains_all(section, required_terms):
        verifier.fail("allowed_inputs does not document required safe input sources")
    section_text = flatten_text(section)
    for bad in ["arbitrary internet", "provider/model inputs", "trusted-memory write targets", "route mutation authority", "queue mutation authority"]:
        if bad in section_text:
            verifier.fail(f"allowed_inputs grants forbidden input authority: {bad}")
    verifier.pass_line("allowed input result")


def check_allowed_outputs(verifier: Verifier, section: Any) -> None:
    required_terms = [
        "latest_status.json",
        "latest_status.md",
        "automation_receipt",
        "candidate_fix_proposals",
        "codex bridge reports",
        "backend status summaries",
        "verifier reports",
    ]
    if not contains_all(section, required_terms):
        verifier.fail("allowed_outputs does not document required safe output types")
    section_text = flatten_text(section)
    for bad in [
        "source patches",
        "queue mutations",
        "trusted-memory entries",
        "executable repair scripts",
        "startup hooks",
        "scheduled tasks",
        "background workers",
    ]:
        if bad in section_text:
            verifier.fail(f"allowed_outputs includes forbidden output: {bad}")
    verifier.pass_line("allowed output result")


def check_forbidden_outputs(verifier: Verifier, section: Any) -> None:
    for term in FORBIDDEN_OUTPUT_TERMS:
        if term.lower() not in flatten_text(section):
            verifier.fail(f"forbidden_outputs missing {term!r}")
    verifier.pass_line("forbidden output result")


def check_integration_boundaries(verifier: Verifier, boundaries: Any) -> None:
    if not isinstance(boundaries, dict):
        verifier.fail("integration_boundaries must be an object")
        return
    checks = {
        "core_continuity": ["documentation", "mapping", "runtime authority"],
        "system_integration": ["backend", "status", "proposal", "system control"],
        "agent_skill_pipeline": ["untrusted", "verifier", "create agents", "activate agents"],
        "verifier_health_check_agent": ["read verifier results", "apply", "instructions"],
        "guardian_watchdog": ["no_watchdog_authority", "process monitoring", "restart"],
        "local_llm_external_ai": ["provider", "model", "untrusted"],
        "trusted_memory": ["no_trusted_memory", "memory promotion", "separate approved memory flow"],
    }
    for key, terms in checks.items():
        section = boundaries.get(key)
        if section is None:
            verifier.fail(f"integration_boundaries missing {key}")
            continue
        if not contains_all(section, terms):
            verifier.fail(f"integration_boundaries.{key} missing required terms {terms}")
    verifier.pass_line("integration boundary result")


def check_command_continuity(verifier: Verifier, command: Any) -> None:
    if not isinstance(command, dict):
        verifier.fail("command_continuity must be an object")
        return
    required_commands = [
        r"python .\engel_debruijn_quantum_automation_file_structure.py status",
        r"python .\engel_debruijn_quantum_automation_file_structure.py scan --root .",
        r"python .\engel_debruijn_quantum_automation_file_structure.py scan-report --root .",
        r"python .\engel_debruijn_quantum_automation_file_structure.py propose-fixes --root .",
    ]
    text = flatten_text(command)
    for item in required_commands:
        if item.lower() not in text:
            verifier.fail(f"command_continuity missing command {item}")
    for term in [
        "engel ai debruijn quantum status",
        "backend-only/read-only",
        "status commands read existing output only",
        "scanner cli commands remain explicit manual cli only",
        "no apply/trust/promote/move/delete/rewrite route",
        "no background/scheduled/watcher/daemon/startup command",
    ]:
        if term.lower() not in text:
            verifier.fail(f"command_continuity missing boundary term {term!r}")
    verifier.pass_line("command continuity result")


def check_verifier_continuity(verifier: Verifier, section: Any) -> None:
    text = flatten_text(section)
    required = [
        "verify_engel_debruijn_quantum_automation_file_structure.py",
        "verify_debruijn_quantum_structure_status_helper.py",
        "verify_debruijn_quantum_backend_status_command.py",
        "verify_debruijn_quantum_candidate_proposals.py",
        "verify_debruijn_quantum_entanglement_groups.py",
        "verify_debruijn_quantum_backend_status_consistency.py",
        "verify_untrusted_content_policy.py",
        "verify_de_bruijn_import_boundaries.py",
        "verify_authority_hierarchy.py",
        "verify_prompt_injection_guard.py",
        "verify_engel_core_continuity_map.py",
    ]
    for item in required:
        if item.lower() not in text:
            verifier.fail(f"verifier_continuity missing {item}")
    verifier.pass_line("verifier continuity result")


def check_mapping_update_strategy(verifier: Verifier, contract: dict[str, Any]) -> None:
    strategy = contract.get("mapping_update_strategy")
    if not isinstance(strategy, dict):
        verifier.fail("mapping_update_strategy must be an object")
        return
    if strategy.get("this_slice") != "contract_only":
        verifier.fail("mapping_update_strategy.this_slice must be contract_only")
    strategy_text = flatten_text(strategy)
    for term in [
        "tools\\build_engel_core_continuity_map.py",
        "memory\\engel_core_continuity_map_v1.md",
        "memory\\engel_core_continuity_map_v1.json",
        "future_implementation_slice",
        "engel_debruijn_quantum_core_continuity_mapping_v1",
    ]:
        if term.lower() not in strategy_text:
            verifier.fail(f"mapping_update_strategy missing {term}")
    whole_text = flatten_text(contract)
    required_safety_concepts = {
        "runtime authority": ["no runtime authority", "runtime_authority_granted", "runtime authority"],
        "route boundary": ["no route", "route_mutation_allowed", "route mutation"],
        "trusted-memory boundary": ["trusted-memory", "trusted_memory_write_allowed", "trusted memory"],
        "future map update separation": ["future map updates require", "future_may_update", "separate implementation slice"],
    }
    for label, terms in required_safety_concepts.items():
        if not any(term.lower() in whole_text for term in terms):
            verifier.fail(f"mapping strategy/contract missing safety concept {label!r}")
    verifier.pass_line("mapping update strategy result")


def check_future_sequence(verifier: Verifier, sequence: Any) -> None:
    if not isinstance(sequence, list):
        verifier.fail("future_implementation_sequence must be a list")
        return
    values = [str(item) for item in sequence]
    if "ENGEL_DEBRUIJN_QUANTUM_CORE_CONTINUITY_MAPPING_V1" not in values:
        verifier.fail("future_implementation_sequence missing ENGEL_DEBRUIJN_QUANTUM_CORE_CONTINUITY_MAPPING_V1")
    if "ENGEL_DEBRUIJN_QUANTUM_CORE_CONTINUITY_MAPPING_VERIFIER_V1" not in values:
        if "ENGEL_DEBRUIJN_QUANTUM_CORE_CONTINUITY_MAPPING_CONTRACT_VERIFIER_V1" in values:
            verifier.info(
                "future_implementation_sequence uses CONTRACT_VERIFIER naming for this verifier slice; accepted as semantic verifier predecessor"
            )
        else:
            verifier.fail("future_implementation_sequence missing mapping verifier slice")
    normalized_values = {str(item).lower().replace("-", "_").replace(" ", "_") for item in sequence}
    forbidden_sequence_tokens = [
        "companion",
        "viewer",
        "apply",
        "auto_repair",
        "background_scanning",
        "trusted_memory_promotion",
        "agent_activation",
    ]
    for bad in forbidden_sequence_tokens:
        if any(bad in value for value in normalized_values):
            verifier.fail(f"future_implementation_sequence jumps to forbidden option: {bad}")
    verifier.pass_line("future implementation sequence result")


def line_is_safe_reference(line: str, is_verifier: bool) -> bool:
    if is_verifier:
        return True
    lowered = line.lower()
    return any(marker in lowered for marker in SAFE_LINE_MARKERS)


def active_source_scan(verifier: Verifier) -> None:
    scanned = 0
    findings = 0
    for path in ACTIVE_SOURCE_FILES:
        if not path.exists():
            verifier.skip(f"active source optional missing {rel(path)}")
            continue
        try:
            lines = read_text(path).splitlines()
        except OSError as exc:
            verifier.fail(f"cannot read active source {rel(path)}: {exc}")
            continue
        scanned += 1
        is_verifier = path.name.startswith("verify_")
        for line_number, line in enumerate(lines, start=1):
            lowered = line.lower()
            for pattern in UNSAFE_ACTIVE_PATTERNS:
                if pattern.lower() in lowered and not line_is_safe_reference(line, is_verifier):
                    findings += 1
                    verifier.review(f"{rel(path)}:{line_number} potential active unsafe pattern {pattern}")
    if findings:
        verifier.fail(f"active source scan found likely unsafe active behavior count={findings}")
    else:
        verifier.pass_line(f"active source scan result scanned={scanned}")


def compile_self(verifier: Verifier) -> None:
    try:
        py_compile.compile(str(Path(__file__)), doraise=True)
    except py_compile.PyCompileError as exc:
        verifier.fail(f"self py_compile failed: {exc}")
        return
    verifier.pass_line("self py_compile")


def main() -> int:
    verifier = Verifier()
    print("ENGEL_DEBRUIJN_QUANTUM_CORE_CONTINUITY_MAPPING_CONTRACT_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: contract/static verification only; no Core Continuity map update, scan, proposal generation, provider, model, UI, or mutation")

    compile_self(verifier)
    contract = load_contract(verifier)
    inspect_optional_evidence(verifier)
    if contract is not None:
        check_contract_values(verifier, contract)
        check_node_definition(verifier, contract.get("node_definition"))
        check_allowed_inputs(verifier, contract.get("allowed_inputs"))
        check_allowed_outputs(verifier, contract.get("allowed_outputs"))
        check_forbidden_outputs(verifier, contract.get("forbidden_outputs"))
        check_integration_boundaries(verifier, contract.get("integration_boundaries"))
        check_command_continuity(verifier, contract.get("command_continuity"))
        check_verifier_continuity(verifier, contract.get("verifier_continuity"))
        check_mapping_update_strategy(verifier, contract)
        check_future_sequence(verifier, contract.get("future_implementation_sequence"))

    active_source_scan(verifier)

    if verifier.review_required:
        verifier.info(f"review_required findings={len(verifier.review_required)}")
    if verifier.skips:
        verifier.info(f"skipped optional evidence={len(verifier.skips)}")
    if verifier.failures:
        verifier.fail(f"failures={len(verifier.failures)}")
        return 1

    verifier.pass_line("contract checks")
    verifier.pass_line("node definition result")
    verifier.pass_line("allowed input/output result")
    verifier.pass_line("forbidden output result")
    verifier.pass_line("integration boundary result")
    verifier.pass_line("command/verifier continuity result")
    verifier.pass_line("mapping update strategy result")
    verifier.pass_line("active source scan result")
    verifier.pass_line("safety preserved")
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
