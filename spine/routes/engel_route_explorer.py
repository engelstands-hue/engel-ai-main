"""User-facing Engel AI route explorer.

This module is a presentation layer over ``engel_ai_update_routes.UPDATE_ROUTES``.
It does not define a second router and it does not execute routes on import.
The GUI and CLI use it to show the same routes Engel AI can already resolve.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable


def _group_for_route(route_id: str) -> str:
    route_id = str(route_id or "")
    if route_id.startswith("engel.script"):
        return "EngelScript"
    if route_id.startswith("engel.capability"):
        return "Engel Capability Index"
    if route_id.startswith("engel.progress_dashboard") or route_id.startswith("engel.memory_candidate") or route_id.startswith("engel.archive_shelf"):
        return "Core Status"
    if route_id.startswith("engel.engel_agent"):
        return "Engel Agent"
    if route_id.startswith("engel.engel3d"):
        return "Engel 3D Office"
    if route_id.startswith("engel.engel_sandbox"):
        return "Engel Sandbox"
    if route_id.startswith("engel.wsl_ubuntu"):
        return "WSL Ubuntu Runtime"
    if route_id.startswith("engel.wsl"):
        return "WSL Bridge"
    if route_id.startswith("engel.engelcode"):
        return "EngelCode"
    if route_id.startswith("engel.engel_main"):
        return "Engel Main"
    if route_id.startswith("engel.engel_lan"):
        return "Engel LAN"
    if route_id.startswith("engel.engel_humanizer"):
        return "Engel Humanizer"
    if route_id.startswith("engel.native_agent"):
        return "Engel Native Agent"
    if route_id.startswith("engel.ide"):
        return "Engel IDE"
    if route_id.startswith("engel.evolution_lab"):
        return "Engel Evolution Lab"
    if route_id.startswith("engel.knowledge_graph_v2"):
        return "Knowledge Graph V2"
    if route_id.startswith("engel.knowledge_graph"):
        return "Engel Knowledge Graph"
    if route_id.startswith("engel.evolution_engine"):
        return "Engel Evolution Engine"
    if route_id.startswith("engel.ai_connectors"):
        return "AI Connectors"
    if route_id.startswith("engel.accounts"):
        return "Accounts"
    if route_id.startswith("engel.capabilities") or route_id.startswith("engel.minor_tools"):
        return "Capabilities"
    if route_id.startswith("engel.routes"):
        return "Route Explorer"
    if route_id.startswith("engel.verify"):
        return "Workspace Verify"
    if route_id.startswith("engel.vault_migration"):
        return "Vault Migration"
    if route_id.startswith("engel.main_server_merge"):
        return "Engel Main Server Merge"
    if route_id.startswith("engel.external_memory"):
        return "External Memory"
    if route_id.startswith("engel.llama_cli"):
        return "llama-cli Runtime"
    # Wave 2 vendored modules
    if route_id.startswith("engel.new_tools"):
        return "Wave 2 Modules"
    if route_id.startswith("engel.cli_anything"):
        return "CLI Anything"
    if route_id.startswith("engel.git_nexus"):
        return "GitNexus"
    if route_id.startswith("engel.octogent"):
        return "Octogent Swarm"
    if route_id.startswith("engel.open_agents"):
        return "Open Agents"
    if route_id.startswith("engel.airllm"):
        return "AirLLM"
    if route_id.startswith("engel.jarvis"):
        return "OpenJarvis"
    if route_id.startswith("engel.chat_ui"):
        return "Agent Chat UI"
    if route_id.startswith("engel.ai_gallery"):
        return "AI Gallery"
    if route_id.startswith("engel.cluster"):
        return "Cluster"
    if route_id.startswith("engel.meeting_room"):
        return "Agent Meeting Room"
    # Wave 3 modules
    if route_id.startswith("engel.wave3"):
        return "Wave 3 Modules"
    if route_id.startswith("engel.gstack"):
        return "GStack Agent Framework"
    if route_id.startswith("engel.lfm2_code_review"):
        return "LFM2 Code Review"
    if route_id.startswith("engel.lfm2_mobile"):
        return "LFM2.5 Mobile"
    if route_id.startswith("engel.lfm2_vision"):
        return "LFM2 Vision"
    if route_id.startswith("engel.lfm2"):
        return "LFM2 SDK"
    # Wave 4 modules
    if route_id.startswith("engel.wave4"):
        return "Wave 4 Modules"
    if route_id.startswith("engel.claw3d"):
        return "Claw3D 3D Agent Office"
    if route_id.startswith("engel.cubesandbox"):
        return "CubeSandbox Agent Sandbox"
    if route_id.startswith("engel.darwinian_evolver"):
        return "Darwinian Evolver"
    if route_id.startswith("engel.hermes_agent"):
        return "Hermes Agent"
    if route_id.startswith("engel.localsend"):
        return "LocalSend"
    # Architect Agent (Zones 1-5)
    if route_id.startswith("engel.architect"):
        return "Architect Agent"
    if route_id.startswith("engel.grok_bot"):
        return "Grok Bot"
    if route_id.startswith("engel.routines"):
        return "Routines"
    if route_id.startswith("engel.compaction"):
        return "Context Compaction"
    if route_id.startswith("engel.mcp_allowlist"):
        return "MCP Allowlist"
    if route_id.startswith("engel.icm"):
        return "ICM Architect"
    if route_id.startswith("engel.graph_studio"):
        return "Graph & Loop Studio"
    if route_id.startswith("engel.grover"):
        return "Grover Algorithm"
    if route_id.startswith("engel.next_stage"):
        return "Next Stage Merge"
    if route_id.startswith("engel.wiki_one"):
        return "Wiki One"
    # Local models & inference
    if route_id.startswith("engel.models"):
        return "Local Models"
    if route_id.startswith("engel.model_intake") or route_id.startswith("engel.model_review_approval"):
        return "Model Intake & Approval"
    if route_id.startswith("engel.llama_cpp") or route_id.startswith("engel.llama_swap_approval"):
        return "Local Models"
    if route_id.startswith("engel.offline_model") or route_id.startswith("engel.offline_seed_llm") or route_id.startswith("engel.no_generation_load_check"):
        return "Local Models"
    # Research, learning, colony
    if route_id.startswith("engel.research") or route_id.startswith("engel.learning"):
        return "Research & Learning"
    if route_id.startswith("engel.self_learning") or route_id.startswith("engel.candidate_learning") or route_id.startswith("engel.candidate_review") or route_id.startswith("engel.candidate_set_approval"):
        return "Self-Learning & Candidates"
    if route_id.startswith("engel.hive_mind") or route_id.startswith("engel.worker_ants"):
        return "Hive Mind"
    if route_id.startswith("engel.colony") or route_id.startswith("engel.swarm_trails"):
        return "Colony & Swarm"
    if route_id.startswith("engel.communication_queen"):
        return "Hive Mind"
    # Overnight loop
    if route_id.startswith("engel.overnight"):
        return "Overnight Runner"
    # Code Companion & Patch Apply pipeline
    if route_id.startswith("engel.cc_") or route_id.startswith("engel.code_companion") or route_id.startswith("engel.patch_receipts") or route_id.startswith("engel.protected_actions"):
        return "Code Companion & Patch"
    if route_id.startswith("engel.fix_candidate_queue") or route_id.startswith("engel.human_review_draft"):
        return "Code Companion & Patch"
    if route_id.startswith("engel.daily_cycle") or route_id.startswith("engel.lowrisk_selffix") or route_id.startswith("engel.self_fix"):
        return "Code Companion & Patch"
    # Runtime Readiness
    if route_id.startswith("engel.runtime_readiness") or route_id.startswith("engel.runtime_path") or route_id.startswith("engel.local_runtime_path"):
        return "Runtime Readiness"
    if route_id.startswith("engel.runtime_candidate") or route_id.startswith("engel.offline_runtime_dry_run"):
        return "Runtime Readiness"
    # Memory & Promotion
    if route_id.startswith("engel.approved_memory") or route_id.startswith("engel.memory_archive") or route_id.startswith("engel.memory_inventory"):
        return "Memory & Promotion"
    if route_id.startswith("engel.memory_roots_storage") or route_id.startswith("engel.trusted_memory_target") or route_id.startswith("engel.training_trusted_memory"):
        return "Memory & Promotion"
    if route_id.startswith("engel.long_term_memory"):
        return "Memory & Promotion"
    # Android Workers & multi-device
    if route_id.startswith("engel.android_workers") or route_id.startswith("engel.multi_android") or route_id.startswith("engel.lan_pairing"):
        return "Android Workers & Pairing"
    # Browser Queen
    if route_id.startswith("engel.browser_queen"):
        return "Browser Queen"
    # Worker Assignment & Remote Worker
    if route_id.startswith("engel.worker_assignment") or route_id.startswith("engel.result_intake") or route_id.startswith("engel.remote_worker_app_scaffold"):
        return "Worker Assignment & Results"
    # Local Chat smoke / drafts / review bridges
    if route_id.startswith("engel.local_chat") or route_id.startswith("engel.local_open_chat"):
        return "Local Chat"
    if route_id.startswith("engel.bounded_local_chat_smoke") or route_id.startswith("engel.first_local_response_smoke") or route_id.startswith("engel.output_filter_tuning") or route_id.startswith("engel.persistent_chat_plan"):
        return "Local Chat"
    if route_id.startswith("engel.chat_export_intake"):
        return "Local Chat"
    # Product workbench / cycle
    if route_id.startswith("engel.product_"):
        return "Product Workbench"
    # System integration & safety guards
    if route_id.startswith("engel.system_integration") or route_id.startswith("engel.password_gate") or route_id.startswith("engel.truthfulness_guard") or route_id.startswith("engel.outside_ai_boundary"):
        return "System Integration & Safety"
    # Intent planning / guided library
    if route_id.startswith("engel.intent_planner") or route_id.startswith("engel.guided_library"):
        return "Intent Planning & Guides"
    if route_id.startswith("engel.speech_spc"):
        return "Speech Packet Compiler"
    # Whole-system audit
    if route_id.startswith("engel.whole_system"):
        return "Whole-System Audit"
    # Dev tools
    if route_id.startswith("engel.talk_to_code"):
        return "Dev Tools"
    if route_id.startswith("engel.growth") or route_id.startswith("engel.ai_growth_dashboard"):
        return "Dev Tools"
    if route_id.startswith("engel.route_explorer"):
        return "Route Explorer"
    # Engel saved-skill registry (skills/ + memory/skills), not hermes-native
    if route_id == "engel.skills.saved_list":
        return "Core Status"
    # Native runtime / gateway / system
    if route_id in (
        "engel.cron.list", "engel.cron.status",
        "engel.gateway.start", "engel.gateway.status", "engel.gateway.stop",
        "engel.memory.status", "engel.native_runtime",
        "engel.sessions.list", "engel.sessions.stats",
        "engel.skills.list", "engel.toolsets", "engel.plugins.list",
        "engel.top.status", "engel.version",
        "engel.doctor", "engel.invoke",
    ):
        return "Native Runtime"
    # Core Status (Engel-wide health/identity)
    if route_id.startswith("engel.identity"):
        return "Core Status"
    if route_id.startswith("engel.ai_body") or route_id.startswith("engel.core_continuity") or route_id.startswith("engel.core_v1"):
        return "Core Status"
    if route_id.startswith("engel.engel_mind") or route_id.startswith("engel.progress") or route_id.startswith("engel.future_upgrades"):
        return "Core Status"
    return "Other Engel Routes"


def _mode_label(meta: dict[str, object]) -> str:
    if bool(meta.get("read_only")) and bool(meta.get("status_only")):
        return "status"
    return "action"


def _safety_label(meta: dict[str, object]) -> str:
    warnings: list[str] = []
    if not bool(meta.get("no_provider_model_network")):
        warnings.append("provider/model/network possible in target")
    if not bool(meta.get("no_background_worker")):
        warnings.append("background work possible in target")
    if not bool(meta.get("no_archive_mutation")):
        warnings.append("target runtime/archive mutation possible")
    if not warnings:
        return "local route; no host router mutation"
    return "local explicit route; " + "; ".join(warnings)


def route_catalog_for_gui() -> list[dict[str, object]]:
    """Return every Engel AI update route as simple GUI-safe dictionaries."""
    from engel_ai_update_routes import UPDATE_ROUTES, route_metadata

    catalog: list[dict[str, object]] = []
    for route in UPDATE_ROUTES:
        meta = route_metadata(route.route_id)
        aliases = [str(alias) for alias in meta.get("aliases", [])]
        primary_alias = aliases[0] if aliases else route.route_id
        catalog.append(
            {
                "route_id": route.route_id,
                "label": str(meta.get("label", route.route_id)),
                "group": _group_for_route(route.route_id),
                "target": str(meta.get("target_module", "")) + "." + str(meta.get("target_function", "")),
                "aliases": aliases,
                "primary_alias": primary_alias,
                "read_only": bool(meta.get("read_only")),
                "status_only": bool(meta.get("status_only")),
                "mode": _mode_label(meta),
                "safety": _safety_label(meta),
            }
        )
    catalog.sort(key=lambda item: (str(item["group"]), str(item["label"]), str(item["route_id"])))
    return catalog


def route_catalog_groups(catalog: Iterable[dict[str, object]] | None = None) -> list[str]:
    entries = list(catalog) if catalog is not None else route_catalog_for_gui()
    return sorted({str(entry.get("group", "Other Engel Routes")) for entry in entries})


def route_catalog_summary(catalog: Iterable[dict[str, object]] | None = None) -> dict[str, object]:
    entries = list(catalog) if catalog is not None else route_catalog_for_gui()
    groups: dict[str, int] = defaultdict(int)
    action_count = 0
    alias_count = 0
    for entry in entries:
        groups[str(entry.get("group", "Other Engel Routes"))] += 1
        alias_count += len(entry.get("aliases", []))
        if str(entry.get("mode", "")) == "action":
            action_count += 1
    return {
        "route_count": len(entries),
        "alias_count": alias_count,
        "action_route_count": action_count,
        "status_route_count": len(entries) - action_count,
        "group_counts": dict(sorted(groups.items())),
    }


def filter_route_catalog(search_text: str = "", group: str = "All") -> list[dict[str, object]]:
    needle = " ".join(str(search_text or "").casefold().split())
    wanted_group = str(group or "All")
    filtered: list[dict[str, object]] = []
    for entry in route_catalog_for_gui():
        if wanted_group != "All" and str(entry.get("group")) != wanted_group:
            continue
        haystack = " ".join(
            [
                str(entry.get("route_id", "")),
                str(entry.get("label", "")),
                str(entry.get("group", "")),
                str(entry.get("target", "")),
                " ".join(str(alias) for alias in entry.get("aliases", [])),
            ]
        ).casefold()
        if needle and needle not in haystack:
            continue
        filtered.append(entry)
    return filtered


def render_route_details(route_id: str) -> str:
    for entry in route_catalog_for_gui():
        if str(entry.get("route_id")) == str(route_id):
            aliases = [str(alias) for alias in entry.get("aliases", [])]
            return "\n".join(
                [
                    "# " + str(entry.get("label", route_id)),
                    "",
                    "Route ID: " + str(entry.get("route_id", "")),
                    "Group: " + str(entry.get("group", "")),
                    "Target: " + str(entry.get("target", "")),
                    "Mode: " + str(entry.get("mode", "")),
                    "Safety: " + str(entry.get("safety", "")),
                    "",
                    "Run phrases:",
                    *["- " + alias for alias in aliases],
                ]
            )
    return "Unknown Engel AI route: " + str(route_id)


def render_route_explorer(_payload: str = "") -> str:
    catalog = route_catalog_for_gui()
    summary = route_catalog_summary(catalog)
    lines = [
        "# Engel Route Explorer",
        "",
        "One route catalog, read from engel_ai_update_routes.UPDATE_ROUTES.",
        "Use any phrase under Run phrases in Engel AI chat, or use the Super Swarm Routes tab to search and run without memorizing commands.",
        "",
        "Totals:",
        "- Routes: " + str(summary["route_count"]),
        "- Aliases: " + str(summary["alias_count"]),
        "- Status routes: " + str(summary["status_route_count"]),
        "- Explicit action routes: " + str(summary["action_route_count"]),
        "",
        "Easy starts:",
        "- route explorer",
        "- engel capabilities",
        "- connect my account",
        "- show account providers",
        "- show ai connectors",
        "- engel status",
        "- check wsl status",
        "- super swarm routes",
        "",
        "Safety:",
        "- This explorer is a menu over the existing Engel AI router.",
        "- It does not create a second route system.",
        "- Status routes are read-only/status-only.",
        "- Action routes remain explicit user-invoked routes.",
        "- The Super Swarm GUI asks for confirmation before running action routes.",
    ]
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for entry in catalog:
        groups[str(entry.get("group", "Other Engel Routes"))].append(entry)
    for group in sorted(groups):
        entries = groups[group]
        lines.extend(["", "## " + group + " (" + str(len(entries)) + ")"])
        for entry in entries:
            aliases = [str(alias) for alias in entry.get("aliases", [])]
            shown_aliases = aliases[:5]
            if len(aliases) > len(shown_aliases):
                shown_aliases.append("... +" + str(len(aliases) - len(shown_aliases)) + " more")
            lines.extend(
                [
                    "",
                    "- " + str(entry.get("label", "")),
                    "  route_id: " + str(entry.get("route_id", "")),
                    "  mode: " + str(entry.get("mode", "")),
                    "  target: " + str(entry.get("target", "")),
                    "  run phrases: " + "; ".join(shown_aliases),
                ]
            )
    return "\n".join(lines)


def render_route_search(payload: str = "") -> str:
    """Search route labels, aliases, and IDs by keyword.

    Payload: keyword(s) to search for. Separate group filter with '|':
      'llm'          → search all groups
      'llm | local'  → search label/aliases for 'llm' in group 'local' (partial match)
    """
    query = str(payload or "").strip()
    group_filter = "All"

    if "|" in query:
        parts = query.split("|", 1)
        query = parts[0].strip()
        group_filter = parts[1].strip()

    if not query and group_filter == "All":
        return (
            "# Engel Route Search\n\n"
            "Provide a keyword to search routes.\n"
            "Usage: engel route search <keyword>\n"
            "       engel route search <keyword> | <group>\n\n"
            "Examples:\n"
            "  engel route search llm\n"
            "  engel route search status | Knowledge Graph V2\n"
        )

    # Resolve partial group name
    if group_filter != "All":
        all_groups = route_catalog_groups()
        matched = [g for g in all_groups if group_filter.casefold() in g.casefold()]
        if len(matched) == 1:
            group_filter = matched[0]
        elif len(matched) > 1:
            group_filter = "All"  # ambiguous — search all groups

    results = filter_route_catalog(search_text=query, group=group_filter)

    if not results:
        msg = f"# Engel Route Search: {query!r}\n\nNo routes matched."
        if group_filter != "All":
            msg += f"\n(Group filter: {group_filter!r})"
        return msg

    lines = [
        f"# Engel Route Search: {query!r}",
        "",
        f"Found {len(results)} route(s)" + (f" in group {group_filter!r}" if group_filter != "All" else ""),
        "",
        f"  {'Label':<45} {'Group':<22} {'Run phrase'}",
        "  " + "-" * 100,
    ]
    for entry in results[:30]:
        label = str(entry.get("label", ""))[:44]
        group = str(entry.get("group", ""))[:21]
        aliases = entry.get("aliases", [])
        phrase = str(aliases[0]) if aliases else str(entry.get("route_id", ""))
        lines.append(f"  {label:<45} {group:<22} {phrase}")

    if len(results) > 30:
        lines.append(f"\n  ... and {len(results) - 30} more. Narrow your search or add a group filter.")

    lines += [
        "",
        "Route details: engel route details <route_id>",
        "Group list:    engel route explorer",
    ]
    return "\n".join(lines)


def main() -> int:
    print(render_route_explorer())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
