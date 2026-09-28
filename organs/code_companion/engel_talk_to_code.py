"""Engel Talk-to-Code — let Engel explain its own source files.

Reads local Python source files and optionally passes a summary snippet
through the offline seed LLM for a plain-language explanation.

Safety: read-only. No file writes, no network, no imports that mutate state.
"""
from __future__ import annotations

import os
from pathlib import Path

_APP_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)

_SOURCE_FILES: dict[str, str] = {
    "engel_ai": "engel_ai.py",
    "engel_ai_update_routes": "engel_ai_update_routes.py",
    "engel_communication_router": "engel_communication_router.py",
    "engel_offline_seed_llm": "engel_offline_seed_llm.py",
    "engel_airllm_bridge": "engel_airllm_bridge.py",
    "engel_overnight_runner": "engel_overnight_runner.py",
    "engel_overnight_status": "engel_overnight_status.py",
    "engel_new_tools_runner": "engel_new_tools_runner.py",
    "engel_desktop_v2": "engel_desktop_v2.py",
    "engel_talk_to_code": "engel_talk_to_code.py",
    "engel_de_bruijn_memory_loader": "engel_de_bruijn_memory_loader.py",
}

_SNIPPET_LINES = 60


def list_talkable_modules() -> str:
    lines = [
        "# Engel Talk-to-Code — Available Modules",
        "",
        "Say 'explain <module_name>' to get a plain-language summary.",
        "Example: 'explain engel_ai_update_routes'",
        "",
        "Module                         File",
        "-" * 60,
    ]
    for slug, filename in sorted(_SOURCE_FILES.items()):
        present = "YES" if (_APP_ROOT / filename).exists() else "missing"
        lines.append(f"  {slug:<35} [{present}]  {filename}")
    lines += [
        "",
        "Use route: engel.talk_to_code.list",
        "Or:        engel.talk_to_code.explain  <module_slug>",
    ]
    return "\n".join(lines)


def _read_snippet(filename: str) -> str:
    path = _APP_ROOT / filename
    if not path.exists():
        return f"[file not found: {path}]"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        total = len(lines)
        snippet = "\n".join(lines[:_SNIPPET_LINES])
        if total > _SNIPPET_LINES:
            snippet += f"\n\n... [{total - _SNIPPET_LINES} more lines not shown]"
        return snippet
    except Exception as exc:
        return f"[read error: {exc}]"


def explain_module(module_slug: str = "") -> str:
    slug = str(module_slug or "").strip().lower().replace(".py", "").replace("-", "_")

    if not slug:
        return list_talkable_modules()

    filename = _SOURCE_FILES.get(slug)
    if filename is None:
        close = [k for k in _SOURCE_FILES if slug in k or k in slug]
        hint = ("Did you mean: " + ", ".join(close)) if close else "Use 'engel.talk_to_code.list' to see available modules."
        return "\n".join([
            f"Talk-to-Code: module '{slug}' not found.",
            hint,
        ])

    snippet = _read_snippet(filename)
    header = "\n".join([
        f"# Engel Talk-to-Code — {slug}",
        f"File: {filename}",
        f"Path: {_APP_ROOT / filename}",
        "",
        "## Source (first 60 lines)",
        "",
    ])

    # Try local LLM explanation if the gate is on
    llm_section = _llm_explain(slug, snippet)

    return header + snippet + "\n\n" + llm_section


def _llm_explain(slug: str, snippet: str) -> str:
    try:
        from engel_offline_seed_llm import offline_seed_llm_gate_enabled, run_offline_seed_llm_for_companion_chat
        if not offline_seed_llm_gate_enabled():
            return "## LLM Explanation\n\nOffline LLM gate is off — no explanation available."

        prompt = (
            f"In 2-3 short sentences, what does the Python module '{slug}' do based on this snippet?\n\n"
            + snippet[:800]
        )
        resp = run_offline_seed_llm_for_companion_chat(prompt)
        if resp.guardian_blocked:
            return "## LLM Explanation\n\nGuardian blocked the model response."
        if resp.error:
            return f"## LLM Explanation\n\nModel error: {resp.error}"
        if resp.used_llm and resp.response:
            return "## LLM Explanation\n\n" + resp.response
        return "## LLM Explanation\n\nNo response from model."
    except Exception as exc:
        return f"## LLM Explanation\n\n[unavailable: {exc}]"
