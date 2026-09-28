#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import engel_project_paths

ROOT = Path(__file__).resolve().parents[1]


def _module(name: str) -> Path:
    found = engel_project_paths.workspace_module_path(ROOT, name)
    return found if found is not None else ROOT / f"{name}.py"


EXPLORER = _module("engel_route_explorer")
ROUTES = ROOT / "engel_ai_update_routes.py"
ENTRY = ROOT / "engel_ai.py"
RESEARCH_OFFICE = _module("engel_research_office")
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_ROUTE_EXPLORER_SUPERSWARM_V1.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"


REMOVED_STATUS_TABS = [
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


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def import_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "could not create import spec for " + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def check_files_and_static_safety() -> None:
    for path in [EXPLORER, ROUTES, ENTRY, RESEARCH_OFFICE, COMMANDS, REPORT, CODEX_VERIFY]:
        require(path.exists() and path.is_file(), "missing required file: " + str(path.relative_to(ROOT)))

    source = read(EXPLORER)
    tree = ast.parse(source)
    require("UPDATE_ROUTES" in source, "route explorer must read UPDATE_ROUTES")
    require("route_catalog_for_gui" in source, "route explorer missing GUI catalog API")
    require("render_route_explorer" in source, "route explorer missing renderer")
    blocked_import_roots = {"subprocess", "socket", "requests", "urllib", "webbrowser", "threading", "multiprocessing"}
    blocked_calls = {"Popen", "run", "system", "write_text", "write_bytes", "unlink", "remove", "rename", "mkdir", "rmdir"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in blocked_import_roots, "explorer imports runtime package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in blocked_import_roots, "explorer imports runtime package: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                require(func.attr not in blocked_calls, "explorer calls runtime/mutation helper: " + func.attr)
            elif isinstance(func, ast.Name):
                require(func.id not in blocked_calls, "explorer calls runtime/mutation helper: " + func.id)


def check_catalog_covers_current_registry() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import engel_ai_update_routes as routes
    import engel_route_explorer as explorer

    catalog = explorer.route_catalog_for_gui()
    catalog_ids = {str(entry.get("route_id")) for entry in catalog}
    registry_ids = {route.route_id for route in routes.UPDATE_ROUTES}
    require(catalog_ids == registry_ids, "route explorer catalog does not exactly cover UPDATE_ROUTES")
    require(len(catalog) == len(routes.UPDATE_ROUTES), "route explorer route count mismatch")
    require(len(catalog_ids) == len(catalog), "route explorer has duplicate route IDs")
    summary = explorer.route_catalog_summary(catalog)
    require(summary.get("route_count") == len(routes.UPDATE_ROUTES), "summary route count mismatch")
    require(int(summary.get("alias_count", 0)) >= len(routes.UPDATE_ROUTES), "summary alias count too small")
    require(int(summary.get("action_route_count", 0)) >= 6, "action routes not visible in summary")

    required_routes = {
        "engel.routes.explorer",
        "engel.native_agent.launch_dashboard",
        "engel.native_agent.launch_agent",
        "engel.ide.install_to_project",
        "engel.evolution_lab.run_example",
        "engel.knowledge_graph.build",
        "engel.evolution_engine.run",
        "engel.ai_connectors.status",
        "engel.ai_connectors.adapters",
        "engel.ai_connectors.blueprint",
        "engel.ai_connectors.rules",
        "engel.ai_connectors.zip_audit",
        "engel.graph_studio.status",
        "engel.graph_studio.open",
        "engel.graph_studio.new",
        "engel.graph_studio.list",
    }
    require(required_routes.issubset(catalog_ids), "required branded routes missing from route explorer")

    for phrase in [
        "route explorer",
        "show command menu",
        "help me use engel",
        "what can i do",
        "super swarm routes",
        "superswarm routes",
    ]:
        require(routes.resolve_update_route(phrase) == "engel.routes.explorer", "route explorer alias did not resolve: " + phrase)
    require(routes.resolve_update_route("graph studio") == "engel.graph_studio.status", "graph studio status alias failed")
    require(routes.resolve_update_route("open graph studio") == "engel.graph_studio.open", "graph studio open alias failed")
    require(routes.resolve_update_route("new engel graph") == "engel.graph_studio.new", "graph studio new alias failed")

    rendered = explorer.render_route_explorer()
    for needle in [
        "One route catalog",
        "engel_ai_update_routes.UPDATE_ROUTES",
        "Super Swarm Routes tab",
        "does not create a second route system",
        "Action routes remain explicit user-invoked routes",
        "Engel Native Agent",
        "Engel Knowledge Graph",
        "Engel Evolution Engine",
        "AI Connectors",
        "show ai connectors",
        "Graph & Loop Studio",
    ]:
        require(needle in rendered, "route explorer output missing: " + needle)


def check_router_and_entry() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from engel_communication_router import classify_user_input, route_companion_text_or_command

    intent = classify_user_input("route explorer")
    require(intent.route_target == "engel.routes.explorer", "communication router did not target route explorer")
    result = route_companion_text_or_command("route explorer", context="verifier")
    require(result.handled is True, "route explorer was not handled")
    require(result.route_target == "engel.routes.explorer", "route explorer route target mismatch")
    require("Engel Route Explorer" in result.response, "route explorer response missing title")

    entry = read(ENTRY)
    require("ENGEL_ROUTE_EXPLORER_ROUTE_ID" in entry, "engel_ai self-test does not include route explorer")
    require("route explorer / show command menu / super swarm routes" in entry, "engel_ai routes output missing easy command menu")
    require(
        "engel humanizer/codex/cursor/darwin/graphify/evolver status" not in entry,
        "stale non-branded minor-tool summary remains in engel_ai.py",
    )


def check_superswarm_gui_surface() -> None:
    source = read(RESEARCH_OFFICE)
    ast.parse(source)
    for needle in [
        "self.tabs.addTab(self._make_route_explorer_tab(), \"Routes\")",
        "def _make_route_explorer_tab",
        "route_catalog_for_gui",
        "filter_route_catalog",
        "render_route_explorer",
        "Run Selected Route",
        "ACTION ROUTES CONFIRM FIRST",
        "QMessageBox.question",
        "route_companion_text_or_command",
    ]:
        require(needle in source, "Super Swarm route explorer GUI missing: " + needle)
    for tab in REMOVED_STATUS_TABS:
        require(f'addTab(self._make_ai_growth_gui_status_tab(tab_name), "{tab}")' not in source, "removed status tab restored: " + tab)
    for tab in ["Engel Mind", "Hive", "Swarm", "Routes", "Queen Links", "Guided Library Review", "Permissions"]:
        require(f'"{tab}"' in source, "expected Super Swarm tab/label missing: " + tab)


def check_docs_and_full_verifier_hook() -> None:
    commands = read(COMMANDS)
    report = read(REPORT)
    codex = read(CODEX_VERIFY)
    for needle in [
        "Engel Route Explorer and Super Swarm route menu",
        "engel_route_explorer.py",
        "super swarm routes",
        "Routes tab",
        "Explicit action routes ask for confirmation before running",
    ]:
        require(needle in commands, "ENGEL_COMMANDS missing route explorer text: " + needle)
    for needle in [
        "# Engel Route Explorer and Super Swarm Routes V1",
        "Existing route registry",
        "Super Swarm Routes tab",
        "No second route system",
        "Verification",
    ]:
        require(needle in report, "report missing route explorer text: " + needle)
    require("tools\\verify_engel_route_explorer_superswarm.py" in codex, "codex_verify missing route explorer verifier")


def main() -> int:
    checks = [
        ("files_and_static_safety", check_files_and_static_safety),
        ("catalog_covers_current_registry", check_catalog_covers_current_registry),
        ("router_and_entry", check_router_and_entry),
        ("superswarm_gui_surface", check_superswarm_gui_surface),
        ("docs_and_full_verifier_hook", check_docs_and_full_verifier_hook),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(name + ": " + str(exc))
            print("FAIL " + name + ": " + str(exc))
        except Exception as exc:
            failures.append(name + ": unexpected " + type(exc).__name__ + ": " + str(exc))
            print("FAIL " + name + ": unexpected " + type(exc).__name__ + ": " + str(exc))
    if failures:
        print("\nEngel route explorer Super Swarm verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nEngel route explorer Super Swarm verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
