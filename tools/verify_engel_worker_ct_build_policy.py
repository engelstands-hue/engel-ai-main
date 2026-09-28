#!/usr/bin/env python3
"""Prove ROG build requests reach CT246 before any local build helper."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT, ROOT / "tools"):
    value = str(item)
    if value not in sys.path:
        sys.path.insert(0, value)

import engel_main_local_model_worker as worker  # noqa: E402
import engel_command_planner  # noqa: E402
import engel_build_lane  # noqa: E402


def main() -> int:
    server_calls: list[str] = []
    planner_calls: list[str] = []

    def forbidden(*_args, **_kwargs):
        raise AssertionError("ROG-local build helper was called before CT246")

    def fake_server(prompt, *_args, **_kwargs):
        server_calls.append(prompt)
        return {
            "ok": True,
            "status": "app build action",
            "assistant_reply": "built on CT246",
            "assistant_output_text": "built on CT246",
            "selected_provider": "ct_build_lane",
            "runtime_provider": "engel-build-lane-bridge",
            "action": {
                "kind": "app_build",
                "result": {
                    "ok": True,
                    "path": "/opt/engel/workspaces/test",
                    "files": ["main.py"],
                },
                "run": {"ran": True, "exit_code": 0, "output": "ok"},
            },
        }

    originals = {
        "fleet": worker._run_fleet_dispatch,
        "app": worker._run_app_build,
        "workspace": worker._run_workspace_setup,
        "info": worker._is_info_question,
        "stream": worker._stream_server_chat,
        "server": worker._main_server_fast_chat,
        "planner": engel_command_planner.plan_actions,
    }
    try:
        worker._run_fleet_dispatch = lambda *_args, **_kwargs: None
        worker._run_app_build = forbidden
        worker._run_workspace_setup = forbidden
        worker._is_info_question = lambda *_args, **_kwargs: False
        worker._stream_server_chat = forbidden
        worker._main_server_fast_chat = fake_server
        engel_command_planner.plan_actions = (
            lambda prompt: planner_calls.append(prompt) or None
        )
        operator_prompt = (
            "Build me a self-contained web page called drawing_review_board "
            "with working controls, overwrite."
        )
        wrapped_prompt = (
            "Engel code capability context: package install and language tools.\n\n"
            f"Operator request follows:\n{operator_prompt}"
        )
        result = worker._handle(
            {
                "id": "ct-build-policy-test",
                "command": "chat",
                "prompt": wrapped_prompt,
                "timeout": 30,
                "max_tokens": 120,
                "stream": True,
            }
        )
    finally:
        worker._run_fleet_dispatch = originals["fleet"]
        worker._run_app_build = originals["app"]
        worker._run_workspace_setup = originals["workspace"]
        worker._is_info_question = originals["info"]
        worker._stream_server_chat = originals["stream"]
        worker._main_server_fast_chat = originals["server"]
        engel_command_planner.plan_actions = originals["planner"]

    assert planner_calls == []
    assert server_calls == [wrapped_prompt]
    assert result.get("ok") is True
    assert (result.get("receipt") or {}).get("selected_provider") == "ct_build_lane"
    assert worker._project_is_interactive(
        {"script.sh": "while IFS= read -r file; do echo \"$file\"; done < <(find . -type f)"},
        "bash",
    ) is False
    assert worker._project_is_interactive(
        {"main.py": "value = input('Enter value: ')"},
        "python",
    ) is True
    assert worker._requested_workspace_setup(
        "Summarize which projects were actually created in this session and what remains unproven."
    ) is None
    large_operator_prompt = (
        "Build me a large multi-file Python command-line app called Drafting Job Manager "
        "with clients, projects, JSON persistence, report export, and automated tests, overwrite."
    )
    large_wrapped_prompt = (
        "Engel code capability context: preferred language Python; workspace/project tools available.\n\n"
        f"Operator request follows:\n{large_operator_prompt}"
    )
    assert engel_build_lane.is_build_request(large_wrapped_prompt) is not None
    assert worker._requested_workspace_setup(
        worker._operator_request_text(large_wrapped_prompt)
    ) is None
    assert worker._requested_app_build(
        "Build me a Python app. Use and repair the existing workspace at "
        "/opt/engel/workspaces/example."
    ) is not None
    print(
        "PASS: ROG build request routes to CT246 before planner; "
        "local build helpers were not called"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
