#!/usr/bin/env python3
from __future__ import annotations

import json
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.md"
CORE_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
CORE_MD = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md"
SYSTEM_INTEGRATION = ROOT / "engel_system_integration_status.py"

REQUIRED_STATUSES = [
    "WSL_UBUNTU_RUNTIME_DEPENDENCY",
    "ENVIRONMENT_DEPENDENCY",
    "LOCAL_RUNTIME_DEPENDENCY",
    "NOT_MODEL_LIBRARY_MATERIAL",
    "NOT_TRUSTED_MEMORY",
    "MANUAL_INSTALL_RECORDED",
    "CT246_SSD_RUNTIME_STORAGE",
    "WINDOWS_SYSTEM_FILES_NOT_MOVED",
    "STAGE_2_AUTONOMY",
    "AUTO_RUN_AUTHORIZED",
    "BACKGROUND_WORKER_AUTHORIZED",
    "STAGE_3_AUTONOMY",
    "AUTO_INSTALL_AUTHORIZED",
    "PACKAGE_REFRESH_AUTHORIZED",
    "PACKAGE_MANAGER_NETWORK_AUTHORIZED",
    "MODEL_HOSTING_AUTHORIZED",
    "MODEL_LOADING_AUTHORIZED",
    "INFERENCE_AUTHORIZED",
    "TRAINING_AUTHORIZED",
    "STAGE_4_NATIVE_HERMES",
    "ENGEL_AI_IS_HERMES_AGENT_NATIVE",
    "PROVIDER_CALLS_AUTHORIZED_VIA_HERMES_SURFACE",
    "BACKGROUND_TOOL_LOOPS_AUTHORIZED",
    "NO_ARBITRARY_OUTBOUND_NETWORK",
    "NO_BROWSER",
    "NO_PROVIDER_CALLS",
    "NO_SOURCE_MUTATION",
]

REQUIRED_TEXT = [
    "Ubuntu",
    "engelz",
    "/opt/engel/models-active/wsl/Ubuntu",
    "/mnt/engel-hdd-vault/wsl/Ubuntu.tar",
    "WSL/Ubuntu is an operating-system runtime, not an AI model.",
    "Windows wsl.exe remains on C:",
    "Windows WinSxS remains untouched",
    "WSL Start Menu shortcut remains untouched",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_contract_files() -> None:
    require(CONTRACT_JSON.exists(), "JSON contract missing")
    require(CONTRACT_MD.exists(), "Markdown contract missing")
    data = json.loads(read(CONTRACT_JSON))
    md = read(CONTRACT_MD)
    for status in REQUIRED_STATUSES:
        require(status in data.get("status", []), "JSON missing status: " + status)
        require(status in md, "Markdown missing status: " + status)
    for text in REQUIRED_TEXT:
        require(text in read(CONTRACT_JSON) or text in md, "contract missing text: " + text)
    require(data.get("type") == "runtime_environment_dependency", "JSON type mismatch")
    require(data.get("distro_name") == "Ubuntu", "distro name mismatch")
    require(data.get("wsl_version") == 2, "WSL version mismatch")
    require(data.get("linux_user") == "engelz", "Linux user mismatch")
    require(data.get("runtime_category") == "local_linux_runtime", "runtime category mismatch")
    require(data.get("engel_classification") == "environment/runtime dependency", "classification mismatch")
    for key in [
        "runtime_activation_added",
        "trusted_memory_write_added",
        "source_mutation_added",
    ]:
        require(data.get(key) is False, "JSON safety flag should be false: " + key)
    forbidden = data.get("forbidden_uses", [])
    require(
        "do not auto-run background workers" not in forbidden,
        "Stage 2: 'do not auto-run background workers' forbidden use must be removed",
    )
    for lifted in (
        "do not install packages without approval",
        "do not treat as model",
        "do not load as model",
        "do not use provider/network/browser without separate contract",
    ):
        require(lifted not in forbidden, f"Stage 3: forbidden use '{lifted}' must be removed")
    stage2 = data.get("stage_2_autonomy_authorization")
    require(isinstance(stage2, dict), "Stage 2 autonomy authorization block missing")
    require(stage2.get("stage") == 2, "Stage 2 stage field mismatch")
    require(stage2.get("auto_run_authorized") is True, "Stage 2 auto_run_authorized must be true")
    require(stage2.get("background_worker_authorized") is True, "Stage 2 background_worker_authorized must be true")
    require(stage2.get("authorized_on") == "2026-05-20", "Stage 2 authorized_on mismatch")
    require(stage2.get("authorized_by") == "Josh", "Stage 2 authorized_by mismatch")
    stage3 = data.get("stage_3_autonomy_authorization")
    require(isinstance(stage3, dict), "Stage 3 autonomy authorization block missing")
    require(stage3.get("stage") == 3, "Stage 3 stage field mismatch")
    for flag in (
        "auto_install_authorized",
        "package_refresh_authorized",
        "package_manager_network_authorized",
        "model_hosting_authorized",
        "model_loading_authorized",
        "inference_authorized",
        "training_authorized",
    ):
        require(stage3.get(flag) is True, f"Stage 3 flag must be true: {flag}")
    require(stage3.get("authorized_on") == "2026-05-20", "Stage 3 authorized_on mismatch")
    require(stage3.get("authorized_by") == "Josh", "Stage 3 authorized_by mismatch")
    for preserved in [
        "NOT_MODEL_LIBRARY_MATERIAL",
        "NOT_TRUSTED_MEMORY",
        "NO_ARBITRARY_OUTBOUND_NETWORK",
        "NO_BROWSER",
        "NO_PROVIDER_CALLS",
        "NO_SOURCE_MUTATION",
    ]:
        require(preserved in stage3.get("preserved_boundaries", []), "Stage 3 preserved boundary missing: " + preserved)
    for lifted_status in ("NOT_AI_MODEL", "NO_MODEL_LOADING", "NO_INFERENCE", "NO_TRAINING", "NO_AUTO_INSTALL", "NO_PACKAGE_REFRESH", "NO_NETWORK"):
        require(lifted_status not in data.get("status", []), f"Stage 3: status '{lifted_status}' must be removed from JSON status list")
        require(lifted_status not in md, f"Stage 3: status '{lifted_status}' must be removed from markdown")
    require("Stage 2 Autonomy Authorization" in md, "Markdown missing Stage 2 Autonomy Authorization section")
    require("Stage 3 Autonomy Authorization" in md, "Markdown missing Stage 3 Autonomy Authorization section")
    require("AUTO_RUN_AUTHORIZED" in md, "Markdown Runtime Effect must declare AUTO_RUN_AUTHORIZED")
    require("AUTO_INSTALL_AUTHORIZED" in md, "Markdown Runtime Effect must declare AUTO_INSTALL_AUTHORIZED")
    require("MODEL_LOADING_AUTHORIZED" in md, "Markdown Runtime Effect must declare MODEL_LOADING_AUTHORIZED")
    require("NO_AUTO_RUN" not in md, "Markdown must no longer assert NO_AUTO_RUN")
    require("do not auto-run background workers" not in md, "Markdown must drop the auto-run forbidden use")
    # ---- Stage 4 ----
    stage4 = data.get("stage_4_native_hermes_integration")
    require(isinstance(stage4, dict), "Stage 4 native hermes integration block missing")
    require(stage4.get("stage") == 4, "Stage 4 stage field mismatch")
    for flag in (
        "engel_ai_is_hermes_agent_native",
        "provider_calls_authorized_via_hermes_surface",
        "background_tool_loops_authorized",
    ):
        require(stage4.get(flag) is True, f"Stage 4 flag must be true: {flag}")
    require(stage4.get("authorized_on") == "2026-05-20", "Stage 4 authorized_on mismatch")
    require(stage4.get("authorized_by") == "Josh", "Stage 4 authorized_by mismatch")
    for route_id in (
        "engel.identity",
        "engel.gateway.start",
        "engel.cron.list",
        "engel.memory.status",
        "engel.skills.list",
        "engel.sessions.list",
        "engel.plugins.list",
        "engel.toolsets",
        "engel.doctor",
        "engel.version",
        "engel.invoke",
    ):
        require(route_id in stage4.get("absorption_surface_top_level", []), f"Stage 4 absorption route id missing: {route_id}")
    require("Stage 4 Native Hermes Integration" in md, "Markdown missing Stage 4 Native Hermes Integration section")
    require("ENGEL_AI_IS_HERMES_AGENT_NATIVE" in md, "Markdown Status line must declare ENGEL_AI_IS_HERMES_AGENT_NATIVE")
    require("PROVIDER_CALLS_AUTHORIZED_VIA_HERMES_SURFACE" in md, "Markdown Status line must declare PROVIDER_CALLS_AUTHORIZED_VIA_HERMES_SURFACE")
    # ---- Stage 4 Phase D ----
    phase_d = stage4.get("phase_d_source_level_absorption")
    require(isinstance(phase_d, dict), "Stage 4 Phase D block missing")
    require(phase_d.get("phase") == "D", "Phase D phase field mismatch")
    require(phase_d.get("source_level_absorption_proven_in_process") is True, "Phase D source_level_absorption_proven_in_process must be true")
    require(phase_d.get("absorbed_on") == "2026-05-20", "Phase D absorbed_on mismatch")
    require(phase_d.get("proof_route") == "engel.native_runtime — imports a representative set of hermes-agent modules in-process and reports per-module status. Acts as the live smoke test for Phase D.", "Phase D proof_route mismatch")
    require("Phase D: source-level absorption proven in-process" in md, "Markdown missing Phase D section")


def check_core_continuity() -> None:
    data = json.loads(read(CORE_JSON))
    md = read(CORE_MD)
    node = data.get("engel_wsl_ubuntu_runtime_dependency_v1")
    require(isinstance(node, dict), "Core Continuity node missing")
    require(node.get("type") == "runtime_environment_dependency", "Core Continuity node type mismatch")
    for status in [
        "WSL_UBUNTU_RUNTIME_DEPENDENCY",
        "ENVIRONMENT_DEPENDENCY",
        "LOCAL_RUNTIME_DEPENDENCY",
        "NOT_TRUSTED_MEMORY",
        "CT246_SSD_RUNTIME_STORAGE",
        "WINDOWS_SYSTEM_FILES_NOT_MOVED",
        "STAGE_2_AUTONOMY",
        "AUTO_RUN_AUTHORIZED",
        "STAGE_3_AUTONOMY",
        "AUTO_INSTALL_AUTHORIZED",
        "MODEL_LOADING_AUTHORIZED",
        "INFERENCE_AUTHORIZED",
        "NO_ARBITRARY_OUTBOUND_NETWORK",
        "NO_PROVIDER_CALLS",
    ]:
        require(status in node.get("status", []), "Core Continuity node missing status: " + status)
        require(status in md, "Core Continuity Markdown missing status: " + status)
    for dropped in ("NO_AUTO_RUN", "NO_AUTO_INSTALL", "NO_PACKAGE_REFRESH", "NO_NETWORK", "NOT_AI_MODEL", "NO_MODEL_LOADING", "NO_INFERENCE", "NO_TRAINING"):
        require(dropped not in node.get("status", []), f"Core Continuity node must drop {dropped}")
    for text in [
        "Engel WSL Ubuntu Runtime Dependency V1",
        "WSL Ubuntu is a local runtime/environment dependency.",
        "It is not part of the model library.",
        "It is not trusted memory.",
        "Windows-owned WSL executables were not moved.",
        "Stage 2 autonomy authorizes auto-run and background workers inside the recorded distro.",
        "Stage 3 autonomy authorizes installs, package refresh, model loading, inference, and training inside the recorded distro.",
    ]:
        require(text in md, "Core Continuity Markdown missing text: " + text)


def check_system_integration() -> None:
    text = read(SYSTEM_INTEGRATION)
    for needle in [
        "wsl_ubuntu_runtime_dependency",
        "Runtime / Environment Dependencies",
        "Optional Local Tooling Environment",
        "STAGE_3_AUTONOMY",
        "auto-install authorized",
        "model loading authorized",
    ]:
        require(needle in text, "System Integration missing WSL dependency text: " + needle)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_system_integration_status", SYSTEM_INTEGRATION)
    require(spec is not None and spec.loader is not None, "could not load System Integration module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_system_integration_status"] = module
    spec.loader.exec_module(module)
    payload = module.integration_summary()
    system = next((item for item in payload.get("systems", []) if item.get("system_id") == "wsl_ubuntu_optional_local_tooling"), None)
    require(isinstance(system, dict), "WSL Ubuntu optional local tooling system missing from payload")
    require(system.get("manual_downloads_root") == "/opt/engel/models-active/wsl/Ubuntu", "WSL Ubuntu CT246 SSD folder missing from payload")


def check_report() -> None:
    require(REPORT.exists(), "report missing")
    text = read(REPORT)
    for needle in [
        "Engel WSL Ubuntu Runtime Dependency V1",
        "files read first",
        "files created",
        "files updated",
        "WSL Ubuntu migration facts recorded",
        "runtime dependency classification",
        "Windows system files not moved",
        "verification results",
        "safety scan result",
        "no WSL install/migration/package/network command was run by this step",
        "packaging skipped",
        "stage 2 autonomy amendment",
        "stage 3 autonomy amendment",
        "Full local AI development environment authorized",
    ]:
        require(needle in text, "report missing text: " + needle)


def main() -> int:
    checks = [
        ("contract_files", check_contract_files),
        ("core_continuity", check_core_continuity),
        ("system_integration", check_system_integration),
        ("report", check_report),
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
        print("\nEngel WSL Ubuntu Runtime Dependency verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nEngel WSL Ubuntu Runtime Dependency verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
