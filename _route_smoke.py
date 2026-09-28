"""Smoke-exercise every registered Engel AI update route.

For each entry in UPDATE_ROUTES, pick the first alias and run it through
classify_user_input + route_companion_text_or_command. Verifies:
  - intent.handled is True
  - intent.route_target matches the route's declared route_id
  - response.response is non-empty

Routes that spawn long-running subprocesses (cargo build, npm install,
flutter build, etc.) are skipped automatically — they are tested separately.
Pass --all to include them anyway.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve()
sys.path.insert(0, str(THIS.parent))

from engel_ai_update_routes import UPDATE_ROUTES  # noqa: E402
from engel_communication_router import route_companion_text_or_command  # noqa: E402

# Routes that spawn real long-running processes (cargo, npm, flutter, etc.)
# Skip in the default smoke run to keep it under ~2 minutes.
_SLOW_SUFFIXES = (
    ".build", ".tauri_build", ".install", ".dev_start", ".app_dev_start",
    ".cli_receive_start", ".install_to_project",
)

_SLOW_IDS = frozenset(
    route_id
    for route_id in (
        "engel.engel_agent.gateway_start",
        "engel.gateway.start",
        "engel.jarvis.start",
        "engel.chat_ui.start",
        "engel.lfm2_vision.start",
        "engel.octogent.start",
        "engel.invoke",
        "engel.native_agent.launch_dashboard",
        "engel.native_agent.launch_agent",
        "engel.llama_cli.run",
        "engel.llama_cli.benchmark",
        "engel.llama_cli.run_slug",
        "engel.llama_cli.gpu_benchmark",
        "engel.llama_cli.compare",
        "engel.evolution_lab.darwin_learning_log",
        "engel.evolution_lab.darwin_local_parrot_run",
        # These five each run the LOCAL MODEL end-to-end (~160-170s apiece,
        # measured 2026-08-01) and had quietly grown the "2 minute" smoke to
        # ~18 minutes. They are report routes over the chat lane -- slow-lane
        # by nature, tested separately like the other entries here.
        "engel.local_open_chat.bridge_report",
        "engel.bounded_local_chat_smoke.report",
        "engel.local_chat_prompt_draft.report",
        "engel.first_local_response_smoke.report",
        "engel.local_chat_session_draft.report",
    )
)


def _is_slow(route_id: str) -> bool:
    if route_id in _SLOW_IDS:
        return True
    return any(route_id.endswith(s) for s in _SLOW_SUFFIXES)


def main() -> int:
    run_all = "--all" in sys.argv
    failures: list[str] = []
    skipped: list[str] = []
    timings: list[tuple[str, float]] = []
    total_start = time.monotonic()

    for route in UPDATE_ROUTES:
        if not route.aliases:
            print(f"SKIP {route.route_id} (no aliases)")
            skipped.append(route.route_id)
            continue
        if not run_all and _is_slow(route.route_id):
            print(f"SKIP {route.route_id} (slow — run with --all to include)")
            skipped.append(route.route_id)
            continue
        phrase = route.aliases[0]
        t0 = time.monotonic()
        try:
            result = route_companion_text_or_command(phrase, context="ROUTE_SMOKE")
        except Exception as exc:
            failures.append(f"{route.route_id} :: {phrase!r} raised {type(exc).__name__}: {exc}")
            timings.append((route.route_id, time.monotonic() - t0))
            print(f"RAISE  {route.route_id} ({time.monotonic() - t0:.2f}s) :: {exc}")
            continue
        dt = time.monotonic() - t0
        timings.append((route.route_id, dt))
        ok_route = result.route_target == route.route_id
        ok_handled = bool(result.handled)
        ok_response = bool(str(result.response).strip())
        verdict = "PASS" if (ok_route and ok_handled and ok_response) else "FAIL"
        print(f"{verdict}   {route.route_id:<48} ({dt:5.2f}s)  alias={phrase!r}")
        if verdict == "FAIL":
            failures.append(
                f"{route.route_id} :: handled={ok_handled} "
                f"target_match={ok_route} response_present={ok_response}"
            )

    total = time.monotonic() - total_start
    print()
    print(f"Total routes registered: {len(UPDATE_ROUTES)}")
    print(f"Routes tested          : {len(timings)}")
    print(f"Routes skipped         : {len(skipped)}")
    print(f"Total time             : {total:.2f}s")
    if timings:
        print(f"Slowest five           :")
        for name, dt in sorted(timings, key=lambda x: -x[1])[:5]:
            print(f"  {dt:6.2f}s  {name}")
    print()
    if failures:
        print(f"Failures ({len(failures)}):")
        for line in failures:
            print(f"  - {line}")
        return 1
    print("ALL TESTED ROUTES PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
