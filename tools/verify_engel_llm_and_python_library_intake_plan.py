from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN_JSON = ROOT / "memory" / "ENGEL_LLM_AND_PYTHON_LIBRARY_INTAKE_PLAN_V1.json"
PLAN_MD = ROOT / "memory" / "ENGEL_LLM_AND_PYTHON_LIBRARY_INTAKE_PLAN_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_LLM_AND_PYTHON_LIBRARY_INTAKE_PLAN_V1.md"
SYSTEM_INTEGRATION = ROOT / "engel_system_integration_status.py"
CORE_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
CORE_MD = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md"

REQUIRED_STATUSES = [
    "LLM_AND_PYTHON_LIBRARY_INTAKE_PLAN",
    "PLAN_ONLY",
    "INTAKE_CONTRACT_ONLY",
    "HUMAN_REVIEW_REQUIRED",
    "MANUAL_DOWNLOADS_ONLY",
    "APPROVED_LIBRARY_CANDIDATES_ONLY",
    "MODEL_CANDIDATES_NOT_LOADED",
    "PYTHON_DOCS_NOT_EXECUTED",
    "UNTRUSTED_UNTIL_REVIEWED",
    "NOT_TRUSTED_MEMORY",
    "NO_MODEL_LOADING",
    "NO_INFERENCE",
    "NO_TRAINING",
    "NO_AUTO_DOWNLOAD",
    "NO_AUTO_IMPORT",
    "NO_AUTO_MOVE",
    "NO_AUTO_DELETE",
    "NO_PACKAGE_INSTALL",
    "NO_PIP_INSTALL",
    "NO_WSL_EXECUTION",
    "NO_HERMES_EXECUTION",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
]

REQUIRED_LIBRARY_AREAS = [
    "LLM Model Candidates",
    "Embedding Model Candidates",
    "Reranker / Retrieval Model Candidates",
    "Local Inference Runtime References",
    "Python Core Documentation",
    "PySide6 / Qt Documentation",
    "SQLite Documentation",
    "PyInstaller / Packaging Documentation",
    "Testing / Pytest / Unit Testing References",
    "Static Analysis / Linting References",
    "Security / Prompt Injection / Agent Safety References",
    "Python Standard Library References",
    "Code Companion / Patch Planning References",
    "Math / Logic / Reasoning References",
    "Data Structures / Algorithms References",
    "Local Runtime / WSL / Ubuntu References",
    "Hermes Rejection / Do Not Install Boundary Notes",
    "Engel Manuals / Reports / Receipts / Verifiers",
    "Approved Library Human Review Receipts",
    "Future Offline Research Papers",
    "Android Remote Worker reference docs, if future Android companion documentation is added",
]

REQUIRED_FOLDER_REFERENCES = [
    r"G:\ENGEL_APP_MEMORY\library",
    r"G:\ENGEL_APP_MEMORY\library\quarantine",
    r"G:\ENGEL_APP_MEMORY\library\manual_downloads",
    r"G:\ENGEL_APP_MEMORY\library\approved",
    r"G:\ENGEL_APP_MEMORY\models\manual_downloads",
    r"G:\ENGEL_APP_MEMORY\models\reviewed_candidates",
    r"G:\ENGEL_APP_MEMORY\models\approved_runtime_candidates",
    r"G:\ENGEL_APP_MEMORY\models\rejected_or_quarantine",
    r"G:\ENGEL_APP_MEMORY\library\manual_downloads\python_docs",
    r"G:\ENGEL_APP_MEMORY\library\manual_downloads\android_remote_worker_references",
    r"G:\ENGEL_APP_MEMORY\library\approved\python_docs",
    r"G:\ENGEL_APP_MEMORY\library\approved\android_remote_worker_references",
]

REQUIRED_MODEL_TIERS = [
    "Tiny Seed Mode",
    "Daily Local Mode",
    "Research Worker Mode",
    "Alternative Research Worker",
    "Embedding Support Candidate",
    "Reranker Support Candidate",
    "Unsupported Format",
    "Too Large For Current Machine",
    "Not A Model",
    "Unknown Origin / Quarantine",
]

REQUIRED_PYTHON_CATEGORIES = [
    "python_standard_library_docs",
    "python_packaging_docs",
    "pyside6_qt_docs",
    "sqlite_docs",
    "testing_pytest_docs",
    "verifier_patterns",
    "security_prompt_injection_docs",
    "local_agent_safety_docs",
    "code_companion_patch_planning_docs",
    "math_logic_reasoning_docs",
    "algorithms_data_structures_docs",
    "android_remote_worker_reference_docs",
]

REQUIRED_APPROVAL_STATES = [
    "CANDIDATE",
    "HOLD_SOURCE_REVIEW",
    "HOLD_UNSUPPORTED_FORMAT",
    "HOLD_TOO_LARGE",
    "APPROVED_LIBRARY_CANDIDATE",
    "APPROVED_FOR_OFFLINE_REFERENCE",
    "APPROVED_FOR_RUNTIME_CANDIDATE",
    "REJECTED_NOT_A_MODEL",
    "REJECTED_UNSAFE_OR_UNKNOWN",
    "QUARANTINE_CANDIDATE",
]

REQUIRED_RECEIPT_FIELDS = [
    "material_id",
    "material_type",
    "source_path",
    "source_origin",
    "reviewed_by",
    "reviewed_at",
    "decision",
    "decision_reason",
    "approved_category",
    "storage_location",
    "safety_boundary",
    "prompt_injection_review",
    "license_review_required",
    "trusted_memory_allowed",
    "runtime_allowed",
    "model_loading_allowed",
    "package_install_allowed",
    "human_signature_required",
]

REQUIRED_NEXT_STEPS = [
    "Manual LLM Candidate Review Batch V1",
    "Python Library Approved Materials Intake V1",
    "Library Review Queue Integration V1",
    "Learning Job Queue from Approved Library Sources V1",
    "Code Companion Python Reference Bridge V1",
    "Offline Model Runtime Readiness Check V1",
    "Android Remote Worker Reference Intake V1",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_plan_files() -> None:
    require(PLAN_JSON.exists(), "JSON plan missing")
    require(PLAN_MD.exists(), "Markdown plan missing")
    data = json.loads(read(PLAN_JSON))
    text = read(PLAN_MD)
    require(data.get("plan_name") == "Engel LLM and Python Library Intake Plan V1", "plan name mismatch")
    for status in REQUIRED_STATUSES:
        require(status in data.get("status", []), "JSON missing status: " + status)
        require(status in text, "Markdown missing status: " + status)
    for area in REQUIRED_LIBRARY_AREAS:
        require(area in data.get("library_areas", []), "JSON missing library area: " + area)
        require(area in text, "Markdown missing library area: " + area)
    full_text = json.dumps(data, sort_keys=True) + "\n" + text
    for folder in REQUIRED_FOLDER_REFERENCES:
        require(folder in full_text, "missing folder reference: " + folder)
    for needle in ["NOT_AI_MODEL", "NOT_TRUSTED_MEMORY", r"G:\ENGEL_APP_MEMORY\models\manual_downloads\wsl\Ubuntu", r"G:\ENGEL_APP_MEMORY\models\manual_downloads\wsl\Ubuntu.tar"]:
        require(needle in full_text, "missing WSL boundary: " + needle)
    for needle in [
        "Android Remote Worker is not a Queen",
        "Android Remote Worker references/docs are non-model library materials",
        "Communication Queen controls routing for any future mobile worker",
        "No Android runtime, phone connection, network relay, or app build is enabled",
    ]:
        require(needle in full_text, "missing Android Remote Worker boundary: " + needle)
    for tier in REQUIRED_MODEL_TIERS:
        require(tier in full_text, "missing model tier: " + tier)
    for category in REQUIRED_PYTHON_CATEGORIES:
        require(category in full_text, "missing Python category: " + category)
    for state in REQUIRED_APPROVAL_STATES:
        require(state in full_text, "missing approval state: " + state)
    for field in REQUIRED_RECEIPT_FIELDS:
        require(field in full_text, "missing receipt field: " + field)
    for step in REQUIRED_NEXT_STEPS:
        require(step in full_text, "missing next step: " + step)
    for boundary in [
        "LLM library does not activate model runtime",
        "Python library does not install packages",
        "Docs do not become trusted instructions",
        "Memory promotion remains separate",
        "Core Continuity tracks this plan but does not approve materials by itself",
    ]:
        require(boundary in full_text, "missing safety boundary: " + boundary)
    for forbidden in [
        "Hermes Runtime Notes if installed later",
        "WSL/Hermes may support future tooling",
        "future Hermes runtime",
    ]:
        require(forbidden not in full_text, "unsafe Hermes intake wording remains: " + forbidden)
    for required in [
        "Hermes Rejection / Do Not Install Boundary Notes",
        "REJECTED / DO NOT INSTALL ON THIS COMPUTER",
        "must_not_be_used_for_hermes_runtime_work",
    ]:
        require(required in full_text, "missing Hermes rejection boundary: " + required)


def check_system_integration() -> None:
    text = read(SYSTEM_INTEGRATION)
    for needle in [
        "llm_python_library_intake_plan",
        "Engel LLM and Python Library Intake Plan V1",
        "model candidate intake path",
        "Python docs/reference intake path",
        "Manual LLM Candidate Review Batch V1",
        "Python Library Approved Materials Intake V1",
        "no model loading/inference/package install",
    ]:
        require(needle in text, "System Integration missing: " + needle)


def check_core_continuity() -> None:
    data = json.loads(read(CORE_JSON))
    md_text = read(CORE_MD)
    node = data.get("engel_llm_and_python_library_intake_plan_v1")
    require(isinstance(node, dict), "Core Continuity node missing")
    require(node.get("type") == "llm_and_python_library_intake_plan", "Core Continuity node type mismatch")
    for status in [
        "LLM_AND_PYTHON_LIBRARY_INTAKE_PLAN",
        "PLAN_ONLY",
        "HUMAN_REVIEW_REQUIRED",
        "MANUAL_DOWNLOADS_ONLY",
        "MODEL_CANDIDATES_NOT_LOADED",
        "PYTHON_DOCS_NOT_EXECUTED",
        "UNTRUSTED_UNTIL_REVIEWED",
        "NOT_TRUSTED_MEMORY",
        "NO_MODEL_LOADING",
        "NO_INFERENCE",
        "NO_PACKAGE_INSTALL",
        "NO_AUTO_IMPORT",
        "NO_TRUSTED_MEMORY_WRITE",
    ]:
        require(status in node.get("status", []), "Core node missing status: " + status)
        require(status in md_text, "Core Markdown missing status: " + status)
    for related in [
        "Model Library Plan V1",
        "Non-Model Library Plan V1",
        "Manual Model Intake Evaluator V1",
        "WSL Ubuntu Runtime Dependency V1",
        "Android Remote Worker Plan V1",
        "Approved Library Import Intake Contract V1",
        "Approved Library Human Review Receipt Template V1",
        "Manual Review Queue Contract V1",
        "Self-Research Topic Library V1",
        "Self-Learning Mini Runner V1",
        "Bounded Self-Learning Scheduler V1",
        "Code Companion Intelligence Loop V1",
        "Global Password-Gated Action Layer V1",
        "Protected Action Registry V1",
        "Active Build Plan Learning and Fixing V1",
    ]:
        require(related in node.get("related_nodes", []), "Core node missing related node: " + related)
    for key in [
        "no_model_loading",
        "no_inference",
        "no_training",
        "no_auto_download",
        "no_auto_import",
        "no_auto_move",
        "no_auto_delete",
        "no_package_install",
        "no_pip_install",
        "no_wsl_execution",
        "no_hermes_execution",
        "no_provider_calls",
        "no_network",
        "no_browser",
        "no_trusted_memory_write",
        "no_source_mutation",
        "no_background_worker",
        "no_startup_autorun",
    ]:
        require(node.get("boundaries", {}).get(key) is True, "Core node boundary missing/false: " + key)
    for needle in [
        "Engel LLM and Python Library Intake Plan V1",
        "Manual LLM Candidate Review Batch V1",
        "Python Library Approved Materials Intake V1",
        "Learning Job Queue from Approved Library Sources V1",
        "Code Companion Python Reference Bridge V1",
        "Offline Model Runtime Readiness Check V1",
        "Android Remote Worker Reference Intake V1",
        "WSL Ubuntu is NOT_AI_MODEL",
        "Android Remote Worker references may support future mobile worker design, not runtime control.",
        "Python docs are not executed",
    ]:
        require(needle in md_text, "Core Markdown missing text: " + needle)


def check_report() -> None:
    require(REPORT.exists(), "report missing")
    text = read(REPORT)
    for needle in [
        "files read first",
        "files created",
        "files updated",
        "plan summary",
        "LLM library intake rules",
        "Python library intake rules",
        "WSL runtime boundary",
        "Android Remote Worker reference boundary",
        "manual model intake relationship",
        "system integration update",
        "Core Continuity update",
        "verification results",
        "smoke results",
        "safety scan result",
        "no model was loaded",
        "no inference/training occurred",
        "no package/pip install occurred",
        "no WSL/Hermes/Android runtime was executed",
        "packaging skipped",
        "final process sweep",
        "git status",
    ]:
        require(needle in text, "report missing: " + needle)


def main() -> int:
    checks = [
        ("plan_files", check_plan_files),
        ("system_integration", check_system_integration),
        ("core_continuity", check_core_continuity),
        ("report", check_report),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(f"{name}: {exc}")
            print("FAIL " + name + ": " + str(exc))
        except Exception as exc:
            failures.append(f"{name}: unexpected error: {exc}")
            print("FAIL " + name + ": unexpected error: " + str(exc))
    if failures:
        print("\nEngel LLM and Python Library Intake Plan verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nEngel LLM and Python Library Intake Plan verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
