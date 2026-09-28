from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTE_MODULE = ROOT / "engel_ai_update_routes.py"
ROUTER = ROOT / "engel_communication_router.py"
APP = ROOT / "engel_app.py"
ENTRY = ROOT / "engel_ai.py"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CORE_MD = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md"
CORE_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
CORE_BUILDER = ROOT / "tools" / "build_engel_core_continuity_map.py"
CORE_VERIFIER = ROOT / "tools" / "verify_engel_core_continuity_map.py"
SYSTEM_INTEGRATION = ROOT / "engel_system_integration_status.py"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
RESEARCH_OFFICE = ROOT / "engel_research_office.py"
CODE_COMPANION = ROOT / "engel_code_companion.py"
CODE_WORKSHOP = ROOT / "engel_code_workshop.py"
CODE_COMPANION_VERIFIER = ROOT / "tools" / "verify_engel_code_companion.py"
ENGEL_SPEC = ROOT / "Engel.spec"
HIVE_SPEC = ROOT / "EngelSuperSwarmHive3D.spec"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_route_resolution() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from engel_ai_update_routes import (
        ARCHIVE_SHELF_ROUTE_ID,
        ENGEL3D_START_ROUTE_ID,
        ENGEL3D_STATUS_ROUTE_ID,
        ENGEL_AGENT_GATEWAY_START_ROUTE_ID,
        ENGEL_AGENT_INVOKE_ROUTE_ID,
        ENGEL_AGENT_STATUS_ROUTE_ID,
        ENGEL_EVOLUTION_ENGINE_RUN_ROUTE_ID,
        ENGEL_EVOLUTION_LAB_RUN_EXAMPLE_ROUTE_ID,
        ENGEL_IDE_INSTALL_TO_PROJECT_ROUTE_ID,
        ENGEL_KNOWLEDGE_GRAPH_BUILD_ROUTE_ID,
        ENGEL_NATIVE_AGENT_LAUNCH_AGENT_ROUTE_ID,
        ENGEL_NATIVE_AGENT_LAUNCH_DASHBOARD_ROUTE_ID,
        ENGEL_SANDBOX_BRING_UP_ROUTE_ID,
        ENGEL_SANDBOX_STATUS_ROUTE_ID,
        MEMORY_CANDIDATE_ROUTE_ID,
        PROGRESS_ROUTE_ID,
        ROUTE_BY_ID,
        UPDATE_ROUTES,
        resolve_update_route,
        route_metadata,
    )
    from engel_communication_router import classify_user_input, route_companion_text_or_command

    required_route_ids = {
        PROGRESS_ROUTE_ID,
        MEMORY_CANDIDATE_ROUTE_ID,
        ARCHIVE_SHELF_ROUTE_ID,
        ENGEL_AGENT_STATUS_ROUTE_ID,
        ENGEL_AGENT_INVOKE_ROUTE_ID,
        ENGEL_AGENT_GATEWAY_START_ROUTE_ID,
        ENGEL3D_STATUS_ROUTE_ID,
        ENGEL3D_START_ROUTE_ID,
        ENGEL_SANDBOX_STATUS_ROUTE_ID,
        ENGEL_SANDBOX_BRING_UP_ROUTE_ID,
    }
    require(required_route_ids.issubset(set(ROUTE_BY_ID)), "New Engel AI route id set is incomplete")
    require(len(UPDATE_ROUTES) >= 25, "New Engel AI route family count unexpectedly small")

    phrase_targets = {
        "what is engel status": PROGRESS_ROUTE_ID,
        "show current blockers": PROGRESS_ROUTE_ID,
        "is the verifier clean": PROGRESS_ROUTE_ID,
        "codex status": PROGRESS_ROUTE_ID,
        "what failed": PROGRESS_ROUTE_ID,
        "check memory candidates": MEMORY_CANDIDATE_ROUTE_ID,
        "compare memory candidates": MEMORY_CANDIDATE_ROUTE_ID,
        "check candidate mismatch": MEMORY_CANDIDATE_ROUTE_ID,
        "candidate set approval status": MEMORY_CANDIDATE_ROUTE_ID,
        "why did candidate count fail": MEMORY_CANDIDATE_ROUTE_ID,
        "archive shelf status": ARCHIVE_SHELF_ROUTE_ID,
        "where is engel memory": ARCHIVE_SHELF_ROUTE_ID,
        r"is I:\ENGEL_APP_MEMORY still needed": ARCHIVE_SHELF_ROUTE_ID,
        "show E F G archive shelves": ARCHIVE_SHELF_ROUTE_ID,
        "long term archive status": ARCHIVE_SHELF_ROUTE_ID,
        "engel agent status": ENGEL_AGENT_STATUS_ROUTE_ID,
        "engel agent run": ENGEL_AGENT_INVOKE_ROUTE_ID,
        "engel agent gateway start": ENGEL_AGENT_GATEWAY_START_ROUTE_ID,
        "engel3d status": ENGEL3D_STATUS_ROUTE_ID,
        "engel3d start": ENGEL3D_START_ROUTE_ID,
        "engel sandbox status": ENGEL_SANDBOX_STATUS_ROUTE_ID,
        "engel sandbox bring up": ENGEL_SANDBOX_BRING_UP_ROUTE_ID,
    }

    for phrase, expected in phrase_targets.items():
        require(resolve_update_route(phrase) == expected, "adapter route mismatch for phrase: " + phrase)
        intent = classify_user_input(phrase)
        require(intent.category == "ai_update_status_request", "router category mismatch for phrase: " + phrase)
        require(intent.route_target == expected, "router target mismatch for phrase: " + phrase)

    for phrase, expected in {
        "what is engel status": PROGRESS_ROUTE_ID,
        "check memory candidates": MEMORY_CANDIDATE_ROUTE_ID,
        "archive shelf status": ARCHIVE_SHELF_ROUTE_ID,
        "engel3d status": ENGEL3D_STATUS_ROUTE_ID,
    }.items():
        result = route_companion_text_or_command(phrase, context="verifier")
        require(result.handled is True, "route not handled for phrase: " + phrase)
        require(result.route_target == expected, "route result target mismatch for phrase: " + phrase)
        require(result.should_execute_command is False, "AI update route must not be executable command: " + phrase)
        require(result.response.strip(), "empty response for phrase: " + phrase)

    expected_response_needles = {
        PROGRESS_ROUTE_ID: ["Engel Progress Dashboard", "NO_TRUSTED_MEMORY_WRITE"],
        MEMORY_CANDIDATE_ROUTE_ID: ["Engel Memory Candidate Inventory", "NO_MEMORY_PROMOTION"],
        ARCHIVE_SHELF_ROUTE_ID: ["Engel Archive Shelf Manager", r"I:\ENGEL_APP_MEMORY", "NO_ARCHIVE_MIGRATION"],
        ENGEL3D_STATUS_ROUTE_ID: ["Engel3D Office", "Safety:"],
    }
    for route_id, needles in expected_response_needles.items():
        result = route_companion_text_or_command(next(iter(route_metadata(route_id)["aliases"])), context="verifier")
        for needle in needles:
            require(needle in result.response, "route response missing " + needle + " for " + route_id)

    read_only_status_routes = {
        PROGRESS_ROUTE_ID,
        MEMORY_CANDIDATE_ROUTE_ID,
        ARCHIVE_SHELF_ROUTE_ID,
        ENGEL_AGENT_STATUS_ROUTE_ID,
        ENGEL3D_STATUS_ROUTE_ID,
        ENGEL_SANDBOX_STATUS_ROUTE_ID,
        ENGEL_SANDBOX_BRING_UP_ROUTE_ID,
    }
    for route_id in read_only_status_routes:
        meta = route_metadata(route_id)
        require(meta.get("read_only") is True, "status route should be read-only: " + route_id)
        require(meta.get("status_only") is True, "status route should be status-only: " + route_id)
        require(meta.get("safe_for_ai_route") is True, "route should be safe for AI routing: " + route_id)
        require(meta.get("no_memory_promotion") is True, "route must not promote memory: " + route_id)
        require(meta.get("no_trusted_memory_write") is True, "route must not write trusted memory: " + route_id)
        require(meta.get("no_fix_apply") is True, "route must not apply fixes: " + route_id)
        require(meta.get("no_queue_route_mutation") is True, "route must not mutate host queue/routes: " + route_id)

    explicit_action_routes = {
        ENGEL_AGENT_INVOKE_ROUTE_ID,
        ENGEL_AGENT_GATEWAY_START_ROUTE_ID,
        ENGEL3D_START_ROUTE_ID,
        ENGEL_NATIVE_AGENT_LAUNCH_DASHBOARD_ROUTE_ID,
        ENGEL_NATIVE_AGENT_LAUNCH_AGENT_ROUTE_ID,
        ENGEL_IDE_INSTALL_TO_PROJECT_ROUTE_ID,
        ENGEL_EVOLUTION_LAB_RUN_EXAMPLE_ROUTE_ID,
        ENGEL_KNOWLEDGE_GRAPH_BUILD_ROUTE_ID,
        ENGEL_EVOLUTION_ENGINE_RUN_ROUTE_ID,
    }
    for route_id in explicit_action_routes:
        meta = route_metadata(route_id)
        require(meta.get("read_only") is False, "explicit action route should not be mislabeled read-only: " + route_id)
        require(meta.get("status_only") is False, "explicit action route should not be mislabeled status-only: " + route_id)
        require(meta.get("safe_for_ai_route") is True, "explicit action route should still be declared route-safe: " + route_id)


def check_static_router_wiring() -> None:
    route_source = read(ROUTE_MODULE)
    router_source = read(ROUTER)
    app_source = read(APP)
    entry_source = read(ENTRY)
    for path in [ROUTE_MODULE, ROUTER, APP, ENTRY]:
        ast.parse(read(path))

    for needle in [
        "PROGRESS_ROUTE_ID",
        "MEMORY_CANDIDATE_ROUTE_ID",
        "ARCHIVE_SHELF_ROUTE_ID",
        "ENGEL_AGENT_STATUS_ROUTE_ID",
        "ENGEL_AGENT_INVOKE_ROUTE_ID",
        "ENGEL3D_STATUS_ROUTE_ID",
        "ENGEL_SANDBOX_STATUS_ROUTE_ID",
        "engel_progress_dashboard",
        "engel_memory_candidate_inventory",
        "engel_archive_shelf_manager",
        "engel_engel_agent_runner",
        "engel_engel3d_runner",
        "engel_engel_sandbox_runner",
        "resolve_update_route",
        "render_update_route",
    ]:
        require(needle in route_source, "route adapter missing text: " + needle)

    for needle in [
        "resolve_update_route",
        "render_update_route",
        "ai_update_status_request",
        "safe Engel AI update/status route",
        "ENGEL_AGENT_INVOKE_ROUTE_ID",
    ]:
        require(needle in router_source, "communication router missing update route wiring: " + needle)

    for needle in [
        "engel_ai_update_route_status",
        "resolve_update_route",
        "engel_ai_update_routes",
    ]:
        require(needle in app_source, "engel_app missing update route CLI/fallback wiring: " + needle)

    for needle in [
        "AUTONOMY_ALLOWED",
        "EXPLICIT_USER_ACTION_ONLY",
        "HOST_ROUTER_STATE: NO_MUTATION",
        "NO_MEMORY_PROMOTION",
        "NO_TRUSTED_MEMORY_WRITE",
    ]:
        require(needle in entry_source, "engel_ai route listing missing New Engel AI boundary text: " + needle)


def check_route_adapter_safety_static() -> None:
    route_tree = ast.parse(read(ROUTE_MODULE))
    forbidden_import_roots = {
        "requests",
        "urllib",
        "socket",
        "webbrowser",
        "subprocess",
        "threading",
        "multiprocessing",
        "shutil",
        "openai",
    }
    forbidden_call_names = {
        "write_text",
        "write_bytes",
        "unlink",
        "remove",
        "rename",
        "mkdir",
        "rmdir",
        "rglob",
        "glob",
        "walk",
        "Popen",
        "run",
        "system",
    }
    for node in ast.walk(route_tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in forbidden_import_roots, "route adapter imports forbidden package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in forbidden_import_roots, "route adapter imports forbidden package: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                require(func.attr not in forbidden_call_names, "route adapter contains forbidden direct call: " + func.attr)
            elif isinstance(func, ast.Name):
                require(func.id not in forbidden_call_names, "route adapter contains forbidden direct call: " + func.id)
        elif isinstance(node, (ast.While, ast.AsyncFor)):
            raise CheckFailure("route adapter contains a loop form not needed for routing")


def check_docs_and_continuity() -> None:
    commands = read(COMMANDS)
    core_md = read(CORE_MD)
    core_json = json.loads(read(CORE_JSON))
    builder = read(CORE_BUILDER)
    core_verifier = read(CORE_VERIFIER)
    system_integration = read(SYSTEM_INTEGRATION)
    for needle in [
        "Engel AI update/status and New Engel AI routes",
        "engel_ai_update_routes.py",
        "engel_progress_dashboard.py",
        "engel_memory_candidate_inventory.py",
        "engel_archive_shelf_manager.py",
        "engel_engel_agent_runner.py",
        "engel_engel3d_runner.py",
        "engel_engel_sandbox_runner.py",
        "is I:\\ENGEL_APP_MEMORY required",
        "explicit user-invoked routes",
    ]:
        require(needle in commands, "ENGEL_COMMANDS missing update-route documentation: " + needle)

    for needle in [
        "Engel AI Update Routes V1",
        "Natural-language route connections from Engel AI into New Engel AI status modules and explicit user-invoked action runtimes.",
        "engel.progress_dashboard.status -> engel_progress_dashboard.py",
        "engel.memory_candidate_inventory.status -> engel_memory_candidate_inventory.py",
        "engel.archive_shelf_manager.status -> engel_archive_shelf_manager.py",
        "engel.engel_agent.invoke -> engel_engel_agent_runner.py",
        "engel.engel3d.start -> engel_engel3d_runner.py",
        "engel.engel_sandbox.bring_up -> engel_engel_sandbox_runner.py",
        "No visible UI change, tabs, cards, or panels.",
        "No hidden startup autonomy",
        "Explicit action routes may manage their own target runtime only when the user invokes the route.",
        "/opt/engel, /opt/engel/models-active, and /mnt/engel-hdd-vault remain optional archive shelves.",
    ]:
        require(needle in core_md, "Core Continuity markdown missing update-route text: " + needle)
    for needle in [
        "AI_UPDATE_ROUTES_STATUS",
        "AI_UPDATE_ROUTE_TARGETS",
        "NEW_ENGEL_AI_ROUTE_FAMILIES_CONNECTED",
        "engel_ai_update_routes_v1",
        "check_engel_ai_update_routes",
    ]:
        require(needle in builder or needle in core_verifier, "Core Continuity builder/verifier missing update-route text: " + needle)

    node = core_json.get("engel_ai_update_routes_v1")
    require(isinstance(node, dict), "Core Continuity JSON missing engel_ai_update_routes_v1")
    require(
        node.get("type") == "natural_language_update_and_explicit_action_route_connections",
        "Core Continuity update-route node type mismatch",
    )
    for key in [
        "command_understanding_only",
        "uses_existing_router",
        "status_routes_read_only",
        "explicit_action_routes_user_invoked_only",
        "new_engel_ai_items_preserved",
        "no_visible_ui_change",
        "no_new_tabs_cards_or_panels",
        "no_memory_promotion",
        "no_trusted_memory_write",
        "no_candidate_approval",
        "no_fix_apply",
        "no_host_queue_route_runtime_mutation",
        "no_hidden_startup_autonomy",
        "explicit_routes_may_manage_their_own_target_runtime",
        "i_drive_not_required",
        "efg_archive_shelves_optional",
    ]:
        require(node.get("boundaries", {}).get(key) is True, "Core Continuity update-route boundary missing/false: " + key)

    require("check_engel_ai_update_routes" in core_verifier, "Core Continuity verifier missing update-route check")
    require("engel_ai_update_routes" in system_integration, "System Integration status missing update-route system entry")


def check_ui_guard() -> None:
    research_office = read(RESEARCH_OFFICE)
    forbidden_tabs = [
        "AI Growth",
        "Self-Learning",
        "Candidate Review",
        "Code Companion Review",
        "Global Safety",
        "System Integration",
        "Self-Fix",
        "Memory Promotion",
        "Research-to-Fix",
    ]
    for tab in forbidden_tabs:
        pattern = r"addTab\([^\n]+,\s*[\"']" + re.escape(tab) + r"[\"']\)"
        require(re.search(pattern, research_office) is None, "removed Colony Hive tab was restored: " + tab)
    for tab in ["Engel Mind", "Hive", "Swarm", "Queen Links", "Guided Library Review", "Permissions"]:
        pattern = r"addTab\([^\n]+,\s*[\"']" + re.escape(tab) + r"[\"']\)"
        require(re.search(pattern, research_office) is not None, "expected remaining Colony Hive tab missing: " + tab)


def check_archive_guard() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import engel_archive_shelf_manager

    status = engel_archive_shelf_manager.build_archive_shelf_status()
    configured = [str(item.get("path")) for item in status.get("configured_archive_roots", [])]
    for root in [r"E:\ENGEL_APP_MEMORY", r"F:\ENGEL_APP_MEMORY", r"G:\ENGEL_APP_MEMORY"]:
        require(root in configured, "optional E/F/G archive shelf missing: " + root)
    require(r"I:\ENGEL_APP_MEMORY" in status.get("deprecated_paths", []), r"I:\ENGEL_APP_MEMORY should remain deprecated")
    require(status.get("external_archive_required") is False, "external archive should not be required")
    require(status.get("missing_external_archive_is_failure") is False, "missing archive shelf should not be failure")
    require(str(status.get("active_memory_root")).endswith(r"Engel App\memory"), "active memory root should remain project-local")
    require(str(status.get("project_local_archive_fallback")).endswith(r"memory\ENGEL_APP_MEMORY"), "project-local archive fallback mismatch")


def check_code_companion_guard() -> None:
    companion = read(CODE_COMPANION)
    workshop = read(CODE_WORKSHOP)
    verifier = read(CODE_COMPANION_VERIFIER)
    for needle in [
        "engel_code_workshop as workshop",
        "Workshop Files",
        "Ask Engel",
        "workshop.run_file",
    ]:
        require(needle in companion, "Code Companion new UI/backend wiring missing: " + needle)
    for needle in [
        "def run_file(relpath: str, timeout_seconds: int = 20)",
        "encoding=\"utf-8\"",
        "PYTHONIOENCODING",
        "WORKSPACE",
    ]:
        require(needle in workshop, "Code Workshop sandbox/run guard missing: " + needle)
    require("retired_legacy_ui_needles" in verifier, "Code Companion verifier should preserve retired legacy UI allowance")
    require("Create Script" not in verifier or "retired_legacy_ui_needles" in verifier, "stale Create Script expectation returned")


def check_packaging_specs() -> None:
    for spec_path in [ENGEL_SPEC, HIVE_SPEC]:
        text = read(spec_path)
        for needle in [
            "collect_all('httpx')",
            "('engel_agent_main', 'engel_agent_main')",
            "('engel3d_office_main', 'engel3d_office_main')",
            "('engelsandbox_main', 'engelsandbox_main')",
            "'engel_ai'",
            "'engel_ai_update_routes'",
            "'engel_engel_agent_runner'",
            "'engel_engel3d_runner'",
            "'engel_engel_sandbox_runner'",
            "'engel_agent_bridge'",
            "'httpx'",
        ]:
            require(needle in text, spec_path.name + " missing New Engel AI packaging needle: " + needle)


def check_codex_registration() -> None:
    source = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_update_routes.py" in source, "codex_verify.ps1 missing AI update routes verifier")


def main() -> int:
    try:
        check_route_resolution()
        check_static_router_wiring()
        check_route_adapter_safety_static()
        check_docs_and_continuity()
        check_ui_guard()
        check_archive_guard()
        check_code_companion_guard()
        check_packaging_specs()
        check_codex_registration()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel AI update routes verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
