"""Engel AI Connector Hub.

This is a read-only presentation layer over the Hermes-derived connector
pattern already vendored in ``engel_agent_main`` and the source reference zip at
``D:\\b.WorkSpace\\hermes-agent-main.zip``. It does not create a second router,
does not extract the zip, and does not start provider/model/network processes.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Iterable


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
WORKSPACE_ROOT = ROOT.parent
SOURCE_ZIP = WORKSPACE_ROOT / "hermes-agent-main.zip"
ENGEL_AGENT_ROOT = ROOT / "engel_agent_main"
CONNECTOR_MEMORY_JSON = ROOT / "memory" / "ENGEL_AI_CONNECTOR_HUB_V1.json"
CONNECTOR_MEMORY_MD = ROOT / "memory" / "ENGEL_AI_CONNECTOR_HUB_V1.md"
EXTERNAL_MEMORY_ROOTS: tuple[Path, ...] = (
    Path("/opt/engel"),
    Path("/mnt/engel-hdd-vault"),
)
EXTERNAL_MEMORY_ROLES: dict[str, str] = {
    "/opt/engel": "CT246 fast SSD active runtime, chat, model, and connector-memory surface",
    "/mnt/engel-hdd-vault": "Dell PowerEdge HDD/ZFS cold archive for training outputs and bulk datasets",
}
EXTERNAL_MEMORY_RECORDS: tuple[Path, ...] = tuple(
    root / "manifests" / "ENGEL_AI_CONNECTOR_HUB_V1.md" for root in EXTERNAL_MEMORY_ROOTS
)
MAX_DOC_CHARS = 1800
MAX_LIST_ITEMS = 18


ACP_CORE_PATHS: tuple[str, ...] = (
    "acp_adapter/entry.py",
    "acp_adapter/server.py",
    "acp_adapter/session.py",
    "acp_adapter/events.py",
    "acp_adapter/permissions.py",
    "acp_adapter/tools.py",
    "acp_adapter/auth.py",
    "acp_registry/agent.json",
)

PROVIDER_RUNTIME_PATHS: tuple[str, ...] = (
    "engel_cli/runtime_provider.py",
    "engel_cli/auth.py",
    "engel_cli/model_switch.py",
    "providers/base.py",
    "providers/__init__.py",
    "agent/credential_pool.py",
    "agent/credential_sources.py",
)

NATIVE_ADAPTER_PATHS: tuple[str, ...] = (
    "agent/anthropic_adapter.py",
    "agent/bedrock_adapter.py",
    "agent/codex_responses_adapter.py",
    "agent/gemini_cloudcode_adapter.py",
    "agent/gemini_native_adapter.py",
    "agent/google_code_assist.py",
    "agent/copilot_acp_client.py",
    "agent/azure_identity_adapter.py",
    "agent/browser_provider.py",
    "agent/browser_registry.py",
    "agent/image_gen_provider.py",
    "agent/image_gen_registry.py",
    "agent/web_search_provider.py",
    "agent/web_search_registry.py",
    "agent/video_gen_provider.py",
    "agent/video_gen_registry.py",
    "agent/memory_provider.py",
)

DEVELOPER_DOC_PATHS: tuple[str, ...] = (
    "website/docs/developer-guide/adding-providers.md",
    "website/docs/developer-guide/provider-runtime.md",
    "website/docs/developer-guide/model-provider-plugin.md",
    "website/docs/developer-guide/adding-platform-adapters.md",
    "website/docs/developer-guide/acp-internals.md",
)


def _zip_prefix(path: str) -> str:
    return "hermes-agent-main/" + path.strip("/\\")


def _zip_path_candidates(path: str) -> tuple[str, ...]:
    path = path.strip("/\\")
    if path.startswith("engel_cli/"):
        return (path, "hermes_cli/" + path[len("engel_cli/") :])
    return (path,)


def _zip_names() -> tuple[str, ...]:
    if not SOURCE_ZIP.is_file():
        return ()
    try:
        with zipfile.ZipFile(SOURCE_ZIP) as zf:
            return tuple(zf.namelist())
    except (OSError, zipfile.BadZipFile):
        return ()


def _zip_has(path: str, names: Iterable[str] | None = None) -> bool:
    entries = set(names if names is not None else _zip_names())
    return any(_zip_prefix(candidate) in entries for candidate in _zip_path_candidates(path))


def _local_has(path: str) -> bool:
    return (ENGEL_AGENT_ROOT / path).is_file()


def _local_file_count() -> int:
    if not ENGEL_AGENT_ROOT.is_dir():
        return 0
    return sum(1 for item in ENGEL_AGENT_ROOT.rglob("*") if item.is_file())


def _zip_file_count(names: Iterable[str]) -> int:
    return sum(1 for name in names if not name.endswith("/"))


def _read_zip_text(path: str, limit: int = MAX_DOC_CHARS) -> str:
    if not SOURCE_ZIP.is_file():
        return ""
    try:
        with zipfile.ZipFile(SOURCE_ZIP) as zf:
            data = b""
            for candidate in _zip_path_candidates(path):
                try:
                    data = zf.read(_zip_prefix(candidate))
                    break
                except KeyError:
                    continue
            if not data:
                return ""
    except (KeyError, OSError, zipfile.BadZipFile):
        return ""
    return data.decode("utf-8", "replace")[:limit].replace("\r\n", "\n").replace("\r", "\n")


def _collect_plugin_names(names: Iterable[str], prefix: str, marker: str) -> list[str]:
    found: set[str] = set()
    full_prefix = _zip_prefix(prefix).rstrip("/") + "/"
    for name in names:
        if not name.startswith(full_prefix) or not name.endswith(marker):
            continue
        rest = name[len(full_prefix) :]
        parts = rest.split("/")
        if parts and parts[0]:
            found.add(parts[0])
    return sorted(found)


def _collect_local_plugin_names(prefix: str, marker: str) -> list[str]:
    root = ENGEL_AGENT_ROOT / prefix
    if not root.is_dir():
        return []
    found: set[str] = set()
    for path in root.rglob(marker):
        try:
            found.add(path.relative_to(root).parts[0])
        except ValueError:
            continue
    return sorted(found)


def _format_check_rows(title: str, paths: Iterable[str], zip_names: Iterable[str]) -> list[str]:
    lines = [title + ":"]
    for rel in paths:
        zip_ok = "zip" if _zip_has(rel, zip_names) else "zip-missing"
        local_ok = "local" if _local_has(rel) else "local-missing"
        lines.append("- " + rel + " [" + zip_ok + ", " + local_ok + "]")
    return lines


def _format_list(title: str, values: Iterable[str], *, limit: int = MAX_LIST_ITEMS) -> list[str]:
    items = list(values)
    if not items:
        return [title + ": none found"]
    shown = items[:limit]
    lines = [title + " (" + str(len(items)) + "):"]
    lines.extend("- " + item for item in shown)
    if len(items) > len(shown):
        lines.append("- ... +" + str(len(items) - len(shown)) + " more")
    return lines


def build_connector_inventory() -> dict[str, object]:
    names = _zip_names()
    zip_model_plugins = _collect_plugin_names(names, "plugins/model-providers", "plugin.yaml")
    local_model_plugins = _collect_local_plugin_names("plugins/model-providers", "plugin.yaml")
    zip_platform_adapters = _collect_plugin_names(names, "plugins/platforms", "adapter.py")
    local_platform_adapters = _collect_local_plugin_names("plugins/platforms", "adapter.py")
    zip_web_plugins = _collect_plugin_names(names, "plugins/web", "provider.py")
    local_web_plugins = _collect_local_plugin_names("plugins/web", "provider.py")
    zip_browser_plugins = _collect_plugin_names(names, "plugins/browser", "provider.py")
    local_browser_plugins = _collect_local_plugin_names("plugins/browser", "provider.py")
    return {
        "source_zip": str(SOURCE_ZIP),
        "source_zip_present": SOURCE_ZIP.is_file(),
        "source_zip_entries": len(names),
        "source_zip_files": _zip_file_count(names),
        "vendored_root": str(ENGEL_AGENT_ROOT),
        "vendored_root_present": ENGEL_AGENT_ROOT.is_dir(),
        "vendored_file_count": _local_file_count(),
        "memory_json": str(CONNECTOR_MEMORY_JSON),
        "memory_json_present": CONNECTOR_MEMORY_JSON.is_file(),
        "memory_markdown": str(CONNECTOR_MEMORY_MD),
        "memory_markdown_present": CONNECTOR_MEMORY_MD.is_file(),
        "external_memory_roots": [str(root) for root in EXTERNAL_MEMORY_ROOTS],
        "external_memory_roles": dict(EXTERNAL_MEMORY_ROLES),
        "external_memory_roots_present": {str(root): root.is_dir() for root in EXTERNAL_MEMORY_ROOTS},
        "external_memory_records": [str(path) for path in EXTERNAL_MEMORY_RECORDS],
        "external_memory_records_present": {str(path): path.is_file() for path in EXTERNAL_MEMORY_RECORDS},
        "acp_core_complete": all(_zip_has(path, names) and _local_has(path) for path in ACP_CORE_PATHS),
        "provider_runtime_complete": all(_zip_has(path, names) and _local_has(path) for path in PROVIDER_RUNTIME_PATHS),
        "native_adapters_found": [path for path in NATIVE_ADAPTER_PATHS if _zip_has(path, names) or _local_has(path)],
        "model_provider_plugins": sorted(set(zip_model_plugins) | set(local_model_plugins)),
        "platform_adapters": sorted(set(zip_platform_adapters) | set(local_platform_adapters)),
        "web_provider_plugins": sorted(set(zip_web_plugins) | set(local_web_plugins)),
        "browser_provider_plugins": sorted(set(zip_browser_plugins) | set(local_browser_plugins)),
        "developer_docs_found": [path for path in DEVELOPER_DOC_PATHS if _zip_has(path, names) or _local_has(path)],
    }


def render_ai_connector_status(_payload: str = "") -> str:
    inv = build_connector_inventory()
    lines = [
        "# Engel AI Connector Hub",
        "",
        "Purpose: connect other AI runtimes to Engel through the existing Engel AI route spine.",
        "",
        "Current spine:",
        "- engel_ai.py ask",
        "- engel_communication_router.py",
        "- engel_ai_update_routes.py",
        "- connector runner module",
        "- Super Swarm Routes tab reads the same registry",
        "",
        "Source pattern copied into Engel branding:",
        "- Source zip: " + str(inv["source_zip"]),
        "- Source zip present: " + str(inv["source_zip_present"]),
        "- Source zip entries/files: " + str(inv["source_zip_entries"]) + "/" + str(inv["source_zip_files"]),
        "- Vendored Engel Agent root: " + str(inv["vendored_root"]),
        "- Vendored root present: " + str(inv["vendored_root_present"]),
        "- Vendored file count: " + str(inv["vendored_file_count"]),
        "- Connector memory JSON present: " + str(inv["memory_json_present"]),
        "- Connector memory Markdown present: " + str(inv["memory_markdown_present"]),
        "- External memory roots: " + ", ".join(str(root) for root in inv["external_memory_roots"]),
        "- External memory roles: " + "; ".join(
            str(root) + "=" + str(role)
            for root, role in dict(inv["external_memory_roles"]).items()
        ),
        "- External memory root presence: " + "; ".join(
            str(root) + "=" + str(present)
            for root, present in dict(inv["external_memory_roots_present"]).items()
        ),
        "- External connector memory records: " + "; ".join(
            str(path) + "=" + str(present)
            for path, present in dict(inv["external_memory_records_present"]).items()
        ),
        "- ACP core complete: " + str(inv["acp_core_complete"]),
        "- Provider runtime complete: " + str(inv["provider_runtime_complete"]),
        "",
        "What this gives Engel:",
        "- ACP-style editor/agent bridge pattern",
        "- model provider plugin registry",
        "- native provider adapters",
        "- credential pool/source pattern",
        "- platform adapter pattern",
        "- Super Swarm-visible route registration pattern",
        "- durable project-local memory record for connector internals",
        "",
        "Try:",
        "- show ai connectors",
        "- show hermes ai adapters",
        "- ai connector blueprint",
        "- ai connector rules",
    ]
    return "\n".join(lines)


def render_ai_connector_adapters(_payload: str = "") -> str:
    inv = build_connector_inventory()
    names = _zip_names()
    lines = [
        "# Engel AI Connector Adapter Inventory",
        "",
        "This is the Hermes connector pattern as an Engel route surface. It inspects the vendored tree and source zip without extracting or running either one.",
        "",
        *_format_check_rows("ACP bridge files", ACP_CORE_PATHS, names),
        "",
        *_format_check_rows("Provider runtime and credential files", PROVIDER_RUNTIME_PATHS, names),
        "",
        *_format_check_rows("Native adapter/provider files", NATIVE_ADAPTER_PATHS, names),
        "",
        *_format_list("Model provider plugins", inv["model_provider_plugins"]),
        "",
        *_format_list("Platform adapters", inv["platform_adapters"]),
        "",
        *_format_list("Web provider plugins", inv["web_provider_plugins"]),
        "",
        *_format_list("Browser provider plugins", inv["browser_provider_plugins"]),
        "",
        *_format_list("Developer docs copied as reference pattern", inv["developer_docs_found"]),
    ]
    return "\n".join(lines)


def render_ai_connector_blueprint(_payload: str = "") -> str:
    lines = [
        "# Engel AI Connector Blueprint",
        "",
        "Use this pattern when adding another AI to Engel. The connector is part of Engel AI, not a separate command island.",
        "",
        "Required path through the system:",
        "1. Add or vendor the AI runtime under an Engel-branded folder.",
        "2. Add one runner module that owns that runtime's adapter calls.",
        "3. Register natural phrases in engel_ai_update_routes.py.",
        "4. Let engel_communication_router.py resolve phrases to route IDs.",
        "5. Let Super Swarm discover the routes through engel_route_explorer.py.",
        "6. Add a verifier that proves the routes render, safety flags match the phase, and no dead-end aliases exist.",
        "",
        "Connector descriptor shape:",
        "```json",
        "{",
        "  \"connector_id\": \"engel.<brand>.status\",",
        "  \"brand_name\": \"Engel <Brand>\",",
        "  \"runtime_root\": \"D:\\\\b.WorkSpace\\\\Engel App\\\\engel_<brand>_main\",",
        "  \"runner_module\": \"engel_<brand>_runner.py\",",
        "  \"route_owner\": \"engel_ai_update_routes.py\",",
        "  \"gui_surface\": \"Super Swarm Routes tab\",",
        "  \"provider_network\": \"explicit_action_routes_only\",",
        "  \"background_work\": \"explicit_action_routes_only\",",
        "  \"credential_source\": \"runtime-owned; never hardcoded in route aliases\",",
        "  \"verifier\": \"tools\\\\verify_engel_<brand>_connector.py\"",
        "}",
        "```",
        "",
        "Minimum routes for each outside AI connector:",
        "- status: what is installed and what is missing",
        "- features: what the connector can do in plain language",
        "- docs: where the relevant local docs live",
        "- invoke or run: explicit action route only, with clear safety flags",
        "",
        "Hermes pieces copied into the Engel mental model:",
        "- ACP adapter: editor/agent session bridge",
        "- provider runtime: provider/model/credential resolution",
        "- provider plugins: first-class named AI backends",
        "- native adapters: non-OpenAI API shapes",
        "- permission bridge: dangerous actions route through explicit approval",
        "- tests/verifiers: route behavior is proven instead of assumed",
    ]
    return "\n".join(lines)


def render_ai_connector_rules(_payload: str = "") -> str:
    lines = [
        "# Engel AI Connector Rules",
        "",
        "Phase rule: Engel can connect outside AIs, but every connector must remain inside Engel AI's route registry.",
        "",
        "Allowed in this phase:",
        "- branded connector routes",
        "- provider/model/network behavior for routes explicitly marked as action routes",
        "- background work only for explicit action routes that declare it",
        "- credentials owned by the runtime/provider layer, not by natural-language aliases",
        "- Super Swarm visibility through the shared route catalog",
        "- verifiers proving every added alias resolves and renders",
        "",
        "Still blocked by default:",
        "- hidden startup provider calls",
        "- unregistered route execution",
        "- a second route registry",
        "- silent credential creation or hardcoded secrets",
        "- provider/model/network behavior from status routes",
        "- action routes that are invisible from Super Swarm",
        "- aliases that render instructions but lead nowhere",
        "",
        "Naming rule:",
        "- User-facing names should be Engel-branded.",
        "- Upstream names may remain in provenance, docs, command binaries, or adapter internals when changing them would break the runtime.",
        "- Route IDs should prefer stable Engel names like engel.ai_connectors.* over upstream project labels.",
    ]
    return "\n".join(lines)


def render_ai_connector_zip_audit(_payload: str = "") -> str:
    inv = build_connector_inventory()
    agent_manifest = _read_zip_text("acp_registry/agent.json", 1000)
    provider_runtime_doc = _read_zip_text("website/docs/developer-guide/provider-runtime.md", MAX_DOC_CHARS)
    adding_providers_doc = _read_zip_text("website/docs/developer-guide/adding-providers.md", MAX_DOC_CHARS)
    lines = [
        "# Hermes Source Zip Audit For Engel",
        "",
        "No extraction was performed. The zip is read as source evidence for the Engel connector pattern.",
        "",
        "Counts:",
        "- Zip entries: " + str(inv["source_zip_entries"]),
        "- Zip files: " + str(inv["source_zip_files"]),
        "- Engel vendored files: " + str(inv["vendored_file_count"]),
        "",
        "ACP registry manifest excerpt:",
        "```json",
        agent_manifest.strip(),
        "```",
        "",
        "Provider runtime excerpt:",
        "```md",
        provider_runtime_doc.strip(),
        "```",
        "",
        "Adding providers excerpt:",
        "```md",
        adding_providers_doc.strip(),
        "```",
    ]
    return "\n".join(lines)


def main() -> int:
    print(render_ai_connector_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
