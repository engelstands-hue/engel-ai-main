"""Engel account connector surface.

This module makes provider/account setup visible through Engel AI routes.
It is intentionally status and guidance only: it does not read secret values,
does not start login flows, and does not run subprocesses on import.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
WORKSPACE_ROOT = ROOT.parent
ENGEL_AGENT_ROOT = ROOT / "engel_agent_main"
MODEL_PROVIDER_PLUGIN_ROOT = ENGEL_AGENT_ROOT / "plugins" / "model-providers"
ACCOUNT_MEMORY_JSON = ROOT / "memory" / "ENGEL_ACCOUNT_CONNECTOR_V1.json"
ACCOUNT_MEMORY_MD = ROOT / "memory" / "ENGEL_ACCOUNT_CONNECTOR_V1.md"
FAST_EXTERNAL_MEMORY = Path(r"D:\b.WorkSpace\Engel App\runtime")
CT246_ACTIVE_ROOT = Path("/opt/engel")
CT246_HDD_ARCHIVE_ROOT = Path("/mnt/engel-hdd-vault")
APPROVED_ENGEL_HOME = FAST_EXTERNAL_MEMORY / "engel-home"
FAST_EXTERNAL_RECORD = FAST_EXTERNAL_MEMORY / "manifests" / "ENGEL_ACCOUNT_CONNECTOR_V1.md"
CT246_POLICY_RECORD = FAST_EXTERNAL_MEMORY / "manifests" / "ENGEL_CT246_STORAGE_POLICY_V1.md"


def _path_on_os_drive(path: Path | str | None) -> bool:
    if path is None:
        return False
    text = str(path).replace("/", "\\").lower()
    return text.startswith("c:\\") or text.startswith("\\\\?\\c:\\")


def _resolve_engel_home() -> tuple[Path, str, bool]:
    env_value = os.environ.get("ENGEL_HOME", "").strip()
    if env_value:
        candidate = Path(env_value)
        if not _path_on_os_drive(candidate):
            return candidate, "ENGEL_HOME", False
        return APPROVED_ENGEL_HOME, "approved_f_external_default", True
    return APPROVED_ENGEL_HOME, "approved_f_external_default", False


ENGEL_HOME, ENGEL_HOME_SOURCE, ENGEL_HOME_ENV_REJECTED_ON_OS_DRIVE = _resolve_engel_home()
CONFIG_FILE = ENGEL_HOME / "config.yaml"
ENV_FILE = ENGEL_HOME / ".env"
AUTH_FILE = ENGEL_HOME / "auth.json"
AUTH_FOLDER = ENGEL_HOME / "auth"

REQUIRED_IMPORTS: tuple[tuple[str, str], ...] = (
    ("dotenv", "python-dotenv"),
    ("openai", "openai"),
    ("rich", "rich"),
    ("httpx", "httpx"),
    ("yaml", "pyyaml"),
)

ACCOUNT_PROVIDER_MENU: tuple[dict[str, str], ...] = (
    {
        "name": "ChatGPT / OpenAI Codex",
        "plugin": "openai-codex",
        "auth": "OAuth or provider token through the Engel Agent provider layer",
    },
    {
        "name": "Anthropic / Claude",
        "plugin": "anthropic",
        "auth": "OAuth where available, or ANTHROPIC_API_KEY through Engel-owned secret storage",
    },
    {
        "name": "GitHub Copilot",
        "plugin": "copilot-acp",
        "auth": "OAuth or GitHub token through the credential pool",
    },
    {
        "name": "Google Gemini",
        "plugin": "gemini",
        "auth": "OAuth or GEMINI_API_KEY through Engel-owned secret storage",
    },
    {
        "name": "OpenRouter",
        "plugin": "openrouter",
        "auth": "OPENROUTER_API_KEY through Engel-owned secret storage",
    },
    {
        "name": "xAI / Grok",
        "plugin": "xai",
        "auth": "xAI OAuth or API key flow owned by the provider layer",
    },
    {
        "name": "MiniMax",
        "plugin": "minimax",
        "auth": "MiniMax OAuth flow owned by the provider layer",
    },
    {
        "name": "Local or custom endpoint",
        "plugin": "custom, ollama-cloud, ai-gateway",
        "auth": "local endpoint or custom provider configuration",
    },
)


def _is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def _dependency_status() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for module_name, package_name in REQUIRED_IMPORTS:
        rows.append(
            {
                "module": module_name,
                "package": package_name,
                "available": importlib.util.find_spec(module_name) is not None,
            }
        )
    return rows


def _provider_plugins() -> list[str]:
    if not _is_dir(MODEL_PROVIDER_PLUGIN_ROOT):
        return []
    plugins: list[str] = []
    try:
        children = sorted(MODEL_PROVIDER_PLUGIN_ROOT.iterdir(), key=lambda item: item.name.lower())
    except OSError:
        return []
    for child in children:
        if child.is_dir() and (child / "plugin.yaml").is_file():
            plugins.append(child.name)
    return plugins


def _file_presence_rows() -> list[dict[str, object]]:
    return [
        {"label": "Engel home", "path": str(ENGEL_HOME), "present": _is_dir(ENGEL_HOME), "kind": "directory"},
        {"label": "config.yaml", "path": str(CONFIG_FILE), "present": _is_file(CONFIG_FILE), "kind": "configuration"},
        {"label": ".env", "path": str(ENV_FILE), "present": _is_file(ENV_FILE), "kind": "secret file, contents not read"},
        {"label": "auth.json", "path": str(AUTH_FILE), "present": _is_file(AUTH_FILE), "kind": "credential pool, contents not read"},
        {"label": "auth folder", "path": str(AUTH_FOLDER), "present": _is_dir(AUTH_FOLDER), "kind": "provider OAuth folder, contents not read"},
    ]


def build_account_connector_inventory() -> dict[str, object]:
    dependencies = _dependency_status()
    missing = [str(row["package"]) for row in dependencies if not bool(row.get("available"))]
    provider_plugins = _provider_plugins()
    return {
        "inside_engel_ai": True,
        "route_spine": [
            "engel_ai.py ask",
            "engel_communication_router.py",
            "engel_ai_update_routes.py",
            "engel_account_connector.py",
            "engel_route_explorer.py",
            "Super Swarm Routes tab",
        ],
        "engel_agent_root": str(ENGEL_AGENT_ROOT),
        "engel_agent_root_present": _is_dir(ENGEL_AGENT_ROOT),
        "provider_plugin_root": str(MODEL_PROVIDER_PLUGIN_ROOT),
        "provider_plugin_root_present": _is_dir(MODEL_PROVIDER_PLUGIN_ROOT),
        "provider_plugins": provider_plugins,
        "provider_plugin_count": len(provider_plugins),
        "engel_home": str(ENGEL_HOME),
        "engel_home_source": ENGEL_HOME_SOURCE,
        "engel_home_on_os_drive": _path_on_os_drive(ENGEL_HOME),
        "engel_home_env_rejected_on_os_drive": ENGEL_HOME_ENV_REJECTED_ON_OS_DRIVE,
        "secret_file_rows": _file_presence_rows(),
        "dependency_rows": dependencies,
        "missing_dependency_packages": missing,
        "runtime_dependency_gate": "ready" if not missing else "blocked",
        "account_memory_json": str(ACCOUNT_MEMORY_JSON),
        "account_memory_json_present": _is_file(ACCOUNT_MEMORY_JSON),
        "account_memory_markdown": str(ACCOUNT_MEMORY_MD),
        "account_memory_markdown_present": _is_file(ACCOUNT_MEMORY_MD),
        "fast_external_memory": str(FAST_EXTERNAL_MEMORY),
        "fast_external_memory_present": _is_dir(FAST_EXTERNAL_MEMORY),
        "slow_external_memory": str(SLOW_EXTERNAL_MEMORY),
        "slow_external_memory_present": _is_dir(SLOW_EXTERNAL_MEMORY),
        "fast_external_record": str(FAST_EXTERNAL_RECORD),
        "fast_external_record_present": _is_file(FAST_EXTERNAL_RECORD),
        "slow_external_record": str(SLOW_EXTERNAL_RECORD),
        "slow_external_record_present": _is_file(SLOW_EXTERNAL_RECORD),
    }


def _format_bool(value: object) -> str:
    return "yes" if bool(value) else "no"


def _format_dependency_rows(rows: list[dict[str, object]]) -> list[str]:
    lines: list[str] = []
    for row in rows:
        lines.append(
            "- "
            + str(row["package"])
            + " / module "
            + str(row["module"])
            + ": "
            + ("available" if bool(row.get("available")) else "missing")
        )
    return lines


def _format_secret_rows(rows: list[dict[str, object]]) -> list[str]:
    lines: list[str] = []
    for row in rows:
        lines.append(
            "- "
            + str(row["label"])
            + ": "
            + ("present" if bool(row.get("present")) else "missing")
            + " ("
            + str(row["kind"])
            + ") at "
            + str(row["path"])
        )
    return lines


def _format_provider_plugins(plugins: list[str], limit: int = 24) -> list[str]:
    if not plugins:
        return ["- none found"]
    shown = plugins[:limit]
    lines = ["- " + plugin for plugin in shown]
    if len(plugins) > len(shown):
        lines.append("- ... +" + str(len(plugins) - len(shown)) + " more")
    return lines


def render_account_connector_status(_payload: str = "") -> str:
    inv = build_account_connector_inventory()
    missing = list(inv["missing_dependency_packages"])
    lines = [
        "# Engel Account Connector",
        "",
        "Yes: account connection belongs inside Engel, not outside as a separate ritual.",
        "This route is the Engel-owned account connection surface for provider login readiness, provider choices, and secret-safety guidance.",
        "",
        "One Engel route spine:",
        *["- " + item for item in inv["route_spine"]],
        "",
        "Current status:",
        "- Engel Agent root present: " + _format_bool(inv["engel_agent_root_present"]),
        "- Provider plugin root present: " + _format_bool(inv["provider_plugin_root_present"]),
        "- Provider plugins found: " + str(inv["provider_plugin_count"]),
        "- Runtime dependency gate: " + str(inv["runtime_dependency_gate"]).upper(),
        "- Engel home: " + str(inv["engel_home"]),
        "- Engel home source: " + str(inv["engel_home_source"]),
        "- Engel home on OS drive: " + _format_bool(inv["engel_home_on_os_drive"]),
        "- C-side ENGEL_HOME rejected: " + _format_bool(inv["engel_home_env_rejected_on_os_drive"]),
        "- Super Swarm visibility: Routes tab through engel_route_explorer.py",
        "- Actual login attempted by this route: no",
        "- Secret values read or printed: no",
        "",
        "Dependency check:",
        *_format_dependency_rows(list(inv["dependency_rows"])),
    ]
    if missing:
        lines.extend(
            [
                "",
                "Current gate:",
                "- Account login cannot be honestly started yet because required Engel Agent dependencies are missing: "
                + ", ".join(missing),
                "- The next step should be an explicit Engel dependency/setup action route, then account login can run through Engel-owned provider flows.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Current gate:",
                "- Engel Agent account dependencies appear ready for the provider layer.",
                "- Login should still be started only by an explicit user action route or Engel-owned local UI flow.",
            ]
        )
    lines.extend(
        [
            "",
            "Try inside Engel:",
            "- connect my account",
            "- show account providers",
            "- account setup in engel",
            "- account connection safety",
        ]
    )
    return "\n".join(lines)


def render_account_connector_providers(_payload: str = "") -> str:
    inv = build_account_connector_inventory()
    plugins = list(inv["provider_plugins"])
    lines = [
        "# Engel Account Providers",
        "",
        "Provider accounts should connect through Engel's provider layer and route registry.",
        "Do not paste API keys or OAuth tokens into chat.",
        "",
        "Common choices:",
    ]
    for provider in ACCOUNT_PROVIDER_MENU:
        plugin = str(provider["plugin"])
        plugin_names = [part.strip() for part in plugin.split(",")]
        present = any(name in plugins for name in plugin_names)
        lines.extend(
            [
                "",
                "- " + str(provider["name"]),
                "  plugin: " + plugin,
                "  local plugin present: " + ("yes" if present else "not detected"),
                "  account flow: " + str(provider["auth"]),
            ]
        )
    lines.extend(
        [
            "",
            "All detected model provider plugins:",
            *_format_provider_plugins(plugins),
        ]
    )
    return "\n".join(lines)


def render_account_connector_setup(_payload: str = "") -> str:
    inv = build_account_connector_inventory()
    missing = list(inv["missing_dependency_packages"])
    lines = [
        "# Engel Account Setup",
        "",
        "Account setup should be driven from Engel.",
        "The friendly path is: open Engel or Super Swarm, search Routes for Account, then run the account route for the provider you want.",
        "",
        "Where Engel stores account material:",
        *_format_secret_rows(list(inv["secret_file_rows"])),
        "",
        "Important:",
        "- These status routes never read or print secret values.",
        "- OAuth/device login should happen in the provider-owned local flow.",
        "- API keys should be entered only into Engel-owned secret storage or a protected local prompt, not into chat.",
        "- Account selection belongs to Engel's provider layer, inherited from the vendored Engel Agent internals.",
    ]
    if missing:
        lines.extend(
            [
                "",
                "Before account login:",
                "- Dependency gate is BLOCKED by missing packages: " + ", ".join(missing),
                "- No login was attempted.",
                "- No package install was attempted by this status route.",
                "- The clean next Engel step is an explicit dependency/setup route, then provider login through Engel.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Ready path:",
                "- Choose a provider in Engel.",
                "- Use the provider layer to start OAuth/device login or a protected API-key prompt.",
                "- Engel records account presence without exposing the secret.",
            ]
        )
    return "\n".join(lines)


def render_account_connector_safety(_payload: str = "") -> str:
    lines = [
        "# Engel Account Connector Safety",
        "",
        "Account connection is part of Engel AI.",
        "",
        "Safety rules:",
        "- No API keys or OAuth tokens in chat.",
        "- No secret values printed by account status routes.",
        "- No provider/model/network call from status routes.",
        "- No hidden startup login.",
        "- No silent credential creation.",
        "- No second route system.",
        "- No route mutation at runtime.",
        "- No trusted-memory promotion from account status.",
        "- Action routes must be explicit and visible in Super Swarm.",
        "",
        "Memory placement:",
        "- Project authority remains D:\\b.WorkSpace\\Engel App\\memory.",
        "- CT246 /opt/engel is the active SSD runtime, memory, and model root.",
        "- Dell PowerEdge /mnt/engel-hdd-vault is the HDD archive root when mounted.",
        "- Retired E/F/G external-drive mirrors and CT245 offline-vault paths are not active routes.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else os.sys.argv[1:])
    command = args[0] if args else "status"
    if command in {"status", "connect"}:
        print(render_account_connector_status())
    elif command in {"providers", "provider"}:
        print(render_account_connector_providers())
    elif command in {"setup", "help"}:
        print(render_account_connector_setup())
    elif command in {"safety", "safe"}:
        print(render_account_connector_safety())
    else:
        print("Unknown Engel account connector command: " + command)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
