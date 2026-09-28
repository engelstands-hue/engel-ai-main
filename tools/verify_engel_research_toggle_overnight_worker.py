from __future__ import annotations

import ast
import importlib.util
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "engel_research_toggle_worker.py"
STATUS = ROOT / "engel_research_toggle_status.py"
CONTRACT_JSON = ROOT / "memory" / "ENGEL_RESEARCH_TOGGLE_OVERNIGHT_WORKER_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_RESEARCH_TOGGLE_OVERNIGHT_WORKER_CONTRACT_V1.md"
BACKGROUND_CONTRACT_JSON = ROOT / "memory" / "ENGEL_BACKGROUND_WORKER_STARTUP_AUTORUN_CONTRACT_V1.json"
BACKGROUND_CONTRACT_MD = ROOT / "memory" / "ENGEL_BACKGROUND_WORKER_STARTUP_AUTORUN_CONTRACT_V1.md"
REGISTRY = ROOT / "engel_protected_action_registry.py"
REGISTRY_JSON = ROOT / "memory" / "ENGEL_PROTECTED_ACTION_REGISTRY_V1.json"
REGISTRY_MD = ROOT / "memory" / "ENGEL_PROTECTED_ACTION_REGISTRY_V1.md"
COMPANION = ROOT / "engel_companion.py"
RESEARCH_OFFICE = ROOT / "engel_research_office.py"
MAP_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
MAP_MD = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_RESEARCH_TOGGLE_OVERNIGHT_WORKER_V1.md"
BACKGROUND_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_BACKGROUND_WORKER_STARTUP_AUTORUN_CONTRACT_V1.md"
TEMP_JOBS = ROOT / "reports" / "research_toggle_worker_verifier_temp_jobs.json"

REQUIRED_STATUSES = [
    "RESEARCH_TOGGLE_OVERNIGHT_WORKER",
    "BOUNDED_RESEARCH_WORKER",
    "NO_PASSWORD_GATE_REQUIRED",
    "PROTECTED_ACTION_REGISTRY_REQUIRED",
    "HUMAN_ENABLE_REQUIRED",
    "DISABLED_BY_DEFAULT",
    "CANDIDATE_OUTPUTS_ONLY",
    "LOCAL_ONLY_BY_DEFAULT",
    "APPROVED_LOCAL_SOURCES_ONLY",
    "EXPLICIT_JOB_LIST_ONLY",
    "RECEIPT_REQUIRED",
    "RESOURCE_LIMITS_REQUIRED",
    "TIME_LIMIT_REQUIRED",
    "MAX_JOB_LIMIT_REQUIRED",
    "KILL_SWITCH_REQUIRED",
    "STOP_ON_HIGH_RISK",
    "STOP_ON_UNCLEAR_RISK",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_VERIFIER_UPDATE",
    "NO_PROVIDER_CALLS_BY_DEFAULT",
    "NO_NETWORK_BY_DEFAULT",
    "NO_BROWSER_BY_DEFAULT",
    "NO_MODEL_RUNTIME_BY_DEFAULT",
    "NO_PACKAGE_REFRESH",
    "NO_STARTUP_AUTORUN_INSTALL",
    "NO_ENDLESS_LOOP",
    "NO_HIDDEN_AUTONOMY",
]

REQUIRED_CLI_FLAGS = [
    "--status",
    "--dry-run",
    "--run-once",
    "--overnight",
    "--jobs",
    "--max-runtime-minutes",
    "--max-jobs",
    "--disable",
    "--kill-switch",
]

REQUIRED_ACTIONS = [
    "enable_research_toggle_overnight_worker",
    "disable_research_toggle_overnight_worker",
    "run_research_toggle_worker_dry_run",
    "run_research_toggle_worker_once",
    "run_research_toggle_worker_overnight",
    "research_toggle_worker_kill_switch",
]

REQUIRED_LIMIT_TEXT = [
    "MAX_JOBS = 3",
    "MAX_RUNTIME_MINUTES = 480",
    "candidate_only",
    "explicit project-local JSON job list",
    "max 1 topic/source per job",
    "reject live/staging paths",
    "reject URLs",
    "reject external drives",
    "reject model or trusted-memory paths",
]

REQUIRED_RECEIPT_FIELDS = [
    "research_worker_run_id",
    "started_at",
    "completed_at",
    "mode",
    "research_toggle_state",
    "jobs_requested",
    "jobs_run",
    "jobs_stopped",
    "output_paths",
    "max_runtime_minutes",
    "max_jobs",
    "password_gate_checked",
    "protected_action_id",
    "safety_boundary",
    "stopped",
    "stop_reason",
    "final_summary",
    "no_trusted_memory_write",
    "no_source_mutation",
    "no_provider_network_browser",
    "no_model_runtime",
    "no_background_escape",
    "no_startup_autorun_install",
]

REQUIRED_GUI_TEXT = [
    "Research Toggle Overnight Worker",
    "Research Toggle status",
    "Overnight Research Worker status",
    "Password gate required",
    "Candidate-only boundary",
    "max jobs: 3",
    "max runtime minutes: 480",
    "Safe next steps",
    "Research toggle enables bounded candidate-only research",
]

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "openai",
    "subprocess",
    "threading",
    "multiprocessing",
}

FORBIDDEN_ACTIVE_LABELS = [
    "Start Infinite Research",
    "Enable Network Research",
    "Enable Browser Research",
    "Enable Model Research",
    "Write Trusted Memory",
    "Apply Patches",
    "Update Verifiers",
    "Start Startup Autorun",
    "Install Startup Entry",
    "Run Forever",
    "Bypass Password",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_module(name: str, path: Path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "could not load module: " + name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [
        WORKER,
        STATUS,
        CONTRACT_JSON,
        CONTRACT_MD,
        BACKGROUND_CONTRACT_JSON,
        BACKGROUND_CONTRACT_MD,
        REGISTRY,
        REGISTRY_JSON,
        REGISTRY_MD,
        COMPANION,
        RESEARCH_OFFICE,
    ]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path.relative_to(ROOT)))


def check_static_text() -> None:
    combined = "\n".join(
        read(path)
        for path in [
            WORKER,
            STATUS,
            CONTRACT_JSON,
            CONTRACT_MD,
            BACKGROUND_CONTRACT_JSON,
            BACKGROUND_CONTRACT_MD,
            REGISTRY,
            REGISTRY_JSON,
            REGISTRY_MD,
            COMPANION,
            RESEARCH_OFFICE,
        ]
    )
    for status in REQUIRED_STATUSES:
        require(status in combined, "required research toggle status missing: " + status)
    for flag in REQUIRED_CLI_FLAGS:
        require(flag in read(WORKER), "worker CLI flag missing: " + flag)
    require("--explain" in read(STATUS), "status CLI --explain missing")
    for action_id in REQUIRED_ACTIONS:
        require(action_id in combined, "protected action missing: " + action_id)
    for field in REQUIRED_RECEIPT_FIELDS:
        require(field in combined, "receipt field missing: " + field)
    worker_text = read(WORKER)
    for needle in REQUIRED_LIMIT_TEXT:
        require(needle in worker_text, "worker limit/boundary text missing: " + needle)
    for gui_file in [COMPANION, RESEARCH_OFFICE]:
        gui_text = read(gui_file)
        require("Research Toggle Overnight Worker" in gui_text, gui_file.name + " missing Research Toggle worker section")
        require("research_toggle_status.render_status" in gui_text, gui_file.name + " missing rendered worker status call")
    for forbidden in FORBIDDEN_ACTIVE_LABELS:
        require(forbidden not in read(COMPANION), "forbidden GUI label in Companion: " + forbidden)
        require(forbidden not in read(RESEARCH_OFFICE), "forbidden GUI label in Research Office: " + forbidden)


def check_ast_safety() -> None:
    for path in [WORKER, STATUS]:
        tree = ast.parse(read(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, f"{path.name} imports forbidden module: {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, f"{path.name} imports forbidden module: {node.module}")
            elif isinstance(node, ast.While):
                raise CheckFailure(path.name + " contains a while loop")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                require(node.func.id not in {"eval", "exec", "__import__"}, path.name + " uses forbidden dynamic execution")
    source = read(WORKER)
    for forbidden in [
        "winreg",
        "schtasks",
        "Startup folder",
        "Startup\\",
        "provider call implementation",
        "network call implementation",
        "browser call implementation",
        "model runtime implementation",
        "trusted_memory write",
        "source mutation implementation",
        "patch apply implementation",
        "verifier update implementation",
        "package refresh implementation",
    ]:
        require(forbidden not in source, "worker contains active-forbidden implementation marker: " + forbidden)


def check_contract_json() -> None:
    contract = json.loads(read(CONTRACT_JSON))
    require(
        contract.get("type") in {"research_toggle_overnight_worker", "research_toggle_overnight_worker_contract"},
        "research contract type mismatch",
    )
    for status in REQUIRED_STATUSES:
        require(status in contract.get("status", []), "research contract JSON missing status: " + status)
    limits = contract.get("limits", {})
    require(limits.get("max_jobs_per_overnight_run") == 3, "contract max jobs limit mismatch")
    require(limits.get("max_runtime_minutes") == 480, "contract max runtime mismatch")
    require(limits.get("disabled_by_default") is True, "contract disabled by default missing")
    for field in REQUIRED_RECEIPT_FIELDS:
        require(field in contract.get("receipt_fields", []), "contract receipt field missing: " + field)


def check_runtime_behavior() -> None:
    worker = load_module("engel_research_toggle_worker", WORKER)
    status_module = load_module("engel_research_toggle_status", STATUS)
    status = worker.worker_status()
    require(status.get("enabled") is False, "worker should be disabled by default")
    require(status.get("startup_enabled") is False, "startup must remain disabled")
    require(status.get("startup_allowed") is False, "startup must not be allowed in V1")
    require(status.get("max_jobs") == 3, "runtime max jobs mismatch")
    require(status.get("max_runtime_minutes") == 480, "runtime max runtime mismatch")
    rendered = status_module.render_status()
    explained = status_module.render_explain()
    for needle in REQUIRED_GUI_TEXT + ["OFF meaning", "Safe next steps"]:
        require(needle in rendered or needle in explained, "rendered status missing: " + needle)

    jobs = [
        {
            "topic_id": "SRT-01-01-python_error_handling_patterns_for_local_tools",
            "source": "memory\\ENGEL_SELF_RESEARCH_CONTRACT_V1.md",
            "mode": "candidate_only",
        }
    ]
    TEMP_JOBS.write_text(json.dumps(jobs, indent=2) + "\n", encoding="utf-8")
    try:
        output, stopped = worker.run_batch(str(TEMP_JOBS.relative_to(ROOT)), "dry-run", 480, 3)
    finally:
        if TEMP_JOBS.exists():
            TEMP_JOBS.unlink()
    require(stopped is False, "dry-run should not stop for safe temp job")
    require("Mode: dry-run" in output, "dry-run output missing mode")
    require("DRY_RUN_NOT_WRITTEN" in output, "dry-run should not write candidate files")

    out = io.StringIO()
    err = io.StringIO()
    result = worker.main(["--run-once", "--jobs", "missing.json"], stdout=out, stderr=err)
    require(result == 1, "run-once without --password-prompt should continue to normal job validation")
    require("Protected action requires --password-prompt." not in err.getvalue(), "run-once still requires password prompt")


def check_core_continuity() -> None:
    data = json.loads(read(MAP_JSON))
    md = read(MAP_MD)
    background = data.get("engel_background_worker_startup_autorun_contract_v1")
    research = data.get("engel_research_toggle_overnight_worker_v1")
    require(isinstance(background, dict), "Core Continuity missing background/startup contract node")
    require(isinstance(research, dict), "Core Continuity missing research toggle worker node")
    require(background.get("type") == "background_worker_startup_autorun_contract", "background node type mismatch")
    require(research.get("type") == "research_toggle_overnight_worker", "research node type mismatch")
    for status in [
        "DISABLED_BY_DEFAULT",
        "KILL_SWITCH_REQUIRED",
        "NO_ENDLESS_LOOP",
        "NO_HIDDEN_AUTONOMY",
        "NO_STARTUP_AUTORUN_INSTALL",
    ]:
        require(status in background.get("status", []), "background node missing status: " + status)
    for status in REQUIRED_STATUSES:
        require(status in research.get("status", []), "research node missing status: " + status)
    for needle in [
        "Engel Background Worker and Startup Autorun Contract V1",
        "Engel Research Toggle Overnight Worker V1",
        "Research toggle is connected to bounded overnight research worker",
        "Background Worker/Startup contract governs worker behavior",
        "Research worker no longer requires Global Password Gate for enable/run actions",
        "Worker is disabled by default",
        "Startup autorun is not installed in V1",
        "Candidate outputs remain untrusted",
        "Provider/browser/model research remains blocked",
        "No hidden autonomy or endless loop exists",
    ]:
        require(needle in md, "Core Continuity Markdown missing text: " + needle)


def check_report_if_present() -> None:
    for path, name in [(REPORT, "research toggle worker report"), (BACKGROUND_REPORT, "background/startup report")]:
        if not path.exists():
            return
        text = read(path)
        for needle in [
            "files read first",
            "files created/updated",
            "contract summary",
            "research toggle behavior",
            "worker modes",
            "protected action registry additions",
            "GUI behavior",
            "Core Continuity update",
            "verification results",
            "smoke results",
            "safety scan result",
            "no actual startup autorun was installed",
            "no unbounded background loop was started",
            "packaging skipped",
            "final scoped process sweep",
            "git status",
        ]:
            require(needle in text, name + " missing text: " + needle)


def main() -> int:
    checks = [
        ("files", check_files),
        ("static_text", check_static_text),
        ("ast_safety", check_ast_safety),
        ("contract_json", check_contract_json),
        ("runtime_behavior", check_runtime_behavior),
        ("core_continuity", check_core_continuity),
        ("reports", check_report_if_present),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(f"{name}: {exc}")
            print(f"FAIL {name}: {exc}")
        except Exception as exc:
            failures.append(f"{name}: unexpected error: {exc}")
            print(f"FAIL {name}: unexpected error: {exc}")
    if failures:
        print("\nEngel Research Toggle Overnight Worker verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nEngel Research Toggle Overnight Worker verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
