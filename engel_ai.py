from __future__ import annotations

import argparse
import sys
from typing import Iterable

from engel_ai_update_routes import (
    ARCHIVE_SHELF_ROUTE_ID,
    ENGEL_ACCOUNT_CONNECTOR_STATUS_ROUTE_ID,
    ENGEL_AI_CONNECTORS_STATUS_ROUTE_ID,
    ENGEL_AGENT_STATUS_ROUTE_ID,
    ENGEL_LAN_STATUS_ROUTE_ID,
    ENGEL_MAIN_STATUS_ROUTE_ID,
    ENGEL_ROUTE_EXPLORER_ROUTE_ID,
    ENGEL_SANDBOX_STATUS_ROUTE_ID,
    ENGEL_WSL_STATUS_ROUTE_ID,
    ENGEL3D_STATUS_ROUTE_ID,
    ENGELCODE_STATUS_ROUTE_ID,
    MEMORY_CANDIDATE_ROUTE_ID,
    MINOR_TOOLS_LIST_ROUTE_ID,
    PROGRESS_ROUTE_ID,
    UPDATE_ROUTES,
    route_metadata,
)
from engel_communication_router import route_companion_text_or_command


SELF_TEST_PHRASES: tuple[tuple[str, str], ...] = (
    # Original baseline routes (host)
    ("what is engel status", PROGRESS_ROUTE_ID),
    ("check memory candidates", MEMORY_CANDIDATE_ROUTE_ID),
    ("archive shelf status", ARCHIVE_SHELF_ROUTE_ID),
    ("is I drive required", ARCHIVE_SHELF_ROUTE_ID),
    # Vendored subtrees — pick the cheapest status route from each
    ("engel agent status", ENGEL_AGENT_STATUS_ROUTE_ID),
    ("engel3d status", ENGEL3D_STATUS_ROUTE_ID),
    ("engel sandbox status", ENGEL_SANDBOX_STATUS_ROUTE_ID),
    ("engelcode status", ENGELCODE_STATUS_ROUTE_ID),
    ("engel main status", ENGEL_MAIN_STATUS_ROUTE_ID),
    ("engel lan status", ENGEL_LAN_STATUS_ROUTE_ID),
    ("engel minor tools list", MINOR_TOOLS_LIST_ROUTE_ID),
    ("check wsl status", ENGEL_WSL_STATUS_ROUTE_ID),
    ("show ai connectors", ENGEL_AI_CONNECTORS_STATUS_ROUTE_ID),
    ("connect my account", ENGEL_ACCOUNT_CONNECTOR_STATUS_ROUTE_ID),
    ("route explorer", ENGEL_ROUTE_EXPLORER_ROUTE_ID),
)


def ask_engel_ai(text: str) -> str:
    result = route_companion_text_or_command(text, context="ENGEL_AI_RUN_ENTRY_V1")
    if result.response:
        return result.response
    return "Engel AI did not produce a local response for: " + str(text or "").strip()


def render_routes() -> str:
    lines = [
        "Engel AI Run Entry V1",
        "",
        "Safe route groups:",
    ]
    for route in UPDATE_ROUTES:
        meta = route_metadata(route.route_id)
        aliases = [str(alias) for alias in meta.get("aliases", [])]
        read_only = bool(meta.get("read_only"))
        status_only = bool(meta.get("status_only"))
        mode = "local / read-only / status-only" if read_only and status_only else "local / explicit user action route"
        if not bool(meta.get("no_provider_model_network")):
            mode += " / may use provider-model-network inside target"
        if not bool(meta.get("no_background_worker")):
            mode += " / may start background work inside target"
        if not bool(meta.get("no_archive_mutation")):
            mode += " / may mutate target runtime/archive state"
        lines.extend(
            [
                "",
                "- " + str(meta.get("label", route.route_id)),
                "  route_id: " + route.route_id,
                "  target: " + str(meta.get("target_module")) + "." + str(meta.get("target_function")),
                "  mode: " + mode,
                "  examples:",
            ]
        )
        for alias in aliases[:8]:
            lines.append("    - " + alias)
    lines.extend(
        [
            "",
            "Existing safe router surfaces:",
            "- colony hive status",
            "- offline seed llm status",
            "- engel agent status (read-only inventory of bundled engel-agent)",
            "- engel agent run <task> (autonomous invocation of bundled engel-agent)",
            "- engel agent doctor / version / top status (bundled CLI introspection)",
            "- engel agent gateway status / start / stop (messaging + cron service)",
            "- engel agent cron list / cron status (scheduled jobs)",
            "- engel agent memory status / skills list / sessions list / sessions stats / plugins list",
            "- engel3d status / start / stop / build (3D office Next.js runtime, vendored Claw3D fork)",
            "- engel sandbox status / nodes / list / create / delete / bring up (Linux/KVM hypervisor, vendored CubeSandbox fork)",
            "- wsl status / distros / tools / paths / self-test (bounded WSL Ubuntu readiness bridge)",
            "- engelcode status / version / crates / build / invoke / bring up (Rust TUI coding agent, vendored jcode fork)",
            "- engel main status / version / binaries / install / build / dev start|stop / tauri build / bring up (Tauri desktop companion, vendored OpenHuman fork)",
            "- engel lan status / version / cli help / cli receive start|stop / app dev start|stop / bring up (LAN file-sharing, vendored LocalSend fork)",
            "- engel minor tools list + engel humanizer / native agent / ide / evolution lab / knowledge graph / evolution engine status (batch of 6 smaller vendored tools)",
            "- show ai connectors / ai connector blueprint / show hermes ai adapters (Engel AI Connector Hub for bringing other AIs into the same route spine)",
            "- connect my account / show account providers / account setup in engel (Engel Account Connector, inside the same route spine)",
            "- route explorer / show command menu / super swarm routes (easy route catalog from the same registry)",
            "",
            "Safety (post-2026-05-19 ruling):",
            "- AUTONOMY_ALLOWED (engel-agent subprocess may drive tool loops)",
            "- BACKGROUND_WORK_ALLOWED (engel-agent subprocess may run in background)",
            "- PROVIDER_NETWORK_ALLOWED (engel-agent may call model providers)",
            "- EXPLICIT_USER_ACTION_ONLY for action routes; no hidden startup loop",
            "- HOST_ROUTER_STATE: NO_MUTATION (Engel AI's deterministic router is unchanged)",
            "- HOST_PACKAGE_ISOLATION: bundled engel package shadows nothing in-host",
            "- NO_MEMORY_PROMOTION on the host Engel AI side",
            "- NO_TRUSTED_MEMORY_WRITE on the host Engel AI side",
        ]
    )
    return "\n".join(lines)


def run_self_test() -> tuple[bool, str]:
    lines = [
        "Engel AI Run Entry V1 Self-Test",
        "",
        "Mode: local route smoke only",
    ]
    ok = True
    for phrase, expected_route in SELF_TEST_PHRASES:
        result = route_companion_text_or_command(phrase, context="ENGEL_AI_RUN_ENTRY_V1_SELF_TEST")
        route_ok = result.handled and result.route_target == expected_route and not result.should_execute_command
        response_ok = bool(result.response.strip())
        passed = bool(route_ok and response_ok)
        ok = ok and passed
        lines.append("")
        lines.append("Phrase: " + phrase)
        lines.append("Expected route: " + expected_route)
        lines.append("Observed route: " + str(result.route_target or ""))
        lines.append("Handled: " + str(bool(result.handled)))
        lines.append("Executable command: " + str(bool(result.should_execute_command)))
        lines.append("Response present: " + str(response_ok))
        lines.append("Result: " + ("PASS" if passed else "FAIL"))
    lines.extend(
        [
            "",
            "Safety:",
            "- route smoke only",
            "- no provider/model route invoked by this self-test",
            "- no hidden background worker",
            "- no memory promotion or trusted-memory write",
            "- no fix apply",
            "- no archive mutation",
        ]
    )
    return ok, "\n".join(lines)


def chat_loop() -> int:
    print("Engel AI Run Entry V1")
    print("Local safe chat. Type exit or quit to leave.")
    while True:
        try:
            text = input("Engel> ").strip()
        except EOFError:
            print()
            return 0
        if not text:
            continue
        if text.casefold() in {"exit", "quit"}:
            return 0
        print(ask_engel_ai(text))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safe local Engel AI entrypoint for read-only router/status testing."
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("chat", help="start an explicit local REPL")

    ask_parser = subparsers.add_parser("ask", help="ask one local Engel AI route/question")
    ask_parser.add_argument("text", nargs="+", help="message to route")

    subparsers.add_parser("routes", help="list safe local route groups")
    subparsers.add_parser("self-test", help="run route smoke tests")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    command = args.command or "chat"

    if command == "chat":
        return chat_loop()
    if command == "ask":
        print(ask_engel_ai(" ".join(args.text)))
        return 0
    if command == "routes":
        print(render_routes())
        return 0
    if command == "self-test":
        ok, rendered = run_self_test()
        print(rendered)
        return 0 if ok else 1
    print("Unknown Engel AI command: " + str(command))
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
