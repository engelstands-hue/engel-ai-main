#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = ROOT / "engel_account_connector.py"
ROUTES = ROOT / "engel_ai_update_routes.py"
EXPLORER = ROOT / "engel_route_explorer.py"
ENTRY = ROOT / "engel_ai.py"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
MEMORY_JSON = ROOT / "memory" / "ENGEL_ACCOUNT_CONNECTOR_V1.json"
MEMORY_MD = ROOT / "memory" / "ENGEL_ACCOUNT_CONNECTOR_V1.md"
CORE_MAP_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
CORE_MAP_MD = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_ACCOUNT_CONNECTOR_V1.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
VENDORED_AGENT_ROOT = ROOT / "engel_agent_main"
FAST_EXTERNAL_MEMORY = Path(r"F:\ENGEL_APP_MEMORY")
SLOW_EXTERNAL_MEMORY = Path(r"E:\ENGEL_APP_MEMORY")
FAST_EXTERNAL_RECORD = FAST_EXTERNAL_MEMORY / "manifests" / "ENGEL_ACCOUNT_CONNECTOR_V1.md"
SLOW_EXTERNAL_RECORD = SLOW_EXTERNAL_MEMORY / "manifests" / "ENGEL_ACCOUNT_CONNECTOR_V1.md"


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
    for path in [ACCOUNT, ROUTES, EXPLORER, ENTRY, COMMANDS, MEMORY_JSON, MEMORY_MD, CORE_MAP_JSON, CORE_MAP_MD, REPORT, CODEX_VERIFY]:
        require(path.exists() and path.is_file(), "missing required file: " + str(path.relative_to(ROOT)))
    require(VENDORED_AGENT_ROOT.exists() and VENDORED_AGENT_ROOT.is_dir(), "missing vendored Engel Agent root")
    require(FAST_EXTERNAL_MEMORY.exists() and FAST_EXTERNAL_MEMORY.is_dir(), "missing fast external memory root")
    require(SLOW_EXTERNAL_MEMORY.exists() and SLOW_EXTERNAL_MEMORY.is_dir(), "missing slow external memory root")
    require(FAST_EXTERNAL_RECORD.exists() and FAST_EXTERNAL_RECORD.is_file(), "missing fast external account memory record")
    require(SLOW_EXTERNAL_RECORD.exists() and SLOW_EXTERNAL_RECORD.is_file(), "missing slow external account memory record")

    source = read(ACCOUNT)
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
        "read_text",
        "read_bytes",
        "open",
        "unlink",
        "remove",
        "rename",
        "mkdir",
        "rmdir",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in blocked_import_roots, "account connector imports runtime/network package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in blocked_import_roots, "account connector imports runtime/network package: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                require(func.attr not in blocked_calls, "account connector calls secret/runtime/mutation helper: " + func.attr)
            elif isinstance(func, ast.Name):
                require(func.id not in blocked_calls, "account connector calls secret/runtime/mutation helper: " + func.id)

    module = import_module(ACCOUNT, "engel_account_connector_import_check")
    require(hasattr(module, "build_account_connector_inventory"), "account connector missing inventory builder")
    require(hasattr(module, "render_account_connector_status"), "account connector missing status renderer")


def check_inventory_and_outputs() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import engel_account_connector as account

    inv = account.build_account_connector_inventory()
    require(inv.get("inside_engel_ai") is True, "inventory does not mark account connector inside Engel")
    require(inv.get("engel_agent_root_present") is True, "vendored Engel Agent root not detected")
    require(int(inv.get("provider_plugin_count", 0)) >= 20, "provider plugin count unexpectedly low")
    plugins = set(str(item) for item in inv.get("provider_plugins", []))
    for plugin in ["openai-codex", "anthropic", "copilot-acp", "gemini", "openrouter", "xai"]:
        require(plugin in plugins, "provider plugin missing from inventory: " + plugin)

    dependency_rows = list(inv.get("dependency_rows", []))
    require(dependency_rows, "dependency rows missing")
    for package in ["python-dotenv", "openai", "rich", "httpx", "pyyaml"]:
        require(any(str(row.get("package")) == package for row in dependency_rows), "dependency row missing: " + package)

    rendered = account.render_account_connector_status()
    gate = str(inv.get("runtime_dependency_gate", "")).upper()
    for needle in [
        "Engel Account Connector",
        "account connection belongs inside Engel",
        "One Engel route spine",
        "Super Swarm visibility",
        "Actual login attempted by this route: no",
        "Secret values read or printed: no",
        gate,
    ]:
        require(needle in rendered, "status output missing: " + needle)
    providers = account.render_account_connector_providers()
    for needle in ["ChatGPT / OpenAI Codex", "Anthropic / Claude", "GitHub Copilot", "OpenRouter", "All detected model provider plugins"]:
        require(needle in providers, "provider output missing: " + needle)
    setup = account.render_account_connector_setup()
    for needle in ["Account setup should be driven from Engel", "Where Engel stores account material", "not into chat"]:
        require(needle in setup, "setup output missing: " + needle)
    safety = account.render_account_connector_safety()
    for needle in ["No API keys or OAuth tokens in chat", "F:\\ENGEL_APP_MEMORY", "E:\\ENGEL_APP_MEMORY"]:
        require(needle in safety, "safety output missing: " + needle)


def check_routes_and_superswarm_visibility() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import engel_ai_update_routes as routes
    import engel_route_explorer as explorer
    from engel_communication_router import route_companion_text_or_command

    required_route_ids = {
        "engel.accounts.status",
        "engel.accounts.providers",
        "engel.accounts.setup",
        "engel.accounts.safety",
    }
    registry_ids = {route.route_id for route in routes.UPDATE_ROUTES}
    require(required_route_ids.issubset(registry_ids), "account connector routes missing from UPDATE_ROUTES")

    for route_id in required_route_ids:
        meta = routes.route_metadata(route_id)
        require(meta.get("target_module") == "engel_account_connector", "account route target module mismatch: " + route_id)
        require(bool(meta.get("read_only")) is True, "account route must be read-only: " + route_id)
        require(bool(meta.get("status_only")) is True, "account route must be status-only: " + route_id)
        require(bool(meta.get("no_provider_model_network")) is True, "account status route must not allow provider/network: " + route_id)
        rendered = routes.render_update_route(route_id)
        require("Engel Account" in rendered, "route did not render account connector text: " + route_id)

    alias_expectations = {
        "connect my account": "engel.accounts.status",
        "connect account to engel": "engel.accounts.status",
        "show account providers": "engel.accounts.providers",
        "account setup in engel": "engel.accounts.setup",
        "how do i connect my account in engel": "engel.accounts.setup",
        "account connection safety": "engel.accounts.safety",
        "where does engel store accounts": "engel.accounts.safety",
        "should i paste my api key": "engel.accounts.safety",
    }
    for phrase, route_id in alias_expectations.items():
        require(routes.resolve_update_route(phrase) == route_id, "alias did not resolve: " + phrase)
        result = route_companion_text_or_command(phrase, context="account_connector_verifier")
        require(result.handled is True, "communication router did not handle: " + phrase)
        require(result.route_target == route_id, "communication router route mismatch: " + phrase)
        require(bool(result.response.strip()), "communication router empty response: " + phrase)

    catalog = explorer.route_catalog_for_gui()
    account_entries = [entry for entry in catalog if str(entry.get("route_id", "")).startswith("engel.accounts")]
    require(len(account_entries) == len(required_route_ids), "Super Swarm route catalog missing account entries")
    for entry in account_entries:
        require(entry.get("group") == "Accounts", "account route grouped incorrectly")
    rendered_catalog = explorer.render_route_explorer()
    require("Accounts" in rendered_catalog, "route explorer output missing Accounts group")
    require("Engel Account Connector status" in rendered_catalog, "route explorer output missing account status")


def check_entry_docs_memory_and_verifier_hook() -> None:
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

    require("ENGEL_ACCOUNT_CONNECTOR_STATUS_ROUTE_ID" in entry, "engel_ai self-test missing account connector status")
    require("connect my account / show account providers / account setup in engel" in entry, "engel_ai routes output missing account connector summary")
    for needle in [
        "Engel Account Connector routes",
        "engel_account_connector.py",
        "connect my account",
        "show account providers",
        "account setup in engel",
        "should i paste my api key",
        "Super Swarm Routes tab",
    ]:
        require(needle in commands, "ENGEL_COMMANDS missing account text: " + needle)
    for needle in [
        "ACCOUNT_CONNECTION_BELONGS_INSIDE_ENGEL",
        "NO_CHAT_SECRET_CAPTURE",
        "engel.accounts.status",
        "engel_account_connector.py",
        r"F:\\ENGEL_APP_MEMORY",
        r"E:\\ENGEL_APP_MEMORY",
    ]:
        require(needle in memory_json, "account memory JSON missing: " + needle)
    for needle in [
        "# Engel Account Connector V1",
        "account connection belongs inside Engel",
        "connect my account",
        "Do not paste API keys or OAuth tokens into chat",
        "F:\\ENGEL_APP_MEMORY",
        "E:\\ENGEL_APP_MEMORY",
    ]:
        require(needle in memory_md, "account memory Markdown missing: " + needle)
    for text, label in [(fast_record, "fast external record"), (slow_record, "slow external record")]:
        for needle in [
            "Engel Account Connector V1",
            "Project authority remains",
            "engel_ai_update_routes.py",
            "connect my account",
            "recall/archive mirror only",
        ]:
            require(needle in text, label + " missing: " + needle)
    require("faster external memory shelf" in fast_record, "fast external record missing F role")
    require("slower disk-drive archive shelf" in slow_record, "slow external record missing E role")

    nodes = core_data.get("nodes", {})
    core_node = nodes.get("engel_account_connector_v1") if isinstance(nodes, dict) else None
    if not isinstance(core_node, dict):
        core_node = core_data.get("engel_account_connector_v1")
    require(isinstance(core_node, dict), "Core Continuity missing Engel Account Connector node")
    require(core_node.get("type") == "account_connector_internal_memory", "Core Continuity account node type mismatch")
    require(core_node.get("external_memory", {}).get("fast_external_memory_root") == str(FAST_EXTERNAL_MEMORY), "Core Continuity missing F fast memory root")
    require(core_node.get("external_memory", {}).get("slow_archive_external_memory_root") == str(SLOW_EXTERNAL_MEMORY), "Core Continuity missing E slow archive root")
    for route_id in ["engel.accounts.status", "engel.accounts.providers", "engel.accounts.setup", "engel.accounts.safety"]:
        require(route_id in core_node.get("routes", []), "Core Continuity account node missing route: " + route_id)
    for needle in [
        "Engel Account Connector V1",
        "ACCOUNT_CONNECTION_BELONGS_INSIDE_ENGEL",
        "F:\\ENGEL_APP_MEMORY",
        "E:\\ENGEL_APP_MEMORY",
        "no hidden sync",
    ]:
        require(needle in core_md, "Core Continuity Markdown missing account text: " + needle)
    for needle in [
        "# Engel Account Connector V1",
        "Changed Files",
        "Engel AI Routes Added",
        "Verification",
        "No second route system",
    ]:
        require(needle in report, "report missing account text: " + needle)
    require("tools\\verify_engel_account_connector.py" in codex, "codex_verify missing account connector verifier")


def main() -> int:
    checks = [
        ("files_and_import_safety", check_files_and_import_safety),
        ("inventory_and_outputs", check_inventory_and_outputs),
        ("routes_and_superswarm_visibility", check_routes_and_superswarm_visibility),
        ("entry_docs_memory_and_verifier_hook", check_entry_docs_memory_and_verifier_hook),
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
        print("\nEngel Account Connector verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nEngel Account Connector verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
