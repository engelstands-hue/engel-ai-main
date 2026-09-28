#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "engel_ai_connector_hub.py"
ROUTES = ROOT / "engel_ai_update_routes.py"
EXPLORER = ROOT / "engel_route_explorer.py"
ENTRY = ROOT / "engel_ai.py"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
MEMORY_JSON = ROOT / "memory" / "ENGEL_AI_CONNECTOR_HUB_V1.json"
MEMORY_MD = ROOT / "memory" / "ENGEL_AI_CONNECTOR_HUB_V1.md"
CORE_MAP_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
CORE_MAP_MD = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_CONNECTOR_HUB_V1.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
SOURCE_ZIP = ROOT.parent / "hermes-agent-main.zip"
VENDORED_AGENT_ROOT = ROOT / "engel_agent_main"
FAST_EXTERNAL_MEMORY = Path(r"F:\ENGEL_APP_MEMORY")
SLOW_EXTERNAL_MEMORY = Path(r"E:\ENGEL_APP_MEMORY")
FAST_EXTERNAL_RECORD = FAST_EXTERNAL_MEMORY / "manifests" / "ENGEL_AI_CONNECTOR_HUB_V1.md"
SLOW_EXTERNAL_RECORD = SLOW_EXTERNAL_MEMORY / "manifests" / "ENGEL_AI_CONNECTOR_HUB_V1.md"


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


def check_files_and_import_safety() -> None:
    for path in [HUB, ROUTES, EXPLORER, ENTRY, COMMANDS, MEMORY_JSON, MEMORY_MD, CORE_MAP_JSON, CORE_MAP_MD, REPORT, CODEX_VERIFY]:
        require(path.exists() and path.is_file(), "missing required file: " + str(path.relative_to(ROOT)))
    require(SOURCE_ZIP.exists() and SOURCE_ZIP.is_file(), "missing source zip: " + str(SOURCE_ZIP))
    require(VENDORED_AGENT_ROOT.exists() and VENDORED_AGENT_ROOT.is_dir(), "missing vendored Engel Agent root")
    require(FAST_EXTERNAL_MEMORY.exists() and FAST_EXTERNAL_MEMORY.is_dir(), "missing fast external memory root: " + str(FAST_EXTERNAL_MEMORY))
    require(SLOW_EXTERNAL_MEMORY.exists() and SLOW_EXTERNAL_MEMORY.is_dir(), "missing slow external memory root: " + str(SLOW_EXTERNAL_MEMORY))
    require(FAST_EXTERNAL_RECORD.exists() and FAST_EXTERNAL_RECORD.is_file(), "missing fast external connector memory record")
    require(SLOW_EXTERNAL_RECORD.exists() and SLOW_EXTERNAL_RECORD.is_file(), "missing slow external connector memory record")

    source = read(HUB)
    tree = ast.parse(source)
    blocked_import_roots = {
        "subprocess",
        "socket",
        "requests",
        "urllib",
        "http",
        "webbrowser",
        "threading",
        "multiprocessing",
    }
    blocked_calls = {
        "Popen",
        "run",
        "system",
        "startfile",
        "write_text",
        "write_bytes",
        "unlink",
        "remove",
        "rename",
        "mkdir",
        "rmdir",
        "extract",
        "extractall",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in blocked_import_roots, "hub imports runtime/network package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in blocked_import_roots, "hub imports runtime/network package: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                require(func.attr not in blocked_calls, "hub calls mutation/runtime helper: " + func.attr)
            elif isinstance(func, ast.Name):
                require(func.id not in blocked_calls, "hub calls mutation/runtime helper: " + func.id)

    module = import_module(HUB, "engel_ai_connector_hub_import_check")
    require(hasattr(module, "build_connector_inventory"), "hub missing inventory builder")
    require(hasattr(module, "render_ai_connector_status"), "hub missing status renderer")


def check_inventory_copies_hermes_connector_pattern() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import engel_ai_connector_hub as hub

    inv = hub.build_connector_inventory()
    require(inv.get("source_zip_present") is True, "Hermes source zip not detected")
    require(inv.get("vendored_root_present") is True, "vendored Engel Agent root not detected")
    require(inv.get("memory_json_present") is True, "connector memory JSON not detected")
    require(inv.get("memory_markdown_present") is True, "connector memory Markdown not detected")
    roots_present = dict(inv.get("external_memory_roots_present", {}))
    records_present = dict(inv.get("external_memory_records_present", {}))
    roles = dict(inv.get("external_memory_roles", {}))
    require(roots_present.get(str(FAST_EXTERNAL_MEMORY)) is True, "fast external memory root not detected")
    require(roots_present.get(str(SLOW_EXTERNAL_MEMORY)) is True, "slow external memory root not detected")
    require(records_present.get(str(FAST_EXTERNAL_RECORD)) is True, "fast external record not detected")
    require(records_present.get(str(SLOW_EXTERNAL_RECORD)) is True, "slow external record not detected")
    require("fast external memory shelf" in str(roles.get(str(FAST_EXTERNAL_MEMORY), "")), "F role missing fast memory wording")
    require("slower disk-drive archive" in str(roles.get(str(SLOW_EXTERNAL_MEMORY), "")), "E role missing slow archive wording")
    require(int(inv.get("source_zip_entries", 0)) >= 4000, "Hermes zip entry count unexpectedly small")
    require(int(inv.get("vendored_file_count", 0)) >= 3000, "vendored Engel Agent file count unexpectedly small")
    require(inv.get("acp_core_complete") is True, "ACP core files not complete in zip and vendored root")
    require(inv.get("provider_runtime_complete") is True, "provider runtime files not complete in zip and vendored root")

    native = set(str(item) for item in inv.get("native_adapters_found", []))
    for rel in [
        "agent/anthropic_adapter.py",
        "agent/codex_responses_adapter.py",
        "agent/gemini_native_adapter.py",
        "agent/copilot_acp_client.py",
        "agent/credential_pool.py",
    ]:
        require(rel in native or rel.endswith("credential_pool.py"), "required adapter missing from inventory: " + rel)
    plugins = set(str(item) for item in inv.get("model_provider_plugins", []))
    for plugin in ["anthropic", "gemini", "openai-codex", "copilot-acp", "ollama-cloud"]:
        require(plugin in plugins, "required model provider plugin missing: " + plugin)

    rendered = hub.render_ai_connector_status()
    for needle in [
        "Engel AI Connector Hub",
        "existing Engel AI route spine",
        "Source pattern copied into Engel branding",
        "Super Swarm Routes tab",
        "durable project-local memory record",
        "F:\\ENGEL_APP_MEMORY",
        "E:\\ENGEL_APP_MEMORY",
    ]:
        require(needle in rendered, "status output missing: " + needle)


def check_routes_and_superswarm_visibility() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import engel_ai_update_routes as routes
    import engel_route_explorer as explorer
    from engel_communication_router import route_companion_text_or_command

    required_route_ids = {
        "engel.ai_connectors.status",
        "engel.ai_connectors.adapters",
        "engel.ai_connectors.blueprint",
        "engel.ai_connectors.rules",
        "engel.ai_connectors.zip_audit",
    }
    registry_ids = {route.route_id for route in routes.UPDATE_ROUTES}
    require(required_route_ids.issubset(registry_ids), "AI connector routes missing from UPDATE_ROUTES")

    for route_id in required_route_ids:
        meta = routes.route_metadata(route_id)
        require(meta.get("target_module") == "engel_ai_connector_hub", "route target module mismatch: " + route_id)
        require(bool(meta.get("read_only")) is True, "connector route must be read-only: " + route_id)
        require(bool(meta.get("status_only")) is True, "connector route must be status-only: " + route_id)
        require(bool(meta.get("no_provider_model_network")) is True, "connector status route must not allow provider/network: " + route_id)
        rendered = routes.render_update_route(route_id)
        require("Engel AI Connector" in rendered or "Hermes Source Zip Audit" in rendered, "route did not render connector text: " + route_id)

    alias_expectations = {
        "show ai connectors": "engel.ai_connectors.status",
        "connect other ais": "engel.ai_connectors.status",
        "show hermes ai adapters": "engel.ai_connectors.adapters",
        "ai connector blueprint": "engel.ai_connectors.blueprint",
        "copy hermes connector pattern": "engel.ai_connectors.blueprint",
        "ai connector rules": "engel.ai_connectors.rules",
        "hermes zip audit": "engel.ai_connectors.zip_audit",
    }
    for phrase, route_id in alias_expectations.items():
        require(routes.resolve_update_route(phrase) == route_id, "alias did not resolve: " + phrase)
        result = route_companion_text_or_command(phrase, context="ai_connector_hub_verifier")
        require(result.handled is True, "communication router did not handle: " + phrase)
        require(result.route_target == route_id, "communication router route mismatch: " + phrase)
        require(bool(result.response.strip()), "communication router empty response: " + phrase)

    catalog = explorer.route_catalog_for_gui()
    connector_entries = [entry for entry in catalog if str(entry.get("route_id", "")).startswith("engel.ai_connectors")]
    require(len(connector_entries) == len(required_route_ids), "Super Swarm route catalog missing AI connector entries")
    for entry in connector_entries:
        require(entry.get("group") == "AI Connectors", "AI connector route grouped incorrectly")
    rendered_catalog = explorer.render_route_explorer()
    require("AI Connectors" in rendered_catalog, "route explorer output missing AI Connectors group")
    require("Engel AI Connector Hub status" in rendered_catalog, "route explorer output missing connector status")


def check_entry_docs_and_full_verifier_hook() -> None:
    entry = read(ENTRY)
    commands = read(COMMANDS)
    memory_json = read(MEMORY_JSON)
    memory_md = read(MEMORY_MD)
    fast_record = read(FAST_EXTERNAL_RECORD)
    slow_record = read(SLOW_EXTERNAL_RECORD)
    core_data = json.loads(read(CORE_MAP_JSON))
    core_md = read(CORE_MAP_MD)
    report = read(REPORT)
    codex = read(CODEX_VERIFY)
    require("ENGEL_AI_CONNECTORS_STATUS_ROUTE_ID" in entry, "engel_ai self-test missing AI connector status")
    require("show ai connectors / ai connector blueprint / show hermes ai adapters" in entry, "engel_ai routes output missing AI connector summary")
    for needle in [
        "Engel AI Connector Hub routes",
        "engel_ai_connector_hub.py",
        "show ai connectors",
        "copy hermes connector pattern",
        "Super Swarm",
    ]:
        require(needle in commands, "ENGEL_COMMANDS missing connector text: " + needle)
    for needle in [
        "ENGEL_INTERNAL_MEMORY_RECORD",
        "CONNECT_OTHER_AIS_THROUGH_ENGEL",
        "engel.ai_connectors.status",
        "engel_ai_update_routes.py",
        r"F:\\ENGEL_APP_MEMORY",
        r"E:\\ENGEL_APP_MEMORY",
        "fast external memory shelf",
        "slower disk-drive archive shelf",
    ]:
        require(needle in memory_json, "connector memory JSON missing: " + needle)
    for needle in [
        "# Engel AI Connector Hub V1",
        "Engel remembers the internal connector pattern",
        "show ai connectors",
        "Future outside-AI action routes",
        "F:\\ENGEL_APP_MEMORY",
        "E:\\ENGEL_APP_MEMORY",
        "faster external memory shelf",
        "slower disk-drive archive shelf",
    ]:
        require(needle in memory_md, "connector memory Markdown missing: " + needle)
    for text, label in [(fast_record, "fast external record"), (slow_record, "slow external record")]:
        for needle in [
            "Engel AI Connector Hub V1",
            "Project authority remains",
            "engel_ai_update_routes.py",
            "show ai connectors",
            "recall/archive mirror only",
        ]:
            require(needle in text, label + " missing: " + needle)
    require("fast external memory shelf" in fast_record, "fast external record missing F role")
    require("slower disk-drive archive shelf" in slow_record, "slow external record missing E role")
    nodes = core_data.get("nodes", {})
    core_node = nodes.get("engel_ai_connector_hub_v1") if isinstance(nodes, dict) else None
    if not isinstance(core_node, dict):
        core_node = core_data.get("engel_ai_connector_hub_v1")
    require(isinstance(core_node, dict), "Core Continuity missing Engel AI Connector Hub node")
    require(core_node.get("type") == "ai_connector_hub_internal_memory", "Core Continuity connector node type mismatch")
    require(core_node.get("external_memory", {}).get("fast_external_memory_root") == str(FAST_EXTERNAL_MEMORY), "Core Continuity missing F fast memory root")
    require(core_node.get("external_memory", {}).get("slow_archive_external_memory_root") == str(SLOW_EXTERNAL_MEMORY), "Core Continuity missing E slow archive root")
    for route_id in [
        "engel.ai_connectors.status",
        "engel.ai_connectors.adapters",
        "engel.ai_connectors.blueprint",
        "engel.ai_connectors.rules",
        "engel.ai_connectors.zip_audit",
    ]:
        require(route_id in core_node.get("routes", []), "Core Continuity connector node missing route: " + route_id)
    for needle in [
        "Engel AI Connector Hub V1",
        "CONNECT_OTHER_AIS_THROUGH_ENGEL",
        "F:\\ENGEL_APP_MEMORY",
        "E:\\ENGEL_APP_MEMORY",
        "no hidden sync",
    ]:
        require(needle in core_md, "Core Continuity Markdown missing connector text: " + needle)
    for needle in [
        "# Engel AI Connector Hub V1",
        "Hermes connector pattern",
        "Changed Files",
        "Verification",
        "No second route system",
    ]:
        require(needle in report, "report missing connector text: " + needle)
    require("tools\\verify_engel_ai_connector_hub.py" in codex, "codex_verify missing AI connector hub verifier")


def main() -> int:
    checks = [
        ("files_and_import_safety", check_files_and_import_safety),
        ("inventory_copies_hermes_connector_pattern", check_inventory_copies_hermes_connector_pattern),
        ("routes_and_superswarm_visibility", check_routes_and_superswarm_visibility),
        ("entry_docs_and_full_verifier_hook", check_entry_docs_and_full_verifier_hook),
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
        print("\nEngel AI Connector Hub verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nEngel AI Connector Hub verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
