#!/usr/bin/env python3
"""
Engel AI Main — agent harness: tool registry + hook SDK.

Ported concept from OpenClaw (MIT) plugin-sdk (agent-harness, hooks
before-prompt-build / before-tool-call / lifecycle, plugin-tools, mcp-tools).
OpenClaw's philosophy is "lean core, capabilities as plugins"; this brings that
to Engel: a lean tool registry + hook system that ties the ported modules
(failover loop, sub-agents, browser, MCP, cron) into one extensible agent
runtime, plus a plugin loader so new tools/hooks drop in as .py files.

Hook points:
  before_run  — mutate the prompt/context before a run (OpenClaw before-prompt-build)
  before_tool — inspect/deny/mutate a tool call (OpenClaw before-tool-call)
  after_tool  — observe a tool result
  after_run   — post-process the reply

Reimplemented natively in Python; MIT-attributed.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
PLUGIN_DIR = ROOT / "runtime" / "plugins"

# --- Hook system ------------------------------------------------------------
HOOK_POINTS = ("before_run", "before_tool", "after_tool", "after_run")
_HOOKS: dict[str, list] = {p: [] for p in HOOK_POINTS}


def register_hook(point: str, fn: Callable[[dict], dict], priority: int = 100) -> None:
    """Register a hook. `fn(ctx)->ctx` may mutate and return the context dict."""
    if point not in _HOOKS:
        raise ValueError(f"unknown hook point {point}; valid: {HOOK_POINTS}")
    _HOOKS[point].append((priority, fn))
    _HOOKS[point].sort(key=lambda x: x[0])


def fire_hook(point: str, ctx: dict) -> dict:
    for _prio, fn in _HOOKS.get(point, []):
        try:
            out = fn(ctx)
            if isinstance(out, dict):
                ctx = out
        except Exception as exc:
            ctx.setdefault("_hook_errors", []).append(f"{point}:{exc}")
    return ctx


# --- Tool registry ----------------------------------------------------------
@dataclass
class Tool:
    name: str
    description: str
    schema: dict
    fn: Callable[..., Any]


_TOOLS: dict[str, Tool] = {}


def register_tool(name: str, description: str, schema: dict, fn: Callable[..., Any]) -> None:
    _TOOLS[name] = Tool(name, description, schema, fn)


def list_tools() -> list[dict]:
    return [{"name": t.name, "description": t.description, "schema": t.schema} for t in _TOOLS.values()]


def run_tool(name: str, args: Optional[dict] = None) -> dict:
    args = args or {}
    if name not in _TOOLS:
        return {"ok": False, "error": f"unknown tool: {name}", "available": list(_TOOLS)}
    ctx = fire_hook("before_tool", {"tool": name, "args": args})
    if ctx.get("deny"):
        return {"ok": False, "denied": True, "reason": ctx.get("deny_reason", "denied by hook")}
    args = ctx.get("args", args)
    try:
        result = _TOOLS[name].fn(**args)
        out = {"ok": True, "tool": name, "result": result}
    except Exception as exc:
        out = {"ok": False, "tool": name, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
    return fire_hook("after_tool", out)


# --- run_agent (hooks + failover loop) --------------------------------------
def run_agent(prompt: str, chain: Optional[list] = None, *, timeout_s: int = 60, max_tokens: int = 512) -> dict:
    import engel_agent_failover_loop as fl
    ctx = fire_hook("before_run", {"prompt": prompt, "chain": chain})
    result = fl.run_with_failover(ctx.get("prompt", prompt), chain=ctx.get("chain", chain),
                                  timeout_s=timeout_s, max_tokens=max_tokens)
    out = fire_hook("after_run", {"ok": result.ok, "reply": result.reply, "provider": result.provider,
                                  "lane": result.lane, "elapsed_ms": result.elapsed_ms,
                                  "hook_notes": ctx.get("_notes", [])})
    return out


# --- Built-in tools (wrap the ported modules) -------------------------------
def _tool_web_fetch(url: str, max_chars: int = 4000) -> dict:
    if "://" not in url:
        url = "https://" + url
    req = urllib.request.Request(url, headers={"User-Agent": "EngelAIMain/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read().decode("utf-8", errors="replace")
    import re
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", raw, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return {"url": url, "chars": len(text), "text": text[:max_chars]}


def _tool_spawn_subagent(task: str, chain: Optional[list] = None) -> dict:
    import engel_subagents as sa
    r = sa.spawn_subagent(task, chain=chain)
    return {"reply": r.reply, "provider": r.provider, "ok": r.ok, "elapsed_ms": r.elapsed_ms}


def _tool_cron_add(name: str, schedule: str, prompt: str) -> dict:
    import engel_cron as cron
    import uuid
    skind, _, sval = schedule.partition(":")
    sched = {"kind": skind}
    if skind == "every":
        sched["every_s"] = int(sval)
    elif skind == "cron":
        sched["cron"] = sval
    elif skind == "at":
        from datetime import datetime
        sched["at_ms"] = int(datetime.fromisoformat(sval).timestamp() * 1000)
    store = cron.CronStore()
    job = cron.CronJob(id="cron-" + uuid.uuid4().hex[:8], name=name, schedule=sched,
                       payload={"kind": "agentTurn", "prompt": prompt})
    store.add(job)
    return {"job_id": job.id, "name": name}


def _tool_browser_snapshot(url: str) -> dict:
    """One-shot: navigate + snapshot via the browser tool in browser_ai_venv."""
    import subprocess
    venv = ROOT / "runtime" / "browser_ai_venv" / "Scripts" / "python.exe"
    script = ROOT / "tools" / "engel_browser_tool.py"
    cmds = "\n".join([json.dumps({"id": 1, "cmd": "navigate", "url": url}),
                      json.dumps({"id": 2, "cmd": "snapshot"}),
                      json.dumps({"id": 3, "cmd": "stop"})]) + "\n"
    cp = subprocess.run([str(venv), str(script), "--daemon"], input=cmds,
                        capture_output=True, text=True, timeout=90, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    elements = []
    for ln in cp.stdout.splitlines():
        try:
            o = json.loads(ln)
        except Exception:
            continue
        if o.get("id") == 2 and o.get("ok"):
            elements = o.get("elements", [])
    return {"url": url, "elements": elements[:20]}


def _tool_orchestrate_goal(goal: str) -> dict:
    """Fan a multi-part goal into parallel read-only Conductor lanes
    (docs/ENGEL_ORCHESTRA_DESIGN.md) and return the merged outcome."""
    import engel_orchestra as eo
    receipt = eo.orchestrate(goal)
    return {
        "status": receipt.get("status", ""),
        "ok": bool(receipt.get("ok")),
        "lanes": len(receipt.get("lanes", [])),
        "executed_routes": receipt.get("executed_routes", 0),
        "receipt": receipt.get("receipt_path", ""),
    }


def _tool_execute_goal(goal: str) -> dict:
    """Use Engel's native dispatch spine. Without a model callback it still
    executes exact safe routes and saved plans, and reports planner absence
    honestly for work that needs drafting."""
    import engel_agent_kernel as kernel

    receipt = kernel.run_goal(goal)
    return {
        "status": receipt.get("status", ""),
        "ok": bool(receipt.get("ok")),
        "engines": receipt.get("engines_used", []),
        "lanes": len(receipt.get("lanes", [])),
        "receipt": receipt.get("receipt_path", ""),
    }


def _register_builtins() -> None:
    register_tool("web_fetch", "Fetch a URL and return its readable text.",
                  {"url": "string", "max_chars": "int?"}, _tool_web_fetch)
    register_tool("spawn_subagent", "Run a sub-task on another AI (failover chain) and return its reply.",
                  {"task": "string", "chain": "string[]?"}, _tool_spawn_subagent)
    register_tool("orchestrate_goal", "Fan a multi-part goal ('a | b | c') into parallel read-only Conductor lanes and merge the results.",
                  {"goal": "string"}, _tool_orchestrate_goal)
    register_tool("execute_goal", "Automatically dispatch one goal to Engel's safe route, Conductor, Orchestra, or Code Forge.",
                  {"goal": "string"}, _tool_execute_goal)
    register_tool("cron_add", "Schedule a recurring agent turn (every:<s>|cron:<expr>|at:<iso>).",
                  {"name": "string", "schedule": "string", "prompt": "string"}, _tool_cron_add)
    register_tool("browser_snapshot", "Open a URL in a real browser and list its interactive elements.",
                  {"url": "string"}, _tool_browser_snapshot)


def load_plugins(plugin_dir: Optional[Path] = None) -> list[str]:
    """Load plugin .py files (each may call register_hook / register_tool)."""
    plugin_dir = plugin_dir or PLUGIN_DIR
    loaded = []
    if not plugin_dir.exists():
        return loaded
    for f in sorted(plugin_dir.glob("*.py")):
        try:
            spec = importlib.util.spec_from_file_location(f"engel_plugin_{f.stem}", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore
            if hasattr(mod, "register"):
                mod.register(sys.modules[__name__])
            loaded.append(f.name)
        except Exception as exc:
            sys.stderr.write(f"[engel] plugin {f.name} failed: {exc}\n")
    return loaded


_register_builtins()


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print("=== registered tools ===")
    for t in list_tools():
        print(f"  {t['name']:16} — {t['description']}")
    print("loaded plugins:", load_plugins() or "(none)")
