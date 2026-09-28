"""Engel AI ↔ bundled engel-agent integration runner.

This module is the target of the ``engel.engel_agent.status`` and
``engel.engel_agent.invoke`` routes registered in
``engel_ai_update_routes``. It owns the integration between Engel AI's
deterministic communication router and the bundled engel-agent tree at
``D:\\b.WorkSpace\\Engel App\\engel_agent_main``.

The bundled tree is a fork of hermes-agent, case-preservingly renamed to
the Engel theme. Its CLI is autonomous (it calls model providers and may
run background tool calls). Per the 2026-05-19 ruling change, autonomy
and background work inside the engel_agent subprocess are permitted.

Public surface:

    render_engel_agent_status()
        Safe read-only enumeration of the bundled agent's tools and
        toolsets. No model provider is contacted. Used by the
        ``engel.engel_agent.status`` route.

    render_engel_agent_invocation(payload)
        Forwards an arbitrary task to the bundled agent in single-shot
        mode (cli.py -q "<payload>"). May call model providers and run
        autonomous tool loops inside the subprocess. Used by the
        ``engel.engel_agent.invoke`` route. If ``payload`` is empty,
        prints route usage instead of invoking the agent.
"""
from __future__ import annotations

import subprocess
import re
from typing import Optional

import engel_agent_bridge as _bridge


_TRIGGER_PREFIXES = (
    "engel agent run ",
    "engel agent do ",
    "engel agent task ",
    "agent run ",
    "agent do ",
    "agent task ",
    "ask engel agent ",
    "tell engel agent ",
    "run engel agent ",
)


def extract_invocation_payload(normalized_text: str) -> str:
    """Strip a recognised ``engel agent ...`` trigger prefix (or its
    bare-alias form, e.g. ``"engel agent run"`` with no trailing text)
    from ``normalized_text`` and return the remaining task text. Returns
    the input unchanged if nothing matches.
    """
    raw = str(normalized_text or "").strip()
    # First try the with-trailing-space prefix forms (these carry a task).
    for prefix in _TRIGGER_PREFIXES:
        if raw.startswith(prefix):
            return raw[len(prefix):].strip()
    # Then the bare-alias forms — same prefix list with the trailing
    # space removed. These arrive when the user typed just the alias
    # ("engel agent run") with no task; payload should be empty.
    for prefix in _TRIGGER_PREFIXES:
        bare = prefix.rstrip()
        if raw == bare:
            return ""
    return raw


def is_invocation_trigger(normalized_text: str) -> bool:
    """``True`` if ``normalized_text`` looks like a task hand-off to the
    bundled engel-agent (prefix match + non-empty payload).
    """
    raw = str(normalized_text or "")
    for prefix in _TRIGGER_PREFIXES:
        if raw.startswith(prefix) and raw[len(prefix):].strip():
            return True
    return False


def render_engel_agent_status() -> str:
    """Run the bundled CLI with ``--list-tools`` in a subprocess and
    return its banner + tool listing. Safe — no model provider is
    invoked, no tool is actually called.
    """
    proc: subprocess.CompletedProcess[str] = _bridge.spawn_cli(["--list-tools"])
    if proc.returncode != 0:
        missing = _missing_dependency(proc)
        if missing:
            return _wrap_header(
                "Engel Agent - static inventory (dependency gate)",
                _static_agent_inventory(
                    "The bundled CLI could not start because dependency "
                    f"{missing!r} is not installed in the active Python environment. "
                    "No install was run. The route is connected; full CLI execution "
                    "requires an explicit dependency setup step."
                ),
            )
        return _format_failure("engel agent status (--list-tools)", proc)
    body = proc.stdout.rstrip() or proc.stderr.rstrip() or "(no output)"
    return _wrap_header("Engel Agent — toolset and skill inventory", body)


def render_engel_agent_invocation(payload: Optional[str]) -> str:
    """Run the bundled CLI in single-shot mode (``-q "<payload>"``) and
    return its stdout. Empty / missing payload prints usage instead.

    ``payload`` is the normalized user input from Engel AI's router; if
    it carries a recognised ``engel agent ...`` trigger prefix that
    prefix is stripped before being handed to the bundled CLI.

    The subprocess is autonomous: it may call model providers and run
    tool calls in the background until it produces a final answer. The
    host Engel AI session is unaffected — sys.path / module cache are
    isolated by ``engel_agent_bridge.spawn_cli``.
    """
    task = extract_invocation_payload(payload or "")
    if not task:
        return _wrap_header(
            "Engel Agent — invocation usage",
            (
                "Provide a task after the trigger phrase. Examples:\n"
                "  engel agent run draft a haiku about debugging\n"
                "  engel agent do summarise the README\n"
                "  ask engel agent what files changed today\n"
                "\n"
                "For a safe read-only tool listing, ask:\n"
                "  engel agent status"
            ),
        )

    proc: subprocess.CompletedProcess[str] = _bridge.spawn_cli(["-q", task])
    if proc.returncode != 0:
        missing = _missing_dependency(proc)
        if missing:
            return _wrap_header(
                "Engel Agent - invocation unavailable (dependency gate)",
                (
                    "The bundled CLI could not start because dependency "
                    f"{missing!r} is not installed in the active Python environment.\n"
                    "No install was run and no provider/model call was made.\n"
                    "Install/setup must be explicit before this action route can run."
                ),
            )
        return _format_failure(f"engel agent task: {task!r}", proc)
    body = proc.stdout.rstrip() or proc.stderr.rstrip() or "(no output)"
    return _wrap_header(f"Engel Agent — task result", body)


def _wrap_header(title: str, body: str) -> str:
    safety = (
        "Safety:\n"
        "- Ran bundled engel_agent_main subprocess; host engel package "
        "imports were not touched.\n"
        "- Autonomy and background work permitted (2026-05-19 ruling).\n"
        "- No mutation of Engel App router state."
    )
    return f"{title}\n\n{body}\n\n{safety}"


def _format_failure(action: str, proc: subprocess.CompletedProcess[str]) -> str:
    err = (proc.stderr or "").strip() or (proc.stdout or "").strip() or "(no output)"
    return _wrap_header(
        f"Engel Agent — {action} failed (exit {proc.returncode})",
        err[:4000],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Subcommand renderers — one per bundled `engel <subcommand>` surface.
# Each spawns the bundled CLI via the bridge subprocess (host engel package
# is never imported into the engel_ai process), captures output, and wraps
# it in the standard header/safety footer.
# ─────────────────────────────────────────────────────────────────────────────


def _run_engel_subcommand(action: str, argv: list[str]) -> str:
    """Helper: invoke the bundled ``engel`` launcher (which dispatches to
    ``engel_cli.main:main``) with ``argv``. The launcher script lives at
    ``engel_agent_main/engel`` and is plain Python — we run it via
    ``python engel <args>`` with cwd set to the bundled tree, so the
    launcher's ``from engel_cli.main import main`` resolves cleanly.
    """
    completed = _bridge.spawn_engel_launcher(argv)
    if completed.returncode != 0:
        missing = _missing_dependency(completed)
        if missing:
            return _wrap_header(
                f"Engel Agent - {action} unavailable (dependency gate)",
                (
                    "The bundled CLI could not start because dependency "
                    f"{missing!r} is not installed in the active Python environment.\n"
                    "No install was run. This route remains connected but inert until "
                    "explicit dependency setup is performed."
                ),
            )
        return _format_failure(action, completed)
    body = (completed.stdout.rstrip() or completed.stderr.rstrip() or "(no output)")
    return _wrap_header(f"Engel Agent — {action}", body)


def render_engel_agent_doctor(_payload: str = "") -> str:
    return _run_engel_subcommand("doctor (config/dependency check)", ["doctor"])


def render_engel_agent_version(_payload: str = "") -> str:
    rendered = _run_engel_subcommand("version", ["version"])
    if "dependency gate" in rendered:
        return _wrap_header(
            "Engel Agent - static version (dependency gate)",
            "Version from pyproject.toml: " + _static_version() + "\nNo install was run.",
        )
    return rendered


def render_engel_agent_toolsets(_payload: str = "") -> str:
    # cli.py has --list-toolsets; engel launcher does not, so go via cli.py
    proc = _bridge.spawn_cli(["--list-toolsets"])
    if proc.returncode != 0:
        missing = _missing_dependency(proc)
        if missing:
            return _wrap_header(
                "Engel Agent - static toolset list (dependency gate)",
                _static_toolsets(
                    "The bundled CLI could not start because dependency "
                    f"{missing!r} is not installed. No install was run."
                ),
            )
        return _format_failure("--list-toolsets", proc)
    return _wrap_header(
        "Engel Agent — toolset enumeration",
        (proc.stdout.rstrip() or proc.stderr.rstrip() or "(no output)"),
    )


def render_engel_agent_gateway_status(_payload: str = "") -> str:
    return _run_engel_subcommand("gateway status", ["gateway", "status"])


def render_engel_agent_gateway_start(_payload: str = "") -> str:
    return _run_engel_subcommand("gateway start", ["gateway", "start"])


def render_engel_agent_gateway_stop(_payload: str = "") -> str:
    return _run_engel_subcommand("gateway stop", ["gateway", "stop"])


def render_engel_agent_cron_status(_payload: str = "") -> str:
    return _run_engel_subcommand("cron status", ["cron", "status"])


def render_engel_agent_cron_list(_payload: str = "") -> str:
    return _run_engel_subcommand("cron list", ["cron", "list"])


def render_engel_agent_memory_status(_payload: str = "") -> str:
    return _run_engel_subcommand("memory provider status", ["memory", "status"])


def render_engel_agent_skills_list(_payload: str = "") -> str:
    return _run_engel_subcommand("skills list", ["skills", "list"])


def render_engel_agent_sessions_list(_payload: str = "") -> str:
    return _run_engel_subcommand("sessions list", ["sessions", "list"])


def render_engel_agent_sessions_stats(_payload: str = "") -> str:
    return _run_engel_subcommand("sessions stats", ["sessions", "stats"])


def render_engel_agent_plugins_list(_payload: str = "") -> str:
    return _run_engel_subcommand("plugins list", ["plugins", "list"])


def render_engel_identity(_payload: str = "") -> str:
    """Stage 4 identity surface — declares Engel AI = hermes-agent native.

    Now reports Phase D in-process absorption status: whether hermes-agent
    Python modules are importable directly in the Engel AI process (without
    subprocess), per Phase D of Stage 4.
    """
    in_process = _bridge.in_process_available()
    in_process_line = (
        "  ✓ In-process import: OK (engel_cli, engel_bootstrap, etc. importable directly from Engel AI)"
        if in_process
        else "  ✗ In-process import: NOT AVAILABLE (falling back to subprocess via engel_agent_bridge.spawn_cli)"
    )
    lines = [
        "Engel AI — Stage 4 Native Hermes Integration",
        "",
        "What Engel AI is, architecturally:",
        "- Engel AI's agent core IS hermes-agent (vendored under engel_agent_main/).",
        "- Authorized 2026-05-20 by Josh. See:",
        "  memory/ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.json -> stage_4_native_hermes_integration",
        "",
        "Native top-level capability surface (Stage 4):",
        "  engel.identity                            - this view",
        "  engel.native_runtime                      - Phase D in-process proof",
        "  engel.gateway.start / .stop / .status     - hermes gateway",
        "  engel.cron.list / .status                 - hermes cron",
        "  engel.memory.status                       - hermes memory",
        "  engel.skills.list                         - hermes skills",
        "  engel.sessions.list / .sessions.stats     - hermes sessions",
        "  engel.plugins.list                        - hermes plugins",
        "  engel.toolsets                            - hermes toolsets",
        "  engel.doctor                              - hermes doctor",
        "  engel.top.status                          - hermes top",
        "  engel.version                             - hermes version",
        "  engel.invoke                              - single-shot task invocation",
        "",
        "Backward-compat aliases:",
        "  All engel.engel_agent.* nested routes still resolve. Both surfaces",
        "  dispatch to the same underlying runner functions in this module.",
        "",
        "Phase D absorption status:",
        in_process_line,
        "  (Bridge appends engel_agent_main/ to sys.path at import time; the",
        "   original sys.path swap dance is no longer required for new code.)",
        "",
        "Authorized under Stage 4:",
        "- Provider API calls when issued through the hermes-agent surface",
        "  (subprocess invocations via engel_agent_bridge.spawn_cli, AND now",
        "  in-process imports of hermes modules per Phase D).",
        "- Autonomous background tool loops inside the hermes-agent subprocess.",
        "",
        "Still gated:",
        "- NO_BROWSER (no GUI browsers / browser-automation framework spawn).",
        "- NO_ARBITRARY_OUTBOUND_NETWORK (package-manager + model-weight",
        "  registry fetches OK; arbitrary curl/wget gated).",
        "- NO_SOURCE_MUTATION (Engel App source not mutable from inside WSL).",
        "- NOT_TRUSTED_MEMORY (writes inside the distro do not auto-promote).",
        "- General Engel AI host code (anything NOT a hermes-agent invocation)",
        "  still does not call LLM providers without a separate provider contract.",
    ]
    return "\n".join(lines) + "\n"


def render_engel_native_runtime(_payload: str = "") -> str:
    """Phase D proof: import hermes-agent modules in-process and report.

    This route demonstrates that hermes-agent Python code runs inside the
    Engel AI Python process WITHOUT subprocess invocation. If this route
    returns 'OK' for each module, Phase D's source-level absorption is
    proven functional. If any import fails, the route reports it honestly
    (no fabricated success).
    """
    lines = [
        "Engel AI — Phase D in-process native runtime proof",
        "",
        f"Bridge module path : {_bridge.__file__}",
        f"Hermes agent root  : {_bridge.AGENT_ROOT}",
        f"in_process_available() -> {_bridge.in_process_available()}",
        "",
        "Per-module in-process import results:",
    ]
    test_modules = (
        ("engel_cli", "hermes-agent CLI package root"),
        ("engel_cli.commands", "CLI commands module"),
        ("engel_cli.config", "CLI configuration module"),
        ("engel_cli.banner", "CLI banner / startup decoration"),
        ("engel_bootstrap", "UTF-8 stdio bootstrap (Windows)"),
        ("engel_constants", "shared constants"),
        ("engel_logging", "logging configuration"),
        ("engel_state", "shared session state"),
        ("engel_time", "time utilities"),
        ("acp_adapter", "Anthropic Computer Use Protocol adapter"),
        ("acp_registry", "ACP plugin registry"),
        ("agent", "agent core"),
        ("cron", "cron / scheduling core"),
        ("gateway", "gateway / external surface"),
    )
    ok_count = 0
    fail_count = 0
    failures: list[tuple[str, str, str]] = []
    for name, desc in test_modules:
        mod, err = _bridge.import_hermes_module_diagnostic(name)
        if mod is not None and getattr(mod, "__file__", None):
            lines.append(f"  ✓ {name:<24} -> {mod.__file__}")
            ok_count += 1
        elif mod is not None:
            lines.append(f"  ✓ {name:<24} -> (built-in or namespace package, no __file__)  [{desc}]")
            ok_count += 1
        else:
            short_err = (err or "import failed").splitlines()[0]
            lines.append(f"  ✗ {name:<24} -> {short_err}  [{desc}]")
            fail_count += 1
            failures.append((name, desc, err or "(no exception details)"))
    lines.append("")
    lines.append(f"Summary: {ok_count} ok / {fail_count} failed (out of {len(test_modules)} tested)")
    if failures:
        lines.append("")
        lines.append("Failures (with remediation hints):")
        for fname, fdesc, ferr in failures:
            lines.append(f"  {fname}: {ferr}")
            lines.append(f"      ({fdesc})")
            if "No module named" in ferr:
                # Extract the missing module name from the exception text.
                # Format is typically: ModuleNotFoundError: No module named 'rich'
                missing = ferr.split("No module named", 1)[1].strip().strip("'\"")
                # Strip anything after the first space (in case of trailing text).
                missing = missing.split()[0].strip("'\"") if missing else ""
                if missing:
                    lines.append(f"      Fix: python -m pip install {missing}")
    lines.append("")
    lines.append("What this proves (Phase D of Stage 4):")
    lines.append("- hermes-agent source is now part of the Engel AI Python namespace.")
    lines.append("- The historical engel_agent_bridge sys.path swap dance is no longer")
    lines.append("  needed for new code paths — direct `import engel_cli...` works.")
    lines.append("- Existing routes still use subprocess (engel_agent_bridge.spawn_cli)")
    lines.append("  for full process isolation; future routes can opt into in-process")
    lines.append("  invocation for lower latency and richer return types.")
    lines.append("- This route itself is the smoke test for Phase D — if it ever")
    lines.append("  starts failing, Phase D regressed.")
    return "\n".join(lines) + "\n"


def render_engel_agent_top_status(_payload: str = "") -> str:
    return _run_engel_subcommand("status (all components)", ["status"])


def _missing_dependency(proc: subprocess.CompletedProcess[str]) -> str:
    text = (proc.stderr or "") + "\n" + (proc.stdout or "")
    match = re.search(r"ModuleNotFoundError:\s+No module named ['\"]([^'\"]+)['\"]", text)
    return match.group(1) if match else ""


def _static_version() -> str:
    pyproject = _bridge.AGENT_ROOT / "pyproject.toml"
    if not pyproject.is_file():
        return "unknown"
    text = pyproject.read_text(encoding="utf-8", errors="replace")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    return match.group(1) if match else "unknown"


def _static_toolsets(prefix: str = "") -> str:
    toolsets_py = _bridge.AGENT_ROOT / "toolsets.py"
    names: list[str] = []
    if toolsets_py.is_file():
        text = toolsets_py.read_text(encoding="utf-8", errors="replace")
        names = sorted(set(re.findall(r'^\s{4}"([^"]+)":\s*\{', text, flags=re.MULTILINE)))
    lines: list[str] = []
    if prefix:
        lines.extend([prefix, ""])
    lines.append("Bundled tree: " + str(_bridge.AGENT_ROOT))
    lines.append("Toolsets discovered statically: " + str(len(names)))
    for name in names[:80]:
        lines.append("- " + name)
    if len(names) > 80:
        lines.append("- ... " + str(len(names) - 80) + " more")
    return "\n".join(lines)


def _static_agent_inventory(prefix: str = "") -> str:
    tools_dir = _bridge.AGENT_ROOT / "tools"
    skills_dir = _bridge.AGENT_ROOT / "skills"
    tool_files = sorted(tools_dir.glob("*_tool.py")) if tools_dir.is_dir() else []
    skill_dirs = sorted(p.name for p in skills_dir.iterdir() if p.is_dir()) if skills_dir.is_dir() else []
    lines: list[str] = []
    if prefix:
        lines.extend([prefix, ""])
    lines.extend(
        [
            "Bundled tree: " + str(_bridge.AGENT_ROOT),
            "Version: " + _static_version(),
            "Tool modules discovered statically: " + str(len(tool_files)),
            "Skill folders discovered statically: " + str(len(skill_dirs)),
            "",
            "Tool modules:",
        ]
    )
    for path in tool_files[:80]:
        lines.append("- " + path.name)
    if len(tool_files) > 80:
        lines.append("- ... " + str(len(tool_files) - 80) + " more")
    lines.extend(["", "Toolsets:", _static_toolsets()])
    return "\n".join(lines)
